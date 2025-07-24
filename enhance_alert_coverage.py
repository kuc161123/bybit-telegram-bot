#!/usr/bin/env python3
"""
Enhance Alert Coverage for All Positions
Ensures all positions have chat_id for alerts
"""

import asyncio
import logging
import sys
import os
import pickle
from typing import Dict, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import DEFAULT_ALERT_CHAT_ID

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def find_default_chat_id():
    """Find a default chat_id from existing positions"""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Find most common chat_id
        chat_ids = {}
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        for key, monitor in monitors.items():
            chat_id = monitor.get('chat_id')
            if chat_id:
                chat_ids[chat_id] = chat_ids.get(chat_id, 0) + 1
        
        if chat_ids:
            # Get most common chat_id
            default_chat_id = max(chat_ids, key=chat_ids.get)
            logger.info(f"Found default chat_id from existing positions: {default_chat_id}")
            return default_chat_id
        
        # Check user data for chat IDs
        user_data = data.get('user_data', {})
        if user_data:
            first_chat_id = list(user_data.keys())[0]
            logger.info(f"Found chat_id from user data: {first_chat_id}")
            return first_chat_id
            
    except Exception as e:
        logger.error(f"Error finding default chat_id: {e}")
    
    return None

async def fix_missing_chat_ids():
    """Fix positions missing chat_id"""
    try:
        # Find default chat_id
        default_chat_id = await find_default_chat_id()
        
        if not default_chat_id:
            if DEFAULT_ALERT_CHAT_ID:
                default_chat_id = DEFAULT_ALERT_CHAT_ID
                logger.info(f"Using DEFAULT_ALERT_CHAT_ID from settings: {default_chat_id}")
            else:
                logger.error("❌ No default chat_id found and DEFAULT_ALERT_CHAT_ID not set")
                logger.error("   Please set DEFAULT_ALERT_CHAT_ID in your .env file")
                return False
        
        # Load pickle data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        # Create backup
        backup_file = f'{pickle_file}.backup_alert_fix_{timestamp}'
        os.system(f'cp {pickle_file} {backup_file}')
        logger.info(f"✅ Created backup: {backup_file}")
        
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        # Fix missing chat_ids
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        fixed_count = 0
        
        for key, monitor in monitors.items():
            if not monitor.get('chat_id'):
                monitor['chat_id'] = default_chat_id
                fixed_count += 1
                logger.info(f"✅ Fixed chat_id for {monitor.get('symbol')} {monitor.get('side')}")
        
        if fixed_count > 0:
            # Save updated data
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"\n✅ Fixed {fixed_count} positions with missing chat_id")
            logger.info(f"✅ All positions now have chat_id: {default_chat_id}")
            
            # Create signal file for bot to reload
            with open('reload_monitors.signal', 'w') as f:
                f.write(str(time.time()))
            logger.info("✅ Created reload signal - bot will reload within 5 seconds")
            
            return True
        else:
            logger.info("✅ All positions already have chat_id - no fixes needed")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error fixing chat_ids: {e}")
        import traceback
        traceback.print_exc()
        return False

async def verify_alert_triggers():
    """Verify all alert trigger conditions"""
    logger.info("\n🔍 Verifying Alert Trigger Conditions...")
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        alert_ready = 0
        missing_tp = 0
        missing_sl = 0
        inactive = 0
        
        for key, monitor in monitors.items():
            symbol = monitor.get('symbol', 'Unknown')
            side = monitor.get('side', 'Unknown')
            status = monitor.get('status', 'unknown')
            
            if status != 'active':
                inactive += 1
                continue
            
            has_tp = bool(monitor.get('tp_orders'))
            has_sl = bool(monitor.get('sl_order'))
            has_chat = bool(monitor.get('chat_id'))
            
            if has_tp and has_sl and has_chat:
                alert_ready += 1
            else:
                if not has_tp:
                    missing_tp += 1
                    logger.warning(f"⚠️ {symbol} {side} - Missing TP orders")
                if not has_sl:
                    missing_sl += 1
                    logger.warning(f"⚠️ {symbol} {side} - Missing SL order")
        
        logger.info(f"\n📊 Alert Readiness Summary:")
        logger.info(f"   ✅ Alert Ready: {alert_ready}")
        logger.info(f"   ⚠️ Missing TP: {missing_tp}")
        logger.info(f"   ⚠️ Missing SL: {missing_sl}")
        logger.info(f"   ⏸️ Inactive: {inactive}")
        
        if missing_tp > 0 or missing_sl > 0:
            logger.warning("\n⚠️ Some positions missing TP/SL orders - alerts may not trigger properly")
            
    except Exception as e:
        logger.error(f"❌ Error verifying triggers: {e}")

async def create_alert_test_positions():
    """Create test data to verify each alert type"""
    logger.info("\n🧪 Alert Test Scenarios Available:")
    
    scenarios = {
        "test_tp_hit": "Simulate TP1 hit with 85% position reduction",
        "test_sl_hit": "Simulate SL hit with full position closure",
        "test_limit_fill": "Simulate limit order fill with position increase",
        "test_breakeven": "Simulate SL move to breakeven after TP1",
        "test_position_close": "Simulate position fully closed",
        "test_rebalance": "Simulate conservative rebalancing"
    }
    
    for scenario, description in scenarios.items():
        logger.info(f"   - {scenario}: {description}")
    
    logger.info("\n💡 To test alerts, use the test scripts in scripts/tests/")

async def main():
    """Main enhancement function"""
    logger.info("🚀 Alert System Enhancement Tool")
    logger.info("="*80)
    
    # Step 1: Fix missing chat_ids
    logger.info("\n📍 Step 1: Fixing Missing Chat IDs...")
    success = await fix_missing_chat_ids()
    
    if not success:
        logger.error("\n❌ Failed to fix chat_ids - aborting")
        return
    
    # Step 2: Verify alert triggers
    logger.info("\n📍 Step 2: Verifying Alert Triggers...")
    await verify_alert_triggers()
    
    # Step 3: Show test scenarios
    logger.info("\n📍 Step 3: Available Test Scenarios...")
    await create_alert_test_positions()
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("✅ ALERT SYSTEM ENHANCEMENT COMPLETE")
    logger.info("="*80)
    logger.info("\n📋 Next Steps:")
    logger.info("   1. Monitor bot logs for alert messages")
    logger.info("   2. Check Telegram for alert delivery")
    logger.info("   3. Use test scripts to verify each alert type")
    logger.info("\n💡 Tips:")
    logger.info("   - Set DEFAULT_ALERT_CHAT_ID in .env for future positions")
    logger.info("   - All alerts now go through Enhanced TP/SL system")
    logger.info("   - Alerts include comprehensive trade context")

if __name__ == "__main__":
    import time
    asyncio.run(main())