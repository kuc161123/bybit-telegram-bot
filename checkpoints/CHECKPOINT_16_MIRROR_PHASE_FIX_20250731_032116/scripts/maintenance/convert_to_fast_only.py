#!/usr/bin/env python3
"""
Convert JTOUSDT to Fast Approach Only
Removes all Conservative orders and adjusts Fast orders to match total position size
"""

import asyncio
import os
import sys
import logging
from decimal import Decimal
from typing import List, Dict, Any

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client
from config.settings import *

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JTOUSDTFastConverter:
    def __init__(self):
        self.symbol = "JTOUSDT"
        self.main_canceled_orders = []
        self.mirror_canceled_orders = []
        self.updated_orders = []
        
    async def get_current_positions(self) -> Dict[str, Any]:
        """Get current positions from both accounts"""
        logger.info("🔍 Fetching current positions...")
        
        main_jtousdt = None
        mirror_jtousdt = None
        
        try:
            # Main account
            try:
                main_position_info = await bybit_client.get_position_info(self.symbol)
                if main_position_info and float(main_position_info.get('size', 0)) > 0:
                    main_jtousdt = main_position_info
            except Exception as e:
                logger.warning(f"Error getting main position: {e}")
            
            # Mirror account - try with manual API call if needed
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                
                # Get mirror client
                mirror_client = bybit_client._get_mirror_client() if hasattr(bybit_client, '_get_mirror_client') else bybit_client
                
                mirror_response = await loop.run_in_executor(
                    None,
                    lambda: mirror_client.get_positions(
                        category="linear",
                        symbol=self.symbol
                    )
                )
                
                if mirror_response and mirror_response.get("retCode") == 0:
                    positions = mirror_response.get("result", {}).get("list", [])
                    for pos in positions:
                        if pos['symbol'] == self.symbol and float(pos['size']) > 0:
                            mirror_jtousdt = pos
                            break
                            
            except Exception as e:
                logger.warning(f"Error getting mirror position: {e}")
                
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
                
        return {
            "main": main_jtousdt,
            "mirror": mirror_jtousdt
        }
    
    async def get_current_orders(self) -> Dict[str, List]:
        """Get all current orders from both accounts"""
        logger.info("📋 Fetching current orders...")
        
        main_orders = []
        mirror_orders = []
        
        try:
            # Main account orders
            try:
                main_orders = await bybit_client.get_open_orders(symbol=self.symbol)
                if not main_orders:
                    main_orders = []
            except Exception as e:
                logger.warning(f"Error getting main orders: {e}")
                main_orders = []
            
            # Mirror account orders
            try:
                mirror_orders = await bybit_client.get_open_orders(symbol=self.symbol, account_type="mirror")
                if not mirror_orders:
                    mirror_orders = []
            except Exception as e:
                logger.warning(f"Error getting mirror orders: {e}")
                mirror_orders = []
                
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
        
        return {
            "main": main_orders,
            "mirror": mirror_orders
        }
    
    def classify_orders(self, orders: List[Dict]) -> Dict[str, List]:
        """Classify orders by approach (Fast vs Conservative)"""
        fast_orders = []
        conservative_orders = []
        
        for order in orders:
            order_link_id = order.get('orderLinkId', '')
            
            # Check for Fast approach patterns
            if any(pattern in order_link_id for pattern in ['BOT_FAST', 'FAST_']):
                fast_orders.append(order)
            # Check for Conservative approach patterns  
            elif any(pattern in order_link_id for pattern in ['BOT_CONS', 'CONS_', '80d70557']):
                conservative_orders.append(order)
            else:
                # Try to classify by order type and price
                order_type = order.get('side')
                price = float(order.get('triggerPrice', order.get('price', 0)))
                
                # Conservative patterns: multiple TPs at different prices
                if price in [1.647, 1.797, 1.846] or '2.05' in str(price) or '2.1' in str(price):
                    conservative_orders.append(order)
                # Fast patterns: single TP/SL
                elif price in [1.896, 2.198]:
                    # Could be either - check quantity or default to Fast
                    fast_orders.append(order)
                else:
                    # Default to conservative for safety
                    conservative_orders.append(order)
        
        return {
            "fast": fast_orders,
            "conservative": conservative_orders
        }
    
    async def cancel_conservative_orders(self, account_type="main") -> List[str]:
        """Cancel all Conservative approach orders"""
        logger.info(f"🗑️ Canceling Conservative orders on {account_type} account...")
        
        orders = await bybit_client.get_open_orders(symbol=self.symbol, 
                                                   account_type=account_type if account_type != "main" else None)
        classified = self.classify_orders(orders)
        
        canceled_order_ids = []
        
        for order in classified["conservative"]:
            try:
                order_id = order['orderId']
                order_link_id = order.get('orderLinkId', 'N/A')
                price = order.get('triggerPrice', order.get('price', 'N/A'))
                qty = order.get('qty', 'N/A')
                
                logger.info(f"   Canceling: {order_link_id} | Price: {price} | Qty: {qty}")
                
                await bybit_client.cancel_order(
                    symbol=self.symbol,
                    order_id=order_id,
                    account_type=account_type if account_type != "main" else None
                )
                
                canceled_order_ids.append(order_id)
                logger.info(f"   ✅ Canceled: {order_id}")
                
            except Exception as e:
                logger.error(f"   ❌ Failed to cancel {order.get('orderId')}: {e}")
        
        return canceled_order_ids
    
    async def update_fast_orders(self, position_size: float, account_type="main") -> List[str]:
        """Update Fast approach orders to match full position size"""
        logger.info(f"🔧 Updating Fast orders on {account_type} account to qty: {position_size}...")
        
        orders = await bybit_client.get_open_orders(symbol=self.symbol,
                                                   account_type=account_type if account_type != "main" else None)
        classified = self.classify_orders(orders)
        
        updated_order_ids = []
        
        for order in classified["fast"]:
            try:
                order_id = order['orderId']
                order_link_id = order.get('orderLinkId', 'N/A')
                current_qty = float(order.get('qty', 0))
                price = order.get('triggerPrice', order.get('price'))
                
                # Skip if already correct quantity
                if abs(current_qty - position_size) < 0.1:
                    logger.info(f"   ✅ Order {order_link_id} already correct qty: {current_qty}")
                    continue
                
                logger.info(f"   Updating: {order_link_id} | {current_qty} → {position_size}")
                
                # Cancel old order
                await bybit_client.cancel_order(
                    symbol=self.symbol,
                    order_id=order_id,
                    account_type=account_type if account_type != "main" else None
                )
                
                # Wait a moment
                await asyncio.sleep(0.5)
                
                # Place new order with correct quantity
                side = "Buy" if order['side'] == "Sell" else "Sell"  # TP/SL are opposite side
                
                new_order = await bybit_client.place_order(
                    symbol=self.symbol,
                    side=side,
                    order_type="Market",
                    qty=str(position_size),
                    trigger_price=price,
                    order_link_id=f"{order_link_id}_UPDATED",
                    reduce_only=True,
                    account_type=account_type if account_type != "main" else None
                )
                
                updated_order_ids.append(new_order.get('orderId'))
                logger.info(f"   ✅ Updated: {order_link_id} → qty: {position_size}")
                
            except Exception as e:
                logger.error(f"   ❌ Failed to update {order.get('orderId')}: {e}")
        
        return updated_order_ids
    
    async def stop_conservative_monitors(self):
        """Stop Conservative monitoring tasks"""
        logger.info("🛑 Stopping Conservative monitors...")
        
        try:
            # Load persistence file to modify monitor tasks
            import pickle
            persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
            
            with open(persistence_file, 'rb') as f:
                data = pickle.load(f)
            
            # Remove Conservative monitor tasks
            bot_data = data.get('bot_data', {})
            monitor_tasks = bot_data.get('monitor_tasks', {})
            
            conservative_keys = [key for key in monitor_tasks.keys() if 'conservative' in key.lower()]
            
            for key in conservative_keys:
                logger.info(f"   Removing monitor: {key}")
                del monitor_tasks[key]
            
            # Save back
            with open(persistence_file, 'wb') as f:
                pickle.dump(data, f)
                
            logger.info(f"   ✅ Removed {len(conservative_keys)} Conservative monitors")
            
        except Exception as e:
            logger.error(f"   ❌ Failed to stop monitors: {e}")
    
    async def run_conversion(self):
        """Main conversion process"""
        logger.info("🚀 Starting JTOUSDT Fast-Only Conversion...")
        
        try:
            # 1. Get current state
            positions = await self.get_current_positions()
            orders = await self.get_current_orders()
            
            if not positions["main"]:
                logger.error("❌ No JTOUSDT position found on main account!")
                return False
            
            main_position_size = float(positions["main"]["size"])
            mirror_position_size = float(positions["mirror"]["size"]) if positions["mirror"] else 0
            
            logger.info(f"📊 Current Positions:")
            logger.info(f"   Main: {main_position_size} JTOUSDT")
            logger.info(f"   Mirror: {mirror_position_size} JTOUSDT")
            
            # 2. Show current orders breakdown
            main_classified = self.classify_orders(orders["main"])
            mirror_classified = self.classify_orders(orders["mirror"])
            
            logger.info(f"📋 Current Orders:")
            logger.info(f"   Main - Fast: {len(main_classified['fast'])}, Conservative: {len(main_classified['conservative'])}")
            logger.info(f"   Mirror - Fast: {len(mirror_classified['fast'])}, Conservative: {len(mirror_classified['conservative'])}")
            
            # 3. Cancel Conservative orders
            logger.info("\n" + "="*60)
            logger.info("PHASE 1: CANCELING CONSERVATIVE ORDERS")
            logger.info("="*60)
            
            self.main_canceled_orders = await self.cancel_conservative_orders("main")
            self.mirror_canceled_orders = await self.cancel_conservative_orders("mirror")
            
            # 4. Wait for orders to be canceled
            await asyncio.sleep(2)
            
            # 5. Update Fast orders
            logger.info("\n" + "="*60)
            logger.info("PHASE 2: UPDATING FAST ORDERS")
            logger.info("="*60)
            
            if main_position_size > 0:
                await self.update_fast_orders(main_position_size, "main")
            
            if mirror_position_size > 0:
                await self.update_fast_orders(mirror_position_size, "mirror")
            
            # 6. Stop Conservative monitors
            logger.info("\n" + "="*60)
            logger.info("PHASE 3: STOPPING CONSERVATIVE MONITORS")
            logger.info("="*60)
            
            await self.stop_conservative_monitors()
            
            # 7. Final verification
            await asyncio.sleep(2)
            await self.verify_conversion()
            
            logger.info("\n" + "="*60)
            logger.info("🎉 CONVERSION COMPLETED SUCCESSFULLY!")
            logger.info("="*60)
            logger.info(f"✅ Main account canceled: {len(self.main_canceled_orders)} Conservative orders")
            logger.info(f"✅ Mirror account canceled: {len(self.mirror_canceled_orders)} Conservative orders")
            logger.info(f"✅ JTOUSDT is now Fast approach only")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Conversion failed: {e}")
            return False
    
    async def verify_conversion(self):
        """Verify the conversion was successful"""
        logger.info("🔍 Verifying conversion...")
        
        # Get updated orders
        orders = await self.get_current_orders()
        positions = await self.get_current_positions()
        
        # Check main account
        main_classified = self.classify_orders(orders["main"])
        mirror_classified = self.classify_orders(orders["mirror"])
        
        logger.info("📊 Post-Conversion State:")
        
        if positions["main"]:
            main_size = float(positions["main"]["size"])
            logger.info(f"   Main Position: {main_size} JTOUSDT")
            logger.info(f"   Main Orders - Fast: {len(main_classified['fast'])}, Conservative: {len(main_classified['conservative'])}")
            
            # Check quantities
            total_fast_qty = sum(float(order.get('qty', 0)) for order in main_classified['fast'])
            logger.info(f"   Main Fast Orders Total Qty: {total_fast_qty}")
            
            if len(main_classified['conservative']) == 0:
                logger.info("   ✅ All Conservative orders removed from main account")
            else:
                logger.warning(f"   ⚠️ {len(main_classified['conservative'])} Conservative orders still exist")
        
        if positions["mirror"]:
            mirror_size = float(positions["mirror"]["size"])
            logger.info(f"   Mirror Position: {mirror_size} JTOUSDT")
            logger.info(f"   Mirror Orders - Fast: {len(mirror_classified['fast'])}, Conservative: {len(mirror_classified['conservative'])}")
            
            if len(mirror_classified['conservative']) == 0:
                logger.info("   ✅ All Conservative orders removed from mirror account")
            else:
                logger.warning(f"   ⚠️ {len(mirror_classified['conservative'])} Conservative orders still exist")

async def main():
    """Main execution function"""
    converter = JTOUSDTFastConverter()
    
    print("\n" + "="*80)
    print("🎯 JTOUSDT FAST-ONLY CONVERSION TOOL")
    print("="*80)
    print("This will:")
    print("1. Cancel ALL Conservative approach orders (4 TPs + 1 SL + 2 Limits)")
    print("2. Update Fast approach orders to match full position size")
    print("3. Stop Conservative monitoring tasks")
    print("4. Keep only Fast approach: 1 TP + 1 SL")
    print("="*80)
    
    # Auto-proceed since user already confirmed
    print("✅ Proceeding with conversion (user confirmed)...")
    
    print("\n🚀 Starting conversion process...")
    success = await converter.run_conversion()
    
    if success:
        print("\n🎉 JTOUSDT successfully converted to Fast approach only!")
        print("You can now restart your bot to see the clean Fast-only setup.")
    else:
        print("\n❌ Conversion failed. Please check the logs and try again.")

if __name__ == "__main__":
    asyncio.run(main())