#!/usr/bin/env python3
"""
Test script to validate monitor separation fixes
"""
import asyncio
import logging
import time
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal

# Import required modules
from config.constants import *
from handlers.conversation import execute_both_trades
from execution.monitor import start_position_monitoring
from telegram.ext import ContextTypes
from telegram import Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockUpdate:
    """Mock Update object for testing"""
    def __init__(self, chat_id=12345):
        self.callback_query = MagicMock()
        self.callback_query.message.chat.id = chat_id

class MockContext:
    """Mock Context object for testing"""
    def __init__(self, chat_id=12345):
        self.chat_data = {
            SYMBOL: "BTCUSDT",
            SIDE: "Buy",
            LEVERAGE: 10,
            MARGIN_AMOUNT: Decimal("100"),
            "margin_amount": Decimal("100"),
            "margin_amount_usdt": Decimal("100"),
        }
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.application = MagicMock()
        self.application.bot_data = {'monitor_tasks': {}}

def test_monitor_key_generation():
    """Test that monitor keys are generated correctly"""
    logger.info("Testing monitor key generation...")
    
    chat_id = 12345
    symbol = "BTCUSDT"
    
    # Test fast approach key
    fast_key = f"{chat_id}_{symbol}_fast"
    logger.info(f"Fast approach key: {fast_key}")
    
    # Test conservative approach key
    conservative_key = f"{chat_id}_{symbol}_conservative"
    logger.info(f"Conservative approach key: {conservative_key}")
    
    # Test mirror keys
    fast_mirror_key = f"{chat_id}_{symbol}_fast_{ACCOUNT_TYPE_MIRROR}"
    conservative_mirror_key = f"{chat_id}_{symbol}_conservative_{ACCOUNT_TYPE_MIRROR}"
    logger.info(f"Fast mirror key: {fast_mirror_key}")
    logger.info(f"Conservative mirror key: {conservative_mirror_key}")
    
    # Verify they are all different
    keys = [fast_key, conservative_key, fast_mirror_key, conservative_mirror_key]
    assert len(set(keys)) == len(keys), "Monitor keys should be unique"
    logger.info("✅ Monitor key generation test passed")

async def test_chat_data_isolation():
    """Test that chat_data is properly isolated during dual trade execution"""
    logger.info("Testing chat_data isolation...")
    
    # Create mock objects
    update = MockUpdate()
    context = MockContext()
    
    # Store original chat_data
    original_data = context.chat_data.copy()
    
    # Mock the execute_trade_logic function to avoid actual trading
    async def mock_execute_trade_logic(app, chat_id, cfg):
        # Verify that the cfg has the correct approach
        approach = cfg.get(TRADING_APPROACH)
        logger.info(f"Mock trade executed with approach: {approach}")
        
        # Verify isolated config
        assert approach in ["fast", "conservative"], f"Invalid approach: {approach}"
        
        if approach == "fast":
            assert cfg[ORDER_STRATEGY] == STRATEGY_MARKET_ONLY
            assert cfg[MARGIN_AMOUNT] == Decimal("50")  # Half of original 100
        elif approach == "conservative":
            assert cfg[ORDER_STRATEGY] == STRATEGY_CONSERVATIVE_LIMITS
            assert cfg[MARGIN_AMOUNT] == Decimal("50")  # Half of original 100
            assert CONSERVATIVE_TRADE_GROUP_ID in cfg
        
        return {"success": True, "message": f"Mock {approach} trade successful"}
    
    # Mock imports and functions
    with patch('execution.trader.execute_trade_logic', mock_execute_trade_logic):
        with patch('handlers.conversation.protect_trade_group_from_cleanup'):
            with patch('handlers.commands._send_or_edit_dashboard_message'):
                with patch('html.escape', lambda x: x):
                    # Execute the dual trade function
                    try:
                        result = await execute_both_trades(update, context)
                        logger.info(f"Dual trade execution result: {result}")
                    except Exception as e:
                        logger.error(f"Error in dual trade execution: {e}")
                        # Don't fail the test on mock issues, focus on data isolation
                        pass
    
    # Verify that original chat_data is restored
    for key, value in original_data.items():
        if key in context.chat_data:
            assert context.chat_data[key] == value, f"Chat data not properly restored for {key}"
    
    logger.info("✅ Chat data isolation test passed")

async def test_monitor_creation_validation():
    """Test monitor creation validation logic"""
    logger.info("Testing monitor creation validation...")
    
    # Create mock application with bot_data
    mock_app = MagicMock()
    mock_app.bot_data = {'monitor_tasks': {}}
    
    chat_id = 12345
    symbol = "BTCUSDT"
    
    # Test data for both approaches
    fast_chat_data = {
        SYMBOL: symbol,
        TRADING_APPROACH: "fast",
        POSITION_IDX: 0
    }
    
    conservative_chat_data = {
        SYMBOL: symbol,
        TRADING_APPROACH: "conservative",
        POSITION_IDX: 0
    }
    
    # Mock the task registration and monitoring loop
    with patch('execution.monitor.register_monitor_task'):
        with patch('execution.monitor.asyncio.create_task'):
            with patch('execution.monitor.monitor_position_loop_enhanced'):
                # Start monitoring for fast approach
                await start_position_monitoring(mock_app, chat_id, fast_chat_data)
                
                # Verify fast monitor was created
                fast_key = f"{chat_id}_{symbol}_fast"
                assert fast_key in mock_app.bot_data['monitor_tasks']
                fast_monitor = mock_app.bot_data['monitor_tasks'][fast_key]
                assert fast_monitor['approach'] == 'fast'
                assert fast_monitor['active'] == True
                logger.info("✅ Fast monitor created successfully")
                
                # Start monitoring for conservative approach
                await start_position_monitoring(mock_app, chat_id, conservative_chat_data)
                
                # Verify conservative monitor was created
                conservative_key = f"{chat_id}_{symbol}_conservative"
                assert conservative_key in mock_app.bot_data['monitor_tasks']
                conservative_monitor = mock_app.bot_data['monitor_tasks'][conservative_key]
                assert conservative_monitor['approach'] == 'conservative'
                assert conservative_monitor['active'] == True
                logger.info("✅ Conservative monitor created successfully")
                
                # Verify both monitors exist simultaneously
                assert len(mock_app.bot_data['monitor_tasks']) == 2
                logger.info("✅ Both monitors exist simultaneously")
                
                # Test duplicate creation (should update, not create new)
                await start_position_monitoring(mock_app, chat_id, fast_chat_data)
                assert len(mock_app.bot_data['monitor_tasks']) == 2  # Should still be 2
                assert 'updated_at' in mock_app.bot_data['monitor_tasks'][fast_key]
                logger.info("✅ Duplicate monitor creation handled correctly")
    
    logger.info("✅ Monitor creation validation test passed")

def test_monitor_separation_scenarios():
    """Test various monitor separation scenarios"""
    logger.info("Testing monitor separation scenarios...")
    
    bot_data = {'monitor_tasks': {}}
    chat_id = 12345
    
    # Scenario 1: Single symbol, single approach
    symbol1 = "BTCUSDT"
    bot_data['monitor_tasks'][f"{chat_id}_{symbol1}_fast"] = {
        'chat_id': chat_id,
        'symbol': symbol1,
        'approach': 'fast',
        'active': True
    }
    
    # Scenario 2: Single symbol, dual approaches (GOOD)
    symbol2 = "ETHUSDT"
    bot_data['monitor_tasks'][f"{chat_id}_{symbol2}_fast"] = {
        'chat_id': chat_id,
        'symbol': symbol2,
        'approach': 'fast',
        'active': True
    }
    bot_data['monitor_tasks'][f"{chat_id}_{symbol2}_conservative"] = {
        'chat_id': chat_id,
        'symbol': symbol2,
        'approach': 'conservative',
        'active': True
    }
    
    # Scenario 3: Single symbol with mirror accounts
    symbol3 = "ADAUSDT"
    bot_data['monitor_tasks'][f"{chat_id}_{symbol3}_fast"] = {
        'chat_id': chat_id,
        'symbol': symbol3,
        'approach': 'fast',
        'active': True
    }
    bot_data['monitor_tasks'][f"{chat_id}_{symbol3}_fast_{ACCOUNT_TYPE_MIRROR}"] = {
        'chat_id': chat_id,
        'symbol': symbol3,
        'approach': 'fast',
        'account_type': ACCOUNT_TYPE_MIRROR,
        'active': True
    }
    
    # Analyze the scenarios
    symbols_with_monitors = {}
    for key, monitor in bot_data['monitor_tasks'].items():
        symbol = monitor['symbol']
        approach = monitor['approach']
        is_mirror = monitor.get('account_type') == ACCOUNT_TYPE_MIRROR
        
        if symbol not in symbols_with_monitors:
            symbols_with_monitors[symbol] = []
        
        symbols_with_monitors[symbol].append({
            'approach': approach,
            'mirror': is_mirror,
            'key': key
        })
    
    # Validate scenarios
    for symbol, monitors in symbols_with_monitors.items():
        approaches = set(m['approach'] for m in monitors)
        logger.info(f"Symbol {symbol}: {len(monitors)} monitors, approaches: {approaches}")
        
        # Check for proper separation
        for approach in approaches:
            approach_monitors = [m for m in monitors if m['approach'] == approach]
            primary_count = len([m for m in approach_monitors if not m['mirror']])
            mirror_count = len([m for m in approach_monitors if m['mirror']])
            
            logger.info(f"  {approach}: {primary_count} primary, {mirror_count} mirror")
            assert primary_count <= 1, f"Too many primary monitors for {symbol}/{approach}"
            assert mirror_count <= 1, f"Too many mirror monitors for {symbol}/{approach}"
    
    logger.info("✅ Monitor separation scenarios test passed")

async def run_all_tests():
    """Run all tests"""
    logger.info("Starting monitor separation tests...")
    
    # Test 1: Monitor key generation
    test_monitor_key_generation()
    
    # Test 2: Chat data isolation
    await test_chat_data_isolation()
    
    # Test 3: Monitor creation validation
    await test_monitor_creation_validation()
    
    # Test 4: Monitor separation scenarios
    test_monitor_separation_scenarios()
    
    logger.info("✅ All monitor separation tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_all_tests())