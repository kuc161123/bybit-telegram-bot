#!/usr/bin/env python3
"""
Force Clean Slate - Aggressively close all positions and orders
Uses multiple attempts to ensure complete cleanup
"""
import asyncio
import logging
import sys
import os
import time
from decimal import Decimal

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ForceCleanSlate:
    def __init__(self):
        self.main_client = bybit_client
        self.mirror_client = None
        self._init_mirror_client()
        
    def _init_mirror_client(self):
        """Initialize mirror client if available"""
        try:
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
    
    def force_cancel_orders(self, client, max_attempts=3):
        """Force cancel all orders with multiple attempts"""
        logger.info("🔄 Force cancelling all orders...")
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_attempts}")
                
                # Get current orders
                result = client.get_open_orders(category="linear", settleCoin="USDT")
                orders = result.get('result', {}).get('list', [])
                
                if not orders:
                    logger.info("✅ No orders remaining")
                    return True
                
                logger.info(f"📋 Found {len(orders)} orders to cancel")
                
                # Try to cancel each order
                cancelled = 0
                for order in orders:
                    try:
                        symbol = order['symbol']
                        order_id = order['orderId']
                        
                        cancel_result = client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        )
                        
                        if cancel_result.get('retCode') == 0:
                            logger.info(f"✅ Cancelled {symbol} order")
                            cancelled += 1
                        else:
                            logger.warning(f"⚠️ Cancel failed for {symbol}: {cancel_result.get('retMsg', 'Unknown error')}")
                            
                    except Exception as e:
                        logger.error(f"❌ Error cancelling {order.get('symbol', 'unknown')} order: {e}")
                
                logger.info(f"📊 Cancelled {cancelled}/{len(orders)} orders")
                
                # Short wait between attempts
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"❌ Error in cancel attempt {attempt + 1}: {e}")
        
        return False
    
    def force_close_positions(self, client, max_attempts=3):
        """Force close all positions with multiple attempts"""
        logger.info("🔄 Force closing all positions...")
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_attempts}")
                
                # Get current positions
                result = client.get_positions(category="linear", settleCoin="USDT")
                positions = result.get('result', {}).get('list', [])
                active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
                
                if not active_positions:
                    logger.info("✅ No positions remaining")
                    return True
                
                logger.info(f"📊 Found {len(active_positions)} positions to close")
                
                # Try to close each position
                closed = 0
                for position in active_positions:
                    try:
                        symbol = position['symbol']
                        size = abs(float(position['size']))
                        side = position['side']
                        position_idx = position.get('positionIdx', 0)
                        
                        # Determine close side (opposite of position side)
                        close_side = "Buy" if side == "Sell" else "Sell"
                        
                        close_result = client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=close_side,
                            orderType="Market",
                            qty=str(size),
                            reduceOnly=True,
                            positionIdx=position_idx
                        )
                        
                        if close_result.get('retCode') == 0:
                            logger.info(f"✅ Closed {symbol} {side} position")
                            closed += 1
                        else:
                            logger.warning(f"⚠️ Close failed for {symbol}: {close_result.get('retMsg', 'Unknown error')}")
                            
                    except Exception as e:
                        logger.error(f"❌ Error closing {position.get('symbol', 'unknown')} position: {e}")
                
                logger.info(f"📊 Closed {closed}/{len(active_positions)} positions")
                
                # Short wait between attempts
                if attempt < max_attempts - 1:
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"❌ Error in close attempt {attempt + 1}: {e}")
        
        return False
    
    def cancel_all_orders_batch(self, client):
        """Cancel all orders using batch API if available"""
        try:
            logger.info("🔄 Attempting batch order cancellation...")
            
            # Try to cancel all orders at once
            result = client.cancel_all_orders(category="linear")
            
            if result.get('retCode') == 0:
                cancelled_list = result.get('result', {}).get('list', [])
                logger.info(f"✅ Batch cancelled {len(cancelled_list)} orders")
                return True
            else:
                logger.warning(f"⚠️ Batch cancel failed: {result.get('retMsg', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Batch cancel not available or failed: {e}")
            return False
    
    def verify_clean_account(self, client, account_name):
        """Verify account is completely clean"""
        try:
            # Check positions
            pos_result = client.get_positions(category="linear", settleCoin="USDT")
            positions = pos_result.get('result', {}).get('list', [])
            active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
            
            # Check orders
            ord_result = client.get_open_orders(category="linear", settleCoin="USDT")
            orders = ord_result.get('result', {}).get('list', [])
            
            logger.info(f"🔍 {account_name} verification:")
            logger.info(f"   Active positions: {len(active_positions)}")
            logger.info(f"   Open orders: {len(orders)}")
            
            if active_positions:
                logger.warning(f"⚠️ {account_name}: Still has {len(active_positions)} positions:")
                for pos in active_positions[:5]:  # Show first 5
                    logger.warning(f"   - {pos['symbol']} {pos['side']}: {pos['size']}")
                    
            if orders:
                logger.warning(f"⚠️ {account_name}: Still has {len(orders)} orders:")
                for order in orders[:5]:  # Show first 5
                    logger.warning(f"   - {order['symbol']} {order.get('orderType', 'Unknown')}: {order['orderId'][:8]}...")
            
            return len(active_positions) == 0 and len(orders) == 0
            
        except Exception as e:
            logger.error(f"❌ Error verifying {account_name}: {e}")
            return False
    
    async def force_clean_account(self, client, account_name):
        """Force clean a specific account"""
        logger.info(f"🚀 FORCE CLEANING {account_name.upper()} ACCOUNT")
        logger.info("-" * 50)
        
        success = True
        
        # Step 1: Try batch cancel first
        batch_success = self.cancel_all_orders_batch(client)
        if not batch_success:
            # Fall back to individual cancellation
            cancel_success = self.force_cancel_orders(client, max_attempts=5)
            if not cancel_success:
                success = False
        
        # Step 2: Force close positions
        close_success = self.force_close_positions(client, max_attempts=5)
        if not close_success:
            success = False
        
        # Step 3: Final verification
        await asyncio.sleep(3)  # Wait for settlement
        clean = self.verify_clean_account(client, account_name)
        
        if clean:
            logger.info(f"✅ {account_name} account: COMPLETELY CLEAN")
        else:
            logger.warning(f"⚠️ {account_name} account: May still have remaining items")
            success = False
        
        return clean
    
    async def execute_force_clean(self):
        """Execute force clean on all accounts"""
        logger.info("🚀 STARTING FORCE CLEAN SLATE")
        logger.info("=" * 60)
        logger.info("This will AGGRESSIVELY close ALL positions and orders")
        logger.info("Using multiple attempts and batch operations")
        logger.info("=" * 60)
        
        # Clean main account
        main_clean = await self.force_clean_account(self.main_client, "MAIN")
        
        # Clean mirror account if available
        mirror_clean = True
        if self.mirror_client:
            mirror_clean = await self.force_clean_account(self.mirror_client, "MIRROR")
        
        # Final results
        logger.info("\n" + "=" * 60)
        if main_clean and mirror_clean:
            logger.info("🎉 FORCE CLEAN SLATE COMPLETE!")
            logger.info("✅ Main account: CLEAN")
            if self.mirror_client:
                logger.info("✅ Mirror account: CLEAN")
            else:
                logger.info("ℹ️ Mirror account: Not configured")
            logger.info("🆕 All accounts ready for fresh trading")
        else:
            logger.error("❌ FORCE CLEAN INCOMPLETE")
            logger.error("❌ Some positions or orders may remain")
            logger.error("❌ Manual intervention may be required")
        
        logger.info("=" * 60)
        return main_clean and mirror_clean

async def main():
    """Main execution function"""
    try:
        cleaner = ForceCleanSlate()
        success = await cleaner.execute_force_clean()
        
        if success:
            print("\n🎊 Force clean slate successful!")
            print("All accounts are now completely clean.")
        else:
            print("\n❌ Force clean slate incomplete.")
            print("Some manual cleanup may be required.")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fatal error during force clean: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    print("🔥 FORCE CLEAN SLATE - AGGRESSIVE CLEANUP")
    print("=" * 50)
    print("This will AGGRESSIVELY close ALL positions and orders.")
    print("Multiple attempts will be made to ensure complete cleanup.")
    print("Proceeding automatically...")
    print("")
    
    asyncio.run(main())