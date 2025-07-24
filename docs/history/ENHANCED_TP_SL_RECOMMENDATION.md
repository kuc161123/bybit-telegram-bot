# Enhanced TP/SL System Recommendation

## Executive Summary

After extensive research on professional trading bots like Cornix and analyzing Bybit's capabilities, I recommend implementing a **Hybrid Monitoring System with Dynamic Order Management** that replaces conditional orders with active monitoring and intelligent order placement.

## Current Issues with Conditional Orders

1. **Reliability Problems**: Conditional orders can fail to trigger or execute improperly
2. **Limited Flexibility**: Can't place both TP and SL for 100% of position simultaneously
3. **Poor Error Recovery**: When conditional orders fail, they create cascading errors
4. **Complex Management**: Difficult to adjust orders as position sizes change

## Recommended Solution: Enhanced TP/SL Manager

### Core Features

1. **Multiple Partial TP Orders** (Cornix-style)
   - Place actual limit orders for each TP level (not conditional)
   - Use Bybit's "Current Order/Partial Position" mode
   - Example for Conservative: 85%, 5%, 5%, 5% as separate limit orders

2. **Dynamic SL Management**
   - Single stop order covering entire position
   - Automatically adjusts quantity as TPs fill
   - Moves to breakeven after TP1 (85%) fills
   - Optional trailing stop functionality

3. **Active Position Monitoring**
   - Monitor position size changes to detect TP fills
   - Programmatic OCO (One-Cancels-Other) logic
   - Real-time order adjustments based on market conditions

## Implementation Details

### Phase 1: Basic Implementation (Immediate)

```python
# Instead of conditional orders:
Old: Place conditional TP/SL that may not trigger properly
New: Place actual limit orders for TPs + stop order for SL

# Benefits:
- Orders are visible in order book
- Can be modified/cancelled reliably
- No dependency on trigger conditions
- Better fill rates
```

### Phase 2: Enhanced Features (Next Sprint)

1. **Trailing Stop Enhancement**
   - After TP2 fills, trail SL by X%
   - Lock in profits dynamically

2. **Smart Order Routing**
   - Split large orders across price levels
   - Improve fill rates

3. **Advanced Risk Management**
   - Position-based SL (% of account)
   - Correlation-aware sizing

## Key Advantages

1. **Reliability**: Direct orders instead of conditionals = fewer failures
2. **Transparency**: All orders visible and manageable
3. **Flexibility**: Easy to adjust individual TP levels
4. **Recovery**: Better error handling and recovery options
5. **Professional**: Similar to how Cornix and other pro bots operate

## Technical Implementation

The new `enhanced_tp_sl_manager.py` module provides:

```python
# Setup multiple TPs with single function call
await enhanced_tp_sl_manager.setup_tp_sl_orders(
    symbol="BTCUSDT",
    side="Buy",
    position_size=Decimal("0.1"),
    entry_price=Decimal("50000"),
    tp_prices=[51000, 52000, 53000, 54000],  # 4 TP levels
    tp_percentages=[85, 5, 5, 5],           # Distribution
    sl_price=Decimal("49000"),
    chat_id=12345,
    approach="CONSERVATIVE"
)

# Automatic monitoring and adjustment
await enhanced_tp_sl_manager.monitor_and_adjust_orders("BTCUSDT", "Buy")
```

## Migration Strategy

1. **Keep existing system operational** during transition
2. **Add toggle** for new vs old system in settings
3. **Test with small positions** first
4. **Gradual rollout** by trading approach (Fast first, then Conservative)
5. **Monitor performance** and adjust as needed

## Risk Mitigation

1. **Fallback to old system** if issues detected
2. **Comprehensive logging** of all order operations
3. **Alert system** for any anomalies
4. **Manual override** capabilities

## Performance Benefits

1. **Reduced API calls**: No need to constantly check conditional order status
2. **Faster execution**: Direct orders execute immediately when price reached
3. **Better fills**: Limit orders can get better prices than market orders
4. **Lower latency**: No conditional trigger delay

## Conclusion

This enhanced TP/SL system addresses all the limitations of conditional orders while providing a more reliable, flexible, and professional trading experience. It's based on proven approaches used by successful trading bots like Cornix and leverages Bybit's full capabilities.

The implementation is designed to be:
- **Backwards compatible** (can run alongside existing system)
- **Incrementally adoptable** (can migrate one approach at a time)
- **Battle-tested** (based on patterns from professional bots)
- **Maintainable** (clear separation of concerns, good error handling)

This will significantly improve the reliability of TP/SL execution and reduce the "current position is zero" errors you've been experiencing.