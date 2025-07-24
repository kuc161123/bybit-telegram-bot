#!/usr/bin/env python3
"""
Enhanced monitoring patch for execution/enhanced_tp_sl_manager.py

Key improvements:
1. Remove fill percentage restrictions for limit order alerts
2. Always adjust TP/SL orders when position size changes
3. Send alerts for ALL limit fills, not just small ones
4. Better position change detection
"""

# Apply these changes to execution/enhanced_tp_sl_manager.py:

# 1. Around line 1333 - Position increase detection
# When position size increases, ALWAYS:
# - Mark limit_orders_filled = True
# - Call _adjust_all_orders_for_partial_fill()
# - Send limit fill alert

# 2. Around line 1472 - Fix limit fill alert condition
# OLD (problematic):
if not limit_orders_filled and fill_percentage < 50:
    # Only sends alert for fills under 50%
    
# NEW (fixed):
if not limit_orders_filled and current_size > 0:
    # Send alert for ANY limit fill
    await self._send_trade_alert(
        symbol=symbol,
        message=(
            f"🔔 <b>Limit Orders Filled - {symbol}</b>\n\n"
            f"Account: {account_type.upper()}\n"
            f"Filled: {current_size:.1f} / {position_size:.1f} ({fill_percentage:.1f}%)\n"
            f"Avg Entry: {entry_price}\n\n"
            f"✅ Position partially filled via limit orders"
        ),
        chat_id=chat_id
    )
    
    # Mark as filled
    monitor_data['limit_orders_filled'] = True
    
    # ALWAYS adjust orders regardless of fill percentage
    await self._adjust_all_orders_for_partial_fill(
        symbol, side, current_size, position_size, 
        monitor_data, account_type
    )

# 3. Ensure TP/SL quantities match actual position size
# In _adjust_all_orders_for_partial_fill():
# - Recalculate all TP quantities based on ACTUAL filled size
# - Update SL quantity to match current position size
# - Don't assume any specific fill pattern

# 4. Better state management
# - Always update remaining_size when position changes
# - Track actual_filled_size separately from position_size
# - Don't rely on phase alone to determine if orders need adjustment
