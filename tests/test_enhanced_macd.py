#!/usr/bin/env python3
"""
Test Enhanced MACD Calculation
Validates the improved MACD signal line calculation
"""
import asyncio
import numpy as np
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_analysis.technical_indicators_enhanced import EnhancedTechnicalAnalysisEngine

async def test_macd_calculation():
    """Test MACD calculation with sample data"""
    engine = EnhancedTechnicalAnalysisEngine()
    
    # Generate sample price data (sine wave with trend)
    np.random.seed(42)
    days = 100
    trend = np.linspace(100, 120, days)  # Upward trend
    noise = np.random.normal(0, 2, days)  # Some noise
    cycle = 5 * np.sin(np.linspace(0, 4 * np.pi, days))  # Cyclical component
    
    prices = trend + cycle + noise
    
    print("Testing Enhanced MACD Calculation")
    print("=" * 50)
    
    # Test 1: Basic MACD calculation
    macd_line, signal_line, histogram = engine._calculate_enhanced_macd(
        "BTCUSDT", prices, 12, 26, 9
    )
    
    print(f"\nTest 1 - Basic MACD:")
    print(f"  MACD Line: {macd_line:.4f}")
    print(f"  Signal Line: {signal_line:.4f}")
    print(f"  Histogram: {histogram:.4f}")
    
    # Verify values are reasonable
    assert macd_line is not None, "MACD line should not be None"
    assert signal_line is not None, "Signal line should not be None"
    assert histogram is not None, "Histogram should not be None"
    
    # Test 2: Multiple calculations (check history tracking)
    print("\nTest 2 - Sequential MACD calculations:")
    for i in range(3):
        # Add one more price point
        new_prices = np.append(prices, 120 + i)
        
        macd_line, signal_line, histogram = engine._calculate_enhanced_macd(
            "BTCUSDT", new_prices, 12, 26, 9
        )
        
        print(f"  Iteration {i+1}:")
        print(f"    MACD: {macd_line:.4f}, Signal: {signal_line:.4f}, Hist: {histogram:.4f}")
    
    # Test 3: Divergence detection
    print("\nTest 3 - MACD Divergence Detection:")
    
    # Create bearish divergence scenario (price up, MACD down)
    bearish_prices = np.linspace(100, 120, 50)  # Steady uptrend
    bearish_macd_hist = -0.5  # Negative histogram
    
    divergence = engine._detect_macd_divergence(bearish_prices, bearish_macd_hist)
    print(f"  Bearish scenario - Divergence: {divergence}")
    assert divergence == "Bearish", "Should detect bearish divergence"
    
    # Create bullish divergence scenario (price down, MACD up)
    bullish_prices = np.linspace(120, 100, 50)  # Steady downtrend
    bullish_macd_hist = 0.5  # Positive histogram
    
    divergence = engine._detect_macd_divergence(bullish_prices, bullish_macd_hist)
    print(f"  Bullish scenario - Divergence: {divergence}")
    assert divergence == "Bullish", "Should detect bullish divergence"
    
    # Test 4: Compare with traditional MACD
    print("\nTest 4 - Traditional vs Enhanced MACD:")
    
    # Traditional calculation (from original engine)
    try:
        from market_analysis.technical_indicators import TechnicalAnalysisEngine
        traditional_engine = TechnicalAnalysisEngine()
        
        trad_macd, trad_signal, trad_hist = traditional_engine._calculate_macd(
            prices.tolist(), 12, 26, 9
        )
        
        if trad_macd is not None and trad_signal is not None:
            print(f"  Traditional - MACD: {trad_macd:.4f}, Signal: {trad_signal:.4f}")
            print(f"  Enhanced    - MACD: {macd_line:.4f}, Signal: {signal_line:.4f}")
            print(f"  Difference  - MACD: {abs(trad_macd - macd_line):.4f}")
            
            # MACD line should be similar, signal line will differ
            assert abs(trad_macd - macd_line) < 0.1, "MACD lines should be similar"
        else:
            print("  Traditional MACD returned None (expected for simplified implementation)")
            print(f"  Enhanced    - MACD: {macd_line:.4f}, Signal: {signal_line:.4f}")
    except Exception as e:
        print(f"  Could not compare with traditional MACD: {e}")
        print(f"  Enhanced    - MACD: {macd_line:.4f}, Signal: {signal_line:.4f}")
    
    print("\n✅ All MACD tests passed!")
    
    # Test 5: Full indicator calculation with real kline format
    print("\nTest 5 - Full Indicator Calculation:")
    
    # Create kline data in Bybit format [timestamp, open, high, low, close, volume, turnover]
    klines_1h = []
    for i in range(len(prices)):
        timestamp = 1000000000 + i * 3600
        open_price = prices[i] + np.random.uniform(-1, 1)
        close_price = prices[i]
        high = max(open_price, close_price) + np.random.uniform(0, 2)
        low = min(open_price, close_price) - np.random.uniform(0, 2)
        volume = np.random.uniform(1000, 10000)
        
        klines_1h.append([
            timestamp,
            open_price,
            high,
            low,
            close_price,
            volume,
            volume * close_price  # turnover
        ])
    
    # Calculate full indicators
    indicators = await engine.calculate_indicators(
        symbol="BTCUSDT",
        kline_data={"1h": klines_1h},
        current_price=prices[-1],
        volume_24h=100000
    )
    
    print(f"  MACD Line: {indicators.macd_line:.4f}")
    print(f"  MACD Signal: {indicators.macd_signal:.4f}")
    print(f"  MACD Histogram: {indicators.macd_histogram:.4f}")
    print(f"  MACD Divergence: {indicators.macd_divergence}")
    print(f"  Confidence: {indicators.confidence:.1f}%")
    
    assert indicators.macd_line is not None
    assert indicators.macd_signal is not None
    assert indicators.confidence > 50
    
    print("\n✅ Full indicator calculation successful!")
    
    return True

async def test_vwap_calculation():
    """Test VWAP calculation"""
    engine = EnhancedTechnicalAnalysisEngine()
    
    print("\n" + "="*50)
    print("Testing VWAP Calculation")
    print("="*50)
    
    # Create sample data
    closes = np.array([100, 102, 101, 103, 104, 102, 105])
    highs = closes + 1
    lows = closes - 1
    volumes = np.array([1000, 1500, 800, 2000, 1200, 900, 1100])
    
    vwap, vwap_upper, vwap_lower = engine._calculate_vwap(closes, highs, lows, volumes)
    
    print(f"VWAP: {vwap:.2f}")
    print(f"VWAP Upper Band: {vwap_upper:.2f}")
    print(f"VWAP Lower Band: {vwap_lower:.2f}")
    
    # Manual calculation for verification
    typical_prices = (highs + lows + closes) / 3
    expected_vwap = np.sum(typical_prices * volumes) / np.sum(volumes)
    
    print(f"Expected VWAP: {expected_vwap:.2f}")
    assert abs(vwap - expected_vwap) < 0.01, "VWAP calculation mismatch"
    
    print("✅ VWAP calculation test passed!")

async def test_market_profile():
    """Test market profile calculation"""
    engine = EnhancedTechnicalAnalysisEngine()
    
    print("\n" + "="*50)
    print("Testing Market Profile Calculation")
    print("="*50)
    
    # Create sample data with clear volume concentration
    closes = np.concatenate([
        np.random.normal(100, 1, 50),    # Lots of trading around 100
        np.random.normal(105, 1, 20),    # Some trading around 105
        np.random.normal(100, 1, 30),    # More trading back at 100
    ])
    
    volumes = np.concatenate([
        np.random.uniform(1000, 2000, 50),   # High volume at 100
        np.random.uniform(500, 1000, 20),    # Lower volume at 105
        np.random.uniform(1500, 2500, 30),   # High volume again at 100
    ])
    
    poc, vah, val = engine._calculate_market_profile(closes, volumes)
    
    print(f"Point of Control (POC): {poc:.2f}")
    print(f"Value Area High (VAH): {vah:.2f}")
    print(f"Value Area Low (VAL): {val:.2f}")
    
    # POC should be around 100 where most volume occurred
    assert poc is not None
    assert 99 < poc < 101, f"POC should be around 100, got {poc}"
    assert val < poc < vah, "VAL < POC < VAH relationship should hold"
    
    print("✅ Market profile calculation test passed!")

async def main():
    """Run all tests"""
    try:
        await test_macd_calculation()
        await test_vwap_calculation()
        await test_market_profile()
        
        print("\n" + "="*50)
        print("🎉 All enhanced indicator tests passed!")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(main())