"""Every run note passes ``security.redaction.redact`` (A-69).

A run note can carry an error text from AWS or from the credential code (a
failed account's reason, a state error). The log lines are redacted by the
log filter, but the notes also go into the report file and into
``results["run_notes"]``, which had no such filter. Account IDs and ARNs are
not secrets and stay as they are.
"""

import boto3

from inventag.core.cloud_bom_generator import (
    AccountContext,
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)
from inventag.security.redaction import (
    REDACTED,
    clear_registered_secrets,
    register_secret,
)

SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYPLANTEDKEY1"
ARN = "arn:aws:iam::222222222222:role/InvenTagRole"


def test_a_note_built_from_an_error_text_shows_the_mask(tmp_path):
    register_secret(SECRET)
    try:
        generator = CloudBOMGenerator(
            MultiAccountConfig(accounts=[], output_directory=str(tmp_path))
        )
        generator.account_contexts["222222222222"] = AccountContext(
            credentials=AccountCredentials(
                account_id="222222222222", account_name="prod"
            ),
            session=None,
            caller_identity={},
            processing_errors=[
                f"Role assumption failed for {ARN}: "
                f"aws_secret_access_key='{SECRET}' "
                "{'SessionToken': 'FwoGZXIvYXdzEPLANTEDTOKEN'}"
            ],
        )
        generator.account_contexts["111111111111"] = AccountContext(
            credentials=AccountCredentials(account_id="111111111111"),
            session=boto3.Session(region_name="us-east-1"),
            caller_identity={"Account": "111111111111"},
        )
        notes = generator._run_notes()
    finally:
        clear_registered_secrets()
    text = "\n".join(notes)
    assert SECRET not in text and "PLANTEDTOKEN" not in text, text
    assert REDACTED in text
    assert ARN in text and "222222222222 (prod)" in text
