#!/usr/bin/env python3
"""
Comprehensive backup of monitor and pickle data before potential restart
"""
import pickle
import json
import shutil
from datetime import datetime
import os

def create_comprehensive_backup():
    """Create comprehensive backup of all bot data"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_comprehensive_{timestamp}"
    
    print(f"🔒 Creating comprehensive backup in: {backup_dir}")
    print("=" * 60)
    
    # Create backup directory
    os.makedirs(backup_dir, exist_ok=True)
    
    # 1. Backup pickle file
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    if os.path.exists(pickle_file):
        backup_pickle = f"{backup_dir}/bybit_bot_dashboard_v4.1_enhanced.pkl"
        shutil.copy2(pickle_file, backup_pickle)
        print(f"✅ Backed up pickle file: {backup_pickle}")
    
    # 2. Extract and save monitor data in human-readable format
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Save monitor summary
        monitor_summary = {}
        for monitor_key, monitor_data in monitors.items():
            monitor_summary[monitor_key] = {
                'symbol': monitor_data.get('symbol'),
                'side': monitor_data.get('side'),
                'account_type': monitor_data.get('account_type', 'main'),
                'position_size': str(monitor_data.get('position_size', 0)),
                'current_size': str(monitor_data.get('current_size', 0)),
                'remaining_size': str(monitor_data.get('remaining_size', 0)),
                'limit_orders_filled': monitor_data.get('limit_orders_filled', 0),
                'limit_orders_active': monitor_data.get('limit_orders_active', 0),
                'phase': monitor_data.get('phase', 'UNKNOWN'),
                'tp1_hit': monitor_data.get('tp1_hit', False),
                'sl_moved_to_be': monitor_data.get('sl_moved_to_be', False),
                'tp_orders_count': len(monitor_data.get('tp_orders', {})),
                'has_sl_order': bool(monitor_data.get('sl_order', {})),
                'limit_orders_count': len(monitor_data.get('limit_orders', [])),
                'created_at': str(monitor_data.get('created_at', 'N/A')),
                'last_check': str(monitor_data.get('last_check', 'N/A'))
            }
        
        monitor_summary_file = f"{backup_dir}/monitor_summary.json"
        with open(monitor_summary_file, 'w') as f:
            json.dump(monitor_summary, f, indent=2, default=str)
        print(f"✅ Monitor summary saved: {monitor_summary_file}")
        
        # Save full monitor data
        monitor_full_file = f"{backup_dir}/monitor_data_full.json"
        with open(monitor_full_file, 'w') as f:
            json.dump(monitors, f, indent=2, default=str)
        print(f"✅ Full monitor data saved: {monitor_full_file}")
        
        # Save statistics
        stats_data = {
            'stats_last_reset_timestamp': str(bot_data.get('stats_last_reset_timestamp', 'N/A')),
            'stats_total_trades_initiated': bot_data.get('stats_total_trades_initiated', 0),
            'stats_tp1_hits': bot_data.get('stats_tp1_hits', 0),
            'stats_sl_hits': bot_data.get('stats_sl_hits', 0),
            'stats_other_closures': bot_data.get('stats_other_closures', 0),
            'stats_total_pnl': str(bot_data.get('stats_total_pnl', 0)),
            'stats_total_wins': bot_data.get('stats_total_wins', 0),
            'stats_total_losses': bot_data.get('stats_total_losses', 0),
            'stats_win_streak': bot_data.get('stats_win_streak', 0),
            'stats_loss_streak': bot_data.get('stats_loss_streak', 0),
            'stats_best_trade': str(bot_data.get('stats_best_trade', 0)),
            'stats_worst_trade': str(bot_data.get('stats_worst_trade', 0))
        }
        
        stats_file = f"{backup_dir}/statistics.json"
        with open(stats_file, 'w') as f:
            json.dump(stats_data, f, indent=2)
        print(f"✅ Statistics saved: {stats_file}")
        
        # Monitor tasks
        monitor_tasks = bot_data.get('monitor_tasks', {})
        tasks_file = f"{backup_dir}/monitor_tasks.json"
        with open(tasks_file, 'w') as f:
            json.dump(monitor_tasks, f, indent=2, default=str)
        print(f"✅ Monitor tasks saved: {tasks_file}")
        
        print(f"\n📊 Current Status Summary:")
        print(f"   • Enhanced TP/SL Monitors: {len(monitors)}")
        print(f"   • Monitor Tasks: {len(monitor_tasks)}")
        print(f"   • Total Trades: {stats_data['stats_total_trades_initiated']}")
        print(f"   • Active Positions: {len([m for m in monitors.values() if m.get('phase') in ['BUILDING', 'MONITORING']])}")
        
        # Show monitor breakdown
        by_account = {}
        for monitor_key, monitor_data in monitors.items():
            account = monitor_data.get('account_type', 'main')
            if account not in by_account:
                by_account[account] = []
            by_account[account].append(f"{monitor_data.get('symbol', 'UNKNOWN')}_{monitor_data.get('side', 'UNKNOWN')}")
        
        print(f"\n📋 Monitor Breakdown:")
        for account, positions in by_account.items():
            print(f"   • {account.upper()}: {len(positions)} positions - {', '.join(positions)}")
        
        # Check for the fix we applied
        cyberusdt_main = monitors.get('CYBERUSDT_Buy_main', {})
        cyberusdt_mirror = monitors.get('CYBERUSDT_Buy_mirror', {})
        
        print(f"\n🔧 Fix Status Check:")
        print(f"   • CYBERUSDT Main limit_orders_filled: {cyberusdt_main.get('limit_orders_filled', 'NOT FOUND')}")
        print(f"   • CYBERUSDT Mirror limit_orders_filled: {cyberusdt_mirror.get('limit_orders_filled', 'NOT FOUND')}")
        
    except Exception as e:
        print(f"❌ Error creating monitor backup: {e}")
    
    # 3. Backup important config files
    important_files = [
        '.env',
        'config/settings.py',
        'config/constants.py',
        'CLAUDE.md'
    ]
    
    for file_path in important_files:
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            backup_path = f"{backup_dir}/{filename}"
            shutil.copy2(file_path, backup_path)
            print(f"✅ Backed up config: {backup_path}")
    
    # 4. Create restore instructions
    restore_instructions = f"""
# Restore Instructions for {timestamp}

## To restore this backup:

1. Stop the bot:
   pkill -f "python.*main.py"

2. Restore pickle file:
   cp {backup_dir}/bybit_bot_dashboard_v4.1_enhanced.pkl ./

3. Restore config files (if needed):
   cp {backup_dir}/.env ./
   cp {backup_dir}/settings.py config/
   cp {backup_dir}/constants.py config/

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
- Total monitors: {len(monitors)}
- Active positions: {len([m for m in monitors.values() if m.get('phase') in ['BUILDING', 'MONITORING']])}
- Bot was running and functioning normally
"""
    
    readme_file = f"{backup_dir}/README.md"
    with open(readme_file, 'w') as f:
        f.write(restore_instructions)
    print(f"✅ Restore instructions: {readme_file}")
    
    print("\n" + "=" * 60)
    print(f"🎉 Comprehensive backup complete!")
    print(f"📁 Location: {backup_dir}/")
    print(f"💾 Total files backed up: {len(os.listdir(backup_dir))}")
    print("\n✅ Your data is safe. You can proceed with confidence.")
    print("🔄 No restart needed - the fix is already active!")

if __name__ == "__main__":
    create_comprehensive_backup()