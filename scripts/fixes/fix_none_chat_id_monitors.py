#!/usr/bin/env python3
"""
Fix monitors with None chat_id by finding the correct chat_id from user data
"""
import pickle
import logging
from typing import Dict, Any, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_chat_id_for_position(symbol: str, side: str, user_data: Dict) -> Optional[int]:
    """Find chat_id that owns this position"""
    for chat_id, data in user_data.items():
        positions = data.get('positions', [])
        for pos in positions:
            if pos.get('symbol') == symbol and pos.get('side') == side:
                return chat_id
    return None

def fix_monitors_with_none_chat_id():
    """Fix all monitors that have None as chat_id"""
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        # Load pickle data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        user_data = data.get('user_data', {})
        chat_data = data.get('chat_data', {})
        
        # Get the active chat ID
        active_chat_ids = list(chat_data.keys())
        if not active_chat_ids:
            active_chat_ids = list(user_data.keys())
        
        default_chat_id = active_chat_ids[0] if active_chat_ids else None
        
        if default_chat_id:
            logger.info(f"Found active chat ID: {default_chat_id}")
        
        # Check enhanced_tp_sl_monitors
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        fixed_count = 0
        
        logger.info(f"Checking {len(enhanced_monitors)} enhanced monitors...")
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            if monitor_data.get('chat_id') is None:
                symbol = monitor_data.get('symbol')
                side = monitor_data.get('side')
                
                logger.warning(f"Found monitor with None chat_id: {monitor_key} ({symbol} {side})")
                
                # Try to find chat_id
                chat_id = find_chat_id_for_position(symbol, side, user_data)
                
                if not chat_id and default_chat_id:
                    # Use the default active chat ID
                    chat_id = default_chat_id
                
                if chat_id:
                    monitor_data['chat_id'] = chat_id
                    fixed_count += 1
                    logger.info(f"✅ Fixed {monitor_key} with chat_id: {chat_id}")
                else:
                    logger.error(f"❌ Could not find chat_id for {monitor_key}")
        
        # Also check monitor_tasks with None_ prefix or None chat_id value
        monitor_tasks = bot_data.get('monitor_tasks', {})
        none_monitors = [k for k in monitor_tasks.keys() if k.startswith('None_')]
        
        # Also fix monitor_tasks entries where chat_id value is None
        for key, monitor in monitor_tasks.items():
            if monitor.get('chat_id') is None and default_chat_id:
                monitor['chat_id'] = default_chat_id
                fixed_count += 1
                logger.info(f"✅ Fixed monitor_tasks {key} chat_id value to {default_chat_id}")
        
        logger.info(f"\nFound {len(none_monitors)} monitor_tasks with None_ prefix")
        
        for old_key in none_monitors:
            monitor = monitor_tasks[old_key]
            symbol = monitor.get('symbol')
            side = monitor.get('side', '')
            approach = monitor.get('approach', 'fast')
            
            # Find chat_id - use the default active chat ID
            chat_id = default_chat_id
            
            if chat_id:
                # Create new key with proper chat_id
                new_key = f"{chat_id}_{symbol}_{approach}"
                monitor_tasks[new_key] = monitor
                monitor['chat_id'] = chat_id
                
                # Remove old key
                del monitor_tasks[old_key]
                fixed_count += 1
                logger.info(f"✅ Fixed monitor_tasks: {old_key} -> {new_key}")
            else:
                logger.error(f"❌ Could not fix monitor_tasks: {old_key}")
        
        if fixed_count > 0:
            # Save updated data
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"\n✅ Fixed {fixed_count} monitors and saved to {pkl_path}")
        else:
            logger.info("\n✅ No monitors needed fixing")
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("SUMMARY:")
        logger.info(f"Enhanced monitors checked: {len(enhanced_monitors)}")
        logger.info(f"Monitor tasks checked: {len(monitor_tasks)}")
        logger.info(f"Total fixes applied: {fixed_count}")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Error fixing monitors: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_monitors_with_none_chat_id()