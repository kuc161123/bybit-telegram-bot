# This is a patched version with account-aware monitor keys
# Import the original first
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from execution.enhanced_tp_sl_manager import *

# Patch the monitor_and_adjust_orders method
original_monitor_and_adjust_orders = EnhancedTPSLManager.monitor_and_adjust_orders

async def patched_monitor_and_adjust_orders(self, symbol: str, side: str):
    # First, try to find the monitor by looking for all possible keys
    main_key = f"{symbol}_{side}_main"
    mirror_key = f"{symbol}_{side}_mirror"
    legacy_key = f"{symbol}_{side}"  # For backward compatibility

    # Determine which key exists
    monitor_key = None
    account_type = 'main'

    if main_key in self.position_monitors:
        monitor_key = main_key
        account_type = 'main'
    elif mirror_key in self.position_monitors:
        monitor_key = mirror_key
        account_type = 'mirror'
    elif legacy_key in self.position_monitors:
        # Handle legacy monitors
        monitor_key = legacy_key
        monitor_data = self.position_monitors[legacy_key]
        account_type = monitor_data.get('account_type', 'main')

        # Migrate to new key format
        new_key = f"{symbol}_{side}_{account_type}"
        self.position_monitors[new_key] = monitor_data
        del self.position_monitors[legacy_key]
        monitor_key = new_key
        logger.info(f"Migrated monitor: {legacy_key} → {new_key}")

    if not monitor_key:
        return

    # Store account type in self for use by other methods
    self._current_account_type = account_type

    # Call original method
    await original_monitor_and_adjust_orders(self, symbol, side)

# Apply the patch
EnhancedTPSLManager.monitor_and_adjust_orders = patched_monitor_and_adjust_orders

# Also patch cleanup_position_orders to use account-aware keys
original_cleanup = EnhancedTPSLManager.cleanup_position_orders

async def patched_cleanup_position_orders(self, symbol: str, side: str, account_type: str = None):
    # Use stored account type if not provided
    if account_type is None:
        account_type = getattr(self, '_current_account_type', 'main')

    # Update monitor key to include account type
    monitor_key = f"{symbol}_{side}_{account_type}"

    # Check legacy key too
    legacy_key = f"{symbol}_{side}"
    if legacy_key in self.position_monitors and monitor_key not in self.position_monitors:
        monitor_key = legacy_key

    # Store the key temporarily
    self._cleanup_monitor_key = monitor_key

    # Call original
    await original_cleanup(self, symbol, side)

EnhancedTPSLManager.cleanup_position_orders = patched_cleanup_position_orders
