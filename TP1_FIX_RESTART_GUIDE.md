# TP1 Fix Restart Requirements Guide

## Do I Need to Restart the Bot?

### Short Answer: YES, for 100% certainty

While the fix will partially apply without a restart, **a bot restart is strongly recommended** to ensure the fix is fully active for all positions.

## Why Restart is Recommended

### 1. **Module Loading**
The `enhanced_tp_sl_manager` is loaded as a singleton instance when the bot starts:
```python
enhanced_tp_sl_manager = EnhancedTPSLManager()  # Created at module level
```

### 2. **Code Changes**
The fixes modify core monitoring logic in `enhanced_tp_sl_manager.py`:
- `_identify_filled_tp_order()` - New method
- `_handle_conservative_position_change()` - Modified logic
- `_verify_order_fill_history()` - Enhanced for mirror accounts

### 3. **Python Import Caching**
Python caches imported modules. Without a restart:
- The old code remains in memory
- New monitoring cycles use the old logic
- Only new imports would get the updated code

## What Happens Without Restart?

### ❌ **Will NOT Work:**
- Existing monitoring loops continue with old logic
- TP1 detection remains broken for current positions
- Limit orders won't be cancelled when TP1 hits
- SL won't move to breakeven

### ✅ **Might Work (Partially):**
- If monitors are recreated (position closed and reopened)
- If the module is somehow reloaded (unlikely in production)

## Recommended Steps

### 1. **Apply Fix to Existing Positions**
```bash
python fix_tp1_for_existing_positions.py
```
This script:
- Checks all open positions
- Identifies positions where TP1 was filled
- Sets the `tp1_hit` flag correctly
- Creates a backup before making changes

### 2. **Restart the Bot**
```bash
# Safe shutdown
./kill_bot.sh

# Wait a few seconds
sleep 5

# Start the bot
python main.py
# OR for auto-restart mode:
./scripts/shell/run_main.sh
```

### 3. **Verify the Fix**
After restart, check the logs for:
```
✅ Detected TP1 fill - Order ID: xxxxx...
✅ TP1 hit detected - will trigger breakeven movement and limit order cleanup
🔒 ENHANCED TP1 BREAKEVEN: SYMBOL_SIDE - TP1 has been hit
```

## Timeline After Restart

### Immediate (0-5 seconds):
- New code is loaded into memory
- All monitoring functions use updated logic

### First Monitoring Cycle (5-12 seconds):
- Positions are checked with new TP detection
- TP1 hits are properly identified
- Breakeven and limit order cleanup triggered

### Within 1 minute:
- All positions have been checked at least once
- Any missed TP1 hits are detected and processed
- SL movements and limit cancellations complete

## Alternative: Hot Reload (NOT Recommended)

While Python supports module reloading, it's risky in production:
```python
import importlib
importlib.reload(enhanced_tp_sl_manager)
```

Issues with hot reload:
- Existing references keep old code
- State can become inconsistent
- May cause unexpected errors

## Summary

| Action | Effect | Recommendation |
|--------|--------|----------------|
| No Restart | Fix won't apply to existing monitors | ❌ Not recommended |
| Restart Bot | All monitors use new logic immediately | ✅ **Recommended** |
| Run fix script + Restart | Existing positions fixed + new logic active | ✅ **Best approach** |

## Commands to Run

```bash
# 1. Fix existing positions
python fix_tp1_for_existing_positions.py

# 2. Restart the bot
./kill_bot.sh && sleep 5 && python main.py

# 3. Monitor logs
tail -f trading_bot.log | grep -E "TP1|breakeven|limit.*cancel"
```

## Verification

After restart, the fix is working if you see:
1. "Detected TP1 fill" messages for conservative positions
2. "TP1 hit detected" when TP1 orders fill
3. Limit orders being cancelled after TP1
4. SL moving to breakeven after TP1

## Future Positions

All positions opened after the restart will automatically use the fixed logic. No additional action needed.