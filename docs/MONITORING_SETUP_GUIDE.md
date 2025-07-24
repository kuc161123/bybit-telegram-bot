# Complete Monitoring Setup Guide for Trade Notifications

## Overview
This guide ensures you receive notifications for all order fills (market, limit, TP, SL) for future trades.

## 1. Pre-Trade Setup

### Verify Bot is Running
```bash
# Check if bot is running
ps aux | grep main.py

# If not running, start it:
./run_bot.sh
# or
python main.py
```

### Check Configuration
Ensure these are set in your `.env` file:
```
TELEGRAM_TOKEN=your_bot_token
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
USE_TESTNET=false
```

## 2. Opening Trades for Proper Monitoring

### Method 1: Manual Trade Setup (Recommended)
1. Start trade setup:
   ```
   /trade
   ```

2. Follow the conversation flow:
   - Enter symbol (e.g., GALAUSDT)
   - Choose side (Buy/Sell)
   - Choose approach:
     - **Conservative**: 3 limit orders + 4 TPs + 1 SL
     - **Fast**: 1 market order + 1 TP + 1 SL
   - Enter prices and parameters
   - Confirm execution

### Method 2: GGShot (Screenshot Analysis)
1. Take screenshot of trade setup
2. Send to bot with:
   ```
   /trade
   ```
3. Choose GGShot approach
4. Upload screenshot
5. Verify extracted parameters
6. Execute trade

## 3. Monitoring Features by Approach

### Conservative Approach Notifications
- **Limit Order Fills**: Alert when each limit order fills
- **TP1 Hit (Early)**: Alert if TP1 hits before limits fill (cancels all orders)
- **TP1 Hit (With Fills)**: Alert if TP1 hits after some limits fill (cancels remaining limits)
- **TP2/3/4 Hits**: Individual alerts for each TP
- **SL Hit**: Alert with total loss
- **Position Closed**: Summary with final P&L

### Fast Approach Notifications
- **Market Order Fill**: Immediate execution confirmation
- **TP Hit**: Alert when take profit is reached
- **SL Hit**: Alert when stop loss is triggered
- **Position Closed**: Summary with final P&L

## 4. Monitoring Commands

### Check Active Monitors
```
/dashboard
```
Shows all actively monitored positions

### List All Monitors
```
/list_monitors
```
Detailed list of all monitoring tasks

### Clean Up Stuck Monitors
```
/cleanup_monitors
```
Removes duplicate or stuck monitors

## 5. Troubleshooting

### Issue: No Notifications
1. Check monitor is active:
   ```
   /dashboard
   ```

2. Verify position exists:
   - Check Bybit app/website
   - Confirm position is open

3. Check bot logs:
   ```
   tail -f trading_bot.log | grep GALAUSDT
   ```

### Issue: Duplicate Notifications
1. Clean up monitors:
   ```
   /cleanup_monitors
   ```

2. Restart specific monitor:
   - Close position manually
   - Re-open through bot

### Issue: Bot Restart Lost Monitoring
After bot restart, existing positions need re-initialization:
1. Bot will auto-detect open positions
2. Creates monitors for bot-placed positions
3. Manual positions won't have limit order tracking

## 6. Best Practices

### For Reliable Notifications
1. **Always use the bot to open positions**
2. **Don't modify orders manually on exchange**
3. **Keep bot running continuously**
4. **Use /dashboard to verify monitoring**

### For Conservative Trades
1. **Set meaningful limit levels** (not too far from market)
2. **Use proper position sizing** (divide margin by 3 for limits)
3. **Set realistic TP levels** (TP1 at 70% is standard)

### For Fast Trades
1. **Ensure TP/SL are at reasonable distances**
2. **Check risk/reward ratio before confirming**
3. **Monitor for slippage on market orders**

## 7. Alert Types You'll Receive

### Limit Order Filled (Conservative Only)
```
🎯 LIMIT ORDER FILLED

📊 BTCUSDT LONG - Conservative
💰 Limit 2/3 Filled

📍 Fill Price: $45,000.00
📦 Size: 0.0333 BTC
⏱️ Time: 10:30:45

📈 Progress: 2 of 3 limits filled
```

### TP Hit Alerts
```
✅ TAKE PROFIT HIT!

📊 BTCUSDT LONG
🎯 TP1 Hit (70% Exit)

💵 Entry: $44,000
📈 Exit: $46,000
💰 P&L: +$200.50
📊 R:R Achieved: 2.5:1

🔄 Remaining: TP2, TP3, TP4 active
```

### Position Closed Summary
```
📊 POSITION CLOSED

BTCUSDT LONG - Conservative
⏱️ Duration: 4h 23m

💰 Total P&L: +$580.25 (+3.2%)
📈 Win Rate Impact: 85% → 86%

Entry Fills: 3/3 limits @ avg $44,500
Exit: TP1 + TP3 hit
```

## 8. Advanced Monitoring Features

### Stop Loss Management
- **Auto-move to breakeven** after TP1 hit
- **Includes fees** in breakeven calculation (0.12%)
- **Safety margin** of 2 ticks beyond breakeven

### Position Merge Detection
- Automatically detects same symbol/side positions
- Merges orders to stay within Bybit limits
- Maintains optimal TP/SL levels

### Performance Tracking
- Real-time P&L updates
- Trade history recording
- Win rate tracking
- Performance analytics

## 9. Environment-Specific Setup

### For Production
```bash
# Ensure production settings
USE_TESTNET=false

# Run with auto-restart
./run_bot.sh
```

### For Testing
```bash
# Use testnet first
USE_TESTNET=true

# Test monitoring
python test_monitor_detection.py
```

## 10. Quick Start Checklist

- [ ] Bot is running (`ps aux | grep main.py`)
- [ ] Environment configured (`.env` file)
- [ ] Telegram connected (`/start` works)
- [ ] Bybit API connected (`/dashboard` shows balance)
- [ ] Open trades through bot only
- [ ] Verify monitoring after trade (`/dashboard`)
- [ ] Keep bot running 24/7

## Support

If you need help:
1. Check logs: `tail -f trading_bot.log`
2. Run diagnostics: `python check_positions_count.py`
3. Clean monitors: `/cleanup_monitors`
4. Restart bot: `./run_bot.sh`

Remember: The bot can only track and notify for orders it places itself!