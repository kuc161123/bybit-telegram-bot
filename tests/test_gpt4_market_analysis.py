#!/usr/bin/env python3
"""
Test GPT-4 Enhanced Market Analysis
Tests the new AI recommendation system with BUY/HOLD/SELL recommendations
"""
import asyncio
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_ai_market_analysis():
    """Test the AI enhanced market analysis"""
    try:
        # Import required modules
        from execution.ai_market_analysis import AIMarketAnalyzer
        from clients.ai_client import get_ai_client
        from clients.bybit_client import bybit_client
        
        # Get AI client
        ai_client = get_ai_client()
        
        if ai_client.llm_provider == "stub":
            logger.warning("AI features are disabled. Set OPENAI_API_KEY to enable.")
            return
        
        # Create analyzer
        analyzer = AIMarketAnalyzer(bybit_client, ai_client)
        
        # Test symbols
        test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        
        logger.info("🤖 Testing GPT-4 Enhanced Market Analysis")
        logger.info("=" * 60)
        
        for symbol in test_symbols:
            logger.info(f"\n📊 Analyzing {symbol}...")
            
            # Get market insight
            insight = await analyzer.analyze_market(symbol)
            
            if insight:
                logger.info(f"✅ Analysis completed for {symbol}")
                logger.info(f"   Market Regime: {insight.market_regime}")
                logger.info(f"   Prediction: {insight.prediction}")
                logger.info(f"   Base Confidence: {insight.confidence:.1f}%")
                
                if insight.recommendation:
                    rec_emoji = "🟢" if insight.recommendation == "BUY" else "🔴" if insight.recommendation == "SELL" else "🟡"
                    logger.info(f"   {rec_emoji} AI Recommendation: {insight.recommendation}")
                
                if insight.risk_assessment:
                    risk_emoji = "⚠️" if insight.risk_assessment == "HIGH" else "⚡" if insight.risk_assessment == "MEDIUM" else "✅"
                    logger.info(f"   {risk_emoji} Risk Assessment: {insight.risk_assessment}")
                
                if insight.enhanced_confidence:
                    boost = insight.enhanced_confidence - insight.confidence
                    logger.info(f"   🚀 Enhanced Confidence: {insight.enhanced_confidence:.1f}% (+{boost:.1f}% boost)")
                
                if insight.ai_analysis:
                    logger.info(f"   💡 AI Reasoning: {insight.ai_analysis[:100]}...")
                
                # Show key technical signals
                if insight.technical_signals:
                    logger.info(f"   📈 Technical Signals:")
                    if "rsi" in insight.technical_signals:
                        logger.info(f"      RSI: {insight.technical_signals['rsi']:.1f}")
                    if "macd" in insight.technical_signals:
                        macd_signal = "Bullish" if insight.technical_signals.get("macd", 0) > insight.technical_signals.get("macd_signal", 0) else "Bearish"
                        logger.info(f"      MACD: {macd_signal}")
                    if "volume_ratio" in insight.technical_signals:
                        logger.info(f"      Volume: {insight.technical_signals['volume_ratio']:.1f}x average")
            else:
                logger.error(f"❌ Failed to get analysis for {symbol}")
            
            # Small delay between requests
            await asyncio.sleep(2)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ GPT-4 Enhanced Market Analysis Test Complete")
        
    except Exception as e:
        logger.error(f"❌ Error in AI market analysis test: {e}")
        import traceback
        traceback.print_exc()

async def test_dashboard_integration():
    """Test the dashboard integration with AI recommendations"""
    try:
        logger.info("\n🎯 Testing Dashboard Integration")
        logger.info("=" * 60)
        
        # Import dashboard models
        from dashboard.models import MarketStatus
        from dashboard.components import DashboardComponents
        
        # Create a sample market status with AI data
        market_status = MarketStatus(
            primary_symbol="BTCUSDT",
            timestamp=datetime.now(),
            market_sentiment="Bullish",
            sentiment_score=75.0,
            sentiment_emoji="🟢",
            volatility="Normal",
            volatility_score=45.0,
            volatility_emoji="📊",
            trend="Uptrend",
            trend_strength=65.0,
            trend_emoji="📈",
            momentum="Bullish",
            momentum_score=70.0,
            momentum_emoji="⚡",
            market_regime="Bull Market",
            regime_strength=80.0,
            volume_strength=65.0,
            current_price=43250.50,
            price_change_24h=850.25,
            price_change_pct_24h=2.01,
            confidence=81.0,
            data_quality=85.0,
            analysis_depth="Comprehensive",
            data_sources=["bybit_api", "technical_analysis", "ai_analysis"],
            last_updated=datetime.now(),
            # AI fields
            ai_recommendation="BUY",
            ai_reasoning="Strong uptrend with bullish momentum. RSI shows room for growth without being overbought.",
            ai_risk_assessment="MEDIUM",
            ai_confidence=92.0
        )
        
        # Generate market status display
        components = DashboardComponents()
        display = components.market_status(market_status)
        
        logger.info("Generated Market Status Display:")
        logger.info("-" * 40)
        # Print without HTML tags for clarity
        clean_display = display.replace("<b>", "").replace("</b>", "")
        print(clean_display)
        logger.info("-" * 40)
        
        logger.info("✅ Dashboard Integration Test Complete")
        
    except Exception as e:
        logger.error(f"❌ Error in dashboard integration test: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run all tests"""
    # Test AI market analysis
    await test_ai_market_analysis()
    
    # Test dashboard integration
    await test_dashboard_integration()

if __name__ == "__main__":
    asyncio.run(main())