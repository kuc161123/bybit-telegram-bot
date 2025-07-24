#!/usr/bin/env python3
"""
Enhanced manual close logging patch
Ensures all manual closes are properly logged to trade history
"""

# This patch should be applied to execution/monitor.py

MANUAL_CLOSE_LOGGING_PATCH = '''
# Add this import at the top
from utils.trade_logger import log_order_fill, log_manual_close

# Replace the manual close detection section (around line 2177) with:

                        close_reason = "MANUAL_CLOSE"
                        final_pnl = last_known_pnl
                        
                        # REFINED: Better P&L calculation - use last_position_data if position is empty
                        position_for_pnl = last_position_data if last_position_data else position
                        if position_for_pnl:
                            final_pnl = await calculate_accurate_pnl(position_for_pnl, chat_data)
                        else:
                            # Fallback to last known P&L
                            final_pnl = last_known_pnl
                        logger.info(f"📊 Position closed - Final P&L calculated: {final_pnl}")
                        
                        # Log manual close to trade history
                        try:
                            # Get fill price (use current price as exit price for manual close)
                            exit_price = current_price if current_price else safe_decimal_conversion(position_for_pnl.get("markPrice", "0"))
                            fill_qty = last_position_size if last_position_size else safe_decimal_conversion(position_for_pnl.get("size", "0"))
                            
                            # Log the manual close fill
                            await log_order_fill(
                                symbol=symbol,
                                side=side,
                                order_type="Manual",
                                fill_price=exit_price,
                                fill_qty=fill_qty,
                                order_id=f"MANUAL_{int(time.time())}"
                            )
                            logger.info(f"✅ Logged manual close to trade history")
                            
                            # Also log specific manual close event
                            if hasattr(trade_logger, 'log_manual_close'):
                                await trade_logger.log_manual_close(
                                    symbol=symbol,
                                    side=side,
                                    approach=approach,
                                    entry_price=entry_price,
                                    exit_price=exit_price,
                                    size=fill_qty,
                                    pnl=final_pnl,
                                    reason="Manual position close"
                                )
                                logger.info(f"✅ Logged manual close event details")
                                
                        except Exception as log_error:
                            logger.error(f"Failed to log manual close to trade history: {log_error}")
'''

# Add this method to TradeLogger class in utils/trade_logger.py:

TRADE_LOGGER_ENHANCEMENT = '''
    async def log_manual_close(self, symbol: str, side: str, approach: str,
                             entry_price: Decimal, exit_price: Decimal, 
                             size: Decimal, pnl: Decimal, reason: str = "Manual close"):
        """Log manual position close with full details"""
        try:
            history = await self._load_history()
            
            # Find active trade
            trade_key = await self._find_active_trade(history, symbol, side, approach)
            
            if trade_key:
                close_data = {
                    "type": "manual_close",
                    "timestamp": datetime.utcnow().isoformat(),
                    "entry_price": str(entry_price),
                    "exit_price": str(exit_price),
                    "size": str(size),
                    "pnl": str(pnl),
                    "reason": reason
                }
                
                # Add to fills as a manual close
                history[trade_key]["fills"].append({
                    "type": "Manual",
                    "price": str(exit_price),
                    "quantity": str(size),
                    "timestamp": datetime.utcnow().isoformat(),
                    "order_id": f"MANUAL_{int(time.time())}"
                })
                
                # Mark trade as closed
                history[trade_key]["status"] = "closed"
                history[trade_key]["close_reason"] = "manual"
                history[trade_key]["close_data"] = close_data
                
                await self._save_history(history)
                logger.info(f"Logged manual close for {trade_key}: P&L={pnl}")
                
        except Exception as e:
            logger.error(f"Error logging manual close: {e}")
'''

print("Manual close logging enhancement patch ready!")
print("\nTo apply:")
print("1. Add the import and manual close detection code to execution/monitor.py")
print("2. Add the log_manual_close method to utils/trade_logger.py")
print("\nThis ensures all manual closes are properly tracked in trade history.")