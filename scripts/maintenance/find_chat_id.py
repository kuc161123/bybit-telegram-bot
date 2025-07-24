#!/usr/bin/env python3
"""
Find valid chat ID from pickle file
"""
import pickle
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pkl_path, 'rb') as f:
        data = pickle.load(f)
    
    # Look for chat IDs in various places
    chat_ids = set()
    
    # Check chat_data
    if 'chat_data' in data:
        for chat_id in data['chat_data'].keys():
            chat_ids.add(chat_id)
            logger.info(f"Found chat ID in chat_data: {chat_id}")
    
    # Check user_data
    if 'user_data' in data:
        for user_id in data['user_data'].keys():
            logger.info(f"Found user ID in user_data: {user_id}")
    
    # Check bot_data for any stored chat IDs
    if 'bot_data' in data:
        bot_data = data['bot_data']
        
        # Check settings
        if 'settings' in bot_data:
            for key, settings in bot_data['settings'].items():
                if isinstance(key, int):
                    chat_ids.add(key)
                    logger.info(f"Found chat ID in settings: {key}")
        
        # Check monitor tasks for chat IDs
        if 'monitor_tasks' in bot_data:
            for key, monitor in bot_data['monitor_tasks'].items():
                if 'chat_id' in monitor:
                    chat_ids.add(monitor['chat_id'])
                    logger.info(f"Found chat ID in monitor: {monitor['chat_id']}")
        
        # Check positions data
        if 'positions' in bot_data:
            for pos_key, pos_data in bot_data['positions'].items():
                if isinstance(pos_data, dict) and 'chat_id' in pos_data:
                    chat_ids.add(pos_data['chat_id'])
                    logger.info(f"Found chat ID in position: {pos_data['chat_id']}")
    
    if chat_ids:
        logger.info(f"\n✅ Found {len(chat_ids)} unique chat ID(s):")
        for chat_id in sorted(chat_ids):
            logger.info(f"   - {chat_id}")
        
        # Get the most common or first valid chat ID
        valid_chat_id = list(sorted(chat_ids))[0]
        logger.info(f"\n🎯 Recommended chat ID to use: {valid_chat_id}")
    else:
        logger.warning("❌ No chat IDs found in pickle file")
        
except Exception as e:
    logger.error(f"Error reading pickle file: {e}")
    import traceback
    traceback.print_exc()