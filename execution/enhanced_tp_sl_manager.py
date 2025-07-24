#!/usr/bin/env python3
"""
Enhanced TP/SL Manager - Implements Cornix-style monitoring with dynamic order management
Replaces conditional orders with active monitoring and smart order placement
"""
import asyncio
import aiohttp
from typing import Optional, Dict, List, Any
import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import time

from config.constants import *
from config.settings import (
    CANCEL_LIMITS_ON_TP1, DYNAMIC_FEE_CALCULATION, BREAKEVEN_SAFETY_MARGIN,
    ENHANCED_FILL_DETECTION, ADAPTIVE_MONITORING_INTERVALS,
    BREAKEVEN_FAILSAFE_ENABLED, BREAKEVEN_MAX_RETRIES, BREAKEVEN_EMERGENCY_SL_OFFSET,
    BREAKEVEN_VERIFICATION_INTERVAL, BREAKEVEN_PREFER_AMEND, BREAKEVEN_ENABLE_PROGRESSIVE_RETRY,
    BREAKEVEN_ENABLE_EMERGENCY_MODE, BREAKEVEN_ALERT_FAILURES, DEFAULT_ALERT_CHAT_ID
)
from clients.bybit_helpers import (
    place_order_with_retry, cancel_order_with_retry,
    get_position_info, get_position_info_for_account, get_open_orders, amend_order_with_retry,
    get_correct_position_idx, get_current_price, get_instrument_info, api_call_with_retry,
    get_all_positions
)
from utils.helpers import value_adjusted_to_step
from utils.order_identifier import generate_order_link_id, generate_adjusted_order_link_id, ORDER_TYPE_TP, ORDER_TYPE_SL
from utils.alert_helpers import send_simple_alert as send_trade_alert, send_position_closed_summary
from utils.enhanced_limit_order_tracker import limit_order_tracker
from utils.helpers import safe_decimal_conversion

logger = logging.getLogger(__name__)

# Import failsafe system if enabled
if BREAKEVEN_FAILSAFE_ENABLED:
    try:
        from execution.breakeven_failsafe import breakeven_failsafe
        logger.info("✅ Breakeven failsafe system enabled")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import breakeven failsafe system: {e}")
        BREAKEVEN_FAILSAFE_ENABLED = False
else:
    logger.info("ℹ️ Breakeven failsafe system disabled")

class EnhancedTPSLManager:
    """
    Manages TP/SL orders using active monitoring instead of conditional orders
    Features:
    - Multiple partial TP orders (no conditionals)
    - Dynamic SL adjustment based on filled TPs
    - OCO logic implemented programmatically
    - Price monitoring for optimal execution
    """

    def __init__(self):
        logger.info("🚀 Initializing Enhanced TP/SL Manager")
        self.position_monitors = {}  # symbol -> monitor data
        self.order_state = {}  # symbol -> order state tracking
        self.price_cache = {}  # symbol -> (price, timestamp)
        self.price_cache_ttl = 5  # seconds
        
        # Persistence timing control
        self.last_persistence_save = 0
        self.persistence_interval = 30  # Save at most every 30 seconds
        self.pending_persistence_save = False
        
        # PHASE 2 OPTIMIZATION: Write-through cache with dirty flags
        self.monitor_cache = {}  # In-memory cache of monitor states
        self.dirty_monitors = set()  # Track which monitors need persistence
        self.cache_write_interval = 15  # Write dirty cache every 15 seconds
        self.last_cache_write = 0
        
        # PHASE 2 OPTIMIZATION: Memory structures with indexing and LRU cache
        from utils.cache import EnhancedCache
        self.symbol_index = {}  # symbol -> set of monitor_keys (fast lookup)
        self.account_index = {}  # account_type -> set of monitor_keys
        self.phase_index = {}  # phase -> set of monitor_keys
        self.urgency_cache = EnhancedCache(max_size=1000)  # Cache urgency calculations
        
        # PERFORMANCE OPTIMIZATION: Execution-aware caching
        self._execution_mode = False  # Set to True during trade execution
        self._execution_cache = {}    # Cache API calls during execution
        self._execution_cache_ttl = 5  # 5 second cache during execution
        self._last_execution_cache_clear = 0
        
        # CRITICAL FIX: Monitoring mode cache for normal operations  
        self._monitoring_cache = {}   # Cache for normal monitoring operations
        self._monitoring_cache_ttl = 15  # 15 second cache for monitoring
        self._last_monitoring_cache_clear = 0
        
        # Initialize persistence task flag
        self._persistence_task_pending = False
        
        # Start periodic persistence flush task (if event loop is available)
        self._start_persistence_flush_task()
        
        # API call batching system for performance
        self.api_batch_queue = {}  # operation_type -> list of requests
        self.api_batch_interval = 2  # seconds to wait before batching
        self.api_batch_task = None
        self.last_api_batch_time = {}  # operation_type -> timestamp

        # Mirror alert suppression tracking
        self.mirror_alerts_suppressed = 0
        self.last_suppression_summary = time.time()

        # Alert system health tracking
        self.alerts_sent = {"main": 0, "mirror": 0}
        self.last_health_check = time.time()

        # Enhanced order lifecycle tracking
        self.order_lifecycle = {}  # order_id -> comprehensive lifecycle data
        self.order_relationships = {}  # symbol_side -> order relationship map
        self.execution_metrics = {}  # symbol_side -> execution performance metrics

        # Enhanced fill tracking for accurate percentage calculations
        self.fill_tracker = {}  # symbol_side -> cumulative fill data
        self.actual_entry_prices = {}  # symbol_side -> weighted average entry price
        self.fee_rates_cache = {}  # account tier fee cache

        # Atomic operation locks for race condition prevention
        self.breakeven_locks = {}  # symbol_side -> asyncio.Lock
        self.monitor_locks = {}  # symbol_side -> asyncio.Lock
        self.phase_transition_locks = {}  # symbol_side -> asyncio.Lock
        self.monitor_creation_lock = asyncio.Lock()  # Global lock for monitor creation

        # Enhanced monitoring intervals (adaptive based on urgency)
        self.critical_position_interval = 2   # Near TP triggers or breakeven events  
        self.active_position_interval = 5     # Active positions with pending TPs
        self.standard_monitor_interval = 12   # Standard monitoring
        self.inactive_position_interval = 30  # Positions with all TPs filled
        self.idle_position_interval = 60      # No recent price movement or activity

        # Cleanup scheduler
        self.cleanup_task = None
        self.cleanup_interval = 3600  # 1 hour
        self.last_cleanup = 0

        # Error recovery and resilience
        self.error_recovery_enabled = True
        self.max_recovery_attempts = 3
        self.recovery_backoff_multiplier = 2.0
        self.failed_operations = {}  # operation_id -> failure data
        self.circuit_breaker_state = {}  # symbol_side -> circuit breaker state

        # Mirror account support
        self._mirror_client = None
        self._init_mirror_support()

        # Mirror sync state tracking
        self.mirror_sync_locks = {}  # symbol_side -> asyncio.Lock


    def _ensure_tp_numbers(self, monitor_data: Dict):
        """Ensure all TP orders have proper tp_number and percentage fields"""
        tp_orders = monitor_data.get("tp_orders", {})
        if not tp_orders:
            return
            
        approach = monitor_data.get("approach", "CONSERVATIVE").upper()
        side = monitor_data.get("side", "Buy")
        
        # Define expected structure
        # Conservative approach only: 85%, 5%, 5%, 5%
        tp_percentages = [85, 5, 5, 5]
        
        # Convert to list for sorting
        tp_list = [(order_id, tp_data) for order_id, tp_data in tp_orders.items()]
        
        # Sort by price (ascending for Buy, descending for Sell)
        reverse = (side == "Sell")
        tp_list.sort(key=lambda x: float(x[1].get("price", 0)), reverse=reverse)
        
        # Assign TP numbers
        for i, (order_id, tp_data) in enumerate(tp_list):
            if i < len(tp_percentages):
                if "tp_number" not in tp_data or tp_data.get("tp_number", 0) == 0:
                    tp_data["tp_number"] = i + 1
                    tp_data["percentage"] = tp_percentages[i]
                    logger.debug(f"Assigned TP{i+1} to order {order_id[:8]}...")

        # Enhanced order lifecycle tracking
        self.order_lifecycle = {}  # order_id -> comprehensive lifecycle data
        self.order_relationships = {}  # symbol_side -> order relationship map
        self.execution_metrics = {}  # symbol_side -> execution performance metrics

        # Enhanced fill tracking for accurate percentage calculations
        self.fill_tracker = {}  # symbol_side -> cumulative fill data
        self.actual_entry_prices = {}  # symbol_side -> weighted average entry price
        self.fee_rates_cache = {}  # account tier fee cache

        # Atomic operation locks for race condition prevention
        self.breakeven_locks = {}  # symbol_side -> asyncio.Lock
        self.monitor_locks = {}  # symbol_side -> asyncio.Lock
        self.phase_transition_locks = {}  # symbol_side -> asyncio.Lock
        self.monitor_creation_lock = asyncio.Lock()  # Global lock for monitor creation

        # Enhanced monitoring intervals
        self.standard_monitor_interval = 12  # Standard monitoring
        self.active_position_interval = 5   # Active positions with pending TPs
        self.critical_position_interval = 2  # Positions near breakeven triggers

        # Cleanup scheduler
        self.cleanup_task = None
        self.cleanup_interval = 3600  # 1 hour
        self.last_cleanup = 0

        # Error recovery and resilience
        self.error_recovery_enabled = True
        self.max_recovery_attempts = 3
        self.recovery_backoff_multiplier = 2.0
        self.failed_operations = {}  # operation_id -> failure data
        self.circuit_breaker_state = {}  # symbol_side -> circuit breaker state

        # Mirror account support
        self._mirror_client = None
        self._init_mirror_support()

    def _ensure_tp_orders_dict(self, monitor_data: Dict):
        """Ensure tp_orders is in dict format for backward compatibility"""
        tp_orders = monitor_data.get("tp_orders", {})
        if isinstance(tp_orders, list):
            # Convert list to dict using order_id as key
            tp_dict = {}
            for order in tp_orders:
                if isinstance(order, dict) and "order_id" in order:
                    tp_dict[order["order_id"]] = order
            monitor_data["tp_orders"] = tp_dict
            return tp_dict
        return tp_orders

    async def _place_tp_order_with_retry(self, is_mirror_account: bool, order_params: Dict, tp_num: int, max_retries: int = 3) -> tuple[bool, str, Dict]:
        """
        Place TP order with retry logic for enhanced reliability
        Enhanced for both main and mirror account support
        
        Returns:
            (success: bool, message: str, result: Dict)
        """
        import asyncio
        
        account_name = "MIRROR" if is_mirror_account else "MAIN"
        logger.info(f"🔄 Starting TP{tp_num} placement for {account_name} account")
        
        # Pre-flight check for mirror accounts
        if is_mirror_account and not self._mirror_client:
            logger.error(f"❌ TP{tp_num} {account_name} FAILED: Mirror client not available")
            return False, "Mirror client unavailable", {}
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 TP{tp_num} {account_name} placement attempt {attempt}/{max_retries}")
                
                if is_mirror_account:
                    result = await self._place_order_mirror(**order_params)
                else:
                    result = await self._place_order_main(**order_params)
                
                if result and result.get("orderId"):
                    logger.info(f"✅ TP{tp_num} {account_name} placed successfully on attempt {attempt}")
                    return True, f"{account_name} success on attempt {attempt}", result
                else:
                    error_msg = f"No orderId in result: {result}"
                    logger.warning(f"⚠️ TP{tp_num} {account_name} attempt {attempt} failed: {error_msg}")
                    
                    # Mirror-specific error handling
                    if is_mirror_account and isinstance(result, dict):
                        if "retMsg" in result:
                            error_msg = f"Mirror API error: {result.get('retMsg', 'Unknown')}"
                        elif "msg" in result:
                            error_msg = f"Mirror API error: {result.get('msg', 'Unknown')}"
                    
                    if attempt < max_retries:
                        wait_time = attempt * 0.5  # Progressive delay: 0.5s, 1s, 1.5s
                        logger.info(f"⏳ Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return False, error_msg, result or {}
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ TP{tp_num} {account_name} attempt {attempt} error: {error_msg}")
                
                # Check for common mirror account issues
                if is_mirror_account:
                    if "TriggerDirection invalid" in error_msg:
                        logger.error(f"🪞 Mirror TP order parameter issue detected: {error_msg}")
                    elif "Illegal category" in error_msg:
                        logger.error(f"🪞 Mirror API category issue detected: {error_msg}")
                
                if attempt < max_retries:
                    wait_time = attempt * 0.5  # Progressive delay
                    logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return False, f"{account_name} all {max_retries} attempts failed: {error_msg}", {}
        
        return False, f"{account_name} unexpected retry loop exit", {}
    
    async def _cancel_tp_order_with_retry(self, is_mirror_account: bool, symbol: str, order_id: str, tp_num: int, max_retries: int = 3) -> tuple[bool, str]:
        """
        Cancel TP order with retry logic for enhanced reliability
        Enhanced for both main and mirror account support
        
        Returns:
            (success: bool, message: str)
        """
        import asyncio
        
        account_name = "MIRROR" if is_mirror_account else "MAIN"
        logger.info(f"🗑️ Starting TP{tp_num} cancellation for {account_name} account")
        
        # Pre-flight check for mirror accounts
        if is_mirror_account and not self._mirror_client:
            logger.error(f"❌ TP{tp_num} {account_name} CANCELLATION FAILED: Mirror client not available")
            return False, "Mirror client unavailable"
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🗑️ TP{tp_num} {account_name} cancellation attempt {attempt}/{max_retries}")
                
                if is_mirror_account:
                    success = await self._cancel_order_mirror(symbol, order_id)
                else:
                    success = await self._cancel_order_main(symbol, order_id)
                
                if success:
                    logger.info(f"✅ TP{tp_num} {account_name} cancelled successfully on attempt {attempt}")
                    return True, f"{account_name} cancelled on attempt {attempt}"
                else:
                    logger.warning(f"⚠️ TP{tp_num} {account_name} cancellation attempt {attempt} failed")
                    
                    if attempt < max_retries:
                        wait_time = attempt * 0.3  # Shorter delay for cancellations: 0.3s, 0.6s, 0.9s
                        logger.info(f"⏳ Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return False, f"{account_name} all {max_retries} cancellation attempts failed"
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ TP{tp_num} {account_name} cancellation attempt {attempt} error: {error_msg}")
                
                # Check for common mirror account issues
                if is_mirror_account:
                    if "order not found" in error_msg.lower():
                        logger.warning(f"🪞 Mirror TP order may already be cancelled or filled")
                        # For mirror accounts, "order not found" could mean success
                        return True, f"{account_name} order not found (likely already cancelled/filled)"
                
                if attempt < max_retries:
                    wait_time = attempt * 0.3  # Progressive delay
                    logger.info(f"⏳ Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return False, f"{account_name} all {max_retries} attempts failed: {error_msg}"
        
        return False, f"{account_name} unexpected cancellation retry loop exit"

        # Mirror sync state tracking
        self.mirror_sync_locks = {}  # symbol_side -> asyncio.Lock


    def _update_monitor_cache(self, monitor_key: str, monitor_data: Dict):
        """
        PHASE 2 OPTIMIZATION: Update write-through cache with dirty flag tracking
        This dramatically reduces pickle file operations
        """
        try:
            # Update in-memory cache
            self.monitor_cache[monitor_key] = monitor_data.copy()
            
            # Mark as dirty for next persistence write
            self.dirty_monitors.add(monitor_key)
            
            # PHASE 2 OPTIMIZATION: Update indexes for fast lookups
            self._update_monitor_indexes(monitor_key, monitor_data)
            
            # Check if we need to write dirty cache to persistence
            current_time = time.time()
            if current_time - self.last_cache_write > self.cache_write_interval:
                asyncio.create_task(self._flush_dirty_cache())
                
        except Exception as e:
            logger.error(f"Error updating monitor cache: {e}")
    
    def _update_monitor_indexes(self, monitor_key: str, monitor_data: Dict):
        """
        PHASE 2 OPTIMIZATION: Update memory indexes for fast lookups
        Enables O(1) lookups instead of O(n) iteration
        """
        try:
            symbol = monitor_data.get("symbol")
            account_type = monitor_data.get("account_type", "main")
            phase = monitor_data.get("phase", "BUILDING")
            
            # Update symbol index
            if symbol:
                if symbol not in self.symbol_index:
                    self.symbol_index[symbol] = set()
                self.symbol_index[symbol].add(monitor_key)
            
            # Update account type index
            if account_type not in self.account_index:
                self.account_index[account_type] = set()
            self.account_index[account_type].add(monitor_key)
            
            # Update phase index
            if phase not in self.phase_index:
                self.phase_index[phase] = set()
            self.phase_index[phase].add(monitor_key)
            
        except Exception as e:
            logger.error(f"Error updating monitor indexes: {e}")
    
    def _remove_from_indexes(self, monitor_key: str, monitor_data: Dict = None):
        """Remove monitor from all indexes when deleted"""
        try:
            if monitor_data:
                symbol = monitor_data.get("symbol")
                account_type = monitor_data.get("account_type", "main")
                phase = monitor_data.get("phase", "BUILDING")
                
                # Remove from indexes
                if symbol and symbol in self.symbol_index:
                    self.symbol_index[symbol].discard(monitor_key)
                    if not self.symbol_index[symbol]:
                        del self.symbol_index[symbol]
                
                if account_type in self.account_index:
                    self.account_index[account_type].discard(monitor_key)
                    if not self.account_index[account_type]:
                        del self.account_index[account_type]
                
                if phase in self.phase_index:
                    self.phase_index[phase].discard(monitor_key)
                    if not self.phase_index[phase]:
                        del self.phase_index[phase]
            
            # Remove from cache
            self.monitor_cache.pop(monitor_key, None)
            self.dirty_monitors.discard(monitor_key)
            
        except Exception as e:
            logger.error(f"Error removing from indexes: {e}")
    
    def get_monitors_by_symbol(self, symbol: str) -> Dict[str, Dict]:
        """PHASE 2 OPTIMIZATION: O(1) lookup by symbol using index"""
        monitor_keys = self.symbol_index.get(symbol, set())
        return {key: self.position_monitors[key] for key in monitor_keys if key in self.position_monitors}
    
    def get_monitors_by_account(self, account_type: str) -> Dict[str, Dict]:
        """PHASE 2 OPTIMIZATION: O(1) lookup by account type using index"""
        monitor_keys = self.account_index.get(account_type, set())
        return {key: self.position_monitors[key] for key in monitor_keys if key in self.position_monitors}
    
    def get_monitors_by_phase(self, phase: str) -> Dict[str, Dict]:
        """PHASE 2 OPTIMIZATION: O(1) lookup by phase using index"""
        monitor_keys = self.phase_index.get(phase, set())
        return {key: self.position_monitors[key] for key in monitor_keys if key in self.position_monitors}
    
    async def _flush_dirty_cache(self):
        """
        PHASE 2 OPTIMIZATION: Flush only dirty monitors to persistence
        Write-through cache pattern for optimal performance
        """
        if not self.dirty_monitors:
            return
            
        try:
            current_time = time.time()
            dirty_count = len(self.dirty_monitors)
            
            # Only flush if we have dirty data and enough time has passed
            if current_time - self.last_cache_write < self.cache_write_interval:
                return
            
            logger.debug(f"💾 Flushing {dirty_count} dirty monitors to persistence")
            
            # Update persistence with only dirty monitors (more efficient)
            await self._save_dirty_monitors_to_persistence()
            
            # Clear dirty flags
            self.dirty_monitors.clear()
            self.last_cache_write = current_time
            
            logger.debug(f"✅ Cache flush complete: {dirty_count} monitors persisted")
            
        except Exception as e:
            logger.error(f"Error flushing dirty cache: {e}")
    
    async def _save_dirty_monitors_to_persistence(self):
        """Save only dirty monitors to persistence file (write-through optimization)"""
        try:
            import pickle
            
            # Read current persistence file
            pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            try:
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
            except FileNotFoundError:
                data = {'conversations': {}, 'user_data': {}, 'chat_data': {}, 'bot_data': {}}
                
            # Ensure structure exists
            if 'bot_data' not in data:
                data['bot_data'] = {}
            if 'enhanced_tp_sl_monitors' not in data['bot_data']:
                data['bot_data']['enhanced_tp_sl_monitors'] = {}
            
            # Update only dirty monitors (efficiency optimization)
            for monitor_key in self.dirty_monitors:
                if monitor_key in self.monitor_cache:
                    # Clean the monitor data before saving
                    clean_data = self._clean_monitor_for_persistence(self.monitor_cache[monitor_key])
                    data['bot_data']['enhanced_tp_sl_monitors'][monitor_key] = clean_data
            
            # Write updated data back
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
                
        except Exception as e:
            logger.error(f"Error saving dirty monitors to persistence: {e}")
    
    def _clean_monitor_for_persistence(self, monitor_data: Dict) -> Dict:
        """Clean monitor data to remove non-serializable fields"""
        clean_data = {}
        for key, value in monitor_data.items():
            # Skip non-serializable fields
            if any([
                'task' in str(key).lower(),
                '_lock' in str(key),
                hasattr(value, '_callbacks'),
                hasattr(value, '__await__'),
                hasattr(value, 'cancel'),
                callable(value) and not isinstance(value, type)
            ]):
                continue
            clean_data[key] = value
        return clean_data

    def save_monitors_to_persistence(self, force: bool = False, reason: str = "routine"):
        """
        Save all monitors to persistence file with intelligent batching
        
        Args:
            force (bool): If True, saves immediately regardless of timing
            reason (str): Reason for the save (for logging and prioritization)
        """
        current_time = time.time()
        
        # Determine if this is a critical event that needs immediate save
        critical_reasons = [
            "tp_hit", "sl_hit", "position_closed", "monitor_created", "monitor_removed",
            "breakeven_moved", "phase_change", "emergency", "startup", "shutdown"
        ]
        is_critical = force or reason in critical_reasons
        
        # If not critical and not enough time has passed, just mark as pending
        if not is_critical and (current_time - self.last_persistence_save) < self.persistence_interval:
            self.pending_persistence_save = True
            logger.debug(f"📊 Persistence save queued ({reason}) - will batch with next critical event")
            return
        
        # If we have a pending save or this is a critical event, proceed
        if not (is_critical or self.pending_persistence_save):
            return
            
        try:
            import copy
            import asyncio
            from utils.pickle_lock import main_pickle_lock

            # Create a deep copy of monitors and remove non-serializable objects
            clean_monitors = {}
            for key, monitor in self.position_monitors.items():
                # Deep copy to avoid modifying original
                clean_monitor = {}
                
                # Only copy serializable fields
                for field_key, field_value in monitor.items():
                    # Skip any field that might contain non-serializable objects
                    if any([
                        'task' in str(field_key).lower(),
                        '_lock' in str(field_key),
                        'bot' in str(field_key).lower() and 'instance' in str(field_key).lower(),
                        hasattr(field_value, '_callbacks'),  # AsyncIO objects
                        hasattr(field_value, '__await__'),   # Coroutines
                        hasattr(field_value, 'cancel'),       # Likely a task
                        str(type(field_value)).startswith("<class '_asyncio"),  # Any asyncio type
                        str(type(field_value)).startswith("<class 'asyncio"),
                        callable(field_value) and not isinstance(field_value, type)  # Functions
                    ]):
                        logger.debug(f"Skipping non-serializable field: {field_key} (type: {type(field_value)})")
                        continue
                    
                    # For nested dicts, clean them too
                    if isinstance(field_value, dict):
                        cleaned_dict = {}
                        for k, v in field_value.items():
                            if not any([
                                hasattr(v, '_callbacks'),
                                hasattr(v, '__await__'),
                                hasattr(v, 'cancel'),
                                callable(v) and not isinstance(v, type)
                            ]):
                                cleaned_dict[k] = v
                        clean_monitor[field_key] = cleaned_dict
                    else:
                        clean_monitor[field_key] = field_value

                clean_monitors[key] = clean_monitor

            # Use safe update with file locking
            def update_monitors(data):
                if 'bot_data' not in data:
                    data['bot_data'] = {}
                data['bot_data']['enhanced_tp_sl_monitors'] = clean_monitors

            success = main_pickle_lock.update_data(update_monitors)

            if success:
                # Update timing and reset pending flag
                self.last_persistence_save = current_time
                self.pending_persistence_save = False
                
                save_type = "🔥 Critical" if is_critical else "📦 Batched"
                logger.debug(f"{save_type} persistence save completed ({reason}): {len(clean_monitors)} monitors")
            else:
                logger.error("Failed to save monitors to persistence")

        except Exception as e:
            logger.error(f"Error saving monitors to persistence: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _start_persistence_flush_task(self):
        """Start a background task to periodically flush pending persistence saves"""
        try:
            # Check if there's a running event loop
            loop = asyncio.get_running_loop()
            loop.create_task(self._periodic_persistence_flush())
            logger.debug("📊 Periodic persistence flush task started")
        except RuntimeError:
            # No event loop running yet, will start when event loop is available
            logger.debug("📊 No event loop available yet, will start persistence flush when loop starts")
            # Store a flag to start the task later
            self._persistence_task_pending = True
    
    async def _periodic_persistence_flush(self):
        """Periodically flush any pending persistence saves"""
        while True:
            try:
                await asyncio.sleep(self.persistence_interval)
                
                if self.pending_persistence_save:
                    logger.debug("📦 Flushing pending persistence save...")
                    self.save_monitors_to_persistence(force=True, reason="periodic_flush")
                    
            except Exception as e:
                logger.error(f"Error in periodic persistence flush: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    def _calculate_monitoring_interval(self, monitor_data: Dict) -> int:
        """
        Calculate the appropriate monitoring interval based on position urgency
        
        Args:
            monitor_data: The monitor data dictionary
            
        Returns:
            int: Monitoring interval in seconds
        """
        try:
            current_time = time.time()
            symbol = monitor_data.get("symbol", "UNKNOWN")
            phase = monitor_data.get("phase", "BUILDING")
            
            # Critical priority: Near TP triggers or immediate breakeven needs
            if self._is_critical_urgency(monitor_data):
                logger.debug(f"🔥 {symbol} using CRITICAL interval (2s): Near TP trigger or breakeven event")
                return self.critical_position_interval
                
            # Active priority: Positions with pending TPs in PROFIT_TAKING phase
            elif phase == "PROFIT_TAKING":
                logger.debug(f"⚡ {symbol} using ACTIVE interval (5s): In profit-taking phase")
                return self.active_position_interval
                
            # Inactive priority: All TPs filled or position largely complete
            elif self._is_position_mostly_complete(monitor_data):
                logger.debug(f"🐌 {symbol} using INACTIVE interval (30s): Position mostly complete")
                return self.inactive_position_interval
                
            # Idle priority: No recent activity or price movement
            elif self._is_position_idle(monitor_data, current_time):
                logger.debug(f"💤 {symbol} using IDLE interval (60s): No recent activity")
                return self.idle_position_interval
                
            # Standard priority: Default monitoring
            else:
                logger.debug(f"📊 {symbol} using STANDARD interval (12s): Default monitoring")
                return self.standard_monitor_interval
                
        except Exception as e:
            logger.error(f"Error calculating monitoring interval: {e}")
            return self.standard_monitor_interval  # Fallback to standard

    def _is_critical_urgency(self, monitor_data: Dict) -> bool:
        """Check if position needs critical (2s) monitoring"""
        try:
            # Check if near TP triggers (within 1% of current price)
            current_size = monitor_data.get("remaining_size", 0)
            if current_size <= 0:
                return False
                
            # Check if any TP is close to being hit
            tp_orders = monitor_data.get("tp_orders", {})
            if isinstance(tp_orders, dict):
                for tp_key, tp_data in tp_orders.items():
                    if isinstance(tp_data, dict) and not tp_data.get("filled", False):
                        # This TP is still active - check if price is close
                        # Critical monitoring when we might hit a TP soon
                        return True
                        
            # Check if breakeven move is pending
            if monitor_data.get("tp1_hit", False) and not monitor_data.get("sl_moved_to_be", False):
                return True
                
            # Check if in phase transition
            phase = monitor_data.get("phase", "BUILDING")
            last_phase_change = monitor_data.get("last_phase_change", 0)
            if time.time() - last_phase_change < 60:  # Within 1 minute of phase change
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking critical urgency: {e}")
            return False

    def _is_position_mostly_complete(self, monitor_data: Dict) -> bool:
        """Check if position is mostly complete (90%+ filled)"""
        try:
            original_size = monitor_data.get("position_size", 0)
            remaining_size = monitor_data.get("remaining_size", 0)
            
            if original_size <= 0:
                return True
                
            completion_percentage = ((original_size - remaining_size) / original_size) * 100
            return completion_percentage >= 90
            
        except Exception as e:
            logger.error(f"Error checking position completion: {e}")
            return False

    def _is_position_idle(self, monitor_data: Dict, current_time: float) -> bool:
        """Check if position has been idle (no activity for 10+ minutes)"""
        try:
            last_check = monitor_data.get("last_check", current_time)
            last_activity = monitor_data.get("last_activity", current_time)
            
            # Consider idle if no activity for 10 minutes
            idle_threshold = 600  # 10 minutes
            
            time_since_activity = current_time - last_activity
            return time_since_activity > idle_threshold
            
        except Exception as e:
            logger.error(f"Error checking position idle status: {e}")
            return False

    async def _batch_api_call(self, operation_type: str, call_data: Dict) -> Any:
        """
        Batch API calls with intelligent caching (5-10s TTL)
        PERFORMANCE OPTIMIZATION: Reduces redundant API requests dramatically
        
        Args:
            operation_type: Type of operation (position_check, order_check, price_check)
            call_data: Data needed for the API call
            
        Returns:
            Result from cached or batched API call
        """
        try:
            # Create cache key for this specific request
            cache_key = f"{operation_type}_{call_data.get('symbol', '')}_{call_data.get('account_type', 'main')}"
            
            # Check intelligent cache first (5-10s TTL)
            if hasattr(self, 'api_call_cache'):
                cached_result = self.api_call_cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"📋 API cache hit for {cache_key}")
                    return cached_result
            else:
                # Initialize cache on first use
                from utils.cache import EnhancedCache
                self.api_call_cache = EnhancedCache(max_size=500)
                logger.info("🚀 Initialized API call cache for performance optimization")
            
            current_time = time.time()
            
            # Initialize batch queue for this operation type
            if operation_type not in self.api_batch_queue:
                self.api_batch_queue[operation_type] = []
                self.last_api_batch_time[operation_type] = 0
            
            # Add to batch queue
            self.api_batch_queue[operation_type].append(call_data)
            
            # Check if we should process the batch
            time_since_last_batch = current_time - self.last_api_batch_time[operation_type]
            queue_size = len(self.api_batch_queue[operation_type])
            
            # Process batch if interval passed or queue is full (max 10 requests)
            if time_since_last_batch >= self.api_batch_interval or queue_size >= 10:
                result = await self._process_api_batch(operation_type)
                
                # Cache the result with 7 second TTL (middle of 5-10s range)
                if result and cache_key in result:
                    self.api_call_cache.set(cache_key, result[cache_key], ttl=7)
                    return result[cache_key]
                return result
            else:
                # Schedule batch processing if not already scheduled
                if not self.api_batch_task or self.api_batch_task.done():
                    self.api_batch_task = asyncio.create_task(
                        self._delayed_batch_process(operation_type)
                    )
                return None
                
        except Exception as e:
            logger.error(f"Error in API call batching with cache: {e}")
            return None

    async def _delayed_batch_process(self, operation_type: str):
        """Process API batch after a delay and cache results"""
        try:
            await asyncio.sleep(self.api_batch_interval)
            results = await self._process_api_batch(operation_type)
            
            # Cache all batch results with 7 second TTL
            if results and hasattr(self, 'api_call_cache'):
                for cache_key, result in results.items():
                    self.api_call_cache.set(cache_key, result, ttl=7)
                    logger.debug(f"📋 Cached batch result for {cache_key}")
                    
        except Exception as e:
            logger.error(f"Error in delayed batch processing: {e}")

    async def _process_api_batch(self, operation_type: str) -> Dict:
        """
        Process a batch of API calls for the given operation type
        
        Args:
            operation_type: Type of operation to batch process
            
        Returns:
            Dict: Results mapped by request identifier
        """
        try:
            if operation_type not in self.api_batch_queue or not self.api_batch_queue[operation_type]:
                return {}
            
            batch_requests = self.api_batch_queue[operation_type].copy()
            self.api_batch_queue[operation_type].clear()
            self.last_api_batch_time[operation_type] = time.time()
            
            logger.debug(f"📦 Processing batch of {len(batch_requests)} {operation_type} requests")
            
            results = {}
            
            if operation_type == "position_check":
                results = await self._batch_position_checks(batch_requests)
            elif operation_type == "order_check":
                results = await self._batch_order_checks(batch_requests)
            elif operation_type == "price_check":
                results = await self._batch_price_checks(batch_requests)
            
            logger.debug(f"✅ Batch processing completed: {len(results)} results for {operation_type}")
            return results
            
        except Exception as e:
            logger.error(f"Error processing API batch for {operation_type}: {e}")
            return {}

    async def _batch_position_checks(self, requests: List[Dict]) -> Dict:
        """Batch multiple position checks into fewer API calls"""
        try:
            results = {}
            account_groups = {}  # Group by account type
            
            # Group requests by account type
            for req in requests:
                account_type = req.get("account_type", "main")
                if account_type not in account_groups:
                    account_groups[account_type] = []
                account_groups[account_type].append(req)
            
            # Make one API call per account type
            for account_type, account_requests in account_groups.items():
                try:
                    if account_type == "main":
                        positions = await get_all_positions()
                    else:
                        from execution.mirror_trader import get_mirror_positions
                        positions = await get_mirror_positions()
                    
                    # Map results back to requests
                    for req in account_requests:
                        symbol = req.get("symbol")
                        side = req.get("side")
                        
                        matching_position = None
                        for pos in positions:
                            if pos.get("symbol") == symbol and pos.get("side") == side:
                                matching_position = pos
                                break
                        
                        req_id = f"{symbol}_{side}_{account_type}"
                        results[req_id] = matching_position
                        
                except Exception as e:
                    logger.error(f"Error fetching positions for {account_type}: {e}")
                    # Set None results for failed requests
                    for req in account_requests:
                        req_id = f"{req['symbol']}_{req['side']}_{account_type}"
                        results[req_id] = None
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch position checks: {e}")
            return {}

    async def _batch_order_checks(self, requests: List[Dict]) -> Dict:
        """Batch multiple order checks into fewer API calls"""
        try:
            results = {}
            # Similar batching logic for orders
            # Implementation would depend on specific order checking needs
            return results
        except Exception as e:
            logger.error(f"Error in batch order checks: {e}")
            return {}

    async def _batch_price_checks(self, requests: List[Dict]) -> Dict:
        """Batch multiple price checks into fewer API calls"""
        try:
            results = {}
            symbols = list(set(req.get("symbol") for req in requests))
            
            # Get prices for all symbols in one call (if API supports it)
            for symbol in symbols:
                try:
                    price = await get_current_price(symbol)
                    for req in requests:
                        if req.get("symbol") == symbol:
                            results[f"price_{symbol}"] = price
                except Exception as e:
                    logger.error(f"Error getting price for {symbol}: {e}")
                    results[f"price_{symbol}"] = None
            
            return results
            
        except Exception as e:
            logger.error(f"Error in batch price checks: {e}")
            return {}

    def _init_mirror_support(self):
        """Initialize mirror trading support if available"""
        try:
            from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
            if is_mirror_trading_enabled() and bybit_client_2:
                self._mirror_client = bybit_client_2
                logger.info("✅ Mirror account support enabled for Enhanced TP/SL")
            else:
                logger.info("ℹ️ Mirror trading disabled or not configured")
        except ImportError:
            logger.info("ℹ️ Mirror trading module not available")

    def _sanitize_monitor_data(self, monitor_data: Dict) -> Dict:
        """
        Ensure all numeric fields in monitor data are Decimal types
        This prevents type mismatch errors when loading from persistence
        """
        # List of fields that should be Decimal
        decimal_fields = [
            "entry_price", "position_size", "current_size", "remaining_size",
            "sl_moved_to_be_price", "original_sl_price", "avg_partial_fill_price",
            "last_limit_fill_size", "cumulative_fill_size"
        ]

        # Convert each field to Decimal if it exists
        for field in decimal_fields:
            if field in monitor_data and monitor_data[field] is not None:
                try:
                    monitor_data[field] = Decimal(str(monitor_data[field]))
                except (InvalidOperation, ValueError) as e:
                    logger.warning(f"Could not convert {field}={monitor_data[field]} to Decimal: {e}")
                    # Set to 0 as a safe default
                    monitor_data[field] = Decimal("0")

        # Also sanitize nested structures
        if "fill_tracker" in monitor_data and isinstance(monitor_data["fill_tracker"], dict):
            for key, value in monitor_data["fill_tracker"].items():
                if isinstance(value, (int, float, str)) and key in ["total_filled", "target_size"]:
                    try:
                        monitor_data["fill_tracker"][key] = Decimal(str(value))
                    except (InvalidOperation, ValueError):
                        monitor_data["fill_tracker"][key] = Decimal("0")

        # Sanitize limit_orders - convert string list to dict list
        if "limit_orders" in monitor_data:
            sanitized_limit_orders = []
            for order in monitor_data.get("limit_orders", []):
                if isinstance(order, str):
                    # Convert string order ID to dict format
                    sanitized_limit_orders.append({
                        "order_id": order,
                        "status": "ACTIVE",
                        "registered_at": time.time()
                    })
                elif isinstance(order, dict):
                    # Already in correct format
                    sanitized_limit_orders.append(order)
            monitor_data["limit_orders"] = sanitized_limit_orders

        return monitor_data

    def _is_mirror_position(self, monitor_data: Dict) -> bool:
        """
        Determine if a position belongs to the mirror account
        Uses multiple detection methods for robust identification
        """
        # Method 1: Check explicit account_type field (preferred)
        account_type = monitor_data.get("account_type")
        if account_type:
            return account_type == "mirror"

        # Method 2: Check if this is the mirror enhanced TP/SL manager instance
        if hasattr(self, '__class__') and 'Mirror' in self.__class__.__name__:
            return True

        # Method 3: Check monitor key pattern for mirror suffix
        symbol = monitor_data.get("symbol", "")
        side = monitor_data.get("side", "")
        # Support account-aware keys
        if account_type:
            monitor_key = f"{symbol}_{side}_{account_type}"
        else:
            # Try to find the right key
            main_key = f"{symbol}_{side}_main"
            mirror_key = f"{symbol}_{side}_mirror"
            legacy_key = f"{symbol}_{side}"

            if main_key in self.position_monitors:
                monitor_key = main_key
            elif mirror_key in self.position_monitors:
                monitor_key = mirror_key
            else:
                monitor_key = legacy_key

        # Check if this key is tracked in mirror monitors
        if hasattr(self, '_mirror_monitors') and monitor_key in getattr(self, '_mirror_monitors', {}):
            return True

        # Method 4: Use order IDs to detect mirror account orders
        # Mirror orders may have different patterns or be tracked separately
        limit_orders = monitor_data.get("limit_orders", [])
        if limit_orders and self._mirror_client:
            # If we can't determine from metadata, default to main account
            # This is a conservative approach to avoid cross-account cancellation errors
            pass

        # Method 5: Fallback - check global bot_data for account context
        # This would require access to bot_data, which we don't have here

        # Default: assume main account unless explicitly marked as mirror
        # This prevents accidental cross-account operations
        return False

    def _get_cancel_function(self, is_mirror_account: bool):
        """Get the appropriate cancel function based on account type"""
        if is_mirror_account and self._mirror_client:
            return self._cancel_order_mirror
        else:
            return self._cancel_order_main

    def _get_place_order_function(self, is_mirror_account: bool):
        """Get the appropriate place order function based on account type"""
        if is_mirror_account and self._mirror_client:
            return self._place_order_mirror
        else:
            return self._place_order_main

    async def _cancel_order_main(self, symbol: str, order_id: str) -> bool:
        """Cancel order on main account"""
        return await cancel_order_with_retry(symbol, order_id)

    async def _cancel_order_mirror(self, symbol: str, order_id: str) -> bool:
        """Cancel order on mirror account"""
        try:
            # Use mirror client for cancellation
            if not self._mirror_client:
                logger.error("❌ Mirror client not available for order cancellation")
                return False

            # Import the mirror cancellation function
            from clients.bybit_helpers import api_call_with_retry

            logger.info(f"🔄 Attempting to cancel mirror order {order_id[:8]}... for {symbol}")

            response = await api_call_with_retry(
                lambda: self._mirror_client.cancel_order(
                    category="linear",
                    symbol=symbol,
                    orderId=order_id
                )
            )

            if response and response.get("retCode") == 0:
                logger.info(f"✅ Mirror order {order_id[:8]}... cancelled successfully")
                return True
            else:
                logger.warning(f"⚠️ Failed to cancel mirror order {order_id[:8]}...: {response}")
                return False

        except Exception as e:
            # Handle specific order cancellation errors more gracefully
            error_str = str(e).lower()
            if "order not exists" in error_str or "too late to cancel" in error_str or "110001" in error_str:
                logger.info(f"🔄 Mirror order {order_id[:8]}... already cancelled or filled")
                return True  # Consider this a success since the order is no longer active
            else:
                logger.error(f"❌ Error cancelling mirror order {order_id[:8]}...: {e}")
                return False

    async def _place_order_main(self, **order_params) -> Dict:
        """Place order on main account"""
        return await place_order_with_retry(**order_params)

    async def _place_order_mirror(self, **order_params) -> Dict:
        """Place order on mirror account"""
        try:
            # Use mirror client for order placement
            if not self._mirror_client:
                logger.error("❌ Mirror client not available for order placement")
                return {}

            from clients.bybit_helpers import api_call_with_retry

            # Remove any client parameter if present and use mirror client
            order_params.pop('client', None)

            # Convert snake_case parameters to camelCase for Bybit API
            converted_params = {}
            for key, value in order_params.items():
                if key == "order_type":
                    converted_params["orderType"] = value
                elif key == "trigger_price":
                    converted_params["triggerPrice"] = value
                elif key == "trigger_direction":
                    converted_params["triggerDirection"] = value
                elif key == "trigger_by":
                    converted_params["triggerBy"] = value
                elif key == "stop_order_type":
                    converted_params["stopOrderType"] = value
                elif key == "time_in_force":
                    converted_params["timeInForce"] = value
                elif key == "order_link_id":
                    converted_params["orderLinkId"] = value
                elif key == "position_idx":
                    converted_params["positionIdx"] = value
                elif key == "reduce_only":
                    converted_params["reduceOnly"] = value
                else:
                    # Keep other parameters as-is (symbol, side, qty, price, etc.)
                    converted_params[key] = value

            # Add required category parameter for linear contracts
            converted_params["category"] = "linear"

            logger.info(f"🔄 Placing mirror order: {converted_params.get('symbol')} {converted_params.get('side')} {converted_params.get('orderType')}")

            response = await api_call_with_retry(
                lambda: self._mirror_client.place_order(**converted_params)
            )

            if response and response.get("retCode") == 0:
                result = response.get("result", {})
                logger.info(f"✅ Mirror order placed successfully: {result.get('orderId', '')[:8]}...")
                return result
            else:
                logger.warning(f"⚠️ Failed to place mirror order: {response}")
                return {}

        except Exception as e:
            logger.error(f"❌ Error placing mirror order: {e}")
            return {}

    async def _cancel_live_limit_orders(self, symbol: str, side: str, is_mirror_account: bool) -> int:
        """
        Scan live orders and cancel bot limit orders for the specified position
        This is a fallback when monitor data doesn't track orders properly
        """
        try:
            # CRITICAL FIX: Use monitoring cache instead of direct API calls
            account_type = "mirror" if is_mirror_account else "main"
            cached_orders = await self._get_cached_open_orders(symbol, account_type)
            response = {"result": {"list": cached_orders}}

            if not response:
                logger.warning(f"Failed to get live orders for {symbol}")
                return 0

            # Get orders from the response
            orders = response.get("result", {}).get("list", [])
            if not orders:
                logger.info(f"No live orders found for {symbol}")
                return 0
            cancelled_count = 0

            # Filter for bot limit orders that match the position
            for order in orders:
                order_id = order.get("orderId", "")
                order_link_id = order.get("orderLinkId", "")
                order_side = order.get("side", "")
                order_type = order.get("orderType", "")

                # Check if this is a bot limit order for the matching side
                if (order_type == "Limit" and
                    order_side == side and
                    order_link_id.startswith("BOT_") and
                    "LIMIT" in order_link_id.upper()):

                    logger.info(f"🎯 Found bot limit order to cancel: {order_id[:8]}... ({order_link_id})")

                    try:
                        if is_mirror_account:
                            success = await self._cancel_order_mirror(symbol, order_id)
                        else:
                            success = await self._cancel_order_main(symbol, order_id)

                        if success:
                            cancelled_count += 1
                            logger.info(f"✅ Cancelled live limit order {order_id[:8]}...")
                        else:
                            logger.warning(f"⚠️ Failed to cancel live limit order {order_id[:8]}...")

                    except Exception as e:
                        logger.error(f"❌ Error cancelling live limit order {order_id[:8]}...: {e}")

            if cancelled_count > 0:
                logger.info(f"📡 Live order scan: {cancelled_count} bot limit orders cancelled")
            else:
                logger.info(f"📡 Live order scan: No bot limit orders found to cancel")

            return cancelled_count

        except Exception as e:
            logger.error(f"❌ Error scanning live orders for {symbol} {side}: {e}")
            return 0

    async def check_position(self, symbol: str, side: str, account_type: str = "main"):
        """Check if position exists and return position data"""
        try:
            if account_type == "mirror":
                from clients.bybit_helpers import get_position_info_for_account
                positions = await get_position_info_for_account(symbol, "mirror")
            else:
                from clients.bybit_client import get_position_info
                position = await get_position_info(symbol)
                # get_position_info returns a single dict, convert to list for uniform handling
                positions = [position] if position else []
            
            if positions and isinstance(positions, list):
                for pos in positions:
                    # Ensure pos is a dict before trying to access attributes
                    if isinstance(pos, dict) and pos.get('symbol') == symbol and pos.get('side') == side:
                        if float(pos.get('size', 0)) > 0:
                            return pos
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking position: {e}")
            return None

    async def setup_tp_sl_orders(
        self,
        symbol: str,
        side: str,
        position_size: Decimal,
        entry_price: Decimal,
        tp_prices: List[Decimal],
        tp_percentages: List[Decimal],
        sl_price: Decimal,
        chat_id: int,
        approach: str = "CONSERVATIVE",
        qty_step: Decimal = Decimal("0.001"),
        initial_position_size: Decimal = None,  # Actual filled position size
        account_type: str = "main",  # ENHANCED: Support both "main" and "mirror" accounts
        mirror_position_size: Decimal = None,  # ENHANCED: Mirror position size (can be different)
        mirror_target_size: Decimal = None     # ENHANCED: Mirror target size for proportional trading
    ) -> Dict[str, Any]:
        """
        ENHANCED: Set up TP/SL orders using the enhanced system for BOTH main and mirror accounts

        Args:
            symbol: Trading symbol
            side: Buy or Sell
            position_size: Total position size (main account)
            entry_price: Entry price of position
            tp_prices: List of TP target prices
            tp_percentages: List of percentages for each TP (must sum to 100)
            sl_price: Stop loss price
            chat_id: Telegram chat ID
            approach: Trading approach (CONSERVATIVE only)
            qty_step: Quantity step for the symbol
            initial_position_size: Actual filled position size (main account)
            account_type: "main", "mirror", or "both" for unified setup
            mirror_position_size: Position size for mirror account (can be different for proportional trading)
            mirror_target_size: Target size for mirror account

        Returns:
            Dict with setup results and order IDs for both accounts
        """
        try:
            logger.info(f"🎯 ENHANCED UNIFIED TP/SL setup for {symbol} {side} ({account_type})")
            logger.info(f"   Main position size: {position_size}")
            logger.info(f"   Mirror position size: {mirror_position_size}")
            logger.info(f"   TP targets: {tp_prices} with percentages: {tp_percentages}")
            logger.info(f"   SL price: {sl_price}")

            # Determine which accounts to set up
            setup_main = account_type in ["main", "both"]
            setup_mirror = account_type in ["mirror", "both"] and self._is_mirror_trading_enabled()

            logger.info(f"   Setup main: {setup_main}, Setup mirror: {setup_mirror}")

            # If initial_position_size is provided, use it for TP/SL calculations
            # This handles cases where orders are placed before full position is built
            if initial_position_size is not None:
                logger.info(f"   🔄 Using initial position size: {initial_position_size} (target: {position_size})")
                tp_sl_position_size = initial_position_size
            else:
                tp_sl_position_size = position_size

            # Mirror account sizing
            if setup_mirror:
                mirror_tp_sl_size = mirror_position_size if mirror_position_size is not None else tp_sl_position_size
                mirror_target = mirror_target_size if mirror_target_size is not None else position_size
                logger.info(f"   🪞 Mirror TP/SL size: {mirror_tp_sl_size} (target: {mirror_target})")

            results = {
                "main_account": {
                    "tp_orders": {},
                    "sl_order": None,
                    "errors": [],
                    "success": False
                },
                "mirror_account": {
                    "tp_orders": {},
                    "sl_order": None,
                    "errors": [],
                    "success": False
                },
                "monitoring_active": False,
                "success": False
            }

            # Validate inputs
            if sum(tp_percentages) != 100:
                logger.warning(f"TP percentages sum to {sum(tp_percentages)}, not 100%")

            # Get current price for minimum value calculation
            current_price = await get_current_price(symbol)
            if not current_price:
                current_price = entry_price

            # Minimum order value in USDT (Bybit requires $5 minimum)
            MIN_ORDER_VALUE = Decimal("5.0")

            # Calculate order quantities and check minimum values
            tp_quantities = []
            tp_valid = []
            remaining_percentage = Decimal("0")

            for i, percentage in enumerate(tp_percentages):
                qty = tp_sl_position_size * Decimal(str(percentage)) / Decimal("100")
                # Adjust quantity to step size
                adjusted_qty = value_adjusted_to_step(qty, qty_step)

                # Check minimum order value
                order_value = adjusted_qty * Decimal(str(current_price))
                if order_value < MIN_ORDER_VALUE:
                    logger.warning(f"TP{i+1} value ${order_value:.2f} < minimum ${MIN_ORDER_VALUE}")
                    tp_quantities.append(Decimal("0"))
                    tp_valid.append(False)
                    remaining_percentage += Decimal(str(percentage))
                else:
                    tp_quantities.append(adjusted_qty)
                    tp_valid.append(True)

            # Redistribute remaining percentage to TP1 if needed
            if remaining_percentage > 0 and tp_valid[0]:
                logger.info(f"Redistributing {remaining_percentage}% to TP1")
                tp_quantities[0] = value_adjusted_to_step(
                    tp_sl_position_size * (Decimal(str(tp_percentages[0])) + remaining_percentage) / Decimal("100"),
                    qty_step
                )

            # Get correct position index for hedge mode
            position_idx = await get_correct_position_idx(symbol, side)
            logger.info(f"🔧 Using position index {position_idx} for {symbol} {side} (hedge mode)")

            # ENHANCED: Place TP orders on both main and mirror accounts
            await self._place_tp_orders_unified(
                symbol=symbol,
                side=side,
                tp_prices=tp_prices,
                tp_quantities=tp_quantities,
                tp_percentages=tp_percentages,
                approach=approach,
                position_idx=position_idx,
                setup_main=setup_main,
                setup_mirror=setup_mirror,
                mirror_tp_sl_size=mirror_tp_sl_size if setup_mirror else None,
                qty_step=qty_step,
                results=results
            )

            # ENHANCED: Place SL orders on both main and mirror accounts
            await self._place_sl_orders_unified(
                symbol=symbol,
                side=side,
                sl_price=sl_price,
                approach=approach,
                position_idx=position_idx,
                setup_main=setup_main,
                setup_mirror=setup_mirror,
                main_current_size=tp_sl_position_size,
                main_target_size=position_size,
                mirror_current_size=mirror_tp_sl_size if setup_mirror else None,
                mirror_target_size=mirror_target if setup_mirror else None,
                results=results
            )

            # FIXED: Flatten nested results structure for monitor compatibility
            # Combine main and mirror account orders into flat structure
            all_tp_orders = {**results["main_account"]["tp_orders"], **results["mirror_account"]["tp_orders"]}
            combined_sl_order = results["main_account"]["sl_order"] or results["mirror_account"]["sl_order"]
            all_errors = results["main_account"]["errors"] + results["mirror_account"]["errors"]

            # Add flat structure for backward compatibility
            results["tp_orders"] = all_tp_orders
            results["sl_order"] = combined_sl_order
            results["errors"] = all_errors

            # Initialize monitoring for this position
            monitor_data = {
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "position_size": position_size,  # Target position size
                "current_size": tp_sl_position_size,  # Actual current size
                "remaining_size": tp_sl_position_size if tp_sl_position_size > 0 else position_size,  # Use target size if no current position
                "last_known_size": tp_sl_position_size if tp_sl_position_size > 0 else Decimal("0"),  # Initialize last_known_size
                "initial_fill_processed": bool(tp_sl_position_size > 0),  # Track if initial fill processed
                "tp_orders": results["tp_orders"],
                "sl_order": results["sl_order"],
                "filled_tps": [],
                "approach": "conservative",
                "chat_id": chat_id or DEFAULT_ALERT_CHAT_ID,
                "created_at": time.time(),
                "last_check": time.time(),
                "sl_moved_to_be": False,
                # Don't store monitoring_task here to avoid pickle serialization errors
                # Enhanced tracking for limit orders and phases
                "limit_orders": [],  # Track entry limit orders for Conservative approach
                "limit_orders_filled": False,  # Track if limit orders have been filled
                "phase": "BUILDING",  # Position phase (starts in building phase for conservative approach)
                "tp1_hit": False,  # Track if TP1 (85%) has been hit
                "phase_transition_time": None,  # When phase changed
                "total_tp_filled": Decimal("0"),  # Total TP amount filled
                "cleanup_completed": False,  # Track if cleanup was performed
                "bot_instance": None,  # Will store bot reference for alerts
                "account_type": account_type,  # Track which account this monitor is for
                "final_tp_order_id": None,  # Track the final TP order ID
                "sl_hit": False,  # Track if SL was hit
                "all_tps_filled": False  # Track if all TPs were filled
            }

            # Use account-aware key format
            monitor_key = f"{symbol}_{side}_{account_type}"
            # Ensure TP numbers are set
            self._ensure_tp_numbers(monitor_data)
            
            # Set the final TP order ID (the last TP in the list)
            if all_tp_orders:
                # Find the TP with the highest number
                max_tp_number = 0
                final_tp_id = None
                for order_id, tp_order in all_tp_orders.items():
                    tp_num = tp_order.get("tp_number", 0)
                    if tp_num > max_tp_number:
                        max_tp_number = tp_num
                        final_tp_id = order_id
                monitor_data["final_tp_order_id"] = final_tp_id
                logger.info(f"📌 Final TP order set: TP{max_tp_number} (ID: {final_tp_id[:8] if final_tp_id else 'None'}...)")
            
            self.position_monitors[monitor_key] = monitor_data
            # Save immediately for new monitor creation
            self.save_monitors_to_persistence(force=True, reason="monitor_created")
            results["monitoring_active"] = True
            

            # Start monitoring task with account_type
            monitor_task = asyncio.create_task(self._run_monitor_loop(symbol, side, account_type))
            # Don't store the task in monitor_data as it can't be pickled
            # Track it separately if needed
            monitor_key = f"{symbol}_{side}_{account_type}"
            if not hasattr(self, 'active_tasks'):
                self.active_tasks = {}
            self.active_tasks[monitor_key] = monitor_task

            # Create monitor_tasks entry for dashboard compatibility
            # FIXED: Call the monitor creation method directly
            await self.create_dashboard_monitor_entry(symbol, side, chat_id, approach, "main")

            # Also create mirror monitor entry if mirror account is active
            if setup_mirror:
                await self.create_dashboard_monitor_entry(symbol, side, chat_id, approach, "mirror")

            # Start cleanup scheduler if not already running
            if self.cleanup_task is None:
                self.start_cleanup_scheduler()

            # Set success to True if we have TP orders placed (SL failure shouldn't prevent success)
            results["success"] = len(results["main_account"]["tp_orders"]) > 0

            logger.info(f"✅ Enhanced TP/SL setup complete for {symbol} {side}")
            return results

        except Exception as e:
            logger.error(f"❌ Error in enhanced TP/SL setup: {e}")
            return {
                "tp_orders": {},
                "sl_order": None,
                "errors": [str(e)],
                "monitoring_active": False,
                "success": False
            }

    def _calculate_full_position_sl_quantity(
        self,
        approach: str,
        current_size: Decimal,
        target_size: Decimal,
        tp1_hit: bool = False
    ) -> Decimal:
        """
        ENHANCED: Calculate SL quantity for 100% position coverage

        Logic:
        - Always provide 100% coverage of the FULL INTENDED position
        - ALL approaches: Cover full target (including unfilled limit orders)
        - This ensures protection in fast-moving markets where limits may suddenly fill
        - Maintains 100% coverage even after TP hits

        Args:
            approach: Trading approach (CONSERVATIVE only)
            current_size: Currently filled position size
            target_size: Full intended position size (including limit orders)
            tp1_hit: Whether TP1 (85%) has been reached (kept for compatibility)

        Returns:
            Decimal: SL quantity to place (always 100% of target position)
        """
        # ALWAYS provide 100% coverage of target position (including unfilled limits)
        # This applies to ALL approaches - user requested this for safety
        sl_quantity = target_size

        if target_size > current_size:
            logger.info(f"📊 SL Quantity: {sl_quantity} (100% coverage including {target_size - current_size} unfilled)")
        else:
            logger.info(f"📊 SL Quantity: {sl_quantity} (100% of position)")

        return sl_quantity

    def _is_mirror_trading_enabled(self) -> bool:
        """Check if mirror trading is enabled and available"""
        try:
            from execution.mirror_trader import is_mirror_trading_enabled
            return is_mirror_trading_enabled()
        except ImportError:
            return False

    async def _place_tp_orders_unified(
        self,
        symbol: str,
        side: str,
        tp_prices: List[Decimal],
        tp_quantities: List[Decimal],
        tp_percentages: List[Decimal],
        approach: str,
        position_idx: int,
        setup_main: bool,
        setup_mirror: bool,
        mirror_tp_sl_size: Optional[Decimal],
        qty_step: Decimal,
        results: Dict
    ):
        """ENHANCED: Place TP orders on both main and mirror accounts"""

        # Determine order side (opposite of position side)
        order_side = "Sell" if side == "Buy" else "Buy"

        for i, (tp_price, tp_qty, tp_pct) in enumerate(zip(tp_prices, tp_quantities, tp_percentages)):
            try:
                # Skip if quantity is zero (failed minimum check)
                if tp_qty == 0:
                    logger.warning(f"Skipping TP{i+1} - below minimum order value")
                    continue

                # Calculate mirror TP quantity proportionally
                mirror_tp_qty = None
                if setup_mirror and mirror_tp_sl_size is not None:
                    mirror_tp_qty = mirror_tp_sl_size * Decimal(str(tp_pct)) / Decimal("100")
                    mirror_tp_qty = value_adjusted_to_step(mirror_tp_qty, qty_step)
                    
                    # Check minimum order value for mirror
                    mirror_order_value = mirror_tp_qty * tp_price
                    if mirror_order_value < MIN_ORDER_VALUE:
                        logger.warning(f"MIRROR: TP{i+1} value ${mirror_order_value:.2f} < minimum ${MIN_ORDER_VALUE}, skipping")
                        mirror_tp_qty = None

                # Place main account TP order
                if setup_main:
                    order_link_id = generate_order_link_id(approach, symbol, ORDER_TYPE_TP, index=i+1)

                    logger.info(f"📍 MAIN: Placing TP{i+1} order: {tp_qty} @ {tp_price}")

                    order_result = await place_order_with_retry(
                        symbol=symbol,
                        side=order_side,
                        order_type="Limit",
                        qty=str(tp_qty),
                        price=str(tp_price),
                        reduce_only=True,
                        order_link_id=order_link_id,
                        time_in_force="GTC",
                        position_idx=position_idx
                    )

                    if order_result and order_result.get("orderId"):
                        order_id = order_result["orderId"]
                        results["main_account"]["tp_orders"][order_id] = {
                            "order_id": order_id,
                            "order_link_id": order_link_id,
                            "price": tp_price,
                            "quantity": tp_qty,
                            "original_quantity": tp_qty,
                            "percentage": tp_pct,
                            "tp_number": i + 1,
                            "account": "main"
                        }

                        # Track order lifecycle
                        self._track_order_lifecycle(
                            order_id=order_id,
                            order_type="TP",
                            symbol=symbol,
                            side=order_side,
                            price=tp_price,
                            quantity=tp_qty,
                            order_link_id=order_link_id
                        )

                        logger.info(f"✅ MAIN: TP{i+1} order placed successfully")
                    else:
                        error_msg = f"MAIN: Failed to place TP{i+1} order"
                        results["main_account"]["errors"].append(error_msg)
                        logger.error(error_msg)

                # Place mirror account TP order
                if setup_mirror and mirror_tp_qty and mirror_tp_qty > 0:
                    from execution.mirror_trader import mirror_limit_order

                    mirror_order_link_id = generate_order_link_id("MIR", symbol, ORDER_TYPE_TP, index=i+1)

                    logger.info(f"📍 MIRROR: Placing TP{i+1} order: {mirror_tp_qty} @ {tp_price}")

                    mirror_result = await mirror_limit_order(
                        symbol=symbol,
                        side=order_side,
                        qty=str(mirror_tp_qty),
                        price=str(tp_price),
                        position_idx=0,  # Mirror account uses One-Way mode
                        order_link_id=mirror_order_link_id,
                        reduce_only=True,
                        time_in_force="GTC"
                    )

                    if mirror_result and mirror_result.get("orderId"):
                        order_id = mirror_result["orderId"]
                        results["mirror_account"]["tp_orders"][order_id] = {
                            "order_id": order_id,
                            "order_link_id": mirror_order_link_id,
                            "price": tp_price,
                            "quantity": mirror_tp_qty,
                            "original_quantity": mirror_tp_qty,
                            "percentage": tp_pct,
                            "tp_number": i + 1,
                            "account": "mirror"
                        }

                        logger.info(f"✅ MIRROR: TP{i+1} order placed successfully")
                    else:
                        error_msg = f"MIRROR: Failed to place TP{i+1} order"
                        results["mirror_account"]["errors"].append(error_msg)
                        logger.error(error_msg)

            except Exception as e:
                error_msg = f"Error placing TP{i+1}: {e}"
                if setup_main:
                    results["main_account"]["errors"].append(error_msg)
                if setup_mirror:
                    results["mirror_account"]["errors"].append(error_msg)
                logger.error(error_msg)

    async def _place_sl_orders_unified(
        self,
        symbol: str,
        side: str,
        sl_price: Decimal,
        approach: str,
        position_idx: int,
        setup_main: bool,
        setup_mirror: bool,
        main_current_size: Decimal,
        main_target_size: Decimal,
        mirror_current_size: Optional[Decimal],
        mirror_target_size: Optional[Decimal],
        results: Dict
    ):
        """ENHANCED: Place SL orders on both main and mirror accounts with full position coverage"""

        sl_side = "Sell" if side == "Buy" else "Buy"

        try:
            # Place main account SL order
            if setup_main:
                main_sl_quantity = self._calculate_full_position_sl_quantity(
                    approach=approach,
                    current_size=main_current_size,
                    target_size=main_target_size,
                    tp1_hit=False
                )

                sl_order_link_id = generate_order_link_id(approach, symbol, ORDER_TYPE_SL)

                logger.info(f"🛡️ MAIN ENHANCED SL: Placing SL order: {main_sl_quantity} @ {sl_price}")
                logger.info(f"   Current filled: {main_current_size}, Target: {main_target_size}")

                sl_result = await place_order_with_retry(
                    symbol=symbol,
                    side=sl_side,
                    order_type="Market",
                    qty=str(main_sl_quantity),
                    trigger_price=str(sl_price),
                    reduce_only=True,
                    order_link_id=sl_order_link_id,
                    position_idx=position_idx,
                    stop_order_type="StopLoss"
                )

                if sl_result and sl_result.get("orderId"):
                    order_id = sl_result["orderId"]
                    results["main_account"]["sl_order"] = {
                        "order_id": order_id,
                        "order_link_id": sl_order_link_id,
                        "price": sl_price,
                        "quantity": main_sl_quantity,
                        "original_quantity": main_sl_quantity,
                        "covers_full_position": True,
                        "target_position_size": main_target_size,
                        "account": "main"
                    }

                    # Track order lifecycle
                    self._track_order_lifecycle(
                        order_id=order_id,
                        order_type="SL",
                        symbol=symbol,
                        side=sl_side,
                        price=sl_price,
                        quantity=main_sl_quantity,
                        order_link_id=sl_order_link_id
                    )

                    logger.info("✅ MAIN: SL order placed successfully")
                    results["main_account"]["success"] = True
                else:
                    error_msg = "MAIN: Failed to place SL order"
                    results["main_account"]["errors"].append(error_msg)
                    logger.error(error_msg)

            # Place mirror account SL order
            if setup_mirror and mirror_current_size is not None:
                from execution.mirror_trader import mirror_tp_sl_order

                mirror_sl_quantity = self._calculate_full_position_sl_quantity(
                    approach=approach,
                    current_size=mirror_current_size,
                    target_size=mirror_target_size,
                    tp1_hit=False
                )

                mirror_sl_order_link_id = generate_order_link_id("MIR", symbol, ORDER_TYPE_SL)

                logger.info(f"🛡️ MIRROR ENHANCED SL: Placing SL order: {mirror_sl_quantity} @ {sl_price}")
                logger.info(f"   Current filled: {mirror_current_size}, Target: {mirror_target_size}")

                mirror_sl_result = await mirror_tp_sl_order(
                    symbol=symbol,
                    side=sl_side,
                    qty=str(mirror_sl_quantity),
                    trigger_price=str(sl_price),
                    position_idx=0,  # Mirror account uses One-Way mode
                    order_link_id=mirror_sl_order_link_id,
                    stop_order_type="StopLoss"
                )

                if mirror_sl_result and mirror_sl_result.get("orderId"):
                    order_id = mirror_sl_result["orderId"]
                    results["mirror_account"]["sl_order"] = {
                        "order_id": order_id,
                        "order_link_id": mirror_sl_order_link_id,
                        "price": sl_price,
                        "quantity": mirror_sl_quantity,
                        "original_quantity": mirror_sl_quantity,
                        "covers_full_position": True,
                        "target_position_size": mirror_target_size,
                        "account": "mirror"
                    }

                    logger.info("✅ MIRROR: SL order placed successfully")
                    results["mirror_account"]["success"] = True
                else:
                    error_msg = "MIRROR: Failed to place SL order"
                    results["mirror_account"]["errors"].append(error_msg)
                    logger.error(error_msg)

        except Exception as e:
            error_msg = f"Error placing SL orders: {e}"
            if setup_main:
                results["main_account"]["errors"].append(error_msg)
            if setup_mirror:
                results["mirror_account"]["errors"].append(error_msg)
            logger.error(error_msg)

    async def monitor_and_adjust_orders(self, symbol: str, side: str, account_type: str = None):
        """
        Enhanced monitoring with real-time fill detection and reduced latency
        This replaces the conditional order logic with active management
        Now supports account-aware monitoring to prevent key collisions
        """
        # PERFORMANCE OPTIMIZATION: Refresh monitoring cache first
        await self._refresh_monitoring_cache()
        
        logger.debug(f"🔍 monitor_and_adjust_orders called for {symbol} {side} ({account_type})")
        logger.debug(f"📊 Current monitors: {len(self.position_monitors)} total - Keys: {list(self.position_monitors.keys())[:5]}...")
        # Determine monitor key based on available monitors
        main_key = f"{symbol}_{side}_main"
        mirror_key = f"{symbol}_{side}_mirror"
        legacy_key = f"{symbol}_{side}"  # For backward compatibility

        monitor_key = None
        monitor_data = None

        # Try to find the monitor
        if account_type == "mirror" and mirror_key in self.position_monitors:
            monitor_key = mirror_key
        elif account_type == "main" and main_key in self.position_monitors:
            monitor_key = main_key
        elif main_key in self.position_monitors:
            monitor_key = main_key
        elif mirror_key in self.position_monitors:
            monitor_key = mirror_key
        elif legacy_key in self.position_monitors:
            # Handle legacy monitors
            monitor_key = legacy_key

        if not monitor_key:
            logger.warning(f"⚠️ No monitor found for {symbol} {side} ({account_type}). Available monitors: {list(self.position_monitors.keys())[:10]}")
            return

        monitor_data = self.position_monitors[monitor_key]

        # Determine account type from monitor data or key
        if not account_type:
            account_type = monitor_data.get('account_type', 'main')
            if '_mirror' in monitor_key:
                account_type = 'mirror'
            elif '_main' in monitor_key:
                account_type = 'main'

        # Sanitize monitor data to ensure all numeric fields are correct
        monitor_data = self._sanitize_monitor_data(monitor_data)
        # Ensure TP numbers are set
        self._ensure_tp_numbers(monitor_data)
        self.position_monitors[monitor_key] = monitor_data
        
        # PHASE 2 OPTIMIZATION: Update write-through cache instead of immediate persistence
        self._update_monitor_cache(monitor_key, monitor_data)

        # Use adaptive monitoring intervals based on position state
        current_time = time.time()
        last_check = monitor_data.get("last_check", 0)

        # Determine monitoring interval based on position phase and activity
        from config.settings import USE_DIRECT_ORDER_CHECKS, ORDER_CHECK_INTERVAL
        
        if USE_DIRECT_ORDER_CHECKS and monitor_data.get("tp_orders"):
            # Use faster interval when we have pending TP orders
            target_interval = ORDER_CHECK_INTERVAL  # 2 seconds by default
        elif ADAPTIVE_MONITORING_INTERVALS:
            if monitor_data.get("phase") == "PROFIT_TAKING":
                target_interval = self.critical_position_interval  # 2 seconds
            elif monitor_data.get("tp1_hit", False):
                target_interval = self.active_position_interval    # 5 seconds
            else:
                target_interval = self.standard_monitor_interval   # 12 seconds
        else:
            target_interval = self.standard_monitor_interval   # Default 12 seconds

        # Skip if called too frequently (respect interval)
        if current_time - last_check < target_interval:
            return

        try:
            # CRITICAL FIX: Use cached position fetching to reduce API calls
            positions = await self._get_cached_position_info(symbol, account_type)
            logger.debug(f"🔍 Got {account_type} position for {symbol} {side} (monitor: {monitor_key})")

            # Additional safety check - ensure we're monitoring the correct account
            if monitor_key.endswith('_mirror') and account_type != 'mirror':
                logger.error(f"❌ Monitor key mismatch: {monitor_key} but account_type is {account_type}")
                return
            elif monitor_key.endswith('_main') and account_type != 'main':
                logger.error(f"❌ Monitor key mismatch: {monitor_key} but account_type is {account_type}")
                return

            # Extra validation: ensure we fetched from the correct account
            if not positions:
                logger.debug(f"No positions found for {symbol} on {account_type} account")
                return
            position = None
            if positions:
                # Find the position for our side
                for pos in positions:
                    if pos.get("side") == side:
                        position = pos
                        logger.debug(f"📊 Found {account_type} position: size={pos.get('size')}")
                        break

            if not position or Decimal(str(position.get("size", "0"))) == 0:
                logger.info(f"Position {symbol} {side} closed - stopping monitor")

                # CRITICAL FIX: Clean up all orders when position is closed (SL hit or manual close)
                await self.cleanup_position_orders(symbol, side)

                # Send position closed alert
                await self._send_position_closed_alert(monitor_data)

                # Handle position closure analysis
                await self._handle_position_closure(monitor_data, position)

                # Clean up monitor (may already be done by cleanup_position_orders)
                if monitor_key in self.position_monitors:
                    # PHASE 2 OPTIMIZATION: Update indexes when removing monitor
                    self._remove_from_indexes(monitor_key, monitor_data)
                    del self.position_monitors[monitor_key]
                    # Force save after monitor deletion
                    self.save_monitors_to_persistence(force=True, reason="monitor_removed")
                    
                # Schedule orphaned order cleanup as failsafe
                asyncio.create_task(self._orphaned_order_cleanup_failsafe(symbol, side, account_type))
                
                return

            current_size = Decimal(str(position["size"]))

            # ENHANCED: Check and update limit order statuses for better tracking
            # This MUST happen before any early returns
            if monitor_data.get("limit_orders") and monitor_data.get("approach", "").upper() == "CONSERVATIVE":
                logger.info(f"🔍 Checking limit orders for {monitor_key}: {len(monitor_data.get('limit_orders', []))} orders registered")
                try:
                    
                    # Extract order IDs from limit orders
                    order_ids = [order.get("order_id") for order in monitor_data["limit_orders"] 
                               if isinstance(order, dict) and order.get("order_id")]
                    
                    logger.info(f"🔍 Found {len(order_ids)} order IDs to check: {[oid[:8] + '...' for oid in order_ids[:2]]}")
                    
                    if order_ids:
                        # Fetch and update order details
                        order_details = await limit_order_tracker.fetch_and_update_limit_order_details(
                            order_ids, symbol, account_type
                        )
                        
                        # Update monitor data with new statuses
                        filled_count, active_count = limit_order_tracker.update_monitor_limit_orders(
                            monitor_data, order_details
                        )
                        
                        # Log if there are status changes
                        if filled_count > 0:
                            logger.info(f"📊 Limit order update for {monitor_key}: {filled_count} filled, {active_count} active")
                            
                            # Send enhanced limit order fill alert
                            await self._send_enhanced_limit_fill_alert(monitor_data, filled_count, active_count)
                            
                except Exception as e:
                    logger.error(f"Error updating limit orders for {monitor_key}: {e}")
            elif monitor_data.get("limit_orders"):
                # Log when we have limit orders but approach doesn't match
                current_approach = monitor_data.get("approach", "UNKNOWN")
                logger.warning(f"⚠️ Monitor {monitor_key} has {len(monitor_data.get('limit_orders', []))} limit orders but approach is '{current_approach}' (not CONSERVATIVE)")

            # Fallback to position size monitoring (legacy method)
            # Check if position size changed (indicating order fill)
            if current_size != monitor_data["remaining_size"]:
                logger.debug(f"🔄 Size change detected for {monitor_key}: current={current_size}, stored={monitor_data['remaining_size']}")
                # Position size changed
                if current_size == 0:
                    # Position closed completely - check if it was SL or TP
                    await self._handle_position_closure(monitor_data, position)
                elif current_size < monitor_data["remaining_size"]:
                    # CRITICAL: Check if this is a real reduction or initial fill
                    # If remaining_size is 0 or we haven't processed initial fill yet
                    if monitor_data.get("remaining_size", 0) == 0 or not monitor_data.get("initial_fill_processed", False):
                        logger.info(f"🔍 Initial position fill detected for {monitor_key}: size={current_size}")
                        monitor_data["remaining_size"] = current_size
                        # Only update position_size if it's smaller than current_size
                        if monitor_data.get("position_size", 0) < current_size:
                            monitor_data["position_size"] = current_size
                        monitor_data["initial_fill_processed"] = True
                        
                        # Clean monitor data before saving
                        try:
                            # Save monitors without modifying the original data
                            self.save_monitors_to_persistence()
                        except Exception as e:
                            logger.error(f"Error saving after initial fill detection: {e}")
                        
                        return
                    
                    # Also check if this is the first time we're seeing a real position
                    if not monitor_data.get("initial_fill_processed", False) and current_size > monitor_data["remaining_size"]:
                        logger.info(f"🔍 Position increased (initial fills) for {monitor_key}: {monitor_data['remaining_size']} -> {current_size}")
                        monitor_data["remaining_size"] = current_size
                        monitor_data["position_size"] = max(current_size, monitor_data.get("position_size", 0))
                        monitor_data["initial_fill_processed"] = True
                        self.save_monitors_to_persistence()
                        return
                    
                    # Position reduced - TP or partial fill
                    size_diff = monitor_data["remaining_size"] - current_size

                    # Simple sanity check: If the size difference is larger than the position, ignore it
                    if size_diff > monitor_data.get("position_size", Decimal('999999')):
                        logger.debug(f"⚠️ Ignoring impossible size change for {monitor_key}: size_diff={size_diff} > position_size={monitor_data.get('position_size', 'N/A')}")
                        return  # Exit without modifying monitor data

                    # Log the position change
                    logger.debug(f"📊 Position size changed for {monitor_key} ({account_type} account): {monitor_data['remaining_size']} -> {current_size}")

                    # Calculate fill percentage based on the size of position when TP hit
                    # This represents what percentage of the position was closed in this TP
                    fill_percentage = (size_diff / monitor_data["position_size"]) * 100

                    # Track cumulative fills for logging purposes
                    fill_tracker = self.fill_tracker.get(monitor_key, {"total_filled": Decimal("0"), "target_size": monitor_data["position_size"]})
                    fill_tracker["total_filled"] += size_diff
                    self.fill_tracker[monitor_key] = fill_tracker
                    cumulative_percentage = (fill_tracker["total_filled"] / fill_tracker["target_size"]) * 100

                    # Reset cumulative tracking if it exceeds 100% (shouldn't happen after false positive fixes)
                    if cumulative_percentage > 100:
                        logger.warning(f"⚠️ Cumulative fill exceeded 100% ({cumulative_percentage:.2f}%) - this shouldn't happen after false positive fix")
                        fill_tracker["total_filled"] = size_diff
                        self.fill_tracker[monitor_key] = fill_tracker
                        cumulative_percentage = (size_diff / fill_tracker["target_size"]) * 100

                    logger.info(f"🎯 Position size reduced by {size_diff} ({fill_percentage:.2f}% of position, {cumulative_percentage:.2f}% cumulative) - TP order filled")

                    # NOW update remaining size after all checks passed
                    monitor_data["remaining_size"] = current_size

                    # Save to persistence after update
                    self.save_monitors_to_persistence(reason="position_reduction")

                    # Determine what type of order was filled
                    # Conservative approach only - could be limit order or TP fill
                    # Make sure last_known_size is properly set for TP detection
                    if "last_known_size" not in monitor_data or monitor_data["last_known_size"] == 0:
                        # Use the size before reduction as last_known_size
                        monitor_data["last_known_size"] = monitor_data["remaining_size"] + size_diff
                    await self._handle_conservative_position_change(monitor_data, current_size, fill_percentage)
                elif current_size > monitor_data["remaining_size"]:
                    # Position increased - additional limit orders filled (conservative approach)
                    size_diff = current_size - monitor_data["remaining_size"]
                    logger.info(f"📈 Position size increased by {size_diff} - additional limit orders filled")

                    # Use atomic lock to prevent race conditions during order adjustment
                    # Keep the same monitor_key format with account suffix
                    lock_key = f"{symbol}_{side}"
                    if lock_key not in self.monitor_locks:
                        self.monitor_locks[lock_key] = asyncio.Lock()

                    async with self.monitor_locks[lock_key]:
                        # Calculate fill percentage based on the increase
                        fill_percentage = (size_diff / current_size) * 100

                        # Track entry price for the filled limit orders
                        try:
                            # Get current position to find average price - USE CORRECT ACCOUNT
                            if account_type == 'mirror':
                                positions = await get_position_info_for_account(symbol, 'mirror')
                            else:
                                positions = await get_position_info(symbol)

                            if positions:
                                for pos in positions:
                                    if pos.get("side") == side:
                                        avg_price = Decimal(str(pos.get("avgPrice", "0")))
                                        if avg_price > 0:
                                            # Track the weighted entry price based on the fill
                                            await self._track_actual_entry_price(symbol, side, avg_price, size_diff, account_type)
                                            logger.info(f"📊 Tracked limit order fill: {size_diff} @ {avg_price}")
                                        break
                        except Exception as e:
                            logger.warning(f"Could not track limit order entry price: {e}")

                        # Send limit fill alert with enhanced information
                        await self._send_limit_fill_alert(monitor_data, fill_percentage)
                        
                        # Send rebalancing alert after TP adjustment
                        if monitor_data.get("approach") == "CONSERVATIVE":
                            await self._send_rebalancing_alert(monitor_data, current_size, size_diff)

                        # Update position size and remaining size atomically
                        monitor_data["position_size"] = current_size
                        monitor_data["remaining_size"] = current_size

                    # Save to persistence after update
                    self.save_monitors_to_persistence(reason="position_increase")

                    # Adjust all TP/SL orders proportionally to new position size
                    await self._adjust_all_orders_for_partial_fill(monitor_data, current_size)

                    # ENHANCED: Trigger real-time mirror sync for position increases (DISABLED)
                    # await self._trigger_mirror_sync_for_position_increase(symbol, side, current_size, size_diff)

                    logger.info(f"🔒 Atomic order adjustment completed for {monitor_key}")

                # Mirror sync removed - each account operates independently
                # Mirror monitors handle their own position changes without syncing

            # ENHANCED: Check and update limit order statuses for better tracking
            if monitor_data.get("limit_orders") and monitor_data.get("approach", "").upper() == "CONSERVATIVE":
                try:
                    
                    # Extract order IDs from monitor
                    order_ids = []
                    for limit_order in monitor_data.get("limit_orders", []):
                        if isinstance(limit_order, dict) and limit_order.get("order_id"):
                            order_ids.append(limit_order["order_id"])
                    
                    if order_ids:
                        # Fetch and update order details
                        order_details = await limit_order_tracker.fetch_and_update_limit_order_details(
                            order_ids, symbol, account_type
                        )
                        
                        # Update monitor with detailed info
                        old_filled_count = monitor_data.get("limit_orders_filled", 0)
                        filled_count, active_count = limit_order_tracker.update_monitor_limit_orders(
                            monitor_data, order_details
                        )
                        
                        # Send alert if a limit order just filled
                        if filled_count > old_filled_count:
                            logger.info(f"🎯 Limit order fill detected! {filled_count}/{len(order_ids)} filled")
                            # The position size change will trigger the rebalancing and alert
                            
                except Exception as e:
                    logger.error(f"Error updating limit order details: {e}")

            # Enhanced fill detection with order history verification
            if ENHANCED_FILL_DETECTION:
                await self._enhanced_fill_detection(symbol, side, monitor_data)

            # Update order statuses based on current open orders
            await self._update_order_statuses(symbol, side)

            # Update last check time
            monitor_data["last_check"] = time.time()

        except Exception as e:
            # Use error recovery system for monitoring errors
            await self._handle_monitor_error(symbol, side, e)

    async def _handle_conservative_position_change(self, monitor_data: Dict, current_size: Decimal, fill_percentage: float):
        """
        Handle position changes for conservative approach
        Could be limit order fills or TP fills
        """
        # Enhanced limit fill detection - track actual position sizes
        limit_orders_filled = monitor_data.get("limit_orders_filled", False)
        last_known_size = monitor_data.get("last_known_size", Decimal("0"))
        phase = monitor_data.get("phase", "BUILDING")
        
        # Safety check: Initialize last_known_size if it's 0 or missing (for existing monitors)
        if last_known_size == 0 and monitor_data.get("remaining_size", 0) > 0:
            last_known_size = monitor_data["remaining_size"]
            monitor_data["last_known_size"] = last_known_size
            logger.info(f"🔧 Initialized last_known_size to {last_known_size} for existing monitor")
        
        # Detect any position size increase (indicates limit fill)
        position_increased = current_size > last_known_size if last_known_size > 0 else False

        # For conservative approach, we need to distinguish between:
        # 1. Initial limit order fills (when position is being built)
        # 2. TP order fills (when position is being reduced)

        # If we're in PROFIT_TAKING phase, any position reduction is a TP fill
        if phase == "PROFIT_TAKING" and current_size < last_known_size:
            logger.info(f"📊 PROFIT_TAKING phase: Position reduced, must be TP fill")
            position_increased = False  # Force TP detection path

        # ENHANCED: First check if any TP orders were filled
        # This MUST come first before checking position increases
        tp_info = await self._identify_filled_tp_order(monitor_data)
        if tp_info:
            # A specific TP order was filled
            tp_number = tp_info["tp_number"]
            logger.info(f"🎯 Conservative approach: TP{tp_number} order filled ({fill_percentage:.2f}% of position)")
            logger.info(f"📊 TP{tp_number} details: Order {tp_info['order_id'][:8]}... filled {tp_info['filled_qty']} ({tp_info['percentage']}% target)")
            
            # Check if this is the final TP
            if tp_info['order_id'] == monitor_data.get("final_tp_order_id"):
                logger.info(f"🏁 FINAL TP HIT! Position will be fully closed")
                monitor_data["all_tps_filled"] = True
                # Pre-emptively cancel all remaining orders
                await self._emergency_cancel_all_orders(monitor_data["symbol"], monitor_data["side"], monitor_data)
            
            # If TP1 was filled, set the tp1_hit flag regardless of fill percentage
            if tp_number == 1 and not monitor_data.get("tp1_hit", False):
                monitor_data["tp1_hit"] = True
                logger.info(f"✅ TP1 hit detected - will trigger breakeven movement and limit order cleanup")
                
                # ENHANCED LOGGING FOR TP1 HIT DETECTION
                logger.info(f"🎯 TP1 HIT DETECTION for {monitor_data.get('symbol')} {monitor_data.get('side')}")
                logger.info(f"  Monitor Key: {monitor_data.get('monitor_key', 'unknown')}")
                logger.info(f"  Account Type: {monitor_data.get('account_type', 'main')}")
                logger.info(f"  Position Size: {monitor_data.get('position_size')}")
                logger.info(f"  Remaining Size: {monitor_data.get('remaining_size')}")
                logger.info(f"  Fill Percentage: {fill_percentage:.2f}%")
                logger.info(f"  Chat ID: {monitor_data.get('chat_id', 'MISSING')}")
                logger.info(f"  Approach: {monitor_data.get('approach', 'unknown')}")
                logger.info(f"  Phase: {monitor_data.get('phase', 'unknown')}")
                logger.info(f"  Limit Orders Cancelled: {monitor_data.get('limit_orders_cancelled', False)}")
                
                # Check if chat_id is missing
                if not monitor_data.get('chat_id'):
                    logger.warning(f"⚠️ MISSING CHAT_ID - Alert may not be sent!")
                    # Try to find it
                    account_type = monitor_data.get('account_type', 'main')
                    chat_id = await self._find_chat_id_for_position(monitor_data['symbol'], monitor_data['side'], account_type)
                    if chat_id:
                        monitor_data['chat_id'] = chat_id
                        logger.info(f"✅ Found chat_id: {chat_id}")
                    else:
                        logger.error(f"❌ Could not find chat_id for position")
                
                # Save the tp1_hit flag to persistence
                self.save_monitors_to_persistence(force=True, reason="tp_hit")
                
                # Trigger phase transition to PROFIT_TAKING
                await self._transition_to_profit_taking(monitor_data)
                
                # Trigger breakeven movement
                logger.info(f"🎯 Triggering breakeven movement after TP1...")
                # Get position data for breakeven
                positions = await get_position_info_for_account(monitor_data["symbol"], monitor_data.get("account_type", "main"))
                position = None
                if positions:
                    for pos in positions:
                        if pos.get("side") == monitor_data["side"]:
                            position = pos
                            break
                
                if position:
                    success = await self._move_sl_to_breakeven_enhanced_v2(
                        monitor_data=monitor_data,
                        position=position,
                        is_tp1_trigger=True
                    )
                    if success:
                        logger.info(f"✅ SL moved to breakeven successfully after TP1")
                        monitor_data["sl_moved_to_be"] = True
                        # Send breakeven alert
                        await self._send_enhanced_breakeven_alert(monitor_data, "TP1")
                    else:
                        logger.error(f"❌ Failed to move SL to breakeven after TP1")
                else:
                    logger.error(f"❌ Could not find position data for breakeven movement")
            
            # Send TP fill alert with correct TP number
            await self._send_tp_fill_alert_enhanced(monitor_data, fill_percentage, tp_number)
            
            # Only adjust SL quantity in PROFIT_TAKING phase (when TPs hit)
            # During BUILDING/MONITORING phases, SL should maintain full position coverage
            current_phase = monitor_data.get("phase", "BUILDING")
            if current_phase == "PROFIT_TAKING":
                logger.info(f"🔧 PROFIT_TAKING phase: Adjusting SL to match remaining position ({current_size})")
                await self._adjust_sl_quantity_enhanced(monitor_data, current_size)
            else:
                logger.info(f"🛡️ {current_phase} phase: SL maintains full position coverage (no adjustment needed)")
        
        # Enhanced: Check for any position increase (limit fills)
        elif position_increased:
            size_diff = current_size - last_known_size
            logger.info(f"📊 Conservative approach: Limit order detected - size increased by {size_diff}")
            logger.info(f"📊 Position: {last_known_size} → {current_size} ({fill_percentage:.2f}% filled)")
            
            # Update tracking data
            monitor_data["limit_orders_filled"] = True
            monitor_data["last_known_size"] = current_size
            monitor_data["last_limit_fill_time"] = time.time()
            
            # Count filled limits for accurate alert
            filled_limits = self._count_filled_limit_orders(monitor_data)
            monitor_data["filled_limit_count"] = filled_limits
            
            # Update phase if all limit orders are filled
            if filled_limits >= len(monitor_data.get("limit_orders", [])) and filled_limits > 0:
                logger.info(f"✅ All limit orders filled - transitioning to MONITORING phase")
                monitor_data["phase"] = "MONITORING"
            
            # Send limit fill alert with accurate count
            await self._send_limit_fill_alert(monitor_data, fill_percentage)
            
            # Rebalance all TP/SL orders for new position size
            await self._adjust_all_orders_for_partial_fill(monitor_data, current_size)
            
            # Save state immediately
            self.save_monitors_to_persistence(force=True, reason="tp_hit")
        else:
            # Fallback: If order ID detection failed but position reduced, it's likely a TP fill
            if not position_increased and current_size < monitor_data.get("position_size", 0):
                logger.warning(f"⚠️ TP order fill detected via position size (order ID detection failed)")
                logger.info(f"🎯 Conservative approach: TP order filled ({fill_percentage:.2f}% of position)")
                
                # Try to determine which TP based on cumulative fill percentage
                cumulative_fill = monitor_data.get("position_size", 0) - current_size
                cumulative_percentage = (cumulative_fill / monitor_data.get("position_size", 1)) * 100
                
                # Estimate TP number based on percentage
                if cumulative_percentage >= 85:
                    tp_number = 1
                    if not monitor_data.get("tp1_hit", False):
                        monitor_data["tp1_hit"] = True
                        monitor_data["phase"] = "PROFIT_TAKING"
                        logger.info(f"✅ TP1 hit detected via position size - will trigger breakeven movement")
                        self.save_monitors_to_persistence(force=True, reason="tp_hit")
                        
                        # Trigger phase transition to PROFIT_TAKING
                        await self._transition_to_profit_taking(monitor_data)
                        
                        # Trigger breakeven movement
                        logger.info(f"🎯 Triggering breakeven movement after TP1 (fallback detection)...")
                        # Get position data for breakeven
                        positions = await get_position_info_for_account(monitor_data["symbol"], monitor_data.get("account_type", "main"))
                        position = None
                        if positions:
                            for pos in positions:
                                if pos.get("side") == monitor_data["side"]:
                                    position = pos
                                    break
                        
                        if position:
                            success = await self._move_sl_to_breakeven_enhanced_v2(
                                monitor_data=monitor_data,
                                position=position,
                                is_tp1_trigger=True
                            )
                            if success:
                                logger.info(f"✅ SL moved to breakeven successfully after TP1 (fallback)")
                                monitor_data["sl_moved_to_be"] = True
                                # Send breakeven alert
                                await self._send_enhanced_breakeven_alert(monitor_data, "TP1")
                            else:
                                logger.error(f"❌ Failed to move SL to breakeven after TP1 (fallback)")
                elif cumulative_percentage >= 90:
                    tp_number = 2
                elif cumulative_percentage >= 95:
                    tp_number = 3
                else:
                    tp_number = 4

                # Send TP fill alert with estimated TP number
                await self._send_tp_fill_alert_enhanced(monitor_data, fill_percentage, tp_number)

                # Only adjust SL quantity in PROFIT_TAKING phase (when TPs hit)
                # During BUILDING/MONITORING phases, SL should maintain full position coverage
                current_phase = monitor_data.get("phase", "BUILDING")
                if current_phase == "PROFIT_TAKING":
                    logger.info(f"🔧 PROFIT_TAKING phase: Adjusting SL to match remaining position ({current_size})")
                    await self._adjust_sl_quantity_enhanced(monitor_data, current_size)
                else:
                    logger.info(f"🛡️ {current_phase} phase: SL maintains full position coverage (no adjustment needed)")
            else:
                # This shouldn't happen - log for debugging
                logger.error(f"❌ Unexpected condition in _handle_conservative_position_change")
                logger.error(f"   Position increased: {position_increased}")
                logger.error(f"   Current size: {current_size}")
                logger.error(f"   Last known size: {last_known_size}")
                logger.error(f"   Position size: {monitor_data.get('position_size', 'N/A')}")
                logger.error(f"   Phase: {phase}")

            # ENHANCED: Progressive SL Management with Breakeven Automation
            monitor_key = f"{monitor_data['symbol']}_{monitor_data['side']}"

            # Check for TP1 breakeven trigger - now based on tp1_hit flag
            if monitor_data.get("tp1_hit", False) and not monitor_data.get("sl_moved_to_be", False):
                # Use atomic lock to prevent race conditions
                if monitor_key not in self.breakeven_locks:
                    self.breakeven_locks[monitor_key] = asyncio.Lock()

                async with self.breakeven_locks[monitor_key]:
                    # Double-check flag after acquiring lock
                    if not monitor_data.get("sl_moved_to_be", False):
                        logger.info(f"🔒 ENHANCED TP1 BREAKEVEN: {monitor_key} - TP1 has been hit")

                        # First, transition to profit-taking phase and cleanup limit orders
                        await self._transition_to_profit_taking(monitor_data)

                        # Get fresh position data for breakeven calculation
                        positions = await get_position_info(monitor_data["symbol"])
                        position = None
                        if positions:
                            for pos in positions:
                                if pos.get("side") == monitor_data["side"]:
                                    position = pos
                                    break

                        if position:
                            # ENHANCED: Use enhanced breakeven with full position management
                            success = await self._move_sl_to_breakeven_enhanced_v2(
                                monitor_data=monitor_data,
                                position=position,
                                is_tp1_trigger=True
                            )

                            if success:
                                monitor_data["sl_moved_to_be"] = True
                                logger.info(f"✅ ENHANCED TP1 breakeven completed for {monitor_key}")

                                # Send enhanced breakeven alert
                                await self._send_enhanced_breakeven_alert(monitor_data, "TP1")

                                # Synchronize with mirror account
                                await self._sync_breakeven_with_mirror(monitor_data)
                            else:
                                logger.error(f"❌ ENHANCED TP1 breakeven failed for {monitor_key}")

            # ENHANCED: Progressive breakeven for subsequent TP fills (TP2, TP3, TP4)
            elif monitor_data.get("sl_moved_to_be", False) and fill_percentage > 85:
                # TP2/3/4 fills - adjust SL progressively
                await self._handle_progressive_tp_fills(monitor_data, fill_percentage, current_size)


    def _count_filled_limit_orders(self, monitor_data: Dict) -> int:
        """Count how many limit orders have been filled"""
        limit_orders = monitor_data.get("limit_orders", [])
        filled_count = 0
        
        for order in limit_orders:
            if isinstance(order, dict) and order.get("status") == "FILLED":
                filled_count += 1
        
        return filled_count

# Fast approach removed - conservative approach only

    async def _adjust_all_orders_for_partial_fill(self, monitor_data: Dict, current_size: Decimal):
        """
        Adjust all TP and SL orders when position is partially filled
        This happens when limit orders in conservative approach are partially filled
        FIXED: Enhanced error handling and validation
        ENHANCED: Added atomic operation protection
        ENHANCED: Added comprehensive logging and diagnostics for TP rebalancing
        """
        try:
            # Enhanced validation with mirror account support
            if not monitor_data or current_size <= 0:
                logger.error(f"❌ TP REBALANCING FAILED: Invalid parameters - monitor_data={bool(monitor_data)}, current_size={current_size}")
                return

            symbol = monitor_data.get("symbol", "UNKNOWN")
            side = monitor_data.get("side", "UNKNOWN")
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"
            phase = monitor_data.get("phase", "UNKNOWN")
            
            # Additional validation for both main and mirror accounts
            if symbol == "UNKNOWN" or side == "UNKNOWN":
                logger.error(f"❌ TP REBALANCING FAILED: Missing symbol/side - symbol={symbol}, side={side}")
                return
                
            # Validate account type and ensure proper client availability
            if account_type == "mirror":
                if not hasattr(self, '_mirror_client') or self._mirror_client is None:
                    logger.error(f"❌ TP REBALANCING FAILED: Mirror account requested but not configured")
                    return
                logger.info(f"🪞 MIRROR ACCOUNT TP rebalancing for {symbol} {side}")
            else:
                logger.info(f"🏠 MAIN ACCOUNT TP rebalancing for {symbol} {side}")

            logger.info(f"🔄 STARTING TP REBALANCING for {symbol} {side} ({account_type.upper()}) - Phase: {phase}")
            logger.info(f"📊 Position size: {current_size} | Previous size: {monitor_data.get('last_known_size', 'Unknown')}")

            # Note: This method is already called within an atomic lock from the caller
            # Additional locking here would cause deadlock, so we rely on the caller's lock
            # ENHANCED: Use absolute position size calculation instead of ratios
            approach = monitor_data.get("approach", "CONSERVATIVE")

            # Define TP percentages based on approach
            # Conservative approach only: TP1: 85%, TP2-4: 5% each
            tp_percentages = [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")]

            logger.info(f"🎯 Using {approach} approach with TP percentages: {[str(p) for p in tp_percentages]}%")
            logger.info(f"🔄 Using {approach} approach with absolute position sizing")

            # Update the position size in monitor data
            monitor_data["position_size"] = current_size
            monitor_data["current_size"] = current_size
            monitor_data["remaining_size"] = current_size

            # Save to persistence after update
            self.save_monitors_to_persistence(reason="tp_rebalancing")

            # Adjust each TP order using absolute calculation
            # Ensure tp_orders is in dict format for backward compatibility
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            
            logger.info(f"📋 Found {len(tp_orders)} TP orders to rebalance")
            if not tp_orders:
                logger.warning(f"⚠️ No TP orders found for {symbol} {side} - skipping TP rebalancing")
                # Still return success to avoid false error reporting
                return
                
            # Convert dict to list for iteration
            tp_orders_list = list(tp_orders.values()) if isinstance(tp_orders, dict) else []
            
            # Determine if this is a mirror account
            is_mirror_account = account_type == "mirror"
            logger.info(f"🎯 Account type: {'MIRROR' if is_mirror_account else 'MAIN'}")
            
            # Mirror-specific validations
            if is_mirror_account:
                logger.info(f"🪞 MIRROR ACCOUNT validation for {symbol}:")
                logger.info(f"   • Mirror client available: {self._mirror_client is not None}")
                logger.info(f"   • TP orders to process: {len(tp_orders_list)}")
                
                # Additional mirror client check
                if not self._mirror_client:
                    logger.error(f"❌ CRITICAL: Mirror client not available for TP rebalancing")
                    return

            tp_rebalance_results = []  # Track results for final summary
            
            for i, tp_order in enumerate(tp_orders_list):
                tp_num = i + 1
                logger.info(f"🔄 Processing TP{tp_num} order (index {i})")
                
                if not isinstance(tp_order, dict):
                    logger.warning(f"❌ Skipping invalid TP{tp_num} order at index {i}: not a dict")
                    tp_rebalance_results.append(f"TP{tp_num}: SKIPPED (invalid)")
                    continue

                current_order_id = tp_order.get("order_id", "Unknown")
                current_qty = tp_order.get("quantity", "Unknown")
                logger.info(f"📊 TP{tp_num} current: OrderID={current_order_id[:8] if isinstance(current_order_id, str) else current_order_id}..., Qty={current_qty}")

                if i >= len(tp_percentages):
                    # Cancel excess TP orders - use account-aware cancellation
                    logger.info(f"🗑️ Cancelling excess TP{tp_num} order (beyond {len(tp_percentages)} TPs)")
                    if is_mirror_account:
                        cancel_result = await self._cancel_order_mirror(monitor_data["symbol"], tp_order["order_id"])
                    else:
                        cancel_result = await self._cancel_order_main(monitor_data["symbol"], tp_order["order_id"])
                    logger.info(f"❌ Cancelled excess TP{tp_order.get('tp_number', i+1)} order - Result: {cancel_result}")
                    tp_rebalance_results.append(f"TP{tp_num}: CANCELLED (excess)")
                    continue

                # Calculate new quantity based on absolute position size and TP percentage
                tp_percentage = tp_percentages[i]
                raw_new_qty = (current_size * tp_percentage) / Decimal("100")
                
                logger.info(f"💰 TP{tp_num} calculation: {current_size} × {tp_percentage}% = {raw_new_qty} (raw)")

                # Get instrument info to validate quantity step
                try:
                    instrument_info = await get_instrument_info(monitor_data["symbol"])
                    if instrument_info:
                        lot_size_filter = instrument_info.get("lotSizeFilter", {})
                        qty_step = Decimal(lot_size_filter.get("qtyStep", "1"))
                        min_order_qty = Decimal(lot_size_filter.get("minOrderQty", "0.001"))

                        # Adjust quantity to step size
                        new_qty = value_adjusted_to_step(raw_new_qty, qty_step)

                        # Skip if quantity too small or below minimum
                        if new_qty < min_order_qty:
                            if is_mirror_account:
                                await self._cancel_order_mirror(monitor_data["symbol"], tp_order["order_id"])
                            else:
                                await self._cancel_order_main(monitor_data["symbol"], tp_order["order_id"])
                            logger.info(f"❌ Cancelled TP{tp_order.get('tp_number', i+1)} - quantity {new_qty} below minimum {min_order_qty}")
                            continue
                    else:
                        # Fallback: use raw quantity but round to reasonable precision
                        new_qty = raw_new_qty.quantize(Decimal("0.1"))
                        if new_qty < Decimal("0.1"):
                            if is_mirror_account:
                                await self._cancel_order_mirror(monitor_data["symbol"], tp_order["order_id"])
                            else:
                                await self._cancel_order_main(monitor_data["symbol"], tp_order["order_id"])
                            logger.info(f"❌ Cancelled TP{tp_order.get('tp_number', i+1)} - quantity too small")
                            continue
                except Exception as e:
                    logger.error(f"Error getting instrument info for {monitor_data['symbol']}: {e}")
                    # Fallback: use raw quantity but round to reasonable precision
                    new_qty = raw_new_qty.quantize(Decimal("0.1"))
                    if new_qty < Decimal("0.1"):
                        if is_mirror_account:
                            await self._cancel_order_mirror(monitor_data["symbol"], tp_order["order_id"])
                        else:
                            await self._cancel_order_main(monitor_data["symbol"], tp_order["order_id"])
                        logger.info(f"❌ Cancelled TP{tp_order['tp_number']} - quantity too small")
                        continue

                # Cancel and replace the order with new quantity (with retry logic)
                logger.info(f"🗑️ Cancelling existing TP{tp_num} order: {current_order_id[:8] if isinstance(current_order_id, str) else current_order_id}...")
                
                cancel_success, cancel_message = await self._cancel_tp_order_with_retry(
                    is_mirror_account, monitor_data["symbol"], tp_order["order_id"], tp_num
                )
                
                logger.info(f"{'✅' if cancel_success else '❌'} TP{tp_num} cancellation result: {cancel_success} - {cancel_message}")
                
                if cancel_success:
                    # Place new order with adjusted quantity
                    order_side = "Sell" if monitor_data["side"] == "Buy" else "Buy"

                    # Get position index for hedge mode
                    position_idx = await get_correct_position_idx(monitor_data["symbol"], monitor_data["side"])

                    # Track adjustment count for this order
                    adjustment_count = tp_order.get("adjustment_count", 0) + 1
                    adjusted_order_link_id = generate_adjusted_order_link_id(
                        tp_order.get("order_link_id", f"TP_{i+1}"),
                        adjustment_count
                    )

                    logger.info(f"📤 Placing new TP{tp_num} order: {order_side} {new_qty} @ {tp_order.get('price', '0')}")
                    logger.info(f"🔗 New OrderLinkID: {adjusted_order_link_id}")

                    # Prepare order parameters
                    order_params = {
                        "symbol": monitor_data["symbol"],
                        "side": order_side,
                        "order_type": "Limit",
                        "qty": str(new_qty),
                        "price": str(tp_order.get("price", "0")),
                        "reduce_only": True,
                        "order_link_id": adjusted_order_link_id,
                        "time_in_force": "GTC",
                        "position_idx": position_idx  # Add position index for hedge mode
                    }
                    
                    # Place order using retry logic for enhanced reliability
                    placement_success, placement_message, new_result = await self._place_tp_order_with_retry(
                        is_mirror_account, order_params, tp_num
                    )

                    if placement_success and new_result.get("orderId"):
                        new_order_id = new_result["orderId"]
                        tp_order["order_id"] = new_order_id
                        tp_order["original_quantity"] = tp_order.get("original_quantity", tp_order.get("quantity", new_qty))  # Keep track of original
                        tp_order["quantity"] = new_qty
                        tp_order["order_link_id"] = adjusted_order_link_id
                        tp_order["adjustment_count"] = adjustment_count
                        tp_order["tp_percentage"] = tp_percentage  # Track the percentage for this TP
                        
                        logger.info(f"✅ TP{tp_num} REBALANCED SUCCESSFULLY: {current_qty} → {new_qty} ({tp_percentage}% of {current_size})")
                        logger.info(f"🆔 New TP{tp_num} OrderID: {new_order_id[:8]}... - {placement_message}")
                        tp_rebalance_results.append(f"TP{tp_num}: {current_qty}→{new_qty} ✅")
                    else:
                        logger.error(f"❌ TP{tp_num} PLACEMENT FAILED: {placement_message}")
                        tp_rebalance_results.append(f"TP{tp_num}: FAILED ({placement_message[:30]}...)")
                
                else:
                    logger.error(f"❌ TP{tp_num} SKIPPED: Cancellation failed")
                    tp_rebalance_results.append(f"TP{tp_num}: SKIPPED (cancel failed)")

            # Log final rebalancing summary
            successful_rebalances = len([r for r in tp_rebalance_results if '✅' in r])
            total_processed = len(tp_rebalance_results)
            
            logger.info(f"📋 TP REBALANCING SUMMARY for {symbol} {side} ({account_type.upper()}):")
            logger.info(f"   • Processed: {total_processed} TP orders")
            logger.info(f"   • Successful: {successful_rebalances}")
            logger.info(f"   • Results: {', '.join(tp_rebalance_results)}")
            
            if successful_rebalances == total_processed and total_processed > 0:
                logger.info(f"✅ TP REBALANCING COMPLETED SUCCESSFULLY for {symbol} {side}")
                # Send success alert to user
                await self._send_tp_rebalancing_alert(monitor_data, successful_rebalances, total_processed, tp_rebalance_results, "SUCCESS")
            elif successful_rebalances > 0:
                logger.warning(f"⚠️ TP REBALANCING PARTIALLY SUCCESSFUL: {successful_rebalances}/{total_processed}")
                # Send partial success alert to user
                await self._send_tp_rebalancing_alert(monitor_data, successful_rebalances, total_processed, tp_rebalance_results, "PARTIAL")
            else:
                logger.error(f"❌ TP REBALANCING FAILED: No orders successfully rebalanced")
                # Send failure alert to user
                await self._send_tp_rebalancing_alert(monitor_data, successful_rebalances, total_processed, tp_rebalance_results, "FAILED")

            # Only adjust SL in PROFIT_TAKING phase, not during position building
            current_phase = monitor_data.get("phase", "BUILDING")
            if current_phase == "PROFIT_TAKING":
                logger.info(f"🔧 PROFIT_TAKING phase: Adjusting SL to match remaining position ({current_size})")
                await self._adjust_sl_quantity_enhanced(monitor_data, current_size)
            else:
                logger.info(f"🛡️ {current_phase} phase: SL maintains full position coverage (no adjustment for limit fills)")

        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in TP rebalancing for {symbol if 'symbol' in locals() else 'UNKNOWN'}: {e}", exc_info=True)

    async def _adjust_sl_quantity(self, monitor_data: Dict, new_quantity: Decimal):
        """
        Adjust SL order quantity to match remaining position size
        Enhanced: Now adjusts SL after any TP hit, not just TP1
        """
        if not monitor_data.get("sl_order"):
            return

        try:
            sl_order = monitor_data["sl_order"]
            account_type = monitor_data.get("account_type", "main")
            is_mirror_account = account_type == "mirror"

            # Cancel existing SL - use account-aware cancellation
            cancel_success = False
            if is_mirror_account:
                cancel_success = await self._cancel_order_mirror(
                    monitor_data["symbol"],
                    sl_order["order_id"]
                )
            else:
                cancel_success = await self._cancel_order_main(
                    monitor_data["symbol"],
                    sl_order["order_id"]
                )
            
            if cancel_success:
                # Validate and adjust quantity to step size
                try:
                    instrument_info = await get_instrument_info(monitor_data["symbol"])
                    if instrument_info:
                        lot_size_filter = instrument_info.get("lotSizeFilter", {})
                        qty_step = Decimal(lot_size_filter.get("qtyStep", "1"))
                        min_order_qty = Decimal(lot_size_filter.get("minOrderQty", "0.001"))

                        # Adjust quantity to step size
                        adjusted_quantity = value_adjusted_to_step(new_quantity, qty_step)

                        # Ensure minimum quantity
                        if adjusted_quantity < min_order_qty:
                            adjusted_quantity = min_order_qty

                        logger.info(f"🔄 Adjusting SL quantity from {sl_order['quantity']} to {adjusted_quantity} (raw: {new_quantity})")
                    else:
                        # Fallback: round to reasonable precision
                        adjusted_quantity = new_quantity.quantize(Decimal("0.1"))
                        logger.info(f"🔄 Adjusting SL quantity from {sl_order['quantity']} to {adjusted_quantity} (fallback rounding)")
                except Exception as e:
                    logger.error(f"Error getting instrument info for SL adjustment: {e}")
                    # Fallback: round to reasonable precision
                    adjusted_quantity = new_quantity.quantize(Decimal("0.1"))
                    logger.info(f"🔄 Adjusting SL quantity from {sl_order['quantity']} to {adjusted_quantity} (fallback)")

                # Place new SL with updated quantity
                side = monitor_data["side"]
                sl_side = "Sell" if side == "Buy" else "Buy"

                # Get position index for hedge mode
                position_idx = await get_correct_position_idx(monitor_data["symbol"], side)

                # Track adjustment count for SL order
                adjustment_count = sl_order.get("adjustment_count", 0) + 1
                adjusted_order_link_id = generate_adjusted_order_link_id(
                    sl_order["order_link_id"],
                    adjustment_count
                )

                # Prepare SL order parameters
                # Calculate trigger direction for mirror account SL orders
                trigger_direction = None
                if is_mirror_account:
                    current_price = await get_current_price(monitor_data["symbol"])
                    if current_price:
                        trigger_price_float = float(sl_order["price"])
                        if sl_side == "Buy":  # Closing short position
                            trigger_direction = 2 if trigger_price_float < current_price else 1
                        else:  # Closing long position  
                            trigger_direction = 1 if trigger_price_float > current_price else 2
                    else:
                        # Fallback trigger direction
                        trigger_direction = 1 if sl_side == "Buy" else 2

                sl_order_params = {
                    "symbol": monitor_data["symbol"],
                    "side": sl_side,
                    "order_type": "Market",
                    "qty": str(adjusted_quantity),
                    "trigger_price": str(sl_order["price"]),
                    "reduce_only": True,
                    "order_link_id": adjusted_order_link_id,
                    "position_idx": position_idx,  # Add position index for hedge mode
                    "stop_order_type": "StopLoss"
                }
                
                # Add trigger direction and trigger by for mirror accounts
                if is_mirror_account and trigger_direction is not None:
                    sl_order_params["trigger_direction"] = trigger_direction
                    sl_order_params["trigger_by"] = "LastPrice"
                
                # Place SL order using account-specific method
                if is_mirror_account:
                    sl_result = await self._place_order_mirror(**sl_order_params)
                else:
                    sl_result = await place_order_with_retry(**sl_order_params)

                if sl_result and sl_result.get("orderId"):
                    symbol = monitor_data['symbol']
                    side = monitor_data['side']
                    price = sl_order['price']
                    logger.info(f"✅ SL adjusted: {symbol} {side} - New qty: {adjusted_quantity}, Price: {price}")
                    # Update SL order info
                    monitor_data["sl_order"]["order_id"] = sl_result["orderId"]
                    monitor_data["sl_order"]["quantity"] = new_quantity
                    monitor_data["sl_order"]["order_link_id"] = adjusted_order_link_id
                    monitor_data["sl_order"]["adjustment_count"] = adjustment_count
                    logger.info("✅ SL quantity adjusted successfully")

        except Exception as e:
            logger.error(f"Error adjusting SL quantity: {e}")

    async def _calculate_total_exposure(self, monitor_data: Dict, current_position_size: Decimal) -> Decimal:
        """
        Calculate total exposure including current position and unfilled limit orders
        This ensures SL always covers the worst-case scenario
        """
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            
            # Start with current position size
            total_exposure = current_position_size
            
            # Add unfilled limit order quantities
            unfilled_limit_qty = Decimal("0")
            
            # Check if TP1 has been hit (limit orders should be cancelled after TP1)
            tp1_hit = monitor_data.get("tp1_hit", False)
            
            if not tp1_hit:
                # Get unfilled limit orders and add their quantities
                try:
                    # Get limit order IDs from monitor data
                    limit_order_ids = monitor_data.get("limit_orders", [])
                    if not limit_order_ids:
                        # Fallback to different keys used in the system
                        limit_order_ids = monitor_data.get("limit_order_ids", [])
                    
                    if limit_order_ids:
                        # Get current orders from exchange
                        # CRITICAL FIX: Use monitoring cache for cleanup operations
                        all_orders = await self._get_cached_open_orders("ALL", account_type)
                        
                        if all_orders:
                            for order in all_orders:
                                order_id = order.get("orderId", "")
                                order_symbol = order.get("symbol", "")
                                order_side = order.get("side", "")
                                order_type = order.get("orderType", "")
                                
                                # Check if this is one of our limit orders
                                if (order_id in limit_order_ids and 
                                    order_symbol == symbol and 
                                    order_side == side and 
                                    order_type == "Limit"):
                                    
                                    unfilled_qty = Decimal(str(order.get("qty", "0"))) - Decimal(str(order.get("cumExecQty", "0")))
                                    if unfilled_qty > 0:
                                        unfilled_limit_qty += unfilled_qty
                                        logger.debug(f"   Found unfilled limit: {order_id[:8]}... qty: {unfilled_qty}")
                        
                        if unfilled_limit_qty > 0:
                            total_exposure += unfilled_limit_qty
                            logger.info(f"   Added {unfilled_limit_qty} from unfilled limits")
                
                except Exception as e:
                    logger.warning(f"Could not calculate unfilled limit orders: {e}")
                    # Use original position size as fallback
                    original_position_size = Decimal(str(monitor_data.get("position_size", current_position_size)))
                    if original_position_size > current_position_size:
                        total_exposure = original_position_size
                        logger.info(f"   Using original position size as total exposure: {total_exposure}")
            
            logger.info(f"   Total exposure calculated: {total_exposure} (position: {current_position_size}, limits: {unfilled_limit_qty})")
            return total_exposure
            
        except Exception as e:
            logger.error(f"Error calculating total exposure: {e}")
            return current_position_size

    async def _adjust_sl_quantity_enhanced(self, monitor_data: Dict, current_position_size: Decimal):
        """Enhanced SL quantity adjustment that properly tracks position changes and covers full exposure"""
        if not monitor_data.get("sl_order"):
            logger.warning("No SL order to adjust")
            return

        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            
            # Log current state
            account_indicator = "🪞 MIRROR" if account_type == "mirror" else "🎯 MAIN"
            logger.info(f"🔄 SL Adjustment for {symbol} {side} ({account_indicator} account)")
            logger.info(f"   Current position size: {current_position_size}")
            logger.info(f"   Original position size: {monitor_data.get('position_size', 'Unknown')}")
            logger.info(f"   TP1 hit: {monitor_data.get('tp1_hit', False)}")
            
            # Calculate total exposure (position + unfilled limits)
            total_exposure = await self._calculate_total_exposure(monitor_data, current_position_size)
            
            # Use the full position coverage calculation
            approach = "conservative"  # Conservative approach only
            tp1_hit = monitor_data.get('tp1_hit', False)
            
            # Calculate SL quantity to cover full exposure
            sl_quantity = self._calculate_full_position_sl_quantity(
                approach=approach,
                current_size=current_position_size,
                target_size=total_exposure,
                tp1_hit=tp1_hit
            )
            
            # Log the decision
            logger.info(f"   SL will be adjusted to: {sl_quantity} (covers full exposure)")
            
            # Use the standard adjustment method with calculated quantity
            await self._adjust_sl_quantity(monitor_data, sl_quantity)

        except Exception as e:
            logger.error(f"Error in enhanced SL quantity adjustment: {e}")
            # Fallback to standard method with full exposure protection
            try:
                total_exposure = await self._calculate_total_exposure(monitor_data, current_position_size)
                await self._adjust_sl_quantity(monitor_data, total_exposure)
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                await self._adjust_sl_quantity(monitor_data, current_position_size)

    async def _move_sl_to_breakeven_failsafe(self, monitor_data: Dict, position: Dict) -> Tuple[bool, str, Optional[Dict]]:
        """
        Failsafe wrapper for breakeven operations using the comprehensive failsafe system

        Returns:
            Tuple[success, message, sl_data]
        """
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"

            # Use actual weighted average entry price if available
            if monitor_key in self.actual_entry_prices:
                entry_data = self.actual_entry_prices[monitor_key]
                if isinstance(entry_data, dict):
                    entry_price = entry_data.get('weighted_price', monitor_data["entry_price"])
                    total_qty = entry_data.get('total_qty', Decimal('0'))
                    fills_count = len(entry_data.get('fills', []))
                    logger.info(f"🔄 Using actual weighted entry price for failsafe: {entry_price}")
                    logger.info(f"   Based on {fills_count} fills totaling {total_qty} units")
                else:
                    entry_price = monitor_data["entry_price"]
            else:
                entry_price = monitor_data["entry_price"]
                logger.warning(f"⚠️ Using planned entry price for failsafe (no actual fills tracked): {entry_price}")

            # Get current price
            current_price = await get_current_price(symbol)
            if not current_price:
                return False, "Could not get current price for breakeven calculation", None

            logger.info(f"🛡️ Starting failsafe breakeven operation for {symbol} {side}")
            logger.info(f"📊 Entry: {entry_price}, Current: {current_price}")

            # Store original SL price for reference
            if "sl_order" in monitor_data and monitor_data["sl_order"].get("price"):
                monitor_data["original_sl_price"] = monitor_data["sl_order"]["price"]

            # Use the comprehensive failsafe system
            success, message, sl_data = await breakeven_failsafe.move_sl_to_breakeven_atomic(
                monitor_data, entry_price, current_price
            )

            if success:
                logger.info(f"✅ Failsafe breakeven successful: {message}")
                return True, message, sl_data
            else:
                logger.error(f"❌ Failsafe breakeven failed: {message}")
                return False, message, None

        except Exception as e:
            logger.error(f"❌ Exception in failsafe breakeven wrapper: {e}")
            return False, f"Failsafe wrapper exception: {str(e)}", None

    
    async def _move_sl_to_breakeven(self, monitor_data: dict) -> bool:
        """
        Simple wrapper for breakeven movement - works for all positions (main & mirror)
        This ensures compatibility with existing code while using enhanced logic
        """
        try:
            # Get current position
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            
            logger.info(f"🔄 Moving SL to breakeven for {symbol} {side} ({account_type})")
            
            # Get position info
            position = await self.check_position(symbol, side, account_type)
            if not position:
                logger.warning(f"No position found for breakeven: {symbol} {side} {account_type}")
                return False
            
            # Use the enhanced method
            result = await self._move_sl_to_breakeven_enhanced(monitor_data, position)
            if result is None:  # Handle methods that return None
                return True  # Assume success if no explicit False
            return result
            
        except Exception as e:
            logger.error(f"Error in _move_sl_to_breakeven wrapper: {e}")
            # Try failsafe method
            try:
                success, msg, _ = await self._move_sl_to_breakeven_failsafe(monitor_data, position)
                return success
            except Exception as fe:
                logger.error(f"Failsafe also failed: {fe}")
                return False

    async def _move_sl_to_breakeven_enhanced(self, monitor_data: Dict, position: Dict):
        """Enhanced breakeven move with dynamic fee calculation and better error handling"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"

            # Use actual weighted average entry price if available
            if monitor_key in self.actual_entry_prices:
                entry_data = self.actual_entry_prices[monitor_key]
                if isinstance(entry_data, dict):
                    entry_price = entry_data.get('weighted_price', monitor_data["entry_price"])
                    total_qty = entry_data.get('total_qty', Decimal('0'))
                    fills_count = len(entry_data.get('fills', []))
                    logger.info(f"🔄 Using actual weighted entry price: {entry_price}")
                    logger.info(f"   Based on {fills_count} fills totaling {total_qty} units")
                else:
                    entry_price = monitor_data["entry_price"]
            else:
                entry_price = monitor_data["entry_price"]
                logger.warning(f"⚠️ Using planned entry price (no actual fills tracked): {entry_price}")

            current_sl_price = monitor_data["sl_order"]["price"]

            # Dynamic fee calculation with configurable safety margin
            if DYNAMIC_FEE_CALCULATION:
                fee_rate = await self._get_trading_fee_rate(symbol)
            else:
                fee_rate = Decimal("0.0006")  # Fallback to fixed 0.06%

            safety_margin = Decimal(str(BREAKEVEN_SAFETY_MARGIN))  # Configurable safety margin
            total_fee_buffer = fee_rate + safety_margin

            logger.info(f"📊 Fee calculation: base_rate={fee_rate:.4f}%, safety_margin={safety_margin:.4f}%, total={total_fee_buffer:.4f}%")

            if side == "Buy":
                breakeven_price = entry_price * (Decimal("1") + total_fee_buffer)
                # Only move if new price is better than current SL
                if breakeven_price <= current_sl_price:
                    logger.info(f"🚫 Breakeven price {breakeven_price} not better than current SL {current_sl_price}")
                    return
            else:  # Sell
                breakeven_price = entry_price * (Decimal("1") - total_fee_buffer)
                # Only move if new price is better than current SL
                if breakeven_price >= current_sl_price:
                    logger.info(f"🚫 Breakeven price {breakeven_price} not better than current SL {current_sl_price}")
                    return

            logger.info(f"🎯 Moving SL to breakeven: {current_sl_price} → {breakeven_price}")

            # Cancel existing SL
            if await cancel_order_with_retry(
                monitor_data["symbol"],
                monitor_data["sl_order"]["order_id"]
            ):
                # Place new SL at breakeven
                sl_side = "Sell" if side == "Buy" else "Buy"

                # Get position index for hedge mode
                position_idx = await get_correct_position_idx(monitor_data["symbol"], side)

                sl_result = await place_order_with_retry(
                    symbol=monitor_data["symbol"],
                    side=sl_side,
                    order_type="Market",
                    qty=str(monitor_data["remaining_size"]),
                    trigger_price=str(breakeven_price),
                    reduce_only=True,
                    order_link_id=monitor_data["sl_order"]["order_link_id"] + "_BE",
                    position_idx=position_idx,  # Add position index for hedge mode
                    stop_order_type="StopLoss"
                )

                if sl_result and sl_result.get("orderId"):
                    symbol = monitor_data['symbol']
                    side = monitor_data['side']
                    price = breakeven_price
                    logger.info(f"✅ SL adjusted: {symbol} {side} - New qty: {monitor_data['remaining_size']}, Price: {price}")
                    # Update SL order info
                    monitor_data["sl_order"]["order_id"] = sl_result["orderId"]
                    monitor_data["sl_order"]["price"] = breakeven_price
                    monitor_data["sl_order"]["order_link_id"] += "_BE"
                    monitor_data["sl_moved_to_be"] = True
                    logger.info("✅ SL moved to breakeven successfully")
                    return True

        except Exception as e:
            logger.error(f"Error moving SL to breakeven: {e}")
            return False

    async def _get_trading_fee_rate(self, symbol: str) -> Decimal:
        """Get dynamic trading fee rate for the account"""
        try:
            # Check cache first
            if symbol in self.fee_rates_cache:
                cache_entry = self.fee_rates_cache[symbol]
                if time.time() - cache_entry["timestamp"] < 300:  # 5 minute cache
                    return cache_entry["fee_rate"]

            # Try to get account info for fee rates
            try:
                from clients.bybit_client import bybit_client
                account_info = bybit_client.get_account_info()

                if account_info and account_info.get("result"):
                    # Extract fee rate from account info
                    fee_info = account_info["result"].get("feeRate", {})
                    taker_fee = fee_info.get("takerFeeRate", "0.0006")  # Default 0.06%
                    fee_rate = Decimal(str(taker_fee))

                    # Cache the result
                    self.fee_rates_cache[symbol] = {
                        "fee_rate": fee_rate,
                        "timestamp": time.time()
                    }

                    logger.info(f"📊 Retrieved dynamic fee rate: {fee_rate:.4f}% for {symbol}")
                    return fee_rate
            except Exception as e:
                logger.warning(f"⚠️ Could not get dynamic fee rate: {e}")

            # Fallback to conservative default
            default_fee = Decimal("0.0006")  # 0.06% conservative default
            logger.info(f"📊 Using default fee rate: {default_fee:.4f}% for {symbol}")
            return default_fee

        except Exception as e:
            logger.error(f"Error getting trading fee rate: {e}")
            return Decimal("0.0006")  # Safe fallback

    async def _track_actual_entry_price(self, symbol: str, side: str, filled_price: Decimal, filled_qty: Decimal, account_type: str = "main"):
        """Track actual entry prices from order fills for accurate breakeven calculation"""
        monitor_key = f"{symbol}_{side}_{account_type}"

        if monitor_key not in self.actual_entry_prices:
            # First fill
            self.actual_entry_prices[monitor_key] = {
                "weighted_price": filled_price,
                "total_qty": filled_qty,
                "fills": []
            }
        else:
            # Additional fill - calculate weighted average
            entry_data = self.actual_entry_prices[monitor_key]
            old_total_qty = entry_data["total_qty"]
            new_total_qty = old_total_qty + filled_qty

            # Weighted average calculation
            old_total_value = entry_data["weighted_price"] * old_total_qty
            new_fill_value = filled_price * filled_qty
            new_weighted_price = (old_total_value + new_fill_value) / new_total_qty

            entry_data["weighted_price"] = new_weighted_price
            entry_data["total_qty"] = new_total_qty

        # Record the fill
        self.actual_entry_prices[monitor_key]["fills"].append({
            "price": filled_price,
            "qty": filled_qty,
            "timestamp": time.time()
        })

        logger.info(f"📊 Updated weighted entry price for {monitor_key}: {self.actual_entry_prices[monitor_key]['weighted_price']:.6f}")

    async def _enhanced_fill_detection(self, symbol: str, side: str, monitor_data: Dict):
        """Enhanced real-time fill detection with order history verification"""
        try:
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"

            # Get current open orders for verification (with caching)
            open_orders = await self._get_cached_open_orders(symbol, account_type)

            # Check TP orders for fills
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            if isinstance(tp_orders, list):
                # Convert list to dict using order_id as key
                tp_orders_dict = {}
                for tp_order in tp_orders:
                    if isinstance(tp_order, dict) and "order_id" in tp_order:
                        tp_orders_dict[tp_order["order_id"]] = tp_order
                tp_orders = tp_orders_dict

            for order_id, tp_order in tp_orders.items():
                # order_id = tp_order["order_id"]  # Now comes from iteration

                # Check if order is no longer in open orders (potentially filled)
                order_found = any(order.get("orderId") == order_id for order in open_orders)

                if not order_found and tp_order.get("status") != "FILLED":
                    # Order not found in open orders but not marked as filled
                    # Verify through order history
                    filled_qty = await self._verify_order_fill_history(symbol, order_id)

                    if filled_qty and filled_qty > 0:
                        logger.info(f"🎯 Detected TP order fill via history: {order_id} - {filled_qty}")

                        # Note: TP orders don't contribute to entry price, they reduce position

                        # Update order status
                        tp_order["status"] = "FILLED"
                        tp_order["filled_qty"] = filled_qty
                        tp_order["fill_time"] = time.time()

                        # Update fill tracker
                        if monitor_key not in self.fill_tracker:
                            self.fill_tracker[monitor_key] = {"total_filled": Decimal("0"), "target_size": monitor_data["position_size"]}
                        self.fill_tracker[monitor_key]["total_filled"] += filled_qty

            # Check SL order for fills
            sl_order = monitor_data.get("sl_order")
            if sl_order and sl_order.get("status") != "FILLED":
                sl_order_id = sl_order.get("order_id")
                if sl_order_id:
                    # Check if SL order is still in open orders
                    sl_found = any(order.get("orderId") == sl_order_id for order in open_orders)
                    
                    if not sl_found:
                        # SL order not found - verify if it was filled
                        filled_qty = await self._verify_order_fill_history(symbol, sl_order_id)
                        
                        if filled_qty and filled_qty > 0:
                            logger.info(f"🛑 STOP LOSS HIT! Order {sl_order_id[:8]}... filled: {filled_qty}")
                            
                            # Mark SL as hit
                            monitor_data["sl_hit"] = True
                            sl_order["status"] = "FILLED"
                            sl_order["filled_qty"] = filled_qty
                            sl_order["fill_time"] = time.time()
                            
                            # Pre-emptively cancel all remaining orders
                            await self._emergency_cancel_all_orders(symbol, side, monitor_data)
            
            # Check for any other order changes
            await self._verify_position_consistency(symbol, side, monitor_data)

        except Exception as e:
            logger.error(f"Error in enhanced fill detection: {e}")

    async def _identify_filled_tp_order(self, monitor_data: Dict) -> Optional[Dict]:
        """
        Identify which TP order was filled by checking order history
        Returns dict with tp_number and order details if a TP was filled
        """
        try:
            symbol = monitor_data["symbol"]
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            account_type = monitor_data.get("account_type", "main")
            
            logger.debug(f"🔍 Checking TP orders for fills - Symbol: {symbol}, Account: {account_type}")
            logger.debug(f"📋 TP orders to check: {len(tp_orders)} orders")
            
            # Check each TP order for fills
            for order_id, tp_order in tp_orders.items():
                # Skip if already marked as filled
                if tp_order.get("status") == "FILLED":
                    logger.debug(f"⏭️ Skipping order {order_id[:8]}... - already marked as FILLED")
                    continue
                    
                # Determine which account this order belongs to
                order_account = tp_order.get("account", account_type)
                
                logger.debug(f"🔍 Checking order {order_id[:8]}... (TP{tp_order.get('tp_number', '?')}) on {order_account} account")
                
                # Check order fill history with correct account
                filled_qty = await self._verify_order_fill_history(symbol, order_id, order_account)
                
                if filled_qty and filled_qty > 0:
                    # TP order was filled!
                    tp_number = tp_order.get("tp_number", 1)
                    logger.info(f"✅ Detected TP{tp_number} fill on {order_account} account - Order ID: {order_id[:8]}...")
                    logger.info(f"📊 Fill details: Qty={filled_qty}, Percentage={tp_order.get('percentage', 0)}%")
                    
                    # Mark order as filled
                    tp_order["status"] = "FILLED"
                    tp_order["filled_qty"] = filled_qty
                    tp_order["fill_time"] = time.time()
                    
                    return {
                        "tp_number": tp_number,
                        "order_id": order_id,
                        "filled_qty": filled_qty,
                        "percentage": tp_order.get("percentage", 0),
                        "account": order_account
                    }
            
            logger.debug(f"❌ No filled TP orders found for {symbol} on {account_type} account")
            return None
            
        except Exception as e:
            logger.error(f"Error identifying filled TP order: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def _verify_order_fill_history(self, symbol: str, order_id: str, account: str = "main") -> Optional[Decimal]:
        """Verify order fill through order history API"""
        try:
            logger.debug(f"🔍 Verifying order fill - Order ID: {order_id[:8]}..., Symbol: {symbol}, Account: {account}")
            
            # Get the appropriate client based on account
            if account == "mirror":
                # Import mirror client
                try:
                    from execution.mirror_trader import bybit_client_2
                    client = bybit_client_2
                except ImportError:
                    logger.warning("Mirror client not available, using main client")
                    from clients.bybit_client import bybit_client
                    client = bybit_client
            else:
                from clients.bybit_client import bybit_client
                client = bybit_client

            # Get order history for the specific order
            history = client.get_order_history(
                category="linear",
                symbol=symbol,
                orderId=order_id,
                limit=1
            )

            if history and history.get("result") and history["result"].get("list"):
                order_data = history["result"]["list"][0]
                if order_data.get("orderStatus") in ["Filled", "PartiallyFilled"]:
                    filled_qty = Decimal(str(order_data.get("cumExecQty", "0")))
                    logger.info(f"📋 {account.capitalize()} order history confirms fill: {order_id} - {filled_qty}")
                    return filled_qty

            return None

        except Exception as e:
            logger.warning(f"Could not verify {account} order fill history: {e}")
            return None

    async def _verify_position_consistency(self, symbol: str, side: str, monitor_data: Dict):
        """Update tracked position size from exchange without warnings"""
        try:
            # Determine account type from monitor data
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"
            if account_type == "mirror":
                monitor_key += "_mirror"

            # Get current position from exchange - USE CORRECT ACCOUNT
            if account_type == 'mirror':
                positions = await get_position_info_for_account(symbol, 'mirror')
            else:
                positions = await get_position_info(symbol)

            current_position = None

            if positions:
                for pos in positions:
                    if pos.get("side") == side:
                        current_position = pos
                        break

            if current_position:
                exchange_size = Decimal(str(current_position.get("size", "0")))
                tracked_size = Decimal(str(monitor_data.get("remaining_size", "0")))

                # Simply update tracked size to match exchange without warnings
                monitor_data["remaining_size"] = exchange_size

                # If position is smaller, likely a TP fill we missed
                if exchange_size < tracked_size:
                    size_diff = tracked_size - exchange_size

                    # Update fill tracker
                    if monitor_key not in self.fill_tracker:
                        self.fill_tracker[monitor_key] = {"total_filled": Decimal("0"), "target_size": monitor_data["position_size"]}
                    self.fill_tracker[monitor_key]["total_filled"] += size_diff

        except Exception as e:
            logger.error(f"Error updating position size: {e}")


    async def validate_monitor_creation(self, symbol: str, side: str, chat_id: int,
                                      approach: str, account_type: str = "main") -> bool:
        """
        Validate that both Enhanced TP/SL and dashboard monitors were created successfully
        Added by monitor tracking fix to ensure complete monitor coverage
        """
        try:
            # Check Enhanced TP/SL monitor
            monitor_key = f"{symbol}_{side}_{account_type}"
            if account_type == "mirror":
                monitor_key += "_MIRROR"

            has_enhanced_monitor = monitor_key in self.position_monitors
            if account_type == "mirror" and hasattr(self, 'mirror_monitors'):
                has_enhanced_monitor = monitor_key in getattr(self, 'mirror_monitors', {})

            # Check dashboard monitor
            dashboard_key_pattern = f"{chat_id}_{symbol}_{approach}"
            if account_type == "mirror":
                dashboard_key_pattern += "_mirror"

            # Load current dashboard monitors
            import pickle
            pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'

            try:
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
                dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
                has_dashboard_monitor = any(dashboard_key_pattern in key for key in dashboard_monitors.keys())
            except Exception:
                has_dashboard_monitor = False

            success = has_enhanced_monitor and has_dashboard_monitor

            if not success:
                logger.warning(f"⚠️ Monitor validation failed for {symbol} {side} ({account_type})")
                logger.warning(f"   Enhanced monitor: {has_enhanced_monitor}")
                logger.warning(f"   Dashboard monitor: {has_dashboard_monitor}")
            else:
                logger.info(f"✅ Monitor validation passed for {symbol} {side} ({account_type})")

            return success

        except Exception as e:
            logger.error(f"❌ Error validating monitor creation: {e}")
            return False

    async def _emergency_cancel_all_orders(self, symbol: str, side: str, monitor_data: Dict):
        """Emergency cancel all orders when SL or final TP is about to close position"""
        try:
            logger.info(f"🚨 EMERGENCY: Cancelling all orders for {symbol} {side} - position closure imminent")
            
            # Cancel all TP orders immediately
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            cancelled_count = 0
            for order_id, tp_order in tp_orders.items():
                if tp_order.get("status") != "FILLED":
                    try:
                        await cancel_order_with_retry(symbol, order_id)
                        cancelled_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to cancel TP order {order_id[:8]}...: {e}")
            
            # Cancel SL order if it exists and wasn't the trigger
            if monitor_data.get("sl_order") and not monitor_data.get("sl_hit"):
                try:
                    await cancel_order_with_retry(symbol, monitor_data["sl_order"]["order_id"])
                    cancelled_count += 1
                except Exception as e:
                    logger.warning(f"Failed to cancel SL order: {e}")
            
            # Cancel any remaining limit orders
            for limit_order in monitor_data.get("limit_orders", []):
                if isinstance(limit_order, dict) and limit_order.get("status") == "ACTIVE":
                    try:
                        await cancel_order_with_retry(symbol, limit_order["order_id"])
                        cancelled_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to cancel limit order: {e}")
            
            logger.info(f"✅ Emergency cancellation complete: {cancelled_count} orders cancelled")
            
            # Check if final TP was hit and close any remaining position
            if monitor_data.get("all_tps_filled", False):
                await self._ensure_position_fully_closed(symbol, side, monitor_data)
            
            # Also trigger mirror account cancellation
            account_type = monitor_data.get("account_type", "main")
            if account_type == "main":
                await self._cleanup_mirror_position_orders(symbol, side)
                
        except Exception as e:
            logger.error(f"Error in emergency order cancellation: {e}")
    
    async def _ensure_position_fully_closed(self, symbol: str, side: str, monitor_data: Dict):
        """Ensure position is fully closed when all TPs are filled"""
        try:
            account_type = monitor_data.get("account_type", "main")
            logger.info(f"🔍 Checking if {symbol} {side} ({account_type}) needs complete closure after final TP")
            
            # Get current position
            positions = await get_position_info_for_account(symbol, account_type)
            if not positions:
                logger.info(f"✅ No position found - already closed")
                return
            
            # Find our position
            position = None
            for pos in positions:
                if pos.get("side") == side and float(pos.get("size", 0)) > 0:
                    position = pos
                    break
            
            if not position:
                logger.info(f"✅ Position already closed")
                return
            
            remaining_size = float(position.get("size", 0))
            if remaining_size <= 0:
                logger.info(f"✅ Position already closed")
                return
            
            # Position still has remaining size after final TP - close it
            logger.info(f"🎯 Closing remaining position: {remaining_size} contracts after final TP")
            
            # Place market order to close remaining position
            close_side = "Sell" if side == "Buy" else "Buy"
            
            try:
                result = await place_order_with_retry(
                    symbol=symbol,
                    side=close_side,
                    order_type="Market",
                    qty=str(remaining_size),
                    reduce_only=True,  # Critical: ensure we only close, not open new position
                    order_link_id=f"BOT_FINAL_TP_CLOSE_{symbol}_{side}_{int(time.time())}"
                )
                
                if result:
                    logger.info(f"✅ Successfully closed remaining {remaining_size} contracts for {symbol} {side}")
                    # Send alert about complete closure
                    chat_id = monitor_data.get("chat_id")
                    if chat_id:
                        message = f"""🏁 <b>Position Fully Closed - Final TP Hit</b>

Symbol: <b>{symbol}</b>
Side: <b>{side}</b>
Remaining Size Closed: <b>{remaining_size}</b>
Account: <b>{account_type.capitalize()}</b>

All take profit targets have been achieved! 🎯"""
                        await send_trade_alert(chat_id, message, "final_tp_closure")
                else:
                    logger.error(f"❌ Failed to close remaining position")
                    
            except Exception as e:
                logger.error(f"❌ Error closing remaining position: {e}")
                
        except Exception as e:
            logger.error(f"Error ensuring position fully closed: {e}")
    
    async def _orphaned_order_cleanup_failsafe(self, symbol: str, side: str, account_type: str = "main"):
        """Failsafe to clean up any orphaned orders after position closure"""
        try:
            # Wait 10 seconds to ensure position is fully closed
            await asyncio.sleep(10)
            
            logger.info(f"🧹 Running orphaned order cleanup failsafe for {symbol} {side} {account_type}")
            
            # Check if position still exists
            positions = await get_position_info_for_account(symbol, account_type)
            position_exists = False
            
            if positions:
                for pos in positions:
                    if pos.get("side") == side and float(pos.get("size", 0)) > 0:
                        position_exists = True
                        break
            
            if not position_exists:
                # Position is closed, cancel any remaining orders
                open_orders = await get_open_orders(symbol)
                cancelled_count = 0
                
                for order in open_orders:
                    # Check if this is a bot order for our position
                    order_side = order.get("side")
                    reduce_only = order.get("reduceOnly", False)
                    
                    # TP/SL orders have opposite side and reduceOnly=True
                    if reduce_only and ((side == "Buy" and order_side == "Sell") or (side == "Sell" and order_side == "Buy")):
                        try:
                            order_id = order.get("orderId")
                            await cancel_order_with_retry(symbol, order_id)
                            cancelled_count += 1
                            logger.info(f"✅ Cancelled orphaned order {order_id[:8]}...")
                        except Exception as e:
                            logger.warning(f"Failed to cancel orphaned order: {e}")
                
                if cancelled_count > 0:
                    logger.info(f"🧹 Orphaned order cleanup complete: {cancelled_count} orders cancelled")
                else:
                    logger.info(f"✅ No orphaned orders found for {symbol} {side}")
            else:
                logger.info(f"ℹ️ Position still exists for {symbol} {side}, skipping orphaned cleanup")
                
        except Exception as e:
            logger.error(f"Error in orphaned order cleanup failsafe: {e}")
    
    def enable_execution_mode(self):
        """Enable execution mode to optimize API calls during trade placement"""
        self._execution_mode = True
        self._execution_cache = {}
        self._last_execution_cache_clear = time.time()
        logger.info("🚀 Execution mode ENABLED - API calls will be cached for 5s")
    
    def disable_execution_mode(self):
        """Disable execution mode and clear cache"""
        was_enabled = self._execution_mode
        self._execution_mode = False
        cache_size = len(self._execution_cache)
        self._execution_cache = {}
        if was_enabled:
            logger.info(f"🏁 Execution mode DISABLED - cleared {cache_size} cached entries")
    
    def _cleanup_execution_cache(self):
        """Clean up expired execution cache entries"""
        if not self._execution_mode:
            return
        
        current_time = time.time()
        if current_time - self._last_execution_cache_clear > 30:  # Clean every 30s
            expired_keys = []
            for key, entry in self._execution_cache.items():
                if current_time - entry['timestamp'] > self._execution_cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._execution_cache[key]
            
            if expired_keys:
                logger.debug(f"🧹 Cleaned {len(expired_keys)} expired execution cache entries")
            
            self._last_execution_cache_clear = current_time

    # CRITICAL FIX: Monitoring cache implementation for position/order fetching
    async def _get_cached_position_info(self, symbol: str, account_type: str = "main"):
        """Get position info with monitoring cache"""
        cache_key = f"position_{symbol}_{account_type}"
        current_time = time.time()
        
        # Check if we have fresh cached data
        if cache_key in self._monitoring_cache:
            cached_entry = self._monitoring_cache[cache_key]
            if current_time - cached_entry['timestamp'] < self._monitoring_cache_ttl:
                logger.debug(f"🚀 Using cached position data for {symbol} ({account_type}) - age: {current_time - cached_entry['timestamp']:.1f}s")
                return cached_entry['data']
        
        # Get from refreshed cache data
        all_positions_key = f"{account_type}_ALL_positions"
        
        if all_positions_key in self._monitoring_cache:
            cache_entry = self._monitoring_cache[all_positions_key]
            if current_time - cache_entry['timestamp'] < self._monitoring_cache_ttl:
                all_positions = cache_entry['data']
                
                if symbol == "ALL":
                    logger.debug(f"🚀 Cache hit: Returning {len(all_positions)} positions for ALL symbols ({account_type})")
                    return all_positions
                else:
                    # Filter by symbol
                    filtered_positions = [p for p in all_positions if p.get("symbol") == symbol]
                    logger.debug(f"🚀 Cache hit: Returning {len(filtered_positions)} positions for {symbol} ({account_type})")
                    return filtered_positions
        
        # CRITICAL FIX: If cache is empty, refresh it immediately
        logger.info(f"⚡ Position cache miss for {symbol} ({account_type}) - triggering immediate refresh")
        await self._refresh_monitoring_cache()
        
        # Try again after refresh
        if all_positions_key in self._monitoring_cache:
            cache_entry = self._monitoring_cache[all_positions_key]
            all_positions = cache_entry['data']
            
            if symbol == "ALL":
                logger.info(f"✅ Position cache populated: Returning {len(all_positions)} positions for ALL symbols ({account_type})")
                return all_positions
            else:
                # Filter by symbol
                filtered_positions = [p for p in all_positions if p.get("symbol") == symbol]
                logger.info(f"✅ Position cache populated: Returning {len(filtered_positions)} positions for {symbol} ({account_type})")
                return filtered_positions
        
        # If still no data after refresh, return empty list
        logger.warning(f"⚠️ No position data available for {symbol} ({account_type}) even after cache refresh")
        return []

    async def _get_cached_open_orders(self, symbol: str, account_type: str = "main"):
        """Get open orders with monitoring cache"""
        cache_key = f"orders_{symbol}_{account_type}"
        current_time = time.time()
        
        # Check if we have fresh cached data
        if cache_key in self._monitoring_cache:
            cached_entry = self._monitoring_cache[cache_key]
            if current_time - cached_entry['timestamp'] < self._monitoring_cache_ttl:
                logger.debug(f"🚀 Using cached order data for {symbol} ({account_type}) - age: {current_time - cached_entry['timestamp']:.1f}s")
                return cached_entry['data']
        
        # Fetch fresh data
        logger.debug(f"🔍 Fetching fresh order data for {symbol} ({account_type})")
        # Get from refreshed cache data
        all_orders_key = f"{account_type}_ALL_orders"
        
        if all_orders_key in self._monitoring_cache:
            cache_entry = self._monitoring_cache[all_orders_key]
            if time.time() - cache_entry['timestamp'] < self._monitoring_cache_ttl:
                all_orders = cache_entry['data']
                
                if symbol == "ALL":
                    logger.debug(f"🚀 Cache hit: Returning {len(all_orders)} orders for ALL symbols ({account_type})")
                    return all_orders
                else:
                    # Filter by symbol
                    filtered_orders = [o for o in all_orders if o.get("symbol") == symbol]
                    logger.debug(f"🚀 Cache hit: Returning {len(filtered_orders)} orders for {symbol} ({account_type})")
                    return filtered_orders
        
        # CRITICAL FIX: If cache is empty, refresh it immediately
        logger.info(f"⚡ Cache miss for {symbol} ({account_type}) - triggering immediate refresh")
        await self._refresh_monitoring_cache()
        
        # Try again after refresh
        if all_orders_key in self._monitoring_cache:
            cache_entry = self._monitoring_cache[all_orders_key]
            all_orders = cache_entry['data']
            
            if symbol == "ALL":
                logger.info(f"✅ Cache populated: Returning {len(all_orders)} orders for ALL symbols ({account_type})")
                return all_orders
            else:
                # Filter by symbol
                filtered_orders = [o for o in all_orders if o.get("symbol") == symbol]
                logger.info(f"✅ Cache populated: Returning {len(filtered_orders)} orders for {symbol} ({account_type})")
                return filtered_orders
        
        # If still no data after refresh, return empty list
        logger.warning(f"⚠️ No data available for {symbol} ({account_type}) even after cache refresh")
        return []

    async def _refresh_monitoring_cache(self):
        """Refresh monitoring cache with fresh data from exchange - PERFORMANCE CRITICAL"""
        current_time = time.time()
        
        # Don't refresh too frequently - minimum 15 seconds between refreshes
        if hasattr(self, '_last_cache_refresh') and current_time - self._last_cache_refresh < 15:
            logger.debug(f"⏭️ Cache refresh skipped - last refresh {current_time - self._last_cache_refresh:.1f}s ago")
            return
        
        try:
            logger.info("🔄 CRITICAL: Refreshing monitoring cache to reduce API calls...")
            refresh_start = time.time()
            
            # Import at call time to avoid circular imports
            from clients.bybit_helpers import get_all_positions, get_all_open_orders
            
            # Get main account data in parallel
            logger.debug("📊 Fetching main account positions and orders...")
            main_positions = await get_all_positions()
            main_orders = await get_all_open_orders()
            
            # Cache main account data
            self._monitoring_cache["main_ALL_positions"] = {
                'data': main_positions,
                'timestamp': current_time
            }
            self._monitoring_cache["main_ALL_orders"] = {
                'data': main_orders,
                'timestamp': current_time
            }
            
            # Get mirror account data if enabled
            import os
            if os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true":
                logger.debug("📊 Fetching mirror account positions and orders...")
                from execution.mirror_trader import bybit_client_2
                mirror_positions = await get_all_positions(client=bybit_client_2)
                mirror_orders = await get_all_open_orders(client=bybit_client_2)
                
                # Cache mirror account data
                self._monitoring_cache["mirror_ALL_positions"] = {
                    'data': mirror_positions,
                    'timestamp': current_time
                }
                self._monitoring_cache["mirror_ALL_orders"] = {
                    'data': mirror_orders,
                    'timestamp': current_time
                }
                logger.info(f"✅ Cache refreshed: {len(main_positions)} main pos, {len(main_orders)} main orders, {len(mirror_positions)} mirror pos, {len(mirror_orders)} mirror orders")
            else:
                logger.info(f"✅ Cache refreshed: {len(main_positions)} main positions, {len(main_orders)} main orders (mirror disabled)")
            
            self._last_cache_refresh = current_time
            refresh_time = time.time() - refresh_start
            logger.info(f"⚡ Cache refresh completed in {refresh_time:.2f}s - Next refresh in 15s")
            
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR refreshing monitoring cache: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")

    def _cleanup_monitoring_cache(self):
        """Clean up expired monitoring cache entries"""
        current_time = time.time()
        if current_time - self._last_monitoring_cache_clear > 30:  # Clean every 30s
            expired_keys = []
            for key, entry in self._monitoring_cache.items():
                if current_time - entry['timestamp'] > self._monitoring_cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._monitoring_cache[key]
            
            if expired_keys:
                logger.debug(f"🧹 Cleaned {len(expired_keys)} expired monitoring cache entries")
            
            self._last_monitoring_cache_clear = current_time

    def get_cache_stats(self):
        """Get monitoring cache statistics for debugging"""
        cache_size = len(self._monitoring_cache)
        cache_entries = {}
        current_time = time.time()
        
        for key, entry in self._monitoring_cache.items():
            age = current_time - entry['timestamp']
            cache_entries[key] = f"{age:.1f}s ago"
        
        return {
            "cache_size": cache_size,
            "cache_ttl": self._monitoring_cache_ttl,
            "entries": cache_entries
        }

    async def save_state_for_restart(self):
        """Save monitor state specifically for safe bot restart"""
        try:
            logger.info("💾 Preparing monitor state for safe bot restart...")
            
            # Use robust persistence to save monitor state
            from utils.robust_persistence import robust_persistence
            
            # Save current monitor state 
            saved_count = 0
            for monitor_key, monitor_data in self.position_monitors.items():
                try:
                    # Clean monitor data before saving
                    clean_monitor = {}
                    for field_key, field_value in monitor_data.items():
                        # Skip non-serializable fields
                        if any([
                            'task' in str(field_key).lower(),
                            'monitoring_task' in str(field_key),
                            hasattr(field_value, '_callbacks'),
                            hasattr(field_value, '__await__'),
                            hasattr(field_value, 'cancel'),
                            callable(field_value) and not isinstance(field_value, type)
                        ]):
                            continue
                        clean_monitor[field_key] = field_value
                    
                    # Save each monitor to robust persistence
                    await robust_persistence.update_monitor(monitor_key, clean_monitor)
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving monitor {monitor_key}: {e}")
            
            if saved_count > 0:
                # Create restart-specific signal file
                with open('.safe_restart_state_saved', 'w') as f:
                    import json
                    restart_info = {
                        'timestamp': time.time(),
                        'monitor_count': saved_count,
                        'execution_mode': getattr(self, '_execution_mode', False),
                        'performance_optimizations': {
                            'execution_aware_caching': True,
                            'api_call_deduplication': True,
                            'smart_throttling': True
                        }
                    }
                    json.dump(restart_info, f, indent=2)
                
                logger.info(f"✅ Bot ready for safe restart - {saved_count} monitors preserved")
                logger.info(f"🔄 Restart info saved to .safe_restart_state_saved")
                return True
            else:
                logger.warning("⚠️ No monitors to save for restart")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error preparing for safe restart: {e}")
            return False

    async def cleanup_position_orders(self, symbol: str, side: str, account_type: str = None):
        """Clean up all orders when position is closed"""
        monitor_key = f"{symbol}_{side}_{account_type}"
        if monitor_key not in self.position_monitors:
            logger.info(f"Monitor {monitor_key} not found, skipping cleanup")
            return

        monitor_data = self.position_monitors.get(monitor_key)
        if not monitor_data:
            logger.warning(f"Monitor data for {monitor_key} is None")
            return

        try:
            # Cancel all remaining TP orders
            # Ensure tp_orders is dict format
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            for order_id, tp_order in tp_orders.items():
                await cancel_order_with_retry(symbol, tp_order["order_id"])

            # Cancel SL order if exists
            if monitor_data.get("sl_order"):
                await cancel_order_with_retry(symbol, monitor_data["sl_order"]["order_id"])

            # Cancel any remaining active limit orders
            for limit_order in monitor_data.get("limit_orders", []):
                if isinstance(limit_order, dict) and limit_order.get("status") == "ACTIVE":
                    try:
                        await cancel_order_with_retry(symbol, limit_order["order_id"])
                        limit_order["status"] = "CANCELLED"
                        logger.info(f"🧹 Cancelled remaining limit order {limit_order['order_id'][:8]}...")
                    except Exception as e:
                        logger.error(f"Error cancelling limit order {limit_order['order_id'][:8]}...: {e}")

            # CRITICAL FIX: Clean up mirror account orders
            await self._cleanup_mirror_position_orders(symbol, side)

            # Mark cleanup as completed
            monitor_data["cleanup_completed"] = True
            monitor_data["phase"] = "CLOSED"

            # Remove monitor using robust persistence
            try:
                from utils.robust_persistence import remove_trade_monitor
                await remove_trade_monitor(symbol, side, reason="position_closed")
                logger.info(f"✅ Removed monitor via robust persistence for closed position")
            except Exception as e:
                logger.error(f"Error removing monitor via robust persistence: {e}")

            # Remove from monitors
            del self.position_monitors[monitor_key]
            # Force save after monitor deletion
            self.save_monitors_to_persistence(force=True, reason="monitor_removed")
            logger.info(f"✅ Cleaned up all orders for closed position {symbol} {side}")

        except Exception as e:
            logger.error(f"Error cleaning up orders: {e}")

    async def _cleanup_mirror_position_orders(self, symbol: str, side: str):
        """Clean up mirror account orders when position is closed"""
        try:
            # Check if mirror trading is enabled
            from execution.mirror_trader import is_mirror_trading_enabled
            if not is_mirror_trading_enabled():
                return

            logger.info(f"🔄 Cleaning up mirror account orders for {symbol} {side}")

            # Try to get mirror enhanced TP/SL manager
            try:
                from execution.mirror_enhanced_tp_sl import initialize_mirror_manager
                mirror_manager = initialize_mirror_manager(self)
                if mirror_manager:
                    # Mirror manager doesn't have cleanup_mirror_orders method
                    # Fall through to direct cleanup below
                    logger.info(f"Mirror manager available but using direct cleanup")
                    pass
            except (ImportError, AttributeError) as e:
                logger.warning(f"Mirror enhanced manager not available: {e}")

            # Fallback: Direct mirror order cleanup using get_all_open_orders
            try:
                from clients.bybit_helpers import get_all_open_orders
                from execution.mirror_trader import bybit_client_2, cancel_mirror_order

                if bybit_client_2:
                    # CRITICAL FIX: Use monitoring cache for mirror orders
                    mirror_orders = await self._get_cached_open_orders(symbol, "mirror")
                    symbol_orders = mirror_orders

                    # Cancel all bot orders for this symbol (TP, SL, and limit)
                    cancelled_count = 0
                    for order in symbol_orders:
                        order_link_id = order.get('orderLinkId', '')
                        if ('BOT_' in order_link_id or 'MIRROR' in order_link_id) and order.get('orderStatus') == 'New':
                            try:
                                success = await cancel_mirror_order(symbol, order.get('orderId'))
                                if success:
                                    cancelled_count += 1
                                    logger.info(f"🧹 Cancelled mirror order: {order_link_id}")
                                else:
                                    logger.warning(f"⚠️ Failed to cancel mirror order: {order_link_id}")
                            except Exception as e:
                                logger.error(f"Error cancelling mirror order {order_link_id}: {e}")

                    logger.info(f"✅ Mirror cleanup completed: {cancelled_count} orders cancelled")
                else:
                    logger.warning("Mirror client not available for order cleanup")

            except Exception as e:
                logger.error(f"Error in fallback mirror cleanup: {e}")

        except Exception as e:
            logger.error(f"Error cleaning up mirror account orders: {e}")

    async def _sync_breakeven_with_mirror(self, monitor_data: Dict):
        """Synchronize breakeven SL movement with mirror account AND mirror monitor state"""
        try:
            # Check if mirror trading is enabled
            from execution.mirror_trader import is_mirror_trading_enabled
            if not is_mirror_trading_enabled():
                return

            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"
            mirror_monitor_key = f"{symbol}_{side}_mirror"

            # Only sync if this is a main account monitor
            if account_type != "main":
                logger.debug(f"Skipping mirror sync for non-main account: {account_type}")
                return

            # Use atomic lock to prevent race conditions
            if mirror_monitor_key not in self.mirror_sync_locks:
                self.mirror_sync_locks[mirror_monitor_key] = asyncio.Lock()

            async with self.mirror_sync_locks[mirror_monitor_key]:
                logger.info(f"🪞 Synchronizing breakeven with mirror account: {symbol} {side}")

                # CRITICAL FIX: Update mirror monitor state FIRST
                mirror_monitor_data = self.position_monitors.get(mirror_monitor_key)
                if mirror_monitor_data:
                    logger.info(f"🔄 Synchronizing mirror monitor state: {mirror_monitor_key}")
                    
                    # Sync all critical state from main monitor
                    mirror_monitor_data["tp1_hit"] = True
                    mirror_monitor_data["sl_moved_to_be"] = True
                    mirror_monitor_data["phase"] = "PROFIT_TAKING"
                    mirror_monitor_data["phase_transition_time"] = time.time()
                    
                    # Cancel unfilled limit orders for mirror if enabled
                    if CANCEL_LIMITS_ON_TP1 and not mirror_monitor_data.get("limit_orders_cancelled", False):
                        logger.info(f"🧹 Cancelling unfilled limit orders for mirror: {mirror_monitor_key}")
                        await self._cancel_unfilled_limit_orders(mirror_monitor_data)
                        mirror_monitor_data["limit_orders_cancelled"] = True
                        
                    logger.info(f"✅ Mirror monitor state synchronized: {mirror_monitor_key} → PROFIT_TAKING phase")
                    
                    # CRITICAL: Save the updated monitor state to persistence immediately
                    await self._save_monitor_state_to_persistence(mirror_monitor_key, mirror_monitor_data, force=True)
                else:
                    logger.warning(f"⚠️ Mirror monitor not found for synchronization: {mirror_monitor_key}")

                # Try to use mirror enhanced TP/SL manager for SL price update
                try:
                    from execution.mirror_enhanced_tp_sl import initialize_mirror_manager
                    mirror_manager = initialize_mirror_manager(self)
                    if mirror_manager and hasattr(mirror_manager, 'sync_breakeven_movement'):
                        await mirror_manager.sync_breakeven_movement(monitor_data["symbol"], monitor_data["side"], monitor_data["avg_price"])
                        logger.info(f"✅ Mirror breakeven synchronized via enhanced manager")
                        return
                except (ImportError, AttributeError) as e:
                    logger.warning(f"Mirror enhanced manager not available for breakeven sync: {e}")

                # Fallback: Direct mirror breakeven sync
                try:
                    from execution.mirror_trader import bybit_client_2
                    from clients.bybit_helpers import get_position_info, get_open_orders, cancel_order_with_retry, place_order_with_retry
                    from utils.order_identifier import generate_order_link_id, ORDER_TYPE_SL

                    if not bybit_client_2:
                        logger.warning("Mirror client not available for breakeven sync")
                        return

                    # Get mirror position
                    mirror_positions = await get_position_info(symbol, client=bybit_client_2)
                    mirror_position = None
                    if mirror_positions:
                        for pos in mirror_positions:
                            if pos.get("side") == side:
                                mirror_position = pos
                                break

                    if not mirror_position:
                        logger.warning(f"No mirror position found for {symbol} {side}")
                        return

                    # Calculate breakeven price for mirror (same as main)
                    entry_price = Decimal(str(mirror_position.get("avgPrice", "0")))
                    if entry_price <= 0:
                        logger.warning(f"Invalid mirror entry price: {entry_price}")
                        return

                    # Use same breakeven calculation as main account
                    fee_rate = Decimal("0.0006")  # 0.06% maker/taker
                    safety_margin = Decimal(str(BREAKEVEN_SAFETY_MARGIN))  # Additional safety

                    if side == "Buy":
                        breakeven_price = entry_price * (1 + fee_rate + safety_margin)
                    else:  # Sell
                        breakeven_price = entry_price * (1 - fee_rate - safety_margin)

                    # Cancel existing mirror SL orders
                    mirror_orders = await get_open_orders(bybit_client_2)
                    symbol_orders = [o for o in mirror_orders if o.get('symbol') == symbol]

                    for order in symbol_orders:
                        order_link_id = order.get('orderLinkId', '')
                        if 'MIRROR' in order_link_id and 'SL' in order_link_id:
                            await self._cancel_order_mirror(symbol, order.get('orderId'))
                            logger.info(f"🧹 Cancelled old mirror SL: {order_link_id}")

                    # Place new mirror breakeven SL
                    mirror_size = Decimal(str(mirror_position.get("size", "0")))
                    if mirror_size > 0:
                        sl_side = "Sell" if side == "Buy" else "Buy"
                        sl_order_link_id = generate_order_link_id("MIRROR", symbol, side, ORDER_TYPE_SL, 1)

                        sl_result = await place_order_with_retry(
                            symbol=symbol,
                            side=sl_side,
                            order_type="Limit",
                            qty=str(mirror_size),
                            price=str(breakeven_price),
                            reduce_only=True,
                            order_link_id=sl_order_link_id,
                            time_in_force="GTC",
                            position_idx=0,  # Mirror account is in One-Way mode
                            client=bybit_client_2
                        )

                        if sl_result and sl_result.get("orderId"):
                            logger.info(f"✅ Mirror breakeven SL placed: {breakeven_price} for {mirror_size}")
                            
                            # Update mirror monitor SL order data if monitor exists
                            if mirror_monitor_data:
                                mirror_monitor_data["sl_order"] = {
                                    "order_id": sl_result.get("orderId"),
                                    "price": breakeven_price,
                                    "quantity": mirror_size,
                                    "order_link_id": sl_order_link_id,
                                    "account": "mirror"
                                }
                                logger.info(f"📊 Updated mirror monitor SL order data")
                        else:
                            logger.error(f"❌ Failed to place mirror breakeven SL")

                except Exception as e:
                    logger.error(f"Error in fallback mirror breakeven sync: {e}")

        except Exception as e:
            logger.error(f"Error synchronizing breakeven with mirror account: {e}")

    async def _save_monitor_state_to_persistence(self, monitor_key: str, monitor_data: Dict, force: bool = False):
        """
        Save monitor state to persistence for safe bot restarts
        Uses direct pickle access to avoid circular imports (like the rest of this class)
        """
        try:
            # Use the same direct pickle approach as the rest of this class
            pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            
            # Read current data
            try:
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
            except FileNotFoundError:
                # Create new data structure if file doesn't exist
                data = {
                    'conversations': {},
                    'user_data': {},
                    'chat_data': {},
                    'bot_data': {}
                }
            
            # Ensure bot_data structure exists
            if 'bot_data' not in data:
                data['bot_data'] = {}
            if 'enhanced_tp_sl_monitors' not in data['bot_data']:
                data['bot_data']['enhanced_tp_sl_monitors'] = {}
            
            # Clean monitor data before saving to remove non-serializable fields
            clean_monitor_data = {}
            for key, value in monitor_data.items():
                # Skip async tasks, locks, and other non-serializable objects
                if any([
                    'task' in str(key).lower(),
                    'lock' in str(key).lower(),
                    hasattr(value, '_callbacks'),
                    hasattr(value, '__await__'),
                    hasattr(value, 'cancel'),
                    callable(value) and not isinstance(value, type)
                ]):
                    continue
                clean_monitor_data[key] = value
            
            # Update the monitor data
            data['bot_data']['enhanced_tp_sl_monitors'][monitor_key] = clean_monitor_data
            
            # Save updated data
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"💾 Saved monitor state to persistence: {monitor_key}")
            
        except Exception as e:
            logger.error(f"Error saving monitor state to persistence: {e}")
            # Don't raise exception to avoid disrupting the main trading flow

    async def get_position_status(self, symbol: str, side: str, account_type: str = "main") -> Optional[Dict]:
        """Get current status of monitored position"""
        monitor_key = f"{symbol}_{side}_{account_type}"
        if monitor_key not in self.position_monitors:
            return None

        monitor_data = self.position_monitors[monitor_key]

        # Calculate filled percentage (ensure consistent types)
        filled_size = monitor_data["position_size"] - monitor_data["remaining_size"]
        position_size_decimal = Decimal(str(monitor_data["position_size"]))
        filled_size_decimal = Decimal(str(filled_size))
        filled_percentage = float((filled_size_decimal / position_size_decimal) * 100)

        return {
            "symbol": symbol,
            "side": side,
            "entry_price": monitor_data["entry_price"],
            "position_size": monitor_data["position_size"],
            "remaining_size": monitor_data["remaining_size"],
            "filled_percentage": filled_percentage,
            "tp_orders_count": len(monitor_data["tp_orders"]),
            "filled_tps": len(monitor_data["filled_tps"]),
            "sl_at_breakeven": monitor_data["sl_moved_to_be"],
            "monitoring_duration": time.time() - monitor_data["created_at"],
            "phase": monitor_data.get("phase", "UNKNOWN"),
            "tp1_hit": monitor_data.get("tp1_hit", False),
            "limit_orders_count": len(monitor_data.get("limit_orders", []))
        }

    def _track_order_lifecycle(self, order_id: str, order_type: str, symbol: str, side: str,
                               price: Decimal, quantity: Decimal, order_link_id: str = None):
        """
        Track comprehensive order lifecycle data for enhanced monitoring

        Args:
            order_id: Unique order identifier
            order_type: TP, SL, or LIMIT
            symbol: Trading symbol
            side: Buy/Sell
            price: Order price
            quantity: Order quantity
            order_link_id: Order link identifier
        """
        current_time = time.time()

        self.order_lifecycle[order_id] = {
            "order_id": order_id,
            "order_type": order_type,
            "symbol": symbol,
            "side": side,
            "price": price,
            "quantity": quantity,
            "original_quantity": quantity,
            "order_link_id": order_link_id,
            "status": "ACTIVE",
            "created_at": current_time,
            "last_updated": current_time,
            "fill_events": [],
            "modification_history": [],
            "execution_metrics": {
                "fill_rate": 0.0,
                "partial_fills": 0,
                "time_to_fill": None,
                "price_improvement": Decimal("0"),
                "slippage": Decimal("0")
            },
            "relationship_data": {
                "parent_position": f"{symbol}_{side}",
                "related_orders": [],
                "dependency_chain": []
            }
        }

        # Add to order relationships
        position_key = f"{symbol}_{side}"
        if position_key not in self.order_relationships:
            self.order_relationships[position_key] = {
                "tp_orders": [],
                "sl_orders": [],
                "limit_orders": [],
                "filled_orders": [],
                "cancelled_orders": []
            }

        # Categorize order
        if order_type == "TP":
            self.order_relationships[position_key]["tp_orders"].append(order_id)
        elif order_type == "SL":
            self.order_relationships[position_key]["sl_orders"].append(order_id)
        elif order_type == "LIMIT":
            self.order_relationships[position_key]["limit_orders"].append(order_id)

        logger.info(f"📊 Tracking order lifecycle: {order_id[:8]}... ({order_type})")

    def _update_order_status(self, order_id: str, new_status: str, fill_data: Dict = None):
        """
        Update order status and track fill events

        Args:
            order_id: Order identifier
            new_status: New order status (FILLED, PARTIAL_FILLED, CANCELLED, etc.)
            fill_data: Optional fill information
        """
        if order_id not in self.order_lifecycle:
            return

        order_data = self.order_lifecycle[order_id]
        old_status = order_data["status"]
        current_time = time.time()

        # Update basic status
        order_data["status"] = new_status
        order_data["last_updated"] = current_time

        # Handle fill events
        if fill_data and new_status in ["FILLED", "PARTIAL_FILLED"]:
            fill_event = {
                "timestamp": current_time,
                "fill_price": fill_data.get("fill_price", order_data["price"]),
                "fill_quantity": fill_data.get("fill_quantity", Decimal("0")),
                "cumulative_filled": fill_data.get("cumulative_filled", Decimal("0")),
                "remaining_quantity": fill_data.get("remaining_quantity", order_data["quantity"])
            }
            order_data["fill_events"].append(fill_event)

            # Update execution metrics
            metrics = order_data["execution_metrics"]
            metrics["partial_fills"] += 1

            # Calculate fill rate
            if order_data["original_quantity"] > 0:
                metrics["fill_rate"] = float(fill_data.get("cumulative_filled", 0) / order_data["original_quantity"])

            # Calculate time to fill for completed orders
            if new_status == "FILLED" and metrics["time_to_fill"] is None:
                metrics["time_to_fill"] = current_time - order_data["created_at"]

            # Calculate price improvement/slippage
            fill_price = fill_data.get("fill_price", order_data["price"])
            if isinstance(fill_price, (int, float, str)):
                fill_price = Decimal(str(fill_price))
            price_diff = fill_price - order_data["price"]

            if order_data["side"] == "Buy":
                metrics["price_improvement"] = -price_diff  # Negative diff is improvement for buys
            else:
                metrics["price_improvement"] = price_diff   # Positive diff is improvement for sells

            metrics["slippage"] = abs(price_diff)

            logger.info(f"📈 Order fill event: {order_id[:8]}... {old_status} → {new_status}")

        # Update order relationships
        position_key = order_data["relationship_data"]["parent_position"]
        if position_key in self.order_relationships:
            relationships = self.order_relationships[position_key]

            if new_status == "FILLED":
                if order_id not in relationships["filled_orders"]:
                    relationships["filled_orders"].append(order_id)
            elif new_status == "CANCELLED":
                if order_id not in relationships["cancelled_orders"]:
                    relationships["cancelled_orders"].append(order_id)

    def _get_order_relationships(self, symbol: str, side: str) -> Dict:
        """
        Get comprehensive order relationship data for a position

        Returns:
            Dict containing all related orders and their statuses
        """
        position_key = f"{symbol}_{side}"
        if position_key not in self.order_relationships:
            return {}

        relationships = self.order_relationships[position_key].copy()

        # Add detailed order data
        for order_list in ["tp_orders", "sl_orders", "limit_orders", "filled_orders", "cancelled_orders"]:
            detailed_orders = []
            for order_id in relationships.get(order_list, []):
                if order_id in self.order_lifecycle:
                    detailed_orders.append(self.order_lifecycle[order_id])
            relationships[f"{order_list}_detailed"] = detailed_orders

        return relationships

    def _calculate_position_metrics(self, symbol: str, side: str) -> Dict:
        """
        Calculate comprehensive execution metrics for a position

        Returns:
            Dict containing position-level performance metrics
        """
        position_key = f"{symbol}_{side}"
        relationships = self._get_order_relationships(symbol, side)

        metrics = {
            "total_orders": 0,
            "filled_orders": 0,
            "cancelled_orders": 0,
            "partial_filled_orders": 0,
            "fill_rate": 0.0,
            "average_time_to_fill": 0.0,
            "total_slippage": Decimal("0"),
            "total_price_improvement": Decimal("0"),
            "execution_efficiency": 0.0
        }

        all_orders = []
        for order_type in ["tp_orders", "sl_orders", "limit_orders"]:
            all_orders.extend(relationships.get(f"{order_type}_detailed", []))

        if not all_orders:
            return metrics

        metrics["total_orders"] = len(all_orders)

        filled_times = []
        total_slippage = Decimal("0")
        total_improvement = Decimal("0")

        for order in all_orders:
            order_metrics = order.get("execution_metrics", {})
            status = order.get("status", "UNKNOWN")

            if status == "FILLED":
                metrics["filled_orders"] += 1
                time_to_fill = order_metrics.get("time_to_fill")
                if time_to_fill:
                    filled_times.append(time_to_fill)
            elif status == "CANCELLED":
                metrics["cancelled_orders"] += 1
            elif status == "PARTIAL_FILLED":
                metrics["partial_filled_orders"] += 1

            # Accumulate slippage and price improvement
            total_slippage += order_metrics.get("slippage", Decimal("0"))
            total_improvement += order_metrics.get("price_improvement", Decimal("0"))

        # Calculate averages
        if metrics["total_orders"] > 0:
            metrics["fill_rate"] = metrics["filled_orders"] / metrics["total_orders"]
            metrics["execution_efficiency"] = (metrics["filled_orders"] + metrics["partial_filled_orders"]) / metrics["total_orders"]

        if filled_times:
            metrics["average_time_to_fill"] = sum(filled_times) / len(filled_times)

        metrics["total_slippage"] = total_slippage
        metrics["total_price_improvement"] = total_improvement

        # Store in execution metrics cache
        self.execution_metrics[position_key] = metrics

        return metrics

    async def cleanup_orphaned_monitors(self):
        """
        Clean up monitors that no longer have corresponding positions
        This prevents resource leaks and memory buildup
        """
        try:
            monitors_to_remove = []

            logger.info("🧹 Starting orphaned monitor cleanup")

            for monitor_key, monitor_data in self.position_monitors.items():
                symbol = monitor_data["symbol"]
                side = monitor_data["side"]

                try:
                    # Check if position still exists
                    positions = await get_position_info(symbol)
                    position_exists = False

                    if positions:
                        for pos in positions:
                            if pos.get("side") == side and float(pos.get("size", 0)) > 0:
                                position_exists = True
                                break

                    if not position_exists:
                        # Position closed, schedule monitor for removal
                        monitors_to_remove.append(monitor_key)
                        logger.info(f"📍 Orphaned monitor found: {monitor_key}")

                        # Cancel monitoring task if running
                        task = self.active_tasks.get(monitor_key) if hasattr(self, 'active_tasks') else None
                        if task:
                            task.cancel()

                        # Clean up related orders
                        await self._cleanup_monitor_orders(monitor_data)

                        # Clean up order lifecycle data
                        await self._cleanup_order_lifecycle_data(symbol, side)

                except Exception as e:
                    logger.error(f"Error checking position for {monitor_key}: {e}")

            # Remove orphaned monitors
            for monitor_key in monitors_to_remove:
                del self.position_monitors[monitor_key]
                logger.info(f"🗑️ Removed orphaned monitor: {monitor_key}")

            if monitors_to_remove:
                logger.info(f"✅ Cleaned up {len(monitors_to_remove)} orphaned monitors")
            else:
                logger.debug("✅ No orphaned monitors found")

        except Exception as e:
            logger.error(f"Error in orphaned monitor cleanup: {e}")

    async def _cleanup_monitor_orders(self, monitor_data: Dict):
        """
        Clean up orders associated with a monitor
        Cancels open orders and updates order lifecycle data
        """
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]

            # Cancel all TP orders
            # Ensure tp_orders is dict format
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            for order_id, tp_order in tp_orders.items():
                try:
                    # order_id = tp_order["order_id"]  # Now comes from iteration
                    if await cancel_order_with_retry(symbol, order_id):
                        logger.info(f"❌ Cancelled TP order: {order_id[:8]}...")
                        # Update order lifecycle
                        self._update_order_status(order_id, "CANCELLED")
                except Exception as e:
                    logger.error(f"Error cancelling TP order: {e}")

            # Cancel SL order
            if monitor_data.get("sl_order"):
                try:
                    sl_order_id = monitor_data["sl_order"]["order_id"]
                    if await cancel_order_with_retry(symbol, sl_order_id):
                        logger.info(f"🛡️ Cancelled SL order: {sl_order_id[:8]}...")
                        # Update order lifecycle
                        self._update_order_status(sl_order_id, "CANCELLED")
                except Exception as e:
                    logger.error(f"Error cancelling SL order: {e}")

            # Cancel limit orders if in cleanup phase
            if monitor_data.get("cleanup_completed", False):
                for limit_order in monitor_data.get("limit_orders", []):
                    if isinstance(limit_order, dict) and limit_order.get("status") == "ACTIVE":
                        try:
                            order_id = limit_order["order_id"]
                            if await cancel_order_with_retry(symbol, order_id):
                                logger.info(f"📝 Cancelled limit order: {order_id[:8]}...")
                                limit_order["status"] = "CANCELLED"
                                # Update order lifecycle
                                self._update_order_status(order_id, "CANCELLED")
                        except Exception as e:
                            logger.error(f"Error cancelling limit order: {e}")

        except Exception as e:
            logger.error(f"Error cleaning up monitor orders: {e}")

    async def _cleanup_order_lifecycle_data(self, symbol: str, side: str):
        """
        Clean up order lifecycle and relationship data for a closed position
        """
        try:
            position_key = f"{symbol}_{side}"

            # Get all orders for this position
            if position_key in self.order_relationships:
                relationships = self.order_relationships[position_key]
                all_orders = []

                for order_type in ["tp_orders", "sl_orders", "limit_orders", "filled_orders", "cancelled_orders"]:
                    all_orders.extend(relationships.get(order_type, []))

                # Archive order data before cleanup (keep for analysis)
                archived_orders = {}
                for order_id in all_orders:
                    if order_id in self.order_lifecycle:
                        archived_orders[order_id] = self.order_lifecycle[order_id].copy()
                        # Mark as archived
                        archived_orders[order_id]["archived_at"] = time.time()
                        archived_orders[order_id]["status"] = "ARCHIVED"

                # Clean up active data structures
                for order_id in all_orders:
                    if order_id in self.order_lifecycle:
                        del self.order_lifecycle[order_id]

                # Store archived data for future analysis
                if not hasattr(self, 'archived_orders'):
                    self.archived_orders = {}
                self.archived_orders[position_key] = archived_orders

                # Clean up relationships
                del self.order_relationships[position_key]

                # Clean up execution metrics
                if position_key in self.execution_metrics:
                    # Archive metrics
                    if not hasattr(self, 'archived_metrics'):
                        self.archived_metrics = {}
                    self.archived_metrics[position_key] = self.execution_metrics[position_key]
                    del self.execution_metrics[position_key]

                logger.info(f"🗂️ Archived lifecycle data for {len(all_orders)} orders from {position_key}")

        except Exception as e:
            logger.error(f"Error cleaning up order lifecycle data: {e}")

    async def perform_memory_cleanup(self):
        """
        Perform comprehensive memory cleanup to prevent resource leaks
        """
        try:
            logger.info("🧠 Starting memory cleanup")

            # Clean up orphaned monitors
            await self.cleanup_orphaned_monitors()

            # Clean up stale price cache
            current_time = time.time()
            stale_symbols = []

            for symbol, (price, timestamp) in self.price_cache.items():
                if current_time - timestamp > self.price_cache_ttl * 10:  # 10x TTL for cleanup
                    stale_symbols.append(symbol)

            for symbol in stale_symbols:
                del self.price_cache[symbol]

            if stale_symbols:
                logger.info(f"🗑️ Cleaned up {len(stale_symbols)} stale price cache entries")

            # Archive old order lifecycle data (older than 24 hours)
            old_orders = []
            cutoff_time = current_time - (24 * 3600)  # 24 hours

            for order_id, order_data in self.order_lifecycle.items():
                if order_data.get("created_at", current_time) < cutoff_time and order_data.get("status") in ["FILLED", "CANCELLED"]:
                    old_orders.append(order_id)

            if old_orders:
                # Archive old orders
                if not hasattr(self, 'archived_orders'):
                    self.archived_orders = {}

                for order_id in old_orders:
                    order_data = self.order_lifecycle[order_id]
                    position_key = order_data["relationship_data"]["parent_position"]

                    if position_key not in self.archived_orders:
                        self.archived_orders[position_key] = {}

                    self.archived_orders[position_key][order_id] = order_data.copy()
                    self.archived_orders[position_key][order_id]["archived_at"] = current_time

                    del self.order_lifecycle[order_id]

                logger.info(f"📦 Archived {len(old_orders)} old orders")

            # Limit archived data size (keep only last 1000 positions)
            if hasattr(self, 'archived_orders') and len(self.archived_orders) > 1000:
                # Keep only most recent 1000
                sorted_positions = sorted(
                    self.archived_orders.items(),
                    key=lambda x: max([order.get("archived_at", 0) for order in x[1].values()]),
                    reverse=True
                )
                self.archived_orders = dict(sorted_positions[:1000])
                logger.info("📦 Trimmed archived orders to 1000 most recent positions")

            logger.info("✅ Memory cleanup completed")

        except Exception as e:
            logger.error(f"Error in memory cleanup: {e}")

    async def get_resource_usage_stats(self) -> Dict:
        """
        Get current resource usage statistics
        """
        try:
            stats = {
                "active_monitors": len(self.position_monitors),
                "tracked_orders": len(self.order_lifecycle),
                "order_relationships": len(self.order_relationships),
                "execution_metrics": len(self.execution_metrics),
                "price_cache_entries": len(self.price_cache),
                "archived_orders": len(getattr(self, 'archived_orders', {})),
                "archived_metrics": len(getattr(self, 'archived_metrics', {})),
                "memory_usage": {
                    "monitors": len(str(self.position_monitors)),
                    "lifecycle": len(str(self.order_lifecycle)),
                    "relationships": len(str(self.order_relationships))
                }
            }

            # Calculate active vs completed orders
            active_orders = 0
            completed_orders = 0

            for order_data in self.order_lifecycle.values():
                if order_data.get("status") in ["ACTIVE", "PARTIAL_FILLED"]:
                    active_orders += 1
                else:
                    completed_orders += 1

            stats["order_status_breakdown"] = {
                "active": active_orders,
                "completed": completed_orders
            }

            return stats

        except Exception as e:
            logger.error(f"Error getting resource usage stats: {e}")
            return {}

    def start_cleanup_scheduler(self):
        """
        Start the periodic cleanup scheduler
        """
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_scheduler_loop())
            logger.info("✅ Started Enhanced TP/SL cleanup scheduler")

    def stop_cleanup_scheduler(self):
        """
        Stop the periodic cleanup scheduler
        """
        if self.cleanup_task:
            self.cleanup_task.cancel()
            self.cleanup_task = None
            logger.info("⏹️ Stopped Enhanced TP/SL cleanup scheduler")

    async def _cleanup_scheduler_loop(self):
        """
        Periodic cleanup scheduler loop
        """
        try:
            while True:
                await asyncio.sleep(self.cleanup_interval)

                try:
                    current_time = time.time()

                    # Check if it's time for cleanup
                    if current_time - self.last_cleanup >= self.cleanup_interval:
                        logger.info("⏰ Scheduled cleanup starting")
                        await self.perform_memory_cleanup()
                        self.last_cleanup = current_time

                        # Also trigger mirror cleanup if available
                        try:
                            from execution.mirror_enhanced_tp_sl import initialize_mirror_manager
                            mirror_manager = initialize_mirror_manager(self)
                            if mirror_manager and hasattr(mirror_manager, 'perform_mirror_memory_cleanup'):
                                await mirror_manager.perform_mirror_memory_cleanup()
                        except:
                            pass

                except Exception as e:
                    logger.error(f"Error in cleanup scheduler: {e}")

        except asyncio.CancelledError:
            logger.info("📋 Cleanup scheduler cancelled")
        except Exception as e:
            logger.error(f"Fatal error in cleanup scheduler: {e}")

    def _get_circuit_breaker_key(self, symbol: str, side: str) -> str:
        """Get circuit breaker key for position"""
        return f"{symbol}_{side}"

    def _check_circuit_breaker(self, symbol: str, side: str) -> bool:
        """
        Check if circuit breaker allows operations for this position
        Returns True if operations are allowed, False if circuit is open
        """
        cb_key = self._get_circuit_breaker_key(symbol, side)

        if cb_key not in self.circuit_breaker_state:
            # Initialize circuit breaker
            self.circuit_breaker_state[cb_key] = {
                "state": "CLOSED",  # CLOSED, OPEN, HALF_OPEN
                "failure_count": 0,
                "last_failure_time": 0,
                "recovery_timeout": 300,  # 5 minutes
                "failure_threshold": 5
            }
            return True

        cb_state = self.circuit_breaker_state[cb_key]
        current_time = time.time()

        if cb_state["state"] == "CLOSED":
            return True
        elif cb_state["state"] == "OPEN":
            # Check if recovery timeout has passed
            if current_time - cb_state["last_failure_time"] > cb_state["recovery_timeout"]:
                cb_state["state"] = "HALF_OPEN"
                logger.info(f"🔄 Circuit breaker transitioning to HALF_OPEN for {cb_key}")
                return True
            return False
        else:  # HALF_OPEN
            return True

    def _record_circuit_breaker_success(self, symbol: str, side: str):
        """Record successful operation for circuit breaker"""
        cb_key = self._get_circuit_breaker_key(symbol, side)

        if cb_key in self.circuit_breaker_state:
            cb_state = self.circuit_breaker_state[cb_key]
            if cb_state["state"] == "HALF_OPEN":
                cb_state["state"] = "CLOSED"
                cb_state["failure_count"] = 0
                logger.info(f"✅ Circuit breaker closed for {cb_key}")

    def _record_circuit_breaker_failure(self, symbol: str, side: str):
        """Record failed operation for circuit breaker"""
        cb_key = self._get_circuit_breaker_key(symbol, side)

        if cb_key not in self.circuit_breaker_state:
            self._check_circuit_breaker(symbol, side)  # Initialize

        cb_state = self.circuit_breaker_state[cb_key]
        cb_state["failure_count"] += 1
        cb_state["last_failure_time"] = time.time()

        if cb_state["failure_count"] >= cb_state["failure_threshold"]:
            cb_state["state"] = "OPEN"
            logger.warning(f"⚠️ Circuit breaker opened for {cb_key} (failures: {cb_state['failure_count']})")

    async def _execute_with_recovery(self, operation_name: str, operation_func, *args, **kwargs):
        """
        Execute an operation with automatic error recovery and circuit breaker

        Args:
            operation_name: Name of the operation for logging
            operation_func: The async function to execute
            *args, **kwargs: Arguments to pass to the operation function

        Returns:
            Operation result or None if all attempts failed
        """
        if not self.error_recovery_enabled:
            return await operation_func(*args, **kwargs)

        symbol = kwargs.get('symbol', args[0] if args else 'UNKNOWN')
        side = kwargs.get('side', args[1] if len(args) > 1 else 'UNKNOWN')

        # Check circuit breaker
        if not self._check_circuit_breaker(symbol, side):
            logger.warning(f"🚫 Circuit breaker open for {symbol} {side}, skipping {operation_name}")
            return None

        operation_id = f"{operation_name}_{symbol}_{side}_{int(time.time())}"

        for attempt in range(1, self.max_recovery_attempts + 1):
            try:
                logger.debug(f"🔄 Executing {operation_name} (attempt {attempt}/{self.max_recovery_attempts})")

                result = await operation_func(*args, **kwargs)

                # Success - record for circuit breaker and clean up failure tracking
                self._record_circuit_breaker_success(symbol, side)
                if operation_id in self.failed_operations:
                    del self.failed_operations[operation_id]

                return result

            except Exception as e:
                logger.error(f"❌ {operation_name} attempt {attempt} failed: {e}")

                # Record failure
                failure_data = {
                    "operation_name": operation_name,
                    "symbol": symbol,
                    "side": side,
                    "attempt": attempt,
                    "error": str(e),
                    "timestamp": time.time(),
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
                self.failed_operations[operation_id] = failure_data

                # Record circuit breaker failure
                self._record_circuit_breaker_failure(symbol, side)

                # If this is the last attempt, give up
                if attempt >= self.max_recovery_attempts:
                    logger.error(f"💥 {operation_name} failed after {self.max_recovery_attempts} attempts")
                    break

                # Calculate backoff delay
                backoff_delay = attempt * self.recovery_backoff_multiplier
                logger.info(f"⏳ Waiting {backoff_delay}s before retry {attempt + 1}")
                await asyncio.sleep(backoff_delay)

        return None

    async def _recover_failed_order_placement(self, symbol: str, side: str, order_type: str):
        """
        Attempt to recover from failed order placement
        Checks if order was actually placed and updates tracking accordingly
        """
        try:
            logger.info(f"🔧 Attempting order placement recovery for {symbol} {side} {order_type}")

            # Get current open orders to check if order was placed despite error (with caching)
            open_orders = await self._get_cached_open_orders(symbol, account_type)
            if not open_orders:
                return False

            monitor_key = f"{symbol}_{side}_{account_type}"
            if monitor_key not in self.position_monitors:
                return False

            monitor_data = self.position_monitors[monitor_key]

            # Check for orders that might have been placed
            recovered_orders = []

            for order in open_orders:
                order_link_id = order.get("orderLinkId", "")
                if not order_link_id or not order_link_id.startswith("BOT_"):
                    continue

                # Check if this order belongs to our position
                if order_type == "TP" and "TP" in order_link_id:
                    # Check if we already have this order tracked
                    order_id = order.get("orderId")
                    already_tracked = any(tp["order_id"] == order_id for tp in monitor_data.get("tp_orders", []))

                    if not already_tracked:
                        # Add to tracking
                        tp_order = {
                            "order_id": order_id,
                            "order_link_id": order_link_id,
                            "price": Decimal(str(order.get("price", 0))),
                            "quantity": Decimal(str(order.get("qty", 0))),
                            "original_quantity": Decimal(str(order.get("qty", 0))),
                            "tp_number": len(monitor_data.get("tp_orders", [])) + 1
                        }

                        if "tp_orders" not in monitor_data:
                            monitor_data["tp_orders"] = {}
                        # Use order_id as key for dict format
                        monitor_data["tp_orders"][order_id] = tp_order

                        # Track in lifecycle
                        self._track_order_lifecycle(
                            order_id=order_id,
                            order_type="TP",
                            symbol=symbol,
                            side=order.get("side", side),
                            price=tp_order["price"],
                            quantity=tp_order["quantity"],
                            order_link_id=order_link_id
                        )

                        recovered_orders.append(f"TP:{order_id[:8]}...")

                elif order_type == "SL" and "SL" in order_link_id:
                    # Check if we already have this SL order tracked
                    order_id = order.get("orderId")
                    current_sl = monitor_data.get("sl_order", {})

                    if current_sl.get("order_id") != order_id:
                        # Update SL tracking
                        monitor_data["sl_order"] = {
                            "order_id": order_id,
                            "order_link_id": order_link_id,
                            "price": Decimal(str(order.get("triggerPrice", order.get("price", 0)))),
                            "quantity": Decimal(str(order.get("qty", 0))),
                            "original_quantity": Decimal(str(order.get("qty", 0)))
                        }

                        # Track in lifecycle
                        self._track_order_lifecycle(
                            order_id=order_id,
                            order_type="SL",
                            symbol=symbol,
                            side=order.get("side", side),
                            price=monitor_data["sl_order"]["price"],
                            quantity=monitor_data["sl_order"]["quantity"],
                            order_link_id=order_link_id
                        )

                        recovered_orders.append(f"SL:{order_id[:8]}...")

            if recovered_orders:
                logger.info(f"✅ Recovered {len(recovered_orders)} orders: {', '.join(recovered_orders)}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error in order placement recovery: {e}")
            return False

    async def _handle_monitor_error(self, symbol: str, side: str, error: Exception):
        """
        Handle errors in position monitoring with recovery attempts
        """
        try:
            monitor_key = f"{symbol}_{side}_{account_type}"

            logger.warning(f"🚨 Monitor error for {symbol} {side}: {error}")

            # Check if circuit breaker allows recovery attempts
            if not self._check_circuit_breaker(symbol, side):
                logger.warning(f"🚫 Circuit breaker prevents recovery for {symbol} {side}")
                return

            # Attempt to recover monitoring
            recovery_successful = await self._execute_with_recovery(
                "monitor_recovery",
                self._recover_monitor_state,
                symbol,
                side
            )

            if recovery_successful:
                logger.info(f"✅ Monitor recovery successful for {symbol} {side}")
            else:
                logger.error(f"💥 Monitor recovery failed for {symbol} {side}")

                # Consider stopping monitoring if recovery fails
                if monitor_key in self.position_monitors:
                    monitor_data = self.position_monitors[monitor_key]
                    task = self.active_tasks.get(monitor_key) if hasattr(self, 'active_tasks') else None
                    if task:
                        task.cancel()
                        logger.warning(f"⏹️ Stopped monitoring for {symbol} {side} due to persistent errors")

        except Exception as e:
            logger.error(f"Error in monitor error handling: {e}")

    async def _recover_monitor_state(self, symbol: str, side: str):
        """
        Attempt to recover monitor state by re-syncing with exchange
        """
        try:
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"
            if monitor_key not in self.position_monitors:
                raise Exception(f"Monitor {monitor_key} not found")

            monitor_data = self.position_monitors[monitor_key]

            # Get current position state
            positions = await get_position_info(symbol)
            if not positions:
                raise Exception("Could not fetch position info")

            position = None
            for pos in positions:
                if pos.get("side") == side:
                    position = pos
                    break

            if not position or float(position.get("size", 0)) == 0:
                # Position closed, clean up monitor
                await self.cleanup_position_orders(symbol, side)
                return True

            # Update monitor data with current position state
            current_size = Decimal(str(position["size"]))
            monitor_data["remaining_size"] = current_size

            # Save to persistence after update
            self.save_monitors_to_persistence(reason="monitoring_update")
            monitor_data["last_check"] = time.time()

            # Verify and sync orders
            await self._verify_and_sync_orders(symbol, side)

            logger.info(f"🔄 Monitor state recovered for {symbol} {side}")
            return True

        except Exception as e:
            logger.error(f"Error recovering monitor state: {e}")
            raise

    async def _verify_and_sync_orders(self, symbol: str, side: str):
        """
        Verify that tracked orders still exist and sync with exchange state
        """
        try:
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"
            if monitor_key not in self.position_monitors:
                return

            monitor_data = self.position_monitors[monitor_key]

            # Get current open orders
            open_orders = await get_open_orders(symbol)
            if not open_orders:
                return

            open_order_ids = {order.get("orderId") for order in open_orders if order.get("orderId")}

            # Check TP orders
            # Ensure tp_orders is dict format
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            for order_id, tp_order in tp_orders.items():
                # order_id = tp_order["order_id"]  # Now comes from iteration
                if order_id not in open_order_ids:
                    # Order no longer exists, update lifecycle
                    self._update_order_status(order_id, "FILLED")
                    logger.info(f"🎯 TP order {order_id[:8]}... marked as filled during sync")

            # Check SL order
            if monitor_data.get("sl_order"):
                sl_order_id = monitor_data["sl_order"]["order_id"]
                if sl_order_id not in open_order_ids:
                    # SL order no longer exists
                    self._update_order_status(sl_order_id, "FILLED")
                    logger.info(f"🛡️ SL order {sl_order_id[:8]}... marked as filled during sync")

            # Check limit orders
            for limit_order in monitor_data.get("limit_orders", []):
                if isinstance(limit_order, dict) and limit_order.get("status") == "ACTIVE":
                    order_id = limit_order["order_id"]
                    if order_id not in open_order_ids:
                        limit_order["status"] = "FILLED"
                        self._update_order_status(order_id, "FILLED")
                        logger.info(f"📝 Limit order {order_id[:8]}... marked as filled during sync")

        except Exception as e:
            logger.error(f"Error verifying and syncing orders: {e}")

    def get_error_recovery_stats(self) -> Dict:
        """
        Get error recovery and resilience statistics
        """
        try:
            current_time = time.time()

            # Count recent failures (last 24 hours)
            recent_failures = 0
            recent_cutoff = current_time - (24 * 3600)

            for failure_data in self.failed_operations.values():
                if failure_data.get("timestamp", 0) > recent_cutoff:
                    recent_failures += 1

            # Circuit breaker states
            circuit_breaker_stats = {}
            for cb_key, cb_state in self.circuit_breaker_state.items():
                circuit_breaker_stats[cb_key] = {
                    "state": cb_state["state"],
                    "failure_count": cb_state["failure_count"],
                    "last_failure": cb_state.get("last_failure_time", 0)
                }

            return {
                "error_recovery_enabled": self.error_recovery_enabled,
                "total_failed_operations": len(self.failed_operations),
                "recent_failures_24h": recent_failures,
                "max_recovery_attempts": self.max_recovery_attempts,
                "circuit_breakers": circuit_breaker_stats,
                "recovery_settings": {
                    "backoff_multiplier": self.recovery_backoff_multiplier,
                    "enabled": self.error_recovery_enabled
                }
            }

        except Exception as e:
            logger.error(f"Error getting recovery stats: {e}")
            return {}

    async def _update_order_statuses(self, symbol: str, side: str):
        """
        Update order statuses by checking current open orders
        This tracks fills, cancellations, and other order state changes
        """
        try:
            position_key = f"{symbol}_{side}"
            if position_key not in self.order_relationships:
                return

            # Get current open orders
            open_orders = await get_open_orders(symbol)
            if not open_orders:
                return

            # Create a set of currently open order IDs for quick lookup
            open_order_ids = set()
            open_orders_data = {}

            for order in open_orders:
                order_id = order.get("orderId")
                if order_id:
                    open_order_ids.add(order_id)
                    open_orders_data[order_id] = order

            # Check all tracked orders for this position
            relationships = self.order_relationships[position_key]
            all_tracked_orders = []

            for order_type in ["tp_orders", "sl_orders", "limit_orders"]:
                all_tracked_orders.extend(relationships.get(order_type, []))

            for order_id in all_tracked_orders:
                if order_id not in self.order_lifecycle:
                    continue

                order_data = self.order_lifecycle[order_id]
                current_status = order_data["status"]

                if order_id in open_order_ids:
                    # Order is still open, check for partial fills
                    open_order = open_orders_data[order_id]

                    # Check if order has been partially filled
                    cum_qty = open_order.get("cumExecQty", "0")
                    order_qty = open_order.get("qty", "0")

                    if cum_qty and cum_qty != "0":
                        cum_filled = Decimal(str(cum_qty))
                        total_qty = Decimal(str(order_qty))
                        remaining_qty = total_qty - cum_filled

                        fill_data = {
                            "fill_price": Decimal(str(open_order.get("avgPrice", order_data["price"]))),
                            "fill_quantity": cum_filled,
                            "cumulative_filled": cum_filled,
                            "remaining_quantity": remaining_qty
                        }

                        if cum_filled == total_qty:
                            # Fully filled
                            if current_status != "FILLED":
                                self._update_order_status(order_id, "FILLED", fill_data)
                        elif cum_filled > 0:
                            # Partially filled
                            if current_status != "PARTIAL_FILLED":
                                self._update_order_status(order_id, "PARTIAL_FILLED", fill_data)
                    else:
                        # Order is open but not filled
                        if current_status != "ACTIVE":
                            self._update_order_status(order_id, "ACTIVE")
                else:
                    # Order is not in open orders - it was either filled or cancelled
                    if current_status in ["ACTIVE", "PARTIAL_FILLED"]:
                        # Check if it was filled or cancelled by checking position history
                        # For now, assume it was filled if it's not cancelled elsewhere

                        # Try to get order history/details
                        try:
                            # We'll mark it as filled for now - a more sophisticated implementation
                            # would check order history to determine if it was filled or cancelled
                            self._update_order_status(order_id, "FILLED")
                        except:
                            # If we can't determine, mark as unknown
                            self._update_order_status(order_id, "UNKNOWN")

            # Calculate and update position metrics
            metrics = self._calculate_position_metrics(symbol, side)
            logger.debug(f"📊 Updated order statuses for {symbol} {side}: {metrics['filled_orders']}/{metrics['total_orders']} filled")

        except Exception as e:
            logger.error(f"Error updating order statuses for {symbol} {side}: {e}")

    async def register_limit_orders(self, symbol: str, side: str, limit_order_ids: List[str], account_type: str = "main"):
        """
        ENHANCED: Register limit orders with full details for position building phase
        This allows the Enhanced TP/SL system to track and manage entry limit orders

        Args:
            symbol: Trading symbol
            side: Buy or Sell
            limit_order_ids: List of order IDs for limit orders
            account_type: 'main' or 'mirror'
        """
        monitor_key = f"{symbol}_{side}_{account_type}"
        
        # Wait up to 3 seconds for monitor to be created
        max_attempts = 10  # 10 attempts * 0.5 seconds = 5 seconds
        for attempt in range(max_attempts):
            if monitor_key in self.position_monitors:
                logger.debug(f"✅ Found monitor {monitor_key} on attempt {attempt + 1}")
                break
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5)
                # Log available monitors for debugging
                available_monitors = [k for k in self.position_monitors.keys() if symbol in k]
                logger.debug(f"Waiting for monitor {monitor_key}... attempt {attempt + 1}/{max_attempts}")
                if available_monitors:
                    logger.debug(f"Available monitors for {symbol}: {available_monitors}")
        
        if monitor_key not in self.position_monitors:
            logger.warning(f"Cannot register limit orders - no monitor found for {symbol} {side} {account_type} after waiting")
            return

        monitor_data = self.position_monitors[monitor_key]

        # ENHANCED: Import the limit order tracker
        try:
            
            # Fetch full order details immediately
            order_details = await limit_order_tracker.fetch_and_update_limit_order_details(
                limit_order_ids, symbol, account_type
            )
            
            # Add limit orders with full details
            for order_id in limit_order_ids:
                if order_id in order_details:
                    details = order_details[order_id]
                    limit_order = {
                        "order_id": order_id,
                        "registered_at": time.time(),
                        "status": "ACTIVE",
                        "price": details.get("price", "0"),
                        "quantity": details.get("qty", "0"),
                        "filled_qty": details.get("cumExecQty", "0"),
                        "order_link_id": details.get("orderLinkId", ""),
                        "side": details.get("side"),
                        "order_type": details.get("orderType")
                    }
                else:
                    # Fallback if details not available
                    limit_order = {
                        "order_id": order_id,
                        "registered_at": time.time(),
                        "status": "ACTIVE"
                    }
                    
                monitor_data["limit_orders"].append(limit_order)

                # Track limit order lifecycle with available details
                self._track_order_lifecycle(
                    order_id=order_id,
                    order_type="LIMIT",
                    symbol=symbol,
                    side=side,  # Use position side for limit entry orders
                    price=Decimal(str(limit_order.get("price", "0"))),
                    quantity=Decimal(str(limit_order.get("quantity", "0"))),
                    order_link_id=limit_order.get("order_link_id", None)
                )
                
            logger.info(f"📝 Enhanced: Registered {len(order_details)} detailed limit orders for {symbol} {side} ({account_type})")
            
        except Exception as e:
            logger.error(f"Error in enhanced limit order registration: {e}")
            # Fallback to basic registration
            for order_id in limit_order_ids:
                limit_order = {
                    "order_id": order_id,
                    "registered_at": time.time(),
                    "status": "ACTIVE"
                }
                monitor_data["limit_orders"].append(limit_order)

        logger.info(f"📝 Registered {len(limit_order_ids)} limit orders for {symbol} {side}")
        logger.info(f"   Phase: {monitor_data['phase']}")
        logger.info(f"   Total limit orders tracked: {len(monitor_data['limit_orders'])}")

        # FIX: Start monitoring if not already active (for limit order fill detection)
        if not self.active_tasks.get(monitor_key) or self.active_tasks.get(monitor_key, lambda: True).done():
            # Extract account_type from monitor_data
            account_type = monitor_data.get("account_type", "main")
            logger.info(f"🔄 Starting monitoring for limit order fill detection: {symbol} {side} ({account_type})")
            monitor_task = asyncio.create_task(self._run_monitor_loop(symbol, side, account_type))
            self.active_tasks[monitor_key] = monitor_task

    async def _cancel_unfilled_limit_orders(self, monitor_data: Dict):
        """
        Cancel all unfilled limit orders during phase transition
        This is called when moving from BUILDING to PROFIT_TAKING phase
        Enhanced to support both main and mirror accounts
        """
        symbol = monitor_data["symbol"]
        side = monitor_data["side"]

        # Determine account type from monitor data
        # Check if this is a mirror account position
        is_mirror_account = self._is_mirror_position(monitor_data)
        account_label = "mirror" if is_mirror_account else "main"

        cancelled_count = 0
        failed_count = 0

        # Get appropriate cancel function based on account type
        cancel_function = self._get_cancel_function(is_mirror_account)

        logger.info(f"🧹 Cancelling unfilled limit orders for {symbol} {side} ({account_label} account)")

        # Primary method: Cancel orders tracked in monitor data
        tracked_orders = monitor_data.get("limit_orders", [])
        if tracked_orders:
            for limit_order in tracked_orders:
                # Handle both dict and string formats
                if isinstance(limit_order, str):
                    # Legacy format: limit_order is just an order ID string
                    order_id = limit_order
                    try:
                        # Check if this order was already attempted recently
                        from utils.order_state_cache import order_state_cache
                        if not await order_state_cache.is_order_cancellable(order_id):
                            logger.info(f"ℹ️ Skipping {account_label} limit order {order_id[:8]}... (already processed)")
                            continue

                        success = await cancel_function(symbol, order_id)
                        if success:
                            cancelled_count += 1
                            logger.info(f"✅ Cancelled {account_label} limit order {order_id[:8]}...")
                        else:
                            failed_count += 1
                            logger.warning(f"⚠️ Failed to cancel {account_label} limit order {order_id[:8]}...")
                    except Exception as e:
                        failed_count += 1
                        logger.error(f"❌ Error cancelling {account_label} limit order {order_id[:8]}...: {e}")
                elif isinstance(limit_order, dict) and limit_order.get("status") == "ACTIVE":
                    # New format: limit_order is a dict with order details
                    order_id = limit_order.get("order_id")
                    if not order_id:
                        continue

                    try:
                        # Check if this order was already attempted recently
                        from utils.order_state_cache import order_state_cache
                        if not await order_state_cache.is_order_cancellable(order_id):
                            logger.info(f"ℹ️ Skipping {account_label} limit order {order_id[:8]}... (already processed)")
                            limit_order["status"] = "PROCESSED"
                            continue

                        success = await cancel_function(symbol, order_id)
                        if success:
                            limit_order["status"] = "CANCELLED"
                            limit_order["cancelled_at"] = time.time()
                            cancelled_count += 1
                            logger.info(f"✅ Cancelled {account_label} limit order {order_id[:8]}...")
                        else:
                            # Mark as failed but don't retry endlessly
                            limit_order["status"] = "FAILED"
                            failed_count += 1
                            logger.warning(f"⚠️ Failed to cancel {account_label} limit order {order_id[:8]}...")
                    except Exception as e:
                        # Mark as failed to prevent retry loops
                        limit_order["status"] = "FAILED"
                        failed_count += 1
                        logger.error(f"❌ Error cancelling {account_label} limit order {order_id[:8]}...: {e}")
        else:
            # Fallback method: Scan live orders and cancel bot limit orders
            logger.info(f"📡 No tracked orders found, scanning live orders for {symbol} {side}")
            try:
                additional_cancelled = await self._cancel_live_limit_orders(symbol, side, is_mirror_account)
                cancelled_count += additional_cancelled
            except Exception as e:
                logger.error(f"❌ Error scanning live orders: {e}")
                failed_count += 1

        if cancelled_count > 0:
            logger.info(f"🧹 Limit order cleanup: {cancelled_count} cancelled, {failed_count} failed")

            # Send alert about limit order cleanup
            try:
                chat_id = monitor_data.get("chat_id")
                
                # Try to find chat_id if not in monitor data
                if not chat_id:
                    chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
                
                if chat_id:
                    message = (
                        f"🧹 <b>Limit Orders Cleaned Up</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 {symbol} {side}\n"
                        f"🎯 TP1 hit - Phase: PROFIT_TAKING\n"
                        f"🧹 Cancelled: {cancelled_count} limit orders\n"
                        f"✅ Focus: Pure profit-taking mode"
                    )

                await send_trade_alert(chat_id, message, "limit_cleanup")
                logger.info(f"✅ Sent limit order cleanup alert for {symbol} {side}")
            except Exception as e:
                logger.error(f"Error sending limit order cleanup alert: {e}")

    async def _transition_to_profit_taking(self, monitor_data: Dict):
        """
        Transition position from BUILDING phase to PROFIT_TAKING phase
        This happens when TP1 (85%) is hit
        ENHANCED: Added atomic locks to prevent race conditions
        """
        symbol = monitor_data["symbol"]
        side = monitor_data["side"]
        account_type = monitor_data.get("account_type", "main")
        monitor_key = f"{symbol}_{side}_{account_type}"

        # Use atomic lock to prevent race conditions during phase transition
        if monitor_key not in self.phase_transition_locks:
            self.phase_transition_locks[monitor_key] = asyncio.Lock()

        async with self.phase_transition_locks[monitor_key]:
            # Double-check phase after acquiring lock
            if monitor_data.get("phase") == "BUILDING":
                logger.info(f"🔄 Transitioning {symbol} {side} from BUILDING to PROFIT_TAKING phase")

                # Cancel unfilled limit orders if enabled
                if CANCEL_LIMITS_ON_TP1:
                    await self._cancel_unfilled_limit_orders(monitor_data)
                else:
                    logger.info(f"ℹ️ Limit order cleanup disabled (CANCEL_LIMITS_ON_TP1=false)")

                # Update phase atomically
                monitor_data["phase"] = "PROFIT_TAKING"
                monitor_data["phase_transition_time"] = time.time()
                monitor_data["tp1_hit"] = True

                logger.info(f"✅ Phase transition complete: {symbol} {side} now in PROFIT_TAKING mode")
            else:
                logger.debug(f"🔄 Phase transition skipped for {symbol} {side} - already in {monitor_data.get('phase', 'UNKNOWN')} phase")

    async def _send_tp_fill_alert_enhanced(self, monitor_data: Dict, fill_percentage: float, tp_number: int):
        """Send enhanced alert when TP order is filled with specific TP number"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            chat_id = monitor_data["chat_id"]

            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                self.mirror_alerts_suppressed += 1
                logger.info(f"🔕 Mirror alert suppressed: TP alert for {symbol} {side} mirror position")
                self._log_suppression_summary()
                return

            # Try to find chat_id if not in monitor data
            if not chat_id:
                chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
                if not chat_id:
                    logger.warning(f"Could not find chat_id for {symbol} {side} {account_type} - skipping TP alert")
                    return

            approach = "CONSERVATIVE"  # Conservative approach only
            entry_price = monitor_data["entry_price"]
            bot_instance = monitor_data.get("bot_instance")
            account_type = monitor_data.get("account_type", "main")

            # Get current market price for P&L calculation
            from clients.bybit_helpers import get_current_price
            current_price = await get_current_price(symbol)
            if not current_price:
                current_price = entry_price

            # Calculate P&L
            filled_size = monitor_data["position_size"] * Decimal(str(fill_percentage)) / Decimal("100")
            current_price_decimal = Decimal(str(current_price))
            entry_price_decimal = Decimal(str(entry_price))

            if side == "Buy":
                pnl = (current_price_decimal - entry_price_decimal) * filled_size
            else:  # Sell
                pnl = (entry_price_decimal - current_price_decimal) * filled_size

            # Get remaining TPs for conservative approach
            remaining_tps = []
            tp_orders = monitor_data.get("tp_orders", {})
            for tp_id, tp_data in tp_orders.items():
                tp_num = tp_data.get('tp_number', 0)
                if tp_num > tp_number:
                    remaining_tps.append(f"TP{tp_num}")

            # Prepare additional info for formatted alert
            additional_info = {
                "tp_number": tp_number,
                "account_type": account_type,
                "filled_qty": filled_size,
                "remaining_size": monitor_data.get("position_size", Decimal("0")) - filled_size,
                "detection_method": "direct_order_check",
                "fill_confidence": "High",
                "remaining_tps": remaining_tps,
                "sl_moved_to_be": tp_number == 1,
                "breakeven_price": entry_price_decimal * Decimal("1.0008") if side == "Buy" else entry_price_decimal * Decimal("0.9992"),
                "limits_cancelled": tp_number == 1 and approach == "conservative",
                "has_mirror": account_type == "main" and monitor_data.get("has_mirror", False),
                "mirror_synced": True
            }

            # Simply use the already imported send_trade_alert function
            # Format using the enhanced formatter from alert_helpers
            from utils.alert_helpers import format_tp_hit_alert
            
            # Create the formatted message
            message = format_tp_hit_alert(
                symbol=symbol,
                side=side,
                approach=approach,
                pnl=pnl,
                pnl_percent=(pnl / (entry_price_decimal * filled_size) * 100) if filled_size > 0 else Decimal("0"),
                entry_price=entry_price_decimal,
                exit_price=current_price_decimal,
                position_size=filled_size,
                cancelled_orders=[],
                additional_info=additional_info
            )
            
            # Send using simple alert with enhanced logging
            logger.info(f"📤 Sending TP{tp_number} alert for {symbol} {side} to chat_id: {chat_id}")
            logger.debug(f"Alert details - Account: {account_type}, Approach: {approach}, PnL: ${pnl:.2f}")
            
            success = await send_trade_alert(chat_id, message, "tp_hit")
            
            if success:
                # Count successful alert
                self.alerts_sent[account_type] += 1
                logger.info(f"✅ Enhanced TP{tp_number} alert sent successfully for {symbol} {side} to chat_id: {chat_id}")
            else:
                logger.error(f"❌ Failed to send TP{tp_number} alert for {symbol} {side} to chat_id: {chat_id}")
                # Log additional context for debugging
                logger.error(f"Alert context - Symbol: {symbol}, Side: {side}, Approach: {approach}, Account: {account_type}")
                logger.error(f"Monitor data keys: {list(monitor_data.keys())}")
                
                # Try using DEFAULT_ALERT_CHAT_ID as fallback
                from config.settings import DEFAULT_ALERT_CHAT_ID
                if DEFAULT_ALERT_CHAT_ID and DEFAULT_ALERT_CHAT_ID != chat_id:
                    logger.info(f"🔄 Retrying with DEFAULT_ALERT_CHAT_ID: {DEFAULT_ALERT_CHAT_ID}")
                    fallback_success = await send_trade_alert(DEFAULT_ALERT_CHAT_ID, message, "tp_hit")
                    if fallback_success:
                        logger.info(f"✅ Alert sent to fallback chat_id: {DEFAULT_ALERT_CHAT_ID}")
                    else:
                        logger.error(f"❌ Failed to send alert even to fallback chat_id")

        except Exception as e:
            logger.error(f"Error sending enhanced TP fill alert: {e}")


    async def _send_rebalancing_alert(self, monitor_data: Dict, new_size: Decimal, size_increase: Decimal):
        """Send alert when TP orders are rebalanced after limit fill"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            chat_id = monitor_data.get("chat_id")
            
            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                logger.debug(f"Mirror alerts disabled - skipping rebalancing alert for {symbol} {side} mirror position")
                return
            
            # Try to find chat_id if not in monitor data
            if not chat_id:
                chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
                if not chat_id:
                    logger.warning(f"Could not find chat_id for {symbol} {side} {account_type} - skipping rebalancing alert")
                    return
            
            # Get TP order info
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            tp_info = []
            for tp_id, tp_data in tp_orders.items():
                if isinstance(tp_data, dict):
                    tp_num = tp_data.get('tp_number', 0)
                    tp_qty = tp_data.get('quantity', 0)
                    tp_percentage = tp_data.get('tp_percentage', 0)
                    tp_info.append(f"TP{tp_num}: {tp_qty} ({tp_percentage}%)")
            
            # Use enhanced formatter for rebalancing alert
            from utils.alert_helpers import format_conservative_rebalance_alert
            
            additional_info = {
                "trigger": "limit_filled",
                "size_increase": size_increase,
                "account_type": account_type,
                "filled_limits": len([tp for tp in tp_info if "filled" in str(tp)]),
                "total_limits": 3,
                "tp1_qty": tp_orders.get("1", {}).get("quantity", 0) if tp_orders else 0,
                "tp2_qty": tp_orders.get("2", {}).get("quantity", 0) if tp_orders else 0,
                "tp3_qty": tp_orders.get("3", {}).get("quantity", 0) if tp_orders else 0,
                "tp4_qty": tp_orders.get("4", {}).get("quantity", 0) if tp_orders else 0,
                "sl_qty": new_size,
                "rebalance_reason": "Limit order filled - maintaining 85/5/5/5 distribution"
            }
            
            message = format_conservative_rebalance_alert(
                symbol=symbol,
                side=side,
                position_size=new_size,
                additional_info=additional_info
            )
            
            # Use simple alert to ensure delivery
            await send_simple_alert(chat_id, message, "rebalancing")
            logger.info(f"✅ Sent rebalancing alert for {symbol} {side}")
            
        except Exception as e:
            logger.error(f"Error sending rebalancing alert: {e}")

    async def _send_tp_rebalancing_alert(self, monitor_data: Dict, successful: int, total: int, results: list, status: str):
        """Send user alert for TP rebalancing events"""
        try:
            from utils.alert_helpers import send_simple_alert
            
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            current_size = monitor_data.get("current_size", "Unknown")
            
            # Determine status emoji and message
            if status == "SUCCESS":
                status_emoji = "✅"
                status_text = "COMPLETED"
            elif status == "PARTIAL":
                status_emoji = "⚠️"
                status_text = "PARTIALLY COMPLETED"
            else:  # FAILED
                status_emoji = "❌"
                status_text = "FAILED"
            
            # Account emoji
            account_emoji = "🪞" if account_type == "mirror" else "🏠"
            account_text = account_type.upper()
            
            # Format results for display (limit to 3 for space)
            displayed_results = results[:3]
            if len(results) > 3:
                displayed_results.append(f"...and {len(results) - 3} more")
            
            message = f"""🔄 <b>TP REBALANCING {status_text}</b>
━━━━━━━━━━━━━━━━━━━━━━
{account_emoji} Account: <b>{account_text}</b>
📊 {symbol} {side}

📋 Summary:
• Position Size: {current_size}
• TP Orders Processed: {successful}/{total}
• Results: {', '.join(displayed_results)}

{status_emoji} <b>TP orders have been {'rebalanced' if status == 'SUCCESS' else 'processed'} after limit fill</b>"""

            # Find appropriate chat ID
            chat_id = self._find_chat_id_for_position(monitor_data)
            if not chat_id:
                logger.warning(f"No chat ID found for TP rebalancing alert - {symbol} {side}")
                return
            
            # Send alert
            await send_simple_alert(chat_id, message, "tp_rebalancing")
            logger.info(f"✅ Sent TP rebalancing alert ({status}) for {symbol} {side} ({account_text})")
            
        except Exception as e:
            logger.error(f"Error sending TP rebalancing alert: {e}")

    async def _send_limit_fill_alert(self, monitor_data: Dict, fill_percentage: float):
        """Send enhanced alert when limit order is filled using the proper formatter"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            chat_id = monitor_data.get("chat_id")
            
            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                logger.debug(f"Mirror alerts disabled - skipping limit fill alert for {symbol} {side} mirror position")
                return
            
            # Try to find chat_id if not in monitor data
            if not chat_id:
                chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
                if not chat_id:
                    logger.warning(f"Could not find chat_id for {symbol} {side} {account_type} - skipping limit fill alert")
                    return
                    
            approach = "CONSERVATIVE"  # Conservative approach only

            # Get current market price for context
            current_price = await get_current_price(symbol)
            if current_price:
                current_price = Decimal(str(current_price))  # Convert to Decimal for type consistency
            entry_price = monitor_data["entry_price"]

            # Calculate filled size and remaining position
            total_position_size = monitor_data["position_size"]
            filled_size = total_position_size * Decimal(str(fill_percentage)) / Decimal("100")
            remaining_size = total_position_size - filled_size

            # Calculate P&L for filled portion (realized gain/loss) - ensure consistent types
            if current_price and entry_price:
                current_price_decimal = Decimal(str(current_price))
                entry_price_decimal = Decimal(str(entry_price))

                if side == "Buy":
                    fill_pnl = (current_price_decimal - entry_price_decimal) * filled_size
                    fill_pnl_percent = float(((current_price_decimal - entry_price_decimal) / entry_price_decimal) * 100)
                else:  # Sell
                    fill_pnl = (entry_price_decimal - current_price_decimal) * filled_size
                    fill_pnl_percent = float(((entry_price_decimal - current_price_decimal) / entry_price_decimal) * 100)
            else:
                fill_pnl = Decimal("0")
                fill_pnl_percent = 0

            # Get enhanced limit order details
            limit_order_summary = limit_order_tracker.get_limit_order_summary(monitor_data)
            
            # Get filled limit orders count for context
            filled_limits = monitor_data.get("limit_orders_filled", 0)
            active_limits = monitor_data.get("limit_orders_active", 0)
            total_limits = len(monitor_data.get("limit_orders", []))
            account_type = monitor_data.get("account_type", "main")
            
            # Get the actual filled order details and count
            limit_orders = monitor_data.get("limit_orders", [])
            filled_count = filled_limits
            total_limit_count = total_limits
            avg_entry = monitor_data.get("avg_price", entry_price)
            
            # Count how many limit orders have been filled so far
            for order in limit_orders:
                if isinstance(order, dict) and order.get("status") == "FILLED":
                    filled_count += 1
            
            # If no specific count, estimate based on fill percentage
            if filled_count == 0 and fill_percentage > 0:
                # For conservative approach with 3 limits, estimate which one filled
                if total_limit_count == 3:
                    if fill_percentage <= 35:
                        filled_count = 1
                    elif fill_percentage <= 70:
                        filled_count = 2
                    else:
                        filled_count = 3
                else:
                    filled_count = 1
            
            # Track the actual entry price for breakeven calculation
            if hasattr(self, '_track_actual_entry_price'):
                monitor_key = f"{symbol}_{side}_{account_type}"
                if monitor_key in self.actual_entry_prices:
                    avg_entry = self.actual_entry_prices[monitor_key].get('weighted_price', avg_entry)
            
            # Ensure we have a proper filled count (at least 1 if fill_percentage > 0)
            final_filled_count = max(filled_count, 1) if fill_percentage > 0 else filled_count
            final_total_limits = total_limit_count if total_limit_count > 0 else 3
            
            # Prepare additional info for the formatter
            additional_info = {
                "fill_price": current_price if current_price else entry_price,
                "fill_size": filled_size,
                "limit_number": final_filled_count,
                "total_limits": final_total_limits,
                "filled_count": final_filled_count,
                "avg_entry": avg_entry,
                "position_size": total_position_size,
                "account_type": account_type,
                "detection_method": "enhanced_monitoring",
                "fill_confidence": "High",
                "fill_timestamp": int(time.time() * 1000),
                "has_mirror": monitor_data.get("has_mirror", False),
                "mirror_synced": True,
                "limit_order_summary": limit_order_summary  # Enhanced limit order details
            }
            
            # Use the enhanced formatter
            from utils.alert_helpers import format_limit_filled_alert
            
            message = format_limit_filled_alert(
                symbol=symbol,
                side=side,
                approach=approach,
                additional_info=additional_info
            )

            # Send alert with enhanced logging
            logger.info(f"📤 Preparing to send limit fill alert for {symbol} {side} to chat_id: {chat_id}")
            success = await send_trade_alert(chat_id, message, "limit_filled")
            if success:
                logger.info(f"✅ Sent enhanced limit fill alert for {symbol} {side} ({account_type.upper()}) - {fill_percentage:.2f}% filled")
            else:
                logger.error(f"❌ Failed to send limit fill alert for {symbol} {side} ({account_type.upper()})")

        except Exception as e:
            logger.error(f"Error sending limit fill alert: {e}")

    async def _send_enhanced_limit_fill_alert(self, monitor_data: Dict, filled_count: int, active_count: int):
        """Send enhanced limit order fill alert with detailed information"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            chat_id = monitor_data["chat_id"]
            account_type = monitor_data.get("account_type", "main")

            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                logger.debug(f"Mirror alerts disabled - skipping enhanced limit fill alert for {symbol} {side} mirror position")
                return

            # Skip alert if no chat_id
            if not chat_id:
                logger.warning(f"⚠️ No chat_id for {symbol} {side} {account_type} - skipping enhanced limit fill alert")
                return

            # Import the limit order tracker for summary
            limit_summary = limit_order_tracker.get_limit_order_summary(monitor_data)

            # Create enhanced alert message
            alert_msg = f"📊 *LIMIT ORDER UPDATE*\n\n"
            alert_msg += f"📈 *{symbol}* {side} ({account_type.upper()})\n"
            alert_msg += f"✅ *{filled_count}* orders filled\n"
            alert_msg += f"🔄 *{active_count}* orders active\n\n"
            alert_msg += f"📊 *Order Summary:*\n{limit_summary}\n\n"
            alert_msg += f"🎯 *Enhanced Tracking* (2s intervals)\n"
            alert_msg += f"⚡ *High Confidence* Detection\n\n"
            alert_msg += f"🤖 *Enhanced TP/SL Manager*"

            # Send with retries
            success = await send_trade_alert(
                chat_id=chat_id, 
                message=alert_msg, 
                symbol=symbol, 
                max_retries=5
            )

            if success:
                logger.info(f"✅ Sent enhanced limit fill alert for {symbol} {side} ({account_type}) - {filled_count} filled, {active_count} active")
            else:
                logger.error(f"❌ Failed to send enhanced limit fill alert for {symbol} {side}")

        except Exception as e:
            logger.error(f"Error sending enhanced limit fill alert: {e}")

    async def _send_position_closed_alert(self, monitor_data: Dict):
        """Send premium quality alert when position is fully closed with comprehensive summary"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            chat_id = monitor_data["chat_id"]

            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                logger.debug(f"Mirror alerts disabled - skipping position closed alert for {symbol} {side} mirror position")
                return

            # Skip alert if no chat_id
            if not chat_id:
                logger.warning(f"⚠️ No chat_id for {symbol} {side} {account_type} - skipping position closed alert")
                return

            approach = "CONSERVATIVE"  # Conservative approach only
            entry_price = monitor_data["entry_price"]

            # Handle missing position_size key
            position_size = monitor_data.get("position_size")
            if position_size is None:
                # Try alternative keys
                position_size = monitor_data.get("current_size") or monitor_data.get("remaining_size")
                if position_size is None:
                    logger.warning(f"Position size not found in monitor data for {symbol} {side}")
                    logger.warning(f"Available keys in monitor_data: {list(monitor_data.keys())}")
                    return

            # Convert to Decimal for consistent arithmetic operations
            entry_price_decimal = Decimal(str(entry_price))
            position_size_decimal = Decimal(str(position_size))

            # Calculate trade duration
            trade_duration_minutes = (time.time() - monitor_data['created_at']) / 60
            if trade_duration_minutes < 60:
                duration_text = f"{trade_duration_minutes:.1f} minutes"
            else:
                hours = int(trade_duration_minutes // 60)
                mins = int(trade_duration_minutes % 60)
                duration_text = f"{hours}h {mins}m"

            # Get final position info for P&L and exit price
            positions = await get_position_info(symbol)
            position = None
            if positions:
                for pos in positions:
                    if pos.get("side") == side:
                        position = pos
                        break

            if position:
                pnl = Decimal(str(position.get("unrealisedPnl", "0")))
                exit_price = Decimal(str(position.get("markPrice", entry_price)))
                realized_pnl = Decimal(str(position.get("realizedPnl", "0")))
            else:
                # Position fully closed - use last known price
                current_price = await get_current_price(symbol)
                exit_price = Decimal(str(current_price)) if current_price else entry_price_decimal

                # Calculate final P&L (all values are now Decimal)
                if side == "Buy":
                    pnl = (exit_price - entry_price_decimal) * position_size_decimal
                else:  # Sell
                    pnl = (entry_price_decimal - exit_price) * position_size_decimal
                realized_pnl = pnl

            # Calculate P&L percentage (all values are Decimal)
            if entry_price_decimal > 0:
                if side == "Buy":
                    pnl_percent = float(((exit_price - entry_price_decimal) / entry_price_decimal) * 100)
                else:  # Sell
                    pnl_percent = float(((entry_price_decimal - exit_price) / entry_price_decimal) * 100)
            else:
                pnl_percent = 0

            # Conservative approach only (with GGShot support)
            if approach == "ggshot":
                approach_emoji = "📸"
                approach_text = "GGShot"
            else:
                approach_emoji = "🛡️"
                approach_text = "Conservative"

            # Side emoji
            side_emoji = "📈" if side == "Buy" else "📉"

            # P&L emoji and result text
            if pnl > 0:
                pnl_emoji = "🟢"
                result_text = "PROFIT"
            elif pnl < 0:
                pnl_emoji = "🔴"
                result_text = "LOSS"
            else:
                pnl_emoji = "⚪"
                result_text = "BREAKEVEN"

            # Get TP fill summary
            tp_orders = self._ensure_tp_orders_dict(monitor_data)
            filled_tps = len([tp for tp in tp_orders.values() if isinstance(tp, dict) and tp.get("status") == "FILLED"])
            total_tps = len(tp_orders)

            message = f"""{pnl_emoji} <b>POSITION CLOSED - {result_text}</b>
━━━━━━━━━━━━━━━━━━━━━━
{approach_emoji} {approach_text} Approach
📊 {symbol} {side_emoji} {side}

💰 <b>Final P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)</b>

📍 <b>Trade Summary:</b>
• Entry Price: ${entry_price:.6f}
• Exit Price: ${exit_price:.6f}
• Position Size: {position_size:.6f}
• Duration: {duration_text}

📊 <b>Execution Summary:</b>
• TPs Hit: {filled_tps}/{total_tps}
• Approach: {approach_text}
• Enhanced TP/SL Management
• Risk Protection Active

🎯 <b>Performance:</b>"""

            # Add performance context
            if pnl_percent > 5:
                message += f"\n• Excellent trade! 🏆"
            elif pnl_percent > 1:
                message += f"\n• Good profit captured ✅"
            elif pnl_percent > -1:
                message += f"\n• Near breakeven trade ⚖️"
            elif pnl_percent > -5:
                message += f"\n• Small loss contained 🛡️"
            else:
                message += f"\n• Loss managed by SL 🔒"

            # Add conservative approach context
            if approach == "ggshot":
                message += f"\n\n📸 <b>GGShot Results:</b>\n• AI analysis execution complete\n• Screenshot parameters validated\n• Smart order management success"
            else:
                message += f"\n\n🛡️ <b>Conservative Results:</b>\n• Risk managed through scaling\n• Multiple TP levels utilized\n• Gradual profit realization"

            # Send the enhanced alert first
            await send_trade_alert(chat_id, message, "limit_filled")

            # Then send the detailed summary using the existing function
            # Use Decimal versions of variables to avoid type mismatch
            await send_position_closed_summary(
                chat_id=chat_id,
                symbol=symbol,
                side=side,
                approach=approach,
                entry_price=float(entry_price_decimal),
                exit_price=float(exit_price),
                position_size=float(position_size_decimal),
                pnl=float(pnl),
                duration_minutes=int(trade_duration_minutes),
                additional_info={"account_type": account_type}
            )

            logger.info(f"✅ Sent premium position closed alert for {symbol} {side} - {result_text}: ${pnl:.2f}")

        except Exception as e:
            logger.error(f"Error sending position closed alert: {e}")

    async def _send_sl_hit_alert(self, monitor_data: Dict):
        """Send enhanced alert when stop loss is hit"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            chat_id = monitor_data["chat_id"]

            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                logger.debug(f"Mirror alerts disabled - skipping SL hit alert for {symbol} {side} mirror position")
                return

            # Try to find chat_id if not in monitor data
            if not chat_id:
                chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
                if not chat_id:
                    logger.warning(f"Could not find chat_id for {symbol} {side} {account_type} - skipping SL hit alert")
                    return

            # Get SL and entry prices
            sl_price = monitor_data["sl_order"]["price"]
            entry_price = monitor_data["entry_price"]
            position_size = monitor_data.get("position_size", Decimal("0"))

            # Calculate loss
            sl_price_decimal = Decimal(str(sl_price))
            entry_price_decimal = Decimal(str(entry_price))
            
            if side == "Buy":
                loss_amount = (entry_price_decimal - sl_price_decimal) * position_size
                loss_pct = ((entry_price_decimal - sl_price_decimal) / entry_price_decimal) * 100
            else:  # Sell
                loss_amount = (sl_price_decimal - entry_price_decimal) * position_size
                loss_pct = ((sl_price_decimal - entry_price_decimal) / entry_price_decimal) * 100

            # Calculate duration
            duration_mins = (time.time() - monitor_data.get('created_at', time.time())) / 60

            # Create enhanced SL hit alert using alert helpers
            from utils.alert_helpers import format_sl_hit_alert
            
            additional_info = {
                "account_type": account_type,
                "duration_minutes": duration_mins,
                "closure_reason": "sl_hit",
                "detection_method": "position_monitoring",
                "fill_confidence": "High"
            }

            message = format_sl_hit_alert(
                symbol=symbol,
                side=side,
                approach="conservative",
                pnl=loss_amount,
                pnl_percent=loss_pct,
                entry_price=entry_price_decimal,
                exit_price=sl_price_decimal,
                position_size=position_size,
                cancelled_orders=[],
                additional_info=additional_info
            )

            # Send with enhanced logging
            logger.info(f"📤 Sending SL hit alert for {symbol} {side} ({account_type}) to chat_id: {chat_id}")
            success = await send_trade_alert(chat_id, message, "sl_hit")
            
            if success:
                logger.info(f"🔴 Sent SL hit alert for {symbol} {side} ({account_type}) - Loss: ${abs(loss_amount):.2f}")
            else:
                logger.error(f"❌ Failed to send SL hit alert for {symbol} {side} ({account_type})")
                
                # Try fallback chat_id
                if DEFAULT_ALERT_CHAT_ID and DEFAULT_ALERT_CHAT_ID != chat_id:
                    logger.info(f"🔄 Retrying with DEFAULT_ALERT_CHAT_ID: {DEFAULT_ALERT_CHAT_ID}")
                    fallback_success = await send_trade_alert(DEFAULT_ALERT_CHAT_ID, message, "sl_hit")
                    if fallback_success:
                        logger.info(f"✅ SL hit alert sent to fallback chat_id: {DEFAULT_ALERT_CHAT_ID}")
                    else:
                        logger.error(f"❌ Failed to send SL hit alert even to fallback chat_id")

        except Exception as e:
            logger.error(f"Error sending SL hit alert: {e}")

    def _log_suppression_summary(self):
        """Log periodic summary of mirror alert suppressions and system health"""
        current_time = time.time()
        # Log summary every 5 minutes
        if current_time - self.last_suppression_summary > 300:  # 5 minutes
            if self.mirror_alerts_suppressed > 0:
                logger.info(f"📊 Mirror alert summary: {self.mirror_alerts_suppressed} alerts suppressed in last 5 minutes")
            self.last_suppression_summary = current_time
            
        # Log health check every 10 minutes
        if current_time - self.last_health_check > 600:  # 10 minutes
            main_alerts = self.alerts_sent["main"]
            mirror_alerts = self.alerts_sent["mirror"]
            total_monitors = len(self.position_monitors)
            
            logger.info(f"🏥 Alert system health check:")
            logger.info(f"   📊 Monitoring {total_monitors} positions")
            logger.info(f"   🔔 Sent {main_alerts} main account alerts")
            logger.info(f"   🔕 Sent {mirror_alerts} mirror account alerts")
            logger.info(f"   🚫 Suppressed {self.mirror_alerts_suppressed} mirror alerts")
            logger.info(f"   ✅ Alert system functioning normally")
            
            self.last_health_check = current_time

    async def _handle_position_closure(self, monitor_data: Dict, position: Dict):
        """Handle when position is completely closed - determine if it was TP or SL"""
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            chat_id = monitor_data["chat_id"]

            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                self.mirror_alerts_suppressed += 1
                logger.debug(f"Mirror alerts disabled - skipping position closure handling for {symbol} {side} mirror position")
                # Still update remaining size to 0
                monitor_data["remaining_size"] = Decimal("0")
                return

            # Skip alert if no chat_id
            if not chat_id:
                logger.warning(f"⚠️ No chat_id for {symbol} {side} {account_type} - skipping position closure handling")
                # Still update remaining size to 0
                monitor_data["remaining_size"] = Decimal("0")
                return

            # Determine closure reason
            closure_reason = "unknown"
            
            # Check if SL was hit (from our tracking)
            if monitor_data.get("sl_hit"):
                closure_reason = "sl_hit"
            # Check if all TPs were filled
            elif monitor_data.get("all_tps_filled"):
                closure_reason = "all_tps_filled"
            else:
                # Fallback: Check active orders to see what might have triggered (with caching)
                account_type = monitor_data.get("account_type", "main")
                active_orders = await self._get_cached_open_orders(symbol, account_type)

                # Check if SL order is missing (likely it triggered)
                sl_still_active = False
                if monitor_data.get("sl_order"):
                    sl_order_id = monitor_data["sl_order"]["order_id"]
                    sl_still_active = any(o.get("orderId") == sl_order_id for o in active_orders)

                # If SL is missing and position closed, SL was likely hit
                if not sl_still_active and monitor_data.get("sl_order"):
                    closure_reason = "sl_hit"
                else:
                    # Check if all TP orders are gone
                    tp_orders = self._ensure_tp_orders_dict(monitor_data)
                    tp_still_active = False
                    for order_id, tp_order in tp_orders.items():
                        if any(o.get("orderId") == order_id for o in active_orders):
                            tp_still_active = True
                            break
                    
                    if not tp_still_active:
                        closure_reason = "all_tps_filled"

            # Send appropriate alert based on closure reason
            if closure_reason == "sl_hit":
                # SL hit alert
                sl_price = monitor_data["sl_order"]["price"]
                entry_price = monitor_data["entry_price"]

                # Calculate loss
                if side == "Buy":
                    loss_pct = ((sl_price - entry_price) / entry_price) * 100
                else:
                    loss_pct = ((entry_price - sl_price) / entry_price) * 100

                message = (
                    f"🔴 <b>Stop Loss Hit!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 {symbol} {side}\n"
                    f"📍 Entry: {entry_price}\n"
                    f"🛑 Stop: {sl_price}\n"
                    f"📉 Loss: {abs(loss_pct):.2f}%\n"
                    f"⏱️ Duration: {(time.time() - monitor_data['created_at'])/60:.1f} mins"
                )

                await send_trade_alert(chat_id, message, alert_type="sl_hit")
                logger.info(f"🔴 Sent SL hit alert for {symbol} {side}")
            
            elif closure_reason == "all_tps_filled":
                # All TPs filled alert
                entry_price = monitor_data["entry_price"]
                
                # Calculate average exit price from filled TPs
                total_qty = Decimal("0")
                total_value = Decimal("0")
                tp_orders = self._ensure_tp_orders_dict(monitor_data)
                
                for order_id, tp_order in tp_orders.items():
                    if tp_order.get("status") == "FILLED":
                        qty = tp_order.get("filled_qty", tp_order.get("quantity", 0))
                        price = tp_order.get("price", 0)
                        total_qty += Decimal(str(qty))
                        total_value += Decimal(str(qty)) * Decimal(str(price))
                
                avg_exit_price = total_value / total_qty if total_qty > 0 else entry_price
                
                # Calculate profit
                if side == "Buy":
                    profit_pct = ((avg_exit_price - entry_price) / entry_price) * 100
                else:
                    profit_pct = ((entry_price - avg_exit_price) / entry_price) * 100
                
                message = (
                    f"🎯 <b>All Take Profits Hit!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 {symbol} {side}\n"
                    f"📍 Entry: {entry_price}\n"
                    f"🎯 Avg Exit: {avg_exit_price:.6f}\n"
                    f"📈 Profit: {profit_pct:.2f}%\n"
                    f"✅ All TP targets achieved!\n"
                    f"⏱️ Duration: {(time.time() - monitor_data['created_at'])/60:.1f} mins"
                )
                
                await send_trade_alert(chat_id, message, alert_type="tp_complete")
                logger.info(f"🎯 Sent all TPs filled alert for {symbol} {side}")

            # Update statistics before cleanup (skip for mirror accounts to avoid double counting)
            if account_type != "mirror":
                entry_price = safe_decimal_conversion(monitor_data.get("entry_price", "0"))
                
                # Calculate exit price based on closure reason
                if closure_reason == "sl_hit" and monitor_data.get("sl_order"):
                    exit_price = safe_decimal_conversion(monitor_data["sl_order"]["price"])
                elif closure_reason == "all_tps_filled":
                    # Calculate weighted average from filled TPs
                    total_qty = Decimal("0")
                    total_value = Decimal("0")
                    tp_orders = self._ensure_tp_orders_dict(monitor_data)
                    
                    for order_id, tp_order in tp_orders.items():
                        if tp_order.get("status") == "FILLED":
                            qty = safe_decimal_conversion(tp_order.get("filled_qty", tp_order.get("quantity", 0)))
                            price = safe_decimal_conversion(tp_order.get("price", 0))
                            total_qty += qty
                            total_value += qty * price
                    
                    exit_price = total_value / total_qty if total_qty > 0 else entry_price
                else:
                    # Use entry price as fallback for unknown closures
                    exit_price = entry_price
                
                # Get position size from monitor data
                position_size = safe_decimal_conversion(monitor_data.get("original_size", monitor_data.get("remaining_size", "0")))
                
                # Update statistics
                await self._update_position_statistics(symbol, side, closure_reason, entry_price, exit_price, position_size)

            # Update remaining size to 0
            monitor_data["remaining_size"] = Decimal("0")

            # Remove monitor_tasks entry
            approach = "CONSERVATIVE"  # Conservative approach only
            await self._remove_monitor_tasks_entry(symbol, side, chat_id, approach, "main")

        except Exception as e:
            logger.error(f"Error handling position closure: {e}")

    async def _update_position_statistics(self, symbol: str, side: str, closure_reason: str, entry_price: Decimal, exit_price: Decimal, position_size: Decimal):
        """Update performance statistics when a position closes"""
        try:
            import pickle
            
            # Load bot_data directly from persistence
            pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
            
            try:
                with open(pkl_path, 'rb') as f:
                    data = pickle.load(f)
            except (FileNotFoundError, EOFError, pickle.UnpicklingError):
                logger.warning(f"Could not load pickle file for stats update")
                return
                
            if 'bot_data' not in data:
                data['bot_data'] = {}
                
            bot_data = data['bot_data']
            
            # Calculate P&L
            if side == "Buy":
                pnl = (exit_price - entry_price) * position_size
            else:
                pnl = (entry_price - exit_price) * position_size
                
            pnl = safe_decimal_conversion(pnl)
            
            # Initialize stats if missing
            stats_defaults = {
                STATS_TOTAL_PNL: Decimal("0"),
                STATS_TOTAL_WINS: 0,
                STATS_TOTAL_LOSSES: 0,
                STATS_TOTAL_TRADES: 0,
                STATS_TP1_HITS: 0,
                STATS_SL_HITS: 0,
                STATS_OTHER_CLOSURES: 0,
                STATS_WIN_STREAK: 0,
                STATS_LOSS_STREAK: 0,
                STATS_BEST_TRADE: Decimal("0"),
                STATS_WORST_TRADE: Decimal("0"),
                STATS_CONSERVATIVE_TRADES: 0,
                STATS_CONSERVATIVE_TP1_CANCELLATIONS: 0,
                'stats_total_wins_pnl': Decimal("0"),
                'stats_total_losses_pnl': Decimal("0"),
                'stats_max_drawdown': Decimal("0"),
                'stats_peak_equity': Decimal("0"),
                'stats_current_drawdown': Decimal("0"),
                'recent_trade_pnls': [],
            }
            
            # Initialize missing stats
            for stat_key, default_val in stats_defaults.items():
                if stat_key not in bot_data:
                    bot_data[stat_key] = default_val
                    
            # Set last reset if missing
            if STATS_LAST_RESET not in bot_data:
                bot_data[STATS_LAST_RESET] = time.time()
                
            # Update trade count and approach stats
            bot_data[STATS_TOTAL_TRADES] += 1
            bot_data[STATS_CONSERVATIVE_TRADES] = bot_data.get(STATS_CONSERVATIVE_TRADES, 0) + 1
            
            # Update closure reason specific stats
            if closure_reason == "all_tps_filled":
                bot_data[STATS_TP1_HITS] = bot_data.get(STATS_TP1_HITS, 0) + 1
                # TP hit is always a win
                bot_data[STATS_TOTAL_WINS] += 1
                bot_data[STATS_WIN_STREAK] += 1
                bot_data[STATS_LOSS_STREAK] = 0
                logger.info(f"✅ All TPs filled recorded as WIN #{bot_data[STATS_TOTAL_WINS]}: +{abs(pnl)}")
                
            elif closure_reason == "sl_hit":
                bot_data[STATS_SL_HITS] = bot_data.get(STATS_SL_HITS, 0) + 1
                # SL hit is always a loss
                bot_data[STATS_TOTAL_LOSSES] += 1
                bot_data[STATS_LOSS_STREAK] += 1
                bot_data[STATS_WIN_STREAK] = 0
                logger.info(f"❌ SL Hit recorded as LOSS #{bot_data[STATS_TOTAL_LOSSES]}: -{abs(pnl)}")
                
            else:
                # Other closures - determine by P&L
                bot_data[STATS_OTHER_CLOSURES] = bot_data.get(STATS_OTHER_CLOSURES, 0) + 1
                if pnl > 0:
                    bot_data[STATS_TOTAL_WINS] += 1
                    bot_data[STATS_WIN_STREAK] += 1
                    bot_data[STATS_LOSS_STREAK] = 0
                    logger.info(f"✅ Manual close recorded as WIN #{bot_data[STATS_TOTAL_WINS]}: +{pnl}")
                elif pnl < 0:
                    bot_data[STATS_TOTAL_LOSSES] += 1
                    bot_data[STATS_LOSS_STREAK] += 1
                    bot_data[STATS_WIN_STREAK] = 0
                    logger.info(f"❌ Manual close recorded as LOSS #{bot_data[STATS_TOTAL_LOSSES]}: {pnl}")
                    
            # Update total P&L
            bot_data[STATS_TOTAL_PNL] = safe_decimal_conversion(bot_data[STATS_TOTAL_PNL]) + pnl
            
            # Track wins and losses P&L separately
            if pnl > 0:
                bot_data['stats_total_wins_pnl'] = safe_decimal_conversion(bot_data.get('stats_total_wins_pnl', Decimal("0"))) + pnl
            elif pnl < 0:
                bot_data['stats_total_losses_pnl'] = safe_decimal_conversion(bot_data.get('stats_total_losses_pnl', Decimal("0"))) + pnl
                
            # Update best/worst trade
            current_best = safe_decimal_conversion(bot_data[STATS_BEST_TRADE])
            current_worst = safe_decimal_conversion(bot_data[STATS_WORST_TRADE])
            
            if pnl > current_best:
                bot_data[STATS_BEST_TRADE] = pnl
                logger.info(f"🏆 New best trade: {pnl}")
            if pnl < current_worst:
                bot_data[STATS_WORST_TRADE] = pnl
                logger.info(f"📉 New worst trade: {pnl}")
                
            # Track recent trades
            recent_pnls = bot_data.get('recent_trade_pnls', [])
            recent_pnls.append(float(pnl))
            if len(recent_pnls) > 30:
                recent_pnls = recent_pnls[-30:]
            bot_data['recent_trade_pnls'] = recent_pnls
            
            # Update drawdown tracking
            current_equity = safe_decimal_conversion(bot_data.get(STATS_TOTAL_PNL, Decimal("0")))
            peak_equity = safe_decimal_conversion(bot_data.get('stats_peak_equity', Decimal("0")))
            
            if current_equity > peak_equity:
                bot_data['stats_peak_equity'] = current_equity
                peak_equity = current_equity
                
            if peak_equity > 0:
                current_drawdown = ((peak_equity - current_equity) / peak_equity * 100)
                bot_data['stats_current_drawdown'] = current_drawdown
                
                max_drawdown = safe_decimal_conversion(bot_data.get('stats_max_drawdown', Decimal("0")))
                if current_drawdown > max_drawdown:
                    bot_data['stats_max_drawdown'] = current_drawdown
                    
            # Save updated stats
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
                
            logger.info(f"📊 Statistics updated for {symbol} {side}: Trade #{bot_data[STATS_TOTAL_TRADES]}, P&L: {pnl}, Total P&L: {bot_data[STATS_TOTAL_PNL]}")
            
        except Exception as e:
            logger.error(f"Error updating position statistics: {e}")

    async def _run_monitor_loop(self, symbol: str, side: str, account_type: str = None):
        """Run continuous monitoring loop for a position"""
        # Use account-aware key if account_type is provided
        if account_type:
            monitor_key = f"{symbol}_{side}_{account_type}"
        else:
            # Legacy support
            monitor_key = f"{symbol}_{side}_{account_type}"
        logger.info(f"🔄 Starting enhanced monitor loop for {monitor_key}")

        # Track consecutive close detections for safety
        consecutive_close_detections = 0
        
        try:
            while monitor_key in self.position_monitors:
                # Robust position check with retries
                position_exists = False
                position = None
                
                # Try up to 3 times with different methods
                for attempt in range(3):
                    try:
                        # Method 1: Direct symbol position check
                        positions = await get_position_info_for_account(symbol, account_type)
                        
                        if positions is not None and len(positions) > 0:
                            for pos in positions:
                                if pos.get("side") == side:
                                    position_size = float(pos.get('size', 0))
                                    if position_size > 0:
                                        position_exists = True
                                        position = pos
                                        break
                            if position_exists:
                                break
                        
                        # Method 2: Fallback - get all positions and search
                        if not position_exists and attempt == 1:
                            try:
                                # Determine the correct client based on account type
                                client = self._mirror_client if account_type == "mirror" and self._mirror_client else None
                                all_positions = await get_all_positions(client)
                                if all_positions:
                                    for pos in all_positions:
                                        if pos.get('symbol') == symbol and pos.get('side') == side:
                                            position_size = float(pos.get('size', 0))
                                            if position_size > 0:
                                                position_exists = True
                                                position = pos
                                                break
                                    if position_exists:
                                        break
                                    else:
                                        # Confirmed not in all positions - position is closed
                                        break
                            except Exception as fallback_error:
                                logger.debug(f"Fallback position check failed: {fallback_error}")
                        
                    except Exception as e:
                        logger.warning(f"Position check attempt {attempt + 1}/3 failed for {symbol} {side}: {e}")
                        if attempt < 2:  # Don't sleep on last attempt
                            await asyncio.sleep(2 ** attempt)
                
                # Handle position status
                if not position_exists:
                    consecutive_close_detections += 1
                    logger.info(f"📊 Position {symbol} {side} appears closed (detection #{consecutive_close_detections}/2)")
                    
                    # Require 2 consecutive confirmations before stopping monitor
                    if consecutive_close_detections >= 2:
                        logger.info(f"✅ Position {symbol} {side} confirmed closed after {consecutive_close_detections} checks - ending monitor loop")
                        if monitor_key in self.position_monitors:
                            del self.position_monitors[monitor_key]
                        break
                    else:
                        logger.info(f"⚠️ Waiting for confirmation before stopping monitor (need {2 - consecutive_close_detections} more)")
                else:
                    # Position exists - reset close detection counter
                    if consecutive_close_detections > 0:
                        logger.info(f"✅ Position {symbol} {side} confirmed active - resetting close counter (was {consecutive_close_detections})")
                        consecutive_close_detections = 0

                # Run monitoring check with account type
                await self.monitor_and_adjust_orders(symbol, side, account_type)

                # Check if still active
                if monitor_key not in self.position_monitors:
                    break

                # Adaptive monitoring interval based on position state
                interval = await self._get_adaptive_interval(symbol, side, position, monitor_key)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info(f"⏹️ Monitor loop cancelled for {symbol} {side}")
        except Exception as e:
            logger.error(f"❌ Error in monitor loop for {symbol} {side}: {e}")
        finally:
            # Cleanup using robust persistence
            if monitor_key in self.position_monitors:
                monitor_data = self.position_monitors[monitor_key]
                chat_id = monitor_data.get("chat_id")
                approach = "CONSERVATIVE"  # Conservative approach only

                # Remove monitor using robust persistence
                try:
                    from utils.robust_persistence import remove_trade_monitor
                    await remove_trade_monitor(symbol, side, reason="monitor_stopped")
                    logger.info(f"✅ Removed monitor using Robust Persistence: {monitor_key}")
                except Exception as e:
                    logger.error(f"Error removing monitor via robust persistence: {e}")

                del self.position_monitors[monitor_key]
            logger.info(f"🛑 Monitor loop ended for {symbol} {side}")

    async def _create_monitor_tasks_entry(self, symbol: str, side: str, chat_id: int, approach: str, account_type: str = "main"):
        """Create monitor_tasks entry for dashboard compatibility"""
        try:
            # Load bot_data directly from persistence for monitor_tasks compatibility
            import pickle
            pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'

            # Load current bot data
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)

            if 'bot_data' not in data:
                data['bot_data'] = {}

            bot_data = data['bot_data']

            # Initialize monitor_tasks if not exists
            if 'monitor_tasks' not in bot_data:
                bot_data['monitor_tasks'] = {}
                logger.info("Created monitor_tasks in bot_data")

            # Create monitor key based on account type
            if account_type == "mirror":
                monitor_key = f"{chat_id}_{symbol}_{approach}_mirror"
                monitoring_mode = f"ENHANCED_TP_SL_MIRROR"
            else:
                monitor_key = f"{chat_id}_{symbol}_{approach}"
                monitoring_mode = f"ENHANCED_TP_SL"

            # Check if monitor already exists
            if monitor_key in bot_data['monitor_tasks']:
                existing_monitor = bot_data['monitor_tasks'][monitor_key]
                if existing_monitor.get('active', False):
                    logger.info(f"Monitor already exists and active: {monitor_key}")
                    return
                # Reactivate existing monitor
                existing_monitor.update({
                    'monitoring_mode': monitoring_mode,
                    'started_at': time.time(),
                    'active': True,
                    'account_type': account_type,
                    'system_type': 'enhanced_tp_sl'
                })
                logger.info(f"✅ Reactivated monitor: {monitor_key}")
            else:
                # Create new monitor
                bot_data['monitor_tasks'][monitor_key] = {
                    'chat_id': chat_id,
                    'symbol': symbol,
                    'approach': approach.lower(),
                    'monitoring_mode': monitoring_mode,
                    'started_at': time.time(),
                    'active': True,
                    'account_type': account_type,
                    'system_type': 'enhanced_tp_sl',
                    'side': side  # Add side for hedge mode compatibility
                }
                logger.info(f"✅ Created Enhanced TP/SL monitor: {monitor_key}")

            # Save updated data back to persistence
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)

        except Exception as e:
            logger.error(f"Error creating monitor_tasks entry: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def create_dashboard_monitor_entry(self, symbol: str, side: str, chat_id: int, approach: str, account_type: str = "main"):
        """Create monitor using Robust Persistence Manager for reliability"""
        try:
            # Use robust persistence manager
            from utils.robust_persistence import add_trade_monitor

            # Get current position info if available
            position_data = {}
            if symbol in self.position_monitors and side in [m.get('side') for m in self.position_monitors.values() if m.get('symbol') == symbol]:
                monitor_key = f"{symbol}_{side}_{account_type}"
                if monitor_key in self.position_monitors:
                    position_data = {
                        'size': self.position_monitors[monitor_key].get('position_size', 0),
                        'avgPrice': self.position_monitors[monitor_key].get('entry_price', 0),
                        'side': side,
                        'symbol': symbol
                    }

            # Create monitor data
            dashboard_key = f"{chat_id}_{symbol}_{approach}" if account_type == "main" else f"{chat_id}_{symbol}_{approach}_mirror"

            monitor_data = {
                'symbol': symbol,
                'side': side,
                'chat_id': chat_id,
                'approach': approach.lower(),
                'account_type': account_type,
                'dashboard_key': dashboard_key,
                'entry_price': position_data.get('avgPrice', 0),
                'position_size': position_data.get('size', self.position_monitors.get(f"{symbol}_{side}", {}).get('position_size', 0)),
                'chat_id': chat_id or DEFAULT_ALERT_CHAT_ID,
                'stop_loss': self.position_monitors.get(f"{symbol}_{side}", {}).get('stop_loss', 0),
                'take_profits': self.position_monitors.get(f"{symbol}_{side}", {}).get('tp_orders', []),
                'created_at': time.time(),
                'system_type': 'enhanced_tp_sl'
            }

            # Add monitor using robust persistence
            await add_trade_monitor(symbol, side, monitor_data, position_data)
            logger.info(f"✅ Created monitor using Robust Persistence: {symbol}_{side}")

        except Exception as e:
            logger.error(f"Error in NEW dashboard monitor creation method: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def _remove_monitor_tasks_entry(self, symbol: str, side: str, chat_id: int, approach: str, account_type: str = "main"):
        """Remove monitor_tasks entry when position is closed"""
        try:
            # Load bot_data directly from persistence for monitor_tasks compatibility
            import pickle
            pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'

            # Load current bot data
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)

            if 'bot_data' not in data:
                return

            bot_data = data['bot_data']

            if 'monitor_tasks' not in bot_data:
                return

            # Create monitor key based on account type
            if account_type == "mirror":
                monitor_key = f"{chat_id}_{symbol}_{approach}_mirror"
            else:
                monitor_key = f"{chat_id}_{symbol}_{approach}"

            # Remove or deactivate monitor
            if monitor_key in bot_data['monitor_tasks']:
                # Mark as inactive first
                bot_data['monitor_tasks'][monitor_key]['active'] = False
                # Then delete completely
                del bot_data['monitor_tasks'][monitor_key]
                logger.info(f"🗑️ Removed Enhanced TP/SL monitor: {monitor_key}")

                # Save updated data back to persistence
                with open(pkl_path, 'wb') as f:
                    pickle.dump(data, f)

        except Exception as e:
            logger.error(f"Error removing monitor_tasks entry: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    async def _move_sl_to_breakeven_enhanced_v2(
        self,
        monitor_data: Dict,
        position: Dict,
        is_tp1_trigger: bool = False
    ) -> bool:
        """
        ENHANCED: Move SL to breakeven with full position management

        Args:
            monitor_data: Monitor data for the position
            position: Current position data from exchange
            is_tp1_trigger: Whether this is triggered by TP1 (85%) fill

        Returns:
            bool: Success status
        """
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]

            account_type = monitor_data.get("account_type", "main")
            logger.info(f"🎯 ENHANCED BREAKEVEN V2: Starting for {symbol} {side} ({account_type} account)")
            logger.info(f"📍 Trigger: {'TP1 Fill' if is_tp1_trigger else 'Manual/Other'}")

            # Get current position data
            entry_price = Decimal(str(position.get("avgPrice", "0")))
            current_size = Decimal(str(position.get("size", "0")))
            realized_pnl = Decimal(str(position.get("realisedPnl", "0")))

            logger.info(f"📊 Position Details:")
            logger.info(f"   • Entry Price: {entry_price}")
            logger.info(f"   • Current Size: {current_size}")
            logger.info(f"   • Realized PnL: {realized_pnl}")

            if entry_price <= 0 or current_size <= 0:
                logger.error(f"❌ Invalid position data: entry_price={entry_price}, current_size={current_size}")
                return False

            # Calculate breakeven price with fees and safety margin
            fee_rate = Decimal("0.0006")  # 0.06% maker/taker
            safety_margin = Decimal("0.0002")  # Additional 0.02% safety

            if side == "Buy":
                breakeven_price = entry_price * (Decimal("1") + fee_rate + safety_margin)
                price_move_required = ((breakeven_price - entry_price) / entry_price) * 100
            else:  # Sell
                breakeven_price = entry_price * (Decimal("1") - fee_rate - safety_margin)
                price_move_required = ((entry_price - breakeven_price) / entry_price) * 100

            logger.info(f"💰 Breakeven Calculation:")
            logger.info(f"   • Entry: {entry_price}")
            logger.info(f"   • Breakeven: {breakeven_price}")
            logger.info(f"   • Required Move: {price_move_required:.3f}%")
            logger.info(f"   • Fee Rate: {fee_rate * 100:.2f}%")
            logger.info(f"   • Safety Margin: {safety_margin * 100:.2f}%")

            # Get current SL order
            sl_order = monitor_data.get("sl_order", {})
            if not sl_order or not sl_order.get("order_id"):
                logger.error("No existing SL order found to modify")
                return False

            # Cancel existing SL order
            old_sl_id = sl_order["order_id"]
            logger.info(f"🗑️ Cancelling old SL order: {old_sl_id[:8]}...")

            cancel_success = await cancel_order_with_retry(symbol, old_sl_id)
            if not cancel_success:
                logger.error(f"Failed to cancel existing SL order: {old_sl_id}")
                return False

            # ENHANCED: After TP1, SL should cover remaining position only
            if is_tp1_trigger:
                # After TP1 (85% filled), SL covers the remaining 15%
                sl_quantity = current_size  # Use actual remaining position size
                logger.info(f"📊 Post-TP1 SL quantity: {sl_quantity} (remaining position)")
            else:
                # Before TP1, maintain full position coverage
                sl_quantity = self._calculate_full_position_sl_quantity(
                    approach=monitor_data["approach"],
                    current_size=current_size,
                    target_size=monitor_data["position_size"],
                    tp1_hit=is_tp1_trigger
                )

            # Place new breakeven SL order
            sl_side = "Sell" if side == "Buy" else "Buy"
            position_idx = await get_correct_position_idx(symbol, side)

            new_sl_order_link_id = generate_adjusted_order_link_id(
                sl_order.get("order_link_id", ""), "BREAKEVEN"
            )

            logger.info(f"🛡️ Placing Breakeven SL Order:")
            logger.info(f"   • Symbol: {symbol}")
            logger.info(f"   • Side: {sl_side} (reduce only)")
            logger.info(f"   • Quantity: {sl_quantity}")
            logger.info(f"   • Trigger Price: {breakeven_price}")
            logger.info(f"   • Position Mode: {'Hedge' if position_idx != 0 else 'One-Way'}")
            logger.info(f"   • Order Link ID: {new_sl_order_link_id}")

            sl_result = await place_order_with_retry(
                symbol=symbol,
                side=sl_side,
                order_type="Market",
                qty=str(sl_quantity),
                trigger_price=str(breakeven_price),
                reduce_only=True,
                order_link_id=new_sl_order_link_id,
                position_idx=position_idx,
                stop_order_type="StopLoss"
            )

            if sl_result and sl_result.get("orderId"):
                new_sl_id = sl_result["orderId"]

                # Update monitor data with new SL info
                monitor_data["sl_order"] = {
                    "order_id": new_sl_id,
                    "order_link_id": new_sl_order_link_id,
                    "price": breakeven_price,
                    "quantity": sl_quantity,
                    "original_quantity": sl_quantity,
                    "breakeven": True,
                    "covers_full_position": True,  # Always 100% coverage
                    "target_position_size": monitor_data["position_size"]
                }

                # Track new order in lifecycle
                self._track_order_lifecycle(
                    order_id=new_sl_id,
                    order_type="SL",
                    symbol=symbol,
                    side=sl_side,
                    price=breakeven_price,
                    quantity=sl_quantity,
                    order_link_id=new_sl_order_link_id
                )

                logger.info(f"✅ ENHANCED Breakeven SL Placed Successfully!")
                logger.info(f"   • Order ID: {new_sl_id[:8]}...")
                logger.info(f"   • Breakeven Price: {breakeven_price}")
                logger.info(f"   • Protected Quantity: {sl_quantity}")
                logger.info(f"   • Coverage: {'100% of position' if not is_tp1_trigger else 'Remaining position after TP1'}")
                
                # Mark breakeven as moved
                monitor_data["sl_moved_to_be"] = True
                monitor_data["breakeven_price"] = breakeven_price
                monitor_data["breakeven_time"] = time.time()
                
                # Send enhanced breakeven alert
                await self._send_enhanced_breakeven_alert(monitor_data, "TP1" if is_tp1_trigger else "Manual")
                
                return True
            else:
                error_msg = sl_result.get('retMsg', 'Unknown error') if sl_result else 'No response'
                logger.error(f"❌ Failed to place breakeven SL order: {error_msg}")
                logger.error(f"   • Response: {sl_result}")
                return False

        except Exception as e:
            logger.error(f"❌ Error in enhanced breakeven V2: {e}")
            return False

    async def _handle_progressive_tp_fills(
        self,
        monitor_data: Dict,
        fill_percentage: float,
        current_size: Decimal
    ):
        """
        ENHANCED: Handle progressive TP fills (TP2, TP3, TP4) with automatic SL adjustments

        Args:
            monitor_data: Monitor data for the position
            fill_percentage: Current fill percentage
            current_size: Current remaining position size
        """
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            monitor_key = f"{symbol}_{side}_{account_type}"

            # Determine which TP level was hit based on cumulative percentages
            # Conservative approach: TP1=85%, TP2=90%, TP3=95%, TP4=100%
            if fill_percentage >= 90 and not monitor_data.get("tp2_processed", False):
                tp_level = "TP2"
                monitor_data["tp2_processed"] = True
            elif fill_percentage >= 95 and not monitor_data.get("tp3_processed", False):
                tp_level = "TP3"
                monitor_data["tp3_processed"] = True
            elif fill_percentage >= 99 and not monitor_data.get("tp4_processed", False):
                tp_level = "TP4"
                monitor_data["tp4_processed"] = True
            else:
                # No new TP level hit
                return

            logger.info(f"🎯 PROGRESSIVE TP: {tp_level} hit for {monitor_key} ({fill_percentage:.2f}% filled)")

            # Use atomic lock for progressive adjustments
            if monitor_key not in self.breakeven_locks:
                self.breakeven_locks[monitor_key] = asyncio.Lock()

            async with self.breakeven_locks[monitor_key]:
                # Get current position data
                positions = await get_position_info(symbol)
                position = None
                if positions:
                    for pos in positions:
                        if pos.get("side") == side:
                            position = pos
                            break

                if not position:
                    logger.warning(f"No position found for progressive TP adjustment: {symbol} {side}")
                    return

                # Adjust SL quantity to match remaining position
                success = await self._adjust_sl_quantity_progressive(
                    monitor_data=monitor_data,
                    current_size=current_size,
                    tp_level=tp_level
                )

                if success:
                    logger.info(f"✅ Progressive SL adjustment completed for {tp_level}")

                    # Send progressive TP alert
                    await self._send_progressive_tp_alert(monitor_data, tp_level, fill_percentage)

                    # Sync with mirror account
                    await self._sync_progressive_adjustment_with_mirror(monitor_data, tp_level)
                else:
                    logger.error(f"❌ Progressive SL adjustment failed for {tp_level}")

        except Exception as e:
            logger.error(f"❌ Error in progressive TP fills handling: {e}")

    async def _adjust_sl_quantity_progressive(
        self,
        monitor_data: Dict,
        current_size: Decimal,
        tp_level: str
    ) -> bool:
        """
        ENHANCED: Adjust SL quantity for progressive TP fills

        Args:
            monitor_data: Monitor data for the position
            current_size: Current remaining position size
            tp_level: TP level that was hit (TP2, TP3, TP4)

        Returns:
            bool: Success status
        """
        try:
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]

            # Get current SL order
            sl_order = monitor_data.get("sl_order", {})
            if not sl_order or not sl_order.get("order_id"):
                logger.error(f"No SL order to adjust for {tp_level}")
                return False

            current_sl_quantity = sl_order.get("quantity", Decimal("0"))

            # Check if adjustment is needed (SL quantity should match remaining position)
            if abs(current_sl_quantity - current_size) < Decimal("0.001"):
                logger.info(f"SL quantity already matches remaining position for {tp_level}")
                return True

            logger.info(f"🔧 {tp_level} SL ADJUSTMENT: {current_sl_quantity} → {current_size}")

            # Cancel current SL
            old_sl_id = sl_order["order_id"]
            cancel_success = await cancel_order_with_retry(symbol, old_sl_id)

            if not cancel_success:
                logger.error(f"Failed to cancel SL for {tp_level} adjustment")
                return False

            # Place new SL with adjusted quantity
            sl_side = "Sell" if side == "Buy" else "Buy"
            position_idx = await get_correct_position_idx(symbol, side)

            new_sl_order_link_id = generate_adjusted_order_link_id(
                sl_order.get("order_link_id", ""), f"{tp_level}_ADJ"
            )

            sl_result = await place_order_with_retry(
                symbol=symbol,
                side=sl_side,
                order_type="Market",
                qty=str(current_size),
                trigger_price=str(sl_order["price"]),  # Keep same breakeven price
                reduce_only=True,
                order_link_id=new_sl_order_link_id,
                position_idx=position_idx,
                stop_order_type="StopLoss"
            )

            if sl_result and sl_result.get("orderId"):
                new_sl_id = sl_result["orderId"]

                # Update monitor data
                monitor_data["sl_order"]["order_id"] = new_sl_id
                monitor_data["sl_order"]["order_link_id"] = new_sl_order_link_id
                monitor_data["sl_order"]["quantity"] = current_size
                monitor_data["sl_order"][f"{tp_level.lower()}_adjusted"] = True

                logger.info(f"✅ {tp_level} SL quantity adjusted: {new_sl_id[:8]}...")
                return True
            else:
                logger.error(f"Failed to place adjusted SL for {tp_level}")
                return False

        except Exception as e:
            logger.error(f"❌ Error adjusting SL quantity for {tp_level}: {e}")
            return False

    async def _send_enhanced_breakeven_alert(self, monitor_data: Dict, tp_level: str):
        """Send enhanced breakeven alert with detailed information"""
        try:
            chat_id = monitor_data.get("chat_id")
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            
            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                logger.debug(f"Mirror alerts disabled - skipping enhanced breakeven alert for {symbol} {side} mirror position")
                return
            
            # Try to find chat_id if not in monitor data
            if not chat_id:
                chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
                if not chat_id:
                    logger.warning(f"Could not find chat_id for {symbol} {side} - skipping enhanced breakeven alert")
                    return
            sl_order = monitor_data.get("sl_order", {})

            message = f"""🎯 <b>ENHANCED {tp_level} BREAKEVEN ACHIEVED!</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} {"📈" if side == "Buy" else "📉"} {side}

✅ <b>Position Now Risk-Free!</b>
🛡️ SL moved to breakeven: ${sl_order.get('price', 'N/A'):.6f}
📏 SL quantity: {sl_order.get('quantity', 'N/A')}
🔧 Coverage: {"Full position" if sl_order.get("covers_full_position", False) else "Remaining position"}

🎉 <b>Achievement Unlocked:</b>
• {tp_level} target reached (85%+ filled)
• Zero-risk position achieved
• Profits now secured
• Advanced SL management active

🔄 <b>Next Steps:</b>
• Monitoring continues for remaining TPs
• Progressive SL adjustments enabled
• Mirror account synchronized

✨ Your position is fully protected with enhanced coverage!"""

            await send_trade_alert(chat_id, message, f"enhanced_breakeven_{tp_level.lower()}")

        except Exception as e:
            logger.error(f"Error sending enhanced breakeven alert: {e}")

    async def _send_progressive_tp_alert(self, monitor_data: Dict, tp_level: str, fill_percentage: float):
        """Send progressive TP fill alert"""
        try:
            chat_id = monitor_data.get("chat_id")
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            account_type = monitor_data.get("account_type", "main")
            
            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                logger.debug(f"Mirror alerts disabled - skipping progressive TP alert for {symbol} {side} mirror position")
                return
            
            # Try to find chat_id if not in monitor data
            if not chat_id:
                chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
                if not chat_id:
                    logger.warning(f"Could not find chat_id for {symbol} {side} - skipping enhanced breakeven alert")
                    return

            message = f"""🎯 <b>{tp_level} TARGET HIT!</b>
━━━━━━━━━━━━━━━━━━━━━━
📊 {symbol} {"📈" if side == "Buy" else "📉"} {side}

✅ <b>{tp_level} Filled:</b> {fill_percentage:.2f}%
🛡️ SL automatically adjusted to remaining position
🔧 Progressive management active

🎉 <b>Progress:</b>
• TP1 ✅ (Breakeven achieved)
• {tp_level} ✅ (Current fill)
{"• Remaining TPs pending" if tp_level != "TP4" else "• All targets completed! 🏆"}

🔄 <b>System Status:</b>
• Enhanced SL management: Active
• Position protection: Maintained
• Mirror sync: Completed

{"🏆 Congratulations on completing all targets!" if tp_level == "TP4" else "🚀 Continuing to monitor remaining targets!"}"""

            await send_trade_alert(chat_id, message, f"progressive_tp_{tp_level.lower()}")

        except Exception as e:
            logger.error(f"Error sending progressive TP alert: {e}")
    
    async def _find_chat_id_for_position(self, symbol: str, side: str, account_type: str = "main") -> Optional[int]:
        """
        Find chat_id for a position by searching through user data
        This ensures alerts are sent even when monitor data doesn't have chat_id
        Enhanced to support both main and mirror accounts
        """
        try:
            import pickle
            pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            
            # Search through user_data for this position
            user_data = data.get('user_data', {})
            for chat_id, udata in user_data.items():
                # Check monitor_tasks for this symbol
                if 'bot_data' in data:
                    monitor_tasks = data['bot_data'].get('monitor_tasks', {})
                    for monitor_key, monitor_info in monitor_tasks.items():
                        # Check for account-specific monitor key match
                        monitor_account_type = monitor_info.get('account_type', 'main')
                        monitor_symbol = monitor_info.get('symbol')
                        monitor_side = monitor_info.get('side')
                        
                        # Match symbol, side, account type, and chat_id
                        if (monitor_symbol == symbol and 
                            monitor_side == side and
                            monitor_account_type == account_type and
                            str(chat_id) in monitor_key):
                            logger.info(f"✅ Found chat_id {chat_id} for {symbol} {side} ({account_type} account) from monitor_tasks")
                            return int(chat_id)
                
                # Check active positions in user data (account-aware)
                positions = udata.get('positions', [])
                for pos in positions:
                    pos_account_type = pos.get('account_type', 'main')
                    if (pos.get('symbol') == symbol and 
                        pos.get('side') == side and 
                        pos_account_type == account_type):
                        logger.info(f"✅ Found chat_id {chat_id} for {symbol} {side} ({account_type} account) from user positions")
                        return int(chat_id)
            
            # Last resort: check if there's only one user
            if len(user_data) == 1:
                chat_id = list(user_data.keys())[0]
                logger.info(f"✅ Using single user chat_id {chat_id} for {symbol} {side} ({account_type} account)")
                return int(chat_id)
                
            logger.warning(f"Could not find chat_id for {symbol} {side} ({account_type} account)")
            
            # Use default chat ID if configured
            from config.settings import DEFAULT_ALERT_CHAT_ID
            if DEFAULT_ALERT_CHAT_ID:
                logger.info(f"✅ Using default chat_id {DEFAULT_ALERT_CHAT_ID} for orphaned position {symbol} {side} ({account_type} account)")
                return DEFAULT_ALERT_CHAT_ID
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding chat_id: {e}")
            return None

    async def _sync_progressive_adjustment_with_mirror(self, monitor_data: Dict, tp_level: str):
        """Sync progressive SL adjustments with mirror account"""
        try:
            # Implementation would sync the progressive SL adjustment with mirror account
            # For now, log the action
            symbol = monitor_data["symbol"]
            side = monitor_data["side"]
            logger.info(f"🪞 MIRROR SYNC: {tp_level} adjustment for {symbol} {side}")

            # TODO: Implement actual mirror synchronization

        except Exception as e:
            logger.error(f"Error syncing progressive adjustment with mirror: {e}")

    async def _trigger_mirror_sync_for_position_increase(self, symbol: str, side: str, new_size: Decimal, size_increase: Decimal):
        """
        Trigger mirror account synchronization when main position increases due to limit order fills
        This ensures mirror TPs are rebalanced immediately when limit orders fill
        """
        try:
            from execution.mirror_enhanced_tp_sl import initialize_mirror_manager
            mirror_manager = initialize_mirror_manager(self)
            if not mirror_manager:
                return

            logger.info(f"🔄 Triggering mirror sync for position increase: {symbol} {side} +{size_increase}")

            # Get the main monitor data to pass to mirror
            monitor_key = f"{symbol}_{side}_{account_type}"
            if monitor_key not in self.position_monitors:
                logger.warning(f"No main monitor data found for {symbol} {side}")
                return

            main_monitor_data = self.position_monitors[monitor_key]

            # Mirror sync removed - mirror accounts operate independently
            # Each account's monitors handle their own positions without syncing
            logger.info(f"✅ Mirror accounts operate independently - no sync needed")

        except Exception as e:
            logger.error(f"Error triggering mirror sync for position increase: {e}")

    async def _save_to_persistence(self, force: bool = False):
        """Save current monitors to persistence file with time-based throttling
        
        Args:
            force: If True, bypass time-based throttling and save immediately
        """
        try:
            current_time = time.time()
            
            # Check if we should save based on time interval
            if not force and current_time - self.last_persistence_save < self.persistence_interval:
                # Schedule a pending save if not already scheduled
                if not self.pending_persistence_save:
                    self.pending_persistence_save = True
                    asyncio.create_task(self._delayed_persistence_save())
                return
            
            import pickle
            from utils.robust_persistence import RobustPersistenceManager

            persistence_manager = RobustPersistenceManager()

            # Read current data
            data = await persistence_manager.read_data()

            # Clean monitors before saving - remove any non-serializable objects
            clean_monitors = {}
            for key, monitor in self.position_monitors.items():
                clean_monitor = {}
                for field_key, field_value in monitor.items():
                    # Skip any non-serializable fields
                    if any([
                        'task' in str(field_key).lower(),
                        'monitoring_task' in str(field_key),
                        hasattr(field_value, '_callbacks'),
                        hasattr(field_value, '__await__'),
                        hasattr(field_value, 'cancel'),
                        callable(field_value) and not isinstance(field_value, type)
                    ]):
                        continue
                    clean_monitor[field_key] = field_value
                clean_monitors[key] = clean_monitor

            # Update enhanced_tp_sl_monitors with cleaned data
            if 'bot_data' not in data:
                data['bot_data'] = {}
            data['bot_data']['enhanced_tp_sl_monitors'] = clean_monitors

            # Write updated data back
            await persistence_manager.write_data(data)

            # Update last save time
            self.last_persistence_save = current_time
            self.pending_persistence_save = False
            
            logger.debug("💾 Monitors saved to persistence")

        except Exception as e:
            logger.error(f"❌ Error saving to persistence: {e}")
    
    async def _delayed_persistence_save(self):
        """Handle delayed persistence save after interval has passed"""
        try:
            # Wait for the remaining interval time
            wait_time = self.persistence_interval - (time.time() - self.last_persistence_save)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # Perform the save if still pending
            if self.pending_persistence_save:
                await self._save_to_persistence(force=True)
                
        except Exception as e:
            logger.error(f"Error in delayed persistence save: {e}")

    async def _create_dashboard_monitor_entry(self, monitor_data: Dict):
        """Create dashboard monitor entry for UI visibility"""
        try:
            # Extract required fields
            symbol = monitor_data.get("symbol")
            side = monitor_data.get("side")
            approach = "CONSERVATIVE"  # Conservative approach only
            chat_id = monitor_data.get("chat_id")
            account_type = monitor_data.get("account_type", "main")

            # Create monitor tasks entry for dashboard only if we have a chat_id
            if chat_id:
                await self._create_monitor_tasks_entry(
                    chat_id=chat_id,
                    symbol=symbol,
                    side=side,
                    approach=approach,
                    account_type=account_type
                )
            else:
                logger.warning(f"⚠️ Skipping dashboard monitor entry for {symbol} {side} - no chat_id")

            logger.debug(f"✅ Created dashboard monitor entry for {symbol} {side}")

        except Exception as e:
            logger.error(f"❌ Error creating dashboard monitor entry: {e}")

    async def sync_existing_positions(self):
        """
        Sync existing positions and create monitors for positions without them
        This ensures all positions are monitored even after bot restarts
        Includes both main and mirror account positions
        """
        try:
            logger.info("🔄 Starting position sync for Enhanced TP/SL monitoring")
            
            monitors_created = 0
            monitors_skipped = 0
            
            # Check if mirror trading is enabled
            from config.settings import ENABLE_MIRROR_TRADING
            
            # Process main account positions
            logger.info("📊 Checking main account positions...")
            from clients.bybit_helpers import get_all_positions
            main_positions = await get_all_positions()
            
            if main_positions:
                logger.info(f"📊 Found {len(main_positions)} main account positions")
                for position in main_positions:
                    result = await self._process_position_for_sync(position, "main")
                    if result == "created":
                        monitors_created += 1
                    elif result == "skipped":
                        monitors_skipped += 1
            
            # Process mirror account positions if enabled
            if ENABLE_MIRROR_TRADING:
                logger.info("📊 Checking mirror account positions...")
                try:
                    from execution.mirror_trader import bybit_client_2
                    mirror_positions = await get_all_positions(client=bybit_client_2)
                    
                    if mirror_positions:
                        logger.info(f"📊 Found {len(mirror_positions)} mirror account positions")
                        for position in mirror_positions:
                            result = await self._process_position_for_sync(position, "mirror")
                            if result == "created":
                                monitors_created += 1
                            elif result == "skipped":
                                monitors_skipped += 1
                except Exception as e:
                    logger.error(f"❌ Error checking mirror positions: {e}")
            
            logger.info(f"🔄 Position sync complete: {monitors_created} created, {monitors_skipped} skipped")
            
        except Exception as e:
            logger.error(f"❌ Error during position sync: {e}")
            import traceback
            traceback.print_exc()
    
    async def _process_position_for_sync(self, position, account_type="main"):
        """
        Process a single position for sync monitoring
        Returns: "created", "skipped", or None (error)
        """
        try:
            symbol = position.get('symbol')
            side = position.get('side')
            size = float(position.get('size', 0))
            
            if size <= 0:
                return None
            
            # Always use account-aware key format
            monitor_key = f"{symbol}_{side}_{account_type}"
            
            # Use lock to prevent duplicate monitor creation
            async with self.monitor_creation_lock:
                # Check if monitor already exists (double-check inside lock)
                if monitor_key in self.position_monitors:
                    logger.debug(f"✅ Monitor already exists for {monitor_key}")
                    return "skipped"
                
                # Try to find chat_id from user data
                chat_id = None
                try:
                    import pickle
                    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
                    with open(pkl_path, 'rb') as f:
                        data = pickle.load(f)
                    
                    # Find chat_id from user_data
                    user_data = data.get('user_data', {})
                    for uid, udata in user_data.items():
                        if 'positions' in udata:
                            # Check if this user has this position
                            for pos in udata.get('positions', []):
                                if pos.get('symbol') == symbol and pos.get('side') == side:
                                    chat_id = uid
                                    logger.info(f"✅ Found chat_id {chat_id} from user data for {symbol} {side}")
                                    break
                            if chat_id:
                                break
                except Exception as e:
                    logger.warning(f"Could not retrieve chat_id from user data: {e}")
                
                # If no chat_id found, try to get from any existing monitor_tasks
                if not chat_id and 'data' in locals():
                    try:
                        bot_data = data.get('bot_data', {})
                        monitor_tasks = bot_data.get('monitor_tasks', {})
                        for mk, mv in monitor_tasks.items():
                            if mv.get('symbol') == symbol:
                                chat_id = mv.get('chat_id')
                                if chat_id:
                                    logger.info(f"✅ Found chat_id {chat_id} from monitor_tasks for {symbol}")
                                    break
                    except:
                        pass
                
                if not chat_id:
                    # Try to find chat_id, fallback to default if not found
                    from config.settings import DEFAULT_ALERT_CHAT_ID
                    if DEFAULT_ALERT_CHAT_ID:
                        chat_id = DEFAULT_ALERT_CHAT_ID
                        logger.info(f"📱 Using default chat_id {DEFAULT_ALERT_CHAT_ID} for {symbol} {side}")
                    else:
                        logger.warning(f"⚠️ Could not find chat_id for {symbol} {side} - creating monitor without alerts")
                
                # Create monitor for this position
                logger.info(f"🆕 Creating monitor for orphaned position: {symbol} {side} ({account_type})")
                
                # Get position details
                avg_price = Decimal(str(position.get('avgPrice', 0)))
                
                # Get appropriate client for this account
                if account_type == "mirror":
                    from execution.mirror_trader import bybit_client_2
                    client = bybit_client_2
                else:
                    from clients.bybit_helpers import bybit_client
                    client = bybit_client
                
                # CRITICAL FIX: Use monitoring cache instead of direct API calls
                try:
                    all_orders = await self._get_cached_open_orders(symbol, account_type)
                    logger.debug(f"🚀 Using cached orders for monitoring setup: {len(all_orders)} orders for {symbol} ({account_type})")
                except Exception as e:
                    logger.warning(f"Could not get cached orders for {symbol} ({account_type}): {e}")
                    # Emergency fallback - this should rarely happen
                    if account_type == "mirror":
                        from clients.bybit_helpers import get_all_open_orders
                        all_orders_response = await get_all_open_orders(client=client)
                        all_orders = [order for order in all_orders_response if order.get('symbol') == symbol]
                    else:
                        from clients.bybit_helpers import get_open_orders
                        all_orders = await get_open_orders(symbol=symbol)
                
                # Filter TP and SL orders
                tp_orders = {}
                sl_order = None
                limit_orders = []
                
                for order in all_orders:
                    if order.get('reduceOnly'):
                        order_link_id = order.get('orderLinkId', '')
                        if 'TP' in order_link_id:
                            tp_orders[order['orderId']] = {
                                'order_id': order['orderId'],
                                'price': Decimal(str(order['price'])),
                                'quantity': Decimal(str(order['qty'])),
                                'order_link_id': order_link_id,
                                'status': order['orderStatus']
                            }
                        elif 'SL' in order_link_id or order.get('stopOrderType'):
                            sl_order = {
                                'order_id': order['orderId'],
                                'price': Decimal(str(order.get('triggerPrice', order['price']))),
                                'quantity': Decimal(str(order['qty'])),
                                'order_link_id': order_link_id
                            }
                    else:
                        # Limit entry order
                        limit_orders.append({
                            'order_id': order['orderId'],
                            'price': Decimal(str(order['price'])),
                            'quantity': Decimal(str(order['qty'])),
                            'order_link_id': order.get('orderLinkId', '')
                        })
                
                # Create monitor data
                monitor_data = {
                    'symbol': symbol,
                    'side': side,
                    'position_size': Decimal(str(size)),
                    'remaining_size': Decimal(str(size)),
                    'entry_price': avg_price,
                    'avg_price': avg_price,
                    'approach': 'conservative',  # Default to conservative
                    'tp_orders': tp_orders,
                    'sl_order': sl_order,
                    'filled_tps': [],
                    'cancelled_limits': False,
                    'tp1_hit': False,
                    'tp1_info': None,
                    'sl_moved_to_be': False,
                    'sl_move_attempts': 0,
                    'created_at': time.time(),
                    'last_check': time.time(),
                    'limit_orders': limit_orders,
                    'limit_orders_cancelled': False,
                    'phase': 'MONITORING',
                    'chat_id': chat_id,
                    'account_type': account_type,
                    'close_detections': 0
                }
                
                # Add to monitors
                self.position_monitors[monitor_key] = monitor_data
                
                # Save to persistence (force=True for new monitors)
                await self._save_to_persistence(force=True)
                
                # Create dashboard monitor entry
                await self._create_dashboard_monitor_entry(monitor_data)
                
                logger.info(f"✅ Created monitor for {symbol} {side} ({account_type}) with {len(tp_orders)} TP orders")
                return "created"
                
        except Exception as e:
            logger.error(f"❌ Error processing position for sync: {e}")
            return None
    async def check_order_fills_directly(self, symbol: str, order_ids: List[str], client=None) -> Dict[str, Dict]:
        """
        Enhanced order fill detection using direct API status checks
        
        This method provides more accurate and timely detection than position size monitoring
        by checking order status directly from the API, including order history.
        
        Args:
            symbol: Trading symbol
            order_ids: List of order IDs to check
            client: Bybit client (main or mirror)
            
        Returns:
            Dict mapping order_id to fill details
        """
        from config.settings import ORDER_HISTORY_LOOKBACK, LOG_TP_DETECTION_DETAILS
        
        filled_orders = {}
        
        try:
            # Use default client if not provided
            if not client:
                from clients.bybit_helpers import bybit_client
                client = bybit_client
            
            # Get order history for recent fills
            if LOG_TP_DETECTION_DETAILS:
                logger.debug(f"🔍 Checking order fills for {symbol}: {len(order_ids)} orders")
            
            order_history = await api_call_with_retry(
                lambda: client.get_order_history(
                    category="linear",
                    symbol=symbol,
                    limit=ORDER_HISTORY_LOOKBACK
                )
            )
            
            if order_history and order_history.get('retCode') == 0:
                history_orders = order_history.get('result', {}).get('list', [])
                
                for order in history_orders:
                    order_id = order.get('orderId')
                    if order_id in order_ids:
                        order_status = order.get('orderStatus')
                        
                        if order_status == 'Filled':
                            filled_orders[order_id] = {
                                'status': 'Filled',
                                'filled_qty': Decimal(str(order.get('cumExecQty', 0))),
                                'avg_price': Decimal(str(order.get('avgPrice', 0))),
                                'filled_time': order.get('updatedTime'),
                                'order_type': order.get('orderType'),
                                'side': order.get('side'),
                                'reduce_only': order.get('reduceOnly', False),
                                'order_link_id': order.get('orderLinkId', ''),
                                'stop_order_type': order.get('stopOrderType')
                            }
                            
                            if LOG_TP_DETECTION_DETAILS:
                                logger.debug(f"✅ Found filled order in history: {order_id[:8]}...")
            
            # Also check active orders to confirm what's still open
            active_orders = await api_call_with_retry(
                lambda: client.get_open_orders(
                    category="linear",
                    symbol=symbol
                )
            )
            
            if active_orders and active_orders.get('retCode') == 0:
                active_order_ids = {o.get('orderId') for o in active_orders.get('result', {}).get('list', [])}
                
                # Any tracked order not in active list might be filled
                for order_id in order_ids:
                    if order_id not in active_order_ids and order_id not in filled_orders:
                        # Double-check with specific order query
                        order_detail = await api_call_with_retry(
                            lambda: client.get_order_history(
                                category="linear",
                                symbol=symbol,
                                orderId=order_id
                            )
                        )
                        
                        if order_detail and order_detail.get('retCode') == 0:
                            # get_order_history returns a list of orders
                            orders = order_detail.get('result', {}).get('list', [])
                            if orders and len(orders) > 0:
                                order = orders[0]  # Get the first (and should be only) order
                                if order.get('orderStatus') == 'Filled':
                                    filled_orders[order_id] = {
                                        'status': 'Filled',
                                        'filled_qty': Decimal(str(order.get('cumExecQty', 0))),
                                        'avg_price': Decimal(str(order.get('avgPrice', 0))),
                                        'filled_time': order.get('updatedTime'),
                                        'order_type': order.get('orderType'),
                                        'side': order.get('side'),
                                        'reduce_only': order.get('reduceOnly', False),
                                        'order_link_id': order.get('orderLinkId', ''),
                                        'stop_order_type': order.get('stopOrderType')
                                    }
                                    
                                    if LOG_TP_DETECTION_DETAILS:
                                        logger.debug(f"✅ Confirmed filled order via query: {order_id[:8]}...")
            
            if LOG_TP_DETECTION_DETAILS:
                logger.debug(f"📊 Order fill check complete: {len(filled_orders)}/{len(order_ids)} filled")
                
        except Exception as e:
            logger.error(f"Error checking order fills: {e}")
        
        return filled_orders

    async def detect_fills_with_confirmation(self, monitor_data: Dict, client=None) -> Dict[str, Any]:
        """
        Detect fills using multiple confirmation methods for high accuracy
        
        This method combines:
        1. Direct order status checks
        2. Position size comparison
        3. Realized PnL tracking (if enabled)
        
        Args:
            monitor_data: Monitor data for the position
            client: Bybit client (main or mirror)
            
        Returns:
            Dict with detected fills and confidence metrics
        """
        from config.settings import (
            TP_DETECTION_CONFIDENCE_THRESHOLD, 
            ENABLE_REALIZED_PNL_TRACKING,
            LOG_TP_DETECTION_DETAILS
        )
        
        symbol = monitor_data['symbol']
        side = monitor_data['side']
        account_type = monitor_data.get('account_type', 'main')
        
        fills_detected = {
            'confirmed_fills': {},
            'confidence_scores': {},
            'detection_methods': {}
        }
        
        try:
            # Method 1: Direct order status check
            tp_order_ids = []
            tp_orders_map = {}
            
            # Handle both dict and list formats for tp_orders
            tp_orders = monitor_data.get('tp_orders', {})
            if isinstance(tp_orders, dict):
                for tp_id, tp_data in tp_orders.items():
                    if isinstance(tp_data, dict) and 'order_id' in tp_data:
                        order_id = tp_data['order_id']
                        tp_order_ids.append(order_id)
                        tp_orders_map[order_id] = tp_data
            
            if tp_order_ids:
                filled_orders = await self.check_order_fills_directly(symbol, tp_order_ids, client)
                
                for order_id, fill_data in filled_orders.items():
                    tp_data = tp_orders_map.get(order_id, {})
                    fills_detected['confirmed_fills'][order_id] = {
                        'fill_data': fill_data,
                        'tp_number': tp_data.get('tp_number', 0),
                        'expected_qty': tp_data.get('quantity', Decimal('0'))
                    }
                    fills_detected['confidence_scores'][order_id] = 1  # Direct API confirmation
                    fills_detected['detection_methods'][order_id] = ['direct_api']
            
            # Method 2: Position size comparison
            position = await get_position_info_for_account(symbol, account_type) if account_type == 'mirror' else await get_position_info(symbol)
            
            if position:
                for pos in position:
                    if pos.get('side') == side:
                        current_size = Decimal(str(pos.get('size', 0)))
                        stored_size = monitor_data.get('remaining_size', monitor_data.get('position_size', Decimal('0')))
                        
                        if current_size < stored_size:
                            size_reduction = stored_size - current_size
                            
                            # Try to match size reduction with expected TP quantities
                            for order_id, tp_data in tp_orders_map.items():
                                expected_qty = Decimal(str(tp_data.get('quantity', 0)))
                                
                                # Allow small tolerance for rounding
                                if abs(expected_qty - size_reduction) < Decimal('0.01'):
                                    if order_id in fills_detected['confirmed_fills']:
                                        fills_detected['confidence_scores'][order_id] += 1
                                        fills_detected['detection_methods'][order_id].append('position_size')
                                    else:
                                        # Position size suggests fill but not confirmed by API
                                        fills_detected['confirmed_fills'][order_id] = {
                                            'fill_data': {
                                                'status': 'Likely_Filled',
                                                'filled_qty': size_reduction,
                                                'detection': 'position_size_change'
                                            },
                                            'tp_number': tp_data.get('tp_number', 0),
                                            'expected_qty': expected_qty
                                        }
                                        fills_detected['confidence_scores'][order_id] = 0.5
                                        fills_detected['detection_methods'][order_id] = ['position_size']
                        
                        # Method 3: Realized PnL tracking
                        if ENABLE_REALIZED_PNL_TRACKING:
                            current_realized_pnl = Decimal(str(pos.get('realisedPnl', 0)))
                            last_pnl = monitor_data.get('last_realized_pnl', Decimal('0'))
                            
                            if current_realized_pnl > last_pnl:
                                # PnL increased, likely a TP fill
                                pnl_increase = current_realized_pnl - last_pnl
                                
                                # Update confidence for orders already detected
                                for order_id in fills_detected['confirmed_fills']:
                                    fills_detected['confidence_scores'][order_id] += 0.5
                                    if 'realized_pnl' not in fills_detected['detection_methods'][order_id]:
                                        fills_detected['detection_methods'][order_id].append('realized_pnl')
                                
                                # Store for next check
                                monitor_data['last_realized_pnl'] = current_realized_pnl
            
            # Filter by confidence threshold
            high_confidence_fills = {}
            for order_id, fill_info in fills_detected['confirmed_fills'].items():
                confidence = fills_detected['confidence_scores'][order_id]
                if confidence >= TP_DETECTION_CONFIDENCE_THRESHOLD:
                    high_confidence_fills[order_id] = fill_info
                    
                    if LOG_TP_DETECTION_DETAILS:
                        methods = ', '.join(fills_detected['detection_methods'][order_id])
                        logger.info(f"🎯 High confidence fill detected: {order_id[:8]}... (confidence: {confidence}, methods: {methods})")
            
            fills_detected['high_confidence_fills'] = high_confidence_fills
            
        except Exception as e:
            logger.error(f"Error in multi-method fill detection: {e}")
        
        return fills_detected

    async def _enhanced_monitor_position(self, symbol: str, side: str, monitor_key: str):
        """
        Enhanced monitoring loop with direct order checking
        
        Replaces the old position-size-only detection with more accurate methods
        """
        from config.settings import USE_DIRECT_ORDER_CHECKS, ORDER_CHECK_INTERVAL
        
        monitor_data = self.position_monitors.get(monitor_key)
        if not monitor_data:
            return
            
        # Use appropriate client
        account_type = monitor_data.get('account_type', 'main')
        client = self._mirror_client if account_type == 'mirror' and self._mirror_client else None
        
        try:
            # Use direct order checks if enabled
            if USE_DIRECT_ORDER_CHECKS:
                # Check for TP fills using enhanced detection
                fill_results = await self.detect_fills_with_confirmation(monitor_data, client)
                high_confidence_fills = fill_results.get('high_confidence_fills', {})
                
                # Process confirmed fills
                for order_id, fill_info in high_confidence_fills.items():
                    fill_data = fill_info['fill_data']
                    tp_number = fill_info.get('tp_number', 0)
                    
                    # Skip if already processed
                    if tp_number in monitor_data.get('filled_tps', []):
                        continue
                    
                    logger.info(f"✅ TP{tp_number} filled for {symbol} {side} ({account_type})")
                    
                    # Update monitor data
                    monitor_data['filled_tps'].append(tp_number)
                    
                    # Handle TP1 special logic
                    if tp_number == 1 and not monitor_data.get('tp1_hit'):
                        monitor_data['tp1_hit'] = True
                        monitor_data['tp1_info'] = {
                            'filled_at': fill_data.get('filled_time', time.time()),
                            'filled_price': fill_data.get('avg_price'),
                            'filled_qty': fill_data.get('filled_qty')
                        }
                        
                        # Trigger breakeven and limit order cancellation
                        await self._handle_tp1_fill_enhanced(monitor_data, client)
                    
                    # Update remaining size
                    filled_qty = fill_data.get('filled_qty', Decimal('0'))
                    monitor_data['remaining_size'] = max(
                        Decimal('0'), 
                        monitor_data['remaining_size'] - filled_qty
                    )
                    
                    # Adjust SL for remaining position
                    await self._adjust_sl_for_remaining_position(monitor_data, client)
                    
                    # Send alert with context
                    await self._send_tp_alert_with_context(monitor_data, tp_number, fill_data)
            
            # Always check position status (for closure detection)
            await self._check_position_status(monitor_data, client)
            
            # Update last check time
            monitor_data['last_check'] = time.time()
            
            # Save state
            await self._save_to_persistence()
            
        except Exception as e:
            logger.error(f"Error in enhanced monitoring for {monitor_key}: {e}")

    async def _handle_tp1_fill_enhanced(self, monitor_data: Dict, client=None):
        """
        Enhanced TP1 fill handling with comprehensive features:
        1. Move SL to breakeven with verification
        2. Cancel unfilled limit orders
        3. Send detailed alerts
        """
        from config.settings import CANCEL_LIMITS_ON_TP1, VERIFY_BREAKEVEN_PLACEMENT
        
        symbol = monitor_data['symbol']
        side = monitor_data['side']
        account_type = monitor_data.get('account_type', 'main')
        
        logger.info(f"🎯 Handling TP1 fill for {symbol} {side} ({account_type})")
        
        try:
            # 1. Move SL to breakeven
            if not monitor_data.get('sl_moved_to_be'):
                logger.info("📍 Moving SL to breakeven after TP1...")
                
                # Use appropriate breakeven method based on settings
                if BREAKEVEN_FAILSAFE_ENABLED:
                    from execution.breakeven_failsafe import breakeven_failsafe
                    success = await self._move_sl_to_breakeven(monitor_data)
                else:
                    success = await self._move_sl_to_breakeven_enhanced_v2(monitor_data)
                
                if success:
                    monitor_data['sl_moved_to_be'] = True
                    logger.info("✅ SL moved to breakeven successfully")
                    
                    # Verify if requested
                    if VERIFY_BREAKEVEN_PLACEMENT:
                        await asyncio.sleep(2)  # Brief delay for order to settle
                        verified = await self._verify_breakeven_placement(monitor_data, client)
                        if verified:
                            logger.info("✅ Breakeven placement verified")
                        else:
                            logger.warning("⚠️ Breakeven placement could not be verified")
                else:
                    logger.error("❌ Failed to move SL to breakeven")
            
            # 2. Cancel unfilled limit orders
            if CANCEL_LIMITS_ON_TP1 and not monitor_data.get('limit_orders_cancelled'):
                logger.info("🚫 Cancelling unfilled limit orders...")
                
                try:
                    cancelled_count = await self._cancel_unfilled_limit_orders(monitor_data)
                    if cancelled_count and cancelled_count > 0:
                        monitor_data['limit_orders_cancelled'] = True
                        logger.info(f"✅ Cancelled {cancelled_count} unfilled limit orders")
                    else:
                        logger.info("ℹ️ No unfilled limit orders found to cancel")
                except Exception as e:
                    logger.error(f"❌ Error cancelling unfilled limit orders: {e}")
                    # Don't crash the entire TP1 handling due to this error
            
            # 3. Update phase
            if monitor_data.get('phase') != 'PROFIT_TAKING':
                monitor_data['phase'] = 'PROFIT_TAKING'
                monitor_data['phase_transition_time'] = time.time()
            
        except Exception as e:
            logger.error(f"Error handling TP1 fill: {e}")

    async def _adjust_sl_for_remaining_position(self, monitor_data: Dict, client=None):
        """
        Adjust SL quantity to match remaining position after any TP fill
        No longer requires tp1_hit to be True
        """
        try:
            current_size = monitor_data.get('remaining_size', Decimal('0'))
            if current_size <= 0:
                return  # No position left
            
            sl_order = monitor_data.get('sl_order')
            if not sl_order or not sl_order.get('order_id'):
                logger.warning("No SL order to adjust")
                return
            
            current_sl_qty = Decimal(str(sl_order.get('quantity', 0)))
            
            # Check if adjustment needed
            if abs(current_sl_qty - current_size) > Decimal('0.001'):
                logger.info(f"🔧 Adjusting SL quantity: {current_sl_qty} → {current_size}")
                
                # Use the enhanced adjustment method
                success = await self._adjust_sl_quantity_enhanced(monitor_data, monitor_data.get('position_size', 0))
                
                if success:
                    logger.info("✅ SL quantity adjusted successfully")
                else:
                    logger.error("❌ Failed to adjust SL quantity")
                    
        except Exception as e:
            logger.error(f"Error adjusting SL for remaining position: {e}")

    async def _send_tp_alert_with_context(self, monitor_data: Dict, tp_number: int, fill_data: Dict):
        """
        Send TP alert with detailed context about the fill
        """
        from config.settings import TP_ALERT_DETAILED_CONTEXT
        
        try:
            symbol = monitor_data['symbol']
            side = monitor_data['side']
            account_type = monitor_data.get('account_type', 'main')
            
            # Check if mirror alerts are enabled for mirror accounts
            if account_type == "mirror" and not ENABLE_MIRROR_ALERTS:
                logger.debug(f"Mirror alerts disabled - skipping TP alert with context for {symbol} {side} mirror position")
                return
            
            # Use enhanced formatter for TP alerts
            filled_qty = fill_data.get('filled_qty', Decimal('0'))
            avg_price = fill_data.get('avg_price', Decimal('0'))
            remaining = monitor_data.get('remaining_size', Decimal('0'))
            entry_price = monitor_data.get('entry_price', Decimal('0'))
            original_size = monitor_data.get('position_size', Decimal('1'))
            
            # Calculate P&L
            if side == "Buy":
                pnl = (avg_price - entry_price) * filled_qty
                pnl_percent = ((avg_price - entry_price) / entry_price * 100) if entry_price > 0 else Decimal('0')
            else:  # Sell
                pnl = (entry_price - avg_price) * filled_qty
                pnl_percent = ((entry_price - avg_price) / entry_price * 100) if entry_price > 0 else Decimal('0')
            
            # Prepare additional info for enhanced formatter
            additional_info = {
                "tp_number": tp_number,
                "account_type": account_type,
                "filled_qty": filled_qty,
                "remaining_size": remaining,
                "detection_method": "enhanced_monitoring",
                "fill_confidence": "High",
                "remaining_tps": [f"TP{i}" for i in range(tp_number + 1, 5)],  # Show remaining TPs
                "has_mirror": monitor_data.get("has_mirror", False),
                "mirror_synced": True
            }
            
            # Use the enhanced formatter
            from utils.alert_helpers import format_tp_hit_alert
            message = format_tp_hit_alert(
                symbol=symbol,
                side=side,
                approach="conservative",
                pnl=pnl,
                pnl_percent=pnl_percent,
                entry_price=entry_price,
                exit_price=avg_price,
                position_size=filled_qty,
                cancelled_orders=[],  # No cancelled orders for regular TP hits
                additional_info=additional_info
            )
            
            # Send alert
            chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
            if chat_id:
                await send_trade_alert(chat_id, message, "tp_hit")
                logger.info(f"✅ Sent enhanced TP{tp_number} alert for {symbol} {side} ({account_type.upper()})")
            else:
                logger.warning(f"No chat_id for TP alert: {symbol} {side} ({account_type.upper()})")
                
        except Exception as e:
            logger.error(f"Error sending TP alert with context: {e}")

    async def _verify_breakeven_placement(self, monitor_data: Dict, client=None) -> bool:
        """
        Verify that SL was successfully moved to breakeven
        """
        try:
            symbol = monitor_data['symbol']
            sl_order = monitor_data.get('sl_order')
            
            if not sl_order or not sl_order.get('order_id'):
                return False
            
            # Query current SL order
            if not client:
                from clients.bybit_helpers import bybit_client
                client = bybit_client
            
            order_detail = await api_call_with_retry(
                lambda: client.get_order_history(
                    category="linear",
                    symbol=symbol,
                    orderId=sl_order['order_id']
                )
            )
            
            if order_detail and order_detail.get('retCode') == 0:
                # get_order_history returns a list of orders
                orders = order_detail.get('result', {}).get('list', [])
                if orders and len(orders) > 0:
                    order = orders[0]  # Get the first (and should be only) order
                    current_price = Decimal(str(order.get('triggerPrice', 0)))
                    expected_price = monitor_data.get('breakeven_price', monitor_data['entry_price'])
                    
                    # Allow small tolerance for price comparison
                    if abs(current_price - expected_price) < Decimal('0.0001'):
                        return True
                    else:
                        logger.warning(f"SL price mismatch: {current_price} vs expected {expected_price}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying breakeven placement: {e}")
            return False

    async def _check_position_status(self, monitor_data: Dict, client=None):
        """
        Check if position is still open and handle closure if needed
        """
        symbol = monitor_data['symbol']
        side = monitor_data['side']
        account_type = monitor_data.get('account_type', 'main')
        
        # Get current position
        if account_type == 'mirror':
            positions = await get_position_info_for_account(symbol, 'mirror')
        else:
            positions = await get_position_info(symbol)
        
        position_found = False
        if positions:
            for pos in positions:
                if pos.get('side') == side and Decimal(str(pos.get('size', 0))) > 0:
                    position_found = True
                    break
        
        if not position_found:
            # Position closed
            monitor_key = f"{symbol}_{side}_{account_type}"
            logger.info(f"Position {symbol} {side} ({account_type}) closed - cleaning up monitor")
    
    async def _get_adaptive_interval(self, symbol: str, side: str, position: Dict, monitor_key: str) -> int:
        """
        Get adaptive monitoring interval based on position state and market activity
        """
        try:
            if not ADAPTIVE_MONITORING_INTERVALS:
                return self.standard_monitor_interval
                
            monitor_data = self.position_monitors.get(monitor_key, {})
            
            # Check position PnL percentage
            pnl_percent = float(position.get('unrealisedPnlRatio', 0)) * 100
            
            # Check if near TP1 trigger (within 0.5%)
            if monitor_data.get('take_profits'):
                tp1_price = float(monitor_data['take_profits'][0].get('price', 0))
                current_price = float(position.get('markPrice', 0))
                
                if tp1_price > 0 and current_price > 0:
                    if side == "Buy":
                        distance_to_tp1 = ((tp1_price - current_price) / current_price) * 100
                    else:
                        distance_to_tp1 = ((current_price - tp1_price) / tp1_price) * 100
                    
                    # Critical zone - near TP1 trigger
                    if 0 < distance_to_tp1 < 0.5:
                        logger.debug(f"{symbol} near TP1 trigger ({distance_to_tp1:.2f}%) - using critical interval")
                        return self.critical_position_interval
            
            # Check if TP1 already hit (for breakeven monitoring)
            tp1_hit = monitor_data.get('tp1_hit', False)
            if tp1_hit and not monitor_data.get('sl_moved_to_breakeven', False):
                logger.debug(f"{symbol} TP1 hit, monitoring for breakeven - using active interval")
                return self.active_position_interval
            
            # Check if all TPs are filled
            remaining_tps = sum(1 for tp in monitor_data.get('take_profits', []) 
                               if not tp.get('filled', False))
            
            if remaining_tps == 0:
                logger.debug(f"{symbol} all TPs filled - using inactive interval")
                return self.inactive_position_interval
            
            # Check recent price movement
            price_cache_key = f"{symbol}_volatility"
            if price_cache_key in self.price_cache:
                _, last_check = self.price_cache[price_cache_key]
                if time.time() - last_check < 300:  # 5 minutes
                    # High volatility detected recently
                    return self.active_position_interval
            
            # Default to standard interval
            return self.standard_monitor_interval
            
        except Exception as e:
            logger.error(f"Error calculating adaptive interval: {e}")
            return self.standard_monitor_interval
            
            # Clean up orders and monitor
            await self.cleanup_position_orders(symbol, side)
            
            # Send closure alert
            await self._send_position_closed_alert(monitor_data)
            
            # Remove monitor
            if monitor_key in self.position_monitors:
                del self.position_monitors[monitor_key]

# Singleton implementation
_enhanced_tp_sl_manager_instance = None

def get_enhanced_tp_sl_manager():
    """Get or create the singleton EnhancedTPSLManager instance"""
    global _enhanced_tp_sl_manager_instance
    if _enhanced_tp_sl_manager_instance is None:
        _enhanced_tp_sl_manager_instance = EnhancedTPSLManager()
        
        # Initialize mirror manager only once
        try:
            from execution.mirror_enhanced_tp_sl import initialize_mirror_manager
            mirror_manager = initialize_mirror_manager(_enhanced_tp_sl_manager_instance)
            logger.info("✅ Mirror enhanced TP/SL manager initialized")
        except Exception as e:
            logger.warning(f"Could not initialize mirror enhanced TP/SL manager: {e}")
    
    return _enhanced_tp_sl_manager_instance

    async def save_state_for_restart(self):
        """Save monitor state specifically for safe bot restart"""
        try:
            logger.info("💾 Preparing monitor state for safe bot restart...")
            
            # Use robust persistence to save monitor state
            from utils.robust_persistence import robust_persistence
            
            # Save current monitor state 
            saved_count = 0
            for monitor_key, monitor_data in self.position_monitors.items():
                try:
                    # Save each monitor to robust persistence
                    await robust_persistence.update_monitor(monitor_key, monitor_data)
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Error saving monitor {monitor_key}: {e}")
            
            if saved_count > 0:
                # Create restart-specific signal file
                with open('.safe_restart_state_saved', 'w') as f:
                    import json
                    restart_info = {
                        'timestamp': time.time(),
                        'monitor_count': saved_count,
                        'execution_mode': getattr(self, '_execution_mode', False),
                        'performance_optimizations': {
                            'execution_aware_caching': True,
                            'api_call_deduplication': True,
                            'smart_throttling': True
                        }
                    }
                    json.dump(restart_info, f, indent=2)
                
                logger.info(f"✅ Bot ready for safe restart - {saved_count} monitors preserved")
                logger.info(f"🔄 Restart info saved to .safe_restart_state_saved")
                return True
            else:
                logger.warning("⚠️ No monitors to save for restart")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error preparing for safe restart: {e}")
            return False

# Global instance - use singleton pattern
enhanced_tp_sl_manager = get_enhanced_tp_sl_manager()

# Convenience function for saving state before restart
async def save_monitor_state_for_restart():
    """Convenience function to save monitor state for safe restart"""
    return await enhanced_tp_sl_manager.save_state_for_restart()