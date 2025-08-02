"""Execution package for the trading bot."""

from .trader import execute_trade_logic
from .monitor import (
    start_position_monitoring,
    start_mirror_position_monitoring,
    stop_position_monitoring,
    update_performance_stats_on_close
)

__all__ = [
    'execute_trade_logic',
    'start_position_monitoring',
    'start_mirror_position_monitoring',
    'stop_position_monitoring',
    'update_performance_stats_on_close'
]