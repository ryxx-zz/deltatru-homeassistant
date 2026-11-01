"""DeltaTru HVAC monitor integration."""

from __future__ import annotations

import logging

from homeassistant.components import persistent_notification
from homeassistant.const import Platform
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event

from .api import DeltaTruClient
from .const import (
    CONF_ANON_KEY,
    CONF_DASHBOARD,
    CONF_DEVICE_MAP,
    CONF_NOTIFY,
    CONF_REFRESH_TOKEN,
    CONF_SUPABASE_URL,
    DOMAIN,
)
from .coordinator import DeltaTruConfigEntry, DeltaTruCoordinator
from .dashboard import async_register_dashboard, async_unregister_dashboard
from .discovery import assign, find_monitors
from .entity import system_device_info

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: DeltaTruConfigEntry) -> bool:
    client = DeltaTruClient(
        async_get_clientsession(hass),
        entry.data[CONF_SUPABASE_URL],
        entry.data[CONF_ANON_KEY],
        entry.data[CONF_REFRESH_TOKEN],
    )
    coordinator = DeltaTruCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _link(*_: object) -> None:
        async_link_devices(hass, entry)

    _link()
    entry.async_on_unload(coordinator.async_add_listener(_link))
    if entry.options.get(CONF_DASHBOARD, True):
        async_register_dashboard(hass)
    if entry.options.get(CONF_NOTIFY, True):
        _watch_problem(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DeltaTruConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok and len(hass.config_entries.async_loaded_entries(DOMAIN)) <= 1:
        async_unregister_dashboard(hass)
    return ok


@callback
def async_link_devices(hass: HomeAssistant, entry: DeltaTruConfigEntry) -> None:
    """Hang each ESPHome monitor under its 'DeltaTru <system>' device."""
    data = entry.runtime_data.data or {}
    dev_reg = dr.async_get(hass)
    groups = assign(find_monitors(hass), list(data), entry.options.get(CONF_DEVICE_MAP, {}))
    for sid, monitors in groups.items():
        parent = dev_reg.async_get_or_create(config_entry_id=entry.entry_id, **system_device_info(data[sid]))
        for mon in monitors:
            dev = dev_reg.async_get(mon.device_id)
            if dev and dev.via_device_id != parent.id:
                dev_reg.async_update_device(mon.device_id, via_device_id=parent.id)


@callback
def _watch_problem(hass: HomeAssistant, entry: DeltaTruConfigEntry) -> None:
    """Persistent notification while any monitor's Problem sensor is on."""
    monitors = [m for m in find_monitors(hass) if "problem" in m.entities]
    if not monitors:
        return
    names = {m.entities["problem"]: m for m in monitors}

    @callback
    def _changed(event: Event[EventStateChangedData]) -> None:
        eid = event.data["entity_id"]
        new = event.data["new_state"]
        nid = f"{DOMAIN}_{eid}"
        if new is None or new.state != "on":
            persistent_notification.async_dismiss(hass, nid)
            return
        old = event.data["old_state"]
        if old is not None and old.state == "on":
            return
        mon = names[eid]
        status = hass.states.get(mon.entities.get("status", ""))
        detail = status.state if status and status.state not in ("unknown", "unavailable") else "Check the DeltaTru dashboard."
        persistent_notification.async_create(
            hass, f"{mon.name}: {detail}", title="DeltaTru: HVAC problem", notification_id=nid
        )

    entry.async_on_unload(async_track_state_change_event(hass, list(names), _changed))
