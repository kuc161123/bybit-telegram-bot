#!/usr/bin/env python3
"""
Simple JUPUSDT status check using pickle file only
"""

import pickle
from datetime import datetime

def check_jupusdt_status():
    print("=" * 80)
    print("JUPUSDT STATUS FROM PICKLE FILE")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Check Enhanced TP/SL monitors
        print("🔍 ENHANCED TP/SL MONITORS:")
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        jupusdt_enhanced = []
        for key, monitor in enhanced_monitors.items():
            if 'JUPUSDT' in key:
                jupusdt_enhanced.append((key, monitor))
        
        if jupusdt_enhanced:
            for key, monitor in jupusdt_enhanced:
                print(f"\n  Key: {key}")
                print(f"    Account: {monitor.get('account_type', 'Unknown')}")
                print(f"    Symbol: {monitor.get('symbol', 'Unknown')}")
                print(f"    Side: {monitor.get('side', 'Unknown')}")
                print(f"    Created: {monitor.get('created_at', 'Unknown')}")
                print(f"    Active: {monitor.get('active', 'Unknown')}")
                print(f"    Task Status: {monitor.get('task', {}).get('status', 'Unknown') if isinstance(monitor.get('task'), dict) else 'Task object'}")
        else:
            print("  ❌ No Enhanced TP/SL monitors found for JUPUSDT")
        
        # Check dashboard monitors
        print("\n\n🖥️ DASHBOARD MONITORS:")
        monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
        jupusdt_dashboard = []
        for key, monitor in monitor_tasks.items():
            if 'JUPUSDT' in key:
                jupusdt_dashboard.append((key, monitor))
        
        if jupusdt_dashboard:
            for key, monitor in jupusdt_dashboard:
                print(f"\n  Key: {key}")
                print(f"    Status: {monitor.get('status', 'Unknown')}")
                print(f"    Symbol: {monitor.get('symbol', 'Unknown') if isinstance(monitor, dict) else 'N/A'}")
        else:
            print("  ❌ No dashboard monitors found for JUPUSDT")
        
        # Check user positions
        print("\n\n📊 USER POSITIONS:")
        user_data = data.get('user_data', {})
        
        for chat_id, user_info in user_data.items():
            positions = user_info.get('positions', {})
            
            # Check main account positions
            main_positions = positions.get('main', [])
            for pos in main_positions:
                if pos.get('symbol') == 'JUPUSDT':
                    print(f"\n  MAIN Account (Chat {chat_id}):")
                    print(f"    Symbol: {pos.get('symbol')}")
                    print(f"    Side: {pos.get('side')}")
                    print(f"    Size: {pos.get('size')}")
                    print(f"    Avg Price: {pos.get('avgPrice')}")
                    print(f"    P&L: {pos.get('unrealisedPnl')}")
            
            # Check mirror account positions
            mirror_positions = positions.get('mirror', [])
            for pos in mirror_positions:
                if pos.get('symbol') == 'JUPUSDT':
                    print(f"\n  MIRROR Account (Chat {chat_id}):")
                    print(f"    Symbol: {pos.get('symbol')}")
                    print(f"    Side: {pos.get('side')}")
                    print(f"    Size: {pos.get('size')}")
                    print(f"    Avg Price: {pos.get('avgPrice')}")
                    print(f"    P&L: {pos.get('unrealisedPnl')}")
        
        # Check active_monitors (another place monitors might be stored)
        print("\n\n🔎 ACTIVE MONITORS:")
        active_monitors = data.get('bot_data', {}).get('active_monitors', {})
        jupusdt_active = []
        for key, monitor in active_monitors.items():
            if 'JUPUSDT' in str(key):
                jupusdt_active.append((key, monitor))
        
        if jupusdt_active:
            for key, monitor in jupusdt_active:
                print(f"\n  Key: {key}")
                print(f"    Monitor: {monitor}")
        else:
            print("  No active monitors found for JUPUSDT")
            
    except Exception as e:
        print(f"❌ Error reading pickle file: {e}")
    
    print("\n" + "=" * 80)
    print("JUPUSDT PICKLE STATUS CHECK COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    check_jupusdt_status()