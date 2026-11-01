"""Base entity for a DeltaTru system device."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import DeltaTruCoordinator, SystemState


def system_device_info(system: SystemState) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, system.id)},
        name=f"DeltaTru {system.name}",
        manufacturer=MANUFACTURER,
        model="HVAC system",
        configuration_url="https://deltatru.com",
    )


class DeltaTruEntity(CoordinatorEntity[DeltaTruCoordinator]):
    """Entity bound to one cloud system."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DeltaTruCoordinator, system_id: str, key: str) -> None:
        super().__init__(coordinator)
        self.system_id = system_id
        self._attr_unique_id = f"{system_id}_{key}"
        self._attr_device_info = system_device_info(coordinator.data[system_id])

    @property
    def system(self) -> SystemState | None:
        return self.coordinator.data.get(self.system_id)

    @property
    def available(self) -> bool:
        return super().available and self.system is not None
