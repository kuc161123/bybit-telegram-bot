#!/usr/bin/env python3
"""
Check JUPUSDT position and monitor status across both accounts
"""

import asyncio
import pickle
import json
from datetime import datetime
from clients.bybit_client import BybitClient
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def check_jupusdt_status():
    print("=" * 80)
    print("JUPUSDT DETAILED STATUS CHECK")
    print("=" * 80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize clients
    main_client = BybitClient(
        testnet=os.getenv('USE_TESTNET', 'false').lower() == 'true',
        api_key=os.getenv('BYBIT_API_KEY'),
        api_secret=os.getenv('BYBIT_API_SECRET'),
        demo_trading=os.getenv('DEMO_TRADING', 'false').lower() == 'true'
    )
    
    mirror_client = BybitClient(
        testnet=os.getenv('USE_TESTNET', 'false').lower() == 'true',
        api_key=os.getenv('BYBIT_API_KEY_2'),
        api_secret=os.getenv('BYBIT_API_SECRET_2'),
        demo_trading=os.getenv('DEMO_TRADING', 'false').lower() == 'true'
    )
    
    # Check pickle file for monitors
    print("📁 CHECKING PICKLE FILE FOR JUPUSDT MONITORS...")
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        # Check Enhanced TP/SL monitors
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        jupusdt_enhanced = []
        for key, monitor in enhanced_monitors.items():
            if 'JUPUSDT' in key:
                jupusdt_enhanced.append((key, monitor))
        
        print(f"\n🔍 Enhanced TP/SL Monitors for JUPUSDT:")
        if jupusdt_enhanced:
            for key, monitor in jupusdt_enhanced:
                print(f"  - Key: {key}")
                print(f"    Account: {monitor.get('account_type', 'Unknown')}")
                print(f"    Created: {monitor.get('created_at', 'Unknown')}")
                print(f"    Active: {monitor.get('active', 'Unknown')}")
        else:
            print("  ❌ No Enhanced TP/SL monitors found for JUPUSDT")
        
        # Check dashboard monitors
        monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
        jupusdt_dashboard = []
        for key, monitor in monitor_tasks.items():
            if 'JUPUSDT' in key:
                jupusdt_dashboard.append((key, monitor))
        
        print(f"\n🖥️ Dashboard Monitors for JUPUSDT:")
        if jupusdt_dashboard:
            for key, monitor in jupusdt_dashboard:
                print(f"  - Key: {key}")
                print(f"    Status: {monitor.get('status', 'Unknown')}")
        else:
            print("  ❌ No dashboard monitors found for JUPUSDT")
            
    except Exception as e:
        print(f"❌ Error reading pickle file: {e}")
    
    # Check main account
    print("\n" + "=" * 60)
    print("MAIN ACCOUNT - JUPUSDT")
    print("=" * 60)
    
    try:
        # Get position
        positions = await main_client.get_positions(symbol="JUPUSDT")
        if positions:
            pos = positions[0]
            print(f"\n📊 POSITION:")
            print(f"  Side: {pos['side']}")
            print(f"  Size: {pos['size']}")
            print(f"  Avg Price: {pos['avgPrice']}")
            print(f"  Mark Price: {pos['markPrice']}")
            print(f"  P&L: ${pos['unrealisedPnl']}")
        else:
            print("\n❌ No JUPUSDT position found")
        
        # Get orders
        orders = await main_client.get_open_orders(symbol="JUPUSDT")
        if orders:
            print(f"\n📝 OPEN ORDERS ({len(orders)} total):")
            tp_orders = []
            sl_orders = []
            limit_orders = []
            
            for order in orders:
                order_type = order.get('stopOrderType', 'Limit')
                if order_type == 'TakeProfit':
                    tp_orders.append(order)
                elif order_type == 'StopLoss':
                    sl_orders.append(order)
                else:
                    limit_orders.append(order)
            
            if tp_orders:
                print(f"\n  ✅ Take Profit Orders ({len(tp_orders)}):")
                total_tp_qty = 0
                for o in tp_orders:
                    print(f"    - Qty: {o['qty']}, Trigger: {o.get('triggerPrice', 'N/A')}, OrderLinkId: {o.get('orderLinkId', 'N/A')}")
                    total_tp_qty += float(o['qty'])
                print(f"    Total TP Quantity: {total_tp_qty}")
            
            if sl_orders:
                print(f"\n  🛑 Stop Loss Orders ({len(sl_orders)}):")
                total_sl_qty = 0
                for o in sl_orders:
                    print(f"    - Qty: {o['qty']}, Trigger: {o.get('triggerPrice', 'N/A')}, OrderLinkId: {o.get('orderLinkId', 'N/A')}")
                    total_sl_qty += float(o['qty'])
                print(f"    Total SL Quantity: {total_sl_qty}")
            
            if limit_orders:
                print(f"\n  📋 Limit Orders ({len(limit_orders)}):")
                for o in limit_orders:
                    print(f"    - Side: {o['side']}, Qty: {o['qty']}, Price: {o['price']}")
        else:
            print("\n❌ No open orders for JUPUSDT")
            
    except Exception as e:
        print(f"\n❌ Error checking main account: {e}")
    
    # Check mirror account
    print("\n" + "=" * 60)
    print("MIRROR ACCOUNT - JUPUSDT")
    print("=" * 60)
    
    try:
        # Get position
        positions = await mirror_client.get_positions(symbol="JUPUSDT")
        if positions:
            pos = positions[0]
            print(f"\n📊 POSITION:")
            print(f"  Side: {pos['side']}")
            print(f"  Size: {pos['size']}")
            print(f"  Avg Price: {pos['avgPrice']}")
            print(f"  Mark Price: {pos['markPrice']}")
            print(f"  P&L: ${pos['unrealisedPnl']}")
        else:
            print("\n❌ No JUPUSDT position found")
        
        # Get orders
        orders = await mirror_client.get_open_orders(symbol="JUPUSDT")
        if orders:
            print(f"\n📝 OPEN ORDERS ({len(orders)} total):")
            tp_orders = []
            sl_orders = []
            limit_orders = []
            
            for order in orders:
                order_type = order.get('stopOrderType', 'Limit')
                if order_type == 'TakeProfit':
                    tp_orders.append(order)
                elif order_type == 'StopLoss':
                    sl_orders.append(order)
                else:
                    limit_orders.append(order)
            
            if tp_orders:
                print(f"\n  ✅ Take Profit Orders ({len(tp_orders)}):")
                for o in tp_orders:
                    print(f"    - Qty: {o['qty']}, Trigger: {o.get('triggerPrice', 'N/A')}")
            else:
                print("\n  ❌ No TP orders found")
            
            if sl_orders:
                print(f"\n  🛑 Stop Loss Orders ({len(sl_orders)}):")
                for o in sl_orders:
                    print(f"    - Qty: {o['qty']}, Trigger: {o.get('triggerPrice', 'N/A')}")
            else:
                print("\n  ❌ No SL orders found")
            
            if limit_orders:
                print(f"\n  📋 Limit Orders ({len(limit_orders)}):")
                for o in limit_orders:
                    print(f"    - Side: {o['side']}, Qty: {o['qty']}, Price: {o['price']}")
        else:
            print("\n❌ No open orders for JUPUSDT")
            
    except Exception as e:
        print(f"\n❌ Error checking mirror account: {e}")
    
    print("\n" + "=" * 80)
    print("JUPUSDT STATUS CHECK COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(check_jupusdt_status())