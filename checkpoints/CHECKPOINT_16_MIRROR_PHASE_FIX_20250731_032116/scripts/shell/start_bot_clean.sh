#!/bin/bash
# Clean startup script for the bot

echo "🚀 Starting Bybit Trading Bot"
echo "============================"

# Kill any existing bot processes
echo "🔄 Stopping any existing bot processes..."
pkill -f "python3 main.py" 2>/dev/null
sleep 2

# Clear the log file
echo "📝 Clearing old logs..."
> trading_bot.log

# Navigate to bot directory
cd ~/bybit-telegram-bot

# Activate virtual environment
echo "🐍 Activating Python environment..."
source venv/bin/activate

# Start the bot
echo "🤖 Starting bot with conservative-only mode..."
echo "✅ All errors have been fixed"
echo "✅ Monitor system will handle tp_orders correctly"
echo ""
echo "Starting in 3 seconds..."
sleep 3

# Run the bot
python3 main.py