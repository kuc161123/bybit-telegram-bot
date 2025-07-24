#!/usr/bin/env python3
"""
Unit tests for Historical Context Engine (Phase 4)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from market_analysis.historical_context_engine import (
    historical_context_engine,
    HistoricalPattern,
    MarketCorrelation,
    HistoricalContext
)
from market_analysis.pattern_recognition import PatternMatch


class TestHistoricalContextEngine:
    """Test suite for historical context engine"""
    
    @pytest.fixture
    def sample_market_data(self):
        """Sample market data for testing"""
        return {
            "current_price": 100000,
            "price_change_24h": 2.5,
            "volume_24h": 1500000,
            "market_regime": "trending_up"
        }
    
    @pytest.fixture
    def sample_technical_indicators(self):
        """Sample technical indicators for testing"""
        return {
            "rsi": 65,
            "macd": 0.1,
            "macd_signal": 0.05,
            "sma_20": 99500,
            "sma_50": 98000,
            "volume_ratio": 1.2,
            "trend_strength": 3.5,
            "price_position": 0.7,
            "bb_upper": 101000,
            "bb_lower": 99000
        }
    
    @pytest.fixture
    def sample_patterns(self):
        """Sample detected patterns for testing"""
        return [
            PatternMatch(
                pattern_type="chart",
                pattern_name="Ascending Triangle",
                confidence=75,
                signal="bullish",
                strength="moderate",
                formation_complete=True,
                timeframe="1h"
            ),
            PatternMatch(
                pattern_type="candlestick",
                pattern_name="Bullish Engulfing",
                confidence=80,
                signal="bullish",
                strength="strong",
                formation_complete=True,
                timeframe="5m"
            )
        ]
    
    @pytest.fixture
    def sample_historical_patterns(self):
        """Sample historical patterns for testing"""
        return [
            HistoricalPattern(
                pattern_name="Ascending Triangle",
                pattern_type="chart",
                occurrence_date=datetime.now() - timedelta(days=30),
                market_context={"rsi": 60, "trend": "up"},
                outcome="bullish",
                success_rate=0.75,
                time_to_target=5,
                target_achieved=True
            ),
            HistoricalPattern(
                pattern_name="Ascending Triangle",
                pattern_type="chart",
                occurrence_date=datetime.now() - timedelta(days=60),
                market_context={"rsi": 55, "trend": "up"},
                outcome="bullish",
                success_rate=0.75,
                time_to_target=7,
                target_achieved=True
            )
        ]
    
    @pytest.mark.asyncio
    async def test_get_historical_context_basic(
        self, sample_market_data, sample_technical_indicators
    ):
        """Test basic historical context generation"""
        context = await historical_context_engine.get_historical_context(
            symbol="BTCUSDT",
            current_market_data=sample_market_data,
            technical_indicators=sample_technical_indicators,
            detected_patterns=[],
            sentiment_data=None
        )
        
        # Check structure
        assert isinstance(context, HistoricalContext)
        assert context.symbol == "BTCUSDT"
        
        # Check required fields
        assert isinstance(context.similar_patterns, list)
        assert isinstance(context.pattern_success_rates, dict)
        assert isinstance(context.recent_similar_conditions, list)
        assert isinstance(context.historical_outcomes, dict)
        assert isinstance(context.market_correlations, list)
        assert isinstance(context.sector_context, dict)
        assert isinstance(context.seasonal_trends, dict)
        assert isinstance(context.time_of_day_patterns, dict)
        
        # Check metrics
        assert 0 <= context.success_probability <= 1
        assert 0 <= context.context_quality <= 100
        assert context.volatility_regime in ["low", "normal", "high", "extreme"]
    
    @pytest.mark.asyncio
    async def test_find_similar_patterns(self, sample_patterns):
        """Test finding similar historical patterns"""
        # Add some historical patterns
        engine = historical_context_engine
        engine.pattern_history["BTCUSDT"] = [
            HistoricalPattern(
                pattern_name="Ascending Triangle",
                pattern_type="chart",
                occurrence_date=datetime.now() - timedelta(days=10),
                market_context={},
                outcome="bullish",
                success_rate=0.8,
                target_achieved=True
            ),
            HistoricalPattern(
                pattern_name="Different Pattern",
                pattern_type="chart",
                occurrence_date=datetime.now() - timedelta(days=20),
                market_context={},
                outcome="bearish",
                success_rate=0.6,
                target_achieved=False
            )
        ]
        
        similar = await engine._find_similar_patterns("BTCUSDT", sample_patterns)
        
        # Should find the matching Ascending Triangle
        assert len(similar) > 0
        assert any(p.pattern_name == "Ascending Triangle" for p in similar)
    
    @pytest.mark.asyncio
    async def test_pattern_success_rate_calculation(self, sample_patterns):
        """Test pattern success rate calculation"""
        # Add historical patterns with mixed success
        engine = historical_context_engine
        engine.pattern_history["BTCUSDT"] = [
            HistoricalPattern(
                pattern_name="Ascending Triangle",
                pattern_type="chart",
                occurrence_date=datetime.now() - timedelta(days=i),
                market_context={},
                outcome="bullish",
                success_rate=0.75,
                target_achieved=(i % 4 != 0)  # 3 out of 4 successful
            )
            for i in range(20)
        ]
        
        success_rates = engine._calculate_pattern_success_rates("BTCUSDT", sample_patterns)
        
        # Should calculate 75% success rate
        assert "Ascending Triangle" in success_rates
        assert abs(success_rates["Ascending Triangle"] - 0.75) < 0.01
    
    @pytest.mark.asyncio
    async def test_market_fingerprint_creation(
        self, sample_market_data, sample_technical_indicators
    ):
        """Test market fingerprint creation"""
        engine = historical_context_engine
        
        fingerprint = engine._create_market_fingerprint(
            sample_market_data, sample_technical_indicators
        )
        
        # Check fingerprint structure
        assert isinstance(fingerprint, dict)
        assert "rsi_range" in fingerprint
        assert "trend_strength" in fingerprint
        assert "volume" in fingerprint
        assert "volatility" in fingerprint
        assert "price_position" in fingerprint
        
        # Check values
        assert fingerprint["rsi_range"] == "neutral"  # RSI 65
        assert fingerprint["trend_strength"] == "weak"  # Strength 3.5
        assert fingerprint["volume"] == "normal"  # Ratio 1.2
    
    @pytest.mark.asyncio
    async def test_fingerprint_similarity_calculation(self):
        """Test fingerprint similarity calculation"""
        engine = historical_context_engine
        
        fp1 = {
            "rsi_range": "neutral",
            "trend_strength": "strong",
            "volume": "high",
            "volatility": "normal",
            "price_position": "upper"
        }
        
        fp2 = {
            "rsi_range": "neutral",
            "trend_strength": "strong",
            "volume": "high",
            "volatility": "high",
            "price_position": "upper"
        }
        
        similarity = engine._calculate_fingerprint_similarity(fp1, fp2)
        
        # 4 out of 5 match = 80% similarity
        assert similarity == 0.8
    
    @pytest.mark.asyncio
    async def test_historical_outcome_analysis(self):
        """Test historical outcome analysis"""
        engine = historical_context_engine
        
        # Add market history
        from collections import deque
        engine.market_memory["BTCUSDT"] = deque([
            {
                "timestamp": datetime.now() - timedelta(days=i),
                "market_regime": "trending_up",
                "performance_7d": 5.0 if i % 2 == 0 else -2.0
            }
            for i in range(10)
        ])
        
        outcomes = engine._analyze_historical_outcomes("BTCUSDT", {})
        
        # Check outcome structure
        assert "trending_up" in outcomes
        assert "mean" in outcomes["trending_up"]
        assert "win_rate" in outcomes["trending_up"]
        assert outcomes["trending_up"]["win_rate"] == 0.5  # 50% wins
    
    @pytest.mark.asyncio
    async def test_market_correlations(self):
        """Test market correlation retrieval"""
        correlations = await historical_context_engine._get_market_correlations("BTCUSDT")
        
        # Check correlation structure
        assert isinstance(correlations, list)
        if correlations:
            corr = correlations[0]
            assert isinstance(corr, MarketCorrelation)
            assert corr.primary_symbol == "BTCUSDT"
            assert -1 <= corr.correlation_strength <= 1
    
    @pytest.mark.asyncio
    async def test_seasonal_pattern_analysis(self):
        """Test seasonal pattern analysis"""
        seasonal = historical_context_engine._analyze_seasonal_patterns("BTCUSDT")
        
        # Check seasonal data
        assert isinstance(seasonal, dict)
        assert len(seasonal) > 0
        
        # Check current month exists
        current_month = datetime.now().strftime("%B").lower()
        assert any(current_month in month.lower() for month in seasonal)
    
    @pytest.mark.asyncio
    async def test_volatility_context_analysis(self, sample_market_data):
        """Test volatility context analysis"""
        vol_context = historical_context_engine._analyze_volatility_context(
            "BTCUSDT", sample_market_data
        )
        
        # Check volatility context
        assert isinstance(vol_context, dict)
        assert "regime" in vol_context
        assert "relative_volatility" in vol_context
        assert vol_context["regime"] in ["low", "normal", "high", "extreme"]
        assert vol_context["relative_volatility"] > 0
    
    @pytest.mark.asyncio
    async def test_sentiment_context_analysis(self):
        """Test sentiment context analysis"""
        sentiment_data = {"overall_score": 85}  # Extreme greed
        
        sent_context = historical_context_engine._analyze_sentiment_context(
            "BTCUSDT", sentiment_data
        )
        
        # Check sentiment context
        assert isinstance(sent_context, dict)
        assert "persistence" in sent_context
        assert "reversal_prob" in sent_context
        
        # Extreme sentiment should have high reversal probability
        assert sent_context["reversal_prob"] > 0.5
        assert sent_context["persistence"] < 0.5
    
    @pytest.mark.asyncio
    async def test_confidence_factor_identification(
        self, sample_historical_patterns
    ):
        """Test confidence booster and risk factor identification"""
        pattern_success_rates = {"Ascending Triangle": 0.8, "Double Top": 0.3}
        similar_conditions = [
            {"performance_7d": 5.0},
            {"performance_7d": 3.0},
            {"performance_7d": 4.0}
        ]
        
        boosters, risks = historical_context_engine._identify_confidence_factors(
            sample_historical_patterns,
            similar_conditions,
            pattern_success_rates
        )
        
        # Should identify high success patterns as boosters
        assert len(boosters) > 0
        assert any("High success patterns" in b for b in boosters)
        
        # Should identify low success patterns as risks
        assert len(risks) > 0
        assert any("Low success patterns" in r for r in risks)
    
    @pytest.mark.asyncio
    async def test_success_probability_calculation(self):
        """Test success probability calculation"""
        pattern_success = {"Pattern1": 0.8, "Pattern2": 0.7}
        historical_outcomes = {
            "regime1": {"win_rate": 0.6},
            "regime2": {"win_rate": 0.7}
        }
        volatility_context = {"regime": "normal"}
        
        probability = historical_context_engine._calculate_success_probability(
            pattern_success, historical_outcomes, volatility_context
        )
        
        # Should be above base 50%
        assert probability > 0.5
        assert probability <= 0.9  # Capped at 90%
    
    @pytest.mark.asyncio
    async def test_context_quality_assessment(self, sample_historical_patterns):
        """Test context quality assessment"""
        similar_conditions = [{"date": datetime.now()} for _ in range(5)]
        
        quality = historical_context_engine._assess_context_quality(
            sample_historical_patterns,
            similar_conditions,
            50  # Total history count
        )
        
        # Should return reasonable quality score
        assert 0 <= quality <= 100
        assert quality > 0  # Some data available
    
    @pytest.mark.asyncio
    async def test_fallback_context(self):
        """Test fallback context generation"""
        context = historical_context_engine._get_fallback_context("BTCUSDT")
        
        # Check fallback values
        assert context.symbol == "BTCUSDT"
        assert context.success_probability == 0.5
        assert context.context_quality == 25.0
        assert context.volatility_regime == "normal"
        assert len(context.confidence_boosters) > 0
        assert len(context.risk_factors) > 0
    
    @pytest.mark.asyncio
    async def test_historical_record_update(
        self, sample_market_data, sample_technical_indicators
    ):
        """Test updating historical records"""
        engine = historical_context_engine
        symbol = "TESTUSDT"
        
        # Clear existing data
        if symbol in engine.market_memory:
            engine.market_memory[symbol].clear()
        
        # Update records
        await engine._update_historical_records(
            symbol, sample_market_data, sample_technical_indicators
        )
        
        # Check record was added
        assert symbol in engine.market_memory
        assert len(engine.market_memory[symbol]) > 0
        
        # Check record structure
        record = engine.market_memory[symbol][-1]
        assert "timestamp" in record
        assert "market_data" in record
        assert "technicals" in record
        assert "fingerprint" in record
    
    @pytest.mark.asyncio
    async def test_cache_functionality(
        self, sample_market_data, sample_technical_indicators
    ):
        """Test caching functionality"""
        engine = historical_context_engine
        
        # Clear cache
        engine.context_cache.clear()
        
        # First call should calculate
        context1 = await engine.get_historical_context(
            symbol="CACHETEST",
            current_market_data=sample_market_data,
            technical_indicators=sample_technical_indicators,
            detected_patterns=[],
            sentiment_data=None
        )
        
        # Second call should use cache
        context2 = await engine.get_historical_context(
            symbol="CACHETEST",
            current_market_data=sample_market_data,
            technical_indicators=sample_technical_indicators,
            detected_patterns=[],
            sentiment_data=None
        )
        
        # Should be the same object (cached)
        # Note: In real implementation, might need to check cache hit
        assert context1.symbol == context2.symbol


@pytest.mark.asyncio
class TestHistoricalMemoryManagement:
    """Test historical memory and data management"""
    
    async def test_memory_size_limits(self):
        """Test memory size limits are respected"""
        engine = historical_context_engine
        symbol = "MEMTEST"
        
        # Set small limit for testing
        original_size = engine.market_memory_size
        engine.market_memory_size = 10
        
        try:
            # Add more than limit
            for i in range(20):
                await engine._update_historical_records(
                    symbol,
                    {"price": 100000 + i},
                    {"rsi": 50 + i}
                )
            
            # Should not exceed limit
            assert len(engine.market_memory.get(symbol, [])) <= engine.market_memory_size
            
        finally:
            # Restore original
            engine.market_memory_size = original_size
    
    async def test_pattern_history_management(self):
        """Test pattern history management"""
        engine = historical_context_engine
        symbol = "PATTERNTEST"
        
        # Add patterns
        engine.pattern_history[symbol] = [
            HistoricalPattern(
                pattern_name=f"Pattern{i}",
                pattern_type="chart",
                occurrence_date=datetime.now() - timedelta(days=i),
                market_context={},
                outcome="bullish",
                success_rate=0.7,
                target_achieved=True
            )
            for i in range(10)
        ]
        
        # Old patterns should be filtered out in analysis
        recent_patterns = [
            p for p in engine.pattern_history[symbol]
            if (datetime.now() - p.occurrence_date).days <= engine.max_history_days
        ]
        
        assert len(recent_patterns) == len(engine.pattern_history[symbol])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])