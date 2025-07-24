#!/usr/bin/env python3
"""
Sync mirror account orders with proper TP/SL designation.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from config.settings import ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from execution.mirror_trader import bybit_client_2
from clients.bybit_client import bybit_client
from pybit.unified_trading import HTTP


def identify_order_purpose(order):
    """Identify if order is TP or SL based on order details."""
    link_id = order.get('orderLinkId', '').upper()
    
    # Check orderLinkId for hints
    if 'TP' in link_id:
        return 'TP'
    elif 'SL' in link_id:
        return 'SL'
    
    # Check trigger direction and position
    trigger_direction = order.get('triggerDirection', 0)
    side = order.get('side', '')
    reduce_only = order.get('reduceOnly', False)
    
    if not reduce_only:
        return 'LIMIT'
    
    # For reduce orders with triggers:
    # Buy position: TP=Sell with higher trigger, SL=Sell with lower trigger
    # Sell position: TP=Buy with lower trigger, SL=Buy with higher trigger
    # But we need to know the position side, which is opposite of reduce order side
    position_side = 'Buy' if side == 'Sell' else 'Sell'
    
    # Without current price, we can't determine based on price alone
    # But triggerDirection helps: 1=rise above, 2=fall below
    if position_side == 'Buy':
        # Long position
        if trigger_direction == 1:  # Trigger when price rises
            return 'TP'
        else:
            return 'SL'
    else:
        # Short position
        if trigger_direction == 2:  # Trigger when price falls
            return 'TP'
        else:
            return 'SL'
    
    return 'UNKNOWN'


async def sync_orders_properly():
    """Sync orders from main to mirror with proper TP/SL setup."""
    
    print("🔄 PROPER MIRROR ORDER SYNC")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Check configuration
    if not ENABLE_MIRROR_TRADING or not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2:
        print("❌ Mirror trading is not configured")
        return
    
    # Step 1: Cancel all mirror orders
    print("\n🗑️  Cancelling all mirror orders...")
    try:
        orders_resp = bybit_client_2.get_open_orders(
            category="linear",
            settleCoin="USDT",
            limit=200
        )
        
        if orders_resp and orders_resp.get('retCode') == 0:
            orders = orders_resp.get('result', {}).get('list', [])
            cancelled = 0
            
            for order in orders:
                try:
                    cancel_resp = bybit_client_2.cancel_order(
                        category="linear",
                        symbol=order['symbol'],
                        orderId=order['orderId']
                    )
                    if cancel_resp.get('retCode') == 0:
                        cancelled += 1
                except:
                    pass
            
            print(f"   ✅ Cancelled {cancelled} orders")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Wait for cancellations
    await asyncio.sleep(2)
    
    # Step 2: Load trading log for proper TP/SL info
    print("\n📋 Loading trading log for TP/SL information...")
    positions_data = {}
    
    if os.path.exists("current_positions_trigger_prices.json"):
        with open("current_positions_trigger_prices.json", 'r') as f:
            data = json.load(f)
        
        for pos in data.get('positions', []):
            key = f"{pos['symbol']}_{pos['side']}"
            positions_data[key] = pos
        
        print(f"   ✅ Loaded {len(positions_data)} positions from trading log")
    
    # Step 3: Get mirror positions
    print("\n🔍 Checking mirror positions...")
    mirror_positions = {}
    
    pos_resp = bybit_client_2.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    if pos_resp and pos_resp.get('retCode') == 0:
        for pos in pos_resp.get('result', {}).get('list', []):
            if float(pos.get('size', 0)) > 0:
                key = f"{pos['symbol']}_{pos['side']}"
                mirror_positions[key] = pos
    
    print(f"   ✅ Found {len(mirror_positions)} open positions on mirror")
    
    # Step 4: Create orders for each position
    print("\n📝 Creating TP/SL orders for mirror positions...")
    total_created = 0
    
    for pos_key, mirror_pos in mirror_positions.items():
        symbol = mirror_pos['symbol']
        pos_side = mirror_pos['side']
        pos_size = float(mirror_pos['size'])
        
        print(f"\n   {symbol} ({pos_side}):")
        
        # Get trading log data
        log_data = positions_data.get(pos_key)
        if not log_data:
            print(f"      ⚠️  No trading log data found")
            continue
        
        # Create TP orders
        tp_orders = log_data.get('tp_orders', [])
        for i, tp in enumerate(tp_orders):
            try:
                # For TP, order side is opposite of position
                order_side = 'Sell' if pos_side == 'Buy' else 'Buy'
                
                # Scale quantity to actual position size
                orig_total = sum(float(t.get('quantity', 0)) for t in tp_orders)
                if orig_total > 0:
                    scaled_qty = int(pos_size * float(tp['quantity']) / orig_total)
                else:
                    scaled_qty = int(pos_size / len(tp_orders))
                
                if scaled_qty <= 0:
                    continue
                
                # Determine position index
                pos_idx = 1 if pos_side == 'Buy' else 2
                
                # For TP orders on long positions, trigger when price rises above
                # For TP orders on short positions, trigger when price falls below
                trigger_direction = 1 if pos_side == 'Buy' else 2
                
                order_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": order_side,
                    "orderType": "Market",
                    "qty": str(scaled_qty),
                    "triggerPrice": str(tp['price']),
                    "triggerDirection": trigger_direction,
                    "triggerBy": "LastPrice",
                    "reduceOnly": True,
                    "positionIdx": pos_idx,
                    "orderLinkId": f"MIRROR_TP{i+1}_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                }
                
                # Place the order without stopOrderType (since API doesn't accept it properly)
                resp = bybit_client_2.place_order(**order_params)
                if resp.get('retCode') == 0:
                    total_created += 1
                    print(f"      ✅ TP{i+1} created at {tp['price']}")
                else:
                    print(f"      ❌ TP{i+1} failed: {resp.get('retMsg')}")
                    
            except Exception as e:
                print(f"      ❌ TP{i+1} error: {e}")
        
        # Create SL order
        sl_price = log_data.get('sl_price')
        if sl_price:
            try:
                # For SL, order side is opposite of position
                order_side = 'Sell' if pos_side == 'Buy' else 'Buy'
                
                # Determine position index
                pos_idx = 1 if pos_side == 'Buy' else 2
                
                # For SL orders on long positions, trigger when price falls below
                # For SL orders on short positions, trigger when price rises above
                trigger_direction = 2 if pos_side == 'Buy' else 1
                
                order_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": order_side,
                    "orderType": "Market",
                    "qty": str(int(pos_size)),
                    "triggerPrice": str(sl_price),
                    "triggerDirection": trigger_direction,
                    "triggerBy": "LastPrice",
                    "reduceOnly": True,
                    "positionIdx": pos_idx,
                    "orderLinkId": f"MIRROR_SL_{symbol}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                }
                
                resp = bybit_client_2.place_order(**order_params)
                if resp.get('retCode') == 0:
                    total_created += 1
                    print(f"      ✅ SL created at {sl_price}")
                else:
                    print(f"      ❌ SL failed: {resp.get('retMsg')}")
                    
            except Exception as e:
                print(f"      ❌ SL error: {e}")
    
    print(f"\n✅ Total orders created: {total_created}")
    
    # Step 5: Final count
    await asyncio.sleep(2)
    
    print("\n📊 Final order count:")
    final_resp = bybit_client_2.get_open_orders(
        category="linear",
        settleCoin="USDT",
        limit=200
    )
    
    if final_resp and final_resp.get('retCode') == 0:
        orders = final_resp.get('result', {}).get('list', [])
        
        # Analyze orders
        tp_count = 0
        sl_count = 0
        limit_count = 0
        
        for order in orders:
            purpose = identify_order_purpose(order)
            if purpose == 'TP':
                tp_count += 1
            elif purpose == 'SL':
                sl_count += 1
            else:
                limit_count += 1
        
        print(f"\n✅ Total active orders on mirror: {len(orders)}")
        print(f"   Identified as TP: {tp_count}")
        print(f"   Identified as SL: {sl_count}")
        print(f"   Limit/Other: {limit_count}")
        
        # Check by symbol
        print("\n📈 Orders by symbol:")
        symbols = {}
        for order in orders:
            symbol = order['symbol']
            purpose = identify_order_purpose(order)
            
            if symbol not in symbols:
                symbols[symbol] = {'TP': 0, 'SL': 0, 'LIMIT': 0}
            
            if purpose == 'TP':
                symbols[symbol]['TP'] += 1
            elif purpose == 'SL':
                symbols[symbol]['SL'] += 1
            else:
                symbols[symbol]['LIMIT'] += 1
        
        for symbol, counts in sorted(symbols.items()):
            status = "✅" if counts['SL'] > 0 else "⚠️"
            print(f"   {status} {symbol}: {counts['TP']} TP, {counts['SL']} SL, {counts['LIMIT']} limit")


async def main():
    """Main function."""
    await sync_orders_properly()


if __name__ == "__main__":
    asyncio.run(main())