#!/usr/bin/env python3
"""
Test script to verify enhanced market status with new data points
"""
import asyncio
import logging
from datetime import datetime
from market_analysis.market_status_engine import market_status_engine
from dashboard.components import DashboardComponents
from dashboard.models import MarketStatus

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)

async def test_enhanced_market_status():
    """Test the enhanced market status with new data points"""
    try:
        print("🔍 Testing Enhanced Market Status...\n")
        
        # Test with Bitcoin
        symbol = "BTCUSDT"
        print(f"Testing with {symbol}...")
        
        # Get enhanced market status
        enhanced_status = await market_status_engine.get_enhanced_market_status(
            symbol=symbol,
            positions=[],  # No positions for clean test
            chat_data={}
        )
        
        print(f"\n✅ Enhanced Market Status Retrieved:")
        print(f"Symbol: {enhanced_status.symbol}")
        print(f"Confidence: {enhanced_status.confidence:.1f}%")
        print(f"Data Quality: {enhanced_status.data_quality:.1f}%")
        
        print(f"\n📊 Core Metrics:")
        print(f"Sentiment: {enhanced_status.sentiment_label} ({enhanced_status.sentiment_score:.0f}/100)")
        print(f"Volatility: {enhanced_status.volatility_level} ({enhanced_status.volatility_score:.0f}/100)")
        if enhanced_status.volatility_percentage:
            print(f"Volatility %: {enhanced_status.volatility_percentage:.2f}%")
        print(f"Trend: {enhanced_status.trend_direction} (Strength: {enhanced_status.trend_strength:.0f})")
        print(f"Momentum: {enhanced_status.momentum_state} (Score: {enhanced_status.momentum_score:.0f})")
        
        print(f"\n💰 Price Information:")
        print(f"Current Price: ${enhanced_status.current_price:,.2f}")
        print(f"24h Change: {'+' if enhanced_status.price_change_pct_24h > 0 else ''}{enhanced_status.price_change_pct_24h:.2f}%")
        
        print(f"\n🆕 New Enhanced Metrics:")
        
        # Support and Resistance
        if enhanced_status.support_level and enhanced_status.resistance_level:
            print(f"📊 Support/Resistance: ${enhanced_status.support_level:,.2f} / ${enhanced_status.resistance_level:,.2f}")
        else:
            print("📊 Support/Resistance: Not available")
        
        # Volume Profile
        if enhanced_status.volume_profile:
            print(f"📈 Volume Profile: {enhanced_status.volume_profile}", end="")
            if enhanced_status.volume_ratio:
                print(f" ({enhanced_status.volume_ratio:.1f}x average)")
            else:
                print()
        else:
            print("📈 Volume Profile: Not available")
        
        # Market Structure
        if enhanced_status.market_structure:
            print(f"🏗️ Market Structure: {enhanced_status.market_structure} ({enhanced_status.structure_bias})")
        else:
            print("🏗️ Market Structure: Not available")
        
        # Funding Rate
        if enhanced_status.funding_rate is not None:
            print(f"💰 Funding Rate: {enhanced_status.funding_rate:.3f}% ({enhanced_status.funding_bias})")
        else:
            print("💰 Funding Rate: Not available")
        
        # Open Interest Change
        if enhanced_status.open_interest_change_24h is not None:
            sign = '+' if enhanced_status.open_interest_change_24h > 0 else ''
            print(f"📊 Open Interest 24h: {sign}{enhanced_status.open_interest_change_24h:.1f}%")
        else:
            print("📊 Open Interest 24h: Not available")
        
        # Now test the dashboard display
        print("\n" + "="*50)
        print("📱 Dashboard Display Test:")
        print("="*50 + "\n")
        
        # Convert to MarketStatus model for dashboard
        market_status = MarketStatus(
            primary_symbol=enhanced_status.symbol,
            timestamp=enhanced_status.timestamp,
            market_sentiment=enhanced_status.sentiment_label,
            sentiment_score=enhanced_status.sentiment_score,
            sentiment_emoji=enhanced_status.sentiment_emoji,
            volatility=enhanced_status.volatility_level,
            volatility_score=enhanced_status.volatility_score,
            volatility_percentage=enhanced_status.volatility_percentage,
            volatility_emoji=enhanced_status.volatility_emoji,
            trend=enhanced_status.trend_direction,
            trend_strength=enhanced_status.trend_strength,
            trend_emoji=enhanced_status.trend_emoji,
            momentum=enhanced_status.momentum_state,
            momentum_score=enhanced_status.momentum_score,
            momentum_emoji=enhanced_status.momentum_emoji,
            market_regime=enhanced_status.market_regime,
            regime_strength=enhanced_status.regime_strength,
            volume_strength=enhanced_status.volume_strength,
            current_price=enhanced_status.current_price,
            price_change_24h=enhanced_status.price_change_24h,
            price_change_pct_24h=enhanced_status.price_change_pct_24h,
            support_level=enhanced_status.support_level,
            resistance_level=enhanced_status.resistance_level,
            volume_profile=enhanced_status.volume_profile,
            volume_ratio=enhanced_status.volume_ratio,
            market_structure=enhanced_status.market_structure,
            structure_bias=enhanced_status.structure_bias,
            funding_rate=enhanced_status.funding_rate,
            funding_bias=enhanced_status.funding_bias,
            open_interest_change_24h=enhanced_status.open_interest_change_24h,
            confidence=enhanced_status.confidence,
            data_quality=enhanced_status.data_quality,
            analysis_depth=enhanced_status.analysis_depth,
            key_levels=enhanced_status.key_levels,
            data_sources=enhanced_status.data_sources,
            last_updated=enhanced_status.last_updated
        )
        
        # Generate dashboard display
        components = DashboardComponents()
        dashboard_display = components.market_status(market_status)
        
        # Print raw HTML (telegram format)
        print("Raw Dashboard Output:")
        print(dashboard_display)
        
        # Print cleaned version for console
        print("\nFormatted Display:")
        # Remove HTML tags for console display
        import re
        clean_display = re.sub('<[^<]+?>', '', dashboard_display)
        print(clean_display)
        
        print("\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_enhanced_market_status())