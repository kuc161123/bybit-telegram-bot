#!/usr/bin/env python3
"""
Restore Enhanced TP/SL monitors for existing positions
"""
import asyncio
import logging
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def restore_monitors():
    """Restore Enhanced TP/SL monitors for all open positions"""
    try:
        # Import required modules
        from clients.bybit_helpers import get_all_positions, get_open_orders
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from shared.state import get_application
        
        logger.info("🔧 Restoring Enhanced TP/SL Monitors...")
        
        # Get application context for chat ID
        app = get_application()
        default_chat_id = None
        
        # Try to get a chat ID from the application
        if app and hasattr(app, 'chat_data') and app.chat_data:
            # Get the first available chat ID
            default_chat_id = list(app.chat_data.keys())[0]
            logger.info(f"✅ Found default chat ID: {default_chat_id}")
        else:
            logger.warning("⚠️ No chat ID found in application context")
            # Try to get from environment or use a fallback
            import os
            default_chat_id = int(os.getenv('DEFAULT_CHAT_ID', '5634913742'))
            logger.info(f"✅ Using fallback chat ID: {default_chat_id}")
        
        # Get current positions
        positions = await get_all_positions()
        if not positions:
            logger.info("📋 No open positions found")
            return
        
        logger.info(f"📊 Found {len(positions)} open positions")
        
        # Get all open orders
        all_orders = await get_open_orders()
        
        restored_count = 0
        
        for position in positions:
            symbol = position.get('symbol', '')
            side = position.get('side', '')
            size = Decimal(str(position.get('size', '0')))
            avg_price = Decimal(str(position.get('avgPrice', '0')))
            
            if not symbol or not side or size == 0:
                continue
            
            monitor_key = f"{symbol}_{side}"
            
            # Check if monitor already exists
            if monitor_key in enhanced_tp_sl_manager.position_monitors:
                logger.info(f"✅ Monitor already exists for {symbol} {side}")
                continue
            
            # Find TP/SL orders for this position
            tp_orders = []
            sl_order = None
            
            for order in all_orders:
                if order.get('symbol') != symbol:
                    continue
                
                order_link_id = order.get('orderLinkId', '')
                if not order_link_id.startswith('BOT_'):
                    continue
                
                # Check if it's a TP or SL order
                if 'TP' in order_link_id and order.get('reduceOnly'):
                    tp_orders.append({
                        'order_id': order.get('orderId'),
                        'order_link_id': order_link_id,
                        'price': Decimal(str(order.get('price', '0'))),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'original_quantity': Decimal(str(order.get('qty', '0')))
                    })
                elif 'SL' in order_link_id and order.get('reduceOnly'):
                    sl_order = {
                        'order_id': order.get('orderId'),
                        'order_link_id': order_link_id,
                        'price': Decimal(str(order.get('triggerPrice', order.get('price', '0')))),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'original_quantity': Decimal(str(order.get('qty', '0')))
                    }
            
            # Sort TP orders by price
            tp_orders.sort(key=lambda x: x['price'], reverse=(side == 'Buy'))
            
            # Determine approach based on number of TPs
            if len(tp_orders) >= 3:
                approach = 'conservative'
            else:
                approach = 'fast'
            
            # Create monitor data
            monitor_data = {
                'symbol': symbol,
                'side': side,
                'chat_id': default_chat_id,
                'approach': approach,
                'position_size': size,
                'remaining_size': size,
                'entry_price': avg_price,
                'tp_orders': tp_orders,
                'sl_order': sl_order,
                'limit_orders': [],
                'phase': 'MONITORING',
                'created_at': position.get('createdTime', 0) / 1000,  # Convert ms to seconds
                'account_type': 'main'
            }
            
            # Add to monitors
            enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
            
            logger.info(f"✅ Restored monitor for {symbol} {side}:")
            logger.info(f"   - Approach: {approach}")
            logger.info(f"   - TP Orders: {len(tp_orders)}")
            logger.info(f"   - SL Order: {'Yes' if sl_order else 'No'}")
            logger.info(f"   - Chat ID: {default_chat_id}")
            
            restored_count += 1
        
        logger.info(f"\n✅ Restored {restored_count} monitors")
        
        # Start monitoring if not already running
        if restored_count > 0:
            logger.info("\n🚀 Starting monitoring loops for restored positions...")
            for monitor_key in enhanced_tp_sl_manager.position_monitors.keys():
                symbol, side = monitor_key.split('_')
                # Create monitoring task
                monitor_task = asyncio.create_task(enhanced_tp_sl_manager._run_monitor_loop(symbol, side))
                logger.info(f"✅ Started monitoring for {symbol} {side}")
        
        logger.info("\n✅ Monitor restoration completed!")
        
    except Exception as e:
        logger.error(f"❌ Error restoring monitors: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(restore_monitors())