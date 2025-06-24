# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a sophisticated Telegram trading bot for Bybit exchange with the following key features:
- Fully async architecture using python-telegram-bot v20+
- Real-time position monitoring with automatic TP/SL management
- AI-powered market analysis and portfolio optimization (optional)
- Social media sentiment analysis integration
- Mobile-first UI with touch-optimized interfaces
- Comprehensive error handling and resource management

## Development Commands

### Running the Bot
```bash
# Direct execution
python main.py

# Using the restart script (auto-restarts on crash)
./run_bot.sh

# Note: bot.py doesn't exist - use main.py instead
```

### Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env  # Create .env file with required variables
```

### Required Environment Variables
- `TELEGRAM_TOKEN` - Telegram bot token
- `BYBIT_API_KEY` - Bybit API key
- `BYBIT_API_SECRET` - Bybit API secret
- `USE_TESTNET` - true/false (default: false)
- `OPENAI_API_KEY` - Optional, for AI features
- `LLM_PROVIDER` - Optional, defaults to "stub"

### Optional Social Media Sentiment Analysis Variables
- `ENABLE_SOCIAL_SENTIMENT` - Enable social sentiment analysis (default: true)
- `REDDIT_CLIENT_ID` - Reddit API client ID
- `REDDIT_CLIENT_SECRET` - Reddit API client secret  
- `TWITTER_BEARER_TOKEN` - Twitter API v2 Bearer Token
- `YOUTUBE_API_KEY` - YouTube Data API v3 key
- `DISCORD_BOT_TOKEN` - Discord bot token (optional)

### Testing & Diagnostics
```bash
# Run OpenAI integration test
python test_openai.py

# Setup and test social media sentiment analysis
python setup_social_sentiment.py

# Check Bybit client setup and connectivity
python check_bybit_setup.py

# Clean up duplicate/orphaned monitors
python cleanup_monitors.py

# Clean up stuck monitors
python cleanup_stuck_monitors.py

# Debug position counts and monitoring
python check_positions_count.py

# Verify PnL calculations
python verify_pnl_calculations.py

# Run tests with pytest (when tests are added)
pytest
pytest --asyncio-mode=auto  # For async tests
```

### Development & Debugging Tools
```bash
# Test enhanced dashboard
python test_enhanced_dashboard.py

# Test GGShot screenshot analyzer
python test_ggshot_accuracy.py

# Debug order placement
python debug_orders.py

# Debug PnL calculations
python debug_pnl_calculations.py

# Clear cache and refresh data
python clear_cache_and_refresh.py

# Validate configuration
python -c "from utils.config_validator import validate_configuration; validate_configuration()"
```

### Recent Enhancements (2025-06-18)

1. **Fixed Statistics Buttons**
   - Added handlers for: detailed_stats, performance_chart, fast_approach_stats, conservative_approach_stats, export_stats
   - All statistics buttons in the statistics menu now work properly
   - Located in: handlers/callbacks.py (functions: show_detailed_stats, show_performance_chart, etc.)

2. **Added Back Button Navigation**
   - Users can now navigate backwards in the trade setup conversation flow
   - Back button appears on all conversation states except the first (symbol input)
   - Preserves previously entered data when going back
   - Handler: handle_back_callback in handlers/conversation.py
   - Pattern: "conv_back:{state_number}" callback data

3. **Social Media Sentiment Analysis** (Latest Enhancement)
   - Multi-platform sentiment collection (Reddit, Twitter, YouTube, Discord, News)
   - 6-hour automated collection cycles optimized for free API limits
   - Advanced OpenAI sentiment analysis with VADER and TextBlob fallbacks
   - Integration with existing AI insights in dashboard
   - Professional market mood detection and signal generation
   - Located in: social_media/ module with complete integration

## High-Level Architecture

### Core Components

1. **Telegram Bot Layer** (`handlers/`)
   - Command handlers manage user interactions
   - Conversation handlers for multi-step flows
   - Callback handlers for inline keyboard responses
   - Mobile-optimized UI components

2. **Trading Execution** (`execution/`)
   - `trader.py` - Handles order placement and management
   - `monitor.py` - Continuous position monitoring with automatic TP/SL
   - `portfolio_ai.py` - AI-powered portfolio optimization

3. **External Services** (`clients/`)
   - `bybit_client.py` - Bybit exchange integration with connection pooling
   - `ai_client.py` - OpenAI integration for market analysis
   - Circuit breaker pattern for fault tolerance

4. **Risk Management** (`risk/`)
   - Position sizing based on account balance and risk percentage
   - Market regime detection for adaptive strategies
   - Sentiment analysis for trade timing

5. **State Management** (`shared/state.py`)
   - Centralized state constants
   - Persistence via pickle files
   - Chat-specific data isolation

6. **Social Media Intelligence** (`social_media/`)
   - Multi-platform data collectors (Reddit, Twitter, YouTube, Discord, News)
   - Advanced sentiment analysis with OpenAI integration
   - 6-hour automated collection cycles with API rate limiting
   - Caching and storage systems for performance
   - Professional dashboard integration

### Trading Approaches

The bot supports two main trading approaches:

1. **Fast Market**
   - Single TP at 100% of position
   - Quick in/out trades
   - Higher risk/reward

2. **Conservative**
   - 4 TPs: 70%, 10%, 10%, 10%
   - Gradual profit taking
   - Lower risk profile

### Key Design Patterns

1. **Async/Await Throughout**
   - All I/O operations are async
   - Prevents blocking the event loop
   - Enables concurrent operations

2. **Resource Management**
   - Connection pooling with limits
   - Memory caching with TTL
   - Graceful shutdown handlers
   - Background task lifecycle management

3. **External Position Adoption**
   - Monitors positions not created by the bot
   - Read-only tracking for P&L
   - No interference with external orders

4. **Mobile-First UI**
   - Touch-optimized button layouts
   - Quick selection for common values
   - Streamlined information display

### Critical Files

- `main.py` - Primary entry point with initialization
- `config/settings.py` - Runtime configuration
- `config/constants.py` - Trading constants and state keys
- `shared/state.py` - State management constants
- `execution/monitor.py` - Position monitoring logic
- `handlers/commands.py` - User command handlers

### Data Flow

1. User initiates trade via Telegram
2. Handler validates input and calculates position
3. Trader places orders on Bybit
4. Monitor tracks position and manages TP/SL
5. Dashboard updates with real-time status
6. AI components provide market insights (optional)
7. Social media sentiment collected every 6 hours and integrated into AI insights

### Performance Considerations

- Connection pools: 200 max, 50 per host
- Rate limiting: 5 calls/sec, burst of 10
- Cache TTL: 300 seconds
- Monitor interval: 10 seconds
- Max concurrent monitors: 50
- Social sentiment collection: 6-hour cycles with API-optimized limits
- Sentiment cache: 30min aggregated, 1hr platform, 24hr history

## Important Implementation Details

### State Persistence

The bot uses a pickle file (`bybit_bot_dashboard_v4.1_enhanced.pkl`) for persistence. This file stores:
- Active monitor tasks
- Position history
- Alert configurations
- User preferences
- Trading statistics

**Warning**: The pickle file is automatically backed up before major operations. Use `cleanup_monitors.py` to safely clean up state.

### Monitor Task Management

Monitors are uniquely identified by `{symbol}_{side}_{approach}_{chat_id}`. Key points:
- Only ONE monitor per position is allowed
- Monitors auto-detect trading approach from TP orders
- Orphaned monitors are cleaned up on startup
- Use `check_positions_count.py` to debug monitor issues

### Error Handling Patterns

The codebase uses several error handling patterns:

1. **Decorator-based** (`@handle_errors` in `utils/error_handler.py`):
   ```python
   @handle_errors(default_return=None, log_level=logging.WARNING)
   async def risky_operation():
       pass
   ```

2. **Context managers** (`ErrorContext` for operation tracking):
   ```python
   with ErrorContext("order_placement", symbol=symbol):
       # risky code here
   ```

3. **Circuit breakers** (in `clients/` for external services):
   - Automatically disable failing services
   - Exponential backoff for retries
   - Graceful degradation

### Resource Management

Critical for preventing memory leaks:

1. **Connection pooling** (configured in `clients/bybit_client.py`):
   - Uses aiohttp with connection limits
   - Automatic cleanup on shutdown
   - Timeout handling

2. **Task lifecycle** (in `helpers/background_tasks.py`):
   - All background tasks tracked in `_cleanup_tasks`
   - Graceful shutdown on SIGTERM/SIGINT
   - Monitor tasks have 24-hour maximum lifetime

3. **Message deduplication** (`shared/state.py`):
   - Prevents Telegram API spam
   - Smart message editing with caching
   - Automatic message splitting for long content

### Configuration Validation

The bot validates configuration on startup (`utils/config_validator.py`):
- Required vs optional environment variables
- API key format validation
- File permission checks
- Network configuration sanity checks

Run validation manually:
```bash
python -c "from utils.config_validator import validate_configuration; validate_configuration()"
```

### Trading Approach Detection

The bot automatically detects trading approaches by analyzing TP orders:
- **Fast Market**: Single TP at 100%
- **Conservative**: Multiple TPs (70%, 10%, 10%, 10%)
- Located in `execution/monitor.py` → `detect_approach_from_orders()`

### Position Adoption

All Bybit positions are now treated as bot positions (no external monitoring):
- Monitors created for any open position on startup
- P&L tracking for all positions
- No interference with manually placed orders

### Dashboard Generation

The dashboard (`dashboard/generator_analytics_compact.py`) uses PIL for image generation:
- Mobile-optimized layouts
- Real-time data updates
- Multiple theme support (dark/light)
- Responsive design for different screen sizes

### GGShot Feature

Screenshot analysis for quick trade setup (`utils/screenshot_analyzer.py`):
- OCR for text extraction
- Color-coded signal detection (green=long, red=short)
- Automatic symbol and price extraction
- Enhanced image processing for accuracy

### Mirror Trading

Optional feature for copying trades to secondary account:
- Configure with `BYBIT_API_KEY_2` and `BYBIT_API_SECRET_2`
- Automatic order synchronization
- Separate monitoring for mirror positions
- Alerts disabled for mirror accounts

## Code Organization Patterns

### Import Structure

The project uses a specific import pattern to avoid circular dependencies:

1. **Configuration first**: Always import from `config` before other modules
2. **Clients before handlers**: External service clients imported before handlers
3. **Use `__all__` exports**: Modules expose public APIs via `__init__.py`

Example from `main.py`:
```python
# Import configuration
from config import *

# Import clients and core components  
from clients import bybit_client, openai_client
from utils import *
from risk import *

# Import handlers last
from handlers import *
```

### Async Patterns

All I/O operations must be async. Common patterns:

1. **Async context managers**:
   ```python
   async with aiohttp.ClientSession() as session:
       async with session.get(url) as response:
           data = await response.json()
   ```

2. **Concurrent operations**:
   ```python
   results = await asyncio.gather(
       fetch_positions(),
       fetch_orders(),
       fetch_account_info(),
       return_exceptions=True
   )
   ```

3. **Background tasks**:
   ```python
   task = asyncio.create_task(monitor_position())
   _cleanup_tasks.append(task)  # Track for cleanup
   ```

### Handler Registration

Telegram handlers follow a specific registration pattern in `main.py`:

1. Command handlers registered first
2. Callback query handlers next  
3. Conversation handlers last (they can intercept)
4. Message handlers at the end

### Constants Organization

Constants are split across multiple files by purpose:
- `config/constants.py`: Trading constants and state keys
- `config/settings.py`: Runtime configuration from environment
- `config/image_settings.py`: Dashboard and UI constants
- `shared/state.py`: State management constants

### Testing Patterns

Test files follow naming convention `test_*.py` and typically:
1. Import the module being tested
2. Mock external dependencies (Bybit, Telegram)
3. Test both success and failure paths
4. Use `pytest-asyncio` for async tests

## Common Issues & Solutions

1. **"Too many monitors" error**:
   - Run `cleanup_monitors.py` to remove duplicates
   - Check `check_positions_count.py` for diagnostics

2. **Memory leaks**:
   - Monitor tasks have 24-hour lifetime
   - Check resource usage with performance monitor
   - Restart bot periodically with `run_bot.sh`

3. **Telegram message errors**:
   - Bot uses smart message editing with deduplication
   - Long messages automatically split
   - Rate limiting built-in

4. **Order placement failures**:
   - Check decimal precision for symbol
   - Verify account has sufficient balance
   - Use `debug_orders.py` for testing

5. **Configuration issues**:
   - Run config validator
   - Check `.env` file exists and is readable
   - Verify API keys are correct format