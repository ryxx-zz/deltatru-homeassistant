"""Config flow tests."""

from ipaddress import ip_address

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.deltatru.const import DOMAIN

USER = {"email": "a@b.c", "password": "pw"}


async def test_user_flow(hass, mock_cloud):
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert r["type"] is FlowResultType.FORM
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {**USER, "password": "nope"})
    assert r["errors"] == {"base": "invalid_auth"}
    r = await hass.config_entries.flow.async_configure(r["flow_id"], USER)
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"]["refresh_token"] == "rt" and "password" not in r["data"]
    assert r["result"].unique_id == "user-1"


async def test_zeroconf(hass, mock_cloud):
    info = ZeroconfServiceInfo(ip_address=ip_address("192.168.1.9"), ip_addresses=[ip_address("192.168.1.9")],
                               hostname="ahu-1.local.", name="ahu-1._esphomelib._tcp.local.", port=6053,
                               type="_esphomelib._tcp.local.",
                               properties={"project_name": "elmer.hvac-monitor-ahu", "friendly_name": "Kitchen AHU"})
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info)
    assert r["step_id"] == "zeroconf_confirm"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
    assert r["step_id"] == "user"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], USER)
    assert r["type"] is FlowResultType.CREATE_ENTRY
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_ZEROCONF}, data=info)
    assert r["type"] is FlowResultType.ABORT
