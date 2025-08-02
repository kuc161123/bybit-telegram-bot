#!/usr/bin/env python3
"""
Startup TP Fill Recovery System
==============================

This script detects and handles missed TP fills when bot was offline.
Specifically designed to fix JASMY TP1 issue and prevent future occurrences.

Key Features:
- Detects TP fills by comparing position sizes
- Updates monitor states retroactively
- Executes missed actions (breakeven, limit cancellation, alerts)
- Validates state consistency between exchange and pickle

Usage:
    python scripts/fixes/startup_tp_fill_recovery.py

"""
import asyncio
import logging
import pickle
import time
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from config.settings import CANCEL_LIMITS_ON_TP1, DEFAULT_ALERT_CHAT_ID
from clients.bybit_helpers import get_position_info, get_open_orders, cancel_order_with_retry
from utils.alert_helpers import send_simple_alert

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StartupTPFillRecovery:
    """Recovery system for missed TP fills during bot downtime"""
    
    def __init__(self):
        self.pickle_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        self.recovery_actions = []
        self.validation_results = []
        
    async def detect_missed_tp_fills(self) -> List[Dict]:
        """
        Detect missed TP fills by comparing stored vs actual position sizes
        Returns list of positions requiring recovery
        """
        logger.info("🔍 Starting missed TP fill detection...")
        
        missed_fills = []
        
        # Load pickle data
        try:
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)
            
            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            logger.info(f"📊 Found {len(enhanced_monitors)} Enhanced TP/SL monitors")
            
        except Exception as e:
            logger.error(f"❌ Failed to load pickle data: {e}")
            return missed_fills
        
        # Check each monitor for potential missed TP fills
        for monitor_key, monitor_data in enhanced_monitors.items():
            try:
                symbol = monitor_data.get('symbol')
                side = monitor_data.get('side')
                account = monitor_data.get('account_type', 'main')
                
                if not symbol or not side:
                    continue
                
                # Get current position from exchange
                current_position = await self._get_current_position(symbol, side, account)
                
                if current_position:
                    # Compare stored vs actual position size
                    missed_fill_data = await self._analyze_position_for_missed_fills(
                        monitor_key, monitor_data, current_position
                    )
                    
                    if missed_fill_data:
                        missed_fills.append(missed_fill_data)
                        logger.info(f"🎯 Detected missed TP fill: {symbol} {side} ({account})")
                
            except Exception as e:
                logger.error(f"❌ Error analyzing {monitor_key}: {e}")
                continue
        
        logger.info(f"✅ Detection complete. Found {len(missed_fills)} missed TP fills")
        return missed_fills
    
    async def _get_current_position(self, symbol: str, side: str, account: str) -> Optional[Dict]:
        """Get current position from exchange for both main and mirror accounts"""
        try:
            # Import the appropriate client
            if account == 'mirror':
                try:
                    from execution.mirror_trader import bybit_client_2 as client
                    logger.info(f"🔍 Checking {symbol} {side} on MIRROR account")
                except ImportError:
                    logger.error("❌ Mirror trading not available")
                    return None
            else:
                from clients.bybit_client import bybit_client as client
                logger.info(f"🔍 Checking {symbol} {side} on MAIN account")
            
            response = client.get_positions(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0:
                for pos in response['result']['list']:
                    if pos['symbol'] == symbol and pos['side'] == side:
                        pos_size = Decimal(str(pos.get('size', '0')))
                        if pos_size > 0:
                            logger.info(f"✅ Found position: {pos_size} {symbol} on {account} account")
                            return {
                                'symbol': symbol,
                                'side': side,
                                'size': pos_size,
                                'avgPrice': Decimal(str(pos.get('avgPrice', '0'))),
                                'account': account
                            }
                        else:
                            logger.info(f"ℹ️ Position size is 0 for {symbol} on {account} account")
            else:
                logger.error(f"❌ API error for {symbol} on {account}: {response.get('retMsg')}")
            
            logger.info(f"ℹ️ No active position found for {symbol} {side} on {account} account")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting position for {symbol} on {account}: {e}")
            return None
    
    async def _analyze_position_for_missed_fills(self, monitor_key: str, monitor_data: Dict, 
                                               current_position: Dict) -> Optional[Dict]:
        """Analyze if position indicates missed TP fills"""
        try:
            stored_remaining = Decimal(str(monitor_data.get('remaining_size', '0')))
            current_size = current_position['size']
            tp1_hit = monitor_data.get('tp1_hit', False)
            
            # Check if position size decreased but tp1_hit flag is still False
            if current_size < stored_remaining and not tp1_hit:
                # Calculate how much was filled
                filled_amount = stored_remaining - current_size
                
                # Check if this matches TP1 order quantity
                tp_orders = monitor_data.get('tp_orders', {})
                tp1_order = None
                
                for order_id, order_info in tp_orders.items():
                    if order_info.get('tp_number') == 1:
                        tp1_order = order_info
                        break
                
                if tp1_order:
                    expected_tp1_qty = Decimal(str(tp1_order.get('quantity', '0')))
                    
                    # Check if filled amount matches TP1 quantity (with 5% tolerance)
                    tolerance = expected_tp1_qty * Decimal('0.05')
                    
                    if abs(filled_amount - expected_tp1_qty) <= tolerance:
                        logger.info(f"🎯 {monitor_key}: TP1 fill detected!")
                        logger.info(f"   Expected: {expected_tp1_qty}, Filled: {filled_amount}")
                        
                        return {
                            'monitor_key': monitor_key,
                            'monitor_data': monitor_data,
                            'current_position': current_position,
                            'tp1_order': tp1_order,
                            'filled_amount': filled_amount,
                            'action_type': 'tp1_fill'
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error analyzing position for {monitor_key}: {e}")
            return None
    
    async def execute_recovery_actions(self, missed_fills: List[Dict]) -> None:
        """Execute recovery actions for missed TP fills"""
        logger.info(f"🔧 Executing recovery actions for {len(missed_fills)} positions...")
        
        for fill_data in missed_fills:
            try:
                await self._execute_single_recovery(fill_data)
                self.recovery_actions.append(f"✅ {fill_data['monitor_key']}: Recovery completed")
                
            except Exception as e:
                error_msg = f"❌ {fill_data['monitor_key']}: Recovery failed - {e}"
                logger.error(error_msg)
                self.recovery_actions.append(error_msg)
        
        logger.info("✅ Recovery actions completed")
    
    async def _execute_single_recovery(self, fill_data: Dict) -> None:
        """Execute recovery actions for a single position"""
        monitor_key = fill_data['monitor_key']
        monitor_data = fill_data['monitor_data']
        current_position = fill_data['current_position']
        tp1_order = fill_data['tp1_order']
        
        logger.info(f"🔧 Recovering {monitor_key}...")
        
        # 1. Update monitor state
        await self._update_monitor_state(monitor_key, monitor_data, current_position, tp1_order)
        
        # 2. Move SL to breakeven
        await self._move_sl_to_breakeven(monitor_data, current_position)
        
        # 3. Cancel limit orders if enabled
        if CANCEL_LIMITS_ON_TP1:
            await self._cancel_unfilled_limits(monitor_data, current_position)
        
        # 4. Send TP1 alert
        await self._send_tp1_alert(monitor_data, tp1_order, current_position)
        
        logger.info(f"✅ {monitor_key}: Recovery completed")
    
    async def _update_monitor_state(self, monitor_key: str, monitor_data: Dict, 
                                  current_position: Dict, tp1_order: Dict) -> None:
        """Update monitor state in pickle file"""
        try:
            # Load pickle data
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)
            
            enhanced_monitors = data['bot_data']['enhanced_tp_sl_monitors']
            
            if monitor_key in enhanced_monitors:
                # Update the monitor state
                enhanced_monitors[monitor_key]['tp1_hit'] = True
                enhanced_monitors[monitor_key]['phase'] = 'PROFIT_TAKING'
                enhanced_monitors[monitor_key]['remaining_size'] = str(current_position['size'])
                enhanced_monitors[monitor_key]['phase_transition_time'] = time.time()
                
                # Add TP1 info
                enhanced_monitors[monitor_key]['tp1_info'] = {
                    'filled_at': str(int(time.time() * 1000)),
                    'filled_price': tp1_order.get('price'),
                    'filled_qty': tp1_order.get('quantity')
                }
                
                # Update filled_tps list
                if 'filled_tps' not in enhanced_monitors[monitor_key]:
                    enhanced_monitors[monitor_key]['filled_tps'] = []
                
                if 1 not in enhanced_monitors[monitor_key]['filled_tps']:
                    enhanced_monitors[monitor_key]['filled_tps'].append(1)
                
                # Save updated data
                with open(self.pickle_path, 'wb') as f:
                    pickle.dump(data, f)
                
                logger.info(f"✅ Updated monitor state for {monitor_key}")
            
        except Exception as e:
            logger.error(f"❌ Failed to update monitor state: {e}")
            raise
    
    async def _move_sl_to_breakeven(self, monitor_data: Dict, current_position: Dict) -> None:
        """Move SL order to breakeven for both main and mirror accounts"""
        try:
            symbol = monitor_data['symbol']
            account = monitor_data.get('account_type', 'main')
            entry_price = Decimal(str(monitor_data.get('entry_price', '0')))
            
            logger.info(f"🔄 Moving SL to breakeven for {symbol} on {account.upper()} account")
            
            # Calculate breakeven price (entry + small buffer)
            buffer = entry_price * Decimal('0.001')  # 0.1% buffer
            breakeven_price = entry_price + buffer
            
            # Get SL order info
            sl_order = monitor_data.get('sl_order')
            if not sl_order or not sl_order.get('order_id'):
                logger.warning(f"⚠️ No SL order found for {symbol} on {account}")
                return
            
            # Import appropriate client
            if account == 'mirror':
                try:
                    from execution.mirror_trader import bybit_client_2 as client
                    order_prefix = "MIR"
                except ImportError:
                    logger.error("❌ Mirror trading not available")
                    return
            else:
                from clients.bybit_client import bybit_client as client
                order_prefix = "BOT_CONS"
            
            # Cancel existing SL order
            logger.info(f"🚫 Cancelling existing SL order: {sl_order['order_id']}")
            cancel_response = client.cancel_order(
                category="linear",
                symbol=symbol,
                orderId=sl_order['order_id']
            )
            
            if cancel_response['retCode'] != 0:
                logger.error(f"❌ Failed to cancel SL order on {account}: {cancel_response.get('retMsg')}")
                return
            
            # Place new SL order at breakeven
            side = "Sell" if monitor_data['side'] == "Buy" else "Buy"
            
            new_sl_response = client.place_order(
                category="linear",
                symbol=symbol,
                side=side,
                orderType="Market",
                qty=str(current_position['size']),
                triggerPrice=str(breakeven_price),
                triggerDirection=2 if monitor_data['side'] == "Buy" else 1,
                orderLinkId=f"{order_prefix}_{symbol}_SL_BE_RECOVERY_{int(time.time())}",
                reduceOnly=True,
                stopOrderType="StopLoss"
            )
            
            if new_sl_response['retCode'] == 0:
                logger.info(f"✅ SL moved to breakeven on {account}: {breakeven_price}")
                
                # Update monitor data
                monitor_data['sl_order'] = {
                    'order_id': new_sl_response['result']['orderId'],
                    'price': breakeven_price,
                    'quantity': current_position['size'],
                    'moved_to_breakeven': True,
                    'account': account
                }
                monitor_data['sl_moved_to_be'] = True
            else:
                logger.error(f"❌ Failed to place new SL on {account}: {new_sl_response.get('retMsg')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to move SL to breakeven on {account}: {e}")
    
    async def _cancel_unfilled_limits(self, monitor_data: Dict, current_position: Dict) -> None:
        """Cancel unfilled limit orders for both main and mirror accounts"""
        try:
            symbol = monitor_data['symbol']
            account = monitor_data.get('account_type', 'main')
            
            logger.info(f"🚫 Cancelling unfilled limit orders for {symbol} on {account.upper()} account")
            
            # Import appropriate client
            if account == 'mirror':
                try:
                    from execution.mirror_trader import bybit_client_2 as client
                    order_prefixes = ['MIR_']
                except ImportError:
                    logger.error("❌ Mirror trading not available")
                    return
            else:
                from clients.bybit_client import bybit_client as client
                order_prefixes = ['BOT_CONS_', 'BOT_']
            
            # Get open orders
            response = client.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] != 0:
                logger.error(f"❌ Failed to get open orders on {account}: {response.get('retMsg')}")
                return
            
            cancelled_count = 0
            orders = response.get('result', {}).get('list', [])
            
            logger.info(f"🔍 Found {len(orders)} open orders for {symbol} on {account}")
            
            for order in orders:
                order_link_id = order.get('orderLinkId', '')
                
                # Check if this is an unfilled limit entry order from our bot
                is_bot_order = any(prefix in order_link_id for prefix in order_prefixes)
                
                if (order.get('orderType') == 'Limit' and 
                    not order.get('reduceOnly') and 
                    order.get('side') == monitor_data['side'] and
                    order.get('orderStatus') in ['New', 'PartiallyFilled'] and
                    is_bot_order):
                    
                    logger.info(f"🎯 Found unfilled limit order: {order['orderId']} ({order_link_id})")
                    
                    # Cancel the order
                    cancel_response = client.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=order['orderId']
                    )
                    
                    if cancel_response['retCode'] == 0:
                        cancelled_count += 1
                        logger.info(f"✅ Cancelled limit order on {account}: {order['orderId']}")
                    else:
                        logger.error(f"❌ Failed to cancel order {order['orderId']} on {account}: {cancel_response.get('retMsg')}")
            
            if cancelled_count > 0:
                monitor_data['limit_orders_cancelled'] = True
                logger.info(f"✅ Cancelled {cancelled_count} unfilled limit orders on {account}")
            else:
                logger.info(f"ℹ️ No unfilled limit orders to cancel on {account}")
            
        except Exception as e:
            logger.error(f"❌ Failed to cancel limit orders on {account}: {e}")
    
    async def _send_tp1_alert(self, monitor_data: Dict, tp1_order: Dict, current_position: Dict) -> None:
        """Send TP1 fill alert for both main and mirror accounts"""
        try:
            symbol = monitor_data['symbol']
            side = monitor_data['side']
            account = monitor_data.get('account_type', 'main')
            chat_id = monitor_data.get('chat_id', DEFAULT_ALERT_CHAT_ID)
            
            tp1_price = tp1_order.get('price', '0')
            tp1_qty = tp1_order.get('quantity', '0')
            
            # Calculate percentage filled
            original_size = Decimal(str(monitor_data.get('position_size', '0')))
            filled_qty = Decimal(str(tp1_qty))
            percentage = (filled_qty / original_size * 100) if original_size > 0 else 0
            
            # Account-specific emoji
            account_emoji = "🎯" if account == "main" else "🪞"
            
            alert_message = f"""
{account_emoji} **TP1 FILLED** - {account.upper()} ACCOUNT
📊 {symbol} {side}

💰 **TP1**: {tp1_qty} @ {tp1_price}
📈 **Filled**: {percentage:.1f}% of position
🔄 **SL Moved**: To breakeven
{'🚫 **Limits Cancelled**: Unfilled orders removed' if CANCEL_LIMITS_ON_TP1 else ''}

⚠️ *Detected during startup recovery*
🔧 *Retroactive actions executed*
"""
            
            await send_simple_alert(chat_id, alert_message.strip())
            logger.info(f"✅ TP1 alert sent for {symbol} on {account} account")
            
        except Exception as e:
            logger.error(f"❌ Failed to send TP1 alert for {account}: {e}")
    
    async def validate_recovery(self) -> None:
        """Validate that recovery was successful for both main and mirror accounts"""
        logger.info("🔍 Validating recovery results for both accounts...")
        
        try:
            # Load updated pickle data
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)
            
            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            
            main_count = 0
            mirror_count = 0
            
            for monitor_key, monitor_data in enhanced_monitors.items():
                symbol = monitor_data.get('symbol')
                account = monitor_data.get('account_type', 'main')
                
                if symbol == 'JASMYUSDT':  # Focus on JASMY for now
                    tp1_hit = monitor_data.get('tp1_hit', False)
                    phase = monitor_data.get('phase', '')
                    sl_moved = monitor_data.get('sl_moved_to_be', False)
                    limits_cancelled = monitor_data.get('limit_orders_cancelled', False)
                    
                    account_emoji = "🎯" if account == "main" else "🪞"
                    
                    validation_msg = f"📋 {account_emoji} {monitor_key} ({account.upper()}) Validation:"
                    validation_msg += f"\n   TP1 Hit: {'✅' if tp1_hit else '❌'} {tp1_hit}"
                    validation_msg += f"\n   Phase: {'✅' if phase == 'PROFIT_TAKING' else '❌'} {phase}"
                    validation_msg += f"\n   SL to BE: {'✅' if sl_moved else '❌'} {sl_moved}"
                    
                    if CANCEL_LIMITS_ON_TP1:
                        validation_msg += f"\n   Limits Cancelled: {'✅' if limits_cancelled else '❌'} {limits_cancelled}"
                    
                    logger.info(validation_msg)
                    self.validation_results.append(validation_msg)
                    
                    if account == 'main':
                        main_count += 1
                    else:
                        mirror_count += 1
            
            # Summary
            summary_msg = f"📊 Recovery Validation Summary:"
            summary_msg += f"\n   Main Account Monitors: {main_count}"
            summary_msg += f"\n   Mirror Account Monitors: {mirror_count}"
            summary_msg += f"\n   Total Validated: {main_count + mirror_count}"
            
            logger.info(summary_msg)
            self.validation_results.append(summary_msg)
            
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
    
    def print_summary(self) -> None:
        """Print recovery summary"""
        print("\n" + "="*60)
        print("🔧 STARTUP TP FILL RECOVERY SUMMARY")
        print("="*60)
        
        print("\n📋 Recovery Actions:")
        for action in self.recovery_actions:
            print(f"   {action}")
        
        print("\n🔍 Validation Results:")
        for result in self.validation_results:
            print(f"   {result}")
        
        print("\n" + "="*60)

async def main():
    """Main recovery function"""
    recovery = StartupTPFillRecovery()
    
    try:
        # 1. Detect missed TP fills
        missed_fills = await recovery.detect_missed_tp_fills()
        
        if not missed_fills:
            logger.info("✅ No missed TP fills detected")
            return
        
        # 2. Execute recovery actions
        await recovery.execute_recovery_actions(missed_fills)
        
        # 3. Validate recovery
        await recovery.validate_recovery()
        
        # 4. Print summary
        recovery.print_summary()
        
    except Exception as e:
        logger.error(f"❌ Recovery failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())