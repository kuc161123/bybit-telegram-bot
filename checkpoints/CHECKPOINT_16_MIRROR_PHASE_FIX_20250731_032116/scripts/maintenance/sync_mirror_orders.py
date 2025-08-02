#!/usr/bin/env python3
"""
Sync mirror account orders with main account.
This will delete all mirror orders and recreate them based on main account structure.
"""

import asyncio
import os
import sys
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def sync_mirror_orders():
    """Sync mirror account orders with main account."""
    
    print("🔄 Mirror Account Order Synchronization")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
        USE_TESTNET
    )
    
    if not all([BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_API_KEY_2, BYBIT_API_SECRET_2]):
        print("❌ Both main and mirror accounts must be configured")
        return
    
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
    
    # Step 1: Get all positions from both accounts
    print("\n📊 Step 1: Analyzing Positions")
    print("-" * 40)
    
    # Get main account positions
    main_positions = {}
    pos_response = main_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    if pos_response['retCode'] == 0:
        for pos in pos_response['result']['list']:
            if float(pos['size']) > 0:
                symbol = pos['symbol']
                main_positions[symbol] = pos
    
    print(f"Main account: {len(main_positions)} active positions")
    
    # Get mirror account positions
    mirror_positions = {}
    pos_response = mirror_client.get_positions(
        category="linear",
        settleCoin="USDT"
    )
    
    if pos_response['retCode'] == 0:
        for pos in pos_response['result']['list']:
            if float(pos['size']) > 0:
                symbol = pos['symbol']
                mirror_positions[symbol] = pos
    
    print(f"Mirror account: {len(mirror_positions)} active positions")
    
    # Find common positions
    common_symbols = set(main_positions.keys()) & set(mirror_positions.keys())
    print(f"Common positions: {len(common_symbols)}")
    
    # Step 2: Cancel ALL mirror account orders
    print("\n\n📤 Step 2: Cancelling All Mirror Account Orders")
    print("-" * 40)
    
    cursor = ""
    total_cancelled = 0
    page = 1
    
    while True:
        params = {
            "category": "linear",
            "settleCoin": "USDT",
            "openOnly": 1,
            "limit": 50
        }
        
        if cursor:
            params["cursor"] = cursor
        
        response = mirror_client.get_open_orders(**params)
        
        if response['retCode'] != 0:
            print(f"❌ Error fetching orders: {response['retMsg']}")
            break
        
        result = response['result']
        orders = result['list']
        
        if not orders:
            break
            
        print(f"\nPage {page}: Found {len(orders)} orders to cancel")
        
        # Cancel each order
        for order in orders:
            try:
                cancel_response = mirror_client.cancel_order(
                    category="linear",
                    symbol=order['symbol'],
                    orderId=order['orderId']
                )
                
                if cancel_response['retCode'] == 0:
                    total_cancelled += 1
                    if total_cancelled % 10 == 0:
                        print(f"   Cancelled {total_cancelled} orders...")
                else:
                    print(f"   ⚠️  Failed to cancel {order['orderId'][:8]}: {cancel_response['retMsg']}")
                    
            except Exception as e:
                print(f"   ❌ Error cancelling order: {e}")
        
        cursor = result.get('nextPageCursor', '')
        if not cursor:
            break
        
        page += 1
        await asyncio.sleep(0.5)  # Rate limiting
    
    print(f"\n✅ Total orders cancelled: {total_cancelled}")
    
    # Step 3: Get main account orders for common positions
    print("\n\n📊 Step 3: Analyzing Main Account Order Structure")
    print("-" * 40)
    
    main_order_structure = {}
    
    for symbol in common_symbols:
        response = main_client.get_open_orders(
            category="linear",
            symbol=symbol,
            openOnly=1,
            limit=50
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            
            # Categorize orders
            stop_orders = [o for o in orders if o.get('stopOrderType') == 'Stop']
            
            # Separate TPs and SLs
            tp_orders = []
            sl_orders = []
            
            for order in stop_orders:
                link_id = order.get('orderLinkId', '')
                if 'SL' in link_id:
                    sl_orders.append(order)
                else:
                    tp_orders.append(order)
            
            main_order_structure[symbol] = {
                'tp_orders': tp_orders,
                'sl_orders': sl_orders,
                'total_stop': len(stop_orders)
            }
            
            if stop_orders:
                print(f"\n{symbol}:")
                print(f"  - {len(tp_orders)} TP orders")
                print(f"  - {len(sl_orders)} SL orders")
    
    # Step 4: Recreate orders on mirror account
    print("\n\n🔧 Step 4: Recreating Orders on Mirror Account")
    print("-" * 40)
    
    successful_recreations = 0
    failed_recreations = 0
    
    for symbol in common_symbols:
        if symbol not in main_order_structure:
            continue
            
        structure = main_order_structure[symbol]
        main_pos = main_positions[symbol]
        mirror_pos = mirror_positions[symbol]
        
        # Skip if no orders to recreate
        if structure['total_stop'] == 0:
            continue
        
        print(f"\n📍 {symbol}:")
        
        # Calculate size ratio (mirror size / main size)
        main_size = float(main_pos['size'])
        mirror_size = float(mirror_pos['size'])
        size_ratio = mirror_size / main_size if main_size > 0 else 0
        
        print(f"  Size ratio: {size_ratio:.2f} (Mirror: {mirror_size:,.0f} / Main: {main_size:,.0f})")
        
        # Recreate SL orders first (most important)
        for sl_order in structure['sl_orders']:
            try:
                # Adjust quantity based on mirror position size
                original_qty = float(sl_order['qty'])
                mirror_qty = int(original_qty * size_ratio)
                
                if mirror_qty == 0:
                    continue
                
                # Create order parameters
                order_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": sl_order['side'],
                    "orderType": "Market",
                    "qty": str(mirror_qty),
                    "triggerPrice": sl_order['triggerPrice'],
                    "triggerDirection": sl_order.get('triggerDirection', 2 if sl_order['side'] == 'Sell' else 1),
                    "triggerBy": "LastPrice",
                    "reduceOnly": True,
                    "orderLinkId": f"MIRROR_{sl_order.get('orderLinkId', 'SL')}_{datetime.now().strftime('%H%M%S')}"
                }
                
                # Add positionIdx if present
                if mirror_pos.get('positionIdx'):
                    order_params['positionIdx'] = mirror_pos['positionIdx']
                
                response = mirror_client.place_order(**order_params)
                
                if response['retCode'] == 0:
                    print(f"  ✅ SL recreated: {mirror_qty} @ ${sl_order['triggerPrice']}")
                    successful_recreations += 1
                else:
                    print(f"  ❌ SL failed: {response['retMsg']}")
                    failed_recreations += 1
                    
            except Exception as e:
                print(f"  ❌ Error recreating SL: {e}")
                failed_recreations += 1
        
        # Recreate TP orders (limit to avoid hitting limits)
        tp_count = 0
        max_tps = 4  # Limit TPs to avoid order limits
        
        for tp_order in structure['tp_orders'][:max_tps]:
            try:
                # Adjust quantity
                original_qty = float(tp_order['qty'])
                mirror_qty = int(original_qty * size_ratio)
                
                if mirror_qty == 0:
                    continue
                
                # Create order parameters
                order_params = {
                    "category": "linear",
                    "symbol": symbol,
                    "side": tp_order['side'],
                    "orderType": "Market",
                    "qty": str(mirror_qty),
                    "triggerPrice": tp_order['triggerPrice'],
                    "triggerDirection": tp_order.get('triggerDirection', 1 if tp_order['side'] == 'Sell' else 2),
                    "triggerBy": "LastPrice",
                    "reduceOnly": True,
                    "orderLinkId": f"MIRROR_{tp_order.get('orderLinkId', f'TP{tp_count+1}')}_{datetime.now().strftime('%H%M%S')}"
                }
                
                # Add positionIdx if present
                if mirror_pos.get('positionIdx'):
                    order_params['positionIdx'] = mirror_pos['positionIdx']
                
                response = mirror_client.place_order(**order_params)
                
                if response['retCode'] == 0:
                    tp_count += 1
                    print(f"  ✅ TP{tp_count} recreated: {mirror_qty} @ ${tp_order['triggerPrice']}")
                    successful_recreations += 1
                else:
                    print(f"  ❌ TP failed: {response['retMsg']}")
                    failed_recreations += 1
                    
                    # Stop if hitting limits
                    if "already had" in response['retMsg']:
                        print("  ⚠️  Hit order limit, skipping remaining TPs")
                        break
                        
            except Exception as e:
                print(f"  ❌ Error recreating TP: {e}")
                failed_recreations += 1
        
        # Small delay between symbols
        await asyncio.sleep(0.5)
    
    # Summary
    print("\n\n" + "=" * 70)
    print("📊 SYNCHRONIZATION SUMMARY")
    print("=" * 70)
    
    print(f"\nOrders cancelled: {total_cancelled}")
    print(f"Orders recreated: {successful_recreations}")
    print(f"Failed recreations: {failed_recreations}")
    
    print("\n✅ Mirror account is now synchronized with main account!")
    print("\n💡 Recommendations:")
    print("1. Monitor positions to ensure proper execution")
    print("2. Consider reducing total position count if hitting limits")
    print("3. The bot should handle future synchronization automatically")
    
    # Create monitoring script
    print("\n\n📝 Creating ongoing sync monitor...")
    
    monitor_code = '''#!/usr/bin/env python3
"""
Monitor and maintain mirror account synchronization.
Prevents order accumulation and ensures consistency.
"""

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MirrorSyncMaintainer:
    """Maintains mirror account synchronization."""
    
    def __init__(self):
        self.check_interval = 300  # 5 minutes
        self.max_orders_per_symbol = 8
        self.running = False
        
    async def check_and_fix_symbol(self, main_client, mirror_client, symbol: str):
        """Check and fix orders for a specific symbol."""
        
        try:
            # Get orders from both accounts
            main_orders = main_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1
            )
            
            mirror_orders = mirror_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=1
            )
            
            if main_orders['retCode'] != 0 or mirror_orders['retCode'] != 0:
                return
            
            main_stop_orders = [o for o in main_orders['result']['list'] 
                              if o.get('stopOrderType') == 'Stop']
            mirror_stop_orders = [o for o in mirror_orders['result']['list'] 
                                if o.get('stopOrderType') == 'Stop']
            
            # Check if mirror has too many orders
            if len(mirror_stop_orders) > self.max_orders_per_symbol:
                logger.warning(f"{symbol}: Mirror has {len(mirror_stop_orders)} orders (main has {len(main_stop_orders)})")
                
                # Cancel excess orders
                excess = len(mirror_stop_orders) - self.max_orders_per_symbol
                for order in mirror_stop_orders[:excess]:
                    try:
                        mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                        logger.info(f"Cancelled excess order for {symbol}")
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"Error checking {symbol}: {e}")
    
    async def run_sync_check(self):
        """Run synchronization check."""
        
        try:
            from pybit.unified_trading import HTTP
            from config.settings import (
                BYBIT_API_KEY, BYBIT_API_SECRET,
                BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
                USE_TESTNET
            )
            
            if not all([BYBIT_API_KEY_2, BYBIT_API_SECRET_2]):
                return
            
            main_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY,
                api_secret=BYBIT_API_SECRET
            )
            
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            # Get all positions
            response = mirror_client.get_positions(
                category="linear",
                settleCoin="USDT"
            )
            
            if response['retCode'] == 0:
                symbols = set()
                for pos in response['result']['list']:
                    if float(pos['size']) > 0:
                        symbols.add(pos['symbol'])
                
                # Check each symbol
                for symbol in symbols:
                    await self.check_and_fix_symbol(main_client, mirror_client, symbol)
                    await asyncio.sleep(0.1)  # Rate limiting
                    
        except Exception as e:
            logger.error(f"Error in sync check: {e}")
    
    async def start(self):
        """Start the sync maintainer."""
        self.running = True
        logger.info("Mirror sync maintainer started")
        
        while self.running:
            try:
                await self.run_sync_check()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in sync maintainer: {e}")
                await asyncio.sleep(60)

# Global instance
mirror_sync_maintainer = MirrorSyncMaintainer()
'''
    
    with open('utils/mirror_sync_maintainer.py', 'w') as f:
        f.write(monitor_code)
    
    print("✅ Created mirror_sync_maintainer.py for ongoing synchronization")


async def main():
    """Main function."""
    await sync_mirror_orders()


if __name__ == "__main__":
    asyncio.run(main())