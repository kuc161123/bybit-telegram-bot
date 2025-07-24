#!/usr/bin/env python3
"""
Test the Robust Persistence Manager system
"""
import asyncio
import logging
from datetime import datetime
from utils.robust_persistence import robust_persistence, add_trade_monitor, remove_trade_monitor, sync_monitors_with_positions

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_persistence_manager():
    """Test all robust persistence features"""
    try:
        logger.info("🚀 Testing Robust Persistence Manager...")
        
        # 1. Test adding a monitor
        logger.info("\n1. Testing monitor addition...")
        monitor_data = {
            'symbol': 'BTCUSDT',
            'side': 'Buy',
            'chat_id': 123456,
            'approach': 'conservative',
            'account_type': 'main',
            'entry_price': 45000.0,
            'stop_loss': 44000.0,
            'take_profits': [
                {'price': 46000.0, 'size': 0.85},
                {'price': 47000.0, 'size': 0.05},
                {'price': 48000.0, 'size': 0.05},
                {'price': 49000.0, 'size': 0.05}
            ],
            'created_at': datetime.now().timestamp()
        }
        
        position_data = {
            'symbol': 'BTCUSDT',
            'side': 'Buy',
            'size': 1.0,
            'avgPrice': 45000.0
        }
        
        await add_trade_monitor('BTCUSDT', 'Buy', monitor_data, position_data)
        logger.info("✅ Monitor added successfully")
        
        # 2. Test getting all monitors
        logger.info("\n2. Testing monitor retrieval...")
        monitors = await robust_persistence.get_all_monitors()
        logger.info(f"✅ Retrieved {len(monitors)} monitors")
        for key, monitor in monitors.items():
            logger.info(f"  - {key}: {monitor.get('symbol')} {monitor.get('side')}")
        
        # 3. Test updating a monitor
        logger.info("\n3. Testing monitor update...")
        await robust_persistence.update_monitor('BTCUSDT_Buy', {
            'stop_loss': 44500.0,
            'status': 'breakeven_moved'
        })
        logger.info("✅ Monitor updated successfully")
        
        # 4. Test syncing with positions
        logger.info("\n4. Testing position sync...")
        test_positions = [
            {'symbol': 'BTCUSDT', 'side': 'Buy', 'size': 1.0},
            {'symbol': 'ETHUSDT', 'side': 'Sell', 'size': 10.0}
        ]
        await sync_monitors_with_positions(test_positions)
        logger.info("✅ Synced monitors with positions")
        
        # 5. Test statistics
        logger.info("\n5. Testing persistence statistics...")
        stats = await robust_persistence.get_stats()
        logger.info(f"✅ Persistence stats:")
        logger.info(f"  - File size: {stats.get('file_size_mb', 0):.2f} MB")
        logger.info(f"  - Total monitors: {stats.get('total_monitors', 0)}")
        logger.info(f"  - Dashboard monitors: {stats.get('total_dashboard_monitors', 0)}")
        logger.info(f"  - Registry size: {stats.get('registry_size', 0)}")
        logger.info(f"  - Backup count: {stats.get('backup_count', 0)}")
        
        # 6. Test transaction rollback
        logger.info("\n6. Testing transaction rollback...")
        txn_id = await robust_persistence.begin_transaction()
        
        try:
            # Make a change within transaction
            data = await robust_persistence.read_data()
            if 'bot_data' in data and 'enhanced_tp_sl_monitors' in data['bot_data']:
                if 'BTCUSDT_Buy' in data['bot_data']['enhanced_tp_sl_monitors']:
                    data['bot_data']['enhanced_tp_sl_monitors']['BTCUSDT_Buy']['test_field'] = 'this_should_be_rolled_back'
            
            await robust_persistence.write_data(data, txn_id)
            
            # Rollback
            await robust_persistence.rollback_transaction(txn_id)
            logger.info("✅ Transaction rolled back")
            
            # Verify rollback
            monitors = await robust_persistence.get_all_monitors()
            if 'test_field' not in monitors.get('BTCUSDT_Buy', {}):
                logger.info("✅ Rollback verified - test field not present")
            else:
                logger.error("❌ Rollback failed - test field still present")
        except Exception as e:
            await robust_persistence.rollback_transaction(txn_id)
            raise
        
        # 7. Test removing a monitor
        logger.info("\n7. Testing monitor removal...")
        await remove_trade_monitor('BTCUSDT', 'Buy', reason='test_completed')
        logger.info("✅ Monitor removed successfully")
        
        # Final verification
        final_monitors = await robust_persistence.get_all_monitors()
        logger.info(f"\n✅ Test completed. Final monitor count: {len(final_monitors)}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def main():
    """Main test function"""
    await test_persistence_manager()

if __name__ == "__main__":
    asyncio.run(main())