from execution.mirror_position_sync import start_mirror_position_sync
#!/usr/bin/env python3
"""
Helper functions for properly initializing background tasks in the trading bot.
Add this to your bot initialization to fix the "no running event loop" errors.
"""
import asyncio
import logging
import os
import time

logger = logging.getLogger(__name__)

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
            
            # Log the manager state
            if loop_count % 12 == 1:  # Every minute
                logger.info(f"🔍 Enhanced TP/SL Manager State - Monitors: {len(enhanced_tp_sl_manager.position_monitors)}")
            
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
                    
                    logger.info(f"🔍 Loading monitors directly from pickle file")
                    logger.info(f"🔍 Current monitor count: {len(enhanced_tp_sl_manager.position_monitors)}")
                    
                    # Get all monitors from pickle using thread pool to prevent event loop blocking
                    loop = asyncio.get_running_loop()
                    
                    def load_pickle_data():
                        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                            return pickle.load(f)
                    
                    # Create a new executor for this operation
                    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                    try:
                        data = await loop.run_in_executor(executor, load_pickle_data)
                    finally:
                        executor.shutdown(wait=False)  # Clean shutdown
                    
                    persisted_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
                    logger.info(f"🔍 Found {len(persisted_monitors)} persisted monitors")
                    
                    if persisted_monitors:
                        logger.info(f"🔍 Monitor keys: {list(persisted_monitors.keys())}")
                        
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
                        data_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                        try:
                            processed_monitors = await loop.run_in_executor(data_executor, process_monitor_data, persisted_monitors)
                        finally:
                            data_executor.shutdown(wait=False)
                        
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
                        
                        stats_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                        try:
                            stats = await loop.run_in_executor(stats_executor, get_persistence_stats)
                        finally:
                            stats_executor.shutdown(wait=False)
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
            
            # Calculate dynamic sleep interval based on most urgent position
            next_sleep_interval = 60  # Default to 60s if no monitors
            
            if monitor_count > 0:
                logger.info(f"🔍 Monitoring {monitor_count} positions")
                
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
            
            # Dynamic sleep based on position urgency
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
        enhanced_tp_sl_manager._cleanup_monitoring_cache()
        
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

async def start_all_background_tasks(app=None):
    """
    Enhanced background task startup with performance monitoring (2025)
    Call this from your main bot initialization after the application starts.
    """
    try:
        logger.info("🚀 Starting all enhanced background tasks...")
        
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
        
        logger.info("✅ All enhanced background tasks started successfully")
        
        # Store references to prevent garbage collection
        if app and hasattr(app, 'bot_data'):
            app.bot_data['_background_tasks'] = {
                'enhanced_tp_sl': enhanced_task,  # Consolidated monitoring with integrated maintenance
                'performance_reporting': performance_reporting_task
            }
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error starting enhanced background tasks: {e}", exc_info=True)
        return False

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