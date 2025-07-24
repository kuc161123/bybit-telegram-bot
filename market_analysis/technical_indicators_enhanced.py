#!/usr/bin/env python3
"""
Enhanced Technical Indicators Calculation Engine
Provides comprehensive technical analysis with improved accuracy
"""
import asyncio
import logging
import statistics
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import math
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class EnhancedTechnicalIndicators:
    """Enhanced container for technical indicator results"""
    # Trend Indicators
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    
    # NEW: VWAP (Volume Weighted Average Price)
    vwap: Optional[float] = None
    vwap_upper: Optional[float] = None  # +1 std dev
    vwap_lower: Optional[float] = None  # -1 std dev
    
    # Volatility Indicators
    atr_14: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    
    # Enhanced Momentum Indicators
    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_divergence: Optional[str] = None  # NEW: Bullish/Bearish/None
    roc_10: Optional[float] = None
    
    # Volume Indicators
    volume_sma_20: Optional[float] = None
    volume_ratio: Optional[float] = None
    
    # NEW: Cumulative Delta (Buy vs Sell pressure)
    cumulative_delta: Optional[float] = None
    delta_trend: Optional[str] = None  # Increasing/Decreasing/Neutral
    
    # NEW: Market Profile
    poc: Optional[float] = None  # Point of Control (highest volume price)
    vah: Optional[float] = None  # Value Area High
    val: Optional[float] = None  # Value Area Low
    
    # Price Action
    current_price: Optional[float] = None
    price_change_24h: Optional[float] = None
    price_change_pct_24h: Optional[float] = None
    
    # Higher Level Analysis
    trend_strength: Optional[float] = None  # -100 to 100
    volatility_percentile: Optional[float] = None  # 0 to 100
    momentum_score: Optional[float] = None  # -100 to 100
    volume_strength: Optional[float] = None  # 0 to 100
    
    # Confidence and timing
    confidence: float = 0.0
    calculated_at: datetime = None
    
    # Enhanced Support and Resistance
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)
    major_support: Optional[float] = None
    major_resistance: Optional[float] = None
    
    # NEW: Volume Profile Support/Resistance
    volume_nodes: List[Dict[str, float]] = field(default_factory=list)  # Price levels with high volume

class EnhancedTechnicalAnalysisEngine:
    """Enhanced technical analysis calculation engine with improved accuracy"""
    
    def __init__(self):
        self.cache_ttl = 300  # 5 minutes
        self.indicator_cache = {}
        self.macd_history = {}  # Store MACD history for proper signal calculation
        
    async def calculate_indicators(
        self,
        symbol: str,
        kline_data: Dict[str, List],
        current_price: float,
        volume_24h: float = None,
        orderbook_data: Optional[Dict] = None
    ) -> EnhancedTechnicalIndicators:
        """
        Calculate comprehensive technical indicators with enhanced accuracy
        """
        try:
            logger.info(f"🔍 Calculating enhanced technical indicators for {symbol}")
            
            # Get primary timeframe data (1h)
            primary_data = kline_data.get('1h', [])
            minute_data = kline_data.get('5m', [])  # For more granular analysis
            daily_data = kline_data.get('1d', [])
            
            if not primary_data:
                logger.warning(f"⚠️ No kline data available for {symbol}")
                return EnhancedTechnicalIndicators(
                    current_price=current_price,
                    calculated_at=datetime.now(),
                    confidence=0.0
                )
            
            # Extract price and volume arrays
            closes = np.array([float(candle[4]) for candle in primary_data])
            highs = np.array([float(candle[2]) for candle in primary_data])
            lows = np.array([float(candle[3]) for candle in primary_data])
            volumes = np.array([float(candle[5]) for candle in primary_data])
            
            # Extract minute data for VWAP and cumulative delta
            if minute_data:
                minute_closes = np.array([float(candle[4]) for candle in minute_data[-288:]])  # Last 24h
                minute_volumes = np.array([float(candle[5]) for candle in minute_data[-288:]])
                minute_highs = np.array([float(candle[2]) for candle in minute_data[-288:]])
                minute_lows = np.array([float(candle[3]) for candle in minute_data[-288:]])
            else:
                minute_closes = minute_volumes = minute_highs = minute_lows = None
            
            # Calculate trend indicators
            sma_20 = self._calculate_sma(closes, 20)
            sma_50 = self._calculate_sma(closes, 50)
            sma_200 = self._calculate_sma(closes, 200) if len(closes) >= 200 else None
            ema_20 = self._calculate_ema(closes, 20)
            ema_50 = self._calculate_ema(closes, 50)
            
            # Calculate VWAP
            vwap, vwap_upper, vwap_lower = self._calculate_vwap(
                minute_closes, minute_highs, minute_lows, minute_volumes
            ) if minute_closes is not None else (None, None, None)
            
            # Calculate volatility indicators
            atr_14 = self._calculate_atr(highs, lows, closes, 14)
            bb_upper, bb_lower, bb_width = self._calculate_bollinger_bands(closes, 20, 2.0)
            
            # Enhanced MACD calculation with proper signal line
            macd_line, macd_signal, macd_histogram = self._calculate_enhanced_macd(
                symbol, closes, 12, 26, 9
            )
            
            # Detect MACD divergence
            macd_divergence = self._detect_macd_divergence(
                closes, macd_histogram if macd_histogram else None
            )
            
            # Calculate momentum indicators
            rsi_14 = self._calculate_rsi(closes, 14)
            roc_10 = self._calculate_roc(closes, 10)
            
            # Calculate volume indicators
            volume_sma_20 = self._calculate_sma(volumes, 20) if len(volumes) >= 20 else None
            volume_ratio = volumes[-1] / volume_sma_20 if volume_sma_20 and volumes.size > 0 else None
            
            # Calculate cumulative delta (if orderbook data available)
            cumulative_delta, delta_trend = self._calculate_cumulative_delta(
                orderbook_data, minute_closes, minute_volumes
            ) if orderbook_data else (None, None)
            
            # Calculate market profile
            poc, vah, val = self._calculate_market_profile(
                minute_closes, minute_volumes
            ) if minute_closes is not None else (None, None, None)
            
            # Calculate price change
            price_change_24h = closes[-1] - closes[-24] if len(closes) >= 24 else None
            price_change_pct_24h = (price_change_24h / closes[-24] * 100) if price_change_24h and closes[-24] else None
            
            # Calculate higher-level analysis
            trend_strength = self._calculate_trend_strength(
                current_price, sma_20, sma_50, ema_20, ema_50
            )
            volatility_percentile = self._calculate_volatility_percentile(
                atr_14, closes, 30
            )
            momentum_score = self._calculate_momentum_score(
                rsi_14, macd_histogram, roc_10
            )
            volume_strength = self._calculate_volume_strength(
                volume_ratio, volumes, 20
            )
            
            # Enhanced support and resistance with volume profile
            support_levels, resistance_levels, major_support, major_resistance, volume_nodes = \
                self._calculate_enhanced_support_resistance(
                    highs, lows, closes, volumes, current_price,
                    vah, val, poc
                )
            
            # Calculate overall confidence
            confidence = self._calculate_confidence(
                len(closes), sma_20, rsi_14, atr_14, volume_sma_20,
                vwap is not None, macd_divergence is not None
            )
            
            indicators = EnhancedTechnicalIndicators(
                # Trend Indicators
                sma_20=float(sma_20) if sma_20 is not None else None,
                sma_50=float(sma_50) if sma_50 is not None else None,
                sma_200=float(sma_200) if sma_200 is not None else None,
                ema_20=float(ema_20) if ema_20 is not None else None,
                ema_50=float(ema_50) if ema_50 is not None else None,
                vwap=float(vwap) if vwap is not None else None,
                vwap_upper=float(vwap_upper) if vwap_upper is not None else None,
                vwap_lower=float(vwap_lower) if vwap_lower is not None else None,
                
                # Volatility Indicators
                atr_14=float(atr_14) if atr_14 is not None else None,
                bb_upper=float(bb_upper) if bb_upper is not None else None,
                bb_lower=float(bb_lower) if bb_lower is not None else None,
                bb_width=float(bb_width) if bb_width is not None else None,
                
                # Enhanced Momentum Indicators
                rsi_14=float(rsi_14) if rsi_14 is not None else None,
                macd_line=float(macd_line) if macd_line is not None else None,
                macd_signal=float(macd_signal) if macd_signal is not None else None,
                macd_histogram=float(macd_histogram) if macd_histogram is not None else None,
                macd_divergence=macd_divergence,
                roc_10=float(roc_10) if roc_10 is not None else None,
                
                # Volume Indicators
                volume_sma_20=float(volume_sma_20) if volume_sma_20 is not None else None,
                volume_ratio=float(volume_ratio) if volume_ratio is not None else None,
                cumulative_delta=cumulative_delta,
                delta_trend=delta_trend,
                
                # Market Profile
                poc=float(poc) if poc is not None else None,
                vah=float(vah) if vah is not None else None,
                val=float(val) if val is not None else None,
                
                # Price Action
                current_price=current_price,
                price_change_24h=float(price_change_24h) if price_change_24h is not None else None,
                price_change_pct_24h=float(price_change_pct_24h) if price_change_pct_24h is not None else None,
                
                # Higher Level Analysis
                trend_strength=float(trend_strength) if trend_strength is not None else None,
                volatility_percentile=float(volatility_percentile) if volatility_percentile is not None else None,
                momentum_score=float(momentum_score) if momentum_score is not None else None,
                volume_strength=float(volume_strength) if volume_strength is not None else None,
                
                # Metadata
                confidence=confidence,
                calculated_at=datetime.now(),
                
                # Enhanced Support and Resistance
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                major_support=major_support,
                major_resistance=major_resistance,
                volume_nodes=volume_nodes
            )
            
            logger.info(f"✅ Enhanced technical indicators calculated for {symbol} with {confidence:.1f}% confidence")
            return indicators
            
        except Exception as e:
            logger.error(f"❌ Error calculating enhanced technical indicators for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return EnhancedTechnicalIndicators(
                current_price=current_price,
                calculated_at=datetime.now(),
                confidence=0.0
            )
    
    def _calculate_sma(self, data: np.ndarray, period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if len(data) < period:
            return None
        return np.mean(data[-period:])
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return None
        
        # Initialize with SMA
        multiplier = 2.0 / (period + 1)
        ema = np.mean(data[:period])
        
        # Calculate EMA for remaining data
        for price in data[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_enhanced_macd(self, symbol: str, data: np.ndarray, 
                                fast: int = 12, slow: int = 26, 
                                signal: int = 9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate MACD with proper signal line using historical values"""
        if len(data) < slow:
            return None, None, None
        
        # Initialize MACD history for this symbol if not exists
        if symbol not in self.macd_history:
            self.macd_history[symbol] = []
        
        # Calculate MACD line for all available data
        macd_values = []
        
        for i in range(slow, len(data) + 1):
            subset = data[:i]
            ema_fast = self._calculate_ema(subset, fast)
            ema_slow = self._calculate_ema(subset, slow)
            
            if ema_fast is not None and ema_slow is not None:
                macd_values.append(ema_fast - ema_slow)
        
        if not macd_values:
            return None, None, None
        
        # Update MACD history
        self.macd_history[symbol] = macd_values[-100:]  # Keep last 100 values
        
        # Current MACD line
        macd_line = macd_values[-1]
        
        # Calculate signal line (9-period EMA of MACD)
        if len(macd_values) >= signal:
            signal_line = self._calculate_ema(np.array(macd_values), signal)
        else:
            signal_line = macd_line  # Fallback
        
        # Calculate histogram
        histogram = macd_line - signal_line if signal_line is not None else None
        
        return macd_line, signal_line, histogram
    
    def _detect_macd_divergence(self, prices: np.ndarray, 
                               macd_histogram: Optional[float]) -> Optional[str]:
        """Detect MACD divergence (price vs MACD direction mismatch)"""
        if macd_histogram is None or len(prices) < 20:
            return None
        
        # Look at recent price trend
        recent_prices = prices[-20:]
        price_trend = "up" if recent_prices[-1] > recent_prices[0] else "down"
        
        # Look at MACD histogram trend (needs historical data)
        # For now, use histogram value as proxy
        macd_trend = "up" if macd_histogram > 0 else "down"
        
        # Detect divergence
        if price_trend == "up" and macd_trend == "down":
            return "Bearish"  # Price up, MACD down = bearish divergence
        elif price_trend == "down" and macd_trend == "up":
            return "Bullish"  # Price down, MACD up = bullish divergence
        
        return None
    
    def _calculate_vwap(self, closes: np.ndarray, highs: np.ndarray, 
                       lows: np.ndarray, volumes: np.ndarray) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate Volume Weighted Average Price with standard deviation bands"""
        if closes is None or len(closes) < 1:
            return None, None, None
        
        # Calculate typical price for each candle
        typical_prices = (highs + lows + closes) / 3
        
        # Calculate VWAP
        cum_price_volume = np.cumsum(typical_prices * volumes)
        cum_volume = np.cumsum(volumes)
        
        # Avoid division by zero
        if cum_volume[-1] == 0:
            return None, None, None
        
        vwap = cum_price_volume[-1] / cum_volume[-1]
        
        # Calculate standard deviation
        squared_deviations = (typical_prices - vwap) ** 2
        variance = np.sum(squared_deviations * volumes) / cum_volume[-1]
        std_dev = np.sqrt(variance)
        
        vwap_upper = vwap + std_dev
        vwap_lower = vwap - std_dev
        
        return vwap, vwap_upper, vwap_lower
    
    def _calculate_cumulative_delta(self, orderbook_data: Optional[Dict], 
                                   closes: np.ndarray, volumes: np.ndarray) -> Tuple[Optional[float], Optional[str]]:
        """Calculate cumulative delta (buy vs sell pressure)"""
        if not orderbook_data:
            return None, None
        
        try:
            # Extract bid/ask data
            bids = orderbook_data.get('bids', [])
            asks = orderbook_data.get('asks', [])
            
            if not bids or not asks:
                return None, None
            
            # Calculate bid/ask imbalance
            total_bid_volume = sum(float(bid[1]) for bid in bids[:10])  # Top 10 levels
            total_ask_volume = sum(float(ask[1]) for ask in asks[:10])
            
            # Cumulative delta as percentage
            if total_bid_volume + total_ask_volume > 0:
                delta = ((total_bid_volume - total_ask_volume) / 
                        (total_bid_volume + total_ask_volume)) * 100
            else:
                delta = 0
            
            # Determine trend
            if delta > 10:
                trend = "Bullish"
            elif delta < -10:
                trend = "Bearish"
            else:
                trend = "Neutral"
            
            return delta, trend
            
        except Exception as e:
            logger.debug(f"Error calculating cumulative delta: {e}")
            return None, None
    
    def _calculate_market_profile(self, closes: np.ndarray, 
                                 volumes: np.ndarray) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate market profile (POC, VAH, VAL)"""
        if closes is None or len(closes) < 20:
            return None, None, None
        
        try:
            # Create price bins
            price_min = np.min(closes)
            price_max = np.max(closes)
            num_bins = min(50, len(closes) // 5)  # Adaptive bin count
            
            bins = np.linspace(price_min, price_max, num_bins)
            
            # Calculate volume at each price level
            volume_profile = {}
            
            for i, price in enumerate(closes):
                # Find the appropriate bin
                bin_idx = np.digitize(price, bins) - 1
                bin_idx = max(0, min(bin_idx, len(bins) - 2))
                
                bin_price = (bins[bin_idx] + bins[bin_idx + 1]) / 2
                
                if bin_price not in volume_profile:
                    volume_profile[bin_price] = 0
                volume_profile[bin_price] += volumes[i] if i < len(volumes) else 0
            
            if not volume_profile:
                return None, None, None
            
            # Find POC (Point of Control) - highest volume price
            poc = max(volume_profile.keys(), key=lambda x: volume_profile[x])
            
            # Calculate Value Area (70% of volume)
            total_volume = sum(volume_profile.values())
            target_volume = total_volume * 0.7
            
            # Sort prices by volume
            sorted_prices = sorted(volume_profile.keys(), 
                                 key=lambda x: volume_profile[x], reverse=True)
            
            # Accumulate volume until we reach 70%
            accumulated_volume = 0
            value_area_prices = []
            
            for price in sorted_prices:
                accumulated_volume += volume_profile[price]
                value_area_prices.append(price)
                if accumulated_volume >= target_volume:
                    break
            
            if value_area_prices:
                vah = max(value_area_prices)  # Value Area High
                val = min(value_area_prices)  # Value Area Low
            else:
                vah = val = poc
            
            return poc, vah, val
            
        except Exception as e:
            logger.debug(f"Error calculating market profile: {e}")
            return None, None, None
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, 
                      closes: np.ndarray, period: int) -> Optional[float]:
        """Calculate Average True Range"""
        if len(highs) < period + 1:
            return None
        
        true_ranges = []
        for i in range(1, len(highs)):
            tr1 = highs[i] - lows[i]
            tr2 = abs(highs[i] - closes[i-1])
            tr3 = abs(lows[i] - closes[i-1])
            true_ranges.append(max(tr1, tr2, tr3))
        
        if len(true_ranges) < period:
            return None
        
        return np.mean(true_ranges[-period:])
    
    def _calculate_bollinger_bands(self, data: np.ndarray, period: int, 
                                 deviation: float) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate Bollinger Bands"""
        if len(data) < period:
            return None, None, None
        
        sma = self._calculate_sma(data, period)
        if sma is None:
            return None, None, None
        
        # Calculate standard deviation
        recent_data = data[-period:]
        std_dev = np.std(recent_data)
        
        upper = sma + (deviation * std_dev)
        lower = sma - (deviation * std_dev)
        width = (upper - lower) / sma * 100  # Width as percentage
        
        return upper, lower, width
    
    def _calculate_rsi(self, data: np.ndarray, period: int) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if len(data) < period + 1:
            return None
        
        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        if len(gains) < period:
            return None
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_roc(self, data: np.ndarray, period: int) -> Optional[float]:
        """Calculate Rate of Change"""
        if len(data) < period + 1:
            return None
        
        current = data[-1]
        previous = data[-(period + 1)]
        
        if previous == 0:
            return None
        
        roc = ((current - previous) / previous) * 100
        return roc
    
    def _calculate_trend_strength(self, current_price: float, sma_20: Optional[float],
                                sma_50: Optional[float], ema_20: Optional[float],
                                ema_50: Optional[float]) -> Optional[float]:
        """Calculate trend strength (-100 to 100)"""
        if not all([current_price, sma_20, ema_20]):
            return None
        
        scores = []
        
        # Price vs SMA 20
        sma_score = ((current_price - sma_20) / sma_20) * 100
        scores.append(np.clip(sma_score * 10, -100, 100))
        
        # Price vs EMA 20
        ema_score = ((current_price - ema_20) / ema_20) * 100
        scores.append(np.clip(ema_score * 10, -100, 100))
        
        # SMA 20 vs SMA 50 (if available)
        if sma_50:
            sma_cross_score = ((sma_20 - sma_50) / sma_50) * 100
            scores.append(np.clip(sma_cross_score * 20, -100, 100))
        
        return np.mean(scores)
    
    def _calculate_volatility_percentile(self, atr: Optional[float], 
                                       closes: np.ndarray, lookback: int) -> Optional[float]:
        """Calculate volatility percentile (0 to 100)"""
        if not atr or len(closes) < lookback:
            return None
        
        # Calculate historical volatility
        returns = np.diff(closes[-lookback:]) / closes[-lookback:-1]
        historical_vols = []
        
        for i in range(10, len(returns)):
            vol = np.std(returns[i-10:i]) * np.sqrt(252)  # Annualized
            historical_vols.append(vol)
        
        if not historical_vols:
            return 50.0
        
        current_vol = atr / closes[-1] * np.sqrt(252) if closes[-1] != 0 else atr
        
        # Calculate percentile
        percentile = (np.sum(current_vol > np.array(historical_vols)) / 
                     len(historical_vols)) * 100
        
        return percentile
    
    def _calculate_momentum_score(self, rsi: Optional[float], macd_hist: Optional[float],
                                roc: Optional[float]) -> Optional[float]:
        """Calculate momentum score (-100 to 100)"""
        scores = []
        
        if rsi is not None:
            # RSI: 50 = neutral, >70 = overbought, <30 = oversold
            rsi_score = (rsi - 50) * 2  # Scale to -100/100
            scores.append(np.clip(rsi_score, -100, 100))
        
        if macd_hist is not None:
            # MACD histogram: positive = bullish momentum
            macd_score = np.clip(macd_hist * 1000, -100, 100)
            scores.append(macd_score)
        
        if roc is not None:
            # Rate of Change: direct momentum indicator
            roc_score = np.clip(roc * 5, -100, 100)
            scores.append(roc_score)
        
        if not scores:
            return None
        
        return np.mean(scores)
    
    def _calculate_volume_strength(self, volume_ratio: Optional[float],
                                 volumes: np.ndarray, period: int) -> Optional[float]:
        """Calculate volume strength (0 to 100)"""
        if not volume_ratio or len(volumes) < period:
            return 50.0
        
        # Volume ratio above 1.0 indicates above-average volume
        if volume_ratio > 2.0:
            strength = 90
        elif volume_ratio > 1.5:
            strength = 75
        elif volume_ratio > 1.2:
            strength = 65
        elif volume_ratio > 0.8:
            strength = 50
        elif volume_ratio > 0.5:
            strength = 35
        else:
            strength = 20
        
        return float(strength)
    
    def _calculate_enhanced_support_resistance(self, highs: np.ndarray, lows: np.ndarray, 
                                             closes: np.ndarray, volumes: np.ndarray,
                                             current_price: float, vah: Optional[float],
                                             val: Optional[float], poc: Optional[float]) -> Tuple[List[float], List[float], Optional[float], Optional[float], List[Dict[str, float]]]:
        """Enhanced support/resistance calculation with volume profile integration"""
        if len(highs) < 20:
            return [], [], None, None, []
        
        # Traditional support/resistance levels
        lookback = min(100, len(highs))
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        recent_closes = closes[-lookback:]
        recent_volumes = volumes[-lookback:] if len(volumes) >= lookback else volumes
        
        levels = []
        
        # Find swing highs and lows
        for i in range(2, len(recent_highs) - 2):
            # Swing high (resistance)
            if (recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i-2] and
                recent_highs[i] > recent_highs[i+1] and recent_highs[i] > recent_highs[i+2]):
                levels.append({
                    "price": float(recent_highs[i]), 
                    "type": "resistance", 
                    "strength": 1,
                    "volume": float(recent_volumes[i]) if i < len(recent_volumes) else 0
                })
            
            # Swing low (support)
            if (recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i-2] and
                recent_lows[i] < recent_lows[i+1] and recent_lows[i] < recent_lows[i+2]):
                levels.append({
                    "price": float(recent_lows[i]), 
                    "type": "support", 
                    "strength": 1,
                    "volume": float(recent_volumes[i]) if i < len(recent_volumes) else 0
                })
        
        # Add market profile levels if available
        if vah is not None:
            levels.append({"price": float(vah), "type": "resistance", "strength": 2, "volume": 0})
        if val is not None:
            levels.append({"price": float(val), "type": "support", "strength": 2, "volume": 0})
        if poc is not None:
            # POC can act as both support and resistance
            if current_price > poc:
                levels.append({"price": float(poc), "type": "support", "strength": 3, "volume": 0})
            else:
                levels.append({"price": float(poc), "type": "resistance", "strength": 3, "volume": 0})
        
        # Volume-weighted price levels
        if len(recent_volumes) > 0:
            # Find high volume nodes
            volume_threshold = np.percentile(recent_volumes, 80)
            
            for i, vol in enumerate(recent_volumes):
                if vol > volume_threshold:
                    avg_price = (recent_highs[i] + recent_lows[i] + recent_closes[i]) / 3
                    level_type = "support" if avg_price < current_price else "resistance"
                    levels.append({
                        "price": float(avg_price), 
                        "type": level_type, 
                        "strength": 2,
                        "volume": float(vol)
                    })
        
        # Cluster nearby levels
        clustered_levels = self._cluster_levels(levels, sensitivity=0.01)
        
        # Separate support and resistance
        support_levels = sorted([l["price"] for l in clustered_levels if l["type"] == "support"], reverse=True)
        resistance_levels = sorted([l["price"] for l in clustered_levels if l["type"] == "resistance"])
        
        # Find major levels
        major_support = None
        major_resistance = None
        
        # Major support: strongest support below current price
        support_candidates = [(l["price"], l["strength"]) for l in clustered_levels 
                            if l["type"] == "support" and l["price"] < current_price * 0.98]
        if support_candidates:
            support_candidates.sort(key=lambda x: x[1], reverse=True)
            major_support = support_candidates[0][0]
        
        # Major resistance: strongest resistance above current price
        resistance_candidates = [(l["price"], l["strength"]) for l in clustered_levels 
                               if l["type"] == "resistance" and l["price"] > current_price * 1.02]
        if resistance_candidates:
            resistance_candidates.sort(key=lambda x: x[1], reverse=True)
            major_resistance = resistance_candidates[0][0]
        
        # Create volume nodes for visualization
        volume_nodes = [
            {"price": l["price"], "volume": l["volume"], "strength": l["strength"]}
            for l in clustered_levels if l["volume"] > 0
        ]
        
        # Limit levels
        support_levels = support_levels[:5]
        resistance_levels = resistance_levels[:5]
        
        return support_levels, resistance_levels, major_support, major_resistance, volume_nodes
    
    def _cluster_levels(self, levels: List[Dict], sensitivity: float = 0.01) -> List[Dict]:
        """Cluster nearby price levels"""
        if not levels:
            return []
        
        # Sort by price
        levels.sort(key=lambda x: x["price"])
        
        clustered = []
        i = 0
        
        while i < len(levels):
            cluster = [levels[i]]
            j = i + 1
            
            # Cluster levels within sensitivity range
            while j < len(levels) and (levels[j]["price"] - cluster[0]["price"]) / cluster[0]["price"] < sensitivity:
                cluster.append(levels[j])
                j += 1
            
            if cluster:
                # Calculate weighted average price
                total_strength = sum(l["strength"] for l in cluster)
                total_volume = sum(l["volume"] for l in cluster)
                
                if total_strength > 0:
                    weighted_price = sum(l["price"] * l["strength"] for l in cluster) / total_strength
                else:
                    weighted_price = np.mean([l["price"] for l in cluster])
                
                # Determine dominant type
                type_counts = {}
                for l in cluster:
                    type_counts[l["type"]] = type_counts.get(l["type"], 0) + l["strength"]
                
                dominant_type = max(type_counts.keys(), key=lambda x: type_counts[x])
                
                clustered.append({
                    "price": weighted_price,
                    "type": dominant_type,
                    "strength": total_strength,
                    "volume": total_volume
                })
            
            i = j
        
        return clustered
    
    def _calculate_confidence(self, data_points: int, sma_20: Optional[float],
                            rsi: Optional[float], atr: Optional[float],
                            volume_sma: Optional[float], has_vwap: bool,
                            has_divergence: bool) -> float:
        """Calculate overall confidence in the analysis"""
        confidence_factors = []
        
        # Data availability
        if data_points >= 200:
            confidence_factors.append(100)
        elif data_points >= 50:
            confidence_factors.append(80)
        elif data_points >= 20:
            confidence_factors.append(60)
        else:
            confidence_factors.append(30)
        
        # Indicator availability
        available_indicators = sum(1 for x in [sma_20, rsi, atr, volume_sma] if x is not None)
        indicator_confidence = (available_indicators / 4) * 80
        confidence_factors.append(indicator_confidence)
        
        # Enhanced indicators bonus
        if has_vwap:
            confidence_factors.append(90)
        if has_divergence:
            confidence_factors.append(85)
        
        # Return average confidence
        return np.mean(confidence_factors)

# Global instance
enhanced_technical_analysis_engine = EnhancedTechnicalAnalysisEngine()