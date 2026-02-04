"""Binary sensor platform for Shine Monitor integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DATA_WARNING_COUNT,
    DATA_INVERTER_ALARMS,
    DATA_GRID_ALARMS,
    ICON_WARNING,
)
from .coordinator import ShineMonitorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shine Monitor binary sensors."""
    coordinator: ShineMonitorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = []

    # Add plant-level alarm sensor
    entities.append(ShineMonitorPlantAlarmSensor(coordinator))
    
    # Add inverter-specific alarm sensor (excludes grid faults)
    entities.append(ShineMonitorInverterAlarmSensor(coordinator))

    async_add_entities(entities)


class ShineMonitorPlantAlarmSensor(
    CoordinatorEntity[ShineMonitorDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if there are unhandled alarms."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = ICON_WARNING

    def __init__(self, coordinator: ShineMonitorDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.plant_id}_has_alarms"
        self._attr_name = "Has Unhandled Alarms"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.plant_id)},
            name=f"Solar Plant {self.coordinator.plant_name}",
            manufacturer="Shine Monitor",
            model="Solar Plant",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if there are unhandled alarms."""
        if self.coordinator.data is None:
            return None
        # Use unhandled count - only shows Problem for alarms that haven't been handled
        unhandled_count = self.coordinator.data.get("unhandled_warning_count", 0)
        return unhandled_count > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}
        return {
            "unhandled_alarm_count": self.coordinator.data.get("unhandled_warning_count", 0),
            "total_alarm_count": self.coordinator.data.get(DATA_WARNING_COUNT, 0),
        }


class ShineMonitorInverterAlarmSensor(
    CoordinatorEntity[ShineMonitorDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if there are real inverter alarms (excludes grid faults)."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = ICON_WARNING

    def __init__(self, coordinator: ShineMonitorDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.plant_id}_has_inverter_alarms"
        self._attr_name = "Has Inverter Alarms"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.plant_id)},
            name=f"Solar Plant {self.coordinator.plant_name}",
            manufacturer="Shine Monitor",
            model="Solar Plant",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if there are real inverter alarms (not grid faults)."""
        if self.coordinator.data is None:
            return None
        inverter_alarms = self.coordinator.data.get(DATA_INVERTER_ALARMS, 0)
        return inverter_alarms > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}
        return {
            "inverter_alarm_count": self.coordinator.data.get(DATA_INVERTER_ALARMS, 0),
            "grid_fault_count": self.coordinator.data.get(DATA_GRID_ALARMS, 0),
            "latest_inverter_alarm": self.coordinator.data.get("latest_inverter_alarm"),
        }
