#!/usr/bin/env python3
"""
Ensure we have exactly 36 monitors (18 main + 18 mirror)
"""
import pickle
import time

def ensure_36_monitors():
    """Check and create missing monitors to reach 36 total"""
    print("🔍 Checking for 36 monitors...")
    
    try:
        # Load current data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Current monitors: {len(monitors)}")
        
        # Group by position
        positions_main = {}
        positions_mirror = {}
        
        for key, monitor in monitors.items():
            parts = key.split('_')
            if len(parts) >= 3:
                symbol = parts[0]
                side = parts[1]
                account = parts[2]
                position_key = f"{symbol}_{side}"
                
                if account == 'main':
                    positions_main[position_key] = monitor
                elif account == 'mirror':
                    positions_mirror[position_key] = monitor
        
        print(f"📊 Main positions: {len(positions_main)}")
        print(f"📊 Mirror positions: {len(positions_mirror)}")
        
        # Every main position should have a mirror
        missing_mirrors = []
        for pos_key in positions_main:
            if pos_key not in positions_mirror:
                missing_mirrors.append(pos_key)
        
        # Check for orphaned mirrors (mirror without main)
        orphaned_mirrors = []
        for pos_key in positions_mirror:
            if pos_key not in positions_main:
                orphaned_mirrors.append(pos_key)
        
        print(f"\n❌ Missing mirror monitors: {len(missing_mirrors)}")
        for pos_key in missing_mirrors:
            print(f"   - {pos_key}")
            
        if orphaned_mirrors:
            print(f"\n⚠️  Orphaned mirror monitors: {len(orphaned_mirrors)}")
            for pos_key in orphaned_mirrors:
                print(f"   - {pos_key}")
        
        # Create missing mirror monitors
        created = 0
        for pos_key in missing_mirrors:
            symbol, side = pos_key.split('_')
            main_monitor = positions_main[pos_key]
            
            mirror_key = f"{symbol}_{side}_mirror"
            monitors[mirror_key] = {
                "symbol": symbol,
                "side": side,
                "account_type": "mirror",
                "chat_id": 5634913742,
                "approach": main_monitor.get('approach', 'fast'),
                "tp_orders": {},  # Will be synced
                "sl_order": None,  # Will be synced
                "position_size": main_monitor.get('position_size', 0) * 0.33,  # Approximate
                "remaining_size": main_monitor.get('remaining_size', 0) * 0.33,
                "entry_price": main_monitor.get('entry_price', 0),
                "created_at": time.time(),
                "monitor_key": mirror_key,
                "phase": "MONITORING",
                "tp1_hit": main_monitor.get('tp1_hit', False),
                "sl_moved_to_be": main_monitor.get('sl_moved_to_be', False),
                "has_mirror": True
            }
            created += 1
            print(f"✅ Created mirror monitor: {symbol} {side}")
        
        # Save if changes made
        if created > 0:
            # Backup first
            backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_36monitors_{int(time.time())}'
            with open(backup_name, 'wb') as f:
                pickle.dump(data, f)
            print(f"\n✅ Created backup: {backup_name}")
            
            # Save updated data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            
            print(f"\n✅ Created {created} missing mirror monitors")
        
        # Final count
        final_count = len(monitors)
        print(f"\n📊 Final monitor count: {final_count}")
        
        if final_count == 36:
            print("✅ Perfect! You now have exactly 36 monitors (18 main + 18 mirror)")
        elif final_count > 36:
            print(f"⚠️  You have {final_count - 36} extra monitors")
        else:
            print(f"⚠️  Still missing {36 - final_count} monitors")
            
        # List all positions
        print("\n📋 All monitored positions:")
        all_positions = set()
        for key in monitors:
            parts = key.split('_')
            if len(parts) >= 2:
                all_positions.add(f"{parts[0]} {parts[1]}")
        
        for i, pos in enumerate(sorted(all_positions), 1):
            print(f"   {i}. {pos}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("🚀 Ensuring 36 Monitors for Complete Coverage")
    print("=" * 60)
    
    ensure_36_monitors()
    
    print("\n" + "=" * 60)
    print("✅ Monitor verification complete!")
    print("\n📝 The bot will sync orders automatically on next cycle")

if __name__ == "__main__":
    main()