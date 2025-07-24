#!/usr/bin/env python3
"""
Verify Clean Accounts - Check that both accounts are completely clean
"""
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_account(client, account_name):
    """Verify an account is completely clean"""
    try:
        logger.info(f"🔍 Verifying {account_name} account...")
        
        # Check positions
        pos_result = client.get_positions(category="linear", settleCoin="USDT")
        positions = pos_result.get('result', {}).get('list', [])
        active_positions = [p for p in positions if float(p.get('size', 0)) != 0]
        
        # Check orders
        ord_result = client.get_open_orders(category="linear", settleCoin="USDT")
        orders = ord_result.get('result', {}).get('list', [])
        
        logger.info(f"📊 {account_name} Account Status:")
        logger.info(f"   Active positions: {len(active_positions)}")
        logger.info(f"   Open orders: {len(orders)}")
        
        if active_positions:
            logger.warning(f"⚠️ {account_name}: Active positions found:")
            for pos in active_positions:
                logger.warning(f"   - {pos['symbol']} {pos['side']}: {pos['size']}")
                
        if orders:
            logger.warning(f"⚠️ {account_name}: Open orders found:")
            for order in orders:
                logger.warning(f"   - {order['symbol']} {order.get('orderType', 'Unknown')}")
        
        is_clean = len(active_positions) == 0 and len(orders) == 0
        
        if is_clean:
            logger.info(f"✅ {account_name}: COMPLETELY CLEAN")
        else:
            logger.warning(f"⚠️ {account_name}: NOT CLEAN")
            
        return is_clean, len(active_positions), len(orders)
        
    except Exception as e:
        logger.error(f"❌ Error verifying {account_name}: {e}")
        return False, -1, -1

def main():
    """Main verification function"""
    logger.info("🔍 VERIFYING CLEAN ACCOUNTS")
    logger.info("=" * 50)
    
    # Verify main account
    main_clean, main_positions, main_orders = verify_account(bybit_client, "MAIN")
    
    # Try to verify mirror account
    mirror_clean = True
    mirror_positions = 0
    mirror_orders = 0
    
    try:
        import os
        if os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true':
            from clients.bybit_client import bybit_client_2
            if bybit_client_2:
                mirror_clean, mirror_positions, mirror_orders = verify_account(bybit_client_2, "MIRROR")
            else:
                logger.info("ℹ️ Mirror client not available")
        else:
            logger.info("ℹ️ Mirror trading not enabled")
    except Exception as e:
        logger.info(f"ℹ️ Mirror account not available: {e}")
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("🎯 VERIFICATION SUMMARY")
    logger.info("=" * 50)
    
    logger.info(f"MAIN Account:")
    logger.info(f"  ✅ Clean: {main_clean}")
    logger.info(f"  📊 Positions: {main_positions}")
    logger.info(f"  📋 Orders: {main_orders}")
    
    if mirror_clean and mirror_positions >= 0:
        logger.info(f"MIRROR Account:")
        logger.info(f"  ✅ Clean: {mirror_clean}")
        logger.info(f"  📊 Positions: {mirror_positions}")
        logger.info(f"  📋 Orders: {mirror_orders}")
    
    overall_clean = main_clean and mirror_clean
    
    if overall_clean:
        logger.info("\n🎉 ALL ACCOUNTS COMPLETELY CLEAN!")
        logger.info("✅ Ready for fresh trading")
    else:
        logger.warning("\n⚠️ SOME ACCOUNTS NOT CLEAN")
        logger.warning("❌ Manual cleanup may be needed")
    
    logger.info("=" * 50)
    return overall_clean

if __name__ == "__main__":
    print("🔍 ACCOUNT VERIFICATION")
    print("=" * 30)
    
    success = main()
    if success:
        print("\n✅ Verification complete - All accounts clean!")
    else:
        print("\n❌ Verification shows remaining items.")