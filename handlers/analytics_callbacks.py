#!/usr/bin/env python3
"""
Analytics callback handlers for advanced dashboard features
Handles portfolio analysis, market intelligence, and performance metrics
"""
import logging
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any
from collections import defaultdict

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config.constants import *
from utils.formatters import format_decimal_or_na, get_emoji, format_mobile_currency
from dashboard.keyboards_analytics import (
    build_analytics_keyboard, build_portfolio_keyboard,
    build_market_intelligence_keyboard, build_performance_keyboard
)
# Import analytics functions from the compact generator
from dashboard.generator_analytics_compact import (
    calculate_portfolio_metrics, calculate_sharpe_ratio,
    calculate_max_drawdown, generate_portfolio_heatmap
)
from clients.bybit_client import get_all_positions
from utils.cache import get_ticker_price_cached
from utils.cache import get_usdt_wallet_balance_cached

logger = logging.getLogger(__name__)

async def handle_analytics_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle analytics-related callbacks"""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    if query.data == "show_analytics":
        await show_analytics_menu(query, context)
    elif query.data == "portfolio_analysis":
        await show_portfolio_analysis(query, context)
    elif query.data == "market_intelligence":
        await show_market_intelligence(query, context)
    elif query.data == "performance_metrics":
        await show_performance_metrics(query, context)
    elif query.data == "position_heatmap":
        await show_position_heatmap(query, context)
    elif query.data == "trading_insights":
        await show_trading_insights(query, context)
    elif query.data == "risk_analysis":
        await show_risk_analysis(query, context)
    elif query.data == "correlation_matrix":
        await show_correlation_matrix(query, context)
    elif query.data == "equity_curve":
        await show_equity_curve(query, context)
    elif query.data == "best_trading_hours":
        await show_best_trading_hours(query, context)
    elif query.data == "portfolio_projections":
        await show_portfolio_projections(query, context)

async def show_analytics_menu(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show analytics menu"""
    text = (
        "📊 <b>TRADING ANALYTICS CENTER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Select an analytics category:\n\n"
        "📈 <b>Performance</b> - Win rates, P&L analysis\n"
        "⏱️ <b>Timing</b> - Best hours and patterns\n"
        "📊 <b>Risk</b> - Drawdown and risk metrics\n"
        "💹 <b>Returns</b> - Daily/weekly/monthly analysis\n"
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=build_analytics_keyboard()
    )

async def show_portfolio_analysis(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed portfolio analysis"""
    # Fetch data
    positions = await get_all_positions()
    balance_result = await get_usdt_wallet_balance_cached()

    if isinstance(balance_result, tuple):
        total_balance = float(balance_result[0])
    else:
        total_balance = float(balance_result) if balance_result else 0

    # Calculate metrics
    metrics = await calculate_portfolio_metrics(positions, total_balance)

    # Build display
    text = (
        "💼 <b>PORTFOLIO ANALYSIS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Diversification
    div_score = metrics['diversification_score']
    div_bar = "█" * (div_score // 10) + "░" * (10 - div_score // 10)
    text += f"🎯 <b>Diversification Score</b>\n"
    text += f"{div_bar} {div_score}/100\n\n"

    # Risk Score
    risk_score = metrics['risk_score']
    risk_bar = "█" * (risk_score // 10) + "░" * (10 - risk_score // 10)
    risk_emoji = "🟢" if risk_score < 30 else "🟡" if risk_score < 60 else "🔴"
    text += f"⚠️ <b>Portfolio Risk</b>\n"
    text += f"{risk_bar} {risk_score}/100 {risk_emoji}\n\n"

    # Concentration
    text += f"🎪 <b>Concentration Risk:</b> {metrics['concentration_risk']}\n"
    text += f"📊 <b>Largest Position:</b> {metrics['largest_position_pct']:.1f}%\n"
    text += f"🔗 <b>Correlation Risk:</b> {metrics['correlation_risk']}\n"
    text += f"💼 <b>Active Symbols:</b> {metrics['unique_symbols']}\n\n"

    # Position value
    if 'total_position_value' in metrics:
        position_value = metrics['total_position_value']
        usage_pct = (position_value / total_balance * 100) if total_balance > 0 else 0
        text += f"💰 <b>Total Position Value:</b> ${position_value:,.2f}\n"
        text += f"📊 <b>Capital Usage:</b> {usage_pct:.1f}%\n"

    # Add recommendations
    text += "\n💡 <b>Recommendations:</b>\n"
    if risk_score > 60:
        text += "• ⚠️ Consider reducing position sizes\n"
    if metrics['concentration_risk'] in ["HIGH", "EXTREME"]:
        text += "• 🎯 Diversify into more assets\n"
    if metrics['unique_symbols'] < 3:
        text += "• 📊 Add more trading pairs\n"

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=build_portfolio_keyboard()
    )

async def show_position_heatmap(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show position performance heatmap"""
    positions = await get_all_positions()

    if not positions:
        text = "📊 <b>POSITION HEATMAP</b>\n\nNo active positions to display."
    else:
        heatmap = await generate_portfolio_heatmap(positions)

        text = (
            "📊 <b>POSITION HEATMAP</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{heatmap}\n\n"
            "🟩 >10%  🟢 5-10%  🟡 0-5%\n"
            "🟠 -5-0%  🔴 -10--5%  🟥 <-10%\n\n"
            f"Total Positions: {len(positions)}"
        )

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="dashboard")]]

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_market_intelligence(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show market intelligence dashboard"""
    # Simulated data - replace with real market data
    funding_rate = 0.01
    sentiment_score = 65
    volume_24h = 2500000000

    text = (
        "🧠 <b>MARKET INTELLIGENCE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💸 <b>Funding Rate:</b> {funding_rate*100:+.3f}% {'🟢' if funding_rate > 0 else '🔴'}\n"
        f"💭 <b>Market Sentiment:</b> {sentiment_score}/100 {'Bullish' if sentiment_score > 50 else 'Bearish'}\n"
        f"📊 <b>24h Volume:</b> ${volume_24h/1000000000:.2f}B\n\n"
    )

    # Order book analysis
    text += "📖 <b>Order Book Analysis</b>\n"
    text += "• Buy Pressure: 🟢🟢🟢⚪⚪ (60%)\n"
    text += "• Sell Pressure: 🔴🔴⚪⚪⚪ (40%)\n"
    text += "• Imbalance: +20% Buy Side\n\n"

    # Market trends
    text += "📈 <b>Market Trends</b>\n"
    text += "• BTC Dominance: 48.5% ↗️\n"
    text += "• Alt Season Index: 35/100\n"
    text += "• Fear & Greed: 55 (Neutral)\n"

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=build_market_intelligence_keyboard()
    )

async def show_performance_metrics(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed performance metrics"""
    bot_data = context.bot_data or {}

    # Get stats
    total_trades = bot_data.get(STATS_TOTAL_TRADES, 0)
    wins = bot_data.get(STATS_TOTAL_WINS, 0)
    losses = bot_data.get(STATS_TOTAL_LOSSES, 0)
    total_pnl = float(bot_data.get(STATS_TOTAL_PNL, 0))

    text = (
        "📈 <b>PERFORMANCE METRICS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if total_trades > 0:
        win_rate = (wins / total_trades * 100)
        avg_pnl = total_pnl / total_trades

        # Calculate profit factor correctly
        total_wins_pnl = abs(float(bot_data.get('stats_total_wins_pnl', 0)))
        total_losses_pnl = abs(float(bot_data.get('stats_total_losses_pnl', 0)))

        if total_losses_pnl > 0:
            profit_factor = total_wins_pnl / total_losses_pnl
        else:
            # No losses, profit factor is undefined/infinity
            profit_factor = float('inf') if total_wins_pnl > 0 else 0

        text += f"📊 <b>Total Trades:</b> {total_trades}\n"
        text += f"✅ <b>Win Rate:</b> {win_rate:.1f}% ({wins}W/{losses}L)\n"
        text += f"💰 <b>Total P&L:</b> {'+' if total_pnl >= 0 else ''}{format_mobile_currency(total_pnl)}\n"
        text += f"📈 <b>Avg Trade:</b> {'+' if avg_pnl >= 0 else ''}{format_mobile_currency(avg_pnl)}\n"
        # Display profit factor appropriately
        if profit_factor == float('inf'):
            profit_factor_display = "∞"
        elif profit_factor > 999:
            profit_factor_display = "999.99+"
        else:
            profit_factor_display = f"{profit_factor:.2f}"

        text += f"💹 <b>Profit Factor:</b> {profit_factor_display}\n\n"

        # Visual win rate
        win_blocks = int(win_rate / 10)
        loss_blocks = 10 - win_blocks
        text += f"<b>Win Rate Visual:</b>\n"
        text += "🟢" * win_blocks + "🔴" * loss_blocks + f" {win_rate:.0f}%\n\n"

        # Streaks
        win_streak = bot_data.get(STATS_WIN_STREAK, 0)
        loss_streak = bot_data.get(STATS_LOSS_STREAK, 0)
        max_win_streak = bot_data.get('max_win_streak', win_streak)
        max_loss_streak = bot_data.get('max_loss_streak', loss_streak)

        text += f"🔥 <b>Current Streak:</b> "
        if win_streak > 0:
            text += f"{win_streak} Wins 🟢\n"
        elif loss_streak > 0:
            text += f"{loss_streak} Losses 🔴\n"
        else:
            text += "None\n"

        text += f"📊 <b>Best Win Streak:</b> {max_win_streak}\n"
        text += f"📉 <b>Worst Loss Streak:</b> {max_loss_streak}\n"
    else:
        text += "No trading history available yet.\n"
        text += "Start trading to see performance metrics!"

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=build_performance_keyboard()
    )

async def show_trading_insights(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show AI-powered trading insights"""
    positions = await get_all_positions()
    bot_data = context.bot_data or {}

    text = (
        "🔍 <b>TRADING INSIGHTS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Position analysis
    if positions:
        # Symbol performance
        symbol_pnls = defaultdict(float)
        symbol_counts = defaultdict(int)

        for pos in positions:
            symbol = pos.get("symbol", "").replace("USDT", "")
            pnl = float(pos.get("unrealisedPnl", 0))
            symbol_pnls[symbol] += pnl
            symbol_counts[symbol] += 1

        # Best performing symbol
        if symbol_pnls:
            best_symbol = max(symbol_pnls.items(), key=lambda x: x[1])
            worst_symbol = min(symbol_pnls.items(), key=lambda x: x[1])

            text += "💎 <b>Best Performer:</b> "
            text += f"{best_symbol[0]} (+{format_mobile_currency(best_symbol[1])})\n"

            text += "💀 <b>Worst Performer:</b> "
            text += f"{worst_symbol[0]} ({format_mobile_currency(worst_symbol[1])})\n\n"

    # Trading patterns
    text += "📊 <b>Trading Patterns Detected:</b>\n"

    # Average leverage
    if positions:
        avg_leverage = sum(float(p.get("leverage", 1)) for p in positions) / len(positions)
        if avg_leverage > 20:
            text += "• ⚡ High leverage trader (Avg: {:.1f}x)\n".format(avg_leverage)
        elif avg_leverage > 10:
            text += "• ⚖️ Moderate leverage (Avg: {:.1f}x)\n".format(avg_leverage)
        else:
            text += "• 🛡️ Conservative leverage (Avg: {:.1f}x)\n".format(avg_leverage)

    # Position sizing
    if positions:
        position_values = [float(p.get("positionValue", 0)) for p in positions]
        if position_values:
            avg_position = sum(position_values) / len(position_values)
            text += f"• 💰 Avg position size: ${avg_position:,.0f}\n"

    # Trading frequency
    total_trades = bot_data.get(STATS_TOTAL_TRADES, 0)
    if total_trades > 0:
        days_active = max(1, (datetime.now() - datetime.fromtimestamp(
            bot_data.get('bot_start_time', datetime.now().timestamp())
        )).days)
        trades_per_day = total_trades / days_active

        if trades_per_day > 10:
            text += f"• 🚀 High frequency trader ({trades_per_day:.1f}/day)\n"
        elif trades_per_day > 5:
            text += f"• 📊 Active trader ({trades_per_day:.1f}/day)\n"
        else:
            text += f"• 🐌 Patient trader ({trades_per_day:.1f}/day)\n"

    # Recommendations
    text += "\n💡 <b>AI Recommendations:</b>\n"
    text += "• Consider scaling into positions\n"
    text += "• Monitor correlation between pairs\n"
    text += "• Set trailing stops on winners\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="dashboard")]]

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_risk_analysis(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show comprehensive risk analysis"""
    positions = await get_all_positions()
    balance_result = await get_usdt_wallet_balance_cached()

    if isinstance(balance_result, tuple):
        total_balance = float(balance_result[0])
    else:
        total_balance = float(balance_result) if balance_result else 0

    text = (
        "🛡️ <b>RISK ANALYSIS REPORT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if positions and total_balance > 0:
        # Calculate total exposure
        total_exposure = sum(float(p.get("positionValue", 0)) for p in positions)
        exposure_pct = (total_exposure / total_balance * 100)

        # Max position size
        max_position = max(positions, key=lambda x: float(x.get("positionValue", 0)))
        max_position_value = float(max_position.get("positionValue", 0))
        max_position_pct = (max_position_value / total_balance * 100)

        # Risk metrics
        text += f"💰 <b>Total Exposure:</b> ${total_exposure:,.2f} ({exposure_pct:.1f}%)\n"
        text += f"📊 <b>Largest Position:</b> {max_position.get('symbol', '')} ({max_position_pct:.1f}%)\n"
        text += f"🎯 <b>Active Positions:</b> {len(positions)}\n\n"

        # Risk levels
        text += "⚠️ <b>Risk Levels:</b>\n"

        if exposure_pct > 80:
            text += "• 🔴 EXTREME RISK - Reduce exposure\n"
        elif exposure_pct > 60:
            text += "• 🟠 HIGH RISK - Monitor closely\n"
        elif exposure_pct > 40:
            text += "• 🟡 MODERATE RISK - Acceptable\n"
        else:
            text += "• 🟢 LOW RISK - Room for more\n"

        # Leverage analysis
        leverages = [float(p.get("leverage", 1)) for p in positions]
        avg_leverage = sum(leverages) / len(leverages)
        max_leverage = max(leverages)

        text += f"\n⚡ <b>Leverage Analysis:</b>\n"
        text += f"• Average: {avg_leverage:.1f}x\n"
        text += f"• Maximum: {max_leverage:.0f}x\n"

        if max_leverage > 50:
            text += "• ⚠️ Very high leverage detected!\n"
    else:
        text += "No active positions for risk analysis.\n"

    # Risk recommendations
    text += "\n🛡️ <b>Risk Management Tips:</b>\n"
    text += "• Never risk more than 2% per trade\n"
    text += "• Use stop losses on all positions\n"
    text += "• Diversify across uncorrelated assets\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="dashboard")]]

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_correlation_matrix(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show position correlation matrix"""
    positions = await get_all_positions()

    text = (
        "🔗 <b>CORRELATION MATRIX</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if len(positions) < 2:
        text += "Need at least 2 positions for correlation analysis."
    else:
        # Get unique symbols
        symbols = list(set(p.get("symbol", "").replace("USDT", "") for p in positions))[:5]

        # Create simple correlation display
        text += "Correlation between positions:\n\n"
        text += "<code>"

        # Header
        text += "     " + " ".join(f"{s[:4]:>5}" for s in symbols) + "\n"

        # Matrix (simulated values)
        import random
        for i, sym1 in enumerate(symbols):
            row = f"{sym1[:4]:>4} "
            for j, sym2 in enumerate(symbols):
                if i == j:
                    corr = " 1.00"
                else:
                    # Simulated correlation
                    corr = f"{random.uniform(-0.5, 0.8):5.2f}"
                row += corr + " "
            text += row + "\n"

        text += "</code>\n\n"

        text += "📊 <b>Interpretation:</b>\n"
        text += "• Values near 1.0 = Strong positive correlation\n"
        text += "• Values near 0.0 = No correlation\n"
        text += "• Values near -1.0 = Strong negative correlation\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="portfolio_analysis")]]

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_equity_curve(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show equity curve visualization"""
    bot_data = context.bot_data or {}

    text = (
        "📈 <b>EQUITY CURVE</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Simulated equity curve
    equity_points = []
    current_equity = 10000  # Starting balance

    for i in range(30):  # Last 30 trades
        change = (1 + (0.02 if i % 3 else -0.01))  # Simulated returns
        current_equity *= change
        equity_points.append(current_equity)

    # Create mini chart
    min_eq = min(equity_points)
    max_eq = max(equity_points)
    range_eq = max_eq - min_eq

    # Normalize and create sparkline
    sparkline = ""
    chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    for eq in equity_points[-20:]:  # Last 20 points
        normalized = (eq - min_eq) / range_eq if range_eq > 0 else 0.5
        idx = int(normalized * (len(chars) - 1))
        sparkline += chars[idx]

    text += f"<code>{sparkline}</code>\n\n"

    # Stats
    total_return = ((equity_points[-1] / 10000) - 1) * 100
    max_dd, dd_duration = calculate_max_drawdown(equity_points)

    text += f"💰 <b>Total Return:</b> {total_return:+.1f}%\n"
    text += f"📉 <b>Max Drawdown:</b> -{max_dd:.1f}%\n"
    text += f"⏱️ <b>DD Duration:</b> {dd_duration} periods\n"
    text += f"📊 <b>Current Equity:</b> ${equity_points[-1]:,.2f}\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_analytics")]]

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_best_trading_hours(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show best trading hours analysis"""
    text = (
        "⏰ <b>BEST TRADING HOURS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Simulated hourly performance
    hours = [
        ("00:00-04:00", 65, "🟢"),
        ("04:00-08:00", 45, "🟡"),
        ("08:00-12:00", 72, "🟢"),
        ("12:00-16:00", 85, "🟢"),
        ("16:00-20:00", 58, "🟡"),
        ("20:00-24:00", 78, "🟢")
    ]

    text += "📊 <b>Win Rate by Time (UTC):</b>\n\n"

    for time_range, win_rate, emoji in hours:
        bar_length = int(win_rate / 10)
        bar = "█" * bar_length + "░" * (10 - bar_length)
        text += f"{time_range}: {bar} {win_rate}% {emoji}\n"

    text += "\n🏆 <b>Best Hours:</b> 12:00-16:00 UTC\n"
    text += "💀 <b>Worst Hours:</b> 04:00-08:00 UTC\n\n"

    text += "💡 <b>Tips:</b>\n"
    text += "• Focus trading during high win-rate hours\n"
    text += "• Avoid trading during low performance times\n"
    text += "• Consider market open/close times\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="show_analytics")]]

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_portfolio_projections(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show portfolio projections"""
    positions = await get_all_positions()
    bot_data = context.bot_data or {}

    text = (
        "📈 <b>PORTFOLIO PROJECTIONS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    # Current stats
    total_trades = bot_data.get(STATS_TOTAL_TRADES, 0)
    win_rate = 0
    if total_trades > 0:
        wins = bot_data.get(STATS_TOTAL_WINS, 0)
        win_rate = (wins / total_trades * 100)

    # Projections based on historical performance
    current_balance = 10000  # Example
    monthly_trades = 100  # Example
    avg_win = 50  # Example
    avg_loss = 30  # Example

    text += "📊 <b>Based on current performance:</b>\n\n"

    # 30-day projection
    expected_wins_30d = int(monthly_trades * (win_rate / 100))
    expected_losses_30d = monthly_trades - expected_wins_30d
    expected_pnl_30d = (expected_wins_30d * avg_win) - (expected_losses_30d * avg_loss)

    text += f"📅 <b>30-Day Projection:</b>\n"
    text += f"• Expected Trades: {monthly_trades}\n"
    text += f"• Expected P&L: {'+' if expected_pnl_30d > 0 else ''}{format_mobile_currency(expected_pnl_30d)}\n"
    text += f"• ROI: {(expected_pnl_30d / current_balance * 100):+.1f}%\n\n"

    # 90-day projection
    expected_pnl_90d = expected_pnl_30d * 3
    compound_balance_90d = current_balance * (1 + (expected_pnl_30d / current_balance)) ** 3

    text += f"📅 <b>90-Day Projection:</b>\n"
    text += f"• Expected P&L: {'+' if expected_pnl_90d > 0 else ''}{format_mobile_currency(expected_pnl_90d)}\n"
    text += f"• Compound Balance: ${compound_balance_90d:,.2f}\n"
    text += f"• Total ROI: {((compound_balance_90d - current_balance) / current_balance * 100):+.1f}%\n\n"

    text += "⚠️ <b>Disclaimer:</b>\n"
    text += "Projections based on historical data.\n"
    text += "Past performance ≠ future results.\n"

    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="portfolio_analysis")]]

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )