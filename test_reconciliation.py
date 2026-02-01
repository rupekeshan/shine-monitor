"""Test the reconciliation logic to debug why import isn't working."""
import asyncio
import aiohttp
import hashlib
import time
import calendar
import os
from datetime import datetime

API_BASE_URL = "http://api.shinemonitor.com/public/"

async def main():
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
        print("All fields required!")
        return
        
    async with aiohttp.ClientSession() as session:
        # Authenticate
        salt = str(int(time.time() * 1000))
        hashed_password = hashlib.sha1(password.encode("utf-8")).hexdigest()
        action = f"&action=auth&usr={username}&company-key={company_key}"
        sign_string = salt + hashed_password + action
        sign = hashlib.sha1(sign_string.encode("utf-8")).hexdigest()
        
        url = f"{API_BASE_URL}?sign={sign}&salt={salt}{action}"
        async with session.get(url) as response:
            data = await response.json()
            print(f"Auth response: {data}")
            token = data["dat"]["token"]
            secret = data["dat"]["secret"]
        
        async def api_request(action_name, params=None):
            salt = str(int(time.time() * 1000))
            action_str = f"&action={action_name}"
            if params:
                for key, value in params.items():
                    action_str += f"&{key}={value}"
            
            sign_string = salt + secret + token + action_str
            sign = hashlib.sha1(sign_string.encode("utf-8")).hexdigest()
            url = f"{API_BASE_URL}?sign={sign}&token={token}&salt={salt}{action_str}"
            
            async with session.get(url) as response:
                return await response.json()
        
        # First get the user's plants
        print("\n=== Getting Plants ===")
        plants_data = await api_request("queryPlants")
        print(f"Plants response: {plants_data}")
        
        plants = plants_data.get("dat", {}).get("plant", [])
        if not plants:
            print("No plants found!")
            return
        
        plant_id = plants[0].get("pid") or plants[0].get("id")
        plant_name = plants[0].get("name", "Unknown")
        print(f"Using plant: {plant_name} (ID: {plant_id})")
        
        # Test get_energy_month - this is what we use for monthly totals
        print("\n=== Testing get_energy_month (queryPlantEnergyYearPerMonth) ===")
        
        # Test for 2024
        year = 2024
        data = await api_request("queryPlantEnergyYearPerMonth", {"plantid": plant_id, "date": str(year)})
        print(f"\nYear {year} response:")
        print(f"  Full response: {data}")
        
        dat = data.get("dat", {})
        print(f"  dat keys: {dat.keys() if isinstance(dat, dict) else 'not a dict'}")
        
        # Check what fields are available
        if isinstance(dat, dict):
            for key, value in dat.items():
                print(f"  dat.{key}: {value[:3] if isinstance(value, list) and len(value) > 3 else value}")
        
        # Test for 2025
        year = 2025
        data = await api_request("queryPlantEnergyYearPerMonth", {"plantid": plant_id, "date": str(year)})
        print(f"\nYear {year} response:")
        print(f"  Full response: {data}")
        
        # Test daily data for a month we know has gaps
        print("\n=== Testing get_energy_month_per_day (queryPlantEnergyMonthPerDay) ===")
        
        # December 2024 - we know this had gaps
        data = await api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "date": "2024-12"})
        print(f"\n2024-12 daily data:")
        print(f"  Full response keys: {data.keys()}")
        dat = data.get("dat", {})
        print(f"  dat keys: {dat.keys() if isinstance(dat, dict) else 'not a dict'}")
        
        perday = dat.get("perday", [])
        print(f"  Number of daily records: {len(perday)}")
        if perday:
            print(f"  First record: {perday[0]}")
            print(f"  Last record: {perday[-1]}")
        
        # Now simulate the reconciliation logic
        print("\n=== Simulating Reconciliation for 2024-12 ===")
        
        # Get monthly total
        year_data = await api_request("queryPlantEnergyYearPerMonth", {"plantid": plant_id, "date": "2024"})
        monthly_totals = year_data.get("dat", {}).get("permonth", [])
        
        # Find December
        dec_total = 0
        for m in monthly_totals:
            ts = str(m.get("ts", ""))
            if "12" in ts or ts == "12":
                dec_total = float(m.get("val", 0))
                print(f"  Found December in permonth: ts={ts}, val={dec_total}")
                break
        
        if dec_total == 0:
            # Maybe it's in a different format
            print(f"  permonth data: {monthly_totals}")
        
        # Get daily data
        daily_data = await api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "date": "2024-12"})
        perday = daily_data.get("dat", {}).get("perday", [])
        
        daily_values = {}
        for day_record in perday:
            day_str = day_record.get("ts", "")
            if day_str:
                day_str = day_str.split(" ")[0]
                try:
                    day_date = datetime.strptime(day_str, "%Y-%m-%d")
                    day_energy = float(day_record.get("val", 0))
                    daily_values[day_date.day] = day_energy
                except ValueError:
                    pass
        
        days_in_month = 31  # December
        daily_sum = sum(daily_values.values())
        
        print(f"  Monthly API total: {dec_total}")
        print(f"  Daily sum: {daily_sum}")
        print(f"  Days with data: {sorted(daily_values.keys())}")
        print(f"  Missing days: {[d for d in range(1, days_in_month+1) if d not in daily_values or daily_values.get(d, 0) == 0]}")
        
        # Test a recent month - January 2025
        print("\n=== Testing January 2025 ===")
        
        year_data = await api_request("queryPlantEnergyYearPerMonth", {"plantid": plant_id, "date": "2025"})
        print(f"  2025 year data: {year_data}")
        
        daily_data = await api_request("queryPlantEnergyMonthPerDay", {"plantid": plant_id, "date": "2025-01"})
        perday = daily_data.get("dat", {}).get("perday", [])
        print(f"  January 2025 daily records: {len(perday)}")
        if perday:
            print(f"  Sample: {perday[:3]}")
        
        # Check what the actual structure looks like for monthly totals
        print("\n=== Checking alternative monthly total endpoints ===")
        
        # Maybe we need queryPlantEnergyMonth with a date parameter?
        for test_date in ["2024-12", "2025-01"]:
            data = await api_request("queryPlantEnergyMonth", {"plantid": plant_id, "date": test_date})
            print(f"  queryPlantEnergyMonth date={test_date}: {data}")

if __name__ == "__main__":
    asyncio.run(main())
