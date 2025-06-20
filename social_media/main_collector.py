#!/usr/bin/env python3
"""
Main Social Media Collector
Orchestrates 6-hour sentiment collection cycles across all platforms
"""
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from .collectors.reddit_collector import RedditCollector
from .collectors.twitter_collector import TwitterCollector
from .collectors.youtube_collector import YouTubeCollector
from .collectors.discord_collector import DiscordCollector
from .collectors.news_collector import NewsCollector

# Import new scrapers for credential-free collection
from .collectors.reddit_scraper import RedditScraper
from .collectors.twitter_scraper import TwitterScraper
from .collectors.youtube_scraper import YouTubeScraper
from .processors.sentiment_analyzer import SentimentAnalyzer
from .processors.data_aggregator import DataAggregator

logger = logging.getLogger(__name__)

class SocialMediaCollector:
    def __init__(self, openai_client=None):
        """Initialize the main social media collector"""
        self.openai_client = openai_client
        
        # Initialize collectors (API-based)
        self.reddit_collector = RedditCollector()
        self.twitter_collector = TwitterCollector()
        self.youtube_collector = YouTubeCollector()
        self.discord_collector = DiscordCollector()
        self.news_collector = NewsCollector()
        
        # Initialize scrapers (credential-free fallbacks)
        self.reddit_scraper = RedditScraper()
        self.twitter_scraper = TwitterScraper()
        self.youtube_scraper = YouTubeScraper()
        
        # Initialize processors
        self.sentiment_analyzer = SentimentAnalyzer(openai_client)
        self.data_aggregator = DataAggregator()
        
        # Collection tracking
        self.last_collection_time = None
        self.collection_cycle = 0
        self.total_api_calls = 0
        
        # 6-hour cycle configuration
        self.cycle_interval = 21600  # 6 hours in seconds
        self.cycle_names = {
            0: "night",     # 00:00 UTC - Asia/Pacific sentiment
            6: "morning",   # 06:00 UTC - Europe sentiment
            12: "afternoon", # 12:00 UTC - Americas sentiment
            18: "evening"   # 18:00 UTC - Global evening sentiment
        }
    
    async def run_collection_cycle(self) -> Dict[str, Any]:
        """Run a complete 6-hour sentiment collection cycle"""
        cycle_start = time.time()
        current_hour = datetime.utcnow().hour
        cycle_name = self.cycle_names.get(current_hour, "custom")
        
        logger.info(f"🚀 Starting {cycle_name} sentiment collection cycle (Hour: {current_hour})")
        
        collection_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "cycle_name": cycle_name,
            "cycle_hour": current_hour,
            "platform_data": {},
            "platform_sentiments": {},
            "aggregated_sentiment": {},
            "api_usage": {},
            "collection_time_seconds": 0,
            "success": False
        }
        
        try:
            # Collect data from all platforms concurrently
            platform_tasks = {
                "reddit": self._collect_reddit_data(),
                "twitter": self._collect_twitter_data(),
                "youtube": self._collect_youtube_data(),
                "discord": self._collect_discord_data(),
                "news_market": self._collect_news_data()
            }
            
            # Execute all collections concurrently with timeouts
            platform_results = {}
            for platform, task in platform_tasks.items():
                try:
                    result = await asyncio.wait_for(task, timeout=300)  # 5 minute timeout per platform
                    platform_results[platform] = result
                    logger.info(f"✅ {platform.title()} collection completed")
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ {platform.title()} collection timed out")
                    platform_results[platform] = self._empty_platform_result(platform)
                except Exception as e:
                    logger.error(f"❌ {platform.title()} collection failed: {e}")
                    platform_results[platform] = self._empty_platform_result(platform)
            
            collection_result["platform_data"] = platform_results
            
            # Analyze sentiment for each platform
            logger.info("🧠 Analyzing sentiment for all platforms...")
            sentiment_tasks = {}
            for platform, data in platform_results.items():
                if data.get("total_posts", 0) > 0 or data.get("total_comments", 0) > 0 or data.get("total_tweets", 0) > 0:
                    sentiment_tasks[platform] = self.sentiment_analyzer.analyze_platform_sentiment(data)
            
            platform_sentiments = {}
            for platform, task in sentiment_tasks.items():
                try:
                    sentiment_result = await asyncio.wait_for(task, timeout=120)  # 2 minute timeout
                    platform_sentiments[platform] = sentiment_result
                    logger.info(f"✅ {platform.title()} sentiment analysis completed")
                except Exception as e:
                    logger.error(f"❌ {platform.title()} sentiment analysis failed: {e}")
            
            collection_result["platform_sentiments"] = platform_sentiments
            
            # Aggregate all platform sentiments
            if platform_sentiments:
                logger.info("📊 Aggregating multi-platform sentiment data...")
                try:
                    aggregated_sentiment = await self.data_aggregator.aggregate_platform_data(platform_sentiments)
                    collection_result["aggregated_sentiment"] = aggregated_sentiment
                    logger.info(f"✅ Sentiment aggregation completed: {aggregated_sentiment.get('overall_sentiment', 'UNKNOWN')} "
                              f"({aggregated_sentiment.get('sentiment_score', 0)}/100)")
                except Exception as e:
                    logger.error(f"❌ Sentiment aggregation failed: {e}")
            
            # Collect API usage statistics
            collection_result["api_usage"] = self._collect_api_usage_stats()
            
            # Calculate collection time
            collection_result["collection_time_seconds"] = time.time() - cycle_start
            collection_result["success"] = True
            
            # Update tracking
            self.last_collection_time = datetime.utcnow()
            self.collection_cycle += 1
            
            logger.info(f"🎉 {cycle_name.title()} sentiment collection cycle completed successfully "
                       f"in {collection_result['collection_time_seconds']:.1f} seconds")
            
            return collection_result
            
        except Exception as e:
            logger.error(f"💥 Sentiment collection cycle failed: {e}")
            collection_result["error"] = str(e)
            collection_result["collection_time_seconds"] = time.time() - cycle_start
            return collection_result
    
    async def _collect_reddit_data(self) -> Dict[str, Any]:
        """Collect Reddit data with API fallback to scraper"""
        try:
            # Try API first
            result = await self.reddit_collector.collect_sentiment_data()
            if result.get("data_quality") != "unavailable":
                return result
            else:
                logger.info("Reddit API unavailable, using scraper fallback")
                return await self.reddit_scraper.collect_sentiment_data()
        except Exception as e:
            logger.warning(f"Reddit API failed ({e}), trying scraper fallback")
            try:
                return await self.reddit_scraper.collect_sentiment_data()
            except Exception as scraper_e:
                logger.error(f"Reddit scraper also failed: {scraper_e}")
                return self._empty_platform_result("reddit")
    
    async def _collect_twitter_data(self) -> Dict[str, Any]:
        """Collect Twitter data with API fallback to scraper"""
        try:
            # Try API first
            result = await self.twitter_collector.collect_sentiment_data()
            if result.get("data_quality") != "unavailable":
                return result
            else:
                logger.info("Twitter API unavailable, using scraper fallback")
                return await self.twitter_scraper.collect_sentiment_data()
        except Exception as e:
            logger.warning(f"Twitter API failed ({e}), trying scraper fallback")
            try:
                return await self.twitter_scraper.collect_sentiment_data()
            except Exception as scraper_e:
                logger.error(f"Twitter scraper also failed: {scraper_e}")
                return self._empty_platform_result("twitter")
    
    async def _collect_youtube_data(self) -> Dict[str, Any]:
        """Collect YouTube data with API fallback to scraper"""
        try:
            # Try API first
            result = await self.youtube_collector.collect_sentiment_data()
            if result.get("data_quality") != "unavailable":
                return result
            else:
                logger.info("YouTube API unavailable, using scraper fallback")
                return await self.youtube_scraper.collect_sentiment_data()
        except Exception as e:
            logger.warning(f"YouTube API failed ({e}), trying scraper fallback")
            try:
                return await self.youtube_scraper.collect_sentiment_data()
            except Exception as scraper_e:
                logger.error(f"YouTube scraper also failed: {scraper_e}")
                return self._empty_platform_result("youtube")
    
    async def _collect_discord_data(self) -> Dict[str, Any]:
        """Collect Discord data with error handling"""
        try:
            return await self.discord_collector.collect_sentiment_data()
        except Exception as e:
            logger.error(f"Discord collection error: {e}")
            return self._empty_platform_result("discord")
    
    async def _collect_news_data(self) -> Dict[str, Any]:
        """Collect news/market data with error handling"""
        try:
            return await self.news_collector.collect_sentiment_data()
        except Exception as e:
            logger.error(f"News collection error: {e}")
            return self._empty_platform_result("news_market")
    
    def _empty_platform_result(self, platform: str) -> Dict[str, Any]:
        """Return empty result for failed platform collection"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": platform,
            "posts": [],
            "comments": [],
            "tweets": [],
            "messages": [],
            "videos": [],
            "api_calls_used": 0,
            "total_posts": 0,
            "total_comments": 0,
            "total_tweets": 0,
            "total_messages": 0,
            "total_videos": 0,
            "data_quality": "unavailable",
            "error": "Collection failed or unavailable"
        }
    
    def _collect_api_usage_stats(self) -> Dict[str, Any]:
        """Collect API usage statistics from all collectors and scrapers"""
        try:
            usage_stats = {
                "total_cycle_calls": 0,
                "platforms": {},
                "scrapers": {}
            }
            
            # API-based collectors
            # Reddit usage
            reddit_stats = self.reddit_collector.get_usage_stats()
            usage_stats["platforms"]["reddit"] = reddit_stats
            usage_stats["total_cycle_calls"] += reddit_stats.get("requests_made", 0)
            
            # Twitter usage
            twitter_stats = self.twitter_collector.get_usage_stats()
            usage_stats["platforms"]["twitter"] = twitter_stats
            usage_stats["total_cycle_calls"] += twitter_stats.get("posts_collected", 0)
            
            # YouTube usage
            youtube_stats = self.youtube_collector.get_usage_stats()
            usage_stats["platforms"]["youtube"] = youtube_stats
            usage_stats["total_cycle_calls"] += youtube_stats.get("units_used", 0)
            
            # Discord usage
            discord_stats = self.discord_collector.get_usage_stats()
            usage_stats["platforms"]["discord"] = discord_stats
            usage_stats["total_cycle_calls"] += discord_stats.get("requests_made", 0)
            
            # News usage
            news_stats = self.news_collector.get_usage_stats()
            usage_stats["platforms"]["news_market"] = news_stats
            usage_stats["total_cycle_calls"] += news_stats.get("calls_made", 0)
            
            # Scraper usage (credential-free)
            reddit_scraper_stats = self.reddit_scraper.get_usage_stats()
            usage_stats["scrapers"]["reddit"] = reddit_scraper_stats
            
            twitter_scraper_stats = self.twitter_scraper.get_usage_stats()
            usage_stats["scrapers"]["twitter"] = twitter_scraper_stats
            
            youtube_scraper_stats = self.youtube_scraper.get_usage_stats()
            usage_stats["scrapers"]["youtube"] = youtube_scraper_stats
            
            # Check if within limits
            usage_stats["within_all_limits"] = all(
                platform_stats.get("within_limits", True) 
                for platform_stats in usage_stats["platforms"].values()
            )
            
            usage_stats["within_scraper_limits"] = all(
                scraper_stats.get("within_limits", True) 
                for scraper_stats in usage_stats["scrapers"].values()
            )
            
            # Add summary
            usage_stats["collection_method"] = "hybrid_api_scraper"
            usage_stats["credential_free_available"] = True
            
            return usage_stats
            
        except Exception as e:
            logger.error(f"Error collecting API usage stats: {e}")
            return {"error": str(e)}
    
    def get_collection_status(self) -> Dict[str, Any]:
        """Get current collection status"""
        now = datetime.utcnow()
        
        # Calculate next collection time
        current_hour = now.hour
        next_cycle_hours = [0, 6, 12, 18]
        next_hour = None
        
        for cycle_hour in next_cycle_hours:
            if cycle_hour > current_hour:
                next_hour = cycle_hour
                break
        
        if next_hour is None:
            next_hour = 0  # Next day
            next_collection = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            next_collection = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        
        time_until_next = (next_collection - now).total_seconds()
        
        status = {
            "current_time": now.isoformat(),
            "last_collection": self.last_collection_time.isoformat() if self.last_collection_time else None,
            "next_collection": next_collection.isoformat(),
            "time_until_next_seconds": time_until_next,
            "time_until_next_formatted": self._format_time_remaining(time_until_next),
            "cycles_completed": self.collection_cycle,
            "current_cycle_name": self.cycle_names.get(current_hour, "custom"),
            "api_usage_status": self._collect_api_usage_stats()
        }
        
        return status
    
    def _format_time_remaining(self, seconds: float) -> str:
        """Format remaining time in human-readable format"""
        if seconds <= 0:
            return "Now"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    async def test_all_collectors(self) -> Dict[str, Any]:
        """Test all collectors and scrapers to verify configurations"""
        test_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "unknown",
            "collectors": {},
            "scrapers": {}
        }
        
        # Test API-based collectors
        collectors = {
            "reddit": self.reddit_collector,
            "twitter": self.twitter_collector,
            "youtube": self.youtube_collector,
            "discord": self.discord_collector,
            "news_market": self.news_collector
        }
        
        # Test scrapers (credential-free)
        scrapers = {
            "reddit": self.reddit_scraper,
            "twitter": self.twitter_scraper,
            "youtube": self.youtube_scraper
        }
        
        working_collectors = 0
        working_scrapers = 0
        total_collectors = len(collectors)
        total_scrapers = len(scrapers)
        
        # Test collectors
        for name, collector in collectors.items():
            try:
                rate_limit_ok = collector.check_rate_limit()
                usage_stats = collector.get_usage_stats()
                
                test_results["collectors"][name] = {
                    "status": "ready" if rate_limit_ok else "rate_limited",
                    "rate_limit_ok": rate_limit_ok,
                    "usage_stats": usage_stats,
                    "configured": True
                }
                
                if rate_limit_ok:
                    working_collectors += 1
                    
            except Exception as e:
                test_results["collectors"][name] = {
                    "status": "error",
                    "error": str(e),
                    "configured": False
                }
        
        # Test scrapers
        for name, scraper in scrapers.items():
            try:
                rate_limit_ok = scraper.check_rate_limit()
                usage_stats = scraper.get_usage_stats()
                
                test_results["scrapers"][name] = {
                    "status": "ready" if rate_limit_ok else "rate_limited",
                    "rate_limit_ok": rate_limit_ok,
                    "usage_stats": usage_stats,
                    "configured": True,
                    "credential_free": True
                }
                
                if rate_limit_ok:
                    working_scrapers += 1
                    
            except Exception as e:
                test_results["scrapers"][name] = {
                    "status": "error",
                    "error": str(e),
                    "configured": False,
                    "credential_free": True
                }
        
        # Determine overall status based on total working components
        total_working = working_collectors + working_scrapers
        total_components = total_collectors + total_scrapers
        
        if total_working == total_components:
            test_results["overall_status"] = "excellent"
        elif total_working >= 6:
            test_results["overall_status"] = "good"
        elif total_working >= 4:
            test_results["overall_status"] = "fair"
        else:
            test_results["overall_status"] = "limited"
        
        test_results["working_collectors"] = working_collectors
        test_results["total_collectors"] = total_collectors
        test_results["working_scrapers"] = working_scrapers
        test_results["total_scrapers"] = total_scrapers
        test_results["total_working"] = total_working
        test_results["total_components"] = total_components
        test_results["has_credential_free_fallback"] = working_scrapers > 0
        
        return test_results