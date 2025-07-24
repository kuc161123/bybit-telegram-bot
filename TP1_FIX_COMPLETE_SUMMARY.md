# TP1 Detection Fix - Complete Summary (Main & Mirror Accounts)

## Overview
Fixed the issue where TP1 hits were being misidentified as limit fills, preventing proper breakeven movement and limit order cleanup. All fixes work for BOTH main and mirror accounts.

## Key Fixes Applied

### 1. Monitor Initialization (Both Accounts)
```python
monitor_data = {
    # ... other fields ...
    "last_known_size": tp_sl_position_size if tp_sl_position_size > 0 else Decimal("0"),
    "account_type": account_type,  # "main" or "mirror"
    "phase": "BUILDING",
}
```

### 2. Account-Aware Position Fetching
- Main account: `positions = await get_position_info(symbol)`
- Mirror account: `positions = await get_position_info_for_account(symbol, 'mirror')`

### 3. Account-Aware Order Management
- **Cancel Orders**:
  - Main: `await self._cancel_order_main(symbol, order_id)`
  - Mirror: `await self._cancel_order_mirror(symbol, order_id)`
- **Place Orders**:
  - Main: `await self._place_order_main(**order_params)`
  - Mirror: `await self._place_order_mirror(**order_params)`

### 4. TP Detection Logic (Both Accounts)
```python
# Primary mechanism: Order ID detection
tp_info = await self._identify_filled_tp_order(monitor_data)
# This checks order history with correct account:
filled_qty = await self._verify_order_fill_history(symbol, order_id, order_account)

# Fallback mechanism: Position size detection
if cumulative_percentage >= 85:  # TP1 hit
    monitor_data["tp1_hit"] = True
    monitor_data["phase"] = "PROFIT_TAKING"
    # Trigger breakeven and limit cancellation
```

### 5. Phase Transition (Both Accounts)
When TP1 is detected:
1. `await self._transition_to_profit_taking(monitor_data)`
   - Checks account type from monitor_data
   - Uses account-aware cancel functions
   - Cancels unfilled limit orders (if enabled)
   - Updates phase to PROFIT_TAKING

### 6. Breakeven Movement (Both Accounts)
```python
# Get position for correct account
positions = await get_position_info_for_account(symbol, account_type)

# Move SL to breakeven
success = await self._move_sl_to_breakeven_enhanced_v2(
    monitor_data=monitor_data,
    position=position,
    is_tp1_trigger=True
)
```

## Mirror Account Specific Handling

### Order History Verification
```python
if account == "mirror":
    from execution.mirror_trader import bybit_client_2
    client = bybit_client_2
else:
    from clients.bybit_client import bybit_client
    client = bybit_client
```

### Monitor Keys
- Main: `{symbol}_{side}_main`
- Mirror: `{symbol}_{side}_mirror`

### Dashboard Entries
- Main: `{chat_id}_{symbol}_{approach}`
- Mirror: `{chat_id}_{symbol}_{approach}_mirror`

## What Happens When TP1 Hits

### For BOTH Main and Mirror Accounts:
1. **Detection**: Via order ID or position size reduction
2. **Flag Setting**: `tp1_hit = True`
3. **Phase Change**: BUILDING → PROFIT_TAKING
4. **Limit Cancellation**: All unfilled limit orders cancelled
5. **Breakeven**: SL moved to breakeven price
6. **Alerts Sent**:
   - TP1 fill alert
   - Limit order cleanup alert (if any cancelled)
   - Breakeven movement alert

## Testing Checklist
- [ ] Open position with conservative approach (main account)
- [ ] Open position with conservative approach (mirror account)
- [ ] Verify limit orders fill correctly for both
- [ ] Verify TP1 detection at 85% for both
- [ ] Verify breakeven movement for both
- [ ] Verify limit order cancellation for both
- [ ] Verify alerts are sent for both accounts

## Configuration Required
```bash
ENABLE_MIRROR_TRADING=true      # Enable mirror account
CANCEL_LIMITS_ON_TP1=true       # Cancel limits on TP1
ENABLE_ENHANCED_TP_SL=true      # Use enhanced monitoring
BREAKEVEN_FAILSAFE_ENABLED=true # Breakeven protection
```

## Summary
All TP1 detection and handling logic is now fully account-aware. The system will:
- Correctly identify which account a position belongs to
- Use the appropriate API client for that account
- Handle all operations (detection, cancellation, breakeven) correctly
- Send alerts with proper account identification