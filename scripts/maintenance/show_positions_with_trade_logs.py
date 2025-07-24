#!/usr/bin/env python3
"""
Show all open positions with their corresponding trading log data.
Reads from multiple sources to find the most complete information.
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


def load_all_trading_logs():
    """Load trading logs from all available sources."""
    trade_data = {}
    
    print("📚 Loading trading logs from all sources...")
    
    # 1. Check current_positions_trigger_prices.json
    if os.path.exists("current_positions_trigger_prices.json"):
        try:
            with open("current_positions_trigger_prices.json", 'r') as f:
                data = json.load(f)
                if 'positions' in data:
                    for pos in data['positions']:
                        symbol = pos.get('symbol')
                        side = pos.get('side')
                        if symbol and side:
                            key = f"{symbol}-{side}"
                            tp_prices = [tp.get('price') for tp in pos.get('tp_orders', [])]
                            trade_data[key] = {
                                'source': 'current_positions_trigger_prices.json',
                                'entry_price': pos.get('entry_price'),
                                'tp_prices': tp_prices,
                                'sl_price': pos.get('sl_price'),
                                'size': pos.get('entry_size'),
                                'approach': pos.get('approach'),
                                'timestamp': pos.get('entry_timestamp')
                            }
            print(f"   ✅ Loaded {len(trade_data)} entries from current_positions_trigger_prices.json")
        except Exception as e:
            print(f"   ❌ Error loading current_positions_trigger_prices.json: {e}")
    
    # 2. Check backup trade history
    backup_files = [
        "backups/backup_20250630_095042/data/trade_history.json",
        "backups/comprehensive_20250630_000644/trade_history.json",
        "data/shutdown_backup/20250630_004554_trade_history.json"
    ]
    
    for backup_file in backup_files:
        if os.path.exists(backup_file):
            try:
                with open(backup_file, 'r') as f:
                    data = json.load(f)
                    count = 0
                    if isinstance(data, dict):
                        for trade_id, trade_info in data.items():
                            symbol = trade_info.get('symbol')
                            side = trade_info.get('side')
                            if symbol and side:
                                key = f"{symbol}-{side}"
                                if key not in trade_data:  # Don't overwrite newer data
                                    tp_prices = []
                                    for tp in trade_info.get('tp_orders', []):
                                        if 'price' in tp:
                                            tp_prices.append(tp['price'])
                                    
                                    sl_price = None
                                    if 'sl_order' in trade_info and isinstance(trade_info['sl_order'], dict):
                                        sl_price = trade_info['sl_order'].get('price')
                                    
                                    entry_data = trade_info.get('entry', {})
                                    
                                    trade_data[key] = {
                                        'source': backup_file,
                                        'entry_price': entry_data.get('price'),
                                        'tp_prices': tp_prices,
                                        'sl_price': sl_price,
                                        'size': entry_data.get('size'),
                                        'approach': trade_info.get('approach'),
                                        'timestamp': entry_data.get('timestamp')
                                    }
                                    count += 1
                    print(f"   ✅ Added {count} new entries from {backup_file}")
            except Exception as e:
                print(f"   ❌ Error loading {backup_file}: {e}")
    
    return trade_data


async def show_positions_with_logs():
    """Show all positions with their trading log data."""
    
    print("📊 Main Account Positions with Trading Log Data")
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
    
    # Load all trading logs
    trade_logs = load_all_trading_logs()
    print(f"\n📚 Total trading log entries found: {len(trade_logs)}")
    
    # Get all positions
    print("\n📋 Fetching current positions...")
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
        for pos in active_positions:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos.get('avgPrice', 0))
            mark_price = float(pos.get('markPrice', 0))
            pnl = float(pos.get('unrealisedPnl', 0))
            position_idx = pos.get('positionIdx', 0)
            
            print(f"\n{'='*70}")
            print(f"🔸 {symbol} {side}")
            print(f"{'='*70}")
            
            # Position info
            print(f"📊 Current Position:")
            print(f"   Size: {size:,.0f}")
            print(f"   Entry Price: ${avg_price:.4f}")
            print(f"   Current Price: ${mark_price:.4f}")
            print(f"   P&L: ${pnl:,.2f}")
            print(f"   Position Index: {position_idx}")
            
            # Get current orders
            try:
                order_resp = client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    openOnly=1,
                    limit=50
                )
                
                if order_resp['retCode'] == 0:
                    orders = order_resp['result']['list']
                    
                    # Count current orders
                    tp_count = 0
                    sl_count = 0
                    
                    current_tp_prices = []
                    current_sl_price = None
                    
                    for order in orders:
                        if order.get('reduceOnly') and order.get('orderStatus') in ['New', 'Untriggered']:
                            trigger_price_str = order.get('triggerPrice', '')
                            if trigger_price_str and trigger_price_str != '0':
                                trigger_price = float(trigger_price_str)
                                
                                if side == 'Buy':
                                    if trigger_price > avg_price:
                                        tp_count += 1
                                        current_tp_prices.append(trigger_price)
                                    else:
                                        sl_count += 1
                                        current_sl_price = trigger_price
                                else:  # Sell
                                    if trigger_price < avg_price:
                                        tp_count += 1
                                        current_tp_prices.append(trigger_price)
                                    else:
                                        sl_count += 1
                                        current_sl_price = trigger_price
                    
                    # Sort TPs
                    if side == 'Buy':
                        current_tp_prices.sort()
                    else:
                        current_tp_prices.sort(reverse=True)
                    
                    print(f"\n📈 Current Orders:")
                    print(f"   Take Profits: {tp_count}")
                    if current_tp_prices:
                        for i, tp in enumerate(current_tp_prices):
                            print(f"      TP{i+1}: ${tp:.4f}")
                    
                    print(f"   Stop Losses: {sl_count}")
                    if current_sl_price:
                        print(f"      SL: ${current_sl_price:.4f}")
                    
            except Exception as e:
                print(f"\n❌ Error fetching orders: {e}")
            
            # Get trading log data
            key = f"{symbol}-{side}"
            log_data = trade_logs.get(key)
            
            if log_data:
                print(f"\n📚 Trading Log Data:")
                print(f"   Source: {log_data['source']}")
                
                if log_data.get('approach'):
                    print(f"   Approach: {log_data['approach']}")
                
                if log_data.get('entry_price'):
                    print(f"   Entry Price (from logs): ${log_data['entry_price']}")
                
                if log_data.get('tp_prices'):
                    print(f"   TP Prices (from logs):")
                    for i, tp in enumerate(log_data['tp_prices']):
                        print(f"      TP{i+1}: ${tp}")
                
                if log_data.get('sl_price'):
                    print(f"   SL Price (from logs): ${log_data['sl_price']}")
                
                if log_data.get('size'):
                    print(f"   Original Size: {log_data['size']}")
                
                if log_data.get('timestamp'):
                    print(f"   Trade Time: {log_data['timestamp']}")
                
                # Compare current orders with logs
                print(f"\n🔍 Comparison:")
                
                # Check TPs
                if log_data.get('tp_prices') and current_tp_prices:
                    if len(current_tp_prices) == len(log_data['tp_prices']):
                        matches = True
                        for i, (current, logged) in enumerate(zip(current_tp_prices, log_data['tp_prices'])):
                            if abs(current - float(logged)) > 0.0001:
                                matches = False
                                print(f"   ⚠️ TP{i+1} mismatch: Current ${current:.4f} vs Logged ${logged}")
                        if matches:
                            print(f"   ✅ All TP prices match the logs")
                    else:
                        print(f"   ⚠️ TP count mismatch: {len(current_tp_prices)} current vs {len(log_data['tp_prices'])} in logs")
                
                # Check SL
                if log_data.get('sl_price') and current_sl_price:
                    if abs(current_sl_price - float(log_data['sl_price'])) < 0.0001:
                        print(f"   ✅ SL price matches the logs")
                    else:
                        print(f"   ⚠️ SL mismatch: Current ${current_sl_price:.4f} vs Logged ${log_data['sl_price']}")
                
            else:
                print(f"\n⚠️ No trading log data found for {key}")
        
        # Summary of log coverage
        print(f"\n\n{'='*70}")
        print("📊 TRADING LOG COVERAGE SUMMARY")
        print(f"{'='*70}")
        
        positions_with_logs = 0
        for pos in active_positions:
            key = f"{pos['symbol']}-{pos['side']}"
            if key in trade_logs:
                positions_with_logs += 1
        
        print(f"\nTotal Active Positions: {len(active_positions)}")
        print(f"Positions with Trading Logs: {positions_with_logs}")
        print(f"Positions without Logs: {len(active_positions) - positions_with_logs}")
        
        # List positions without logs
        if positions_with_logs < len(active_positions):
            print(f"\nPositions without trading logs:")
            for pos in active_positions:
                key = f"{pos['symbol']}-{pos['side']}"
                if key not in trade_logs:
                    print(f"   - {pos['symbol']} {pos['side']}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    await show_positions_with_logs()


if __name__ == "__main__":
    asyncio.run(main())