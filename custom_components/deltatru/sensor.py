"""System health, latest alert and last upload sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import HEALTH_STATES
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
        ents = []
        for sid in new:
            ents += [HealthSensor(coordinator, sid), LatestAlertSensor(coordinator, sid), LastUploadSensor(coordinator, sid)]
        async_add_entities(ents)

    _add()
    entry.async_on_unload(coordinator.async_add_listener(_add))


class HealthSensor(DeltaTruEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = HEALTH_STATES
    _attr_translation_key = "health"

    def __init__(self, coordinator, system_id: str) -> None:
        super().__init__(coordinator, system_id, "health")

    @property
    def native_value(self) -> str | None:
        return self.system.health if self.system else None

    @property
    def extra_state_attributes(self):
        return {"active_alerts": len(self.system.alerts), "system_status": self.system.status} if self.system else None


class LatestAlertSensor(DeltaTruEntity, SensorEntity):
    _attr_translation_key = "latest_alert"

    def __init__(self, coordinator, system_id: str) -> None:
        super().__init__(coordinator, system_id, "latest_alert")

    @property
    def native_value(self) -> str | None:
        if not self.system:
            return None
        a = self.system.latest_alert
        return (a.get("title") or "")[:255] if a else "No active alerts"

    @property
    def extra_state_attributes(self):
        a = self.system.latest_alert if self.system else None
        return {k: a.get(k) for k in ("family", "severity", "status", "rule_id", "first_seen", "last_seen")} if a else None


class LastUploadSensor(DeltaTruEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_upload"

    def __init__(self, coordinator, system_id: str) -> None:
        super().__init__(coordinator, system_id, "last_upload")

    @property
    def native_value(self):
        return self.system.last_upload if self.system else None
