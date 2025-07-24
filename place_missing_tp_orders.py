#!/usr/bin/env python3
"""
Place missing TP orders for positions that only have SL orders
"""
import asyncio
import sys
import pickle
import time
from decimal import Decimal
from typing import Dict, Any

# Add project root to path
sys.path.append('.')

from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from utils.helpers import value_adjusted_to_step

# Positions missing TP orders (only have SL)
POSITIONS_MISSING_TPS = ['AUCTIONUSDT', 'CRVUSDT', 'SEIUSDT', 'ARBUSDT']

async def place_missing_tp_orders():
    """Place missing TP orders for specific positions using pickle data"""
    
    print("=== PLACING MISSING TP ORDERS ===")
    
    # Load pickle data to get monitor information
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading pickle data: {e}")
        return
    
    # Get monitors from bot_data section
    bot_data = data.get('bot_data', {})
    monitors = bot_data.get('enhanced_tp_sl_monitors', {})
    
    for symbol in POSITIONS_MISSING_TPS:
        print(f"\n🔧 Processing {symbol}...")
        
        # Process main account
        main_key = f"{symbol}_Buy_main"
        if main_key in monitors:
            monitor = monitors[main_key]
            await place_tp_orders_for_position(symbol, monitor, bybit_client, "main")
        else:
            print(f"  ⚠️ No monitor found for {main_key}")
        
        # Process mirror account
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_key = f"{symbol}_Buy_mirror"
            if mirror_key in monitors:
                monitor = monitors[mirror_key]
                await place_tp_orders_for_position(symbol, monitor, bybit_client_2, "mirror")
            else:
                print(f"  ⚠️ No monitor found for {mirror_key}")

async def place_tp_orders_for_position(symbol: str, monitor: Dict[str, Any], client, account: str):
    """Place TP orders for a specific position using monitor data"""
    
    entry_price = float(monitor.get('entry_price', 0))
    remaining_size = float(monitor.get('remaining_size', 0))
    
    if entry_price <= 0 or remaining_size <= 0:
        print(f"  ❌ Invalid data for {symbol} {account}: entry={entry_price}, size={remaining_size}")
        return
    
    print(f"  📊 {symbol} {account}: entry=${entry_price:.6f}, size={remaining_size}")
    
    # Get TP orders from monitor data
    tp_orders = monitor.get('tp_orders', {})
    if not tp_orders:
        print(f"  ❌ No TP orders found in monitor for {symbol} {account}")
        return
    
    # Extract TP prices and quantities from monitor
    tp_data = []
    for order_info in tp_orders.values():
        tp_price = float(order_info.get('price', 0))
        tp_quantity = float(order_info.get('quantity', 0))
        tp_number = order_info.get('tp_number', 0)
        
        # Adjust quantity precision for different symbols
        if symbol == 'ARBUSDT':
            tp_quantity = round(tp_quantity, 1)  # qtyStep=0.1
        else:
            tp_quantity = int(tp_quantity)  # Most symbols use integer quantities
        
        if tp_price > 0 and tp_quantity > 0:
            tp_data.append((tp_number, tp_price, tp_quantity))
    
    if not tp_data:
        print(f"  ❌ No valid TP data found for {symbol} {account}")
        return
    
    # Sort by TP number
    tp_data.sort(key=lambda x: x[0])
    
    print(f"  📋 Found {len(tp_data)} TP orders to place:")
    for tp_num, price, qty in tp_data:
        print(f"    TP{tp_num}: {qty} @ ${price:.6f}")
    
    # Place TP orders
    success_count = 0
    for tp_num, tp_price, tp_quantity in tp_data:
        try:
            # Generate order link ID
            timestamp = int(time.time() * 1000)
            if account == "main":
                order_link_id = f"FIX_TP{tp_num}_{symbol}_{timestamp}"
            else:
                order_link_id = f"FIX_MIR_TP{tp_num}_{symbol}_{timestamp}"
            
            # Place TP order with trigger direction
            result = client.place_order(
                category='linear',
                symbol=symbol,
                side='Sell',  # Sell for Buy positions
                orderType='Market',
                qty=str(tp_quantity),
                triggerPrice=str(tp_price),
                triggerDirection='1',  # Above market for long positions
                reduceOnly=True,
                positionIdx=0,  # Hedge mode
                orderLinkId=order_link_id
            )
            
            if result.get('retCode') == 0:
                order_id = result.get('result', {}).get('orderId', 'Unknown')
                print(f"    ✅ TP{tp_num} placed: {order_id}")
                success_count += 1
            else:
                error_msg = result.get('retMsg', 'Unknown error')
                print(f"    ❌ TP{tp_num} failed: {error_msg}")
                
        except Exception as e:
            print(f"    ❌ TP{tp_num} error: {e}")
        
        # Small delay between orders
        await asyncio.sleep(0.5)
    
    print(f"  📊 {symbol} {account}: {success_count}/{len(tp_data)} TP orders placed successfully")

async def main():
    """Main execution function"""
    print("🚀 Starting TP order placement for positions missing TPs...")
    print(f"📋 Positions to fix: {', '.join(POSITIONS_MISSING_TPS)}")
    
    try:
        await place_missing_tp_orders()
        print("\n✅ TP order placement complete!")
        
    except Exception as e:
        print(f"\n❌ Error during TP placement: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())