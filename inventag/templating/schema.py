"""The InvenTag template format (version 1), described as data.

The same description drives three things, so they cannot drift apart:

* validation (:func:`validate_fields`), with ``file:line`` in every message;
* default values (:func:`apply_defaults`), which the renderers rely on;
* the field reference in the docs (:mod:`inventag.templating.reference`).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .errors import TemplateIssue

FORMAT_VERSION = 1
KINDS = ("report", "tag-policy", "config")
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
COLOR_PATTERN = re.compile(r"^#?[0-9A-Fa-f]{6}$")
ACCOUNT_ID_PATTERN = re.compile(r"^\d{12}$")
ROLE_ARN_PATTERN = re.compile(r"^arn:aws[a-z-]*:iam::\d{12}:role/[\w+=,.@/-]+$")
REGION_PATTERN = re.compile(r"^[a-z]{2}(-[a-z]+)+-\d{1,2}$")
CREDENTIAL_KEYS = ("access_key_id", "secret_access_key", "session_token")
WORD_SECTIONS = (
    "cover",
    "summary",
    "service-summary",
    "tag-compliance",
    "service-tables",
    "about",
)
LOGO_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp")


@dataclass
class Field:
    """Description of one template field."""

    # string, integer, boolean, list, mapping, enum, color, name, ref,
    # relpath, regex or tag_columns
    type: str
    description: str
    default: Any = None
    required: bool = False
    choices: Tuple[str, ...] = ()
    item: Optional["Field"] = None  # for lists
    fields: Optional[Dict[str, "Field"]] = None  # for mappings
    minimum: Optional[int] = None
    maximum: Optional[int] = None
    min_items: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[re.Pattern] = None
    pattern_hint: str = ""
    unique: bool = False
    example: Any = None
    rejected_keys: Dict[str, str] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Field definitions
# --------------------------------------------------------------------------

COLUMN = Field(
    "mapping",
    "One column in a table.",
    fields={
        "field": Field(
            "string",
            "Resource field to show. Use dots for nested values: `tags.Owner` is "
            "the `Owner` tag, `raw_data.InstanceType` is a value from the AWS API "
            "response.",
            required=True,
            max_length=200,
            example="resource_name",
        ),
        "header": Field(
            "string",
            "Column heading. Defaults to the field name in plain words "
            "(`resource_name` becomes `Resource name`).",
            max_length=100,
        ),
        "width": Field(
            "integer",
            "Excel column width in characters. Defaults to a width that fits the "
            "content, capped by `excel.max_column_width`.",
            minimum=4,
            maximum=120,
        ),
    },
)

REPORT_SPEC: Dict[str, Field] = {
    "title": Field(
        "string",
        "Report title, used on the Word cover and the Excel summary sheet.",
        default="AWS Resource Inventory",
        max_length=200,
    ),
    "subtitle": Field(
        "string", "Optional line under the title.", default="", max_length=300
    ),
    "company_name": Field(
        "string",
        "Organisation name shown on the cover and stored in the file properties.",
        default="",
        max_length=200,
    ),
    "colors": Field(
        "mapping",
        "Header colours as six-digit hex values (with or without `#`).",
        fields={
            "header_fill": Field(
                "color", "Background of table header rows.", default="1F3A5F"
            ),
            "header_text": Field(
                "color", "Text colour of table header rows.", default="FFFFFF"
            ),
        },
    ),
    "logo": Field(
        "relpath",
        "Image shown on the Word cover (PNG, JPEG, GIF or BMP). The path is "
        "relative to the template file and must stay inside its folder.",
        default=None,
    ),
    "logo_alt_text": Field(
        "string",
        "Alternative text for the logo, read by screen readers. Defaults to "
        "`<company_name> logo`.",
        default="",
        max_length=200,
    ),
    "columns": Field(
        "list",
        "Columns for resource tables, in order.",
        item=COLUMN,
        min_items=1,
        default=[
            {"field": "source_account_id", "header": "Account"},
            {"field": "region", "header": "Region"},
            {"field": "service", "header": "Service"},
            {"field": "resource_type", "header": "Type"},
            {"field": "resource_name", "header": "Name"},
            {"field": "resource_id", "header": "ID"},
            {"field": "arn", "header": "ARN"},
        ],
    ),
    "tag_columns": Field(
        "tag_columns",
        "Extra columns, one per tag key, added after `columns`. Either a list of "
        "tag keys, or `all` for every tag key found on the resources in that "
        "table, or `none`.",
        default="all",
    ),
    "tag_policy": Field(
        "ref",
        "Tag policy to check, by name or by relative path. A `--template` with "
        "a tag policy on the command line takes precedence.",
        default=None,
    ),
    "excel": Field(
        "mapping",
        "Excel workbook layout.",
        fields={
            "summary_sheet": Field(
                "boolean",
                "Add a Summary sheet with resource counts per service.",
                default=True,
            ),
            "layout": Field(
                "enum",
                "`per-service` puts each service on its own sheet. `single-sheet` "
                "puts every resource on one sheet with a Service column.",
                default="per-service",
                choices=("per-service", "single-sheet"),
            ),
            "single_sheet_name": Field(
                "string",
                "Sheet name when `layout` is `single-sheet`.",
                default="Resources",
                max_length=31,
            ),
            "include_all_fields": Field(
                "boolean",
                "Also add every other field found on the resources, after the "
                "listed columns. Useful for audits; makes wide sheets.",
                default=False,
            ),
            "freeze_header": Field(
                "boolean",
                "Keep the header row visible when scrolling.",
                default=True,
            ),
            "autofilter": Field(
                "boolean", "Add filter buttons to the header row.", default=True
            ),
            "max_column_width": Field(
                "integer",
                "Upper limit for automatic column widths, in characters.",
                default=50,
                minimum=10,
                maximum=120,
            ),
            "tag_compliance_sheet": Field(
                "boolean",
                "Add a Tag Compliance sheet when a tag policy is active.",
                default=True,
            ),
        },
    ),
    "word": Field(
        "mapping",
        "Word document layout.",
        fields={
            "orientation": Field(
                "enum",
                "Page orientation.",
                default="portrait",
                choices=("portrait", "landscape"),
            ),
            "sections": Field(
                "list",
                "Sections to include, in order. Choose from: "
                + ", ".join(f"`{s}`" for s in WORD_SECTIONS)
                + ". `tag-compliance` is skipped when no tag policy is active.",
                item=Field("enum", "Section name.", choices=WORD_SECTIONS),
                default=list(WORD_SECTIONS),
                min_items=1,
                unique=True,
            ),
            "columns": Field(
                "list",
                "Columns for the per-service tables. Defaults to the first "
                "`max_columns` entries of `columns`. Tag columns are not added.",
                item=COLUMN,
                default=None,
            ),
            "max_columns": Field(
                "integer",
                "How many of `columns` to use when `word.columns` is not set. "
                "Word tables get hard to read beyond six or seven columns.",
                default=6,
                minimum=1,
                maximum=12,
            ),
            "max_rows_per_service": Field(
                "integer",
                "Rows shown per service table. A note says how many were left out.",
                default=50,
                minimum=1,
                maximum=10000,
            ),
            "max_noncompliant_rows": Field(
                "integer",
                "Rows shown in the non-compliant resources table.",
                default=100,
                minimum=1,
                maximum=10000,
            ),
        },
    ),
}

REQUIRED_TAG = Field(
    "mapping",
    "A tag every in-scope resource must have.",
    fields={
        "key": Field(
            "string",
            "Tag key. AWS tag keys are case-sensitive, so `costcenter` does not "
            "satisfy `CostCenter`.",
            required=True,
            max_length=128,
        ),
        "description": Field(
            "string", "Why the tag exists. Shown in reports.", default=""
        ),
        "allowed_values": Field(
            "list",
            "If set, the tag value must be one of these.",
            item=Field("string", "Allowed value.", max_length=256),
            default=None,
            min_items=1,
        ),
        "case_sensitive": Field(
            "boolean",
            "Compare `allowed_values` case-sensitively.",
            default=False,
        ),
        "pattern": Field(
            "regex",
            "If set, the whole tag value must match this regular expression "
            "(Python syntax).",
            default=None,
            max_length=200,
        ),
        "remove": Field(
            "boolean",
            "In a template that `extends` another, drop this tag from the "
            "inherited list.",
            default=False,
        ),
    },
)

TAG_POLICY_SPEC: Dict[str, Field] = {
    "required_tags": Field(
        "list",
        "Tags that in-scope resources must have. When a template `extends` "
        "another, entries are merged by `key`: same key replaces, new keys are "
        "added, and `remove: true` drops one.",
        item=REQUIRED_TAG,
        required=True,
        min_items=1,
    ),
    "scope": Field(
        "mapping",
        "Which resources the policy applies to. Resources outside the scope are "
        "counted but not checked.",
        fields={
            "services": Field(
                "list",
                "Only check these services (as shown in the report, for example "
                "`EC2`, `S3`). Empty means all services.",
                item=Field("string", "Service name."),
                default=[],
            ),
            "resource_types": Field(
                "list",
                "Only check these resource types (for example `Bucket`, "
                "`Instance`). Empty means all types.",
                item=Field("string", "Resource type."),
                default=[],
            ),
            "exclude_resource_types": Field(
                "list",
                "Never check these resource types, for example types that cannot "
                "carry tags.",
                item=Field("string", "Resource type."),
                default=[],
            ),
        },
    ),
}

ACCOUNT = Field(
    "mapping",
    "One AWS account to scan.",
    fields={
        "account_id": Field(
            "string",
            "12-digit AWS account ID, in quotes so YAML keeps leading zeros.",
            required=True,
            pattern=ACCOUNT_ID_PATTERN,
            pattern_hint='a 12-digit account ID in quotes, for example "012345678901"',
        ),
        "account_name": Field("string", "Friendly name used in reports.", default=""),
        "profile_name": Field(
            "string", "AWS CLI profile to use for this account.", default=None
        ),
        "role_arn": Field(
            "string",
            "IAM role to assume in this account, as a full ARN.",
            default=None,
            pattern=ROLE_ARN_PATTERN,
            pattern_hint=(
                "a role ARN such as " "arn:aws:iam::012345678901:role/InvenTagReadOnly"
            ),
        ),
        "external_id": Field(
            "string", "External ID required by the role's trust policy.", default=None
        ),
        "regions": Field(
            "list",
            "Regions to scan in this account. Overrides `spec.regions`.",
            item=Field(
                "string",
                "Region code.",
                pattern=REGION_PATTERN,
                pattern_hint="a region code such as us-east-1",
            ),
            default=None,
        ),
        "services": Field(
            "list",
            "Services to scan in this account.",
            item=Field("string", "Service name."),
            default=None,
        ),
    },
    rejected_keys={
        key: "templates must not contain credentials; use profile_name or role_arn"
        for key in CREDENTIAL_KEYS
    },
)

CONFIG_SPEC: Dict[str, Field] = {
    "accounts": Field(
        "list",
        "Accounts to scan. Leave out to scan the account of your current AWS "
        "credentials. Each account needs `profile_name` or `role_arn`.",
        item=ACCOUNT,
        default=None,
        min_items=1,
    ),
    "regions": Field(
        "list",
        "Regions to scan (`--account-regions`). Leave out to scan every enabled "
        "region.",
        item=Field(
            "string",
            "Region code.",
            pattern=REGION_PATTERN,
            pattern_hint="a region code such as us-east-1",
        ),
        default=None,
        min_items=1,
    ),
    "services": Field(
        "list",
        "Services to include (`--account-services`). Currently applied in one "
        "discovery path only, so other services can still appear.",
        item=Field("string", "Service name."),
        default=None,
        min_items=1,
    ),
    "outputs": Field(
        "list",
        "Files to produce (`--create-excel`, `--create-word`).",
        item=Field("enum", "Output format.", choices=("excel", "word")),
        default=["excel"],
        min_items=1,
        unique=True,
    ),
    "output_directory": Field(
        "string",
        "Folder for the reports (`--output-directory`).",
        default="bom_output",
    ),
    "report_template": Field(
        "ref",
        "Report template to use, by name or relative path.",
        default="standard-bom",
    ),
    "tag_policy": Field(
        "ref", "Tag policy to check, by name or relative path.", default=None
    ),
    "fail_on_tag_violations": Field(
        "boolean",
        "Exit with code 3 after writing the reports if any in-scope resource "
        "breaks the tag policy. Needs `tag_policy`.",
        default=False,
    ),
    "max_concurrent_accounts": Field(
        "integer",
        "Accounts scanned at the same time (`--max-concurrent-accounts`).",
        default=4,
        minimum=1,
        maximum=64,
    ),
    "account_processing_timeout": Field(
        "integer",
        "Seconds allowed per account (`--account-processing-timeout`).",
        default=1800,
        minimum=60,
    ),
    "parallel_processing": Field(
        "boolean",
        "Scan accounts in parallel. `false` is the same as "
        "`--disable-parallel-processing`.",
        default=True,
    ),
}

SPECS: Dict[str, Dict[str, Field]] = {
    "report": REPORT_SPEC,
    "tag-policy": TAG_POLICY_SPEC,
    "config": CONFIG_SPEC,
}

TOP_LEVEL: Dict[str, Field] = {
    "format_version": Field(
        "integer",
        f"Template format version. Only `{FORMAT_VERSION}` exists today.",
        default=FORMAT_VERSION,
        minimum=FORMAT_VERSION,
        maximum=FORMAT_VERSION,
    ),
    "kind": Field(
        "enum",
        "What the template controls: `report`, `tag-policy` or `config`.",
        required=True,
        choices=KINDS,
    ),
    "name": Field(
        "name",
        "Lower-case letters, digits and hyphens. Should match the file name "
        "(`my-report.yaml` has `name: my-report`).",
        required=True,
    ),
    "description": Field(
        "string", "One sentence shown by `templates list`.", default=""
    ),
    "extends": Field(
        "ref",
        "Template to inherit from, by name or by relative path. Must be the same "
        "kind.",
        default=None,
    ),
    "spec": Field("mapping", "The settings for this kind (see below).", required=True),
}

TYPE_LABELS = {
    "string": "text",
    "integer": "whole number",
    "boolean": "true or false",
    "list": "list",
    "mapping": "mapping",
    "enum": "one of a fixed set",
    "color": "hex colour",
    "name": "template name",
    "ref": "template name or relative path",
    "relpath": "relative file path",
    "regex": "regular expression",
    "tag_columns": "`all`, `none` or list of tag keys",
}

# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

LineLookup = Callable[[Tuple[Any, ...]], Tuple[Optional[str], Optional[int]]]


def _dotted(path: Tuple[Any, ...]) -> str:
    out = ""
    for part in path:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += ("." if out else "") + str(part)
    return out


def _type_name(value: Any) -> str:
    if value is None:
        return "nothing (null)"
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, int):
        return "a number"
    if isinstance(value, float):
        return "a decimal number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a mapping"
    return type(value).__name__


class _Validator:
    def __init__(self, lookup: LineLookup, partial: bool):
        self.lookup = lookup
        self.partial = partial
        self.issues: List[TemplateIssue] = []

    def add(self, path: Tuple[Any, ...], message: str) -> None:
        source, line = self.lookup(path)
        self.issues.append(TemplateIssue(message, source, line, _dotted(path)))

    def mapping(self, value: Any, fields: Dict[str, Field], path, spec: Field = None):
        if not isinstance(value, dict):
            self.add(
                path, f"must be a mapping (key: value pairs), got {_type_name(value)}"
            )
            return
        rejected = spec.rejected_keys if spec else {}
        for key, item in value.items():
            if not isinstance(key, str):
                self.add(path, f"keys must be text, got {_type_name(key)} {key!r}")
                continue
            if key in rejected:
                self.add(path + (key,), rejected[key])
                continue
            if key not in fields:
                hint = difflib.get_close_matches(key, list(fields), n=1)
                suggestion = f"; did you mean '{hint[0]}'?" if hint else ""
                allowed = ", ".join(sorted(fields))
                self.add(
                    path + (key,),
                    f"unknown field '{key}'{suggestion} Allowed here: {allowed}",
                )
                continue
            if item is None and not fields[key].required:
                # null resets an inherited value to the default
                continue
            self.value(item, fields[key], path + (key,))
        if not self.partial:
            for key, spec_field in fields.items():
                if spec_field.required and value.get(key) is None:
                    self.add(path + (key,), "is required")

    def value(self, value: Any, spec: Field, path) -> None:
        kind = spec.type
        if kind == "mapping":
            if spec.fields is None:  # free-form here; checked elsewhere
                if not isinstance(value, dict):
                    self.add(
                        path,
                        "must be a mapping (key: value pairs), got "
                        f"{_type_name(value)}",
                    )
                return
            self.mapping(value, spec.fields, path, spec)
            return
        if kind == "list":
            self.list(value, spec, path)
            return
        if kind == "boolean":
            if not isinstance(value, bool):
                self.add(path, f"must be true or false, got {_type_name(value)}")
            return
        if kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                self.add(path, f"must be a whole number, got {_type_name(value)}")
                return
            if spec.minimum is not None and value < spec.minimum:
                self.add(path, f"must be at least {spec.minimum}, got {value}")
            if spec.maximum is not None and value > spec.maximum:
                self.add(path, f"must be at most {spec.maximum}, got {value}")
            return
        if kind == "tag_columns":
            if isinstance(value, str):
                if value not in ("all", "none"):
                    self.add(
                        path,
                        f"must be 'all', 'none' or a list of tag keys, got '{value}'",
                    )
                return
            if not isinstance(value, list) or not all(
                isinstance(v, str) and v for v in value
            ):
                self.add(path, "must be 'all', 'none' or a list of tag keys")
            return
        # Everything else is text.
        if not isinstance(value, str):
            hint = ""
            if (
                kind == "string"
                and isinstance(value, int)
                and spec.pattern is ACCOUNT_ID_PATTERN
            ):
                hint = ' Put account IDs in quotes, for example "012345678901".'
            self.add(
                path, f"must be text, got {_type_name(value)}.{hint}".replace("..", ".")
            )
            return
        if spec.max_length and len(value) > spec.max_length:
            self.add(path, f"must be at most {spec.max_length} characters long")
        if kind == "enum" and value not in spec.choices:
            hint = difflib.get_close_matches(value, list(spec.choices), n=1)
            suggestion = f"; did you mean '{hint[0]}'?" if hint else ""
            self.add(
                path,
                f"must be one of {', '.join(spec.choices)} (got '{value}'){suggestion}",
            )
        elif kind == "color" and not COLOR_PATTERN.match(value):
            self.add(
                path, f"must be a six-digit hex colour such as 1F3A5F (got '{value}')"
            )
        elif kind == "name" and not NAME_PATTERN.match(value):
            self.add(
                path,
                "must use only lower-case letters, digits and hyphens, start with a "
                f"letter or digit, and be at most 63 characters (got '{value}')",
            )
        elif kind == "regex":
            try:
                re.compile(value)
            except re.error as error:
                self.add(path, f"is not a valid regular expression: {error}")
        elif kind in ("ref", "relpath") and not value.strip():
            self.add(path, "must not be empty")
        if spec.pattern is not None and not spec.pattern.match(value):
            self.add(path, f"must be {spec.pattern_hint} (got '{value}')")

    def list(self, value: Any, spec: Field, path) -> None:
        if not isinstance(value, list):
            self.add(path, f"must be a list, got {_type_name(value)}")
            return
        if spec.min_items and len(value) < spec.min_items and not self.partial:
            self.add(path, f"must have at least {spec.min_items} item(s)")
        if spec.unique:
            seen = set()
            for index, item in enumerate(value):
                marker = repr(item)
                if marker in seen:
                    self.add(path + (index,), f"duplicate entry {item!r}")
                seen.add(marker)
        if spec.item is not None:
            for index, item in enumerate(value):
                self.value(item, spec.item, path + (index,))


def validate_fields(
    data: Dict[str, Any], lookup: LineLookup, partial: bool = False
) -> List[TemplateIssue]:
    """Validate a template's data against the schema.

    ``partial`` is used for a template that ``extends`` another: unknown fields
    and wrong types are still errors, but required fields may come from the
    parent.
    """
    validator = _Validator(lookup, partial)
    validator.mapping(data, TOP_LEVEL, ())
    kind = data.get("kind")
    spec = data.get("spec")
    if kind in SPECS and isinstance(spec, dict):
        validator.mapping(spec, SPECS[kind], ("spec",))
        if not partial:
            _semantic_checks(kind, spec, validator)
    return validator.issues


def _semantic_checks(kind: str, spec: Dict[str, Any], v: _Validator) -> None:
    if kind == "tag-policy":
        tags = spec.get("required_tags") or []
        seen: Dict[str, int] = {}
        for index, tag in enumerate(tags):
            if not isinstance(tag, dict):
                continue
            key = tag.get("key")
            if key in seen:
                v.add(
                    ("spec", "required_tags", index, "key"),
                    f"tag '{key}' is listed twice",
                )
            seen[key] = index
            values = tag.get("allowed_values")
            if isinstance(values, list) and tag.get("pattern"):
                v.add(
                    ("spec", "required_tags", index),
                    "use either allowed_values or pattern, not both",
                )
    if kind == "config":
        if spec.get("fail_on_tag_violations") and not spec.get("tag_policy"):
            v.add(("spec", "fail_on_tag_violations"), "needs spec.tag_policy to be set")
        for index, account in enumerate(spec.get("accounts") or []):
            if not isinstance(account, dict):
                continue
            if not (account.get("profile_name") or account.get("role_arn")):
                v.add(
                    ("spec", "accounts", index),
                    "each account needs profile_name or role_arn",
                )
            arn = account.get("role_arn")
            acct = account.get("account_id")
            if (
                isinstance(arn, str)
                and isinstance(acct, str)
                and ROLE_ARN_PATTERN.match(arn)
            ):
                arn_account = arn.split(":")[4]
                if arn_account != acct:
                    v.add(
                        ("spec", "accounts", index, "role_arn"),
                        f"role is in account {arn_account} but account_id is {acct}",
                    )


# --------------------------------------------------------------------------
# Defaults
# --------------------------------------------------------------------------


def _default_for(spec: Field) -> Any:
    if spec.type == "mapping" and spec.fields is not None:
        return apply_defaults({}, spec.fields)
    if isinstance(spec.default, (list, dict)):
        import copy

        return copy.deepcopy(spec.default)
    return spec.default


def apply_defaults(
    data: Optional[Dict[str, Any]], fields: Dict[str, Field]
) -> Dict[str, Any]:
    """Return a copy of ``data`` with every missing or null field defaulted."""
    result: Dict[str, Any] = dict(data or {})
    for key, spec in fields.items():
        value = result.get(key)
        if value is None:
            result[key] = _default_for(spec)
        elif spec.type == "mapping" and spec.fields and isinstance(value, dict):
            result[key] = apply_defaults(value, spec.fields)
        elif (
            spec.type == "list"
            and spec.item is not None
            and spec.item.fields
            and isinstance(value, list)
        ):
            result[key] = [
                (
                    apply_defaults(item, spec.item.fields)
                    if isinstance(item, dict)
                    else item
                )
                for item in value
            ]
    return result
