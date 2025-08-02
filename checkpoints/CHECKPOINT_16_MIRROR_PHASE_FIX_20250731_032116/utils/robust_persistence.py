#!/usr/bin/env python3
"""
Robust Persistence Manager - Ensures reliable trade and monitor storage
Features:
- Atomic operations with rollback capability
- Automatic cleanup when positions close
- Data integrity with checksums
- Monitor lifecycle management
- Comprehensive error recovery
"""

import os
import pickle
import json
import hashlib
import logging
import asyncio
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from pathlib import Path
import shutil
from decimal import Decimal
from utils.pickle_lock import PickleFileLock
from utils.optimized_pickle_persistence import get_optimized_persistence, mark_data_dirty

logger = logging.getLogger(__name__)

# Configuration
PERSISTENCE_FILE = "bybit_bot_dashboard_v4.1_enhanced.pkl"
BACKUP_DIR = "data/persistence_backups"
MAX_BACKUPS = 10
CHECKSUM_FILE = ".persistence_checksum"
LOCK_TIMEOUT = 30  # seconds
INTEGRITY_CHECK_INTERVAL = 300  # 5 minutes

class RobustPersistenceManager:
    """
    Centralized persistence manager with atomic operations and integrity checks
    """

    def __init__(self, filepath: str = PERSISTENCE_FILE):
        self.filepath = filepath
        self.backup_dir = Path(BACKUP_DIR)
        self._last_backup_time = {}  # Track backup times by operation
        self._backup_interval = 900  # 15 minutes between backups
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Use PickleFileLock for safe operations
        self._pickle_lock = PickleFileLock(filepath)
        
        # Initialize optimized persistence system
        self._optimized_persistence = get_optimized_persistence(filepath)
        self._use_optimized = True  # Enable optimized persistence by default

        # Locks for thread-safety
        self._write_lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()

        # Transaction tracking
        self._transaction_id = None
        self._transaction_backup = None

        # Integrity tracking
        self._last_checksum = None
        self._last_integrity_check = 0

        # Monitor registry for lifecycle management
        self._monitor_registry = {}  # monitor_key -> {"created": timestamp, "position": {...}}

        # Operation history for debugging
        self._operation_history = []
        self._max_history = 100

        # Initialize with integrity check
        self._initialize()

    def _initialize(self):
        """Initialize persistence manager and verify integrity"""
        try:
            if os.path.exists(self.filepath):
                # Verify existing file
                if not self._verify_integrity():
                    logger.debug("Initial integrity check failed, attempting recovery...")
                    self._recover_from_backup()
                else:
                    logger.debug("✅ Persistence file integrity verified")
            else:
                # Create new persistence file
                self._create_new_persistence()
                logger.info("✅ Created new persistence file")

        except Exception as e:
            logger.error(f"Error initializing persistence: {e}")
            self._create_new_persistence()

    def _create_empty_data(self):
        """Create empty data structure"""
        return {
            'conversations': {},
            'user_data': {},
            'chat_data': {},
            'bot_data': {}
        }

    def _create_new_persistence(self):
        """Create a new, clean persistence file"""
        fresh_data = {
            'conversations': {},
            'user_data': {},
            'chat_data': {},
            'bot_data': {
                'stats_total_trades_initiated': 0,
                'stats_tp1_hits': 0,
                'stats_sl_hits': 0,
                'stats_other_closures': 0,
                'stats_last_reset_timestamp': time.time(),
                'stats_total_pnl': 0.0,
                'stats_win_streak': 0,
                'stats_loss_streak': 0,
                'stats_best_trade': 0.0,
                'stats_worst_trade': 0.0,
                'stats_total_wins': 0,
                'stats_total_losses': 0,
                'stats_conservative_trades': 0,
                'stats_fast_trades_removed': 0,
                'stats_conservative_tp1_cancellations': 0,
                'stats_total_wins_pnl': 0.0,
                'stats_total_losses_pnl': 0.0,
                'stats_max_drawdown': 0.0,
                'stats_peak_equity': 0.0,
                'stats_current_drawdown': 0.0,
                'recent_trade_pnls': [],
                'bot_start_time': time.time(),
                'overall_win_rate': 0.0,
                'ai_enabled': False,
                'chat_data': {},
                'monitor_tasks': {},
                'enhanced_tp_sl_monitors': {},
                'STATS_EXTERNAL_TRADES': 0,
                'STATS_EXTERNAL_PNL': 0.0,
                'STATS_EXTERNAL_WINS': 0,
                'STATS_EXTERNAL_LOSSES': 0
            },
            'callback_data': {}
        }

        with open(self.filepath, 'wb') as f:
            pickle.dump(fresh_data, f)

        self._update_checksum()

    def _calculate_checksum(self, data: Any = None) -> str:
        """Calculate SHA256 checksum of data or file"""
        if data is not None:
            # Calculate checksum of data object
            data_str = str(sorted(str(data).encode()))
            return hashlib.sha256(data_str.encode()).hexdigest()
        else:
            # Calculate checksum of file
            sha256_hash = hashlib.sha256()
            with open(self.filepath, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()

    def _update_checksum(self):
        """Update stored checksum"""
        try:
            checksum = self._calculate_checksum()
            with open(CHECKSUM_FILE, 'w') as f:
                json.dump({
                    "checksum": checksum,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "filepath": self.filepath
                }, f)
            self._last_checksum = checksum
        except Exception as e:
            logger.error(f"Error updating checksum: {e}")

    def _verify_integrity(self) -> bool:
        """Verify file integrity using checksum"""
        try:
            # If pickle file doesn't exist, nothing to verify
            if not os.path.exists(self.filepath):
                return True
                
            # If checksum file doesn't exist, create it
            if not os.path.exists(CHECKSUM_FILE):
                self._update_checksum()
                return True

            # Try to read checksum file
            try:
                with open(CHECKSUM_FILE, 'r') as f:
                    checksum_data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                # Checksum file is corrupted or missing, recreate it
                logger.warning("Checksum file corrupted or missing, recreating...")
                self._update_checksum()
                return True

            stored_checksum = checksum_data.get("checksum")
            if not stored_checksum:
                # Invalid checksum data, recreate
                self._update_checksum()
                return True
                
            current_checksum = self._calculate_checksum()

            # If checksums don't match, it might be due to a recent write
            # Check if the file is still valid by trying to load it
            if stored_checksum != current_checksum:
                try:
                    # Try to load the pickle file to verify it's not corrupted
                    with open(self.filepath, 'rb') as f:
                        pickle.load(f)
                    # File is valid, update checksum
                    logger.debug("Checksum mismatch but file is valid, updating checksum...")
                    self._update_checksum()
                    return True
                except Exception:
                    # File is corrupted
                    logger.error("Checksum mismatch and file is corrupted")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error verifying integrity: {e}")
            # In case of error, try to load the file directly
            try:
                with open(self.filepath, 'rb') as f:
                    pickle.load(f)
                return True  # File is loadable
            except Exception:
                return False  # File is corrupted

    async def begin_transaction(self) -> str:
        """Begin atomic transaction with automatic rollback on failure"""
        async with self._write_lock:
            try:
                # Generate transaction ID
                self._transaction_id = f"txn_{int(time.time())}_{os.getpid()}"

                # Create transaction backup
                backup_path = self.backup_dir / f"transaction_{self._transaction_id}.pkl"
                shutil.copy2(self.filepath, backup_path)
                self._transaction_backup = backup_path

                self._log_operation("begin_transaction", {"id": self._transaction_id})
                return self._transaction_id

            except Exception as e:
                logger.error(f"Error beginning transaction: {e}")
                raise

    async def commit_transaction(self, transaction_id: str):
        """Commit transaction and update integrity"""
        if transaction_id != self._transaction_id:
            raise ValueError(f"Invalid transaction ID: {transaction_id}")

        try:
            # Update checksum for new state
            self._update_checksum()

            # Clean up transaction backup
            if self._transaction_backup and self._transaction_backup.exists():
                self._transaction_backup.unlink()

            self._log_operation("commit_transaction", {"id": transaction_id})

            # Reset transaction state
            self._transaction_id = None
            self._transaction_backup = None

        except Exception as e:
            logger.error(f"Error committing transaction: {e}")
            await self.rollback_transaction(transaction_id)
            raise

    async def rollback_transaction(self, transaction_id: str):
        """Rollback transaction to previous state"""
        if transaction_id != self._transaction_id:
            raise ValueError(f"Invalid transaction ID: {transaction_id}")

        try:
            if self._transaction_backup and self._transaction_backup.exists():
                # Restore from backup
                shutil.copy2(self._transaction_backup, self.filepath)
                self._transaction_backup.unlink()

                # Restore checksum
                self._update_checksum()

                self._log_operation("rollback_transaction", {"id": transaction_id})

            # Reset transaction state
            self._transaction_id = None
            self._transaction_backup = None

        except Exception as e:
            logger.error(f"Error rolling back transaction: {e}")
            raise

    async def read_data(self) -> Dict:
        """Read data with integrity check and safe locking"""
        async with self._read_lock:
            try:
                # Periodic integrity check
                if time.time() - self._last_integrity_check > INTEGRITY_CHECK_INTERVAL:
                    if not self._verify_integrity():
                        logger.debug("Integrity check failed during read, using safe_load")
                        # Use safe_load which handles recovery
                        return self._pickle_lock.safe_load()
                    self._last_integrity_check = time.time()

                # Use safe_load for all reads
                data = self._pickle_lock.safe_load()
                return data

            except Exception as e:
                logger.error(f"Error reading data: {e}")
                # Return empty data structure on error
                return self._create_empty_data()

    async def write_data(self, data: Dict, transaction_id: Optional[str] = None):
        """Write data with atomic operation and safe locking"""
        if transaction_id and transaction_id != self._transaction_id:
            raise ValueError(f"Invalid transaction ID: {transaction_id}")

        async with self._write_lock:
            try:
                # Create backup if not in transaction AND forced
                if not transaction_id and getattr(self, '_force_backup', False):
                    await self._create_backup("write")
                    self._force_backup = False

                # Use safe_save for atomic write
                success = self._pickle_lock.safe_save(data)

                if not success:
                    raise Exception("Failed to save data with safe_save")

                # Update checksum if not in transaction
                if not transaction_id:
                    self._update_checksum()

                self._log_operation("write_data", {"transaction": transaction_id})

            except Exception as e:
                logger.error(f"Error writing data: {e}")
                if not transaction_id:
                    self._recover_from_backup()
                raise
    
    async def write_data_optimized(self, data: Dict, force: bool = False, mark_dirty_keys: List[str] = None):
        """
        Write data using optimized persistence with dirty flags and batch writes
        Based on 2025 best practices for high-performance pickle operations
        
        Args:
            data: Data to save
            force: Force immediate save (bypass batching)
            mark_dirty_keys: Keys to mark as dirty for priority batching
        """
        async with self._write_lock:
            try:
                # Use optimized persistence system
                success = await self._optimized_persistence.save_data(data, force=force)
                
                # Mark specified keys as dirty for priority batching
                if mark_dirty_keys:
                    mark_data_dirty(*mark_dirty_keys)
                
                # Auto-mark critical trading data as dirty
                if 'bot_data' in data:
                    bot_data = data['bot_data']
                    critical_keys = []
                    
                    if 'enhanced_tp_sl_monitors' in bot_data:
                        critical_keys.append('enhanced_tp_sl_monitors')
                    if 'monitor_tasks' in bot_data:
                        critical_keys.append('monitor_tasks')
                    if 'positions' in bot_data:
                        critical_keys.append('positions')
                    
                    if critical_keys:
                        mark_data_dirty(*critical_keys)
                
                if not success:
                    raise Exception("Failed to save data with optimized persistence")
                
                # Update checksum for integrity verification
                self._update_checksum()
                
                self._log_operation("write_data_optimized", {
                    "force": force, 
                    "dirty_keys": mark_dirty_keys or [],
                    "optimized": True
                })
                
                return success
                
            except Exception as e:
                logger.error(f"Error writing data with optimized persistence: {e}")
                # Fallback to traditional method
                try:
                    logger.info("🔄 Falling back to traditional persistence method")
                    success = self._pickle_lock.safe_save(data)
                    if success:
                        self._update_checksum()
                        return True
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback persistence also failed: {fallback_error}")
                
                self._recover_from_backup()
                raise
    
    async def start_optimized_persistence(self):
        """Start the optimized persistence system"""
        try:
            await self._optimized_persistence.start()
            logger.info("🚀 Optimized persistence system started")
        except Exception as e:
            logger.error(f"❌ Failed to start optimized persistence: {e}")
            self._use_optimized = False
    
    async def stop_optimized_persistence(self):
        """Stop the optimized persistence system gracefully"""
        try:
            await self._optimized_persistence.stop()
            logger.info("⏹️ Optimized persistence system stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping optimized persistence: {e}")
    
    def get_optimized_stats(self) -> Dict[str, Any]:
        """Get statistics from optimized persistence system"""
        if self._use_optimized:
            return self._optimized_persistence.get_stats()
        return {"optimized_persistence": "disabled"}

    async def add_monitor(self, monitor_key: str, monitor_data: Dict, position_data: Dict):
        """Add a new monitor with automatic lifecycle management"""
        txn_id = await self.begin_transaction()

        try:
            data = await self.read_data()

            # Add to enhanced_tp_sl_monitors
            if 'bot_data' not in data:
                data['bot_data'] = {}
            if 'enhanced_tp_sl_monitors' not in data['bot_data']:
                data['bot_data']['enhanced_tp_sl_monitors'] = {}

            data['bot_data']['enhanced_tp_sl_monitors'][monitor_key] = monitor_data

            # Add to monitor_tasks for dashboard
            if 'monitor_tasks' not in data['bot_data']:
                data['bot_data']['monitor_tasks'] = {}

            # Create dashboard monitor entry
            dashboard_key = monitor_data.get('dashboard_key', monitor_key)
            data['bot_data']['monitor_tasks'][dashboard_key] = {
                'symbol': monitor_data['symbol'],
                'side': monitor_data['side'],
                'approach': monitor_data.get('approach', 'unknown'),
                'entry_price': str(monitor_data.get('entry_price', 0)),
                'stop_loss': str(monitor_data.get('stop_loss', 0)),
                'take_profits': monitor_data.get('take_profits', []),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'status': 'active',
                'account_type': monitor_data.get('account_type', 'main')
            }

            # Register monitor for lifecycle tracking
            self._monitor_registry[monitor_key] = {
                "created": time.time(),
                "position": position_data,
                "dashboard_key": dashboard_key
            }

            # Write updated data
            await self.write_data(data, txn_id)
            await self.commit_transaction(txn_id)

            # Log to enhanced trade logger if available
            try:
                from utils.enhanced_trade_logger import log_trade_entry
                await log_trade_entry(
                    symbol=monitor_data['symbol'],
                    side=monitor_data['side'],
                    approach=monitor_data.get('approach', 'unknown'),
                    entry_price=monitor_data.get('entry_price', 0),
                    size=position_data.get('size', 0),
                    stop_loss=monitor_data.get('stop_loss'),
                    take_profits=monitor_data.get('take_profits', [])
                )
            except Exception as e:
                logger.debug(f"Could not log to enhanced trade logger: {e}")

            logger.info(f"✅ Added monitor: {monitor_key}")
            self._log_operation("add_monitor", {"key": monitor_key})

        except Exception as e:
            await self.rollback_transaction(txn_id)
            logger.error(f"Error adding monitor: {e}")
            raise

    async def remove_monitor(self, monitor_key: str, reason: str = "position_closed"):
        """Remove monitor when position closes"""
        txn_id = await self.begin_transaction()

        try:
            data = await self.read_data()

            removed = False

            # Remove from enhanced_tp_sl_monitors
            if 'bot_data' in data and 'enhanced_tp_sl_monitors' in data['bot_data']:
                if monitor_key in data['bot_data']['enhanced_tp_sl_monitors']:
                    del data['bot_data']['enhanced_tp_sl_monitors'][monitor_key]
                    removed = True

            # Remove from monitor_tasks
            if monitor_key in self._monitor_registry:
                dashboard_key = self._monitor_registry[monitor_key].get('dashboard_key', monitor_key)
                if 'bot_data' in data and 'monitor_tasks' in data['bot_data']:
                    if dashboard_key in data['bot_data']['monitor_tasks']:
                        del data['bot_data']['monitor_tasks'][dashboard_key]

                # Remove from registry
                del self._monitor_registry[monitor_key]

            if removed:
                await self.write_data(data, txn_id)
                await self.commit_transaction(txn_id)

                logger.info(f"✅ Removed monitor: {monitor_key} (reason: {reason})")
                self._log_operation("remove_monitor", {"key": monitor_key, "reason": reason})
            else:
                await self.rollback_transaction(txn_id)
                logger.warning(f"Monitor not found: {monitor_key}")

        except Exception as e:
            await self.rollback_transaction(txn_id)
            logger.error(f"Error removing monitor: {e}")
            raise

    async def update_monitor(self, monitor_key: str, updates: Dict):
        """Update monitor data atomically"""
        txn_id = await self.begin_transaction()

        try:
            data = await self.read_data()

            updated = False

            # Update enhanced_tp_sl_monitors
            if 'bot_data' in data and 'enhanced_tp_sl_monitors' in data['bot_data']:
                if monitor_key in data['bot_data']['enhanced_tp_sl_monitors']:
                    data['bot_data']['enhanced_tp_sl_monitors'][monitor_key].update(updates)
                    updated = True

            # Update monitor_tasks if needed
            if monitor_key in self._monitor_registry:
                dashboard_key = self._monitor_registry[monitor_key].get('dashboard_key', monitor_key)
                if 'bot_data' in data and 'monitor_tasks' in data['bot_data']:
                    if dashboard_key in data['bot_data']['monitor_tasks']:
                        # Update relevant fields in dashboard monitor
                        for field in ['status', 'stop_loss', 'take_profits']:
                            if field in updates:
                                data['bot_data']['monitor_tasks'][dashboard_key][field] = updates[field]

            if updated:
                await self.write_data(data, txn_id)
                await self.commit_transaction(txn_id)

                self._log_operation("update_monitor", {"key": monitor_key, "updates": list(updates.keys())})
            else:
                await self.rollback_transaction(txn_id)
                logger.warning(f"Monitor not found for update: {monitor_key}")

        except Exception as e:
            await self.rollback_transaction(txn_id)
            logger.error(f"Error updating monitor: {e}")
            raise

    async def get_all_monitors(self) -> Dict:
        """Get all active monitors"""
        try:
            data = await self.read_data()
            monitors = {}

            if 'bot_data' in data and 'enhanced_tp_sl_monitors' in data['bot_data']:
                monitors = data['bot_data']['enhanced_tp_sl_monitors']

            return monitors

        except Exception as e:
            logger.error(f"Error getting monitors: {e}")
            return {}

    async def sync_with_positions(self, active_positions: List[Dict]):
        """Sync monitors with actual positions, removing orphaned monitors"""
        try:
            # Get current monitors
            monitors = await self.get_all_monitors()

            # Create position lookup with account-aware keys
            position_keys = set()
            for pos in active_positions:
                symbol = pos.get('symbol')
                side = pos.get('side')
                if symbol and side:
                    # Add both legacy and account-aware formats for compatibility
                    position_keys.add(f"{symbol}_{side}")  # Legacy format
                    position_keys.add(f"{symbol}_{side}_main")  # Main account format
                    position_keys.add(f"{symbol}_{side}_mirror")  # Mirror account format

            # Find orphaned monitors
            orphaned = []
            for monitor_key in monitors:
                if monitor_key not in position_keys:
                    orphaned.append(monitor_key)

            # Remove orphaned monitors
            for monitor_key in orphaned:
                await self.remove_monitor(monitor_key, reason="position_not_found")

            logger.info(f"✅ Synced monitors: removed {len(orphaned)} orphaned monitors")

        except Exception as e:
            logger.error(f"Error syncing monitors: {e}")

    async def _create_backup(self, operation: str = "manual"):
        """Create timestamped backup"""
        try:
            # Check if we should create a backup - use global timer, not per-operation
            import time
            current_time = time.time()
            last_backup = max(self._last_backup_time.values()) if self._last_backup_time else 0
            
            if current_time - last_backup < self._backup_interval:
                logger.debug(f"Skipping backup for {operation} - last backup was {int(current_time - last_backup)}s ago")
                return
            
            self._last_backup_time[operation] = current_time
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"backup_{operation}_{timestamp}.pkl"

            shutil.copy2(self.filepath, backup_path)

            # Clean up old backups
            self._cleanup_old_backups()

            logger.info(f"✅ Created backup: {backup_path.name}")

        except Exception as e:
            logger.error(f"Error creating backup: {e}")

    def _cleanup_old_backups(self):
        """Keep only the most recent backups"""
        try:
            backups = sorted(self.backup_dir.glob("backup_*.pkl"),
                           key=lambda p: p.stat().st_mtime,
                           reverse=True)

            # Keep only MAX_BACKUPS
            for backup in backups[MAX_BACKUPS:]:
                backup.unlink()
                logger.debug(f"Removed old backup: {backup.name}")

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

    def _recover_from_backup(self):
        """Recover from the most recent valid backup"""
        # Check for safeguard files that prevent backup restoration
        safeguard_files = [
            '.no_backup_restore',
            '.disable_persistence_recovery',
            '.false_tp_fix_verified'
        ]

        for safeguard in safeguard_files:
            if os.path.exists(safeguard):
                logger.warning(f"⚠️ Backup recovery blocked by {safeguard} - preserving current state")
                return  # Don't restore from backup

        try:
            backups = sorted(self.backup_dir.glob("*.pkl"),
                           key=lambda p: p.stat().st_mtime,
                           reverse=True)

            for backup in backups:
                try:
                    # Try to load backup
                    with open(backup, 'rb') as f:
                        pickle.load(f)

                    # If successful, restore it
                    shutil.copy2(backup, self.filepath)
                    self._update_checksum()

                    logger.info(f"✅ Recovered from backup: {backup.name}")
                    return

                except Exception as e:
                    logger.warning(f"Backup {backup.name} is corrupted: {e}")
                    continue

            # If no valid backup, create new file
            logger.warning("No valid backup found, creating new persistence file")
            self._create_new_persistence()

        except Exception as e:
            logger.error(f"Error recovering from backup: {e}")
            self._create_new_persistence()

    def _log_operation(self, operation: str, details: Dict):
        """Log operation for debugging"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "details": details
        }

        self._operation_history.append(entry)

        # Keep only recent history
        if len(self._operation_history) > self._max_history:
            self._operation_history = self._operation_history[-self._max_history:]

    async def get_stats(self) -> Dict:
        """Get persistence manager statistics"""
        try:
            data = await self.read_data()

            stats = {
                "file_size_mb": os.path.getsize(self.filepath) / (1024 * 1024),
                "total_monitors": len(data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})),
                "total_dashboard_monitors": len(data.get('bot_data', {}).get('monitor_tasks', {})),
                "registry_size": len(self._monitor_registry),
                "backup_count": len(list(self.backup_dir.glob("*.pkl"))),
                "last_integrity_check": datetime.fromtimestamp(self._last_integrity_check).isoformat(),
                "recent_operations": self._operation_history[-10:]
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

# Global instance
robust_persistence = RobustPersistenceManager()

# Convenience functions
async def add_trade_monitor(symbol: str, side: str, monitor_data: Dict, position_data: Dict):
    """Add a new trade monitor"""
    monitor_key = f"{symbol}_{side}"
    await robust_persistence.add_monitor(monitor_key, monitor_data, position_data)

async def remove_trade_monitor(symbol: str, side: str, reason: str = "position_closed"):
    """Remove a trade monitor"""
    monitor_key = f"{symbol}_{side}"
    await robust_persistence.remove_monitor(monitor_key, reason)

async def update_trade_monitor(symbol: str, side: str, updates: Dict):
    """Update a trade monitor"""
    monitor_key = f"{symbol}_{side}"
    await robust_persistence.update_monitor(monitor_key, updates)

async def sync_monitors_with_positions(positions: List[Dict]):
    """Sync monitors with actual positions"""
    await robust_persistence.sync_with_positions(positions)

async def get_persistence_stats() -> Dict:
    """Get persistence statistics"""
    return await robust_persistence.get_stats()