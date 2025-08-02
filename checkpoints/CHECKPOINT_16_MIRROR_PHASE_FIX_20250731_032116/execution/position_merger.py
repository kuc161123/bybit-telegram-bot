#!/usr/bin/env python3
"""
Position merger for both conservative and fast approaches - handles merging of positions
with same symbol to bypass Bybit's stop order limits while maintaining optimal risk/reward parameters
"""
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from abc import ABC, abstractmethod
import asyncio

from clients.bybit_helpers import (
    get_position_info, get_all_open_orders,
    cancel_order_with_retry as cancel_order
)
from utils.cache import get_ticker_price_cached

logger = logging.getLogger(__name__)

class BasePositionMerger(ABC):
    """Base class for position mergers"""

    def __init__(self):
        self.logger = logger

    @abstractmethod
    def get_bot_order_patterns(self) -> List[str]:
        """Get order patterns that identify bot positions for this approach"""
        pass

    @abstractmethod
    def get_approach_name(self) -> str:
        """Get the approach name"""
        pass

    async def should_merge_positions(self, symbol: str, side: str, approach: str, bot_data: dict = None) -> Tuple[bool, Optional[Dict]]:
        """
        Check if we should merge with an existing BOT position (not external)
        Returns: (should_merge, existing_position_data)
        """
        # Only merge for matching approach
        if approach != self.get_approach_name():
            return False, None

        try:
            # Get existing positions for symbol
            position_info = await get_position_info(symbol)

            if not position_info or len(position_info) == 0:
                return False, None

            # Check if we have an open position with same side
            for position in position_info:
                if (float(position.get('size', 0)) > 0 and
                    position.get('side') == side):

                    # Get existing orders for this position
                    all_orders = await get_all_open_orders()
                    orders = [o for o in all_orders if o.get('symbol') == symbol]

                    # CRITICAL: Check if this position belongs to the bot
                    # Look for bot-created orders with recognizable patterns
                    is_bot_position = False
                    bot_order_patterns = self.get_bot_order_patterns()

                    for order in orders:
                        order_link_id = order.get('orderLinkId', '')
                        # Check if order has bot patterns
                        if any(pattern in order_link_id for pattern in bot_order_patterns):
                            is_bot_position = True
                            break

                    # Also check bot_data for position tracking
                    if bot_data:
                        # Check if symbol is tracked in any chat's monitoring
                        for key, value in bot_data.items():
                            if (key.startswith('MONITOR_') and
                                isinstance(value, dict) and
                                value.get('symbol') == symbol and
                                value.get('approach') == self.get_approach_name()):
                                is_bot_position = True
                                break

                    if not is_bot_position:
                        logger.info(f"🚫 Found {side} position for {symbol} but it's EXTERNAL - skipping merge")
                        return False, None

                    # Extract TP/SL orders
                    tp_orders = self._extract_tp_orders(orders)
                    sl_order = self._extract_sl_order(orders)

                    position_data = {
                        'position': position,
                        'tp_orders': tp_orders,
                        'sl_order': sl_order,
                        'orders': orders
                    }

                    logger.info(f"🔄 Found existing BOT {side} position for {symbol} ({self.get_approach_name()}) - merge candidate")
                    return True, position_data

            return False, None

        except Exception as e:
            logger.error(f"Error checking for position merge: {e}")
            return False, None

    @abstractmethod
    def _extract_tp_orders(self, orders: List[Dict]) -> List[Dict]:
        """Extract TP orders from order list"""
        pass

    @abstractmethod
    def _extract_sl_order(self, orders: List[Dict]) -> Optional[Dict]:
        """Extract SL order from order list"""
        pass

    async def cancel_existing_orders(self, orders: List[Dict], max_retries: int = 3) -> bool:
        """Cancel existing TP/SL orders for position with retry logic"""
        try:
            cancelled_count = 0
            failed_cancellations = []

            for order in orders:
                order_id = order.get('orderId')
                symbol = order.get('symbol')
                order_type = order.get('orderType', '')
                link_id = order.get('orderLinkId', '')

                # Only cancel TP/SL orders
                if order_type in ['Market', 'Limit'] and order.get('reduceOnly', False):
                    logger.info(f"🗑️ Attempting to cancel {order_type} order {order_id[:8]}... ({link_id})")

                    # Try to cancel with retries
                    cancelled = False
                    for attempt in range(max_retries):
                        try:
                            cancelled = await cancel_order(symbol, order_id)
                            if cancelled:
                                cancelled_count += 1
                                logger.info(f"✅ Successfully cancelled order {order_id[:8]}... on attempt {attempt + 1}")
                                break
                            else:
                                logger.warning(f"⚠️ Failed to cancel order {order_id[:8]}... on attempt {attempt + 1}")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(0.5)  # Wait before retry
                        except Exception as e:
                            logger.error(f"Error on attempt {attempt + 1} to cancel {order_id[:8]}...: {e}")
                            if attempt < max_retries - 1:
                                await asyncio.sleep(0.5)

                    if not cancelled:
                        failed_cancellations.append({
                            'orderId': order_id,
                            'symbol': symbol,
                            'linkId': link_id
                        })

            if failed_cancellations:
                logger.error(f"❌ Failed to cancel {len(failed_cancellations)} orders:")
                for failed in failed_cancellations:
                    logger.error(f"   - {failed['orderId'][:8]}... ({failed['linkId']})")
                return False

            logger.info(f"✅ Successfully cancelled all {cancelled_count} orders")
            return True

        except Exception as e:
            logger.error(f"Error in cancel_existing_orders: {e}")
            return False

    async def validate_merge(self, symbol: str, side: str, merged_params: Dict) -> bool:
        """Validate merged parameters are logical"""
        try:
            # Get current price
            current_price = await get_ticker_price_cached(symbol)
            if not current_price:
                logger.error(f"Could not get current price for {symbol}")
                return False

            current_price = Decimal(str(current_price))
            sl_price = Decimal(str(merged_params.get('sl_price', 0)))

            # Validate SL makes sense
            if side == 'Sell':  # SHORT
                if sl_price <= current_price:
                    logger.error(f"Invalid SHORT SL: {sl_price} should be above current {current_price}")
                    return False
            else:  # LONG
                if sl_price >= current_price:
                    logger.error(f"Invalid LONG SL: {sl_price} should be below current {current_price}")
                    return False

            # Validate TPs
            for i, tp in enumerate(merged_params.get('take_profits', [])):
                tp_price = Decimal(str(tp.get('price', 0)))

                if side == 'Sell':  # SHORT
                    if tp_price >= current_price:
                        logger.error(f"Invalid SHORT TP{i+1}: {tp_price} should be below current {current_price}")
                        return False
                else:  # LONG
                    if tp_price <= current_price:
                        logger.error(f"Invalid LONG TP{i+1}: {tp_price} should be above current {current_price}")
                        return False

            logger.info(f"✅ Merge parameters validated successfully")
            return True

        except Exception as e:
            logger.error(f"Error validating merge parameters: {e}")
            return False

    def count_existing_limit_orders(self, orders: List[Dict]) -> int:
        """Count existing limit orders (non reduce-only)"""
        limit_count = 0
        for order in orders:
            if (order.get('orderType') == 'Limit' and
                not order.get('reduceOnly', False) and
                not order.get('stopOrderType')):
                limit_count += 1
                logger.debug(f"Found limit order: {order.get('orderId', 'Unknown')[:8]}... @ {order.get('price', 'Unknown')}")

        logger.info(f"📊 Total existing limit orders: {limit_count}")
        return limit_count

    async def verify_orders_cancelled(self, orders_to_cancel: List[Dict], symbol: str) -> bool:
        """Verify that orders were actually cancelled with enhanced checks"""
        if not orders_to_cancel:
            return True

        # Get list of order IDs to check
        order_ids_to_check = [o.get('orderId') for o in orders_to_cancel if o.get('orderId')]

        if not order_ids_to_check:
            logger.warning("No order IDs to verify cancellation")
            return True

        logger.info(f"🔍 Verifying cancellation of {len(order_ids_to_check)} orders...")

        # Multiple verification attempts with increasing wait times
        max_attempts = 3
        wait_times = [0.5, 1.0, 2.0]

        for attempt in range(max_attempts):
            await asyncio.sleep(wait_times[attempt])

            try:
                all_open_orders = await get_all_open_orders()
                open_orders_for_symbol = [o for o in all_open_orders if o.get('symbol') == symbol]

                # Check if any of the cancelled orders still exist
                still_open = []
                still_open_details = []
                for order in open_orders_for_symbol:
                    if order.get('orderId') in order_ids_to_check:
                        still_open.append(order.get('orderId'))
                        still_open_details.append({
                            'id': order.get('orderId', '')[:8],
                            'type': order.get('orderType'),
                            'price': order.get('price', order.get('triggerPrice')),
                            'linkId': order.get('orderLinkId', '')
                        })

                if not still_open:
                    logger.info(f"✅ Attempt {attempt + 1}: All {len(order_ids_to_check)} orders verified as cancelled")
                    return True
                else:
                    logger.warning(f"⚠️ Attempt {attempt + 1}: {len(still_open)} orders still open")
                    if attempt < max_attempts - 1:
                        logger.info(f"   Waiting longer for exchange to process...")
                    else:
                        logger.error(f"❌ Final attempt failed: {len(still_open)} orders remain:")
                        for detail in still_open_details:
                            logger.error(f"   - {detail['id']}... Type: {detail['type']}, Price: {detail['price']}, LinkId: {detail['linkId']}")
                        return False

            except Exception as e:
                logger.error(f"Error during verification attempt {attempt + 1}: {e}")
                if attempt == max_attempts - 1:
                    return False

        return False  # Should not reach here

class ConservativePositionMerger(BasePositionMerger):
    """Handles merging of conservative positions with same symbol"""

    def get_bot_order_patterns(self) -> List[str]:
        """Conservative approach uses TP1_, TP2_, etc. patterns"""
        return ['TP1_', 'TP2_', 'TP3_', 'TP4_', 'SL_', '_LIMIT']

    async def validate_merge_readiness(self, symbol: str, existing_orders: List[Dict], new_limit_count: int) -> Tuple[bool, str]:
        """
        Validate that the position is ready for merge operation
        Returns: (is_ready, reason)
        """
        try:
            # Check current order counts
            limit_count = self.count_existing_limit_orders(existing_orders)
            tp_count = len(self._extract_tp_orders(existing_orders))
            sl_count = 1 if self._extract_sl_order(existing_orders) else 0

            logger.info(f"📋 MERGE READINESS CHECK for {symbol}:")
            logger.info(f"   Current limit orders: {limit_count}")
            logger.info(f"   Current TP orders: {tp_count}")
            logger.info(f"   Current SL orders: {sl_count}")
            logger.info(f"   New limit orders to place: {new_limit_count}")

            # Check for stop order limit
            total_stop_orders = tp_count + sl_count
            expected_new_stop_orders = 5  # 4 TPs + 1 SL for conservative

            if total_stop_orders + expected_new_stop_orders > 10:
                reason = f"Would exceed stop order limit: {total_stop_orders} existing + {expected_new_stop_orders} new > 10"
                logger.warning(f"   ❌ NOT READY: {reason}")
                return False, reason

            # Check for potential duplicates
            if limit_count > 0 and new_limit_count > 0:
                logger.warning(f"   ⚠️ WARNING: Existing limit orders present before placing new ones")
                logger.info(f"   Will need to cancel {limit_count} orders first")

            # Validate order IDs are not corrupted
            for order in existing_orders:
                order_id = order.get('orderId', '')
                symbol_check = order.get('symbol', '')

                # Check for swapped fields
                if 'USDT' in str(order_id) and 'USDT' not in str(symbol_check):
                    reason = f"Corrupted order data detected: orderId contains symbol"
                    logger.error(f"   ❌ NOT READY: {reason}")
                    return False, reason

            logger.info(f"   ✅ READY for merge operation")
            return True, "All checks passed"

        except Exception as e:
            logger.error(f"Error in merge readiness check: {e}")
            return False, f"Validation error: {str(e)}"

    def get_approach_name(self) -> str:
        """Return approach name"""
        return "conservative"

    def _extract_tp_orders(self, orders: List[Dict]) -> List[Dict]:
        """Extract TP orders for conservative approach"""
        tp_orders = []
        for order in orders:
            order_link_id = order.get('orderLinkId', '')
            if order_link_id.startswith('TP'):
                tp_orders.append(order)
        return sorted(tp_orders, key=lambda x: x.get('orderLinkId', ''))

    def _extract_sl_order(self, orders: List[Dict]) -> Optional[Dict]:
        """Extract SL order for conservative approach with enhanced detection"""
        sl_order = None

        # Multiple detection methods for robustness
        for order in orders:
            order_link_id = order.get('orderLinkId', '')
            stop_order_type = order.get('stopOrderType', '')
            order_type = order.get('orderType', '')
            reduce_only = order.get('reduceOnly', False)

            # Method 1: Check orderLinkId pattern
            if order_link_id.startswith('SL_') or 'SL_' in order_link_id:
                self.logger.info(f"🔍 Found SL by orderLinkId: {order_link_id}")
                sl_order = order
                break

            # Method 2: Check stopOrderType
            elif stop_order_type in ['StopLoss', 'Stop'] and reduce_only:
                self.logger.info(f"🔍 Found SL by stopOrderType: {stop_order_type}, linkId: {order_link_id}")
                sl_order = order
                break

            # Method 3: Check for stop market orders with reduce_only
            elif order_type == 'Market' and reduce_only and order.get('triggerPrice'):
                # Additional check - ensure it's not a TP order
                if not any(tp_pattern in order_link_id for tp_pattern in ['TP', 'TAKE_PROFIT', 'TakeProfit']):
                    self.logger.info(f"🔍 Found SL by Market+ReduceOnly+TriggerPrice: {order_link_id}")
                    sl_order = order
                    break

        if sl_order:
            self.logger.info(f"✅ SL order detected: {sl_order.get('orderId', 'Unknown')[:8]}... @ {sl_order.get('triggerPrice', 'Unknown')}")
        else:
            self.logger.warning("⚠️ No SL order found in existing position")

        return sl_order

    def calculate_merged_parameters(self,
                                  existing_data: Dict,
                                  new_params: Dict,
                                  side: str) -> Dict:
        """
        Calculate optimal merged parameters for TP/SL

        For SHORT:
        - SL: Choose HIGHER price (more conservative)
        - TPs: Choose LOWER prices (more aggressive)

        For LONG:
        - SL: Choose LOWER price (more conservative)
        - TPs: Choose HIGHER prices (more aggressive)
        """
        try:
            # Extract existing position data
            existing_position = existing_data['position']
            existing_tps = existing_data['tp_orders']
            existing_sl = existing_data['sl_order']

            # Calculate new position size
            existing_size = Decimal(str(existing_position.get('size', 0)))
            new_size = Decimal(str(new_params.get('position_size', 0)))
            merged_size = existing_size + new_size

            # Prepare merged parameters
            merged_params = {
                'merged_size': merged_size,
                'existing_size': existing_size,
                'new_size': new_size,
                'symbol': new_params['symbol'],
                'side': side,
                'leverage': new_params.get('leverage', existing_position.get('leverage')),
            }

            # Calculate merged stop loss with enhanced detection and verification
            sl_changed = False
            existing_sl_price = None

            if existing_sl:
                # Enhanced SL validation with multiple checks
                sl_trigger_price = existing_sl.get('triggerPrice')
                sl_order_id = existing_sl.get('orderId', 'Unknown')
                sl_order_type = existing_sl.get('orderType', '')
                sl_stop_type = existing_sl.get('stopOrderType', '')
                sl_link_id = existing_sl.get('orderLinkId', '')

                logger.info(f"🔍 EXISTING SL ANALYSIS:")
                logger.info(f"   Order ID: {sl_order_id[:8]}...")
                logger.info(f"   Trigger Price: {sl_trigger_price}")
                logger.info(f"   Order Type: {sl_order_type}")
                logger.info(f"   Stop Type: {sl_stop_type}")
                logger.info(f"   Link ID: {sl_link_id}")

                # Validate SL is genuine
                if sl_trigger_price and float(sl_trigger_price) > 0:
                    existing_sl_price = Decimal(str(sl_trigger_price))
                    new_sl_price = Decimal(str(new_params.get('sl_price', 0)))

                    logger.info(f"\n📊 SL MERGE DECISION ANALYSIS:")
                    logger.info(f"   Existing SL: ${existing_sl_price}")
                    logger.info(f"   New SL: ${new_sl_price}")
                    logger.info(f"   Side: {side}")

                    # Validate SL makes sense for the position side
                    current_price = existing_position.get('markPrice') or existing_position.get('avgPrice')
                    if current_price:
                        current_price = Decimal(str(current_price))
                        logger.info(f"   Current Price: ${current_price}")

                        # Sanity check existing SL
                        if side == 'Sell':  # SHORT
                            if existing_sl_price <= current_price:
                                logger.warning(f"   ⚠️ Existing SHORT SL ${existing_sl_price} is BELOW current price ${current_price}!")
                                logger.warning(f"   This SL would trigger immediately. Ignoring it.")
                                existing_sl_price = None
                        else:  # LONG
                            if existing_sl_price >= current_price:
                                logger.warning(f"   ⚠️ Existing LONG SL ${existing_sl_price} is ABOVE current price ${current_price}!")
                                logger.warning(f"   This SL would trigger immediately. Ignoring it.")
                                existing_sl_price = None

                    if existing_sl_price:  # If SL passed sanity check
                        if side == 'Sell':  # SHORT position
                            # Choose HIGHER stop loss (more conservative)
                            merged_params['sl_price'] = max(existing_sl_price, new_sl_price)
                            logger.info(f"   🎯 SHORT DECISION: ${existing_sl_price} vs ${new_sl_price}")
                            logger.info(f"   → Using HIGHER (conservative): ${merged_params['sl_price']} ✅")
                        else:  # LONG position
                            # Choose LOWER stop loss (more conservative)
                            merged_params['sl_price'] = min(existing_sl_price, new_sl_price)
                            logger.info(f"   🎯 LONG DECISION: ${existing_sl_price} vs ${new_sl_price}")
                            logger.info(f"   → Using LOWER (conservative): ${merged_params['sl_price']} ✅")

                        # Track if SL changed
                        sl_changed = merged_params['sl_price'] != existing_sl_price
                        if sl_changed:
                            logger.info(f"   🔄 RESULT: SL WILL CHANGE")
                            logger.info(f"      From: ${existing_sl_price}")
                            logger.info(f"      To: ${merged_params['sl_price']}")
                            logger.info(f"      Reason: Better risk management")
                        else:
                            logger.info(f"   ✔️ RESULT: SL UNCHANGED")
                            logger.info(f"      Keeping: ${existing_sl_price}")
                            logger.info(f"      Reason: Already optimal")
                    else:
                        # Existing SL failed sanity check
                        logger.warning(f"   ❌ Existing SL failed validation - using new SL")
                        merged_params['sl_price'] = new_params.get('sl_price')
                        sl_changed = True
                else:
                    # Invalid existing SL
                    logger.warning(f"⚠️ Existing SL has invalid/zero trigger price: {sl_trigger_price}")
                    merged_params['sl_price'] = new_params.get('sl_price')
                    sl_changed = True
            else:
                logger.info(f"\n🆕 SL DECISION: No existing SL detected")
                logger.info(f"   100% CONFIDENT: No SL order found after extensive search")
                logger.info(f"   Will set NEW SL: ${new_params.get('sl_price')}")
                merged_params['sl_price'] = new_params.get('sl_price')
                sl_changed = True  # No existing SL, so it's a change

            # Track TP changes
            tps_changed = False

            # Calculate merged take profits
            merged_params['take_profits'] = []
            new_tps = new_params.get('take_profits', [])

            # Match up to 4 TP levels
            for i in range(4):
                existing_tp = None
                new_tp = None

                # Get existing TP for this level
                if i < len(existing_tps):
                    tp_order = existing_tps[i]
                    if tp_order.get('orderLinkId', '').startswith(f'TP{i+1}'):
                        existing_tp = {
                            'price': Decimal(str(tp_order.get('triggerPrice', 0))),
                            'percentage': self._extract_tp_percentage(tp_order)
                        }

                # Get new TP for this level
                if i < len(new_tps):
                    new_tp = new_tps[i]

                # Merge TP levels
                if existing_tp and new_tp:
                    if side == 'Sell':  # SHORT position
                        # Choose LOWER TP (more aggressive)
                        merged_price = min(existing_tp['price'], Decimal(str(new_tp['price'])))
                        logger.info(f"🎯 SHORT TP{i+1}: Existing {existing_tp['price']} vs New {new_tp['price']} → Using {merged_price} (lower/aggressive)")
                    else:  # LONG position
                        # Choose HIGHER TP (more aggressive)
                        merged_price = max(existing_tp['price'], Decimal(str(new_tp['price'])))
                        logger.info(f"🎯 LONG TP{i+1}: Existing {existing_tp['price']} vs New {new_tp['price']} → Using {merged_price} (higher/aggressive)")

                    # Track if TP changed
                    if merged_price != existing_tp['price']:
                        tps_changed = True

                    # Use the percentage allocation from new params
                    merged_params['take_profits'].append({
                        'price': merged_price,
                        'percentage': new_tp['percentage']
                    })
                elif new_tp:
                    # Only new TP exists
                    merged_params['take_profits'].append(new_tp)
                    tps_changed = True  # New TP added
                elif existing_tp:
                    # Only existing TP exists
                    merged_params['take_profits'].append({
                        'price': existing_tp['price'],
                        'percentage': existing_tp['percentage']
                    })

            # Add other necessary parameters
            merged_params['tick_size'] = new_params.get('tick_size')
            merged_params['qty_step'] = new_params.get('qty_step')
            merged_params['approach'] = 'conservative'

            # Track if parameters changed
            merged_params['sl_changed'] = sl_changed
            merged_params['tps_changed'] = tps_changed
            merged_params['parameters_changed'] = sl_changed or tps_changed

            logger.info(f"✅ Calculated merged parameters for {merged_size} {side} {new_params['symbol']}")
            if merged_params['parameters_changed']:
                logger.info(f"📊 Parameters changed: SL={merged_params['sl_changed']}, TPs={merged_params['tps_changed']}")
            else:
                logger.info(f"📊 No parameter changes - keeping original SL and TPs")
            return merged_params

        except Exception as e:
            logger.error(f"Error calculating merged parameters: {e}")
            raise

    def _extract_tp_percentage(self, tp_order: Dict) -> int:
        """Extract TP percentage from order link ID or default"""
        try:
            # Try to extract from orderLinkId like "TP1_70"
            link_id = tp_order.get('orderLinkId', '')
            if '_' in link_id:
                percentage = int(link_id.split('_')[1])
                return percentage
        except:
            pass

        # Default percentages for TP1-4
        tp_num = self._get_tp_number(tp_order)
        default_percentages = {1: 70, 2: 10, 3: 10, 4: 10}
        return default_percentages.get(tp_num, 10)

    def _get_tp_number(self, tp_order: Dict) -> int:
        """Get TP number from order"""
        link_id = tp_order.get('orderLinkId', '')
        if link_id.startswith('TP'):
            try:
                return int(link_id[2])
            except:
                pass
        return 1

    async def cancel_existing_orders(self, orders: List[Dict], order_type_filter: str = "all") -> Tuple[bool, int]:
        """
        Cancel existing orders with enhanced validation and filtering

        Args:
            orders: List of orders to cancel
            order_type_filter: "all", "tp_sl_only", or "limit_only"

        Returns:
            Tuple of (success, cancelled_count)
        """
        try:
            cancelled_count = 0
            failed_cancellations = []
            orders_to_cancel = []

            # First, filter and validate orders
            for order in orders:
                order_id = order.get('orderId')
                symbol = order.get('symbol')
                order_type = order.get('orderType', '')
                link_id = order.get('orderLinkId', '')
                reduce_only = order.get('reduceOnly', False)
                stop_order_type = order.get('stopOrderType')

                # Debug logging
                logger.debug(f"Evaluating order: id={order_id}, symbol={symbol}, type={order_type}, linkId={link_id}, reduceOnly={reduce_only}")

                # Validate order data
                if not order_id or not symbol:
                    logger.warning(f"Skipping order with missing data: orderId={order_id}, symbol={symbol}")
                    continue

                # Check if orderId looks like a symbol (contains "USDT")
                if "USDT" in str(order_id) and "USDT" not in str(symbol):
                    logger.warning(f"Detected swapped order fields! Swapping back: orderId={order_id}, symbol={symbol}")
                    order_id, symbol = symbol, order_id
                    order['orderId'] = order_id
                    order['symbol'] = symbol

                # Apply filter
                should_cancel = False

                if order_type_filter == "tp_sl_only":
                    # Only cancel TP/SL orders
                    if (link_id.startswith(('TP', 'SL')) or
                        stop_order_type in ['TakeProfit', 'StopLoss', 'Stop'] or
                        (reduce_only and order.get('triggerPrice'))):
                        should_cancel = True

                elif order_type_filter == "limit_only":
                    # Only cancel limit orders (non reduce-only)
                    if order_type == 'Limit' and not reduce_only and not stop_order_type:
                        should_cancel = True

                else:  # "all"
                    should_cancel = True

                if should_cancel:
                    orders_to_cancel.append(order)

            logger.info(f"📋 Found {len(orders_to_cancel)} orders to cancel (filter: {order_type_filter})")

            # Now cancel the filtered orders
            for order in orders_to_cancel:
                order_id = order['orderId']
                symbol = order['symbol']
                link_id = order.get('orderLinkId', '')

                logger.info(f"🗑️ Cancelling order {order_id[:8]}... ({link_id})")

                # Try with retries
                success = False
                for attempt in range(3):
                    try:
                        success = await cancel_order(symbol, order_id)
                        if success:
                            cancelled_count += 1
                            logger.info(f"✅ Cancelled {order_id[:8]}... on attempt {attempt + 1}")
                            break
                        else:
                            logger.warning(f"Attempt {attempt + 1} failed for {order_id[:8]}...")
                            if attempt < 2:
                                await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Error cancelling {order_id[:8]}... on attempt {attempt + 1}: {e}")
                        if attempt < 2:
                            await asyncio.sleep(0.5)

                if not success:
                    failed_cancellations.append(order_id)

            # Verify cancellations if requested
            if cancelled_count > 0:
                logger.info(f"⏳ Verifying {cancelled_count} cancellations...")
                verified = await self.verify_orders_cancelled(orders_to_cancel, symbol)
                if not verified:
                    logger.error("❌ Some orders may still be open after cancellation!")
                    return False, cancelled_count

            if failed_cancellations:
                logger.error(f"❌ Failed to cancel {len(failed_cancellations)} orders: {failed_cancellations}")
                return False, cancelled_count

            logger.info(f"✅ Successfully cancelled {cancelled_count}/{len(orders_to_cancel)} orders")
            return True, cancelled_count

        except Exception as e:
            logger.error(f"Error in cancel_existing_orders: {e}")
            return False, 0

    async def validate_merge(self, symbol: str, side: str, merged_params: Dict) -> bool:
        """Validate that merge parameters are safe and logical"""
        try:
            # Get current price
            current_price = await get_ticker_price_cached(symbol)
            if not current_price:
                logger.error("Cannot validate merge - no current price")
                return False

            current_price = Decimal(str(current_price))
            sl_price = merged_params.get('sl_price')

            # Validate stop loss
            if sl_price:
                sl_price = Decimal(str(sl_price))
                if side == 'Sell':
                    # For SHORT, SL should be above current price
                    if sl_price <= current_price:
                        logger.error(f"Invalid SHORT SL: {sl_price} <= current {current_price}")
                        return False
                else:
                    # For LONG, SL should be below current price
                    if sl_price >= current_price:
                        logger.error(f"Invalid LONG SL: {sl_price} >= current {current_price}")
                        return False

            # Validate take profits
            for i, tp in enumerate(merged_params.get('take_profits', [])):
                tp_price = Decimal(str(tp['price']))
                if side == 'Sell':
                    # For SHORT, TPs should be below current price
                    if tp_price >= current_price:
                        logger.error(f"Invalid SHORT TP{i+1}: {tp_price} >= current {current_price}")
                        return False
                else:
                    # For LONG, TPs should be above current price
                    if tp_price <= current_price:
                        logger.error(f"Invalid LONG TP{i+1}: {tp_price} <= current {current_price}")
                        return False

            logger.info("✅ Merge parameters validated successfully")
            return True

        except Exception as e:
            logger.error(f"Error validating merge: {e}")
            return False


#             raise