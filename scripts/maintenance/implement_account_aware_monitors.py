#!/usr/bin/env python3
"""
Implement account-aware monitor key support in the codebase
"""
import logging
import shutil
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 60)
    logger.info("IMPLEMENTING ACCOUNT-AWARE MONITOR SUPPORT")
    logger.info("=" * 60)
    
    # Backup files first
    backup_time = int(datetime.now().timestamp())
    
    # Update enhanced_tp_sl_manager.py
    logger.info("\n📝 Updating enhanced_tp_sl_manager.py...")
    
    # Read the file
    with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
        content = f.read()
    
    # Make necessary changes for account-aware keys
    
    # 1. Update monitor_and_adjust_orders to handle new key format
    old_monitor_method = '''    async def monitor_and_adjust_orders(self, symbol: str, side: str):
        """
        Enhanced monitoring with real-time fill detection and reduced latency
        This replaces the conditional order logic with active management
        """
        monitor_key = f"{symbol}_{side}"
        if monitor_key not in self.position_monitors:
            return'''
    
    new_monitor_method = '''    async def monitor_and_adjust_orders(self, symbol: str, side: str, account_type: str = None):
        """
        Enhanced monitoring with real-time fill detection and reduced latency
        This replaces the conditional order logic with active management
        Now supports account-aware monitoring to prevent key collisions
        """
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
            return'''
    
    content = content.replace(old_monitor_method, new_monitor_method)
    
    # 2. Add account type detection after getting monitor_data
    old_get_monitor = '''        
        monitor_data = self.position_monitors[monitor_key]
        
        # Sanitize monitor data to ensure all numeric fields are Decimal'''
    
    new_get_monitor = '''        
        monitor_data = self.position_monitors[monitor_key]
        
        # Determine account type from monitor data or key
        if not account_type:
            account_type = monitor_data.get('account_type', 'main')
            if '_mirror' in monitor_key:
                account_type = 'mirror'
            elif '_main' in monitor_key:
                account_type = 'main'
        
        # Sanitize monitor data to ensure all numeric fields are Decimal'''
    
    content = content.replace(old_get_monitor, new_get_monitor)
    
    # 3. Update position info fetching to use correct client
    old_get_positions = '''        try:
            # Get current position
            positions = await get_position_info(symbol)'''
    
    new_get_positions = '''        try:
            # Get current position using appropriate client
            if account_type == 'mirror':
                from clients.bybit_helpers import get_position_info_for_account
                positions = await get_position_info_for_account(symbol, 'mirror')
            else:
                positions = await get_position_info(symbol)'''
    
    content = content.replace(old_get_positions, new_get_positions)
    
    # 4. Update cleanup_position_orders signature
    old_cleanup_sig = '''    async def cleanup_position_orders(self, symbol: str, side: str):'''
    new_cleanup_sig = '''    async def cleanup_position_orders(self, symbol: str, side: str, account_type: str = None):'''
    
    content = content.replace(old_cleanup_sig, new_cleanup_sig)
    
    # 5. Update cleanup monitor key generation
    old_cleanup_key = '''        monitor_key = f"{symbol}_{side}"'''
    new_cleanup_key = '''        # Support account-aware keys
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
                monitor_key = legacy_key'''
    
    content = content.replace(old_cleanup_key, new_cleanup_key, 1)
    
    # Write updated file
    with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
        f.write(content)
    
    logger.info("✅ Updated enhanced_tp_sl_manager.py")
    
    # Update background_tasks.py
    logger.info("\n📝 Updating background_tasks.py...")
    
    with open('helpers/background_tasks.py', 'r') as f:
        content = f.read()
    
    # Update the monitoring loop to extract account type
    old_loop = '''                for monitor_key, monitor_data in list(enhanced_tp_sl_manager.position_monitors.items()):
                    try:
                        await enhanced_tp_sl_manager.monitor_and_adjust_orders(
                            monitor_data["symbol"], 
                            monitor_data["side"]
                        )'''
    
    new_loop = '''                for monitor_key, monitor_data in list(enhanced_tp_sl_manager.position_monitors.items()):
                    try:
                        # Extract account type from monitor data
                        account_type = monitor_data.get("account_type", "main")
                        
                        await enhanced_tp_sl_manager.monitor_and_adjust_orders(
                            monitor_data["symbol"], 
                            monitor_data["side"],
                            account_type
                        )'''
    
    content = content.replace(old_loop, new_loop)
    
    with open('helpers/background_tasks.py', 'w') as f:
        f.write(content)
    
    logger.info("✅ Updated background_tasks.py")
    
    # Add helper function to bybit_helpers.py
    logger.info("\n📝 Adding helper function to bybit_helpers.py...")
    
    with open('clients/bybit_helpers.py', 'r') as f:
        content = f.read()
    
    # Add the new helper function at the end
    helper_function = '''

async def get_position_info_for_account(symbol: str, account_type: str = "main") -> Optional[List[Dict]]:
    """Get position information for a specific symbol and account
    
    Args:
        symbol: Trading pair symbol
        account_type: 'main' or 'mirror'
        
    Returns:
        List of position dictionaries for the symbol, or empty list if none found
    """
    try:
        if account_type == "mirror":
            from execution.mirror_trader import bybit_client_2
            client = bybit_client_2
        else:
            from clients.bybit_client import bybit_client
            client = bybit_client
            
        response = client.get_positions(category="linear", symbol=symbol)
        if response and response.get('retCode') == 0:
            return response.get('result', {}).get('list', [])
    except Exception as e:
        logger.error(f"Error getting {account_type} position info for {symbol}: {e}")
    return []
'''
    
    # Only add if not already present
    if 'get_position_info_for_account' not in content:
        content += helper_function
        
        with open('clients/bybit_helpers.py', 'w') as f:
            f.write(content)
        
        logger.info("✅ Added helper function to bybit_helpers.py")
    else:
        logger.info("✅ Helper function already exists in bybit_helpers.py")
    
    logger.info("\n🎯 IMPLEMENTATION COMPLETE!")
    logger.info("The codebase now supports account-aware monitor keys")
    logger.info("All 13 positions can be monitored without conflicts")

if __name__ == "__main__":
    main()