#!/usr/bin/env python3
"""
Reddit Data Collector - Optimized for Free API Limits
Rate Limit: 100 requests/minute = 144,000 requests/day
6-Hour Budget: 36,000 requests (using only 2,500 for safety)
"""
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class RedditCollector:
    def __init__(self):
        self.client_id = os.getenv("REDDIT_CLIENT_ID")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        self.user_agent = "CryptoSentimentBot/1.0"
        self.reddit = None
        
        # Rate limiting configuration
        self.requests_per_minute = 100
        self.cycle_budget = 2500  # Conservative usage per 6-hour cycle
        self.requests_made = 0
        self.cycle_start = time.time()
        
        # Target subreddits for crypto sentiment
        self.target_subreddits = [
            "CryptoCurrency",
            "Bitcoin", 
            "ethereum",
            "altcoins",
            "CryptoMarkets"
        ]
        
        self.initialize_reddit()
    
    def initialize_reddit(self):
        """Initialize Reddit API client"""
        try:
            if not self.client_id or not self.client_secret:
                logger.warning("Reddit API credentials not configured - skipping Reddit collection")
                self.reddit = None
                return False
                
            import praw
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
            
            logger.info("✅ Reddit API client initialized successfully")
            return True
            
        except ImportError:
            logger.error("praw library not installed. Run: pip install praw")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Reddit client: {e}")
            return False
    
    def check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        current_time = time.time()
        cycle_elapsed = current_time - self.cycle_start
        
        # Reset counter every 6 hours
        if cycle_elapsed > 21600:  # 6 hours
            self.requests_made = 0
            self.cycle_start = current_time
            
        # Check if we're within budget
        if self.requests_made >= self.cycle_budget:
            logger.warning(f"Reddit API cycle budget ({self.cycle_budget}) reached")
            return False
            
        return True
    
    async def collect_sentiment_data(self) -> Dict[str, Any]:
        """Collect sentiment data from Reddit within rate limits"""
        if not self.reddit or not self.check_rate_limit():
            return self._empty_result()
        
        collected_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "reddit",
            "posts": [],
            "comments": [],
            "subreddit_data": {},
            "api_calls_used": 0,
            "data_quality": "high"
        }
        
        try:
            # Collect from each target subreddit
            posts_per_subreddit = 100  # Top 100 hot posts
            comments_per_post = 20     # Top 20 comments
            
            for subreddit_name in self.target_subreddits:
                if not self.check_rate_limit():
                    break
                    
                subreddit_data = await self._collect_subreddit_data(
                    subreddit_name, posts_per_subreddit, comments_per_post
                )
                
                collected_data["subreddit_data"][subreddit_name] = subreddit_data
                collected_data["posts"].extend(subreddit_data["posts"])
                collected_data["comments"].extend(subreddit_data["comments"])
                
            collected_data["api_calls_used"] = self.requests_made
            collected_data["total_posts"] = len(collected_data["posts"])
            collected_data["total_comments"] = len(collected_data["comments"])
            
            logger.info(f"Reddit collection complete: {collected_data['total_posts']} posts, "
                       f"{collected_data['total_comments']} comments, "
                       f"{collected_data['api_calls_used']} API calls")
            
            return collected_data
            
        except Exception as e:
            logger.error(f"Error collecting Reddit data: {e}")
            return self._empty_result()
    
    async def _collect_subreddit_data(self, subreddit_name: str, 
                                    posts_limit: int, comments_limit: int) -> Dict[str, Any]:
        """Collect data from a specific subreddit"""
        subreddit_data = {
            "name": subreddit_name,
            "posts": [],
            "comments": [],
            "subscriber_count": 0,
            "active_users": 0
        }
        
        try:
            # Get subreddit info
            subreddit = self.reddit.subreddit(subreddit_name)
            self.requests_made += 1
            
            # Get subscriber count and active users
            try:
                subreddit_data["subscriber_count"] = subreddit.subscribers
                subreddit_data["active_users"] = subreddit.active_user_count
                self.requests_made += 1
            except:
                pass  # Some data might not be available
            
            # Collect hot posts
            post_count = 0
            for post in subreddit.hot(limit=posts_limit):
                if not self.check_rate_limit() or post_count >= posts_limit:
                    break
                    
                post_data = {
                    "id": post.id,
                    "title": post.title,
                    "text": post.selftext if hasattr(post, 'selftext') else "",
                    "score": post.score,
                    "upvote_ratio": post.upvote_ratio,
                    "num_comments": post.num_comments,
                    "created_utc": post.created_utc,
                    "author": str(post.author) if post.author else "[deleted]",
                    "url": post.url,
                    "flair": post.link_flair_text,
                    "sentiment_text": f"{post.title} {post.selftext}"[:500]  # Limit text for analysis
                }
                
                subreddit_data["posts"].append(post_data)
                
                # Collect top comments for this post
                await self._collect_post_comments(post, subreddit_data, comments_limit)
                
                post_count += 1
                self.requests_made += 1
                
                # Small delay to be respectful
                await asyncio.sleep(0.1)
            
            return subreddit_data
            
        except Exception as e:
            logger.error(f"Error collecting from r/{subreddit_name}: {e}")
            return subreddit_data
    
    async def _collect_post_comments(self, post, subreddit_data: Dict, limit: int):
        """Collect top comments from a post"""
        try:
            if not self.check_rate_limit():
                return
                
            # Get top comments
            post.comments.replace_more(limit=0)  # Don't expand "more comments"
            self.requests_made += 1
            
            comment_count = 0
            for comment in post.comments[:limit]:
                if not self.check_rate_limit() or comment_count >= limit:
                    break
                    
                if hasattr(comment, 'body') and comment.body != "[deleted]":
                    comment_data = {
                        "id": comment.id,
                        "post_id": post.id,
                        "body": comment.body[:300],  # Limit comment length
                        "score": comment.score,
                        "created_utc": comment.created_utc,
                        "author": str(comment.author) if comment.author else "[deleted]",
                        "sentiment_text": comment.body[:300]
                    }
                    
                    subreddit_data["comments"].append(comment_data)
                    comment_count += 1
                    
        except Exception as e:
            logger.error(f"Error collecting comments: {e}")
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "reddit",
            "posts": [],
            "comments": [],
            "subreddit_data": {},
            "api_calls_used": 0,
            "total_posts": 0,
            "total_comments": 0,
            "data_quality": "unavailable",
            "error": "API unavailable or rate limited"
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics"""
        cycle_elapsed = time.time() - self.cycle_start
        cycle_remaining = max(0, 21600 - cycle_elapsed)  # 6 hours
        budget_remaining = max(0, self.cycle_budget - self.requests_made)
        
        return {
            "requests_made": self.requests_made,
            "cycle_budget": self.cycle_budget,
            "budget_remaining": budget_remaining,
            "cycle_time_remaining": cycle_remaining,
            "usage_percentage": (self.requests_made / self.cycle_budget) * 100,
            "within_limits": self.requests_made < self.cycle_budget
        }