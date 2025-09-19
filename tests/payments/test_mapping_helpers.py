from infrastructure.external.payments.base import BasePaymentClient


class _MapClient(BasePaymentClient):
    provider = "stripe"


def test_provider_status_mapping():
    c = _MapClient()
    assert c._map_status("succeeded") == "succeeded"
    assert c._map_status("processing") == "pending"
    assert c._map_status("requires_action") == "pending"

