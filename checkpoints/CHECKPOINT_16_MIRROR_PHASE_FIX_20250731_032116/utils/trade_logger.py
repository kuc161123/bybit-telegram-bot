#!/usr/bin/env python3
"""
Trade Logger - Comprehensive logging system for all trade operations
Tracks entry prices, TP/SL levels, fills, merges, and rebalances
"""

import json
import os
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal
import asyncio
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

# Trade history file configuration
TRADE_HISTORY_DIR = "data"
TRADE_HISTORY_FILE = "trade_history.json"
TRADE_HISTORY_BACKUP = "trade_history_backup.json"
MAX_HISTORY_SIZE_MB = 50  # Rotate when file exceeds this size

class TradeLogger:
    """Comprehensive trade logging system"""

    def __init__(self):
        self.history_file = os.path.join(TRADE_HISTORY_DIR, TRADE_HISTORY_FILE)
        self.backup_file = os.path.join(TRADE_HISTORY_DIR, TRADE_HISTORY_BACKUP)
        self._ensure_data_dir()
        self._lock = asyncio.Lock()

    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        Path(TRADE_HISTORY_DIR).mkdir(parents=True, exist_ok=True)

    def _get_trade_key(self, symbol: str, side: str, approach: str, chat_id: str = None) -> str:
        """Generate unique trade key"""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        if chat_id:
            return f"{symbol}_{side}_{approach}_{chat_id}_{timestamp}"
        return f"{symbol}_{side}_{approach}_{timestamp}"

    async def _load_history(self) -> Dict:
        """Load trade history from file"""
        if not os.path.exists(self.history_file):
            return {}

        try:
            async with self._lock:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading trade history: {e}")
            return {}

    async def _save_history(self, history: Dict):
        """Save trade history to file with rotation check"""
        try:
            async with self._lock:
                # Check file size and rotate if needed
                if os.path.exists(self.history_file):
                    size_mb = os.path.getsize(self.history_file) / (1024 * 1024)
                    if size_mb > MAX_HISTORY_SIZE_MB:
                        await self._rotate_history()

                # Save current history
                with open(self.history_file, 'w') as f:
                    json.dump(history, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error saving trade history: {e}")

    async def _rotate_history(self):
        """Rotate history file when it gets too large"""
        try:
            # Create timestamped backup
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_file = os.path.join(TRADE_HISTORY_DIR, f"trade_history_{timestamp}.json")
            shutil.move(self.history_file, archive_file)
            logger.info(f"Rotated trade history to {archive_file}")

            # Keep only recent trades in main file
            history = await self._load_history()
            cutoff_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=1)  # Keep current month only

            recent_history = {}
            for key, trade in history.items():
                trade_date = datetime.fromisoformat(trade.get('entry', {}).get('timestamp', ''))
                if trade_date >= cutoff_date:
                    recent_history[key] = trade

            await self._save_history(recent_history)

        except Exception as e:
            logger.error(f"Error rotating trade history: {e}")

    async def log_trade_entry(self, symbol: str, side: str, approach: str,
                            entry_price: Decimal, size: Decimal,
                            order_type: str = "Market", chat_id: str = None,
                            leverage: int = None, risk_percentage: Decimal = None) -> str:
        """Log new trade entry"""
        try:
            history = await self._load_history()
            trade_key = self._get_trade_key(symbol, side, approach, chat_id)

            trade_data = {
                "symbol": symbol,
                "side": side,
                "approach": approach,
                "chat_id": chat_id,
                "entry": {
                    "price": str(entry_price),
                    "size": str(size),
                    "timestamp": datetime.utcnow().isoformat(),
                    "order_type": order_type,
                    "leverage": leverage,
                    "risk_percentage": str(risk_percentage) if risk_percentage else None
                },
                "tp_orders": [],
                "sl_order": {},
                "fills": [],
                "merges": [],
                "rebalances": [],
                "status": "active"
            }

            history[trade_key] = trade_data
            await self._save_history(history)

            logger.info(f"Logged trade entry: {trade_key}")
            return trade_key

        except Exception as e:
            logger.error(f"Error logging trade entry: {e}")
            return None

    async def log_tp_orders(self, trade_key: str, tp_orders: List[Dict]):
        """Log TP orders for a trade"""
        try:
            history = await self._load_history()

            if trade_key not in history:
                # Find by symbol/side/approach if exact key not found
                trade_key = await self._find_recent_trade(
                    history,
                    tp_orders[0].get('symbol') if tp_orders else None,
                    tp_orders[0].get('side') if tp_orders else None
                )

            if trade_key and trade_key in history:
                tp_data = []
                for i, order in enumerate(tp_orders):
                    tp_data.append({
                        "level": i + 1,
                        "price": str(order.get('price', 0)),
                        "quantity": str(order.get('qty', 0)),
                        "percentage": order.get('percentage', 0),
                        "order_id": order.get('orderId', ''),
                        "order_link_id": order.get('orderLinkId', ''),
                        "status": "pending"
                    })

                history[trade_key]["tp_orders"] = tp_data
                await self._save_history(history)
                logger.info(f"Logged {len(tp_orders)} TP orders for {trade_key}")

        except Exception as e:
            logger.error(f"Error logging TP orders: {e}")

    async def log_sl_order(self, trade_key: str, sl_order: Dict):
        """Log SL order for a trade"""
        try:
            history = await self._load_history()

            if trade_key not in history:
                trade_key = await self._find_recent_trade(
                    history,
                    sl_order.get('symbol'),
                    sl_order.get('side')
                )

            if trade_key and trade_key in history:
                sl_data = {
                    "price": str(sl_order.get('triggerPrice', 0)),
                    "quantity": str(sl_order.get('qty', 0)),
                    "percentage": 100,
                    "order_id": sl_order.get('orderId', ''),
                    "order_link_id": sl_order.get('orderLinkId', ''),
                    "status": "pending"
                }

                history[trade_key]["sl_order"] = sl_data
                await self._save_history(history)
                logger.info(f"Logged SL order for {trade_key}")

        except Exception as e:
            logger.error(f"Error logging SL order: {e}")

    async def log_order_fill(self, symbol: str, side: str, order_type: str,
                           fill_price: Decimal, fill_qty: Decimal,
                           order_id: str = None):
        """Log order fill"""
        try:
            history = await self._load_history()

            # Find active trade for this symbol/side
            trade_key = await self._find_active_trade(history, symbol, side)

            if trade_key:
                fill_data = {
                    "type": order_type,  # "TP", "SL", "Manual"
                    "price": str(fill_price),
                    "quantity": str(fill_qty),
                    "timestamp": datetime.utcnow().isoformat(),
                    "order_id": order_id
                }

                history[trade_key]["fills"].append(fill_data)

                # Update order status
                if order_type == "TP":
                    for tp in history[trade_key]["tp_orders"]:
                        if tp.get("order_id") == order_id:
                            tp["status"] = "filled"
                            break
                elif order_type == "SL":
                    if history[trade_key]["sl_order"].get("order_id") == order_id:
                        history[trade_key]["sl_order"]["status"] = "filled"
                        history[trade_key]["status"] = "closed"

                # Check if position is fully closed
                total_filled = sum(Decimal(fill["quantity"]) for fill in history[trade_key]["fills"])
                position_size = Decimal(history[trade_key]["entry"]["size"])
                if total_filled >= position_size:
                    history[trade_key]["status"] = "closed"

                await self._save_history(history)
                logger.info(f"Logged {order_type} fill for {trade_key}")

        except Exception as e:
            logger.error(f"Error logging order fill: {e}")

    async def log_position_merge(self, symbol: str, side: str, approach: str,
                               old_sizes: List[Decimal], new_size: Decimal,
                               new_avg_price: Decimal):
        """Log position merge operation"""
        try:
            history = await self._load_history()

            # Find trades being merged
            trades_to_merge = []
            for key, trade in history.items():
                if (trade["symbol"] == symbol and
                    trade["side"] == side and
                    trade["approach"] == approach and
                    trade["status"] == "active"):
                    trades_to_merge.append(key)

            if len(trades_to_merge) >= 2:
                # Use the oldest trade as the primary
                primary_key = sorted(trades_to_merge)[0]

                merge_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "old_sizes": [str(s) for s in old_sizes],
                    "new_size": str(new_size),
                    "new_avg_price": str(new_avg_price),
                    "merged_trades": trades_to_merge[1:]  # Exclude primary
                }

                history[primary_key]["merges"].append(merge_data)
                history[primary_key]["entry"]["size"] = str(new_size)
                history[primary_key]["entry"]["price"] = str(new_avg_price)

                # Mark merged trades as merged
                for key in trades_to_merge[1:]:
                    history[key]["status"] = "merged"
                    history[key]["merged_into"] = primary_key

                await self._save_history(history)
                logger.info(f"Logged merge of {len(trades_to_merge)} trades into {primary_key}")

        except Exception as e:
            logger.error(f"Error logging position merge: {e}")

    async def log_rebalance(self, symbol: str, side: str, approach: str,
                          orders_cancelled: int, orders_created: int,
                          trigger_type: str, details: Dict = None):
        """Log rebalancing operation"""
        try:
            history = await self._load_history()

            # Find active trade
            trade_key = await self._find_active_trade(history, symbol, side, approach)

            if trade_key:
                rebalance_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "trigger_type": trigger_type,  # "new_position", "merge", "orders_filled"
                    "orders_cancelled": orders_cancelled,
                    "orders_created": orders_created,
                    "details": details or {}
                }

                history[trade_key]["rebalances"].append(rebalance_data)
                await self._save_history(history)
                logger.info(f"Logged rebalance for {trade_key}")

        except Exception as e:
            logger.error(f"Error logging rebalance: {e}")

    async def get_trade_history(self, symbol: str = None, side: str = None,
                              approach: str = None, status: str = "active") -> List[Dict]:
        """Get trade history with filters"""
        try:
            history = await self._load_history()
            results = []

            for key, trade in history.items():
                if symbol and trade["symbol"] != symbol:
                    continue
                if side and trade["side"] != side:
                    continue
                if approach and trade["approach"] != approach:
                    continue
                if status and trade["status"] != status:
                    continue

                trade["trade_key"] = key
                results.append(trade)

            # Sort by entry timestamp (newest first)
            results.sort(
                key=lambda x: x["entry"]["timestamp"],
                reverse=True
            )

            return results

        except Exception as e:
            logger.error(f"Error getting trade history: {e}")
            return []

    async def get_original_trigger_prices(self, symbol: str, side: str) -> Optional[Dict]:
        """Get original trigger prices for a position"""
        try:
            trades = await self.get_trade_history(symbol, side, status="active")

            if trades:
                latest_trade = trades[0]
                return {
                    "entry_price": latest_trade["entry"]["price"],
                    "tp_prices": [tp["price"] for tp in latest_trade["tp_orders"]],
                    "sl_price": latest_trade["sl_order"].get("price"),
                    "approach": latest_trade["approach"],
                    "trade_key": latest_trade["trade_key"]
                }

            return None

        except Exception as e:
            logger.error(f"Error getting original trigger prices: {e}")
            return None

    async def _find_recent_trade(self, history: Dict, symbol: str, side: str) -> Optional[str]:
        """Find most recent trade for symbol/side"""
        matching_trades = []

        for key, trade in history.items():
            if (trade["symbol"] == symbol and
                trade["side"] == side and
                trade["status"] == "active"):
                matching_trades.append((key, trade["entry"]["timestamp"]))

        if matching_trades:
            # Return most recent
            matching_trades.sort(key=lambda x: x[1], reverse=True)
            return matching_trades[0][0]

        return None

    async def _find_active_trade(self, history: Dict, symbol: str, side: str,
                               approach: str = None) -> Optional[str]:
        """Find active trade matching criteria"""
        for key, trade in history.items():
            if (trade["symbol"] == symbol and
                trade["side"] == side and
                trade["status"] == "active"):
                if approach is None or trade["approach"] == approach:
                    return key
        return None

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
            else:
                logger.warning(f"No active trade found for {symbol} {side} to log manual close")

        except Exception as e:
            logger.error(f"Error logging manual close: {e}")


# Global trade logger instance
trade_logger = TradeLogger()


# Convenience functions
async def log_trade_entry(*args, **kwargs):
    """Log new trade entry"""
    return await trade_logger.log_trade_entry(*args, **kwargs)

async def log_tp_orders(*args, **kwargs):
    """Log TP orders"""
    return await trade_logger.log_tp_orders(*args, **kwargs)

async def log_sl_order(*args, **kwargs):
    """Log SL order"""
    return await trade_logger.log_sl_order(*args, **kwargs)

async def log_order_fill(*args, **kwargs):
    """Log order fill"""
    return await trade_logger.log_order_fill(*args, **kwargs)

async def log_position_merge(*args, **kwargs):
    """Log position merge"""
    return await trade_logger.log_position_merge(*args, **kwargs)

async def log_rebalance(*args, **kwargs):
    """Log rebalancing operation"""
    return await trade_logger.log_rebalance(*args, **kwargs)

async def get_trade_history(*args, **kwargs):
    """Get trade history"""
    return await trade_logger.get_trade_history(*args, **kwargs)

async def get_original_trigger_prices(*args, **kwargs):
    """Get original trigger prices"""
    return await trade_logger.get_original_trigger_prices(*args, **kwargs)