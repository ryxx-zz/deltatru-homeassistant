"""End-to-end setup: entities, device linking, dashboard, notifications."""

from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from homeassistant.util import dt as dt_util
from datetime import timedelta

from custom_components.deltatru.const import DOMAIN, SCAN_INTERVAL
from custom_components.deltatru.dashboard import build_dashboard

from .conftest import SYS, cloud

MAC = "aa:bb:cc:dd:ee:01"


def add_esphome_ahu(hass: HomeAssistant, system_id: str | None = None) -> str:
    esp = MockConfigEntry(domain="esphome", data={})
    esp.add_to_hass(hass)
    dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=esp.entry_id, connections={(dr.CONNECTION_NETWORK_MAC, MAC)},
        name="ahu-1", manufacturer="Espressif", model="esp32-c3-devkitm-1",
    )
    ent_reg = er.async_get(hass)
    for domain, oid in [("sensor", "delta_t"), ("sensor", "return_air"), ("sensor", "supply_air"),
                        ("sensor", "blower_amps"), ("binary_sensor", "problem"),
                        ("text_sensor", "status"), ("text", "system_id")]:
        ent_reg.async_get_or_create(domain if domain != "text_sensor" else "sensor", "esphome",
                                    f"{MAC}-{domain}-{oid}", suggested_object_id=f"ahu_1_{oid}",
                                    device_id=dev.id, config_entry=esp)
    if system_id:
        hass.states.async_set("text.ahu_1_system_id", system_id)
    return dev.id


async def setup(hass):
    await async_setup_component(hass, "lovelace", {})
    entry = MockConfigEntry(domain=DOMAIN, unique_id="user-1", data={
        "email": "a@b.c", "supabase_url": "https://x.supabase.co", "anon_key": "k", "refresh_token": "rt"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_entities_and_link(hass, mock_cloud):
    dev_id = add_esphome_ahu(hass)
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.deltatru_kitchen_system_health").state == "ok"
    assert hass.states.get("sensor.deltatru_kitchen_latest_alert").state == "No active alerts"
    assert hass.states.get("binary_sensor.deltatru_kitchen_airflow_alert").state == "off"
    assert hass.states.get("sensor.deltatru_kitchen_last_upload") is not None
    assert hass.states.get("binary_sensor.deltatru_kitchen_connected") is not None
    parent = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, SYS), entry.entry_id)
    assert parent.name == "DeltaTru Kitchen"
    assert dr.async_get(hass).async_get(dev_id).via_device_id == parent.id


async def test_alert_updates(hass, mock_cloud):
    await setup(hass)
    mock_cloud["data"] = cloud(alerts=[{"system_id": SYS, "family": "airflow", "severity": "critical",
                                        "status": "open", "title": "Low airflow", "rule_id": "R2"}])
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.deltatru_kitchen_airflow_alert").state == "on"
    assert hass.states.get("binary_sensor.deltatru_kitchen_capacity_alert").state == "off"
    assert hass.states.get("binary_sensor.deltatru_kitchen_active_alert").state == "on"
    assert hass.states.get("sensor.deltatru_kitchen_latest_alert").state == "Low airflow"
    assert hass.states.get("sensor.deltatru_kitchen_system_health").state == "problem"


async def test_offline(hass, mock_cloud):
    mock_cloud["data"] = cloud(seen_minutes_ago=90)
    await setup(hass)
    assert hass.states.get("sensor.deltatru_kitchen_system_health").state == "offline"


async def test_dashboard(hass, mock_cloud):
    add_esphome_ahu(hass, system_id=SYS)
    await setup(hass)
    dash = hass.data[LOVELACE_DATA].dashboards["deltatru"]
    cfg = await dash.async_load(False)
    assert cfg == build_dashboard(hass)
    view = cfg["views"][0]
    assert view["title"] == "Kitchen"
    types = [c["type"] for c in view["cards"]]
    assert types[:1] == ["conditional"] and "gauge" in types and "history-graph" in types
    gauge = next(c for c in view["cards"] if c["type"] == "gauge")
    assert gauge["entity"] == "sensor.ahu_1_delta_t"
    tiles = [t["entity"] for t in next(c for c in view["cards"] if c["type"] == "grid")["cards"]]
    assert "sensor.deltatru_kitchen_system_health" in tiles and "binary_sensor.ahu_1_problem" in tiles
    assert "deltatru" in hass.data["frontend_panels"]


async def test_unload_removes_dashboard(hass, mock_cloud):
    entry = await setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert "deltatru" not in hass.data[LOVELACE_DATA].dashboards


async def test_problem_notification(hass, mock_cloud):
    add_esphome_ahu(hass)
    await setup(hass)
    hass.states.async_set("sensor.ahu_1_status", "Low airflow - check filter")
    hass.states.async_set("binary_sensor.ahu_1_problem", "on")
    await hass.async_block_till_done()
    notes = hass.data["persistent_notification"]
    nid = "deltatru_binary_sensor.ahu_1_problem"
    assert nid in notes and "Low airflow" in notes[nid]["message"]
    hass.states.async_set("binary_sensor.ahu_1_problem", "off")
    await hass.async_block_till_done()
    assert nid not in hass.data["persistent_notification"]


async def test_options_flow_maps_device(hass, mock_cloud):
    dev_id = add_esphome_ahu(hass)
    entry = await setup(hass)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["step_id"] == "init"
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"dashboard": False, "notify_problem": True, "Monitor: ahu-1": SYS})
    await hass.async_block_till_done()
    assert entry.options["device_map"] == {dev_id: SYS}
    assert "deltatru" not in hass.data[LOVELACE_DATA].dashboards


async def test_reauth_on_auth_failure(hass, mock_cloud):
    from unittest.mock import patch
    from custom_components.deltatru.api import DeltaTruAuthError

    async def boom(self):
        raise DeltaTruAuthError("expired")

    with patch("custom_components.deltatru.api.DeltaTruClient.async_snapshot", boom):
        await async_setup_component(hass, "lovelace", {})
        entry = MockConfigEntry(domain=DOMAIN, unique_id="user-1", data={
            "email": "a@b.c", "supabase_url": "u", "anon_key": "k", "refresh_token": "rt"})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert flows and flows[0]["context"]["source"] == "reauth"
    r = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {"email": "a@b.c", "password": "pw"})
    assert r["reason"] == "reauth_successful"


async def test_subscription_inactive_is_graceful(hass, mock_cloud):
    from homeassistant.helpers import issue_registry as ir
    dev_id = add_esphome_ahu(hass)
    mock_cloud["active"] = False
    entry = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.deltatru_kitchen_system_health") is None
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"subscription_{entry.entry_id}")
    assert issue and issue.translation_key == "subscription_required"
    cfg = build_dashboard(hass)
    assert "need an active subscription" in cfg["views"][0]["cards"][0]["content"]
    assert dr.async_get(hass).async_get(dev_id).via_device_id is None
    # reactivated -> entities appear and the notice clears
    mock_cloud["active"] = True
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.deltatru_kitchen_system_health").state == "ok"
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"subscription_{entry.entry_id}") is None
