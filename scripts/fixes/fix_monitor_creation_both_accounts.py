#!/usr/bin/env python3
"""
Fix monitor creation to properly handle both main and mirror accounts
"""

def create_monitor_creation_fix():
    """
    Create a fix that ensures both main and mirror monitors are created for new trades
    """
    
    fix_code = '''
            # Initialize monitoring for positions based on account type
            if account_type == "both":
                # Create monitors for BOTH accounts
                
                # Main account monitor
                main_monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "position_size": position_size,  # Target position size
                    "current_size": tp_sl_position_size,  # Actual current size
                    "remaining_size": tp_sl_position_size,  # Start with actual size
                    "tp_orders": [order for order in results["tp_orders"] if order.get("account") == "main"],
                    "sl_order": results["main_account"]["sl_order"],
                    "filled_tps": [],
                    "approach": approach,
                    "chat_id": chat_id,
                    "created_at": time.time(),
                    "last_check": time.time(),
                    "sl_moved_to_be": False,
                    "monitoring_task": None,
                    "limit_orders": [],
                    "limit_orders_filled": approach == "FAST",
                    "phase": "PROFIT_TAKING" if approach == "FAST" else "BUILDING",
                    "tp1_hit": False,
                    "phase_transition_time": None,
                    "total_tp_filled": Decimal("0"),
                    "cleanup_completed": False,
                    "bot_instance": None,
                    "account_type": "main"
                }
                
                main_monitor_key = f"{symbol}_{side}_main"
                self.position_monitors[main_monitor_key] = main_monitor_data
                
                # Start monitoring task for main
                main_monitor_task = asyncio.create_task(self._run_monitor_loop(symbol, side, "main"))
                main_monitor_data["monitoring_task"] = main_monitor_task
                
                # Create dashboard entry for main
                await self.create_dashboard_monitor_entry(symbol, side, chat_id, approach, "main")
                
                # Mirror account monitor (if setup)
                if setup_mirror and mirror_tp_sl_size is not None:
                    mirror_monitor_data = {
                        "symbol": symbol,
                        "side": side,
                        "entry_price": entry_price,
                        "position_size": mirror_target_size if mirror_target_size else mirror_tp_sl_size,
                        "current_size": mirror_tp_sl_size,
                        "remaining_size": mirror_tp_sl_size,
                        "tp_orders": [order for order in results["tp_orders"] if order.get("account") == "mirror"],
                        "sl_order": results["mirror_account"]["sl_order"],
                        "filled_tps": [],
                        "approach": approach,
                        "chat_id": chat_id,
                        "created_at": time.time(),
                        "last_check": time.time(),
                        "sl_moved_to_be": False,
                        "monitoring_task": None,
                        "limit_orders": [],
                        "limit_orders_filled": approach == "FAST",
                        "phase": "PROFIT_TAKING" if approach == "FAST" else "BUILDING",
                        "tp1_hit": False,
                        "phase_transition_time": None,
                        "total_tp_filled": Decimal("0"),
                        "cleanup_completed": False,
                        "bot_instance": None,
                        "account_type": "mirror",
                        "has_mirror": True
                    }
                    
                    mirror_monitor_key = f"{symbol}_{side}_mirror"
                    self.position_monitors[mirror_monitor_key] = mirror_monitor_data
                    
                    # Start monitoring task for mirror
                    mirror_monitor_task = asyncio.create_task(self._run_monitor_loop(symbol, side, "mirror"))
                    mirror_monitor_data["monitoring_task"] = mirror_monitor_task
                    
                    # Create dashboard entry for mirror
                    await self.create_dashboard_monitor_entry(symbol, side, chat_id, approach, "mirror")
                    
                logger.info(f"✅ Created monitors for both main and mirror accounts")
                
            else:
                # Single account monitor (backward compatibility)
                monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "entry_price": entry_price,
                    "position_size": position_size if account_type == "main" else (mirror_target_size if mirror_target_size else mirror_tp_sl_size),
                    "current_size": tp_sl_position_size if account_type == "main" else mirror_tp_sl_size,
                    "remaining_size": tp_sl_position_size if account_type == "main" else mirror_tp_sl_size,
                    "tp_orders": results["tp_orders"],
                    "sl_order": results["sl_order"],
                    "filled_tps": [],
                    "approach": approach,
                    "chat_id": chat_id,
                    "created_at": time.time(),
                    "last_check": time.time(),
                    "sl_moved_to_be": False,
                    "monitoring_task": None,
                    "limit_orders": [],
                    "limit_orders_filled": approach == "FAST",
                    "phase": "PROFIT_TAKING" if approach == "FAST" else "BUILDING",
                    "tp1_hit": False,
                    "phase_transition_time": None,
                    "total_tp_filled": Decimal("0"),
                    "cleanup_completed": False,
                    "bot_instance": None,
                    "account_type": account_type
                }
                
                # Use account-aware key format
                monitor_key = f"{symbol}_{side}_{account_type}"
                self.position_monitors[monitor_key] = monitor_data
                
                # Start monitoring task
                monitor_task = asyncio.create_task(self._run_monitor_loop(symbol, side, account_type))
                monitor_data["monitoring_task"] = monitor_task
                
                # Create monitor_tasks entry for dashboard compatibility
                await self.create_dashboard_monitor_entry(symbol, side, chat_id, approach, account_type)
            
            results["monitoring_active"] = True
    '''
    
    # Also need to update the _run_monitor_loop to handle account type
    monitor_loop_fix = '''
    async def _run_monitor_loop(self, symbol: str, side: str, account_type: str = None):
        """Run continuous monitoring loop for a position with account awareness"""
        # Use account-aware key
        if account_type:
            monitor_key = f"{symbol}_{side}_{account_type}"
        else:
            # Legacy support
            monitor_key = f"{symbol}_{side}"
            
        logger.info(f"🔄 Starting enhanced monitor loop for {monitor_key}")
        
        try:
            while monitor_key in self.position_monitors:
                # Run monitoring check with account type
                await self.monitor_and_adjust_orders(symbol, side, account_type)
                
                # Check if still active
                if monitor_key not in self.position_monitors:
                    break
                
                # Wait before next check (12 seconds like regular monitors)
                await asyncio.sleep(12)
                
        except asyncio.CancelledError:
            logger.info(f"⏹️ Monitor loop cancelled for {monitor_key}")
        except Exception as e:
            logger.error(f"❌ Error in monitor loop for {monitor_key}: {e}")
        finally:
            # Cleanup using robust persistence
            if monitor_key in self.position_monitors:
                monitor_data = self.position_monitors[monitor_key]
                chat_id = monitor_data.get("chat_id")
                approach = monitor_data.get("approach", "conservative")
                
                # Remove monitor using robust persistence
                try:
                    from utils.robust_persistence import remove_trade_monitor
                    await remove_trade_monitor(symbol, side, reason="monitor_stopped")
                    logger.info(f"✅ Removed monitor using Robust Persistence: {monitor_key}")
                except Exception as e:
                    logger.error(f"Error removing monitor via robust persistence: {e}")
                
                del self.position_monitors[monitor_key]
            logger.info(f"🛑 Monitor loop ended for {monitor_key}")
    '''
    
    print("✅ Created monitor creation fix")
    print("\nThe fix ensures:")
    print("1. When account_type='both', creates separate monitors for main and mirror")
    print("2. Each monitor tracks its own account's orders")
    print("3. Each monitor has its own monitoring task")
    print("4. Dashboard entries created for both accounts")
    print("5. Account-aware monitor keys used throughout")
    
    return fix_code, monitor_loop_fix

if __name__ == "__main__":
    fix_code, monitor_loop_fix = create_monitor_creation_fix()
    
    # Save to files for review
    with open('monitor_creation_fix.py', 'w') as f:
        f.write(fix_code)
    
    with open('monitor_loop_fix.py', 'w') as f:
        f.write(monitor_loop_fix)
    
    print("\n📝 Fix code saved to:")
    print("- monitor_creation_fix.py")
    print("- monitor_loop_fix.py")
    print("\nReview and apply these fixes to enhanced_tp_sl_manager.py")