#!/usr/bin/env python3
"""
Reusable UI components for the dashboard
"""
import html
import logging
from typing import List, Optional, Tuple
from decimal import Decimal
from dashboard.models import (
    AccountSummary, PnLAnalysis, PositionSummary,
    PerformanceMetrics, MarketStatus, DashboardData
)

logger = logging.getLogger(__name__)
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
        import html
        symbol_str = f" ({status.primary_symbol})" if status.primary_symbol else ""

        # Enhanced display with additional metrics
        result = f"<b>🌍 MARKET STATUS</b>{symbol_str}\n"

        # Core metrics with scores - escape HTML special characters in text fields
        sentiment_text = html.escape(str(status.market_sentiment)) if status.market_sentiment else "Unknown"
        result += f"{status.sentiment_emoji} Sentiment: {sentiment_text} ({status.sentiment_score:.0f}/100)\n"
        
        volatility_text = html.escape(str(status.volatility)) if status.volatility else "Unknown"
        result += f"{status.volatility_emoji} Volatility: {volatility_text}"
        if status.volatility_percentage:
            result += f" ({status.volatility_percentage:.1f}%)"
        result += "\n"
        
        trend_text = html.escape(str(status.trend)) if status.trend else "Unknown"
        result += f"{status.trend_emoji} Trend: {trend_text}\n"
        
        momentum_text = html.escape(str(status.momentum)) if status.momentum else "Unknown"
        result += f"{status.momentum_emoji} Momentum: {momentum_text}\n"

        # Enhanced information if available
        if status.is_enhanced:
            regime_text = html.escape(str(status.market_regime)) if status.market_regime else "Unknown"
            result += f"\n🔍 Regime: {regime_text}\n"

            # Price information if available
            if status.current_price > 0:
                result += f"💰 Price: {status.price_display}\n"

            # NEW: Support and Resistance levels
            if status.support_level and status.resistance_level:
                result += f"📊 S/R: ${status.support_level:,.2f} / ${status.resistance_level:,.2f}\n"

            # NEW: Volume Profile with trend
            if status.volume_profile:
                volume_emoji = "📈" if status.volume_profile == "High" else "📉" if status.volume_profile == "Low" else "📊"
                result += f"{volume_emoji} Volume: {status.volume_profile}"
                
                # Add volume ratio
                if status.volume_ratio:
                    result += f" ({status.volume_ratio:.1f}x avg)"
                
                # Add volume trend indicator
                if hasattr(status, 'volume_trend') and status.volume_trend:
                    if status.volume_trend == "increasing":
                        trend_indicator = " ↗️"
                        if hasattr(status, 'volume_change_pct') and status.volume_change_pct:
                            trend_indicator += f" +{abs(status.volume_change_pct):.0f}%"
                    elif status.volume_trend == "decreasing":
                        trend_indicator = " ↘️"
                        if hasattr(status, 'volume_change_pct') and status.volume_change_pct:
                            trend_indicator += f" -{abs(status.volume_change_pct):.0f}%"
                    else:  # stable
                        trend_indicator = " →"
                    result += trend_indicator
                
                result += "\n"

            # NEW: Market Structure - Multi-timeframe display
            if status.market_structure:
                # Display single structure for backward compatibility
                structure_emoji = "🔺" if status.structure_bias == "Bullish" else "🔻" if status.structure_bias == "Bearish" else "⚖️"
                structure_text = html.escape(str(status.market_structure))
                result += f"{structure_emoji} Structure: {structure_text}\n"
            
            # Display multi-timeframe structures if available
            has_structure = False
            if hasattr(status, 'market_structure_1h') and status.market_structure_1h:
                has_structure = True
                # 1-hour structure
                emoji_1h = "🔺" if "Bullish" in str(status.structure_bias_1h) else "🔻" if "Bearish" in str(status.structure_bias_1h) else "⚖️"
                structure_1h_text = html.escape(str(status.market_structure_1h))
                result += f"{emoji_1h} Structure (1h): {structure_1h_text}\n"
                
            if hasattr(status, 'market_structure_4h') and status.market_structure_4h:
                has_structure = True
                # 4-hour structure
                emoji_4h = "🔺" if "Bullish" in str(status.structure_bias_4h) else "🔻" if "Bearish" in str(status.structure_bias_4h) else "⚖️"
                structure_4h_text = html.escape(str(status.market_structure_4h))
                result += f"{emoji_4h} Structure (4h): {structure_4h_text}\n"
                
            if hasattr(status, 'market_structure_1d') and status.market_structure_1d:
                has_structure = True
                # Daily structure
                emoji_1d = "🔺" if "Bullish" in str(status.structure_bias_1d) else "🔻" if "Bearish" in str(status.structure_bias_1d) else "⚖️"
                structure_1d_text = html.escape(str(status.market_structure_1d))
                result += f"{emoji_1d} Structure (D): {structure_1d_text}\n"
            
            # Add structure explanation and recommendation if we have structure data
            if has_structure:
                explanation = DashboardComponents._get_structure_explanation(status)
                if explanation:
                    result += f"\n{explanation}\n"

            # Funding Rate and Open Interest - REMOVED per user request
            # Commenting out to simplify dashboard display
            # if status.funding_rate is not None:
            #     funding_emoji = "💚" if status.funding_rate < -0.01 else "💛" if abs(status.funding_rate) <= 0.01 else "❤️"
            #     result += f"{funding_emoji} Funding: {status.funding_rate:.3f}%"
            #     if status.funding_bias:
            #         bias_text = html.escape(str(status.funding_bias))
            #         result += f" ({bias_text})"
            #     result += "\n"

            # if status.open_interest_change_24h is not None:
            #     oi_emoji = "📈" if status.open_interest_change_24h > 5 else "📉" if status.open_interest_change_24h < -5 else "➖"
            #     result += f"{oi_emoji} OI 24h: {'+' if status.open_interest_change_24h > 0 else ''}{status.open_interest_change_24h:.1f}%\n"

            # AI Signal and Confidence - REMOVED per user request
            # Commenting out to simplify dashboard display
            # The AI recommendation, risk assessment, and confidence indicators have been removed

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
                        # Don't show "Fresh" timestamp - removed per user request
                        pass
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
    def _get_structure_explanation(status: 'MarketStatus') -> str:
        """Generate brief explanation and trading recommendation based on market structure"""
        
        # Get structure patterns for all timeframes
        structures = []
        if hasattr(status, 'market_structure_1h') and status.market_structure_1h:
            structures.append(('1h', status.market_structure_1h, status.structure_bias_1h))
        if hasattr(status, 'market_structure_4h') and status.market_structure_4h:
            structures.append(('4h', status.market_structure_4h, status.structure_bias_4h))
        if hasattr(status, 'market_structure_1d') and status.market_structure_1d:
            structures.append(('D', status.market_structure_1d, status.structure_bias_1d))
        
        if not structures:
            return ""
        
        # Analyze alignment
        bullish_count = sum(1 for _, _, bias in structures if bias and "Bullish" in str(bias))
        bearish_count = sum(1 for _, _, bias in structures if bias and "Bearish" in str(bias))
        
        # Generate pattern explanations
        explanations = []
        for tf, pattern, bias in structures:
            if pattern == "HH-HL":
                explanations.append(f"{tf}: Uptrend (higher highs/lows)")
            elif pattern == "LH-LL":
                explanations.append(f"{tf}: Downtrend (lower highs/lows)")
            elif pattern == "Expanding":
                explanations.append(f"{tf}: Increasing volatility")
            elif pattern == "Contracting":
                explanations.append(f"{tf}: Consolidating")
            elif pattern == "Consolidation":
                explanations.append(f"{tf}: Sideways")
        
        # Generate recommendation based on confluence
        recommendation = ""
        if bullish_count == len(structures) and bullish_count > 0:
            recommendation = "💡 <b>Strong Buy Signal</b> - All timeframes bullish\n📈 Look for long entries on pullbacks"
        elif bearish_count == len(structures) and bearish_count > 0:
            recommendation = "💡 <b>Strong Sell Signal</b> - All timeframes bearish\n📉 Look for short entries on rallies"
        elif bullish_count > bearish_count:
            recommendation = "💡 <b>Bullish Bias</b> - Favor longs\n⚠️ Watch for support levels"
        elif bearish_count > bullish_count:
            recommendation = "💡 <b>Bearish Bias</b> - Favor shorts\n⚠️ Watch resistance levels"
        else:
            # Check for specific patterns
            has_contracting = any("Contracting" in str(p) for _, p, _ in structures)
            has_expanding = any("Expanding" in str(p) for _, p, _ in structures)
            
            if has_contracting and has_expanding:
                recommendation = "💡 <b>Mixed Signals</b> - Breakout imminent\n⚡ Wait for directional confirmation"
            elif has_expanding:
                recommendation = "💡 <b>High Volatility</b> - Use wider stops\n🎯 Good for range trading"
            elif has_contracting:
                recommendation = "💡 <b>Low Volatility</b> - Breakout setup\n⏳ Prepare for explosive move"
            else:
                recommendation = "💡 <b>Neutral</b> - No clear direction\n⏸️ Wait for better setup"
        
        # Combine explanations
        result = "📖 <i>" + " | ".join(explanations) + "</i>\n"
        result += recommendation
        
        return result
    
    @staticmethod
    def trade_recommendations(status: 'MarketStatus') -> str:
        """Generate timeframe-specific trade recommendations"""
        try:
            from market_analysis.trade_recommendation_engine import trade_recommendation_engine
            
            # Convert MarketStatus to dict for recommendation engine
            status_dict = {
                'sentiment_score': status.sentiment_score if hasattr(status, 'sentiment_score') else 50,
                'momentum_score': getattr(status, 'momentum_score', 0),
                'trend_strength': getattr(status, 'trend_strength', 0),
                'market_structure_1h': getattr(status, 'market_structure_1h', None),
                'market_structure_4h': getattr(status, 'market_structure_4h', None),
                'market_structure_1d': getattr(status, 'market_structure_1d', None),
                'structure_bias_1h': getattr(status, 'structure_bias_1h', None),
                'structure_bias_4h': getattr(status, 'structure_bias_4h', None),
                'structure_bias_1d': getattr(status, 'structure_bias_1d', None),
                'volatility_level': status.volatility if hasattr(status, 'volatility') else 'Normal',
                'volatility_percentage': getattr(status, 'volatility_percentage', 2.0),
                'volume_profile': getattr(status, 'volume_profile', 'Normal'),
                'volume_ratio': getattr(status, 'volume_ratio', 1.0),
                'volume_trend': getattr(status, 'volume_trend', 'stable'),
            }
            
            # Get recommendations
            recommendations = trade_recommendation_engine.get_recommendations(status_dict)
            
            # Format for display
            return trade_recommendation_engine.format_recommendations_for_display(recommendations)
            
        except Exception as e:
            logger.error(f"Error generating trade recommendations: {e}")
            return ""
    
    @staticmethod
    def divider() -> str:
        """Generate a section divider"""
        return "━" * 25 + "\n"