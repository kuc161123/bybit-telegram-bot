# Mirror Account Rebalancing Fix Summary

## Problem
When a limit order filled on both main and mirror accounts (STRKUSDT), the main account successfully rebalanced all TP orders but the mirror account failed with "order not exists or too late to cancel" errors.

## Root Cause
The `_adjust_all_orders_for_partial_fill` method was using:
- `cancel_order_with_retry()` which always uses the main account client
- `place_order_with_retry()` without client parameter for mirror accounts

This meant mirror account orders were being cancelled/placed on the main account where they don't exist.

## Fixes Applied

### 1. Fixed TP Order Cancellation in `_adjust_all_orders_for_partial_fill`
- Added `is_mirror_account` detection based on `account_type`
- Replaced `cancel_order_with_retry()` with account-aware methods:
  - `self._cancel_order_mirror()` for mirror accounts
  - `self._cancel_order_main()` for main accounts

### 2. Fixed TP Order Placement
- Added client parameter to `place_order_with_retry()` calls
- Uses `self._mirror_client` (which is properly initialized from `execution.mirror_trader`)
- Fixed import error by using the class's mirror client instance instead of incorrect import

### 3. Fixed SL Order Adjustment in `_adjust_sl_quantity`
- Added account type detection
- Used account-aware cancellation methods
- Added client parameter for SL order placement

### 4. Fixed Import Error
- Removed incorrect import `from clients.bybit_client import bybit_client_2`
- Used `self._mirror_client` which is properly initialized in the class constructor

## Expected Result
After these fixes:
- Mirror account will properly cancel its own TP orders during rebalancing
- New TP orders will be placed on the correct account with adjusted quantities
- Both main and mirror accounts will rebalance independently and correctly
- No more "order not exists" errors for mirror account operations
- No more import errors when adjusting orders

## Testing
The bot should be restarted to test these changes. When a limit order fills on the mirror account, you should see:
- Successful TP order cancellations (no errors)
- New TP orders placed with adjusted quantities
- SL order adjusted to match new position size
- No import errors in the logs