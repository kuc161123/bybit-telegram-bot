#!/usr/bin/env python3
"""
Handler for displaying detailed AI market insights
"""
import logging
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config.constants import *
from execution.ai_market_analysis import get_ai_market_insights
from utils.formatters import format_number, format_price
from utils.safe_format import safe_format, sanitize_for_telegram
from clients.bybit_helpers import get_all_positions

logger = logging.getLogger(__name__)

async def show_ai_insights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed AI market insights"""
    try:
        query = update.callback_query
        if query:
            await query.answer()
            message = query.message
        else:
            message = update.message

        # Get positions to find symbols
        positions = await get_all_positions()
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]

        if not active_positions:
            no_positions_msg = (
                "🤖 <b>AI Market Insights</b>\n\n"
                "No active positions found.\n"
                "Open a position to get AI-powered market analysis."
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="analytics_dashboard")]
            ])

            if query:
                await query.edit_message_text(no_positions_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await message.reply_text(no_positions_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return

        # Get stats data from bot_data
        stats_data = context.bot_data if context.bot_data else {}

        # Build insights for all active positions
        insights_msg = "🤖 <b>AI MARKET INSIGHTS</b>\n"
        insights_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # Sort positions by size (largest first)
        sorted_positions = sorted(active_positions, key=lambda p: float(p.get('positionIM', 0)), reverse=True)

        # Show detailed analysis for top 3 positions
        for i, position in enumerate(sorted_positions[:3]):
            symbol = position.get('symbol', 'UNKNOWN')
            size = float(position.get('size', 0))
            pnl = float(position.get('unrealisedPnl', 0))
            pnl_pct = float(position.get('percentage', 0))

            # Get AI analysis for this symbol
            try:
                ai_analysis = await get_ai_market_insights(symbol, stats_data)

                # Format position header
                insights_msg += f"<b>{i+1}. {html.escape(symbol)}</b> "
                if pnl >= 0:
                    insights_msg += f"<code>+${html.escape(format_number(pnl))} (+{pnl_pct:.1f}%)</code>\n"
                else:
                    insights_msg += f"<code>-${html.escape(format_number(abs(pnl)))} ({pnl_pct:.1f}%)</code>\n"

                # Market outlook
                outlook = ai_analysis.get('market_outlook', 'NEUTRAL')
                signal_strength = ai_analysis.get('signal_strength', 'WEAK')
                confidence = ai_analysis.get('confidence', 50)

                outlook_emoji = "🟢" if outlook == "BULLISH" else "🔴" if outlook == "BEARISH" else "🟡"
                insights_msg += f"├ {outlook_emoji} Outlook: <b>{html.escape(outlook)}</b> ({html.escape(signal_strength)} signal)\n"
                insights_msg += f"├ 🎯 Confidence: <b>{confidence}%</b>\n"

                # Short-term prediction
                prediction = ai_analysis.get('short_term_prediction', 'No prediction available')
                insights_msg += f"├ 📈 Prediction: {html.escape(prediction)}\n"

                # Market data
                market_data = ai_analysis.get('market_data', {})
                if market_data:
                    price_change = market_data.get('price_change_24h', 0)
                    insights_msg += f"├ 📊 24h Change: {price_change:+.1f}%\n"

                # Technical indicators
                technical = ai_analysis.get('technical', {})
                if technical:
                    trend = technical.get('trend', 'N/A')
                    momentum = technical.get('momentum', 0)
                    volatility = technical.get('volatility', 0)
                    insights_msg += f"├ 📉 Technical: {html.escape(trend)} trend, {momentum:+.1f}% momentum, {volatility:.1f}% volatility\n"

                # Sentiment if available
                sentiment = ai_analysis.get('sentiment', {})
                if sentiment.get('available'):
                    sent_score = sentiment.get('score', 50)
                    sent_trend = sentiment.get('trend', 'NEUTRAL')
                    insights_msg += f"├ 💭 Sentiment: {sent_score}/100 ({html.escape(sent_trend)})\n"

                # Key risks
                risks = ai_analysis.get('key_risks', [])
                if risks:
                    insights_msg += f"├ ⚠️ Top Risk: {html.escape(risks[0])}\n"

                # Recommendations
                recommendations = ai_analysis.get('recommended_actions', [])
                if recommendations:
                    insights_msg += f"└ 💡 Action: {html.escape(recommendations[0])}\n"

                insights_msg += "\n"

            except Exception as e:
                logger.error(f"Error getting AI analysis for {symbol}: {e}")
                insights_msg += "└ ⚠️ Analysis temporarily unavailable\n\n"

        # Add performance summary
        total_trades = stats_data.get(STATS_TOTAL_TRADES, 0)
        wins = stats_data.get(STATS_TOTAL_WINS, 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = float(stats_data.get(STATS_TOTAL_PNL, 0))

        insights_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        insights_msg += f"📊 <b>PERFORMANCE CONTEXT</b>\n"
        insights_msg += f"├ Win Rate: {win_rate:.1f}% ({wins}W/{total_trades - wins}L)\n"
        insights_msg += f"├ Total P&L: ${html.escape(format_number(total_pnl))}\n"

        # Add profit factor if available
        total_wins_pnl = float(stats_data.get('stats_total_wins_pnl', 0))
        total_losses_pnl = abs(float(stats_data.get('stats_total_losses_pnl', 0)))
        if total_losses_pnl > 0:
            profit_factor = total_wins_pnl / total_losses_pnl
            insights_msg += f"├ Profit Factor: {profit_factor:.2f}\n"

        # Current streak
        win_streak = stats_data.get(STATS_WIN_STREAK, 0)
        loss_streak = stats_data.get(STATS_LOSS_STREAK, 0)
        if win_streak > 0:
            insights_msg += f"└ Current Streak: 🔥 {win_streak} wins\n"
        elif loss_streak > 0:
            insights_msg += f"└ Current Streak: ❄️ {loss_streak} losses\n"
        else:
            insights_msg += f"└ Current Streak: None\n"

        insights_msg += "\n<i>Analysis updates every 5 minutes</i>"

        # Apply final sanitization to catch any remaining issues
        insights_msg = sanitize_for_telegram(insights_msg)

        # Debug logging to identify the problematic content
        logger.debug(f"AI Insights message length: {len(insights_msg)} characters")
        if len(insights_msg) > 1192:
            logger.debug(f"Message at byte 1180-1210: {repr(insights_msg[1180:1210])}")
            logger.debug(f"Message at byte 1190: {repr(insights_msg[1190])}")

        # Add navigation buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="ai_insights"),
                InlineKeyboardButton("📊 Dashboard", callback_data="analytics_dashboard")
            ],
            [InlineKeyboardButton("❌ Close", callback_data="delete_message")]
        ])

        if query:
            try:
                await query.edit_message_text(insights_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            except Exception as edit_error:
                logger.warning(f"Could not edit message with HTML: {edit_error}")

                # Save problematic message for debugging
                try:
                    with open('debug_ai_insights_error.txt', 'w') as f:
                        f.write(f"Error: {edit_error}\n")
                        f.write(f"Message length: {len(insights_msg)}\n")
                        f.write(f"Raw message:\n{repr(insights_msg)}\n")
                        f.write(f"Around byte 1190:\n{repr(insights_msg[1180:1210]) if len(insights_msg) > 1192 else 'Too short'}\n")
                    logger.info("Saved problematic AI insights message to debug_ai_insights_error.txt")
                except:
                    pass

                # Try with plain text as fallback
                try:
                    # Strip HTML tags for plain text
                    plain_msg = insights_msg.replace('<b>', '').replace('</b>', '')
                    plain_msg = plain_msg.replace('<i>', '').replace('</i>', '')
                    plain_msg = plain_msg.replace('<code>', '').replace('</code>', '')
                    await query.message.reply_text(plain_msg, parse_mode=None, reply_markup=keyboard)
                    logger.info("Sent AI insights as plain text due to HTML parsing error")
                except Exception as plain_error:
                    logger.error(f"Failed to send as plain text: {plain_error}")
                    await query.message.reply_text("⚠️ Error displaying AI insights. Please try again.", reply_markup=keyboard)
        else:
            await message.reply_text(insights_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error showing AI insights: {e}", exc_info=True)
        error_msg = "⚠️ Unable to generate AI insights. Please try again later."

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="analytics_dashboard")]
        ])

        if query:
            try:
                await query.edit_message_text(error_msg, reply_markup=keyboard)
            except Exception as edit_error:
                logger.warning(f"Could not edit error message, sending new one: {edit_error}")
                await query.message.reply_text(error_msg, reply_markup=keyboard)
        else:
            await message.reply_text(error_msg, reply_markup=keyboard)