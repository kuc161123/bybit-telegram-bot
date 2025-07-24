#!/usr/bin/env python3
"""
Find which monitors are missing and create them
"""
import pickle
import asyncio
from clients.bybit_client import bybit_client

async def find_missing_monitors():
    """Find which positions don't have monitors"""
    print("🔍 Finding missing monitors...")
    
    try:
        # Get all active positions
        positions = await bybit_client.get_all_positions()
        print(f"📊 Found {len(positions)} active positions")
        
        # Load current monitors
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Current monitors: {len(monitors)}")
        
        # Check which positions are missing monitors
        missing_main = []
        missing_mirror = []
        
        for pos in positions:
            symbol = pos['symbol']
            side = pos['side']
            
            # Check main account monitor
            main_key = f"{symbol}_{side}_main"
            if main_key not in monitors:
                missing_main.append((symbol, side))
                
            # Check mirror account monitor (should exist for every position)
            mirror_key = f"{symbol}_{side}_mirror"
            if mirror_key not in monitors:
                missing_mirror.append((symbol, side))
        
        print(f"\n❌ Missing MAIN monitors: {len(missing_main)}")
        for symbol, side in missing_main:
            print(f"   - {symbol} {side}")
            
        print(f"\n❌ Missing MIRROR monitors: {len(missing_mirror)}")
        for symbol, side in missing_mirror:
            print(f"   - {symbol} {side}")
            
        # Count by symbol
        main_positions = {}
        mirror_positions = {}
        
        for key in monitors:
            parts = key.split('_')
            if len(parts) >= 3:
                symbol = parts[0]
                side = parts[1]
                account = parts[2]
                
                if account == 'main':
                    main_positions[f"{symbol}_{side}"] = True
                elif account == 'mirror':
                    mirror_positions[f"{symbol}_{side}"] = True
        
        print(f"\n📊 Summary:")
        print(f"   Active positions: {len(positions)}")
        print(f"   Main monitors: {len(main_positions)}")
        print(f"   Mirror monitors: {len(mirror_positions)}")
        print(f"   Total monitors: {len(monitors)}")
        print(f"   Expected: 36 (18 main + 18 mirror)")
        
        return missing_main, missing_mirror
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return [], []

async def create_missing_monitors(missing_main, missing_mirror):
    """Create the missing monitors"""
    if not missing_main and not missing_mirror:
        print("\n✅ No missing monitors to create")
        return
        
    print("\n🔧 Creating missing monitors...")
    
    try:
        # Load current data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Create missing main monitors
        for symbol, side in missing_main:
            monitor_key = f"{symbol}_{side}_main"
            monitors[monitor_key] = {
                "symbol": symbol,
                "side": side,
                "account_type": "main",
                "chat_id": 5634913742,
                "approach": "fast",  # Will be updated based on orders
                "tp_orders": {},
                "sl_order": None,
                "position_size": 0,
                "remaining_size": 0,
                "entry_price": 0,
                "created_at": time.time(),
                "monitor_key": monitor_key,
                "phase": "MONITORING",
                "tp1_hit": False,
                "sl_moved_to_be": False
            }
            print(f"✅ Created main monitor: {symbol} {side}")
        
        # Create missing mirror monitors
        for symbol, side in missing_mirror:
            monitor_key = f"{symbol}_{side}_mirror"
            
            # Try to get info from main monitor
            main_key = f"{symbol}_{side}_main"
            if main_key in monitors:
                main_monitor = monitors[main_key]
                approach = main_monitor.get('approach', 'fast')
            else:
                approach = 'fast'
                
            monitors[monitor_key] = {
                "symbol": symbol,
                "side": side,
                "account_type": "mirror",
                "chat_id": 5634913742,
                "approach": approach,
                "tp_orders": {},
                "sl_order": None,
                "position_size": 0,
                "remaining_size": 0,
                "entry_price": 0,
                "created_at": time.time(),
                "monitor_key": monitor_key,
                "phase": "MONITORING",
                "tp1_hit": False,
                "sl_moved_to_be": False,
                "has_mirror": True
            }
            print(f"✅ Created mirror monitor: {symbol} {side}")
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
            
        print(f"\n✅ Created {len(missing_main)} main monitors")
        print(f"✅ Created {len(missing_mirror)} mirror monitors")
        print(f"📊 Total monitors now: {len(monitors)}")
        
    except Exception as e:
        print(f"Error creating monitors: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("🚀 Ensuring 36 Monitors (18 Main + 18 Mirror)")
    print("=" * 60)
    
    # Find missing monitors
    missing_main, missing_mirror = await find_missing_monitors()
    
    # Create them
    await create_missing_monitors(missing_main, missing_mirror)
    
    print("\n" + "=" * 60)
    print("✅ Monitor check complete!")
    print("\n📝 Next: The bot will sync these monitors with actual orders")

if __name__ == "__main__":
    import time
    asyncio.run(main())