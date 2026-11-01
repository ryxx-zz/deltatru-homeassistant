"""Real-world ESPHome layouts: new unique_id formats, friendly device names, two systems, sparse COND boards."""

from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.deltatru.discovery import assign, find_esphome_devices, find_monitors

from .conftest import SYS
from .test_init import setup

SYS2 = "99999999-2222-3333-4444-555555555555"


def add_board(hass, esp, mac, name, entities, uid_fmt):
    dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=esp.entry_id, connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        name=name, manufacturer="Espressif", model="esp32-c3-devkitm-1", suggested_area="ACMonitoring",
    )
    reg = er.async_get(hass)
    slug = name.lower().replace(" ", "_").replace("-", "_")
    for domain, ent_name in entities:
        oid = ent_name.lower().replace(" ", "_").replace("-", "_")
        uid = {"v3": f"{mac}/0/{domain}/{ent_name}", "v2": f"{mac}-{domain}-{ent_name}",
               "v1": f"{mac}-{domain}-{oid}"}[uid_fmt]
        reg.async_get_or_create("sensor" if domain == "text_sensor" else domain, "esphome", uid,
                                suggested_object_id=f"{slug}_{oid}", original_name=ent_name,
                                device_id=dev.id, config_entry=esp)
    return dev.id


AHU = [("sensor", "Return air"), ("sensor", "Supply air"), ("sensor", "Delta T"), ("sensor", "Blower amps"),
       ("binary_sensor", "Problem"), ("text_sensor", "Status"), ("text_sensor", "HVAC mode"), ("sensor", "Wi-Fi signal")]


def richards_ha(hass):
    esp = MockConfigEntry(domain="esphome", data={})
    esp.add_to_hass(hass)
    return {
        "AHU 1": add_board(hass, esp, "aa:00:00:00:00:01", "AHU 1", AHU, "v3"),
        "AHU-2": add_board(hass, esp, "aa:00:00:00:00:02", "AHU-2", AHU, "v2"),
        "COND 1": add_board(hass, esp, "aa:00:00:00:00:03", "COND 1",
                            [("sensor", "Outdoor temp"), ("sensor", "Compressor amps"), ("sensor", "Wi-Fi signal")], "v3"),
        "COND 2": add_board(hass, esp, "aa:00:00:00:00:04", "COND 2",
                            [("sensor", "Wi-Fi signal"), ("sensor", "Uptime")], "v3"),
    }


async def test_detects_new_unique_id_formats(hass):
    ids = richards_ha(hass)
    mons = {m.name: m for m in find_monitors(hass)}
    assert set(mons) == {"AHU 1", "AHU-2", "COND 1"}  # COND 2 has no DeltaTru sensors yet
    assert mons["AHU 1"].role == "ahu" and mons["COND 1"].role == "cond"
    assert mons["AHU 1"].entities["delta_t"] == "sensor.ahu_1_delta_t"
    assert mons["AHU-2"].entities["problem"].startswith("binary_sensor.")
    # every ESPHome device is listed for manual mapping, including COND 2
    assert {n for _, n in find_esphome_devices(hass)} == {"AHU 1", "AHU-2", "COND 1", "COND 2"}
    # a manually mapped unknown board is included
    assert "COND 2" in {m.name for m in find_monitors(hass, {ids["COND 2"]})}


async def test_two_systems_manual_mapping(hass):
    ids = richards_ha(hass)
    groups = assign(find_monitors(hass, {ids["COND 2"]}), [SYS, SYS2],
                    {ids["AHU 1"]: SYS, ids["COND 1"]: SYS, ids["AHU-2"]: SYS2, ids["COND 2"]: SYS2})
    assert sorted(m.name for m in groups[SYS]) == ["AHU 1", "COND 1"]
    assert sorted(m.name for m in groups[SYS2]) == ["AHU-2", "COND 2"]


async def test_options_lists_all_esphome_devices(hass, mock_cloud):
    mock_cloud["data"]["systems"].append({"id": SYS2, "name": "Kitchen heat pump", "status": "monitoring"})
    ids = richards_ha(hass)
    entry = await setup(hass)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    keys = {str(k) for k in r["data_schema"].schema}
    assert {"Monitor: AHU 1", "Monitor: AHU-2", "Monitor: COND 1", "ESPHome device: COND 2"} <= keys
    assert "none" not in r["description_placeholders"]["monitors"]
    r = await hass.config_entries.options.async_configure(r["flow_id"], {
        "dashboard": True, "notify_problem": True, "Monitor: AHU 1": SYS, "ESPHome device: COND 2": SYS2})
    await hass.async_block_till_done()
    assert entry.options["device_map"] == {ids["AHU 1"]: SYS, ids["COND 2"]: SYS2}
