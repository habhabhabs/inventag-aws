"""InvenTag templates: reusable report layouts, tag policies and run settings.

A template is a small YAML file::

    format_version: 1
    kind: report            # report | tag-policy | config
    name: acme-bom
    description: Our standard inventory layout
    extends: standard-bom   # optional: inherit and override
    spec: {...}             # settings for this kind

See ``docs/templates/`` for the full guide and field reference.
"""

from .errors import TemplateError, TemplateIssue, TemplateNotFoundError
from .loader import TemplateFile, load_template_file, parse_template_text
from .registry import BUILTIN_DIR, ResolvedTemplate, TemplateRegistry, search_dirs
from .render_excel import render_excel
from .render_word import render_word
from .tag_policy import ComplianceReport, evaluate

__all__ = [
    "BUILTIN_DIR",
    "ComplianceReport",
    "ResolvedTemplate",
    "TemplateError",
    "TemplateFile",
    "TemplateIssue",
    "TemplateNotFoundError",
    "TemplateRegistry",
    "evaluate",
    "load_template_file",
    "parse_template_text",
    "render_excel",
    "render_word",
    "search_dirs",
]
