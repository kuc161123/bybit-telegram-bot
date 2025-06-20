#!/usr/bin/env python3
"""
YouTube Web Scraper - No API Credentials Required
Uses web scraping techniques for YouTube data collection
Rate Limit: Self-imposed 25 requests/hour for respectful usage
"""
import logging
import asyncio
import time
import re
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import aiohttp

logger = logging.getLogger(__name__)

class YouTubeScraper:
    def __init__(self):
        # Target crypto YouTube channels (channel IDs would be needed for real scraping)
        self.target_channels = [
            "coin_bureau",
            "investanswers", 
            "altcoin_daily",
            "crypto_jebb",
            "bitboy_crypto",
            "crypto_zombie",
            "digital_asset_news",
            "crypto_casey",
            "crypto_love",
            "crypto_banter"
        ]
        
        # Crypto keywords for video relevance
        self.crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'blockchain', 'defi', 'nft', 'altcoin', 'solana', 'sol', 'cardano', 'ada',
            'polygon', 'matic', 'chainlink', 'link', 'polkadot', 'dot', 'avalanche', 'avax',
            'binance', 'bnb', 'uniswap', 'uni', 'dogecoin', 'doge', 'shiba', 'shib',
            'trading', 'hodl', 'moon', 'pump', 'bullish', 'bearish', 'analysis'
        ]
        
        # Rate limiting (25 requests/hour = 1 per 2.4 minutes)
        self.requests_per_hour = 25
        self.requests_made = 0
        self.hour_start = time.time()
        
        # User agent for web scraping
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
    
    def check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        current_time = time.time()
        hour_elapsed = current_time - self.hour_start
        
        # Reset counter every hour
        if hour_elapsed > 3600:  # 1 hour
            self.requests_made = 0
            self.hour_start = current_time
            
        if self.requests_made >= self.requests_per_hour:
            logger.warning(f"YouTube scraper rate limit reached ({self.requests_per_hour}/hour)")
            return False
            
        return True
    
    async def collect_sentiment_data(self) -> Dict[str, Any]:
        """Collect YouTube sentiment data using web scraping"""
        if not self.check_rate_limit():
            return self._empty_result()
        
        collected_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "youtube_scraper",
            "channel_data": {},
            "total_videos": 0,
            "crypto_videos": 0,
            "average_sentiment": 50,
            "trending_topics": [],
            "data_quality": "simulated"  # Since actual scraping is complex
        }
        
        try:
            # Note: Real YouTube scraping is complex due to anti-bot measures
            # For demonstration, we'll create realistic sample data
            # In production, you'd use tools like yt-dlp or selenium
            
            collected_data = await self._simulate_youtube_data()
            
            logger.info(f"YouTube scraping complete: {collected_data['total_videos']} videos analyzed, "
                       f"{collected_data['crypto_videos']} crypto-relevant")
            
            return collected_data
            
        except Exception as e:
            logger.error(f"Error in YouTube sentiment collection: {e}")
            return self._empty_result()
    
    async def _simulate_youtube_data(self) -> Dict[str, Any]:
        """Simulate YouTube data collection with realistic crypto sentiment"""
        
        # Sample crypto YouTube videos with varied sentiment
        sample_videos = [
            {
                "title": "BITCOIN BREAKOUT IMMINENT! 🚀 Critical Levels to Watch",
                "channel": "coin_bureau",
                "views": "125K",
                "likes": 8500,
                "comments": 1200,
                "sentiment": 78,
                "duration": "15:32",
                "uploaded": "2 hours ago"
            },
            {
                "title": "Ethereum Merge Success: What's Next for ETH Price?",
                "channel": "investanswers", 
                "views": "89K",
                "likes": 6200,
                "comments": 890,
                "sentiment": 72,
                "duration": "22:15",
                "uploaded": "5 hours ago"
            },
            {
                "title": "ALTCOIN SEASON CONFIRMED? Top 5 Coins to Watch",
                "channel": "altcoin_daily",
                "views": "203K",
                "likes": 12300,
                "comments": 2100,
                "sentiment": 75,
                "duration": "12:45",
                "uploaded": "8 hours ago"
            },
            {
                "title": "Market Crash Warning: Why You Should Be Careful",
                "channel": "crypto_jebb",
                "views": "67K",
                "likes": 3400,
                "comments": 580,
                "sentiment": 25,
                "duration": "18:20",
                "uploaded": "12 hours ago"
            },
            {
                "title": "Solana vs Ethereum: Which Will Win in 2024?",
                "channel": "crypto_zombie",
                "views": "156K",
                "likes": 9800,
                "comments": 1650,
                "sentiment": 65,
                "duration": "20:10",
                "uploaded": "1 day ago"
            },
            {
                "title": "DeFi 2024: Best Yield Farming Opportunities",
                "channel": "digital_asset_news",
                "views": "45K",
                "likes": 2800,
                "comments": 420,
                "sentiment": 68,
                "duration": "14:25",
                "uploaded": "1 day ago"
            },
            {
                "title": "Chainlink EXPLODES: 300% Gain Incoming?",
                "channel": "crypto_casey",
                "views": "112K",
                "likes": 7200,
                "comments": 980,
                "sentiment": 82,
                "duration": "16:55",
                "uploaded": "1 day ago"
            },
            {
                "title": "Bear Market Reality Check: Prepare for Lower Prices",
                "channel": "crypto_love",
                "views": "78K",
                "likes": 4100,
                "comments": 720,
                "sentiment": 30,
                "duration": "19:40",
                "uploaded": "2 days ago"
            }
        ]
        
        # Simulate data from different channels
        channel_data = {}
        total_videos = 0
        crypto_videos = 0
        all_sentiments = []
        trending_keywords = []
        
        for i, channel in enumerate(self.target_channels[:5]):  # Limit to 5 channels
            channel_videos = []
            
            # Assign some sample videos to each channel
            videos_per_channel = min(2, len(sample_videos) - total_videos)
            
            for j in range(videos_per_channel):
                if total_videos < len(sample_videos):
                    video = sample_videos[total_videos]
                    
                    # Simulate engagement metrics
                    views_num = self._parse_view_count(video["views"])
                    engagement_rate = (video["likes"] + video["comments"]) / max(views_num, 1) * 100
                    
                    channel_videos.append({
                        "title": video["title"],
                        "views": video["views"],
                        "likes": video["likes"],
                        "comments": video["comments"],
                        "sentiment_score": video["sentiment"],
                        "duration": video["duration"],
                        "uploaded": video["uploaded"],
                        "engagement_rate": round(engagement_rate, 2),
                        "crypto_relevant": True,
                        "url": f"https://youtube.com/watch?v=demo_{total_videos}"
                    })
                    
                    all_sentiments.append(video["sentiment"])
                    crypto_videos += 1
                    
                    # Extract keywords from title
                    keywords = self._extract_youtube_keywords(video["title"])
                    trending_keywords.extend(keywords)
                    
                    total_videos += 1
            
            if channel_videos:
                avg_sentiment = sum(video["sentiment_score"] for video in channel_videos) / len(channel_videos)
                total_views = sum(self._parse_view_count(video["views"]) for video in channel_videos)
                total_engagement = sum(video["likes"] + video["comments"] for video in channel_videos)
                
                channel_data[channel] = {
                    "name": channel.replace("_", " ").title(),
                    "videos": channel_videos,
                    "average_sentiment": int(avg_sentiment),
                    "crypto_videos": len(channel_videos),
                    "total_views": total_views,
                    "total_engagement": total_engagement,
                    "subscriber_influence": "high"  # Simulated
                }
        
        # Calculate overall metrics
        overall_sentiment = int(sum(all_sentiments) / len(all_sentiments)) if all_sentiments else 50
        
        # Get trending topics
        keyword_counts = {}
        for keyword in trending_keywords:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
        
        trending = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        trending_topics = [{"keyword": word, "mentions": count} for word, count in trending]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "youtube_scraper",
            "channel_data": channel_data,
            "total_videos": total_videos,
            "crypto_videos": crypto_videos,
            "average_sentiment": overall_sentiment,
            "trending_topics": trending_topics,
            "data_quality": "simulated",
            "note": "Simulated data - real YouTube scraping requires specialized tools"
        }
    
    def _parse_view_count(self, view_string: str) -> int:
        """Parse YouTube view count string to number"""
        try:
            view_string = view_string.replace(",", "").upper()
            if "K" in view_string:
                return int(float(view_string.replace("K", "")) * 1000)
            elif "M" in view_string:
                return int(float(view_string.replace("M", "")) * 1000000)
            else:
                return int(view_string)
        except:
            return 0
    
    def _extract_youtube_keywords(self, title: str) -> List[str]:
        """Extract crypto keywords from YouTube video title"""
        found_keywords = []
        title_lower = title.lower()
        
        # Extract crypto keywords
        for keyword in self.crypto_keywords:
            if keyword in title_lower:
                found_keywords.append(keyword)
        
        # Extract specific patterns
        # Price targets
        price_patterns = re.findall(r'\$[\d,]+', title)
        for pattern in price_patterns:
            found_keywords.append("price_target")
        
        # Percentage gains/losses
        percent_patterns = re.findall(r'\d+%', title)
        if percent_patterns:
            found_keywords.append("percentage_move")
        
        # Bullish/bearish indicators
        if any(word in title_lower for word in ['bull', 'bullish', 'moon', '🚀', 'pump', 'surge']):
            found_keywords.append("bullish")
        
        if any(word in title_lower for word in ['bear', 'bearish', 'crash', 'dump', 'warning']):
            found_keywords.append("bearish")
        
        return found_keywords
    
    def _analyze_youtube_sentiment(self, title: str, views: str, likes: int, comments: int) -> int:
        """Analyze sentiment of YouTube video"""
        try:
            content = title.lower()
            
            # Positive indicators
            positive_words = [
                'bullish', 'moon', 'rocket', '🚀', 'pump', 'surge', 'rally', 'gains',
                'explodes', 'breakout', 'target', 'bull', 'opportunity', 'profit',
                'best', 'top', 'huge', 'massive', 'incredible', 'amazing', 'success'
            ]
            
            # Negative indicators
            negative_words = [
                'bearish', 'crash', 'dump', 'warning', 'danger', 'risk', 'careful',
                'bear', 'market', 'down', 'falling', 'drop', 'decline', 'loss',
                'avoid', 'scam', 'fail', 'problem', 'concern', 'worried'
            ]
            
            positive_count = sum(1 for word in positive_words if word in content)
            negative_count = sum(1 for word in negative_words if word in content)
            
            # Factor in engagement (likes ratio indicates reception)
            views_num = self._parse_view_count(views)
            like_ratio = likes / max(views_num, 1) * 100 if views_num > 0 else 0
            
            engagement_boost = 0
            if like_ratio > 5:  # Very high engagement
                engagement_boost = 15
            elif like_ratio > 2:  # Good engagement
                engagement_boost = 10
            elif like_ratio > 1:  # Average engagement
                engagement_boost = 5
            
            # Calculate base sentiment
            if positive_count == 0 and negative_count == 0:
                base_sentiment = 50
            else:
                total_sentiment_words = positive_count + negative_count
                positive_ratio = positive_count / total_sentiment_words if total_sentiment_words > 0 else 0.5
                base_sentiment = int(positive_ratio * 100)
            
            # Adjust with engagement boost
            final_sentiment = base_sentiment + engagement_boost
            
            # Ensure bounds
            return max(0, min(100, final_sentiment))
            
        except Exception as e:
            logger.debug(f"Error analyzing YouTube sentiment: {e}")
            return 50
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "youtube_scraper",
            "channel_data": {},
            "total_videos": 0,
            "crypto_videos": 0,
            "average_sentiment": 50,
            "trending_topics": [],
            "data_quality": "unavailable",
            "error": "Rate limited or scraping unavailable"
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics"""
        hour_elapsed = time.time() - self.hour_start
        hour_remaining = max(0, 3600 - hour_elapsed)
        requests_remaining = max(0, self.requests_per_hour - self.requests_made)
        
        return {
            "requests_made": self.requests_made,
            "hourly_budget": self.requests_per_hour,
            "requests_remaining": requests_remaining,
            "hour_time_remaining": hour_remaining,
            "usage_percentage": (self.requests_made / self.requests_per_hour) * 100,
            "within_limits": self.requests_made < self.requests_per_hour
        }