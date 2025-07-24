#!/usr/bin/env python3
"""
Properly sync mirror account orders to match main account.
Handles the correct order statuses including Untriggered orders.
"""

import asyncio
import os
import sys
import time
import hashlib
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


def generate_order_link_id(prefix):
    """Generate unique order link ID."""
    timestamp = str(int(time.time() * 1000))
    random_str = hashlib.md5(f"{prefix}{timestamp}".encode()).hexdigest()[:6]
    return f"{prefix}_{timestamp}_{random_str}"[:36]


async def sync_mirror_orders_properly():
    """Properly sync all orders from main account to mirror account."""
    
    print("🔄 Properly Syncing Mirror Account Orders")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    from pybit.unified_trading import HTTP
    from config.settings import (
        BYBIT_API_KEY, BYBIT_API_SECRET,
        BYBIT_API_KEY_2, BYBIT_API_SECRET_2,
        USE_TESTNET, ENABLE_MIRROR_TRADING
    )
    
    if not ENABLE_MIRROR_TRADING or not BYBIT_API_KEY_2:
        print("❌ Mirror trading not enabled")
        return
    
    # Initialize clients
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
    
    print("\n📋 Fetching positions and orders from both accounts...")
    
    try:
        # Get all positions from both accounts
        main_positions = {}
        mirror_positions = {}
        
        # Main account positions
        main_resp = main_client.get_positions(category="linear", settleCoin="USDT")
        if main_resp['retCode'] == 0:
            for pos in main_resp['result']['list']:
                if float(pos.get('size', 0)) > 0:
                    key = f"{pos['symbol']}_{pos['side']}"
                    main_positions[key] = pos
        
        # Mirror account positions
        mirror_resp = mirror_client.get_positions(category="linear", settleCoin="USDT")
        if mirror_resp['retCode'] == 0:
            for pos in mirror_resp['result']['list']:
                if float(pos.get('size', 0)) > 0:
                    key = f"{pos['symbol']}_{pos['side']}"
                    mirror_positions[key] = pos
        
        print(f"\nMain account: {len(main_positions)} positions")
        print(f"Mirror account: {len(mirror_positions)} positions")
        
        # Process each mirror position that exists on main
        positions_synced = 0
        orders_added = 0
        orders_cancelled = 0
        
        for key, mirror_pos in mirror_positions.items():
            symbol = mirror_pos['symbol']
            side = mirror_pos['side']
            
            if key not in main_positions:
                print(f"\n⚠️ {symbol} {side} exists on mirror but not main - skipping")
                continue
            
            print(f"\n📍 Syncing {symbol} {side}...")
            
            main_pos = main_positions[key]
            mirror_size = float(mirror_pos['size'])
            mirror_avg_price = float(mirror_pos.get('avgPrice', 0))
            mirror_position_idx = mirror_pos.get('positionIdx', 0)
            
            # Get orders from both accounts using openOnly=0 to get ALL orders
            main_orders_resp = main_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=0,  # Get ALL orders including Untriggered
                limit=50
            )
            
            mirror_orders_resp = mirror_client.get_open_orders(
                category="linear",
                symbol=symbol,
                openOnly=0,  # Get ALL orders including Untriggered
                limit=50
            )
            
            if main_orders_resp['retCode'] != 0 or mirror_orders_resp['retCode'] != 0:
                print(f"   ❌ Error fetching orders")
                continue
            
            # Get only ACTIVE reduce orders (Untriggered, New, PartiallyFilled)
            active_statuses = ['Untriggered', 'New', 'PartiallyFilled']
            
            main_reduce_orders = [o for o in main_orders_resp['result']['list'] 
                                if o.get('reduceOnly') and o.get('orderStatus') in active_statuses]
            
            mirror_reduce_orders = [o for o in mirror_orders_resp['result']['list'] 
                                  if o.get('reduceOnly') and o.get('orderStatus') in active_statuses]
            
            # Categorize orders
            main_tp_orders = []
            main_sl_orders = []
            mirror_tp_orders = []
            mirror_sl_orders = []
            
            # Process main orders
            for order in main_reduce_orders:
                trigger_price_str = order.get('triggerPrice', '')
                if trigger_price_str and trigger_price_str != '0':
                    trigger_price = float(trigger_price_str)
                    
                    if side == 'Buy':
                        if trigger_price > mirror_avg_price:
                            main_tp_orders.append(order)
                        else:
                            main_sl_orders.append(order)
                    else:  # Sell
                        if trigger_price < mirror_avg_price:
                            main_tp_orders.append(order)
                        else:
                            main_sl_orders.append(order)
            
            # Process mirror orders
            for order in mirror_reduce_orders:
                trigger_price_str = order.get('triggerPrice', '')
                if trigger_price_str and trigger_price_str != '0':
                    trigger_price = float(trigger_price_str)
                    
                    if side == 'Buy':
                        if trigger_price > mirror_avg_price:
                            mirror_tp_orders.append(order)
                        else:
                            mirror_sl_orders.append(order)
                    else:  # Sell
                        if trigger_price < mirror_avg_price:
                            mirror_tp_orders.append(order)
                        else:
                            mirror_sl_orders.append(order)
            
            print(f"   Main: {len(main_tp_orders)} active TPs, {len(main_sl_orders)} active SLs")
            print(f"   Mirror: {len(mirror_tp_orders)} active TPs, {len(mirror_sl_orders)} active SLs")
            
            # Only proceed if there's a mismatch
            if (len(main_tp_orders) == len(mirror_tp_orders) and 
                len(main_sl_orders) == len(mirror_sl_orders)):
                print(f"   ✅ Orders already match")
                continue
            
            # Cancel all existing mirror orders first
            if mirror_tp_orders or mirror_sl_orders:
                print(f"\n   📤 Cancelling existing mirror orders...")
                
                for order in mirror_tp_orders + mirror_sl_orders:
                    try:
                        cancel_resp = mirror_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order['orderId']
                        )
                        
                        if cancel_resp['retCode'] == 0:
                            orders_cancelled += 1
                            print(f"      ✅ Cancelled order at ${float(order['triggerPrice']):.4f}")
                        else:
                            print(f"      ⚠️ Could not cancel: {cancel_resp['retMsg']}")
                    except Exception as e:
                        print(f"      ❌ Error: {e}")
                
                await asyncio.sleep(1)  # Wait for cancellations to process
            
            # Copy all orders from main to mirror
            if main_tp_orders or main_sl_orders:
                print(f"\n   📥 Copying orders from main to mirror...")
                
                # Sort TP orders by price
                if side == 'Buy':
                    main_tp_orders.sort(key=lambda x: float(x['triggerPrice']))
                else:
                    main_tp_orders.sort(key=lambda x: float(x['triggerPrice']), reverse=True)
                
                # Copy TP orders
                for i, order in enumerate(main_tp_orders):
                    try:
                        trigger_price = order.get('triggerPrice')
                        
                        # Calculate proportional quantity for mirror
                        main_qty = float(order.get('qty', 0))
                        main_size = float(main_pos['size'])
                        
                        # Use same proportion
                        proportion = main_qty / main_size
                        mirror_qty = int(mirror_size * proportion)
                        
                        if mirror_qty == 0:
                            mirror_qty = 1  # Minimum quantity
                        
                        order_params = {
                            "category": "linear",
                            "symbol": symbol,
                            "side": "Sell" if side == "Buy" else "Buy",
                            "orderType": "Market",
                            "qty": str(mirror_qty),
                            "triggerPrice": trigger_price,
                            "triggerBy": "LastPrice",
                            "reduceOnly": True,
                            "orderLinkId": generate_order_link_id(f"MIRROR_TP{i+1}_SYNC")
                        }
                        
                        order_params['triggerDirection'] = 1 if side == "Buy" else 2
                        
                        if mirror_position_idx > 0:
                            order_params['positionIdx'] = mirror_position_idx
                        
                        resp = mirror_client.place_order(**order_params)
                        
                        if resp['retCode'] == 0:
                            orders_added += 1
                            print(f"      ✅ Added TP{i+1} at ${float(trigger_price):.4f} for {mirror_qty:,} units")
                        else:
                            print(f"      ❌ Failed to add TP{i+1}: {resp['retMsg']}")
                            
                    except Exception as e:
                        print(f"      ❌ Error adding TP{i+1}: {e}")
                    
                    await asyncio.sleep(0.2)
                
                # Copy SL orders
                for order in main_sl_orders:
                    try:
                        trigger_price = order.get('triggerPrice')
                        
                        # SL should be for full position size
                        mirror_qty = int(mirror_size)
                        
                        order_params = {
                            "category": "linear",
                            "symbol": symbol,
                            "side": "Sell" if side == "Buy" else "Buy",
                            "orderType": "Market",
                            "qty": str(mirror_qty),
                            "triggerPrice": trigger_price,
                            "triggerBy": "LastPrice",
                            "reduceOnly": True,
                            "orderLinkId": generate_order_link_id(f"MIRROR_SL_SYNC")
                        }
                        
                        order_params['triggerDirection'] = 2 if side == "Buy" else 1
                        
                        if mirror_position_idx > 0:
                            order_params['positionIdx'] = mirror_position_idx
                        
                        resp = mirror_client.place_order(**order_params)
                        
                        if resp['retCode'] == 0:
                            orders_added += 1
                            print(f"      ✅ Added SL at ${float(trigger_price):.4f} for {mirror_qty:,} units")
                        else:
                            print(f"      ❌ Failed to add SL: {resp['retMsg']}")
                            
                    except Exception as e:
                        print(f"      ❌ Error adding SL: {e}")
                    
                    await asyncio.sleep(0.2)
            
            positions_synced += 1
        
        # Handle positions that exist on main but not mirror
        print("\n\n" + "="*80)
        print("CHECKING FOR MISSING POSITIONS ON MIRROR")
        print("="*80)
        
        for key, main_pos in main_positions.items():
            if key not in mirror_positions:
                symbol = main_pos['symbol']
                side = main_pos['side']
                print(f"\n⚠️ {symbol} {side} exists on main but not mirror")
        
        # Summary
        print("\n\n" + "="*80)
        print("SYNC SUMMARY")
        print("="*80)
        print(f"\n✅ Sync completed!")
        print(f"   Positions synced: {positions_synced}")
        print(f"   Orders cancelled: {orders_cancelled}")
        print(f"   Orders added: {orders_added}")
        
        # Run a quick verification
        if positions_synced > 0:
            print("\n📋 Running quick verification...")
            await asyncio.sleep(2)
            
            # Just show counts for a few positions
            verify_symbols = ['ALTUSDT', 'TONUSDT', 'NEARUSDT']
            
            for symbol in verify_symbols:
                # Get orders using openOnly=0
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
                    main_active = len([o for o in main_orders['result']['list'] 
                                     if o.get('reduceOnly') and o.get('orderStatus') in active_statuses])
                    mirror_active = len([o for o in mirror_orders['result']['list'] 
                                       if o.get('reduceOnly') and o.get('orderStatus') in active_statuses])
                    
                    status = "✅" if main_active == mirror_active else "⚠️"
                    print(f"   {status} {symbol}: Main has {main_active}, Mirror has {mirror_active}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main function."""
    await sync_mirror_orders_properly()


if __name__ == "__main__":
    asyncio.run(main())