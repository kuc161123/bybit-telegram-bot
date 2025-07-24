#!/usr/bin/env python3
"""
Integration tests for Enhanced Market Analysis System (Phases 1-4)
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_analysis.market_status_engine_enhanced import enhanced_market_status_engine
from market_analysis.sentiment_aggregator import sentiment_aggregator, SentimentData
from execution.ai_reasoning_engine_enhanced import get_enhanced_reasoning_engine


class TestEnhancedMarketAnalysisIntegration:
    """Integration tests for the complete enhanced market analysis system"""
    
    @pytest.fixture
    def mock_bybit_client(self):
        """Mock Bybit client responses"""
        client = MagicMock()
        
        # Mock ticker response
        client.get_tickers.return_value = {
            "retCode": 0,
            "result": {
                "list": [{
                    "symbol": "BTCUSDT",
                    "lastPrice": "100000",
                    "price24hPcnt": "0.025",
                    "volume24h": "50000000",
                    "highPrice24h": "101000",
                    "lowPrice24h": "99000",
                    "turnover24h": "5000000000",
                    "fundingRate": "0.0001"
                }]
            }
        }
        
        # Mock kline response
        kline_data = []
        for i in range(100):
            kline_data.append([
                str(1640000000 + i * 300),
                str(100000 + i * 10),
                str(100100 + i * 10),
                str(99900 + i * 10),
                str(100050 + i * 10),
                str(1000 + i)
            ])
        
        client.get_kline.return_value = {
            "retCode": 0,
            "result": {
                "list": kline_data
            }
        }
        
        # Mock orderbook response
        client.get_orderbook.return_value = {
            "retCode": 0,
            "result": {
                "b": [["99950", "10"], ["99940", "20"]],
                "a": [["100050", "12"], ["100060", "15"]]
            }
        }
        
        # Mock open interest response
        client.get_open_interest.return_value = {
            "retCode": 0,
            "result": {
                "list": [
                    {"openInterest": "1000000", "timestamp": "1640000000000"},
                    {"openInterest": "1100000", "timestamp": "1640000300000"}
                ]
            }
        }
        
        # Mock funding rate history
        client.get_funding_rate_history.return_value = {
            "retCode": 0,
            "result": {
                "list": [{"fundingRate": "0.0001"}]
            }
        }
        
        return client
    
    @pytest.fixture
    def mock_ai_client(self):
        """Mock AI client for testing"""
        ai_client = MagicMock()
        ai_client.llm_provider = "openai"
        
        # Mock GPT-4 response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """RECOMMENDATION: HOLD
REASONING: Market shows mixed signals with neutral sentiment and volatile conditions. Technical indicators suggest ranging behavior.
CONFIDENCE_DRIVERS: Multi-timeframe alignment, stable sentiment
RISK: MEDIUM
TIMEFRAME: 1-2 weeks"""
        
        ai_client.client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        return ai_client
    
    @pytest.fixture
    def mock_fear_greed_response(self):
        """Mock Fear & Greed Index API response"""
        return {
            "data": [{
                "value": "65",
                "value_classification": "Greed",
                "timestamp": "1640000000"
            }]
        }
    
    @pytest.mark.asyncio
    async def test_full_market_analysis_pipeline(self, mock_bybit_client, mock_ai_client):
        """Test the complete market analysis pipeline"""
        with patch('clients.bybit_client.bybit_client', mock_bybit_client), \
             patch('clients.ai_client.get_ai_client', return_value=mock_ai_client):
            
            # Run full analysis
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=True
            )
            
            # Verify all components integrated
            assert status.symbol == "BTCUSDT"
            assert status.current_price > 0
            assert status.sentiment_score >= 0
            assert status.volatility_level in ["Very Low", "Low", "Normal", "High", "Very High", "Extreme"]
            assert status.market_regime in [
                "Bull Market", "Bear Market", "Ranging Market", "Volatile Market",
                "Accumulation", "Distribution", "Breakout", "Breakdown"
            ]
            assert status.confidence > 0
            assert status.data_quality > 0
    
    @pytest.mark.asyncio
    async def test_sentiment_integration(self, mock_bybit_client, mock_fear_greed_response):
        """Test real sentiment data integration"""
        with patch('clients.bybit_client.bybit_client', mock_bybit_client):
            # Mock Fear & Greed API
            async def mock_get(*args, **kwargs):
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value=mock_fear_greed_response)
                return mock_resp
            
            with patch('aiohttp.ClientSession.get', mock_get):
                async with sentiment_aggregator as aggregator:
                    sentiment = await aggregator.get_aggregated_sentiment(
                        symbol="BTCUSDT",
                        include_social=False
                    )
                    
                    # Verify sentiment data
                    assert sentiment.overall_score > 0
                    assert sentiment.overall_label in [
                        "Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"
                    ]
                    assert sentiment.fear_greed_score == 65.0
                    assert len(sentiment.sources_used) > 0
    
    @pytest.mark.asyncio
    async def test_pattern_recognition_integration(self, mock_bybit_client):
        """Test pattern recognition integration"""
        from market_analysis.pattern_recognition import pattern_recognition_engine
        
        with patch('clients.bybit_client.bybit_client', mock_bybit_client):
            # Get kline data
            kline_response = mock_bybit_client.get_kline()
            kline_data = {
                "5m": kline_response["result"]["list"],
                "15m": kline_response["result"]["list"][::3],
                "1h": kline_response["result"]["list"][::12]
            }
            
            # Analyze patterns
            pattern_analysis = await pattern_recognition_engine.analyze_patterns(
                symbol="BTCUSDT",
                kline_data=kline_data,
                current_price=100000
            )
            
            # Verify pattern analysis
            assert pattern_analysis.pattern_count >= 0
            assert pattern_analysis.dominant_signal in ["bullish", "bearish", "neutral"]
            assert 0 <= pattern_analysis.pattern_confluence <= 100
            assert len(pattern_analysis.key_insights) > 0
    
    @pytest.mark.asyncio
    async def test_enhanced_ai_reasoning_integration(
        self, mock_bybit_client, mock_ai_client
    ):
        """Test enhanced AI reasoning with patterns and context"""
        with patch('clients.bybit_client.bybit_client', mock_bybit_client), \
             patch('clients.ai_client.get_ai_client', return_value=mock_ai_client):
            
            enhanced_engine = get_enhanced_reasoning_engine(mock_ai_client)
            
            # Prepare test data
            market_data = {
                "current_price": 100000,
                "price_change_24h": 2.5,
                "volume_24h": 50000000
            }
            
            technical_signals = {
                "rsi": 65,
                "macd": 0.1,
                "macd_signal": 0.05,
                "sma_20": 99500,
                "sma_50": 98000,
                "volume_ratio": 1.2
            }
            
            # Run enhanced reasoning
            recommendation, reasoning, confidence, risk = await enhanced_engine.analyze_with_enhanced_reasoning(
                symbol="BTCUSDT",
                market_data=market_data,
                technical_signals=technical_signals,
                market_regime="volatile_market",
                current_confidence=70.0,
                kline_data={"5m": [], "15m": [], "1h": []},
                sentiment_data={"overall_score": 65}
            )
            
            # Verify enhanced results
            assert recommendation in ["BUY", "HOLD", "SELL"]
            assert confidence > 70.0  # Should be enhanced
            assert risk in ["LOW", "MEDIUM", "HIGH"]
            assert len(reasoning) > 0
    
    @pytest.mark.asyncio
    async def test_cache_performance(self, mock_bybit_client):
        """Test caching performance across components"""
        with patch('clients.bybit_client.bybit_client', mock_bybit_client):
            # First call - should calculate
            start_time = datetime.now()
            status1 = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=False
            )
            first_call_time = (datetime.now() - start_time).total_seconds()
            
            # Second call - should use cache
            start_time = datetime.now()
            status2 = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=False
            )
            cached_call_time = (datetime.now() - start_time).total_seconds()
            
            # Cache should be significantly faster
            assert cached_call_time < first_call_time / 10
            
            # Results should be identical
            assert status1.confidence == status2.confidence
            assert status1.sentiment_score == status2.sentiment_score
    
    @pytest.mark.asyncio
    async def test_error_handling_and_fallbacks(self):
        """Test error handling and fallback mechanisms"""
        # Test with failing Bybit client
        failing_client = MagicMock()
        failing_client.get_tickers.side_effect = Exception("API Error")
        failing_client.get_kline.side_effect = Exception("API Error")
        
        with patch('clients.bybit_client.bybit_client', failing_client):
            # Should still return valid status with fallbacks
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=False
            )
            
            # Verify fallback values
            assert status.symbol == "BTCUSDT"
            assert status.confidence == 0.0
            assert status.analysis_depth == "Basic"
            assert "fallback" in status.data_sources
    
    @pytest.mark.asyncio
    async def test_multi_timeframe_confluence(self, mock_bybit_client):
        """Test multi-timeframe analysis confluence"""
        with patch('clients.bybit_client.bybit_client', mock_bybit_client):
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=False
            )
            
            # Check timeframe analysis
            assert status.timeframe_alignment is not None
            assert status.timeframe_confluence >= 0
            
            # If multiple timeframes align, confluence should be high
            if status.timeframe_alignment:
                aligned_count = sum(
                    1 for tf, direction in status.timeframe_alignment.items()
                    if direction == list(status.timeframe_alignment.values())[0]
                )
                if aligned_count > len(status.timeframe_alignment) / 2:
                    assert status.timeframe_confluence > 50
    
    @pytest.mark.asyncio
    async def test_adaptive_thresholds(self, mock_bybit_client):
        """Test adaptive threshold functionality"""
        from market_analysis.market_regime_detector_enhanced import enhanced_market_regime_detector
        
        with patch('clients.bybit_client.bybit_client', mock_bybit_client):
            # First analysis to establish baseline
            status1 = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=False
            )
            
            # Check adaptive thresholds confidence
            assert status1.adaptive_thresholds_confidence >= 0
            
            # Multiple analyses should increase threshold confidence
            for _ in range(3):
                await enhanced_market_status_engine.get_enhanced_market_status(
                    symbol="BTCUSDT",
                    enable_ai_analysis=False
                )
            
            # Later analysis should have adapted thresholds
            status2 = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=False
            )
            
            # Adaptive system should be learning
            assert status2.adaptive_thresholds_confidence >= status1.adaptive_thresholds_confidence


@pytest.mark.asyncio
class TestPerformanceBenchmarks:
    """Performance benchmarking tests"""
    
    async def test_analysis_time_benchmarks(self, mock_bybit_client):
        """Test analysis time meets performance targets"""
        import time
        
        with patch('clients.bybit_client.bybit_client', mock_bybit_client):
            # Measure uncached analysis time
            start = time.time()
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="PERFTEST",
                enable_ai_analysis=False
            )
            analysis_time = time.time() - start
            
            # Should complete within reasonable time
            assert analysis_time < 10.0  # 10 seconds max
            
            # Cached should be sub-second
            start = time.time()
            cached_status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="PERFTEST",
                enable_ai_analysis=False
            )
            cache_time = time.time() - start
            
            assert cache_time < 0.1  # 100ms max for cached
    
    async def test_memory_usage(self):
        """Test memory usage stays reasonable"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Run multiple analyses
        for i in range(10):
            await enhanced_market_status_engine.get_enhanced_market_status(
                symbol=f"MEMTEST{i}USDT",
                enable_ai_analysis=False
            )
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable
        assert memory_increase < 100  # Less than 100MB increase


@pytest.mark.asyncio
class TestAccuracyMetrics:
    """Accuracy and quality metric tests"""
    
    async def test_confidence_score_accuracy(self, mock_bybit_client):
        """Test confidence score reflects data quality"""
        with patch('clients.bybit_client.bybit_client', mock_bybit_client):
            # Full data should give high confidence
            status_full = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=False
            )
            
            # Mock limited data
            mock_bybit_client.get_kline.return_value = {
                "retCode": 0,
                "result": {"list": []}  # Empty kline data
            }
            
            # Limited data should give low confidence
            status_limited = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT_LIMITED",
                enable_ai_analysis=False
            )
            
            assert status_full.confidence > status_limited.confidence
            assert status_full.data_quality > status_limited.data_quality
    
    async def test_analysis_depth_classification(self, mock_bybit_client):
        """Test analysis depth classification"""
        with patch('clients.bybit_client.bybit_client', mock_bybit_client):
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol="BTCUSDT",
                enable_ai_analysis=False
            )
            
            # Should classify depth based on confidence and data
            if status.confidence > 80 and status.data_quality > 80:
                assert status.analysis_depth in ["Comprehensive", "Advanced"]
            elif status.confidence > 50:
                assert status.analysis_depth in ["Standard", "Comprehensive"]
            else:
                assert status.analysis_depth == "Basic"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])