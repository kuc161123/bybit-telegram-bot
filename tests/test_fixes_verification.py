#!/usr/bin/env python3
"""
Test script to verify all fixes are working correctly
"""
import asyncio
import logging
import pickle
from decimal import Decimal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_enhanced_tp_sl_alerts():
    """Test that enhanced TP/SL alerts work with proper chat_id"""
    try:
        # Load pickle to check chat_ids
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        monitor_tasks = bot_data.get('monitor_tasks', {})
        
        logger.info("=== ENHANCED TP/SL MONITORS ===")
        none_chat_count = 0
        for key, monitor in enhanced_monitors.items():
            chat_id = monitor.get('chat_id')
            symbol = monitor.get('symbol')
            side = monitor.get('side')
            
            if chat_id is None:
                logger.error(f"❌ Monitor {key} still has None chat_id")
                none_chat_count += 1
            else:
                logger.info(f"✅ Monitor {key}: chat_id={chat_id}, {symbol} {side}")
        
        logger.info(f"\nEnhanced monitors with None chat_id: {none_chat_count}/{len(enhanced_monitors)}")
        
        logger.info("\n=== MONITOR TASKS ===")
        none_prefix_count = 0
        none_value_count = 0
        
        for key, task in monitor_tasks.items():
            if key.startswith('None_'):
                logger.error(f"❌ Monitor task still has None_ prefix: {key}")
                none_prefix_count += 1
            
            if task.get('chat_id') is None:
                logger.error(f"❌ Monitor task {key} has None chat_id value")
                none_value_count += 1
            else:
                logger.info(f"✅ Monitor task {key}: chat_id={task.get('chat_id')}")
        
        logger.info(f"\nMonitor tasks with None_ prefix: {none_prefix_count}/{len(monitor_tasks)}")
        logger.info(f"Monitor tasks with None chat_id: {none_value_count}/{len(monitor_tasks)}")
        
        return none_chat_count == 0 and none_prefix_count == 0 and none_value_count == 0
        
    except Exception as e:
        logger.error(f"Error testing enhanced TP/SL alerts: {e}")
        return False

async def test_mirror_tp_sl_setup():
    """Test that mirror TP/SL setup works"""
    try:
        from execution.mirror_enhanced_tp_sl import MirrorEnhancedTPSLManager
        
        # Create a mock main manager
        class MockMainManager:
            async def create_dashboard_monitor_entry(self, **kwargs):
                logger.info(f"Mock dashboard monitor created: {kwargs}")
                return True
        
        # Test initialization
        mock_main = MockMainManager()
        mirror_manager = MirrorEnhancedTPSLManager(mock_main)
        
        # Check if setup_mirror_tp_sl_orders exists
        if hasattr(mirror_manager, 'setup_mirror_tp_sl_orders'):
            logger.info("✅ Mirror manager has setup_mirror_tp_sl_orders method")
            return True
        else:
            logger.error("❌ Mirror manager missing setup_mirror_tp_sl_orders method")
            return False
            
    except Exception as e:
        logger.error(f"Error testing mirror TP/SL setup: {e}")
        return False

async def test_persistence_integrity():
    """Test that persistence file has proper integrity"""
    try:
        from utils.robust_persistence import RobustPersistenceManager
        
        # Initialize manager
        persistence_manager = RobustPersistenceManager()
        
        # Test read operation
        data = await persistence_manager.read_data()
        
        # Check structure
        required_keys = ['conversations', 'user_data', 'chat_data', 'bot_data', 'callback_data']
        missing_keys = [k for k in required_keys if k not in data]
        
        if missing_keys:
            logger.error(f"❌ Missing required keys: {missing_keys}")
            return False
        
        # Check bot_data structure
        bot_data = data.get('bot_data', {})
        required_bot_keys = ['enhanced_tp_sl_monitors', 'monitor_tasks']
        missing_bot_keys = [k for k in required_bot_keys if k not in bot_data]
        
        if missing_bot_keys:
            logger.error(f"❌ Missing bot_data keys: {missing_bot_keys}")
            return False
        
        logger.info("✅ Persistence file structure is valid")
        
        # Test write operation
        test_key = '_test_verification_timestamp'
        bot_data[test_key] = asyncio.get_event_loop().time()
        
        success = await persistence_manager.write_data(data)
        
        if success:
            logger.info("✅ Persistence write operation successful")
            
            # Clean up test key
            del bot_data[test_key]
            await persistence_manager.write_data(data)
            
            return True
        else:
            logger.error("❌ Persistence write operation failed")
            return False
            
    except Exception as e:
        logger.error(f"Error testing persistence integrity: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("Starting fixes verification tests...")
    logger.info("=" * 60)
    
    # Test 1: Enhanced TP/SL alerts
    logger.info("\n1. Testing Enhanced TP/SL alerts with chat_id...")
    alerts_ok = await test_enhanced_tp_sl_alerts()
    
    # Test 2: Mirror TP/SL setup
    logger.info("\n2. Testing Mirror TP/SL setup...")
    mirror_ok = await test_mirror_tp_sl_setup()
    
    # Test 3: Persistence integrity
    logger.info("\n3. Testing Persistence integrity...")
    persistence_ok = await test_persistence_integrity()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST RESULTS:")
    logger.info(f"  Enhanced TP/SL alerts: {'✅ PASS' if alerts_ok else '❌ FAIL'}")
    logger.info(f"  Mirror TP/SL setup: {'✅ PASS' if mirror_ok else '❌ FAIL'}")
    logger.info(f"  Persistence integrity: {'✅ PASS' if persistence_ok else '❌ FAIL'}")
    
    all_tests_passed = alerts_ok and mirror_ok and persistence_ok
    logger.info(f"\nOVERALL: {'✅ ALL TESTS PASSED' if all_tests_passed else '❌ SOME TESTS FAILED'}")
    logger.info("=" * 60)
    
    return all_tests_passed

if __name__ == "__main__":
    asyncio.run(main())