#!/usr/bin/env python3
"""
YouTube Data Collector - Optimized for Free API Limits
Rate Limit: 10,000 units/day = 2,500 units per 6-hour cycle
Comment analysis: ~240,000 comments per cycle
"""
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class YouTubeCollector:
    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY")
        self.youtube = None
        
        # Rate limiting configuration
        self.units_per_day = 10000
        self.units_per_cycle = 2500  # 6-hour cycle budget
        self.units_used = 0
        self.cycle_start = time.time()
        
        # Target crypto YouTube channels (major educators/influencers)
        self.target_channels = {
            "UCqK_GSMbpiV8spgD3ZGloSw": "Coin Bureau",
            "UCrYmtJBtLdtm2ov84ulV-yg": "Altcoin Daily", 
            "UCRvqjQPSeaWn-uEx-w0XOIg": "Benjamin Cowen",
            "UC4f8-6wuWXhqGaAHe3eVPKQ": "InvestAnswers",
            "UC0zGwzu0zzCImC1hjP0TKxg": "Crypto Zombie",
            "UCjemQfjaXAzA-95RKoy9n_g": "BitBoy Crypto",
            "UC-BhiXCUcTIaQ7rEd9b8uAQ": "The Modern Investor",
            "UCCatR7nWbYrkVXdxXb4cGXw": "DataDash",
            "UCrYmtJBtLdtm2ov84ulV-yg": "Ivan on Tech",
            "UC3RaY_-L0QvOvVbKzLkTGsg": "Crypto Banter"
        }
        
        # API cost mapping
        self.api_costs = {
            "search": 100,        # Search for videos
            "videos": 1,          # Get video details
            "comments": 1,        # Get comments (per 100 comments)
            "channels": 1         # Get channel info
        }
        
        self.initialize_youtube()
    
    def initialize_youtube(self):
        """Initialize YouTube API client"""
        try:
            if not self.api_key:
                logger.warning("YouTube API key not configured")
                return False
                
            from googleapiclient.discovery import build
            
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            
            logger.info("✅ YouTube Data API v3 client initialized successfully")
            return True
            
        except ImportError:
            logger.error("google-api-python-client not installed. Run: pip install google-api-python-client")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize YouTube client: {e}")
            return False
    
    def check_rate_limit(self, units_needed: int) -> bool:
        """Check if we have enough units remaining"""
        current_time = time.time()
        cycle_elapsed = current_time - self.cycle_start
        
        # Reset counter every 6 hours
        if cycle_elapsed > 21600:  # 6 hours
            self.units_used = 0
            self.cycle_start = current_time
            
        # Check if we have enough units for the operation
        if self.units_used + units_needed > self.units_per_cycle:
            logger.warning(f"YouTube API units exhausted: {self.units_used}/{self.units_per_cycle}")
            return False
            
        return True
    
    def use_units(self, units: int):
        """Record API units used"""
        self.units_used += units
        logger.debug(f"YouTube API units used: {units}, Total: {self.units_used}/{self.units_per_cycle}")
    
    async def collect_sentiment_data(self) -> Dict[str, Any]:
        """Collect sentiment data from YouTube within unit limits"""
        if not self.youtube or not self.check_rate_limit(100):
            return self._empty_result()
        
        collected_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "youtube",
            "videos": [],
            "comments": [],
            "channel_data": {},
            "api_units_used": 0,
            "data_quality": "high"
        }
        
        try:
            # Collect from target channels
            videos_per_channel = 2  # Latest 2 videos per channel
            comments_per_video = 100  # Top 100 comments per video
            
            # Process channels in order of importance
            channels_processed = 0
            max_channels = 10  # Limit channels per cycle
            
            for channel_id, channel_name in list(self.target_channels.items())[:max_channels]:
                if not self.check_rate_limit(200):  # Estimate units needed
                    break
                    
                channel_data = await self._collect_channel_data(
                    channel_id, channel_name, videos_per_channel, comments_per_video
                )
                
                if channel_data["videos"]:
                    collected_data["channel_data"][channel_name] = channel_data
                    collected_data["videos"].extend(channel_data["videos"])
                    collected_data["comments"].extend(channel_data["comments"])
                    channels_processed += 1
                
                # Small delay between channels
                await asyncio.sleep(0.5)
            
            collected_data["api_units_used"] = self.units_used
            collected_data["total_videos"] = len(collected_data["videos"])
            collected_data["total_comments"] = len(collected_data["comments"])
            collected_data["channels_processed"] = channels_processed
            
            logger.info(f"YouTube collection complete: {collected_data['total_videos']} videos, "
                       f"{collected_data['total_comments']} comments from "
                       f"{channels_processed} channels, {self.units_used} units used")
            
            return collected_data
            
        except Exception as e:
            logger.error(f"Error collecting YouTube data: {e}")
            return self._empty_result()
    
    async def _collect_channel_data(self, channel_id: str, channel_name: str,
                                   video_limit: int, comment_limit: int) -> Dict[str, Any]:
        """Collect data from a specific YouTube channel"""
        channel_data = {
            "name": channel_name,
            "id": channel_id,
            "videos": [],
            "comments": [],
            "subscriber_count": 0,
            "video_count": 0
        }
        
        try:
            # Get channel statistics
            if self.check_rate_limit(self.api_costs["channels"]):
                channel_response = self.youtube.channels().list(
                    part="statistics,snippet",
                    id=channel_id
                ).execute()
                
                self.use_units(self.api_costs["channels"])
                
                if channel_response["items"]:
                    stats = channel_response["items"][0]["statistics"]
                    channel_data["subscriber_count"] = int(stats.get("subscriberCount", 0))
                    channel_data["video_count"] = int(stats.get("videoCount", 0))
            
            # Get recent videos from channel
            if self.check_rate_limit(self.api_costs["search"]):
                search_response = self.youtube.search().list(
                    part="snippet",
                    channelId=channel_id,
                    maxResults=video_limit,
                    order="date",
                    type="video",
                    q="crypto OR bitcoin OR ethereum OR altcoin OR trading"  # Crypto-relevant only
                ).execute()
                
                self.use_units(self.api_costs["search"])
                
                # Process each video
                for item in search_response.get("items", []):
                    if not self.check_rate_limit(100):  # Estimate for video + comments
                        break
                        
                    video_data = await self._process_video(item, comment_limit)
                    if video_data:
                        channel_data["videos"].append(video_data)
                        channel_data["comments"].extend(video_data.get("comments", []))
            
            return channel_data
            
        except Exception as e:
            logger.error(f"Error collecting from channel {channel_name}: {e}")
            return channel_data
    
    async def _process_video(self, video_item: Dict, comment_limit: int) -> Optional[Dict[str, Any]]:
        """Process a single video and collect its comments"""
        try:
            video_id = video_item["id"]["videoId"]
            snippet = video_item["snippet"]
            
            # Get video statistics
            video_data = {
                "id": video_id,
                "title": snippet["title"],
                "description": snippet["description"][:500],  # Limit description length
                "published_at": snippet["publishedAt"],
                "channel_title": snippet["channelTitle"],
                "view_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "comments": [],
                "sentiment_text": f"{snippet['title']} {snippet['description'][:200]}"
            }
            
            # Get video statistics
            if self.check_rate_limit(self.api_costs["videos"]):
                video_response = self.youtube.videos().list(
                    part="statistics",
                    id=video_id
                ).execute()
                
                self.use_units(self.api_costs["videos"])
                
                if video_response["items"]:
                    stats = video_response["items"][0]["statistics"]
                    video_data["view_count"] = int(stats.get("viewCount", 0))
                    video_data["like_count"] = int(stats.get("likeCount", 0))
                    video_data["comment_count"] = int(stats.get("commentCount", 0))
            
            # Get top comments
            await self._collect_video_comments(video_id, video_data, comment_limit)
            
            return video_data
            
        except Exception as e:
            logger.error(f"Error processing video: {e}")
            return None
    
    async def _collect_video_comments(self, video_id: str, video_data: Dict, limit: int):
        """Collect top comments from a video"""
        try:
            if not self.check_rate_limit(self.api_costs["comments"]):
                return
                
            # Get comment threads
            comments_response = self.youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(limit, 100),  # API max is 100
                order="relevance"  # Get most relevant comments
            ).execute()
            
            self.use_units(self.api_costs["comments"])
            
            for item in comments_response.get("items", []):
                comment_snippet = item["snippet"]["topLevelComment"]["snippet"]
                
                # Filter for crypto-relevant comments
                comment_text = comment_snippet["textDisplay"]
                if self._is_crypto_relevant_comment(comment_text):
                    comment_data = {
                        "id": item["id"],
                        "video_id": video_id,
                        "text": comment_text[:300],  # Limit comment length
                        "author": comment_snippet["authorDisplayName"],
                        "like_count": comment_snippet.get("likeCount", 0),
                        "published_at": comment_snippet["publishedAt"],
                        "reply_count": item["snippet"].get("totalReplyCount", 0),
                        "sentiment_text": comment_text[:300]
                    }
                    
                    video_data["comments"].append(comment_data)
                    
        except Exception as e:
            logger.error(f"Error collecting comments for video {video_id}: {e}")
    
    def _is_crypto_relevant_comment(self, text: str) -> bool:
        """Check if comment is crypto-relevant"""
        if len(text) < 20:  # Skip very short comments
            return False
            
        crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'blockchain', 'defi', 'nft', 'altcoin', 'satoshi', 'hodl',
            'trading', 'pump', 'dump', 'moon', 'bear', 'bull', 'market',
            'price', 'chart', 'analysis', 'prediction', 'investment'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in crypto_keywords)
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "youtube",
            "videos": [],
            "comments": [],
            "channel_data": {},
            "api_units_used": 0,
            "total_videos": 0,
            "total_comments": 0,
            "channels_processed": 0,
            "data_quality": "unavailable",
            "error": "API unavailable or rate limited"
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics"""
        cycle_elapsed = time.time() - self.cycle_start
        cycle_remaining = max(0, 21600 - cycle_elapsed)  # 6 hours
        units_remaining = max(0, self.units_per_cycle - self.units_used)
        
        return {
            "units_used": self.units_used,
            "cycle_budget": self.units_per_cycle,
            "units_remaining": units_remaining,
            "cycle_time_remaining": cycle_remaining,
            "usage_percentage": (self.units_used / self.units_per_cycle) * 100,
            "within_limits": self.units_used < self.units_per_cycle,
            "daily_limit": self.units_per_day,
            "comments_analyzed_approx": self.units_used * 100  # Rough estimate
        }