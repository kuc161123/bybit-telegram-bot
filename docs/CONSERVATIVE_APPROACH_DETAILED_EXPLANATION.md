# Conservative Approach - Complete Detailed Explanation

## Overview
The Conservative Approach is designed for risk-managed trading with gradual profit-taking. Unlike the Fast approach which uses a single entry and exit, Conservative uses multiple entry points and multiple take-profit levels.

## Key Components

### 1. Entry Strategy: Multiple Limit Orders
- **3 Limit Entry Orders** at different price levels
- Each limit order gets 1/3 of your total position size
- Allows for cost averaging if price moves against you initially

### 2. Exit Strategy: 4 Take Profits + 1 Stop Loss
- **TP1**: 85% of position (main profit target)
- **TP2**: 5% of position  
- **TP3**: 5% of position
- **TP4**: 5% of position
- **SL**: 100% of remaining position (protection)

### 3. Position Distribution
When all limit orders fill, your position is distributed as:
- 85% exits at TP1 (securing most profits)
- 15% rides to higher targets (TP2, TP3, TP4)
- Stop loss always covers 100% of remaining position

## Step-by-Step Process

### Step 1: User Input Collection
When you select Conservative approach, the bot asks for:
1. **Symbol** (e.g., BTCUSDT)
2. **Direction** (Long/Short)
3. **Margin Amount** (e.g., $100)
4. **Leverage** (e.g., 10x)
5. **3 Limit Entry Prices** (Limit 1, Limit 2, Limit 3)
6. **4 Take Profit Prices** (TP1, TP2, TP3, TP4)
7. **1 Stop Loss Price**

### Step 2: Pre-Trade Checks
Before placing orders, the bot:
1. **Checks for existing orders** on the same symbol
2. **Handles conflicts**:
   - If Fast approach exists → Cancels it
   - If mixed approaches → Cleans all orders
   - If Conservative exists → Checks for merge opportunity
3. **Sets leverage** on both accounts (main + mirror if enabled)

### Step 3: Position Size Calculation
```
Total Position Size = Margin × Leverage
Average Limit Price = (Limit1 + Limit2 + Limit3) / 3
Total Quantity = Total Position Size / Average Limit Price
Quantity per Limit = Total Quantity / 3
```

Example with $100 margin, 10x leverage:
- Total Position Size = $100 × 10 = $1,000
- If average price = $50,000, Total Qty = 0.02 BTC
- Each limit order = 0.00667 BTC

### Step 4: Order Placement Sequence

#### A. Limit Orders (Entry)
The bot places 3 limit orders:
```
Limit 1: Buy/Sell 0.00667 BTC at Price1
Limit 2: Buy/Sell 0.00667 BTC at Price2  
Limit 3: Buy/Sell 0.00667 BTC at Price3
```

#### B. Take Profit Orders (Exit)
Once ANY limit order fills, the bot places TPs:
```
TP1: 85% of filled quantity
TP2: 5% of filled quantity
TP3: 5% of filled quantity
TP4: 5% of filled quantity
```

#### C. Stop Loss Order
Places SL for 100% of filled quantity

### Step 5: Monitoring & Management

#### A. Limit Order Monitoring
- Bot checks every 10 seconds for filled limit orders
- When a limit fills → Places corresponding TP/SL orders
- Updates position tracking

#### B. TP1 Hit → Move SL to Breakeven
Special feature: When TP1 (85%) fills:
1. Bot detects the fill
2. Moves SL to entry price + fees (breakeven)
3. Remaining 15% position is now risk-free

#### C. Order Quantity Adjustments
As limits fill at different times:
- Bot recalculates TP/SL quantities
- Ensures 100% position coverage
- Adjusts for partial fills

### Step 6: Position Merging

If you already have a Conservative position and place another:
1. **Merge Decision** based on:
   - MORE aggressive TP (higher for long, lower for short)
   - SAFER SL (lower for long, higher for short)

2. **If both conditions met**:
   - Updates to new TP/SL prices
   - Increases position size
   - Rebalances order quantities

3. **If conditions NOT met**:
   - Keeps original TP/SL prices
   - Only increases position size

## Example Trade Flow

### Long Trade Example:
1. **Setup**: BTCUSDT, $100 margin, 10x leverage
2. **Entries**: $49,900, $49,800, $49,700
3. **TPs**: $51,000, $51,500, $52,000, $52,500
4. **SL**: $49,000

**What happens:**
- Places 3 buy limit orders
- Price drops to $49,900 → Limit 1 fills
- Bot places TPs for that portion
- Price drops to $49,800 → Limit 2 fills
- Bot updates TPs to include new quantity
- If TP1 at $51,000 hits → 85% position closes
- SL moves to $49,850 (breakeven)
- Remaining 15% rides to higher targets risk-free

## Mirror Trading Integration

If mirror trading is enabled:
1. **Proportional Sizing**: Mirror account uses its own balance percentage
2. **Synchronized Orders**: All orders replicated on mirror account
3. **Independent Monitoring**: Each account monitored separately
4. **No Alerts**: Mirror account operates silently

## Key Differences from Fast Approach

| Feature | Conservative | Fast |
|---------|--------------|------|
| Entry | 3 Limit Orders | 1 Market Order |
| Take Profits | 4 Levels (85/5/5/5%) | 1 Level (100%) |
| Risk Management | Gradual, breakeven after TP1 | All or nothing |
| Best For | Swing trades, trends | Quick scalps |
| Order Complexity | High (up to 8 orders) | Low (3 orders) |

## Important Notes

1. **Order Limits**: Bybit allows max 10 open orders per symbol
2. **Minimum Values**: Each order must be ≥ $5 USDT
3. **Precision**: Bot handles decimal precision automatically
4. **Fees**: Considered in breakeven calculations
5. **Monitoring**: Continues until position fully closed

## Risk Management Features

1. **Gradual Entry**: Averages your entry price
2. **Majority Exit at TP1**: 85% secures profits early
3. **Breakeven Protection**: After TP1, no more risk
4. **Full SL Coverage**: Always 100% protection
5. **Smart Merging**: Only improves risk/reward

This approach is ideal for traders who want to:
- Build positions gradually
- Secure profits while leaving upside potential
- Minimize risk after initial profit target
- Trade longer timeframes with patience