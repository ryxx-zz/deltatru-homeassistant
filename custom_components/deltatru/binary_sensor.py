"""One problem binary_sensor per alert family, per system."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ALERT_FAMILIES
from .coordinator import DeltaTruConfigEntry
from .entity import DeltaTruEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: DeltaTruConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    def _add() -> None:
        new = [sid for sid in coordinator.data if sid not in known]
        known.update(new)
        async_add_entities(
            [AlertFamilySensor(coordinator, sid, fam) for sid in new for fam in ALERT_FAMILIES]
            + [AnyAlertSensor(coordinator, sid) for sid in new]
        )

    _add()
    entry.async_on_unload(coordinator.async_add_listener(_add))


class AlertFamilySensor(DeltaTruEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, system_id: str, family: str) -> None:
        super().__init__(coordinator, system_id, f"alert_{family}")
        self.family = family
        self._attr_translation_key = f"alert_{family}"

    @property
    def is_on(self) -> bool:
        return self.system is not None and self.family in self.system.families()

    @property
    def extra_state_attributes(self):
        if not self.system:
            return None
        hits = [a for a in self.system.alerts if a["family"] == self.family]
        if not hits:
            return None
        a = hits[0]
        return {"title": a.get("title"), "severity": a.get("severity"), "status": a.get("status"),
                "rule_id": a.get("rule_id"), "first_seen": a.get("first_seen"), "last_seen": a.get("last_seen")}


class AnyAlertSensor(DeltaTruEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "problem"

    def __init__(self, coordinator, system_id: str) -> None:
        super().__init__(coordinator, system_id, "problem")

    @property
    def is_on(self) -> bool:
        return bool(self.system and self.system.alerts)
