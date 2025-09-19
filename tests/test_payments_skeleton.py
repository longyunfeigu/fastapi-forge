import os
import pytest


@pytest.mark.asyncio
async def test_webhook_route_registered():
    # Basic import test to ensure router loads
    from main import app
    routes = {r.path for r in app.routes}
    assert "/api/v1/payments/webhooks/{provider}" in routes

