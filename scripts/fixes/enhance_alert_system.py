#!/usr/bin/env python3
"""
Enhance Alert System for All Trading Events
This script ensures all trading events generate alerts for both main and mirror accounts
"""

import asyncio
import logging
from decimal import Decimal
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def enhance_alert_system():
    """Update system to ensure all trading events generate alerts"""
    try:
        import pickle
        
        logger.info("🔔 Enhancing Alert System for All Trading Events")
        logger.info("=" * 80)
        
        # Load pickle data
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        user_data = data.get('user_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Find active chat IDs
        active_chat_ids = set()
        for chat_id in user_data.keys():
            try:
                chat_id_int = int(chat_id)
                active_chat_ids.add(chat_id_int)
            except:
                pass
        
        logger.info(f"Found {len(active_chat_ids)} active chat IDs")
        
        # Check each monitor for missing chat_id
        fixed_count = 0
        for monitor_key, monitor_data in enhanced_monitors.items():
            if not monitor_data.get('chat_id') and active_chat_ids:
                # Try to find appropriate chat_id
                symbol = monitor_data.get('symbol')
                side = monitor_data.get('side')
                
                # Search in monitor_tasks
                monitor_tasks = bot_data.get('monitor_tasks', {})
                found_chat_id = None
                
                for task_key, task_data in monitor_tasks.items():
                    if task_data.get('symbol') == symbol and task_data.get('side') == side:
                        # Extract chat_id from task key
                        parts = task_key.split('_')
                        if parts:
                            try:
                                potential_chat_id = int(parts[0])
                                if potential_chat_id in active_chat_ids:
                                    found_chat_id = potential_chat_id
                                    break
                            except:
                                pass
                
                # If not found, use the first active chat_id
                if not found_chat_id and active_chat_ids:
                    found_chat_id = list(active_chat_ids)[0]
                
                if found_chat_id:
                    monitor_data['chat_id'] = found_chat_id
                    fixed_count += 1
                    logger.info(f"✅ Added chat_id {found_chat_id} to monitor {monitor_key}")
        
        # Add alert flags to ensure all events are tracked
        for monitor_key, monitor_data in enhanced_monitors.items():
            # Ensure alert tracking flags exist
            if 'alerts_sent' not in monitor_data:
                monitor_data['alerts_sent'] = {
                    'position_opened': False,
                    'limit_fills': [],
                    'tp_fills': [],
                    'sl_moved_to_be': False,
                    'position_closed': False,
                    'rebalances': 0
                }
            
            # Ensure mirror sync flags
            if 'mirror' in monitor_key.lower() or monitor_data.get('account_type') == 'mirror':
                monitor_data['is_mirror'] = True
                monitor_data['send_separate_alerts'] = True
        
        # Save updates
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n✅ Alert System Enhanced!")
        logger.info(f"   Fixed {fixed_count} monitors with missing chat_id")
        logger.info(f"   Added alert tracking to all monitors")
        
        # Create verification script
        create_alert_verification_script()
        
        logger.info("\n📝 Next Steps:")
        logger.info("   1. Run verify_alert_system.py to test alerts")
        logger.info("   2. Monitor trading_bot.log for alert delivery")
        logger.info("   3. All future trades will have comprehensive alerts")
        
    except Exception as e:
        logger.error(f"❌ Error enhancing alert system: {e}")
        import traceback
        traceback.print_exc()

def create_alert_verification_script():
    """Create a script to verify alert system is working"""
    script_content = '''#!/usr/bin/env python3
"""Verify Alert System is Working"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_alerts():
    try:
        from utils.alert_helpers import send_simple_alert
        import pickle
        
        # Load data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Find a test chat_id
        user_data = data.get('user_data', {})
        test_chat_id = None
        
        for chat_id in user_data.keys():
            try:
                test_chat_id = int(chat_id)
                break
            except:
                pass
        
        if not test_chat_id:
            logger.error("No chat_id found for testing")
            return
        
        logger.info(f"Testing alerts with chat_id: {test_chat_id}")
        
        # Test various alert types
        test_alerts = [
            ("🧪 TEST: Position Opened Alert", "position_opened"),
            ("🧪 TEST: Limit Order Fill Alert", "limit_filled"),
            ("🧪 TEST: TP Rebalancing Alert", "rebalancing"),
            ("🧪 TEST: Breakeven Alert", "breakeven"),
            ("🧪 TEST: TP Fill Alert", "tp_hit"),
            ("🧪 TEST: Position Closed Alert", "position_closed")
        ]
        
        success_count = 0
        for message, alert_type in test_alerts:
            try:
                result = await send_simple_alert(test_chat_id, message, alert_type)
                if result:
                    logger.info(f"✅ {alert_type} alert sent successfully")
                    success_count += 1
                else:
                    logger.error(f"❌ Failed to send {alert_type} alert")
                await asyncio.sleep(1)  # Avoid rate limiting
            except Exception as e:
                logger.error(f"❌ Error sending {alert_type} alert: {e}")
        
        logger.info(f"\\n📊 Alert Test Results: {success_count}/{len(test_alerts)} successful")
        
    except Exception as e:
        logger.error(f"❌ Error in alert verification: {e}")

if __name__ == "__main__":
    asyncio.run(verify_alerts())
'''
    
    script_path = 'scripts/fixes/verify_alert_system.py'
    with open(script_path, 'w') as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)
    logger.info(f"✅ Created alert verification script: {script_path}")

if __name__ == "__main__":
    asyncio.run(enhance_alert_system())