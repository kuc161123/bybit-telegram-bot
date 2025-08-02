"""
Predictive Signals Handler - AI-powered trading predictions
"""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime

from config.constants import *
from execution.ai_market_analysis import get_ai_market_insights

logger = logging.getLogger(__name__)

async def show_predictive_signals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AI-powered predictive signals"""
    query = update.callback_query
    if query:
        await query.answer()

    try:
        # Get stats data from bot_data
        bot_data = context.bot_data or {}
        stats_data = {
            'overall_win_rate': 0,
            STATS_WIN_STREAK: bot_data.get(STATS_WIN_STREAK, 0),
            STATS_LOSS_STREAK: bot_data.get(STATS_LOSS_STREAK, 0),
            STATS_TOTAL_TRADES: bot_data.get(STATS_TOTAL_TRADES, 0),
            STATS_TOTAL_PNL: bot_data.get(STATS_TOTAL_PNL, 0),
            'stats_total_wins_pnl': bot_data.get('stats_total_wins_pnl', 0),
            'stats_total_losses_pnl': bot_data.get('stats_total_losses_pnl', 0)
        }

        # Calculate win rate
        total_trades = stats_data[STATS_TOTAL_TRADES]
        wins = bot_data.get(STATS_TOTAL_WINS, 0)
        if total_trades > 0:
            stats_data['overall_win_rate'] = (wins / total_trades) * 100

        # Get the primary trading symbol
        primary_symbol = None
        try:
            from clients.bybit_helpers import get_all_positions
            positions = await get_all_positions()
            active_positions = [p for p in positions if float(p.get('size', 0)) > 0]

            if active_positions:
                # Use the symbol with the largest position
                primary_symbol = max(active_positions, key=lambda p: float(p.get('positionIM', 0))).get('symbol')
            else:
                # Default to BTCUSDT if no active positions
                primary_symbol = "BTCUSDT"
        except Exception as e:
            logger.error(f"Error getting positions for predictive signals: {e}")
            primary_symbol = "BTCUSDT"

        # Get AI market insights
        ai_data = await get_ai_market_insights(primary_symbol, stats_data)

        # Build the predictive signals text
        signals_text = f"""🎯 <b>PREDICTIVE SIGNALS</b>
{'═' * 35}

├─ Win Rate: {ai_data['win_rate']:.1f}% over {ai_data['total_trades']} trades
├─ Win Streak: {ai_data['win_streak']} | Loss Streak: {ai_data['loss_streak']}
├─ Momentum: {ai_data['momentum']}
├─ Next Trade Confidence: {ai_data['confidence']:.0f}%
└─ Trend: {ai_data['trend']}

📊 <b>AI MARKET ANALYSIS</b> ({primary_symbol})
├─ Market Outlook: {ai_data['market_outlook']}
├─ Signal Strength: {ai_data['signal_strength']}
├─ Short-term: {ai_data['short_term_prediction'][:50]}...
└─ Risk Level: {'⚠️ High' if len(ai_data.get('key_risks', [])) > 2 else '✅ Low' if len(ai_data.get('key_risks', [])) == 0 else '🟡 Moderate'}

🎯 <b>TRADING RECOMMENDATIONS</b>
"""

        # Add recommendations
        for i, action in enumerate(ai_data.get('recommended_actions', ['Monitor market conditions'])[:3]):
            if i == len(ai_data.get('recommended_actions', [])) - 1:
                signals_text += f"└─ {action}\n"
            else:
                signals_text += f"├─ {action}\n"

        # Add key risks section
        if ai_data.get('key_risks'):
            signals_text += f"\n⚠️ <b>KEY RISK FACTORS</b>\n"
            for i, risk in enumerate(ai_data['key_risks'][:3]):
                if i == len(ai_data['key_risks']) - 1:
                    signals_text += f"└─ {risk}\n"
                else:
                    signals_text += f"├─ {risk}\n"

        # Add technical indicators if available
        if 'technical' in ai_data and ai_data['technical']:
            signals_text += f"\n📈 <b>TECHNICAL INDICATORS</b>\n"
            signals_text += f"├─ Trend: {ai_data['technical']['trend']}\n"
            signals_text += f"├─ Momentum: {ai_data['technical']['momentum']:+.1f}%\n"
            signals_text += f"└─ Market Regime: {ai_data.get('market_outlook', 'Analyzing')}\n"

        # Add performance metrics
        if 'performance_metrics' in ai_data:
            signals_text += f"\n💰 <b>PERFORMANCE METRICS</b>\n"
            signals_text += f"├─ Profit Factor: {ai_data['performance_metrics']['profit_factor']:.2f}\n"
            signals_text += f"└─ Expectancy: ${ai_data['performance_metrics']['expectancy']:.2f}/trade\n"

        # Add AI insights if available
        if ai_data.get('ai_insights') and not ai_data.get('error'):
            signals_text += f"\n🧠 <b>AI INSIGHTS</b>\n{ai_data['ai_insights']}\n"

        signals_text += f"\n<i>Last updated: {datetime.now().strftime('%H:%M:%S UTC')}</i>"

        # Create keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="predictive_signals"),
                InlineKeyboardButton("📊 Full Analysis", callback_data="ai_insights")
            ],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")]
        ])

        # Send or edit the message
        if query:
            await query.edit_message_text(
                signals_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                signals_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error showing predictive signals: {e}", exc_info=True)
        error_text = "⚠️ <b>Error Loading Predictive Signals</b>\n\nPlease try again later."

        if query:
            await query.edit_message_text(error_text, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(error_text, parse_mode=ParseMode.HTML)