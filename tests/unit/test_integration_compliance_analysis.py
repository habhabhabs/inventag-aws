"""``CloudBOMGenerator`` with ``compliance_policies`` (library path) works.

It used to call a constructor keyword and a method that do not exist, so the
result was always ``{"success": False}``.
"""

from unittest.mock import MagicMock

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)


def test_compliance_analysis_uses_the_checker_api(tmp_path):
    generator = CloudBOMGenerator(
        MultiAccountConfig(accounts=[], output_directory=str(tmp_path))
    )
    session = MagicMock()
    generator.account_contexts["111111111111"] = AccountContext(
        credentials=AccountCredentials(account_id="111111111111"),
        session=session,
        caller_identity={},
        accessible_regions=["eu-west-1"],
    )
    resources = [
        {
            "service": "S3",
            "type": "Bucket",
            "id": "a",
            "arn": "arn:aws:s3:::a",
            "tags": {"Owner": "x"},
        },
        {
            "service": "S3",
            "type": "Bucket",
            "id": "b",
            "arn": "arn:aws:s3:::b",
            "tags": {"Team": "y"},
        },
        {
            "service": "S3",
            "type": "Bucket",
            "id": "c",
            "arn": "arn:aws:s3:::c",
            "tags": {},
        },
    ]
    result = generator._run_compliance_analysis(resources, {"required_tags": ["Owner"]})
    assert result.get("success") is not False, result
    summary = result["summary"]
    assert summary["compliant_resources"] == 1
    assert summary["non_compliant_resources"] == 1
    assert summary["untagged_resources"] == 1
    assert result["multi_account_analysis"]["total_accounts"] == 1
    # No AWS call: the regions came from the account context.
    session.client.assert_not_called()
