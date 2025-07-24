#!/usr/bin/env python3
"""
Automatically close positions that have no TP orders (all TPs have been hit)
Enhanced safety checks to ensure we only close positions that truly have no TPs
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
    
    print("=" * 80)
    print("CHECKING FOR POSITIONS WITHOUT TP ORDERS - ENHANCED SAFETY MODE")
    print("=" * 80)
    print("\nCriteria for closing:")
    print("1. Position must have NO take profit orders")
    print("2. Position must have a stop loss order")
    print("3. Only positions with small size (likely remainder after TPs hit)")
    print("=" * 80)
    
    # Process main account
    print("\n=== MAIN ACCOUNT ===")
    main_results = await process_account(session, "main")
    
    # Process mirror account if enabled
    mirror_results = []
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        print("\n=== MIRROR ACCOUNT ===")
        mirror_session = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
        mirror_results = await process_account(mirror_session, "mirror")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    total_closed = len([r for r in main_results + mirror_results if r['closed']])
    total_skipped = len([r for r in main_results + mirror_results if not r['closed']])
    
    print(f"\n✅ Positions closed: {total_closed}")
    print(f"⏭️  Positions skipped: {total_skipped}")
    
    if total_closed > 0:
        print("\nClosed positions:")
        for result in main_results + mirror_results:
            if result['closed']:
                print(f"  - {result['symbol']} ({result['account']}) - {result['reason']}")
    
    print("\n✅ Process complete!")


async def process_account(session, account_type: str):
    """Process positions for a specific account"""
    
    results = []
    
    try:
        # Get all positions
        position_result = session.get_positions(
            category="linear",
            settleCoin="USDT"
        )
        
        if position_result.get("retCode") == 0:
            positions = position_result.get("result", {}).get("list", [])
            
            print(f"\n📊 Found {len(positions)} positions on {account_type} account")
            
            for position in positions:
                symbol = position.get("symbol", "")
                side = position.get("side", "")
                size = float(position.get("size", "0"))
                avg_price = float(position.get("avgPrice", "0"))
                
                if size > 0:
                    # Get open orders for this symbol
                    orders_result = session.get_open_orders(
                        category="linear",
                        symbol=symbol
                    )
                    
                    if orders_result.get("retCode") == 0:
                        orders = orders_result.get("result", {}).get("list", [])
                        
                        # Categorize orders
                        tp_orders = []
                        sl_orders = []
                        other_orders = []
                        
                        for order in orders:
                            order_type = order.get("orderType", "")
                            reduce_only = order.get("reduceOnly", False)
                            order_side = order.get("side", "")
                            link_id = str(order.get("orderLinkId", ""))
                            
                            # Check if it's a TP order
                            is_tp = False
                            if reduce_only and order_type == "Limit":
                                if (side == "Buy" and order_side == "Sell") or (side == "Sell" and order_side == "Buy"):
                                    # Check price to confirm it's TP not entry
                                    price = float(order.get("price", "0"))
                                    if side == "Buy" and price > avg_price:
                                        is_tp = True
                                    elif side == "Sell" and price < avg_price:
                                        is_tp = True
                            
                            # Also check orderLinkId
                            if "TP" in link_id or "tp" in link_id:
                                is_tp = True
                            
                            # Check if it's SL order
                            is_sl = False
                            if "SL" in link_id or "sl" in link_id:
                                is_sl = True
                            elif order.get("triggerPrice") and reduce_only:
                                is_sl = True
                            
                            if is_tp:
                                tp_orders.append(order)
                            elif is_sl:
                                sl_orders.append(order)
                            else:
                                other_orders.append(order)
                        
                        # Log position details
                        pnl = float(position.get("unrealisedPnl", 0))
                        pnl_ratio = float(position.get("unrealisedPnlRatio", 0)) * 100
                        position_value = float(position.get("positionValue", 0))
                        
                        print(f"\n🔍 {symbol} {side}:")
                        print(f"   Size: {size} contracts (${position_value:.2f})")
                        print(f"   P&L: ${pnl:.2f} ({pnl_ratio:.2f}%)")
                        print(f"   Orders: {len(tp_orders)} TP, {len(sl_orders)} SL, {len(other_orders)} other")
                        
                        # Decision logic with safety checks
                        should_close = False
                        reason = ""
                        
                        if len(tp_orders) == 0 and len(sl_orders) > 0:
                            # No TPs but has SL - likely all TPs hit
                            # Additional safety: only close if position value is small
                            if position_value < 100:  # Less than $100
                                should_close = True
                                reason = f"No TPs, has SL, small size (${position_value:.2f})"
                            else:
                                print(f"   ⚠️  No TPs but position too large (${position_value:.2f}) - manual review needed")
                        
                        if should_close:
                            print(f"   ✅ Will close: {reason}")
                            success = await close_position_and_orders(session, {
                                'symbol': symbol,
                                'side': side,
                                'size': size,
                                'orders': orders
                            }, account_type)
                            
                            results.append({
                                'symbol': symbol,
                                'account': account_type,
                                'closed': success,
                                'reason': reason
                            })
                        else:
                            print(f"   ⏭️  Keeping position (has {len(tp_orders)} TPs)")
                            results.append({
                                'symbol': symbol,
                                'account': account_type,
                                'closed': False,
                                'reason': f"Has {len(tp_orders)} TPs"
                            })
                    
        else:
            print(f"❌ Failed to get positions: {position_result.get('retMsg', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error processing {account_type} account: {e}")
    
    return results


async def close_position_and_orders(session, position_data: dict, account_type: str):
    """Close a position and cancel all its orders"""
    
    symbol = position_data['symbol']
    side = position_data['side']
    size = position_data['size']
    
    try:
        # First, cancel all open orders
        try:
            cancel_result = session.cancel_all_orders(
                category="linear",
                symbol=symbol
            )
            if cancel_result.get("retCode") == 0:
                print(f"      ✅ Cancelled all orders")
            else:
                print(f"      ⚠️  Failed to cancel orders: {cancel_result.get('retMsg', 'Unknown error')}")
        except Exception as e:
            print(f"      ⚠️  Error cancelling orders: {e}")
        
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
                print(f"      ✅ Position closed successfully")
                return True
            else:
                print(f"      ❌ Failed to close: {order_result.get('retMsg', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"      ❌ Error closing position: {e}")
            return False
            
    except Exception as e:
        print(f"      ❌ Error processing {symbol}: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(check_and_close_positions_without_tps())