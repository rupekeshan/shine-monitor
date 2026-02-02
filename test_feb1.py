#!/usr/bin/env python3
"""Test API data for Feb 1 to investigate the 7.20 kWh dip."""
import asyncio
import aiohttp
import hashlib
import time
import os

API_BASE_URL = 'https://api.shinemonitor.com/public/'

async def test():
    username = os.environ.get('SHINE_USERNAME', 'rupekeshan')
    password = os.environ.get('SHINE_PASSWORD', 'Lala@1998')
    company_key = os.environ.get('SHINE_COMPANY_KEY', 'bnrl_frRFjEz8Mkn')
    
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
        
        # Get TOTAL energy (this is what populates the Total Energy sensor)
        print('=== queryPlantEnergyTotal (used for Total Energy sensor) ===')
        resp = await api_call('queryPlantEnergyTotal', {'plantid': '1198507'})
        print(f'Total lifetime energy: {resp}')
        
        # Get Feb 1 daily energy
        print('\n=== Feb 1, 2026 Daily Energy ===')
        resp = await api_call('queryPlantEnergyDay', {'plantid': '1198507', 'date': '2026-02-01'})
        print(f'Daily energy for Feb 1: {resp}')
        
        # Get power readings for Feb 1 (5-min intervals)
        print('\n=== Feb 1, 2026 Power Output (5-min intervals) ===')
        resp = await api_call('queryPlantActiveOuputPowerOneDay', {'plantid': '1198507', 'date': '2026-02-01'})
        
        if resp.get('dat', {}).get('outputPower'):
            readings = resp['dat']['outputPower']
            
            # Filter to show readings around 3:00 PM - 4:00 PM
            print('\nPower readings around 3:00 PM - 4:00 PM on Feb 1:')
            for r in readings:
                ts = r.get('ts', '')
                if '15:' in ts or '16:0' in ts:
                    print(f"  {ts}: {r.get('val')} kW")
            
            # Calculate cumulative energy throughout the day
            # Energy (kWh) = sum of (power * time_interval)
            # Each reading is 5 min = 5/60 hours
            print('\n=== Estimated Cumulative Energy by Time ===')
            print('(Calculating energy generated UP TO each timestamp)')
            cumulative = 0.0
            for r in readings:
                ts = r.get('ts', '')
                power = float(r.get('val', 0))
                cumulative += power * (5/60)  # 5 minutes in hours
                
                # Show hourly timestamps and around 3:22 PM
                hour_marks = [':00:00']
                around_322 = ['15:15', '15:20', '15:25', '15:30']
                
                if any(mark in ts for mark in hour_marks + around_322):
                    print(f"  {ts}: cumulative ~{cumulative:.2f} kWh")
                    
            print(f'\nTotal daily energy (calculated from power): {cumulative:.2f} kWh')
            
        else:
            print(f'Response: {resp}')

if __name__ == '__main__':
    asyncio.run(test())
