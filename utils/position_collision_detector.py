#!/usr/bin/env python3
"""
Position Collision Detection System
Prevents opening duplicate positions on the same symbol for both main and mirror accounts.
Ensures optimal Enhanced TP/SL system operation with one position per symbol per account.
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from decimal import Decimal
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Cache to avoid API spam
_position_cache = {}
_cache_ttl = 30  # 30 seconds cache

class PositionCollisionResult:
    """Result of position collision check"""
    def __init__(self):
        self.has_collision = False
        self.main_positions = []
        self.mirror_positions = []
        self.total_positions = 0
        self.formatted_summary = ""
        self.cache_used = False

async def check_existing_positions(symbol: str) -> PositionCollisionResult:
    """
    Check for existing positions on both main and mirror accounts for the given symbol.
    
    Args:
        symbol: Trading symbol to check (e.g., "BTCUSDT")
        
    Returns:
        PositionCollisionResult with collision status and position details
    """
    result = PositionCollisionResult()
    
    try:
        # Check cache first
        cache_key = f"positions_{symbol}"
        current_time = time.time()
        
        if cache_key in _position_cache:
            cached_data, cache_time = _position_cache[cache_key]
            if current_time - cache_time < _cache_ttl:
                logger.debug(f"Using cached position data for {symbol}")
                result = cached_data
                result.cache_used = True
                return result
        
        # Import here to avoid circular imports
        from clients.bybit_helpers import get_all_positions
        try:
            from clients.bybit_client import bybit_client_2
            has_mirror = True
        except ImportError:
            has_mirror = False
            logger.debug("Mirror account not configured")
        
        # Check main account positions
        logger.debug(f"Checking main account positions for {symbol}")
        try:
            main_positions = await get_all_positions()
            result.main_positions = [
                pos for pos in main_positions 
                if pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0
            ]
            logger.debug(f"Found {len(result.main_positions)} main positions for {symbol}")
        except Exception as e:
            logger.error(f"Failed to get main account positions: {e}")
            result.main_positions = []
        
        # Check mirror account positions if enabled
        if has_mirror:
            logger.debug(f"Checking mirror account positions for {symbol}")
            try:
                mirror_positions = await get_all_positions(client=bybit_client_2)
                result.mirror_positions = [
                    pos for pos in mirror_positions 
                    if pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0
                ]
                logger.debug(f"Found {len(result.mirror_positions)} mirror positions for {symbol}")
            except Exception as e:
                logger.error(f"Failed to get mirror account positions: {e}")
                result.mirror_positions = []
        
        # Calculate totals
        result.total_positions = len(result.main_positions) + len(result.mirror_positions)
        result.has_collision = result.total_positions > 0
        
        # Generate formatted summary
        if result.has_collision:
            result.formatted_summary = format_position_summary(
                symbol, result.main_positions, result.mirror_positions
            )
        
        # Cache the result
        _position_cache[cache_key] = (result, current_time)
        
        logger.info(f"Position collision check for {symbol}: {result.total_positions} existing positions")
        return result
        
    except Exception as e:
        logger.error(f"Error checking existing positions for {symbol}: {e}")
        # Return safe default - no collision detected on error
        result.has_collision = False
        result.formatted_summary = f"⚠️ Could not check existing positions for {symbol}. Proceeding with caution."
        return result

def format_position_summary(symbol: str, main_positions: List[Dict], mirror_positions: List[Dict]) -> str:
    """
    Format existing positions into a user-friendly summary for both accounts.
    
    Args:
        symbol: Trading symbol
        main_positions: List of main account positions
        mirror_positions: List of mirror account positions
        
    Returns:
        Formatted string summary of existing positions
    """
    if not main_positions and not mirror_positions:
        return ""
    
    summary = f"⚠️ <b>EXISTING POSITIONS DETECTED</b>\n\n"
    summary += f"📊 <b>{symbol}</b> already has open positions:\n\n"
    
    # Main account positions
    if main_positions:
        summary += f"📍 <b>MAIN ACCOUNT:</b>\n"
        for pos in main_positions:
            side = pos.get('side', 'Unknown')
            size = pos.get('size', '0')
            entry_price = pos.get('avgPrice', '0')
            unrealized_pnl = pos.get('unrealisedPnl', '0')
            
            # Format side with emoji
            side_emoji = "📈" if side == "Buy" else "📉" if side == "Sell" else "❓"
            
            # Format P&L with color indication
            pnl_float = float(unrealized_pnl) if unrealized_pnl else 0
            if pnl_float > 0:
                pnl_str = f"+${abs(pnl_float):,.2f} 🟢"
            elif pnl_float < 0:
                pnl_str = f"-${abs(pnl_float):,.2f} 🔴"
            else:
                pnl_str = f"${pnl_float:,.2f} ⚪"
            
            summary += f"• {side_emoji} {side} • Size: {size} • Entry: ${float(entry_price):,.4f}\n"
            summary += f"  P&L: {pnl_str}\n"
        summary += "\n"
    
    # Mirror account positions
    if mirror_positions:
        summary += f"🪞 <b>MIRROR ACCOUNT:</b>\n"
        for pos in mirror_positions:
            side = pos.get('side', 'Unknown')
            size = pos.get('size', '0')
            entry_price = pos.get('avgPrice', '0')
            unrealized_pnl = pos.get('unrealisedPnl', '0')
            
            # Format side with emoji
            side_emoji = "📈" if side == "Buy" else "📉" if side == "Sell" else "❓"
            
            # Format P&L with color indication
            pnl_float = float(unrealized_pnl) if unrealized_pnl else 0
            if pnl_float > 0:
                pnl_str = f"+${abs(pnl_float):,.2f} 🟢"
            elif pnl_float < 0:
                pnl_str = f"-${abs(pnl_float):,.2f} 🔴"
            else:
                pnl_str = f"${pnl_float:,.2f} ⚪"
            
            summary += f"• {side_emoji} {side} • Size: {size} • Entry: ${float(entry_price):,.4f}\n"
            summary += f"  P&L: {pnl_str}\n"
        summary += "\n"
    
    total_positions = len(main_positions) + len(mirror_positions)
    summary += f"📋 <b>Total: {total_positions} open position{'s' if total_positions != 1 else ''}</b>\n\n"
    summary += f"💡 <b>Recommendation:</b> Consider closing existing positions first\n"
    summary += f"⚠️ Multiple positions may conflict with Enhanced TP/SL system"
    
    return summary

def clear_position_cache(symbol: str = None):
    """
    Clear position cache for a specific symbol or all symbols.
    
    Args:
        symbol: Specific symbol to clear, or None to clear all
    """
    global _position_cache
    
    if symbol:
        cache_key = f"positions_{symbol}"
        if cache_key in _position_cache:
            del _position_cache[cache_key]
            logger.debug(f"Cleared position cache for {symbol}")
    else:
        _position_cache.clear()
        logger.debug("Cleared all position cache")

def get_cache_stats() -> Dict[str, Any]:
    """Get position cache statistics"""
    current_time = time.time()
    active_entries = 0
    expired_entries = 0
    
    for cache_key, (data, cache_time) in _position_cache.items():
        if current_time - cache_time < _cache_ttl:
            active_entries += 1
        else:
            expired_entries += 1
    
    return {
        "total_entries": len(_position_cache),
        "active_entries": active_entries,
        "expired_entries": expired_entries,
        "cache_ttl": _cache_ttl
    }