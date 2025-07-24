# StopOrderType Parameter Update

## Overview
Added `stopOrderType` parameter to all TP/SL order placements to ensure Bybit correctly identifies order types.

## Changes Made

### 1. Updated `clients/bybit_helpers.py`
- Added `stop_order_type` parameter to `place_order_with_retry()` function
- Function now includes `stopOrderType` in order params when provided

### 2. Updated `execution/trader.py` (via Task tool)
- All TP orders now include `stop_order_type="TakeProfit"`
- All SL orders now include `stop_order_type="StopLoss"`
- Applies to:
  - Fast Market approach orders
  - Conservative approach orders
  - Merge position orders
  - GGShot orders

### 3. Updated `execution/conservative_rebalancer.py`
- TP rebalancing orders: Added `stop_order_type="TakeProfit"`
- SL rebalancing orders: Added `stop_order_type="StopLoss"`
- Mirror TP orders: Added `stop_order_type="TakeProfit"`
- Mirror SL orders: Added `stop_order_type="StopLoss"`

### 4. Verified `execution/mirror_trader.py`
- Already supports `stop_order_type` parameter
- Properly includes it in order parameters when provided

## Benefits
1. Bybit will correctly identify orders as TakeProfit or StopLoss
2. Improved order visibility and management in exchange interface
3. Prevents issues with old format orders showing as generic "Stop" orders
4. Consistent order type identification across all trading approaches

## Technical Details
- Parameter is optional for backward compatibility
- TakeProfit orders: `stopOrderType="TakeProfit"`
- StopLoss orders: `stopOrderType="StopLoss"`
- Applies to both main and mirror accounts