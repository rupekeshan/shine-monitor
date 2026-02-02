"""Sensor platform for Shine Monitor integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfPower,
    UnitOfMass,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfFrequency,
    UnitOfTemperature,
    PERCENTAGE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_CURRENCY,
    DEFAULT_CURRENCY,
    DATA_CURRENT_POWER,
    DATA_DAILY_ENERGY,
    DATA_MONTHLY_ENERGY,
    DATA_YEARLY_ENERGY,
    DATA_TOTAL_ENERGY,
    DATA_PROFIT,
    DATA_COAL,
    DATA_CO2,
    DATA_SO2,
    DATA_WARNING_COUNT,
    DATA_INSTALLED_CAPACITY,
    DATA_DEVICES,
    DATA_INVERTER_ALARMS,
    DATA_GRID_ALARMS,
    ICON_SOLAR_POWER,
    ICON_ENERGY,
    ICON_PROFIT,
    ICON_COAL,
    ICON_CO2,
    ICON_SO2,
    ICON_WARNING,
    ICON_CAPACITY,
    ICON_INVERTER,
    ICON_TEMPERATURE,
    ICON_VOLTAGE,
    ICON_CURRENT,
    ICON_FREQUENCY,
)
from .coordinator import ShineMonitorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ShineMonitorSensorEntityDescription(SensorEntityDescription):
    """Describes Shine Monitor sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None


# Plant-level sensors
PLANT_SENSORS: tuple[ShineMonitorSensorEntityDescription, ...] = (
    ShineMonitorSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        name="Current Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon=ICON_SOLAR_POWER,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_CURRENT_POWER),
    ),
    ShineMonitorSensorEntityDescription(
        key="daily_energy",
        translation_key="daily_energy",
        name="Daily Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,  # TOTAL because it resets daily
        icon=ICON_ENERGY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_DAILY_ENERGY),
    ),
    ShineMonitorSensorEntityDescription(
        key="monthly_energy",
        translation_key="monthly_energy",
        name="Monthly Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,  # TOTAL because it resets monthly
        icon=ICON_ENERGY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_MONTHLY_ENERGY),
    ),
    ShineMonitorSensorEntityDescription(
        key="yearly_energy",
        translation_key="yearly_energy",
        name="Yearly Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,  # TOTAL because it resets yearly
        icon=ICON_ENERGY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_YEARLY_ENERGY),
    ),
    ShineMonitorSensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        name="Total Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon=ICON_ENERGY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_TOTAL_ENERGY),
    ),
    ShineMonitorSensorEntityDescription(
        key="installed_capacity",
        translation_key="installed_capacity",
        name="Installed Capacity",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        icon=ICON_CAPACITY,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_INSTALLED_CAPACITY),
    ),
    ShineMonitorSensorEntityDescription(
        key="warning_count",
        translation_key="warning_count",
        name="Total Alarms",
        icon=ICON_WARNING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get(DATA_WARNING_COUNT),
    ),
    ShineMonitorSensorEntityDescription(
        key="unhandled_warning_count",
        translation_key="unhandled_warning_count",
        name="Unhandled Alarms",
        icon=ICON_WARNING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("unhandled_warning_count"),
    ),
    ShineMonitorSensorEntityDescription(
        key="inverter_alarms",
        translation_key="inverter_alarms",
        name="Inverter Alarms",
        icon=ICON_WARNING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get(DATA_INVERTER_ALARMS, 0),
    ),
    ShineMonitorSensorEntityDescription(
        key="grid_alarms",
        translation_key="grid_alarms",
        name="Grid Fault Alarms",
        icon=ICON_WARNING,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get(DATA_GRID_ALARMS, 0),
    ),
)

# Environmental sensors
ENVIRONMENTAL_SENSORS: tuple[ShineMonitorSensorEntityDescription, ...] = (
    ShineMonitorSensorEntityDescription(
        key="daily_profit",
        translation_key="daily_profit",
        name="Daily Profit",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon=ICON_PROFIT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_PROFIT),
    ),
    ShineMonitorSensorEntityDescription(
        key="total_profit",
        translation_key="total_profit",
        name="Total Profit",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon=ICON_PROFIT,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("total_profit"),
    ),
    ShineMonitorSensorEntityDescription(
        key="daily_coal_saving",
        translation_key="daily_coal_saving",
        name="Daily Coal Saving",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon=ICON_COAL,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_COAL),
    ),
    ShineMonitorSensorEntityDescription(
        key="total_coal_saving",
        translation_key="total_coal_saving",
        name="Total Coal Saving",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon=ICON_COAL,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("total_coal"),
    ),
    ShineMonitorSensorEntityDescription(
        key="daily_co2_reduction",
        translation_key="daily_co2_reduction",
        name="Daily CO₂ Reduction",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon=ICON_CO2,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_CO2),
    ),
    ShineMonitorSensorEntityDescription(
        key="total_co2_reduction",
        translation_key="total_co2_reduction",
        name="Total CO₂ Reduction",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon=ICON_CO2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("total_co2"),
    ),
    ShineMonitorSensorEntityDescription(
        key="daily_so2_reduction",
        translation_key="daily_so2_reduction",
        name="Daily SO₂ Reduction",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon=ICON_SO2,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda data: data.get(DATA_SO2),
    ),
    ShineMonitorSensorEntityDescription(
        key="total_so2_reduction",
        translation_key="total_so2_reduction",
        name="Total SO₂ Reduction",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        icon=ICON_SO2,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: data.get("total_so2"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Shine Monitor sensor platform."""
    coordinator: ShineMonitorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    currency = entry.options.get(CONF_CURRENCY, DEFAULT_CURRENCY)

    entities: list[SensorEntity] = []

    # Add plant sensors
    for description in PLANT_SENSORS:
        entities.append(ShineMonitorPlantSensor(coordinator, description))

    # Add environmental sensors
    for description in ENVIRONMENTAL_SENSORS:
        entities.append(
            ShineMonitorPlantSensor(coordinator, description, currency=currency)
        )

    # Add device sensors if device data is available
    if coordinator.data and DATA_DEVICES in coordinator.data:
        for device in coordinator.data[DATA_DEVICES]:
            device_sn = device.get("sn", "")
            device_name = device.get("name", device_sn)
            device_data = device.get("data", {})
            
            # Add device-specific sensors based on available data
            entities.extend(
                _create_device_sensors(coordinator, device_sn, device_name, device_data)
            )

    async_add_entities(entities)


def _create_device_sensors(
    coordinator: ShineMonitorDataUpdateCoordinator,
    device_sn: str,
    device_name: str,
    device_data: dict[str, Any],
) -> list[SensorEntity]:
    """Create sensors for a device based on available data."""
    entities: list[SensorEntity] = []
    
    # Common inverter fields that might be in the data
    # The actual field names depend on the device type and API response
    # These will be dynamically created based on what's available
    
    if device_data:
        # Create a generic device sensor that shows all data
        entities.append(
            ShineMonitorDeviceSensor(
                coordinator=coordinator,
                device_sn=device_sn,
                device_name=device_name,
            )
        )
    
    return entities


class ShineMonitorPlantSensor(CoordinatorEntity[ShineMonitorDataUpdateCoordinator], SensorEntity):
    """Representation of a Shine Monitor plant sensor."""

    entity_description: ShineMonitorSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ShineMonitorDataUpdateCoordinator,
        description: ShineMonitorSensorEntityDescription,
        currency: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.plant_id}_{description.key}"
        
        # Set currency for monetary sensors
        if description.device_class == SensorDeviceClass.MONETARY and currency:
            self._attr_native_unit_of_measurement = currency

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
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator.data)
        return None


class ShineMonitorDeviceSensor(CoordinatorEntity[ShineMonitorDataUpdateCoordinator], SensorEntity):
    """Representation of a Shine Monitor device sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ShineMonitorDataUpdateCoordinator,
        device_sn: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_sn = device_sn
        self._device_name = device_name
        self._attr_unique_id = f"{coordinator.plant_id}_{device_sn}_power"
        self._attr_name = "Power"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = ICON_INVERTER

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.plant_id}_{self._device_sn}")},
            name=self._device_name,
            manufacturer="Shine Monitor",
            model="Inverter",
            via_device=(DOMAIN, self.coordinator.plant_id),
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        
        devices = self.coordinator.data.get(DATA_DEVICES, [])
        for device in devices:
            if device.get("sn") == self._device_sn:
                device_data = device.get("data", {})
                # Try to get power from the device data
                # Field names vary by device type
                for field in ["power", "outputPower", "activePower", "pac"]:
                    if field in device_data:
                        return device_data[field]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if self.coordinator.data is None:
            return {}
        
        devices = self.coordinator.data.get(DATA_DEVICES, [])
        for device in devices:
            if device.get("sn") == self._device_sn:
                return {
                    "device_sn": self._device_sn,
                    "status": device.get("status", "unknown"),
                    "device_type": device.get("type", "unknown"),
                    **device.get("data", {}),
                }
        return {}

