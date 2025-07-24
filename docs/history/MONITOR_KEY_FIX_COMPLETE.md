# Monitor Key Collision Fix - Status Update

## Summary
Implemented account-aware monitor keys to resolve the issue where only 7 monitors existed for 13 positions. The fix is working but position sync continues to create legacy monitors.

## What Was Fixed
1. **Monitor Key Format**: Changed from `{SYMBOL}_{SIDE}` to `{SYMBOL}_{SIDE}_{ACCOUNT_TYPE}`
2. **Prevented Collisions**: Both main and mirror accounts can now have monitors for the same symbol/side
3. **Created Missing Monitors**: Added 6 missing main account monitors
4. **Updated Position Sync**: Fixed the sync_existing_positions() method to use account-aware keys

## Changes Made
1. Updated `enhanced_tp_sl_manager.py` line 549 to use account-aware keys
2. Updated `background_tasks.py` to pass account_type to monitor functions
3. Updated `trader.py` to pass account_type="main" when creating monitors
4. Updated `sync_existing_positions()` lines 4380-4492 to use account-aware keys
5. Created scripts to remove duplicate monitors

## Current Status
- Bot is now monitoring 19 positions (was 20, then 13, now 19)
- Position sync is still creating some legacy monitors despite the fix
- The robust persistence manager is interfering with monitor storage
- Monitor count fluctuates as duplicates are created and removed

## Known Issues
1. Position sync may still have other code paths creating legacy monitors
2. Robust persistence manager removes monitors it considers "orphaned"
3. Monitor count is not stable at the expected 13

## Bot Log Status
```
2025-07-08 11:29:16,997 - helpers.background_tasks - INFO - 🔍 Monitoring 19 positions
```

The fix has been partially implemented but additional work may be needed to fully stabilize the monitor system.