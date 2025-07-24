#!/usr/bin/env python3
"""
Comprehensive Position & Order Manager
Shows detailed view of all positions and orders for both main and mirror accounts
Allows closing positions and canceling orders
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config.constants import *
from utils.formatters import format_number
from clients.bybit_helpers import (
    get_all_positions, get_all_open_orders,
    cancel_order_with_retry, get_positions_and_orders_batch
)
from clients.bybit_client import bybit_client

# Mirror trading imports
try:
    from execution.mirror_trader import (
        bybit_client_2, is_mirror_trading_enabled
    )
    MIRROR_AVAILABLE = True
except ImportError:
    MIRROR_AVAILABLE = False
    bybit_client_2 = None

# Helper functions for mirror trading
async def get_mirror_positions():
    """Get mirror account positions"""
    if MIRROR_AVAILABLE and bybit_client_2:
        # Use mirror client to get positions
        from clients.bybit_helpers import get_all_positions_with_client
        return await get_all_positions_with_client(bybit_client_2)
    return []

async def get_mirror_orders():
    """Get mirror account orders"""
    if MIRROR_AVAILABLE and bybit_client_2:
        # Use mirror client to get orders
        from clients.bybit_helpers import get_all_open_orders_with_client
        try:
            return await get_all_open_orders_with_client(bybit_client_2)
        except:
            # Fallback if the helper doesn't exist
            try:
                response = bybit_client_2.get_open_orders(category="linear")
                if response and response.get("result") and response["result"].get("list"):
                    return response["result"]["list"]
            except Exception as e:
                logger.warning(f"Could not get mirror orders: {e}")
    return []

logger = logging.getLogger(__name__)


class ComprehensivePositionManager:
    """Manages comprehensive position and order display"""

    @staticmethod
    async def get_comprehensive_data() -> Dict[str, Any]:
        """Get all position and order data for both accounts"""
        data = {
            'main': {'positions': [], 'orders': []},
            'mirror': {'positions': [], 'orders': []},
            'error': None
        }

        try:
            # Get main account data
            main_positions, main_orders, mirror_positions, mirror_orders = await get_positions_and_orders_batch()
            data['main']['positions'] = [p for p in main_positions if float(p.get('size', 0)) > 0]
            data['main']['orders'] = main_orders

            # Get mirror account data if available (already fetched by get_positions_and_orders_batch)
            if MIRROR_AVAILABLE and is_mirror_trading_enabled():
                data['mirror']['positions'] = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
                data['mirror']['orders'] = mirror_orders

        except Exception as e:
            data['error'] = str(e)
            logger.error(f"Error getting comprehensive data: {e}")

        return data

    @staticmethod
    def classify_orders(orders: List[Dict], positions: List[Dict]) -> Dict[str, List[Dict]]:
        """Classify orders by type"""
        classified = {
            'limit_orders': [],
            'take_profits': [],
            'stop_losses': []
        }

        # Create position lookup
        position_map = {}
        for pos in positions:
            symbol = pos.get('symbol')
            side = pos.get('side')
            avg_price = float(pos.get('avgPrice', 0))
            position_map[symbol] = {'side': side, 'avg_price': avg_price}

        for order in orders:
            symbol = order.get('symbol', '')
            side = order.get('side', '')
            reduce_only = order.get('reduceOnly', False)
            trigger_price = order.get('triggerPrice', '')
            limit_price = order.get('price', '')
            stop_order_type = order.get('stopOrderType', '')
            order_link_id = order.get('orderLinkId', '')
            order_type = order.get('orderType', '').lower()

            # Check if order is TP/SL based on OrderLinkId first (for Enhanced TP/SL system)
            is_enhanced_tp_sl = ('_TP' in order_link_id.upper() or
                                'TP1' in order_link_id.upper() or
                                'TP2' in order_link_id.upper() or
                                'TP3' in order_link_id.upper() or
                                'TP4' in order_link_id.upper() or
                                '_SL' in order_link_id.upper() or
                                'SL' in order_link_id.upper())

            # Limit orders (entry orders) - NOT reduce only AND NOT TP/SL orders
            if not reduce_only and not trigger_price and not is_enhanced_tp_sl:
                classified['limit_orders'].append(order)
                continue

            # Exit orders (TP/SL) - Enhanced TP/SL compatible
            # Include orders that are either reduce_only OR have TP/SL naming patterns
            if ((reduce_only or is_enhanced_tp_sl) and (trigger_price or limit_price) and symbol in position_map):
                pos_info = position_map[symbol]
                pos_side = pos_info['side']
                pos_avg_price = pos_info['avg_price']

                # Get the effective price (trigger_price for stops, limit_price for limits)
                effective_price = 0
                if trigger_price:
                    effective_price = float(trigger_price)
                elif limit_price:
                    effective_price = float(limit_price)

                if effective_price == 0:
                    continue  # Skip orders without valid prices

                # Determine if TP or SL based on price relative to position
                is_tp = False
                if pos_side == 'Buy' and effective_price > pos_avg_price:
                    is_tp = True
                elif pos_side == 'Sell' and effective_price < pos_avg_price:
                    is_tp = True

                # Enhanced classification for Enhanced TP/SL orders
                # Priority 1: Order Link ID detection (most reliable)
                if ('_TP' in order_link_id.upper() or
                    'TP1' in order_link_id.upper() or
                    'TP2' in order_link_id.upper() or
                    'TP3' in order_link_id.upper() or
                    'TP4' in order_link_id.upper()):
                    classified['take_profits'].append(order)
                elif ('_SL' in order_link_id.upper() or
                      'SL' in order_link_id.upper()):
                    classified['stop_losses'].append(order)
                # Priority 2: Stop order type
                elif stop_order_type == 'TakeProfit':
                    classified['take_profits'].append(order)
                elif stop_order_type in ['StopLoss', 'Stop']:
                    classified['stop_losses'].append(order)
                # Priority 3: Price-based classification
                elif is_tp:
                    classified['take_profits'].append(order)
                else:
                    classified['stop_losses'].append(order)

        return classified

    @staticmethod
    def format_position_display(position: Dict, orders_for_position: Dict, account_type: str) -> str:
        """Format a single position with its orders - complete information"""
        symbol = position.get('symbol', '')
        side = position.get('side', '')
        size = float(position.get('size', 0))
        avg_price = float(position.get('avgPrice', 0))
        mark_price = float(position.get('markPrice', 0))
        unrealized_pnl = float(position.get('unrealisedPnl', 0))
        cum_realized_pnl = float(position.get('cumRealisedPnl', 0))
        position_value = float(position.get('positionValue', 0))
        leverage = position.get('leverage', 'N/A')

        # Position header with more details
        side_emoji = "🟢" if side == "Buy" else "🔴"
        pnl_emoji = "📈" if unrealized_pnl >= 0 else "📉"
        pnl_str = f"+${format_number(abs(unrealized_pnl))}" if unrealized_pnl >= 0 else f"-${format_number(abs(unrealized_pnl))}"
        cum_pnl_str = f"+${format_number(abs(cum_realized_pnl))}" if cum_realized_pnl >= 0 else f"-${format_number(abs(cum_realized_pnl))}"

        result = f"\n{side_emoji} <b>{symbol}</b> - {side} ({account_type.upper()})\n"
        result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"📊 Position Details:\n"
        result += f"   • Size: {format_number(size)} contracts\n"
        result += f"   • Entry: ${format_number(avg_price)}\n"
        result += f"   • Mark: ${format_number(mark_price)}\n"
        result += f"   • Value: ${format_number(position_value)}\n"
        result += f"   • Leverage: {leverage}x\n"
        result += f"   • Unrealized P&L: {pnl_str} {pnl_emoji}\n"
        if cum_realized_pnl != 0:
            result += f"   • Cumulative P&L: {cum_pnl_str}\n"

        # Orders for this position - show ALL orders
        limit_orders = orders_for_position.get('limit_orders', [])
        take_profits = orders_for_position.get('take_profits', [])
        stop_losses = orders_for_position.get('stop_losses', [])

        total_orders = len(limit_orders) + len(take_profits) + len(stop_losses)
        if total_orders > 0:
            result += f"\n📋 Orders ({total_orders} total):\n"

        if limit_orders:
            result += f"\n   📝 <b>Entry Orders ({len(limit_orders)}):</b>\n"
            # Sort by price
            sorted_limits = sorted(limit_orders, key=lambda x: float(x.get('price', 0)), reverse=(side == "Sell"))
            for i, order in enumerate(sorted_limits, 1):
                price = float(order.get('price', 0))
                qty = float(order.get('qty', 0))
                order_id = order.get('orderId', '')[:8]
                order_link_id = order.get('orderLinkId', '')

                # Calculate percentage from current entry price if applicable
                pct_from_entry = ((price - avg_price) / avg_price * 100) if side == "Buy" else ((avg_price - price) / avg_price * 100)
                pct_str = f" ({pct_from_entry:+.1f}%)" if abs(pct_from_entry) > 0.1 else ""

                result += f"      {i}. ${format_number(price)} × {format_number(qty)}{pct_str}"
                if order_link_id:
                    result += f" [{order_link_id}]"
                result += "\n"

        if take_profits:
            result += f"\n   🎯 <b>Take Profit Orders ({len(take_profits)}):</b>\n"
            # Sort by price (handle both trigger_price and limit_price)
            def get_tp_price(order):
                trigger_price = order.get('triggerPrice', '')
                limit_price = order.get('price', '')
                if trigger_price:
                    return float(trigger_price)
                elif limit_price:
                    return float(limit_price)
                return 0

            sorted_tps = sorted(take_profits, key=get_tp_price, reverse=(side == "Buy"))
            for i, order in enumerate(sorted_tps, 1):
                price = get_tp_price(order)
                qty = float(order.get('qty', 0))
                order_type = order.get('orderType', '')
                order_link_id = order.get('orderLinkId', '')
                pct_from_entry = ((price - avg_price) / avg_price * 100) if side == "Buy" else ((avg_price - price) / avg_price * 100)
                result += f"      TP{i}: ${format_number(price)} × {format_number(qty)} (+{format_number(abs(pct_from_entry))}%)"
                if order_link_id:
                    result += f" [{order_link_id}]"
                result += "\n"

        if stop_losses:
            result += f"\n   🛑 <b>Stop Loss Orders ({len(stop_losses)}):</b>\n"
            # Sort by price
            sorted_sls = sorted(stop_losses, key=lambda x: float(x.get('triggerPrice', 0)), reverse=(side == "Sell"))
            for i, order in enumerate(sorted_sls, 1):
                price = float(order.get('triggerPrice', 0))
                qty = float(order.get('qty', 0))
                order_type = order.get('orderType', '')
                order_link_id = order.get('orderLinkId', '')
                pct_from_entry = ((price - avg_price) / avg_price * 100) if side == "Buy" else ((avg_price - price) / avg_price * 100)
                result += f"      SL: ${format_number(price)} × {format_number(qty)} ({format_number(pct_from_entry)}%)"
                if order_link_id:
                    result += f" [{order_link_id}]"
                result += "\n"

        if not any([limit_orders, take_profits, stop_losses]):
            result += "\n   ⚠️ <b>No active orders found for this position</b>\n"
            result += "   💡 Position has no TP/SL protection - consider adding orders\n"

        return result

    @staticmethod
    def build_position_keyboard(symbol: str, account: str) -> InlineKeyboardMarkup:
        """Build keyboard for position actions"""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"❌ Close {symbol}",
                    callback_data=f"close_pos:{account}:{symbol}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚫 Cancel All Orders",
                    callback_data=f"cancel_orders:{account}:{symbol}"
                ),
                InlineKeyboardButton(
                    "📊 Details",
                    callback_data=f"pos_details:{account}:{symbol}"
                )
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="show_all_positions"),
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def build_main_keyboard() -> InlineKeyboardMarkup:
        """Build main positions overview keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="show_all_positions"),
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)


async def show_all_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show comprehensive view of all positions and orders"""
    query = update.callback_query
    if query:
        from utils.telegram_helpers import safe_answer_callback
        await safe_answer_callback(query)

    try:
        # Get comprehensive data
        data = await ComprehensivePositionManager.get_comprehensive_data()

        if data['error']:
            await query.edit_message_text(
                f"❌ Error loading positions: {data['error']}",
                reply_markup=ComprehensivePositionManager.build_main_keyboard()
            )
            return

        # Build message
        message_parts = ["<b>📊 COMPREHENSIVE POSITIONS & ORDERS</b>"]

        # Main account
        main_positions = data['main']['positions']
        main_orders = data['main']['orders']

        # Mirror account data
        mirror_positions = data['mirror']['positions']
        mirror_orders = data['mirror']['orders']

        # Calculate totals
        total_main_pnl = sum(float(p.get('unrealisedPnl', 0)) for p in main_positions)
        total_mirror_pnl = sum(float(p.get('unrealisedPnl', 0)) for p in mirror_positions)
        total_pnl = total_main_pnl + total_mirror_pnl

        # Summary section
        message_parts.append(f"\n📈 <b>SUMMARY</b>")
        message_parts.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        message_parts.append(f"Main Account: {len(main_positions)} positions, {len(main_orders)} orders")
        message_parts.append(f"Mirror Account: {len(mirror_positions)} positions, {len(mirror_orders)} orders")
        message_parts.append(f"Total Unrealized P&L: {'+'if total_pnl >= 0 else ''}${format_number(abs(total_pnl))}")
        message_parts.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

        message_parts.append(f"<b>📍 MAIN ACCOUNT</b> ({len(main_positions)} positions)")

        if main_positions:
            for position in main_positions:
                symbol = position.get('symbol', '')

                # Get orders for this position
                position_orders = [o for o in main_orders if o.get('symbol') == symbol]
                classified_orders = ComprehensivePositionManager.classify_orders(
                    position_orders, [position]
                )

                position_display = ComprehensivePositionManager.format_position_display(
                    position, classified_orders, "main"
                )
                message_parts.append(position_display)

                # Add individual position controls
                keyboard_row = [
                    InlineKeyboardButton(
                        f"❌ Close {symbol}",
                        callback_data=f"close_pos:main:{symbol}"
                    )
                ]
                if position_orders:
                    keyboard_row.append(
                        InlineKeyboardButton(
                            f"🚫 Cancel {symbol} Orders",
                            callback_data=f"cancel_orders:main:{symbol}"
                        )
                    )

                # Create inline keyboard for this position
                pos_keyboard = InlineKeyboardMarkup([keyboard_row])
        else:
            message_parts.append("No active positions on main account\n")

        # Mirror account section
        if mirror_positions or mirror_orders:
            message_parts.append(f"\n<b>🪞 MIRROR ACCOUNT</b> ({len(mirror_positions)} positions)")

            if mirror_positions:
                for position in mirror_positions:
                    symbol = position.get('symbol', '')

                    # Get orders for this position
                    position_orders = [o for o in mirror_orders if o.get('symbol') == symbol]
                    classified_orders = ComprehensivePositionManager.classify_orders(
                        position_orders, [position]
                    )

                    position_display = ComprehensivePositionManager.format_position_display(
                        position, classified_orders, "mirror"
                    )
                    message_parts.append(position_display)
            else:
                message_parts.append("No active positions on mirror account\n")

        # Build final message
        message = "\n".join(message_parts)

        # Handle long messages by splitting them
        messages = []
        if len(message) > 4000:
            # Split message into chunks while preserving position blocks
            current_message = "<b>📊 COMPREHENSIVE POSITIONS & ORDERS</b>\n"
            for part in message_parts[1:]:  # Skip the header
                if len(current_message) + len(part) + 2 < 4000:
                    current_message += "\n" + part
                else:
                    messages.append(current_message)
                    current_message = part
            if current_message:
                messages.append(current_message)
        else:
            messages = [message]

        # Main keyboard
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="show_all_positions")
            ],
            [
                InlineKeyboardButton("⚠️ Close All Main", callback_data="close_all_positions:main"),
                InlineKeyboardButton("⚠️ Close All Mirror", callback_data="close_all_positions:mirror")
            ],
            [
                InlineKeyboardButton("🚫 Cancel All Orders", callback_data="cancel_all_orders"),
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send messages
        if query:
            # For callback queries, we can only edit the current message
            # Send the first part as an edit, then send additional parts as new messages
            await query.edit_message_text(
                messages[0],
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup if len(messages) == 1 else None
            )

            # Send additional parts as new messages
            for i, msg in enumerate(messages[1:], 1):
                is_last = i == len(messages) - 1
                await query.message.reply_text(
                    msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup if is_last else None
                )
        else:
            # For regular messages, send all parts
            for i, msg in enumerate(messages):
                is_last = i == len(messages) - 1
                await update.message.reply_text(
                    msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup if is_last else None
                )

    except Exception as e:
        logger.error(f"Error in show_all_positions: {e}")
        error_message = f"❌ Error: {str(e)}"

        if query:
            await query.edit_message_text(
                error_message,
                reply_markup=ComprehensivePositionManager.build_main_keyboard()
            )
        else:
            await update.message.reply_text(error_message)


async def handle_position_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle position action callbacks"""
    query = update.callback_query
    if not query:
        return

    from utils.telegram_helpers import safe_answer_callback
    await safe_answer_callback(query)

    try:
        action_data = query.data.split(':')
        action = action_data[0]

        if action == "close_pos":
            account, symbol = action_data[1], action_data[2]
            await close_single_position(query, account, symbol)

        elif action == "cancel_orders":
            account, symbol = action_data[1], action_data[2]
            await cancel_position_orders(query, account, symbol)

        elif action == "close_all_positions":
            account = action_data[1]
            await close_all_account_positions(query, account)

        elif action == "cancel_all_orders":
            await cancel_all_orders(query)

        elif action == "pos_details":
            account, symbol = action_data[1], action_data[2]
            await show_position_details(query, account, symbol)

    except Exception as e:
        logger.error(f"Error handling position action: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")


async def close_single_position(query, account: str, symbol: str) -> None:
    """Close a single position"""
    try:
        client = bybit_client if account == "main" else bybit_client_2

        # Get position info
        positions = await get_all_positions(client)
        position = next((p for p in positions if p.get('symbol') == symbol), None)

        if not position:
            await query.edit_message_text(f"❌ Position {symbol} not found")
            return

        # Close position logic here
        # This would use the existing position closing functionality
        await query.edit_message_text(
            f"⏳ Closing {symbol} position on {account} account...",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Refresh", callback_data="show_all_positions")
            ]])
        )

    except Exception as e:
        logger.error(f"Error closing position: {e}")
        await query.edit_message_text(f"❌ Error closing position: {str(e)}")


async def cancel_position_orders(query, account: str, symbol: str) -> None:
    """Cancel all orders for a specific position"""
    try:
        client = bybit_client if account == "main" else bybit_client_2

        # Get orders for symbol
        if account == "main":
            orders = await get_all_open_orders()
        else:
            orders = await get_mirror_orders()

        symbol_orders = [o for o in orders if o.get('symbol') == symbol]

        if not symbol_orders:
            await query.edit_message_text(f"No orders found for {symbol}")
            return

        # Cancel orders
        cancelled_count = 0
        for order in symbol_orders:
            try:
                await cancel_order_with_retry(symbol, order['orderId'])
                cancelled_count += 1
            except Exception as e:
                logger.error(f"Error cancelling order {order['orderId']}: {e}")

        await query.edit_message_text(
            f"✅ Cancelled {cancelled_count}/{len(symbol_orders)} orders for {symbol}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Refresh", callback_data="show_all_positions")
            ]])
        )

    except Exception as e:
        logger.error(f"Error cancelling orders: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")


async def close_all_account_positions(query, account: str) -> None:
    """Close all positions for an account"""
    confirmation_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Close All", callback_data=f"confirm_close_all:{account}"),
            InlineKeyboardButton("❌ Cancel", callback_data="show_all_positions")
        ]
    ])

    await query.edit_message_text(
        f"⚠️ Are you sure you want to close ALL positions on {account} account?",
        reply_markup=confirmation_keyboard
    )


async def cancel_all_orders(query) -> None:
    """Cancel all orders on both accounts"""
    confirmation_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Cancel All", callback_data="confirm_cancel_all"),
            InlineKeyboardButton("❌ Cancel", callback_data="show_all_positions")
        ]
    ])

    await query.edit_message_text(
        "⚠️ Are you sure you want to cancel ALL orders on both accounts?",
        reply_markup=confirmation_keyboard
    )


async def show_position_details(query, account: str, symbol: str) -> None:
    """Show detailed information for a specific position"""
    try:
        # Get detailed position and order information
        # This would show more detailed analytics for the specific position
        await query.edit_message_text(
            f"📊 Detailed view for {symbol} ({account}) - Coming soon",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="show_all_positions")
            ]])
        )

    except Exception as e:
        logger.error(f"Error showing position details: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")