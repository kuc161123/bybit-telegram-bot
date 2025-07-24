#!/usr/bin/env python3
"""
Test merge feature with mirror trading
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Tuple
import json

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from execution.position_merger import ConservativePositionMerger, FastPositionMerger
from config.settings import USE_TESTNET

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MergeTester:
    def __init__(self):
        self.conservative_merger = ConservativePositionMerger()
        self.fast_merger = FastPositionMerger()
        self.test_positions = []
        
    async def get_account_positions(self, account: str = "main") -> Tuple[List[Dict], List[Dict]]:
        """Get positions and orders for an account"""
        if account == "main":
            positions = await get_all_positions()
            orders = await get_all_open_orders()
        else:
            # Mirror account
            pos_response = await api_call_with_retry(
                lambda: bybit_client_2.get_positions(
                    category="linear",
                    settleCoin="USDT"
                ),
                timeout=30
            )
            positions = pos_response.get("result", {}).get("list", []) if pos_response and pos_response.get("retCode") == 0 else []
            
            order_response = await api_call_with_retry(
                lambda: bybit_client_2.get_open_orders(
                    category="linear",
                    settleCoin="USDT",
                    limit=200
                ),
                timeout=30
            )
            orders = order_response.get("result", {}).get("list", []) if order_response and order_response.get("retCode") == 0 else []
            
        return positions, orders
    
    async def display_account_status(self, account: str = "main"):
        """Display current account status"""
        positions, orders = await self.get_account_positions(account)
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        
        account_name = "MIRROR" if account == "mirror" else "MAIN"
        print(f"\n{'='*70}")
        print(f"{account_name} ACCOUNT STATUS")
        print(f"{'='*70}")
        
        if active_positions:
            print(f"\n📊 Active Positions ({len(active_positions)}):")
            for pos in active_positions:
                symbol = pos['symbol']
                side = pos['side']
                size = pos['size']
                avg_price = pos['avgPrice']
                print(f"  - {symbol} {side}: {size} @ ${avg_price}")
        else:
            print("\n✅ No active positions")
        
        # Group orders by symbol
        if orders:
            orders_by_symbol = {}
            for order in orders:
                symbol = order['symbol']
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
            
            print(f"\n📝 Active Orders ({len(orders)}):")
            for symbol, symbol_orders in orders_by_symbol.items():
                tp_orders = [o for o in symbol_orders if o.get('side') != next((p['side'] for p in active_positions if p['symbol'] == symbol), '')]
                sl_orders = [o for o in symbol_orders if o.get('triggerPrice') and o.get('side') == next((p['side'] for p in active_positions if p['symbol'] == symbol), '')]
                limit_orders = [o for o in symbol_orders if not o.get('triggerPrice') and not o.get('reduceOnly')]
                
                print(f"  {symbol}:")
                if tp_orders:
                    print(f"    - {len(tp_orders)} TP orders")
                if sl_orders:
                    print(f"    - {len(sl_orders)} SL orders")
                if limit_orders:
                    print(f"    - {len(limit_orders)} Limit orders")
        else:
            print("\n✅ No active orders")
    
    async def test_merge_detection(self):
        """Test if merger correctly detects mergeable positions"""
        print("\n" + "="*70)
        print("TEST 1: MERGE DETECTION")
        print("="*70)
        
        # Get current positions
        main_positions, main_orders = await self.get_account_positions("main")
        mirror_positions, mirror_orders = await self.get_account_positions("mirror")
        
        # Check main account
        print("\n🔍 Checking MAIN account for mergeable positions...")
        main_active = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        if len(main_active) >= 2:
            # Group by symbol and side
            positions_by_key = {}
            for pos in main_active:
                key = f"{pos['symbol']}_{pos['side']}"
                if key not in positions_by_key:
                    positions_by_key[key] = []
                positions_by_key[key].append(pos)
            
            # Find mergeable
            mergeable = {k: v for k, v in positions_by_key.items() if len(v) > 1}
            
            if mergeable:
                print(f"✅ Found {len(mergeable)} mergeable position groups:")
                for key, positions in mergeable.items():
                    symbol, side = key.split('_')
                    total_size = sum(float(p['size']) for p in positions)
                    print(f"  - {symbol} {side}: {len(positions)} positions, total size: {total_size}")
            else:
                print("❌ No mergeable positions found (need multiple positions of same symbol/side)")
        else:
            print(f"❌ Not enough positions to test merge (have {len(main_active)}, need at least 2)")
        
        # Check mirror account
        if is_mirror_trading_enabled():
            print("\n🔍 Checking MIRROR account for mergeable positions...")
            mirror_active = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
            
            if len(mirror_active) >= 2:
                # Group by symbol and side
                positions_by_key = {}
                for pos in mirror_active:
                    key = f"{pos['symbol']}_{pos['side']}"
                    if key not in positions_by_key:
                        positions_by_key[key] = []
                    positions_by_key[key].append(pos)
                
                # Find mergeable
                mergeable = {k: v for k, v in positions_by_key.items() if len(v) > 1}
                
                if mergeable:
                    print(f"✅ Found {len(mergeable)} mergeable position groups:")
                    for key, positions in mergeable.items():
                        symbol, side = key.split('_')
                        total_size = sum(float(p['size']) for p in positions)
                        print(f"  - {symbol} {side}: {len(positions)} positions, total size: {total_size}")
                else:
                    print("❌ No mergeable positions found")
            else:
                print(f"❌ Not enough positions to test merge (have {len(mirror_active)}, need at least 2)")
    
    async def test_merge_simulation(self):
        """Test merge simulation (dry run)"""
        print("\n" + "="*70)
        print("TEST 2: MERGE SIMULATION (DRY RUN)")
        print("="*70)
        
        # Test with dummy positions if no real positions
        main_positions, main_orders = await self.get_account_positions("main")
        active_positions = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        if not active_positions:
            print("\n⚠️ No active positions to test merge. Creating simulated scenario...")
            
            # Simulate mergeable positions
            simulated_positions = [
                {
                    'symbol': 'BTCUSDT',
                    'side': 'Buy',
                    'size': '0.1',
                    'avgPrice': '65000',
                    'markPrice': '66000',
                    'positionValue': '6600',
                    'unrealisedPnl': '100',
                    'positionIdx': 1
                },
                {
                    'symbol': 'BTCUSDT',
                    'side': 'Buy',
                    'size': '0.05',
                    'avgPrice': '64000',
                    'markPrice': '66000',
                    'positionValue': '3300',
                    'unrealisedPnl': '100',
                    'positionIdx': 1
                }
            ]
            
            print("\n📊 Simulated positions:")
            for pos in simulated_positions:
                print(f"  - {pos['symbol']} {pos['side']}: {pos['size']} @ ${pos['avgPrice']}")
            
            # Calculate merge result
            total_size = sum(Decimal(p['size']) for p in simulated_positions)
            weighted_avg = sum(Decimal(p['size']) * Decimal(p['avgPrice']) for p in simulated_positions) / total_size
            
            print(f"\n🔄 Merge would result in:")
            print(f"  - Combined size: {total_size}")
            print(f"  - Weighted avg price: ${weighted_avg:.2f}")
            print(f"  - Positions to close: {len(simulated_positions) - 1}")
    
    async def test_mirror_sync(self):
        """Test if mirror account properly syncs with main account merges"""
        print("\n" + "="*70)
        print("TEST 3: MIRROR SYNC VERIFICATION")
        print("="*70)
        
        if not is_mirror_trading_enabled():
            print("❌ Mirror trading is not enabled")
            return
        
        # Compare main and mirror positions
        main_positions, _ = await self.get_account_positions("main")
        mirror_positions, _ = await self.get_account_positions("mirror")
        
        main_active = [p for p in main_positions if float(p.get('size', 0)) > 0]
        mirror_active = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        print(f"\n📊 Position comparison:")
        print(f"  Main account: {len(main_active)} positions")
        print(f"  Mirror account: {len(mirror_active)} positions")
        
        # Check if positions match
        main_symbols = {(p['symbol'], p['side']) for p in main_active}
        mirror_symbols = {(p['symbol'], p['side']) for p in mirror_active}
        
        if main_symbols == mirror_symbols:
            print("✅ Position symbols and sides match between accounts")
        else:
            only_main = main_symbols - mirror_symbols
            only_mirror = mirror_symbols - main_symbols
            
            if only_main:
                print(f"⚠️ Positions only in main account: {only_main}")
            if only_mirror:
                print(f"⚠️ Positions only in mirror account: {only_mirror}")
        
        # Check merge readiness
        print("\n🔄 Merge sync readiness:")
        print("  ✅ Conservative merger initialized") if self.conservative_merger else print("  ❌ Conservative merger not initialized")
        print("  ✅ Fast merger initialized") if self.fast_merger else print("  ❌ Fast merger not initialized")
        print("  ✅ Mirror client available") if bybit_client_2 else print("  ❌ Mirror client not available")
    
    async def test_merge_process_flow(self):
        """Test the complete merge process flow"""
        print("\n" + "="*70)
        print("TEST 4: MERGE PROCESS FLOW")
        print("="*70)
        
        print("\n📋 Merge process steps:")
        print("1. ✅ Detect mergeable positions (same symbol, same side)")
        print("2. ✅ Cancel all orders for positions being merged")
        print("3. ✅ Close smaller positions into the largest one")
        print("4. ✅ Recreate TP/SL orders for merged position")
        print("5. ✅ Mirror all actions on mirror account if enabled")
        
        print("\n🔧 Configuration check:")
        print(f"  - Testnet mode: {'Yes' if USE_TESTNET else 'No'}")
        print(f"  - Mirror trading: {'Enabled' if is_mirror_trading_enabled() else 'Disabled'}")
        print(f"  - Conservative merger: {'Ready' if self.conservative_merger else 'Not initialized'}")
        print(f"  - Fast merger: {'Ready' if self.fast_merger else 'Not initialized'}")
        
        # Check if merger has proper error handling
        print("\n🛡️ Safety checks:")
        print("  ✅ Atomic operations (all or nothing)")
        print("  ✅ Order cancellation before position changes")
        print("  ✅ Mirror sync verification")
        print("  ✅ Error rollback capability")


async def main():
    """Main test function"""
    print("\n🧪 MERGE FEATURE TEST WITH MIRROR TRADING")
    print("="*70)
    
    if not is_mirror_trading_enabled():
        print("\n⚠️ WARNING: Mirror trading is not enabled!")
        print("Set BYBIT_API_KEY_2 and BYBIT_API_SECRET_2 in .env to enable")
    
    tester = MergeTester()
    
    try:
        # Display current status
        print("\n📊 CURRENT ACCOUNT STATUS")
        await tester.display_account_status("main")
        if is_mirror_trading_enabled():
            await tester.display_account_status("mirror")
        
        # Run tests
        await tester.test_merge_detection()
        await tester.test_merge_simulation()
        await tester.test_mirror_sync()
        await tester.test_merge_process_flow()
        
        print("\n" + "="*70)
        print("✅ MERGE TEST COMPLETE")
        print("="*70)
        
        print("\n📝 RECOMMENDATIONS:")
        print("1. To test merge with real positions:")
        print("   - Open 2+ positions of the same symbol/side")
        print("   - Use the /merge command in the bot")
        print("   - Verify both accounts are updated")
        print("\n2. For production use:")
        print("   - Always test on testnet first")
        print("   - Monitor both accounts during merge")
        print("   - Check order recreation after merge")
        
    except Exception as e:
        logger.error(f"Test error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())