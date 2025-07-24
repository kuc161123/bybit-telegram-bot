#!/usr/bin/env python3
"""
Create Missing Main Account Dashboard Monitors

The validator shows we need to create dashboard monitors for the 10 missing main account positions.
Currently: Enhanced=12, Dashboard=2 for main accounts

This will bring us to the full 28 monitors (14 main + 14 mirror).
"""

import pickle
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_missing_main_monitors():
    """Create dashboard monitors for missing main account positions"""
    try:
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        backup_path = f'{pkl_path}.backup_main_fix_{int(time.time())}'
        
        # Backup
        logger.info(f"💾 Creating backup: {backup_path}")
        with open(pkl_path, 'rb') as src, open(backup_path, 'wb') as dst:
            dst.write(src.read())
        
        # Load data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
        
        logger.info(f"📊 Current state:")
        logger.info(f"   Enhanced monitors: {len(enhanced_monitors)}")
        logger.info(f"   Dashboard monitors: {len(dashboard_monitors)}")
        
        # Find main account enhanced monitors without dashboard monitors
        main_enhanced = [k for k in enhanced_monitors.keys() if '_MIRROR' not in k]
        
        # Get chat_id from existing dashboard monitors
        chat_id = 5634913742  # From previous analysis
        
        created_count = 0
        
        for main_key in main_enhanced:
            symbol, side = main_key.split('_', 1)
            
            # Check if dashboard monitor already exists
            has_dashboard = any(
                f"{chat_id}_{symbol}_" in dashboard_key and 'mirror' not in dashboard_key.lower()
                for dashboard_key in dashboard_monitors.keys()
            )
            
            if not has_dashboard:
                # Create dashboard monitor
                approach = "conservative"  # Most positions are conservative
                dashboard_key = f"{chat_id}_{symbol}_{approach}"
                
                monitor_data = enhanced_monitors.get(main_key, {})
                
                dashboard_entry = {
                    "symbol": symbol,
                    "side": side,
                    "approach": approach,
                    "account_type": "main",
                    "chat_id": chat_id,
                    "active": True,
                    "started_at": time.time(),
                    "last_update": time.time(),
                    "position_size": monitor_data.get("position_size", "0"),
                    "entry_price": monitor_data.get("entry_price", "0"),
                    "current_status": "monitoring",
                    "tp_orders": monitor_data.get("tp_orders", []),
                    "sl_orders": monitor_data.get("sl_orders", []),
                    "created_by": "missing_main_monitor_fix",
                    "mirror_monitor": False
                }
                
                dashboard_monitors[dashboard_key] = dashboard_entry
                created_count += 1
                
                logger.info(f"✅ Created main dashboard monitor: {dashboard_key}")
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"✅ Created {created_count} missing main account dashboard monitors")
        logger.info(f"📊 New totals:")
        logger.info(f"   Enhanced monitors: {len(enhanced_monitors)}")
        logger.info(f"   Dashboard monitors: {len(dashboard_monitors)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating missing main monitors: {e}")
        return False

if __name__ == "__main__":
    success = create_missing_main_monitors()
    if success:
        logger.info("✅ Main monitor creation completed successfully!")
    else:
        logger.error("❌ Main monitor creation failed!")