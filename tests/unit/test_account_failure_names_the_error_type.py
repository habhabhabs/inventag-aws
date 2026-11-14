"""An account failure whose exception has no message still names its type.

``str(EOFError())`` is "", so v1.2.0 wrote "Context establishment failed: "
with nothing after it (S2 A5: MFA prompt without a terminal). The text now
falls back to the exception's type name. Exit codes are unchanged.
"""

import logging

from inventag.core.cloud_bom_generator import (
    AccountCredentials,
    CloudBOMGenerator,
    MultiAccountConfig,
)


def test_an_empty_exception_message_names_the_exception_type(
    tmp_path, monkeypatch, caplog
):
    caplog.set_level(logging.INFO)
    generator = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[AccountCredentials(account_id="111111111111")],
            output_directory=str(tmp_path),
        )
    )

    def no_session(credentials):
        raise EOFError()

    monkeypatch.setattr(generator, "_create_account_session", no_session)
    contexts = generator._establish_account_contexts()
    errors = contexts["111111111111"].processing_errors
    assert errors == ["Context establishment failed: EOFError"]
    assert any(
        r.getMessage()
        == "Failed to establish context for account 111111111111: EOFError"
        for r in caplog.records
    )
