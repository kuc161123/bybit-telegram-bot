# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A sophisticated Telegram trading bot for Bybit exchange featuring:
- Fully async architecture using python-telegram-bot v20+
- Real-time position monitoring with Enhanced TP/SL management
- Dual account support (main + mirror) with position mode flexibility
- AI-powered features (market analysis, GGShot screenshot trading)
- Advanced alert system with comprehensive error recovery
- Mobile-optimized UI with touch-friendly interfaces
- Social media sentiment analysis integration (Reddit, Twitter/X, YouTube)

## Key Technical Details

### Mirror Trading Behavior
- Mirror positions use **percentage-based sizing** (same % of balance as main)
- Not fixed 50% ratio - proportional to each account's available balance
- Example: 2% on main = 2% on mirror (results in different absolute sizes)
- Mirror account typically uses ~33% of main position size in practice
- When TP4 or SL hits, mirror positions are automatically cleaned up

### API Parameter Requirements
- Bybit API requires `settleCoin="USDT"` for position queries without specific symbol
- Use `get_all_positions()` from `clients/bybit_helpers.py` instead of `get_position_info(None)`
- Mirror account API calls need explicit client parameter: `get_all_positions(client=bybit_client_2)`
- **Order ID Parameter**: Bybit API expects `orderId` (camelCase), not `order_id`
- **Mirror Account Order Fetching**: Use `get_all_open_orders(client=client)` then filter by symbol
- **Mirror Account Order Placement**: Requires parameter conversion from snake_case to camelCase and `category="linear"` parameter

### Order Management Behavior
- When TP1 (85%) hits: Unfilled limit orders are cancelled if `CANCEL_LIMITS_ON_TP1=true`
- When TP4 (final TP) or SL hits: ALL remaining orders are cancelled and position closes 100%
- SL orders cover full position including unfilled limit orders
- Mirror account SL orders automatically sync prices from main account
- Orphaned order cleanup runs periodically for both main and mirror accounts

### TP Distribution (Conservative Approach Only)
- **TP1**: 85% of position (triggers SL to breakeven, cancels limits if enabled)
- **TP2**: 5% of position (cumulative 90%)
- **TP3**: 5% of position (cumulative 95%)
- **TP4**: 5% of position (cumulative 100%)
- Fast approach has been completely removed from the codebase

### Complete TP/SL Rebalancing Behavior

#### When TP1 Hits (85% of position):
1. **SL Moves to Breakeven**:
   - Calculates breakeven price including fees (0.06%) and safety margin (0.02%)
   - Cancels existing SL order and places new one at breakeven price
   - SL quantity is adjusted to match remaining position (15% after TP1)

2. **Quantity Adjustments**:
   - SL quantity: Adjusted from 100% to remaining 15% of position
   - Remaining TPs: DO NOT rebalance - they stay at original sizes (5% each)

3. **Limit Order Cancellation**:
   - All unfilled limit orders are cancelled (if `CANCEL_LIMITS_ON_TP1=true`)
   - Phase transitions from BUILDING/MONITORING to PROFIT_TAKING

#### For Subsequent TP Hits (TP2, TP3, TP4):
1. **SL Quantity Adjustment Only**:
   - When TP2 hits: SL quantity → remaining 10%
   - When TP3 hits: SL quantity → remaining 5%
   - When TP4 hits: Position fully closed, all orders cancelled

2. **No TP Rebalancing**:
   - Remaining TPs keep their original quantities
   - This is by design for the conservative approach

#### Important Note:
- **Limit Fills**: Trigger full TP/SL rebalancing (increases position)
- **TP Hits**: Only trigger SL quantity adjustment (decreases position)

## Development Commands

### Quick Start (Makefile)
```bash
# Setup and Installation
make setup          # Initial project setup (creates venv, guides through config)
make install        # Install production dependencies
make dev-install    # Install all dependencies including dev tools

# Running the Bot
make run            # Start the bot (python main.py)
make run-prod       # Start with auto-restart (./scripts/shell/run_main.sh)
make kill           # Stop the bot (./kill_bot.sh)

# Testing
make test           # Run all tests
make test-unit      # Run unit tests only (pytest -m unit)
make test-integration # Run integration tests only (pytest -m integration)
pytest tests/test_emergency_dry_run.py -v  # Run specific test

# Code Quality
make lint           # Run flake8 and black check
make format         # Auto-format code with black
make check-env      # Verify Python version and environment variables

# Diagnostics (Bot-specific)
make diag-status    # Check current bot status
make diag-monitors  # Check monitor coverage
make diag-positions # Check mirror positions (if script exists)

# Maintenance
make clean          # Clean *.pyc, __pycache__, *.log, debug_*.png files
make clean-monitors # Clean orphaned monitors
make clean-stuck    # Clean stuck monitors
```

### Critical Scripts

#### System Verification
```bash
python find_missing_monitors_complete.py    # Verify all positions have monitors  
python check_monitor_status.py              # Check monitor status and coverage
python comprehensive_position_monitor_analyzer.py  # Analyze position-monitor mapping
```

#### Mirror Account Management
```bash
python scripts/fixes/sync_mirror_sl_from_main.py     # Sync SL orders from main to mirror
python scripts/fixes/verify_all_mirror_tp_sl.py      # Verify mirror TP/SL coverage
python scripts/fixes/place_missing_mirror_sl_only.py # Place only missing SL orders
```

#### Position Diagnostics
```bash
python scripts/fixes/verify_tp1_limit_cancellation.py      # Verify TP1 behavior
python scripts/fixes/verify_position_closure_completeness.py # Verify clean closure
python scripts/fixes/monitor_tp1_events.py                 # Real-time TP1 monitoring
```

#### Order Protection Management
```bash
python scripts/fixes/disable_external_order_protection.py  # Disable protection at runtime
python scripts/fixes/restore_external_order_protection.py  # Restore protection
python scripts/fixes/set_external_protection_env.py       # Set env vars persistently
```

## High-Level Architecture

### Core System Flow
```
User Command → Telegram Handler → Trading Execution → Bybit API
                                           ↓
                              Enhanced TP/SL Monitor (5-sec loop)
                                           ↓
                              Position State Changes → Alerts → User
```

### Critical Components

#### Enhanced TP/SL System (`execution/enhanced_tp_sl_manager.py`)
- Replaces Bybit conditional orders with programmatic monitoring
- 5-second monitoring loops with adaptive intervals (2s/5s/12s based on urgency)
- Direct pickle access to prevent circular imports
- Monitor keys: `{symbol}_{side}_{account}` (e.g., "BTCUSDT_Buy_main")
- Handles OCO logic, breakeven movements, and order cleanup
- Monitors position size changes to detect TP fills (not just order events)
- **Critical**: Detects TP hits by position size reduction, not order status
- **Background Task**: Runs `enhanced_tp_sl_monitoring_loop()` continuously via `helpers/background_tasks.py`
- **State Management**: Tracks monitor phases (BUILDING → MONITORING → PROFIT_TAKING → POSITION_CLOSED)

#### Mirror Trading System (`execution/mirror_enhanced_tp_sl.py`)
- Automatically syncs positions from main to mirror account
- Proportional position sizing based on account balance
- Full SL coverage including unfilled limit orders
- Independent monitoring for each account

#### State Persistence
- File: `bybit_bot_dashboard_v4.1_enhanced.pkl`
- Contains: positions, monitors, orders, chat data, system state
- Direct pickle access pattern used to avoid import cycles
- Automatic timestamped backups before critical operations
- **Backup Frequency**: Fixed excessive backups (1-2 seconds → 15 minutes)
- **Persistence Throttling**: Non-critical saves throttled to 30 seconds maximum
- **Critical Operations**: Monitor creation/deletion saves immediately with `force=True`
- **Thread Safety**: Uses `PickleFileLock` for atomic operations

### Trading Approaches
1. **Conservative** (Only approach now): 4 TPs (85%, 5%, 5%, 5%), gradual limit entry
2. **GGShot**: Screenshot-based trading via AI image analysis
3. **Fast Market**: Removed from current implementation

## Critical Implementation Details

### Position Closure Guarantees
When TP4 or SL hits, the system ensures 100% closure by:
1. Calling `_emergency_cancel_all_orders()` to cancel ALL orders
2. Calling `_ensure_position_fully_closed()` to close any remaining size
3. Triggering mirror account cleanup if main position closes
4. Removing all monitors and sending closure alerts

### Comprehensive Alert System
The enhanced alert system provides notifications for all trading events:
1. **Limit Order Fills**: Shows which order filled (e.g., "Limit 2/3 filled at $0.12345")
2. **TP Alerts**: All TP levels (TP1-TP4) with profit calculations and remaining targets
3. **TP Rebalancing**: Alerts when TPs are adjusted after limit fills
4. **Breakeven Movement**: Notifies when SL moves to breakeven after TP1
5. **Position Closure**: Final summary with total P&L and closure details
6. **Stop Loss Hits**: Risk management alerts with detailed context
7. **Chat ID Resolution**: Uses `_find_chat_id_for_position()` to ensure alerts reach the right user
8. **Account Identification**: All alerts clearly marked as MAIN or MIRROR account
9. **Detection Confidence**: Shows "Enhanced (2s intervals)" with High confidence
10. **Mirror Independence**: Separate alert streams for main and mirror accounts
11. **Retry Logic**: 5 attempts with exponential backoff for delivery reliability
12. **Fallback Support**: Uses `DEFAULT_ALERT_CHAT_ID` if primary chat unavailable

### Import Error Prevention
The codebase uses direct pickle access in `enhanced_tp_sl_manager.py` to avoid circular imports:
```python
# Instead of importing from shared.state
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)
```

### External Order Protection
- System only manages orders with bot's orderLinkId prefix by default
- Prevents modification of manually placed orders
- Can be disabled with `EXTERNAL_ORDER_PROTECTION=false` in .env
- Runtime disable available via `scripts/fixes/disable_external_order_protection.py`
- When disabled, orphaned order cleanup works for all orders

### Monitor Phase Management
Monitors transition through phases based on position state:
- **BUILDING**: Initial phase, position being established
- **MONITORING**: Active monitoring, no TPs hit yet
- **PROFIT_TAKING**: TP1 has been hit (85%+ filled)
- **POSITION_CLOSED**: All TPs hit or position manually closed

### Monitor Loading and Persistence
- **Startup**: Bot loads monitors from `bybit_bot_dashboard_v4.1_enhanced.pkl`
- **Account-Aware Keys**: Uses `{symbol}_{side}_{account}` format (e.g., "BTCUSDT_Buy_main")
- **Independent Monitoring**: Main and mirror accounts have separate monitors
- **Background Loop**: `enhanced_tp_sl_monitoring_loop()` runs every 5 seconds
- **Position Sync**: Automatically syncs monitors with actual positions every 60 seconds
- **Orphaned Cleanup**: Removes monitors for positions that no longer exist
- **Signal Files**: Uses `.reload_enhanced_monitors.signal` to trigger monitor reload
- **Force Load**: `.force_load_all_monitors` signal preserves all monitors without position sync

### Monitor Robustness (Critical Fix - January 2025)
The monitoring system now includes robust position checking to prevent premature monitor termination:
- **Retry Logic**: 3 attempts with exponential backoff before considering position closed
- **Dual Verification**: Direct position check + fallback to all positions check
- **Consecutive Confirmations**: Requires 2 consecutive "closed" detections before stopping
- **API Error Handling**: Distinguishes between API errors and actual position closure
- **Safety Default**: If all checks fail, assumes position still exists

### Enhanced Limit Order Tracking System
A comprehensive system for tracking limit orders throughout their lifecycle:
- **Full Order Details**: Fetches complete order information including price, quantity, status
- **Real-time Status Updates**: Monitors limit order fills and cancellations
- **Enhanced Alerts**: Detailed notifications when limit orders fill or are cancelled
- **TP Rebalancing**: Automatically adjusts TP levels when limit orders fill via `_adjust_all_orders_for_partial_fill()`
- **Account Support**: Works for both main and mirror accounts independently
- **Persistence**: Order tracking data survives bot restarts via pickle storage
- **API Compatibility**: Handles different API requirements for main vs mirror accounts

### Performance Statistics Integration
The Enhanced TP/SL Manager now properly updates performance statistics when positions close:
- **Statistics Update**: `_update_position_statistics()` method in Enhanced TP/SL Manager
- **Direct Pickle Access**: Updates bot_data statistics using direct pickle file access
- **Closure Reason Tracking**: Accurately categorizes closures as TP hits, SL hits, or manual
- **P&L Calculation**: Calculates real P&L based on entry/exit prices and position size
- **Mirror Account Handling**: Skips mirror positions to avoid double-counting statistics
- **Comprehensive Metrics**: Updates total trades, wins/losses, streaks, best/worst trades, drawdown tracking

### Margin Input Enhancement (July 2025)
- **0.5% Option Added**: Dashboard now includes 0.5% margin selection option
- **Percentage Default**: Manual keyboard input always treated as percentage unless explicitly expecting USDT
- **Common Percentages**: 0.5%, 1%, 2%, 5%, 10% available as quick selection buttons
- **Mobile Optimized**: Touch-friendly margin selection interface

## Environment Configuration

### Essential Variables
```bash
TELEGRAM_TOKEN=                  # Required: Telegram bot token
BYBIT_API_KEY=                  # Required: Main account API key
BYBIT_API_SECRET=               # Required: Main account API secret
ENABLE_MIRROR_TRADING=true      # Enable mirror account
BYBIT_API_KEY_2=                # Mirror account API key
BYBIT_API_SECRET_2=             # Mirror account API secret
```

### Key Feature Flags
```bash
CANCEL_LIMITS_ON_TP1=true       # Cancel unfilled limits when TP1 hits
ENABLE_ENHANCED_TP_SL=true      # Use enhanced monitoring (required)
ENABLE_MIRROR_ALERTS=true       # Enable enhanced alerts for mirror accounts
BREAKEVEN_FAILSAFE_ENABLED=true # Comprehensive breakeven protection
DYNAMIC_FEE_CALCULATION=true    # Use actual fee rates vs fixed 0.06%
EXTERNAL_ORDER_PROTECTION=false # Disable external order protection (if all trades are bot trades)
BOT_ORDER_PREFIX_STRICT=false   # Relaxed order validation
```

## Common Troubleshooting

### Position Issues
- **Missing SL on mirror**: Run `sync_mirror_sl_from_main.py`
- **Monitor count mismatch**: Run `find_missing_monitors_complete.py`
- **Orders not cancelling**: Check `CANCEL_LIMITS_ON_TP1` setting
- **TP not detected**: Check if position actually reached the percentage threshold (85% for TP1)
- **No monitors loaded**: Check if `bybit_bot_dashboard_v4.1_enhanced.pkl` exists and contains monitors
- **Monitors not activating**: Verify `enhanced_tp_sl_monitoring_loop()` is running in background tasks
- **Monitor stopped prematurely**: Check logs for API timeouts, monitor now has retry protection
- **Limit orders not tracked**: Ensure enhanced limit order tracker is working in monitor loop

### API Errors
- **"Missing some parameters"**: Use `get_all_positions()` not `get_position_info(None)`
- **"Illegal category" errors**: Mirror account orders need `category="linear"` parameter and camelCase conversion
- **Mirror account issues**: Ensure explicit client parameter in API calls
- **Rate limits**: Bot uses connection pooling and intelligent caching
- **Read timeout errors**: Monitor system now retries 3 times before considering position closed
- **"orderId" errors**: Remember Bybit API uses camelCase parameters
- **"Client parameter" errors**: Use account-specific placement methods, not direct client parameters

### System Recovery
- **Graceful shutdown**: `python safe_shutdown.py`
- **Emergency close all**: `python close_all_positions_and_orders.py` (USE WITH CAUTION)
- **Remove stuck monitors**: `python cleanup_stuck_monitors.py`
- **Fix monitor states**: Use scripts in `scripts/fixes/` for various recovery scenarios
- **Restore missing monitors**: Create `.force_load_all_monitors` signal file to reload from pickle

### Cache Management
- **Force refresh market data**: Use "Refresh AI" button in dashboard for immediate fresh analysis
- **Clear specific symbol cache**: `invalidate_market_analysis_cache("BTCUSDT")` and `invalidate_ai_insights_cache("BTCUSDT")`
- **Clear volatile data only**: `invalidate_volatile_caches()` - preserves 24-hour market analysis cache
- **Clear all caches**: `invalidate_all_caches()` - use sparingly as it clears expensive AI analysis
- **Check cache status**: Monitor logs for "cached X.Xh ago" messages to see cache age

## Market Analysis System (Real-time Enhancement)

### Enhanced Market Data Collection (`market_analysis/market_data_collector.py`)
- **Real-time WebSocket Integration**: Live price data via WebSocket streams for immediate updates
- **Cache TTL Optimization**: Reduced from 5 minutes to 60 seconds for responsive market data
- **Enhanced Volume Analysis**: 30-day average baseline vs current volume with ratio calculations
- **Robust Open Interest**: Multiple fallback methods with confidence indicators (high/medium/low)
- **Advanced Funding Rate**: Real-time funding rate collection with enhanced error handling
- **Data Quality Scoring**: Comprehensive quality metrics (0-100%) based on data availability

### Real-time Data Stream (`market_analysis/realtime_data_stream.py`)
- **WebSocket Implementation**: Direct connection to Bybit WebSocket API for live data
- **Auto-reconnection Logic**: Robust connection management with exponential backoff
- **Multi-symbol Support**: Simultaneous real-time data for multiple trading pairs
- **Integration with Bot**: Automatically starts with background tasks in main.py
- **Graceful Shutdown**: Proper cleanup and disconnection handling

### Enhanced Technical Analysis (`market_analysis/technical_indicators.py`)
- **Real-time Calculations**: ATR-based volatility percentage with proper price scaling
- **Support/Resistance Detection**: Dynamic level identification using multiple methods
- **Advanced Market Structure**: Multi-signal analysis with weighted scoring systems
- **Confidence Scoring**: Data quality assessment for reliable indicator calculations

### Enhanced Market Status Engine (`market_analysis/market_status_engine.py`)
- **Multi-source Sentiment**: Price action, volume, momentum, volatility, funding rates, open interest
- **Dynamic Market Structure**: HH-HL, LH-LL, Consolidation patterns with bias determination
- **Volume-weighted Sentiment**: Bullish/bearish volume distribution with conviction scaling
- **Technical Sentiment Analysis**: 6h/24h momentum, volatility interpretation, contrarian signals

### Advanced Sentiment Aggregation (`market_analysis/sentiment_aggregator.py`)
- **Fear & Greed Index**: Real-time crypto market sentiment integration
- **Funding Rate Analysis**: Contrarian sentiment from perpetual funding rates
- **Open Interest Sentiment**: Rising/falling OI interpretation with price context
- **Long/Short Ratio**: Crowd sentiment analysis for contrarian opportunities
- **Weighted Scoring**: Multi-source sentiment with confidence-adjusted calculations

### 24-Hour Caching System (Token Usage Optimization)
- **Cache TTL**: Market analysis and AI insights cache for 24 hours (down from 5 minutes)
- **Selective Invalidation**: Normal dashboard refreshes preserve market analysis cache
- **Manual Override**: "Refresh AI" button bypasses cache for immediate fresh data
- **Token Savings**: ~95% reduction in AI API calls (288 calls/day → 1 call/day per symbol)
- **Cache Constants**: `MARKET_ANALYSIS_CACHE_TTL = 86400`, `AI_INSIGHTS_CACHE_TTL = 86400`
- **Smart Refresh**: `invalidate_volatile_caches()` vs `invalidate_all_caches()` for targeted cache management

### Market Analysis Testing
```bash
# Test all market analysis enhancements
python test_market_status_enhancements.py

# Test specific components
python -m pytest tests/test_market_analysis.py -v
python -c "from market_analysis.market_data_collector import market_data_collector; import asyncio; print(asyncio.run(market_data_collector.collect_market_data('BTCUSDT')))"
```

## Recent Critical Updates

### January 2025 Updates
- **TP Detection Fix**: Corrected monitor states to properly detect TP fills based on position size changes
- **Phase Management**: Fixed incorrect POSITION_CLOSED markings for positions still open
- **Fast Approach Removal**: Completely removed fast approach, conservative only now
- **Monitor Recovery**: Created comprehensive scripts to sync monitors with exchange data
- **Monitor Robustness**: Added retry logic and consecutive confirmations to prevent premature stopping
- **API Error Handling**: Monitors now distinguish between network errors and position closure

### July 2025 Updates
- **Enhanced Limit Order Tracking**: Comprehensive limit order monitoring with full order details
- **Margin Selection Enhancement**: Added 0.5% margin option and percentage-based input handling
- **API Parameter Fixes**: Corrected camelCase parameters (orderId) and mirror account API calls
- **TP Rebalancing Confirmation**: Verified automatic TP adjustment on limit fills
- **Alert System Enhancement**: Detailed alerts for all limit order events and fills
- **Mirror Account Fixes**: Fixed "Illegal category" errors with proper parameter conversion and category inclusion
- **Enhanced Alert Integration**: All alert types now use enhanced formatters for both main and mirror accounts
- **Market Analysis Real-time Enhancement**: Complete overhaul of market data system for dynamic updates
- **WebSocket Integration**: Real-time price feeds with background task management and graceful shutdown
- **Advanced Sentiment Analysis**: Multi-source sentiment calculation with technical indicators and volume analysis
- **24-Hour Caching System**: Implemented long-term caching for market analysis to reduce AI token usage by 95%
- **Statistics Tracking Fix**: Enhanced TP/SL Manager now properly updates performance statistics on position closure
- **Selective Cache Invalidation**: Smart cache management preserves expensive AI analysis while refreshing volatile data

### Known Issues
- Message length: Position lists auto-switch to compact format for >20 positions
- Multiple bot instances: Only run ONE instance at a time to avoid Telegram conflicts
- PTBUserWarning: Deprecation warnings about `per_message` parameter (cosmetic only)
- Order fetch warnings: Normal for market orders that execute immediately
- WebSocket Stream: May take 2-3 seconds to establish connection on startup

### Recent Fixes
- **Market Data Static Issue**: Fixed non-updating market status by implementing real-time data collection
- **Cache TTL Optimization**: Reduced cache from 5 minutes to 60 seconds for responsive updates
- **Volume Ratio Calculation**: Enhanced 30-day average baseline vs 20-hour data for accuracy
- **Open Interest Reliability**: Multiple fallback methods with confidence indicators
- **WebSocket Real-time Data**: Live price integration with automatic startup and cleanup
- **Sentiment Analysis Enhancement**: Multi-source sentiment from price action, volume, and technical indicators
- **Backup Frequency**: Fixed excessive backup creation (1-2 seconds → 15 minutes)
- **TP Detection**: Corrected monitor states to properly detect TP fills
- **Mirror Account**: Enhanced independent monitoring with proper SL sync
- **Alert System**: Comprehensive notifications for all trading events (12+ types per position)
- **Monitor Premature Stopping**: Fixed with robust retry logic and confirmation requirements
- **Limit Order Tracking**: Full order details with enhanced error handling
- **Performance Dashboard**: Enhanced zero-statistics display with "Building History" messaging instead of confusing zeros
- **Mirror API Parameters**: Fixed snake_case to camelCase conversion and added required category parameter
- **Enhanced Alert Routing**: All alerts now use enhanced formatters with proper account identification
- **Statistics Tracking**: Fixed "Building History" issue by ensuring Enhanced TP/SL Manager updates statistics on position closure
- **24-Hour Caching**: Implemented long-term caching for market analysis with 95% token usage reduction
- **Cache Management**: Added selective invalidation functions preserving expensive AI analysis while refreshing volatile data

## Testing

### Running Tests
```bash
# Run all tests
make test

# Run unit tests only  
make test-unit

# Run integration tests only
make test-integration

# Run specific test file
pytest tests/test_emergency_dry_run.py -v

# Run with coverage
pytest --cov=. --cov-report=html
```

### Test Organization
- Unit tests: Mark with `@pytest.mark.unit`
- Integration tests: Mark with `@pytest.mark.integration`
- Slow tests: Mark with `@pytest.mark.slow`
- Async tests: Automatically handled with `asyncio_mode = auto`
- Test files: Must follow `test_*.py` naming convention
- Test functions: Must start with `test_`

### Statistics and Performance Data
- **Performance Statistics**: Stored in `bot_data` section of pickle file with keys like `stats_total_trades_initiated`, `stats_total_wins`, etc.
- **Statistics Reset**: The system tracks a `stats_last_reset_timestamp` - if all metrics are zero, this indicates a fresh start
- **Dashboard Zero State**: When no completed trades exist, dashboard shows "Building History" messaging instead of confusing zero values
- **Trade Completion Tracking**: Statistics only update when positions are fully closed via TP hits, SL hits, or manual closure

## Bot Startup Process

### Clean Startup Sequence
```bash
# 1. Kill any existing instances
pkill -f "python.*main.py"

# 2. Verify no instances running
ps aux | grep -E "(python.*main\.py)" | grep -v grep

# 3. Start the bot (choose ONE method)
python main.py                          # Foreground (see output)
python main.py > trading_bot.log 2>&1 & # Background with logging
nohup python main.py > trading_bot.log 2>&1 & # Survives terminal close
./scripts/shell/run_main.sh             # Auto-restart script
```

### Monitoring Bot Health
```bash
# Check if running
ps aux | grep main.py

# View real-time logs
tail -f trading_bot.log

# Check for errors
grep ERROR trading_bot.log | tail -20

# Check monitor status
grep "Monitoring.*positions" trading_bot.log | tail -5
```

## Performance Optimization

### Connection Pool Settings
The bot uses optimized connection pooling:
- HTTP Pool Size: 300 total connections
- Per-Host Connections: 75 
- Keep-alive Timeout: 60 seconds
- DNS Cache TTL: 300 seconds

### Monitoring Intervals
Enhanced TP/SL system uses adaptive intervals:
- Critical positions (near triggers): 2 seconds
- Active positions (pending TPs): 5 seconds  
- Standard monitoring: 12 seconds
- Inactive positions: 30 seconds

### Memory Management
- Automatic cache cleanup every 5 minutes
- Pickle file optimization with compression
- Connection pool recycling
- Background task management to prevent leaks

## Code Style and Formatting

### Black Configuration
- Line length: 120 characters
- Target version: Python 3.9+
- Excludes: venv, env, archive, backups directories

### Import Organization
- Use `isort` with black profile
- Group imports: standard library, third-party, local
- Absolute imports preferred for clarity

### Type Hints
- Use type hints for function parameters and returns
- Optional imports from `typing` module
- Mypy configured with Python 3.9 target

## Key Project Characteristics

### Development Dependencies and Tools
- **Testing Framework**: pytest with async support (`pytest-asyncio`)
- **Code Formatting**: Black (120 char line length) and isort
- **Type Checking**: MyPy with Python 3.9+ target
- **Linting**: flake8 with relaxed line length (120)
- **Build System**: Modern pyproject.toml-based setup
- **Package Management**: Uses requirements.txt for compatibility

### Project Version and Architecture Maturity
- **Version**: 4.1.0 (Beta stage according to pyproject.toml)
- **Architecture Pattern**: Event-driven with persistent state management
- **Concurrency Model**: Fully async using asyncio and python-telegram-bot v20+
- **State Management**: Pickle-based persistence with atomic operations and backups
- **Error Recovery**: Comprehensive retry logic, circuit breakers, and graceful degradation

### Critical Implementation Patterns
- **Direct Pickle Access**: Used in `enhanced_tp_sl_manager.py` to avoid circular imports
- **Account-Aware Keys**: Monitor keys use format `{symbol}_{side}_{account}` for dual account support
- **Adaptive Monitoring**: 2s/5s/12s intervals based on position urgency
- **Conservative-Only Trading**: Fast approach completely removed, only conservative and GGShot remain
- **Comprehensive Alerting**: 12+ different alert types per position with retry logic and fallback chat IDs