#!/usr/bin/env python3
"""
Show all open positions on main account with their orders and trading log data.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from decimal import Decimal
from collections import defaultdict
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


def load_all_trade_data():
    """Load trade data from all available sources."""
    trade_data = {}
    
    print("📚 Loading trade data from available sources...")
    
    # Try to load from trade history JSON
    if os.path.exists("data/trade_history.json"):
        try:
            with open("data/trade_history.json", 'r') as f:
                content = f.read().strip()
                if content and content != '[]':
                    data = json.loads(content)
                    if isinstance(data, list):
                        for entry in data:
                            if isinstance(entry, dict) and entry.get('type') == 'position_opened':
                                symbol = entry.get('symbol')
                                side = entry.get('side')
                                if symbol and side:
                                    key = f"{symbol}-{side}"
                                    trade_data[key] = {
                                        'entry_price': entry.get('entry_price'),
                                        'tp_prices': entry.get('tp_prices', []),
                                        'sl_price': entry.get('sl_price'),
                                        'size': entry.get('total_size'),
                                        'timestamp': entry.get('timestamp')
                                    }
                        print(f"   Loaded {len(trade_data)} entries from trade_history.json")
        except Exception as e:
            print(f"   Error loading trade_history.json: {e}")
    
    # Try to load from pickle file
    if os.path.exists("bybit_bot_dashboard_v4.1_enhanced.pkl"):
        try:
            import pickle
            with open("bybit_bot_dashboard_v4.1_enhanced.pkl", 'rb') as f:
                pkl_data = pickle.load(f)
                
                # Look for trade logs in pickle
                if 'trade_logs' in pkl_data:
                    logs = pkl_data['trade_logs']
                    if isinstance(logs, dict):
                        for key, log_data in logs.items():
                            if isinstance(log_data, dict):
                                symbol = log_data.get('symbol')
                                side = log_data.get('side')
                                if symbol and side:
                                    trade_key = f"{symbol}-{side}"
                                    if trade_key not in trade_data:
                                        trade_data[trade_key] = {
                                            'entry_price': log_data.get('entry_price'),
                                            'tp_prices': log_data.get('tp_prices', []),
                                            'sl_price': log_data.get('sl_price'),
                                            'size': log_data.get('size'),
                                            'timestamp': log_data.get('timestamp')
                                        }
                        print(f"   Added data from pickle file, total entries: {len(trade_data)}")
        except Exception as e:
            print(f"   Error loading pickle file: {e}")
    
    # Try to load from any backup files
    for filename in os.listdir('.'):
        if filename.startswith('trade_') and filename.endswith('.json'):
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                    # Process similar to above
                    print(f"   Found backup file: {filename}")
            except:
                pass
    
    return trade_data


async def show_positions_and_orders():
    """Show all positions with their orders and trading log data."""
    
    print("📊 Main Account - All Open Positions with Orders")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        USE_TESTNET
    )
    
    if not all([BYBIT_API_KEY, BYBIT_API_SECRET]):
        print("❌ API credentials not configured")
        return
    
    # Initialize client
    client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    # Load trade data
    trade_data = load_all_trade_data()
    
    # Get all positions
    print("\n📋 Fetching all positions...")
    try:
        response = client.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if response['retCode'] != 0:
            print(f"❌ Error: {response['retMsg']}")
            return
        
        all_positions = response['result']['list']
        active_positions = [p for p in all_positions if float(p.get('size', 0)) > 0]
        
        print(f"Found {len(active_positions)} active position(s)\n")
        
        if not active_positions:
            print("✅ No active positions")
            return
        
        # Process each position
        position_summary = []
        
        for pos in active_positions:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos.get('avgPrice', 0))
            mark_price = float(pos.get('markPrice', 0))
            pnl = float(pos.get('unrealisedPnl', 0))
            position_idx = pos.get('positionIdx', 0)
            
            print(f"\n{'='*70}")
            print(f"🔸 {symbol} {side} Position")
            print(f"{'='*70}")
            print(f"📊 Position Details:")
            print(f"   Size: {size:,.0f}")
            print(f"   Entry Price: ${avg_price:.4f}")
            print(f"   Current Price: ${mark_price:.4f}")
            print(f"   Unrealized P&L: ${pnl:,.2f}")
            print(f"   Position Index: {position_idx}")
            
            # Get all orders for this symbol
            print(f"\n📋 Fetching orders...")
            try:
                order_resp = client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    openOnly=0,  # Get all orders
                    limit=50
                )
                
                if order_resp['retCode'] == 0:
                    all_orders = order_resp['result']['list']
                    
                    # Filter and categorize orders
                    limit_entries = []
                    tp_orders = []
                    sl_orders = []
                    other_orders = []
                    
                    for order in all_orders:
                        status = order.get('orderStatus', '')
                        order_type = order.get('orderType', '')
                        stop_type = order.get('stopOrderType', '')
                        order_side = order.get('side', '')
                        trigger_price = float(order.get('triggerPrice', 0))
                        price = float(order.get('price', 0))
                        qty = float(order.get('qty', 0))
                        reduce_only = order.get('reduceOnly', False)
                        order_idx = order.get('positionIdx', 0)
                        
                        # Only consider active orders
                        if status not in ['New', 'PartiallyFilled', 'Untriggered']:
                            continue
                        
                        # Categorize order
                        if not reduce_only and order_side == side:
                            # Entry order
                            if order_type == 'Limit':
                                limit_entries.append({
                                    'price': price,
                                    'qty': qty,
                                    'status': status
                                })
                        elif reduce_only:
                            # TP or SL
                            if trigger_price > 0:
                                if side == 'Buy':
                                    if trigger_price > avg_price:
                                        tp_orders.append({
                                            'price': trigger_price,
                                            'qty': qty,
                                            'status': status,
                                            'idx': order_idx
                                        })
                                    else:
                                        sl_orders.append({
                                            'price': trigger_price,
                                            'qty': qty,
                                            'status': status,
                                            'idx': order_idx
                                        })
                                else:  # Sell
                                    if trigger_price < avg_price:
                                        tp_orders.append({
                                            'price': trigger_price,
                                            'qty': qty,
                                            'status': status,
                                            'idx': order_idx
                                        })
                                    else:
                                        sl_orders.append({
                                            'price': trigger_price,
                                            'qty': qty,
                                            'status': status,
                                            'idx': order_idx
                                        })
                            else:
                                other_orders.append({
                                    'type': f"{order_type} {stop_type}".strip(),
                                    'side': order_side,
                                    'price': price,
                                    'qty': qty,
                                    'status': status
                                })
                    
                    # Sort orders
                    limit_entries.sort(key=lambda x: x['price'])
                    if side == 'Buy':
                        tp_orders.sort(key=lambda x: x['price'])
                        sl_orders.sort(key=lambda x: x['price'])
                    else:
                        tp_orders.sort(key=lambda x: x['price'], reverse=True)
                        sl_orders.sort(key=lambda x: x['price'], reverse=True)
                    
                    # Display orders
                    print(f"\n💼 LIMIT ENTRY ORDERS: {len(limit_entries)}")
                    if limit_entries:
                        for i, entry in enumerate(limit_entries):
                            print(f"   Entry {i+1}: ${entry['price']:.4f} for {entry['qty']:,.0f} units ({entry['status']})")
                    
                    print(f"\n📈 TAKE PROFIT ORDERS: {len(tp_orders)}")
                    if tp_orders:
                        for i, tp in enumerate(tp_orders):
                            print(f"   TP{i+1}: ${tp['price']:.4f} for {tp['qty']:,.0f} units ({tp['status']}) [idx={tp['idx']}]")
                    
                    print(f"\n🛡️ STOP LOSS ORDERS: {len(sl_orders)}")
                    if sl_orders:
                        for sl in sl_orders:
                            print(f"   SL: ${sl['price']:.4f} for {sl['qty']:,.0f} units ({sl['status']}) [idx={sl['idx']}]")
                    
                    if other_orders:
                        print(f"\n📦 OTHER ORDERS: {len(other_orders)}")
                        for other in other_orders:
                            print(f"   {other['type']} {other['side']}: ${other['price']:.4f} for {other['qty']:,.0f} ({other['status']})")
                    
                    # Get trade log data
                    key = f"{symbol}-{side}"
                    log_data = trade_data.get(key, {})
                    
                    print(f"\n📚 TRADING LOG DATA:")
                    if log_data:
                        if log_data.get('entry_price'):
                            print(f"   Entry Price: ${float(log_data['entry_price']):.4f}")
                        
                        if log_data.get('tp_prices'):
                            print(f"   TP Prices from logs:")
                            for i, tp_price in enumerate(log_data['tp_prices']):
                                if tp_price:
                                    print(f"      TP{i+1}: ${float(tp_price):.4f}")
                        
                        if log_data.get('sl_price'):
                            print(f"   SL Price from logs: ${float(log_data['sl_price']):.4f}")
                        
                        if log_data.get('size'):
                            print(f"   Original Size: {log_data['size']:,.0f}")
                        
                        if log_data.get('timestamp'):
                            print(f"   Trade Time: {log_data['timestamp']}")
                    else:
                        print(f"   ⚠️ No trading log data found for {key}")
                    
                    # Summary for this position
                    position_summary.append({
                        'symbol': symbol,
                        'side': side,
                        'size': size,
                        'pnl': pnl,
                        'entry_orders': len(limit_entries),
                        'tp_orders': len(tp_orders),
                        'sl_orders': len(sl_orders),
                        'has_logs': bool(log_data)
                    })
                    
            except Exception as e:
                print(f"❌ Error fetching orders: {e}")
        
        # Final summary
        print(f"\n\n{'='*70}")
        print("📊 SUMMARY OF ALL POSITIONS")
        print(f"{'='*70}")
        
        total_pnl = 0
        for pos in position_summary:
            status_parts = []
            
            if pos['entry_orders'] > 0:
                status_parts.append(f"{pos['entry_orders']} Entry")
            
            status_parts.append(f"{pos['tp_orders']} TP")
            status_parts.append(f"{pos['sl_orders']} SL")
            
            if not pos['has_logs']:
                status_parts.append("No Logs")
            
            status = " | ".join(status_parts)
            
            print(f"{pos['symbol']:<12} {pos['side']:<4} - P&L: ${pos['pnl']:>+8,.2f} - Orders: {status}")
            total_pnl += pos['pnl']
        
        print(f"\nTotal Unrealized P&L: ${total_pnl:,.2f}")
        print(f"Total Positions: {len(position_summary)}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    await show_positions_and_orders()


if __name__ == "__main__":
    asyncio.run(main())