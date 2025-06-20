# GGShot Complete Guide - LONG & SHORT Trades

## Visual Indicators

The GGShot system uses **colored boxes** to identify different price levels:

- 🔴 **RED BOXES** = Entry prices and Take Profit levels
- ⬜ **GREY BOXES** = Stop Loss price

## LONG Trade Rules (Buy)

### Position Layout
```
TP4 ━━━━━━━━━ [red box] 66000  ← Highest TP (farthest from entry)
TP3 ━━━━━━━━━ [red box] 65000
TP2 ━━━━━━━━━ [red box] 64000  
TP1 ━━━━━━━━━ [red box] 63000  ← Lowest TP (closest to entry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Current Price (~62100)
Entry ━━━━━━━ [red box] 62000  ← Primary (highest entry)
Limit 1 ━━━━━ [red box] 61500  ← Lower than primary
Limit 2 ━━━━━ [red box] 61000  ← Lower than limit 1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SL ━━━━━━━━━━ [grey box] 60000 ← Stop Loss at BOTTOM
```

### LONG Trade Ordering
1. **Stop Loss**: LOWEST value (grey box at bottom)
2. **Entries**: 
   - Primary Entry: HIGHEST entry value (closest to current price)
   - Limit Entry 1: LOWER than primary
   - Limit Entry 2: LOWER than limit 1
   - Order: Primary > Limit 1 > Limit 2 (descending)
3. **Take Profits**:
   - TP1: LOWEST TP value
   - TP2: HIGHER than TP1
   - TP3: HIGHER than TP2
   - TP4: HIGHEST TP value
   - Order: TP1 < TP2 < TP3 < TP4 (ascending)

## SHORT Trade Rules (Sell)

### Position Layout
```
SL ━━━━━━━━━━ [grey box] 3500  ← Stop Loss at TOP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Limit 2 ━━━━━ [red box] 3440   ← Higher than limit 1
Limit 1 ━━━━━ [red box] 3420   ← Higher than primary
Entry ━━━━━━━ [red box] 3400   ← Primary (lowest entry)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ Current Price (~3395)
TP1 ━━━━━━━━━ [red box] 3300   ← Highest TP (closest to entry)
TP2 ━━━━━━━━━ [red box] 3200
TP3 ━━━━━━━━━ [red box] 3100
TP4 ━━━━━━━━━ [red box] 3000   ← Lowest TP (farthest from entry)
```

### SHORT Trade Ordering
1. **Stop Loss**: HIGHEST value (grey box at top)
2. **Entries**:
   - Primary Entry: LOWEST entry value (closest to current price)
   - Limit Entry 1: HIGHER than primary
   - Limit Entry 2: HIGHER than limit 1
   - Order: Primary < Limit 1 < Limit 2 (ascending)
3. **Take Profits**:
   - TP1: HIGHEST TP value
   - TP2: LOWER than TP1
   - TP3: LOWER than TP2
   - TP4: LOWEST TP value
   - Order: TP1 > TP2 > TP3 > TP4 (descending)

## Quick Reference

### LONG (Buy) Summary
- SL: Bottom (lowest price)
- Entries: Start high, go lower (62000 → 61500 → 61000)
- TPs: Start low, go higher (63000 → 64000 → 65000 → 66000)
- All values ABOVE stop loss

### SHORT (Sell) Summary
- SL: Top (highest price)
- Entries: Start low, go higher (3400 → 3420 → 3440)
- TPs: Start high, go lower (3300 → 3200 → 3100 → 3000)
- All values BELOW stop loss

## How the System Works

1. **Color Detection**: AI identifies red and grey boxes
2. **Position Analysis**: Determines which red boxes are entries vs TPs based on position relative to SL
3. **Proper Ordering**: Sorts values according to trade direction rules
4. **Validation**: Ensures all ordering rules are followed

## Testing

Use these scripts to test the system:

```bash
# Test logic for both trade types
python test_ggshot_long_short.py

# Create visual test screenshots
python test_ggshot_visual.py

# Test complete system
python test_ggshot_final.py
```

## Troubleshooting

If extraction is incorrect:
1. Check that colored boxes are clearly visible
2. Ensure all values are within their expected ranges
3. Look at debug_enhanced_*.png files to see what AI sees
4. Verify stop loss position matches trade direction

The system is now fully configured to handle both LONG and SHORT trades with proper ordering!