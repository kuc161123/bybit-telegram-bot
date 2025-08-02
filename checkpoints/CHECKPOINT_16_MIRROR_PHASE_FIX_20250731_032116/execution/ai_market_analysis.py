"""
AI Market Analysis Module for Enhanced Trading Insights
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import statistics
from dataclasses import dataclass
import json

from clients.bybit_client import bybit_client as global_bybit_client
from clients.ai_client import AIClient, get_ai_client
from utils.cache import async_cache
from config.constants import (
    STATS_WIN_STREAK, STATS_LOSS_STREAK, STATS_TOTAL_TRADES, STATS_TOTAL_PNL,
    AI_INSIGHTS_CACHE_TTL
)

logger = logging.getLogger(__name__)

@dataclass
class MarketInsight:
    """Container for AI market analysis results"""
    symbol: str
    confidence: float  # 0-100
    market_regime: str  # trending_up, trending_down, ranging, volatile
    prediction: str  # bullish, bearish, neutral
    key_levels: Dict[str, float]  # support, resistance, pivot
    risk_factors: List[str]
    opportunities: List[str]
    technical_signals: Dict[str, Any]
    sentiment_score: Optional[float] = None
    ai_analysis: Optional[str] = None
    recommendation: Optional[str] = None  # BUY/HOLD/SELL
    timeframe_analysis: Optional[Dict[str, str]] = None
    risk_assessment: Optional[str] = None  # LOW/MEDIUM/HIGH
    enhanced_confidence: Optional[float] = None  # GPT-4 enhanced confidence

class AIMarketAnalyzer:
    """Advanced AI-powered market analysis system"""

    def __init__(self, bybit_client, ai_client: Optional[AIClient] = None):
        self.bybit_client = bybit_client
        self.ai_client = ai_client
        self.performance_history = []

    @async_cache(ttl_seconds=AI_INSIGHTS_CACHE_TTL)  # 24-hour cache for reduced token usage
    async def analyze_market(self, symbol: str, position_data: Optional[Dict] = None) -> MarketInsight:
        """Perform comprehensive market analysis for a symbol"""
        try:
            # Gather market data
            market_data = await self._gather_market_data(symbol)

            # Technical analysis
            technical_signals = await self._analyze_technicals(symbol, market_data)

            # Market regime detection
            market_regime = self._detect_market_regime(market_data, technical_signals)

            # Calculate key levels
            key_levels = self._calculate_key_levels(market_data)

            # Risk assessment
            risk_factors = self._assess_risks(market_data, technical_signals, market_regime)

            # Opportunity identification
            opportunities = self._identify_opportunities(market_data, technical_signals, market_regime)

            # Multi-timeframe analysis
            timeframe_analysis = self._analyze_multiple_timeframes(market_data, technical_signals)

            # Calculate base confidence first
            base_confidence = self._calculate_confidence(
                technical_signals, market_regime, risk_factors,
                opportunities, position_data
            )

            # Get AI analysis if available
            ai_analysis = None
            recommendation = None
            enhanced_reasoning = None
            risk_assessment = None
            enhanced_confidence = base_confidence

            if self.ai_client and self.ai_client.llm_provider != "stub":
                # Try Phase 4 enhanced reasoning with patterns and historical context
                try:
                    from .ai_reasoning_engine_enhanced import get_enhanced_reasoning_engine
                    enhanced_reasoning_engine = get_enhanced_reasoning_engine(self.ai_client)

                    # Prepare kline data for pattern analysis
                    kline_data = {
                        "5m": market_data.get("klines_5m", []),
                        "15m": market_data.get("klines_15m", []),
                        "1h": market_data.get("klines_1h", [])
                    }

                    # Get enhanced analysis with patterns and historical context
                    recommendation, enhanced_reasoning, enhanced_confidence, risk_assessment = await enhanced_reasoning_engine.analyze_with_enhanced_reasoning(
                        symbol=symbol,
                        market_data=market_data,
                        technical_signals=technical_signals,
                        market_regime=market_regime,
                        current_confidence=base_confidence,
                        kline_data=kline_data,
                        sentiment_data=None  # Could be enhanced with sentiment data
                    )

                    # Log confidence improvement
                    if enhanced_confidence > base_confidence:
                        logger.info(f"🚀 Phase 4 Enhanced AI: confidence boosted from {base_confidence:.1f}% to {enhanced_confidence:.1f}%")

                    ai_analysis = enhanced_reasoning

                except Exception as e:
                    logger.warning(f"Phase 4 enhanced reasoning failed, falling back to standard: {e}")
                    # Fallback to standard reasoning
                    try:
                        from .ai_reasoning_engine import get_reasoning_engine
                        reasoning_engine = get_reasoning_engine(self.ai_client)

                        # Get enhanced analysis
                        recommendation, enhanced_reasoning, enhanced_confidence, risk_assessment = await reasoning_engine.analyze_with_reasoning(
                            symbol, market_data, technical_signals, market_regime,
                            base_confidence  # Pass base confidence
                        )

                        # Log confidence improvement
                        if enhanced_confidence > base_confidence:
                            logger.info(f"AI enhanced confidence from {base_confidence:.1f}% to {enhanced_confidence:.1f}%")

                        ai_analysis = enhanced_reasoning

                    except Exception as e2:
                        logger.warning(f"Standard reasoning also failed: {e2}")
                        ai_analysis, recommendation = await self._get_ai_insights(
                            symbol, market_data, technical_signals, market_regime
                        )
                        enhanced_confidence = base_confidence

            # Use enhanced confidence if available
            confidence = enhanced_confidence

            # Determine prediction
            prediction = self._make_prediction(
                technical_signals, market_regime, confidence, ai_analysis
            )

            # Get sentiment if available
            sentiment_score = await self._get_sentiment_score(symbol)

            return MarketInsight(
                symbol=symbol,
                confidence=confidence,
                market_regime=market_regime,
                prediction=prediction,
                key_levels=key_levels,
                risk_factors=risk_factors,
                opportunities=opportunities,
                technical_signals=technical_signals,
                sentiment_score=sentiment_score,
                ai_analysis=ai_analysis,
                recommendation=recommendation or self._generate_recommendation(
                    prediction, confidence, risk_factors
                ),
                timeframe_analysis=timeframe_analysis,
                risk_assessment=risk_assessment,
                enhanced_confidence=enhanced_confidence if enhanced_confidence != base_confidence else None
            )

        except Exception as e:
            logger.error(f"Error analyzing market for {symbol}: {e}")
            return self._get_fallback_insight(symbol)

    async def _gather_market_data(self, symbol: str) -> Dict:
        """Gather comprehensive market data"""
        try:
            # Get multiple timeframe candles
            loop = asyncio.get_event_loop()

            # Execute Bybit API calls in thread pool
            klines_5m_response = await loop.run_in_executor(
                None,
                lambda: self.bybit_client.get_kline(category="linear", symbol=symbol, interval="5", limit=100)
            )
            klines_15m_response = await loop.run_in_executor(
                None,
                lambda: self.bybit_client.get_kline(category="linear", symbol=symbol, interval="15", limit=50)
            )
            klines_1h_response = await loop.run_in_executor(
                None,
                lambda: self.bybit_client.get_kline(category="linear", symbol=symbol, interval="60", limit=24)
            )

            # Extract kline data
            klines_5m = klines_5m_response.get("result", {}).get("list", []) if klines_5m_response.get("retCode") == 0 else []
            klines_15m = klines_15m_response.get("result", {}).get("list", []) if klines_15m_response.get("retCode") == 0 else []
            klines_1h = klines_1h_response.get("result", {}).get("list", []) if klines_1h_response.get("retCode") == 0 else []

            # Current price and 24h stats
            ticker_response = await loop.run_in_executor(
                None,
                lambda: self.bybit_client.get_tickers(category="linear", symbol=symbol)
            )
            ticker_data = ticker_response.get("result", {}).get("list", [])[0] if ticker_response.get("retCode") == 0 and ticker_response.get("result", {}).get("list") else {}

            # Order book depth
            orderbook_response = await loop.run_in_executor(
                None,
                lambda: self.bybit_client.get_orderbook(category="linear", symbol=symbol, limit=50)
            )
            orderbook_data = orderbook_response.get("result", {}) if orderbook_response.get("retCode") == 0 else {}

            return {
                "klines_5m": klines_5m,
                "klines_15m": klines_15m,
                "klines_1h": klines_1h,
                "ticker": ticker_data,
                "orderbook": orderbook_data,
                "current_price": float(ticker_data.get("lastPrice", 0)),
                "volume_24h": float(ticker_data.get("volume24h", 0)),
                "price_change_24h": float(ticker_data.get("price24hPcnt", 0)) * 100
            }
        except Exception as e:
            logger.error(f"Error gathering market data: {e}")
            return {}

    async def _analyze_technicals(self, symbol: str, market_data: Dict) -> Dict:
        """Perform technical analysis"""
        signals = {}

        try:
            if "klines_5m" in market_data and market_data["klines_5m"]:
                # Extract price data
                # Bybit kline format: [timestamp, open, high, low, close, volume, turnover]
                closes = [float(k[4]) for k in market_data["klines_5m"][-50:]]
                highs = [float(k[2]) for k in market_data["klines_5m"][-50:]]
                lows = [float(k[3]) for k in market_data["klines_5m"][-50:]]
                volumes = [float(k[5]) for k in market_data["klines_5m"][-50:]]

                if len(closes) >= 20:
                    # Moving averages
                    signals["sma_20"] = sum(closes[-20:]) / 20
                    signals["sma_50"] = sum(closes) / len(closes) if len(closes) >= 50 else signals["sma_20"]

                    # RSI
                    signals["rsi"] = self._calculate_rsi(closes, 14)

                    # MACD
                    signals["macd"], signals["macd_signal"] = self._calculate_macd(closes)

                    # Bollinger Bands
                    signals["bb_upper"], signals["bb_middle"], signals["bb_lower"] = self._calculate_bollinger_bands(closes)

                    # Volume analysis
                    signals["volume_sma"] = sum(volumes[-20:]) / 20
                    signals["volume_ratio"] = volumes[-1] / signals["volume_sma"] if signals["volume_sma"] > 0 else 1

                    # Price position
                    current_price = market_data["current_price"]
                    signals["price_position"] = (current_price - signals["bb_lower"]) / (signals["bb_upper"] - signals["bb_lower"]) if signals["bb_upper"] != signals["bb_lower"] else 0.5

                    # Trend strength
                    signals["trend_strength"] = abs(signals["sma_20"] - signals["sma_50"]) / signals["sma_50"] * 100 if signals["sma_50"] > 0 else 0

        except Exception as e:
            logger.error(f"Error in technical analysis: {e}")

        return signals

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(self, prices: List[float]) -> Tuple[float, float]:
        """Calculate MACD and signal line"""
        if len(prices) < 26:
            return 0.0, 0.0

        # Simple EMA calculation
        ema_12 = self._calculate_ema(prices, 12)
        ema_26 = self._calculate_ema(prices, 26)

        macd_line = ema_12 - ema_26

        # Signal line (9-period EMA of MACD)
        macd_values = []
        for i in range(26, len(prices)):
            ema_12_temp = self._calculate_ema(prices[:i+1], 12)
            ema_26_temp = self._calculate_ema(prices[:i+1], 26)
            macd_values.append(ema_12_temp - ema_26_temp)

        signal_line = self._calculate_ema(macd_values, 9) if len(macd_values) >= 9 else macd_line

        return macd_line, signal_line

    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return sum(prices) / len(prices)

        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period

        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            current_price = prices[-1]
            return current_price * 1.02, current_price, current_price * 0.98

        sma = sum(prices[-period:]) / period
        std_dev = statistics.stdev(prices[-period:])

        upper_band = sma + (2 * std_dev)
        lower_band = sma - (2 * std_dev)

        return upper_band, sma, lower_band

    def _detect_market_regime(self, market_data: Dict, technical_signals: Dict) -> str:
        """Detect current market regime"""
        if not technical_signals:
            return "unknown"

        regimes = []

        # Trend detection
        if "sma_20" in technical_signals and "sma_50" in technical_signals:
            if technical_signals["sma_20"] > technical_signals["sma_50"] * 1.01:
                regimes.append("trending_up")
            elif technical_signals["sma_20"] < technical_signals["sma_50"] * 0.99:
                regimes.append("trending_down")
            else:
                regimes.append("ranging")

        # Volatility check
        if "bb_upper" in technical_signals and "bb_lower" in technical_signals:
            bb_width = (technical_signals["bb_upper"] - technical_signals["bb_lower"]) / technical_signals["bb_middle"]
            if bb_width > 0.05:  # 5% band width
                regimes.append("volatile")

        # Momentum check
        if "rsi" in technical_signals:
            if technical_signals["rsi"] > 70:
                regimes.append("overbought")
            elif technical_signals["rsi"] < 30:
                regimes.append("oversold")

        # Determine primary regime
        if "trending_up" in regimes:
            return "trending_up"
        elif "trending_down" in regimes:
            return "trending_down"
        elif "volatile" in regimes:
            return "volatile"
        else:
            return "ranging"

    def _calculate_key_levels(self, market_data: Dict) -> Dict[str, float]:
        """Calculate support and resistance levels"""
        levels = {}

        try:
            if "klines_1h" in market_data and market_data["klines_1h"]:
                highs = [float(k[2]) for k in market_data["klines_1h"]]
                lows = [float(k[3]) for k in market_data["klines_1h"]]

                # Simple pivot points
                last_high = highs[-1]
                last_low = lows[-1]
                last_close = float(market_data["klines_1h"][-1][4])

                pivot = (last_high + last_low + last_close) / 3

                levels["pivot"] = pivot
                levels["resistance_1"] = 2 * pivot - last_low
                levels["support_1"] = 2 * pivot - last_high
                levels["resistance_2"] = pivot + (last_high - last_low)
                levels["support_2"] = pivot - (last_high - last_low)

                # Recent high/low
                levels["daily_high"] = max(highs[-24:]) if len(highs) >= 24 else last_high
                levels["daily_low"] = min(lows[-24:]) if len(lows) >= 24 else last_low

        except Exception as e:
            logger.error(f"Error calculating key levels: {e}")
            current_price = market_data.get("current_price", 0)
            levels = {
                "pivot": current_price,
                "resistance_1": current_price * 1.01,
                "support_1": current_price * 0.99
            }

        return levels

    def _assess_risks(self, market_data: Dict, technical_signals: Dict, market_regime: str) -> List[str]:
        """Identify current market risks"""
        risks = []

        # RSI extremes
        if technical_signals.get("rsi", 50) > 80:
            risks.append("Extreme overbought conditions (RSI > 80)")
        elif technical_signals.get("rsi", 50) < 20:
            risks.append("Extreme oversold conditions (RSI < 20)")

        # Volatility risks
        if market_regime == "volatile":
            risks.append("High market volatility detected")

        # Volume concerns
        if technical_signals.get("volume_ratio", 1) < 0.5:
            risks.append("Low volume - potential false signals")
        elif technical_signals.get("volume_ratio", 1) > 3:
            risks.append("Unusual high volume spike")

        # Trend reversal risk
        if technical_signals.get("macd", 0) < technical_signals.get("macd_signal", 0) and market_regime == "trending_up":
            risks.append("MACD bearish crossover in uptrend")
        elif technical_signals.get("macd", 0) > technical_signals.get("macd_signal", 0) and market_regime == "trending_down":
            risks.append("MACD bullish crossover in downtrend")

        # Price extension
        if technical_signals.get("price_position", 0.5) > 0.95:
            risks.append("Price near upper Bollinger Band")
        elif technical_signals.get("price_position", 0.5) < 0.05:
            risks.append("Price near lower Bollinger Band")

        return risks

    def _identify_opportunities(self, market_data: Dict, technical_signals: Dict, market_regime: str) -> List[str]:
        """Identify trading opportunities"""
        opportunities = []

        # Trend continuation
        if market_regime == "trending_up" and technical_signals.get("rsi", 50) < 70:
            opportunities.append("Uptrend with room to run (RSI < 70)")
        elif market_regime == "trending_down" and technical_signals.get("rsi", 50) > 30:
            opportunities.append("Downtrend continuation potential (RSI > 30)")

        # Mean reversion
        if market_regime == "ranging":
            if technical_signals.get("price_position", 0.5) < 0.2:
                opportunities.append("Near range bottom - bounce potential")
            elif technical_signals.get("price_position", 0.5) > 0.8:
                opportunities.append("Near range top - reversal potential")

        # MACD signals
        if technical_signals.get("macd", 0) > technical_signals.get("macd_signal", 0):
            opportunities.append("MACD bullish crossover")

        # Volume confirmation
        if technical_signals.get("volume_ratio", 1) > 1.5 and market_regime in ["trending_up", "trending_down"]:
            opportunities.append("Strong volume supporting trend")

        # Oversold/Overbought reversals
        if technical_signals.get("rsi", 50) < 30 and market_regime != "trending_down":
            opportunities.append("RSI oversold - potential reversal")
        elif technical_signals.get("rsi", 50) > 70 and market_regime != "trending_up":
            opportunities.append("RSI overbought - potential reversal")

        return opportunities

    async def _get_ai_insights(self, symbol: str, market_data: Dict,
                              technical_signals: Dict, market_regime: str) -> Tuple[Optional[str], Optional[str]]:
        """Get AI-powered market insights"""
        try:
            # Prepare context for AI
            context = {
                "symbol": symbol,
                "current_price": market_data.get("current_price", 0),
                "price_change_24h": market_data.get("price_change_24h", 0),
                "volume_24h": market_data.get("volume_24h", 0),
                "market_regime": market_regime,
                "rsi": technical_signals.get("rsi", 50),
                "macd_signal": "bullish" if technical_signals.get("macd", 0) > technical_signals.get("macd_signal", 0) else "bearish",
                "price_vs_sma20": "above" if market_data.get("current_price", 0) > technical_signals.get("sma_20", 0) else "below"
            }

            prompt = f"""Analyze this cryptocurrency market data and provide trading insights:

Symbol: {symbol}
Current Price: ${context['current_price']:.2f}
24h Change: {context['price_change_24h']:.2f}%
Market Regime: {context['market_regime']}
RSI: {context['rsi']:.1f}
MACD: {context['macd_signal']}
Price vs SMA20: {context['price_vs_sma20']}

Provide:
1. Market outlook (1-2 sentences)
2. Key insight or pattern detected
3. Specific trading recommendation
4. Risk level assessment

Be concise and actionable."""

            response = await self.ai_client.analyze_market(prompt)

            if response and "error" not in response.lower():
                # Extract recommendation
                lines = response.split('\n')
                recommendation = None
                for line in lines:
                    if 'recommendation' in line.lower():
                        recommendation = line.split(':', 1)[1].strip() if ':' in line else line
                        break

                return response, recommendation

        except Exception as e:
            logger.error(f"Error getting AI insights: {e}")

        return None, None

    def _analyze_multiple_timeframes(self, market_data: Dict, technical_signals: Dict) -> Dict[str, str]:
        """Analyze multiple timeframes for confluence"""
        analysis = {}

        try:
            # 5-minute timeframe
            if "klines_5m" in market_data and len(market_data["klines_5m"]) > 0:
                recent_5m = market_data["klines_5m"][-1]
                analysis["5m"] = "Bullish" if float(recent_5m[4]) > float(recent_5m[1]) else "Bearish"

            # 15-minute timeframe
            if "klines_15m" in market_data and len(market_data["klines_15m"]) > 0:
                recent_15m = market_data["klines_15m"][-1]
                analysis["15m"] = "Bullish" if float(recent_15m[4]) > float(recent_15m[1]) else "Bearish"

            # 1-hour timeframe
            if "klines_1h" in market_data and len(market_data["klines_1h"]) > 0:
                recent_1h = market_data["klines_1h"][-1]
                analysis["1h"] = "Bullish" if float(recent_1h[4]) > float(recent_1h[1]) else "Bearish"

            # Overall bias
            bullish_count = sum(1 for v in analysis.values() if v == "Bullish")
            bearish_count = sum(1 for v in analysis.values() if v == "Bearish")

            if bullish_count > bearish_count:
                analysis["overall"] = "Bullish alignment"
            elif bearish_count > bullish_count:
                analysis["overall"] = "Bearish alignment"
            else:
                analysis["overall"] = "Mixed signals"

        except Exception as e:
            logger.error(f"Error in timeframe analysis: {e}")

        return analysis

    def _calculate_confidence(self, technical_signals: Dict, market_regime: str,
                            risk_factors: List[str], opportunities: List[str],
                            position_data: Optional[Dict] = None) -> float:
        """Calculate overall confidence score"""
        confidence = 50.0  # Base confidence

        # Technical signal alignment
        if technical_signals:
            # RSI confirmation
            rsi = technical_signals.get("rsi", 50)
            if 40 <= rsi <= 60:
                confidence += 5  # Neutral zone
            elif (rsi > 60 and market_regime == "trending_up") or (rsi < 40 and market_regime == "trending_down"):
                confidence += 10  # Trend confirmation
            else:
                confidence -= 5  # Divergence

            # MACD confirmation
            if technical_signals.get("macd", 0) > technical_signals.get("macd_signal", 0):
                if market_regime == "trending_up":
                    confidence += 10
                else:
                    confidence += 5
            elif market_regime == "trending_down":
                confidence += 10

            # Volume confirmation
            volume_ratio = technical_signals.get("volume_ratio", 1)
            if 0.8 <= volume_ratio <= 2.0:
                confidence += 5  # Normal volume
            elif volume_ratio > 2.0:
                confidence += 10  # High volume confirmation
            else:
                confidence -= 5  # Low volume warning

        # Risk/Opportunity balance
        risk_score = len(risk_factors) * 5
        opportunity_score = len(opportunities) * 7

        confidence += min(opportunity_score, 20) - min(risk_score, 20)

        # Position performance adjustment
        if position_data:
            pnl_percentage = position_data.get("pnl_percentage", 0)
            if pnl_percentage > 5:
                confidence += 10  # Winning position
            elif pnl_percentage < -5:
                confidence -= 10  # Losing position

        # Market regime adjustment
        if market_regime in ["trending_up", "trending_down"]:
            confidence += 5  # Clear trend
        elif market_regime == "volatile":
            confidence -= 10  # High uncertainty

        # Ensure confidence is within bounds
        return max(0, min(100, confidence))

    def _make_prediction(self, technical_signals: Dict, market_regime: str,
                        confidence: float, ai_analysis: Optional[str]) -> str:
        """Make market prediction based on all factors"""
        # Check AI analysis first
        if ai_analysis:
            ai_lower = ai_analysis.lower()
            if any(word in ai_lower for word in ["bullish", "buy", "long", "upward"]):
                return "bullish"
            elif any(word in ai_lower for word in ["bearish", "sell", "short", "downward"]):
                return "bearish"

        # Technical-based prediction
        bullish_signals = 0
        bearish_signals = 0

        # Market regime
        if market_regime == "trending_up":
            bullish_signals += 2
        elif market_regime == "trending_down":
            bearish_signals += 2

        # RSI
        rsi = technical_signals.get("rsi", 50)
        if rsi > 60:
            bearish_signals += 1
        elif rsi < 40:
            bullish_signals += 1

        # MACD
        if technical_signals.get("macd", 0) > technical_signals.get("macd_signal", 0):
            bullish_signals += 1
        else:
            bearish_signals += 1

        # Price vs MA
        if technical_signals.get("sma_20", 0) > 0:
            current_price = technical_signals.get("current_price", technical_signals["sma_20"])
            if current_price > technical_signals["sma_20"]:
                bullish_signals += 1
            else:
                bearish_signals += 1

        # Make decision
        if bullish_signals > bearish_signals:
            return "bullish"
        elif bearish_signals > bullish_signals:
            return "bearish"
        else:
            return "neutral"

    async def _get_sentiment_score(self, symbol: str) -> Optional[float]:
        """Get social sentiment score if available"""
        try:
            # Integrate with social sentiment module
            from social_media.integration import SocialMediaIntegration

            social_integration = SocialMediaIntegration()
            if social_integration.is_initialized:
                # Get sentiment for the base symbol (remove USDT)
                base_symbol = symbol.replace('USDT', '')
                sentiment_data = await social_integration.get_symbol_sentiment(base_symbol)

                if sentiment_data and 'overall_score' in sentiment_data:
                    return float(sentiment_data['overall_score'])

            return None
        except Exception as e:
            logger.error(f"Error getting sentiment score: {e}")
            return None

    def _generate_recommendation(self, prediction: str, confidence: float, risk_factors: List[str]) -> str:
        """Generate trading recommendation"""
        risk_level = "high" if len(risk_factors) >= 3 else "moderate" if len(risk_factors) >= 1 else "low"

        if confidence >= 80:
            strength = "Strong"
        elif confidence >= 60:
            strength = "Moderate"
        else:
            strength = "Weak"

        if prediction == "bullish":
            if confidence >= 70 and risk_level == "low":
                return f"{strength} BUY signal - Consider long position"
            elif confidence >= 60:
                return f"{strength} bullish bias - Wait for confirmation"
            else:
                return "Weak bullish signal - Exercise caution"
        elif prediction == "bearish":
            if confidence >= 70 and risk_level == "low":
                return f"{strength} SELL signal - Consider short position"
            elif confidence >= 60:
                return f"{strength} bearish bias - Wait for confirmation"
            else:
                return "Weak bearish signal - Exercise caution"
        else:
            return f"Neutral market - Wait for clearer signals ({risk_level} risk)"

    def _get_fallback_insight(self, symbol: str) -> MarketInsight:
        """Return basic insight when analysis fails"""
        return MarketInsight(
            symbol=symbol,
            confidence=50.0,
            market_regime="unknown",
            prediction="neutral",
            key_levels={},
            risk_factors=["Analysis data unavailable"],
            opportunities=[],
            technical_signals={},
            recommendation="Unable to analyze - check connection"
        )

    async def get_portfolio_insights(self, positions: List[Dict]) -> List[MarketInsight]:
        """Get insights for multiple positions"""
        tasks = []
        for position in positions[:5]:  # Limit to top 5 positions
            symbol = position.get("symbol", "")
            if symbol:
                tasks.append(self.analyze_market(symbol, position))

        if tasks:
            insights = await asyncio.gather(*tasks, return_exceptions=True)
            return [i for i in insights if isinstance(i, MarketInsight)]

        return []

# Helper function for dashboard integration
async def get_ai_market_insights(symbol: str, stats_data: Dict) -> Dict:
    """Get AI market insights for dashboard display"""
    try:
        from clients.bybit_client import bybit_client
        from clients.ai_client import get_ai_client

        ai_client = get_ai_client()

        analyzer = AIMarketAnalyzer(bybit_client, ai_client)

        # Get position data if available
        position_data = None
        try:
            from clients.bybit_helpers import get_all_positions
            positions = await get_all_positions()
            for pos in positions:
                if pos.get("symbol") == symbol:
                    position_data = pos
                    break
        except:
            pass

        # Analyze market
        insight = await analyzer.analyze_market(symbol, position_data)

        # Calculate trading metrics
        win_rate = stats_data.get('overall_win_rate', 50)
        win_streak = stats_data.get(STATS_WIN_STREAK, 0)
        loss_streak = stats_data.get(STATS_LOSS_STREAK, 0)
        total_trades = stats_data.get(STATS_TOTAL_TRADES, 0)

        # Determine momentum
        momentum_status = "🔥 Hot" if win_streak >= 3 else "❄️ Cold" if loss_streak >= 3 else "⚖️ Neutral"

        # Determine trend
        if insight.market_regime == "trending_up":
            trend = "▲ Uptrend"
        elif insight.market_regime == "trending_down":
            trend = "▼ Downtrend"
        else:
            trend = "↔️ Ranging"

        # Format for dashboard
        return {
            # Basic metrics
            'win_rate': win_rate,
            'total_trades': total_trades,
            'win_streak': win_streak,
            'loss_streak': loss_streak,
            'momentum': momentum_status,
            'trend': trend,
            'confidence': insight.confidence,

            # AI insights
            'market_outlook': insight.prediction.upper(),
            'signal_strength': "STRONG" if insight.confidence >= 70 else "MODERATE" if insight.confidence >= 50 else "WEAK",
            'short_term_prediction': insight.recommendation or f"Market {insight.market_regime.replace('_', ' ')}",
            'key_risks': insight.risk_factors[:2] if insight.risk_factors else ["Standard market risk"],
            'recommended_actions': insight.opportunities[:2] if insight.opportunities else ["Monitor market conditions"],

            # Advanced data
            'market_data': {
                'price_change_24h': 0,  # Would need ticker data
                'volume': 0
            },
            'technical': {
                'trend': insight.market_regime.replace('_', ' ').title(),
                'volatility': 0,
                'momentum': (insight.technical_signals.get('rsi', 50) - 50) / 5  # Convert RSI to momentum
            },
            'sentiment': {
                'score': insight.sentiment_score or 50,
                'trend': 'Neutral'
            },
            'performance_metrics': {
                'profit_factor': calculate_profit_factor(stats_data),
                'expectancy': float(stats_data.get(STATS_TOTAL_PNL, 0)) / total_trades if total_trades > 0 else 0
            },
            'ai_insights': insight.ai_analysis if insight.ai_analysis else None
        }

    except Exception as e:
        logger.error(f"Error getting AI market insights: {e}")
        # Return basic fallback data
        win_rate = stats_data.get('overall_win_rate', 50)
        win_streak = stats_data.get(STATS_WIN_STREAK, 0)
        loss_streak = stats_data.get(STATS_LOSS_STREAK, 0)

        return {
            'win_rate': win_rate,
            'total_trades': stats_data.get(STATS_TOTAL_TRADES, 0),
            'win_streak': win_streak,
            'loss_streak': loss_streak,
            'momentum': "🔥 Hot" if win_streak >= 3 else "❄️ Cold" if loss_streak >= 3 else "⚖️ Neutral",
            'trend': "↔️ Ranging",
            'confidence': 50,
            'market_outlook': 'ANALYZING',
            'signal_strength': 'WEAK',
            'short_term_prediction': f'Win rate: {win_rate:.1f}%',
            'key_risks': ['Market volatility'],
            'recommended_actions': ['Trade with caution'],
            'error': True
        }

def calculate_profit_factor(stats_data: Dict) -> float:
    """Calculate profit factor from stats"""
    total_wins_pnl = float(stats_data.get('stats_total_wins_pnl', 0))
    total_losses_pnl = abs(float(stats_data.get('stats_total_losses_pnl', 0)))

    if total_losses_pnl > 0:
        return total_wins_pnl / total_losses_pnl
    elif total_wins_pnl > 0:
        return 999.99
    return 0.0