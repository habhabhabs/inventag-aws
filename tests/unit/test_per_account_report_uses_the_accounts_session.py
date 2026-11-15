"""With ``--per-account-reports`` each account's report reads with that
account's own session (A-58, generator side).

v1.2.1 gave every per-account converter the first account's session, so the
Network and Security sheets of account B could be read from account A.
Senior F's converter (fix2/track-f) uses the session it is given; this test
checks only what the generator passes, so it holds with or without that
branch.
"""

from unittest.mock import patch

from inventag.core import cloud_bom_generator as cbg
from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
from tests.unit.test_account_time_limit_and_failures import (  # noqa: F401
    CountingInventory,
    _contexts,
    aws,
)


def test_each_per_account_converter_gets_its_accounts_session(
    aws, tmp_path, monkeypatch  # noqa: F811
):
    generator = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[object(), object()],
            output_directory=str(tmp_path),
            enable_state_management=False,
            generate_per_account_reports=True,
        )
    )
    contexts = _contexts(["111111111111", "222222222222"])
    for account_id, ctx in contexts.items():
        ctx.session._account = account_id

    def establish():
        generator.account_contexts = dict(contexts)
        return contexts

    generator._establish_account_contexts = establish
    sessions = []
    original = cbg.BOMConverter.__init__

    def spy(self, *args, **kwargs):
        sessions.append(getattr(kwargs.get("session"), "_account", None))
        original(self, *args, **kwargs)

    monkeypatch.setattr(cbg.BOMConverter, "__init__", spy)
    CountingInventory.fail = set()
    with patch.object(cbg, "AWSResourceInventory", CountingInventory):
        result = generator.generate_multi_account_bom(output_formats=["json"])
    assert result["success"] is True
    # The first converter is the consolidated one; then one per account.
    assert sessions[1:] == ["111111111111", "222222222222"], sessions
