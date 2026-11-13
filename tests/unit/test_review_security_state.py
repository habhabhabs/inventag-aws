"""Release-gate review: snapshots and change reports do not reveal secrets."""

import json

from inventag.state import ChangelogGenerator, DeltaDetector, StateManager

OLD = "planted-old-secret-a1b2c3"
NEW = "planted-new-secret-d4e5f6"


def _fn(secret, output):
    return {
        "service": "Lambda",
        "type": "Function",
        "id": "fn",
        "arn": "arn:aws:lambda:us-east-1:123456789012:function:fn",
        "account_id": "123456789012",
        "region": "us-east-1",
        "tags": {"Owner": "team"},
        "raw_data": {
            "Environment": {"Variables": {"DB_PASSWORD": secret}},
            "Outputs": [{"OutputKey": "K", "OutputValue": output}],
            "Actions": [{"Arguments": {"--x": secret}}],
        },
    }


def test_a_changed_secret_is_not_revealed_by_snapshots_or_the_change_report(tmp_path):
    manager = StateManager(state_dir=str(tmp_path))
    first = manager.save_state([_fn(OLD, OLD)], "123456789012", ["us-east-1"])
    second = manager.save_state([_fn(NEW, NEW)], "123456789012", ["us-east-1"])
    assert first != second
    report = DeltaDetector().detect_changes_by_state_id(manager, first, second)
    changelog = ChangelogGenerator().generate_changelog(report)
    blob = json.dumps(
        [report.__dict__ if hasattr(report, "__dict__") else str(report), changelog],
        default=str,
    )
    for path in tmp_path.rglob("*"):
        if path.is_file():
            blob += path.read_text(errors="ignore")
    assert OLD not in blob and NEW not in blob
    assert "DB_PASSWORD" in blob  # the name stays
