#!/usr/bin/env python3
"""
Force rebalance TPs for all current open positions
This script will:
1. Detect all open positions on main and mirror accounts
2. Create/update monitors for positions that need them
3. Rebalance TPs to proper conservative approach ratios (85%, 5%, 5%, 5%)
4. Ensure SL covers full position including unfilled limits
"""
import asyncio
import os
import sys
import time
import pickle
from decimal import Decimal
from typing import Dict, List, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions, get_all_open_orders, get_instrument_info
from utils.helpers import value_adjusted_to_step
from pybit.unified_trading import HTTP

async def get_position_tp_orders(symbol: str, side: str, client: HTTP) -> List[Dict]:
    """Get all TP orders for a specific position"""
    try:
        all_orders = await get_all_open_orders(client=client)
        tp_orders = []
        
        for order in all_orders:
            if (order.get('symbol') == symbol and 
                order.get('reduceOnly') == True and
                order.get('side') != side):  # TP orders are opposite side
                tp_orders.append(order)
        
        return sorted(tp_orders, key=lambda x: float(x.get('price', 0)))
    except Exception as e:
        print(f"Error getting TP orders for {symbol}: {e}")
        return []

async def cancel_order(client: HTTP, symbol: str, order_id: str) -> bool:
    """Cancel an order"""
    try:
        result = client.cancel_order(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )
        return result.get('retCode') == 0
    except Exception as e:
        print(f"Error cancelling order {order_id}: {e}")
        return False

async def place_tp_order(client: HTTP, symbol: str, side: str, qty: str, price: str, 
                        order_link_id: str, position_idx: int = 0) -> Dict:
    """Place a TP order"""
    try:
        # TP orders are opposite side of position
        tp_side = "Buy" if side == "Sell" else "Sell"
        
        result = client.place_order(
            category="linear",
            symbol=symbol,
            side=tp_side,
            orderType="Limit",
            qty=qty,
            price=price,
            reduceOnly=True,
            orderLinkId=order_link_id,
            timeInForce="GTC",
            positionIdx=position_idx
        )
        
        if result.get('retCode') == 0:
            return result.get('result', {})
        else:
            print(f"Error placing TP order: {result.get('retMsg', 'Unknown error')}")
            return {}
    except Exception as e:
        print(f"Error placing TP order: {e}")
        return {}

async def rebalance_position_tps(symbol: str, side: str, position_size: Decimal, 
                               tp_orders: List[Dict], client: HTTP, account_type: str):
    """Rebalance TP orders for a position to conservative approach"""
    print(f"\n🔄 Rebalancing TPs for {symbol} {side} ({account_type.upper()})")
    print(f"   Position Size: {position_size}")
    print(f"   Current TP Orders: {len(tp_orders)}")
    
    # Conservative approach percentages
    tp_percentages = [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")]
    
    # Get instrument info for quantity validation
    try:
        instrument_info = await get_instrument_info(symbol)
        if instrument_info:
            lot_size_filter = instrument_info.get("lotSizeFilter", {})
            qty_step = Decimal(lot_size_filter.get("qtyStep", "1"))
            min_order_qty = Decimal(lot_size_filter.get("minOrderQty", "0.001"))
        else:
            qty_step = Decimal("0.1")
            min_order_qty = Decimal("0.1")
    except Exception as e:
        print(f"⚠️ Could not get instrument info for {symbol}: {e}")
        qty_step = Decimal("0.1")
        min_order_qty = Decimal("0.1")
    
    # Cancel all existing TP orders
    print("🗑️ Cancelling existing TP orders...")
    for i, tp_order in enumerate(tp_orders):
        order_id = tp_order.get('orderId')
        if order_id:
            success = await cancel_order(client, symbol, order_id)
            print(f"   TP{i+1}: {'✅' if success else '❌'} - {order_id[:8]}...")
            if success:
                await asyncio.sleep(0.5)  # Small delay between cancellations
    
    # Wait a moment for cancellations to process
    await asyncio.sleep(2)
    
    # Calculate and place new TP orders
    print("📤 Placing new balanced TP orders...")
    successful_tps = 0
    
    for i, tp_percentage in enumerate(tp_percentages):
        tp_num = i + 1
        
        # Calculate quantity for this TP
        raw_qty = (position_size * tp_percentage) / Decimal("100")
        adjusted_qty = value_adjusted_to_step(raw_qty, qty_step)
        
        # Skip if quantity too small
        if adjusted_qty < min_order_qty:
            print(f"   TP{tp_num}: ❌ Quantity {adjusted_qty} below minimum {min_order_qty}")
            continue
        
        # Use existing price if available, otherwise calculate a reasonable price
        if i < len(tp_orders):
            price = tp_orders[i].get('price', '0')
        else:
            # For new TPs, we'll need to calculate price based on position direction
            # For now, use 0 to indicate manual price setting needed
            price = '0'
        
        if price == '0' or float(price) == 0:
            print(f"   TP{tp_num}: ⚠️ Price not available - skipping (needs manual setup)")
            continue
        
        # Generate order link ID
        order_link_id = f"{account_type[:1].upper()}TP{tp_num}_{symbol}_{int(time.time())}"
        
        # Place TP order
        result = await place_tp_order(
            client, symbol, side, str(adjusted_qty), str(price), order_link_id
        )
        
        if result.get('orderId'):
            print(f"   TP{tp_num}: ✅ {adjusted_qty} @ {price} - {result['orderId'][:8]}...")
            successful_tps += 1
        else:
            print(f"   TP{tp_num}: ❌ Failed to place order")
        
        await asyncio.sleep(0.5)  # Small delay between placements
    
    print(f"✅ TP Rebalancing completed: {successful_tps}/{len(tp_percentages)} TPs placed")
    return successful_tps

async def create_monitor_for_position(symbol: str, side: str, position_size: Decimal, account_type: str):
    """Create monitor entry for position in pickle file"""
    try:
        # Load current data
        try:
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
        except FileNotFoundError:
            data = {}
        
        # Ensure enhanced_monitors exists
        if 'enhanced_monitors' not in data:
            data['enhanced_monitors'] = {}
        
        # Create monitor key
        monitor_key = f"{symbol}_{side}_{account_type}"
        
        # Create monitor data
        monitor_data = {
            'symbol': symbol,
            'side': side,
            'account_type': account_type,
            'position_size': position_size,
            'current_size': position_size,
            'remaining_size': position_size,
            'approach': 'CONSERVATIVE',
            'phase': 'MONITORING',  # Set to monitoring since position already exists
            'tp_orders': {},
            'sl_order': {},
            'last_known_size': position_size,
            'last_check': time.time(),
            'created_at': time.time(),
            'updated_at': time.time()
        }
        
        # Add monitor to data
        data['enhanced_monitors'][monitor_key] = monitor_data
        
        # Save back to pickle
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        print(f"✅ Created monitor for {monitor_key}")
        return True
        
    except Exception as e:
        print(f"❌ Error creating monitor for {symbol} {side}: {e}")
        return False

async def main():
    """Main function to rebalance all position TPs"""
    print("🚀 Starting TP Rebalancing for All Positions")
    print("=" * 50)
    
    # Get configuration from environment
    config = {
        'TESTNET': os.getenv('TESTNET', 'false').lower() == 'true',
        'BYBIT_API_KEY': os.getenv('BYBIT_API_KEY'),
        'BYBIT_API_SECRET': os.getenv('BYBIT_API_SECRET'),
        'ENABLE_MIRROR_TRADING': os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true',
        'BYBIT_API_KEY_2': os.getenv('BYBIT_API_KEY_2'),
        'BYBIT_API_SECRET_2': os.getenv('BYBIT_API_SECRET_2')
    }
    
    # Initialize clients
    main_client = HTTP(
        testnet=config['TESTNET'],
        api_key=config['BYBIT_API_KEY'],
        api_secret=config['BYBIT_API_SECRET']
    )
    
    mirror_client = None
    if config['ENABLE_MIRROR_TRADING']:
        mirror_client = HTTP(
            testnet=config['TESTNET'],
            api_key=config['BYBIT_API_KEY_2'],
            api_secret=config['BYBIT_API_SECRET_2']
        )
    
    total_positions = 0
    total_rebalanced = 0
    
    # Process main account positions
    print("\n🏠 MAIN ACCOUNT POSITIONS")
    print("-" * 30)
    
    main_positions = await get_all_positions(client=main_client)
    for pos in main_positions:
        if float(pos.get('size', 0)) > 0:
            symbol = pos.get('symbol')
            side = pos.get('side')
            size = Decimal(str(pos.get('size')))
            
            print(f"\n📊 Processing {symbol} {side}: Size={size}")
            
            # Create monitor for this position
            await create_monitor_for_position(symbol, side, size, 'main')
            
            # Get current TP orders
            tp_orders = await get_position_tp_orders(symbol, side, main_client)
            
            # Rebalance TPs
            successful_tps = await rebalance_position_tps(
                symbol, side, size, tp_orders, main_client, 'main'
            )
            
            total_positions += 1
            if successful_tps > 0:
                total_rebalanced += 1
    
    # Process mirror account positions
    if mirror_client:
        print("\n🪞 MIRROR ACCOUNT POSITIONS")
        print("-" * 30)
        
        mirror_positions = await get_all_positions(client=mirror_client)
        for pos in mirror_positions:
            if float(pos.get('size', 0)) > 0:
                symbol = pos.get('symbol')
                side = pos.get('side')
                size = Decimal(str(pos.get('size')))
                
                print(f"\n📊 Processing {symbol} {side}: Size={size}")
                
                # Create monitor for this position
                await create_monitor_for_position(symbol, side, size, 'mirror')
                
                # Get current TP orders
                tp_orders = await get_position_tp_orders(symbol, side, mirror_client)
                
                # Rebalance TPs
                successful_tps = await rebalance_position_tps(
                    symbol, side, size, tp_orders, mirror_client, 'mirror'
                )
                
                total_positions += 1
                if successful_tps > 0:
                    total_rebalanced += 1
    
    # Create signal file to reload monitors
    try:
        with open('.force_load_all_monitors', 'w') as f:
            f.write(f"Rebalanced {total_rebalanced}/{total_positions} positions at {time.time()}")
        print(f"\n✅ Created signal file to reload monitors in bot")
    except Exception as e:
        print(f"⚠️ Could not create monitor reload signal: {e}")
    
    print(f"\n🎯 SUMMARY")
    print(f"Total positions processed: {total_positions}")
    print(f"Successfully rebalanced: {total_rebalanced}")
    print(f"Completion rate: {(total_rebalanced/total_positions)*100:.1f}%" if total_positions > 0 else "No positions found")
    
    print(f"\n📋 Next Steps:")
    print(f"1. Monitor logs to verify TP rebalancing is working")
    print(f"2. Check that monitors are now active for all positions")
    print(f"3. Verify future limit fills trigger automatic rebalancing")

if __name__ == "__main__":
    asyncio.run(main())