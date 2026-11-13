"""
Report templates for the Word and Excel BOM reports.

A report template is a YAML or JSON file that a user gives to the CLI with
``--word-template`` or ``--excel-template``. The template controls the title,
the branding fields, the sections or sheets and their order, the columns, the
header and footer text, and ``{{ variable }}`` substitution.

Design rules:

* The schema is data (:data:`TOP_LEVEL_KEYS`, :data:`SECTION_KEYS` ...). The
  validator and the key reference in the user guide both read it.
* Validation is strict: unknown keys, wrong types, unknown sections, unknown
  columns and unknown variables are errors. :func:`load_report_template`
  raises :class:`TemplateValidationError` with every problem it found, each
  with the key path, before the caller makes any AWS call.
* Substitution is a fixed-whitelist ``{{ name }}`` replacement. There is no
  expression language, no attribute access, no filters and no file inclusion.
  A substituted value is never scanned again.
* Files are read with a size limit and parsed with ``yaml.safe_load`` or
  ``json.loads`` only. ``branding.logo_path`` must stay inside the directory
  of the template file.
* The built-in defaults (:data:`DEFAULT_WORD_TEMPLATE`,
  :data:`DEFAULT_EXCEL_TEMPLATE`) reproduce the report structure that
  InvenTag wrote before templates existed. ``templates/default_*`` in the
  repository are copies of them for users to start from.
"""

import copy
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from ..security.safe_output import safe_join

TEMPLATE_VERSION = "2.0"
FORMATS = ("word", "excel")
TEMPLATE_SUFFIXES = (".yaml", ".yml", ".json")
LOGO_SUFFIXES = (".png", ".jpg", ".jpeg")

# Limits. A template is a small configuration file, not a document.
MAX_TEMPLATE_BYTES = 256 * 1024
MAX_LOGO_BYTES = 5 * 1024 * 1024
MAX_TEXT_LENGTH = 2000
MAX_SECTIONS = 50
MAX_COLUMNS = 100
MAX_PARAGRAPHS = 100
MAX_VARIABLES = 50
MAX_EXTRA_FIELDS = 200
MAX_SERVICES = 500
MAX_ROWS_LIMIT = 100000
EXCEL_SHEET_NAME_MAX = 31

_FORMAT_LABELS = {"word": "Word", "excel": "Excel"}
_A_FORMAT = {"word": "a Word", "excel": "an Excel"}

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_FIELD_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.:\-/ ]{0,199}$")
_COLOR_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")
_SHEET_NAME_FORBIDDEN = re.compile(r"[\[\]:*?/\\]")
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


# --------------------------------------------------------------- variables
# name -> description. These are the only names that {{ name }} accepts,
# together with the names a template defines under ``variables``.
GLOBAL_VARIABLES: Dict[str, str] = {
    "company_name": "The value of branding.company_name.",
    "document_title": "The value of document.title after substitution.",
    "document_subtitle": "The value of document.subtitle after substitution.",
    "generated_at": "Generation time in UTC, format YYYY-MM-DD HH:MM:SS.",
    "generated_date": "Generation date in UTC, format YYYY-MM-DD.",
    "account_ids": "The account IDs in the report, sorted, separated by a comma and a space.",
    "account_count": "The number of different account IDs in the report.",
    "total_resources": "The number of resources in the report.",
    "service_count": "The number of different services in the report.",
    "region_count": "The number of different regions in the report.",
}

# Only valid in the per-service texts of a Word ``resources`` section
# (``service_title`` and ``truncation_note``).
SERVICE_VARIABLES: Dict[str, str] = {
    "service": "The service name of the current table.",
    "service_resource_count": "The number of resources of the current service.",
    "shown_resource_count": "The number of rows in the current table.",
}

# document.title and document.subtitle cannot refer to themselves.
_TITLE_FORBIDDEN = ("document_title", "document_subtitle")


# ------------------------------------------------------------------ fields
SUMMARY_FIELDS: Tuple[str, ...] = ("service", "resource_count", "percentage")

# Resource fields that a ``resources`` section can show. Discovery adds more
# keys for some services; ``tags.<key>`` and ``raw_data.<key>`` are always
# valid, and a template can declare other names under ``extra_fields``.
CORE_FIELDS: Tuple[str, ...] = ("service", "type", "id", "name", "arn")
ACCOUNT_FIELDS: Tuple[str, ...] = (
    "account_id",
    "source_account_id",
    "source_account_name",
    "account_name",
    "region",
    "availability_zone",
)
DETAIL_FIELDS: Tuple[str, ...] = (
    "status",
    "state",
    "creation_date",
    "created_time",
    "launch_time",
    "size",
    "instance_type",
    "storage_type",
    "engine",
    "engine_version",
    "allocated_storage",
    "storage_encrypted",
    "multi_az",
    "publicly_accessible",
    "vpc_id",
    "vpc_name",
    "subnet_id",
    "subnet_name",
    "security_groups",
    "security_group_ids",
)
NETWORK_FIELDS: Tuple[str, ...] = (
    "vpc_cidr_block",
    "vpc_total_ips",
    "vpc_utilization_percentage",
    "subnet_cidr_block",
    "subnet_total_ips",
    "subnet_utilization_percentage",
    "subnet_is_public",
    "subnet_availability_zone",
)
SECURITY_FIELDS: Tuple[str, ...] = (
    "security_risk_level",
    "security_group_count",
    "max_security_risk",
    "inbound_rules_count",
    "outbound_rules_count",
    "associated_resources_count",
    "has_permissive_rules",
    "permissive_rules",
)
COST_FIELDS: Tuple[str, ...] = (
    "estimated_monthly_cost",
    "cost_breakdown",
    "pricing_model",
    "confidence_level",
    "cost_optimization_opportunities",
    "monthly_spend",
    "service_monthly_spend",
    "billing_validated",
)
TRACKING_FIELDS: Tuple[str, ...] = (
    "compliance_status",
    "compliance_score",
    "discovery_timestamp",
    "consolidation_timestamp",
    "total_accounts_in_consolidation",
    "discovered_at",
    "discovered_via",
    "priority",
    "tagged",
    "tags",
    "service_description",
    "resource_id",
    "resource_name",
    "resource_type",
)
KNOWN_RESOURCE_FIELDS: Tuple[str, ...] = (
    CORE_FIELDS
    + ACCOUNT_FIELDS
    + DETAIL_FIELDS
    + NETWORK_FIELDS
    + SECURITY_FIELDS
    + COST_FIELDS
    + TRACKING_FIELDS
)
DYNAMIC_FIELD_PREFIXES: Tuple[str, ...] = ("tags.", "raw_data.")

# Table styles of the python-docx default document.
WORD_TABLE_STYLES_FALLBACK: Tuple[str, ...] = (
    "Table Grid",
    "Light Shading",
    "Light Shading Accent 1",
    "Light List",
    "Light List Accent 1",
    "Light Grid",
    "Light Grid Accent 1",
    "Medium Shading 1",
    "Medium Shading 1 Accent 1",
    "Medium Grid 1",
    "Medium Grid 1 Accent 1",
)


def word_table_styles() -> Tuple[str, ...]:
    """Names of the table styles that the Word builder can apply."""
    try:
        from docx import Document
        from docx.enum.style import WD_STYLE_TYPE

        return tuple(
            sorted(s.name for s in Document().styles if s.type == WD_STYLE_TYPE.TABLE)
        )
    except Exception:  # pragma: no cover - python-docx not installed
        return WORD_TABLE_STYLES_FALLBACK


# ------------------------------------------------------------------ schema
@dataclass(frozen=True)
class Key:
    """One key of the template schema."""

    name: str
    type: str  # string, boolean, integer, number, mapping, list, columns
    description: str
    formats: Tuple[str, ...] = FORMATS
    required: bool = False
    default: Any = None
    content_types: Tuple[str, ...] = ()  # sections only; empty means all


CONTENT_TYPES: Dict[str, Tuple[str, ...]] = {
    "word": ("title", "text", "service_summary", "resources"),
    "excel": (
        "service_summary",
        "resources",
        "network_analysis",
        "security_analysis",
        "cost_analysis",
    ),
}

CONTENT_TYPE_DESCRIPTIONS: Dict[str, str] = {
    "title": "The document title, the subtitle and the logo.",
    "text": "An optional heading and a list of paragraphs.",
    "service_summary": "One row for each service: name, resource count, percentage. "
    "A table in Word, a sheet in Excel.",
    "resources": "The resource tables. Word: one table for each service. "
    "Excel: one sheet for each service, or one sheet for all resources.",
    "network_analysis": "The network analysis sheet. InvenTag writes it only if "
    "network analysis data exists.",
    "security_analysis": "The security analysis sheet. InvenTag writes it only if "
    "security analysis data exists.",
    "cost_analysis": "The cost analysis sheet. InvenTag writes it only if "
    "cost analysis data exists (--enable-cost-analysis).",
}

TOP_LEVEL_KEYS: Tuple[Key, ...] = (
    Key(
        "template_version",
        "string",
        'Schema version. Must be "2.0".',
        required=True,
    ),
    Key("format_type", "string", "`word` or `excel`.", required=True),
    Key("name", "string", "A name for the template. Not shown in the report."),
    Key("description", "string", "A description. Not shown in the report."),
    Key("document", "mapping", "Title and subtitle. See `document`."),
    Key("branding", "mapping", "Company name, logo and color. See `branding`."),
    Key(
        "variables",
        "mapping",
        "Your own variables: name to text. Use them as `{{ name }}`.",
    ),
    Key(
        "extra_fields",
        "list",
        "More resource field names that `columns` can use, for example a "
        "column from your tag mappings.",
    ),
    Key("header_footer", "mapping", "Header and footer text. See `header_footer`."),
    Key(
        "sections",
        "list",
        "The sections (Word) or sheets (Excel), in report order.",
        required=True,
    ),
)

DOCUMENT_KEYS: Tuple[Key, ...] = (
    Key(
        "title",
        "string",
        "Word: the text of the `title` section. Excel: the workbook title property.",
        default="",
    ),
    Key(
        "subtitle",
        "string",
        "Word: a line below the title. Excel: the workbook subject property.",
        default="",
    ),
)

BRANDING_KEYS: Tuple[Key, ...] = (
    Key(
        "company_name",
        "string",
        "The value of `{{ company_name }}`. Excel: also the workbook creator property.",
        default="",
    ),
    Key(
        "logo_path",
        "string",
        "PNG or JPEG file shown above the title. The path is relative to the "
        "template file and must stay in its directory.",
        formats=("word",),
    ),
    Key(
        "logo_width_inches",
        "number",
        "Logo width, 0.25 to 7.",
        formats=("word",),
        default=1.5,
    ),
    Key(
        "header_color",
        "string",
        "Fill color of the header row, six hexadecimal digits.",
        formats=("excel",),
        default="366092",
    ),
)

HEADER_FOOTER_KEYS: Tuple[Key, ...] = (
    Key(
        "header_text",
        "string",
        "Word: page header. Excel: print header of each sheet.",
        default="",
    ),
    Key(
        "footer_text",
        "string",
        "Word: page footer. Excel: print footer of each sheet.",
        default="",
    ),
    Key(
        "include_page_numbers",
        "boolean",
        "Add `Page <number>` to the page footer.",
        formats=("word",),
        default=False,
    ),
)

SECTION_KEYS: Tuple[Key, ...] = (
    Key(
        "id",
        "string",
        "Unique name of the section: lowercase letters, digits and underscores.",
        required=True,
    ),
    Key("content_type", "string", "What the section shows.", required=True),
    Key(
        "enabled",
        "boolean",
        "Set to `false` to leave the section out.",
        default=True,
    ),
    Key(
        "title",
        "string",
        "Heading text of the section.",
        formats=("word",),
        content_types=("text", "service_summary", "resources"),
        default="",
    ),
    Key(
        "level",
        "integer",
        "Heading level, 1 to 3. Service headings use the next level.",
        formats=("word",),
        content_types=("text", "service_summary", "resources"),
        default=1,
    ),
    Key(
        "page_break_before",
        "boolean",
        "Start the section on a new page.",
        formats=("word",),
        default=False,
    ),
    Key(
        "paragraphs",
        "list",
        "The paragraphs of a `text` section.",
        formats=("word",),
        content_types=("text",),
        default=[],
    ),
    Key(
        "columns",
        "columns",
        "`auto`, or a list of columns. See `columns`.",
        content_types=("service_summary", "resources"),
        default="auto",
    ),
    Key(
        "table_style",
        "string",
        "Word table style, for example `Light List Accent 1`.",
        formats=("word",),
        content_types=("service_summary", "resources"),
    ),
    Key(
        "services",
        "list",
        "Show only these services, in this order. The comparison ignores "
        "case, spaces, and the prefixes `Amazon` and `AWS`.",
        content_types=("resources",),
    ),
    Key(
        "service_title",
        "string",
        "Heading of each service table.",
        formats=("word",),
        content_types=("resources",),
        default="{{ service }} Resources ({{ service_resource_count }})",
    ),
    Key(
        "max_rows",
        "integer",
        "Maximum number of rows in each service table, 1 to 100000.",
        formats=("word",),
        content_types=("resources",),
        default=50,
    ),
    Key(
        "max_columns",
        "integer",
        "Maximum number of columns if `columns` is `auto`, 1 to 100.",
        formats=("word",),
        content_types=("resources",),
        default=6,
    ),
    Key(
        "truncation_note",
        "string",
        "Paragraph below a table that does not show all resources.",
        formats=("word",),
        content_types=("resources",),
        default="Note: Showing first {{ shown_resource_count }} of "
        "{{ service_resource_count }} {{ service }} resources.",
    ),
    Key(
        "page_break_after_service",
        "boolean",
        "Start a new page after each service table.",
        formats=("word",),
        content_types=("resources",),
        default=True,
    ),
    Key(
        "sheet_name",
        "string",
        "Sheet name, 1 to 31 characters. Necessary for a `resources` "
        "section with `group_by_service: false`.",
        formats=("excel",),
        content_types=("service_summary", "resources"),
    ),
    Key(
        "group_by_service",
        "boolean",
        "`true`: one sheet for each service. `false`: one sheet for all resources.",
        formats=("excel",),
        content_types=("resources",),
        default=True,
    ),
    Key(
        "show_title",
        "boolean",
        "Write the document title and subtitle above the table.",
        formats=("excel",),
        content_types=("service_summary",),
        default=False,
    ),
)

COLUMN_KEYS: Tuple[Key, ...] = (
    Key("field", "string", "The field to show.", required=True),
    Key("heading", "string", "The column heading. Default: the field name."),
    Key(
        "width",
        "number",
        "Column width. Word: inches, 0.2 to 10. Excel: characters, 1 to 255.",
    ),
)

_DEFAULT_TABLE_STYLE = {
    "service_summary": "Light Grid Accent 1",
    "resources": "Light List Accent 1",
}


# ---------------------------------------------------------------- defaults
DEFAULT_WORD_TEMPLATE: Dict[str, Any] = {
    "template_version": TEMPLATE_VERSION,
    "format_type": "word",
    "name": "Default Word BOM template",
    "description": "The report structure that InvenTag writes if you give no --word-template.",
    "document": {"title": "AWS Resource Inventory - BOM Report", "subtitle": ""},
    "branding": {"company_name": ""},
    "header_footer": {
        "header_text": "",
        "footer_text": "",
        "include_page_numbers": False,
    },
    "sections": [
        {"id": "title", "content_type": "title"},
        {
            "id": "generated_on",
            "content_type": "text",
            "paragraphs": ["Generated on: {{ generated_at }} UTC"],
        },
        {
            "id": "executive_summary",
            "content_type": "text",
            "title": "Executive Summary",
            "level": 1,
            "paragraphs": [
                "Total Resources: {{ total_resources }}",
                "Services Covered: {{ service_count }}",
                "AWS Regions: {{ region_count }}",
            ],
        },
        {
            "id": "service_summary",
            "content_type": "service_summary",
            "title": "Service Summary",
            "level": 2,
            "table_style": "Light Grid Accent 1",
            "columns": [
                {"field": "service", "heading": "Service"},
                {"field": "resource_count", "heading": "Resource Count"},
                {"field": "percentage", "heading": "Percentage"},
            ],
        },
        {
            "id": "resource_inventory",
            "content_type": "resources",
            "title": "Detailed Resource Inventory",
            "level": 1,
            "service_title": "{{ service }} Resources ({{ service_resource_count }})",
            "table_style": "Light List Accent 1",
            "columns": "auto",
            "max_columns": 6,
            "max_rows": 50,
            "truncation_note": "Note: Showing first {{ shown_resource_count }} of "
            "{{ service_resource_count }} {{ service }} resources.",
            "page_break_after_service": True,
        },
        {
            "id": "report_information",
            "content_type": "text",
            "title": "Report Information",
            "level": 1,
            "paragraphs": [
                "This report was generated using InvenTag - AWS Resource Inventory Tool",
                "For more information, visit: https://github.com/habhabhabs/inventag-aws",
            ],
        },
    ],
}

DEFAULT_EXCEL_TEMPLATE: Dict[str, Any] = {
    "template_version": TEMPLATE_VERSION,
    "format_type": "excel",
    "name": "Default Excel BOM template",
    "description": "The workbook structure that InvenTag writes if you give no --excel-template.",
    "document": {"title": "", "subtitle": ""},
    "branding": {"company_name": "", "header_color": "366092"},
    "header_footer": {"header_text": "", "footer_text": ""},
    "sections": [
        {
            "id": "summary",
            "content_type": "service_summary",
            "sheet_name": "Summary",
            "show_title": False,
            "columns": [
                {"field": "service", "heading": "Service"},
                {"field": "resource_count", "heading": "Resource Count"},
                {"field": "percentage", "heading": "Percentage"},
            ],
        },
        {
            "id": "service_sheets",
            "content_type": "resources",
            "group_by_service": True,
            "columns": "auto",
        },
        {"id": "network_analysis", "content_type": "network_analysis"},
        {"id": "security_analysis", "content_type": "security_analysis"},
        {"id": "cost_analysis", "content_type": "cost_analysis"},
    ],
}

_DEFAULTS = {"word": DEFAULT_WORD_TEMPLATE, "excel": DEFAULT_EXCEL_TEMPLATE}
_SHIPPED_FILES = {
    "word": "default_word_template.yaml",
    "excel": "default_excel_template.json",
}


# ------------------------------------------------------------------ errors
@dataclass(frozen=True)
class TemplateIssue:
    """One validation problem: where it is and what is wrong."""

    key_path: str
    reason: str

    def __str__(self) -> str:
        return f"{self.key_path}: {self.reason}" if self.key_path else self.reason


class TemplateValidationError(ValueError):
    """A template file is not valid. ``issues`` lists every problem found."""

    def __init__(self, source: str, issues: Sequence[TemplateIssue]):
        self.source = source
        self.issues = list(issues)
        super().__init__("\n".join(self.messages()))

    def messages(self) -> List[str]:
        """One line for each problem: ``<file>: <key path>: <reason>``."""
        return [f"{self.source}: {issue}" for issue in self.issues]


@dataclass
class ReportTemplate:
    """A validated template. ``data`` has every default filled in."""

    format_type: str
    data: Dict[str, Any]
    source: str = "<built-in default>"
    base_dir: Optional[Path] = None
    logo_file: Optional[Path] = None

    @property
    def sections(self) -> List[Dict[str, Any]]:
        """The enabled sections, in report order."""
        return [s for s in self.data["sections"] if s["enabled"]]

    @property
    def variables(self) -> Dict[str, str]:
        return dict(self.data["variables"])

    @property
    def resource_fields(self) -> frozenset:
        return frozenset(KNOWN_RESOURCE_FIELDS) | frozenset(self.data["extra_fields"])


# ------------------------------------------------------------ substitution
def placeholder_names(text: str) -> List[str]:
    """The variable names that ``text`` refers to, in order."""
    return _PLACEHOLDER_RE.findall(text)


def placeholder_errors(text: str, allowed: Iterable[str]) -> List[str]:
    """Reasons why ``text`` is not a valid template text (empty if valid)."""
    allowed = set(allowed)
    errors = []
    for name in dict.fromkeys(placeholder_names(text)):
        if name not in allowed:
            errors.append(
                f"unknown variable '{name}'. Allowed variables: "
                + ", ".join(sorted(allowed))
            )
    remainder = _PLACEHOLDER_RE.sub("", text)
    if "{{" in remainder or "}}" in remainder:
        errors.append(
            "malformed placeholder. Write {{ name }} with one variable name of "
            "letters, digits and underscores. Expressions, filters and nested "
            "braces are not supported"
        )
    return errors


def substitute(text: str, values: Dict[str, Any]) -> str:
    """Replace each ``{{ name }}`` in ``text`` with ``values[name]``.

    Only whole-name placeholders are replaced. The replacement is one pass:
    a value that contains ``{{ ... }}`` is inserted as literal text. A name
    that is not in ``values`` raises ``KeyError`` (a validated template never
    contains one).
    """
    if not text:
        return text

    def replace(match: "re.Match[str]") -> str:
        name = match.group(1)
        if name not in values:
            raise KeyError(f"unknown template variable '{name}'")
        return str(values[name])

    return _PLACEHOLDER_RE.sub(replace, text)


# -------------------------------------------------------------- validation
_TYPE_LABELS = {
    "string": "a string",
    "boolean": "true or false",
    "integer": "an integer",
    "number": "a number",
    "mapping": "a mapping",
    "list": "a list",
}


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "mapping"
    if isinstance(value, list):
        return "list"
    return type(value).__name__


def _is_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "mapping":
        return isinstance(value, dict)
    if expected == "list":
        return isinstance(value, list)
    return True


class _Validator:
    """Validate raw template data and build the normalized form."""

    def __init__(self, expected_format: Optional[str], base_dir: Optional[Path]):
        self.expected_format = expected_format
        self.base_dir = base_dir
        self.issues: List[TemplateIssue] = []
        self.logo_file: Optional[Path] = None

    def error(self, key_path: str, reason: str) -> None:
        self.issues.append(TemplateIssue(key_path, reason))

    # -- generic helpers
    def check_keys(
        self, data: Dict[str, Any], keys: Sequence[Key], path: str, fmt: str
    ) -> None:
        allowed = [k.name for k in keys if fmt in k.formats]
        for name in data:
            child = f"{path}.{name}" if path else str(name)
            if not isinstance(name, str):
                self.error(child, "a key must be a string")
            elif name not in {k.name for k in keys}:
                self.error(child, "unknown key. Allowed keys: " + ", ".join(allowed))
            elif name not in allowed:
                self.error(
                    child,
                    f"this key is not valid in {_A_FORMAT[fmt]} template. "
                    "Allowed keys: " + ", ".join(allowed),
                )

    def typed(self, data: Dict[str, Any], key: Key, path: str) -> Tuple[bool, Any]:
        """Return (present_and_valid, value) for ``key`` in ``data``."""
        child = f"{path}.{key.name}" if path else key.name
        if key.name not in data or data[key.name] is None:
            return False, None
        value = data[key.name]
        if not _is_type(value, key.type):
            self.error(
                child,
                f"must be {_TYPE_LABELS.get(key.type, key.type)}, "
                f"but the value is {_type_name(value)}",
            )
            return False, None
        return True, value

    def text(
        self,
        value: str,
        path: str,
        allowed_vars: Iterable[str],
        max_length: int = MAX_TEXT_LENGTH,
    ) -> str:
        if len(value) > max_length:
            self.error(
                path, f"text is {len(value)} characters. The maximum is {max_length}"
            )
            return ""
        if "\x00" in value:
            self.error(path, "text must not contain a NUL character")
            return ""
        for reason in placeholder_errors(value, allowed_vars):
            self.error(path, reason)
        return value

    # -- top level
    def validate(self, raw: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(raw, dict):
            self.error(
                "", f"the template must be a mapping, but it is {_type_name(raw)}"
            )
            return None

        fmt = raw.get("format_type")
        if "format_type" not in raw:
            self.error("format_type", "missing key. Use 'word' or 'excel'")
        elif fmt not in FORMATS:
            self.error("format_type", f"must be 'word' or 'excel', but it is {fmt!r}")
        elif self.expected_format and fmt != self.expected_format:
            self.error(
                "format_type",
                f"the file is a template for {_FORMAT_LABELS[fmt]} reports, but "
                f"this flag needs a template for {_FORMAT_LABELS[self.expected_format]} "
                "reports",
            )
        version = raw.get("template_version")
        if "template_version" not in raw:
            self.error("template_version", f'missing key. Use "{TEMPLATE_VERSION}"')
        elif str(version) != TEMPLATE_VERSION:
            self.error(
                "template_version",
                f"unsupported version {str(version)!r}. This version of InvenTag "
                f'reads version "{TEMPLATE_VERSION}". Start from the output of '
                "--print-default-template",
            )
        if fmt not in FORMATS:
            fmt = self.expected_format
        if fmt not in FORMATS:
            return None

        self.check_keys(raw, TOP_LEVEL_KEYS, "", fmt)
        out: Dict[str, Any] = {"template_version": TEMPLATE_VERSION, "format_type": fmt}
        for name in ("name", "description"):
            ok, value = self.typed(raw, Key(name, "string", ""), "")
            out[name] = self.text(value, name, ()) if ok else ""

        out["variables"] = self.user_variables(raw)
        out["extra_fields"] = self.extra_fields(raw)
        global_vars = set(GLOBAL_VARIABLES) | set(out["variables"])

        out["branding"] = self.branding(raw, fmt)
        out["document"] = self.document(raw, fmt, global_vars)
        out["header_footer"] = self.header_footer(raw, fmt, global_vars)
        out["sections"] = self.sections(raw, fmt, global_vars, out["extra_fields"])
        return out

    def user_variables(self, raw: Dict[str, Any]) -> Dict[str, str]:
        ok, variables = self.typed(raw, Key("variables", "mapping", ""), "")
        result: Dict[str, str] = {}
        if not ok:
            return result
        if len(variables) > MAX_VARIABLES:
            self.error(
                "variables", f"too many variables. The maximum is {MAX_VARIABLES}"
            )
            return result
        reserved = set(GLOBAL_VARIABLES) | set(SERVICE_VARIABLES)
        for name, value in variables.items():
            path = f"variables.{name}"
            if not isinstance(name, str) or not _NAME_RE.match(name):
                self.error(
                    path,
                    "a variable name must start with a lowercase letter and "
                    "contain only lowercase letters, digits and underscores",
                )
                continue
            if name in reserved:
                self.error(
                    path, "this name is a built-in variable. Use a different name"
                )
                continue
            if isinstance(value, bool) or not isinstance(value, (str, int, float)):
                self.error(
                    path,
                    f"must be a string or a number, but the value is {_type_name(value)}",
                )
                continue
            value = str(value)
            if len(value) > MAX_TEXT_LENGTH:
                self.error(
                    path,
                    f"text is {len(value)} characters. The maximum is {MAX_TEXT_LENGTH}",
                )
                continue
            if "{{" in value or "}}" in value:
                self.error(
                    path,
                    "a variable value must not contain {{ or }}. A variable "
                    "cannot refer to a different variable",
                )
                continue
            result[name] = value
        return result

    def extra_fields(self, raw: Dict[str, Any]) -> List[str]:
        ok, fields = self.typed(raw, Key("extra_fields", "list", ""), "")
        result: List[str] = []
        if not ok:
            return result
        if len(fields) > MAX_EXTRA_FIELDS:
            self.error(
                "extra_fields", f"too many entries. The maximum is {MAX_EXTRA_FIELDS}"
            )
            return result
        for index, name in enumerate(fields):
            path = f"extra_fields[{index}]"
            if not isinstance(name, str) or not _FIELD_RE.match(name):
                self.error(path, "must be a field name of 1 to 200 characters")
            else:
                result.append(name)
        return result

    def mapping(self, raw: Dict[str, Any], name: str) -> Dict[str, Any]:
        ok, value = self.typed(raw, Key(name, "mapping", ""), "")
        return value if ok else {}

    def branding(self, raw: Dict[str, Any], fmt: str) -> Dict[str, Any]:
        data = self.mapping(raw, "branding")
        self.check_keys(data, BRANDING_KEYS, "branding", fmt)
        out: Dict[str, Any] = {
            "company_name": "",
            "logo_path": None,
            "logo_width_inches": 1.5,
            "header_color": "366092",
        }
        keys = {k.name: k for k in BRANDING_KEYS}
        ok, value = self.typed(data, keys["company_name"], "branding")
        if ok:
            if "{{" in value or "}}" in value:
                self.error(
                    "branding.company_name",
                    "must not contain {{ or }}. Write the company name as plain text",
                )
            else:
                out["company_name"] = self.text(value, "branding.company_name", ())
        if fmt == "word":
            ok, value = self.typed(data, keys["logo_path"], "branding")
            if ok:
                out["logo_path"] = value
                self.logo_file = self.logo(value)
            ok, value = self.typed(data, keys["logo_width_inches"], "branding")
            if ok:
                if 0.25 <= value <= 7:
                    out["logo_width_inches"] = float(value)
                else:
                    self.error("branding.logo_width_inches", "must be from 0.25 to 7")
        if fmt == "excel":
            ok, value = self.typed(data, keys["header_color"], "branding")
            if ok:
                if _COLOR_RE.match(value):
                    out["header_color"] = value.lstrip("#").upper()
                else:
                    self.error(
                        "branding.header_color",
                        "must be six hexadecimal digits, for example 366092",
                    )
        return out

    def logo(self, value: str) -> Optional[Path]:
        path = "branding.logo_path"
        if self.base_dir is None:
            self.error(path, "a logo is only possible in a template file")
            return None
        if not value or "\x00" in value or len(value) > 255:
            self.error(path, "must be a file path of 1 to 255 characters")
            return None
        candidate = Path(value)
        if candidate.is_absolute() or re.match(r"^[A-Za-z]:", value):
            self.error(path, "must be a relative path in the template directory")
            return None
        try:
            resolved = safe_join(self.base_dir, value)
        except ValueError:
            self.error(path, "the path must stay in the directory of the template file")
            return None
        if resolved.suffix.lower() not in LOGO_SUFFIXES:
            self.error(path, "the logo must be a .png, .jpg or .jpeg file")
            return None
        if not resolved.is_file():
            self.error(path, f"file not found: {value}")
            return None
        if resolved.stat().st_size > MAX_LOGO_BYTES:
            self.error(path, f"the file is larger than {MAX_LOGO_BYTES} bytes")
            return None
        return resolved

    def document(
        self, raw: Dict[str, Any], fmt: str, global_vars: set
    ) -> Dict[str, str]:
        data = self.mapping(raw, "document")
        self.check_keys(data, DOCUMENT_KEYS, "document", fmt)
        allowed = global_vars - set(_TITLE_FORBIDDEN)
        out = {"title": "", "subtitle": ""}
        for key in DOCUMENT_KEYS:
            ok, value = self.typed(data, key, "document")
            if ok:
                out[key.name] = self.text(value, f"document.{key.name}", allowed)
        return out

    def header_footer(
        self, raw: Dict[str, Any], fmt: str, global_vars: set
    ) -> Dict[str, Any]:
        data = self.mapping(raw, "header_footer")
        self.check_keys(data, HEADER_FOOTER_KEYS, "header_footer", fmt)
        out: Dict[str, Any] = {
            "header_text": "",
            "footer_text": "",
            "include_page_numbers": False,
        }
        for key in HEADER_FOOTER_KEYS:
            if fmt not in key.formats:
                continue
            ok, value = self.typed(data, key, "header_footer")
            if not ok:
                continue
            if key.type == "string":
                value = self.text(value, f"header_footer.{key.name}", global_vars, 255)
            out[key.name] = value
        return out

    # -- sections
    def sections(
        self,
        raw: Dict[str, Any],
        fmt: str,
        global_vars: set,
        extra_fields: List[str],
    ) -> List[Dict[str, Any]]:
        if "sections" not in raw or raw["sections"] is None:
            self.error(
                "sections", "missing key. A template must have a list of sections"
            )
            return []
        sections = raw["sections"]
        if not isinstance(sections, list):
            self.error(
                "sections", f"must be a list, but the value is {_type_name(sections)}"
            )
            return []
        if not sections:
            self.error("sections", "the list is empty. Add one section or more")
            return []
        if len(sections) > MAX_SECTIONS:
            self.error("sections", f"too many sections. The maximum is {MAX_SECTIONS}")
            return []
        out = []
        seen_ids: Dict[str, int] = {}
        sheet_names: Dict[str, int] = {}
        for index, section in enumerate(sections):
            path = f"sections[{index}]"
            if not isinstance(section, dict):
                self.error(
                    path, f"must be a mapping, but the value is {_type_name(section)}"
                )
                continue
            normalized = self.section(section, path, fmt, global_vars, extra_fields)
            if normalized is None:
                continue
            section_id = normalized["id"]
            if section_id in seen_ids:
                self.error(
                    f"{path}.id",
                    f"duplicate id '{section_id}'. sections[{seen_ids[section_id]}] "
                    "has the same id",
                )
            seen_ids.setdefault(section_id, index)
            sheet_name = normalized.get("sheet_name")
            if fmt == "excel" and sheet_name:
                key = sheet_name.lower()
                if key in sheet_names:
                    self.error(
                        f"{path}.sheet_name",
                        f"duplicate sheet name '{sheet_name}'. "
                        f"sections[{sheet_names[key]}] has the same name",
                    )
                sheet_names.setdefault(key, index)
            out.append(normalized)
        if out and not any(s["enabled"] for s in out):
            self.error(
                "sections", "all sections are disabled. Enable one section or more"
            )
        return out

    def section(
        self,
        section: Dict[str, Any],
        path: str,
        fmt: str,
        global_vars: set,
        extra_fields: List[str],
    ) -> Optional[Dict[str, Any]]:
        content_types = CONTENT_TYPES[fmt]
        content_type = section.get("content_type")
        valid_type = True
        if "content_type" not in section:
            self.error(
                f"{path}.content_type",
                "missing key. Allowed values: " + ", ".join(content_types),
            )
            valid_type = False
        elif content_type not in content_types:
            self.error(
                f"{path}.content_type",
                f"unknown section type {content_type!r} for {_A_FORMAT[fmt]} template. "
                "Allowed values: " + ", ".join(content_types),
            )
            valid_type = False

        section_id = section.get("id")
        if "id" not in section:
            self.error(f"{path}.id", "missing key")
        elif not isinstance(section_id, str) or not _NAME_RE.match(section_id):
            self.error(
                f"{path}.id",
                "must start with a lowercase letter and contain only lowercase "
                "letters, digits and underscores",
            )
            section_id = None

        known = {k.name: k for k in SECTION_KEYS}
        allowed = [
            k.name
            for k in SECTION_KEYS
            if fmt in k.formats
            and (
                not valid_type or not k.content_types or content_type in k.content_types
            )
        ]
        for name in section:
            child = f"{path}.{name}"
            if name not in known:
                self.error(child, "unknown key. Allowed keys: " + ", ".join(allowed))
            elif name not in allowed:
                where = (
                    f"a '{content_type}' section of {_A_FORMAT[fmt]} template"
                    if valid_type
                    else f"{_A_FORMAT[fmt]} template"
                )
                self.error(
                    child,
                    f"this key is not valid in {where}. Allowed keys: "
                    + ", ".join(allowed),
                )
        if not valid_type or not section_id:
            return None

        out: Dict[str, Any] = {"id": section_id, "content_type": content_type}
        text_vars = {
            "service_title": global_vars | set(SERVICE_VARIABLES),
            "truncation_note": global_vars | set(SERVICE_VARIABLES),
        }
        for key in SECTION_KEYS:
            if key.name in ("id", "content_type") or key.name not in allowed:
                continue
            child = f"{path}.{key.name}"
            default = copy.deepcopy(key.default)
            if key.name == "table_style":
                default = _DEFAULT_TABLE_STYLE.get(content_type)
            if key.name == "sheet_name" and content_type == "service_summary":
                default = "Summary"
            if key.type == "columns":
                out["columns"] = self.columns(
                    section.get("columns"), child, fmt, content_type, extra_fields
                )
                continue
            ok, value = self.typed(section, key, path)
            if not ok:
                out[key.name] = default
                continue
            if key.type == "string" and key.name not in ("table_style", "sheet_name"):
                value = self.text(value, child, text_vars.get(key.name, global_vars))
            out[key.name] = value

        self.section_rules(out, path, fmt, global_vars)
        return out

    def section_rules(
        self, out: Dict[str, Any], path: str, fmt: str, global_vars: set
    ) -> None:
        content_type = out["content_type"]
        if "level" in out and not 1 <= out["level"] <= 3:
            self.error(f"{path}.level", "must be 1, 2 or 3")
            out["level"] = 1
        if "max_rows" in out and not 1 <= out["max_rows"] <= MAX_ROWS_LIMIT:
            self.error(f"{path}.max_rows", f"must be from 1 to {MAX_ROWS_LIMIT}")
            out["max_rows"] = 50
        if "max_columns" in out and not 1 <= out["max_columns"] <= MAX_COLUMNS:
            self.error(f"{path}.max_columns", f"must be from 1 to {MAX_COLUMNS}")
            out["max_columns"] = 6
        if out.get("table_style") is not None and fmt == "word":
            styles = word_table_styles()
            if out["table_style"] not in styles:
                self.error(
                    f"{path}.table_style",
                    f"unknown table style {out['table_style']!r}. Examples of "
                    "valid styles: " + ", ".join(WORD_TABLE_STYLES_FALLBACK),
                )
                out["table_style"] = _DEFAULT_TABLE_STYLE.get(content_type)
        if "paragraphs" in out:
            paragraphs = out["paragraphs"] or []
            checked = []
            if len(paragraphs) > MAX_PARAGRAPHS:
                self.error(
                    f"{path}.paragraphs",
                    f"too many paragraphs. The maximum is {MAX_PARAGRAPHS}",
                )
                paragraphs = []
            for index, paragraph in enumerate(paragraphs):
                child = f"{path}.paragraphs[{index}]"
                if not isinstance(paragraph, str):
                    self.error(
                        child,
                        f"must be a string, but the value is {_type_name(paragraph)}",
                    )
                    continue
                checked.append(self.text(paragraph, child, global_vars))
            out["paragraphs"] = checked
            if content_type == "text" and not checked and not out.get("title"):
                self.error(path, "a 'text' section must have a title or paragraphs")
        if "services" in out:
            services = out["services"]
            checked_services: List[str] = []
            if services is not None:
                if not services:
                    self.error(f"{path}.services", "the list is empty")
                elif len(services) > MAX_SERVICES:
                    self.error(
                        f"{path}.services",
                        f"too many services. The maximum is {MAX_SERVICES}",
                    )
                else:
                    for index, name in enumerate(services):
                        if not isinstance(name, str) or not name.strip():
                            self.error(
                                f"{path}.services[{index}]",
                                "must be a service name, for example EC2",
                            )
                        elif len(name) > 100:
                            self.error(
                                f"{path}.services[{index}]",
                                "a service name has a maximum of 100 characters",
                            )
                        else:
                            checked_services.append(name)
            out["services"] = checked_services or None
        if fmt == "excel" and content_type in ("service_summary", "resources"):
            sheet_name = out.get("sheet_name")
            if sheet_name is not None:
                if not 1 <= len(sheet_name) <= EXCEL_SHEET_NAME_MAX:
                    self.error(
                        f"{path}.sheet_name",
                        f"must have 1 to {EXCEL_SHEET_NAME_MAX} characters",
                    )
                elif _SHEET_NAME_FORBIDDEN.search(sheet_name) or "{{" in sheet_name:
                    self.error(
                        f"{path}.sheet_name",
                        "must not contain [ ] : * ? / \\ or a {{ variable }}",
                    )
            if content_type == "resources":
                if out["group_by_service"] and sheet_name is not None:
                    self.error(
                        f"{path}.sheet_name",
                        "only valid with group_by_service: false. With "
                        "group_by_service: true, each sheet has the service name",
                    )
                if not out["group_by_service"] and sheet_name is None:
                    self.error(
                        f"{path}.sheet_name",
                        "missing key. A 'resources' section with "
                        "group_by_service: false must have a sheet_name",
                    )

    def columns(
        self,
        value: Any,
        path: str,
        fmt: str,
        content_type: str,
        extra_fields: List[str],
    ) -> Any:
        if value is None or value == "auto":
            if content_type == "service_summary":
                return [
                    {"field": f, "heading": None, "width": None} for f in SUMMARY_FIELDS
                ]
            return "auto"
        if not isinstance(value, list):
            self.error(
                path,
                f"must be 'auto' or a list of columns, but the value is {_type_name(value)}",
            )
            return "auto"
        if not value:
            self.error(path, "the list is empty. Use 'auto' or add one column or more")
            return "auto"
        if len(value) > MAX_COLUMNS:
            self.error(path, f"too many columns. The maximum is {MAX_COLUMNS}")
            return "auto"
        if content_type == "service_summary":
            valid_fields = set(SUMMARY_FIELDS)
        else:
            valid_fields = set(KNOWN_RESOURCE_FIELDS) | set(extra_fields)
        width_range = (0.2, 10) if fmt == "word" else (1, 255)
        columns = []
        seen = set()
        for index, item in enumerate(value):
            child = f"{path}[{index}]"
            if isinstance(item, str):
                item = {"field": item}
            if not isinstance(item, dict):
                self.error(
                    child,
                    "must be a field name or a mapping with the key 'field', "
                    f"but the value is {_type_name(item)}",
                )
                continue
            self.check_keys(item, COLUMN_KEYS, child, fmt)
            name = item.get("field")
            if "field" not in item:
                self.error(f"{child}.field", "missing key")
                continue
            if not isinstance(name, str) or not _FIELD_RE.match(name):
                self.error(f"{child}.field", "must be a field name")
                continue
            dynamic = content_type == "resources" and any(
                name.startswith(prefix) and len(name) > len(prefix)
                for prefix in DYNAMIC_FIELD_PREFIXES
            )
            if name not in valid_fields and not dynamic:
                if content_type == "service_summary":
                    hint = "Allowed columns: " + ", ".join(SUMMARY_FIELDS)
                else:
                    hint = (
                        "Use a known field (for example service, type, id, name, "
                        "region, account_id, tags), a tags.<key> field, or add "
                        "the name to extra_fields"
                    )
                self.error(f"{child}.field", f"unknown column '{name}'. {hint}")
                continue
            if name in seen:
                self.error(f"{child}.field", f"duplicate column '{name}'")
                continue
            seen.add(name)
            column: Dict[str, Any] = {"field": name, "heading": None, "width": None}
            heading = item.get("heading")
            if heading is not None:
                if not isinstance(heading, str):
                    self.error(
                        f"{child}.heading",
                        f"must be a string, but the value is {_type_name(heading)}",
                    )
                elif not heading.strip() or len(heading) > 100:
                    self.error(f"{child}.heading", "must have 1 to 100 characters")
                elif "{{" in heading or "}}" in heading:
                    self.error(
                        f"{child}.heading", "a heading cannot contain a variable"
                    )
                else:
                    column["heading"] = heading
            width = item.get("width")
            if width is not None:
                if not _is_type(width, "number"):
                    self.error(
                        f"{child}.width",
                        f"must be a number, but the value is {_type_name(width)}",
                    )
                elif not width_range[0] <= width <= width_range[1]:
                    unit = "inches" if fmt == "word" else "characters"
                    self.error(
                        f"{child}.width",
                        f"must be from {width_range[0]} to {width_range[1]} {unit}",
                    )
                else:
                    column["width"] = float(width)
            columns.append(column)
        return columns or "auto"


def validate_template_data(
    raw: Any,
    expected_format: Optional[str] = None,
    source: str = "<template>",
    base_dir: Optional[Path] = None,
) -> ReportTemplate:
    """Validate parsed template data and return a :class:`ReportTemplate`.

    Raises :class:`TemplateValidationError` with every problem found.
    """
    validator = _Validator(expected_format, base_dir)
    data = validator.validate(raw)
    if validator.issues or data is None:
        raise TemplateValidationError(source, validator.issues)
    return ReportTemplate(
        format_type=data["format_type"],
        data=data,
        source=source,
        base_dir=base_dir,
        logo_file=validator.logo_file,
    )


# ----------------------------------------------------------------- loading
class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses a key written twice in one mapping.

    Plain PyYAML keeps the last one without a word, so a misplaced copy of a
    key silently changes the template.
    """

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            seen = set()
            for key_node, _ in node.value:
                if not isinstance(key_node, yaml.ScalarNode):
                    continue
                key = key_node.value
                if key in seen and key_node.tag != "tag:yaml.org,2002:merge":
                    raise yaml.constructor.ConstructorError(
                        None,
                        None,
                        f"duplicate key '{key}'",
                        key_node.start_mark,
                    )
                seen.add(key)
        return super().construct_mapping(node, deep)


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key '{key}'")
        result[key] = value
    return result


def read_template_file(path: Any) -> Tuple[Any, Path]:
    """Read and parse a template file. Returns ``(data, resolved_path)``.

    Raises :class:`TemplateValidationError` if the file cannot be used.
    """
    source = str(path)

    def fail(reason: str) -> TemplateValidationError:
        return TemplateValidationError(source, [TemplateIssue("", reason)])

    if not isinstance(path, (str, Path)) or not str(path) or "\x00" in str(path):
        raise fail("the template path is not valid")
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in TEMPLATE_SUFFIXES:
        raise fail(
            "unsupported file type. A template file must end with .yaml, .yml or .json"
        )
    try:
        resolved = file_path.resolve()
        if not resolved.is_file():
            raise fail("file not found, or the path is not a regular file")
        if resolved.stat().st_size > MAX_TEMPLATE_BYTES:
            raise fail(
                f"the file is {resolved.stat().st_size} bytes. "
                f"The maximum is {MAX_TEMPLATE_BYTES} bytes"
            )
        with open(resolved, "rb") as handle:
            raw_bytes = handle.read(MAX_TEMPLATE_BYTES + 1)
    except OSError as e:
        raise fail(f"cannot read the file: {e.strerror or e}") from None
    if len(raw_bytes) > MAX_TEMPLATE_BYTES:
        raise fail(f"the file is larger than {MAX_TEMPLATE_BYTES} bytes")
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise fail("the file is not UTF-8 text") from None
    try:
        if suffix == ".json":
            data = json.loads(text, object_pairs_hook=_no_duplicate_keys)
        else:
            data = yaml.load(text, Loader=_UniqueKeyLoader)  # noqa: S506 - SafeLoader
    except json.JSONDecodeError as e:
        raise fail(
            f"JSON syntax error at line {e.lineno}, column {e.colno}: {e.msg}"
        ) from None
    except ValueError as e:  # a key written twice in a JSON file
        raise fail(f"JSON error: {e}") from None
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        problem = getattr(e, "problem", None) or "the file is not valid YAML"
        raise fail(f"YAML syntax error{where}: {problem}") from None
    except RecursionError:
        raise fail("the file has too many nested levels") from None
    return data, resolved


def load_report_template(
    path: Any, expected_format: Optional[str] = None
) -> ReportTemplate:
    """Load, parse and validate a template file.

    Args:
        path: a ``.yaml``, ``.yml`` or ``.json`` file.
        expected_format: ``"word"`` or ``"excel"``; a template of the other
            format is an error.

    Raises:
        TemplateValidationError: with the file path, the key path and the
            reason for every problem.
    """
    data, resolved = read_template_file(path)
    return validate_template_data(
        data, expected_format, source=str(path), base_dir=resolved.parent
    )


def default_template(format_type: str) -> ReportTemplate:
    """The built-in template that reproduces the report without a template."""
    if format_type not in _DEFAULTS:
        raise ValueError(f"Unknown report format: {format_type!r}")
    return validate_template_data(
        copy.deepcopy(_DEFAULTS[format_type]),
        format_type,
        source="<built-in default>",
    )


def shipped_template_path(format_type: str) -> Path:
    """Path of the default template file in the repository ``templates/`` directory."""
    if format_type not in _SHIPPED_FILES:
        raise ValueError(f"Unknown report format: {format_type!r}")
    return (
        Path(__file__).resolve().parents[2] / "templates" / _SHIPPED_FILES[format_type]
    )


def default_template_text(format_type: str) -> str:
    """Text of the default template, for ``--print-default-template``.

    The shipped file is preferred because it has comments. If it is absent
    (for example the package was copied without ``templates/``), the built-in
    data is written as YAML (Word) or JSON (Excel).
    """
    path = shipped_template_path(format_type)
    try:
        if path.is_file() and path.stat().st_size <= MAX_TEMPLATE_BYTES:
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    data = _DEFAULTS[format_type]
    if format_type == "excel":
        return json.dumps(data, indent=2) + "\n"
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


# --------------------------------------------------------------- rendering
def _text(value: Any) -> str:
    return "" if value is None else str(value)


def build_context(
    template: ReportTemplate,
    resources: Sequence[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> Dict[str, str]:
    """Values for the global variables of ``template`` for these resources."""
    now = now or datetime.now(timezone.utc)
    account_ids = sorted(
        {
            _text(r.get("source_account_id") or r.get("account_id"))
            for r in resources
            if isinstance(r, dict)
            and (r.get("source_account_id") or r.get("account_id"))
        }
    )
    services = {r.get("service", "Unknown") for r in resources if isinstance(r, dict)}
    regions = {r.get("region", "Unknown") for r in resources if isinstance(r, dict)}
    context: Dict[str, str] = dict(template.variables)
    context.update(
        {
            "company_name": template.data["branding"]["company_name"],
            "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "generated_date": now.strftime("%Y-%m-%d"),
            "account_ids": ", ".join(account_ids),
            "account_count": str(len(account_ids)),
            "total_resources": str(len(resources)),
            "service_count": str(len(services)),
            "region_count": str(len(regions)),
        }
    )
    context["document_title"] = substitute(template.data["document"]["title"], context)
    context["document_subtitle"] = substitute(
        template.data["document"]["subtitle"], context
    )
    return context


def schema_reference() -> Dict[str, Tuple[Key, ...]]:
    """The schema tables, by group name (used by the docs check)."""
    return {
        "top level": TOP_LEVEL_KEYS,
        "document": DOCUMENT_KEYS,
        "branding": BRANDING_KEYS,
        "header_footer": HEADER_FOOTER_KEYS,
        "sections": SECTION_KEYS,
        "columns": COLUMN_KEYS,
    }


__all__ = [
    "TEMPLATE_VERSION",
    "FORMATS",
    "MAX_TEMPLATE_BYTES",
    "MAX_TEXT_LENGTH",
    "GLOBAL_VARIABLES",
    "SERVICE_VARIABLES",
    "SUMMARY_FIELDS",
    "KNOWN_RESOURCE_FIELDS",
    "CONTENT_TYPES",
    "DEFAULT_WORD_TEMPLATE",
    "DEFAULT_EXCEL_TEMPLATE",
    "Key",
    "ReportTemplate",
    "TemplateIssue",
    "TemplateValidationError",
    "build_context",
    "default_template",
    "default_template_text",
    "load_report_template",
    "placeholder_errors",
    "placeholder_names",
    "schema_reference",
    "shipped_template_path",
    "substitute",
    "validate_template_data",
    "word_table_styles",
]
