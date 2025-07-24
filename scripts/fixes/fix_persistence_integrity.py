#!/usr/bin/env python3
"""
Fix persistence integrity issues by cleaning up the pickle file
and implementing better error handling
"""
import pickle
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_backup(pkl_path: str) -> str:
    """Create a backup of the pickle file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{pkl_path}.backup_{timestamp}"
    shutil.copy2(pkl_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    return backup_path

def clean_data_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and validate the data structure"""
    # Ensure all required top-level keys exist
    required_keys = ['conversations', 'user_data', 'chat_data', 'bot_data', 'callback_data']
    for key in required_keys:
        if key not in data:
            data[key] = {}
            logger.info(f"Added missing key: {key}")
    
    # Clean bot_data
    bot_data = data.get('bot_data', {})
    
    # Ensure monitor structures exist
    if 'enhanced_tp_sl_monitors' not in bot_data:
        bot_data['enhanced_tp_sl_monitors'] = {}
        logger.info("Added missing enhanced_tp_sl_monitors")
    
    if 'monitor_tasks' not in bot_data:
        bot_data['monitor_tasks'] = {}
        logger.info("Added missing monitor_tasks")
    
    # Remove any corrupted monitor entries
    enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
    corrupted_monitors = []
    
    for key, monitor in enhanced_monitors.items():
        # Check for required fields
        required_fields = ['symbol', 'side', 'position_size', 'entry_price']
        if not all(field in monitor for field in required_fields):
            corrupted_monitors.append(key)
            logger.warning(f"Found corrupted monitor: {key}")
    
    # Remove corrupted monitors
    for key in corrupted_monitors:
        del enhanced_monitors[key]
        logger.info(f"Removed corrupted monitor: {key}")
    
    # Clean monitor_tasks
    monitor_tasks = bot_data.get('monitor_tasks', {})
    corrupted_tasks = []
    
    for key, task in monitor_tasks.items():
        # Check for required fields
        required_fields = ['symbol', 'chat_id']
        if not all(field in task for field in required_fields):
            corrupted_tasks.append(key)
            logger.warning(f"Found corrupted monitor task: {key}")
        # Ensure chat_id is not None
        elif task.get('chat_id') is None:
            corrupted_tasks.append(key)
            logger.warning(f"Found monitor task with None chat_id: {key}")
    
    # Remove corrupted tasks
    for key in corrupted_tasks:
        del monitor_tasks[key]
        logger.info(f"Removed corrupted monitor task: {key}")
    
    # Ensure stats exist with proper defaults
    stats_keys = {
        'stats_total_trades_initiated': 0,
        'stats_tp1_hits': 0,
        'stats_sl_hits': 0,
        'stats_other_closures': 0,
        'stats_last_reset_timestamp': 0,
        'stats_total_pnl': 0.0,
        'stats_win_streak': 0,
        'stats_loss_streak': 0,
        'stats_best_trade': {'symbol': '', 'pnl': 0.0},
        'stats_worst_trade': {'symbol': '', 'pnl': 0.0},
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
        'recent_trade_pnls': []
    }
    
    for key, default in stats_keys.items():
        if key not in bot_data:
            bot_data[key] = default
            logger.info(f"Added missing stat: {key}")
    
    return data

def validate_pickle_file(pkl_path: str) -> bool:
    """Validate the pickle file can be loaded and saved"""
    try:
        # Try to load
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Try to save to a temp file
        temp_path = pkl_path + '.temp'
        with open(temp_path, 'wb') as f:
            pickle.dump(data, f)
        
        # If successful, remove temp file
        os.remove(temp_path)
        return True
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return False

def fix_persistence_integrity():
    """Main function to fix persistence integrity issues"""
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        # Create backup first
        backup_path = create_backup(pkl_path)
        
        # Load data
        logger.info("Loading pickle file...")
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        logger.info("Cleaning data structure...")
        cleaned_data = clean_data_structure(data)
        
        # Save cleaned data
        logger.info("Saving cleaned data...")
        with open(pkl_path, 'wb') as f:
            pickle.dump(cleaned_data, f)
        
        # Validate the file
        if validate_pickle_file(pkl_path):
            logger.info("✅ Persistence file integrity restored!")
            
            # Clean up old backups (keep only last 5)
            backup_files = sorted([f for f in os.listdir('.') if f.startswith(pkl_path + '.backup_')])
            if len(backup_files) > 5:
                for old_backup in backup_files[:-5]:
                    os.remove(old_backup)
                    logger.info(f"Removed old backup: {old_backup}")
        else:
            # Restore from backup if validation fails
            logger.error("Validation failed, restoring from backup...")
            shutil.copy2(backup_path, pkl_path)
            logger.info("Restored from backup")
            
    except Exception as e:
        logger.error(f"Error fixing persistence integrity: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_persistence_integrity()