#!/usr/bin/env python3
"""
Simple check for alert status
"""

import pickle
import asyncio
from clients.bybit_helpers import get_all_positions

async def check_alerts():
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
    
    print(f"\n📊 ACTIVE POSITIONS: {len(active_positions)}")
    for pos in active_positions:
        symbol = pos.get('symbol')
        side = pos.get('side')
        size = float(pos.get('size', 0))
        pnl = float(pos.get('unrealisedPnl', 0))
        print(f"   • {symbol} {side}: {size} (P&L: ${pnl:.2f})")
    
    # Check monitor tasks
    monitor_tasks = bot_data.get('monitor_tasks', {})
    print(f"\n📊 MONITOR TASKS: {len(monitor_tasks)} found")
    
    # Check chat data
    chat_data_all = bot_data.get('chat_data', {})
    
    print("\n" + "="*80)
    print("🔔 ALERT STATUS BY POSITION")
    print("="*80)
    
    # Check each position for monitoring
    for pos in active_positions:
        symbol = pos.get('symbol')
        side = pos.get('side')
        
        print(f"\n📱 {symbol} {side}:")
        
        # Find monitors for this symbol
        found_monitor = False
        
        # Check all chat data for monitors
        for chat_id, chat_data in chat_data_all.items():
            # Check active_monitor_task_data_v2
            active_monitors = chat_data.get('active_monitor_task_data_v2', {})
            
            for monitor_key, monitor_data in active_monitors.items():
                if isinstance(monitor_data, dict) and monitor_data.get('symbol') == symbol:
                    found_monitor = True
                    approach = monitor_data.get('approach', 'unknown')
                    
                    print(f"   ✅ Monitor found ({approach} approach)")
                    
                    # Check alert tracking
                    if approach == 'conservative':
                        limit_ids = monitor_data.get('conservative_limit_order_ids', [])
                        tp_ids = monitor_data.get('conservative_tp_order_ids', [])
                        sl_id = monitor_data.get('conservative_sl_order_id')
                        
                        print(f"   📋 Order tracking:")
                        print(f"      • Limit orders: {len(limit_ids)} tracked")
                        print(f"      • TP orders: {len(tp_ids)} tracked")
                        print(f"      • SL order: {'✅ Yes' if sl_id else '❌ No'}")
                        
                        if limit_ids and tp_ids and sl_id:
                            print(f"   🔔 ALERTS: ✅ ALL WORKING")
                        else:
                            missing = []
                            if not limit_ids: missing.append("limit fills")
                            if not tp_ids: missing.append("TP hits")
                            if not sl_id: missing.append("SL hits")
                            print(f"   🔔 ALERTS: ⚠️ MISSING: {', '.join(missing)}")
                            
                    elif approach == 'fast':
                        tp_id = monitor_data.get('fast_tp_order_id')
                        sl_id = monitor_data.get('fast_sl_order_id')
                        
                        print(f"   📋 Order tracking:")
                        print(f"      • TP order: {'✅ Yes' if tp_id else '❌ No'}")
                        print(f"      • SL order: {'✅ Yes' if sl_id else '❌ No'}")
                        
                        if tp_id and sl_id:
                            print(f"   🔔 ALERTS: ✅ ALL WORKING")
                        else:
                            missing = []
                            if not tp_id: missing.append("TP hits")
                            if not sl_id: missing.append("SL hits")
                            print(f"   🔔 ALERTS: ⚠️ MISSING: {', '.join(missing)}")
                    
                    break
            
            if found_monitor:
                break
        
        if not found_monitor:
            print(f"   ❌ NO MONITOR FOUND - NO ALERTS!")
    
    # Summary
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    
    # Count positions with working alerts
    positions_with_alerts = 0
    positions_without_alerts = 0
    
    for pos in active_positions:
        symbol = pos.get('symbol')
        has_working_alerts = False
        
        for chat_data in chat_data_all.values():
            active_monitors = chat_data.get('active_monitor_task_data_v2', {})
            
            for monitor_data in active_monitors.values():
                if isinstance(monitor_data, dict) and monitor_data.get('symbol') == symbol:
                    approach = monitor_data.get('approach')
                    
                    if approach == 'conservative':
                        if (monitor_data.get('conservative_limit_order_ids') and 
                            monitor_data.get('conservative_tp_order_ids') and 
                            monitor_data.get('conservative_sl_order_id')):
                            has_working_alerts = True
                    elif approach == 'fast':
                        if (monitor_data.get('fast_tp_order_id') and 
                            monitor_data.get('fast_sl_order_id')):
                            has_working_alerts = True
                    break
        
        if has_working_alerts:
            positions_with_alerts += 1
        else:
            positions_without_alerts += 1
    
    print(f"✅ Positions with working alerts: {positions_with_alerts}/{len(active_positions)}")
    print(f"⚠️  Positions without alerts: {positions_without_alerts}/{len(active_positions)}")
    
    if positions_with_alerts == len(active_positions) and len(active_positions) > 0:
        print("\n🎉 ALL POSITIONS HAVE WORKING ALERTS!")
        print("You will receive notifications for all TP hits, SL hits, and limit fills")
    elif positions_without_alerts > 0:
        print("\n⚠️  SOME POSITIONS NEED ATTENTION")
        print("Restart the bot or run fix scripts for positions without alerts")

if __name__ == "__main__":
    asyncio.run(check_alerts())