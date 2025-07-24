#!/bin/bash

echo "🔍 Force killing ALL Python processes related to the bot..."

# Kill any Python process in the bot directory
PIDS=$(lsof +D /Users/lualakol/bybit-telegram-bot 2>/dev/null | grep python | awk '{print $2}' | sort -u)

if [ ! -z "$PIDS" ]; then
    echo "Found Python processes in bot directory: $PIDS"
    for PID in $PIDS; do
        kill -9 $PID 2>/dev/null
        echo "   ✅ Force killed process $PID"
    done
fi

# Kill any process with main.py
pkill -9 -f "main.py"

# Kill any process with run_main.sh
pkill -9 -f "run_main.sh"

# Kill any Python process with telegram in the command
pkill -9 -f "python.*telegram"

# Kill any process using the persistence file
PERSISTENCE_PIDS=$(lsof 2>/dev/null | grep "bybit_bot_dashboard" | awk '{print $2}' | sort -u)
if [ ! -z "$PERSISTENCE_PIDS" ]; then
    echo "Found processes using persistence file: $PERSISTENCE_PIDS"
    for PID in $PERSISTENCE_PIDS; do
        kill -9 $PID 2>/dev/null
        echo "   ✅ Killed process using persistence file: $PID"
    done
fi

echo "🏁 Force cleanup complete"
echo ""
echo "⏳ Waiting 5 seconds for processes to fully terminate..."
sleep 5

echo ""
echo "🔍 Checking if any processes remain..."
REMAINING=$(ps aux | grep -E "(python.*main\.py|run_main\.sh)" | grep -v grep)
if [ -z "$REMAINING" ]; then
    echo "✅ All bot processes successfully terminated!"
else
    echo "⚠️  Some processes may still be running:"
    echo "$REMAINING"
fi