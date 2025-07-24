#!/usr/bin/env python3
"""
Test GGShot for both LONG and SHORT trades
"""
import asyncio
import logging
from decimal import Decimal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_long_trade_logic():
    """Test LONG trade entry and TP ordering"""
    logger.info("\n" + "="*60)
    logger.info("Testing LONG Trade Logic")
    logger.info("="*60)
    
    # Simulate LONG trade data
    sl_price = 60000  # Stop loss at bottom
    red_box_values = [
        61000,  # Entry 3 (furthest from current)
        61500,  # Entry 2
        62000,  # Entry 1 (closest to current/highest)
        63000,  # TP1 (lowest TP)
        64000,  # TP2
        65000,  # TP3
        66000   # TP4 (highest TP)
    ]
    
    # Separate entries and TPs
    entries = []
    tps = []
    
    # For LONG: entries are closer to SL (lower values), TPs are farther (higher values)
    for value in sorted(red_box_values):
        if value > sl_price:
            if len(entries) < 3:
                entries.append(value)
            else:
                tps.append(value)
    
    # Sort entries for LONG
    entries.sort(reverse=True)  # Highest to lowest
    tps.sort()  # Lowest to highest
    
    logger.info(f"Stop Loss: {sl_price}")
    logger.info(f"\nEntries (sorted for LONG):")
    logger.info(f"  Primary Entry: {entries[0]} (highest/closest to current)")
    logger.info(f"  Limit Entry 1: {entries[1] if len(entries) > 1 else 'N/A'} (should be < primary)")
    logger.info(f"  Limit Entry 2: {entries[2] if len(entries) > 2 else 'N/A'} (should be < limit 1)")
    
    logger.info(f"\nTake Profits (sorted for LONG):")
    for i, tp in enumerate(tps):
        logger.info(f"  TP{i+1}: {tp}")
    
    # Validate ordering
    logger.info("\nValidation checks:")
    
    # Check entry ordering for LONG (descending)
    if len(entries) >= 2:
        entry_order_ok = entries[0] > entries[1]
        if len(entries) >= 3:
            entry_order_ok = entry_order_ok and entries[1] > entries[2]
        logger.info(f"Entry order (primary > limit1 > limit2): {'✅' if entry_order_ok else '❌'}")
    
    # Check TP ordering for LONG (ascending)
    if len(tps) >= 2:
        tp_order_ok = all(tps[i] < tps[i+1] for i in range(len(tps)-1))
        logger.info(f"TP order (TP1 < TP2 < TP3 < TP4): {'✅' if tp_order_ok else '❌'}")
    
    # Check all values relative to SL
    all_above_sl = all(e > sl_price for e in entries) and all(t > sl_price for t in tps)
    logger.info(f"All values above SL: {'✅' if all_above_sl else '❌'}")

def test_short_trade_logic():
    """Test SHORT trade entry and TP ordering"""
    logger.info("\n" + "="*60)
    logger.info("Testing SHORT Trade Logic")
    logger.info("="*60)
    
    # Simulate SHORT trade data
    sl_price = 70000  # Stop loss at top
    red_box_values = [
        69000,  # Entry 3 (furthest from current)
        68500,  # Entry 2
        68000,  # Entry 1 (closest to current/lowest)
        67000,  # TP1 (highest TP)
        66000,  # TP2
        65000,  # TP3
        64000   # TP4 (lowest TP)
    ]
    
    # Separate entries and TPs
    entries = []
    tps = []
    
    # For SHORT: entries are closer to SL (higher values), TPs are farther (lower values)
    for value in sorted(red_box_values, reverse=True):
        if value < sl_price:
            if len(entries) < 3:
                entries.append(value)
            else:
                tps.append(value)
    
    # Sort entries for SHORT
    entries.sort()  # Lowest to highest
    tps.sort(reverse=True)  # Highest to lowest
    
    logger.info(f"Stop Loss: {sl_price}")
    logger.info(f"\nEntries (sorted for SHORT):")
    logger.info(f"  Primary Entry: {entries[0]} (lowest/closest to current)")
    logger.info(f"  Limit Entry 1: {entries[1] if len(entries) > 1 else 'N/A'} (should be > primary)")
    logger.info(f"  Limit Entry 2: {entries[2] if len(entries) > 2 else 'N/A'} (should be > limit 1)")
    
    logger.info(f"\nTake Profits (sorted for SHORT):")
    for i, tp in enumerate(tps):
        logger.info(f"  TP{i+1}: {tp}")
    
    # Validate ordering
    logger.info("\nValidation checks:")
    
    # Check entry ordering for SHORT (ascending)
    if len(entries) >= 2:
        entry_order_ok = entries[0] < entries[1]
        if len(entries) >= 3:
            entry_order_ok = entry_order_ok and entries[1] < entries[2]
        logger.info(f"Entry order (primary < limit1 < limit2): {'✅' if entry_order_ok else '❌'}")
    
    # Check TP ordering for SHORT (descending)
    if len(tps) >= 2:
        tp_order_ok = all(tps[i] > tps[i+1] for i in range(len(tps)-1))
        logger.info(f"TP order (TP1 > TP2 > TP3 > TP4): {'✅' if tp_order_ok else '❌'}")
    
    # Check all values relative to SL
    all_below_sl = all(e < sl_price for e in entries) and all(t < sl_price for t in tps)
    logger.info(f"All values below SL: {'✅' if all_below_sl else '❌'}")

def main():
    """Run all tests"""
    test_long_trade_logic()
    test_short_trade_logic()
    
    logger.info("\n" + "="*60)
    logger.info("Summary of Expected Ordering")
    logger.info("="*60)
    
    logger.info("\nLONG Trades:")
    logger.info("- Stop Loss: LOWEST value (at bottom)")
    logger.info("- Primary Entry: HIGHEST entry (closest to current)")
    logger.info("- Limit Entries: DESCENDING order (limit1 > limit2 > limit3)")
    logger.info("- Take Profits: ASCENDING order (TP1 < TP2 < TP3 < TP4)")
    logger.info("- All values ABOVE stop loss")
    
    logger.info("\nSHORT Trades:")
    logger.info("- Stop Loss: HIGHEST value (at top)")
    logger.info("- Primary Entry: LOWEST entry (closest to current)")
    logger.info("- Limit Entries: ASCENDING order (limit1 < limit2 < limit3)")
    logger.info("- Take Profits: DESCENDING order (TP1 > TP2 > TP3 > TP4)")
    logger.info("- All values BELOW stop loss")

if __name__ == "__main__":
    main()