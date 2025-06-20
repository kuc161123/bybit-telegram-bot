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

# Configuration for external position monitoring
ENABLE_EXTERNAL_POSITION_MONITORING = True  # Set to False to disable
READ_ONLY_MONITORING_CHAT_ID_BASE = 9000000000  # Base for synthetic chat IDs

async def create_read_only_chat_data_for_position(position: dict) -> dict:
    """
    NEW: Create READ-ONLY chat data for external positions
    
    This creates minimal data needed for P&L tracking WITHOUT any order management
    """
    try:
        symbol = position.get("symbol", "")
        side = position.get("side", "")
        size = Decimal(str(position.get("size", "0")))
        entry_price = Decimal(str(position.get("avgPrice", "0")))
        
        logger.info(f"🔍 Creating READ-ONLY monitoring data for external position: {symbol} {side} {size}")
        
        # Create MINIMAL read-only chat data (NO ORDER IDs, NO TP/SL PRICES)
        chat_data = {
            # Basic position info for tracking
            SYMBOL: symbol,
            SIDE: side,
            LAST_KNOWN_POSITION_SIZE: size,
            PRIMARY_ENTRY_PRICE: entry_price,
            
            # Mark as read-only external position
            "external_position": True,
            "read_only_monitoring": True,
            TRADING_APPROACH: "read_only",
            
            # NO TP/SL prices = NO automatic actions
            # NO order IDs = NO order management
            # NO leverage/margin = NO trade interference
            
            # Timestamp for tracking
            "external_adoption_time": time.time(),
        }
        
        logger.info(f"✅ READ-ONLY monitoring data created for {symbol} (NO order management)")
        return chat_data
        
    except Exception as e:
        logger.error(f"❌ Error creating read-only chat data for position: {e}")
        return {}

async def adopt_external_positions_for_monitoring(application: Application, external_positions: list):
    """
    NEW: Adopt external positions for READ-ONLY monitoring
    """
    try:
        if not ENABLE_EXTERNAL_POSITION_MONITORING:
            logger.info("📊 External position monitoring is disabled")
            return 0
        
        if not external_positions:
            logger.info("📊 No external positions to adopt")
            return 0
        
        logger.info(f"🔄 Adopting {len(external_positions)} external positions for READ-ONLY monitoring...")
        
        adopted_count = 0
        
        for i, position in enumerate(external_positions):
            try:
                symbol = position.get("symbol", "")
                side = position.get("side", "")
                
                # Create synthetic chat ID for this external position
                synthetic_chat_id = READ_ONLY_MONITORING_CHAT_ID_BASE + i + 1
                
                logger.info(f"📊 Adopting external position: {symbol} {side} → Chat {synthetic_chat_id}")
                
                # Create read-only chat data
                read_only_chat_data = await create_read_only_chat_data_for_position(position)
                
                if not read_only_chat_data:
                    logger.warning(f"⚠️ Failed to create read-only data for {symbol}")
                    continue
                
                # ENHANCED: Store external positions in bot_data (more reliable)
                if 'external_positions' not in application.bot_data:
                    application.bot_data['external_positions'] = {}
                application.bot_data['external_positions'][synthetic_chat_id] = read_only_chat_data
                logger.info(f"✅ READ-ONLY data stored in bot_data for {symbol}")
                
                # Start READ-ONLY monitoring
                try:
                    from execution.monitor import start_position_monitoring
                    await start_position_monitoring(application, synthetic_chat_id, read_only_chat_data)
                    logger.info(f"✅ READ-ONLY monitor started for external position: {symbol}")
                except Exception as monitor_error:
                    logger.error(f"❌ Error starting monitor for {symbol}: {monitor_error}")
                    continue
                
                adopted_count += 1
                
                # Small delay between adoptions
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"❌ Error adopting external position {position.get('symbol', 'unknown')}: {e}")
                continue
        
        if adopted_count > 0:
            logger.info(f"🎉 Successfully adopted {adopted_count} external positions for READ-ONLY monitoring!")
            logger.info(f"📊 These positions will be tracked for P&L but NO orders will be modified")
            await application.update_persistence()
        
        return adopted_count
        
    except Exception as e:
        logger.error(f"❌ Error in external position adoption: {e}")
        return 0

async def get_positions_requiring_monitoring():
    """
    ENHANCED: Get all positions from Bybit that require monitoring
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
    ENHANCED: Get all orders from Bybit that require monitoring
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

async def find_chat_data_for_symbol(application: Application, symbol: str, side: str = None):
    """
    ENHANCED: Find chat data that corresponds to a symbol/side combination
    """
    matching_chats = []
    
    try:
        # Check regular chat_data first
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
                
                # Match symbol first
                if chat_symbol == symbol:
                    # If side is specified, match it too
                    if side is None or chat_side == side:
                        matching_chats.append((chat_id, chat_data))
                        is_external = chat_data.get("external_position", False)
                        chat_type = "EXTERNAL" if is_external else "BOT"
                        logger.info(f"🎯 Found matching chat {chat_id} ({chat_type}) for {symbol} {side or 'any side'}")
            except Exception as e:
                logger.error(f"Error processing chat_data for chat {chat_id}: {e}")
                continue
        
        # Also check external positions stored in bot_data (fallback)
        try:
            external_positions = application.bot_data.get('external_positions', {})
            for chat_id, chat_data in external_positions.items():
                if not isinstance(chat_data, dict):
                    continue
                
                try:
                    chat_symbol = chat_data.get(SYMBOL)
                    chat_side = chat_data.get(SIDE)
                    
                    # Match symbol first
                    if chat_symbol == symbol:
                        # If side is specified, match it too
                        if side is None or chat_side == side:
                            # Avoid duplicates
                            if (chat_id, chat_data) not in matching_chats:
                                matching_chats.append((chat_id, chat_data))
                                logger.info(f"🎯 Found matching external chat {chat_id} (EXTERNAL) for {symbol} {side or 'any side'}")
                except Exception as e:
                    logger.error(f"Error processing external position for chat {chat_id}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error accessing external positions from bot_data: {e}")
        
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
        status = await get_monitor_task_status(chat_id, chat_data.get(SYMBOL, ""))
        
        if status.get("running", False):
            is_external = chat_data.get("external_position", False)
            monitor_type = "READ-ONLY" if is_external else "FULL"
            logger.info(f"✅ {monitor_type} monitor for {chat_data.get(SYMBOL)} in chat {chat_id} is actively running")
            return True
        else:
            logger.info(f"🔄 Monitor task for {chat_data.get(SYMBOL)} in chat {chat_id} needs restart")
            return False
        
    except Exception as e:
        logger.error(f"Error verifying monitor status for chat {chat_id}: {e}")
        return False

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
                    is_external = chat_data.get("external_position", False)
                    monitor_type = "READ-ONLY" if is_external else "FULL"
                    logger.info(f"✅ {monitor_type} monitor already running for {symbol} in chat {chat_id}")
                    continue
                
                # Update chat data with current position info
                chat_data[LAST_KNOWN_POSITION_SIZE] = position["size"]
                
                # Determine approach for proper monitoring
                approach = chat_data.get(TRADING_APPROACH, "fast")
                is_external = chat_data.get("external_position", False)
                
                # Start monitoring
                from execution.monitor import start_position_monitoring
                await start_position_monitoring(application, int(chat_id), chat_data)
                
                monitor_type = "READ-ONLY" if is_external else "FULL"
                logger.info(f"✅ {monitor_type} monitor restored for {symbol} ({approach}) in chat {chat_id}")
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
                                
                                is_external = chat_data.get("external_position", False)
                                monitor_type = "READ-ONLY" if is_external else "FULL"
                                logger.info(f"✅ {monitor_type} monitor restored for orders on {symbol} in chat {chat_id}")
                                restored_count += 1
                                
                                # Small delay between restorations
                                await asyncio.sleep(0.5)
                            else:
                                is_external = chat_data.get("external_position", False)
                                monitor_type = "READ-ONLY" if is_external else "FULL"
                                logger.info(f"✅ {monitor_type} monitor already running for orders on {symbol} in chat {chat_id}")
                        
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

async def clean_up_orphaned_monitors(application: Application):
    """
    ENHANCED: Clean up monitors for chats that no longer have active positions/orders
    """
    try:
        logger.info("🧹 Cleaning up orphaned monitors...")
        
        # Get current positions and orders from Bybit
        positions = await get_positions_requiring_monitoring()
        orders = await get_orders_requiring_monitoring()
        
        # Create sets of active symbols for quick lookup
        active_symbols_with_positions = {pos["symbol"] for pos in positions}
        active_symbols_with_orders = {order["symbol"] for order in orders}
        all_active_symbols = active_symbols_with_positions | active_symbols_with_orders
        
        cleaned_count = 0
        
        # Check each chat's monitor status
        for chat_id, chat_data in application.chat_data.items():
            if not isinstance(chat_data, dict):
                continue
            
            try:
                monitor_task_info = chat_data.get(ACTIVE_MONITOR_TASK, {})
                
                if not monitor_task_info.get("active"):
                    continue
                
                chat_symbol = chat_data.get(SYMBOL)
                is_external = chat_data.get("external_position", False)
                
                if chat_symbol and chat_symbol not in all_active_symbols:
                    # This chat has a monitor but no active positions/orders
                    monitor_type = "READ-ONLY" if is_external else "FULL"
                    logger.info(f"🧹 Cleaning up orphaned {monitor_type} monitor for {chat_symbol} in chat {chat_id}")
                    
                    # Stop the monitor
                    monitor_task_info["active"] = False
                    chat_data[ACTIVE_MONITOR_TASK] = {}
                    
                    # If it's an external position, remove the synthetic chat data
                    if is_external:
                        logger.info(f"🧹 Removing synthetic chat data for closed external position {chat_symbol}")
                    
                    cleaned_count += 1
                    
            except Exception as e:
                logger.error(f"Error cleaning up monitor for chat {chat_id}: {e}")
                continue
        
        if cleaned_count > 0:
            logger.info(f"🧹 Cleaned up {cleaned_count} orphaned monitors")
            await application.update_persistence()
        else:
            logger.info("🧹 No orphaned monitors found")
            
    except Exception as e:
        logger.error(f"❌ Error cleaning up orphaned monitors: {e}")

async def check_and_restart_position_monitors(application: Application):
    """
    ENHANCED: Comprehensive monitor restoration system with external position adoption
    """
    try:
        logger.info("🚀 Starting ENHANCED monitor restoration with EXTERNAL POSITION ADOPTION...")
        
        # Step 1: Get current positions and orders from Bybit
        logger.info("📊 Step 1: Fetching current positions and orders from Bybit...")
        positions = await get_positions_requiring_monitoring()
        orders = await get_orders_requiring_monitoring()
        
        if not positions and not orders:
            logger.info("✅ No active positions or orders found - no monitors needed")
            return
        
        logger.info(f"📊 Found {len(positions)} positions and {len(orders)} orders requiring monitoring")
        
        # Step 2: Separate positions with and without chat data
        logger.info("🔍 Step 2: Identifying bot vs external positions...")
        
        # DEBUG: Log persistence data status
        try:
            chat_data_count = len(application.chat_data) if hasattr(application.chat_data, '__len__') else 0
            bot_data_keys = list(application.bot_data.keys()) if hasattr(application.bot_data, 'keys') else []
            logger.info(f"🔍 DEBUG: chat_data entries: {chat_data_count}, bot_data keys: {bot_data_keys}")
            
            # Log symbols in chat_data
            symbols_in_chat_data = []
            try:
                for chat_id, chat_data in application.chat_data.items():
                    if isinstance(chat_data, dict):
                        symbol = chat_data.get(SYMBOL)
                        if symbol:
                            symbols_in_chat_data.append(f"{symbol}({chat_id})")
            except Exception as e:
                logger.warning(f"Could not enumerate chat_data: {e}")
            
            logger.info(f"🔍 DEBUG: Symbols in chat_data: {symbols_in_chat_data}")
        except Exception as e:
            logger.error(f"Error debugging persistence data: {e}")
        
        bot_positions = []
        external_positions = []
        
        for position in positions:
            symbol = position["symbol"]
            side = position["side"]
            
            # Check if we have chat data for this position
            matching_chats = await find_chat_data_for_symbol(application, symbol, side)
            
            if matching_chats:
                # Determine if this is a real BOT position or external position
                has_real_bot_chat = False
                has_external_chat = False
                
                for chat_id, chat_data in matching_chats:
                    is_external = chat_data.get("external_position", False)
                    if is_external:
                        has_external_chat = True
                    else:
                        has_real_bot_chat = True
                
                if has_real_bot_chat:
                    # Real BOT position - has actual chat_data (not external)
                    bot_positions.append(position)
                    chat_types = []
                    for chat_id, chat_data in matching_chats:
                        is_external = chat_data.get("external_position", False)
                        chat_types.append("EXTERNAL" if is_external else "BOT")
                    logger.info(f"🤖 BOT position: {symbol} {side} (Chat types: {', '.join(chat_types)})")
                elif has_external_chat:
                    # External position - only has external chat data
                    external_positions.append(position)
                    logger.info(f"🌍 EXTERNAL position: {symbol} {side} (from previous adoption)")
                else:
                    # Fallback - treat as external
                    external_positions.append(position)
                    logger.info(f"🌍 EXTERNAL position: {symbol} {side} (no clear classification)")
            else:
                # No chat data - EXTERNAL position
                external_positions.append(position)
                logger.info(f"🌍 EXTERNAL position: {symbol} {side}")
        
        logger.info(f"📊 Categorized: {len(bot_positions)} BOT positions, {len(external_positions)} EXTERNAL positions")
        
        # Step 3: Restore monitoring for bot positions
        logger.info("🤖 Step 3: Restoring monitoring for BOT positions...")
        restored_bot_positions = 0
        
        for position in bot_positions:
            try:
                success = await restore_monitoring_for_position(application, position)
                if success:
                    restored_bot_positions += 1
                    
                # Small delay between position restorations
                await asyncio.sleep(0.3)
                
            except Exception as e:
                logger.error(f"❌ Error restoring monitor for bot position {position.get('symbol', 'unknown')}: {e}")
                continue
        
        # Step 4: Adopt external positions for read-only monitoring
        logger.info("🌍 Step 4: Adopting EXTERNAL positions for READ-ONLY monitoring...")
        adopted_external_positions = await adopt_external_positions_for_monitoring(application, external_positions)
        
        # Step 5: Restore monitoring for orders
        logger.info("📋 Step 5: Restoring monitoring for orders...")
        restored_orders = await restore_monitoring_for_orders(application, orders)
        
        # Step 6: Clean up orphaned monitors
        logger.info("🧹 Step 6: Cleaning up orphaned monitors...")
        await clean_up_orphaned_monitors(application)
        
        # Step 7: Update persistence
        if restored_bot_positions > 0 or adopted_external_positions > 0 or restored_orders > 0:
            logger.info("💾 Step 7: Updating persistence...")
            await application.update_persistence()
        
        # Summary
        total_restored = restored_bot_positions + adopted_external_positions + (1 if restored_orders > 0 else 0)
        if total_restored > 0:
            logger.info(f"✅ ENHANCED Monitor Restoration with External Adoption Complete!")
            logger.info(f"   🤖 BOT positions monitored: {restored_bot_positions}")
            logger.info(f"   🌍 EXTERNAL positions adopted (READ-ONLY): {adopted_external_positions}")
            logger.info(f"   📋 Order groups monitored: {restored_orders}")
            logger.info(f"   💾 Persistence updated")
            
            if adopted_external_positions > 0:
                logger.info(f"🛡️ SAFETY: External positions have READ-ONLY monitoring (NO order interference)")
        else:
            logger.info("✅ ENHANCED Monitor Restoration: No restoration needed")
            logger.info("   📊 All active positions/orders already monitored")
        
    except Exception as e:
        logger.error(f"❌ Error in ENHANCED monitor restoration with external adoption: {e}", exc_info=True)

async def auto_restart_monitors_with_delay(application: Application):
    """Restart monitors with a delay to ensure everything is initialized"""
    try:
        await asyncio.sleep(3)
        logger.info("🔄 Starting ENHANCED automatic monitor restart check with EXTERNAL ADOPTION...")
        await check_and_restart_position_monitors(application)
    except Exception as e:
        logger.error(f"❌ Error in delayed ENHANCED monitor restart: {e}")

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
        
        logger.info("🧹 Running startup orphaned order cleanup...")
        
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
    """Enhanced post-initialization with EXTERNAL POSITION ADOPTION and better resource management"""
    global _global_app
    _global_app = application
    
    logger.info("🚀 Enhanced Trading Bot initializing with EXTERNAL POSITION ADOPTION...")
    
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
        STATS_CONSERVATIVE_TP1_CANCELLATIONS: 0
    }
    
    for stat_key, default_val in stats_defaults.items():
        if stat_key not in application.bot_data:
            application.bot_data[stat_key] = default_val
    
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
    
    # ENHANCED: Start background tasks (within async context)
    await start_background_tasks()
    
    # ENHANCED: Monitor restoration with external position adoption
    logger.info("🔄 Initializing ENHANCED monitor restoration with EXTERNAL ADOPTION...")
    asyncio.create_task(auto_restart_monitors_with_delay(application))
    
    # Order cleanup
    logger.info("🧹 Initializing order cleanup...")
    asyncio.create_task(startup_order_cleanup())
    
    await application.update_persistence()
    logger.info("✅ Enhanced bot initialization with EXTERNAL POSITION ADOPTION completed!")

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
    
    logger.info(f"🚀 Enhanced Trading Bot starting with EXTERNAL POSITION ADOPTION!")
    logger.info(f"📱 Mobile-first design with manual trading optimization")
    logger.info(f"Environment: {'TESTNET' if USE_TESTNET else 'LIVE'}")
    logger.info(f"Version: Enhanced Manual v5.2 - EXTERNAL ADOPTION + RESOURCE MANAGEMENT")
    
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
    logger.info(f"🌍 EXTERNAL Position Adoption: Read-only monitoring for external trades")
    logger.info(f"🧹 Order Cleanup: Prevention of orphaned orders")
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
        "🌍 External Position Adoption",
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
    logger.info(f"   • Automatic orphaned monitor cleanup")
    logger.info(f"   • Conservative and fast approach support")
    
    logger.info(f"🌍 EXTERNAL Position Adoption:")
    logger.info(f"   • READ-ONLY monitoring for external positions")
    logger.info(f"   • P&L tracking without order interference") 
    logger.info(f"   • Combined dashboard view of all positions")
    logger.info(f"   • Performance stats for external trades")
    logger.info(f"   • SAFE: No modification of external orders")
    
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