"""Find DeltaTru ESPHome monitors already in Home Assistant and group them by system."""

from __future__ import annotations

import re
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


KNOWN_KEYS: tuple[str, ...] = (
    "delta_t", "return_air", "supply_air", "suction_line", "liquid_line", "blower_amps",
    "compressor_amps", "outdoor_air", "outdoor_temp", "contactor_24v_present_y_c",
    "hvac_mode", "status", "problem", "system_id",
)
_SIGNATURE = set(AHU_MARKERS) | set(COND_MARKERS) | {"suction_line", "liquid_line", "outdoor_temp"}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _uid_tail(unique_id: str) -> str | None:
    """Entity part of an ESPHome unique_id, any version.

    v1 '{mac}-{type}-{object_id}', v2 '{mac}-{type}-{Name}', either optionally '@{sub_device}';
    v3 '{mac}/{sub_device}/{type}/{Name}'.
    """
    if "/" in unique_id:
        parts = unique_id.split("/")
        return parts[-1] if len(parts) >= 4 else None
    parts = unique_id.split("-", 2)
    if len(parts) == 3 and parts[2]:
        return parts[2].rsplit("@", 1)[0]
    return None


def _candidates(entry: er.RegistryEntry) -> list[str]:
    out = []
    for raw in (_uid_tail(entry.unique_id or ""), entry.original_name, entry.name, entry.entity_id.split(".", 1)[1]):
        if raw and (slug := _slug(raw)) and slug not in out:
            out.append(slug)
    return out


def object_id(entry: er.RegistryEntry) -> str:
    """Canonical key for an ESPHome entity ('delta_t', 'problem', ...), whatever the unique_id format.

    Known DeltaTru keys are matched exactly or as a suffix ('ahu_1_delta_t'), case-insensitive.
    """
    cands = _candidates(entry)
    for cand in cands:
        if cand in KNOWN_KEYS:
            return cand
    for cand in cands:
        for key in sorted(KNOWN_KEYS, key=len, reverse=True):
            if cand.endswith("_" + key):
                return key
    return cands[0] if cands else entry.entity_id.split(".", 1)[1]


def _esphome_devices(hass: HomeAssistant) -> dict[str, dict[str, str]]:
    ent_reg = er.async_get(hass)
    by_device: dict[str, dict[str, str]] = {}
    for ent in ent_reg.entities.values():
        if ent.platform != "esphome" or not ent.device_id:
            continue
        by_device.setdefault(ent.device_id, {}).setdefault(object_id(ent), ent.entity_id)
    return by_device


def _device_name(device: dr.DeviceEntry, fallback: str) -> str:
    return device.name_by_user or device.name or fallback


def find_esphome_devices(hass: HomeAssistant) -> list[tuple[str, str]]:
    """Every ESPHome device in HA as (device_id, name), for manual mapping."""
    dev_reg = dr.async_get(hass)
    out = []
    for device_id in _esphome_devices(hass):
        if device := dev_reg.async_get(device_id):
            out.append((device_id, _device_name(device, device_id)))
    return sorted(out, key=lambda d: d[1].lower())


def _role(model: str, keys: set[str], name: str = "") -> str | None:
    if PROJECT_PREFIX in model:
        return "cond" if model.endswith("cond") else "ahu"
    if keys & {"compressor_amps", "outdoor_air", "outdoor_temp", "contactor_24v_present_y_c"} and not keys & {
        "blower_amps", "return_air", "supply_air"
    }:
        return "cond"
    if keys & _SIGNATURE or keys & {"delta_t", "problem", "hvac_mode"}:
        return "cond" if "cond" in name.lower() else "ahu"
    return None


def find_monitors(hass: HomeAssistant, include: set[str] | None = None) -> list[Monitor]:
    """Every ESPHome device that looks like a DeltaTru monitor (plus any device ids in `include`)."""
    dev_reg = dr.async_get(hass)
    include = include or set()
    monitors: list[Monitor] = []
    for device_id, ents in _esphome_devices(hass).items():
        device = dev_reg.async_get(device_id)
        if device is None:
            continue
        name = _device_name(device, device_id)
        role = _role((device.model or "").lower(), set(ents), name)
        if role is None and device_id in include:
            role = "cond" if "cond" in name.lower() else "ahu"
        if role is None:
            continue
        mon = Monitor(device_id, _device_name(device, device_id), role, ents)
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
