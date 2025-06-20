#!/usr/bin/env python3
"""
Twitter/X Data Collector - Ultra-Conservative for Free API Limits
Rate Limit: 1,500 posts/month = ~50 posts/day = ~12 posts per 6-hour cycle
"""
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class TwitterCollector:
    def __init__(self):
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        self.api_key = os.getenv("TWITTER_API_KEY")
        self.api = None
        
        # Ultra-conservative rate limiting for free tier
        self.posts_per_month = 1500
        self.posts_per_day = 50
        self.posts_per_cycle = 12  # 6-hour cycle budget
        self.posts_collected = 0
        self.cycle_start = time.time()
        
        # High-impact crypto influencers (quality over quantity)
        self.target_accounts = [
            "elonmusk",        # Elon Musk
            "michael_saylor",  # Michael Saylor
            "coinbureau",      # Coin Bureau
            "altcoindaily",    # Altcoin Daily
            "PlanB_99",        # PlanB
            "APompliano",      # Anthony Pompliano
            "VitalikButerin",  # Vitalik Buterin
            "justinsuntron",   # Justin Sun
            "cz_binance",      # CZ Binance
            "BTC_Archive"      # Bitcoin Archive
        ]
        
        self.initialize_twitter()
    
    def initialize_twitter(self):
        """Initialize Twitter API client"""
        try:
            if not self.bearer_token:
                logger.warning("Twitter API credentials not configured")
                return False
                
            import tweepy
            
            # Initialize with Bearer Token (v2 API)
            self.api = tweepy.Client(bearer_token=self.bearer_token)
            
            logger.info("✅ Twitter API v2 client initialized successfully")
            return True
            
        except ImportError:
            logger.error("tweepy library not installed. Run: pip install tweepy")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Twitter client: {e}")
            return False
    
    def check_rate_limit(self) -> bool:
        """Check if we're within ultra-conservative rate limits"""
        current_time = time.time()
        cycle_elapsed = current_time - self.cycle_start
        
        # Reset counter every 6 hours
        if cycle_elapsed > 21600:  # 6 hours
            self.posts_collected = 0
            self.cycle_start = current_time
            
        # Check if we're within budget
        if self.posts_collected >= self.posts_per_cycle:
            logger.warning(f"Twitter API cycle budget ({self.posts_per_cycle}) reached")
            return False
            
        return True
    
    async def collect_sentiment_data(self) -> Dict[str, Any]:
        """Collect sentiment data from Twitter within strict rate limits"""
        if not self.api or not self.check_rate_limit():
            return self._empty_result()
        
        collected_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "twitter",
            "tweets": [],
            "influencer_data": {},
            "api_calls_used": 0,
            "data_quality": "premium"  # High quality due to selective collection
        }
        
        try:
            # Collect from high-impact accounts only
            tweets_per_account = 2  # Latest 2 tweets per account
            accounts_to_process = min(6, len(self.target_accounts))  # Limit accounts per cycle
            
            for i, username in enumerate(self.target_accounts[:accounts_to_process]):
                if not self.check_rate_limit():
                    break
                    
                account_data = await self._collect_account_tweets(username, tweets_per_account)
                
                if account_data["tweets"]:
                    collected_data["influencer_data"][username] = account_data
                    collected_data["tweets"].extend(account_data["tweets"])
                
                # Small delay between accounts
                await asyncio.sleep(1)
            
            collected_data["api_calls_used"] = self.posts_collected
            collected_data["total_tweets"] = len(collected_data["tweets"])
            collected_data["accounts_processed"] = len(collected_data["influencer_data"])
            
            logger.info(f"Twitter collection complete: {collected_data['total_tweets']} tweets "
                       f"from {collected_data['accounts_processed']} accounts, "
                       f"{collected_data['api_calls_used']} API calls")
            
            return collected_data
            
        except Exception as e:
            logger.error(f"Error collecting Twitter data: {e}")
            return self._empty_result()
    
    async def _collect_account_tweets(self, username: str, limit: int) -> Dict[str, Any]:
        """Collect recent tweets from a specific account"""
        account_data = {
            "username": username,
            "tweets": [],
            "follower_count": 0,
            "verified": False
        }
        
        try:
            if not self.check_rate_limit():
                return account_data
                
            # Get user info first
            user = self.api.get_user(username=username, user_fields=['public_metrics', 'verified'])
            
            if user.data:
                account_data["follower_count"] = user.data.public_metrics.get('followers_count', 0)
                account_data["verified"] = user.data.verified or False
                user_id = user.data.id
                
                # Get recent tweets
                tweets = self.api.get_users_tweets(
                    id=user_id,
                    max_results=min(limit, 10),  # API minimum is 5, max for free tier
                    tweet_fields=['created_at', 'public_metrics', 'context_annotations', 'lang'],
                    exclude=['retweets', 'replies']  # Focus on original content
                )
                
                if tweets.data:
                    for tweet in tweets.data[:limit]:
                        # Only process English tweets with crypto relevance
                        if self._is_crypto_relevant(tweet.text) and tweet.lang == 'en':
                            tweet_data = {
                                "id": tweet.id,
                                "text": tweet.text[:280],  # Twitter limit
                                "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                                "author": username,
                                "follower_count": account_data["follower_count"],
                                "verified": account_data["verified"],
                                "retweet_count": tweet.public_metrics.get('retweet_count', 0),
                                "like_count": tweet.public_metrics.get('like_count', 0),
                                "reply_count": tweet.public_metrics.get('reply_count', 0),
                                "quote_count": tweet.public_metrics.get('quote_count', 0),
                                "engagement_score": self._calculate_engagement_score(tweet.public_metrics),
                                "sentiment_text": tweet.text
                            }
                            
                            account_data["tweets"].append(tweet_data)
                            self.posts_collected += 1
                            
                            if not self.check_rate_limit():
                                break
            
            return account_data
            
        except Exception as e:
            logger.error(f"Error collecting tweets from @{username}: {e}")
            return account_data
    
    def _is_crypto_relevant(self, text: str) -> bool:
        """Check if tweet is crypto-relevant"""
        crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'blockchain', 'defi', 'nft', 'altcoin', 'satoshi', 'hodl',
            'trading', 'pump', 'dump', 'moon', 'bear', 'bull', 'market',
            'binance', 'coinbase', 'exchange', 'wallet', 'mining',
            'solana', 'cardano', 'polkadot', 'chainlink', 'dogecoin'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in crypto_keywords)
    
    def _calculate_engagement_score(self, metrics: Dict) -> float:
        """Calculate engagement score for tweet prioritization"""
        if not metrics:
            return 0.0
            
        likes = metrics.get('like_count', 0)
        retweets = metrics.get('retweet_count', 0) 
        replies = metrics.get('reply_count', 0)
        quotes = metrics.get('quote_count', 0)
        
        # Weighted engagement score
        score = (likes * 1.0) + (retweets * 2.0) + (replies * 1.5) + (quotes * 2.5)
        return score
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "twitter",
            "tweets": [],
            "influencer_data": {},
            "api_calls_used": 0,
            "total_tweets": 0,
            "accounts_processed": 0,
            "data_quality": "unavailable",
            "error": "API unavailable or rate limited"
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics"""
        cycle_elapsed = time.time() - self.cycle_start
        cycle_remaining = max(0, 21600 - cycle_elapsed)  # 6 hours
        budget_remaining = max(0, self.posts_per_cycle - self.posts_collected)
        
        return {
            "posts_collected": self.posts_collected,
            "cycle_budget": self.posts_per_cycle,
            "budget_remaining": budget_remaining,
            "cycle_time_remaining": cycle_remaining,
            "usage_percentage": (self.posts_collected / self.posts_per_cycle) * 100,
            "within_limits": self.posts_collected < self.posts_per_cycle,
            "monthly_limit": self.posts_per_month,
            "daily_limit": self.posts_per_day
        }