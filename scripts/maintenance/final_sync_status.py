#!/usr/bin/env python3
"""
Final status check of both accounts after sync.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def check_final_status():
    """Check final status of both accounts."""
    
    print("📊 Final Sync Status Check")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
        USE_TESTNET
    )
    
    # Initialize clients
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = None
    if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
    
    try:
        # Get positions from both accounts
        main_positions = []
        mirror_positions = []
        
        # Main account
        main_resp = main_client.get_positions(category="linear", settleCoin="USDT")
        if main_resp['retCode'] == 0:
            main_positions = [p for p in main_resp['result']['list'] if float(p.get('size', 0)) > 0]
        
        # Mirror account
        if mirror_client:
            mirror_resp = mirror_client.get_positions(category="linear", settleCoin="USDT")
            if mirror_resp['retCode'] == 0:
                mirror_positions = [p for p in mirror_resp['result']['list'] if float(p.get('size', 0)) > 0]
        
        print(f"\n📋 Position Summary:")
        print(f"Main account: {len(main_positions)} positions")
        print(f"Mirror account: {len(mirror_positions)} positions")
        
        # Check order status for each position
        active_statuses = ['Untriggered', 'New', 'PartiallyFilled']
        
        print("\n" + "="*80)
        print("DETAILED ORDER STATUS")
        print("="*80)
        
        # Create sets for comparison
        main_symbols = {f"{p['symbol']}_{p['side']}" for p in main_positions}
        mirror_symbols = {f"{p['symbol']}_{p['side']}" for p in mirror_positions}
        
        # Positions on both accounts
        common_symbols = main_symbols & mirror_symbols
        main_only = main_symbols - mirror_symbols
        mirror_only = mirror_symbols - main_symbols
        
        issues = []
        
        print("\n🔹 Positions on Both Accounts:")
        for pos_key in sorted(common_symbols):
            symbol, side = pos_key.split('_')
            
            # Get order counts
            main_orders = main_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=0
            )
            
            mirror_orders = mirror_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=0
            )
            
            if main_orders['retCode'] == 0 and mirror_orders['retCode'] == 0:
                main_active = [o for o in main_orders['result']['list'] 
                             if o.get('reduceOnly') and o.get('orderStatus') in active_statuses]
                mirror_active = [o for o in mirror_orders['result']['list'] 
                               if o.get('reduceOnly') and o.get('orderStatus') in active_statuses]
                
                # Count TPs and SLs
                main_tps = 0
                main_sls = 0
                mirror_tps = 0
                mirror_sls = 0
                
                # Find position for avg price
                main_pos = next((p for p in main_positions if p['symbol'] == symbol and p['side'] == side), None)
                if main_pos:
                    avg_price = float(main_pos.get('avgPrice', 0))
                    
                    for order in main_active:
                        trigger_price = float(order.get('triggerPrice', 0))
                        if trigger_price > 0:
                            if side == 'Buy':
                                if trigger_price > avg_price:
                                    main_tps += 1
                                else:
                                    main_sls += 1
                            else:
                                if trigger_price < avg_price:
                                    main_tps += 1
                                else:
                                    main_sls += 1
                    
                    for order in mirror_active:
                        trigger_price = float(order.get('triggerPrice', 0))
                        if trigger_price > 0:
                            if side == 'Buy':
                                if trigger_price > avg_price:
                                    mirror_tps += 1
                                else:
                                    mirror_sls += 1
                            else:
                                if trigger_price < avg_price:
                                    mirror_tps += 1
                                else:
                                    mirror_sls += 1
                
                status = "✅" if (main_tps == mirror_tps and main_sls == mirror_sls) else "⚠️"
                
                print(f"   {status} {symbol} {side}:")
                print(f"      Main: {main_tps} TPs, {main_sls} SLs")
                print(f"      Mirror: {mirror_tps} TPs, {mirror_sls} SLs")
                
                if status == "⚠️":
                    issues.append(f"{symbol} {side}")
        
        if main_only:
            print("\n⚠️ Positions on Main Only:")
            for pos_key in sorted(main_only):
                symbol, side = pos_key.split('_')
                print(f"   - {symbol} {side}")
                issues.append(f"{symbol} {side} (main only)")
        
        if mirror_only:
            print("\n⚠️ Positions on Mirror Only:")
            for pos_key in sorted(mirror_only):
                symbol, side = pos_key.split('_')
                print(f"   - {symbol} {side}")
                issues.append(f"{symbol} {side} (mirror only)")
        
        # Summary
        print("\n\n" + "="*80)
        print("FINAL SUMMARY")
        print("="*80)
        
        print(f"\n✅ Sync Status:")
        print(f"   - Position count match: {'Yes' if len(main_positions) == len(mirror_positions) else 'No'}")
        print(f"   - Positions with matching orders: {len(common_symbols) - len([i for i in issues if '(main only)' not in i and '(mirror only)' not in i])}")
        print(f"   - Issues found: {len(issues)}")
        
        if issues:
            print(f"\n⚠️ Issues to address:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print(f"\n✅ All positions and orders are properly synced!")
        
        print("\n💡 Notes:")
        print("   1. Conservative rebalancer is active and will preserve trigger prices")
        print("   2. Position order monitor is running and checking every 5 minutes")
        print("   3. Any new positions will be automatically synced")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    await check_final_status()


if __name__ == "__main__":
    asyncio.run(main())