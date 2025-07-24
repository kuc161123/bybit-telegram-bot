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
from config.constants import BOT_PREFIX

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
    
    # Updated patterns to include BOT_ prefix
    conservative_patterns = ['CONS_', 'TP1_', 'TP2_', 'TP3_', 'TP4_', '_LIMIT']
    fast_patterns = ['FAST_', '_FAST_TP', '_FAST_SL', '_FAST_MARKET']
    ggshot_patterns = ['GGSHOT_', '_GGSHOT_', 'GGShot']
    
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
                chat_approach = "conservative"
                
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
        approach = "conservative"
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
            
            # Check if monitor is stale (older than 24 hours) AND has no active position
            started_at = task_info.get('started_at', 0)
            if started_at > 0 and (current_time - started_at) > 86400:  # 24 hours
                # Before removing, check if there's still an active position
                symbol = task_info.get('symbol')
                account_type = task_info.get('account_type', 'primary')
                
                has_active_position = False
                if symbol:
                    try:
                        if account_type == 'mirror':
                            # Check mirror account for active position
                            from execution.mirror_trader import get_mirror_positions
                            mirror_positions = await get_mirror_positions()
                            has_active_position = any(
                                pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0 
                                for pos in mirror_positions
                            )
                        else:
                            # Check primary account for active position
                            from clients.bybit_helpers import get_position_info
                            positions = await get_position_info(symbol)
                            has_active_position = any(
                                float(pos.get('size', 0)) > 0 for pos in positions
                            ) if positions else False
                    except Exception as e:
                        logger.warning(f"Could not check position for {symbol}: {e}")
                
                if not has_active_position:
                    stale_monitors.append(monitor_key)
                    logger.info(f"🗑️ Removing stale monitor {monitor_key} (age: {(current_time - started_at)/3600:.1f}h, active: {task_info.get('active', False)})")
                else:
                    logger.info(f"⏰ Keeping old monitor {monitor_key} (age: {(current_time - started_at)/3600:.1f}h) - position still active")
                continue
            
            # Check if monitor is marked as active but has no running task
            if task_info.get('active', False):
                chat_id = task_info.get('chat_id')
                symbol = task_info.get('symbol')
                approach = "conservative"
                
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
                approach = "conservative"
                
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
                    approach = "conservative"
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
            
            # Check if this position has any bot-initiated orders
            has_bot_orders = any(
                BOT_PREFIX in o.get('orderLinkId', '')
                for o in position_orders
            )
            
            # Skip monitoring for positions without bot orders (protect external positions)
            from config.constants import MANAGE_EXTERNAL_POSITIONS
            from utils.position_identifier import position_identifier
            
            # Use position identifier to check if this is a bot position
            is_bot_pos = position_identifier.is_bot_position(position, position_orders)
            
            if not is_bot_pos:
                logger.info(f"🛡️ Skipping external position {symbol} {side} - no bot orders found")
                continue
            
            logger.info(f"✅ Identified {symbol} {side} as bot position - will restore monitoring")
            
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
                                chat_approach = "conservative"
                                
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
                            "bot_position": True,  # Already filtered for bot orders above
                            "has_bot_orders": True  # Explicit flag for persistence
                        }
                        
                        # Add approach-specific order IDs if they match
                        if approach == "conservative" and position_orders:
                            tp_orders = [o for o in position_orders if o.get('orderLinkId', '').startswith('TP')]
                            sl_orders = [o for o in position_orders if o.get('orderLinkId', '').startswith('SL')]
                            # Detect limit entry orders (non-reduce-only Limit orders)
                            limit_orders = [o for o in position_orders if o.get('orderType') == 'Limit' and not o.get('reduceOnly', False)]
                            
                            if tp_orders:
                                tp_order_ids = [o.get('orderId') for o in sorted(tp_orders, key=lambda x: x.get('orderLinkId', ''))]
                                new_chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids
                            if sl_orders:
                                new_chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_orders[0].get('orderId')
                            if limit_orders:
                                limit_order_ids = [o.get('orderId') for o in sorted(limit_orders, key=lambda x: float(x.get('price', 0)))]
                                new_chat_data[LIMIT_ORDER_IDS] = limit_order_ids
                                logger.info(f"📝 Detected {len(limit_order_ids)} limit orders for {symbol} conservative approach")
                        
                        # Store in the main chat's data
                        if main_chat_id not in application.chat_data:
                            application.chat_data[main_chat_id] = {}
                        
                        # Create a unique key for this position including approach
                        position_key = f"position_{symbol}_{side}_{approach}"
                        application.chat_data[main_chat_id][position_key] = new_chat_data
                        
                        # Start monitoring
                        try:
                            from execution.monitor import start_position_monitoring, start_mirror_position_monitoring
                            await start_position_monitoring(application, int(main_chat_id), new_chat_data)
                            
                            # Also start mirror monitoring if mirror trading is enabled
                            try:
                                from execution.mirror_trader import is_mirror_trading_enabled
                                if is_mirror_trading_enabled():
                                    await start_mirror_position_monitoring(application, int(main_chat_id), new_chat_data)
                                    logger.info(f"✅ Started mirror monitor for {symbol} ({approach})")
                            except Exception as mirror_error:
                                logger.warning(f"Could not start mirror monitor for {symbol} ({approach}): {mirror_error}")
                            
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
                            chat_approach = "conservative"
                            
                            # Skip if approach doesn't match detected approach (if we detected one)
                            if detected_approach and chat_approach != detected_approach:
                                logger.info(f"⚠️ Skipping chat {chat_id} - approach mismatch: {chat_approach} != {detected_approach}")
                                continue
                            
                            # Check if this was a bot-initiated trade (from persistence)
                            if not chat_data.get("has_bot_orders", False) and not chat_data.get("bot_position", False):
                                logger.info(f"⏭️ Skipping external position from persistence: {symbol} {side}")
                                continue
                            
                            # All positions are bot trades now - no external positions
                            chat_data.pop("read_only_monitoring", None)
                            
                            # Verify if monitor is already running
                            is_running = await verify_monitor_status(chat_id, chat_data)
                            
                            if not is_running:
                                # Update chat data with current position info
                                chat_data[LAST_KNOWN_POSITION_SIZE] = position["size"]
                                
                                # Start monitoring
                                from execution.monitor import start_position_monitoring, start_mirror_position_monitoring
                                await start_position_monitoring(application, int(chat_id), chat_data)
                                
                                # Also restore mirror monitoring if mirror trading is enabled
                                try:
                                    from execution.mirror_trader import is_mirror_trading_enabled
                                    if is_mirror_trading_enabled():
                                        await start_mirror_position_monitoring(application, int(chat_id), chat_data)
                                        logger.info(f"✅ Restored mirror monitor for {symbol} ({chat_approach})")
                                except Exception as mirror_error:
                                    logger.warning(f"Could not restore mirror monitor for {symbol} ({chat_approach}): {mirror_error}")
                                
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
                
                # If no monitor found, detect and create monitors for all approaches used
                if not monitor_found:
                    # Analyze orders to detect which approaches were used
                    approaches_used = set()
                    
                    if position_orders:
                        # Check for conservative patterns
                        has_conservative = any(
                            'CONS_' in o.get('orderLinkId', '') or
                            o.get('orderLinkId', '').startswith(('TP1_', 'TP2_', 'TP3_', 'TP4_', 'SL_', '_LIMIT'))
                            for o in position_orders
                        )
                        # Check for fast patterns  
                        has_fast = any(
                            'FAST_' in o.get('orderLinkId', '') or
                            o.get('orderLinkId', '').startswith(('TP_', 'SL_')) or
                            (o.get('stopOrderType') in ['TakeProfit', 'StopLoss'] and 'CONS_' not in o.get('orderLinkId', ''))
                            for o in position_orders
                        )
                        
                        if has_conservative:
                            approaches_used.add("conservative")
                        if has_fast:
                            approach = "conservative"
                    
                    # If no patterns detected, use detected approach = "conservative"
                    if not approaches_used:
                        approach = "conservative"
                    
                    logger.info(f"📝 Creating monitors for {symbol} {side} with approaches: {list(approaches_used)}")
                    
                    # Create monitor for each detected approach
                    for approach in approaches_used:
                        logger.info(f"📝 Creating new chat data for position: {symbol} {side} ({approach})")
                        
                        # Create chat data for this position
                        new_chat_data = {
                            SYMBOL: symbol,
                            SIDE: side,
                            LAST_KNOWN_POSITION_SIZE: position["size"],
                            PRIMARY_ENTRY_PRICE: position.get("avgPrice", "0"),
                            TRADING_APPROACH: approach,
                            "position_created": True,
                            "bot_position": True,  # Already filtered for bot orders above
                            "has_bot_orders": True  # Explicit flag for persistence
                        }
                        
                        # Add approach-specific order IDs if available
                        if approach == "conservative" and position_orders:
                            tp_orders = [o for o in position_orders if o.get('orderLinkId', '').startswith('TP')]
                            sl_orders = [o for o in position_orders if o.get('orderLinkId', '').startswith('SL')]
                            # Detect limit entry orders (non-reduce-only Limit orders)
                            limit_orders = [o for o in position_orders if o.get('orderType') == 'Limit' and not o.get('reduceOnly', False)]
                            
                            if tp_orders:
                                tp_order_ids = [o.get('orderId') for o in sorted(tp_orders, key=lambda x: x.get('orderLinkId', ''))]
                                new_chat_data[CONSERVATIVE_TP_ORDER_IDS] = tp_order_ids
                            if sl_orders:
                                new_chat_data[CONSERVATIVE_SL_ORDER_ID] = sl_orders[0].get('orderId')
                            if limit_orders:
                                limit_order_ids = [o.get('orderId') for o in sorted(limit_orders, key=lambda x: float(x.get('price', 0)))]
                                new_chat_data[LIMIT_ORDER_IDS] = limit_order_ids
                                logger.info(f"📝 Detected {len(limit_order_ids)} limit orders for {symbol} conservative approach")
                        elif approach == "conservative" and position_orders:
                            # Enhanced Fast approach order detection
                            fast_tp_orders = []
                            fast_sl_orders = []
                            
                            for order in position_orders:
                                order_link_id = order.get('orderLinkId', '')
                                stop_order_type = order.get('stopOrderType', '')
                                
                                # TP detection - more flexible patterns
                                if (stop_order_type == 'TakeProfit' or 
                                    any(pattern in order_link_id for pattern in ['_FAST_TP', 'FAST_TP', '_TP', 'BOT_TP', 'BOT_FAST']) and
                                    'TP' in order_link_id):
                                    fast_tp_orders.append(order)
                                    
                                # SL detection - more flexible patterns
                                elif (stop_order_type == 'StopLoss' or 
                                      any(pattern in order_link_id for pattern in ['_FAST_SL', 'FAST_SL', '_SL', 'BOT_SL', 'BOT_FAST']) and
                                      'SL' in order_link_id):
                                    fast_sl_orders.append(order)
                            
                            if fast_tp_orders:
                                tp_order = fast_tp_orders[0]
                                tp_order_id = tp_order.get('orderId')
                                new_chat_data["tp_order_id"] = tp_order_id
                                new_chat_data[TP_ORDER_IDS] = [tp_order_id]
                                logger.info(f"📝 Detected fast TP order for {symbol}: {tp_order_id[:8]}... (trigger: {tp_order.get('triggerPrice')})")
                            else:
                                logger.warning(f"⚠️ No TP order found for {symbol} fast position")
                                
                            if fast_sl_orders:
                                sl_order = fast_sl_orders[0]
                                sl_order_id = sl_order.get('orderId')
                                new_chat_data[SL_ORDER_ID] = sl_order_id
                                new_chat_data["sl_order_id"] = sl_order_id
                                logger.info(f"📝 Detected fast SL order for {symbol}: {sl_order_id[:8]}... (trigger: {sl_order.get('triggerPrice')})")
                            else:
                                logger.warning(f"⚠️ No SL order found for {symbol} fast position")
                        
                        # Store in the main chat's data
                        if main_chat_id not in application.chat_data:
                            application.chat_data[main_chat_id] = {}
                        
                        # Create a unique key for this position including approach
                        position_key = f"position_{symbol}_{side}_{approach}"
                        application.chat_data[main_chat_id][position_key] = new_chat_data
                        
                        # Start monitoring
                        try:
                            from execution.monitor import start_position_monitoring, start_mirror_position_monitoring
                            await start_position_monitoring(application, int(main_chat_id), new_chat_data)
                            
                            # Also start mirror monitoring if mirror trading is enabled
                            try:
                                from execution.mirror_trader import is_mirror_trading_enabled
                                if is_mirror_trading_enabled():
                                    await start_mirror_position_monitoring(application, int(main_chat_id), new_chat_data)
                                    logger.info(f"✅ Started mirror monitor for {symbol} ({approach})")
                            except Exception as mirror_error:
                                logger.warning(f"Could not start mirror monitor for {symbol} ({approach}): {mirror_error}")
                            
                            logger.info(f"✅ Created new monitor for {symbol} ({approach}) in chat {main_chat_id}")
                            created_new_entries += 1
                        except Exception as e:
                            logger.error(f"❌ Error creating monitor for {symbol} ({approach}): {e}")
            
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
        
        # Check and rebalance Conservative positions on startup
        logger.info("🔄 Checking Conservative positions for rebalancing...")
        from startup_conservative_rebalancer import check_and_rebalance_conservative_positions
        # Get positions first
        positions = await get_positions_requiring_monitoring()
        await check_and_rebalance_conservative_positions(positions)
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
        
        # Start stats backup task
        try:
            from utils.stats_backup import auto_backup_stats
            stats_backup_task = asyncio.create_task(auto_backup_stats(_global_app))
            _cleanup_tasks.append(stats_backup_task)
            logger.info("✅ Stats backup task started")
        except Exception as e:
            logger.warning(f"Could not start stats backup task: {e}")
        
        # Start Enhanced TP/SL monitoring loop if enabled
        try:
            from config.settings import ENABLE_ENHANCED_TP_SL
            if ENABLE_ENHANCED_TP_SL:
                from helpers.background_tasks import enhanced_tp_sl_monitoring_loop
                enhanced_tp_sl_task = asyncio.create_task(enhanced_tp_sl_monitoring_loop())
                _cleanup_tasks.append(enhanced_tp_sl_task)
                logger.info("✅ Enhanced TP/SL monitoring task started (5s interval)")
                
                # Log mirror alert configuration status
                from config.constants import ENABLE_MIRROR_ALERTS
                if ENABLE_MIRROR_ALERTS:
                    logger.info("🔔 Mirror account alerts: ENABLED - Mirror positions will send separate alerts")
                else:
                    logger.info("🔕 Mirror account alerts: DISABLED - Preventing duplicate notifications")
                
                # Sync existing positions on startup
                try:
                    from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
                    await enhanced_tp_sl_manager.sync_existing_positions()
                    logger.info("✅ Initial position sync completed")
                except Exception as sync_error:
                    logger.warning(f"Could not sync existing positions: {sync_error}")
            else:
                logger.info("ℹ️ Enhanced TP/SL monitoring disabled")
        except Exception as e:
            logger.warning(f"Could not start Enhanced TP/SL monitoring: {e}")
        
        # Start conservative rebalancer only if enhanced TP/SL is disabled
        try:
            from config.settings import ENABLE_ENHANCED_TP_SL
            if not ENABLE_ENHANCED_TP_SL:
                from execution.conservative_rebalancer import conservative_rebalancer
                await conservative_rebalancer.start()
                logger.info("✅ Conservative rebalancer started (preserving trigger prices)")
            else:
                logger.info("ℹ️ Conservative rebalancer disabled - using Enhanced TP/SL system for order management")
        except Exception as e:
            logger.warning(f"Could not start conservative rebalancer: {e}")
        
        # Ensure all conservative positions are monitored
        try:
            from scripts.maintenance.ensure_conservative_monitoring import ensure_all_conservative_positions_monitored
            await ensure_all_conservative_positions_monitored()
            logger.info("✅ Conservative position monitoring check complete")
        except Exception as e:
            logger.warning(f"Could not run conservative monitoring check: {e}")
        
        # Start real-time market data WebSocket stream
        try:
            from market_analysis.realtime_data_stream import start_realtime_stream
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "SOLUSDT", "XRPUSDT"]
            realtime_task = asyncio.create_task(start_realtime_stream(symbols))
            _cleanup_tasks.append(realtime_task)
            logger.info(f"✅ Real-time market data stream started for {len(symbols)} symbols")
        except Exception as e:
            logger.warning(f"Could not start real-time market data stream: {e}")
        
        logger.info("✅ All background tasks started successfully")
        
    except Exception as e:
        logger.error(f"❌ Error starting background tasks: {e}")

async def enhanced_post_init(application: Application) -> None:
    """Enhanced post-initialization with better resource management"""
    global _global_app
    _global_app = application
    
    logger.info("🚀 Enhanced Trading Bot initializing...")
    
    # Initialize alert system with application reference
    try:
        from utils.alert_helpers import set_application
        set_application(application)
        logger.info("✅ Alert system initialized with application reference")
    except Exception as e:
        logger.warning(f"Could not initialize alert system: {e}")
    
    # Initialize persistence optimizer
    try:
        from utils.persistence_optimizer import persistence_optimizer
        persistence_optimizer.set_app(application)
        logger.info("✅ Persistence optimizer initialized")
    except Exception as e:
        logger.warning(f"Could not initialize persistence optimizer: {e}")
    
    # First, try to restore stats from backup if needed
    try:
        from utils.stats_backup import restore_stats
        stats_restored = await restore_stats(application.bot_data)
        if stats_restored:
            logger.info("📊 Stats restored from backup")
            await application.update_persistence()
    except Exception as e:
        logger.warning(f"Could not restore stats from backup: {e}")
    
    # Check if we have existing stats before initializing
    has_existing_stats = (
        application.bot_data.get(STATS_TOTAL_TRADES, 0) > 0 or
        application.bot_data.get(STATS_TOTAL_PNL, Decimal("0")) != Decimal("0")
    )
    
    # Initialize enhanced bot data
    stats_defaults = {
        STATS_TOTAL_TRADES: 0,
        STATS_TP1_HITS: 0,
        STATS_SL_HITS: 0,
        STATS_OTHER_CLOSURES: 0,
        STATS_TOTAL_PNL: Decimal("0"),
        STATS_WIN_STREAK: 0,
        STATS_LOSS_STREAK: 0,
        STATS_BEST_TRADE: Decimal("0"),
        STATS_WORST_TRADE: Decimal("0"),
        STATS_TOTAL_WINS: 0,
        STATS_TOTAL_LOSSES: 0,
        STATS_CONSERVATIVE_TRADES: 0,
        STATS_CONSERVATIVE_TP1_CANCELLATIONS: 0,
        # Additional stats for portfolio metrics
        'stats_total_wins_pnl': Decimal("0"),
        'stats_total_losses_pnl': Decimal("0"),
        'stats_max_drawdown': Decimal("0"),
        'stats_peak_equity': Decimal("0"),
        'stats_current_drawdown': Decimal("0"),
        'recent_trade_pnls': []
    }
    
    # Special handling for STATS_LAST_RESET
    if STATS_LAST_RESET not in application.bot_data:
        if has_existing_stats:
            # We have stats but STATS_LAST_RESET is missing - preserve stats
            application.bot_data[STATS_LAST_RESET] = application.bot_data.get('bot_start_time', time.time() - 86400)
            logger.warning("Found existing stats but STATS_LAST_RESET missing - preserving stats")
        else:
            # First time initialization
            application.bot_data[STATS_LAST_RESET] = time.time()
            logger.info("First time initialization - setting STATS_LAST_RESET")
    
    # Initialize only missing stats
    for stat_key, default_val in stats_defaults.items():
        if stat_key not in application.bot_data:
            application.bot_data[stat_key] = default_val
            logger.info(f"Initialized missing stat: {stat_key}")
    
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
    
    # Monitor restoration (disabled when Enhanced TP/SL is active)
    from config.settings import ENABLE_ENHANCED_TP_SL
    if not ENABLE_ENHANCED_TP_SL:
        logger.info("🔄 Initializing monitor restoration...")
        asyncio.create_task(auto_restart_monitors_with_delay(application))
    else:
        logger.info("ℹ️ Monitor restoration disabled - Enhanced TP/SL system handles monitoring")
    
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
        
        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
            if loop and not loop.is_closed():
                loop.create_task(graceful_shutdown())
            else:
                logger.warning("Event loop is not running or closed, cannot schedule graceful shutdown")
        except RuntimeError:
            # No event loop running, try to run shutdown directly
            logger.warning("No event loop running, attempting direct shutdown")
            try:
                asyncio.run(graceful_shutdown())
            except Exception as e:
                logger.error(f"Failed to run graceful shutdown: {e}")
    
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
        # Cancel all background tasks with timeout
        if _cleanup_tasks:
            logger.info(f"🔄 Cancelling {len(_cleanup_tasks)} background tasks...")
            for task in _cleanup_tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for all tasks to complete with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*_cleanup_tasks, return_exceptions=True),
                    timeout=5.0
                )
                logger.info("✅ All background tasks cancelled successfully")
            except asyncio.TimeoutError:
                logger.warning("⚠️ Some background tasks did not complete within timeout")
            except Exception as e:
                logger.warning(f"⚠️ Error during task cancellation: {e}")
        
        # Stop alert manager
        if _global_app:
            try:
                alert_manager = getattr(_global_app, '_alert_manager', None)
                if alert_manager:
                    await alert_manager.stop()
                    logger.info("✅ Alert manager stopped")
            except Exception as e:
                logger.error(f"Error stopping alert manager: {e}")
        
        # Stop auto-rebalancer - DISABLED
        # try:
        #     from execution.auto_rebalancer import stop_auto_rebalancer, is_auto_rebalancer_running
        #     if is_auto_rebalancer_running():
        #         await stop_auto_rebalancer()
        #         logger.info("✅ Auto-rebalancer stopped")
        # except Exception as e:
        #     logger.error(f"Error stopping auto-rebalancer: {e}")
        
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
        
        # Cleanup real-time data stream
        try:
            from market_analysis.realtime_data_stream import realtime_stream
            await realtime_stream.disconnect()
            logger.info("✅ Real-time data stream disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting real-time data stream: {e}")
        
        # Cleanup HTTP sessions
        try:
            from clients.bybit_client import cleanup_http_session
            await cleanup_http_session()
        except Exception as e:
            logger.error(f"Error cleaning up HTTP sessions: {e}")
        
        # Shutdown persistence optimizer and perform final update
        try:
            from utils.persistence_optimizer import shutdown_persistence_optimizer
            await shutdown_persistence_optimizer()
        except Exception as e:
            logger.error(f"Error shutting down persistence optimizer: {e}")
        
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
    
    # Register cleanup function with better error handling
    def cleanup_handler():
        if _global_app:
            try:
                # Try to use existing event loop if available
                loop = asyncio.get_event_loop()
                if loop and not loop.is_closed():
                    loop.run_until_complete(graceful_shutdown())
                else:
                    # Event loop is closed, create new one for cleanup
                    asyncio.run(graceful_shutdown())
            except RuntimeError:
                # No event loop or closed, create new one
                try:
                    asyncio.run(graceful_shutdown())
                except Exception as e:
                    logger.error(f"Failed to run cleanup: {e}")
            except Exception as e:
                logger.error(f"Error in atexit cleanup: {e}")
    
    atexit.register(cleanup_handler)
    
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
    logger.info(f"   • Conservative approach support only")
    
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