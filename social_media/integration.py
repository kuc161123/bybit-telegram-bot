#!/usr/bin/env python3
"""
Social Media Sentiment Integration
Main integration point for the trading bot
"""
import logging
import asyncio
from typing import Dict, Any, Optional

from .scheduler import SentimentScheduler
from .storage.sentiment_cache import SentimentCache
from .config import FEATURE_FLAGS, get_configuration_summary
from clients.ai_client import openai_client

logger = logging.getLogger(__name__)

class SocialMediaIntegration:
    """Main integration class for social media sentiment analysis"""
    
    def __init__(self):
        self.scheduler: Optional[SentimentScheduler] = None
        self.cache: Optional[SentimentCache] = None
        self.is_initialized = False
        self.initialization_error = None
    
    async def initialize(self) -> bool:
        """Initialize the social media sentiment system"""
        if self.is_initialized:
            return True
        
        try:
            # Check if feature is enabled
            if not FEATURE_FLAGS["enable_social_sentiment"]:
                logger.info("📱 Social media sentiment analysis is disabled")
                return False
            
            # Get configuration summary
            config_summary = get_configuration_summary()
            enabled_platforms = config_summary["enabled_platforms"]
            
            if not enabled_platforms:
                logger.warning("📱 No social media platforms configured - sentiment analysis unavailable")
                logger.info("💡 Configure API credentials to enable social sentiment analysis")
                return False
            
            logger.info(f"📱 Initializing social media sentiment analysis...")
            logger.info(f"🔧 Enabled platforms: {', '.join(enabled_platforms)} ({len(enabled_platforms)}/5)")
            
            # Initialize cache
            self.cache = SentimentCache()
            
            # Initialize scheduler
            if FEATURE_FLAGS["enable_scheduler"]:
                self.scheduler = SentimentScheduler(openai_client)
                await self.scheduler.start()
                logger.info("⏰ Sentiment collection scheduler started")
            else:
                logger.info("⏰ Sentiment scheduler disabled - manual collection only")
            
            self.is_initialized = True
            logger.info("✅ Social media sentiment system initialized successfully")
            
            return True
            
        except Exception as e:
            self.initialization_error = str(e)
            logger.error(f"❌ Failed to initialize social media sentiment system: {e}")
            return False
    
    async def shutdown(self):
        """Shutdown the social media sentiment system"""
        try:
            if self.scheduler:
                await self.scheduler.stop()
                logger.info("⏹️ Sentiment scheduler stopped")
            
            self.is_initialized = False
            logger.info("📱 Social media sentiment system shutdown complete")
            
        except Exception as e:
            logger.error(f"Error shutting down social media sentiment system: {e}")
    
    async def get_current_sentiment(self) -> Optional[Dict[str, Any]]:
        """Get current aggregated sentiment data"""
        try:
            if not self.is_initialized or not self.cache:
                return None
            
            return await self.cache.get_latest_aggregated_sentiment()
            
        except Exception as e:
            logger.error(f"Error getting current sentiment: {e}")
            return None
    
    async def run_manual_collection(self) -> Dict[str, Any]:
        """Manually trigger a sentiment collection cycle"""
        try:
            if not self.is_initialized:
                await self.initialize()
            
            if not self.scheduler:
                # Create temporary scheduler for manual collection
                temp_scheduler = SentimentScheduler(openai_client)
                result = await temp_scheduler.run_manual_collection()
                return result
            else:
                return await self.scheduler.run_manual_collection()
            
        except Exception as e:
            logger.error(f"Error running manual collection: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": __import__('datetime').datetime.utcnow().isoformat()
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        try:
            config_summary = get_configuration_summary()
            
            status = {
                "initialized": self.is_initialized,
                "feature_enabled": FEATURE_FLAGS["enable_social_sentiment"],
                "platforms_available": config_summary["platforms_count"],
                "enabled_platforms": config_summary["enabled_platforms"],
                "scheduler_running": False,
                "cache_available": self.cache is not None,
                "openai_available": openai_client is not None,
                "initialization_error": self.initialization_error
            }
            
            # Add scheduler status if available
            if self.scheduler:
                scheduler_status = self.scheduler.get_scheduler_status()
                status.update({
                    "scheduler_running": scheduler_status.get("is_running", False),
                    "collection_count": scheduler_status.get("collection_count", 0),
                    "last_collection": scheduler_status.get("last_collection"),
                    "last_collection_success": scheduler_status.get("last_collection_success")
                })
            
            # Add cache status if available
            if self.cache:
                cache_stats = self.cache.get_cache_stats()
                status["cache_stats"] = cache_stats
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "initialized": False,
                "error": str(e)
            }
    
    async def test_system(self) -> Dict[str, Any]:
        """Test the complete social media sentiment system"""
        logger.info("🧪 Testing social media sentiment system...")
        
        try:
            # Test initialization
            if not self.is_initialized:
                init_success = await self.initialize()
                if not init_success:
                    return {
                        "overall_status": "failed",
                        "error": "System initialization failed",
                        "initialization_error": self.initialization_error
                    }
            
            # Test collectors if scheduler is available
            if self.scheduler:
                test_results = await self.scheduler.test_collection_setup()
            else:
                # Basic configuration test
                config_summary = get_configuration_summary()
                test_results = {
                    "overall_status": "basic" if config_summary["platforms_count"] > 0 else "limited",
                    "enabled_platforms": config_summary["enabled_platforms"],
                    "platforms_count": config_summary["platforms_count"]
                }
            
            # Test cache functionality
            if self.cache:
                test_data = {
                    "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
                    "test": True,
                    "overall_sentiment": "NEUTRAL",
                    "sentiment_score": 50
                }
                
                cache_store_success = await self.cache.store_aggregated_sentiment(test_data)
                cached_data = await self.cache.get_latest_aggregated_sentiment()
                cache_working = cache_store_success and cached_data is not None
                
                test_results["cache_test"] = {
                    "working": cache_working,
                    "store_success": cache_store_success,
                    "retrieve_success": cached_data is not None
                }
                
                # Clean up test data
                if cache_working:
                    await self.cache.clear_cache("aggregated_sentiment")
            
            logger.info(f"🧪 System test completed: {test_results.get('overall_status', 'unknown')}")
            return test_results
            
        except Exception as e:
            logger.error(f"System test failed: {e}")
            return {
                "overall_status": "error",
                "error": str(e)
            }

# Global instance
social_media_integration = SocialMediaIntegration()

# Convenience functions for external use
async def initialize_social_media_sentiment() -> bool:
    """Initialize social media sentiment analysis"""
    return await social_media_integration.initialize()

async def get_current_market_sentiment() -> Optional[Dict[str, Any]]:
    """Get current market sentiment from social media"""
    return await social_media_integration.get_current_sentiment()

async def trigger_sentiment_collection() -> Dict[str, Any]:
    """Manually trigger a sentiment collection cycle"""
    return await social_media_integration.run_manual_collection()

def get_sentiment_system_status() -> Dict[str, Any]:
    """Get social media sentiment system status"""
    return social_media_integration.get_system_status()

async def test_sentiment_system() -> Dict[str, Any]:
    """Test the social media sentiment system"""
    return await social_media_integration.test_system()

async def shutdown_social_media_sentiment():
    """Shutdown social media sentiment system"""
    await social_media_integration.shutdown()