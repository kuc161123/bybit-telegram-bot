#!/usr/bin/env python3
"""
Complete fresh start - wipe all bot memory and data.
"""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def create_backup():
    """Create a backup of important files before wiping."""
    backup_dir = f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"📦 Creating backup in {backup_dir}...")
    os.makedirs(backup_dir, exist_ok=True)
    
    # Files to backup
    files_to_backup = [
        "bybit_bot_dashboard_v4.1_enhanced.pkl",
        "current_positions_trigger_prices.json",
        "data/enhanced_trade_history.json",
        "data/enhanced_trade_history_backup.json",
        "trading_bot.log",
        ".env"  # Important to keep API keys
    ]
    
    backed_up = 0
    for file in files_to_backup:
        if os.path.exists(file):
            try:
                if os.path.isfile(file):
                    shutil.copy2(file, backup_dir)
                else:
                    shutil.copytree(file, os.path.join(backup_dir, os.path.basename(file)))
                backed_up += 1
                print(f"   ✅ Backed up: {file}")
            except Exception as e:
                print(f"   ⚠️  Could not backup {file}: {e}")
    
    print(f"   Backed up {backed_up} files/directories")
    return backup_dir


def wipe_bot_memory():
    """Wipe all bot memory and data files."""
    
    print("\n🧹 COMPLETE BOT MEMORY WIPE")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Create backup first
    backup_dir = create_backup()
    
    print("\n⚠️  WARNING: This will delete all bot memory and data!")
    print("A backup has been created at:", backup_dir)
    
    # Auto-confirm for script execution
    print("\n✅ Proceeding with complete memory wipe...")
    
    print("\n🗑️  Wiping bot memory...")
    
    # Files to delete
    files_to_delete = [
        # Main bot state
        "bybit_bot_dashboard_v4.1_enhanced.pkl",
        "bybit_bot_dashboard_v4.1_enhanced.pkl.backup",
        
        # Trading logs
        "current_positions_trigger_prices.json",
        "CALCULATED_LIMIT_ORDERS.json",
        "position_balance_state.json",
        "order_recreation_results.json",
        "fresh_start_config.json",
        
        # Logs
        "trading_bot.log",
        "trading_bot.log.1",
        "bot_restart_log.txt",
        
        # Alert data
        "alerts_data.pkl",
        "alerts_data.pkl.backup",
        
        # Temporary files
        "COMPREHENSIVE_ORDER_REPORT.txt",
        "COMPREHENSIVE_ORDER_STRUCTURE.json",
        "ORIGINAL_TRIGGER_PRICES.md",
        "position_balance_report_*.txt"
    ]
    
    # Directories to clean
    dirs_to_clean = [
        "data",
        "__pycache__",
        "logs"
    ]
    
    deleted_files = 0
    
    # Delete individual files
    for file_pattern in files_to_delete:
        if '*' in file_pattern:
            # Handle wildcards
            for file in Path('.').glob(file_pattern):
                try:
                    os.remove(file)
                    deleted_files += 1
                    print(f"   ✅ Deleted: {file}")
                except Exception as e:
                    print(f"   ⚠️  Could not delete {file}: {e}")
        else:
            # Regular file
            if os.path.exists(file_pattern):
                try:
                    os.remove(file_pattern)
                    deleted_files += 1
                    print(f"   ✅ Deleted: {file_pattern}")
                except Exception as e:
                    print(f"   ⚠️  Could not delete {file_pattern}: {e}")
    
    # Clean directories
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            try:
                # For data directory, recreate it empty
                if dir_name == "data":
                    shutil.rmtree(dir_name)
                    os.makedirs(dir_name)
                    print(f"   ✅ Cleaned and recreated: {dir_name}/")
                else:
                    shutil.rmtree(dir_name)
                    print(f"   ✅ Deleted: {dir_name}/")
            except Exception as e:
                print(f"   ⚠️  Could not clean {dir_name}: {e}")
    
    # Create fresh data directory structure
    print("\n📁 Creating fresh directory structure...")
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    # Create empty trade history
    with open("data/enhanced_trade_history.json", "w") as f:
        import json
        json.dump({
            "trades": {},
            "metadata": {
                "version": "2.0",
                "created": datetime.now().isoformat(),
                "fresh_start": True
            }
        }, f, indent=2)
    print("   ✅ Created empty trade history")
    
    print(f"\n✅ Complete! Deleted {deleted_files} files")
    print("\n🎉 BOT MEMORY COMPLETELY WIPED!")
    print("\nThe bot is now in a clean state as if starting for the first time.")
    print("\nNext steps:")
    print("1. Start the bot with: python main.py")
    print("2. All positions will be treated as new")
    print("3. No historical data will influence decisions")
    print("4. Fresh trade logging will begin")
    print("\n⚠️  Note: Your API keys in .env are preserved")


def main():
    """Main function."""
    wipe_bot_memory()


if __name__ == "__main__":
    main()