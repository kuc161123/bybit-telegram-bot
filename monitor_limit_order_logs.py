#!/usr/bin/env python3
"""
Monitor the bot logs in real-time to see when limit order checking happens.
This helps verify the fix is working during actual bot operation.
"""
import subprocess
import re
from datetime import datetime

print("🔍 Monitoring Bot Logs for Limit Order Detection")
print("="*80)
print("Looking for limit order checking messages...")
print("Press Ctrl+C to stop monitoring\n")

# Patterns to look for
patterns = [
    (r"🔍 Checking limit orders for (\S+): (\d+) orders registered", "LIMIT_CHECK"),
    (r"🔍 Found (\d+) order IDs to check for (\S+)", "ORDER_IDS"),
    (r"📊 Checking order (\S+) status", "ORDER_STATUS"),
    (r"✅ Limit order (\d+) filled", "LIMIT_FILLED"),
    (r"🎯 Detected limit fill", "FILL_DETECTED"),
    (r"📊 Rebalancing TPs after limit fill", "TP_REBALANCE"),
    (r"USE_DIRECT_ORDER_CHECKS is True, using optimized monitoring", "DIRECT_CHECK")
]

# Stats
stats = {
    "LIMIT_CHECK": 0,
    "ORDER_IDS": 0,
    "ORDER_STATUS": 0,
    "LIMIT_FILLED": 0,
    "FILL_DETECTED": 0,
    "TP_REBALANCE": 0,
    "DIRECT_CHECK": 0
}

try:
    # Use tail -f to follow the log file
    process = subprocess.Popen(
        ['tail', '-f', 'trading_bot.log'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    print("📊 Real-time Log Analysis:")
    print("-"*80)
    
    for line in process.stdout:
        # Check each pattern
        for pattern, event_type in patterns:
            match = re.search(pattern, line)
            if match:
                timestamp = datetime.now().strftime("%H:%M:%S")
                stats[event_type] += 1
                
                if event_type == "LIMIT_CHECK":
                    print(f"[{timestamp}] ✅ Limit order check triggered for {match.group(1)} ({match.group(2)} orders)")
                elif event_type == "ORDER_IDS":
                    print(f"[{timestamp}] 📍 Checking {match.group(1)} order IDs for {match.group(2)}")
                elif event_type == "ORDER_STATUS":
                    print(f"[{timestamp}] 🔍 Checking status of order {match.group(1)}")
                elif event_type == "LIMIT_FILLED":
                    print(f"[{timestamp}] 🎯 LIMIT ORDER {match.group(1)} FILLED! Alert should be sent.")
                elif event_type == "FILL_DETECTED":
                    print(f"[{timestamp}] 💰 Fill detection confirmed!")
                elif event_type == "TP_REBALANCE":
                    print(f"[{timestamp}] 🔄 TP rebalancing triggered!")
                elif event_type == "DIRECT_CHECK":
                    print(f"[{timestamp}] ⚠️ USE_DIRECT_ORDER_CHECKS is active")
                
                # Show running stats every 10 events
                total_events = sum(stats.values())
                if total_events % 10 == 0:
                    print(f"\n📊 Stats: Checks={stats['LIMIT_CHECK']}, Fills={stats['LIMIT_FILLED']}, Rebalances={stats['TP_REBALANCE']}\n")
                    
except KeyboardInterrupt:
    print("\n\n📊 Final Statistics:")
    print("="*80)
    for event_type, count in stats.items():
        if count > 0:
            print(f"{event_type:15}: {count:5} occurrences")
    
    print("\n💡 Summary:")
    if stats["LIMIT_CHECK"] > 0:
        print("✅ Limit order checking is working!")
        print(f"   - {stats['LIMIT_CHECK']} limit order checks performed")
        if stats["LIMIT_FILLED"] > 0:
            print(f"   - {stats['LIMIT_FILLED']} limit fills detected")
            print(f"   - {stats['TP_REBALANCE']} TP rebalances triggered")
    else:
        print("⚠️ No limit order checking detected during monitoring period")
        print("   - Make sure you have positions with limit orders")
        print("   - Check if monitors are loaded properly")
finally:
    if 'process' in locals():
        process.terminate()