#!/usr/bin/env python3
"""
News and Market Data Collector - Free APIs
CoinGecko API: 50 calls/minute = 72,000 calls/day
Using ~25 calls per 6-hour cycle
"""
import logging
import asyncio
import time
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os
import aiohttp

logger = logging.getLogger(__name__)

class NewsCollector:
    def __init__(self):
        # CoinGecko API (free tier)
        self.coingecko_base_url = "https://api.coingecko.com/api/v3"
        
        # Alternative.me API (completely free)
        self.alternative_me_base_url = "https://api.alternative.me"
        
        # Free crypto news RSS feeds (no credentials needed)
        self.news_sources = {
            "cointelegraph": "https://cointelegraph.com/rss",
            "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "decrypt": "https://decrypt.co/feed",
            "cryptonews": "https://cryptonews.com/news/feed/",
            "bitcoinist": "https://bitcoinist.com/feed/"
        }
        
        # Rate limiting for all sources
        self.calls_per_cycle = 35  # Increased for more sources
        self.calls_made = 0
        self.cycle_start = time.time()
        
        # Target cryptocurrencies for news/sentiment
        self.target_cryptocurrencies = [
            "bitcoin", "ethereum", "binancecoin", "cardano", "solana",
            "polkadot", "chainlink", "litecoin", "avalanche-2", "polygon",
            "avalanche", "uniswap", "chainlink", "dogecoin", "shiba-inu"
        ]
    
    def check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        current_time = time.time()
        cycle_elapsed = current_time - self.cycle_start
        
        # Reset counter every 6 hours
        if cycle_elapsed > 21600:  # 6 hours
            self.calls_made = 0
            self.cycle_start = current_time
            
        if self.calls_made >= self.calls_per_cycle:
            logger.warning(f"News API cycle budget ({self.calls_per_cycle}) reached")
            return False
            
        return True
    
    async def collect_sentiment_data(self) -> Dict[str, Any]:
        """Collect market sentiment and news data"""
        if not self.check_rate_limit():
            return self._empty_result()
        
        collected_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "news_market",
            "fear_greed_index": {},
            "trending_coins": [],
            "market_data": {},
            "global_market_cap": {},
            "api_calls_used": 0,
            "data_quality": "official"
        }
        
        try:
            # Collect Fear & Greed Index
            await self._collect_fear_greed_index(collected_data)
            
            # Collect trending coins
            await self._collect_trending_coins(collected_data)
            
            # Collect global market data
            await self._collect_global_market_data(collected_data)
            
            # Collect price data for major cryptocurrencies
            await self._collect_crypto_prices(collected_data)
            
            # Collect crypto news from RSS feeds (no API calls)
            await self._collect_crypto_news(collected_data)
            
            collected_data["api_calls_used"] = self.calls_made
            
            logger.info(f"News/Market collection complete: {collected_data['api_calls_used']} API calls")
            
            return collected_data
            
        except Exception as e:
            logger.error(f"Error collecting news/market data: {e}")
            return self._empty_result()
    
    async def _collect_fear_greed_index(self, data: Dict):
        """Collect Fear & Greed Index data"""
        try:
            if not self.check_rate_limit():
                return
                
            # Alternative Fear & Greed Index (free)
            url = "https://api.alternative.me/fng/"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get("data"):
                            fng_data = result["data"][0]
                            data["fear_greed_index"] = {
                                "value": int(fng_data.get("value", 50)),
                                "value_classification": fng_data.get("value_classification", "Neutral"),
                                "timestamp": fng_data.get("timestamp"),
                                "time_until_update": fng_data.get("time_until_update")
                            }
                            
                            # Convert to sentiment score
                            fng_value = int(fng_data.get("value", 50))
                            if fng_value <= 25:
                                sentiment = "EXTREMELY_BEARISH"
                            elif fng_value <= 45:
                                sentiment = "BEARISH"
                            elif fng_value <= 55:
                                sentiment = "NEUTRAL"
                            elif fng_value <= 75:
                                sentiment = "BULLISH"
                            else:
                                sentiment = "EXTREMELY_BULLISH"
                                
                            data["fear_greed_index"]["market_sentiment"] = sentiment
                            
            self.calls_made += 1
            
        except Exception as e:
            logger.error(f"Error collecting Fear & Greed Index: {e}")
    
    async def _collect_trending_coins(self, data: Dict):
        """Collect trending cryptocurrencies"""
        try:
            if not self.check_rate_limit():
                return
                
            url = f"{self.coingecko_base_url}/search/trending"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        trending_coins = []
                        for coin in result.get("coins", [])[:10]:  # Top 10
                            coin_data = coin.get("item", {})
                            trending_coins.append({
                                "id": coin_data.get("id"),
                                "name": coin_data.get("name"),
                                "symbol": coin_data.get("symbol"),
                                "market_cap_rank": coin_data.get("market_cap_rank"),
                                "score": coin_data.get("score", 0)
                            })
                        
                        data["trending_coins"] = trending_coins
                        
            self.calls_made += 1
            
        except Exception as e:
            logger.error(f"Error collecting trending coins: {e}")
    
    async def _collect_global_market_data(self, data: Dict):
        """Collect global cryptocurrency market data"""
        try:
            if not self.check_rate_limit():
                return
                
            url = f"{self.coingecko_base_url}/global"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        global_data = result.get("data", {})
                        data["global_market_cap"] = {
                            "total_market_cap_usd": global_data.get("total_market_cap", {}).get("usd", 0),
                            "total_volume_usd": global_data.get("total_volume", {}).get("usd", 0),
                            "market_cap_percentage": global_data.get("market_cap_percentage", {}),
                            "active_cryptocurrencies": global_data.get("active_cryptocurrencies", 0),
                            "markets": global_data.get("markets", 0),
                            "market_cap_change_percentage_24h": global_data.get("market_cap_change_percentage_24h_usd", 0)
                        }
                        
            self.calls_made += 1
            
        except Exception as e:
            logger.error(f"Error collecting global market data: {e}")
    
    async def _collect_crypto_prices(self, data: Dict):
        """Collect price data for major cryptocurrencies"""
        try:
            if not self.check_rate_limit():
                return
                
            # Get top 20 cryptocurrencies by market cap
            url = f"{self.coingecko_base_url}/coins/markets"
            params = {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 20,
                "page": 1,
                "sparkline": False,
                "price_change_percentage": "24h"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        market_data = {}
                        for coin in result:
                            market_data[coin["symbol"].upper()] = {
                                "id": coin["id"],
                                "name": coin["name"],
                                "symbol": coin["symbol"].upper(),
                                "current_price": coin["current_price"],
                                "market_cap": coin["market_cap"],
                                "market_cap_rank": coin["market_cap_rank"],
                                "price_change_24h": coin["price_change_24h"],
                                "price_change_percentage_24h": coin["price_change_percentage_24h"],
                                "volume_24h": coin["total_volume"]
                            }
                        
                        data["market_data"] = market_data
                        
            self.calls_made += 1
            
        except Exception as e:
            logger.error(f"Error collecting crypto prices: {e}")
    
    async def _collect_crypto_news(self, data: Dict):
        """Collect crypto news from RSS feeds (no API credentials needed)"""
        try:
            news_articles = []
            crypto_keywords = [
                'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
                'blockchain', 'defi', 'nft', 'altcoin', 'solana', 'cardano',
                'polygon', 'chainlink', 'polkadot', 'avalanche', 'binance'
            ]
            
            for source_name, rss_url in self.news_sources.items():
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(rss_url, timeout=10) as response:
                            if response.status == 200:
                                xml_content = await response.text()
                                root = ET.fromstring(xml_content)
                                
                                # Parse RSS items
                                for item in root.findall('.//item')[:5]:  # Top 5 articles per source
                                    try:
                                        title = item.find('title')
                                        description = item.find('description')
                                        pub_date = item.find('pubDate')
                                        link = item.find('link')
                                        
                                        if title is not None:
                                            title_text = title.text or ""
                                            desc_text = description.text or "" if description is not None else ""
                                            
                                            # Check if article is crypto-related
                                            content = (title_text + " " + desc_text).lower()
                                            if any(keyword in content for keyword in crypto_keywords):
                                                
                                                # Basic sentiment analysis on title + description
                                                sentiment_score = self._analyze_news_sentiment(title_text + " " + desc_text)
                                                
                                                news_articles.append({
                                                    "source": source_name,
                                                    "title": title_text[:200],  # Truncate long titles
                                                    "description": desc_text[:300] if desc_text else "",
                                                    "sentiment_score": sentiment_score,
                                                    "pub_date": pub_date.text if pub_date is not None else "",
                                                    "link": link.text if link is not None else "",
                                                    "crypto_relevance": True
                                                })
                                    except Exception as article_error:
                                        logger.debug(f"Error parsing article from {source_name}: {article_error}")
                                        continue
                                        
                except Exception as source_error:
                    logger.debug(f"Error collecting from {source_name}: {source_error}")
                    continue
                    
                # Small delay between sources to be respectful
                await asyncio.sleep(0.5)
            
            data["news_articles"] = news_articles
            logger.info(f"Collected {len(news_articles)} crypto news articles from {len(self.news_sources)} sources")
            
        except Exception as e:
            logger.error(f"Error collecting crypto news: {e}")
            data["news_articles"] = []
    
    def _analyze_news_sentiment(self, text: str) -> int:
        """Basic sentiment analysis for news articles"""
        try:
            if not text:
                return 50
                
            text_lower = text.lower()
            
            # Positive indicators
            positive_words = [
                'bullish', 'surge', 'rally', 'gains', 'pump', 'moon', 'positive', 'growth',
                'adoption', 'breakthrough', 'success', 'profit', 'bull', 'rising', 'soar',
                'milestone', 'record', 'high', 'optimistic', 'strong', 'boost', 'upgrade'
            ]
            
            # Negative indicators  
            negative_words = [
                'bearish', 'crash', 'dump', 'loss', 'decline', 'bear', 'falling', 'drop',
                'scam', 'hack', 'fraud', 'regulation', 'ban', 'crackdown', 'warning',
                'concern', 'risk', 'volatile', 'uncertainty', 'weak', 'plummet', 'collapse'
            ]
            
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            # Calculate sentiment score (0-100)
            if positive_count == 0 and negative_count == 0:
                return 50  # Neutral
            
            total_sentiment_words = positive_count + negative_count
            positive_ratio = positive_count / total_sentiment_words if total_sentiment_words > 0 else 0.5
            
            # Convert to 0-100 scale
            sentiment_score = int(positive_ratio * 100)
            
            # Ensure bounds
            return max(0, min(100, sentiment_score))
            
        except Exception as e:
            logger.debug(f"Error analyzing news sentiment: {e}")
            return 50  # Default neutral
    
    def generate_market_sentiment_summary(self, data: Dict) -> Dict[str, Any]:
        """Generate market sentiment summary from collected data"""
        try:
            summary = {
                "overall_sentiment": "NEUTRAL",
                "sentiment_score": 50,
                "key_factors": [],
                "market_mood": "Mixed"
            }
            
            # Analyze Fear & Greed Index
            if data.get("fear_greed_index"):
                fng_value = data["fear_greed_index"]["value"]
                summary["sentiment_score"] = fng_value
                summary["overall_sentiment"] = data["fear_greed_index"]["market_sentiment"]
                summary["key_factors"].append(f"Fear & Greed Index: {fng_value}/100")
            
            # Analyze market cap change
            if data.get("global_market_cap"):
                market_change = data["global_market_cap"]["market_cap_change_percentage_24h"]
                if market_change > 2:
                    summary["key_factors"].append("Strong market cap growth (+2%)")
                elif market_change < -2:
                    summary["key_factors"].append("Market cap decline (-2%)")
                else:
                    summary["key_factors"].append("Stable market conditions")
            
            # Analyze trending coins
            if data.get("trending_coins"):
                trending_count = len(data["trending_coins"])
                summary["key_factors"].append(f"{trending_count} coins trending")
            
            # Analyze news sentiment
            if data.get("news_articles"):
                news_articles = data["news_articles"]
                if news_articles:
                    avg_news_sentiment = sum(article.get("sentiment_score", 50) for article in news_articles) / len(news_articles)
                    
                    # Weight news sentiment with market sentiment
                    if "sentiment_score" in summary:
                        # 70% market data, 30% news sentiment
                        combined_sentiment = (summary["sentiment_score"] * 0.7) + (avg_news_sentiment * 0.3)
                        summary["sentiment_score"] = int(combined_sentiment)
                    else:
                        summary["sentiment_score"] = int(avg_news_sentiment)
                    
                    # Update overall sentiment based on combined score
                    if summary["sentiment_score"] >= 70:
                        summary["overall_sentiment"] = "BULLISH"
                    elif summary["sentiment_score"] >= 55:
                        summary["overall_sentiment"] = "SLIGHTLY_BULLISH" 
                    elif summary["sentiment_score"] >= 45:
                        summary["overall_sentiment"] = "NEUTRAL"
                    elif summary["sentiment_score"] >= 30:
                        summary["overall_sentiment"] = "SLIGHTLY_BEARISH"
                    else:
                        summary["overall_sentiment"] = "BEARISH"
                    
                    summary["key_factors"].append(f"{len(news_articles)} news articles analyzed")
                    
                    # Add news source diversity
                    news_sources = set(article.get("source", "") for article in news_articles)
                    summary["key_factors"].append(f"News from {len(news_sources)} sources")
            
            # Determine market mood
            if summary["sentiment_score"] >= 75:
                summary["market_mood"] = "Extremely Bullish"
            elif summary["sentiment_score"] >= 55:
                summary["market_mood"] = "Bullish"
            elif summary["sentiment_score"] >= 45:
                summary["market_mood"] = "Neutral"
            elif summary["sentiment_score"] >= 25:
                summary["market_mood"] = "Bearish"
            else:
                summary["market_mood"] = "Extremely Bearish"
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating market sentiment summary: {e}")
            return {
                "overall_sentiment": "NEUTRAL",
                "sentiment_score": 50,
                "key_factors": ["Unable to analyze"],
                "market_mood": "Unknown"
            }
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "news_market",
            "fear_greed_index": {},
            "trending_coins": [],
            "market_data": {},
            "global_market_cap": {},
            "api_calls_used": 0,
            "data_quality": "unavailable",
            "error": "API unavailable or rate limited"
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics"""
        cycle_elapsed = time.time() - self.cycle_start
        cycle_remaining = max(0, 21600 - cycle_elapsed)  # 6 hours
        calls_remaining = max(0, self.calls_per_cycle - self.calls_made)
        
        return {
            "calls_made": self.calls_made,
            "cycle_budget": self.calls_per_cycle,
            "calls_remaining": calls_remaining,
            "cycle_time_remaining": cycle_remaining,
            "usage_percentage": (self.calls_made / self.calls_per_cycle) * 100,
            "within_limits": self.calls_made < self.calls_per_cycle
        }