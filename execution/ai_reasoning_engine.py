#!/usr/bin/env python3
"""
AI Reasoning Engine - Enhanced market analysis using GPT-4
Provides BUY/HOLD/SELL recommendations with advanced reasoning
"""
import asyncio
import logging
from typing import Dict, Optional, Tuple, List
from datetime import datetime
import json
from config.settings import AI_MODEL

logger = logging.getLogger(__name__)

class AIReasoningEngine:
    """Advanced AI reasoning engine using GPT-4 for market analysis"""

    def __init__(self, ai_client):
        self.ai_client = ai_client
        self.gpt4_model = AI_MODEL  # Use configured model from settings
        self.reasoning_cache = {}
        self.cache_ttl = 300  # 5 minutes
        logger.info(f"🤖 AI Reasoning Engine initialized with model: {self.gpt4_model}")

    async def analyze_with_reasoning(
        self,
        symbol: str,
        market_data: Dict,
        technical_signals: Dict,
        market_regime: str,
        current_confidence: float
    ) -> Tuple[str, str, float, str]:
        """
        Perform advanced market analysis with GPT-4 reasoning

        Returns:
            - recommendation: BUY/HOLD/SELL
            - reasoning: Detailed explanation
            - enhanced_confidence: Improved confidence score
            - risk_assessment: Current risk level
        """
        try:
            # Check cache first
            cache_key = f"{symbol}_{market_regime}"
            if cache_key in self.reasoning_cache:
                cached_time, cached_result = self.reasoning_cache[cache_key]
                if (datetime.now() - cached_time).seconds < self.cache_ttl:
                    return cached_result

            # Prepare comprehensive context for GPT-4
            context = self._prepare_analysis_context(
                symbol, market_data, technical_signals, market_regime
            )

            # Get GPT-4 analysis
            recommendation, reasoning, risk_assessment = await self._get_gpt4_analysis(context)

            # Calculate enhanced confidence
            enhanced_confidence = self._calculate_enhanced_confidence(
                current_confidence, technical_signals, recommendation, market_regime
            )

            # Cache result
            result = (recommendation, reasoning, enhanced_confidence, risk_assessment)
            self.reasoning_cache[cache_key] = (datetime.now(), result)

            return result

        except Exception as e:
            logger.error(f"Error in AI reasoning analysis: {e}")
            # Fallback to simple recommendation
            return self._get_fallback_recommendation(technical_signals, market_regime)

    def _prepare_analysis_context(
        self,
        symbol: str,
        market_data: Dict,
        technical_signals: Dict,
        market_regime: str
    ) -> Dict:
        """Prepare comprehensive context for AI analysis"""

        # Extract key metrics
        current_price = market_data.get("current_price", 0)
        price_change_24h = market_data.get("price_change_24h_percent", 0)
        volume_ratio = technical_signals.get("volume_ratio", 1.0)

        # Technical indicators
        rsi = technical_signals.get("rsi", 50)
        macd = technical_signals.get("macd", 0)
        macd_signal = technical_signals.get("macd_signal", 0)

        # Support/Resistance
        support = technical_signals.get("support", current_price * 0.98)
        resistance = technical_signals.get("resistance", current_price * 1.02)

        # Moving averages
        sma_20 = technical_signals.get("sma_20", current_price)
        sma_50 = technical_signals.get("sma_50", current_price)

        # Bollinger Bands
        bb_upper = technical_signals.get("bb_upper", current_price * 1.02)
        bb_lower = technical_signals.get("bb_lower", current_price * 0.98)

        return {
            "symbol": symbol,
            "current_price": current_price,
            "price_change_24h": price_change_24h,
            "market_regime": market_regime,
            "volume_analysis": {
                "ratio": volume_ratio,
                "interpretation": "High" if volume_ratio > 2 else "Normal" if volume_ratio > 0.8 else "Low"
            },
            "technical_indicators": {
                "rsi": {
                    "value": rsi,
                    "condition": "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
                },
                "macd": {
                    "value": macd,
                    "signal": macd_signal,
                    "crossover": "Bullish" if macd > macd_signal else "Bearish"
                },
                "moving_averages": {
                    "sma_20": sma_20,
                    "sma_50": sma_50,
                    "trend": "Bullish" if sma_20 > sma_50 else "Bearish"
                },
                "bollinger_bands": {
                    "upper": bb_upper,
                    "lower": bb_lower,
                    "position": "Near Upper" if current_price > (bb_upper * 0.95) else "Near Lower" if current_price < (bb_lower * 1.05) else "Middle"
                }
            },
            "price_levels": {
                "support": support,
                "resistance": resistance,
                "distance_to_support": ((current_price - support) / current_price) * 100 if current_price > 0 else 0,
                "distance_to_resistance": ((resistance - current_price) / current_price) * 100 if current_price > 0 else 0
            }
        }

    async def _get_gpt4_analysis(self, context: Dict) -> Tuple[str, str, str]:
        """Get GPT-4 analysis with reasoning"""

        prompt = f"""You are an expert cryptocurrency trader analyzing {context['symbol']}. Based on the following comprehensive market data, provide a clear trading recommendation.

CURRENT MARKET DATA:
- Price: ${context['current_price']:,.2f} ({context['price_change_24h']:+.2f}% 24h)
- Market Regime: {context['market_regime']}
- Volume: {context['volume_analysis']['interpretation']} ({context['volume_analysis']['ratio']:.1f}x average)

TECHNICAL INDICATORS:
- RSI: {context['technical_indicators']['rsi']['value']:.1f} ({context['technical_indicators']['rsi']['condition']})
- MACD: {context['technical_indicators']['macd']['crossover']} crossover
- Moving Averages: {context['technical_indicators']['moving_averages']['trend']} trend (SMA20/SMA50)
- Bollinger Bands: Price is {context['technical_indicators']['bollinger_bands']['position']}

KEY LEVELS:
- Support: ${context['price_levels']['support']:,.2f} ({context['price_levels']['distance_to_support']:.1f}% away)
- Resistance: ${context['price_levels']['resistance']:,.2f} ({context['price_levels']['distance_to_resistance']:.1f}% away)

TASK:
1. Analyze all indicators holistically
2. Consider the market regime and volume
3. Provide ONE clear recommendation: BUY, HOLD, or SELL
4. Give a concise reasoning (2-3 sentences max)
5. Assess the current risk level: LOW, MEDIUM, or HIGH

FORMAT YOUR RESPONSE EXACTLY AS:
RECOMMENDATION: [BUY/HOLD/SELL]
REASONING: [Your 2-3 sentence explanation]
RISK: [LOW/MEDIUM/HIGH]

Be decisive and clear. Consider both technical signals and market context."""

        try:
            if self.ai_client.llm_provider == "stub":
                # Fallback analysis
                return self._get_simple_recommendation(context)

            # Use GPT-4 for enhanced analysis
            response = self.ai_client.client.chat.completions.create(
                model=self.gpt4_model,
                messages=[
                    {"role": "system", "content": "You are a professional cryptocurrency trading analyst. Provide clear, actionable recommendations based on technical analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=1000
            )

            # Parse response
            content = response.choices[0].message.content
            lines = content.strip().split('\n')

            recommendation = "HOLD"
            reasoning = "Unable to determine clear direction"
            risk = "MEDIUM"

            for line in lines:
                if line.startswith("RECOMMENDATION:"):
                    recommendation = line.split(":", 1)[1].strip()
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()
                elif line.startswith("RISK:"):
                    risk = line.split(":", 1)[1].strip()

            return recommendation, reasoning, risk

        except Exception as e:
            logger.error(f"GPT-4 analysis error: {e}")
            return self._get_simple_recommendation(context)

    def _get_simple_recommendation(self, context: Dict) -> Tuple[str, str, str]:
        """Simple rule-based recommendation as fallback"""
        rsi = context['technical_indicators']['rsi']['value']
        macd_cross = context['technical_indicators']['macd']['crossover']
        ma_trend = context['technical_indicators']['moving_averages']['trend']

        if rsi < 30 and macd_cross == "Bullish":
            return "BUY", "Oversold with bullish momentum", "LOW"
        elif rsi > 70 and macd_cross == "Bearish":
            return "SELL", "Overbought with bearish momentum", "LOW"
        elif ma_trend == "Bullish" and context['price_change_24h'] > 2:
            return "BUY", "Strong uptrend with positive momentum", "MEDIUM"
        elif ma_trend == "Bearish" and context['price_change_24h'] < -2:
            return "SELL", "Downtrend with negative momentum", "MEDIUM"
        else:
            return "HOLD", "Mixed signals, wait for clearer direction", "MEDIUM"

    def _calculate_enhanced_confidence(
        self,
        current_confidence: float,
        technical_signals: Dict,
        recommendation: str,
        market_regime: str
    ) -> float:
        """Calculate enhanced confidence with AI reasoning boost"""

        enhanced_confidence = current_confidence

        # Base AI reasoning boost (5-15%)
        ai_boost = 10.0

        # Additional boosts based on signal alignment

        # Volume confirmation
        volume_ratio = technical_signals.get("volume_ratio", 1.0)
        if volume_ratio > 2.0:
            ai_boost += 3.0  # High volume confirmation

        # Trend alignment
        if recommendation == "BUY" and market_regime in ["trending_up", "accumulation"]:
            ai_boost += 5.0
        elif recommendation == "SELL" and market_regime in ["trending_down", "distribution"]:
            ai_boost += 5.0
        elif recommendation == "HOLD" and market_regime == "ranging":
            ai_boost += 3.0

        # RSI confirmation
        rsi = technical_signals.get("rsi", 50)
        if (recommendation == "BUY" and rsi < 40) or (recommendation == "SELL" and rsi > 60):
            ai_boost += 2.0

        # Cap the total boost
        ai_boost = min(ai_boost, 20.0)

        # Apply boost
        enhanced_confidence = min(current_confidence + ai_boost, 95.0)

        return round(enhanced_confidence, 1)

    def _get_fallback_recommendation(
        self,
        technical_signals: Dict,
        market_regime: str
    ) -> Tuple[str, str, float, str]:
        """Fallback recommendation when AI analysis fails"""

        # Simple technical-based recommendation
        rsi = technical_signals.get("rsi", 50)

        if rsi < 30:
            return "BUY", "Oversold conditions detected", 75.0, "LOW"
        elif rsi > 70:
            return "SELL", "Overbought conditions detected", 75.0, "LOW"
        else:
            return "HOLD", "No clear directional bias", 70.0, "MEDIUM"

# Singleton instance
_reasoning_engine = None

def get_reasoning_engine(ai_client):
    """Get or create reasoning engine instance"""
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = AIReasoningEngine(ai_client)
    return _reasoning_engine