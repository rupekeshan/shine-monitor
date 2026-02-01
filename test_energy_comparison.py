#!/usr/bin/env python3
"""
Test script to compare Daily, Monthly, and Yearly energy data from Shine Monitor API.
This helps identify discrepancies between different API endpoints.

Usage:
    $env:SHINE_USERNAME = "your_username"
    $env:SHINE_PASSWORD = "your_password"
    $env:SHINE_COMPANY_KEY = "your_company_key"
    uv run test_energy_comparison.py
"""
import asyncio
import sys
import os
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any
import calendar

import aiohttp

API_BASE_URL = "http://api.shinemonitor.com/public/"


class ShineMonitorAPIClient:
    """API Client for testing."""

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

    async def get_energy_month_per_day(self, plant_id: str, year: int, month: int) -> list:
        """Get daily energy for a specific month."""
        date_str = f"{year}-{month:02d}"
        data = await self._api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "date": date_str})
        if data.get("err") != 0:
            return []
        return data.get("dat", {}).get("perday", [])

    async def get_energy_year_per_month(self, plant_id: str, year: int) -> dict:
        """Get raw monthly energy response for a year."""
        # Try with year parameter
        data = await self._api_request("queryPlantEnergyYearPerMonth", {"plantid": plant_id, "year": year})
        return data
    
    async def get_energy_year_per_month_v2(self, plant_id: str, year: int) -> dict:
        """Try with date parameter."""
        data = await self._api_request("queryPlantEnergyYearPerMonth", {"plantid": plant_id, "date": str(year)})
        return data

    async def get_total_energy(self, plant_id: str) -> float:
        """Get total lifetime energy."""
        data = await self._api_request("queryPlantEnergyTotal", {"plantid": plant_id})
        if data.get("err") != 0:
            return 0.0
        return float(data.get("dat", {}).get("energy", 0))
    
    async def get_energy_month(self, plant_id: str, year: int, month: int) -> dict:
        """Get energy for a specific month directly."""
        date_str = f"{year}-{month:02d}"
        data = await self._api_request("queryPlantEnergyMonth", {"plantid": plant_id, "date": date_str})
        return data
    
    async def get_energy_year(self, plant_id: str, year: int) -> dict:
        """Get energy for a specific year directly."""
        data = await self._api_request("queryPlantEnergyYear", {"plantid": plant_id, "year": year})
        return data


async def compare_energy_data(username: str, password: str, company_key: str):
    """Compare energy data from different API endpoints."""
    print("\n" + "=" * 80)
    print("Shine Monitor Energy Data Comparison")
    print("=" * 80)

    async with aiohttp.ClientSession() as session:
        client = ShineMonitorAPIClient(
            session=session,
            username=username,
            password=password,
            company_key=company_key,
        )

        # Authenticate
        print("\n[1] Authenticating...")
        await client.authenticate()
        print("    ✓ Authenticated")

        # Get plants
        plants = await client.get_plants()
        if not plants:
            print("    ✗ No plants found")
            return

        plant_id = str(plants[0].get("pid"))
        plant_name = plants[0].get("name", "Unknown")
        print(f"    Using plant: {plant_name} (ID: {plant_id})")

        # Get total energy for reference
        total_energy = await client.get_total_energy(plant_id)
        print(f"\n[2] Total Energy from API: {total_energy:.2f} kWh")

        # Analyze last 2 years
        now = datetime.now()
        start_year = now.year - 2
        
        print(f"\n[3] Analyzing data from {start_year} to {now.year}...")
        print("-" * 80)

        grand_total_from_daily = 0.0
        grand_total_from_monthly = 0.0
        yearly_totals = {}

        for year in range(start_year, now.year + 1):
            print(f"\n{'='*40}")
            print(f"YEAR: {year}")
            print(f"{'='*40}")

            # Get monthly data from API - try both parameter formats
            yearly_response = await client.get_energy_year_per_month(plant_id, year)
            yearly_response_v2 = await client.get_energy_year_per_month_v2(plant_id, year)
            print(f"\nYearly API (year={year}): {yearly_response}")
            print(f"Yearly API (date={year}): {yearly_response_v2}")

            monthly_api_data = {}
            # Parse response - it uses 'ts' for timestamp and 'val' for value
            best_response = yearly_response_v2 if yearly_response_v2.get("err") == 0 else yearly_response
            if best_response.get("err") == 0:
                permonth = best_response.get("dat", {}).get("permonth", [])
                for m in permonth:
                    # Parse timestamp to get month
                    ts = m.get("ts", "")
                    if ts:
                        try:
                            ts_year = int(ts.split("-")[0])
                            ts_month = int(ts.split("-")[1])
                            # Only use data matching the requested year
                            if ts_year == year:
                                month_val = float(m.get("val", 0))
                                monthly_api_data[ts_month] = month_val
                        except (ValueError, IndexError):
                            pass

            year_sum_daily = 0.0
            year_sum_monthly_api = 0.0
            
            print(f"\n{'Month':<12} {'Daily Sum':>12} {'Monthly API':>12} {'Difference':>12}")
            print("-" * 50)

            for month in range(1, 13):
                # Skip future months
                if year == now.year and month > now.month:
                    continue

                # Get daily data for this month
                daily_data = await client.get_energy_month_per_day(plant_id, year, month)
                
                # Sum up daily values
                daily_sum = 0.0
                for day in daily_data:
                    val = float(day.get("val", 0))
                    daily_sum += val
                
                # Get monthly value from API
                monthly_api_val = monthly_api_data.get(month, 0.0)
                
                # Calculate difference
                diff = monthly_api_val - daily_sum
                
                month_name = calendar.month_abbr[month]
                
                if daily_sum > 0 or monthly_api_val > 0:
                    diff_str = f"{diff:+.2f}" if diff != 0 else "0.00"
                    marker = " ⚠️" if abs(diff) > 0.5 else ""
                    print(f"{month_name:<12} {daily_sum:>12.2f} {monthly_api_val:>12.2f} {diff_str:>12}{marker}")
                
                year_sum_daily += daily_sum
                year_sum_monthly_api += monthly_api_val

            print("-" * 50)
            year_diff = year_sum_monthly_api - year_sum_daily
            diff_str = f"{year_diff:+.2f}" if year_diff != 0 else "0.00"
            marker = " ⚠️" if abs(year_diff) > 0.5 else ""
            print(f"{'YEAR TOTAL':<12} {year_sum_daily:>12.2f} {year_sum_monthly_api:>12.2f} {diff_str:>12}{marker}")

            grand_total_from_daily += year_sum_daily
            grand_total_from_monthly += year_sum_monthly_api
            yearly_totals[year] = {
                "daily_sum": year_sum_daily,
                "monthly_api": year_sum_monthly_api,
            }

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"\n{'Source':<30} {'Value (kWh)':>15}")
        print("-" * 50)
        print(f"{'Total from Daily sums':<30} {grand_total_from_daily:>15.2f}")
        print(f"{'Total from Monthly API':<30} {grand_total_from_monthly:>15.2f}")
        print(f"{'Total Energy API':<30} {total_energy:>15.2f}")
        print("-" * 50)
        
        diff_daily_monthly = grand_total_from_monthly - grand_total_from_daily
        diff_daily_total = total_energy - grand_total_from_daily
        diff_monthly_total = total_energy - grand_total_from_monthly
        
        print(f"\n{'Difference Analysis:'}")
        print(f"  Monthly API - Daily sums:  {diff_daily_monthly:+.2f} kWh")
        print(f"  Total API - Daily sums:    {diff_daily_total:+.2f} kWh")
        print(f"  Total API - Monthly API:   {diff_monthly_total:+.2f} kWh")

        if abs(diff_daily_monthly) > 1:
            print("\n⚠️  DISCREPANCY DETECTED between daily and monthly data!")
            print("   The Shine Monitor API returns different values for:")
            print("   - Sum of daily energy values")
            print("   - Monthly energy totals")
            print("   This is a data inconsistency in the Shine Monitor system.")
        else:
            print("\n✓ Daily and Monthly data are consistent!")

        # Special analysis for December 2025
        print("\n" + "=" * 80)
        print("DETAILED ANALYSIS: December 2025")
        print("=" * 80)
        
        dec_daily_data = await client.get_energy_month_per_day(plant_id, 2025, 12)
        print(f"\nDecember 2025 - Daily breakdown:")
        print(f"{'Day':<6} {'Energy (kWh)':>12}")
        print("-" * 20)
        dec_total = 0.0
        for day in dec_daily_data:
            ts = day.get("ts", "")
            val = float(day.get("val", 0))
            if val > 0:
                day_num = ts.split(" ")[0].split("-")[2] if ts else "?"
                print(f"{day_num:<6} {val:>12.2f}")
            dec_total += val
        print("-" * 20)
        print(f"{'TOTAL':<6} {dec_total:>12.2f}")
        
        # Try direct month/year API endpoints
        print("\n--- Testing direct energy endpoints ---")
        dec_month_direct = await client.get_energy_month(plant_id, 2025, 12)
        print(f"queryPlantEnergyMonth (2025-12): {dec_month_direct}")
        
        year_2025_direct = await client.get_energy_year(plant_id, 2025)
        print(f"queryPlantEnergyYear (2025): {year_2025_direct}")
        
        # Check if there's different data in energyTotal breakdown
        print("\n--- Year by year totals ---")
        for y in [2024, 2025, 2026]:
            year_data = await client.get_energy_year(plant_id, y)
            print(f"Year {y}: {year_data}")

        print("\n" + "=" * 80)


def main():
    """Main entry point."""
    username = os.environ.get("SHINE_USERNAME", "")
    password = os.environ.get("SHINE_PASSWORD", "")
    company_key = os.environ.get("SHINE_COMPANY_KEY", "")
    
    if not all([username, password, company_key]):
        print("Please set environment variables:")
        print("  $env:SHINE_USERNAME = 'your_username'")
        print("  $env:SHINE_PASSWORD = 'your_password'")
        print("  $env:SHINE_COMPANY_KEY = 'your_company_key'")
        sys.exit(1)
    
    asyncio.run(compare_energy_data(username, password, company_key))


if __name__ == "__main__":
    main()
