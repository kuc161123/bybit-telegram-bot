#!/usr/bin/env python3
"""
Verify that the TP1 calculation fix is properly implemented
"""
import asyncio
import logging
from dashboard.generator_analytics_compact import build_analytics_dashboard_text

# Enable all logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def verify_tp1_fix():
    """Verify the TP1 calculation is correct"""
    
    print("\n=== VERIFYING TP1 CALCULATION FIX ===\n")
    
    # Mock context
    class MockContext:
        def __init__(self):
            self.chat_data = {}
            self.bot_data = {}
    
    context = MockContext()
    
    # Build dashboard multiple times to check for consistency
    print("Building dashboard 3 times to check for consistency...\n")
    
    tp1_values = []
    
    for i in range(3):
        print(f"Run {i+1}:")
        dashboard = await build_analytics_dashboard_text(context.chat_data, context)
        
        # Extract TP1 value
        lines = dashboard.split('\n')
        for line in lines:
            if 'TP1 Orders' in line:
                # Extract the dollar value
                import re
                match = re.search(r'\$([0-9,]+\.?\d*)', line)
                if match:
                    value = float(match.group(1).replace(',', ''))
                    tp1_values.append(value)
                    print(f"   Found: {line.strip()} (value: ${value})")
                break
    
    print(f"\n=== RESULTS ===")
    print(f"TP1 values found: {tp1_values}")
    
    if len(set(tp1_values)) == 1:
        print("✅ Values are consistent across runs")
        
        actual_value = tp1_values[0]
        if abs(actual_value - 177.15) < 1:
            print("✅ Value matches expected $177.15")
            print("\n✅ FIX IS PROPERLY IMPLEMENTED!")
            print("\nIf user still sees $337.3, they may need to:")
            print("1. Restart the bot to load the latest code")
            print("2. Clear any cached dashboard data")
            print("3. Use /refresh command to get fresh data")
        elif abs(actual_value - 337.3) < 1:
            print("❌ Value matches the incorrect $337.3")
            print("The deduplication fix is NOT working properly!")
        else:
            print(f"⚠️ Unexpected value: ${actual_value}")
    else:
        print("❌ Values are INCONSISTENT across runs!")
        print("This suggests a race condition or caching issue")
    
    # Also check the implementation
    print("\n=== CHECKING IMPLEMENTATION ===")
    
    # Read the deduplication code
    with open('dashboard/generator_analytics_compact.py', 'r') as f:
        content = f.read()
        
    if 'Skipping duplicate mirror position' in content:
        print("✅ Deduplication logging is present")
    else:
        print("❌ Deduplication logging is missing")
    
    if 'mirror_key not in main_position_keys' in content:
        print("✅ Deduplication logic is present")
    else:
        print("❌ Deduplication logic is missing")
    
    if 'potential_profit_tp1_full' in content:
        print("✅ Full position TP1 calculation is present")
    else:
        print("❌ Full position TP1 calculation is missing")

if __name__ == "__main__":
    asyncio.run(verify_tp1_fix())