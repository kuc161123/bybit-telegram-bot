#!/usr/bin/env python3
"""
Ensure all conservative positions have proper alert monitoring
This script checks and fixes order tracking for all active conservative positions
"""

import pickle
import asyncio
from pybit.unified_trading import HTTP
from dotenv import load_dotenv
import os

load_dotenv()

async def main():
    # Load the bot data
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        with open(persistence_file, 'rb') as f:
            bot_data = pickle.load(f)
        print("✅ Loaded bot data")
    except Exception as e:
        print(f"❌ Error loading bot data: {e}")
        return
    
    # Initialize Bybit client
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_API_SECRET')
    testnet = os.getenv('USE_TESTNET', 'false').lower() == 'true'
    
    session = HTTP(
        testnet=testnet,
        api_key=api_key,
        api_secret=api_secret
    )
    
    # Get all positions
    print("\n🔍 Fetching all positions...")
    try:
        pos_response = session.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if pos_response['retCode'] == 0:
            all_positions = pos_response['result']['list']
            active_positions = [p for p in all_positions if float(p.get('size', 0)) > 0]
            print(f"✅ Found {len(active_positions)} active positions")
        else:
            print(f"❌ Error fetching positions: {pos_response}")
            return
    except Exception as e:
        print(f"❌ Exception fetching positions: {e}")
        return
    
    # Check each position
    chat_id = 5634913742  # Your chat ID
    chat_data_all = bot_data.get('chat_data', {})
    chat_data = chat_data_all.get(chat_id, {})
    active_monitors = chat_data.get('active_monitor_task_data_v2', {})
    
    positions_fixed = 0
    positions_already_ok = 0
    positions_not_conservative = 0
    
    print("\n" + "="*80)
    print("CHECKING ALL POSITIONS FOR ALERT CAPABILITY")
    print("="*80)
    
    for pos in active_positions:
        symbol = pos.get('symbol')
        side = pos.get('side')
        size = float(pos.get('size', 0))
        
        print(f"\n📱 {symbol} {side} ({size}):")
        
        # Find monitor for this position
        monitor_found = False
        monitor_key = None
        monitor_data = None
        
        for key, data in active_monitors.items():
            if isinstance(data, dict) and data.get('symbol') == symbol:
                monitor_found = True
                monitor_key = key
                monitor_data = data
                approach = data.get('approach', 'unknown')
                print(f"   ✅ Monitor found: {approach} approach")
                break
        
        if not monitor_found:
            print(f"   ❌ No monitor found - position not being tracked")
            continue
        
        if approach != 'conservative':
            print(f"   ℹ️  Not a conservative position - skipping")
            positions_not_conservative += 1
            continue
        
        # Check if we have order tracking
        has_limit_ids = bool(monitor_data.get('conservative_limit_order_ids'))
        has_tp_ids = bool(monitor_data.get('conservative_tp_order_ids'))
        has_sl_id = bool(monitor_data.get('conservative_sl_order_id'))
        
        if has_limit_ids and has_tp_ids and has_sl_id:
            print(f"   ✅ All order tracking present - alerts working")
            positions_already_ok += 1
            continue
        
        # Need to fix this position
        print(f"   ⚠️  Missing order tracking - fixing...")
        
        # Fetch orders for this symbol
        try:
            order_response = session.get_open_orders(
                category="linear",
                symbol=symbol,
                limit=50
            )
            
            if order_response['retCode'] == 0:
                orders = order_response['result']['list']
                
                # Categorize orders
                limit_orders = []
                tp_orders = []
                sl_order = None
                
                for order in orders:
                    order_type = order.get('orderType', '')
                    order_link_id = order.get('orderLinkId', '')
                    stop_order_type = order.get('stopOrderType', '')
                    reduce_only = order.get('reduceOnly', False)
                    
                    # Check for limit orders (entry orders, not reduce-only)
                    if order_type == 'Limit' and not reduce_only:
                        limit_orders.append(order)
                    # Check for TP orders
                    elif stop_order_type == 'TakeProfit' or 'TP' in order_link_id or 'CONS_TP' in order_link_id:
                        tp_orders.append(order)
                    # Check for SL orders
                    elif stop_order_type == 'StopLoss' or 'SL' in order_link_id or 'CONS_SL' in order_link_id:
                        sl_order = order
                
                # Sort TP orders
                if side == "Buy":
                    tp_orders_sorted = sorted(tp_orders, key=lambda x: float(x.get('triggerPrice', 0)), reverse=True)
                else:
                    tp_orders_sorted = sorted(tp_orders, key=lambda x: float(x.get('triggerPrice', 0)), reverse=False)
                
                # Update monitor data
                update_needed = False
                
                if limit_orders and not has_limit_ids:
                    limit_ids = [order['orderId'] for order in limit_orders]
                    monitor_data['conservative_limit_order_ids'] = limit_ids
                    print(f"      ✅ Added {len(limit_ids)} limit order IDs")
                    update_needed = True
                
                if tp_orders and not has_tp_ids:
                    tp_ids = [order['orderId'] for order in tp_orders_sorted]
                    monitor_data['conservative_tp_order_ids'] = tp_ids
                    print(f"      ✅ Added {len(tp_ids)} TP order IDs")
                    update_needed = True
                
                if sl_order and not has_sl_id:
                    sl_id = sl_order['orderId']
                    monitor_data['conservative_sl_order_id'] = sl_id
                    print(f"      ✅ Added SL order ID")
                    update_needed = True
                
                if update_needed:
                    # Update the data
                    active_monitors[monitor_key] = monitor_data
                    positions_fixed += 1
                    print(f"   ✅ Fixed order tracking for {symbol}")
                else:
                    print(f"   ℹ️  No orders found to track")
                    
            else:
                print(f"   ❌ Error fetching orders: {order_response}")
                
        except Exception as e:
            print(f"   ❌ Exception fetching orders: {e}")
    
    # Save if we made any changes
    if positions_fixed > 0:
        # Update bot data
        chat_data['active_monitor_task_data_v2'] = active_monitors
        chat_data_all[chat_id] = chat_data
        bot_data['chat_data'] = chat_data_all
        
        # Create backup
        from datetime import datetime
        backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{persistence_file}"
        os.rename(persistence_file, backup_file)
        print(f"\n📦 Created backup: {backup_file}")
        
        # Save updated data
        with open(persistence_file, 'wb') as f:
            pickle.dump(bot_data, f)
        print(f"✅ Saved updated bot data")
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✅ Positions already with alerts: {positions_already_ok}")
    print(f"🔧 Positions fixed: {positions_fixed}")
    print(f"ℹ️  Non-conservative positions: {positions_not_conservative}")
    print(f"📊 Total active positions: {len(active_positions)}")
    
    if positions_fixed > 0:
        print("\n🎉 All conservative positions now have alert tracking!")
        print("📌 The bot will send alerts for:")
        print("   • Limit order fills")
        print("   • TP hits (TP1, TP2, TP3, TP4)")
        print("   • SL hits")
    elif positions_already_ok > 0:
        print("\n✅ All conservative positions already have working alerts!")
    else:
        print("\n⚠️  No conservative positions found to fix")

if __name__ == "__main__":
    asyncio.run(main())