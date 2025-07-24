#!/usr/bin/env python3
"""
Fix monitor.py to better detect and track conservative positions
"""

import os
import shutil
from datetime import datetime

def main():
    monitor_file = "/Users/lualakol/bybit-telegram-bot/execution/monitor.py"
    
    # Create backup
    backup_file = f"{monitor_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(monitor_file, backup_file)
    print(f"✅ Created backup: {backup_file}")
    
    # Read the file
    with open(monitor_file, 'r') as f:
        lines = f.readlines()
    
    # Find and enhance the start_position_monitoring function
    modified = False
    for i, line in enumerate(lines):
        # Fix approach detection to be more flexible
        if "if tp_count == 4:" in line:
            lines[i] = line.replace("if tp_count == 4:", "if tp_count >= 4:")
            print("✅ Fixed TP count check for conservative detection")
            modified = True
        
        # Add logging for approach detection
        if "# Determine approach based on order counts" in line and i + 1 < len(lines):
            if "logger.info" not in lines[i + 1]:
                lines.insert(i + 1, f"    logger.info(f\"Detecting approach: {{tp_count}} TPs, {{limit_count}} limits\")\n")
                print("✅ Added logging for approach detection")
                modified = True
    
    # Add a new function to ensure conservative positions are tracked
    new_function = '''
async def ensure_conservative_position_monitored(symbol: str, chat_id: int, chat_data: dict) -> bool:
    """
    Ensure a conservative position has proper monitoring
    This prevents issues like JUPUSDT not being found
    """
    try:
        # Get all orders for this symbol
        all_orders = await get_all_open_orders()
        symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]
        
        # Count TPs
        tp_count = sum(1 for o in symbol_orders if 
                      ('TP' in o.get('orderLinkId', '') and o.get('reduceOnly')) or
                      (o.get('stopOrderType') == 'TakeProfit'))
        
        # If 4 or more TPs, it's conservative
        if tp_count >= 4:
            active_monitors = chat_data.get('active_monitor_task_data_v2', {})
            monitor_key = f"{chat_id}_{symbol}_conservative"
            
            if monitor_key not in active_monitors:
                logger.info(f"📌 Creating missing conservative monitor for {symbol}")
                
                # Get position info
                positions = await get_position_info(symbol)
                if positions:
                    position = next((p for p in positions if float(p.get('size', 0)) > 0), None)
                    if position:
                        side = position.get('side')
                        
                        # Create monitor entry
                        active_monitors[monitor_key] = {
                            'symbol': symbol,
                            'side': side,
                            'approach': 'conservative',
                            'started_at': asyncio.get_event_loop().time(),
                            'chat_id': chat_id,
                            'is_conservative': True,
                            'tp_count': tp_count,
                            'auto_created': True
                        }
                        
                        # Extract order IDs
                        tp_order_ids = []
                        for order in symbol_orders:
                            if 'TP' in order.get('orderLinkId', '') and order.get('reduceOnly'):
                                tp_order_ids.append(order.get('orderId'))
                        
                        if tp_order_ids:
                            active_monitors[monitor_key]['conservative_tp_order_ids'] = tp_order_ids[:4]
                        
                        logger.info(f"✅ Created conservative monitor for {symbol}")
                        return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error ensuring conservative monitor: {e}")
        return False
'''
    
    # Find a good place to insert the function (after imports)
    insert_pos = None
    for i, line in enumerate(lines):
        if "# FIXED: ENHANCED FAST APPROACH" in line:
            insert_pos = i
            break
    
    if insert_pos:
        lines.insert(insert_pos, new_function + "\n")
        print("✅ Added ensure_conservative_position_monitored function")
        modified = True
    
    if modified:
        # Write back
        with open(monitor_file, 'w') as f:
            f.writelines(lines)
        print("✅ Monitor enhancements applied!")
    else:
        print("⚠️ No modifications needed")
    
    print("\n📌 What this fix does:")
    print("• More flexible conservative detection (4+ TPs)")
    print("• Function to ensure conservative positions are monitored")
    print("• Better logging for debugging")
    print("• Prevents positions from being missed by auto-rebalancer")

if __name__ == "__main__":
    main()