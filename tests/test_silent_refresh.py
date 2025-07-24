#!/usr/bin/env python3
"""
Test script to verify silent dashboard refresh functionality
"""
import asyncio
import logging
from unittest.mock import Mock, AsyncMock, MagicMock

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Mock the required modules
import sys
from unittest.mock import MagicMock

# Create mock modules
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['telegram.constants'] = MagicMock()
sys.modules['config'] = MagicMock()
sys.modules['config.constants'] = MagicMock()
sys.modules['utils'] = MagicMock()
sys.modules['utils.helpers'] = MagicMock()
sys.modules['dashboard'] = MagicMock()
sys.modules['dashboard.generator_analytics_compact'] = MagicMock()
sys.modules['dashboard.keyboards_analytics'] = MagicMock()
sys.modules['shared'] = MagicMock()
sys.modules['utils.formatters'] = MagicMock()
sys.modules['utils.position_modes'] = MagicMock()
sys.modules['clients'] = MagicMock()
sys.modules['clients.bybit_helpers'] = MagicMock()

# Set up mock constants
sys.modules['config.constants'].LAST_UI_MESSAGE_ID = 'last_ui_message_id'
sys.modules['telegram.constants'].ParseMode = MagicMock()
sys.modules['telegram.constants'].ParseMode.HTML = 'HTML'

# Import after mocking
from handlers.commands import _send_or_edit_dashboard_message

async def test_auto_refresh_scenarios():
    """Test different auto-refresh scenarios"""
    
    print("Testing Dashboard Silent Refresh Functionality")
    print("=" * 50)
    
    # Test 1: Auto-refresh with unchanged content
    print("\nTest 1: Auto-refresh with unchanged content")
    ctx = Mock()
    ctx.chat_data = {
        'last_dashboard_content_hash': 'abc123',
        'last_ui_message_id': 12345
    }
    ctx.bot = AsyncMock()
    
    # Mock dashboard generation to return same content
    sys.modules['dashboard.generator_analytics_compact'].build_mobile_dashboard_text = AsyncMock(
        return_value="Dashboard content"
    )
    sys.modules['dashboard.keyboards_analytics'].build_enhanced_dashboard_keyboard = Mock()
    sys.modules['clients.bybit_helpers'].get_all_positions = AsyncMock(return_value=[])
    
    await _send_or_edit_dashboard_message(123456, ctx, new_msg=False)
    
    # Should not send any message
    ctx.bot.send_message.assert_not_called()
    ctx.bot.edit_message_text.assert_not_called()
    print("✅ Passed: No message sent for unchanged content")
    
    # Test 2: Auto-refresh with changed content
    print("\nTest 2: Auto-refresh with changed content")
    ctx = Mock()
    ctx.chat_data = {
        'last_dashboard_content_hash': 'old_hash',
        'last_ui_message_id': 12345
    }
    ctx.bot = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock()
    
    # Mock dashboard with new content
    sys.modules['dashboard.generator_analytics_compact'].build_mobile_dashboard_text = AsyncMock(
        return_value="New dashboard content"
    )
    
    await _send_or_edit_dashboard_message(123456, ctx, new_msg=False)
    
    # Should edit existing message
    ctx.bot.edit_message_text.assert_called_once()
    ctx.bot.send_message.assert_not_called()
    print("✅ Passed: Edited existing message for changed content")
    
    # Test 3: Auto-refresh when message is deleted
    print("\nTest 3: Auto-refresh when message is deleted")
    ctx = Mock()
    ctx.chat_data = {
        'last_ui_message_id': 12345
    }
    ctx.bot = AsyncMock()
    ctx.bot.edit_message_text = AsyncMock(side_effect=Exception("Message to edit not found"))
    ctx.bot.send_message = AsyncMock(return_value=Mock(message_id=67890))
    
    await _send_or_edit_dashboard_message(123456, ctx, new_msg=False)
    
    # Should send new message with disable_notification=True
    ctx.bot.send_message.assert_called_once()
    call_args = ctx.bot.send_message.call_args
    assert call_args.kwargs.get('disable_notification') == True
    print("✅ Passed: Sent silent message when original was deleted")
    
    # Test 4: Manual refresh
    print("\nTest 4: Manual refresh")
    ctx = Mock()
    ctx.chat_data = {
        'last_ui_message_id': 12345
    }
    ctx.bot = AsyncMock()
    ctx.bot.delete_message = AsyncMock()
    ctx.bot.send_message = AsyncMock(return_value=Mock(message_id=67890))
    
    await _send_or_edit_dashboard_message(123456, ctx, new_msg=True)
    
    # Should delete old and send new WITHOUT disable_notification
    ctx.bot.delete_message.assert_called_once()
    ctx.bot.send_message.assert_called_once()
    call_args = ctx.bot.send_message.call_args
    assert 'disable_notification' not in call_args.kwargs
    print("✅ Passed: Manual refresh sends with notification")
    
    print("\n" + "=" * 50)
    print("All tests passed! Dashboard refresh is now silent.")
    print("\nSummary:")
    print("- Auto-refresh skips update if content unchanged")
    print("- Auto-refresh edits existing message when possible")
    print("- Auto-refresh sends silent message if original deleted")
    print("- Manual refresh still sends notifications")

if __name__ == "__main__":
    asyncio.run(test_auto_refresh_scenarios())