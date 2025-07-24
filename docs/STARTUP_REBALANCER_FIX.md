# Startup Rebalancer Fix for Old Order Format

## Problem
The startup rebalancer was reporting "Wrong number of TP orders: 0 vs expected 4" for INJUSDT even though the orders existed. Investigation revealed that:
- INJUSDT orders use the old Bybit API format where all stop orders have `stopOrderType='Stop'`
- The rebalancer was only looking for the new format with `stopOrderType='TakeProfit'` and `stopOrderType='StopLoss'`

## Solution
Updated `startup_conservative_rebalancer.py` to handle both order formats:

### 1. In `check_if_needs_rebalance()` function:
- Added logic to detect old format orders with `stopOrderType='Stop'`
- Identifies TP/SL based on order side vs position side
- Separates TP from SL orders by checking quantities (SL should be ~100% of position)

### 2. In `get_position_chat_data()` function:
- Added handling for old format orders when creating minimal chat data
- Collects all stop orders and separates them based on quantity analysis
- The order with quantity closest to position size is identified as the SL

## Testing
Created `test_startup_rebalancer_fix.py` which confirms:
- Old format orders are correctly identified
- TP and SL orders are properly separated
- Quantity checks work correctly
- No false rebalancing triggers for correctly balanced positions

## Result
The startup rebalancer will now correctly handle both:
- New format: `stopOrderType='TakeProfit'` or `stopOrderType='StopLoss'`
- Old format: `stopOrderType='Stop'` with intelligent TP/SL detection

When you restart the bot, INJUSDT will be properly checked and only rebalanced if quantities are actually mismatched.