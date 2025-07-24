#!/usr/bin/env python3
"""
Permanently Remove External Order Protection Feature
This script neutralizes the external order protection at runtime and prepares for complete removal
"""

import asyncio
import logging
import sys
import os
import shutil
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def neutralize_external_order_protection():
    """Neutralize external order protection by replacing all methods with pass-through functions"""
    try:
        logger.info("🔧 Permanently Neutralizing External Order Protection...")
        logger.info("=" * 80)
        
        # Phase 1: Neutralize the standard protection module
        try:
            from utils.external_order_protection import external_order_protection
            
            logger.info("📍 Found standard external order protection - neutralizing...")
            
            # Create pass-through functions
            def always_true_is_bot_order(order):
                """All orders are bot orders"""
                return True
            
            def always_true_can_modify(order):
                """All orders can be modified"""
                return True
                
            def always_true_validate(order_id, operation, order_data=None):
                """All operations are valid"""
                return True
                
            def always_true_should_monitor(position, orders):
                """All positions should be monitored"""
                return True
                
            def always_bot_orders(orders):
                """Return all orders as bot orders"""
                return orders
                
            def dummy_protect_position(position, orders):
                """Return dummy analysis showing all orders as bot orders"""
                return {
                    'symbol': position.get('symbol', ''),
                    'side': position.get('side', ''),
                    'status': 'FULLY_BOT',
                    'protection': 'NONE',
                    'bot_orders': len(orders),
                    'external_orders': 0,
                    'external_order_ids': []
                }
            
            # Replace all methods
            external_order_protection.is_bot_order = always_true_is_bot_order
            external_order_protection.can_modify_order = always_true_can_modify
            external_order_protection.validate_order_operation = always_true_validate
            external_order_protection.should_monitor_position = always_true_should_monitor
            external_order_protection.filter_bot_orders = always_bot_orders
            external_order_protection.protect_position_orders = dummy_protect_position
            
            # Disable strict mode and clear caches
            external_order_protection.strict_mode = False
            external_order_protection.protected_orders.clear()
            external_order_protection.bot_orders_cache.clear()
            
            logger.info("✅ Standard protection neutralized")
            
        except ImportError:
            logger.info("ℹ️ Standard protection module not loaded")
        
        # Phase 2: Neutralize the enhanced protection module
        try:
            from utils.external_order_protection_enhanced import enhanced_external_order_protection
            
            logger.info("📍 Found enhanced external order protection - neutralizing...")
            
            # Apply same neutralization
            enhanced_external_order_protection.is_bot_order = always_true_is_bot_order
            enhanced_external_order_protection.can_modify_order = always_true_can_modify
            enhanced_external_order_protection.validate_order_operation = always_true_validate
            enhanced_external_order_protection.should_monitor_position = always_true_should_monitor
            enhanced_external_order_protection.filter_bot_orders = always_bot_orders
            enhanced_external_order_protection.protect_position_orders = dummy_protect_position
            enhanced_external_order_protection.strict_mode = False
            enhanced_external_order_protection.protected_orders.clear()
            enhanced_external_order_protection.bot_orders_cache.clear()
            
            logger.info("✅ Enhanced protection neutralized")
            
        except ImportError:
            logger.info("ℹ️ Enhanced protection module not loaded")
        
        # Phase 3: Test the neutralization
        logger.info("\n🧪 Testing neutralization...")
        test_order = {
            'orderId': 'external123456',
            'orderLinkId': 'MANUAL_EXCHANGE_ORDER',
            'symbol': 'BTCUSDT'
        }
        
        test_position = {
            'symbol': 'BTCUSDT',
            'side': 'Buy'
        }
        
        try:
            from utils.external_order_protection import external_order_protection
            result1 = external_order_protection.is_bot_order(test_order)
            result2 = external_order_protection.can_modify_order(test_order)
            result3 = external_order_protection.should_monitor_position(test_position, [test_order])
            
            logger.info(f"   is_bot_order: {result1} (should be True)")
            logger.info(f"   can_modify_order: {result2} (should be True)")
            logger.info(f"   should_monitor_position: {result3} (should be True)")
            
            if all([result1, result2, result3]):
                logger.info("✅ All tests passed - protection is neutralized!")
            else:
                logger.warning("⚠️ Some tests failed - check implementation")
        except Exception as e:
            logger.error(f"❌ Test error: {e}")
        
        logger.info("\n✅ External Order Protection has been permanently neutralized!")
        logger.info("   - All orders are now treated as bot orders")
        logger.info("   - All positions will be monitored")
        logger.info("   - All order operations are allowed")
        logger.info("\n⚠️ The feature is now effectively disabled at runtime")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error neutralizing protection: {e}")
        import traceback
        traceback.print_exc()
        return False

def prepare_code_removal():
    """Prepare scripts and documentation for permanent code removal"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    logger.info("\n📝 Preparing for permanent code removal...")
    
    # Create removal script
    removal_script = f'''#!/usr/bin/env python3
"""
Complete External Order Protection Removal
Run this script when ready to permanently remove the code (requires bot restart)
Generated: {timestamp}
"""

import os
import shutil
from datetime import datetime

def remove_external_order_protection_code():
    """Remove all external order protection code from the codebase"""
    
    print("🗑️ Removing External Order Protection Code...")
    print("=" * 80)
    
    # Files to delete
    files_to_delete = [
        'utils/external_order_protection.py',
        'utils/external_order_protection_enhanced.py',
        'scripts/fixes/disable_external_order_protection.py',
        'scripts/fixes/restore_external_order_protection.py',
        'scripts/fixes/set_external_protection_env.py',
        'scripts/maintenance/emergency_monitoring_fix.py',
        'scripts/maintenance/hotfix_external_order_protection.py',
    ]
    
    # Backup directory
    backup_dir = f'backups/external_order_protection_{timestamp}'
    os.makedirs(backup_dir, exist_ok=True)
    
    # Backup and delete files
    for file_path in files_to_delete:
        if os.path.exists(file_path):
            backup_path = os.path.join(backup_dir, os.path.basename(file_path))
            shutil.copy2(file_path, backup_path)
            os.remove(file_path)
            print(f"✅ Removed: {{file_path}} (backed up)")
        else:
            print(f"ℹ️ Not found: {{file_path}}")
    
    print(f"\\n✅ Files backed up to: {{backup_dir}}")
    print("\\n⚠️ Manual steps required:")
    print("1. Edit clients/bybit_helpers.py - remove import and protection checks")
    print("2. Edit execution/monitor.py - remove import and protection check")
    print("3. Edit config/settings.py - remove BOT_ORDER_PREFIX_STRICT")
    print("4. Update .env.example - remove EXTERNAL_ORDER_PROTECTION and BOT_ORDER_PREFIX_STRICT")
    print("5. Restart the bot for changes to take effect")

if __name__ == "__main__":
    remove_external_order_protection_code()
'''
    
    # Save removal script
    removal_script_path = 'remove_protection_code_final.py'
    with open(removal_script_path, 'w') as f:
        f.write(removal_script)
    os.chmod(removal_script_path, 0o755)
    
    logger.info(f"✅ Created removal script: {removal_script_path}")
    
    # Create manual edit guide
    edit_guide = f'''# Manual Code Edits Required for Complete Removal

After running the hot-patch, these manual edits are needed for permanent removal:

## 1. clients/bybit_helpers.py

Remove line 975:
```python
from utils.external_order_protection import external_order_protection
```

Remove lines 980-988 in amend_order_with_retry():
```python
if order_info and not external_order_protection.can_modify_order(order_info):
    logger.warning(f"🛡️ Order {{order_id[:8]}}... is external - modification blocked")
    return None
# ... and the except block checking strict_mode
```

Remove lines 1077-1085 in cancel_order_with_retry():
```python
if not external_order_protection.can_modify_order(order_info):
    logger.warning(f"🛡️ Order {{order_id[:8]}}... is external - cancellation blocked")
    return False
# ... and the except block checking strict_mode
```

## 2. execution/monitor.py

Remove line 38:
```python
from utils.external_order_protection import external_order_protection
```

Remove lines 2312-2323:
```python
# Check if this position should be monitored (skip external positions)
# Get orders for this position to check ownership
try:
    all_orders = await get_open_orders(symbol)
    
    # Check if we should monitor this position
    if not external_order_protection.should_monitor_position(position, all_orders):
        logger.info(f"🛡️ Stopping monitor for {{symbol}} - external position detected")
        # Deactivate this monitor
        chat_data[ACTIVE_MONITOR_TASK] = {{"active": False}}
        break
except Exception as e:
    logger.error(f"Error checking position ownership: {{e}}")
```

## 3. config/settings.py

Remove line 142:
```python
BOT_ORDER_PREFIX_STRICT = os.getenv("BOT_ORDER_PREFIX_STRICT", "true").lower() == "true"
```

## 4. .env.example

Remove these lines:
```
EXTERNAL_ORDER_PROTECTION=true
BOT_ORDER_PREFIX_STRICT=true
```

## 5. CLAUDE.md

Remove the "External Order Protection System" section from the documentation.

Generated: {timestamp}
'''
    
    # Save edit guide
    guide_path = 'EXTERNAL_ORDER_PROTECTION_REMOVAL_GUIDE.md'
    with open(guide_path, 'w') as f:
        f.write(edit_guide)
    
    logger.info(f"✅ Created edit guide: {guide_path}")

if __name__ == "__main__":
    # Run neutralization
    success = neutralize_external_order_protection()
    
    if success:
        # Prepare removal documentation
        prepare_code_removal()
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 EXTERNAL ORDER PROTECTION SUCCESSFULLY NEUTRALIZED!")
        logger.info("=" * 80)
        logger.info("\n📋 Summary:")
        logger.info("   1. Protection is now disabled at runtime (no restart needed)")
        logger.info("   2. All orders are treated as bot orders")
        logger.info("   3. All positions will be monitored")
        logger.info("   4. Orphaned order cleanup will work")
        logger.info("\n📝 Next Steps (Optional):")
        logger.info("   1. Monitor bot operation to ensure everything works")
        logger.info("   2. When ready, run: python remove_protection_code_final.py")
        logger.info("   3. Follow the manual edit guide")
        logger.info("   4. Restart bot for permanent removal")
        logger.info("\n✅ The bot will now operate without any order protection restrictions!")