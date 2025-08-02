#!/usr/bin/env python3
"""
Monitor Persistence Validator - Ensures monitor tracking integrity
"""
import pickle
import logging
import time

logger = logging.getLogger(__name__)

def validate_monitor_integrity():
    """Validate that all positions have proper monitor coverage"""
    try:
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'

        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)

        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})

        # Count by account type
        main_enhanced = [k for k in enhanced_monitors.keys() if '_MIRROR' not in k]
        mirror_enhanced = [k for k in enhanced_monitors.keys() if '_MIRROR' in k]
        main_dashboard = [k for k in dashboard_monitors.keys() if 'mirror' not in k.lower()]
        mirror_dashboard = [k for k in dashboard_monitors.keys() if 'mirror' in k.lower()]

        logger.info(f"📊 Monitor Integrity Report:")
        logger.info(f"   Enhanced TP/SL - Main: {len(main_enhanced)}, Mirror: {len(mirror_enhanced)}")
        logger.info(f"   Dashboard - Main: {len(main_dashboard)}, Mirror: {len(mirror_dashboard)}")
        logger.info(f"   Total Enhanced: {len(enhanced_monitors)}")
        logger.info(f"   Total Dashboard: {len(dashboard_monitors)}")

        # Check for integrity
        if len(main_enhanced) != len(main_dashboard):
            logger.warning(f"⚠️ Main account monitor mismatch: Enhanced={len(main_enhanced)}, Dashboard={len(main_dashboard)}")

        if len(mirror_enhanced) != len(mirror_dashboard):
            logger.warning(f"⚠️ Mirror account monitor mismatch: Enhanced={len(mirror_enhanced)}, Dashboard={len(mirror_dashboard)}")

        return len(enhanced_monitors) == len(dashboard_monitors)

    except Exception as e:
        logger.error(f"❌ Error validating monitor integrity: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    validate_monitor_integrity()
