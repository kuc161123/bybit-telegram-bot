# Conservative Rebalancer - stopOrderType Fix Summary

## Changes Made

### 1. Preserve Original stopOrderType
All rebalancing functions now preserve the exact `stopOrderType` from the original order when placing replacements:

- `_rebalance_position()` - Main rebalancing logic
- `rebalance_conservative_on_limit_fill()` - When limit orders fill
- `rebalance_sl_quantity_after_tp1()` - After TP1 hits
- `rebalance_conservative_on_tp_hit()` - After any TP hits

### 2. Helper Function Added
Created `get_stop_order_type_for_replacement()` that:
- Preserves exact stopOrderType from original order
- Maps variations like "PartialTakeProfit" → "TakeProfit"
- Falls back to orderLinkId analysis if needed
- Logs warnings if type cannot be determined

### 3. Enhanced Logging
All rebalancing operations now log the stopOrderType being used:
```
✅ Rebalanced TP1: 1163 → 1164 (price: $0.08397, type: Stop)
✅ SL rebalanced successfully after TP1 (type: Stop)
```

### 4. 5-Minute Check Interval
The rebalancer already checks every 5 minutes (`self.check_interval = 300`).

## How It Works

When rebalancing any order:
1. Gets the original `stopOrderType` from the order being replaced
2. Uses the helper function to ensure correct type
3. Places new order with same `stopOrderType` value
4. Logs the type used for verification

This ensures 100% API compatibility and prevents any issues with order types.

## Expected Behavior

- All rebalanced orders maintain their original order types
- Bybit API accepts orders without type mismatches
- Progressive SL rebalancing after TP hits works correctly
- 5-minute checks ensure positions stay balanced