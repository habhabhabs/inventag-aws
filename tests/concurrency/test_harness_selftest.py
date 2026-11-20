"""A5: the tools of the equality and race tests are tested themselves (fast, no scan).

A comparator that finds no difference proves nothing until it has been shown to find
one. These tests give it a changed cell, a moved sheet, a changed paragraph and a
changed key order, and give the hold rules their two ways out (event and timeout).
"""

import json
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from tests.concurrency import _child, compare, harness


def _book(path: Path, sheets: dict):
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    wb.save(path)


def _folders(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    return a, b


def test_equal_folders_have_no_difference(tmp_path):
    a, b = _folders(tmp_path)
    for folder in (a, b):
        _book(folder / "r.xlsx", {"Summary": [["x", 1]], "EC2": [["id"], ["i-1"]]})
        (folder / "s.json").write_text('{"b": 1, "a": 2}')
    assert compare.describe_difference(a, b) is None


def test_a_changed_cell_is_named_with_sheet_row_and_column(tmp_path):
    a, b = _folders(tmp_path)
    _book(a / "r.xlsx", {"EC2": [["id"], ["i-1"], ["i-2"]]})
    _book(b / "r.xlsx", {"EC2": [["id"], ["i-1"], ["i-3"]]})
    assert compare.describe_difference(a, b) == (
        "r.xlsx/EC2: row 3 column 1: 'i-2' against 'i-3'"
    )


def test_a_moved_sheet_and_a_missing_file_are_found(tmp_path):
    a, b = _folders(tmp_path)
    _book(a / "r.xlsx", {"A": [[1]], "B": [[1]]})
    _book(b / "r.xlsx", {"B": [[1]], "A": [[1]]})
    assert "sheets ['A', 'B'] against ['B', 'A']" in compare.describe_difference(a, b)
    (b / "extra.json").write_text("{}")
    assert "different files" in compare.describe_difference(a, b)


def test_a_changed_key_order_in_json_is_a_difference_and_the_path_is_named(tmp_path):
    a, b = _folders(tmp_path)
    (a / "s.json").write_text('{"x": {"b": 1, "a": 2}}')
    (b / "s.json").write_text('{"x": {"a": 2, "b": 1}}')
    assert compare.describe_difference(a, b) == (
        "s.json: bytes differ; first difference at $.x (keys or key order)"
    )


def test_the_folder_a_run_names_in_its_files_is_not_a_difference(tmp_path):
    a, b = _folders(tmp_path)
    (a / "m.json").write_text(json.dumps({"file": str(a / "state_1.json")}))
    (b / "m.json").write_text(json.dumps({"file": str(b / "state_1.json")}))
    assert compare.describe_difference(a, b) is None


def test_a_changed_paragraph_and_table_cell_in_word_are_found(tmp_path):
    from docx import Document

    a, b = _folders(tmp_path)
    for folder, text, cell in ((a, "one", "x"), (b, "one", "y")):
        doc = Document()
        doc.add_paragraph(text)
        table = doc.add_table(rows=1, cols=1)
        table.rows[0].cells[0].text = cell
        doc.save(folder / "r.docx")
    assert "r.docx: line 2" in compare.describe_difference(a, b)


def test_the_fixed_clock_stops_every_wall_clock_reader():
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "from tests.concurrency._child import install_fixed_clock\n"
        "install_fixed_clock('2026-01-15T12:00:00+00:00')\n"
        "import datetime, time, logging\n"
        "print(datetime.datetime.now().isoformat(), datetime.datetime.utcnow().isoformat(),"
        " datetime.date.today().isoformat(), int(time.time()),"
        " time.strftime('%%H:%%M:%%S', time.gmtime()), time.monotonic() > 0)\n"
        "rec = logging.LogRecord('x', 20, 'f', 1, 'm', (), None)\n"
        "print(logging.Formatter('%%(asctime)s').format(rec)[:19])\n"
    ) % str(harness.REPO)
    out = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    assert out[0].endswith("True")
    first = out[0].split()
    assert first[1].startswith("2026-01-15T12:00:00")
    assert first[2] == "2026-01-15" and first[3] == "1768478400"
    assert first[4] == "12:00:00"
    assert out[1].endswith(":00:00")


def _request(service, operation, key="K"):
    return SimpleNamespace(
        url=f"https://{service}.us-east-1.amazonaws.com/",
        headers={"Authorization": f"AWS4-HMAC-SHA256 Credential={key}/20260115/x"},
    )


def test_a_hold_ends_by_the_event_when_the_other_request_starts():
    rules = [
        dict(
            name="h",
            match=dict(service="ec2", operation="A"),
            until=dict(service="ec2", operation="B"),
            timeout=30,
        )
    ]
    holds = _child.Holds(rules)
    holds.first_key = "K"
    done = threading.Event()

    def held():
        holds.before("before-send.ec2.A", _request("ec2", "A"))
        done.set()

    thread = threading.Thread(target=held)
    thread.start()
    assert not done.wait(0)  # it has not been released: nothing else started yet
    holds.before("before-send.ec2.B", _request("ec2", "B"))
    thread.join()
    assert done.is_set() and holds.outcome == {"h": "event"}


def test_a_hold_that_cannot_be_released_ends_by_its_timeout():
    rules = [
        dict(
            name="h",
            match=dict(service="ec2", operation="A"),
            until=dict(service="ec2", operation="B"),
            timeout=0.05,
        )
    ]
    holds = _child.Holds(rules)
    holds.before("before-send.ec2.A", _request("ec2", "A"))
    assert holds.outcome == {"h": "timeout"}


def test_two_requests_that_meet_wait_for_each_other_and_only_the_first_of_each_is_held():
    rules = [
        dict(
            name="m",
            meet=[
                dict(service="sqs", operation="ListQueues"),
                dict(service="sns", operation="ListTopics"),
            ],
            timeout=30,
        )
    ]
    holds = _child.Holds(rules)
    arrived = []

    def go(service, operation):
        holds.before(f"before-send.{service}.{operation}", _request(service, operation))
        arrived.append(operation)

    threads = [
        threading.Thread(target=go, args=("sqs", "ListQueues")),
        threading.Thread(target=go, args=("sns", "ListTopics")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(arrived) == ["ListQueues", "ListTopics"] and holds.outcome == {
        "m": "event"
    }
    holds.before(
        "before-send.sqs.ListQueues", _request("sqs", "ListQueues")
    )  # a second one passes
    assert holds.outcome == {"m": "event"}


def test_the_account_of_a_request_is_read_from_its_signature():
    holds = _child.Holds([])
    holds.first_key = "FIRST"
    assert (
        holds.describe("before-send.ec2.DescribeVpcs", _request("ec2", "x", "FIRST"))[
            "account"
        ]
        == "first"
    )
    other = holds.describe(
        "before-send.ec2.DescribeVpcs", _request("ec2", "x", "ASIAOTHER")
    )
    assert other["account"] == "other" and other["region"] == "us-east-1"
