#!/bin/bash

echo "🔧 Restarting bot with performance fixes..."

# Kill existing bot processes
echo "🛑 Stopping existing bot..."
pkill -f "python.*main.py" || echo "No existing bot process found"
sleep 2

# Verify no processes running
RUNNING=$(ps aux | grep -E "(python.*main\.py)" | grep -v grep | wc -l)
if [ "$RUNNING" -gt 0 ]; then
    echo "⚠️  Bot still running, force killing..."
    pkill -9 -f "python.*main.py"
    sleep 2
fi

echo "✅ Bot stopped"

# Start the bot with optimizations
echo "🚀 Starting bot with performance optimizations..."
cd /Users/lualakol/bybit-telegram-bot
source venv/bin/activate

# Start in background with logging
nohup python main.py > trading_bot.log 2>&1 &
PID=$!

echo "🎯 Bot started with PID: $PID"
echo "📋 To monitor: tail -f trading_bot.log"
echo "🛑 To stop: kill $PID"

# Wait a moment and check if it's running
sleep 3
if ps -p $PID > /dev/null; then
    echo "✅ Bot is running successfully!"
    echo "📊 Performance improvements active:"
    echo "   • Enhanced cache utilization (target: 85%+ hit rate)"
    echo "   • Adaptive semaphore concurrency control"
    echo "   • Thread pool for CPU-bound operations"
    echo "   • Lock-free connection pool with burst capability"
else
    echo "❌ Bot failed to start, check trading_bot.log"
fi