#!/usr/bin/env python3
"""
Check mirror account rebalancing functionality
"""
import asyncio
import logging
from decimal import Decimal

from config import *
from execution.mirror_trader import bybit_client_2, get_mirror_position_info
from utils.helpers import safe_decimal_conversion

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

async def check_mirror_rebalancing():
    """Check mirror account positions and orders"""
    if not bybit_client_2:
        logger.error("❌ Mirror trading not enabled")
        return
    
    logger.info("=" * 80)
    logger.info("MIRROR ACCOUNT REBALANCING CHECK")
    logger.info("=" * 80)
    
    try:
        # Get all positions from mirror account
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: bybit_client_2.get_positions(
                category="linear",
                settleCoin="USDT"
            )
        )
        
        if not response or response.get("retCode") != 0:
            logger.error("Failed to get mirror positions")
            return
        
        positions = response.get("result", {}).get("list", [])
        
        # Get all orders from mirror account
        order_response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: bybit_client_2.get_open_orders(
                category="linear",
                settleCoin="USDT"
            )
        )
        
        if not order_response or order_response.get("retCode") != 0:
            logger.error("Failed to get mirror orders")
            return
        
        all_orders = order_response.get("result", {}).get("list", [])
        
        # Group orders by symbol
        orders_by_symbol = {}
        for order in all_orders:
            symbol = order.get("symbol")
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)
        
        # Check each position
        for position in positions:
            symbol = position.get("symbol")
            side = position.get("side")
            size = safe_decimal_conversion(position.get("size", "0"))
            
            if size == 0:
                continue
            
            logger.info(f"\n📊 {symbol} {side} - Size: {size}")
            
            # Get orders for this symbol
            symbol_orders = orders_by_symbol.get(symbol, [])
            
            # Separate TP and SL orders
            tp_orders = []
            sl_orders = []
            
            for order in symbol_orders:
                order_type = order.get("stopOrderType", "")
                order_side = order.get("side", "")
                order_link_id = order.get("orderLinkId", "")
                
                # Check if it's a bot order
                if not (order_link_id.startswith("BOT_") or "_MIRROR" in order_link_id):
                    continue
                
                # TP orders are opposite side
                if order_type == "TakeProfit" and order_side != side:
                    tp_orders.append(order)
                elif order_type == "StopLoss" and order_side != side:
                    sl_orders.append(order)
            
            # Sort TP orders by price
            if side == "Buy":
                tp_orders.sort(key=lambda x: float(x.get("triggerPrice", "0")))
            else:
                tp_orders.sort(key=lambda x: float(x.get("triggerPrice", "0")), reverse=True)
            
            # Display orders
            logger.info(f"   TP Orders: {len(tp_orders)}")
            total_tp_qty = Decimal("0")
            for i, tp in enumerate(tp_orders, 1):
                qty = safe_decimal_conversion(tp.get("qty", "0"))
                price = tp.get("triggerPrice")
                total_tp_qty += qty
                pct = (qty / size * 100) if size > 0 else 0
                logger.info(f"      TP{i}: {qty} ({pct:.1f}%) @ {price}")
            
            logger.info(f"   SL Orders: {len(sl_orders)}")
            total_sl_qty = Decimal("0")
            for sl in sl_orders:
                qty = safe_decimal_conversion(sl.get("qty", "0"))
                price = sl.get("triggerPrice")
                total_sl_qty += qty
                pct = (qty / size * 100) if size > 0 else 0
                logger.info(f"      SL: {qty} ({pct:.1f}%) @ {price}")
            
            # Check coverage
            tp_coverage = (total_tp_qty / size * 100) if size > 0 else 0
            sl_coverage = (total_sl_qty / size * 100) if size > 0 else 0
            
            logger.info(f"\n   Coverage:")
            logger.info(f"      TP: {tp_coverage:.1f}% {'✅' if 99 <= tp_coverage <= 101 else '❌'}")
            logger.info(f"      SL: {sl_coverage:.1f}% {'✅' if 99 <= sl_coverage <= 101 else '❌'}")
            
            # Check if it's conservative approach
            if len(tp_orders) == 4:
                logger.info(f"\n   Conservative Distribution Check:")
                expected = [85, 5, 5, 5]
                for i, (tp, exp) in enumerate(zip(tp_orders, expected), 1):
                    qty = safe_decimal_conversion(tp.get("qty", "0"))
                    actual = (qty / size * 100) if size > 0 else 0
                    logger.info(f"      TP{i}: {actual:.1f}% (expected {exp}%)")
            elif len(tp_orders) > 0:
                logger.info(f"\n   Equal Distribution Check (after TP hit):")
                expected_pct = 100 / len(tp_orders)
                for i, tp in enumerate(tp_orders, 1):
                    qty = safe_decimal_conversion(tp.get("qty", "0"))
                    actual = (qty / size * 100) if size > 0 else 0
                    logger.info(f"      TP{i}: {actual:.1f}% (expected {expected_pct:.1f}%)")
        
        # Check recent rebalancing activity
        logger.info("\n" + "=" * 80)
        logger.info("REBALANCING TRIGGERS")
        logger.info("=" * 80)
        logger.info("\n✅ Mirror rebalancing is triggered on:")
        logger.info("   • Limit order fills")
        logger.info("   • Position merges")
        logger.info("   • TP hits (any TP)")
        logger.info("\n📊 To check recent activity:")
        logger.info("   grep 'MIRROR Conservative rebalance' trading_bot.log | tail -20")
        
    except Exception as e:
        logger.error(f"Error checking mirror rebalancing: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(check_mirror_rebalancing())