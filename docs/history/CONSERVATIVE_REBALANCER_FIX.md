# Conservative Rebalancer Fix - Preventing Recreation of Hit TPs

## Date: 2025-06-30

### Issue Identified
The Conservative rebalancer was recreating TP orders that had already been executed. When a TP hit (e.g., TP1 closing 85% of position), the rebalancer would recreate that TP order during subsequent rebalancing events, essentially trying to close more than 100% of the position.

### Root Cause
The `rebalance_on_limit_fill` function always created all 4 TPs with 85/5/5/5 distribution without checking which TPs had already been executed. While `rebalance_on_tp_hit` correctly handled distribution among remaining TPs, limit fill and merge rebalancing ignored the hit history.

### Fix Implementation

#### 1. Added TP Hit Tracking (monitor.py)
- TP1 hits are tracked in `conservative_tps_hit` list when detected (already implemented)
- TP2, TP3, TP4 hits are tracked in `check_conservative_other_tp_hits` function (already implemented)
- Added cleanup of `conservative_tps_hit` list when positions close (lines 2705-2708, 3262-3265)

#### 2. Updated Main Account Rebalancing (conservative_rebalancer.py)
- Modified `rebalance_on_limit_fill` to check `conservative_tps_hit` list (lines 83-119)
- Only creates TP orders for TPs that haven't hit yet
- Distributes position equally among remaining active TPs
- Skips creation of orders for TPs that have already executed

#### 3. Updated Mirror Account Rebalancing (conservative_rebalancer.py)
- Modified `rebalance_mirror_account` to check hit TPs for limit fills (lines 639-675)
- Updated cancellation logic to skip already-hit TPs (lines 692-699)
- Added checks when placing new orders to skip hit TPs (lines 734-737)

### Key Changes Summary

1. **Track Hit TPs**: The system maintains a `conservative_tps_hit` list containing ["TP1", "TP2", etc.] for executed TPs
2. **Check Before Rebalancing**: Before creating new TP orders, check which TPs are in the hit list
3. **Skip Hit TPs**: Don't cancel or recreate orders for TPs that have already executed
4. **Distribute Among Remaining**: Position is distributed equally among TPs that haven't hit yet
5. **Clear on Close**: The tracking list is cleared when the position closes

### Example Scenarios

**Scenario 1: TP1 hits, then limit order fills**
- Before: Would create TP1 (85%), TP2 (5%), TP3 (5%), TP4 (5%) 
- After: Skips TP1, creates TP2 (33.33%), TP3 (33.33%), TP4 (33.33%)

**Scenario 2: TP1 and TP2 hit, then rebalancing**
- Before: Would recreate all 4 TPs
- After: Skips TP1 and TP2, creates TP3 (50%), TP4 (50%)

### Benefits
1. **Correct Position Management**: Prevents trying to close more than 100% of position
2. **Accurate Order Distribution**: Remaining position correctly distributed among active TPs
3. **No Duplicate Orders**: Hit TPs are never recreated
4. **Consistent Behavior**: Both main and mirror accounts handle hit TPs correctly

### Testing Recommendations
1. Open a Conservative position with 3 limit orders
2. Wait for TP1 to hit (should close 85%)
3. Let a limit order fill
4. Verify rebalancer only creates TP2, TP3, TP4 with 33.33% each
5. Verify TP1 is not recreated
6. Check logs for "TPs already hit: ['TP1']" message
7. Repeat test with multiple TPs hitting