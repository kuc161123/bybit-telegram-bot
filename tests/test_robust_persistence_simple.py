#!/usr/bin/env python3
"""
Simple test for Robust Persistence Manager
"""
import asyncio
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_basic_operations():
    """Test basic persistence operations"""
    try:
        logger.info("🚀 Testing Basic Robust Persistence Operations...")
        
        # Import after logging is set up
        from utils.robust_persistence import robust_persistence
        
        # 1. Test reading current data
        logger.info("\n1. Testing data read...")
        data = await robust_persistence.read_data()
        logger.info(f"✅ Successfully read data with keys: {list(data.keys())}")
        
        # 2. Test getting monitors
        logger.info("\n2. Testing monitor retrieval...")
        monitors = await robust_persistence.get_all_monitors()
        logger.info(f"✅ Found {len(monitors)} monitors")
        
        # 3. Test stats
        logger.info("\n3. Testing statistics...")
        stats = await robust_persistence.get_stats()
        logger.info(f"✅ Stats: {stats}")
        
        logger.info("\n✅ All basic tests passed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(test_basic_operations())