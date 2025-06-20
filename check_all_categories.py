#!/usr/bin/env python3
"""
Check positions across all categories and settlement coins
"""
import asyncio
from clients.bybit_client import bybit_client
from clients.bybit_helpers import api_call_with_retry

async def check_all_positions():
    print("\nChecking positions across all categories...")
    
    # Check linear USDT positions
    print("\n=== LINEAR USDT POSITIONS ===")
    response = await api_call_with_retry(
        lambda: bybit_client.get_positions(category="linear", settleCoin="USDT", limit=200)
    )
    if response and response.get("retCode") == 0:
        positions = response.get("result", {}).get("list", [])
        active = [p for p in positions if float(p.get('size', 0)) > 0]
        print(f"Total: {len(positions)}, Active: {len(active)}")
        
    # Check linear USDC positions
    print("\n=== LINEAR USDC POSITIONS ===")
    response = await api_call_with_retry(
        lambda: bybit_client.get_positions(category="linear", settleCoin="USDC", limit=200)
    )
    if response and response.get("retCode") == 0:
        positions = response.get("result", {}).get("list", [])
        active = [p for p in positions if float(p.get('size', 0)) > 0]
        print(f"Total: {len(positions)}, Active: {len(active)}")
        
    # Check inverse positions
    print("\n=== INVERSE POSITIONS ===")
    response = await api_call_with_retry(
        lambda: bybit_client.get_positions(category="inverse", limit=200)
    )
    if response and response.get("retCode") == 0:
        positions = response.get("result", {}).get("list", [])
        active = [p for p in positions if float(p.get('size', 0)) > 0]
        print(f"Total: {len(positions)}, Active: {len(active)}")
        
    # Check without settleCoin filter
    print("\n=== ALL LINEAR POSITIONS (no settleCoin filter) ===")
    response = await api_call_with_retry(
        lambda: bybit_client.get_positions(category="linear", limit=200)
    )
    if response and response.get("retCode") == 0:
        positions = response.get("result", {}).get("list", [])
        active = [p for p in positions if float(p.get('size', 0)) > 0]
        print(f"Total: {len(positions)}, Active: {len(active)}")
        
        # Group by settleCoin
        by_coin = {}
        for p in active:
            coin = p.get('settleCoin', 'Unknown')
            if coin not in by_coin:
                by_coin[coin] = 0
            by_coin[coin] += 1
        
        print("\nBy settlement coin:")
        for coin, count in by_coin.items():
            print(f"  {coin}: {count} positions")

if __name__ == "__main__":
    asyncio.run(check_all_positions())