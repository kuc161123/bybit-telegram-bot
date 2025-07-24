#!/usr/bin/env python3
"""
Technical Indicators Calculation Engine
Provides comprehensive technical analysis calculations for market status accuracy
"""
import asyncio
import logging
import statistics
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import math

logger = logging.getLogger(__name__)

@dataclass
class TechnicalIndicators:
    """Container for technical indicator results"""
    # Trend Indicators
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    
    # Volatility Indicators
    atr_14: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    
    # Momentum Indicators
    rsi_14: Optional[float] = None
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    roc_10: Optional[float] = None
    
    # Volume Indicators
    volume_sma_20: Optional[float] = None
    volume_ratio: Optional[float] = None
    
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
    
    # NEW: Support and Resistance levels
    support_levels: List[float] = None
    resistance_levels: List[float] = None
    major_support: Optional[float] = None
    major_resistance: Optional[float] = None

class TechnicalAnalysisEngine:
    """Advanced technical analysis calculation engine"""
    
    def __init__(self):
        self.cache_ttl = 60   # 1 minute for real-time updates
        self.indicator_cache = {}
        
    async def calculate_indicators(
        self,
        symbol: str,
        kline_data: Dict[str, List],
        current_price: float,
        volume_24h: float = None
    ) -> TechnicalIndicators:
        """
        Calculate comprehensive technical indicators
        
        Args:
            symbol: Trading symbol
            kline_data: Dict with timeframes as keys and kline data as values
            current_price: Current market price
            volume_24h: 24h trading volume
            
        Returns:
            TechnicalIndicators object with all calculated values
        """
        try:
            logger.info(f"🔍 Calculating technical indicators for {symbol}")
            
            # Get primary timeframe data (1h)
            primary_data = kline_data.get('1h', [])
            daily_data = kline_data.get('1d', [])
            
            if not primary_data:
                logger.warning(f"⚠️ No kline data available for {symbol}")
                return TechnicalIndicators(
                    current_price=current_price,
                    calculated_at=datetime.now(),
                    confidence=0.0
                )
            
            # Extract price and volume arrays
            closes = [float(candle[4]) for candle in primary_data]  # Close prices
            highs = [float(candle[2]) for candle in primary_data]   # High prices
            lows = [float(candle[3]) for candle in primary_data]    # Low prices
            volumes = [float(candle[5]) for candle in primary_data] # Volumes
            
            # Calculate trend indicators
            sma_20 = self._calculate_sma(closes, 20)
            sma_50 = self._calculate_sma(closes, 50)
            sma_200 = self._calculate_sma(closes, 200) if len(closes) >= 200 else None
            ema_20 = self._calculate_ema(closes, 20)
            ema_50 = self._calculate_ema(closes, 50)
            
            # Calculate volatility indicators
            atr_14 = self._calculate_atr(highs, lows, closes, 14)
            if atr_14:
                volatility_pct = (atr_14 / current_price) * 100 if current_price > 0 else 0
                logger.debug(f"ATR-14 for {symbol}: {atr_14:.6f} (volatility: {volatility_pct:.2f}%)")
            bb_upper, bb_lower, bb_width = self._calculate_bollinger_bands(closes, 20, 2.0)
            
            # Calculate momentum indicators
            rsi_14 = self._calculate_rsi(closes, 14)
            macd_line, macd_signal, macd_histogram = self._calculate_macd(closes, 12, 26, 9)
            roc_10 = self._calculate_roc(closes, 10)
            
            # Calculate volume indicators
            volume_sma_20 = self._calculate_sma(volumes, 20) if volumes else None
            volume_ratio = volumes[-1] / volume_sma_20 if volume_sma_20 and volumes else None
            
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
            
            # Calculate support and resistance levels
            support_levels, resistance_levels, major_support, major_resistance = self._calculate_support_resistance(
                highs, lows, closes, current_price
            )
            
            # Calculate overall confidence
            confidence = self._calculate_confidence(
                len(closes), sma_20, rsi_14, atr_14, volume_sma_20
            )
            
            indicators = TechnicalIndicators(
                # Trend Indicators
                sma_20=sma_20,
                sma_50=sma_50,
                sma_200=sma_200,
                ema_20=ema_20,
                ema_50=ema_50,
                
                # Volatility Indicators
                atr_14=atr_14,
                bb_upper=bb_upper,
                bb_lower=bb_lower,
                bb_width=bb_width,
                
                # Momentum Indicators
                rsi_14=rsi_14,
                macd_line=macd_line,
                macd_signal=macd_signal,
                macd_histogram=macd_histogram,
                roc_10=roc_10,
                
                # Volume Indicators
                volume_sma_20=volume_sma_20,
                volume_ratio=volume_ratio,
                
                # Price Action
                current_price=current_price,
                price_change_24h=price_change_24h,
                price_change_pct_24h=price_change_pct_24h,
                
                # Higher Level Analysis
                trend_strength=trend_strength,
                volatility_percentile=volatility_percentile,
                momentum_score=momentum_score,
                volume_strength=volume_strength,
                
                # Metadata
                confidence=confidence,
                calculated_at=datetime.now(),
                
                # Support and Resistance
                support_levels=support_levels,
                resistance_levels=resistance_levels,
                major_support=major_support,
                major_resistance=major_resistance
            )
            
            logger.info(f"✅ Technical indicators calculated for {symbol} with {confidence:.1f}% confidence")
            return indicators
            
        except Exception as e:
            logger.error(f"❌ Error calculating technical indicators for {symbol}: {e}")
            return TechnicalIndicators(
                current_price=current_price,
                calculated_at=datetime.now(),
                confidence=0.0
            )
    
    def _calculate_sma(self, data: List[float], period: int) -> Optional[float]:
        """Calculate Simple Moving Average"""
        if len(data) < period:
            return None
        return statistics.mean(data[-period:])
    
    def _calculate_ema(self, data: List[float], period: int) -> Optional[float]:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return None
        
        # Initialize with SMA
        multiplier = 2.0 / (period + 1)
        ema = statistics.mean(data[:period])
        
        # Calculate EMA for remaining data
        for price in data[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_atr(self, highs: List[float], lows: List[float], 
                      closes: List[float], period: int) -> Optional[float]:
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
        
        return statistics.mean(true_ranges[-period:])
    
    def _calculate_bollinger_bands(self, data: List[float], period: int, 
                                 deviation: float) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate Bollinger Bands"""
        if len(data) < period:
            return None, None, None
        
        sma = self._calculate_sma(data, period)
        if sma is None:
            return None, None, None
        
        # Calculate standard deviation
        recent_data = data[-period:]
        variance = sum((x - sma) ** 2 for x in recent_data) / period
        std_dev = math.sqrt(variance)
        
        upper = sma + (deviation * std_dev)
        lower = sma - (deviation * std_dev)
        width = (upper - lower) / sma * 100  # Width as percentage
        
        return upper, lower, width
    
    def _calculate_rsi(self, data: List[float], period: int) -> Optional[float]:
        """Calculate Relative Strength Index"""
        if len(data) < period + 1:
            return None
        
        deltas = [data[i] - data[i-1] for i in range(1, len(data))]
        gains = [max(d, 0) for d in deltas]
        losses = [abs(min(d, 0)) for d in deltas]
        
        if len(gains) < period:
            return None
        
        avg_gain = statistics.mean(gains[-period:])
        avg_loss = statistics.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_macd(self, data: List[float], fast: int = 12, 
                       slow: int = 26, signal: int = 9) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(data) < slow:
            return None, None, None
        
        ema_fast = self._calculate_ema(data, fast)
        ema_slow = self._calculate_ema(data, slow)
        
        if ema_fast is None or ema_slow is None:
            return None, None, None
        
        macd_line = ema_fast - ema_slow
        
        # For signal line, we'd need historical MACD values
        # Simplified approach: use recent price momentum as proxy
        signal_line = self._calculate_ema([macd_line], signal) if macd_line else None
        histogram = macd_line - signal_line if macd_line and signal_line else None
        
        return macd_line, signal_line, histogram
    
    def _calculate_roc(self, data: List[float], period: int) -> Optional[float]:
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
        scores.append(min(max(sma_score * 10, -100), 100))  # Scale and clamp
        
        # Price vs EMA 20
        ema_score = ((current_price - ema_20) / ema_20) * 100
        scores.append(min(max(ema_score * 10, -100), 100))
        
        # SMA 20 vs SMA 50 (if available)
        if sma_50:
            sma_cross_score = ((sma_20 - sma_50) / sma_50) * 100
            scores.append(min(max(sma_cross_score * 20, -100), 100))
        
        return statistics.mean(scores)
    
    def _calculate_volatility_percentile(self, atr: Optional[float], 
                                       closes: List[float], lookback: int) -> Optional[float]:
        """Calculate volatility percentile (0 to 100)"""
        if not atr or len(closes) < lookback:
            return None
        
        # Calculate historical ATR values for comparison
        recent_ranges = []
        for i in range(max(1, len(closes) - lookback), len(closes)):
            if i > 0:
                daily_range = abs(closes[i] - closes[i-1]) / closes[i-1] * 100
                recent_ranges.append(daily_range)
        
        if not recent_ranges:
            return 50.0  # Default to median
        
        current_vol = atr / closes[-1] * 100 if closes else atr
        sorted_ranges = sorted(recent_ranges)
        
        # Find percentile
        position = 0
        for i, vol in enumerate(sorted_ranges):
            if current_vol <= vol:
                position = i
                break
        else:
            position = len(sorted_ranges)
        
        percentile = (position / len(sorted_ranges)) * 100
        return percentile
    
    def _calculate_momentum_score(self, rsi: Optional[float], macd_hist: Optional[float],
                                roc: Optional[float]) -> Optional[float]:
        """Calculate momentum score (-100 to 100)"""
        scores = []
        
        if rsi is not None:
            # RSI: 50 = neutral, >70 = overbought, <30 = oversold
            rsi_score = (rsi - 50) * 2  # Scale to -100/100
            scores.append(min(max(rsi_score, -100), 100))
        
        if macd_hist is not None:
            # MACD histogram: positive = bullish momentum
            macd_score = min(max(macd_hist * 1000, -100), 100)  # Scale appropriately
            scores.append(macd_score)
        
        if roc is not None:
            # Rate of Change: direct momentum indicator
            roc_score = min(max(roc * 5, -100), 100)  # Scale for readability
            scores.append(roc_score)
        
        if not scores:
            return None
        
        return statistics.mean(scores)
    
    def _calculate_volume_strength(self, volume_ratio: Optional[float],
                                 volumes: List[float], period: int) -> Optional[float]:
        """Calculate volume strength (0 to 100)"""
        if not volume_ratio or len(volumes) < period:
            return 50.0  # Default neutral
        
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
    
    def _calculate_confidence(self, data_points: int, sma_20: Optional[float],
                            rsi: Optional[float], atr: Optional[float],
                            volume_sma: Optional[float]) -> float:
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
        indicator_confidence = (available_indicators / 4) * 100
        confidence_factors.append(indicator_confidence)
        
        # Return average confidence
        return statistics.mean(confidence_factors)
    
    def _calculate_support_resistance(self, highs: List[float], lows: List[float], 
                                    closes: List[float], current_price: float,
                                    lookback: int = 100, sensitivity: float = 0.02) -> Tuple[List[float], List[float], Optional[float], Optional[float]]:
        """
        Calculate support and resistance levels using price action analysis
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            current_price: Current market price
            lookback: Number of candles to analyze
            sensitivity: Price clustering sensitivity (default 2%)
            
        Returns:
            Tuple of (support_levels, resistance_levels, major_support, major_resistance)
        """
        try:
            from config.settings import SUPPORT_RESISTANCE_LOOKBACK, SUPPORT_RESISTANCE_SENSITIVITY
            lookback = SUPPORT_RESISTANCE_LOOKBACK
            sensitivity = SUPPORT_RESISTANCE_SENSITIVITY
        except ImportError:
            pass  # Use defaults
        
        if len(highs) < 20:  # Need minimum data
            return [], [], None, None
        
        # Limit lookback to available data
        lookback = min(lookback, len(highs))
        
        # Get recent price data
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        recent_closes = closes[-lookback:]
        
        # Find potential support/resistance levels using multiple methods
        levels = []
        
        # Method 1: Local maxima and minima
        for i in range(2, len(recent_highs) - 2):
            # Check for local high (resistance)
            if (recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i-2] and
                recent_highs[i] > recent_highs[i+1] and recent_highs[i] > recent_highs[i+2]):
                levels.append({"price": recent_highs[i], "type": "resistance", "strength": 1})
            
            # Check for local low (support)
            if (recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i-2] and
                recent_lows[i] < recent_lows[i+1] and recent_lows[i] < recent_lows[i+2]):
                levels.append({"price": recent_lows[i], "type": "support", "strength": 1})
        
        # Method 2: Round numbers (psychological levels)
        if current_price > 0:
            # Find the appropriate round number interval based on price magnitude
            if current_price < 1:
                interval = 0.1
            elif current_price < 10:
                interval = 1
            elif current_price < 100:
                interval = 10
            elif current_price < 1000:
                interval = 100
            elif current_price < 10000:
                interval = 1000
            else:
                interval = 10000
            
            # Add round numbers near current price
            base = int(current_price / interval) * interval
            for i in range(-3, 4):
                round_level = base + (i * interval)
                if round_level > 0:
                    levels.append({"price": round_level, "type": "psychological", "strength": 0.5})
        
        # Method 3: High volume nodes (using closes as proxy)
        price_counts = {}
        for close in recent_closes:
            # Round to sensitivity level
            rounded_price = round(close / current_price / sensitivity) * sensitivity * current_price
            price_counts[rounded_price] = price_counts.get(rounded_price, 0) + 1
        
        # Find price levels with high frequency (touched multiple times)
        avg_count = statistics.mean(price_counts.values()) if price_counts else 0
        for price, count in price_counts.items():
            if count > avg_count * 1.5:  # 50% above average
                level_type = "support" if price < current_price else "resistance"
                levels.append({"price": price, "type": level_type, "strength": count / len(recent_closes)})
        
        # Cluster nearby levels
        clustered_levels = []
        levels.sort(key=lambda x: x["price"])
        
        i = 0
        while i < len(levels):
            cluster = [levels[i]]
            j = i + 1
            
            # Cluster levels within sensitivity range
            while j < len(levels) and (levels[j]["price"] - cluster[0]["price"]) / cluster[0]["price"] < sensitivity:
                cluster.append(levels[j])
                j += 1
            
            # Calculate cluster strength and average price
            if cluster:
                avg_price = statistics.mean([l["price"] for l in cluster])
                total_strength = sum([l["strength"] for l in cluster])
                
                # Determine if support or resistance based on position relative to current price
                if avg_price < current_price:
                    clustered_levels.append({"price": avg_price, "type": "support", "strength": total_strength})
                else:
                    clustered_levels.append({"price": avg_price, "type": "resistance", "strength": total_strength})
            
            i = j
        
        # Separate support and resistance levels
        support_levels = sorted([l["price"] for l in clustered_levels if l["type"] == "support"], reverse=True)
        resistance_levels = sorted([l["price"] for l in clustered_levels if l["type"] == "resistance"])
        
        # Find major levels (strongest support and resistance)
        major_support = None
        major_resistance = None
        
        # Major support: closest strong support below current price
        support_candidates = [(l["price"], l["strength"]) for l in clustered_levels 
                            if l["type"] == "support" and l["price"] < current_price * 0.98]  # At least 2% below
        if support_candidates:
            # Sort by strength and proximity
            support_candidates.sort(key=lambda x: x[1] * (x[0] / current_price), reverse=True)
            major_support = support_candidates[0][0]
        
        # Major resistance: closest strong resistance above current price
        resistance_candidates = [(l["price"], l["strength"]) for l in clustered_levels 
                               if l["type"] == "resistance" and l["price"] > current_price * 1.02]  # At least 2% above
        if resistance_candidates:
            # Sort by strength and proximity
            resistance_candidates.sort(key=lambda x: x[1] * (current_price / x[0]), reverse=True)
            major_resistance = resistance_candidates[0][0]
        
        # Limit to top 5 levels for each type
        support_levels = support_levels[:5]
        resistance_levels = resistance_levels[:5]
        
        return support_levels, resistance_levels, major_support, major_resistance

# Global instance
technical_analysis_engine = TechnicalAnalysisEngine()