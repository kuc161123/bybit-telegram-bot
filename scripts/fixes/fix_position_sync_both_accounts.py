#!/usr/bin/env python3
"""
Fix position sync to create monitors for both main and mirror accounts
"""

import asyncio
import logging
from decimal import Decimal
import time

logger = logging.getLogger(__name__)

def create_position_sync_fix():
    """Create the enhanced position sync that handles both accounts"""
    
    enhanced_sync_code = '''
    async def sync_existing_positions(self):
        """
        Sync existing positions and create monitors for positions without them
        This ensures all positions are monitored even after bot restarts
        ENHANCED: Now handles both main and mirror accounts
        """
        try:
            logger.info("🔄 Starting position sync for Enhanced TP/SL monitoring")
            
            # Sync main account positions
            await self._sync_account_positions("main")
            
            # Sync mirror account positions if enabled
            if self._is_mirror_trading_enabled():
                await self._sync_account_positions("mirror")
            
            logger.info("✅ Position sync completed for all accounts")
            
        except Exception as e:
            logger.error(f"❌ Error during position sync: {e}")
            import traceback
            traceback.print_exc()
    
    async def _sync_account_positions(self, account_type: str):
        """
        Sync positions for a specific account (main or mirror)
        """
        try:
            logger.info(f"🔄 Syncing {account_type} account positions")
            
            # Get positions based on account type
            if account_type == "mirror":
                from execution.mirror_trader import bybit_client_2
                if not bybit_client_2:
                    logger.warning("Mirror client not available")
                    return
                    
                response = bybit_client_2.get_positions(category="linear")
                if response['retCode'] != 0:
                    logger.error(f"Failed to get mirror positions: {response}")
                    return
                    
                all_positions = [pos for pos in response['result']['list'] if float(pos.get('size', 0)) > 0]
            else:
                # Main account
                from clients.bybit_helpers import get_all_positions
                all_positions = await get_all_positions()
            
            if not all_positions:
                logger.info(f"📊 No open positions found in {account_type} account")
                return
                
            logger.info(f"📊 Found {len(all_positions)} positions in {account_type} account")
            
            monitors_created = 0
            monitors_skipped = 0
            
            for position in all_positions:
                try:
                    symbol = position.get('symbol')
                    side = position.get('side')
                    size = float(position.get('size', 0))
                    
                    if size <= 0:
                        continue
                    
                    # Use account-aware key format
                    monitor_key = f"{symbol}_{side}_{account_type}"
                    
                    # Check if monitor already exists
                    if monitor_key in self.position_monitors:
                        logger.debug(f"✅ Monitor already exists for {monitor_key}")
                        monitors_skipped += 1
                        continue
                    
                    # Try to find chat_id
                    chat_id = await self._find_chat_id_for_position(symbol, side, account_type)
                    
                    if not chat_id:
                        logger.warning(f"⚠️ Could not find chat_id for {symbol} {side} ({account_type}) - creating monitor without alerts")
                    
                    # Create monitor for this position
                    logger.info(f"🆕 Creating monitor for {account_type} position: {symbol} {side}")
                    
                    # Get position details
                    avg_price = Decimal(str(position.get('avgPrice', 0)))
                    
                    # Get orders for this position
                    if account_type == "mirror":
                        orders_response = bybit_client_2.get_open_orders(
                            category="linear",
                            symbol=symbol
                        )
                        orders = orders_response['result']['list'] if orders_response['retCode'] == 0 else []
                    else:
                        orders = await get_open_orders(symbol)
                    
                    tp_orders = {}
                    sl_order = None
                    
                    for order in orders:
                        order_type = order.get('orderType', '')
                        stop_type = order.get('stopOrderType', '')
                        
                        if order_type == 'Limit' and order.get('reduceOnly'):
                            # TP order
                            tp_order_data = {
                                'order_id': order['orderId'],
                                'order_link_id': order.get('orderLinkId', ''),
                                'price': Decimal(str(order['price'])),
                                'quantity': Decimal(str(order['qty'])),
                                'original_quantity': Decimal(str(order['qty'])),
                                'percentage': 100,  # Will be adjusted based on approach
                                'tp_number': len(tp_orders) + 1,
                                'account': account_type
                            }
                            tp_orders[order['orderId']] = tp_order_data
                            
                        elif stop_type == 'StopLoss':
                            sl_order = {
                                'order_id': order['orderId'],
                                'order_link_id': order.get('orderLinkId', ''),
                                'price': Decimal(str(order.get('triggerPrice', 0))),
                                'quantity': Decimal(str(order['qty'])),
                                'original_quantity': Decimal(str(order['qty'])),
                                'covers_full_position': True,
                                'target_position_size': Decimal(str(size)),
                                'account': account_type
                            }
                    
                    # Create monitor data
                    monitor_data = {
                        "symbol": symbol,
                        "side": side,
                        "position_size": Decimal(str(size)),
                        "remaining_size": Decimal(str(size)),
                        "entry_price": avg_price,
                        "avg_price": avg_price,
                        "approach": "conservative" if len(tp_orders) > 1 else "fast",
                        "tp_orders": tp_orders,
                        "sl_order": sl_order,
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
                        "account_type": account_type,
                        "has_mirror": account_type == "mirror"
                    }
                    
                    # Add to monitors
                    self.position_monitors[monitor_key] = monitor_data
                    
                    # Save to persistence
                    await self._save_to_persistence()
                    
                    # Create dashboard monitor entry
                    if chat_id:
                        await self.create_dashboard_monitor_entry(
                            symbol=symbol,
                            side=side,
                            chat_id=chat_id,
                            approach=monitor_data["approach"],
                            account_type=account_type
                        )
                    
                    monitors_created += 1
                    logger.info(f"✅ Created {account_type} monitor for {symbol} {side} with {len(tp_orders)} TP orders")
                    
                except Exception as e:
                    logger.error(f"❌ Error creating monitor for {account_type} position {position}: {e}")
                    continue
            
            logger.info(f"🔄 {account_type.title()} account sync: {monitors_created} created, {monitors_skipped} skipped")
            
        except Exception as e:
            logger.error(f"❌ Error syncing {account_type} positions: {e}")
            import traceback
            traceback.print_exc()
    
    async def _find_chat_id_for_position(self, symbol: str, side: str, account_type: str) -> int:
        """
        Try to find chat_id for a position from various sources
        """
        chat_id = None
        
        try:
            import pickle
            pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            
            # First try user_data
            user_data = data.get('user_data', {})
            for uid, udata in user_data.items():
                if 'positions' in udata:
                    for pos in udata.get('positions', []):
                        if pos.get('symbol') == symbol and pos.get('side') == side:
                            chat_id = uid
                            logger.info(f"✅ Found chat_id {chat_id} from user data for {symbol} {side}")
                            return chat_id
            
            # Then try monitor_tasks
            bot_data = data.get('bot_data', {})
            monitor_tasks = bot_data.get('monitor_tasks', {})
            for mk, mv in monitor_tasks.items():
                if mv.get('symbol') == symbol:
                    # Check if it matches our account type
                    if (account_type == "mirror" and "_mirror" in mk) or \
                       (account_type == "main" and "_mirror" not in mk):
                        chat_id = mv.get('chat_id')
                        if chat_id:
                            logger.info(f"✅ Found chat_id {chat_id} from monitor_tasks for {symbol}")
                            return chat_id
            
            # Finally check existing enhanced monitors
            enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
            for mon_key, mon_data in enhanced_monitors.items():
                if mon_data.get('symbol') == symbol and mon_data.get('side') == side:
                    if (account_type == "mirror" and mon_key.endswith("_mirror")) or \
                       (account_type == "main" and mon_key.endswith("_main")):
                        chat_id = mon_data.get('chat_id')
                        if chat_id:
                            logger.info(f"✅ Found chat_id {chat_id} from enhanced monitors for {symbol}")
                            return chat_id
                            
        except Exception as e:
            logger.warning(f"Error finding chat_id: {e}")
        
        return chat_id
    '''
    
    # Write the fix to a patch file
    with open('fix_position_sync_patch.py', 'w') as f:
        f.write(enhanced_sync_code)
    
    print("✅ Created position sync fix patch")
    print("\nThe fix includes:")
    print("1. Separate sync for main and mirror accounts")
    print("2. Account-aware monitor key creation")
    print("3. Proper chat_id lookup for each account")
    print("4. Support for positions without chat_id")
    print("5. Full order tracking for each account")
    
    return True

def apply_position_sync_fix():
    """Apply the fix to enhanced_tp_sl_manager.py"""
    
    try:
        # Read the current file
        with open('execution/enhanced_tp_sl_manager.py', 'r') as f:
            content = f.read()
        
        # Create backup
        backup_path = f'execution/enhanced_tp_sl_manager.py.backup_{int(time.time())}'
        with open(backup_path, 'w') as f:
            f.write(content)
        print(f"✅ Created backup: {backup_path}")
        
        # Find the sync_existing_positions method and replace it
        import re
        
        # Read the patch
        with open('fix_position_sync_patch.py', 'r') as f:
            patch_content = f.read()
        
        # Find the method start
        method_pattern = r'(    async def sync_existing_positions\(self\):.*?)(?=    async def|\Z)'
        
        # Extract just the new method from patch
        new_method = patch_content.strip()
        
        # Replace the method
        if 'async def sync_existing_positions(self):' in content:
            # Count indentation by looking at the line before
            lines = content.split('\n')
            for i, line in enumerate(lines):
                if 'async def sync_existing_positions(self):' in line:
                    # Get indentation from this line
                    indent = len(line) - len(line.lstrip())
                    break
            
            # Add proper indentation to new method
            new_method_lines = new_method.split('\n')
            indented_lines = []
            for line in new_method_lines:
                if line.strip():  # Non-empty lines
                    if line.strip().startswith('async def') and not line.startswith(' '):
                        # This is a method definition at wrong indentation
                        indented_lines.append(' ' * indent + line.strip())
                    else:
                        indented_lines.append(line)
                else:
                    indented_lines.append(line)
            
            new_method_indented = '\n'.join(indented_lines)
            
            # Now do the replacement
            content_new = re.sub(
                method_pattern,
                new_method_indented + '\n\n',
                content,
                flags=re.DOTALL
            )
            
            # Write the modified content
            with open('execution/enhanced_tp_sl_manager.py', 'w') as f:
                f.write(content_new)
            
            print("✅ Applied position sync fix to enhanced_tp_sl_manager.py")
            print("\nChanges:")
            print("- sync_existing_positions now syncs both accounts")
            print("- Added _sync_account_positions helper method")
            print("- Added _find_chat_id_for_position helper method")
            print("- Monitors use account-aware keys")
            
            return True
        else:
            print("❌ Could not find sync_existing_positions method")
            return False
            
    except Exception as e:
        print(f"❌ Error applying fix: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if create_position_sync_fix():
        print("\n📝 Patch file created: fix_position_sync_patch.py")
        print("Review the patch and then apply it.")
        
        # Uncomment to auto-apply
        # if apply_position_sync_fix():
        #     print("\n✅ Fix applied successfully!")
        # else:
        #     print("\n❌ Failed to apply fix")