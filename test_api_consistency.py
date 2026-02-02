#!/usr/bin/env python3
"""Test API consistency - call multiple times to check for inconsistent responses."""
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
        
        print("=== Testing API Consistency (10 calls each) ===\n")
        
        total_energies = []
        daily_energies = []
        
        for i in range(10):
            # Call both APIs
            total_resp = await api_call('queryPlantEnergyTotal', {'plantid': '1198507'})
            daily_resp = await api_call('queryPlantEnergyDay', {'plantid': '1198507'})
            
            total_energy = total_resp.get('dat', {}).get('energy', 'ERROR')
            daily_energy = daily_resp.get('dat', {}).get('energy', 'ERROR')
            
            total_energies.append(total_energy)
            daily_energies.append(daily_energy)
            
            print(f"Call {i+1}: Total={total_energy} kWh, Daily={daily_energy} kWh")
            await asyncio.sleep(0.5)  # Small delay between calls
        
        print("\n=== Summary ===")
        print(f"Total Energy values: {set(total_energies)}")
        print(f"Daily Energy values: {set(daily_energies)}")
        
        if len(set(total_energies)) > 1:
            print("WARNING: Total energy API returned inconsistent values!")
        if len(set(daily_energies)) > 1:
            print("WARNING: Daily energy API returned inconsistent values!")

if __name__ == '__main__':
    asyncio.run(test())
