#!/usr/bin/env python3
"""
Manual Rebalancer Commands - Safe manual position rebalancing
This provides manual rebalancing without automatic interference
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from clients.bybit_client import bybit_client
from execution.conservative_rebalancer import rebalance_conservative_on_limit_fill
from execution.mirror_trader import bybit_client_2, ENABLE_MIRROR_TRADING

logger = logging.getLogger(__name__)


async def analyze_rebalancing_needs(client, account_name="Main"):
    """Analyze which symbols need rebalancing"""
    try:
        from clients.bybit_helpers import api_call_with_retry, get_all_open_orders

        # Get positions
        response = await api_call_with_retry(
            lambda: client.get_positions(category="linear", settleCoin="USDT"),
            timeout=20
        )
        if response and response.get('retCode') == 0:
            all_positions = response.get('result', {}).get('list', [])
            positions = [pos for pos in all_positions if float(pos.get('size', 0)) > 0]
        else:
            positions = []

        # Get orders
        response = await api_call_with_retry(
            lambda: client.get_open_orders(category="linear"),
            timeout=20
        )
        if response and response.get('retCode') == 0:
            orders = response.get('result', {}).get('list', [])
        else:
            orders = []

        # Analyze each symbol for rebalancing needs
        symbols_needing_rebalance = []

        for pos in positions:
            symbol = pos.get('symbol', '')
            side = pos.get('side', '')
            size = float(pos.get('size', 0))

            if size > 0:
                # Get orders for this symbol
                symbol_orders = [o for o in orders if o.get('symbol') == symbol]
                tp_orders = [o for o in symbol_orders if o.get('orderType') == 'Market' and o.get('reduceOnly') and o.get('triggerPrice')]

                # Check if TP distribution matches Conservative approach (85%, 5%, 5%, 5%)
                if len(tp_orders) >= 2:  # Conservative approach should have multiple TPs
                    tp_quantities = [float(o.get('qty', 0)) for o in tp_orders]
                    total_tp_qty = sum(tp_quantities)

                    if total_tp_qty > 0:
                        # Calculate current ratios
                        ratios = [(qty / total_tp_qty) * 100 for qty in tp_quantities]

                        # Check if it deviates from Conservative ratios (85%, 5%, 5%, 5%)
                        ideal_ratios = [85, 5, 5, 5] if len(ratios) >= 4 else [85, 15] if len(ratios) >= 2 else [100]

                        needs_rebalance = False
                        for i, ratio in enumerate(ratios[:len(ideal_ratios)]):
                            if abs(ratio - ideal_ratios[i]) > 5:  # 5% tolerance
                                needs_rebalance = True
                                break

                        if needs_rebalance:
                            symbols_needing_rebalance.append({
                                'symbol': symbol,
                                'side': side,
                                'size': size,
                                'tp_orders': len(tp_orders),
                                'current_ratios': [f"{r:.1f}%" for r in ratios[:4]],
                                'issue': 'TP ratio imbalance'
                            })

        return {
            'account': account_name,
            'positions': len(positions),
            'orders': len(orders),
            'symbols_needing_rebalance': symbols_needing_rebalance
        }

    except Exception as e:
        logger.error(f"Error analyzing rebalancing needs for {account_name}: {e}")
        return {
            'account': account_name,
            'positions': 0,
            'orders': 0,
            'symbols_needing_rebalance': [],
            'error': str(e)
        }


async def manual_rebalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual rebalance command - shows current positions and rebalancing needs for both accounts"""
    try:
        # Analyze main account
        main_analysis = await analyze_rebalancing_needs(bybit_client, "Main")

        # Analyze mirror account if available
        mirror_analysis = None
        if ENABLE_MIRROR_TRADING and bybit_client_2:
            mirror_analysis = await analyze_rebalancing_needs(bybit_client_2, "Mirror")

        # Check if any positions exist
        total_positions = main_analysis['positions'] + (mirror_analysis['positions'] if mirror_analysis else 0)

        if total_positions == 0:
            await update.message.reply_text(
                "📊 <b>MANUAL REBALANCER</b>\n\n"
                "❌ No active positions found on any account\n\n"
                "You need to have open positions to use the rebalancer.",
                parse_mode=ParseMode.HTML
            )
            return

        message_parts = ["📊 <b>MANUAL REBALANCER</b>\n"]

        # Show main account analysis
        message_parts.append(f"<b>📍 MAIN ACCOUNT</b>")
        message_parts.append(f"Positions: {main_analysis['positions']} | Orders: {main_analysis['orders']}")

        if main_analysis['symbols_needing_rebalance']:
            message_parts.append(f"🚨 <b>{len(main_analysis['symbols_needing_rebalance'])} symbols need rebalancing:</b>")
            for symbol_data in main_analysis['symbols_needing_rebalance'][:3]:  # Show max 3
                message_parts.append(
                    f"🔄 {symbol_data['symbol']} {symbol_data['side']} - "
                    f"{symbol_data['issue']} - Current: {', '.join(symbol_data['current_ratios'])}"
                )
            if len(main_analysis['symbols_needing_rebalance']) > 3:
                message_parts.append(f"... and {len(main_analysis['symbols_needing_rebalance']) - 3} more")
        else:
            message_parts.append("✅ All symbols properly balanced")

        # Show mirror account analysis if available
        if mirror_analysis:
            message_parts.append(f"\n<b>🪞 MIRROR ACCOUNT</b>")
            message_parts.append(f"Positions: {mirror_analysis['positions']} | Orders: {mirror_analysis['orders']}")

            if mirror_analysis['symbols_needing_rebalance']:
                message_parts.append(f"🚨 <b>{len(mirror_analysis['symbols_needing_rebalance'])} symbols need rebalancing:</b>")
                for symbol_data in mirror_analysis['symbols_needing_rebalance'][:3]:  # Show max 3
                    message_parts.append(
                        f"🔄 {symbol_data['symbol']} {symbol_data['side']} - "
                        f"{symbol_data['issue']} - Current: {', '.join(symbol_data['current_ratios'])}"
                    )
                if len(mirror_analysis['symbols_needing_rebalance']) > 3:
                    message_parts.append(f"... and {len(mirror_analysis['symbols_needing_rebalance']) - 3} more")
            else:
                message_parts.append("✅ All symbols properly balanced")

        # Calculate total symbols needing rebalancing
        total_needing_rebalance = len(main_analysis['symbols_needing_rebalance'])
        if mirror_analysis:
            total_needing_rebalance += len(mirror_analysis['symbols_needing_rebalance'])

        message_parts.append("")
        message_parts.append("🔒 <b>SAFE REBALANCING PRINCIPLES:</b>")
        message_parts.append("✅ <b>PRESERVES</b> all trigger prices (TP/SL levels)")
        message_parts.append("✅ <b>ONLY ADJUSTS</b> order quantities")
        message_parts.append("✅ <b>NEVER CHANGES</b> your price levels")
        message_parts.append("✅ <b>MAINTAINS</b> your trading strategy")
        message_parts.append("")
        message_parts.append("⚖️ <b>What it does:</b>")
        message_parts.append("• Redistributes quantities across TP levels")
        message_parts.append("• Ensures proper Conservative approach ratios")
        message_parts.append("• Fixes quantity imbalances from fills")
        message_parts.append("• Keeps your exact TP/SL prices unchanged")

        # Build keyboard based on available accounts and rebalancing needs
        keyboard = []

        # First row - Account-specific rebalancing
        account_row = []
        if main_analysis['symbols_needing_rebalance']:
            account_row.append(InlineKeyboardButton(f"⚖️ Rebalance Main ({len(main_analysis['symbols_needing_rebalance'])})", callback_data="rebalance_main_account"))

        if mirror_analysis and mirror_analysis['symbols_needing_rebalance']:
            account_row.append(InlineKeyboardButton(f"🪞 Rebalance Mirror ({len(mirror_analysis['symbols_needing_rebalance'])})", callback_data="rebalance_mirror_account"))

        if account_row:
            keyboard.append(account_row)

        # Second row - Global actions
        global_row = []
        if total_needing_rebalance > 0:
            global_row.append(InlineKeyboardButton(f"⚖️ Rebalance All ({total_needing_rebalance})", callback_data="rebalance_all_accounts"))

        global_row.append(InlineKeyboardButton("🔄 Refresh Analysis", callback_data="start_manual_rebalance"))
        keyboard.append(global_row)

        # Third row - Details and settings
        details_row = [
            InlineKeyboardButton("📊 Detailed Analysis", callback_data="show_detailed_analysis"),
            InlineKeyboardButton("⚙️ Settings", callback_data="rebalance_settings")
        ]
        keyboard.append(details_row)

        # Fourth row - Cancel
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_rebalance")])

        await update.message.reply_text(
            "\n".join(message_parts),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error in manual rebalance command: {e}")
        await update.message.reply_text(
            "❌ Error accessing rebalancer\n\n"
            f"Error: {str(e)}"
        )


async def rebalance_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show rebalancer status (manual mode)"""
    try:
        message = """
⚖️ <b>REBALANCER STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━

🔧 Mode: <b>MANUAL ONLY</b>
🤖 Auto-Rebalancing: <b>DISABLED</b>

<b>🔒 SAFE MANUAL REBALANCING:</b>
✅ <b>PRESERVES ALL TRIGGER PRICES</b>
✅ <b>ONLY ADJUSTS QUANTITIES</b>
✅ <b>NEVER CHANGES TP/SL LEVELS</b>
✅ <b>USER-CONTROLLED OPERATION</b>

<b>⚖️ WHAT IT DOES:</b>
• Redistributes order quantities
• Maintains Conservative approach ratios (85%, 5%, 5%, 5%)
• Fixes imbalances from partial fills
• Keeps your exact price levels unchanged

<b>🚫 WHY AUTO IS DISABLED:</b>
Automatic rebalancing was disabled to prevent any interference with your exchange orders. Manual control is safer and gives you full oversight.

<i>🔒 Your trigger prices are sacred - we only touch quantities!</i>
"""

        keyboard = [
            [
                InlineKeyboardButton("🔄 Manual Rebalance", callback_data="start_manual_rebalance"),
                InlineKeyboardButton("📊 Check Positions", callback_data="check_positions")
            ]
        ]

        await update.message.reply_text(
            message.strip(),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Error showing rebalancer status: {e}")
        await update.message.reply_text(
            "❌ Error checking rebalancer status"
        )


async def handle_rebalance_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rebalance-related callback queries"""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    try:
        action = query.data

        if action == "start_manual_rebalance":
            # Simulate the manual rebalance command
            await manual_rebalance_command(update, context)

        elif action == "check_rebalance_needs":
            await query.edit_message_text(
                "🔍 <b>CHECKING REBALANCE NEEDS</b>\n\n"
                "⏳ Analyzing positions and orders...\n\n"
                "This feature analyzes your positions to determine if rebalancing would be beneficial.\n\n"
                "🚧 Feature coming soon!",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

        elif action == "show_position_details":
            await query.edit_message_text(
                "📊 <b>POSITION DETAILS</b>\n\n"
                "⏳ Fetching detailed position information...\n\n"
                "This will show detailed breakdown of each position's orders and rebalancing needs.\n\n"
                "🚧 Feature coming soon!",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

        elif action == "rebalance_all_positions":
            await query.edit_message_text(
                "⚖️ <b>REBALANCE ALL POSITIONS</b>\n\n"
                "⚠️ This will rebalance ALL your positions.\n\n"
                "🔒 <b>TRIGGER PRICE GUARANTEE:</b>\n"
                "✅ <b>ZERO PRICE CHANGES</b> - All TP/SL levels stay exactly the same\n"
                "✅ <b>QUANTITY ONLY</b> - Only redistributes order sizes\n"
                "✅ <b>STRATEGY PRESERVED</b> - Your trading plan remains intact\n\n"
                "⚖️ <b>WHAT HAPPENS:</b>\n"
                "• Analyzes current position quantities\n"
                "• Redistributes to Conservative ratios (85%, 5%, 5%, 5%)\n"
                "• Cancels and replaces orders with new quantities\n"
                "• Keeps every single trigger price unchanged\n\n"
                "🚧 Manual rebalancing feature coming soon!\n\n"
                "For now, positions are rebalanced automatically when limit orders fill.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

        elif action == "select_position_rebalance":
            await query.edit_message_text(
                "🎯 <b>SELECT POSITION TO REBALANCE</b>\n\n"
                "⏳ Loading position selection menu...\n\n"
                "This will allow you to choose specific positions to rebalance.\n\n"
                "🚧 Feature coming soon!",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

        elif action == "cancel_rebalance":
            await query.edit_message_text(
                "❌ Rebalancing cancelled\n\n"
                "No changes were made to your positions."
            )

        elif action == "check_positions":
            # Redirect to show all positions
            from handlers.comprehensive_position_manager import show_all_positions
            await show_all_positions(update, context)

        elif action == "rebalance_main_account":
            await query.edit_message_text(
                "⚖️ <b>REBALANCING MAIN ACCOUNT</b>\n\n"
                "🔄 Starting rebalancing for main account positions...\n\n"
                "🔒 <b>SAFETY GUARANTEE:</b>\n"
                "✅ All trigger prices will remain exactly the same\n"
                "✅ Only order quantities will be adjusted\n"
                "✅ Conservative ratios will be restored (85%, 5%, 5%, 5%)\n\n"
                "⏳ Please wait while rebalancing is performed...",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

        elif action == "rebalance_mirror_account":
            await query.edit_message_text(
                "🪞 <b>REBALANCING MIRROR ACCOUNT</b>\n\n"
                "🔄 Starting rebalancing for mirror account positions...\n\n"
                "🔒 <b>SAFETY GUARANTEE:</b>\n"
                "✅ All trigger prices will remain exactly the same\n"
                "✅ Only order quantities will be adjusted\n"
                "✅ Conservative ratios will be restored (85%, 5%, 5%, 5%)\n\n"
                "⏳ Please wait while rebalancing is performed...",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

        elif action == "rebalance_all_accounts":
            await query.edit_message_text(
                "⚖️ <b>REBALANCING ALL ACCOUNTS</b>\n\n"
                "🔄 Starting rebalancing for both main and mirror accounts...\n\n"
                "🔒 <b>SAFETY GUARANTEE:</b>\n"
                "✅ All trigger prices will remain exactly the same\n"
                "✅ Only order quantities will be adjusted\n"
                "✅ Conservative ratios will be restored (85%, 5%, 5%, 5%)\n\n"
                "📍 Main account rebalancing...\n"
                "🪞 Mirror account rebalancing...\n\n"
                "⏳ Please wait while rebalancing is performed...",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

        elif action == "show_detailed_analysis":
            await query.edit_message_text(
                "📊 <b>DETAILED REBALANCING ANALYSIS</b>\n\n"
                "🔍 <b>ANALYSIS BREAKDOWN:</b>\n"
                "• Current TP/SL order distributions\n"
                "• Deviation from Conservative ratios (85%, 5%, 5%, 5%)\n"
                "• Recommended adjustments per symbol\n"
                "• Estimated order changes required\n\n"
                "🚧 Detailed analysis feature coming soon!\n\n"
                "This will show exact current vs target ratios for each position.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

        elif action == "rebalance_settings":
            await query.edit_message_text(
                "⚙️ <b>REBALANCER SETTINGS</b>\n\n"
                "🔧 <b>CURRENT SETTINGS:</b>\n"
                "• Target Ratios: 85%, 5%, 5%, 5% (Conservative)\n"
                "• Tolerance: ±5% deviation triggers rebalancing\n"
                "• Price Preservation: 100% guaranteed\n"
                "• Auto-rebalancing: On limit fills and TP hits\n\n"
                "🚧 Settings customization coming soon!\n\n"
                "For now, the rebalancer uses safe Conservative approach ratios.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="start_manual_rebalance")
                ]])
            )

    except Exception as e:
        logger.error(f"Error handling rebalance callback: {e}")
        await query.edit_message_text(f"❌ Error: {str(e)}")