#!/usr/bin/env python3
"""
Compact Analytics Dashboard - Legacy compatibility wrapper
This file now redirects to the new V2 dashboard generator
"""
import logging
from typing import Any

# Import the new V2 generator
from .generator_v2 import build_mobile_dashboard_text as build_mobile_dashboard_text_v2

logger = logging.getLogger(__name__)

# Redirect all calls to the new V2 generator
async def build_mobile_dashboard_text(chat_id: int, context: Any) -> str:
    """Legacy wrapper - redirects to V2 dashboard"""
    logger.debug("Legacy dashboard function called, redirecting to V2")
    return await build_mobile_dashboard_text_v2(chat_id, context)

# Legacy alias for compatibility
async def build_analytics_dashboard_text(chat_data: Any, bot_data: Any) -> str:
    """Legacy wrapper - redirects to V2 dashboard"""
    logger.debug("Legacy analytics dashboard function called, redirecting to V2")
    # Create a mock context object for V2
    class MockContext:
        def __init__(self, chat_data, bot_data):
            self.chat_data = chat_data if isinstance(chat_data, dict) else {}
            self.bot_data = bot_data if isinstance(bot_data, dict) else {}

    # Use a dummy chat_id
    chat_id = 0
    context = MockContext(chat_data, bot_data)

    return await build_mobile_dashboard_text_v2(chat_id, context)

# Legacy functions that may be imported by other modules
async def calculate_portfolio_metrics(positions=None, total_balance=None):
    """Legacy function for portfolio metrics calculation"""
    return {
        'total_value': 0,
        'risk_score': 0,
        'diversification': 0,
        'leverage_ratio': 0,
        'largest_position_pct': 0,
        'correlation_score': 0
    }

def calculate_sharpe_ratio(returns=None):
    """Legacy function for Sharpe ratio calculation"""
    return 0.0

def calculate_max_drawdown(equity_curve=None):
    """Legacy function for max drawdown calculation"""
    return 0.0

def generate_portfolio_heatmap(positions=None):
    """Legacy function for portfolio heatmap generation"""
    return "📊 Portfolio heatmap not available"

def format_dashboard_metrics(metrics):
    """Legacy function for formatting metrics"""
    return "No data available"

def calculate_correlation_matrix(positions=None):
    """Legacy function for correlation matrix calculation"""
    return {}

def calculate_risk_metrics(positions=None):
    """Legacy function for risk metrics calculation"""
    return {
        'var_95': 0,
        'expected_shortfall': 0,
        'beta': 0,
        'alpha': 0
    }

# Export for compatibility
__all__ = [
    'build_mobile_dashboard_text',
    'build_analytics_dashboard_text',
    'calculate_portfolio_metrics',
    'calculate_sharpe_ratio',
    'calculate_max_drawdown',
    'generate_portfolio_heatmap',
    'format_dashboard_metrics',
    'calculate_correlation_matrix',
    'calculate_risk_metrics'
]