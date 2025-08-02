#!/usr/bin/env python3
"""
Compare positions between main and mirror accounts.
Identifies positions that are on mirror but not on main account.
This is a read-only script that won't affect the running bot.
"""

import asyncio
import os
import sys
from decimal import Decimal
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

async def compare_accounts():
    """Compare positions between main and mirror accounts."""
    
    print("🔍 Main vs Mirror Account Position Comparison")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        # Import necessary functions
        from clients.bybit_helpers import get_all_positions
        from execution.mirror_trader import get_mirror_positions, bybit_client_2
        from config.settings import ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
        
        # Check mirror configuration
        if not ENABLE_MIRROR_TRADING or not BYBIT_API_KEY_2 or not BYBIT_API_SECRET_2:
            print("❌ Mirror trading is not configured!")
            return
        
        # Fetch main account positions
        print("\n📊 Fetching main account positions...")
        main_positions = await get_all_positions()
        main_active = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        # Fetch mirror account positions
        print("📊 Fetching mirror account positions...")
        mirror_positions = await get_mirror_positions()
        mirror_active = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        print(f"\n✅ Main account: {len(main_active)} active positions")
        print(f"✅ Mirror account: {len(mirror_active)} active positions")
        
        # Create sets of symbol-side combinations for comparison
        main_positions_set = set()
        main_positions_dict = {}
        
        for pos in main_active:
            symbol = pos.get('symbol')
            side = pos.get('side')
            key = f"{symbol}-{side}"
            main_positions_set.add(key)
            main_positions_dict[key] = pos
        
        mirror_positions_set = set()
        mirror_positions_dict = {}
        
        for pos in mirror_active:
            symbol = pos.get('symbol')
            side = pos.get('side')
            key = f"{symbol}-{side}"
            mirror_positions_set.add(key)
            mirror_positions_dict[key] = pos
        
        # Find positions that are on mirror but not on main
        mirror_only = mirror_positions_set - main_positions_set
        main_only = main_positions_set - mirror_positions_set
        both_accounts = main_positions_set & mirror_positions_set
        
        # Display positions on BOTH accounts
        print("\n✅ POSITIONS ON BOTH ACCOUNTS:")
        print("-" * 80)
        if both_accounts:
            for key in sorted(both_accounts):
                symbol, side = key.split('-')
                main_pos = main_positions_dict[key]
                mirror_pos = mirror_positions_dict[key]
                
                main_size = float(main_pos.get('size', 0))
                mirror_size = float(mirror_pos.get('size', 0))
                main_pnl = float(main_pos.get('unrealisedPnl', 0))
                mirror_pnl = float(mirror_pos.get('unrealisedPnl', 0))
                
                print(f"  {symbol:<12} {side:<4}")
                print(f"    Main:   Size: {main_size:>10,.2f} | P&L: ${main_pnl:>+8,.2f}")
                print(f"    Mirror: Size: {mirror_size:>10,.2f} | P&L: ${mirror_pnl:>+8,.2f}")
        else:
            print("  None")
        
        # Display positions ONLY on main account
        print("\n📍 POSITIONS ONLY ON MAIN ACCOUNT:")
        print("-" * 80)
        if main_only:
            for key in sorted(main_only):
                symbol, side = key.split('-')
                pos = main_positions_dict[key]
                size = float(pos.get('size', 0))
                pnl = float(pos.get('unrealisedPnl', 0))
                entry = float(pos.get('avgPrice', 0))
                
                print(f"  {symbol:<12} {side:<4} | Size: {size:>10,.2f} | Entry: ${entry:>10,.4f} | P&L: ${pnl:>+8,.2f}")
        else:
            print("  None")
        
        # Display positions ONLY on mirror account (these should potentially be closed)
        print("\n⚠️  POSITIONS ONLY ON MIRROR ACCOUNT (NOT ON MAIN):")
        print("-" * 80)
        if mirror_only:
            total_mirror_only_pnl = Decimal('0')
            total_mirror_only_value = Decimal('0')
            
            for key in sorted(mirror_only):
                symbol, side = key.split('-')
                pos = mirror_positions_dict[key]
                size = float(pos.get('size', 0))
                pnl = float(pos.get('unrealisedPnl', 0))
                entry = float(pos.get('avgPrice', 0))
                mark = float(pos.get('markPrice', 0))
                value = float(pos.get('positionValue', 0))
                
                total_mirror_only_pnl += Decimal(str(pnl))
                total_mirror_only_value += Decimal(str(value))
                
                print(f"  {symbol:<12} {side:<4}")
                print(f"    Size: {size:>10,.2f} | Entry: ${entry:>10,.4f} | Current: ${mark:>10,.4f}")
                print(f"    P&L: ${pnl:>+8,.2f} | Value: ${value:>10,.2f}")
                print()
            
            print(f"  📊 Total P&L for mirror-only positions: ${total_mirror_only_pnl:+,.2f}")
            print(f"  💰 Total value of mirror-only positions: ${total_mirror_only_value:,.2f}")
            print(f"\n  ⚠️  These {len(mirror_only)} positions exist on mirror but NOT on main account!")
            print("  Consider closing these positions to sync with main account.")
        else:
            print("  ✅ None - Mirror account is in sync with main account")
        
        # Summary statistics
        print("\n📊 SUMMARY:")
        print("-" * 80)
        print(f"Positions on both accounts: {len(both_accounts)}")
        print(f"Positions only on main: {len(main_only)}")
        print(f"Positions only on mirror: {len(mirror_only)}")
        
        if mirror_only:
            print(f"\n💡 RECOMMENDATION:")
            print(f"   You have {len(mirror_only)} positions on mirror that don't exist on main.")
            print("   These are likely old positions that weren't closed when main positions were closed.")
            print("   You may want to close these mirror-only positions to keep accounts in sync.")
            
            # Create a list of symbols to close
            symbols_to_close = [key.split('-')[0] for key in mirror_only]
            print(f"\n   Symbols to potentially close on mirror: {', '.join(sorted(set(symbols_to_close)))}")
        
        print("\n" + "=" * 80)
        print("✅ Position comparison completed successfully!")
        print("This check did not affect any running bot operations or trades.")
        
    except Exception as e:
        print(f"\n❌ Error comparing positions: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    await compare_accounts()


if __name__ == "__main__":
    asyncio.run(main())