#!/usr/bin/env python3
"""
Add monitoring to an existing position that was opened manually
Note: This will only monitor TP/SL hits, not limit order fills (since we don't have the order IDs)
"""
import asyncio
import logging
import pickle
import time
from datetime import datetime

from config.constants import *
from clients.bybit_helpers import get_position_info, get_all_open_orders
from telegram import Bot
from telegram.ext import Application

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def add_monitoring_for_position(symbol: str, chat_id: int, approach: str = "conservative"):
    """
    Add monitoring to an existing position
    
    Args:
        symbol: Trading symbol (e.g., 'GALAUSDT')
        chat_id: Your Telegram chat ID
        approach: Trading approach ('conservative' or 'fast')
    """
    logger.info(f"Adding monitoring for {symbol}...")
    
    try:
        # Check if position exists
        positions = await get_position_info(symbol)
        active_position = None
        
        for pos in positions:
            if float(pos.get('size', 0)) > 0:
                active_position = pos
                break
        
        if not active_position:
            logger.error(f"❌ No active position found for {symbol}")
            return False
        
        logger.info(f"✅ Found position: {active_position.get('side')} {active_position.get('size')} @ ${active_position.get('avgPrice')}")
        
        # Get open orders
        all_orders = await get_all_open_orders()
        symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]
        
        # Categorize orders
        limit_orders = []
        tp_orders = []
        sl_order = None
        
        for order in symbol_orders:
            order_type = order.get('orderType')
            reduce_only = order.get('reduceOnly', False)
            stop_type = order.get('stopOrderType', '')
            link_id = order.get('orderLinkId', '')
            
            if order_type == 'Limit' and not reduce_only:
                limit_orders.append(order)
            elif stop_type == 'TakeProfit' or 'TP' in link_id:
                tp_orders.append(order)
            elif stop_type in ['StopLoss', 'Stop'] or 'SL' in link_id:
                sl_order = order
        
        logger.info(f"📋 Found orders: {len(limit_orders)} limits, {len(tp_orders)} TPs, {'1' if sl_order else '0'} SL")
        
        # Load bot data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            bot_data = pickle.load(f)
        
        # Create chat_data entry if not exists
        chat_data_key = str(chat_id)
        if chat_data_key not in bot_data:
            bot_data[chat_data_key] = {}
        
        chat_data = bot_data[chat_data_key]
        
        # Set up monitoring data
        chat_data[SYMBOL] = symbol
        chat_data[SIDE] = active_position.get('side')
        chat_data[TRADING_APPROACH] = approach
        chat_data[PRIMARY_ENTRY_PRICE] = active_position.get('avgPrice')
        chat_data[LAST_KNOWN_POSITION_SIZE] = active_position.get('size')
        
        # Store order IDs (what we can find)
        if approach == "conservative":
            # For limit orders - we can try to track them
            limit_ids = [o.get('orderId') for o in limit_orders if o.get('orderId')]
            chat_data[LIMIT_ORDER_IDS] = limit_ids
            chat_data[CONSERVATIVE_LIMITS_FILLED] = []  # Start with empty
            
            # For TP orders
            tp_ids = [o.get('orderId') for o in tp_orders if o.get('orderId')]
            chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_ids
            
            # For SL order
            if sl_order:
                chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_order.get('orderId')
            
            logger.info(f"✅ Set up conservative monitoring with {len(limit_ids)} limits")
        else:
            # Fast approach
            if tp_orders:
                chat_data["tp_order_id"] = tp_orders[0].get('orderId')
            if sl_order:
                chat_data[SL_ORDER_ID] = sl_order.get('orderId')
            
            logger.info(f"✅ Set up fast approach monitoring")
        
        # Create monitor task entry
        monitor_key = f"{chat_id}_{symbol}_{approach}"
        if 'monitor_tasks' not in bot_data:
            bot_data['monitor_tasks'] = {}
        
        bot_data['monitor_tasks'][monitor_key] = {
            'chat_id': chat_id,
            'symbol': symbol,
            'approach': approach,
            'monitoring_mode': 'FULL',
            'started_at': time.time(),
            'active': True
        }
        
        # Set active monitor task
        chat_data[ACTIVE_MONITOR_TASK] = {
            'active': True,
            'symbol': symbol,
            'approach': approach,
            'chat_id': chat_id,
            'started_at': time.time(),
            'monitoring_mode': 'FULL'
        }
        
        # Save bot data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(bot_data, f)
        
        logger.info(f"✅ Monitoring added successfully!")
        logger.info(f"📊 Monitor key: {monitor_key}")
        logger.info(f"🔄 The bot will now track this position")
        
        # Note about limitations
        if approach == "conservative" and limit_orders:
            logger.warning("\n⚠️ IMPORTANT LIMITATION:")
            logger.warning("Since these orders were placed manually, limit fill notifications")
            logger.warning("may not work perfectly. The bot works best with orders it places itself.")
            logger.warning("\nYou WILL get notifications for:")
            logger.warning("- TP hits (all levels)")
            logger.warning("- SL hit")
            logger.warning("- Position closure")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding monitoring: {e}", exc_info=True)
        return False

async def main():
    """Main function to add monitoring"""
    # Configuration - CHANGE THESE VALUES
    SYMBOL = "GALAUSDT"  # Change to your symbol
    CHAT_ID = 123456789  # Change to your Telegram chat ID
    APPROACH = "conservative"  # or "fast"
    
    logger.info("=" * 60)
    logger.info("ADDING MONITORING TO EXISTING POSITION")
    logger.info("=" * 60)
    logger.info(f"Symbol: {SYMBOL}")
    logger.info(f"Chat ID: {CHAT_ID}")
    logger.info(f"Approach: {APPROACH}")
    
    if CHAT_ID == 123456789:
        logger.error("❌ Please update CHAT_ID in the script first!")
        logger.info("\nTo find your chat ID:")
        logger.info("1. Send any message to your bot")
        logger.info("2. Check the bot logs or use /dashboard")
        logger.info("3. Your chat ID will be shown")
        return
    
    success = await add_monitoring_for_position(SYMBOL, CHAT_ID, APPROACH)
    
    if success:
        logger.info("\n✅ SUCCESS! Monitoring has been added.")
        logger.info("\nNext steps:")
        logger.info("1. Run /dashboard to verify monitoring is active")
        logger.info("2. You'll now get notifications for TP/SL hits")
        logger.info("3. For future trades, use /trade for full functionality")
    else:
        logger.info("\n❌ Failed to add monitoring")
        logger.info("Please check the errors above")

if __name__ == "__main__":
    asyncio.run(main())