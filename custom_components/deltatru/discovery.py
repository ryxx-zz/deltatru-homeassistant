"""Find DeltaTru ESPHome monitors already in Home Assistant and group them by system."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import AHU_MARKERS, COND_MARKERS, PROJECT_PREFIX


@dataclass
class Monitor:
    """One ESPHome DeltaTru monitor."""

    device_id: str  # HA device registry id
    name: str
    role: str  # "ahu" | "cond"
    entities: dict[str, str] = field(default_factory=dict)  # object_id -> entity_id
    system_id: str | None = None  # from the "System ID" text entity, if any


def object_id(entry: er.RegistryEntry) -> str:
    """ESPHome unique_id is '{mac}-{domain}-{object_id}'; fall back to entity_id."""
    parts = entry.unique_id.split("-", 2)
    if len(parts) == 3 and parts[2]:
        return parts[2]
    return entry.entity_id.split(".", 1)[1]


def find_monitors(hass: HomeAssistant) -> list[Monitor]:
    """Return every ESPHome device that looks like a DeltaTru monitor."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    by_device: dict[str, dict[str, str]] = {}
    for ent in ent_reg.entities.values():
        if ent.platform != "esphome" or not ent.device_id:
            continue
        by_device.setdefault(ent.device_id, {})[object_id(ent)] = ent.entity_id

    monitors: list[Monitor] = []
    for device_id, ents in by_device.items():
        device = dev_reg.async_get(device_id)
        if device is None:
            continue
        model = (device.model or "").lower()
        keys = set(ents)
        role: str | None = None
        if PROJECT_PREFIX in model:
            role = "cond" if model.endswith("cond") else "ahu"
        elif keys & set(AHU_MARKERS):
            role = "ahu"
        elif keys & set(COND_MARKERS):
            role = "cond"
        if role is None:
            continue
        mon = Monitor(device_id, device.name_by_user or device.name or device_id, role, ents)
        if (sid := ents.get("system_id")) and (state := hass.states.get(sid)):
            if state.state not in ("", "unknown", "unavailable"):
                mon.system_id = state.state
        monitors.append(mon)
    return sorted(monitors, key=lambda m: (m.role, m.name))


def assign(monitors: list[Monitor], system_ids: list[str], device_map: dict[str, str]) -> dict[str, list[Monitor]]:
    """Map monitors to cloud systems: option override, then firmware System ID, then the only system."""
    out: dict[str, list[Monitor]] = {sid: [] for sid in system_ids}
    for mon in monitors:
        sid = device_map.get(mon.device_id) or mon.system_id
        if sid not in out and len(system_ids) == 1:
            sid = system_ids[0]
        if sid in out:
            out[sid].append(mon)
    return out
