# Startup Conservative Rebalancer Implementation

## Overview

The startup Conservative rebalancer automatically checks and fixes Conservative positions on bot startup that have mismatched TP/SL quantities.

## How It Works

### On Bot Startup

1. **Waits 3 seconds** for bot initialization
2. **Scans all positions** to find Conservative ones
3. **Checks TP/SL quantities** against actual position size
4. **Triggers rebalancing** if quantities don't match

### Detection Logic

A position is identified as Conservative if:
- It has 4 TP orders (typical for Conservative)
- OrderLinkId contains 'CONS' or 'conservative'
- Multiple TP orders exist

### Rebalance Criteria

Rebalancing is triggered when:
- TP1 quantity ≠ 85% of position size (±5% tolerance)
- SL quantity ≠ 100% of position size (±5% tolerance)
- Wrong number of TP orders (not 4)

### Example: INJUSDT

Your current situation:
- Position: 20.1 (only 1/3 filled)
- TP1: 51.3 (calculated for full 60.4)
- SL: 60.4 (for full position)

After startup rebalancing:
- Position: 20.1 (unchanged)
- TP1: 17.1 (85% of 20.1)
- TP2-4: 1.0 each (5% of 20.1)
- SL: 20.1 (100% of actual position)

## Integration

The rebalancer is integrated into:
1. `main.py` - Runs during startup sequence
2. `startup_conservative_rebalancer.py` - Core logic
3. Works with existing `conservative_rebalancer.py`

## Benefits

1. **Prevents order failures** - TP orders match actual position size
2. **Automatic fix** - No manual intervention needed
3. **Preserves prices** - Only quantities are adjusted
4. **Works for all Conservative positions** - Not just new ones

## Usage

Simply restart the bot and it will:
1. Detect Conservative positions with wrong quantities
2. Automatically rebalance them
3. Send alerts for main account rebalances
4. Fix the INJUSDT issue you're experiencing

## Important Notes

- Only runs once on startup
- Won't affect positions that are already correctly balanced
- Preserves all trigger prices
- Works for both main and mirror accounts