"""Checks of the command line that run before any AWS call.

``collect(args)`` returns one :class:`UsageError` for each problem found in the
options themselves (conflicts, refused options, a role name without accounts,
unknown region names, folders that cannot be written). ``apply_implied``
turns options whose intent is clear into the options they need, and says so
with one ``inventag: note:`` line.

Everything here is local: no AWS or Google call is made.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import List, Optional

from ..security.arn import (
    InvalidRoleError,
    is_role_arn,
    validate_role_arn,
    validate_role_name,
)
from . import safety
from .errors import UsageError, note

S3_UPLOAD = "reference/cli#s3-upload"
MANY_ACCOUNTS = "guides/scan-multiple-accounts"
RUN_A_SCAN = "guides/run-a-scan"
GOOGLE_GUIDE = "guides/google-sheets-and-docs"
CLI_REFERENCE = "reference/cli"


def _validate_only(args) -> bool:
    return bool(
        getattr(args, "validate_templates", False)
        or getattr(args, "validate_config", False)
        or getattr(args, "validate_config_only", False)
        or getattr(args, "validate_credentials", False)
    )


# ------------------------------------------------------------ implied options


def apply_implied(args) -> List[str]:
    """Set the options a given option needs; return the notes printed.

    ``--word-template`` implies ``--create-word``, ``--excel-template`` implies
    ``--create-excel``, ``--risk-threshold`` implies
    ``--enable-security-analysis`` and ``--s3-kms-key-id`` implies
    ``--s3-encryption aws:kms`` when the encryption was not typed. Also turns
    the untyped ``--s3-encryption`` (None) into its default, ``AES256``.
    """
    notes: List[str] = []
    if not _validate_only(args):
        if getattr(args, "word_template", None) and not args.create_word:
            args.create_word = True
            notes.append("--word-template implies --create-word.")
        if getattr(args, "excel_template", None) and not args.create_excel:
            args.create_excel = True
            notes.append("--excel-template implies --create-excel.")
    if args.risk_threshold and not args.enable_security_analysis:
        args.enable_security_analysis = True
        notes.append("--risk-threshold implies --enable-security-analysis.")
    if args.s3_kms_key_id and getattr(args, "s3_encryption", None) is None:
        args.s3_encryption = "aws:kms"
        notes.append("--s3-kms-key-id implies --s3-encryption aws:kms.")
    if getattr(args, "s3_encryption", None) is None:
        args.s3_encryption = "AES256"
    for text in notes:
        note(text)
    return notes


# ------------------------------------------------------- conflicts and stops


def _role_errors(args) -> List[UsageError]:
    errors: List[UsageError] = []
    role = args.cross_account_role
    if not role:
        return errors
    try:
        if is_role_arn(role):
            validate_role_arn(role)
        else:
            validate_role_name(role)
    except InvalidRoleError as e:
        errors.append(
            UsageError(
                "--cross-account-role",
                str(e),
                "pass a role name (for example InvenTagReadOnly) with "
                "--accounts-file, or a full role ARN: "
                "arn:aws:iam::<account-id>:role/<name>",
                MANY_ACCOUNTS,
            )
        )
        return errors
    if is_role_arn(role) and (args.accounts_file or args.accounts_prompt):
        errors.append(
            UsageError(
                "--cross-account-role",
                "a full role ARN names one account and cannot be combined with "
                "--accounts-file or --accounts-prompt",
                "give a role name to use in every account, or put role_arn in "
                "the accounts file.",
                MANY_ACCOUNTS,
            )
        )
    elif not is_role_arn(role) and not (args.accounts_file or args.accounts_prompt):
        errors.append(
            UsageError(
                "--cross-account-role",
                f"'{role}' is a role name; it needs --accounts-file to know "
                "which accounts to use",
                "pass the full role ARN (arn:aws:iam::<account-id>:role/"
                f"{role}), or list the account IDs in --accounts-file.",
                MANY_ACCOUNTS,
            )
        )
    return errors


def _conflict_errors(args) -> List[UsageError]:
    errors: List[UsageError] = []
    if args.accounts_file and args.accounts_prompt:
        errors.append(
            UsageError(
                "--accounts-file and --accounts-prompt",
                "give one of them, not both",
                "keep --accounts-file to read the accounts from the file, or "
                "--accounts-prompt to type them.",
                MANY_ACCOUNTS,
            )
        )
    if args.s3_kms_key_id and getattr(args, "s3_encryption", None) == "AES256":
        errors.append(
            UsageError(
                "--s3-kms-key-id",
                "needs --s3-encryption aws:kms, but you gave --s3-encryption AES256",
                "remove one of the two: drop --s3-encryption AES256 to use the "
                "KMS key, or drop --s3-kms-key-id.",
                S3_UPLOAD,
            )
        )
    if args.resume and args.disable_state_management:
        errors.append(
            UsageError(
                "--resume",
                "needs state management, because the saved results live in the "
                "state folder",
                "remove --disable-state-management, or remove --resume.",
                f"{RUN_A_SCAN}#continue-after-a-failed-run",
            )
        )
    return errors


def _template_errors(args) -> List[UsageError]:
    if args.validate_templates and not (args.word_template or args.excel_template):
        return [
            UsageError(
                "--validate-templates",
                "needs a layout file to check",
                "give --word-template PATH or --excel-template PATH, or run "
                "'inventag templates validate NAME|PATH'.",
                f"{CLI_REFERENCE}#report-layout-files",
            )
        ]
    return []


_GOOGLE_LIBS = 'pip install "inventag-aws[google]"'


def _google_errors(args) -> List[UsageError]:
    from ..reporting.google_output import validate_options
    from .main import google_options_from_args

    options = google_options_from_args(args)
    if options is None:
        stray = [
            flag
            for flag, used in (
                ("--google-credentials", args.google_credentials),
                ("--google-oauth-client", args.google_oauth_client),
                ("--google-folder-id", args.google_folder_id),
                ("--google-share-with", args.google_share_with),
                ("--google-share-anyone", args.google_share_anyone),
                ("--google-title", args.google_title),
            )
            if used
        ]
        if stray:
            return [
                UsageError(
                    ", ".join(stray),
                    "needs --create-google-sheets or --create-google-docs",
                    "add --create-google-sheets or --create-google-docs, or "
                    "remove " + ("them" if len(stray) > 1 else "it") + ".",
                    GOOGLE_GUIDE,
                )
            ]
        return []
    errors = []
    for problem in validate_options(options):
        subject: Optional[str] = None
        what = problem
        if problem.startswith("--") and ": " in problem.split(" ")[0] + " ":
            subject, what = problem.split(": ", 1)
        if "not both" in problem:
            instead = "keep --google-credentials (service account) or --google-oauth-client, not both."
        elif "file not found" in problem:
            instead = "check the path, or create the key file in Google Cloud first."
        elif "--google-share-role" in problem:
            instead = "use --google-share-role reader, commenter or writer."
        elif "email" in problem:
            instead = "give a full address such as name@example.com."
        else:
            instead = "add --create-google-sheets or --create-google-docs."
        errors.append(UsageError(subject or "Google", what, instead, GOOGLE_GUIDE))
    return errors


# ------------------------------------------------------------------ regions


def known_regions() -> List[str]:
    """Region names botocore knows, for every partition."""
    import boto3

    session = boto3.session.Session()
    names = set()
    for partition in session.get_available_partitions():
        names.update(session.get_available_regions("ec2", partition_name=partition))
    return sorted(names)


def region_errors(args) -> List[UsageError]:
    """``--account-regions`` names that are not AWS regions (typo guard)."""
    text = getattr(args, "account_regions", None)
    if not text:
        return []
    known = known_regions()
    errors = []
    for name in (part.strip() for part in text.split(",")):
        if not name or name in known:
            continue
        close = difflib.get_close_matches(name, known, n=1, cutoff=0.7)
        guess = f"did you mean '{close[0]}'? " if close else ""
        errors.append(
            UsageError(
                "--account-regions",
                f"unknown region '{name}'",
                f"{guess}List your regions with: aws ec2 describe-regions "
                "--query 'Regions[].RegionName'. If the region is new, upgrade "
                "with: pip install -U boto3",
                f"{RUN_A_SCAN}#choose-the-regions",
            )
        )
    return errors


# --------------------------------------------------------------------- paths


def path_problem(path: str) -> Optional[str]:
    """Why ``path`` (a folder or a file) cannot be created, or None.

    Nothing is created. Walks up to the nearest folder that exists and checks
    that it is a folder you can write to.
    """
    target = Path(path).expanduser()
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    if not probe.is_dir():
        return f"{probe} is not a folder"
    if probe == target and not target.is_dir():
        return f"{target} is not a folder"
    if not os.access(probe, os.W_OK | os.X_OK):
        return f"{probe}: Permission denied"
    return None


def path_errors(args) -> List[UsageError]:
    """``--output-directory`` and ``--audit-output`` that cannot be written."""
    errors = []
    if getattr(args, "validate_operations", None):
        return errors
    if not _validate_only(args):
        reason = path_problem(args.output_directory)
        if reason:
            errors.append(
                UsageError(
                    "--output-directory",
                    f"cannot create {args.output_directory}: {reason}",
                    "choose a folder you can write to, or create it first.",
                    f"{CLI_REFERENCE}#output",
                )
            )
    if args.audit_output:
        parent = str(Path(args.audit_output).expanduser().parent)
        reason = path_problem(parent)
        if reason:
            errors.append(
                UsageError(
                    "--audit-output",
                    f"cannot write {args.audit_output}: {reason}",
                    "choose a file in a folder you can write to, or create the "
                    "folder first.",
                    f"{CLI_REFERENCE}#read-only-guard-and-audit",
                )
            )
    return errors


def log_file_problem(log_file: Optional[str]) -> Optional[str]:
    """A warning line for an unusable ``--log-file`` (the run goes on), or None."""
    if not log_file:
        return None
    parent = str(Path(log_file).expanduser().parent)
    reason = path_problem(parent)
    if reason is None and Path(log_file).expanduser().is_dir():
        reason = f"{log_file} is a folder"
    if reason is None:
        return None
    return (
        f"--log-file: cannot open {log_file}: {reason}. Logging to the console "
        "only. Instead: choose a writable path, or leave --log-file out. "
        f"More: https://habhabhabs.github.io/inventag-aws/docs/{CLI_REFERENCE}#logging"
    )


# ------------------------------------------------------------------- collect


def collect(args) -> List[UsageError]:
    """Every option problem found before any AWS call, in one list."""
    errors: List[UsageError] = list(safety.unimplemented_flag_errors(args))
    errors.extend(_role_errors(args))
    errors.extend(_conflict_errors(args))
    errors.extend(_template_errors(args))
    errors.extend(_google_errors(args))
    errors.extend(region_errors(args))
    errors.extend(path_errors(args))
    return errors
