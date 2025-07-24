# Quick Reference Guide

## Starting the Bot
```bash
python main.py
```

## Common Scripts

### Diagnostics
```bash
# Check both accounts
python scripts/diagnostics/check_both_accounts.py

# Check current positions
python scripts/diagnostics/check_current_status.py

# Check mirror account
python scripts/diagnostics/check_mirror_account.py
```

### Fixes
```bash
# Fix order cancellation errors
python scripts/fixes/fix_order_cancellation_errors.py

# Ensure mirror monitoring
python scripts/fixes/ensure_mirror_monitoring.py

# Fix missing TP/SL orders
python scripts/fixes/fix_missing_tp_sl_orders.py
```

### Maintenance
```bash
# Clean up monitors
python scripts/maintenance/cleanup_monitors.py

# Verify monitoring setup
python scripts/maintenance/verify_monitoring_setup.py

# Manual cleanup
python scripts/maintenance/manual_cleanup.py
```

## Shell Scripts
```bash
# Kill the bot
./scripts/shell/kill_bot.sh

# Force kill (if regular kill doesn't work)
./scripts/shell/force_kill_bot.sh

# Run with auto-restart
./scripts/shell/run_main.sh
```

## Project Structure
- `alerts/` - Alert system
- `clients/` - API clients (Bybit, OpenAI)
- `config/` - Configuration files
- `dashboard/` - Dashboard generators
- `execution/` - Trading execution (monitor, trader)
- `handlers/` - Telegram bot handlers
- `risk/` - Risk management
- `social_media/` - Social sentiment analysis
- `utils/` - Utility functions

## Scripts Organization
- `scripts/diagnostics/` - Check and debug scripts
- `scripts/fixes/` - Fix specific issues
- `scripts/analysis/` - Analyze data
- `scripts/maintenance/` - Cleanup and maintenance
- `scripts/shell/` - Shell scripts

## Other Directories
- `tests/` - Test files
- `docs/` - Documentation
- `data/` - Data files
- `logs/` - Log files
- `backups/` - Backup files
- `assets/` - Images and other assets
- `archive/` - Old/deprecated files
- `cache/` - Cached data