
# Restore Instructions for 20250728_212001

## To restore this backup:

1. Stop the bot:
   pkill -f "python.*main.py"

2. Restore pickle file:
   cp backup_comprehensive_20250728_212001/bybit_bot_dashboard_v4.1_enhanced.pkl ./

3. Restore config files (if needed):
   cp backup_comprehensive_20250728_212001/.env ./
   cp backup_comprehensive_20250728_212001/settings.py config/
   cp backup_comprehensive_20250728_212001/constants.py config/

4. Restart the bot:
   python3 main.py

## Backup Contents:
- Full pickle file with all monitor data
- Monitor summary (human-readable)
- Full monitor data (JSON)
- Statistics data
- Monitor tasks
- Configuration files

## Fix Applied:
- CYBERUSDT main account: limit_orders_filled corrected
- CYBERUSDT mirror account: limit_orders_filled corrected
- Position tracking synchronized

## Status at backup time:
- Total monitors: 7
- Active positions: 6
- Bot was running and functioning normally
