#!/usr/bin/env python3
"""Test dashboard command to force enhanced UI"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from dashboard.generator_analytics_compact import build_mobile_dashboard_text
from dashboard.keyboards_analytics import build_enhanced_dashboard_keyboard
from utils.helpers import initialize_chat_data

logger = logging.getLogger(__name__)

async def test_dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command that forces the enhanced dashboard UI"""
    chat_id = update.effective_chat.id

    # Initialize chat data
    if context.chat_data is None:
        context.chat_data = {}
    initialize_chat_data(context.chat_data)

    logger.info(f"🧪 TEST DASHBOARD COMMAND for chat {chat_id}")

    try:
        # Build the enhanced dashboard
        dashboard_text = await build_mobile_dashboard_text(context.chat_data, context.application.bot_data)
        keyboard = build_enhanced_dashboard_keyboard()

        # Log first 500 chars to verify it's the enhanced UI
        logger.info(f"Dashboard preview: {dashboard_text[:500]}...")

        # Send the message
        await update.message.reply_text(
            dashboard_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )

        logger.info("✅ Enhanced dashboard sent successfully")

    except Exception as e:
        logger.error(f"Error in test dashboard: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Error displaying enhanced dashboard. Check logs.",
            parse_mode=ParseMode.HTML
        )