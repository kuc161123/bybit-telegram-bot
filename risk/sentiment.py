#!/usr/bin/env python3
"""
AI-powered market sentiment analysis.
"""
import logging
import asyncio
import json
from decimal import Decimal
from typing import Dict, Any

from utils.cache import get_ticker_price_cached, enhanced_cache

logger = logging.getLogger(__name__)

class MarketSentimentAnalyzer:
    def __init__(self, openai_client=None):
        self.client = openai_client
        
    async def get_overall_sentiment(self, symbol="BTCUSDT") -> Dict[str, Any]:
        """Get overall market sentiment with AI analysis"""
        try:
            # Check cache first
            cache_key = f"sentiment_{symbol}"
            cached = enhanced_cache.get(cache_key)
            if cached:
                return cached
            
            if not self.client:
                # Fallback to technical sentiment
                result = await self._get_technical_sentiment(symbol)
            else:
                # Use AI-powered sentiment analysis
                result = await self._get_ai_sentiment(symbol)
            
            # Cache for 5 minutes
            enhanced_cache.set(cache_key, result, ttl=300)
            return result
            
        except Exception as e:
            logger.error(f"Error getting sentiment for {symbol}: {e}")
            return {
                "sentiment": "NEUTRAL",
                "score": 50,
                "confidence": 0,
                "factors": ["Error analyzing sentiment"],
                "error": str(e)
            }
    
    async def _get_ai_sentiment(self, symbol: str) -> Dict[str, Any]:
        """AI-powered sentiment analysis"""
        try:
            # Get market data
            current_price = await get_ticker_price_cached(symbol)
            if not current_price:
                raise Exception("Could not fetch current price")
            
            # Get price history for context
            price_data = await self._get_price_context(symbol)
            
            prompt = f"""
            Analyze market sentiment for {symbol}:
            
            Current Price: {current_price}
            Price Context: {price_data}
            
            Based on recent price action, provide sentiment analysis:
            
            1. Overall sentiment: BULLISH, BEARISH, or NEUTRAL
            2. Sentiment score: 0-100 (0=Very Bearish, 50=Neutral, 100=Very Bullish)
            3. Confidence level: 0-100
            4. Key factors influencing sentiment (max 3 points)
            
            Respond ONLY with valid JSON in this format:
            {{
                "sentiment": "BULLISH/BEARISH/NEUTRAL",
                "score": 65,
                "confidence": 80,
                "factors": ["Factor 1", "Factor 2", "Factor 3"]
            }}
            """
            
            # Use proper OpenAI API call with asyncio executor
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: self.client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=200
                    )
                ),
                timeout=10.0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate result
            if not all(key in result for key in ["sentiment", "score", "confidence", "factors"]):
                raise Exception("Invalid AI response format")
                
            return result
            
        except Exception as e:
            logger.error(f"AI sentiment analysis failed: {e}")
            # Fallback to technical analysis
            return await self._get_technical_sentiment(symbol)
    
    async def _get_technical_sentiment(self, symbol: str) -> Dict[str, Any]:
        """Fallback technical sentiment analysis"""
        try:
            current_price = await get_ticker_price_cached(symbol)
            if not current_price:
                raise Exception("Could not fetch price")
            
            # Simple price-based sentiment
            price_float = float(current_price)
            
            # Determine sentiment based on price patterns
            if price_float > 50000:  # Example thresholds for BTC
                sentiment = "BULLISH"
                score = min(80, 50 + (price_float - 50000) / 1000)
            elif price_float < 30000:
                sentiment = "BEARISH" 
                score = max(20, 50 - (30000 - price_float) / 1000)
            else:
                sentiment = "NEUTRAL"
                score = 50
            
            return {
                "sentiment": sentiment,
                "score": int(score),
                "confidence": 60,
                "factors": [
                    f"Current price: ${price_float:,.0f}",
                    "Technical analysis",
                    "Price level assessment"
                ]
            }
            
        except Exception as e:
            logger.error(f"Technical sentiment analysis failed: {e}")
            return {
                "sentiment": "NEUTRAL",
                "score": 50,
                "confidence": 0,
                "factors": ["Unable to analyze"],
                "error": str(e)
            }
    
    async def _get_price_context(self, symbol: str) -> str:
        """Get price context for AI analysis"""
        try:
            # Get recent price data (simplified)
            current_price = await get_ticker_price_cached(symbol)
            if current_price:
                return f"Recent price around {current_price}"
            return "Price data unavailable"
        except:
            return "Price data unavailable"

# Global instance
sentiment_analyzer = MarketSentimentAnalyzer()