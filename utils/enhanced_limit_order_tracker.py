#!/usr/bin/env python3
"""
Enhanced limit order tracking system for both main and mirror accounts.
Provides better visibility into limit order fills and accurate tracking.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import time

from clients.bybit_helpers import (
    get_open_orders, get_all_open_orders,
    api_call_with_retry
)
from execution.mirror_trader import bybit_client_2

logger = logging.getLogger(__name__)


class EnhancedLimitOrderTracker:
    """
    Enhanced limit order tracking with full order details and status monitoring
    """
    
    def __init__(self):
        self.order_cache = {}  # order_id -> full order details
        self.last_update = {}  # order_id -> last update timestamp
        self.cache_ttl = 30  # Cache for 30 seconds
        self.recent_check_cache = {}  # order_id -> last check timestamp
        self.check_throttle = 10  # Minimum 10 seconds between checks for same order
        
        # ENHANCED: Cache performance tracking
        self.cache_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls_saved": 0,
            "last_reset": time.time()
        }
        
        # ENHANCED: Frequently accessed orders for cache warming
        self.frequent_orders = {}  # order_id -> access_count
        self.cache_warming_threshold = 5  # Orders accessed 5+ times get cache priority
        
    async def fetch_and_update_limit_order_details(
        self, 
        order_ids: List[str], 
        symbol: str,
        account_type: str = "main"
    ) -> Dict[str, Dict]:
        """
        Fetch full details for limit orders and update their status
        
        Args:
            order_ids: List of order IDs to fetch
            symbol: Trading symbol
            account_type: 'main' or 'mirror'
            
        Returns:
            Dict mapping order_id to full order details
        """
        current_time = time.time()
        updated_orders = {}
        
        # ENHANCED: Track cache performance
        self.cache_stats["total_requests"] += len(order_ids)
        
        # ENHANCED: Track frequently accessed orders for cache warming
        for order_id in order_ids:
            self.frequent_orders[order_id] = self.frequent_orders.get(order_id, 0) + 1
        
        # PERFORMANCE OPTIMIZATION: Comprehensive cache-first strategy
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            
            # Try multiple cache sources for maximum hit rate
            cache_sources = [
                ('monitoring_cache', lambda: enhanced_tp_sl_manager._get_cached_open_orders(symbol, account_type)),
                ('execution_cache', lambda: enhanced_tp_sl_manager._get_cached_position_info(symbol, account_type))
            ]
            
            cache_hits = 0
            all_cached_orders = []
            
            # Aggregate orders from all cache sources
            for cache_name, cache_func in cache_sources:
                try:
                    cached_data = await cache_func()
                    if isinstance(cached_data, list):
                        all_cached_orders.extend(cached_data)
                    elif isinstance(cached_data, dict) and 'orders' in cached_data:
                        all_cached_orders.extend(cached_data['orders'])
                    logger.debug(f"📊 Retrieved {len(cached_data) if isinstance(cached_data, list) else 'N/A'} orders from {cache_name}")
                except Exception as cache_err:
                    logger.debug(f"Cache source {cache_name} unavailable: {cache_err}")
                    continue
            
            # Find orders that exist in the aggregated cached data
            for order_id in order_ids:
                found = False
                for cached_order in all_cached_orders:
                    if cached_order.get("orderId") == order_id:
                        order_status = cached_order.get("orderStatus", "New")
                        cum_exec_qty = cached_order.get("cumExecQty", "0")
                        
                        updated_orders[order_id] = {
                            "orderId": order_id,
                            "orderLinkId": cached_order.get("orderLinkId", ""),
                            "symbol": symbol,
                            "side": cached_order.get("side"),
                            "orderType": cached_order.get("orderType"),
                            "price": cached_order.get("price", "0"),
                            "qty": cached_order.get("qty", "0"),
                            "cumExecQty": cum_exec_qty,
                            "orderStatus": order_status,
                            "avgPrice": cached_order.get("avgPrice", "0"),
                            "createdTime": cached_order.get("createdTime", ""),
                            "updatedTime": cached_order.get("updatedTime", "")
                        }
                        cache_hits += 1
                        
                        # CRITICAL FIX: Special handling for unfilled limit orders
                        # These orders change frequently and need shorter cache TTL
                        if order_status in ["New", "PartiallyFilled", "PartialFilled"] and float(cum_exec_qty) == 0:
                            # Unfilled limit orders - use shorter cache TTL (15 seconds)
                            self.order_cache[order_id] = updated_orders[order_id]
                            self.last_update[order_id] = current_time
                            logger.debug(f"📊 Cached unfilled limit order {order_id[:8]}... with reduced TTL")
                        else:
                            # Filled or other orders - use normal cache TTL
                            self.order_cache[order_id] = updated_orders[order_id]
                            self.last_update[order_id] = current_time
                            logger.debug(f"📊 Cached order {order_id[:8]}... status: {order_status}")
                        
                        found = True
                        break
                
                # If not found in live cache, check local cache with dynamic TTL
                if not found and order_id in self.order_cache:
                    cache_age = current_time - self.last_update.get(order_id, 0)
                    cached_order = self.order_cache[order_id]
                    cached_status = cached_order.get("orderStatus", "New")
                    cached_cum_exec = float(cached_order.get("cumExecQty", "0"))
                    
                    # ENHANCED: Dynamic TTL based on order type and status
                    if cached_status in ["New", "PartiallyFilled", "PartialFilled"] and cached_cum_exec == 0:
                        # Unfilled limit orders - shorter TTL (15 seconds)
                        dynamic_ttl = 15
                        logger.debug(f"🔄 Unfilled limit order - using reduced TTL: {dynamic_ttl}s")
                    elif cached_status in ["Filled", "Cancelled"]:
                        # Final states - longer TTL (120 seconds)
                        dynamic_ttl = 120
                        logger.debug(f"📋 Final state order - using extended TTL: {dynamic_ttl}s")
                    else:
                        # Default TTL with load-based extension
                        dynamic_ttl = 60 if cache_hits > len(order_ids) * 0.7 else self.cache_ttl
                    
                    if cache_age < dynamic_ttl:
                        updated_orders[order_id] = cached_order
                        cache_hits += 1
                        logger.debug(f"🏪 Dynamic cache hit for order {order_id[:8]}... (age: {cache_age:.1f}s, TTL: {dynamic_ttl}s)")
            
            # Log cache effectiveness with improved metrics
            if cache_hits > 0:
                hit_rate = (cache_hits / len(order_ids)) * 100
                logger.info(f"🚀 Cache hit rate: {cache_hits}/{len(order_ids)} ({hit_rate:.1f}%) for {symbol} ({account_type})")
            
        except Exception as e:
            logger.debug(f"Cache strategy failed: {e}")
            cache_hits = 0
        
        # ENHANCED SMART BATCHING: Improved cache utilization
        orders_to_fetch = []
        cache_extensions = 0
        
        for order_id in order_ids:
            if order_id in updated_orders:
                continue  # Already found in cache
            
            # ENHANCED THROTTLING: More intelligent cache reuse
            last_check = self.recent_check_cache.get(order_id, 0)
            time_since_check = current_time - last_check
            
            if time_since_check < self.check_throttle:
                # Use cached data even if slightly stale during throttle period
                if order_id in self.order_cache:
                    cache_age = current_time - self.last_update.get(order_id, 0)
                    
                    # ENHANCED: Dynamic cache TTL based on system load
                    max_stale_age = 90  # Base: 90s stale data during throttle
                    if cache_hits > len(order_ids) * 0.8:  # High cache hit rate
                        max_stale_age = 120  # Allow 2 minutes for high-performing cache
                    
                    if cache_age < max_stale_age:
                        updated_orders[order_id] = self.order_cache[order_id]
                        cache_extensions += 1
                        logger.debug(f"⏱️ Extended cache for order {order_id[:8]}... (age: {cache_age:.1f}s, load-based)")
                        continue
            
            # ENHANCED: Check if order was recently marked as stale
            if hasattr(self, 'stale_order_ids') and order_id in self.stale_order_ids:
                # Skip fetching known stale orders to reduce API calls
                logger.debug(f"🗑️ Skipping known stale order {order_id[:8]}...")
                continue
            
            orders_to_fetch.append(order_id)
        
        # Log enhanced cache performance
        if cache_extensions > 0:
            logger.debug(f"🚀 Extended cache for {cache_extensions} orders to improve hit rate")
        
        # If no orders need fetching, return cached results
        if not orders_to_fetch:
            hit_rate = (len(updated_orders) / len(order_ids)) * 100
            logger.info(f"💾 All {len(order_ids)} orders served from cache ({hit_rate:.1f}% hit rate) - no API calls needed")
            return updated_orders
        
        # BATCH PROCESSING: Group orders by symbol/account for efficient API calls
        client = bybit_client_2 if account_type == "mirror" else None
        
        cache_count = len(order_ids) - len(orders_to_fetch)
        hit_rate = (cache_count / len(order_ids)) * 100
        logger.info(f"🔍 Fetching {len(orders_to_fetch)}/{len(order_ids)} orders from exchange ({hit_rate:.1f}% cache hit rate)")
        
        # PERFORMANCE OPTIMIZATION: Batch process orders to reduce API calls
        if len(orders_to_fetch) > 5:
            # Use batch processing for multiple orders
            try:
                batch_results = await self._fetch_batch_order_details(
                    orders_to_fetch, symbol, client
                )
                for order_id, order_details in batch_results.items():
                    if order_details:
                        # Update cache
                        self.order_cache[order_id] = order_details
                        self.last_update[order_id] = current_time
                        self.recent_check_cache[order_id] = current_time
                        updated_orders[order_id] = order_details
                        
                        logger.debug(
                            f"📊 Batch updated order {order_id[:8]}... "
                            f"Status: {order_details.get('orderStatus')} "
                            f"({account_type} account)"
                        )
                    else:
                        # Mark as stale for cleanup
                        if not hasattr(self, 'stale_order_ids'):
                            self.stale_order_ids = set()
                        self.stale_order_ids.add(order_id)
                        self.recent_check_cache[order_id] = current_time
                        
            except Exception as e:
                logger.warning(f"🔄 Batch processing failed, falling back to individual requests: {e}")
                # Fall back to individual processing
                await self._process_orders_individually(orders_to_fetch, symbol, client, updated_orders, current_time)
        else:
            # Process individually for small batches
            await self._process_orders_individually(orders_to_fetch, symbol, client, updated_orders, current_time)
        
        # Clean up stale orders from tracking (async to not block)
        if hasattr(self, 'stale_order_ids') and self.stale_order_ids:
            asyncio.create_task(self._async_cleanup_stale_orders())
                
        return updated_orders
    
    async def _fetch_batch_order_details(
        self, 
        order_ids: List[str], 
        symbol: str,
        client=None
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch multiple orders in batches to reduce API calls
        """
        batch_results = {}
        account_type = "mirror" if client else "main"
        
        try:
            # First try to get all orders for this symbol in one API call
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            all_orders = await enhanced_tp_sl_manager._get_cached_open_orders(symbol, account_type)
            
            # Check if we can get orders from the symbol query
            for order_id in order_ids:
                found = False
                for order in all_orders:
                    if order.get("orderId") == order_id:
                        batch_results[order_id] = {
                            "orderId": order_id,
                            "orderLinkId": order.get("orderLinkId", ""),
                            "symbol": symbol,
                            "side": order.get("side"),
                            "orderType": order.get("orderType"),
                            "price": order.get("price", "0"),
                            "qty": order.get("qty", "0"),
                            "cumExecQty": order.get("cumExecQty", "0"),
                            "orderStatus": order.get("orderStatus", "New"),
                            "avgPrice": order.get("avgPrice", "0"),
                            "createdTime": order.get("createdTime", ""),
                            "updatedTime": order.get("updatedTime", "")
                        }
                        found = True
                        break
                
                if not found:
                    batch_results[order_id] = None
            
            logger.info(f"📦 Batch processed {len(order_ids)} orders for {symbol} ({account_type})")
            return batch_results
            
        except Exception as e:
            logger.error(f"❌ Batch order fetch failed: {e}")
            # Return empty dict to trigger fallback
            return {}
    
    async def _process_orders_individually(
        self, 
        order_ids: List[str], 
        symbol: str, 
        client, 
        updated_orders: Dict, 
        current_time: float
    ):
        """
        Process orders individually with improved error handling
        """
        for order_id in order_ids:
            try:
                # Update recent check timestamp
                self.recent_check_cache[order_id] = current_time
                
                # Fetch order details from exchange
                order_details = await self._fetch_single_order_details(
                    order_id, symbol, client
                )
                
                if order_details:
                    # Update cache
                    self.order_cache[order_id] = order_details
                    self.last_update[order_id] = current_time
                    updated_orders[order_id] = order_details
                    
                    logger.debug(
                        f"📊 Updated limit order {order_id[:8]}... "
                        f"Status: {order_details.get('orderStatus')} "
                        f"Filled: {order_details.get('cumExecQty', '0')}/{order_details.get('qty', '0')}"
                    )
                else:
                    # Order not found - likely filled, cancelled, or expired
                    if not hasattr(self, 'stale_order_ids'):
                        self.stale_order_ids = set()
                    self.stale_order_ids.add(order_id)
                    
                    logger.debug(f"🔍 Order {order_id[:8]}... not found (likely filled/cancelled)")
                    
            except Exception as e:
                # Enhanced error context with better categorization
                error_str = str(e).lower()
                if any(term in error_str for term in ["timeout", "connection", "network"]):
                    logger.warning(f"🌐 Network issue fetching order {order_id[:8]}...: {e}")
                elif any(term in error_str for term in ["rate limit", "too many requests"]):
                    logger.warning(f"⏱️ Rate limit hit while fetching order {order_id[:8]}...: {e}")
                else:
                    logger.error(f"❌ Unexpected error fetching order {order_id[:8]}...: {e}")
    
    async def _async_cleanup_stale_orders(self):
        """
        Asynchronous cleanup of stale orders to prevent blocking
        """
        try:
            # Use thread pool executor for CPU-bound pickle operations
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._cleanup_stale_orders)
        except Exception as e:
            logger.error(f"❌ Async cleanup failed: {e}")
    
    async def _fetch_single_order_details(
        self, 
        order_id: str, 
        symbol: str,
        client=None
    ) -> Optional[Dict]:
        """
        Fetch details for a single order from exchange
        """
        try:
            # CRITICAL FIX: Use enhanced TP/SL manager's cached orders instead of direct API calls
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            account_type = "mirror" if client else "main"
            open_orders = await enhanced_tp_sl_manager._get_cached_open_orders(symbol, account_type)
            
            for order in open_orders:
                if order.get("orderId") == order_id:
                    return {
                        "orderId": order_id,
                        "orderLinkId": order.get("orderLinkId", ""),
                        "symbol": symbol,
                        "side": order.get("side"),
                        "orderType": order.get("orderType"),
                        "price": order.get("price", "0"),
                        "qty": order.get("qty", "0"),
                        "cumExecQty": order.get("cumExecQty", "0"),
                        "orderStatus": order.get("orderStatus", "New"),
                        "avgPrice": order.get("avgPrice", "0"),
                        "createdTime": order.get("createdTime", ""),
                        "updatedTime": order.get("updatedTime", "")
                    }
            
            # If not in open orders, check order history
            if client:
                # For mirror account, use client's method with api_call_with_retry
                history_response = await api_call_with_retry(
                    lambda: client.get_order_history(
                        category="linear",
                        symbol=symbol,
                        orderId=order_id,  # Note: orderId (camelCase) for Bybit API
                        limit=50
                    )
                )
            else:
                # For main account, use bybit_helpers function
                from clients.bybit_helpers import get_order_history
                history_response = await get_order_history(
                    symbol=symbol,
                    orderId=order_id  # Note: orderId (camelCase) for Bybit API
                )
            
            if history_response and history_response.get("list"):
                for order in history_response["list"]:
                    if order.get("orderId") == order_id:
                        return {
                            "orderId": order_id,
                            "orderLinkId": order.get("orderLinkId", ""),
                            "symbol": symbol,
                            "side": order.get("side"),
                            "orderType": order.get("orderType"),
                            "price": order.get("price", "0"),
                            "qty": order.get("qty", "0"),
                            "cumExecQty": order.get("cumExecQty", "0"),
                            "orderStatus": order.get("orderStatus", "Unknown"),
                            "avgPrice": order.get("avgPrice", "0"),
                            "createdTime": order.get("createdTime", ""),
                            "updatedTime": order.get("updatedTime", "")
                        }
                        
        except Exception as e:
            # Distinguish between API errors and expected "not found" scenarios
            error_str = str(e).lower()
            if any(term in error_str for term in ["not found", "invalid orderid", "order not exist"]):
                logger.debug(f"🔍 Order {order_id[:8]}... not found in exchange (likely completed)")
            else:
                logger.error(f"❌ API error fetching order {order_id[:8]}...: {e}")
            
        # Order not found in either open orders or history
        logger.debug(f"🔍 Order {order_id[:8]}... not found in open orders or history")
        return None
    
    def _cleanup_stale_orders(self):
        """
        Remove stale order IDs from monitor data to prevent repeated failed fetches
        ENHANCED: Added atomic file operations and corruption protection
        """
        try:
            # Get current monitor data with atomic file operations
            import pickle
            import os
            import tempfile
            
            pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
            
            # CRITICAL FIX: Create backup before reading to prevent corruption
            if os.path.exists(pickle_file):
                backup_file = f"{pickle_file}.backup_cleanup_{int(time.time())}"
                try:
                    import shutil
                    shutil.copy2(pickle_file, backup_file)
                    logger.debug(f"🔒 Created cleanup backup: {backup_file}")
                except Exception as backup_err:
                    logger.warning(f"⚠️ Could not create backup: {backup_err}")
            
            # ENHANCED: Robust pickle loading with retry and corruption detection
            max_retries = 3
            data = None
            
            for attempt in range(max_retries):
                try:
                    with open(pickle_file, 'rb') as f:
                        data = pickle.load(f)
                    break  # Success
                except (pickle.UnpicklingError, EOFError, OSError) as e:
                    if "truncated" in str(e).lower() or "eof" in str(e).lower():
                        logger.error(f"❌ Pickle corruption detected on attempt {attempt + 1}: {e}")
                        if attempt < max_retries - 1:
                            logger.info(f"🔄 Retrying pickle load in 1 second...")
                            time.sleep(1)
                        else:
                            logger.error(f"❌ Pickle file corrupted beyond recovery - skipping cleanup")
                            return
                    else:
                        raise  # Re-raise other exceptions
            
            if data is None:
                logger.error(f"❌ Could not load pickle data after {max_retries} attempts")
                return
            
            monitor_tasks = data.get('bot_data', {}).get('monitor_tasks', {})
            cleanup_count = 0
            
            for monitor_key, monitor_data in monitor_tasks.items():
                if 'limit_orders' in monitor_data:
                    original_count = len(monitor_data['limit_orders'])
                    
                    # Filter out stale orders
                    monitor_data['limit_orders'] = [
                        order for order in monitor_data['limit_orders']
                        if isinstance(order, dict) and 
                        order.get('order_id') not in self.stale_order_ids
                    ]
                    
                    removed_count = original_count - len(monitor_data['limit_orders'])
                    if removed_count > 0:
                        cleanup_count += removed_count
                        logger.info(f"🧹 Cleaned {removed_count} stale order(s) from {monitor_key}")
            
            # Save updated data if any cleanup occurred with atomic write
            if cleanup_count > 0:
                # CRITICAL FIX: Atomic write to prevent corruption
                temp_file = f"{pickle_file}.tmp_{int(time.time())}"
                try:
                    # Write to temporary file first
                    with open(temp_file, 'wb') as f:
                        pickle.dump(data, f)
                    
                    # Verify the temporary file is valid
                    with open(temp_file, 'rb') as f:
                        pickle.load(f)
                    
                    # Atomic replace
                    if os.name == 'nt':  # Windows
                        try:
                            os.remove(pickle_file)
                        except FileNotFoundError:
                            pass
                        os.rename(temp_file, pickle_file)
                    else:  # Unix/Linux/Mac
                        os.rename(temp_file, pickle_file)
                    
                    logger.info(f"✅ Cleaned up {cleanup_count} stale order references from monitor data")
                    
                except Exception as save_err:
                    logger.error(f"❌ Failed to save cleaned data: {save_err}")
                    # Clean up temp file
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    return
            
            # Clear the stale orders set
            self.stale_order_ids.clear()
            
            # Clean up old entries from recent check cache
            current_time = time.time()
            old_checks = [
                order_id for order_id, timestamp in self.recent_check_cache.items()
                if current_time - timestamp > self.check_throttle * 2  # Keep for 20 seconds
            ]
            for order_id in old_checks:
                del self.recent_check_cache[order_id]
            
            if old_checks:
                logger.debug(f"🧹 Cleaned {len(old_checks)} old check timestamps")
            
        except Exception as e:
            logger.error(f"Error during stale order cleanup: {e}")
    
    def update_monitor_limit_orders(
        self, 
        monitor_data: Dict, 
        order_details: Dict[str, Dict]
    ) -> Tuple[int, int]:
        """
        Update limit order information in monitor data with full details
        
        Returns:
            Tuple of (filled_count, active_count)
        """
        limit_orders = monitor_data.get("limit_orders", [])
        filled_count = 0
        active_count = 0
        
        # Update existing orders with details
        for i, limit_order in enumerate(limit_orders):
            if isinstance(limit_order, dict):
                order_id = limit_order.get("order_id")
                if order_id and order_id in order_details:
                    details = order_details[order_id]
                    
                    # Update with full details
                    limit_order["price"] = details.get("price", "0")
                    limit_order["quantity"] = details.get("qty", "0")
                    limit_order["filled_qty"] = details.get("cumExecQty", "0")
                    limit_order["avg_fill_price"] = details.get("avgPrice", "0")
                    limit_order["order_link_id"] = details.get("orderLinkId", "")
                    
                    # Update status based on exchange data
                    order_status = details.get("orderStatus", "Unknown")
                    if order_status == "Filled":
                        limit_order["status"] = "FILLED"
                        limit_order["filled_at"] = time.time()
                        filled_count += 1
                    elif order_status in ["PartiallyFilled", "PartialFilled"]:
                        limit_order["status"] = "PARTIAL"
                        active_count += 1
                    elif order_status == "Cancelled":
                        limit_order["status"] = "CANCELLED"
                    elif order_status in ["New", "Created"]:
                        limit_order["status"] = "ACTIVE"
                        active_count += 1
                    else:
                        limit_order["status"] = order_status.upper()
                        
                    logger.debug(
                        f"Updated limit order {order_id[:8]}... "
                        f"Status: {limit_order['status']} "
                        f"Filled: {limit_order.get('filled_qty', '0')}/{limit_order.get('quantity', '0')}"
                    )
        
        # Update monitor tracking fields
        monitor_data["limit_orders_filled"] = filled_count
        monitor_data["limit_orders_active"] = active_count
        monitor_data["limit_order_update_time"] = time.time()
        
        return filled_count, active_count
    
    async def check_and_update_all_limit_orders(
        self, 
        monitors: Dict[str, Dict]
    ) -> Dict[str, Tuple[int, int]]:
        """
        Check and update limit orders for all monitors
        
        Returns:
            Dict mapping monitor_key to (filled_count, active_count)
        """
        results = {}
        
        for monitor_key, monitor_data in monitors.items():
            try:
                limit_orders = monitor_data.get("limit_orders", [])
                if not limit_orders:
                    continue
                    
                # Extract order IDs
                order_ids = []
                for order in limit_orders:
                    if isinstance(order, dict) and order.get("order_id"):
                        order_ids.append(order["order_id"])
                
                if not order_ids:
                    continue
                
                # Determine account type
                account_type = monitor_data.get("account_type", "main")
                symbol = monitor_data.get("symbol")
                
                if not symbol:
                    logger.warning(f"No symbol found for monitor {monitor_key}")
                    continue
                
                # Fetch and update order details
                order_details = await self.fetch_and_update_limit_order_details(
                    order_ids, symbol, account_type
                )
                
                # Update monitor data
                filled_count, active_count = self.update_monitor_limit_orders(
                    monitor_data, order_details
                )
                
                results[monitor_key] = (filled_count, active_count)
                
                # Log summary
                if filled_count > 0 or active_count > 0:
                    logger.info(
                        f"📊 Limit orders for {monitor_key}: "
                        f"{filled_count} filled, {active_count} active"
                    )
                    
            except Exception as e:
                logger.error(f"Error updating limit orders for {monitor_key}: {e}")
                
        return results
    
    def get_limit_order_summary(self, monitor_data: Dict) -> str:
        """
        Get a formatted summary of limit orders for alerts with synchronized counting
        """
        limit_orders = monitor_data.get("limit_orders", [])
        if not limit_orders:
            return "No limit orders"
        
        filled = []
        active = []
        cancelled = []
        
        for order in limit_orders:
            if isinstance(order, dict):
                status = order.get("status", "UNKNOWN")
                price = order.get("price", "?")
                qty = order.get("quantity", "?")
                filled_qty = order.get("filled_qty", "0")
                
                order_info = f"${price} ({filled_qty}/{qty})"
                
                if status == "FILLED":
                    filled.append(order_info)
                elif status in ["ACTIVE", "PARTIAL"]:
                    active.append(order_info)
                elif status == "CANCELLED":
                    cancelled.append(order_info)
        
        # ENHANCEMENT: Use synchronized fill count if available
        synchronized_fill_count = monitor_data.get('limit_orders_filled', len(filled))
        if synchronized_fill_count != len(filled) and synchronized_fill_count > 0:
            # Use synchronized count for consistency
            filled_display_count = synchronized_fill_count
        else:
            filled_display_count = len(filled)
        
        summary_parts = []
        if filled_display_count > 0:
            if filled:
                summary_parts.append(f"Filled: {filled_display_count} [{', '.join(filled[:2])}{'...' if len(filled) > 2 else ''}]")
            else:
                summary_parts.append(f"Filled: {filled_display_count} [Synchronized count]")
        if active:
            summary_parts.append(f"Active: {len(active)} [{', '.join(active[:2])}{'...' if len(active) > 2 else ''}]")
        if cancelled:
            summary_parts.append(f"Cancelled: {len(cancelled)}")
            
        return " | ".join(summary_parts) if summary_parts else "No active limit orders"
    
    def get_synchronized_fill_count(self, monitor_data: Dict) -> int:
        """
        Get the synchronized fill count for consistent alerts across accounts
        """
        # Check if monitor data has a synchronized count
        synchronized_count = monitor_data.get('limit_orders_filled', 0)
        
        # Fallback to counting filled orders
        if synchronized_count == 0:
            limit_orders = monitor_data.get("limit_orders", [])
            filled_count = 0
            for order in limit_orders:
                if isinstance(order, dict) and order.get("status") == "FILLED":
                    filled_count += 1
            return filled_count
        
        return synchronized_count
    
    def get_cache_statistics(self) -> Dict:
        """Get comprehensive cache performance statistics"""
        current_time = time.time()
        uptime = current_time - self.cache_stats["last_reset"]
        
        total_requests = self.cache_stats["total_requests"]
        cache_hits = self.cache_stats["cache_hits"]
        
        hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        # Analyze frequently accessed orders
        frequent_count = len([order_id for order_id, count in self.frequent_orders.items() 
                            if count >= self.cache_warming_threshold])
        
        # Calculate cache efficiency
        cache_size = len(self.order_cache)
        stale_orders = len(getattr(self, 'stale_order_ids', set()))
        
        return {
            "total_requests": total_requests,
            "cache_hits": cache_hits,
            "cache_misses": self.cache_stats["cache_misses"],
            "hit_rate_percent": round(hit_rate, 2),
            "api_calls_saved": self.cache_stats["api_calls_saved"],
            "cache_size": cache_size,
            "frequent_orders": frequent_count,
            "stale_orders": stale_orders,
            "uptime_minutes": round(uptime / 60, 2),
            "cache_ttl_seconds": self.cache_ttl,
            "check_throttle_seconds": self.check_throttle
        }
    
    def reset_cache_statistics(self):
        """Reset cache performance statistics"""
        self.cache_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "api_calls_saved": 0,
            "last_reset": time.time()
        }
        logger.info("🔄 Cache statistics reset")
    
    def optimize_cache_for_unfilled_orders(self, symbol: str = None):
        """
        Optimize cache specifically for unfilled limit orders
        These orders change frequently and benefit from different caching strategies
        """
        try:
            current_time = time.time()
            unfilled_optimized = 0
            
            for order_id, order_data in self.order_cache.items():
                if symbol and order_data.get("symbol") != symbol:
                    continue
                
                status = order_data.get("orderStatus", "New")
                cum_exec = float(order_data.get("cumExecQty", "0"))
                
                # Identify unfilled limit orders
                if status in ["New", "PartiallyFilled", "PartialFilled"] and cum_exec == 0:
                    # Mark for more frequent updates
                    self.frequent_orders[order_id] = self.frequent_orders.get(order_id, 0) + 1
                    unfilled_optimized += 1
            
            if unfilled_optimized > 0:
                logger.info(f"🔧 Optimized cache for {unfilled_optimized} unfilled limit orders")
                
        except Exception as e:
            logger.error(f"❌ Cache optimization failed: {e}")


# Global instance
limit_order_tracker = EnhancedLimitOrderTracker()