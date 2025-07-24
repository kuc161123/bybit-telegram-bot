#!/usr/bin/env python3
"""
Fresh Start Script - Cleans all bot memory and state for a complete restart.
This will:
1. Backup existing data
2. Clear all persistence files
3. Clear all monitoring states
4. Reset trade history
5. Prepare for a fresh start
"""

import os
import shutil
import json
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Files and directories to clean
PERSISTENCE_FILES = [
    "bybit_bot_dashboard_v4.1_enhanced.pkl",
    "alerts_data.pkl",
    "bybit_bot_dashboard_v4.1_enhanced.pkl.backup",
    "monitor_restart_config.json",
    "monitor_restart_status.json"
]

CACHE_FILES = [
    "data/cache/*",
    "data/temp/*"
]

LOG_FILES = [
    "trading_bot.log",
    "trading_bot.log.*",
    "monitor_restart.log",
    "recreate_orders.log",
    "order_investigation_detailed.log"
]

TRADE_HISTORY_FILES = [
    "data/trade_history.json",
    "data/enhanced_trade_history.json",
    "data/trade_history_*.json",
    "data/trade_archives/*"
]

BACKUP_DIR = "backups"

def create_backup():
    """Create a timestamped backup of all important files."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
    
    # Create backup directory
    Path(backup_path).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Creating backup at: {backup_path}")
    
    # Backup persistence files
    for file in PERSISTENCE_FILES:
        if os.path.exists(file):
            try:
                shutil.copy2(file, os.path.join(backup_path, file))
                logger.info(f"  ✅ Backed up: {file}")
            except Exception as e:
                logger.error(f"  ❌ Failed to backup {file}: {e}")
    
    # Backup data directory
    if os.path.exists("data"):
        try:
            shutil.copytree("data", os.path.join(backup_path, "data"), dirs_exist_ok=True)
            logger.info(f"  ✅ Backed up: data directory")
        except Exception as e:
            logger.error(f"  ❌ Failed to backup data directory: {e}")
    
    # Create backup info file
    info = {
        "timestamp": timestamp,
        "datetime": datetime.now().isoformat(),
        "files_backed_up": os.listdir(backup_path)
    }
    
    with open(os.path.join(backup_path, "backup_info.json"), 'w') as f:
        json.dump(info, f, indent=2)
    
    logger.info(f"✅ Backup completed: {backup_path}")
    return backup_path

def clean_persistence_files():
    """Remove all persistence files."""
    logger.info("\n🧹 Cleaning persistence files...")
    
    for file in PERSISTENCE_FILES:
        if os.path.exists(file):
            try:
                os.remove(file)
                logger.info(f"  ✅ Removed: {file}")
            except Exception as e:
                logger.error(f"  ❌ Failed to remove {file}: {e}")

def clean_log_files():
    """Clean log files."""
    logger.info("\n📄 Cleaning log files...")
    
    import glob
    for pattern in LOG_FILES:
        for file in glob.glob(pattern):
            try:
                os.remove(file)
                logger.info(f"  ✅ Removed: {file}")
            except Exception as e:
                logger.error(f"  ❌ Failed to remove {file}: {e}")

def clean_trade_history():
    """Clean existing trade history files."""
    logger.info("\n📈 Cleaning trade history...")
    
    import glob
    for pattern in TRADE_HISTORY_FILES:
        for file in glob.glob(pattern):
            try:
                if os.path.isfile(file):
                    os.remove(file)
                    logger.info(f"  ✅ Removed: {file}")
                elif os.path.isdir(file):
                    shutil.rmtree(file)
                    logger.info(f"  ✅ Removed directory: {file}")
            except Exception as e:
                logger.error(f"  ❌ Failed to remove {file}: {e}")
    
    # Ensure trade archives directory is clean
    archives_dir = "data/trade_archives"
    if os.path.exists(archives_dir):
        try:
            shutil.rmtree(archives_dir)
            logger.info(f"  ✅ Cleaned trade archives directory")
        except Exception as e:
            logger.error(f"  ❌ Failed to clean archives: {e}")
    Path(archives_dir).mkdir(parents=True, exist_ok=True)

def reset_trade_history():
    """Reset trade history but keep structure."""
    logger.info("\n📊 Resetting trade history...")
    
    # Ensure data directory exists
    Path("data").mkdir(parents=True, exist_ok=True)
    
    # Create fresh trade history file
    fresh_history = {
        "trades": {},
        "metadata": {
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "fresh_start": True,
            "note": "Fresh start after fixes applied"
        }
    }
    
    # Save both regular and enhanced history
    for filename in ["trade_history.json", "enhanced_trade_history.json"]:
        filepath = os.path.join("data", filename)
        try:
            with open(filepath, 'w') as f:
                json.dump(fresh_history, f, indent=2)
            logger.info(f"  ✅ Created fresh: {filepath}")
        except Exception as e:
            logger.error(f"  ❌ Failed to create {filepath}: {e}")

def create_fresh_config():
    """Create fresh configuration file."""
    logger.info("\n⚙️  Creating fresh configuration...")
    
    config = {
        "fresh_start": True,
        "timestamp": datetime.now().isoformat(),
        "settings": {
            "enhanced_logging": True,
            "log_all_orders": True,
            "log_limit_orders": True,
            "comprehensive_tracking": True,
            "track_order_modifications": True,
            "track_cancellations": True,
            "track_rebalances": True
        },
        "fixes_applied": [
            "Conservative rebalancer position size check",
            "TP1 execution verification",
            "Limit order fill rebalancing",
            "Order recreation loop prevention"
        ]
    }
    
    try:
        with open("fresh_start_config.json", 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"  ✅ Created fresh configuration")
    except Exception as e:
        logger.error(f"  ❌ Failed to create config: {e}")

def clean_cache_files():
    """Clean cache files."""
    logger.info("\n💾 Cleaning cache files...")
    
    # Clean cache directory
    cache_dir = "data/cache"
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"  ✅ Cleaned cache directory")
        except Exception as e:
            logger.error(f"  ❌ Failed to clean cache: {e}")

def verify_environment():
    """Verify environment is ready for fresh start."""
    logger.info("\n🔍 Verifying environment...")
    
    # Check .env file exists
    if os.path.exists(".env"):
        logger.info("  ✅ .env file found")
    else:
        logger.error("  ❌ .env file not found - bot won't start without it!")
    
    # Check required directories
    for dir_path in ["data", "logs", "backups"]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"  ✅ Directory ready: {dir_path}")
    
    # Check main.py exists
    if os.path.exists("main.py"):
        logger.info("  ✅ main.py found")
    else:
        logger.error("  ❌ main.py not found!")

def main():
    """Main function to perform fresh start."""
    print("\n" + "="*80)
    print("FRESH START - COMPLETE BOT RESET")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n⚠️  WARNING: This will reset ALL bot memory and state!")
    print("\nThis will:")
    print("1. Backup all existing data")
    print("2. Clear all persistence files")
    print("3. Reset trade history")
    print("4. Clean all caches and logs")
    print("5. Prepare for a completely fresh start")
    
    # Confirm action
    response = input("\nDo you want to continue? Type 'YES' to confirm: ")
    if response != "YES":
        print("❌ Operation cancelled")
        return
    
    # Create backup first
    backup_path = create_backup()
    
    # Clean everything
    clean_persistence_files()
    clean_log_files()
    clean_trade_history()  # Clean existing trade history first
    clean_cache_files()
    reset_trade_history()  # Then create fresh trade history
    create_fresh_config()
    
    # Verify environment
    verify_environment()
    
    # Summary
    print("\n" + "="*80)
    print("FRESH START COMPLETE")
    print("="*80)
    print(f"\n✅ Backup saved to: {backup_path}")
    print("\n📋 Next steps:")
    print("1. Start the bot: python main.py")
    print("2. The bot will start with completely fresh memory")
    print("3. All trades will be logged comprehensively including:")
    print("   - All limit orders")
    print("   - All TP/SL orders")
    print("   - All order modifications")
    print("   - All cancellations")
    print("   - All rebalances")
    print("   - Complete position lifecycle")
    print("\n🔧 Fixes applied:")
    print("   ✅ Conservative rebalancer position size validation")
    print("   ✅ TP1 execution verification (85% close)")
    print("   ✅ Limit order fill rebalancing")
    print("   ✅ Order recreation loop prevention")
    print("\n📊 Enhanced logging enabled:")
    print("   ✅ Comprehensive trade history")
    print("   ✅ All order events tracked")
    print("   ✅ Performance metrics")
    print("   ✅ Risk management data")
    print("\n🚀 Ready for fresh start!")

if __name__ == "__main__":
    main()