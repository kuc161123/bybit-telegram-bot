#!/usr/bin/env python3
"""
Test Telegram connection
"""
import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot

async def test_connection():
    # Load environment variables
    load_dotenv()
    
    token = os.getenv('TELEGRAM_TOKEN')
    if not token:
        print("❌ No TELEGRAM_TOKEN found in .env file")
        return
    
    print(f"🔍 Testing connection with token: {token[:10]}...{token[-5:]}")
    
    try:
        bot = Bot(token=token)
        me = await bot.get_me()
        print(f"✅ Successfully connected to Telegram!")
        print(f"🤖 Bot name: {me.first_name}")
        print(f"🆔 Bot username: @{me.username}")
        print(f"🔢 Bot ID: {me.id}")
    except Exception as e:
        print(f"❌ Failed to connect: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())