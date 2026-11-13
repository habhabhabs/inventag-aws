"""
Upload generated reports to S3, and (opt-in) manage an expiry lifecycle rule.

Security properties:

* Every object is written with server-side encryption (``AES256`` or
  ``aws:kms``); public ACLs are refused.
* Under the read-only guard, only the uploader's own S3 client is allowed
  ``PutObject`` (plus the lifecycle calls when the caller opted in to them).
* The lifecycle rule is merged into the bucket's existing configuration by
  rule ID. ``PutBucketLifecycleConfiguration`` replaces the whole
  configuration, so writing a single rule would delete everyone else's rules.
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from ..security.read_only_guard import ReadOnlyGuard, ReadOnlyViolationError
from ..security.safe_output import safe_filename_component

logger = logging.getLogger(__name__)

LIFECYCLE_RULE_ID = "InvenTagBOMLifecycle"
VALID_ENCRYPTION = ("AES256", "aws:kms")
_BUCKET_RE = re.compile(
    r"^(?!xn--)(?!sthree-)(?!.*-s3alias$)[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
)


class S3UploadError(Exception):
    """Raised for invalid S3 upload configuration."""


def validate_bucket_name(bucket: str) -> str:
    if not isinstance(bucket, str) or not _BUCKET_RE.match(bucket) or ".." in bucket:
        raise S3UploadError(f"Invalid S3 bucket name: {bucket!r}")
    return bucket


def normalize_key_prefix(prefix: Optional[str]) -> str:
    """Strip leading/trailing slashes and drop empty, '.' and '..' segments."""
    parts = [p for p in (prefix or "").split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def build_object_key(prefix: str, timestamp: str, file_name: str) -> str:
    parts = [
        normalize_key_prefix(prefix),
        timestamp,
        safe_filename_component(file_name),
    ]
    return "/".join(p for p in parts if p)


def upload_files(
    s3_client,
    files: List[str],
    bucket: str,
    key_prefix: str = "bom-reports",
    encryption: str = "AES256",
    kms_key_id: Optional[str] = None,
    storage_class: str = "STANDARD",
    public_read: bool = False,
    timestamp: Optional[str] = None,
) -> Dict[str, Any]:
    """Upload ``files`` to ``s3://bucket/key_prefix/<timestamp>/<name>``.

    Returns ``{"uploaded": [{"file", "key", "url"}], "errors": [{"file", "error"}]}``.
    """
    validate_bucket_name(bucket)
    if public_read:
        raise S3UploadError(
            "Public-read uploads are not supported: BOM reports describe your "
            "infrastructure and must not be public. Share them with a presigned "
            "URL or bucket policy instead."
        )
    if encryption not in VALID_ENCRYPTION:
        raise S3UploadError(
            f"Unsupported S3 encryption {encryption!r}; use one of {VALID_ENCRYPTION}"
        )

    ReadOnlyGuard.allow_on_client(s3_client, {"PutObject"})
    timestamp = timestamp or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    region = (
        getattr(getattr(s3_client, "meta", None), "region_name", None) or "us-east-1"
    )
    result: Dict[str, Any] = {"uploaded": [], "errors": []}

    for file_path in files:
        path = Path(file_path)
        try:
            if not path.is_file():
                raise FileNotFoundError(f"Report file not found: {file_path}")
            key = build_object_key(key_prefix, timestamp, path.name)
            params = {
                "Bucket": bucket,
                "Key": key,
                "ServerSideEncryption": encryption,
            }
            if encryption == "aws:kms" and kms_key_id:
                params["SSEKMSKeyId"] = kms_key_id
            if storage_class and storage_class != "STANDARD":
                params["StorageClass"] = storage_class
            with open(path, "rb") as body:
                s3_client.put_object(Body=body, **params)
            url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
            result["uploaded"].append({"file": str(path), "key": key, "url": url})
            logger.info(f"Uploaded {path.name} to s3://{bucket}/{key}")
        except Exception as e:  # report every failure; caller decides exit code
            logger.error(f"Failed to upload {file_path} to s3://{bucket}: {e}")
            result["errors"].append({"file": str(path), "error": str(e)})
    return result


def merge_lifecycle_rule(
    existing_rules: List[Dict[str, Any]], key_prefix: str, days: int
) -> List[Dict[str, Any]]:
    """Return ``existing_rules`` with InvenTag's expiry rule added or updated."""
    if days <= 0:
        raise ValueError("Lifecycle days must be positive")
    prefix = normalize_key_prefix(key_prefix)
    new_rule = {
        "ID": LIFECYCLE_RULE_ID,
        "Status": "Enabled",
        "Filter": {"Prefix": f"{prefix}/" if prefix else ""},
        "Expiration": {"Days": int(days)},
    }
    merged = [r for r in existing_rules if r.get("ID") != LIFECYCLE_RULE_ID]
    merged.append(new_rule)
    return merged


def ensure_lifecycle_rule(
    s3_client,
    bucket: str,
    key_prefix: str,
    days: int,
    *,
    allow_bucket_writes: bool = False,
) -> bool:
    """Add/update InvenTag's expiry rule without removing the bucket's other rules.

    This changes the bucket's configuration (a write), so it refuses unless
    the caller passes ``allow_bucket_writes=True``. It never opens the
    read-only guard: under the guard (every CLI run) the write stays blocked.

    Returns True if the configuration was written.
    """
    if allow_bucket_writes is not True:
        raise ReadOnlyViolationError(
            "s3",
            "PutBucketLifecycleConfiguration",
            "ensure_lifecycle_rule() changes the bucket's lifecycle configuration; "
            "pass allow_bucket_writes=True to confirm",
        )
    validate_bucket_name(bucket)
    try:
        current = s3_client.get_bucket_lifecycle_configuration(Bucket=bucket)
        existing = current.get("Rules", [])
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "NoSuchLifecycleConfiguration":
            logger.warning(
                f"Not changing lifecycle of s3://{bucket}: could not read the "
                f"existing configuration ({e}); refusing to overwrite it blind"
            )
            return False
        existing = []
    rules = merge_lifecycle_rule(existing, key_prefix, days)
    if rules == existing:
        return False
    s3_client.put_bucket_lifecycle_configuration(
        Bucket=bucket, LifecycleConfiguration={"Rules": rules}
    )
    logger.info(
        f"Set lifecycle rule {LIFECYCLE_RULE_ID} on s3://{bucket} "
        f"({days} days); kept {len(rules) - 1} existing rule(s)"
    )
    return True
