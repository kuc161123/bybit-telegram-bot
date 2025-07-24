#!/usr/bin/env python3
"""
Hot patch chat IDs in running bot's memory.
This modifies the bot's in-memory state directly before persisting.
"""

import asyncio
import logging
from pathlib import Path
import pickle
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def hot_patch_chat_ids():
    """Hot patch chat IDs in the running bot's memory."""
    try:
        # Import shared state to get the running application
        from shared.state import get_application
        
        # Get the application instance
        app = get_application()
        if not app:
            logger.error("No application instance found. Is the bot running?")
            return False
            
        # Access bot_data through the application context
        bot_data = app.bot_data
        
        # Get enhanced TP/SL monitors
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Monitors that need chat_id update
        monitors_to_update = [
            'AUCTIONUSDT_Buy_main',
            'AUCTIONUSDT_Buy_mirror',
            'CRVUSDT_Buy_mirror',
            'SEIUSDT_Buy_mirror',
            'ARBUSDT_Buy_mirror'
        ]
        
        correct_chat_id = 5634913742
        updated_count = 0
        
        # Update chat_ids in memory
        for monitor_key in monitors_to_update:
            if monitor_key in enhanced_monitors:
                old_chat_id = enhanced_monitors[monitor_key].get('chat_id', 'None')
                enhanced_monitors[monitor_key]['chat_id'] = correct_chat_id
                logger.info(f"Updated {monitor_key}: chat_id {old_chat_id} -> {correct_chat_id}")
                updated_count += 1
            else:
                logger.warning(f"Monitor {monitor_key} not found in enhanced_tp_sl_monitors")
        
        logger.info(f"Updated {updated_count} monitors in memory")
        
        # Force the bot to save its state using its own persistence mechanism
        if hasattr(app, 'persistence') and app.persistence:
            logger.info("Triggering bot's persistence save...")
            await app.persistence.flush()
            logger.info("Bot state saved through persistence mechanism")
        else:
            logger.warning("No persistence mechanism found, saving directly to pickle")
            # Fallback: Save directly to pickle file
            pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            
            # Create backup first
            backup_file = f"{pickle_file}.backup_hotpatch_{int(datetime.now().timestamp())}"
            import shutil
            shutil.copy2(pickle_file, backup_file)
            logger.info(f"Created backup: {backup_file}")
            
            # Read current pickle data
            with open(pickle_file, 'rb') as f:
                data = pickle.load(f)
            
            # Update the data
            if 'bot_data' in data:
                data['bot_data']['enhanced_tp_sl_monitors'] = enhanced_monitors
                
                # Write back
                with open(pickle_file, 'wb') as f:
                    pickle.dump(data, f)
                logger.info("Pickle file updated directly")
        
        # Create reload signals to ensure monitors pick up changes
        logger.info("Creating reload signals...")
        
        # Standard reload signal
        reload_signal = Path('force_reload.trigger')
        reload_signal.touch()
        logger.info("Created force_reload.trigger")
        
        # Monitor-specific reload signal
        monitor_signal = Path('reload_monitors.signal')
        monitor_signal.touch()
        logger.info("Created reload_monitors.signal")
        
        # Enhanced monitor reload signal
        enhanced_signal = Path('.reload_enhanced_monitors')
        enhanced_signal.touch()
        logger.info("Created .reload_enhanced_monitors")
        
        # Verify the changes in bot_data
        logger.info("\nVerifying in-memory changes:")
        for monitor_key in monitors_to_update:
            if monitor_key in enhanced_monitors:
                chat_id = enhanced_monitors[monitor_key].get('chat_id', 'None')
                logger.info(f"{monitor_key}: chat_id = {chat_id}")
        
        logger.info("\nHot patch completed successfully!")
        logger.info("The running monitors should pick up these changes on their next cycle.")
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import shared state: {e}")
        logger.error("Make sure the bot is running and shared.state is properly initialized")
        return False
    except Exception as e:
        logger.error(f"Error during hot patch: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_pickle_update():
    """Verify the changes were persisted to the pickle file."""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        logger.info("\nVerifying pickle file:")
        monitors_to_check = [
            'AUCTIONUSDT_Buy_main',
            'AUCTIONUSDT_Buy_mirror',
            'CRVUSDT_Buy_mirror',
            'SEIUSDT_Buy_mirror',
            'ARBUSDT_Buy_mirror'
        ]
        
        for monitor_key in monitors_to_check:
            if monitor_key in enhanced_monitors:
                chat_id = enhanced_monitors[monitor_key].get('chat_id', 'None')
                status = "✓" if chat_id == 5634913742 else "✗"
                logger.info(f"{status} {monitor_key}: chat_id = {chat_id}")
            else:
                logger.warning(f"✗ {monitor_key}: Not found in pickle")
                
    except Exception as e:
        logger.error(f"Error verifying pickle: {e}")

if __name__ == "__main__":
    logger.info("Starting hot patch for chat IDs...")
    logger.info("This will modify the running bot's memory directly")
    
    # Run the async hot patch
    success = asyncio.run(hot_patch_chat_ids())
    
    if success:
        # Verify the pickle was updated
        verify_pickle_update()
        
        logger.info("\n" + "="*50)
        logger.info("HOT PATCH COMPLETE")
        logger.info("The bot's in-memory state has been updated.")
        logger.info("Monitors should use the correct chat_id on their next check.")
        logger.info("No bot restart required!")
        logger.info("="*50)
    else:
        logger.error("\nHot patch failed. Please check the errors above.")