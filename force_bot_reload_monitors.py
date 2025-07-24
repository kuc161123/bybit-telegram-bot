#!/usr/bin/env python3
"""
Force the bot to reload monitors from pickle without restart
"""
import asyncio
from datetime import datetime

async def force_reload():
    """Force the enhanced TP/SL manager to reload monitors"""
    print("="*60)
    print("FORCING BOT TO RELOAD MONITORS")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    try:
        # Import the manager
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Clear current monitors to force reload
        print(f"Current monitors: {len(enhanced_tp_sl_manager.position_monitors)}")
        enhanced_tp_sl_manager.position_monitors.clear()
        print("✅ Cleared current monitors")
        
        # Force reload from pickle
        import pickle
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        all_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"\n📊 Found {len(all_monitors)} monitors in pickle:")
        
        # Load ALL monitors (both main and mirror)
        for key, monitor in all_monitors.items():
            enhanced_tp_sl_manager.position_monitors[key] = monitor
            account = monitor.get('account_type', 'unknown')
            print(f"  ✅ Loaded {key} ({account})")
        
        print(f"\n✅ Successfully loaded {len(enhanced_tp_sl_manager.position_monitors)} monitors")
        print("The bot should now show 'Monitoring 10 positions'")
        
        # Create a signal file
        with open('monitors_reloaded.signal', 'w') as f:
            f.write(f"RELOAD_TIME={datetime.now()}\n")
            f.write(f"MONITORS_LOADED={len(all_monitors)}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(force_reload())
    
    if not success:
        print("\n⚠️  Could not force reload")
        print("The bot may need the independent mirror sync to be integrated")