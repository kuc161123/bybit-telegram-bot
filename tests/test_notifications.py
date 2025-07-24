#!/usr/bin/env python3
"""
Test notification system to ensure alerts are working
"""
import asyncio
import logging
import os
from decimal import Decimal
from dotenv import load_dotenv

from telegram import Bot
from utils.alert_helpers import send_trade_alert

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_limit_fill_notification(bot: Bot, chat_id: int):
    """Test limit order fill notification"""
    logger.info("Testing limit order fill notification...")
    
    await send_trade_alert(
        bot=bot,
        chat_id=chat_id,
        alert_type="limit_filled",
        symbol="TESTUSDT",
        side="Buy",
        approach="conservative",
        pnl=Decimal("0"),
        entry_price=Decimal("50000"),
        current_price=Decimal("50000"),
        position_size=Decimal("0.1"),
        additional_info={
            "limit_number": 2,
            "total_limits": 3,
            "fill_price": Decimal("50000"),
            "fill_size": Decimal("0.1"),
            "filled_count": 2
        }
    )
    logger.info("✅ Limit fill notification sent")

async def test_tp_hit_notification(bot: Bot, chat_id: int):
    """Test TP hit notification"""
    logger.info("Testing TP hit notification...")
    
    await send_trade_alert(
        bot=bot,
        chat_id=chat_id,
        alert_type="tp_hit",
        symbol="TESTUSDT",
        side="Buy",
        approach="conservative",
        pnl=Decimal("150.50"),
        entry_price=Decimal("50000"),
        current_price=Decimal("51500"),
        position_size=Decimal("0.1"),
        cancelled_orders=[],
        additional_info={
            "tp_number": 1,
            "remaining_tps": ["TP2", "TP3", "TP4"]
        }
    )
    logger.info("✅ TP hit notification sent")

async def test_sl_hit_notification(bot: Bot, chat_id: int):
    """Test SL hit notification"""
    logger.info("Testing SL hit notification...")
    
    await send_trade_alert(
        bot=bot,
        chat_id=chat_id,
        alert_type="sl_hit",
        symbol="TESTUSDT",
        side="Buy",
        approach="conservative",
        pnl=Decimal("-50.25"),
        entry_price=Decimal("50000"),
        current_price=Decimal("49000"),
        position_size=Decimal("0.1"),
        cancelled_orders=["Unfilled limit 12345...", "TP2 order 67890..."]
    )
    logger.info("✅ SL hit notification sent")

async def test_position_closed_notification(bot: Bot, chat_id: int):
    """Test position closed notification"""
    logger.info("Testing position closed notification...")
    
    from utils.alert_helpers import send_position_closed_summary
    
    # Simulate position closed data
    await send_position_closed_summary(
        bot=bot,
        chat_id=chat_id,
        symbol="TESTUSDT",
        side="Buy",
        approach="conservative",
        final_pnl=Decimal("250.75"),
        close_reason="TP_HIT",
        entry_price=Decimal("50000"),
        close_price=Decimal("52500"),
        position_size=Decimal("0.1"),
        duration_minutes=245,
        trade_summary={
            "total_fills": 3,
            "tp_hits": ["TP1", "TP3"],
            "fees_paid": Decimal("5.25")
        }
    )
    logger.info("✅ Position closed notification sent")

async def main():
    """Run all notification tests"""
    # Get bot token and chat ID
    bot_token = os.getenv('TELEGRAM_TOKEN')
    if not bot_token:
        logger.error("❌ TELEGRAM_TOKEN not found in .env file")
        return
    
    # You need to set your chat ID here
    CHAT_ID = 123456789  # CHANGE THIS TO YOUR CHAT ID
    
    if CHAT_ID == 123456789:
        logger.error("❌ Please update CHAT_ID in the script!")
        logger.info("\nTo find your chat ID:")
        logger.info("1. Send /start to your bot")
        logger.info("2. Check bot logs for your chat ID")
        return
    
    logger.info("=" * 60)
    logger.info("TESTING NOTIFICATION SYSTEM")
    logger.info("=" * 60)
    logger.info(f"Bot Token: {bot_token[:10]}...")
    logger.info(f"Chat ID: {CHAT_ID}")
    
    # Create bot instance
    bot = Bot(token=bot_token)
    
    try:
        # Test bot connection
        bot_info = await bot.get_me()
        logger.info(f"✅ Connected to bot: @{bot_info.username}")
        
        # Send test message
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🧪 <b>NOTIFICATION TEST STARTING</b>\n\nYou should receive 4 test notifications:",
            parse_mode='HTML'
        )
        
        # Run tests with delays
        await asyncio.sleep(2)
        await test_limit_fill_notification(bot, CHAT_ID)
        
        await asyncio.sleep(2)
        await test_tp_hit_notification(bot, CHAT_ID)
        
        await asyncio.sleep(2)
        await test_sl_hit_notification(bot, CHAT_ID)
        
        await asyncio.sleep(2)
        await test_position_closed_notification(bot, CHAT_ID)
        
        # Final message
        await asyncio.sleep(2)
        await bot.send_message(
            chat_id=CHAT_ID,
            text="✅ <b>NOTIFICATION TEST COMPLETE</b>\n\nIf you received all 4 notifications, your alert system is working correctly!",
            parse_mode='HTML'
        )
        
        logger.info("\n✅ All test notifications sent!")
        logger.info("\nCheck your Telegram to verify you received:")
        logger.info("1. Limit order fill notification")
        logger.info("2. TP hit notification")
        logger.info("3. SL hit notification")
        logger.info("4. Position closed notification")
        
    except Exception as e:
        logger.error(f"❌ Error during test: {e}")
        logger.info("\nTroubleshooting:")
        logger.info("1. Check TELEGRAM_TOKEN is correct")
        logger.info("2. Verify CHAT_ID is your actual chat ID")
        logger.info("3. Ensure bot is not blocked in Telegram")

if __name__ == "__main__":
    asyncio.run(main())