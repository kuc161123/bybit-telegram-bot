#!/usr/bin/env python3
"""
Debug script to trace TP1 calculation issue showing $337.3
"""
import asyncio
import logging
from dashboard.generator_analytics_compact import build_analytics_dashboard_text

# Configure logging to see all warnings
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def debug_tp1_calculation():
    """Debug the TP1 calculation to find where $337.3 comes from"""
    
    print("\n=== DEBUGGING TP1 CALCULATION ($337.3 issue) ===\n")
    
    # Mock context with empty data to trigger fresh calculation
    class MockContext:
        def __init__(self):
            self.chat_data = {}
            self.bot_data = {}
    
    context = MockContext()
    
    print("Building dashboard with enhanced logging...")
    print("Check the WARNING logs below for TP1 calculation details:\n")
    
    # Build dashboard which will trigger our debug logging
    dashboard = await build_analytics_dashboard_text(context.chat_data, context)
    
    # Extract and display the P&L section
    print("\n=== DASHBOARD P&L SECTION ===")
    lines = dashboard.split('\n')
    for i, line in enumerate(lines):
        if 'POTENTIAL P&L ANALYSIS' in line:
            for j in range(i, min(i+6, len(lines))):
                print(lines[j].strip())
            break
    
    print("\n=== ANALYSIS ===")
    print("1. Check if the logged position count matches what's shown")
    print("2. Look for any positions with unusually high TP1 profits")
    print("3. Verify if TP1 quantity matches position size")
    print("4. Check if there are any calculation errors in the logs above")

if __name__ == "__main__":
    asyncio.run(debug_tp1_calculation())