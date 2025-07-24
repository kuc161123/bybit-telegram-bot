#!/usr/bin/env python3
"""
Test the emergency shutdown fix
"""

import asyncio
import logging
from execution.emergency import execute_emergency_shutdown

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def test_emergency():
    """Test emergency shutdown functionality"""
    print("\n🚨 TESTING EMERGENCY SHUTDOWN...")
    
    try:
        # Execute emergency shutdown
        success, message = await execute_emergency_shutdown(include_mirror=True)
        
        print(f"\nSuccess: {success}")
        print(f"Message:\n{message}")
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_emergency())