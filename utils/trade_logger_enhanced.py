#!/usr/bin/env python3
"""
Wrapper for enhanced trade logger to maintain compatibility with existing code.
"""

from utils.enhanced_trade_logger import (
    enhanced_trade_logger,
    log_trade_entry as enhanced_log_trade_entry,
    log_order_event,
    log_position_update,
    update_performance,
    get_active_trades,
    export_report
)

# Create wrapper class for compatibility
class TradeLoggerWrapper:
    """Wrapper to maintain compatibility with existing trade logger interface."""

    def __init__(self):
        self.logger = enhanced_trade_logger

    async def log_trade_entry(self, symbol, side, approach, entry_price, size,
                            order_type="Market", chat_id=None, leverage=None,
                            risk_percentage=None, **kwargs):
        """Log trade entry with enhanced details."""
        # Add any limit orders if passed
        limit_orders = kwargs.pop('limit_orders', [])
        take_profits = kwargs.pop('take_profits', [])
        stop_loss = kwargs.pop('stop_loss', None)

        return await enhanced_log_trade_entry(
            symbol=symbol,
            side=side,
            approach=approach,
            entry_price=entry_price,
            size=size,
            order_type=order_type,
            chat_id=chat_id,
            leverage=leverage,
            risk_percentage=risk_percentage,
            limit_orders=limit_orders,
            take_profits=take_profits,
            stop_loss=stop_loss,
            **kwargs
        )

    async def log_tp_orders(self, trade_key, tp_orders):
        """Log TP orders - now handled in trade entry."""
        # In enhanced logger, this is handled during trade entry
        # But we'll log as order events for compatibility
        if trade_key:
            for order in tp_orders:
                await log_order_event(
                    trade_key,
                    "placed",
                    "tp",
                    order.get('orderId', ''),
                    order
                )

    async def log_sl_order(self, trade_key, sl_order):
        """Log SL order - now handled in trade entry."""
        if trade_key:
            await log_order_event(
                trade_key,
                "placed",
                "sl",
                sl_order.get('orderId', ''),
                sl_order
            )

    async def log_order_fill(self, symbol, side, order_type, fill_price, fill_qty, order_id=None):
        """Log order fill."""
        # Find active trade for this symbol
        trades = await get_active_trades()
        for trade in trades:
            if trade['symbol'] == symbol and trade['side'] == side:
                await log_order_event(
                    trade['trade_id'],
                    "filled",
                    order_type.lower(),
                    order_id or '',
                    {
                        'fill_price': str(fill_price),
                        'fill_qty': str(fill_qty),
                        'order_type': order_type
                    }
                )
                break

    async def log_position_merge(self, symbol, side, approach, old_sizes, new_size, new_avg_price):
        """Log position merge."""
        trades = await get_active_trades()
        for trade in trades:
            if trade['symbol'] == symbol and trade['side'] == side:
                await log_position_update(
                    trade['trade_id'],
                    "merge",
                    {
                        'old_sizes': [str(s) for s in old_sizes],
                        'new_size': str(new_size),
                        'new_avg_price': str(new_avg_price)
                    }
                )
                break

    async def log_rebalance(self, symbol, side, approach, details):
        """Log rebalance event."""
        trades = await get_active_trades()
        for trade in trades:
            if trade['symbol'] == symbol and trade['side'] == side:
                await log_position_update(
                    trade['trade_id'],
                    "rebalance",
                    details
                )
                break

# Global instance
trade_logger = TradeLoggerWrapper()

# Export wrapper methods as standalone functions for compatibility
log_trade_entry = trade_logger.log_trade_entry
log_tp_orders = trade_logger.log_tp_orders
log_sl_order = trade_logger.log_sl_order

# Export all functions for compatibility
__all__ = [
    'trade_logger',
    'log_trade_entry',
    'log_tp_orders',
    'log_sl_order',
    'log_order_event',
    'log_position_update',
    'update_performance',
    'get_active_trades',
    'export_report'
]
