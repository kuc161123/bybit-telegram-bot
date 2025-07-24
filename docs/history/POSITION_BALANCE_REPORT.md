# Position Balance Report

**Date:** 2025-06-30  
**Accounts Analyzed:** Main & Mirror

## Summary

### Main Account
- **Total Positions:** 16
- **Properly Balanced:** 0 (0%)
- **Need Rebalancing:** 16 (100%)

### Mirror Account
- **Total Positions:** 16
- **Properly Balanced:** 0 (0%)
- **Need Rebalancing:** 16 (100%)

## Key Findings

### 1. Incorrect TP Distribution Pattern
Several positions show an inverted distribution pattern:
- **RUNEUSDT, ONEUSDT, PEOPLEUSDT** (both accounts)
  - Current: ~5% / 5% / 5% / 85%
  - Expected: 85% / 5% / 5% / 5%
  - The TP orders appear to be in reverse order

### 2. Missing TP/SL Orders
Most positions have **NO TP or SL orders** at all:
- **Main Account:** 12 out of 16 positions missing all TP orders
- **Mirror Account:** 12 out of 16 positions missing all TP orders
- Most also missing SL orders

### 3. Positions with Missing Orders

#### Both Accounts:
- NKNUSDT - No TP/SL orders
- NTRNUSDT - No TP/SL orders  
- NEARUSDT - No TP/SL orders
- DOTUSDT - No TP/SL orders
- HIGHUSDT - No TP/SL orders
- AUCTIONUSDT - No TP/SL orders
- WIFUSDT - No TP/SL orders
- VANRYUSDT - No TP/SL orders
- ZENUSDT - No TP/SL orders
- ENSUSDT - No TP/SL orders
- SUIUSDT - No TP/SL orders
- EGLDUSDT - No TP/SL orders

#### Partial Orders:
- BAKEUSDT - Has SL but no TP orders

## Issues Identified

1. **Inverted TP Distribution**: Some positions have TP orders but in wrong percentages (85% is last instead of first)
2. **Missing Orders**: Most positions lack any TP/SL orders entirely
3. **Quantity Mismatches**: Small discrepancies between total TP quantities and position sizes
4. **No Conservative Compliance**: 0% of positions follow the expected 85/5/5/5 distribution

## Recommendations

1. **Immediate Action Required**:
   - Run auto-rebalancer on all positions to create proper TP/SL orders
   - Fix the inverted distribution on RUNEUSDT, ONEUSDT, and PEOPLEUSDT
   - Create missing TP/SL orders for all other positions

2. **Verify Auto-Rebalancer**:
   - Check if auto-rebalancer is running properly
   - Ensure it's creating orders with correct distribution (85/5/5/5)
   - Verify order creation is not failing silently

3. **Monitor Going Forward**:
   - Set up alerts for positions without TP/SL orders
   - Regular balance checks to ensure compliance
   - Consider running this check daily

## Command to Fix

To trigger rebalancing for all positions:
```
/rebalancer_force
```

Or restart the auto-rebalancer:
```
/rebalancer_stop
/rebalancer_start
```