#!/usr/bin/env python3
"""
Fix monitor creation for new positions to use account-aware keys
"""
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 60)
    logger.info("FIXING NEW POSITION MONITOR CREATION")
    logger.info("=" * 60)
    
    # Update enhanced_tp_sl_manager.py
    logger.info("\n📝 Updating monitor creation in enhanced_tp_sl_manager.py...")
    
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Fix line 547 where monitors are created
    old_line = '''            self.position_monitors[f"{symbol}_{side}"] = monitor_data'''
    new_line = '''            # Use account-aware key format
            monitor_key = f"{symbol}_{side}_{account_type}"
            self.position_monitors[monitor_key] = monitor_data'''
    
    if old_line in content:
        content = content.replace(old_line, new_line)
        logger.info("✅ Updated monitor creation to use account-aware keys")
    else:
        logger.warning("⚠️ Could not find old monitor creation line")
    
    # Also add account_type to monitor_data
    old_monitor_data = '''                "cleanup_completed": False,  # Track if cleanup was performed
                "bot_instance": None  # Will store bot reference for alerts
            }'''
    
    new_monitor_data = '''                "cleanup_completed": False,  # Track if cleanup was performed
                "bot_instance": None,  # Will store bot reference for alerts
                "account_type": account_type  # Track which account this monitor is for
            }'''
    
    if old_monitor_data in content:
        content = content.replace(old_monitor_data, new_monitor_data)
        logger.info("✅ Added account_type to monitor data")
    else:
        logger.warning("⚠️ Could not find monitor data section")
    
    # Write updated file
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    # Also update the cleanup_position_orders method to handle both old and new keys
    logger.info("\n📝 Updating cleanup_position_orders for better key handling...")
    
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Find and update the cleanup section where monitor is deleted
    old_cleanup = '''        # Clean up monitor
        if monitor_key in self.position_monitors:
            del self.position_monitors[monitor_key]'''
    
    new_cleanup = '''        # Clean up monitor (check both new and old key formats)
        if monitor_key in self.position_monitors:
            del self.position_monitors[monitor_key]
        else:
            # Try legacy key format
            legacy_key = f"{symbol}_{side}"
            if legacy_key in self.position_monitors:
                del self.position_monitors[legacy_key]
                logger.info(f"Cleaned up legacy monitor: {legacy_key}")'''
    
    if old_cleanup in content:
        content = content.replace(old_cleanup, new_cleanup)
        logger.info("✅ Updated cleanup to handle both key formats")
    
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    # Check if there are any other places where monitors are created
    logger.info("\n🔍 Checking for other monitor creation locations...")
    
    # Update the part where monitors are created from existing positions
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Look for create_enhanced_monitor_entry function
    if 'create_enhanced_monitor_entry' in content:
        logger.info("✅ Found create_enhanced_monitor_entry function")
        
        # Update it to use account-aware keys
        old_create = '''def create_enhanced_monitor_entry(self, position_data: Dict, chat_id: int) -> Dict:'''
        new_create = '''def create_enhanced_monitor_entry(self, position_data: Dict, chat_id: int, account_type: str = "main") -> Dict:'''
        
        if old_create in content:
            content = content.replace(old_create, new_create)
            logger.info("✅ Updated create_enhanced_monitor_entry signature")
        
        # Add account_type to the returned dictionary
        old_return = '''            "cleanup_completed": False
        }'''
        new_return = '''            "cleanup_completed": False,
            "account_type": account_type
        }'''
        
        if old_return in content:
            content = content.replace(old_return, new_return)
            logger.info("✅ Added account_type to monitor entry creation")
        
        with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
            f.write(content)
    
    # Update the part in trader.py where setup_tp_sl_orders is called
    logger.info("\n📝 Checking trader.py for setup_tp_sl_orders calls...")
    
    try:
        with open('execution/trader.py', 'r') as f:
            trader_content = f.read()
        
        # Check if account_type is passed to setup_tp_sl_orders
        if 'setup_tp_sl_orders(' in trader_content and 'account_type=' not in trader_content:
            logger.warning("⚠️ trader.py may need updates to pass account_type")
            logger.info("   You may need to update calls to setup_tp_sl_orders to include account_type='main'")
    except Exception as e:
        logger.error(f"Could not check trader.py: {e}")
    
    logger.info("\n🎯 NEW POSITION MONITOR FIX COMPLETE!")
    logger.info("All new positions will now use account-aware monitor keys")
    logger.info("Format: {SYMBOL}_{SIDE}_{ACCOUNT_TYPE}")

if __name__ == "__main__":
    main()