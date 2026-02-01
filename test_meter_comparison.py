#!/usr/bin/env python3
"""
Compare Shine Monitor data with actual electricity meter readings.
Bi-monthly meter data is compared against both daily sums and monthly API totals.
"""
import asyncio
import sys
import os
import hashlib
import time
from datetime import datetime
from typing import Any

import aiohttp

API_BASE_URL = "http://api.shinemonitor.com/public/"

# Actual meter data - bi-monthly export readings (2 months combined)
# Format: "Bill Period" -> (month1, year1, month2, year2, meter_reading)
METER_DATA = [
    ("May-24", 4, 2024, 5, 2024, 322),   # Apr-May 2024
    ("Jul-24", 6, 2024, 7, 2024, 632),   # Jun-Jul 2024
    ("Sep-24", 8, 2024, 9, 2024, 593),   # Aug-Sep 2024
    ("Nov-24", 10, 2024, 11, 2024, 488), # Oct-Nov 2024
    ("Jan-25", 12, 2024, 1, 2025, 466),  # Dec 2024 - Jan 2025
    ("Mar-25", 2, 2025, 3, 2025, 483),   # Feb-Mar 2025
    ("May-25", 4, 2025, 5, 2025, 594),   # Apr-May 2025
    ("Jul-25", 6, 2025, 7, 2025, 532),   # Jun-Jul 2025
    ("Sep-25", 8, 2025, 9, 2025, 210),   # Aug-Sep 2025
    ("Nov-25", 10, 2025, 11, 2025, 152), # Oct-Nov 2025
    ("Jan-26", 12, 2025, 1, 2026, 344),  # Dec 2025 - Jan 2026
]


class ShineMonitorAPIClient:
    def __init__(self, session, username, password, company_key):
        self._session = session
        self._username = username
        self._password = password
        self._company_key = company_key
        self._token = None
        self._secret = None

    def _generate_salt(self):
        return str(int(time.time() * 1000))

    def _generate_auth_signature(self, salt, action):
        hashed_password = hashlib.sha1(self._password.encode("utf-8")).hexdigest()
        sign_string = salt + hashed_password + action
        return hashlib.sha1(sign_string.encode("utf-8")).hexdigest()

    def _generate_data_signature(self, salt, action):
        sign_string = salt + self._secret + self._token + action
        return hashlib.sha1(sign_string.encode("utf-8")).hexdigest()

    async def authenticate(self):
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

    async def _api_request(self, action, params=None):
        salt = self._generate_salt()
        action_str = f"&action={action}"
        if params:
            for key, value in params.items():
                action_str += f"&{key}={value}"
        sign = self._generate_data_signature(salt, action_str)
        url = f"{API_BASE_URL}?sign={sign}&token={self._token}&salt={salt}{action_str}"
        async with self._session.get(url) as response:
            return await response.json()

    async def get_plants(self):
        data = await self._api_request("queryPlants")
        return data.get("dat", {}).get("plant", [])

    async def get_energy_month_per_day(self, plant_id, year, month):
        date_str = f"{year}-{month:02d}"
        data = await self._api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "date": date_str})
        if data.get("err") != 0:
            return []
        return data.get("dat", {}).get("perday", [])

    async def get_monthly_energy(self, plant_id, year, month):
        """Get monthly total from API."""
        date_str = f"{year}-{month:02d}"
        data = await self._api_request("queryPlantEnergyMonth", {"plantid": plant_id, "date": date_str})
        if data.get("err") != 0:
            return 0.0
        return float(data.get("dat", {}).get("energy", 0))


async def compare_with_meter(username, password, company_key):
    print("\n" + "=" * 100)
    print("SHINE MONITOR vs ACTUAL METER DATA COMPARISON")
    print("=" * 100)

    async with aiohttp.ClientSession() as session:
        client = ShineMonitorAPIClient(session, username, password, company_key)
        
        await client.authenticate()
        print("\n✓ Authenticated")

        plants = await client.get_plants()
        plant_id = str(plants[0].get("pid"))
        print(f"✓ Using plant: {plants[0].get('name')} (ID: {plant_id})")

        print("\n" + "-" * 100)
        print(f"{'Bill Period':<12} {'Months':<20} {'Meter':>10} {'Daily Sum':>12} {'Monthly API':>12} {'Daily Diff':>12} {'API Diff':>12}")
        print("-" * 100)

        total_meter = 0
        total_daily = 0
        total_monthly_api = 0

        for bill_period, m1, y1, m2, y2, meter_reading in METER_DATA:
            # Get daily sums for both months
            daily_m1 = await client.get_energy_month_per_day(plant_id, y1, m1)
            daily_m2 = await client.get_energy_month_per_day(plant_id, y2, m2)
            
            daily_sum_m1 = sum(float(d.get("val", 0)) for d in daily_m1)
            daily_sum_m2 = sum(float(d.get("val", 0)) for d in daily_m2)
            daily_total = daily_sum_m1 + daily_sum_m2

            # Get monthly API totals
            monthly_api_m1 = await client.get_monthly_energy(plant_id, y1, m1)
            monthly_api_m2 = await client.get_monthly_energy(plant_id, y2, m2)
            monthly_api_total = monthly_api_m1 + monthly_api_m2

            # Calculate differences
            daily_diff = daily_total - meter_reading
            api_diff = monthly_api_total - meter_reading

            # Format month names
            import calendar
            months_str = f"{calendar.month_abbr[m1]}-{y1 % 100:02d} + {calendar.month_abbr[m2]}-{y2 % 100:02d}"

            # Markers for accuracy
            daily_marker = "✓" if abs(daily_diff) <= 10 else "⚠️" if abs(daily_diff) <= 30 else "❌"
            api_marker = "✓" if abs(api_diff) <= 10 else "⚠️" if abs(api_diff) <= 30 else "❌"

            print(f"{bill_period:<12} {months_str:<20} {meter_reading:>10.0f} {daily_total:>12.1f} {monthly_api_total:>12.1f} {daily_diff:>+10.1f} {daily_marker} {api_diff:>+10.1f} {api_marker}")

            total_meter += meter_reading
            total_daily += daily_total
            total_monthly_api += monthly_api_total

        print("-" * 100)
        total_daily_diff = total_daily - total_meter
        total_api_diff = total_monthly_api - total_meter
        print(f"{'TOTALS':<12} {'':<20} {total_meter:>10.0f} {total_daily:>12.1f} {total_monthly_api:>12.1f} {total_daily_diff:>+10.1f}    {total_api_diff:>+10.1f}")

        # Summary
        print("\n" + "=" * 100)
        print("ANALYSIS SUMMARY")
        print("=" * 100)
        
        daily_accuracy = 100 * (1 - abs(total_daily_diff) / total_meter)
        api_accuracy = 100 * (1 - abs(total_api_diff) / total_meter)
        
        print(f"\n{'Data Source':<25} {'Total (kWh)':>15} {'Difference':>15} {'Accuracy':>15}")
        print("-" * 70)
        print(f"{'Actual Meter':<25} {total_meter:>15.0f} {'-':>15} {'100%':>15}")
        print(f"{'Shine Daily Sum':<25} {total_daily:>15.1f} {total_daily_diff:>+15.1f} {daily_accuracy:>14.1f}%")
        print(f"{'Shine Monthly API':<25} {total_monthly_api:>15.1f} {total_api_diff:>+15.1f} {api_accuracy:>14.1f}%")

        print("\n" + "-" * 70)
        if abs(total_api_diff) < abs(total_daily_diff):
            print("🏆 WINNER: Monthly API data is closer to actual meter readings!")
            print("   Recommendation: Use monthly totals for historical data import.")
        else:
            print("🏆 WINNER: Daily sum data is closer to actual meter readings!")
            print("   Recommendation: Use daily data for historical import.")

        print("\n" + "=" * 100)


def main():
    username = os.environ.get("SHINE_USERNAME", "")
    password = os.environ.get("SHINE_PASSWORD", "")
    company_key = os.environ.get("SHINE_COMPANY_KEY", "")
    
    if not all([username, password, company_key]):
        print("Set environment variables: SHINE_USERNAME, SHINE_PASSWORD, SHINE_COMPANY_KEY")
        sys.exit(1)
    
    asyncio.run(compare_with_meter(username, password, company_key))


if __name__ == "__main__":
    main()
