import asyncio
import os
from pybit.unified_trading import HTTP

async def check_position_mode():
    # Get mirror account credentials
    api_key = os.getenv('BYBIT_API_KEY_2')
    api_secret = os.getenv('BYBIT_API_SECRET_2')
    testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
    
    if not api_key or not api_secret:
        print("Mirror account credentials not found!")
        return
    
    # Create client
    client = HTTP(
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret
    )
    
    print("=== CHECKING MIRROR ACCOUNT POSITION MODE ===")
    
    try:
        # Check position mode
        response = client.switch_position_mode(category="linear")
        print(f"Current response: {response}")
    except Exception as e:
        print(f"Error (this might tell us current mode): {e}")
    
    # Get account info
    try:
        response = client.get_account_info()
        print(f"\nAccount info: {response}")
    except Exception as e:
        print(f"Error getting account info: {e}")
    
    # Try to get position with positionIdx
    print("\n=== CHECKING POSITIONS WITH POSITION INDEX ===")
    try:
        response = client.get_positions(category="linear", settleCoin="USDT")
        positions = response.get('result', {}).get('list', [])
        
        for pos in positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                position_idx = pos.get('positionIdx', 0)
                side = pos.get('side')
                print(f"\n{symbol}:")
                print(f"  Side: {side}")
                print(f"  Position Index: {position_idx}")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(check_position_mode())