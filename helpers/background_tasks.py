#!/usr/bin/env python3
"""
Helper functions for properly initializing background tasks in the trading bot.
Add this to your bot initialization to fix the "no running event loop" errors.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

async def start_all_background_tasks(app=None):
    """
    Start all background tasks after the event loop is running.
    Call this from your main bot initialization after the application starts.
    """
    try:
        logger.info("🚀 Starting all background tasks...")
        
        # Import the tasks here to avoid circular imports
        from execution.monitor import periodic_monitor_cleanup
        from clients.bybit_helpers import periodic_order_cleanup_task
        
        # Start monitor cleanup task
        monitor_task = asyncio.create_task(periodic_monitor_cleanup())
        logger.info("✅ Monitor cleanup task started")
        
        # Start order cleanup task
        order_task = asyncio.create_task(periodic_order_cleanup_task())
        logger.info("✅ Order cleanup task started")
        
        # Add any other background tasks here
        # Example: cache cleanup, protection cleanup, etc.
        
        logger.info("✅ All background tasks started successfully")
        
        # Store references to prevent garbage collection
        if app and hasattr(app, 'bot_data'):
            app.bot_data['_background_tasks'] = {
                'monitor_cleanup': monitor_task,
                'order_cleanup': order_task
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