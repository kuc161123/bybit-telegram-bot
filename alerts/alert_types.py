#!/usr/bin/env python3
"""
Alert type definitions and configurations
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime

class AlertType(Enum):
    """Types of alerts available"""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_CROSS = "price_cross"
    PRICE_CHANGE_PERCENT = "price_change_percent"
    
    POSITION_PROFIT_AMOUNT = "position_profit_amount"
    POSITION_PROFIT_PERCENT = "position_profit_percent"
    POSITION_LOSS_AMOUNT = "position_loss_amount"
    POSITION_LOSS_PERCENT = "position_loss_percent"
    POSITION_NEAR_TP = "position_near_tp"
    POSITION_NEAR_SL = "position_near_sl"
    POSITION_BREAKEVEN = "position_breakeven"
    
    HIGH_LEVERAGE = "high_leverage"
    LARGE_POSITION = "large_position"
    ACCOUNT_DRAWDOWN = "account_drawdown"
    CORRELATED_POSITIONS = "correlated_positions"
    
    VOLATILITY_SPIKE = "volatility_spike"
    VOLUME_SPIKE = "volume_spike"
    FUNDING_RATE = "funding_rate"
    
    DAILY_SUMMARY = "daily_summary"
    
    # Trade execution alerts
    TRADE_TP_HIT = "trade_tp_hit"
    TRADE_SL_HIT = "trade_sl_hit"
    TRADE_LIMIT_FILLED = "trade_limit_filled"
    TRADE_TP1_EARLY_HIT = "trade_tp1_early_hit"
    TRADE_TP1_WITH_FILLS = "trade_tp1_with_fills"

class AlertPriority(Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

@dataclass
class Alert:
    """Alert configuration"""
    id: str
    type: AlertType
    chat_id: int
    symbol: Optional[str] = None
    condition_value: Optional[Decimal] = None
    condition_params: Optional[Dict[str, Any]] = None
    priority: AlertPriority = AlertPriority.MEDIUM
    created_at: datetime = None
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    enabled: bool = True
    cooldown_minutes: int = 30  # Minimum time between triggers
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.condition_params is None:
            self.condition_params = {}
    
    def should_trigger(self, current_time: datetime) -> bool:
        """Check if alert should trigger based on cooldown"""
        if not self.enabled:
            return False
        
        if self.expires_at and current_time > self.expires_at:
            return False
        
        if self.last_triggered:
            time_since_last = (current_time - self.last_triggered).total_seconds() / 60
            if time_since_last < self.cooldown_minutes:
                return False
        
        return True
    
    def mark_triggered(self):
        """Mark alert as triggered"""
        self.last_triggered = datetime.utcnow()
        self.trigger_count += 1

# Alert configurations
ALERT_CONFIGS = {
    AlertType.PRICE_ABOVE: {
        "name": "Price Above",
        "description": "Alert when price goes above target",
        "emoji": "📈",
        "requires_symbol": True,
        "requires_value": True,
        "priority": AlertPriority.MEDIUM
    },
    AlertType.PRICE_BELOW: {
        "name": "Price Below",
        "description": "Alert when price goes below target",
        "emoji": "📉",
        "requires_symbol": True,
        "requires_value": True,
        "priority": AlertPriority.MEDIUM
    },
    AlertType.PRICE_CHANGE_PERCENT: {
        "name": "Price Change %",
        "description": "Alert on percentage price change",
        "emoji": "📊",
        "requires_symbol": True,
        "requires_value": True,
        "priority": AlertPriority.MEDIUM
    },
    AlertType.POSITION_PROFIT_AMOUNT: {
        "name": "Position Profit $",
        "description": "Alert when position reaches profit target",
        "emoji": "💰",
        "requires_symbol": True,
        "requires_value": True,
        "priority": AlertPriority.HIGH
    },
    AlertType.POSITION_LOSS_AMOUNT: {
        "name": "Position Loss $",
        "description": "Alert when position reaches loss threshold",
        "emoji": "🔴",
        "requires_symbol": True,
        "requires_value": True,
        "priority": AlertPriority.HIGH
    },
    AlertType.HIGH_LEVERAGE: {
        "name": "High Leverage",
        "description": "Alert when using high leverage",
        "emoji": "⚠️",
        "requires_symbol": False,
        "requires_value": True,
        "priority": AlertPriority.URGENT
    },
    AlertType.DAILY_SUMMARY: {
        "name": "Daily Summary",
        "description": "Daily trading summary report",
        "emoji": "📊",
        "requires_symbol": False,
        "requires_value": False,
        "priority": AlertPriority.LOW
    },
    AlertType.TRADE_TP_HIT: {
        "name": "Take Profit Hit",
        "description": "Alert when take profit order is executed",
        "emoji": "🎯",
        "requires_symbol": True,
        "requires_value": False,
        "priority": AlertPriority.HIGH
    },
    AlertType.TRADE_SL_HIT: {
        "name": "Stop Loss Hit",
        "description": "Alert when stop loss order is executed",
        "emoji": "🛡️",
        "requires_symbol": True,
        "requires_value": False,
        "priority": AlertPriority.HIGH
    },
    AlertType.TRADE_LIMIT_FILLED: {
        "name": "Limit Order Filled",
        "description": "Alert when limit order is filled",
        "emoji": "📦",
        "requires_symbol": True,
        "requires_value": False,
        "priority": AlertPriority.MEDIUM
    },
    AlertType.TRADE_TP1_EARLY_HIT: {
        "name": "TP1 Early Hit",
        "description": "Alert when TP1 hits before any limits fill",
        "emoji": "🚨",
        "requires_symbol": True,
        "requires_value": False,
        "priority": AlertPriority.HIGH
    },
    AlertType.TRADE_TP1_WITH_FILLS: {
        "name": "TP1 Hit With Fills",
        "description": "Alert when TP1 hits after some limits filled",
        "emoji": "🎯",
        "requires_symbol": True,
        "requires_value": False,
        "priority": AlertPriority.HIGH
    }
}