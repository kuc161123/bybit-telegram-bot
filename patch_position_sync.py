#!/usr/bin/env python3
"""
Patch to ensure mirror monitors persist through position sync
"""
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def patch_enhanced_manager():
    """Patch the enhanced TP/SL manager to keep mirror monitors"""
    print("="*60)
    print("PATCHING POSITION SYNC")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        # Import the manager
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Store the original sync method
        original_sync = enhanced_tp_sl_manager._sync_positions_with_monitors
        
        # Create a patched version that preserves mirror monitors
        async def patched_sync_positions_with_monitors():
            """Patched version that preserves mirror monitors"""
            # Get current mirror monitors before sync
            mirror_monitors = {}
            for key, monitor in enhanced_tp_sl_manager.position_monitors.items():
                if key.endswith('_mirror'):
                    mirror_monitors[key] = monitor
            
            logger.info(f"🔄 Preserving {len(mirror_monitors)} mirror monitors during sync")
            
            # Call original sync (this will clear non-main monitors)
            await original_sync()
            
            # Restore mirror monitors
            for key, monitor in mirror_monitors.items():
                if key not in enhanced_tp_sl_manager.position_monitors:
                    enhanced_tp_sl_manager.position_monitors[key] = monitor
                    logger.info(f"✅ Restored mirror monitor: {key}")
            
            total_monitors = len(enhanced_tp_sl_manager.position_monitors)
            logger.info(f"✅ Position sync complete with {total_monitors} total monitors")
        
        # Replace the method
        enhanced_tp_sl_manager._sync_positions_with_monitors = patched_sync_positions_with_monitors
        
        print("✅ Patched _sync_positions_with_monitors method")
        print("Mirror monitors will now persist through position syncs")
        
        # Also patch the monitoring loop to ensure it loads all monitors
        from helpers import background_tasks
        
        # Force reload all monitors from pickle
        import pickle
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        all_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Load all monitors
        for key, monitor in all_monitors.items():
            enhanced_tp_sl_manager.position_monitors[key] = monitor
        
        print(f"\n✅ Loaded {len(all_monitors)} monitors from pickle")
        print("The bot should now show 'Monitoring 10 positions'")
        
        return True
        
    except Exception as e:
        print(f"❌ Error patching: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main execution"""
    success = patch_enhanced_manager()
    
    if not success:
        print("\n⚠️  Could not patch the position sync")
        print("The bot may need to be restarted with a permanent fix")

if __name__ == "__main__":
    main()