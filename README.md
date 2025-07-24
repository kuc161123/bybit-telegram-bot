# Bybit Telegram Trading Bot 🤖

A sophisticated, production-ready Telegram bot for automated cryptocurrency trading on Bybit exchange. Built with Python 3.9+ and featuring AI-powered market analysis, social media sentiment integration, and advanced risk management.

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Async](https://img.shields.io/badge/async-ready-brightgreen.svg)
![Telegram Bot API](https://img.shields.io/badge/telegram--bot-20.0+-blue.svg)

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Trading Approaches](#-trading-approaches)
- [Commands](#-commands)
- [Advanced Features](#-advanced-features)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)
- [Security](#-security)
- [Contributing](#-contributing)
- [License](#-license)

## 🚀 Features

### Core Trading Features
- **Automated Trading**: Execute trades via Telegram with advanced order management
- **Conservative Trading Approach**: Multiple limit orders with 4 TP levels (85/5/5/5%)
- **Position Monitoring**: Real-time tracking with automatic TP/SL management
- **Smart Position Merging**: Intelligent merge logic for both approaches
- **Auto-Rebalancing**: Automatic position size adjustment based on approach
- **Mirror Trading**: Optional secondary account synchronization

### Risk Management
- **Position Sizing**: Dynamic sizing based on account balance and risk percentage
- **Stop Loss Protection**: Automatic SL placement with all positions
- **Take Profit Management**: Single or multiple TP levels based on approach
- **Emergency Shutdown**: Instant close all positions with `/emergency`
- **Health Monitoring**: Continuous position health checks with auto-recovery

### User Interface
- **Mobile-First Design**: Touch-optimized buttons and layouts
- **Interactive Dashboard**: Real-time position and P&L visualization
- **GGShot Integration**: Screenshot analysis for quick trade setup
- **Back Navigation**: Navigate through trade setup with data preservation
- **Multi-Language**: Emoji-based universal understanding

### AI & Analytics
- **Market Analysis**: AI-powered insights using OpenAI GPT-4
- **Social Sentiment**: Multi-platform sentiment analysis (Reddit, Twitter, YouTube)
- **Performance Metrics**: Comprehensive trading statistics and analytics
- **Predictive Signals**: ML-based trade recommendations (optional)

### Technical Features
- **Fully Async**: Non-blocking architecture for maximum performance
- **Connection Pooling**: Optimized API connections with rate limiting
- **Smart Caching**: Reduced API calls with intelligent data caching
- **Error Recovery**: Circuit breakers and automatic retry mechanisms
- **State Persistence**: Reliable state management with backup systems

## 🏗️ Architecture

### System Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                 │     │                  │     │                 │
│  Telegram Users ├────►│  Telegram Bot    ├────►│  Bybit Exchange │
│                 │     │  (python-telegram│     │  (REST API)     │
└─────────────────┘     │   -bot v20+)     │     └─────────────────┘
                        └────────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              ┌─────▼──────┐          ┌──────▼──────┐
              │            │          │             │
              │  Trading   │          │  Monitoring │
              │  Engine    │          │  System     │
              │            │          │             │
              └─────┬──────┘          └──────┬──────┘
                    │                         │
                    └────────────┬────────────┘
                                 │
                         ┌───────▼────────┐
                         │                │
                         │  AI & Analytics│
                         │  (Optional)    │
                         │                │
                         └────────────────┘
```

### Directory Structure

```
bybit-telegram-bot/
├── clients/                # External service integrations
│   ├── bybit_client.py     # Bybit API wrapper
│   ├── bybit_helpers.py    # Helper functions
│   └── ai_client.py        # OpenAI integration
├── config/                 # Configuration management
│   ├── constants.py        # Trading constants
│   └── settings.py         # Environment settings
├── dashboard/              # Dashboard generation
│   ├── generator_v2.py     # Main dashboard generator
│   ├── components.py       # UI components
│   ├── models.py          # Data models
│   └── keyboards_v2.py    # Keyboard layouts
├── execution/              # Trading execution layer
│   ├── trader.py          # Order placement (conservative approach only)
│   ├── monitor.py         # Position monitoring
│   ├── enhanced_tp_sl_manager.py  # Enhanced TP/SL system
│   ├── mirror_enhanced_tp_sl.py   # Mirror account TP/SL
│   └── position_merger.py # Position merge logic
├── handlers/               # Telegram bot handlers
│   ├── commands.py         # Command handlers
│   ├── conversation.py     # Multi-step flows
│   ├── callbacks.py        # Button callbacks
│   ├── position_stats_handlers.py  # Position statistics
│   └── ai_insights_handler.py      # AI market insights
├── market_analysis/        # Market analysis tools
│   ├── market_status_engine.py     # Market conditions
│   └── technical_indicators.py     # Technical analysis
├── scripts/                # Utility scripts (organized)
│   ├── diagnostics/        # System health checks
│   ├── fixes/             # Issue resolution scripts
│   ├── maintenance/       # Routine maintenance
│   └── analysis/          # Data analysis tools
├── tests/                  # Test suite
│   ├── test_*.py          # Unit and integration tests
│   └── conftest.py        # Test configuration
├── utils/                  # Utility functions
│   ├── formatters.py      # Message formatting
│   ├── screenshot_analyzer.py  # GGShot feature
│   ├── pickle_lock.py     # Thread-safe persistence
│   └── alert_helpers.py   # Alert system helpers
├── docs/                   # Documentation
│   ├── CLAUDE.md          # AI assistant guide
│   └── history/           # Historical documentation
├── main.py                # Application entry point
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
├── Makefile              # Build automation
└── README.md             # This file
```

## 📋 Prerequisites

### System Requirements
- Python 3.9 or higher
- 2GB RAM minimum (4GB recommended)
- 1GB free disk space
- Linux/macOS/Windows with WSL2
- Stable internet connection

### API Requirements
- **Telegram Bot Token** (required) - [Create bot with @BotFather](https://t.me/botfather)
- **Bybit API Key & Secret** (required) - [Generate at Bybit](https://www.bybit.com/app/user/api-management)
- **OpenAI API Key** (optional) - For AI features
- **Social Media APIs** (optional) - For sentiment analysis

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/bybit-telegram-bot.git
cd bybit-telegram-bot
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use any text editor
```

### 5. Verify Installation

```bash
# Test Bybit connection
python check_bybit_setup.py

# Validate configuration
python -c "from utils.config_validator import validate_configuration; validate_configuration()"
```

## ⚙️ Configuration

### Essential Environment Variables

```bash
# Core Bot Configuration (REQUIRED)
TELEGRAM_TOKEN=your_telegram_bot_token
BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret
USE_TESTNET=false  # Set to true for testing

# AI Features (OPTIONAL)
OPENAI_API_KEY=your_openai_api_key
LLM_PROVIDER=openai  # or "stub" to disable

# Mirror Trading (OPTIONAL)
BYBIT_API_KEY_2=secondary_account_api_key
BYBIT_API_SECRET_2=secondary_account_api_secret

# Advanced Settings
LOG_LEVEL=INFO
PERSISTENCE_FILE=bybit_bot_dashboard_v4.1_enhanced.pkl
```

### Bybit API Permissions

Ensure your Bybit API key has the following permissions:
- ✅ Spot Trading
- ✅ Derivatives Trading
- ✅ Read Account Info
- ❌ Withdrawal (keep disabled for security)

### Social Media APIs (Optional)

For sentiment analysis features:

```bash
# Reddit
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_secret

# Twitter
TWITTER_BEARER_TOKEN=your_twitter_token

# YouTube
YOUTUBE_API_KEY=your_youtube_api_key
```

## 🎯 Usage

### Starting the Bot

```bash
# Direct execution
python main.py

# Using auto-restart script (recommended)
./run_main.sh
```

### First Time Setup

1. **Start a conversation** with your bot on Telegram
2. **Send `/start`** to initialize
3. **Verify dashboard** appears with your account info
4. **Test with small position** before full trading

### Basic Trading Flow

1. **Click "⚡ New Trade"** or send `/trade`
2. **Enter symbol** (e.g., BTCUSDT)
3. **Select direction** (Long/Short)
4. **Choose approach** (Fast/Conservative/GGShot)
5. **Set parameters** (entry, TP, SL, leverage, margin)
6. **Confirm and execute**

## 📊 Trading Approaches

### Conservative Approach 🛡️

The bot's primary trading approach with sophisticated order management:
- **Entry**: Multiple limit orders (up to 3) for gradual position building
- **Take Profits**: 4 levels with 85%, 5%, 5%, 5% distribution
- **Stop Loss**: Single SL covering entire position
- **Monitoring**: Enhanced TP/SL system with 5-second checks
- **Use Case**: Swing trades, trend following, risk management

### GGShot Approach 📸

Screenshot-based trading for quick signal execution:
- **Upload screenshot** of trade setup (TradingView, etc.)
- **AI extracts** symbol, direction, entry, TP, and SL automatically
- **Executes with** Conservative approach internally
- **Use Case**: Social media signals, quick entry, mobile trading

### Position Merge Logic

Merging existing positions follows these rules:

**For LONG positions:**
- New TP > Old TP = More aggressive ✅
- New SL < Old SL = Safer ✅

**For SHORT positions:**
- New TP < Old TP = More aggressive ✅
- New SL > Old SL = Safer ✅

If BOTH conditions met → Update trigger prices
Otherwise → Keep original prices, increase size only

## 📱 Commands

### Trading Commands
- `/start` or `/dashboard` - Show main dashboard
- `/trade` - Start new trade setup
- `/emergency` - Emergency close all positions (with confirmation)

### Position Management
- `/positions` - List all open positions
- `/closeposition` - Close individual positions (with confirmation)
- `/rebalancer` - Check auto-rebalancer status
- `/rebalancer_start` - Start auto-rebalancer
- `/rebalancer_stop` - Stop auto-rebalancer

### Information Commands
- `/help` - Show help menu
- `/stats` - View trading statistics
- `/alerts` - Manage price alerts

### Utility Commands
- `/cleanup_monitors` - Clean duplicate monitors
- `/check_mode` - Check position mode (hedge/one-way)
- `/hedge_mode` - Enable hedge mode
- `/one_way_mode` - Enable one-way mode

## 🔧 Advanced Features

### 1. Auto-Rebalancer

Automatically adjusts position sizes based on approach:

```bash
# Check status
/rebalancer

# Start/stop
/rebalancer_start
/rebalancer_stop
```

Triggers on:
- New positions (Fast approach)
- Position merges (both approaches)
- Filled limit orders

### 2. Mirror Trading

Synchronize trades to secondary account:

```bash
# Configure in .env
BYBIT_API_KEY_2=secondary_api_key
BYBIT_API_SECRET_2=secondary_api_secret

# Trades automatically mirror
# Separate monitoring for each account
```

### 3. Alert System

Set price alerts for any symbol:

```bash
# Via command
/alerts

# Select alert type:
- Price crosses above/below
- Position P&L thresholds
- Volatility alerts
- Custom conditions
```

### 4. AI Market Analysis

Get AI-powered insights:

```bash
# Requires OpenAI API key
# Automatic analysis in dashboard
# Includes:
- Market regime detection
- Trend analysis
- Risk assessment
- Trade recommendations
```

### 5. Social Media Sentiment

Automated sentiment collection:

```bash
# Configure API keys in .env
# 6-hour collection cycles
# Platforms:
- Reddit (crypto subreddits)
- Twitter (crypto hashtags)
- YouTube (crypto channels)
- Discord (optional)
```

### 6. Performance Analytics

Comprehensive trading metrics:

```bash
# Access via dashboard
- Win rate & profit factor
- Sharpe ratio
- Maximum drawdown
- Daily/weekly/monthly P&L
- Per-approach statistics
```

## 🔍 Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test
pytest test_emergency_dry_run.py

# Run with coverage
pytest --cov=. --cov-report=html
```

### Debugging Tools

```bash
# Test dashboard generation
python test_enhanced_dashboard.py

# Debug order placement
python debug_orders.py

# Check position counts
python check_positions_count.py

# Verify P&L calculations
python verify_pnl_calculations.py
```

### Code Style

The project follows PEP 8 with these conventions:
- Async functions for all I/O operations
- Type hints where beneficial
- Comprehensive docstrings
- Error handling with context

### Adding New Features

1. **Create feature branch**
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Follow architecture patterns**
   - Handlers in `handlers/`
   - Business logic in `execution/`
   - Utilities in `utils/`

3. **Add tests**
   - Unit tests for logic
   - Integration tests for API calls

4. **Update documentation**
   - Add to README.md
   - Update CLAUDE.md if needed

## 🐛 Troubleshooting

### Common Issues

#### 1. Bot Not Responding
```bash
# Check bot is running
ps aux | grep main.py

# Check logs
tail -f trading_bot.log

# Restart bot
./run_main.sh
```

#### 2. API Connection Errors
```bash
# Verify API credentials
python check_bybit_setup.py

# Check network connectivity
ping api.bybit.com

# Review rate limits in logs
```

#### 3. Monitor Issues
```bash
# Too many monitors error
python cleanup_monitors.py

# Check monitor status
python check_positions_count.py

# Force cleanup
python cleanup_stuck_monitors.py
```

#### 4. Order Failures
```bash
# Debug orders
python debug_orders.py

# Check decimal precision
# Verify balance
# Review API permissions
```

#### 5. Message Too Long Errors
```bash
# Automatic handling for position lists
# Ultra-compact format activates for >20 positions
# Shows only symbol and P&L with account indicators
# (M) = Main account, (🔄) = Mirror account
```

### Log Files

- `trading_bot.log` - Main application logs
- `bot_output.log` - Console output
- `failed_alerts.json` - Failed alert queue

### Getting Help

1. **Check logs** for error messages
2. **Run diagnostics** with provided scripts
3. **Review documentation** in `/docs`
4. **Enable debug logging**: `LOG_LEVEL=DEBUG`

## 🔒 Security

### Best Practices

1. **API Key Security**
   - Never commit `.env` files
   - Use read-only keys when possible
   - Disable withdrawal permissions
   - Rotate keys regularly

2. **Bot Security**
   - Use strong Telegram bot token
   - Limit bot to private chats
   - Enable PIN for emergency commands
   - Regular security audits

3. **Server Security**
   - Run on secure VPS
   - Use firewall rules
   - Keep Python updated
   - Monitor access logs

### Security Features

- **Order Prefix Protection**: BOT_ prefix prevents external interference
- **Two-Factor Confirmation**: Critical actions require confirmation
- **Rate Limiting**: Built-in protection against spam
- **Circuit Breakers**: Automatic service disable on failures

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository**
2. **Create feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit changes** (`git commit -m 'Add amazing feature'`)
4. **Push to branch** (`git push origin feature/amazing-feature`)
5. **Open Pull Request**

### Contribution Guidelines

- Follow existing code style
- Add tests for new features
- Update documentation
- Keep commits atomic
- Write clear commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram bot framework
- [pybit](https://github.com/bybit-exchange/pybit) - Bybit API wrapper
- [OpenAI](https://openai.com/) - AI integration
- All contributors and testers

## 📞 Support

- **Documentation**: See `/docs` folder
- **Issues**: GitHub Issues
- **Updates**: Watch this repository

---

**Disclaimer**: This bot is for educational purposes. Cryptocurrency trading carries significant risk. Always do your own research and trade responsibly.