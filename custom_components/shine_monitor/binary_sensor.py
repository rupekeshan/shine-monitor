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
    DATA_DEVICES,
    DATA_DATALOGGERS,
    DATA_WARNING_COUNT,
    ICON_WARNING,
    ICON_DATALOGGER,
    ICON_INVERTER,
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

    # Add device status sensors
    if coordinator.data:
        # Add device (inverter) status sensors
        devices = coordinator.data.get(DATA_DEVICES, [])
        for device in devices:
            device_sn = device.get("sn", "")
            device_name = device.get("name", device_sn)
            if device_sn:
                entities.append(
                    ShineMonitorDeviceStatusSensor(
                        coordinator=coordinator,
                        device_sn=device_sn,
                        device_name=device_name,
                        device_type="inverter",
                    )
                )

        # Add datalogger status sensors
        dataloggers = coordinator.data.get(DATA_DATALOGGERS, [])
        for datalogger in dataloggers:
            dl_sn = datalogger.get("sn", "")
            dl_name = datalogger.get("name", dl_sn)
            if dl_sn:
                entities.append(
                    ShineMonitorDeviceStatusSensor(
                        coordinator=coordinator,
                        device_sn=dl_sn,
                        device_name=dl_name,
                        device_type="datalogger",
                    )
                )

    async_add_entities(entities)


class ShineMonitorPlantAlarmSensor(
    CoordinatorEntity[ShineMonitorDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if there are active alarms."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = ICON_WARNING

    def __init__(self, coordinator: ShineMonitorDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.plant_id}_has_alarms"
        self._attr_name = "Has Active Alarms"

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
        """Return true if there are active alarms."""
        if self.coordinator.data is None:
            return None
        warning_count = self.coordinator.data.get(DATA_WARNING_COUNT, 0)
        return warning_count > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}
        return {
            "alarm_count": self.coordinator.data.get(DATA_WARNING_COUNT, 0),
        }


class ShineMonitorDeviceStatusSensor(
    CoordinatorEntity[ShineMonitorDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating device online status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator: ShineMonitorDataUpdateCoordinator,
        device_sn: str,
        device_name: str,
        device_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_sn = device_sn
        self._device_name = device_name
        self._device_type = device_type
        self._attr_unique_id = f"{coordinator.plant_id}_{device_sn}_online"
        self._attr_name = "Online"
        self._attr_icon = ICON_DATALOGGER if device_type == "datalogger" else ICON_INVERTER

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        model = "Datalogger" if self._device_type == "datalogger" else "Inverter"
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.plant_id}_{self._device_sn}")},
            name=self._device_name,
            manufacturer="Shine Monitor",
            model=model,
            via_device=(DOMAIN, self.coordinator.plant_id),
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if device is online."""
        if self.coordinator.data is None:
            return None

        # Check the appropriate data source based on device type
        if self._device_type == "datalogger":
            dataloggers = self.coordinator.data.get(DATA_DATALOGGERS, [])
            for dl in dataloggers:
                if dl.get("sn") == self._device_sn:
                    status = dl.get("status", "").lower()
                    return status in ("online", "1", "normal")
        else:
            devices = self.coordinator.data.get(DATA_DEVICES, [])
            for device in devices:
                if device.get("sn") == self._device_sn:
                    status = device.get("status", "").lower()
                    return status in ("online", "1", "normal")

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}

        # Get status from appropriate data source
        if self._device_type == "datalogger":
            dataloggers = self.coordinator.data.get(DATA_DATALOGGERS, [])
            for dl in dataloggers:
                if dl.get("sn") == self._device_sn:
                    return {
                        "device_sn": self._device_sn,
                        "status": dl.get("status", "unknown"),
                    }
        else:
            devices = self.coordinator.data.get(DATA_DEVICES, [])
            for device in devices:
                if device.get("sn") == self._device_sn:
                    return {
                        "device_sn": self._device_sn,
                        "status": device.get("status", "unknown"),
                        "device_type": device.get("type", "unknown"),
                    }

        return {"device_sn": self._device_sn}
