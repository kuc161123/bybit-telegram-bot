#!/usr/bin/env python3
"""
Enhance trade logging to properly track manual closes and prevent duplicates
"""

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Step 1: Add manual close logging method to trade_logger.py
TRADE_LOGGER_ENHANCEMENT = '''
# Add this method to the TradeLogger class in utils/trade_logger.py

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

# Step 2: Fix duplicate prevention in monitor.py
MONITOR_DUPLICATE_FIX = '''
# In execution/monitor.py, update the _trade_history class to prevent duplicates better

class TradeHistoryTracker:
    """Track processed trades to prevent duplicate stats updates"""
    
    def __init__(self):
        self.processed_trades = set()
        self.trade_details = {}
        
    async def generate_trade_id(self, symbol: str, side: str, entry_price: Decimal, 
                               close_time: float, pnl: Decimal) -> str:
        """Generate unique trade ID"""
        # Include more details in the hash to ensure uniqueness
        trade_data = f"{symbol}_{side}_{entry_price}_{close_time}_{pnl}"
        trade_hash = hashlib.md5(trade_data.encode()).hexdigest()[:12]
        return trade_hash
        
    async def is_trade_processed(self, trade_id: str) -> bool:
        """Check if trade already processed"""
        return trade_id in self.processed_trades
        
    async def mark_trade_processed(self, trade_id: str, details: dict):
        """Mark trade as processed with details"""
        self.processed_trades.add(trade_id)
        self.trade_details[trade_id] = details
        
        # Keep only last 100 trades to prevent memory growth
        if len(self.processed_trades) > 100:
            oldest_trades = sorted(self.processed_trades)[:50]
            for old_trade in oldest_trades:
                self.processed_trades.remove(old_trade)
                self.trade_details.pop(old_trade, None)
'''

# Step 3: Enhanced manual close detection with trade logging
MANUAL_CLOSE_DETECTION = '''
# In monitor.py, around line 2177, enhance the manual close detection:

                    if not position_closed and last_position_size and last_position_size > 0:
                        logger.info(f"🎯 POSITION CLOSED DETECTED for {symbol} ({monitoring_mode})")
                        
                        # Determine close reason and final P&L
                        close_reason = "MANUAL_CLOSE"
                        final_pnl = last_known_pnl
                        
                        # Better P&L calculation
                        position_for_pnl = last_position_data if last_position_data else position
                        if position_for_pnl:
                            final_pnl = await calculate_accurate_pnl(position_for_pnl, chat_data)
                        else:
                            final_pnl = last_known_pnl
                        logger.info(f"📊 Position closed - Final P&L calculated: {final_pnl}")
                        
                        # Log manual close to trade history
                        try:
                            from utils.trade_logger import log_order_fill, trade_logger
                            
                            # Get exit price and quantities
                            exit_price = current_price if current_price else safe_decimal_conversion(
                                position_for_pnl.get("markPrice", "0")
                            )
                            fill_qty = last_position_size if last_position_size else safe_decimal_conversion(
                                position_for_pnl.get("size", "0")
                            )
                            
                            # Log the manual close fill
                            await log_order_fill(
                                symbol=symbol,
                                side=side,
                                order_type="Manual",
                                fill_price=exit_price,
                                fill_qty=fill_qty,
                                order_id=f"MANUAL_{int(time.time())}"
                            )
                            logger.info(f"✅ Logged manual close fill to trade history")
                            
                            # Log detailed manual close event
                            if hasattr(trade_logger, 'log_manual_close'):
                                await trade_logger.log_manual_close(
                                    symbol=symbol,
                                    side=side,
                                    approach=approach,
                                    entry_price=entry_price,
                                    exit_price=exit_price,
                                    size=fill_qty,
                                    pnl=final_pnl,
                                    reason="Manual position close detected"
                                )
                                logger.info(f"✅ Logged manual close event details")
                                
                        except Exception as log_error:
                            logger.error(f"Failed to log manual close: {log_error}")
'''

print("=" * 60)
print("Trade Logging Enhancement Instructions")
print("=" * 60)
print("\n1. Add the log_manual_close method to TradeLogger class in utils/trade_logger.py")
print("\n2. Update the TradeHistoryTracker class in execution/monitor.py to prevent duplicates")
print("\n3. Enhance manual close detection in monitor.py to log to trade history")
print("\n4. Restart the bot to apply changes")
print("\nThese changes will ensure:")
print("- All manual closes are properly logged to trade history")
print("- Duplicate trade stats are prevented")
print("- Accurate profit factor and performance metrics")
print("=" * 60)