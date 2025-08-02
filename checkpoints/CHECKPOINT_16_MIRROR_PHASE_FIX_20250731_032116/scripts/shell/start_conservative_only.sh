#!/bin/bash
# Clean startup for conservative-only trading

echo "🛡️ Starting Conservative-Only Trading Bot"
echo "========================================"

# Kill any existing instances
pkill -f "python3 main.py" 2>/dev/null
sleep 2

# Clear any stuck monitors
rm -f .stop_*_monitoring 2>/dev/null

# Clear logs
> trading_bot.log

# Set environment variable
export TRADING_APPROACH_OVERRIDE="conservative"

# Start the bot
cd ~/bybit-telegram-bot
source venv/bin/activate
python3 main.py
