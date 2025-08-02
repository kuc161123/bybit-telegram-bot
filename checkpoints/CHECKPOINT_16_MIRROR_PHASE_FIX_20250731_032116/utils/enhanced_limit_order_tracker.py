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
        # CACHE SYSTEM REMOVED - Direct API calls only for reliability
        # No caching to ensure real-time TP detection and position monitoring
        
        # Rate limiting to prevent API overload - 60 second intervals for reliability
        self.api_call_timestamps = {}  # order_id -> last API call timestamp
        self.min_call_interval = 60  # Minimum 60 seconds between API calls for same order
        
        # CONSERVATIVE: Intelligent rate limiting for stable positions (optional)
        self.position_activity_timestamps = {}  # position_key -> last activity timestamp
        self.stable_position_cache = {}  # position_key -> cached order data
        self.stable_position_cache_timestamps = {}  # position_key -> cache timestamp
        
        # Performance tracking (non-cache based)
        self.api_stats = {
            "total_api_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "last_reset": time.time()
        }
        
    def _is_position_stable(self, symbol: str, account_type: str) -> bool:
        """
        Conservative check if position is stable (no recent activity)
        Only for positions that haven't had fills or changes recently
        """
        from config.settings import STABLE_POSITION_THRESHOLD, STABLE_POSITION_CACHE_TTL
        
        position_key = f"{symbol}_{account_type}"
        current_time = time.time()
        
        # Check if position has recent activity
        last_activity = self.position_activity_timestamps.get(position_key, 0)
        stable_duration = current_time - last_activity
        
        # Position is stable if no activity for > STABLE_POSITION_THRESHOLD seconds
        return stable_duration > STABLE_POSITION_THRESHOLD
    
    def _get_stable_position_cache(self, symbol: str, account_type: str) -> Optional[Dict]:
        """Get cached data for stable positions"""
        from config.settings import STABLE_POSITION_CACHE_TTL
        
        position_key = f"{symbol}_{account_type}"
        current_time = time.time()
        
        if position_key in self.stable_position_cache:
            cache_time = self.stable_position_cache_timestamps.get(position_key, 0)
            if current_time - cache_time < STABLE_POSITION_CACHE_TTL:
                return self.stable_position_cache[position_key]
        
        return None
    
    def _set_stable_position_cache(self, symbol: str, account_type: str, data: Dict):
        """Cache data for stable positions"""
        position_key = f"{symbol}_{account_type}"
        current_time = time.time()
        
        self.stable_position_cache[position_key] = data
        self.stable_position_cache_timestamps[position_key] = current_time
    
    def _mark_position_activity(self, symbol: str, account_type: str):
        """Mark position as having recent activity (clears stable status)"""
        position_key = f"{symbol}_{account_type}"
        current_time = time.time()
        
        self.position_activity_timestamps[position_key] = current_time
        
        # Clear cache for positions with activity
        if position_key in self.stable_position_cache:
            del self.stable_position_cache[position_key]
        if position_key in self.stable_position_cache_timestamps:
            del self.stable_position_cache_timestamps[position_key]

    async def fetch_and_update_limit_order_details(
        self, 
        order_ids: List[str], 
        symbol: str,
        account_type: str = "main"
    ) -> Dict[str, Dict]:
        """
        Fetch full details for limit orders with DIRECT API calls
        CONSERVATIVE: Uses short-term caching for stable positions only
        
        Args:
            order_ids: List of order IDs to fetch
            symbol: Trading symbol
            account_type: 'main' or 'mirror'
            
        Returns:
            Dict mapping order_id to full order details
        """
        current_time = time.time()
        updated_orders = {}
        
        # CONSERVATIVE: Check if position is stable and can use brief caching
        is_stable = self._is_position_stable(symbol, account_type)
        if is_stable:
            cached_data = self._get_stable_position_cache(symbol, account_type)
            if cached_data:
                # Use cached data for stable positions
                for order_id in order_ids:
                    if order_id in cached_data:
                        updated_orders[order_id] = cached_data[order_id]
                
                if len(updated_orders) == len(order_ids):
                    logger.debug(f"📋 Used stable position cache for {symbol} ({account_type})")
                    return updated_orders
        
        # Track API performance
        self.api_stats["total_api_calls"] += len(order_ids)
        
        # Rate limiting to prevent API overload
        orders_to_fetch = []
        for order_id in order_ids:
            last_call = self.api_call_timestamps.get(order_id, 0)
            if current_time - last_call >= self.min_call_interval:
                orders_to_fetch.append(order_id)
                self.api_call_timestamps[order_id] = current_time
            else:
                logger.debug(f"⏱️ Rate limiting order {order_id[:8]}... (last call {current_time - last_call:.1f}s ago)")
        
        if not orders_to_fetch:
            # Reduced to DEBUG level to reduce log noise
            logger.debug(f"🚫 All {len(order_ids)} orders are rate limited - try again in 60s")
            return updated_orders
        
        # Only log if more than 2 orders to reduce noise
        if len(orders_to_fetch) > 2:
            logger.info(f"🔍 DIRECT API FETCH: {len(orders_to_fetch)} orders for {symbol} ({account_type})")
        else:
            logger.debug(f"🔍 Direct API fetch: {len(orders_to_fetch)} orders for {symbol} ({account_type})")
        
        # DIRECT API CALLS - No cache system
        client = bybit_client_2 if account_type == "mirror" else None
        
        # Batch process orders for efficiency
        if len(orders_to_fetch) > 3:
            try:
                batch_results = await self._fetch_batch_order_details_direct(
                    orders_to_fetch, symbol, client
                )
                for order_id, order_details in batch_results.items():
                    if order_details:
                        updated_orders[order_id] = order_details
                        self.api_stats["successful_calls"] += 1
                        logger.debug(
                            f"✅ Direct API: order {order_id[:8]}... "
                            f"Status: {order_details.get('orderStatus')} "
                            f"Filled: {order_details.get('cumExecQty', '0')}/{order_details.get('qty', '0')}"
                        )
                    else:
                        self.api_stats["failed_calls"] += 1
                        logger.debug(f"❌ Direct API: order {order_id[:8]}... not found")
                        
            except Exception as e:
                logger.warning(f"🔄 Batch API call failed, using individual requests: {e}")
                await self._process_orders_individually_direct(orders_to_fetch, symbol, client, updated_orders)
        else:
            # Process individually for small batches
            await self._process_orders_individually_direct(orders_to_fetch, symbol, client, updated_orders)
        
        # CONSERVATIVE: Cache results for stable positions only (very short TTL)
        if updated_orders and is_stable:
            self._set_stable_position_cache(symbol, account_type, updated_orders)
        
        # Detect activity: if any orders have changes, mark position as active
        if updated_orders:
            for order_id, order_data in updated_orders.items():
                # Check if order has recent activity (fills, cancellations, etc.)
                order_status = order_data.get('orderStatus', 'Unknown')
                cum_exec_qty = float(order_data.get('cumExecQty', '0'))
                
                if order_status in ['PartiallyFilled', 'Filled', 'Cancelled'] or cum_exec_qty > 0:
                    # Mark position as having activity
                    self._mark_position_activity(symbol, account_type)
                    break
                
        return updated_orders
    
    async def _fetch_batch_order_details_direct(
        self, 
        order_ids: List[str], 
        symbol: str,
        client=None
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch multiple orders using DIRECT API calls - NO CACHE
        """
        batch_results = {}
        account_type = "mirror" if client else "main"
        
        try:
            # DIRECT API CALL - Get all open orders for this symbol
            if client:
                # Mirror account
                from clients.bybit_helpers import api_call_with_retry
                response = await api_call_with_retry(
                    lambda: client.get_open_orders(
                        category="linear",
                        symbol=symbol
                    )
                )
            else:
                # Main account
                from clients.bybit_helpers import get_all_open_orders
                response = await get_all_open_orders()
            
            all_orders = response if isinstance(response, list) else []
            
            # Filter orders by symbol and match by ID
            for order_id in order_ids:
                found = False
                for order in all_orders:
                    if order.get("orderId") == order_id and order.get("symbol") == symbol:
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
            
            # Only log batch processing for larger batches
            if len(order_ids) > 3:
                logger.info(f"📦 Batch processed {len(order_ids)} orders for {symbol} ({account_type})")
            else:
                logger.debug(f"📦 Batch processed {len(order_ids)} orders for {symbol} ({account_type})")
            return batch_results
            
        except Exception as e:
            logger.error(f"❌ Direct API batch fetch failed: {e}")
            return {}
    
    async def _process_orders_individually_direct(
        self, 
        order_ids: List[str], 
        symbol: str, 
        client, 
        updated_orders: Dict
    ):
        """
        Process orders individually using DIRECT API calls - NO CACHE
        """
        for order_id in order_ids:
            try:
                # DIRECT API CALL - Fetch order details from exchange
                order_details = await self._fetch_single_order_details_direct(
                    order_id, symbol, client
                )
                
                if order_details:
                    updated_orders[order_id] = order_details
                    self.api_stats["successful_calls"] += 1
                    
                    logger.debug(
                        f"✅ DIRECT API: order {order_id[:8]}... "
                        f"Status: {order_details.get('orderStatus')} "
                        f"Filled: {order_details.get('cumExecQty', '0')}/{order_details.get('qty', '0')}"
                    )
                else:
                    self.api_stats["failed_calls"] += 1
                    logger.debug(f"❌ DIRECT API: order {order_id[:8]}... not found")
                    
            except Exception as e:
                self.api_stats["failed_calls"] += 1
                # Enhanced error context
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
    
    async def _fetch_single_order_details_direct(
        self, 
        order_id: str, 
        symbol: str,
        client=None
    ) -> Optional[Dict]:
        """
        Fetch details for a single order using DIRECT API calls - NO CACHE
        """
        try:
            # DIRECT API CALL - Check open orders first
            if client:
                # Mirror account
                from clients.bybit_helpers import api_call_with_retry
                open_response = await api_call_with_retry(
                    lambda: client.get_open_orders(
                        category="linear",
                        symbol=symbol
                    )
                )
            else:
                # Main account
                from clients.bybit_helpers import get_all_open_orders
                open_response = await get_all_open_orders()
            
            all_orders = open_response if isinstance(open_response, list) else []
            
            # Check if order is in open orders (filter by symbol)
            for order in all_orders:
                if order.get("orderId") == order_id and order.get("symbol") == symbol:
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
            
            # If not in open orders, check order history with DIRECT API
            if client:
                # Mirror account
                history_response = await api_call_with_retry(
                    lambda: client.get_order_history(
                        category="linear",
                        symbol=symbol,
                        orderId=order_id,  # Note: orderId (camelCase) for Bybit API
                        limit=50
                    )
                )
            else:
                # Main account
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
                logger.debug(f"🔍 DIRECT API: Order {order_id[:8]}... not found (likely completed)")
            else:
                logger.error(f"❌ DIRECT API error fetching order {order_id[:8]}...: {e}")
            
        # Order not found in either open orders or history
        logger.debug(f"🔍 DIRECT API: Order {order_id[:8]}... not found")
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
                
                # Log summary only for significant changes
                if filled_count > 0:
                    logger.info(f"✅ {monitor_key}: {filled_count} limit orders filled")
                elif active_count > 3:  # Only log active count if more than 3 orders
                    logger.debug(f"📊 {monitor_key}: {active_count} active limit orders")
                    
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
    
    def get_api_statistics(self) -> Dict:
        """Get comprehensive API performance statistics (NO CACHE)"""
        current_time = time.time()
        uptime = current_time - self.api_stats["last_reset"]
        
        total_calls = self.api_stats["total_api_calls"]
        successful_calls = self.api_stats["successful_calls"]
        failed_calls = self.api_stats["failed_calls"]
        
        success_rate = (successful_calls / total_calls * 100) if total_calls > 0 else 0
        
        return {
            "total_api_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "success_rate_percent": round(success_rate, 2),
            "uptime_minutes": round(uptime / 60, 2),
            "min_call_interval_seconds": self.min_call_interval,
            "tracked_orders": len(self.api_call_timestamps),
            "cache_system": "DISABLED - Direct API calls only"
        }
    
    def reset_api_statistics(self):
        """Reset API performance statistics"""
        self.api_stats = {
            "total_api_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "last_reset": time.time()
        }
        logger.info("🔄 API statistics reset - NO CACHE system active")


# Global instance
limit_order_tracker = EnhancedLimitOrderTracker()