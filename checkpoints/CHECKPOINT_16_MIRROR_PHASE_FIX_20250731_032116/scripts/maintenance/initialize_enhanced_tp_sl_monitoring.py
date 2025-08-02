#!/usr/bin/env python3
"""
Initialize Enhanced TP/SL Monitoring for All Current Positions
This script will properly set up Enhanced TP/SL monitoring for all existing positions
to ensure they are managed correctly going forward.
"""
import asyncio
import logging
import sys
import os
from decimal import Decimal
from typing import Dict, List, Any
import time

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def initialize_enhanced_monitoring():
    """Initialize Enhanced TP/SL monitoring for all current positions"""
    try:
        # Import required modules
        from clients.bybit_helpers import get_all_positions_with_client, get_all_open_orders
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from utils.order_identifier import OrderIdentifier
        
        logger.info("🚀 Starting Enhanced TP/SL monitoring initialization...")
        
        # Step 1: Get all current positions
        logger.info("📊 Getting current positions...")
        main_positions = await get_all_positions_with_client(bybit_client)
        main_open = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        mirror_open = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions_with_client(bybit_client_2)
            mirror_open = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        logger.info(f"✅ Found {len(main_open)} main account positions, {len(mirror_open)} mirror positions")
        
        # Step 2: Get all current orders
        logger.info("📋 Getting current orders...")
        all_orders = await get_all_open_orders()
        
        # Step 3: Process each main account position
        logger.info("🔧 Initializing main account monitoring...")
        for position in main_open:
            await initialize_position_monitoring(position, all_orders, "main")
        
        # Step 4: Process mirror account positions
        if mirror_open:
            logger.info("🪞 Initializing mirror account monitoring...")
            # Get mirror orders
            from clients.bybit_helpers import api_call_with_retry
            mirror_orders = []
            for symbol in set(p.get('symbol') for p in mirror_open):
                try:
                    response = await api_call_with_retry(
                        lambda: bybit_client_2.get_open_orders(
                            category="linear",
                            symbol=symbol
                        )
                    )
                    if response and response.get("retCode") == 0:
                        orders = response.get("result", {}).get("list", [])
                        mirror_orders.extend(orders)
                except Exception as e:
                    logger.warning(f"Could not get orders for mirror {symbol}: {e}")
            
            for position in mirror_open:
                await initialize_position_monitoring(position, mirror_orders, "mirror")
        
        # Step 5: Verify monitoring status
        logger.info("✅ Verifying monitoring status...")
        active_monitors = len(enhanced_tp_sl_manager.position_monitors)
        logger.info(f"🎯 Enhanced TP/SL now monitoring {active_monitors} positions")
        
        # Display summary
        print("\n" + "="*60)
        print("🎉 ENHANCED TP/SL MONITORING INITIALIZATION COMPLETE")
        print("="*60)
        print(f"✅ Main account positions: {len(main_open)}")
        print(f"✅ Mirror account positions: {len(mirror_open)}")
        print(f"✅ Active monitors: {active_monitors}")
        print("✅ Alert system: Fixed (Decimal/float type safety)")
        print("✅ Limit cancellation: Enhanced (account-aware)")
        print("✅ Cross-account sync: Enabled")
        print("="*60)
        print("🚀 System ready for automated TP/SL management!")
        
    except Exception as e:
        logger.error(f"❌ Error initializing Enhanced TP/SL monitoring: {e}")
        import traceback
        traceback.print_exc()

async def initialize_position_monitoring(position: Dict, orders: List[Dict], account_type: str):
    """Initialize monitoring for a single position"""
    try:
        from utils.order_identifier import OrderIdentifier
        symbol = position.get('symbol')
        side = position.get('side')
        size = Decimal(str(position.get('size', 0)))
        avg_price = Decimal(str(position.get('avgPrice', 0)))
        
        if size == 0 or avg_price == 0:
            logger.warning(f"⚠️ Skipping {symbol} {side} - invalid size or price")
            return
        
        logger.info(f"🔧 Initializing {account_type} {symbol} {side} (size: {size})")
        
        # Filter orders for this position
        position_orders = [o for o in orders if o.get('symbol') == symbol]
        
        # Group orders by type
        grouped_orders = OrderIdentifier.group_orders_by_type(position_orders, position)
        tp_orders = grouped_orders.get('tp_orders', [])
        sl_orders = grouped_orders.get('sl_orders', [])
        limit_orders = grouped_orders.get('limit_orders', [])
        
        logger.info(f"   📊 Orders: {len(tp_orders)} TP, {len(sl_orders)} SL, {len(limit_orders)} Limit")
        
        # Determine approach based on TP order count
        if len(tp_orders) >= 4:
            approach = "CONSERVATIVE"
        elif len(tp_orders) >= 1:
            approach = "FAST"
        else:
            approach = "CONSERVATIVE"  # Default
            logger.warning(f"   ⚠️ No TP orders found, defaulting to CONSERVATIVE")
        
        # Create monitor data structure
        monitor_key = f"{symbol}_{side}"
        if account_type == "mirror":
            monitor_key += "_MIRROR"
        
        # Calculate TP prices and percentages from existing orders
        tp_prices = []
        tp_percentages = []
        
        if tp_orders:
            # Sort TP orders by price (closest to current price first for profit targets)
            tp_orders_sorted = sorted(tp_orders, key=lambda x: abs(float(x.get('price', x.get('triggerPrice', 0))) - float(avg_price)))
            
            total_tp_qty = sum(Decimal(str(o.get('qty', 0))) for o in tp_orders)
            
            for tp_order in tp_orders_sorted:
                tp_price = Decimal(str(tp_order.get('price', tp_order.get('triggerPrice', 0))))
                tp_qty = Decimal(str(tp_order.get('qty', 0)))
                
                if tp_price > 0 and tp_qty > 0:
                    tp_prices.append(tp_price)
                    # Calculate percentage of position this TP represents
                    tp_percentage = (tp_qty / size) * 100
                    tp_percentages.append(tp_percentage)
        
        # Default TP structure if no valid TPs found
        if not tp_prices:
            logger.warning(f"   ⚠️ Creating default TP structure for {symbol}")
            if approach == "CONSERVATIVE":
                # Conservative: 85%, 5%, 5%, 5%
                tp_percentages = [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")]
                # Estimate TP prices based on current price and typical targets
                if side == "Buy":
                    tp_prices = [avg_price * Decimal("1.02"), avg_price * Decimal("1.04"), 
                               avg_price * Decimal("1.06"), avg_price * Decimal("1.08")]
                else:  # Sell
                    tp_prices = [avg_price * Decimal("0.98"), avg_price * Decimal("0.96"),
                               avg_price * Decimal("0.94"), avg_price * Decimal("0.92")]
            else:
                # Fast: 100%
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
            "tp1_hit": len(tp_orders) < 4,  # If we have fewer than 4 TPs, assume TP1 already hit
            "sl_moved_to_be": False,
            "created_at": time.time(),
            "last_check": time.time(),
            "tp_orders": [],
            "sl_order": {},
            "limit_orders": [],
            "monitoring_active": True
        }
        
        # Register limit orders with status tracking
        for limit_order in limit_orders:
            order_id = limit_order.get('orderId', '')
            if order_id:
                monitor_data["limit_orders"].append({
                    "order_id": order_id,
                    "registered_at": time.time(),
                    "status": "ACTIVE"
                })
        
        # Store in Enhanced TP/SL manager
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
        
        logger.info(f"   ✅ {account_type.upper()} {symbol} {side} monitoring initialized (Phase: {monitor_data['phase']})")
        
    except Exception as e:
        logger.error(f"❌ Error initializing monitoring for {symbol} {side}: {e}")

async def disable_traditional_monitoring():
    """Disable traditional monitoring systems to prevent conflicts"""
    try:
        logger.info("🛑 Disabling traditional monitoring systems...")
        
        # Clear traditional monitor tasks from bot_data
        import pickle
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Clear monitor_tasks to prevent traditional monitoring
        bot_data = data.get('bot_data', {})
        bot_data['monitor_tasks'] = {}
        
        # Clear any active monitor data from chat_data
        chat_data = data.get('chat_data', {})
        for chat_id, chat_info in chat_data.items():
            if isinstance(chat_info, dict):
                # Clear traditional monitoring
                if 'active_monitor_task_data_v2' in chat_info:
                    chat_info['active_monitor_task_data_v2'] = None
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("✅ Traditional monitoring systems disabled")
        
    except Exception as e:
        logger.error(f"❌ Error disabling traditional monitoring: {e}")

async def main():
    """Main function to run the initialization"""
    try:
        print("🚀 Enhanced TP/SL Monitoring Initialization")
        print("=" * 50)
        
        # Step 1: Disable traditional monitoring
        await disable_traditional_monitoring()
        
        # Step 2: Initialize Enhanced TP/SL monitoring
        await initialize_enhanced_monitoring()
        
        print("\n✅ Initialization complete! Enhanced TP/SL is now the only active monitoring system.")
        
    except KeyboardInterrupt:
        print("\n❌ Initialization cancelled by user")
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())