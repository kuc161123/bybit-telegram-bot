#!/usr/bin/env python3
"""Close specific positions (PENDLEUSDT, NTRNUSDT, ENAUSDT) on both accounts"""

import asyncio
import logging
from decimal import Decimal
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    BYBIT_API_KEY_2, BYBIT_API_SECRET_2, ENABLE_MIRROR_TRADING
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def close_positions_and_orders():
    """Close specific positions and their orders"""
    
    # Target symbols
    symbols = ["PENDLEUSDT", "NTRNUSDT", "ENAUSDT"]
    
    # Initialize main client
    session = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    print("=== CLOSING POSITIONS ON MAIN ACCOUNT ===\n")
    
    for symbol in symbols:
        print(f"\nProcessing {symbol}:")
        
        try:
            # Cancel all open orders first
            try:
                cancel_result = session.cancel_all_orders(
                    category="linear",
                    symbol=symbol
                )
                if cancel_result.get("retCode") == 0:
                    print(f"  ✅ Cancelled all open orders for {symbol}")
                else:
                    print(f"  ℹ️  No open orders to cancel for {symbol}")
            except Exception as e:
                print(f"  ⚠️  Error cancelling orders: {e}")
            
            # Get current position
            try:
                position_result = session.get_positions(
                    category="linear",
                    symbol=symbol
                )
                
                if position_result.get("retCode") == 0:
                    positions = position_result.get("result", {}).get("list", [])
                    
                    if positions and len(positions) > 0:
                        position = positions[0]
                        size = float(position.get("size", "0"))
                        side = position.get("side", "")
                        
                        if size > 0:
                            # Close the position
                            close_side = "Sell" if side == "Buy" else "Buy"
                            
                            print(f"  Closing position: {side} {size} contracts")
                            
                            order_result = session.place_order(
                                category="linear",
                                symbol=symbol,
                                side=close_side,
                                orderType="Market",
                                qty=str(size),
                                reduceOnly=True
                            )
                            
                            if order_result.get("retCode") == 0:
                                print(f"  ✅ Successfully closed {symbol} position on main account")
                            else:
                                print(f"  ❌ Failed to close position: {order_result.get('retMsg', 'Unknown error')}")
                        else:
                            print(f"  ℹ️  No active position for {symbol}")
                    else:
                        print(f"  ℹ️  No position found for {symbol}")
                        
            except Exception as e:
                print(f"  ❌ Error processing position: {e}")
                
        except Exception as e:
            print(f"  ❌ Error processing {symbol}: {e}")
    
    # Process mirror account if enabled
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        print("\n\n=== CLOSING POSITIONS ON MIRROR ACCOUNT ===\n")
        
        # Initialize mirror client
        mirror_session = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        
        for symbol in symbols:
            print(f"\nProcessing {symbol}:")
            
            try:
                # Cancel all open orders first
                try:
                    cancel_result = mirror_session.cancel_all_orders(
                        category="linear",
                        symbol=symbol
                    )
                    if cancel_result.get("retCode") == 0:
                        print(f"  ✅ Cancelled all open orders for {symbol}")
                    else:
                        print(f"  ℹ️  No open orders to cancel for {symbol}")
                except Exception as e:
                    print(f"  ⚠️  Error cancelling orders: {e}")
                
                # Get current position
                try:
                    position_result = mirror_session.get_positions(
                        category="linear",
                        symbol=symbol
                    )
                    
                    if position_result.get("retCode") == 0:
                        positions = position_result.get("result", {}).get("list", [])
                        
                        if positions and len(positions) > 0:
                            position = positions[0]
                            size = float(position.get("size", "0"))
                            side = position.get("side", "")
                            
                            if size > 0:
                                # Close the position
                                close_side = "Sell" if side == "Buy" else "Buy"
                                
                                print(f"  Closing position: {side} {size} contracts")
                                
                                order_result = mirror_session.place_order(
                                    category="linear",
                                    symbol=symbol,
                                    side=close_side,
                                    orderType="Market",
                                    qty=str(size),
                                    reduceOnly=True
                                )
                                
                                if order_result.get("retCode") == 0:
                                    print(f"  ✅ Successfully closed {symbol} position on mirror account")
                                else:
                                    print(f"  ❌ Failed to close position: {order_result.get('retMsg', 'Unknown error')}")
                            else:
                                print(f"  ℹ️  No active position for {symbol}")
                        else:
                            print(f"  ℹ️  No position found for {symbol}")
                            
                except Exception as e:
                    print(f"  ❌ Error processing position: {e}")
                    
            except Exception as e:
                print(f"  ❌ Error processing {symbol}: {e}")
    
    print("\n\n✅ Position closure process completed!")
    print("\nSummary:")
    print("- Attempted to close positions for: PENDLEUSDT, NTRNUSDT, ENAUSDT")
    print("- Cancelled all related orders")
    print("- Check your Bybit dashboard to verify all positions are closed")

if __name__ == "__main__":
    asyncio.run(close_positions_and_orders())