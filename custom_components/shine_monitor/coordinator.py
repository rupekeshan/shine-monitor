"""Data update coordinator for Shine Monitor integration."""
from __future__ import annotations

import logging
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    API_BASE_URL,
    DEFAULT_UPDATE_INTERVAL,
    REAUTH_INTERVAL,
    ACTION_AUTH,
    ACTION_QUERY_PLANT_ACTIVE_OUTPUT_POWER_CURRENT,
    ACTION_QUERY_PLANT_ENERGY_DAY,
    ACTION_QUERY_PLANT_ENERGY_MONTH,
    ACTION_QUERY_PLANT_ENERGY_YEAR,
    ACTION_QUERY_PLANT_ENERGY_TOTAL,
    ACTION_QUERY_PLANT_ENERGY_MONTH_PER_DAY,
    ACTION_QUERY_PLANT_ENERGY_YEAR_PER_MONTH,
    ACTION_QUERY_PLANTS_PROFIT_ONE_DAY,
    ACTION_QUERY_PLANTS_PROFIT,
    ACTION_QUERY_PLANT_WARNING_COUNT,
    ACTION_QUERY_PLANTS_NOMINAL_POWER,
    ACTION_QUERY_DEVICES,
    ACTION_QUERY_DEVICE_LAST_DATA,
    ACTION_QUERY_DEVICE_STATUS,
    ACTION_QUERY_COLLECTORS,
    ACTION_QUERY_COLLECTOR_STATUS,
    CONF_ENABLE_DEVICES,
    DEFAULT_ENABLE_DEVICES,
    GRID_FAULT_CODES,
    DATA_CURRENT_POWER,
    DATA_DAILY_ENERGY,
    DATA_MONTHLY_ENERGY,
    DATA_YEARLY_ENERGY,
    DATA_TOTAL_ENERGY,
    DATA_PROFIT,
    DATA_COAL,
    DATA_CO2,
    DATA_SO2,
    DATA_LAST_UPDATED,
    DATA_DEVICES,
    DATA_DATALOGGERS,
    DATA_WARNING_COUNT,
    DATA_INSTALLED_CAPACITY,
    DATA_INVERTER_FAULT_COUNT,
    DATA_GRID_FAULT_COUNT,
    DATA_INVERTER_ALARMS,
    DATA_GRID_ALARMS,
    DATA_LATEST_ALARM,
    DATA_LATEST_INVERTER_FAULT,
)

_LOGGER = logging.getLogger(__name__)


class ShineMonitorAPIClient:
    """API Client for Shine Monitor."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        username: str,
        password: str,
        company_key: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._username = username
        self._password = password
        self._company_key = company_key
        self._token: str | None = None
        self._secret: str | None = None
        self._last_auth: float = 0

    @property
    def token(self) -> str | None:
        """Return current token."""
        return self._token

    @property
    def secret(self) -> str | None:
        """Return current secret."""
        return self._secret

    def set_credentials(self, token: str, secret: str) -> None:
        """Set authentication credentials."""
        self._token = token
        self._secret = secret
        self._last_auth = time.time()

    def _generate_salt(self) -> str:
        """Generate salt for API requests."""
        return str(int(time.time() * 1000))

    def _generate_auth_signature(self, salt: str, action: str) -> str:
        """Generate signature for authentication."""
        hashed_password = hashlib.sha1(self._password.encode("utf-8")).hexdigest()
        sign_string = salt + hashed_password + action
        return hashlib.sha1(sign_string.encode("utf-8")).hexdigest()

    def _generate_data_signature(self, salt: str, action: str) -> str:
        """Generate signature for data requests."""
        sign_string = salt + self._secret + self._token + action
        return hashlib.sha1(sign_string.encode("utf-8")).hexdigest()

    async def authenticate(self) -> dict[str, Any]:
        """Authenticate with the API and get token/secret."""
        salt = self._generate_salt()
        action = f"&action={ACTION_AUTH}&usr={self._username}&company-key={self._company_key}"
        sign = self._generate_auth_signature(salt, action)
        url = f"{API_BASE_URL}?sign={sign}&salt={salt}{action}"

        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    raise UpdateFailed(f"Authentication failed with status {response.status}")
                data = await response.json()
                if data.get("err") != 0:
                    raise UpdateFailed(f"Authentication failed: {data.get('desc')}")
                
                self._token = data["dat"]["token"]
                self._secret = data["dat"]["secret"]
                self._last_auth = time.time()
                return data["dat"]
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error during authentication: {err}") from err

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authentication token."""
        if not self._token or not self._secret:
            await self.authenticate()
        elif time.time() - self._last_auth >= REAUTH_INTERVAL.total_seconds():
            await self.authenticate()

    async def _api_request(
        self, action: str, params: dict[str, Any] | None = None, retry_auth: bool = True
    ) -> dict[str, Any]:
        """Make an authenticated API request."""
        await self._ensure_authenticated()

        salt = self._generate_salt()
        action_str = f"&action={action}"
        if params:
            for key, value in params.items():
                action_str += f"&{key}={value}"

        sign = self._generate_data_signature(salt, action_str)
        url = f"{API_BASE_URL}?sign={sign}&token={self._token}&salt={salt}{action_str}"

        try:
            async with self._session.get(url) as response:
                if response.status != 200:
                    raise UpdateFailed(f"Request failed with status {response.status}")
                
                data = await response.json()
                
                # Handle auth errors with retry
                if data.get("desc") == "ERR_NO_AUTH" and retry_auth:
                    _LOGGER.debug("Token expired, re-authenticating")
                    await self.authenticate()
                    return await self._api_request(action, params, retry_auth=False)
                
                if data.get("err") != 0 and data.get("desc") not in ("ERR_NO_RECORD", "ERR_FORMAT_ERROR"):
                    raise UpdateFailed(f"API error: {data.get('desc')}")
                
                return data
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Connection error: {err}") from err

    async def get_plants(self) -> list[dict[str, Any]]:
        """Get list of plants."""
        data = await self._api_request("queryPlants")
        return data.get("dat", {}).get("plant", [])

    async def get_current_power(self, plant_id: str) -> float:
        """Get current output power for a plant."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_ACTIVE_OUTPUT_POWER_CURRENT,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0.0
        return float(data.get("dat", {}).get("outputPower", 0))

    async def get_daily_energy(self, plant_id: str) -> float:
        """Get daily energy production."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_DAY,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0.0
        return float(data.get("dat", {}).get("energy", 0))

    async def get_monthly_energy(self, plant_id: str) -> float | None:
        """Get monthly energy production.
        
        Returns None on error to prevent statistics corruption.
        """
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_MONTH,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return None
        energy = data.get("dat", {}).get("energy")
        if energy is None:
            return None
        return float(energy)

    async def get_yearly_energy(self, plant_id: str) -> float | None:
        """Get yearly energy production.
        
        Returns None on error to prevent statistics corruption for TOTAL_INCREASING sensors.
        """
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_YEAR,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return None  # Return None, not 0, to prevent TOTAL_INCREASING reset
        energy = data.get("dat", {}).get("energy")
        if energy is None:
            return None
        return float(energy)

    async def get_total_energy(self, plant_id: str) -> float | None:
        """Get total energy production.
        
        Returns None on error to prevent statistics corruption for TOTAL_INCREASING sensors.
        """
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_TOTAL,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return None  # Return None, not 0, to prevent TOTAL_INCREASING reset
        energy = data.get("dat", {}).get("energy")
        if energy is None:
            return None
        return float(energy)

    async def get_profit_data(self, plant_id: str, daily_energy: float = 0) -> dict[str, float]:
        """Get profit and environmental data for today."""
        data = await self._api_request(
            ACTION_QUERY_PLANTS_PROFIT_ONE_DAY,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return {"profit": 0, "coal": 0, "co2": 0, "so2": 0}
        
        plants = data.get("dat", {}).get("plant", [])
        if plants:
            plant_data = plants[0]
            # API returns conversion factors, multiply by energy to get actual values
            energy = float(plant_data.get("energy", 0)) or daily_energy
            coal_factor = float(plant_data.get("coal", 0))
            co2_factor = float(plant_data.get("co2", 0))
            so2_factor = float(plant_data.get("so2", 0))
            return {
                "profit": float(plant_data.get("profit", 0)),
                "coal": energy * coal_factor,
                "co2": energy * co2_factor,
                "so2": energy * so2_factor,
            }
        return {"profit": 0, "coal": 0, "co2": 0, "so2": 0}

    async def get_total_profit_data(self, plant_id: str, total_energy: float = 0) -> dict[str, float]:
        """Get total profit and environmental data."""
        data = await self._api_request(
            ACTION_QUERY_PLANTS_PROFIT,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return {"profit": 0, "coal": 0, "co2": 0, "so2": 0}
        
        plants = data.get("dat", {}).get("plant", [])
        if plants:
            plant_data = plants[0]
            # API returns conversion factors, multiply by energy to get actual values
            energy = float(plant_data.get("energy", 0)) or total_energy
            coal_factor = float(plant_data.get("coal", 0))
            co2_factor = float(plant_data.get("co2", 0))
            so2_factor = float(plant_data.get("so2", 0))
            return {
                "profit": float(plant_data.get("profit", 0)),
                "coal": energy * coal_factor,
                "co2": energy * co2_factor,
                "so2": energy * so2_factor,
            }
        return {"profit": 0, "coal": 0, "co2": 0, "so2": 0}

    async def get_warning_count(self, plant_id: str) -> int:
        """Get total alarm/warning count for plant."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_WARNING_COUNT,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0
        return int(data.get("dat", {}).get("count", 0))

    async def get_unhandled_warning_count(self, plant_id: str) -> int:
        """Get count of unhandled/active warnings by checking warning list."""
        # Get first page of warnings to check handle status
        # We need to iterate through pages if there are many unhandled ones
        data = await self._api_request(
            "queryPlantWarning",
            {"plantid": plant_id, "pagesize": 100}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0
        
        warnings = data.get("dat", {}).get("warning", [])
        # Count warnings where handle is False (unhandled)
        unhandled = sum(1 for w in warnings if not w.get("handle", True))
        return unhandled

    async def get_alarm_summary(self, plant_id: str) -> dict[str, Any]:
        """Get categorized alarm summary - separates grid faults from inverter faults.
        
        Returns:
            dict with:
            - inverter_fault_count: Real inverter issues needing attention
            - grid_fault_count: Grid/power cut issues (usually ignorable)
            - latest_alarm: Most recent alarm description
            - latest_inverter_fault: Most recent non-grid fault (if any)
        """
        data = await self._api_request(
            "queryPlantWarning",
            {"plantid": plant_id, "pagesize": 50}  # Get recent 50 alarms
        )
        
        result = {
            "inverter_fault_count": 0,
            "grid_fault_count": 0,
            "latest_alarm": None,
            "latest_inverter_fault": None,
        }
        
        if data.get("desc") == "ERR_NO_RECORD":
            return result
        
        warnings = data.get("dat", {}).get("warning", [])
        if not warnings:
            return result
        
        # Most recent alarm (first in list)
        result["latest_alarm"] = warnings[0].get("desc", "Unknown") if warnings else None
        
        # Categorize alarms
        for warning in warnings:
            # Only count unhandled (active) alarms
            if warning.get("handle", True):
                continue
                
            code = warning.get("code", "")
            if code in GRID_FAULT_CODES:
                result["grid_fault_count"] += 1
            else:
                result["inverter_fault_count"] += 1
                # Track the most recent inverter fault
                if result["latest_inverter_fault"] is None:
                    result["latest_inverter_fault"] = warning.get("desc", "Unknown fault")
        
        return result

    async def get_installed_capacity(self, plant_id: str) -> float:
        """Get installed capacity (nominal power) for plant."""
        data = await self._api_request(
            ACTION_QUERY_PLANTS_NOMINAL_POWER,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0.0
        # API returns nominalPower directly in dat
        dat = data.get("dat", {})
        if isinstance(dat, dict):
            # Try direct field first
            if "nominalPower" in dat:
                return float(dat.get("nominalPower", 0))
            # Fall back to plant array
            plants = dat.get("plant", [])
            if plants:
                return float(plants[0].get("nominalPower", 0))
        return 0.0

    async def get_devices(self, plant_id: str) -> list[dict[str, Any]]:
        """Get list of devices for a plant."""
        data = await self._api_request(
            ACTION_QUERY_DEVICES,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return []
        return data.get("dat", {}).get("device", [])

    async def get_device_last_data(self, device_sn: str, device_pn: str, devcode: int = 0, devaddr: int = 0) -> dict[str, Any]:
        """Get latest data for a device."""
        try:
            data = await self._api_request(
                ACTION_QUERY_DEVICE_LAST_DATA,
                {"sn": device_sn, "pn": device_pn, "devcode": devcode, "devaddr": devaddr}
            )
            if data.get("desc") in ("ERR_NO_RECORD", "ERR_FORMAT_ERROR"):
                return {}
            return data.get("dat", {})
        except Exception as err:
            _LOGGER.debug("Failed to get device data for %s: %s", device_sn, err)
            return {}

    async def get_device_status(self, device_sn: str, device_pn: str, devcode: int = 0, devaddr: int = 0) -> str:
        """Get status of a device."""
        try:
            data = await self._api_request(
                ACTION_QUERY_DEVICE_STATUS,
                {"sn": device_sn, "pn": device_pn, "devcode": devcode, "devaddr": devaddr}
            )
            if data.get("desc") in ("ERR_NO_RECORD", "ERR_FORMAT_ERROR", "ERR_MISSING_PARAMETER"):
                return "unknown"
            return data.get("dat", {}).get("status", "unknown")
        except Exception as err:
            _LOGGER.debug("Failed to get device status for %s: %s", device_sn, err)
            return "unknown"

    async def get_collectors(self, plant_id: str) -> list[dict[str, Any]]:
        """Get list of dataloggers/collectors for a plant."""
        data = await self._api_request(
            ACTION_QUERY_COLLECTORS,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return []
        return data.get("dat", {}).get("collector", [])

    async def get_collector_status(self, collector_sn: str, collector_pn: str) -> str:
        """Get status of a datalogger."""
        try:
            data = await self._api_request(
                ACTION_QUERY_COLLECTOR_STATUS,
                {"sn": collector_sn, "pn": collector_pn}
            )
            if data.get("desc") in ("ERR_NO_RECORD", "ERR_FORMAT_ERROR"):
                return "unknown"
            return data.get("dat", {}).get("status", "unknown")
        except Exception as err:
            _LOGGER.debug("Failed to get collector status for %s: %s", collector_sn, err)
            return "unknown"

    async def get_energy_month_per_day(
        self, plant_id: str, year: int, month: int
    ) -> list[dict[str, Any]]:
        """Get daily energy for a specific month (for history import)."""
        # API expects date parameter in YYYY-MM format
        date_str = f"{year}-{month:02d}"
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_MONTH_PER_DAY,
            {"plantid": plant_id, "date": date_str}
        )
        _LOGGER.debug("Energy month per day response for %s: %s", date_str, data)
        if data.get("desc") == "ERR_NO_RECORD":
            return []
        # API returns dat.perday with val and ts fields
        dat = data.get("dat", {})
        return dat.get("perday", []) or dat.get("energy", []) or []

    async def get_energy_year_per_month(
        self, plant_id: str, year: int
    ) -> list[dict[str, Any]]:
        """Get monthly energy for a specific year (for history import)."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_YEAR_PER_MONTH,
            {"plantid": plant_id, "year": year}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return []
        return data.get("dat", {}).get("energy", [])

    async def get_energy_month(
        self, plant_id: str, year: int, month: int
    ) -> float:
        """Get total energy for a specific month from yearly per-month data."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_YEAR_PER_MONTH,
            {"plantid": plant_id, "date": str(year)}
        )
        _LOGGER.debug("get_energy_month response for %d: %s", year, data)
        
        if data.get("desc") == "ERR_NO_RECORD":
            return 0.0
        
        # Response contains permonth array with ts like "2024-12-01 00:00:00" and val (energy)
        monthly_data = data.get("dat", {}).get("permonth", [])
        _LOGGER.debug("permonth data: %s", monthly_data)
        
        for month_record in monthly_data:
            try:
                # ts field format: "2024-12-01 00:00:00"
                ts = str(month_record.get("ts", ""))
                month_val = month_record.get("val", 0)
                
                # Parse the month from ts - format is YYYY-MM-DD HH:MM:SS
                if ts:
                    date_part = ts.split(" ")[0]  # Get "2024-12-01"
                    parts = date_part.split("-")
                    if len(parts) >= 2:
                        record_month = int(parts[1])
                        if record_month == month:
                            _LOGGER.debug("Found month %d: val=%.1f", month, float(month_val))
                            return float(month_val)
            except (ValueError, TypeError, IndexError):
                continue
        
        _LOGGER.debug("Month %d not found in data", month)
        return 0.0

    async def get_power_one_day(
        self, plant_id: str, date: datetime.date
    ) -> list[dict[str, Any]]:
        """Get power readings for a specific day (for history import).
        
        Returns list of power readings with timestamps throughout the day.
        """
        from .const import ACTION_QUERY_PLANT_ACTIVE_OUTPUT_POWER_ONE_DAY
        
        date_str = date.strftime("%Y-%m-%d")
        data = await self._api_request(
            ACTION_QUERY_PLANT_ACTIVE_OUTPUT_POWER_ONE_DAY,
            {"plantid": plant_id, "date": date_str}
        )
        
        if data.get("desc") == "ERR_NO_RECORD":
            return []
        
        # API returns dat.power array with ts and val fields
        dat = data.get("dat", {})
        return dat.get("power", []) or dat.get("outputPower", []) or []


class ShineMonitorDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Shine Monitor data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ShineMonitorAPIClient,
        plant_id: str,
        plant_name: str,
    ) -> None:
        """Initialize the data update coordinator."""
        self.client = client
        self.plant_id = plant_id
        self.plant_name = plant_name
        self._enable_devices = entry.options.get(CONF_ENABLE_DEVICES, DEFAULT_ENABLE_DEVICES)
        
        # Track last known good values for cumulative sensors
        # This prevents statistics corruption when API errors return None
        self._last_total_energy: float | None = None
        self._last_yearly_energy: float | None = None
        self._last_monthly_energy: float | None = None
        
        # Get update interval from options or use default
        update_interval_minutes = entry.options.get("update_interval", 5)
        update_interval = timedelta(minutes=update_interval_minutes)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{plant_id}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the Shine Monitor API."""
        try:
            # Fetch plant-level data
            current_power = await self.client.get_current_power(self.plant_id)
            daily_energy = await self.client.get_daily_energy(self.plant_id)
            monthly_energy = await self.client.get_monthly_energy(self.plant_id)
            yearly_energy = await self.client.get_yearly_energy(self.plant_id)
            total_energy = await self.client.get_total_energy(self.plant_id)
            
            # For cumulative sensors (TOTAL_INCREASING), preserve last known good values
            # to prevent statistics corruption from API errors or temporary glitches
            if total_energy is not None:
                # Validate: total_energy should never decrease significantly (allow small fluctuations)
                if self._last_total_energy is not None and total_energy < self._last_total_energy * 0.9:
                    _LOGGER.warning(
                        "Total energy dropped from %.1f to %.1f kWh - keeping last known value to prevent statistics corruption",
                        self._last_total_energy, total_energy
                    )
                    total_energy = self._last_total_energy
                else:
                    self._last_total_energy = total_energy
            else:
                # API error - use last known value
                total_energy = self._last_total_energy
                if total_energy is None:
                    _LOGGER.warning("No total energy data available and no cached value")
            
            if yearly_energy is not None:
                if self._last_yearly_energy is not None and yearly_energy < self._last_yearly_energy * 0.9:
                    _LOGGER.warning(
                        "Yearly energy dropped from %.1f to %.1f kWh - keeping last known value",
                        self._last_yearly_energy, yearly_energy
                    )
                    yearly_energy = self._last_yearly_energy
                else:
                    self._last_yearly_energy = yearly_energy
            else:
                yearly_energy = self._last_yearly_energy
            
            if monthly_energy is not None:
                # Monthly resets at start of month, so only validate if we have a previous value
                # and it's not the first few days of the month
                if self._last_monthly_energy is not None and monthly_energy < self._last_monthly_energy * 0.5:
                    now = dt_util.now()
                    if now.day > 3:  # Only warn if not start of month
                        _LOGGER.warning(
                            "Monthly energy dropped from %.1f to %.1f kWh - keeping last known value",
                            self._last_monthly_energy, monthly_energy
                        )
                        monthly_energy = self._last_monthly_energy
                    else:
                        self._last_monthly_energy = monthly_energy
                else:
                    self._last_monthly_energy = monthly_energy
            else:
                monthly_energy = self._last_monthly_energy
            
            # Pass energy values for environmental calculations (use 0 if None for calculations)
            profit_data = await self.client.get_profit_data(self.plant_id, daily_energy or 0)
            total_profit_data = await self.client.get_total_profit_data(self.plant_id, total_energy or 0)
            warning_count = await self.client.get_warning_count(self.plant_id)
            unhandled_warning_count = await self.client.get_unhandled_warning_count(self.plant_id)
            alarm_summary = await self.client.get_alarm_summary(self.plant_id)
            installed_capacity = await self.client.get_installed_capacity(self.plant_id)

            data: dict[str, Any] = {
                DATA_CURRENT_POWER: current_power,
                DATA_DAILY_ENERGY: daily_energy,
                DATA_MONTHLY_ENERGY: monthly_energy,
                DATA_YEARLY_ENERGY: yearly_energy,
                DATA_TOTAL_ENERGY: total_energy,
                DATA_PROFIT: profit_data.get("profit", 0),
                DATA_COAL: profit_data.get("coal", 0),
                DATA_CO2: profit_data.get("co2", 0),
                DATA_SO2: profit_data.get("so2", 0),
                "total_profit": total_profit_data.get("profit", 0),
                "total_coal": total_profit_data.get("coal", 0),
                "total_co2": total_profit_data.get("co2", 0),
                "total_so2": total_profit_data.get("so2", 0),
                DATA_WARNING_COUNT: warning_count,
                "unhandled_warning_count": unhandled_warning_count,
                DATA_INVERTER_ALARMS: alarm_summary.get("unhandled_inverter", 0),
                DATA_GRID_ALARMS: alarm_summary.get("unhandled_grid", 0),
                "latest_inverter_alarm": alarm_summary.get("latest_inverter_alarm"),
                DATA_INSTALLED_CAPACITY: installed_capacity,
                DATA_LAST_UPDATED: dt_util.now().isoformat(),
            }

            # Fetch device-level data if enabled
            if self._enable_devices:
                devices = await self.client.get_devices(self.plant_id)
                device_data = []
                for device in devices:
                    device_sn = device.get("sn", "")
                    device_pn = device.get("pn", "")
                    devcode = device.get("devcode", 0)
                    devaddr = device.get("devaddr", 0)
                    if device_sn and device_pn:
                        last_data = await self.client.get_device_last_data(device_sn, device_pn, devcode, devaddr)
                        status = await self.client.get_device_status(device_sn, device_pn, devcode, devaddr)
                        device_data.append({
                            "sn": device_sn,
                            "pn": device_pn,
                            "name": device.get("name", device_sn),
                            "type": device.get("devType", ""),
                            "status": status,
                            "data": last_data,
                        })
                data[DATA_DEVICES] = device_data

                # Fetch datalogger data
                collectors = await self.client.get_collectors(self.plant_id)
                collector_data = []
                for collector in collectors:
                    collector_sn = collector.get("sn", "")
                    collector_pn = collector.get("pn", "")
                    if collector_sn and collector_pn:
                        status = await self.client.get_collector_status(collector_sn, collector_pn)
                        collector_data.append({
                            "sn": collector_sn,
                            "pn": collector_pn,
                            "name": collector.get("name", collector_sn),
                            "status": status,
                        })
                data[DATA_DATALOGGERS] = collector_data

            return data

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
