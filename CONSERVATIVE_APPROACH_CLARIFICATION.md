# Conservative Approach Order Structure Clarification

## User Interface Flow
The bot asks for "3 limit prices" during setup, but this is slightly misleading terminology.

## Actual Execution Structure
1. **First "limit" price** → Executes as a MARKET order (immediate fill)
2. **Second "limit" price** → Places as actual LIMIT order #1
3. **Third "limit" price** → Places as actual LIMIT order #2

## Total Orders
- **3 entry orders total**: 1 market + 2 limits
- **4 take profit orders**: TP1 (85%), TP2 (5%), TP3 (5%), TP4 (5%)
- **1 stop loss order**: Covers full position

## Why This Design?
- The first order needs to execute immediately to establish the position
- The remaining 2 orders are true limit orders for gradual position building
- This provides a balanced approach between immediate entry and dollar-cost averaging

## Fix Applied
The code has been updated to correctly track only the 2 actual limit orders in the Enhanced TP/SL monitoring system, not including the initial market order.

## Code Logic
```python
# In trader.py
if order_type == "Limit":
    limit_order_ids.append(order_id)  # Only actual limit orders
else:
    # It's a market order - don't add to limit_order_ids
```

This ensures the monitoring system correctly tracks:
- 2 limit orders (not 3 or 4)
- Proper order type identification
- Accurate order status tracking