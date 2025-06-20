# GGShot User Issue - Incorrect Value Assignment

## Problem Identified

Your screenshot contains these values (based on extraction):
- 0.9000 (Stop Loss - should be in grey box)
- 0.8500, 0.8000, 0.7500, 0.7000 (Mix of entries and TPs in red boxes)
- 0.6500, 0.6000, 0.5500, 0.5000 (More TPs in red boxes)

## Current Issues

1. **Pass 1 Result**:
   - Assigned 0.8000 as primary entry (might be wrong)
   - Assigned 0.8500 as limit_1 (should be lower than primary for SHORT)
   - Assigned 0.9000 as both limit_2 AND stop loss (clearly wrong)

2. **Pass 2 Result**:
   - Assigned 0.8500 as primary entry
   - Then 0.8000, 0.7500, 0.7000 as limit entries (all lower than primary - wrong for SHORT)

## What Should Happen for SHORT Trades

For LDOUSDT SHORT with these values:

1. **Stop Loss**: 0.9000 (grey box) - HIGHEST value
2. **Entries** (red boxes, ordered lowest to highest):
   - Primary Entry: Should be the LOWEST entry value
   - Limit 1: Next higher value
   - Limit 2: Highest entry value (but still below SL)
3. **Take Profits** (red boxes, ordered highest to lowest):
   - TP1: Highest TP value
   - TP2: Next lower
   - TP3: Next lower
   - TP4: Lowest value

## Likely Correct Assignment

Based on typical trading setups:
- SL: 0.9000 (grey box)
- Entries: 0.7500 (primary), 0.8000 (limit 1), 0.8500 (limit 2)
- TPs: 0.7000 (TP1), 0.6500 (TP2), 0.6000 (TP3), 0.5500 (TP4)

## The Real Issue

The OCR is finding the numbers but the system isn't:
1. Detecting which numbers are in RED boxes vs GREY box
2. Properly determining which red box values are entries vs TPs
3. Ordering them correctly for SHORT trades

## Quick Workaround

Until the color detection is more accurate, you can:

1. **Use Manual Entry** instead of screenshot for complex setups
2. **Take clearer screenshots**:
   - Ensure red and grey boxes are clearly visible
   - Use light mode if possible
   - Zoom in on the price levels
   - Make sure boxes have good contrast

3. **Simplify your setup**:
   - Use fewer entry levels
   - Make sure there's clear separation between entry and TP zones

## What Needs Fixing

The system needs to:
1. Better detect the actual COLOR of boxes (red vs grey)
2. Use color info to categorize prices correctly
3. Apply proper SHORT trade logic for ordering