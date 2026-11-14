"""moto answers requests from several discovery threads without corrupting a response.

Discovery calls AWS from up to 15 threads, and the tests run it against moto in
one process. moto is not built for that: describe_key_pairs
(moto/ec2/responses/key_pairs.py) writes into the class-level dict
EC2BaseResponse.RESPONSE_KEY_PATH_TO_TRANSFORMER, while another thread's EC2
response is being written by moto/core/serialize.py AttributePicker.__call__,
which iterates that dict. The second thread then fails with "dictionary changed
size during iteration" and the scan loses that listing (CI, pull request #43).

This test forces that interleaving instead of waiting for it: the dict pauses
in the middle of one iteration until the other thread has called
describe_key_pairs. It takes about one second when requests are serialised.
"""

import threading

import boto3
from moto import mock_aws
from moto.ec2.responses._base_response import EC2BaseResponse

PUBLIC_KEY_PATH = "DescribeKeyPairsResult.KeyPairs.KeyPairInfo.PublicKey"


def test_a_moto_response_is_not_changed_by_another_thread_while_it_is_written(
    monkeypatch,
):
    paused = threading.Event()
    key_pairs_done = threading.Event()

    class PausingDict(dict):
        """Pauses once, inside an iteration, until describe_key_pairs ran."""

        def items(self):
            for index, item in enumerate(super(PausingDict, self).items()):
                yield item
                if index == 0 and not paused.is_set():
                    paused.set()
                    key_pairs_done.wait(1)

    transformers = {
        path: transform
        for path, transform in EC2BaseResponse.RESPONSE_KEY_PATH_TO_TRANSFORMER.items()
        if path != PUBLIC_KEY_PATH
    }
    monkeypatch.setattr(
        EC2BaseResponse, "RESPONSE_KEY_PATH_TO_TRANSFORMER", PausingDict(transformers)
    )

    errors = []

    def list_security_groups():
        try:
            client = boto3.client("ec2", region_name="us-east-1")
            client.describe_security_groups()
        except Exception as exc:  # the failure under test
            errors.append(exc)

    def list_key_pairs():
        try:
            paused.wait(5)
            client = boto3.client("ec2", region_name="us-east-1")
            client.describe_key_pairs()
        except Exception as exc:
            errors.append(exc)
        finally:
            key_pairs_done.set()

    with mock_aws():
        threads = [
            threading.Thread(target=list_security_groups),
            threading.Thread(target=list_key_pairs),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)

    assert paused.is_set(), "the security group response was never written"
    assert errors == []
