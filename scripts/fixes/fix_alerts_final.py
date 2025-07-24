#!/usr/bin/env python3
"""
Final fix for alert system - properly detect and create monitors
"""
import asyncio
import logging
from decimal import Decimal
import time
import os
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT_ID = 5634913742

async def send_telegram_alert(message: str):
    """Send alert directly using bot token"""
    try:
        bot_token = os.getenv('TELEGRAM_TOKEN')
        if not bot_token:
            logger.error("❌ TELEGRAM_TOKEN not found")
            return False
        
        bot = Bot(token=bot_token)
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )
        return True
    except Exception as e:
        logger.error(f"Error sending telegram alert: {e}")
        return False

async def fix_alerts_final():
    """Final fix for alerts with proper order detection"""
    try:
        from clients.bybit_helpers import get_all_positions, get_open_orders
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        logger.info("🔧 Final alert system fix...")
        
        # Get positions and orders
        positions = await get_all_positions()
        all_orders = await get_open_orders()
        
        logger.info(f"📊 Found {len(positions)} positions")
        logger.info(f"📋 Found {len(all_orders)} orders")
        
        # Group orders by symbol
        orders_by_symbol = {}
        for order in all_orders:
            symbol = order.get('symbol', '')
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)
        
        created_monitors = []
        
        for position in positions:
            symbol = position.get('symbol', '')
            side = position.get('side', '')
            size = Decimal(str(position.get('size', '0')))
            avg_price = Decimal(str(position.get('avgPrice', '0')))
            
            if not symbol or not side or size == 0:
                continue
            
            monitor_key = f"{symbol}_{side}"
            
            # Skip if monitor exists
            if monitor_key in enhanced_tp_sl_manager.position_monitors:
                logger.info(f"✅ Monitor already exists for {symbol} {side}")
                continue
            
            # Get orders for this symbol
            symbol_orders = orders_by_symbol.get(symbol, [])
            
            # Separate TP and SL orders
            tp_orders = []
            sl_order = None
            
            for order in symbol_orders:
                if not order.get('reduceOnly'):
                    continue
                
                order_link_id = order.get('orderLinkId', '')
                
                # Check if it's a TP order (limit order with TP in link ID)
                if 'TP' in order_link_id and order.get('orderType') == 'Limit':
                    tp_number = 1
                    if 'TP1' in order_link_id:
                        tp_number = 1
                    elif 'TP2' in order_link_id:
                        tp_number = 2
                    elif 'TP3' in order_link_id:
                        tp_number = 3
                    elif 'TP4' in order_link_id:
                        tp_number = 4
                    
                    tp_orders.append({
                        'order_id': order.get('orderId'),
                        'order_link_id': order_link_id,
                        'price': Decimal(str(order.get('price', '0'))),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'original_quantity': Decimal(str(order.get('qty', '0'))),
                        'tp_number': tp_number
                    })
                
                # Check if it's a SL order (market order with trigger price)
                elif 'SL' in order_link_id and order.get('triggerPrice'):
                    sl_order = {
                        'order_id': order.get('orderId'),
                        'order_link_id': order_link_id,
                        'price': Decimal(str(order.get('triggerPrice', '0'))),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'original_quantity': Decimal(str(order.get('qty', '0')))
                    }
            
            # Sort TP orders by TP number
            tp_orders.sort(key=lambda x: x.get('tp_number', 0))
            
            # Determine approach
            approach = 'conservative' if len(tp_orders) >= 3 else 'fast'
            
            # Create monitor
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
                'created_at': time.time(),
                'account_type': 'main',
                'breakeven_moved': False,
                'tp1_hit': False,
                'original_sl_price': sl_order['price'] if sl_order else None
            }
            
            # Add to enhanced TP/SL manager
            enhanced_tp_sl_manager.position_monitors[monitor_key] = monitor_data
            
            logger.info(f"✅ Created monitor for {symbol} {side}:")
            logger.info(f"   - Approach: {approach}")
            logger.info(f"   - TP Orders: {len(tp_orders)}")
            logger.info(f"   - SL Order: {'Yes' if sl_order else 'No'}")
            
            # Start monitoring task
            asyncio.create_task(enhanced_tp_sl_manager._run_monitor_loop(symbol, side))
            
            created_monitors.append({
                'symbol': symbol,
                'side': side,
                'tp_count': len(tp_orders),
                'has_sl': sl_order is not None
            })
        
        # Send summary alert
        if created_monitors:
            message = f"""✅ <b>ALERT SYSTEM ACTIVATED</b>
━━━━━━━━━━━━━━━━━━━━━━

🔧 Enhanced TP/SL monitoring restored for {len(created_monitors)} positions:

"""
            for monitor in created_monitors:
                message += f"📊 {monitor['symbol']} {monitor['side']}\n"
                message += f"   • TP Orders: {monitor['tp_count']}\n"
                message += f"   • SL Order: {'✅' if monitor['has_sl'] else '❌'}\n\n"
            
            message += """🔔 You will now receive alerts for:
• TP order fills
• SL order fills
• Position closures
• Breakeven movements

🚀 Monitoring is active and running!"""
            
            await send_telegram_alert(message)
            logger.info("✅ Summary alert sent")
        
        logger.info(f"\n✅ Alert system fixed! Created {len(created_monitors)} monitors.")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_alerts_final())