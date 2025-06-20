#!/usr/bin/env python3
"""
Enhanced mobile layouts for optimal iPhone 16 Pro Max experience.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config.constants import *
from utils.formatters import get_emoji

def build_mobile_optimized_quick_trade_keyboard():
    """Mobile-optimized quick trading with better thumb-reach ergonomics"""
    return InlineKeyboardMarkup([
        # Primary actions (most reachable area)
        [
            InlineKeyboardButton("⚡ BTC Long 10x", callback_data="quick_trade:long:BTCUSDT:10"),
            InlineKeyboardButton("⚡ BTC Short 10x", callback_data="quick_trade:short:BTCUSDT:10")
        ],
        [
            InlineKeyboardButton("⚡ ETH Long 10x", callback_data="quick_trade:long:ETHUSDT:10"),
            InlineKeyboardButton("⚡ ETH Short 10x", callback_data="quick_trade:short:ETHUSDT:10")
        ],
        [
            InlineKeyboardButton("⚡ SOL Long 10x", callback_data="quick_trade:long:SOLUSDT:10"),
            InlineKeyboardButton("⚡ SOL Short 10x", callback_data="quick_trade:short:SOLUSDT:10")
        ],
        
        # Separator for visual grouping
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        
        # Secondary actions (thumb-friendly grouping)
        [
            InlineKeyboardButton("📊 Portfolio", callback_data="view_status"),
            InlineKeyboardButton("🔧 Custom", callback_data="action:start_conversation")
        ],
        [
            InlineKeyboardButton("🎤 Voice Trade", callback_data="voice_command"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="back_to_dashboard")
        ]
    ])

def build_mobile_dashboard_primary_keyboard():
    """Primary mobile dashboard keyboard - optimized for one-handed use"""
    return InlineKeyboardMarkup([
        # Top tier (easiest thumb reach) - most used actions
        [
            InlineKeyboardButton("🎤 Voice Trade", callback_data="voice_command"),
            InlineKeyboardButton("📝 Manual", callback_data="start_conversation")
        ],
        
        # Second tier (comfortable reach) - monitoring actions
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard"),
            InlineKeyboardButton("📊 Positions", callback_data="view_positions")
        ],
        
        # Third tier (still reachable) - secondary actions
        [
            InlineKeyboardButton("📈 Stats", callback_data="view_stats"),
            InlineKeyboardButton("⚙️ Settings", callback_data="trade_settings")
        ]
    ])

def build_mobile_position_management_keyboard():
    """Mobile-optimized position management with clear visual hierarchy"""
    return InlineKeyboardMarkup([
        # Critical actions first (large buttons for safety)
        [InlineKeyboardButton("⚠️ CLOSE ALL POSITIONS", callback_data="close_all_positions_confirm")],
        
        # Separator
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        
        # Individual position actions
        [
            InlineKeyboardButton("🎯 Modify TP/SL", callback_data="modify_tp_sl"),
            InlineKeyboardButton("📏 Position Size", callback_data="modify_size")
        ],
        [
            InlineKeyboardButton("➕ Add to Position", callback_data="add_to_position"),
            InlineKeyboardButton("📋 Position Details", callback_data="position_details")
        ],
        
        # Navigation
        [
            InlineKeyboardButton("📊 View All", callback_data="view_positions"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])

def build_mobile_voice_keyboard():
    """Mobile-optimized voice trading interface"""
    return InlineKeyboardMarkup([
        # Primary voice actions (prominent placement)
        [InlineKeyboardButton("🎤 START VOICE COMMAND", callback_data="voice_command")],
        
        # Separator for visual clarity
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        
        # Support actions
        [
            InlineKeyboardButton("💡 Examples", callback_data="voice_examples"),
            InlineKeyboardButton("🧪 Test Parser", callback_data="test_voice_parser")
        ],
        [
            InlineKeyboardButton("📝 Manual Instead", callback_data="start_conversation"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])

def build_mobile_ai_insights_keyboard():
    """Mobile-optimized AI insights and recommendations"""
    return InlineKeyboardMarkup([
        # AI actions (thumb-friendly)
        [
            InlineKeyboardButton("🧠 Detailed Analysis", callback_data="detailed_ai_analysis"),
            InlineKeyboardButton("🎯 Get Recommendation", callback_data="ai_trade_recommendation")
        ],
        [
            InlineKeyboardButton("📊 Market Sentiment", callback_data="market_sentiment"),
            InlineKeyboardButton("💡 Portfolio Health", callback_data="portfolio_health")
        ],
        [
            InlineKeyboardButton("🔄 Refresh AI", callback_data="refresh_ai_insights"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])

def build_mobile_settings_keyboard():
    """Mobile-optimized settings with clear grouping"""
    return InlineKeyboardMarkup([
        # Trading settings (most important)
        [
            InlineKeyboardButton("⚡ Default Leverage", callback_data="set_default_leverage"),
            InlineKeyboardButton("💰 Default Margin", callback_data="set_default_margin")
        ],
        
        # Feature settings
        [
            InlineKeyboardButton("🎤 Voice Settings", callback_data="voice_settings"),
            InlineKeyboardButton("🧠 AI Settings", callback_data="ai_settings")
        ],
        
        # Risk & notifications
        [
            InlineKeyboardButton("🛡️ Risk Management", callback_data="risk_settings"),
            InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings")
        ],
        
        # App settings
        [
            InlineKeyboardButton("📱 Mobile Prefs", callback_data="mobile_preferences"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])

def build_mobile_stats_keyboard():
    """Mobile-optimized statistics display"""
    return InlineKeyboardMarkup([
        # Main stats actions
        [
            InlineKeyboardButton("📊 Detailed Stats", callback_data="detailed_stats"),
            InlineKeyboardButton("📈 Performance Chart", callback_data="performance_chart")
        ],
        [
            InlineKeyboardButton("📋 Trade History", callback_data="trade_history"),
            InlineKeyboardButton("💰 P&L Breakdown", callback_data="pnl_breakdown")
        ],
        
        # Export options
        [
            InlineKeyboardButton("📤 Export CSV", callback_data="export_csv"),
            InlineKeyboardButton("📄 Export PDF", callback_data="export_pdf")
        ],
        
        # Management
        [
            InlineKeyboardButton("🔄 Reset Stats", callback_data="reset_stats"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])

def build_mobile_error_recovery_keyboard():
    """Mobile-optimized error recovery options"""
    return InlineKeyboardMarkup([
        # Primary recovery actions
        [InlineKeyboardButton("🔄 Try Again", callback_data="retry_last_action")],
        
        # Alternative actions
        [
            InlineKeyboardButton("🎤 Voice Trade", callback_data="voice_command"),
            InlineKeyboardButton("📝 Manual Trade", callback_data="start_conversation")
        ],
        [
            InlineKeyboardButton("📊 Check Positions", callback_data="view_positions"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ],
        
        # Support
        [InlineKeyboardButton("❓ Get Help", callback_data="mobile_help")]
    ])

def build_mobile_help_keyboard():
    """Enhanced mobile help system"""
    return InlineKeyboardMarkup([
        # Quick start guides
        [
            InlineKeyboardButton("🚀 Quick Start", callback_data="help:quick_start"),
            InlineKeyboardButton("📱 Mobile Guide", callback_data="help:mobile_guide")
        ],
        
        # Feature help
        [
            InlineKeyboardButton("🎤 Voice Help", callback_data="help:voice_trading"),
            InlineKeyboardButton("🧠 AI Features", callback_data="help:ai_features")
        ],
        [
            InlineKeyboardButton("📊 Trading Help", callback_data="help:trading_basics"),
            InlineKeyboardButton("🛡️ Risk Guide", callback_data="help:risk_management")
        ],
        
        # Troubleshooting
        [
            InlineKeyboardButton("🔧 Troubleshooting", callback_data="help:troubleshooting"),
            InlineKeyboardButton("❓ FAQ", callback_data="help:faq")
        ],
        
        # Navigation
        [InlineKeyboardButton("🏠 Back to Dashboard", callback_data="back_to_dashboard")]
    ])

def build_mobile_trade_confirmation_keyboard():
    """Mobile-optimized trade confirmation with clear visual hierarchy"""
    return InlineKeyboardMarkup([
        # EXECUTE button (prominent, green, large)
        [InlineKeyboardButton("🚀 EXECUTE TRADE", callback_data="confirm_execute_trade")],
        
        # Visual separator for safety
        [InlineKeyboardButton("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", callback_data="noop")],
        
        # Modification options
        [
            InlineKeyboardButton("🔧 Modify", callback_data="modify_trade"),
            InlineKeyboardButton("📝 Review", callback_data="review_trade_setup")
        ],
        
        # Cancel options
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_conversation"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])

def build_mobile_symbol_selection_keyboard():
    """Mobile-optimized symbol selection with popular pairs first"""
    # Popular symbols organized by categories for mobile
    return InlineKeyboardMarkup([
        # Major cryptocurrencies (most popular)
        [
            InlineKeyboardButton("₿ BTC", callback_data="select_symbol_BTCUSDT"),
            InlineKeyboardButton("Ξ ETH", callback_data="select_symbol_ETHUSDT"),
            InlineKeyboardButton("◎ SOL", callback_data="select_symbol_SOLUSDT")
        ],
        [
            InlineKeyboardButton("₳ ADA", callback_data="select_symbol_ADAUSDT"),
            InlineKeyboardButton("● DOT", callback_data="select_symbol_DOTUSDT"),
            InlineKeyboardButton("🔗 LINK", callback_data="select_symbol_LINKUSDT")
        ],
        
        # DeFi & Layer 2
        [
            InlineKeyboardButton("🔺 AVAX", callback_data="select_symbol_AVAXUSDT"),
            InlineKeyboardButton("🟣 MATIC", callback_data="select_symbol_MATICUSDT"),
            InlineKeyboardButton("🟡 BNB", callback_data="select_symbol_BNBUSDT")
        ],
        
        # Meme & trending
        [
            InlineKeyboardButton("🐕 DOGE", callback_data="select_symbol_DOGEUSDT"),
            InlineKeyboardButton("🐸 PEPE", callback_data="select_symbol_PEPEUSDT"),
            InlineKeyboardButton("🔥 SHIB", callback_data="select_symbol_SHIBUSDT")
        ],
        
        # Search & navigation
        [
            InlineKeyboardButton("🔍 Search Symbol", callback_data="search_symbol"),
            InlineKeyboardButton("📝 Type Symbol", callback_data="manual_symbol_entry")
        ],
        [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
    ])

def build_mobile_leverage_selection_keyboard():
    """Mobile-optimized leverage selection with visual risk indicators"""
    return InlineKeyboardMarkup([
        # Conservative (green)
        [
            InlineKeyboardButton("🟢 5x (Safe)", callback_data="select_leverage_5"),
            InlineKeyboardButton("🟢 10x (Safe)", callback_data="select_leverage_10")
        ],
        
        # Moderate (yellow)
        [
            InlineKeyboardButton("🟡 20x (Moderate)", callback_data="select_leverage_20"),
            InlineKeyboardButton("🟡 25x (Moderate)", callback_data="select_leverage_25")
        ],
        
        # Aggressive (orange)
        [
            InlineKeyboardButton("🟠 50x (High Risk)", callback_data="select_leverage_50"),
            InlineKeyboardButton("🟠 75x (High Risk)", callback_data="select_leverage_75")
        ],
        
        # Extreme (red)
        [
            InlineKeyboardButton("🔴 100x (EXTREME)", callback_data="select_leverage_100"),
            InlineKeyboardButton("📝 Custom", callback_data="custom_leverage")
        ],
        
        # Navigation
        [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
    ])

def build_mobile_margin_selection_keyboard():
    """Mobile-optimized margin selection with dollar amounts"""
    return InlineKeyboardMarkup([
        # Small amounts
        [
            InlineKeyboardButton("💰 $25", callback_data="select_margin_25"),
            InlineKeyboardButton("💰 $50", callback_data="select_margin_50"),
            InlineKeyboardButton("💰 $100", callback_data="select_margin_100")
        ],
        
        # Medium amounts
        [
            InlineKeyboardButton("💰 $200", callback_data="select_margin_200"),
            InlineKeyboardButton("💰 $500", callback_data="select_margin_500"),
            InlineKeyboardButton("💰 $1000", callback_data="select_margin_1000")
        ],
        
        # Large amounts
        [
            InlineKeyboardButton("💰 $2000", callback_data="select_margin_2000"),
            InlineKeyboardButton("💰 $5000", callback_data="select_margin_5000")
        ],
        
        # Custom & percentage
        [
            InlineKeyboardButton("📝 Custom Amount", callback_data="custom_margin"),
            InlineKeyboardButton("📊 Percentage", callback_data="percentage_margin")
        ],
        
        # Navigation
        [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
    ])

def build_mobile_loading_keyboard():
    """Mobile loading state with cancel option"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ Processing... Please wait", callback_data="noop")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_current_operation")]
    ])

def build_mobile_success_keyboard():
    """Mobile success state with next actions"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 View Position", callback_data="view_positions"),
            InlineKeyboardButton("🚀 New Trade", callback_data="start_conversation")
        ],
        [
            InlineKeyboardButton("🎤 Voice Trade", callback_data="voice_command"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])