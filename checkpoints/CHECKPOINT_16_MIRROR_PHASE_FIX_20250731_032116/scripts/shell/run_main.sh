#!/bin/bash

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables if .env exists
if [ -f ".env" ]; then
    export $(cat .env | xargs)
    echo "✅ Loaded environment variables from .env file"
fi

while true
do
    echo "Starting bot at $(date)"
    python main.py
    echo "Bot crashed at $(date). Restarting in 5 seconds..."
    sleep 5
done