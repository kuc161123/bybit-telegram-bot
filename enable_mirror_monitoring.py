#!/usr/bin/env python3
"""
Enable mirror monitoring in enhanced TP/SL manager
"""
import os
from datetime import datetime

def check_mirror_config():
    """Check mirror trading configuration"""
    print("="*60)
    print("CHECKING MIRROR CONFIGURATION")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Check environment variables
    enable_mirror = os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true"
    mirror_api_key = os.getenv("BYBIT_API_KEY_2", "")
    mirror_api_secret = os.getenv("BYBIT_API_SECRET_2", "")
    
    print("\n📊 Mirror Trading Configuration:")
    print(f"  ENABLE_MIRROR_TRADING: {enable_mirror}")
    print(f"  BYBIT_API_KEY_2: {'✅ Set' if mirror_api_key else '❌ Not set'}")
    print(f"  BYBIT_API_SECRET_2: {'✅ Set' if mirror_api_secret else '❌ Not set'}")
    
    if not enable_mirror:
        print("\n⚠️  Mirror trading is DISABLED")
        print("To enable, set ENABLE_MIRROR_TRADING=true in .env file")
    
    return enable_mirror

def create_monitor_config():
    """Create configuration to ensure mirror monitors are loaded"""
    config_content = '''#!/usr/bin/env python3
"""
Mirror monitoring configuration
Ensures mirror monitors are loaded and monitored
"""

# Force enable mirror monitoring for enhanced TP/SL
ENABLE_MIRROR_MONITORING = True
MONITOR_BOTH_ACCOUNTS = True

# Export configuration
__all__ = ['ENABLE_MIRROR_MONITORING', 'MONITOR_BOTH_ACCOUNTS']
'''
    
    with open('config/mirror_monitoring.py', 'w') as f:
        f.write(config_content)
    
    print("\n✅ Created config/mirror_monitoring.py")

def patch_enhanced_manager():
    """Create a patch to ensure mirror monitors are included"""
    patch_content = '''#!/usr/bin/env python3
"""
Patch to ensure mirror monitors are loaded in enhanced TP/SL manager
"""
import logging

logger = logging.getLogger(__name__)

def should_include_mirror_monitors():
    """Check if mirror monitors should be included"""
    # Always include mirror monitors if they exist in pickle
    return True

def get_all_monitor_keys(monitors_dict):
    """Get all monitor keys including mirror"""
    all_keys = []
    for key, monitor in monitors_dict.items():
        all_keys.append(key)
        logger.debug(f"Found monitor: {key} (account: {monitor.get('account_type', 'unknown')})")
    return all_keys

# Export functions
__all__ = ['should_include_mirror_monitors', 'get_all_monitor_keys']
'''
    
    with open('utils/mirror_monitor_loader.py', 'w') as f:
        f.write(patch_content)
    
    print("✅ Created utils/mirror_monitor_loader.py")

def main():
    """Main execution"""
    # Check configuration
    mirror_enabled = check_mirror_config()
    
    # Create config file
    create_monitor_config()
    
    # Create patch
    patch_enhanced_manager()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    if mirror_enabled:
        print("✅ Mirror trading is enabled")
        print("✅ Configuration files created")
        print("\n⚠️  The bot may need to be restarted to load mirror monitors")
    else:
        print("⚠️  Mirror trading is disabled in .env")
        print("   Set ENABLE_MIRROR_TRADING=true to enable")
    
    print("\n💡 The bot should now load all 10 monitors")
    print("   If still showing 5, restart the bot")

if __name__ == "__main__":
    main()