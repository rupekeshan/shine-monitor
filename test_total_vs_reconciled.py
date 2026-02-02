#!/usr/bin/env python3
"""
Test to compare:
1. queryPlantEnergyTotal - lifetime total from API
2. Sum of monthly totals from queryPlantEnergyYearPerMonth
3. Sum of all daily data from queryPlantEnergyMonthPerDay
4. Reconciled sum (monthly totals used as source of truth)

This helps decide if we can just use queryPlantEnergyTotal instead of reconciliation.

Usage:
    $env:SHINE_USERNAME = "your_username"
    $env:SHINE_PASSWORD = "your_password"  
    $env:SHINE_COMPANY_KEY = "your_company_key"
    uv run test_total_vs_reconciled.py
"""
import asyncio
import sys
import os
import hashlib
import time
from datetime import datetime
import calendar

import aiohttp

API_BASE_URL = "http://api.shinemonitor.com/public/"


class ShineMonitorAPIClient:
    """API Client for testing."""

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
            return data["dat"]

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

    async def get_total_energy(self, plant_id):
        """Get lifetime total energy from API."""
        data = await self._api_request("queryPlantEnergyTotal", {"plantid": plant_id})
        if data.get("err") != 0:
            return 0.0
        return float(data.get("dat", {}).get("energy", 0))

    async def get_energy_year_per_month(self, plant_id, year):
        """Get monthly breakdown for a year."""
        data = await self._api_request("queryPlantEnergyYearPerMonth", {"plantid": plant_id, "date": str(year)})
        if data.get("err") != 0:
            return []
        return data.get("dat", {}).get("permonth", [])

    async def get_energy_month_per_day(self, plant_id, year, month):
        """Get daily breakdown for a month."""
        date_str = f"{year}-{month:02d}"
        data = await self._api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "date": date_str})
        if data.get("err") != 0:
            return []
        return data.get("dat", {}).get("perday", [])


async def main():
    username = os.environ.get("SHINE_USERNAME", "")  
    password = os.environ.get("SHINE_PASSWORD", "")
    company_key = os.environ.get("SHINE_COMPANY_KEY", "")
    
    if not all([username, password, company_key]):
        print("Credentials not found in environment. Please enter:")
        username = input("Username (email): ").strip()
        password = input("Password: ").strip()  
        company_key = input("Company Key: ").strip()
        
    if not all([username, password, company_key]):
        print("Error: All credentials are required")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("Total Energy API vs Reconciled Sum Comparison")
    print("=" * 80)

    async with aiohttp.ClientSession() as session:
        client = ShineMonitorAPIClient(session, username, password, company_key)
        
        print("\n[1] Authenticating...")
        await client.authenticate()
        print("    ✓ Authenticated")

        plants = await client.get_plants()
        if not plants:
            print("    ✗ No plants found")
            return

        plant_id = str(plants[0].get("pid"))
        plant_name = plants[0].get("name", "Unknown")
        print(f"    Using plant: {plant_name} (ID: {plant_id})")

        # Get API total
        print("\n[2] Getting Total Energy from API (queryPlantEnergyTotal)...")
        api_total = await client.get_total_energy(plant_id)
        print(f"    API Total: {api_total:.2f} kWh")

        # Calculate sum of monthly totals
        print("\n[3] Calculating sum of Monthly Totals...")
        now = datetime.now()
        monthly_sum = 0.0
        monthly_breakdown = {}
        
        for year in range(2015, now.year + 1):
            monthly_data = await client.get_energy_year_per_month(plant_id, year)
            year_sum = 0.0
            for m in monthly_data:
                ts = m.get("ts", "")
                val = float(m.get("val", 0))
                if ts and val > 0:
                    try:
                        ts_year = int(ts.split("-")[0])
                        ts_month = int(ts.split("-")[1].split(" ")[0])
                        if ts_year == year:
                            year_sum += val
                            monthly_breakdown[f"{year}-{ts_month:02d}"] = val
                    except (ValueError, IndexError):
                        pass
            if year_sum > 0:
                monthly_sum += year_sum
                print(f"    Year {year}: {year_sum:.2f} kWh")
        
        print(f"    Monthly Sum Total: {monthly_sum:.2f} kWh")

        # Calculate sum of daily totals
        print("\n[4] Calculating sum of Daily Totals (this may take a while)...")
        daily_sum = 0.0
        daily_by_month = {}
        
        for year in range(2015, now.year + 1):
            for month in range(1, 13):
                # Skip future months
                if year == now.year and month > now.month:
                    continue
                    
                daily_data = await client.get_energy_month_per_day(plant_id, year, month)
                month_daily_sum = 0.0
                for d in daily_data:
                    val = float(d.get("val", 0))
                    month_daily_sum += val
                
                if month_daily_sum > 0:
                    daily_sum += month_daily_sum
                    key = f"{year}-{month:02d}"
                    daily_by_month[key] = month_daily_sum
                    
                    # Compare with monthly total
                    monthly_val = monthly_breakdown.get(key, 0)
                    diff = monthly_val - month_daily_sum
                    if abs(diff) > 0.5:
                        print(f"    {key}: daily={month_daily_sum:.1f}, monthly={monthly_val:.1f}, diff={diff:+.1f} ⚠️")

        print(f"    Daily Sum Total: {daily_sum:.2f} kWh")

        # Summary
        print("\n" + "=" * 80)
        print("COMPARISON SUMMARY")
        print("=" * 80)
        print(f"\n{'Source':<35} {'Value (kWh)':>15}")
        print("-" * 55)
        print(f"{'1. API Total (queryPlantEnergyTotal)':<35} {api_total:>15.2f}")
        print(f"{'2. Sum of Monthly Totals':<35} {monthly_sum:>15.2f}")
        print(f"{'3. Sum of Daily Totals':<35} {daily_sum:>15.2f}")
        print("-" * 55)

        diff_api_monthly = api_total - monthly_sum
        diff_api_daily = api_total - daily_sum
        diff_monthly_daily = monthly_sum - daily_sum

        print(f"\n{'Differences:'}")
        print(f"  API Total - Monthly Sum:  {diff_api_monthly:+.2f} kWh ({diff_api_monthly/api_total*100:+.2f}%)")
        print(f"  API Total - Daily Sum:    {diff_api_daily:+.2f} kWh ({diff_api_daily/api_total*100:+.2f}%)")
        print(f"  Monthly Sum - Daily Sum:  {diff_monthly_daily:+.2f} kWh ({diff_monthly_daily/monthly_sum*100 if monthly_sum else 0:+.2f}%)")

        print("\n" + "=" * 80)
        print("RECOMMENDATION")
        print("=" * 80)
        
        if abs(diff_api_monthly) < 10 and abs(diff_api_daily) < 50:
            print("\n✓ API Total is consistent with calculated sums!")
            print("  You could potentially use queryPlantEnergyTotal directly.")
            print("  However, it won't give you daily breakdown for historical graphs.")
        else:
            print("\n⚠️ Significant discrepancy detected!")
            print("  Continue using reconciliation logic to ensure accuracy.")
            
        if abs(diff_monthly_daily) > 10:
            print(f"\n⚠️ Monthly and Daily APIs differ by {diff_monthly_daily:.1f} kWh")
            print("  Reconciliation is needed to match daily data to monthly totals.")
        
        print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
