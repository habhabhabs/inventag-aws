"""After a report format failed, the log says that nothing was uploaded (A-12).

v1.2.0 skipped the S3 upload after a failed format without a word. The
line comes from ``s3_upload.skipped_upload_message`` (senior G).
"""

import logging
from types import SimpleNamespace
from unittest.mock import patch

from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig

WANTED = (
    "Nothing was uploaded to s3://reports-bucket/inventag/nightly/ because a "
    "report format failed. The report files that were written are in the "
    "output folder."
)


def _upload_config():
    return SimpleNamespace(
        bucket_name="reports-bucket", key_prefix="/inventag/nightly/"
    )


def test_a_failed_format_says_nothing_was_uploaded(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    generator = CloudBOMGenerator(MultiAccountConfig(output_directory=str(tmp_path)))
    failed = {
        "success": False,
        "error": "Could not write: word: boom",
        "bom_generation": {"generated_files": [str(tmp_path / "a.xlsx")]},
    }
    with (
        patch.object(
            CloudBOMGenerator, "generate_multi_account_bom", return_value=failed
        ),
        patch.object(CloudBOMGenerator, "upload_reports_to_s3") as upload,
    ):
        result = generator.generate_comprehensive_bom(
            output_formats=["excel", "word"], s3_upload_config=_upload_config()
        )
    upload.assert_not_called()
    assert result["success"] is False
    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors == [WANTED]


def test_a_run_that_failed_before_the_reports_says_nothing_about_uploads(
    tmp_path, caplog
):
    caplog.set_level(logging.INFO)
    generator = CloudBOMGenerator(MultiAccountConfig(output_directory=str(tmp_path)))
    with patch.object(
        CloudBOMGenerator,
        "generate_multi_account_bom",
        return_value={"success": False, "error": "all accounts failed"},
    ):
        generator.generate_comprehensive_bom(s3_upload_config=_upload_config())
    assert not [r for r in caplog.records if "uploaded" in r.getMessage()]
