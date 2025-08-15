#!/usr/bin/env python3
"""
Enhanced keyboard layouts for the new dashboard design
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional, List


class DashboardKeyboards:
    """Collection of dashboard keyboard layouts"""

    @staticmethod
    def main_dashboard(has_positions: bool = False, has_mirror: bool = False) -> InlineKeyboardMarkup:
        """Simplified main dashboard keyboard with essential actions only"""
        keyboard = []

        # First row - Primary actions
        first_row = [
            InlineKeyboardButton("📊 New Trade", callback_data="start_conversation"),
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard")
        ]
        keyboard.append(first_row)

        # Second row - Essential monitoring
        second_row = [
            InlineKeyboardButton("📊 All Positions", callback_data="show_all_positions"),
            InlineKeyboardButton("⚡ Monitors", callback_data="show_monitors")
        ]
        keyboard.append(second_row)

        # Third row - Analytics and tips
        third_row = [
            InlineKeyboardButton("📊 Analytics", callback_data="show_analytics"),
            InlineKeyboardButton("💡 Tips", callback_data="show_trading_tips")
        ]
        keyboard.append(third_row)

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def quick_actions() -> InlineKeyboardMarkup:
        """Quick actions grid keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Trade", callback_data="start_conversation"),
                InlineKeyboardButton("📋 Positions", callback_data="list_positions"),
                InlineKeyboardButton("📈 Stats", callback_data="show_statistics")
            ],
            [
                InlineKeyboardButton("🔔 Alerts", callback_data="alerts_list"),
                InlineKeyboardButton("🤖 AI", callback_data="ai_insights"),
                InlineKeyboardButton("⚙️ Settings", callback_data="show_settings")
            ],
            [
                InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def position_details() -> InlineKeyboardMarkup:
        """Position details keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Add to Position", callback_data="add_to_position"),
                InlineKeyboardButton("❌ Close Position", callback_data="close_position")
            ],
            [
                InlineKeyboardButton("📈 Modify TP", callback_data="modify_tp"),
                InlineKeyboardButton("🛑 Modify SL", callback_data="modify_sl")
            ],
            [
                InlineKeyboardButton("🔙 Back to Positions", callback_data="list_positions"),
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def statistics_menu() -> InlineKeyboardMarkup:
        """Statistics menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📊 Overall Stats", callback_data="detailed_stats"),
                InlineKeyboardButton("📈 Performance Chart", callback_data="performance_chart")
            ],
            [
                InlineKeyboardButton("🛡️ Conservative", callback_data="conservative_approach_stats")
            ],
            [
                InlineKeyboardButton("💰 P&L Analysis", callback_data="show_pnl_details"),
                InlineKeyboardButton("📉 Risk Metrics", callback_data="risk_analysis")
            ],
            [
                InlineKeyboardButton("💾 Export Stats", callback_data="export_stats"),
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def analytics_menu() -> InlineKeyboardMarkup:
        """Analytics menu keyboard"""
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
                InlineKeyboardButton("⏰ Best Trading Hours", callback_data="best_trading_hours"),
                InlineKeyboardButton("📉 Drawdown Analysis", callback_data="drawdown_analysis")
            ],
            [
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def settings_menu() -> InlineKeyboardMarkup:
        """Settings menu keyboard"""
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
                InlineKeyboardButton("⚖️ Position Mode", callback_data="position_mode_settings"),
                InlineKeyboardButton("🛡️ Risk Settings", callback_data="risk_settings")
            ],
            [
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def help_menu() -> InlineKeyboardMarkup:
        """Help menu keyboard"""
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
                InlineKeyboardButton("📹 Video Tutorials", url="https://youtube.com/your-channel"),
                InlineKeyboardButton("📖 Documentation", url="https://docs.your-site.com")
            ],
            [
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def pnl_details() -> InlineKeyboardMarkup:
        """P&L details keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📊 By Position", callback_data="pnl_by_position"),
                InlineKeyboardButton("📅 By Date", callback_data="pnl_by_date")
            ],
            [
                InlineKeyboardButton("🎯 TP Analysis", callback_data="tp_analysis"),
                InlineKeyboardButton("🛑 SL Analysis", callback_data="sl_analysis")
            ],
            [
                InlineKeyboardButton("📈 Projections", callback_data="pnl_projections"),
                InlineKeyboardButton("💡 Optimization", callback_data="pnl_optimization")
            ],
            [
                InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def confirmation(action: str, callback_yes: str, callback_no: str) -> InlineKeyboardMarkup:
        """Generic confirmation keyboard"""
        keyboard = [
            [
                InlineKeyboardButton(f"✅ Yes, {action}", callback_data=callback_yes),
                InlineKeyboardButton("❌ Cancel", callback_data=callback_no)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def back_button(callback_data: str = "refresh_dashboard") -> InlineKeyboardMarkup:
        """Simple back button"""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data=callback_data)]]
        return InlineKeyboardMarkup(keyboard)


# Alias for compatibility
build_enhanced_dashboard_keyboard = lambda c, ctx, p, m: DashboardKeyboards.main_dashboard(p > 0, False)