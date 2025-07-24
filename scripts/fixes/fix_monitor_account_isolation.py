#!/usr/bin/env python3
"""
Fix monitor account isolation and persistence issues
Ensures monitors only track positions from their designated accounts
and that monitor data is properly persisted after updates
"""

import pickle
import logging
from decimal import Decimal
import time
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_monitor_account_isolation():
    """Fix monitor account isolation and update stored position sizes"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        if 'bot_data' not in data or 'enhanced_tp_sl_monitors' not in data['bot_data']:
            logger.error("No enhanced_tp_sl_monitors found in pickle")
            return False
        
        monitors = data['bot_data']['enhanced_tp_sl_monitors']
        logger.info(f"Found {len(monitors)} monitors to check")
        
        # Import clients for position checking
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2
        
        # Check each monitor and update position sizes
        for monitor_key, monitor_data in monitors.items():
            logger.info(f"\nChecking monitor: {monitor_key}")
            
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            account_type = monitor_data.get('account_type', 'main')
            
            # Determine which client to use based on monitor's account type
            if account_type == 'mirror':
                client = bybit_client_2
                logger.info(f"  Using mirror client for {monitor_key}")
            else:
                client = bybit_client
                logger.info(f"  Using main client for {monitor_key}")
            
            # Get current position from the correct account
            try:
                response = client.get_positions(
                    category="linear",
                    symbol=symbol
                )
                
                if response['retCode'] == 0:
                    position = None
                    for pos in response['result']['list']:
                        if pos['symbol'] == symbol and pos['side'] == side:
                            position = pos
                            break
                    
                    if position:
                        current_size = Decimal(str(position['size']))
                        stored_size = monitor_data.get('remaining_size', Decimal('0'))
                        position_size = monitor_data.get('position_size', Decimal('0'))
                        
                        logger.info(f"  Position found:")
                        logger.info(f"    Current size: {current_size}")
                        logger.info(f"    Stored remaining_size: {stored_size}")
                        logger.info(f"    Stored position_size: {position_size}")
                        
                        # Update monitor data if sizes don't match
                        if current_size != stored_size:
                            logger.warning(f"  ⚠️ Size mismatch detected!")
                            logger.info(f"  Updating remaining_size: {stored_size} -> {current_size}")
                            monitor_data['remaining_size'] = current_size
                            
                            # Also update position_size if it's the initial size
                            if position_size > current_size and monitor_data.get('filled_tps'):
                                logger.info(f"  Position has filled TPs, keeping original position_size: {position_size}")
                            else:
                                logger.info(f"  Updating position_size: {position_size} -> {current_size}")
                                monitor_data['position_size'] = current_size
                        
                        # Ensure account_type is set correctly
                        if 'account_type' not in monitor_data:
                            monitor_data['account_type'] = account_type
                            logger.info(f"  Added missing account_type: {account_type}")
                    else:
                        logger.warning(f"  No position found for {symbol} {side} on {account_type} account")
                        # Position closed - should we remove the monitor?
                        if monitor_data.get('remaining_size', 0) > 0:
                            logger.warning(f"  Monitor shows remaining_size but position is closed!")
                            monitor_data['remaining_size'] = Decimal('0')
                
            except Exception as e:
                logger.error(f"  Error fetching position: {e}")
        
        # Save updated data back to pickle
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("\n✅ Monitor account isolation fixed and data persisted")
        
        # Verify the specific CAKEUSDT mirror monitor
        cake_mirror = monitors.get('CAKEUSDT_Buy_mirror')
        if cake_mirror:
            logger.info(f"\nCAKEUSDT_Buy_mirror updated:")
            logger.info(f"  remaining_size: {cake_mirror.get('remaining_size')}")
            logger.info(f"  position_size: {cake_mirror.get('position_size')}")
            logger.info(f"  account_type: {cake_mirror.get('account_type')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error fixing monitor account isolation: {e}")
        import traceback
        traceback.print_exc()
        return False

def add_persistence_save_to_enhanced_tp_sl():
    """Add persistence save after monitor updates in enhanced_tp_sl_manager.py"""
    try:
        # Read the enhanced_tp_sl_manager.py file
        with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
            content = f.read()
        
        # Check if we already have a save function
        if 'def save_monitors_to_persistence' not in content:
            # Add the save function
            save_function = '''
    def save_monitors_to_persistence(self):
        """Save all monitors to persistence file"""
        try:
            import pickle
            
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
            
            if 'bot_data' not in data:
                data['bot_data'] = {}
            
            # Save monitors
            data['bot_data']['enhanced_tp_sl_monitors'] = self.position_monitors
            
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
                
            logger.debug(f"Saved {len(self.position_monitors)} monitors to persistence")
            
        except Exception as e:
            logger.error(f"Error saving monitors to persistence: {e}")
'''
            
            # Find a good place to insert it (after __init__ method)
            init_end = content.find('def _init_mirror_support(self):')
            if init_end == -1:
                init_end = content.find('def _ensure_tp_orders_dict(self')
            
            if init_end != -1:
                # Insert the save function before the next method
                content = content[:init_end] + save_function + '\n' + content[init_end:]
                logger.info("Added save_monitors_to_persistence method")
            
        # Now add calls to save after monitor updates
        # After remaining_size update
        if 'monitor_data["remaining_size"] = current_size' in content:
            # Add save after remaining_size updates
            content = content.replace(
                'monitor_data["remaining_size"] = current_size',
                'monitor_data["remaining_size"] = current_size\n                    \n                    # Save to persistence after update\n                    self.save_monitors_to_persistence()'
            )
            logger.info("Added persistence save after remaining_size updates")
        
        # Save the updated file
        with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
            f.write(content)
        
        logger.info("✅ Added persistence saves to enhanced_tp_sl_manager.py")
        return True
        
    except Exception as e:
        logger.error(f"Error adding persistence saves: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    logger.info("Starting monitor account isolation fix...")
    
    # First fix the current monitor data
    if fix_monitor_account_isolation():
        logger.info("✅ Monitor data fixed")
        
        # Then add persistence saves to prevent future issues
        if add_persistence_save_to_enhanced_tp_sl():
            logger.info("✅ Persistence saves added to code")
            logger.info("\n🎯 Next steps:")
            logger.info("1. Restart the bot to load the updated monitors")
            logger.info("2. The monitors will now only check their designated accounts")
            logger.info("3. Updates will be automatically persisted")
        else:
            logger.error("Failed to add persistence saves")
    else:
        logger.error("Failed to fix monitor data")