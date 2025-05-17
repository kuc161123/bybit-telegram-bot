#!/usr/bin/env python3
# Required packages:
# pip install python-telegram-bot[persistence,job-queue]==21.0.1 pybit==5.5.0 python-dotenv httpx==0.25.2

import os
import logging
import asyncio
import time
import math
import uuid # Added for unique trade IDs
from decimal import Decimal, ROUND_DOWN, InvalidOperation, DivisionByZero
from typing import Union, List, Dict, Optional, Any
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
    PicklePersistence,
    ConversationHandler,
    TypeHandler,
)
from telegram.error import BadRequest, Forbidden, TimedOut as TelegramTimedOut

from pybit.unified_trading import HTTP
from pybit.exceptions import InvalidRequestError, FailedRequestError

import httpx
import requests

# --- Optional: Load .env file ---
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Loaded environment variables from .env file")
except ImportError:
    print("python-dotenv not installed, skipping .env file loading")

# --- Logging & Config ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3").setLevel(logging.WARNING)
logging.getLogger("telegram.ext.Application").setLevel(logging.INFO)
logging.getLogger("telegram.ext.ExtBot").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# --- Bot & Trade Configuration ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"
PERSISTENCE_FILE = os.getenv("PERSISTENCE_FILE", "bybit_bot_dashboard_v3.16.pkl") # Version bump for structure change
BYBIT_TIMEOUT_SECONDS = 20

ENTRY_PORTION_ALLOCATION = [Decimal("0.34"), Decimal("0.33"), Decimal("0.33")] # For Market + 2 Limits strategy
TP_PERCENTAGES = [Decimal("0.73"), Decimal("0.01"), Decimal("0.01"), Decimal("0.23")]
MONITOR_TP1_INTERVAL_SECONDS = 60
AUTO_MOVE_SL_TO_BE_AFTER_TP1 = True

if sum(ENTRY_PORTION_ALLOCATION) != Decimal("1.0"): logger.warning(f"ENTRY_PORTION_ALLOCATION sum != 1.0")
if sum(TP_PERCENTAGES) > Decimal("1.0"): logger.warning(f"TP_PERCENTAGES sum > 1.0")

if not all([TELEGRAM_TOKEN, BYBIT_API_KEY, BYBIT_API_SECRET]):
    logger.error("Missing critical environment variables."); exit(1)
try:
    bybit_client = HTTP(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        testnet=USE_TESTNET,
        timeout=BYBIT_TIMEOUT_SECONDS
    )
    logger.info(f"Bybit client initialized. Testnet: {USE_TESTNET}, Timeout: {BYBIT_TIMEOUT_SECONDS}s")
except Exception as e: logger.error(f"Failed Bybit client init: {e}", exc_info=True); exit(1)

# --- chat_data keys ---
SYMBOL = "symbol"; SIDE = "side"; MARGIN_AMOUNT = "margin_amount_usdt"
LEVERAGE = "leverage"
ORDER_STRATEGY = "order_strategy" # New key
LIMIT_ENTRY_1_PRICE = "limit_entry_1_price"
LIMIT_ENTRY_2_PRICE = "limit_entry_2_price"; TP1_PRICE = "tp1_price"
TP2_PRICE = "tp2_price"; TP3_PRICE = "tp3_price"; TP4_PRICE = "tp4_price"
SL_PRICE = "sl_price"; AWAITING_INPUT_FOR = "awaiting_input_for"
LAST_UI_MESSAGE_ID = "last_ui_message_id"; POSITION_IDX = "positionIdx"
PLACED_LIMIT_ENTRY_IDS = "placed_limit_entry_ids"; INITIAL_MARKET_FILL_QTY = "initial_market_fill_qty"
INITIAL_AVG_ENTRY_PRICE = "initial_avg_entry_price"
# ACTIVE_MONITOR_TASK will now store a dictionary: {unique_trade_id: monitor_data_dict}
ACTIVE_MONITOR_TASK = "active_monitor_task_data_v2" # Renamed to signify structural change & avoid pkl load issues
INSTRUMENT_TICK_SIZE = "instrument_tick_size"
INSTRUMENT_QTY_STEP = "instrument_qty_step"

# Order Strategy Values
STRATEGY_MARKET_ONLY = "strategy_market_only"
STRATEGY_MARKET_AND_LIMITS = "strategy_market_and_limits"


# --- Conversation Handler States ---
(ASK_SYMBOL, PROCESS_SYMBOL, ASK_SIDE, PROCESS_SIDE, ASK_MARGIN, PROCESS_MARGIN,
 ASK_LEVERAGE, PROCESS_LEVERAGE,
 ASK_ORDER_STRATEGY, PROCESS_ORDER_STRATEGY, # New states
 ASK_L1_PRICE, PROCESS_L1_PRICE,
 ASK_L2_PRICE, PROCESS_L2_PRICE, ASK_TP1_PRICE, PROCESS_TP1_PRICE,
 ASK_TP2_PRICE, PROCESS_TP2_PRICE, ASK_TP3_PRICE, PROCESS_TP3_PRICE,
 ASK_TP4_PRICE, PROCESS_TP4_PRICE, ASK_SL_PRICE, PROCESS_SL_PRICE,
 REVIEW_TRADE, PROCESS_FINAL_CONFIRMATION) = range(26) # Range updated

CONVERSATION_TIMEOUT_SECONDS = 300

# --- Helper Functions ---
def get_field_emoji_and_name(field_key: str) -> str:
    mapping = {
        SYMBOL: "🪙 Symbol", SIDE: "↕️ Side", MARGIN_AMOUNT: "💵 Margin (USDT)",
        LEVERAGE: "🚀 Leverage", ORDER_STRATEGY: "📋 Order Strategy",
        LIMIT_ENTRY_1_PRICE: " L1 Entry Price",
        LIMIT_ENTRY_2_PRICE: " L2 Entry Price", TP1_PRICE: "🎯 TP1 Price (73%)",
        TP2_PRICE: "🎯 TP2 Price (1%)", TP3_PRICE: "🎯 TP3 Price (1%)",
        TP4_PRICE: "🎯 TP4 Price (23%)", SL_PRICE: "🛡️ Stop Loss",
    }
    if field_key == LIMIT_ENTRY_1_PRICE: return "📥 L1 Entry Price"
    if field_key == LIMIT_ENTRY_2_PRICE: return "📥 L2 Entry Price"
    return mapping.get(field_key, field_key.replace("_", " ").capitalize())

def format_decimal_or_na(value: Optional[Union[Decimal, float, str]], precision: int = 8) -> str:
    if value is None or value == '': return "N/A"
    try:
        val_str = str(value) if isinstance(value, float) else value
        return str(Decimal(str(val_str)).quantize(Decimal('1e-' + str(precision))).normalize())
    except InvalidOperation: return "Invalid"

async def safe_edit_message(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: Optional[int], text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    if not message_id: logger.warning(f"No message ID to edit for chat {chat_id}. Text: {text[:50]}"); return
    try:
        await ctx.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "Message is not modified" not in str(e) and "message to edit not found" not in str(e) and "unsupported start tag" not in str(e) :
            logger.debug(f"SafeEdit BadRequest (likely ignorable): {e}")
        elif "message to edit not found" in str(e) and ctx.chat_data and ctx.chat_data.get(LAST_UI_MESSAGE_ID) == message_id:
            if ctx.chat_data: ctx.chat_data[LAST_UI_MESSAGE_ID] = None
        elif "unsupported start tag" in str(e):
            logger.error(f"SafeEdit HTML PARSE ERROR: {e}. Text was: {text[:200]}...")
            try: await ctx.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="Error displaying content (HTML parse issue).", reply_markup=reply_markup)
            except: pass
    except Forbidden: logger.error(f"SafeEdit Forbidden for msg {message_id} in chat {chat_id}")
    except TelegramTimedOut: logger.warning(f"SafeEdit TimedOut for msg {message_id} in chat {chat_id}")
    except Exception as e: logger.error(f"SafeEdit Exception: {e}", exc_info=True)

async def delete_message_if_exists(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: Optional[int]):
    if message_id:
        try: await ctx.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except Exception: pass

def get_instrument_info(symbol: str) -> Optional[dict]:
    try:
        resp = bybit_client.get_instruments_info(category="linear", symbol=symbol)
        if resp and resp.get("retCode") == 0 and resp.get("result", {}).get("list"):
            logger.info(f"Fetched instrument info for {symbol}"); return resp["result"]["list"][0]
        logger.error(f"Failed instrument info {symbol}: {resp.get('retMsg') if resp else 'No resp'} (ErrCode: {resp.get('retCode')}) (ErrTime: {time.strftime('%H:%M:%S', time.gmtime(int(resp.get('time', 0))/1000)) if resp and resp.get('time') else 'N/A'}).\nRequest → GET https://api.bybit.com/v5/market/instruments-info: category=linear&symbol={symbol}.")
    except (requests.exceptions.ReadTimeout, httpx.ReadTimeout) as e_timeout:
        logger.error(f"Timeout get_instrument_info {symbol}: {e_timeout}")
    except (InvalidRequestError, FailedRequestError) as e: logger.error(f"API Error get_instrument_info {symbol}: {e}", exc_info=False)
    except Exception as e: logger.error(f"Exc get_instrument_info {symbol}: {e}", exc_info=True)
    return None

def _adjust_value(value: Decimal, step: Decimal, round_mode=ROUND_DOWN) -> str:
    if step <= Decimal("0"): return str(value.quantize(Decimal('1e-8'), rounding=round_mode))
    adjusted_value = (value // step) * step
    if round_mode == "ROUND_UP":
        adjusted_value = Decimal(math.ceil(value / step)) * step
    elif round_mode == "ROUND_NEAREST":
        adjusted_value = Decimal(round(value / step)) * step
    step_str = str(step.normalize())
    if '.' in step_str: dec_places = len(step_str.split('.')[-1])
    else: dec_places = 0
    return str(adjusted_value.quantize(Decimal('1e-' + str(dec_places))))

def adjust_price(price: Decimal, tick_size: Decimal) -> str: return _adjust_value(price, tick_size)
def adjust_qty(qty: Decimal, qty_step: Decimal) -> str: return _adjust_value(qty, qty_step)

def fetch_all_trades_status_sync() -> str:
    status_messages = ["<b>📊 All Active Trades Status</b>"]
    any_active_position = False
    errors_occurred = False
    try:
        positions_response = bybit_client.get_positions(category="linear", limit=50)
        if positions_response.get("retCode") == 0:
            all_positions_data = positions_response.get("result", {}).get("list", [])
            active_positions = [p for p in all_positions_data if p.get("size") and Decimal(p.get("size", "0")) > 0]
            if not active_positions:
                status_messages.append("\nℹ️ No active positions found across all symbols.")
                return "\n".join(status_messages)
            any_active_position = True
            overall_open_orders_found = False
            for pos_data in active_positions:
                symbol = pos_data.get("symbol")
                pos_idx = int(pos_data.get("positionIdx", 0))
                pos_size_str = format_decimal_or_na(pos_data.get("size"))
                pos_side = pos_data.get("side")
                avg_price_str = format_decimal_or_na(pos_data.get("avgPrice"))
                mark_price_str = format_decimal_or_na(pos_data.get("markPrice"))
                unrealised_pnl_val_str = format_decimal_or_na(pos_data.get("unrealisedPnl"), 4)
                liq_price_str = format_decimal_or_na(pos_data.get("liqPrice"))
                leverage_str = pos_data.get("leverage", "N/A")
                created_time_display_str = "N/A"
                if pos_data.get("createdTime"):
                    try:
                        created_ts_ms = int(pos_data.get("createdTime"))
                        created_time_display_str = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(created_ts_ms / 1000))
                    except (ValueError, Exception) as e_time:
                        logger.warning(f"Could not parse/format createdTime: {pos_data.get('createdTime')} for {symbol}: {e_time}")
                pnl_percentage_str = ""
                try:
                    p_lev_decimal = Decimal(str(leverage_str))
                    avg_p_decimal = Decimal(str(pos_data.get("avgPrice","0")))
                    pos_size_decimal = Decimal(str(pos_data.get("size","0")))
                    unrealised_pnl_decimal = Decimal(str(pos_data.get("unrealisedPnl","0")))
                    if p_lev_decimal > 0 and avg_p_decimal > 0 and pos_size_decimal > 0:
                        initial_margin_usdt = (pos_size_decimal * avg_p_decimal) / p_lev_decimal
                        if initial_margin_usdt != 0:
                            pnl_calc_percentage = (unrealised_pnl_decimal / initial_margin_usdt) * 100
                            pnl_percentage_str = f" ({pnl_calc_percentage:+.2f}%)"
                except (TypeError, ValueError, InvalidOperation, DivisionByZero) as e_pnl_calc:
                    logger.debug(f"Could not calculate PNL percentage for {symbol}: {e_pnl_calc}")
                side_indicator_str = "📈 Long" if pos_side == "Buy" else "📉 Short"
                pnl_color_indicator = "🟢" if Decimal(pos_data.get("unrealisedPnl", "0")) >= 0 else "🔴"
                pos_info_lines = [
                    f"\n\n➖ <b>{escape(symbol)}</b> (Idx: <code>{pos_idx}</code>) ➖",
                    f"  Side: {escape(side_indicator_str)}", f"  Size: <code>{escape(pos_size_str)}</code>",
                    f"  Avg Entry: <code>{escape(avg_price_str)}</code>", f"  Mark Price: <code>{escape(mark_price_str)}</code>",
                    f"  Leverage: <code>{escape(str(leverage_str))}</code>×",
                    f"  uPnL: {pnl_color_indicator}<code>{escape(unrealised_pnl_val_str)}</code> USDT{escape(pnl_percentage_str)}",
                    f"  Liq. Price: <code>{escape(liq_price_str)}</code>", f"  Created: <code>{escape(created_time_display_str)}</code>",
                ]
                status_messages.extend(pos_info_lines)
                try:
                    orders_response = bybit_client.get_open_orders(category="linear", symbol=symbol, limit=50)
                    if orders_response.get("retCode") == 0:
                        open_orders_list = orders_response.get("result", {}).get("list", [])
                        if open_orders_list:
                            overall_open_orders_found = True
                            status_messages.append("    <b>Open Orders for Symbol:</b>")
                            for o in open_orders_list:
                                order_side_display = f"{'🟢' if o.get('side') == 'Buy' else '🔴'} {escape(o.get('side',''))}"
                                tp_sl_info = ""
                                if o.get("takeProfit"): tp_sl_info += f" TP:<code>{format_decimal_or_na(o.get('takeProfit'),8)}</code>"
                                if o.get("stopLoss"): tp_sl_info += f" SL:<code>{format_decimal_or_na(o.get('stopLoss'),8)}</code>"
                                reduce_only_info = " (Reduce)" if o.get('reduceOnly') else ""
                                status_messages.append(
                                    f"      {order_side_display} {escape(o.get('orderType',''))}: Qty<code>{escape(format_decimal_or_na(o.get('qty'),8))}</code>@<code>{escape(format_decimal_or_na(o.get('price'),8))}</code>{tp_sl_info}{reduce_only_info} (ID:...<code>{escape(o.get('orderId','')[-6:])}</code>)"
                                )
                    else:
                        status_messages.append(f"    ⚠️ Error orders ({escape(symbol)}): {escape(orders_response.get('retMsg', 'N/A'))}")
                        errors_occurred = True
                except (requests.exceptions.ReadTimeout, httpx.ReadTimeout) as e_timeout_ord:
                     logger.error(f"Timeout getting orders for {symbol}: {e_timeout_ord}")
                     status_messages.append(f"    🕒 Timeout getting orders for {escape(symbol)}.")
                     errors_occurred = True
                except Exception as e_ord:
                    logger.error(f"Exc. orders for {symbol}: {e_ord}", exc_info=True)
                    status_messages.append(f"    ❌ Exc. orders ({escape(symbol)}): {escape(str(e_ord))}")
                    errors_occurred = True
            if any_active_position and not overall_open_orders_found:
                 status_messages.append("\n\nℹ️ No open orders found for any active position symbols.")
        else:
            status_messages.append(f"\n⚠️ Error fetching positions: {escape(positions_response.get('retMsg', 'N/A'))} (Code: {positions_response.get('retCode')})")
            errors_occurred = True
    except (requests.exceptions.ReadTimeout, httpx.ReadTimeout) as e_timeout:
        logger.error(f"Timeout in fetch_all_trades_status_sync: {e_timeout}")
        status_messages.append(f"\n🕒 Network timeout fetching data from Bybit.")
        errors_occurred = True
    except (InvalidRequestError, FailedRequestError) as e_bybit:
        logger.error(f"Bybit API Error in fetch_all_trades_status_sync: {e_bybit}", exc_info=False)
        status_messages.append(f"\n❌ Bybit API Error: {escape(str(e_bybit))}")
        errors_occurred = True
    except Exception as e_pos:
        logger.error(f"General Exception in fetch_all_trades_status_sync: {e_pos}", exc_info=True)
        status_messages.append(f"\n❌ General Exception fetching positions: {escape(str(e_pos))}")
        errors_occurred = True
    if errors_occurred and not any_active_position :
         status_messages.append("\n<i>Note: Could not retrieve position data due to errors.</i>")
    elif errors_occurred:
        status_messages.append("\n<i>Note: Some information might be missing or incomplete due to errors.</i>")
    return "\n".join(status_messages)

# --- UI Building Functions ---
def build_dashboard_text(chat_data: Dict[str, Any]) -> str:
    display_side = "N/A"; effective_pos_usdt_str = "N/A (Set Margin & Lev)"
    if chat_data.get(SIDE) == "Buy": display_side = "📈 Long"
    elif chat_data.get(SIDE) == "Sell": display_side = "📉 Short"

    order_strategy_val = chat_data.get(ORDER_STRATEGY)
    display_order_strategy = "N/A"
    entry_info_text = ""
    if order_strategy_val == STRATEGY_MARKET_ONLY:
        display_order_strategy = "Market Order Only"
        entry_info_text = f" Mkt Entry (at exec price, ~100% allocation)\n"
    elif order_strategy_val == STRATEGY_MARKET_AND_LIMITS:
        display_order_strategy = "Market + 2 Limit Entries"
        entry_info_text = (
            f"<i>(Mkt: ~{ENTRY_PORTION_ALLOCATION[0]*100:.0f}%, L1: ~{ENTRY_PORTION_ALLOCATION[1]*100:.0f}%, L2: ~{ENTRY_PORTION_ALLOCATION[2]*100:.0f}%)</i>\n\n"
            f"<b>Entries:</b>\n Mkt Entry (at exec price)\n"
            f"📥 L1 Price: <code>{escape(format_decimal_or_na(chat_data.get(LIMIT_ENTRY_1_PRICE)))}</code>\n"
            f"📥 L2 Price: <code>{escape(format_decimal_or_na(chat_data.get(LIMIT_ENTRY_2_PRICE)))}</code>\n"
        )
    else: # Default or unknown
        display_order_strategy = "Market + 2 Limit Entries (Default)" # Or handle as error
        entry_info_text = ( # Fallback to default display if strategy is not set or unknown
            f"<i>(Mkt: ~{ENTRY_PORTION_ALLOCATION[0]*100:.0f}%, L1: ~{ENTRY_PORTION_ALLOCATION[1]*100:.0f}%, L2: ~{ENTRY_PORTION_ALLOCATION[2]*100:.0f}%)</i>\n\n"
            f"<b>Entries:</b>\n Mkt Entry (at exec price)\n"
            f"📥 L1 Price: <code>{escape(format_decimal_or_na(chat_data.get(LIMIT_ENTRY_1_PRICE)))}</code>\n"
            f"📥 L2 Price: <code>{escape(format_decimal_or_na(chat_data.get(LIMIT_ENTRY_2_PRICE)))}</code>\n"
        )


    margin_val = chat_data.get(MARGIN_AMOUNT); leverage_val = chat_data.get(LEVERAGE)
    if margin_val and leverage_val and isinstance(leverage_val, int) and leverage_val > 0:
        try:
            effective_pos_usdt = Decimal(str(margin_val)) * Decimal(str(leverage_val))
            effective_pos_usdt_str = format_decimal_or_na(effective_pos_usdt, precision=2)
        except: effective_pos_usdt_str = "CalcErr"

    monitor_status_msg = ""
    active_monitors_dict = chat_data.get(ACTIVE_MONITOR_TASK, {})
    if isinstance(active_monitors_dict, dict) and active_monitors_dict:
        # Displaying symbols from monitored tasks
        monitored_symbols_list = []
        for monitor_id, monitor_details in active_monitors_dict.items():
            if isinstance(monitor_details, dict) and 'symbol' in monitor_details:
                monitored_symbols_list.append(f"<code>{escape(monitor_details['symbol'])}</code> (ID: ...{escape(str(monitor_id)[-4:])})")
            else: # Fallback if structure is unexpected for some reason
                monitored_symbols_list.append(f"Monitor ID: ...{escape(str(monitor_id)[-4:])}")

        if monitored_symbols_list:
             monitor_status_msg = f"\n\n⏱️ Active Monitor(s) for: {', '.join(list(set(monitored_symbols_list)))}." # Use set to avoid duplicate symbol displays if any
        else:
             monitor_status_msg = "\n\n⏱️ No active monitors with valid symbols."

    return (
        f"<b>🤖 Bybit Trade Dashboard</b>\n\n"
        f"🪙 Symbol: <code>{escape(str(chat_data.get(SYMBOL,'N/A')))}</code>\n"
        f"↕️ Side: <b>{display_side}</b> ({escape(str(chat_data.get(SIDE,'N/A')))})\n"
        f"🚀 Leverage: <code>{escape(str(chat_data.get(LEVERAGE,'N/A')))}</code>×\n"
        f"💵 Margin: <code>{escape(format_decimal_or_na(margin_val,2))}</code> USDT\n"
        f"  ▻ Eff.Position: ~<code>{escape(effective_pos_usdt_str)}</code> USDT\n"
        f"{get_field_emoji_and_name(ORDER_STRATEGY)}: <b>{escape(display_order_strategy)}</b>\n"
        f"{entry_info_text}\n" # This now dynamically includes L1/L2 or not
        f"<b>Take Profits (on initial mkt fill):</b>\n"
        f"🎯 TP1 ({TP_PERCENTAGES[0]*100:.0f}%): <code>{escape(format_decimal_or_na(chat_data.get(TP1_PRICE)))}</code>\n"
        f"🎯 TP2 ({TP_PERCENTAGES[1]*100:.0f}%): <code>{escape(format_decimal_or_na(chat_data.get(TP2_PRICE)))}</code>\n"
        f"🎯 TP3 ({TP_PERCENTAGES[2]*100:.0f}%): <code>{escape(format_decimal_or_na(chat_data.get(TP3_PRICE)))}</code>\n"
        f"🎯 TP4 ({TP_PERCENTAGES[3]*100:.0f}%): <code>{escape(format_decimal_or_na(chat_data.get(TP4_PRICE)))}</code>\n\n"
        f"🛡️ SL Price: <code>{escape(format_decimal_or_na(chat_data.get(SL_PRICE)))}</code>"
        f"{monitor_status_msg}\n\n"
        f"Use /start to begin a new trade setup, or use buttons below." )

def build_dashboard_keyboard() -> InlineKeyboardMarkup:
    # Dynamically show L1/L2 buttons based on order strategy IF strategy is set and is Market+Limits
    # For simplicity in dashboard, always show them, but their edit might be contextual.
    # The dashboard text will reflect if they are used.
    buttons = [
        [InlineKeyboardButton("✍️ New Trade Setup (/start)", callback_data="action:start_conversation")],
        [InlineKeyboardButton(get_field_emoji_and_name(SYMBOL), callback_data=f"edit:{SYMBOL}"),
         InlineKeyboardButton(get_field_emoji_and_name(SIDE), callback_data=f"edit:{SIDE}")],
        [InlineKeyboardButton(get_field_emoji_and_name(LEVERAGE), callback_data=f"edit:{LEVERAGE}"),
         InlineKeyboardButton(get_field_emoji_and_name(MARGIN_AMOUNT), callback_data=f"edit:{MARGIN_AMOUNT}")],
        [InlineKeyboardButton(get_field_emoji_and_name(ORDER_STRATEGY), callback_data=f"edit:{ORDER_STRATEGY}")], # New Button
    ]
    # Conditionally add L1/L2 buttons if current strategy needs them, or always show
    # For now, always showing to allow strategy switch then edit
    buttons.extend([
        [InlineKeyboardButton(get_field_emoji_and_name(LIMIT_ENTRY_1_PRICE), callback_data=f"edit:{LIMIT_ENTRY_1_PRICE}"),
         InlineKeyboardButton(get_field_emoji_and_name(LIMIT_ENTRY_2_PRICE), callback_data=f"edit:{LIMIT_ENTRY_2_PRICE}")],
    ])
    buttons.extend([
        [InlineKeyboardButton(get_field_emoji_and_name(TP1_PRICE), callback_data=f"edit:{TP1_PRICE}"),
         InlineKeyboardButton(get_field_emoji_and_name(TP2_PRICE), callback_data=f"edit:{TP2_PRICE}")],
        [InlineKeyboardButton(get_field_emoji_and_name(TP3_PRICE), callback_data=f"edit:{TP3_PRICE}"),
         InlineKeyboardButton(get_field_emoji_and_name(TP4_PRICE), callback_data=f"edit:{TP4_PRICE}")],
        [InlineKeyboardButton(get_field_emoji_and_name(SL_PRICE), callback_data=f"edit:{SL_PRICE}")],
        [InlineKeyboardButton("🔄 Reset Bot State", callback_data="reset_all"),
         InlineKeyboardButton("📊 View All Active Trades", callback_data="view_status")],
        [InlineKeyboardButton("✅ Review & Confirm Current Setup", callback_data="confirm_trade_prompt")]
    ])
    return InlineKeyboardMarkup(buttons)

def build_side_selection_keyboard(callback_prefix="set_conv"):
    return InlineKeyboardMarkup([ [InlineKeyboardButton("📈 Long(Buy)",callback_data=f"{callback_prefix}:{SIDE}:Buy"), InlineKeyboardButton("📉 Short(Sell)",callback_data=f"{callback_prefix}:{SIDE}:Sell")], [InlineKeyboardButton("❌ Cancel Setup",callback_data="cancel_conversation")] ])

def build_order_strategy_keyboard(callback_prefix="set_conv_os"): # New Keyboard
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Market Order Only", callback_data=f"{callback_prefix}:{ORDER_STRATEGY}:{STRATEGY_MARKET_ONLY}")],
        [InlineKeyboardButton("Market + 2 Limit Entries", callback_data=f"{callback_prefix}:{ORDER_STRATEGY}:{STRATEGY_MARKET_AND_LIMITS}")],
        [InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]
    ])

def build_cancel_edit_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Edit",callback_data="cancel_editing")]])

def build_quick_edit_options_keyboard(field_key: str, current_value_str: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([ [InlineKeyboardButton(f"✅ Keep Current: {current_value_str[:20]}", callback_data=f"quick_edit_keep:{field_key}")], [InlineKeyboardButton("✏️ Enter New Value", callback_data=f"quick_edit_new:{field_key}")], [InlineKeyboardButton("❌ Cancel Edit", callback_data="cancel_editing")] ])

def build_cancel_conv_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Setup", callback_data="cancel_conversation")]])

def build_final_confirmation_keyboard(callback_prefix="confirm_conv"):
    return InlineKeyboardMarkup([ [InlineKeyboardButton("🚀 YES, Execute This Trade",callback_data=f"{callback_prefix}:execute")], [InlineKeyboardButton("⏪ NO, Go Back & Edit (Not Implemented, use /start to re-enter)",callback_data="cancel_conversation")] ])

def initialize_chat_data(chat_data:Dict[str,Any]):
    defaults = {
        SYMBOL:"BTCUSDT", SIDE:"Buy", MARGIN_AMOUNT:Decimal("15.0"), LEVERAGE:10,
        ORDER_STRATEGY: STRATEGY_MARKET_AND_LIMITS, # Default strategy
        LIMIT_ENTRY_1_PRICE:None, LIMIT_ENTRY_2_PRICE:None,
        TP1_PRICE:None, TP2_PRICE:None, TP3_PRICE:None, TP4_PRICE:None, SL_PRICE:None,
        AWAITING_INPUT_FOR:None, LAST_UI_MESSAGE_ID:None, POSITION_IDX:0,
        PLACED_LIMIT_ENTRY_IDS:[], INITIAL_MARKET_FILL_QTY:Decimal("0"),
        INITIAL_AVG_ENTRY_PRICE:Decimal("0"),
        ACTIVE_MONITOR_TASK:{}, # Changed to new key and structure (dict of dicts)
        INSTRUMENT_TICK_SIZE: None, INSTRUMENT_QTY_STEP: None,
    }
    for k,v in defaults.items():
        if k not in chat_data or (chat_data.get(k) is None and v is not None):
            chat_data[k] = v
        elif k == MARGIN_AMOUNT and isinstance(chat_data.get(k), (int, float, str)):
            try: chat_data[k] = Decimal(str(chat_data[k]))
            except: chat_data[k] = v # Revert to default if conversion fails
        elif k == LEVERAGE and isinstance(chat_data.get(k), (str, float)):
            try: chat_data[k] = int(chat_data[k])
            except: chat_data[k] = v # Revert to default
        elif k == ACTIVE_MONITOR_TASK and not isinstance(chat_data.get(k), dict): # Ensure it's a dict
             chat_data[k] = {}
        elif k == ORDER_STRATEGY and chat_data.get(k) not in [STRATEGY_MARKET_ONLY, STRATEGY_MARKET_AND_LIMITS]:
            chat_data[k] = v # Revert to default if invalid


async def _send_or_edit_dashboard_message(update_or_chat_id:Union[Update,int],ctx:ContextTypes.DEFAULT_TYPE,new_message:bool=False):
    chat_id = update_or_chat_id if isinstance(update_or_chat_id,int) else update_or_chat_id.effective_chat.id
    if ctx.chat_data is None: ctx.chat_data = {}
    initialize_chat_data(ctx.chat_data)
    text=build_dashboard_text(ctx.chat_data)
    kb=build_dashboard_keyboard()
    last_ui_id = ctx.chat_data.get(LAST_UI_MESSAGE_ID)
    if new_message or not last_ui_id:
        if last_ui_id: await delete_message_if_exists(ctx,chat_id,last_ui_id)
        try:
            msg=await ctx.bot.send_message(chat_id,text,reply_markup=kb,parse_mode=ParseMode.HTML)
            if ctx.chat_data: ctx.chat_data[LAST_UI_MESSAGE_ID]=msg.message_id
        except Forbidden: logger.error(f"Failed to send new dashboard (Forbidden) for chat {chat_id}.")
        except Exception as e: logger.error(f"Failed send new dash:{e}",exc_info=True)
    else: await safe_edit_message(ctx,chat_id,last_ui_id,text,kb)
    if ctx.chat_data: ctx.chat_data[AWAITING_INPUT_FOR]=None

async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Dashboard command received for chat {update.effective_chat.id}")
    await _send_or_edit_dashboard_message(update, context, new_message=True)

async def start_trade_setup_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = -1; reply_target = None
    if isinstance(update, Update) and update.message: chat_id = update.effective_chat.id; reply_target = update.message
    elif isinstance(update, CallbackQuery):
        if update.message and update.message.chat: chat_id = update.message.chat.id
        reply_target = update.message
    else:
        logger.error(f"Unexpected update type in start_trade_setup_conversation: {type(update)}")
        if hasattr(context, '_chat_id') and context._chat_id: chat_id = context._chat_id
        if chat_id != -1 and chat_id is not None:
            try: await context.bot.send_message(chat_id, "Error starting setup. Please try /start again.")
            except Exception as e_send: logger.error(f"Failed to send error message in start_trade_setup_conversation: {e_send}")
        return ConversationHandler.END

    if chat_id == -1 or reply_target is None: logger.error(f"Could not determine chat_id or reply_target in start_trade_setup_conversation."); return ConversationHandler.END

    logger.info(f"Starting new trade setup conversation for chat {chat_id}")
    if context.chat_data is None: context.chat_data = {}
    initialize_chat_data(context.chat_data) # Resets to defaults for a new setup

    last_msg_id = context.chat_data.get(LAST_UI_MESSAGE_ID)
    if last_msg_id: await delete_message_if_exists(context, chat_id, last_msg_id); context.chat_data[LAST_UI_MESSAGE_ID] = None

    prompt_text = "Let's set up a new trade! 🚀\n\nFirst, what is the <b>trading symbol</b>? (e.g., BTCUSDT, ETHUSDT)"
    try:
        sent_message = await reply_target.reply_text(prompt_text, parse_mode=ParseMode.HTML, reply_markup=build_cancel_conv_keyboard())
        if context.chat_data: context.chat_data[LAST_UI_MESSAGE_ID] = sent_message.message_id
    except Exception as e: logger.error(f"Failed to send initial prompt in start_trade_setup_conversation for chat {chat_id}: {e}"); return ConversationHandler.END
    return ASK_SYMBOL

async def ask_next_field_in_conversation(update_or_query: Union[Update, CallbackQuery],context: ContextTypes.DEFAULT_TYPE,current_field_key: str,prompt_text: str,next_state: int,reply_markup: Optional[InlineKeyboardMarkup] = None) -> int:
    chat_id = -1
    if isinstance(update_or_query, Update):
        if update_or_query.effective_chat: chat_id = update_or_query.effective_chat.id
        if update_or_query.message and update_or_query.message.text:
            if chat_id != -1: await delete_message_if_exists(context, chat_id, update_or_query.message.message_id)
    elif isinstance(update_or_query, CallbackQuery):
        if update_or_query.message and update_or_query.message.chat: chat_id = update_or_query.message.chat.id
    else:
        logger.error(f"Could not determine chat_id from update_or_query type {type(update_or_query)} in ask_next_field.")
        if hasattr(context, '_chat_id') and context._chat_id: chat_id = context._chat_id
        if not chat_id or chat_id == -1: logger.critical("CRITICAL: Chat ID unknown in ask_next_field. Ending conversation abruptly."); return ConversationHandler.END

    if chat_id == -1: logger.critical("CRITICAL: Chat ID is -1 after checks in ask_next_field. Ending conversation."); return ConversationHandler.END

    last_msg_id = context.chat_data.get(LAST_UI_MESSAGE_ID)
    current_value_display = escape(str(context.chat_data.get(current_field_key, 'N/A')))

    if current_field_key == SIDE:
        side_val = context.chat_data.get(SIDE)
        if side_val == "Buy": current_value_display = "📈 Long (Buy)"
        elif side_val == "Sell": current_value_display = "📉 Short (Sell)"
    elif current_field_key == ORDER_STRATEGY:
        strategy_val = context.chat_data.get(ORDER_STRATEGY)
        if strategy_val == STRATEGY_MARKET_ONLY: current_value_display = "Market Order Only"
        elif strategy_val == STRATEGY_MARKET_AND_LIMITS: current_value_display = "Market + 2 Limit Entries"


    final_prompt = f"✅ {get_field_emoji_and_name(current_field_key)} set to: <b>{current_value_display}</b>\n\n{prompt_text}"
    if not reply_markup: reply_markup = build_cancel_conv_keyboard()

    if last_msg_id: await safe_edit_message(context, chat_id, last_msg_id, final_prompt, reply_markup)
    else:
        logger.warning(f"No LAST_UI_MESSAGE_ID in ask_next_field for chat {chat_id}, sending new message.")
        try:
            sent_msg = await context.bot.send_message(chat_id, final_prompt, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            if context.chat_data: context.chat_data[LAST_UI_MESSAGE_ID] = sent_msg.message_id
        except Exception as e: logger.error(f"Failed to send message in ask_next_field for chat {chat_id}: {e}"); return ConversationHandler.END
    return next_state

async def process_symbol_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip().upper(); chat_id = update.effective_chat.id; last_msg_id = context.chat_data.get(LAST_UI_MESSAGE_ID)
    if not user_input:
        prompt_text = "⚠️ Symbol was empty. What is the <b>trading symbol</b>? (e.g., BTCUSDT, ETHUSDT)"
        await safe_edit_message(context, chat_id, last_msg_id, prompt_text, build_cancel_conv_keyboard()); await delete_message_if_exists(context, chat_id, update.message.message_id); return ASK_SYMBOL

    inst_info = get_instrument_info(user_input)
    if not inst_info:
        error_msg = f"⚠️ Invalid or unsupported symbol: <code>{escape(user_input)}</code>.\n\nPlease enter a valid LINEAR contract symbol (e.g., BTCUSDT) or /cancel."
        await safe_edit_message(context, chat_id, last_msg_id, error_msg, build_cancel_conv_keyboard()); await delete_message_if_exists(context, chat_id, update.message.message_id); return ASK_SYMBOL

    context.chat_data[SYMBOL] = user_input; context.chat_data[INSTRUMENT_TICK_SIZE] = Decimal(inst_info["priceFilter"]["tickSize"]); context.chat_data[INSTRUMENT_QTY_STEP] = Decimal(inst_info["lotSizeFilter"]["qtyStep"])
    next_prompt = "Next, what is the <b>trade side</b>?"
    return await ask_next_field_in_conversation(update, context, SYMBOL, next_prompt, ASK_SIDE, build_side_selection_keyboard("conv_set_side"))

async def process_side_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    try: await query.answer()
    except TelegramTimedOut: logger.warning(f"Timed out answering side_callback query: {query.id}. Proceeding.")
    except BadRequest as e_ans: logger.warning(f"Failed to answer side_callback query (likely too old): {query.id} - {e_ans}")

    _, field, value = query.data.split(":", 2)
    if field == SIDE:
        context.chat_data[SIDE] = value;
        next_prompt = f"What is your <b>margin amount</b> in USDT? (e.g., 10.5 for 10.50 USDT)"
        return await ask_next_field_in_conversation(query, context, SIDE, next_prompt, ASK_MARGIN)
    logger.warning(f"Unexpected callback in process_side_callback: {query.data}"); return ConversationHandler.END

async def _handle_numerical_input_error(update: Update, context: ContextTypes.DEFAULT_TYPE,field_key_for_reprompt: str, error_message: str, current_ask_state: int) -> int:
    chat_id = update.effective_chat.id; last_msg_id = context.chat_data.get(LAST_UI_MESSAGE_ID); current_field_display_name = get_field_emoji_and_name(field_key_for_reprompt)
    prompt_text = f"⚠️ {escape(error_message)}\n\nPlease re-enter the value for <b>{current_field_display_name}</b> or /cancel."
    await safe_edit_message(context, chat_id, last_msg_id, prompt_text, build_cancel_conv_keyboard()); await delete_message_if_exists(context, chat_id, update.message.message_id); return current_ask_state

async def process_margin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    try:
        val = Decimal(user_input);
        if val <= Decimal("0"): return await _handle_numerical_input_error(update, context, MARGIN_AMOUNT, "Margin must be positive.", ASK_MARGIN)
        context.chat_data[MARGIN_AMOUNT] = val;
        next_prompt = "Next, your <b>leverage</b> (e.g., 10 for 10x)."
        return await ask_next_field_in_conversation(update, context, MARGIN_AMOUNT, next_prompt, ASK_LEVERAGE)
    except InvalidOperation: return await _handle_numerical_input_error(update, context, MARGIN_AMOUNT, "Invalid number format.", ASK_MARGIN)

async def process_leverage_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    try:
        val = int(user_input)
        if val <= 0: return await _handle_numerical_input_error(update, context, LEVERAGE, "Leverage must be a positive whole number.", ASK_LEVERAGE)
        context.chat_data[LEVERAGE] = val;
        next_prompt = "Please choose your <b>Order Strategy</b>:"
        return await ask_next_field_in_conversation(update, context, LEVERAGE, next_prompt, ASK_ORDER_STRATEGY, build_order_strategy_keyboard("conv_set_os"))
    except ValueError: return await _handle_numerical_input_error(update, context, LEVERAGE, "Invalid whole number format.", ASK_LEVERAGE)

async def process_order_strategy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: # New Handler
    query = update.callback_query
    try: await query.answer()
    except TelegramTimedOut: logger.warning(f"Timed out answering order_strategy_callback: {query.id}")
    except BadRequest as e_ans: logger.warning(f"Failed to answer order_strategy_callback: {query.id} - {e_ans}")

    _, field, value = query.data.split(":", 2) # e.g., "conv_set_os:order_strategy:strategy_market_only"

    if field == ORDER_STRATEGY:
        context.chat_data[ORDER_STRATEGY] = value
        if value == STRATEGY_MARKET_ONLY:
            context.chat_data[LIMIT_ENTRY_1_PRICE] = None # Explicitly nullify
            context.chat_data[LIMIT_ENTRY_2_PRICE] = None
            next_prompt = f"Market Only selected. Limit Entries skipped.\n\nWhat is your <b>Take Profit 1 Price ({TP_PERCENTAGES[0]*100:.0f}%)</b>?"
            return await ask_next_field_in_conversation(query, context, ORDER_STRATEGY, next_prompt, ASK_TP1_PRICE)
        elif value == STRATEGY_MARKET_AND_LIMITS:
            next_prompt = "Market + 2 Limit Entries selected.\n\nWhat is your <b>Limit Entry 1 Price</b>?"
            return await ask_next_field_in_conversation(query, context, ORDER_STRATEGY, next_prompt, ASK_L1_PRICE)
    logger.warning(f"Unexpected callback in process_order_strategy_callback: {query.data}"); return ConversationHandler.END


async def process_l1_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    # This should only be reached if STRATEGY_MARKET_AND_LIMITS was chosen
    if context.chat_data.get(ORDER_STRATEGY) != STRATEGY_MARKET_AND_LIMITS:
        logger.warning(f"process_l1_price_input reached unexpectedly with strategy: {context.chat_data.get(ORDER_STRATEGY)}")
        # Potentially redirect or end, for now assume it's logically correct path
        # Or just proceed, as validation is next
    try:
        val = Decimal(user_input)
        if val <= Decimal("0"): return await _handle_numerical_input_error(update, context, LIMIT_ENTRY_1_PRICE, "L1 Price must be positive.", ASK_L1_PRICE)
        context.chat_data[LIMIT_ENTRY_1_PRICE] = val;
        return await ask_next_field_in_conversation(update, context, LIMIT_ENTRY_1_PRICE, "<b>Limit Entry 2 Price</b>?", ASK_L2_PRICE)
    except InvalidOperation: return await _handle_numerical_input_error(update, context, LIMIT_ENTRY_1_PRICE, "Invalid number format.", ASK_L1_PRICE)

async def process_l2_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    if context.chat_data.get(ORDER_STRATEGY) != STRATEGY_MARKET_AND_LIMITS: # Defensive
        logger.warning(f"process_l2_price_input reached unexpectedly with strategy: {context.chat_data.get(ORDER_STRATEGY)}")

    try:
        val = Decimal(user_input)
        if val <= Decimal("0"): return await _handle_numerical_input_error(update, context, LIMIT_ENTRY_2_PRICE, "L2 Price must be positive.", ASK_L2_PRICE)
        context.chat_data[LIMIT_ENTRY_2_PRICE] = val;
        next_prompt = f"What is your <b>Take Profit 1 Price ({TP_PERCENTAGES[0]*100:.0f}%)</b>?"
        return await ask_next_field_in_conversation(update, context, LIMIT_ENTRY_2_PRICE, next_prompt, ASK_TP1_PRICE)
    except InvalidOperation: return await _handle_numerical_input_error(update, context, LIMIT_ENTRY_2_PRICE, "Invalid number format.", ASK_L2_PRICE)

async def process_tp1_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    try:
        val = Decimal(user_input)
        if val <= Decimal("0"): return await _handle_numerical_input_error(update, context, TP1_PRICE, "TP1 Price must be positive.", ASK_TP1_PRICE)
        context.chat_data[TP1_PRICE] = val;
        return await ask_next_field_in_conversation(update, context, TP1_PRICE, f"<b>Take Profit 2 Price ({TP_PERCENTAGES[1]*100:.0f}%)</b>?", ASK_TP2_PRICE)
    except InvalidOperation: return await _handle_numerical_input_error(update, context, TP1_PRICE, "Invalid number format.", ASK_TP1_PRICE)

async def process_tp2_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    try:
        val = Decimal(user_input)
        if val <= Decimal("0"): return await _handle_numerical_input_error(update, context, TP2_PRICE, "TP2 Price must be positive.", ASK_TP2_PRICE)
        context.chat_data[TP2_PRICE] = val;
        return await ask_next_field_in_conversation(update, context, TP2_PRICE, f"<b>Take Profit 3 Price ({TP_PERCENTAGES[2]*100:.0f}%)</b>?", ASK_TP3_PRICE)
    except InvalidOperation: return await _handle_numerical_input_error(update, context, TP2_PRICE, "Invalid number format.", ASK_TP2_PRICE)

async def process_tp3_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    try:
        val = Decimal(user_input)
        if val <= Decimal("0"): return await _handle_numerical_input_error(update, context, TP3_PRICE, "TP3 Price must be positive.", ASK_TP3_PRICE)
        context.chat_data[TP3_PRICE] = val;
        return await ask_next_field_in_conversation(update, context, TP3_PRICE, f"<b>Take Profit 4 Price ({TP_PERCENTAGES[3]*100:.0f}%)</b>?", ASK_TP4_PRICE)
    except InvalidOperation: return await _handle_numerical_input_error(update, context, TP3_PRICE, "Invalid number format.", ASK_TP3_PRICE)

async def process_tp4_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    try:
        val = Decimal(user_input)
        if val <= Decimal("0"): return await _handle_numerical_input_error(update, context, TP4_PRICE, "TP4 Price must be positive.", ASK_TP4_PRICE)
        context.chat_data[TP4_PRICE] = val;
        return await ask_next_field_in_conversation(update, context, TP4_PRICE, "Finally, your <b>Stop Loss Price</b>?", ASK_SL_PRICE)
    except InvalidOperation: return await _handle_numerical_input_error(update, context, TP4_PRICE, "Invalid number format.", ASK_TP4_PRICE)

async def process_sl_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip(); chat_id = update.effective_chat.id
    try:
        val = Decimal(user_input)
        if val <= Decimal("0"): return await _handle_numerical_input_error(update, context, SL_PRICE, "SL Price must be positive.", ASK_SL_PRICE)
        context.chat_data[SL_PRICE] = val;
        await delete_message_if_exists(context, chat_id, update.message.message_id) # Delete user's price input

        dashboard_summary_text = build_dashboard_text(context.chat_data) # Full dashboard
        # Extract relevant part for review message, avoid redundant buttons/instructions
        relevant_summary_part = "\n\n".join(dashboard_summary_text.split("\n\n")[1:-2]) # Exclude title and last instruction line
        if "Active Monitor(s) for:" in relevant_summary_part: # Remove monitor line from this specific summary
             relevant_summary_part = relevant_summary_part.split("⏱️ Active Monitor(s) for:")[0].strip()


        last_field_confirmation = f"✅ {get_field_emoji_and_name(SL_PRICE)} set to: <b>{escape(str(context.chat_data.get(SL_PRICE)))}</b>\n\n"
        review_text = (
            f"{last_field_confirmation}Alright, all inputs received! Here's your trade setup:\n\n"
            f"{relevant_summary_part}\n\n" # Use the extracted part
            f"Please review carefully. Do you want to execute this trade?"
        )
        await safe_edit_message(context, chat_id, context.chat_data.get(LAST_UI_MESSAGE_ID), review_text, build_final_confirmation_keyboard("conv_confirm"));
        return REVIEW_TRADE
    except InvalidOperation: return await _handle_numerical_input_error(update, context, SL_PRICE, "Invalid number format.", ASK_SL_PRICE)


async def process_final_confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    try: await query.answer()
    except TelegramTimedOut: logger.warning(f"Timed out answering final_confirm_callback query: {query.id}. Proceeding.")
    except BadRequest as e_ans: logger.warning(f"Failed to answer final_confirm_callback query: {query.id} - {e_ans}")

    action = query.data.split(":")[1]; chat_id = -1
    if query.message and query.message.chat: chat_id = query.message.chat.id
    else:
        logger.error("Could not determine chat_id from callback query in process_final_confirmation_callback.")
        if query.message:
            try: await query.message.reply_text("An error occurred processing your request. Please try again.")
            except Exception as e_reply_err: logger.error(f"Failed to send error reply in process_final_confirmation_callback: {e_reply_err}")
        return ConversationHandler.END

    message_to_edit_id = context.chat_data.get(LAST_UI_MESSAGE_ID, query.message.message_id if query.message else None)

    if action == "execute":
        if message_to_edit_id: await safe_edit_message(context, chat_id, message_to_edit_id, "⏳ Processing trade execution... Please wait.", reply_markup=None)
        else:
            logger.warning("No message ID to edit for 'Processing execution...' in final confirm. Sending new.")
            try:
                processing_msg = await context.bot.send_message(chat_id, "⏳ Processing trade execution... Please wait.")
                if context.chat_data: context.chat_data[LAST_UI_MESSAGE_ID] = processing_msg.message_id
            except Exception as e_send_proc: logger.error(f"Failed to send 'Processing...' message to chat {chat_id}: {e_send_proc}")

        if context.chat_data: context.chat_data["_temp_chat_id"] = chat_id # Pass chat_id to thread
        current_loop = asyncio.get_running_loop()

        async def run_execution_task():
            trade_setup_config = context.chat_data.copy(); execution_summary = "❌ Execution error: Unknown issue."
            try: execution_summary = await asyncio.to_thread(execute_trade_logic, trade_setup_config, context.application, current_loop); logger.info(f"Trade execution task completed for chat {chat_id}.")
            except Exception as e: logger.error(f"Exception in trade execution thread for chat {chat_id}: {e}", exc_info=True); execution_summary = f"❌ Critical error during trade execution: {escape(str(e))}"
            finally:
                try:
                    logger.info(f"Execution summary for chat {chat_id} PRE-SEND (ConvHandler):\n{execution_summary}")
                    # Instead of deleting LAST_UI_MESSAGE_ID here, let the final message become the new context, or let dashboard handle it.
                    # For conversation, this usually means the interaction sequence is over.
                    # A new message is sent below.
                    final_msg = await context.bot.send_message(chat_id, execution_summary, parse_mode=ParseMode.HTML)
                    # After execution, the setup is complete. Resetting relevant parts or let /dashboard handle next UI
                    if context.chat_data:
                         context.chat_data[LAST_UI_MESSAGE_ID] = final_msg.message_id # Update with the summary message
                         # Consider if some specific keys should be cleared or if initialize_chat_data handles new setup start well
                except Exception as e_final:
                    logger.error(f"Error sending final summary/cleaning up for chat {chat_id} (ConvHandler): {e_final}", exc_info=True)
                    try: await context.bot.send_message(chat_id, f"Error displaying trade summary. Details logged. Raw summary: {escape(execution_summary[:1000])}")
                    except Exception as e_fallback: logger.error(f"Failed to send fallback error message for chat {chat_id} (ConvHandler): {e_fallback}")

                if context.chat_data: context.chat_data.pop("_temp_chat_id", None) # Clean up temp chat_id

        asyncio.create_task(run_execution_task()); return ConversationHandler.END
    else: # "cancel" or "go_back" (currently leads to cancel)
        if message_to_edit_id: await safe_edit_message(context, chat_id, message_to_edit_id, "Trade setup cancelled. Use /start to begin a new one or /dashboard.", None)
        else:
            logger.warning("No message ID to edit for cancellation in final confirm. Sending new.")
            try: await context.bot.send_message(chat_id, "Trade setup cancelled. Use /start or /dashboard.")
            except Exception as e_send_cancel: logger.error(f"Failed send cancel from final confirm for chat {chat_id}: {e_send_cancel}")
        return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = -1; user_message_to_delete = None
    if isinstance(update, Update) and update.message: chat_id = update.effective_chat.id; user_message_to_delete = update.message.message_id
    elif isinstance(update, CallbackQuery):
        if update.message and update.message.chat: chat_id = update.message.chat.id
        try: await update.answer()
        except (TelegramTimedOut, BadRequest): pass
    else:
        logger.info(f"cancel_conversation potentially called by TypeHandler with update type: {type(update)}")
        if hasattr(context, '_chat_id') and context._chat_id: chat_id = context._chat_id
        elif update.effective_chat : chat_id = update.effective_chat.id
        if not chat_id or chat_id == -1: logger.error("Cancel called, but no chat_id from context or update."); return ConversationHandler.END

    if chat_id == -1 : logger.error("Failed to determine chat_id in cancel_conversation."); return ConversationHandler.END

    logger.info(f"User in chat {chat_id} cancelled or ended the conversation.")
    if user_message_to_delete: await delete_message_if_exists(context, chat_id, user_message_to_delete)

    last_bot_msg_id = context.chat_data.get(LAST_UI_MESSAGE_ID) if context.chat_data else None
    cancel_text = "Trade setup process ended. Use /start to begin a new setup or /dashboard to view current settings."

    if last_bot_msg_id: await safe_edit_message(context, chat_id, last_bot_msg_id, cancel_text, None)
    else:
        try: await context.bot.send_message(chat_id, cancel_text)
        except Exception as e: logger.error(f"Failed to send cancel message to chat {chat_id}: {e}")

    if context.chat_data: context.chat_data[AWAITING_INPUT_FOR] = None
    # Do not clear all chat_data here, let /start or /dashboard refresh the view based on existing data
    # initialize_chat_data is called at the beginning of /start if a full reset is needed
    return ConversationHandler.END


async def conversation_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = None
    if hasattr(update, 'effective_chat') and update.effective_chat: chat_id = update.effective_chat.id
    elif hasattr(context, '_chat_id') and context._chat_id: chat_id = context._chat_id
    elif update and hasattr(update, 'callback_query') and update.callback_query and update.callback_query.message: chat_id = update.callback_query.message.chat.id

    if not chat_id: logger.error("Conversation timed out, but could not determine chat_id."); return ConversationHandler.END

    logger.info(f"Conversation timed out for chat {chat_id}")
    last_msg_id = context.chat_data.get(LAST_UI_MESSAGE_ID) if context.chat_data else None
    timeout_text = "Trade setup timed out. Use /start to begin again or /dashboard."

    if last_msg_id: await safe_edit_message(context, chat_id, last_msg_id, timeout_text, None)
    else:
        try: await context.bot.send_message(chat_id, timeout_text)
        except Exception as e: logger.error(f"Failed to send timeout message to chat {chat_id}: {e}")
    # AWAITING_INPUT_FOR should be cleared, dashboard state is fine
    if context.chat_data: context.chat_data[AWAITING_INPUT_FOR] = None
    return ConversationHandler.END

async def button_callback_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    if not q: return
    try: await q.answer()
    except TelegramTimedOut: logger.warning(f"Timed out answering button_callback_handler query: {q.id}. Proceeding.")
    except BadRequest as e_ans: logger.warning(f"Failed to answer button_callback_handler query: {q.id} - {e_ans}")

    c_id = q.message.chat.id if q.message and q.message.chat else None; m_id = q.message.message_id if q.message else None; act = q.data
    if not c_id : logger.error("Button callback: Could not determine chat_id."); return

    if ctx.chat_data is None: ctx.chat_data = {}
    if m_id : ctx.chat_data[LAST_UI_MESSAGE_ID] = m_id # Ensure LAST_UI_MESSAGE_ID is up-to-date
    logger.debug(f"Button callback: '{act}' from chat {c_id}, message {m_id if m_id else 'N/A'}")
    initialize_chat_data(ctx.chat_data) # Ensure defaults are present

    if act == "action:start_conversation":
        if q.message : await q.message.delete() # Delete the dashboard message
        if ctx.chat_data : ctx.chat_data[LAST_UI_MESSAGE_ID] = None # Clear last UI ID
        await start_trade_setup_conversation(q, ctx); return # This will handle re-initializing for new setup

    elif act.startswith("edit:"):
        field_to_edit = act.split(":")[1]; current_val = ctx.chat_data.get(field_to_edit)
        precision_map = {MARGIN_AMOUNT: 2, SYMBOL: 8, LEVERAGE: 0} # Default precisions

        if isinstance(current_val, Decimal):
            precision = precision_map.get(field_to_edit, 8); current_val_str = format_decimal_or_na(current_val, precision)
        elif field_to_edit == LEVERAGE and isinstance(current_val, int): current_val_str = str(current_val)
        elif field_to_edit == SIDE:
            current_val_str = "📈 Long" if current_val == "Buy" else "📉 Short" if current_val == "Sell" else "N/A"
        elif field_to_edit == ORDER_STRATEGY:
            if current_val == STRATEGY_MARKET_ONLY: current_val_str = "Market Only"
            elif current_val == STRATEGY_MARKET_AND_LIMITS: current_val_str = "Market + 2 Limits"
            else: current_val_str = "N/A"
        else: current_val_str = escape(str(current_val)) if current_val is not None else "N/A"

        prompt_text_edit = f"Editing <b>{get_field_emoji_and_name(field_to_edit)}</b>.\nCurrent value: <code>{current_val_str}</code>"

        if field_to_edit == SIDE:
            side_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📈 Long(Buy)",callback_data=f"set_dash:{SIDE}:Buy"), InlineKeyboardButton("📉 Short(Sell)",callback_data=f"set_dash:{SIDE}:Sell")],
                [InlineKeyboardButton("❌ Cancel Edit",callback_data="cancel_editing")]
            ])
            await safe_edit_message(ctx,c_id,m_id, f"Select new <b>{get_field_emoji_and_name(SIDE)}</b>:", side_kb)
            ctx.chat_data[AWAITING_INPUT_FOR]=None
        elif field_to_edit == ORDER_STRATEGY: # New edit case
            os_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("Market Order Only",callback_data=f"set_dash:{ORDER_STRATEGY}:{STRATEGY_MARKET_ONLY}")],
                [InlineKeyboardButton("Market + 2 Limit Entries",callback_data=f"set_dash:{ORDER_STRATEGY}:{STRATEGY_MARKET_AND_LIMITS}")],
                [InlineKeyboardButton("❌ Cancel Edit",callback_data="cancel_editing")]
            ])
            await safe_edit_message(ctx,c_id,m_id, f"Select new <b>{get_field_emoji_and_name(ORDER_STRATEGY)}</b>:", os_kb)
            ctx.chat_data[AWAITING_INPUT_FOR]=None
        else: # For text input fields
            quick_edit_kb = build_quick_edit_options_keyboard(field_to_edit, current_val_str)
            await safe_edit_message(ctx,c_id,m_id, prompt_text_edit, quick_edit_kb)
        return

    elif act.startswith("quick_edit_new:"): # User wants to type a new value
        field_to_edit = act.split(":")[1]; ctx.chat_data[AWAITING_INPUT_FOR] = field_to_edit
        prompt_detail = ""; example_val_str = ""
        if field_to_edit == SYMBOL: prompt_detail = "(e.g., <code>BTCUSDT</code>)"
        elif field_to_edit == MARGIN_AMOUNT: prompt_detail = "(e.g., <code>10.5</code> for USDT 10.50)"
        elif field_to_edit == LEVERAGE: prompt_detail = "(e.g., <code>10</code> for 10x)"
        elif field_to_edit.startswith(("LIMIT_ENTRY","TP","SL_PRICE")):
             current_field_val = ctx.chat_data.get(field_to_edit)
             if isinstance(current_field_val, Decimal): example_val_str = format_decimal_or_na(current_field_val)
             elif current_field_val is not None: example_val_str = str(current_field_val)
             else: example_val_str = '25000.75' # Generic example
             prompt_detail = f"(e.g., <code>{escape(example_val_str)}</code>)"

        prm=f"✏️ Please send the new value for <b>{get_field_emoji_and_name(field_to_edit)}</b> {prompt_detail}:"
        await safe_edit_message(ctx,c_id,m_id,prm,build_cancel_edit_keyboard()); return

    elif act.startswith("quick_edit_keep:") or act == "cancel_editing": # User keeps current or cancels edit mode
        ctx.chat_data[AWAITING_INPUT_FOR]=None; await _send_or_edit_dashboard_message(c_id,ctx); return

    elif act.startswith("set_dash:"): # Direct set from button (e.g., Side, Order Strategy)
        _,fld,val_str=act.split(":",2); ctx.chat_data[fld]=val_str;
        logger.info(f"Dashboard edit: Set '{fld}' to '{val_str}' for {c_id}")
        if fld == ORDER_STRATEGY and val_str == STRATEGY_MARKET_ONLY: # If strategy changed to market only, clear L1/L2
            ctx.chat_data[LIMIT_ENTRY_1_PRICE] = None
            ctx.chat_data[LIMIT_ENTRY_2_PRICE] = None
        ctx.chat_data[AWAITING_INPUT_FOR]=None;
        await _send_or_edit_dashboard_message(c_id,ctx)

    elif act=="reset_all":
        logger.info(f"Resetting bot state for {c_id}")
        active_monitors_dict = ctx.chat_data.get(ACTIVE_MONITOR_TASK) # New key
        if isinstance(active_monitors_dict, dict) and active_monitors_dict:
            logger.info(f"Chat {c_id} reset: Clearing all ({len(active_monitors_dict)}) monitor tasks by unique_trade_id: {list(active_monitors_dict.keys())}")
            # Monitors will stop on their next check because their data will be gone from chat_data[ACTIVE_MONITOR_TASK]
            ctx.chat_data[ACTIVE_MONITOR_TASK] = {} # Clear the dictionary
        elif active_monitors_dict is not None :
            logger.info(f"Chat {c_id} reset: Clearing legacy/unexpected monitor task data: {active_monitors_dict}")
            ctx.chat_data[ACTIVE_MONITOR_TASK] = {}

        old_m_id = ctx.chat_data.get(LAST_UI_MESSAGE_ID); ctx.chat_data.clear(); initialize_chat_data(ctx.chat_data)
        # Re-send dashboard after reset because the old one might have been tied to a deleted message or specific context.
        if old_m_id: await delete_message_if_exists(ctx, c_id, old_m_id);
        await _send_or_edit_dashboard_message(c_id, ctx, new_message=True) # Force new message

    elif act=="view_status":
        if m_id: await safe_edit_message(ctx, c_id, m_id, "⏳ Fetching status...", None)
        else: await ctx.bot.send_message(c_id, "⏳ Fetching status...")

        status_text = "Error fetching status."
        try: status_text = await asyncio.to_thread(fetch_all_trades_status_sync)
        except Exception as e: logger.error(f"Error in fetch_all_trades_status_sync thread for {c_id}: {e}", exc_info=True); status_text = f"❌ Critical error fetching status: {escape(str(e))}"
        # Send status as a new message, then refresh dashboard to avoid status message being overwritten
        try:
            status_msg = await ctx.bot.send_message(c_id, status_text, parse_mode=ParseMode.HTML)
            # If dashboard was displaying status, that dashboard will be replaced.
            # Let dashboard refresh itself without trying to edit over the status_msg.
        except Exception as e_send:
            logger.error(f"Failed send status msg for {c_id}: {e_send}")
            try: await ctx.bot.send_message(c_id, escape(status_text), parse_mode=None) # Fallback to no parse mode
            except Exception as e_send_no_reply: logger.error(f"Failed send status (no reply) {c_id}: {e_send_no_reply}")
        await _send_or_edit_dashboard_message(c_id,ctx) # Refresh original dashboard message

    elif act=="confirm_trade_prompt": # From Dashboard "Review & Confirm"
        # Validate all required fields for the current ORDER_STRATEGY
        required_fields=[SYMBOL,SIDE,MARGIN_AMOUNT,LEVERAGE,ORDER_STRATEGY,TP1_PRICE,TP2_PRICE,TP3_PRICE,TP4_PRICE,SL_PRICE]
        if ctx.chat_data.get(ORDER_STRATEGY) == STRATEGY_MARKET_AND_LIMITS:
            required_fields.extend([LIMIT_ENTRY_1_PRICE, LIMIT_ENTRY_2_PRICE])

        missing_fields = [f for f in required_fields if not ctx.chat_data.get(f) and ctx.chat_data.get(f) !=0 ] # 0 is valid for positionIdx

        margin_val = ctx.chat_data.get(MARGIN_AMOUNT); leverage_val = ctx.chat_data.get(LEVERAGE)
        if not isinstance(margin_val, Decimal) or margin_val <= Decimal("0"):
            if MARGIN_AMOUNT not in missing_fields: missing_fields.append(MARGIN_AMOUNT)
        if not isinstance(leverage_val, int) or leverage_val <= 0:
            if LEVERAGE not in missing_fields: missing_fields.append(LEVERAGE)

        if missing_fields:
            missing_display = ', '.join([get_field_emoji_and_name(f) for f in set(missing_fields)])
            msg_to_send = f"⚠️<b>Validation Error!</b>\nMissing or invalid values for:\n{missing_display}\n\nPlease edit these fields from the dashboard or use /start to re-enter setup."
            if q.message: await q.message.reply_text(msg_to_send, parse_mode=ParseMode.HTML) # Reply to dashboard for context
            else: await ctx.bot.send_message(c_id, msg_to_send, parse_mode=ParseMode.HTML)
            return

        dashboard_text_content = build_dashboard_text(ctx.chat_data)
        summary_part = "\n\n".join(dashboard_text_content.split("\n\n")[1:-2]) # Exclude title and last general instruction line
        if "Active Monitor(s) for:" in summary_part:
             summary_part = summary_part.split("⏱️ Active Monitor(s) for:")[0].strip()


        text=f"<b>⚠️ Final Confirmation (Dashboard) ⚠️</b>\n\n"+summary_part+"\n\nExecute this trade?"
        await safe_edit_message(ctx,c_id,m_id,text,build_final_confirmation_keyboard("dash_confirm_exec"))

    elif act.startswith("dash_confirm_exec:"): # Confirmation from dashboard
        action = act.split(":")[1]
        if action == "execute":
            current_msg_id_for_edit = ctx.chat_data.get(LAST_UI_MESSAGE_ID, m_id) # Use dashboard's message ID
            if current_msg_id_for_edit : await safe_edit_message(ctx, c_id, current_msg_id_for_edit, "⏳ Processing trade execution from dashboard... Please wait.", reply_markup=None)
            else: # Should not happen if "confirm_trade_prompt" set LAST_UI_MESSAGE_ID
                 processing_msg_dash = await ctx.bot.send_message(c_id, "⏳ Processing trade execution from dashboard... Please wait.")
                 if ctx.chat_data: ctx.chat_data[LAST_UI_MESSAGE_ID] = processing_msg_dash.message_id

            if ctx.chat_data: ctx.chat_data["_temp_chat_id"] = c_id # Pass chat_id to thread
            current_loop = asyncio.get_running_loop()

            async def run_execution_task():
                trade_setup_config = ctx.chat_data.copy(); execution_summary = "❌ Execution error."
                try: execution_summary = await asyncio.to_thread(execute_trade_logic, trade_setup_config, ctx.application, current_loop)
                except Exception as e: logger.error(f"Exc in dash trade exec thread for {c_id}: {e}", exc_info=True); execution_summary = f"❌ Critical error during trade execution: {escape(str(e))}"
                finally:
                    try:
                        logger.info(f"Execution summary for chat {c_id} PRE-SEND (Dashboard):\n{execution_summary}")
                        # Send summary as a new message.
                        exec_summary_msg = await ctx.bot.send_message(c_id, execution_summary, parse_mode=ParseMode.HTML)
                        # Then refresh the main dashboard. The dashboard should not be the summary message.
                        if ctx.chat_data: ctx.chat_data[LAST_UI_MESSAGE_ID] = None # Force dashboard refresh to a new message if old one was exec prompt
                        await _send_or_edit_dashboard_message(c_id, ctx, new_message=True) # Refresh dashboard
                    except Exception as e_final:
                        logger.error(f"Error in dash exec finally for {c_id}: {e_final}", exc_info=True)
                        try:
                            await ctx.bot.send_message(c_id, f"Error displaying trade summary. Details logged. Raw summary: {escape(execution_summary[:1000])}")
                            await _send_or_edit_dashboard_message(c_id, ctx, new_message=True) # Attempt to show dashboard
                        except Exception as e_fallback: logger.error(f"Failed send fallback/dash for chat {c_id} (Dashboard): {e_fallback}")

                    if ctx.chat_data: ctx.chat_data.pop("_temp_chat_id", None)

            asyncio.create_task(run_execution_task())
        else: # "cancel" from dash_confirm_exec
            await _send_or_edit_dashboard_message(c_id, ctx) # Just show the dashboard again

async def text_input_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE): # For quick edits from dashboard
    if not update.message or not update.message.text: return
    chat_id=update.effective_chat.id; user_message_id=update.message.message_id; user_input_text=update.message.text.strip()
    await delete_message_if_exists(ctx, chat_id, user_message_id) # Delete user's input message

    if not ctx.chat_data: initialize_chat_data(ctx.chat_data) # Should be initialized
    field_awaiting_input = ctx.chat_data.get(AWAITING_INPUT_FOR); dashboard_message_id = ctx.chat_data.get(LAST_UI_MESSAGE_ID)

    if not field_awaiting_input:
        logger.debug(f"Ignoring unsolicited text '{user_input_text}' from {chat_id} (not in edit mode for dashboard)."); return

    logger.info(f"Processing dashboard quick edit input '{user_input_text}' for field '{field_awaiting_input}' in chat {chat_id}")
    error_message = None; parsed_value: Any = None

    try:
        if not user_input_text: error_message = "Input cannot be empty."
        elif field_awaiting_input == SYMBOL:
            parsed_value = user_input_text.upper().replace(" ", "")
            if not parsed_value: error_message = "Symbol cannot be empty."
            else:
                inst_info = get_instrument_info(parsed_value)
                if not inst_info: error_message = f"Invalid or unsupported symbol: <code>{escape(parsed_value)}</code>"
                else: # Update instrument details
                    if ctx.chat_data:
                        ctx.chat_data[INSTRUMENT_TICK_SIZE] = Decimal(inst_info["priceFilter"]["tickSize"])
                        ctx.chat_data[INSTRUMENT_QTY_STEP] = Decimal(inst_info["lotSizeFilter"]["qtyStep"])
        elif field_awaiting_input == LEVERAGE:
            parsed_value = int(user_input_text)
            if parsed_value <= 0: error_message = "Leverage must be a positive whole number."
        elif field_awaiting_input in [MARGIN_AMOUNT, LIMIT_ENTRY_1_PRICE, LIMIT_ENTRY_2_PRICE, TP1_PRICE, TP2_PRICE, TP3_PRICE, TP4_PRICE, SL_PRICE]:
            parsed_value = Decimal(user_input_text)
            if parsed_value <= Decimal("0"): error_message = f"{get_field_emoji_and_name(field_awaiting_input)} must be positive."
        # ORDER_STRATEGY and SIDE are handled by buttons, not text input via this handler.
        else: error_message = "Unknown field for text input (dashboard edit)."
    except ValueError: error_message = f"Invalid format for {get_field_emoji_and_name(field_awaiting_input)}. Expected a whole number (integer)."
    except InvalidOperation: error_message = f"Invalid format for {get_field_emoji_and_name(field_awaiting_input)}. Expected a number (decimal)."
    except Exception as e: error_message = f"An unexpected error occurred: {escape(str(e))}"; logger.error(f"Error processing dashboard text input for {field_awaiting_input}: {e}", exc_info=True)

    if error_message:
        prompt_text = f"⚠️ {escape(error_message)}\n\nPlease re-enter the value for <b>{get_field_emoji_and_name(field_awaiting_input)}</b>, or cancel using the button:"
        # Re-display prompt on the dashboard message
        await safe_edit_message(ctx, chat_id, dashboard_message_id, prompt_text, build_cancel_edit_keyboard())
    else: # Success
        if ctx.chat_data:
            ctx.chat_data[field_awaiting_input] = parsed_value
            logger.info(f"Dashboard quick edit: Updated '{field_awaiting_input}' to '{parsed_value}' for chat {chat_id}")
            ctx.chat_data[AWAITING_INPUT_FOR] = None # Clear awaiting state
        await _send_or_edit_dashboard_message(chat_id,ctx) # Refresh dashboard with new value

# Monitor function now takes unique_trade_id
async def monitor_tp1_and_cancel_entries(application: Application, unique_trade_id: str, monitor_data: Dict[str, Any]):
    chat_id = monitor_data["chat_id"]; symbol = monitor_data["symbol"]
    initial_pos_size = monitor_data["initial_pos_size"]; tp1_expected_close_qty = monitor_data["tp1_expected_close_qty"]
    limit_entry_order_ids = monitor_data.get("limit_entry_order_ids", [])
    instrument_tick_size = monitor_data["instrument_tick_size"]; instrument_qty_step = monitor_data["instrument_qty_step"]
    position_idx_to_monitor = monitor_data.get("position_idx", 0)

    logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Started. Init Pos: {initial_pos_size}, TP1 Qty: {tp1_expected_close_qty}, Limits: {len(limit_entry_order_ids)}, BE SL: {AUTO_MOVE_SL_TO_BE_AFTER_TP1}, PosIdx: {position_idx_to_monitor}")

    tp1_considered_hit = False
    while True:
        await asyncio.sleep(MONITOR_TP1_INTERVAL_SECONDS)
        current_chat_data_for_persistence_check = application.chat_data.get(chat_id)
        # Check based on unique_trade_id now
        active_monitors_dict_in_persistence = current_chat_data_for_persistence_check.get(ACTIVE_MONITOR_TASK, {}) if current_chat_data_for_persistence_check else {}

        if unique_trade_id not in active_monitors_dict_in_persistence:
            logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Monitor for trade {unique_trade_id} no longer in chat_data. Stopping.")
            break
        # Optional: Deep compare persisted_data with initial monitor_data if necessary
        # persisted_monitor_data = active_monitors_dict_in_persistence.get(unique_trade_id)
        # if persisted_monitor_data != monitor_data: # This could be too strict if any minor field changes unintentionally
        #     logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Persisted monitor data changed. Stopping.")
        #     break
        try:
            pos_response = bybit_client.get_positions(category="linear", symbol=symbol)
            if pos_response and pos_response.get("retCode") == 0 and pos_response.get("result",{}).get("list"):
                current_position_data = next((p for p in pos_response["result"]["list"] if p.get("symbol") == symbol and int(p.get("positionIdx", -1)) == position_idx_to_monitor),None)
                if current_position_data:
                    current_size = Decimal(current_position_data.get("size", "0"))
                    logger.debug(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Current Pos Size: {current_size}, Initial for this trade: {initial_pos_size}")
                    if current_size == Decimal("0"):
                        logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Position for {symbol} (idx {position_idx_to_monitor}) is zero. Assuming closed / TP1 hit broadly. Stopping."); tp1_considered_hit = True; break
                    # This logic assumes initial_pos_size was the size of the market order fill of *this* specific trade.
                    # The reduction is checked against the full position on Bybit.
                    # If other trades add to the position, this could be tricky. For now, it's based on the position snapshot.
                    # A more robust way is to track order fills for TPs. Current logic is size-based.
                    reduction_in_size_from_initial_trade_start = initial_pos_size - current_size
                    if current_size < initial_pos_size : # Ensure position reduced at all since this monitor started
                         qty_tolerance = tp1_expected_close_qty * Decimal("0.05") # 5% tolerance
                         # Check if the reduction in position is approximately what TP1 would cause
                         if tp1_expected_close_qty > Decimal("0") and (tp1_expected_close_qty - qty_tolerance <= reduction_in_size_from_initial_trade_start <= tp1_expected_close_qty + qty_tolerance):
                            logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Position reduced by approx TP1 qty for this trade. TP1 HIT for this instance!"); tp1_considered_hit = True; break
                else: logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] No position record for {symbol} (idx {position_idx_to_monitor}). Assuming closed. Stopping."); tp1_considered_hit = True; break
            else: logger.warning(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Error fetching positions: {pos_response.get('retMsg') if pos_response else 'No resp'}. Retrying.")
        except (requests.exceptions.ReadTimeout, httpx.ReadTimeout) as e_timeout_monitor: logger.warning(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Timeout fetching positions: {e_timeout_monitor}. Retrying.")
        except Exception as e: logger.error(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Exception in monitor loop: {e}. Retrying.", exc_info=False)

    loop = asyncio.get_running_loop() # Get loop for sending messages from thread
    if tp1_considered_hit:
        if limit_entry_order_ids:
            logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] TP1/Pos Closed for trade instance. Cancelling associated entries: {limit_entry_order_ids}"); active_orders_to_cancel_reqs = []
            try:
                # Fetch all open orders for the symbol to find which ones are still active
                open_orders_resp = bybit_client.get_open_orders(category="linear", symbol=symbol, openOnly=0, limit=50) # openOnly=0 might include filled/cancelled, check status
                if open_orders_resp.get("retCode") == 0 and open_orders_resp.get("result",{}).get("list"):
                    active_order_ids_on_exchange = {
                        o['orderId'] for o in open_orders_resp['result']['list']
                        if o['orderId'] in limit_entry_order_ids and o['orderStatus'] in ['New', 'PartiallyFilled', 'Untriggered']
                    }
                    if active_order_ids_on_exchange: active_orders_to_cancel_reqs = [{"category": "linear", "symbol": symbol, "orderId": oid} for oid in active_order_ids_on_exchange]
                    else: logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] No active limit entry orders from this trade instance's IDs found for cancellation.")
                else:
                    logger.warning(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Could not verify open orders for cancellation: {open_orders_resp.get('retMsg')}")
                    asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id, f"⚠️ {escape(symbol)} (Trade ...{unique_trade_id[-6:]}): TP1 hit/Pos closed. Could not verify related entry orders. Please check Bybit.", parse_mode=ParseMode.HTML), loop )

            except Exception as e_get_orders:
                logger.error(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Exception getting open orders for cancellation: {e_get_orders}", exc_info=False)
                asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id, f"⚠️ {escape(symbol)} (Trade ...{unique_trade_id[-6:]}): TP1 hit/Pos closed. ERROR verifying related entry orders. Check Bybit!", parse_mode=ParseMode.HTML), loop )

            if active_orders_to_cancel_reqs:
                try:
                    cancel_response = bybit_client.cancel_batch_order(category="linear", request=active_orders_to_cancel_reqs); cancelled_count, failed_count = 0,0
                    if cancel_response.get("retCode") == 0 and cancel_response.get("result",{}).get("list"):
                        for item_result in cancel_response["result"]["list"]:
                            if item_result.get("orderId"): cancelled_count +=1
                            else: failed_count +=1; logger.warning(f"[Monitor] Failed cancel order linked to trade {unique_trade_id[-6:]}: {item_result.get('orderLinkId')} - {item_result.get('msg')}")
                    elif cancel_response.get("retCode") != 0 : logger.error(f"[Monitor] Batch cancel API failed for trade {unique_trade_id[-6:]}: {cancel_response.get('retMsg')}"); failed_count = len(active_orders_to_cancel_reqs)

                    status_msg = f"ℹ️ {escape(symbol)} (Trade ...{unique_trade_id[-6:]}): TP1 hit/Pos closed. Limit Entries Cancel attempts: {len(active_orders_to_cancel_reqs)}. Success: {cancelled_count}, Fail: {failed_count}."
                    asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id, status_msg, parse_mode=ParseMode.HTML), loop)
                except Exception as e_cancel_batch:
                    logger.error(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Exception during batch cancellation: {e_cancel_batch}", exc_info=True)
                    asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id, f"⚠️ {escape(symbol)} (Trade ...{unique_trade_id[-6:]}): TP1 hit/Pos closed. CRITICAL ERROR cancelling related entries. Check Bybit!", parse_mode=ParseMode.HTML),loop)
            elif limit_entry_order_ids: # If there were IDs but none active
                 logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] TP1 hit/Pos closed. No active limit entry orders matching this trade instance's IDs were found to cancel.")


        if AUTO_MOVE_SL_TO_BE_AFTER_TP1:
            logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] TP1 hit. Attempting SL to BE for remaining position (if any).")
            try:
                pos_resp_be = bybit_client.get_positions(category="linear", symbol=symbol)
                if pos_resp_be and pos_resp_be.get("retCode") == 0 and pos_resp_be.get("result",{}).get("list"):
                    pos_idx_be = position_idx_to_monitor # Use the idx from the monitor_data
                    current_pos_be = next((p for p in pos_resp_be["result"]["list"] if p.get("symbol") == symbol and int(p.get("positionIdx", -1)) == pos_idx_be), None)

                    if current_pos_be and Decimal(current_pos_be.get("size", "0")) > Decimal("0"):
                        be_price_dec = Decimal(current_pos_be.get("avgPrice", "0")); remaining_size_dec = Decimal(current_pos_be.get("size", "0"))
                        tick_size = instrument_tick_size; qty_step = instrument_qty_step # From monitor_data

                        if not tick_size or not qty_step:
                            logger.error(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] CRITICAL: Tick/Qty step missing in monitor_data for BE SL.");
                            asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id, f"⚠️ {escape(symbol)} (Trade ...{unique_trade_id[-6:]}): TP1. Internal error (no inst. info) for SL to BE.", parse_mode=ParseMode.HTML), loop)
                        else:
                            adjusted_be_price_str = adjust_price(be_price_dec, tick_size)
                            adjusted_rem_size_str = adjust_qty(remaining_size_dec, qty_step)
                            if Decimal(adjusted_rem_size_str) <= Decimal("0"):
                                logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Rem. size for BE SL <=0 after adjustment. No BE SL set.")
                            else:
                                logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Setting SL to BE: Price {adjusted_be_price_str}, Size {adjusted_rem_size_str} for positionIdx {pos_idx_be}")
                                res_sl_be = bybit_client.set_trading_stop(category="linear", symbol=symbol,stopLoss=adjusted_be_price_str,slTriggerBy="LastPrice",positionIdx=pos_idx_be,tpslMode="Partial",slSize=adjusted_rem_size_str)
                                if res_sl_be.get("retCode") == 0:
                                    msg = f"✅ {escape(symbol)} (Trade ...{unique_trade_id[-6:]}): TP1 hit. SL moved to BE @<code>{adjusted_be_price_str}</code> for Qty <code>{adjusted_rem_size_str}</code>."
                                    logger.info(msg)
                                    asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML), loop)
                                else:
                                    msg = f"⚠️ {escape(symbol)} (Trade ...{unique_trade_id[-6:]}): TP1 hit. Failed to move SL to BE: {escape(res_sl_be.get('retMsg','Unknown'))} (Code: {res_sl_be.get('retCode')})"
                                    logger.error(msg + f" Response: {res_sl_be}")
                                    asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML), loop)
                    else: logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] No active position for {symbol} (idx {pos_idx_be}) found to move SL to BE.")
                else: logger.warning(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Could not get position data for BE SL check: {pos_resp_be.get('retMsg') if pos_resp_be else 'No resp'}")
            except Exception as e_be_sl:
                logger.error(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Exception moving SL to BE: {e_be_sl}", exc_info=True)
                asyncio.run_coroutine_threadsafe(application.bot.send_message(chat_id, f"⚠️ {escape(symbol)} (Trade ...{unique_trade_id[-6:]}): TP1 hit. CRITICAL ERROR moving SL to BE. Details: {escape(str(e_be_sl)[:100])}", parse_mode=ParseMode.HTML), loop)
    else:
        logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Loop exited. TP1 for this trade instance NOT considered hit or monitor stopped for other reasons. Associated entries remain if not cancelled by other means.")

    # Clean up this monitor's entry from persistence using unique_trade_id
    chat_data_for_cleanup = application.chat_data.get(chat_id)
    if chat_data_for_cleanup:
        all_active_monitors = chat_data_for_cleanup.get(ACTIVE_MONITOR_TASK) # New key
        if isinstance(all_active_monitors, dict) and unique_trade_id in all_active_monitors:
            del all_active_monitors[unique_trade_id]
            logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Removed monitor data for trade {unique_trade_id} from persistence.")
            if not all_active_monitors: # If the main dictionary is now empty
                # Keep the ACTIVE_MONITOR_TASK key even if empty, to avoid type issues on next access
                # chat_data_for_cleanup[ACTIVE_MONITOR_TASK] = {} # This is already the state
                logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] No active monitors left for chat {chat_id}.")
    logger.info(f"[Monitor-{symbol}-{unique_trade_id[-6:]}-{chat_id}] Task finished.")

async def resume_active_monitors(application: Application) -> None:
    logger.info("Attempting to resume active monitors on startup...")
    if not application.chat_data: logger.info("No chat_data found, skipping monitor resumption."); return
    main_event_loop = asyncio.get_running_loop(); resumed_monitors_count = 0

    for chat_id_key, chat_data_val in list(application.chat_data.items()): # Use list() for safe iteration if modifying
        if not isinstance(chat_data_val, dict): logger.debug(f"Skipping item in app.chat_data, not dict: key {chat_id_key}"); continue

        # ACTIVE_MONITOR_TASK now stores {unique_trade_id: monitor_data_dict}
        persisted_monitors_for_chat = chat_data_val.get(ACTIVE_MONITOR_TASK, {})

        if not isinstance(persisted_monitors_for_chat, dict):
            logger.warning(f"Chat {chat_id_key}: {ACTIVE_MONITOR_TASK} is not a dict ({type(persisted_monitors_for_chat)}). Clearing and skipping.")
            chat_data_val[ACTIVE_MONITOR_TASK] = {}
            continue

        if not persisted_monitors_for_chat: continue # No monitors for this chat

        trade_ids_to_remove_after_check = []
        for trade_id_to_resume, monitor_task_data in persisted_monitors_for_chat.items():
            if not (isinstance(monitor_task_data, dict) and
                    "symbol" in monitor_task_data and
                    "chat_id" in monitor_task_data and
                    "initial_pos_size" in monitor_task_data and
                    "tp1_expected_close_qty" in monitor_task_data):
                logger.warning(f"Corrupted/incomplete monitor data for trade_id {trade_id_to_resume} in chat {chat_id_key}. Data: {monitor_task_data}. Removing.")
                trade_ids_to_remove_after_check.append(trade_id_to_resume)
                continue

            actual_chat_id = monitor_task_data["chat_id"]
            symbol_to_resume = monitor_task_data["symbol"]
            position_idx_to_check = monitor_task_data.get("position_idx", 0)
            logger.info(f"Found potential monitor for chat {actual_chat_id}, trade_id {trade_id_to_resume[-6:]} (Symbol: {symbol_to_resume})")

            try:
                pos_response = bybit_client.get_positions(category="linear", symbol=symbol_to_resume)
                position_is_active = False; current_pos_size_on_exchange = Decimal("0")
                persisted_initial_pos_size = monitor_task_data["initial_pos_size"] # Already asserted to be Decimal if loaded from pkl right
                persisted_tp1_expected_close_qty = monitor_task_data["tp1_expected_close_qty"]

                if pos_response.get("retCode") == 0 and pos_response.get("result", {}).get("list"):
                    current_pos_data_on_exchange = next((p for p in pos_response["result"]["list"] if p.get("symbol") == symbol_to_resume and int(p.get("positionIdx",-1)) == position_idx_to_check), None)
                    if current_pos_data_on_exchange:
                        current_pos_size_on_exchange = Decimal(current_pos_data_on_exchange.get("size", "0"))
                        if current_pos_size_on_exchange > Decimal("0"): position_is_active = True
                else:
                    logger.warning(f"Could not fetch position for {symbol_to_resume} (trade {trade_id_to_resume[-6:]}, chat {actual_chat_id}) for resumption. Error: {pos_response.get('retMsg')}. Skipping.")
                    asyncio.run_coroutine_threadsafe(application.bot.send_message(actual_chat_id, f"⚠️ Bot restarted. Could not fetch position data for {escape(symbol_to_resume)} (Trade ...{trade_id_to_resume[-6:]}) monitor. It will not be resumed.", parse_mode=ParseMode.HTML), main_event_loop)
                    trade_ids_to_remove_after_check.append(trade_id_to_resume)
                    continue

                if position_is_active:
                    # Check if TP1 logic indicates it might have been hit while bot was down
                    reduction_since_initial_trade = persisted_initial_pos_size - current_pos_size_on_exchange
                    if current_pos_size_on_exchange < persisted_initial_pos_size: # Position reduced
                        qty_tolerance_resumed = persisted_tp1_expected_close_qty * Decimal("0.05")
                        if persisted_tp1_expected_close_qty > Decimal("0") and \
                           (persisted_tp1_expected_close_qty - qty_tolerance_resumed <= reduction_since_initial_trade <= persisted_tp1_expected_close_qty + qty_tolerance_resumed):
                            logger.info(f"Monitor for {symbol_to_resume} (Trade {trade_id_to_resume[-6:]}, chat {actual_chat_id}) not resumed: TP1 for this trade instance appears met based on position size reduction.")
                            trade_ids_to_remove_after_check.append(trade_id_to_resume)
                            # Potentially trigger the rest of TP1 logic (cancel entries, SL to BE) here if desired for missed events
                            continue

                    logger.info(f"Resuming monitor for chat {actual_chat_id}, trade_id {trade_id_to_resume[-6:]} (Symbol: {symbol_to_resume}).")
                    # Pass trade_id and the full monitor_data dict
                    asyncio.run_coroutine_threadsafe(monitor_tp1_and_cancel_entries(application=application, unique_trade_id=trade_id_to_resume, monitor_data=monitor_task_data),main_event_loop)
                    asyncio.run_coroutine_threadsafe(application.bot.send_message(actual_chat_id, f"ℹ️ Bot restarted. Monitor for {escape(symbol_to_resume)} (Trade ...{trade_id_to_resume[-6:]}) RESUMED.", parse_mode=ParseMode.HTML), main_event_loop); resumed_monitors_count +=1
                else: # Position not active
                    logger.info(f"Monitor for {symbol_to_resume} (Trade {trade_id_to_resume[-6:]}, chat {actual_chat_id}) not resumed: Position seems closed or zero for specified symbol/idx.")
                    trade_ids_to_remove_after_check.append(trade_id_to_resume)

            except (requests.exceptions.ReadTimeout, httpx.ReadTimeout) as e_timeout_resume:
                logger.error(f"Timeout resuming monitor for {symbol_to_resume} (Trade {trade_id_to_resume[-6:]}): {e_timeout_resume}")
                asyncio.run_coroutine_threadsafe(application.bot.send_message(actual_chat_id, f"⚠️ Bot restarted. Network timeout resuming monitor for {escape(symbol_to_resume)} (Trade ...{trade_id_to_resume[-6:]}). It will not be resumed.", parse_mode=ParseMode.HTML),main_event_loop)
                trade_ids_to_remove_after_check.append(trade_id_to_resume)
            except Exception as e_resume:
                logger.error(f"Error resuming monitor for chat {actual_chat_id}, trade_id {trade_id_to_resume[-6:]} (Symbol {symbol_to_resume}): {e_resume}", exc_info=True)
                asyncio.run_coroutine_threadsafe(application.bot.send_message(actual_chat_id, f"⚠️ Bot restarted. Error resuming monitor for {escape(symbol_to_resume)} (Trade ...{trade_id_to_resume[-6:]}). It will not be resumed.", parse_mode=ParseMode.HTML),main_event_loop)
                trade_ids_to_remove_after_check.append(trade_id_to_resume)

        # Clean up monitors that were not resumed or had bad data
        for trade_id_to_del in trade_ids_to_remove_after_check:
            if trade_id_to_del in persisted_monitors_for_chat:
                del persisted_monitors_for_chat[trade_id_to_del]
                logger.info(f"Chat {chat_id_key}: Removed trade_id {trade_id_to_del} from {ACTIVE_MONITOR_TASK}.")
        # Persisted_monitors_for_chat (which is chat_data_val[ACTIVE_MONITOR_TASK]) is now updated

    logger.info(f"Finished checking monitors. Resumed: {resumed_monitors_count} tasks.")


def execute_trade_logic(trade_config:Dict[str,Any],application_obj: Application, main_event_loop:asyncio.AbstractEventLoop)->str:
    sym = trade_config.get(SYMBOL); margin_u = trade_config.get(MARGIN_AMOUNT, Decimal("0")); leverage_raw = trade_config.get(LEVERAGE, 1)
    current_order_strategy = trade_config.get(ORDER_STRATEGY, STRATEGY_MARKET_AND_LIMITS) # Default if not set
    try: lev_val = int(leverage_raw); assert lev_val > 0
    except: return "❌ Invalid leverage. Aborting."

    eff_total_u = margin_u * Decimal(str(lev_val))
    limit_entry_1_price_raw = trade_config.get(LIMIT_ENTRY_1_PRICE); limit_entry_2_price_raw = trade_config.get(LIMIT_ENTRY_2_PRICE)
    tp_prices_raw = [trade_config.get(TP1_PRICE), trade_config.get(TP2_PRICE), trade_config.get(TP3_PRICE), trade_config.get(TP4_PRICE)]; sl_price_raw = trade_config.get(SL_PRICE)
    position_idx_val = trade_config.get(POSITION_IDX, 0); chat_id_for_notifications = trade_config.get("_temp_chat_id", 0); side = trade_config.get(SIDE)

    summary = [f"🚀 <b>Trade Execution Summary for {escape(str(sym))}</b>"]
    summary.append(f"ℹ️ Side: <b>{escape(str(side))}</b>, Margin: <code>{margin_u}</code> USDT, Leverage: {lev_val}x ▻ Eff. Pos: ~<code>{eff_total_u:.2f}</code> USDT")
    strategy_display = "Market + 2 Limits" if current_order_strategy == STRATEGY_MARKET_AND_LIMITS else "Market Order Only"
    summary.append(f"📋 Order Strategy: <b>{strategy_display}</b>")

    required_fields_present = all([sym, side, margin_u > Decimal("0"), sl_price_raw, all(tp is not None for tp in tp_prices_raw)])
    if current_order_strategy == STRATEGY_MARKET_AND_LIMITS:
        if not (limit_entry_1_price_raw and limit_entry_2_price_raw):
            required_fields_present = False

    if not required_fields_present:
        summary.append("❌ Critical config fields missing for the chosen strategy. Aborting."); return "\n".join(summary)

    try:
        sl_price_dec = Decimal(str(sl_price_raw))
        tp_prices_dec = [Decimal(str(p)) for p in tp_prices_raw]
        if sl_price_dec <= 0 or any(p <= 0 for p in tp_prices_dec): raise InvalidOperation("TP/SL prices must be positive.")
        limit_entry_prices_dec = []
        if current_order_strategy == STRATEGY_MARKET_AND_LIMITS:
            limit_entry_prices_dec = [Decimal(str(limit_entry_1_price_raw)), Decimal(str(limit_entry_2_price_raw))]
            if any(p <= 0 for p in limit_entry_prices_dec): raise InvalidOperation("Limit entry prices must be positive for Market+Limits strategy.")
    except InvalidOperation as e:
        summary.append(f"❌ Invalid price format: {escape(str(e))}. Aborting."); return "\n".join(summary)

    # Unique ID for this specific trade execution instance
    unique_trade_instance_id = uuid.uuid4().hex
    summary.append(f"🆔 Trade Instance ID: ...<code>{unique_trade_instance_id[-12:]}</code>")


    app_chat_data_exec = application_obj.chat_data.get(chat_id_for_notifications) if chat_id_for_notifications else None
    tick_size_dec = app_chat_data_exec.get(INSTRUMENT_TICK_SIZE) if app_chat_data_exec else None
    qty_step_dec = app_chat_data_exec.get(INSTRUMENT_QTY_STEP) if app_chat_data_exec else None

    if not tick_size_dec or not qty_step_dec:
        logger.warning(f"[{sym}-{unique_trade_instance_id[-6:]}] Tick/Qty step not in chat_data. Fetching fresh.")
        inst_info_exec = get_instrument_info(sym)
        if not inst_info_exec:
            summary.append(f"❌ Could not get instrument info for {escape(str(sym))} to proceed. Aborting."); return "\n".join(summary)
        try:
            tick_size_dec = Decimal(inst_info_exec["priceFilter"]["tickSize"]); qty_step_dec = Decimal(inst_info_exec["lotSizeFilter"]["qtyStep"])
            if app_chat_data_exec:
                app_chat_data_exec[INSTRUMENT_TICK_SIZE] = tick_size_dec
                app_chat_data_exec[INSTRUMENT_QTY_STEP] = qty_step_dec
        except (KeyError, InvalidOperation, TypeError) as e_inst_fallback:
            summary.append(f"❌ Error processing instrument info (tick/qty) fallback: {escape(str(e_inst_fallback))}. Aborting."); return "\n".join(summary)

    try: # Fetch latest info like minOrderQty
        latest_inst_info = get_instrument_info(sym)
        if not latest_inst_info: summary.append(f"❌ CRITICAL: Failed to get latest instrument info for {escape(str(sym))} (min_qty/base_coin). Aborting."); return "\n".join(summary)
        min_order_qty_dec = Decimal(latest_inst_info["lotSizeFilter"]["minOrderQty"]); base_coin = latest_inst_info.get("baseCoin", "")
        adjusted_sl_price_str = adjust_price(sl_price_dec, tick_size_dec)
        summary.append(f"🔩 Instrument Details: Tick Size <code>{tick_size_dec.normalize()}</code>, Qty Step <code>{qty_step_dec.normalize()}</code>, Min Qty <code>{min_order_qty_dec.normalize()}</code>"); summary.append(f"🛡️ Adj. SL Price: <code>{adjusted_sl_price_str}</code>")
    except (KeyError, InvalidOperation, TypeError) as e: summary.append(f"❌ Error processing instrument info (min_qty/base_coin section): {escape(str(e))}. Aborting."); logger.error(f"Inst info processing error for {sym}: {e}", exc_info=True); return "\n".join(summary)


    try: # Leverage Setting
        logger.info(f"[{sym}-{unique_trade_instance_id[-6:]}] Attempting to set leverage to {str(lev_val)}x (Idx: {position_idx_val})")
        # This call will raise InvalidRequestError if retCode != 0
        res_leverage = bybit_client.set_leverage(
            category="linear",
            symbol=sym,
            buyLeverage=str(lev_val),
            sellLeverage=str(lev_val),
            positionIdx=position_idx_val
        )
        # If pybit didn't raise an exception, retCode was 0
        summary.append(f"✅ Leverage set to {lev_val}x successfully.")
        # Log the full response for transparency, even on success
        logger.info(f"[{sym}-{unique_trade_instance_id[-6:]}] Leverage set successfully (retCode 0). Response: {res_leverage}")

    except InvalidRequestError as e_lev_invalid:
        # pybit raised InvalidRequestError, now check the specific Bybit retCode stored in e_lev_invalid.status_code
        bybit_ret_code = e_lev_invalid.status_code
        bybit_ret_msg = e_lev_invalid.message # This should contain the original message from Bybit

        if bybit_ret_code in [110043, 110025] or "leverage not modified" in bybit_ret_msg.lower() or "leverage is the same as before" in bybit_ret_msg.lower():
            # These are codes for "leverage not modified" or "leverage is the same as before"
            summary.append(f"ℹ️ Leverage for {sym} already at {lev_val}x or no change needed (API Code: {bybit_ret_code}, Msg: {escape(bybit_ret_msg)}).")
            logger.info(f"[{sym}-{unique_trade_instance_id[-6:]}] Leverage already set or not modified (API Code: {bybit_ret_code}, Msg: '{bybit_ret_msg}'). Continuing execution.")
            # This is NOT an aborting error, so we allow execution to continue.
        else:
            # This is a different, unexpected API error for leverage setting from Bybit via InvalidRequestError
            summary.append(f"❌ API Error setting leverage: {escape(bybit_ret_msg)} (Code: {bybit_ret_code}). Aborting.")
            logger.error(f"[{sym}-{unique_trade_instance_id[-6:]}] Unhandled Bybit API Error via InvalidRequestError while setting leverage: {bybit_ret_msg} (Code: {bybit_ret_code})", exc_info=True)
            return "\n".join(summary) # Abort on other leverage errors

    except FailedRequestError as e_lev_failed: # Catches network issues, timeouts during the request, etc., from pybit
        summary.append(f"❌ API Request Failed setting leverage: {escape(str(e_lev_failed))}. Aborting.")
        logger.error(f"[{sym}-{unique_trade_instance_id[-6:]}] Leverage API FailedRequestError: {e_lev_failed}", exc_info=True)
        return "\n".join(summary)

    except Exception as e_lev_unexp: # Catches any other unexpected Python errors during the leverage operation
        summary.append(f"❌ Unexpected Python error setting leverage: {escape(str(e_lev_unexp))}. Aborting.")
        logger.error(f"[{sym}-{unique_trade_instance_id[-6:]}] Unexpected Python Error during leverage setting: {e_lev_unexp}", exc_info=True)
        return "\n".join(summary)


    # Market Order
    market_usdt_alloc = eff_total_u * (Decimal("1.0") if current_order_strategy == STRATEGY_MARKET_ONLY else ENTRY_PORTION_ALLOCATION[0])
    actual_market_fill_qty = Decimal("0"); actual_avg_entry_price = Decimal("0"); min_order_value_usdt = Decimal("5.0") # Bybit's typical minimum for USDT pair derivatives

    logger.info(f"[{sym}-{unique_trade_instance_id[-6:]}] Market Order. Strategy: {current_order_strategy}. USDT Allocation: {market_usdt_alloc:.2f}")
    if market_usdt_alloc > Decimal("0"): # Only proceed if allocation is positive
        try:
            tickers_resp = bybit_client.get_tickers(category="linear", symbol=sym)
            if not (tickers_resp and tickers_resp.get("retCode") == 0 and tickers_resp.get("result",{}).get("list")):
                summary.append(f"❌ Could not fetch current price for {escape(str(sym))} for market order. Market entry aborted.")
                logger.error(f"[{sym}-{unique_trade_instance_id[-6:]}] Could not fetch tickers. Response: {tickers_resp}")
            else:
                last_price_dec = Decimal(tickers_resp["result"]["list"][0]["lastPrice"])
                if last_price_dec <= 0:
                    summary.append(f"❌ Invalid last price (<code>{last_price_dec}</code>) for {escape(str(sym))}. Market entry aborted.")
                else:
                    estimated_market_qty = market_usdt_alloc / last_price_dec
                    adjusted_market_qty_str = adjust_qty(estimated_market_qty, qty_step_dec)

                    if market_usdt_alloc < min_order_value_usdt:
                         summary.append(f"⚠️ Market order value (<code>{market_usdt_alloc:.2f}</code> USDT) < min (<code>{min_order_value_usdt}</code> USDT). Skipping market order.")
                    elif Decimal(adjusted_market_qty_str) < min_order_qty_dec:
                        summary.append(f"⚠️ Adj. market qty <code>{adjusted_market_qty_str}</code> {base_coin} < min <code>{min_order_qty_dec}</code> {base_coin}. Skipping market order.")
                    else:
                        summary.append(f"🛒 Placing Market Order ({side}): Qty ~<code>{adjusted_market_qty_str}</code> {base_coin} (Value: ~<code>{market_usdt_alloc:.2f}</code> USDT)...")
                        market_order_params = {"category": "linear","symbol": sym,"side": side,"orderType": "Market","qty": adjusted_market_qty_str,"positionIdx": position_idx_val,"orderLinkId": f"mkt_{sym}_{unique_trade_instance_id[-12:]}"} # Use part of unique_id for link
                        res_market_order = bybit_client.place_order(**market_order_params)
                        if res_market_order.get("retCode") == 0 and res_market_order.get("result",{}).get("orderId"):
                            summary.append(f"✅ Market order submitted (ID: ...<code>{escape(res_market_order['result']['orderId'][-6:])}</code>). Checking fill...")
                            time.sleep(3) # Allow time for fill
                            pos_after_market = bybit_client.get_positions(category="linear", symbol=sym, positionIdx=position_idx_val)
                            if pos_after_market.get("retCode") == 0 and pos_after_market.get("result",{}).get("list"):
                                current_pos_data = next((p for p in pos_after_market["result"]["list"] if p.get("symbol") == sym and int(p.get("positionIdx", -1)) == position_idx_val),None)
                                if current_pos_data and current_pos_data.get("side") == side: # Check side matches
                                    actual_market_fill_qty = Decimal(current_pos_data.get("size", "0"))
                                    actual_avg_entry_price = Decimal(current_pos_data.get("avgPrice", "0"))
                                    if actual_market_fill_qty > 0 and actual_avg_entry_price > 0:
                                        summary.append(f"🟢 Market Order Filled: Qty <code>{actual_market_fill_qty.normalize()}</code> {base_coin} @ Avg Price <code>{actual_avg_entry_price.normalize()}</code>")
                                    else:
                                        summary.append(f"⚠️ Market submitted, but position size/avgP is zero/invalid. Check Bybit.")
                                else: # Position not found for this idx or side mismatch
                                     summary.append(f"⚠️ Market submitted, but no matching position found or side mismatch for idx {position_idx_val}. Expected side: {side}. Found: {current_pos_data}. Check Bybit.")
                            else:
                                summary.append(f"⚠️ Could not confirm market fill (position fetch error: {escape(pos_after_market.get('retMsg','N/A'))}). Check Bybit.")
                        else:
                            summary.append(f"❌ Market order placement failed: {escape(res_market_order.get('retMsg', 'Err'))} (Code: {res_market_order.get('retCode')})")
        except Exception as e_mkt:
            summary.append(f"❌ Error during market order: {escape(str(e_mkt))}."); logger.error(f"[{sym}-{unique_trade_instance_id[-6:]}] Market order error: {e_mkt}", exc_info=True)
    else:
        summary.append("ℹ️ Market order portion is zero. Skipping market order.")


    # Store actual fill details (even if zero) for monitor use
    if app_chat_data_exec:
        app_chat_data_exec[INITIAL_MARKET_FILL_QTY] = actual_market_fill_qty # Could be zero if skipped/failed
        app_chat_data_exec[INITIAL_AVG_ENTRY_PRICE] = actual_avg_entry_price

    # Limit Entry Orders (only if strategy is Market + Limits)
    limit_order_requests = []; placed_limit_entry_ids_local = []
    if current_order_strategy == STRATEGY_MARKET_AND_LIMITS and len(limit_entry_prices_dec) == 2 :
        limit_usdt_allocs = [eff_total_u * ENTRY_PORTION_ALLOCATION[1], eff_total_u * ENTRY_PORTION_ALLOCATION[2]]
        for i, limit_price_dec_val in enumerate(limit_entry_prices_dec):
            usdt_alloc_for_limit = limit_usdt_allocs[i]; adjusted_limit_price_str = adjust_price(limit_price_dec_val, tick_size_dec)
            if Decimal(adjusted_limit_price_str) <= 0: summary.append(f"⚠️ L{i+1} Entry: Adj. price <code>{adjusted_limit_price_str}</code> invalid. Skipping."); continue
            try:
                limit_qty_estimated = usdt_alloc_for_limit / Decimal(adjusted_limit_price_str)
                adjusted_limit_qty_str = adjust_qty(limit_qty_estimated, qty_step_dec)
                if usdt_alloc_for_limit < min_order_value_usdt : summary.append(f"⚠️ L{i+1} value (<code>{usdt_alloc_for_limit:.2f}</code> USDT) < min (<code>{min_order_value_usdt}</code> USDT). Skipping limit order."); continue
                if Decimal(adjusted_limit_qty_str) < min_order_qty_dec: summary.append(f"⚠️ L{i+1} Qty <code>{adjusted_limit_qty_str}</code> {base_coin} < min <code>{min_order_qty_dec}</code> {base_coin}. Skipping limit order."); continue

                limit_order_requests.append({
                    "category": "linear","symbol": sym,"side": side,"orderType": "Limit",
                    "qty": adjusted_limit_qty_str,"price": adjusted_limit_price_str,
                    "positionIdx": position_idx_val,"orderLinkId": f"L{i+1}_{sym}_{unique_trade_instance_id[-12:]}_{i}"
                })
            except Exception as e_prep_limit:
                summary.append(f"❌ Error preparing L{i+1} @<code>{limit_price_dec_val}</code>: {escape(str(e_prep_limit))}. Skipping."); logger.error(f"L{i+1} Entry prep error: {e_prep_limit}", exc_info=True)

        if limit_order_requests:
            summary.append(f"📬 Placing {len(limit_order_requests)} Limit Entry orders..."); logger.info(f"[{sym}-{unique_trade_instance_id[-6:]}] Attempting {len(limit_order_requests)} limit entry orders.")
            try:
                res_batch_limit = bybit_client.place_batch_order(category="linear", request=limit_order_requests)
                if res_batch_limit.get("retCode") == 0 and res_batch_limit.get("result",{}).get("list"):
                    for idx, item_res in enumerate(res_batch_limit["result"]["list"]):
                        original_req = limit_order_requests[idx] # Assumes order matches
                        if item_res.get("orderId"):
                            placed_limit_entry_ids_local.append(item_res["orderId"])
                            summary.append(f"✅ Limit Entry {idx+1} @<code>{escape(original_req['price'])}</code> submitted (ID: ...<code>{escape(item_res['orderId'][-6:])}</code>)")
                        else: summary.append(f"❌ Limit Entry {idx+1} @<code>{escape(original_req['price'])}</code> failed: {escape(item_res.get('msg','Err'))} (Code: {item_res.get('code')})")
                elif res_batch_limit.get("retCode") !=0 : summary.append(f"❌ Batch Limit Entry submission failed: {escape(res_batch_limit.get('retMsg'))} (Code: {res_batch_limit.get('retCode')})")
                else: summary.append("⚠️ Batch Limit Entry response OK but no result list. Check Bybit.")
            except Exception as e_blimit:
                summary.append(f"❌ Error placing Batch Limit Entries: {escape(str(e_blimit))}"); logger.error(f"Batch Limit Entry error: {e_blimit}", exc_info=True)

    if app_chat_data_exec: app_chat_data_exec[PLACED_LIMIT_ENTRY_IDS] = placed_limit_entry_ids_local # Store IDs (could be empty)

    # TPs and SL for the Market Filled Portion
    if actual_market_fill_qty > Decimal("0"):
        summary.append(f"🎯 Preparing TPs & SL for market fill of <code>{actual_market_fill_qty.normalize()}</code> {base_coin}..."); tp_order_requests = []; tp_side = "Sell" if side == "Buy" else "Buy"; qty_covered_by_tps = Decimal("0")

        for i, tp_price_dec_val_loop in enumerate(tp_prices_dec): # tp_prices_dec are already Decimal
            if actual_avg_entry_price > 0: # Logical check
                if side == "Buy" and tp_price_dec_val_loop <= actual_avg_entry_price: summary.append(f"⚠️ TP{i+1} @<code>{tp_price_dec_val_loop}</code> not logical (≤ Avg Entry <code>{actual_avg_entry_price}</code>). Skipping."); continue
                if side == "Sell" and tp_price_dec_val_loop >= actual_avg_entry_price: summary.append(f"⚠️ TP{i+1} @<code>{tp_price_dec_val_loop}</code> not logical (≥ Avg Entry <code>{actual_avg_entry_price}</code>). Skipping."); continue

            tp_qty_this_level = actual_market_fill_qty * TP_PERCENTAGES[i]
            # Ensure last TP covers remaining if percentages don't sum perfectly or due to qty_step adjustments
            if i == len(TP_PERCENTAGES) - 1:
                tp_qty_this_level = max(Decimal("0"), actual_market_fill_qty - qty_covered_by_tps)

            adj_tp_qty_str = adjust_qty(tp_qty_this_level, qty_step_dec); adj_tp_price_str = adjust_price(tp_price_dec_val_loop, tick_size_dec)

            if Decimal(adj_tp_qty_str) < min_order_qty_dec:
                if tp_qty_this_level > Decimal("0"): # Only warn if it was meant to be placed
                    summary.append(f"⚠️ TP{i+1} Qty <code>{adj_tp_qty_str}</code> ({tp_qty_this_level.normalize()}) {base_coin} < min <code>{min_order_qty_dec}</code>. Skipping.");
                continue # Skip if below min qty

            # Safety check: cumulative TP qty shouldn't grossly exceed total market fill
            if (qty_covered_by_tps + Decimal(adj_tp_qty_str)) > actual_market_fill_qty * Decimal("1.01"): # Allow 1% buffer for dust
                summary.append(f"⚠️ TP{i+1} makes total TP qty (<code>{qty_covered_by_tps + Decimal(adj_tp_qty_str)}</code>) exceed fill (<code>{actual_market_fill_qty}</code>). Adjusted/Stopping TP prep.");
                # Potentially adjust last TP qty down here if strictly needed or just break.
                # For simplicity, if this happens, this TP might be skipped or user needs to check allocations.
                break # Stop adding more TPs

            qty_covered_by_tps += Decimal(adj_tp_qty_str)
            tp_order_requests.append({
                "category": "linear","symbol": sym,"side": tp_side,"orderType": "Limit",
                "qty": adj_tp_qty_str,"price": adj_tp_price_str,"reduceOnly": True,
                "positionIdx": position_idx_val, "orderLinkId": f"TP{i+1}_{sym}_{unique_trade_instance_id[-12:]}_{i}"
            })

        if tp_order_requests:
            summary.append(f"💸 Placing {len(tp_order_requests)} Take Profit orders..."); logger.info(f"[{sym}-{unique_trade_instance_id[-6:]}] Attempting {len(tp_order_requests)} TP orders.")
            try:
                res_batch_tp = bybit_client.place_batch_order(category="linear", request=tp_order_requests)
                if res_batch_tp.get("retCode") == 0 and res_batch_tp.get("result",{}).get("list"):
                    for idx, item_res_tp in enumerate(res_batch_tp["result"]["list"]):
                        original_req_tp = tp_order_requests[idx]
                        if item_res_tp.get("orderId"): summary.append(f"✅ TP{idx+1} Qty<code>{escape(original_req_tp['qty'])}</code> @<code>{escape(original_req_tp['price'])}</code> submitted (ID: ...<code>{escape(item_res_tp['orderId'][-6:])}</code>)")
                        else: summary.append(f"❌ TP{idx+1} @<code>{escape(original_req_tp['price'])}</code> failed: {escape(item_res_tp.get('msg','Err'))} (Code: {item_res_tp.get('code')})")
                elif res_batch_tp.get("retCode") !=0: summary.append(f"❌ Batch TP submission failed: {escape(res_batch_tp.get('retMsg'))} (Code: {res_batch_tp.get('retCode')})")
                else: summary.append("⚠️ Batch TP response OK but no result list. Check Bybit.")
            except Exception as e_btp:
                summary.append(f"❌ Error placing Batch TPs: {escape(str(e_btp))}"); logger.error(f"Batch TP error: {e_btp}", exc_info=True)

        # Stop Loss for the entire market-filled quantity
        sl_logical = True
        if actual_avg_entry_price > 0: # Logical check for SL
            if side == "Buy" and sl_price_dec >= actual_avg_entry_price: summary.append(f"⚠️ SL Price <code>{adjusted_sl_price_str}</code> is not logical (should be < avg entry for Long). SL not set."); sl_logical = False
            if side == "Sell" and sl_price_dec <= actual_avg_entry_price: summary.append(f"⚠️ SL Price <code>{adjusted_sl_price_str}</code> is not logical (should be > avg entry for Short). SL not set."); sl_logical = False

        if sl_logical:
            sl_size_str = adjust_qty(actual_market_fill_qty, qty_step_dec) # SL for the whole filled market qty
            if Decimal(sl_size_str) < min_order_qty_dec:
                summary.append(f"⚠️ Adjusted SL Size (<code>{sl_size_str}</code>) < Min Order Qty (<code>{min_order_qty_dec}</code>). SL not set.")
            else:
                try:
                    logger.info(f"[{sym}-{unique_trade_instance_id[-6:]}] Setting SL: SL='{adjusted_sl_price_str}', Qty='{sl_size_str}', PosIdx={position_idx_val}")
                    res_sl = bybit_client.set_trading_stop(category="linear",symbol=sym,stopLoss=adjusted_sl_price_str,slTriggerBy="LastPrice",positionIdx=position_idx_val,tpslMode="Partial",slSize=sl_size_str) # Partial mode to set for specific size
                    if res_sl.get("retCode") == 0: summary.append(f"✅ SL set @<code>{escape(adjusted_sl_price_str)}</code> for qty <code>{escape(sl_size_str)}</code>.")
                    else: summary.append(f"❌ SL setting failed: {escape(res_sl.get('retMsg', 'Err'))} (Code: {res_sl.get('retCode')})")
                except Exception as e_sl:
                    summary.append(f"❌ Error setting SL: {escape(str(e_sl))}"); logger.error(f"SL setting error: {e_sl}", exc_info=True)
        else: # SL not logical
             summary.append("ℹ️ SL not set due to logical price issue.")

        # Schedule Monitor if needed
        # Conditions:
        # 1. EITHER limit entries were placed (and might need cancelling if TP1 hits early)
        # OR auto SL-to-BE is enabled.
        # 2. TP1 percentage > 0 and TP1 price is valid.
        # 3. Chat_id, loop, and application object are available.
        monitor_needed = (placed_limit_entry_ids_local or AUTO_MOVE_SL_TO_BE_AFTER_TP1) and \
                         len(TP_PERCENTAGES) > 0 and TP_PERCENTAGES[0] > Decimal("0") and \
                         len(tp_prices_dec) > 0 and tp_prices_dec[0] > Decimal("0") and \
                         chat_id_for_notifications != 0 and main_event_loop and application_obj

        if monitor_needed:
            tp1_expected_close_qty_val = actual_market_fill_qty * TP_PERCENTAGES[0]
            # Ensure all data passed to monitor is of correct type (Decimal for calcs)
            monitor_params_for_persistence = {
                "chat_id": chat_id_for_notifications, "symbol": sym,
                "initial_pos_size": Decimal(actual_market_fill_qty), # Ensure Decimal
                "tp1_expected_close_qty": Decimal(tp1_expected_close_qty_val), # Ensure Decimal
                "limit_entry_order_ids": placed_limit_entry_ids_local,
                "instrument_tick_size": Decimal(tick_size_dec), # Ensure Decimal
                "instrument_qty_step": Decimal(qty_step_dec), # Ensure Decimal
                "position_idx": position_idx_val,
                "unique_trade_id": unique_trade_instance_id # For self-reference if needed inside monitor
            }
            logger.info(f"[{sym}-{unique_trade_instance_id[-6:]}] Scheduling monitor. Data: {monitor_params_for_persistence}")
            asyncio.run_coroutine_threadsafe(
                monitor_tp1_and_cancel_entries(application=application_obj, unique_trade_id=unique_trade_instance_id, monitor_data=monitor_params_for_persistence),
                main_event_loop
            )
            if app_chat_data_exec:
                app_chat_data_exec.setdefault(ACTIVE_MONITOR_TASK, {})[unique_trade_instance_id] = monitor_params_for_persistence
                summary.append(f"⏱️ TP1 & BE SL monitor for Trade ...<code>{unique_trade_instance_id[-6:]}</code> scheduled.")
            else:
                logger.warning(f"[{sym}-{unique_trade_instance_id[-6:]}] No app_chat_data to store monitor task.")
                summary.append(f"⚠️ Monitor scheduled, but couldn't store persistent data for Trade ...<code>{unique_trade_instance_id[-6:]}</code>.")
        else:
            reason = ""
            if not (placed_limit_entry_ids_local or AUTO_MOVE_SL_TO_BE_AFTER_TP1): reason += "No limits/BE."
            if not (len(TP_PERCENTAGES) > 0 and TP_PERCENTAGES[0] > Decimal("0") and len(tp_prices_dec) > 0 and tp_prices_dec[0] > Decimal("0")): reason += " No TP1 defined."
            # other conditions are system level
            summary.append(f"ℹ️ Monitor task NOT scheduled for Trade ...<code>{unique_trade_instance_id[-6:]}</code>. Reason hint: {reason if reason else 'Conditions not met.'}")

    else: # actual_market_fill_qty <= 0
        if current_order_strategy == STRATEGY_MARKET_ONLY:
             summary.append("❌ Market Only strategy chosen, but market order was not filled or skipped. No further actions taken.")
        else: # Market + Limits, but market portion failed/skipped. Limit orders might still be active if placed before market fill check.
             summary.append("ℹ️ No market order filled. TPs/SL for market portion not set. Any placed limit entries remain.")

    summary.append("\n🏁 Trade setup process complete. Verify orders and positions on Bybit.")
    return "\n".join(summary)

async def error_handler(update:object,context:ContextTypes.DEFAULT_TYPE):
    logger.error(f"Global ErrorHandler caught an exception:",exc_info=context.error)
    if isinstance(context.error, BadRequest) and ("Query is too old" in str(context.error) or "Message is not modified" in str(context.error) or "message to edit not found" in str(context.error)):
        logger.warning(f"Suppressed common BadRequest: {context.error}"); return

    chat_id_for_error = None
    if isinstance(update, Update) and update.effective_chat: chat_id_for_error = update.effective_chat.id
    elif isinstance(update, CallbackQuery) and update.message and update.message.chat: chat_id_for_error = update.message.chat.id
    elif hasattr(context, '_chat_id') and context._chat_id : chat_id_for_error = context._chat_id # For conv timeouts

    error_message_text = f"⚠️ An unexpected error occurred: {escape(str(context.error))[:200]}"
    if isinstance(context.error, TelegramTimedOut): error_message_text = "🕒 Telegram request timed out. Please try your action again."; logger.warning(f"Telegram API TimedOut: {context.error}")
    elif isinstance(context.error, (requests.exceptions.ReadTimeout, httpx.ReadTimeout, httpx.ConnectTimeout)): error_message_text = "🕒 Connection to Bybit API timed out. Check internet or try later."; logger.warning(f"Bybit/HTTPX API Timeout/ConnectionError: {context.error}")

    if chat_id_for_error:
        try: await context.bot.send_message(chat_id_for_error, error_message_text + "\nIf issues persist, you can use /start to begin a fresh setup or /dashboard.", parse_mode=ParseMode.HTML)
        except Exception as e: logger.error(f"Failed to send global error notification to chat {chat_id_for_error}: {e}")
    else: logger.error("Global error, but could not determine chat_id to notify user.")

async def post_init(application: Application) -> None:
    # If using a new ACTIVE_MONITOR_TASK key, this will start fresh for that key.
    # Ensure any old .pkl files with the OLD key are removed or handled.
    await resume_active_monitors(application)

def main():
    logger.info("Bot starting up...")
    try:
        persistence_dir = os.path.dirname(PERSISTENCE_FILE)
        if persistence_dir and not os.path.exists(persistence_dir): os.makedirs(persistence_dir)
        persistence = PicklePersistence(filepath=PERSISTENCE_FILE)
        logger.info(f"Using persistence file: {PERSISTENCE_FILE}")
    except Exception as e:
        logger.error(f"Failed PicklePersistence init: {e}. No persistence.", exc_info=True); persistence = None

    app_builder = ApplicationBuilder().token(TELEGRAM_TOKEN)
    if persistence: app_builder = app_builder.persistence(persistence)
    app_builder.post_init(post_init) # To resume monitors after persistence is loaded
    application = app_builder.build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start_trade_setup_conversation)],
        states={
            ASK_SYMBOL: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_symbol_input)],
            ASK_SIDE: [CallbackQueryHandler(process_side_callback, pattern="^conv_set_side:side:.*")],
            ASK_MARGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_margin_input)],
            ASK_LEVERAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_leverage_input)],
            ASK_ORDER_STRATEGY: [CallbackQueryHandler(process_order_strategy_callback, pattern="^conv_set_os:order_strategy:.*")],
            ASK_L1_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_l1_price_input)],
            ASK_L2_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_l2_price_input)],
            ASK_TP1_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_tp1_price_input)],
            ASK_TP2_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_tp2_price_input)],
            ASK_TP3_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_tp3_price_input)],
            ASK_TP4_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_tp4_price_input)],
            ASK_SL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_sl_price_input)],
            REVIEW_TRADE: [CallbackQueryHandler(process_final_confirmation_callback, pattern="^conv_confirm:.*")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern="^cancel_conversation$"),
            TypeHandler(Update, conversation_timeout) # Catch unhandled updates during conversation as timeout
        ],
        conversation_timeout=CONVERSATION_TIMEOUT_SECONDS,
        per_user=True, per_chat=True, # Independent conversations per user in different chats
        allow_reentry=True # Allows /start to restart the conversation
    )
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("dashboard", dashboard_command))
    application.add_handler(CallbackQueryHandler(button_callback_handler)) # Handles dashboard buttons etc.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, text_input_handler)) # Handles quick edits
    application.add_error_handler(error_handler)

    logger.info("Bot is now polling for updates.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()