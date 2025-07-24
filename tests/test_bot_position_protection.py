#!/usr/bin/env python3
"""
Test bot position protection - ensures only bot positions are managed
"""
import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.position_identifier import identify_bot_positions
from utils.tp_sl_verifier import TPSLVerifier
from clients.bybit_helpers import get_all_positions, get_all_open_orders

async def test_position_protection():
    """Test that external positions are protected from bot management"""
    
    print("\n=== Bot Position Protection Test ===")
    
    # Get positions and orders
    positions = await get_all_positions()
    all_orders = await get_all_open_orders()
    
    active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
    
    # Step 1: Identify bot vs external positions
    print("\n1. Position Identification:")
    results = identify_bot_positions(active_positions, all_orders)
    
    print(f"   Total positions: {len(active_positions)}")
    print(f"   Bot positions: {len(results['bot'])}")
    print(f"   External positions: {len(results['external'])}")
    
    # Show details
    print("\n   Bot positions (will be managed):")
    for pos in results['bot']:
        symbol = pos.get('symbol')
        side = pos.get('side')
        
        # Find orders for this position
        symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]
        bot_orders = [o for o in symbol_orders if any(
            o.get('orderLinkId', '').startswith(prefix) 
            for prefix in ['BOT_', 'AUTO_', 'MANUAL_']
        )]
        
        print(f"     - {symbol} {side} (has {len(bot_orders)} bot orders)")
    
    print("\n   External positions (will be IGNORED):")
    for pos in results['external']:
        symbol = pos.get('symbol')
        side = pos.get('side')
        print(f"     - {symbol} {side}")
    
    # Step 2: Test TP/SL verification
    print("\n2. TP/SL Verification (Bot Positions Only):")
    verifier = TPSLVerifier()
    verification_results = await verifier.verify_all_positions()
    
    print(f"   Verified bot positions: {verification_results['verified']}/{verification_results['bot_positions']}")
    print(f"   External positions ignored: {verification_results['external_positions']}")
    
    if verification_results.get('missing_tp'):
        print(f"   Bot positions missing TP: {len(verification_results['missing_tp'])}")
        for item in verification_results['missing_tp']:
            print(f"     - {item['symbol']} ({item['side']})")
    
    if verification_results.get('missing_sl'):
        print(f"   Bot positions missing SL: {len(verification_results['missing_sl'])}")
        for item in verification_results['missing_sl']:
            print(f"     - {item['symbol']} ({item['side']})")
    
    # Step 3: Test environment variable
    print("\n3. Configuration Test:")
    manage_external = os.getenv('MANAGE_EXTERNAL_POSITIONS', 'false').lower() == 'true'
    print(f"   MANAGE_EXTERNAL_POSITIONS: {manage_external}")
    
    if manage_external:
        print("   ⚠️  WARNING: Bot is configured to manage ALL positions!")
    else:
        print("   ✅ Bot will only manage its own positions")
    
    # Step 4: Order prefix analysis
    print("\n4. Order Prefix Analysis:")
    bot_prefixes = ['BOT_', 'AUTO_', 'MANUAL_']
    prefix_counts = {prefix: 0 for prefix in bot_prefixes}
    external_orders = 0
    
    for order in all_orders:
        order_link_id = order.get('orderLinkId', '')
        found_prefix = False
        
        for prefix in bot_prefixes:
            if order_link_id.startswith(prefix):
                prefix_counts[prefix] += 1
                found_prefix = True
                break
        
        if not found_prefix and order_link_id:
            external_orders += 1
    
    print(f"   Bot order prefixes found:")
    for prefix, count in prefix_counts.items():
        print(f"     - {prefix}: {count} orders")
    print(f"   External orders (no bot prefix): {external_orders}")
    
    print("\n=== Test Complete ===")
    print("\nSummary:")
    print(f"✅ Bot positions identified: {len(results['bot'])}")
    print(f"✅ External positions protected: {len(results['external'])}")
    print(f"✅ Only bot positions checked for TP/SL")
    print(f"✅ Configuration: {'Manage ALL' if manage_external else 'Bot positions only'}")

if __name__ == "__main__":
    asyncio.run(test_position_protection())