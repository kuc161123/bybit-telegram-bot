#!/usr/bin/env python3
"""Test API connection"""

from pybit.unified_trading import HTTP
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET

try:
    client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    # Test connection
    result = client.get_wallet_balance(accountType="UNIFIED", coin="USDT")
    if result['retCode'] == 0:
        print("✅ API connection successful!")
        balance = result['result']['list'][0]['coin'][0]['walletBalance']
        print(f"USDT Balance: {balance}")
    else:
        print(f"❌ API error: {result}")
        
except Exception as e:
    print(f"❌ Connection failed: {e}")
    import traceback
    traceback.print_exc()