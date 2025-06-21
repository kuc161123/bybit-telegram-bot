#!/bin/bash
while true
do
    echo "Starting bot at $(date)"
    python3 main.py
    echo "Bot crashed at $(date). Restarting in 5 seconds..."
    sleep 5
done

