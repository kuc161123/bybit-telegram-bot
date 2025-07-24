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
                    # Load directly from pickle file
                    import pickle
                    
                    logger.info(f"🔍 Loading monitors directly from pickle file")
                    logger.info(f"🔍 Current monitor count: {len(enhanced_tp_sl_manager.position_monitors)}")
                    
                    # Get all monitors from pickle
                    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                        data = pickle.load(f)
                    
                    persisted_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
                    logger.info(f"🔍 Found {len(persisted_monitors)} persisted monitors")
                    
                    if persisted_monitors:
                        logger.info(f"🔍 Monitor keys: {list(persisted_monitors.keys())}")
                        
                        # Clear existing monitors and load fresh from persistence
                        enhanced_tp_sl_manager.position_monitors.clear()
                        
                        # Sanitize each monitor data to ensure numeric fields are Decimal
                        for monitor_key, monitor_data in persisted_monitors.items():
                            # Only load monitors with proper account suffixes to prevent legacy monitor issues
                            if monitor_key.endswith('_main') or monitor_key.endswith('_mirror'):
                                sanitized_data = enhanced_tp_sl_manager._sanitize_monitor_data(monitor_data)
                                
                                # FIX FOR EXISTING MONITORS: Initialize last_known_size if missing
                                if 'last_known_size' not in sanitized_data or sanitized_data.get('last_known_size', 0) == 0:
                                    remaining_size = sanitized_data.get('remaining_size', 0)
                                    position_size = sanitized_data.get('position_size', 0)
                                    from decimal import Decimal
                                    sanitized_data['last_known_size'] = Decimal(str(remaining_size)) if remaining_size > 0 else Decimal(str(position_size))
                                    logger.info(f"🔧 Fixed last_known_size for {monitor_key}: {sanitized_data['last_known_size']}")
                                
                                # Also ensure phase is set if missing
                                if 'phase' not in sanitized_data:
                                    if sanitized_data.get('tp1_hit', False):
                                        sanitized_data['phase'] = 'PROFIT_TAKING'
                                    elif sanitized_data.get('limit_orders_filled', False):
                                        sanitized_data['phase'] = 'MONITORING'
                                    else:
                                        sanitized_data['phase'] = 'BUILDING'
                                    logger.info(f"🔧 Set phase for {monitor_key}: {sanitized_data['phase']}")
                                
                                enhanced_tp_sl_manager.position_monitors[monitor_key] = sanitized_data
                            else:
                                logger.warning(f"⚠️ Skipping legacy monitor: {monitor_key}")
                        
                        logger.info(f"✅ Loaded {len(enhanced_tp_sl_manager.position_monitors)} monitors from robust persistence")
                        logger.info(f"🔍 Manager now has {len(enhanced_tp_sl_manager.position_monitors)} monitors")
                        
                        # Only sync with positions if NOT force loading (force load keeps all monitors)
                        if not os.path.exists(force_load_signal):
                            # Sync with actual positions to remove orphaned monitors
                            from clients.bybit_helpers import get_all_positions
                            positions = await get_all_positions()
                            # Note: sync_with_positions will remove orphaned monitors but not sync sizes
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
                        
                    # Log persistence stats
                    stats = await robust_persistence.get_stats()
                    logger.info(f"📊 Persistence stats: {stats.get('total_monitors')} monitors, {stats.get('file_size_mb'):.2f}MB file")
                
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
                
                # PERFORMANCE OPTIMIZATION: Smart urgency-based grouping with parallel processing
                urgency_groups = {
                    'critical': [],    # 2s interval - near TP triggers
                    'active': [],      # 5s interval - profit taking
                    'standard': [],    # 12s interval - normal monitoring  
                    'inactive': [],    # 30s interval - mostly complete
                    'idle': []         # 60s interval - no activity
                }
                min_interval = float('inf')
                
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
                            'interval': interval
                        }
                        urgency_groups[urgency_level].append(task_data)
                        
                    except Exception as e:
                        logger.error(f"❌ Error grouping monitor {monitor_key}: {e}")
                
                # PHASE 3 OPTIMIZATION: Priority queue processing with separate critical/maintenance queues
                critical_tasks = []
                standard_tasks = []
                maintenance_tasks = []
                
                # Separate tasks by priority
                for urgency_level, group_monitors in urgency_groups.items():
                    if not group_monitors:
                        continue
                    
                    # Create tasks for this urgency group
                    group_tasks = []
                    for task_data in group_monitors:
                        task = enhanced_tp_sl_manager.monitor_and_adjust_orders(
                            task_data["symbol"], 
                            task_data["side"],
                            task_data["account_type"]
                        )
                        group_tasks.append((task_data["monitor_key"], task, urgency_level))
                    
                    # Sort into priority queues
                    if urgency_level in ['critical', 'active']:
                        critical_tasks.extend(group_tasks)
                    elif urgency_level in ['standard']:
                        standard_tasks.extend(group_tasks)
                    else:  # inactive, idle
                        maintenance_tasks.extend(group_tasks)
                
                total_processed = 0
                start_time = time.time()
                
                # PRIORITY EXECUTION: Process critical tasks first with highest priority
                if critical_tasks:
                    try:
                        critical_task_list = [task for _, task, _ in critical_tasks]
                        critical_results = await asyncio.gather(*critical_task_list, return_exceptions=True)
                        
                        # Process critical results
                        for i, ((monitor_key, _, urgency_level), result) in enumerate(zip(critical_tasks, critical_results)):
                            if isinstance(result, Exception):
                                logger.error(f"🚨 CRITICAL ERROR monitoring {monitor_key} ({urgency_level}): {result}")
                        
                        total_processed += len(critical_tasks)
                        logger.debug(f"🔥 Processed {len(critical_tasks)} CRITICAL priority monitors")
                    except Exception as e:
                        logger.error(f"❌ Error processing critical priority queue: {e}")
                
                # Process standard tasks with normal priority
                if standard_tasks:
                    try:
                        standard_task_list = [task for _, task, _ in standard_tasks]
                        standard_results = await asyncio.gather(*standard_task_list, return_exceptions=True)
                        
                        # Process standard results
                        for i, ((monitor_key, _, urgency_level), result) in enumerate(zip(standard_tasks, standard_results)):
                            if isinstance(result, Exception):
                                logger.error(f"⚠️ Error monitoring {monitor_key} ({urgency_level}): {result}")
                        
                        total_processed += len(standard_tasks)
                        logger.debug(f"⚡ Processed {len(standard_tasks)} STANDARD priority monitors")
                    except Exception as e:
                        logger.error(f"❌ Error processing standard priority queue: {e}")
                
                # Process maintenance tasks with lower priority (can be skipped if time constrained)
                if maintenance_tasks and (time.time() - start_time) < 5:  # Only if we have time
                    try:
                        maintenance_task_list = [task for _, task, _ in maintenance_tasks]
                        maintenance_results = await asyncio.gather(*maintenance_task_list, return_exceptions=True)
                        
                        # Process maintenance results
                        for i, ((monitor_key, _, urgency_level), result) in enumerate(zip(maintenance_tasks, maintenance_results)):
                            if isinstance(result, Exception):
                                logger.debug(f"💤 Error monitoring {monitor_key} ({urgency_level}): {result}")
                        
                        total_processed += len(maintenance_tasks)
                        logger.debug(f"🔧 Processed {len(maintenance_tasks)} MAINTENANCE priority monitors")
                    except Exception as e:
                        logger.debug(f"💤 Error processing maintenance priority queue: {e}")
                elif maintenance_tasks:
                    logger.debug(f"⏭️ Skipped {len(maintenance_tasks)} maintenance tasks due to time constraints")
                
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
    """Consolidated maintenance task that runs periodic cleanup operations"""
    try:
        logger.info("🧹 Running FULL maintenance tasks...")
        
        # Import cleanup functions
        from execution.monitor import periodic_monitor_cleanup
        from clients.bybit_helpers import periodic_order_cleanup_task
        from utils.cache import enhanced_cache
        
        # Run cleanup tasks concurrently for efficiency
        maintenance_tasks = [
            _run_monitor_cleanup(),
            _run_order_cleanup(), 
            _run_cache_cleanup()
        ]
        
        results = await asyncio.gather(*maintenance_tasks, return_exceptions=True)
        
        success_count = sum(1 for result in results if not isinstance(result, Exception))
        logger.info(f"✅ Full maintenance completed: {success_count}/3 tasks successful")
        
    except Exception as e:
        logger.error(f"❌ Error in consolidated maintenance task: {e}")

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
    Start all background tasks after the event loop is running.
    Call this from your main bot initialization after the application starts.
    """
    try:
        logger.info("🚀 Starting all background tasks...")
        
        # Import the tasks here to avoid circular imports
        # Note: Cleanup tasks are now consolidated into the main monitoring loop
        # from execution.auto_rebalancer import start_auto_rebalancer  # DISABLED
        
        # Cleanup tasks are now consolidated - no separate tasks needed
        logger.info("📊 Using consolidated maintenance tasks (integrated with monitoring loop)")
        
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
        
        # Add any other background tasks here
        # Example: cache cleanup, protection cleanup, etc.
        
        logger.info("✅ All background tasks started successfully")
        
        # Store references to prevent garbage collection
        if app and hasattr(app, 'bot_data'):
            app.bot_data['_background_tasks'] = {
                'enhanced_tp_sl': enhanced_task  # Consolidated monitoring with integrated maintenance
            }
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error starting background tasks: {e}", exc_info=True)
        return False

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