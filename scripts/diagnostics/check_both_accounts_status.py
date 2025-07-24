import asyncio
import os
from pybit.unified_trading import HTTP

async def check_both_accounts():
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
    print("MAIN ACCOUNT STATUS")
    print("=" * 60)
    
    # Check main account positions
    print("\n=== MAIN ACCOUNT POSITIONS ===")
    try:
        response = main_client.get_positions(category="linear", settleCoin="USDT")
        positions = response.get('result', {}).get('list', [])
        
        active_positions = []
        total_pnl = 0
        
        for pos in positions:
            if float(pos.get('size', 0)) > 0:
                active_positions.append(pos)
                symbol = pos.get('symbol', 'N/A')
                side = pos.get('side', 'N/A')
                size = float(pos.get('size', 0))
                avg_price = float(pos.get('avgPrice', 0))
                mark_price = float(pos.get('markPrice', 0))
                pnl = float(pos.get('unrealisedPnl', 0))
                leverage = pos.get('leverage', 'N/A')
                
                total_pnl += pnl
                
                print(f"\n{symbol}:")
                print(f"  Side: {side}")
                print(f"  Size: {size}")
                print(f"  Avg Price: {avg_price}")
                print(f"  Mark Price: {mark_price}")
                print(f"  Leverage: {leverage}x")
                print(f"  Unrealized PnL: ${pnl:.2f}")
        
        if active_positions:
            print(f"\nTotal Positions: {len(active_positions)}")
            print(f"Total Unrealized PnL: ${total_pnl:.2f}")
            
            # Check orders for active positions
            print("\n=== MAIN ACCOUNT ORDERS ===")
            for pos in active_positions:
                symbol = pos.get('symbol')
                response = main_client.get_open_orders(category="linear", symbol=symbol)
                orders = response.get('result', {}).get('list', [])
                
                if orders:
                    print(f"\n{symbol} Orders ({len(orders)}):")
                    
                    tp_orders = []
                    sl_orders = []
                    limit_orders = []
                    
                    for order in orders:
                        order_type = order.get('stopOrderType', '')
                        if order_type == 'TakeProfit':
                            tp_orders.append(order)
                        elif order_type == 'StopLoss':
                            sl_orders.append(order)
                        else:
                            limit_orders.append(order)
                    
                    if tp_orders:
                        print("  Take Profit Orders:")
                        for o in sorted(tp_orders, key=lambda x: float(x.get('triggerPrice', 0))):
                            qty = o.get('qty', 0)
                            price = o.get('triggerPrice', 0)
                            print(f"    - TP @ {price}: Qty={qty}")
                    
                    if sl_orders:
                        print("  Stop Loss Orders:")
                        for o in sl_orders:
                            qty = o.get('qty', 0)
                            price = o.get('triggerPrice', 0)
                            print(f"    - SL @ {price}: Qty={qty}")
                    
                    if limit_orders:
                        print("  Limit Orders:")
                        for o in sorted(limit_orders, key=lambda x: float(x.get('price', 0))):
                            qty = o.get('qty', 0)
                            price = o.get('price', 0)
                            side = o.get('side', '')
                            print(f"    - Limit {side} @ {price}: Qty={qty}")
        else:
            print("No active positions found")
            
    except Exception as e:
        print(f"Error checking main positions: {e}")
    
    # Check main account balance
    print("\n=== MAIN ACCOUNT BALANCE ===")
    try:
        response = main_client.get_wallet_balance(accountType="UNIFIED")
        accounts = response.get('result', {}).get('list', [])
        
        for account in accounts:
            for coin_data in account.get('coin', []):
                if coin_data.get('coin') == 'USDT':
                    equity = float(coin_data.get('equity', 0))
                    available = float(coin_data.get('availableToWithdraw', 0))
                    print(f"Total Equity: ${equity:.2f}")
                    print(f"Available Balance: ${available:.2f}")
                    print(f"Used Margin: ${equity - available:.2f}")
                    break
    except Exception as e:
        print(f"Error getting main balance: {e}")
    
    print("\n" + "=" * 60)
    print("MIRROR ACCOUNT STATUS")
    print("=" * 60)
    
    # Check mirror account positions
    print("\n=== MIRROR ACCOUNT POSITIONS ===")
    try:
        response = mirror_client.get_positions(category="linear", settleCoin="USDT")
        positions = response.get('result', {}).get('list', [])
        
        active_positions = []
        total_pnl = 0
        
        for pos in positions:
            if float(pos.get('size', 0)) > 0:
                active_positions.append(pos)
                symbol = pos.get('symbol', 'N/A')
                side = pos.get('side', 'N/A')
                size = float(pos.get('size', 0))
                avg_price = float(pos.get('avgPrice', 0))
                mark_price = float(pos.get('markPrice', 0))
                pnl = float(pos.get('unrealisedPnl', 0))
                leverage = pos.get('leverage', 'N/A')
                position_idx = pos.get('positionIdx', 'N/A')
                
                total_pnl += pnl
                
                print(f"\n{symbol}:")
                print(f"  Side: {side}")
                print(f"  Size: {size}")
                print(f"  Avg Price: {avg_price}")
                print(f"  Mark Price: {mark_price}")
                print(f"  Leverage: {leverage}x")
                print(f"  Position Index: {position_idx}")
                print(f"  Unrealized PnL: ${pnl:.2f}")
        
        if active_positions:
            print(f"\nTotal Positions: {len(active_positions)}")
            print(f"Total Unrealized PnL: ${total_pnl:.2f}")
            
            # Check orders for active positions
            print("\n=== MIRROR ACCOUNT ORDERS ===")
            for pos in active_positions:
                symbol = pos.get('symbol')
                response = mirror_client.get_open_orders(category="linear", symbol=symbol)
                orders = response.get('result', {}).get('list', [])
                
                if orders:
                    print(f"\n{symbol} Orders ({len(orders)}):")
                    
                    tp_orders = []
                    sl_orders = []
                    limit_orders = []
                    
                    for order in orders:
                        order_type = order.get('stopOrderType', '')
                        if order_type == 'TakeProfit':
                            tp_orders.append(order)
                        elif order_type == 'StopLoss':
                            sl_orders.append(order)
                        else:
                            limit_orders.append(order)
                    
                    if tp_orders:
                        print("  Take Profit Orders:")
                        for o in sorted(tp_orders, key=lambda x: float(x.get('triggerPrice', 0))):
                            qty = o.get('qty', 0)
                            price = o.get('triggerPrice', 0)
                            print(f"    - TP @ {price}: Qty={qty}")
                    
                    if sl_orders:
                        print("  Stop Loss Orders:")
                        for o in sl_orders:
                            qty = o.get('qty', 0)
                            price = o.get('triggerPrice', 0)
                            print(f"    - SL @ {price}: Qty={qty}")
                    
                    if limit_orders:
                        print("  Limit Orders:")
                        for o in sorted(limit_orders, key=lambda x: float(x.get('price', 0))):
                            qty = o.get('qty', 0)
                            price = o.get('price', 0)
                            side = o.get('side', '')
                            print(f"    - Limit {side} @ {price}: Qty={qty}")
        else:
            print("No active positions found")
            
    except Exception as e:
        print(f"Error checking mirror positions: {e}")
    
    # Check mirror account balance
    print("\n=== MIRROR ACCOUNT BALANCE ===")
    try:
        response = mirror_client.get_wallet_balance(accountType="UNIFIED")
        accounts = response.get('result', {}).get('list', [])
        
        for account in accounts:
            for coin_data in account.get('coin', []):
                if coin_data.get('coin') == 'USDT':
                    equity = float(coin_data.get('equity', 0))
                    available = float(coin_data.get('availableToWithdraw', 0))
                    print(f"Total Equity: ${equity:.2f}")
                    print(f"Available Balance: ${available:.2f}")
                    print(f"Used Margin: ${equity - available:.2f}")
                    break
    except Exception as e:
        print(f"Error getting mirror balance: {e}")

asyncio.run(check_both_accounts())