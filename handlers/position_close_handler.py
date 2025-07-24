#!/usr/bin/env python3
"""
Position Close Handler - Handles individual position closing with confirmation
Provides a safe way to close specific positions with all their orders
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
from decimal import Decimal

from execution.position_manager import position_manager
from utils.formatters import get_emoji, format_mobile_currency

logger = logging.getLogger(__name__)


async def handle_close_position_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle initial close position request"""
    query = update.callback_query
    await query.answer()

    # Parse callback data: close_position:BTCUSDT:Buy:main
    try:
        parts = query.data.split(":")
        if len(parts) != 4:
            await query.edit_message_text("❌ Invalid position data")
            return

        _, symbol, side, account = parts

        # Get position details
        position = await position_manager.get_position_details(symbol, side, account)
        if not position:
            await query.edit_message_text(
                f"❌ No active position found for {symbol}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="list_positions")
                ]])
            )
            return

        # Format confirmation message
        position_summary = position_manager.format_position_summary(position)
        account_label = "MAIN" if account == "main" else "MIRROR"
        
        # Count orders by type
        orders = position.get('orders', [])
        tp_orders = [o for o in orders if o.get('stopOrderType') == 'TakeProfit' or 'TP' in o.get('orderLinkId', '')]
        sl_orders = [o for o in orders if o.get('stopOrderType') == 'StopLoss' or 'SL' in o.get('orderLinkId', '')]
        limit_orders = [o for o in orders if o.get('orderType') == 'Limit' and not o.get('stopOrderType')]

        confirmation_text = f"""⚠️ <b>CONFIRM POSITION CLOSE</b> ⚠️

You are about to close this position on your <b>{account_label}</b> account:

{position_summary}

<b>This will:</b>
• Cancel ALL {len(orders)} orders for {symbol}
  - {len(tp_orders)} Take Profit orders
  - {len(sl_orders)} Stop Loss orders
  - {len(limit_orders)} Limit orders
• Close the position at market price
• Stop any active monitors
• This action cannot be undone

<b>Are you sure you want to close this position?</b>"""

        # Create confirmation keyboard
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                f"✅ YES, CLOSE {symbol}",
                callback_data=f"confirm_close_position:{symbol}:{side}:{account}"
            )],
            [InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel_close_position"
            )]
        ])

        await query.edit_message_text(
            confirmation_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error in close position request: {e}")
        await query.edit_message_text(
            "❌ Error processing request. Please try again.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="list_positions")
            ]])
        )


async def handle_confirm_close_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmed close position request"""
    query = update.callback_query
    await query.answer()

    # Parse callback data: confirm_close_position:BTCUSDT:Buy:main
    try:
        parts = query.data.split(":")
        if len(parts) != 4:
            await query.edit_message_text("❌ Invalid position data")
            return

        _, symbol, side, account = parts
        account_label = "MAIN" if account == "main" else "MIRROR"

        # Update message to show progress
        await query.edit_message_text(
            f"{get_emoji('loading')} Closing position for {symbol} on {account_label} account...\n\n"
            f"• Step 1: Stopping monitors...\n"
            f"• Step 2: Cancelling orders...\n"
            f"• Step 3: Closing position...",
            parse_mode=ParseMode.HTML
        )

        # Stop any active monitors for this position
        try:
            # Stop Enhanced TP/SL monitor if active
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            monitor_key = f"{symbol}_{side}_{account}"
            if monitor_key in enhanced_tp_sl_manager.position_monitors:
                # Cancel the monitoring task
                monitor_data = enhanced_tp_sl_manager.position_monitors[monitor_key]
                if 'monitoring_task' in monitor_data and monitor_data['monitoring_task']:
                    monitor_data['monitoring_task'].cancel()
                # Remove from monitors
                del enhanced_tp_sl_manager.position_monitors[monitor_key]
                logger.info(f"Stopped Enhanced TP/SL monitor for {monitor_key}")
                
            # Also check for dashboard monitors
            if 'monitor_tasks' in context.bot_data:
                monitor_tasks = context.bot_data['monitor_tasks']
                # Find and remove any monitors for this symbol
                keys_to_remove = []
                for key, task_info in monitor_tasks.items():
                    if (task_info.get('symbol') == symbol and 
                        task_info.get('account_type', 'main') == account):
                        keys_to_remove.append(key)
                
                for key in keys_to_remove:
                    del monitor_tasks[key]
                    logger.info(f"Removed dashboard monitor: {key}")
                    
        except Exception as e:
            logger.warning(f"Error stopping monitors: {e}")

        # Execute the close operation
        result = await position_manager.close_position_with_orders(symbol, side, account)

        # Format result message
        if result["position_closed"]:
            success_text = f"✅ <b>POSITION CLOSED SUCCESSFULLY</b>\n\n"
            success_text += f"<b>Symbol:</b> {symbol}\n"
            success_text += f"<b>Account:</b> {account_label}\n"
            success_text += f"<b>Orders Cancelled:</b> {result['total_orders_cancelled']}\n"
            
            if result.get('position_details'):
                pnl = float(result['position_details'].get('unrealisedPnl', 0))
                if pnl != 0:
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    success_text += f"<b>Final P&L:</b> {pnl_emoji} ${format_mobile_currency(Decimal(str(pnl)))}\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Dashboard", callback_data="refresh_dashboard")],
                [InlineKeyboardButton("📋 Close Another Position", callback_data="list_positions")]
            ])
            
            await query.edit_message_text(
                success_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            error_text = f"❌ <b>FAILED TO CLOSE POSITION</b>\n\n"
            error_text += f"<b>Symbol:</b> {symbol}\n"
            error_text += f"<b>Account:</b> {account_label}\n"
            
            if result.get("errors"):
                error_text += f"\n<b>Errors:</b>\n"
                for error in result["errors"]:
                    error_text += f"• {error}\n"
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data=f"close_position:{symbol}:{side}:{account}")],
                [InlineKeyboardButton("🔙 Back", callback_data="list_positions")]
            ])
            
            await query.edit_message_text(
                error_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error confirming close position: {e}")
        await query.edit_message_text(
            f"❌ Error closing position: {str(e)}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back", callback_data="list_positions")
            ]])
        )


async def handle_cancel_close_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle cancel close position request"""
    query = update.callback_query
    await query.answer("Cancelled")
    
    # Go back to position list
    await handle_list_positions(update, context)


async def handle_list_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle list positions callback - same as closeposition command"""
    query = update.callback_query
    await query.answer()
    
    # Show loading message
    await query.edit_message_text(
        f"{get_emoji('loading')} Loading positions...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Get all positions from both accounts
        positions = await position_manager.get_all_positions_with_details()
        
        if not positions:
            await query.edit_message_text(
                f"{get_emoji('info')} No active positions found on either account.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
                ]])
            )
            return
        
        # Format position list with compact format to avoid message too long
        text = f"<b>📊 ACTIVE POSITIONS</b>\n"
        text += f"{'━' * 30}\n"
        
        # Group by account
        main_positions = [p for p in positions if p['account'] == 'main']
        mirror_positions = [p for p in positions if p['account'] == 'mirror']
        
        keyboard_buttons = []
        
        # Count total positions
        total_main = len(main_positions)
        total_mirror = len(mirror_positions)
        total_positions = total_main + total_mirror
        
        # If too many positions, use ultra-compact format
        if total_positions > 20:
            # Ultra-compact format - just symbol and P&L
            if main_positions:
                text += f"\n<b>💼 MAIN ({total_main})</b>\n"
                for pos in main_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    pnl = float(pos.get('unrealisedPnl', 0))
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    pnl_str = format_mobile_currency(Decimal(str(pnl)))
                    
                    text += f"{pnl_emoji} {symbol}: ${pnl_str}\n"
                    
                    # Add button for this position
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            f"❌ {symbol} (M)",
                            callback_data=f"close_position:{symbol}:{side}:main"
                        )
                    ])
            
            if mirror_positions:
                text += f"\n<b>🔄 MIRROR ({total_mirror})</b>\n"
                for pos in mirror_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    pnl = float(pos.get('unrealisedPnl', 0))
                    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                    pnl_str = format_mobile_currency(Decimal(str(pnl)))
                    
                    text += f"{pnl_emoji} {symbol}: ${pnl_str}\n"
                    
                    # Add button for this position
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            f"❌ {symbol} (🔄)",
                            callback_data=f"close_position:{symbol}:{side}:mirror"
                        )
                    ])
        else:
            # Standard format for fewer positions
            if main_positions:
                text += f"\n<b>💼 MAIN ACCOUNT ({total_main} positions)</b>\n"
                for pos in main_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = pos['size']
                    pnl = pos.get('unrealisedPnl', 0)
                    pnl_emoji = "🟢" if float(pnl) >= 0 else "🔴"
                    
                    text += f"\n{pnl_emoji} <b>{symbol}</b> {side}\n"
                    text += f"   Size: {size}, PnL: ${format_mobile_currency(Decimal(str(pnl)))}\n"
                    
                    # Add button for this position
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            f"❌ Close {symbol} (Main)",
                            callback_data=f"close_position:{symbol}:{side}:main"
                        )
                    ])
            
            # Mirror account positions
            if mirror_positions:
                text += f"\n<b>🔄 MIRROR ACCOUNT ({total_mirror} positions)</b>\n"
                for pos in mirror_positions:
                    symbol = pos['symbol']
                    side = pos['side']
                    size = pos['size']
                    pnl = pos.get('unrealisedPnl', 0)
                    pnl_emoji = "🟢" if float(pnl) >= 0 else "🔴"
                    
                    text += f"\n{pnl_emoji} <b>{symbol}</b> {side}\n"
                    text += f"   Size: {size}, PnL: ${format_mobile_currency(Decimal(str(pnl)))}\n"
                    
                    # Add button for this position
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            f"❌ Close {symbol} (Mirror)",
                            callback_data=f"close_position:{symbol}:{side}:mirror"
                        )
                    ])
        
        # Add back to dashboard button
        keyboard_buttons.append([
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        text += f"\n\n⚠️ <b>Warning:</b> Closing a position will:\n"
        text += f"• Cancel ALL orders for that symbol\n"
        text += f"• Close at market price\n"
        text += f"• This cannot be undone"
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error listing positions: {e}")
        await query.edit_message_text(
            f"{get_emoji('error')} Error loading positions: {str(e)}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
            ]])
        )


# Create handlers
close_position_handler = CallbackQueryHandler(
    handle_close_position_request,
    pattern="^close_position:"
)

confirm_close_handler = CallbackQueryHandler(
    handle_confirm_close_position,
    pattern="^confirm_close_position:"
)

cancel_close_handler = CallbackQueryHandler(
    handle_cancel_close_position,
    pattern="^cancel_close_position$"
)

list_positions_handler = CallbackQueryHandler(
    handle_list_positions,
    pattern="^list_positions$"
)