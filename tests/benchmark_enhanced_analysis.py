#!/usr/bin/env python3
"""
Performance Benchmarking for Enhanced Market Analysis System
Measures and tracks performance metrics across all phases
"""
import asyncio
import time
import statistics
import json
from datetime import datetime
from typing import Dict, List, Tuple
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class EnhancedAnalysisBenchmark:
    """Comprehensive benchmarking for enhanced market analysis"""
    
    def __init__(self):
        self.results = {
            "technical_analysis": [],
            "pattern_recognition": [],
            "sentiment_aggregation": [],
            "historical_context": [],
            "ai_reasoning": [],
            "full_pipeline": [],
            "cache_performance": []
        }
        
    async def benchmark_technical_indicators(self, iterations: int = 10) -> Dict:
        """Benchmark Phase 1 - Enhanced Technical Indicators"""
        from market_analysis.technical_indicators_enhanced import enhanced_technical_analysis_engine
        
        logger.info("🔍 Benchmarking Enhanced Technical Indicators...")
        
        # Generate sample data
        kline_data = self._generate_sample_kline_data()
        
        times = []
        for i in range(iterations):
            start_time = time.time()
            
            indicators = await enhanced_technical_analysis_engine.calculate_indicators(
                symbol="BTCUSDT",
                kline_data=kline_data,
                current_price=100000,
                volume_24h=50000000
            )
            
            elapsed = time.time() - start_time
            times.append(elapsed)
            
            if i == 0:  # Log first result
                logger.info(f"  Indicators calculated with {indicators.confidence:.1f}% confidence")
        
        return {
            "component": "technical_indicators",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0
        }
    
    async def benchmark_pattern_recognition(self, iterations: int = 10) -> Dict:
        """Benchmark Phase 4 - Pattern Recognition"""
        from market_analysis.pattern_recognition import pattern_recognition_engine
        
        logger.info("📊 Benchmarking Pattern Recognition...")
        
        kline_data = self._generate_sample_kline_data()
        
        times = []
        pattern_counts = []
        
        for i in range(iterations):
            start_time = time.time()
            
            analysis = await pattern_recognition_engine.analyze_patterns(
                symbol="BTCUSDT",
                kline_data=kline_data,
                current_price=100000,
                timeframes=["5m", "15m", "1h"]
            )
            
            elapsed = time.time() - start_time
            times.append(elapsed)
            pattern_counts.append(analysis.pattern_count)
        
        return {
            "component": "pattern_recognition",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "avg_patterns_found": statistics.mean(pattern_counts)
        }
    
    async def benchmark_sentiment_aggregation(self, iterations: int = 5) -> Dict:
        """Benchmark Phase 3 - Sentiment Aggregation"""
        from market_analysis.sentiment_aggregator import sentiment_aggregator
        
        logger.info("📈 Benchmarking Sentiment Aggregation...")
        
        times = []
        
        async with sentiment_aggregator as aggregator:
            for i in range(iterations):
                start_time = time.time()
                
                sentiment = await aggregator.get_aggregated_sentiment(
                    symbol="BTCUSDT",
                    include_social=False  # Faster without social
                )
                
                elapsed = time.time() - start_time
                times.append(elapsed)
                
                if i == 0:
                    logger.info(f"  Sentiment: {sentiment.overall_label} ({sentiment.overall_score:.1f}/100)")
        
        return {
            "component": "sentiment_aggregation",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0
        }
    
    async def benchmark_historical_context(self, iterations: int = 10) -> Dict:
        """Benchmark Phase 4 - Historical Context"""
        from market_analysis.historical_context_engine import historical_context_engine
        
        logger.info("📚 Benchmarking Historical Context Engine...")
        
        market_data = {
            "current_price": 100000,
            "price_change_24h": 2.5,
            "volume_24h": 1500000
        }
        
        technical_indicators = {
            "rsi": 65,
            "macd": 0.1,
            "volume_ratio": 1.2
        }
        
        times = []
        
        for i in range(iterations):
            start_time = time.time()
            
            context = await historical_context_engine.get_historical_context(
                symbol="BTCUSDT",
                current_market_data=market_data,
                technical_indicators=technical_indicators,
                detected_patterns=[],
                sentiment_data=None
            )
            
            elapsed = time.time() - start_time
            times.append(elapsed)
            
            if i == 0:
                logger.info(f"  Context quality: {context.context_quality:.1f}%, Success probability: {context.success_probability:.2f}")
        
        return {
            "component": "historical_context",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0
        }
    
    async def benchmark_full_pipeline(self, iterations: int = 3) -> Dict:
        """Benchmark complete analysis pipeline"""
        from market_analysis.market_status_engine_enhanced import enhanced_market_status_engine
        
        logger.info("🚀 Benchmarking Full Pipeline...")
        
        times = []
        confidence_scores = []
        
        for i in range(iterations):
            # Clear cache for fair comparison
            enhanced_market_status_engine.cache.clear()
            
            start_time = time.time()
            
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol=f"BENCH{i}USDT",  # Different symbol to avoid cache
                enable_ai_analysis=False  # Exclude AI for consistent timing
            )
            
            elapsed = time.time() - start_time
            times.append(elapsed)
            confidence_scores.append(status.confidence)
            
            if i == 0:
                logger.info(f"  Market regime: {status.market_regime}, Confidence: {status.confidence:.1f}%")
        
        return {
            "component": "full_pipeline",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "avg_confidence": statistics.mean(confidence_scores)
        }
    
    async def benchmark_cache_performance(self) -> Dict:
        """Benchmark cache performance"""
        from market_analysis.market_status_engine_enhanced import enhanced_market_status_engine
        
        logger.info("💾 Benchmarking Cache Performance...")
        
        # First call - no cache
        enhanced_market_status_engine.cache.clear()
        start_time = time.time()
        
        status1 = await enhanced_market_status_engine.get_enhanced_market_status(
            symbol="CACHETEST",
            enable_ai_analysis=False
        )
        
        uncached_time = time.time() - start_time
        
        # Second call - cached
        start_time = time.time()
        
        status2 = await enhanced_market_status_engine.get_enhanced_market_status(
            symbol="CACHETEST",
            enable_ai_analysis=False
        )
        
        cached_time = time.time() - start_time
        
        speedup = uncached_time / cached_time if cached_time > 0 else 0
        
        logger.info(f"  Cache speedup: {speedup:.0f}x")
        
        return {
            "component": "cache_performance",
            "uncached_time": uncached_time,
            "cached_time": cached_time,
            "speedup_factor": speedup,
            "cache_efficiency": (1 - cached_time/uncached_time) * 100 if uncached_time > 0 else 0
        }
    
    async def benchmark_ai_reasoning(self, iterations: int = 3) -> Dict:
        """Benchmark AI reasoning performance"""
        from execution.ai_reasoning_engine_enhanced import get_enhanced_reasoning_engine
        from clients.ai_client import get_ai_client
        
        logger.info("🤖 Benchmarking AI Reasoning...")
        
        ai_client = get_ai_client()
        
        if ai_client.llm_provider == "stub":
            logger.info("  Skipping AI benchmark (stub client)")
            return {
                "component": "ai_reasoning",
                "status": "skipped",
                "reason": "stub_client"
            }
        
        enhanced_engine = get_enhanced_reasoning_engine(ai_client)
        
        times = []
        confidence_boosts = []
        
        market_data = {
            "current_price": 100000,
            "price_change_24h": 2.5,
            "volume_24h": 50000000
        }
        
        technical_signals = {
            "rsi": 65,
            "macd": 0.1,
            "volume_ratio": 1.2
        }
        
        for i in range(iterations):
            start_time = time.time()
            
            recommendation, reasoning, enhanced_confidence, risk = await enhanced_engine.analyze_with_enhanced_reasoning(
                symbol="BTCUSDT",
                market_data=market_data,
                technical_signals=technical_signals,
                market_regime="volatile_market",
                current_confidence=70.0,
                kline_data={"5m": [], "15m": [], "1h": []},
                sentiment_data=None
            )
            
            elapsed = time.time() - start_time
            times.append(elapsed)
            confidence_boosts.append(enhanced_confidence - 70.0)
            
            if i == 0:
                logger.info(f"  Recommendation: {recommendation}, Confidence boost: +{enhanced_confidence - 70.0:.1f}%")
        
        return {
            "component": "ai_reasoning",
            "iterations": iterations,
            "avg_time": statistics.mean(times),
            "min_time": min(times),
            "max_time": max(times),
            "std_dev": statistics.stdev(times) if len(times) > 1 else 0,
            "avg_confidence_boost": statistics.mean(confidence_boosts)
        }
    
    def _generate_sample_kline_data(self, size: int = 100) -> Dict:
        """Generate sample kline data for benchmarking"""
        import numpy as np
        
        klines = []
        base_price = 100000
        
        for i in range(size):
            # Generate realistic price movement
            price_change = np.sin(i * 0.1) * 500 + np.random.randn() * 100
            open_price = base_price + price_change
            close_price = open_price + np.random.randn() * 50
            high_price = max(open_price, close_price) + abs(np.random.randn() * 30)
            low_price = min(open_price, close_price) - abs(np.random.randn() * 30)
            volume = 1000 + abs(np.random.randn() * 200)
            
            klines.append([
                1640000000 + i * 300,
                open_price,
                high_price,
                low_price,
                close_price,
                volume
            ])
        
        return {
            "5m": klines,
            "15m": klines[::3],
            "1h": klines[::12],
            "4h": klines[::48],
            "1d": klines[::288]
        }
    
    async def run_all_benchmarks(self) -> Dict:
        """Run all benchmarks and compile results"""
        logger.info("\n" + "="*60)
        logger.info("🏃 Running Enhanced Market Analysis Benchmarks")
        logger.info("="*60 + "\n")
        
        # Run individual benchmarks
        results = []
        
        # Phase 1
        results.append(await self.benchmark_technical_indicators())
        
        # Phase 3
        results.append(await self.benchmark_sentiment_aggregation())
        
        # Phase 4
        results.append(await self.benchmark_pattern_recognition())
        results.append(await self.benchmark_historical_context())
        results.append(await self.benchmark_ai_reasoning())
        
        # Full system
        results.append(await self.benchmark_full_pipeline())
        results.append(await self.benchmark_cache_performance())
        
        # Compile summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "benchmarks": results,
            "summary": self._generate_summary(results)
        }
        
        # Save results
        self._save_results(summary)
        
        # Print summary
        self._print_summary(summary)
        
        return summary
    
    def _generate_summary(self, results: List[Dict]) -> Dict:
        """Generate benchmark summary"""
        total_time = sum(r.get("avg_time", 0) for r in results if "avg_time" in r)
        
        # Find slowest component
        slowest = max(
            (r for r in results if "avg_time" in r),
            key=lambda x: x["avg_time"],
            default=None
        )
        
        # Calculate cache efficiency
        cache_result = next((r for r in results if r["component"] == "cache_performance"), None)
        
        return {
            "total_avg_time": total_time,
            "slowest_component": slowest["component"] if slowest else None,
            "slowest_time": slowest["avg_time"] if slowest else 0,
            "cache_speedup": cache_result["speedup_factor"] if cache_result else 0,
            "components_tested": len(results)
        }
    
    def _save_results(self, summary: Dict):
        """Save benchmark results to file"""
        filename = f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        logger.info(f"\n📄 Results saved to: {filename}")
    
    def _print_summary(self, summary: Dict):
        """Print benchmark summary"""
        logger.info("\n" + "="*60)
        logger.info("📊 BENCHMARK SUMMARY")
        logger.info("="*60)
        
        for result in summary["benchmarks"]:
            if result.get("status") == "skipped":
                logger.info(f"\n{result['component']}: SKIPPED ({result['reason']})")
                continue
                
            logger.info(f"\n{result['component'].upper()}:")
            
            if "avg_time" in result:
                logger.info(f"  Average time: {result['avg_time']:.3f}s")
                logger.info(f"  Min/Max: {result['min_time']:.3f}s / {result['max_time']:.3f}s")
                
            if "speedup_factor" in result:
                logger.info(f"  Cache speedup: {result['speedup_factor']:.0f}x")
                logger.info(f"  Cache efficiency: {result.get('cache_efficiency', 0):.1f}%")
                
            if "avg_patterns_found" in result:
                logger.info(f"  Avg patterns found: {result['avg_patterns_found']:.1f}")
                
            if "avg_confidence" in result:
                logger.info(f"  Avg confidence: {result['avg_confidence']:.1f}%")
                
            if "avg_confidence_boost" in result:
                logger.info(f"  Avg confidence boost: +{result['avg_confidence_boost']:.1f}%")
        
        logger.info("\n" + "-"*60)
        logger.info("OVERALL PERFORMANCE:")
        logger.info(f"  Total components tested: {summary['summary']['components_tested']}")
        logger.info(f"  Total average time: {summary['summary']['total_avg_time']:.3f}s")
        logger.info(f"  Slowest component: {summary['summary']['slowest_component']}")
        logger.info(f"  Cache speedup: {summary['summary']['cache_speedup']:.0f}x")
        logger.info("="*60 + "\n")


async def main():
    """Run benchmarks"""
    benchmark = EnhancedAnalysisBenchmark()
    await benchmark.run_all_benchmarks()


if __name__ == "__main__":
    # Initialize environment
    import dotenv
    dotenv.load_dotenv()
    
    # Run benchmarks
    asyncio.run(main())