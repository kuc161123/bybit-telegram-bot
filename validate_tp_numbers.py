#!/usr/bin/env python3
"""
Validate TP numbers in monitor data
"""
import pickle

def validate_tp_numbers():
    """Check all monitors for TP numbering issues"""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        issues = []
        
        for monitor_key, monitor_data in monitors.items():
            symbol = monitor_data.get('symbol', 'Unknown')
            side = monitor_data.get('side', 'Unknown')
            account_type = monitor_data.get('account_type', 'main')
            approach = monitor_data.get('approach', 'fast').lower()
            tp_orders = monitor_data.get('tp_orders', {})
            
            for order_id, tp_data in tp_orders.items():
                tp_number = tp_data.get('tp_number', 0)
                percentage = tp_data.get('percentage', 0)
                
                if tp_number == 0:
                    issues.append(f"TP0 found in {symbol} {side} ({account_type})")
                
                # Validate percentage matches TP number for conservative
                if approach == 'conservative':
                    expected_percentages = {1: 85, 2: 5, 3: 5, 4: 5}
                    if tp_number in expected_percentages and percentage != expected_percentages[tp_number]:
                        issues.append(f"Wrong percentage for TP{tp_number} in {symbol} {side} ({account_type}): {percentage}% (expected {expected_percentages[tp_number]}%)")
        
        if issues:
            print("❌ Issues found:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("✅ All TP numbers are valid!")
        
        return len(issues) == 0
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    validate_tp_numbers()
