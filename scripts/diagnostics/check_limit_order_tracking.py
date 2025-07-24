#!/usr/bin/env python3
"""
Check Limit Order Tracking
=========================

This script checks if limit orders are properly tracked in the Enhanced TP/SL monitors.
"""

import pickle
import json
from datetime import datetime

def check_limit_order_tracking():
    """Check limit order tracking in all monitors"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        print("\n" + "="*80)
        print("📊 LIMIT ORDER TRACKING REPORT")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total monitors: {len(monitors)}")
        print("="*80)
        
        # Check each monitor
        monitors_with_limits = 0
        total_limit_orders = 0
        
        for monitor_key, monitor in monitors.items():
            symbol = monitor.get('symbol', 'Unknown')
            side = monitor.get('side', 'Unknown')
            approach = monitor.get('approach', 'Unknown')
            account = monitor.get('account_type', 'main')
            limit_orders = monitor.get('limit_orders', [])
            
            if limit_orders:
                monitors_with_limits += 1
                print(f"\n🎯 {symbol} {side} ({account}) - {approach.upper()}")
                print(f"   Monitor key: {monitor_key}")
                print(f"   Position size: {monitor.get('position_size', 'N/A')}")
                print(f"   Limit orders tracked: {len(limit_orders)}")
                
                # Check each limit order
                for i, order in enumerate(limit_orders, 1):
                    if isinstance(order, str):
                        print(f"   {i}. Order ID: {order[:8]}... (legacy format)")
                        total_limit_orders += 1
                    elif isinstance(order, dict):
                        order_id = order.get('order_id', 'Unknown')
                        status = order.get('status', 'Unknown')
                        registered = order.get('registered_at', 0)
                        if registered:
                            reg_time = datetime.fromtimestamp(registered).strftime('%H:%M:%S')
                        else:
                            reg_time = 'Unknown'
                        
                        print(f"   {i}. Order ID: {order_id[:8]}...")
                        print(f"      Status: {status}")
                        print(f"      Registered: {reg_time}")
                        
                        if status == "CANCELLED":
                            cancelled_at = order.get('cancelled_at', 0)
                            if cancelled_at:
                                cancel_time = datetime.fromtimestamp(cancelled_at).strftime('%H:%M:%S')
                                print(f"      Cancelled: {cancel_time}")
                        
                        total_limit_orders += 1
                
                # Check phase
                phase = monitor.get('phase', 'Unknown')
                print(f"   Phase: {phase}")
                if monitor.get('tp1_hit'):
                    print(f"   TP1 Hit: ✅ (limit orders should be cancelled)")
        
        # Summary
        print("\n" + "="*80)
        print("📊 SUMMARY")
        print("="*80)
        print(f"Monitors with limit orders: {monitors_with_limits}/{len(monitors)}")
        print(f"Total limit orders tracked: {total_limit_orders}")
        
        if monitors_with_limits == 0:
            print("\n⚠️ No monitors are tracking limit orders!")
            print("This could mean:")
            print("1. All positions are using fast approach (no limit orders)")
            print("2. Limit orders were not registered properly")
            print("3. All limit orders have been cancelled (TP1 hit)")
        
        # Check for conservative positions without limit orders
        print("\n" + "="*80)
        print("🔍 CONSERVATIVE POSITIONS CHECK")
        print("="*80)
        
        conservative_without_limits = []
        for monitor_key, monitor in monitors.items():
            if monitor.get('approach') == 'conservative' and not monitor.get('limit_orders'):
                conservative_without_limits.append(monitor_key)
        
        if conservative_without_limits:
            print(f"⚠️ Found {len(conservative_without_limits)} conservative positions without limit orders:")
            for key in conservative_without_limits:
                monitor = monitors[key]
                print(f"   - {monitor.get('symbol')} {monitor.get('side')} ({monitor.get('account_type', 'main')})")
                print(f"     Phase: {monitor.get('phase', 'Unknown')}")
                print(f"     TP1 Hit: {'✅' if monitor.get('tp1_hit') else '❌'}")
        else:
            print("✅ All conservative positions have limit order tracking")
        
        return monitors_with_limits > 0
        
    except Exception as e:
        print(f"Error checking limit order tracking: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_limit_order_tracking()