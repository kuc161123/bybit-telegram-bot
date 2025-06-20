# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Running the Bot
```bash
# Direct execution
python main.py

# Using the restart script (auto-restarts on crash)
./run_bot.sh

# Alternative entry point
python bot.py
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

### Testing
```bash
# Run OpenAI integration test
python test_openai.py

# Setup and test social media sentiment analysis
python setup_social_sentiment.py

# Run tests with pytest (when tests are added)
pytest
pytest --asyncio-mode=auto  # For async tests
```

### Diagnostics
```bash
# Check Bybit setup
python check_bybit_setup.py

# Test social media sentiment configuration
python setup_social_sentiment.py
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