# 📚 BYBIT TELEGRAM TRADING BOT - COMPLETE USER GUIDE

> Last Updated: June 25, 2025
> Version: 4.1 Enhanced

## 📋 TABLE OF CONTENTS

1. [🚀 Quick Start Guide](#-quick-start-guide)
2. [⚡ Trading Features](#-trading-features)
3. [📊 Dashboard & Analytics](#-dashboard--analytics)
4. [🔔 Alert System](#-alert-system)
5. [📱 User Interface](#-user-interface)
6. [⚙️ Configuration](#️-configuration)
7. [🤖 AI Features](#-ai-features)
8. [🛡️ Risk Management](#️-risk-management)
9. [📋 Command Reference](#-command-reference)
10. [🔧 Troubleshooting](#-troubleshooting)
11. [💡 Advanced Features](#-advanced-features)
12. [❓ FAQ](#-faq)

---

## 🚀 QUICK START GUIDE

### First Time Setup

1. **Start the Bot**
   ```
   Send /start to your bot
   ```

2. **Access Main Dashboard**
   - You'll see the main dashboard with:
     - Account balance
     - Active positions
     - Performance metrics
     - Quick action buttons

3. **Place Your First Trade**
   - Click "📈 New Trade" button
   - Follow the step-by-step wizard
   - Or upload a screenshot with "📸 GGShot"

### Essential Commands
- `/start` - Main dashboard
- `/trade` - Start new trade
- `/help` - This guide
- `/alerts` - Manage alerts

---

## ⚡ TRADING FEATURES

### Trading Approaches Explained

#### 1. ⚡ Fast Market Approach
**Best for**: Quick scalps, momentum trades, news trading

**How it works**:
- Places one market order immediately
- Sets one take profit (TP) at your target
- Sets one stop loss (SL) for protection
- Entire position closes at once

**Example**:
```
Buy 1000 USDT of BTCUSDT
Entry: Market price
TP: +2% from entry
SL: -1% from entry
```

#### 2. 🛡️ Conservative Limits Approach
**Best for**: Range trading, accumulation, risk distribution

**How it works**:
- Places 3 limit orders (33.33% each) below/above market
- Sets 4 take profit levels:
  - TP1: 70% of position (main target)
  - TP2-4: 10% each (runners)
- One stop loss for entire position
- Smart TP1 logic: Cancels unfilled limits when TP1 hits

**Example**:
```
Buy 1000 USDT of BTCUSDT
Limit 1: 69,500 (333 USDT)
Limit 2: 69,000 (333 USDT)
Limit 3: 68,500 (334 USDT)
TP1: 71,000 (70% = 700 USDT)
TP2: 72,000 (10% = 100 USDT)
TP3: 73,000 (10% = 100 USDT)
TP4: 74,000 (10% = 100 USDT)
SL: 68,000 (all)
```

#### 3. 📸 GGShot Screenshot Trading
**Best for**: TradingView users, quick setup, visual traders

**How it works**:
1. Take screenshot of your TradingView chart
2. Upload to bot
3. AI analyzes and extracts:
   - Symbol
   - Entry levels
   - TP/SL levels
   - Suggested approach
4. Confirm and execute

**Supported formats**: PNG, JPG, JPEG
**Best practices**: 
- Clear, uncluttered charts
- Visible price levels
- Good lighting/contrast

### Trading Flow Step-by-Step

#### Manual Trading
1. **Start Trade**: Click "📈 New Trade" or send `/trade`

2. **Enter Symbol**: 
   - Type symbol (e.g., "BTCUSDT")
   - No need for pairs format
   - Bot validates automatically

3. **Choose Direction**:
   - 🟢 BUY (Long)
   - 🔴 SELL (Short)

4. **Select Approach**:
   - ⚡ Fast Market
   - 🛡️ Conservative Limits
   - 📸 Upload Screenshot (GGShot)

5. **Set Prices** (varies by approach):
   - Entry price(s)
   - Take profit level(s)
   - Stop loss

6. **Risk Parameters**:
   - Leverage (1x-100x)
   - Margin (fixed USDT or % of account)

7. **Review & Execute**:
   - Check all parameters
   - Confirm execution
   - Monitor position

#### GGShot Trading
1. Click "📸 GGShot" or select in trade flow
2. Upload TradingView screenshot
3. AI analyzes (10-20 seconds)
4. Review extracted parameters
5. Adjust if needed
6. Execute trade

### Position Monitoring

**Automatic Monitoring Features**:
- Real-time P&L tracking
- Position status updates every 10 seconds
- Automatic TP/SL management
- Alert notifications
- Performance tracking

**Monitor Lifecycle**:
1. Created after trade execution
2. Runs continuously while position open
3. Handles partial fills and updates
4. Closes when position fully closed
5. Maximum lifetime: 24 hours

---

## 📊 DASHBOARD & ANALYTICS

### Main Dashboard Components

#### Account Overview
```
💰 Balance: 10,000 USDT
📊 Available: 8,500 USDT
📈 Active Positions: 3
💵 Unrealized PnL: +125.50 USDT
```

#### Position Summary
For each position:
- Symbol & Side (BTCUSDT LONG)
- Size & Margin
- Entry & Current Price
- P&L ($ and %)
- Risk % of account

#### Performance Metrics
- **Win Rate**: Success percentage
- **Total Trades**: All time count
- **Net P&L**: Total profit/loss
- **Profit Factor**: Gross profit/loss ratio
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough
- **Recovery Factor**: Profit/drawdown ratio

### Statistics Menu

Access via "📊 Statistics" button:

1. **📈 Detailed Stats**
   - Trade breakdown by approach
   - Win/loss distribution
   - Average trade metrics
   - Best/worst trades

2. **📊 Performance Chart**
   - Visual P&L history
   - Cumulative returns
   - Drawdown periods

3. **⚡ Fast Approach Stats**
   - Fast market specific metrics
   - Success rate
   - Average hold time

4. **🛡️ Conservative Stats**
   - Conservative approach metrics
   - Limit fill rates
   - TP level analysis

5. **📤 Export Stats**
   - Download CSV/JSON
   - Full trade history
   - Performance report

### Dashboard Features

**Auto-Refresh**: Updates every 30s when positions active
**Manual Refresh**: Click "🔄 Refresh" anytime
**Quick Actions**: One-tap access to common tasks
**Mobile Optimized**: Fits all screen sizes

---

## 🔔 ALERT SYSTEM

### Alert Types

#### 1. Price Alerts
- **Above Price**: Notifies when price exceeds level
- **Below Price**: Notifies when price drops below
- **Cross Price**: Triggers on any cross
- **% Change**: Percentage movement alerts

#### 2. Position Alerts
- **Profit Target**: $ or % profit reached
- **Loss Limit**: $ or % loss reached
- **Near TP**: Approaching take profit (90%)
- **Near SL**: Approaching stop loss (90%)
- **Breakeven**: Position at breakeven

#### 3. Risk Alerts
- **High Leverage**: >50x leverage warning
- **Large Position**: >10% of account
- **Drawdown**: Account down >20%
- **Correlation**: Multiple similar positions

#### 4. Market Alerts
- **Volatility Spike**: Sudden price movement
- **Volume Surge**: Unusual volume detected
- **Funding Rate**: High funding costs
- **Trend Change**: Market regime shift

### Alert Management

**Create Alert**:
1. Click "🔔 Alerts" → "➕ Create Alert"
2. Select alert type
3. Configure parameters
4. Set priority (High/Medium/Low)
5. Enable/disable as needed

**Alert Features**:
- Mute hours (e.g., 23:00-07:00)
- Priority filtering
- One-time vs recurring
- Custom messages
- Multi-condition alerts

### Daily Reports

**Configuration**:
- Set preferred time (e.g., 9:00 AM)
- Choose included metrics
- Enable/disable sections

**Report Contents**:
- Trading summary
- P&L breakdown
- Position analysis
- Win rate trends
- Risk metrics
- Recommendations

---

## 📱 USER INTERFACE

### Mobile Optimization

**Touch-Friendly Design**:
- Large tap targets (44px minimum)
- Spaced buttons to prevent mis-taps
- Swipe gestures for navigation
- Responsive layouts

**Quick Selections**:
- Popular symbols shortcuts
- Common leverage presets (5x, 10x, 25x)
- Margin % quick picks (1%, 2%, 5%)
- Price increment buttons

### Navigation Features

**Back Button**: Available in all conversation steps
**Cancel**: Exit trade setup anytime
**Help**: Context-sensitive help
**Home**: Return to dashboard

### Input Validation

**Smart Validation**:
- Symbol existence check
- Price tick size compliance
- Minimum order validation
- Leverage limits
- Balance sufficiency

**Error Messages**:
- Clear, actionable feedback
- Suggested corrections
- Links to help sections

---

## ⚙️ CONFIGURATION

### Trading Settings

#### Position Modes
```
/hedge_mode - Enable hedge mode
/one_way_mode - Enable one-way mode
/check_mode - Check current mode
```

**Hedge Mode**: Hold both long and short positions
**One-Way Mode**: One direction per symbol only

#### Default Settings
- Leverage: Set preferred leverage
- Margin: Default margin amount/percentage
- Approach: Preferred trading approach
- Risk: Maximum risk per trade

### Alert Configuration

**Global Settings**:
- Master enable/disable
- Default priority
- Mute hours
- Rate limiting

**Per-Alert Settings**:
- Individual enable/disable
- Custom thresholds
- Notification frequency
- Expiration time

### Account Settings

**API Configuration**:
- Primary Bybit account
- Mirror account (optional)
- Testnet/Mainnet selection

**Display Preferences**:
- Currency display
- Decimal precision
- Time zone
- Language (future)

---

## 🤖 AI FEATURES

### Market Analysis (OpenAI Required)

**AI Insights Include**:
- Market sentiment analysis
- Risk assessment score
- Trade timing suggestions
- Portfolio recommendations
- Trend identification

**Access**: Click "🤖 AI Insights" on dashboard

### Social Sentiment Analysis

**Data Sources**:
- Reddit (crypto subreddits)
- Twitter (crypto influencers)
- YouTube (analysis videos)
- Discord (trading servers)
- News aggregators

**Sentiment Metrics**:
- Bullish/Bearish ratio
- FOMO indicator
- Fear & Greed index
- Social volume
- Trending topics

**Update Cycle**: Every 6 hours

### GGShot AI Analysis

**Multi-Model Processing**:
- Parallel analysis for accuracy
- Confidence scoring
- Error detection
- Validation checks

**Extracted Data**:
- Symbol identification
- Support/resistance levels
- Entry/exit points
- Risk/reward ratios
- Suggested approach

---

## 🛡️ RISK MANAGEMENT

### Position Sizing

**Percentage Method**:
```
Account: 10,000 USDT
Risk: 2%
Margin: 200 USDT
```

**Fixed Amount**:
```
Always trade: 100 USDT
Regardless of account size
```

### Risk Metrics

**Per-Trade Risk**:
- Maximum loss if SL hit
- Percentage of account
- Risk/reward ratio
- Break-even price

**Account Risk**:
- Total exposure
- Correlation risk
- Maximum drawdown
- Recovery requirements

### Safety Features

**Order Validation**:
- Minimum notional checks
- Tick size compliance
- Balance verification
- Leverage limits

**Position Limits**:
- Maximum positions
- Per-symbol limits
- Total exposure cap
- Margin requirements

---

## 📋 COMMAND REFERENCE

### Core Commands
| Command | Description |
|---------|-------------|
| `/start` | Open main dashboard |
| `/dashboard` | Quick dashboard access |
| `/trade` | Start new trade |
| `/help` | Show this guide |

### Trading Commands
| Command | Description |
|---------|-------------|
| `/positions` | View all positions |
| `/close` | Close position menu |
| `/pnl` | P&L summary |
| `/stats` | Trading statistics |

### Configuration Commands
| Command | Description |
|---------|-------------|
| `/settings` | Bot settings |
| `/hedge_mode` | Enable hedge mode |
| `/one_way_mode` | Enable one-way mode |
| `/check_mode` | Check position mode |

### Alert Commands
| Command | Description |
|---------|-------------|
| `/alerts` | Alert management |
| `/mute` | Mute alerts temporarily |
| `/unmute` | Unmute alerts |
| `/testreport` | Generate test report |

### Maintenance Commands
| Command | Description |
|---------|-------------|
| `/cleanup_monitors` | Fix stuck monitors |
| `/backup` | Backup bot data |
| `/restore` | Restore from backup |
| `/logs` | View recent logs |

---

## 🔧 TROUBLESHOOTING

### Common Issues

#### "Too Many Monitors" Error
**Cause**: Duplicate or stuck monitors
**Solution**: Run `/cleanup_monitors`

#### Orders Not Placing
**Check**:
1. Sufficient balance
2. Correct position mode
3. Valid symbol
4. API permissions

#### Bot Not Responding
**Try**:
1. Check bot status with `/start`
2. Verify internet connection
3. Restart bot if needed
4. Check logs for errors

#### Incorrect P&L
**Verify**:
1. Entry prices correct
2. Fees included
3. Funding costs
4. Currency conversion

### Error Messages

| Error | Meaning | Solution |
|-------|---------|----------|
| "Insufficient balance" | Not enough USDT | Deposit or reduce size |
| "Invalid symbol" | Symbol not found | Check spelling |
| "Below minimum" | Order too small | Increase size |
| "Connection error" | API issue | Wait and retry |

### Performance Issues

**Slow Response**:
- Check internet speed
- Reduce active monitors
- Clear old data
- Restart bot

**Memory Usage**:
- Monitors auto-cleanup after 24h
- Regular state file maintenance
- Automatic cache clearing

---

## 💡 ADVANCED FEATURES

### Mirror Trading

**Setup**:
1. Add second API keys to .env
2. Enable in settings
3. Configure ratio (e.g., 50%)

**Features**:
- Proportional sizing
- Synchronized execution
- Separate monitoring
- Combined P&L tracking

### Trade Protection

**BOT_ Prefix System**:
- Orders marked with BOT_ prefix
- Protected from cleanup
- Grouped by trade
- Persistent tracking

### Advanced Monitoring

**Multi-Approach Trading**:
- Different approaches per symbol
- Separate monitoring
- Combined analytics
- Risk aggregation

**Position Adoption**:
- Monitors all Bybit positions
- Detects approach from orders
- Preserves external trades
- Unified dashboard

### API Features

**Rate Limiting**:
- 5 calls/second base
- 10 call burst
- Automatic throttling
- Retry with backoff

**Connection Pooling**:
- 300 total connections
- 75 per host
- Keep-alive enabled
- DNS caching

---

## ❓ FAQ

### General Questions

**Q: Is this bot safe to use?**
A: Yes, with proper API permissions (trade only, no withdrawal)

**Q: Can I use testnet?**
A: Yes, set USE_TESTNET=true in .env

**Q: What's the minimum trade size?**
A: Varies by symbol, typically 5-10 USDT

**Q: Can I run multiple instances?**
A: Not recommended, may cause conflicts

### Trading Questions

**Q: Which approach is better?**
A: Depends on market conditions:
- Fast: Quick moves, news
- Conservative: Ranges, accumulation

**Q: Can I change approach mid-trade?**
A: No, complete current trade first

**Q: How does TP1 cancellation work?**
A: If TP1 hits before limits fill, remaining limits cancel

**Q: What happens at 24-hour monitor limit?**
A: Monitor stops, position remains, manual management needed

### Technical Questions

**Q: Why pickle for storage?**
A: Fast serialization for Python objects

**Q: Is my data encrypted?**
A: API keys in .env, state in pickle (add encryption if needed)

**Q: Can I modify the code?**
A: Yes, it's your bot, customize as needed

**Q: How to contribute?**
A: Submit issues/PRs on GitHub

### Troubleshooting Questions

**Q: Bot stopped working after update?**
A: Check breaking changes, update dependencies

**Q: Lost my positions?**
A: Check Bybit directly, bot only monitors

**Q: Alerts not working?**
A: Verify enabled, check mute hours, review thresholds

**Q: GGShot not accurate?**
A: Ensure clear screenshots, good contrast, visible prices

---

## 📞 SUPPORT

### Getting Help
- Use `/help` command
- Check troubleshooting section
- Review error messages
- Check logs for details

### Reporting Issues
- GitHub Issues: Best for bugs
- Include error messages
- Steps to reproduce
- Bot version

### Feature Requests
- GitHub Discussions
- Detailed use case
- Expected behavior
- Priority/impact

---

## 🎯 QUICK TIPS

1. **Start Small**: Test with minimum sizes first
2. **Use Testnet**: Practice without real money
3. **Monitor Actively**: Bot assists, doesn't replace judgment
4. **Set Alerts**: Stay informed of important changes
5. **Regular Backups**: Protect your data
6. **Check Logs**: Understand what's happening
7. **Stay Updated**: Pull latest changes
8. **Risk Management**: Never risk more than you can afford
9. **Learn Approaches**: Master one before trying all
10. **Ask Questions**: Community is here to help

---

## 📈 EXAMPLE WORKFLOWS

### Scalping Workflow
1. Use Fast Market approach
2. Set tight TP (0.5-1%)
3. Set tighter SL (0.3-0.5%)
4. Higher leverage (10-25x)
5. Quick in/out

### Swing Trading Workflow
1. Use Conservative approach
2. Wide limit orders (1-3% gaps)
3. Multiple TP levels (2-10% each)
4. Lower leverage (3-10x)
5. Patient accumulation

### News Trading Workflow
1. Set price alerts around event
2. Use GGShot for quick entry
3. Fast Market approach
4. Wider SL for volatility
5. Take profits quickly

---

## 🚀 GETTING STARTED CHECKLIST

- [ ] Bot token from @BotFather
- [ ] Bybit API keys (trade permissions only)
- [ ] Environment variables configured
- [ ] Bot started successfully
- [ ] Test trade on testnet
- [ ] Understand both approaches
- [ ] Configure your alerts
- [ ] Set risk parameters
- [ ] Practice with small sizes
- [ ] Join community/support

---

*Happy Trading! Remember: Trade responsibly, never invest more than you can afford to lose, and always do your own research.*

---

**Bot Version**: 4.1 Enhanced
**Last Updated**: June 25, 2025
**Documentation Version**: 1.0.0