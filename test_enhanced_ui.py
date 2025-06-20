#!/usr/bin/env python3
"""Test the enhanced UI designs"""
import asyncio
from decimal import Decimal
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard.generator import build_mobile_dashboard_text
from config.constants import *

async def test_enhanced_dashboard():
    """Test the enhanced dashboard design"""
    
    # Mock bot data with various trades
    bot_data = {
        STATS_TOTAL_TRADES: 45,
        STATS_TOTAL_WINS: 35,
        STATS_TOTAL_LOSSES: 10,
        STATS_TOTAL_PNL: Decimal("2345.67"),
        STATS_WIN_STREAK: 5,
        STATS_BEST_TRADE: Decimal("567.89"),
        STATS_WORST_TRADE: Decimal("-123.45"),
        STATS_CONSERVATIVE_TRADES: 23,
        STATS_FAST_TRADES: 22,
        STATS_TP1_HITS: 30,
        STATS_SL_HITS: 5,
        "STATS_EXTERNAL_TRADES": 12,
        "STATS_EXTERNAL_PNL": Decimal("456.78"),
        "STATS_EXTERNAL_WINS": 8,
        "STATS_EXTERNAL_LOSSES": 4,
        "bot_start_time": datetime.now().timestamp() - 7200,  # 2 hours ago
        "active_monitors": 3
    }
    
    # Mock chat data
    chat_data = {}
    
    # Generate dashboard
    dashboard_text = await build_mobile_dashboard_text(chat_data, bot_data)
    
    print("=" * 50)
    print("ENHANCED DASHBOARD PREVIEW")
    print("=" * 50)
    print(dashboard_text)
    print("=" * 50)
    
    # Test trade execution messages
    from execution.trader import TradeExecutor
    executor = TradeExecutor()
    
    # Test fast approach message
    print("\n" + "=" * 50)
    print("FAST APPROACH MESSAGE PREVIEW")
    print("=" * 50)
    
    # Mock fast trade result
    fast_message = (
        f"⚡ <b>FAST TRADE EXECUTED</b> ⚡\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>BTCUSDT LONG</b> │ <code>10x</code>\n"
        f"💰 Margin: <code>$500.00</code> │ Size: <code>0.0730</code>\n\n"
        f"📍 Entry: <code>$68,450.00</code> (Market)\n"
        f"🎯 Target: <code>$69,134.50</code> (+1.0%)\n"
        f"🛡️ Stop: <code>$67,765.50</code> (-1.0%)\n\n"
        f"⚖️ <b>Risk/Reward:</b> 1:1.0\n"
        f"🚀 <b>Execution:</b> ⚡ Ultra Fast (0.8s)\n\n"
        f"✅ Monitoring Active"
    )
    print(fast_message)
    
    # Test conservative approach message
    print("\n" + "=" * 50)
    print("CONSERVATIVE APPROACH MESSAGE PREVIEW")
    print("=" * 50)
    
    conservative_message = (
        f"🛡️ <b>CONSERVATIVE TRADE DEPLOYED</b> 🛡️\n"
        f"════════════════════════════════════\n"
        f"📊 <b>ETHUSDT SHORT</b> │ <code>15x</code> │ ID: <code>abc123</code>\n\n"
        f"💼 <b>POSITION METRICS</b>\n"
        f"├─ Margin: <code>$1,000.00</code>\n"
        f"├─ Total Size: <code>3.4500</code> ETH\n"
        f"└─ Position Value: <code>$12,765.00</code>\n\n"
        f"📍 <b>ENTRY STRATEGY</b> (3 Limits)\n"
        f"├─ Primary: <code>$3,700.00</code> (33.3%)\n"
        f"├─ Limit 1: <code>$3,720.00</code> (33.3%)\n"
        f"└─ Limit 2: <code>$3,740.00</code> (33.3%)\n\n"
        f"🎯 <b>EXIT STRATEGY</b> (4 TPs)\n"
        f"├─ TP1: <code>$3,663.00</code> (-1.0%) │ 70%\n"
        f"├─ TP2: <code>$3,644.00</code> (-1.5%) │ 10%\n"
        f"├─ TP3: <code>$3,626.00</code> (-2.0%) │ 10%\n"
        f"└─ TP4: <code>$3,589.00</code> (-3.0%) │ 10%\n\n"
        f"🛡️ <b>RISK MANAGEMENT</b>\n"
        f"├─ Stop Loss: <code>$3,774.00</code> (+2.0%)\n"
        f"├─ Max Risk: <code>$148.00</code>\n"
        f"├─ Max Reward: <code>$592.00</code>\n"
        f"└─ R:R Ratio: 1:4.0 🌟 EXCELLENT\n\n"
        f"⚡ Execution Time: 🚀 Fast (2.3s)\n"
        f"🔄 Enhanced Monitoring: ACTIVE"
    )
    print(conservative_message)
    
    # Test GGShot approach message
    print("\n" + "=" * 50)
    print("GGSHOT APPROACH MESSAGE PREVIEW")
    print("=" * 50)
    
    ggshot_message = (
        f"📸 <b>GGSHOT AI TRADE EXECUTED</b> 📸\n"
        f"════════════════════════════════════\n"
        f"🤖 AI Analysis: ✅ HIGH CONFIDENCE\n\n"
        f"📊 <b>LDOUSDT SHORT</b> │ <code>20x</code> │ AI Score: 9.2/10\n\n"
        f"💡 <b>AI EXTRACTION RESULTS</b>\n"
        f"├─ Accuracy: 98.5%\n"
        f"├─ Processing: 3 passes\n"
        f"└─ Validation: ✅ PASSED\n\n"
        f"📍 <b>DETECTED PARAMETERS</b>\n"
        f"├─ Entries: <code>$0.8500, $0.8000, $0.7500</code>\n"
        f"├─ Targets: <code>$0.7000, $0.6500, $0.6000, $0.5500</code>\n"
        f"└─ Stop Loss: <code>$0.9000</code>\n\n"
        f"💰 <b>POSITION DEPLOYED</b>\n"
        f"├─ Margin Used: <code>$750.00</code>\n"
        f"├─ Position Size: <code>2,556.7</code> LDO\n"
        f"└─ Total Value: <code>$2,173.20</code>\n\n"
        f"⚖️ <b>RISK PROFILE</b>\n"
        f"├─ Risk Amount: <code>$127.50</code>\n"
        f"├─ Reward Potential: <code>$510.00</code>\n"
        f"├─ R:R Ratio: 1:4.0 🎯\n"
        f"└─ AI Risk Score: 3/10 (LOW) 🟢\n\n"
        f"✨ GGShot Monitoring: ACTIVE"
    )
    print(ggshot_message)

if __name__ == "__main__":
    asyncio.run(test_enhanced_dashboard())