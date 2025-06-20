#!/usr/bin/env python3
"""
Test script for the ultra feature-rich dashboard
"""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dashboard.generator_analytics_compact import build_mobile_dashboard_text
from config.constants import *

async def test_dashboard():
    """Test the ultra feature-rich dashboard generation"""
    
    # Mock chat data
    chat_data = {
        SYMBOL: "BTCUSDT",
        SIDE: "Buy",
        MARGIN_AMOUNT: Decimal("100"),
        LEVERAGE: 10
    }
    
    # Mock bot data with some stats
    bot_data = {
        STATS_TOTAL_TRADES: 150,
        STATS_TOTAL_WINS: 90,
        STATS_TOTAL_LOSSES: 60,
        STATS_TOTAL_PNL: 2500.50,
        STATS_WIN_STREAK: 5,
        "bot_start_time": datetime.now().timestamp() - 86400 * 7,  # 7 days ago
        "active_monitors": 3
    }
    
    # Generate dashboard
    try:
        logger.info("Generating ultra feature-rich dashboard...")
        dashboard_text = await build_mobile_dashboard_text(chat_data, bot_data)
        
        print("\n" + "="*50)
        print("ULTRA FEATURE-RICH DASHBOARD OUTPUT:")
        print("="*50 + "\n")
        print(dashboard_text)
        print("\n" + "="*50)
        
        # Test keyboard generation
        from dashboard.keyboards_analytics import build_analytics_dashboard_keyboard
        # Create dummy chat ID and context for keyboard function
        chat_id = 12345
        class DummyContext:
            chat_data = {}
            bot_data = {}
        context = DummyContext()
        keyboard = build_analytics_dashboard_keyboard(chat_id, context, active_positions=3, has_monitors=True)
        
        print("\nKEYBOARD STRUCTURE:")
        print("="*50)
        for row in keyboard.inline_keyboard:
            buttons = [btn.text for btn in row]
            print(" | ".join(buttons))
        
        logger.info("✅ Dashboard test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Dashboard test failed: {e}", exc_info=True)

async def test_analytics():
    """Test analytics features"""
    # Analytics functions in generator_analytics_compact.py
    from dashboard.generator_analytics_compact import (
        calculate_portfolio_metrics,
        generate_portfolio_heatmap,
        calculate_sharpe_ratio,
        calculate_max_drawdown
    )
    
    # Mock positions
    positions = [
        {"symbol": "BTCUSDT", "unrealisedPnl": "150.50", "positionValue": "5000", "side": "Buy", "percentage": "3.01", "leverage": "10"},
        {"symbol": "ETHUSDT", "unrealisedPnl": "-50.25", "positionValue": "3000", "side": "Sell", "percentage": "-1.67", "leverage": "5"},
        {"symbol": "SOLUSDT", "unrealisedPnl": "75.00", "positionValue": "2000", "side": "Buy", "percentage": "3.75", "leverage": "15"},
    ]
    
    print("\n" + "="*50)
    print("ANALYTICS FEATURES TEST:")
    print("="*50 + "\n")
    
    # Test portfolio metrics
    metrics = await calculate_portfolio_metrics(positions, 10000)
    print("Portfolio Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    # Test heatmap
    print("\nPosition Heatmap:")
    heatmap = await generate_portfolio_heatmap(positions)
    print(heatmap)
    
    # Test Sharpe ratio
    returns = [0.02, -0.01, 0.03, 0.01, -0.02, 0.04, 0.02, -0.01]
    sharpe = calculate_sharpe_ratio(returns)
    print(f"\nSharpe Ratio: {sharpe:.2f}")
    
    # Test max drawdown
    equity_curve = [10000, 10200, 10100, 9800, 9900, 10500, 10300, 10800]
    max_dd, duration = calculate_max_drawdown(equity_curve)
    print(f"Max Drawdown: {max_dd:.1f}% (Duration: {duration} periods)")

async def main():
    """Run all tests"""
    print("🧪 Testing Ultra Feature-Rich Dashboard v6.0")
    print("="*50)
    
    await test_dashboard()
    await test_analytics()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())