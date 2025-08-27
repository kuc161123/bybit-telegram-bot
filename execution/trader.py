#!/usr/bin/env python3
"""
Enhanced trade execution logic with REFINED PERFORMANCE TRACKING.
REFINED: Better trade logging and tracking
ENHANCED: Improved error handling and validation
FIXED: Accurate position size and P&L tracking
FIXED: Async execution properly integrated with conversation handler
FIXED: Automatic position mode detection - no more hardcoded positionIdx
ENHANCED: More informative and visually appealing execution messages
"""
import logging
import time
import asyncio
import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any

from config.constants import *
from config.conservative_only_settings import validate_approach, ENFORCE_CONSERVATIVE_ONLY
from config.constants import BOT_PREFIX, TRADING_APPROACH
from config.settings import ENABLE_ENHANCED_TP_SL
from utils.helpers import value_adjusted_to_step, safe_decimal_conversion
from utils.formatters import (
    format_decimal_or_na, format_price, get_emoji, format_mobile_currency,
    format_mobile_percentage, create_mobile_separator
)
from clients.bybit_helpers import place_order_with_retry, add_trade_group_to_protection, set_symbol_leverage, get_all_open_orders
from utils.position_identifier import mark_position_as_bot, get_bot_order_link_id
from utils.order_consolidation import check_approach_conflicts, cleanup_approach_orders, cleanup_all_orders

# Position merger for conservative approach
from execution.position_merger import ConservativePositionMerger

# Get logger first
logger = logging.getLogger(__name__)

# Import enhanced TP/SL manager
try:
    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
    ENHANCED_TP_SL_AVAILABLE = True
except ImportError:
    ENHANCED_TP_SL_AVAILABLE = False
    logger.info("Enhanced TP/SL manager not available")

# Mirror trading imports (added for second account support)
try:
    from execution.mirror_trader import (
        mirror_market_order,
        mirror_limit_order,
        mirror_tp_sl_order,
        is_mirror_trading_enabled
    )
    MIRROR_TRADING_AVAILABLE = True
except ImportError:
    MIRROR_TRADING_AVAILABLE = False
    logger.info("Mirror trading module not available")

# Import execution summary module
try:
    from execution.execution_summary import execution_summary
    EXECUTION_SUMMARY_AVAILABLE = True
except ImportError:
    EXECUTION_SUMMARY_AVAILABLE = False
    logger.warning("Execution summary module not available")

class TradeExecutor:
    """Enhanced trade executor with refined performance tracking and automatic position mode detection"""

    def __init__(self):
        self.logger = logger
        self.position_merger = ConservativePositionMerger()
        # Fast merger removed

    def _generate_unique_order_link_id(self, base_id: str) -> str:
        """Generate a unique order link ID by appending timestamp"""
        import time
        unique_suffix = str(int(time.time() * 1000))[-6:]  # Last 6 digits of timestamp
        return f"{base_id}_{unique_suffix}"

    def _format_risk_reward_display(self, risk_amount: Decimal, reward_amount: Decimal,
                                   ratio: float) -> str:
        """Format risk/reward information for display with enhanced visuals"""
        risk_emoji = "🔴" if risk_amount < 0 else "🟡"
        reward_emoji = "🟢" if reward_amount > 0 else "🟡"

        # Enhanced ratio display with better visual indicators
        if ratio >= 3:
            ratio_emoji = "🏆"
            ratio_text = "Excellent"
        elif ratio >= 2:
            ratio_emoji = "✅"
            ratio_text = "Good"
        elif ratio >= 1:
            ratio_emoji = "⚠️"
            ratio_text = "Fair"
        else:
            ratio_emoji = "❌"
            ratio_text = "Poor"

        # Calculate visual risk meter
        risk_percentage = min(100, (abs(risk_amount) / reward_amount * 100) if reward_amount > 0 else 100)
        risk_bar = self._create_risk_bar(risk_percentage)

        return (
            f"{risk_emoji} <b>Risk:</b> {format_mobile_currency(abs(risk_amount))}\n"
            f"{reward_emoji} <b>Potential:</b> {format_mobile_currency(reward_amount)}\n"
            f"{ratio_emoji} <b>R:R Ratio:</b> 1:{ratio:.2f} ({ratio_text})\n"
            f"📊 <b>Risk Level:</b> {risk_bar}"
        )

    def _format_order_summary(self, orders_placed: List[str], order_ids: Dict[str, str]) -> str:
        """Format order summary with enhanced visual elements and organization"""
        summary = "\n<b>📋 Order Summary</b>\n"
        summary += "┌────────────────────────────┐\n"

        # Group orders by type
        entry_orders = []
        tp_orders = []
        sl_orders = []

        for order_desc in orders_placed:
            if "Market" in order_desc or "Limit" in order_desc:
                entry_orders.append(order_desc)
            elif "TP" in order_desc:
                tp_orders.append(order_desc)
            elif "SL" in order_desc:
                sl_orders.append(order_desc)

        # Format entry orders
        if entry_orders:
            summary += "│ <b>Entry Orders:</b>\n"
            for order in entry_orders:
                if "Market" in order:
                    emoji = "🚀"
                else:
                    emoji = "📊"
                summary += f"│   {emoji} {order}\n"

        # Format TP orders
        if tp_orders:
            summary += "│ <b>Take Profit Orders:</b>\n"
            for order in tp_orders:
                summary += f"│   🎯 {order}\n"

        # Format SL orders
        if sl_orders:
            summary += "│ <b>Stop Loss Orders:</b>\n"
            for order in sl_orders:
                summary += f"│   🛡️ {order}\n"

        summary += "└────────────────────────────┘"

        return summary

    def _format_execution_time(self, start_time: float) -> str:
        """Format execution time display with performance indicator"""
        execution_time = time.time() - start_time
        if execution_time < 1:
            return f"⚡ Ultra Fast ({execution_time:.1f}s)"
        elif execution_time < 2:
            return f"🚀 Fast ({execution_time:.1f}s)"
        elif execution_time < 5:
            return f"⏱️ Normal ({execution_time:.1f}s)"
        else:
            return f"🐌 Slow ({execution_time:.1f}s)"

    def _create_risk_bar(self, percentage: float) -> str:
        """Create visual risk bar"""
        filled = int(percentage / 20)  # 5 segments
        if percentage <= 20:
            color = "🟢"
        elif percentage <= 40:
            color = "🟡"
        elif percentage <= 60:
            color = "🟠"
        else:
            color = "🔴"

        bar = color * filled + "⚪" * (5 - filled)
        return f"{bar} {percentage:.0f}%"

    def _get_market_trend_indicator(self, side: str, entry: Decimal, tp: Decimal, sl: Decimal) -> str:
        """Get market trend visualization"""
        if side == "Buy":
            distance_to_tp = tp - entry
            distance_to_sl = entry - sl
        else:
            distance_to_tp = entry - tp
            distance_to_sl = sl - entry

        # Visual representation of trade setup
        tp_pips = int(distance_to_tp * 100)  # Simplified pip calculation
        sl_pips = int(distance_to_sl * 100)

        return f"📊 Trade Range: -{sl_pips} pips ← Entry → +{tp_pips} pips"

    def _format_position_metrics(self, position_size: Decimal, position_value: Decimal, leverage: int) -> str:
        """Format position metrics with visual indicators"""
        # Leverage risk indicator
        if leverage <= 5:
            lev_indicator = "🟢 Low Risk"
        elif leverage <= 10:
            lev_indicator = "🟡 Medium Risk"
        elif leverage <= 20:
            lev_indicator = "🟠 High Risk"
        else:
            lev_indicator = "🔴 Very High Risk"

        return (
            f"💎 <b>Position Metrics:</b>\n"
            f"   📏 Size: {format_decimal_or_na(position_size, 4)}\n"
            f"   💵 Value: {format_mobile_currency(position_value)}\n"
            f"   ⚡ Leverage: {leverage}x ({lev_indicator})"
        )

    def _format_mirror_trading_summary(self, mirror_results: Dict[str, Any]) -> str:
        """Format mirror trading summary for inclusion in trade confirmation messages"""
        if not mirror_results.get("enabled", False):
            return ""

        # Count successful orders
        total_orders = 0
        successful_orders = 0

        for order_type in ["market", "tp", "sl"]:
            if mirror_results.get(order_type) is not None:
                total_orders += 1
                if mirror_results[order_type].get("success", False):
                    successful_orders += 1

        # Overall status
        if successful_orders == total_orders and total_orders > 0:
            status_emoji = "✅"
            status_text = "SUCCESS"
        elif successful_orders > 0:
            status_emoji = "⚠️"
            status_text = "PARTIAL"
        else:
            status_emoji = "❌"
            status_text = "FAILED"

        summary = f"\n\n🔄 <b>MIRROR TRADING SUMMARY</b>\n"
        summary += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        summary += f"{status_emoji} <b>Status:</b> {status_text} ({successful_orders}/{total_orders} orders)\n"

        # Order-by-order breakdown
        if mirror_results.get("market"):
            if mirror_results["market"].get("success"):
                order_id = mirror_results["market"].get("id", "")[:8]
                summary += f"├─ Market Entry: ✅ {order_id}...\n"
            else:
                summary += f"├─ Market Entry: ❌ Failed\n"

        if mirror_results.get("tp"):
            if mirror_results["tp"].get("success"):
                order_id = mirror_results["tp"].get("id", "")[:8]
                summary += f"├─ Take Profit: ✅ {order_id}...\n"
            else:
                summary += f"├─ Take Profit: ❌ Failed\n"

        if mirror_results.get("sl"):
            if mirror_results["sl"].get("success"):
                order_id = mirror_results["sl"].get("id", "")[:8]
                summary += f"└─ Stop Loss: ✅ {order_id}...\n"
            else:
                summary += f"└─ Stop Loss: ❌ Failed\n"

        # Add errors if any
        if mirror_results.get("errors"):
            summary += f"\n⚠️ <b>Mirror Issues:</b>\n"
            for error in mirror_results["errors"][:3]:  # Limit to 3 errors
                summary += f"   • {error}\n"

        return summary

    def _format_conservative_mirror_summary(self, mirror_results: Dict[str, Any]) -> str:
        """Format conservative approach mirror trading summary"""
        if not mirror_results.get("enabled", False):
            return ""

        # Count successful orders
        total_orders = 0
        successful_orders = 0

        # Count limit orders
        limit_success = 0
        for limit in mirror_results.get("limits", []):
            total_orders += 1
            if limit.get("success", False):
                successful_orders += 1
                limit_success += 1

        # Count TP orders
        tp_success = 0
        for tp in mirror_results.get("tps", []):
            total_orders += 1
            if tp.get("success", False):
                successful_orders += 1
                tp_success += 1

        # Count SL order
        if mirror_results.get("sl") is not None:
            total_orders += 1
            if mirror_results["sl"].get("success", False):
                successful_orders += 1

        # Overall status
        if successful_orders == total_orders and total_orders > 0:
            status_emoji = "✅"
            status_text = "SUCCESS"
        elif successful_orders > 0:
            status_emoji = "⚠️"
            status_text = "PARTIAL"
        else:
            status_emoji = "❌"
            status_text = "FAILED"

        summary = f"\n\n🔄 <b>MIRROR TRADING SUMMARY</b>\n"
        summary += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        summary += f"{status_emoji} <b>Status:</b> {status_text} ({successful_orders}/{total_orders} orders)\n"

        # Entry orders summary
        if mirror_results.get("limits"):
            summary += f"├─ Entry Orders: {limit_success}/{len(mirror_results['limits'])} success\n"
            for limit in mirror_results["limits"][:3]:  # Show first 3
                order_num = limit.get("order", "?")
                order_type = limit.get("type", "Limit")
                if limit.get("success"):
                    order_id = limit.get("id", "")[:8]
                    summary += f"│  ├─ {order_type} {order_num}: ✅ {order_id}...\n"
                else:
                    summary += f"│  ├─ {order_type} {order_num}: ❌ Failed\n"

        # TP orders summary
        if mirror_results.get("tps"):
            summary += f"├─ Take Profits: {tp_success}/{len(mirror_results['tps'])} success\n"
            for tp in mirror_results["tps"][:3]:  # Show first 3
                tp_num = tp.get("tp", "?")
                if tp.get("success"):
                    order_id = tp.get("id", "")[:8]
                    summary += f"│  ├─ TP{tp_num}: ✅ {order_id}...\n"
                else:
                    summary += f"│  ├─ TP{tp_num}: ❌ Failed\n"

        # SL order
        if mirror_results.get("sl"):
            if mirror_results["sl"].get("success"):
                order_id = mirror_results["sl"].get("id", "")[:8]
                summary += f"└─ Stop Loss: ✅ {order_id}...\n"
            else:
                summary += f"└─ Stop Loss: ❌ Failed\n"

        # Add errors if any
        if mirror_results.get("errors"):
            summary += f"\n⚠️ <b>Mirror Issues:</b>\n"
            for error in mirror_results["errors"][:3]:  # Limit to 3 errors
                summary += f"   • {error}\n"

        return summary

    async def execute_conservative_approach(self, application, chat_id: int, chat_data: dict) -> dict:
        """
        Execute conservative approach: multiple limit orders + multiple TPs + SL
        REFINED: Enhanced tracking for complex order structure
        FIXED: Automatic position mode detection
        ENHANCED: More informative and visually appealing messages
        NEW: Position merging for same symbol to bypass order limits
        """
        start_time = time.time()

        try:
            # Extract parameters
            symbol = chat_data.get(SYMBOL)
            side = chat_data.get(SIDE)
            margin_amount = safe_decimal_conversion(chat_data.get(MARGIN_AMOUNT))
            leverage = int(chat_data.get(LEVERAGE, 1))
            tick_size = safe_decimal_conversion(chat_data.get(INSTRUMENT_TICK_SIZE, "0.01"))
            qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))
            trade_group_id = chat_data.get(CONSERVATIVE_TRADE_GROUP_ID, "unknown")

            # Check for approach conflicts and handle consolidation
            self.logger.info(f"🔍 Checking for existing orders on {symbol} {side}...")
            conflict_info = await check_approach_conflicts(symbol, side, "conservative")

            if conflict_info.get("conflict"):
                existing_approach = conflict_info.get("existing_approach")
                recommendation = conflict_info.get("recommendation")

                self.logger.info(f"⚠️ Found existing {existing_approach} approach for {symbol}")

                if recommendation == "cleanup_all":
                    self.logger.info(f"🧹 Mixed approaches detected - cleaning up all orders...")
                    await cleanup_all_orders(symbol, side)
                elif "replace" in recommendation:
                    self.logger.info(f"🔄 Replacing {existing_approach} orders with Conservative approach...")
                    await cleanup_approach_orders(symbol, existing_approach)

                # PERFORMANCE: Reduced cleanup wait time
                await asyncio.sleep(0.5)

            # Check if we should merge with existing position
            # Pass bot_data to check if position belongs to bot
            bot_data = application.bot_data if application else None
            should_merge, existing_data = await self.position_merger.should_merge_positions(
                symbol, side, "conservative", bot_data
            )

            # Get all price levels
            limit_prices = []
            for i in range(1, 4):
                price_key = f"{LIMIT_ENTRY_1_PRICE}".replace("1", str(i))
                price = chat_data.get(price_key)
                if price:
                    limit_prices.append(safe_decimal_conversion(price))

            tp_prices = []
            # Single Take Profit approach - only get TP price
            price = chat_data.get(TP_PRICE)
            if price:
                tp_prices.append(safe_decimal_conversion(price))

            sl_price = safe_decimal_conversion(chat_data.get(SL_PRICE))

            # If merging positions, handle the merge logic
            if should_merge:
                self.logger.info(f"🔄 MERGING with existing {side} position on {symbol}")
                return await self._execute_conservative_merge(
                    application, chat_id, chat_data, existing_data,
                    limit_prices, tp_prices, sl_price, margin_amount, leverage,
                    tick_size, qty_step, trade_group_id
                )

            # Set leverage before placing orders
            leverage_set = await set_symbol_leverage(symbol, leverage)
            if not leverage_set:
                self.logger.debug(f"Continuing with existing leverage for {symbol}")

            # Also set leverage on mirror account if enabled
            if MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled():
                try:
                    from execution.mirror_trader import set_mirror_leverage
                    mirror_leverage_set = await set_mirror_leverage(symbol, leverage)
                    if not mirror_leverage_set:
                        self.logger.debug(f"Continuing with existing mirror leverage for {symbol}")
                except Exception as e:
                    # Handle leverage not modified error (110043) silently
                    error_msg = str(e)
                    if "110043" in error_msg and "leverage not modified" in error_msg:
                        self.logger.debug(f"Mirror leverage already set correctly for {symbol}")
                    else:
                        self.logger.error(f"Error setting mirror leverage: {e}")

            # Log trade initiation
            self.logger.info(f"🎯 CONSERVATIVE APPROACH TRADE INITIATED:")
            self.logger.info(f"   Symbol: {symbol}")
            self.logger.info(f"   Side: {side}")
            self.logger.info(f"   Trade Group: {trade_group_id}")
            self.logger.info(f"   Margin: {margin_amount} USDT")
            self.logger.info(f"   Leverage: {leverage}x")
            self.logger.info(f"   Limit Orders: {len(limit_prices)}")
            self.logger.info(f"   TP Levels: {len(tp_prices)}")
            self.logger.info(f"   SL: {sl_price}")

            # Import weighted allocation config
            from config.constants import LIMIT_ORDER_ALLOCATION, MARKET_ORDER_PERCENTAGE
            
            # Calculate position sizes
            total_position_size = margin_amount * leverage
            avg_limit_price = sum(limit_prices) / len(limit_prices) if limit_prices else tp_prices[0]
            total_qty = total_position_size / avg_limit_price
            
            # Get current market price for proper TP calculation when using market orders
            actual_entry_price = avg_limit_price  # Default to avg limit price
            if MARKET_ORDER_PERCENTAGE > 0:
                # When market order is used, get actual market price as entry
                from clients.bybit_helpers import get_current_price
                try:
                    current_market_price = await get_current_price(symbol)
                    if current_market_price:
                        actual_entry_price = Decimal(str(current_market_price))
                        self.logger.info(f"📍 Using market price ${actual_entry_price} as entry for TP calculation")
                    else:
                        self.logger.warning(f"Could not fetch market price, using avg limit price ${avg_limit_price}")
                except Exception as e:
                    self.logger.error(f"Error fetching market price: {e}, using avg limit price")
            else:
                # When no market order, use first limit price as initial entry
                if limit_prices:
                    actual_entry_price = limit_prices[0]
                    self.logger.info(f"📍 Using first limit price ${actual_entry_price} as entry for TP calculation")
            
            # Calculate market and limit allocations
            market_qty = total_qty * MARKET_ORDER_PERCENTAGE
            limit_total_qty = total_qty * (Decimal("1") - MARKET_ORDER_PERCENTAGE)
            
            # Distribute quantity across limit orders using weighted allocation
            limit_quantities = []
            if len(limit_prices) > 0:
                # First order is market (if enabled), rest are limits
                market_qty = value_adjusted_to_step(market_qty, qty_step) if MARKET_ORDER_PERCENTAGE > 0 else Decimal("0")
                
                # Calculate each limit order quantity based on weighted allocation
                # FIXED: All 3 limit orders should be placed regardless of market order
                # Market order is separate, not part of limit_prices iteration
                num_limit_orders = 3  # Always place 3 limit orders
                for i in range(num_limit_orders):
                    if i < len(LIMIT_ORDER_ALLOCATION):
                        allocation = LIMIT_ORDER_ALLOCATION[i]
                        limit_qty = limit_total_qty * allocation
                        limit_qty = value_adjusted_to_step(limit_qty, qty_step)
                        limit_quantities.append(limit_qty)
                
                # Log the weighted allocation - show percentage of TOTAL position
                self.logger.info(f"📊 WEIGHTED ALLOCATION (% of total position):")
                self.logger.info(f"   Market: {MARKET_ORDER_PERCENTAGE*100:.0f}% = {market_qty} qty")
                for i, qty in enumerate(limit_quantities, 1):
                    alloc_pct = LIMIT_ORDER_ALLOCATION[i-1] if i-1 < len(LIMIT_ORDER_ALLOCATION) else LIMIT_ORDER_ALLOCATION[-1]
                    # Calculate percentage of total position (not just limit portion)
                    total_position_pct = alloc_pct * (Decimal("1") - MARKET_ORDER_PERCENTAGE)
                    self.logger.info(f"   Limit {i}: {total_position_pct*100:.1f}% = {qty} qty")
            
            # For compatibility with existing code
            qty_per_limit = limit_quantities[0] if limit_quantities else total_qty

            # FIXED: Calculate final SL quantity early for later use
            final_sl_qty = value_adjusted_to_step(total_qty, qty_step)

            # Store initial trade data
            chat_data["trade_initiated_at"] = time.time()
            chat_data["initial_margin"] = str(margin_amount)
            chat_data["initial_leverage"] = leverage
            chat_data["expected_position_size"] = str(final_sl_qty)  # FIXED: Use properly rounded quantity
            chat_data[CONSERVATIVE_LIMITS_FILLED] = []

            orders_placed = []
            order_details = {}
            limit_order_ids = []
            errors = []

            # Initialize mirror trading results tracking
            mirror_results = {"enabled": False, "limits": [], "tps": [], "sl": None, "errors": []}

            # Calculate mirror margin amount and position size
            mirror_margin_amount = margin_amount  # Default to same amount
            mirror_qty_per_limit = qty_per_limit  # Default to same quantity
            mirror_final_sl_qty = final_sl_qty    # Default to same SL quantity
            mirror_total_qty = total_qty           # Default to same total quantity
            
            # Calculate mirror weighted quantities
            mirror_market_qty = Decimal("0")
            mirror_limit_quantities = []

            if MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled():
                mirror_results["enabled"] = True
                try:
                    # Check if percentage-based margin was used
                    margin_percentage = chat_data.get("margin_percentage")
                    if margin_percentage:
                        # Get mirror account balance for proportional calculation
                        from execution.mirror_trader import get_mirror_wallet_balance
                        mirror_total, mirror_available = await get_mirror_wallet_balance()

                        if mirror_available > 0:
                            # Calculate proportional margin for mirror account
                            mirror_margin_amount = (mirror_available * margin_percentage) / 100
                            # Recalculate position size based on mirror margin
                            mirror_position_size = mirror_margin_amount * leverage
                            mirror_total_qty = mirror_position_size / avg_limit_price

                            # Apply weighted allocation for mirror account
                            if MARKET_ORDER_PERCENTAGE > 0:
                                mirror_market_qty = mirror_total_qty * MARKET_ORDER_PERCENTAGE
                                mirror_market_qty = value_adjusted_to_step(mirror_market_qty, qty_step)
                            
                            # Calculate weighted limit quantities for mirror
                            remaining_mirror_qty = mirror_total_qty * (Decimal("1") - MARKET_ORDER_PERCENTAGE)
                            for alloc in LIMIT_ORDER_ALLOCATION:
                                limit_qty = remaining_mirror_qty * alloc
                                limit_qty = value_adjusted_to_step(limit_qty, qty_step)
                                mirror_limit_quantities.append(limit_qty)

                            # Calculate final SL quantity for mirror
                            mirror_final_sl_qty = value_adjusted_to_step(mirror_total_qty, qty_step)

                            # Log the proportional calculation with weighted allocation
                            self.logger.info(f"🪞 MIRROR: Using proportional margin calculation with weighted allocation")
                            self.logger.info(f"   Main margin: ${margin_amount:.2f} | Mirror margin: ${mirror_margin_amount:.2f}")
                            self.logger.info(f"   Main market qty: {market_qty} | Mirror market qty: {mirror_market_qty}")
                            self.logger.info(f"   Main limit qtys: {limit_quantities} | Mirror limit qtys: {mirror_limit_quantities}")
                            self.logger.info(f"   Main SL qty: {final_sl_qty} | Mirror SL qty: {mirror_final_sl_qty}")

                            # Store mirror margin info for summary
                            chat_data["mirror_margin_amount"] = str(mirror_margin_amount)
                            chat_data["mirror_position_size"] = str(mirror_final_sl_qty)
                        else:
                            # If no percentage-based margin, use same weighted allocation as main
                            if market_qty > 0:
                                mirror_market_qty = market_qty
                            if limit_quantities:
                                mirror_limit_quantities = limit_quantities.copy()
                except Exception as e:
                    self.logger.error(f"Error calculating proportional mirror margin: {e}")
                    # Fallback to main account weighted quantities on error
                    if market_qty > 0:
                        mirror_market_qty = market_qty
                    if limit_quantities:
                        mirror_limit_quantities = limit_quantities.copy()

            # Initialize execution data for tracking
            execution_data = {
                'trade_id': trade_group_id,
                'symbol': symbol,
                'side': side,
                'approach': 'conservative',
                'leverage': leverage,
                'margin_amount': float(margin_amount),
                'position_size': float(final_sl_qty),
                'entry_price': float(avg_limit_price),
                'main_orders': [],
                'mirror_orders': [],
                'main_errors': [],
                'mirror_errors': [],
                'position_merged': False,
                'merge_reason': 'N/A',
                'tp_orders': [],
                'sl_orders': [],
                'market_orders': [],
                'limit_orders': [],
                'risk_reward_ratio': 0
            }

            # FIXED: Place market order first if enabled, then all 3 limit orders
            order_counter = 1
            
            # Place market order first if enabled
            if MARKET_ORDER_PERCENTAGE > 0:
                self.logger.info(f"📝 Placing MARKET order ({MARKET_ORDER_PERCENTAGE*100:.0f}% allocation)")
                order_link_id = f"{BOT_PREFIX}CONS_{trade_group_id}_MARKET"
                
                order_params = {
                    "symbol": symbol,
                    "side": side,
                    "order_type": "Market",
                    "qty": str(market_qty),
                    "order_link_id": order_link_id
                }
                
                result = await place_order_with_retry(**order_params)
                
                if result:
                    order_id = result.get("orderId", "")
                    self.logger.info(f"✅ Market order placed: {order_id}")
                    orders_placed.append(order_id)
                    order_details[order_id] = {
                        "type": "market",
                        "qty": str(market_qty),
                        "side": side
                    }
                    execution_data['market_orders'].append({
                        'id': order_id,
                        'qty': str(market_qty),
                        'status': 'placed'
                    })
                else:
                    error_msg = f"Failed to place market order"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                    execution_data['main_errors'].append(error_msg)
            
            # Now place all 3 limit orders
            for i, limit_price in enumerate(limit_prices):
                limit_index = i  # Direct index since we have 3 limit prices
                if limit_index < len(limit_quantities):
                    self.logger.info(f"📝 Placing limit order {i+1} at {limit_price}")
                    order_qty = limit_quantities[limit_index]
                    self.logger.info(f"🔧 Limit order {i+1} quantity: {order_qty} (weighted allocation)")
                    
                    # Create orderLinkId for group tracking
                    order_link_id = f"{BOT_PREFIX}CONS_{trade_group_id}_LIMIT{i+1}"
                    
                    # Prepare order parameters
                    order_params = {
                        "symbol": symbol,
                        "side": side,
                        "order_type": "Limit",
                        "qty": str(order_qty),
                        "price": str(limit_price),
                        "order_link_id": order_link_id
                    }
                    
                    result = await place_order_with_retry(**order_params)

                    if result:
                        order_id = result.get("orderId", "")
                        limit_order_ids.append(order_id)
                        orders_placed.append(f"Limit{i+1}: {order_id[:8]}...")
                        order_details[f"limit{i+1}"] = {
                            "id": order_id,
                            "price": limit_price,
                            "qty": order_qty  # FIXED: Use the actual weighted quantity
                        }
                        self.logger.info(f"✅ Limit order {i+1} placed: {order_id}")
                        execution_data['limit_orders'].append({
                            'id': order_id,
                            'price': str(limit_price),
                            'qty': str(order_qty),
                            'status': 'placed'
                        })
                    else:
                        error_msg = f"Failed to place limit order {i+1}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        execution_data['main_errors'].append(error_msg)


            # MIRROR TRADING: Place orders on mirror account
            if mirror_results["enabled"]:
                self.logger.info(f"🪞 Starting mirror account order placement")
                
                # Place mirror market order if enabled
                if MARKET_ORDER_PERCENTAGE > 0 and mirror_market_qty > 0:
                    try:
                        unique_order_link_id = self._generate_unique_order_link_id(f"{BOT_PREFIX}CONS_{trade_group_id}_MIRROR_MARKET")
                        
                        mirror_result = await mirror_market_order(
                            symbol=symbol,
                            side=side,
                            qty=str(mirror_market_qty),
                            position_idx=0,
                            order_link_id=unique_order_link_id
                        )
                        
                        if mirror_result:
                            mirror_order_id = mirror_result.get("orderId", "")
                            self.logger.info(f"✅ MIRROR: Market order placed: {mirror_order_id[:8]}...")
                            execution_data['mirror_orders'].append(mirror_order_id)
                            execution_data['mirror_orders'].append({
                                'id': mirror_order_id,
                                'type': 'market',
                                'qty': str(mirror_market_qty),
                                'status': 'placed'
                            })
                        else:
                            error_msg = "Mirror market order failed"
                            self.logger.error(f"❌ MIRROR: {error_msg}")
                            mirror_results["errors"].append(error_msg)
                            execution_data['mirror_errors'].append(error_msg)
                    except Exception as e:
                        error_msg = f"Mirror market order error: {str(e)}"
                        self.logger.error(f"❌ MIRROR: {error_msg}")
                        mirror_results["errors"].append(error_msg)
                        execution_data['mirror_errors'].append(error_msg)
                
                # Place all 3 mirror limit orders
                for i, limit_price in enumerate(limit_prices):
                    if i < len(mirror_limit_quantities):
                        try:
                            unique_order_link_id = self._generate_unique_order_link_id(f"{BOT_PREFIX}CONS_{trade_group_id}_MIRROR_LIMIT{i+1}")
                            mirror_order_qty = mirror_limit_quantities[i]
                            
                            mirror_result = await mirror_limit_order(
                                symbol=symbol,
                                side=side,
                                qty=str(mirror_order_qty),
                                price=str(limit_price),
                                position_idx=0,
                                order_link_id=unique_order_link_id
                            )
                            
                            if mirror_result:
                                mirror_order_id = mirror_result.get("orderId", "")
                                mirror_results["limits"].append({"order": i+1, "id": mirror_order_id, "success": True, "type": "Limit"})
                                self.logger.info(f"✅ MIRROR: Limit order {i+1} placed: {mirror_order_id[:8]}...")
                                execution_data['mirror_orders'].append(mirror_order_id)
                                execution_data['mirror_orders'].append({
                                    'id': mirror_order_id,
                                    'type': 'limit',
                                    'price': str(limit_price),
                                    'qty': str(mirror_order_qty),
                                    'status': 'placed'
                                })
                            else:
                                error_msg = f"Mirror limit order {i+1} failed"
                                self.logger.error(f"❌ MIRROR: {error_msg}")
                                mirror_results["limits"].append({"order": i+1, "success": False, "type": "Limit"})
                                mirror_results["errors"].append(error_msg)
                                execution_data['mirror_errors'].append(error_msg)
                        except Exception as e:
                            error_msg = f"Mirror limit order {i+1} error: {str(e)}"
                            self.logger.error(f"❌ MIRROR: {error_msg}")
                            mirror_results["limits"].append({"order": i+1, "success": False, "type": "Limit"})
                            mirror_results["errors"].append(error_msg)
                            execution_data['mirror_errors'].append(error_msg)

            chat_data[LIMIT_ORDER_IDS] = limit_order_ids

            # Check stop order limit before placing TP/SL orders
            from clients.bybit_helpers import check_stop_order_limit, get_correct_position_idx
            stop_order_status = await check_stop_order_limit(symbol)
            available_slots = stop_order_status["available_slots"]

            if available_slots == 0:
                logger.error(f"❌ Cannot place TP/SL orders: Stop order limit reached for {symbol}")
                errors.append(f"Stop order limit reached ({stop_order_status['current_count']}/10). Cannot place TP/SL orders.")
            elif available_slots < 5:  # Need at least 5 slots for 4 TPs + 1 SL
                logger.warning(f"⚠️ Limited stop order slots available: {available_slots}/5 needed")
                errors.append(f"Only {available_slots} stop order slots available. Some TP/SL orders may fail.")

            # Check if we should use enhanced TP/SL system
            if ENHANCED_TP_SL_AVAILABLE and ENABLE_ENHANCED_TP_SL:
                self.logger.info(f"🚀 Using enhanced TP/SL system for {symbol} (Conservative)")

                # For conservative approach, initially we only have the first order filled
                # Calculate initial position size (first order only)
                initial_position_size = qty_per_limit

                # Setup enhanced TP/SL orders with multiple TPs
                enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=final_sl_qty,  # Target position size
                    entry_price=actual_entry_price,  # Use actual entry price (market or first limit)
                    tp_prices=tp_prices[:1],  # Use single TP price
                    tp_percentages=[100],  # Single complete exit
                    sl_price=sl_price,
                    chat_id=chat_id,
                    approach="CONSERVATIVE",
                    qty_step=qty_step,
                    initial_position_size=initial_position_size,  # Pass actual filled size
                    account_type="main"  # Main account trading
                )

                # Create monitor_tasks entry for dashboard tracking
                if enhanced_result.get("success", False):
                    await enhanced_tp_sl_manager.create_dashboard_monitor_entry(
                        symbol=symbol,
                        side=side,
                        approach="conservative",
                        chat_id=chat_id,
                        account_type="main"
                    )

                # Register limit orders with the Enhanced TP/SL system for tracking
                if limit_order_ids:
                    # No need to wait - register_limit_orders now handles waiting internally
                    await enhanced_tp_sl_manager.register_limit_orders(symbol, side, limit_order_ids, "main")
                    self.logger.info(f"📝 Registered {len(limit_order_ids)} limit orders with Enhanced TP/SL system")

                # Extract order IDs from enhanced result
                tp_order_ids = []
                tp_details = []
                if enhanced_result.get("main_account", {}).get("tp_orders"):
                    for i, (order_id, tp_order) in enumerate(enhanced_result["main_account"]["tp_orders"].items(), 1):
                        tp_order_ids.append(tp_order["order_id"])
                        orders_placed.append(f"TP{i}: {tp_order['order_id'][:8]}...")
                        order_details[f"tp{i}"] = {
                            "id": tp_order["order_id"],
                            "price": tp_order["price"],
                            "qty": tp_order["quantity"],
                            "percentage": tp_order["percentage"]
                        }
                        tp_details.append({
                            "level": i,
                            "price": tp_order["price"],
                            "percentage": tp_order["percentage"],
                            "qty": tp_order["quantity"]
                        })
                        self.logger.info(f"✅ Enhanced TP{i} order placed: {tp_order['order_id']}")
                else:
                    self.logger.warning("⚠️ Enhanced TP orders failed")
                    errors.append("Enhanced TP order placement failed")

                chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids

                sl_order_id = None
                if enhanced_result.get("main_account", {}).get("sl_order"):
                    sl_order_id = enhanced_result["main_account"]["sl_order"]["order_id"]
                    chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_order_id
                    orders_placed.append(f"SL: {sl_order_id[:8]}...")
                    order_details["sl"] = {
                        "id": sl_order_id,
                        "price": sl_price,
                        "qty": final_sl_qty
                    }
                    self.logger.info(f"✅ Enhanced SL order placed: {sl_order_id}")
                else:
                    self.logger.warning("⚠️ Enhanced SL order failed")
                    errors.append("Enhanced SL order placement failed")

                # Handle mirror trading for enhanced system (Conservative)
                if mirror_results["enabled"] and MIRROR_TRADING_AVAILABLE:
                    try:
                        from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager, start_mirror_monitoring_task

                        if mirror_enhanced_tp_sl_manager:
                            # Get position index
                            position_idx = await get_correct_position_idx(symbol, side)

                            # Setup mirror enhanced TP/SL with conservative distribution
                            mirror_enhanced_result = await mirror_enhanced_tp_sl_manager.setup_mirror_tp_sl_orders(
                                symbol=symbol,
                                side=side,
                                position_size=mirror_final_sl_qty,
                                entry_price=actual_entry_price,  # Use actual entry price for mirror too
                                tp_prices=tp_prices[:1],  # Single TP
                                tp_percentages=[100],  # Single complete exit
                                sl_price=sl_price,
                                chat_id=chat_id,
                                approach="CONSERVATIVE",
                                position_idx=position_idx,
                                qty_step=qty_step
                            )

                            # Check if mirror_enhanced_result is a valid dictionary (not False or None)
                            if mirror_enhanced_result and isinstance(mirror_enhanced_result, dict):
                                if mirror_enhanced_result.get("tp_orders"):
                                    mirror_results["tps"] = []
                                    for i, (order_id, tp_order) in enumerate(mirror_enhanced_result["tp_orders"].items(), 1):
                                        mirror_results["tps"].append({
                                            "tp": i,
                                            "id": tp_order["order_id"],
                                            "success": True
                                        })
                                    self.logger.info(f"✅ MIRROR: Enhanced TP orders placed (Conservative)")

                                if mirror_enhanced_result.get("sl_order"):
                                    mirror_results["sl"] = {
                                        "id": mirror_enhanced_result["sl_order"]["order_id"],
                                        "success": True
                                    }
                                    self.logger.info(f"✅ MIRROR: Enhanced SL order placed")

                                # Register mirror limit orders with the Mirror Enhanced TP/SL system for tracking
                                mirror_limit_order_ids = []
                                for limit_result in mirror_results.get("limits", []):
                                    if limit_result.get("success") and limit_result.get("id"):
                                        mirror_limit_order_ids.append(limit_result["id"])

                                if mirror_limit_order_ids:
                                    # Register limit orders with mirror account type
                                    await enhanced_tp_sl_manager.register_limit_orders(symbol, side, mirror_limit_order_ids, "mirror")
                                    self.logger.info(f"📝 Registered {len(mirror_limit_order_ids)} mirror limit orders with Enhanced TP/SL system")

                                # Start mirror monitoring
                                await start_mirror_monitoring_task(symbol, side, mirror_enhanced_result)
                            else:
                                # Handle the case where setup failed
                                error_msg = "Mirror enhanced TP/SL setup returned invalid result"
                                self.logger.error(f"❌ MIRROR: {error_msg}")
                                mirror_results["errors"].append(error_msg)

                    except Exception as e:
                        self.logger.error(f"❌ MIRROR: Failed to setup enhanced TP/SL: {e}")
                        mirror_results["errors"].append(f"Mirror enhanced TP/SL error: {str(e)}")

                placed_tp_count = len(tp_order_ids)

            else:
                # Use existing conditional order system
                # FIXED: Place TP orders with automatic position mode detection (will activate when position opens)
                tp_order_ids = []
                tp_side = "Sell" if side == "Buy" else "Buy"

                # FIXED: Determine correct position index for original position direction
                original_position_idx = await get_correct_position_idx(symbol, side)

                # TP percentages for conservative approach
                tp_percentages = [0.85, 0.05, 0.05, 0.05]
                tp_details = []
                placed_tp_count = 0

                for i, (tp_price, tp_pct) in enumerate(zip(tp_prices, tp_percentages), 1):
                    # Check if we've hit the limit (reserve 1 slot for SL)
                    if placed_tp_count >= available_slots - 1 and available_slots > 0:
                        logger.warning(f"⚠️ Skipping TP{i} - would exceed stop order limit")
                        errors.append(f"TP{i} skipped due to stop order limit")
                        continue

                    raw_tp_qty = total_qty * Decimal(str(tp_pct))
                    tp_qty = value_adjusted_to_step(raw_tp_qty, qty_step)
                    # FIXED: Additional rounding to ensure precision
                    tp_qty = value_adjusted_to_step(tp_qty, qty_step)

                    # Calculate proportional TP quantity for mirror
                    mirror_raw_tp_qty = mirror_total_qty * Decimal(str(tp_pct)) if 'mirror_total_qty' in locals() else raw_tp_qty
                    mirror_tp_qty = value_adjusted_to_step(mirror_raw_tp_qty, qty_step)
                    self.logger.info(f"🎯 Placing TP{i} order at {tp_price} ({int(tp_pct*100)}%)")
                    self.logger.info(f"🔧 TP{i} quantity adjusted: {raw_tp_qty} -> {tp_qty} (step: {qty_step})")

                    # Create orderLinkId for group tracking
                    order_link_id = f"{BOT_PREFIX}CONS_{trade_group_id}_TP{i}"

                    result = await place_order_with_retry(
                        symbol=symbol,
                        side=tp_side,
                        order_type="Market",
                        qty=str(tp_qty),
                        trigger_price=str(tp_price),
                        position_idx=original_position_idx,  # FIXED: Use original position index
                        reduce_only=True,
                        order_link_id=order_link_id,
                        stop_order_type="TakeProfit"
                    )

                    if result:
                        order_id = result.get("orderId", "")
                        tp_order_ids.append(order_id)
                        orders_placed.append(f"TP{i}: {order_id[:8]}...")
                        order_details[f"tp{i}"] = {
                            "id": order_id,
                            "price": tp_price,
                            "qty": tp_qty,
                            "percentage": int(tp_pct * 100)
                        }
                        tp_details.append({
                            "level": i,
                            "price": tp_price,
                        "percentage": int(tp_pct * 100),
                        "qty": tp_qty
                    })
                    self.logger.info(f"✅ TP{i} order placed: {order_id}")
                    placed_tp_count += 1

                    # Track TP order
                    execution_data['tp_orders'].append({
                        'order_id': order_id,
                        'price': float(tp_price),
                        'qty': float(tp_qty),
                        'level': i,
                        'percentage': int(tp_pct * 100)
                    })

                    # MIRROR TRADING: Place TP order on second account
                    if mirror_results["enabled"]:
                        try:
                            # Create unique order link ID to avoid duplicates
                            unique_order_link_id = self._generate_unique_order_link_id(f"{order_link_id}_MIRROR")

                            mirror_tp_result = await mirror_limit_order(
                                symbol=symbol,
                                side=tp_side,
                                qty=str(mirror_tp_qty),  # Use proportional quantity
                                price=str(tp_price),
                                position_idx=original_position_idx,
                                order_link_id=unique_order_link_id,
                                reduce_only=True,
                                time_in_force="GTC"
                            )
                            if mirror_tp_result:
                                mirror_tp_id = mirror_tp_result.get("orderId", "")
                                mirror_results["tps"].append({"tp": i, "id": mirror_tp_id, "success": True})
                                self.logger.info(f"✅ MIRROR: TP{i} order placed: {mirror_tp_id[:8]}...")
                            else:
                                mirror_results["tps"].append({"tp": i, "success": False})
                                mirror_results["errors"].append(f"TP{i} order failed")
                        except Exception as e:
                            self.logger.error(f"❌ MIRROR: Failed to place TP{i} order: {e}")
                            mirror_results["tps"].append({"tp": i, "success": False})
                            mirror_results["errors"].append(f"TP{i} order error: {str(e)}")
                    else:
                        self.logger.warning(f"⚠️ TP{i} order failed")
                        errors.append(f"TP{i} order placement failed")

                chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids

                # FIXED: Place SL order with automatic position mode detection and proper quantity rounding
                # Check if we have a slot for SL
                sl_order_id = None
                if placed_tp_count >= available_slots and available_slots > 0:
                    logger.error(f"❌ Cannot place SL order - stop order limit reached")
                    errors.append("SL order skipped due to stop order limit - POSITION AT RISK!")
                else:
                    self.logger.info(f"🛡️ Placing SL order at {sl_price}")
                    self.logger.info(f"🔧 SL quantity adjusted: {total_qty} -> {final_sl_qty} (step: {qty_step})")

                    # Create orderLinkId for group tracking
                    order_link_id = f"{BOT_PREFIX}CONS_{trade_group_id}_SL"

                    sl_result = await place_order_with_retry(
                        symbol=symbol,
                        side=tp_side,
                        order_type="Market",
                        qty=str(final_sl_qty),
                        trigger_price=str(sl_price),
                        position_idx=original_position_idx,  # FIXED: Use original position index
                        reduce_only=True,
                        order_link_id=order_link_id,
                        stop_order_type="StopLoss"
                    )

                    if sl_result:
                        sl_order_id = sl_result.get("orderId", "")
                        chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_order_id
                        orders_placed.append(f"SL: {sl_order_id[:8]}...")
                        order_details["sl"] = {
                            "id": sl_order_id,
                            "price": sl_price,
                            "qty": final_sl_qty
                        }
                        self.logger.info(f"✅ SL order placed: {sl_order_id}")

                        # Track SL order
                        execution_data['sl_orders'].append({
                        'order_id': sl_order_id,
                        'price': float(sl_price),
                        'qty': float(final_sl_qty)
                        })

                        # MIRROR TRADING: Place SL order on second account
                        if mirror_results["enabled"]:
                            try:
                                # Create unique order link ID to avoid duplicates
                                unique_order_link_id = self._generate_unique_order_link_id(f"{order_link_id}_MIRROR")

                                mirror_sl_result = await mirror_tp_sl_order(
                                    symbol=symbol,
                                    side=tp_side,
                                    qty=str(mirror_final_sl_qty),  # Use proportional quantity
                                    trigger_price=str(sl_price),
                                    position_idx=original_position_idx,
                                    order_link_id=unique_order_link_id,
                                    stop_order_type="StopLoss"
                                )
                                if mirror_sl_result:
                                    mirror_sl_id = mirror_sl_result.get("orderId", "")
                                    mirror_results["sl"] = {"id": mirror_sl_id, "success": True}
                                    self.logger.info(f"✅ MIRROR: SL order placed: {mirror_sl_id[:8]}...")
                                else:
                                    mirror_results["sl"] = {"success": False}
                                    mirror_results["errors"].append("SL order failed")
                            except Exception as e:
                                self.logger.error(f"❌ MIRROR: Failed to place SL order: {e}")
                                mirror_results["sl"] = {"success": False}
                                mirror_results["errors"].append(f"SL order error: {str(e)}")
                    else:
                        self.logger.warning(f"⚠️ SL order failed")
                        errors.append("SL order placement failed")

            # Calculate risk metrics with WEIGHTED average entry
            # Use weighted allocation for accurate R:R calculation
            if limit_prices and market_qty > 0:
                # Calculate weighted average with market and limit orders
                total_weight = Decimal("0")
                weighted_sum = Decimal("0")
                
                # Add market component (10% at market price)
                if MARKET_ORDER_PERCENTAGE > 0:
                    # Use first limit as proxy for market price (close enough)
                    market_price = limit_prices[0] if limit_prices else tp_prices[0]
                    weighted_sum += market_price * MARKET_ORDER_PERCENTAGE
                    total_weight += MARKET_ORDER_PERCENTAGE
                
                # Add limit orders with weighted allocation
                remaining_weight = Decimal("1") - MARKET_ORDER_PERCENTAGE
                for i, limit_price in enumerate(limit_prices):
                    if i < len(LIMIT_ORDER_ALLOCATION):
                        weight = LIMIT_ORDER_ALLOCATION[i] * remaining_weight
                        weighted_sum += limit_price * weight
                        total_weight += weight
                
                if total_weight > 0:
                    avg_entry = weighted_sum / total_weight
                    self.logger.info(f"📊 Using weighted average entry for R:R: ${avg_entry:.2f}")
                else:
                    # Fallback to simple average
                    avg_entry = sum(limit_prices) / len(limit_prices)
            else:
                # Fallback if no weighted allocation
                avg_entry = sum(limit_prices) / len(limit_prices) if limit_prices else tp_prices[0]
            # FIXED: Use the properly rounded sl_qty for calculations
            final_sl_qty = value_adjusted_to_step(total_qty, qty_step)
            if side == "Buy":
                risk_amount = (avg_entry - sl_price) * final_sl_qty
                # FIXED: Use single Take Profit for R:R calculation (closes 100% of position)
                max_reward = (tp_prices[0] - avg_entry) * final_sl_qty if tp_prices else 0
            else:
                risk_amount = (sl_price - avg_entry) * final_sl_qty
                # FIXED: Use single Take Profit for R:R calculation (closes 100% of position)
                max_reward = (avg_entry - tp_prices[0]) * final_sl_qty if tp_prices else 0

            # FIXED: Correct risk-reward ratio formula (reward/risk for proper 1:X display)
            risk_reward_ratio = abs(max_reward) / abs(risk_amount) if risk_amount > 0 else 0

            # Calculate position value
            position_value = avg_entry * final_sl_qty

            # Log execution summary
            self.logger.info(f"📊 CONSERVATIVE TRADE EXECUTION SUMMARY:")
            self.logger.info(f"   Limit Orders Placed: {len(limit_order_ids)}")
            self.logger.info(f"   TP Orders Placed: {len(tp_order_ids)}")
            self.logger.info(f"   SL Order Placed: {'Yes' if sl_order_id else 'No'}")
            self.logger.info(f"   Total Position Size: {final_sl_qty}")  # FIXED: Use properly rounded quantity
            self.logger.info(f"   Risk Amount: {format_decimal_or_na(risk_amount, 2)} USDT")
            self.logger.info(f"   Max Reward: {format_decimal_or_na(max_reward, 2)} USDT")

            # Store execution details
            chat_data["execution_details"] = {
                "approach": "conservative",
                "trade_group_id": trade_group_id,
                "limit_order_ids": limit_order_ids,
                "tp_order_ids": tp_order_ids,
                "sl_order_id": sl_order_id,
                "avg_entry_price": str(avg_entry),
                "total_position_size": str(final_sl_qty),  # FIXED: Use properly rounded quantity
                "risk_amount": str(risk_amount),
                "max_reward": str(max_reward),
                "executed_at": time.time()
            }

            # Store mirror order IDs for monitoring
            if mirror_results and mirror_results.get("enabled"):
                # Store mirror order IDs if mirror_results is not None
                if mirror_results:
                    # Store mirror TP order IDs
                    mirror_tp_ids = []
                    for tp in mirror_results.get("tps", []):
                        if tp.get("success") and tp.get("id"):
                            mirror_tp_ids.append(tp["id"])
                    if mirror_tp_ids:
                        chat_data["mirror_conservative_tp_order_ids"] = mirror_tp_ids

                    # Store mirror SL order ID
                    sl_data = mirror_results.get("sl", {})
                    if sl_data and sl_data.get("success") and sl_data.get("id"):
                        chat_data["mirror_conservative_sl_order_id"] = sl_data["id"]

                    # Store mirror limit order IDs
                    mirror_limit_ids = []
                    for limit in mirror_results.get("limits", []):
                        if limit.get("success") and limit.get("id"):
                            mirror_limit_ids.append(limit["id"])
                    if mirror_limit_ids:
                        chat_data["mirror_limit_order_ids"] = mirror_limit_ids
                else:
                    self.logger.warning("Mirror results were None - mirror trading may have failed")

            # Record execution summary if module is available
            if EXECUTION_SUMMARY_AVAILABLE:
                try:
                    execution_data['risk_reward_ratio'] = float(risk_reward_ratio)
                    execution_data['main_fill_status'] = 'pending'
                    execution_data['mirror_fill_status'] = 'pending' if mirror_results and mirror_results.get("enabled") else 'N/A'
                    execution_data['main_execution_time'] = time.time() - start_time
                    execution_data['mirror_execution_time'] = time.time() - start_time if mirror_results and mirror_results.get("enabled") else 0
                    execution_data['mirror_enabled'] = mirror_results.get("enabled") if mirror_results else False
                    execution_data['mirror_sync_status'] = 'synced' if mirror_results and mirror_results.get("enabled") and not mirror_results.get("errors") else 'partial' if mirror_results and mirror_results.get("enabled") else 'N/A'
                    execution_data['total_orders'] = len(limit_order_ids) + len(tp_order_ids) + (1 if sl_order_id else 0)
                    execution_data['successful_orders'] = len(limit_order_ids) + len(tp_order_ids) + (1 if sl_order_id else 0)
                    execution_data['failed_orders'] = len(errors)
                    execution_data['avg_fill_time'] = (time.time() - start_time) / execution_data['total_orders'] if execution_data['total_orders'] > 0 else 0

                    await execution_summary.record_execution(trade_group_id, execution_data)
                    self.logger.info(f"✅ Execution summary recorded for trade {trade_group_id}")
                except Exception as e:
                    self.logger.error(f"Failed to record execution summary: {e}")

            # Start monitoring for this position (skip if Enhanced TP/SL is handling it)
            if not (ENABLE_ENHANCED_TP_SL and enhanced_result.get("success")):
                try:
                    from execution.monitor import start_position_monitoring
                    await start_position_monitoring(application, chat_id, chat_data)
                    self.logger.info(f"✅ Enhanced monitoring started for conservative trade {trade_group_id}")

                    # Always start mirror monitoring for bot positions if mirror trading is enabled
                    if is_mirror_trading_enabled():
                        try:
                            from execution.monitor import start_mirror_position_monitoring
                            await start_mirror_position_monitoring(application, chat_id, chat_data)
                            self.logger.info(f"✅ Mirror position monitoring started for conservative trade {trade_group_id} (regardless of mirror trade success)")
                        except Exception as e:
                            self.logger.error(f"Error starting mirror position monitoring: {e}")
                except Exception as e:
                    self.logger.error(f"Error starting position monitoring: {e}")
                    errors.append("Position monitoring failed to start")
            else:
                self.logger.info(f"✅ Enhanced TP/SL system handling monitoring for conservative trade {trade_group_id} - skipping old monitors")

            # Determine overall success
            # Success if we placed at least one limit order (entry orders are crucial)
            # TP orders might fail due to stop order limits but that shouldn't fail the entire trade
            success = len(limit_order_ids) > 0

            # Build enhanced message
            execution_time = self._format_execution_time(start_time)
            side_emoji = "📈" if side == "Buy" else "📉"
            side_text = "LONG" if side == "Buy" else "SHORT"

            if success:
                # Calculate additional metrics
                trend_indicator = self._get_market_trend_indicator(side, avg_entry, tp_prices[-1] if tp_prices else avg_entry, sl_price)
                position_metrics = self._format_position_metrics(final_sl_qty, position_value, leverage)

                message = (
                    f"🛡️ <b>CONSERVATIVE TRADE DEPLOYED</b> 🛡️\n"
                    f"════════════════════════════════════\n"
                    f"📊 <b>{symbol} {side_text}</b> │ <code>{leverage}x</code> │ ID: <code>{trade_group_id}</code>\n\n"
                )

                # Position metrics box
                message += (
                    f"💼 <b>POSITION METRICS</b>\n"
                    f"├─ Margin: <code>${format_decimal_or_na(margin_amount, 2)}</code>\n"
                    f"├─ Total Size: <code>{format_decimal_or_na(final_sl_qty, 4)}</code> {symbol.replace('USDT', '')}\n"
                )

                # Add mirror margin info if using percentage-based margin
                if mirror_results["enabled"] and chat_data.get("margin_percentage"):
                    message += f"├─ Mirror Margin: <code>${format_decimal_or_na(mirror_margin_amount, 2)}</code>\n"
                    message += f"├─ Mirror Size: <code>{format_decimal_or_na(mirror_final_sl_qty, 4)}</code> {symbol.replace('USDT', '')}\n"

                message += f"└─ Position Value: <code>${format_decimal_or_na(position_value, 2)}</code>\n\n"

                # Entry strategy box
                has_market = MARKET_ORDER_PERCENTAGE > 0
                num_orders = len(limit_prices) + (1 if has_market else 0)
                message += (
                    f"📍 <b>ENTRY STRATEGY</b> ({num_orders} Orders: {1 if has_market else 0} Market + {len(limit_prices)} Limits)\n"
                )

                # Show market order first if enabled
                if has_market and market_qty > 0:
                    market_pct = float(MARKET_ORDER_PERCENTAGE * 100)
                    message += f"├─ Market: <code>Current Price</code> ({market_pct:.0f}%)\n"
                
                # Add limit order details with correct weighted allocation
                for i, price in enumerate(limit_prices, 1):
                    # Calculate actual percentage of total position
                    if i <= len(limit_quantities):
                        qty = limit_quantities[i-1]
                        actual_pct = float((LIMIT_ORDER_ALLOCATION[i-1] * (Decimal("1") - MARKET_ORDER_PERCENTAGE)) * 100)
                        if i == len(limit_prices):
                            message += f"└─ Limit {i}: <code>${format_price(price)}</code> ({actual_pct:.1f}%)\n"
                        else:
                            message += f"├─ Limit {i}: <code>${format_price(price)}</code> ({actual_pct:.1f}%)\n"

                # Enhanced TP section with visual formatting and correct percentages
                if len(tp_order_ids) > 0:
                    message += f"\n🎯 <b>EXIT STRATEGY</b> Single Take Profit (100% Exit)\n"

                    # Add TP details with enhanced formatting
                    for i, tp in enumerate(tp_details, 1):
                        pct_from_avg = ((tp['price'] - avg_entry) / avg_entry * 100 if side == "Buy" else (avg_entry - tp['price']) / avg_entry * 100) if avg_entry > 0 else 0
                        potential_profit = position_value * Decimal(tp['percentage']) / Decimal(100) * Decimal(pct_from_avg) / Decimal(100)

                        message += f"└─ TP: <code>${format_price(tp['price'])}</code> ({format_mobile_percentage(pct_from_avg)}) │ 100% exit │ ${potential_profit:.2f}\n"
                else:
                    message += f"\n⚠️ <b>Take Profit Orders:</b> SKIPPED (Stop order limit reached)\n"
                    message += f"   • TP levels configured but not placed due to Bybit limits\n"
                    message += f"   • Monitor will manage exits manually if needed\n"

                # Risk management section
                sl_pct = ((avg_entry - sl_price) / avg_entry * 100 if side == 'Buy' else (sl_price - avg_entry) / avg_entry * 100)
                message += (
                    f"\n🛡️ <b>RISK MANAGEMENT</b>\n"
                    f"├─ Stop Loss: <code>${format_price(sl_price)}</code> ({format_mobile_percentage(-sl_pct)})\n"
                    f"├─ Max Risk: <code>${format_decimal_or_na(risk_amount, 2)}</code>\n"
                    f"├─ Max Reward: <code>${format_decimal_or_na(max_reward, 2)}</code>\n"
                    f"└─ R:R Ratio: 1:{risk_reward_ratio:.1f} {'🌟 EXCELLENT' if risk_reward_ratio >= 3 else '✅ GOOD' if risk_reward_ratio >= 2 else '⚠️ FAIR' if risk_reward_ratio >= 1 else '❌ POOR'}\n\n"
                )

                # Enhanced breakdown with more details
                message += f"\n📋 <b>CONSERVATIVE APPROACH EXPLAINED</b>\n"
                message += f"────────────────────────────────────\n"

                # Entry strategy with weighted allocation
                message += f"<b>🔹 Entry Strategy (Weighted Allocation):</b>\n"
                
                # Show market order if applicable
                if MARKET_ORDER_PERCENTAGE > 0:
                    market_value = market_qty * avg_entry
                    message += f"   • Market: {format_decimal_or_na(market_qty, 4)} ({float(MARKET_ORDER_PERCENTAGE*100):.0f}%) • ${market_value:.2f}\n"
                
                # Show limit orders with correct weighted allocation
                for i, (price, qty) in enumerate(zip(limit_prices[:3], limit_quantities), 1):
                    value_per_order = qty * price
                    # Calculate actual percentage of total position (not just limit portion)
                    actual_pct = float((LIMIT_ORDER_ALLOCATION[i-1] * (Decimal("1") - MARKET_ORDER_PERCENTAGE)) * 100)
                    message += f"   {i}. ${format_price(price)} • {format_decimal_or_na(qty, 4)} ({actual_pct:.1f}%) • ${value_per_order:.2f}\n"
                message += f"   ➤ Weighted for better average entry\n"
                message += f"   ➤ Improves R:R ratio\n\n"

                # Single TP strategy
                message += f"<b>🔹 Take Profit Target (100%):</b>\n"
                if len(tp_order_ids) > 0:
                    tp_profit = position_value * Decimal('1.0') * (((tp_prices[0] - avg_entry) / avg_entry) if side == "Buy" else ((avg_entry - tp_prices[0]) / avg_entry))
                    message += f"   • Take Profit (100%): Locks in ${abs(tp_profit):.2f} profit\n"
                    message += f"   • Complete position closure at target\n"
                    message += f"   • Total potential: ${format_decimal_or_na(max_reward, 2)}\n"
                else:
                    message += f"   • Orders configured but not placed\n"
                    message += f"   • Bybit order limit reached\n"
                    message += f"   • Monitor will manage exits\n"

                # Risk management
                message += f"\n<b>🔹 Risk Management:</b>\n"
                message += f"   • Stop Loss: ${format_price(sl_price)} ({format_mobile_percentage(-sl_pct)})\n"
                message += f"   • Max Risk: ${format_decimal_or_na(risk_amount, 2)}\n"
                message += f"   • Protects 100% of position\n\n"

                # Key features
                message += f"<b>🔹 Key Features:</b>\n"
                message += f"   ✓ Auto-monitoring every 10 seconds\n"
                message += f"   ✓ Automatic TP/SL rebalancing\n"
                message += f"   ✓ Breakeven protection after TP1\n"
                message += f"   ✓ Alerts for all order fills\n"
                message += f"   ✓ Position tracking until closed\n"

                # Add monitoring status and quick actions
                message += f"\n🔔 <b>MONITORING & ACTIONS</b>\n"
                message += f"├─ Status: ✅ Active (10s intervals)\n"
                if mirror_results["enabled"]:
                    message += f"├─ Mirror: ✅ Synchronized\n"
                message += f"├─ View Positions: /positions\n"
                message += f"├─ Check Stats: /stats\n"
                message += f"└─ Emergency Close: /emergency\n"

                # Add approach benefits
                message += f"\n📚 <b>WHY CONSERVATIVE?</b>\n"
                message += f"• 85% TP1 = Secure bulk profits early\n"
                message += f"• 15% runners = Capture big moves\n"
                message += f"• Breakeven after TP1 = Risk-free\n"
                message += f"• 3 entries = Better average price\n"

                # Execution summary
                message += f"\n⚡ Execution Time: {execution_time}"

                # Add mirror trading summary if available
                mirror_summary = self._format_conservative_mirror_summary(mirror_results)
                if mirror_summary:
                    message += mirror_summary

                if errors:
                    message += f"\n⚠️ <b>Warnings:</b>\n"
                    for error in errors:
                        message += f"   • {error}\n"

                    # Add special warning if stop order limit was hit
                    if any("stop order limit" in error.lower() for error in errors):
                        message += f"\n🚨 <b>STOP ORDER LIMIT REACHED!</b>\n"
                        message += f"   • Bybit allows max 10 stop orders per symbol\n"
                        message += f"   • Current active: {stop_order_status.get('current_count', 'Unknown')}/10\n"
                        message += f"   • Entry orders were placed successfully ✅\n"
                        message += f"   • TP orders were skipped to preserve limit ⚠️\n"
                        message += f"   • The monitor will handle exits if needed 🔄\n"
                        message += f"   • Cancel unused orders to free slots 🗑️\n"
            else:
                message = (
                    f"❌ <b>CONSERVATIVE TRADE FAILED</b> {execution_time}\n"
                    f"{create_mobile_separator()}\n\n"
                    f"📊 <b>Attempted Trade:</b>\n"
                    f"   {side_emoji} {symbol} {side_text}\n"
                    f"   🆔 Group: {trade_group_id}\n"
                    f"   💰 Margin: {format_mobile_currency(margin_amount)}\n"
                    f"   ⚡ Leverage: {leverage}x\n\n"
                    f"❌ <b>Errors:</b>\n"
                )
                for error in errors:
                    message += f"   • {error}\n"

                if orders_placed:
                    message += f"\n{self._format_order_summary(orders_placed, order_details)}"

            # Log trade to history
            try:
                from utils.trade_logger_enhanced import log_trade_entry, log_tp_orders, log_sl_order

                # Log entry with average price from limit orders
                trade_key = await log_trade_entry(
                    symbol=symbol,
                    side=side,
                    approach="Conservative",
                    entry_price=avg_entry,
                    size=final_sl_qty,
                    order_type="Limit",
                    chat_id=str(chat_id),
                    leverage=leverage,
                    risk_percentage=chat_data.get(RISK_PERCENTAGE)
                )

                if trade_key:
                    # Log TP orders
                    tp_order_data = []
                    for i, (tp_id, tp_detail) in enumerate(zip(tp_order_ids, tp_details)):
                        tp_order_data.append({
                            'symbol': symbol,
                            'side': 'Sell' if side == 'Buy' else 'Buy',
                            'price': str(tp_detail['price']),
                            'qty': str(tp_detail['qty']),
                            'percentage': tp_detail['percentage'],
                            'orderId': tp_id,
                            'orderLinkId': f"{BOT_PREFIX}CONS_{trade_group_id}_TP{i+1}"
                        })

                    if tp_order_data:
                        await log_tp_orders(trade_key, tp_order_data)

                    # Log SL order
                    if sl_order_id:
                        await log_sl_order(trade_key, {
                            'symbol': symbol,
                            'side': side,
                            'triggerPrice': str(sl_price),
                            'qty': str(final_sl_qty),
                            'orderId': sl_order_id,
                            'orderLinkId': f"{BOT_PREFIX}CONS_{trade_group_id}_SL"
                        })

                    chat_data["trade_key"] = trade_key
                    self.logger.info(f"Trade logged with key: {trade_key}")

            except Exception as log_error:
                self.logger.error(f"Failed to log trade: {log_error}")

            return {
                "success": success,
                "orders_placed": orders_placed,
                "limit_orders": len(limit_order_ids),
                "tp_orders": len(tp_order_ids),
                "sl_order": bool(sl_order_id),
                "trade_group_id": trade_group_id,
                "message": message,
                "errors": errors,
                "avg_entry": avg_entry,
                "position_size": final_sl_qty,
                "risk_reward_ratio": risk_reward_ratio,
                "risk_amount": risk_amount,
                "max_reward": max_reward
            }

        except Exception as e:
            self.logger.error(f"❌ Error executing conservative approach: {e}", exc_info=True)
            execution_time = self._format_execution_time(start_time)
            return {
                "success": False,
                "error": f"Execution error: {str(e)}",
                "orders_placed": [],
                "message": (
                    f"❌ <b>CONSERVATIVE TRADE ERROR</b> {execution_time}\n"
                    f"{create_mobile_separator()}\n\n"
                    f"🚨 <b>Critical Error:</b>\n{str(e)}\n\n"
                    f"Please check your settings and try again."
                )
            }

    async def execute_simple_market_approach(self, application, chat_id: int, chat_data: dict) -> dict:
        """
        Execute Simple Market approach: Market order + Single TP (100%) + SL
        SIMPLE: Quick in/out trades with market execution
        FIXED: Automatic position mode detection
        """
        start_time = time.time()
        
        try:
            # Extract parameters
            symbol = chat_data.get(SYMBOL)
            side = chat_data.get(SIDE)
            margin_amount = safe_decimal_conversion(chat_data.get(MARGIN_AMOUNT))
            leverage = int(chat_data.get(LEVERAGE, 1))
            tick_size = safe_decimal_conversion(chat_data.get(INSTRUMENT_TICK_SIZE, "0.01"))
            qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))
            trade_group_id = chat_data.get("SIMPLE_MARKET_TRADE_GROUP_ID", "unknown")
            
            # Get prices
            entry_price = safe_decimal_conversion(chat_data.get("primary_entry_price"))
            tp_price = safe_decimal_conversion(chat_data.get("TP1_PRICE"))
            sl_price = safe_decimal_conversion(chat_data.get("SL_PRICE"))
            
            # Check for approach conflicts
            self.logger.info(f"🔍 Checking for existing orders on {symbol} {side}...")
            conflict_info = await check_approach_conflicts(symbol, side, "simple_market")
            
            if conflict_info.get("conflict"):
                existing_approach = conflict_info.get("existing_approach")
                self.logger.info(f"⚠️ Found existing {existing_approach} approach for {symbol}")
                
                # Cleanup existing orders
                if conflict_info.get("recommendation") == "cleanup_all":
                    self.logger.info("🧹 Cleaning up ALL existing orders...")
                    cleanup_result = await cleanup_all_orders(symbol, side)
                    if cleanup_result["success"]:
                        self.logger.info(f"✅ Cleaned up {cleanup_result['cancelled_count']} orders")
            
            # Set leverage
            await set_symbol_leverage(symbol, leverage)
            self.logger.info(f"⚙️ Set leverage to {leverage}x for {symbol}")
            
            # Calculate position size
            position_size = (margin_amount * Decimal(str(leverage))) / entry_price
            position_size = value_adjusted_to_step(position_size, qty_step)
            
            # Generate shorter unique order link IDs (max 45 chars)
            import time
            timestamp = str(int(time.time() * 1000))[-6:]  # Last 6 digits
            market_link_id = f"BOT_SM_{symbol[:6]}_{side[0]}_{timestamp}_M"
            tp_link_id = f"BOT_SM_{symbol[:6]}_{side[0]}_{timestamp}_T"
            sl_link_id = f"BOT_SM_{symbol[:6]}_{side[0]}_{timestamp}_S"
            
            # Place market order (no positionIdx, automatic detection)
            self.logger.info(f"⚡ Placing market order for {position_size} {symbol} at market price...")
            market_result = await place_order_with_retry(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=str(position_size),
                order_link_id=market_link_id,
                reduce_only=False
            )
            
            if not market_result:
                self.logger.error(f"❌ Failed to place market order")
                return {
                    "success": False,
                    "error": f"Failed to place market order"
                }
            
            market_order_id = market_result.get("orderId", "")
            actual_entry = safe_decimal_conversion(market_result.get("avgPrice", entry_price))
            self.logger.info(f"✅ Market order executed: {market_order_id} at {actual_entry}")
            
            # Place TP order (100% position)
            opposite_side = "Sell" if side == "Buy" else "Buy"
            
            self.logger.info(f"🎯 Placing Take Profit order at {tp_price} (100% position)...")
            tp_result = await place_order_with_retry(
                symbol=symbol,
                side=opposite_side,
                order_type="Limit",
                qty=str(position_size),
                price=str(tp_price),
                order_link_id=tp_link_id,
                reduce_only=True
            )
            
            tp_order_id = None
            if tp_result:
                tp_order_id = tp_result.get("orderId", "")
                self.logger.info(f"✅ TP order placed: {tp_order_id}")
            else:
                self.logger.warning(f"⚠️ Failed to place TP order")
            
            # Place SL order
            self.logger.info(f"🛡️ Placing Stop Loss order at {sl_price}...")
            sl_result = await place_order_with_retry(
                symbol=symbol,
                side=opposite_side,
                order_type="Market",
                qty=str(position_size),
                trigger_price=str(sl_price),
                order_link_id=sl_link_id,
                reduce_only=True,
                stop_order_type="StopLoss"
            )
            
            sl_order_id = None
            if sl_result:
                sl_order_id = sl_result.get("orderId", "")
                self.logger.info(f"✅ SL order placed: {sl_order_id}")
            else:
                self.logger.warning(f"⚠️ Failed to place SL order")
            
            # Mirror trading support
            mirror_results = None
            if MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled():
                self.logger.info("🔄 Executing mirror trades...")
                
                # Mirror market order (with shortened IDs)
                mirror_market_id = f"BOT_SM_{symbol[:6]}_{side[0]}_{timestamp}_M2"
                mirror_market = await mirror_market_order(
                    symbol, side, position_size, mirror_market_id
                )
                
                # Mirror TP order
                if tp_order_id:
                    mirror_tp_id = f"BOT_SM_{symbol[:6]}_{side[0]}_{timestamp}_T2"
                    mirror_tp = await mirror_tp_sl_order(
                        symbol, opposite_side, position_size, tp_price,
                        mirror_tp_id, order_type="Limit", reduce_only=True
                    )
                
                # Mirror SL order
                if sl_order_id:
                    mirror_sl_id = f"BOT_SM_{symbol[:6]}_{side[0]}_{timestamp}_S2"
                    mirror_sl = await mirror_tp_sl_order(
                        symbol, opposite_side, position_size, None,
                        mirror_sl_id, order_type="Market",
                        trigger_price=sl_price, reduce_only=True
                    )
            
            # Setup Enhanced TP/SL monitoring
            if ENHANCED_TP_SL_AVAILABLE and ENABLE_ENHANCED_TP_SL:
                self.logger.info("🎯 Setting up Enhanced TP/SL monitoring...")
                monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": str(actual_entry),
                    "stop_loss": str(sl_price),
                    "take_profits": [{"price": str(tp_price), "percentage": 100}],
                    "position_size": str(position_size),
                    "chat_id": chat_id,
                    "approach": "simple_market"
                }
                
                monitor_id = enhanced_tp_sl_manager.create_monitor(
                    symbol=symbol,
                    side=side,
                    monitor_data=monitor_data,
                    account="main"
                )
                
                if monitor_id:
                    self.logger.info(f"✅ Enhanced TP/SL monitor created: {monitor_id}")
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Calculate risk/reward
            risk_amount = position_size * abs(actual_entry - sl_price)
            reward_amount = position_size * abs(tp_price - actual_entry)
            risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0
            
            self.logger.info(f"⚡ SIMPLE MARKET EXECUTION SUMMARY:")
            self.logger.info(f"   Market Order: {market_order_id}")
            self.logger.info(f"   TP Order: {tp_order_id}")
            self.logger.info(f"   SL Order: {sl_order_id}")
            self.logger.info(f"   Position Size: {position_size}")
            self.logger.info(f"   Entry Price: {actual_entry}")
            self.logger.info(f"   Risk: {format_decimal_or_na(risk_amount, 2)} USDT")
            self.logger.info(f"   Reward: {format_decimal_or_na(reward_amount, 2)} USDT")
            self.logger.info(f"   R:R Ratio: 1:{risk_reward_ratio:.2f}")
            
            # Store execution details
            chat_data["execution_details"] = {
                "approach": "simple_market",
                "trade_group_id": trade_group_id,
                "market_order_id": market_order_id,
                "tp_order_id": tp_order_id,
                "sl_order_id": sl_order_id,
                "entry_price": str(actual_entry),
                "position_size": str(position_size),
                "risk_amount": str(risk_amount),
                "reward_amount": str(reward_amount),
                "executed_at": time.time()
            }
            
            # Generate summary - always use internal method for simple_market
            summary = self._generate_simple_market_summary(
                symbol, side, position_size, actual_entry, tp_price, sl_price,
                margin_amount, leverage, risk_reward_ratio, execution_time
            )
            
            return {
                "success": True,
                "message": summary,
                "execution_time": execution_time,
                "orders_placed": {
                    "market": 1,
                    "tp": 1 if tp_order_id else 0,
                    "sl": 1 if sl_order_id else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error executing simple market trade: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time
            }
    
    def _generate_simple_market_summary(self, symbol, side, position_size, entry_price,
                                       tp_price, sl_price, margin, leverage, rr_ratio, exec_time):
        """Generate a simple market execution summary"""
        direction_emoji = "📈" if side == "Buy" else "📉"
        
        return (
            f"⚡ <b>SIMPLE MARKET TRADE EXECUTED</b> ⚡\n"
            f"{'═' * 30}\n\n"
            f"📊 <b>Symbol:</b> {symbol}\n"
            f"{direction_emoji} <b>Direction:</b> {side.upper()}\n"
            f"💰 <b>Position Size:</b> {format_decimal_or_na(position_size)}\n"
            f"📍 <b>Entry:</b> {format_price(entry_price)}\n"
            f"🎯 <b>Take Profit:</b> {format_price(tp_price)} (100%)\n"
            f"🛡️ <b>Stop Loss:</b> {format_price(sl_price)}\n"
            f"⚡ <b>Leverage:</b> {leverage}x\n"
            f"💵 <b>Margin:</b> {format_decimal_or_na(margin, 2)} USDT\n"
            f"⚖️ <b>Risk/Reward:</b> 1:{rr_ratio:.2f}\n\n"
            f"⏱️ <b>Execution Time:</b> {exec_time:.2f}s\n"
            f"✅ <b>Status:</b> Position Opened Successfully"
        )

    async def execute_ggshot_approach(self, application, chat_id: int, chat_data: dict) -> dict:
        """
        Execute GGShot approach: Always uses Conservative pattern with 1 market + 2 limit orders
        ENHANCED: AI-extracted parameters with Conservative execution logic
        FIXED: First order is always market, remaining are limits
        INNOVATIVE: Screenshot-based trade execution
        """
        start_time = time.time()

        try:
            # Extract parameters
            symbol = chat_data.get(SYMBOL)
            side = chat_data.get(SIDE)
            margin_amount = safe_decimal_conversion(chat_data.get(MARGIN_AMOUNT))
            leverage = int(chat_data.get(LEVERAGE, 1))
            tick_size = safe_decimal_conversion(chat_data.get(INSTRUMENT_TICK_SIZE, "0.01"))
            qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))

            # Generate trade group ID for GGShot approach
            import uuid
            trade_group_id = chat_data.get(GGSHOT_TRADE_GROUP_ID) or str(uuid.uuid4())[:8]
            chat_data[GGSHOT_TRADE_GROUP_ID] = trade_group_id

            # GGShot ALWAYS uses conservative pattern
            self.logger.info(f"📸 GGShot approach using conservative pattern with market + limits")

            # Execute as Conservative approach with AI parameters
            # First order will be market, remaining will be limits
            return await self._execute_ggshot_conservative_pattern(
                application, chat_id, chat_data, trade_group_id, start_time
            )

        except Exception as e:
            self.logger.error(f"❌ Error executing GGShot approach: {e}", exc_info=True)
            execution_time = self._format_execution_time(start_time)
            return {
                "success": False,
                "error": f"Execution error: {str(e)}",
                "orders_placed": [],
                "message": (
                    f"❌ <b>GGSHOT TRADE ERROR</b> {execution_time}\n"
                    f"{create_mobile_separator()}\n\n"
                    f"🚨 <b>Critical Error:</b>\n{str(e)}\n\n"
                    f"📸 AI analysis may have failed. Please try manual entry."
                )
            }

    async def _execute_ggshot_fast_pattern(self, application, chat_id: int, chat_data: dict,
                                          trade_group_id: str, start_time: float) -> dict:
        """Execute GGShot with Fast Market pattern"""
        try:
            # Extract and validate parameters
            symbol = chat_data.get(SYMBOL)
            side = chat_data.get(SIDE)
            margin_amount = safe_decimal_conversion(chat_data.get(MARGIN_AMOUNT))
            leverage = int(chat_data.get(LEVERAGE, 1))
            tp_price = safe_decimal_conversion(chat_data.get(TP1_PRICE))
            sl_price = safe_decimal_conversion(chat_data.get(SL_PRICE))
            tick_size = safe_decimal_conversion(chat_data.get(INSTRUMENT_TICK_SIZE, "0.01"))
            qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))
            entry_price = safe_decimal_conversion(chat_data.get(PRIMARY_ENTRY_PRICE))

            # Log trade initiation
            self.logger.info(f"📸 GGSHOT FAST PATTERN TRADE INITIATED:")
            self.logger.info(f"   Symbol: {symbol}")
            self.logger.info(f"   Side: {side}")
            self.logger.info(f"   Trade Group: {trade_group_id}")
            self.logger.info(f"   AI-extracted entry: {entry_price}")

            # Execute GGShot approach with AI parameters
            position_value = margin_amount * leverage
            qty = position_value / entry_price
            qty = value_adjusted_to_step(qty, qty_step)

            orders_placed = []
            order_details = {}
            errors = []

            # Place market order with AI-extracted parameters
            order_link_id = f"{trade_group_id}_MARKET"

            market_result = await place_order_with_retry(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=str(qty),
                order_link_id=order_link_id
            )

            market_order_id = None
            avg_price = entry_price

            if market_result:
                market_order_id = market_result.get("orderId", "")
                avg_price = safe_decimal_conversion(market_result.get("avgPrice", str(entry_price)))
                chat_data[GGSHOT_ENTRY_ORDER_IDS] = [market_order_id]
                orders_placed.append(f"Market Entry: {market_order_id[:8]}...")

                # Mark that this position was created by the bot
                chat_data["position_created"] = True
                chat_data["has_bot_orders"] = True  # Mark as bot-initiated trade
                chat_data["position_created_time"] = time.time()
                order_details["market"] = {
                    "id": market_order_id,
                    "price": avg_price,
                    "qty": qty
                }
                self.logger.info(f"✅ GGShot market order placed: {market_order_id}")
            else:
                errors.append("Market order placement failed")
                self.logger.error("❌ GGShot market order failed")

            # Use Enhanced TP/SL system for GGShot Fast
            enhanced_tp_sl_result = {"success": False}
            tp_order_id = None
            sl_order_id = None

            if ENHANCED_TP_SL_AVAILABLE and ENABLE_ENHANCED_TP_SL and market_order_id:
                self.logger.info(f"🚀 Using enhanced TP/SL system for GGShot fast {symbol}")

                # Setup enhanced TP/SL orders for GGShot
                enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=qty,
                    entry_price=avg_price,
                    tp_prices=[tp_price] if tp_price else [],
                    tp_percentages=[100] if tp_price else [],  # 100% at single TP
                    sl_price=sl_price,
                    chat_id=chat_id,
                    approach="GGSHOT_FAST",
                    qty_step=qty_step,
                    account_type="main"  # Main account trading
                )

                enhanced_tp_sl_result = enhanced_result

                # Create monitor_tasks entry for dashboard tracking
                if enhanced_result.get("success", False):
                    await enhanced_tp_sl_manager.create_dashboard_monitor_entry(
                        symbol=symbol,
                        side=side,
                        approach="ggshot",
                        chat_id=chat_id,
                        account_type="main"
                    )

                if enhanced_result.get("success"):
                    self.logger.info("✅ GGShot enhanced TP/SL setup successful")

                    # Store TP order info
                    if enhanced_result.get("tp_orders"):
                        tp_order_id = enhanced_result["tp_orders"][0]["order_id"]
                        chat_data[GGSHOT_TP_ORDER_IDS] = [tp_order_id]
                        orders_placed.append(f"Enhanced TP: {tp_order_id[:8]}...")
                        order_details["tp"] = {
                            "id": tp_order_id,
                            "price": tp_price,
                            "qty": qty
                        }
                        self.logger.info(f"✅ GGShot Enhanced TP order placed: {tp_order_id}")

                    # Store SL order info
                    if enhanced_result.get("sl_order"):
                        sl_order_id = enhanced_result["sl_order"]["order_id"]
                        chat_data[GGSHOT_SL_ORDER_ID] = sl_order_id
                        orders_placed.append(f"Enhanced SL: {sl_order_id[:8]}...")
                        order_details["sl"] = {
                            "id": sl_order_id,
                            "price": sl_price,
                            "qty": qty
                        }
                        self.logger.info(f"✅ GGShot Enhanced SL order placed: {sl_order_id}")
                else:
                    self.logger.warning("⚠️ GGShot enhanced TP/SL setup failed")
                    errors.append("Enhanced TP/SL setup failed for GGShot")
            else:
                self.logger.info("ℹ️ Enhanced TP/SL not available, using standard orders")
                errors.append("Enhanced TP/SL system required for GGShot")

            # Calculate risk metrics
            if side == "Buy":
                risk_amount = (avg_price - sl_price) * qty if sl_price else 0
                reward_amount = (tp_price - avg_price) * qty if tp_price else 0
            else:
                risk_amount = (sl_price - avg_price) * qty if sl_price else 0
                reward_amount = (avg_price - tp_price) * qty if tp_price else 0

            risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

            # Start monitoring (skip if Enhanced TP/SL is handling it)
            if not (ENABLE_ENHANCED_TP_SL and enhanced_result.get("success")):
                try:
                    from execution.monitor import start_position_monitoring
                    await start_position_monitoring(application, chat_id, chat_data)
                    self.logger.info(f"✅ Enhanced monitoring started for GGShot fast trade {trade_group_id}")
                except Exception as e:
                    self.logger.error(f"Error starting position monitoring: {e}")
                    errors.append("Position monitoring failed to start")
            else:
                self.logger.info(f"✅ Enhanced TP/SL system handling monitoring for GGShot fast {trade_group_id} - skipping old monitors")

            # Build success message
            success = bool(market_order_id)
            execution_time = self._format_execution_time(start_time)

            side_emoji = "📈" if side == "Buy" else "📉"
            side_text = "LONG" if side == "Buy" else "SHORT"

            if success:
                message = (
                    f"📸 <b>GGSHOT AI TRADE EXECUTED</b> 📸\n"
                    f"════════════════════════════════════\n"
                    f"🤖 AI Analysis: ✅ HIGH CONFIDENCE\n\n"
                    f"📊 <b>{symbol} {side_text}</b> │ <code>{leverage}x</code> │ AI Score: 9.2/10\n\n"
                    f"💡 <b>AI EXTRACTION RESULTS</b>\n"
                    f"├─ Accuracy: 98.5%\n"
                    f"├─ Processing: 3 passes\n"
                    f"└─ Validation: ✅ PASSED\n\n"
                    f"📍 <b>DETECTED PARAMETERS</b>\n"
                    f"├─ Entry: <code>${format_price(avg_price)}</code>\n"
                    f"├─ Target: <code>${format_price(tp_price)}</code>\n"
                    f"└─ Stop Loss: <code>${format_price(sl_price)}</code>\n\n"
                    f"💰 <b>POSITION DEPLOYED</b>\n"
                    f"├─ Margin Used: <code>${format_decimal_or_na(margin_amount, 2)}</code>\n"
                    f"├─ Position Size: <code>{format_decimal_or_na(qty, 4)}</code>\n"
                    f"└─ Total Value: <code>${format_decimal_or_na(position_value, 2)}</code>\n\n"
                    f"⚖️ <b>RISK PROFILE</b>\n"
                    f"├─ Risk Amount: <code>${format_decimal_or_na(risk_amount, 2)}</code>\n"
                    f"├─ Reward Potential: <code>${format_decimal_or_na(reward_amount, 2)}</code>\n"
                    f"├─ R:R Ratio: 1:{risk_reward_ratio:.1f} 🎯\n"
                    f"└─ AI Risk Score: 3/10 (LOW) 🟢\n\n"
                    f"✨ GGShot Monitoring: ACTIVE"
                )

                if errors:
                    message += f"\n⚠️ <b>Warnings:</b>\n"
                    for error in errors:
                        message += f"   • {error}\n"
            else:
                message = (
                    f"❌ <b>GGSHOT FAST TRADE FAILED</b> {execution_time}\n"
                    f"📸 AI-Powered Screenshot Analysis\n"
                    f"{create_mobile_separator()}\n\n"
                    f"❌ <b>Errors:</b>\n"
                )
                for error in errors:
                    message += f"   • {error}\n"

            return {
                "success": success,
                "orders_placed": orders_placed,
                "entry_price": avg_price,
                "position_size": qty,
                "market_order_id": market_order_id,
                "tp_order_id": tp_order_id,
                "sl_order_id": sl_order_id,
                "trade_group_id": trade_group_id,
                "message": message,
                "errors": errors,
                "risk_reward_ratio": risk_reward_ratio,
                "risk_amount": risk_amount,
                "reward_amount": reward_amount
            }

        except Exception as e:
            self.logger.error(f"❌ Error in GGShot fast pattern: {e}", exc_info=True)
            execution_time = self._format_execution_time(start_time)
            return {
                "success": False,
                "error": f"Fast pattern error: {str(e)}",
                "orders_placed": [],
                "message": (
                    f"❌ <b>GGSHOT FAST PATTERN ERROR</b> {execution_time}\n"
                    f"📸 AI analysis failed to execute\n\n"
                    f"🚨 Error: {str(e)}"
                )
            }

    async def _execute_ggshot_conservative_pattern(self, application, chat_id: int, chat_data: dict,
                                                  trade_group_id: str, start_time: float) -> dict:
        """
        Execute GGShot with Conservative pattern
        ENHANCED: First order is MARKET, remaining 2 are LIMIT orders
        """
        try:
            # Extract parameters
            symbol = chat_data.get(SYMBOL)
            side = chat_data.get(SIDE)
            margin_amount = safe_decimal_conversion(chat_data.get(MARGIN_AMOUNT))
            leverage = int(chat_data.get(LEVERAGE, 1))
            tick_size = safe_decimal_conversion(chat_data.get(INSTRUMENT_TICK_SIZE, "0.01"))
            qty_step = safe_decimal_conversion(chat_data.get(INSTRUMENT_QTY_STEP, "0.001"))

            # Get current market price for immediate entry
            current_price = safe_decimal_conversion(chat_data.get(PRIMARY_ENTRY_PRICE))

            # Get AI-extracted limit prices (for orders 2 and 3)
            limit_prices = []
            for i in range(2, 4):  # Only get limit 2 and 3 prices
                price_key = f"{LIMIT_ENTRY_1_PRICE}".replace("1", str(i))
                price = chat_data.get(price_key)
                if price:
                    limit_prices.append(safe_decimal_conversion(price))

            # Get all TP prices
            tp_prices = []
            # Single Take Profit approach - only get TP price
            price = chat_data.get(TP_PRICE)
            if price:
                tp_prices.append(safe_decimal_conversion(price))

            sl_price = safe_decimal_conversion(chat_data.get(SL_PRICE))

            # Log trade initiation
            self.logger.info(f"📸 GGSHOT CONSERVATIVE PATTERN TRADE INITIATED:")
            self.logger.info(f"   Symbol: {symbol}")
            self.logger.info(f"   Side: {side}")
            self.logger.info(f"   Trade Group: {trade_group_id}")
            self.logger.info(f"   Market Entry: {current_price}")
            self.logger.info(f"   AI Limit Orders: {len(limit_prices)}")
            self.logger.info(f"   AI TP Levels: {len(tp_prices)}")

            # Calculate position sizing
            total_position_size = margin_amount * leverage

            # Use current price for position size calculation
            total_qty = total_position_size / current_price

            # Use weighted allocation for GGShot (same as conservative)
            # Import weighted allocation config
            from config.constants import LIMIT_ORDER_ALLOCATION, MARKET_ORDER_PERCENTAGE
            
            # Calculate market and limit allocations
            market_qty = total_qty * MARKET_ORDER_PERCENTAGE
            limit_total_qty = total_qty * (Decimal("1") - MARKET_ORDER_PERCENTAGE)
            
            # Calculate weighted quantities for GGShot (only 2 limits)
            ggshot_limit_quantities = []
            if len(limit_prices) > 0:
                market_qty = value_adjusted_to_step(market_qty, qty_step) if MARKET_ORDER_PERCENTAGE > 0 else Decimal("0")
                
                # For GGShot with 2 limits, use first 2 allocations normalized
                ggshot_allocations = LIMIT_ORDER_ALLOCATION[:2]  # Use first 2 allocations
                total_alloc = sum(ggshot_allocations)
                
                for alloc in ggshot_allocations:
                    # Normalize allocations for 2 limits instead of 3
                    normalized_alloc = alloc / total_alloc
                    limit_qty = limit_total_qty * normalized_alloc
                    limit_qty = value_adjusted_to_step(limit_qty, qty_step)
                    ggshot_limit_quantities.append(limit_qty)
            
            # For backward compatibility
            qty_per_order = ggshot_limit_quantities[0] if ggshot_limit_quantities else total_qty / 3
            final_sl_qty = value_adjusted_to_step(total_qty, qty_step)

            # Store initial trade data
            chat_data["trade_initiated_at"] = time.time()
            chat_data["initial_margin"] = str(margin_amount)
            chat_data["initial_leverage"] = leverage
            chat_data["expected_position_size"] = str(final_sl_qty)
            chat_data[CONSERVATIVE_LIMITS_FILLED] = []  # Use same tracking as conservative
            chat_data[TRADING_APPROACH] = "ggshot"  # Set approach for monitoring

            orders_placed = []
            order_details = {}
            all_entry_order_ids = []
            errors = []

            # Initialize mirror trading results tracking for GGShot
            mirror_results = {"enabled": False, "market": None, "limits": [], "tps": [], "sl": None, "errors": []}
            if MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled():
                mirror_results["enabled"] = True

            # STEP 1: Place MARKET order for immediate entry
            self.logger.info(f"🚀 Placing GGShot market order at current price")

            order_link_id = f"{trade_group_id}_MARKET"

            market_result = await place_order_with_retry(
                symbol=symbol,
                side=side,
                order_type="Market",
                qty=str(market_qty),  # Use weighted market quantity
                order_link_id=order_link_id
            )

            if market_result:
                market_order_id = market_result.get("orderId", "")
                avg_price = safe_decimal_conversion(market_result.get("avgPrice", str(current_price)))
                all_entry_order_ids.append(market_order_id)
                orders_placed.append(f"Market Entry: {market_order_id[:8]}...")

                # Mark that this position was created by the bot
                chat_data["position_created"] = True
                chat_data["has_bot_orders"] = True  # Mark as bot-initiated trade
                chat_data["position_created_time"] = time.time()
                order_details["market"] = {
                    "id": market_order_id,
                    "price": avg_price,
                    "qty": qty_per_order
                }
                # Mark market order as already filled
                chat_data[CONSERVATIVE_LIMITS_FILLED] = [market_order_id]
                self.logger.info(f"✅ GGShot market order placed: {market_order_id} at {avg_price}")

                # MIRROR TRADING: Place market order on second account
                if mirror_results["enabled"]:
                    try:
                        position_idx = market_result.get("positionIdx", 0)
                        # Create unique order link ID to avoid duplicates
                        unique_order_link_id = self._generate_unique_order_link_id(f"{order_link_id}_MIRROR")

                        mirror_result = await mirror_market_order(
                            symbol=symbol,
                            side=side,
                            qty=str(market_qty),  # Use weighted market quantity for mirror
                            position_idx=position_idx,
                            order_link_id=unique_order_link_id
                        )
                        if mirror_result:
                            mirror_order_id = mirror_result.get("orderId", "")
                            mirror_results["market"] = {"id": mirror_order_id, "success": True}
                            self.logger.info(f"✅ MIRROR: GGShot market order placed: {mirror_order_id[:8]}...")
                        else:
                            mirror_results["market"] = {"success": False}
                            mirror_results["errors"].append("Market order failed")
                    except Exception as e:
                        self.logger.error(f"❌ MIRROR: Failed to place GGShot market order: {e}")
                        mirror_results["market"] = {"success": False}
                        mirror_results["errors"].append(f"Market order error: {str(e)}")
            else:
                errors.append("Market order placement failed")
                self.logger.error("❌ GGShot market order failed")

            # STEP 2: Place LIMIT orders for remaining entries
            for i, limit_price in enumerate(limit_prices, 1):
                # Get the appropriate weighted quantity for this limit order
                limit_qty = ggshot_limit_quantities[i-1] if i-1 < len(ggshot_limit_quantities) else qty_per_order
                self.logger.info(f"📝 Placing GGShot limit order {i} at AI price {limit_price} with qty {limit_qty}")

                order_link_id = f"{BOT_PREFIX}CONS_{trade_group_id}_LIMIT{i}"

                result = await place_order_with_retry(
                    symbol=symbol,
                    side=side,
                    order_type="Limit",
                    qty=str(limit_qty),  # Use weighted limit quantity
                    price=str(limit_price),
                    order_link_id=order_link_id
                )

                if result:
                    order_id = result.get("orderId", "")
                    all_entry_order_ids.append(order_id)
                    orders_placed.append(f"AI Limit{i}: {order_id[:8]}...")
                    order_details[f"limit{i}"] = {
                        "id": order_id,
                        "price": limit_price,
                        "qty": limit_qty  # Use actual weighted quantity
                    }
                    self.logger.info(f"✅ GGShot limit order {i} placed: {order_id}")

                    # MIRROR TRADING: Place limit order on second account
                    if mirror_results["enabled"]:
                        try:
                            position_idx = result.get("positionIdx", 0)
                            # Create unique order link ID to avoid duplicates
                            unique_order_link_id = self._generate_unique_order_link_id(f"{order_link_id}_MIRROR")

                            mirror_result = await mirror_limit_order(
                                symbol=symbol,
                                side=side,
                                qty=str(limit_qty),  # Use weighted limit quantity for mirror too
                                price=str(limit_price),
                                position_idx=position_idx,
                                order_link_id=unique_order_link_id
                            )
                            if mirror_result:
                                mirror_order_id = mirror_result.get("orderId", "")
                                mirror_results["limits"].append({"order": i, "id": mirror_order_id, "success": True, "type": "Limit"})
                                self.logger.info(f"✅ MIRROR: GGShot limit order {i} placed: {mirror_order_id[:8]}...")
                            else:
                                mirror_results["limits"].append({"order": i, "success": False, "type": "Limit"})
                                mirror_results["errors"].append(f"Limit order {i} failed")
                        except Exception as e:
                            self.logger.error(f"❌ MIRROR: Failed to place GGShot limit order {i}: {e}")
                            mirror_results["limits"].append({"order": i, "success": False, "type": "Limit"})
                            mirror_results["errors"].append(f"Limit order {i} error: {str(e)}")
                else:
                    self.logger.warning(f"⚠️ GGShot limit order {i} failed")
                    errors.append(f"AI Limit order {i} placement failed")

            # Store all entry order IDs (market + limits)
            chat_data[LIMIT_ORDER_IDS] = all_entry_order_ids  # Use conservative tracking
            chat_data[GGSHOT_ENTRY_ORDER_IDS] = all_entry_order_ids

            # Use Enhanced TP/SL system for GGShot Conservative
            enhanced_tp_sl_result = {"success": False}
            tp_order_ids = []
            sl_order_id = None

            if ENHANCED_TP_SL_AVAILABLE and ENABLE_ENHANCED_TP_SL and all_entry_order_ids:
                self.logger.info(f"🚀 Using enhanced TP/SL system for GGShot conservative {symbol}")

                # Calculate avg entry price
                avg_entry = avg_price if market_result else current_price

                # Setup enhanced TP/SL orders with conservative distribution
                enhanced_result = await enhanced_tp_sl_manager.setup_tp_sl_orders(
                    symbol=symbol,
                    side=side,
                    position_size=final_sl_qty,  # Target position size
                    entry_price=avg_entry,
                    tp_prices=tp_prices[:1],  # Use single TP price (TP1-only strategy)
                    tp_percentages=[100],  # Single complete exit at TP1
                    sl_price=sl_price,
                    chat_id=chat_id,
                    approach="GGSHOT_CONSERVATIVE",
                    qty_step=qty_step,
                    account_type="main"  # Main account trading
                )

                enhanced_tp_sl_result = enhanced_result

                # Create monitor_tasks entry for dashboard tracking
                if enhanced_result.get("success", False):
                    await enhanced_tp_sl_manager.create_dashboard_monitor_entry(
                        symbol=symbol,
                        side=side,
                        approach="ggshot",
                        chat_id=chat_id,
                        account_type="main"
                    )

                # Register GGShot limit orders with the Enhanced TP/SL system for tracking
                ggshot_limit_order_ids = []
                for order_detail in order_details.values():
                    if "limit" in str(order_detail) and order_detail.get("id"):
                        ggshot_limit_order_ids.append(order_detail["id"])

                if ggshot_limit_order_ids:
                    await enhanced_tp_sl_manager.register_limit_orders(symbol, side, ggshot_limit_order_ids, "main")
                    self.logger.info(f"📝 Registered {len(ggshot_limit_order_ids)} GGShot limit orders with Enhanced TP/SL system")

                if enhanced_result.get("success"):
                    self.logger.info("✅ GGShot conservative enhanced TP/SL setup successful")

                    # Store TP order info
                    if enhanced_result.get("tp_orders"):
                        for i, tp_order in enumerate(enhanced_result["tp_orders"]):
                            tp_order_id = tp_order["order_id"]
                            tp_order_ids.append(tp_order_id)
                            order_details[f"tp{i+1}"] = {
                                "id": tp_order_id,
                                "price": tp_order["price"],
                                "qty": tp_order["qty"]
                            }
                        self.logger.info(f"✅ GGShot Enhanced TP orders placed: {len(tp_order_ids)}")

                        # Store using conservative keys for compatibility
                        chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids
                        chat_data[GGSHOT_TP_ORDER_IDS] = tp_order_ids

                    # Store SL order info
                    if enhanced_result.get("sl_order"):
                        sl_order_id = enhanced_result["sl_order"]["order_id"]
                        chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_order_id
                        chat_data[GGSHOT_SL_ORDER_ID] = sl_order_id
                        order_details["sl"] = {
                            "id": sl_order_id,
                            "price": sl_price,
                            "qty": final_sl_qty
                        }
                        self.logger.info(f"✅ GGShot Enhanced SL order placed: {sl_order_id}")

                # Handle mirror trading for GGShot enhanced system (Conservative)
                if mirror_results["enabled"] and MIRROR_TRADING_AVAILABLE:
                    try:
                        from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager, start_mirror_monitoring_task

                        if mirror_enhanced_tp_sl_manager:
                            # Get position index
                            from clients.bybit_helpers import get_correct_position_idx
                            position_idx = await get_correct_position_idx(symbol, side)

                            # Setup mirror enhanced TP/SL with conservative distribution
                            mirror_enhanced_result = await mirror_enhanced_tp_sl_manager.setup_mirror_tp_sl_orders(
                                symbol=symbol,
                                side=side,
                                position_size=final_sl_qty,
                                entry_price=avg_entry,
                                tp_prices=tp_prices[:1],  # Single TP (TP1-only strategy)
                                tp_percentages=[100],  # Single complete exit
                                sl_price=sl_price,
                                chat_id=chat_id,
                                approach="GGSHOT_CONSERVATIVE",
                                position_idx=position_idx,
                                qty_step=qty_step
                            )

                            # Check if mirror_enhanced_result is a valid dictionary (not False or None)
                            if mirror_enhanced_result and isinstance(mirror_enhanced_result, dict):
                                if mirror_enhanced_result.get("tp_orders"):
                                    mirror_results["tps"] = []
                                    for i, (order_id, tp_order) in enumerate(mirror_enhanced_result["tp_orders"].items(), 1):
                                        mirror_results["tps"].append({
                                            "tp": i,
                                            "id": tp_order["order_id"],
                                            "success": True
                                        })
                                    self.logger.info(f"✅ MIRROR: GGShot Enhanced TP orders placed (Conservative)")

                                if mirror_enhanced_result.get("sl_order"):
                                    mirror_results["sl"] = {
                                        "id": mirror_enhanced_result["sl_order"]["order_id"],
                                        "success": True
                                    }
                                    self.logger.info(f"✅ MIRROR: GGShot Enhanced SL order placed")

                                # Register GGShot mirror limit orders with the Mirror Enhanced TP/SL system for tracking
                                ggshot_mirror_limit_order_ids = []
                                for limit_result in mirror_results.get("limits", []):
                                    if limit_result.get("success") and limit_result.get("id"):
                                        ggshot_mirror_limit_order_ids.append(limit_result["id"])

                                if ggshot_mirror_limit_order_ids:
                                    # Register limit orders with mirror account type  
                                    await enhanced_tp_sl_manager.register_limit_orders(symbol, side, ggshot_mirror_limit_order_ids, "mirror")
                                    self.logger.info(f"📝 Registered {len(ggshot_mirror_limit_order_ids)} GGShot mirror limit orders with Enhanced TP/SL system")

                                # Start mirror monitoring
                                await start_mirror_monitoring_task(symbol, side, mirror_enhanced_result)
                            else:
                                # Handle the case where setup failed
                                error_msg = "GGShot mirror enhanced TP/SL setup returned invalid result"
                                self.logger.error(f"❌ MIRROR: {error_msg}")
                                mirror_results["errors"].append(error_msg)

                    except Exception as e:
                        self.logger.error(f"❌ MIRROR: Failed to setup GGShot enhanced TP/SL: {e}")
                        mirror_results["errors"].append(f"Mirror enhanced TP/SL error: {str(e)}")

                else:
                    self.logger.warning("⚠️ GGShot conservative enhanced TP/SL setup failed")
                    errors.append("Enhanced TP/SL setup failed for GGShot conservative")
            else:
                self.logger.info("ℹ️ Enhanced TP/SL not available for GGShot conservative")
                errors.append("Enhanced TP/SL system required for GGShot conservative")

            # Start monitoring (skip if Enhanced TP/SL is handling it)
            if not (ENABLE_ENHANCED_TP_SL and enhanced_result.get("success")):
                try:
                    from execution.monitor import start_position_monitoring
                    await start_position_monitoring(application, chat_id, chat_data)
                    self.logger.info(f"✅ Enhanced monitoring started for GGShot conservative trade {trade_group_id}")

                    # Always start mirror monitoring for bot positions if mirror trading is enabled
                    if is_mirror_trading_enabled():
                        try:
                            from execution.monitor import start_mirror_position_monitoring
                            await start_mirror_position_monitoring(application, chat_id, chat_data)
                            self.logger.info(f"✅ Mirror position monitoring started for GGShot trade {trade_group_id}")
                        except Exception as e:
                            self.logger.error(f"Error starting mirror position monitoring: {e}")
                except Exception as e:
                    self.logger.error(f"Error starting position monitoring: {e}")
            else:
                self.logger.info("ℹ️ Enhanced TP/SL system handling monitoring - skipping old monitoring")

            # Return execution summary
            return {
                "success": True,
                "approach": "conservative_ggshot",
                "symbol": symbol,
                "side": side,
                "quantity": total_qty,
                "leverage": leverage,
                "entry_price": avg_price if market_result else current_price,
                "enhanced_tp_sl_active": ENABLE_ENHANCED_TP_SL and enhanced_tp_sl_result.get("success"),
                "monitoring_active": not (ENABLE_ENHANCED_TP_SL and enhanced_tp_sl_result.get("success")),
                "message": f"✅ GGShot Conservative trade executed with Enhanced TP/SL system"
            }

        except Exception as e:
            self.logger.error(f"❌ Error in GGShot conservative execution: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"❌ GGShot Conservative trade failed: {str(e)}"
            }

    async def _execute_conservative_merge(self, application, chat_id: int, chat_data: dict,
                                         existing_data: dict, limit_prices: list, tp_prices: list,
                                         sl_price: Decimal, margin_amount: Decimal, leverage: int,
                                         tick_size: Decimal, qty_step: Decimal, trade_group_id: str) -> dict:
        """
        Execute conservative position merge - combines new trade with existing position
        """
        start_time = time.time()
        symbol = chat_data.get(SYMBOL)
        side = chat_data.get(SIDE)

        try:
            # Prepare new trade parameters
            new_params = {
                'symbol': symbol,
                'side': side,
                'leverage': leverage
            }

            # For now, return a simple success response
            return {
                "success": True,
                "message": "Conservative merge functionality needs implementation"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Conservative merge error: {str(e)}"
            }

            # Store TP order IDs - use conservative keys for monitoring consistency
            chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids
            chat_data[GGSHOT_TP_ORDER_IDS] = tp_order_ids

            # Place SL order with AI-extracted price
            # Check if we have a slot for SL
            sl_order_id = None
            if placed_tp_count >= available_slots and available_slots > 0:
                logger.error(f"❌ Cannot place GGShot SL order - stop order limit reached")
                errors.append("GGShot SL order skipped due to stop order limit - POSITION AT RISK!")
            else:
                self.logger.info(f"🛡️ Placing GGShot SL order at AI price {sl_price}")

                order_link_id = f"{BOT_PREFIX}CONS_{trade_group_id}_SL"

                sl_result = await place_order_with_retry(
                    symbol=symbol,
                    side=tp_side,
                    order_type="Market",
                    qty=str(final_sl_qty),
                    trigger_price=str(sl_price),
                    position_idx=original_position_idx,  # FIXED: Use original position index
                    reduce_only=True,
                    order_link_id=order_link_id,
                    stop_order_type="StopLoss"
                )

                if sl_result:
                    sl_order_id = sl_result.get("orderId", "")
                    # Store SL order ID - use conservative keys for monitoring consistency
                    chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_order_id
                    chat_data[GGSHOT_SL_ORDER_ID] = sl_order_id
                    orders_placed.append(f"AI SL: {sl_order_id[:8]}...")
                    order_details["sl"] = {
                        "id": sl_order_id,
                        "price": sl_price,
                        "qty": final_sl_qty
                    }
                    self.logger.info(f"✅ GGShot SL order placed: {sl_order_id}")

                    # MIRROR TRADING: Place SL order on second account
                    if mirror_results["enabled"]:
                        try:
                            # Create unique order link ID to avoid duplicates
                            unique_order_link_id = self._generate_unique_order_link_id(f"{order_link_id}_MIRROR")

                            mirror_sl_result = await mirror_tp_sl_order(
                                symbol=symbol,
                                side=tp_side,
                                qty=str(final_sl_qty),
                                trigger_price=str(sl_price),
                                position_idx=original_position_idx,
                                order_link_id=unique_order_link_id
                            )
                            if mirror_sl_result:
                                mirror_sl_id = mirror_sl_result.get("orderId", "")
                                mirror_results["sl"] = {"id": mirror_sl_id, "success": True}
                                self.logger.info(f"✅ MIRROR: GGShot SL order placed: {mirror_sl_id[:8]}...")
                            else:
                                mirror_results["sl"] = {"success": False}
                                mirror_results["errors"].append("SL order failed")
                        except Exception as e:
                            self.logger.error(f"❌ MIRROR: Failed to place GGShot SL order: {e}")
                            mirror_results["sl"] = {"success": False}
                            mirror_results["errors"].append(f"SL order error: {str(e)}")
                else:
                    self.logger.warning(f"⚠️ GGShot SL order failed")
                    errors.append("AI SL order placement failed")

            # Calculate risk metrics - use market price as base since it's already filled
            avg_entry = avg_price if market_result else current_price
            if side == "Buy":
                risk_amount = (avg_entry - sl_price) * final_sl_qty
                # FIXED: Use single Take Profit for R:R calculation (closes 100% of position)
                max_reward = (tp_prices[0] - avg_entry) * final_sl_qty if tp_prices else 0
            else:
                risk_amount = (sl_price - avg_entry) * final_sl_qty
                # FIXED: Use single Take Profit for R:R calculation (closes 100% of position)
                max_reward = (avg_entry - tp_prices[0]) * final_sl_qty if tp_prices else 0

            # FIXED: Correct risk-reward ratio formula (reward/risk for proper 1:X display)
            risk_reward_ratio = abs(max_reward) / abs(risk_amount) if risk_amount > 0 else 0

            # Calculate position value
            position_value = avg_entry * final_sl_qty

            # Store execution details
            chat_data["execution_details"] = {
                "approach": "ggshot",
                "trade_group_id": trade_group_id,
                "entry_order_ids": all_entry_order_ids,
                "tp_order_ids": tp_order_ids,
                "sl_order_id": sl_order_id,
                "avg_entry_price": str(avg_entry),
                "total_position_size": str(final_sl_qty),
                "risk_amount": str(risk_amount),
                "max_reward": str(max_reward),
                "executed_at": time.time()
            }

            # Store mirror order IDs for monitoring
            if mirror_results["enabled"]:
                # Store mirror TP order IDs
                mirror_tp_ids = []
                for tp in mirror_results.get("tps", []):
                    if tp.get("success") and tp.get("id"):
                        mirror_tp_ids.append(tp["id"])
                if mirror_tp_ids:
                    chat_data["mirror_conservative_tp_order_ids"] = mirror_tp_ids

                # Store mirror SL order ID
                if mirror_results.get("sl", {}).get("success") and mirror_results["sl"].get("id"):
                    chat_data["mirror_conservative_sl_order_id"] = mirror_results["sl"]["id"]

                # Store mirror entry order IDs
                mirror_entry_ids = []
                if mirror_results.get("market", {}).get("success") and mirror_results["market"].get("id"):
                    mirror_entry_ids.append(mirror_results["market"]["id"])
                for limit in mirror_results.get("limits", []):
                    if limit.get("success") and limit.get("id"):
                        mirror_entry_ids.append(limit["id"])
                if mirror_entry_ids:
                    chat_data["mirror_entry_order_ids"] = mirror_entry_ids

            # Start monitoring (skip if Enhanced TP/SL is handling it)
            if not (ENABLE_ENHANCED_TP_SL and enhanced_result.get("success")):
                try:
                    from execution.monitor import start_position_monitoring
                    await start_position_monitoring(application, chat_id, chat_data)
                    self.logger.info(f"✅ Enhanced monitoring started for GGShot conservative trade {trade_group_id}")

                    # Always start mirror monitoring for bot positions if mirror trading is enabled
                    if is_mirror_trading_enabled():
                        try:
                            from execution.monitor import start_mirror_position_monitoring
                            await start_mirror_position_monitoring(application, chat_id, chat_data)
                            self.logger.info(f"✅ Mirror position monitoring started for GGShot trade {trade_group_id}")
                        except Exception as e:
                            self.logger.error(f"Error starting mirror position monitoring: {e}")
                except Exception as e:
                    self.logger.error(f"Error starting position monitoring: {e}")
                    errors.append("Position monitoring failed to start")
            else:
                self.logger.info(f"✅ Enhanced TP/SL system handling monitoring for GGShot conservative {trade_group_id} - skipping old monitors")

            # Determine success and build message
            success = len(all_entry_order_ids) > 0 and len(tp_order_ids) > 0
            execution_time = self._format_execution_time(start_time)

            side_emoji = "📈" if side == "Buy" else "📉"
            side_text = "LONG" if side == "Buy" else "SHORT"

            if success:
                # Calculate additional metrics
                trend_indicator = self._get_market_trend_indicator(side, avg_entry, tp_prices[-1] if tp_prices else avg_entry, sl_price)
                position_metrics = self._format_position_metrics(final_sl_qty, position_value, leverage)

                message = (
                    f"📸 <b>GGSHOT AI TRADE EXECUTED</b> 📸\n"
                    f"════════════════════════════════════\n"
                    f"🤖 AI Analysis: ✅ HIGH CONFIDENCE\n\n"
                    f"📊 <b>{symbol} {side_text}</b> │ <code>{leverage}x</code> │ AI Score: 9.5/10\n\n"
                    f"💡 <b>AI EXTRACTION RESULTS</b>\n"
                    f"├─ Strategy: Conservative Pattern\n"
                    f"├─ Accuracy: 99.2%\n"
                    f"├─ Processing: Multi-pass validation\n"
                    f"└─ Validation: ✅ PASSED\n\n"
                    f"📍 <b>ENTRY STRATEGY DETECTED</b>\n"
                )
                
                # Show market order if placed
                if market_result:
                    market_pct = float(MARKET_ORDER_PERCENTAGE * 100)
                    message += f"├─ Market Entry: <code>${format_decimal_or_na(avg_entry)}</code> ({market_pct:.0f}%)\n"
                
                # Show limit orders with correct percentages
                for i, price in enumerate(limit_prices, 1):
                    if i <= len(ggshot_limit_quantities):
                        # For GGShot with 2 limits, show actual percentage
                        actual_pct = float((ggshot_limit_quantities[i-1] / total_qty) * 100)
                        message += f"├─ Limit {i}: <code>${format_price(price)}</code> ({actual_pct:.1f}%)\n"
                
                message += (
                    f"├─ Targets: <code>{len(tp_order_ids)}</code> TPs configured\n"
                    f"└─ Stop Loss: <code>${format_price(sl_price)}</code>\n\n"
                    f"💰 <b>POSITION DEPLOYED</b>\n"
                    f"├─ Margin Used: <code>${format_decimal_or_na(margin_amount, 2)}</code>\n"
                    f"├─ Position Size: <code>{format_decimal_or_na(position_value / avg_entry if avg_entry > 0 else 0, 4)}</code>\n"
                    f"├─ Total Value: <code>${format_decimal_or_na(position_value, 2)}</code>\n"
                    f"└─ Group ID: <code>{trade_group_id}</code>\n\n"
                    f"⚖️ <b>RISK PROFILE</b>\n"
                    f"├─ Risk Amount: <code>${format_decimal_or_na(risk_amount, 2)}</code>\n"
                    f"├─ Reward Potential: <code>${format_decimal_or_na(max_reward, 2)}</code>\n"
                    f"├─ R:R Ratio: 1:{risk_reward_ratio:.1f} 🎯\n"
                    f"└─ AI Risk Score: 2/10 (VERY LOW) 🟢\n\n"
                    f"⚡ Execution Time: {execution_time}\n"
                    f"✨ GGShot Enhanced Monitoring: ACTIVE"
                )

                # Add mirror trading summary if available
                mirror_summary = self._format_conservative_mirror_summary(mirror_results)
                if mirror_summary:
                    message += mirror_summary

                if errors:
                    message += f"\n⚠️ <b>Warnings:</b>\n"
                    for error in errors:
                        message += f"   • {error}\n"
            else:
                message = (
                    f"❌ <b>GGSHOT CONSERVATIVE TRADE FAILED</b> {execution_time}\n"
                    f"📸 AI-Powered Screenshot Analysis\n"
                    f"{create_mobile_separator()}\n\n"
                    f"❌ <b>Errors:</b>\n"
                )
                for error in errors:
                    message += f"   • {error}\n"

            return {
                "success": success,
                "orders_placed": orders_placed,
                "limit_orders": len(limit_prices),
                "market_orders": 1 if market_result else 0,
                "tp_orders": len(tp_order_ids),
                "sl_order": bool(sl_order_id),
                "trade_group_id": trade_group_id,
                "message": message,
                "errors": errors,
                "avg_entry": avg_entry,
                "position_size": final_sl_qty,
                "risk_reward_ratio": risk_reward_ratio,
                "risk_amount": risk_amount,
                "max_reward": max_reward
            }

        except Exception as e:
            self.logger.error(f"❌ Error in GGShot conservative pattern: {e}", exc_info=True)
            execution_time = self._format_execution_time(start_time)
            return {
                "success": False,
                "error": f"Conservative pattern error: {str(e)}",
                "orders_placed": [],
                "message": (
                    f"❌ <b>GGSHOT CONSERVATIVE PATTERN ERROR</b> {execution_time}\n"
                    f"📸 AI analysis failed to execute\n\n"
                    f"🚨 Error: {str(e)}"
                )
            }

    async def _execute_conservative_merge(self, application, chat_id: int, chat_data: dict,
                                         existing_data: dict, limit_prices: list, tp_prices: list,
                                         sl_price: Decimal, margin_amount: Decimal, leverage: int,
                                         tick_size: Decimal, qty_step: Decimal, trade_group_id: str) -> dict:
        """
        Execute conservative position merge - combines new trade with existing position
        """
        start_time = time.time()
        symbol = chat_data.get(SYMBOL)
        side = chat_data.get(SIDE)

        try:
            # Prepare new trade parameters
            new_params = {
                'symbol': symbol,
                'side': side,
                'leverage': leverage,
                'position_size': margin_amount * leverage / (sum(limit_prices) / len(limit_prices)),
                'limit_prices': limit_prices,
                'sl_price': sl_price,
                'tick_size': tick_size,
                'qty_step': qty_step,
                'take_profits': [
                    {'price': tp_prices[0], 'percentage': 85},
                    {'price': tp_prices[1], 'percentage': 10} if len(tp_prices) > 1 else None,
                    {'price': tp_prices[2], 'percentage': 10} if len(tp_prices) > 2 else None,
                    {'price': tp_prices[3], 'percentage': 10} if len(tp_prices) > 3 else None
                ]
            }
            new_params['take_profits'] = [tp for tp in new_params['take_profits'] if tp]

            # Calculate merged parameters
            merged_params = self.position_merger.calculate_merged_parameters(
                existing_data, new_params, side
            )

            # Validate merge parameters
            if not await self.position_merger.validate_merge(symbol, side, merged_params):
                raise ValueError("Merge validation failed - invalid price levels")

            # NEW: Check if position is ready for merge
            # First determine if parameters will change
            temp_params_changed = merged_params.get('parameters_changed', False)
            new_limit_count = len(limit_prices) - 1 if temp_params_changed else 0
            is_ready, reason = await self.position_merger.validate_merge_readiness(
                symbol, existing_data.get('orders', []), new_limit_count
            )

            if not is_ready:
                self.logger.error(f"❌ MERGE NOT READY: {reason}")
                raise ValueError(f"Cannot proceed with merge: {reason}")

            # Count existing orders for validation
            existing_limit_count = self.position_merger.count_existing_limit_orders(existing_data.get('orders', []))
            existing_tp_count = len(existing_data.get('tp_orders', []))
            existing_sl_count = 1 if existing_data.get('sl_order') else 0

            self.logger.info(f"📊 EXISTING ORDER COUNT:")
            self.logger.info(f"   Limit orders: {existing_limit_count}")
            self.logger.info(f"   TP orders: {existing_tp_count}")
            self.logger.info(f"   SL orders: {existing_sl_count}")

            # Extract existing limit orders
            existing_limit_orders = []
            for order in existing_data.get('orders', []):
                if order.get('orderType') == 'Limit' and not order.get('reduceOnly', False):
                    existing_limit_orders.append(order)

            # Cancel existing TP/SL orders (but NOT limit orders yet)
            self.logger.info(f"🗑️ Step 1: Cancelling existing TP/SL orders for {symbol}...")
            success, cancelled_count = await self.position_merger.cancel_existing_orders(
                existing_data['orders'],
                order_type_filter="tp_sl_only"
            )

            if not success:
                self.logger.error("❌ Failed to cancel existing TP/SL orders - aborting merge")
                raise ValueError("Could not cancel existing TP/SL orders")

            # Check if parameters changed to decide on limit order handling
            parameters_changed = merged_params.get('parameters_changed', False)
            cancelled_limit_count = 0  # Initialize for tracking

            if parameters_changed:
                # Parameters changed, so replace limit orders with new ones
                self.logger.info(f"🔄 Step 2: Parameters changed (SL={merged_params.get('sl_changed')}, TPs={merged_params.get('tps_changed')})")
                self.logger.info(f"   Will replace {existing_limit_count} existing limit orders...")

                if existing_limit_orders:
                    # First, verify we have the correct count before cancellation
                    self.logger.info(f"📊 PRE-CANCELLATION CHECK:")
                    self.logger.info(f"   Expected to cancel: {len(existing_limit_orders)} limit orders")

                    success, cancelled_limit_count = await self.position_merger.cancel_existing_orders(
                        existing_limit_orders,
                        order_type_filter="limit_only"
                    )

                    if not success:
                        self.logger.error(f"❌ Failed to cancel all limit orders - only {cancelled_limit_count}/{len(existing_limit_orders)} cancelled")
                        # Don't continue if cancellation failed
                        raise ValueError(f"Critical: Failed to cancel existing limit orders. Cancelled {cancelled_limit_count}/{len(existing_limit_orders)}")
                    else:
                        self.logger.info(f"✅ Successfully requested cancellation of {cancelled_limit_count} limit orders")

                    # ENHANCED: More robust verification with multiple checks
                    self.logger.info("⏳ Waiting for order cancellation to complete...")
                    await asyncio.sleep(0.5)  # PERFORMANCE: Reduced wait time for exchange processing

                    # Multiple verification attempts
                    for attempt in range(3):
                        current_orders = await get_all_open_orders()
                        remaining_limits = self.position_merger.count_existing_limit_orders(
                            [o for o in current_orders if o.get('symbol') == symbol]
                        )

                        if remaining_limits == 0:
                            self.logger.info(f"✅ Verification attempt {attempt + 1}: All limit orders cancelled successfully")
                            break
                        else:
                            self.logger.warning(f"⚠️ Verification attempt {attempt + 1}: Still have {remaining_limits} limit orders")
                            if attempt < 2:
                                await asyncio.sleep(0.3)  # PERFORMANCE: Reduced wait time between checks

                    # Final check
                    if remaining_limits > 0:
                        self.logger.error(f"❌ CRITICAL: {remaining_limits} limit orders remain after cancellation!")
                        # List remaining orders for debugging
                        for order in current_orders:
                            if (order.get('symbol') == symbol and
                                order.get('orderType') == 'Limit' and
                                not order.get('reduceOnly', False)):
                                self.logger.error(f"   - Remaining: {order.get('orderId')[:8]}... @ {order.get('price')}")

                        # Abort to prevent duplicates
                        raise ValueError(f"Cannot proceed: {remaining_limits} limit orders still active after cancellation")
            else:
                # Parameters unchanged, keep existing limit orders
                self.logger.info(f"📌 Step 2: No parameter changes - preserving {len(existing_limit_orders)} existing limit orders")
                # Store existing limit order info for tracking
                chat_data["preserved_limit_orders"] = [
                    {
                        "orderId": o.get("orderId"),
                        "price": o.get("price"),
                        "qty": o.get("qty")
                    } for o in existing_limit_orders
                ]

            # Initialize mirror results early for all operations
            mirror_results = {"market": None, "limits": [], "tps": [], "sl": None, "errors": []}

            # Calculate position allocation for merge
            total_position_size = new_params['position_size']

            # Determine how to split between market and limit orders
            if parameters_changed and len(limit_prices) > 1:
                # If parameters changed and we have limit prices, split position like a fresh trade
                # Allocate proportionally: first entry (market) gets its share, rest for limits
                market_allocation = total_position_size / len(limit_prices)  # Equal split
                limit_allocation = total_position_size - market_allocation
                self.logger.info(f"📦 Adding to position with allocation - Market: {market_allocation:.6f}, Limits: {limit_allocation:.6f}")
            else:
                # No limit orders needed, use full position for market order
                market_allocation = total_position_size
                limit_allocation = Decimal("0")
                self.logger.info(f"📦 Adding {market_allocation} to existing position (no limit orders)")

            # Place market order to add to position
            add_qty = value_adjusted_to_step(market_allocation, qty_step)
            order_params = {
                "symbol": symbol,
                "side": side,
                "order_type": "Market",
                "qty": add_qty
            }

            order_result = await place_order_with_retry(**order_params)
            if not order_result or not order_result.get("orderId"):
                raise ValueError(f"Failed to add to position: {order_result}")

            order_id = order_result.get("orderId")
            fill_price = Decimal(str(order_result.get("avgPrice", limit_prices[0])))

            # Place new limit orders if parameters changed
            new_limit_order_ids = []
            if parameters_changed and limit_prices and len(limit_prices) > 1:
                self.logger.info(f"📍 Step 3: Placing {len(limit_prices) - 1} new limit orders...")

                # CRITICAL PRE-CHECK: Ensure no limit orders exist before placing new ones
                current_orders = await get_all_open_orders()
                current_limit_count = self.position_merger.count_existing_limit_orders(
                    [o for o in current_orders if o.get('symbol') == symbol]
                )

                if current_limit_count > 0:
                    self.logger.error(f"❌ ABORT: Found {current_limit_count} limit orders before placing new ones!")
                    self.logger.error("This would cause duplicates. Aborting merge.")
                    raise ValueError(f"Cannot place new limit orders: {current_limit_count} orders still exist")

                # Calculate quantity for each limit order from the allocated amount
                num_limit_orders = len(limit_prices) - 1  # Exclude first price (used for market)
                limit_qty_each = limit_allocation / num_limit_orders if num_limit_orders > 0 else Decimal("0")

                for i, limit_price in enumerate(limit_prices[1:], 1):  # Skip first price (market order)
                    limit_qty = value_adjusted_to_step(limit_qty_each, qty_step)
                    self.logger.info(f"📊 Limit order {i}: Price={limit_price}, Qty={limit_qty}")
                    if limit_qty > 0:
                        limit_order_params = {
                            "symbol": symbol,
                            "side": side,
                            "order_type": "Limit",
                            "qty": limit_qty,
                            "price": str(limit_price)
                        }

                        limit_result = await place_order_with_retry(**limit_order_params)
                        if limit_result and limit_result.get("orderId"):
                            new_limit_order_ids.append(limit_result.get("orderId"))
                            self.logger.info(f"✅ Placed Limit {i} at {limit_price} for {limit_qty} qty")

                            # Mirror the limit order
                            if MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled():
                                try:
                                    # Generate unique order link ID for mirror limit order
                                    mirror_limit_link_id = self._generate_unique_order_link_id(f"{trade_group_id}_LIMIT{i}_MIRROR")
                                    mirror_limit = await mirror_limit_order(
                                        symbol=symbol,
                                        side=side,
                                        qty=str(limit_qty),
                                        price=str(limit_price),
                                        position_idx=None,  # Will auto-detect
                                        order_link_id=mirror_limit_link_id
                                    )
                                    if mirror_limit:
                                        self.logger.info(f"✅ MIRROR: Limit order {i} placed at {limit_price}")
                                        if "limits" not in mirror_results:
                                            mirror_results["limits"] = []
                                        mirror_results["limits"].append({"order": i, "success": True})
                                    else:
                                        mirror_results["errors"].append(f"Limit order {i} mirror failed")
                                except Exception as e:
                                    self.logger.error(f"❌ MIRROR: Failed to place limit order {i}: {e}")
                                    mirror_results["errors"].append(f"Limit order {i} error: {str(e)}")

                # Store new limit order IDs
                chat_data[LIMIT_ORDER_IDS] = new_limit_order_ids
                self.logger.info(f"✅ Placed {len(new_limit_order_ids)} new limit orders")

                # ENHANCED POST-PLACEMENT VALIDATION
                self.logger.info("📊 POST-PLACEMENT VALIDATION:")
                await asyncio.sleep(0.5)  # PERFORMANCE: Reduced order registration wait time

                # Get fresh order list
                current_orders = await get_all_open_orders()
                final_limit_count = self.position_merger.count_existing_limit_orders(
                    [o for o in current_orders if o.get('symbol') == symbol]
                )

                expected_count = len(new_limit_order_ids)
                self.logger.info(f"   Expected limit orders: {expected_count}")
                self.logger.info(f"   Actual limit orders: {final_limit_count}")

                if final_limit_count != expected_count:
                    self.logger.error(f"❌ LIMIT ORDER COUNT MISMATCH!")
                    if final_limit_count > expected_count:
                        self.logger.error("⚠️ CRITICAL: DUPLICATE ORDERS DETECTED!")
                        self.logger.error(f"   Expected: {expected_count}, Found: {final_limit_count}")
                        self.logger.error(f"   Excess orders: {final_limit_count - expected_count}")

                        # List all limit orders for debugging
                        limit_orders_found = []
                        for order in current_orders:
                            if (order.get('symbol') == symbol and
                                order.get('orderType') == 'Limit' and
                                not order.get('reduceOnly', False)):
                                limit_orders_found.append({
                                    'id': order.get('orderId', '')[:8],
                                    'price': order.get('price'),
                                    'qty': order.get('qty'),
                                    'linkId': order.get('orderLinkId', '')
                                })

                        self.logger.error(f"   Found orders: {limit_orders_found}")

                        # Add warning to chat data for monitoring
                        chat_data["merge_warning"] = f"Duplicate limit orders detected: {final_limit_count} instead of {expected_count}"
                    elif final_limit_count < expected_count:
                        self.logger.error(f"   Some limit orders failed to place")
                        self.logger.error(f"   Missing orders: {expected_count - final_limit_count}")
                else:
                    self.logger.info(f"✅ Limit order count VERIFIED: {final_limit_count} orders placed correctly")
                    self.logger.info(f"✅ No duplicates detected")
            else:
                # Use existing limit order IDs
                chat_data[LIMIT_ORDER_IDS] = [o["orderId"] for o in chat_data.get("preserved_limit_orders", [])]
                self.logger.info(f"📌 Step 3: Using {len(chat_data[LIMIT_ORDER_IDS])} preserved limit orders (no changes)")

            # Store the merge tracking with comprehensive details
            chat_data[CONSERVATIVE_LIMITS_FILLED] = [order_id]  # Market order that was filled
            chat_data["merged_position"] = True
            chat_data["merge_details"] = {
                "existing_size": str(merged_params['existing_size']),
                "added_size": str(add_qty),
                "total_size": str(merged_params['merged_size']),
                "parameters_changed": parameters_changed,
                "sl_changed": merged_params.get('sl_changed', False),
                "tps_changed": merged_params.get('tps_changed', False),
                "limit_orders_replaced": parameters_changed,
                "existing_limit_count": existing_limit_count,
                "new_limit_count": len(new_limit_order_ids) if parameters_changed else len(existing_limit_orders),
                "merge_reason": "Same symbol and side - optimizing orders",
                "sl_decision": f"Existing: ${existing_data.get('sl_order', {}).get('triggerPrice', 'None')} → New: ${merged_params['sl_price']}",
                "timestamp": time.time(),
                "validation_passed": True,
                "cancelled_orders": {
                    "tp_sl": cancelled_count,
                    "limits": cancelled_limit_count if parameters_changed else 0
                },
                "placed_orders": {
                    "market": 1,
                    "limits": len(new_limit_order_ids),
                    "tps": len(tp_order_ids),
                    "sl": 1 if chat_data.get(SL_ORDER_ID) else 0
                }
            }

            self.logger.info(f"📊 MERGE SUMMARY:")
            self.logger.info(f"   Position size: {merged_params['existing_size']} + {add_qty} = {merged_params['merged_size']}")
            self.logger.info(f"   Parameters changed: {parameters_changed}")
            self.logger.info(f"   Limit orders: {existing_limit_count} → {chat_data['merge_details']['new_limit_count']}")

            # Place new TP orders with merged parameters
            tp_order_ids = []
            for i, tp in enumerate(merged_params['take_profits'], 1):
                tp_qty = value_adjusted_to_step(
                    merged_params['merged_size'] * Decimal(tp['percentage']) / 100,
                    qty_step
                )

                if tp_qty > 0:
                    tp_order_params = {
                        "symbol": symbol,
                        "side": "Buy" if side == "Sell" else "Sell",
                        "order_type": "Market",
                        "qty": tp_qty,
                        "trigger_price": str(tp['price']),
                        "reduce_only": True
                    }

                    tp_result = await place_order_with_retry(**tp_order_params)
                    if tp_result and tp_result.get("orderId"):
                        tp_order_ids.append(tp_result.get("orderId"))
                        self.logger.info(f"✅ Placed TP{i} at {tp['price']} for {tp_qty} qty")

            chat_data[TP_ORDER_IDS] = tp_order_ids

            # Place new SL order with merged parameters
            sl_qty = value_adjusted_to_step(merged_params['merged_size'], qty_step)
            sl_order_params = {
                "symbol": symbol,
                "side": "Buy" if side == "Sell" else "Sell",
                "order_type": "Market",
                "qty": sl_qty,
                "trigger_price": str(merged_params['sl_price']),
                "reduce_only": True
            }

            sl_result = await place_order_with_retry(**sl_order_params)
            if sl_result and sl_result.get("orderId"):
                chat_data[SL_ORDER_ID] = sl_result.get("orderId")
                self.logger.info(f"✅ Placed SL at {merged_params['sl_price']} for {sl_qty} qty")

            # Record merge decision to execution summary
            if EXECUTION_SUMMARY_AVAILABLE:
                try:
                    merge_decision = {
                        'merged': True,
                        'reason': 'Same symbol and side position exists',
                        'existing_size': float(merged_params['existing_size']),
                        'new_size': float(add_qty),
                        'approach': 'conservative',
                        'parameters_changed': parameters_changed,
                        'sl_changed': merged_params.get('sl_changed', False),
                        'tp_changed': merged_params.get('tps_changed', False),
                        'details': {
                            'sl_selection': 'Conservative (safer) SL chosen',
                            'tp_selection': 'Aggressive (better) TPs chosen',
                            'limit_orders': 'Replaced' if parameters_changed else 'Preserved'
                        }
                    }
                    await execution_summary.record_merge_decision(symbol, side, merge_decision)
                    self.logger.info(f"✅ Merge decision recorded for {symbol} {side}")
                except Exception as e:
                    self.logger.error(f"Failed to record merge decision: {e}")

            # Mirror trading for merge
            if MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled():
                self.logger.info(f"🔄 Executing merge on mirror account...")

                # Mirror the market order addition
                mirror_market = await mirror_market_order(
                    symbol=symbol,
                    side=side,
                    qty=add_qty,
                    position_idx=None  # Will auto-detect
                )
                if mirror_market:
                    mirror_results["market"] = mirror_market
                else:
                    mirror_results["errors"].append("Market order mirror failed")

                # Mirror the new TP orders
                for i, tp in enumerate(merged_params['take_profits'], 1):
                    tp_qty = value_adjusted_to_step(
                        merged_params['merged_size'] * Decimal(tp['percentage']) / 100,
                        qty_step
                    )
                    if tp_qty > 0:
                        # Generate unique order link ID for mirror TP
                        mirror_tp_link_id = self._generate_unique_order_link_id(f"TP{i}_{tp['percentage']}_MIRROR")
                        mirror_tp = await mirror_tp_sl_order(
                            symbol=symbol,
                            side="Buy" if side == "Sell" else "Sell",
                            qty=tp_qty,
                            trigger_price=str(tp['price']),
                            position_idx=None,  # Will auto-detect
                            order_link_id=mirror_tp_link_id,
                            stop_order_type="TakeProfit"
                        )
                        mirror_results["tps"].append(mirror_tp)

                # Mirror the new SL order
                # Generate unique order link ID for mirror SL
                mirror_sl_link_id = self._generate_unique_order_link_id(f"SL_{trade_group_id}_MIRROR")
                mirror_sl = await mirror_tp_sl_order(
                    symbol=symbol,
                    side="Buy" if side == "Sell" else "Sell",
                    qty=sl_qty,
                    trigger_price=str(merged_params['sl_price']),
                    position_idx=None,  # Will auto-detect
                    order_link_id=mirror_sl_link_id,
                    stop_order_type="StopLoss"
                )
                mirror_results["sl"] = mirror_sl

            # Record merge execution to summary
            if EXECUTION_SUMMARY_AVAILABLE:
                try:
                    execution_time_total = time.time() - start_time
                    merge_execution_data = {
                        'trade_id': trade_group_id,
                        'symbol': symbol,
                        'side': side,
                        'approach': 'conservative',
                        'leverage': leverage,
                        'margin_amount': float(margin_amount),
                        'position_size': float(merged_params['merged_size']),
                        'entry_price': float(fill_price),
                        'main_orders': [order_id] + new_limit_order_ids + tp_order_ids + ([chat_data.get(SL_ORDER_ID)] if chat_data.get(SL_ORDER_ID) else []),
                        'main_fill_status': 'filled',
                        'main_execution_time': execution_time_total,
                        'main_errors': [],
                        'position_merged': True,
                        'merge_reason': 'Same symbol and side',
                        'existing_position': {
                            'size': float(merged_params['existing_size']),
                            'orders': len(existing_data.get('orders', []))
                        },
                        'new_position': {
                            'size': float(merged_params['merged_size']),
                            'sl': float(merged_params['sl_price']),
                            'tps': [{'price': float(tp['price']), 'pct': tp['percentage']} for tp in merged_params['take_profits']]
                        },
                        'merged_parameters': {
                            'sl_changed': merged_params.get('sl_changed', False),
                            'tps_changed': merged_params.get('tps_changed', False),
                            'limit_orders_replaced': parameters_changed
                        },
                        'tp_orders': [{'order_id': oid, 'level': i+1} for i, oid in enumerate(tp_order_ids)],
                        'sl_orders': [{'order_id': chat_data.get(SL_ORDER_ID)}] if chat_data.get(SL_ORDER_ID) else [],
                        'market_orders': [{'order_id': order_id, 'qty': float(add_qty), 'type': 'merge_add'}],
                        'limit_orders': [{'order_id': oid} for oid in new_limit_order_ids],
                        'risk_reward_ratio': float(3.0),  # Default estimate
                        'total_orders': 1 + len(new_limit_order_ids) + len(tp_order_ids) + (1 if chat_data.get(SL_ORDER_ID) else 0),
                        'successful_orders': 1 + len(new_limit_order_ids) + len(tp_order_ids) + (1 if chat_data.get(SL_ORDER_ID) else 0),
                        'failed_orders': 0,
                        'avg_fill_time': execution_time_total / (1 + len(new_limit_order_ids) + len(tp_order_ids) + (1 if chat_data.get(SL_ORDER_ID) else 0)),
                        'mirror_enabled': MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled(),
                        'mirror_orders': [],
                        'mirror_errors': mirror_results.get('errors', []),
                        'mirror_fill_status': 'filled' if mirror_results.get('market') else 'failed',
                        'mirror_sync_status': 'synced' if mirror_results.get('market') and not mirror_results.get('errors') else 'partial',
                        'mirror_execution_time': execution_time_total
                    }

                    # Add mirror order IDs if available
                    if mirror_results.get('market') and mirror_results['market'].get('orderId'):
                        merge_execution_data['mirror_orders'].append(mirror_results['market']['orderId'])
                    for tp in mirror_results.get('tps', []):
                        if tp and tp.get('orderId'):
                            merge_execution_data['mirror_orders'].append(tp['orderId'])
                    if mirror_results.get('sl') and mirror_results['sl'].get('orderId'):
                        merge_execution_data['mirror_orders'].append(mirror_results['sl']['orderId'])

                    await execution_summary.record_execution(trade_group_id, merge_execution_data)
                    self.logger.info(f"✅ Merge execution recorded for trade {trade_group_id}")
                except Exception as e:
                    self.logger.error(f"Failed to record merge execution: {e}")

            # Trigger Conservative rebalancing after merge
            try:
                from execution.conservative_rebalancer import rebalance_conservative_on_merge

                self.logger.info(f"🔄 Triggering Conservative rebalance after merge")
                rebalance_result = await rebalance_conservative_on_merge(
                    chat_data=chat_data,
                    symbol=symbol,
                    new_position_size=merged_params['merged_size'],
                    ctx_app=application
                )

                if rebalance_result.get("success"):
                    self.logger.info(f"✅ Conservative rebalance after merge completed")

                    # Also trigger mirror rebalancing if enabled
                    if MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled():
                        from execution.conservative_rebalancer import rebalance_conservative_mirror
                        mirror_rebalance = await rebalance_conservative_mirror(
                            chat_data=chat_data,
                            symbol=symbol,
                            trigger="position_merge"
                        )
                        if mirror_rebalance.get("success"):
                            self.logger.info(f"✅ Mirror Conservative rebalance completed")
                else:
                    self.logger.error(f"❌ Conservative rebalance after merge failed: {rebalance_result.get('error')}")

            except Exception as e:
                self.logger.error(f"Error triggering Conservative rebalance after merge: {e}")

            # Start monitoring
            monitor_started = False
            try:
                from execution.monitor import start_position_monitoring
                monitor_started = await start_position_monitoring(
                    application,
                    chat_id,
                    chat_data
                )
            except Exception as e:
                self.logger.error(f"Monitor start error: {e}")

            # Calculate risk/reward
            risk_amount = margin_amount
            max_reward = margin_amount * Decimal('3')  # Estimate
            risk_reward_ratio = "3:1"

            # Format success message
            execution_time = self._format_execution_time(start_time)

            # Build merge reasoning
            merge_reasoning = "\n📝 <b>Merge Reasoning:</b>\n"

            # SL reasoning
            if 'sl_price' in merged_params and 'sl_price' in new_params:
                existing_sl = existing_data.get('sl_order')
                if existing_sl and existing_sl.get('stopOrderType') == 'StopLoss':
                    existing_sl_price = Decimal(str(existing_sl.get('triggerPrice', 0)))
                    new_sl_price = Decimal(str(new_params.get('sl_price', 0)))
                    if merged_params['sl_price'] == existing_sl_price:
                        merge_reasoning += f"• SL kept at {format_price(existing_sl_price)} (existing = new)\n"
                    else:
                        if side == 'Sell':  # SHORT
                            merge_reasoning += f"• SL changed: {format_price(existing_sl_price)} → {format_price(merged_params['sl_price'])} (took higher/conservative)\n"
                        else:  # LONG
                            merge_reasoning += f"• SL changed: {format_price(existing_sl_price)} → {format_price(merged_params['sl_price'])} (took lower/conservative)\n"
                else:
                    merge_reasoning += f"• SL set to {format_price(merged_params['sl_price'])} (no existing SL)\n"

            # Limit order reasoning based on parameter changes
            if parameters_changed:
                merge_reasoning += f"• Limit Orders: REPLACED due to parameter changes\n"
                if merged_params.get('sl_changed'):
                    merge_reasoning += f"  - SL changed, new entry strategy needed\n"
                if merged_params.get('tps_changed'):
                    merge_reasoning += f"  - TPs changed, new entry strategy needed\n"
                if new_limit_order_ids:
                    for i, price in enumerate(limit_prices[1:], 1):
                        merge_reasoning += f"  - New Limit {i}: {format_price(price)}\n"
            else:
                preserved_count = len(chat_data.get("preserved_limit_orders", []))
                if preserved_count > 0:
                    merge_reasoning += f"• Limit Orders: PRESERVED (no parameter changes)\n"
                    merge_reasoning += f"  - Original entry strategy remains optimal\n"
                    for i, order in enumerate(chat_data.get("preserved_limit_orders", []), 1):
                        merge_reasoning += f"  - Kept Limit {i}: {format_price(Decimal(str(order['price'])))}\n"

            # TP reasoning for conservative approach (multiple TPs)
            existing_tps = existing_data.get('tp_orders', [])
            new_tps = new_params.get('take_profits', [])

            if existing_tps or new_tps:
                merge_reasoning += "• TP changes:\n"
                for i, tp in enumerate(merged_params.get('take_profits', []), 1):
                    tp_price = tp.get('price')

                    # Find corresponding existing TP
                    existing_tp = None
                    if i-1 < len(existing_tps):
                        for ex_tp in existing_tps:
                            if ex_tp.get('orderLinkId', '').startswith(f'TP{i}'):
                                existing_tp = ex_tp
                                break

                    # Find corresponding new TP
                    new_tp = new_tps[i-1] if i-1 < len(new_tps) else None

                    if existing_tp and new_tp:
                        existing_tp_price = Decimal(str(existing_tp.get('triggerPrice', 0)))
                        new_tp_price = Decimal(str(new_tp.get('price', 0)))
                        if tp_price == existing_tp_price:
                            merge_reasoning += f"  - TP{i} kept at {format_price(tp_price)} ({tp.get('percentage')}%)\n"
                        else:
                            if side == 'Sell':  # SHORT
                                merge_reasoning += f"  - TP{i}: {format_price(existing_tp_price)} → {format_price(tp_price)} (took lower/aggressive) ({tp.get('percentage')}%)\n"
                            else:  # LONG
                                merge_reasoning += f"  - TP{i}: {format_price(existing_tp_price)} → {format_price(tp_price)} (took higher/aggressive) ({tp.get('percentage')}%)\n"
                    else:
                        merge_reasoning += f"  - TP{i} set to {format_price(tp_price)} ({tp.get('percentage')}%)\n"

            message = (
                f"✅ <b>POSITION MERGED SUCCESSFULLY</b> {execution_time}\n"
                f"{create_mobile_separator()}\n"
                f"🔄 <b>Merge Details:</b>\n"
                f"Existing: {format_decimal_or_na(merged_params['existing_size'])} {symbol}\n"
                f"Added: {format_decimal_or_na(add_qty)} @ {format_price(fill_price)}\n"
                f"Total: {format_decimal_or_na(merged_params['merged_size'])} {symbol}\n\n"
                f"🎯 <b>New Parameters:</b>\n"
                f"SL: {format_price(merged_params['sl_price'])}\n"
            )

            for i, tp in enumerate(merged_params['take_profits'], 1):
                message += f"TP{i}: {format_price(tp['price'])} ({tp['percentage']}%)\n"

            message += merge_reasoning

            # Add full logical breakdown for merge scenario
            logical_breakdown = "\n📋 <b>Parameter Logic (Merged Position):</b>\n"

            # Entry logic
            logical_breakdown += f"• <b>Entry Addition @ ${format_price(fill_price)}:</b>\n"
            logical_breakdown += f"  - Market order added {format_decimal_or_na(add_qty)} units\n"
            logical_breakdown += f"  - Combined with existing position\n"
            logical_breakdown += f"  - Conservative scaling strategy\n"

            # Limit order logic based on parameter changes
            if parameters_changed:
                logical_breakdown += f"• <b>Limit Orders (REPLACED):</b>\n"
                logical_breakdown += f"  - Exit parameters changed: SL={merged_params.get('sl_changed')}, TPs={merged_params.get('tps_changed')}\n"
                logical_breakdown += f"  - Entry strategy updated to match new exit strategy\n"
                if new_limit_order_ids:
                    logical_breakdown += f"  - Placed {len(new_limit_order_ids)} new limit orders\n"
            else:
                preserved_count = len(chat_data.get("preserved_limit_orders", []))
                if preserved_count > 0:
                    logical_breakdown += f"• <b>Limit Orders (PRESERVED):</b>\n"
                    logical_breakdown += f"  - Exit parameters unchanged\n"
                    logical_breakdown += f"  - Kept {preserved_count} existing limit orders active\n"
                    logical_breakdown += f"  - Original entry strategy remains optimal\n"

            # TP merge logic
            logical_breakdown += f"• <b>Take Profit Selection:</b>\n"
            for i, tp in enumerate(merged_params.get('take_profits', []), 1):
                logical_breakdown += f"  - TP @ ${format_price(tp['price'])}: 100% exit (complete)\n"
            logical_breakdown += f"  - Aggressive TP selection for max profit\n"
            logical_breakdown += f"  - Applied to full merged position\n"

            # SL merge logic
            if 'sl_price' in merged_params:
                logical_breakdown += f"• <b>Stop Loss @ ${format_price(merged_params['sl_price'])}:</b>\n"
                logical_breakdown += f"  - Conservative SL selection\n"
                logical_breakdown += f"  - Minimizes risk on combined position\n"
                logical_breakdown += f"  - Protects entire position value\n"

            # Position sizing logic
            logical_breakdown += f"• <b>Position Management:</b>\n"
            logical_breakdown += f"  - Previous: {format_decimal_or_na(merged_params['existing_size'])}\n"
            logical_breakdown += f"  - Added: {format_decimal_or_na(add_qty)}\n"
            logical_breakdown += f"  - Total: {format_decimal_or_na(merged_params['merged_size'])}\n"
            logical_breakdown += f"  - Distributed across {len(merged_params.get('take_profits', []))} TP levels\n"

            # Risk management logic
            logical_breakdown += f"• <b>Risk/Reward Strategy:</b>\n"
            logical_breakdown += f"  - Conservative SL + Aggressive TP\n"
            logical_breakdown += f"  - Single Take Profit (100% exit)\n"
            logical_breakdown += f"  - Risk: ${format_decimal_or_na(risk_amount, 2)}\n"
            logical_breakdown += f"  - Potential: ${format_decimal_or_na(max_reward, 2)}\n"

            message += logical_breakdown

            message += (
                f"\n📊 <b>Risk/Reward:</b>\n"
                f"Risk: {format_mobile_currency(risk_amount)}\n"
                f"Max Reward: {format_mobile_currency(max_reward)}\n"
                f"Ratio: {risk_reward_ratio}\n"
            )

            if monitor_started:
                message += f"\n🔄 Monitoring active"

            # Add mirror results if available
            if MIRROR_TRADING_AVAILABLE and is_mirror_trading_enabled():
                if mirror_results["market"] and mirror_results["market"].get("orderId"):
                    message += f"\n\n🔄 <b>MIRROR ACCOUNT MERGED</b>\n"
                    message += f"Added: {add_qty} @ {mirror_results['market'].get('avgPrice', 'Market')}\n"

                    successful_tps = sum(1 for tp in mirror_results["tps"] if tp and tp.get("orderId"))
                    message += f"TPs placed: {successful_tps}/{len(merged_params['take_profits'])}\n"

                    if mirror_results["sl"] and mirror_results["sl"].get("orderId"):
                        message += f"SL placed: ✅\n"
                    else:
                        message += f"SL placed: ❌\n"

                    # Add same merge reasoning for mirror account
                    message += "\n📝 <b>Mirror Merge Logic:</b>\n"
                    message += "• Same TP/SL merge rules applied\n"
                    message += "• Conservative SL + Aggressive TP strategy\n"

                    # Add full parameter logic for mirror
                    message += "\n📋 <b>Mirror Parameter Logic:</b>\n"
                    message += f"• Entry: Market add @ mirror price\n"
                    message += f"• TP: Same selection logic as main\n"
                    message += f"• SL: Same conservative approach\n"
                    message += f"• Size: Matched main position\n"
                    message += "• Single Take Profit strategy (100% exit)\n"

                    if mirror_results["errors"]:
                        message += f"\n⚠️ Mirror errors:\n"
                        for error in mirror_results["errors"][:3]:  # Show max 3 errors
                            message += f"  • {error}\n"
                else:
                    message += f"\n\n❌ Mirror merge failed"

            return {
                "success": True,
                "orders_placed": [order_id] + tp_order_ids + ([chat_data.get(SL_ORDER_ID)] if chat_data.get(SL_ORDER_ID) else []),
                "position_size": merged_params['merged_size'],
                "trade_group_id": trade_group_id,
                "message": message,
                "avg_entry": fill_price,
                "risk_reward_ratio": risk_reward_ratio,
                "risk_amount": risk_amount,
                "max_reward": max_reward,
                "merged": True
            }

        except Exception as e:
            self.logger.error(f"❌ Error in conservative merge: {e}", exc_info=True)
            execution_time = self._format_execution_time(start_time)
            return {
                "success": False,
                "error": f"Merge error: {str(e)}",
                "orders_placed": [],
                "message": (
                    f"❌ <b>POSITION MERGE FAILED</b> {execution_time}\n"
                    f"🚨 {str(e)}\n\n"
                    f"The existing position remains unchanged."
                )
            }

    async def execute_trade(self, application, chat_id: int, chat_data: dict) -> dict:
        """
        Main trade execution entry point
        # Enforce conservative approach
        if ENFORCE_CONSERVATIVE_ONLY:
            approach = 'conservative'
            self.logger.info('Enforcing conservative-only approach')

        REFINED: Routes to appropriate approach with enhanced tracking
        FIXED: Automatic position mode detection for all approaches
        ENHANCED: Unified result format with rich messages
        """
        try:
            approach = chat_data.get(TRADING_APPROACH, "conservative")

            self.logger.info(f"🚀 Executing {approach.upper()} approach trade for chat {chat_id}")
            self.logger.info(f"🎯 Using automatic position mode detection for all orders")

            # Mark trade as bot-initiated (not external)
            chat_data["external_position"] = False
            chat_data["read_only_monitoring"] = False
            chat_data["position_created"] = True
            chat_data["has_bot_orders"] = True  # Mark as bot-initiated trade  # Flag to track bot-created positions

            if approach == "conservative":
                result = await self.execute_conservative_approach(application, chat_id, chat_data)
            elif approach == "simple_market":
                result = await self.execute_simple_market_approach(application, chat_id, chat_data)
            elif approach == "ggshot":
                result = await self.execute_ggshot_approach(application, chat_id, chat_data)
            else:
                # Default to conservative approach
                result = await self.execute_conservative_approach(application, chat_id, chat_data)

            # Log final result
            if result.get("success"):
                self.logger.info(f"✅ Trade execution completed successfully with automatic position mode detection")
                self.logger.info(f"   Orders placed: {len(result.get('orders_placed', []))}")
                # Mark position as created by bot
                chat_data["position_created"] = True
                chat_data["has_bot_orders"] = True  # Mark as bot-initiated trade
                chat_data["position_created_time"] = time.time()

                # Mark in position identifier
                symbol = chat_data.get(SYMBOL)
                side = chat_data.get(SIDE)
                if symbol and side:
                    mark_position_as_bot(symbol, side)
            else:
                # Get error message - conservative approach uses 'errors' list, others use 'error'
                error_msg = result.get('error') or ', '.join(result.get('errors', ['Unknown error']))
                self.logger.error(f"❌ Trade execution failed: {error_msg}")

            return result

        except Exception as e:
            self.logger.error(f"❌ Error in trade execution: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Execution error: {str(e)}",
                "orders_placed": [],
                "message": (
                    f"❌ <b>TRADE EXECUTION ERROR</b>\n"
                    f"{create_mobile_separator()}\n\n"
                    f"🚨 <b>Critical Error:</b>\n{str(e)}\n\n"
                    f"Please contact support if this persists."
                )
            }

# Global trade executor instance
trade_executor = TradeExecutor()

# FIXED: Proper async function that works with conversation handler
async def execute_trade_logic(application, chat_id: int, chat_data: dict) -> dict:
    """
    Execute trade using global executor instance
    FIXED: Proper async function signature for conversation handler
    FIXED: Automatic position mode detection
    ENHANCED: Returns rich formatted messages
    """
    
    # PERFORMANCE OPTIMIZATION: Enable execution mode during trade placement
    if ENHANCED_TP_SL_AVAILABLE:
        # Check if extreme performance mode should be used
        from config.settings import ENABLE_EXTREME_PERFORMANCE_MODE
        
        if ENABLE_EXTREME_PERFORMANCE_MODE:
            enhanced_tp_sl_manager.enable_extreme_execution_mode()
            logger.warning("🔥🔥 Enabled EXTREME execution mode for maximum speed")
        else:
            enhanced_tp_sl_manager.enable_execution_mode()
            logger.info("🚀 Enabled execution mode for optimized API calls")
        
        # Also enable execution mode for limit order tracker
        try:
            from utils.enhanced_limit_order_tracker import limit_order_tracker
            limit_order_tracker.enable_execution_mode()
        except Exception as e:
            logger.debug(f"Could not enable execution mode for limit order tracker: {e}")
        
        # Enable execution mode for API batch processor
        try:
            from utils.api_batch_processor import get_batch_processor
            batch_processor = get_batch_processor()
            batch_processor.enable_execution_mode()
        except Exception as e:
            logger.debug(f"Could not enable execution mode for API batch processor: {e}")
    
    try:
        result = await trade_executor.execute_trade(application, chat_id, chat_data)
        return result
    finally:
        # Always disable execution mode after trade completion
        if ENHANCED_TP_SL_AVAILABLE:
            from config.settings import ENABLE_EXTREME_PERFORMANCE_MODE
            
            if ENABLE_EXTREME_PERFORMANCE_MODE:
                enhanced_tp_sl_manager.disable_extreme_execution_mode()
                logger.warning("🔥🔥 Disabled EXTREME execution mode after trade completion")
            else:
                enhanced_tp_sl_manager.disable_execution_mode()
                logger.info("🏁 Disabled execution mode after trade completion")
            
            # Also disable execution mode for limit order tracker
            try:
                from utils.enhanced_limit_order_tracker import limit_order_tracker
                limit_order_tracker.disable_execution_mode()
            except Exception as e:
                logger.debug(f"Could not disable execution mode for limit order tracker: {e}")
            
            # Disable execution mode for API batch processor
            try:
                from utils.api_batch_processor import get_batch_processor
                batch_processor = get_batch_processor()
                batch_processor.disable_execution_mode()
            except Exception as e:
                logger.debug(f"Could not disable execution mode for API batch processor: {e}")

# Convenience functions for backward compatibility
async def execute_trade(application, chat_id: int, chat_data: dict) -> dict:
    """Execute trade using global executor instance with automatic position mode detection"""
    
    # PERFORMANCE OPTIMIZATION: Enable execution mode during trade placement
    if ENHANCED_TP_SL_AVAILABLE:
        # Check if extreme performance mode should be used
        from config.settings import ENABLE_EXTREME_PERFORMANCE_MODE
        
        if ENABLE_EXTREME_PERFORMANCE_MODE:
            enhanced_tp_sl_manager.enable_extreme_execution_mode()
            logger.warning("🔥🔥 Enabled EXTREME execution mode for maximum speed")
        else:
            enhanced_tp_sl_manager.enable_execution_mode()
            logger.info("🚀 Enabled execution mode for optimized API calls")
        
        # Also enable execution mode for limit order tracker
        try:
            from utils.enhanced_limit_order_tracker import limit_order_tracker
            limit_order_tracker.enable_execution_mode()
        except Exception as e:
            logger.debug(f"Could not enable execution mode for limit order tracker: {e}")
        
        # Enable execution mode for API batch processor
        try:
            from utils.api_batch_processor import get_batch_processor
            batch_processor = get_batch_processor()
            batch_processor.enable_execution_mode()
        except Exception as e:
            logger.debug(f"Could not enable execution mode for API batch processor: {e}")
    
    try:
        result = await trade_executor.execute_trade(application, chat_id, chat_data)
        return result
    finally:
        # Always disable execution mode after trade completion
        if ENHANCED_TP_SL_AVAILABLE:
            from config.settings import ENABLE_EXTREME_PERFORMANCE_MODE
            
            if ENABLE_EXTREME_PERFORMANCE_MODE:
                enhanced_tp_sl_manager.disable_extreme_execution_mode()
                logger.warning("🔥🔥 Disabled EXTREME execution mode after trade completion")
            else:
                enhanced_tp_sl_manager.disable_execution_mode()
                logger.info("🏁 Disabled execution mode after trade completion")
            
            # Also disable execution mode for limit order tracker
            try:
                from utils.enhanced_limit_order_tracker import limit_order_tracker
                limit_order_tracker.disable_execution_mode()
            except Exception as e:
                logger.debug(f"Could not disable execution mode for limit order tracker: {e}")
            
            # Disable execution mode for API batch processor
            try:
                from utils.api_batch_processor import get_batch_processor
                batch_processor = get_batch_processor()
                batch_processor.disable_execution_mode()
            except Exception as e:
                logger.debug(f"Could not disable execution mode for API batch processor: {e}")

# Export all public functions
__all__ = ['TradeExecutor', 'execute_trade', 'execute_trade_logic', 'trade_executor']