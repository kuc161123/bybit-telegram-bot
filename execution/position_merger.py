#!/usr/bin/env python3
"""
Position merger for both conservative and fast approaches - handles merging of positions 
with same symbol to bypass Bybit's stop order limits while maintaining optimal risk/reward parameters
"""
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from abc import ABC, abstractmethod

from clients.bybit_helpers import (
    get_position_info, get_all_open_orders,
    cancel_order_with_retry as cancel_order
)
from utils.cache import get_ticker_price_cached

logger = logging.getLogger(__name__)

class BasePositionMerger(ABC):
    """Base class for position mergers"""
    
    def __init__(self):
        self.logger = logger
        
    @abstractmethod
    def get_bot_order_patterns(self) -> List[str]:
        """Get order patterns that identify bot positions for this approach"""
        pass
    
    @abstractmethod
    def get_approach_name(self) -> str:
        """Get the approach name"""
        pass
    
    async def should_merge_positions(self, symbol: str, side: str, approach: str, bot_data: dict = None) -> Tuple[bool, Optional[Dict]]:
        """
        Check if we should merge with an existing BOT position (not external)
        Returns: (should_merge, existing_position_data)
        """
        # Only merge for matching approach
        if approach != self.get_approach_name():
            return False, None
            
        try:
            # Get existing positions for symbol
            position_info = await get_position_info(symbol)
            
            if not position_info or len(position_info) == 0:
                return False, None
                
            # Check if we have an open position with same side
            for position in position_info:
                if (float(position.get('size', 0)) > 0 and 
                    position.get('side') == side):
                    
                    # Get existing orders for this position
                    all_orders = await get_all_open_orders()
                    orders = [o for o in all_orders if o.get('symbol') == symbol]
                    
                    # CRITICAL: Check if this position belongs to the bot
                    # Look for bot-created orders with recognizable patterns
                    is_bot_position = False
                    bot_order_patterns = self.get_bot_order_patterns()
                    
                    for order in orders:
                        order_link_id = order.get('orderLinkId', '')
                        # Check if order has bot patterns
                        if any(pattern in order_link_id for pattern in bot_order_patterns):
                            is_bot_position = True
                            break
                    
                    # Also check bot_data for position tracking
                    if bot_data:
                        # Check if symbol is tracked in any chat's monitoring
                        for key, value in bot_data.items():
                            if (key.startswith('MONITOR_') and 
                                isinstance(value, dict) and 
                                value.get('symbol') == symbol and
                                value.get('approach') == self.get_approach_name()):
                                is_bot_position = True
                                break
                    
                    if not is_bot_position:
                        logger.info(f"🚫 Found {side} position for {symbol} but it's EXTERNAL - skipping merge")
                        return False, None
                    
                    # Extract TP/SL orders
                    tp_orders = self._extract_tp_orders(orders)
                    sl_order = self._extract_sl_order(orders)
                    
                    position_data = {
                        'position': position,
                        'tp_orders': tp_orders,
                        'sl_order': sl_order,
                        'orders': orders
                    }
                    
                    logger.info(f"🔄 Found existing BOT {side} position for {symbol} ({self.get_approach_name()}) - merge candidate")
                    return True, position_data
                    
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking for position merge: {e}")
            return False, None
    
    @abstractmethod
    def _extract_tp_orders(self, orders: List[Dict]) -> List[Dict]:
        """Extract TP orders from order list"""
        pass
    
    @abstractmethod
    def _extract_sl_order(self, orders: List[Dict]) -> Optional[Dict]:
        """Extract SL order from order list"""
        pass
    
    async def cancel_existing_orders(self, orders: List[Dict]) -> bool:
        """Cancel existing TP/SL orders for position"""
        try:
            cancelled_count = 0
            
            for order in orders:
                order_id = order.get('orderId')
                symbol = order.get('symbol')
                order_type = order.get('orderType', '')
                link_id = order.get('orderLinkId', '')
                
                # Only cancel TP/SL orders
                if order_type in ['Market', 'Limit'] and order.get('reduceOnly', False):
                    logger.info(f"🗑️ Cancelling {order_type} order {order_id[:8]}... ({link_id})")
                    
                    cancelled = await cancel_order(symbol, order_id)
                    if cancelled:
                        cancelled_count += 1
                        logger.info(f"✅ Cancelled order {order_id[:8]}...")
                    else:
                        logger.warning(f"⚠️ Failed to cancel order {order_id[:8]}...")
            
            logger.info(f"✅ Cancelled {cancelled_count} existing orders")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling existing orders: {e}")
            return False
    
    async def validate_merge(self, symbol: str, side: str, merged_params: Dict) -> bool:
        """Validate merged parameters are logical"""
        try:
            # Get current price
            current_price = await get_ticker_price_cached(symbol)
            if not current_price:
                logger.error(f"Could not get current price for {symbol}")
                return False
                
            current_price = Decimal(str(current_price))
            sl_price = Decimal(str(merged_params.get('sl_price', 0)))
            
            # Validate SL makes sense
            if side == 'Sell':  # SHORT
                if sl_price <= current_price:
                    logger.error(f"Invalid SHORT SL: {sl_price} should be above current {current_price}")
                    return False
            else:  # LONG
                if sl_price >= current_price:
                    logger.error(f"Invalid LONG SL: {sl_price} should be below current {current_price}")
                    return False
            
            # Validate TPs
            for i, tp in enumerate(merged_params.get('take_profits', [])):
                tp_price = Decimal(str(tp.get('price', 0)))
                
                if side == 'Sell':  # SHORT
                    if tp_price >= current_price:
                        logger.error(f"Invalid SHORT TP{i+1}: {tp_price} should be below current {current_price}")
                        return False
                else:  # LONG
                    if tp_price <= current_price:
                        logger.error(f"Invalid LONG TP{i+1}: {tp_price} should be above current {current_price}")
                        return False
            
            logger.info(f"✅ Merge parameters validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error validating merge parameters: {e}")
            return False

class ConservativePositionMerger(BasePositionMerger):
    """Handles merging of conservative positions with same symbol"""
    
    def get_bot_order_patterns(self) -> List[str]:
        """Conservative approach uses TP1_, TP2_, etc. patterns"""
        return ['TP1_', 'TP2_', 'TP3_', 'TP4_', 'SL_', '_LIMIT']
    
    def get_approach_name(self) -> str:
        """Return approach name"""
        return "conservative"
    
    def _extract_tp_orders(self, orders: List[Dict]) -> List[Dict]:
        """Extract TP orders for conservative approach"""
        tp_orders = []
        for order in orders:
            order_link_id = order.get('orderLinkId', '')
            if order_link_id.startswith('TP'):
                tp_orders.append(order)
        return sorted(tp_orders, key=lambda x: x.get('orderLinkId', ''))
    
    def _extract_sl_order(self, orders: List[Dict]) -> Optional[Dict]:
        """Extract SL order for conservative approach"""
        for order in orders:
            order_link_id = order.get('orderLinkId', '')
            if order_link_id.startswith('SL'):
                return order
        return None
    
    def calculate_merged_parameters(self, 
                                  existing_data: Dict,
                                  new_params: Dict,
                                  side: str) -> Dict:
        """
        Calculate optimal merged parameters for TP/SL
        
        For SHORT:
        - SL: Choose HIGHER price (more conservative)
        - TPs: Choose LOWER prices (more aggressive)
        
        For LONG:
        - SL: Choose LOWER price (more conservative) 
        - TPs: Choose HIGHER prices (more aggressive)
        """
        try:
            # Extract existing position data
            existing_position = existing_data['position']
            existing_tps = existing_data['tp_orders']
            existing_sl = existing_data['sl_order']
            
            # Calculate new position size
            existing_size = Decimal(str(existing_position.get('size', 0)))
            new_size = Decimal(str(new_params.get('position_size', 0)))
            merged_size = existing_size + new_size
            
            # Prepare merged parameters
            merged_params = {
                'merged_size': merged_size,
                'existing_size': existing_size,
                'new_size': new_size,
                'symbol': new_params['symbol'],
                'side': side,
                'leverage': new_params.get('leverage', existing_position.get('leverage')),
            }
            
            # Calculate merged stop loss
            if existing_sl and existing_sl.get('stopOrderType') == 'StopLoss':
                existing_sl_price = Decimal(str(existing_sl.get('triggerPrice', 0)))
                new_sl_price = Decimal(str(new_params.get('sl_price', 0)))
                
                if side == 'Sell':  # SHORT position
                    # Choose HIGHER stop loss (more conservative)
                    merged_params['sl_price'] = max(existing_sl_price, new_sl_price)
                    logger.info(f"🛡️ SHORT SL: Existing {existing_sl_price} vs New {new_sl_price} → Using {merged_params['sl_price']} (higher/safer)")
                else:  # LONG position  
                    # Choose LOWER stop loss (more conservative)
                    merged_params['sl_price'] = min(existing_sl_price, new_sl_price)
                    logger.info(f"🛡️ LONG SL: Existing {existing_sl_price} vs New {new_sl_price} → Using {merged_params['sl_price']} (lower/safer)")
                
                # Track if SL changed
                sl_changed = merged_params['sl_price'] != existing_sl_price
            else:
                merged_params['sl_price'] = new_params.get('sl_price')
                sl_changed = True  # No existing SL, so it's a change
            
            # Track TP changes
            tps_changed = False
            
            # Calculate merged take profits
            merged_params['take_profits'] = []
            new_tps = new_params.get('take_profits', [])
            
            # Match up to 4 TP levels
            for i in range(4):
                existing_tp = None
                new_tp = None
                
                # Get existing TP for this level
                if i < len(existing_tps):
                    tp_order = existing_tps[i]
                    if tp_order.get('orderLinkId', '').startswith(f'TP{i+1}'):
                        existing_tp = {
                            'price': Decimal(str(tp_order.get('triggerPrice', 0))),
                            'percentage': self._extract_tp_percentage(tp_order)
                        }
                
                # Get new TP for this level
                if i < len(new_tps):
                    new_tp = new_tps[i]
                
                # Merge TP levels
                if existing_tp and new_tp:
                    if side == 'Sell':  # SHORT position
                        # Choose LOWER TP (more aggressive)
                        merged_price = min(existing_tp['price'], Decimal(str(new_tp['price'])))
                        logger.info(f"🎯 SHORT TP{i+1}: Existing {existing_tp['price']} vs New {new_tp['price']} → Using {merged_price} (lower/aggressive)")
                    else:  # LONG position
                        # Choose HIGHER TP (more aggressive)  
                        merged_price = max(existing_tp['price'], Decimal(str(new_tp['price'])))
                        logger.info(f"🎯 LONG TP{i+1}: Existing {existing_tp['price']} vs New {new_tp['price']} → Using {merged_price} (higher/aggressive)")
                    
                    # Track if TP changed
                    if merged_price != existing_tp['price']:
                        tps_changed = True
                    
                    # Use the percentage allocation from new params
                    merged_params['take_profits'].append({
                        'price': merged_price,
                        'percentage': new_tp['percentage']
                    })
                elif new_tp:
                    # Only new TP exists
                    merged_params['take_profits'].append(new_tp)
                    tps_changed = True  # New TP added
                elif existing_tp:
                    # Only existing TP exists
                    merged_params['take_profits'].append({
                        'price': existing_tp['price'],
                        'percentage': existing_tp['percentage']
                    })
            
            # Add other necessary parameters
            merged_params['tick_size'] = new_params.get('tick_size')
            merged_params['qty_step'] = new_params.get('qty_step')
            merged_params['approach'] = 'conservative'
            
            # Track if parameters changed
            merged_params['sl_changed'] = sl_changed
            merged_params['tps_changed'] = tps_changed
            merged_params['parameters_changed'] = sl_changed or tps_changed
            
            logger.info(f"✅ Calculated merged parameters for {merged_size} {side} {new_params['symbol']}")
            if merged_params['parameters_changed']:
                logger.info(f"📊 Parameters changed: SL={merged_params['sl_changed']}, TPs={merged_params['tps_changed']}")
            else:
                logger.info(f"📊 No parameter changes - keeping original SL and TPs")
            return merged_params
            
        except Exception as e:
            logger.error(f"Error calculating merged parameters: {e}")
            raise
    
    def _extract_tp_percentage(self, tp_order: Dict) -> int:
        """Extract TP percentage from order link ID or default"""
        try:
            # Try to extract from orderLinkId like "TP1_70" 
            link_id = tp_order.get('orderLinkId', '')
            if '_' in link_id:
                percentage = int(link_id.split('_')[1])
                return percentage
        except:
            pass
        
        # Default percentages for TP1-4
        tp_num = self._get_tp_number(tp_order)
        default_percentages = {1: 70, 2: 10, 3: 10, 4: 10}
        return default_percentages.get(tp_num, 10)
    
    def _get_tp_number(self, tp_order: Dict) -> int:
        """Get TP number from order"""
        link_id = tp_order.get('orderLinkId', '')
        if link_id.startswith('TP'):
            try:
                return int(link_id[2])
            except:
                pass
        return 1
    
    async def cancel_existing_orders(self, orders: List[Dict]) -> bool:
        """Cancel existing TP/SL orders for position"""
        try:
            cancelled_count = 0
            
            for order in orders:
                order_id = order.get('orderId')
                symbol = order.get('symbol')
                order_type = order.get('orderType', '')
                link_id = order.get('orderLinkId', '')
                
                # Debug logging
                logger.debug(f"Order data: orderId={order_id}, symbol={symbol}, type={order_type}, linkId={link_id}")
                
                # Validate order data
                if not order_id or not symbol:
                    logger.warning(f"Skipping order with missing data: orderId={order_id}, symbol={symbol}")
                    continue
                
                # Check if orderId looks like a symbol (contains "USDT")
                if "USDT" in str(order_id) and "USDT" not in str(symbol):
                    logger.warning(f"Detected swapped order fields! Swapping back: orderId={order_id}, symbol={symbol}")
                    order_id, symbol = symbol, order_id
                
                # Only cancel TP/SL orders
                if (link_id.startswith('TP') or link_id.startswith('SL') or 
                    order_type in ['Market', 'Limit'] and order.get('stopOrderType')):
                    
                    logger.info(f"🗑️ Cancelling {link_id or order_type} order {order_id}... ({link_id})")
                    success = await cancel_order(symbol, order_id)
                    
                    if success:
                        cancelled_count += 1
                    else:
                        logger.warning(f"Failed to cancel order {order_id}")
            
            logger.info(f"✅ Cancelled {cancelled_count} existing orders")
            return cancelled_count > 0
            
        except Exception as e:
            logger.error(f"Error cancelling existing orders: {e}")
            return False
    
    async def validate_merge(self, symbol: str, side: str, merged_params: Dict) -> bool:
        """Validate that merge parameters are safe and logical"""
        try:
            # Get current price
            current_price = await get_ticker_price_cached(symbol)
            if not current_price:
                logger.error("Cannot validate merge - no current price")
                return False
            
            current_price = Decimal(str(current_price))
            sl_price = merged_params.get('sl_price')
            
            # Validate stop loss
            if sl_price:
                sl_price = Decimal(str(sl_price))
                if side == 'Sell':
                    # For SHORT, SL should be above current price
                    if sl_price <= current_price:
                        logger.error(f"Invalid SHORT SL: {sl_price} <= current {current_price}")
                        return False
                else:
                    # For LONG, SL should be below current price
                    if sl_price >= current_price:
                        logger.error(f"Invalid LONG SL: {sl_price} >= current {current_price}")
                        return False
            
            # Validate take profits
            for i, tp in enumerate(merged_params.get('take_profits', [])):
                tp_price = Decimal(str(tp['price']))
                if side == 'Sell':
                    # For SHORT, TPs should be below current price
                    if tp_price >= current_price:
                        logger.error(f"Invalid SHORT TP{i+1}: {tp_price} >= current {current_price}")
                        return False
                else:
                    # For LONG, TPs should be above current price  
                    if tp_price <= current_price:
                        logger.error(f"Invalid LONG TP{i+1}: {tp_price} <= current {current_price}")
                        return False
            
            logger.info("✅ Merge parameters validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error validating merge: {e}")
            return False


class FastPositionMerger(BasePositionMerger):
    """Handles merging of fast approach positions with same symbol"""
    
    def get_bot_order_patterns(self) -> List[str]:
        """Fast approach uses _FAST_TP, _FAST_SL patterns"""
        return ['_FAST_TP', '_FAST_SL', '_FAST_MARKET', 'TP_', 'SL_']
    
    def get_approach_name(self) -> str:
        """Return approach name"""
        return "fast"
    
    def _extract_tp_orders(self, orders: List[Dict]) -> List[Dict]:
        """Extract TP orders for fast approach (single TP)"""
        tp_orders = []
        for order in orders:
            order_link_id = order.get('orderLinkId', '')
            # Fast approach has single TP
            if ('_FAST_TP' in order_link_id or 
                order_link_id.startswith('TP_') or
                (order.get('stopOrderType') == 'TakeProfit' and order.get('reduceOnly'))):
                tp_orders.append(order)
        return tp_orders
    
    def _extract_sl_order(self, orders: List[Dict]) -> Optional[Dict]:
        """Extract SL order for fast approach"""
        for order in orders:
            order_link_id = order.get('orderLinkId', '')
            if ('_FAST_SL' in order_link_id or 
                order_link_id.startswith('SL_') or
                (order.get('stopOrderType') == 'StopLoss' and order.get('reduceOnly'))):
                return order
        return None
    
    def calculate_merged_parameters(self, 
                                  existing_data: Dict,
                                  new_params: Dict,
                                  side: str) -> Dict:
        """
        Calculate optimal merged parameters for fast approach (single TP/SL)
        
        For SHORT:
        - SL: Choose HIGHER price (more conservative)
        - TP: Choose LOWER price (more aggressive)
        
        For LONG:
        - SL: Choose LOWER price (more conservative) 
        - TP: Choose HIGHER price (more aggressive)
        """
        try:
            # Extract existing position data
            existing_position = existing_data['position']
            existing_tps = existing_data['tp_orders']
            existing_sl = existing_data['sl_order']
            
            # Calculate new position size
            existing_size = Decimal(str(existing_position.get('size', 0)))
            new_size = Decimal(str(new_params.get('position_size', 0)))
            merged_size = existing_size + new_size
            
            # Prepare merged parameters
            merged_params = {
                'merged_size': merged_size,
                'existing_size': existing_size,
                'new_size': new_size,
                'symbol': new_params['symbol'],
                'side': side,
                'leverage': new_params.get('leverage', existing_position.get('leverage')),
            }
            
            # Calculate merged stop loss
            if existing_sl and existing_sl.get('stopOrderType') == 'StopLoss':
                existing_sl_price = Decimal(str(existing_sl.get('triggerPrice', 0)))
                new_sl_price = Decimal(str(new_params.get('sl_price', 0)))
                
                if side == 'Sell':  # SHORT position
                    # Choose HIGHER stop loss (more conservative)
                    merged_params['sl_price'] = max(existing_sl_price, new_sl_price)
                    logger.info(f"🛡️ SHORT SL: Existing {existing_sl_price} vs New {new_sl_price} → Using {merged_params['sl_price']} (higher/safer)")
                else:  # LONG position  
                    # Choose LOWER stop loss (more conservative)
                    merged_params['sl_price'] = min(existing_sl_price, new_sl_price)
                    logger.info(f"🛡️ LONG SL: Existing {existing_sl_price} vs New {new_sl_price} → Using {merged_params['sl_price']} (lower/safer)")
            else:
                merged_params['sl_price'] = new_params.get('sl_price')
            
            # Calculate merged take profit (fast has single TP)
            if existing_tps and len(existing_tps) > 0:
                existing_tp = existing_tps[0]  # Fast only has one TP
                existing_tp_price = Decimal(str(existing_tp.get('triggerPrice', 0)))
                new_tp_price = Decimal(str(new_params.get('tp_price', 0)))
                
                if side == 'Sell':  # SHORT position
                    # Choose LOWER TP (more aggressive)
                    merged_params['tp_price'] = min(existing_tp_price, new_tp_price)
                    logger.info(f"🎯 SHORT TP: Existing {existing_tp_price} vs New {new_tp_price} → Using {merged_params['tp_price']} (lower/aggressive)")
                else:  # LONG position
                    # Choose HIGHER TP (more aggressive)
                    merged_params['tp_price'] = max(existing_tp_price, new_tp_price)
                    logger.info(f"🎯 LONG TP: Existing {existing_tp_price} vs New {new_tp_price} → Using {merged_params['tp_price']} (higher/aggressive)")
            else:
                merged_params['tp_price'] = new_params.get('tp_price')
            
            # Add other necessary parameters
            merged_params['tick_size'] = new_params.get('tick_size')
            merged_params['qty_step'] = new_params.get('qty_step')
            merged_params['approach'] = 'fast'
            
            logger.info(f"✅ Calculated merged parameters for {merged_size} {side} {new_params['symbol']} (FAST)")
            return merged_params
            
        except Exception as e:
            logger.error(f"Error calculating merged parameters: {e}")
            raise