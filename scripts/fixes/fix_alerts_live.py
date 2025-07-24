#!/usr/bin/env python3
"""
Fix alerts for running bot without restart
This script will:
1. Check current Enhanced TP/SL manager state
2. Create monitors for positions that don't have them
3. Ensure alerts are working
"""
import asyncio
import logging
import pickle
from decimal import Decimal
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def fix_alerts_live():
    """Fix alerts without restarting the bot"""
    try:
        # Import required modules
        from clients.bybit_helpers import get_all_positions, get_open_orders
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from utils.alert_helpers import send_simple_alert
        
        logger.info("🔧 Fixing alerts for running bot...")
        
        # Use the known chat ID
        CHAT_ID = 5634913742
        
        # Test alert system first
        logger.info("📤 Testing alert system...")
        test_message = "🧪 <b>ALERT SYSTEM TEST</b>\n\nThis is a test to verify alerts are working after the fix."
        
        try:
            result = await send_simple_alert(CHAT_ID, test_message, "test")
            if result:
                logger.info("✅ Alert system is working!")
            else:
                logger.error("❌ Alert system test failed")
        except Exception as e:
            logger.error(f"❌ Alert test error: {e}")
        
        # Get current positions
        positions = await get_all_positions()
        if not positions:
            logger.info("📋 No open positions found")
            return
        
        logger.info(f"📊 Found {len(positions)} open positions")
        
        # Check existing monitors
        existing_monitors = len(enhanced_tp_sl_manager.position_monitors)
        logger.info(f"📍 Existing Enhanced TP/SL monitors: {existing_monitors}")
        
        # Get all open orders to determine approach and find TP/SL orders
        all_orders = await get_open_orders()
        
        created_count = 0
        
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
                # Update chat ID if missing
                monitor = enhanced_tp_sl_manager.position_monitors[monitor_key]
                if not monitor.get('chat_id') or monitor.get('chat_id') == 'NO_CHAT_ID':
                    monitor['chat_id'] = CHAT_ID
                    logger.info(f"   Updated chat ID to {CHAT_ID}")
                continue
            
            logger.info(f"⚠️ No monitor for {symbol} {side}, creating one...")
            
            # Find TP/SL orders for this position
            tp_orders = []
            sl_order = None
            
            for order in all_orders:
                if order.get('symbol') != symbol:
                    continue
                
                order_link_id = order.get('orderLinkId', '')
                # Accept all orders for now (not just BOT_ prefixed)
                
                # Check if it's a TP or SL order
                if order.get('reduceOnly') and order.get('orderStatus') == 'New':
                    trigger_price = order.get('triggerPrice', '')
                    if trigger_price:  # It's a stop order (TP or SL)
                        order_side = order.get('side', '')
                        # For Buy position: TP is Sell above entry, SL is Sell below entry
                        # For Sell position: TP is Buy below entry, SL is Buy above entry
                        if side == 'Buy':
                            if order_side == 'Sell':
                                trigger_price_decimal = Decimal(str(trigger_price))
                                if trigger_price_decimal > avg_price:
                                    # It's a TP
                                    tp_orders.append({
                                        'order_id': order.get('orderId'),
                                        'order_link_id': order_link_id,
                                        'price': trigger_price_decimal,
                                        'quantity': Decimal(str(order.get('qty', '0'))),
                                        'original_quantity': Decimal(str(order.get('qty', '0')))
                                    })
                                else:
                                    # It's a SL
                                    sl_order = {
                                        'order_id': order.get('orderId'),
                                        'order_link_id': order_link_id,
                                        'price': trigger_price_decimal,
                                        'quantity': Decimal(str(order.get('qty', '0'))),
                                        'original_quantity': Decimal(str(order.get('qty', '0')))
                                    }
                        else:  # Sell position
                            if order_side == 'Buy':
                                trigger_price_decimal = Decimal(str(trigger_price))
                                if trigger_price_decimal < avg_price:
                                    # It's a TP
                                    tp_orders.append({
                                        'order_id': order.get('orderId'),
                                        'order_link_id': order_link_id,
                                        'price': trigger_price_decimal,
                                        'quantity': Decimal(str(order.get('qty', '0'))),
                                        'original_quantity': Decimal(str(order.get('qty', '0')))
                                    })
                                else:
                                    # It's a SL
                                    sl_order = {
                                        'order_id': order.get('orderId'),
                                        'order_link_id': order_link_id,
                                        'price': trigger_price_decimal,
                                        'quantity': Decimal(str(order.get('qty', '0'))),
                                        'original_quantity': Decimal(str(order.get('qty', '0')))
                                    }
            
            # Sort TP orders by price
            tp_orders.sort(key=lambda x: x['price'], reverse=(side == 'Buy'))
            
            # Determine approach based on number of TPs
            if len(tp_orders) >= 3:
                approach = 'conservative'
            elif len(tp_orders) == 1:
                approach = 'fast'
            else:
                approach = 'standard'
            
            # Create monitor data
            monitor_data = {
                'symbol': symbol,
                'side': side,
                'chat_id': CHAT_ID,
                'approach': approach,
                'position_size': size,
                'remaining_size': size,
                'entry_price': avg_price,
                'tp_orders': tp_orders,
                'sl_order': sl_order,
                'limit_orders': [],
                'phase': 'MONITORING',
                'created_at': int(position.get('createdTime', '0')) / 1000 if position.get('createdTime') else time.time(),  # Convert ms to seconds
                'account_type': 'main',
                'breakeven_moved': False,
                'tp1_hit': False
            }
            
            # Add to monitors
            enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
            
            logger.info(f"✅ Created monitor for {symbol} {side}:")
            logger.info(f"   - Approach: {approach}")
            logger.info(f"   - TP Orders: {len(tp_orders)}")
            logger.info(f"   - SL Order: {'Yes' if sl_order else 'No'}")
            logger.info(f"   - Chat ID: {CHAT_ID}")
            
            # Start monitoring task
            monitor_task = asyncio.create_task(enhanced_tp_sl_manager._run_monitor_loop(symbol, side))
            logger.info(f"   - Started monitoring task")
            
            created_count += 1
            
            # Send alert about monitor creation
            alert_message = f"""🔧 <b>MONITOR RESTORED</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} {'📈' if side == 'Buy' else '📉'} {side}

✅ Enhanced TP/SL monitoring restored
🎯 Approach: {approach}
📍 Entry: ${avg_price:.6f}
📦 Size: {size:.6f}

📋 Orders Found:
• TP Orders: {len(tp_orders)}
• SL Order: {'Yes' if sl_order else 'No'}

🔄 Monitoring active - Alerts enabled"""
            
            try:
                await send_simple_alert(CHAT_ID, alert_message, "monitor_restored")
            except Exception as e:
                logger.error(f"Error sending restoration alert: {e}")
        
        # Summary
        total_monitors = len(enhanced_tp_sl_manager.position_monitors)
        logger.info(f"\n📊 Summary:")
        logger.info(f"   - Positions: {len(positions)}")
        logger.info(f"   - Monitors created: {created_count}")
        logger.info(f"   - Total monitors: {total_monitors}")
        
        if total_monitors == len(positions):
            logger.info("✅ All positions now have monitors!")
            
            # Send summary alert
            summary_message = f"""✅ <b>ALERT SYSTEM FIXED</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 Monitoring Status:
• Positions: {len(positions)}
• Active Monitors: {total_monitors}
• New Monitors: {created_count}

✅ All positions are now being monitored
🔔 Alerts are enabled and working

You will now receive alerts for:
• TP hits
• SL hits  
• Limit fills
• Position closures"""
            
            try:
                await send_simple_alert(CHAT_ID, summary_message, "system_fixed")
            except Exception as e:
                logger.error(f"Error sending summary alert: {e}")
        else:
            logger.warning(f"⚠️ Monitor count mismatch: {total_monitors} monitors for {len(positions)} positions")
        
        logger.info("\n✅ Alert fix completed!")
        
    except Exception as e:
        logger.error(f"❌ Error fixing alerts: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_alerts_live())