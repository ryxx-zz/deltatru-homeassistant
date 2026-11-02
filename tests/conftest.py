"""Fixtures."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.util import dt as dt_util

SYS = "11111111-2222-3333-4444-555555555555"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def cloud(alerts=None, seen_minutes_ago=2):
    seen = (dt_util.utcnow() - timedelta(minutes=seen_minutes_ago)).isoformat()
    return {
        "systems": [{"id": SYS, "name": "Kitchen", "status": "monitoring"}],
        "devices": [
            {"device_id": "hv1-a", "role": "ahu", "system_id": SYS, "last_seen_at": seen},
            {"device_id": "hv1-c", "role": "cond", "system_id": SYS, "last_seen_at": seen},
        ],
        "alerts": alerts or [],
    }


@pytest.fixture
def mock_cloud():
    state = {"data": cloud()}

    async def sign_in(self, email, password):
        if password != "pw":
            from custom_components.deltatru.api import DeltaTruAuthError
            raise DeltaTruAuthError("bad")
        self.refresh_token, self.user_id = "rt", "user-1"

    async def snapshot(self):
        if not state.get("active", True):
            return {"subscription_active": False}
        return {"subscription_active": True, **state["data"]}

    base = "custom_components.deltatru.api.DeltaTruClient."
    with patch(base + "async_sign_in", sign_in), patch(base + "async_snapshot", snapshot):
        yield state
