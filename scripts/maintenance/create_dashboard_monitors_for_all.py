#!/usr/bin/env python3
"""
Create Dashboard Monitors for All Positions

Ensures every position has both Enhanced TP/SL monitor and Dashboard monitor
"""

import asyncio
import pickle
import logging
import time
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def create_dashboard_monitors():
    """Create dashboard monitors for all positions"""
    try:
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f'{pkl_path}.backup_dashboard_{int(time.time())}'
        
        # Backup
        logger.info(f"💾 Creating backup: {backup_path}")
        with open(pkl_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        
        # Load current data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        monitor_tasks = bot_data.get('monitor_tasks', {})
        
        logger.info(f"📊 Current Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        logger.info(f"📊 Current Dashboard monitors: {len(monitor_tasks)}")
        
        created_count = 0
        
        # Create dashboard monitors for each Enhanced monitor
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            approach = monitor_data.get('approach', 'fast').lower()
            account_type = monitor_data.get('account_type', 'main')
            chat_id = monitor_data.get('chat_id')
            
            # Create dashboard monitor key
            # Format: {chat_id}_{symbol}_{approach}_{account_type}
            if chat_id:
                dashboard_key = f"{chat_id}_{symbol}_{approach}_{account_type}"
            else:
                dashboard_key = f"None_{symbol}_{approach}_{account_type}"
            
            if dashboard_key not in monitor_tasks:
                dashboard_monitor = {
                    'chat_id': chat_id,
                    'symbol': symbol,
                    'approach': approach,
                    'monitoring_mode': 'ENHANCED_TP_SL',
                    'started_at': time.time(),
                    'active': True,
                    'account_type': account_type,
                    'system_type': 'enhanced_tp_sl',
                    'side': side
                }
                
                monitor_tasks[dashboard_key] = dashboard_monitor
                created_count += 1
                logger.info(f"✅ Created dashboard monitor: {dashboard_key}")
            else:
                logger.info(f"ℹ️ Dashboard monitor already exists: {dashboard_key}")
        
        # Save updated data
        bot_data['monitor_tasks'] = monitor_tasks
        data['bot_data'] = bot_data
        
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"\n✅ Created {created_count} dashboard monitors")
        logger.info(f"📊 Total dashboard monitors: {len(monitor_tasks)}")
        
        # Show all dashboard monitor keys
        logger.info("\n📋 All dashboard monitor keys:")
        for key in sorted(monitor_tasks.keys()):
            logger.info(f"   {key}")
        
        return created_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error creating dashboard monitors: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main execution"""
    logger.info("🎯 Creating Dashboard Monitors for All Positions")
    logger.info("=" * 50)
    
    success = await create_dashboard_monitors()
    
    if success:
        logger.info("\n✅ Dashboard monitors created successfully!")
        logger.info("📊 All positions now have complete monitoring coverage")
    else:
        logger.info("\nℹ️ No new dashboard monitors needed")

if __name__ == "__main__":
    asyncio.run(main())