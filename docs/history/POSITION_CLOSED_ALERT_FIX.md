# Position Closed Alert Fix Summary

## Issue
Error message: `Error sending position closed alert: 'position_size'`

The error occurred in the Enhanced TP/SL Manager when trying to send a position closed alert. The `monitor_data` dictionary was missing the `position_size` key.

## Root Cause
When a position is closed (either by hitting SL or manual closure), the `_send_position_closed_alert` method is called with the monitor data. In some cases, the monitor data might not have the `position_size` key, possibly due to:
1. Corrupted monitor data
2. Position closed externally before monitor initialization completed
3. Legacy monitor data structure

## Fix Applied
Modified `/execution/enhanced_tp_sl_manager.py` in the `_send_position_closed_alert` method:

1. Added defensive check for missing `position_size` key
2. Falls back to `current_size` or `remaining_size` if `position_size` is missing
3. Added logging to track available keys when position_size is not found
4. Returns early if no size information is available

## Code Changes
```python
# Handle missing position_size key
position_size = monitor_data.get("position_size")
if position_size is None:
    # Try alternative keys
    position_size = monitor_data.get("current_size") or monitor_data.get("remaining_size")
    if position_size is None:
        logger.warning(f"Position size not found in monitor data for {symbol} {side}")
        logger.warning(f"Available keys in monitor_data: {list(monitor_data.keys())}")
        return
```

## Testing
The fix will:
- Prevent the KeyError from occurring
- Log detailed information if the issue happens again
- Still send the alert if alternative size keys are available
- Gracefully skip the alert if no size information is found

## Impact
- No functional changes to normal operation
- Improved error handling for edge cases
- Better debugging information for future issues