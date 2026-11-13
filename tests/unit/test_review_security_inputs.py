"""Release-gate review: untrusted names and values in output paths and cells."""

import copy
import zipfile

import openpyxl
import pytest

from inventag.security.safe_output import safe_filename_component, safe_join
from inventag.templating.loader import safe_relative_path
from inventag.templating.registry import TemplateRegistry
from inventag.templating.render_excel import render_excel

FORMULAS = ['=HYPERLINK("http://x","y")', "+cmd|' /C calc'!A0", "-1+1", "@SUM(A1)"]


def _resources():
    rows = []
    for i, text in enumerate(FORMULAS):
        rows.append(
            {
                "service": "EC2" if i % 2 else text,
                "resource_type": text,
                "resource_name": text,
                "resource_id": f"i-{i}",
                "account_id": "123456789012",
                "region": "us-east-1",
                "tags": {text: text, "Owner": text},
            }
        )
    return rows


@pytest.mark.parametrize("include_all_fields", [False, True])
def test_template_excel_has_no_formula_cell_in_headers_or_data(
    tmp_path, include_all_fields
):
    template = TemplateRegistry().resolve("standard-bom")
    template = copy.copy(template)
    template.spec = copy.deepcopy(template.spec)
    template.spec["excel"]["include_all_fields"] = include_all_fields
    path = render_excel(str(tmp_path / "r.xlsx"), _resources(), template)
    wb = openpyxl.load_workbook(path)
    formulas = [
        (ws.title, c.coordinate, c.value)
        for ws in wb.worksheets
        for row in ws.iter_rows()
        for c in row
        if c.data_type == "f"
    ]
    assert not formulas
    with zipfile.ZipFile(path) as z:
        sheets = b"".join(z.read(n) for n in z.namelist() if "worksheets" in n)
    assert b"<f>" not in sheets and b"<f " not in sheets


@pytest.mark.parametrize(
    "value",
    ["../../etc/passwd", "..\\..\\x", "/abs/path", "a/../../b", "\x00x", ".hidden", ""],
)
def test_untrusted_names_cannot_leave_the_output_folder(tmp_path, value):
    part = safe_filename_component(value)
    assert "/" not in part and "\\" not in part and ".." not in part
    assert not part.startswith(".")
    assert safe_join(tmp_path, part).parent == tmp_path.resolve()


@pytest.mark.parametrize(
    "reference",
    [
        "../outside.yaml",
        "/etc/passwd",
        "~/x.yaml",
        "a/../../x.yaml",
        "file:///etc/passwd",
        "..\\x.yaml",
    ],
)
def test_template_relative_paths_stay_in_the_template_folder(tmp_path, reference):
    with pytest.raises(ValueError):
        safe_relative_path(tmp_path, reference)


def test_template_symlink_out_of_the_folder_is_refused(tmp_path):
    outside = tmp_path / "outside.yaml"
    outside.write_text("x: 1")
    folder = tmp_path / "templates"
    folder.mkdir()
    (folder / "link.yaml").symlink_to(outside)
    with pytest.raises(ValueError):
        safe_relative_path(folder, "link.yaml")
