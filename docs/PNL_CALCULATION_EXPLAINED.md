# P&L Calculation Explanation

## Overview
The bot calculates potential profit and loss (P&L) based on your current positions and their associated take profit (TP) and stop loss (SL) orders.

## Key Metrics Explained

### 1. 🎯 TP1 Orders (X%)
- **What it means**: The profit if your ACTUAL TP1 orders execute
- **Coverage %**: Shows what percentage of your total position is covered by TP1 orders
- **Example**: If you have 100 units position but TP1 order is only for 25 units, coverage is 25%

### 2. 💯 Full Positions @ TP1
- **What it means**: The profit if ALL your positions exit at the TP1 price level
- **Difference from above**: This assumes 100% of position exits at TP1, not just the TP1 order quantity
- **Use case**: Shows the maximum profit potential if you manually close entire positions at TP1 price

### 3. 🚀 If All TPs Hit
- **What it means**: The sum of profits from ALL your TP orders at their respective prices
- **Calculation**: TP1 profit + TP2 profit + TP3 profit + TP4 profit (if they exist)
- **Conservative approach**: Different TPs may have different quantities and prices

### 4. 🛑 If All SL Hit
- **What it means**: The total loss if ALL positions hit their stop losses
- **Calculation**: Based on full position sizes, not partial
- **Risk management**: Shows your maximum risk exposure

### 5. 📊 Risk:Reward
- **What it means**: Ratio of potential full TP1 profit to potential SL loss
- **Formula**: Full Positions @ TP1 / If All SL Hit
- **Example**: 1:1.2 means for every $1 risked, potential reward is $1.20

## Important Notes

1. **Real-time Updates**: Calculations update every time you refresh the dashboard
2. **Mirror Accounts**: Mirror account positions are EXCLUDED from P&L calculations
3. **External Positions**: Only positions with BOT_ prefixed orders are included
4. **Position Sizing**: Uses actual position sizes from Bybit (not divided by leverage)

## Calculation Examples

### Long Position (Buy)
- Entry: $100, TP1: $110, SL: $95
- Position size: 10 units
- TP1 order size: 7 units (70% coverage)

**TP1 Orders P&L**: (110 - 100) × 7 = $70
**Full Position @ TP1**: (110 - 100) × 10 = $100
**If SL Hit**: (100 - 95) × 10 = $50 loss

### Short Position (Sell)
- Entry: $100, TP1: $90, SL: $105
- Position size: 10 units
- TP1 order size: 2.5 units (25% coverage)

**TP1 Orders P&L**: (100 - 90) × 2.5 = $25
**Full Position @ TP1**: (100 - 90) × 10 = $100
**If SL Hit**: (105 - 100) × 10 = $50 loss

## Validation Checks

The bot performs several validation checks:
1. Ensures TP1 order profit doesn't exceed full position profit
2. Verifies all TPs profit is greater than or equal to TP1 profit
3. Checks that TP orders are on the correct side of entry price
4. Validates order quantities don't exceed position sizes

## Dashboard Update Frequency

The P&L analysis updates:
- When you use the `/dashboard` command
- When monitors update position status
- The timestamp shows when calculations were last refreshed (HH:MM:SS format)