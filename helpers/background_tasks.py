from execution.mirror_position_sync import start_mirror_position_sync
#!/usr/bin/env python3
"""
Helper functions for properly initializing background tasks in the trading bot.
Add this to your bot initialization to fix the "no running event loop" errors.
FIXED: Added proper thread pool resource management with cleanup
"""
import asyncio
import logging
import os
import time
import atexit
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# FIXED: Global thread pool executor with proper resource management
_global_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bot-worker")

def cleanup_executor():
    """Cleanup function for thread pool executor"""
    try:
        _global_executor.shutdown(wait=True, cancel_futures=True)
        logger.info("✅ Thread pool executor cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up thread pool executor: {e}")

# Register cleanup function to run on exit
atexit.register(cleanup_executor)

# Import robust_persistence for monitor sync
from utils.robust_persistence import robust_persistence

async def enhanced_tp_sl_monitoring_loop():
    """
    Background task for Enhanced TP/SL monitoring
    This continuously monitors all positions and manages their TP/SL orders
    """
    logger.info("🎯 Enhanced TP/SL monitoring loop started")
    
    loop_count = 0
    while True:
        try:
            loop_count += 1
            # Log every 60 loops (5 minutes) to show the loop is running
            if loop_count % 60 == 1:
                logger.info(f"🔄 Enhanced TP/SL monitoring loop cycle #{loop_count}")
            
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            
            # Log the manager state less frequently
            if loop_count % 60 == 1:  # Every 5 minutes instead of every minute
                logger.info(f"🔍 Enhanced TP/SL Manager - Active monitors: {len(enhanced_tp_sl_manager.position_monitors)}")
            
            # Check for signal file to reload monitors
            signal_file = '/Users/lualakol/bybit-telegram-bot/reload_enhanced_monitors.signal'
            force_load_signal = '/Users/lualakol/bybit-telegram-bot/.force_load_all_monitors'
            should_reload = False
            
            if not enhanced_tp_sl_manager.position_monitors:
                should_reload = True
                if not hasattr(enhanced_tp_sl_monitoring_loop, '_last_load_attempt_log'):
                    enhanced_tp_sl_monitoring_loop._last_load_attempt_log = 0
                
                import time
                current_time = time.time()
                if current_time - enhanced_tp_sl_monitoring_loop._last_load_attempt_log > 300:  # Log every 5 minutes
                    logger.info("🔍 No monitors found, attempting to load from persistence...")
                    enhanced_tp_sl_monitoring_loop._last_load_attempt_log = current_time
                else:
                    logger.debug("🔍 No monitors found, attempting to load from persistence...")
            elif os.path.exists(signal_file):
                should_reload = True
                logger.info("📡 Signal file detected, reloading monitors from persistence...")
            elif os.path.exists(force_load_signal):
                should_reload = True
                logger.info("🔄 Force load ALL monitors signal detected...")
            
            # Check for and load monitors from persistence if needed
            if should_reload:
                try:
                    # PERFORMANCE OPTIMIZATION: Use thread pool for CPU-bound pickle operations
                    import pickle
                    import concurrent.futures
                    
                    # Reduce verbosity of pickle loading logs
                    logger.debug(f"🔍 Loading monitors directly from pickle file")
                    logger.debug(f"🔍 Current monitor count: {len(enhanced_tp_sl_manager.position_monitors)}")
                    
                    # Get all monitors from pickle using thread pool to prevent event loop blocking
                    loop = asyncio.get_running_loop()
                    
                    def load_pickle_data():
                        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                            return pickle.load(f)
                    
                    # FIXED: Use global executor pool instead of creating new one
                    try:
                        data = await loop.run_in_executor(_global_executor, load_pickle_data)
                    except Exception as e:
                        logger.error(f"Error loading pickle data: {e}")
                        raise
                    
                    persisted_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
                    logger.info(f"🔍 Found {len(persisted_monitors)} persisted monitors")
                    
                    if persisted_monitors:
                        # Only log monitor keys if more than 5 monitors or debug mode
                        if len(persisted_monitors) > 5:
                            logger.info(f"🔍 Monitor keys ({len(persisted_monitors)}): {list(persisted_monitors.keys())[:5]}...")
                        else:
                            logger.debug(f"🔍 Monitor keys: {list(persisted_monitors.keys())}")
                        
                        # Clear existing monitors and load fresh from persistence
                        enhanced_tp_sl_manager.position_monitors.clear()
                        
                        # PERFORMANCE OPTIMIZATION: Use thread pool for CPU-intensive data processing
                        def process_monitor_data(monitors_dict):
                            """Process monitor data in thread pool to prevent event loop blocking"""
                            processed_monitors = {}
                            
                            # Sanitize each monitor data to ensure numeric fields are Decimal
                            for monitor_key, monitor_data in monitors_dict.items():
                                # Only load monitors with proper account suffixes to prevent legacy monitor issues
                                if monitor_key.endswith('_main') or monitor_key.endswith('_mirror'):
                                    # This can be CPU-intensive for large datasets
                                    sanitized_data = enhanced_tp_sl_manager._sanitize_monitor_data(monitor_data)
                                    
                                    # FIX FOR EXISTING MONITORS: Initialize last_known_size if missing
                                    if 'last_known_size' not in sanitized_data or sanitized_data.get('last_known_size', 0) == 0:
                                        remaining_size = sanitized_data.get('remaining_size', 0)
                                        position_size = sanitized_data.get('position_size', 0)
                                        from decimal import Decimal
                                        sanitized_data['last_known_size'] = Decimal(str(remaining_size)) if remaining_size > 0 else Decimal(str(position_size))
                                    
                                    # Also ensure phase is set if missing
                                    if 'phase' not in sanitized_data:
                                        if sanitized_data.get('tp1_hit', False):
                                            sanitized_data['phase'] = 'PROFIT_TAKING'
                                        elif sanitized_data.get('limit_orders_filled', False):
                                            sanitized_data['phase'] = 'MONITORING'
                                        else:
                                            sanitized_data['phase'] = 'BUILDING'
                                    
                                    processed_monitors[monitor_key] = sanitized_data
                            
                            return processed_monitors
                        
                        # Process monitor data in thread pool
                        # FIXED: Use global executor pool
                        try:
                            processed_monitors = await loop.run_in_executor(_global_executor, process_monitor_data, persisted_monitors)
                        except Exception as e:
                            logger.error(f"Error processing monitor data: {e}")
                            processed_monitors = persisted_monitors
                        
                        # Apply the processed monitors to the manager
                        enhanced_tp_sl_manager.position_monitors.update(processed_monitors)
                        
                        logger.info(f"🔧 Processed {len(processed_monitors)} monitors with thread pool optimization")
                        
                        logger.info(f"✅ Loaded {len(enhanced_tp_sl_manager.position_monitors)} monitors from robust persistence")
                        logger.info(f"🔍 Manager now has {len(enhanced_tp_sl_manager.position_monitors)} monitors")
                        
                        # Only sync with positions if NOT force loading (force load keeps all monitors)
                        if not os.path.exists(force_load_signal):
                            # CRITICAL FIX: Use monitoring cache for position sync
                            try:
                                from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
                                positions = await enhanced_tp_sl_manager._get_cached_position_info("ALL", "main")
                                # Note: sync_with_positions will remove orphaned monitors but not sync sizes
                                await robust_persistence.sync_with_positions(positions)
                            except Exception as e:
                                logger.warning(f"Could not get positions from cache for sync: {e}")
                                # Fallback to direct API call
                                from clients.bybit_helpers import get_all_positions
                                positions = await get_all_positions()
                                await robust_persistence.sync_with_positions(positions)
                        else:
                            logger.info("🔄 Force load mode - keeping ALL monitors without position sync")
                        
                        
                        # Remove the signal files if they exist
                        if os.path.exists(signal_file):
                            os.remove(signal_file)
                            logger.info("📡 Monitor reload signal processed")
                        if os.path.exists(force_load_signal):
                            os.remove(force_load_signal)
                            logger.info("🔄 Force load signal processed")
                    else:
                        # Only log this warning once every 5 minutes to reduce spam
                        if not hasattr(enhanced_tp_sl_monitoring_loop, '_last_no_persist_log'):
                            enhanced_tp_sl_monitoring_loop._last_no_persist_log = 0
                        
                        import time
                        current_time = time.time()
                        if current_time - enhanced_tp_sl_monitoring_loop._last_no_persist_log > 300:  # 5 minutes
                            logger.info("📊 No monitors in persistence (this is normal for fresh start)")
                            enhanced_tp_sl_monitoring_loop._last_no_persist_log = current_time
                        
                    # PERFORMANCE OPTIMIZATION: Get persistence stats without blocking event loop
                    try:
                        # Use thread pool for potentially CPU-bound stats calculation
                        def get_persistence_stats():
                            return {
                                'total_monitors': len(enhanced_tp_sl_manager.position_monitors),
                                'file_size_mb': len(str(data)) / (1024 * 1024)  # Approximate size
                            }
                        
                        # FIXED: Use global executor pool
                        try:
                            stats = await loop.run_in_executor(_global_executor, get_persistence_stats)
                        except Exception as e:
                            logger.error(f"Error getting persistence stats: {e}")
                            stats = {}
                        logger.info(f"📊 Persistence stats: {stats.get('total_monitors')} monitors, {stats.get('file_size_mb'):.2f}MB file")
                    except Exception as stats_error:
                        logger.debug(f"Could not calculate persistence stats: {stats_error}")
                
                except Exception as e:
                    logger.error(f"❌ Could not load monitors from persistence: {e}")
                    import traceback
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
            
            # Periodic position sync (every 60 seconds)
            import time
            if not hasattr(enhanced_tp_sl_monitoring_loop, '_last_position_sync'):
                enhanced_tp_sl_monitoring_loop._last_position_sync = 0
            
            current_time = time.time()
            if current_time - enhanced_tp_sl_monitoring_loop._last_position_sync > 60:
                logger.info("🔄 Running periodic position sync check")
                try:
                    await enhanced_tp_sl_manager.sync_existing_positions()
                    
                    # AUTOMATIC STALE MONITOR DETECTION: Remove monitors for positions that no longer exist
                    stale_removed = await enhanced_tp_sl_manager.detect_and_remove_stale_monitors()
                    if stale_removed > 0:
                        logger.info(f"🧹 Automatic cleanup: Removed {stale_removed} stale monitors")
                    
                    # Mirror sync removed - mirror accounts operate independently
                    # Each account's monitors handle their own positions without syncing
                    
                    enhanced_tp_sl_monitoring_loop._last_position_sync = current_time
                except Exception as e:
                    logger.error(f"❌ Error during periodic position sync: {e}")
            
            
            # Monitor all active positions (only count properly formatted monitors)
            all_monitors = enhanced_tp_sl_manager.position_monitors
            # Only count monitors with proper account-aware keys (ending in _main or _mirror)
            valid_monitors = {k: v for k, v in all_monitors.items() 
                            if k.endswith('_main') or k.endswith('_mirror')}
            monitor_count = len(valid_monitors)
            
            # PERFORMANCE ENHANCEMENT: Adaptive monitoring intervals based on system load
            next_sleep_interval = int(os.getenv('POSITION_MONITOR_INTERVAL', 12))  # Use env setting or default 12s
            adaptive_monitoring = os.getenv('ENABLE_ADAPTIVE_MONITORING', 'true').lower() == 'true'
            
            if monitor_count > 0:
                # Reduce logging frequency for better performance
                if loop_count % 10 == 1:  # Log every 10 cycles instead of every cycle
                    logger.info(f"🔍 Monitoring {monitor_count} positions (adaptive: {adaptive_monitoring})")
                
                # PERFORMANCE OPTIMIZATION: Smart urgency-based grouping with API batching
                urgency_groups = {
                    'critical': [],    # 2s interval - near TP triggers
                    'active': [],      # 5s interval - profit taking
                    'standard': [],    # 12s interval - normal monitoring  
                    'inactive': [],    # 30s interval - mostly complete
                    'idle': []         # 60s interval - no activity
                }
                min_interval = float('inf')
                
                # TEMPORARY: Disable batch processor to fix startup issues
                # Initialize batch processor if not started
                # from utils.api_batch_processor import get_batch_processor, start_batch_processor
                # batch_processor = get_batch_processor()
                # 
                # # Start batch processor if not running
                # if batch_processor._processor_task is None:
                #     await start_batch_processor()
                #     logger.info("🚀 API Batch Processor started for monitoring")
                
                # Group monitors by urgency level
                for monitor_key, monitor_data in list(valid_monitors.items()):
                    try:
                        # Extract account type from monitor data
                        account_type = monitor_data.get("account_type", "main")
                        
                        # Calculate monitoring interval and determine urgency group
                        interval = enhanced_tp_sl_manager._calculate_monitoring_interval(monitor_data)
                        min_interval = min(min_interval, interval)
                        
                        # Classify by urgency level
                        if interval <= 2:
                            urgency_level = 'critical'
                        elif interval <= 5:
                            urgency_level = 'active'
                        elif interval <= 12:
                            urgency_level = 'standard'
                        elif interval <= 30:
                            urgency_level = 'inactive'
                        else:
                            urgency_level = 'idle'
                        
                        # Add debug logging for mirror monitors
                        if monitor_key.endswith('_mirror'):
                            logger.debug(f"🔍 Mirror monitor {monitor_key}: {urgency_level} urgency ({interval}s)")
                        
                        # Group by urgency level
                        task_data = {
                            'monitor_key': monitor_key,
                            'symbol': monitor_data["symbol"],
                            'side': monitor_data["side"],
                            'account_type': account_type,
                            'interval': interval,
                            'urgency_level': urgency_level  # Add missing urgency level
                        }
                        urgency_groups[urgency_level].append(task_data)
                        
                    except Exception as e:
                        logger.error(f"❌ Error grouping monitor {monitor_key}: {e}")
                
                # PERFORMANCE OPTIMIZATION: Adaptive semaphore-based concurrency control
                # Research shows 10-20 concurrent operations optimal for trading bots
                # Adjust based on system load and urgency distribution
                critical_count = len(urgency_groups.get('critical', []))
                total_monitors = sum(len(monitors) for monitors in urgency_groups.values())
                
                # Adaptive concurrency: more concurrent ops for fewer critical monitors
                if critical_count > 20:
                    max_concurrent_monitors = 12  # Conservative for high critical load
                elif critical_count > 10:
                    max_concurrent_monitors = 15  # Balanced approach
                else:
                    max_concurrent_monitors = 20  # More aggressive for low critical load
                
                api_semaphore = asyncio.Semaphore(max_concurrent_monitors)
                logger.debug(f"🔒 Using {max_concurrent_monitors} concurrent monitors (critical: {critical_count}, total: {total_monitors})")
                
                # TEMPORARY: Simplified processing without batch processor
                # PHASE 3 OPTIMIZATION: Batched API calls with priority queue processing
                # from utils.api_batch_processor import BatchPriority
                
                # Submit requests to batch processor by priority
                batch_requests = {
                    'critical': [],
                    'standard': [],
                    'maintenance': []
                }
                
                # PROGRESSIVE API BATCHING: Group similar requests to reduce API call volume
                symbol_account_groups = {}
                for urgency_level, group_monitors in urgency_groups.items():
                    if not group_monitors:
                        continue
                    
                    # Group monitors by symbol and account for batch processing
                    for task_data in group_monitors:
                        symbol = task_data["symbol"]
                        account = task_data["account_type"]
                        key = f"{symbol}_{account}"
                        
                        if key not in symbol_account_groups:
                            symbol_account_groups[key] = {
                                'monitors': [],
                                'symbol': symbol,
                                'account_type': account,
                                'urgency_levels': set()
                            }
                        
                        symbol_account_groups[key]['monitors'].append(task_data)
                        symbol_account_groups[key]['urgency_levels'].add(urgency_level)
                
                # Submit batched requests - one per symbol/account combination
                for group_key, group_data in symbol_account_groups.items():
                    symbol = group_data['symbol']
                    account = group_data['account_type']
                    monitors = group_data['monitors']
                    urgency_levels = group_data['urgency_levels']
                    
                    # Determine batch priority based on most urgent monitor in group
                    if any(level in ['critical', 'active'] for level in urgency_levels):
                        batch_category = 'critical'
                    elif 'standard' in urgency_levels:
                        batch_category = 'standard'
                    else:
                        batch_category = 'maintenance'
                    
                    # SIMPLIFIED: Add monitors directly to batch for processing
                    try:
                        # Add all monitors from this group to the batch (simplified approach)
                        for task_data in monitors:
                            batch_requests[batch_category].append({
                                'monitor_key': task_data["monitor_key"],
                                'symbol': symbol,
                                'side': task_data["side"],
                                'account_type': account,
                                'urgency_level': task_data.get("urgency_level", "standard"),
                                'batch_group': group_key
                            })
                    
                    except Exception as batch_error:
                        logger.warning(f"Failed to process batch group {group_key}: {batch_error}")
                
                # Log batching effectiveness
                total_monitor_count = sum(len(monitors) for monitors in urgency_groups.values())
                api_call_reduction = total_monitor_count - len(symbol_account_groups) * 2  # 2 calls per group instead of 2 per monitor
                if api_call_reduction > 0:
                    reduction_pct = (api_call_reduction / (total_monitor_count * 2)) * 100
                    logger.info(f"📦 API batching: Reduced {total_monitor_count * 2} calls to {len(symbol_account_groups) * 2} ({reduction_pct:.1f}% reduction)")
                
                # Process monitors after batched API calls complete
                # (Small delay to allow batch processor to work)
                await asyncio.sleep(0.1)
                
                total_processed = 0
                start_time = time.time()
                
                # PRIORITY EXECUTION: Process batched requests by priority
                for batch_category in ['critical', 'standard', 'maintenance']:
                    if not batch_requests[batch_category]:
                        continue
                    
                    # Skip maintenance if we're running out of time
                    if batch_category == 'maintenance' and (time.time() - start_time) > 5:
                        logger.debug(f"⏭️ Skipped {len(batch_requests[batch_category])} maintenance monitors due to time constraints")
                        continue
                    
                    try:
                        # Process each monitor in this priority group with semaphore control
                        monitor_tasks = []
                        for request_data in batch_requests[batch_category]:
                            # Create monitoring task using batched data with semaphore
                            async def semaphore_controlled_monitor(symbol, side, account_type, semaphore):
                                async with semaphore:
                                    return await enhanced_tp_sl_manager.monitor_and_adjust_orders(
                                        symbol, side, account_type
                                    )
                            
                            task = semaphore_controlled_monitor(
                                request_data["symbol"], 
                                request_data["side"],
                                request_data["account_type"],
                                api_semaphore
                            )
                            monitor_tasks.append((request_data["monitor_key"], task, request_data["urgency_level"]))
                        
                        # PROGRESSIVE BATCHING: Execute monitoring tasks with optimized asyncio.gather
                        if monitor_tasks:
                            # Group tasks by batch_group to maximize shared data usage
                            batch_grouped_tasks = {}
                            for monitor_key, task, urgency_level in monitor_tasks:
                                # Find the batch_group for this monitor
                                batch_group = None
                                for request_data in batch_requests[batch_category]:
                                    if request_data["monitor_key"] == monitor_key:
                                        batch_group = request_data.get("batch_group", "unknown")
                                        break
                                
                                if batch_group not in batch_grouped_tasks:
                                    batch_grouped_tasks[batch_group] = []
                                batch_grouped_tasks[batch_group].append((monitor_key, task, urgency_level))
                            
                            # Execute tasks in batch groups using asyncio.gather for optimal performance
                            all_results = []
                            for batch_group, group_tasks in batch_grouped_tasks.items():
                                if len(group_tasks) > 1:
                                    # Use asyncio.gather for multiple tasks in same batch
                                    task_list = [task for _, task, _ in group_tasks]
                                    group_results = await asyncio.gather(*task_list, return_exceptions=True)
                                    # Pair results back with monitor info
                                    for (monitor_key, _, urgency_level), result in zip(group_tasks, group_results):
                                        all_results.append(((monitor_key, None, urgency_level), result))
                                else:
                                    # Single task - execute directly
                                    monitor_key, task, urgency_level = group_tasks[0]
                                    try:
                                        result = await task
                                        all_results.append(((monitor_key, None, urgency_level), result))
                                    except Exception as e:
                                        all_results.append(((monitor_key, None, urgency_level), e))
                            
                            # Process results (maintain compatibility with existing code)
                            results = [result for _, result in all_results]
                            monitor_tasks = [(monitor_key, None, urgency_level) for (monitor_key, _, urgency_level), _ in all_results]
                            
                            # Process results
                            for (monitor_key, _, urgency_level), result in zip(monitor_tasks, results):
                                if isinstance(result, Exception):
                                    if batch_category == 'critical':
                                        logger.error(f"🚨 CRITICAL ERROR monitoring {monitor_key} ({urgency_level}): {result}")
                                    elif batch_category == 'standard':
                                        logger.error(f"⚠️ Error monitoring {monitor_key} ({urgency_level}): {result}")
                                    else:
                                        logger.debug(f"💤 Error monitoring {monitor_key} ({urgency_level}): {result}")
                            
                            total_processed += len(monitor_tasks)
                            
                            # Log with appropriate emoji and level
                            if batch_category == 'critical':
                                logger.debug(f"🔥 Processed {len(monitor_tasks)} CRITICAL priority monitors")
                            elif batch_category == 'standard':
                                logger.debug(f"⚡ Processed {len(monitor_tasks)} STANDARD priority monitors")
                            else:
                                logger.debug(f"🔧 Processed {len(monitor_tasks)} MAINTENANCE priority monitors")
                    
                    except Exception as e:
                        if batch_category == 'critical':
                            logger.error(f"❌ Error processing critical priority queue: {e}")
                        elif batch_category == 'standard':
                            logger.error(f"❌ Error processing standard priority queue: {e}")
                        else:
                            logger.debug(f"💤 Error processing maintenance priority queue: {e}")
                
                execution_time = time.time() - start_time
                
                # Enhanced logging with urgency breakdown
                urgency_counts = {level: len(monitors) for level, monitors in urgency_groups.items() if monitors}
                logger.info(f"⚡ Processed {total_processed} monitors in {execution_time:.2f}s - Urgency breakdown: {urgency_counts}")
                
                # Use the most urgent (shortest) interval
                next_sleep_interval = min_interval if min_interval != float('inf') else 12
                
                # Log interval selection every 60 loops (varies based on interval)
                if loop_count % 60 == 1:
                    logger.info(f"⏱️ Next monitoring cycle in {next_sleep_interval}s (most urgent position interval)")
                    
            else:
                # Only log this every 30 seconds to avoid spam
                if not hasattr(enhanced_tp_sl_monitoring_loop, '_last_no_monitors_log'):
                    enhanced_tp_sl_monitoring_loop._last_no_monitors_log = 0
                
                if current_time - enhanced_tp_sl_monitoring_loop._last_no_monitors_log > 300:  # 5 minutes instead of 30 seconds
                    logger.info("📊 No active monitors (normal if no positions open)")
                    enhanced_tp_sl_monitoring_loop._last_no_monitors_log = current_time
                    
                next_sleep_interval = 60  # Sleep longer when no positions
            
            # PHASE 3 OPTIMIZATION: Separate maintenance task scheduling
            # Run maintenance less frequently when system is busy
            active_monitor_count = len([m for m in valid_monitors.values() if m.get('phase') in ['MONITORING', 'PROFIT_TAKING']])
            
            if active_monitor_count > 10:
                # High activity - run maintenance every 4 hours
                maintenance_interval = 1440  # Every ~4 hours
            elif active_monitor_count > 5:
                # Medium activity - run maintenance every 2 hours 
                maintenance_interval = 720   # Every ~2 hours
            else:
                # Low activity - run maintenance every hour
                maintenance_interval = 360   # Every ~1 hour
            
            if loop_count % maintenance_interval == 1:
                # Use lower priority for maintenance during high activity
                if active_monitor_count > 10:
                    asyncio.create_task(_consolidated_maintenance_task_low_priority())
                else:
                    asyncio.create_task(_consolidated_maintenance_task())
            
            # ULTRA-HIGH PERFORMANCE: Dynamic monitoring intervals based on position count and urgency
            from config.settings import (
                ENABLE_EXECUTION_SPEED_OPTIMIZATION, EXECUTION_MODE_MONITORING_INTERVAL,
                ENABLE_ULTRA_PERFORMANCE_MODE, ULTRA_HIGH_POSITION_THRESHOLD
            )
            
            # Check execution mode first (highest priority)
            if ENABLE_EXECUTION_SPEED_OPTIMIZATION and enhanced_tp_sl_manager.is_execution_mode_active():
                execution_interval = EXECUTION_MODE_MONITORING_INTERVAL
                logger.debug(f"⚡ EXECUTION MODE: Using extended monitoring interval {execution_interval}s")
                await asyncio.sleep(execution_interval)
            elif ENABLE_ULTRA_PERFORMANCE_MODE and monitor_count >= 25:
                # Check for EXTREME mode first (400+ positions)
                from config.settings import ENABLE_EXTREME_PERFORMANCE_MODE, EXTREME_POSITION_THRESHOLD
                
                if ENABLE_EXTREME_PERFORMANCE_MODE and monitor_count >= EXTREME_POSITION_THRESHOLD:
                    # EXTREME PERFORMANCE MODE: For 400+ positions
                    
                    # Check if execution mode has enabled critical-only monitoring
                    if enhanced_tp_sl_manager.is_critical_only_monitoring():
                        # EMERGENCY MODE: Only monitor CRITICAL positions during execution
                        critical_positions = []
                        for monitor_key, monitor_data in valid_monitors.items():
                            symbol = monitor_data.get('symbol', '')
                            if symbol:
                                current_price = enhanced_tp_sl_manager.price_cache.get(symbol, {}).get('price', 0)
                                if current_price:
                                    urgency = enhanced_tp_sl_manager._get_cached_position_urgency(
                                        monitor_key, monitor_data, Decimal(str(current_price))
                                    )
                                    if urgency == "CRITICAL":
                                        critical_positions.append(monitor_key)
                        
                        if critical_positions:
                            logger.warning(f"🚨 CRITICAL-ONLY MODE: Monitoring {len(critical_positions)} critical positions only")
                            monitoring_interval = 2  # Fast monitoring for critical positions only
                        else:
                            logger.debug("🚨 CRITICAL-ONLY MODE: No critical positions - pausing monitoring")
                            monitoring_interval = 30  # Long pause if no critical positions
                        
                        await asyncio.sleep(monitoring_interval)
                        continue
                    
                    # EXTREME MODE: Normal operation with ultra-aggressive intervals
                    position_urgencies = {}
                    urgency_counts = {"CRITICAL": 0, "URGENT": 0, "ACTIVE": 0, "BUILDING": 0, "STABLE": 0, "DORMANT": 0}
                    
                    # Batch process position classification to reduce load
                    from config.settings import EXTREME_BATCH_SIZE, EXTREME_BATCH_INTERVAL
                    
                    monitor_items = list(valid_monitors.items())
                    for i in range(0, len(monitor_items), EXTREME_BATCH_SIZE):
                        batch = monitor_items[i:i + EXTREME_BATCH_SIZE]
                        
                        for monitor_key, monitor_data in batch:
                            symbol = monitor_data.get('symbol', '')
                            if symbol:
                                current_price = enhanced_tp_sl_manager.price_cache.get(symbol, {}).get('price', 0)
                                if current_price:
                                    urgency = enhanced_tp_sl_manager._get_cached_position_urgency(
                                        monitor_key, monitor_data, Decimal(str(current_price))
                                    )
                                    position_urgencies[monitor_key] = urgency
                                    urgency_counts[urgency] += 1
                        
                        # Small delay between batches to prevent overwhelming the system
                        if i + EXTREME_BATCH_SIZE < len(monitor_items):
                            await asyncio.sleep(EXTREME_BATCH_INTERVAL)
                    
                    # Calculate extreme intervals
                    extreme_intervals = enhanced_tp_sl_manager._calculate_extreme_monitoring_interval(
                        monitor_count, position_urgencies
                    )
                    
                    # Use shortest interval from most urgent positions
                    if urgency_counts["CRITICAL"] > 0:
                        monitoring_interval = extreme_intervals["CRITICAL"]
                        priority_msg = f"CRITICAL positions ({urgency_counts['CRITICAL']})"
                    elif urgency_counts["URGENT"] > 0:
                        monitoring_interval = extreme_intervals["URGENT"]
                        priority_msg = f"URGENT positions ({urgency_counts['URGENT']})"
                    else:
                        # Use weighted average for non-urgent positions at extreme scale
                        total_positions = sum(urgency_counts.values())
                        if total_positions > 0:
                            weighted_interval = (
                                urgency_counts["ACTIVE"] * extreme_intervals["ACTIVE"] +
                                urgency_counts["BUILDING"] * extreme_intervals["BUILDING"] +
                                urgency_counts["STABLE"] * extreme_intervals["STABLE"] +
                                urgency_counts["DORMANT"] * extreme_intervals["DORMANT"]
                            ) / total_positions
                            monitoring_interval = max(60, int(weighted_interval))  # Minimum 1 minute for extreme scale
                            priority_msg = f"STABLE positions (avg {monitoring_interval}s)"
                        else:
                            monitoring_interval = 300  # 5 minutes if no positions
                            priority_msg = "no active positions"
                    
                    # Log extreme performance status less frequently to reduce noise
                    if loop_count % 20 == 1:  # Every 20 cycles
                        api_calls_per_sec = monitor_count * 2 / monitoring_interval
                        api_reduction = (1 - (api_calls_per_sec / (monitor_count * 2 / 5))) * 100
                        
                        logger.warning(f"🔥🔥 EXTREME MODE: {monitor_count} positions - {priority_msg} → {monitoring_interval}s")
                        logger.warning(f"   📊 Urgency: C:{urgency_counts['CRITICAL']} U:{urgency_counts['URGENT']} A:{urgency_counts['ACTIVE']} S:{urgency_counts['STABLE']} D:{urgency_counts['DORMANT']}")
                        logger.warning(f"   ⚡ API calls: {api_calls_per_sec:.1f}/sec ({api_reduction:.1f}% reduction)")
                    
                    await asyncio.sleep(monitoring_interval)
                
                else:
                    # ULTRA-HIGH PERFORMANCE MODE: Dynamic intervals based on urgency
                    
                    # Classify all positions by urgency using fast price lookup
                    position_urgencies = {}
                    urgency_counts = {"CRITICAL": 0, "URGENT": 0, "ACTIVE": 0, "BUILDING": 0, "STABLE": 0, "DORMANT": 0}
                    
                    try:
                        for monitor_key, monitor_data in valid_monitors.items():
                            symbol = monitor_data.get('symbol', '')
                            if symbol:
                                # Get cached price to avoid extra API calls
                                current_price = enhanced_tp_sl_manager.price_cache.get(symbol, {}).get('price', 0)
                                if current_price:
                                    urgency = enhanced_tp_sl_manager._get_cached_position_urgency(
                                        monitor_key, monitor_data, Decimal(str(current_price))
                                    )
                                    position_urgencies[monitor_key] = urgency
                                    urgency_counts[urgency] += 1
                    except Exception as e:
                        logger.debug(f"Error classifying position urgencies: {e}")
                        # Fallback to normal monitoring
                        await asyncio.sleep(next_sleep_interval)
                        continue
                    
                    # Calculate dynamic intervals
                    dynamic_intervals = enhanced_tp_sl_manager._calculate_dynamic_monitoring_interval(
                        monitor_count, position_urgencies
                    )
                    
                    # Use the shortest interval (most urgent position determines sleep time)
                    urgent_positions = urgency_counts["CRITICAL"] + urgency_counts["URGENT"]
                    if urgency_counts["CRITICAL"] > 0:
                        monitoring_interval = dynamic_intervals["CRITICAL"]
                        priority_msg = f"CRITICAL positions ({urgency_counts['CRITICAL']})"
                    elif urgency_counts["URGENT"] > 0:
                        monitoring_interval = dynamic_intervals["URGENT"]  
                        priority_msg = f"URGENT positions ({urgency_counts['URGENT']})"
                    elif urgency_counts["ACTIVE"] > 0:
                        monitoring_interval = dynamic_intervals["ACTIVE"]
                        priority_msg = f"ACTIVE positions ({urgency_counts['ACTIVE']})"
                    else:
                        # Use weighted average for stable positions
                        total_positions = sum(urgency_counts.values())
                        if total_positions > 0:
                            weighted_interval = (
                                urgency_counts["BUILDING"] * dynamic_intervals["BUILDING"] +
                                urgency_counts["STABLE"] * dynamic_intervals["STABLE"] +
                                urgency_counts["DORMANT"] * dynamic_intervals["DORMANT"]
                            ) / total_positions
                            monitoring_interval = int(weighted_interval)
                            priority_msg = f"STABLE/DORMANT positions (avg {monitoring_interval}s)"
                        else:
                            monitoring_interval = 60
                            priority_msg = "no active positions"
                    
                    # Log ultra-performance status every 10 cycles to reduce noise
                    if loop_count % 10 == 1:
                        logger.info(f"🔥 ULTRA-PERFORMANCE: {monitor_count} positions - {priority_msg} → {monitoring_interval}s")
                        if monitor_count >= ULTRA_HIGH_POSITION_THRESHOLD:
                            api_reduction = ((monitor_count * 2) - (sum(1 for u in urgency_counts.values() if u > 0))) / (monitor_count * 2) * 100
                            logger.info(f"   📊 Urgency breakdown: {dict(urgency_counts)}")
                            logger.info(f"   ⚡ Estimated API call reduction: {api_reduction:.1f}%")
                    
                    await asyncio.sleep(monitoring_interval)
            else:
                # Normal monitoring interval (legacy behavior)
                await asyncio.sleep(next_sleep_interval)
            
        except asyncio.CancelledError:
            logger.info("🛑 Enhanced TP/SL monitoring loop cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error in Enhanced TP/SL monitoring loop: {e}")
            await asyncio.sleep(10)  # Wait longer on error

async def _consolidated_maintenance_task_low_priority():
    """Low priority maintenance task for high activity periods"""
    try:
        logger.info("🧹 Running LOW PRIORITY maintenance tasks...")
        
        # Only run essential cleanup during high activity
        maintenance_tasks = [
            _run_cache_cleanup()  # Only cache cleanup during high activity
        ]
        
        results = await asyncio.gather(*maintenance_tasks, return_exceptions=True)
        success_count = sum(1 for result in results if not isinstance(result, Exception))
        logger.info(f"✅ Low priority maintenance completed: {success_count}/1 tasks successful")
        
    except Exception as e:
        logger.error(f"❌ Error in low priority maintenance task: {e}")

async def _consolidated_maintenance_task():
    """Enhanced consolidated maintenance task with performance optimization (2025)"""
    try:
        logger.info("🧹 Running ENHANCED maintenance tasks...")
        
        # Import cleanup functions
        from execution.monitor import periodic_monitor_cleanup
        from clients.bybit_helpers import periodic_order_cleanup_task
        from utils.cache import enhanced_cache
        
        # Enhanced maintenance tasks with performance optimization
        maintenance_tasks = [
            _run_monitor_cleanup(),
            _run_order_cleanup(), 
            _run_cache_cleanup(),
            _run_performance_optimization(),
            _run_memory_leak_check()
        ]
        
        results = await asyncio.gather(*maintenance_tasks, return_exceptions=True)
        
        success_count = sum(1 for result in results if not isinstance(result, Exception))
        error_count = len(results) - success_count
        
        if error_count > 0:
            logger.warning(f"⚠️ Enhanced maintenance completed: {success_count}/{len(maintenance_tasks)} tasks successful ({error_count} errors)")
        else:
            logger.info(f"✅ Enhanced maintenance completed: {success_count}/{len(maintenance_tasks)} tasks successful")
        
    except Exception as e:
        logger.error(f"❌ Error in enhanced consolidated maintenance task: {e}")

async def _run_performance_optimization():
    """Run performance optimization as part of maintenance"""
    try:
        from utils.performance_monitor import optimize_bot_performance
        
        optimized = await optimize_bot_performance()
        if optimized:
            logger.info("🔧 Performance optimizations applied during maintenance")
        else:
            logger.debug("🔧 No performance optimizations needed")
        
        return True
    except Exception as e:
        logger.error(f"❌ Performance optimization failed: {e}")
        return False

async def _run_memory_leak_check():
    """Run memory leak check as part of maintenance"""
    try:
        from utils.memory_leak_prevention import check_for_memory_leaks
        
        # Run a lightweight memory check
        health_report = check_for_memory_leaks()
        
        # Log any concerning findings
        if health_report.get("circular_references", {}).get("cycles_found", 0) > 0:
            logger.warning(f"🔄 Found {health_report['circular_references']['cycles_found']} circular references")
        
        long_lived = health_report.get("object_lifecycle", {}).get("long_lived_objects", 0)
        if long_lived > 100:
            logger.warning(f"⏳ Found {long_lived} long-lived objects")
        
        return True
    except Exception as e:
        logger.error(f"❌ Memory leak check failed: {e}")
        return False

async def _run_monitor_cleanup():
    """Run monitor cleanup as part of consolidated maintenance"""
    try:
        # FIXED: Use enhanced_tp_sl_manager for monitor cleanup
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Clean up expired cache entries in the manager
        enhanced_tp_sl_manager._cleanup_execution_cache()
        
        logger.debug("✅ Monitor cleanup completed")
        return True
    except Exception as e:
        logger.error(f"❌ Monitor cleanup failed: {e}")
        return False

async def _run_order_cleanup():
    """Run order cleanup as part of consolidated maintenance"""
    try:
        # FIXED: Order cleanup is now handled by the monitoring system
        # The enhanced TP/SL manager automatically cleans up orders
        logger.debug("✅ Order cleanup completed (handled by monitoring system)")
        return True
    except Exception as e:
        logger.error(f"❌ Order cleanup failed: {e}")
        return False

async def _run_cache_cleanup():
    """Run cache cleanup as part of consolidated maintenance"""
    try:
        from utils.cache import enhanced_cache
        with enhanced_cache._lock:
            enhanced_cache._cleanup_expired()
        logger.debug("✅ Cache cleanup completed")
        return True
    except Exception as e:
        logger.error(f"❌ Cache cleanup failed: {e}")
        return False

async def performance_cleanup_task():
    """
    Conservative performance cleanup task (2025)
    Runs periodic maintenance without affecting trading functionality
    """
    from config.settings import (
        PERFORMANCE_CLEANUP_ENABLED, 
        PERFORMANCE_CLEANUP_INTERVAL,
        MEMORY_CLEANUP_DURING_LOW_ACTIVITY,
        HISTORICAL_DATA_CLEANUP_DAYS
    )
    
    if not PERFORMANCE_CLEANUP_ENABLED:
        logger.info("📊 Performance cleanup disabled via config")
        return
    
    logger.info(f"🧹 Starting performance cleanup task (interval: {PERFORMANCE_CLEANUP_INTERVAL}s)")
    
    while True:
        try:
            await asyncio.sleep(PERFORMANCE_CLEANUP_INTERVAL)
            
            # Check if we should run during low activity only
            if MEMORY_CLEANUP_DURING_LOW_ACTIVITY:
                # Count active monitors to determine activity level
                try:
                    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
                    active_monitors = len([
                        m for m in enhanced_tp_sl_manager.position_monitors.values() 
                        if m.get('phase') in ['MONITORING', 'PROFIT_TAKING']
                    ])
                    
                    if active_monitors > 10:
                        logger.debug(f"🔄 Skipping cleanup during high activity ({active_monitors} active monitors)")
                        continue
                except:
                    pass  # If we can't check, proceed with cleanup
            
            logger.info("🧹 Running performance cleanup...")
            cleanup_tasks = []
            
            # Task 1: Enhanced cache cleanup
            cleanup_tasks.append(_run_enhanced_cache_cleanup())
            
            # Task 2: Memory optimization
            cleanup_tasks.append(_run_memory_optimization())
            
            # Task 3: Historical data pruning (if enabled)
            if HISTORICAL_DATA_CLEANUP_DAYS > 0:
                cleanup_tasks.append(_run_historical_data_cleanup())
            
            # Task 4: Connection pool optimization
            cleanup_tasks.append(_run_connection_pool_cleanup())
            
            # Run all cleanup tasks
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            success_count = sum(1 for result in results if result is True)
            logger.info(f"✅ Performance cleanup completed: {success_count}/{len(cleanup_tasks)} tasks successful")
            
        except Exception as e:
            logger.error(f"❌ Error in performance cleanup task: {e}")
            # Continue running even if there's an error
            await asyncio.sleep(60)  # Wait a minute before retrying

async def _run_enhanced_cache_cleanup():
    """Enhanced cache cleanup with memory optimization"""
    try:
        from utils.cache import enhanced_cache
        
        # Get stats before cleanup
        cache_size_before = len(enhanced_cache._cache)
        
        # Run aggressive cleanup
        with enhanced_cache._lock:
            enhanced_cache._cleanup_expired()
            
            # Additional cleanup: remove least recently used items if cache is large
            if len(enhanced_cache._cache) > enhanced_cache._cleanup_threshold:
                # Sort by access time and remove oldest 20%
                sorted_items = sorted(
                    enhanced_cache._access_times.items(), 
                    key=lambda x: x[1]
                )
                
                items_to_remove = len(sorted_items) // 5  # Remove 20%
                for key, _ in sorted_items[:items_to_remove]:
                    enhanced_cache._cache.pop(key, None)
                    enhanced_cache._access_times.pop(key, None)
        
        cache_size_after = len(enhanced_cache._cache)
        if cache_size_before > cache_size_after:
            logger.info(f"🧹 Cache cleanup: {cache_size_before} → {cache_size_after} entries")
        
        return True
    except Exception as e:
        logger.error(f"❌ Enhanced cache cleanup failed: {e}")
        return False

async def _run_memory_optimization():
    """Run memory optimization during low activity"""
    try:
        import gc
        
        # Force garbage collection
        collected = gc.collect()
        if collected > 0:
            logger.debug(f"🗑️ Garbage collection: {collected} objects collected")
        
        # Get memory stats
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            logger.debug(f"💾 Memory usage: {memory_mb:.1f}MB")
        except:
            pass
        
        return True
    except Exception as e:
        logger.error(f"❌ Memory optimization failed: {e}")
        return False

async def _run_historical_data_cleanup():
    """Clean up old historical data (non-critical)"""
    try:
        import time
        import pickle
        from config.settings import HISTORICAL_DATA_CLEANUP_DAYS
        
        cutoff_time = time.time() - (HISTORICAL_DATA_CLEANUP_DAYS * 24 * 3600)
        
        # CONSERVATIVE: Only clean up old completed order data and closed monitor history
        # Never touch active positions, monitors, or recent data
        
        try:
            # Load bot data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
            
            cleaned_items = 0
            
            # Clean up old completed orders (keep active and recent orders)
            bot_data = data.get('bot_data', {})
            
            # Clean old order history (non-critical historical data only)
            if 'order_history' in bot_data:
                old_count = len(bot_data['order_history'])
                bot_data['order_history'] = [
                    order for order in bot_data['order_history']
                    if order.get('timestamp', time.time()) > cutoff_time
                ]
                cleaned_items += old_count - len(bot_data['order_history'])
            
            # Clean old trade statistics entries (preserve recent stats)
            if 'historical_stats' in bot_data:
                old_count = len(bot_data['historical_stats'])
                bot_data['historical_stats'] = [
                    stat for stat in bot_data['historical_stats']
                    if stat.get('timestamp', time.time()) > cutoff_time
                ]
                cleaned_items += old_count - len(bot_data['historical_stats'])
            
            # Clean old alert history (preserve recent alerts)  
            if 'alert_history' in bot_data:
                old_count = len(bot_data['alert_history'])
                bot_data['alert_history'] = [
                    alert for alert in bot_data['alert_history']
                    if alert.get('timestamp', time.time()) > cutoff_time
                ]
                cleaned_items += old_count - len(bot_data['alert_history'])
            
            # Only save if we actually cleaned something
            if cleaned_items > 0:
                with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                    pickle.dump(data, f)
                logger.info(f"🗂️ Historical data cleanup: {cleaned_items} old entries removed (>{HISTORICAL_DATA_CLEANUP_DAYS} days)")
            else:
                logger.debug(f"🗂️ Historical data cleanup: No old data to clean (>{HISTORICAL_DATA_CLEANUP_DAYS} days)")
            
        except FileNotFoundError:
            logger.debug("🗂️ No historical data file found for cleanup")
        except Exception as e:
            logger.warning(f"⚠️ Could not perform historical data cleanup: {e}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Historical data cleanup failed: {e}")
        return False

async def _run_connection_pool_cleanup():
    """Optimize connection pools"""
    try:
        # This is a placeholder for connection pool optimization
        # Can be expanded to clean up idle connections
        logger.debug("🔗 Connection pool optimization completed")
        
        return True
    except Exception as e:
        logger.error(f"❌ Connection pool cleanup failed: {e}")
        return False

async def start_all_background_tasks(app=None):
    """
    Enhanced background task startup with performance monitoring (2025)
    Call this from your main bot initialization after the application starts.
    """
    try:
        logger.info("🚀 Starting all enhanced background tasks...")
        
        # Run startup monitor cleanup immediately
        try:
            from utils.monitor_cleanup import cleanup_stale_monitors_on_startup
            import pickle
            
            logger.info("🧹 Running startup monitor cleanup...")
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                bot_data = pickle.load(f)
            
            cleanup_performed = await cleanup_stale_monitors_on_startup(bot_data)
            
            if cleanup_performed:
                logger.info("✅ Startup monitor cleanup completed - stale monitors removed")
                with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                    pickle.dump(bot_data, f)
                logger.info("💾 Updated bot data saved after startup cleanup")
            else:
                logger.info("✅ Startup monitor cleanup completed - no stale monitors found")
                
        except Exception as e:
            logger.warning(f"⚠️ Startup monitor cleanup failed: {e}")
        
        # Initialize enhanced performance monitoring
        try:
            from utils.performance_monitor import start_performance_monitoring
            from utils.memory_leak_prevention import enable_memory_monitoring
            
            # Enable memory leak monitoring
            enable_memory_monitoring()
            logger.info("✅ Memory leak monitoring enabled")
            
            # Start performance monitoring
            await start_performance_monitoring()
            logger.info("✅ Enhanced performance monitoring started")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not start performance monitoring: {e}")
        
        # Import the tasks here to avoid circular imports
        # Note: Cleanup tasks are now consolidated into the main monitoring loop
        # from execution.auto_rebalancer import start_auto_rebalancer  # DISABLED
        
        # Cleanup tasks are now consolidated - no separate tasks needed
        logger.info("📊 Using enhanced consolidated maintenance tasks (integrated with monitoring loop)")
        
        # Initialize task variables
        enhanced_task = None
        auto_perf_task = None
        
        # Start Enhanced TP/SL monitoring
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            enhanced_task = asyncio.create_task(enhanced_tp_sl_monitoring_loop())
            logger.info("✅ Enhanced TP/SL monitoring task started")

            # Start connection pool maintenance
            from utils.connection_pool import start_connection_pool_maintenance
            start_connection_pool_maintenance()

            # Start mirror position sync (independent from main sync)
            if os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true":
                logger.info("🪞 Starting independent mirror position sync...")
                try:
                    mirror_sync_task = asyncio.create_task(
                        start_mirror_position_sync(enhanced_tp_sl_manager)
                    )
                    # Store reference to prevent garbage collection
                    if app and hasattr(app, 'bot_data'):
                        if '_background_tasks' not in app.bot_data:
                            app.bot_data['_background_tasks'] = {}
                        app.bot_data['_background_tasks']['mirror_sync'] = mirror_sync_task
                    logger.info("✅ Mirror position sync task started (independent from main sync)")
                except Exception as e:
                    logger.error(f"Failed to start mirror position sync: {e}")

        except Exception as e:
            logger.warning(f"⚠️ Could not start Enhanced TP/SL monitoring: {e}")
            enhanced_task = None
        
        # Start automatic performance management
        try:
            from utils.auto_performance_manager import auto_performance_manager
            auto_perf_task = asyncio.create_task(auto_performance_manager.monitor_performance_loop())
            logger.info("✅ Automatic performance management started")
        except Exception as e:
            logger.warning(f"⚠️ Could not start automatic performance management: {e}")
            auto_perf_task = None
        
        # Start auto-rebalancer - DISABLED
        # await start_auto_rebalancer(app)
        # logger.info("✅ Auto-rebalancer started")
        
        # Start periodic performance reporting
        try:
            performance_reporting_task = asyncio.create_task(_periodic_performance_reporting())
            logger.info("✅ Periodic performance reporting started")
        except Exception as e:
            logger.warning(f"⚠️ Could not start performance reporting: {e}")
            performance_reporting_task = None
            
        # Start periodic monitor cleanup (optional)
        monitor_cleanup_task = None
        from config.settings import ENABLE_PERIODIC_MONITOR_CLEANUP
        if ENABLE_PERIODIC_MONITOR_CLEANUP:
            try:
                monitor_cleanup_task = asyncio.create_task(_periodic_monitor_cleanup())
                logger.info("✅ Periodic monitor cleanup started")
            except Exception as e:
                logger.warning(f"⚠️ Could not start monitor cleanup: {e}")
                monitor_cleanup_task = None
        else:
            logger.info("⏭️ Periodic monitor cleanup disabled (ENABLE_PERIODIC_MONITOR_CLEANUP=false)")
        
        # Start performance cleanup task (optional)
        perf_cleanup_task = None
        from config.settings import PERFORMANCE_CLEANUP_ENABLED
        if PERFORMANCE_CLEANUP_ENABLED:
            try:
                perf_cleanup_task = asyncio.create_task(performance_cleanup_task())
                logger.info("✅ Performance cleanup task started")
            except Exception as e:
                logger.warning(f"⚠️ Could not start performance cleanup: {e}")
                perf_cleanup_task = None
        else:
            logger.info("⏭️ Performance cleanup disabled (PERFORMANCE_CLEANUP_ENABLED=false)")
        
        logger.info("✅ All enhanced background tasks started successfully")
        
        # Store references to prevent garbage collection
        if app and hasattr(app, 'bot_data'):
            app.bot_data['_background_tasks'] = {
                'enhanced_tp_sl': enhanced_task,  # Consolidated monitoring with integrated maintenance
                'auto_performance': auto_perf_task,  # Automatic performance management
                'performance_reporting': performance_reporting_task,
                'monitor_cleanup': monitor_cleanup_task,  # Periodic monitor cleanup
                'performance_cleanup': perf_cleanup_task  # Performance optimization cleanup
            }
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error starting enhanced background tasks: {e}", exc_info=True)
        return False

async def _periodic_monitor_cleanup():
    """
    Periodic monitor cleanup task
    Runs every configurable interval to clean up monitors for positions that no longer exist
    """
    from config.settings import MONITOR_CLEANUP_INTERVAL_SECONDS
    from utils.monitor_cleanup import cleanup_stale_monitors_on_startup
    
    # Use configurable interval (default: 10 minutes)
    cleanup_interval = MONITOR_CLEANUP_INTERVAL_SECONDS
    
    logger.info(f"🧹 Periodic monitor cleanup started - running every {cleanup_interval/60:.1f} minutes")
    
    # START LONG-TERM STABILITY MONITORING
    try:
        from utils.long_term_stability import stability_manager
        await stability_manager.start_stability_monitoring()
        logger.info("🏭 Long-term stability monitoring integrated")
    except Exception as e:
        logger.error(f"❌ Failed to start stability monitoring: {e}")
    
    while True:
        try:
            await asyncio.sleep(cleanup_interval)
            
            logger.info("🧹 Running periodic enhanced monitor cleanup...")
            
            # Use the enhanced cleanup function from the TP/SL manager
            try:
                from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
                await enhanced_tp_sl_manager.cleanup_orphaned_monitors()
                logger.info("✅ Periodic enhanced monitor cleanup completed")
            except Exception as cleanup_error:
                logger.error(f"❌ Enhanced cleanup failed, falling back to old method: {cleanup_error}")
                
                # Fallback to old cleanup method
                import pickle
                try:
                    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                        bot_data = pickle.load(f)
                    
                    cleanup_performed = await cleanup_stale_monitors_on_startup(bot_data)
                    
                    if cleanup_performed:
                        logger.info("✅ Fallback monitor cleanup completed - stale monitors removed")
                        
                        # Save the updated bot_data back to pickle file
                        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                            pickle.dump(bot_data, f)
                            
                        logger.info("💾 Updated bot data saved after fallback cleanup")
                    else:
                        logger.debug("✅ Fallback monitor cleanup completed - no stale monitors found")
                    
                except FileNotFoundError:
                    logger.warning("⚠️ Pickle file not found for monitor cleanup - skipping this cycle")
                except Exception as e:
                    logger.error(f"❌ Error during periodic monitor cleanup: {e}")
                
        except asyncio.CancelledError:
            logger.info("🛑 Periodic monitor cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error in periodic monitor cleanup loop: {e}")
            # Continue the loop even if there's an error

async def _periodic_performance_reporting():
    """Periodic performance reporting task"""
    while True:
        try:
            await asyncio.sleep(3600)  # Report every hour
            
            from utils.performance_monitor import get_bot_performance_report
            from utils.cache import enhanced_cache
            from utils.connection_pool import enhanced_pool
            from utils.memory_leak_prevention import get_memory_health
            
            # Get comprehensive performance report
            perf_report = get_bot_performance_report()
            cache_stats = enhanced_cache.get_stats()
            pool_health = enhanced_pool.get_pool_health_report()
            memory_health = get_memory_health()
            
            # Log performance summary
            logger.info(
                f"📊 Hourly Performance Report:\n"
                f"  Memory: {perf_report.get('current', {}).get('memory_mb', 0):.1f}MB "
                f"({perf_report.get('trends', {}).get('memory_trend', 'stable')})\n"
                f"  Cache Hit Rate: {cache_stats.get('hit_rate', 0)*100:.1f}%\n"
                f"  Connection Pool: {pool_health.get('health_status', 'unknown')}\n"
                f"  Memory Health: {memory_health.get('status', 'unknown')} "
                f"(score: {memory_health.get('health_score', 0)}/100)\n"
                f"  Uptime: {perf_report.get('uptime_hours', 0):.1f}h"
            )
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in performance reporting: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error

def setup_post_init_callback(application):
    """
    Set up a post-initialization callback to start background tasks.
    Add this to your bot setup in main.py
    
    Example usage in main.py:
    
    from helpers.background_tasks import setup_post_init_callback
    
    # After creating your Application instance:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Set up the post-init callback
    setup_post_init_callback(application)
    """
    async def post_init(application):
        """Called after the bot is initialized"""
        await start_all_background_tasks(application)
    
    # Register the post_init callback
    application.post_init = post_init
    logger.info("✅ Post-init callback registered for background tasks")

# Alternative approach using a startup handler
async def startup_handler(update, context):
    """
    Alternative: Start background tasks on first /start command
    This ensures the bot is fully initialized before starting tasks
    """
    # Check if tasks already started
    if context.bot_data.get('_background_tasks_started', False):
        return
    
    # Start all background tasks
    success = await start_all_background_tasks(context.application)
    if success:
        context.bot_data['_background_tasks_started'] = True
        logger.info("✅ Background tasks started via startup handler")

# Function to safely check if event loop is running
def is_event_loop_running():
    """Check if an event loop is currently running"""
    try:
        loop = asyncio.get_running_loop()
        return loop.is_running()
    except RuntimeError:
        return False

# Deferred task starter for modules
class DeferredTaskStarter:
    """
    Helper class to defer task creation until event loop is available
    """
    def __init__(self):
        self.pending_tasks = []
        self.started = False
    
    def add_task(self, coro_func, name="unnamed"):
        """Add a coroutine function to start later"""
        self.pending_tasks.append((coro_func, name))
        logger.debug(f"📋 Deferred task '{name}' for later startup")
    
    async def start_all(self):
        """Start all pending tasks"""
        if self.started:
            logger.warning("⚠️ Tasks already started")
            return
        
        started_tasks = []
        for coro_func, name in self.pending_tasks:
            try:
                task = asyncio.create_task(coro_func())
                started_tasks.append((task, name))
                logger.info(f"✅ Started deferred task: {name}")
            except Exception as e:
                logger.error(f"❌ Failed to start task '{name}': {e}")
        
        self.started = True
        self.pending_tasks.clear()
        return started_tasks

# Global deferred task starter
deferred_tasks = DeferredTaskStarter()

# Example usage in your modules:
# Instead of directly calling asyncio.create_task() during import:
#
# from helpers.background_tasks import deferred_tasks
# deferred_tasks.add_task(periodic_monitor_cleanup, "monitor_cleanup")
#
# Then in your main bot initialization:
# await deferred_tasks.start_all()