# Monitor Separation Fix - Implementation Summary

## Problem Identified
The bot was not properly differentiating between positions with the same symbol but different trading approaches (fast vs conservative). This could lead to:
- Wrong monitor being attached to a position
- Monitors being merged incorrectly
- Conservative positions being monitored as fast trades or vice versa

## Root Cause
1. Monitor keys were using format: `{chat_id}_{symbol}_{approach}`
2. However, monitor restoration logic was defaulting all unknown positions to "fast" approach
3. No approach detection from existing orders was implemented

## Solution Implemented

### 1. Enhanced Approach Detection
Added `detect_approach_from_orders()` function that analyzes order patterns:
- **Conservative**: TP1_, TP2_, TP3_, TP4_, _LIMIT patterns
- **Fast**: _FAST_TP, _FAST_SL, _FAST_MARKET patterns  
- **GGShot**: _GGSHOT_, GGShot patterns
- Falls back to counting TPs (multiple TPs = conservative)

### 2. Enhanced Monitor Restoration
Modified `check_and_restart_position_monitors()` to:
- Fetch all orders for approach detection
- Group orders by symbol for efficient lookup
- Detect approach from order patterns before creating monitors
- Only restore monitors if approach matches
- Create new monitors with detected approach (not default "fast")
- Use unique position keys including approach: `position_{symbol}_{side}_{approach}`

### 3. Enhanced Chat Data Lookup
Updated `find_chat_data_for_symbol()` to:
- Accept optional approach parameter for filtering
- Prioritize exact approach matches when searching

## Key Changes Made

### File: `/Users/lualakol/bybit-telegram-bot/main.py`

1. **Added imports**:
   ```python
   from typing import List, Dict, Optional, Tuple
   ```

2. **Added function**: `detect_approach_from_orders(orders: List[Dict]) -> Optional[str]`
   - Detects trading approach from order patterns
   - Returns "conservative", "fast", "ggshot", or None

3. **Enhanced**: `check_and_restart_position_monitors()`
   - Fetches all orders for approach detection
   - Groups orders by symbol
   - Detects approach before creating/restoring monitors
   - Only matches monitors with same approach
   - Creates position keys with approach included

## Additional Tools Created

### 1. `fix_monitor_restoration.py`
- Contains enhanced monitor restoration logic
- Can be used as a reference implementation

### 2. `test_monitor_separation.py`
- Unit tests for approach detection
- Tests monitor key generation
- Validates position restoration scenarios

### 3. `fix_duplicate_monitors.py`
- Utility to analyze existing monitors
- Detects and fixes duplicate monitors
- Validates monitor approaches against actual orders
- Provides monitor summary reporting

### 4. `MONITOR_SEPARATION_FIX.md` (this file)
- Documents the problem and solution
- Provides implementation details
- Serves as future reference

## How It Works Now

1. **On Position Discovery**:
   - Bot fetches position from Bybit
   - Bot fetches all orders for that symbol
   - Bot detects approach from order patterns
   - Bot searches for matching chat data with same symbol AND approach
   - If no match found, creates new monitor with detected approach

2. **Monitor Key Format**:
   - Primary: `{chat_id}_{symbol}_{approach}`
   - Mirror: `{chat_id}_{symbol}_{approach}_MIRROR`
   - Position data: `position_{symbol}_{side}_{approach}`

3. **Approach Detection Priority**:
   - GGShot patterns (highest priority)
   - Conservative patterns (TP1_, TP2_, etc.)
   - Fast patterns (_FAST_TP, etc.)
   - TP count (>1 TP = conservative)
   - Default: None (let bot decide)

## Testing

Run the test script to verify the fix:
```bash
python test_monitor_separation.py
```

To check for duplicate monitors:
```bash
python fix_duplicate_monitors.py --summary
```

To fix duplicate monitors:
```bash
python fix_duplicate_monitors.py
```

## Impact
- Positions with same symbol but different approaches are now properly separated
- Each approach has its own monitor with correct TP/SL tracking
- Monitor restoration correctly identifies and matches approaches
- No more cross-contamination between fast and conservative trades

## Future Considerations
1. Consider adding approach info to monitor status displays
2. Add approach filtering to dashboard views
3. Consider storing detected approach in persistence for validation
4. Add metrics tracking per approach