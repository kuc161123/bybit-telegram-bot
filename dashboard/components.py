#!/usr/bin/env python3
"""
Reusable UI components for the dashboard
"""
import html
from typing import List, Optional, Tuple
from decimal import Decimal
from dashboard.models import (
    AccountSummary, PnLAnalysis, PositionSummary,
    PerformanceMetrics, MarketStatus, DashboardData
)
from utils.formatters import format_number


class DashboardComponents:
    """Collection of reusable dashboard UI components"""

    @staticmethod
    def header(timestamp: str, auto_refresh: bool = False) -> str:
        """Generate dashboard header with status"""
        status = "🔄" if auto_refresh else "📊"
        return f"<b>📈 TRADING DASHBOARD</b>\n{timestamp} • {status} Live\n"

    @staticmethod
    def quick_commands() -> str:
        """Generate quick command pills"""
        return (
            "📍 Quick Commands:\n"
            "<code>/trade</code> <code>/start</code> "
            "<code>/help</code> <code>/settings</code>\n"
        )

    @staticmethod
    def account_comparison(main: AccountSummary, mirror: Optional[AccountSummary] = None) -> str:
        """Generate side-by-side account comparison"""
        if mirror:
            return f"""<b>💼 ACCOUNT OVERVIEW</b>

<b>📍 MAIN ACCOUNT</b>
Balance: <b>${format_number(main.balance)}</b>
Available: ${format_number(main.available_balance)}
P&L: ${format_number(main.total_pnl)}
Positions: {main.position_count}
Health: {main.health_emoji} {main.health_score:.0f}%

<b>🪞 MIRROR ACCOUNT</b>
Balance: <b>${format_number(mirror.balance)}</b>
Available: ${format_number(mirror.available_balance)}
P&L: ${format_number(mirror.total_pnl)}
Positions: {mirror.position_count}
Health: {mirror.health_emoji} {mirror.health_score:.0f}%"""
        else:
            # Single account display
            return f"""<b>💼 ACCOUNT OVERVIEW</b>
💰 Balance: <b>${format_number(main.balance)}</b>
🔓 Available: ${format_number(main.available_balance)}
📊 In Use: ${format_number(main.margin_used)} ({main.balance_used_pct:.1f}%)
{main.health_emoji} Health: {main.health_score:.0f}% ({main.health_status})
💎 P&L: ${format_number(main.total_pnl)}"""

    @staticmethod
    def pnl_analysis_table(main: PnLAnalysis, mirror: Optional[PnLAnalysis] = None) -> str:
        """Generate P&L analysis table"""
        if mirror:
            return f"""<b>💡 POTENTIAL P&L ANALYSIS</b>

<b>📍 MAIN</b> | <b>🪞 MIRROR</b>
🎯 TP1 (100%): +${format_number(main.tp_profit)} | +${format_number(mirror.tp_profit)}
🛑 All SL: -${format_number(main.all_sl_loss)} | -${format_number(mirror.all_sl_loss)}
📊 R:R: 1:{main.risk_reward_ratio:.1f} | 1:{mirror.risk_reward_ratio:.1f}"""
        else:
            # Single account P&L for TP1-only strategy
            return f"""<b>💡 POTENTIAL P&L ANALYSIS</b>
🎯 TP1 (100%): <b>+${format_number(main.tp_profit)}</b>
🛑 If All SL Hit: -${format_number(main.all_sl_loss)}
📊 Risk:Reward = <b>1:{main.risk_reward_ratio:.1f}</b>"""

    @staticmethod
    def positions_summary(positions: List[PositionSummary], limit: int = 5) -> str:
        """Generate positions summary table - DISABLED for cleaner dashboard"""
        # Return empty string to remove from dashboard
        return ""

    @staticmethod
    def performance_summary(metrics: PerformanceMetrics, expanded: bool = False) -> str:
        """Generate performance metrics summary"""
        # Check if we have any meaningful data
        has_trades = metrics.total_trades > 0
        
        if not has_trades:
            if expanded:
                return f"""<b>📊 PERFORMANCE METRICS</b>
🔄 <i>Building Trading History...</i>
📈 Trades Completed: 0
📋 Statistics will appear after first position closes
💡 <i>Start trading to see performance metrics</i>"""
            else:
                # Compact view for no data
                return f"""<b>📊 PERFORMANCE</b>
🔄 <i>Building History</i> • 📈 <i>0 Trades Completed</i>"""
        
        if expanded:
            return f"""<b>📊 PERFORMANCE METRICS</b>
📈 Win Rate: {metrics.win_rate:.1f}% ({metrics.wins}W/{metrics.losses}L)
💰 Profit Factor: {metrics.profit_factor_display}
📊 Sharpe: {metrics.sharpe_ratio:.2f} | Sortino: {metrics.sortino_ratio:.2f}
📉 Max DD: {metrics.max_drawdown:.1f}% | Recovery: {metrics.recovery_factor:.1f}x
🎯 Avg Trade: ${format_number(metrics.avg_trade)}
✅ Best: +${format_number(metrics.best_trade)}
❌ Worst: -${format_number(abs(metrics.worst_trade))}
🔥 Streak: {metrics.streak_display}"""
        else:
            # Compact view with data
            return f"""<b>📊 PERFORMANCE</b>
Win Rate: {metrics.win_rate:.1f}% • PF: {metrics.profit_factor_display}
Sharpe: {metrics.sharpe_ratio:.2f} • DD: {metrics.max_drawdown:.1f}%"""

    @staticmethod
    def market_status(status: MarketStatus) -> str:
        """Generate enhanced market status section"""
        symbol_str = f" ({status.primary_symbol})" if status.primary_symbol else ""

        # Enhanced display with additional metrics
        result = f"<b>🌍 MARKET STATUS</b>{symbol_str}\n"

        # Core metrics with scores
        result += f"{status.sentiment_emoji} Sentiment: {status.market_sentiment} ({status.sentiment_score:.0f}/100)\n"
        result += f"{status.volatility_emoji} Volatility: {status.volatility}"
        if status.volatility_percentage:
            result += f" ({status.volatility_percentage:.1f}%)"
        result += "\n"
        result += f"{status.trend_emoji} Trend: {status.trend}\n"
        result += f"{status.momentum_emoji} Momentum: {status.momentum}\n"

        # Enhanced information if available
        if status.is_enhanced:
            result += f"\n🔍 Regime: {status.market_regime}\n"

            # Price information if available
            if status.current_price > 0:
                result += f"💰 Price: {status.price_display}\n"

            # NEW: Support and Resistance levels
            if status.support_level and status.resistance_level:
                result += f"📊 S/R: ${status.support_level:,.2f} / ${status.resistance_level:,.2f}\n"

            # NEW: Volume Profile
            if status.volume_profile:
                volume_emoji = "📈" if status.volume_profile == "High" else "📉" if status.volume_profile == "Low" else "📊"
                result += f"{volume_emoji} Volume: {status.volume_profile}"
                if status.volume_ratio:
                    result += f" ({status.volume_ratio:.1f}x avg)"
                result += "\n"

            # NEW: Market Structure
            if status.market_structure:
                structure_emoji = "🔺" if status.structure_bias == "Bullish" else "🔻" if status.structure_bias == "Bearish" else "⚖️"
                result += f"{structure_emoji} Structure: {status.market_structure}\n"

            # NEW: Funding Rate (for perpetuals)
            if status.funding_rate is not None:
                funding_emoji = "💚" if status.funding_rate < -0.01 else "💛" if abs(status.funding_rate) <= 0.01 else "❤️"
                result += f"{funding_emoji} Funding: {status.funding_rate:.3f}%"
                if status.funding_bias:
                    result += f" ({status.funding_bias})"
                result += "\n"

            # NEW: Open Interest Change
            if status.open_interest_change_24h is not None:
                oi_emoji = "📈" if status.open_interest_change_24h > 5 else "📉" if status.open_interest_change_24h < -5 else "➖"
                result += f"{oi_emoji} OI 24h: {'+' if status.open_interest_change_24h > 0 else ''}{status.open_interest_change_24h:.1f}%\n"

            # NEW: AI Recommendation (GPT-4 Enhanced)
            if status.ai_recommendation:
                rec_emoji = "🟢" if status.ai_recommendation == "BUY" else "🔴" if status.ai_recommendation == "SELL" else "🟡"
                result += f"\n{rec_emoji} AI: {status.ai_recommendation}"
                if status.ai_risk_assessment:
                    risk_emoji = "⚠️" if status.ai_risk_assessment == "HIGH" else "⚡" if status.ai_risk_assessment == "MEDIUM" else "✅"
                    result += f" {risk_emoji} {status.ai_risk_assessment} Risk"
                
                # OPTIMIZED: Concise AI reasoning - extract key pattern and timeframe only
                if status.ai_reasoning:
                    reasoning = status.ai_reasoning
                    
                    # Extract key pattern (first mentioned pattern)
                    key_pattern = None
                    patterns = ["Shooting Star", "Doji", "Hammer", "Hanging Man", "Engulfing", "MACD", "RSI", "Bollinger", "Support", "Resistance"]
                    for pattern in patterns:
                        if pattern in reasoning:
                            key_pattern = pattern
                            break
                    
                    # Extract timeframe (look for "1-2 weeks", "few days", etc.)
                    timeframe = None
                    import re
                    timeframe_match = re.search(r'(\d+[-‒–—]\d+\s+(?:days?|weeks?|months?)|\d+\s+(?:days?|weeks?|months?)|few\s+(?:days?|weeks?))', reasoning.lower())
                    if timeframe_match:
                        timeframe = timeframe_match.group(1).title()
                    
                    # Concise summary
                    summary_parts = []
                    if key_pattern:
                        summary_parts.append(f"{key_pattern}")
                    if timeframe:
                        summary_parts.append(f"{timeframe}")
                    
                    if summary_parts:
                        result += f"\n💡 {' • '.join(summary_parts)}"

            # Confidence indicator (enhanced if AI boosted)
            conf_label = "AI Confidence" if status.ai_confidence and status.ai_confidence > status.confidence else "Confidence"
            conf_value = status.ai_confidence if status.ai_confidence else status.confidence
            result += f"\n{status.confidence_emoji} {conf_label}: {conf_value:.0f}%"

            # Update timestamp with data freshness indicator
            if status.last_updated:
                timestamp_str = status.last_updated.strftime('%H:%M:%S')
                
                # Enhanced real-time data detection
                try:
                    import time
                    from datetime import datetime, timedelta
                    
                    # Check if data is very fresh (less than 30 seconds old)
                    data_age = datetime.now() - status.last_updated
                    is_fresh = data_age.total_seconds() < 30
                    
                    # Try to get real-time data for confirmation
                    try:
                        from market_analysis.realtime_data_stream import get_realtime_price
                        realtime_price = get_realtime_price(status.primary_symbol or "BTCUSDT")
                        has_realtime = realtime_price and realtime_price > 0
                    except:
                        has_realtime = False
                    
                    # Smart display based on data freshness and real-time availability
                    if is_fresh and has_realtime:
                        result += f" • 🟢 Live {timestamp_str}"
                    elif is_fresh:
                        result += f" • 🟡 Fresh {timestamp_str}"
                    else:
                        result += f" • 🔵 API {timestamp_str}"
                        
                except Exception:
                    result += f" • 📊 {timestamp_str}"
        else:
            # Fallback mode indicator
            result += f"\n📱 Basic Mode"

        return result

    @staticmethod
    def monitor_status(monitors: dict, has_mirror: bool = False) -> str:
        """Generate monitor status section"""
        total = monitors.get('total', 0)

        result = f"<b>⚡ ACTIVE MONITORS</b> ({total} Total)\n"

        # Show by account
        main_count = monitors.get('main', 0)
        mirror_count = monitors.get('mirror', 0)

        if main_count > 0:
            result += f"📍 Main Account: {main_count} monitors\n"

        if has_mirror and mirror_count > 0:
            result += f"🪞 Mirror Account: {mirror_count} monitors\n"

        # Optionally show approach breakdown if needed
        # fast = monitors.get('fast', 0)
        # conservative = monitors.get('conservative', 0)
        # if fast > 0 or conservative > 0:
        #     result += f"\n"
        #     if fast > 0:
        #         result += f"⚡ Fast: {fast} | "
        #     if conservative > 0:
        #         result += f"🛡️ Conservative: {conservative}"

        return result.rstrip('\n')

    @staticmethod
    def quick_actions_grid() -> str:
        """Generate quick actions grid - DISABLED for cleaner dashboard"""
        # Return empty string to remove from dashboard
        return ""

    @staticmethod
    def divider() -> str:
        """Generate a section divider"""
        return "━" * 25 + "\n"