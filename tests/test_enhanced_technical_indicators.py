#!/usr/bin/env python3
"""
Unit tests for Enhanced Technical Indicators (Phase 1)
"""
import pytest
import numpy as np
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from market_analysis.technical_indicators_enhanced import (
    enhanced_technical_analysis_engine,
    EnhancedTechnicalIndicators
)


class TestEnhancedTechnicalIndicators:
    """Test suite for enhanced technical indicators"""
    
    @pytest.fixture
    def sample_kline_data(self):
        """Sample kline data for testing"""
        # Generate sample OHLCV data
        klines = []
        base_price = 100000
        
        for i in range(100):
            open_price = base_price + i * 100
            close_price = open_price + 50
            high_price = close_price + 30
            low_price = open_price - 20
            volume = 1000 + i * 10
            
            klines.append([
                1640000000 + i * 300,  # timestamp
                open_price,
                high_price,
                low_price,
                close_price,
                volume
            ])
        
        return {
            "1h": klines,
            "4h": klines[::4],
            "1d": klines[::24]
        }
    
    @pytest.fixture
    def sample_orderbook_data(self):
        """Sample orderbook data for testing"""
        return {
            "b": [  # Bids
                ["100500", "10"],
                ["100400", "20"],
                ["100300", "15"]
            ],
            "a": [  # Asks
                ["100600", "12"],
                ["100700", "18"],
                ["100800", "25"]
            ]
        }
    
    @pytest.mark.asyncio
    async def test_calculate_indicators_basic(self, sample_kline_data):
        """Test basic indicator calculation"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check that all required fields are present
        assert indicators.symbol == "BTCUSDT"
        assert indicators.timestamp is not None
        assert indicators.current_price == 105000
        
        # Check basic indicators
        assert indicators.sma_20 is not None
        assert indicators.sma_50 is not None
        assert indicators.ema_12 is not None
        assert indicators.ema_26 is not None
        
        # Check RSI is in valid range
        assert 0 <= indicators.rsi_14 <= 100
        
        # Check confidence score
        assert 0 <= indicators.confidence <= 100
    
    @pytest.mark.asyncio
    async def test_macd_calculation(self, sample_kline_data):
        """Test MACD calculation with signal line"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check MACD components
        assert indicators.macd is not None
        assert indicators.macd_signal is not None
        assert indicators.macd_histogram is not None
        
        # MACD histogram should be the difference
        expected_histogram = indicators.macd - indicators.macd_signal
        assert abs(indicators.macd_histogram - expected_histogram) < 0.01
        
        # Check divergence detection
        assert indicators.macd_divergence in [None, "Bullish", "Bearish"]
    
    @pytest.mark.asyncio
    async def test_vwap_calculation(self, sample_kline_data):
        """Test VWAP calculation"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check VWAP components
        assert indicators.vwap is not None
        assert indicators.vwap > 0
        
        # VWAP should be within reasonable range of price
        price_diff_pct = abs(indicators.vwap - indicators.current_price) / indicators.current_price
        assert price_diff_pct < 0.2  # Within 20% of current price
        
        # Check VWAP bands if calculated
        if indicators.vwap_upper:
            assert indicators.vwap_upper > indicators.vwap
            assert indicators.vwap_lower < indicators.vwap
    
    @pytest.mark.asyncio
    async def test_market_profile_calculation(self, sample_kline_data):
        """Test market profile calculation"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check market profile components
        assert indicators.poc is not None  # Point of Control
        assert indicators.vah is not None  # Value Area High
        assert indicators.val is not None  # Value Area Low
        
        # Validate relationships
        assert indicators.val <= indicators.poc <= indicators.vah
        
        # Check volume nodes
        assert isinstance(indicators.volume_nodes, list)
        if indicators.volume_nodes:
            # Each node should have price and strength
            for node in indicators.volume_nodes:
                assert "price" in node
                assert "strength" in node
                assert 0 <= node["strength"] <= 10
    
    @pytest.mark.asyncio
    async def test_cumulative_delta_calculation(self, sample_kline_data):
        """Test cumulative delta calculation"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check cumulative delta
        assert indicators.cumulative_delta is not None
        assert isinstance(indicators.cumulative_delta, (int, float))
        
        # Check delta trend
        assert indicators.delta_trend in ["Bullish", "Bearish", "Neutral"]
    
    @pytest.mark.asyncio
    async def test_support_resistance_detection(self, sample_kline_data):
        """Test support and resistance level detection"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check major levels
        assert indicators.major_support is not None
        assert indicators.major_resistance is not None
        
        # Support should be below current price, resistance above
        assert indicators.major_support < indicators.current_price
        assert indicators.major_resistance > indicators.current_price
        
        # Check support/resistance levels list
        assert isinstance(indicators.support_levels, list)
        assert isinstance(indicators.resistance_levels, list)
        
        # Levels should be sorted
        if len(indicators.support_levels) > 1:
            assert indicators.support_levels == sorted(indicators.support_levels, reverse=True)
        if len(indicators.resistance_levels) > 1:
            assert indicators.resistance_levels == sorted(indicators.resistance_levels)
    
    @pytest.mark.asyncio
    async def test_microstructure_analysis(self, sample_kline_data, sample_orderbook_data):
        """Test market microstructure analysis"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000,
            orderbook_data=sample_orderbook_data
        )
        
        # Microstructure should be calculated when orderbook provided
        assert indicators.bid_ask_spread is not None
        assert indicators.order_book_imbalance is not None
        assert indicators.liquidity_score is not None
        
        # Validate ranges
        assert indicators.bid_ask_spread >= 0
        assert -100 <= indicators.order_book_imbalance <= 100
        assert 0 <= indicators.liquidity_score <= 100
    
    @pytest.mark.asyncio
    async def test_volatility_metrics(self, sample_kline_data):
        """Test volatility calculations"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check ATR
        assert indicators.atr_14 is not None
        assert indicators.atr_14 > 0
        
        # Check volatility percentile
        assert indicators.volatility_percentile is not None
        assert 0 <= indicators.volatility_percentile <= 100
        
        # Check Bollinger Bands
        assert indicators.bb_upper > indicators.sma_20
        assert indicators.bb_lower < indicators.sma_20
        assert indicators.bb_width > 0
    
    @pytest.mark.asyncio
    async def test_trend_analysis(self, sample_kline_data):
        """Test trend strength and direction analysis"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check trend metrics
        assert indicators.trend_strength is not None
        assert -100 <= indicators.trend_strength <= 100
        
        # Check trend consistency
        assert indicators.trend_consistency is not None
        assert 0 <= indicators.trend_consistency <= 1
    
    @pytest.mark.asyncio
    async def test_momentum_indicators(self, sample_kline_data):
        """Test momentum indicator calculations"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check momentum score
        assert indicators.momentum_score is not None
        assert -100 <= indicators.momentum_score <= 100
        
        # Check stochastic if calculated
        if hasattr(indicators, 'stoch_k') and indicators.stoch_k:
            assert 0 <= indicators.stoch_k <= 100
            if hasattr(indicators, 'stoch_d') and indicators.stoch_d:
                assert 0 <= indicators.stoch_d <= 100
    
    @pytest.mark.asyncio
    async def test_volume_analysis(self, sample_kline_data):
        """Test volume-based indicators"""
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=sample_kline_data,
            current_price=105000,
            volume_24h=50000000
        )
        
        # Check volume metrics
        assert indicators.volume_sma is not None
        assert indicators.volume_sma > 0
        
        assert indicators.volume_ratio is not None
        assert indicators.volume_ratio > 0
        
        assert indicators.volume_strength is not None
        assert 0 <= indicators.volume_strength <= 100
    
    @pytest.mark.asyncio
    async def test_edge_cases(self):
        """Test edge cases and error handling"""
        # Test with minimal data
        minimal_klines = {
            "1h": [[1640000000, 100000, 100100, 99900, 100050, 1000]]
        }
        
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=minimal_klines,
            current_price=100000,
            volume_24h=1000000
        )
        
        # Should still return valid indicators with lower confidence
        assert indicators is not None
        assert indicators.confidence < 50  # Low confidence due to minimal data
        
        # Test with empty data
        empty_klines = {"1h": [], "4h": [], "1d": []}
        
        indicators = await enhanced_technical_analysis_engine.calculate_indicators(
            symbol="BTCUSDT",
            kline_data=empty_klines,
            current_price=100000,
            volume_24h=1000000
        )
        
        # Should return minimal valid indicators
        assert indicators is not None
        assert indicators.confidence == 0  # No confidence with no data
    
    def test_indicator_relationships(self):
        """Test logical relationships between indicators"""
        # Create a known uptrend scenario
        uptrend_klines = []
        for i in range(50):
            price = 100000 + i * 500  # Clear uptrend
            uptrend_klines.append([
                1640000000 + i * 300,
                price,
                price + 100,
                price - 50,
                price + 80,
                1000
            ])
        
        # This would be an async test in real implementation
        # Just showing the logical checks that should be done
        
        # In an uptrend:
        # - SMA20 should be above SMA50
        # - RSI should be above 50
        # - MACD should be positive
        # - Trend strength should be positive
        # - Momentum should be positive
        pass


@pytest.mark.asyncio
class TestMACDHistoricalTracking:
    """Test MACD historical tracking functionality"""
    
    async def test_macd_history_initialization(self):
        """Test MACD history is properly initialized"""
        engine = enhanced_technical_analysis_engine
        
        # Clear any existing history
        engine.macd_history.clear()
        
        # Calculate indicators for a new symbol
        kline_data = {"1h": [[1640000000, 100000, 100100, 99900, 100050, 1000]] * 30}
        
        await engine.calculate_indicators(
            symbol="TESTUSDT",
            kline_data=kline_data,
            current_price=100000,
            volume_24h=1000000
        )
        
        # Check history was created
        assert "TESTUSDT" in engine.macd_history
        assert isinstance(engine.macd_history["TESTUSDT"], list)
        assert len(engine.macd_history["TESTUSDT"]) > 0
    
    async def test_macd_history_limit(self):
        """Test MACD history respects size limit"""
        engine = enhanced_technical_analysis_engine
        
        # Set a small limit for testing
        original_limit = engine.macd_history_limit
        engine.macd_history_limit = 10
        
        try:
            # Add more than limit
            for i in range(20):
                kline_data = {"1h": [[1640000000 + i * 3600, 100000 + i * 100, 100100, 99900, 100050, 1000]] * 30}
                
                await engine.calculate_indicators(
                    symbol="LIMITTEST",
                    kline_data=kline_data,
                    current_price=100000,
                    volume_24h=1000000
                )
            
            # Check history doesn't exceed limit
            assert len(engine.macd_history.get("LIMITTEST", [])) <= engine.macd_history_limit
            
        finally:
            # Restore original limit
            engine.macd_history_limit = original_limit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])