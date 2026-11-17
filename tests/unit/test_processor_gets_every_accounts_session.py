"""The generator hands every account's session to the processor (A-71, with
senior F's WO-F3).

The processor analysed the consolidated report's Network and Security sheets
with the first account's session only. With senior F's processor
(``account_sessions=``) it analyses each account with its own session. The
generator passes the argument only when the processor accepts it, so this
branch works with and without fix3/track-f.
"""

from unittest.mock import patch

from inventag.core import cloud_bom_generator as cbg
from inventag.core.cloud_bom_generator import CloudBOMGenerator, MultiAccountConfig
from tests.unit.test_account_time_limit_and_failures import (  # noqa: F401
    CountingInventory,
    _contexts,
    aws,
)

ACCOUNTS = ["111111111111", "222222222222"]


def _run(tmp_path, processor_class):
    generator = CloudBOMGenerator(
        MultiAccountConfig(
            accounts=[object(), object()],
            output_directory=str(tmp_path),
            enable_state_management=False,
        )
    )
    contexts = _contexts(ACCOUNTS)
    for account_id, ctx in contexts.items():
        ctx.session._account = account_id

    def establish():
        generator.account_contexts = dict(contexts)
        return contexts

    generator._establish_account_contexts = establish
    CountingInventory.fail = set()
    with (
        patch.object(cbg, "AWSResourceInventory", CountingInventory),
        patch.object(cbg, "BOMDataProcessor", processor_class),
    ):
        return generator.generate_multi_account_bom(output_formats=["json"])


def test_a_processor_that_takes_account_sessions_gets_every_account(
    aws, tmp_path  # noqa: F811
):
    seen = {}
    real = cbg.BOMDataProcessor

    class Processor(real):
        def __init__(self, config, session=None, account_sessions=None):
            seen["session"] = getattr(session, "_account", None)
            seen["accounts"] = {
                k: getattr(v, "_account", None)
                for k, v in (account_sessions or {}).items()
            }
            super().__init__(config, session=session)

    assert _run(tmp_path, Processor)["success"] is True
    assert seen["session"] == "111111111111"  # the fallback, as before
    assert seen["accounts"] == {a: a for a in ACCOUNTS}


def test_a_processor_without_the_argument_works_as_before(aws, tmp_path):  # noqa: F811
    calls = []
    real = cbg.BOMDataProcessor

    class Processor(real):
        def __init__(self, config, session=None):
            calls.append(getattr(session, "_account", None))
            super().__init__(config, session=session)

    assert _run(tmp_path, Processor)["success"] is True
    assert calls == ["111111111111"]
