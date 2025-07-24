# Mirror Trading Alert Configuration

## Overview
Mirror trading in this bot allows trades to be replicated on a second Bybit account. By design, mirror account monitoring operates **silently** without sending Telegram alerts.

## Why Mirror Alerts are Disabled

1. **Prevent Duplicate Notifications**: Users already receive alerts for main account activity. Sending identical alerts for mirror accounts would create notification overload.

2. **Clarity**: Having separate alerts for main and mirror accounts could confuse users about which account triggered the notification.

3. **Performance**: Reducing unnecessary notifications improves bot performance and user experience.

## Configuration

Mirror alerts are controlled by the `ENABLE_MIRROR_ALERTS` constant in `config/constants.py`:

```python
ENABLE_MIRROR_ALERTS = False  # Disable alerts for mirror account positions
```

## What Gets Logged vs Alerted

### Main Account (Primary)
- ✅ Full Telegram alerts for all events
- ✅ Detailed logging
- ✅ Performance tracking updates

### Mirror Account
- ❌ No Telegram alerts
- ✅ Full logging (viewable in bot logs)
- ❌ No performance tracking updates (prevents double counting)

## Events Affected

The following events will be logged but NOT alerted for mirror accounts:
- Position openings
- Take Profit (TP) hits
- Stop Loss (SL) hits
- Position closures
- Limit order fills
- Order cancellations

## Future Considerations

If mirror alerts are needed in the future:
1. Set `ENABLE_MIRROR_ALERTS = True`
2. Implement alert differentiation (e.g., prefix alerts with "[MIRROR]")
3. Add user preference settings for mirror alerts
4. Consider separate notification channels for mirror events