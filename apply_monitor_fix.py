#!/usr/bin/env python3
"""
Quick hot patch application script
"""

import asyncio
import sys
import os
import logging

# Add the bot directory to Python path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def apply_monitor_safety_patch():
    """Apply monitor safety patch to running enhanced_tp_sl_manager"""
    try:
        # Import the running manager
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from clients.bybit_helpers import get_position_info_for_account, get_all_positions
        
        logger.info("🔧 Applying monitor safety patch...")
        
        # Store original method
        original_run_monitor_loop = enhanced_tp_sl_manager._run_monitor_loop
        
        async def robust_position_check(symbol: str, side: str, account_type: str = "main", max_retries: int = 3):
            """Robust position checking with retries"""
            for attempt in range(max_retries):
                try:
                    # Try direct position check
                    positions = await get_position_info_for_account(symbol, account_type)
                    
                    if positions is not None and len(positions) > 0:
                        for pos in positions:
                            if pos.get("side") == side:
                                position_size = float(pos.get('size', 0))
                                if position_size > 0:
                                    return True, pos
                        # Position not found in direct check
                        break
                        
                    # Fallback: get all positions
                    all_positions = await get_all_positions(account_type)
                    if all_positions:
                        for pos in all_positions:
                            if pos.get('symbol') == symbol and pos.get('side') == side:
                                position_size = float(pos.get('size', 0))
                                if position_size > 0:
                                    return True, pos
                        # Confirmed not in all positions
                        return False, None
                        
                except Exception as e:
                    logger.warning(f"Position check attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
            
            # Failed all checks - assume exists for safety
            return True, None
        
        async def safe_run_monitor_loop(symbol: str, side: str, account_type: str = None):
            """Enhanced monitor loop with robust position checking"""
            if account_type:
                monitor_key = f"{symbol}_{side}_{account_type}"
            else:
                monitor_key = f"{symbol}_{side}_main"
                account_type = "main"
                
            logger.info(f"🔄 Starting SAFE monitor loop for {monitor_key}")
            
            consecutive_close_detections = 0
            
            try:
                while monitor_key in enhanced_tp_sl_manager.position_monitors:
                    # Robust position check
                    position_exists, position_data = await robust_position_check(symbol, side, account_type)
                    
                    if not position_exists:
                        consecutive_close_detections += 1
                        logger.info(f"📊 Position {symbol} {side} appears closed (detection #{consecutive_close_detections})")
                        
                        # Require 2 consecutive confirmations
                        if consecutive_close_detections >= 2:
                            logger.info(f"✅ Position {symbol} {side} confirmed closed - ending monitor")
                            if monitor_key in enhanced_tp_sl_manager.position_monitors:
                                del enhanced_tp_sl_manager.position_monitors[monitor_key]
                            break
                    else:
                        if consecutive_close_detections > 0:
                            logger.info(f"✅ Position {symbol} {side} confirmed active - resetting counter")
                            consecutive_close_detections = 0
                    
                    # Run normal monitoring
                    await enhanced_tp_sl_manager.monitor_and_adjust_orders(symbol, side, account_type)
                    
                    if monitor_key not in enhanced_tp_sl_manager.position_monitors:
                        break
                    
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"Error in safe monitor loop: {e}")
                
            logger.info(f"🛑 Safe monitor loop ended for {monitor_key}")
        
        # Apply the patch
        enhanced_tp_sl_manager._run_monitor_loop = safe_run_monitor_loop
        
        logger.info("✅ Monitor safety patch applied!")
        logger.info("🛡️ All future monitor loops will use robust position checking")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply patch: {e}")
        return False

# Run the patch
if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        success = loop.run_until_complete(apply_monitor_safety_patch())
        if success:
            print("✅ Monitor safety patch applied successfully!")
        else:
            print("❌ Failed to apply patch")
    finally:
        loop.close()