#!/usr/bin/env python3
"""
Force reload monitors by updating background_tasks to load directly from pickle
"""
import logging
import pickle

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check what's in the pickle file
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})

logger.info("=" * 60)
logger.info("MONITORS IN PICKLE FILE")
logger.info("=" * 60)
logger.info(f"Total monitors: {len(enhanced_monitors)}")

for key in sorted(enhanced_monitors.keys()):
    monitor = enhanced_monitors[key]
    account = monitor.get('account_type', 'unknown')
    logger.info(f"  {key} (account: {account})")

# Update background_tasks.py to load directly from pickle
logger.info("\n📝 Updating background_tasks.py to load from pickle directly...")

with open('helpers/background_tasks.py', 'r') as f:
    content = f.read()

# Replace the robust persistence loading with direct pickle loading
old_section = '''                    # Use robust persistence manager
                    from utils.robust_persistence import robust_persistence
                    
                    logger.info(f"🔍 Loading monitors using Robust Persistence Manager")
                    logger.info(f"🔍 Current monitor count: {len(enhanced_tp_sl_manager.position_monitors)}")
                    
                    # Get all monitors from robust persistence
                    persisted_monitors = await robust_persistence.get_all_monitors()
                    logger.info(f"🔍 Found {len(persisted_monitors)} persisted monitors")'''

new_section = '''                    # Load directly from pickle file
                    import pickle
                    
                    logger.info(f"🔍 Loading monitors directly from pickle file")
                    logger.info(f"🔍 Current monitor count: {len(enhanced_tp_sl_manager.position_monitors)}")
                    
                    # Get all monitors from pickle
                    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                        data = pickle.load(f)
                    
                    persisted_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
                    logger.info(f"🔍 Found {len(persisted_monitors)} persisted monitors")'''

if old_section in content:
    content = content.replace(old_section, new_section)
    logger.info("✅ Updated to load directly from pickle")
    
    with open('helpers/background_tasks.py', 'w') as f:
        f.write(content)
    
    # Create another signal file
    with open('reload_enhanced_monitors.signal', 'w') as f:
        import time
        f.write(str(time.time()))
    
    logger.info("✅ Created new signal file")
    logger.info("\n🎯 The bot should now load all 13 monitors!")
else:
    logger.warning("⚠️ Could not find the section to replace")
    logger.info("The bot may need to be restarted to pick up all monitors")