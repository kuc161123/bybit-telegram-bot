#!/usr/bin/env python3
"""
Fix mirror monitors to have chat_id=None and has_mirror=False
"""
import pickle
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load pickle
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

# Backup first
backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_mirror_fix_{int(datetime.now().timestamp())}'
with open(backup_name, 'wb') as f:
    pickle.dump(data, f)
logger.info(f"Created backup: {backup_name}")

# Fix mirror monitors
enhanced_monitors = data['bot_data']['enhanced_tp_sl_monitors']
fixed_count = 0

for key, monitor in enhanced_monitors.items():
    if monitor.get('account_type') == 'mirror':
        old_chat_id = monitor.get('chat_id')
        old_has_mirror = monitor.get('has_mirror', True)
        
        # Fix settings
        monitor['chat_id'] = None
        monitor['has_mirror'] = False
        
        fixed_count += 1
        logger.info(f"✅ Fixed {key}:")
        logger.info(f"   - chat_id: {old_chat_id} → None")
        logger.info(f"   - has_mirror: {old_has_mirror} → False")

# Save fixed data
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
    pickle.dump(data, f)

logger.info(f"\n✅ Fixed {fixed_count} mirror monitors")
logger.info("✅ All mirror monitors now have:")
logger.info("   - chat_id = None (no alerts)")
logger.info("   - has_mirror = False")
logger.info("✅ Saved changes to pickle file")

# Create signal file to trigger reload
with open('reload_monitors.signal', 'w') as f:
    f.write(str(datetime.now().timestamp()))
logger.info("\n✅ Created signal file to trigger reload in running bot")