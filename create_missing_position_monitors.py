#!/usr/bin/env python3
"""
Create missing Enhanced TP/SL monitors for positions
"""

import asyncio
import logging
import pickle
import time
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_missing_monitors():
    """Create monitors for TIAUSDT, RUNEUSDT, and WLDUSDT on mirror account"""
    
    print("=" * 80)
    print("CREATING MISSING ENHANCED TP/SL MONITORS")
    print("=" * 80)
    
    # Positions that need monitors
    missing_positions = [
        {'symbol': 'TIAUSDT', 'side': 'Buy', 'account': 'mirror'},
        {'symbol': 'RUNEUSDT', 'side': 'Buy', 'account': 'mirror'}, 
        {'symbol': 'WLDUSDT', 'side': 'Buy', 'account': 'mirror'}
    ]
    
    # Initialize mirror client
    mirror_session = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    # Load current pickle data
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading pickle file: {e}")
        return
    
    # Get existing monitors
    if 'bot_data' not in data:
        data['bot_data'] = {}
    if 'enhanced_tp_sl_monitors' not in data['bot_data']:
        data['bot_data']['enhanced_tp_sl_monitors'] = {}
    
    enhanced_monitors = data['bot_data']['enhanced_tp_sl_monitors']
    
    # Process each missing position
    for pos_info in missing_positions:
        symbol = pos_info['symbol']
        side = pos_info['side']
        account = pos_info['account']
        
        print(f"\n📊 Processing {symbol} {side} ({account})...")
        
        try:
            # Get position details
            position_result = mirror_session.get_positions(
                category="linear",
                symbol=symbol
            )
            
            if position_result.get("retCode") != 0:
                print(f"❌ Failed to get position: {position_result.get('retMsg', 'Unknown error')}")
                continue
            
            positions = position_result.get("result", {}).get("list", [])
            position = None
            
            for p in positions:
                if p.get("side") == side and float(p.get("size", 0)) > 0:
                    position = p
                    break
            
            if not position:
                print(f"❌ No active position found for {symbol} {side}")
                continue
            
            # Get order details
            orders_result = mirror_session.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if orders_result.get("retCode") != 0:
                print(f"❌ Failed to get orders: {orders_result.get('retMsg', 'Unknown error')}")
                continue
            
            orders = orders_result.get("result", {}).get("list", [])
            
            # Extract TP and SL orders
            tp_orders = []
            sl_order = None
            
            for order in orders:
                link_id = str(order.get("orderLinkId", ""))
                
                if "TP" in link_id:
                    tp_orders.append({
                        'price': order.get('price'),
                        'qty': order.get('qty'),
                        'order_id': order.get('orderId'),
                        'filled': False
                    })
                elif "SL" in link_id or order.get("triggerPrice"):
                    sl_order = {
                        'price': order.get('triggerPrice', order.get('price')),
                        'qty': order.get('qty'),
                        'order_id': order.get('orderId')
                    }
            
            # Sort TP orders by price
            tp_orders.sort(key=lambda x: float(x['price']), reverse=(side == "Buy"))
            
            # Create monitor data
            monitor_key = f"{symbol}_{side}_{account}"
            monitor_data = {
                'symbol': symbol,
                'side': side,
                'entry_price': position.get('avgPrice'),
                'current_size': position.get('size'),
                'stop_loss': sl_order['price'] if sl_order else None,
                'take_profits': tp_orders,
                'created_at': time.time(),
                'account_type': account,
                'tp1_hit': False,
                'sl_moved_to_breakeven': False,
                'approach': 'conservative',  # Default approach
                'chat_id': None
            }
            
            # Add to monitors
            enhanced_monitors[monitor_key] = monitor_data
            
            print(f"✅ Created monitor for {symbol}:")
            print(f"   Entry: {monitor_data['entry_price']}")
            print(f"   Size: {monitor_data['current_size']}")
            print(f"   TPs: {len(tp_orders)}")
            print(f"   SL: {sl_order['price'] if sl_order else 'None'}")
            
        except Exception as e:
            print(f"❌ Error processing {symbol}: {e}")
    
    # Save updated data
    try:
        # Create backup first
        import shutil
        backup_file = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_{int(time.time())}"
        shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
        print(f"\n📦 Created backup: {backup_file}")
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print("\n✅ Successfully saved updated monitors to pickle file")
        
        # Verify
        print("\n📊 Final Monitor Count:")
        print(f"   Enhanced TP/SL Monitors: {len(enhanced_monitors)}")
        
    except Exception as e:
        print(f"\n❌ Error saving data: {e}")


if __name__ == "__main__":
    asyncio.run(create_missing_monitors())