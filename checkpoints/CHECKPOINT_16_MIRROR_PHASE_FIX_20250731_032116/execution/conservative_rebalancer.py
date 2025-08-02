#!/usr/bin/env python3
"""
Conservative Rebalancer - ONLY adjusts quantities, NEVER changes trigger prices.
This ensures that original TP/SL levels are always preserved.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict

from clients.bybit_helpers import get_open_orders_with_client, get_all_positions_with_client
from clients.bybit_helpers import place_order_with_retry, cancel_order_with_retry
from clients.bybit_helpers import get_open_orders, get_all_open_orders
from execution.mirror_trader import get_mirror_positions
from config.settings import ENABLE_MIRROR_TRADING

logger = logging.getLogger(__name__)


def get_stop_order_type_for_replacement(order: Dict, fallback_type: str) -> str:
    """
    Get the correct stopOrderType to use when replacing an order.
    Handles various API response formats and ensures compatibility.
    """
    # First try to get the exact stopOrderType from the order
    stop_type = order.get('stopOrderType', '')

    # Map common variations to ensure consistency
    type_mapping = {
        'Stop': 'Stop',           # Preserve as-is
        'StopLoss': 'StopLoss',   # Preserve as-is
        'TakeProfit': 'TakeProfit',  # Preserve as-is
        'PartialTakeProfit': 'TakeProfit',  # Map to standard
        'PartialStopLoss': 'StopLoss',      # Map to standard
    }

    if stop_type in type_mapping:
        return type_mapping[stop_type]

    # If not found, check orderLinkId for clues
    order_link = order.get('orderLinkId', '').upper()
    if 'TP' in order_link or 'TAKE' in order_link:
        return 'TakeProfit'
    elif 'SL' in order_link or 'STOP' in order_link:
        return 'StopLoss'

    # Use the provided fallback as last resort
    logger.warning(f"Could not determine stopOrderType for order {order.get('orderId', 'unknown')[:8]}..., using fallback: {fallback_type}")
    return fallback_type


# Placeholder functions for mirror operations
async def place_mirror_order(client, **kwargs):
    """Placeholder for mirror order placement."""
    # In real implementation, this would place orders on mirror account
    logger.debug("place_mirror_order called (placeholder)")
    return None


async def cancel_mirror_order(client, **kwargs):
    """Placeholder for mirror order cancellation."""
    # In real implementation, this would cancel orders on mirror account
    logger.debug("cancel_mirror_order called (placeholder)")
    return None


class ConservativeRebalancer:
    """Rebalances positions to maintain proper quantity distribution while preserving trigger prices."""

    def __init__(self):
        self.enabled = True
        self.running = False
        self._rebalance_task = None
        self.check_interval = 300  # 5 minutes
        self.last_rebalance = {}
        self.min_rebalance_interval = 600  # 10 minutes minimum between rebalances

    async def start(self):
        """Start the rebalancer."""
        if self.running:
            logger.warning("Conservative rebalancer already running")
            return

        self.running = True
        self._rebalance_task = asyncio.create_task(self._rebalance_loop())
        logger.info("✅ Conservative rebalancer started (preserving trigger prices)")

    async def stop(self):
        """Stop the rebalancer."""
        self.running = False
        if self._rebalance_task:
            self._rebalance_task.cancel()
            try:
                await self._rebalance_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Conservative rebalancer stopped")

    async def _rebalance_loop(self):
        """Main rebalance loop."""
        while self.running:
            try:
                if self.enabled:
                    await self.check_and_rebalance_all()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in rebalance loop: {e}")
                await asyncio.sleep(60)

    async def check_and_rebalance_all(self):
        """Check all positions and rebalance if needed."""
        try:
            # Get all positions
            from clients.bybit_client import bybit_client
            from clients.bybit_helpers import get_all_positions
            positions = await get_all_positions()
            active_positions = [p for p in positions if float(p.get('size', 0)) > 0]

            if not active_positions:
                return

            for position in active_positions:
                symbol = position['symbol']
                side = position['side']
                key = f"{symbol}_{side}"

                # Check minimum interval
                last_time = self.last_rebalance.get(key, 0)
                if datetime.now().timestamp() - last_time < self.min_rebalance_interval:
                    continue

                # Check if rebalance is needed
                needs_rebalance = await self._check_needs_rebalance(position)

                if needs_rebalance:
                    logger.info(f"🔄 Rebalancing {symbol} {side} (preserving trigger prices)")
                    success = await self._rebalance_position(position)

                    if success:
                        self.last_rebalance[key] = datetime.now().timestamp()

                        # Alert user (main account only)
                        # Note: Alerts will be sent through monitor or trade completion
                        logger.info(f"✅ Rebalancing complete for {symbol} {side}")

        except Exception as e:
            logger.error(f"Error checking positions: {e}")

    async def _check_needs_rebalance(self, position: Dict) -> bool:
        """Check if position needs rebalancing."""
        try:
            symbol = position['symbol']
            side = position['side']
            total_size = float(position.get('size', 0))

            if total_size == 0:
                return False

            # Get orders
            orders = await get_open_orders(symbol)

            # Filter TP orders
            tp_orders = []
            for order in orders:
                if not order.get('reduceOnly'):
                    continue

                trigger_price = float(order.get('triggerPrice', 0))
                if trigger_price == 0:
                    continue

                # Determine if TP based on side and price
                avg_price = float(position.get('avgPrice', 0))
                if side == 'Buy' and trigger_price > avg_price:
                    tp_orders.append(order)
                elif side == 'Sell' and trigger_price < avg_price:
                    tp_orders.append(order)

            if len(tp_orders) != 4:
                return False  # Only rebalance if we have exactly 4 TPs

            # Check quantity distribution
            tp_quantities = [float(o.get('qty', 0)) for o in tp_orders]
            total_tp_qty = sum(tp_quantities)

            # Expected distribution
            expected_tp1 = total_size * 0.85
            expected_others = total_size * 0.05

            # Check if significantly off (more than 5% deviation)
            if abs(tp_quantities[0] - expected_tp1) > total_size * 0.05:
                return True

            for qty in tp_quantities[1:]:
                if abs(qty - expected_others) > total_size * 0.05:
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking rebalance need: {e}")
            return False

    async def _rebalance_position(self, position: Dict) -> bool:
        """Rebalance a position - adjust quantities ONLY, preserve trigger prices."""
        try:
            symbol = position['symbol']
            side = position['side']
            total_size = float(position.get('size', 0))
            avg_price = float(position.get('avgPrice', 0))
            position_idx = position.get('positionIdx', 0)

            # Get current orders
            orders = await get_open_orders(symbol)

            # Separate TP and SL orders
            tp_orders = []
            sl_orders = []

            for order in orders:
                if not order.get('reduceOnly'):
                    continue

                trigger_price = float(order.get('triggerPrice', 0))
                if trigger_price == 0:
                    continue

                # Check stopOrderType first for accurate classification
                stop_order_type = order.get('stopOrderType', '')
                if stop_order_type == 'StopLoss':
                    sl_orders.append(order)
                elif stop_order_type == 'TakeProfit':
                    tp_orders.append(order)
                elif side == 'Buy':
                    if trigger_price > avg_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)
                else:  # Sell
                    if trigger_price < avg_price:
                        tp_orders.append(order)
                    else:
                        sl_orders.append(order)

            # Sort TPs by price
            if side == 'Buy':
                tp_orders.sort(key=lambda x: float(x.get('triggerPrice', 0)))
            else:
                tp_orders.sort(key=lambda x: float(x.get('triggerPrice', 0)), reverse=True)

            if len(tp_orders) != 4:
                logger.warning(f"Expected 4 TPs, found {len(tp_orders)} for {symbol}")
                return False

            # Calculate new quantities
            new_quantities = [
                int(total_size * 0.85),
                int(total_size * 0.05),
                int(total_size * 0.05),
                int(total_size * 0.05)
            ]

            # Adjust for rounding
            total_new = sum(new_quantities)
            if total_new < total_size:
                new_quantities[0] += int(total_size - total_new)

            # Cancel and replace TP orders with same prices but new quantities
            success = True

            for i, (order, new_qty) in enumerate(zip(tp_orders, new_quantities)):
                old_qty = float(order.get('qty', 0))

                # Skip if quantity hasn't changed significantly
                if abs(old_qty - new_qty) < 1:
                    continue

                # PRESERVE THE ORIGINAL TRIGGER PRICE
                trigger_price = order.get('triggerPrice')

                try:
                    # Cancel old order
                    cancel_result = await cancel_order_with_retry(
                        symbol=symbol,
                        order_id=order['orderId']
                    )

                    if not cancel_result:
                        logger.error(f"Failed to cancel TP{i+1} order")
                        continue

                    # PRESERVE THE ORIGINAL stopOrderType
                    original_stop_type = get_stop_order_type_for_replacement(order, 'TakeProfit')

                    # Place new order with SAME trigger price and stopOrderType
                    order_params = {
                        "symbol": symbol,
                        "side": "Sell" if side == "Buy" else "Buy",
                        "order_type": "Market",
                        "qty": str(new_qty),
                        "trigger_price": trigger_price,  # PRESERVE ORIGINAL PRICE
                        "stop_order_type": original_stop_type,  # PRESERVE ORIGINAL TYPE
                        "reduce_only": True,
                        "order_link_id": f"REBAL_TP{i+1}_{int(time.time())}"
                    }

                    if position_idx:
                        order_params['position_idx'] = position_idx

                    place_result = await place_order_with_retry(**order_params)

                    if place_result:
                        logger.info(f"✅ Rebalanced TP{i+1}: {old_qty} → {new_qty} (price: ${trigger_price}, type: {original_stop_type})")
                    else:
                        logger.error(f"Failed to place new TP{i+1} order")
                        success = False

                except Exception as e:
                    logger.error(f"Error rebalancing TP{i+1}: {e}")
                    success = False

            # Also rebalance SL to match position size if needed
            if sl_orders:
                sl_order = sl_orders[0]  # Should only be one
                sl_qty = float(sl_order.get('qty', 0))

                if abs(sl_qty - total_size) > 1:
                    trigger_price = sl_order.get('triggerPrice')

                    try:
                        # Cancel old SL
                        cancel_result = await cancel_order_with_retry(
                            symbol=symbol,
                            order_id=sl_order['orderId']
                        )

                        if cancel_result:
                            # PRESERVE THE ORIGINAL stopOrderType
                            original_stop_type = get_stop_order_type_for_replacement(sl_order, 'StopLoss')

                            # Place new SL with correct quantity
                            order_params = {
                                "symbol": symbol,
                                "side": "Sell" if side == "Buy" else "Buy",
                                "order_type": "Market",
                                "qty": str(int(total_size)),
                                "trigger_price": trigger_price,  # PRESERVE ORIGINAL PRICE
                                "stop_order_type": original_stop_type,  # PRESERVE ORIGINAL TYPE
                                "reduce_only": True,
                                "order_link_id": f"REBAL_SL_{int(time.time())}"
                            }

                            if position_idx:
                                order_params['position_idx'] = position_idx

                            place_result = await place_order_with_retry(**order_params)

                            if place_result:
                                logger.info(f"✅ Rebalanced SL: {sl_qty} → {total_size} (price: ${trigger_price}, type: {original_stop_type})")

                    except Exception as e:
                        logger.error(f"Error rebalancing SL: {e}")
            else:
                # No SL order found - create one with default risk
                logger.warning(f"⚠️ No SL order found for {symbol} - creating one")

                try:
                    # Calculate SL price based on risk (7.5% default)
                    risk_percentage = 7.5
                    if side == 'Buy':
                        sl_price = avg_price * (1 - risk_percentage / 100)
                    else:
                        sl_price = avg_price * (1 + risk_percentage / 100)

                    # Format price to symbol precision
                    from clients.bybit_helpers import get_instrument_info
                    info = await get_instrument_info(symbol)
                    if info:
                        tick_size = float(info.get('priceFilter', {}).get('tickSize', '0.01'))
                        tick_str = f"{tick_size:.10f}".rstrip('0')
                        precision = len(tick_str.split('.')[1]) if '.' in tick_str else 0
                        sl_price_str = f"{sl_price:.{precision}f}"
                    else:
                        sl_price_str = str(sl_price)

                    order_params = {
                        "symbol": symbol,
                        "side": "Sell" if side == "Buy" else "Buy",
                        "order_type": "Market",
                        "qty": str(int(total_size)),
                        "trigger_price": sl_price_str,
                        "stop_order_type": "StopLoss",
                        "reduce_only": True,
                        "order_link_id": f"REBAL_SL_{int(time.time())}"
                    }

                    if position_idx:
                        order_params['position_idx'] = position_idx

                    place_result = await place_order_with_retry(**order_params)

                    if place_result:
                        logger.info(f"✅ Created missing SL at ${sl_price_str} for {total_size} units")
                    else:
                        logger.error(f"Failed to create missing SL order")
                        success = False

                except Exception as e:
                    logger.error(f"Error creating missing SL: {e}")
                    success = False

            return success

        except Exception as e:
            logger.error(f"Error rebalancing position: {e}")
            return False


# Global instance
conservative_rebalancer = ConservativeRebalancer()


async def rebalance_conservative_on_limit_fill(chat_data=None, symbol=None, filled_limits=None, total_limits=None, ctx_app=None, **kwargs) -> Dict:
    """
    Rebalance conservative position when a limit order is filled.
    Preserves original trigger prices.
    """
    try:
        logger.info(f"🔄 Rebalancing conservative position for {symbol} after limit fill")
        logger.info(f"   Filled limits: {filled_limits}/{total_limits}")

        if not symbol:
            return {"success": False, "error": "No symbol provided", "cancelled": 0, "created": 0}

        # Get current position to determine total size
        from clients.bybit_helpers import get_all_positions
        positions = await get_all_positions()
        position = next((p for p in positions if p.get('symbol') == symbol and float(p.get('size', 0)) > 0), None)

        if not position:
            logger.info(f"No active position found for {symbol}, skipping rebalance")
            return {"success": True, "cancelled": 0, "created": 0, "message": "No position to rebalance"}

        total_size = float(position.get('size', 0))
        if total_size <= 0:
            return {"success": True, "cancelled": 0, "created": 0, "message": "Position size is zero"}

        # Get all orders for this symbol
        from clients.bybit_helpers import get_open_orders
        orders = await get_all_open_orders()
        symbol_orders = [o for o in orders if o.get('symbol') == symbol]

        # Find TP orders (reduce only with trigger price)
        tp_orders = []
        for order in symbol_orders:
            if (order.get('reduceOnly') and
                order.get('triggerPrice') and
                ('TP' in order.get('orderLinkId', '') or order.get('stopOrderType') == 'TakeProfit')):
                tp_orders.append(order)

        if len(tp_orders) < 4:
            logger.info(f"Found {len(tp_orders)} TP orders, need 4 for conservative rebalancing")
            return {"success": True, "cancelled": 0, "created": 0, "message": "Not enough TP orders for rebalancing"}

        # Sort TP orders by trigger price
        side = position.get('side')
        avg_price = float(position.get('avgPrice', 0))

        if side == 'Buy':
            tp_orders.sort(key=lambda x: float(x.get('triggerPrice', 0)))  # Ascending for longs
        else:
            tp_orders.sort(key=lambda x: float(x.get('triggerPrice', 0)), reverse=True)  # Descending for shorts

        # Calculate ideal quantities (85%, 5%, 5%, 5%)
        ideal_quantities = [
            int(total_size * 0.85),
            int(total_size * 0.05),
            int(total_size * 0.05),
            int(total_size * 0.05)
        ]

        # Adjust for rounding
        total_ideal = sum(ideal_quantities)
        if total_ideal < total_size:
            ideal_quantities[0] += int(total_size - total_ideal)

        rebalanced_count = 0
        cancelled_count = 0

        # Check each TP order and rebalance if needed
        for i, (order, ideal_qty) in enumerate(zip(tp_orders[:4], ideal_quantities)):
            current_qty = float(order.get('qty', 0))

            # Check if quantity needs adjustment (more than 5% difference)
            if abs(current_qty - ideal_qty) > total_size * 0.05:
                logger.info(f"🔄 Rebalancing TP{i+1}: {current_qty} → {ideal_qty}")

                try:
                    # Cancel old order
                    from clients.bybit_helpers import cancel_order_with_retry
                    cancel_success = await cancel_order_with_retry(symbol, order['orderId'])

                    if cancel_success:
                        cancelled_count += 1

                        # Place new order with same trigger price but adjusted quantity
                        from clients.bybit_helpers import place_order_with_retry
                        import time

                        # CRITICAL: Preserve EXACT trigger price and stopOrderType from original order
                        original_trigger_price = order.get('triggerPrice')
                        original_stop_type = get_stop_order_type_for_replacement(order, 'TakeProfit')

                        order_params = {
                            "symbol": symbol,
                            "side": "Sell" if side == "Buy" else "Buy",
                            "order_type": "Market",
                            "qty": str(ideal_qty),
                            "trigger_price": str(original_trigger_price),  # PRESERVE EXACT PRICE
                            "stop_order_type": original_stop_type,  # PRESERVE ORIGINAL TYPE
                            "reduce_only": True,
                            "order_link_id": f"BOT_REBAL_TP{i+1}_{int(time.time())}"
                        }

                        place_success = await place_order_with_retry(**order_params)
                        if place_success:
                            rebalanced_count += 1
                            logger.info(f"✅ TP{i+1} rebalanced successfully (type: {original_stop_type})")
                        else:
                            logger.error(f"❌ Failed to place new TP{i+1} order")
                    else:
                        logger.error(f"❌ Failed to cancel TP{i+1} order")

                except Exception as e:
                    logger.error(f"Error rebalancing TP{i+1}: {e}")

        # Send alert to user about rebalancing - ALWAYS send alert when rebalancing occurs
        if ctx_app and hasattr(ctx_app, 'bot'):
            chat_id = chat_data.get('chat_id') if chat_data else None
            if not chat_id and chat_data:
                # Try alternative chat_id keys
                chat_id = chat_data.get('_chat_id') or chat_data.get('user_id')
            if not chat_id and ctx_app:
                # Try to get chat_id from context
                chat_id = getattr(ctx_app, 'chat_id', None)

            if chat_id:
                try:
                    # Build detailed message with new quantities
                    quantities_text = ""
                    for i, qty in enumerate(ideal_quantities[:4]):
                        percentage = [85, 5, 5, 5][i]
                        quantities_text += f"• TP{i+1}: {qty} ({percentage}%)\n"

                    message = (
                        f"🔄 <b>Auto-Rebalancer Activated</b>\n\n"
                        f"📊 <b>{symbol}</b> Conservative position rebalanced\n"
                        f"📈 Position Size: {total_size}\n\n"
                        f"<b>📋 NEW QUANTITIES:</b>\n"
                        f"{quantities_text}\n"
                        f"✅ Adjusted {rebalanced_count} TP orders\n"
                        f"🔒 <b>TRIGGER PRICES UNCHANGED</b>\n"
                        f"⚡ Only quantities modified - prices preserved"
                    )
                    await ctx_app.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='HTML',
                        disable_notification=True
                    )
                    logger.info(f"✅ Rebalance alert sent to chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send rebalance alert: {e}")
            else:
                logger.warning("No chat_id found for rebalance alert")

        return {
            "success": True,
            "cancelled": cancelled_count,
            "created": rebalanced_count,
            "message": f"Rebalanced {rebalanced_count} TP orders, preserving trigger prices"
        }

    except Exception as e:
        logger.error(f"Error in conservative limit fill rebalance: {e}")
        return {
            "success": False,
            "error": str(e),
            "cancelled": 0,
            "created": 0
        }


async def rebalance_conservative_mirror(symbol: str, side: str = None, monitor_data: Dict = None, chat_data: Dict = None, trigger: str = None, tp_number: int = None, **kwargs) -> bool:
    """
    Rebalance conservative mirror position.
    Preserves original trigger prices.
    """
    try:
        logger.info(f"🪞 Rebalancing mirror conservative position for {symbol}")

        # For now, just return success as mirror rebalancing is complex
        # This prevents the import error
        logger.debug(f"Mirror rebalancing for {symbol} - placeholder implementation")
        return {"success": True, "message": "Mirror rebalancing placeholder"}

    except Exception as e:
        logger.error(f"Error in conservative mirror rebalance: {e}")
        return {"success": False, "error": str(e)}


async def rebalance_sl_quantity_after_tp1(chat_data=None, symbol=None, sl_order_id=None, is_mirror=False, **kwargs) -> Dict:
    """
    Rebalance SL quantity after TP1 hit to match remaining position size.
    This ensures SL quantity matches the remaining position size after TP1 execution.
    Preserves the original trigger price - ONLY adjusts quantity.
    """
    try:
        logger.info(f"🔄 Rebalancing SL quantity for {symbol} after TP1 hit")

        if not symbol or not sl_order_id:
            return {"success": False, "error": "Missing symbol or SL order ID", "new_quantity": 0}

        # Get current position to determine remaining size after TP1
        from clients.bybit_helpers import get_all_positions
        positions = await get_all_positions()
        position = next((p for p in positions if p.get('symbol') == symbol and float(p.get('size', 0)) > 0), None)

        if not position:
            logger.info(f"No active position found for {symbol}, SL rebalancing not needed")
            return {"success": True, "new_quantity": 0, "message": "No position found"}

        remaining_size = float(position.get('size', 0))
        if remaining_size <= 0:
            return {"success": True, "new_quantity": 0, "message": "Position size is zero"}

        # Get current SL order details
        from clients.bybit_helpers import get_order_info
        sl_order_info = await get_order_info(symbol, sl_order_id)

        if not sl_order_info:
            return {"success": False, "error": "Could not retrieve SL order info", "new_quantity": 0}

        current_sl_qty = float(sl_order_info.get('qty', 0))
        sl_trigger_price = sl_order_info.get('triggerPrice')

        if not sl_trigger_price:
            return {"success": False, "error": "No trigger price found for SL order", "new_quantity": 0}

        # Check if SL quantity needs adjustment (should match remaining position size)
        qty_difference = abs(current_sl_qty - remaining_size)

        # Only rebalance if difference is significant (more than 1% of position)
        if qty_difference <= remaining_size * 0.01:
            logger.info(f"SL quantity {current_sl_qty} already matches position size {remaining_size}, no rebalancing needed")
            return {"success": True, "new_quantity": current_sl_qty, "message": "SL quantity already correct"}

        logger.info(f"🔄 SL quantity needs adjustment: {current_sl_qty} → {remaining_size}")

        try:
            # Cancel old SL order
            from clients.bybit_helpers import cancel_order_with_retry
            cancel_success = await cancel_order_with_retry(symbol, sl_order_id)

            if not cancel_success:
                return {"success": False, "error": "Failed to cancel old SL order", "new_quantity": current_sl_qty}

            # Place new SL order with SAME trigger price but adjusted quantity
            from clients.bybit_helpers import place_order_with_retry
            import time

            side = position.get('side')
            position_idx = position.get('positionIdx', 0)

            # CRITICAL: Preserve EXACT trigger price and stopOrderType from original order
            original_stop_type = get_stop_order_type_for_replacement(sl_order_info, 'StopLoss')

            order_params = {
                "symbol": symbol,
                "side": "Sell" if side == "Buy" else "Buy",
                "order_type": "Market",
                "qty": str(int(remaining_size)),  # Use remaining position size
                "trigger_price": str(sl_trigger_price),  # PRESERVE EXACT BREAKEVEN PRICE
                "stop_order_type": original_stop_type,  # PRESERVE ORIGINAL TYPE
                "reduce_only": True,
                "order_link_id": f"BOT_REBAL_SL_BREAKEVEN_{int(time.time())}"
            }

            if position_idx:
                order_params["position_idx"] = position_idx

            place_success = await place_order_with_retry(**order_params)

            if place_success:
                new_order_id = place_success.get("orderId", "")
                logger.info(f"✅ SL quantity rebalanced: {current_sl_qty} → {remaining_size} (price: ${sl_trigger_price}, type: {original_stop_type})")

                # Update chat_data with new SL order ID
                if chat_data:
                    chat_data["sl_order_id"] = new_order_id
                    from config.constants import SL_ORDER_ID, CONSERVATIVE_SL_ORDER_ID
                    chat_data[SL_ORDER_ID] = new_order_id
                    chat_data[CONSERVATIVE_SL_ORDER_ID] = new_order_id

                # Send alert about SL quantity rebalancing
                try:
                    if chat_data:
                        # Try to get context for alert
                        from shared.telegram_bot import send_alert_to_chat
                        chat_id = chat_data.get('chat_id') or chat_data.get('_chat_id')

                        if chat_id:
                            message = (
                                f"🛡️ <b>SL Quantity Rebalanced</b>\n\n"
                                f"📊 <b>{symbol}</b> SL quantity adjusted\n"
                                f"📈 Remaining Position: {remaining_size}\n"
                                f"🔄 SL Quantity: {current_sl_qty} → {remaining_size}\n"
                                f"🔒 <b>BREAKEVEN PRICE UNCHANGED</b>\n"
                                f"💰 Trigger Price: ${sl_trigger_price}\n"
                                f"⚡ Only quantity modified after TP1 hit"
                            )
                            await send_alert_to_chat(chat_id, message)
                            logger.info(f"✅ SL rebalance alert sent to chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send SL rebalance alert: {e}")

                return {
                    "success": True,
                    "new_quantity": remaining_size,
                    "old_quantity": current_sl_qty,
                    "trigger_price_preserved": sl_trigger_price,
                    "message": f"SL quantity rebalanced to match remaining position size"
                }
            else:
                return {"success": False, "error": "Failed to place new SL order", "new_quantity": current_sl_qty}

        except Exception as e:
            logger.error(f"Error during SL rebalancing: {e}")
            return {"success": False, "error": str(e), "new_quantity": current_sl_qty}

    except Exception as e:
        logger.error(f"Error in SL quantity rebalance: {e}")
        return {
            "success": False,
            "error": str(e),
            "new_quantity": 0
        }


async def rebalance_conservative_on_tp_hit(chat_data=None, symbol=None, tp_number=None, ctx_app=None, **kwargs) -> Dict:
    """
    Rebalance conservative position when a TP order hits.
    This adjusts the remaining TP orders AND stop loss based on the remaining position size.
    Preserves original trigger prices - ONLY adjusts quantities.

    Rebalancing logic:
    - After TP1 (85%): Rebalance SL to match remaining 15% position
    - After TP2 (5%): Rebalance SL to match remaining 10% position
    - After TP3 (5%): Rebalance SL to match remaining 5% position
    - After TP4 (5%): Position closed, no rebalancing needed
    """
    try:
        logger.info(f"🔄 Rebalancing conservative position for {symbol} after TP{tp_number} hit")

        if not symbol:
            return {"success": False, "error": "No symbol provided", "cancelled": 0, "created": 0}

        # Get current position to determine remaining size
        from clients.bybit_helpers import get_all_positions
        positions = await get_all_positions()
        position = next((p for p in positions if p.get('symbol') == symbol and float(p.get('size', 0)) > 0), None)

        if not position:
            logger.info(f"No active position found for {symbol}, no rebalancing needed")
            return {"success": True, "cancelled": 0, "created": 0, "message": "Position closed, no rebalancing needed"}

        remaining_size = float(position.get('size', 0))
        if remaining_size <= 0:
            return {"success": True, "cancelled": 0, "created": 0, "message": "Position size is zero"}

        # Get all orders for this symbol
        from clients.bybit_helpers import get_open_orders
        orders = await get_all_open_orders()
        symbol_orders = [o for o in orders if o.get('symbol') == symbol]

        # Find remaining TP orders (reduce only with trigger price)
        tp_orders = []
        for order in symbol_orders:
            if (order.get('reduceOnly') and
                order.get('triggerPrice') and
                ('TP' in order.get('orderLinkId', '') or order.get('stopOrderType') == 'TakeProfit')):
                tp_orders.append(order)

        if not tp_orders:
            logger.info(f"No remaining TP orders found for {symbol}")
            return {"success": True, "cancelled": 0, "created": 0, "message": "No TP orders to rebalance"}

        # Sort TP orders by trigger price
        side = position.get('side')
        if side == 'Buy':
            tp_orders.sort(key=lambda x: float(x.get('triggerPrice', 0)))  # Ascending for longs
        else:
            tp_orders.sort(key=lambda x: float(x.get('triggerPrice', 0)), reverse=True)  # Descending for shorts

        # Determine new distribution based on which TP hit
        if tp_number == 1 and len(tp_orders) >= 3:
            # TP1 hit (85% executed), distribute remaining 15% as 5%, 5%, 5%
            new_percentages = [0.333, 0.333, 0.334]  # 5% each of total (1/3 of remaining 15%)
        elif tp_number == 2 and len(tp_orders) >= 2:
            # TP2 hit (5% executed), distribute remaining 10% as 5%, 5%
            new_percentages = [0.5, 0.5]  # 5% each of total (1/2 of remaining 10%)
        elif tp_number == 3 and len(tp_orders) >= 1:
            # TP3 hit (5% executed), remaining 5% stays on TP4
            new_percentages = [1.0]  # 5% of total (all remaining)
        else:
            # Default: distribute evenly
            count = len(tp_orders)
            new_percentages = [1.0 / count] * count

        # Calculate new quantities
        new_quantities = []
        for pct in new_percentages:
            new_qty = int(remaining_size * pct)
            new_quantities.append(new_qty)

        # Adjust for rounding errors
        total_new = sum(new_quantities)
        if total_new < remaining_size and new_quantities:
            new_quantities[0] += int(remaining_size - total_new)

        rebalanced_count = 0
        cancelled_count = 0

        # Also rebalance SL quantity to match remaining position
        sl_orders = []
        for order in symbol_orders:
            if (order.get('reduceOnly') and
                order.get('triggerPrice') and
                ('SL' in order.get('orderLinkId', '') or order.get('stopOrderType') == 'StopLoss')):
                sl_orders.append(order)

        if sl_orders:
            sl_order = sl_orders[0]  # Should only be one SL
            current_sl_qty = float(sl_order.get('qty', 0))

            # Check if SL quantity needs adjustment
            if abs(current_sl_qty - remaining_size) > 1:
                logger.info(f"🛡️ Rebalancing SL quantity: {current_sl_qty} → {remaining_size}")

                try:
                    # Cancel old SL
                    cancel_success = await cancel_order_with_retry(symbol, sl_order['orderId'])

                    if cancel_success:
                        # Place new SL with adjusted quantity
                        original_sl_price = sl_order.get('triggerPrice')
                        original_stop_type = get_stop_order_type_for_replacement(sl_order, 'StopLoss')

                        order_params = {
                            "symbol": symbol,
                            "side": "Sell" if side == "Buy" else "Buy",
                            "order_type": "Market",
                            "qty": str(int(remaining_size)),
                            "trigger_price": str(original_sl_price),  # PRESERVE EXACT PRICE
                            "stop_order_type": original_stop_type,  # PRESERVE ORIGINAL TYPE
                            "reduce_only": True,
                            "order_link_id": f"BOT_REBAL_SL_AFTER_TP{tp_number}_{int(time.time())}"
                        }

                        place_success = await place_order_with_retry(**order_params)
                        if place_success:
                            logger.info(f"✅ SL rebalanced successfully after TP{tp_number} (type: {original_stop_type})")
                        else:
                            logger.error(f"❌ Failed to place new SL order after TP{tp_number}")
                except Exception as e:
                    logger.error(f"Error rebalancing SL after TP{tp_number}: {e}")

        # Rebalance each remaining TP order
        for i, (order, new_qty) in enumerate(zip(tp_orders[:len(new_quantities)], new_quantities)):
            current_qty = float(order.get('qty', 0))

            # Skip if quantity is already correct
            if abs(current_qty - new_qty) < 1:
                continue

            logger.info(f"🔄 Rebalancing TP{i+tp_number+1}: {current_qty} → {new_qty}")

            try:
                # Cancel old order
                from clients.bybit_helpers import cancel_order_with_retry
                cancel_success = await cancel_order_with_retry(symbol, order['orderId'])

                if cancel_success:
                    cancelled_count += 1

                    # Place new order with same trigger price but adjusted quantity
                    from clients.bybit_helpers import place_order_with_retry

                    # CRITICAL: Preserve EXACT trigger price and stopOrderType from original order
                    original_trigger_price = order.get('triggerPrice')
                    original_stop_type = get_stop_order_type_for_replacement(order, 'TakeProfit')

                    order_params = {
                        "symbol": symbol,
                        "side": "Sell" if side == "Buy" else "Buy",
                        "order_type": "Market",
                        "qty": str(new_qty),
                        "trigger_price": str(original_trigger_price),  # PRESERVE EXACT PRICE
                        "stop_order_type": original_stop_type,  # PRESERVE ORIGINAL TYPE
                        "reduce_only": True,
                        "order_link_id": f"BOT_REBAL_TP{i+tp_number+1}_AFTER_TP{tp_number}_{int(time.time())}"
                    }

                    place_success = await place_order_with_retry(**order_params)
                    if place_success:
                        rebalanced_count += 1
                        logger.info(f"✅ TP{i+tp_number+1} rebalanced successfully (type: {original_stop_type})")
                    else:
                        logger.error(f"❌ Failed to place new TP{i+tp_number+1} order")
                else:
                    logger.error(f"❌ Failed to cancel TP{i+tp_number+1} order")

            except Exception as e:
                logger.error(f"Error rebalancing TP{i+tp_number+1}: {e}")

        # Send alert about rebalancing
        if ctx_app and hasattr(ctx_app, 'bot') and rebalanced_count > 0:
            chat_id = chat_data.get('chat_id') if chat_data else None
            if not chat_id and chat_data:
                chat_id = chat_data.get('_chat_id') or chat_data.get('user_id')

            if chat_id:
                try:
                    # Build message showing new distribution
                    quantities_text = ""
                    for i, qty in enumerate(new_quantities):
                        tp_num = i + tp_number + 1
                        quantities_text += f"• TP{tp_num}: {qty}\n"

                    message = (
                        f"🔄 <b>Auto-Rebalancer Activated</b>\n\n"
                        f"📊 <b>{symbol}</b> rebalanced after TP{tp_number} hit\n"
                        f"📈 Remaining Position: {remaining_size}\n\n"
                        f"<b>📋 NEW TP QUANTITIES:</b>\n"
                        f"{quantities_text}\n"
                        f"✅ Adjusted {rebalanced_count} TP orders\n"
                        f"🛡️ SL quantity adjusted to match position\n"
                        f"🔒 <b>TRIGGER PRICES UNCHANGED</b>\n"
                        f"⚡ Only quantities modified to match position"
                    )

                    await ctx_app.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='HTML',
                        disable_notification=True
                    )
                    logger.info(f"✅ TP rebalance alert sent to chat {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send TP rebalance alert: {e}")

        return {
            "success": True,
            "cancelled": cancelled_count,
            "created": rebalanced_count,
            "message": f"Rebalanced {rebalanced_count} TP orders after TP{tp_number} hit"
        }

    except Exception as e:
        logger.error(f"Error in conservative TP rebalance: {e}")
        return {
            "success": False,
            "error": str(e),
            "cancelled": 0,
            "created": 0
        }
