#!/usr/bin/env python3
"""
Clear Dashboard Cache

Forces the dashboard to regenerate with the latest AI reasoning
"""

import logging
from utils.dashboard_cache import dashboard_cache

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_cache():
    """Clear all dashboard cache entries"""
    try:
        logger.info("🧹 Clearing dashboard cache...")
        
        # Clear all cache entries
        dashboard_cache._cache.clear()
        
        logger.info("✅ Dashboard cache cleared!")
        logger.info("📌 The next dashboard refresh will show the full AI reasoning")
        logger.info("📌 No bot restart required")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error clearing cache: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Dashboard Cache Clear")
    logger.info("=" * 60)
    
    if clear_cache():
        logger.info("\n🎉 Cache cleared successfully!")
        logger.info("📌 Refresh your dashboard to see the full AI reasoning text")
    else:
        logger.error("\n❌ Failed to clear cache")