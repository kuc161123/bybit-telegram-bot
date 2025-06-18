#!/usr/bin/env python3
"""
Conversation flow handlers for trade setup - ENHANCED WITH CONSERVATIVE APPROACH.
ADDED: Dual trading approaches (Fast Market vs Conservative Limits)
ENHANCED: Support for 3 limit orders and 4 take profits in conservative mode
ADVANCED: Integration with sophisticated orphan protection system
FIXED: Coroutine serialization error in execute_trade_logic
UPDATED: Display enhanced trade execution messages
"""
import asyncio
import logging
from decimal import Decimal, InvalidOperation
from telegram import Update, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from html import escape
import uuid

from config.constants import *
from config.settings import LLM_PROVIDER
from utils.formatters import get_emoji, format_decimal_or_na, create_risk_meter, progress_bar
from utils.helpers import initialize_chat_data, get_field_emoji_and_name, safe_decimal_conversion
from utils.cache import get_instrument_info_cached, get_usdt_wallet_balance_cached
from risk.calculations import calculate_risk_reward_ratio
from dashboard.keyboards import *
from shared import msg_manager
from clients.bybit_helpers import protect_symbol_from_cleanup, protect_trade_group_from_cleanup  # ENHANCED: Import protection functions

logger = logging.getLogger(__name__)

# Define conversation states - ENHANCED with GGShot screenshot strategy
SYMBOL, SIDE, APPROACH_SELECTION, SCREENSHOT_UPLOAD, PRIMARY_ENTRY, LIMIT_ENTRIES, TAKE_PROFITS, STOP_LOSS, LEVERAGE, MARGIN, CONFIRMATION = range(11)

def build_conversation_keyboard(include_back=False, back_state=None, include_cancel=True):
    """Build conversation keyboard with optional back button"""
    buttons = []
    
    if include_back and back_state is not None:
        buttons.append([InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{back_state}")])
    
    if include_cancel:
        buttons.append([InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")])
    
    return InlineKeyboardMarkup(buttons) if buttons else None

def calculate_trade_pnl_preview(entry_price: Decimal, tp_price: Decimal, sl_price: Decimal, 
                               margin: Decimal, leverage: int, side: str) -> str:
    """Calculate simple USDT P&L preview for the trade"""
    try:
        # Calculate position size: (margin * leverage) / entry_price
        position_value = margin * leverage
        position_size = position_value / entry_price
        
        # Calculate profit if TP is hit
        if side == "Buy":
            tp_profit = (tp_price - entry_price) * position_size
            sl_loss = (sl_price - entry_price) * position_size
        else:  # Sell
            tp_profit = (entry_price - tp_price) * position_size
            sl_loss = (entry_price - sl_price) * position_size
        
        preview_text = f"\n💡 <b>TRADE P&L PREVIEW</b>\n"
        preview_text += f"{'─' * 20}\n"
        preview_text += f"🎯 <b>If TP Hit:</b> 🟢 +{format_decimal_or_na(tp_profit, 2)} USDT\n"
        preview_text += f"🛡️ <b>If SL Hit:</b> 🔴 {format_decimal_or_na(sl_loss, 2)} USDT\n"
        
        return preview_text
        
    except Exception as e:
        logger.error(f"Error calculating trade P&L preview: {e}")
        return ""

# =============================================
# MAIN ENTRY POINT - ENHANCED
# =============================================

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start enhanced trade setup conversation with dual approaches and protection system"""
    
    # Determine the source and chat info
    if update.callback_query:
        query = update.callback_query
        chat_id = query.message.chat.id
        user_id = query.from_user.id
        # Always answer the callback first
        try:
            await query.answer("🚀 Starting enhanced trade setup with protection system...")
        except:
            pass
        is_callback = True
    else:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        is_callback = False
    
    logger.info(f"Starting enhanced trade conversation with dual approaches and protection system for chat {chat_id}")
    
    # Initialize chat data
    if context.chat_data is None:
        context.chat_data = {}
    
    # Backup any existing monitor data
    monitor_backup = context.chat_data.get(ACTIVE_MONITOR_TASK, {})
    old_ui_msg_id = context.chat_data.get(LAST_UI_MESSAGE_ID)
    
    # Clear and reinitialize
    context.chat_data.clear()
    initialize_chat_data(context.chat_data)
    context.chat_data[ACTIVE_MONITOR_TASK] = monitor_backup
    
    # Delete old UI message if exists
    if old_ui_msg_id:
        try:
            await context.bot.delete_message(chat_id, old_ui_msg_id)
        except:
            pass
    
    # Create enhanced welcome message with GGShot
    welcome_msg = (
        f"{get_emoji('rocket')} <b>ENHANCED TRADE SETUP</b> {get_emoji('lightning')}\n\n"
        f"Set up your trade with our advanced trading system!\n\n"
        f"🛡️ <b>Advanced protection system prevents order cleanup</b>\n"
        f"⚡ <b>Fast Market:</b> Instant execution with single TP/SL\n"
        f"🛡️ <b>Conservative Limits:</b> 3 entries + 4 take profits\n"
        f"📸 <b>GGShot Screenshot:</b> AI extracts trade parameters\n\n"
        f"📈 <b>Step 1 of 8: Trading Symbol</b>\n\n"
        f"Enter the symbol you want to trade:\n"
        f"💡 Examples: <code>BTCUSDT</code>, <code>ETHUSDT</code>, <code>SOLUSDT</code>\n\n"
        f"Type the symbol and press send..."
    )
    
    # Build cancel keyboard
    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")],
        [InlineKeyboardButton("📊 Back to Dashboard", callback_data="refresh_dashboard")]
    ])
    
    try:
        if is_callback and update.callback_query.message:
            # Try to edit the callback message first
            try:
                await update.callback_query.edit_message_text(
                    welcome_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=cancel_keyboard
                )
                context.chat_data[LAST_UI_MESSAGE_ID] = update.callback_query.message.message_id
                logger.info(f"Successfully edited callback message for chat {chat_id}")
            except Exception as e_edit:
                logger.warning(f"Could not edit callback message: {e_edit}, sending new message")
                # If edit fails, send new message
                sent_msg = await context.bot.send_message(
                    chat_id,
                    welcome_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=cancel_keyboard
                )
                context.chat_data[LAST_UI_MESSAGE_ID] = sent_msg.message_id
        else:
            # Send new message for non-callback scenarios
            sent_msg = await context.bot.send_message(
                chat_id,
                welcome_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard
            )
            context.chat_data[LAST_UI_MESSAGE_ID] = sent_msg.message_id
        
        logger.info(f"Enhanced trade conversation started successfully for chat {chat_id}")
        return SYMBOL
        
    except Exception as e:
        logger.error(f"Error starting conversation for chat {chat_id}: {e}")
        # Fallback: send a simple message
        try:
            await context.bot.send_message(
                chat_id,
                f"{get_emoji('error')} Error starting trade setup. Please try again with /start",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        return ConversationHandler.END

# =============================================
# SYMBOL HANDLER - ENHANCED WITH PROTECTION
# =============================================

async def symbol_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle symbol input with enhanced protection system"""
    if not update.message or not update.message.text:
        return SYMBOL
    
    user_input = update.message.text.strip().upper()
    chat_id = update.effective_chat.id
    
    logger.info(f"Processing symbol input: {user_input}")
    
    # Delete user's message
    try:
        await update.message.delete()
    except:
        pass
    
    # Validate symbol
    if not user_input:
        await send_error_and_retry(
            context, chat_id, 
            "Symbol cannot be empty. Please enter a valid symbol:",
            SYMBOL
        )
        return SYMBOL
    
    # Show validation message
    await edit_last_message(
        context, chat_id,
        f"{get_emoji('loading')} Validating symbol <code>{escape(user_input)}</code>...",
        None
    )
    
    # Check if symbol exists
    try:
        inst_info = await get_instrument_info_cached(user_input)
        if not inst_info:
            await send_error_and_retry(
                context, chat_id,
                f"❌ Invalid symbol: <code>{escape(user_input)}</code>\n\n"
                f"Please enter a valid USDT perpetual contract symbol:",
                SYMBOL
            )
            return SYMBOL
    except Exception as e:
        logger.error(f"Error validating symbol: {e}")
        await send_error_and_retry(
            context, chat_id,
            f"❌ Error validating symbol. Please try again:",
            SYMBOL
        )
        return SYMBOL
    
    # PROTECTION: Immediately protect the symbol once it's validated
    try:
        protect_symbol_from_cleanup(user_input)
        logger.info(f"🛡️ Symbol {user_input} protected from cleanup during conversation")
    except Exception as e:
        logger.error(f"Error protecting symbol: {e}")
        # Continue anyway, this is not critical for trade setup
    
    # Store symbol with multiple key formats for compatibility
    context.chat_data["symbol"] = user_input
    context.chat_data[SYMBOL] = user_input
    context.chat_data["SYMBOL"] = user_input  # Backup
    
    # Store instrument info with proper error handling
    try:
        context.chat_data[INSTRUMENT_TICK_SIZE] = safe_decimal_conversion(inst_info["priceFilter"]["tickSize"])
        context.chat_data[INSTRUMENT_QTY_STEP] = safe_decimal_conversion(inst_info["lotSizeFilter"]["qtyStep"])
        context.chat_data[MIN_ORDER_QTY] = safe_decimal_conversion(inst_info["lotSizeFilter"].get("minOrderQty", "0"))
        context.chat_data[MIN_ORDER_NOTIONAL_VALUE] = safe_decimal_conversion(inst_info["lotSizeFilter"].get("minNotional", "0"))
        context.chat_data[MAX_LEVERAGE_FOR_SYMBOL] = safe_decimal_conversion(inst_info.get("leverageFilter", {}).get("maxLeverage", "100"))
        
        logger.info(f"Instrument info stored: tickSize={context.chat_data[INSTRUMENT_TICK_SIZE]}, qtyStep={context.chat_data[INSTRUMENT_QTY_STEP]}")
    except Exception as e:
        logger.error(f"Error parsing instrument info: {e}")
        # Set safe defaults
        context.chat_data[MAX_LEVERAGE_FOR_SYMBOL] = Decimal("100")
        context.chat_data[MIN_ORDER_QTY] = Decimal("0")
        context.chat_data[MIN_ORDER_NOTIONAL_VALUE] = Decimal("0")
        context.chat_data[INSTRUMENT_TICK_SIZE] = Decimal("0.01")
        context.chat_data[INSTRUMENT_QTY_STEP] = Decimal("0.01")
    
    # Ask for side
    side_msg = (
        f"✅ <b>Symbol:</b> <code>{user_input}</code> 🛡️\n\n"
        f"📈 <b>Step 2 of 7: Trade Direction</b>\n\n"
        f"Choose your trading direction:"
    )
    
    side_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📈 LONG (Buy)", callback_data="conv_side:Buy")],
        [InlineKeyboardButton(f"📉 SHORT (Sell)", callback_data="conv_side:Sell")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{SYMBOL}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")]
    ])
    
    await edit_last_message(context, chat_id, side_msg, side_keyboard)
    return SIDE

# =============================================
# SIDE HANDLER  
# =============================================

async def side_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle side selection via callback"""
    # This should be handled by callback, not text input
    # If we get here via text, it's an error
    if update.message:
        await update.message.delete()
        await send_error_and_retry(
            context, update.effective_chat.id,
            "Please use the buttons to select your trading direction:",
            SIDE
        )
    return SIDE

async def handle_side_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle side selection callback and move to approach selection"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    if not query.data.startswith("conv_side:"):
        return SIDE
    
    side = query.data.split(":")[1]
    
    # Store side with multiple key formats
    context.chat_data["side"] = side
    context.chat_data[SIDE] = side
    context.chat_data["SIDE"] = side  # Backup
    
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    
    # ENHANCED: Ask for trading approach selection including GGShot
    approach_msg = (
        f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
        f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n\n"
        f"🎯 <b>Step 3 of 8: Trading Approach</b>\n\n"
        f"Choose your trading strategy:\n\n"
        f"⚡ <b>Fast Market</b>\n"
        f"• Single entry at market price\n"
        f"• One take profit (100% close)\n"
        f"• Best for quick moves\n\n"
        f"🛡️ <b>Conservative Limits</b>\n"
        f"• 3 limit orders (equal allocation)\n"
        f"• 4 take profits (70%, 10%, 10%, 10%)\n"
        f"• Better risk management\n\n"
        f"📸 <b>GGShot Screenshot</b>\n"
        f"• Upload trading screenshot\n"
        f"• AI extracts trade parameters\n"
        f"• Auto-populate setup\n"
        f"• Smart strategy detection\n\n"
        f"Select your preferred approach:"
    )
    
    approach_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ Fast Market", callback_data="conv_approach:fast")],
        [InlineKeyboardButton(f"🛡️ Conservative Limits", callback_data="conv_approach:conservative")],
        [InlineKeyboardButton(f"📸 GGShot Screenshot", callback_data="conv_approach:ggshot")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{SIDE}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")]
    ])
    
    try:
        await query.edit_message_text(
            approach_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=approach_keyboard
        )
    except Exception as e:
        logger.error(f"Error editing message in handle_side_callback: {e}")
        # Send new message if edit fails
        sent = await context.bot.send_message(
            query.message.chat.id,
            approach_msg,
            parse_mode=ParseMode.HTML,
            reply_markup=approach_keyboard
        )
        context.chat_data[LAST_UI_MESSAGE_ID] = sent.message_id
    
    return APPROACH_SELECTION

# =============================================
# ENHANCED: APPROACH SELECTION HANDLER WITH PROTECTION
# =============================================

async def approach_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle approach selection via callback"""
    if update.message:
        await update.message.delete()
        await send_error_and_retry(
            context, update.effective_chat.id,
            "Please use the buttons to select your trading approach:",
            APPROACH_SELECTION
        )
    return APPROACH_SELECTION

async def handle_approach_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle trading approach selection callback with protection system integration"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    if not query.data.startswith("conv_approach:"):
        return APPROACH_SELECTION
    
    approach = query.data.split(":")[1]
    
    # Store approach selection
    context.chat_data[TRADING_APPROACH] = approach
    
    # Generate unique trade group ID for conservative approach
    if approach == "conservative":
        trade_group_id = str(uuid.uuid4())[:8]
        context.chat_data[CONSERVATIVE_TRADE_GROUP_ID] = trade_group_id
        context.chat_data[ORDER_STRATEGY] = STRATEGY_CONSERVATIVE_LIMITS
        
        # PROTECTION: Protect the trade group from cleanup
        try:
            protect_trade_group_from_cleanup(trade_group_id)
            logger.info(f"🛡️ Trade group {trade_group_id} protected from cleanup during conversation")
        except Exception as e:
            logger.error(f"Error protecting trade group: {e}")
            # Continue anyway, this is not critical for trade setup
    elif approach == "ggshot":
        # GGShot approach - will determine strategy after AI analysis
        context.chat_data[ORDER_STRATEGY] = None  # Will be set after screenshot analysis
    else:
        context.chat_data[ORDER_STRATEGY] = STRATEGY_MARKET_ONLY
    
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    side = context.chat_data.get(SIDE, "Buy")
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    
    if approach == "fast":
        approach_emoji = "⚡"
        approach_text = "Fast Market"
    elif approach == "conservative":
        approach_emoji = "🛡️"
        approach_text = "Conservative Limits"
    elif approach == "ggshot":
        approach_emoji = "📸"
        approach_text = "GGShot Screenshot"
    
    if approach == "fast":
        # Fast approach - ask for single entry price
        entry_msg = (
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Approach:</b> {approach_emoji} {approach_text}\n\n"
            f"💰 <b>Step 4 of 7: Entry Price</b>\n\n"
            f"Enter your market entry price:\n"
            f"💡 Example: <code>65000.50</code>\n\n"
            f"🛡️ Orders will be protected from cleanup"
        )
        
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
            [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
        ])
        
        try:
            await query.edit_message_text(
                entry_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message for fast approach: {e}")
        
        return PRIMARY_ENTRY
    
    elif approach == "conservative":
        # Conservative approach - ask for 3 limit order prices
        trade_group_id = context.chat_data.get(CONSERVATIVE_TRADE_GROUP_ID, "Unknown")
        
        limit_msg = (
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Approach:</b> {approach_emoji} {approach_text}\n"
            f"✅ <b>Trade Group:</b> {trade_group_id} 🛡️\n\n"
            f"📊 <b>Step 4 of 8: Limit Order Prices</b>\n\n"
            f"Enter 3 limit order prices (one per message):\n"
            f"💡 Each order will use 33.33% of your capital\n"
            f"💡 Enter them in order of preference\n"
            f"🛡️ All orders will be protected from cleanup\n\n"
            f"Enter <b>Limit Order #1</b> price:"
        )
        
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
            [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
        ])
        
        try:
            await query.edit_message_text(
                limit_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message for conservative approach: {e}")
        
        # Initialize limit order tracking
        context.chat_data["limit_orders_entered"] = 0
        
        return LIMIT_ENTRIES
    
    elif approach == "ggshot":
        # GGShot approach - ask for screenshot upload
        screenshot_msg = (
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Approach:</b> {approach_emoji} {approach_text}\n\n"
            f"📸 <b>Step 4 of 8: Upload Screenshot</b>\n\n"
            f"Upload your trading screenshot:\n\n"
            f"📋 <b>What to include:</b>\n"
            f"• Entry price(s)\n"
            f"• Take profit level(s)\n"
            f"• Stop loss level\n"
            f"• Clear price labels\n\n"
            f"🤖 AI will analyze and extract trade parameters automatically\n"
            f"🛡️ All extracted orders will be protected from cleanup\n\n"
            f"📤 <b>Send your screenshot now...</b>"
        )
        
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
            [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
        ])
        
        try:
            await query.edit_message_text(
                screenshot_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message for GGShot approach: {e}")
        
        return SCREENSHOT_UPLOAD

# =============================================
# SCREENSHOT UPLOAD HANDLER (GGShot Approach)
# =============================================

async def screenshot_upload_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle screenshot upload and AI analysis for GGShot approach"""
    if not update.message:
        return SCREENSHOT_UPLOAD
    
    chat_id = update.effective_chat.id
    
    # Check if user sent a photo
    if update.message.photo:
        try:
            # Get the highest quality photo
            photo = update.message.photo[-1]
            
            # Validate file size (Telegram limit is 20MB, but we'll use 10MB for safety)
            if photo.file_size > 10 * 1024 * 1024:  # 10MB
                await send_error_and_retry(
                    context, chat_id,
                    "📷 Screenshot is too large (>10MB).\n\nPlease upload a smaller image:",
                    SCREENSHOT_UPLOAD
                )
                return SCREENSHOT_UPLOAD
            
            # Show processing message
            await edit_last_message(
                context, chat_id,
                f"{get_emoji('loading')} <b>Processing Screenshot...</b>\n\n"
                f"🤖 AI is analyzing your trading setup\n"
                f"📊 Extracting trade parameters\n"
                f"⏳ This may take a few seconds...",
                None
            )
            
            photo_file = await context.bot.get_file(photo.file_id)
            
            # Store screenshot info for processing
            context.chat_data["screenshot_file_id"] = photo.file_id
            context.chat_data["screenshot_file_path"] = photo_file.file_path
            
            # Real AI analysis using OpenAI Vision API
            from utils.screenshot_analyzer import analyze_trading_screenshot
            
            symbol = context.chat_data.get(SYMBOL, "BTCUSDT")
            side = context.chat_data.get(SIDE, "Buy")
            
            # Analyze screenshot with OpenAI Vision API
            extracted_data = await analyze_trading_screenshot(photo_file.file_path, symbol, side)
            
            if extracted_data.get("success"):
                # Store extracted parameters
                context.chat_data.update(extracted_data["parameters"])
                
                # Show extracted parameters for confirmation
                return await show_extracted_parameters_confirmation(context, chat_id, extracted_data)
            else:
                # AI analysis failed - offer manual entry
                return await handle_screenshot_analysis_failure(context, chat_id, extracted_data.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Error processing screenshot: {e}")
            await send_error_and_retry(
                context, chat_id,
                f"Error processing screenshot: {escape(str(e))}\n\nPlease try uploading again or use manual entry:",
                SCREENSHOT_UPLOAD
            )
            return SCREENSHOT_UPLOAD
    
    # User sent text instead of photo
    elif update.message.text:
        # Delete user's message
        try:
            await update.message.delete()
        except:
            pass
        
        await send_error_and_retry(
            context, chat_id,
            "Please upload a screenshot image, not text.\n\nSend a photo of your trading setup:",
            SCREENSHOT_UPLOAD
        )
        return SCREENSHOT_UPLOAD
    
    else:
        # Some other message type
        await send_error_and_retry(
            context, chat_id,
            "Please upload a screenshot image.\n\nSend a photo of your trading setup:",
            SCREENSHOT_UPLOAD
        )
        return SCREENSHOT_UPLOAD

async def mock_ai_screenshot_analysis(chat_data: dict) -> dict:
    """Mock AI analysis function - replace with real OpenAI Vision API call"""
    # Simulate AI processing
    await asyncio.sleep(1)
    
    # Mock extracted parameters based on symbol/side already selected
    symbol = chat_data.get(SYMBOL, "BTCUSDT")
    side = chat_data.get(SIDE, "Buy")
    
    # Return mock analysis results
    if side == "Buy":
        # Mock long trade
        return {
            "success": True,
            "confidence": 0.85,
            "strategy_type": "conservative",  # or "fast"
            "parameters": {
                PRIMARY_ENTRY_PRICE: Decimal("65000"),
                LIMIT_ENTRY_1_PRICE: Decimal("64800"),
                LIMIT_ENTRY_2_PRICE: Decimal("64600"),
                LIMIT_ENTRY_3_PRICE: Decimal("64400"),
                TP1_PRICE: Decimal("66500"),
                TP2_PRICE: Decimal("67000"),
                TP3_PRICE: Decimal("67500"),
                TP4_PRICE: Decimal("68000"),
                SL_PRICE: Decimal("63000"),
                "leverage": 10,
                "margin_amount": Decimal("100")
            }
        }
    else:
        # Mock short trade
        return {
            "success": True,
            "confidence": 0.80,
            "strategy_type": "fast",
            "parameters": {
                PRIMARY_ENTRY_PRICE: Decimal("65000"),
                TP1_PRICE: Decimal("64000"),
                SL_PRICE: Decimal("66000"),
                "leverage": 10,
                "margin_amount": Decimal("100")
            }
        }

async def show_extracted_parameters_confirmation(context: ContextTypes.DEFAULT_TYPE, chat_id: int, extracted_data: dict) -> int:
    """Show extracted parameters and ask for confirmation"""
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    side = context.chat_data.get(SIDE, "Buy")
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    
    confidence = extracted_data.get("confidence", 0.0)
    strategy_type = extracted_data.get("strategy_type", "fast")
    params = extracted_data.get("parameters", {})
    validation_errors = extracted_data.get("validation_errors", [])
    
    # Check if validation failed
    if validation_errors:
        # Show validation errors
        from utils.ggshot_validator import ggshot_validator
        error_report = ggshot_validator.format_validation_report(validation_errors, params, side)
        
        error_msg = (
            f"🤖 <b>AI ANALYSIS COMPLETE</b> 📸\n"
            f"{'═' * 25}\n\n"
            f"✅ <b>Extraction Successful</b>\n"
            f"❌ <b>Validation Failed</b>\n\n"
            f"{error_report}\n\n"
            f"🔄 <b>Options:</b>\n"
            f"• Upload a clearer screenshot\n"
            f"• Override and continue anyway\n"
            f"• Switch to manual entry"
        )
        
        validation_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ Override & Continue", callback_data="ggshot_override_validation")],
            [InlineKeyboardButton("📸 Upload New Screenshot", callback_data="ggshot_retry_upload")],
            [InlineKeyboardButton("✏️ Manual Entry", callback_data="ggshot_manual_entry")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")]
        ])
        
        await edit_last_message(context, chat_id, error_msg, validation_keyboard)
        return CONFIRMATION
    
    # Update approach based on AI detection
    if strategy_type == "conservative":
        context.chat_data[TRADING_APPROACH] = "conservative"
        context.chat_data[ORDER_STRATEGY] = STRATEGY_CONSERVATIVE_LIMITS
        # Generate trade group ID for conservative approach
        trade_group_id = str(uuid.uuid4())[:8]
        context.chat_data[CONSERVATIVE_TRADE_GROUP_ID] = trade_group_id
        try:
            protect_trade_group_from_cleanup(trade_group_id)
        except Exception as e:
            logger.error(f"Error protecting trade group: {e}")
    else:
        context.chat_data[TRADING_APPROACH] = "fast"
        context.chat_data[ORDER_STRATEGY] = STRATEGY_MARKET_ONLY
    
    # Build confirmation message based on detected strategy
    if strategy_type == "conservative":
        confirmation_msg = (
            f"🤖 <b>AI ANALYSIS COMPLETE</b> 📸\n"
            f"{'═' * 25}\n\n"
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Detected Strategy:</b> 🛡️ Conservative Limits\n"
            f"✅ <b>AI Confidence:</b> {confidence:.0%}\n\n"
            f"📊 <b>EXTRACTED PARAMETERS:</b>\n\n"
            f"🔹 <b>Limit Orders:</b>\n"
            f"• Entry #1: <code>{format_decimal_or_na(params.get(LIMIT_ENTRY_1_PRICE))}</code>\n"
            f"• Entry #2: <code>{format_decimal_or_na(params.get(LIMIT_ENTRY_2_PRICE))}</code>\n"
            f"• Entry #3: <code>{format_decimal_or_na(params.get(LIMIT_ENTRY_3_PRICE))}</code>\n\n"
            f"🎯 <b>Take Profits:</b>\n"
            f"• TP1 (70%): <code>{format_decimal_or_na(params.get(TP1_PRICE))}</code>\n"
            f"• TP2 (10%): <code>{format_decimal_or_na(params.get(TP2_PRICE))}</code>\n"
            f"• TP3 (10%): <code>{format_decimal_or_na(params.get(TP3_PRICE))}</code>\n"
            f"• TP4 (10%): <code>{format_decimal_or_na(params.get(TP4_PRICE))}</code>\n\n"
            f"🛡️ <b>Stop Loss:</b> <code>{format_decimal_or_na(params.get(SL_PRICE))}</code>\n\n"
            f"💡 <i>Next: You'll set your leverage and margin preferences</i>\n\n"
            f"❓ <b>Accept AI prices and continue?</b>"
        )
    else:
        confirmation_msg = (
            f"🤖 <b>AI ANALYSIS COMPLETE</b> 📸\n"
            f"{'═' * 25}\n\n"
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Detected Strategy:</b> ⚡ Fast Market\n"
            f"✅ <b>AI Confidence:</b> {confidence:.0%}\n\n"
            f"📊 <b>EXTRACTED PARAMETERS:</b>\n\n"
            f"💰 <b>Entry Price:</b> <code>{format_decimal_or_na(params.get(PRIMARY_ENTRY_PRICE))}</code>\n"
            f"🎯 <b>Take Profit:</b> <code>{format_decimal_or_na(params.get(TP1_PRICE))}</code> (100%)\n"
            f"🛡️ <b>Stop Loss:</b> <code>{format_decimal_or_na(params.get(SL_PRICE))}</code>\n\n"
            f"💡 <i>Next: You'll set your leverage and margin preferences</i>\n\n"
            f"❓ <b>Accept AI prices and continue?</b>"
        )
    
    confirmation_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Accept Prices & Continue", callback_data="ggshot_confirm_ai")],
        [InlineKeyboardButton("✏️ Manual Override", callback_data="ggshot_manual_override")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")]
    ])
    
    await edit_last_message(context, chat_id, confirmation_msg, confirmation_keyboard)
    return CONFIRMATION

async def handle_screenshot_analysis_failure(context: ContextTypes.DEFAULT_TYPE, chat_id: int, error_msg: str) -> int:
    """Handle AI analysis failure and offer alternatives"""
    # Escape HTML special characters in error message
    safe_error_msg = escape(error_msg) if error_msg else "Unknown error"
    
    failure_msg = (
        f"❌ <b>AI Analysis Failed</b>\n\n"
        f"Error: {safe_error_msg}\n\n"
        f"🔄 <b>Options:</b>\n"
        f"• Try uploading a clearer screenshot\n"
        f"• Switch to manual entry\n\n"
        f"What would you like to do?"
    )
    
    failure_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Upload Again", callback_data="ggshot_retry_upload")],
        [InlineKeyboardButton("✏️ Manual Entry", callback_data="ggshot_manual_entry")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")]
    ])
    
    await edit_last_message(context, chat_id, failure_msg, failure_keyboard)
    return SCREENSHOT_UPLOAD

# =============================================
# GGSHOT CALLBACK HANDLERS
# =============================================

async def handle_ggshot_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle GGShot specific callback queries"""
    query = update.callback_query
    if not query:
        return CONFIRMATION
        
    try:
        await query.answer()
    except:
        pass
    
    if query.data == "ggshot_confirm_ai":
        # User confirmed AI extracted parameters - now ask for leverage
        symbol = context.chat_data.get(SYMBOL, "Unknown")
        side = context.chat_data.get(SIDE, "Buy")
        direction_emoji = "📈" if side == "Buy" else "📉"
        direction_text = "LONG" if side == "Buy" else "SHORT"
        approach = context.chat_data.get(TRADING_APPROACH, "fast")
        approach_emoji = "⚡" if approach == "fast" else "🛡️"
        approach_text = "Fast Market" if approach == "fast" else "Conservative Limits"
        
        # Get max leverage and show leverage selection
        max_leverage = context.chat_data.get(MAX_LEVERAGE_FOR_SYMBOL, 100)
        
        leverage_msg = (
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Approach:</b> {approach_emoji} {approach_text}\n"
            f"✅ <b>AI Prices:</b> 📸 Extracted\n\n"
            f"⚡ <b>Step 5 of 7: Select Leverage</b>\n\n"
            f"Choose your leverage for this trade:\n"
            f"💡 Higher leverage = higher risk & reward\n"
            f"🛡️ Maximum for {symbol}: {max_leverage}x"
        )
        
        from dashboard.keyboards import build_leverage_selection_keyboard
        leverage_keyboard = build_leverage_selection_keyboard(max_leverage)
        
        await edit_last_message(context, query.message.chat.id, leverage_msg, leverage_keyboard)
        return LEVERAGE
    
    elif query.data == "ggshot_manual_override":
        # User wants to manually override AI parameters
        approach = context.chat_data.get(TRADING_APPROACH, "fast")
        
        if approach == "fast":
            # Go to fast approach flow
            return await ask_for_fast_take_profit(context, query.message.chat.id)
        else:
            # Go to conservative approach flow
            return await ask_for_conservative_take_profits(context, query.message.chat.id)
    
    elif query.data == "ggshot_retry_upload":
        # User wants to upload a new screenshot
        return await retry_screenshot_upload(context, query.message.chat.id)
    
    elif query.data == "ggshot_manual_entry":
        # User wants to switch to manual entry - ask which approach
        return await offer_manual_approach_selection(context, query.message.chat.id)
    
    elif query.data == "ggshot_override_validation":
        # User wants to override validation errors and continue
        symbol = context.chat_data.get(SYMBOL, "Unknown")
        side = context.chat_data.get(SIDE, "Buy")
        direction_emoji = "📈" if side == "Buy" else "📉"
        direction_text = "LONG" if side == "Buy" else "SHORT"
        approach = context.chat_data.get(TRADING_APPROACH, "fast")
        approach_emoji = "⚡" if approach == "fast" else "🛡️"
        approach_text = "Fast Market" if approach == "fast" else "Conservative Limits"
        
        # Get max leverage and show leverage selection
        max_leverage = context.chat_data.get(MAX_LEVERAGE_FOR_SYMBOL, 100)
        
        override_msg = (
            f"⚠️ <b>VALIDATION OVERRIDE</b>\n\n"
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Approach:</b> {approach_emoji} {approach_text}\n"
            f"⚠️ <b>AI Prices:</b> 📸 Extracted (Unvalidated)\n\n"
            f"⚡ <b>Step 5 of 7: Select Leverage</b>\n\n"
            f"Choose your leverage for this trade:\n"
            f"💡 Higher leverage = higher risk & reward\n"
            f"🛡️ Maximum for {symbol}: {max_leverage}x\n\n"
            f"🚨 <b>WARNING:</b> Proceeding with unvalidated parameters!"
        )
        
        from dashboard.keyboards import build_leverage_selection_keyboard
        leverage_keyboard = build_leverage_selection_keyboard(max_leverage)
        
        await edit_last_message(context, query.message.chat.id, override_msg, leverage_keyboard)
        return LEVERAGE
    
    return CONFIRMATION

async def retry_screenshot_upload(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Allow user to retry screenshot upload"""
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    side = context.chat_data.get(SIDE, "Buy")
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    
    retry_msg = (
        f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
        f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
        f"✅ <b>Approach:</b> 📸 GGShot Screenshot\n\n"
        f"📸 <b>Upload New Screenshot</b>\n\n"
        f"📋 <b>Tips for better analysis:</b>\n"
        f"• Clear, high-resolution image\n"
        f"• All price levels visible\n"
        f"• Good contrast and lighting\n"
        f"• Minimal clutter around trade setup\n\n"
        f"📤 <b>Send your screenshot now...</b>"
    )
    
    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
        [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
    ])
    
    await edit_last_message(context, chat_id, retry_msg, cancel_keyboard)
    return SCREENSHOT_UPLOAD

async def offer_manual_approach_selection(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Offer manual approach selection after GGShot failure"""
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    side = context.chat_data.get(SIDE, "Buy")
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    
    manual_msg = (
        f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
        f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n\n"
        f"✏️ <b>Manual Entry Mode</b>\n\n"
        f"Choose your manual trading approach:\n\n"
        f"⚡ <b>Fast Market</b>\n"
        f"• Single entry + single TP\n"
        f"• Quick setup\n\n"
        f"🛡️ <b>Conservative Limits</b>\n"
        f"• 3 limit orders + 4 TPs\n"
        f"• Advanced risk management\n\n"
        f"Select your preferred approach:"
    )
    
    manual_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚡ Fast Market", callback_data="conv_approach:fast")],
        [InlineKeyboardButton(f"🛡️ Conservative Limits", callback_data="conv_approach:conservative")],
        [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")]
    ])
    
    await edit_last_message(context, chat_id, manual_msg, manual_keyboard)
    return APPROACH_SELECTION

# =============================================
# PRIMARY ENTRY HANDLER (Fast Approach)
# =============================================

async def primary_entry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle primary entry price input for fast approach"""
    if not update.message or not update.message.text:
        return PRIMARY_ENTRY
    
    chat_id = update.effective_chat.id
    
    # Delete user's message
    try:
        await update.message.delete()
    except:
        pass
    
    try:
        price = Decimal(update.message.text.strip())
        if price <= 0:
            await send_error_and_retry(
                context, chat_id,
                "Entry price must be greater than 0. Please enter a valid price:",
                PRIMARY_ENTRY
            )
            return PRIMARY_ENTRY
        
        # Store primary entry with multiple key formats
        context.chat_data["primary_entry_price"] = price
        context.chat_data[PRIMARY_ENTRY_PRICE] = price
        context.chat_data["PRIMARY_ENTRY_PRICE"] = price  # Backup
        
        # Ask for SINGLE take profit (100% close) for fast approach
        return await ask_for_fast_take_profit(context, chat_id)
        
    except (ValueError, InvalidOperation):
        await send_error_and_retry(
            context, chat_id,
            "Please enter a valid number for the entry price:",
            PRIMARY_ENTRY
        )
        return PRIMARY_ENTRY

# =============================================
# ENHANCED: LIMIT ENTRIES HANDLER (Conservative Approach)
# =============================================

async def limit_entries_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle limit order price inputs for conservative approach"""
    if not update.message or not update.message.text:
        return LIMIT_ENTRIES
    
    chat_id = update.effective_chat.id
    
    # Delete user's message
    try:
        await update.message.delete()
    except:
        pass
    
    try:
        price = Decimal(update.message.text.strip())
        if price <= 0:
            await send_error_and_retry(
                context, chat_id,
                "Limit price must be greater than 0. Please enter a valid price:",
                LIMIT_ENTRIES
            )
            return LIMIT_ENTRIES
        
        # Track which limit order we're entering
        orders_entered = context.chat_data.get("limit_orders_entered", 0)
        
        if orders_entered == 0:
            context.chat_data[LIMIT_ENTRY_1_PRICE] = price
            context.chat_data["limit_orders_entered"] = 1
            
            # Ask for second limit order
            symbol = context.chat_data.get(SYMBOL, "Unknown")
            side = context.chat_data.get(SIDE, "Buy")
            trade_group_id = context.chat_data.get(CONSERVATIVE_TRADE_GROUP_ID, "Unknown")
            direction_emoji = "📈" if side == "Buy" else "📉"
            direction_text = "LONG" if side == "Buy" else "SHORT"
            
            limit2_msg = (
                f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
                f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
                f"✅ <b>Approach:</b> 🛡️ Conservative Limits\n"
                f"✅ <b>Trade Group:</b> {trade_group_id} 🛡️\n"
                f"✅ <b>Limit #1:</b> <code>{format_decimal_or_na(price)}</code>\n\n"
                f"📊 <b>Step 4 of 7: Limit Order Prices</b>\n\n"
                f"Enter <b>Limit Order #2</b> price:"
            )
            
            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
                [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
            ])
            
            await edit_last_message(context, chat_id, limit2_msg, cancel_keyboard)
            return LIMIT_ENTRIES
            
        elif orders_entered == 1:
            context.chat_data[LIMIT_ENTRY_2_PRICE] = price
            context.chat_data["limit_orders_entered"] = 2
            
            # Ask for third limit order
            symbol = context.chat_data.get(SYMBOL, "Unknown")
            side = context.chat_data.get(SIDE, "Buy")
            trade_group_id = context.chat_data.get(CONSERVATIVE_TRADE_GROUP_ID, "Unknown")
            direction_emoji = "📈" if side == "Buy" else "📉"
            direction_text = "LONG" if side == "Buy" else "SHORT"
            limit1_price = context.chat_data.get(LIMIT_ENTRY_1_PRICE)
            
            limit3_msg = (
                f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
                f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
                f"✅ <b>Approach:</b> 🛡️ Conservative Limits\n"
                f"✅ <b>Trade Group:</b> {trade_group_id} 🛡️\n"
                f"✅ <b>Limit #1:</b> <code>{format_decimal_or_na(limit1_price)}</code>\n"
                f"✅ <b>Limit #2:</b> <code>{format_decimal_or_na(price)}</code>\n\n"
                f"📊 <b>Step 4 of 7: Limit Order Prices</b>\n\n"
                f"Enter <b>Limit Order #3</b> price:"
            )
            
            cancel_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{APPROACH_SELECTION}")],
                [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
            ])
            
            await edit_last_message(context, chat_id, limit3_msg, cancel_keyboard)
            return LIMIT_ENTRIES
            
        elif orders_entered == 2:
            context.chat_data[LIMIT_ENTRY_3_PRICE] = price
            context.chat_data["limit_orders_entered"] = 3
            
            # All 3 limit orders entered, move to take profits
            return await ask_for_conservative_take_profits(context, chat_id)
        
    except (ValueError, InvalidOperation):
        await send_error_and_retry(
            context, chat_id,
            "Please enter a valid number for the limit price:",
            LIMIT_ENTRIES
        )
        return LIMIT_ENTRIES

# =============================================
# TAKE PROFITS HANDLER - ENHANCED FOR DUAL APPROACHES
# =============================================

async def ask_for_fast_take_profit(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Ask for single take profit in fast approach"""
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    side = context.chat_data.get(SIDE, "Buy")
    entry_price = context.chat_data.get(PRIMARY_ENTRY_PRICE, Decimal("0"))
    
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    
    tp_msg = (
        f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
        f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
        f"✅ <b>Approach:</b> ⚡ Fast Market\n"
        f"✅ <b>Entry Price:</b> <code>{format_decimal_or_na(entry_price)}</code>\n\n"
        f"🎯 <b>Step 5 of 7: Take Profit</b>\n\n"
        f"Enter your take profit price:\n"
        f"💡 This will close 100% of your position\n"
        f"🛡️ Order will be protected from cleanup"
    )
    
    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{PRIMARY_ENTRY}")],
        [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
    ])
    
    await edit_last_message(context, chat_id, tp_msg, cancel_keyboard)
    return TAKE_PROFITS

async def ask_for_conservative_take_profits(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Ask for 4 take profit prices in conservative approach"""
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    side = context.chat_data.get(SIDE, "Buy")
    trade_group_id = context.chat_data.get(CONSERVATIVE_TRADE_GROUP_ID, "Unknown")
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    
    limit1_price = context.chat_data.get(LIMIT_ENTRY_1_PRICE)
    limit2_price = context.chat_data.get(LIMIT_ENTRY_2_PRICE)
    limit3_price = context.chat_data.get(LIMIT_ENTRY_3_PRICE)
    
    tp_msg = (
        f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
        f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
        f"✅ <b>Approach:</b> 🛡️ Conservative Limits\n"
        f"✅ <b>Trade Group:</b> {trade_group_id} 🛡️\n"
        f"✅ <b>Limits:</b> {format_decimal_or_na(limit1_price)}, {format_decimal_or_na(limit2_price)}, {format_decimal_or_na(limit3_price)}\n\n"
        f"🎯 <b>Step 5 of 7: Take Profit Prices</b>\n\n"
        f"Enter 4 take profit prices (one per message):\n"
        f"💡 TP1: 70% | TP2: 10% | TP3: 10% | TP4: 10%\n"
        f"🛡️ All orders will be protected from cleanup\n\n"
        f"Enter <b>Take Profit #1</b> price (70% close):"
    )
    
    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
    ])
    
    # Initialize TP tracking
    context.chat_data["take_profits_entered"] = 0
    
    await edit_last_message(context, chat_id, tp_msg, cancel_keyboard)
    return TAKE_PROFITS

async def take_profits_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle take profit input for both approaches"""
    if not update.message or not update.message.text:
        return TAKE_PROFITS
    
    chat_id = update.effective_chat.id
    
    # Delete user's message
    try:
        await update.message.delete()
    except:
        pass
    
    try:
        price = Decimal(update.message.text.strip())
        if price <= 0:
            await send_error_and_retry(
                context, chat_id,
                "Take profit price must be greater than 0. Please enter a valid price:",
                TAKE_PROFITS
            )
            return TAKE_PROFITS
        
        approach = context.chat_data.get(TRADING_APPROACH, "fast")
        
        if approach == "fast":
            # Fast approach - single TP
            context.chat_data["tp1_price"] = price
            context.chat_data[TP1_PRICE] = price
            context.chat_data["TP1_PRICE"] = price  # Backup
            
            # Go directly to stop loss
            return await ask_for_stop_loss(context, chat_id)
            
        else:  # conservative approach
            # Conservative approach - 4 TPs
            tps_entered = context.chat_data.get("take_profits_entered", 0)
            
            if tps_entered == 0:
                context.chat_data[TP1_PRICE] = price
                context.chat_data["take_profits_entered"] = 1
                
                # Ask for TP2
                tp2_msg = (
                    f"✅ <b>TP1 (70%):</b> <code>{format_decimal_or_na(price)}</code> 🛡️\n\n"
                    f"🎯 <b>Step 5 of 7: Take Profit Prices</b>\n\n"
                    f"Enter <b>Take Profit #2</b> price (10% close):"
                )
                
                cancel_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
                ])
                
                await edit_last_message(context, chat_id, tp2_msg, cancel_keyboard)
                return TAKE_PROFITS
                
            elif tps_entered == 1:
                context.chat_data[TP2_PRICE] = price
                context.chat_data["take_profits_entered"] = 2
                
                # Ask for TP3
                tp1_price = context.chat_data.get(TP1_PRICE)
                tp3_msg = (
                    f"✅ <b>TP1 (70%):</b> <code>{format_decimal_or_na(tp1_price)}</code> 🛡️\n"
                    f"✅ <b>TP2 (10%):</b> <code>{format_decimal_or_na(price)}</code> 🛡️\n\n"
                    f"🎯 <b>Step 5 of 7: Take Profit Prices</b>\n\n"
                    f"Enter <b>Take Profit #3</b> price (10% close):"
                )
                
                cancel_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
                ])
                
                await edit_last_message(context, chat_id, tp3_msg, cancel_keyboard)
                return TAKE_PROFITS
                
            elif tps_entered == 2:
                context.chat_data[TP3_PRICE] = price
                context.chat_data["take_profits_entered"] = 3
                
                # Ask for TP4
                tp1_price = context.chat_data.get(TP1_PRICE)
                tp2_price = context.chat_data.get(TP2_PRICE)
                tp4_msg = (
                    f"✅ <b>TP1 (70%):</b> <code>{format_decimal_or_na(tp1_price)}</code> 🛡️\n"
                    f"✅ <b>TP2 (10%):</b> <code>{format_decimal_or_na(tp2_price)}</code> 🛡️\n"
                    f"✅ <b>TP3 (10%):</b> <code>{format_decimal_or_na(price)}</code> 🛡️\n\n"
                    f"🎯 <b>Step 5 of 7: Take Profit Prices</b>\n\n"
                    f"Enter <b>Take Profit #4</b> price (10% close):"
                )
                
                cancel_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
                ])
                
                await edit_last_message(context, chat_id, tp4_msg, cancel_keyboard)
                return TAKE_PROFITS
                
            elif tps_entered == 3:
                context.chat_data[TP4_PRICE] = price
                context.chat_data["take_profits_entered"] = 4
                
                # All 4 TPs entered, move to stop loss
                return await ask_for_stop_loss(context, chat_id)
        
    except (ValueError, InvalidOperation):
        await send_error_and_retry(
            context, chat_id,
            "Please enter a valid number for the take profit price:",
            TAKE_PROFITS
        )
        return TAKE_PROFITS

# =============================================
# STOP LOSS HANDLER - ENHANCED
# =============================================

async def ask_for_stop_loss(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Ask for stop loss - enhanced for dual approaches"""
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    side = context.chat_data.get(SIDE, "Buy")
    approach = context.chat_data.get(TRADING_APPROACH, "fast")
    
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    approach_emoji = "⚡" if approach == "fast" else "🛡️"
    approach_text = "Fast Market" if approach == "fast" else "Conservative Limits"
    
    # Build summary based on approach
    if approach == "fast":
        entry_price = context.chat_data.get(PRIMARY_ENTRY_PRICE, Decimal("0"))
        tp_price = context.chat_data.get(TP1_PRICE, Decimal("0"))
        
        sl_msg = (
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Approach:</b> {approach_emoji} {approach_text}\n"
            f"✅ <b>Entry Price:</b> <code>{format_decimal_or_na(entry_price)}</code>\n"
            f"✅ <b>Take Profit:</b> <code>{format_decimal_or_na(tp_price)}</code> 🛡️\n\n"
            f"🛡️ <b>Step 6 of 7: Stop Loss</b>\n\n"
            f"Enter your stop loss price:\n"
            f"💡 This protects you from large losses\n"
            f"🛡️ Order will be protected from cleanup"
        )
    else:
        # Conservative approach summary
        trade_group_id = context.chat_data.get(CONSERVATIVE_TRADE_GROUP_ID, "Unknown")
        limit1_price = context.chat_data.get(LIMIT_ENTRY_1_PRICE)
        limit2_price = context.chat_data.get(LIMIT_ENTRY_2_PRICE)
        limit3_price = context.chat_data.get(LIMIT_ENTRY_3_PRICE)
        tp1_price = context.chat_data.get(TP1_PRICE)
        tp2_price = context.chat_data.get(TP2_PRICE)
        tp3_price = context.chat_data.get(TP3_PRICE)
        tp4_price = context.chat_data.get(TP4_PRICE)
        
        sl_msg = (
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"✅ <b>Approach:</b> {approach_emoji} {approach_text}\n"
            f"✅ <b>Trade Group:</b> {trade_group_id} 🛡️\n"
            f"✅ <b>Limits:</b> {format_decimal_or_na(limit1_price)}, {format_decimal_or_na(limit2_price)}, {format_decimal_or_na(limit3_price)}\n"
            f"✅ <b>TPs:</b> {format_decimal_or_na(tp1_price)}, {format_decimal_or_na(tp2_price)}, {format_decimal_or_na(tp3_price)}, {format_decimal_or_na(tp4_price)} 🛡️\n\n"
            f"🛡️ <b>Step 6 of 7: Stop Loss</b>\n\n"
            f"Enter your stop loss price:\n"
            f"💡 This will cancel all remaining orders if hit\n"
            f"🛡️ All orders protected from cleanup"
        )
    
    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
    ])
    
    await edit_last_message(context, chat_id, sl_msg, cancel_keyboard)
    return STOP_LOSS

async def stop_loss_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle stop loss price input"""
    if not update.message or not update.message.text:
        return STOP_LOSS
    
    chat_id = update.effective_chat.id
    
    # Delete user's message
    try:
        await update.message.delete()
    except:
        pass
    
    try:
        price = Decimal(update.message.text.strip())
        if price <= 0:
            await send_error_and_retry(
                context, chat_id,
                "Stop loss price must be greater than 0. Please enter a valid price:",
                STOP_LOSS
            )
            return STOP_LOSS
        
        # Store SL with multiple key formats
        context.chat_data["sl_price"] = price
        context.chat_data[SL_PRICE] = price
        context.chat_data["SL_PRICE"] = price  # Backup
        
        # Move to leverage selection
        return await ask_for_leverage_with_buttons(context, chat_id)
        
    except (ValueError, InvalidOperation):
        await send_error_and_retry(
            context, chat_id,
            "Please enter a valid number for the stop loss price:",
            STOP_LOSS
        )
        return STOP_LOSS

# =============================================
# LEVERAGE SELECTION - UNCHANGED
# =============================================

async def ask_for_leverage_with_buttons(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Ask for leverage with quick selection buttons"""
    max_lev = int(context.chat_data.get(MAX_LEVERAGE_FOR_SYMBOL, 100))
    
    leverage_msg = (
        f"🛡️ <b>Stop Loss Set!</b>\n\n"
        f"⚡ <b>Step 7a: Select Leverage</b>\n\n"
        f"Choose your leverage (max {max_lev}x):\n"
        f"💡 Select a quick option or choose Custom for your own value"
    )
    
    # Build leverage selection keyboard with common options
    common_leverages = [5, 10, 20, 50]
    keyboard = []
    
    # Add common leverage buttons (2 per row)
    for i in range(0, len(common_leverages), 2):
        row = []
        for j in range(2):
            if i + j < len(common_leverages):
                lev = common_leverages[i + j]
                if lev <= max_lev:
                    row.append(InlineKeyboardButton(f"{lev}x", callback_data=f"conv_leverage:{lev}"))
        if row:
            keyboard.append(row)
    
    # Add custom and cancel buttons
    keyboard.append([
        InlineKeyboardButton(f"✏️ Custom", callback_data="conv_leverage:custom"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")
    ])
    
    leverage_keyboard = InlineKeyboardMarkup(keyboard)
    
    await edit_last_message(context, chat_id, leverage_msg, leverage_keyboard)
    return LEVERAGE

async def handle_leverage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle leverage selection callback"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    if not query.data.startswith("conv_leverage:"):
        return LEVERAGE
    
    leverage_value = query.data.split(":")[1]
    
    if leverage_value == "custom":
        # Show custom leverage input
        max_lev = int(context.chat_data.get(MAX_LEVERAGE_FOR_SYMBOL, 100))
        
        custom_leverage_msg = (
            f"⚡ <b>Custom Leverage</b>\n\n"
            f"Enter your custom leverage (1-{max_lev}):\n"
            f"💡 Example: 15"
        )
        
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
        ])
        
        try:
            await query.edit_message_text(
                custom_leverage_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message for custom leverage: {e}")
        
        return LEVERAGE  # Stay in LEVERAGE state for text input
    else:
        # Handle quick selection
        try:
            leverage = int(leverage_value)
            max_lev = int(context.chat_data.get(MAX_LEVERAGE_FOR_SYMBOL, 100))
            
            if leverage < 1 or leverage > max_lev:
                await query.answer(f"❌ Invalid leverage. Must be 1-{max_lev}", show_alert=True)
                return LEVERAGE
            
            # Store leverage with multiple key formats
            context.chat_data["leverage"] = leverage
            context.chat_data[LEVERAGE] = leverage
            context.chat_data["LEVERAGE"] = leverage
            
            logger.info(f"Quick leverage selected: {leverage}")
            
            # Move to margin selection with buttons
            return await ask_for_margin_with_buttons(context, query.message.chat.id, query)
            
        except ValueError:
            await query.answer("❌ Invalid leverage value", show_alert=True)
            return LEVERAGE

async def leverage_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom leverage text input"""
    if not update.message or not update.message.text:
        return LEVERAGE
    
    chat_id = update.effective_chat.id
    
    # Delete user's message
    try:
        await update.message.delete()
    except:
        pass
    
    try:
        leverage = int(update.message.text.strip())
        max_lev = int(context.chat_data.get(MAX_LEVERAGE_FOR_SYMBOL, 100))
        
        if leverage < 1 or leverage > max_lev:
            await send_error_and_retry(
                context, chat_id,
                f"Leverage must be between 1 and {max_lev}. Please enter a valid leverage:",
                LEVERAGE
            )
            return LEVERAGE
        
        # Store leverage with multiple key formats
        context.chat_data["leverage"] = leverage
        context.chat_data[LEVERAGE] = leverage
        context.chat_data["LEVERAGE"] = leverage
        
        logger.info(f"Custom leverage entered: {leverage}")
        
        # Move to margin selection with buttons
        return await ask_for_margin_with_buttons(context, chat_id)
        
    except ValueError:
        await send_error_and_retry(
            context, chat_id,
            "Please enter a valid whole number for leverage:",
            LEVERAGE
        )
        return LEVERAGE

# =============================================
# MARGIN SELECTION - UNCHANGED
# =============================================

async def ask_for_margin_with_buttons(context: ContextTypes.DEFAULT_TYPE, chat_id: int, query: CallbackQuery = None) -> int:
    """Ask for margin with quick selection buttons"""
    leverage = context.chat_data.get(LEVERAGE, 10)
    
    margin_msg = (
        f"⚡ <b>Leverage Set: {leverage}x</b>\n\n"
        f"💰 <b>Step 7b: Select Margin Amount</b>\n\n"
        f"Choose your margin amount in USDT:\n"
        f"💡 Select a quick option or choose Custom for your own amount"
    )
    
    # Build margin selection keyboard with common options
    common_margins = [25, 50, 100, 200]
    keyboard = []
    
    # Add common margin buttons (2 per row)
    for i in range(0, len(common_margins), 2):
        row = []
        for j in range(2):
            if i + j < len(common_margins):
                margin = common_margins[i + j]
                row.append(InlineKeyboardButton(f"{margin} USDT", callback_data=f"conv_margin:{margin}"))
        if row:
            keyboard.append(row)
    
    # Add custom and cancel buttons
    keyboard.append([
        InlineKeyboardButton(f"✏️ Custom", callback_data="conv_margin:custom"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")
    ])
    
    margin_keyboard = InlineKeyboardMarkup(keyboard)
    
    if query:
        # Edit existing message if we have a query
        try:
            await query.edit_message_text(
                margin_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=margin_keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message for margin selection: {e}")
    else:
        # Send new message
        await edit_last_message(context, chat_id, margin_msg, margin_keyboard)
    
    return MARGIN

async def handle_margin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle margin selection callback"""
    query = update.callback_query
    try:
        await query.answer()
    except:
        pass
    
    if not query.data.startswith("conv_margin:"):
        return MARGIN
    
    margin_value = query.data.split(":")[1]
    
    if margin_value == "custom":
        # Show custom margin input
        custom_margin_msg = (
            f"💰 <b>Custom Margin Amount</b>\n\n"
            f"Enter your custom margin amount in USDT:\n"
            f"💡 Example: 75"
        )
        
        cancel_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
        ])
        
        try:
            await query.edit_message_text(
                custom_margin_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message for custom margin: {e}")
        
        return MARGIN  # Stay in MARGIN state for text input
    else:
        # Handle quick selection
        try:
            margin = Decimal(margin_value)
            
            if margin <= 0:
                await query.answer("❌ Margin must be greater than 0", show_alert=True)
                return MARGIN
            
            # Store margin with multiple key formats
            context.chat_data["margin_amount_usdt"] = margin
            context.chat_data["margin_amount"] = margin
            context.chat_data[MARGIN_AMOUNT] = margin
            context.chat_data["MARGIN_AMOUNT"] = margin
            
            logger.info(f"Quick margin selected: {margin}")
            
            # Show final confirmation
            return await show_final_confirmation(context, query.message.chat.id)
            
        except (ValueError, InvalidOperation):
            await query.answer("❌ Invalid margin value", show_alert=True)
            return MARGIN

async def margin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom margin amount text input"""
    if not update.message or not update.message.text:
        return MARGIN
    
    chat_id = update.effective_chat.id
    
    # Delete user's message
    try:
        await update.message.delete()
    except:
        pass
    
    try:
        margin_text = update.message.text.strip()
        margin = Decimal(margin_text)
        
        if margin <= 0:
            await send_error_and_retry(
                context, chat_id,
                "Margin amount must be greater than 0. Please enter a valid amount:",
                MARGIN
            )
            return MARGIN
        
        # Store margin with multiple key formats
        context.chat_data["margin_amount_usdt"] = margin
        context.chat_data["margin_amount"] = margin
        context.chat_data[MARGIN_AMOUNT] = margin
        context.chat_data["MARGIN_AMOUNT"] = margin
        
        logger.info(f"Custom margin entered: {margin}")
        
        # Show final confirmation
        return await show_final_confirmation(context, chat_id)
        
    except (ValueError, InvalidOperation):
        await send_error_and_retry(
            context, chat_id,
            "Please enter a valid number for the margin amount (e.g., 50):",
            MARGIN
        )
        return MARGIN

# =============================================
# FINAL CONFIRMATION - ENHANCED FOR DUAL APPROACHES WITH PROTECTION
# =============================================

async def show_final_confirmation(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> int:
    """Show final trade confirmation - enhanced for GGShot screenshot approach"""
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    side = context.chat_data.get(SIDE, "Buy")
    approach = context.chat_data.get(TRADING_APPROACH, "fast")
    leverage = context.chat_data.get(LEVERAGE, 10)
    margin = context.chat_data.get(MARGIN_AMOUNT, Decimal("0"))
    
    direction_emoji = "📈" if side == "Buy" else "📉"
    direction_text = "LONG" if side == "Buy" else "SHORT"
    
    if approach == "fast":
        approach_emoji = "⚡"
        approach_text = "Fast Market"
    elif approach == "conservative":
        approach_emoji = "🛡️"
        approach_text = "Conservative Limits"
    elif approach == "ggshot":
        approach_emoji = "📸"
        approach_text = "GGShot Screenshot"
    else:
        approach_emoji = "⚡"
        approach_text = "Fast Market"
    
    # Build confirmation based on actual strategy (for GGShot, check order strategy)
    order_strategy = context.chat_data.get(ORDER_STRATEGY)
    
    # Determine display strategy - for GGShot, use the detected strategy
    if approach == "ggshot":
        if order_strategy == STRATEGY_CONSERVATIVE_LIMITS:
            display_strategy = "conservative"
        else:
            display_strategy = "fast"
    else:
        display_strategy = approach
    
    if display_strategy == "fast" or order_strategy == STRATEGY_MARKET_ONLY:
        entry_price = context.chat_data.get(PRIMARY_ENTRY_PRICE, Decimal("0"))
        tp_price = context.chat_data.get(TP1_PRICE, Decimal("0"))
        sl_price = context.chat_data.get(SL_PRICE, Decimal("0"))
        
        # Calculate R:R ratio
        rr_info = ""
        try:
            if entry_price and tp_price and sl_price:
                rr_result = calculate_risk_reward_ratio(entry_price, tp_price, sl_price, side)
                if rr_result and 'ratio' in rr_result:
                    ratio_raw = rr_result.get('ratio', '1:0')
                    rating = rr_result.get('rating', '⚪ UNKNOWN')
                    rr_info = f"\n⚖️ <b>Risk:Reward:</b> {ratio_raw} ({rating})"
        except Exception as e:
            logger.error(f"Error calculating R:R ratio: {e}")
        
        # Calculate simple USDT P&L preview
        pnl_preview = ""
        if all([entry_price, tp_price, sl_price, margin, leverage]):
            pnl_preview = calculate_trade_pnl_preview(
                entry_price, tp_price, sl_price, margin, leverage, side
            )
        
        # Add GGShot indicator if applicable
        ggshot_info = ""
        if approach == "ggshot":
            ggshot_info = f"🤖 <b>AI Extracted:</b> Fast Market strategy detected\n"
        
        confirmation_msg = (
            f"🚀 <b>TRADE CONFIRMATION</b> 🚀\n"
            f"{'═' * 30}\n\n"
            f"📊 <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"📈 <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"⚡ <b>Approach:</b> {approach_emoji} {approach_text}\n"
            f"{ggshot_info}"
            f"💰 <b>Entry:</b> <code>{format_decimal_or_na(entry_price)}</code>\n"
            f"🎯 <b>Take Profit:</b> <code>{format_decimal_or_na(tp_price)}</code> (100%) 🛡️\n"
            f"🛡️ <b>Stop Loss:</b> <code>{format_decimal_or_na(sl_price)}</code> 🛡️\n"
            f"⚡ <b>Leverage:</b> {leverage}x\n"
            f"💰 <b>Margin:</b> {format_decimal_or_na(margin)} USDT{rr_info}\n"
            f"{pnl_preview}\n"
            f"🛡️ <b>Protection:</b> All orders will be protected from cleanup\n\n"
            f"⚠️ <b>Ready to execute this trade?</b>"
        )
    
    else:  # conservative approach
        trade_group_id = context.chat_data.get(CONSERVATIVE_TRADE_GROUP_ID, "Unknown")
        limit1_price = context.chat_data.get(LIMIT_ENTRY_1_PRICE, Decimal("0"))
        limit2_price = context.chat_data.get(LIMIT_ENTRY_2_PRICE, Decimal("0"))
        limit3_price = context.chat_data.get(LIMIT_ENTRY_3_PRICE, Decimal("0"))
        tp1_price = context.chat_data.get(TP1_PRICE, Decimal("0"))
        tp2_price = context.chat_data.get(TP2_PRICE, Decimal("0"))
        tp3_price = context.chat_data.get(TP3_PRICE, Decimal("0"))
        tp4_price = context.chat_data.get(TP4_PRICE, Decimal("0"))
        sl_price = context.chat_data.get(SL_PRICE, Decimal("0"))
        
        # Add GGShot indicator if applicable
        ggshot_info = ""
        if approach == "ggshot":
            ggshot_info = f"🤖 <b>AI Extracted:</b> Conservative Limits strategy detected\n"
        
        confirmation_msg = (
            f"🚀 <b>CONSERVATIVE TRADE CONFIRMATION</b> 🚀\n"
            f"{'═' * 35}\n\n"
            f"📊 <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"📈 <b>Direction:</b> {direction_emoji} {direction_text}\n"
            f"🛡️ <b>Approach:</b> {approach_emoji} {approach_text}\n"
            f"{ggshot_info}"
            f"🛡️ <b>Trade Group:</b> <code>{trade_group_id}</code> 🛡️\n\n"
            f"📊 <b>LIMIT ORDERS (33.33% each):</b>\n"
            f"• <b>Limit #1:</b> <code>{format_decimal_or_na(limit1_price)}</code> 🛡️\n"
            f"• <b>Limit #2:</b> <code>{format_decimal_or_na(limit2_price)}</code> 🛡️\n"
            f"• <b>Limit #3:</b> <code>{format_decimal_or_na(limit3_price)}</code> 🛡️\n\n"
            f"🎯 <b>TAKE PROFITS:</b>\n"
            f"• <b>TP1 (70%):</b> <code>{format_decimal_or_na(tp1_price)}</code> 🛡️\n"
            f"• <b>TP2 (10%):</b> <code>{format_decimal_or_na(tp2_price)}</code> 🛡️\n"
            f"• <b>TP3 (10%):</b> <code>{format_decimal_or_na(tp3_price)}</code> 🛡️\n"
            f"• <b>TP4 (10%):</b> <code>{format_decimal_or_na(tp4_price)}</code> 🛡️\n\n"
            f"🛡️ <b>Stop Loss:</b> <code>{format_decimal_or_na(sl_price)}</code> 🛡️\n"
            f"⚡ <b>Leverage:</b> {leverage}x\n"
            f"💰 <b>Total Margin:</b> {format_decimal_or_na(margin)} USDT\n\n"
            f"🛡️ <b>Protection:</b> Trade group and all orders protected from cleanup\n\n"
            f"⚠️ <b>Special Rule:</b> If TP1 hits before limits fill,\n"
            f"all remaining orders will be cancelled.\n\n"
            f"⚠️ <b>Ready to execute this conservative trade?</b>"
        )
    
    confirmation_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 EXECUTE TRADE", callback_data="confirm_execute_trade")],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation"),
            InlineKeyboardButton("🔧 Modify", callback_data="modify_trade")
        ]
    ])
    
    await edit_last_message(context, chat_id, confirmation_msg, confirmation_keyboard)
    return CONFIRMATION

async def confirmation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle final confirmation"""
    # This should be handled by callback queries
    if update.message:
        await update.message.delete()
    return CONFIRMATION

# =============================================
# EXECUTION HANDLER - ENHANCED FOR DUAL APPROACHES WITH PROTECTION
# =============================================

async def handle_execute_trade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle trade execution for both approaches with protection system - FIXED"""
    query = update.callback_query
    try:
        await query.answer("🚀 Executing trade with protection system...")
    except:
        pass
    
    chat_id = query.message.chat.id
    approach = context.chat_data.get(TRADING_APPROACH, "fast")
    symbol = context.chat_data.get(SYMBOL, "Unknown")
    
    # Show execution message
    if approach == "fast":
        execution_msg = (
            f"{get_emoji('lightning')} <b>EXECUTING FAST TRADE...</b>\n\n"
            f"{get_emoji('rocket')} Placing market order on Bybit\n"
            f"{get_emoji('loading')} Please wait...\n\n"
            f"📊 Single take profit (100% close)\n"
            f"📈 Performance tracking will be enabled\n"
            f"🛡️ Symbol {symbol} protected from cleanup\n"
            f"This may take a few seconds..."
        )
    else:
        trade_group_id = context.chat_data.get(CONSERVATIVE_TRADE_GROUP_ID, "Unknown")
        execution_msg = (
            f"{get_emoji('shield')} <b>EXECUTING CONSERVATIVE TRADE...</b>\n\n"
            f"{get_emoji('rocket')} Placing 3 limit orders + 4 TPs + 1 SL\n"
            f"{get_emoji('loading')} Please wait...\n\n"
            f"📊 Conservative approach with isolated orders\n"
            f"📈 Enhanced monitoring will be enabled\n"
            f"🛡️ Trade group {trade_group_id} protected from cleanup\n"
            f"🛡️ Symbol {symbol} protected from cleanup\n"
            f"This may take longer due to multiple orders..."
        )
    
    try:
        await query.edit_message_text(
            execution_msg,
            parse_mode=ParseMode.HTML
        )
    except:
        pass
    
    # Set order strategy based on approach
    if approach == "conservative":
        context.chat_data["order_strategy"] = STRATEGY_CONSERVATIVE_LIMITS
        if 'ORDER_STRATEGY' in globals():
            context.chat_data[ORDER_STRATEGY] = STRATEGY_CONSERVATIVE_LIMITS
    else:
        context.chat_data["order_strategy"] = STRATEGY_MARKET_ONLY
        if 'ORDER_STRATEGY' in globals():
            context.chat_data[ORDER_STRATEGY] = STRATEGY_MARKET_ONLY
    
    # CRITICAL: Store chat_id for monitoring
    context.chat_data["_temp_chat_id"] = chat_id
    context.chat_data["_execution_source"] = "enhanced_conversation_with_protection"
    
    # Execute the trade using the enhanced trader module with protection system
    try:
        from execution.trader import execute_trade_logic
        
        # Create a copy of chat_data with proper mappings
        cfg = context.chat_data.copy() if context.chat_data else {}
        cfg["_temp_chat_id"] = chat_id  # Ensure chat_id is passed
        
        # CRITICAL FIX: Ensure all required keys are properly mapped
        if not cfg.get('LEVERAGE') and cfg.get('leverage'):
            cfg['LEVERAGE'] = cfg.get('leverage')
        if not cfg.get('MARGIN_AMOUNT') and cfg.get('margin_amount_usdt'):
            cfg['MARGIN_AMOUNT'] = cfg.get('margin_amount_usdt')
        if not cfg.get('SYMBOL') and cfg.get('symbol'):
            cfg['SYMBOL'] = cfg.get('symbol')
        if not cfg.get('SIDE') and cfg.get('side'):
            cfg['SIDE'] = cfg.get('side')
        
        # Map entry prices based on approach
        if approach == "fast":
            if not cfg.get('PRIMARY_ENTRY_PRICE') and cfg.get('primary_entry_price'):
                cfg['PRIMARY_ENTRY_PRICE'] = cfg.get('primary_entry_price')
        
        # Map TP prices
        if not cfg.get('TP1_PRICE') and cfg.get('tp1_price'):
            cfg['TP1_PRICE'] = cfg.get('tp1_price')
        if not cfg.get('SL_PRICE') and cfg.get('sl_price'):
            cfg['SL_PRICE'] = cfg.get('sl_price')
        
        logger.info(f"ENHANCED EXECUTION CONFIG for {approach} approach with protection:")
        logger.info(f"  SYMBOL: {cfg.get('SYMBOL')}")
        logger.info(f"  SIDE: {cfg.get('SIDE')}")
        logger.info(f"  APPROACH: {approach}")
        logger.info(f"  LEVERAGE: {cfg.get('LEVERAGE')}")
        logger.info(f"  MARGIN_AMOUNT: {cfg.get('MARGIN_AMOUNT')}")
        logger.info(f"  PROTECTION: Enabled")
        
        # FIXED: Call async function properly without asyncio.to_thread
        result = await execute_trade_logic(context.application, chat_id, cfg)
        
        # UPDATED: Display the enhanced message from trader.py
        if isinstance(result, dict) and result.get("message"):
            # Use the rich formatted message from trader.py
            await context.bot.send_message(
                chat_id,
                result["message"],
                parse_mode=ParseMode.HTML
            )
        else:
            # Fallback to basic message if no enhanced message
            if isinstance(result, dict):
                if result.get("success"):
                    result_msg = (
                        f"✅ <b>Trade Executed Successfully!</b>\n\n"
                        f"📊 <b>Orders Placed:</b>\n"
                    )
                    for order in result.get("orders_placed", []):
                        result_msg += f"• {order}\n"
                    
                    if approach == "fast" and result.get("entry_price"):
                        result_msg += f"\n📈 <b>Entry Price:</b> {format_decimal_or_na(result.get('entry_price'))}"
                        result_msg += f"\n📊 <b>Position Size:</b> {format_decimal_or_na(result.get('position_size'))}"
                    
                    result_msg += f"\n\n🔄 Automatic monitoring has been started"
                    result_msg += f"\n🛡️ All orders are protected from cleanup"
                else:
                    result_msg = f"❌ <b>Trade Execution Failed</b>\n\n{escape(result.get('error', 'Unknown error'))}"
            else:
                # If result is a string, use it directly
                result_msg = str(result)
            
            # Send result
            await context.bot.send_message(
                chat_id,
                result_msg,
                parse_mode=ParseMode.HTML
            )
        
        logger.info(f"✅ {approach} trade execution completed with advanced protection system enabled")
        
    except Exception as e:
        logger.error(f"Execution error: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id,
            f"{get_emoji('error')} <b>Execution Failed</b>\n\n{escape(str(e))}\n\nPlease try again.",
            parse_mode=ParseMode.HTML
        )
    
    # Return to dashboard
    try:
        from handlers.commands import _send_or_edit_dashboard_message
        await _send_or_edit_dashboard_message(chat_id, context, new_msg=True)
    except:
        pass
    
    return ConversationHandler.END

# =============================================
# BACK HANDLER - NEW
# =============================================

async def handle_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle back button in conversation flow"""
    query = update.callback_query
    if not query or not query.data.startswith("conv_back:"):
        return
    
    try:
        await query.answer()
    except:
        pass
    
    # Get the target state
    target_state = int(query.data.split(":")[1])
    chat_id = query.message.chat.id
    
    # Determine what to do based on target state
    if target_state == SYMBOL:
        # Go back to symbol input
        symbol_msg = (
            f"{get_emoji('rocket')} <b>ENHANCED TRADE SETUP WITH GGSHOT</b>\n"
            f"{'═' * 50}\n\n"
            f"💱 <b>Step 1 of 8: Symbol Selection</b>\n\n"
            f"Enter the trading symbol (e.g., <code>BTCUSDT</code>):\n\n"
            f"💡 <b>Features:</b>\n"
            f"• Fast Market or Conservative Limits\n"
            f"• GGShot Screenshot AI Analysis\n"
            f"• Advanced protection system\n"
            f"• Mobile-optimized interface"
        )
        
        cancel_keyboard = build_conversation_keyboard(include_back=False, include_cancel=True)
        
        try:
            await query.edit_message_text(
                symbol_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_keyboard
            )
        except:
            await edit_last_message(context, chat_id, symbol_msg, cancel_keyboard)
        
        return SYMBOL
    
    elif target_state == SIDE:
        # Go back to side selection
        symbol = context.chat_data.get(SYMBOL, "Unknown")
        
        side_msg = (
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n\n"
            f"📈 <b>Step 2 of 8: Trade Direction</b>\n\n"
            f"Choose your trading direction:"
        )
        
        side_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📈 LONG (Buy)", callback_data="conv_side:Buy")],
            [InlineKeyboardButton(f"📉 SHORT (Sell)", callback_data="conv_side:Sell")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{SYMBOL}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")]
        ])
        
        try:
            await query.edit_message_text(
                side_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=side_keyboard
            )
        except:
            await edit_last_message(context, chat_id, side_msg, side_keyboard)
        
        return SIDE
    
    elif target_state == APPROACH_SELECTION:
        # Go back to approach selection
        symbol = context.chat_data.get(SYMBOL, "Unknown")
        side = context.chat_data.get(SIDE, "Buy")
        direction_emoji = "📈" if side == "Buy" else "📉"
        direction_text = "LONG" if side == "Buy" else "SHORT"
        
        approach_msg = (
            f"✅ <b>Symbol:</b> <code>{symbol}</code> 🛡️\n"
            f"✅ <b>Direction:</b> {direction_emoji} {direction_text}\n\n"
            f"🎯 <b>Step 3 of 8: Trading Approach</b>\n\n"
            f"Choose your trading strategy:\n\n"
            f"⚡ <b>Fast Market</b>\n"
            f"• Single entry at market price\n"
            f"• One take profit (100% close)\n"
            f"• Best for quick moves\n\n"
            f"🛡️ <b>Conservative Limits</b>\n"
            f"• 3 limit orders (equal allocation)\n"
            f"• 4 take profits (70%, 10%, 10%, 10%)\n"
            f"• Better risk management\n\n"
            f"📸 <b>GGShot Screenshot</b>\n"
            f"• Upload trading screenshot\n"
            f"• AI extracts trade parameters\n"
            f"• Auto-populate setup\n"
            f"• Smart strategy detection\n\n"
            f"Select your preferred approach:"
        )
        
        approach_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"⚡ Fast Market", callback_data="conv_approach:fast")],
            [InlineKeyboardButton(f"🛡️ Conservative Limits", callback_data="conv_approach:conservative")],
            [InlineKeyboardButton(f"📸 GGShot Screenshot", callback_data="conv_approach:ggshot")],
            [InlineKeyboardButton("⬅️ Back", callback_data=f"conv_back:{SIDE}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation")]
        ])
        
        try:
            await query.edit_message_text(
                approach_msg,
                parse_mode=ParseMode.HTML,
                reply_markup=approach_keyboard
            )
        except:
            await edit_last_message(context, chat_id, approach_msg, approach_keyboard)
        
        return APPROACH_SELECTION
    
    # Add more states as needed...
    
    return ConversationHandler.END

# =============================================
# CANCEL HANDLER - UNCHANGED
# =============================================

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle conversation cancellation"""
    if update.callback_query:
        query = update.callback_query
        try:
            await query.answer("❌ Trade setup cancelled")
        except:
            pass
        chat_id = query.message.chat.id
    else:
        chat_id = update.effective_chat.id
    
    logger.info(f"Conversation cancelled for chat {chat_id}")
    
    # Clear chat data
    if context.chat_data:
        # Keep monitor data but clear trade setup
        monitor_backup = context.chat_data.get(ACTIVE_MONITOR_TASK, {})
        context.chat_data.clear()
        initialize_chat_data(context.chat_data)
        context.chat_data[ACTIVE_MONITOR_TASK] = monitor_backup
    
    # Send cancellation message and return to dashboard
    try:
        await context.bot.send_message(
            chat_id,
            f"{get_emoji('cross_mark')} Trade setup cancelled.\n\nReturning to dashboard...",
            parse_mode=ParseMode.HTML
        )
        
        # Return to dashboard
        from handlers.commands import _send_or_edit_dashboard_message
        await _send_or_edit_dashboard_message(chat_id, context, new_msg=True)
        
    except Exception as e:
        logger.error(f"Error in cancel handler: {e}")
    
    return ConversationHandler.END

# =============================================
# UTILITY FUNCTIONS - UNCHANGED
# =============================================

async def edit_last_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, keyboard):
    """Edit the last UI message"""
    msg_id = context.chat_data.get(LAST_UI_MESSAGE_ID)
    if msg_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            return
        except Exception as e:
            logger.warning(f"Error editing message {msg_id}: {e}")
    
    # If edit fails or no message ID, send new message
    try:
        sent = await context.bot.send_message(
            chat_id, text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
        context.chat_data[LAST_UI_MESSAGE_ID] = sent.message_id
    except Exception as e:
        logger.error(f"Error sending new message: {e}")

async def send_error_and_retry(context: ContextTypes.DEFAULT_TYPE, chat_id: int, error_msg: str, return_state: int):
    """Send error message and allow retry"""
    error_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
    ])
    
    # Escape HTML special characters in error message
    safe_error_msg = escape(error_msg) if error_msg else "Unknown error"
    await edit_last_message(context, chat_id, f"❌ {safe_error_msg}", error_keyboard)