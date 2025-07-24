#!/usr/bin/env python3
"""
Check for duplicate monitors
"""
import pickle
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load pickle
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})

logger.info("=" * 60)
logger.info("MONITOR ANALYSIS")
logger.info("=" * 60)
logger.info(f"Total monitors: {len(monitors)}")

# Group by symbol/side to find duplicates
positions = {}
for key, monitor in monitors.items():
    symbol = monitor.get('symbol')
    side = monitor.get('side')
    account = monitor.get('account_type', 'unknown')
    
    pos_key = f"{symbol}_{side}"
    if pos_key not in positions:
        positions[pos_key] = []
    
    positions[pos_key].append({
        'key': key,
        'account': account,
        'chat_id': monitor.get('chat_id')
    })

# Show all monitors
logger.info("\nAll monitors:")
for key in sorted(monitors.keys()):
    monitor = monitors[key]
    account = monitor.get('account_type', 'unknown')
    chat_id = monitor.get('chat_id')
    logger.info(f"  {key} (account: {account}, chat_id: {chat_id})")

# Find duplicates
logger.info("\nDuplicate Analysis:")
duplicates_found = False
for pos_key, entries in positions.items():
    if len(entries) > 2:  # More than main + mirror
        duplicates_found = True
        logger.warning(f"\n⚠️ {pos_key} has {len(entries)} monitors!")
        for entry in entries:
            logger.warning(f"   - {entry['key']} (account: {entry['account']})")

if not duplicates_found:
    # Check for legacy keys
    legacy_keys = [k for k in monitors.keys() if not k.endswith('_main') and not k.endswith('_mirror')]
    if legacy_keys:
        logger.warning(f"\n⚠️ Found {len(legacy_keys)} legacy format monitors:")
        for key in legacy_keys:
            logger.warning(f"   - {key}")
        logger.info("\nThese are causing duplicates with the new format monitors!")

# Summary
main_monitors = sum(1 for k in monitors if k.endswith('_main') or (not k.endswith('_mirror') and monitors[k].get('account_type') == 'main'))
mirror_monitors = sum(1 for k in monitors if k.endswith('_mirror') or monitors[k].get('account_type') == 'mirror')
legacy_monitors = sum(1 for k in monitors if not k.endswith('_main') and not k.endswith('_mirror'))

logger.info("\n" + "=" * 60)
logger.info("SUMMARY")
logger.info("=" * 60)
logger.info(f"Total monitors: {len(monitors)}")
logger.info(f"  Main account: {main_monitors}")
logger.info(f"  Mirror account: {mirror_monitors}")
logger.info(f"  Legacy format: {legacy_monitors}")

if legacy_monitors > 0:
    logger.warning(f"\n⚠️ The {legacy_monitors} legacy monitors are duplicates!")
    logger.info("We need to remove them to get back to 13 monitors.")