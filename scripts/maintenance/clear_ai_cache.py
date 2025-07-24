#!/usr/bin/env python3
"""
Clear AI reasoning cache and dashboard cache
"""

import logging
from utils.dashboard_cache import dashboard_cache
from market_analysis.market_status_engine import market_status_engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_all_caches():
    """Clear all relevant caches"""
    try:
        logger.info("🧹 Clearing caches...")
        
        # Clear dashboard cache
        dashboard_cache._cache.clear()
        logger.info("✅ Dashboard cache cleared")
        
        # Clear market status engine cache
        if hasattr(market_status_engine, 'cache'):
            market_status_engine.cache.clear()
            logger.info("✅ Market status cache cleared")
        
        # Clear AI reasoning cache if exists
        try:
            from execution.ai_reasoning_engine import _reasoning_engine
            if _reasoning_engine and hasattr(_reasoning_engine, 'reasoning_cache'):
                _reasoning_engine.reasoning_cache.clear()
                logger.info("✅ AI reasoning cache cleared")
        except:
            pass
        
        logger.info("🎉 All caches cleared successfully!")
        logger.info("📌 The next dashboard refresh will show the full AI reasoning")
        logger.info("📌 No bot restart required")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error clearing caches: {e}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Cache Clear Utility")
    logger.info("=" * 60)
    
    if clear_all_caches():
        logger.info("\n✅ Success! Refresh your dashboard to see the full AI reasoning text")
    else:
        logger.error("\n❌ Failed to clear caches")