"""A5: Ctrl-C and SIGTERM, today's message and exit status, pinned (v1.3.0 semantics).

Plan 2.6: "the stop event is set first; then today's path runs unchanged (same
message, same exit status; WO-A5 pins both before any change)". These rows are
the pin. They run a real process (``tests/concurrency/_child.py``, moto inside),
hold ONE AWS request of a chosen phase until the run ends, wait for that request
to start (a blocking read of a FIFO, no sleep), send the signal and look at what
the process did.

Today (v1.3.0, measured when these rows were written):

    Ctrl-C   exit status 1, one warning "Stopped by the user (Ctrl-C). No report
             was written.", no traceback, no file in the output folder
    SIGTERM  killed by the signal (return code -15), one warning "Terminated
             (SIGTERM). No report was written.", no file in the output folder

The signal reaches the process while it is (a) listing, (b) reading details,
and, from work order A2 on, (c) while a request waits for a limiter slot. Row (c)
is expected to fail until ``--concurrency`` exists; its reason is in the mark.

Slow rows (a real process, 6 to 8 s each): ``pytest -m slow``.
"""

import signal

import pytest

from tests.concurrency import harness

pytestmark = pytest.mark.slow

LISTING = "ec2:DescribeVpcs"
DETAIL = "lambda:GetFunctionConfiguration"

TODAY = {
    signal.SIGINT: (1, "Stopped by the user (Ctrl-C). No report was written."),
    signal.SIGTERM: (-15, "Terminated (SIGTERM). No report was written."),
}


def _assert_as_today(scan, sig):
    code, message = TODAY[sig]
    assert scan.gate_started, (
        "the held request never started; the signal was not sent\n" + scan.text[-1500:]
    )
    assert (
        scan.code == code
    ), f"exit status {scan.code!r}, wanted {code}\n{scan.text[-1500:]}"
    assert (
        message in scan.text
    ), f"the message {message!r} is missing\n{scan.text[-1500:]}"
    assert "Traceback" not in scan.text
    written = [p.name for p in scan.out.rglob("*") if p.is_file()]
    assert written == [], f"a signal left files behind: {written}"


@pytest.mark.parametrize(
    "sig", [signal.SIGINT, signal.SIGTERM], ids=["ctrl-c", "sigterm"]
)
@pytest.mark.parametrize(
    "phase,gate", [("listing", LISTING), ("detail", DETAIL)], ids=["listing", "detail"]
)
def test_signal_during_a_phase_gives_todays_message_and_status(
    tmp_path, phase, gate, sig
):
    scan = harness.run_scan_with_signal(tmp_path, gate, sig=sig)
    _assert_as_today(scan, sig)


needs_a2 = pytest.mark.xfail(
    not harness.concurrency_flag_exists(),
    strict=True,
    reason=(
        "A2: --concurrency is not in the CLI yet, so no request can wait for a limiter "
        "slot; the row starts to run for real when the flag exists"
    ),
)


@needs_a2
@pytest.mark.parametrize(
    "sig", [signal.SIGINT, signal.SIGTERM], ids=["ctrl-c", "sigterm"]
)
def test_signal_while_requests_wait_for_a_slot_gives_todays_message_and_status(
    tmp_path, sig
):
    """``--concurrency 1``: the held request owns the only slot, every other request
    of the run waits for one. The signal ends the waiting at once (plan 2.3, 2.6):
    same message and status as above, and the process is gone within 30 s."""
    scan = harness.run_scan_with_signal(
        tmp_path, LISTING, sig=sig, args=["--concurrency", "1"]
    )
    _assert_as_today(scan, sig)
    assert (
        scan.seconds_after_signal is not None and scan.seconds_after_signal < 30
    ), f"the process took {scan.seconds_after_signal} s to end after the signal"
