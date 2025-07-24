# Conservative Approach Flow Fix

## Issue
The user reported that they could not input values into the conservative approach in the trading bot. The flow was getting stuck and not allowing text input for limit prices.

## Root Causes Found

1. **State Mismatch**: The conversation state constants were defined differently in `handlers/__init__.py` and `handlers/conversation.py`, causing the flow to break.

2. **Incorrect State Returns**: Multiple functions were returning the wrong state:
   - `handle_side_callback` was returning `MARGIN` instead of `APPROACH_SELECTION`
   - `approach_selection_handler` was returning `MARGIN` instead of `APPROACH_SELECTION`
   - `handle_back_callback` had hardcoded `return MARGIN` outside of the if statement

3. **Hardcoded Approach**: Functions were incorrectly setting the trading approach to "conservative" before the user made their selection.

## Fixes Applied

### 1. Fixed State Constants (handlers/conversation.py)
Changed from:
```python
SYMBOL, SIDE, SCREENSHOT_UPLOAD, PRIMARY_ENTRY, LIMIT_ENTRIES, TAKE_PROFITS, STOP_LOSS, LEVERAGE, MARGIN, CONFIRMATION, GGSHOT_EDIT_VALUES, MARGIN = range(12)
APPROACH_SELECTION = 13  # State for approach selection
```

To:
```python
SYMBOL, SIDE, APPROACH_SELECTION, SCREENSHOT_UPLOAD, PRIMARY_ENTRY, LIMIT_ENTRIES, TAKE_PROFITS, STOP_LOSS, LEVERAGE, MARGIN, CONFIRMATION, GGSHOT_EDIT_VALUES, MARGIN_FAST, MARGIN_CONSERVATIVE = range(14)
```

This ensures state constants match between `handlers/__init__.py` and `handlers/conversation.py`.

### 2. Fixed handle_side_callback Function
Removed incorrect lines that were setting approach and returning wrong state:
```python
# Removed these lines:
context.chat_data[TRADING_APPROACH] = "conservative"
return MARGIN

# Changed to:
return APPROACH_SELECTION
```

### 3. Fixed approach_selection_handler Function
Changed return value from `MARGIN` to `APPROACH_SELECTION`.

### 4. Fixed handle_back_callback Function
Removed hardcoded lines outside the if statement:
```python
# Removed these lines that were outside the if block:
context.chat_data[TRADING_APPROACH] = "conservative"
return MARGIN

# Fixed the approach selection case to return:
return APPROACH_SELECTION
```

## Verification

The conservative approach flow now works correctly:
1. User enters symbol → Returns SIDE state
2. User selects side (Buy/Sell) → Returns APPROACH_SELECTION state
3. User selects "Conservative Limits" → Returns LIMIT_ENTRIES state
4. User can now input limit prices (3 times) → Stays in LIMIT_ENTRIES
5. After 3 limit prices → Returns TAKE_PROFITS state

The message handler for LIMIT_ENTRIES is properly registered in `handlers/__init__.py`:
```python
LIMIT_ENTRIES: [
    MessageHandler(filters.TEXT & ~filters.COMMAND, limit_entries_handler)
],
```

## Testing

To test the fix:
1. Start a new trade with `/trade`
2. Enter a symbol (e.g., BTCUSDT)
3. Select Buy or Sell
4. Select "Conservative Limits"
5. You should now be able to enter limit prices via text input

The bot will prompt for 3 limit order prices, then move on to take profit prices.