#!/usr/bin/env python3
"""
AI recommendation handlers for the trading bot.
"""
import logging
from decimal import Decimal
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config.constants import *
from utils.formatters import get_emoji
from dashboard.keyboards import build_margin_type_keyboard, build_order_strategy_keyboard
from .conversation import ask_next_field_in_conversation

logger = logging.getLogger(__name__)

async def handle_ai_recommendation_callback(q: CallbackQuery, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle callbacks for modifying AI recommendations"""
    try:
        await q.answer()
    except:
        pass
    
    if not q.data.startswith("ai_reco:"):
        return ConversationHandler.END
    
    parts = q.data.split(":", 2)
    if len(parts) < 3:
        return ConversationHandler.END
    
    _, param_type, current_value = parts
    
    if param_type == "margin_type":
        # Show margin type options
        kb = build_margin_type_keyboard("ai_modify_mt")
        prompt = (f"{get_emoji('money')} <b>Select Margin Type</b>\n\n"
                 f"Current: {'Fixed USDT' if current_value == 'fixed' else 'Percentage'}\n"
                 f"Choose your preferred margin type:")
        
        await q.message.edit_text(prompt, reply_markup=kb, parse_mode="HTML")
        return MODIFY_AI_MARGIN_TYPE
    
    elif param_type == "margin_value":
        # Ask for new margin value
        ai_reco = ctx.chat_data.get(AI_RECOMMENDATIONS_STORE, {})
        margin_type = ai_reco.get("margin_type", "fixed")
        
        if margin_type == "fixed":
            prompt = (f"{get_emoji('money')} <b>Enter Fixed Margin Amount</b>\n\n"
                     f"Current: {current_value} USDT\n"
                     f"Enter new USDT amount:")
        else:
            prompt = (f"％ <b>Enter Percentage Margin</b>\n\n"
                     f"Current: {current_value}%\n"
                     f"Enter new percentage (0-100):")
        
        ctx.chat_data[AWAITING_INPUT_FOR] = "ai_margin_value"
        await q.message.edit_text(prompt, parse_mode="HTML")
        return MODIFY_AI_MARGIN_VALUE
    
    elif param_type == "leverage":
        # Ask for new leverage
        max_lev = ctx.chat_data.get(MAX_LEVERAGE_FOR_SYMBOL, 100)
        prompt = (f"{get_emoji('rocket')} <b>Enter Leverage</b>\n\n"
                 f"Current: {current_value}x\n"
                 f"Enter new leverage (1-{max_lev}):")
        
        ctx.chat_data[AWAITING_INPUT_FOR] = "ai_leverage"
        await q.message.edit_text(prompt, parse_mode="HTML")
        return MODIFY_AI_LEVERAGE
    
    elif param_type == "strategy":
        # Show strategy options
        kb = build_order_strategy_keyboard("ai_modify_os")
        prompt = (f"{get_emoji('target')} <b>Select Order Strategy</b>\n\n"
                 f"Current: {'Market Only' if current_value == STRATEGY_MARKET_ONLY else 'Market + Limits'}\n"
                 f"Choose your preferred strategy:")
        
        await q.message.edit_text(prompt, reply_markup=kb, parse_mode="HTML")
        return MODIFY_AI_STRATEGY
    
    return ConversationHandler.END

async def handle_ai_margin_type_modification(q: CallbackQuery, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle margin type modification from AI recommendations"""
    try:
        await q.answer()
    except:
        pass
    
    if not q.data.startswith("ai_modify_mt:"):
        return ConversationHandler.END
    
    margin_type = q.data.split(":")[1]
    
    # Update AI recommendations
    ai_reco = ctx.chat_data.get(AI_RECOMMENDATIONS_STORE, {})
    ai_reco["margin_type"] = margin_type
    ctx.chat_data[AI_RECOMMENDATIONS_STORE] = ai_reco
    
    # Ask for value based on type
    if margin_type == "fixed":
        prompt = (f"{get_emoji('money')} <b>Enter Fixed Margin Amount</b>\n\n"
                 f"Enter USDT amount to use as margin:")
    else:
        prompt = (f"％ <b>Enter Percentage Margin</b>\n\n"
                 f"Enter percentage of balance to use (0-100):")
    
    ctx.chat_data[AWAITING_INPUT_FOR] = "ai_margin_value"
    await q.message.edit_text(prompt, parse_mode="HTML")
    return MODIFY_AI_MARGIN_VALUE

async def handle_ai_margin_value_input(upd, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle margin value input for AI recommendation modification"""
    try:
        value = Decimal(upd.message.text.strip())
        ai_reco = ctx.chat_data.get(AI_RECOMMENDATIONS_STORE, {})
        
        if ai_reco.get("margin_type") == "percentage" and (value <= 0 or value > 100):
            await upd.message.reply_text(f"{get_emoji('error')} Percentage must be between 0 and 100")
            return MODIFY_AI_MARGIN_VALUE
        elif value <= 0:
            await upd.message.reply_text(f"{get_emoji('error')} Amount must be greater than 0")
            return MODIFY_AI_MARGIN_VALUE
        
        # Update recommendation
        ai_reco["margin_value"] = str(value)
        ctx.chat_data[AI_RECOMMENDATIONS_STORE] = ai_reco
        ctx.chat_data[AWAITING_INPUT_FOR] = None
        
        # Delete user message
        try:
            await upd.message.delete()
        except:
            pass
        
        # Return to display recommendations
        from .conversation import display_ai_recommendations
        return await display_ai_recommendations(upd, ctx)
        
    except (ValueError, Exception) as e:
        await upd.message.reply_text(f"{get_emoji('error')} Invalid value. Please enter a number.")
        return MODIFY_AI_MARGIN_VALUE

async def handle_ai_leverage_input(upd, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle leverage input for AI recommendation modification"""
    try:
        leverage = int(upd.message.text.strip())
        max_lev = int(ctx.chat_data.get(MAX_LEVERAGE_FOR_SYMBOL, 100))
        
        if leverage < 1 or leverage > max_lev:
            await upd.message.reply_text(f"{get_emoji('error')} Leverage must be between 1 and {max_lev}")
            return MODIFY_AI_LEVERAGE
        
        # Update recommendation
        ai_reco = ctx.chat_data.get(AI_RECOMMENDATIONS_STORE, {})
        ai_reco["leverage"] = leverage
        ctx.chat_data[AI_RECOMMENDATIONS_STORE] = ai_reco
        ctx.chat_data[AWAITING_INPUT_FOR] = None
        
        # Delete user message
        try:
            await upd.message.delete()
        except:
            pass
        
        # Return to display recommendations
        from .conversation import display_ai_recommendations
        return await display_ai_recommendations(upd, ctx)
        
    except ValueError:
        await upd.message.reply_text(f"{get_emoji('error')} Please enter a valid whole number")
        return MODIFY_AI_LEVERAGE

async def handle_ai_strategy_modification(q: CallbackQuery, ctx: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle strategy modification from AI recommendations"""
    try:
        await q.answer()
    except:
        pass
    
    if not q.data.startswith("ai_modify_os:"):
        return ConversationHandler.END
    
    _, _, strategy = q.data.split(":", 2)
    
    # Update AI recommendations
    ai_reco = ctx.chat_data.get(AI_RECOMMENDATIONS_STORE, {})
    ai_reco["strategy"] = strategy
    ctx.chat_data[AI_RECOMMENDATIONS_STORE] = ai_reco
    
    # Return to display recommendations
    from .conversation import display_ai_recommendations
    return await display_ai_recommendations(q, ctx)