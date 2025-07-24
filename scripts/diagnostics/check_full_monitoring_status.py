#!/usr/bin/env python3
"""
Check complete monitoring status including active positions and alerts
"""

import pickle
import asyncio
from datetime import datetime
from clients.bybit_helpers import get_all_positions, get_all_open_orders
from config.constants import (
    MONITOR_TASKS_KEY,
    CHAT_DATA_KEY,
    ACTIVE_MONITOR_TASK_DATA_V2
)

async def check_monitoring_status():
    # Load the bot data
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        with open(persistence_file, 'rb') as f:
            bot_data = pickle.load(f)
        print("✅ Loaded bot data")
    except Exception as e:
        print(f"❌ Error loading bot data: {e}")
        return
    
    # Get current positions from Bybit
    print("\n🔍 Fetching current positions from Bybit...")
    positions = await get_all_positions()
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    print(f"\n📊 BYBIT POSITIONS: {len(active_positions)} active")
    for pos in active_positions:
        symbol = pos.get('symbol')
        side = pos.get('side')
        size = float(pos.get('size', 0))
        pnl = float(pos.get('unrealisedPnl', 0))
        print(f"   • {symbol} {side}: {size} (P&L: ${pnl:.2f})")
    
    # Check monitor tasks in bot data
    monitor_tasks = bot_data.get(MONITOR_TASKS_KEY, {})
    print(f"\n📊 BOT MONITOR TASKS: {len(monitor_tasks)} registered")
    
    # Check each chat's monitoring data
    chat_data_all = bot_data.get(CHAT_DATA_KEY, {})
    print(f"\n📊 CHAT DATA: {len(chat_data_all)} chats")
    
    for chat_id, chat_data in chat_data_all.items():
        # Check for active monitors in V2 format
        active_monitors_v2 = chat_data.get(ACTIVE_MONITOR_TASK_DATA_V2, {})
        if active_monitors_v2:
            print(f"\n🔍 Chat {chat_id} - Active Monitors V2: {len(active_monitors_v2)}")
            for monitor_key, monitor_data in active_monitors_v2.items():
                if isinstance(monitor_data, dict):
                    symbol = monitor_data.get('symbol', 'Unknown')
                    side = monitor_data.get('side', 'Unknown')
                    approach = monitor_data.get('approach', 'Unknown')
                    
                    print(f"\n   📱 Monitor: {symbol} {side} ({approach})")
                    
                    # Check order tracking
                    if approach == 'conservative':
                        limit_ids = monitor_data.get('conservative_limit_order_ids', [])
                        tp_ids = monitor_data.get('conservative_tp_order_ids', [])
                        sl_id = monitor_data.get('conservative_sl_order_id')
                        
                        print(f"      • Limit Orders: {len(limit_ids)} tracked")
                        print(f"      • TP Orders: {len(tp_ids)} tracked") 
                        print(f"      • SL Order: {'✅ Tracked' if sl_id else '❌ NOT TRACKED'}")
                        
                        # Alert status
                        alerts_working = bool(limit_ids and tp_ids and sl_id)
                        print(f"      • 🔔 ALERTS: {'✅ WORKING' if alerts_working else '⚠️ PARTIAL'}")
                        
                    elif approach == 'fast':
                        tp_id = monitor_data.get('fast_tp_order_id')
                        sl_id = monitor_data.get('fast_sl_order_id')
                        
                        print(f"      • TP Order: {'✅ Tracked' if tp_id else '❌ NOT TRACKED'}")
                        print(f"      • SL Order: {'✅ Tracked' if sl_id else '❌ NOT TRACKED'}")
                        
                        # Alert status
                        alerts_working = bool(tp_id and sl_id)
                        print(f"      • 🔔 ALERTS: {'✅ WORKING' if alerts_working else '⚠️ NOT WORKING'}")
    
    # Check for positions without monitors
    print("\n" + "="*80)
    print("📊 POSITION vs MONITOR ANALYSIS")
    print("="*80)
    
    # Get all monitored symbols
    monitored_symbols = set()
    for chat_data in chat_data_all.values():
        active_monitors_v2 = chat_data.get(ACTIVE_MONITOR_TASK_DATA_V2, {})
        for monitor_data in active_monitors_v2.values():
            if isinstance(monitor_data, dict):
                symbol = monitor_data.get('symbol')
                if symbol:
                    monitored_symbols.add(symbol)
    
    # Check each position
    unmonitored = []
    for pos in active_positions:
        symbol = pos.get('symbol')
        if symbol not in monitored_symbols:
            unmonitored.append(symbol)
    
    if unmonitored:
        print(f"\n⚠️  POSITIONS WITHOUT MONITORS: {len(unmonitored)}")
        for symbol in unmonitored:
            print(f"   • {symbol}")
    else:
        print("\n✅ All positions have monitors!")
    
    # Summary
    print("\n" + "="*80)
    print("📊 FINAL SUMMARY")
    print("="*80)
    print(f"• Active Bybit Positions: {len(active_positions)}")
    print(f"• Active Monitors: {sum(len(cd.get(ACTIVE_MONITOR_TASK_DATA_V2, {})) for cd in chat_data_all.values())}")
    print(f"• Positions without monitors: {len(unmonitored)}")
    
    # Alert status summary
    total_monitors = 0
    working_alerts = 0
    
    for chat_data in chat_data_all.values():
        active_monitors_v2 = chat_data.get(ACTIVE_MONITOR_TASK_DATA_V2, {})
        for monitor_data in active_monitors_v2.values():
            if isinstance(monitor_data, dict):
                total_monitors += 1
                approach = monitor_data.get('approach')
                
                if approach == 'conservative':
                    if (monitor_data.get('conservative_limit_order_ids') and 
                        monitor_data.get('conservative_tp_order_ids') and 
                        monitor_data.get('conservative_sl_order_id')):
                        working_alerts += 1
                elif approach == 'fast':
                    if (monitor_data.get('fast_tp_order_id') and 
                        monitor_data.get('fast_sl_order_id')):
                        working_alerts += 1
    
    print(f"\n🔔 ALERT STATUS:")
    print(f"• Monitors with working alerts: {working_alerts}/{total_monitors}")
    print(f"• Monitors with issues: {total_monitors - working_alerts}/{total_monitors}")
    
    if working_alerts == total_monitors and total_monitors > 0:
        print("\n🎉 ALL ALERTS ARE WORKING!")
        print("✅ You will receive notifications for:")
        print("   • All TP hits")
        print("   • All SL hits") 
        print("   • All limit order fills (Conservative approach)")
    elif total_monitors == 0:
        print("\n⚠️  NO ACTIVE MONITORS FOUND")
        print("The bot may need to be restarted to establish monitors")
    else:
        print("\n⚠️  SOME MONITORS NEED ATTENTION")

if __name__ == "__main__":
    asyncio.run(check_monitoring_status())