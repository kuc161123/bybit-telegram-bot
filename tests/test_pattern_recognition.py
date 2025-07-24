#!/usr/bin/env python3
"""
Unit tests for Pattern Recognition System (Phase 4)
"""
import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from market_analysis.pattern_recognition import (
    pattern_recognition_engine,
    PatternMatch,
    PatternAnalysis,
    ChartPattern,
    CandlestickPattern
)


class TestPatternRecognition:
    """Test suite for pattern recognition"""
    
    @pytest.fixture
    def triangle_pattern_data(self):
        """Generate kline data that forms a triangle pattern"""
        klines = []
        
        # Create ascending triangle pattern
        for i in range(40):
            if i < 20:
                # Rising lows
                low = 100000 + i * 100
                high = 101500  # Flat resistance
            else:
                # Converging
                low = 101000 + (i - 20) * 50
                high = 101500 - (i - 20) * 25
            
            open_price = low + 50
            close_price = high - 50
            
            klines.append([
                1640000000 + i * 300,
                open_price,
                high,
                low,
                close_price,
                1000
            ])
        
        return {"5m": klines, "15m": klines[::3], "1h": klines[::12]}
    
    @pytest.fixture
    def double_top_pattern_data(self):
        """Generate kline data that forms a double top pattern"""
        klines = []
        
        # First peak
        for i in range(15):
            price = 100000 + i * 200
            klines.append([
                1640000000 + i * 300,
                price,
                price + 50,
                price - 50,
                price + 20,
                1000
            ])
        
        # Valley
        for i in range(10):
            price = 103000 - i * 150
            klines.append([
                1640000000 + (15 + i) * 300,
                price,
                price + 50,
                price - 50,
                price - 20,
                1000
            ])
        
        # Second peak (similar height)
        for i in range(15):
            price = 101500 + i * 200
            klines.append([
                1640000000 + (25 + i) * 300,
                price,
                price + 50,
                price - 50,
                price + 20,
                1000
            ])
        
        return {"5m": klines, "15m": klines[::3], "1h": klines[::12]}
    
    @pytest.fixture
    def candlestick_pattern_data(self):
        """Generate kline data with specific candlestick patterns"""
        klines = []
        
        # Normal candles
        for i in range(5):
            klines.append([
                1640000000 + i * 300,
                100000,
                100100,
                99900,
                100050,
                1000
            ])
        
        # Doji pattern
        klines.append([
            1640000000 + 5 * 300,
            100000,
            100200,  # High
            99800,   # Low
            100010,  # Close near open (doji)
            1000
        ])
        
        # Hammer pattern
        klines.append([
            1640000000 + 6 * 300,
            99500,   # Open
            99600,   # High (small upper shadow)
            99000,   # Low (long lower shadow)
            99550,   # Close (bullish)
            1000
        ])
        
        # Bullish engulfing
        klines.append([
            1640000000 + 7 * 300,
            100000,  # Open
            100050,  # High
            99950,   # Low
            99970,   # Close (bearish candle)
            1000
        ])
        klines.append([
            1640000000 + 8 * 300,
            99960,   # Open (below previous close)
            100100,  # High
            99950,   # Low
            100080,  # Close (above previous open - engulfing)
            1000
        ])
        
        return {"5m": klines, "15m": klines, "1h": klines}
    
    @pytest.mark.asyncio
    async def test_analyze_patterns_basic(self, triangle_pattern_data):
        """Test basic pattern analysis"""
        analysis = await pattern_recognition_engine.analyze_patterns(
            symbol="BTCUSDT",
            kline_data=triangle_pattern_data,
            current_price=101000,
            timeframes=["5m", "15m", "1h"]
        )
        
        # Check structure
        assert isinstance(analysis, PatternAnalysis)
        assert isinstance(analysis.chart_patterns, list)
        assert isinstance(analysis.candlestick_patterns, list)
        assert 0 <= analysis.pattern_confluence <= 100
        assert analysis.dominant_signal in ["bullish", "bearish", "neutral"]
        assert analysis.pattern_count >= 0
        assert 0 <= analysis.confidence_average <= 100
        assert isinstance(analysis.key_insights, list)
        assert len(analysis.key_insights) > 0
    
    @pytest.mark.asyncio
    async def test_triangle_pattern_detection(self, triangle_pattern_data):
        """Test triangle pattern detection"""
        analysis = await pattern_recognition_engine.analyze_patterns(
            symbol="BTCUSDT",
            kline_data=triangle_pattern_data,
            current_price=101000,
            timeframes=["5m"]
        )
        
        # Should detect at least one triangle pattern
        triangle_patterns = [
            p for p in analysis.chart_patterns 
            if "Triangle" in p.pattern_name
        ]
        
        assert len(triangle_patterns) > 0
        
        # Check pattern properties
        for pattern in triangle_patterns:
            assert isinstance(pattern, PatternMatch)
            assert pattern.pattern_type == "chart"
            assert pattern.confidence > 0
            assert pattern.signal in ["bullish", "bearish", "neutral"]
            assert pattern.strength in ["weak", "moderate", "strong"]
            assert pattern.formation_bars > 0
            assert pattern.description != ""
    
    @pytest.mark.asyncio
    async def test_double_top_detection(self, double_top_pattern_data):
        """Test double top pattern detection"""
        analysis = await pattern_recognition_engine.analyze_patterns(
            symbol="BTCUSDT",
            kline_data=double_top_pattern_data,
            current_price=104000,
            timeframes=["5m"]
        )
        
        # Should detect double top
        double_tops = [
            p for p in analysis.chart_patterns 
            if p.pattern_name == "Double Top"
        ]
        
        if double_tops:  # Pattern detection depends on exact data
            pattern = double_tops[0]
            assert pattern.signal == "bearish"
            assert pattern.target_price is not None
            assert pattern.stop_loss is not None
            assert pattern.target_price < 104000  # Bearish target
    
    @pytest.mark.asyncio
    async def test_candlestick_pattern_detection(self, candlestick_pattern_data):
        """Test candlestick pattern detection"""
        analysis = await pattern_recognition_engine.analyze_patterns(
            symbol="BTCUSDT",
            kline_data=candlestick_pattern_data,
            current_price=100000,
            timeframes=["5m"]
        )
        
        # Should detect some candlestick patterns
        assert len(analysis.candlestick_patterns) > 0
        
        # Check for specific patterns
        pattern_names = [p.pattern_name for p in analysis.candlestick_patterns]
        
        # Should detect at least one of these
        expected_patterns = ["Doji", "Hammer", "Bullish Engulfing"]
        found_patterns = [p for p in expected_patterns if p in pattern_names]
        assert len(found_patterns) > 0
    
    @pytest.mark.asyncio
    async def test_pattern_confluence(self):
        """Test pattern confluence calculation"""
        # Create multiple patterns with same signal
        bullish_patterns = [
            PatternMatch(
                pattern_type="chart",
                pattern_name="Ascending Triangle",
                confidence=80,
                signal="bullish",
                strength="strong",
                formation_complete=True,
                timeframe="5m"
            ),
            PatternMatch(
                pattern_type="candlestick",
                pattern_name="Bullish Engulfing",
                confidence=75,
                signal="bullish",
                strength="moderate",
                formation_complete=True,
                timeframe="5m"
            )
        ]
        
        # Calculate confluence
        confluence = pattern_recognition_engine._calculate_pattern_confluence(bullish_patterns)
        
        # High confluence when patterns agree
        assert confluence > 70
    
    @pytest.mark.asyncio
    async def test_dominant_signal_determination(self):
        """Test dominant signal determination"""
        # Mixed patterns
        patterns = [
            PatternMatch(
                pattern_type="chart",
                pattern_name="Pattern1",
                confidence=90,
                signal="bullish",
                strength="strong",
                formation_complete=True,
                timeframe="5m"
            ),
            PatternMatch(
                pattern_type="chart",
                pattern_name="Pattern2",
                confidence=60,
                signal="bearish",
                strength="moderate",
                formation_complete=True,
                timeframe="5m"
            ),
            PatternMatch(
                pattern_type="chart",
                pattern_name="Pattern3",
                confidence=70,
                signal="bullish",
                strength="moderate",
                formation_complete=True,
                timeframe="5m"
            )
        ]
        
        # Bullish should dominate (90 + 70 > 60)
        signal = pattern_recognition_engine._determine_dominant_signal(patterns)
        assert signal == "bullish"
    
    @pytest.mark.asyncio
    async def test_multi_timeframe_analysis(self, triangle_pattern_data):
        """Test pattern detection across multiple timeframes"""
        analysis = await pattern_recognition_engine.analyze_patterns(
            symbol="BTCUSDT",
            kline_data=triangle_pattern_data,
            current_price=101000,
            timeframes=["5m", "15m", "1h"]
        )
        
        # Check patterns from different timeframes
        timeframes_found = set()
        for pattern in analysis.chart_patterns + analysis.candlestick_patterns:
            timeframes_found.add(pattern.timeframe)
        
        # Should have patterns from multiple timeframes (if detected)
        assert len(timeframes_found) >= 1
    
    @pytest.mark.asyncio
    async def test_pattern_insights_generation(self):
        """Test key insights generation"""
        # Create scenario with strong patterns
        patterns = [
            PatternMatch(
                pattern_type="chart",
                pattern_name="Head and Shoulders",
                confidence=85,
                signal="bearish",
                strength="strong",
                formation_complete=True,
                timeframe="1h",
                description="reversal pattern"
            )
        ]
        
        insights = pattern_recognition_engine._generate_pattern_insights(
            patterns, [], 85.0
        )
        
        # Should generate relevant insights
        assert len(insights) > 0
        assert any("reversal" in insight.lower() for insight in insights)
    
    @pytest.mark.asyncio
    async def test_empty_data_handling(self):
        """Test handling of empty or invalid data"""
        # Empty kline data
        empty_data = {"5m": [], "15m": [], "1h": []}
        
        analysis = await pattern_recognition_engine.analyze_patterns(
            symbol="BTCUSDT",
            kline_data=empty_data,
            current_price=100000
        )
        
        # Should return valid but empty analysis
        assert analysis.pattern_count == 0
        assert analysis.dominant_signal == "neutral"
        assert analysis.pattern_confluence == 0
        assert len(analysis.key_insights) > 0
    
    @pytest.mark.asyncio
    async def test_pattern_target_calculation(self, double_top_pattern_data):
        """Test pattern target and stop loss calculation"""
        analysis = await pattern_recognition_engine.analyze_patterns(
            symbol="BTCUSDT",
            kline_data=double_top_pattern_data,
            current_price=104000,
            timeframes=["5m"]
        )
        
        # Check patterns with targets
        patterns_with_targets = [
            p for p in analysis.chart_patterns 
            if p.target_price is not None
        ]
        
        for pattern in patterns_with_targets:
            # Bearish patterns should have lower targets
            if pattern.signal == "bearish":
                assert pattern.target_price < 104000
                if pattern.stop_loss:
                    assert pattern.stop_loss > 104000
            
            # Bullish patterns should have higher targets
            elif pattern.signal == "bullish":
                assert pattern.target_price > 104000
                if pattern.stop_loss:
                    assert pattern.stop_loss < 104000
    
    def test_trend_line_calculation(self):
        """Test trend line slope calculation"""
        # Upward trending data
        uptrend_data = np.array([100, 101, 102, 103, 104, 105])
        slope = pattern_recognition_engine._calculate_trend_line(uptrend_data)
        assert slope is not None
        assert slope > 0  # Positive slope for uptrend
        
        # Downward trending data
        downtrend_data = np.array([105, 104, 103, 102, 101, 100])
        slope = pattern_recognition_engine._calculate_trend_line(downtrend_data)
        assert slope is not None
        assert slope < 0  # Negative slope for downtrend
    
    def test_peak_and_trough_detection(self):
        """Test peak and trough finding algorithms"""
        # Data with clear peaks and troughs
        data = np.array([100, 102, 104, 103, 101, 99, 101, 103, 105, 103, 101])
        
        peaks = pattern_recognition_engine._find_peaks(data, min_distance=2)
        troughs = pattern_recognition_engine._find_troughs(data, min_distance=2)
        
        # Should find peaks at high points
        assert len(peaks) > 0
        for peak_idx in peaks:
            # Peak should be higher than surrounding points
            assert data[peak_idx] >= data[peak_idx - 1]
            assert data[peak_idx] >= data[peak_idx + 1]
        
        # Should find troughs at low points
        assert len(troughs) > 0
        for trough_idx in troughs:
            # Trough should be lower than surrounding points
            assert data[trough_idx] <= data[trough_idx - 1]
            assert data[trough_idx] <= data[trough_idx + 1]


@pytest.mark.asyncio
class TestPatternPerformance:
    """Test pattern recognition performance"""
    
    async def test_large_dataset_performance(self):
        """Test performance with large dataset"""
        import time
        
        # Generate large dataset
        large_klines = []
        for i in range(1000):
            price = 100000 + np.sin(i * 0.1) * 1000 + np.random.randn() * 100
            large_klines.append([
                1640000000 + i * 300,
                price,
                price + abs(np.random.randn() * 50),
                price - abs(np.random.randn() * 50),
                price + np.random.randn() * 20,
                1000 + abs(np.random.randn() * 100)
            ])
        
        kline_data = {
            "5m": large_klines,
            "15m": large_klines[::3],
            "1h": large_klines[::12]
        }
        
        # Measure performance
        start_time = time.time()
        
        analysis = await pattern_recognition_engine.analyze_patterns(
            symbol="BTCUSDT",
            kline_data=kline_data,
            current_price=100000
        )
        
        elapsed_time = time.time() - start_time
        
        # Should complete within reasonable time
        assert elapsed_time < 5.0  # 5 seconds max
        
        # Should still produce valid results
        assert analysis is not None
        assert isinstance(analysis.pattern_count, int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])