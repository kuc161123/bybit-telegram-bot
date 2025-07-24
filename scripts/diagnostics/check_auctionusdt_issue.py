#!/usr/bin/env python3
"""
Check AUCTIONUSDT TP1 hit but no alert and limit orders not cancelled
"""
import pickle
import sys
import os
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

def check_auctionusdt():
    """Check AUCTIONUSDT monitor and order status"""
    try:
        # Load pickle file
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        print("🔍 CHECKING AUCTIONUSDT TP1 ISSUE")
        print("=" * 60)
        
        # Check Enhanced TP/SL monitors
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Find AUCTIONUSDT monitors
        print("\n📊 AUCTIONUSDT Monitors:")
        auction_monitors = {}
        for key, monitor in enhanced_monitors.items():
            if 'AUCTIONUSDT' in key:
                auction_monitors[key] = monitor
                print(f"\n📋 Monitor: {key}")
                print(f"  Symbol: {monitor.get('symbol')}")
                print(f"  Side: {monitor.get('side')}")
                print(f"  Entry Price: {monitor.get('entry_price')}")
                print(f"  Position Size: {monitor.get('position_size')}")
                print(f"  Remaining Size: {monitor.get('remaining_size')}")
                print(f"  Phase: {monitor.get('phase')}")
                print(f"  Monitoring Active: {monitor.get('monitoring_active')}")
                print(f"  Limit Orders Cancelled: {monitor.get('limit_orders_cancelled')}")
                print(f"  Account Type: {monitor.get('account_type', 'main')}")
                
                # Check TP orders
                tp_orders = monitor.get('tp_orders', {})
                print(f"\n  TP Orders:")
                for tp_id, tp_data in tp_orders.items():
                    print(f"    {tp_id}:")
                    print(f"      Price: {tp_data.get('price')}")
                    print(f"      Quantity: {tp_data.get('qty')}")
                    print(f"      Filled: {tp_data.get('filled', False)}")
                    print(f"      Order ID: {tp_data.get('order_id', 'N/A')}")
                
                # Check SL order
                sl_order = monitor.get('sl_order', {})
                print(f"\n  SL Order:")
                if sl_order:
                    print(f"    Price: {sl_order.get('price')}")
                    print(f"    Quantity: {sl_order.get('qty')}")
                    print(f"    Order ID: {sl_order.get('order_id', 'N/A')}")
                else:
                    print(f"    No SL order data")
                
                # Check limit orders
                limit_orders = monitor.get('limit_orders', [])
                print(f"\n  Limit Orders: {len(limit_orders)} orders")
                for order in limit_orders:
                    print(f"    Order ID: {order.get('order_id')}, Status: {order.get('status', 'unknown')}")
        
        # Check chat data for positions
        print("\n\n📊 AUCTIONUSDT Position Data:")
        user_data = data.get('user_data', {})
        for chat_id, chat_data in user_data.items():
            positions = chat_data.get('positions', {})
            for pos_key, pos_data in positions.items():
                if 'AUCTIONUSDT' in pos_key:
                    print(f"\n📋 Position: {pos_key}")
                    print(f"  Chat ID: {chat_id}")
                    print(f"  Symbol: {pos_data.get('symbol')}")
                    print(f"  Side: {pos_data.get('side')}")
                    print(f"  Size: {pos_data.get('size')}")
                    print(f"  Filled: {pos_data.get('filled')}")
                    print(f"  Entry Price: {pos_data.get('entry_price')}")
                    print(f"  Approach: {pos_data.get('approach')}")
                    print(f"  Account Type: {pos_data.get('account_type', 'main')}")
                    
                    # Check alerts
                    alerts = pos_data.get('alerts', {})
                    print(f"\n  Alerts Sent:")
                    print(f"    Entry: {alerts.get('entry', False)}")
                    print(f"    TP1: {alerts.get('tp1', False)}")
                    print(f"    TP2: {alerts.get('tp2', False)}")
                    print(f"    TP3: {alerts.get('tp3', False)}")
                    print(f"    TP4: {alerts.get('tp4', False)}")
                    print(f"    SL: {alerts.get('sl', False)}")
                    print(f"    Breakeven: {alerts.get('breakeven', False)}")
        
        # Now check actual orders from API
        print("\n\n📊 Checking Live Orders from API...")
        from dotenv import load_dotenv
        load_dotenv()
        
        # Import after env vars are loaded
        from clients.bybit_client import create_bybit_client
        from execution.mirror_trader import bybit_client_2
        
        # Check main account
        bybit_client = create_bybit_client()
        print("\n📈 Main Account AUCTIONUSDT Orders:")
        try:
            # Get open orders
            orders = bybit_client.get_open_orders(
                category="linear",
                symbol="AUCTIONUSDT"
            )
            
            if orders['retCode'] == 0:
                order_list = orders['result']['list']
                print(f"  Total open orders: {len(order_list)}")
                for order in order_list:
                    print(f"\n  Order:")
                    print(f"    ID: {order.get('orderId')}")
                    print(f"    Side: {order.get('side')}")
                    print(f"    Type: {order.get('orderType')}")
                    print(f"    Price: {order.get('price')}")
                    print(f"    Qty: {order.get('qty')}")
                    print(f"    Status: {order.get('orderStatus')}")
                    print(f"    Reduce Only: {order.get('reduceOnly')}")
                    print(f"    Stop Order Type: {order.get('stopOrderType', 'N/A')}")
            
            # Get position
            positions = bybit_client.get_positions(
                category="linear",
                symbol="AUCTIONUSDT"
            )
            
            if positions['retCode'] == 0:
                for pos in positions['result']['list']:
                    if float(pos.get('size', 0)) > 0:
                        print(f"\n  Current Position:")
                        print(f"    Side: {pos.get('side')}")
                        print(f"    Size: {pos.get('size')}")
                        print(f"    Avg Price: {pos.get('avgPrice')}")
                        print(f"    Mark Price: {pos.get('markPrice')}")
                        print(f"    Unrealized PnL: {pos.get('unrealisedPnl')}")
        except Exception as e:
            print(f"  Error checking main orders: {e}")
        
        # Check mirror account
        if bybit_client_2:
            print("\n\n🪞 Mirror Account AUCTIONUSDT Orders:")
            try:
                orders = bybit_client_2.get_open_orders(
                    category="linear",
                    symbol="AUCTIONUSDT"
                )
                
                if orders['retCode'] == 0:
                    order_list = orders['result']['list']
                    print(f"  Total open orders: {len(order_list)}")
                    for order in order_list:
                        print(f"\n  Order:")
                        print(f"    ID: {order.get('orderId')}")
                        print(f"    Side: {order.get('side')}")
                        print(f"    Type: {order.get('orderType')}")
                        print(f"    Price: {order.get('price')}")
                        print(f"    Qty: {order.get('qty')}")
                        print(f"    Status: {order.get('orderStatus')}")
                        print(f"    Reduce Only: {order.get('reduceOnly')}")
                
                # Get position
                positions = bybit_client_2.get_positions(
                    category="linear",
                    symbol="AUCTIONUSDT"
                )
                
                if positions['retCode'] == 0:
                    for pos in positions['result']['list']:
                        if float(pos.get('size', 0)) > 0:
                            print(f"\n  Current Position:")
                            print(f"    Side: {pos.get('side')}")
                            print(f"    Size: {pos.get('size')}")
                            print(f"    Avg Price: {pos.get('avgPrice')}")
                            print(f"    Mark Price: {pos.get('markPrice')}")
            except Exception as e:
                print(f"  Error checking mirror orders: {e}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_auctionusdt()