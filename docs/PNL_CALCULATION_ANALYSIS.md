# P&L Calculation Analysis for Dashboard

## Current Implementation (Lines 269-319 in generator_analytics_compact.py)

### Key Variables:
- **position_size**: Total position size (e.g., 0.1 BTC)
- **leverage**: Leverage used (e.g., 10x)
- **margin_based_size**: `position_size / leverage` (e.g., 0.1 / 10 = 0.01 BTC)
- **avg_price**: Average entry price
- **tp_ratio**: Percentage of position represented by each TP order

### Current P&L Formula:

```python
# For Buy positions:
profit_pct = (tp_price - avg_price) / avg_price
potential_profit = margin_based_size * avg_price * profit_pct * tp_ratio

# For Sell positions:
profit_pct = (avg_price - tp_price) / avg_price
potential_profit = margin_based_size * avg_price * profit_pct * tp_ratio
```

## Issues Identified:

### 1. **Incorrect Use of margin_based_size**
The current formula uses `margin_based_size` (position_size / leverage) which represents the position size in terms of the asset (e.g., BTC), not the margin in USDT.

### 2. **Incorrect P&L Calculation**
The formula `margin_based_size * avg_price * profit_pct * tp_ratio` is conceptually wrong because:
- `margin_based_size * avg_price` gives you the margin in USDT
- Multiplying margin by profit percentage doesn't give you the actual P&L

## Correct P&L Calculation:

### For Perpetual Contracts (USDT-Margined):

**Correct Formula:**
```python
# For Buy positions:
pnl = (exit_price - entry_price) * position_size * tp_ratio

# For Sell positions:
pnl = (entry_price - exit_price) * position_size * tp_ratio
```

**Or using percentage:**
```python
# For Buy positions:
profit_pct = (exit_price - entry_price) / entry_price
pnl = position_size * entry_price * profit_pct * tp_ratio

# For Sell positions:
profit_pct = (entry_price - exit_price) / entry_price
pnl = position_size * entry_price * profit_pct * tp_ratio
```

### Example:
- Position: 0.1 BTC Long
- Entry Price: $50,000
- TP1 Price: $55,000 (10% profit)
- TP1 Size: 70% of position (0.07 BTC)
- Leverage: 10x

**Current (Incorrect) Calculation:**
```
margin_based_size = 0.1 / 10 = 0.01 BTC
profit_pct = (55000 - 50000) / 50000 = 0.1
potential_profit = 0.01 * 50000 * 0.1 * 0.7 = $35
```

**Correct Calculation:**
```
pnl = (55000 - 50000) * 0.07 = $350
# Or:
pnl = 0.07 * 50000 * 0.1 = $350
```

## Recommendations:

1. **Fix the P&L calculation formula** to use the correct position size (not margin-based size)
2. **Remove the division by leverage** when calculating P&L
3. **Use the standard P&L formula**: `(exit_price - entry_price) * size` for longs
4. **Verify with test data** to ensure calculations match Bybit's actual P&L

## Code Changes Needed:

Lines 276-283 should be:
```python
if side == 'Buy':
    # For long positions: profit = (exit_price - entry_price) * size * tp_ratio
    potential_profit_tp1 += (tp1_price - avg_price) * tp1_qty
else:
    # For short positions: profit = (entry_price - exit_price) * size * tp_ratio
    potential_profit_tp1 += (avg_price - tp1_price) * tp1_qty
```

Lines 292-299 should be:
```python
if side == 'Buy':
    # For long positions: profit = (exit_price - entry_price) * size
    potential_profit_all_tp += (tp_price - avg_price) * tp_qty
else:
    # For short positions: profit = (entry_price - exit_price) * size
    potential_profit_all_tp += (avg_price - tp_price) * tp_qty
```

Lines 310-319 should be:
```python
if side == 'Buy':
    # For long positions: loss = (entry_price - exit_price) * position_size
    potential_loss_sl += abs((avg_price - sl_price) * position_size)
else:
    # For short positions: loss = (exit_price - entry_price) * position_size
    potential_loss_sl += abs((sl_price - avg_price) * position_size)
```