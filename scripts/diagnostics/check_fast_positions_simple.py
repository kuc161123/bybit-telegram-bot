import asyncio
from clients.bybit_client import bybit_client
from utils.logger import setup_logger
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
logger = setup_logger()

async def check_fast_positions():
    symbols = ['ENAUSDT', 'TIAUSDT', 'JTOUSDT', 'WIFUSDT', 'JASMYUSDT', 'WLDUSDT', 'KAVAUSDT', 'BTCUSDT']
    
    try:
        # Get positions
        pos_response = bybit_client.get_positions(category="linear")
        positions = pos_response.get("result", {}).get("list", [])
        
        # Get orders
        order_response = bybit_client.get_open_orders(category="linear")
        orders = order_response.get("result", {}).get("list", [])
        
        for symbol in symbols:
            pos = next((p for p in positions if p['symbol'] == symbol and float(p['size']) > 0), None)
            if pos:
                sym_orders = [o for o in orders if o['symbol'] == symbol]
                
                print(f'\n{"="*80}')
                print(f'📊 {symbol} ANALYSIS:')
                print(f'{"="*80}')
                print(f'Position: {pos["size"]} @ {pos["avgPrice"]} ({pos["side"]})')
                print(f'P&L: ${float(pos["unrealisedPnl"]):.2f}')
                print(f'\nOrders ({len(sym_orders)}):')
                
                tp_orders = []
                sl_orders = []
                
                for order in sym_orders:
                    # Check if it's a TP or SL order
                    is_reduce_only = order.get('reduceOnly', False)
                    order_price = float(order['price'])
                    avg_price = float(pos['avgPrice'])
                    
                    if is_reduce_only:
                        if pos['side'] == 'Buy':
                            order_type = 'TP' if order_price > avg_price else 'SL'
                        else:  # Sell
                            order_type = 'TP' if order_price < avg_price else 'SL'
                    else:
                        order_type = 'Entry'
                    
                    print(f'  {order_type}: {order["qty"]} @ ${order["price"]} | {order["orderType"]} | LinkID: {order.get("orderLinkId", "")}')
                    
                    if order_type == 'TP':
                        tp_orders.append(order)
                    elif order_type == 'SL':
                        sl_orders.append(order)
                
                tp_total = sum(float(o['qty']) for o in tp_orders)
                sl_total = sum(float(o['qty']) for o in sl_orders)
                
                print(f'\nTotal TP Qty: {tp_total} ({len(tp_orders)} orders)')
                print(f'Total SL Qty: {sl_total} ({len(sl_orders)} orders)')
                print(f'Position Size: {pos["size"]}')
                
                if tp_total < float(pos['size']) * 0.95:
                    print(f'⚠️  TP quantity mismatch! Missing {float(pos["size"]) - tp_total:.1f}')
                if sl_total < float(pos['size']) * 0.95:
                    print(f'⚠️  SL quantity mismatch! Missing {float(pos["size"]) - sl_total:.1f}')
                    
    except Exception as e:
        logger.error(f"Error checking positions: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(check_fast_positions())