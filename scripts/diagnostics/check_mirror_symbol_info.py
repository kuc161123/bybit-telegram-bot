#!/usr/bin/env python3
"""
Check symbol info for correct decimal precision on mirror account
"""
import asyncio
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_helpers import api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

async def check_symbol_info():
    """Check symbol info for all positions"""
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print("❌ Mirror trading is not enabled")
        return
    
    symbols = ["JUPUSDT", "JASMYUSDT", "COTIUSDT", "GALAUSDT", "SANDUSDT"]
    
    print("📊 Symbol Information:\n")
    
    for symbol in symbols:
        try:
            response = await api_call_with_retry(
                lambda: bybit_client_2.get_instruments_info(
                    category="linear",
                    symbol=symbol
                ),
                timeout=30
            )
            
            if response and response.get("retCode") == 0:
                info = response.get("result", {}).get("list", [])[0]
                
                # Extract important info
                lot_size_filter = info.get("lotSizeFilter", {})
                qty_step = lot_size_filter.get("qtyStep", "0.01")
                min_qty = lot_size_filter.get("minOrderQty", "1")
                max_qty = lot_size_filter.get("maxOrderQty", "1000000")
                
                price_filter = info.get("priceFilter", {})
                tick_size = price_filter.get("tickSize", "0.0001")
                
                # Calculate decimal places
                qty_decimals = str(qty_step).split('.')[-1]
                qty_precision = len(qty_decimals) if '.' in str(qty_step) else 0
                
                print(f"{symbol}:")
                print(f"  Qty Step: {qty_step} ({qty_precision} decimals)")
                print(f"  Min Qty: {min_qty}")
                print(f"  Max Qty: {max_qty}")
                print(f"  Tick Size: {tick_size}")
                print()
                
        except Exception as e:
            print(f"❌ Error fetching {symbol}: {e}")

if __name__ == "__main__":
    asyncio.run(check_symbol_info())