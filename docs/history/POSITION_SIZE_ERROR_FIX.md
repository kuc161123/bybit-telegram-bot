# Position Size Error Fix Summary

## Issue
The bot was encountering an error "Error sending position closed alert: 'position_size'" when trying to send position closed alerts.

## Root Cause
In the `enhanced_tp_sl_manager.py` file, the `create_dashboard_monitor_entry` function was creating monitor data without including the `position_size` field. However, the `_send_position_closed_alert` function expected this field to be present in the monitor_data dictionary.

## Solution
Added the `position_size` field to the monitor_data dictionary in the `create_dashboard_monitor_entry` function:

```python
# Before (line 3765-3777):
monitor_data = {
    'symbol': symbol,
    'side': side,
    'chat_id': chat_id,
    'approach': approach.lower(),
    'account_type': account_type,
    'dashboard_key': dashboard_key,
    'entry_price': position_data.get('avgPrice', 0),
    'stop_loss': self.position_monitors.get(f"{symbol}_{side}", {}).get('stop_loss', 0),
    'take_profits': self.position_monitors.get(f"{symbol}_{side}", {}).get('tp_orders', []),
    'created_at': time.time(),
    'system_type': 'enhanced_tp_sl'
}

# After:
monitor_data = {
    'symbol': symbol,
    'side': side,
    'chat_id': chat_id,
    'approach': approach.lower(),
    'account_type': account_type,
    'dashboard_key': dashboard_key,
    'entry_price': position_data.get('avgPrice', 0),
    'position_size': position_data.get('size', self.position_monitors.get(f"{symbol}_{side}", {}).get('position_size', 0)),
    'stop_loss': self.position_monitors.get(f"{symbol}_{side}", {}).get('stop_loss', 0),
    'take_profits': self.position_monitors.get(f"{symbol}_{side}", {}).get('tp_orders', []),
    'created_at': time.time(),
    'system_type': 'enhanced_tp_sl'
}
```

## Technical Details
- The fix retrieves the position size from the `position_data` dictionary (if available) or falls back to the position monitors data
- This ensures that the `position_size` field is always present when `_send_position_closed_alert` is called
- The mirror account functionality was already correct and didn't need changes

## Files Modified
- `/Users/lualakol/bybit-telegram-bot/execution/enhanced_tp_sl_manager.py` (line 3773)

## Testing
To verify the fix works:
1. Monitor the logs for any "Error sending position closed alert" messages
2. Close a position and verify that the position closed alert is sent successfully
3. Check that the alert includes the correct position size information