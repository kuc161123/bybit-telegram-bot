#!/usr/bin/env python3
"""
Check Mirror Sync Errors
========================

Quick diagnostic to check if mirror sync is experiencing errors.
"""

import os
import sys
import pickle
from datetime import datetime, timedelta
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_recent_logs():
    """Check recent log entries for mirror sync errors"""
    print("\n1. Checking Recent Log Entries:")
    print("-" * 60)
    
    log_file = "trading_bot.log"
    error_patterns = [
        "qty err",
        "quantity error", 
        "order not exists",
        "mirror",
        "sync",
        "retCode",
        "failed to place",
        "failed to cancel"
    ]
    
    error_counts = defaultdict(int)
    recent_errors = []
    
    try:
        with open(log_file, 'r') as f:
            # Read last 1000 lines
            lines = f.readlines()[-1000:]
            
            for line in lines:
                line_lower = line.lower()
                for pattern in error_patterns:
                    if pattern in line_lower and ("error" in line_lower or "warning" in line_lower):
                        error_counts[pattern] += 1
                        if len(recent_errors) < 10:  # Keep last 10 errors
                            recent_errors.append(line.strip())
        
        if error_counts:
            print("Error pattern counts:")
            for pattern, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  - {pattern}: {count} occurrences")
            
            print("\nRecent error samples:")
            for error in recent_errors[-5:]:  # Show last 5
                print(f"  {error[:100]}...")
        else:
            print("✓ No recent mirror sync errors found")
            
    except FileNotFoundError:
        print("⚠️  Log file not found")
    except Exception as e:
        print(f"⚠️  Error reading logs: {e}")

def check_pickle_state():
    """Check pickle file for monitor states"""
    print("\n2. Checking Monitor States:")
    print("-" * 60)
    
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        # Check enhanced monitors
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
        
        print(f"Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        print(f"Dashboard monitor tasks: {len(monitor_tasks)}")
        
        # Check for mirror monitors
        mirror_monitors = [k for k in monitor_tasks.keys() if 'mirror' in k.lower()]
        print(f"Mirror account monitors: {len(mirror_monitors)}")
        
        # Check positions
        total_positions = 0
        mirror_positions = 0
        
        for chat_id, user_data in data.get('user_data', {}).items():
            positions = user_data.get('positions', {})
            for pos_key, pos_data in positions.items():
                total_positions += 1
                if pos_data.get('account_type') == 'mirror':
                    mirror_positions += 1
        
        print(f"\nTotal positions: {total_positions}")
        print(f"Mirror positions: {mirror_positions}")
        
        # Check for any error states in monitor data
        error_monitors = []
        for key, monitor in monitor_tasks.items():
            if monitor.get('status') == 'error' or monitor.get('error_count', 0) > 0:
                error_monitors.append(key)
        
        if error_monitors:
            print(f"\n⚠️  Monitors with errors: {len(error_monitors)}")
            for key in error_monitors[:5]:
                print(f"  - {key}")
        else:
            print("\n✓ No monitors in error state")
            
    except FileNotFoundError:
        print("⚠️  Pickle file not found")
    except Exception as e:
        print(f"⚠️  Error reading pickle file: {e}")

def check_api_connectivity():
    """Quick API connectivity check"""
    print("\n3. Checking API Connectivity:")
    print("-" * 60)
    
    try:
        from clients.bybit_client import bybit_client
        
        # Check main account
        try:
            response = bybit_client.get_wallet_balance(accountType="UNIFIED")
            if response['retCode'] == 0:
                print("✓ Main account API connection OK")
            else:
                print(f"⚠️  Main account API error: {response.get('retMsg')}")
        except Exception as e:
            print(f"❌ Main account connection failed: {e}")
        
        # Check mirror account if enabled
        if os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true':
            try:
                from clients.bybit_client import bybit_client_2
                response = bybit_client_2.get_wallet_balance(accountType="UNIFIED")
                if response['retCode'] == 0:
                    print("✓ Mirror account API connection OK")
                else:
                    print(f"⚠️  Mirror account API error: {response.get('retMsg')}")
            except Exception as e:
                print(f"❌ Mirror account connection failed: {e}")
        else:
            print("ℹ️  Mirror trading not enabled")
            
    except ImportError as e:
        print(f"❌ Failed to import Bybit client: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    """Run all checks"""
    print("Mirror Sync Error Diagnostic")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    check_recent_logs()
    check_pickle_state()
    check_api_connectivity()
    
    print("\n" + "=" * 60)
    print("Diagnostic Summary:")
    print("- Check the log analysis for recent error patterns")
    print("- Monitor states show active/error status")
    print("- API connectivity indicates if connections are working")
    print("\nIf errors are found:")
    print("1. The enhanced error handling will automatically retry")
    print("2. Circuit breakers will prevent error flooding")
    print("3. Positions will remain protected during sync issues")

if __name__ == "__main__":
    main()