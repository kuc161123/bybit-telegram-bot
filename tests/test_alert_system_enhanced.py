#!/usr/bin/env python3
"""
Test script to verify enhanced TP/SL alert system is working
"""
import asyncio
import logging
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_alerts():
    """Test the alert system for all current positions"""
    try:
        # Import required modules
        from utils.alert_helpers import send_simple_alert
        from clients.bybit_helpers import get_all_positions
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from shared.state import get_application
        
        logger.info("🔍 Testing Enhanced TP/SL Alert System...")
        
        # Get current positions
        positions = await get_all_positions()
        if not positions:
            logger.info("📋 No open positions to test alerts for")
            return
        
        logger.info(f"📊 Found {len(positions)} open positions")
        
        # Get chat IDs from monitors
        chat_ids = set()
        for symbol_side, monitor in enhanced_tp_sl_manager.position_monitors.items():
            chat_id = monitor.get('chat_id')
            if chat_id:
                chat_ids.add(chat_id)
        
        if not chat_ids:
            logger.warning("⚠️ No chat IDs found in monitors")
            # Try to get from application context
            try:
                app = get_application()
                if app and hasattr(app, 'chat_data'):
                    for cid in app.chat_data.keys():
                        chat_ids.add(cid)
                        logger.info(f"✅ Found chat ID from app context: {cid}")
            except Exception as e:
                logger.error(f"Could not get chat IDs from app: {e}")
        
        # Test alert for each position
        for position in positions:
            symbol = position.get('symbol', 'UNKNOWN')
            side = position.get('side', 'UNKNOWN')
            size = Decimal(str(position.get('size', '0')))
            avg_price = Decimal(str(position.get('avgPrice', '0')))
            mark_price = Decimal(str(position.get('markPrice', '0')))
            
            # Calculate P&L
            if side == "Buy":
                pnl = (mark_price - avg_price) * size
                pnl_percent = float(((mark_price - avg_price) / avg_price) * 100) if avg_price > 0 else 0
            else:
                pnl = (avg_price - mark_price) * size
                pnl_percent = float(((avg_price - mark_price) / avg_price) * 100) if avg_price > 0 else 0
            
            # Create test alert message
            message = f"""🧪 <b>ALERT SYSTEM TEST</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} {'📈' if side == 'Buy' else '📉'} {side}

📍 Entry: ${avg_price:.6f}
💹 Current: ${mark_price:.6f}
📦 Size: {size:.6f}
💰 P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)

✅ Alert system is working!
This is a test message to verify alerts are being sent correctly."""
            
            # Send test alert to all chat IDs
            success_count = 0
            for chat_id in chat_ids:
                try:
                    logger.info(f"📤 Sending test alert for {symbol} to chat {chat_id}...")
                    result = await send_simple_alert(chat_id, message, "test")
                    if result:
                        success_count += 1
                        logger.info(f"✅ Alert sent successfully to chat {chat_id}")
                    else:
                        logger.error(f"❌ Failed to send alert to chat {chat_id}")
                except Exception as e:
                    logger.error(f"❌ Error sending alert to chat {chat_id}: {e}")
            
            if success_count > 0:
                logger.info(f"✅ Test alerts sent for {symbol}: {success_count}/{len(chat_ids)} successful")
            else:
                logger.error(f"❌ No alerts were sent successfully for {symbol}")
        
        # Check monitor status
        logger.info("\n📊 Monitor Status Check:")
        active_monitors = len(enhanced_tp_sl_manager.position_monitors)
        logger.info(f"Active Enhanced TP/SL Monitors: {active_monitors}")
        
        for monitor_key, monitor_data in enhanced_tp_sl_manager.position_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            side = monitor_data.get('side', 'UNKNOWN')
            phase = monitor_data.get('phase', 'UNKNOWN')
            chat_id = monitor_data.get('chat_id', 'NO_CHAT_ID')
            logger.info(f"  - {symbol} {side}: Phase={phase}, ChatID={chat_id}")
        
        logger.info("\n✅ Alert system test completed!")
        
    except Exception as e:
        logger.error(f"❌ Error testing alerts: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_alerts())