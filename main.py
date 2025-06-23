#!/usr/bin/env python3
"""
Enhanced Trading Bot - VOICE REMOVED, MANUAL OPTIMIZED
FIXED: Better resource management and memory leak prevention
ENHANCED: Improved error handling and graceful shutdown
ENHANCED: Better task management and cleanup
FIXED: Background tasks start properly within async context
"""
import os
import logging
import time
import asyncio
import signal
import atexit
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    PicklePersistence,
    CommandHandler
)

# Import configuration
from config import *

# Import clients and core components
from clients import bybit_client, openai_client
from utils import *
from risk import *
from dashboard import *
from shared import *

# Import handlers
from handlers import *
from execution import *

# Import AI components
try:
    from risk.sentiment import sentiment_analyzer
    from risk.regime import regime_detector
    from execution.portfolio_ai import portfolio_optimizer
    ai_available = True
except ImportError as e:
    ai_available = False
    logger.warning(f"AI components not available: {e}")

logger = logging.getLogger(__name__)

# ENHANCED: Global application reference for cleanup
_global_app = None
_cleanup_tasks = []

# All positions will be treated as bot positions
# All positions are now bot trades - no external monitoring

async def get_positions_requiring_monitoring():
    """
    Get all positions from Bybit that require monitoring
    All positions are treated as bot trades now
    """
    try:
        from clients.bybit_helpers import get_all_positions
        
        logger.info("🔍 Fetching all positions from Bybit for monitor restoration...")
        positions = await get_all_positions()
        
        if not positions:
            logger.info("📊 No positions found on Bybit")
            return []
        
        # Filter positions that need monitoring (size > 0)
        monitoring_positions = []
        for pos in positions:
            try:
                size = Decimal(str(pos.get("size", "0")))
                symbol = pos.get("symbol", "")
                side = pos.get("side", "")
                
                if size > 0 and symbol and side:
                    monitoring_positions.append({
                        "symbol": symbol,
                        "side": side,
                        "size": size,
                        "avgPrice": pos.get("avgPrice", "0"),
                        "unrealisedPnl": pos.get("unrealisedPnl", "0"),
                        "markPrice": pos.get("markPrice", "0")
                    })
                    logger.info(f"📊 Position requiring monitoring: {symbol} {side} {size}")
            except Exception as e:
                logger.error(f"Error processing position {pos}: {e}")
                continue
        
        logger.info(f"📊 Found {len(monitoring_positions)} positions requiring monitoring")
        return monitoring_positions
        
    except Exception as e:
        logger.error(f"❌ Error getting positions for monitoring: {e}")
        return []

async def get_orders_requiring_monitoring():
    """
    Get all orders from Bybit that require monitoring
    All orders are treated as bot orders now
    """
    try:
        from clients.bybit_helpers import get_all_open_orders
        
        logger.info("🔍 Fetching all orders from Bybit for monitor restoration...")
        orders = await get_all_open_orders()
        
        if not orders:
            logger.info("📋 No orders found on Bybit")
            return []
        
        # Filter orders that need monitoring (TP/SL orders or limit orders)
        monitoring_orders = []
        for order in orders:
            try:
                symbol = order.get("symbol", "")
                order_type = order.get("orderType", "")
                side = order.get("side", "")
                trigger_price = order.get("triggerPrice", "")
                reduce_only = order.get("reduceOnly", False)
                order_id = order.get("orderId", "")
                
                # Include TP/SL orders (with trigger price) and limit orders
                if symbol and order_id and (trigger_price or order_type == "Limit"):
                    monitoring_orders.append({
                        "symbol": symbol,
                        "orderId": order_id,
                        "side": side,
                        "orderType": order_type,
                        "triggerPrice": trigger_price,
                        "reduceOnly": reduce_only,
                        "qty": order.get("qty", "0"),
                        "price": order.get("price", "0")
                    })
                    logger.info(f"📋 Order requiring monitoring: {symbol} {order_type} {order_id[:8]}...")
            except Exception as e:
                logger.error(f"Error processing order {order}: {e}")
                continue
        
        logger.info(f"📋 Found {len(monitoring_orders)} orders requiring monitoring")
        return monitoring_orders
        
    except Exception as e:
        logger.error(f"❌ Error getting orders for monitoring: {e}")
        return []


def detect_approach_from_orders(orders: List[Dict]) -> Optional[str]:
    """
    Detect trading approach from order patterns
    Conservative: TP1_, TP2_, TP3_, TP4_, SL_, _LIMIT
    Fast: _FAST_TP, _FAST_SL, TP_, SL_
    GGShot: Similar to conservative but may have specific patterns
    """
    if not orders:
        return None
    
    conservative_patterns = ['TP1_', 'TP2_', 'TP3_', 'TP4_', '_LIMIT']
    fast_patterns = ['_FAST_TP', '_FAST_SL', '_FAST_MARKET']
    ggshot_patterns = ['_GGSHOT_', 'GGShot']
    
    conservative_count = 0
    fast_count = 0
    ggshot_count = 0
    tp_count = 0
    
    for order in orders:
        order_link_id = order.get('orderLinkId', '')
        
        # Check for GGShot patterns first
        if any(pattern in order_link_id for pattern in ggshot_patterns):
            ggshot_count += 1
            
        # Check for conservative patterns
        elif any(pattern in order_link_id for pattern in conservative_patterns):
            conservative_count += 1
            
        # Check for fast patterns
        elif any(pattern in order_link_id for pattern in fast_patterns):
            fast_count += 1
            
        # Count TPs for conservative detection
        if order_link_id.startswith('TP') and '_' in order_link_id:
            tp_count += 1
    
    # Determine approach based on counts
    if ggshot_count > 0:
        return "ggshot"
    elif conservative_count > 0 or tp_count >= 2:  # Multiple TPs indicate conservative
        return "conservative"
    elif fast_count > 0:
        return "fast"
    
    # Default based on order count (single TP/SL = fast, multiple = conservative)
    tp_orders = [o for o in orders if o.get('stopOrderType') == 'TakeProfit']
    if len(tp_orders) > 1:
        return "conservative"
    
    return None


async def find_chat_data_for_symbol(application: Application, symbol: str, side: str = None, approach: str = None):
    """
    Find chat data that corresponds to a symbol/side/approach combination
    """
    matching_chats = []
    
    try:
        # Check regular chat_data
        try:
            chat_data_items = list(application.chat_data.items()) if hasattr(application.chat_data, 'items') else []
        except Exception as e:
            logger.warning(f"Could not access chat_data.items(): {e}")
            chat_data_items = []
        
        for chat_id, chat_data in chat_data_items:
            if not isinstance(chat_data, dict):
                continue
            
            try:
                chat_symbol = chat_data.get(SYMBOL)
                chat_side = chat_data.get(SIDE)
                chat_approach = chat_data.get(TRADING_APPROACH, "fast")
                
                # Match symbol first
                if chat_symbol == symbol:
                    # If side is specified, match it too
                    if side is None or chat_side == side:
                        # If approach is specified, match it too
                        if approach is None or chat_approach == approach:
                            matching_chats.append((chat_id, chat_data))
                            logger.info(f"🎯 Found matching chat {chat_id} for {symbol} {side or 'any side'} ({chat_approach})")
            except Exception as e:
                logger.error(f"Error processing chat_data for chat {chat_id}: {e}")
                continue
        
        return matching_chats
        
    except Exception as e:
        logger.error(f"Error finding chat data for {symbol}: {e}")
        return []

async def verify_monitor_status(chat_id: int, chat_data: dict):
    """
    ENHANCED: Verify if a monitor is actually running for a chat
    """
    try:
        monitor_task_info = chat_data.get(ACTIVE_MONITOR_TASK, {})
        
        if not monitor_task_info.get("active"):
            return False
        
        # Check if we have a stored task reference
        from execution.monitor import get_monitor_task_status
        symbol = chat_data.get(SYMBOL, "")
        approach = chat_data.get(TRADING_APPROACH, "fast")
        status = await get_monitor_task_status(chat_id, symbol, approach)
        
        if status.get("running", False):
            logger.info(f"✅ Monitor for {symbol} ({approach}) in chat {chat_id} is actively running")
            return True
        else:
            logger.info(f"🔄 Monitor task for {symbol} ({approach}) in chat {chat_id} needs restart")
            return False
        
    except Exception as e:
        logger.error(f"Error verifying monitor status for chat {chat_id}: {e}")
        return False

async def cleanup_stale_monitors(application: Application):
    """
    Clean up stale monitor entries from bot_data on startup
    """
    try:
        if 'monitor_tasks' not in application.bot_data:
            logger.info("No monitor_tasks found in bot_data")
            return
        
        monitor_tasks = application.bot_data['monitor_tasks']
        current_time = time.time()
        stale_monitors = []
        
        # Check each monitor entry
        for monitor_key, task_info in monitor_tasks.items():
            if not isinstance(task_info, dict):
                stale_monitors.append(monitor_key)
                continue
            
            # Check if monitor is stale (older than 24 hours)
            started_at = task_info.get('started_at', 0)
            if started_at > 0 and (current_time - started_at) > 86400:  # 24 hours
                stale_monitors.append(monitor_key)
                logger.info(f"Found stale monitor {monitor_key} (started {(current_time - started_at)/3600:.1f} hours ago)")
                continue
            
            # Check if monitor is marked as active but has no running task
            if task_info.get('active', False):
                chat_id = task_info.get('chat_id')
                symbol = task_info.get('symbol')
                approach = task_info.get('approach', 'fast')
                
                if chat_id and symbol:
                    from execution.monitor import get_monitor_task_status
                    status = await get_monitor_task_status(chat_id, symbol, approach)
                    
                    if not status.get("running", False):
                        stale_monitors.append(monitor_key)
                        logger.info(f"Found inactive monitor {monitor_key} marked as active")
        
        # Remove stale monitors
        for monitor_key in stale_monitors:
            del monitor_tasks[monitor_key]
            logger.info(f"Removed stale monitor: {monitor_key}")
        
        if stale_monitors:
            logger.info(f"✅ Cleaned up {len(stale_monitors)} stale monitors")
            await application.update_persistence()
        else:
            logger.info("✅ No stale monitors found")
            
    except Exception as e:
        logger.error(f"Error cleaning up stale monitors: {e}")

async def restore_monitoring_for_position(application: Application, position: dict):
    """
    ENHANCED: Restore monitoring for a specific position
    """
    try:
        symbol = position["symbol"]
        side = position["side"]
        
        logger.info(f"🔄 Attempting to restore monitoring for position: {symbol} {side}")
        
        # Find chat data for this position
        matching_chats = await find_chat_data_for_symbol(application, symbol, side)
        
        if not matching_chats:
            logger.warning(f"⚠️ No chat data found for position {symbol} {side}")
            return False
        
        # Restore monitoring for each matching chat
        restored_count = 0
        for chat_id, chat_data in matching_chats:
            try:
                # Verify if monitor is already running
                is_running = await verify_monitor_status(chat_id, chat_data)
                
                if is_running:
                    logger.info(f"✅ Monitor already running for {symbol} in chat {chat_id}")
                    continue
                
                # Update chat data with current position info
                chat_data[LAST_KNOWN_POSITION_SIZE] = position["size"]
                
                # Determine approach for proper monitoring
                approach = chat_data.get(TRADING_APPROACH, "fast")
                
                # Start monitoring
                from execution.monitor import start_position_monitoring
                await start_position_monitoring(application, int(chat_id), chat_data)
                
                logger.info(f"✅ Monitor restored for {symbol} ({approach}) in chat {chat_id}")
                restored_count += 1
                
                # Small delay between restorations
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Failed to restore monitor for {symbol} in chat {chat_id}: {e}")
                continue
        
        if restored_count > 0:
            logger.info(f"✅ Successfully restored {restored_count} monitors for position {symbol}")
            return True
        else:
            logger.warning(f"⚠️ Could not restore monitoring for position {symbol}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error restoring monitoring for position: {e}")
        return False

async def restore_monitoring_for_orders(application: Application, orders: list):
    """
    ENHANCED: Restore monitoring for orders that need it
    """
    try:
        restored_count = 0
        
        # Group orders by symbol for efficient processing
        orders_by_symbol = {}
        for order in orders:
            symbol = order["symbol"]
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)
        
        # Restore monitoring for each symbol's orders
        for symbol, symbol_orders in orders_by_symbol.items():
            try:
                logger.info(f"🔄 Checking orders for symbol {symbol}: {len(symbol_orders)} orders")
                
                # Find chat data for this symbol
                matching_chats = await find_chat_data_for_symbol(application, symbol)
                
                if not matching_chats:
                    logger.warning(f"⚠️ No chat data found for orders on {symbol}")
                    continue
                
                # Check if any chat has these orders tracked
                for chat_id, chat_data in matching_chats:
                    try:
                        # Check if this chat has order tracking data
                        limit_order_ids = chat_data.get(LIMIT_ORDER_IDS, [])
                        tp_order_ids = chat_data.get(CONSERVATIVE_TP_ORDER_IDS, []) or chat_data.get(TP_ORDER_IDS, [])
                        sl_order_id = chat_data.get(CONSERVATIVE_SL_ORDER_ID) or chat_data.get(SL_ORDER_ID)
                        
                        # Check if any of the Bybit orders match our tracked orders
                        has_matching_orders = False
                        for order in symbol_orders:
                            order_id = order["orderId"]
                            if (order_id in limit_order_ids or 
                                order_id in tp_order_ids or 
                                order_id == sl_order_id):
                                has_matching_orders = True
                                break
                        
                        if has_matching_orders:
                            # Verify if monitor is already running
                            is_running = await verify_monitor_status(chat_id, chat_data)
                            
                            if not is_running:
                                # Restore monitoring
                                from execution.monitor import start_position_monitoring
                                await start_position_monitoring(application, int(chat_id), chat_data)
                                
                                logger.info(f"✅ Bot monitor restored for orders on {symbol} in chat {chat_id}")
                                restored_count += 1
                                
                                # Small delay between restorations
                                await asyncio.sleep(0.5)
                            else:
                                logger.info(f"✅ Bot monitor already running for orders on {symbol} in chat {chat_id}")
                        
                    except Exception as e:
                        logger.error(f"❌ Failed to restore monitor for orders on {symbol} in chat {chat_id}: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Error processing orders for symbol {symbol}: {e}")
                continue
        
        return restored_count
        
    except Exception as e:
        logger.error(f"❌ Error restoring monitoring for orders: {e}")
        return 0

# Orphaned monitor cleanup removed - all trades are now bot trades with persistence

async def check_and_restart_position_monitors(application: Application):
    """
    Comprehensive monitor restoration system - all positions treated as bot positions
    ENHANCED: Properly handles multiple positions with same symbol but different approaches
    """
    try:
        logger.info("🚀 Starting monitor restoration...")
        
        # Step 1: Get current positions and orders from Bybit
        logger.info("📊 Step 1: Fetching current positions and orders from Bybit...")
        positions = await get_positions_requiring_monitoring()
        orders = await get_orders_requiring_monitoring()
        
        if not positions and not orders:
            logger.info("✅ No active positions or orders found - no monitors needed")
            return
        
        logger.info(f"📊 Found {len(positions)} positions and {len(orders)} orders requiring monitoring")
        
        # Get all open orders for approach detection
        from clients.bybit_helpers import get_all_open_orders
        all_orders = await get_all_open_orders()
        
        # Group orders by symbol for efficient lookup
        orders_by_symbol = {}
        for order in all_orders:
            symbol = order.get('symbol', '')
            if symbol:
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
        
        # Step 2: Find the main chat ID to use for positions without chat data
        logger.info("🔍 Step 2: Finding main chat ID...")
        main_chat_id = None
        
        # Find a valid chat ID from existing chat data
        for chat_id, chat_data in application.chat_data.items():
            if isinstance(chat_data, dict) and chat_data.get(SYMBOL):
                # Skip synthetic chat IDs
                try:
                    if int(chat_id) < 9000000000:
                        main_chat_id = chat_id
                        logger.info(f"Found main chat ID: {main_chat_id}")
                        break
                except (ValueError, TypeError):
                    continue
        
        if not main_chat_id:
            logger.warning("⚠️ No valid chat ID found in persistence")
            # You might want to handle this case differently, e.g., get from config
            return
        
        # Step 3: Process all positions as bot positions with approach detection
        logger.info("🤖 Step 3: Processing all positions as bot positions...")
        restored_positions = 0
        created_new_entries = 0
        
        # First, check persistence for existing configured monitors
        existing_monitors = {}
        if 'monitor_tasks' in application.bot_data:
            for key, monitor_info in application.bot_data['monitor_tasks'].items():
                if isinstance(monitor_info, dict) and monitor_info.get('active'):
                    symbol = monitor_info.get('symbol')
                    approach = monitor_info.get('approach', 'fast')
                    if symbol:
                        if symbol not in existing_monitors:
                            existing_monitors[symbol] = []
                        existing_monitors[symbol].append(approach)
                        logger.info(f"Found configured monitor: {symbol} ({approach})")
        
        for position in positions:
            symbol = position["symbol"]
            side = position["side"]
            
            # Get orders for this position to detect approach
            position_orders = orders_by_symbol.get(symbol, [])
            detected_approach = detect_approach_from_orders(position_orders)
            
            # Get configured approaches for this symbol
            configured_approaches = existing_monitors.get(symbol, [])
            
            # If we have configured monitors, restore ALL of them regardless of detection
            if configured_approaches:
                logger.info(f"📊 Symbol {symbol} has configured approaches: {configured_approaches}")
                
                for approach in configured_approaches:
                    # Check if we have chat data for this specific approach
                    matching_chats = await find_chat_data_for_symbol(application, symbol, side, approach)
                    
                    if matching_chats:
                        # Restore monitoring for existing chat data
                        for chat_id, chat_data in matching_chats:
                            try:
                                chat_approach = chat_data.get(TRADING_APPROACH, "fast")
                                
                                # Ensure approach matches
                                if chat_approach != approach:
                                    continue
                                
                                # All positions are bot trades now - no external positions
                                chat_data.pop("read_only_monitoring", None)
                                
                                # Verify if monitor is already running
                                is_running = await verify_monitor_status(chat_id, chat_data)
                                
                                if not is_running:
                                    # Update chat data with current position info
                                    chat_data[LAST_KNOWN_POSITION_SIZE] = position["size"]
                                    
                                    # Start monitoring
                                    from execution.monitor import start_position_monitoring
                                    await start_position_monitoring(application, int(chat_id), chat_data)
                                    
                                    logger.info(f"✅ Monitor restored for {symbol} ({chat_approach}) in chat {chat_id}")
                                    restored_positions += 1
                                else:
                                    logger.info(f"✅ Monitor already running for {symbol} ({chat_approach}) in chat {chat_id}")
                                break  # Found a match for this approach
                            except Exception as e:
                                logger.error(f"❌ Error restoring monitor for {symbol}: {e}")
                    else:
                        # No existing chat data for this approach - create new entry
                        logger.info(f"📝 Creating new chat data for configured approach: {symbol} {side} ({approach})")
                        
                        # Create chat data for this position
                        new_chat_data = {
                            SYMBOL: symbol,
                            SIDE: side,
                            LAST_KNOWN_POSITION_SIZE: position["size"],
                            PRIMARY_ENTRY_PRICE: position.get("avgPrice", "0"),
                            TRADING_APPROACH: approach,
                            "position_created": True,
                            "bot_position": True
                        }
                        
                        # Add approach-specific order IDs if they match
                        if approach == "conservative" and position_orders:
                            tp_orders = [o for o in position_orders if o.get('orderLinkId', '').startswith('TP')]
                            sl_orders = [o for o in position_orders if o.get('orderLinkId', '').startswith('SL')]
                            
                            if tp_orders:
                                tp_order_ids = [o.get('orderId') for o in sorted(tp_orders, key=lambda x: x.get('orderLinkId', ''))]
                                new_chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids
                            if sl_orders:
                                new_chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_orders[0].get('orderId')
                        
                        # Store in the main chat's data
                        if main_chat_id not in application.chat_data:
                            application.chat_data[main_chat_id] = {}
                        
                        # Create a unique key for this position including approach
                        position_key = f"position_{symbol}_{side}_{approach}"
                        application.chat_data[main_chat_id][position_key] = new_chat_data
                        
                        # Start monitoring
                        try:
                            from execution.monitor import start_position_monitoring
                            await start_position_monitoring(application, int(main_chat_id), new_chat_data)
                            
                            logger.info(f"✅ Created new monitor for {symbol} ({approach}) in chat {main_chat_id}")
                            created_new_entries += 1
                        except Exception as e:
                            logger.error(f"❌ Error creating monitor for {symbol}: {e}")
            
            else:
                # No configured monitors - use detected approach or create single monitor
                logger.info(f"📊 No configured monitors for {symbol}, using detected approach")
                
                # Check if we have chat data for this position with detected approach
                matching_chats = await find_chat_data_for_symbol(application, symbol, side, detected_approach)
                
                # Track if we found a monitor
                monitor_found = False
                
                if matching_chats:
                    # Restore monitoring for existing chat data
                    for chat_id, chat_data in matching_chats:
                        try:
                            chat_approach = chat_data.get(TRADING_APPROACH, "fast")
                            
                            # Skip if approach doesn't match detected approach (if we detected one)
                            if detected_approach and chat_approach != detected_approach:
                                logger.info(f"⚠️ Skipping chat {chat_id} - approach mismatch: {chat_approach} != {detected_approach}")
                                continue
                            
                            # All positions are bot trades now - no external positions
                            chat_data.pop("read_only_monitoring", None)
                            
                            # Verify if monitor is already running
                            is_running = await verify_monitor_status(chat_id, chat_data)
                            
                            if not is_running:
                                # Update chat data with current position info
                                chat_data[LAST_KNOWN_POSITION_SIZE] = position["size"]
                                
                                # Start monitoring
                                from execution.monitor import start_position_monitoring
                                await start_position_monitoring(application, int(chat_id), chat_data)
                                
                                logger.info(f"✅ Monitor restored for {symbol} ({chat_approach}) in chat {chat_id}")
                                restored_positions += 1
                                monitor_found = True
                                break  # Found a match, no need to check other chats
                            else:
                                logger.info(f"✅ Monitor already running for {symbol} ({chat_approach}) in chat {chat_id}")
                                monitor_found = True
                                break  # Found a match, no need to check other chats
                        except Exception as e:
                            logger.error(f"❌ Error restoring monitor for {symbol}: {e}")
                
                # If no monitor found, create new entry
                if not monitor_found:
                    approach = detected_approach or "fast"  # Use detected approach or default to fast
                    logger.info(f"📝 Creating new chat data for position: {symbol} {side} ({approach})")
                    
                    # Create chat data for this position
                    new_chat_data = {
                        SYMBOL: symbol,
                        SIDE: side,
                        LAST_KNOWN_POSITION_SIZE: position["size"],
                        PRIMARY_ENTRY_PRICE: position.get("avgPrice", "0"),
                        TRADING_APPROACH: approach,
                        "position_created": True,
                        "bot_position": True
                    }
                    
                    # Add approach-specific order IDs if detected and available
                    if detected_approach == "conservative" and position_orders:
                        tp_orders = [o for o in position_orders if o.get('orderLinkId', '').startswith('TP')]
                        sl_orders = [o for o in position_orders if o.get('orderLinkId', '').startswith('SL')]
                        
                        if tp_orders:
                            tp_order_ids = [o.get('orderId') for o in sorted(tp_orders, key=lambda x: x.get('orderLinkId', ''))]
                            new_chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids
                        if sl_orders:
                            new_chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_orders[0].get('orderId')
                    
                    # Store in the main chat's data
                    if main_chat_id not in application.chat_data:
                        application.chat_data[main_chat_id] = {}
                    
                    # Create a unique key for this position including approach
                    position_key = f"position_{symbol}_{side}_{approach}"
                    application.chat_data[main_chat_id][position_key] = new_chat_data
                    
                    # Start monitoring
                    try:
                        from execution.monitor import start_position_monitoring
                        await start_position_monitoring(application, int(main_chat_id), new_chat_data)
                        
                        logger.info(f"✅ Created new monitor for {symbol} ({approach}) in chat {main_chat_id}")
                        created_new_entries += 1
                    except Exception as e:
                        logger.error(f"❌ Error creating monitor for {symbol}: {e}")
            
            # Small delay between position processing
            await asyncio.sleep(0.3)
        
        # Step 4: Restore monitoring for orders
        logger.info("📋 Step 4: Restoring monitoring for orders...")
        restored_orders = await restore_monitoring_for_orders(application, orders)
        
        # Step 5: Orphaned monitor cleanup no longer needed - all trades are bot trades
        logger.info("✅ Step 5: Skipping orphaned monitor cleanup (all trades are bot trades)")
        
        # Step 6: Update persistence
        if restored_positions > 0 or created_new_entries > 0 or restored_orders > 0:
            logger.info("💾 Step 6: Updating persistence...")
            await application.update_persistence()
        
        # Summary
        total_restored = restored_positions + created_new_entries
        logger.info(f"✅ Monitor Restoration Complete!")
        logger.info(f"   🤖 Positions monitored: {total_restored}")
        logger.info(f"   📝 New entries created: {created_new_entries}")
        logger.info(f"   📋 Order groups monitored: {restored_orders}")
        
    except Exception as e:
        logger.error(f"❌ Error in monitor restoration: {e}", exc_info=True)

async def auto_restart_monitors_with_delay(application: Application):
    """Restart monitors with a delay to ensure everything is initialized"""
    try:
        await asyncio.sleep(3)
        logger.info("🔄 Starting automatic monitor restart check...")
        await check_and_restart_position_monitors(application)
    except Exception as e:
        logger.error(f"❌ Error in delayed monitor restart: {e}")

async def startup_order_cleanup():
    """Run order cleanup on bot startup"""
    try:
        from config.settings import ORDER_CLEANUP_ON_STARTUP, ORDER_CLEANUP_STARTUP_DELAY
        from clients.bybit_helpers import cleanup_expired_protections
        
        if not ORDER_CLEANUP_ON_STARTUP:
            logger.info("🧹 Startup order cleanup is disabled")
            return
        
        logger.info(f"🧹 Scheduling startup order cleanup in {ORDER_CLEANUP_STARTUP_DELAY} seconds...")
        await asyncio.sleep(ORDER_CLEANUP_STARTUP_DELAY)
        
        # Orphaned order cleanup removed - all trades are bot trades
        logger.info("✅ Orphaned order cleanup no longer needed (all trades are bot trades)")
        
        # Clean up expired protections
        cleanup_expired_protections()
        
        # For now, just cleanup expired protections
        # Full cleanup would be implemented here
        logger.info("🧹 Startup cleanup: Expired protections cleaned")
            
    except Exception as e:
        logger.error(f"❌ Error in startup order cleanup: {e}")

async def start_periodic_order_cleanup():
    """Start the periodic order cleanup task"""
    try:
        from config.settings import ENABLE_ORDER_CLEANUP
        from clients.bybit_helpers import periodic_order_cleanup_task
        
        if not ENABLE_ORDER_CLEANUP:
            logger.info("🧹 Periodic order cleanup is disabled")
            return
        
        logger.info("🧹 Starting periodic order cleanup task...")
        cleanup_task = asyncio.create_task(periodic_order_cleanup_task())
        _cleanup_tasks.append(cleanup_task)
        
    except Exception as e:
        logger.error(f"❌ Error starting periodic order cleanup: {e}")

async def start_cache_cleanup_task_async():
    """Start cache cleanup task within async context"""
    try:
        from utils.cache import _periodic_cache_cleanup
        logger.info("✅ Starting cache cleanup task...")
        cleanup_task = asyncio.create_task(_periodic_cache_cleanup())
        _cleanup_tasks.append(cleanup_task)
        logger.info("✅ Cache cleanup task started")
    except Exception as e:
        logger.error(f"Error starting cache cleanup task: {e}")

async def start_monitor_cleanup_task_async():
    """Start monitor cleanup task within async context"""
    try:
        from execution.monitor import periodic_monitor_cleanup
        logger.info("✅ Starting monitor cleanup task...")
        cleanup_task = asyncio.create_task(periodic_monitor_cleanup())
        _cleanup_tasks.append(cleanup_task)
        logger.info("✅ Monitor cleanup task started")
    except Exception as e:
        logger.error(f"Error starting monitor cleanup task: {e}")

async def cleanup_stale_monitors(application: Application):
    """Clean up stale monitors from bot_data on startup"""
    try:
        logger.info("🧹 Cleaning up stale monitors...")
        
        bot_data = application.bot_data
        monitor_tasks = bot_data.get('monitor_tasks', {})
        current_time = time.time()
        stale_count = 0
        
        # Check each monitor and remove if stale
        monitors_to_remove = []
        for monitor_key, task_info in monitor_tasks.items():
            if isinstance(task_info, dict):
                started_at = task_info.get('started_at', 0)
                is_active = task_info.get('active', False)
                
                # Remove if older than 24 hours or marked inactive
                if (started_at > 0 and (current_time - started_at) > 86400) or not is_active:
                    age_hours = (current_time - started_at) / 3600 if started_at > 0 else 0
                    logger.info(f"🗑️ Removing stale monitor {monitor_key} (age: {age_hours:.1f}h, active: {is_active})")
                    monitors_to_remove.append(monitor_key)
                    stale_count += 1
        
        # Remove stale monitors
        for monitor_key in monitors_to_remove:
            del monitor_tasks[monitor_key]
        
        if stale_count > 0:
            logger.info(f"✅ Cleaned up {stale_count} stale monitors")
            await application.update_persistence()
        else:
            logger.info("✅ No stale monitors found")
            
    except Exception as e:
        logger.error(f"❌ Error cleaning up stale monitors: {e}")

async def start_background_tasks():
    """ENHANCED: Start all background tasks with proper management"""
    try:
        logger.info("🚀 Starting enhanced background tasks...")
        
        # Start cache cleanup task (within async context)
        await start_cache_cleanup_task_async()
        
        # Start monitor cleanup task (within async context)
        await start_monitor_cleanup_task_async()
        
        # Start order cleanup
        await start_periodic_order_cleanup()
        
        logger.info("✅ All background tasks started successfully")
        
    except Exception as e:
        logger.error(f"❌ Error starting background tasks: {e}")

async def enhanced_post_init(application: Application) -> None:
    """Enhanced post-initialization with better resource management"""
    global _global_app
    _global_app = application
    
    logger.info("🚀 Enhanced Trading Bot initializing...")
    
    # Initialize enhanced bot data
    stats_defaults = {
        STATS_TOTAL_TRADES: 0,
        STATS_TP1_HITS: 0,
        STATS_SL_HITS: 0,
        STATS_OTHER_CLOSURES: 0,
        STATS_LAST_RESET: time.time(),
        STATS_TOTAL_PNL: Decimal("0"),
        STATS_WIN_STREAK: 0,
        STATS_LOSS_STREAK: 0,
        STATS_BEST_TRADE: Decimal("0"),
        STATS_WORST_TRADE: Decimal("0"),
        STATS_TOTAL_WINS: 0,
        STATS_TOTAL_LOSSES: 0,
        STATS_CONSERVATIVE_TRADES: 0,
        STATS_FAST_TRADES: 0,
        STATS_CONSERVATIVE_TP1_CANCELLATIONS: 0,
        # Additional stats for portfolio metrics
        'stats_total_wins_pnl': Decimal("0"),
        'stats_total_losses_pnl': Decimal("0"),
        'stats_max_drawdown': Decimal("0"),
        'stats_peak_equity': Decimal("0"),
        'stats_current_drawdown': Decimal("0"),
        'recent_trade_pnls': []
    }
    
    for stat_key, default_val in stats_defaults.items():
        if stat_key not in application.bot_data:
            application.bot_data[stat_key] = default_val
    
    # Clean up stale monitors on startup
    try:
        from utils.monitor_cleanup import cleanup_stale_monitors_on_startup
        logger.info("🧹 Running startup monitor cleanup...")
        cleanup_performed = await cleanup_stale_monitors_on_startup(application.bot_data)
        if cleanup_performed:
            # Force persistence update if cleanup was performed
            await application.update_persistence()
            logger.info("✅ Startup monitor cleanup completed and persistence updated")
    except Exception as e:
        logger.error(f"Error during startup monitor cleanup: {e}")
    
    # Initialize AI components
    try:
        if ai_available and openai_client:
            sentiment_analyzer.client = openai_client
            regime_detector.client = openai_client
            portfolio_optimizer.client = openai_client
            logger.info("🧠 AI components initialized")
        else:
            logger.info("🤖 AI components using fallback analysis")
    except Exception as e:
        logger.error(f"Error initializing AI components: {e}")
    
    # DISABLED: Social Media Sentiment Analysis (API keys not configured)
    # To enable: Add valid API keys to .env file
    logger.info("📱 Social media sentiment analysis disabled (no API keys configured)")
    # try:
    #     from social_media.integration import initialize_social_media_sentiment
    #     sentiment_init_success = await initialize_social_media_sentiment()
    #     if sentiment_init_success:
    #         logger.info("📱 Social media sentiment analysis initialized")
    #     else:
    #         logger.info("📱 Social media sentiment analysis disabled or not configured")
    # except ImportError as e:
    #     logger.warning(f"📱 Social media sentiment module not available: {e}")
    # except Exception as e:
    #     logger.error(f"📱 Error initializing social media sentiment: {e}")
    
    # NEW: Initialize alert manager (store reference to it separately to avoid deepcopy issues)
    try:
        from alerts import AlertManager
        alert_manager = AlertManager(application.bot)
        # Don't store in bot_data to avoid deepcopy issues with Bot object
        # Instead, we'll access it through a different mechanism
        await alert_manager.start()
        logger.info("✅ Alert Manager initialized and started")
        
        # Store a reference that can be accessed by handlers
        application._alert_manager = alert_manager
    except Exception as e:
        logger.error(f"❌ Failed to initialize Alert Manager: {e}")
    
    # ENHANCED: Start background tasks (within async context)
    await start_background_tasks()
    
    # Clean up stale monitors before restoration
    logger.info("🧹 Cleaning up stale monitors...")
    await cleanup_stale_monitors(application)
    
    # Monitor restoration
    logger.info("🔄 Initializing monitor restoration...")
    asyncio.create_task(auto_restart_monitors_with_delay(application))
    
    # Order cleanup
    logger.info("🧹 Initializing order cleanup...")
    asyncio.create_task(startup_order_cleanup())
    
    await application.update_persistence()
    logger.info("✅ Enhanced bot initialization completed!")

def setup_signal_handlers():
    """ENHANCED: Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(graceful_shutdown())
    
    # Register signal handlers
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("✅ Signal handlers registered")
    except Exception as e:
        logger.error(f"Error setting up signal handlers: {e}")

async def graceful_shutdown():
    """ENHANCED: Perform graceful shutdown with resource cleanup"""
    global _global_app, _cleanup_tasks
    
    logger.info("🛑 Starting graceful shutdown...")
    
    try:
        # Cancel all background tasks
        for task in _cleanup_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop alert manager
        if _global_app:
            try:
                alert_manager = getattr(_global_app, '_alert_manager', None)
                if alert_manager:
                    await alert_manager.stop()
                    logger.info("✅ Alert manager stopped")
            except Exception as e:
                logger.error(f"Error stopping alert manager: {e}")
        
        # Stop all monitors
        if _global_app:
            try:
                from execution.monitor import stop_position_monitoring
                for chat_id, chat_data in _global_app.chat_data.items():
                    if isinstance(chat_data, dict):
                        monitor_info = chat_data.get(ACTIVE_MONITOR_TASK, {})
                        if monitor_info.get("active"):
                            await stop_position_monitoring(chat_data)
            except Exception as e:
                logger.error(f"Error stopping monitors: {e}")
        
        # DISABLED: Social media sentiment shutdown
        # try:
        #     from social_media.integration import shutdown_social_media_sentiment
        #     await shutdown_social_media_sentiment()
        # except ImportError:
        #     pass
        # except Exception as e:
        #     logger.error(f"Error shutting down social media sentiment: {e}")
        
        # Cleanup HTTP sessions
        try:
            from clients.bybit_client import cleanup_http_session
            await cleanup_http_session()
        except Exception as e:
            logger.error(f"Error cleaning up HTTP sessions: {e}")
        
        # Final persistence update
        if _global_app:
            try:
                await _global_app.update_persistence()
                logger.info("✅ Final persistence update completed")
            except Exception as e:
                logger.error(f"Error in final persistence update: {e}")
        
        logger.info("✅ Graceful shutdown completed")
        
    except Exception as e:
        logger.error(f"❌ Error during graceful shutdown: {e}")

def main():
    """ENHANCED main entry point with better resource management"""
    setup_logging()
    validate_config()
    setup_signal_handlers()
    
    # Register cleanup function
    atexit.register(lambda: asyncio.run(graceful_shutdown()) if _global_app else None)
    
    logger.info(f"🚀 Enhanced Trading Bot starting!")
    logger.info(f"📱 Mobile-first design with manual trading optimization")
    logger.info(f"Environment: {'TESTNET' if USE_TESTNET else 'LIVE'}")
    logger.info(f"Version: Enhanced Manual v5.3 - ALL POSITIONS AS BOT POSITIONS")
    
    # Setup persistence
    persistence_file = PERSISTENCE_FILE
    logger.info(f"Using persistence file: {persistence_file}")
    
    p_dir = os.path.dirname(persistence_file)
    if p_dir and not os.path.exists(p_dir):
        os.makedirs(p_dir)
    
    try:
        pers = PicklePersistence(filepath=persistence_file)
    except Exception as e:
        logger.error(f"Failed to init persistence: {e}")
        pers = None
    
    # Build application
    app_builder = ApplicationBuilder().token(TELEGRAM_TOKEN)
    if pers:
        app_builder = app_builder.persistence(pers)
    
    app_builder.post_init(enhanced_post_init)
    app = app_builder.build()

    # Setup handlers
    setup_handlers(app)
    
    # Enhanced feature summary
    logger.info(f"🚀 Enhanced Trading Bot Features:")
    
    if ai_available:
        logger.info(f"🧠 AI Analysis: Market sentiment, risk assessment, portfolio health")
    
    # logger.info(f"📱 Social Media Intelligence: Multi-platform sentiment analysis")
    
    logger.info(f"📱 Mobile UX: Touch-optimized interface, quick selections")
    logger.info(f"📝 Manual Trading: Enhanced workflow with intelligent defaults")
    logger.info(f"🔄 ROBUST Monitor Restoration: Direct Bybit verification system")
    logger.info(f"🤖 All Positions Bot Mode: Every position gets full monitoring")
    logger.info(f"✅ Order Management: All trades tracked with persistence")
    logger.info(f"📊 Performance: Real-time stats and enhanced tracking")
    logger.info(f"🛡️ Risk Management: Smart position sizing and R:R analysis")
    logger.info(f"🔧 Resource Management: Memory leak prevention and graceful shutdown")
    logger.info(f"💡 POTENTIAL P&L: Shows profit if all TP1 hit, loss if all SL hit")
    
    # Available commands
    commands = [
        "/start (enhanced dashboard)",
        "/trade (manual trade setup)",
        "/dashboard (control panel)",
        "/help (user guide)"
    ]
    
    logger.info(f"💡 Commands: {', '.join(commands)}")
    
    # Trading features
    features = [
        "📝 Enhanced Manual Trading",
        "📱 Mobile-First Interface", 
        "🧠 AI-Powered Insights",
        # "📱 Social Media Intelligence",  # Disabled - API keys not configured
        "🔄 ROBUST Automatic Monitoring",
        "🤖 All Positions as Bot Positions",
        "📊 Real-Time Statistics",
        "🛡️ Smart Risk Management",
        "🔧 Enhanced Resource Management",
        "💡 Potential P&L Display"
    ]
    
    logger.info(f"🎯 Features: {', '.join(features)}")
    
    logger.info(f"📱 Mobile Optimization:")
    logger.info(f"   • Touch-friendly button layouts")
    logger.info(f"   • Quick selection for all inputs")
    logger.info(f"   • Streamlined information display")
    logger.info(f"   • Enhanced error handling and UX")
    
    logger.info(f"📝 Manual Trading Enhancements:")
    logger.info(f"   • Step-by-step guided workflow")
    logger.info(f"   • Intelligent input validation")
    logger.info(f"   • Quick selection buttons")
    logger.info(f"   • Visual confirmation screens")
    
    logger.info(f"🔄 ROBUST Monitor Restoration:")
    logger.info(f"   • Direct Bybit API verification")
    logger.info(f"   • Position and order cross-referencing")
    logger.info(f"   • All trades have chat data and persistence")
    logger.info(f"   • Conservative and fast approach support")
    
    logger.info(f"🤖 All Positions Bot Mode:")
    logger.info(f"   • Every position gets full monitoring capabilities")
    logger.info(f"   • Automatic TP/SL management for all positions") 
    logger.info(f"   • Unified dashboard view of all positions")
    
    # logger.info(f"📱 Social Media Intelligence:")
    # logger.info(f"   • Multi-platform sentiment analysis (Reddit, Twitter, YouTube, Discord)")
    # logger.info(f"   • 6-hour collection cycles with free API tier optimization")
    # logger.info(f"   • Advanced OpenAI sentiment analysis with fallbacks")
    # logger.info(f"   • Market mood detection and trending topics")
    # logger.info(f"   • FOMO and consensus signal generation")
    # logger.info(f"   • Professional dashboard integration")
    
    logger.info(f"💡 POTENTIAL P&L DISPLAY:")
    logger.info(f"   • Shows total profit if all TP1 hit")
    logger.info(f"   • Shows total loss if all SL hit")
    logger.info(f"   • P&L range visualization")
    logger.info(f"   • Hidden behind spoiler tags")
    
    logger.info(f"🔧 Resource Management:")
    logger.info(f"   • Memory leak prevention")
    logger.info(f"   • Connection pool optimization")
    logger.info(f"   • Graceful shutdown handling")
    logger.info(f"   • Background task management")
    
    logger.info(f"🚀 Bot ready! Use /start to begin trading.")
    logger.info(f"📱 Enhanced mobile experience with EXTERNAL POSITION ADOPTION and RESOURCE MANAGEMENT!")
    
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"❌ Error running bot: {e}", exc_info=True)
    finally:
        # Ensure cleanup runs
        if _global_app:
            try:
                asyncio.run(graceful_shutdown())
            except Exception as e:
                logger.error(f"Error in final cleanup: {e}")

if __name__ == "__main__":
    main()