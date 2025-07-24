#!/usr/bin/env python3
"""
Update BOMEUSDT monitor flags to reflect actual state
"""
import pickle
import time

def update_flags():
    """Update monitor flags for BOMEUSDT"""
    print("🔧 Updating BOMEUSDT monitor flags...")
    
    try:
        # Load data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        updated = 0
        
        # Update BOMEUSDT monitors
        for key, monitor in monitors.items():
            if 'BOMEUSDT' in key and monitor.get('tp1_hit'):
                print(f"\n📊 Updating {key}:")
                
                # Mirror had limits cancelled according to logs
                if 'mirror' in key:
                    monitor['limit_orders_cancelled'] = True
                    print("   ✅ Set limit_orders_cancelled = True")
                
                # Update timestamp
                monitor['last_updated'] = time.time()
                updated += 1
        
        if updated > 0:
            # Backup first
            backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_flags_{int(time.time())}'
            with open(backup_name, 'wb') as f:
                pickle.dump(data, f)
            print(f"\n✅ Created backup: {backup_name}")
            
            # Save updated data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            
            print(f"✅ Updated {updated} monitors")
        else:
            print("ℹ️  No updates needed")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("🚀 BOMEUSDT Flag Update Tool")
    print("=" * 60)
    
    update_flags()
    
    print("\n" + "=" * 60)
    print("✅ Flags updated!")
    print("\n📝 Note: You still need to manually:")
    print("1. Cancel BOMEUSDT limit orders on main account exchange")
    print("2. Move both SLs to breakeven price")
    print("3. Ensure SL quantities match remaining positions")

if __name__ == "__main__":
    main()