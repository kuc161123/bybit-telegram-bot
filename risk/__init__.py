#!/usr/bin/env python3
"""
Risk management package for the trading bot.

This package provides:
- Position size calculations
- Risk/reward ratio analysis
- AI-powered risk assessment
- Risk metrics and scoring
"""

from .calculations import (
    calculate_risk_reward_ratio,
    calculate_order_qty_for_margin_and_leverage,
    calculate_position_risk,
    calculate_required_margin,
    calculate_liquidation_price,
    calculate_position_pnl
)

from .assessment import (
    calculate_ai_risk_score,
    get_ai_risk_assessment
)

__all__ = [
    # Calculations
    'calculate_risk_reward_ratio',
    'calculate_order_qty_for_margin_and_leverage', 
    'calculate_position_risk',
    'calculate_required_margin',
    'calculate_liquidation_price',
    'calculate_position_pnl',
    
    # AI Assessment
    'calculate_ai_risk_score',
    'get_ai_risk_assessment'
]