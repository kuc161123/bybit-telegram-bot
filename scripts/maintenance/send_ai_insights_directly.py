#!/usr/bin/env python3
"""
Send AI insights directly to avoid the HTML parsing issue
"""
import asyncio
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config.settings import TELEGRAM_TOKEN
from clients.bybit_client import bybit_client
from execution.ai_market_analysis import get_ai_market_insights
from utils.formatters import format_number
from config.constants import *
import pickle
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_clean_ai_insights(chat_id: int = 5634913742):
    """Send AI insights with proper escaping"""
    bot = Bot(token=TELEGRAM_TOKEN)
    
    try:
        # Load user data from pickle
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        user_data = data.get('user_data', {}).get(chat_id, {})
        stats_data = user_data.get('stats', {})
        
        # Get positions
        try:
            response = bybit_client.get_positions(category="linear", settleCoin="USDT")
            positions = response.get('result', {}).get('list', [])
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            positions = []
        
        if not positions:
            msg = "📊 **AI MARKET INSIGHTS**\n\nNo active positions to analyze.\nOpen some positions to see AI-powered insights!"
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")]])
            await bot.send_message(chat_id, msg, reply_markup=keyboard, parse_mode='Markdown')
            return
        
        # Build message
        msg = "🤖 **AI MARKET INSIGHTS**\n"
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
                
                # Position header
                msg += f"**{i+1}. {symbol}** "
                if pnl >= 0:
                    msg += f"`+${format_number(pnl)} (+{pnl_pct:.1f}%)`\n"
                else:
                    msg += f"`-${format_number(abs(pnl))} ({pnl_pct:.1f}%)`\n"
                
                # Analysis
                outlook = ai_analysis.get('market_outlook', 'NEUTRAL')
                signal = ai_analysis.get('signal_strength', 'WEAK')
                confidence = ai_analysis.get('confidence', 50)
                
                outlook_emoji = "🟢" if outlook == "BULLISH" else "🔴" if outlook == "BEARISH" else "🟡"
                msg += f"├ {outlook_emoji} Outlook: **{outlook}** ({signal} signal)\n"
                msg += f"├ 🎯 Confidence: **{confidence}%**\n"
                
                # Fix predictions with < and >
                prediction = ai_analysis.get('short_term_prediction', 'No prediction')
                prediction = prediction.replace('>', ' greater than')
                prediction = prediction.replace('<', ' less than')
                msg += f"├ 📈 Prediction: {prediction}\n"
                
                # Fix risks
                risks = ai_analysis.get('key_risks', [])
                if risks:
                    risk = risks[0].replace('>', ' greater than').replace('<', ' less than')
                    msg += f"├ ⚠️ Risk: {risk}\n"
                
                # Fix recommendations
                recs = ai_analysis.get('recommended_actions', [])
                if recs:
                    rec = recs[0].replace('>', ' greater than').replace('<', ' less than')
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
        msg += "📊 **PERFORMANCE CONTEXT**\n"
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
        
        msg += "\n_Analysis updates every 5 minutes_"
        
        # Send with Markdown formatting
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="ai_insights"),
                InlineKeyboardButton("📊 Dashboard", callback_data="analytics_dashboard")
            ],
            [InlineKeyboardButton("❌ Close", callback_data="delete_message")]
        ])
        
        await bot.send_message(chat_id, msg, reply_markup=keyboard, parse_mode='Markdown')
        
        print("✅ Successfully sent AI insights with proper formatting!")
        print("📌 Key fixes applied:")
        print("   - Replaced < with 'less than'")
        print("   - Replaced > with 'greater than'")
        print("   - Using Markdown instead of HTML")
        
    except Exception as e:
        logger.error(f"Error sending AI insights: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(send_clean_ai_insights())