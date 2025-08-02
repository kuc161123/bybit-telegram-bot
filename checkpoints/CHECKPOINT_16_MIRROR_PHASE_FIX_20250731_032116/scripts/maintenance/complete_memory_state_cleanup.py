#!/usr/bin/env python3
"""
Complete Memory State Cleanup
Cleans all bot memory, monitors, persistence, and cached data
Ensures a completely fresh start
"""
import os
import sys
import pickle
import logging
import shutil
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backup_before_cleanup():
    """Create a backup of important data before cleanup"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_complete_cleanup_{timestamp}"
    
    logger.info(f"📦 Creating backup in: {backup_dir}")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Files to backup
    files_to_backup = [
        "bybit_bot_dashboard_v4.1_enhanced.pkl",
        "trading_bot.log",
        "data/enhanced_trade_history.json",
        ".env"  # Keep configuration safe
    ]
    
    backup_count = 0
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            try:
                dest_path = os.path.join(backup_dir, os.path.basename(file_path))
                shutil.copy2(file_path, dest_path)
                logger.info(f"   ✅ Backed up: {file_path}")
                backup_count += 1
            except Exception as e:
                logger.warning(f"   ⚠️ Could not backup {file_path}: {e}")
    
    logger.info(f"📦 Backup complete: {backup_count} files backed up")
    return backup_dir

def clear_persistence_file():
    """Clear the main persistence file completely"""
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    logger.info(f"🗑️ Clearing persistence file: {persistence_file}")
    
    # Create completely fresh bot_data structure
    fresh_data = {
        'conversations': {},
        'user_data': {},
        'chat_data': {},
        'bot_data': {
            # Reset all stats to zero
            'stats_total_trades_initiated': 0,
            'stats_tp1_hits': 0,
            'stats_sl_hits': 0,
            'stats_other_closures': 0,
            'stats_last_reset_timestamp': datetime.now().timestamp(),
            'stats_total_pnl': 0.0,
            'stats_win_streak': 0,
            'stats_loss_streak': 0,
            'stats_best_trade': 0.0,
            'stats_worst_trade': 0.0,
            'stats_total_wins': 0,
            'stats_total_losses': 0,
            'stats_conservative_trades': 0,
            'stats_fast_trades': 0,
            'stats_conservative_tp1_cancellations': 0,
            'stats_total_wins_pnl': 0.0,
            'stats_total_losses_pnl': 0.0,
            'stats_max_drawdown': 0.0,
            'stats_peak_equity': 0.0,
            'stats_current_drawdown': 0.0,
            'recent_trade_pnls': [],
            'bot_start_time': datetime.now().timestamp(),
            'overall_win_rate': 0.0,
            'ai_enabled': False,
            
            # Clear ALL monitoring data
            'chat_data': {},
            'monitor_tasks': {},  # Dashboard monitors
            'enhanced_tp_sl_monitors': {},  # Enhanced TP/SL monitors
            
            # Clear external stats
            'STATS_EXTERNAL_TRADES': 0,
            'STATS_EXTERNAL_PNL': 0.0,
            'STATS_EXTERNAL_WINS': 0,
            'STATS_EXTERNAL_LOSSES': 0
        },
        'callback_data': {}
    }
    
    # Save fresh data
    with open(persistence_file, 'wb') as f:
        pickle.dump(fresh_data, f)
    
    logger.info("   ✅ Persistence file cleared and reset to fresh state")
    logger.info("   ✅ All monitors cleared")
    logger.info("   ✅ All statistics reset")
    logger.info("   ✅ All chat data cleared")

def clear_all_backups():
    """Clear all backup pickle files"""
    logger.info("🗑️ Clearing all backup files...")
    
    backup_patterns = [
        "bybit_bot_dashboard_v4.1_enhanced.pkl.backup*",
        "*.pkl.backup*",
        "backup_*",
        "*_backup_*"
    ]
    
    cleared_count = 0
    for pattern in backup_patterns:
        for backup_file in Path('.').glob(pattern):
            # Skip the backup we just created
            if "backup_complete_cleanup_" in str(backup_file):
                continue
                
            if backup_file.is_file():
                try:
                    backup_file.unlink()
                    logger.info(f"   ✅ Removed: {backup_file}")
                    cleared_count += 1
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not remove {backup_file}: {e}")
    
    logger.info(f"   📊 Cleared {cleared_count} backup files")

def clear_trade_history():
    """Clear trade history data"""
    logger.info("🗑️ Clearing trade history...")
    
    trade_files = [
        "data/enhanced_trade_history.json",
        "data/trade_history.json",
        "data/*.json"
    ]
    
    cleared_count = 0
    for pattern in trade_files:
        for trade_file in Path('.').glob(pattern):
            if trade_file.is_file():
                try:
                    # Create empty JSON file
                    with open(trade_file, 'w') as f:
                        f.write('{"trades": {}}\n')
                    logger.info(f"   ✅ Cleared: {trade_file}")
                    cleared_count += 1
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not clear {trade_file}: {e}")
    
    logger.info(f"   📊 Cleared {cleared_count} trade history files")

def clear_logs():
    """Clear log files"""
    logger.info("🗑️ Clearing log files...")
    
    log_files = ["trading_bot.log", "trading_bot.log.*"]
    
    for pattern in log_files:
        for log_file in Path('.').glob(pattern):
            if log_file.is_file():
                try:
                    # Clear log content but keep the file
                    with open(log_file, 'w') as f:
                        f.write(f"# Log cleared for complete fresh start - {datetime.now()}\n")
                    logger.info(f"   ✅ Cleared: {log_file}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not clear {log_file}: {e}")

def clear_cache_and_temp():
    """Clear all cache and temporary data"""
    logger.info("🗑️ Clearing cache and temporary data...")
    
    cache_patterns = [
        "__pycache__",
        "**/__pycache__",
        "*.pyc",
        ".cache",
        "cache",
        "data/cache*",
        ".pytest_cache",
        "*.tmp",
        "temp_*",
        "tmp_*"
    ]
    
    cleared_count = 0
    for pattern in cache_patterns:
        for cache_item in Path('.').rglob(pattern):
            try:
                if cache_item.is_file():
                    cache_item.unlink()
                    cleared_count += 1
                elif cache_item.is_dir():
                    shutil.rmtree(cache_item)
                    cleared_count += 1
                logger.info(f"   ✅ Removed: {cache_item}")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not remove {cache_item}: {e}")
    
    logger.info(f"   📊 Cleared {cleared_count} cache items")

def clear_alert_data():
    """Clear alert system data"""
    logger.info("🗑️ Clearing alert data...")
    
    alert_files = [
        "alerts_data.pkl",
        "alerts_data.pkl.backup",
        "data/alerts_*"
    ]
    
    for pattern in alert_files:
        for alert_file in Path('.').glob(pattern):
            if alert_file.is_file():
                try:
                    alert_file.unlink()
                    logger.info(f"   ✅ Removed: {alert_file}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not remove {alert_file}: {e}")

def clear_monitor_signals():
    """Clear any monitor reload signals"""
    logger.info("🗑️ Clearing monitor signals...")
    
    signal_files = [
        "reload_enhanced_monitors.signal",
        "reload_monitors.signal",
        "*.signal"
    ]
    
    for pattern in signal_files:
        for signal_file in Path('.').glob(pattern):
            if signal_file.is_file():
                try:
                    signal_file.unlink()
                    logger.info(f"   ✅ Removed: {signal_file}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not remove {signal_file}: {e}")

def clear_stats_backups():
    """Clear stats backup files"""
    logger.info("🗑️ Clearing stats backups...")
    
    stats_patterns = [
        "stats_backup_*.json",
        "stats_*.pkl",
        "data/stats_*"
    ]
    
    for pattern in stats_patterns:
        for stats_file in Path('.').glob(pattern):
            if stats_file.is_file():
                try:
                    stats_file.unlink()
                    logger.info(f"   ✅ Removed: {stats_file}")
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not remove {stats_file}: {e}")

def verify_cleanup():
    """Verify the cleanup was successful"""
    logger.info("\n🔍 Verifying cleanup...")
    
    # Check persistence file
    pkl_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    if os.path.exists(pkl_file):
        with open(pkl_file, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        monitors = bot_data.get('monitor_tasks', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"   ✅ Persistence file exists")
        logger.info(f"   ✅ Monitor tasks: {len(monitors)} (should be 0)")
        logger.info(f"   ✅ Enhanced monitors: {len(enhanced_monitors)} (should be 0)")
        logger.info(f"   ✅ Total trades: {bot_data.get('stats_total_trades_initiated', 0)} (should be 0)")
        
        if len(monitors) == 0 and len(enhanced_monitors) == 0:
            logger.info("   ✅ All monitors successfully cleared!")
        else:
            logger.warning("   ⚠️ Some monitors may still exist!")
    else:
        logger.warning("   ⚠️ Persistence file not found!")

def complete_memory_cleanup():
    """Main function to perform complete memory cleanup"""
    logger.info("🧹 COMPLETE MEMORY STATE CLEANUP")
    logger.info("=" * 70)
    logger.info("This will clear ALL bot memory, monitors, and cached data")
    logger.info("=" * 70)
    
    try:
        # Step 1: Backup current data
        backup_dir = backup_before_cleanup()
        
        # Step 2: Clear persistence file (main memory)
        clear_persistence_file()
        
        # Step 3: Clear all backups
        clear_all_backups()
        
        # Step 4: Clear trade history
        clear_trade_history()
        
        # Step 5: Clear logs
        clear_logs()
        
        # Step 6: Clear cache and temp
        clear_cache_and_temp()
        
        # Step 7: Clear alert data
        clear_alert_data()
        
        # Step 8: Clear monitor signals
        clear_monitor_signals()
        
        # Step 9: Clear stats backups
        clear_stats_backups()
        
        # Step 10: Verify cleanup
        verify_cleanup()
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("🎉 COMPLETE MEMORY CLEANUP SUCCESS!")
        logger.info("=" * 70)
        logger.info("✅ All bot memory cleared")
        logger.info("✅ All monitors removed (0 active)")
        logger.info("✅ All statistics reset to zero")
        logger.info("✅ All persistence data cleared")
        logger.info("✅ All cache cleared")
        logger.info("✅ All temporary files removed")
        logger.info("✅ All trade history cleared")
        logger.info("✅ All logs cleared")
        logger.info("")
        logger.info(f"📦 Backup created: {backup_dir}")
        logger.info("")
        logger.info("🚀 Your bot now has completely clean memory!")
        logger.info("   • Start the bot with: python main.py")
        logger.info("   • All monitoring will start fresh")
        logger.info("   • All statistics will start from zero")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during memory cleanup: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🧹 COMPLETE MEMORY STATE CLEANUP")
    print("=" * 50)
    print("This will clear ALL bot memory, monitors, and data.")
    print("A backup will be created before clearing.")
    print("")
    print("✅ Proceeding with complete memory cleanup...")
    print("")
    
    success = complete_memory_cleanup()
    
    if success:
        print("\n🎊 Complete memory cleanup finished successfully!")
        print("Your bot now has a completely clean memory state.")
        print("Restart the bot for a fresh start.")
    else:
        print("\n❌ Memory cleanup failed. Check the logs above.")
        sys.exit(1)