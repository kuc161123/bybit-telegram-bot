#!/usr/bin/env python3
"""
Close positions that have no TP orders (all TPs have been hit)
This handles both main and mirror accounts
"""

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


async def check_and_close_positions_without_tps():
    """Check for positions without TP orders and close them"""
    
    # Initialize main client
    session = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    print("=" * 60)
    print("CHECKING FOR POSITIONS WITHOUT TP ORDERS")
    print("=" * 60)
    
    # Process main account
    print("\n=== MAIN ACCOUNT ===")
    await process_account(session, "main")
    
    # Process mirror account if enabled
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        print("\n=== MIRROR ACCOUNT ===")
        mirror_session = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        await process_account(mirror_session, "mirror")
    
    print("\n" + "=" * 60)
    print("✅ Check complete!")
    print("=" * 60)


async def process_account(session, account_type: str):
    """Process positions for a specific account"""
    
    positions_to_close = []
    
    try:
        # Get all positions
        position_result = session.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if position_result.get("retCode") == 0:
            positions = position_result.get("result", {}).get("list", [])
            
            print(f"\nFound {len(positions)} positions on {account_type} account")
            
            for position in positions:
                symbol = position.get("symbol", "")
                side = position.get("side", "")
                size = float(position.get("size", "0"))
                
                if size > 0:
                    # Get open orders for this symbol
                    orders_result = session.get_open_orders(
                        category="linear",
                        symbol=symbol
                    )
                    
                    if orders_result.get("retCode") == 0:
                        orders = orders_result.get("result", {}).get("list", [])
                        
                        # Check for TP orders
                        tp_orders = [
                            order for order in orders 
                            if order.get("orderType") == "Limit" 
                            and order.get("reduceOnly") == True
                            and ((side == "Buy" and order.get("side") == "Sell") or 
                                 (side == "Sell" and order.get("side") == "Buy"))
                        ]
                        
                        # Also check orderLinkId for TP identification
                        tp_orders.extend([
                            order for order in orders
                            if "TP" in str(order.get("orderLinkId", ""))
                        ])
                        
                        # Remove duplicates
                        tp_order_ids = list(set(order.get("orderId") for order in tp_orders))
                        
                        if not tp_order_ids:
                            # No TP orders found
                            pnl = float(position.get("unrealisedPnl", 0))
                            pnl_ratio = float(position.get("unrealisedPnlRatio", 0)) * 100
                            
                            print(f"\n❗ Position without TPs found:")
                            print(f"   Symbol: {symbol}")
                            print(f"   Side: {side} {size} contracts")
                            print(f"   P&L: ${pnl:.2f} ({pnl_ratio:.2f}%)")
                            print(f"   Total orders: {len(orders)}")
                            
                            positions_to_close.append({
                                'symbol': symbol,
                                'side': side,
                                'size': size,
                                'pnl': pnl,
                                'orders': orders
                            })
                        else:
                            print(f"\n✅ {symbol} {side} has {len(tp_order_ids)} TP order(s)")
                    
        else:
            print(f"❌ Failed to get positions: {position_result.get('retMsg', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error processing {account_type} account: {e}")
        return
    
    # Close positions without TPs
    if positions_to_close:
        print(f"\n🎯 Found {len(positions_to_close)} position(s) to close on {account_type} account")
        
        confirm = input("\nDo you want to close these positions? (yes/no): ")
        if confirm.lower() == 'yes':
            for pos in positions_to_close:
                await close_position_and_orders(session, pos, account_type)
        else:
            print("❌ Operation cancelled")
    else:
        print(f"\n✅ No positions without TPs found on {account_type} account")


async def close_position_and_orders(session, position_data: dict, account_type: str):
    """Close a position and cancel all its orders"""
    
    symbol = position_data['symbol']
    side = position_data['side']
    size = position_data['size']
    
    print(f"\n🔄 Closing {symbol} position on {account_type} account...")
    
    try:
        # First, cancel all open orders
        try:
            cancel_result = session.cancel_all_orders(
                category="linear",
                symbol=symbol
            )
            if cancel_result.get("retCode") == 0:
                print(f"  ✅ Cancelled all orders for {symbol}")
            else:
                print(f"  ⚠️  Failed to cancel orders: {cancel_result.get('retMsg', 'Unknown error')}")
        except Exception as e:
            print(f"  ⚠️  Error cancelling orders: {e}")
        
        # Close the position with market order
        close_side = "Sell" if side == "Buy" else "Buy"
        
        try:
            order_result = session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(size),
                reduceOnly=True
            )
            
            if order_result.get("retCode") == 0:
                print(f"  ✅ Successfully closed {symbol} position")
                order_id = order_result.get("result", {}).get("orderId", "")
                print(f"  📋 Order ID: {order_id}")
            else:
                print(f"  ❌ Failed to close position: {order_result.get('retMsg', 'Unknown error')}")
                
        except Exception as e:
            print(f"  ❌ Error closing position: {e}")
            
    except Exception as e:
        print(f"  ❌ Error processing {symbol}: {e}")


if __name__ == "__main__":
    asyncio.run(check_and_close_positions_without_tps())