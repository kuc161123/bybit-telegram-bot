#!/usr/bin/env python3
"""
Analytics-focused keyboard layouts for the dashboard
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional, List

def build_analytics_dashboard_keyboard(chat_id: int, context: any, 
                                     active_positions: int = 0,
                                     has_monitors: bool = False) -> InlineKeyboardMarkup:
    """Build simplified keyboard for analytics dashboard"""
    
    # First row - Main actions
    first_row = [
        InlineKeyboardButton("📊 New Trade", callback_data="start_conversation"),
        InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard")
    ]
    
    # Second row - Core functions
    second_row = []
    if active_positions > 0:
        second_row.append(InlineKeyboardButton(f"📋 Positions ({active_positions})", callback_data="list_positions"))
    second_row.append(InlineKeyboardButton("📊 Statistics", callback_data="show_statistics"))
    
    # Third row - AI and Analytics
    third_row = [
        InlineKeyboardButton("🎯 Predictive Signals", callback_data="predictive_signals"),
        InlineKeyboardButton("🤖 AI Insights", callback_data="ai_insights")
    ]
    
    # Fourth row - Alerts and Settings
    fourth_row = [
        InlineKeyboardButton("🔔 Alerts", callback_data="alerts_list"),
        InlineKeyboardButton("⚙️ Settings", callback_data="show_settings")
    ]
    
    # Fifth row - Help
    fifth_row = [
        InlineKeyboardButton("❓ Help", callback_data="show_help")
    ]
    
    # Build keyboard
    keyboard = [first_row]
    if second_row:
        keyboard.append(second_row)
    keyboard.append(third_row)
    keyboard.append(fourth_row)
    keyboard.append(fifth_row)
    
    return InlineKeyboardMarkup(keyboard)

def build_performance_analytics_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for performance analytics view"""
    keyboard = [
        [
            InlineKeyboardButton("📈 Daily P&L", callback_data="perf_daily_pnl"),
            InlineKeyboardButton("📊 Weekly", callback_data="perf_weekly_pnl"),
            InlineKeyboardButton("📉 Monthly", callback_data="perf_monthly_pnl")
        ],
        [
            InlineKeyboardButton("🎯 Win Rate", callback_data="perf_win_rate"),
            InlineKeyboardButton("💰 Profit Factor", callback_data="perf_profit_factor"),
            InlineKeyboardButton("📊 Sharpe Ratio", callback_data="perf_sharpe")
        ],
        [
            InlineKeyboardButton("📑 Download Report", callback_data="download_performance_report"),
            InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_risk_analytics_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for risk analytics view"""
    keyboard = [
        [
            InlineKeyboardButton("⚠️ VaR Analysis", callback_data="risk_var"),
            InlineKeyboardButton("📉 Drawdown", callback_data="risk_drawdown"),
            InlineKeyboardButton("🎲 Stress Test", callback_data="risk_stress_test")
        ],
        [
            InlineKeyboardButton("🔗 Correlation", callback_data="risk_correlation"),
            InlineKeyboardButton("📊 Beta Analysis", callback_data="risk_beta"),
            InlineKeyboardButton("💧 Liquidity", callback_data="risk_liquidity")
        ],
        [
            InlineKeyboardButton("🛡️ Set Risk Limits", callback_data="set_risk_limits"),
            InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_time_analysis_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for time-based analysis"""
    keyboard = [
        [
            InlineKeyboardButton("⏰ Hourly", callback_data="time_hourly"),
            InlineKeyboardButton("📅 Daily", callback_data="time_daily"),
            InlineKeyboardButton("📆 Weekly", callback_data="time_weekly")
        ],
        [
            InlineKeyboardButton("🌅 Best Hours", callback_data="time_best_hours"),
            InlineKeyboardButton("📊 Patterns", callback_data="time_patterns"),
            InlineKeyboardButton("🎯 Seasonality", callback_data="time_seasonality")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Alias for compatibility
build_enhanced_dashboard_keyboard = build_analytics_dashboard_keyboard

def build_settings_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for settings menu"""
    keyboard = [
        [
            InlineKeyboardButton("🎯 Trade Settings", callback_data="trade_settings"),
            InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings")
        ],
        [
            InlineKeyboardButton("📊 Display Options", callback_data="display_settings"),
            InlineKeyboardButton("🔗 API Settings", callback_data="api_settings")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_stats_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for statistics menu"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Overall Stats", callback_data="detailed_stats"),
            InlineKeyboardButton("📈 Performance", callback_data="performance_chart")
        ],
        [
            InlineKeyboardButton("🤖 AI Insights", callback_data="ai_insights"),
            InlineKeyboardButton("💭 Market Sentiment", callback_data="sentiment_analysis")
        ],
        [
            InlineKeyboardButton("⚡ Fast Approach", callback_data="fast_approach_stats"),
            InlineKeyboardButton("🛡️ Conservative", callback_data="conservative_approach_stats")
        ],
        [
            InlineKeyboardButton("💾 Export Stats", callback_data="export_stats"),
            InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_position_management_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for position management"""
    keyboard = [
        [
            InlineKeyboardButton("📋 View All", callback_data="list_positions"),
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_positions")
        ],
        [
            InlineKeyboardButton("⚖️ Hedge Mode", callback_data="set_hedge_mode"),
            InlineKeyboardButton("➡️ One Way Mode", callback_data="set_one_way_mode")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_help_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for help menu"""
    keyboard = [
        [
            InlineKeyboardButton("📚 User Guide", callback_data="show_user_guide"),
            InlineKeyboardButton("🎯 Trading Tips", callback_data="show_trading_tips")
        ],
        [
            InlineKeyboardButton("❓ FAQ", callback_data="show_faq"),
            InlineKeyboardButton("💬 Support", callback_data="contact_support")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_analytics_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for analytics menu"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Portfolio Analysis", callback_data="portfolio_analysis"),
            InlineKeyboardButton("🧠 Market Intelligence", callback_data="market_intelligence")
        ],
        [
            InlineKeyboardButton("📈 Performance Metrics", callback_data="performance_metrics"),
            InlineKeyboardButton("🔥 Position Heatmap", callback_data="position_heatmap")
        ],
        [
            InlineKeyboardButton("💡 Trading Insights", callback_data="trading_insights"),
            InlineKeyboardButton("🛡️ Risk Analysis", callback_data="risk_analysis")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_portfolio_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for portfolio analysis"""
    keyboard = [
        [
            InlineKeyboardButton("🔥 Position Heatmap", callback_data="position_heatmap"),
            InlineKeyboardButton("🔗 Correlations", callback_data="correlation_matrix")
        ],
        [
            InlineKeyboardButton("📈 Projections", callback_data="portfolio_projections"),
            InlineKeyboardButton("⚖️ Rebalance", callback_data="suggest_rebalance")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="show_analytics")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_market_intelligence_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for market intelligence"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Volume Analysis", callback_data="volume_analysis"),
            InlineKeyboardButton("💭 Sentiment Score", callback_data="sentiment_analysis")
        ],
        [
            InlineKeyboardButton("📈 Trend Detection", callback_data="trend_analysis"),
            InlineKeyboardButton("⚡ Momentum", callback_data="momentum_analysis")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="show_analytics")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_performance_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for performance metrics"""
    keyboard = [
        [
            InlineKeyboardButton("📈 Equity Curve", callback_data="equity_curve"),
            InlineKeyboardButton("⏰ Best Hours", callback_data="best_trading_hours")
        ],
        [
            InlineKeyboardButton("🎯 Win Streaks", callback_data="win_streaks"),
            InlineKeyboardButton("📊 Trade Analysis", callback_data="trade_analysis")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="show_analytics")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def build_leverage_selection_keyboard(max_leverage: int) -> InlineKeyboardMarkup:
    """Build keyboard for leverage selection"""
    # Create leverage options based on max leverage
    leverage_options = []
    
    # Common leverage options, filtered by max leverage
    common_leverages = [5, 10, 15, 20, 25, 30, 50, 75, 100]
    available_leverages = [lev for lev in common_leverages if lev <= max_leverage]
    
    # Build rows of 3 buttons each
    rows = []
    for i in range(0, len(available_leverages), 3):
        row = []
        for j in range(3):
            if i + j < len(available_leverages):
                leverage = available_leverages[i + j]
                row.append(InlineKeyboardButton(f"{leverage}x", callback_data=f"conv_leverage:{leverage}"))
        if row:
            rows.append(row)
    
    # Add custom input option
    rows.append([InlineKeyboardButton("✏️ Custom Leverage", callback_data="conv_leverage:custom")])
    
    # Add back button - using state 4 which is LEVERAGE state
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="conv_back:4")])
    
    return InlineKeyboardMarkup(rows)