#!/usr/bin/env python3
"""
Activate Enhanced TP/SL Monitoring for Running Bot
This script will connect to the bot's pickle file and add monitors that persist.
"""
import asyncio
import logging
import sys
import os
import pickle
import time
from decimal import Decimal
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def activate_live_monitoring():
    """Activate Enhanced TP/SL monitoring for the running bot"""
    try:
        print("🚀 ACTIVATING ENHANCED TP/SL MONITORING FOR RUNNING BOT")
        print("=" * 70)
        
        # Import required modules
        from clients.bybit_helpers import get_all_positions_with_client, get_all_open_orders
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        from utils.order_identifier import OrderIdentifier
        
        # Step 1: Get current positions
        print("📊 Getting current positions...")
        main_positions = await get_all_positions_with_client(bybit_client)
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        mirror_open = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions_with_client(bybit_client_2)
            mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        print(f"✅ Found {len(main_open)} main positions, {len(mirror_open)} mirror positions")
        
        # Step 2: Create monitor data structures
        monitors_to_add = {}
        
        # Process main account positions
        print("🔧 Processing main account positions...")
        all_orders = await get_all_open_orders()
        
        for position in main_open:
            monitor_data = await create_monitor_data(position, all_orders, "main")
            if monitor_data:
                symbol = monitor_data["symbol"]
                side = monitor_data["side"]
                monitor_key = f"{symbol}_{side}"
                monitors_to_add[monitor_key] = monitor_data
                print(f"  ✅ Created monitor for {symbol} {side} (main)")
        
        # Process mirror account positions
        if mirror_open:
            print("🪞 Processing mirror account positions...")
            # Get mirror orders
            from clients.bybit_helpers import api_call_with_retry
            mirror_orders = []
            for symbol in set(p.get('symbol') for p in mirror_open):
                try:
                    response = await api_call_with_retry(
                        lambda: bybit_client_2.get_open_orders(category="linear", symbol=symbol)
                    )
                    if response and response.get("retCode") == 0:
                        orders = response.get("result", {}).get("list", [])
                        mirror_orders.extend(orders)
                except Exception as e:
                    logger.warning(f"Could not get orders for mirror {symbol}: {e}")
            
            for position in mirror_open:
                monitor_data = await create_monitor_data(position, mirror_orders, "mirror")
                if monitor_data:
                    symbol = monitor_data["symbol"]
                    side = monitor_data["side"]
                    monitor_key = f"{symbol}_{side}_MIRROR"
                    monitors_to_add[monitor_key] = monitor_data
                    print(f"  ✅ Created monitor for {symbol} {side} (mirror)")
        
        # Step 3: Add monitors to the bot's persistence
        print(f"💾 Adding {len(monitors_to_add)} monitors to bot persistence...")
        
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        # Load current bot data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Add Enhanced TP/SL monitors to bot_data
        if 'bot_data' not in data:
            data['bot_data'] = {}
        
        if 'enhanced_tp_sl_monitors' not in data['bot_data']:
            data['bot_data']['enhanced_tp_sl_monitors'] = {}
        
        data['bot_data']['enhanced_tp_sl_monitors'].update(monitors_to_add)
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✅ Successfully added {len(monitors_to_add)} monitors to bot persistence")
        
        # Step 4: Send signal to running bot to reload monitors
        # Create a signal file that the bot can check
        signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(f"{time.time()}\n{len(monitors_to_add)} monitors added\n")
        
        print("📡 Signal file created for bot to reload monitors")
        
        print("\n" + "=" * 70)
        print("🎉 ENHANCED TP/SL MONITORING ACTIVATION COMPLETE")
        print("=" * 70)
        print(f"✅ Main account positions: {len(main_open)}")
        print(f"✅ Mirror account positions: {len(mirror_open)}")
        print(f"✅ Total monitors added: {len(monitors_to_add)}")
        print("✅ Bot persistence updated")
        print("✅ Signal sent to running bot")
        print("=" * 70)
        print("🚀 The running bot should now have Enhanced TP/SL monitoring active!")
        
    except Exception as e:
        logger.error(f"❌ Error activating live monitoring: {e}")
        import traceback
        traceback.print_exc()

async def create_monitor_data(position: Dict, orders: List[Dict], account_type: str) -> Dict:
    """Create monitor data for a position"""
    try:
        from utils.order_identifier import OrderIdentifier
        
        symbol = position.get('symbol')
        side = position.get('side')
        size = Decimal(str(position.get('size', 0)))
        avg_price = Decimal(str(position.get('avgPrice', 0)))
        
        if size == 0 or avg_price == 0:
            return None
        
        # Filter orders for this position
        position_orders = [o for o in orders if o.get('symbol') == symbol]
        
        # Group orders by type
        grouped_orders = OrderIdentifier.group_orders_by_type(position_orders, position)
        tp_orders = grouped_orders.get('tp_orders', [])
        sl_orders = grouped_orders.get('sl_orders', [])
        limit_orders = grouped_orders.get('limit_orders', [])
        
        # Determine approach based on TP order count
        if len(tp_orders) >= 4:
            approach = "CONSERVATIVE"
        elif len(tp_orders) >= 1:
            approach = "FAST"
        else:
            approach = "CONSERVATIVE"  # Default
        
        # Calculate TP prices and percentages from existing orders
        tp_prices = []
        tp_percentages = []
        
        if tp_orders:
            tp_orders_sorted = sorted(tp_orders, key=lambda x: abs(float(x.get('price', x.get('triggerPrice', 0))) - float(avg_price)))
            
            for tp_order in tp_orders_sorted:
                tp_price = Decimal(str(tp_order.get('price', tp_order.get('triggerPrice', 0))))
                tp_qty = Decimal(str(tp_order.get('qty', 0)))
                
                if tp_price > 0 and tp_qty > 0:
                    tp_prices.append(tp_price)
                    tp_percentage = (tp_qty / size) * 100
                    tp_percentages.append(tp_percentage)
        
        # Default TP structure if no valid TPs found
        if not tp_prices:
            if approach == "CONSERVATIVE":
                tp_percentages = [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")]
                if side == "Buy":
                    tp_prices = [avg_price * Decimal("1.02"), avg_price * Decimal("1.04"), 
                               avg_price * Decimal("1.06"), avg_price * Decimal("1.08")]
                else:
                    tp_prices = [avg_price * Decimal("0.98"), avg_price * Decimal("0.96"),
                               avg_price * Decimal("0.94"), avg_price * Decimal("0.92")]
            else:
                tp_percentages = [Decimal("100")]
                if side == "Buy":
                    tp_prices = [avg_price * Decimal("1.02")]
                else:
                    tp_prices = [avg_price * Decimal("0.98")]
        
        # Get SL price
        sl_price = avg_price * Decimal("0.95") if side == "Buy" else avg_price * Decimal("1.05")
        if sl_orders:
            sl_price = Decimal(str(sl_orders[0].get('triggerPrice', sl_orders[0].get('price', sl_price))))
        
        # Create monitor data
        monitor_data = {
            "symbol": symbol,
            "side": side,
            "position_size": size,
            "remaining_size": size,
            "entry_price": avg_price,
            "tp_prices": tp_prices,
            "tp_percentages": tp_percentages,
            "sl_price": sl_price,
            "chat_id": 5634913742,  # Default chat ID
            "approach": approach,
            "account_type": account_type,
            "phase": "PROFIT_TAKING" if len(tp_orders) < 4 else "BUILDING",
            "tp1_hit": len(tp_orders) < 4,
            "sl_moved_to_be": False,
            "created_at": time.time(),
            "last_check": time.time(),
            "tp_orders": [],
            "sl_order": {},
            "limit_orders": [],
            "monitoring_active": True
        }
        
        return monitor_data
        
    except Exception as e:
        logger.error(f"❌ Error creating monitor data for {symbol} {side}: {e}")
        return None

async def main():
    """Main function"""
    await activate_live_monitoring()

if __name__ == "__main__":
    asyncio.run(main())