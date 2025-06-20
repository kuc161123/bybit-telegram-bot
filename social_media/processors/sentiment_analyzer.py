#!/usr/bin/env python3
"""
Enhanced Sentiment Analyzer
Multi-source sentiment analysis with OpenAI integration
"""
import logging
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self, openai_client=None):
        self.openai_client = openai_client
        
        # Initialize backup sentiment analyzers
        self.textblob_available = False
        self.vader_available = False
        
        self._init_backup_analyzers()
        
        # Sentiment keywords for crypto context
        self.bullish_keywords = [
            'moon', 'bullish', 'pump', 'up', 'green', 'buy', 'hodl', 'long',
            'bullrun', 'rally', 'surge', 'breakout', 'strong', 'bullish',
            'optimistic', 'positive', 'gains', 'profit', 'rocket', 'lambo'
        ]
        
        self.bearish_keywords = [
            'dump', 'crash', 'bear', 'down', 'red', 'sell', 'short', 'drop',
            'bearish', 'decline', 'fall', 'correction', 'dip', 'recession',
            'pessimistic', 'negative', 'loss', 'liquidation', 'panic', 'fear'
        ]
        
        # Platform-specific confidence weights
        self.platform_weights = {
            "reddit": 1.0,      # High quality discussions
            "twitter": 0.9,     # Influencer focused, high quality
            "youtube": 1.0,     # In-depth analysis, high quality
            "discord": 0.7,     # More casual, but real-time
            "news_market": 1.2  # Official data, highest weight
        }
    
    def _init_backup_analyzers(self):
        """Initialize backup sentiment analysis libraries"""
        try:
            import textblob
            self.textblob_available = True
            logger.info("✅ TextBlob sentiment analyzer available")
        except ImportError:
            logger.info("TextBlob not available")
        
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self.vader_analyzer = SentimentIntensityAnalyzer()
            self.vader_available = True
            logger.info("✅ VADER sentiment analyzer available")
        except ImportError:
            logger.info("VADER sentiment not available")
    
    async def analyze_platform_sentiment(self, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sentiment for a specific platform's data"""
        platform = platform_data.get("platform", "unknown")
        
        sentiment_result = {
            "platform": platform,
            "timestamp": datetime.utcnow().isoformat(),
            "overall_sentiment": "NEUTRAL",
            "sentiment_score": 50,
            "confidence": 0,
            "total_items": 0,
            "bullish_items": 0,
            "bearish_items": 0,
            "neutral_items": 0,
            "top_keywords": [],
            "analysis_method": "unavailable"
        }
        
        try:
            # Extract text content based on platform
            text_items = self._extract_text_content(platform_data)
            
            if not text_items:
                return sentiment_result
            
            sentiment_result["total_items"] = len(text_items)
            
            # Analyze sentiment using best available method
            if self.openai_client:
                result = await self._analyze_with_openai(text_items, platform)
            elif self.vader_available:
                result = self._analyze_with_vader(text_items)
            elif self.textblob_available:
                result = self._analyze_with_textblob(text_items)
            else:
                result = self._analyze_with_keywords(text_items)
            
            # Update sentiment result
            sentiment_result.update(result)
            
            # Apply platform-specific confidence weighting
            confidence_weight = self.platform_weights.get(platform, 1.0)
            sentiment_result["confidence"] = min(100, sentiment_result["confidence"] * confidence_weight)
            
            # Extract top keywords
            sentiment_result["top_keywords"] = self._extract_keywords(text_items)
            
            logger.info(f"Sentiment analysis complete for {platform}: "
                       f"{sentiment_result['overall_sentiment']} "
                       f"(Score: {sentiment_result['sentiment_score']}, "
                       f"Confidence: {sentiment_result['confidence']:.1f}%)")
            
            return sentiment_result
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment for {platform}: {e}")
            sentiment_result["error"] = str(e)
            return sentiment_result
    
    def _extract_text_content(self, platform_data: Dict[str, Any]) -> List[str]:
        """Extract text content from platform data"""
        text_items = []
        platform = platform_data.get("platform", "")
        
        try:
            if platform in ["reddit", "reddit_scraper"]:
                # Extract from posts and comments - handle both API and scraper formats
                # Handle scraped Reddit data from subreddit_data
                if "subreddit_data" in platform_data:
                    for subreddit, sub_data in platform_data["subreddit_data"].items():
                        for post in sub_data.get("posts", []):
                            title = post.get("title", "")
                            if title and title.strip():
                                text_items.append(title.strip())
                
                # Handle direct posts format
                for post in platform_data.get("posts", []):
                    text = post.get("sentiment_text") or post.get("title") or post.get("text", "")
                    if text and text.strip():
                        text_items.append(text.strip())
                
                for comment in platform_data.get("comments", []):
                    text = comment.get("sentiment_text") or comment.get("body") or comment.get("text", "")
                    if text and text.strip():
                        text_items.append(text.strip())
            
            elif platform in ["twitter", "twitter_scraper"]:
                # Extract from tweets - handle both API and scraper formats
                # Handle scraper Twitter data from account_data
                if "account_data" in platform_data:
                    for account, acc_data in platform_data["account_data"].items():
                        for tweet in acc_data.get("tweets", []):
                            text = tweet.get("text", "")
                            if text and text.strip():
                                text_items.append(text.strip())
                
                # Handle direct tweets format
                for tweet in platform_data.get("tweets", []):
                    text = tweet.get("sentiment_text") or tweet.get("text") or tweet.get("full_text", "")
                    if text and text.strip():
                        text_items.append(text.strip())
            
            elif platform in ["youtube", "youtube_scraper"]:
                # Extract from video titles/descriptions and comments - handle both API and scraper formats
                # Handle scraper YouTube data from channel_data
                if "channel_data" in platform_data:
                    for channel, ch_data in platform_data["channel_data"].items():
                        for video in ch_data.get("videos", []):
                            title = video.get("title", "")
                            if title and title.strip():
                                text_items.append(title.strip())
                
                # Handle direct videos format
                for video in platform_data.get("videos", []):
                    text = video.get("sentiment_text") or video.get("title") or video.get("description", "")
                    if text and text.strip():
                        text_items.append(text.strip())
                
                for comment in platform_data.get("comments", []):
                    text = comment.get("sentiment_text") or comment.get("text") or comment.get("textDisplay", "")
                    if text and text.strip():
                        text_items.append(text.strip())
            
            elif platform in ["discord", "discord_scraper"]:
                # Extract from messages - handle both API and scraper formats
                for message in platform_data.get("messages", []):
                    text = message.get("sentiment_text") or message.get("content") or message.get("text", "")
                    if text and text.strip():
                        text_items.append(text.strip())
            
            elif platform == "news_market":
                # Generate text from market data
                if platform_data.get("fear_greed_index"):
                    fng = platform_data["fear_greed_index"]
                    text_items.append(f"Fear and Greed Index is {fng['value']} indicating {fng['value_classification']} market sentiment")
                
                if platform_data.get("global_market_cap"):
                    market = platform_data["global_market_cap"]
                    change = market.get("market_cap_change_percentage_24h", 0)
                    text_items.append(f"Global market cap changed {change:.2f}% in 24 hours")
        
        except Exception as e:
            logger.error(f"Error extracting text content: {e}")
        
        return text_items
    
    async def _analyze_with_openai(self, text_items: List[str], platform: str) -> Dict[str, Any]:
        """Analyze sentiment using OpenAI"""
        try:
            # Sample text for analysis (to stay within token limits)
            sample_size = min(20, len(text_items))
            sample_texts = text_items[:sample_size]
            
            # Prepare analysis text
            analysis_text = "\n".join([f"- {text[:200]}" for text in sample_texts])
            
            prompt = f"""
            Analyze the sentiment of these {platform} posts/messages about cryptocurrency:

            {analysis_text}

            Provide a JSON response with:
            1. overall_sentiment: "BULLISH", "BEARISH", or "NEUTRAL"
            2. sentiment_score: 0-100 (0=Very Bearish, 50=Neutral, 100=Very Bullish)
            3. confidence: 0-100 (confidence in the analysis)
            4. bullish_count: number of bullish items
            5. bearish_count: number of bearish items
            6. neutral_count: number of neutral items
            7. key_themes: top 3 themes mentioned

            Consider crypto-specific language like "moon", "dump", "HODL", "diamond hands", etc.

            Respond ONLY with valid JSON:
            {{
                "overall_sentiment": "BULLISH/BEARISH/NEUTRAL",
                "sentiment_score": 75,
                "confidence": 85,
                "bullish_count": 12,
                "bearish_count": 3,
                "neutral_count": 5,
                "key_themes": ["bitcoin rally", "altcoin season", "market optimism"]
            }}
            """
            
            # Use async executor for OpenAI call
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.openai_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=300
                    )
                ),
                timeout=15.0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate and normalize result
            return {
                "overall_sentiment": result.get("overall_sentiment", "NEUTRAL"),
                "sentiment_score": max(0, min(100, result.get("sentiment_score", 50))),
                "confidence": max(0, min(100, result.get("confidence", 50))),
                "bullish_items": result.get("bullish_count", 0),
                "bearish_items": result.get("bearish_count", 0),
                "neutral_items": result.get("neutral_count", 0),
                "key_themes": result.get("key_themes", []),
                "analysis_method": "openai_gpt"
            }
            
        except Exception as e:
            logger.error(f"OpenAI sentiment analysis failed: {e}")
            # Fallback to VADER or keyword analysis
            if self.vader_available:
                return self._analyze_with_vader(text_items)
            else:
                return self._analyze_with_keywords(text_items)
    
    def _analyze_with_vader(self, text_items: List[str]) -> Dict[str, Any]:
        """Analyze sentiment using VADER"""
        try:
            scores = []
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0
            
            for text in text_items:
                score = self.vader_analyzer.polarity_scores(text)
                compound_score = score['compound']
                scores.append(compound_score)
                
                if compound_score >= 0.05:
                    bullish_count += 1
                elif compound_score <= -0.05:
                    bearish_count += 1
                else:
                    neutral_count += 1
            
            # Calculate overall sentiment
            avg_score = sum(scores) / len(scores) if scores else 0
            sentiment_score = int((avg_score + 1) * 50)  # Convert from [-1,1] to [0,100]
            
            if avg_score >= 0.1:
                overall_sentiment = "BULLISH"
            elif avg_score <= -0.1:
                overall_sentiment = "BEARISH"
            else:
                overall_sentiment = "NEUTRAL"
            
            # Calculate confidence based on consistency
            confidence = self._calculate_confidence(scores) * 85  # VADER is quite reliable
            
            return {
                "overall_sentiment": overall_sentiment,
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "bullish_items": bullish_count,
                "bearish_items": bearish_count,
                "neutral_items": neutral_count,
                "analysis_method": "vader"
            }
            
        except Exception as e:
            logger.error(f"VADER sentiment analysis failed: {e}")
            return self._analyze_with_keywords(text_items)
    
    def _analyze_with_textblob(self, text_items: List[str]) -> Dict[str, Any]:
        """Analyze sentiment using TextBlob"""
        try:
            from textblob import TextBlob
            
            scores = []
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0
            
            for text in text_items:
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity  # Range: [-1, 1]
                scores.append(polarity)
                
                if polarity > 0.1:
                    bullish_count += 1
                elif polarity < -0.1:
                    bearish_count += 1
                else:
                    neutral_count += 1
            
            # Calculate overall sentiment
            avg_score = sum(scores) / len(scores) if scores else 0
            sentiment_score = int((avg_score + 1) * 50)  # Convert from [-1,1] to [0,100]
            
            if avg_score >= 0.1:
                overall_sentiment = "BULLISH"
            elif avg_score <= -0.1:
                overall_sentiment = "BEARISH"
            else:
                overall_sentiment = "NEUTRAL"
            
            confidence = self._calculate_confidence(scores) * 70  # TextBlob is decent
            
            return {
                "overall_sentiment": overall_sentiment,
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "bullish_items": bullish_count,
                "bearish_items": bearish_count,
                "neutral_items": neutral_count,
                "analysis_method": "textblob"
            }
            
        except Exception as e:
            logger.error(f"TextBlob sentiment analysis failed: {e}")
            return self._analyze_with_keywords(text_items)
    
    def _analyze_with_keywords(self, text_items: List[str]) -> Dict[str, Any]:
        """Fallback keyword-based sentiment analysis"""
        try:
            bullish_count = 0
            bearish_count = 0
            neutral_count = 0
            
            for text in text_items:
                text_lower = text.lower()
                
                bullish_matches = sum(1 for keyword in self.bullish_keywords if keyword in text_lower)
                bearish_matches = sum(1 for keyword in self.bearish_keywords if keyword in text_lower)
                
                if bullish_matches > bearish_matches:
                    bullish_count += 1
                elif bearish_matches > bullish_matches:
                    bearish_count += 1
                else:
                    neutral_count += 1
            
            total_items = len(text_items)
            if total_items == 0:
                return {
                    "overall_sentiment": "NEUTRAL",
                    "sentiment_score": 50,
                    "confidence": 0,
                    "bullish_items": 0,
                    "bearish_items": 0,
                    "neutral_items": 0,
                    "analysis_method": "keyword_fallback"
                }
            
            # Calculate sentiment score
            bullish_ratio = bullish_count / total_items
            bearish_ratio = bearish_count / total_items
            
            sentiment_score = int(50 + (bullish_ratio - bearish_ratio) * 50)
            sentiment_score = max(0, min(100, sentiment_score))
            
            if sentiment_score >= 60:
                overall_sentiment = "BULLISH"
            elif sentiment_score <= 40:
                overall_sentiment = "BEARISH"
            else:
                overall_sentiment = "NEUTRAL"
            
            # Lower confidence for keyword analysis
            confidence = min(60, abs(sentiment_score - 50) * 1.2)
            
            return {
                "overall_sentiment": overall_sentiment,
                "sentiment_score": sentiment_score,
                "confidence": confidence,
                "bullish_items": bullish_count,
                "bearish_items": bearish_count,
                "neutral_items": neutral_count,
                "analysis_method": "keyword_based"
            }
            
        except Exception as e:
            logger.error(f"Keyword sentiment analysis failed: {e}")
            return {
                "overall_sentiment": "NEUTRAL",
                "sentiment_score": 50,
                "confidence": 0,
                "bullish_items": 0,
                "bearish_items": 0,
                "neutral_items": 0,
                "analysis_method": "error_fallback",
                "error": str(e)
            }
    
    def _calculate_confidence(self, scores: List[float]) -> float:
        """Calculate confidence based on score consistency"""
        if not scores:
            return 0.0
        
        # Calculate standard deviation
        avg = sum(scores) / len(scores)
        variance = sum((x - avg) ** 2 for x in scores) / len(scores)
        std_dev = variance ** 0.5
        
        # Lower standard deviation = higher confidence
        # Normalize to 0-1 range
        confidence = max(0, 1 - (std_dev / 2))
        return confidence
    
    def _extract_keywords(self, text_items: List[str]) -> List[str]:
        """Extract top keywords from text content"""
        try:
            # Combine all text
            all_text = " ".join(text_items).lower()
            
            # Define crypto-relevant keywords to track
            crypto_keywords = [
                'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'bullish', 'bearish',
                'moon', 'dump', 'pump', 'hodl', 'altcoin', 'defi', 'nft', 'trading',
                'market', 'price', 'rally', 'crash', 'support', 'resistance'
            ]
            
            # Count keyword occurrences
            keyword_counts = {}
            for keyword in crypto_keywords:
                count = all_text.count(keyword)
                if count > 0:
                    keyword_counts[keyword] = count
            
            # Return top 5 keywords
            top_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            return [keyword for keyword, count in top_keywords]
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []