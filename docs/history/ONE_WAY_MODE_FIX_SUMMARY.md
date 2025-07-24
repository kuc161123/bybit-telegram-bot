# One-Way Mode Fix Summary

## Overview
Fixed the position mode detection to properly support one-way mode for both main and mirror accounts.

## Issue
The bot was detecting one-way mode correctly but then forcing hedge mode anyway, causing "position idx not match position mode" errors.

## Changes Made

### 1. Main Account Position Detection
**File: `clients/bybit_helpers.py`**
- Fixed `detect_position_mode_for_symbol()` to return correct values for one-way mode
- When one-way mode is detected, now returns `(False, 0)` instead of forcing hedge mode
- Removed the incorrect fallback that was defaulting to hedge mode

### 2. Mirror Account Position Detection
**File: `execution/mirror_trader.py`**
- Already has proper position mode detection implemented
- `detect_position_mode_for_symbol_mirror()` correctly detects one-way vs hedge mode
- All mirror order functions (`mirror_market_order`, `mirror_limit_order`, `mirror_tp_sl_order`) automatically detect and use the correct position index

## How It Works Now

### For One-Way Mode:
- Main account: Uses `positionIdx=0` for all orders
- Mirror account: Automatically detects mode and uses `positionIdx=0`

### For Hedge Mode:
- Main account: Uses `positionIdx=1` for Buy, `positionIdx=2` for Sell
- Mirror account: Automatically detects mode and uses appropriate index

## Key Functions:

1. **Main Account Detection**:
   ```python
   async def detect_position_mode_for_symbol(symbol: str) -> Tuple[bool, int]:
       # Returns (False, 0) for one-way mode
       # Returns (True, 1) for hedge mode
   ```

2. **Mirror Account Detection**:
   ```python
   async def detect_position_mode_for_symbol_mirror(symbol: str) -> Tuple[bool, int]:
       # Automatically detects and returns correct mode
   ```

3. **Position Index Assignment**:
   - One-way mode: Always uses `positionIdx=0`
   - Hedge mode: Uses `1` for Buy/Long, `2` for Sell/Short

## Testing
Both accounts should now work correctly in one-way mode:
1. Orders will be placed with `positionIdx=0`
2. No more "position idx not match position mode" errors
3. Mirror account will automatically match the mode of its account