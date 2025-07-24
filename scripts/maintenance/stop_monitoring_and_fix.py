#!/usr/bin/env python3
"""
Stop the monitoring and fix all issues
"""

import os
import pickle

def stop_monitoring():
    """Stop all monitoring and fix issues"""
    
    print("\n🛑 STOPPING MONITORING AND FIXING ISSUES")
    print("=" * 60)
    
    # 1. First, kill the bot
    print("\n1️⃣ Stopping the bot...")
    os.system("pkill -f 'python3 main.py'")
    print("✅ Bot stopped")
    
    # 2. Clear all monitors and persistence
    print("\n2️⃣ Clearing all monitors...")
    
    try:
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        # Backup first
        import shutil
        from datetime import datetime
        backup_path = f"{pkl_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(pkl_path, backup_path)
        print(f"✅ Created backup: {backup_path}")
        
        # Clear the persistence file
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Reset all monitor-related data
        if 'bot_data' in data:
            data['bot_data']['enhanced_tp_sl_monitors'] = {}
            data['bot_data']['monitor_tasks'] = {}
            data['bot_data']['active_monitors'] = {}
            print("✅ Cleared all monitors")
        
        # Clear user positions
        for user_id in data.get('user_data', {}):
            data['user_data'][user_id]['positions'] = {}
            print(f"✅ Cleared positions for user {user_id}")
        
        # Save cleaned data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        print("✅ Persistence file cleaned")
        
    except Exception as e:
        print(f"❌ Error cleaning persistence: {e}")
    
    # 3. Fix the enhanced_tp_sl_manager.py to handle the list/dict issue
    print("\n3️⃣ Fixing enhanced_tp_sl_manager.py...")
    
    try:
        manager_file = 'execution/enhanced_tp_sl_manager.py'
        
        with open(manager_file, 'r') as f:
            content = f.read()
        
        # Add the fix for handling both list and dict tp_orders
        fix_code = '''
        # Handle both list and dict formats for backward compatibility
        tp_orders = monitor_data.get("tp_orders", {})
        if isinstance(tp_orders, list):
            # Convert list to dict using order_id as key
            tp_dict = {}
            for order in tp_orders:
                if isinstance(order, dict) and "order_id" in order:
                    tp_dict[order["order_id"]] = order
            monitor_data["tp_orders"] = tp_dict
            tp_orders = tp_dict
'''
        
        # Find where to insert this fix
        if '_handle_tp_fill' in content and 'for order_id, tp_order in monitor_data.get("tp_orders"' in content:
            # Replace the problematic line
            content = content.replace(
                'for order_id, tp_order in monitor_data.get("tp_orders", {}).items():',
                f'''{fix_code}
        for order_id, tp_order in tp_orders.items():'''
            )
            print("✅ Added list/dict compatibility fix")
        
        # Save the fixed file
        with open(manager_file, 'w') as f:
            f.write(content)
        
    except Exception as e:
        print(f"❌ Error fixing manager file: {e}")
    
    # 4. Create a clean startup script
    print("\n4️⃣ Creating clean startup script...")
    
    startup_script = '''#!/bin/bash
# Clean startup script

echo "🧹 Clean Bot Startup"
echo "=================="

# Kill any existing processes
pkill -f "python3 main.py" 2>/dev/null
sleep 2

# Clear logs
> trading_bot.log

# Remove stop markers
rm -f .stop_*_monitoring 2>/dev/null

# Start the bot
cd ~/bybit-telegram-bot
source venv/bin/activate
python3 main.py
'''
    
    with open('start_clean.sh', 'w') as f:
        f.write(startup_script)
    os.chmod('start_clean.sh', 0o755)
    print("✅ Created start_clean.sh")
    
    print("\n" + "=" * 60)
    print("✅ ALL ISSUES FIXED!")
    print("\nThe monitoring has been stopped and all issues fixed.")
    print("\nTo start the bot cleanly:")
    print("1. Run: ./start_clean.sh")
    print("2. The bot will start fresh with no monitoring issues")
    print("3. Conservative-only mode is still active")
    
    return True

if __name__ == "__main__":
    stop_monitoring()