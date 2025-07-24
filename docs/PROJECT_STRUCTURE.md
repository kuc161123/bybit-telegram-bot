# Bybit Telegram Bot - Complete Project Structure

## Project Overview
This is a sophisticated Telegram trading bot for Bybit exchange with AI-powered features, social media sentiment analysis, and comprehensive position monitoring.

## Directory Structure

```
bybit-telegram-bot/
├── 📁 .claude/                    # Claude AI configuration
│   └── settings.local.json        # Local Claude settings
├── 📁 .cache/                     # Application cache directory
├── 📁 alerts/                     # Alert system components
│   ├── __init__.py               # Alert module initialization
│   ├── alert_manager.py          # Central alert management
│   ├── alert_types.py            # Alert type definitions
│   ├── daily_reports.py          # Daily report generation
│   ├── position_alerts.py        # Position-specific alerts
│   ├── price_alerts.py           # Price movement alerts
│   ├── risk_alerts.py            # Risk management alerts
│   ├── storage.py                # Alert persistence
│   └── volatility_alerts.py      # Volatility monitoring alerts
├── 📁 cache/                      # Runtime cache directory
├── 📁 clients/                    # External service clients
│   ├── __init__.py               # Client module exports
│   ├── ai_client.py              # OpenAI integration client
│   ├── bybit_client.py           # Bybit exchange client
│   └── bybit_helpers.py          # Bybit utility functions
├── 📁 config/                     # Configuration management
│   ├── __init__.py               # Config module exports
│   ├── constants.py              # Trading constants and state keys
│   ├── image_settings.py         # Dashboard image configuration
│   └── settings.py               # Runtime settings from environment
├── 📁 dashboard/                  # Dashboard generation
│   ├── __init__.py               # Dashboard module exports
│   ├── generator_analytics.py     # Analytics dashboard generator
│   ├── generator_analytics_compact.py # Compact dashboard version
│   ├── generator_analytics_compact_fixed.py # Fixed compact version
│   ├── keyboards_analytics.py     # Dashboard keyboard layouts
│   └── mobile_layouts.py          # Mobile-optimized layouts
├── 📁 docs/                       # Documentation
│   ├── ENHANCED_TRADE_MESSAGES.md # Trade message documentation
│   ├── ggshot_enhancements.md    # GGShot feature docs
│   ├── GGSHOT_ROBUSTNESS_REPORT.md # GGShot testing report
│   ├── RESPONSIVE_DASHBOARD_GUIDE.md # Dashboard usage guide
│   └── ULTRA_DASHBOARD_FEATURES.md # Advanced dashboard features
├── 📁 execution/                  # Trading execution logic
│   ├── __init__.py               # Execution module exports
│   ├── ai_market_analysis.py     # AI market analysis integration
│   ├── EXECUTION_SUMMARY.md      # Execution documentation
│   ├── execution_summary.py      # Trade execution summaries
│   ├── mirror_trader.py          # Mirror trading functionality
│   ├── monitor.py                # Position monitoring system
│   ├── portfolio_ai.py           # AI portfolio optimization
│   ├── position_merger.py        # Position merging logic
│   ├── trade_messages.py         # Trade message formatting
│   └── trader.py                 # Main trading logic
├── 📁 handlers/                   # Telegram bot handlers
│   ├── __init__.py               # Handler module exports
│   ├── ai_handlers.py            # AI-related command handlers
│   ├── ai_insights_handler.py    # AI insights display
│   ├── alert_handlers.py         # Alert management handlers
│   ├── analytics_callbacks.py    # Analytics button callbacks
│   ├── analytics_callbacks_new.py # Updated analytics callbacks
│   ├── callbacks.py              # General callback handlers
│   ├── callbacks_enhanced.py     # Enhanced callback handlers
│   ├── commands.py               # Main command handlers
│   ├── conversation.py           # Multi-step conversation flow
│   ├── missing_callbacks.py      # Missing callback handlers
│   ├── mobile_handlers.py        # Mobile UI handlers
│   ├── monitor_commands.py       # Monitor-specific commands
│   ├── monitoring.py             # Position monitoring handlers
│   ├── position_stats_handlers.py # Position statistics
│   ├── predictive_signals_handler.py # Predictive signal display
│   └── test_dashboard.py         # Dashboard testing handler
├── 📁 helpers/                    # Helper utilities
│   └── background_tasks.py       # Background task management
├── 📁 risk/                       # Risk management
│   ├── __init__.py               # Risk module exports
│   ├── assessment.py             # Risk assessment logic
│   ├── calculations.py           # Risk calculations
│   ├── regime.py                 # Market regime detection
│   └── sentiment.py              # Sentiment-based risk
├── 📁 shared/                     # Shared state management
│   ├── __init__.py               # Shared module exports
│   └── state.py                  # Centralized state management
├── 📁 social_media/               # Social media sentiment analysis
│   ├── __init__.py               # Social media module exports
│   ├── config.py                 # Social media configuration
│   ├── integration.py            # Bot integration logic
│   ├── main_collector.py         # Main collection orchestrator
│   ├── scheduler.py              # Collection scheduling
│   ├── 📁 collectors/            # Platform-specific collectors
│   │   ├── __init__.py           # Collector exports
│   │   ├── discord_collector.py  # Discord data collection
│   │   ├── news_collector.py     # News aggregation
│   │   ├── reddit_collector.py   # Reddit API collector
│   │   ├── reddit_scraper.py    # Reddit scraper fallback
│   │   ├── twitter_collector.py  # Twitter API collector
│   │   ├── twitter_scraper.py   # Twitter scraper fallback
│   │   ├── youtube_collector.py  # YouTube API collector
│   │   └── youtube_scraper.py   # YouTube scraper fallback
│   ├── 📁 dashboard/             # Sentiment dashboard
│   │   ├── __init__.py           # Dashboard exports
│   │   └── widgets.py            # Dashboard widgets
│   ├── 📁 processors/            # Data processing
│   │   ├── __init__.py           # Processor exports
│   │   ├── data_aggregator.py   # Data aggregation logic
│   │   ├── sentiment_analyzer.py # Sentiment analysis
│   │   ├── signal_generator.py   # Trading signal generation
│   │   └── trend_detector.py     # Trend detection
│   └── 📁 storage/               # Data storage
│       ├── __init__.py           # Storage exports
│       ├── historical_storage.py # Historical data storage
│       └── sentiment_cache.py    # Sentiment caching
├── 📁 utils/                      # Utility functions
│   ├── __init__.py               # Utils module exports
│   ├── alert_helpers.py          # Alert utility functions
│   ├── bybit_helpers.py          # Bybit-specific utilities
│   ├── cache.py                  # Caching utilities
│   ├── config_validator.py       # Configuration validation
│   ├── error_handler.py          # Error handling decorators
│   ├── formatters.py             # Message formatting
│   ├── ggshot_validator.py       # GGShot validation
│   ├── helpers.py                # General helper functions
│   ├── image_enhancer.py         # Image enhancement for OCR
│   ├── monitor_cleanup.py        # Monitor cleanup utilities
│   ├── performance_monitor.py    # Performance monitoring
│   ├── position_modes.py         # Position mode utilities
│   ├── screenshot_analyzer.py    # Screenshot OCR analysis
│   ├── screenshot_analyzer_enhanced.py # Enhanced OCR
│   └── validation.py             # Input validation
├── 📄 main.py                     # Main bot entry point
├── 📄 .env                        # Environment variables
├── 📄 .env.example                # Environment template
├── 📄 .env.minimal                # Minimal environment config
├── 📄 requirements.txt            # Python dependencies
├── 📄 run_main.sh                 # Bot restart script
├── 📄 CLAUDE.md                   # Claude AI instructions
├── 📄 trading_bot.log             # Main bot log file
├── 📄 bot_output.log              # Bot output log
├── 📄 alerts_data.pkl             # Serialized alert data
└── 📄 bybit_bot_dashboard_v4.1_enhanced.pkl # Bot state persistence

## Test and Utility Scripts

### Testing Scripts
- `test_ai_enhancements.py` - Test AI feature enhancements
- `test_ai_insights.py` - Test AI insights functionality
- `test_clean_dashboard.py` - Test clean dashboard generation
- `test_color_box_extraction.py` - Test color detection in screenshots
- `test_current_enhancement.py` - Test current enhancements
- `test_enhanced_dashboard.py` - Test enhanced dashboard features
- `test_enhanced_ocr.py` - Test enhanced OCR functionality
- `test_enhanced_ui.py` - Test UI enhancements
- `test_final_dashboard.py` - Test final dashboard implementation
- `test_ggshot_accuracy.py` - Test GGShot accuracy
- `test_ggshot_final.py` - Final GGShot tests
- `test_ggshot_long_short.py` - Test long/short detection
- `test_ggshot_validation.py` - Validate GGShot functionality
- `test_ggshot_visual.py` - Visual testing for GGShot
- `test_image_enhancement.py` - Test image enhancement
- `test_monitor_separation_fixes.py` - Test monitor separation
- `test_openai.py` - Test OpenAI integration
- `test_parallel_screenshot.py` - Test parallel screenshot processing
- `test_position_count.py` - Test position counting
- `test_stop_order_limit.py` - Test stop order limits
- `test_telegram_connection.py` - Test Telegram connectivity
- `test_ui.py` - Test UI components
- `test_ultra_dashboard.py` - Test ultra dashboard features

### Diagnostic and Debug Scripts
- `check_all_categories.py` - Check all trading categories
- `check_bybit_setup.py` - Verify Bybit client setup
- `check_positions_count.py` - Debug position counting
- `cleanup_monitors.py` - Clean up duplicate monitors
- `cleanup_stuck_monitors.py` - Remove stuck monitors
- `clear_cache_and_refresh.py` - Clear cache and refresh data
- `debug_orders.py` - Debug order placement
- `debug_pnl_calculations.py` - Debug P&L calculations
- `debug_pnl_totals.py` - Debug P&L totals
- `debug_tp_orders.py` - Debug take profit orders
- `debug_tp1_calculation.py` - Debug TP1 calculations
- `debug_tp1_issue.py` - Debug TP1 issues
- `diagnostic_check.py` - Run diagnostic checks
- `verify_dashboard_pnl.py` - Verify dashboard P&L
- `verify_pnl_calculations.py` - Verify P&L calculations
- `verify_tp1_fix.py` - Verify TP1 fixes

### Setup and Fix Scripts
- `setup_social_sentiment.py` - Setup social media sentiment
- `fix_imports.py` - Fix import issues
- `fix_monitor_count.py` - Fix monitor counting
- `fix_pnl_calculation.py` - Fix P&L calculation issues

## Documentation Files

### Main Documentation
- `CLAUDE.md` - Claude AI instructions for the project
- `README.md` - Project readme (if exists)
- `requirements.txt` - Python package requirements

### Feature Documentation
- `AI_MARKET_INSIGHTS_ENHANCEMENT.md` - AI market insights docs
- `AI_MARKET_INSIGHTS_IMPROVEMENTS.md` - AI improvements
- `ALERTS_IMPLEMENTATION.md` - Alert system documentation
- `ANALYTICS_DASHBOARD_COMPLETE.md` - Complete dashboard docs
- `ANALYTICS_DASHBOARD_FIXED.md` - Dashboard fixes
- `DECIMAL_PRECISION_FIX.md` - Decimal precision fixes
- `GGSHOT_*.md` - Various GGShot documentation files
- `MIRROR_TRADING_*.md` - Mirror trading documentation
- `MONITOR_SEPARATION_*.md` - Monitor separation docs
- `PNL_*.md` - P&L calculation documentation
- `SOCIAL_MEDIA_SETUP.md` - Social media setup guide
- `UI_ENHANCEMENT_*.md` - UI enhancement documentation

### Checkpoint and Reports
- `CHECKPOINT_1.md` - Development checkpoint
- `DIAGNOSTIC_REPORT.md` - Diagnostic report
- `diagnostic_report_20250623.md` - Dated diagnostic report
- `IMPROVEMENT_RECOMMENDATIONS.md` - Improvement suggestions
- `QUICK_IMPROVEMENTS.md` - Quick improvement guide

## Key Features by Directory

### Core Trading (`execution/`)
- Order placement and management
- Position monitoring with auto TP/SL
- Mirror trading to secondary accounts
- AI-powered portfolio optimization

### User Interface (`handlers/`, `dashboard/`)
- Telegram bot command handling
- Multi-step conversation flows
- Mobile-optimized dashboards
- Real-time position updates

### Risk Management (`risk/`)
- Position sizing calculations
- Market regime detection
- Sentiment-based risk assessment

### Social Media Intelligence (`social_media/`)
- Multi-platform data collection
- Sentiment analysis with AI
- Signal generation from social trends
- 6-hour automated collection cycles

### Monitoring & Alerts (`alerts/`, `execution/monitor.py`)
- Real-time position monitoring
- Price and volatility alerts
- Risk management notifications
- Daily performance reports

### Utilities (`utils/`)
- Screenshot analysis (GGShot)
- Error handling and logging
- Performance monitoring
- Configuration validation

## State Management
- Central state in `shared/state.py`
- Persistence via pickle files
- Chat-specific data isolation
- Monitor task tracking

## External Integrations
- Bybit exchange API
- OpenAI for market analysis
- Telegram Bot API
- Social media APIs (Reddit, Twitter, YouTube, Discord)
- News aggregation services