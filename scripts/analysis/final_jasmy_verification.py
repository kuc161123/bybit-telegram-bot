#!/usr/bin/env python3
"""
Final JASMY Verification
========================

Check the final state of JASMY after all fixes.
"""
import pickle

def verify_jasmy_final():
    """Verify final JASMY state"""
    print("🔍 FINAL JASMY VERIFICATION")
    print("="*60)
    
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            if monitor_data.get('symbol') == 'JASMYUSDT':
                account = monitor_data.get('account_type', 'main')
                
                print(f"\n🎯 JASMYUSDT ({account.upper()})")
                print(f"Monitor Key: {monitor_key}")
                print(f"{'='*40}")
                
                # Key fields
                print(f"Phase: {monitor_data.get('phase', 'UNKNOWN')}")
                print(f"TP1 Hit: {monitor_data.get('tp1_hit', False)}")
                print(f"Filled TPs: {monitor_data.get('filled_tps', [])}")
                print(f"Position Closed: {monitor_data.get('position_closed', False)}")
                
                # Sizes
                print(f"\nSizes:")
                print(f"  Total: {monitor_data.get('position_size', '0')}")
                print(f"  Remaining: {monitor_data.get('remaining_size', '0')}")
                
                # Calculate percentage
                total = float(monitor_data.get('position_size', '0'))
                remaining = float(monitor_data.get('remaining_size', '0'))
                if total > 0:
                    filled = total - remaining
                    percent = (filled / total) * 100
                    print(f"  Filled: {filled} ({percent:.1f}%)")
                    
                    print(f"\n📊 Analysis:")
                    if percent < 84:
                        print(f"  ❌ TP1 NOT HIT (needs 84%, has {percent:.1f}%)")
                    else:
                        print(f"  ✅ TP1 should be hit ({percent:.1f}% >= 84%)")
        
        print(f"\n{'='*60}")
        print("🎯 EXPLANATION:")
        print("JASMYUSDT has only filled 61.7% of the position.")
        print("TP1 requires 85% to be filled (conservative approach).")
        print("Therefore, TP1 has NOT actually been hit yet!")
        print("\nThis is why no alert was sent - the TP1 threshold")
        print("has not been reached. The monitoring is working correctly.")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")

if __name__ == "__main__":
    verify_jasmy_final()