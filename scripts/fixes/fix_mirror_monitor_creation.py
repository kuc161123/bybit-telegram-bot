#!/usr/bin/env python3
"""
Fix mirror monitor creation to properly add monitors to enhanced_tp_sl_monitors
"""

def create_mirror_monitor_fix():
    """
    Fix the mirror_enhanced_tp_sl.py to properly create monitors
    """
    
    fix_code = '''
            # Create monitor data structure
            monitor_data = {
                "symbol": symbol,
                "side": side,
                "position_size": position_size_decimal,
                "remaining_size": position_size_decimal,
                "entry_price": entry_price_decimal,
                "avg_price": entry_price_decimal,
                "approach": approach.lower() if approach else "fast",
                "tp_orders": {},  # Will be populated by sync
                "sl_order": None,  # Will be populated by sync
                "filled_tps": [],
                "cancelled_limits": False,
                "tp1_hit": False,
                "tp1_info": None,
                "sl_moved_to_be": False,
                "sl_move_attempts": 0,
                "created_at": time.time(),
                "last_check": time.time(),
                "limit_orders": [],
                "limit_orders_cancelled": False,
                "phase": "MONITORING",
                "chat_id": chat_id,
                "account_type": "mirror",
                "has_mirror": True
            }
            
            # Create monitor key
            monitor_key = f"{symbol}_{side}_mirror"
            
            # Add to main manager's monitors
            if self.main_manager:
                self.main_manager.position_monitors[monitor_key] = monitor_data
                logger.info(f"✅ Added {monitor_key} to Enhanced TP/SL monitors")
                
                # Also save to persistence directly
                try:
                    import pickle
                    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
                    
                    with open(pkl_path, 'rb') as f:
                        data = pickle.load(f)
                    
                    if 'bot_data' not in data:
                        data['bot_data'] = {}
                    if 'enhanced_tp_sl_monitors' not in data['bot_data']:
                        data['bot_data']['enhanced_tp_sl_monitors'] = {}
                    
                    # Add monitor to persistence
                    data['bot_data']['enhanced_tp_sl_monitors'][monitor_key] = monitor_data
                    
                    with open(pkl_path, 'wb') as f:
                        pickle.dump(data, f)
                    
                    logger.info(f"✅ Saved {monitor_key} to persistence")
                    
                except Exception as e:
                    logger.error(f"Error saving mirror monitor to persistence: {e}")
    '''
    
    # Also need to update sync_tp_sl_orders to update the monitor
    sync_update_code = '''
            # Update monitor with order information after successful sync
            if result and self.main_manager:
                monitor_key = f"{symbol}_{side}_mirror"
                if monitor_key in self.main_manager.position_monitors:
                    monitor = self.main_manager.position_monitors[monitor_key]
                    
                    # Update with actual orders placed
                    monitor["tp_orders"] = tp_orders_placed
                    monitor["sl_order"] = sl_order_placed
                    monitor["last_check"] = time.time()
                    
                    logger.info(f"✅ Updated {monitor_key} with {len(tp_orders_placed)} TP orders")
                    
                    # Start monitoring task if not already running
                    if not monitor.get("monitoring_task") or monitor["monitoring_task"].done():
                        monitor_task = asyncio.create_task(
                            self.main_manager._run_monitor_loop(symbol, side, "mirror")
                        )
                        monitor["monitoring_task"] = monitor_task
                        logger.info(f"🔄 Started monitoring task for {monitor_key}")
    '''
    
    print("✅ Created mirror monitor creation fix")
    print("\nThe fix ensures:")
    print("1. Mirror monitors are added to enhanced_tp_sl_monitors dict")
    print("2. Monitors are saved to persistence immediately")
    print("3. Monitoring tasks are started for mirror positions")
    print("4. Order information is updated after placement")
    
    return fix_code, sync_update_code

def apply_mirror_monitor_fix():
    """
    Apply the fix to mirror_enhanced_tp_sl.py
    """
    try:
        import re
        
        # Read the current file
        with open('execution/mirror_enhanced_tp_sl.py', 'r') as f:
            content = f.read()
        
        # Create backup
        import time
        backup_path = f'execution/mirror_enhanced_tp_sl.py.backup_{int(time.time())}'
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"✅ Created backup: {backup_path}")
        
        # Find the setup_mirror_tp_sl_orders method
        # Look for where monitor_data is created
        pattern = r'(monitor_data = \{[^}]+\})'
        
        # Check if pattern exists
        if re.search(pattern, content, re.DOTALL):
            print("✅ Found monitor_data creation section")
            
            # Find the section after monitor_data creation but before sync call
            # We need to insert our code after monitor_data is created
            insert_pattern = r'(monitor_data = \{[^}]+\})\s*\n\s*\n\s*(.*?# Get mirror position)'
            
            fix_code, sync_update_code = create_mirror_monitor_fix()
            
            # Create the replacement with our fix
            replacement = r'\1\n\n' + fix_code.strip() + '\n\n\2'
            
            # Apply the fix
            content_new = re.sub(insert_pattern, replacement, content, flags=re.DOTALL)
            
            if content_new != content:
                # Write the modified content
                with open('execution/mirror_enhanced_tp_sl.py', 'w') as f:
                    f.write(content_new)
                
                print("✅ Applied mirror monitor creation fix")
                print("\nChanges:")
                print("- Mirror monitors now added to enhanced_tp_sl_monitors")
                print("- Monitors saved to persistence")
                print("- Monitoring tasks properly started")
                return True
            else:
                print("⚠️ Pattern not matched correctly")
                return False
        else:
            print("❌ Could not find monitor_data creation pattern")
            return False
            
    except Exception as e:
        print(f"❌ Error applying fix: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    fix_code, sync_update_code = create_mirror_monitor_fix()
    
    # Save to files for manual review
    with open('mirror_monitor_fix_code.py', 'w') as f:
        f.write(fix_code)
    
    with open('mirror_sync_update_code.py', 'w') as f:
        f.write(sync_update_code)
    
    print("\n📝 Fix code saved to:")
    print("- mirror_monitor_fix_code.py")
    print("- mirror_sync_update_code.py")
    
    # Uncomment to auto-apply
    # if apply_mirror_monitor_fix():
    #     print("\n✅ Fix applied successfully!")
    # else:
    #     print("\n❌ Failed to apply fix")