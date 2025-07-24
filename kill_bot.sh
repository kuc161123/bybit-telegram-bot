#!/bin/bash

echo "🛑 Stopping all Bybit Trading Bot instances..."

# Kill all Python processes running main.py
echo "Killing main.py processes..."
pkill -f "python.*main.py"

# Kill any Python processes with bot-related names
echo "Killing bot-related Python processes..."
pkill -f "python.*(bybit|trading|telegram).*bot"

# Kill any remaining Python processes in this directory
echo "Killing Python processes in current directory..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
lsof +D "$SCRIPT_DIR" 2>/dev/null | grep -i python | awk '{print $2}' | sort -u | xargs -r kill -9 2>/dev/null

# Clean up any nohup output
echo "Cleaning up nohup.out..."
rm -f nohup.out

# Check if any processes remain
REMAINING=$(pgrep -f "python.*main.py" | wc -l)
if [ "$REMAINING" -eq 0 ]; then
    echo "✅ All bot instances stopped successfully!"
else
    echo "⚠️  Warning: $REMAINING Python processes may still be running"
    echo "Run 'ps aux | grep python' to check"
fi

echo "🧹 Cleanup complete!"