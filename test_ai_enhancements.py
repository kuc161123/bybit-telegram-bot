#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced AI Market Insights functionality
"""
import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_ai_market_analysis():
    """Test the AI market analysis module"""
    try:
        from clients.bybit_client import bybit_client
        from clients.ai_client import get_ai_client
        from execution.ai_market_analysis import AIMarketAnalyzer, get_ai_market_insights
        from config.constants import STATS_WIN_STREAK, STATS_LOSS_STREAK, STATS_TOTAL_TRADES, STATS_TOTAL_PNL
        
        logger.info("🚀 Testing Enhanced AI Market Analysis...")
        
        # Initialize clients
        ai_client = get_ai_client()
        
        # Create analyzer
        analyzer = AIMarketAnalyzer(bybit_client, ai_client)
        
        # Test with BTCUSDT
        symbol = "BTCUSDT"
        logger.info(f"\n📊 Analyzing {symbol}...")
        
        # Create sample stats data
        stats_data = {
            'overall_win_rate': 73.5,
            STATS_WIN_STREAK: 4,
            STATS_LOSS_STREAK: 0,
            STATS_TOTAL_TRADES: 45,
            STATS_TOTAL_PNL: 2456.78,
            'stats_total_wins_pnl': 3456.78,
            'stats_total_losses_pnl': -1000.00
        }
        
        # Get market insight
        insight = await analyzer.analyze_market(symbol)
        
        print(f"\n🎯 Market Insight for {symbol}")
        print("=" * 50)
        print(f"📊 Market Regime: {insight.market_regime}")
        print(f"🎯 Confidence: {insight.confidence:.1f}%")
        print(f"📈 Prediction: {insight.prediction}")
        print(f"💡 Recommendation: {insight.recommendation}")
        
        if insight.key_levels:
            print(f"\n📍 Key Levels:")
            for level, price in insight.key_levels.items():
                print(f"  - {level}: ${price:,.2f}")
        
        if insight.risk_factors:
            print(f"\n⚠️ Risk Factors:")
            for risk in insight.risk_factors[:3]:
                print(f"  - {risk}")
        
        if insight.opportunities:
            print(f"\n✨ Opportunities:")
            for opp in insight.opportunities[:3]:
                print(f"  - {opp}")
        
        if insight.technical_signals:
            print(f"\n📊 Technical Indicators:")
            print(f"  - RSI: {insight.technical_signals.get('rsi', 0):.1f}")
            print(f"  - SMA20: ${insight.technical_signals.get('sma_20', 0):,.2f}")
            print(f"  - Price Position: {insight.technical_signals.get('price_position', 0.5):.1%}")
        
        if insight.ai_analysis:
            print(f"\n🧠 AI Analysis:")
            print(f"  {insight.ai_analysis[:200]}...")
        
        # Test dashboard integration
        print("\n\n📊 Testing Dashboard Integration...")
        dashboard_data = await get_ai_market_insights(symbol, stats_data)
        
        print(f"\n🎯 Dashboard Display Data:")
        print(f"  Win Rate: {dashboard_data['win_rate']:.1f}% over {dashboard_data['total_trades']} trades")
        print(f"  Win Streak: {dashboard_data['win_streak']} | Loss Streak: {dashboard_data['loss_streak']}")
        print(f"  Momentum: {dashboard_data['momentum']}")
        print(f"  Next Trade Confidence: {dashboard_data['confidence']:.0f}%")
        print(f"  Trend: {dashboard_data['trend']}")
        print(f"\n  Market Outlook: {dashboard_data['market_outlook']}")
        print(f"  Signal Strength: {dashboard_data['signal_strength']}")
        print(f"  Short-term: {dashboard_data['short_term_prediction']}")
        
        # Test multiple symbols
        symbols = ["ETHUSDT", "SOLUSDT"]
        print(f"\n\n🔄 Testing Portfolio Analysis...")
        
        positions = []
        for sym in symbols:
            positions.append({
                "symbol": sym,
                "size": 1.0,
                "positionIM": 1000,
                "unrealisedPnl": 50,
                "percentage": 5.0
            })
        
        portfolio_insights = await analyzer.get_portfolio_insights(positions)
        
        for i, insight in enumerate(portfolio_insights):
            print(f"\n{i+1}. {insight.symbol}")
            print(f"   Confidence: {insight.confidence:.0f}%")
            print(f"   Outlook: {insight.prediction.upper()}")
            print(f"   Action: {insight.recommendation}")
        
        logger.info("\n✅ AI Market Analysis test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error testing AI market analysis: {e}", exc_info=True)

async def test_predictive_signals_view():
    """Test the predictive signals view formatting"""
    try:
        from config.constants import STATS_WIN_STREAK, STATS_LOSS_STREAK, STATS_TOTAL_TRADES
        
        print("\n\n📱 Testing Predictive Signals Display...")
        
        # Sample data
        ai_data = {
            'win_rate': 73.5,
            'total_trades': 45,
            'win_streak': 4,
            'loss_streak': 0,
            'momentum': '🔥 Hot',
            'confidence': 87,
            'trend': '▲ Uptrend',
            'market_outlook': 'BULLISH',
            'signal_strength': 'STRONG',
            'short_term_prediction': 'Expecting continued upward movement with possible retest of support',
            'key_risks': ['MACD bearish divergence', 'Approaching resistance'],
            'recommended_actions': ['Scale in on dips', 'Set tight stop loss', 'Take partial profits at resistance'],
            'technical': {
                'trend': 'Trending Up',
                'momentum': 4.5
            },
            'performance_metrics': {
                'profit_factor': 3.45,
                'expectancy': 54.60
            }
        }
        
        # Format display
        print(f"""
🎯 PREDICTIVE SIGNALS
═══════════════════════════════════

├─ Win Rate: {ai_data['win_rate']:.1f}% over {ai_data['total_trades']} trades
├─ Win Streak: {ai_data['win_streak']} | Loss Streak: {ai_data['loss_streak']}
├─ Momentum: {ai_data['momentum']}
├─ Next Trade Confidence: {ai_data['confidence']:.0f}%
└─ Trend: {ai_data['trend']}

📊 AI MARKET ANALYSIS (BTCUSDT)
├─ Market Outlook: {ai_data['market_outlook']}
├─ Signal Strength: {ai_data['signal_strength']}
├─ Short-term: {ai_data['short_term_prediction'][:50]}...
└─ Risk Level: {'⚠️ High' if len(ai_data.get('key_risks', [])) > 2 else '✅ Low' if len(ai_data.get('key_risks', [])) == 0 else '🟡 Moderate'}

🎯 TRADING RECOMMENDATIONS""")
        
        for i, action in enumerate(ai_data.get('recommended_actions', [])[:3]):
            if i == len(ai_data.get('recommended_actions', [])) - 1:
                print(f"└─ {action}")
            else:
                print(f"├─ {action}")
        
        print(f"\n⚠️ KEY RISK FACTORS")
        for i, risk in enumerate(ai_data['key_risks'][:3]):
            if i == len(ai_data['key_risks']) - 1:
                print(f"└─ {risk}")
            else:
                print(f"├─ {risk}")
        
        print(f"""
📈 TECHNICAL INDICATORS
├─ Trend: {ai_data['technical']['trend']}
├─ Momentum: {ai_data['technical']['momentum']:+.1f}%
└─ Market Regime: {ai_data.get('market_outlook', 'Analyzing')}

💰 PERFORMANCE METRICS
├─ Profit Factor: {ai_data['performance_metrics']['profit_factor']:.2f}
└─ Expectancy: ${ai_data['performance_metrics']['expectancy']:.2f}/trade

Last updated: {datetime.now().strftime('%H:%M:%S UTC')}
""")
        
        print("✅ Predictive Signals display test completed!")
        
    except Exception as e:
        logger.error(f"❌ Error testing predictive signals view: {e}", exc_info=True)

async def main():
    """Run all tests"""
    print("🚀 Starting Enhanced AI Market Insights Tests\n")
    
    # Test AI market analysis
    await test_ai_market_analysis()
    
    # Test predictive signals view
    await test_predictive_signals_view()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())