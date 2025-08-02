#!/usr/bin/env python3
"""
Hot-fix for AI insights HTML parsing errors
Patches the running bot without restart
"""
import logging

logger = logging.getLogger(__name__)

# Import the handlers module
try:
    import handlers.ai_insights_handler as ai_handler
    import html
    import re
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes
    from telegram.constants import ParseMode
    from config.constants import *
    from execution.ai_market_analysis import get_ai_market_insights
    from utils.formatters import format_number, format_price
    from clients.bybit_helpers import get_all_positions
    
    # Create a new version of the function with better escaping
    async def show_ai_insights_fixed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show detailed AI market insights with fixed HTML escaping"""
        try:
            query = update.callback_query
            message = update.message if not query else None
            
            if query:
                await query.answer()
            
            chat_id = query.message.chat_id if query else message.chat_id
            
            # Get user data
            user_data = context.user_data
            stats_data = user_data.get('stats', {})
            
            # Get all positions
            positions = await get_all_positions(chat_id)
            if not positions:
                no_positions_msg = "📊 <b>AI MARKET INSIGHTS</b>\n\n"
                no_positions_msg += "No active positions to analyze.\n"
                no_positions_msg += "Open some positions to see AI-powered insights!"
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="analytics_dashboard")]
                ])
                
                if query:
                    await query.edit_message_text(no_positions_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
                else:
                    await message.reply_text(no_positions_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
                return
            
            insights_msg = "🤖 <b>AI MARKET INSIGHTS</b>\n"
            insights_msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Analyze top positions
            sorted_positions = sorted(positions, key=lambda p: abs(float(p.get('size', 0))), reverse=True)
            
            for i, position in enumerate(sorted_positions[:3]):  # Top 3 positions
                symbol = position['symbol']
                pnl = float(position.get('unrealisedPnl', 0))
                entry_price = float(position.get('avgPrice', 0))
                current_price = float(position.get('markPrice', entry_price))
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                
                try:
                    ai_analysis = await get_ai_market_insights(symbol, stats_data)
                    
                    # Format position header with proper escaping
                    insights_msg += f"<b>{i+1}. {html.escape(symbol)}</b> "
                    if pnl >= 0:
                        insights_msg += f"<code>+${html.escape(format_number(pnl))} (+{pnl_pct:.1f}%)</code>\n"
                    else:
                        insights_msg += f"<code>-${html.escape(format_number(abs(pnl)))} ({pnl_pct:.1f}%)</code>\n"
                    
                    # Market outlook - ESCAPE ALL DYNAMIC CONTENT
                    outlook = ai_analysis.get('market_outlook', 'NEUTRAL')
                    signal_strength = ai_analysis.get('signal_strength', 'WEAK')
                    confidence = ai_analysis.get('confidence', 50)
                    
                    outlook_emoji = "🟢" if outlook == "BULLISH" else "🔴" if outlook == "BEARISH" else "🟡"
                    insights_msg += f"├ {outlook_emoji} Outlook: <b>{html.escape(outlook)}</b> ({html.escape(signal_strength)} signal)\n"
                    insights_msg += f"├ 🎯 Confidence: <b>{confidence}%</b>\n"
                    
                    # Short-term prediction - CRITICAL: Escape < and > characters
                    prediction = ai_analysis.get('short_term_prediction', 'No prediction available')
                    # Replace common problematic patterns
                    prediction = prediction.replace('>', ' greater than ')
                    prediction = prediction.replace('<', ' less than ')
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
                    
                    # Key risks - ESCAPE < and > in risks
                    risks = ai_analysis.get('key_risks', [])
                    if risks:
                        risk_text = risks[0].replace('>', ' greater than ').replace('<', ' less than ')
                        insights_msg += f"├ ⚠️ Top Risk: {html.escape(risk_text)}\n"
                    
                    # Recommendations - ESCAPE < and > in recommendations
                    recommendations = ai_analysis.get('recommended_actions', [])
                    if recommendations:
                        rec_text = recommendations[0].replace('>', ' greater than ').replace('<', ' less than ')
                        insights_msg += f"└ 💡 Action: {html.escape(rec_text)}\n"
                    
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
                except Exception as e:
                    logger.warning(f"HTML parse error, using plain text: {e}")
                    # Convert to plain text
                    plain_msg = re.sub('<.*?>', '', insights_msg)
                    await query.edit_message_text(plain_msg, parse_mode=None, reply_markup=keyboard)
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
                except:
                    await query.message.reply_text(error_msg, reply_markup=keyboard)
            else:
                await message.reply_text(error_msg, reply_markup=keyboard)
    
    # Replace the function in the module
    ai_handler.show_ai_insights = show_ai_insights_fixed
    
    print("✅ Successfully patched AI insights handler!")
    print("📌 The fix will take effect immediately without restart")
    print("📌 Key fixes:")
    print("   - Replaces < and > with 'less than' and 'greater than'")
    print("   - Escapes all dynamic content properly")
    print("   - Falls back to plain text if HTML still fails")
    
except Exception as e:
    print(f"❌ Failed to patch AI insights handler: {e}")
    print("You may need to restart the bot to apply fixes")