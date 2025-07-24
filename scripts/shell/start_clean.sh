#!/bin/bash
# Clean startup script

echo "🧹 Clean Bot Startup"
echo "=================="

# Kill any existing processes
pkill -f "python3 main.py" 2>/dev/null
sleep 2

# Clear logs
> trading_bot.log

# Remove stop markers
rm -f .stop_*_monitoring 2>/dev/null

# Start the bot
cd ~/bybit-telegram-bot
source venv/bin/activate
python3 main.py
