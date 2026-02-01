"""Services for Shine Monitor integration."""
from __future__ import annotations

import datetime
import logging
from datetime import timedelta
from typing import Any

import voluptuous as vol
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    async_import_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.helpers import entity_registry as er
try:
    from homeassistant.components.recorder.models import StatisticMeanType
except ImportError:
    StatisticMeanType = None
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    ATTR_PLANT_ID,
    ATTR_START_DATE,
    SERVICE_IMPORT_HISTORY,
)
from .coordinator import ShineMonitorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_IMPORT_HISTORY_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_START_DATE): cv.date,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Shine Monitor integration."""

    async def handle_import_history(call: ServiceCall) -> None:
        """Handle the import history service call."""
        start_date = call.data.get(ATTR_START_DATE)
        
        # Get all coordinators
        coordinators: dict[str, ShineMonitorDataUpdateCoordinator] = hass.data.get(DOMAIN, {})
        
        if not coordinators:
            _LOGGER.error("No Shine Monitor integrations found")
            return

        for entry_id, coordinator in coordinators.items():
            await _import_history_for_plant(hass, coordinator, start_date)

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_HISTORY,
        handle_import_history,
        schema=SERVICE_IMPORT_HISTORY_SCHEMA,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Shine Monitor services."""
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_IMPORT_HISTORY)


async def _import_history_for_plant(
    hass: HomeAssistant,
    coordinator: ShineMonitorDataUpdateCoordinator,
    start_date: datetime.date | None = None,
) -> None:
    """Import historical data for a specific plant."""
    plant_id = coordinator.plant_id
    plant_name = coordinator.plant_name
    client = coordinator.client

    _LOGGER.info("Starting history import for plant %s (%s)", plant_name, plant_id)

    # Find the total_energy sensor's entity_id from the entity registry
    ent_reg = er.async_get(hass)
    unique_id = f"{plant_id}_total_energy"
    entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
    
    if not entity_id:
        _LOGGER.error("Could not find total_energy sensor for plant %s (unique_id: %s)", plant_name, unique_id)
        return
    
    _LOGGER.info("Importing history into sensor: %s", entity_id)

    # Determine the date range
    now = dt_util.now()
    if start_date is None:
        # Default to 2015 to fetch all available data
        start_dt = datetime.datetime(2015, 1, 1)
        start_dt = dt_util.as_local(start_dt)
    else:
        # Convert date to datetime if needed
        start_dt = datetime.datetime.combine(start_date, datetime.time.min)
        start_dt = dt_util.as_local(start_dt)
    
    # Use sensor entity_id as statistic_id with recorder source
    statistic_id = entity_id
    
    # Build metadata for sensor statistics
    metadata_kwargs = {
        "has_mean": False,
        "has_sum": True,
        "name": f"{plant_name} Total Energy",
        "source": "recorder",
        "statistic_id": statistic_id,
        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        "unit_class": "energy",
    }
    # Add mean_type for HA 2026.11+ compatibility
    if StatisticMeanType is not None:
        metadata_kwargs["mean_type"] = StatisticMeanType.NONE
    else:
        metadata_kwargs["mean_type"] = None
    
    metadata = StatisticMetaData(**metadata_kwargs)

    statistics: list[StatisticData] = []
    cumulative_sum = 0.0

    # Iterate through each month from start_date to now
    current_date = start_dt.replace(day=1)
    
    while current_date <= now:
        year = current_date.year
        month = current_date.month
        
        _LOGGER.debug("Fetching data for %d-%02d", year, month)
        
        try:
            daily_data = await client.get_energy_month_per_day(plant_id, year, month)
            _LOGGER.debug("Got %d records for %d-%02d: %s", len(daily_data), year, month, daily_data[:3] if daily_data else "empty")
            
            for day_record in daily_data:
                try:
                    # Parse the date from the record - API uses 'ts' field with format "YYYY-MM-DD HH:MM:SS"
                    day_str = day_record.get("ts") or day_record.get("date") or day_record.get("time") or ""
                    if not day_str:
                        _LOGGER.debug("No date found in record: %s", day_record)
                        continue
                    
                    # Handle both "YYYY-MM-DD" and "YYYY-MM-DD HH:MM:SS" formats
                    day_str = day_str.split(" ")[0]  # Take just the date part
                    day_date = datetime.datetime.strptime(day_str, "%Y-%m-%d")
                    
                    # Skip future dates
                    if day_date.date() > now.date():
                        continue
                    
                    # API uses 'val' field for energy value
                    day_energy = float(day_record.get("val") or day_record.get("energy") or day_record.get("value") or 0)
                    
                    # Always add to cumulative sum and create entry (even for 0)
                    cumulative_sum += day_energy
                    
                    # Create statistic for this day - must be at top of hour in UTC
                    stat_time = datetime.datetime(
                        day_date.year, day_date.month, day_date.day,
                        0, 0, 0, tzinfo=datetime.timezone.utc
                    )
                    
                    statistics.append(
                        StatisticData(
                            start=stat_time,
                            sum=cumulative_sum,
                            state=day_energy,
                        )
                    )
                except (ValueError, KeyError) as err:
                    _LOGGER.debug("Error parsing day record: %s", err)
                    continue
                    
        except Exception as err:
            _LOGGER.warning("Error fetching data for %d-%02d: %s", year, month, err)

        # Move to next month
        if month == 12:
            current_date = current_date.replace(year=year + 1, month=1)
        else:
            current_date = current_date.replace(month=month + 1)

    # Import the statistics into the sensor
    if statistics:
        _LOGGER.info(
            "Importing %d daily statistics for plant %s into %s (total: %.1f kWh)", 
            len(statistics), plant_name, statistic_id, cumulative_sum
        )
        async_import_statistics(hass, metadata, statistics)
        _LOGGER.info("History import completed for plant %s", plant_name)
    else:
        _LOGGER.warning("No historical data found for plant %s", plant_name)


async def import_monthly_statistics(
    hass: HomeAssistant,
    coordinator: ShineMonitorDataUpdateCoordinator,
    start_year: int | None = None,
) -> None:
    """Import monthly statistics for a plant."""
    plant_id = coordinator.plant_id
    plant_name = coordinator.plant_name
    client = coordinator.client

    now = dt_util.now()
    if start_year is None:
        start_year = now.year - 2

    statistic_id = f"{DOMAIN}:plant_{plant_id}_monthly_energy"
    
    # Build metadata kwargs - handle both old and new HA versions
    metadata_kwargs = {
        "has_mean": False,
        "has_sum": True,
        "name": f"{plant_name} Monthly Energy (Historical)",
        "source": DOMAIN,
        "statistic_id": statistic_id,
        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        "unit_class": "energy",
    }
    if StatisticMeanType is not None:
        metadata_kwargs["mean_type"] = StatisticMeanType.NONE
    else:
        metadata_kwargs["mean_type"] = None
    
    metadata = StatisticMetaData(**metadata_kwargs)

    statistics: list[StatisticData] = []
    cumulative_sum = 0.0

    for year in range(start_year, now.year + 1):
        _LOGGER.debug("Fetching monthly data for year %d", year)
        
        try:
            monthly_data = await client.get_energy_year_per_month(plant_id, year)
            
            for month_record in monthly_data:
                try:
                    month_num = int(month_record.get("month", 0))
                    month_energy = float(month_record.get("energy", 0))
                    
                    if month_num > 0 and month_energy > 0:
                        cumulative_sum += month_energy
                        
                        # Create timestamp for end of month - must be at top of hour in UTC
                        if month_num == 12:
                            next_month = datetime.datetime(year + 1, 1, 1)
                        else:
                            next_month = datetime.datetime(year, month_num + 1, 1)
                        
                        end_of_month = next_month - timedelta(days=1)
                        stat_time = datetime.datetime(
                            end_of_month.year, end_of_month.month, end_of_month.day,
                            0, 0, 0, tzinfo=datetime.timezone.utc
                        )
                        
                        statistics.append(
                            StatisticData(
                                start=stat_time,
                                sum=cumulative_sum,
                                state=month_energy,
                            )
                        )
                except (ValueError, KeyError) as err:
                    _LOGGER.debug("Error parsing month record: %s", err)
                    continue
                    
        except Exception as err:
            _LOGGER.warning("Error fetching monthly data for %d: %s", year, err)

    if statistics:
        _LOGGER.info(
            "Importing %d monthly statistics for plant %s", len(statistics), plant_name
        )
        async_add_external_statistics(hass, metadata, statistics)
    else:
        _LOGGER.warning("No monthly historical data found for plant %s", plant_name)
