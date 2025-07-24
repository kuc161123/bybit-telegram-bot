#!/usr/bin/env python3
"""
Enhanced Market Regime Detector with Adaptive Thresholds
Intelligent classification of market conditions with dynamic adaptation
"""
import asyncio
import logging
import statistics
import numpy as np
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

from .technical_indicators_enhanced import EnhancedTechnicalIndicators
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
    BREAKOUT = "breakout"                # NEW: Breaking out of range with volume
    BREAKDOWN = "breakdown"              # NEW: Breaking down from range with volume

class TrendDirection(Enum):
    """Trend direction classifications"""
    STRONG_UPTREND = "strong_uptrend"     # Dynamic threshold based on volatility
    UPTREND = "uptrend"                   
    RANGING = "ranging"                   
    DOWNTREND = "downtrend"               
    STRONG_DOWNTREND = "strong_downtrend"

class VolatilityLevel(Enum):
    """Volatility level classifications"""
    VERY_LOW = "very_low"         
    LOW = "low"                   
    NORMAL = "normal"             
    HIGH = "high"                 
    VERY_HIGH = "very_high"       
    EXTREME = "extreme"           # NEW: Extreme volatility events

class MomentumState(Enum):
    """Momentum state classifications"""
    VERY_BULLISH = "very_bullish"   
    BULLISH = "bullish"             
    NEUTRAL = "neutral"             
    BEARISH = "bearish"             
    VERY_BEARISH = "very_bearish"   

@dataclass
class AdaptiveThresholds:
    """Dynamic thresholds that adapt to market conditions"""
    # Trend thresholds (% from moving average)
    strong_uptrend: float
    uptrend: float
    ranging: float
    downtrend: float
    strong_downtrend: float
    
    # Volatility thresholds (% ATR)
    very_low_vol: float
    low_vol: float
    normal_vol: float
    high_vol: float
    very_high_vol: float
    extreme_vol: float
    
    # Momentum thresholds (RSI levels)
    very_bearish_rsi: float
    bearish_rsi: float
    neutral_low_rsi: float
    neutral_high_rsi: float
    bullish_rsi: float
    very_bullish_rsi: float
    
    # Volume thresholds (ratio)
    low_volume: float
    normal_volume_low: float
    normal_volume_high: float
    high_volume: float
    extreme_volume: float
    
    # Confidence in thresholds
    confidence: float
    last_updated: datetime

@dataclass
class MarketMicrostructure:
    """Market microstructure analysis"""
    bid_ask_spread: Optional[float] = None
    order_book_imbalance: Optional[float] = None
    trade_flow_ratio: Optional[float] = None  # Buy volume / Total volume
    liquidity_score: Optional[float] = None   # 0-100
    market_depth_ratio: Optional[float] = None # Bid depth / Ask depth

@dataclass
class EnhancedMarketRegimeAnalysis:
    """Enhanced market regime analysis with adaptive features"""
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
    
    # Multi-timeframe analysis
    timeframe_alignment: Dict[str, str] = None  # 5m, 15m, 1h, 4h, 1d trends
    timeframe_confluence: float = 0.0  # 0-100 alignment score
    
    # Market microstructure
    microstructure: MarketMicrostructure = None
    
    # Sentiment analysis
    sentiment_score: float = 50.0    
    sentiment_label: str = "Neutral"
    sentiment_emoji: str = "⚖️"
    
    # Confidence and metadata
    confidence: float = 0.0          
    analysis_timestamp: datetime = None
    data_quality: float = 0.0        
    
    # Additional context
    key_levels: Dict[str, float] = None
    regime_duration: Optional[int] = None  
    regime_strength: float = 0.0     
    regime_transition_probability: float = 0.0  # NEW: Probability of regime change
    
    # Adaptive thresholds used
    thresholds_used: AdaptiveThresholds = None

class EnhancedMarketRegimeDetector:
    """Enhanced market regime detection with adaptive thresholds and multi-timeframe analysis"""
    
    def __init__(self):
        self.regime_history = {}  # Symbol -> regime history
        self.regime_cache = {}    # Symbol -> cached analysis
        self.cache_ttl = 300      # 5 minutes
        
        # Adaptive threshold tracking
        self.volatility_history = {}  # Symbol -> deque of historical volatility
        self.trend_history = {}       # Symbol -> deque of historical trends
        self.volume_history = {}      # Symbol -> deque of historical volumes
        
        # Base thresholds (will be adapted)
        self.base_trend_thresholds = {
            "strong_uptrend": 2.0,
            "uptrend": 0.5,
            "ranging": 0.5,
            "downtrend": -0.5,
            "strong_downtrend": -2.0
        }
        
        self.base_volatility_thresholds = {
            "very_low": 0.5,
            "low": 1.5,
            "normal": 3.0,
            "high": 5.0,
            "very_high": 8.0,
            "extreme": 12.0
        }
        
        self.base_momentum_thresholds = {
            "very_bearish": 20,
            "bearish": 40,
            "neutral_low": 45,
            "neutral_high": 55,
            "bullish": 60,
            "very_bullish": 80
        }
    
    async def analyze_market_regime(
        self,
        symbol: str,
        market_data: MarketData,
        technical_indicators: EnhancedTechnicalIndicators,
        sentiment_score: Optional[float] = None,
        multi_timeframe_data: Optional[Dict[str, Any]] = None,
        orderbook_data: Optional[Dict] = None
    ) -> EnhancedMarketRegimeAnalysis:
        """
        Perform enhanced market regime analysis with adaptive thresholds
        """
        try:
            logger.info(f"🔍 Analyzing enhanced market regime for {symbol}")
            
            # Update historical data for adaptation
            self._update_historical_data(symbol, market_data, technical_indicators)
            
            # Calculate adaptive thresholds
            adaptive_thresholds = self._calculate_adaptive_thresholds(
                symbol, technical_indicators, market_data
            )
            
            # Perform multi-timeframe analysis if data provided
            timeframe_analysis = None
            timeframe_confluence = 0.0
            
            if multi_timeframe_data:
                timeframe_analysis, timeframe_confluence = self._analyze_multiple_timeframes(
                    multi_timeframe_data, adaptive_thresholds
                )
            
            # Calculate market microstructure if orderbook provided
            microstructure = None
            if orderbook_data:
                microstructure = self._analyze_market_microstructure(
                    orderbook_data, market_data
                )
            
            # Classify components with adaptive thresholds
            trend_direction = self._classify_trend_direction_adaptive(
                market_data.current_price, technical_indicators, adaptive_thresholds
            )
            
            volatility_level = self._classify_volatility_level_adaptive(
                technical_indicators, market_data, adaptive_thresholds
            )
            
            momentum_state = self._classify_momentum_state_adaptive(
                technical_indicators, adaptive_thresholds
            )
            
            # Enhanced regime determination
            regime = self._determine_market_regime_enhanced(
                trend_direction, volatility_level, momentum_state, 
                technical_indicators, timeframe_confluence, microstructure
            )
            
            # Calculate transition probability
            transition_probability = self._calculate_regime_transition_probability(
                symbol, regime, trend_direction, volatility_level, momentum_state
            )
            
            # Calculate detailed scores
            trend_strength = technical_indicators.trend_strength or 0.0
            volatility_score = technical_indicators.volatility_percentile or 50.0
            momentum_score = technical_indicators.momentum_score or 0.0
            volume_strength = technical_indicators.volume_strength or 50.0
            
            # Enhanced sentiment analysis
            sentiment_analysis = self._analyze_sentiment_enhanced(
                sentiment_score, trend_strength, momentum_score, timeframe_confluence
            )
            
            # Calculate enhanced key levels
            key_levels = self._calculate_enhanced_key_levels(
                market_data.current_price, technical_indicators
            )
            
            # Calculate regime strength with all factors
            regime_strength = self._calculate_regime_strength_enhanced(
                trend_direction, volatility_level, momentum_state,
                trend_strength, volatility_score, momentum_score,
                timeframe_confluence, microstructure
            )
            
            # Calculate overall confidence
            confidence = self._calculate_confidence_enhanced(
                technical_indicators.confidence, market_data.data_quality,
                regime_strength, timeframe_confluence, adaptive_thresholds.confidence
            )
            
            analysis = EnhancedMarketRegimeAnalysis(
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
                
                # Multi-timeframe
                timeframe_alignment=timeframe_analysis,
                timeframe_confluence=timeframe_confluence,
                
                # Microstructure
                microstructure=microstructure,
                
                # Sentiment
                sentiment_score=sentiment_analysis["score"],
                sentiment_label=sentiment_analysis["label"],
                sentiment_emoji=sentiment_analysis["emoji"],
                
                # Metadata
                confidence=confidence,
                analysis_timestamp=datetime.now(),
                data_quality=market_data.data_quality,
                key_levels=key_levels,
                regime_strength=regime_strength,
                regime_transition_probability=transition_probability,
                thresholds_used=adaptive_thresholds
            )
            
            # Store in history for regime duration tracking
            self._update_regime_history(symbol, regime)
            
            logger.info(f"✅ Enhanced market regime analyzed for {symbol}: {regime.value} "
                       f"({confidence:.1f}% confidence, {transition_probability:.1f}% transition probability)")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Error analyzing enhanced market regime for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return self._get_fallback_analysis(symbol)
    
    def _update_historical_data(self, symbol: str, market_data: MarketData, 
                               indicators: EnhancedTechnicalIndicators):
        """Update historical data for adaptive threshold calculation"""
        # Initialize if needed
        if symbol not in self.volatility_history:
            self.volatility_history[symbol] = deque(maxlen=100)
            self.trend_history[symbol] = deque(maxlen=100)
            self.volume_history[symbol] = deque(maxlen=100)
        
        # Update volatility history
        if indicators.atr_14 and market_data.current_price > 0:
            vol_pct = (indicators.atr_14 / market_data.current_price) * 100
            self.volatility_history[symbol].append(vol_pct)
        
        # Update trend history
        if indicators.trend_strength is not None:
            self.trend_history[symbol].append(indicators.trend_strength)
        
        # Update volume history
        if indicators.volume_ratio is not None:
            self.volume_history[symbol].append(indicators.volume_ratio)
    
    def _calculate_adaptive_thresholds(self, symbol: str, 
                                     indicators: EnhancedTechnicalIndicators,
                                     market_data: MarketData) -> AdaptiveThresholds:
        """Calculate adaptive thresholds based on recent market behavior"""
        
        # Get historical data
        vol_history = list(self.volatility_history.get(symbol, []))
        trend_history = list(self.trend_history.get(symbol, []))
        volume_history = list(self.volume_history.get(symbol, []))
        
        # Calculate adaptive volatility thresholds
        if len(vol_history) >= 20:
            vol_percentiles = np.percentile(vol_history, [10, 30, 50, 70, 90, 98])
            vol_thresholds = {
                "very_low": vol_percentiles[0],
                "low": vol_percentiles[1],
                "normal": vol_percentiles[2],
                "high": vol_percentiles[3],
                "very_high": vol_percentiles[4],
                "extreme": vol_percentiles[5]
            }
        else:
            # Use base thresholds with current volatility adjustment
            current_vol = (indicators.atr_14 / market_data.current_price * 100) if indicators.atr_14 else 3.0
            adjustment = current_vol / 3.0  # Normalize to "normal" volatility
            vol_thresholds = {k: v * adjustment for k, v in self.base_volatility_thresholds.items()}
        
        # Calculate adaptive trend thresholds
        if len(trend_history) >= 20:
            # Use standard deviation of trend strength
            trend_std = np.std(trend_history)
            trend_mean = np.mean(trend_history)
            
            # Adaptive thresholds based on distribution
            trend_thresholds = {
                "strong_uptrend": max(2.0, trend_mean + 2 * trend_std),
                "uptrend": max(0.5, trend_mean + 0.5 * trend_std),
                "ranging": trend_std * 0.5,
                "downtrend": min(-0.5, trend_mean - 0.5 * trend_std),
                "strong_downtrend": min(-2.0, trend_mean - 2 * trend_std)
            }
        else:
            # Use base thresholds with volatility adjustment
            vol_multiplier = 1 + (indicators.volatility_percentile - 50) / 100 if indicators.volatility_percentile else 1
            trend_thresholds = {k: v * vol_multiplier for k, v in self.base_trend_thresholds.items()}
        
        # Calculate adaptive momentum thresholds
        # RSI tends to stay in certain ranges during trending vs ranging markets
        if indicators.trend_strength and abs(indicators.trend_strength) > 50:
            # Trending market - adjust RSI thresholds
            if indicators.trend_strength > 0:
                # Uptrend - RSI tends to stay higher
                momentum_thresholds = {
                    "very_bearish": 25,
                    "bearish": 45,
                    "neutral_low": 50,
                    "neutral_high": 60,
                    "bullish": 65,
                    "very_bullish": 75
                }
            else:
                # Downtrend - RSI tends to stay lower
                momentum_thresholds = {
                    "very_bearish": 15,
                    "bearish": 35,
                    "neutral_low": 40,
                    "neutral_high": 50,
                    "bullish": 55,
                    "very_bullish": 70
                }
        else:
            # Ranging market - use standard thresholds
            momentum_thresholds = self.base_momentum_thresholds.copy()
        
        # Calculate adaptive volume thresholds
        if len(volume_history) >= 20:
            vol_percentiles = np.percentile(volume_history, [20, 40, 60, 80, 95])
            volume_thresholds = {
                "low_volume": vol_percentiles[0],
                "normal_volume_low": vol_percentiles[1],
                "normal_volume_high": vol_percentiles[2],
                "high_volume": vol_percentiles[3],
                "extreme_volume": vol_percentiles[4]
            }
        else:
            volume_thresholds = {
                "low_volume": 0.5,
                "normal_volume_low": 0.8,
                "normal_volume_high": 1.2,
                "high_volume": 2.0,
                "extreme_volume": 3.0
            }
        
        # Calculate confidence in adaptive thresholds
        data_points = min(len(vol_history), len(trend_history), len(volume_history))
        confidence = min(100, data_points)  # 100% confidence with 100+ data points
        
        return AdaptiveThresholds(
            # Trend
            strong_uptrend=trend_thresholds["strong_uptrend"],
            uptrend=trend_thresholds["uptrend"],
            ranging=trend_thresholds["ranging"],
            downtrend=trend_thresholds["downtrend"],
            strong_downtrend=trend_thresholds["strong_downtrend"],
            
            # Volatility
            very_low_vol=vol_thresholds["very_low"],
            low_vol=vol_thresholds["low"],
            normal_vol=vol_thresholds["normal"],
            high_vol=vol_thresholds["high"],
            very_high_vol=vol_thresholds["very_high"],
            extreme_vol=vol_thresholds["extreme"],
            
            # Momentum
            very_bearish_rsi=momentum_thresholds["very_bearish"],
            bearish_rsi=momentum_thresholds["bearish"],
            neutral_low_rsi=momentum_thresholds["neutral_low"],
            neutral_high_rsi=momentum_thresholds["neutral_high"],
            bullish_rsi=momentum_thresholds["bullish"],
            very_bullish_rsi=momentum_thresholds["very_bullish"],
            
            # Volume
            low_volume=volume_thresholds["low_volume"],
            normal_volume_low=volume_thresholds["normal_volume_low"],
            normal_volume_high=volume_thresholds["normal_volume_high"],
            high_volume=volume_thresholds["high_volume"],
            extreme_volume=volume_thresholds["extreme_volume"],
            
            confidence=confidence,
            last_updated=datetime.now()
        )
    
    def _analyze_multiple_timeframes(self, multi_timeframe_data: Dict[str, Any],
                                   thresholds: AdaptiveThresholds) -> Tuple[Dict[str, str], float]:
        """Analyze multiple timeframes for confluence"""
        timeframe_trends = {}
        
        for timeframe, data in multi_timeframe_data.items():
            if "close" in data and "sma_20" in data:
                price = data["close"]
                sma = data["sma_20"]
                
                if price and sma:
                    price_vs_sma = ((price - sma) / sma) * 100
                    
                    # Classify trend for this timeframe
                    if price_vs_sma > thresholds.strong_uptrend:
                        trend = "Strong Up"
                    elif price_vs_sma > thresholds.uptrend:
                        trend = "Up"
                    elif abs(price_vs_sma) <= thresholds.ranging:
                        trend = "Ranging"
                    elif price_vs_sma < thresholds.downtrend:
                        trend = "Down"
                    else:
                        trend = "Strong Down"
                    
                    timeframe_trends[timeframe] = trend
        
        # Calculate confluence score
        if not timeframe_trends:
            return {}, 0.0
        
        # Check alignment
        trend_values = list(timeframe_trends.values())
        up_count = sum(1 for t in trend_values if "Up" in t)
        down_count = sum(1 for t in trend_values if "Down" in t)
        ranging_count = sum(1 for t in trend_values if t == "Ranging")
        
        total = len(trend_values)
        
        # Strong alignment if 80%+ agree
        if up_count / total >= 0.8:
            confluence = 90.0
        elif down_count / total >= 0.8:
            confluence = 90.0
        elif ranging_count / total >= 0.8:
            confluence = 80.0
        elif (up_count + ranging_count) / total >= 0.8:
            confluence = 70.0
        elif (down_count + ranging_count) / total >= 0.8:
            confluence = 70.0
        else:
            # Mixed signals
            confluence = 40.0
        
        return timeframe_trends, confluence
    
    def _analyze_market_microstructure(self, orderbook_data: Dict,
                                     market_data: MarketData) -> MarketMicrostructure:
        """Analyze market microstructure from orderbook"""
        try:
            bids = orderbook_data.get("bids", [])
            asks = orderbook_data.get("asks", [])
            
            if not bids or not asks:
                return MarketMicrostructure()
            
            # Calculate bid-ask spread
            best_bid = float(bids[0][0])
            best_ask = float(asks[0][0])
            spread = ((best_ask - best_bid) / best_bid) * 100
            
            # Calculate order book imbalance
            bid_volume = sum(float(bid[1]) for bid in bids[:10])
            ask_volume = sum(float(ask[1]) for ask in asks[:10])
            
            if bid_volume + ask_volume > 0:
                imbalance = ((bid_volume - ask_volume) / (bid_volume + ask_volume)) * 100
            else:
                imbalance = 0
            
            # Calculate market depth ratio
            depth_ratio = bid_volume / ask_volume if ask_volume > 0 else 1
            
            # Estimate trade flow (simplified)
            # In real implementation, would use actual trade data
            if imbalance > 20:
                trade_flow_ratio = 0.6  # More buying
            elif imbalance < -20:
                trade_flow_ratio = 0.4  # More selling
            else:
                trade_flow_ratio = 0.5  # Balanced
            
            # Calculate liquidity score
            total_depth = bid_volume + ask_volume
            if market_data.volume_24h and market_data.volume_24h > 0:
                liquidity_score = min(100, (total_depth / market_data.volume_24h) * 1000)
            else:
                liquidity_score = 50
            
            return MarketMicrostructure(
                bid_ask_spread=spread,
                order_book_imbalance=imbalance,
                trade_flow_ratio=trade_flow_ratio,
                liquidity_score=liquidity_score,
                market_depth_ratio=depth_ratio
            )
            
        except Exception as e:
            logger.debug(f"Error analyzing market microstructure: {e}")
            return MarketMicrostructure()
    
    def _classify_trend_direction_adaptive(self, current_price: float,
                                         indicators: EnhancedTechnicalIndicators,
                                         thresholds: AdaptiveThresholds) -> TrendDirection:
        """Classify trend direction with adaptive thresholds"""
        if not indicators.sma_20 or current_price <= 0:
            return TrendDirection.RANGING
        
        # Calculate price position relative to SMA 20
        price_vs_sma = ((current_price - indicators.sma_20) / indicators.sma_20) * 100
        
        # Volume confirmation with adaptive threshold
        volume_confirmation = False
        if indicators.volume_ratio:
            volume_confirmation = indicators.volume_ratio > thresholds.high_volume
        
        # Use adaptive thresholds
        if price_vs_sma > thresholds.strong_uptrend:
            if volume_confirmation:
                return TrendDirection.STRONG_UPTREND
            else:
                return TrendDirection.UPTREND
        elif price_vs_sma > thresholds.uptrend:
            return TrendDirection.UPTREND
        elif abs(price_vs_sma) <= thresholds.ranging:
            return TrendDirection.RANGING
        elif price_vs_sma < thresholds.downtrend:
            return TrendDirection.DOWNTREND
        elif price_vs_sma < thresholds.strong_downtrend:
            if volume_confirmation:
                return TrendDirection.STRONG_DOWNTREND
            else:
                return TrendDirection.DOWNTREND
        
        return TrendDirection.RANGING
    
    def _classify_volatility_level_adaptive(self, indicators: EnhancedTechnicalIndicators,
                                          market_data: MarketData,
                                          thresholds: AdaptiveThresholds) -> VolatilityLevel:
        """Classify volatility level with adaptive thresholds"""
        if not indicators.atr_14 or market_data.current_price <= 0:
            return VolatilityLevel.NORMAL
        
        # Calculate ATR as percentage of current price
        atr_pct = (indicators.atr_14 / market_data.current_price) * 100
        
        # Use adaptive thresholds
        if atr_pct < thresholds.very_low_vol:
            return VolatilityLevel.VERY_LOW
        elif atr_pct < thresholds.low_vol:
            return VolatilityLevel.LOW
        elif atr_pct < thresholds.normal_vol:
            return VolatilityLevel.NORMAL
        elif atr_pct < thresholds.high_vol:
            return VolatilityLevel.HIGH
        elif atr_pct < thresholds.very_high_vol:
            return VolatilityLevel.VERY_HIGH
        else:
            return VolatilityLevel.EXTREME
    
    def _classify_momentum_state_adaptive(self, indicators: EnhancedTechnicalIndicators,
                                        thresholds: AdaptiveThresholds) -> MomentumState:
        """Classify momentum state with adaptive thresholds"""
        rsi = indicators.rsi_14
        macd_hist = indicators.macd_histogram
        volume_strength = indicators.volume_strength or 50
        
        if not rsi:
            return MomentumState.NEUTRAL
        
        # Use adaptive RSI thresholds
        if rsi < thresholds.very_bearish_rsi:
            # Very bearish if MACD and volume confirm
            if macd_hist and macd_hist < 0 and volume_strength < 30:
                return MomentumState.VERY_BEARISH
            else:
                return MomentumState.BEARISH
        elif rsi < thresholds.bearish_rsi:
            return MomentumState.BEARISH
        elif rsi < thresholds.neutral_low_rsi:
            return MomentumState.BEARISH if macd_hist and macd_hist < 0 else MomentumState.NEUTRAL
        elif rsi < thresholds.neutral_high_rsi:
            return MomentumState.NEUTRAL
        elif rsi < thresholds.bullish_rsi:
            return MomentumState.BULLISH if macd_hist and macd_hist > 0 else MomentumState.NEUTRAL
        elif rsi < thresholds.very_bullish_rsi:
            return MomentumState.BULLISH
        else:
            # Very bullish if MACD and volume confirm
            if macd_hist and macd_hist > 0 and volume_strength > 70:
                return MomentumState.VERY_BULLISH
            else:
                return MomentumState.BULLISH
    
    def _determine_market_regime_enhanced(self, trend: TrendDirection,
                                        volatility: VolatilityLevel,
                                        momentum: MomentumState,
                                        indicators: EnhancedTechnicalIndicators,
                                        timeframe_confluence: float,
                                        microstructure: Optional[MarketMicrostructure]) -> MarketRegime:
        """Enhanced market regime determination with more nuanced classification"""
        
        # Check for breakout/breakdown conditions first
        if indicators.current_price and indicators.major_resistance and indicators.major_support:
            # Breakout detection
            if (trend in [TrendDirection.STRONG_UPTREND, TrendDirection.UPTREND] and
                indicators.current_price > indicators.major_resistance * 0.99 and
                indicators.volume_ratio and indicators.volume_ratio > 1.5):
                return MarketRegime.BREAKOUT
            
            # Breakdown detection
            if (trend in [TrendDirection.STRONG_DOWNTREND, TrendDirection.DOWNTREND] and
                indicators.current_price < indicators.major_support * 1.01 and
                indicators.volume_ratio and indicators.volume_ratio > 1.5):
                return MarketRegime.BREAKDOWN
        
        # Strong trends with confirmation
        if trend in [TrendDirection.STRONG_UPTREND, TrendDirection.UPTREND]:
            if momentum in [MomentumState.VERY_BULLISH, MomentumState.BULLISH]:
                # Additional confirmation from microstructure
                if microstructure and microstructure.order_book_imbalance is not None and microstructure.order_book_imbalance > 10:
                    return MarketRegime.BULL_MARKET
                elif timeframe_confluence > 70:
                    return MarketRegime.BULL_MARKET
                else:
                    return MarketRegime.BULL_MARKET if momentum == MomentumState.VERY_BULLISH else MarketRegime.ACCUMULATION
        
        if trend in [TrendDirection.STRONG_DOWNTREND, TrendDirection.DOWNTREND]:
            if momentum in [MomentumState.VERY_BEARISH, MomentumState.BEARISH]:
                # Additional confirmation from microstructure
                if microstructure and microstructure.order_book_imbalance is not None and microstructure.order_book_imbalance < -10:
                    return MarketRegime.BEAR_MARKET
                elif timeframe_confluence > 70:
                    return MarketRegime.BEAR_MARKET
                else:
                    return MarketRegime.BEAR_MARKET if momentum == MomentumState.VERY_BEARISH else MarketRegime.DISTRIBUTION
        
        # Extreme volatility overrides other conditions
        if volatility == VolatilityLevel.EXTREME:
            return MarketRegime.VOLATILE_MARKET
        
        # High volatility conditions
        if volatility in [VolatilityLevel.HIGH, VolatilityLevel.VERY_HIGH]:
            # Check if it's directional volatility
            if trend != TrendDirection.RANGING and timeframe_confluence > 60:
                # Directional volatile movement
                if trend in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND]:
                    return MarketRegime.BREAKOUT
                else:
                    return MarketRegime.BREAKDOWN
            else:
                return MarketRegime.VOLATILE_MARKET
        
        # Ranging conditions with volume analysis
        if trend == TrendDirection.RANGING:
            volume_strength = indicators.volume_strength or 50
            
            # Check microstructure for accumulation/distribution
            if microstructure and microstructure.order_book_imbalance is not None:
                if microstructure.order_book_imbalance > 20 and volume_strength > 60:
                    return MarketRegime.ACCUMULATION
                elif microstructure.order_book_imbalance < -20 and volume_strength > 60:
                    return MarketRegime.DISTRIBUTION
            
            # Traditional volume-based classification
            if volume_strength > 70:
                return MarketRegime.ACCUMULATION
            elif volume_strength < 30:
                return MarketRegime.DISTRIBUTION
            else:
                return MarketRegime.RANGING_MARKET
        
        # Default to ranging for unclear conditions
        return MarketRegime.RANGING_MARKET
    
    def _calculate_regime_transition_probability(self, symbol: str,
                                               current_regime: MarketRegime,
                                               trend: TrendDirection,
                                               volatility: VolatilityLevel,
                                               momentum: MomentumState) -> float:
        """Calculate probability of regime change in next period"""
        
        # Get regime history
        history = self.regime_history.get(symbol, [])
        if len(history) < 2:
            return 50.0  # Default uncertainty
        
        # Check how long in current regime
        current_duration = 0
        for entry in reversed(history):
            if entry["regime"] == current_regime:
                current_duration += 1
            else:
                break
        
        transition_prob = 0.0
        
        # Base probability increases with regime duration
        if current_duration > 20:
            transition_prob += 30
        elif current_duration > 10:
            transition_prob += 20
        elif current_duration > 5:
            transition_prob += 10
        
        # Conflicting signals increase transition probability
        
        # Bull market with bearish signals
        if current_regime == MarketRegime.BULL_MARKET:
            if momentum in [MomentumState.BEARISH, MomentumState.VERY_BEARISH]:
                transition_prob += 30
            if trend in [TrendDirection.DOWNTREND, TrendDirection.STRONG_DOWNTREND]:
                transition_prob += 20
        
        # Bear market with bullish signals
        elif current_regime == MarketRegime.BEAR_MARKET:
            if momentum in [MomentumState.BULLISH, MomentumState.VERY_BULLISH]:
                transition_prob += 30
            if trend in [TrendDirection.UPTREND, TrendDirection.STRONG_UPTREND]:
                transition_prob += 20
        
        # Ranging market with directional signals
        elif current_regime == MarketRegime.RANGING_MARKET:
            if trend in [TrendDirection.STRONG_UPTREND, TrendDirection.STRONG_DOWNTREND]:
                transition_prob += 40
            if volatility in [VolatilityLevel.HIGH, VolatilityLevel.VERY_HIGH]:
                transition_prob += 20
        
        # Volatile market calming down
        elif current_regime == MarketRegime.VOLATILE_MARKET:
            if volatility in [VolatilityLevel.LOW, VolatilityLevel.VERY_LOW]:
                transition_prob += 50
        
        # Cap at reasonable bounds
        return min(90, max(10, transition_prob))
    
    def _analyze_sentiment_enhanced(self, sentiment_score: Optional[float],
                                  trend_strength: float, momentum_score: float,
                                  timeframe_confluence: float) -> Dict[str, Any]:
        """Enhanced sentiment analysis with multiple factors"""
        
        # Use provided sentiment or calculate from technical indicators
        if sentiment_score is not None:
            score = sentiment_score
        else:
            # Enhanced calculation with timeframe confluence
            technical_sentiment = 50 + (trend_strength * 0.3) + (momentum_score * 0.2)
            confluence_bonus = (timeframe_confluence - 50) * 0.1  # ±5 points
            score = max(0, min(100, technical_sentiment + confluence_bonus))
        
        # More granular sentiment labels
        if score >= 85:
            label = "Extremely Bullish"
            emoji = "🚀"
        elif score >= 70:
            label = "Very Bullish"
            emoji = "💚"
        elif score >= 60:
            label = "Bullish"
            emoji = "🟢"
        elif score >= 50:
            label = "Slightly Bullish"
            emoji = "🔵"
        elif score >= 40:
            label = "Neutral"
            emoji = "⚖️"
        elif score >= 30:
            label = "Slightly Bearish"
            emoji = "🟡"
        elif score >= 20:
            label = "Bearish"
            emoji = "🔴"
        elif score >= 10:
            label = "Very Bearish"
            emoji = "🩸"
        else:
            label = "Extremely Bearish"
            emoji = "💀"
        
        return {
            "score": score,
            "label": label,
            "emoji": emoji
        }
    
    def _calculate_enhanced_key_levels(self, current_price: float,
                                     indicators: EnhancedTechnicalIndicators) -> Dict[str, float]:
        """Calculate enhanced key levels including VWAP and market profile"""
        levels = {}
        
        # Traditional MAs
        if current_price and indicators.sma_20:
            levels["sma_20"] = indicators.sma_20
        
        if indicators.sma_50:
            levels["sma_50"] = indicators.sma_50
        
        # Bollinger Bands
        if indicators.bb_upper and indicators.bb_lower:
            levels["bb_upper"] = indicators.bb_upper
            levels["bb_lower"] = indicators.bb_lower
        
        # VWAP levels
        if indicators.vwap:
            levels["vwap"] = indicators.vwap
            if indicators.vwap_upper:
                levels["vwap_upper"] = indicators.vwap_upper
            if indicators.vwap_lower:
                levels["vwap_lower"] = indicators.vwap_lower
        
        # Market Profile levels
        if indicators.poc:
            levels["poc"] = indicators.poc
        if indicators.vah:
            levels["vah"] = indicators.vah
        if indicators.val:
            levels["val"] = indicators.val
        
        # Enhanced support/resistance
        if indicators.major_support:
            levels["major_support"] = indicators.major_support
        if indicators.major_resistance:
            levels["major_resistance"] = indicators.major_resistance
        
        return levels
    
    def _calculate_regime_strength_enhanced(self, trend: TrendDirection,
                                          volatility: VolatilityLevel,
                                          momentum: MomentumState,
                                          trend_strength: float,
                                          volatility_score: float,
                                          momentum_score: float,
                                          timeframe_confluence: float,
                                          microstructure: Optional[MarketMicrostructure]) -> float:
        """Enhanced regime strength calculation with all factors"""
        
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
        if volatility == VolatilityLevel.EXTREME:
            strength_factors.append(40)  # Extreme volatility reduces regime clarity
        elif volatility in [VolatilityLevel.VERY_HIGH, VolatilityLevel.HIGH]:
            strength_factors.append(60)
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
        
        # Timeframe confluence
        strength_factors.append(timeframe_confluence)
        
        # Microstructure confirmation
        if microstructure and microstructure.order_book_imbalance is not None:
            micro_score = 50
            if abs(microstructure.order_book_imbalance) > 20:
                micro_score = 80
            elif abs(microstructure.order_book_imbalance) > 10:
                micro_score = 65
            
            strength_factors.append(micro_score)
        
        return statistics.mean(strength_factors)
    
    def _calculate_confidence_enhanced(self, technical_confidence: float,
                                     data_quality: float, regime_strength: float,
                                     timeframe_confluence: float,
                                     adaptive_confidence: float) -> float:
        """Enhanced confidence calculation with all factors"""
        
        confidence_factors = [
            technical_confidence * 0.25,      # Technical indicator confidence
            data_quality * 0.20,              # Data quality
            regime_strength * 0.25,           # Signal strength
            timeframe_confluence * 0.15,      # Multi-timeframe alignment
            adaptive_confidence * 0.15        # Adaptive threshold confidence
        ]
        
        return sum(confidence_factors)
    
    def _get_fallback_analysis(self, symbol: str) -> EnhancedMarketRegimeAnalysis:
        """Get fallback analysis when enhanced analysis fails"""
        return EnhancedMarketRegimeAnalysis(
            regime=MarketRegime.RANGING_MARKET,
            trend_direction=TrendDirection.RANGING,
            volatility_level=VolatilityLevel.NORMAL,
            momentum_state=MomentumState.NEUTRAL,
            analysis_timestamp=datetime.now(),
            confidence=0.0,
            thresholds_used=AdaptiveThresholds(
                strong_uptrend=2.0, uptrend=0.5, ranging=0.5,
                downtrend=-0.5, strong_downtrend=-2.0,
                very_low_vol=0.5, low_vol=1.5, normal_vol=3.0,
                high_vol=5.0, very_high_vol=8.0, extreme_vol=12.0,
                very_bearish_rsi=20, bearish_rsi=40, neutral_low_rsi=45,
                neutral_high_rsi=55, bullish_rsi=60, very_bullish_rsi=80,
                low_volume=0.5, normal_volume_low=0.8, normal_volume_high=1.2,
                high_volume=2.0, extreme_volume=3.0,
                confidence=0.0, last_updated=datetime.now()
            )
        )
    
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
enhanced_market_regime_detector = EnhancedMarketRegimeDetector()