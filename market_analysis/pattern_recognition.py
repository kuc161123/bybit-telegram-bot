#!/usr/bin/env python3
"""
Pattern Recognition System
Detects chart patterns and candlestick formations for enhanced AI context
"""
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import statistics

logger = logging.getLogger(__name__)

class ChartPattern(Enum):
    """Chart pattern types"""
    # Reversal Patterns
    DOUBLE_TOP = "double_top"
    DOUBLE_BOTTOM = "double_bottom"
    HEAD_AND_SHOULDERS = "head_and_shoulders"
    INVERSE_HEAD_AND_SHOULDERS = "inverse_head_and_shoulders"
    TRIPLE_TOP = "triple_top"
    TRIPLE_BOTTOM = "triple_bottom"
    
    # Continuation Patterns
    ASCENDING_TRIANGLE = "ascending_triangle"
    DESCENDING_TRIANGLE = "descending_triangle"
    SYMMETRICAL_TRIANGLE = "symmetrical_triangle"
    RECTANGLE = "rectangle"
    FLAG = "flag"
    PENNANT = "pennant"
    WEDGE_RISING = "wedge_rising"
    WEDGE_FALLING = "wedge_falling"
    
    # Other Patterns
    CUP_AND_HANDLE = "cup_and_handle"
    ROUNDING_BOTTOM = "rounding_bottom"
    ROUNDING_TOP = "rounding_top"

class CandlestickPattern(Enum):
    """Candlestick pattern types"""
    # Single Candlestick Patterns
    DOJI = "doji"
    HAMMER = "hammer"
    INVERTED_HAMMER = "inverted_hammer"
    HANGING_MAN = "hanging_man"
    SHOOTING_STAR = "shooting_star"
    SPINNING_TOP = "spinning_top"
    MARUBOZU = "marubozu"
    
    # Double Candlestick Patterns
    BULLISH_ENGULFING = "bullish_engulfing"
    BEARISH_ENGULFING = "bearish_engulfing"
    PIERCING_PATTERN = "piercing_pattern"
    DARK_CLOUD_COVER = "dark_cloud_cover"
    TWEEZER_TOP = "tweezer_top"
    TWEEZER_BOTTOM = "tweezer_bottom"
    
    # Triple Candlestick Patterns
    THREE_WHITE_SOLDIERS = "three_white_soldiers"
    THREE_BLACK_CROWS = "three_black_crows"
    MORNING_STAR = "morning_star"
    EVENING_STAR = "evening_star"
    THREE_INSIDE_UP = "three_inside_up"
    THREE_INSIDE_DOWN = "three_inside_down"

@dataclass
class PatternMatch:
    """Container for pattern detection results"""
    pattern_type: str
    pattern_name: str
    confidence: float  # 0-100
    signal: str  # "bullish", "bearish", "neutral"
    strength: str  # "weak", "moderate", "strong"
    formation_complete: bool
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    formation_bars: int = 0
    description: str = ""
    timeframe: str = "5m"

@dataclass
class PatternAnalysis:
    """Complete pattern analysis results"""
    chart_patterns: List[PatternMatch]
    candlestick_patterns: List[PatternMatch]
    pattern_confluence: float  # 0-100 multiple pattern agreement
    dominant_signal: str  # Overall signal from all patterns
    pattern_count: int
    confidence_average: float
    key_insights: List[str]

class PatternRecognitionEngine:
    """Advanced pattern recognition for chart and candlestick patterns"""
    
    def __init__(self):
        self.min_bars_for_pattern = 10
        self.confidence_threshold = 60.0
        self.pattern_cache = {}
        self.cache_ttl = 300  # 5 minutes
        
    async def analyze_patterns(
        self, 
        symbol: str,
        kline_data: Dict[str, List],
        current_price: float,
        timeframes: List[str] = ["5m", "15m", "1h"]
    ) -> PatternAnalysis:
        """
        Comprehensive pattern analysis across multiple timeframes
        
        Args:
            symbol: Trading symbol
            kline_data: Dictionary with timeframe keys and kline lists
            current_price: Current market price
            timeframes: List of timeframes to analyze
            
        Returns:
            PatternAnalysis with detected patterns
        """
        try:
            all_chart_patterns = []
            all_candlestick_patterns = []
            
            for timeframe in timeframes:
                if timeframe in kline_data and kline_data[timeframe]:
                    klines = kline_data[timeframe]
                    
                    # Detect chart patterns
                    chart_patterns = await self._detect_chart_patterns(
                        symbol, klines, current_price, timeframe
                    )
                    all_chart_patterns.extend(chart_patterns)
                    
                    # Detect candlestick patterns
                    candlestick_patterns = await self._detect_candlestick_patterns(
                        symbol, klines, current_price, timeframe
                    )
                    all_candlestick_patterns.extend(candlestick_patterns)
            
            # Analyze pattern confluence
            pattern_confluence = self._calculate_pattern_confluence(
                all_chart_patterns + all_candlestick_patterns
            )
            
            # Determine dominant signal
            dominant_signal = self._determine_dominant_signal(
                all_chart_patterns + all_candlestick_patterns
            )
            
            # Calculate averages
            all_patterns = all_chart_patterns + all_candlestick_patterns
            confidence_avg = statistics.mean([p.confidence for p in all_patterns]) if all_patterns else 0
            
            # Generate insights
            key_insights = self._generate_pattern_insights(
                all_chart_patterns, all_candlestick_patterns, pattern_confluence
            )
            
            return PatternAnalysis(
                chart_patterns=all_chart_patterns,
                candlestick_patterns=all_candlestick_patterns,
                pattern_confluence=pattern_confluence,
                dominant_signal=dominant_signal,
                pattern_count=len(all_patterns),
                confidence_average=confidence_avg,
                key_insights=key_insights
            )
            
        except Exception as e:
            logger.error(f"Error in pattern analysis: {e}")
            return PatternAnalysis(
                chart_patterns=[],
                candlestick_patterns=[],
                pattern_confluence=0.0,
                dominant_signal="neutral",
                pattern_count=0,
                confidence_average=0.0,
                key_insights=["Pattern analysis unavailable"]
            )
    
    async def _detect_chart_patterns(
        self, 
        symbol: str, 
        klines: List, 
        current_price: float, 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect chart patterns in price data"""
        patterns = []
        
        if len(klines) < self.min_bars_for_pattern:
            return patterns
        
        # Extract price data
        highs = np.array([float(k[2]) for k in klines])
        lows = np.array([float(k[3]) for k in klines])
        closes = np.array([float(k[4]) for k in klines])
        
        # Detect various chart patterns
        patterns.extend(await self._detect_triangle_patterns(highs, lows, closes, timeframe))
        patterns.extend(await self._detect_double_patterns(highs, lows, closes, timeframe))
        patterns.extend(await self._detect_head_shoulders(highs, lows, closes, timeframe))
        patterns.extend(await self._detect_rectangle_patterns(highs, lows, closes, timeframe))
        patterns.extend(await self._detect_cup_handle(highs, lows, closes, timeframe))
        
        return patterns
    
    async def _detect_triangle_patterns(
        self, 
        highs: np.ndarray, 
        lows: np.ndarray, 
        closes: np.ndarray, 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect triangle patterns (ascending, descending, symmetrical)"""
        patterns = []
        
        if len(highs) < 20:
            return patterns
        
        try:
            # Look for triangle formations in recent data
            recent_highs = highs[-20:]
            recent_lows = lows[-20:]
            
            # Find trend lines
            high_trend = self._calculate_trend_line(recent_highs)
            low_trend = self._calculate_trend_line(recent_lows)
            
            if high_trend is None or low_trend is None:
                return patterns
            
            high_slope, low_slope = high_trend, low_trend
            
            # Classify triangle type
            if abs(high_slope) < 0.001 and low_slope > 0.001:
                # Ascending triangle
                patterns.append(PatternMatch(
                    pattern_type="chart",
                    pattern_name="Ascending Triangle",
                    confidence=75.0,
                    signal="bullish",
                    strength="moderate",
                    formation_complete=True,
                    target_price=closes[-1] * 1.05,  # 5% target
                    stop_loss=closes[-1] * 0.97,    # 3% stop
                    formation_bars=20,
                    description="Horizontal resistance with rising support",
                    timeframe=timeframe
                ))
            elif high_slope < -0.001 and abs(low_slope) < 0.001:
                # Descending triangle
                patterns.append(PatternMatch(
                    pattern_type="chart",
                    pattern_name="Descending Triangle",
                    confidence=75.0,
                    signal="bearish",
                    strength="moderate",
                    formation_complete=True,
                    target_price=closes[-1] * 0.95,  # 5% target
                    stop_loss=closes[-1] * 1.03,    # 3% stop
                    formation_bars=20,
                    description="Horizontal support with falling resistance",
                    timeframe=timeframe
                ))
            elif high_slope < -0.001 and low_slope > 0.001:
                # Symmetrical triangle
                convergence = abs(high_slope) + abs(low_slope)
                confidence = min(80.0, 50.0 + convergence * 1000)  # Higher convergence = higher confidence
                
                patterns.append(PatternMatch(
                    pattern_type="chart",
                    pattern_name="Symmetrical Triangle",
                    confidence=confidence,
                    signal="neutral",
                    strength="moderate",
                    formation_complete=True,
                    target_price=None,  # Breakout direction determines target
                    stop_loss=None,
                    formation_bars=20,
                    description="Converging support and resistance lines",
                    timeframe=timeframe
                ))
                
        except Exception as e:
            logger.debug(f"Error detecting triangle patterns: {e}")
        
        return patterns
    
    async def _detect_double_patterns(
        self, 
        highs: np.ndarray, 
        lows: np.ndarray, 
        closes: np.ndarray, 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect double top and double bottom patterns"""
        patterns = []
        
        if len(highs) < 30:
            return patterns
        
        try:
            # Double top detection
            peaks = self._find_peaks(highs, min_distance=5)
            if len(peaks) >= 2:
                # Check last two significant peaks
                last_peaks = peaks[-2:]
                peak1_height = highs[last_peaks[0]]
                peak2_height = highs[last_peaks[1]]
                
                # Check if peaks are similar height (within 2%)
                if abs(peak1_height - peak2_height) / peak1_height < 0.02:
                    # Find the valley between peaks
                    valley_start, valley_end = last_peaks[0], last_peaks[1]
                    valley_low = np.min(lows[valley_start:valley_end])
                    
                    # Calculate pattern strength
                    peak_avg = (peak1_height + peak2_height) / 2
                    valley_depth = (peak_avg - valley_low) / peak_avg
                    
                    if valley_depth > 0.03:  # At least 3% retracement
                        confidence = min(85.0, 60.0 + valley_depth * 500)
                        
                        patterns.append(PatternMatch(
                            pattern_type="chart",
                            pattern_name="Double Top",
                            confidence=confidence,
                            signal="bearish",
                            strength="strong" if valley_depth > 0.08 else "moderate",
                            formation_complete=True,
                            target_price=valley_low,  # Target is valley low
                            stop_loss=peak_avg * 1.02,  # Stop above resistance
                            formation_bars=last_peaks[1] - last_peaks[0],
                            description=f"Two peaks at similar levels with {valley_depth:.1%} retracement",
                            timeframe=timeframe
                        ))
            
            # Double bottom detection
            troughs = self._find_troughs(lows, min_distance=5)
            if len(troughs) >= 2:
                # Check last two significant troughs
                last_troughs = troughs[-2:]
                trough1_low = lows[last_troughs[0]]
                trough2_low = lows[last_troughs[1]]
                
                # Check if troughs are similar depth (within 2%)
                if abs(trough1_low - trough2_low) / trough1_low < 0.02:
                    # Find the peak between troughs
                    peak_start, peak_end = last_troughs[0], last_troughs[1]
                    peak_high = np.max(highs[peak_start:peak_end])
                    
                    # Calculate pattern strength
                    trough_avg = (trough1_low + trough2_low) / 2
                    peak_height = (peak_high - trough_avg) / trough_avg
                    
                    if peak_height > 0.03:  # At least 3% rally
                        confidence = min(85.0, 60.0 + peak_height * 500)
                        
                        patterns.append(PatternMatch(
                            pattern_type="chart",
                            pattern_name="Double Bottom",
                            confidence=confidence,
                            signal="bullish",
                            strength="strong" if peak_height > 0.08 else "moderate",
                            formation_complete=True,
                            target_price=peak_high,  # Target is peak high
                            stop_loss=trough_avg * 0.98,  # Stop below support
                            formation_bars=last_troughs[1] - last_troughs[0],
                            description=f"Two troughs at similar levels with {peak_height:.1%} rally",
                            timeframe=timeframe
                        ))
                        
        except Exception as e:
            logger.debug(f"Error detecting double patterns: {e}")
        
        return patterns
    
    async def _detect_head_shoulders(
        self, 
        highs: np.ndarray, 
        lows: np.ndarray, 
        closes: np.ndarray, 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect head and shoulders patterns"""
        patterns = []
        
        if len(highs) < 40:
            return patterns
        
        try:
            peaks = self._find_peaks(highs, min_distance=8)
            
            if len(peaks) >= 3:
                # Check last three peaks for head and shoulders
                last_peaks = peaks[-3:]
                left_shoulder = highs[last_peaks[0]]
                head = highs[last_peaks[1]]
                right_shoulder = highs[last_peaks[2]]
                
                # Head should be higher than both shoulders
                if head > left_shoulder and head > right_shoulder:
                    # Shoulders should be roughly equal (within 3%)
                    shoulder_diff = abs(left_shoulder - right_shoulder) / max(left_shoulder, right_shoulder)
                    
                    if shoulder_diff < 0.03:
                        # Calculate neckline (support between shoulders)
                        neckline_start = last_peaks[0]
                        neckline_end = last_peaks[2]
                        neckline = np.min(lows[neckline_start:neckline_end])
                        
                        # Pattern validity checks
                        head_prominence = (head - max(left_shoulder, right_shoulder)) / head
                        
                        if head_prominence > 0.02:  # Head at least 2% higher
                            confidence = min(90.0, 70.0 + head_prominence * 1000)
                            
                            patterns.append(PatternMatch(
                                pattern_type="chart",
                                pattern_name="Head and Shoulders",
                                confidence=confidence,
                                signal="bearish",
                                strength="strong",
                                formation_complete=True,
                                target_price=neckline - (head - neckline),  # Measured move
                                stop_loss=right_shoulder * 1.02,
                                formation_bars=last_peaks[2] - last_peaks[0],
                                description=f"Classic reversal pattern with {head_prominence:.1%} head prominence",
                                timeframe=timeframe
                            ))
            
            # Inverse head and shoulders (on lows)
            troughs = self._find_troughs(lows, min_distance=8)
            
            if len(troughs) >= 3:
                last_troughs = troughs[-3:]
                left_shoulder = lows[last_troughs[0]]
                head = lows[last_troughs[1]]
                right_shoulder = lows[last_troughs[2]]
                
                # Head should be lower than both shoulders
                if head < left_shoulder and head < right_shoulder:
                    shoulder_diff = abs(left_shoulder - right_shoulder) / max(left_shoulder, right_shoulder)
                    
                    if shoulder_diff < 0.03:
                        # Calculate neckline (resistance between shoulders)
                        neckline_start = last_troughs[0]
                        neckline_end = last_troughs[2]
                        neckline = np.max(highs[neckline_start:neckline_end])
                        
                        head_prominence = (min(left_shoulder, right_shoulder) - head) / head
                        
                        if head_prominence > 0.02:
                            confidence = min(90.0, 70.0 + head_prominence * 1000)
                            
                            patterns.append(PatternMatch(
                                pattern_type="chart",
                                pattern_name="Inverse Head and Shoulders",
                                confidence=confidence,
                                signal="bullish",
                                strength="strong",
                                formation_complete=True,
                                target_price=neckline + (neckline - head),  # Measured move
                                stop_loss=right_shoulder * 0.98,
                                formation_bars=last_troughs[2] - last_troughs[0],
                                description=f"Classic reversal pattern with {head_prominence:.1%} head prominence",
                                timeframe=timeframe
                            ))
                            
        except Exception as e:
            logger.debug(f"Error detecting head and shoulders: {e}")
        
        return patterns
    
    async def _detect_rectangle_patterns(
        self, 
        highs: np.ndarray, 
        lows: np.ndarray, 
        closes: np.ndarray, 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect rectangle/channel patterns"""
        patterns = []
        
        if len(highs) < 25:
            return patterns
        
        try:
            recent_data = 25
            recent_highs = highs[-recent_data:]
            recent_lows = lows[-recent_data:]
            
            # Find resistance and support levels
            resistance = np.percentile(recent_highs, 85)
            support = np.percentile(recent_lows, 15)
            
            # Check if price has been respecting these levels
            resistance_touches = np.sum(recent_highs > resistance * 0.99)
            support_touches = np.sum(recent_lows < support * 1.01)
            
            if resistance_touches >= 2 and support_touches >= 2:
                # Calculate channel width
                channel_width = (resistance - support) / support
                
                if 0.03 <= channel_width <= 0.15:  # 3-15% channel width
                    # Check for sideways movement
                    price_range = np.max(closes[-recent_data:]) - np.min(closes[-recent_data:])
                    range_ratio = price_range / closes[-1]
                    
                    confidence = min(80.0, 50.0 + (1 / range_ratio) * 5)
                    
                    patterns.append(PatternMatch(
                        pattern_type="chart",
                        pattern_name="Rectangle",
                        confidence=confidence,
                        signal="neutral",
                        strength="moderate",
                        formation_complete=False,  # Continuation pattern
                        target_price=None,  # Depends on breakout direction
                        stop_loss=None,
                        formation_bars=recent_data,
                        description=f"Horizontal channel with {channel_width:.1%} width",
                        timeframe=timeframe
                    ))
                    
        except Exception as e:
            logger.debug(f"Error detecting rectangle patterns: {e}")
        
        return patterns
    
    async def _detect_cup_handle(
        self, 
        highs: np.ndarray, 
        lows: np.ndarray, 
        closes: np.ndarray, 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect cup and handle patterns"""
        patterns = []
        
        if len(highs) < 50:
            return patterns
        
        try:
            # Look for cup formation in longer timeframe data
            cup_length = min(50, len(highs))
            cup_highs = highs[-cup_length:]
            cup_lows = lows[-cup_length:]
            
            # Find the initial high (cup left rim)
            initial_high = np.max(cup_highs[:cup_length//3])
            
            # Find the cup bottom
            cup_bottom = np.min(cup_lows[cup_length//4:3*cup_length//4])
            
            # Find recent high (cup right rim)
            recent_high = np.max(cup_highs[-cup_length//3:])
            
            # Cup criteria
            depth_ratio = (initial_high - cup_bottom) / initial_high
            rim_similarity = abs(initial_high - recent_high) / initial_high
            
            if 0.12 <= depth_ratio <= 0.50 and rim_similarity < 0.05:  # 12-50% depth, rims within 5%
                # Look for handle (small consolidation after cup)
                handle_data = highs[-10:]
                handle_depth = (recent_high - np.min(handle_data)) / recent_high
                
                if handle_depth < 0.12:  # Handle less than 12% deep
                    confidence = min(85.0, 60.0 + (1 - rim_similarity) * 50)
                    
                    patterns.append(PatternMatch(
                        pattern_type="chart",
                        pattern_name="Cup and Handle",
                        confidence=confidence,
                        signal="bullish",
                        strength="strong",
                        formation_complete=True,
                        target_price=recent_high + (initial_high - cup_bottom),  # Measured move
                        stop_loss=cup_bottom,
                        formation_bars=cup_length,
                        description=f"Cup depth {depth_ratio:.1%}, handle depth {handle_depth:.1%}",
                        timeframe=timeframe
                    ))
                    
        except Exception as e:
            logger.debug(f"Error detecting cup and handle: {e}")
        
        return patterns
    
    async def _detect_candlestick_patterns(
        self, 
        symbol: str, 
        klines: List, 
        current_price: float, 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect candlestick patterns"""
        patterns = []
        
        if len(klines) < 3:
            return patterns
        
        # Extract OHLC data
        candles = []
        for k in klines[-10:]:  # Analyze last 10 candles
            candles.append({
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            })
        
        # Detect various candlestick patterns
        patterns.extend(await self._detect_single_candle_patterns(candles, timeframe))
        patterns.extend(await self._detect_double_candle_patterns(candles, timeframe))
        patterns.extend(await self._detect_triple_candle_patterns(candles, timeframe))
        
        return patterns
    
    async def _detect_single_candle_patterns(
        self, 
        candles: List[Dict], 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect single candlestick patterns"""
        patterns = []
        
        if not candles:
            return patterns
        
        latest = candles[-1]
        body = abs(latest['close'] - latest['open'])
        upper_shadow = latest['high'] - max(latest['open'], latest['close'])
        lower_shadow = min(latest['open'], latest['close']) - latest['low']
        candle_range = latest['high'] - latest['low']
        
        if candle_range == 0:
            return patterns
        
        # Doji pattern
        if body / candle_range < 0.1:  # Body less than 10% of range
            patterns.append(PatternMatch(
                pattern_type="candlestick",
                pattern_name="Doji",
                confidence=70.0,
                signal="neutral",
                strength="moderate",
                formation_complete=True,
                description="Indecision candle with small body",
                timeframe=timeframe
            ))
        
        # Hammer pattern
        elif (lower_shadow > body * 2 and upper_shadow < body * 0.3 and 
              latest['close'] > latest['open']):  # Bullish hammer
            patterns.append(PatternMatch(
                pattern_type="candlestick",
                pattern_name="Hammer",
                confidence=75.0,
                signal="bullish",
                strength="moderate",
                formation_complete=True,
                description="Bullish reversal candle with long lower shadow",
                timeframe=timeframe
            ))
        
        # Shooting star pattern
        elif (upper_shadow > body * 2 and lower_shadow < body * 0.3 and 
              latest['close'] < latest['open']):  # Bearish shooting star
            patterns.append(PatternMatch(
                pattern_type="candlestick",
                pattern_name="Shooting Star",
                confidence=75.0,
                signal="bearish",
                strength="moderate",
                formation_complete=True,
                description="Bearish reversal candle with long upper shadow",
                timeframe=timeframe
            ))
        
        return patterns
    
    async def _detect_double_candle_patterns(
        self, 
        candles: List[Dict], 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect double candlestick patterns"""
        patterns = []
        
        if len(candles) < 2:
            return patterns
        
        prev, curr = candles[-2], candles[-1]
        
        # Bullish engulfing
        if (prev['close'] < prev['open'] and  # Previous candle bearish
            curr['close'] > curr['open'] and  # Current candle bullish
            curr['open'] < prev['close'] and  # Current opens below previous close
            curr['close'] > prev['open']):    # Current closes above previous open
            
            patterns.append(PatternMatch(
                pattern_type="candlestick",
                pattern_name="Bullish Engulfing",
                confidence=80.0,
                signal="bullish",
                strength="strong",
                formation_complete=True,
                description="Bullish candle engulfs previous bearish candle",
                timeframe=timeframe
            ))
        
        # Bearish engulfing
        elif (prev['close'] > prev['open'] and  # Previous candle bullish
              curr['close'] < curr['open'] and  # Current candle bearish
              curr['open'] > prev['close'] and  # Current opens above previous close
              curr['close'] < prev['open']):    # Current closes below previous open
            
            patterns.append(PatternMatch(
                pattern_type="candlestick",
                pattern_name="Bearish Engulfing",
                confidence=80.0,
                signal="bearish",
                strength="strong",
                formation_complete=True,
                description="Bearish candle engulfs previous bullish candle",
                timeframe=timeframe
            ))
        
        return patterns
    
    async def _detect_triple_candle_patterns(
        self, 
        candles: List[Dict], 
        timeframe: str
    ) -> List[PatternMatch]:
        """Detect triple candlestick patterns"""
        patterns = []
        
        if len(candles) < 3:
            return patterns
        
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        
        # Three white soldiers
        if (c1['close'] > c1['open'] and c2['close'] > c2['open'] and c3['close'] > c3['open'] and
            c2['close'] > c1['close'] and c3['close'] > c2['close']):
            
            patterns.append(PatternMatch(
                pattern_type="candlestick",
                pattern_name="Three White Soldiers",
                confidence=85.0,
                signal="bullish",
                strength="strong",
                formation_complete=True,
                description="Three consecutive bullish candles with higher closes",
                timeframe=timeframe
            ))
        
        # Three black crows
        elif (c1['close'] < c1['open'] and c2['close'] < c2['open'] and c3['close'] < c3['open'] and
              c2['close'] < c1['close'] and c3['close'] < c2['close']):
            
            patterns.append(PatternMatch(
                pattern_type="candlestick",
                pattern_name="Three Black Crows",
                confidence=85.0,
                signal="bearish",
                strength="strong",
                formation_complete=True,
                description="Three consecutive bearish candles with lower closes",
                timeframe=timeframe
            ))
        
        return patterns
    
    def _calculate_trend_line(self, data: np.ndarray) -> Optional[float]:
        """Calculate trend line slope using linear regression"""
        try:
            if len(data) < 3:
                return None
            
            x = np.arange(len(data))
            slope, _ = np.polyfit(x, data, 1)
            return slope
        except:
            return None
    
    def _find_peaks(self, data: np.ndarray, min_distance: int = 5) -> List[int]:
        """Find peaks in data"""
        peaks = []
        
        for i in range(min_distance, len(data) - min_distance):
            is_peak = True
            
            # Check if current point is higher than surrounding points
            for j in range(i - min_distance, i + min_distance + 1):
                if j != i and data[j] >= data[i]:
                    is_peak = False
                    break
            
            if is_peak:
                peaks.append(i)
        
        return peaks
    
    def _find_troughs(self, data: np.ndarray, min_distance: int = 5) -> List[int]:
        """Find troughs in data"""
        troughs = []
        
        for i in range(min_distance, len(data) - min_distance):
            is_trough = True
            
            # Check if current point is lower than surrounding points
            for j in range(i - min_distance, i + min_distance + 1):
                if j != i and data[j] <= data[i]:
                    is_trough = False
                    break
            
            if is_trough:
                troughs.append(i)
        
        return troughs
    
    def _calculate_pattern_confluence(self, patterns: List[PatternMatch]) -> float:
        """Calculate how well patterns agree with each other"""
        if not patterns:
            return 0.0
        
        bullish_patterns = [p for p in patterns if p.signal == "bullish"]
        bearish_patterns = [p for p in patterns if p.signal == "bearish"]
        neutral_patterns = [p for p in patterns if p.signal == "neutral"]
        
        total_patterns = len(patterns)
        
        # Calculate weighted agreement
        bullish_weight = sum(p.confidence for p in bullish_patterns)
        bearish_weight = sum(p.confidence for p in bearish_patterns)
        neutral_weight = sum(p.confidence for p in neutral_patterns)
        
        total_weight = bullish_weight + bearish_weight + neutral_weight
        
        if total_weight == 0:
            return 0.0
        
        # Confluence is how much the strongest signal dominates
        max_weight = max(bullish_weight, bearish_weight, neutral_weight)
        confluence = (max_weight / total_weight) * 100
        
        return confluence
    
    def _determine_dominant_signal(self, patterns: List[PatternMatch]) -> str:
        """Determine the overall signal from all patterns"""
        if not patterns:
            return "neutral"
        
        # Weight by confidence
        bullish_score = sum(p.confidence for p in patterns if p.signal == "bullish")
        bearish_score = sum(p.confidence for p in patterns if p.signal == "bearish")
        neutral_score = sum(p.confidence for p in patterns if p.signal == "neutral")
        
        if bullish_score > bearish_score and bullish_score > neutral_score:
            return "bullish"
        elif bearish_score > bullish_score and bearish_score > neutral_score:
            return "bearish"
        else:
            return "neutral"
    
    def _generate_pattern_insights(
        self, 
        chart_patterns: List[PatternMatch], 
        candlestick_patterns: List[PatternMatch],
        confluence: float
    ) -> List[str]:
        """Generate key insights from pattern analysis"""
        insights = []
        
        # Pattern count insights
        if len(chart_patterns) > 0:
            insights.append(f"Detected {len(chart_patterns)} chart pattern(s)")
        
        if len(candlestick_patterns) > 0:
            insights.append(f"Found {len(candlestick_patterns)} candlestick pattern(s)")
        
        # Confluence insights
        if confluence > 80:
            insights.append("Strong pattern confluence - high reliability")
        elif confluence > 60:
            insights.append("Moderate pattern agreement")
        elif confluence < 40:
            insights.append("Mixed pattern signals - exercise caution")
        
        # Strongest patterns
        all_patterns = chart_patterns + candlestick_patterns
        strong_patterns = [p for p in all_patterns if p.confidence > 75]
        
        if strong_patterns:
            strongest = max(strong_patterns, key=lambda p: p.confidence)
            insights.append(f"Strongest pattern: {strongest.pattern_name} ({strongest.confidence:.0f}%)")
        
        # Reversal vs continuation
        reversal_patterns = [p for p in all_patterns if "reversal" in p.description.lower()]
        if reversal_patterns:
            insights.append("Reversal patterns detected - trend change possible")
        
        return insights if insights else ["No significant patterns detected"]

# Global instance
pattern_recognition_engine = PatternRecognitionEngine()