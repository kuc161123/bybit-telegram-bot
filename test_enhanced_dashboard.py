#!/usr/bin/env python3
"""
Test the enhanced analytics dashboard with account info
"""
import asyncio
import logging
from datetime import datetime
from decimal import Decimal

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dashboard.generator_analytics_compact import build_analytics_dashboard_text
from dashboard.keyboards_analytics import build_analytics_dashboard_keyboard
from config.constants import *

async def test_enhanced_dashboard():
    """Test the enhanced dashboard with account info"""
    
    # Mock context with bot data
    mock_context = {
        'application': {
            'bot_data': {
                STATS_TOTAL_TRADES: 150,
                STATS_TOTAL_WINS: 90,
                STATS_TOTAL_LOSSES: 60,
                STATS_TOTAL_PNL: 2500.50,
                # Mock some bot positions
                'chat_12345': {
                    SYMBOL: 'BTCUSDT'
                },
                'chat_67890': {
                    SYMBOL: 'ETHUSDT'
                }
            }
        }
    }
    
    # Generate dashboard
    try:
        logger.info("Generating enhanced analytics dashboard...")
        dashboard_text = await build_analytics_dashboard_text(12345, mock_context)
        
        print("\n" + "="*60)
        print("ENHANCED ANALYTICS DASHBOARD OUTPUT:")
        print("="*60 + "\n")
        print(dashboard_text)
        print("\n" + "="*60)
        
        # Calculate message length
        print(f"\nMessage length: {len(dashboard_text)} characters")
        print(f"Telegram limit: 4096 characters")
        print(f"Status: {'✅ OK' if len(dashboard_text) <= 4096 else '❌ TOO LONG'}")
        
        # Test keyboard generation
        keyboard = build_analytics_dashboard_keyboard(12345, mock_context, active_positions=5, has_monitors=True)
        
        print("\nSIMPLIFIED KEYBOARD STRUCTURE:")
        print("="*60)
        for i, row in enumerate(keyboard.inline_keyboard):
            buttons = [btn.text for btn in row]
            print(f"Row {i+1}: {' | '.join(buttons)}")
        
        logger.info("✅ Enhanced dashboard test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Enhanced dashboard test failed: {e}", exc_info=True)

async def main():
    """Run the test"""
    print("🧪 Testing Enhanced Analytics Dashboard")
    print("="*60)
    
    await test_enhanced_dashboard()
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    asyncio.run(main())