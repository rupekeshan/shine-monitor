#!/usr/bin/env python3
"""
Test script for Shine Monitor API client.
Run this to verify your credentials and API connectivity without Home Assistant.

Usage:
    pip install aiohttp
    python test_api.py
"""
import asyncio
import sys
import os

# Add the custom_components directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiohttp

# Import the API client (standalone version below if import fails)
try:
    from custom_components.shine_monitor.coordinator import ShineMonitorAPIClient
    print("✓ Using API client from custom_components")
except ImportError:
    print("⚠ Could not import from custom_components, using embedded client")
    import hashlib
    import time
    from typing import Any

    API_BASE_URL = "http://api.shinemonitor.com/public/"

    class ShineMonitorAPIClient:
        """Standalone API Client for testing."""

        def __init__(
            self,
            session: aiohttp.ClientSession,
            username: str,
            password: str,
            company_key: str,
        ) -> None:
            self._session = session
            self._username = username
            self._password = password
            self._company_key = company_key
            self._token: str | None = None
            self._secret: str | None = None

        @property
        def token(self) -> str | None:
            return self._token

        @property
        def secret(self) -> str | None:
            return self._secret

        def _generate_salt(self) -> str:
            return str(int(time.time() * 1000))

        def _generate_auth_signature(self, salt: str, action: str) -> str:
            hashed_password = hashlib.sha1(self._password.encode("utf-8")).hexdigest()
            sign_string = salt + hashed_password + action
            return hashlib.sha1(sign_string.encode("utf-8")).hexdigest()

        def _generate_data_signature(self, salt: str, action: str) -> str:
            sign_string = salt + self._secret + self._token + action
            return hashlib.sha1(sign_string.encode("utf-8")).hexdigest()

        async def authenticate(self) -> dict[str, Any]:
            salt = self._generate_salt()
            action = f"&action=auth&usr={self._username}&company-key={self._company_key}"
            sign = self._generate_auth_signature(salt, action)
            url = f"{API_BASE_URL}?sign={sign}&salt={salt}{action}"

            async with self._session.get(url) as response:
                data = await response.json()
                if data.get("err") != 0:
                    raise Exception(f"Authentication failed: {data.get('desc')}")
                self._token = data["dat"]["token"]
                self._secret = data["dat"]["secret"]
                return data["dat"]

        async def _api_request(self, action: str, params: dict | None = None) -> dict:
            salt = self._generate_salt()
            action_str = f"&action={action}"
            if params:
                for key, value in params.items():
                    action_str += f"&{key}={value}"
            sign = self._generate_data_signature(salt, action_str)
            url = f"{API_BASE_URL}?sign={sign}&token={self._token}&salt={salt}{action_str}"
            async with self._session.get(url) as response:
                return await response.json()

        async def get_plants(self) -> list:
            data = await self._api_request("queryPlants")
            return data.get("dat", {}).get("plant", [])

        async def get_current_power(self, plant_id: str) -> float:
            data = await self._api_request("queryPlantsActiveOuputPowerCurrent", {"plantid": plant_id})
            if data.get("desc") == "ERR_NO_RECORD":
                return 0.0
            return float(data.get("dat", {}).get("outputPower", 0))

        async def get_daily_energy(self, plant_id: str) -> float:
            data = await self._api_request("queryPlantEnergyDay", {"plantid": plant_id})
            if data.get("desc") == "ERR_NO_RECORD":
                return 0.0
            return float(data.get("dat", {}).get("energy", 0))

        async def get_total_energy(self, plant_id: str) -> float:
            data = await self._api_request("queryPlantEnergyTotal", {"plantid": plant_id})
            if data.get("desc") == "ERR_NO_RECORD":
                return 0.0
            return float(data.get("dat", {}).get("energy", 0))

        async def get_devices(self, plant_id: str) -> list:
            data = await self._api_request("queryDevices", {"plantid": plant_id})
            if data.get("desc") == "ERR_NO_RECORD":
                return []
            return data.get("dat", {}).get("device", [])

        async def get_energy_month_per_day(self, plant_id: str, year: int, month: int) -> dict:
            """Get raw response for debugging."""
            # Try different parameter formats
            data = await self._api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "year": year, "month": month})
            return data

        async def get_energy_month_per_day_v2(self, plant_id: str, year: int, month: int) -> dict:
            """Try with date parameter."""
            date_str = f"{year}-{month:02d}"
            data = await self._api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "date": date_str})
            return data

        async def get_energy_month_per_day_v3(self, plant_id: str, year: int, month: int) -> dict:
            """Try with mon parameter."""
            data = await self._api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "year": year, "mon": month})
            return data


async def test_api(username: str, password: str, company_key: str):
    """Test the Shine Monitor API."""
    print("\n" + "=" * 60)
    print("Shine Monitor API Test")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        client = ShineMonitorAPIClient(
            session=session,
            username=username,
            password=password,
            company_key=company_key,
        )

        # Test 1: Authentication
        print("\n[1/5] Testing authentication...")
        try:
            auth_data = await client.authenticate()
            print(f"  ✓ Authentication successful!")
            print(f"    Token: {client.token[:20]}..." if client.token else "    Token: None")
        except Exception as e:
            print(f"  ✗ Authentication failed: {e}")
            return

        # Test 2: Get plants
        print("\n[2/5] Fetching plants...")
        try:
            plants = await client.get_plants()
            if plants:
                print(f"  ✓ Found {len(plants)} plant(s):")
                for plant in plants:
                    print(f"    - {plant.get('name', 'Unknown')} (ID: {plant.get('pid')})")
            else:
                print("  ⚠ No plants found")
                return
        except Exception as e:
            print(f"  ✗ Failed to fetch plants: {e}")
            return

        # Use first plant for remaining tests
        plant_id = str(plants[0].get("pid"))
        plant_name = plants[0].get("name", "Unknown")
        print(f"\n  Using plant: {plant_name} (ID: {plant_id})")

        # Test 3: Current power
        print("\n[3/5] Fetching current power...")
        try:
            power = await client.get_current_power(plant_id)
            print(f"  ✓ Current Power: {power} kW")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

        # Test 4: Energy data
        print("\n[4/5] Fetching energy data...")
        try:
            daily = await client.get_daily_energy(plant_id)
            total = await client.get_total_energy(plant_id)
            print(f"  ✓ Daily Energy: {daily} kWh")
            print(f"  ✓ Total Energy: {total} kWh")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

        # Test 5: Devices
        print("\n[5/6] Fetching devices...")
        try:
            devices = await client.get_devices(plant_id)
            if devices:
                print(f"  ✓ Found {len(devices)} device(s):")
                for device in devices:
                    print(f"    - {device.get('name', 'Unknown')} (SN: {device.get('sn')})")
            else:
                print("  ⚠ No devices found")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

        # Test 6: Debug problematic endpoints
        print("\n[6/6] Debugging API responses...")
        try:
            # Test warning count
            print("\n  Warning Count API:")
            warn_data = await client._api_request("queryPlantWarningCount", {"plantid": plant_id})
            print(f"    Response: {warn_data}")
            
            # Test warning count with status filter
            print("\n  Warning Count (status=0 - unhandled):")
            warn_unhandled = await client._api_request("queryPlantWarningCount", {"plantid": plant_id, "status": 0})
            print(f"    Response: {warn_unhandled}")
            
            print("\n  Warning Count (status=1 - handled):")
            warn_handled = await client._api_request("queryPlantWarningCount", {"plantid": plant_id, "status": 1})
            print(f"    Response: {warn_handled}")
            
            # Test warning list to see structure
            print("\n  Warning List API (first 3):")
            warn_list = await client._api_request("queryPlantWarning", {"plantid": plant_id, "pagesize": 3})
            print(f"    Response: {warn_list}")
            
            # Test total profit/environmental data
            print("\n  Total Profit API (queryPlantsProfit):")
            profit_data = await client._api_request("queryPlantsProfit", {"plantid": plant_id})
            print(f"    Response: {profit_data}")
            
            # Test daily profit
            print("\n  Daily Profit API (queryPlantsProfitOneDay):")
            daily_profit = await client._api_request("queryPlantsProfitOneDay", {"plantid": plant_id})
            print(f"    Response: {daily_profit}")
            
            # Test installed capacity
            print("\n  Nominal Power API (queryPlantsNominalPower):")
            capacity = await client._api_request("queryPlantsNominalPower", {"plantid": plant_id})
            print(f"    Response: {capacity}")
            
            # Test hourly/minute power data
            print("\n  --- Testing Power/Energy Granularity ---")
            
            # Try power per hour for today
            import datetime
            today = datetime.date.today().isoformat()
            
            # From API docs: queryPlantActiveOuputPowerOneDay
            print(f"\n  Active Output Power One Day (queryPlantActiveOuputPowerOneDay) date={today}:")
            power_oneday = await client._api_request("queryPlantActiveOuputPowerOneDay", {"plantid": plant_id, "date": today})
            print(f"    Response: {power_oneday}")
            
            # Also try queryPlantsActiveOuputPowerOneDay (with 's')
            print(f"\n  Plants Active Output Power One Day (queryPlantsActiveOuputPowerOneDay) date={today}:")
            power_oneday2 = await client._api_request("queryPlantsActiveOuputPowerOneDay", {"plantid": plant_id, "date": today})
            print(f"    Response: {power_oneday2}")
            
            print(f"\n  Power Per Hour (queryPlantPowerDayPerHour) date={today}:")
            power_hour = await client._api_request("queryPlantPowerDayPerHour", {"plantid": plant_id, "date": today})
            print(f"    Response: {power_hour}")
            
            print(f"\n  Power Per Minute (queryPlantPowerHourPerMinute) date={today} hour=12:")
            power_min = await client._api_request("queryPlantPowerHourPerMinute", {"plantid": plant_id, "date": today, "hour": 12})
            print(f"    Response: {power_min}")
            
            print(f"\n  Energy Per Hour (queryPlantEnergyDayPerHour) date={today}:")
            energy_hour = await client._api_request("queryPlantEnergyDayPerHour", {"plantid": plant_id, "date": today})
            print(f"    Response: {energy_hour}")
            
            # Also test output power history
            print(f"\n  Output Power History (queryPlantsOutputPowerHistory) date={today}:")
            power_hist = await client._api_request("queryPlantsOutputPowerHistory", {"plantid": plant_id, "date": today})
            print(f"    Response: {power_hist}")
            
            # Try per-day data for current month
            year = datetime.date.today().year
            month = datetime.date.today().month
            print(f"\n  Energy per day (queryPlantEnergyMonthPerDay) date={year}-{month:02d}:")
            energy_day = await client._api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "date": f"{year}-{month:02d}"})
            print(f"    Response: {energy_day}")
                
        except Exception as e:
            import traceback
            print(f"  ✗ Failed: {e}")
            traceback.print_exc()

        print("\n" + "=" * 60)
        print("API Test Complete!")
        print("=" * 60 + "\n")


def main():
    """Main entry point."""
    print("\nShine Monitor API Tester")
    print("-" * 40)
    
    # Check for environment variables first
    username = os.environ.get("SHINE_USERNAME", "")
    password = os.environ.get("SHINE_PASSWORD", "")
    company_key = os.environ.get("SHINE_COMPANY_KEY", "")
    
    if username and password and company_key:
        print("Using credentials from environment variables")
    else:
        print("Enter your Shine Monitor credentials:\n")
        username = input("Username (email): ").strip()
        password = input("Password: ").strip()
        company_key = input("Company Key: ").strip()
    
    if not all([username, password, company_key]):
        print("\n✗ All fields are required!")
        sys.exit(1)
    
    asyncio.run(test_api(username, password, company_key))


if __name__ == "__main__":
    main()
