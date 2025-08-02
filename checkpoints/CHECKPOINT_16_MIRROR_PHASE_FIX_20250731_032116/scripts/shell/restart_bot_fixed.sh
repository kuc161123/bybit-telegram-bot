#!/bin/bash
# Restart the bot with fixed monitors

echo "🛑 Stopping the bot..."
pkill -f "python.*main.py" || true
sleep 2

echo "✅ Bot stopped"
echo ""
echo "The false TP fill issue has been fixed:"
echo "1. Moved old backup files that had incorrect data"
echo "2. Fixed all mirror monitor position sizes"
echo "3. Cleared the fill tracker that was accumulating false data"
echo "4. Enhanced the monitoring code to detect false positives"
echo ""
echo "Please restart the bot with: python3 main.py"
echo ""
echo "The false TP fills should now be completely eliminated."