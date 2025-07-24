#!/usr/bin/env python3
"""
Analytics-focused keyboard layouts - Legacy compatibility wrapper
This file now redirects to the new V2 keyboards
"""
from telegram import InlineKeyboardMarkup
from typing import Optional
from .keyboards_v2 import DashboardKeyboards

# Legacy wrapper functions that redirect to V2
def build_analytics_dashboard_keyboard(chat_id: int, context: any,
                                     active_positions: int = 0,
                                     has_monitors: bool = False) -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    has_mirror = False
    try:
        from execution.mirror_trader import is_mirror_trading_enabled
        has_mirror = is_mirror_trading_enabled()
    except:
        pass

    return DashboardKeyboards.main_dashboard(active_positions > 0, has_mirror)

def build_enhanced_dashboard_keyboard(chat_id: int, context: any,
                                    active_positions: int = 0,
                                    has_monitors: bool = False) -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return build_analytics_dashboard_keyboard(chat_id, context, active_positions, has_monitors)

def build_performance_analytics_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.analytics_menu()

def build_risk_analytics_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.analytics_menu()

def build_time_analysis_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.analytics_menu()

def build_settings_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.settings_menu()

def build_stats_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.statistics_menu()

def build_position_management_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.position_details()

def build_help_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.help_menu()

def build_analytics_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.analytics_menu()

def build_portfolio_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.analytics_menu()

def build_market_intelligence_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.analytics_menu()

def build_performance_keyboard() -> InlineKeyboardMarkup:
    """Legacy wrapper - redirects to V2 keyboards"""
    return DashboardKeyboards.analytics_menu()

def build_leverage_selection_keyboard(max_leverage: int) -> InlineKeyboardMarkup:
    """Build keyboard for leverage selection - still used by conversation flow"""
    from telegram import InlineKeyboardButton

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