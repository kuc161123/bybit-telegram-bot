#!/usr/bin/env python3
"""
Social Media Sentiment Collection Scheduler
Manages 6-hour collection cycles and background tasks
"""
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .main_collector import SocialMediaCollector
from .storage.sentiment_cache import SentimentCache

logger = logging.getLogger(__name__)

class SentimentScheduler:
    def __init__(self, openai_client=None):
        """Initialize sentiment collection scheduler"""
        self.openai_client = openai_client
        self.collector = SocialMediaCollector(openai_client)
        self.cache = SentimentCache()
        self.scheduler = AsyncIOScheduler()
        
        # Scheduler state
        self.is_running = False
        self.last_collection_result = None
        self.collection_count = 0
        
        # Setup scheduled jobs
        self._setup_scheduled_jobs()
    
    def _setup_scheduled_jobs(self):
        """Setup all scheduled jobs"""
        
        # Main sentiment collection cycles (every 6 hours)
        self.scheduler.add_job(
            self._run_sentiment_collection_job,
            CronTrigger(hour="0,6,12,18", minute=0),  # 00:00, 06:00, 12:00, 18:00 UTC
            id="sentiment_collection_cycle",
            name="6-Hour Sentiment Collection Cycle",
            max_instances=1,
            coalesce=True
        )
        
        # Daily cleanup and maintenance (02:00 UTC)
        self.scheduler.add_job(
            self._daily_maintenance_job,
            CronTrigger(hour=2, minute=0),
            id="daily_maintenance",
            name="Daily Cache Cleanup and Maintenance",
            max_instances=1
        )
        
        # Hourly cache update (for dashboard refreshing)
        self.scheduler.add_job(
            self._hourly_cache_refresh_job,
            CronTrigger(minute=0),  # Every hour at minute 0
            id="hourly_cache_refresh",
            name="Hourly Cache Refresh",
            max_instances=1
        )
        
        # API usage monitoring (every 30 minutes)
        self.scheduler.add_job(
            self._api_usage_monitoring_job,
            CronTrigger(minute="0,30"),  # Every 30 minutes
            id="api_usage_monitoring",
            name="API Usage Monitoring",
            max_instances=1
        )
        
        logger.info("✅ Scheduled jobs configured:")
        logger.info("  📊 Sentiment Collection: Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)")
        logger.info("  🧹 Daily Maintenance: 02:00 UTC")
        logger.info("  🔄 Cache Refresh: Every hour")
        logger.info("  📈 API Monitoring: Every 30 minutes")
    
    async def start(self):
        """Start the sentiment collection scheduler"""
        try:
            if not self.is_running:
                self.scheduler.start()
                self.is_running = True
                logger.info("🚀 Sentiment collection scheduler started")
                
                # Run initial collection if none exists
                await self._check_initial_collection()
            
        except Exception as e:
            logger.error(f"Error starting sentiment scheduler: {e}")
    
    async def stop(self):
        """Stop the sentiment collection scheduler"""
        try:
            if self.is_running:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("⏹️ Sentiment collection scheduler stopped")
            
        except Exception as e:
            logger.error(f"Error stopping sentiment scheduler: {e}")
    
    async def _check_initial_collection(self):
        """Check if we need to run an initial collection"""
        try:
            # Check if we have recent cached data
            cached_sentiment = await self.cache.get_latest_aggregated_sentiment()
            
            if not cached_sentiment:
                logger.info("📊 No cached sentiment data found, running initial collection...")
                await self._run_sentiment_collection_job()
            else:
                # Check cache age
                cache_timestamp = cached_sentiment.get("timestamp")
                if cache_timestamp:
                    from datetime import datetime
                    cache_time = datetime.fromisoformat(cache_timestamp)
                    age_hours = (datetime.utcnow() - cache_time).total_seconds() / 3600
                    
                    if age_hours > 6:
                        logger.info(f"📊 Cached data is {age_hours:.1f}h old, running fresh collection...")
                        await self._run_sentiment_collection_job()
                    else:
                        logger.info(f"📊 Using cached sentiment data ({age_hours:.1f}h old)")
        
        except Exception as e:
            logger.error(f"Error checking initial collection: {e}")
    
    async def _run_sentiment_collection_job(self):
        """Run the main sentiment collection job"""
        job_start = datetime.utcnow()
        logger.info("🎯 Starting scheduled sentiment collection cycle...")
        
        try:
            # Run collection cycle
            collection_result = await self.collector.run_collection_cycle()
            
            # Store results in cache
            if collection_result.get("success") and collection_result.get("aggregated_sentiment"):
                await self.cache.store_aggregated_sentiment(collection_result["aggregated_sentiment"])
                await self.cache.store_platform_sentiments(collection_result.get("platform_sentiments", {}))
                await self.cache.store_collection_result(collection_result)
                
                logger.info("✅ Sentiment collection completed and cached successfully")
            else:
                logger.warning("⚠️ Sentiment collection completed but with limited success")
            
            # Update tracking
            self.last_collection_result = collection_result
            self.collection_count += 1
            
            # Log completion
            duration = (datetime.utcnow() - job_start).total_seconds()
            overall_sentiment = collection_result.get("aggregated_sentiment", {}).get("overall_sentiment", "UNKNOWN")
            sentiment_score = collection_result.get("aggregated_sentiment", {}).get("sentiment_score", 0)
            
            logger.info(f"🎉 Sentiment collection job completed in {duration:.1f}s: "
                       f"{overall_sentiment} ({sentiment_score}/100)")
            
        except Exception as e:
            logger.error(f"💥 Sentiment collection job failed: {e}")
            
            # Store error result
            error_result = {
                "timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error": str(e),
                "job_duration": (datetime.utcnow() - job_start).total_seconds()
            }
            self.last_collection_result = error_result
    
    async def _daily_maintenance_job(self):
        """Daily maintenance and cleanup job"""
        logger.info("🧹 Running daily maintenance...")
        
        try:
            # Clean old cache files
            cache_stats = self.cache.get_cache_stats()
            
            # Remove cache entries older than 7 days
            for cache_name, cache_info in cache_stats.get("cache_files", {}).items():
                if cache_info.get("exists") and cache_info.get("age_seconds", 0) > 604800:  # 7 days
                    await self.cache.clear_cache(cache_name)
                    logger.info(f"🗑️ Cleared old cache: {cache_name}")
            
            # Log API usage summary
            api_usage = self.collector._collect_api_usage_stats()
            logger.info("📈 Daily API usage summary:")
            for platform, stats in api_usage.get("platforms", {}).items():
                usage_pct = stats.get("usage_percentage", 0)
                logger.info(f"  {platform}: {usage_pct:.1f}% of daily limit used")
            
            logger.info("✅ Daily maintenance completed")
            
        except Exception as e:
            logger.error(f"Error in daily maintenance: {e}")
    
    async def _hourly_cache_refresh_job(self):
        """Hourly cache refresh job for dashboard updates"""
        try:
            # Check if we need to refresh dashboard cache
            cached_sentiment = await self.cache.get_latest_aggregated_sentiment()
            
            if cached_sentiment:
                cache_timestamp = cached_sentiment.get("timestamp")
                if cache_timestamp:
                    cache_time = datetime.fromisoformat(cache_timestamp)
                    age_minutes = (datetime.utcnow() - cache_time).total_seconds() / 60
                    
                    # Only log if cache is getting old
                    if age_minutes > 90:  # 1.5 hours
                        logger.debug(f"📊 Dashboard cache is {age_minutes:.0f} minutes old")
            
        except Exception as e:
            logger.debug(f"Cache refresh check error: {e}")
    
    async def _api_usage_monitoring_job(self):
        """Monitor API usage across all platforms"""
        try:
            api_usage = self.collector._collect_api_usage_stats()
            
            # Check for platforms approaching limits
            warnings = []
            for platform, stats in api_usage.get("platforms", {}).items():
                usage_pct = stats.get("usage_percentage", 0)
                
                if usage_pct > 90:
                    warnings.append(f"{platform}: {usage_pct:.1f}%")
                elif usage_pct > 75:
                    logger.debug(f"📊 {platform} API usage: {usage_pct:.1f}%")
            
            if warnings:
                logger.warning(f"⚠️ High API usage detected: {', '.join(warnings)}")
            
        except Exception as e:
            logger.debug(f"API usage monitoring error: {e}")
    
    async def run_manual_collection(self) -> Dict[str, Any]:
        """Manually trigger a sentiment collection cycle"""
        logger.info("🎯 Manual sentiment collection triggered...")
        
        try:
            collection_result = await self.collector.run_collection_cycle()
            
            # Store results in cache
            if collection_result.get("success") and collection_result.get("aggregated_sentiment"):
                await self.cache.store_aggregated_sentiment(collection_result["aggregated_sentiment"])
                await self.cache.store_platform_sentiments(collection_result.get("platform_sentiments", {}))
                await self.cache.store_collection_result(collection_result)
            
            self.last_collection_result = collection_result
            return collection_result
            
        except Exception as e:
            logger.error(f"Manual collection failed: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "success": False,
                "error": str(e)
            }
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": next_run.isoformat() if next_run else None,
                    "trigger": str(job.trigger)
                })
            
            return {
                "is_running": self.is_running,
                "collection_count": self.collection_count,
                "last_collection": self.last_collection_result.get("timestamp") if self.last_collection_result else None,
                "last_collection_success": self.last_collection_result.get("success") if self.last_collection_result else None,
                "scheduled_jobs": jobs,
                "collector_status": self.collector.get_collection_status()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "is_running": self.is_running
            }
    
    async def test_collection_setup(self) -> Dict[str, Any]:
        """Test the collection setup and API configurations"""
        logger.info("🧪 Testing sentiment collection setup...")
        
        try:
            # Test all collectors
            test_results = await self.collector.test_all_collectors()
            
            # Test cache functionality
            test_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "test": True,
                "overall_sentiment": "NEUTRAL",
                "sentiment_score": 50
            }
            
            cache_test = await self.cache.store_aggregated_sentiment(test_data)
            retrieved_data = await self.cache.get_latest_aggregated_sentiment()
            cache_working = cache_test and retrieved_data is not None
            
            test_results["cache_test"] = {
                "store_success": cache_test,
                "retrieve_success": retrieved_data is not None,
                "overall_working": cache_working
            }
            
            # Clean up test data
            if cache_working:
                await self.cache.clear_cache("aggregated_sentiment")
            
            logger.info(f"🧪 Setup test completed: {test_results['overall_status']}")
            return test_results
            
        except Exception as e:
            logger.error(f"Setup test failed: {e}")
            return {
                "overall_status": "error",
                "error": str(e)
            }