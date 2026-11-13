#!/usr/bin/env python3
"""Regenerate the sample outputs shown in the InvenTag docs.

Every sample on the docs pages comes from this script. It runs the real
InvenTag CLI in-process against mocked AWS (moto) with a small, fictional
estate (account 123456789012 and friends, "acme-*" resources), then:

* writes text previews (console output, sheet/column/row previews, Word
  outlines, JSON, changelog) into the docs, between markers like
  ``<!-- BEGIN EXAMPLE OUTPUT: name -->`` and ``<!-- END EXAMPLE OUTPUT: name -->``;
* renders PNG previews of Excel sheets and Word pages with LibreOffice;
* copies small sample files (.xlsx, .docx, .json) next to the images so the
  docs can offer them as downloads.

Nothing here talks to real AWS: credentials are fake and moto intercepts every
call. Usage (from the repository root):

    pip install -r requirements.txt moto pillow
    # LibreOffice (soffice) and poppler (pdftoppm) are needed for the images
    python scripts/docs/generate_example_outputs.py            # text + images
    python scripts/docs/generate_example_outputs.py --no-images
    python scripts/docs/generate_example_outputs.py --check    # exit 1 if docs are stale

Timestamps and random IDs are fixed so a re-run only changes the docs when
InvenTag's behaviour changes.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets" / "examples"
DOWNLOADS = ROOT / "website" / "static" / "downloads"
FIXED_STAMP = "20261112_090000"
FIXED_ISO = "2026-11-12T09:00:00+00:00"
FIXED_HUMAN = "2026-11-12 09:00 UTC"
ACCOUNT = "123456789012"
ORG_ACCOUNTS = {
    "111111111111": "Production",
    "222222222222": "Staging",
    "333333333333": "Shared services",
}
MAX_DOWNLOAD_BYTES = 200 * 1024

sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------- environment


def fake_aws_environment() -> None:
    for key in list(os.environ):
        if key.startswith("AWS_") or key in ("INVENTAG_TEMPLATE_PATH",):
            del os.environ[key]
    os.environ.update(
        {
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_EC2_METADATA_DISABLED": "true",
            "MOTO_EC2_LOAD_DEFAULT_AMIS": "false",
        }
    )


def drop_guard() -> None:
    """The CLI installs a process-wide read-only guard; seeding needs writes."""
    try:
        from inventag.security.read_only_guard import uninstall_global_guard
    except ImportError:  # older code without the guard
        return
    uninstall_global_guard()


def seed_account(session) -> None:
    """A small, fictional estate. Tags are chosen to show each kind of result."""
    random.seed(1234)
    from moto.moto_api._internal import mock_random

    mock_random.seed(1234)  # moto draws resource IDs from its own generator
    s3 = session.client("s3", region_name="us-east-1")
    buckets = {
        "acme-app-logs": {
            "Environment": "prod",
            "Owner": "platform",
            "CostCenter": "CC-1001",
            "Project": "storefront",
            "DataClassification": "internal",
        },
        "acme-data-lake": {
            "Environment": "prod",
            "Owner": "data",
            "CostCenter": "CC-2002",
        },
        "acme-reports": {
            "Environment": "Production",
            "Owner": "finance",
            "CostCenter": "1234",
            "Project": "reporting",
        },
        "acme-scratch": {},
    }
    for name, tags in buckets.items():
        s3.create_bucket(Bucket=name)
        if tags:
            s3.put_bucket_tagging(
                Bucket=name,
                Tagging={"TagSet": [{"Key": k, "Value": v} for k, v in tags.items()]},
            )
    ec2 = session.client("ec2", region_name="us-east-1")
    ec2.create_volume(
        AvailabilityZone="us-east-1a",
        Size=20,
        VolumeType="gp3",
        TagSpecifications=[
            {
                "ResourceType": "volume",
                "Tags": [{"Key": "Name", "Value": "acme-build-cache"}],
            }
        ],
    )
    image = ec2.register_image(Name="acme-base", RootDeviceName="/dev/sda1")["ImageId"]
    ec2.run_instances(
        ImageId=image,
        MinCount=1,
        MaxCount=1,
        InstanceType="t3.micro",
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {"Key": "Name", "Value": "acme-web-1"},
                    {"Key": "Owner", "Value": "platform"},
                    {"Key": "Environment", "Value": "prod"},
                ],
            }
        ],
    )
    iam = session.client("iam")
    role = iam.create_role(
        RoleName="acme-orders-api-role",
        AssumeRolePolicyDocument=json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        ),
    )["Role"]["Arn"]
    package = io.BytesIO()
    import zipfile

    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("index.py", "def handler(event, context):\n    return {}\n")
    session.client("lambda", region_name="us-east-1").create_function(
        FunctionName="acme-orders-api",
        Runtime="python3.12",
        Role=role,
        Handler="index.handler",
        Code={"ZipFile": package.getvalue()},
        Tags={"Owner": "platform", "Environment": "prod"},
    )
    ddb = session.client("dynamodb", region_name="us-east-1")
    ddb.create_table(
        TableName="acme-orders",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
        Tags=[
            {"Key": "Environment", "Value": "prod"},
            {"Key": "Owner", "Value": "data"},
        ],
    )


def seed_org_account(session, account_name: str) -> None:
    random.seed(sum(map(ord, account_name)))
    from moto.moto_api._internal import mock_random

    mock_random.seed(sum(map(ord, account_name)))
    s3 = session.client("s3", region_name="us-east-1")
    slug = account_name.lower().replace(" ", "-")
    s3.create_bucket(Bucket=f"acme-{slug}-artifacts")
    s3.put_bucket_tagging(
        Bucket=f"acme-{slug}-artifacts",
        Tagging={
            "TagSet": [
                {"Key": "Owner", "Value": "platform"},
                {
                    "Key": "Environment",
                    "Value": "prod" if slug == "production" else "dev",
                },
            ]
        },
    )


def assumed_session(account_id: str):
    import boto3

    creds = boto3.client("sts").assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/InvenTagReadOnly",
        RoleSessionName="seed",
    )["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


# ------------------------------------------------------------------ scenarios

PROJECT_TEMPLATES = {
    "acme-bom.yaml": """format_version: 1
kind: report
name: acme-bom
description: "Acme's inventory layout"
extends: standard-bom
spec:
  title: Acme Cloud Inventory
  company_name: Acme Ltd
  colors:
    header_fill: "0B5D1E"
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
""",
    "team-sheet.yaml": """format_version: 1
kind: report
name: team-sheet
description: One sheet, our columns
extends: standard-bom
spec:
  title: Platform team inventory
  columns:
    - { field: source_account_id, header: Account }
    - { field: service, header: Service }
    - { field: resource_type, header: Type }
    - { field: resource_name, header: Name }
    - { field: region, header: Region }
    - { field: raw_data.VolumeType, header: Volume type }
  tag_columns: [Owner, CostCenter, Environment]
  excel:
    layout: single-sheet
    single_sheet_name: Inventory
""",
    "board-report.yaml": """format_version: 1
kind: report
name: board-report
description: Branded summary for the leadership team
extends: executive-summary
spec:
  title: Cloud Estate Summary
  subtitle: Quarterly review
  company_name: Acme Ltd
  logo: brand/acme-logo.png
  logo_alt_text: Acme Ltd logo
  colors:
    header_fill: "4B2E83"
  tag_policy: security-baseline
  word:
    orientation: landscape
""",
    "network-review.yaml": """format_version: 1
kind: report
name: network-review
description: Every field, for a network review
extends: standard-bom
spec:
  title: Network review
  excel:
    include_all_fields: true
""",
}


@dataclass
class Run:
    name: str
    argv: List[str]
    exit_code: int = 0
    console: str = ""
    workdir: Optional[Path] = None
    files: Dict[str, Path] = field(default_factory=dict)


def logo_png() -> bytes:
    """A small, plain logo: a dark square with a lighter bar (no real brand)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (160, 160), "#4B2E83")
    draw = ImageDraw.Draw(img)
    draw.rectangle([30, 70, 130, 90], fill="#EDE7F6")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def prepare_project(workdir: Path) -> None:
    tdir = workdir / ".inventag" / "templates"
    (tdir / "brand").mkdir(parents=True, exist_ok=True)
    for name, text in PROJECT_TEMPLATES.items():
        (tdir / name).write_text(text)
    (tdir / "brand" / "acme-logo.png").write_bytes(logo_png())
    org = (ROOT / "inventag/templating/builtin/org-multi-account.yaml").read_text()
    (tdir / "our-org.yaml").write_text(
        org.replace("name: org-multi-account", "name: our-org")
    )


SPINNER = re.compile(r"[⣾⣽⣻⢿⡿⣟⣯⣷]")
# Services moto does not implement answer 404; the warning says so. Which of
# them is logged in a run changes (thread timing), and real accounts do not
# show it, so it is dropped from the samples.
MOTO_GAP = re.compile(r" failed \(404\); its resources there may be incomplete\.?$")
LOG_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - ")


def clean_console(text: str, workdir: Path, keep: Optional[str] = None) -> str:
    """Drop progress spinners, DEBUG/INFO lines and log timestamps.

    With ``keep``, only lines containing that text are kept (any level).
    """
    lines = []
    for raw in text.replace("\r", "\n").splitlines():
        line = raw.strip()
        if not line or SPINNER.search(line):
            continue
        if keep is not None:
            if keep not in line:
                continue
        elif " - DEBUG - " in line or " - INFO - " in line:
            continue
        line = LOG_PREFIX.sub("", line)
        if MOTO_GAP.search(line):
            continue  # moto has no such service (404); which one is logged varies
        if "No billing data available" in line:
            continue  # shown or not depending on log set-up; always true under moto
        lines.append(line)
    out = "\n".join(lines)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        out = out.replace(xdg, "~/.config")
    out = out.replace(str(ROOT), "~/inventag-aws")
    return normalise(out, workdir)


def normalise(text: str, workdir: Optional[Path] = None) -> str:
    """Replace paths, timestamps and run-specific stamps with fixed values."""
    if workdir is not None:
        text = text.replace(str(workdir), "~/acme-infra")
    # File-name stamps (YYYYMMDD_HHMMSS): stamps within a few seconds of each
    # other are one moment (a run can cross a second boundary); stamps further
    # apart stay distinct, in order of appearance, so two snapshots stay two.
    seen: Dict[str, str] = {}
    moments: List[tuple] = []  # (seconds, fixed stamp)

    def stamp(match):
        value = match.group(0)
        if value[:12] == FIXED_STAMP[:12] and value.endswith("00"):
            return value  # already a fixed stamp (see the changes scenario)
        if value not in seen:
            when = datetime.strptime(value, "%Y%m%d_%H%M%S").timestamp()
            for seconds, fixed in moments:
                if abs(when - seconds) <= 5:
                    seen[value] = fixed
                    break
            else:
                seen[value] = f"{FIXED_STAMP[:-4]}{len(moments):02d}00"
                moments.append((when, seen[value]))
        return seen[value]

    text = re.sub(r"(?<!\d)20\d{6}_\d{6}(?!\d)", stamp, text)
    text = re.sub(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(\+00:00|Z)?", FIXED_ISO, text
    )
    text = re.sub(r"20\d\d-\d\d-\d\d \d\d:\d\d UTC", FIXED_HUMAN, text)
    # The missing-module name depends on which Google packages are installed.
    text = re.sub(
        r"(libraries that are not installed \()google(?:\.[\w.]+)?(\))",
        r"\1google.auth\2",
        text,
    )
    return text


def stable_zip(src: Path, dest: Path) -> None:
    """Copy an Office file with fixed entry times and fixed dates in its
    document properties, so a re-run produces the same bytes."""
    import zipfile

    with (
        zipfile.ZipFile(src) as zin,
        zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zout,
    ):
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename.endswith(".xml"):
                data = normalise(data.decode("utf-8")).encode("utf-8")
            new = zipfile.ZipInfo(info.filename, date_time=(2026, 11, 12, 9, 0, 0))
            new.compress_type = zipfile.ZIP_DEFLATED
            new.external_attr = info.external_attr
            zout.writestr(new, data)


def run_cli(
    name: str, argv: List[str], workdir: Path, keep: Optional[str] = None
) -> Run:
    """Run the real CLI in-process and capture what a user would see."""
    cli_main = importlib.import_module("inventag.cli.main")
    run = Run(name, argv, workdir=workdir)
    random.seed(1234)
    out = io.StringIO()
    old_cwd = os.getcwd()
    os.chdir(workdir)
    old_argv = sys.argv
    sys.argv = ["inventag", *argv]
    import logging

    root = logging.getLogger()
    saved = list(root.handlers)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                cli_main.main()
            except SystemExit as stop:
                run.exit_code = stop.code or 0
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
        for handler in list(root.handlers):
            if handler not in saved:
                root.removeHandler(handler)
        for logger_name in ("inventag",):
            for handler in list(logging.getLogger(logger_name).handlers):
                logging.getLogger(logger_name).removeHandler(handler)
        drop_guard()
    run.console = clean_console(out.getvalue(), workdir, keep)
    for path in (
        sorted((workdir / "bom_output").glob("*"))
        if (workdir / "bom_output").exists()
        else []
    ):
        if path.is_file():
            run.files[path.suffix.lstrip(".") + ":" + path.name.split("_")[0]] = path
    return run


def run_templates_cli(argv: List[str], workdir: Path) -> str:
    from inventag.templating import cli as tcli

    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    os.chdir(workdir)
    try:
        code = tcli.main(argv, out=out, err=err)
    finally:
        os.chdir(old)
    text = out.getvalue() + err.getvalue()
    text = text.replace(os.environ.get("XDG_CONFIG_HOME", "\0"), "~/.config")
    text = text.replace(str(workdir), "~/acme-infra")
    text = text.replace(str(ROOT), "~/inventag-aws")
    return text.rstrip() + ("" if code == 0 else f"\n(exit code {code})")


@contextlib.contextmanager
def simulate_aws_error(service, operation, region, code_, message):
    """Make matching AWS calls fail with a real-looking AWS error response.

    Used only to show how InvenTag reports errors that moto cannot produce
    (expired tokens, AccessDenied, regions that are not enabled, throttling).
    """
    from botocore.client import BaseClient
    from botocore.exceptions import ClientError

    original = BaseClient._make_api_call

    def fake(self, operation_name, api_params):
        if (
            self.meta.service_model.service_name == service
            and (operation is None or operation_name == operation)
            and (region is None or self.meta.region_name == region)
        ):
            raise ClientError(
                {
                    "Error": {"Code": code_, "Message": message},
                    "ResponseMetadata": {"HTTPStatusCode": 400},
                },
                operation_name,
            )
        return original(self, operation_name, api_params)

    BaseClient._make_api_call = fake
    try:
        yield
    finally:
        BaseClient._make_api_call = original


# ------------------------------------------------------------------ previews


def md_cell(value) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\n", " ").replace("|", "\\|")
    if len(text) > 48:
        text = text[:45] + "..."
    # MDX: braces and angle brackets would be read as code/JSX.
    return (
        text.replace("{", "&#123;")
        .replace("}", "&#125;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def excel_preview(
    path: Path,
    sheet: Optional[str] = None,
    rows: int = 4,
    max_cols: int = 9,
    row_filter=None,
) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(path)
    lines = [f"**Sheets:** {', '.join(f'`{s}`' for s in wb.sheetnames)}", ""]
    ws = wb[sheet] if sheet else wb.worksheets[1 if len(wb.worksheets) > 1 else 0]
    header_row = 1
    if ws.title == "Summary":
        for r in range(1, ws.max_row + 1):
            if ws.cell(r, 1).value in ("Service",):
                header_row = r
                break
        # Show the title lines above the table as text.
        intro = [
            str(ws.cell(r, 1).value)
            for r in range(1, header_row)
            if ws.cell(r, 1).value
        ]
        lines += (
            [f"`{ws.title}` sheet:", ""] + [f"> {md_cell(t)}  " for t in intro] + [""]
        )
    else:
        lines += [f"`{ws.title}` sheet, first rows:", ""]
    headers = [c.value for c in ws[header_row]][: ws.max_column]
    while headers and headers[-1] is None:
        headers.pop()
    cut = len(headers) > max_cols
    shown = headers[:max_cols]
    lines.append(
        "| " + " | ".join(md_cell(h) for h in shown) + (" | ..." if cut else "") + " |"
    )
    lines.append("|" + "---|" * (len(shown) + (1 if cut else 0)))
    count = 0
    for values in ws.iter_rows(min_row=header_row + 1, values_only=True):
        if not any(v is not None for v in values[: len(headers)]):
            break
        if row_filter and not row_filter(dict(zip(headers, values))):
            continue
        lines.append(
            "| "
            + " | ".join(md_cell(v) for v in values[: len(shown)])
            + (" | ..." if cut else "")
            + " |"
        )
        count += 1
        if count >= rows:
            break
    if cut:
        lines += [
            "",
            f"The sheet has {len(headers)} columns; the first {max_cols} are shown.",
        ]
    return "\n".join(lines)


def word_preview(path: Path, table_index: Optional[int] = None, rows: int = 4) -> str:
    from docx import Document

    doc = Document(path)
    outline = []
    for p in doc.paragraphs:
        style = p.style.name
        if style == "Title":
            outline.append(f"- **{md_cell(p.text)}** (title)")
        elif style.startswith("Heading 1"):
            outline.append(f"- {md_cell(p.text)}")
        elif style.startswith("Heading 2"):
            outline.append(f"  - {md_cell(p.text)}")
    lines = ["**Document outline:**", ""] + outline
    if table_index is not None and len(doc.tables) > table_index:
        table = doc.tables[table_index]
        lines += ["", "A table from the document:", ""]
        header = [c.text for c in table.rows[0].cells]
        lines.append("| " + " | ".join(md_cell(h) for h in header) + " |")
        lines.append("|" + "---|" * len(header))
        for row in table.rows[1 : rows + 1]:
            lines.append("| " + " | ".join(md_cell(c.text) for c in row.cells) + " |")
        if len(table.rows) - 1 > rows:
            lines.append(f"\n({len(table.rows) - 1} rows in total; {rows} shown.)")
    return "\n".join(lines)


def code(text: str, lang: str = "text", title: str = "") -> str:
    title_attr = f' title="{title}"' if title else ""
    return f"```{lang}{title_attr}\n{text.rstrip()}\n```"


def details(summary: str, body: str) -> str:
    return f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n</details>"


# ---------------------------------------------------------------- images


def render_png(
    source: Path,
    out: Path,
    sheet: Optional[str] = None,
    page: int = 1,
    crop_height: int = 0,
) -> Optional[Path]:
    """Render one Excel sheet or one Word page to an optimised PNG."""
    if not shutil.which("soffice") or not shutil.which("pdftoppm"):
        return None
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src = tmp / source.name
        if source.suffix == ".xlsx":
            from openpyxl import load_workbook

            wb = load_workbook(source)
            for name in list(wb.sheetnames):
                if name != sheet:
                    del wb[name]
            ws = wb[sheet]
            ws.page_setup.orientation = "landscape"
            ws.page_setup.fitToWidth = 1
            ws.page_setup.fitToHeight = 0
            ws.sheet_properties.pageSetUpPr.fitToPage = True
            ws.print_options.gridLines = True
            wb.save(src)
        else:
            shutil.copy(source, src)
        env = dict(os.environ, HOME=str(tmp))
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(tmp),
                str(src),
            ],
            check=True,
            capture_output=True,
            env=env,
            timeout=180,
        )
        pdf = src.with_suffix(".pdf")
        subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r",
                "110",
                "-f",
                str(page),
                "-l",
                str(page),
                "-singlefile",
                str(pdf),
                str(tmp / "page"),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        img = Image.open(tmp / "page.png").convert("RGB")
        # Trim the empty page margin below the content.
        bbox = Image.eval(img.convert("L"), lambda v: 255 - v).getbbox()
        if bbox:
            pad = 16
            img = img.crop(
                (
                    max(bbox[0] - pad, 0),
                    max(bbox[1] - pad, 0),
                    min(bbox[2] + pad, img.width),
                    min(bbox[3] + pad, img.height),
                )
            )
        if crop_height and img.height > crop_height:
            img = img.crop((0, 0, img.width, crop_height))
        if img.width > 1200:
            img = img.resize(
                (1200, round(img.height * 1200 / img.width)), Image.LANCZOS
            )
        out.parent.mkdir(parents=True, exist_ok=True)
        img.quantize(colors=64, method=Image.Quantize.MEDIANCUT).save(
            out, "PNG", optimize=True
        )
        return out


def image_md(png: Optional[Path], alt: str, page: Path) -> str:
    if png is None:
        return ""
    rel = os.path.relpath(png, page.parent).replace(os.sep, "/")
    # Plain Markdown: JSX such as require() does not work in .md pages.
    safe_alt = alt.replace("[", "(").replace("]", ")").replace("\n", " ")
    return f"![{safe_alt}]({rel})"


def download_md(path: Path, label: str, page: Path) -> str:
    # Served from website/static/downloads, so the link never depends on the page's folder
    size = path.stat().st_size
    return f"[{label}](pathname:///inventag-aws/downloads/{path.name}) ({max(1, round(size / 1024))} KB, sample data)"


def publish_download(src: Path, name: str) -> Optional[Path]:
    if src.stat().st_size > MAX_DOWNLOAD_BYTES:
        return None
    dest = DOWNLOADS / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix == ".json":
        dest.write_text(normalise(src.read_text()))
    elif src.suffix in (".xlsx", ".docx"):
        stable_zip(src, dest)
    else:
        shutil.copy(src, dest)
    return dest


# ------------------------------------------------------------------ main


def collect(images: bool) -> Dict[str, str]:
    """Run every scenario and return {marker name: markdown}."""
    import boto3
    import moto

    blocks: Dict[str, str] = {}
    base = Path(tempfile.mkdtemp(prefix="inventag-docs-"))
    try:
        with moto.mock_aws():
            drop_guard()
            seed_account(boto3.Session())
            for account_id, name in ORG_ACCOUNTS.items():
                seed_org_account(assumed_session(account_id), name)

            def workdir(name: str) -> Path:
                path = base / name
                path.mkdir()
                prepare_project(path)
                os.environ["XDG_CONFIG_HOME"] = str(path / "xdg")
                return path

            regions = ["--account-regions", "us-east-1"]
            add = blocks.__setitem__
            pages = {
                "quick": DOCS / "getting-started/quick-start.md",
                "catalogue": DOCS / "templates/catalogue.md",
                "audit": DOCS / "examples/quick-audit.md",
                "org": DOCS / "examples/accounts-setup.md",
                "ci": DOCS / "examples/tag-policy-in-ci.md",
                "finops": DOCS / "examples/finops-cost-allocation.md",
                "security": DOCS / "examples/security-review.md",
                "board": DOCS / "examples/branded-executive-report.md",
                "columns": DOCS / "examples/custom-columns.md",
                "changes": DOCS / "guides/track-changes.md",
                "tags": DOCS / "guides/check-tag-compliance.md",
                "outputs": DOCS / "reference/outputs.md",
                "adapt": DOCS / "templates/adapt-a-template.md",
                "network": DOCS / "guides/network-and-security-analysis.md",
            }
            img_dir = ASSETS / "img"

            # 1. Default layout, no template
            w = workdir("default")
            r = run_cli("default", ["--create-excel", "--create-word", *regions], w)
            add("quick-default-console", code(r.console, title="Output"))
            add(
                "quick-default-excel",
                excel_preview(r.files["xlsx:multi"], "S3", rows=3, max_cols=8),
            )
            add(
                "quick-default-word", word_preview(r.files["docx:multi"], table_index=0)
            )

            # 2. standard-bom
            w = workdir("standard")
            r = run_cli(
                "standard",
                [
                    "--template",
                    "standard-bom",
                    "--create-excel",
                    "--create-word",
                    *regions,
                ],
                w,
            )
            add("standard-console", code(r.console, title="Output"))
            add(
                "standard-excel-summary",
                excel_preview(r.files["xlsx:multi"], "Summary", rows=12),
            )
            add(
                "standard-excel-s3",
                excel_preview(r.files["xlsx:multi"], "S3", rows=4, max_cols=11),
            )
            add(
                "standard-word",
                word_preview(r.files["docx:multi"], table_index=0, rows=10),
            )
            pic = (
                render_png(
                    r.files["xlsx:multi"],
                    img_dir / "standard-bom-s3-sheet.png",
                    sheet="S3",
                )
                if images
                else None
            )
            add(
                "standard-excel-image",
                image_md(
                    pic,
                    "Excel S3 sheet from the standard-bom template: a dark blue header row with Account, Region, Service, Type, Name, ID, ARN and one column per tag, followed by four bucket rows (sample data)",
                    pages["catalogue"],
                ),
            )
            pic = (
                render_png(
                    r.files["docx:multi"],
                    img_dir / "standard-bom-word-page1.png",
                    page=1,
                    crop_height=900,
                )
                if images
                else None
            )
            add(
                "standard-word-image",
                image_md(
                    pic,
                    "First page of the Word report from the standard-bom template: title, generation date, summary bullet list and the resources-by-service table (sample data)",
                    pages["catalogue"],
                ),
            )
            dl_x = publish_download(r.files["xlsx:multi"], "standard-bom-sample.xlsx")
            dl_d = publish_download(r.files["docx:multi"], "standard-bom-sample.docx")
            add(
                "standard-downloads",
                " and ".join(
                    download_md(p, label, pages["catalogue"])
                    for p, label in (
                        (dl_x, "Download the sample workbook"),
                        (dl_d, "the sample Word report"),
                    )
                    if p
                ),
            )

            # 3. executive-summary
            w = workdir("exec")
            r = run_cli(
                "exec",
                [
                    "--template",
                    "executive-summary",
                    "--create-excel",
                    "--create-word",
                    *regions,
                ],
                w,
            )
            add(
                "exec-excel",
                excel_preview(r.files["xlsx:multi"], "Resources", rows=4, max_cols=7),
            )
            add(
                "exec-word", word_preview(r.files["docx:multi"], table_index=0, rows=10)
            )

            # 4. finops-cost-report
            w = workdir("finops")
            r = run_cli(
                "finops",
                [
                    "--template",
                    "finops-cost-report",
                    "--create-excel",
                    "--create-word",
                    *regions,
                ],
                w,
            )
            add("finops-console", code(r.console, title="Output"))
            add(
                "finops-excel-compliance",
                excel_preview(
                    r.files["xlsx:multi"],
                    "Tag Compliance",
                    rows=4,
                    max_cols=9,
                    row_filter=lambda row: str(row.get("Resource", "")).startswith(
                        "acme-"
                    ),
                ),
            )
            add(
                "finops-excel-s3",
                excel_preview(r.files["xlsx:multi"], "S3", rows=4, max_cols=11),
            )
            add(
                "finops-word",
                word_preview(r.files["docx:multi"], table_index=0, rows=4),
            )
            pic = (
                render_png(
                    r.files["xlsx:multi"],
                    img_dir / "finops-tag-compliance-sheet.png",
                    sheet="Tag Compliance",
                    crop_height=700,
                )
                if images
                else None
            )
            add(
                "finops-compliance-image",
                image_md(
                    pic,
                    "Tag Compliance sheet: one row per resource with account, region, service, type, resource, ARN, status, missing tags and problems, followed by the policy rules table (sample data)",
                    pages["finops"],
                ),
            )
            report = json.loads(normalise(r.files["json:tag"].read_text()))
            short = dict(report)
            short["non_compliant_resources"] = [
                x
                for x in report["non_compliant_resources"]
                if x["resource_id"] == "acme-reports"
            ]
            add(
                "finops-json",
                code(
                    json.dumps(short, indent=2),
                    "json",
                    "tag_compliance_" + FIXED_STAMP + ".json (one resource shown)",
                ),
            )
            add(
                "finops-json-summary",
                code(json.dumps(report["summary"], indent=2), "json", "summary"),
            )
            dl = publish_download(r.files["json:tag"], "tag-compliance-sample.json")
            add(
                "finops-downloads",
                (
                    download_md(
                        dl, "Download the sample tag-compliance JSON", pages["finops"]
                    )
                    if dl
                    else ""
                ),
            )
            add(
                "outputs-json",
                code(
                    json.dumps(short, indent=2),
                    "json",
                    "tag_compliance_" + FIXED_STAMP + ".json (one resource shown)",
                ),
            )

            # 5. security-baseline
            w = workdir("security")
            r = run_cli(
                "security",
                [
                    "--template",
                    "standard-bom",
                    "--template",
                    "security-baseline",
                    "--create-excel",
                    "--create-word",
                    *regions,
                ],
                w,
            )
            add("security-console", code(r.console, title="Output"))
            add(
                "security-excel-compliance",
                excel_preview(
                    r.files["xlsx:multi"],
                    "Tag Compliance",
                    rows=4,
                    max_cols=9,
                    row_filter=lambda row: str(row.get("Resource", "")).startswith(
                        "acme-"
                    ),
                ),
            )

            # 6. ci-pipeline
            w = workdir("ci")
            r = run_cli("ci", ["--template", "ci-pipeline"], w)
            add(
                "ci-console",
                code(r.console + f"\n$ echo $?\n{r.exit_code}", title="Terminal"),
            )
            add(
                "ci-files",
                code(
                    "\n".join(sorted(p.name for p in (w / "bom_output").iterdir())),
                    title="bom_output/",
                ),
            )
            summary_script = (
                "import json, glob\n"
                "r = json.load(open(sorted(glob.glob('bom_output/tag_compliance_*.json'))[-1]))\n"
                "print(f\"{r['summary']['non_compliant']} non-compliant resources\")\n"
                "for x in r['non_compliant_resources'][:10]:\n"
                "    print('-', x['service'], x['resource_id'], 'missing:', ', '.join(x['missing']))\n"
            )
            proc = subprocess.run(
                [sys.executable, "-c", summary_script],
                cwd=w,
                capture_output=True,
                text=True,
                check=True,
            )
            add("ci-summary-output", code(proc.stdout, title="Job summary"))

            # 7. organization
            w = workdir("org")
            add(
                "org-validate",
                code(run_templates_cli(["validate", "our-org"], w), title="Output"),
            )
            r = run_cli("org", ["--template", "our-org"], w)
            add("org-console", code(r.console, title="Output"))
            add(
                "org-excel-summary",
                excel_preview(r.files["xlsx:multi"], "Summary", rows=10),
            )
            add(
                "org-excel-s3",
                excel_preview(r.files["xlsx:multi"], "S3", rows=4, max_cols=7),
            )

            # 8. branded board report
            w = workdir("board")
            add(
                "board-validate",
                code(
                    run_templates_cli(["validate", "board-report"], w), title="Output"
                ),
            )
            r = run_cli(
                "board", ["--template", "board-report", "--create-word", *regions], w
            )
            add("board-console", code(r.console, title="Output"))
            add(
                "board-word", word_preview(r.files["docx:multi"], table_index=1, rows=4)
            )
            pic = (
                render_png(
                    r.files["docx:multi"],
                    img_dir / "board-report-word-page1.png",
                    page=1,
                )
                if images
                else None
            )
            add(
                "board-image",
                image_md(
                    pic,
                    "First page of the branded landscape Word report: a purple square logo, the title Cloud Estate Summary, Quarterly review, Prepared for Acme Ltd and the summary list (sample data)",
                    pages["board"],
                ),
            )
            dl = publish_download(r.files["docx:multi"], "board-report-sample.docx")
            add(
                "board-downloads",
                (
                    download_md(dl, "Download the sample Word report", pages["board"])
                    if dl
                    else ""
                ),
            )
            (w / ".inventag/templates/brand/acme-logo.png").unlink()
            err = run_cli(
                "board-missing",
                ["--template", "board-report", "--create-word", *regions],
                w,
            )
            add(
                "board-missing-logo",
                code(err.console + f"\n$ echo $?\n{err.exit_code}", title="Terminal"),
            )

            # 9. custom columns
            w = workdir("columns")
            add(
                "columns-validate",
                code(
                    run_templates_cli(["validate", "team-sheet"], w), title="Output"
                ),
            )
            r = run_cli(
                "columns", ["--template", "team-sheet", "--create-excel", *regions], w
            )
            add("columns-console", code(r.console, title="Output"))
            add(
                "columns-excel",
                excel_preview(
                    r.files["xlsx:multi"],
                    "Inventory",
                    rows=6,
                    max_cols=9,
                    row_filter=lambda row: row.get("Type") in ("Volume", "Bucket"),
                ),
            )
            pic = (
                render_png(
                    r.files["xlsx:multi"],
                    img_dir / "team-sheet-inventory.png",
                    sheet="Inventory",
                    crop_height=600,
                )
                if images
                else None
            )
            add(
                "columns-image",
                image_md(
                    pic,
                    "Inventory sheet with the columns chosen in the team-sheet template: Account, Service, Type, Name, Region, Volume type and three tag columns (sample data)",
                    pages["columns"],
                ),
            )

            # 10. adapt walkthrough (templates CLI)
            w = workdir("adapt")
            (w / ".inventag/templates/acme-bom.yaml").unlink()
            add(
                "adapt-init",
                code(
                    run_templates_cli(
                        [
                            "init",
                            "standard-bom",
                            "--output",
                            ".inventag/templates/acme-bom.yaml",
                            "--extend",
                        ],
                        w,
                    ),
                    title="Output",
                ),
            )
            add(
                "adapt-init-file",
                code(
                    (w / ".inventag/templates/acme-bom.yaml").read_text(),
                    "yaml",
                    ".inventag/templates/acme-bom.yaml",
                ),
            )
            (w / ".inventag/templates/acme-bom.yaml").write_text(
                PROJECT_TEMPLATES["acme-bom.yaml"].replace("layout:", "layuot:")
            )
            add(
                "adapt-validate-error",
                code(run_templates_cli(["validate", "acme-bom"], w), title="Output"),
            )
            (w / ".inventag/templates/acme-bom.yaml").write_text(
                PROJECT_TEMPLATES["acme-bom.yaml"]
            )
            add(
                "adapt-validate-ok",
                code(run_templates_cli(["validate", "acme-bom"], w), title="Output"),
            )
            add(
                "adapt-list",
                code(
                    run_templates_cli(["list", "--kind", "report"], w), title="Output"
                ),
            )
            r = run_cli(
                "adapt", ["--template", "acme-bom", "--create-excel", *regions], w
            )
            add("adapt-console", code(r.console, title="Output"))
            add(
                "adapt-excel",
                excel_preview(
                    r.files["xlsx:multi"],
                    "Resources",
                    rows=4,
                    max_cols=10,
                    row_filter=lambda row: row.get("Service") == "S3",
                ),
            )
            plain = base / "plain"
            plain.mkdir()
            os.environ["XDG_CONFIG_HOME"] = str(plain / "xdg")
            add(
                "catalogue-list",
                code(run_templates_cli(["list"], plain), title="Output"),
            )

            # 11. two runs: changelog and snapshot diff
            w = workdir("changes")
            run_cli("changes-1", ["--create-excel", *regions], w)
            drop_guard()
            boto3.client("s3", region_name="us-east-1").create_bucket(
                Bucket="acme-new-bucket"
            )
            r = run_cli("changes-2", ["--create-excel", *regions], w)
            # Two runs are only a second or two apart, so give each snapshot a
            # fixed, distinct stamp one minute after the one before.
            state_ids = sorted(
                p.stem[len("state_") :]
                for p in (w / "bom_output/state").glob("state_*.json")
            )
            fixed_ids = {
                sid: f"{FIXED_STAMP[:-4]}{i:02d}00" for i, sid in enumerate(state_ids)
            }

            def fix_states(text: str) -> str:
                for sid, fixed in fixed_ids.items():
                    text = text.replace(sid, fixed)
                return text

            changelog = next((w / "bom_output").glob("changelog_*.md"))
            tree = sorted(
                str(p.relative_to(w))
                for p in (w / "bom_output").rglob("*")
                if p.is_file() and p.suffix in (".json", ".md")
            )
            tree = [
                (
                    f"bom_output/changelog_{fixed_ids[state_ids[-1]]}.md"
                    if line.startswith("bom_output/changelog_")
                    else fix_states(line)
                )
                for line in tree
            ]
            add(
                "changes-tree",
                code(
                    "\n".join(sorted(tree)),
                    title="bom_output/ after two runs (reports omitted)",
                ),
            )
            add(
                "changes-changelog",
                details(
                    f"changelog_{fixed_ids[state_ids[-1]]}.md (first 30 lines)",
                    code(
                        "\n".join(
                            normalise(fix_states(changelog.read_text())).splitlines()[
                                :30
                            ]
                        ),
                        "markdown",
                    ),
                ),
            )
            diff_script = (
                "import json, glob\n"
                "old, new = sorted(glob.glob('bom_output/state/state_*.json'))[-2:]\n"
                "ids = lambda f: {r.get('arn') or r.get('id') for r in json.load(open(f))['resources']}\n"
                "a, b = ids(old), ids(new)\n"
                "print('Added:', sorted(b - a))\n"
                "print('Removed:', sorted(a - b))\n"
            )
            proc = subprocess.run(
                [sys.executable, "-c", diff_script],
                cwd=w,
                capture_output=True,
                text=True,
                check=True,
            )
            add("changes-diff", code(proc.stdout, title="Output"))
            snap = json.loads(
                sorted((w / "bom_output/state").glob("state_*.json"))[-1].read_text()
            )
            first = next(
                x
                for x in snap.get("resources", [])
                if x.get("resource_id") == "acme-app-logs"
            )
            keep = {
                k: first.get(k)
                for k in (
                    "service",
                    "resource_type",
                    "resource_id",
                    "arn",
                    "region",
                    "tags",
                    "source_account_id",
                )
            }
            structure = {
                k: (
                    "..."
                    if k == "resources"
                    else (v if not isinstance(v, (dict, list)) else "...")
                )
                for k, v in snap.items()
            }
            add(
                "changes-snapshot",
                code(
                    normalise(
                        json.dumps(
                            {
                                "top_level_keys": sorted(snap.keys()),
                                "one_resource": keep,
                            },
                            indent=2,
                            default=str,
                        )
                    ),
                    "json",
                    "state/state_<timestamp>.json (structure)",
                ),
            )
            del structure

            # 13. credentials, read-only guard, S3 upload, flags that fail loudly
            w = workdir("safety")
            r = run_cli(
                "validate-credentials",
                ["--validate-credentials", "--verbose", *regions],
                w,
                keep="credentials",
            )
            add(
                "validate-credentials",
                code(r.console + f"\n$ echo $?\n{r.exit_code}", title="Terminal"),
            )
            r = run_cli(
                "validate-ops",
                [
                    "--validate-operations",
                    "ec2:DescribeInstances",
                    "s3:GetBucketTagging",
                    "s3:PutObject",
                    "secretsmanager:GetSecretValue",
                ],
                w,
            )
            add(
                "validate-operations",
                code(r.console + f"\n$ echo $?\n{r.exit_code}", title="Terminal"),
            )
            for flag in (
                ["--create-google-docs"],
                ["--risk-threshold", "HIGH"],
                ["--compliance-standard", "soc2"],
                ["--disable-production-safety"],
            ):
                r = run_cli("flag", flag, w)
                blocks.setdefault("failing-flags", "")
                blocks[
                    "failing-flags"
                ] += f"$ inventag {' '.join(flag)}\n{r.console}\n(exit code {r.exit_code})\n\n"
            blocks["failing-flags"] = code(
                blocks["failing-flags"].strip(), title="Terminal"
            )
            r = run_cli(
                "bare-role", ["--cross-account-role", "InvenTagReadOnly", *regions], w
            )
            add(
                "bare-role",
                code(r.console + f"\n$ echo $?\n{r.exit_code}", title="Terminal"),
            )
            drop_guard()
            boto3.client("s3", region_name="us-east-1").create_bucket(
                Bucket="acme-inventory-reports"
            )
            r = run_cli(
                "s3",
                [
                    "--template",
                    "standard-bom",
                    "--create-excel",
                    *regions,
                    "--s3-bucket",
                    "acme-inventory-reports",
                    "--s3-key-prefix",
                    "inventag/",
                    "--audit-output",
                    "audit.json",
                ],
                w,
            )
            add("s3-console", code(r.console, title="Output"))
            drop_guard()
            keys = [
                o["Key"]
                for o in boto3.client("s3", region_name="us-east-1")
                .list_objects_v2(Bucket="acme-inventory-reports")
                .get("Contents", [])
            ]
            add(
                "s3-keys",
                code("\n".join(keys), title="Objects in s3://acme-inventory-reports"),
            )
            audit = json.loads((w / "audit.json").read_text())
            audit["operations"] = audit["operations"][:6] + (
                ["..."] if len(audit["operations"]) > 6 else []
            )
            add(
                "audit-json",
                code(
                    json.dumps(audit, indent=2),
                    "json",
                    "audit.json (first operations shown)",
                ),
            )

            # 14. errors people hit, with simulated AWS error responses
            w = workdir("errors")
            simulations = {
                "error-expired-token": (
                    "sts",
                    "GetCallerIdentity",
                    None,
                    "InvalidClientTokenId",
                    "The security token included in the request is invalid.",
                ),
                "error-access-denied-ce": (
                    "ce",
                    "GetCostAndUsage",
                    None,
                    "AccessDeniedException",
                    "User: arn:aws:sts::123456789012:assumed-role/InvenTagReadOnly/session is not authorized to perform: ce:GetCostAndUsage",
                ),
                "error-region-disabled": (
                    "ec2",
                    None,
                    "ap-east-1",
                    "AuthFailure",
                    "AWS was not able to validate the provided access credentials",
                ),
            }
            for name, (
                service,
                operation,
                region,
                err_code,
                message,
            ) in simulations.items():
                argv = [
                    "--create-excel",
                    "--account-regions",
                    "us-east-1,ap-east-1" if region else "us-east-1",
                ]
                quiet = name == "error-access-denied-ce"
                with simulate_aws_error(service, operation, region, err_code, message):
                    r = run_cli(name, argv, w)
                body = r.console + f"\n$ echo $?\n{r.exit_code}"
                if quiet:
                    with simulate_aws_error(
                        service, operation, region, err_code, message
                    ):
                        v = run_cli(name, argv + ["--debug"], w, keep=err_code)
                    body += (
                        "\n\n$ # the same run with --debug, lines that mention "
                        + err_code
                        + "\n"
                        + (v.console or "(none)")
                    )
                add(name, code(body, title="Terminal (simulated AWS error response)"))
            saved_env = {
                k: os.environ.pop(k)
                for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
            }
            os.environ["AWS_SHARED_CREDENTIALS_FILE"] = str(w / "none")
            os.environ["AWS_CONFIG_FILE"] = str(w / "none")
            r = run_cli("no-credentials", ["--create-excel", *regions], w)
            add(
                "error-no-credentials",
                code(r.console + f"\n$ echo $?\n{r.exit_code}", title="Terminal"),
            )
            os.environ.update(saved_env)
            del os.environ["AWS_SHARED_CREDENTIALS_FILE"], os.environ["AWS_CONFIG_FILE"]
            (w / "bad-accounts.yaml").write_text(
                "accounts:\n  - account_id: 123456789012\n"
            )
            r = run_cli(
                "bad-accounts",
                [
                    "--accounts-file",
                    "bad-accounts.yaml",
                    "--validate-config-only",
                    "--skip-credential-validation",
                ],
                w,
            )
            add(
                "error-bad-accounts",
                code(r.console + f"\n$ echo $?\n{r.exit_code}", title="Terminal"),
            )
            (w / "bad.yaml").write_text(
                "kind: report\nname: bad\nspec:\n  colors:\n    header_fill: blue\n"
            )
            r = run_cli("bad-template", ["--template", "./bad.yaml", *regions], w)
            add(
                "error-bad-template",
                code(r.console + f"\n$ echo $?\n{r.exit_code}", title="Terminal"),
            )
            r = run_cli("no-template", ["--template", "acme-bomm", *regions], w)
            add(
                "error-unknown-template",
                code(r.console + f"\n$ echo $?\n{r.exit_code}", title="Terminal"),
            )

            # 12. network review (all fields)
            w = workdir("network")
            r = run_cli(
                "network",
                ["--template", "network-review", "--create-excel", *regions],
                w,
            )
            from openpyxl import load_workbook

            vpc = load_workbook(r.files["xlsx:multi"])["VPC"]
            headers = [c.value for c in vpc[1]]
            raw = [h for h in headers if str(h).startswith("raw_data.")]
            add(
                "network-columns",
                f"The VPC sheet has {len(headers)} columns. The `raw_data.*` columns in this sample are:\n\n"
                + code(", ".join(raw)),
            )

            # 13. network and security analysis sheets
            w = workdir("analysis")
            r = run_cli(
                "analysis",
                [
                    "--create-excel",
                    "--enable-network-analysis",
                    "--enable-security-analysis",
                    *regions,
                ],
                w,
            )
            add("analysis-console", code(r.console, title="Output"))
            add(
                "analysis-network",
                excel_preview(
                    r.files["xlsx:multi"], "Network Analysis", rows=1, max_cols=8
                ),
            )
            add(
                "analysis-security",
                excel_preview(
                    r.files["xlsx:multi"], "Security Analysis", rows=1, max_cols=9
                ),
            )
    finally:
        drop_guard()
        shutil.rmtree(base, ignore_errors=True)
    return {name: normalise(body) for name, body in blocks.items()}


BEGIN = "<!-- BEGIN EXAMPLE OUTPUT: {name} -->"
END = "<!-- END EXAMPLE OUTPUT: {name} -->"
MARKER = re.compile(
    r"<!-- BEGIN EXAMPLE OUTPUT: ([a-z0-9-]+) -->.*?<!-- END EXAMPLE OUTPUT: \1 -->",
    re.S,
)


# The audit sample's call totals move by one or two between runs (retries and
# thread timing), so they do not count as a change.
VOLATILE = re.compile(r'("(?:total|allowed)_calls": )\d+')


def apply(blocks: Dict[str, str], check: bool) -> int:
    stale, unknown = [], []
    used = set()
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text()

        def fill(match):
            name = match.group(1)
            used.add(name)
            if name not in blocks:
                unknown.append(f"{page.relative_to(ROOT)}: {name}")
                return match.group(0)
            body = blocks[name].strip()
            if not body:  # images were not rendered (--check, --no-images)
                return match.group(0)
            return f"{BEGIN.format(name=name)}\n\n{body}\n\n{END.format(name=name)}"

        new = MARKER.sub(fill, text)
        if VOLATILE.sub(r"\1N", new) != VOLATILE.sub(r"\1N", text):
            stale.append(str(page.relative_to(ROOT)))
            if not check:
                page.write_text(new)
    for name in unknown:
        print(f"unknown marker: {name}", file=sys.stderr)
    for name in sorted(set(blocks) - used):
        print(f"note: output '{name}' is not used on any page", file=sys.stderr)
    if check and stale:
        print("Out of date: " + ", ".join(stale), file=sys.stderr)
        return 1
    print(
        ("Checked " if check else "Updated ") + f"{len(stale)} page(s)"
        if not check
        else "Docs are up to date"
    )
    return 1 if unknown else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--no-images", action="store_true", help="Skip PNG renders and downloads"
    )
    parser.add_argument(
        "--check", action="store_true", help="Only report pages whose samples are stale"
    )
    args = parser.parse_args()
    fake_aws_environment()
    blocks = collect(images=not (args.no_images or args.check))
    return apply(blocks, args.check)


if __name__ == "__main__":
    sys.exit(main())
