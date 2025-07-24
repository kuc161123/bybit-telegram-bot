# Breakeven Stop Loss and TP Rebalancing Fixes

## Date: 2025-06-29

## Issues Fixed

### 1. Stop Loss Not Moving to Breakeven After TP1 Hit

**Problem**: When a conservative position's TP1 was hit, the system attempted to move the stop loss to breakeven + fees on every monitoring cycle, but it wasn't persisting the state properly.

**Root Cause**: The monitoring loop was using a local variable `sl_moved_to_breakeven` instead of checking the persisted state in `chat_data`.

**Fix Applied**:
- Updated `monitor.py` to check `chat_data.get("sl_moved_to_breakeven", False)` instead of the local variable
- Removed unnecessary local variable assignments
- Added better error logging when SL movement fails
- Applied fix for both main and mirror accounts

**Files Modified**:
- `execution/monitor.py` - Lines 2334-2346, 2369-2386, 2861, 2939-2942

### 2. Automatic Rebalancing When TPs Are Hit

**Problem**: When a take profit order was hit, the remaining TP orders were not being rebalanced to match the new position size.

**Solution Implemented**:
- Added new `rebalance_on_tp_hit()` method to `ConservativeRebalancer` class
- Rebalancing logic distributes remaining position equally among remaining TPs:
  - After TP1 hit: TP2/3/4 get 33.33% each
  - After TP2 hit: TP3/4 get 50% each  
  - After TP3 hit: TP4 gets 100%
- Stop loss always adjusted to 100% of remaining position

**Features Added**:
- Automatic rebalancing triggers when any TP (1-4) is hit
- Works for both main and mirror accounts
- Preserves existing TP prices while adjusting quantities
- Sends rebalancing alerts to main account only
- Handles edge cases like position closure

**Files Modified**:
- `execution/conservative_rebalancer.py` - Added `rebalance_on_tp_hit()` method and updated mirror account method
- `execution/monitor.py` - Added rebalancing calls in `check_conservative_other_tp_hits()` and mirror TP detection

## How It Works

### Breakeven Logic
1. When TP1 is detected as filled, the system calculates breakeven price including:
   - Entry price
   - Trading fees (0.12% total - 0.06% entry + 0.06% exit)
   - Safety margin of 2 ticks
2. The stop loss order is cancelled and replaced at the new breakeven price
3. The state is saved in `chat_data["sl_moved_to_breakeven"] = True`
4. Future monitoring cycles check this flag to avoid repeated attempts

### Rebalancing Logic
1. When any TP order fills, the monitor detects it
2. The rebalancer is triggered with the TP number that was hit
3. Current position size is fetched from Bybit
4. Remaining TPs are cancelled and replaced with new quantities
5. Stop loss is adjusted to match full remaining position
6. All changes are logged and alerts sent (main account only)

## Testing Recommendations

1. **Test Breakeven Movement**:
   - Place a conservative trade
   - Wait for TP1 to hit
   - Verify SL moves to breakeven + fees
   - Check logs confirm no repeated attempts

2. **Test TP Rebalancing**:
   - Place a conservative trade with 4 TPs
   - Let each TP hit sequentially
   - Verify remaining orders are rebalanced correctly
   - Check both main and mirror accounts

3. **Edge Cases to Test**:
   - Position manually closed before rebalancing
   - Multiple TPs hit simultaneously
   - Network issues during rebalancing
   - Mirror account without main account position

## Monitoring Commands

Use these commands to verify the fixes:
```bash
# Check current positions and SL status
python check_stop_loss_status.py

# Monitor logs for breakeven movements
grep "Moving SL to breakeven" trading_bot.log | tail -20

# Check rebalancing activity
grep "Conservative rebalance" trading_bot.log | tail -20

# Verify mirror account activity
grep "MIRROR.*rebalance" trading_bot.log | tail -20
```

## Future Improvements

1. Add configuration for breakeven offset (currently 2 ticks)
2. Allow custom TP redistribution percentages
3. Add manual rebalancing command
4. Enhanced error recovery for failed rebalancing