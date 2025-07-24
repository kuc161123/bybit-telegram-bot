#!/usr/bin/env python3
"""
Force fix AI insights by creating a plain text version
"""
import logging
from shared.state import get_application

logger = logging.getLogger(__name__)

try:
    # Get the running application instance
    app = get_application()
    
    if not app:
        print("❌ Bot not running or application not found")
        exit(1)
    
    # Import required modules
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import ContextTypes, CallbackQueryHandler
    from config.constants import *
    from execution.ai_market_analysis import get_ai_market_insights
    from utils.formatters import format_number
    from clients.bybit_helpers import get_all_positions
    import re
    
    async def ai_insights_plain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show AI insights in plain text to avoid HTML parsing errors"""
        try:
            query = update.callback_query
            if query:
                await query.answer()
            
            chat_id = query.message.chat_id
            user_data = context.user_data
            stats_data = user_data.get('stats', {})
            
            # Get positions
            positions = await get_all_positions(chat_id)
            if not positions:
                msg = "📊 AI MARKET INSIGHTS\n\nNo active positions to analyze.\nOpen some positions to see AI-powered insights!"
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="analytics_dashboard")]])
                await query.edit_message_text(msg, reply_markup=keyboard)
                return
            
            # Build plain text message
            msg = "🤖 AI MARKET INSIGHTS\n"
            msg += "━" * 25 + "\n\n"
            
            # Analyze top 3 positions
            sorted_positions = sorted(positions, key=lambda p: abs(float(p.get('size', 0))), reverse=True)[:3]
            
            for i, position in enumerate(sorted_positions):
                symbol = position['symbol']
                pnl = float(position.get('unrealisedPnl', 0))
                entry_price = float(position.get('avgPrice', 0))
                current_price = float(position.get('markPrice', entry_price))
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                
                try:
                    ai_analysis = await get_ai_market_insights(symbol, stats_data)
                    
                    # Format position
                    msg += f"{i+1}. {symbol} "
                    if pnl >= 0:
                        msg += f"+${format_number(pnl)} (+{pnl_pct:.1f}%)\n"
                    else:
                        msg += f"-${format_number(abs(pnl))} ({pnl_pct:.1f}%)\n"
                    
                    # Analysis details
                    outlook = ai_analysis.get('market_outlook', 'NEUTRAL')
                    signal = ai_analysis.get('signal_strength', 'WEAK')
                    confidence = ai_analysis.get('confidence', 50)
                    
                    outlook_emoji = "🟢" if outlook == "BULLISH" else "🔴" if outlook == "BEARISH" else "🟡"
                    msg += f"├ {outlook_emoji} Outlook: {outlook} ({signal} signal)\n"
                    msg += f"├ 🎯 Confidence: {confidence}%\n"
                    
                    # Prediction - remove problematic characters
                    prediction = ai_analysis.get('short_term_prediction', 'No prediction')
                    prediction = re.sub(r'[<>]', '', prediction)  # Remove < and >
                    msg += f"├ 📈 Prediction: {prediction}\n"
                    
                    # Risks
                    risks = ai_analysis.get('key_risks', [])
                    if risks:
                        risk = re.sub(r'[<>]', '', risks[0])
                        msg += f"├ ⚠️ Risk: {risk}\n"
                    
                    # Recommendations
                    recs = ai_analysis.get('recommended_actions', [])
                    if recs:
                        rec = re.sub(r'[<>]', '', recs[0])
                        msg += f"└ 💡 Action: {rec}\n"
                    
                    msg += "\n"
                    
                except Exception as e:
                    logger.error(f"Error analyzing {symbol}: {e}")
                    msg += "└ ⚠️ Analysis unavailable\n\n"
            
            # Performance summary
            total_trades = stats_data.get(STATS_TOTAL_TRADES, 0)
            wins = stats_data.get(STATS_TOTAL_WINS, 0)
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            total_pnl = float(stats_data.get(STATS_TOTAL_PNL, 0))
            
            msg += "━" * 25 + "\n"
            msg += "📊 PERFORMANCE CONTEXT\n"
            msg += f"├ Win Rate: {win_rate:.1f}% ({wins}W/{total_trades - wins}L)\n"
            msg += f"├ Total P&L: ${format_number(total_pnl)}\n"
            
            # Profit factor
            total_wins_pnl = float(stats_data.get('stats_total_wins_pnl', 0))
            total_losses_pnl = abs(float(stats_data.get('stats_total_losses_pnl', 0)))
            if total_losses_pnl > 0:
                pf = total_wins_pnl / total_losses_pnl
                msg += f"├ Profit Factor: {pf:.2f}\n"
            
            # Streak
            win_streak = stats_data.get(STATS_WIN_STREAK, 0)
            loss_streak = stats_data.get(STATS_LOSS_STREAK, 0)
            if win_streak > 0:
                msg += f"└ Streak: 🔥 {win_streak} wins\n"
            elif loss_streak > 0:
                msg += f"└ Streak: ❄️ {loss_streak} losses\n"
            else:
                msg += "└ Streak: None\n"
            
            msg += "\nAnalysis updates every 5 minutes"
            
            # Send as plain text
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="ai_insights"),
                    InlineKeyboardButton("📊 Dashboard", callback_data="analytics_dashboard")
                ],
                [InlineKeyboardButton("❌ Close", callback_data="delete_message")]
            ])
            
            await query.edit_message_text(msg, reply_markup=keyboard, parse_mode=None)
            
        except Exception as e:
            logger.error(f"Error in plain AI insights: {e}")
            await query.edit_message_text(
                "⚠️ Unable to generate AI insights. Please try again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="analytics_dashboard")]])
            )
    
    # Find and update the callback handler
    handlers = app.handlers
    updated = False
    
    for group in handlers:
        for handler in handlers[group]:
            if isinstance(handler, CallbackQueryHandler):
                if hasattr(handler, 'callback') and handler.callback.__name__ == 'show_ai_insights':
                    # Update the callback
                    handler.callback = ai_insights_plain
                    updated = True
                    logger.info("Updated AI insights handler to plain text version")
                    break
    
    if updated:
        print("✅ Successfully updated AI insights to plain text version!")
        print("📌 The fix is now active - try the AI insights button again")
        print("📌 This version:")
        print("   - Uses plain text (no HTML)")
        print("   - Removes all < and > characters")
        print("   - Should work without any parsing errors")
    else:
        # Try to add a new handler
        from handlers.ai_insights_handler import show_ai_insights
        app.add_handler(CallbackQueryHandler(ai_insights_plain, pattern="^ai_insights$"))
        print("✅ Added new plain text AI insights handler!")
        print("📌 The original handler may still be active, but the new one should intercept")
        
except Exception as e:
    print(f"❌ Error applying fix: {e}")
    print("The bot may need to be restarted to apply this fix")