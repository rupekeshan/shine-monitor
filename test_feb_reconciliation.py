#!/usr/bin/env python3
"""Test the reconciliation logic for February 2026 to debug discrepancy."""
import asyncio
import aiohttp
import hashlib
import time
import os
import calendar
from datetime import datetime, date

API_BASE_URL = 'https://api.shinemonitor.com/public/'

async def test():
    username = os.environ.get('SHINE_USERNAME', 'rupekeshan')
    password = os.environ.get('SHINE_PASSWORD', 'Lala@1998')
    company_key = os.environ.get('SHINE_COMPANY_KEY', 'bnrl_frRFjEz8Mkn')
    plant_id = '1198507'
    
    async with aiohttp.ClientSession() as session:
        # Auth
        salt = str(int(time.time() * 1000))
        hashed_pwd = hashlib.sha1(password.encode()).hexdigest()
        action = f'&action=auth&usr={username}&company-key={company_key}'
        sign = hashlib.sha1((salt + hashed_pwd + action).encode()).hexdigest()
        url = f'{API_BASE_URL}?sign={sign}&salt={salt}{action}'
        
        async with session.get(url) as r:
            auth = await r.json()
            token = auth['dat']['token']
            secret = auth['dat']['secret']
        
        async def api_call(action_name, params):
            salt = str(int(time.time() * 1000))
            action_str = f'&action={action_name}'
            for k, v in params.items():
                action_str += f'&{k}={v}'
            sign = hashlib.sha1((salt + secret + token + action_str).encode()).hexdigest()
            url = f'{API_BASE_URL}?sign={sign}&token={token}&salt={salt}{action_str}'
            async with session.get(url) as r:
                return await r.json()
        
        print("=" * 70)
        print("FEBRUARY 2026 RECONCILIATION TEST")
        print("=" * 70)
        
        now = datetime.now()
        year, month = 2026, 2
        
        # 1. Get monthly total from API
        print("\n[1] Monthly Total from API (queryPlantEnergyMonth)")
        resp = await api_call('queryPlantEnergyMonth', {'plantid': plant_id, 'date': '2026-02'})
        monthly_total = float(resp.get('dat', {}).get('energy', 0))
        print(f"    Monthly Total: {monthly_total} kWh")
        print(f"    Raw response: {resp}")
        
        # 2. Get daily data
        print("\n[2] Daily Data from API (queryPlantEnergyMonthPerDay)")
        resp = await api_call('queryPlantEnergyMonthPerDay', {'plantid': plant_id, 'date': '2026-02'})
        perday = resp.get('dat', {}).get('perday', [])
        print(f"    Raw response: {resp}")
        
        # Parse all daily values
        all_daily_values = {}
        for day_record in perday:
            day_str = day_record.get("ts", "")
            if day_str:
                day_str = day_str.split(" ")[0]
                day_date = datetime.strptime(day_str, "%Y-%m-%d")
                day_energy = float(day_record.get("val", 0))
                all_daily_values[day_date.day] = day_energy
        
        print("\n[3] Daily Values from API:")
        for day in sorted(all_daily_values.keys()):
            marker = " <-- TODAY" if day == now.day else ""
            print(f"    Feb {day:2d}: {all_daily_values[day]:.2f} kWh{marker}")
        
        # 3. Simulate the reconciliation logic (as in services.py)
        print("\n" + "=" * 70)
        print("RECONCILIATION LOGIC SIMULATION")
        print("=" * 70)
        
        # Today's energy (to subtract from monthly total)
        today_energy = all_daily_values.get(now.day, 0)
        print(f"\n[A] Today's energy (Feb {now.day}): {today_energy:.2f} kWh")
        
        # Adjusted monthly total (excluding today)
        adjusted_monthly_total = monthly_total - today_energy
        print(f"[B] Adjusted monthly total (excluding today): {monthly_total:.2f} - {today_energy:.2f} = {adjusted_monthly_total:.2f} kWh")
        
        # Filter daily values to exclude today
        daily_values = {
            day: energy for day, energy in all_daily_values.items()
            if day < now.day  # Exclude today
        }
        
        print(f"\n[C] Daily values (excluding today):")
        for day in sorted(daily_values.keys()):
            print(f"    Feb {day:2d}: {daily_values[day]:.2f} kWh")
        
        # Days in month (up to yesterday)
        days_in_month = now.day - 1
        print(f"\n[D] Days to import (up to yesterday): {days_in_month}")
        
        # Calculate sum and difference
        daily_sum = sum(daily_values.values())
        difference = adjusted_monthly_total - daily_sum
        
        print(f"[E] Sum of daily values (excl. today): {daily_sum:.2f} kWh")
        print(f"[F] Difference (monthly - daily): {adjusted_monthly_total:.2f} - {daily_sum:.2f} = {difference:.2f} kWh")
        
        # Find missing days
        missing_days = [d for d in range(1, days_in_month + 1) if daily_values.get(d, 0) == 0]
        days_with_data = [d for d in range(1, days_in_month + 1) if daily_values.get(d, 0) > 0]
        
        print(f"\n[G] Missing days: {missing_days}")
        print(f"[H] Days with data: {days_with_data}")
        
        # Reconcile
        reconciled_daily = dict(daily_values)
        
        if difference > 0:
            if missing_days:
                per_missing_day = difference / len(missing_days)
                for day in missing_days:
                    reconciled_daily[day] = per_missing_day
                print(f"\n[I] Distributed {difference:.2f} kWh to {len(missing_days)} missing days ({per_missing_day:.2f} each)")
            elif days_with_data:
                total_existing = sum(daily_values[d] for d in days_with_data)
                if total_existing > 0:
                    for day in days_with_data:
                        proportion = daily_values[day] / total_existing
                        reconciled_daily[day] = daily_values[day] + (difference * proportion)
                    print(f"\n[I] Spread {difference:.2f} kWh proportionally across {len(days_with_data)} days")
        elif difference < 0 and days_with_data:
            total_existing = sum(daily_values[d] for d in days_with_data)
            if total_existing > 0:
                scale_factor = adjusted_monthly_total / total_existing
                for day in days_with_data:
                    reconciled_daily[day] = daily_values[day] * scale_factor
                print(f"\n[I] Scaled daily values by {scale_factor:.4f} to match monthly total")
        
        # Final reconciled values
        print("\n" + "=" * 70)
        print("FINAL RECONCILED VALUES (what would be imported)")
        print("=" * 70)
        print(f"\n{'Day':<10} {'API Value':<15} {'Reconciled':<15} {'Difference':<15}")
        print("-" * 55)
        
        total_reconciled = 0
        for day in range(1, days_in_month + 1):
            api_val = daily_values.get(day, 0)
            rec_val = reconciled_daily.get(day, 0)
            diff = rec_val - api_val
            total_reconciled += rec_val
            print(f"Feb {day:<5} {api_val:<15.2f} {rec_val:<15.2f} {diff:+.2f}")
        
        print("-" * 55)
        print(f"{'TOTAL':<10} {daily_sum:<15.2f} {total_reconciled:<15.2f}")
        
        # Compare with expected
        print("\n" + "=" * 70)
        print("COMPARISON WITH EXPECTED VALUES")
        print("=" * 70)
        print(f"\n{'Source':<25} {'Feb 1':<10} {'Feb 2':<10}")
        print("-" * 45)
        print(f"{'Shine Monitor Website':<25} {'8.00':<10} {'9.00':<10}")
        print(f"{'API Daily Value':<25} {all_daily_values.get(1, 0):<10.2f} {all_daily_values.get(2, 0):<10.2f}")
        print(f"{'Reconciled (this logic)':<25} {reconciled_daily.get(1, 0):<10.2f} {reconciled_daily.get(2, 0):<10.2f}")
        
        print("\n" + "=" * 70)
        print("DIAGNOSIS")
        print("=" * 70)
        if abs(difference) > 0.1:
            print(f"\n⚠ Difference of {difference:.2f} kWh is being distributed/scaled")
            print(f"  This could be due to:")
            print(f"  1. Monthly total includes today's {today_energy:.2f} kWh partially")
            print(f"  2. API daily values might be rounded differently than website")
            print(f"  3. Reconciliation is spreading/scaling the difference")
        
        # Also test what happens if we DON'T subtract today
        print("\n" + "=" * 70)
        print("ALTERNATIVE: Without subtracting today's energy")
        print("=" * 70)
        alt_diff = monthly_total - daily_sum
        print(f"Monthly total: {monthly_total:.2f}")
        print(f"Daily sum (excl today): {daily_sum:.2f}")
        print(f"Difference: {alt_diff:.2f}")
        
        if days_with_data and alt_diff != 0:
            total_existing = sum(daily_values[d] for d in days_with_data)
            if alt_diff > 0:
                print(f"\nWould spread {alt_diff:.2f} kWh proportionally:")
                for day in days_with_data:
                    proportion = daily_values[day] / total_existing
                    new_val = daily_values[day] + (alt_diff * proportion)
                    print(f"  Feb {day}: {daily_values[day]:.2f} -> {new_val:.2f}")

if __name__ == '__main__':
    asyncio.run(test())
