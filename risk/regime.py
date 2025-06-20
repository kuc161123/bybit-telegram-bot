#!/usr/bin/env python3
"""
AI-powered market regime detection.
"""
import logging
import asyncio
import json
from decimal import Decimal
from typing import Dict, Any

from utils.cache import get_ticker_price_cached, enhanced_cache

logger = logging.getLogger(__name__)

class AIMarketRegimeDetector:
    def __init__(self, openai_client=None):
        self.client = openai_client
        
    async def detect_market_regime(self, symbol="BTCUSDT") -> Dict[str, Any]:
        """Detect current market regime using AI analysis"""
        try:
            # Check cache first
            cache_key = f"regime_{symbol}"
            cached = enhanced_cache.get(cache_key)
            if cached:
                return cached
            
            if not self.client:
                # Fallback to technical regime detection
                result = await self._get_technical_regime(symbol)
            else:
                # Use AI-powered regime detection
                result = await self._get_ai_regime(symbol)
            
            # Cache for 10 minutes
            enhanced_cache.set(cache_key, result, ttl=600)
            return result
            
        except Exception as e:
            logger.error(f"Error detecting regime for {symbol}: {e}")
            return {
                "regime": "UNKNOWN",
                "confidence": 0,
                "trend_direction": "SIDEWAYS",
                "volatility": "MEDIUM",
                "phase": "CONSOLIDATION",
                "stability": 50,
                "strategy": "Wait for clearer signals",
                "error": str(e)
            }
    
    async def _get_ai_regime(self, symbol: str) -> Dict[str, Any]:
        """AI-powered regime detection"""
        try:
            # Get market data
            current_price = await get_ticker_price_cached(symbol)
            if not current_price:
                raise Exception("Could not fetch current price")
            
            # Simplified market analysis for prompt
            market_context = await self._get_market_context(symbol)
            
            prompt = f"""
            Analyze market regime for {symbol}:
            
            Current Price: {current_price}
            Market Context: {market_context}
            
            Classify the current market regime:
            
            1. Primary Regime: TRENDING, RANGING, VOLATILE, or QUIET
            2. Trend Direction: UP, DOWN, or SIDEWAYS  
            3. Volatility Level: LOW, MEDIUM, or HIGH
            4. Market Phase: ACCUMULATION, MARKUP, DISTRIBUTION, or DECLINE
            5. Regime Stability: 0-100 (how likely to continue)
            6. Optimal Strategy: Brief trading recommendation
            
            Respond ONLY with valid JSON:
            {{
                "regime": "TRENDING/RANGING/VOLATILE/QUIET",
                "confidence": 85,
                "trend_direction": "UP/DOWN/SIDEWAYS",
                "volatility": "LOW/MEDIUM/HIGH", 
                "phase": "ACCUMULATION/MARKUP/DISTRIBUTION/DECLINE",
                "stability": 75,
                "strategy": "Brief strategy recommendation"
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
                        temperature=0.2,
                        max_tokens=250
                    )
                ),
                timeout=15.0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate result
            required_keys = ["regime", "confidence", "trend_direction", "volatility", "phase", "stability", "strategy"]
            if not all(key in result for key in required_keys):
                raise Exception("Invalid AI response format")
                
            return result
            
        except Exception as e:
            logger.error(f"AI regime detection failed: {e}")
            # Fallback to technical analysis
            return await self._get_technical_regime(symbol)
    
    async def _get_technical_regime(self, symbol: str) -> Dict[str, Any]:
        """Fallback technical regime detection"""
        try:
            current_price = await get_ticker_price_cached(symbol)
            if not current_price:
                raise Exception("Could not fetch price")
            
            price_float = float(current_price)
            
            # Simple regime classification based on price
            if price_float > 60000:  # Example for BTC
                regime = "TRENDING"
                trend_direction = "UP"
                volatility = "MEDIUM"
                phase = "MARKUP"
                confidence = 70
                stability = 75
                strategy = "Follow the trend with momentum"
            elif price_float < 25000:
                regime = "TRENDING"
                trend_direction = "DOWN"
                volatility = "HIGH"
                phase = "DECLINE"
                confidence = 70
                stability = 60
                strategy = "Wait for reversal signals"
            else:
                regime = "RANGING"
                trend_direction = "SIDEWAYS"
                volatility = "MEDIUM"
                phase = "CONSOLIDATION"
                confidence = 60
                stability = 65
                strategy = "Range trading approach"
            
            return {
                "regime": regime,
                "confidence": confidence,
                "trend_direction": trend_direction,
                "volatility": volatility,
                "phase": phase,
                "stability": stability,
                "strategy": strategy
            }
            
        except Exception as e:
            logger.error(f"Technical regime detection failed: {e}")
            return {
                "regime": "UNKNOWN",
                "confidence": 0,
                "trend_direction": "SIDEWAYS",
                "volatility": "MEDIUM",
                "phase": "CONSOLIDATION",
                "stability": 50,
                "strategy": "Unable to determine regime"
            }
    
    async def _get_market_context(self, symbol: str) -> str:
        """Get market context for AI analysis"""
        try:
            current_price = await get_ticker_price_cached(symbol)
            if current_price:
                return f"Trading around {current_price} level"
            return "Market data loading"
        except:
            return "Market data unavailable"

# Global instance
regime_detector = AIMarketRegimeDetector()