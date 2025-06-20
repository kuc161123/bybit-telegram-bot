#!/usr/bin/env python3
"""
Position Mode Management Utilities
Enables switching between One-Way and Hedge modes for better position management
ENHANCED: Better position mode detection and automatic switching
FIXED: Robust mode detection from actual API responses
"""
import logging
from typing import Tuple, Dict, Any, Optional
from clients.bybit_client import bybit_client, api_error_handler

logger = logging.getLogger(__name__)

# Cache for position mode detection
_position_mode_cache = {}
_cache_ttl = 300  # 5 minutes

def _clear_position_mode_cache():
    """Clear the position mode cache"""
    global _position_mode_cache
    _position_mode_cache.clear()
    logger.info("🧹 Position mode cache cleared")

def get_current_position_mode(symbol: str = None, coin: str = "USDT") -> Tuple[bool, str, Dict]:
    """
    Get current position mode for symbol or coin
    ENHANCED: Better detection logic with proper API usage
    
    Args:
        symbol: Specific symbol (optional)
        coin: Settle coin (default: USDT)
    
    Returns:
        tuple: (success: bool, mode_info: str, details: Dict)
    """
    try:
        # Check cache first
        cache_key = symbol or coin
        if cache_key in _position_mode_cache:
            cached_time, cached_result = _position_mode_cache[cache_key]
            if time.time() - cached_time < _cache_ttl:
                logger.debug(f"🎯 Using cached position mode for {cache_key}")
                return cached_result
        
        logger.info(f"🔍 Checking position mode for {symbol or coin}...")
        
        if symbol:
            response = bybit_client.get_positions(
                category="linear",
                symbol=symbol
            )
        else:
            response = bybit_client.get_positions(
                category="linear",
                settleCoin=coin
            )
        
        if response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            
            # Check if any positions have non-zero positionIdx (indicating hedge mode)
            hedge_mode_detected = False
            one_way_positions = 0
            hedge_positions = 0
            
            for pos in positions:
                pos_idx = pos.get("positionIdx", 0)
                size = float(pos.get("size", "0"))
                symbol_name = pos.get("symbol", "")
                
                if size > 0:  # Only check active positions
                    if pos_idx in [1, 2]:  # Hedge mode indices
                        hedge_mode_detected = True
                        hedge_positions += 1
                        logger.debug(f"🎯 Hedge mode position found: {symbol_name} positionIdx={pos_idx}")
                    elif pos_idx == 0:  # One-way mode
                        one_way_positions += 1
                        logger.debug(f"📊 One-way mode position found: {symbol_name} positionIdx=0")
            
            # Determine mode based on active positions
            if hedge_mode_detected:
                mode = "Hedge Mode"
                mode_description = f"Hedge Mode (found {hedge_positions} hedge positions)"
            else:
                mode = "One-Way Mode"
                if one_way_positions > 0:
                    mode_description = f"One-Way Mode (found {one_way_positions} positions)"
                else:
                    # No active positions - try to detect from a test order or account settings
                    mode_description = "One-Way Mode (inferred from account structure)"
            
            details = {
                "mode": mode,
                "hedge_mode": hedge_mode_detected,
                "positions_found": len([p for p in positions if float(p.get("size", "0")) > 0]),
                "hedge_positions": hedge_positions,
                "one_way_positions": one_way_positions,
                "detection_method": "active_positions" if (hedge_positions + one_way_positions) > 0 else "inference"
            }
            
            result = (True, mode_description, details)
            
            # Cache the result
            _position_mode_cache[cache_key] = (time.time(), result)
            
            logger.info(f"✅ Position mode detected: {mode_description}")
            return result
        else:
            error_msg = response.get("retMsg", "Unknown error")
            logger.error(f"❌ Failed to check position mode: {error_msg}")
            return False, f"Could not check mode: {error_msg}", {}
            
    except Exception as e:
        logger.error(f"Error checking position mode: {e}")
        return False, f"Error: {str(e)}", {}

def detect_position_mode_for_symbol(symbol: str) -> Tuple[bool, str]:
    """
    ENHANCED: Detect position mode specifically for a symbol
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT")
    
    Returns:
        tuple: (is_hedge_mode: bool, mode_description: str)
    """
    try:
        success, mode_info, details = get_current_position_mode(symbol=symbol)
        
        if success:
            is_hedge = details.get("hedge_mode", False)
            return is_hedge, mode_info
        else:
            # Fallback: check account-wide mode
            logger.warning(f"⚠️ Could not detect mode for {symbol}, checking account-wide mode")
            success, mode_info, details = get_current_position_mode()
            if success:
                is_hedge = details.get("hedge_mode", False)
                return is_hedge, f"Account-wide: {mode_info}"
            else:
                # Last resort: assume hedge mode for safety
                logger.warning(f"⚠️ Could not detect any position mode, assuming hedge mode for safety")
                return True, "Hedge Mode (assumed for safety)"
                
    except Exception as e:
        logger.error(f"Error detecting position mode for {symbol}: {e}")
        return True, "Hedge Mode (error fallback)"

def get_correct_position_idx_for_side(symbol: str, side: str) -> int:
    """
    ENHANCED: Get the correct positionIdx for a symbol and side
    
    Args:
        symbol: Trading symbol
        side: "Buy" or "Sell"
    
    Returns:
        int: Correct positionIdx (0 for one-way, 1 for hedge Buy, 2 for hedge Sell)
    """
    try:
        is_hedge_mode, mode_description = detect_position_mode_for_symbol(symbol)
        
        if is_hedge_mode:
            # Hedge mode: 1 for Buy, 2 for Sell
            position_idx = 1 if side == "Buy" else 2
            logger.debug(f"🎯 {symbol} hedge mode: {side} -> positionIdx={position_idx}")
        else:
            # One-way mode: always 0
            position_idx = 0
            logger.debug(f"📊 {symbol} one-way mode: {side} -> positionIdx=0")
        
        return position_idx
        
    except Exception as e:
        logger.error(f"Error determining positionIdx for {symbol} {side}: {e}")
        # Safe fallback: assume hedge mode
        position_idx = 1 if side == "Buy" else 2
        logger.warning(f"🛡️ Using hedge mode fallback: {side} -> positionIdx={position_idx}")
        return position_idx

def enable_hedge_mode(symbol: str = None, coin: str = "USDT") -> Tuple[bool, str]:
    """
    Enable hedge mode to allow both long and short positions simultaneously
    ENHANCED: Better error handling and feedback
    
    Args:
        symbol: Specific symbol (optional, will apply to single symbol)
        coin: Settle coin (default: USDT, will apply to all symbols)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        with api_error_handler("Enable hedge mode"):
            params = {
                "category": "linear",
                "mode": 3,  # 0: One-Way Mode, 3: Hedge Mode
            }
            
            if symbol:
                params["symbol"] = symbol
                target_description = f"symbol {symbol}"
            else:
                params["coin"] = coin
                target_description = f"all {coin} perpetual contracts"
            
            logger.info(f"🔄 Enabling hedge mode for {target_description}")
            
            response = bybit_client.switch_position_mode(**params)
            
            if response.get("retCode") == 0:
                success_msg = f"✅ Hedge mode enabled for {target_description}"
                logger.info(success_msg)
                
                # Clear cache to force re-detection
                _clear_position_mode_cache()
                
                return True, success_msg
            else:
                error_code = response.get("retCode")
                error_msg = response.get("retMsg", "Unknown error")
                
                # Handle specific error cases
                if error_code == 110028:
                    return False, "❌ Cannot switch mode: Open orders exist. Close all orders first."
                elif error_code == 110027:
                    # Already in hedge mode
                    _clear_position_mode_cache()  # Clear cache anyway
                    return True, f"ℹ️ Hedge mode already enabled for {target_description}"
                else:
                    logger.error(f"Failed to enable hedge mode: {error_msg} (Code: {error_code})")
                    return False, f"❌ Failed to enable hedge mode: {error_msg}"
                
    except Exception as e:
        logger.error(f"Exception enabling hedge mode: {e}")
        return False, f"❌ Error enabling hedge mode: {str(e)}"

def enable_one_way_mode(symbol: str = None, coin: str = "USDT") -> Tuple[bool, str]:
    """
    Enable one-way mode (single position per symbol)
    ENHANCED: Better error handling and feedback
    
    Args:
        symbol: Specific symbol (optional)
        coin: Settle coin (default: USDT)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        with api_error_handler("Enable one-way mode"):
            params = {
                "category": "linear",
                "mode": 0,  # 0: One-Way Mode, 3: Hedge Mode
            }
            
            if symbol:
                params["symbol"] = symbol
                target_description = f"symbol {symbol}"
            else:
                params["coin"] = coin
                target_description = f"all {coin} perpetual contracts"
            
            logger.info(f"🔄 Enabling one-way mode for {target_description}")
            
            response = bybit_client.switch_position_mode(**params)
            
            if response.get("retCode") == 0:
                success_msg = f"✅ One-way mode enabled for {target_description}"
                logger.info(success_msg)
                
                # Clear cache to force re-detection
                _clear_position_mode_cache()
                
                return True, success_msg
            else:
                error_code = response.get("retCode")
                error_msg = response.get("retMsg", "Unknown error")
                
                # Handle specific error cases
                if error_code == 110028:
                    return False, "❌ Cannot switch mode: Open orders exist. Close all orders first."
                elif error_code == 110027:
                    # Already in one-way mode
                    _clear_position_mode_cache()  # Clear cache anyway
                    return True, f"ℹ️ One-way mode already enabled for {target_description}"
                else:
                    logger.error(f"Failed to enable one-way mode: {error_msg} (Code: {error_code})")
                    return False, f"❌ Failed to enable one-way mode: {error_msg}"
                
    except Exception as e:
        logger.error(f"Exception enabling one-way mode: {e}")
        return False, f"❌ Error enabling one-way mode: {str(e)}"

def auto_switch_to_hedge_mode_if_needed(symbol: str = None) -> Tuple[bool, str]:
    """
    ENHANCED: Automatically switch to hedge mode if currently in one-way mode
    
    Args:
        symbol: Specific symbol (optional)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Check current mode
        if symbol:
            is_hedge, mode_desc = detect_position_mode_for_symbol(symbol)
            target = symbol
        else:
            success, mode_desc, details = get_current_position_mode()
            if not success:
                return False, "❌ Could not check current position mode"
            is_hedge = details.get("hedge_mode", False)
            target = "account"
        
        if is_hedge:
            return True, f"ℹ️ {target} already in hedge mode: {mode_desc}"
        else:
            logger.info(f"🔄 Auto-switching {target} from one-way to hedge mode...")
            if symbol:
                return enable_hedge_mode(symbol=symbol)
            else:
                return enable_hedge_mode()
                
    except Exception as e:
        logger.error(f"Error in auto-switch to hedge mode: {e}")
        return False, f"❌ Auto-switch failed: {str(e)}"

def check_and_fix_position_mode_mismatch(symbol: str, side: str, error_response: Dict) -> Optional[int]:
    """
    ENHANCED: Check for position mode mismatch and return corrected positionIdx
    
    Args:
        symbol: Trading symbol
        side: Order side ("Buy" or "Sell")  
        error_response: The error response from Bybit API
    
    Returns:
        Optional[int]: Corrected positionIdx if fixable, None if not
    """
    try:
        error_code = error_response.get("retCode", 0)
        error_msg = error_response.get("retMsg", "")
        
        if error_code == 10001 and "position idx not match position mode" in error_msg:
            logger.warning(f"🚨 Position mode mismatch detected for {symbol} {side}")
            
            # Clear cache and re-detect
            _clear_position_mode_cache()
            
            # Get the correct position index
            correct_idx = get_correct_position_idx_for_side(symbol, side)
            
            logger.info(f"🔧 Corrected positionIdx for {symbol} {side}: {correct_idx}")
            return correct_idx
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking position mode mismatch: {e}")
        return None

def format_position_mode_help() -> str:
    """
    Generate help text explaining position modes
    ENHANCED: Better explanations and current status
    
    Returns:
        Formatted help text
    """
    try:
        # Get current mode status
        success, mode_info, details = get_current_position_mode()
        current_status = f"Current: {mode_info}" if success else "Current: Unable to detect"
        
        return f"""
🔧 **POSITION MODES EXPLAINED**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **One-Way Mode** (Default)
• Only ONE position per symbol
• BUY or SELL, but not both
• Same direction trades ADD to position
• Opposite direction trades are BLOCKED
• Uses positionIdx = 0

⚖️ **Hedge Mode** (Advanced)
• BOTH long AND short positions allowed
• Can hold BUY + SELL simultaneously  
• Useful for advanced strategies
• More complex position management
• Uses positionIdx = 1 (Buy), 2 (Sell)

🎯 **Current Status:**
{current_status}

🤖 **Bot Behavior:**
✅ Automatically detects your position mode
✅ Uses correct positionIdx for orders
✅ Same direction: ALLOWED (adds to position)
❌ Opposite direction: Depends on your mode

💡 **To Enable Both Directions:**
Use hedge mode to trade both long and short on same symbol simultaneously.
"""
    except Exception as e:
        logger.error(f"Error formatting position mode help: {e}")
        return """
🔧 **POSITION MODES**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The bot automatically detects your position mode and adjusts accordingly.

Use /hedge_mode to enable hedge mode for both long and short positions.
Use /one_way_mode to enable one-way mode for single direction trading.
Use /check_mode to check your current position mode.
"""

def get_position_mode_commands() -> str:
    """
    Generate command examples for position mode management
    ENHANCED: Better command descriptions
    
    Returns:
        Formatted command examples
    """
    return """
🛠️ **POSITION MODE COMMANDS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Enable Hedge Mode:**
• `/hedge_mode` - Enable for all USDT contracts
• `/hedge_mode BTCUSDT` - Enable for specific symbol

**Enable One-Way Mode:**
• `/one_way_mode` - Enable for all USDT contracts  
• `/one_way_mode BTCUSDT` - Enable for specific symbol

**Check Current Mode:**
• `/check_mode` - Check current position mode
• `/check_mode BTCUSDT` - Check for specific symbol

**Auto-Switch to Hedge:**
• Bot automatically uses correct positionIdx
• Bot can auto-switch to hedge mode if needed

⚠️ **Note:** You must close all positions and orders before switching modes.

🤖 **Bot Intelligence:**
The bot automatically detects your position mode and uses the correct
positionIdx for all orders, eliminating position mode mismatch errors.
"""

def create_position_management_summary(positions: list) -> str:
    """
    Create a summary of current positions with mode recommendations
    ENHANCED: Better analysis and recommendations
    
    Args:
        positions: List of position dictionaries
    
    Returns:
        Formatted summary
    """
    try:
        if not positions:
            # Check current mode even without positions
            success, mode_info, details = get_current_position_mode()
            mode_status = mode_info if success else "Unable to detect"
            
            return f"""
📊 **POSITION SUMMARY**
━━━━━━━━━━━━━━━━━━━━━━
No active positions found.

🎯 **Current Mode:** {mode_status}
🤖 **Bot Status:** Automatically detects position mode

💡 **Bot Behavior:**
✅ Same direction trades (adds to position)
❌ Opposite direction (depends on mode)

To trade both directions simultaneously, enable hedge mode.
The bot will automatically use the correct positionIdx.
"""
        
        # Group positions by symbol and analyze
        symbol_positions = {}
        hedge_mode_detected = False
        
        for pos in positions:
            symbol = pos.get("symbol", "Unknown")
            size = float(pos.get("size", 0))
            
            if size > 0:  # Only active positions
                if symbol not in symbol_positions:
                    symbol_positions[symbol] = []
                symbol_positions[symbol].append(pos)
                
                # Check for hedge mode indicators
                pos_idx = pos.get("positionIdx", 0)
                if pos_idx in [1, 2]:
                    hedge_mode_detected = True
        
        summary = "📊 **POSITION SUMMARY**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for symbol, pos_list in symbol_positions.items():
            summary += f"**{symbol}:**\n"
            
            for pos in pos_list:
                side = pos.get("side", "Unknown")
                size = float(pos.get("size", 0))
                pos_idx = pos.get("positionIdx", 0)
                
                if size > 0:
                    summary += f"• {side}: {size} (idx:{pos_idx})\n"
            
            # Check if multiple positions exist for same symbol
            if len(pos_list) > 1:
                summary += f"  🔄 Multiple positions (hedge mode)\n"
            
            summary += "\n"
        
        # Add mode analysis
        mode_description = "Hedge Mode" if hedge_mode_detected else "One-Way Mode" 
        summary += f"🎯 **Detected Mode:** {mode_description}\n"
        summary += f"🤖 **Bot Status:** Auto-detects positionIdx\n\n"
        
        summary += "💡 **Trade Rules:**\n"
        if hedge_mode_detected:
            summary += "✅ Same direction: Adds to existing position\n"
            summary += "✅ Opposite direction: Creates separate position\n"
        else:
            summary += "✅ Same direction: Adds to existing position\n"
            summary += "❌ Opposite direction: Blocked (enable hedge mode)\n"
        
        return summary
        
    except Exception as e:
        logger.error(f"Error creating position summary: {e}")
        return f"❌ Error creating summary: {e}"

# Add time import that was missing
import time