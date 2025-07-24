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
        
        # CRITICAL FIX: Use enhanced TP/SL manager's monitoring cache FIRST
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            cached_orders = await enhanced_tp_sl_manager._get_cached_open_orders(symbol, account_type)
            cache_hits = 0
            
            # Find orders that exist in the cached data
            for order_id in order_ids:
                for cached_order in cached_orders:
                    if cached_order.get("orderId") == order_id:
                        updated_orders[order_id] = {
                            "orderId": order_id,
                            "orderLinkId": cached_order.get("orderLinkId", ""),
                            "symbol": symbol,
                            "side": cached_order.get("side"),
                            "orderType": cached_order.get("orderType"),
                            "price": cached_order.get("price", "0"),
                            "qty": cached_order.get("qty", "0"),
                            "cumExecQty": cached_order.get("cumExecQty", "0"),
                            "orderStatus": cached_order.get("orderStatus", "New"),
                            "avgPrice": cached_order.get("avgPrice", "0"),
                            "createdTime": cached_order.get("createdTime", ""),
                            "updatedTime": cached_order.get("updatedTime", "")
                        }
                        cache_hits += 1
                        break
            
            # Log cache effectiveness
            if cache_hits > 0:
                logger.info(f"🚀 Cache hit: Found {cache_hits}/{len(order_ids)} orders in monitoring cache for {symbol} ({account_type})")
        
        except Exception as e:
            logger.debug(f"Could not use monitoring cache: {e}")
            cached_orders = []
            cache_hits = 0
        
        # PERFORMANCE OPTIMIZATION: Check local cache for remaining orders
        orders_to_fetch = []
        for order_id in order_ids:
            if order_id in updated_orders:
                continue  # Already found in monitoring cache
                
            # Check if we have fresh cached data
            if (order_id in self.order_cache and 
                order_id in self.last_update and
                current_time - self.last_update[order_id] < self.cache_ttl):
                updated_orders[order_id] = self.order_cache[order_id]
                logger.debug(f"🚀 Using local cached data for order {order_id[:8]}... (age: {current_time - self.last_update[order_id]:.1f}s)")
                continue
            
            # Check throttling
            last_check = self.recent_check_cache.get(order_id, 0)
            if current_time - last_check < self.check_throttle:
                # Use cached data even if slightly stale during throttle period
                if order_id in self.order_cache:
                    updated_orders[order_id] = self.order_cache[order_id]
                    logger.debug(f"⏱️ Throttled check for order {order_id[:8]}... using stale cache")
                continue
            
            orders_to_fetch.append(order_id)
        
        # If no orders need fetching, return cached results
        if not orders_to_fetch:
            logger.info(f"💾 All {len(order_ids)} orders served from cache - no API calls needed")
            return updated_orders
        
        # Choose client based on account type
        client = bybit_client_2 if account_type == "mirror" else None
        
        logger.info(f"🔍 Fetching {len(orders_to_fetch)}/{len(order_ids)} orders from exchange ({len(order_ids) - len(orders_to_fetch)} cached)")
        
        for order_id in orders_to_fetch:
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
                    
                    logger.info(
                        f"📊 Updated limit order {order_id[:8]}... "
                        f"Status: {order_details.get('orderStatus')} "
                        f"Filled: {order_details.get('cumExecQty', '0')}/{order_details.get('qty', '0')} "
                        f"({account_type} account)"
                    )
                else:
                    # Order not found - likely filled, cancelled, or expired
                    # Add to stale orders list for cleanup
                    if not hasattr(self, 'stale_order_ids'):
                        self.stale_order_ids = set()
                    self.stale_order_ids.add(order_id)
                    
                    # Use debug instead of warning for expected scenario
                    logger.debug(f"🔍 Order {order_id[:8]}... not found (likely filled/cancelled)")
                    
            except Exception as e:
                # Enhanced error context
                error_str = str(e).lower()
                if any(term in error_str for term in ["timeout", "connection", "network"]):
                    logger.warning(f"🌐 Network issue fetching order {order_id[:8]}...: {e}")
                elif any(term in error_str for term in ["rate limit", "too many requests"]):
                    logger.warning(f"⏱️ Rate limit hit while fetching order {order_id[:8]}...: {e}")
                else:
                    logger.error(f"❌ Unexpected error fetching order {order_id[:8]}...: {e}")
                
        # Clean up stale orders from tracking
        if hasattr(self, 'stale_order_ids') and self.stale_order_ids:
            self._cleanup_stale_orders()
                
        return updated_orders
    
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
        """
        try:
            # Get current monitor data
            import pickle
            
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
                data = pickle.load(f)
            
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
            
            # Save updated data if any cleanup occurred
            if cleanup_count > 0:
                with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                    pickle.dump(data, f)
                logger.info(f"✅ Cleaned up {cleanup_count} stale order references from monitor data")
            
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
        Get a formatted summary of limit orders for alerts
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
        
        summary_parts = []
        if filled:
            summary_parts.append(f"Filled: {len(filled)} [{', '.join(filled[:2])}{'...' if len(filled) > 2 else ''}]")
        if active:
            summary_parts.append(f"Active: {len(active)} [{', '.join(active[:2])}{'...' if len(active) > 2 else ''}]")
        if cancelled:
            summary_parts.append(f"Cancelled: {len(cancelled)}")
            
        return " | ".join(summary_parts) if summary_parts else "No active limit orders"


# Global instance
limit_order_tracker = EnhancedLimitOrderTracker()