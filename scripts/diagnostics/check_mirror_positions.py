import asyncio
import os
from pybit.unified_trading import HTTP

async def check_mirror_account():
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
    
    print('=== MIRROR ACCOUNT POSITIONS ===')
    
    # Get positions
    try:
        response = client.get_positions(category="linear", settleCoin="USDT")
        positions = response.get('result', {}).get('list', [])
        
        if positions:
            print(f'Total positions: {len(positions)}')
            print()
            
            total_pnl = 0
            position_data = []
            
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    symbol = pos.get('symbol', 'N/A')
                    side = pos.get('side', 'N/A')
                    size = float(pos.get('size', 0))
                    avg_price = float(pos.get('avgPrice', 0))
                    mark_price = float(pos.get('markPrice', 0))
                    pnl = float(pos.get('unrealisedPnl', 0))
                    leverage = pos.get('leverage', 'N/A')
                    
                    total_pnl += pnl
                    position_data.append(symbol)
                    
                    print(f'{symbol}:')
                    print(f'  Side: {side}')
                    print(f'  Size: {size}')
                    print(f'  Avg Price: {avg_price}')
                    print(f'  Mark Price: {mark_price}')
                    print(f'  Leverage: {leverage}x')
                    print(f'  Unrealized PnL: ${pnl:.2f}')
                    print()
            
            print(f'Total Unrealized PnL: ${total_pnl:.2f}')
            
            # Get orders for each position
            print('\n=== MIRROR ACCOUNT ORDERS ===')
            for symbol in position_data:
                response = client.get_open_orders(category="linear", symbol=symbol)
                orders = response.get('result', {}).get('list', [])
                
                if orders:
                    print(f'\n{symbol} Orders ({len(orders)}):')
                    
                    # Group by order type
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
                    
                    # Show TP orders
                    if tp_orders:
                        print('  Take Profit Orders:')
                        for o in sorted(tp_orders, key=lambda x: float(x.get('triggerPrice', 0))):
                            qty = o.get('qty', 0)
                            price = o.get('triggerPrice', 0)
                            link_id = o.get('orderLinkId', 'N/A')
                            print(f'    - TP @ {price}: Qty={qty}, LinkID={link_id[:40]}...')
                    
                    # Show SL orders
                    if sl_orders:
                        print('  Stop Loss Orders:')
                        for o in sl_orders:
                            qty = o.get('qty', 0)
                            price = o.get('triggerPrice', 0)
                            link_id = o.get('orderLinkId', 'N/A')
                            print(f'    - SL @ {price}: Qty={qty}, LinkID={link_id[:40]}...')
                    
                    # Show limit orders
                    if limit_orders:
                        print('  Limit Orders:')
                        for o in sorted(limit_orders, key=lambda x: float(x.get('price', 0))):
                            qty = o.get('qty', 0)
                            price = o.get('price', 0)
                            side = o.get('side', '')
                            link_id = o.get('orderLinkId', 'N/A')
                            print(f'    - Limit {side} @ {price}: Qty={qty}, LinkID={link_id[:40]}...')
        else:
            print('No open positions found')
            
    except Exception as e:
        print(f"Error: {e}")
    
    # Check account balance
    print('\n=== MIRROR ACCOUNT BALANCE ===')
    try:
        response = client.get_wallet_balance(accountType="UNIFIED")
        accounts = response.get('result', {}).get('list', [])
        
        for account in accounts:
            for coin_data in account.get('coin', []):
                if coin_data.get('coin') == 'USDT':
                    equity = float(coin_data.get('equity', 0))
                    available = float(coin_data.get('availableToWithdraw', 0))
                    print(f'Total Equity: ${equity:.2f}')
                    print(f'Available Balance: ${available:.2f}')
                    print(f'Used Margin: ${equity - available:.2f}')
                    break
    except Exception as e:
        print(f"Error getting balance: {e}")

asyncio.run(check_mirror_account())