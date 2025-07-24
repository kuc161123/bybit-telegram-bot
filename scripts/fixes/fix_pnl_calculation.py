#!/usr/bin/env python3
"""
Script to demonstrate the P&L calculation issue and fix
"""

def demonstrate_pnl_issue():
    """Show the difference between current and correct P&L calculations"""
    
    # Example position
    position_size = 1.0  # 1 BTC
    avg_price = 50000   # Entry at $50,000
    tp1_price = 51000   # TP1 at $51,000
    sl_price = 49000    # SL at $49,000
    leverage = 10       # 10x leverage
    
    print("=== P&L CALCULATION COMPARISON ===\n")
    print(f"Position: {position_size} BTC")
    print(f"Entry Price: ${avg_price:,}")
    print(f"TP1 Price: ${tp1_price:,}")
    print(f"SL Price: ${sl_price:,}")
    print(f"Leverage: {leverage}x")
    
    # Current (incorrect) calculation
    print("\n--- CURRENT (INCORRECT) CALCULATION ---")
    unleveraged_size = position_size / leverage
    tp1_pnl_wrong = (tp1_price - avg_price) * unleveraged_size
    sl_pnl_wrong = (avg_price - sl_price) * unleveraged_size
    
    print(f"Unleveraged Size: {unleveraged_size} BTC (dividing by leverage)")
    print(f"TP1 P&L: ${tp1_pnl_wrong:,.2f}")
    print(f"SL P&L: -${sl_pnl_wrong:,.2f}")
    
    # Correct calculation
    print("\n--- CORRECT CALCULATION ---")
    tp1_pnl_correct = (tp1_price - avg_price) * position_size
    sl_pnl_correct = (avg_price - sl_price) * position_size
    
    print(f"Actual Size: {position_size} BTC (no division needed)")
    print(f"TP1 P&L: ${tp1_pnl_correct:,.2f}")
    print(f"SL P&L: -${sl_pnl_correct:,.2f}")
    
    # Show the difference
    print("\n--- IMPACT ---")
    print(f"TP1 P&L Difference: ${tp1_pnl_correct - tp1_pnl_wrong:,.2f} ({leverage}x higher)")
    print(f"SL P&L Difference: ${sl_pnl_correct - sl_pnl_wrong:,.2f} ({leverage}x higher)")
    
    # Scale to 24 positions
    print("\n--- SCALED TO 24 POSITIONS ---")
    print(f"Current calculation total TP1: ${tp1_pnl_wrong * 24:,.2f}")
    print(f"Correct calculation total TP1: ${tp1_pnl_correct * 24:,.2f}")
    print(f"Difference: ${(tp1_pnl_correct - tp1_pnl_wrong) * 24:,.2f}")
    
    print("\n⚠️  The issue: Position sizes from Bybit are already in base units (BTC, ETH, etc.)")
    print("   They should NOT be divided by leverage for P&L calculations!")
    print("   Only the initial margin (positionIM) reflects the leverage effect.")

if __name__ == "__main__":
    demonstrate_pnl_issue()