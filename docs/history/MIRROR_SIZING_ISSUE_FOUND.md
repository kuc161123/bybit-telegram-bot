# Mirror Position Sizing Issue - Root Cause Found ✅

## The Problem
Mirror positions are at ~33% instead of 50% of main positions.

## Root Cause
The mirror sizing logic is **percentage-based on available balance**, not a fixed proportion of main position:

```python
# Current logic in trader.py:
if percentage_based_margin:
    mirror_margin_amount = (mirror_available * margin_percentage) / 100
    mirror_position_qty = (mirror_margin_amount * leverage) / entry_price
```

This means:
- If main uses 10% of balance
- Mirror also uses 10% of its balance
- But if mirror has less balance, position is smaller!

## Example
- Main balance: $10,000, uses 10% = $1,000 margin
- Mirror balance: $3,300, uses 10% = $330 margin
- Result: Mirror position is 33% of main (not 50%)

## Why It's 33%
This suggests mirror account has approximately 33% of the main account's balance.

## Solutions

### Option 1: Fixed Proportion (Recommended)
Change mirror sizing to always be 50% of main position:
```python
mirror_position_qty = position_qty * 0.5  # Always 50% of main
```

### Option 2: Adjustable Proportion
Add a setting `MIRROR_POSITION_PROPORTION = 0.5` that can be configured.

### Option 3: Keep Current Logic
If intentional, document that mirror positions scale with account balance.

## Immediate Fix Needed
For position sync, when main position increases, mirror should:
1. Calculate target size: `main_size * 0.5`
2. Place market order for the difference
3. Then adjust TP/SL orders

## Missing DOGEUSDT
Mirror never opened DOGEUSDT position - needs manual fix or automated recovery.