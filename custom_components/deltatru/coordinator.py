"""Polling coordinator for DeltaTru cloud state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DeltaTruAuthError, DeltaTruClient, DeltaTruError
from .const import (
    CONF_REFRESH_TOKEN,
    DOMAIN,
    HEALTH_ATTENTION,
    HEALTH_OFFLINE,
    HEALTH_OK,
    HEALTH_PROBLEM,
    HEALTH_SETUP,
    OFFLINE_AFTER,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SystemState:
    """Everything the entities need for one system."""

    id: str
    name: str
    status: str
    devices: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def last_upload(self) -> datetime | None:
        seen = [dt_util.parse_datetime(d["last_seen_at"]) for d in self.devices if d.get("last_seen_at")]
        seen = [s for s in seen if s is not None]
        return max(seen) if seen else None

    @property
    def latest_alert(self) -> dict[str, Any] | None:
        return self.alerts[0] if self.alerts else None

    def families(self) -> set[str]:
        return {a["family"] for a in self.alerts}

    @property
    def health(self) -> str:
        if self.status in ("installing", "paused", "transferred"):
            return HEALTH_SETUP
        last = self.last_upload
        if last is None or dt_util.utcnow() - last > OFFLINE_AFTER:
            return HEALTH_OFFLINE
        sev = {a.get("severity") for a in self.alerts}
        if "critical" in sev:
            return HEALTH_PROBLEM
        if sev:
            return HEALTH_ATTENTION
        return HEALTH_OK


type DeltaTruConfigEntry = ConfigEntry[DeltaTruCoordinator]


class DeltaTruCoordinator(DataUpdateCoordinator[dict[str, SystemState]]):
    """Fetch systems, devices and active alerts every few minutes."""

    config_entry: DeltaTruConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DeltaTruConfigEntry, client: DeltaTruClient) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client
        self.subscription_active = True

    def _sync_issue(self) -> None:
        """Show a friendly repair notice instead of errors when the subscription lapses."""
        issue_id = f"subscription_{self.config_entry.entry_id}"
        if self.subscription_active:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        else:
            ir.async_create_issue(
                self.hass, DOMAIN, issue_id, is_fixable=False, is_persistent=False,
                severity=ir.IssueSeverity.WARNING, translation_key="subscription_required",
                learn_more_url="https://deltatru.com",
            )

    async def _async_update_data(self) -> dict[str, SystemState]:
        old_token = self.client.refresh_token
        try:
            snap = await self.client.async_snapshot()
        except DeltaTruAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except DeltaTruError as err:
            raise UpdateFailed(str(err)) from err
        finally:
            # Supabase rotates refresh tokens; persist the new one.
            if self.client.refresh_token and self.client.refresh_token != old_token:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={**self.config_entry.data, CONF_REFRESH_TOKEN: self.client.refresh_token},
                )
        self.subscription_active = bool(snap.get("subscription_active"))
        self._sync_issue()
        if not self.subscription_active:
            return {}
        systems, devices, alerts = snap.get("systems") or [], snap.get("devices") or [], snap.get("alerts") or []
        out = {s["id"]: SystemState(s["id"], s.get("name") or "HVAC", s.get("status") or "") for s in systems}
        for d in devices:
            if d.get("system_id") in out:
                out[d["system_id"]].devices.append(d)
        for a in alerts:
            if a.get("system_id") in out:
                out[a["system_id"]].alerts.append(a)
        return out
