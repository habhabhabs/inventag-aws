"""
Configuration validation for InvenTag CLI.
"""

import json
import os
import stat
import yaml
import logging
from pathlib import Path

from ..reporting.settings_loader import (
    Locator,
    SettingsFileError,
    did_you_mean,
    load_settings_file,
)
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, field

from ..core import AccountCredentials, MultiAccountConfig
from ..reporting import BOMProcessingConfig
from .errors import S3_BUCKET_RULES_URL, UsageError


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    config: Optional[Dict[str, Any]] = None
    # CLI option problems as contract errors (exit 2); ``errors`` holds the
    # same problems as one-line strings.
    usage_errors: List[UsageError] = field(default_factory=list)


ACCOUNT_KEYS = (
    "account_id",
    "account_name",
    "access_key_id",
    "secret_access_key",
    "session_token",
    "profile_name",
    "role_arn",
    "external_id",
    "regions",
    "services",
    "tags",
)
ACCOUNTS_TOP_KEYS = ("accounts", "settings")
SETTINGS_KEYS = (
    "max_concurrent_accounts",
    "account_processing_timeout",
    "output_directory",
)


class ConfigValidator:
    """Validates InvenTag configuration files and CLI arguments.

    Problems in a file are one line each, ``file:line: key: problem``, built
    with :class:`~inventag.reporting.settings_loader.Locator`.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _is_tag_policy_file(self, config: Dict[str, Any]) -> bool:
        """Check if this looks like a tag policy file instead of tag mappings."""
        tag_policy_indicators = [
            "required_tags",
            "service_specific",
            "exemptions",
            "policies",
            "compliance_rules",
        ]
        return any(key in config for key in tag_policy_indicators)

    def validate_accounts_file(self, file_path: str) -> ValidationResult:
        """
        Validate accounts configuration file.

        Args:
            file_path: Path to accounts configuration file

        Returns:
            ValidationResult with validation status and any errors/warnings
        """
        result = ValidationResult(is_valid=False)

        try:
            path = Path(file_path)
            if not path.exists():
                result.errors.append(f"Accounts file not found: {file_path}")
                return result

            # UTF-8 with or without BOM, duplicate keys refused (with the
            # line), empty files and non-mapping top levels named, size cap.
            try:
                config = load_settings_file(path, "accounts file")
            except SettingsFileError as e:
                result.errors.append(str(e))
                return result

            result.config = config
            loc = Locator(file_path)

            # Validate structure
            if not isinstance(config, dict):
                result.errors.append(
                    loc.message((), "the file must be a mapping with an accounts list")
                )
                return result

            for key in config:
                if key not in ACCOUNTS_TOP_KEYS:
                    result.warnings.append(
                        loc.message(
                            (key,),
                            f"unknown key{did_you_mean(key, ACCOUNTS_TOP_KEYS)}"
                            " It is ignored.",
                        )
                    )

            if "accounts" not in config:
                result.errors.append(
                    loc.message(
                        ("accounts",),
                        "is required: add a top-level 'accounts:' list",
                    )
                )
                return result

            accounts = config["accounts"]
            if not isinstance(accounts, list):
                result.errors.append(loc.message(("accounts",), "must be a list"))
                return result

            if not accounts:
                result.errors.append(
                    loc.message(("accounts",), "needs at least one account")
                )
                return result

            # Validate each account
            seen_ids: Dict[str, int] = {}
            for i, account in enumerate(accounts):
                account_errors = self._validate_account_config(account, i, loc)
                result.errors.extend(account_errors)
                if not isinstance(account, dict):
                    continue
                for key in account:
                    if key not in ACCOUNT_KEYS:
                        result.warnings.append(
                            loc.message(
                                ("accounts", i, key),
                                f"unknown key{did_you_mean(key, ACCOUNT_KEYS)}"
                                " It is ignored.",
                            )
                        )
                account_id = account.get("account_id")
                if isinstance(account_id, str) and account_id.strip():
                    if account_id in seen_ids:
                        result.warnings.append(
                            loc.message(
                                ("accounts", i, "account_id"),
                                f"'{account_id}' is already listed at "
                                f"accounts[{seen_ids[account_id]}]; the account "
                                "is scanned once, with the first entry",
                            )
                        )
                    else:
                        seen_ids[account_id] = i
                if isinstance(account, dict) and not any(
                    key in account
                    for key in ("access_key_id", "profile_name", "role_arn")
                ):
                    result.warnings.append(
                        f"Account {i + 1}: no credentials given; InvenTag will assume "
                        "the --cross-account-role role (default "
                        "InvenTagCrossAccountRole) in this account, or use the default "
                        "credentials only if they belong to this account"
                    )
                regions = account.get("regions")
                if isinstance(regions, list):
                    result.warnings.extend(self._region_warnings(regions, i, loc))

            warning = self._secret_file_permission_warning(path, accounts)
            if warning:
                result.warnings.append(warning)

            # Validate global settings
            if "settings" in config:
                settings = config["settings"]
                if isinstance(settings, dict):
                    for key in settings:
                        if key not in SETTINGS_KEYS:
                            result.warnings.append(
                                loc.message(
                                    ("settings", key),
                                    f"unknown key{did_you_mean(key, SETTINGS_KEYS)}"
                                    " It is ignored.",
                                )
                            )
                result.errors.extend(self._validate_settings_config(settings, loc))

            result.is_valid = len(result.errors) == 0

        except Exception as e:
            result.errors.append(f"Unexpected error validating accounts file: {e}")

        return result

    @staticmethod
    def _region_warnings(regions, index, loc) -> List[str]:
        """Warn about region names AWS does not have (a typo scans nothing)."""
        from .usage_checks import known_regions

        known = known_regions()
        out = []
        for position, name in enumerate(regions):
            if isinstance(name, str) and name.strip() and name.strip() not in known:
                out.append(
                    loc.message(
                        ("accounts", index, "regions", position),
                        f"unknown region '{name}'"
                        f"{did_you_mean(name.strip(), known)} No region of "
                        "that name will answer.",
                    )
                )
        return out

    @staticmethod
    def _secret_file_permission_warning(path: Path, accounts) -> Optional[str]:
        """Warn when a file with secret access keys can be read by others."""
        has_secrets = any(
            isinstance(a, dict)
            and (a.get("secret_access_key") or a.get("session_token"))
            for a in accounts
        )
        if not has_secrets or os.name != "posix":
            return None
        mode = stat.S_IMODE(path.stat().st_mode)
        if not mode & 0o077:
            return None
        return (
            f"{path} contains secret access keys and other users can read it "
            f"(mode {mode:04o}). Run: chmod 600 {path}. Prefer profile_name or "
            "role_arn over access keys in a file."
        )

    def _validate_account_config(
        self, account: Dict[str, Any], index: int, loc: Optional[Locator] = None
    ) -> List[str]:
        """Validate individual account configuration.

        With ``loc`` a problem reads ``file:line: accounts[1].account_id: ...``;
        without it (config templates) ``Account 2: 'account_id' ...``.
        """
        errors: List[str] = []

        def err(key: str, text: str) -> None:
            if loc is not None:
                errors.append(loc.message(("accounts", index, key), text))
            else:
                errors.append(f"Account {index + 1}: '{key}' {text}")

        if not isinstance(account, dict):
            if loc is not None:
                errors.append(
                    loc.message(
                        ("accounts", index),
                        "must be a mapping with at least an account_id",
                    )
                )
            else:
                errors.append(f"Account {index + 1}: must be a mapping")
            return errors

        # Required fields
        if "account_id" not in account:
            err("account_id", "is required")
        elif (
            not isinstance(account["account_id"], str)
            or not account["account_id"].strip()
        ):
            err("account_id", 'must be text, so put it in quotes: "123456789012"')

        # Optional fields validation
        if "account_name" in account and not isinstance(account["account_name"], str):
            err("account_name", "must be a string")

        if "regions" in account:
            if not isinstance(account["regions"], list):
                err("regions", "must be a list")
            elif not all(isinstance(r, str) for r in account["regions"]):
                err("regions", "must contain only strings")

        if "services" in account:
            if not isinstance(account["services"], list):
                err("services", "must be a list")
            elif not all(isinstance(s, str) for s in account["services"]):
                err("services", "must contain only strings")

        if "tags" in account:
            if not isinstance(account["tags"], dict):
                err("tags", "must be a mapping")
            elif not all(
                isinstance(k, str) and isinstance(v, str)
                for k, v in account["tags"].items()
            ):
                err("tags", "keys and values must all be strings")

        # Credential validation
        has_keys = "access_key_id" in account and "secret_access_key" in account
        has_profile = "profile_name" in account
        has_role = "role_arn" in account

        if has_keys:
            for key in ("access_key_id", "secret_access_key"):
                if not isinstance(account[key], str) or not account[key].strip():
                    err(key, "must be a non-empty string")

            if "session_token" in account and not isinstance(
                account["session_token"], str
            ):
                err("session_token", "must be a string")

        if has_profile and not isinstance(account["profile_name"], str):
            err("profile_name", "must be a string")

        if has_role:
            if (
                not isinstance(account["role_arn"], str)
                or not account["role_arn"].strip()
            ):
                err("role_arn", "must be a non-empty string")
            else:
                from ..security.arn import InvalidRoleError, validate_role_arn

                try:
                    validate_role_arn(account["role_arn"].strip())
                except InvalidRoleError as e:
                    err("role_arn", str(e))
            if "external_id" in account and not isinstance(account["external_id"], str):
                err("external_id", "must be a string")

        return errors

    def _validate_settings_config(
        self, settings: Any, loc: Optional[Locator] = None
    ) -> List[str]:
        """Validate global settings configuration."""
        errors: List[str] = []

        def err(key: str, text: str) -> None:
            if loc is not None:
                errors.append(loc.message(("settings", key), text))
            else:
                errors.append(f"'{key}' {text}")

        if not isinstance(settings, dict):
            if loc is not None:
                errors.append(loc.message(("settings",), "must be a mapping"))
            return errors

        if "max_concurrent_accounts" in settings:
            max_concurrent = settings["max_concurrent_accounts"]
            if not isinstance(max_concurrent, int) or max_concurrent < 1:
                err("max_concurrent_accounts", "must be a whole number of 1 or more")

        if "account_processing_timeout" in settings:
            timeout = settings["account_processing_timeout"]
            if not isinstance(timeout, int) or timeout < 60:
                err(
                    "account_processing_timeout",
                    "must be a whole number of seconds, 60 or more",
                )

        if "output_directory" in settings:
            if not isinstance(settings["output_directory"], str):
                err("output_directory", "must be a string")

        return errors

    def validate_service_descriptions_file(self, file_path: str) -> ValidationResult:
        """Validate service descriptions configuration file."""
        result = ValidationResult(is_valid=False)

        try:
            path = Path(file_path)
            if not path.exists():
                result.errors.append(
                    f"Service descriptions file not found: {file_path}"
                )
                return result

            # UTF-8 with or without BOM, duplicate keys refused (with the
            # line), empty files and non-mapping top levels named, size cap.
            try:
                config = load_settings_file(path, "service descriptions file")
            except SettingsFileError as e:
                result.errors.append(str(e))
                return result

            result.config = config
            loc = Locator(file_path)

            def err(path_, text):
                result.errors.append(loc.message(path_, text))

            if not isinstance(config, dict):
                err((), "must be a mapping of service names to descriptions")
                return result

            # Validate structure
            for service, service_config in config.items():
                if not isinstance(service, str):
                    err((service,), "the service name must be text")
                    continue

                if not isinstance(service_config, dict):
                    err((service,), "must be a mapping")
                    continue

                # Validate service-level fields
                if "default_description" in service_config:
                    if not isinstance(service_config["default_description"], str):
                        err((service, "default_description"), "must be a string")

                # Validate resource_types if present
                if "resource_types" in service_config:
                    resource_types = service_config["resource_types"]
                    if not isinstance(resource_types, dict):
                        err((service, "resource_types"), "must be a mapping")
                    else:
                        for resource_type, description in resource_types.items():
                            if not isinstance(resource_type, str):
                                err(
                                    (service, "resource_types"),
                                    f"resource type {resource_type!r} must be text",
                                )
                            elif not isinstance(description, str):
                                err(
                                    (service, "resource_types", resource_type),
                                    "the description must be a string",
                                )

            result.is_valid = len(result.errors) == 0

        except Exception as e:
            result.errors.append(f"Error validating service descriptions file: {e}")

        return result

    def validate_tag_mappings_file(self, file_path: str) -> ValidationResult:
        """Validate tag mappings configuration file."""
        result = ValidationResult(is_valid=False)

        try:
            path = Path(file_path)
            if not path.exists():
                result.errors.append(f"Tag mappings file not found: {file_path}")
                return result

            # UTF-8 with or without BOM, duplicate keys refused (with the
            # line), empty files and non-mapping top levels named, size cap.
            try:
                config = load_settings_file(path, "tag mappings file")
            except SettingsFileError as e:
                result.errors.append(str(e))
                return result

            result.config = config
            loc = Locator(file_path)

            def err(path_, text):
                result.errors.append(loc.message(path_, text))

            if not isinstance(config, dict):
                err((), "must be a mapping")
                return result

            # Check if user accidentally used a tag policy file instead of tag mappings
            if self._is_tag_policy_file(config):
                err(
                    (),
                    "this is a tag policy file, not a tag mappings file. Tag "
                    "mappings map tag keys to column names, for example "
                    "'Owner: {column_name: Resource Owner}'. Use a tag policy "
                    "with --template, or start from "
                    "tag_to_column_mappings_example.yaml",
                )
                return result

            # Check if this has the tag_mappings key (new format)
            if "tag_mappings" in config:
                tag_mappings = config["tag_mappings"]
                if not isinstance(tag_mappings, list):
                    err(("tag_mappings",), "must be a list of mappings")
                    return result

                # Validate each tag mapping in the list
                for i, mapping in enumerate(tag_mappings):
                    if not isinstance(mapping, dict):
                        err(("tag_mappings", i), "must be a mapping")
                        continue

                    for field_name in ("tag", "name"):
                        if field_name not in mapping:
                            err(("tag_mappings", i, field_name), "is required")
                        elif not isinstance(mapping[field_name], str):
                            err(("tag_mappings", i, field_name), "must be a string")

                    for field_name in ("description", "default_value"):
                        if field_name in mapping and not isinstance(
                            mapping[field_name], str
                        ):
                            err(("tag_mappings", i, field_name), "must be a string")
            else:
                # Legacy format validation (dictionary of tag->column mappings)
                for tag_key, mapping in config.items():
                    if not isinstance(tag_key, str):
                        err((tag_key,), "the tag key must be text")
                        continue

                    if not isinstance(mapping, dict):
                        err((tag_key,), "must be a mapping with a column_name")
                        continue

                    if "column_name" not in mapping:
                        err((tag_key, "column_name"), "is required")
                    elif not isinstance(mapping["column_name"], str):
                        err((tag_key, "column_name"), "must be a string")

                    for field_name in ("default_value", "description"):
                        if field_name in mapping and not isinstance(
                            mapping[field_name], str
                        ):
                            err((tag_key, field_name), "must be a string")

            result.is_valid = len(result.errors) == 0

        except Exception as e:
            result.errors.append(f"Error validating tag mappings file: {e}")

        return result

    def validate_cli_arguments(self, args) -> ValidationResult:
        """Validate CLI arguments for consistency and completeness.

        A bad option value is a usage error (exit 2): ``result.usage_errors``
        holds the full messages and ``result.errors`` their first lines.
        """
        result = ValidationResult(is_valid=True)

        def bad(subject, what, instead, more, why=None):
            error = UsageError(subject, what, instead, more, why=why)
            result.usage_errors.append(error)
            result.errors.append(error.first_line())

        # Check format options
        format_options = [
            args.create_word,
            args.create_excel,
            getattr(args, "create_google_docs", False),
            getattr(args, "create_google_sheets", False),
        ]
        if not any(format_options):
            result.warnings.append(
                "No output format specified. Use --create-word or --create-excel"
            )

        # Check account specification
        account_options = [
            bool(args.accounts_file),
            args.accounts_prompt,
            bool(args.cross_account_role),
        ]
        if not any(account_options):
            result.warnings.append(
                "No account specification method provided. Using default AWS credentials."
            )

        # Validate S3 options
        if args.s3_bucket and not args.s3_key_prefix:
            result.warnings.append(
                "S3 bucket specified without key prefix. Using default prefix."
            )

        if args.s3_bucket:
            from ..core.s3_upload import S3UploadError, validate_bucket_name

            try:
                validate_bucket_name(args.s3_bucket)
            except S3UploadError:
                bad(
                    "--s3-bucket",
                    f"'{args.s3_bucket}' is not a valid bucket name",
                    "use a bucket name that follows the S3 naming rules, or "
                    "list yours with: aws s3 ls",
                    S3_BUCKET_RULES_URL,
                    why="names use 3-63 lower-case letters, digits, dots and "
                    "hyphens",
                )

        if args.s3_key_prefix and not args.s3_bucket:
            bad(
                "--s3-key-prefix",
                "has no effect without --s3-bucket",
                "add --s3-bucket NAME, or remove --s3-key-prefix.",
                "reference/cli#s3-upload",
            )

        # Validate parallel processing (0 is not "unset": it is invalid)
        value = args.max_concurrent_accounts
        if value is not None and value < 1:
            bad(
                "--max-concurrent-accounts",
                f"must be 1 or more (got {value})",
                "use a whole number from 1 up, for example "
                "--max-concurrent-accounts 4.",
                "guides/scan-multiple-accounts#tune-the-run",
            )

        # Validate timeouts
        value = args.account_processing_timeout
        if value is not None and value < 60:
            bad(
                "--account-processing-timeout",
                f"must be 60 or more seconds (got {value})",
                "use 60 or more, for example --account-processing-timeout 1800.",
                "guides/run-a-scan#time-limit-and-parallel-accounts",
            )
        value = getattr(args, "credential_timeout", None)
        if value is not None and value < 1:
            bad(
                "--credential-timeout",
                f"must be 1 or more seconds (got {value})",
                "use 1 or more, for example --credential-timeout 30.",
                "reference/cli#credentials",
            )

        value = getattr(args, "resume_max_age_hours", None)
        if value is not None and not 0 < value <= 168:
            bad(
                "--resume-max-age-hours",
                f"must be above 0 and at most 168 hours (got {value})",
                "use a number of hours up to 168, for example "
                "--resume-max-age-hours 24.",
                "guides/run-a-scan#continue-after-a-failed-run",
            )

        account_tags = getattr(args, "account_tags", None)
        if account_tags:
            example = (
                "pass a JSON object of text values, for example "
                '--account-tags \'{"Environment": "prod"}\'.'
            )
            try:
                tags = json.loads(account_tags)
            except json.JSONDecodeError as e:
                bad(
                    "--account-tags",
                    f"is not valid JSON ({e.msg} at position {e.pos})",
                    example,
                    "reference/cli#what-to-scan",
                )
            else:
                if not isinstance(tags, dict) or not all(
                    isinstance(k, str) and isinstance(v, str) for k, v in tags.items()
                ):
                    bad(
                        "--account-tags",
                        "must be a JSON object whose keys and values are text",
                        example,
                        "reference/cli#what-to-scan",
                    )

        result.is_valid = len(result.errors) == 0

        return result
