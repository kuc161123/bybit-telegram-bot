#\!/usr/bin/env python3
"""
Comprehensive verification of all mirror positions and their TP/SL orders
"""
from pybit.unified_trading import HTTP
from config.settings import USE_TESTNET, BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from decimal import Decimal
import pickle

def load_approach_data():
    """Load approach information from pickle file"""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
            approach_map = {}
            
            # Extract approach for each symbol
            for chat_id, user_data in data.get('user_data', {}).items():
                positions = user_data.get('positions', {})
                for pos_key, pos_data in positions.items():
                    symbol = pos_data.get('symbol')
                    approach = pos_data.get('approach')
                    account_type = pos_data.get('account_type', 'main')
                    if symbol and approach:
                        key = f"{symbol}_{account_type}"
                        approach_map[key] = approach
            
            return approach_map
    except Exception as e:
        print(f"Warning: Could not load approach data: {e}")
        return {}

def verify_all_mirror_positions():
    """Verify all mirror positions have proper TP/SL orders"""
    
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
    
    # Load approach data
    approach_map = load_approach_data()
    
    print("=" * 80)
    print("COMPREHENSIVE MIRROR ACCOUNT TP/SL VERIFICATION")
    print("=" * 80)
    
    # Get all mirror positions
    mirror_response = mirror_client.get_positions(category="linear", settleCoin="USDT")
    mirror_positions = []
    
    if mirror_response.get("retCode") == 0:
        for pos in mirror_response.get("result", {}).get("list", []):
            size = float(pos.get("size", 0))
            if size > 0:
                mirror_positions.append(pos)
    
    print(f"\nTotal Mirror Positions: {len(mirror_positions)}")
    
    # Also get main positions for comparison
    main_response = main_client.get_positions(category="linear", settleCoin="USDT")
    main_positions = {}
    
    if main_response.get("retCode") == 0:
        for pos in main_response.get("result", {}).get("list", []):
            size = float(pos.get("size", 0))
            if size > 0:
                symbol = pos.get("symbol")
                main_positions[symbol] = pos
    
    # Get all mirror orders
    mirror_orders_response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
    all_mirror_orders = []
    
    if mirror_orders_response.get("retCode") == 0:
        all_mirror_orders = mirror_orders_response.get("result", {}).get("list", [])
    
    print(f"Total Mirror Orders: {len(all_mirror_orders)}")
    
    # Group orders by symbol
    orders_by_symbol = {}
    for order in all_mirror_orders:
        symbol = order.get("symbol")
        if symbol not in orders_by_symbol:
            orders_by_symbol[symbol] = []
        orders_by_symbol[symbol].append(order)
    
    print("\n" + "-" * 80)
    print("POSITION-BY-POSITION ANALYSIS")
    print("-" * 80)
    
    issues_summary = {
        "missing_sl": [],
        "missing_tp": [],
        "wrong_tp_count": [],
        "wrong_tp_breakdown": [],
        "tp_coverage_issues": []
    }
    
    for i, pos in enumerate(mirror_positions, 1):
        symbol = pos.get("symbol")
        side = pos.get("side")
        size = Decimal(str(pos.get("size", 0)))
        avg_price = pos.get("avgPrice")
        pnl = pos.get("unrealisedPnl")
        
        # Get approach
        approach_key = f"{symbol}_mirror"
        approach = approach_map.get(approach_key, "Unknown")
        
        # Get main position for comparison
        main_pos = main_positions.get(symbol)
        size_ratio = "N/A"
        if main_pos:
            main_size = float(main_pos.get("size", 0))
            if main_size > 0:
                size_ratio = f"{float(size) / main_size * 100:.1f}%"
        
        print(f"\n{i}. {symbol} ({side})")
        print(f"   Size: {size} (Main ratio: {size_ratio})")
        print(f"   Avg Price: ${avg_price}")
        print(f"   Unrealized P&L: ${pnl}")
        print(f"   Approach: {approach}")
        
        # Get orders for this symbol
        symbol_orders = orders_by_symbol.get(symbol, [])
        
        # Categorize orders
        tp_orders = []
        sl_orders = []
        
        for order in symbol_orders:
            order_type = order.get("orderType", "")
            order_side = order.get("side")
            stop_type = order.get("stopOrderType", "")
            link_id = order.get("orderLinkId", "")
            
            # Determine if TP or SL
            if side == "Buy":  # Long position
                if order_side == "Sell":
                    if "TP" in link_id or stop_type == "TakeProfit" or (order_type == "Limit" and not stop_type):
                        tp_orders.append(order)
                    elif "SL" in link_id or stop_type == "StopLoss":
                        sl_orders.append(order)
            else:  # Short position
                if order_side == "Buy":
                    if "TP" in link_id or stop_type == "TakeProfit" or (order_type == "Limit" and not stop_type):
                        tp_orders.append(order)
                    elif "SL" in link_id or stop_type == "StopLoss":
                        sl_orders.append(order)
        
        print(f"\n   Orders Summary:")
        print(f"   - {len(tp_orders)} TP orders")
        print(f"   - {len(sl_orders)} SL orders")
        
        # Check SL
        if len(sl_orders) == 0:
            print("   ❌ Missing Stop Loss order")
            issues_summary["missing_sl"].append(symbol)
        elif len(sl_orders) > 1:
            print(f"   ⚠️ Multiple SL orders ({len(sl_orders)})")
        else:
            sl = sl_orders[0]
            print(f"   ✅ SL: {sl.get('qty')} @ ${sl.get('triggerPrice', sl.get('price'))}")
        
        # Check TP
        if len(tp_orders) == 0:
            print("   ❌ Missing Take Profit orders")
            issues_summary["missing_tp"].append(symbol)
        else:
            # Calculate TP breakdown
            tp_breakdown = []
            total_tp_qty = Decimal("0")
            
            for tp in sorted(tp_orders, key=lambda x: float(x.get("price", 0))):
                tp_qty = Decimal(str(tp.get("qty", 0)))
                tp_percentage = (tp_qty / size * 100).quantize(Decimal("0.01"))
                total_tp_qty += tp_qty
                tp_breakdown.append({
                    "qty": tp_qty,
                    "price": tp.get("price"),
                    "percentage": float(tp_percentage)
                })
            
            total_coverage = (total_tp_qty / size * 100).quantize(Decimal("0.01"))
            
            print(f"\n   TP Analysis:")
            print(f"   Total Coverage: {total_coverage}% of position")
            
            for j, tp in enumerate(tp_breakdown, 1):
                print(f"   TP{j}: {tp['percentage']}% ({tp['qty']}) @ ${tp['price']}")
            
            # Check coverage
            if total_coverage < Decimal("99.5"):
                print(f"   ⚠️ Incomplete TP coverage: {total_coverage}%")
                issues_summary["tp_coverage_issues"].append((symbol, float(total_coverage)))
            elif total_coverage > Decimal("100.5"):
                print(f"   ⚠️ Excessive TP coverage: {total_coverage}%")
                issues_summary["tp_coverage_issues"].append((symbol, float(total_coverage)))
            
            # Check conservative breakdown
            if approach == "Conservative":
                if len(tp_orders) != 4:
                    print(f"   ❌ Conservative should have 4 TPs, found {len(tp_orders)}")
                    issues_summary["wrong_tp_count"].append((symbol, len(tp_orders)))
                else:
                    # Check 85/5/5/5 pattern
                    expected = [85.0, 5.0, 5.0, 5.0]
                    percentages = [tp["percentage"] for tp in tp_breakdown]
                    
                    mismatches = []
                    for k, (actual, exp) in enumerate(zip(percentages, expected)):
                        if abs(actual - exp) > 0.5:  # 0.5% tolerance
                            mismatches.append(f"TP{k+1}: {actual}% (expected {exp}%)")
                    
                    if mismatches:
                        print(f"   ❌ Wrong breakdown: {', '.join(mismatches)}")
                        issues_summary["wrong_tp_breakdown"].append((symbol, mismatches))
                    else:
                        print("   ✅ Correct 85/5/5/5 breakdown")
    
    # Missing positions
    print("\n" + "-" * 80)
    print("MISSING POSITIONS CHECK")
    print("-" * 80)
    
    mirror_symbols = {pos.get("symbol") for pos in mirror_positions}
    missing_positions = []
    
    for symbol, main_pos in main_positions.items():
        if symbol not in mirror_symbols:
            missing_positions.append({
                "symbol": symbol,
                "side": main_pos.get("side"),
                "size": main_pos.get("size"),
                "avgPrice": main_pos.get("avgPrice")
            })
    
    if missing_positions:
        print(f"\n❌ Positions missing on mirror ({len(missing_positions)}):")
        for pos in missing_positions:
            print(f"   - {pos['symbol']}: {pos['side']} {pos['size']} @ ${pos['avgPrice']}")
    else:
        print("\n✅ No missing positions")
    
    # Summary
    print("\n" + "=" * 80)
    print("ISSUES SUMMARY")
    print("=" * 80)
    
    total_issues = 0
    
    if issues_summary["missing_sl"]:
        print(f"\n❌ Missing Stop Loss ({len(issues_summary['missing_sl'])}):")
        for symbol in issues_summary["missing_sl"]:
            print(f"   - {symbol}")
        total_issues += len(issues_summary["missing_sl"])
    
    if issues_summary["missing_tp"]:
        print(f"\n❌ Missing Take Profit ({len(issues_summary['missing_tp'])}):")
        for symbol in issues_summary["missing_tp"]:
            print(f"   - {symbol}")
        total_issues += len(issues_summary["missing_tp"])
    
    if issues_summary["wrong_tp_count"]:
        print(f"\n❌ Wrong TP Count ({len(issues_summary['wrong_tp_count'])}):")
        for symbol, count in issues_summary["wrong_tp_count"]:
            print(f"   - {symbol}: {count} TPs (expected 4)")
        total_issues += len(issues_summary["wrong_tp_count"])
    
    if issues_summary["wrong_tp_breakdown"]:
        print(f"\n❌ Wrong TP Breakdown ({len(issues_summary['wrong_tp_breakdown'])}):")
        for symbol, mismatches in issues_summary["wrong_tp_breakdown"]:
            print(f"   - {symbol}: {', '.join(mismatches)}")
        total_issues += len(issues_summary["wrong_tp_breakdown"])
    
    if issues_summary["tp_coverage_issues"]:
        print(f"\n⚠️ TP Coverage Issues ({len(issues_summary['tp_coverage_issues'])}):")
        for symbol, coverage in issues_summary["tp_coverage_issues"]:
            print(f"   - {symbol}: {coverage}% coverage")
    
    if total_issues == 0 and not issues_summary["tp_coverage_issues"]:
        print("\n✅ All positions have proper TP/SL configuration\!")
    else:
        print(f"\n📊 Total critical issues: {total_issues}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if missing_positions:
        print("\n1. Open missing positions on mirror account")
    
    if issues_summary["missing_sl"] or issues_summary["missing_tp"]:
        print("\n2. Place missing TP/SL orders for affected positions")
    
    if issues_summary["tp_coverage_issues"]:
        print("\n3. Adjust TP quantities to match position sizes")
    
    if issues_summary["wrong_tp_count"] or issues_summary["wrong_tp_breakdown"]:
        print("\n4. Fix conservative position TP structure (85/5/5/5)")

if __name__ == "__main__":
    verify_all_mirror_positions()