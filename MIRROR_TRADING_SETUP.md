# Mirror Trading Setup - Second Bybit Account

## Overview
This document explains the mirror trading functionality that has been added to replicate trades on a second Bybit account.

## What Was Added

### 1. New Module: `execution/mirror_trader.py`
- Completely separate module that operates as a "sidecar"
- Does NOT modify any existing trade logic
- Handles all mirror trading operations independently
- Fails gracefully without affecting primary account

### 2. Environment Variables
Added to `.env` file:
```
ENABLE_MIRROR_TRADING=true
BYBIT_API_KEY_2=gGihfIk8RozZ1WRyRI
BYBIT_API_SECRET_2=Kyp1mBXFRFpBlsTgoyJuWARDXoJAlEFhQ7xd
```

### 3. Configuration Updates
Added to `config/settings.py`:
- `ENABLE_MIRROR_TRADING` - Toggle for mirror trading
- `BYBIT_API_KEY_2` - Second account API key
- `BYBIT_API_SECRET_2` - Second account API secret

### 4. Trade Execution Hooks
Added mirror trading calls in `execution/trader.py`:
- **Fast Approach**: Mirrors market, TP, and SL orders
- **Conservative Approach**: Mirrors all limit orders, TPs, and SL
- **GGShot Approach**: Mirrors market entry, limit orders, TPs, and SL

## How It Works

1. When you execute any trade through the bot, it follows the normal flow
2. After each order is successfully placed on the primary account:
   - The mirror trader is called with the same parameters
   - Orders are placed on the second account
   - Any failures are logged but don't affect the primary trade

3. Order IDs on the mirror account have "_MIRROR" suffix for identification

## Important Notes

### What Was NOT Changed
- ✅ All existing trading logic remains untouched
- ✅ Primary account operations are unaffected
- ✅ Bot architecture and flow remain the same
- ✅ User interface and commands unchanged

### Error Handling
- Mirror trading failures are logged but ignored
- Primary trades continue even if mirror trades fail
- Each mirror operation is wrapped in try/catch blocks

### Performance
- Mirror trades execute asynchronously
- Minimal impact on primary trade execution speed
- Both accounts receive orders nearly simultaneously

## Enabling/Disabling

### To Enable Mirror Trading:
Set in `.env` file:
```
ENABLE_MIRROR_TRADING=true
```

### To Disable Mirror Trading:
Set in `.env` file:
```
ENABLE_MIRROR_TRADING=false
```

## Monitoring

Look for these log messages:
- `✅ MIRROR: Market order placed: XXXXXXXX...` - Successful mirror order
- `❌ MIRROR: Failed to place order: [error]` - Failed mirror order
- `✅ Mirror trading client initialized successfully` - Client ready

## Testing Recommendations

1. Start with a small test trade to verify mirror functionality
2. Check both Bybit accounts to confirm matching positions
3. Monitor logs for any mirror trading errors
4. Test with different trading approaches (Fast/Conservative/GGShot)

## Troubleshooting

### Mirror trades not executing:
1. Check `ENABLE_MIRROR_TRADING=true` in `.env`
2. Verify API credentials are correct
3. Check logs for initialization errors
4. Ensure second account has sufficient balance

### Position differences between accounts:
- Check if second account has different position limits
- Verify both accounts have same leverage settings
- Check for any order rejections in logs

## Security Note
The second account API credentials are stored in the `.env` file. Ensure this file:
- Is not committed to version control
- Has appropriate file permissions
- Is backed up securely