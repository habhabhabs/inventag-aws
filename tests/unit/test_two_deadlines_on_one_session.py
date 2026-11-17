"""Two account deadlines on one session keep their own hooks (A-44, deadline
part; senior D's D4 note).

A library caller can give two accounts the same session object. Both
deadlines registered their botocore hook under one fixed id: botocore keeps
the first registration of an id, so the second deadline was never checked,
and detaching either removed the only hook. No network: a ``before-send``
responder answers every call.
"""

import boto3
import pytest
from botocore.awsrequest import AWSResponse

from inventag.core.cloud_bom_generator import AccountTimeoutError, _AccountDeadline

EMPTY = b"<DescribeVpcsResponse><vpcSet/></DescribeVpcsResponse>"


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class RawBody:
    def __init__(self, data):
        self._data = data

    def stream(self, **kwargs):
        yield self._data


def _session():
    session = boto3.Session(
        aws_access_key_id="AKIAFAKEFAKEFAKEFAKE",
        aws_secret_access_key="fake-secret-for-tests-only",
        region_name="us-east-1",
    )
    session.events.register_last(
        "before-send.ec2",
        lambda request, **kw: AWSResponse(request.url, 200, {}, RawBody(EMPTY)),
    )
    return session


def test_the_second_deadline_on_a_shared_session_is_checked():
    clock = FakeClock()
    session = _session()
    first = _AccountDeadline("111111111111", 600, clock=clock)
    second = _AccountDeadline("222222222222", 60, clock=clock)
    for deadline in (first, second):
        deadline.start()
        deadline.attach(session)
    clock.now += 61  # past the second limit only
    with pytest.raises(AccountTimeoutError, match="222222222222"):
        session.client("ec2").describe_vpcs()


def test_detaching_one_deadline_keeps_the_other():
    clock = FakeClock()
    session = _session()
    first = _AccountDeadline("111111111111", 60, clock=clock)
    second = _AccountDeadline("222222222222", 60, clock=clock)
    for deadline in (first, second):
        deadline.start()
        deadline.attach(session)
    first.detach(session)
    clock.now += 61
    with pytest.raises(AccountTimeoutError, match="222222222222"):
        session.client("ec2").describe_vpcs()
    second.detach(session)
    session.client("ec2").describe_vpcs()  # no hook left
