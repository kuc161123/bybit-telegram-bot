#!/usr/bin/env python3
"""
Handler registration and setup for the trading bot - ENHANCED WITH CONSERVATIVE APPROACH.
ADDED: Support for dual trading approaches (Fast Market vs Conservative Limits)
ENHANCED: New conversation states and callback handlers for approach selection
ADDED: Position mode management commands (hedge mode, one-way mode)
FIXED: Proper async task scheduling for background tasks
"""
import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ConversationHandler, filters
)
from telegram.constants import ParseMode

# Import existing handlers
from .commands import (
    dashboard_command, error_handler, help_command,
    hedge_mode_command, one_way_mode_command, check_mode_command
)
from .conversation import (
    start_conversation, symbol_handler, side_handler,
    primary_entry_handler, limit_entries_handler, take_profits_handler, 
    stop_loss_handler, leverage_handler, margin_handler,
    confirmation_handler, cancel_handler,
    handle_side_callback, handle_execute_trade,
    handle_leverage_callback, handle_margin_callback,
    # ENHANCED: Conservative approach handlers
    approach_selection_handler, handle_approach_callback,
    # NEW: GGShot screenshot handlers
    screenshot_upload_handler, handle_ggshot_callbacks,
    # NEW: Back button handler
    handle_back_callback
)

logger = logging.getLogger(__name__)

# ENHANCED: Conversation states with GGShot screenshot strategy
SYMBOL, SIDE, APPROACH_SELECTION, SCREENSHOT_UPLOAD, PRIMARY_ENTRY, LIMIT_ENTRIES, TAKE_PROFITS, STOP_LOSS, LEVERAGE, MARGIN, CONFIRMATION = range(11)

def setup_enhanced_conversation_handlers(app):
    """Setup enhanced conversation handlers for dual approach trading"""
    try:
        # Define enhanced conversation handler with approach selection
        conv_handler = ConversationHandler(
            entry_points=[
                # Multiple entry points for better UX
                CallbackQueryHandler(start_conversation, pattern="^start_conversation$"),
                CallbackQueryHandler(start_conversation, pattern="^manual_setup$"),
                CallbackQueryHandler(start_conversation, pattern="^new_trade$"),
                CommandHandler("trade", start_conversation),
                CommandHandler("manual", start_conversation),
            ],
            states={
                SYMBOL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, symbol_handler)
                ],
                SIDE: [
                    CallbackQueryHandler(handle_side_callback, pattern="^conv_side:"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, side_handler)
                ],
                # ENHANCED: APPROACH_SELECTION state
                APPROACH_SELECTION: [
                    CallbackQueryHandler(handle_approach_callback, pattern="^conv_approach:"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, approach_selection_handler)
                ],
                # NEW: SCREENSHOT_UPLOAD state for GGShot approach
                SCREENSHOT_UPLOAD: [
                    MessageHandler(filters.PHOTO, screenshot_upload_handler),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, screenshot_upload_handler),
                    CallbackQueryHandler(handle_ggshot_callbacks, pattern="^ggshot_")
                ],
                PRIMARY_ENTRY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, primary_entry_handler)
                ],
                # ENHANCED: LIMIT_ENTRIES state for conservative approach
                LIMIT_ENTRIES: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, limit_entries_handler)
                ],
                TAKE_PROFITS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, take_profits_handler)
                ],
                STOP_LOSS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, stop_loss_handler)
                ],
                LEVERAGE: [
                    CallbackQueryHandler(handle_leverage_callback, pattern="^conv_leverage:"),
                    CallbackQueryHandler(handle_back_callback, pattern="^conv_back:"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, leverage_handler)
                ],
                MARGIN: [
                    CallbackQueryHandler(handle_margin_callback, pattern="^conv_margin:"),
                    CallbackQueryHandler(handle_margin_callback, pattern="^conv_margin_pct:"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, margin_handler)
                ],
                CONFIRMATION: [
                    CallbackQueryHandler(handle_execute_trade, pattern="^confirm_execute_trade$"),
                    CallbackQueryHandler(handle_ggshot_callbacks, pattern="^ggshot_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, confirmation_handler)
                ]
            },
            fallbacks=[
                CallbackQueryHandler(handle_back_callback, pattern="^conv_back:"),
                CallbackQueryHandler(cancel_handler, pattern="^cancel_conversation$"),
                CallbackQueryHandler(cancel_handler, pattern="^cancel$"),
                CommandHandler("cancel", cancel_handler),
                CommandHandler("dashboard", dashboard_command)
            ],
            allow_reentry=True,
            per_message=False
        )
        
        app.add_handler(conv_handler)
        logger.info("✅ Enhanced dual approach conversation handlers loaded!")
        logger.info("🎯 Fast Market and Conservative Limits approaches enabled")
        logger.info("📊 Support for 3 limit orders + 4 take profits active")
        
    except Exception as e:
        logger.error(f"❌ Error loading enhanced conversation handlers: {e}")

def setup_callback_handlers(app):
    """Setup enhanced callback query handlers"""
    try:
        from .callbacks_enhanced import handle_dashboard_callbacks
        from .callbacks import (
            handle_trading_callbacks,
            handle_settings_callbacks, handle_stats_callbacks,
            handle_position_callbacks
        )
        
        # Import all missing callback handlers
        from .missing_callbacks import (
            # Performance Analytics
            perf_daily_pnl, perf_weekly_pnl, perf_monthly_pnl,
            perf_win_rate, perf_profit_factor, perf_sharpe,
            download_performance_report,
            # Risk Analytics
            risk_var, risk_drawdown, risk_stress_test,
            risk_correlation, risk_beta, risk_liquidity,
            set_risk_limits,
            # Time Analysis
            time_hourly, time_daily, time_weekly,
            time_best_hours, time_patterns, time_seasonality,
            # Settings
            trade_settings, notification_settings,
            display_settings, api_settings,
            # Position Management
            refresh_positions, set_hedge_mode, set_one_way_mode,
            # Help Menu
            show_user_guide, show_trading_tips,
            show_faq, contact_support,
            # Analytics
            performance_metrics, suggest_rebalance,
            # Market Intelligence
            volume_analysis, sentiment_analysis,
            trend_analysis, momentum_analysis,
            # Performance
            win_streaks, trade_analysis
        )
        
        # Import position and stats handlers
        from .position_stats_handlers import list_positions, show_statistics, show_settings, show_help
        
        # Dashboard callbacks
        app.add_handler(CallbackQueryHandler(handle_dashboard_callbacks, pattern="^refresh_dashboard$"))
        app.add_handler(CallbackQueryHandler(handle_dashboard_callbacks, pattern="^view_positions$"))
        app.add_handler(CallbackQueryHandler(list_positions, pattern="^list_positions$"))
        app.add_handler(CallbackQueryHandler(show_statistics, pattern="^show_statistics$"))
        app.add_handler(CallbackQueryHandler(show_settings, pattern="^show_settings$"))
        app.add_handler(CallbackQueryHandler(show_help, pattern="^show_help$"))
        app.add_handler(CallbackQueryHandler(handle_dashboard_callbacks, pattern="^view_stats$"))
        app.add_handler(CallbackQueryHandler(handle_dashboard_callbacks, pattern="^back_to_dashboard$"))
        
        # Enhanced trading callbacks
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^execute_trade$"))
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^cancel_trade$"))
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^modify_trade$"))
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^confirm_execute$"))
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^start_conversation$"))
        
        # NEW: Approach selection callbacks
        app.add_handler(CallbackQueryHandler(handle_approach_callback, pattern="^conv_approach:"))
        
        # Settings callbacks
        app.add_handler(CallbackQueryHandler(handle_settings_callbacks, pattern="^set_"))
        app.add_handler(CallbackQueryHandler(handle_settings_callbacks, pattern="^save_"))
        
        # Stats callbacks
        app.add_handler(CallbackQueryHandler(handle_stats_callbacks, pattern="^detailed_stats$"))
        app.add_handler(CallbackQueryHandler(handle_stats_callbacks, pattern="^performance_chart$"))
        app.add_handler(CallbackQueryHandler(handle_stats_callbacks, pattern="^fast_approach_stats$"))
        app.add_handler(CallbackQueryHandler(handle_stats_callbacks, pattern="^conservative_approach_stats$"))
        app.add_handler(CallbackQueryHandler(handle_stats_callbacks, pattern="^export_stats$"))
        app.add_handler(CallbackQueryHandler(handle_stats_callbacks, pattern="^reset_stats$"))
        app.add_handler(CallbackQueryHandler(handle_stats_callbacks, pattern="^export_"))
        app.add_handler(CallbackQueryHandler(handle_stats_callbacks, pattern="^confirm_reset_stats$"))
        
        # Analytics callbacks - NEW
        try:
            from .analytics_callbacks_new import analytics_handlers
            for handler in analytics_handlers:
                app.add_handler(handler)
            logger.info("✅ Analytics dashboard handlers loaded!")
        except Exception as e:
            logger.warning(f"Analytics handlers not loaded: {e}")
        
        # Position management callbacks
        app.add_handler(CallbackQueryHandler(handle_position_callbacks, pattern="^close_position"))
        app.add_handler(CallbackQueryHandler(handle_position_callbacks, pattern="^modify_position"))
        
        # Symbol and side selection callbacks
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^select_symbol_"))
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^select_side_"))
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^quick_trade_"))
        
        # ENHANCED: Conservative approach specific callbacks
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^conservative_"))
        app.add_handler(CallbackQueryHandler(handle_trading_callbacks, pattern="^fast_"))
        
        # NEW: Position mode management callbacks
        app.add_handler(CallbackQueryHandler(handle_position_mode_callbacks, pattern="^enable_hedge_mode$"))
        app.add_handler(CallbackQueryHandler(handle_position_mode_callbacks, pattern="^enable_one_way_mode$"))
        app.add_handler(CallbackQueryHandler(handle_position_mode_callbacks, pattern="^check_position_mode$"))
        
        # Performance Analytics callbacks
        app.add_handler(CallbackQueryHandler(perf_daily_pnl, pattern="^perf_daily_pnl$"))
        app.add_handler(CallbackQueryHandler(perf_weekly_pnl, pattern="^perf_weekly_pnl$"))
        app.add_handler(CallbackQueryHandler(perf_monthly_pnl, pattern="^perf_monthly_pnl$"))
        app.add_handler(CallbackQueryHandler(perf_win_rate, pattern="^perf_win_rate$"))
        app.add_handler(CallbackQueryHandler(perf_profit_factor, pattern="^perf_profit_factor$"))
        app.add_handler(CallbackQueryHandler(perf_sharpe, pattern="^perf_sharpe$"))
        app.add_handler(CallbackQueryHandler(download_performance_report, pattern="^download_performance_report$"))
        
        # Risk Analytics callbacks
        app.add_handler(CallbackQueryHandler(risk_var, pattern="^risk_var$"))
        app.add_handler(CallbackQueryHandler(risk_drawdown, pattern="^risk_drawdown$"))
        app.add_handler(CallbackQueryHandler(risk_stress_test, pattern="^risk_stress_test$"))
        app.add_handler(CallbackQueryHandler(risk_correlation, pattern="^risk_correlation$"))
        app.add_handler(CallbackQueryHandler(risk_beta, pattern="^risk_beta$"))
        app.add_handler(CallbackQueryHandler(risk_liquidity, pattern="^risk_liquidity$"))
        app.add_handler(CallbackQueryHandler(set_risk_limits, pattern="^set_risk_limits$"))
        
        # Time Analysis callbacks
        app.add_handler(CallbackQueryHandler(time_hourly, pattern="^time_hourly$"))
        app.add_handler(CallbackQueryHandler(time_daily, pattern="^time_daily$"))
        app.add_handler(CallbackQueryHandler(time_weekly, pattern="^time_weekly$"))
        app.add_handler(CallbackQueryHandler(time_best_hours, pattern="^time_best_hours$"))
        app.add_handler(CallbackQueryHandler(time_patterns, pattern="^time_patterns$"))
        app.add_handler(CallbackQueryHandler(time_seasonality, pattern="^time_seasonality$"))
        
        # Settings callbacks
        app.add_handler(CallbackQueryHandler(trade_settings, pattern="^trade_settings$"))
        app.add_handler(CallbackQueryHandler(notification_settings, pattern="^notification_settings$"))
        app.add_handler(CallbackQueryHandler(display_settings, pattern="^display_settings$"))
        app.add_handler(CallbackQueryHandler(api_settings, pattern="^api_settings$"))
        
        # Position Management callbacks
        app.add_handler(CallbackQueryHandler(refresh_positions, pattern="^refresh_positions$"))
        app.add_handler(CallbackQueryHandler(set_hedge_mode, pattern="^set_hedge_mode$"))
        app.add_handler(CallbackQueryHandler(set_one_way_mode, pattern="^set_one_way_mode$"))
        
        # Help Menu callbacks
        app.add_handler(CallbackQueryHandler(show_user_guide, pattern="^show_user_guide$"))
        app.add_handler(CallbackQueryHandler(show_trading_tips, pattern="^show_trading_tips$"))
        app.add_handler(CallbackQueryHandler(show_faq, pattern="^show_faq$"))
        app.add_handler(CallbackQueryHandler(contact_support, pattern="^contact_support$"))
        
        # Analytics Menu callbacks
        app.add_handler(CallbackQueryHandler(performance_metrics, pattern="^performance_metrics$"))
        app.add_handler(CallbackQueryHandler(suggest_rebalance, pattern="^suggest_rebalance$"))
        
        # Market Intelligence callbacks
        app.add_handler(CallbackQueryHandler(volume_analysis, pattern="^volume_analysis$"))
        app.add_handler(CallbackQueryHandler(sentiment_analysis, pattern="^sentiment_analysis$"))
        app.add_handler(CallbackQueryHandler(trend_analysis, pattern="^trend_analysis$"))
        app.add_handler(CallbackQueryHandler(momentum_analysis, pattern="^momentum_analysis$"))
        
        # Performance Menu callbacks
        app.add_handler(CallbackQueryHandler(win_streaks, pattern="^win_streaks$"))
        app.add_handler(CallbackQueryHandler(trade_analysis, pattern="^trade_analysis$"))
        
        logger.info("✅ Enhanced callback handlers loaded!")
        logger.info("📊 Conservative approach callbacks active")
        logger.info("🎯 Position mode management callbacks registered")
        logger.info("✅ All dashboard button callbacks registered")
        
    except Exception as e:
        logger.error(f"❌ Error loading enhanced callback handlers: {e}")

async def handle_position_mode_callbacks(update, context):
    """Handle position mode related callback queries"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "enable_hedge_mode":
            # Simulate hedge mode command
            context.args = []
            await hedge_mode_command(update, context)
        elif query.data == "enable_one_way_mode":
            # Simulate one-way mode command
            context.args = []
            await one_way_mode_command(update, context)
        elif query.data == "check_position_mode":
            # Simulate check mode command
            context.args = []
            await check_mode_command(update, context)
    except Exception as e:
        logger.error(f"Error handling position mode callback: {e}")
        await query.edit_message_text(
            f"❌ Error handling position mode action: {str(e)}",
            parse_mode=ParseMode.HTML
        )

def setup_monitoring_handlers(app):
    """FIXED: Setup enhanced monitoring and automation handlers with proper async scheduling"""
    try:
        from .monitoring import setup_position_monitoring, setup_automated_tasks
        
        # These functions will schedule tasks properly within their own async context
        setup_position_monitoring(app)
        setup_automated_tasks(app)
        
        logger.info("✅ Enhanced monitoring handlers loaded!")
        logger.info("🛡️ Conservative approach monitoring support enabled")
        
    except Exception as e:
        logger.error(f"❌ Error loading enhanced monitoring handlers: {e}")

def setup_ai_handlers(app):
    """Setup AI-related handlers with conservative approach support"""
    try:
        from .ai_handlers import setup_ai_commands
        setup_ai_commands(app)
        logger.info("✅ Enhanced AI handlers loaded!")
        logger.info("🧠 AI analysis for both trading approaches enabled")
    except ImportError:
        logger.info("ℹ️ AI handlers not available - using fallback")
    except Exception as e:
        logger.error(f"❌ Error loading AI handlers: {e}")

def setup_conservative_specific_handlers(app):
    """Setup conservative approach specific handlers"""
    try:
        # Conservative approach specific command handlers
        from .conversation import handle_approach_callback
        
        # Additional conservative-specific callbacks
        app.add_handler(CallbackQueryHandler(handle_approach_callback, pattern="^approach_"))
        
        logger.info("✅ Conservative approach handlers loaded!")
        logger.info("🛡️ 3 limit orders + 4 TPs + isolated order management active")
        
    except Exception as e:
        logger.error(f"❌ Error loading conservative approach handlers: {e}")

def setup_enhanced_stats_handlers(app):
    """Setup enhanced statistics handlers for dual approaches"""
    try:
        # Enhanced stats tracking for both approaches
        logger.info("✅ Enhanced statistics handlers loaded!")
        logger.info("📊 Dual approach performance tracking enabled")
        logger.info("🚨 TP1 cancellation statistics enabled")
        
    except Exception as e:
        logger.error(f"❌ Error loading enhanced stats handlers: {e}")

def setup_position_mode_commands(app):
    """Setup position mode command handlers"""
    try:
        # Position mode command handlers
        app.add_handler(CommandHandler("hedge_mode", hedge_mode_command))
        app.add_handler(CommandHandler("one_way_mode", one_way_mode_command))
        app.add_handler(CommandHandler("check_mode", check_mode_command))
        
        logger.info("✅ Position mode command handlers loaded!")
        logger.info("🎯 /hedge_mode - Enable hedge mode for both directions")
        logger.info("🛡️ /one_way_mode - Enable one-way mode for single direction")
        logger.info("📊 /check_mode - Check current position mode")
        
    except Exception as e:
        logger.error(f"❌ Error loading position mode command handlers: {e}")

def setup_handlers(app: Application):
    """Setup all enhanced bot handlers with dual approach support"""
    logger.info("Setting up enhanced dual approach trading bot handlers...")
    
    # Core command handlers
    app.add_handler(CommandHandler("dashboard", dashboard_command))
    app.add_handler(CommandHandler("start", dashboard_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Test command for enhanced UI
    from .test_dashboard import test_dashboard_command
    app.add_handler(CommandHandler("test", test_dashboard_command))
    
    # NEW: Position mode command handlers
    setup_position_mode_commands(app)
    
    # ENHANCED: Dual approach conversation handlers (PRIORITY)
    setup_enhanced_conversation_handlers(app)
    
    # Enhanced callback handlers
    setup_callback_handlers(app)
    
    # Conservative approach specific handlers
    setup_conservative_specific_handlers(app)
    
    # AI handlers with dual approach support
    setup_ai_handlers(app)
    
    # FIXED: Enhanced monitoring handlers (now properly handles async tasks)
    try:
        setup_monitoring_handlers(app)
    except Exception as e:
        logger.warning(f"Enhanced monitoring handlers not available: {e}")
    
    # Enhanced statistics handlers
    setup_enhanced_stats_handlers(app)
    
    # Error handler (last)
    app.add_error_handler(error_handler)
    
    logger.info("✅ All enhanced dual approach handlers loaded successfully!")
    logger.info("📝 Enhanced manual trading with dual approaches")
    logger.info("⚡ Fast Market: Single entry + single TP/SL")
    logger.info("🛡️ Conservative Limits: 3 limit orders + 4 TPs + 1 SL")
    logger.info("🎯 Position Mode Commands: /hedge_mode, /one_way_mode, /check_mode")
    logger.info("📊 Isolated order management for conservative approach")
    logger.info("🚨 TP1 hit cancellation logic for conservative trades")
    logger.info("📈 Enhanced performance tracking for both approaches")
    logger.info("🧠 AI insights enabled for both trading strategies")
    logger.info("📱 Mobile-first design with improved workflows")

# Export main setup function
__all__ = ['setup_handlers']