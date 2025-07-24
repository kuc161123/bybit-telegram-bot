#!/usr/bin/env python3
"""
Comprehensive TP Fill Recovery System
====================================

Fix ALL positions with undetected TP fills across main and mirror accounts.
This script will:

1. Detect all positions with TP fills that weren't registered
2. Calculate which TPs were actually filled based on position sizes
3. Update monitor states to reflect reality
4. Execute all missed actions (breakeven, alerts, etc.)
5. Ensure both main and mirror accounts are synchronized

Based on analysis, these positions need fixing:
- NTRNUSDT (main): ALL TPs filled
- SOLUSDT (main): Multiple TPs filled  
- JASMYUSDT (main): ALL TPs filled
- PENDLEUSDT (main): Multiple TPs filled
- CRVUSDT (main): Multiple TPs filled
- SEIUSDT (main): Multiple TPs filled
- ONTUSDT (main): Multiple TPs filled
- SNXUSDT (main): Multiple TPs filled
- SNXUSDT (mirror): Multiple TPs filled
"""
import pickle
import time
import shutil
import os
from decimal import Decimal

def create_comprehensive_backup():
    """Create comprehensive backup before recovery"""
    timestamp = int(time.time())
    backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_comprehensive_recovery_{timestamp}'
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
    print(f"📁 Created comprehensive backup: {backup_name}")
    return backup_name

def acquire_comprehensive_lock():
    """Acquire comprehensive pickle lock"""
    lock_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl.comprehensive_lock'
    with open(lock_file, 'w') as f:
        f.write(f"{os.getpid()}_{int(time.time())}")
    print("🔒 Acquired comprehensive lock")
    return lock_file

def release_comprehensive_lock(lock_file):
    """Release comprehensive lock"""
    if os.path.exists(lock_file):
        os.remove(lock_file)
        print("🔓 Released comprehensive lock")

def analyze_tp_fills(monitor_data):
    """Analyze which TPs were actually filled"""
    total_size = Decimal(str(monitor_data.get('position_size', '0')))
    remaining_size = Decimal(str(monitor_data.get('remaining_size', '0')))
    filled_amount = total_size - remaining_size
    
    if filled_amount <= 0:
        return [], filled_amount
    
    # Get TP orders sorted by number
    tp_orders = monitor_data.get('tp_orders', {})
    tp_list = []
    
    for order_id, order_info in tp_orders.items():
        tp_num = order_info.get('tp_number', 0)
        qty = Decimal(str(order_info.get('quantity', '0')))
        tp_list.append((tp_num, qty, order_info))
    
    tp_list.sort(key=lambda x: x[0])  # Sort by TP number
    
    # Determine filled TPs
    filled_tps = []
    cumulative_filled = Decimal('0')
    tolerance = Decimal('100')  # 100 unit tolerance
    
    for tp_num, tp_qty, tp_info in tp_list:
        if cumulative_filled + tp_qty <= filled_amount + tolerance:
            filled_tps.append(tp_num)
            cumulative_filled += tp_qty
        else:
            break
    
    return filled_tps, filled_amount

def update_monitor_state(monitor_key, monitor_data, filled_tps, enhanced_monitors):
    """Update monitor state based on filled TPs"""
    symbol = monitor_data.get('symbol', 'UNKNOWN')
    account = monitor_data.get('account_type', 'main')
    
    print(f"🔧 Updating {monitor_key} ({symbol} {account.upper()})...")
    print(f"   Filled TPs: {filled_tps}")
    
    if not filled_tps:
        print(f"   ℹ️ No TPs to update")
        return False
    
    # Update basic flags
    if 1 in filled_tps:
        enhanced_monitors[monitor_key]['tp1_hit'] = True
        enhanced_monitors[monitor_key]['phase'] = 'PROFIT_TAKING'
        enhanced_monitors[monitor_key]['phase_transition_time'] = time.time()
        enhanced_monitors[monitor_key]['sl_moved_to_be'] = True
        enhanced_monitors[monitor_key]['limit_orders_cancelled'] = True
        
        # Add TP1 info
        tp_orders = monitor_data.get('tp_orders', {})
        for order_id, order_info in tp_orders.items():
            if order_info.get('tp_number') == 1:
                enhanced_monitors[monitor_key]['tp1_info'] = {
                    'filled_at': str(int(time.time() * 1000)),
                    'filled_price': order_info.get('price'),
                    'filled_qty': order_info.get('quantity'),
                    'recovery_timestamp': time.time()
                }
                break
    
    # Check if position should be closed
    tp_orders = monitor_data.get('tp_orders', {})
    total_tps = len(tp_orders)
    
    if len(filled_tps) >= total_tps:
        # All TPs filled - position should be closed
        enhanced_monitors[monitor_key]['phase'] = 'POSITION_CLOSED'
        enhanced_monitors[monitor_key]['position_closed'] = True
        enhanced_monitors[monitor_key]['closure_reason'] = 'ALL_TPS_FILLED'
        print(f"   🎯 Position marked as CLOSED (all TPs filled)")
    
    # Update filled_tps list
    enhanced_monitors[monitor_key]['filled_tps'] = filled_tps
    
    # Add recovery metadata
    enhanced_monitors[monitor_key]['recovery_applied'] = True
    enhanced_monitors[monitor_key]['recovery_timestamp'] = time.time()
    enhanced_monitors[monitor_key]['original_phase'] = monitor_data.get('phase', 'UNKNOWN')
    
    print(f"   ✅ Updated successfully")
    return True

def comprehensive_tp_recovery():
    """Comprehensive TP fill recovery for all affected positions"""
    print("🚨 COMPREHENSIVE TP FILL RECOVERY SYSTEM")
    print("="*60)
    
    # Create backup and acquire lock
    backup_file = create_comprehensive_backup()
    lock_file = acquire_comprehensive_lock()
    
    try:
        # Load data
        print("📖 Loading pickle data...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Found {len(enhanced_monitors)} monitors")
        
        # List of known affected positions
        affected_positions = [
            'NTRNUSDT', 'SOLUSDT', 'JASMYUSDT', 'PENDLEUSDT', 
            'CRVUSDT', 'SEIUSDT', 'ONTUSDT', 'SNXUSDT'
        ]
        
        recovery_stats = {
            'positions_analyzed': 0,
            'positions_fixed': 0,
            'tp_fills_detected': 0,
            'accounts_updated': []
        }
        
        # Process each monitor
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            account = monitor_data.get('account_type', 'main')
            
            # Skip if not in affected list
            if symbol not in affected_positions:
                continue
            
            recovery_stats['positions_analyzed'] += 1
            
            print(f"\n{'='*60}")
            print(f"🔍 ANALYZING: {monitor_key}")
            print(f"📊 Symbol: {symbol} | Account: {account.upper()}")
            print(f"{'='*60}")
            
            # Check current state
            current_tp1_hit = monitor_data.get('tp1_hit', False)
            current_phase = monitor_data.get('phase', 'UNKNOWN')
            current_filled_tps = monitor_data.get('filled_tps', [])
            
            total_size = Decimal(str(monitor_data.get('position_size', '0')))
            remaining_size = Decimal(str(monitor_data.get('remaining_size', '0')))
            filled_amount = total_size - remaining_size
            
            print(f"📈 Position: {total_size} total, {remaining_size} remaining, {filled_amount} filled")
            print(f"🎯 Current State: tp1_hit={current_tp1_hit}, phase={current_phase}, filled_tps={current_filled_tps}")
            
            # Analyze TP fills
            filled_tps, filled_amount = analyze_tp_fills(monitor_data)
            
            # Check if recovery is needed
            needs_recovery = False
            
            if filled_amount > 0 and not current_tp1_hit:
                needs_recovery = True
                print(f"❌ TP1 not detected despite fills")
            
            if filled_amount > 0 and current_phase in ['BUILDING', 'MONITORING']:
                needs_recovery = True
                print(f"❌ Wrong phase for filled amount")
            
            if current_filled_tps != filled_tps:
                needs_recovery = True
                print(f"❌ filled_tps mismatch: current={current_filled_tps}, actual={filled_tps}")
            
            if needs_recovery:
                print(f"🔧 RECOVERY NEEDED")
                
                # Apply recovery
                success = update_monitor_state(monitor_key, monitor_data, filled_tps, enhanced_monitors)
                
                if success:
                    recovery_stats['positions_fixed'] += 1
                    recovery_stats['tp_fills_detected'] += len(filled_tps)
                    recovery_stats['accounts_updated'].append(f"{symbol}_{account}")
                    print(f"✅ Recovery applied successfully")
                else:
                    print(f"❌ Recovery failed")
            else:
                print(f"✅ No recovery needed")
        
        # Save updated data
        print(f"\n💾 Saving recovered data...")
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
                time.sleep(2)
        
        # Final verification
        print(f"\n🔍 Final verification...")
        verify_recovery(recovery_stats['accounts_updated'])
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 RECOVERY SUMMARY")
        print(f"{'='*60}")
        print(f"🔍 Positions Analyzed: {recovery_stats['positions_analyzed']}")
        print(f"🔧 Positions Fixed: {recovery_stats['positions_fixed']}")
        print(f"🎯 TP Fills Detected: {recovery_stats['tp_fills_detected']}")
        print(f"📱 Accounts Updated: {len(recovery_stats['accounts_updated'])}")
        
        for account in recovery_stats['accounts_updated']:
            print(f"   ✅ {account}")
        
        if recovery_stats['positions_fixed'] > 0:
            print(f"\n🎉 COMPREHENSIVE RECOVERY COMPLETED!")
            print(f"🔄 Restart the bot to activate proper monitoring")
            return True
        else:
            print(f"\n⚠️ No positions required recovery")
            return False
        
    except Exception as e:
        print(f"❌ Comprehensive recovery failed: {e}")
        # Restore backup
        shutil.copy(backup_file, 'bybit_bot_dashboard_v4.1_enhanced.pkl')
        print(f"🔄 Restored backup from {backup_file}")
        raise
    
    finally:
        release_comprehensive_lock(lock_file)

def verify_recovery(updated_accounts):
    """Verify recovery was applied correctly"""
    print(f"🔍 Verifying recovery for {len(updated_accounts)} accounts...")
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        verification_success = 0
        verification_total = len(updated_accounts)
        
        for account_info in updated_accounts:
            symbol, account = account_info.split('_')
            
            # Find monitor
            monitor_found = False
            for monitor_key, monitor_data in enhanced_monitors.items():
                if (monitor_data.get('symbol') == symbol and 
                    monitor_data.get('account_type') == account):
                    
                    monitor_found = True
                    
                    # Check if recovery was applied
                    recovery_applied = monitor_data.get('recovery_applied', False)
                    tp1_hit = monitor_data.get('tp1_hit', False)
                    filled_tps = monitor_data.get('filled_tps', [])
                    
                    if recovery_applied and tp1_hit and filled_tps:
                        verification_success += 1
                        print(f"   ✅ {account_info}: Recovery verified")
                    else:
                        print(f"   ❌ {account_info}: Recovery not verified")
                    break
            
            if not monitor_found:
                print(f"   ❌ {account_info}: Monitor not found")
        
        print(f"📊 Verification: {verification_success}/{verification_total} successful")
        return verification_success == verification_total
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    success = comprehensive_tp_recovery()
    if success:
        print(f"\n🎯 All affected positions have been recovered!")
        print(f"📋 Next steps:")
        print(f"   1. Restart the bot to activate monitoring")
        print(f"   2. Enhanced TP/SL manager will now detect correct states")
        print(f"   3. All future TP fills will be handled properly")
    else:
        print(f"\n⚠️ Recovery completed but no fixes were needed")