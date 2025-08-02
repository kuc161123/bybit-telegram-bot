import asyncio
import pickle
from clients.bybit_client import bybit_client
import logging
from datetime import datetime
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SYMBOL = "symbol"
SIDE = "side"
TRADING_APPROACH = "trading_approach"
PRIMARY_ENTRY_PRICE = "primary_entry_price"
TP1_PRICE = "tp1_price"
SL_PRICE = "sl_price"
MARGIN_AMOUNT = "margin_amount"
LEVERAGE = "leverage"
TP_ORDER_IDS = "tp_order_ids"
SL_ORDER_ID = "sl_order_id"

async def restart_fast_monitors():
    """
    Restart monitors for fast approach positions
    """
    symbols_to_monitor = ['ENAUSDT', 'TIAUSDT', 'JTOUSDT', 'WIFUSDT', 'JASMYUSDT', 'WLDUSDT', 'BTCUSDT']
    
    try:
        # Load pickle file
        pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        try:
            with open(pickle_file, 'rb') as f:
                data = pickle.load(f)
        except:
            data = {}
        
        if 'active_monitors' not in data:
            data['active_monitors'] = {}
            
        # Get positions
        pos_response = bybit_client.get_positions(category="linear", settleCoin="USDT")
        positions = pos_response.get("result", {}).get("list", [])
        
        # Get orders
        order_response = bybit_client.get_open_orders(category="linear", settleCoin="USDT")
        orders = order_response.get("result", {}).get("list", [])
        
        print("RESTARTING FAST APPROACH MONITORS:")
        print("="*80)
        
        monitors_added = 0
        
        for symbol in symbols_to_monitor:
            pos = next((p for p in positions if p['symbol'] == symbol and float(p['size']) > 0), None)
            if not pos:
                continue
                
            sym_orders = [o for o in orders if o['symbol'] == symbol]
            
            # Get TP/SL orders
            tp_orders = [o for o in sym_orders if o.get('stopOrderType') == 'TakeProfit' and o.get('reduceOnly')]
            sl_orders = [o for o in sym_orders if o.get('stopOrderType') == 'StopLoss' and o.get('reduceOnly')]
            
            if tp_orders and sl_orders:
                side = pos['side']
                
                # Create monitor ID
                monitor_id = f"{symbol}_{side}_fast_1000000"  # Using default chat_id
                
                # Skip if monitor already exists
                if monitor_id in data['active_monitors']:
                    print(f"{symbol} - Monitor already exists")
                    continue
                
                print(f"\n{symbol} - Creating monitor:")
                print(f"Position: {pos['size']} @ {pos['avgPrice']} ({side})")
                
                # Create chat data for monitor
                chat_data = {
                    SYMBOL: symbol,
                    SIDE: side,
                    TRADING_APPROACH: "fast",
                    PRIMARY_ENTRY_PRICE: pos['avgPrice'],
                    "entry_price": pos['avgPrice'],
                    "position_size": pos['size'],
                    "expected_position_size": pos['size'],
                    MARGIN_AMOUNT: "100",  # Default
                    LEVERAGE: "10",  # Default
                    "chat_id": 1000000,  # Default chat ID
                    "_chat_id": 1000000
                }
                
                # Add TP order info
                if tp_orders:
                    tp_order = tp_orders[0]
                    chat_data[TP1_PRICE] = tp_order.get('triggerPrice', '0')
                    chat_data["tp_order_id"] = tp_order.get('orderId')
                    chat_data[TP_ORDER_IDS] = [tp_order.get('orderId')]
                    print(f"TP: {tp_order.get('triggerPrice')} (Order: {tp_order.get('orderId')[:8]}...)")
                
                # Add SL order info
                if sl_orders:
                    sl_order = sl_orders[0]
                    chat_data[SL_PRICE] = sl_order.get('triggerPrice', '0')
                    chat_data[SL_ORDER_ID] = sl_order.get('orderId')
                    chat_data["sl_order_id"] = sl_order.get('orderId')
                    print(f"SL: {sl_order.get('triggerPrice')} (Order: {sl_order.get('orderId')[:8]}...)")
                
                # Add monitor data
                monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "approach": "fast",
                    "trading_approach": "fast",
                    "created_at": datetime.now().isoformat(),
                    "chat_data": chat_data,
                    "tp_order_ids": chat_data.get(TP_ORDER_IDS, []),
                    "sl_order_id": chat_data.get(SL_ORDER_ID)
                }
                
                data['active_monitors'][monitor_id] = monitor_data
                monitors_added += 1
                print(f"✅ Monitor created: {monitor_id}")
        
        # Save updated pickle file
        with open(pickle_file, 'wb') as f:
            pickle.dump(data, f)
            
        print(f"\n{'='*80}")
        print(f"MONITORS RESTARTED: {monitors_added}")
        print(f"Total active monitors: {len(data['active_monitors'])}")
        
    except Exception as e:
        logger.error(f"Error restarting monitors: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(restart_fast_monitors())