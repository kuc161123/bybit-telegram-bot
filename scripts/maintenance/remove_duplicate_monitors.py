#!/usr/bin/env python3
"""
Remove duplicate legacy format monitors
"""
import pickle
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Backup first
backup_file = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_before_dedup_{int(datetime.now().timestamp())}'
import shutil
shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_file)
logger.info(f"✅ Created backup: {backup_file}")

# Load pickle
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

monitors = data['bot_data']['enhanced_tp_sl_monitors']
original_count = len(monitors)

# Find and remove legacy format monitors (those without _main or _mirror suffix)
legacy_keys = []
for key in list(monitors.keys()):
    if not key.endswith('_main') and not key.endswith('_mirror'):
        legacy_keys.append(key)

# Remove legacy monitors
for key in legacy_keys:
    logger.info(f"❌ Removing legacy monitor: {key}")
    del monitors[key]

# Save updated data
data['bot_data']['enhanced_tp_sl_monitors'] = monitors
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
    pickle.dump(data, f)

logger.info(f"\n✅ Removed {len(legacy_keys)} duplicate monitors")
logger.info(f"✅ Monitors reduced from {original_count} to {len(monitors)}")

# Verify final state
main_count = sum(1 for k in monitors if k.endswith('_main'))
mirror_count = sum(1 for k in monitors if k.endswith('_mirror'))

logger.info(f"\nFinal monitor count: {len(monitors)}")
logger.info(f"  Main account: {main_count}")
logger.info(f"  Mirror account: {mirror_count}")

# Create signal file to reload
with open('reload_enhanced_monitors.signal', 'w') as f:
    f.write(str(datetime.now().timestamp()))
logger.info("\n✅ Created signal file for reload")