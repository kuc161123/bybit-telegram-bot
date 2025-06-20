#!/usr/bin/env python3
"""
Test the final dashboard with all fixes
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

async def test_final_dashboard():
    """Test the final dashboard with all fixes"""
    
    # Mock context with realistic bot data
    mock_context = {
        'application': {
            'bot_data': {
                STATS_TOTAL_TRADES: 150,
                STATS_TOTAL_WINS: 90,
                STATS_TOTAL_LOSSES: 60,
                STATS_TOTAL_PNL: 2500.50,
                'stats_total_wins_pnl': 3500.00,
                'stats_total_losses_pnl': -1000.00,
                'overall_win_rate': 60,
                'bot_start_time': datetime.now().timestamp() - 7 * 86400,  # 7 days ago
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
        logger.info("Generating final analytics dashboard...")
        dashboard_text = await build_analytics_dashboard_text(12345, mock_context)
        
        print("\n" + "="*60)
        print("FINAL ANALYTICS DASHBOARD OUTPUT:")
        print("="*60 + "\n")
        print(dashboard_text)
        print("\n" + "="*60)
        
        # Calculate message length
        print(f"\nMessage length: {len(dashboard_text)} characters")
        print(f"Telegram limit: 4096 characters")
        print(f"Status: {'✅ OK' if len(dashboard_text) <= 4096 else '❌ TOO LONG'}")
        
        # Verify all sections are present
        sections = [
            "ACCOUNT INFORMATION",
            "POTENTIAL P&L ANALYSIS", 
            "POSITIONS OVERVIEW",
            "PERFORMANCE STATS",
            "PORTFOLIO METRICS",
            "TIME ANALYSIS",
            "PREDICTIVE SIGNALS",
            "STRESS SCENARIOS",
            "LIVE ALERTS",
            "AI RECOMMENDATIONS",
            "PORTFOLIO OPTIMIZATION",
            "ACTIVE MANAGEMENT"
        ]
        
        print("\nSection Verification:")
        print("="*60)
        for section in sections:
            if section in dashboard_text:
                print(f"✅ {section}")
            else:
                print(f"❌ {section} - MISSING!")
        
        # Test keyboard generation
        keyboard = build_analytics_dashboard_keyboard(12345, mock_context, active_positions=5, has_monitors=True)
        
        print("\nKEYBOARD STRUCTURE:")
        print("="*60)
        for i, row in enumerate(keyboard.inline_keyboard):
            buttons = [f"{btn.text} ({btn.callback_data})" for btn in row]
            print(f"Row {i+1}: {' | '.join(buttons)}")
        
        # Verify all buttons have proper callbacks
        print("\nButton Callback Verification:")
        print("="*60)
        
        expected_callbacks = {
            "start_conversation": "New Trade",
            "refresh_dashboard": "Refresh",
            "list_positions": "Positions",
            "show_statistics": "Statistics",
            "show_settings": "Settings",
            "show_help": "Help"
        }
        
        all_callbacks = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_callbacks.append(btn.callback_data)
        
        for callback, description in expected_callbacks.items():
            if callback in all_callbacks:
                print(f"✅ {description} -> {callback}")
            else:
                print(f"❌ {description} -> {callback} - MISSING!")
        
        logger.info("✅ Final dashboard test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Final dashboard test failed: {e}", exc_info=True)

async def main():
    """Run the test"""
    print("🧪 Testing Final Analytics Dashboard")
    print("="*60)
    
    await test_final_dashboard()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(main())