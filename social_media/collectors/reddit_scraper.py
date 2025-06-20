#!/usr/bin/env python3
"""
Reddit Web Scraper - No API Credentials Required
Uses Reddit's .json endpoints for data collection
Rate Limit: Self-imposed 60 requests/hour for respectful usage
"""
import logging
import asyncio
import time
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import aiohttp

logger = logging.getLogger(__name__)

class RedditScraper:
    def __init__(self):
        # Target crypto subreddits
        self.target_subreddits = [
            "CryptoCurrency",
            "Bitcoin", 
            "ethereum",
            "altcoins",
            "CryptoMarkets",
            "defi",
            "solana",
            "cardano",
            "Chainlink",
            "binance"
        ]
        
        # Rate limiting (60 requests/hour = 1 per minute)
        self.requests_per_hour = 60
        self.requests_made = 0
        self.hour_start = time.time()
        
        # User agent for respectful scraping
        self.headers = {
            "User-Agent": "CryptoSentimentBot/1.0 (Educational Research)"
        }
        
        # Crypto keywords for relevance filtering
        self.crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'blockchain', 'defi', 'nft', 'altcoin', 'solana', 'sol', 'cardano', 'ada',
            'polygon', 'matic', 'chainlink', 'link', 'polkadot', 'dot', 'avalanche', 'avax',
            'binance', 'bnb', 'uniswap', 'uni', 'dogecoin', 'doge', 'shiba', 'shib',
            'litecoin', 'ltc', 'xrp', 'ripple', 'trading', 'hodl', 'moon', 'lambo'
        ]
    
    def check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        current_time = time.time()
        hour_elapsed = current_time - self.hour_start
        
        # Reset counter every hour
        if hour_elapsed > 3600:  # 1 hour
            self.requests_made = 0
            self.hour_start = current_time
            
        if self.requests_made >= self.requests_per_hour:
            logger.warning(f"Reddit scraper rate limit reached ({self.requests_per_hour}/hour)")
            return False
            
        return True
    
    async def collect_sentiment_data(self) -> Dict[str, Any]:
        """Collect Reddit sentiment data from multiple subreddits"""
        if not self.check_rate_limit():
            return self._empty_result()
        
        collected_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "reddit_scraper",
            "subreddit_data": {},
            "total_posts": 0,
            "total_comments": 0,
            "crypto_relevance_score": 0,
            "average_sentiment": 50,
            "trending_topics": [],
            "data_quality": "scraped"
        }
        
        try:
            # Collect from each subreddit
            for subreddit in self.target_subreddits[:5]:  # Limit to 5 subreddits per cycle
                if not self.check_rate_limit():
                    break
                    
                subreddit_data = await self._scrape_subreddit(subreddit)
                if subreddit_data:
                    collected_data["subreddit_data"][subreddit] = subreddit_data
                    collected_data["total_posts"] += subreddit_data.get("posts_analyzed", 0)
                    collected_data["total_comments"] += subreddit_data.get("comments_analyzed", 0)
                
                # Respectful delay between subreddits
                await asyncio.sleep(2)
            
            # Calculate overall metrics
            self._calculate_overall_sentiment(collected_data)
            
            logger.info(f"Reddit scraping complete: {collected_data['total_posts']} posts, "
                       f"{collected_data['total_comments']} comments from "
                       f"{len(collected_data['subreddit_data'])} subreddits")
            
            return collected_data
            
        except Exception as e:
            logger.error(f"Error in Reddit sentiment collection: {e}")
            return self._empty_result()
    
    async def _scrape_subreddit(self, subreddit: str) -> Optional[Dict[str, Any]]:
        """Scrape a specific subreddit for crypto sentiment"""
        try:
            subreddit_data = {
                "name": subreddit,
                "posts": [],
                "posts_analyzed": 0,
                "comments_analyzed": 0,
                "average_sentiment": 50,
                "crypto_posts": 0,
                "trending_keywords": []
            }
            
            # Get hot posts from subreddit
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        posts = data.get("data", {}).get("children", [])
                        
                        crypto_posts = []
                        all_keywords = []
                        
                        for post_data in posts:
                            post = post_data.get("data", {})
                            title = post.get("title", "")
                            selftext = post.get("selftext", "")
                            score = post.get("score", 0)
                            num_comments = post.get("num_comments", 0)
                            
                            # Check crypto relevance
                            content = (title + " " + selftext).lower()
                            if self._is_crypto_relevant(content):
                                sentiment_score = self._analyze_reddit_sentiment(title, selftext, score)
                                
                                crypto_posts.append({
                                    "title": title[:200],  # Truncate long titles
                                    "score": score,
                                    "num_comments": num_comments,
                                    "sentiment_score": sentiment_score,
                                    "crypto_relevance": True
                                })
                                
                                # Extract keywords
                                keywords = self._extract_keywords(content)
                                all_keywords.extend(keywords)
                        
                        subreddit_data["posts"] = crypto_posts
                        subreddit_data["posts_analyzed"] = len(posts)
                        subreddit_data["crypto_posts"] = len(crypto_posts)
                        
                        # Calculate average sentiment
                        if crypto_posts:
                            avg_sentiment = sum(post["sentiment_score"] for post in crypto_posts) / len(crypto_posts)
                            subreddit_data["average_sentiment"] = int(avg_sentiment)
                        
                        # Get trending keywords
                        keyword_counts = {}
                        for keyword in all_keywords:
                            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
                        
                        trending = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                        subreddit_data["trending_keywords"] = [word for word, count in trending]
                        
                        self.requests_made += 1
                        return subreddit_data
                    
                    else:
                        logger.warning(f"Failed to scrape r/{subreddit}: HTTP {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error scraping subreddit r/{subreddit}: {e}")
            return None
    
    def _is_crypto_relevant(self, content: str) -> bool:
        """Check if content is crypto-relevant"""
        content_words = content.lower().split()
        return any(keyword in content_words or keyword in content for keyword in self.crypto_keywords)
    
    def _analyze_reddit_sentiment(self, title: str, text: str, score: int) -> int:
        """Analyze sentiment of Reddit post"""
        try:
            content = (title + " " + text).lower()
            
            # Positive indicators
            positive_words = [
                'moon', 'bull', 'bullish', 'pump', 'surge', 'rally', 'gains', 'profit',
                'hodl', 'diamond hands', 'to the moon', 'lambo', 'adoption', 'breakthrough',
                'positive', 'optimistic', 'strong', 'rising', 'up', 'good', 'great',
                'excellent', 'amazing', 'love', 'buy', 'accumulate', 'dca'
            ]
            
            # Negative indicators
            negative_words = [
                'bear', 'bearish', 'dump', 'crash', 'rekt', 'paper hands', 'fud',
                'scam', 'rug pull', 'dead', 'worthless', 'sell', 'exit', 'fear',
                'panic', 'worried', 'concern', 'risk', 'down', 'falling', 'drop',
                'bad', 'terrible', 'awful', 'hate', 'avoid', 'warning'
            ]
            
            positive_count = sum(1 for word in positive_words if word in content)
            negative_count = sum(1 for word in negative_words if word in content)
            
            # Factor in Reddit score (upvotes - downvotes)
            score_sentiment = 0
            if score > 100:
                score_sentiment = 10
            elif score > 50:
                score_sentiment = 5
            elif score < -10:
                score_sentiment = -10
            elif score < 0:
                score_sentiment = -5
            
            # Calculate base sentiment
            if positive_count == 0 and negative_count == 0:
                base_sentiment = 50
            else:
                total_sentiment_words = positive_count + negative_count
                positive_ratio = positive_count / total_sentiment_words if total_sentiment_words > 0 else 0.5
                base_sentiment = int(positive_ratio * 100)
            
            # Adjust with score sentiment
            final_sentiment = base_sentiment + score_sentiment
            
            # Ensure bounds
            return max(0, min(100, final_sentiment))
            
        except Exception as e:
            logger.debug(f"Error analyzing Reddit sentiment: {e}")
            return 50
    
    def _extract_keywords(self, content: str) -> List[str]:
        """Extract crypto keywords from content"""
        found_keywords = []
        content_lower = content.lower()
        
        for keyword in self.crypto_keywords:
            if keyword in content_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def _calculate_overall_sentiment(self, data: Dict):
        """Calculate overall sentiment metrics"""
        try:
            all_sentiments = []
            all_keywords = []
            
            for subreddit, sub_data in data["subreddit_data"].items():
                # Collect sentiments
                for post in sub_data.get("posts", []):
                    all_sentiments.append(post.get("sentiment_score", 50))
                
                # Collect keywords
                all_keywords.extend(sub_data.get("trending_keywords", []))
            
            # Calculate average sentiment
            if all_sentiments:
                data["average_sentiment"] = int(sum(all_sentiments) / len(all_sentiments))
                
                # Calculate crypto relevance score
                total_posts = data["total_posts"]
                crypto_posts = sum(sub_data.get("crypto_posts", 0) for sub_data in data["subreddit_data"].values())
                data["crypto_relevance_score"] = int((crypto_posts / total_posts) * 100) if total_posts > 0 else 0
            
            # Get overall trending topics
            keyword_counts = {}
            for keyword in all_keywords:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
            
            trending = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            data["trending_topics"] = [{"keyword": word, "mentions": count} for word, count in trending]
            
        except Exception as e:
            logger.error(f"Error calculating overall sentiment: {e}")
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "reddit_scraper",
            "subreddit_data": {},
            "total_posts": 0,
            "total_comments": 0,
            "crypto_relevance_score": 0,
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