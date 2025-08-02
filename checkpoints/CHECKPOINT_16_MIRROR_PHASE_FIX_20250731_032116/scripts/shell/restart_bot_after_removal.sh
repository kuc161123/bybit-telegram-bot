#!/bin/bash

echo "🛑 Stopping current bot instance..."
pkill -f "python main.py" || pkill -f "python3 main.py"
sleep 2

echo "✅ Auto-rebalancer has been completely removed"
echo "🚀 Starting bot without auto-rebalancer..."
cd "$(dirname "$0")"
python main.py