#!/usr/bin/env python3
"""
Direct JASMY Fix
===============

Directly modify the pickle file to fix JASMY TP1 issue.
"""
import pickle
import time

def direct_fix():
    """Direct fix for JASMY"""
    print("🔧 Applying direct JASMY fix...")
    
    # Create backup
    import shutil
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', 'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_jasmy_fix')
    print("📁 Created backup")
    
    # Load data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    for key, monitor in monitors.items():
        if monitor.get('symbol') == 'JASMYUSDT':
            account = monitor.get('account_type', 'main')
            print(f"🎯 Fixing {key} ({account})")
            
            if account == 'main':
                # Main account had ALL TPs filled
                monitor['tp1_hit'] = True
                monitor['phase'] = 'PROFIT_TAKING'
                monitor['phase_transition_time'] = time.time()
                monitor['filled_tps'] = [1, 2, 3, 4]
                monitor['sl_moved_to_be'] = True
                monitor['limit_orders_cancelled'] = True
                
                # Add TP1 info
                tp_orders = monitor.get('tp_orders', {})
                for order_id, order_info in tp_orders.items():
                    if order_info.get('tp_number') == 1:
                        monitor['tp1_info'] = {
                            'filled_at': str(int(time.time() * 1000)),
                            'filled_price': order_info.get('price'),
                            'filled_qty': order_info.get('quantity')
                        }
                        break
                
                print(f"✅ Main account: Set ALL TPs as filled")
                
            else:
                # Mirror account - no fills yet
                print(f"ℹ️ Mirror account: No changes needed")
    
    # Save data
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print("💾 Saved changes")
    
    # Verify
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    for key, monitor in monitors.items():
        if monitor.get('symbol') == 'JASMYUSDT':
            account = monitor.get('account_type', 'main')
            tp1_hit = monitor.get('tp1_hit', False)
            phase = monitor.get('phase', '')
            filled_tps = monitor.get('filled_tps', [])
            
            print(f"✅ {key} ({account}): tp1_hit={tp1_hit}, phase={phase}, filled_tps={filled_tps}")
    
    print("🎉 Direct JASMY fix completed!")

if __name__ == "__main__":
    direct_fix()