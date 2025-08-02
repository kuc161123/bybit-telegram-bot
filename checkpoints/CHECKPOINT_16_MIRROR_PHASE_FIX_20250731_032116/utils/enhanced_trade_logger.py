#!/usr/bin/env python3
"""
Enhanced Trade Logger - Comprehensive logging system that captures EVERYTHING
Tracks all trade details, order modifications, cancellations, and state changes
"""

import json
import os
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal
import asyncio
from pathlib import Path
import shutil
import uuid

logger = logging.getLogger(__name__)

# Trade history file configuration
TRADE_HISTORY_DIR = "data"
TRADE_HISTORY_FILE = "enhanced_trade_history.json"
TRADE_HISTORY_BACKUP = "enhanced_trade_history_backup.json"
MAX_HISTORY_SIZE_MB = 100  # Increased size for comprehensive logging
TRADE_ARCHIVE_DIR = "data/trade_archives"

class EnhancedTradeLogger:
    """Comprehensive trade logging system that captures everything"""

    def __init__(self):
        self.history_file = os.path.join(TRADE_HISTORY_DIR, TRADE_HISTORY_FILE)
        self.backup_file = os.path.join(TRADE_HISTORY_DIR, TRADE_HISTORY_BACKUP)
        self.archive_dir = TRADE_ARCHIVE_DIR
        self._ensure_directories()
        self._lock = asyncio.Lock()

    def _ensure_directories(self):
        """Ensure all required directories exist"""
        Path(TRADE_HISTORY_DIR).mkdir(parents=True, exist_ok=True)
        Path(self.archive_dir).mkdir(parents=True, exist_ok=True)

    def _generate_trade_id(self) -> str:
        """Generate unique trade ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"trade_{timestamp}_{unique_id}"

    async def _load_history(self) -> Dict:
        """Load trade history from file"""
        if not os.path.exists(self.history_file):
            return {"trades": {}, "metadata": {"version": "2.0", "created": datetime.now(timezone.utc).isoformat()}}

        try:
            async with self._lock:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading trade history: {e}")
            return {"trades": {}, "metadata": {"version": "2.0", "created": datetime.now(timezone.utc).isoformat()}}

    async def _save_history(self, history: Dict):
        """Save trade history to file with rotation check"""
        try:
            async with self._lock:
                # Ensure metadata exists
                if "metadata" not in history:
                    history["metadata"] = {"version": "2.0", "created": datetime.now(timezone.utc).isoformat()}

                # Update metadata
                history["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
                history["metadata"]["total_trades"] = len(history.get("trades", {}))

                # Check file size and rotate if needed
                if os.path.exists(self.history_file):
                    size_mb = os.path.getsize(self.history_file) / (1024 * 1024)
                    if size_mb > MAX_HISTORY_SIZE_MB:
                        await self._rotate_history()

                # Create backup before saving
                if os.path.exists(self.history_file):
                    shutil.copy2(self.history_file, self.backup_file)

                # Save current history
                with open(self.history_file, 'w') as f:
                    json.dump(history, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Error saving trade history: {e}")

    async def _rotate_history(self):
        """Rotate history file when it gets too large"""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            archive_file = os.path.join(self.archive_dir, f"trade_history_{timestamp}.json")
            shutil.move(self.history_file, archive_file)
            logger.info(f"Rotated trade history to {archive_file}")

            # Compress old archive files
            self._compress_old_archives()

        except Exception as e:
            logger.error(f"Error rotating trade history: {e}")

    def _compress_old_archives(self):
        """Compress archive files older than 7 days"""
        import gzip
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=7)
        for file in Path(self.archive_dir).glob("trade_history_*.json"):
            if file.stat().st_mtime < cutoff.timestamp():
                try:
                    with open(file, 'rb') as f_in:
                        with gzip.open(f"{file}.gz", 'wb') as f_out:
                            f_out.writelines(f_in)
                    file.unlink()  # Remove original file
                    logger.info(f"Compressed archive: {file}")
                except Exception as e:
                    logger.error(f"Error compressing {file}: {e}")

    async def log_trade_entry(self,
                            symbol: str,
                            side: str,
                            approach: str,
                            entry_price: Union[Decimal, float, str],
                            size: Union[Decimal, float, str],
                            order_type: str = "Market",
                            chat_id: Optional[str] = None,
                            leverage: Optional[int] = None,
                            risk_percentage: Optional[Union[Decimal, float]] = None,
                            account_balance: Optional[Union[Decimal, float]] = None,
                            stop_loss: Optional[Union[Decimal, float]] = None,
                            take_profits: Optional[List[Dict]] = None,
                            limit_orders: Optional[List[Dict]] = None,
                            user_notes: Optional[str] = None,
                            **kwargs) -> str:
        """Log comprehensive trade entry with all details"""
        try:
            history = await self._load_history()
            trade_id = self._generate_trade_id()

            # Comprehensive trade data
            trade_data = {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side,
                "approach": approach,
                "chat_id": chat_id,
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),

                # Entry details
                "entry": {
                    "price": str(entry_price),
                    "size": str(size),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "order_type": order_type,
                    "leverage": leverage,
                    "risk_percentage": str(risk_percentage) if risk_percentage else None,
                    "account_balance": str(account_balance) if account_balance else None,
                    "position_value": str(Decimal(str(entry_price)) * Decimal(str(size))),
                    "user_notes": user_notes
                },

                # Risk management
                "risk_management": {
                    "stop_loss": str(stop_loss.get('price', stop_loss)) if isinstance(stop_loss, dict) else str(stop_loss) if stop_loss else None,
                    "risk_amount": None,
                    "risk_reward_ratio": None,
                    "max_loss": None
                },

                # Orders
                "limit_orders": limit_orders or [],
                "tp_orders": take_profits or [],
                "sl_order": stop_loss if isinstance(stop_loss, dict) else {"price": str(stop_loss)} if stop_loss else {},

                # Execution tracking
                "fills": [],
                "partial_fills": [],
                "order_modifications": [],
                "order_cancellations": [],

                # Position changes
                "merges": [],
                "splits": [],
                "rebalances": [],

                # Performance metrics
                "performance": {
                    "realized_pnl": "0",
                    "unrealized_pnl": "0",
                    "fees_paid": "0",
                    "max_profit": "0",
                    "max_drawdown": "0",
                    "duration_seconds": 0
                },

                # Additional metadata
                "metadata": kwargs
            }

            # Calculate risk metrics if stop loss provided
            if stop_loss and entry_price:
                entry_price_dec = Decimal(str(entry_price))
                # Handle stop_loss as either a dict or a price value
                if isinstance(stop_loss, dict):
                    stop_loss_price = stop_loss.get('price', stop_loss.get('trigger_price', 0))
                else:
                    stop_loss_price = stop_loss
                stop_loss_dec = Decimal(str(stop_loss_price))
                size_dec = Decimal(str(size))

                if side == "Buy":
                    risk_per_unit = entry_price_dec - stop_loss_dec
                else:
                    risk_per_unit = stop_loss_dec - entry_price_dec

                risk_amount = risk_per_unit * size_dec
                trade_data["risk_management"]["risk_amount"] = str(risk_amount)
                trade_data["risk_management"]["max_loss"] = str(risk_amount)

            history["trades"][trade_id] = trade_data
            await self._save_history(history)

            logger.info(f"Logged comprehensive trade entry: {trade_id} for {symbol}")
            return trade_id

        except Exception as e:
            logger.error(f"Error logging trade entry: {e}", exc_info=True)
            return None

    async def log_order_event(self,
                            trade_id: str,
                            event_type: str,  # "placed", "modified", "cancelled", "filled", "rejected"
                            order_type: str,  # "limit", "tp", "sl", "market"
                            order_id: str,
                            details: Dict[str, Any]):
        """Log any order-related event"""
        try:
            history = await self._load_history()

            if trade_id not in history.get("trades", {}):
                logger.warning(f"Trade {trade_id} not found for order event")
                return

            event_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "order_type": order_type,
                "order_id": order_id,
                "details": details
            }

            # Add to appropriate list based on event type
            if event_type == "modified":
                history["trades"][trade_id]["order_modifications"].append(event_data)
            elif event_type == "cancelled":
                history["trades"][trade_id]["order_cancellations"].append(event_data)
            elif event_type == "filled":
                history["trades"][trade_id]["fills"].append(event_data)
            elif event_type == "partial_fill":
                history["trades"][trade_id]["partial_fills"].append(event_data)

            # Update timestamp
            history["trades"][trade_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

            await self._save_history(history)
            logger.info(f"Logged order event: {event_type} for {order_type} order in trade {trade_id}")

        except Exception as e:
            logger.error(f"Error logging order event: {e}", exc_info=True)

    async def log_position_update(self,
                                trade_id: str,
                                update_type: str,  # "merge", "split", "rebalance", "close"
                                details: Dict[str, Any]):
        """Log position updates"""
        try:
            history = await self._load_history()

            if trade_id not in history.get("trades", {}):
                logger.warning(f"Trade {trade_id} not found for position update")
                return

            update_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": update_type,
                "details": details
            }

            if update_type == "merge":
                history["trades"][trade_id]["merges"].append(update_data)
            elif update_type == "split":
                history["trades"][trade_id]["splits"].append(update_data)
            elif update_type == "rebalance":
                history["trades"][trade_id]["rebalances"].append(update_data)
            elif update_type == "close":
                history["trades"][trade_id]["status"] = "closed"
                history["trades"][trade_id]["closed_at"] = datetime.now(timezone.utc).isoformat()

                # Calculate final performance metrics
                if "performance" in history["trades"][trade_id]:
                    # Calculate duration
                    created = datetime.fromisoformat(history["trades"][trade_id]["created_at"].replace('Z', '+00:00'))
                    closed = datetime.now(timezone.utc)
                    duration = (closed - created).total_seconds()
                    history["trades"][trade_id]["performance"]["duration_seconds"] = duration

            history["trades"][trade_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

            await self._save_history(history)
            logger.info(f"Logged position update: {update_type} for trade {trade_id}")

        except Exception as e:
            logger.error(f"Error logging position update: {e}", exc_info=True)

    async def update_performance_metrics(self,
                                       trade_id: str,
                                       realized_pnl: Optional[Union[Decimal, float]] = None,
                                       unrealized_pnl: Optional[Union[Decimal, float]] = None,
                                       fees_paid: Optional[Union[Decimal, float]] = None):
        """Update performance metrics for a trade"""
        try:
            history = await self._load_history()

            if trade_id not in history.get("trades", {}):
                logger.warning(f"Trade {trade_id} not found for performance update")
                return

            perf = history["trades"][trade_id]["performance"]

            if realized_pnl is not None:
                perf["realized_pnl"] = str(realized_pnl)
            if unrealized_pnl is not None:
                perf["unrealized_pnl"] = str(unrealized_pnl)
                # Track max profit/drawdown
                if Decimal(str(unrealized_pnl)) > Decimal(perf.get("max_profit", "0")):
                    perf["max_profit"] = str(unrealized_pnl)
                if Decimal(str(unrealized_pnl)) < Decimal(perf.get("max_drawdown", "0")):
                    perf["max_drawdown"] = str(unrealized_pnl)
            if fees_paid is not None:
                current_fees = Decimal(perf.get("fees_paid", "0"))
                perf["fees_paid"] = str(current_fees + Decimal(str(fees_paid)))

            history["trades"][trade_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

            await self._save_history(history)

        except Exception as e:
            logger.error(f"Error updating performance metrics: {e}", exc_info=True)

    async def get_active_trades(self) -> List[Dict]:
        """Get all active trades"""
        try:
            history = await self._load_history()
            active_trades = []

            for trade_id, trade_data in history.get("trades", {}).items():
                if trade_data.get("status") == "active":
                    active_trades.append(trade_data)

            return active_trades

        except Exception as e:
            logger.error(f"Error getting active trades: {e}", exc_info=True)
            return []

    async def get_trade_by_symbol(self, symbol: str, side: str = None) -> Optional[Dict]:
        """Get most recent active trade for a symbol"""
        try:
            history = await self._load_history()

            # Find most recent active trade for symbol
            latest_trade = None
            latest_time = None

            for trade_id, trade_data in history.get("trades", {}).items():
                if (trade_data.get("symbol") == symbol and
                    trade_data.get("status") == "active" and
                    (side is None or trade_data.get("side") == side)):

                    trade_time = datetime.fromisoformat(trade_data["created_at"].replace('Z', '+00:00'))
                    if latest_time is None or trade_time > latest_time:
                        latest_time = trade_time
                        latest_trade = trade_data

            return latest_trade

        except Exception as e:
            logger.error(f"Error getting trade by symbol: {e}", exc_info=True)
            return None

    async def export_trade_report(self,
                                start_date: Optional[datetime] = None,
                                end_date: Optional[datetime] = None,
                                output_file: Optional[str] = None) -> str:
        """Export comprehensive trade report"""
        try:
            history = await self._load_history()

            # Filter trades by date if specified
            trades_to_export = {}
            for trade_id, trade_data in history.get("trades", {}).items():
                trade_time = datetime.fromisoformat(trade_data["created_at"].replace('Z', '+00:00'))

                if start_date and trade_time < start_date:
                    continue
                if end_date and trade_time > end_date:
                    continue

                trades_to_export[trade_id] = trade_data

            # Create report
            report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "period": {
                    "start": start_date.isoformat() if start_date else "all_time",
                    "end": end_date.isoformat() if end_date else "current"
                },
                "summary": {
                    "total_trades": len(trades_to_export),
                    "active_trades": sum(1 for t in trades_to_export.values() if t["status"] == "active"),
                    "closed_trades": sum(1 for t in trades_to_export.values() if t["status"] == "closed"),
                    "total_realized_pnl": "0",
                    "total_fees": "0"
                },
                "trades": trades_to_export
            }

            # Calculate totals
            total_pnl = Decimal("0")
            total_fees = Decimal("0")

            for trade in trades_to_export.values():
                if trade["status"] == "closed":
                    total_pnl += Decimal(trade["performance"].get("realized_pnl", "0"))
                    total_fees += Decimal(trade["performance"].get("fees_paid", "0"))

            report["summary"]["total_realized_pnl"] = str(total_pnl)
            report["summary"]["total_fees"] = str(total_fees)

            # Save report
            if not output_file:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(TRADE_HISTORY_DIR, f"trade_report_{timestamp}.json")

            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Exported trade report to {output_file}")
            return output_file

        except Exception as e:
            logger.error(f"Error exporting trade report: {e}", exc_info=True)
            return None

# Global instance
enhanced_trade_logger = EnhancedTradeLogger()

# Convenience functions
async def log_trade_entry(**kwargs) -> str:
    """Log a new trade entry with all details"""
    return await enhanced_trade_logger.log_trade_entry(**kwargs)

async def log_order_event(trade_id: str, event_type: str, order_type: str, order_id: str, details: Dict):
    """Log an order event"""
    return await enhanced_trade_logger.log_order_event(trade_id, event_type, order_type, order_id, details)

async def log_position_update(trade_id: str, update_type: str, details: Dict):
    """Log a position update"""
    return await enhanced_trade_logger.log_position_update(trade_id, update_type, details)

async def update_performance(trade_id: str, **kwargs):
    """Update performance metrics"""
    return await enhanced_trade_logger.update_performance_metrics(trade_id, **kwargs)

async def get_active_trades() -> List[Dict]:
    """Get all active trades"""
    return await enhanced_trade_logger.get_active_trades()

async def export_report(start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> str:
    """Export trade report"""
    return await enhanced_trade_logger.export_trade_report(start_date, end_date)