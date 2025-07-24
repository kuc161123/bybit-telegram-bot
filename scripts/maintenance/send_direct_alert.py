#!/usr/bin/env python3
"""
Send direct alert using Telegram bot token
"""
import asyncio
import logging
import os
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def send_direct_alert():
    """Send alert directly using bot token"""
    try:
        # Get bot token from environment
        bot_token = os.getenv('TELEGRAM_TOKEN')
        if not bot_token:
            logger.error("❌ TELEGRAM_TOKEN not found in environment")
            return
        
        # Known chat ID
        CHAT_ID = 5634913742
        
        # Create bot instance
        bot = Bot(token=bot_token)
        
        # Test message
        message = """🔔 <b>ALERT SYSTEM NOTIFICATION</b>
━━━━━━━━━━━━━━━━━━━━━━
✅ Alerts have been fixed!

The Enhanced TP/SL monitoring system is now active for all your positions:
• DOGEUSDT Buy
• WIFUSDT Buy  
• TIAUSDT Buy
• LINKUSDT Buy

You will receive alerts for:
• TP order fills
• SL order fills
• Position closures
• Limit order fills

🔄 Monitoring is active and running."""
        
        # Send message
        logger.info(f"📤 Sending alert to chat {CHAT_ID}...")
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
        logger.info("✅ Alert sent successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error sending alert: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(send_direct_alert())