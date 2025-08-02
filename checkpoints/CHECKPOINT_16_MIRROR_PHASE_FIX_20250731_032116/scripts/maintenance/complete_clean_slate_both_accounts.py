#!/usr/bin/env python3
"""
Complete Clean Slate - Close All Positions and Orders
Closes everything on both main and mirror accounts for a fresh start
"""
import asyncio
import logging
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client
from clients.bybit_helpers import (
    get_all_positions, get_open_orders, cancel_order_with_retry,
    place_order_with_retry, get_current_price
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CompleteCleanSlate:
    def __init__(self):
        self.main_client = bybit_client
        self.mirror_client = None
        self._init_mirror_client()
        
    def _init_mirror_client(self):
        """Initialize mirror client if available"""
        try:
            # Check if mirror trading is enabled via environment
            import os
            if os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true':
                from clients.bybit_client import bybit_client_2
                self.mirror_client = bybit_client_2
                if self.mirror_client:
                    logger.info("✅ Mirror client initialized")
                else:
                    logger.info("ℹ️ Mirror client not available")
            else:
                logger.info("ℹ️ Mirror trading not enabled")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize mirror client: {e}")
    
    async def close_all_positions_account(self, client, account_name: str):
        """Close all positions for a specific account"""
        logger.info(f"🔄 Closing all positions for {account_name} account...")
        
        try:
            # Get all positions (bybit_helpers doesn't use client parameter)
            if account_name == "MIRROR" and client != self.main_client:
                # For mirror account, we need to use mirror-specific function
                from execution.mirror_trader import get_mirror_positions
                positions = await get_mirror_positions()
            else:
                positions = await get_all_positions()
            active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
            
            logger.info(f"📊 Found {len(active_positions)} active positions in {account_name}")
            
            if not active_positions:
                logger.info(f"✅ No active positions in {account_name} account")
                return True
            
            # Close each position
            for position in active_positions:
                try:
                    symbol = position['symbol']
                    size = abs(float(position['size']))
                    side = position['side']
                    position_idx = position.get('positionIdx', 0)
                    
                    logger.info(f"🔄 {account_name}: Closing {symbol} {side} position (size: {size})")
                    
                    # Determine close side (opposite of position side)
                    close_side = "Buy" if side == "Sell" else "Sell"
                    
                    # Place market order to close position
                    if account_name == "MIRROR" and client != self.main_client:
                        # Use mirror trading function
                        from execution.mirror_trader import mirror_market_order
                        close_result = await mirror_market_order(
                            symbol=symbol,
                            side=close_side,
                            qty=str(size),
                            reduce_only=True,
                            position_idx=position_idx
                        )
                    else:
                        close_result = await place_order_with_retry(
                            symbol=symbol,
                            side=close_side,
                            order_type="Market",
                            qty=str(size),
                            reduce_only=True,
                            position_idx=position_idx
                        )
                    
                    if close_result and close_result.get("orderId"):
                        logger.info(f"✅ {account_name}: Closed {symbol} position")
                    else:
                        logger.error(f"❌ {account_name}: Failed to close {symbol} position")
                        
                except Exception as e:
                    logger.error(f"❌ {account_name}: Error closing position {position.get('symbol', 'unknown')}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error getting positions for {account_name}: {e}")
            return False
            
        return True
    
    async def cancel_all_orders_account(self, client, account_name: str):
        """Cancel all orders for a specific account"""
        logger.info(f"🔄 Cancelling all orders for {account_name} account...")
        
        try:
            # Get all open orders (bybit_helpers doesn't use client parameter)
            if account_name == "MIRROR" and client != self.main_client:
                # For mirror account, we need to use mirror-specific function
                from execution.mirror_trader import get_mirror_orders
                orders = await get_mirror_orders()
            else:
                orders = await get_open_orders()
            
            logger.info(f"📋 Found {len(orders)} open orders in {account_name}")
            
            if not orders:
                logger.info(f"✅ No open orders in {account_name} account")
                return True
            
            # Cancel each order
            for order in orders:
                try:
                    symbol = order['symbol']
                    order_id = order['orderId']
                    order_type = order.get('orderType', 'Unknown')
                    
                    logger.info(f"🔄 {account_name}: Cancelling {symbol} {order_type} order ({order_id[:8]}...)")
                    
                    if account_name == "MIRROR" and client != self.main_client:
                        # Use mirror trading function
                        from execution.mirror_trader import cancel_mirror_order
                        cancel_result = await cancel_mirror_order(
                            symbol=symbol,
                            order_id=order_id
                        )
                    else:
                        cancel_result = await cancel_order_with_retry(
                            symbol=symbol,
                            order_id=order_id
                        )
                    
                    if cancel_result:
                        logger.info(f"✅ {account_name}: Cancelled {symbol} order")
                    else:
                        logger.error(f"❌ {account_name}: Failed to cancel {symbol} order")
                        
                except Exception as e:
                    logger.error(f"❌ {account_name}: Error cancelling order {order.get('orderId', 'unknown')}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error getting orders for {account_name}: {e}")
            return False
            
        return True
    
    async def verify_clean_slate_account(self, client, account_name: str):
        """Verify account is completely clean"""
        logger.info(f"🔍 Verifying clean slate for {account_name} account...")
        
        try:
            # Check positions
            if account_name == "MIRROR" and client != self.main_client:
                from execution.mirror_trader import get_mirror_positions, get_mirror_orders
                positions = await get_mirror_positions()
                orders = await get_mirror_orders()
            else:
                positions = await get_all_positions()
                orders = await get_open_orders()
                
            active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
            
            if active_positions:
                logger.warning(f"⚠️ {account_name}: Still has {len(active_positions)} active positions")
                for pos in active_positions:
                    logger.warning(f"   - {pos['symbol']} {pos['side']}: {pos['size']}")
                return False
                
            if orders:
                logger.warning(f"⚠️ {account_name}: Still has {len(orders)} open orders")
                for order in orders:
                    logger.warning(f"   - {order['symbol']} {order.get('orderType', 'Unknown')}: {order['orderId'][:8]}...")
                return False
                
            logger.info(f"✅ {account_name}: Complete clean slate verified")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error verifying {account_name}: {e}")
            return False
    
    async def complete_clean_slate(self):
        """Execute complete clean slate on both accounts"""
        logger.info("🚀 STARTING COMPLETE CLEAN SLATE")
        logger.info("=" * 60)
        logger.info("This will close ALL positions and cancel ALL orders")
        logger.info("on BOTH main and mirror accounts")
        logger.info("=" * 60)
        
        success = True
        
        # Process main account
        logger.info("🎯 PROCESSING MAIN ACCOUNT")
        logger.info("-" * 40)
        
        # Cancel orders first, then close positions
        main_orders_cancelled = await self.cancel_all_orders_account(self.main_client, "MAIN")
        main_positions_closed = await self.close_all_positions_account(self.main_client, "MAIN")
        
        if not (main_orders_cancelled and main_positions_closed):
            success = False
            
        # Process mirror account if available
        if self.mirror_client:
            logger.info("\n🪞 PROCESSING MIRROR ACCOUNT")
            logger.info("-" * 40)
            
            mirror_orders_cancelled = await self.cancel_all_orders_account(self.mirror_client, "MIRROR")
            mirror_positions_closed = await self.close_all_positions_account(self.mirror_client, "MIRROR")
            
            if not (mirror_orders_cancelled and mirror_positions_closed):
                success = False
        
        # Wait a moment for everything to settle
        logger.info("\n⏳ Waiting 3 seconds for settlement...")
        await asyncio.sleep(3)
        
        # Verify clean slate
        logger.info("\n🔍 VERIFICATION PHASE")
        logger.info("-" * 40)
        
        main_clean = await self.verify_clean_slate_account(self.main_client, "MAIN")
        mirror_clean = True
        
        if self.mirror_client:
            mirror_clean = await self.verify_clean_slate_account(self.mirror_client, "MIRROR")
        
        # Final results
        logger.info("\n" + "=" * 60)
        if success and main_clean and mirror_clean:
            logger.info("🎉 COMPLETE CLEAN SLATE SUCCESS!")
            logger.info("✅ Main account: Clean")
            logger.info("✅ Mirror account: Clean" if self.mirror_client else "ℹ️ Mirror account: Not configured")
            logger.info("🆕 Both accounts ready for fresh trading")
        else:
            logger.error("❌ CLEAN SLATE INCOMPLETE")
            logger.error("❌ Some positions or orders may still remain")
            logger.error("❌ Manual verification recommended")
        
        logger.info("=" * 60)
        return success and main_clean and mirror_clean

async def main():
    """Main execution function"""
    try:
        cleaner = CompleteCleanSlate()
        success = await cleaner.complete_clean_slate()
        
        if success:
            print("\n🎊 Complete clean slate achieved!")
            print("Both accounts are now ready for fresh trading.")
        else:
            print("\n❌ Clean slate failed. Check logs above.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fatal error during clean slate: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    print("🧹 COMPLETE CLEAN SLATE - BOTH ACCOUNTS")
    print("=" * 50)
    print("This will close ALL positions and orders on both accounts.")
    print("Proceeding automatically...")
    print("")
    
    asyncio.run(main())