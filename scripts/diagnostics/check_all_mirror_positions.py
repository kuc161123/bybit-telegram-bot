#\!/usr/bin/env python3
"""
Check all positions on both main and mirror accounts to identify discrepancies
"""
from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from decimal import Decimal

def check_all_positions():
    """Compare all positions between main and mirror accounts"""
    
    # Initialize clients
    main_client = HTTP(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        testnet=USE_TESTNET
    )
    
    mirror_client = HTTP(
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2,
        testnet=USE_TESTNET
    )
    
    print("=" * 80)
    print("POSITION COMPARISON - MAIN vs MIRROR")
    print("=" * 80)
    
    # Get all positions
    main_positions = {}
    mirror_positions = {}
    
    # Fetch main positions
    main_response = main_client.get_positions(category="linear", settleCoin="USDT")
    if main_response.get("retCode") == 0:
        for pos in main_response.get("result", {}).get("list", []):
            size = float(pos.get("size", 0))
            if size > 0:
                symbol = pos.get("symbol")
                main_positions[symbol] = {
                    "side": pos.get("side"),
                    "size": size,
                    "avgPrice": pos.get("avgPrice"),
                    "unrealisedPnl": pos.get("unrealisedPnl")
                }
    
    # Fetch mirror positions
    mirror_response = mirror_client.get_positions(category="linear", settleCoin="USDT")
    if mirror_response.get("retCode") == 0:
        for pos in mirror_response.get("result", {}).get("list", []):
            size = float(pos.get("size", 0))
            if size > 0:
                symbol = pos.get("symbol")
                mirror_positions[symbol] = {
                    "side": pos.get("side"),
                    "size": size,
                    "avgPrice": pos.get("avgPrice"),
                    "unrealisedPnl": pos.get("unrealisedPnl")
                }
    
    # All symbols
    all_symbols = sorted(set(main_positions.keys()) | set(mirror_positions.keys()))
    
    print(f"\nTotal unique symbols: {len(all_symbols)}")
    print(f"Main account positions: {len(main_positions)}")
    print(f"Mirror account positions: {len(mirror_positions)}")
    
    print("\n" + "-" * 80)
    print("DETAILED COMPARISON")
    print("-" * 80)
    
    missing_on_mirror = []
    missing_on_main = []
    size_mismatches = []
    
    for symbol in all_symbols:
        main_pos = main_positions.get(symbol)
        mirror_pos = mirror_positions.get(symbol)
        
        print(f"\n{symbol}:")
        
        if main_pos and not mirror_pos:
            print(f"  ❌ MISSING ON MIRROR")
            print(f"  Main: {main_pos['side']} {main_pos['size']} @ ${main_pos['avgPrice']}")
            print(f"  P&L: ${main_pos['unrealisedPnl']}")
            missing_on_mirror.append(symbol)
            
        elif mirror_pos and not main_pos:
            print(f"  ❌ MISSING ON MAIN (orphaned mirror position)")
            print(f"  Mirror: {mirror_pos['side']} {mirror_pos['size']} @ ${mirror_pos['avgPrice']}")
            print(f"  P&L: ${mirror_pos['unrealisedPnl']}")
            missing_on_main.append(symbol)
            
        else:  # Both have positions
            main_size = main_pos['size']
            mirror_size = mirror_pos['size']
            ratio = (mirror_size / main_size * 100) if main_size > 0 else 0
            
            print(f"  Main: {main_pos['side']} {main_size} @ ${main_pos['avgPrice']} (P&L: ${main_pos['unrealisedPnl']})")
            print(f"  Mirror: {mirror_pos['side']} {mirror_size} @ ${mirror_pos['avgPrice']} (P&L: ${mirror_pos['unrealisedPnl']})")
            print(f"  Size ratio: {ratio:.1f}%")
            
            if abs(ratio - 50) > 5:  # More than 5% deviation from 50%
                size_mismatches.append((symbol, ratio))
                print(f"  ⚠️ Size mismatch (expected ~50%)")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if missing_on_mirror:
        print(f"\n❌ Missing on Mirror ({len(missing_on_mirror)}):")
        for symbol in missing_on_mirror:
            print(f"  - {symbol}")
    
    if missing_on_main:
        print(f"\n❌ Orphaned on Mirror ({len(missing_on_main)}):")
        for symbol in missing_on_main:
            print(f"  - {symbol}")
    
    if size_mismatches:
        print(f"\n⚠️ Size Mismatches ({len(size_mismatches)}):")
        for symbol, ratio in size_mismatches:
            print(f"  - {symbol}: {ratio:.1f}% (expected ~50%)")
    
    if not missing_on_mirror and not missing_on_main and not size_mismatches:
        print("\n✅ All positions properly synced\!")
    
    # Check for orders on missing positions
    if missing_on_mirror:
        print("\n" + "-" * 80)
        print("CHECKING ORDERS FOR MISSING POSITIONS")
        print("-" * 80)
        
        for symbol in missing_on_mirror:
            # Check if main has orders
            main_orders_resp = main_client.get_open_orders(category="linear", symbol=symbol)
            if main_orders_resp.get("retCode") == 0:
                orders = main_orders_resp.get("result", {}).get("list", [])
                print(f"\n{symbol}: {len(orders)} orders on main account")
                if orders:
                    tp_count = sum(1 for o in orders if "TP" in o.get("orderLinkId", "") or o.get("stopOrderType") == "TakeProfit")
                    sl_count = sum(1 for o in orders if "SL" in o.get("orderLinkId", "") or o.get("stopOrderType") == "StopLoss")
                    print(f"  - {tp_count} TP orders")
                    print(f"  - {sl_count} SL orders")

if __name__ == "__main__":
    check_all_positions()