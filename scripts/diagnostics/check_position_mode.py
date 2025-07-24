#!/usr/bin/env python3
"""
Check position mode for the account
"""

from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET

session = HTTP(
    testnet=USE_TESTNET,
    api_key=BYBIT_API_KEY,
    api_secret=BYBIT_API_SECRET
)

# Check position mode
try:
    # Get position info
    result = session.get_positions(category="linear", symbol="TIAUSDT")
    positions = result.get("result", {}).get("list", [])
    
    if positions:
        print(f"Position Mode Info:")
        print(f"Position Index: {positions[0].get('positionIdx')}")
        print(f"Position Mode: {positions[0].get('positionMode')}")
        
    # Get account info to confirm position mode
    account_info = session.get_account_info()
    print(f"\nAccount unified margin status: {account_info.get('result', {}).get('unifiedMarginStatus')}")
    
except Exception as e:
    print(f"Error: {e}")