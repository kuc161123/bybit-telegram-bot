# P&L Analysis Calculation Fix

## Issue Found
The Potential P&L Analysis was showing the same values for both main and mirror accounts because:
1. The `_calculate_pnl_analysis` function was returning a tuple but only calculating main account values
2. The mirror P&L was always set to `None` 
3. When called for mirror positions, it was still only processing them as if they were main positions

## Fix Applied
1. Renamed the function to `_calculate_pnl_analysis_single` to clarify it processes one account at a time
2. Changed the return type from tuple to single `PnLAnalysis` object
3. Now correctly calls the function separately for main and mirror positions
4. Each account's P&L is calculated independently based on its own positions and orders

## Result
Now the P&L Analysis section will show:
- **Main Account**: Calculated from main account positions and orders only
- **Mirror Account**: Calculated from mirror account positions and orders only
- Each account shows accurate potential profits/losses based on their actual positions

## Display Clarification
The display is correct in showing:
- **Current P&L** (in account overview): Shows actual unrealized P&L (can be negative)
- **Potential P&L** (in analysis section): Shows hypothetical future P&L if orders hit
  - TP values shown with + (potential profit)
  - SL values shown with - (potential loss)
  - These are future projections, not current values

## Code Changes
```python
# Before:
main_pnl, _ = await self._calculate_pnl_analysis(main_positions, main_orders)
mirror_pnl, _ = await self._calculate_pnl_analysis(mirror_positions, mirror_orders)

# After:
main_pnl = await self._calculate_pnl_analysis_single(main_positions, main_orders)
mirror_pnl = await self._calculate_pnl_analysis_single(mirror_positions, mirror_orders) if mirror_positions else None
```

The bot will now correctly calculate and display separate P&L analysis for each account.