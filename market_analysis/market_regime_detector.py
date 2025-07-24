#!/usr/bin/env python3
"""
Market Regime Detector
Intelligent classification of market conditions and regimes
"""
import asyncio
import logging
import statistics
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .technical_indicators import TechnicalIndicators
from .market_data_collector import MarketData

logger = logging.getLogger(__name__)

class MarketRegime(Enum):
    """Market regime classifications"""
    BULL_MARKET = "bull_market"           # Strong uptrend, high volume, positive sentiment
    BEAR_MARKET = "bear_market"           # Strong downtrend, selling pressure, negative sentiment
    RANGING_MARKET = "ranging_market"     # Sideways movement, low volatility, neutral sentiment
    VOLATILE_MARKET = "volatile_market"   # High volatility, mixed signals, uncertain sentiment
    ACCUMULATION = "accumulation"         # Sideways with increasing volume
    DISTRIBUTION = "distribution"         # Sideways with decreasing volume

class TrendDirection(Enum):
    """Trend direction classifications"""
    STRONG_UPTREND = "strong_uptrend"     # >2% above 20 SMA, volume confirmation
    UPTREND = "uptrend"                   # 0.5-2% above 20 SMA
    RANGING = "ranging"                   # ±0.5% around 20 SMA, low volatility
    DOWNTREND = "downtrend"               # 0.5-2% below 20 SMA
    STRONG_DOWNTREND = "strong_downtrend" # >2% below 20 SMA, volume confirmation

class VolatilityLevel(Enum):
    """Volatility level classifications"""
    VERY_LOW = "very_low"         # <0.5% ATR
    LOW = "low"                   # 0.5-1.5% ATR
    NORMAL = "normal"             # 1.5-3% ATR
    HIGH = "high"                 # 3-5% ATR
    VERY_HIGH = "very_high"       # >5% ATR

class MomentumState(Enum):
    """Momentum state classifications"""
    VERY_BULLISH = "very_bullish"   # RSI >70, MACD positive, strong volume
    BULLISH = "bullish"             # RSI 50-70, positive momentum
    NEUTRAL = "neutral"             # RSI 40-60, mixed signals
    BEARISH = "bearish"             # RSI 30-50, negative momentum
    VERY_BEARISH = "very_bearish"   # RSI <30, MACD negative, weak volume

@dataclass
class MarketRegimeAnalysis:
    """Comprehensive market regime analysis results"""
    # Primary classifications
    regime: MarketRegime
    trend_direction: TrendDirection
    volatility_level: VolatilityLevel
    momentum_state: MomentumState
    
    # Detailed scores
    trend_strength: float = 0.0      # -100 to 100
    volatility_score: float = 0.0    # 0 to 100
    momentum_score: float = 0.0      # -100 to 100
    volume_strength: float = 0.0     # 0 to 100
    
    # Sentiment analysis
    sentiment_score: float = 50.0    # 0 to 100
    sentiment_label: str = "Neutral"
    sentiment_emoji: str = "⚖️"
    
    # Confidence and metadata
    confidence: float = 0.0          # 0 to 100
    analysis_timestamp: datetime = None
    data_quality: float = 0.0        # 0 to 100
    
    # Additional context
    key_levels: Dict[str, float] = None
    regime_duration: Optional[int] = None  # Days in current regime
    regime_strength: float = 0.0     # How strong the regime signals are

class MarketRegimeDetector:
    """Advanced market regime detection and classification system"""
    
    def __init__(self):
        self.regime_history = {}  # Symbol -> regime history
        self.regime_cache = {}    # Symbol -> cached analysis
        self.cache_ttl = 60       # 1 minute for real-time updates
        
        # Regime detection thresholds
        self.trend_thresholds = {
            "strong_uptrend": 2.0,     # % above SMA
            "uptrend": 0.5,
            "ranging": 0.5,            # % around SMA
            "downtrend": -0.5,
            "strong_downtrend": -2.0
        }
        
        self.volatility_thresholds = {
            "very_low": 0.5,           # % ATR
            "low": 1.5,
            "normal": 3.0,
            "high": 5.0
        }
        
        self.momentum_thresholds = {
            "very_bearish": 30,        # RSI levels
            "bearish": 50,
            "neutral_low": 40,
            "neutral_high": 60,
            "bullish": 70
        }
    
    async def analyze_market_regime(
        self,
        symbol: str,
        market_data: MarketData,
        technical_indicators: TechnicalIndicators,
        sentiment_score: Optional[float] = None
    ) -> MarketRegimeAnalysis:
        """
        Perform comprehensive market regime analysis
        
        Args:
            symbol: Trading symbol
            market_data: Real-time market data
            technical_indicators: Technical analysis results
            sentiment_score: Optional sentiment score (0-100)
            
        Returns:
            MarketRegimeAnalysis with complete classification
        """
        try:
            logger.info(f"🔍 Analyzing market regime for {symbol}")
            
            # Classify individual components
            trend_direction = self._classify_trend_direction(
                market_data.current_price, technical_indicators
            )
            
            volatility_level = self._classify_volatility_level(
                technical_indicators, market_data
            )
            
            momentum_state = self._classify_momentum_state(
                technical_indicators
            )
            
            # Determine overall market regime
            regime = self._determine_market_regime(
                trend_direction, volatility_level, momentum_state, technical_indicators
            )
            
            # Calculate detailed scores
            trend_strength = technical_indicators.trend_strength or 0.0
            volatility_score = technical_indicators.volatility_percentile or 50.0
            momentum_score = technical_indicators.momentum_score or 0.0
            volume_strength = technical_indicators.volume_strength or 50.0
            
            # Analyze sentiment
            sentiment_analysis = self._analyze_sentiment(
                sentiment_score, trend_strength, momentum_score
            )
            
            # Calculate key levels
            key_levels = self._calculate_key_levels(
                market_data.current_price, technical_indicators
            )
            
            # Calculate regime strength
            regime_strength = self._calculate_regime_strength(
                trend_direction, volatility_level, momentum_state,
                trend_strength, volatility_score, momentum_score
            )
            
            # Calculate overall confidence
            confidence = self._calculate_confidence(
                technical_indicators.confidence, market_data.data_quality,
                regime_strength
            )
            
            analysis = MarketRegimeAnalysis(
                # Primary classifications
                regime=regime,
                trend_direction=trend_direction,
                volatility_level=volatility_level,
                momentum_state=momentum_state,
                
                # Detailed scores
                trend_strength=trend_strength,
                volatility_score=volatility_score,
                momentum_score=momentum_score,
                volume_strength=volume_strength,
                
                # Sentiment
                sentiment_score=sentiment_analysis["score"],
                sentiment_label=sentiment_analysis["label"],
                sentiment_emoji=sentiment_analysis["emoji"],
                
                # Metadata
                confidence=confidence,
                analysis_timestamp=datetime.now(),
                data_quality=market_data.data_quality,
                key_levels=key_levels,
                regime_strength=regime_strength
            )
            
            # Store in history for regime duration tracking
            self._update_regime_history(symbol, regime)
            
            logger.info(f"✅ Market regime analyzed for {symbol}: {regime.value} ({confidence:.1f}% confidence)")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing market regime for {symbol}: {e}")
            return MarketRegimeAnalysis(
                regime=MarketRegime.RANGING_MARKET,
                trend_direction=TrendDirection.RANGING,
                volatility_level=VolatilityLevel.NORMAL,
                momentum_state=MomentumState.NEUTRAL,
                analysis_timestamp=datetime.now(),
                confidence=0.0
            )
    
    def _classify_trend_direction(
        self,
        current_price: float,
        indicators: TechnicalIndicators
    ) -> TrendDirection:
        """Classify trend direction based on price and moving averages"""
        if not indicators.sma_20 or current_price <= 0:
            return TrendDirection.RANGING
        
        # Calculate price position relative to SMA 20
        price_vs_sma = ((current_price - indicators.sma_20) / indicators.sma_20) * 100
        
        # Volume confirmation
        volume_confirmation = indicators.volume_strength > 60 if indicators.volume_strength else False
        
        if price_vs_sma > self.trend_thresholds["strong_uptrend"]:
            if volume_confirmation:
                return TrendDirection.STRONG_UPTREND
            else:
                return TrendDirection.UPTREND
        elif price_vs_sma > self.trend_thresholds["uptrend"]:
            return TrendDirection.UPTREND
        elif abs(price_vs_sma) <= self.trend_thresholds["ranging"]:
            return TrendDirection.RANGING
        elif price_vs_sma < self.trend_thresholds["downtrend"]:
            return TrendDirection.DOWNTREND
        elif price_vs_sma < self.trend_thresholds["strong_downtrend"]:
            if volume_confirmation:
                return TrendDirection.STRONG_DOWNTREND
            else:
                return TrendDirection.DOWNTREND
        
        return TrendDirection.RANGING
    
    def _classify_volatility_level(
        self,
        indicators: TechnicalIndicators,
        market_data: MarketData
    ) -> VolatilityLevel:
        """Classify volatility level based on ATR and price movements"""
        if not indicators.atr_14 or market_data.current_price <= 0:
            return VolatilityLevel.NORMAL
        
        # Calculate ATR as percentage of current price
        atr_pct = (indicators.atr_14 / market_data.current_price) * 100
        
        if atr_pct < self.volatility_thresholds["very_low"]:
            return VolatilityLevel.VERY_LOW
        elif atr_pct < self.volatility_thresholds["low"]:
            return VolatilityLevel.LOW
        elif atr_pct < self.volatility_thresholds["normal"]:
            return VolatilityLevel.NORMAL
        elif atr_pct < self.volatility_thresholds["high"]:
            return VolatilityLevel.HIGH
        else:
            return VolatilityLevel.VERY_HIGH
    
    def _classify_momentum_state(
        self,
        indicators: TechnicalIndicators
    ) -> MomentumState:
        """Classify momentum state based on RSI, MACD, and other indicators"""
        rsi = indicators.rsi_14
        macd_hist = indicators.macd_histogram
        volume_strength = indicators.volume_strength or 50
        
        if not rsi:
            return MomentumState.NEUTRAL
        
        # Primary RSI classification
        if rsi > self.momentum_thresholds["bullish"]:
            # Very bullish if MACD and volume confirm
            if macd_hist and macd_hist > 0 and volume_strength > 70:
                return MomentumState.VERY_BULLISH
            else:
                return MomentumState.BULLISH
        elif rsi > self.momentum_thresholds["neutral_high"]:
            return MomentumState.BULLISH
        elif rsi > self.momentum_thresholds["neutral_low"]:
            return MomentumState.NEUTRAL
        elif rsi > self.momentum_thresholds["very_bearish"]:
            return MomentumState.BEARISH
        else:
            # Very bearish if MACD and volume confirm
            if macd_hist and macd_hist < 0 and volume_strength < 30:
                return MomentumState.VERY_BEARISH
            else:
                return MomentumState.BEARISH
    
    def _determine_market_regime(
        self,
        trend: TrendDirection,
        volatility: VolatilityLevel,
        momentum: MomentumState,
        indicators: TechnicalIndicators
    ) -> MarketRegime:
        """Determine overall market regime from component classifications"""
        
        # Strong trends with confirmation
        if trend in [TrendDirection.STRONG_UPTREND, TrendDirection.UPTREND]:
            if momentum in [MomentumState.VERY_BULLISH, MomentumState.BULLISH]:
                return MarketRegime.BULL_MARKET
        
        if trend in [TrendDirection.STRONG_DOWNTREND, TrendDirection.DOWNTREND]:
            if momentum in [MomentumState.VERY_BEARISH, MomentumState.BEARISH]:
                return MarketRegime.BEAR_MARKET
        
        # High volatility conditions
        if volatility in [VolatilityLevel.HIGH, VolatilityLevel.VERY_HIGH]:
            return MarketRegime.VOLATILE_MARKET
        
        # Ranging conditions with volume analysis
        if trend == TrendDirection.RANGING:
            volume_strength = indicators.volume_strength or 50
            
            if volume_strength > 70:
                return MarketRegime.ACCUMULATION
            elif volume_strength < 30:
                return MarketRegime.DISTRIBUTION
            else:
                return MarketRegime.RANGING_MARKET
        
        # Default to ranging for unclear conditions
        return MarketRegime.RANGING_MARKET
    
    def _analyze_sentiment(
        self,
        sentiment_score: Optional[float],
        trend_strength: float,
        momentum_score: float
    ) -> Dict[str, Any]:
        """Analyze sentiment and return score, label, and emoji"""
        
        # Use provided sentiment or calculate from technical indicators
        if sentiment_score is not None:
            score = sentiment_score
        else:
            # Calculate sentiment from technical indicators
            technical_sentiment = 50 + (trend_strength * 0.3) + (momentum_score * 0.2)
            score = max(0, min(100, technical_sentiment))
        
        # Determine label and emoji
        if score >= 80:
            label = "Very Bullish"
            emoji = "🚀"
        elif score >= 60:
            label = "Bullish"
            emoji = "🟢"
        elif score >= 40:
            label = "Neutral"
            emoji = "⚖️"
        elif score >= 20:
            label = "Bearish"
            emoji = "🔴"
        else:
            label = "Very Bearish"
            emoji = "💀"
        
        return {
            "score": score,
            "label": label,
            "emoji": emoji
        }
    
    def _calculate_key_levels(
        self,
        current_price: float,
        indicators: TechnicalIndicators
    ) -> Dict[str, float]:
        """Calculate key support and resistance levels"""
        levels = {}
        
        if current_price and indicators.sma_20:
            levels["sma_20"] = indicators.sma_20
        
        if indicators.sma_50:
            levels["sma_50"] = indicators.sma_50
        
        if indicators.bb_upper and indicators.bb_lower:
            levels["bb_upper"] = indicators.bb_upper
            levels["bb_lower"] = indicators.bb_lower
        
        # Simple support/resistance based on recent price action
        if current_price:
            levels["support"] = current_price * 0.98  # 2% below current
            levels["resistance"] = current_price * 1.02  # 2% above current
        
        return levels
    
    def _calculate_regime_strength(
        self,
        trend: TrendDirection,
        volatility: VolatilityLevel,
        momentum: MomentumState,
        trend_strength: float,
        volatility_score: float,
        momentum_score: float
    ) -> float:
        """Calculate how strong the regime signals are (0-100)"""
        
        strength_factors = []
        
        # Trend strength
        if trend in [TrendDirection.STRONG_UPTREND, TrendDirection.STRONG_DOWNTREND]:
            strength_factors.append(90)
        elif trend in [TrendDirection.UPTREND, TrendDirection.DOWNTREND]:
            strength_factors.append(70)
        else:
            strength_factors.append(30)
        
        # Momentum strength
        if momentum in [MomentumState.VERY_BULLISH, MomentumState.VERY_BEARISH]:
            strength_factors.append(90)
        elif momentum in [MomentumState.BULLISH, MomentumState.BEARISH]:
            strength_factors.append(70)
        else:
            strength_factors.append(40)
        
        # Volatility contribution
        if volatility in [VolatilityLevel.VERY_HIGH, VolatilityLevel.HIGH]:
            strength_factors.append(60)  # High volatility reduces regime clarity
        else:
            strength_factors.append(80)
        
        # Technical score alignment
        alignment_score = 50
        if abs(trend_strength) > 50 and abs(momentum_score) > 50:
            if (trend_strength > 0 and momentum_score > 0) or (trend_strength < 0 and momentum_score < 0):
                alignment_score = 90  # Aligned signals
            else:
                alignment_score = 20  # Conflicting signals
        
        strength_factors.append(alignment_score)
        
        return statistics.mean(strength_factors)
    
    def _calculate_confidence(
        self,
        technical_confidence: float,
        data_quality: float,
        regime_strength: float
    ) -> float:
        """Calculate overall confidence in the regime analysis"""
        
        confidence_factors = [
            technical_confidence * 0.4,  # Technical indicator confidence
            data_quality * 0.3,          # Data quality
            regime_strength * 0.3        # Signal strength
        ]
        
        return sum(confidence_factors)
    
    def _update_regime_history(self, symbol: str, regime: MarketRegime):
        """Update regime history for duration tracking"""
        if symbol not in self.regime_history:
            self.regime_history[symbol] = []
        
        # Add current regime with timestamp
        self.regime_history[symbol].append({
            "regime": regime,
            "timestamp": datetime.now()
        })
        
        # Keep only last 30 days of history
        cutoff = datetime.now() - timedelta(days=30)
        self.regime_history[symbol] = [
            entry for entry in self.regime_history[symbol]
            if entry["timestamp"] > cutoff
        ]

# Global instance
market_regime_detector = MarketRegimeDetector()