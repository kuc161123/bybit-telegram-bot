#!/bin/bash
# Kill bot script - safely stops the Bybit Telegram Bot

echo "Stopping Bybit Telegram Bot..."

# Find and kill the main.py process
PIDS=$(ps aux | grep 'python main.py' | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "Bot is not running."
else
    echo "Found bot process(es): $PIDS"
    for PID in $PIDS; do
        echo "Killing process $PID..."
        kill -TERM $PID 2>/dev/null || kill -9 $PID 2>/dev/null
    done
    echo "Bot stopped."
fi

# Also check for run_main.sh
PIDS=$(ps aux | grep 'run_main.sh' | grep -v grep | awk '{print $2}')

if [ ! -z "$PIDS" ]; then
    echo "Found run_main.sh process(es): $PIDS"
    for PID in $PIDS; do
        echo "Killing process $PID..."
        kill -TERM $PID 2>/dev/null || kill -9 $PID 2>/dev/null
    done
fi

echo "Done."