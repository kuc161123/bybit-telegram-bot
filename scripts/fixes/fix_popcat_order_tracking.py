#!/usr/bin/env python3
"""
Fix POPCAT order tracking - ensure limit order IDs are properly stored for monitoring
"""
import os
import pickle
import logging
import asyncio
from datetime import datetime
from clients.bybit_helpers import get_all_open_orders

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def fix_popcat_order_tracking():
    """Fix POPCAT order tracking by populating limit order IDs"""
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    # Create backup
    backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{pickle_file}"
    
    try:
        # Get POPCAT orders from Bybit
        all_orders = await get_all_open_orders()
        popcat_orders = [o for o in all_orders if o.get('symbol') == 'POPCATUSDT']
        
        # Find limit buy orders
        limit_order_ids = []
        for order in popcat_orders:
            if order.get('orderType') == 'Limit' and order.get('side') == 'Buy':
                limit_order_ids.append(order.get('orderId'))
                logger.info(f"Found limit buy order: {order.get('orderId')[:8]}... Price: ${order.get('price')}")
        
        if not limit_order_ids:
            logger.warning("No limit buy orders found for POPCATUSDT")
            return False
        
        # Load current data
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        # Backup
        with open(backup_file, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"✅ Backup created: {backup_file}")
        
        # Find POPCAT chat data
        chat_data_dict = data.get('chat_data', {})
        fixed = False
        
        for chat_id, chat_data in chat_data_dict.items():
            if isinstance(chat_data, dict):
                symbol = chat_data.get('symbol', '')
                if symbol == 'POPCATUSDT':
                    logger.info(f"Found POPCATUSDT data in chat {chat_id}")
                    
                    # Add limit order IDs
                    chat_data['limit_order_ids'] = limit_order_ids
                    chat_data['conservative_limits_filled'] = chat_data.get('conservative_limits_filled', [])
                    chat_data['trading_approach'] = 'conservative'  # Ensure approach is set
                    
                    logger.info(f"✅ Added {len(limit_order_ids)} limit order IDs to POPCATUSDT monitoring")
                    logger.info(f"   Order IDs: {[oid[:8] + '...' for oid in limit_order_ids]}")
                    fixed = True
        
        if fixed:
            # Save updated data
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"✅ Fixed POPCATUSDT order tracking")
            logger.info(f"ℹ️ The monitor will now check these limit orders for fills")
        else:
            logger.warning("⚠️ Could not find POPCATUSDT chat data to update")
            
    except Exception as e:
        logger.error(f"❌ Error fixing POPCAT order tracking: {e}", exc_info=True)
        return False
    
    return True

async def main():
    logger.info("🔧 Starting POPCAT order tracking fix...")
    success = await fix_popcat_order_tracking()
    if success:
        logger.info("✅ Fix completed successfully!")
    else:
        logger.info("❌ Fix failed - check errors above")

if __name__ == "__main__":
    asyncio.run(main())