"""Auto-generated, read-only "DeltaTru" Lovelace dashboard.

The config is rebuilt from the entity registry on every load, so it follows
renamed entities and newly linked monitors without any stored YAML.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components import frontend
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.dashboard import LovelaceConfig
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.json import json_bytes, json_fragment

from .const import ALERT_FAMILIES, DASHBOARD_URL, DOMAIN
from .discovery import Monitor, assign, find_monitors

AHU_TILES = ("hvac_mode", "status", "problem", "return_air", "supply_air", "blower_amps")
COND_TILES = ("outdoor_air", "compressor_amps", "compressor_running")
SUBSCRIPTION_MSG = (
    "## DeltaTru cloud features need an active subscription\n"
    "Your ESPHome monitor entities keep working locally. Alerts, system health and this dashboard "
    "come back automatically once your subscription is active at [deltatru.com](https://deltatru.com)."
)
HISTORY = ("delta_t", "return_air", "supply_air", "blower_amps", "compressor_amps", "outdoor_air")


def _own(ent_reg: er.EntityRegistry, platform: str, sid: str, key: str) -> str | None:
    return ent_reg.async_get_entity_id(platform, DOMAIN, f"{sid}_{key}")


def build_dashboard(hass: HomeAssistant) -> dict[str, Any]:
    """Build the Lovelace config for every DeltaTru system."""
    ent_reg = er.async_get(hass)
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    views: list[dict[str, Any]] = []
    for entry in entries:
        if not entry.runtime_data.subscription_active:
            views.append({"title": "DeltaTru", "cards": [{"type": "markdown", "content": SUBSCRIPTION_MSG}]})
            continue
        data = entry.runtime_data.data or {}
        groups = assign(find_monitors(hass, set(entry.options.get("device_map", {}))), list(data), entry.options.get("device_map", {}))
        for sid, system in data.items():
            views.append(_view(ent_reg, sid, system.name, groups.get(sid, [])))
    if not views:
        views = [{"title": "DeltaTru", "cards": [{"type": "markdown", "content": "No DeltaTru systems yet."}]}]
    return {"title": "DeltaTru", "views": views}


def _pick(monitors: list[Monitor], role: str, keys: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for key in keys:
        for m in monitors:
            if m.role == role and key in m.entities and m.entities[key] not in out:
                out.append(m.entities[key])
    return out


def _view(ent_reg: er.EntityRegistry, sid: str, name: str, monitors: list[Monitor]) -> dict[str, Any]:
    health = _own(ent_reg, "sensor", sid, "health")
    latest = _own(ent_reg, "sensor", sid, "latest_alert")
    connected = _own(ent_reg, "binary_sensor", sid, "connected")
    problem = _own(ent_reg, "binary_sensor", sid, "problem")
    cards: list[dict[str, Any]] = []
    if problem and latest:
        cards.append({
            "type": "conditional",
            "conditions": [{"condition": "state", "entity": problem, "state": "on"}],
            "card": {"type": "markdown",
                     "content": f"## ⚠️ {{{{ states('{latest}') }}}}\n"
                                f"Severity: {{{{ state_attr('{latest}', 'severity') }}}} · "
                                f"since {{{{ state_attr('{latest}', 'first_seen') }}}}"},
        })
    tiles = [e for e in (health, connected) if e]
    tiles += _pick(monitors, "ahu", AHU_TILES) + _pick(monitors, "cond", COND_TILES)
    if tiles:
        cards.append({"type": "grid", "columns": 3, "square": False,
                      "cards": [{"type": "tile", "entity": e} for e in tiles]})
    for dt in _pick(monitors, "ahu", ("delta_t",)):
        cards.append({"type": "gauge", "entity": dt, "name": "Delta T", "min": 0, "max": 30,
                      "needle": True, "severity": {"red": 0, "yellow": 10, "green": 15}})
    hist = _pick(monitors, "ahu", HISTORY) + _pick(monitors, "cond", HISTORY)
    if hist:
        cards.append({"type": "history-graph", "title": "Last 24 h", "hours_to_show": 24, "entities": hist})
    fams = [e for f in ALERT_FAMILIES if (e := _own(ent_reg, "binary_sensor", sid, f"alert_{f}"))]
    if fams:
        cards.append({"type": "entities", "title": "Alert checks", "state_color": True, "entities": fams})
    if not monitors:
        cards.append({"type": "markdown", "content": "No ESPHome monitors linked to this system yet. "
                      "Add them via the ESPHome integration, or pick them in DeltaTru → Configure."})
    return {"title": name, "path": sid[:8], "icon": "mdi:hvac", "cards": cards}


class DeltaTruDashboard(LovelaceConfig):
    """Lovelace config source that is generated, never stored."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass, DASHBOARD_URL, {"mode": "yaml", "title": "DeltaTru",
                                               "icon": "mdi:hvac", "show_in_sidebar": True,
                                               "require_admin": False})

    @property
    def mode(self) -> str:
        return "yaml"

    async def async_get_info(self) -> dict[str, Any]:
        return {"mode": "yaml", "views": len(build_dashboard(self.hass)["views"])}

    async def async_load(self, force: bool) -> dict[str, Any]:
        return build_dashboard(self.hass)

    async def async_json(self, force: bool) -> json_fragment:
        return json_fragment(json_bytes(build_dashboard(self.hass)))


@callback
def async_register_dashboard(hass: HomeAssistant) -> bool:
    """Register the sidebar dashboard once. Returns False if the url is taken."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        return False
    existing = lovelace.dashboards.get(DASHBOARD_URL)
    if existing is not None:
        return isinstance(existing, DeltaTruDashboard)
    lovelace.dashboards[DASHBOARD_URL] = DeltaTruDashboard(hass)
    frontend.async_register_built_in_panel(
        hass, "lovelace", frontend_url_path=DASHBOARD_URL, sidebar_title="DeltaTru",
        sidebar_icon="mdi:hvac", require_admin=False, config={"mode": "yaml"}, update=False,
    )
    return True


@callback
def async_unregister_dashboard(hass: HomeAssistant) -> None:
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace and isinstance(lovelace.dashboards.get(DASHBOARD_URL), DeltaTruDashboard):
        lovelace.dashboards.pop(DASHBOARD_URL)
        frontend.async_remove_panel(hass, DASHBOARD_URL)
