# Future Trades Setup - Quick Reference

## ✅ Pre-Trade Checklist

1. **Bot Running**: 
   ```bash
   ps aux | grep main.py
   # If not running: ./run_bot.sh
   ```

2. **Check Dashboard Works**:
   ```
   /dashboard
   ```

## 🎯 Opening New Trades (For Notifications)

### Method 1: Conservative (With Limit Orders)
```
/trade
→ Enter symbol (e.g., BTCUSDT)
→ Choose Buy/Sell
→ Choose "Conservative"
→ Enter limit prices (3 levels)
→ Enter TP prices (4 levels)
→ Enter SL price
→ Set leverage
→ Set margin
→ Confirm execution
```

### Method 2: Fast (Market Order)
```
/trade
→ Enter symbol
→ Choose Buy/Sell  
→ Choose "Fast"
→ Enter TP price
→ Enter SL price
→ Set leverage
→ Set margin
→ Confirm execution
```

### Method 3: GGShot (Screenshot)
```
/trade
→ Choose "GGShot"
→ Upload screenshot
→ Review extracted values
→ Choose approach (Fast/Conservative)
→ Confirm execution
```

## 📱 Notifications You'll Receive

### Conservative Approach:
- **Limit Fill**: "🎯 LIMIT ORDER FILLED - Limit 2/3 Filled @ $45,000"
- **TP1 Hit**: "✅ TAKE PROFIT HIT! - TP1 Hit (70% Exit)"
- **TP2/3/4 Hit**: Individual alerts for each
- **SL Hit**: "🛡️ STOP LOSS HIT - Loss: -$50.25"
- **Position Closed**: "📊 POSITION CLOSED - Total P&L: +$580.25"

### Fast Approach:
- **Entry**: "⚡ FAST TRADE EXECUTED"
- **TP Hit**: "✅ TAKE PROFIT HIT!"
- **SL Hit**: "🛡️ STOP LOSS HIT"
- **Position Closed**: "📊 POSITION CLOSED"

## 🔍 Verify Monitoring After Trade

Always run after opening a position:
```
/dashboard
```

Look for:
- ✅ Your symbol appears
- ✅ Shows "Monitoring: ACTIVE"
- ✅ Correct approach (Conservative/Fast)

## ⚡ Quick Commands

- **Check positions**: `/dashboard`
- **List monitors**: `/list_monitors`
- **Clean monitors**: `/cleanup_monitors`
- **Open trade**: `/trade`

## 🚨 Important Rules

1. **ALWAYS** use `/trade` to open positions
2. **NEVER** place orders manually on Bybit
3. **NEVER** modify orders outside the bot
4. **KEEP** bot running 24/7

## 💡 Pro Tips

### For Conservative Trades:
- Space limit orders evenly (e.g., -0.5%, -1%, -1.5% from current)
- Set TP1 at 70% (standard)
- TP2/3/4 at higher levels for runners
- SL at a reasonable stop (2-3% typically)

### For Fast Trades:
- Single TP at your target
- SL at your risk level
- Check R:R ratio before confirming

## 🔧 Troubleshooting

**No notifications?**
1. Check `/dashboard` - is monitoring active?
2. Check logs: `tail -f trading_bot.log | grep YOUR_SYMBOL`
3. Ensure position exists on Bybit

**Bot crashed?**
```bash
./run_bot.sh  # Auto-restarts on crash
```

**Need help?**
- Logs: `tail -f trading_bot.log`
- Clean monitors: `/cleanup_monitors`
- Restart: `./run_bot.sh`

---

Remember: The bot can only track orders it places itself!