#!/usr/bin/env python3
"""
Automatically apply chat ID fixes for 5 specific monitors.
Based on fix_missing_chat_ids_safe.py but runs without prompts.
Uses file locking, atomic writes, and comprehensive error handling.
"""

import os
import sys
import pickle
import shutil
import fcntl
import time
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('apply_chat_id_fix_now.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
PICKLE_FILE = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
CHAT_ID = 5634913742
MONITORS_TO_FIX = [
    'AUCTIONUSDT_Buy_main',
    'AUCTIONUSDT_Buy_mirror',
    'CRVUSDT_Buy_mirror',
    'SEIUSDT_Buy_mirror',
    'ARBUSDT_Buy_mirror'
]

# Signal files to create
SIGNAL_FILES = [
    'reload_monitors.signal',
    'force_reload.trigger',
    'monitor_reload_trigger.signal',
    '.reload_enhanced_monitors'
]


class PickleFixer:
    def __init__(self):
        """Initialize in live mode - no dry run."""
        self.pickle_path = Path(PICKLE_FILE)
        self.lock_file = None
        self.backup_path = None
        
    def __enter__(self):
        """Context manager entry - acquire lock."""
        logger.info("Acquiring file lock...")
        self.lock_file = open(f"{PICKLE_FILE}.lock", 'w')
        try:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info("✓ File lock acquired")
            return self
        except IOError:
            logger.error("✗ Could not acquire lock - another process may be using the file")
            raise
            
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release lock."""
        if self.lock_file:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()
            try:
                os.remove(f"{PICKLE_FILE}.lock")
            except:
                pass
            logger.info("✓ File lock released")
            
    def create_backup(self) -> str:
        """Create timestamped backup of pickle file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        backup_path = f"{PICKLE_FILE}.backup_fix_chat_ids_{timestamp}"
        
        logger.info(f"Creating backup: {backup_path}")
        try:
            shutil.copy2(self.pickle_path, backup_path)
            self.backup_path = backup_path
            logger.info(f"✓ Backup created successfully")
            return backup_path
        except Exception as e:
            logger.error(f"✗ Failed to create backup: {e}")
            raise
            
    def load_data(self) -> Dict[str, Any]:
        """Load pickle data with error handling."""
        logger.info("Loading pickle data...")
        try:
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)
            logger.info("✓ Pickle data loaded successfully")
            return data
        except Exception as e:
            logger.error(f"✗ Failed to load pickle: {e}")
            raise
            
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate pickle data structure."""
        logger.info("Validating data structure...")
        
        # Check for required keys
        if 'bot_data' not in data:
            logger.error("✗ Missing 'bot_data' key")
            return False
            
        bot_data = data['bot_data']
        
        if 'enhanced_tp_sl_monitors' not in bot_data:
            logger.error("✗ Missing 'enhanced_tp_sl_monitors' key")
            return False
            
        monitors = bot_data['enhanced_tp_sl_monitors']
        
        if not isinstance(monitors, dict):
            logger.error("✗ enhanced_tp_sl_monitors is not a dict")
            return False
            
        logger.info(f"✓ Data structure valid - found {len(monitors)} monitors")
        return True
        
    def find_monitors_to_fix(self, data: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
        """Find the specific monitors that need fixing."""
        logger.info("Finding monitors to fix...")
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        to_fix = []
        
        for monitor_key in MONITORS_TO_FIX:
            if monitor_key in monitors:
                monitor = monitors[monitor_key]
                current_chat_id = monitor.get('chat_id')
                
                if current_chat_id == CHAT_ID:
                    logger.info(f"  • {monitor_key}: Already has correct chat_id")
                else:
                    logger.info(f"  • {monitor_key}: Needs update (current: {current_chat_id})")
                    to_fix.append((monitor_key, monitor))
            else:
                logger.warning(f"  • {monitor_key}: NOT FOUND in monitors")
                
        logger.info(f"Found {len(to_fix)} monitors that need fixing")
        return to_fix
        
    def apply_fixes(self, data: Dict[str, Any], monitors_to_fix: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Apply chat_id fixes to monitors."""
        logger.info("Applying fixes...")
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        
        for monitor_key, monitor in monitors_to_fix:
            old_chat_id = monitor.get('chat_id')
            monitors[monitor_key]['chat_id'] = CHAT_ID
            logger.info(f"  ✓ Updated {monitor_key}: {old_chat_id} -> {CHAT_ID}")
            
        return data
        
    def save_data_atomic(self, data: Dict[str, Any]) -> None:
        """Save pickle data atomically using temp file + rename."""
        logger.info("Saving data atomically...")
        
        # Create temp file in same directory
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.pickle_path.parent,
            prefix='.tmp_',
            suffix='.pkl'
        )
        
        try:
            # Write to temp file
            with os.fdopen(temp_fd, 'wb') as f:
                pickle.dump(data, f)
                
            # Sync to disk
            os.fsync(temp_fd)
            
            # Atomic rename
            os.rename(temp_path, self.pickle_path)
            logger.info("✓ Data saved successfully")
            
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except:
                pass
            logger.error(f"✗ Failed to save data: {e}")
            raise
            
    def create_signal_files(self) -> None:
        """Create signal files to trigger monitor reload."""
        logger.info("Creating signal files...")
        
        for signal_file in SIGNAL_FILES:
            try:
                Path(signal_file).touch()
                logger.info(f"  ✓ Created {signal_file}")
            except Exception as e:
                logger.warning(f"  ✗ Failed to create {signal_file}: {e}")
                
    def verify_fixes(self, data: Dict[str, Any]) -> bool:
        """Verify that fixes were applied correctly."""
        logger.info("Verifying fixes...")
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        all_correct = True
        
        for monitor_key in MONITORS_TO_FIX:
            if monitor_key in monitors:
                chat_id = monitors[monitor_key].get('chat_id')
                if chat_id == CHAT_ID:
                    logger.info(f"  ✓ {monitor_key}: chat_id = {chat_id}")
                else:
                    logger.error(f"  ✗ {monitor_key}: chat_id = {chat_id} (expected {CHAT_ID})")
                    all_correct = False
            else:
                logger.error(f"  ✗ {monitor_key}: NOT FOUND")
                all_correct = False
                
        return all_correct
        
    def run(self) -> bool:
        """Main execution flow."""
        try:
            logger.info("LIVE RUN - Starting automatic chat ID fix")
            logger.info(f"Target monitors: {', '.join(MONITORS_TO_FIX)}")
            logger.info(f"Target chat_id: {CHAT_ID}")
            
            # Create backup
            self.create_backup()
                
            # Load and validate data
            data = self.load_data()
            if not self.validate_data(data):
                logger.error("✗ Data validation failed")
                return False
                
            # Find monitors to fix
            monitors_to_fix = self.find_monitors_to_fix(data)
            
            if not monitors_to_fix:
                logger.info("✓ No monitors need fixing")
                return True
                
            # Apply fixes
            logger.info(f"Applying changes to {len(monitors_to_fix)} monitors...")
            data = self.apply_fixes(data, monitors_to_fix)
            
            # Save atomically
            self.save_data_atomic(data)
            
            # Verify
            if not self.verify_fixes(data):
                logger.error("✗ Verification failed!")
                return False
                
            # Create signal files
            self.create_signal_files()
            
            logger.info("✓ Fix completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}", exc_info=True)
            return False


def main():
    """Main entry point."""
    print("\n" + "="*60)
    print("AUTOMATIC CHAT ID FIX - LIVE MODE")
    print("="*60 + "\n")
    
    logger.info("Starting automatic chat ID fix...")
    logger.info(f"Will fix {len(MONITORS_TO_FIX)} monitors to use chat_id {CHAT_ID}")
    
    # Check if pickle file exists
    if not os.path.exists(PICKLE_FILE):
        logger.error(f"✗ Pickle file not found: {PICKLE_FILE}")
        sys.exit(1)
        
    # Run the fixer
    try:
        with PickleFixer() as fixer:
            success = fixer.run()
            
        if success:
            logger.info("\n✅ Script completed successfully")
            if fixer.backup_path:
                logger.info(f"Backup saved at: {fixer.backup_path}")
            logger.info("Signal files created - bot should reload monitors on next cycle")
        else:
            logger.error("\n❌ Script failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()