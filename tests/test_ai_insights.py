#!/usr/bin/env python3
"""
Test script for AI Market Insights implementation
"""
import asyncio
import logging
from config.constants import *
from execution.ai_market_analysis import get_ai_market_insights

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def test_ai_insights():
    """Test the AI market insights functionality"""
    print("🧪 Testing AI Market Insights System")
    print("=" * 50)
    
    # Test data - simulating bot statistics
    test_stats = {
        STATS_TOTAL_TRADES: 50,
        STATS_TOTAL_WINS: 32,
        STATS_TOTAL_LOSSES: 18,
        STATS_TOTAL_PNL: 1250.50,
        STATS_WIN_STREAK: 3,
        STATS_LOSS_STREAK: 0,
        STATS_BEST_TRADE: 150.25,
        STATS_WORST_TRADE: -75.50,
        'stats_total_wins_pnl': 2000.0,
        'stats_total_losses_pnl': 750.0,
        'stats_max_drawdown': 5.2,
        'bot_start_time': 1700000000  # Sample timestamp
    }
    
    # Test with a common trading pair
    test_symbol = "BTCUSDT"
    
    print(f"\n📊 Testing analysis for: {test_symbol}")
    print(f"📈 Win Rate: {(test_stats[STATS_TOTAL_WINS] / test_stats[STATS_TOTAL_TRADES] * 100):.1f}%")
    print(f"💰 Total P&L: ${test_stats[STATS_TOTAL_PNL]:.2f}")
    print(f"🔥 Current Streak: {test_stats[STATS_WIN_STREAK]} wins")
    
    try:
        # Get AI market insights
        print("\n🤖 Generating AI Market Analysis...")
        analysis = await get_ai_market_insights(test_symbol, test_stats)
        
        # Display results
        print("\n✅ Analysis Complete!")
        print("=" * 50)
        
        print(f"\n📊 Market Outlook: {analysis.get('market_outlook', 'N/A')}")
        print(f"💪 Signal Strength: {analysis.get('signal_strength', 'N/A')}")
        print(f"🎯 Confidence: {analysis.get('confidence', 0)}%")
        
        print(f"\n📈 Prediction: {analysis.get('short_term_prediction', 'N/A')}")
        
        print("\n⚠️ Key Risks:")
        for i, risk in enumerate(analysis.get('key_risks', [])[:3], 1):
            print(f"  {i}. {risk}")
        
        print("\n💡 Recommended Actions:")
        for i, action in enumerate(analysis.get('recommended_actions', [])[:3], 1):
            print(f"  {i}. {action}")
        
        print(f"\n🧠 AI Insight: {analysis.get('ai_insights', 'N/A')}")
        
        # Show market data if available
        market_data = analysis.get('market_data', {})
        if market_data:
            print(f"\n📊 Market Data:")
            print(f"  • 24h Change: {market_data.get('price_change_24h', 0):+.1f}%")
            print(f"  • Current Price: ${market_data.get('current_price', 0):,.2f}")
        
        # Show technical indicators if available
        technical = analysis.get('technical', {})
        if technical:
            print(f"\n📉 Technical Analysis:")
            print(f"  • Trend: {technical.get('trend', 'N/A')}")
            print(f"  • Momentum: {technical.get('momentum', 0):+.1f}%")
            print(f"  • Volatility: {technical.get('volatility', 0):.1f}%")
        
        # Show sentiment if available
        sentiment = analysis.get('sentiment', {})
        if sentiment.get('available'):
            print(f"\n💭 Social Sentiment:")
            print(f"  • Score: {sentiment.get('score', 0)}/100")
            print(f"  • Trend: {sentiment.get('trend', 'N/A')}")
        
        print("\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting AI Market Insights Test")
    asyncio.run(test_ai_insights())