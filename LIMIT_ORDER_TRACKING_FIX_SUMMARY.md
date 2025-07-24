# Limit Order Tracking Fix Summary

## Issue Identified
The Enhanced TP/SL Manager was incorrectly tracking 4 limit orders instead of 3 for conservative approach trades. The root cause was that the initial market order (which executes immediately) was being added to the `limit_order_ids` list along with the actual limit orders.

## Conservative Approach Structure (Correct)
1. **Initial Market Order** - Executes immediately at the first "limit" price (NOT a limit order)
2. **2 Limit Orders** - Placed at the second and third price levels for gradual position building
3. **Total: 3 entry orders** (1 market + 2 limits)

## Fixes Applied

### 1. Fixed Import Structure (enhanced_tp_sl_manager.py)
- Moved `limit_order_tracker` import to module level
- Removed all dynamic imports from inside methods
- Added initialization logging

### 2. Fixed Order Classification (trader.py)
- Modified the conservative approach execution to only add actual limit orders to `limit_order_ids`
- Market orders are now properly tracked separately
- Fixed logging to distinguish between "Market:" and "Limit{i}:" order messages

### 3. Enhanced Monitoring
- Added debug logging to show monitor counts and state
- Added warning logs when monitors are not found
- Enhanced background task logging to track monitoring loop status

### 4. Cleanup Script
- Created `fix_limit_order_tracking.py` to clean up existing incorrect registrations
- Handles both main and mirror accounts
- Removes market orders and non-existent orders from limit order tracking
- Validates remaining orders are actually open limit orders

## Code Changes

### Before (Incorrect):
```python
if result:
    order_id = result.get("orderId", "")
    limit_order_ids.append(order_id)  # Added ALL orders including market
    orders_placed.append(f"Limit{i}: {order_id[:8]}...")
```

### After (Fixed):
```python
if result:
    order_id = result.get("orderId", "")
    
    # Only append to limit_order_ids if it's actually a limit order
    if order_type == "Limit":
        limit_order_ids.append(order_id)
        orders_placed.append(f"Limit{i}: {order_id[:8]}...")
    else:
        # It's a market order
        orders_placed.append(f"Market: {order_id[:8]}...")
```

## Testing

To verify the fix:
1. Restart the bot to apply the changes
2. Place a new conservative trade
3. Check logs - should show "Market:" for first order and "Limit1:", "Limit2:", "Limit3:" for the limit orders
4. Enhanced TP/SL Manager should only track 3 limit orders, not 4

## Impact
- Existing positions: Cleaned up via `fix_limit_order_tracking.py`
- New positions: Will correctly track only actual limit orders
- Both main and mirror accounts are properly handled