#!/usr/bin/env python3
"""
Analytics-focused keyboard layouts for the dashboard
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional, List

def build_analytics_dashboard_keyboard(chat_id: int, context: any, 
                                     active_positions: int = 0,
                                     has_monitors: bool = False) -> InlineKeyboardMarkup:
    """Build keyboard for analytics dashboard with advanced features"""
    
    # First row - Main actions
    first_row = [
        InlineKeyboardButton("📊 Trade Setup", callback_data="start_conversation"),
        InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard")
    ]
    
    # Second row - Analytics views
    second_row = [
        InlineKeyboardButton("📈 Performance", callback_data="view_performance_analytics"),
        InlineKeyboardButton("🎯 Risk Metrics", callback_data="view_risk_analytics"),
        InlineKeyboardButton("📊 Statistics", callback_data="show_statistics")
    ]
    
    # Third row - Advanced analytics
    third_row = [
        InlineKeyboardButton("🕐 Time Analysis", callback_data="view_time_analysis"),
        InlineKeyboardButton("🔗 Correlations", callback_data="view_correlations"),
        InlineKeyboardButton("🎲 Predictions", callback_data="view_predictions")
    ]
    
    # Fourth row - Reports and insights
    fourth_row = [
        InlineKeyboardButton("📑 Full Report", callback_data="generate_full_report"),
        InlineKeyboardButton("💡 AI Insights", callback_data="view_ai_insights"),
        InlineKeyboardButton("📊 Export Data", callback_data="export_analytics_data")
    ]
    
    # Fifth row - Position management (if has positions)
    if active_positions > 0:
        fifth_row = [
            InlineKeyboardButton(f"📋 Positions ({active_positions})", callback_data="list_positions"),
            InlineKeyboardButton("🛡️ Risk Check", callback_data="check_risk_status"),
            InlineKeyboardButton("⚖️ Rebalance", callback_data="suggest_rebalance")
        ]
    else:
        fifth_row = []
    
    # Sixth row - Settings and modes
    sixth_row = [
        InlineKeyboardButton("⚙️ Settings", callback_data="show_settings"),
        InlineKeyboardButton("🎯 Position Mode", callback_data="check_position_mode"),
        InlineKeyboardButton("❓ Help", callback_data="show_help")
    ]
    
    # Build keyboard
    keyboard = [first_row, second_row, third_row, fourth_row]
    if fifth_row:
        keyboard.append(fifth_row)
    keyboard.append(sixth_row)
    
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