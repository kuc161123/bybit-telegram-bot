import asyncio
from clients.bybit_client import get_client

async def check_mirror_positions():
    # Get mirror account client
    client = await get_client(account='mirror')
    
    print('=== MIRROR ACCOUNT POSITIONS (FROM BYBIT) ===')
    
    # Get all positions
    positions = await client.get_positions()
    
    if positions:
        print(f'Total positions: {len(positions)}')
        print()
        
        total_pnl = 0
        position_symbols = []
        
        for pos in positions:
            symbol = pos.get('symbol', 'N/A')
            side = pos.get('side', 'N/A')
            size = float(pos.get('size', 0))
            avg_price = float(pos.get('avgPrice', 0))
            mark_price = float(pos.get('markPrice', 0))
            pnl = float(pos.get('unrealisedPnl', 0))
            leverage = pos.get('leverage', 'N/A')
            
            total_pnl += pnl
            position_symbols.append(symbol)
            
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
        for symbol in position_symbols:
            orders = await client.get_open_orders(symbol)
            if orders:
                print(f'\n{symbol} Orders ({len(orders)}):')
                
                # Group by order type
                tp_orders = []
                sl_orders = []
                limit_orders = []
                
                for order in orders:
                    order_type = order.get('stopOrderType', 'Limit')
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
                        print(f'    - TP @ {price}: Qty={qty}, LinkID={link_id[:30]}...')
                
                # Show SL orders
                if sl_orders:
                    print('  Stop Loss Orders:')
                    for o in sl_orders:
                        qty = o.get('qty', 0)
                        price = o.get('triggerPrice', 0)
                        link_id = o.get('orderLinkId', 'N/A')
                        print(f'    - SL @ {price}: Qty={qty}, LinkID={link_id[:30]}...')
                
                # Show limit orders
                if limit_orders:
                    print('  Limit Orders:')
                    for o in sorted(limit_orders, key=lambda x: float(x.get('price', 0))):
                        qty = o.get('qty', 0)
                        price = o.get('price', 0)
                        side = o.get('side', '')
                        link_id = o.get('orderLinkId', 'N/A')
                        print(f'    - Limit {side} @ {price}: Qty={qty}, LinkID={link_id[:30]}...')
    else:
        print('No open positions found')
    
    # Also check account balance
    print('\n=== MIRROR ACCOUNT BALANCE ===')
    account_info = await client.get_wallet_balance()
    if account_info and 'list' in account_info:
        for item in account_info['list']:
            if item.get('coin') == 'USDT':
                total_balance = float(item.get('totalWalletBalance', 0))
                available = float(item.get('availableToWithdraw', 0))
                print(f'Total Balance: ${total_balance:.2f}')
                print(f'Available Balance: ${available:.2f}')
                print(f'Used Margin: ${total_balance - available:.2f}')
                break

asyncio.run(check_mirror_positions())