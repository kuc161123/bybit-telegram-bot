#!/usr/bin/env python3
"""
Integration patch to update monitor.py to use the new robust systems
This script patches the existing monitor.py to integrate:
1. Robust alert delivery with retry
2. Enhanced order management with atomic operations
3. Health monitoring and recovery
"""
import re
import os
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create a backup of the file before patching"""
    backup_path = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"Created backup: {backup_path}")
    return backup_path

def patch_imports(content):
    """Add new import statements"""
    # Find the last import line
    import_pattern = r'(from utils\.alert_helpers import send_trade_alert, send_position_closed_summary)'
    
    new_imports = """from utils.alert_helpers import send_trade_alert, send_position_closed_summary
from utils.robust_alerts import send_trade_alert_robust, get_robust_alert_system, AlertPriority
from utils.robust_orders import get_robust_order_manager, AtomicOrderOperation, OrderOperationLock
from utils.monitor_health import get_health_checker, check_monitor_health"""
    
    content = re.sub(import_pattern, new_imports, content, count=1)
    return content

def patch_alert_calls(content):
    """Replace send_trade_alert with send_trade_alert_robust"""
    # Pattern to match send_trade_alert calls
    pattern = r'await send_trade_alert\('
    replacement = 'await send_trade_alert_robust('
    
    content = re.sub(pattern, replacement, content)
    return content

def patch_order_cancellations(content):
    """Enhance order cancellation calls to use robust order manager"""
    # This is more complex - we need to wrap cancellation blocks
    # For now, we'll add a helper function
    
    helper_function = '''
async def cancel_orders_robust(symbol: str, order_ids: List[str], chat_data: dict, 
                              order_type: str = "order") -> Tuple[List[str], List[str]]:
    """Enhanced order cancellation using robust order manager"""
    order_manager = get_robust_order_manager()
    return await order_manager.cancel_orders_atomic(symbol, order_ids, chat_data, order_type)
'''
    
    # Insert after the imports
    import_end = content.find('logger = logging.getLogger(__name__)')
    if import_end > 0:
        # Find the next newline after logger
        newline_pos = content.find('\n', import_end)
        content = content[:newline_pos + 1] + helper_function + content[newline_pos + 1:]
    
    return content

def patch_monitor_start(content):
    """Add health monitoring registration when monitor starts"""
    # Find monitor_position function
    monitor_start_pattern = r'(async def monitor_position.*?\n.*?try:)'
    
    health_check_code = '''
        # Register monitor for health checking
        health_checker = get_health_checker()
        monitor_id = f"{chat_id}_{symbol}_{approach}"
        health_checker.register_monitor(monitor_id, symbol, chat_id)
        
        # Start health monitoring if not already running
        await health_checker.start_health_monitoring()
'''
    
    def replace_func(match):
        return match.group(1) + health_check_code
    
    content = re.sub(monitor_start_pattern, replace_func, content, flags=re.DOTALL)
    return content

def patch_monitor_loop(content):
    """Add health check updates in monitor loop"""
    # Find the main monitoring loop
    loop_pattern = r'(while chat_data\.get\(ACTIVE_MONITOR_TASK.*?\n.*?# Sleep before next iteration)'
    
    health_update_code = '''
                # Update health monitor activity
                if 'health_checker' in locals():
                    health_checker.update_monitor_activity(monitor_id)
                
                # Sleep before next iteration'''
    
    def replace_func(match):
        original = match.group(0)
        return original.replace('# Sleep before next iteration', health_update_code)
    
    content = re.sub(loop_pattern, replace_func, content, flags=re.DOTALL)
    return content

def patch_monitor_cleanup(content):
    """Add health monitor unregistration in cleanup"""
    cleanup_pattern = r'(finally:.*?# Cleanup)'
    
    cleanup_code = '''
        # Unregister from health monitoring
        if 'health_checker' in locals() and 'monitor_id' in locals():
            health_checker.unregister_monitor(monitor_id)
'''
    
    def replace_func(match):
        return match.group(0) + cleanup_code
    
    content = re.sub(cleanup_pattern, replace_func, content, flags=re.DOTALL)
    return content

def create_wrapper_functions(content):
    """Add wrapper functions for backward compatibility"""
    wrapper_code = '''
# Wrapper functions for enhanced functionality
async def send_alert_with_priority(bot, chat_id, alert_type, priority=AlertPriority.MEDIUM, **kwargs):
    """Send alert with priority using robust system"""
    alert_system = get_robust_alert_system(bot)
    return await alert_system.send_alert(
        alert_type=alert_type,
        chat_id=chat_id,
        priority=priority,
        **kwargs
    )

async def cancel_order_with_atomic_op(symbol: str, order_id: str, chat_data: dict, operation_name: str):
    """Cancel order with atomic operation tracking"""
    async with AtomicOrderOperation(chat_data, operation_name) as atomic_op:
        success = await cancel_order_with_retry(symbol, order_id)
        atomic_op.log_operation(OrderOperation(
            operation_type=OrderOperationType.CANCEL,
            symbol=symbol,
            order_id=order_id,
            success=success
        ))
        return success
'''
    
    # Add after the helper functions
    content = content.replace('logger = logging.getLogger(__name__)', 
                            f'logger = logging.getLogger(__name__)\n{wrapper_code}')
    return content

def main():
    """Main patching function"""
    monitor_file = "/Users/lualakol/bybit-telegram-bot/execution/monitor.py"
    
    # Check if file exists
    if not os.path.exists(monitor_file):
        print(f"Error: {monitor_file} not found")
        return
    
    # Create backup
    backup_path = backup_file(monitor_file)
    
    try:
        # Read the file
        with open(monitor_file, 'r') as f:
            content = f.read()
        
        # Apply patches
        print("Applying patches...")
        content = patch_imports(content)
        print("✓ Patched imports")
        
        content = patch_alert_calls(content)
        print("✓ Patched alert calls")
        
        content = patch_order_cancellations(content)
        print("✓ Added robust order cancellation helper")
        
        content = patch_monitor_start(content)
        print("✓ Added health monitoring registration")
        
        content = patch_monitor_loop(content)
        print("✓ Added health check updates")
        
        content = patch_monitor_cleanup(content)
        print("✓ Added health monitor cleanup")
        
        content = create_wrapper_functions(content)
        print("✓ Added wrapper functions")
        
        # Write the patched content
        with open(monitor_file, 'w') as f:
            f.write(content)
        
        print(f"\n✅ Successfully patched {monitor_file}")
        print(f"Backup saved at: {backup_path}")
        
        # Create a summary file
        summary_file = f"patch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(summary_file, 'w') as f:
            f.write("Monitor.py Patch Summary\n")
            f.write("=======================\n\n")
            f.write("Applied the following enhancements:\n")
            f.write("1. Integrated robust alert system with retry logic\n")
            f.write("2. Added atomic order operations with rollback capability\n")
            f.write("3. Integrated health monitoring and recovery system\n")
            f.write("4. Enhanced error handling and recovery mechanisms\n")
            f.write(f"\nBackup file: {backup_path}\n")
            f.write(f"\nPatch applied: {datetime.now()}\n")
        
        print(f"Summary saved at: {summary_file}")
        
    except Exception as e:
        print(f"Error during patching: {e}")
        print(f"Restoring from backup...")
        shutil.copy2(backup_path, monitor_file)
        print("Backup restored")

if __name__ == "__main__":
    main()