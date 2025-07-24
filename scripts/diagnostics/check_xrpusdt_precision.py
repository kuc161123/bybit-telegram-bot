#!/usr/bin/env python3
"""Check XRPUSDT instrument info for quantity precision"""
import asyncio
from clients.bybit_client import bybit_client

async def main():
    # Get instrument info
    response = bybit_client.get_instruments_info(
        category="linear",
        symbol="XRPUSDT"
    )
    
    if response and response.get('retCode') == 0:
        instruments = response.get('result', {}).get('list', [])
        if instruments:
            info = instruments[0]
            print("XRPUSDT Instrument Info:")
            print(f"  Min Order Qty: {info['lotSizeFilter']['minOrderQty']}")
            print(f"  Max Order Qty: {info['lotSizeFilter']['maxOrderQty']}")
            print(f"  Qty Step: {info['lotSizeFilter']['qtyStep']}")
            
            print("\nCurrent mirror position size: 87")
            print("85% of 87 = 73.95")
            print("5% of 87 = 4.35")
            
            # Check if quantities are valid
            qty_step = float(info['lotSizeFilter']['qtyStep'])
            min_qty = float(info['lotSizeFilter']['minOrderQty'])
            
            print(f"\nQuantity step: {qty_step}")
            print(f"Minimum quantity: {min_qty}")
            
            # For XRPUSDT, quantities must be whole numbers
            print("\nCorrected quantities:")
            print(f"  TP1 (85%): 74 (rounded from 73.95)")
            print(f"  TP2 (5%): 4 (rounded from 4.35)")
            print(f"  TP3 (5%): 4 (rounded from 4.35)")
            print(f"  TP4 (5%): 5 (to make total = 87)")

if __name__ == "__main__":
    asyncio.run(main())