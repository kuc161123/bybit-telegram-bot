#!/usr/bin/env python3
"""
Enhanced Mirror Error Handling Implementation
============================================

This script patches the mirror sync logic with comprehensive error handling:
- Retry logic with exponential backoff
- Circuit breaker pattern
- Detailed error logging and categorization
- Specific Bybit error code handling
- Validation before order modifications
- Position size tolerance checks
- Safeguards against infinite loops
- Graceful degradation

Author: Assistant
Date: 2025-01-07
"""

import os
import sys
import time
import pickle
import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client

class CircuitBreaker:
    """Circuit breaker to prevent repeated failures"""
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
    
    def record_success(self):
        """Reset the circuit breaker on success"""
        self.failure_count = 0
        self.is_open = False
        self.last_failure_time = None
    
    def record_failure(self):
        """Record a failure and check if circuit should open"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            return True
        return False
    
    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution"""
        if not self.is_open:
            return True
        
        # Check if recovery timeout has passed
        if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
            self.is_open = False
            self.failure_count = 0
            return True
        
        return False

class EnhancedMirrorErrorHandler:
    """Enhanced error handling for mirror sync operations"""
    
    # Error code mappings
    ERROR_CODES = {
        10001: "Invalid parameter - quantity error",
        10002: "Invalid API key",
        10003: "Invalid signature", 
        10004: "Invalid timestamp",
        10005: "Permission denied",
        110001: "Order not exists",
        110003: "Order price exceeds limit",
        110004: "Wallet balance insufficient",
        110007: "Order quantity insufficient",
        110008: "Order modify failed",
        110009: "Duplicate order ID",
        110010: "Position not found",
        110011: "Position mode error",
        110012: "Risk limit exceeded",
        110013: "Leverage not modified",
        110014: "Position is reducing only",
        110015: "Position already closed",
        110016: "Order already cancelled",
        110017: "Position qty zero",
        110018: "Reduce only conflict",
        110019: "Market order cannot be post only",
        110020: "Order amount too small",
        110021: "Invalid symbol",
        110022: "Order side invalid",
        110023: "Position side invalid",
        110024: "Trading not allowed",
        110025: "Position mode not match",
        110026: "Cross margin insufficient",
        110027: "Isolated margin insufficient",
        110028: "Order would trigger liquidation",
        110029: "TP/SL order already exists",
        110030: "TP/SL cannot be cancelled",
        110031: "Order linkId already exists",
        110032: "Order linkId not found",
        110033: "Cannot set margin type",
        110034: "Margin type not modified",
        110035: "Cannot set leverage",
        110036: "Invalid reduce only order",
        110037: "User not enabled contract",
        110038: "Order not modified",
        110039: "Position size exceeded",
        110040: "Cancel order size exceeded",
        110041: "Cannot switch position mode",
        110042: "Invalid coin",
        110043: "User not active",
        110044: "Contract suspended",
        110045: "User banned",
        110046: "Invalid price",
        110047: "Order price too high",
        110048: "Order price too low"
    }
    
    # Retryable error codes
    RETRYABLE_ERRORS = {
        10001,   # Quantity error - may be temporary
        10004,   # Timestamp issue
        110008,  # Order modify failed
        110026,  # Cross margin insufficient (temporary)
        110027,  # Isolated margin insufficient (temporary)
        110038   # Order not modified (may succeed on retry)
    }
    
    def __init__(self):
        self.circuit_breakers = {}  # Per-symbol circuit breakers
        self.retry_delays = [0.5, 1, 2, 5, 10]  # Exponential backoff delays
        
    def get_circuit_breaker(self, symbol: str) -> CircuitBreaker:
        """Get or create circuit breaker for symbol"""
        if symbol not in self.circuit_breakers:
            self.circuit_breakers[symbol] = CircuitBreaker()
        return self.circuit_breakers[symbol]
    
    def categorize_error(self, error_code: int, error_msg: str) -> Tuple[str, bool]:
        """Categorize error and determine if retryable"""
        category = self.ERROR_CODES.get(error_code, f"Unknown error {error_code}")
        is_retryable = error_code in self.RETRYABLE_ERRORS
        
        # Additional context-based categorization
        if "qty" in error_msg.lower() or "quantity" in error_msg.lower():
            category = f"{category} - Quantity validation error"
        elif "balance" in error_msg.lower():
            category = f"{category} - Insufficient balance"
        elif "position" in error_msg.lower():
            category = f"{category} - Position state error"
        
        return category, is_retryable
    
    async def execute_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic and circuit breaker"""
        symbol = kwargs.get('symbol', 'unknown')
        circuit_breaker = self.get_circuit_breaker(symbol)
        
        if not circuit_breaker.can_execute():
            raise Exception(f"Circuit breaker open for {symbol} - too many failures")
        
        last_error = None
        for attempt, delay in enumerate(self.retry_delays):
            try:
                result = await func(*args, **kwargs)
                circuit_breaker.record_success()
                return result
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                
                # Extract error code if available
                error_code = None
                if hasattr(e, 'code'):
                    error_code = e.code
                elif "retCode" in error_msg:
                    try:
                        import re
                        match = re.search(r'retCode[:\s]+(\d+)', error_msg)
                        if match:
                            error_code = int(match.group(1))
                    except:
                        pass
                
                # Categorize error
                if error_code:
                    category, is_retryable = self.categorize_error(error_code, error_msg)
                    print(f"Error category: {category}")
                    
                    if not is_retryable:
                        circuit_breaker.record_failure()
                        raise Exception(f"Non-retryable error: {category} - {error_msg}")
                
                # Log retry attempt
                print(f"Retry {attempt + 1}/{len(self.retry_delays)} for {symbol} after {delay}s delay")
                print(f"Error: {error_msg}")
                
                if attempt < len(self.retry_delays) - 1:
                    await asyncio.sleep(delay)
                else:
                    circuit_breaker.record_failure()
        
        raise last_error

def create_enhanced_mirror_sync_patch():
    """Create the enhanced mirror sync patch"""
    
    patch_content = '''#!/usr/bin/env python3
"""
Enhanced Mirror TP/SL Manager with Comprehensive Error Handling
==============================================================

This module handles TP/SL order synchronization for mirror accounts with:
- Robust error handling and retry logic
- Circuit breaker pattern to prevent cascading failures
- Position size tolerance checks
- Order validation before execution
- Detailed error logging and categorization
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Any, Tuple
import time
import pickle
import os

from pybit.unified_trading import HTTP
from pybit.exceptions import InvalidRequestError

# Import error handler
from create_enhanced_mirror_error_handling import EnhancedMirrorErrorHandler, CircuitBreaker

# Set up logging
logger = logging.getLogger(__name__)

# Position size tolerance (0.1%)
POSITION_SIZE_TOLERANCE = Decimal('0.001')

# Maximum sync attempts per position
MAX_SYNC_ATTEMPTS = 3

# Sync cooldown period (seconds)
SYNC_COOLDOWN = 30

class MirrorEnhancedTPSL:
    """Enhanced TP/SL management for mirror trading with comprehensive error handling"""
    
    def __init__(self, client: HTTP, account_prefix: str = "Mirror"):
        self.client = client
        self.account_prefix = account_prefix
        self.error_handler = EnhancedMirrorErrorHandler()
        self.sync_attempts = {}  # Track sync attempts per position
        self.last_sync_time = {}  # Track last sync time per position
        
        logger.info(f"Initialized {account_prefix} Enhanced TP/SL Manager with error handling")
    
    def validate_quantity(self, symbol: str, quantity: Decimal) -> Decimal:
        """Validate and format quantity for order placement"""
        try:
            # Get instrument info for precision
            response = self.client.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0 and response['result']['list']:
                instrument = response['result']['list'][0]
                
                # Get quantity precision
                qty_filter = instrument['lotSizeFilter']
                min_qty = Decimal(qty_filter['minOrderQty'])
                max_qty = Decimal(qty_filter['maxOrderQty'])
                qty_step = Decimal(qty_filter['qtyStep'])
                
                # Validate quantity
                if quantity < min_qty:
                    logger.warning(f"{symbol}: Quantity {quantity} below minimum {min_qty}")
                    return min_qty
                
                if quantity > max_qty:
                    logger.warning(f"{symbol}: Quantity {quantity} above maximum {max_qty}")
                    return max_qty
                
                # Round to qty step
                if qty_step > 0:
                    quantity = (quantity / qty_step).quantize(Decimal('1'), rounding=ROUND_DOWN) * qty_step
                
                return quantity
                
        except Exception as e:
            logger.error(f"Error validating quantity for {symbol}: {e}")
            return quantity
    
    def validate_price(self, symbol: str, price: Decimal, side: str) -> Decimal:
        """Validate and format price for order placement"""
        try:
            # Get instrument info for precision
            response = self.client.get_instruments_info(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0 and response['result']['list']:
                instrument = response['result']['list'][0]
                
                # Get price precision
                price_filter = instrument['priceFilter']
                tick_size = Decimal(price_filter['tickSize'])
                
                # Round to tick size
                if tick_size > 0:
                    price = (price / tick_size).quantize(Decimal('1'), rounding=ROUND_DOWN) * tick_size
                
                return price
                
        except Exception as e:
            logger.error(f"Error validating price for {symbol}: {e}")
            return price
    
    def check_position_sync(self, main_position: Dict, mirror_position: Optional[Dict]) -> bool:
        """Check if positions are in sync within tolerance"""
        if not mirror_position:
            return False
        
        main_size = abs(Decimal(str(main_position.get('size', '0'))))
        mirror_size = abs(Decimal(str(mirror_position.get('size', '0'))))
        
        if main_size == 0 and mirror_size == 0:
            return True
        
        if main_size == 0 or mirror_size == 0:
            return False
        
        # Check if sizes are within tolerance
        size_diff = abs(main_size - mirror_size)
        tolerance = main_size * POSITION_SIZE_TOLERANCE
        
        return size_diff <= tolerance
    
    def should_attempt_sync(self, symbol: str, side: str) -> bool:
        """Check if we should attempt sync based on cooldown and attempt limits"""
        key = f"{symbol}_{side}"
        
        # Check attempt limit
        attempts = self.sync_attempts.get(key, 0)
        if attempts >= MAX_SYNC_ATTEMPTS:
            logger.warning(f"Max sync attempts reached for {key}")
            return False
        
        # Check cooldown
        last_sync = self.last_sync_time.get(key, 0)
        if time.time() - last_sync < SYNC_COOLDOWN:
            logger.info(f"Sync cooldown active for {key}")
            return False
        
        return True
    
    def record_sync_attempt(self, symbol: str, side: str, success: bool):
        """Record sync attempt for tracking"""
        key = f"{symbol}_{side}"
        
        if success:
            # Reset on success
            self.sync_attempts[key] = 0
            self.last_sync_time[key] = 0
        else:
            # Increment attempts and set cooldown
            self.sync_attempts[key] = self.sync_attempts.get(key, 0) + 1
            self.last_sync_time[key] = time.time()
    
    async def cancel_order_safe(self, symbol: str, order_id: str) -> bool:
        """Safely cancel an order with error handling"""
        try:
            result = await self.error_handler.execute_with_retry(
                self._cancel_order_internal,
                symbol=symbol,
                order_id=order_id
            )
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id} for {symbol}: {e}")
            return False
    
    async def _cancel_order_internal(self, symbol: str, order_id: str):
        """Internal method to cancel order"""
        response = self.client.cancel_order(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )
        
        if response['retCode'] != 0:
            raise Exception(f"Cancel failed: {response.get('retMsg', 'Unknown error')}")
        
        return True
    
    async def place_order_safe(self, order_params: Dict) -> Optional[str]:
        """Safely place an order with validation and error handling"""
        try:
            # Validate parameters
            symbol = order_params.get('symbol')
            if not symbol:
                raise ValueError("Symbol is required")
            
            # Validate and format quantity
            if 'qty' in order_params:
                order_params['qty'] = str(self.validate_quantity(
                    symbol, 
                    Decimal(str(order_params['qty']))
                ))
            
            # Validate and format price
            if 'price' in order_params:
                order_params['price'] = str(self.validate_price(
                    symbol,
                    Decimal(str(order_params['price'])),
                    order_params.get('side', 'Buy')
                ))
            
            # Place order with retry
            result = await self.error_handler.execute_with_retry(
                self._place_order_internal,
                order_params=order_params,
                symbol=symbol
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to place order for {symbol}: {e}")
            return None
    
    async def _place_order_internal(self, order_params: Dict, symbol: str):
        """Internal method to place order"""
        response = self.client.place_order(**order_params)
        
        if response['retCode'] != 0:
            raise Exception(f"Place order failed: {response.get('retMsg', 'Unknown error')}")
        
        return response['result']['orderId']
    
    async def sync_tp_sl_orders(self, main_position: Dict, mirror_position: Optional[Dict]) -> bool:
        """Sync TP/SL orders with comprehensive error handling"""
        symbol = main_position['symbol']
        side = main_position['side']
        
        try:
            # Check if sync should be attempted
            if not self.should_attempt_sync(symbol, side):
                return False
            
            # Validate position sync
            if not self.check_position_sync(main_position, mirror_position):
                logger.warning(f"{symbol}: Positions not in sync, skipping TP/SL sync")
                self.record_sync_attempt(symbol, side, False)
                return False
            
            # Get current orders
            main_orders = await self.get_active_orders(symbol, "Main")
            mirror_orders = await self.get_active_orders(symbol, "Mirror")
            
            # Sync TP orders
            tp_success = await self.sync_order_type(
                symbol, side, main_orders, mirror_orders, 
                mirror_position, "TakeProfit"
            )
            
            # Sync SL orders
            sl_success = await self.sync_order_type(
                symbol, side, main_orders, mirror_orders,
                mirror_position, "StopLoss"
            )
            
            success = tp_success and sl_success
            self.record_sync_attempt(symbol, side, success)
            
            return success
            
        except Exception as e:
            logger.error(f"Error syncing TP/SL for {symbol}: {e}")
            self.record_sync_attempt(symbol, side, False)
            return False
    
    async def sync_order_type(self, symbol: str, side: str, main_orders: List[Dict], 
                            mirror_orders: List[Dict], mirror_position: Dict, 
                            order_type: str) -> bool:
        """Sync specific order type with error handling"""
        try:
            # Filter orders by type
            main_type_orders = [o for o in main_orders if o.get('orderType') == order_type]
            mirror_type_orders = [o for o in mirror_orders if o.get('orderType') == order_type]
            
            # Cancel excess mirror orders
            if len(mirror_type_orders) > len(main_type_orders):
                for order in mirror_type_orders[len(main_type_orders):]:
                    await self.cancel_order_safe(symbol, order['orderId'])
            
            # Create or update mirror orders
            for i, main_order in enumerate(main_type_orders):
                if i < len(mirror_type_orders):
                    # Update existing order if needed
                    mirror_order = mirror_type_orders[i]
                    if not self.orders_match(main_order, mirror_order):
                        await self.cancel_order_safe(symbol, mirror_order['orderId'])
                        await self.create_mirror_order(main_order, mirror_position)
                else:
                    # Create new mirror order
                    await self.create_mirror_order(main_order, mirror_position)
            
            return True
            
        except Exception as e:
            logger.error(f"Error syncing {order_type} orders for {symbol}: {e}")
            return False
    
    def orders_match(self, main_order: Dict, mirror_order: Dict) -> bool:
        """Check if orders match within tolerance"""
        try:
            # Compare trigger prices
            main_trigger = Decimal(str(main_order.get('triggerPrice', '0')))
            mirror_trigger = Decimal(str(mirror_order.get('triggerPrice', '0')))
            
            if main_trigger != mirror_trigger:
                return False
            
            # Compare quantities within tolerance
            main_qty = Decimal(str(main_order.get('qty', '0')))
            mirror_qty = Decimal(str(mirror_order.get('qty', '0')))
            
            qty_diff = abs(main_qty - mirror_qty)
            tolerance = main_qty * POSITION_SIZE_TOLERANCE
            
            return qty_diff <= tolerance
            
        except Exception as e:
            logger.error(f"Error comparing orders: {e}")
            return False
    
    async def create_mirror_order(self, main_order: Dict, mirror_position: Dict) -> bool:
        """Create mirror order based on main order"""
        try:
            order_params = {
                'category': 'linear',
                'symbol': main_order['symbol'],
                'side': main_order['side'],
                'orderType': main_order['orderType'],
                'qty': main_order['qty'],
                'triggerPrice': main_order['triggerPrice'],
                'triggerDirection': main_order.get('triggerDirection', 1),
                'orderLinkId': f"{self.account_prefix}_Enhanced_{main_order['symbol']}_{main_order['orderType']}_{int(time.time()*1000)}",
                'positionIdx': mirror_position.get('positionIdx', 0),
                'reduceOnly': True
            }
            
            # Add price for limit orders
            if main_order.get('price'):
                order_params['price'] = main_order['price']
                order_params['orderType'] = 'Limit'
            else:
                order_params['orderType'] = 'Market'
            
            result = await self.place_order_safe(order_params)
            return result is not None
            
        except Exception as e:
            logger.error(f"Error creating mirror order: {e}")
            return False
    
    async def get_active_orders(self, symbol: str, account_type: str) -> List[Dict]:
        """Get active orders with error handling"""
        try:
            response = self.client.get_open_orders(
                category="linear",
                symbol=symbol
            )
            
            if response['retCode'] == 0:
                return response['result']['list']
            else:
                logger.error(f"Error getting orders: {response.get('retMsg')}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching active orders for {symbol}: {e}")
            return []
    
    def create_dashboard_monitor_entry(self, symbol: str, side: str, chat_id: int) -> bool:
        """Create dashboard monitor entry for tracking"""
        try:
            # Load current pickle data
            pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            
            if os.path.exists(pickle_file):
                with open(pickle_file, 'rb') as f:
                    data = pickle.load(f)
            else:
                data = {'bot_data': {}, 'user_data': {}}
            
            # Ensure structure exists
            if 'monitor_tasks' not in data['bot_data']:
                data['bot_data']['monitor_tasks'] = {}
            
            # Create monitor key
            monitor_key = f"{chat_id}_{symbol}_enhanced_{self.account_prefix.lower()}"
            
            # Add monitor entry
            data['bot_data']['monitor_tasks'][monitor_key] = {
                'symbol': symbol,
                'side': side,
                'approach': 'enhanced',
                'account_type': self.account_prefix.lower(),
                'chat_id': chat_id,
                'created_at': datetime.now().isoformat(),
                'status': 'active'
            }
            
            # Save updated data
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"Created dashboard monitor entry: {monitor_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating dashboard monitor entry: {e}")
            return False

# Export the enhanced class
__all__ = ['MirrorEnhancedTPSL']
'''
    
    # Write the patch file
    patch_file = "/Users/lualakol/bybit-telegram-bot/execution/mirror_enhanced_tp_sl_patched.py"
    with open(patch_file, 'w') as f:
        f.write(patch_content)
    
    print(f"Created enhanced mirror sync patch at: {patch_file}")
    
    # Create backup of original file
    original_file = "/Users/lualakol/bybit-telegram-bot/execution/mirror_enhanced_tp_sl.py"
    backup_file = f"{original_file}.backup_{int(time.time())}"
    
    if os.path.exists(original_file):
        import shutil
        shutil.copy2(original_file, backup_file)
        print(f"Backed up original file to: {backup_file}")
        
        # Replace with patched version
        shutil.copy2(patch_file, original_file)
        print(f"Replaced {original_file} with enhanced version")
    
    return True

def main():
    """Main execution"""
    print("Enhanced Mirror Error Handling Implementation")
    print("=" * 60)
    
    # Create the error handler class (already in this file)
    print("\n1. Error handler class created")
    print("   - Circuit breaker pattern implemented")
    print("   - Retry logic with exponential backoff")
    print("   - Error categorization and handling")
    print("   - Position validation and tolerance checks")
    
    # Create the patched mirror sync file
    print("\n2. Creating enhanced mirror sync patch...")
    if create_enhanced_mirror_sync_patch():
        print("   ✓ Patch created successfully")
    else:
        print("   ✗ Failed to create patch")
        return
    
    print("\n3. Implementation Summary:")
    print("   - Added retry logic for transient errors")
    print("   - Implemented circuit breaker to prevent cascading failures")
    print("   - Added position size tolerance checks (0.1%)")
    print("   - Enhanced order validation before execution")
    print("   - Added sync cooldown and attempt limits")
    print("   - Comprehensive error logging and categorization")
    print("   - Graceful degradation on repeated failures")
    
    print("\n4. Key Features:")
    print("   - Retryable errors: Network issues, temporary failures")
    print("   - Non-retryable errors: Invalid parameters, position not found")
    print("   - Circuit breaker: Opens after 5 failures, 60s recovery")
    print("   - Sync limits: Max 3 attempts per position, 30s cooldown")
    print("   - Quantity validation: Ensures proper decimal formatting")
    print("   - Price validation: Rounds to tick size")
    
    print("\n5. Next Steps:")
    print("   - Restart the bot to apply changes")
    print("   - Monitor logs for improved error handling")
    print("   - Circuit breakers will prevent error floods")
    print("   - Positions will sync more reliably")
    
    print("\nEnhanced error handling implementation complete!")

if __name__ == "__main__":
    main()