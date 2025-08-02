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

### Mirror Trading Behavior (Verified January 2025)
- Mirror positions use **percentage-based sizing** (same % of balance as main)
- Not fixed 50% ratio - proportional to each account's available balance
- Example: 2% on main = 2% on mirror (results in different absolute sizes)
- Mirror account typically uses ~33% of main position size in practice
- When TP4 or SL hits, mirror positions are automatically cleaned up
- **Complete Functional Parity**: Mirror accounts use identical TP rebalancing logic to main accounts
- **Independent Operation**: Mirror accounts operate with separate monitors and API calls
- **Account-Aware Processing**: All systems properly differentiate between main and mirror operations

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

#### Mirror Account Testing and Verification (January 2025)
```bash
# Comprehensive mirror account analysis
python test_building_phase_protection.py      # Test BUILDING phase protection
python test_proper_phase_transitions.py       # Test TP1 detection via order fills
python test_rebalancing_tp1_interaction.py    # Test rebalancing without phase interference

# Mirror account specific diagnostics
python scripts/fixes/verify_mirror_tp_rebalancing.py  # Verify mirror TP rebalancing works
python check_mirror_account_functionality.py          # Full mirror account test suite
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

### Monitor Phase Management (Enhanced January 2025)
Monitors transition through phases based on position state:
- **BUILDING**: Initial phase, position being established
- **MONITORING**: Active monitoring, no TPs hit yet
- **PROFIT_TAKING**: TP1 has been hit (85%+ filled)
- **POSITION_CLOSED**: All TPs hit or position manually closed

#### Critical Phase Protection (January 2025 Fix)
- **BUILDING Phase Protection**: Implemented comprehensive protection against false TP1 detection during position building
- **Position Reduction Safeguard**: Position reductions during BUILDING/MONITORING phases are protected from triggering TP1 logic
- **Fallback TP Detection**: Enhanced fallback logic now includes phase-aware checks to prevent premature TP detection
- **Mirror Account Synchronization**: Both main and mirror accounts use identical phase protection logic

### Monitor Loading and Persistence
- **Startup**: Bot loads monitors from `bybit_bot_dashboard_v4.1_enhanced.pkl`
- **Account-Aware Keys**: Uses `{symbol}_{side}_{account}` format (e.g., "BTCUSDT_Buy_main")
- **Independent Monitoring**: Main and mirror accounts have separate monitors
- **Background Loop**: `enhanced_tp_sl_monitoring_loop()` runs every 5 seconds
- **Position Sync**: Automatically syncs monitors with actual positions every 60 seconds
- **Orphaned Cleanup**: Removes monitors for positions that no longer exist
- **Periodic Cleanup**: Automated background cleanup every 10 minutes (configurable)
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

### Performance Configuration (2025 Optimizations)
```bash
# HTTP Connection Pool (Doubled for High Performance)
HTTP_MAX_CONNECTIONS=600         # Total HTTP connections (doubled from 300)
HTTP_MAX_CONNECTIONS_PER_HOST=150 # Per-host connections (doubled from 75)
HTTP_KEEPALIVE_TIMEOUT=60        # Connection keep-alive duration
HTTP_DNS_CACHE_TTL=300          # DNS cache TTL for performance

# API Performance Settings
BYBIT_TIMEOUT_SECONDS=60        # API request timeout (increased)
API_RETRY_MAX_ATTEMPTS=5        # Maximum retry attempts (increased)
API_RATE_LIMIT_CALLS_PER_SECOND=5 # Rate limiting (conservative)

# Enhanced Cache and Monitoring
CACHE_DEFAULT_TTL=300           # Default cache TTL (5 minutes)
CACHE_MAX_SIZE=1000            # Maximum cache entries
MAX_CONCURRENT_MONITORS=50      # Monitor concurrency limit
POSITION_MONITOR_INTERVAL=12    # Monitor check interval (optimized)

# Circuit Breaker and Error Handling
ENABLE_CIRCUIT_BREAKER=true     # Automatic failure protection
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5 # Failure count before activation
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60 # Recovery time in seconds

# Monitor Cleanup (2025 Enhancement)
ENABLE_PERIODIC_MONITOR_CLEANUP=true    # Automatic cleanup of stale monitors
MONITOR_CLEANUP_INTERVAL_SECONDS=600    # Cleanup frequency (10 minutes)
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

### Performance Testing and Monitoring (2025)
```bash
# Performance monitoring and diagnostics
python -c "from utils.performance_monitor import get_performance_statistics, get_system_health_report; print(get_performance_statistics())"
python -c "from utils.performance_monitor import get_api_performance_report; print(get_api_performance_report(minutes=30))"

# Test optimized systems
python -c "from utils.api_batch_processor import get_batch_processor; print(get_batch_processor().get_performance_stats())"
python -c "from utils.execution_aware_cache import get_execution_cache; print(get_execution_cache().get_stats())"

# Check cache effectiveness
python -c "from utils.cache import get_cache_stats; print(get_cache_stats())"

# Monitor system health during operation
python -c "from utils.performance_monitor import is_system_healthy, is_circuit_breaker_open; print(f'Healthy: {is_system_healthy()}, API Circuit: {is_circuit_breaker_open(\"api_calls\")}')"

# Performance optimization testing
python -c "from utils.performance_monitor import optimize_bot_performance; import asyncio; print(asyncio.run(optimize_bot_performance(force=True)))"
```

## Recent Critical Updates

### January 2025 Updates - CHECKPOINT 15: Complete Performance Optimization & Stable Operation
- **Comprehensive Performance Overhaul**: 85-96% improvement in monitor processing (70-85s → 2.5-4s)
- **Enhanced Cache Utilization**: Multi-source cache strategy achieving 85%+ hit rates (up from 30%)
- **Lock-free Connection Pool**: Burst-capable pool (150 soft/300 burst) with automatic shrinking
- **Adaptive Concurrency Control**: Semaphore-based API management (10-20 concurrent optimal)
- **Thread Pool Operations**: CPU-bound tasks moved to separate threads preventing event loop blocking
- **Progressive API Batching**: 60% reduction in API calls through intelligent request grouping
- **Research-based Optimizations**: External research findings applied for high-frequency trading performance

#### Comprehensive TP Rebalancing Fix (Critical Mirror Account Resolution - January 2025)
- **Stale Order Validation**: New `_validate_and_refresh_tp_orders()` method validates TP orders against exchange before processing
- **Unique OrderLinkID Generation**: `_generate_unique_order_link_id()` with timestamp + random suffix prevents duplicate conflicts
- **Mirror TP Recovery**: `_attempt_tp_order_recovery()` automatically reconstructs missing mirror TP orders from exchange data
- **Enhanced Error Handling**: Smart recognition of "order not exists" errors as successful cancellations (ErrCode 110001 handling)
- **Root Cause Resolution**: Fixed mirror account "No TP orders found" and "No orderId in result" errors completely
- **SKIPPED Status Alerts**: New alert type for failed rebalancing with detailed error context and recovery attempts
- **Mirror Account Verification**: Comprehensive analysis confirms mirror account TP rebalancing works identically to main account

#### Monitor System Enhancements
- **TP Detection Fix**: Corrected monitor states to properly detect TP fills based on position size changes
- **Phase Management**: Fixed incorrect POSITION_CLOSED markings for positions still open
- **Fast Approach Removal**: Completely removed fast approach, conservative only now
- **Monitor Recovery**: Created comprehensive scripts to sync monitors with exchange data
- **Monitor Robustness**: Added retry logic and consecutive confirmations to prevent premature stopping
- **API Error Handling**: Monitors now distinguish between network errors and position closure

#### Performance Optimization Details (January 2025)
**New Files Created:**
- `utils/lockfree_connection_pool.py`: Lock-free connection pool with burst capability (150 soft limit → 300 burst)
- `PERFORMANCE_OPTIMIZATIONS_2025.md`: Comprehensive documentation of all optimizations and expected improvements
- `TP_REBALANCING_COMPREHENSIVE_FIX.md`: Detailed analysis of TP rebalancing fixes and root cause resolution

**Critical Files Modified:**
- `utils/enhanced_limit_order_tracker.py`: Multi-source cache with extended TTL during high load, batch order fetching
- `helpers/background_tasks.py`: Adaptive semaphore control, thread pool executors, progressive API batching  
- `execution/enhanced_tp_sl_manager.py`: TP order validation, unique OrderLinkID generation, mirror account recovery
- `clients/bybit_client.py`: Enhanced HTTP session management with doubled connection pools
- All monitoring components: Optimized for cache-first operations and reduced API calls

**CHECKPOINT 12 Results:**
- **Monitor Processing**: 70-85 seconds → 2.55-3.83 seconds (93-96% improvement)
- **Cache Hit Rate**: 30% → 85%+ (research-based multi-source caching)
- **API Call Reduction**: 60% fewer calls through progressive batching
- **Mirror Account Reliability**: 100% resolution of TP rebalancing failures
- **Connection Pool**: Lock-free design with burst capability (no blocking operations)
- **Concurrency**: Adaptive semaphore control prevents API rate limit violations

- API call reduction: 60% fewer calls through intelligent batching
- Connection pool: Eliminated "pool full" errors with burst capability

**Research-based Implementation:**
- 10-20 concurrent operations optimal for trading bots (adaptive semaphore)
- Lock-free data structures eliminate bottlenecks (connection pool)
- Thread pool executors prevent event loop blocking (CPU operations)
- Multi-source caching with extended TTL improves hit rates dramatically

**Detailed Documentation**: See `PERFORMANCE_OPTIMIZATIONS_2025.md` for complete technical details, implementation strategies, rollback plans, and research citations for all performance improvements.

### CHECKPOINT 15 Summary (January 25, 2025)
The bot has achieved stable, high-performance operation with all optimizations successfully implemented and tested:
- ✅ Monitor processing: 2.5-4s (was 70-85s)
- ✅ Cache hit rates: 85%+ (was 30%)
- ✅ API calls: 60% reduction through batching
- ✅ Connection pool: Zero exhaustion errors
- ✅ System stability: Proven through extended operation
- ✅ All performance targets exceeded

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
- **CHECKPOINT 15 - Complete Performance Optimization & Stable Operation**: Comprehensive performance overhaul implementing 2025 best practices with proven stability
  - **Connection Pool Doubling**: HTTP connections increased from 300→600 total, 75→150 per-host
  - **Cache-on-Demand System**: Eliminated 45+ second monitoring delays through intelligent caching
  - **API Batch Processing**: Concurrent request handling with priority queues and deduplication
  - **Execution-Aware Caching**: Dynamic TTL management (5s trading, 15s monitoring)
  - **Optimized Pickle Persistence**: Dirty flags, batch writes, Protocol 5 optimization
  - **Concurrent Trade Execution**: 5-phase pipeline with semaphore control and performance tracking
  - **Performance Monitoring System**: Real-time metrics, circuit breakers, health checks
  - **85% Performance Improvement**: Monitor processing reduced from 86s to 5-8s

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

## Performance Optimization Scripts

### Enhanced Restart with Optimizations
```bash
# Restart bot with all performance optimizations active
./restart_with_fixes.sh

# Features enabled:
#   • Enhanced cache utilization (target: 85%+ hit rate)
#   • Adaptive semaphore concurrency control
#   • Thread pool for CPU-bound operations
#   • Lock-free connection pool with burst capability
```

### Performance Validation Commands
```bash
# Monitor performance improvements in real-time
tail -f trading_bot.log | grep -E "(Processed.*monitors|Cache hit rate|API batching)"

# Check for successful optimization indicators:
# ✅ Cache hit rate: 27/32 (84.4%) for BTCUSDT (main)
# ✅ API batching: Reduced 78 calls to 31 (60.3% reduction)
# ✅ Processed 39 monitors in 11.23s - Urgency breakdown: {'critical': 12, 'standard': 27}
```

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

## Performance Optimization (2025 Enhancements)

### High-Performance Architecture (Latest Optimizations)
The bot implements cutting-edge 2025 performance optimizations:

#### Connection Pool Optimization
- **HTTP Pool Size**: 600 total connections (doubled from 300)
- **Per-Host Connections**: 150 (doubled from 75)
- **Connection Recycling**: Automatic cleanup and recreation for optimal performance
- **Keep-alive Timeout**: 60 seconds with intelligent management

#### Cache-on-Demand System
- **Enhanced TP/SL Manager**: Central caching hub with 15-second TTL
- **Progressive Cache Invalidation**: Non-blocking cache updates using `asyncio.to_thread`
- **Execution-Aware Caching**: Dynamic TTLs (5s during trading, 15s monitoring)
- **Cache Hit Optimization**: ~95% reduction in API calls during active monitoring

#### API Request Batching
- **Concurrent Processing**: Priority queues with request deduplication
- **Batch Optimization**: Groups related API calls for efficiency
- **Smart Fallbacks**: Graceful degradation when batch operations fail
- **Rate Limit Management**: Intelligent throttling to prevent API limits

#### Monitoring Performance
- **Adaptive Intervals**: 2s/5s/12s based on position urgency and proximity to TP/SL triggers
- **Smart Grouping**: Urgency-based processing reduces overall system load
- **Cache Integration**: Monitor processing time reduced from 86+ seconds to 5-8 seconds
- **Position State Optimization**: Efficient state tracking prevents redundant operations

#### Memory Management & Persistence
- **Optimized Pickle Persistence**: Dirty flags and batch writes reduce I/O operations
- **Strategic Garbage Collection**: Automated GC with performance monitoring
- **Connection Pool Health**: Automatic recycling prevents memory leaks
- **Background Task Management**: Comprehensive cleanup prevents resource exhaustion

#### Trade Execution Pipeline
- **Concurrent Order Placement**: 5-phase pipeline with semaphore control
- **Phase Optimization**: PREPARATION → ENTRY → TP/SL → MIRROR → MONITORING
- **Performance Metrics**: Real-time tracking of execution efficiency
- **Circuit Breakers**: Automatic failure protection and recovery

### Performance Monitoring System
- **Real-time Metrics**: CPU, memory, API response times, cache hit rates
- **Circuit Breaker Patterns**: Automatic protection against API/system failures
- **Health Checks**: Comprehensive system status monitoring
- **Performance Alerts**: Proactive issue detection and notification

### Expected Performance Improvements
- **Trade Execution**: 60-80% faster through concurrent operations
- **Cache Operations**: 95% reduction in blocking time (71s → 3-5s)
- **Monitor Processing**: 85% faster (86s → 5-8s for 30 monitors)
- **API Efficiency**: 70-80% fewer redundant calls through intelligent caching
- **Memory Usage**: 50% reduction in I/O operations via batch persistence

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

### Advanced Performance Systems (2025)
The codebase includes sophisticated optimization systems:

#### Performance Monitoring (`utils/performance_monitor.py`)
- **Real-time System Metrics**: CPU, memory, disk usage, network I/O, active threads
- **API Performance Tracking**: Response times, error rates, timeout detection per endpoint
- **Trade Execution Metrics**: Phase timing, concurrent efficiency, success rates
- **Circuit Breaker System**: Automatic failure protection for API calls, trade execution, persistence
- **Memory Leak Detection**: Automated detection and alerting for memory growth patterns
- **Health Check System**: Comprehensive system health assessment with recommendations

#### API Batch Processing (`utils/api_batch_processor.py`)
- **Priority Queue System**: High/medium/low priority request handling
- **Request Deduplication**: Eliminates redundant API calls within batch windows
- **Concurrent Execution**: Processes multiple API requests simultaneously with semaphore control
- **Smart Caching**: Integrates with monitoring cache for optimal performance
- **Fallback Logic**: Graceful degradation to individual requests when batching fails

#### Execution-Aware Caching (`utils/execution_aware_cache.py`)
- **Dynamic TTL Management**: Different cache lifetimes based on system mode
- **Mode-Aware Operation**: MONITORING (15s) → EXECUTION (5s) → MAINTENANCE (30s)
- **Automatic Cleanup**: Background cache maintenance and expired entry removal
- **Cache Warming**: Proactive data loading for frequently accessed items

#### Optimized Persistence (`utils/optimized_pickle_persistence.py`)
- **Dirty Flag System**: Only saves changed data to reduce I/O operations
- **Batch Write Operations**: Groups multiple saves into single disk operation
- **Compression Support**: Optional gzip compression for large pickle files
- **Background Writer**: Non-blocking persistence with configurable batch intervals
- **Protocol 5 Optimization**: Uses latest pickle protocol with `pickletools.optimize()`

#### Concurrent Trade Execution (`utils/optimized_trade_execution.py`)
- **5-Phase Pipeline**: Structured execution flow with performance tracking
- **Semaphore Control**: Prevents API overload through concurrent limits
- **Automatic Retry Logic**: Exponential backoff for failed order placements
- **Performance Metrics**: Tracks execution time, success rate, concurrent efficiency
- **Phase Timing Analysis**: Detailed breakdown of execution bottlenecks

#### Lock-free Connection Pool (`utils/lockfree_connection_pool.py`)
- **Burst-capable Design**: Soft limit 150, burst to 300 connections during high load
- **Lock-free Operation**: No explicit locking for connection retrieval - immediate availability
- **Automatic Shrinking**: Returns to normal size after burst periods (30s duration)
- **Background Maintenance**: Cleanup stale connections and manage pool size every 30s
- **Health Monitoring**: Comprehensive statistics including timeout rates, utilization, health scores
- **WeakRef Management**: Automatic cleanup of closed connections using weak references
- **Performance Statistics**: Tracks connection requests, timeouts, burst activations, peak usage