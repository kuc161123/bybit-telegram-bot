import asyncio
import os
from pybit.unified_trading import HTTP
import json

async def check_accounts_detailed():
    # Get credentials
    main_api_key = os.getenv('BYBIT_API_KEY')
    main_api_secret = os.getenv('BYBIT_API_SECRET')
    mirror_api_key = os.getenv('BYBIT_API_KEY_2')
    mirror_api_secret = os.getenv('BYBIT_API_SECRET_2')
    testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
    
    if not all([main_api_key, main_api_secret, mirror_api_key, mirror_api_secret]):
        print("API credentials not found!")
        return
    
    # Create clients
    main_client = HTTP(testnet=testnet, api_key=main_api_key, api_secret=main_api_secret)
    mirror_client = HTTP(testnet=testnet, api_key=mirror_api_key, api_secret=mirror_api_secret)
    
    print("=" * 60)
    print("MAIN ACCOUNT DETAILED CHECK")
    print("=" * 60)
    
    # Check main account positions with raw response
    print("\n=== MAIN ACCOUNT POSITIONS (RAW) ===")
    try:
        response = main_client.get_positions(category="linear", settleCoin="USDT")
        print(f"Raw response: {json.dumps(response, indent=2)}")
        
        positions = response.get('result', {}).get('list', [])
        print(f"\nTotal positions in response: {len(positions)}")
        
        active_count = 0
        for pos in positions:
            size = float(pos.get('size', 0))
            if size > 0:
                active_count += 1
                symbol = pos.get('symbol')
                print(f"\nActive position: {symbol}, size: {size}")
        
        print(f"\nActive positions count: {active_count}")
        
    except Exception as e:
        print(f"Error checking main positions: {e}")
    
    # Check all open orders
    print("\n=== MAIN ACCOUNT ALL ORDERS ===")
    try:
        response = main_client.get_open_orders(category="linear")
        orders = response.get('result', {}).get('list', [])
        print(f"Total open orders: {len(orders)}")
        
        if orders:
            for order in orders[:5]:  # Show first 5
                symbol = order.get('symbol')
                order_type = order.get('orderType')
                side = order.get('side')
                qty = order.get('qty')
                price = order.get('price', 0) or order.get('triggerPrice', 0)
                print(f"  {symbol}: {side} {order_type} @ {price}, Qty: {qty}")
                
    except Exception as e:
        print(f"Error checking main orders: {e}")
    
    # Check main account balance with better parsing
    print("\n=== MAIN ACCOUNT BALANCE ===")
    try:
        response = main_client.get_wallet_balance(accountType="UNIFIED")
        print(f"Wallet response keys: {response.get('result', {}).keys()}")
        
        result = response.get('result', {})
        if 'list' in result:
            for account in result['list']:
                for coin_data in account.get('coin', []):
                    if coin_data.get('coin') == 'USDT':
                        print(f"USDT data: {json.dumps(coin_data, indent=2)}")
                        
                        equity = coin_data.get('equity', '0')
                        available = coin_data.get('availableToWithdraw', '0')
                        
                        # Convert to float safely
                        try:
                            equity_val = float(equity) if equity else 0
                            available_val = float(available) if available else 0
                            print(f"\nParsed values:")
                            print(f"Total Equity: ${equity_val:.2f}")
                            print(f"Available Balance: ${available_val:.2f}")
                            print(f"Used Margin: ${equity_val - available_val:.2f}")
                        except:
                            print(f"Could not parse: equity={equity}, available={available}")
                        break
                        
    except Exception as e:
        print(f"Error getting main balance: {e}")
    
    print("\n" + "=" * 60)
    print("MIRROR ACCOUNT DETAILED CHECK")
    print("=" * 60)
    
    # Check mirror account positions
    print("\n=== MIRROR ACCOUNT POSITIONS (RAW) ===")
    try:
        response = mirror_client.get_positions(category="linear", settleCoin="USDT")
        print(f"Raw response: {json.dumps(response, indent=2)}")
        
        positions = response.get('result', {}).get('list', [])
        print(f"\nTotal positions in response: {len(positions)}")
        
        active_count = 0
        for pos in positions:
            size = float(pos.get('size', 0))
            if size > 0:
                active_count += 1
                symbol = pos.get('symbol')
                position_idx = pos.get('positionIdx', 'N/A')
                print(f"\nActive position: {symbol}, size: {size}, positionIdx: {position_idx}")
        
        print(f"\nActive positions count: {active_count}")
        
    except Exception as e:
        print(f"Error checking mirror positions: {e}")
    
    # Check all open orders
    print("\n=== MIRROR ACCOUNT ALL ORDERS ===")
    try:
        response = mirror_client.get_open_orders(category="linear")
        orders = response.get('result', {}).get('list', [])
        print(f"Total open orders: {len(orders)}")
        
        if orders:
            for order in orders[:5]:  # Show first 5
                symbol = order.get('symbol')
                order_type = order.get('orderType')
                side = order.get('side')
                qty = order.get('qty')
                price = order.get('price', 0) or order.get('triggerPrice', 0)
                stop_type = order.get('stopOrderType', '')
                print(f"  {symbol}: {side} {order_type} @ {price}, Qty: {qty}, StopType: {stop_type}")
                
    except Exception as e:
        print(f"Error checking mirror orders: {e}")
    
    # Check mirror account balance
    print("\n=== MIRROR ACCOUNT BALANCE ===")
    try:
        response = mirror_client.get_wallet_balance(accountType="UNIFIED")
        print(f"Wallet response keys: {response.get('result', {}).keys()}")
        
        result = response.get('result', {})
        if 'list' in result:
            for account in result['list']:
                for coin_data in account.get('coin', []):
                    if coin_data.get('coin') == 'USDT':
                        print(f"USDT data: {json.dumps(coin_data, indent=2)}")
                        
                        equity = coin_data.get('equity', '0')
                        available = coin_data.get('availableToWithdraw', '0')
                        
                        # Convert to float safely
                        try:
                            equity_val = float(equity) if equity else 0
                            available_val = float(available) if available else 0
                            print(f"\nParsed values:")
                            print(f"Total Equity: ${equity_val:.2f}")
                            print(f"Available Balance: ${available_val:.2f}")
                            print(f"Used Margin: ${equity_val - available_val:.2f}")
                        except:
                            print(f"Could not parse: equity={equity}, available={available}")
                        break
                        
    except Exception as e:
        print(f"Error getting mirror balance: {e}")

asyncio.run(check_accounts_detailed())