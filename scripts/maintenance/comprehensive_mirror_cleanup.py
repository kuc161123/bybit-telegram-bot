#!/usr/bin/env python3
"""
Comprehensive Mirror Account Cleanup
Ensures mirror account is completely clean with aggressive cleanup
"""
import asyncio
import logging
import sys
import os
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComprehensiveMirrorCleanup:
    def __init__(self):
        self.mirror_client = None
        self._init_mirror_client()
        
    def _init_mirror_client(self):
        """Initialize mirror client"""
        try:
            # First check environment variable
            if os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() != 'true':
                logger.error("❌ Mirror trading is not enabled in environment!")
                logger.info("Set ENABLE_MIRROR_TRADING=true to enable")
                return
            
            # Check for API keys
            mirror_api_key = os.getenv('BYBIT_API_KEY_2')
            mirror_api_secret = os.getenv('BYBIT_API_SECRET_2')
            
            if not mirror_api_key or not mirror_api_secret:
                logger.error("❌ Mirror API keys not found!")
                logger.info("Set BYBIT_API_KEY_2 and BYBIT_API_SECRET_2")
                return
            
            # Create mirror client directly
            from pybit.unified_trading import HTTP
            
            self.mirror_client = HTTP(
                api_key=mirror_api_key,
                api_secret=mirror_api_secret,
                testnet=os.getenv('USE_TESTNET', 'false').lower() == 'true'
            )
            
            # Test connection
            test_result = self.mirror_client.get_server_time()
            if test_result.get('retCode') == 0:
                logger.info("✅ Mirror client initialized successfully")
            else:
                logger.error(f"❌ Mirror client test failed: {test_result}")
                self.mirror_client = None
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize mirror client: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def get_all_mirror_positions(self):
        """Get all positions from mirror account"""
        try:
            result = self.mirror_client.get_positions(
                category="linear",
                settleCoin="USDT",
                limit=200  # Get more positions
            )
            return result.get('result', {}).get('list', [])
        except Exception as e:
            logger.error(f"Error getting mirror positions: {e}")
            return []
    
    def get_all_mirror_orders(self):
        """Get all orders from mirror account"""
        try:
            result = self.mirror_client.get_open_orders(
                category="linear",
                settleCoin="USDT",
                limit=200  # Get more orders
            )
            return result.get('result', {}).get('list', [])
        except Exception as e:
            logger.error(f"Error getting mirror orders: {e}")
            return []
    
    def cancel_mirror_order(self, symbol, order_id):
        """Cancel a specific mirror order"""
        try:
            result = self.mirror_client.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=order_id
            )
            return result.get('retCode') == 0
        except Exception as e:
            logger.error(f"Error cancelling mirror order {order_id}: {e}")
            return False
    
    def close_mirror_position(self, symbol, side, size, position_idx=0):
        """Close a mirror position"""
        try:
            # Determine close side (opposite of position side)
            close_side = "Buy" if side == "Sell" else "Sell"
            
            result = self.mirror_client.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(size),
                reduceOnly=True,
                positionIdx=position_idx
            )
            return result.get('retCode') == 0
        except Exception as e:
            logger.error(f"Error closing mirror position {symbol}: {e}")
            return False
    
    def cancel_all_mirror_orders_batch(self):
        """Try batch cancellation of all mirror orders"""
        try:
            logger.info("🔄 Attempting batch order cancellation for mirror...")
            
            # Get all unique symbols first
            orders = self.get_all_mirror_orders()
            symbols = list(set([order['symbol'] for order in orders]))
            
            total_cancelled = 0
            
            # Try batch cancel per symbol
            for symbol in symbols:
                try:
                    result = self.mirror_client.cancel_all_orders(
                        category="linear",
                        symbol=symbol
                    )
                    if result.get('retCode') == 0:
                        cancelled = result.get('result', {}).get('list', [])
                        total_cancelled += len(cancelled)
                        logger.info(f"✅ Batch cancelled {len(cancelled)} {symbol} orders")
                except Exception as e:
                    logger.warning(f"⚠️ Batch cancel failed for {symbol}: {e}")
            
            logger.info(f"📊 Total batch cancelled: {total_cancelled} orders")
            return total_cancelled > 0
            
        except Exception as e:
            logger.warning(f"⚠️ Batch cancel not available: {e}")
            return False
    
    async def aggressive_mirror_cleanup(self):
        """Aggressively clean mirror account"""
        if not self.mirror_client:
            logger.error("❌ Mirror client not available!")
            return False
        
        logger.info("🚀 STARTING AGGRESSIVE MIRROR CLEANUP")
        logger.info("=" * 60)
        
        max_attempts = 5
        
        # Step 1: Cancel all orders (multiple attempts)
        logger.info("📋 Step 1: Cancelling all mirror orders...")
        
        # Try batch cancel first
        batch_success = self.cancel_all_mirror_orders_batch()
        
        # Then do individual cancellation
        for attempt in range(max_attempts):
            orders = self.get_all_mirror_orders()
            if not orders:
                logger.info("✅ No mirror orders remaining")
                break
                
            logger.info(f"Attempt {attempt + 1}/{max_attempts}: Found {len(orders)} orders")
            
            cancelled = 0
            for order in orders:
                symbol = order['symbol']
                order_id = order['orderId']
                order_type = order.get('orderType', 'Unknown')
                
                logger.info(f"🔄 Cancelling {symbol} {order_type} order ({order_id[:8]}...)")
                
                if self.cancel_mirror_order(symbol, order_id):
                    logger.info(f"✅ Cancelled {symbol} order")
                    cancelled += 1
                else:
                    logger.error(f"❌ Failed to cancel {symbol} order")
            
            logger.info(f"📊 Cancelled {cancelled}/{len(orders)} orders")
            
            if cancelled < len(orders) and attempt < max_attempts - 1:
                logger.info("⏳ Waiting 2 seconds before retry...")
                time.sleep(2)
        
        # Step 2: Close all positions (multiple attempts)
        logger.info("\n📊 Step 2: Closing all mirror positions...")
        
        for attempt in range(max_attempts):
            positions = self.get_all_mirror_positions()
            active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
            
            if not active_positions:
                logger.info("✅ No mirror positions remaining")
                break
                
            logger.info(f"Attempt {attempt + 1}/{max_attempts}: Found {len(active_positions)} positions")
            
            closed = 0
            for position in active_positions:
                symbol = position['symbol']
                size = abs(float(position['size']))
                side = position['side']
                position_idx = position.get('positionIdx', 0)
                pnl = position.get('unrealisedPnl', 0)
                
                logger.info(f"🔄 Closing {symbol} {side} position (size: {size}, PnL: {pnl})")
                
                if self.close_mirror_position(symbol, side, size, position_idx):
                    logger.info(f"✅ Closed {symbol} position")
                    closed += 1
                else:
                    logger.error(f"❌ Failed to close {symbol} position")
            
            logger.info(f"📊 Closed {closed}/{len(active_positions)} positions")
            
            if closed < len(active_positions) and attempt < max_attempts - 1:
                logger.info("⏳ Waiting 2 seconds before retry...")
                time.sleep(2)
        
        # Step 3: Final verification
        logger.info("\n🔍 Step 3: Final verification...")
        await asyncio.sleep(3)
        
        final_positions = self.get_all_mirror_positions()
        final_orders = self.get_all_mirror_orders()
        
        active_final = [p for p in final_positions if float(p.get('size', 0)) != 0]
        
        # Results
        logger.info("\n" + "=" * 60)
        if not active_final and not final_orders:
            logger.info("🎉 MIRROR ACCOUNT COMPLETELY CLEAN!")
            logger.info("✅ All positions closed")
            logger.info("✅ All orders cancelled")
            logger.info("🆕 Mirror account ready for fresh trading")
            return True
        else:
            logger.warning("⚠️ MIRROR CLEANUP INCOMPLETE")
            if active_final:
                logger.warning(f"⚠️ Still has {len(active_final)} active positions:")
                for pos in active_final:
                    logger.warning(f"   - {pos['symbol']} {pos['side']}: {pos['size']}")
            if final_orders:
                logger.warning(f"⚠️ Still has {len(final_orders)} open orders:")
                for order in final_orders:
                    logger.warning(f"   - {order['symbol']} {order.get('orderType')}: {order['orderId'][:8]}...")
            return False

async def main():
    """Main execution function"""
    try:
        cleaner = ComprehensiveMirrorCleanup()
        
        if not cleaner.mirror_client:
            logger.error("❌ Cannot proceed - mirror client not available")
            logger.info("Please check:")
            logger.info("1. ENABLE_MIRROR_TRADING=true")
            logger.info("2. BYBIT_API_KEY_2 is set")
            logger.info("3. BYBIT_API_SECRET_2 is set")
            return False
        
        success = await cleaner.aggressive_mirror_cleanup()
        
        if success:
            print("\n🎊 Mirror account cleanup successful!")
            print("Mirror account is now completely clean.")
        else:
            print("\n❌ Mirror account cleanup incomplete.")
            print("Some manual cleanup may be required.")
            
        return success
        
    except Exception as e:
        logger.error(f"❌ Fatal error during mirror cleanup: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    print("🪞 COMPREHENSIVE MIRROR ACCOUNT CLEANUP")
    print("=" * 50)
    print("This will aggressively close ALL positions and orders")
    print("on the MIRROR account only.")
    print("Proceeding automatically...")
    print("")
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)