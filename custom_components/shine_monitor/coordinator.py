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
                
                if data.get("err") != 0 and data.get("desc") != "ERR_NO_RECORD":
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

    async def get_monthly_energy(self, plant_id: str) -> float:
        """Get monthly energy production."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_MONTH,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0.0
        return float(data.get("dat", {}).get("energy", 0))

    async def get_yearly_energy(self, plant_id: str) -> float:
        """Get yearly energy production."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_YEAR,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0.0
        return float(data.get("dat", {}).get("energy", 0))

    async def get_total_energy(self, plant_id: str) -> float:
        """Get total energy production."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_TOTAL,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0.0
        return float(data.get("dat", {}).get("energy", 0))

    async def get_profit_data(self, plant_id: str) -> dict[str, float]:
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
            return {
                "profit": float(plant_data.get("profit", 0)),
                "coal": float(plant_data.get("coal", 0)),
                "co2": float(plant_data.get("co2", 0)),
                "so2": float(plant_data.get("so2", 0)),
            }
        return {"profit": 0, "coal": 0, "co2": 0, "so2": 0}

    async def get_total_profit_data(self, plant_id: str) -> dict[str, float]:
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
            return {
                "profit": float(plant_data.get("profit", 0)),
                "coal": float(plant_data.get("coal", 0)),
                "co2": float(plant_data.get("co2", 0)),
                "so2": float(plant_data.get("so2", 0)),
            }
        return {"profit": 0, "coal": 0, "co2": 0, "so2": 0}

    async def get_warning_count(self, plant_id: str) -> int:
        """Get alarm/warning count for plant."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_WARNING_COUNT,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0
        return int(data.get("dat", {}).get("count", 0))

    async def get_installed_capacity(self, plant_id: str) -> float:
        """Get installed capacity (nominal power) for plant."""
        data = await self._api_request(
            ACTION_QUERY_PLANTS_NOMINAL_POWER,
            {"plantid": plant_id}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return 0.0
        plants = data.get("dat", {}).get("plant", [])
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

    async def get_device_last_data(self, device_sn: str, device_pn: str) -> dict[str, Any]:
        """Get latest data for a device."""
        data = await self._api_request(
            ACTION_QUERY_DEVICE_LAST_DATA,
            {"sn": device_sn, "pn": device_pn}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return {}
        return data.get("dat", {})

    async def get_device_status(self, device_sn: str, device_pn: str) -> str:
        """Get status of a device."""
        data = await self._api_request(
            ACTION_QUERY_DEVICE_STATUS,
            {"sn": device_sn, "pn": device_pn}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return "unknown"
        return data.get("dat", {}).get("status", "unknown")

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
        data = await self._api_request(
            ACTION_QUERY_COLLECTOR_STATUS,
            {"sn": collector_sn, "pn": collector_pn}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return "unknown"
        return data.get("dat", {}).get("status", "unknown")

    async def get_energy_month_per_day(
        self, plant_id: str, year: int, month: int
    ) -> list[dict[str, Any]]:
        """Get daily energy for a specific month (for history import)."""
        data = await self._api_request(
            ACTION_QUERY_PLANT_ENERGY_MONTH_PER_DAY,
            {"plantid": plant_id, "year": year, "month": month}
        )
        if data.get("desc") == "ERR_NO_RECORD":
            return []
        return data.get("dat", {}).get("energy", [])

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
            profit_data = await self.client.get_profit_data(self.plant_id)
            total_profit_data = await self.client.get_total_profit_data(self.plant_id)
            warning_count = await self.client.get_warning_count(self.plant_id)
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
                    if device_sn and device_pn:
                        last_data = await self.client.get_device_last_data(device_sn, device_pn)
                        status = await self.client.get_device_status(device_sn, device_pn)
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
