#!/usr/bin/env python3
"""
Validate all positions have correct setup
"""
import pickle

def validate_all_positions():
    """Check all positions for correct configuration"""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        issues = []
        
        for monitor_key, monitor_data in monitors.items():
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account_type = monitor_data.get('account_type', 'unknown')
            
            # Check chat_id
            if not monitor_data.get('chat_id'):
                issues.append(f"{symbol} {side} ({account_type}) - Missing chat_id")
            
            # Check TP numbers
            tp_orders = monitor_data.get('tp_orders', {})
            for order_id, tp_data in tp_orders.items():
                if tp_data.get('tp_number', 0) == 0:
                    issues.append(f"{symbol} {side} ({account_type}) - TP0 found!")
            
            # Check account type
            if account_type == 'unknown':
                issues.append(f"{symbol} {side} - Unknown account type")
        
        if issues:
            print("❌ Issues found:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("✅ All positions properly configured!")
            
        # Summary
        main_count = sum(1 for k in monitors if monitors[k].get('account_type') == 'main')
        mirror_count = sum(1 for k in monitors if monitors[k].get('account_type') == 'mirror')
        
        print(f"\n📊 Position Summary:")
        print(f"  Total: {len(monitors)} monitors")
        print(f"  Main Account: {main_count}")
        print(f"  Mirror Account: {mirror_count}")
        
        return len(issues) == 0
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    validate_all_positions()
