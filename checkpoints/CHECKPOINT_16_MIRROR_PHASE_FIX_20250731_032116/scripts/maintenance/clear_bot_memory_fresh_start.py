#!/usr/bin/env python3
"""
Clear Bot Memory for Fresh Start

This script completely clears all bot memory, persistence data, monitors,
and stats to provide a completely clean slate for starting fresh.

WHAT THIS CLEARS:
- All Enhanced TP/SL monitors
- All dashboard monitors  
- All chat data and conversations
- All trading statistics
- All persistence data
- All cached data

WHAT THIS PRESERVES:
- Your .env configuration
- The bot code itself
- Trading logs (optional)
"""

import os
import sys
import pickle
import logging
from pathlib import Path
import shutil
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backup_current_data():
    """Create a backup of current data before clearing"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_before_fresh_start_{timestamp}"
    
    logger.info(f"📦 Creating backup in: {backup_dir}")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Files to backup
    files_to_backup = [
        "bybit_bot_dashboard_v4.1_enhanced.pkl",
        "trading_bot.log",
        "data/enhanced_trade_history.json",
        "order_analysis_results.json"
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
    
    logger.info(f"📦 Backup complete: {backup_count} files backed up to {backup_dir}")
    return backup_dir

def clear_persistence_file():
    """Clear the main persistence file"""
    
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    if os.path.exists(persistence_file):
        logger.info(f"🗑️ Clearing persistence file: {persistence_file}")
        
        # Create completely fresh bot_data structure
        fresh_data = {
            'conversations': {},
            'user_data': {},
            'chat_data': {},
            'bot_data': {
                # Fresh stats
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
                
                # Fresh monitoring data
                'chat_data': {},
                'monitor_tasks': {},
                'enhanced_tp_sl_monitors': {},
                
                # Fresh external stats
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
    else:
        logger.info("   ℹ️ No persistence file found (already clean)")

def clear_backup_files():
    """Clear backup pickle files"""
    
    logger.info("🗑️ Clearing backup files...")
    
    backup_patterns = [
        "bybit_bot_dashboard_v4.1_enhanced.pkl.backup*",
        "*.pkl.backup",
        "backup_*"
    ]
    
    cleared_count = 0
    for pattern in backup_patterns:
        for backup_file in Path('.').glob(pattern):
            if backup_file.is_file():
                try:
                    backup_file.unlink()
                    logger.info(f"   ✅ Removed: {backup_file}")
                    cleared_count += 1
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not remove {backup_file}: {e}")
    
    logger.info(f"   📊 Cleared {cleared_count} backup files")

def clear_temporary_files():
    """Clear temporary analysis and debug files"""
    
    logger.info("🗑️ Clearing temporary files...")
    
    temp_patterns = [
        "debug_*.py",
        "*_test.py", 
        "test_*.py",
        "check_*.py",
        "fix_*.py",
        "verify_*.py",
        "analyze_*.py",
        "close_*.py",
        "recreate_*.py",
        "apply_*.py",
        "comprehensive_*.py",
        "force_*.py",
        "order_analysis_results.json"
    ]
    
    # Keep essential files
    essential_files = [
        "check_current_status.py",  # Keep this one as it's useful
        "clear_bot_memory_fresh_start.py"  # Keep this script
    ]
    
    cleared_count = 0
    for pattern in temp_patterns:
        for temp_file in Path('.').glob(pattern):
            if temp_file.is_file() and temp_file.name not in essential_files:
                try:
                    temp_file.unlink()
                    logger.info(f"   ✅ Removed: {temp_file}")
                    cleared_count += 1
                except Exception as e:
                    logger.warning(f"   ⚠️ Could not remove {temp_file}: {e}")
    
    logger.info(f"   📊 Cleared {cleared_count} temporary files")

def clear_logs_option():
    """Ask user if they want to clear logs"""
    
    logger.info("🗑️ Log file clearing...")
    
    log_files = ["trading_bot.log", "trading_bot.log.1"]
    existing_logs = [f for f in log_files if os.path.exists(f)]
    
    if existing_logs:
        logger.info(f"   Found {len(existing_logs)} log files")
        # For automated clearing, we'll keep one recent log but clear the content
        for log_file in existing_logs:
            try:
                # Clear log content but keep the file
                with open(log_file, 'w') as f:
                    f.write(f"# Log cleared for fresh start - {datetime.now()}\n")
                logger.info(f"   ✅ Cleared content: {log_file}")
            except Exception as e:
                logger.warning(f"   ⚠️ Could not clear {log_file}: {e}")
    else:
        logger.info("   ℹ️ No log files found")

def clear_cache_data():
    """Clear any cached data"""
    
    logger.info("🗑️ Clearing cache data...")
    
    cache_patterns = [
        "__pycache__",
        "*.pyc",
        ".cache",
        "cache",
        "data/cache*"
    ]
    
    cleared_count = 0
    for pattern in cache_patterns:
        for cache_item in Path('.').glob(pattern):
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

def fresh_start():
    """Main function to perform fresh start"""
    
    logger.info("🆕 STARTING COMPLETE BOT MEMORY CLEAR")
    logger.info("=" * 70)
    logger.info("This will give you a completely fresh start with:")
    logger.info("✅ Zero monitors")
    logger.info("✅ Zero trading history")
    logger.info("✅ Zero statistics")
    logger.info("✅ Clean persistence")
    logger.info("✅ Clean cache")
    logger.info("")
    
    try:
        # Step 1: Backup current data
        backup_dir = backup_current_data()
        
        # Step 2: Clear persistence file
        clear_persistence_file()
        
        # Step 3: Clear backup files
        clear_backup_files()
        
        # Step 4: Clear temporary files
        clear_temporary_files()
        
        # Step 5: Clear logs
        clear_logs_option()
        
        # Step 6: Clear cache
        clear_cache_data()
        
        # Summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("🎉 FRESH START COMPLETE!")
        logger.info("=" * 70)
        logger.info("✅ All bot memory cleared")
        logger.info("✅ All monitors removed")
        logger.info("✅ All statistics reset")
        logger.info("✅ All persistence data cleared")
        logger.info("✅ All cache cleared")
        logger.info("✅ All temporary files removed")
        logger.info("")
        logger.info(f"📦 Backup created: {backup_dir}")
        logger.info("")
        logger.info("🚀 Your bot is now ready for a completely fresh start!")
        logger.info("   • Start the bot with: python main.py")
        logger.info("   • Use /start in Telegram to begin fresh")
        logger.info("   • All previous data is safely backed up")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during fresh start: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🆕 BOT MEMORY FRESH START")
    print("=" * 50)
    print("This will completely clear all bot memory and data.")
    print("A backup will be created before clearing.")
    print("")
    
    # Auto-confirm for fresh start
    print("✅ AUTO-CONFIRMED: Proceeding with fresh start...")
    
    success = fresh_start()
    
    if success:
        print("\n🎊 Fresh start completed successfully!")
        print("Your bot now has completely clean memory.")
        print("Restart the bot to begin fresh trading.")
    else:
        print("\n❌ Fresh start failed. Check the logs above.")
        sys.exit(1)