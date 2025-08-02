#!/usr/bin/env python3
"""
Robust JASMY TP Fix with Pickle Locking
=======================================

This script uses pickle locking to ensure the JASMY fix persists properly.
"""
import pickle
import time
import os
import shutil
from decimal import Decimal

def create_backup():
    """Create timestamped backup"""
    timestamp = int(time.time())
    backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_jasmy_robust_{timestamp}'
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
    print(f"📁 Created backup: {backup_name}")
    return backup_name

def acquire_pickle_lock():
    """Acquire pickle lock"""
    lock_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl.lock'
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))
    print("🔒 Acquired pickle lock")
    return lock_file

def release_pickle_lock(lock_file):
    """Release pickle lock"""
    if os.path.exists(lock_file):
        os.remove(lock_file)
        print("🔓 Released pickle lock")

def robust_jasmy_fix():
    """Apply robust JASMY fix with proper locking"""
    print("🔧 Starting robust JASMY TP fix...")
    
    # Create backup
    backup_file = create_backup()
    
    # Acquire lock
    lock_file = acquire_pickle_lock()
    
    try:
        # Load data with verification
        print("📖 Loading pickle data...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        print(f"✅ Successfully loaded pickle data")
        
        # Get enhanced monitors
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Found {len(enhanced_monitors)} enhanced monitors")
        
        # Find JASMY monitors
        jasmy_monitors = {}
        for monitor_key, monitor_data in enhanced_monitors.items():
            if monitor_data.get('symbol') == 'JASMYUSDT':
                jasmy_monitors[monitor_key] = monitor_data
                print(f"🎯 Found JASMY monitor: {monitor_key}")
        
        if not jasmy_monitors:
            print("❌ No JASMY monitors found!")
            return False
        
        # Apply fixes
        for monitor_key, monitor_data in jasmy_monitors.items():
            account = monitor_data.get('account_type', 'main')
            print(f"\n🔧 Fixing {monitor_key} ({account.upper()})...")
            
            # Get position data
            total_size = Decimal(str(monitor_data.get('position_size', '0')))
            remaining_size = Decimal(str(monitor_data.get('remaining_size', '0')))
            filled_amount = total_size - remaining_size
            
            print(f"📊 Total: {total_size}, Remaining: {remaining_size}, Filled: {filled_amount}")
            
            if account == 'main' and filled_amount > 0:
                # Main account - ALL TPs filled
                print("🎯 Applying main account fixes...")
                
                enhanced_monitors[monitor_key]['tp1_hit'] = True
                enhanced_monitors[monitor_key]['phase'] = 'PROFIT_TAKING'
                enhanced_monitors[monitor_key]['phase_transition_time'] = time.time()
                enhanced_monitors[monitor_key]['filled_tps'] = [1, 2, 3, 4]
                enhanced_monitors[monitor_key]['sl_moved_to_be'] = True
                enhanced_monitors[monitor_key]['limit_orders_cancelled'] = True
                
                # Add TP1 info
                tp_orders = monitor_data.get('tp_orders', {})
                for order_id, order_info in tp_orders.items():
                    if order_info.get('tp_number') == 1:
                        enhanced_monitors[monitor_key]['tp1_info'] = {
                            'filled_at': str(int(time.time() * 1000)),
                            'filled_price': order_info.get('price'),
                            'filled_qty': order_info.get('quantity')
                        }
                        break
                
                print("✅ Applied main account fixes")
                
            elif account == 'mirror':
                # Mirror account - no fills yet
                print("ℹ️ Mirror account - no changes needed")
        
        # Verify changes before saving
        print("\n🔍 Verifying changes...")
        for monitor_key in jasmy_monitors.keys():
            if monitor_key in enhanced_monitors:
                tp1_hit = enhanced_monitors[monitor_key].get('tp1_hit', False)
                phase = enhanced_monitors[monitor_key].get('phase', '')
                print(f"   {monitor_key}: tp1_hit={tp1_hit}, phase={phase}")
        
        # Save with multiple attempts
        print("💾 Saving changes...")
        for attempt in range(3):
            try:
                with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                    pickle.dump(data, f)
                print(f"✅ Save attempt {attempt + 1} successful")
                break
            except Exception as e:
                print(f"❌ Save attempt {attempt + 1} failed: {e}")
                if attempt == 2:
                    raise
                time.sleep(1)
        
        # Immediate verification
        print("🔍 Immediate verification...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            verify_data = pickle.load(f)
        
        verify_monitors = verify_data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        main_fixed = False
        mirror_checked = False
        
        for monitor_key, monitor_data in verify_monitors.items():
            if monitor_data.get('symbol') == 'JASMYUSDT':
                account = monitor_data.get('account_type', 'main')
                tp1_hit = monitor_data.get('tp1_hit', False)
                phase = monitor_data.get('phase', '')
                filled_tps = monitor_data.get('filled_tps', [])
                
                print(f"✅ {monitor_key} ({account}): tp1_hit={tp1_hit}, phase={phase}, filled_tps={filled_tps}")
                
                if account == 'main' and tp1_hit and phase == 'PROFIT_TAKING':
                    main_fixed = True
                elif account == 'mirror':
                    mirror_checked = True
        
        if main_fixed:
            print("🎉 ROBUST JASMY FIX SUCCESSFUL!")
            return True
        else:
            print("❌ ROBUST JASMY FIX FAILED!")
            return False
            
    except Exception as e:
        print(f"❌ Robust fix failed: {e}")
        # Restore backup
        shutil.copy(backup_file, 'bybit_bot_dashboard_v4.1_enhanced.pkl')
        print(f"🔄 Restored backup from {backup_file}")
        raise
    
    finally:
        # Always release lock
        release_pickle_lock(lock_file)

if __name__ == "__main__":
    success = robust_jasmy_fix()
    if success:
        print("🎯 Robust JASMY fix completed successfully!")
        print("🔄 You can now restart the bot - all TPs will be properly detected")
    else:
        print("❌ Robust JASMY fix failed!")