#!/usr/bin/env python3
"""
Emergency Handler - Handles the emergency shutdown confirmation flow
Provides multiple confirmation steps to prevent accidental activation
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    CallbackQueryHandler, MessageHandler, filters
)
from telegram.constants import ParseMode

from execution.emergency import emergency_shutdown, execute_emergency_shutdown
from utils.formatters import format_mobile_currency, get_emoji
logger = logging.getLogger(__name__)

# Conversation states for emergency flow
EMERGENCY_WARNING = 50
EMERGENCY_CONFIRM_1 = 51
EMERGENCY_CONFIRM_2 = 52
EMERGENCY_PIN = 53
EMERGENCY_EXECUTING = 54

# Rate limiting for emergency command
EMERGENCY_COOLDOWN_SECONDS = 300  # 5 minutes between attempts
emergency_last_used: Dict[int, datetime] = {}

# Optional PIN for extra security (set to None to disable)
EMERGENCY_PIN = None  # Set this to a string like "1234" to enable PIN verification


async def emergency_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start emergency shutdown flow with rate limiting"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Check rate limiting
    if user_id in emergency_last_used:
        time_since_last = datetime.now() - emergency_last_used[user_id]
        if time_since_last < timedelta(seconds=EMERGENCY_COOLDOWN_SECONDS):
            remaining = EMERGENCY_COOLDOWN_SECONDS - time_since_last.total_seconds()
            await update.message.reply_text(
                f"⏳ Emergency command is on cooldown.\n"
                f"Please wait {int(remaining)} seconds before trying again.",
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END

    # Log emergency command usage
    logger.critical(f"🚨 EMERGENCY COMMAND initiated by user {user_id} in chat {chat_id}")

    try:
        # Get current status
        status = await emergency_shutdown.get_emergency_status()

        # Count totals
        total_positions = (
            len(status['main']['positions']) +
            len(status['mirror']['positions'])
        )
        total_orders = (
            len(status['main']['orders']) +
            len(status['mirror']['orders'])
        )
        total_exposure = (
            status['main']['total_exposure'] +
            status['mirror']['total_exposure']
        )

        # Build warning message
        lines = [
            "🚨🚨🚨 <b>EMERGENCY SHUTDOWN WARNING</b> 🚨🚨🚨\n",
            "This will IMMEDIATELY:",
            "• Cancel ALL pending orders",
            "• Close ALL open positions",
            "• Stop ALL trading activities\n",
            f"<b>Current Status:</b>",
            f"📊 Active Positions: {total_positions}",
            f"📝 Open Orders: {total_orders}",
            f"💰 Total Exposure: {format_mobile_currency(total_exposure)}\n"
        ]

        # Add position details
        if status['main']['positions']:
            lines.append("<b>Main Account Positions:</b>")
            for pos in status['main']['positions'][:5]:  # Show first 5
                lines.append(
                    f"• {pos['symbol']} {pos['side']}: "
                    f"{pos['size']} ({format_mobile_currency(pos.get('positionValue', 0))})"
                )
            if len(status['main']['positions']) > 5:
                lines.append(f"  ... and {len(status['main']['positions']) - 5} more")

        if status['mirror']['positions']:
            lines.append("\n<b>Mirror Account Positions:</b>")
            for pos in status['mirror']['positions'][:5]:
                lines.append(
                    f"• {pos['symbol']} {pos['side']}: "
                    f"{pos['size']} ({format_mobile_currency(pos.get('positionValue', 0))})"
                )
            if len(status['mirror']['positions']) > 5:
                lines.append(f"  ... and {len(status['mirror']['positions']) - 5} more")

        lines.extend([
            "\n⚠️ <b>THIS ACTION CANNOT BE UNDONE!</b> ⚠️",
            "\nAre you ABSOLUTELY SURE you want to proceed?"
        ])

        # Create confirmation keyboard
        keyboard = [
            [
                InlineKeyboardButton("❌ CANCEL", callback_data="emergency_cancel"),
                InlineKeyboardButton("⚠️ PROCEED", callback_data="emergency_proceed_1")
            ]
        ]

        # Store status in context for later use
        context.user_data['emergency_status'] = status
        context.user_data['emergency_start_time'] = datetime.now()

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return EMERGENCY_CONFIRM_1

    except Exception as e:
        logger.error(f"Error in emergency command: {e}")
        await update.message.reply_text(
            "❌ Error getting current status. Emergency shutdown aborted.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END


async def emergency_confirm_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """First confirmation step"""
    query = update.callback_query
    await query.answer()

    if query.data == "emergency_cancel":
        await query.edit_message_text(
            "✅ Emergency shutdown CANCELLED.\n"
            "No actions were taken.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    # Second confirmation with countdown
    lines = [
        "🚨 <b>FINAL CONFIRMATION REQUIRED</b> 🚨\n",
        "You are about to execute an EMERGENCY SHUTDOWN.",
        "This will close ALL positions and cancel ALL orders.\n",
        "⏱ <b>You have 10 seconds to confirm.</b>\n",
        "Press the button below to EXECUTE SHUTDOWN:"
    ]

    keyboard = [
        [InlineKeyboardButton("🚨 EXECUTE EMERGENCY SHUTDOWN 🚨", callback_data="emergency_execute")]
    ]

    message = await query.edit_message_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # Store message ID for countdown updates
    context.user_data['emergency_message_id'] = message.message_id
    context.user_data['emergency_countdown_start'] = datetime.now()

    # Start countdown task
    asyncio.create_task(emergency_countdown(update.effective_chat.id, message.message_id, context))

    return EMERGENCY_CONFIRM_2


async def emergency_countdown(chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Show countdown timer"""
    for i in range(10, 0, -1):
        await asyncio.sleep(1)

        # Check if still in emergency flow
        if context.user_data.get('emergency_message_id') != message_id:
            return

        try:
            lines = [
                "🚨 <b>FINAL CONFIRMATION REQUIRED</b> 🚨\n",
                "You are about to execute an EMERGENCY SHUTDOWN.",
                "This will close ALL positions and cancel ALL orders.\n",
                f"⏱ <b>You have {i} seconds to confirm.</b>\n",
                "Press the button below to EXECUTE SHUTDOWN:"
            ]

            keyboard = [
                [InlineKeyboardButton("🚨 EXECUTE EMERGENCY SHUTDOWN 🚨", callback_data="emergency_execute")]
            ]

            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception:
            # Message was probably already edited
            return

    # Timeout - cancel emergency
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏰ Emergency shutdown TIMED OUT.\nNo actions were taken.",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass


async def emergency_confirm_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Second confirmation step - check for PIN if enabled"""
    query = update.callback_query
    await query.answer()

    # Check if within timeout
    countdown_start = context.user_data.get('emergency_countdown_start')
    if countdown_start and (datetime.now() - countdown_start).total_seconds() > 10:
        await query.edit_message_text(
            "⏰ Emergency shutdown TIMED OUT.\nNo actions were taken.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    # Clear countdown tracking
    context.user_data.pop('emergency_message_id', None)

    # Check if PIN verification is required
    if EMERGENCY_PIN:
        await query.edit_message_text(
            "🔐 <b>PIN VERIFICATION REQUIRED</b>\n\n"
            "Please enter the emergency PIN to proceed:",
            parse_mode=ParseMode.HTML
        )
        return EMERGENCY_PIN

    # No PIN required, proceed to execution
    return await execute_emergency(query, context)


async def emergency_pin_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Verify emergency PIN"""
    user_pin = update.message.text.strip()

    # Delete the PIN message for security
    try:
        await update.message.delete()
    except Exception:
        pass

    if user_pin != EMERGENCY_PIN:
        await update.effective_chat.send_message(
            "❌ Incorrect PIN. Emergency shutdown aborted.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    # PIN correct, proceed to execution
    return await execute_emergency(update, context)


async def execute_emergency(query_or_update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute the emergency shutdown"""
    # Get chat for sending messages
    if hasattr(query_or_update, 'effective_chat'):
        chat = query_or_update.effective_chat
    else:
        chat = query_or_update.message.chat

    # Update rate limiting
    user_id = query_or_update.effective_user.id if hasattr(query_or_update, 'effective_user') else None
    if user_id:
        emergency_last_used[user_id] = datetime.now()

    # Send execution start message
    progress_msg = await chat.send_message(
        "🚨 <b>EMERGENCY SHUTDOWN IN PROGRESS...</b> 🚨\n\n"
        "⏳ Cancelling orders...",
        parse_mode=ParseMode.HTML
    )

    try:
        # Execute emergency shutdown
        logger.critical(f"🚨 EXECUTING EMERGENCY SHUTDOWN for chat {chat.id}")

        # Update progress
        await progress_msg.edit_text(
            "🚨 <b>EMERGENCY SHUTDOWN IN PROGRESS...</b> 🚨\n\n"
            "✅ Orders cancelled\n"
            "⏳ Closing positions...",
            parse_mode=ParseMode.HTML
        )

        # Execute shutdown
        success, summary_message = await execute_emergency_shutdown(include_mirror=True)

        # Send final summary
        await progress_msg.edit_text(
            summary_message,
            parse_mode=ParseMode.HTML
        )

        # Log completion
        if success:
            logger.critical(f"✅ EMERGENCY SHUTDOWN COMPLETED for chat {chat.id}")
        else:
            logger.critical(f"⚠️ EMERGENCY SHUTDOWN PARTIAL for chat {chat.id}")

    except Exception as e:
        logger.error(f"Error during emergency execution: {e}")
        await progress_msg.edit_text(
            f"❌ <b>EMERGENCY SHUTDOWN FAILED</b>\n\n"
            f"Error: {str(e)}\n\n"
            f"Please check your positions manually!",
            parse_mode=ParseMode.HTML
        )

    return ConversationHandler.END


async def emergency_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel emergency shutdown at any point"""
    # This handles any text message during emergency flow
    await update.message.reply_text(
        "❌ Emergency shutdown cancelled.",
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


# Create the conversation handler
emergency_conversation_handler = ConversationHandler(
    entry_points=[CommandHandler('emergency', emergency_command)],
    states={
        EMERGENCY_CONFIRM_1: [
            CallbackQueryHandler(emergency_confirm_1, pattern='^emergency_')
        ],
        EMERGENCY_CONFIRM_2: [
            CallbackQueryHandler(emergency_confirm_2, pattern='^emergency_execute$')
        ],
        EMERGENCY_PIN: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, emergency_pin_check)
        ]
    },
    fallbacks=[
        CommandHandler('cancel', emergency_cancel),
        MessageHandler(filters.COMMAND, emergency_cancel)
    ],
    conversation_timeout=30  # 30 second timeout for entire flow
)