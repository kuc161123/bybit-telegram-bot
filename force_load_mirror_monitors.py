#!/usr/bin/env python3
"""
Force the enhanced TP/SL manager to load mirror monitors
"""
import pickle
import time
from datetime import datetime

def force_mirror_monitors():
    """Force load mirror monitors into the manager"""
    print("="*60)
    print("FORCING MIRROR MONITOR LOAD")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Access the enhanced TP/SL manager directly
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        print(f"\n📊 Current monitors in manager: {len(enhanced_tp_sl_manager.position_monitors)}")
        
        # Load monitors from pickle
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        all_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Monitors in pickle: {len(all_monitors)}")
        
        # Force load ALL monitors including mirror
        print("\n🔄 Force loading all monitors...")
        for key, monitor in all_monitors.items():
            if key not in enhanced_tp_sl_manager.position_monitors:
                enhanced_tp_sl_manager.position_monitors[key] = monitor
                print(f"  ✅ Added {key}")
            else:
                print(f"  ℹ️  {key} already loaded")
        
        print(f"\n✅ Manager now has {len(enhanced_tp_sl_manager.position_monitors)} monitors")
        
        # List all monitors
        print("\n📋 All loaded monitors:")
        for key in enhanced_tp_sl_manager.position_monitors.keys():
            print(f"  - {key}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_mirror_sync_trigger():
    """Create a trigger to sync mirror positions"""
    trigger_content = f"""# MIRROR SYNC TRIGGER
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Forces enhanced TP/SL to sync mirror positions

SYNC_MIRROR_POSITIONS = True
TIMESTAMP = {int(time.time())}
FORCE_MIRROR_SYNC = True

# Mirror positions to sync
MIRROR_POSITIONS = [
    "COTIUSDT_Buy_mirror",
    "CAKEUSDT_Buy_mirror", 
    "SNXUSDT_Buy_mirror",
    "1INCHUSDT_Buy_mirror",
    "SUSHIUSDT_Buy_mirror"
]
"""
    
    with open('mirror_sync.trigger', 'w') as f:
        f.write(trigger_content)
    
    print("\n✅ Created mirror_sync.trigger")

def main():
    """Main execution"""
    # Try to force load
    success = force_mirror_monitors()
    
    # Create sync trigger
    create_mirror_sync_trigger()
    
    print("\n" + "="*60)
    print("RESULT")
    print("="*60)
    
    if success:
        print("✅ Successfully forced mirror monitors into manager")
        print("🔍 You should now see 'Monitoring 10 positions'")
    else:
        print("⚠️  Could not directly load monitors")
        print("The enhanced TP/SL manager may need modification")
        print("to support mirror account position sync")

if __name__ == "__main__":
    main()