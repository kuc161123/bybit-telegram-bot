# Comprehensive TP Rebalancing Fix - January 25, 2025

## Executive Summary

Implemented a comprehensive fix for mirror account TP rebalancing issues that were causing "No orderId in result" errors and missing rebalancing alerts. The fix addresses all identified root causes with robust error handling and recovery mechanisms.

## Root Causes Identified

### 1. Stale Order IDs (Primary Issue)
- **Problem**: TP orders stored in monitor data became stale (already cancelled/filled)
- **Symptoms**: API errors "order not exists or too late to cancel (ErrCode: 110001)"
- **Impact**: Rebalancing completely failed with no alert sent

### 2. Duplicate OrderLinkIDs (Secondary Issue)  
- **Problem**: OrderLinkID generation produced duplicates
- **Symptoms**: API errors "OrderLinkedID is duplicate (ErrCode: 110072)"
- **Impact**: Order placement failed even after successful cancellation

### 3. Missing TP Orders (Mirror-specific Issue)
- **Problem**: Mirror account monitors had empty tp_orders dict
- **Symptoms**: "No TP orders found" warnings, no rebalancing attempted
- **Impact**: Silent failure with no recovery mechanism

## Comprehensive Solution Implemented

### 1. Fresh Order Validation System

#### New Method: `_validate_and_refresh_tp_orders()`
```python
async def _validate_and_refresh_tp_orders(self, monitor_data: Dict) -> Dict:
    """
    Validate existing TP orders against exchange data and refresh stale information
    This prevents API errors when trying to cancel non-existent orders
    """
```

**Features:**
- ✅ **Real-time Exchange Validation**: Fetches fresh order data from exchange
- ✅ **Stale Order Detection**: Identifies orders that no longer exist
- ✅ **Monitor Data Cleanup**: Removes stale orders from persistence
- ✅ **Account-aware**: Works for both main and mirror accounts
- ✅ **Error Recovery**: Falls back to original data if validation fails

**Logged Output:**
```
🔍 Validating TP orders for BANDUSDT (MIRROR)
📊 Found 2 active orders on exchange for BANDUSDT (mirror)
🗑️ Removing stale TP order 017053f0... (not found on exchange)
🧹 Removed 1 stale TP orders from monitor data
✅ TP order validation complete: 3 valid orders
```

### 2. Unique OrderLinkID Generation

#### New Method: `_generate_unique_order_link_id()`
```python
def _generate_unique_order_link_id(self, symbol: str, tp_num: int, account_type: str) -> str:
    """
    Generate unique OrderLinkID to prevent duplicates
    Format: PREFIX_TP_SYMBOL_TP_NUM_TIMESTAMP_RANDOM
    """
```

**Features:**
- ✅ **Millisecond Timestamp**: Ensures uniqueness across time
- ✅ **Random Suffix**: Additional collision prevention (1000-9999)
- ✅ **Account Prefix**: MIR_ for mirror, BOT_ for main
- ✅ **Length Validation**: Respects Bybit 36-character limit
- ✅ **Fallback Logic**: Truncates symbol if needed

**Example Output:**
```
🔗 Generated OrderLinkID: MIR_TP1_BANDUSDT_1737809937842_7432
```

### 3. Enhanced Error Handling

#### Updated Method: `_cancel_tp_order_with_retry()`
```python
# ENHANCED: Handle common API errors that indicate order is already gone
if ("order not exists" in error_msg.lower() or 
    "order not found" in error_msg.lower() or
    "too late to cancel" in error_msg.lower() or
    "110001" in error_msg):
    logger.warning(f"🔄 Order {order_id[:8]}... already cancelled or filled")
    return True, f"{account_name} order already cancelled/filled (ErrCode: 110001 handled)"
```

**Features:**
- ✅ **Smart Error Recognition**: Detects "order not exists" as success
- ✅ **Multiple Error Patterns**: Handles various Bybit error messages
- ✅ **Error Code Detection**: Recognizes specific Bybit error codes
- ✅ **Continuation Logic**: Treats expected errors as successful cancellations

### 4. Mirror Account Recovery System

#### New Method: `_attempt_tp_order_recovery()`
```python
async def _attempt_tp_order_recovery(self, monitor_data: Dict) -> Dict:
    """
    Attempt to recover missing TP orders for mirror accounts by checking main account
    and reconstructing mirror TP order data
    """
```

**Features:**
- ✅ **Exchange Data Reconstruction**: Builds TP order data from live exchange orders
- ✅ **TP Pattern Recognition**: Identifies TP orders by reduceOnly flag and OrderLinkID
- ✅ **TP Number Detection**: Extracts TP numbers from OrderLinkID patterns
- ✅ **Monitor Data Update**: Saves recovered orders to persistence
- ✅ **Recovery Tracking**: Marks orders with recovery timestamp

**Recovery Flow:**
1. Detect mirror account with missing TP orders
2. Fetch fresh orders from exchange for mirror account
3. Filter for reduceOnly limit orders (TP characteristics)
4. Reconstruct TP order data structure
5. Update monitor data and save to persistence

### 5. Enhanced Alert System

#### Updated Method: `_send_tp_rebalancing_alert()`
- ✅ **New Status Type**: Added "SKIPPED" status with ⏭️ emoji
- ✅ **Detailed Error Messages**: Specific messages for different failure types
- ✅ **Recovery Notifications**: Alerts when recovery is attempted/successful

**Alert Examples:**
```
⏭️ TP REBALANCING SKIPPED
━━━━━━━━━━━━━━━━━━━━━━
🪞 Account: MIRROR
📊 BANDUSDT Sell

📋 Summary:
• Position Size: 921.9
• TP Orders Processed: 0/0
• Results: Mirror TP orders missing and recovery failed

⏭️ TP orders have been skipped due to validation issues after limit fill
```

## Integration and Flow

### Enhanced Rebalancing Process
```python
# 1. Validate existing TP orders
tp_orders = await self._validate_and_refresh_tp_orders(monitor_data)

# 2. Attempt recovery if no valid orders found (mirror accounts)
if not tp_orders and account_type == "mirror":
    tp_orders = await self._attempt_tp_order_recovery(monitor_data)

# 3. Generate unique OrderLinkIDs for new orders
unique_order_link_id = self._generate_unique_order_link_id(symbol, tp_num, account_type)

# 4. Enhanced error handling during cancellation
cancel_success, cancel_message = await self._cancel_tp_order_with_retry(...)

# 5. Comprehensive status reporting
await self._send_tp_rebalancing_alert(monitor_data, successful, total, results, status)
```

## Expected Outcomes

### Before Fix:
- ❌ Mirror account: "No TP orders found" → Silent failure
- ❌ BANDUSDT mirror: API errors → "No orderId in result: {}"
- ❌ No alerts sent for failed rebalancing attempts

### After Fix:
- ✅ **Stale Order Handling**: Orders validated against exchange before processing
- ✅ **Unique OrderLinkIDs**: No more duplicate ID conflicts
- ✅ **Recovery Mechanism**: Missing mirror TP orders automatically recovered
- ✅ **Enhanced Alerts**: Clear status reporting for all scenarios
- ✅ **Robust Error Handling**: API errors properly categorized and handled

## Monitoring and Validation

### Success Indicators in Logs:
```
🔍 Validating TP orders before rebalancing...
✅ TP order validation complete: 4 valid orders
🔄 Processing TP1 order (index 0)
🗑️ Cancelling existing TP1 order: 017053f0...
🔄 Order 017053f0... already cancelled or filled (handled gracefully)
📤 Placing new TP1 order: Buy 783.6 @ 0.6528
🔗 Generated OrderLinkID: MIR_TP1_BANDUSDT_1737809937842_7432
✅ TP1 REBALANCED SUCCESSFULLY: 261.2 → 783.6 (85% of 921.9)
```

### Recovery Success Indicators:
```
🔄 Attempting TP order recovery for mirror account...
🔄 Recovered 4 TP orders from exchange data
✅ Successfully recovered and saved 4 TP orders
✅ Recovered 4 TP orders, proceeding with rebalancing
```

## Files Modified

1. **`execution/enhanced_tp_sl_manager.py`**
   - Added `_validate_and_refresh_tp_orders()` method
   - Added `_generate_unique_order_link_id()` method  
   - Added `_attempt_tp_order_recovery()` method
   - Enhanced `_cancel_tp_order_with_retry()` error handling
   - Updated `_send_tp_rebalancing_alert()` with SKIPPED status
   - Integrated all fixes into `_adjust_all_orders_for_partial_fill()`

## Deployment Notes

- ✅ **Backward Compatible**: All changes are additive, no breaking changes
- ✅ **Graceful Degradation**: Falls back to original behavior if new features fail
- ✅ **Account Agnostic**: Works for both main and mirror accounts
- ✅ **Performance Optimized**: Uses existing caching infrastructure
- ✅ **Comprehensive Logging**: Detailed logs for troubleshooting

## Verification Steps

1. **Monitor Logs**: Look for validation and recovery messages
2. **Check Alerts**: Verify TP rebalancing alerts are sent for mirror accounts  
3. **Exchange Verification**: Confirm TP orders exist on exchange after rebalancing
4. **Error Handling**: Verify graceful handling of stale orders
5. **OrderLinkID Uniqueness**: No more duplicate ID errors

This comprehensive fix addresses all identified root causes and provides a robust, self-healing system for TP rebalancing across both main and mirror accounts.