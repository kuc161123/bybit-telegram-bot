# Stop Order Limit Fix Implementation

## Problem
Bybit has a limit of 10 stop orders per symbol. When placing conservative trades with 4 TPs + 1 SL (5 stop orders total), the bot could exceed this limit if there were already existing orders on the symbol.

## Solution Implemented

### 1. Added Stop Order Limit Checking Function
**File:** `/clients/bybit_helpers.py`
- Added `check_stop_order_limit()` function that:
  - Queries all open orders for a symbol
  - Counts stop orders (orders with trigger prices)
  - Returns current count, limit (10), and available slots
  - Provides list of existing orders for reference

### 2. Updated Conservative Trade Execution
**File:** `/execution/trader.py`
- Modified `execute_conservative_approach()` to:
  - Check stop order limit before placing TP/SL orders
  - Warn if limit is reached or close to limit
  - Skip TP orders if adding them would exceed the limit
  - Prioritize SL order placement (reserve 1 slot)
  - Track placed TP count to manage limit
  - Add enhanced warning messages when limit is hit

### 3. Updated GGShot Conservative Pattern
**File:** `/execution/trader.py`
- Applied same stop order limit checks to `_execute_ggshot_conservative_pattern()`
- Ensures GGShot trades also respect the 10 order limit

## Key Features

1. **Pre-flight Check**: Checks available slots before placing any stop orders
2. **Prioritization**: Always tries to place SL order (most important for risk management)
3. **Clear Warnings**: Notifies user when orders are skipped due to limit
4. **Detailed Messages**: Shows current count vs limit in warning messages
5. **Graceful Degradation**: Trade continues even if some TP orders can't be placed

## Usage Example

When a conservative trade is placed and the limit is reached, users will see:

```
⚠️ Warnings:
   • Only 3 stop order slots available. Some TP/SL orders may fail.
   • TP3 skipped due to stop order limit
   • TP4 skipped due to stop order limit

🚨 IMPORTANT: Stop order limit reached!
   • Bybit allows max 10 stop orders per symbol
   • Current: 8/10
   • Some TP/SL orders may not have been placed
   • Consider canceling unused orders to free slots
```

## Testing

Run the test script to verify the implementation:
```bash
python test_stop_order_limit.py
```

This will show the current stop order status for BTCUSDT.

## Future Enhancements

1. **Order Priority System**: Could implement smarter prioritization (e.g., keep TP1 and TP4, skip TP2-3)
2. **Auto-cleanup**: Could offer to cancel old/unused orders to make room
3. **Multi-symbol Limit Tracking**: Dashboard could show limit status across all traded symbols
4. **Pre-trade Check**: Could check limit before showing trade setup to warn users early