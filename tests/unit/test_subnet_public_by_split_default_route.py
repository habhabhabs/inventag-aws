"""A subnet is public when its route table sends the whole address space to an internet gateway.

``0.0.0.0/1`` plus ``128.0.0.0/1`` (and ``::/1`` plus ``8000::/1``) together are a default route.
Half of the space alone is not.
"""

import pytest

from inventag.discovery.network_analyzer import NetworkAnalyzer

IGW = "igw-0123"


def _route(destination, gateway=IGW, state="active", key="DestinationCidrBlock"):
    return {key: destination, "GatewayId": gateway, "State": state}


V6 = "DestinationIpv6CidrBlock"


@pytest.mark.parametrize(
    "routes,public",
    [
        ([_route("0.0.0.0/0")], True),  # as before
        ([_route("::/0", key=V6)], True),  # as before
        ([_route("0.0.0.0/1"), _route("128.0.0.0/1")], True),
        ([_route("::/1", key=V6), _route("8000::/1", key=V6)], True),
        ([_route("128.0.0.0/1"), _route("0.0.0.0/1")], True),
        ([_route("0.0.0.0/1")], False),  # half of the space only
        ([_route("0.0.0.0/1"), _route("128.0.0.0/2")], False),
        ([_route("0.0.0.0/1"), _route("128.0.0.0/1", gateway="nat-1")], False),
        ([_route("0.0.0.0/1"), _route("128.0.0.0/1", state="blackhole")], False),
        ([_route("0.0.0.0/1", key=V6), _route("128.0.0.0/1")], False),
        ([_route("10.0.0.0/8")], False),
    ],
)
def test_a_route_table_with_the_whole_address_space_to_an_igw_is_public(routes, public):
    assert NetworkAnalyzer._has_internet_route({"Routes": routes}) is public
