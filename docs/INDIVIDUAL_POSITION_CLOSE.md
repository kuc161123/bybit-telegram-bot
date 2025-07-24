# Individual Position Closing Feature

## Overview
This feature allows users to close specific positions individually, along with all their corresponding orders, on both main and mirror accounts. This provides granular control over position management without having to use the emergency close all feature.

## How to Use

1. **Access Position List**
   - Click the "📋 Positions" button in the dashboard
   - Or use the `/list_positions` command

2. **View Positions**
   - Main account positions are shown under "🏦 MAIN ACCOUNT"
   - Mirror account positions (if enabled) are shown under "🔄 MIRROR ACCOUNT"
   - Each position displays:
     - Symbol and side (Buy/Sell)
     - Size and average entry price
     - Current mark price and leverage
     - Unrealized P&L with percentage

3. **Close a Position**
   - Each position has a "❌ Close [SYMBOL]" button
   - Mirror positions show "❌ Close [SYMBOL] (Mirror)"
   - Click the button for the position you want to close

4. **Confirm Closure**
   - A confirmation screen appears showing:
     - Full position details
     - Current P&L (profit/loss)
     - Warning that all orders will be cancelled
   - Click "✅ YES, CLOSE [SYMBOL]" to confirm
   - Or click "❌ Cancel" to abort

5. **Execution**
   - The bot will:
     1. Cancel ALL orders for that symbol (TP, SL, limit orders)
     2. Close the position at market price
   - A summary shows the results

## Safety Features

- **Two-Step Confirmation**: Prevents accidental closures
- **P&L Display**: Shows current profit/loss before closing
- **Clear Account Labels**: Clearly indicates which account (main/mirror)
- **Order Warning**: Explicitly states all orders will be cancelled
- **Error Handling**: Graceful handling of API errors

## Technical Details

### Files Created/Modified

1. **execution/position_manager.py** (NEW)
   - `PositionManager` class with core functionality
   - `close_position_with_orders()` - Main closing logic
   - `get_position_details()` - Fetch position information
   - `cancel_all_orders_for_symbol()` - Cancel all orders
   - Support for both main and mirror accounts

2. **handlers/position_close_handler.py** (NEW)
   - `handle_close_position_request()` - Initial close request
   - `handle_confirm_close_position()` - Execute closure
   - `handle_cancel_close_position()` - Cancel operation
   - Callback patterns for button handling

3. **handlers/position_stats_handlers.py** (MODIFIED)
   - Enhanced `list_positions()` function
   - Added close buttons for each position
   - Support for mirror account display
   - Improved position formatting

4. **handlers/__init__.py** (MODIFIED)
   - Registered new position close handlers
   - Added imports for new handler functions

### Callback Patterns

- `close_position:{symbol}:{account}` - Initial close request
- `confirm_close_position:{symbol}:{account}` - Confirmation
- `cancel_close_position` - Cancel the operation

## Benefits

1. **Granular Control**: Close specific positions without affecting others
2. **Risk Management**: Quickly exit losing positions
3. **Order Cleanup**: Automatically cancels all related orders
4. **Mirror Support**: Manage mirror positions independently
5. **Mobile Friendly**: Easy-to-use button interface

## Example Flow

```
User: [Clicks "📋 Positions"]
Bot: Shows list of positions with close buttons

User: [Clicks "❌ Close BTCUSDT"]
Bot: Shows confirmation with position details and P&L

User: [Clicks "✅ YES, CLOSE BTCUSDT"]
Bot: Cancels orders, closes position, shows summary
```

## Notes

- Positions are closed at market price for immediate execution
- All orders for the symbol are cancelled, including TP/SL
- The feature respects position modes (hedge/one-way)
- Works seamlessly with the existing monitoring system
- Other positions continue to be monitored normally