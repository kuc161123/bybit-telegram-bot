#!/usr/bin/env python3
"""
How to improve R:R when TP and SL distances are fixed
The only variable left: Entry price
"""
from decimal import Decimal

def analyze_fixed_tpsl_strategies():
    """Analyze R:R improvement strategies with fixed TP/SL"""
    
    print("\n" + "="*80)
    print("IMPROVING R:R WITH FIXED TP/SL PLACEMENT")
    print("="*80)
    
    print("\n⚠️ THE CONSTRAINT:")
    print("You want to keep:")
    print("• TP at your chosen level (e.g., resistance)")
    print("• SL at your chosen level (e.g., below support)")
    print("\nThis means the ONLY way to improve R:R is to get a BETTER ENTRY PRICE")
    
    # Example scenario
    market_price = Decimal("100")
    tp_price = Decimal("103")  # Fixed at +3%
    sl_price = Decimal("95")   # Fixed at -5%
    
    print(f"\n📊 EXAMPLE SCENARIO:")
    print(f"Market Price: ${market_price}")
    print(f"Take Profit:  ${tp_price} (FIXED)")
    print(f"Stop Loss:    ${sl_price} (FIXED)")
    
    print("\n" + "="*80)
    print("STRATEGY COMPARISON")
    print("="*80)
    
    strategies = [
        {
            "name": "1. CURRENT APPROACH",
            "description": "25% market + 3 limits at 1%, 2%, 3%",
            "entry": Decimal("98.5"),  # Average from previous analysis
            "method": "Standard conservative entry"
        },
        {
            "name": "2. PATIENCE STRATEGY",
            "description": "Wait for price to come to you",
            "entry": Decimal("97"),
            "method": "Set limit order at -3% and wait"
        },
        {
            "name": "3. SCALE-IN ON PULLBACK",
            "description": "No market order, all limits below",
            "entry": Decimal("96.5"),
            "method": "100% limit orders at 2%, 3%, 4%, 5%"
        },
        {
            "name": "4. WAIT FOR BETTER SETUP",
            "description": "Skip trade, wait for price at support",
            "entry": Decimal("95.5"),
            "method": "Enter only when price touches SL area"
        },
        {
            "name": "5. MARKET TIMING",
            "description": "Enter during dips/fear",
            "entry": Decimal("97.5"),
            "method": "Buy red candles, not green ones"
        }
    ]
    
    print("\nR:R Analysis for Each Strategy:")
    print("-" * 60)
    
    results = []
    for strategy in strategies:
        entry = strategy["entry"]
        
        # Calculate R:R with fixed TP/SL
        risk = entry - sl_price
        reward = tp_price - entry
        rr_ratio = reward / risk if risk > 0 else 0
        
        print(f"\n{strategy['name']}")
        print(f"Method: {strategy['method']}")
        print(f"Entry Price: ${entry}")
        print(f"Risk: ${risk:.2f} ({float(risk/entry*100):.1f}%)")
        print(f"Reward: ${reward:.2f} ({float(reward/entry*100):.1f}%)")
        print(f"R:R Ratio: 1:{rr_ratio:.2f}", end=" ")
        
        if rr_ratio >= 2:
            print("🟢 EXCELLENT")
        elif rr_ratio >= 1.5:
            print("🟡 GOOD")
        elif rr_ratio >= 1:
            print("🟠 MARGINAL")
        else:
            print("🔴 POOR")
        
        results.append({
            "name": strategy["name"],
            "entry": entry,
            "rr": rr_ratio
        })
    
    print("\n" + "="*80)
    print("🎯 PRACTICAL STRATEGIES TO IMPROVE R:R WITH FIXED TP/SL")
    print("="*80)
    
    print("\n1. ⏰ PATIENCE & TIMING:")
    print("   • Don't chase price - let it come to you")
    print("   • Set alerts at key levels and wait")
    print("   • Enter on red days, not green days")
    print("   • Use limit orders only, no market orders")
    
    print("\n2. 📊 TECHNICAL ENTRY TACTICS:")
    print("   a) Enter at support levels (for longs)")
    print("   b) Wait for pullbacks to moving averages")
    print("   c) Use RSI oversold bounces")
    print("   d) Enter on volume capitulation")
    
    print("\n3. 🎯 SELECTIVE TRADING:")
    print("   • Only take trades where entry is favorable")
    print("   • Skip setups where price is too far from SL")
    print("   • Rule: Entry must be in bottom 1/3 of SL-TP range")
    
    print("\n4. 📈 ADVANCED ENTRY TECHNIQUES:")
    print("   • Use wider limit spacing (3%, 5%, 7%)")
    print("   • Weight allocation toward lower limits")
    print("   • Example: 10% at -1%, 30% at -3%, 60% at -5%")
    
    print("\n5. 🔄 ALTERNATIVE APPROACHES:")
    print("   • Split position: 50% at market, 50% on 5% pullback")
    print("   • DCA approach: Add only if price drops")
    print("   • Momentum fade: Enter counter-trend exhaustion")
    
    print("\n" + "="*80)
    print("📐 THE MATH - ENTRY ZONE CALCULATION")
    print("="*80)
    
    print("\nFor favorable R:R with fixed TP/SL:")
    
    # Calculate ideal entry zone
    sl_distance = market_price - sl_price
    tp_distance = tp_price - market_price
    total_range = tp_price - sl_price
    
    # For different R:R targets
    target_rrs = [Decimal("1"), Decimal("1.5"), Decimal("2"), Decimal("3")]
    
    print(f"\nGiven: TP at ${tp_price}, SL at ${sl_price}")
    print(f"Range: ${total_range}")
    
    for target_rr in target_rrs:
        # Entry = SL + (Range / (1 + RR))
        ideal_entry = sl_price + (total_range / (1 + target_rr))
        distance_from_market = market_price - ideal_entry
        percent_below = (distance_from_market / market_price * 100)
        
        print(f"\nFor {target_rr}:1 R:R ratio:")
        print(f"  Required entry: ${ideal_entry:.2f}")
        print(f"  That's {percent_below:.1f}% below current market")
        
        if percent_below > 5:
            print(f"  ⚠️ Unlikely to fill without significant pullback")
        elif percent_below > 2:
            print(f"  🟡 Possible with patience and limit orders")
        else:
            print(f"  🟢 Achievable with current strategy")
    
    print("\n" + "="*80)
    print("✅ RECOMMENDED ACTION PLAN")
    print("="*80)
    
    print("\nSince you want to keep TP/SL fixed, here's what to do:")
    
    print("\n1. IMMEDIATE CHANGES:")
    print("   • Stop using market orders (25% → 0%)")
    print("   • Place all orders as limits below market")
    print("   • Use wider spacing: 2%, 4%, 6% instead of 1%, 2%, 3%")
    
    print("\n2. NEW ENTRY RULES:")
    print("   • Only enter if price is within 2% of your SL")
    print("   • If price is >3% above SL, skip the trade")
    print("   • Wait for red candles/pullbacks")
    
    print("\n3. POSITION SIZING ADJUSTMENT:")
    print("   • Take smaller position at market levels")
    print("   • Save capital for better entries on dips")
    print("   • Example: 30% initial, 70% on pullback")
    
    print("\n4. USE ALERTS:")
    print("   • Set alert at (SL + 2%) level")
    print("   • Only trade when alert triggers")
    print("   • This ensures favorable entry zone")
    
    print("\n⚠️ THE TRUTH:")
    print("With fixed TP at +3% and SL at -5%, you CANNOT get good R:R")
    print("entering at market price. You MUST get a better entry or accept poor R:R.")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    analyze_fixed_tpsl_strategies()