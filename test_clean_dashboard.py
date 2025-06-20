#!/usr/bin/env python3
"""Test the clean dashboard design"""
import asyncio
from decimal import Decimal
from datetime import datetime
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard.generator_clean import build_mobile_dashboard_text
from config.constants import *

async def test_clean_dashboard():
    """Test the clean dashboard design"""
    
    # Mock bot data with various trades
    bot_data = {
        STATS_TOTAL_TRADES: 45,
        STATS_TOTAL_WINS: 35,
        STATS_TOTAL_LOSSES: 10,
        STATS_TOTAL_PNL: Decimal("2345.67"),
        STATS_WIN_STREAK: 5,
        STATS_BEST_TRADE: Decimal("567.89"),
        STATS_WORST_TRADE: Decimal("-123.45"),
        "bot_start_time": datetime.now().timestamp() - 7200,
        "active_monitors": 3
    }
    
    # Mock chat data
    chat_data = {}
    
    # Generate dashboard
    dashboard_text = await build_mobile_dashboard_text(chat_data, bot_data)
    
    print("=" * 50)
    print("CLEAN DASHBOARD PREVIEW v5.1")
    print("=" * 50)
    print(dashboard_text)
    print("=" * 50)
    
    # Show what it looks like with no positions
    print("\n" + "=" * 50)
    print("CLEAN DASHBOARD (NO POSITIONS)")
    print("=" * 50)
    
    # Mock empty positions scenario
    import unittest.mock as mock
    
    async def mock_get_all_positions():
        return []
    
    async def mock_calculate_potential_pnl():
        return {
            "current_pnl": 0.0,
            "positions_count": 0,
            "tp_orders_count": 0,
            "sl_orders_count": 0
        }
    
    async def mock_get_balance():
        return (Decimal("10000.00"), Decimal("8500.00"))
    
    with mock.patch('dashboard.generator_clean.get_all_positions', mock_get_all_positions):
        with mock.patch('dashboard.generator_clean.calculate_potential_pnl_for_positions', mock_calculate_potential_pnl):
            with mock.patch('dashboard.generator_clean.get_usdt_wallet_balance_cached', mock_get_balance):
                dashboard_text = await build_mobile_dashboard_text(chat_data, bot_data)
                print(dashboard_text)

if __name__ == "__main__":
    asyncio.run(test_clean_dashboard())