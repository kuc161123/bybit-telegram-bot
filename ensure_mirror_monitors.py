#!/usr/bin/env python3
"""
Ensure mirror monitors are always loaded
This should be imported by the bot to ensure mirror monitors persist
"""
import logging
import pickle
import os

logger = logging.getLogger(__name__)

class MirrorMonitorEnsurer:
    """Ensures mirror monitors are always loaded"""
    
    @staticmethod
    def ensure_all_monitors_loaded(enhanced_tp_sl_manager):
        """Ensure all monitors including mirror are loaded"""
        try:
            # Load from pickle
            pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            if not os.path.exists(pickle_file):
                return
            
            with open(pickle_file, 'rb') as f:
                data = pickle.load(f)
            
            all_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            
            # Count current vs expected
            current_count = len(enhanced_tp_sl_manager.position_monitors)
            expected_count = len(all_monitors)
            
            if current_count < expected_count:
                logger.info(f"🔄 Loading missing monitors ({current_count} -> {expected_count})")
                
                # Load missing monitors
                for key, monitor in all_monitors.items():
                    if key not in enhanced_tp_sl_manager.position_monitors:
                        enhanced_tp_sl_manager.position_monitors[key] = monitor
                        logger.info(f"✅ Loaded missing monitor: {key}")
                
                logger.info(f"✅ All {len(enhanced_tp_sl_manager.position_monitors)} monitors loaded")
                
        except Exception as e:
            logger.error(f"Error ensuring monitors loaded: {e}")

# Create a startup hook
def on_startup(enhanced_tp_sl_manager):
    """Hook to run on startup"""
    ensurer = MirrorMonitorEnsurer()
    ensurer.ensure_all_monitors_loaded(enhanced_tp_sl_manager)

# Export
__all__ = ['MirrorMonitorEnsurer', 'on_startup']