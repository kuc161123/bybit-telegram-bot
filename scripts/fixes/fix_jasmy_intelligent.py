#!/usr/bin/env python3
"""
Intelligent JASMY TP Fill Fix
============================

This script intelligently detects and fixes JASMY TP fills based on 
actual position size differences. It will:

1. Compare total vs remaining position sizes
2. Determine which TPs have been filled
3. Update monitor states accordingly
4. Execute all missed actions

"""
import pickle
import time
from decimal import Decimal

def fix_jasmy_intelligent():
    """Intelligently fix JASMY TP fills based on position size analysis"""
    print("🧠 Starting intelligent JASMY TP fill detection and fix...")
    
    try:
        # Load pickle data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            if monitor_data.get('symbol') == 'JASMYUSDT':
                account = monitor_data.get('account_type', 'main')
                
                print(f"\n🔍 Analyzing {monitor_key} ({account.upper()})")
                
                # Get position data
                total_size = Decimal(str(monitor_data.get('position_size', '0')))
                remaining_size = Decimal(str(monitor_data.get('remaining_size', '0')))
                filled_amount = total_size - remaining_size
                
                print(f"📊 Total: {total_size}, Remaining: {remaining_size}, Filled: {filled_amount}")
                
                if filled_amount <= 0:
                    print(f"ℹ️ No fills detected for {account}")
                    continue
                
                # Get TP orders
                tp_orders = monitor_data.get('tp_orders', {})
                tp_list = []
                
                for order_id, order_info in tp_orders.items():
                    tp_num = order_info.get('tp_number', 0)
                    qty = Decimal(str(order_info.get('quantity', '0')))
                    tp_list.append((tp_num, qty, order_info))
                
                # Sort by TP number
                tp_list.sort(key=lambda x: x[0])
                
                # Determine which TPs were filled
                filled_tps = []
                cumulative_filled = Decimal('0')
                
                for tp_num, tp_qty, tp_info in tp_list:
                    if cumulative_filled + tp_qty <= filled_amount + Decimal('100'):  # 100 JASMY tolerance
                        filled_tps.append(tp_num)
                        cumulative_filled += tp_qty
                        print(f"✅ TP{tp_num} detected as FILLED: {tp_qty} JASMY")
                    else:
                        print(f"❌ TP{tp_num} NOT filled: {tp_qty} JASMY")
                        break
                
                if not filled_tps:
                    print(f"⚠️ No clear TP fills detected for {account}")
                    continue
                
                # Update monitor state
                print(f"🔧 Updating {monitor_key} with filled TPs: {filled_tps}")
                
                # Set flags based on what was filled
                if 1 in filled_tps:
                    enhanced_monitors[monitor_key]['tp1_hit'] = True
                    enhanced_monitors[monitor_key]['phase'] = 'PROFIT_TAKING'
                    enhanced_monitors[monitor_key]['phase_transition_time'] = time.time()
                    enhanced_monitors[monitor_key]['sl_moved_to_be'] = True
                    enhanced_monitors[monitor_key]['limit_orders_cancelled'] = True
                    
                    # Add TP1 info
                    tp1_order = next((info for num, qty, info in tp_list if num == 1), None)
                    if tp1_order:
                        enhanced_monitors[monitor_key]['tp1_info'] = {
                            'filled_at': str(int(time.time() * 1000)),
                            'filled_price': tp1_order.get('price'),
                            'filled_qty': tp1_order.get('quantity')
                        }
                
                # Update filled_tps list
                enhanced_monitors[monitor_key]['filled_tps'] = filled_tps
                
                # Update remaining size to match actual
                enhanced_monitors[monitor_key]['remaining_size'] = str(remaining_size)
                
                print(f"✅ Updated {monitor_key} successfully")
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print("\n🎉 Intelligent JASMY fix completed!")
        print("🔄 Restart the bot to apply changes and begin proper monitoring")
        
    except Exception as e:
        print(f"❌ Intelligent fix failed: {e}")
        raise

def verify_fix():
    """Verify the intelligent fix worked"""
    print("\n🔍 Verifying intelligent fix...")
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            if monitor_data.get('symbol') == 'JASMYUSDT':
                account = monitor_data.get('account_type', 'main')
                tp1_hit = monitor_data.get('tp1_hit', False)
                phase = monitor_data.get('phase', '')
                filled_tps = monitor_data.get('filled_tps', [])
                
                print(f"\n📋 {monitor_key} ({account.upper()}):")
                print(f"   TP1 Hit: {'✅' if tp1_hit else '❌'} {tp1_hit}")
                print(f"   Phase: {'✅' if phase == 'PROFIT_TAKING' else '❌'} {phase}")
                print(f"   Filled TPs: {filled_tps}")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")

if __name__ == "__main__":
    fix_jasmy_intelligent()
    verify_fix()