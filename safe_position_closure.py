#!/usr/bin/env python3
"""
Safe Position Closure Script
Closes specified positions and orders with comprehensive verification
"""
import asyncio
import sys
sys.path.append('.')
from clients.bybit_helpers import get_all_positions, get_all_open_orders, api_call_with_retry
from execution.mirror_trader import bybit_client_2
import time

class SafePositionCloser:
    def __init__(self):
        self.mirror_symbols = [
            'BATUSDT', 'RENDERUSDT', 'NTRNUSDT', 'ONTUSDT', 'CHZUSDT', 
            'NOTUSDT', 'FLOWUSDT', 'ZECUSDT', 'SXPUSDT', 'WOOUSDT', 
            'ZRXUSDT', 'ORDIUSDT', 'SEIUSDT', 'BAKEUSDT', 'HIGHUSDT', 
            'MEWUSDT', 'ICPUSDT', 'PENDLEUSDT'
        ]
        self.main_symbols = ['HIGHUSDT']
        
    async def cancel_order_safe(self, client, symbol, order_id, account_type="main"):
        """Safely cancel an order with retry logic"""
        try:
            if account_type == "mirror":
                response = await api_call_with_retry(
                    lambda: client.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order_id
                    )
                )
            else:
                from clients.bybit_helpers import cancel_order_with_retry
                return await cancel_order_with_retry(symbol, order_id)
                
            if response and response.get('retCode') == 0:
                return True
            else:
                print(f"  ⚠️ Cancel response: {response}")
                return False
                
        except Exception as e:
            error_str = str(e).lower()
            if any(term in error_str for term in ["not found", "invalid orderid", "order not exist"]):
                print(f"  ℹ️ Order {order_id[:8]}... already cancelled/filled")
                return True
            else:
                print(f"  ❌ Error cancelling order {order_id[:8]}...: {e}")
                return False
    
    async def close_position_safe(self, client, symbol, side, size, account_type="main"):
        """Safely close a position using market order"""
        try:
            # Determine opposite side for closing
            close_side = "Buy" if side == "Sell" else "Sell"
            
            if account_type == "mirror":
                response = await api_call_with_retry(
                    lambda: client.place_order(
                        category="linear",
                        symbol=symbol,
                        side=close_side,
                        orderType="Market",
                        qty=str(size),
                        reduceOnly=True
                    )
                )
            else:
                from clients.bybit_helpers import place_order_with_retry
                response = await place_order_with_retry(
                    symbol=symbol,
                    side=close_side,
                    order_type="Market",
                    qty=str(size),
                    reduce_only=True
                )
                
            if response and response.get('orderId'):
                return True, response.get('orderId')
            else:
                print(f"  ❌ Close response: {response}")
                return False, None
                
        except Exception as e:
            print(f"  ❌ Error closing position: {e}")
            return False, None
    
    async def close_mirror_positions(self):
        """Close all specified mirror account positions and orders"""
        print("🪞 CLOSING MIRROR ACCOUNT POSITIONS AND ORDERS")
        print("=" * 60)
        
        # Get current state
        positions = await get_all_positions(client=bybit_client_2)
        orders = await get_all_open_orders(client=bybit_client_2)
        
        # Group orders by symbol
        orders_by_symbol = {}
        for order in orders:
            symbol = order.get('symbol', '')
            if symbol in self.mirror_symbols:
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
        
        total_cancelled = 0
        total_closed = 0
        
        # Process each symbol
        for symbol in self.mirror_symbols:
            print(f"\n📊 Processing {symbol}...")
            
            # Cancel all orders for this symbol first
            if symbol in orders_by_symbol:
                symbol_orders = orders_by_symbol[symbol]
                print(f"  🧹 Cancelling {len(symbol_orders)} orders...")
                
                for order in symbol_orders:
                    order_id = order.get('orderId')
                    order_type = order.get('orderType', '')
                    side = order.get('side', '')
                    qty = order.get('qty', '0')
                    status = order.get('orderStatus', '')
                    
                    print(f"    📋 Cancelling {order_type} {side} {qty} ({status})")
                    success = await self.cancel_order_safe(bybit_client_2, symbol, order_id, "mirror")
                    if success:
                        total_cancelled += 1
                        print(f"    ✅ Cancelled order {order_id[:8]}...")
                    
                    # Small delay between cancellations
                    await asyncio.sleep(0.1)
            
            # Close position if exists
            position = None
            for pos in positions:
                if pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0:
                    position = pos
                    break
            
            if position:
                side = position.get('side', '')
                size = position.get('size', '0')
                pnl = position.get('unrealisedPnl', '0')
                
                print(f"  📈 Closing position: {side} {size} (PnL: {pnl})")
                success, order_id = await self.close_position_safe(bybit_client_2, symbol, side, size, "mirror")
                if success:
                    total_closed += 1
                    print(f"  ✅ Position closed with order {order_id[:8]}...")
                    
                # Small delay between position closures
                await asyncio.sleep(0.2)
        
        print(f"\n📋 MIRROR CLOSURE SUMMARY:")
        print(f"  🧹 Orders cancelled: {total_cancelled}")
        print(f"  📈 Positions closed: {total_closed}")
        
        return total_cancelled, total_closed
    
    async def close_main_positions(self):
        """Close specified main account positions and orders"""
        print("\n🎯 CHECKING MAIN ACCOUNT POSITIONS")
        print("=" * 60)
        
        # Get current state
        positions = await get_all_positions()
        orders = await get_all_open_orders()
        
        # Check for HIGHUSDT
        highusdt_position = None
        highusdt_orders = []
        
        for pos in positions:
            if pos.get('symbol') == 'HIGHUSDT' and float(pos.get('size', 0)) > 0:
                highusdt_position = pos
                break
        
        for order in orders:
            if order.get('symbol') == 'HIGHUSDT':
                highusdt_orders.append(order)
        
        if not highusdt_position and not highusdt_orders:
            print("  ℹ️ No HIGHUSDT position or orders found - nothing to close")
            return 0, 0
        
        total_cancelled = 0
        total_closed = 0
        
        # Cancel orders first
        if highusdt_orders:
            print(f"  🧹 Cancelling {len(highusdt_orders)} HIGHUSDT orders...")
            for order in highusdt_orders:
                order_id = order.get('orderId')
                order_type = order.get('orderType', '')
                side = order.get('side', '')
                qty = order.get('qty', '0')
                
                print(f"    📋 Cancelling {order_type} {side} {qty}")
                success = await self.cancel_order_safe(None, 'HIGHUSDT', order_id, "main")
                if success:
                    total_cancelled += 1
                    print(f"    ✅ Cancelled order {order_id[:8]}...")
                
                await asyncio.sleep(0.1)
        
        # Close position
        if highusdt_position:
            side = highusdt_position.get('side', '')
            size = highusdt_position.get('size', '0')
            pnl = highusdt_position.get('unrealisedPnl', '0')
            
            print(f"  📈 Closing HIGHUSDT position: {side} {size} (PnL: {pnl})")
            success, order_id = await self.close_position_safe(None, 'HIGHUSDT', side, size, "main")
            if success:
                total_closed += 1
                print(f"  ✅ Position closed with order {order_id[:8]}...")
        
        print(f"\n📋 MAIN CLOSURE SUMMARY:")
        print(f"  🧹 Orders cancelled: {total_cancelled}")
        print(f"  📈 Positions closed: {total_closed}")
        
        return total_cancelled, total_closed
    
    async def verify_closures(self):
        """Verify all specified positions and orders are closed"""
        print("\n🔍 VERIFICATION: Checking closure completion...")
        print("=" * 60)
        
        # Check mirror account
        mirror_positions = await get_all_positions(client=bybit_client_2)
        mirror_orders = await get_all_open_orders(client=bybit_client_2)
        
        remaining_mirror_positions = []
        remaining_mirror_orders = []
        
        for pos in mirror_positions:
            symbol = pos.get('symbol', '')
            size = float(pos.get('size', 0))
            if size > 0 and symbol in self.mirror_symbols:
                remaining_mirror_positions.append(f"{symbol} ({pos.get('side')} {size})")
        
        for order in mirror_orders:
            symbol = order.get('symbol', '')
            if symbol in self.mirror_symbols:
                remaining_mirror_orders.append(f"{symbol} ({order.get('orderType')} {order.get('side')})")
        
        # Check main account
        main_positions = await get_all_positions()
        main_orders = await get_all_open_orders()
        
        remaining_main_positions = []
        remaining_main_orders = []
        
        for pos in main_positions:
            symbol = pos.get('symbol', '')
            size = float(pos.get('size', 0))
            if size > 0 and symbol in self.main_symbols:
                remaining_main_positions.append(f"{symbol} ({pos.get('side')} {size})")
        
        for order in main_orders:
            symbol = order.get('symbol', '')
            if symbol in self.main_symbols:
                remaining_main_orders.append(f"{symbol} ({order.get('orderType')} {order.get('side')})")
        
        # Report results
        print(f"🪞 Mirror account remaining:")
        print(f"  📊 Positions: {len(remaining_mirror_positions)} {remaining_mirror_positions}")
        print(f"  📋 Orders: {len(remaining_mirror_orders)} {remaining_mirror_orders}")
        
        print(f"🎯 Main account remaining:")
        print(f"  📊 Positions: {len(remaining_main_positions)} {remaining_main_positions}")
        print(f"  📋 Orders: {len(remaining_main_orders)} {remaining_main_orders}")
        
        all_closed = (len(remaining_mirror_positions) == 0 and len(remaining_mirror_orders) == 0 and 
                     len(remaining_main_positions) == 0 and len(remaining_main_orders) == 0)
        
        if all_closed:
            print("\n✅ SUCCESS: All specified positions and orders have been closed!")
        else:
            print("\n⚠️ WARNING: Some positions or orders may still be open - please check manually")
        
        return all_closed

async def main():
    closer = SafePositionCloser()
    
    print("🚀 SAFE POSITION CLOSURE SCRIPT")
    print("=" * 60)
    print("This will close:")
    print("📋 Mirror account: 18 symbols and all their orders")
    print("📋 Main account: HIGHUSDT position and orders only")
    print("=" * 60)
    
    try:
        # Close mirror positions
        mirror_cancelled, mirror_closed = await closer.close_mirror_positions()
        
        # Small delay before main account
        await asyncio.sleep(1)
        
        # Close main positions  
        main_cancelled, main_closed = await closer.close_main_positions()
        
        # Wait for closures to settle
        print("\n⏳ Waiting 3 seconds for closures to settle...")
        await asyncio.sleep(3)
        
        # Verify all closures
        all_closed = await closer.verify_closures()
        
        print(f"\n🎯 FINAL SUMMARY:")
        print(f"  🪞 Mirror: {mirror_cancelled} orders cancelled, {mirror_closed} positions closed")
        print(f"  🎯 Main: {main_cancelled} orders cancelled, {main_closed} positions closed")
        print(f"  ✅ All closed: {'Yes' if all_closed else 'No'}")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())