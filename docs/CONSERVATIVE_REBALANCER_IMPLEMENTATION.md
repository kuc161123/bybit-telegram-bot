# Conservative Approach Auto-Rebalancer Implementation

## Overview

The Conservative approach auto-rebalancer has been implemented to automatically adjust TP/SL order quantities when:
1. Limit orders are filled
2. Positions are merged

The rebalancer maintains the 85/5/5/5 TP distribution and 100% SL coverage for the Conservative trading approach.

## Key Features

### 1. Automatic Triggering
- **On Limit Fills**: When any limit order fills, the rebalancer adjusts TP/SL quantities
- **On Position Merge**: When positions merge, the rebalancer recalculates distributions

### 2. Main Account Features
- Sends detailed alerts when rebalancing occurs
- Shows new position sizes and order quantities
- Explains why rebalancing was triggered

### 3. Mirror Account Features
- Operates silently (no alerts)
- Same rebalancing logic as main account
- Triggered on same events

## Implementation Details

### Files Modified

1. **`execution/conservative_rebalancer.py`** (NEW)
   - Core rebalancing logic
   - Functions for limit fill and merge scenarios
   - Mirror account support

2. **`execution/monitor.py`**
   - Added limit fill detection and rebalancer triggering (lines 783-801)
   - Added mirror account limit fill detection (lines 2670-2719)

3. **`execution/trader.py`**
   - Added rebalancer triggering after merge (lines 3531-3560)
   - Includes both main and mirror account rebalancing

4. **`utils/alert_helpers.py`**
   - Added Conservative rebalance alert type handling
   - New formatter for detailed rebalance alerts

## How It Works

### On Limit Fill

1. Monitor detects filled limit orders
2. Triggers `rebalance_conservative_on_limit_fill()`
3. Cancels existing TP/SL orders
4. Calculates new quantities based on actual position size
5. Places new TP orders with 85/5/5/5 distribution
6. Places new SL order at 100% of position
7. Sends alert (main account only)

### On Position Merge

1. Trader completes position merge
2. Triggers `rebalance_conservative_on_merge()`
3. Uses same logic as limit fill rebalancing
4. Alert indicates merge as trigger

### Alert Format

```
🛡️ CONSERVATIVE REBALANCE
━━━━━━━━━━━━━━━━━━━━━━
📊 BTCUSDT 📈 Buy

✅ Trigger: Limit Order Fill (2/3)
📦 Position Size: 0.0150

🎯 NEW TP DISTRIBUTION (85/5/5/5)
├─ TP1: 0.0128 (85%)
├─ TP2: 0.0008 (5%)
├─ TP3: 0.0007 (5%)
└─ TP4: 0.0007 (5%)

🛡️ STOP LOSS
└─ SL: 0.0150 (100%)

🗑️ CANCELLED ORDERS
• TP1
• TP2
• TP3
• TP4
• SL

✅ NEW ORDERS PLACED
• TP1 (0.0128)
• TP2 (0.0008)
• TP3 (0.0007)
• TP4 (0.0007)
• SL (0.0150)

📌 Why Rebalanced?
Limit order filled, adjusting TP/SL quantities to maintain 85/5/5/5 distribution for the updated position size.

✨ Conservative approach maintained with updated quantities.
```

## Configuration

No configuration required - the rebalancer automatically activates for Conservative positions.

## Testing

To test the rebalancer:

1. Place a Conservative trade
2. Wait for limit orders to fill
3. Verify rebalancing alert is received
4. Check that new TP/SL quantities match position size

## Important Notes

1. **Preserves Trigger Prices**: Original TP/SL prices are maintained, only quantities change
2. **Main Account Only Alerts**: Mirror account rebalances silently
3. **85/5/5/5 Distribution**: Always maintains this TP distribution
4. **100% SL Coverage**: Stop loss always covers full position

## Future Enhancements

- Could add configuration to disable/enable rebalancing
- Could allow custom TP distributions
- Could add more granular alerts for each rebalanced order