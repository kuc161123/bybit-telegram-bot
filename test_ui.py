#!/usr/bin/env python3
"""Test script to verify enhanced UI display"""
import asyncio
from dashboard.generator import build_mobile_dashboard_text
from clients.bybit_helpers import calculate_potential_pnl_for_positions

async def test_ui():
    # Mock data
    chat_data = {}
    bot_data = {
        'stats_total_trades': 5,
        'stats_total_pnl': 125.50,
        'stats_total_wins': 3,
        'stats_total_losses': 2
    }
    
    print("Testing enhanced dashboard UI...\n")
    
    # Test P&L calculation
    print("Testing P&L calculations...")
    pnl_data = await calculate_potential_pnl_for_positions()
    print(f"TP1 Profit: ${pnl_data.get('tp1_profit', 0):.2f}")
    print(f"All TP Profit: ${pnl_data.get('all_tp_profit', 0):.2f}")
    print(f"SL Loss: ${pnl_data.get('sl_loss', 0):.2f}")
    print(f"Current P&L: ${pnl_data.get('current_pnl', 0):.2f}")
    print("\n" + "="*50 + "\n")
    
    # Test dashboard generation
    print("Generating enhanced dashboard...\n")
    dashboard_text = await build_mobile_dashboard_text(chat_data, bot_data)
    
    # Remove HTML tags for console display
    import re
    clean_text = re.sub('<[^<]+?>', '', dashboard_text)
    print(clean_text)

if __name__ == "__main__":
    asyncio.run(test_ui())