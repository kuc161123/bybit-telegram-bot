#!/usr/bin/env python3
"""
Final comprehensive summary of all positions and their orders.
Shows current status and what matches/doesn't match the trade logs.
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


def load_trading_logs():
    """Load trading logs from current_positions_trigger_prices.json."""
    trade_data = {}
    
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
                                'entry_price': pos.get('entry_price'),
                                'tp_prices': tp_prices,
                                'sl_price': pos.get('sl_price'),
                                'size': pos.get('entry_size'),
                                'approach': pos.get('approach'),
                                'timestamp': pos.get('entry_timestamp')
                            }
            return trade_data
        except Exception as e:
            print(f"❌ Error loading trade logs: {e}")
            return {}
    return {}


async def final_summary():
    """Create final comprehensive summary."""
    
    print("📊 FINAL POSITION AND ORDER SUMMARY")
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
    
    # Load trading logs
    trade_logs = load_trading_logs()
    
    # Get all positions
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
        
        print(f"\n📋 Total Active Positions: {len(active_positions)}")
        print(f"📚 Trade Log Entries: {len(trade_logs)}")
        
        # Categories
        perfect_positions = []
        minor_issues = []
        major_issues = []
        
        print("\n" + "="*80)
        print("DETAILED POSITION ANALYSIS")
        print("="*80)
        
        for pos in active_positions:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos.get('avgPrice', 0))
            pnl = float(pos.get('unrealisedPnl', 0))
            
            # Get current orders
            tp_count = 0
            sl_count = 0
            current_tp_prices = []
            current_sl_prices = []
            
            try:
                order_resp = client.get_open_orders(
                    category="linear",
                    symbol=symbol,
                    openOnly=0,
                    limit=50
                )
                
                if order_resp['retCode'] == 0:
                    for order in order_resp['result']['list']:
                        if order.get('orderStatus') in ['New', 'Untriggered'] and order.get('reduceOnly'):
                            trigger_price_str = order.get('triggerPrice', '')
                            if trigger_price_str and trigger_price_str != '0':
                                try:
                                    trigger_price = float(trigger_price_str)
                                    
                                    if side == 'Buy':
                                        if trigger_price > avg_price:
                                            tp_count += 1
                                            current_tp_prices.append(trigger_price)
                                        else:
                                            sl_count += 1
                                            current_sl_prices.append(trigger_price)
                                    else:
                                        if trigger_price < avg_price:
                                            tp_count += 1
                                            current_tp_prices.append(trigger_price)
                                        else:
                                            sl_count += 1
                                            current_sl_prices.append(trigger_price)
                                except:
                                    pass
            except:
                pass
            
            # Sort prices
            if side == 'Buy':
                current_tp_prices.sort()
            else:
                current_tp_prices.sort(reverse=True)
            current_sl_prices.sort()
            
            # Get trade log data
            key = f"{symbol}-{side}"
            log_data = trade_logs.get(key)
            
            # Determine status
            status = "❓"
            issues = []
            
            if tp_count == 4 and sl_count == 1:
                if log_data:
                    # Check if prices match logs
                    matches = True
                    if log_data.get('tp_prices'):
                        for i, (current, expected) in enumerate(zip(current_tp_prices, log_data['tp_prices'])):
                            if abs(current - float(expected)) > 0.0001:
                                matches = False
                                issues.append(f"TP{i+1} price mismatch")
                    
                    if log_data.get('sl_price') and current_sl_prices:
                        if abs(current_sl_prices[0] - float(log_data['sl_price'])) > 0.0001:
                            matches = False
                            issues.append("SL price mismatch")
                    
                    if matches:
                        status = "✅"
                        perfect_positions.append(symbol)
                    else:
                        status = "⚠️"
                        minor_issues.append(symbol)
                else:
                    status = "✅"  # Has orders but no logs
                    perfect_positions.append(symbol)
            else:
                status = "❌"
                major_issues.append(symbol)
                if tp_count != 4:
                    issues.append(f"Wrong TP count: {tp_count}")
                if sl_count != 1:
                    issues.append(f"Wrong SL count: {sl_count}")
            
            # Display
            print(f"\n{status} {symbol} {side}")
            print(f"   Size: {size:,.0f} | P&L: ${pnl:,.2f}")
            print(f"   Orders: {tp_count} TPs, {sl_count} SLs")
            
            if log_data:
                print(f"   Trade Log: Found ✅")
            else:
                print(f"   Trade Log: Not found ⚠️")
            
            if issues:
                print(f"   Issues: {', '.join(issues)}")
        
        # Final Summary
        print("\n\n" + "="*80)
        print("SUMMARY STATISTICS")
        print("="*80)
        
        print(f"\n✅ Perfect Positions (4 TPs + 1 SL): {len(perfect_positions)}")
        if perfect_positions:
            print(f"   {', '.join(perfect_positions)}")
        
        print(f"\n⚠️ Minor Issues (orders exist but prices differ): {len(minor_issues)}")
        if minor_issues:
            print(f"   {', '.join(minor_issues)}")
        
        print(f"\n❌ Major Issues (missing orders): {len(major_issues)}")
        if major_issues:
            print(f"   {', '.join(major_issues)}")
        
        # Calculate total P&L
        total_pnl = sum(float(p.get('unrealisedPnl', 0)) for p in active_positions)
        print(f"\n💰 Total Unrealized P&L: ${total_pnl:,.2f}")
        
        # Recommendations
        if major_issues:
            print("\n\n" + "="*80)
            print("📌 RECOMMENDATIONS")
            print("="*80)
            
            print("\nPositions needing immediate attention:")
            for symbol in major_issues:
                print(f"   - {symbol}: Add missing orders")
            
            print("\n💡 The bot's position mode handler has been updated.")
            print("   Future orders should work correctly in hedge mode.")
        
        print("\n\n✅ Summary complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    await final_summary()


if __name__ == "__main__":
    asyncio.run(main())