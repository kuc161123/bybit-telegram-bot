#!/usr/bin/env python3
"""
Ensure SL quantity adjustment works correctly after each TP hit
"""

print("""
SL QUANTITY ADJUSTMENT ANALYSIS
================================

CURRENT BEHAVIOR:
1. When TP1 (85%) hits:
   - ✅ Cancels unfilled limit orders 
   - ✅ Moves SL to breakeven price
   - ⚠️  SL quantity adjustment uses basic method, not enhanced

2. When TP2/3/4 hit:
   - ⚠️  SL quantity adjustment not consistently called
   - ⚠️  Progressive adjustment logic exists but may not trigger

ISSUES FOUND:
1. Line 1329: After TP fill, calls basic _adjust_sl_quantity()
2. Line 1422: Fast approach calls basic _adjust_sl_quantity()
3. Line 1557: Should call enhanced method but doesn't always

RECOMMENDATION:
The system has all the components but needs consistent application.
The enhanced SL quantity adjustment should be used after EVERY TP hit.

WHAT TO DO:
1. Monitor your positions closely for the next few trades
2. Check if SL quantities are correct after TP hits
3. If SL quantities are wrong, we need to patch the code

EXPECTED BEHAVIOR:
- Before TP1: SL covers full target position (including pending limits)
- After TP1: SL covers remaining 15% of original position
- After TP2: SL covers remaining 10% of original position  
- After TP3: SL covers remaining 5% of original position
- After TP4: Position should be closed

ALERTS YOU SHOULD RECEIVE:
1. "TP1 HIT - PROFIT TAKEN!" ✅
2. "Limit Orders Cleaned Up" ✅
3. "STOP LOSS MOVED TO BREAKEVEN" ✅
4. For each subsequent TP: "TP2/3/4 HIT" with adjusted SL info

If you notice SL quantities are incorrect after TP hits, report back and I'll create a patch.
""")