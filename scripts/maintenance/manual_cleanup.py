#!/usr/bin/env python3
"""
Manual cleanup of JTOUSDT Conservative orders
Uses the bot's existing API methods to ensure compatibility
"""

import asyncio
import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_position_info, get_active_tp_sl_orders, api_call_with_retry
from clients.bybit_client import bybit_client
from config.settings import *

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ManualCleanup:
    def __init__(self):
        self.symbol = "JTOUSDT"
        
    async def get_all_orders(self):
        """Get all JTOUSDT orders using bot's method"""
        try:
            logger.info("📋 Getting all JTOUSDT orders...")
            orders = await get_active_tp_sl_orders(self.symbol)
            logger.info(f"Found {len(orders)} orders")
            return orders
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    async def get_position_info(self):
        """Get JTOUSDT position info using bot's method"""
        try:
            logger.info("📊 Getting JTOUSDT position...")
            positions = await get_position_info(self.symbol)
            if positions and len(positions) > 0:
                position = positions[0]  # get_position_info returns a list
                size = float(position.get('size', 0))
                logger.info(f"Position size: {size} JTOUSDT")
                return position
            else:
                logger.info("No position found")
                return None
        except Exception as e:
            logger.error(f"Error getting position: {e}")
            return None
    
    def classify_orders(self, orders):
        """Classify orders by type"""
        fast_orders = []
        conservative_orders = []
        other_orders = []
        
        for order in orders:
            order_link_id = order.get('orderLinkId', '')
            price = float(order.get('triggerPrice', order.get('price', 0)))
            qty = float(order.get('qty', 0))
            side = order.get('side', '')
            
            # Conservative patterns
            if (any(pattern in order_link_id for pattern in ['BOT_CONS', 'CONS_', '80d70557']) or
                price in [1.647, 1.797, 1.846] or 
                '2.05' in str(price) or '2.1' in str(price)):
                conservative_orders.append(order)
            # Fast patterns
            elif (any(pattern in order_link_id for pattern in ['BOT_FAST', 'FAST_']) or
                  (price in [1.896, 2.198] and qty < 300)):  # Smaller qty = likely Fast
                fast_orders.append(order)
            else:
                other_orders.append(order)
        
        return {
            "fast": fast_orders,
            "conservative": conservative_orders,
            "other": other_orders
        }
    
    def print_order_analysis(self, orders, position):
        """Print detailed analysis of orders"""
        classified = self.classify_orders(orders)
        
        print("\n" + "="*60)
        print("📊 CURRENT JTOUSDT ORDER ANALYSIS")
        print("="*60)
        
        if position:
            size = float(position.get('size', 0))
            avg_price = float(position.get('avgPrice', 0))
            pnl = float(position.get('unrealisedPnl', 0))
            print(f"💰 Position: {size} JTOUSDT @ ${avg_price:.6f}")
            print(f"📈 P&L: ${pnl:.2f}")
        else:
            print("❌ No position found")
            return
        
        print(f"\n⚡ FAST ORDERS ({len(classified['fast'])}):")
        fast_total_qty = 0
        for order in classified['fast']:
            order_id = order['orderId']
            order_link_id = order.get('orderLinkId', 'N/A')
            side = order['side']
            qty = float(order.get('qty', 0))
            price = order.get('triggerPrice', order.get('price'))
            order_type = order.get('orderType')
            fast_total_qty += qty
            print(f"   ✅ {side} {qty} @ ${price} | {order_type} | {order_link_id}")
        
        print(f"\n🛡️ CONSERVATIVE ORDERS ({len(classified['conservative'])}):")
        conservative_total_qty = 0
        for order in classified['conservative']:
            order_id = order['orderId']
            order_link_id = order.get('orderLinkId', 'N/A')
            side = order['side']
            qty = float(order.get('qty', 0))
            price = order.get('triggerPrice', order.get('price'))
            order_type = order.get('orderType')
            conservative_total_qty += qty
            print(f"   📋 {side} {qty} @ ${price} | {order_type} | {order_link_id}")
        
        if classified['other']:
            print(f"\n❓ OTHER ORDERS ({len(classified['other'])}):")
            for order in classified['other']:
                order_link_id = order.get('orderLinkId', 'N/A')
                side = order['side']
                qty = float(order.get('qty', 0))
                price = order.get('triggerPrice', order.get('price'))
                print(f"   ? {side} {qty} @ ${price} | {order_link_id}")
        
        print(f"\n📊 QUANTITY ANALYSIS:")
        position_size = float(position.get('size', 0))
        print(f"   Position Size: {position_size}")
        print(f"   Fast Orders Total: {fast_total_qty}")
        print(f"   Conservative Orders Total: {conservative_total_qty}")
        print(f"   Total Orders Qty: {fast_total_qty + conservative_total_qty}")
        
        # Check for over-allocation
        total_orders = fast_total_qty + conservative_total_qty
        if total_orders > position_size * 2.5:  # Each TP+SL should equal position size
            print(f"   ⚠️ OVER-ALLOCATED: {total_orders:.1f} vs expected ~{position_size * 2:.1f}")
        
        return classified
    
    async def cancel_conservative_orders(self, orders):
        """Cancel all Conservative orders"""
        classified = self.classify_orders(orders)
        conservative_orders = classified['conservative']
        
        if not conservative_orders:
            print("✅ No Conservative orders to cancel")
            return
        
        print(f"\n🗑️ CANCELING {len(conservative_orders)} CONSERVATIVE ORDERS...")
        print("="*60)
        
        canceled_count = 0
        for order in conservative_orders:
            try:
                order_id = order['orderId']
                order_link_id = order.get('orderLinkId', 'N/A')
                price = order.get('triggerPrice', order.get('price'))
                qty = order.get('qty')
                
                print(f"   Canceling: {order_link_id} | ${price} | {qty}")
                
                await api_call_with_retry(
                    lambda: bybit_client.cancel_order(
                        category="linear",
                        symbol=self.symbol,
                        orderId=order_id
                    )
                )
                canceled_count += 1
                print(f"   ✅ Canceled: {order_id}")
                
                # Small delay between cancellations
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ Failed to cancel {order.get('orderId')}: {e}")
        
        print(f"\n✅ Canceled {canceled_count}/{len(conservative_orders)} Conservative orders")
    
    async def run_cleanup(self):
        """Run the manual cleanup process"""
        print("\n" + "="*80)
        print("🧹 MANUAL JTOUSDT CLEANUP - CONSERVATIVE ORDERS")
        print("="*80)
        
        # Get current state
        position = await self.get_position_info()
        orders = await self.get_all_orders()
        
        if not position:
            print("❌ No JTOUSDT position found. Nothing to clean up.")
            return
        
        if not orders:
            print("✅ No orders found. Already clean.")
            return
        
        # Analyze current state
        classified = self.print_order_analysis(orders, position)
        
        # Ask for confirmation
        print("\n" + "="*60)
        print("🚨 CLEANUP PLAN:")
        print(f"   • Cancel {len(classified['conservative'])} Conservative orders")
        print(f"   • Keep {len(classified['fast'])} Fast orders")
        print("="*60)
        
        print("\n⚡ AUTO-PROCEEDING with cleanup...")
        # Auto-proceed since we're in automation mode
        
        # Cancel Conservative orders
        await self.cancel_conservative_orders(orders)
        
        # Wait and verify
        print("\n⏱️ Waiting for orders to be canceled...")
        await asyncio.sleep(3)
        
        # Get updated state
        updated_orders = await self.get_all_orders()
        updated_classified = self.classify_orders(updated_orders)
        
        print("\n" + "="*60)
        print("✅ CLEANUP COMPLETED")
        print("="*60)
        print(f"Remaining orders:")
        print(f"   Fast: {len(updated_classified['fast'])}")
        print(f"   Conservative: {len(updated_classified['conservative'])}")
        print(f"   Other: {len(updated_classified['other'])}")
        
        if len(updated_classified['conservative']) == 0:
            print("\n🎉 SUCCESS: All Conservative orders removed!")
        else:
            print(f"\n⚠️ {len(updated_classified['conservative'])} Conservative orders still remain")

async def main():
    """Main execution function"""
    cleanup = ManualCleanup()
    await cleanup.run_cleanup()

if __name__ == "__main__":
    asyncio.run(main())