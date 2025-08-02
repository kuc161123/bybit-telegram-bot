#!/usr/bin/env python3
"""
Smart Leverage Calculator for 2% Risk Management
Calculates recommended leverage to limit maximum loss to 2% of total account balance
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple
from utils.cache import get_usdt_wallet_balance_cached

logger = logging.getLogger(__name__)

async def calculate_2_percent_risk_leverage(
    entry_price: Decimal,
    sl_price: Decimal, 
    margin_amount: Decimal,
    max_leverage: int = 100
) -> Tuple[Optional[int], str]:
    """
    Calculate recommended leverage for 2% account risk
    
    Args:
        entry_price: Entry price for the trade
        sl_price: Stop loss price
        margin_amount: Margin allocated for the trade
        max_leverage: Maximum allowed leverage for the symbol
        
    Returns:
        Tuple of (recommended_leverage, explanation_text)
        If calculation fails, returns (None, error_explanation)
    """
    try:
        # Input validation
        if not all([entry_price > 0, margin_amount > 0]):
            return None, "Invalid entry price or margin amount"
            
        if entry_price == sl_price:
            return None, "Entry and stop loss prices cannot be the same"
        
        # Get total account balance
        try:
            total_balance, available_balance = await get_usdt_wallet_balance_cached()
            if total_balance <= 0:
                return None, "Unable to fetch account balance"
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return None, "Account balance unavailable"
        
        # Calculate target loss (2% of total balance)
        target_loss = total_balance * Decimal("0.02")
        
        # Calculate price distance (absolute difference)
        price_distance = abs(entry_price - sl_price)
        
        # Calculate position size needed for target loss
        # Target Loss = Position Size × Price Distance
        # Position Size = Target Loss / Price Distance
        required_position_size = target_loss / price_distance
        
        # Calculate leverage needed for this position size
        # Position Size = (Margin × Leverage) / Entry Price
        # Leverage = (Position Size × Entry Price) / Margin
        required_leverage = (required_position_size * entry_price) / margin_amount
        
        # Round to nearest integer and ensure minimum of 1x
        recommended_leverage = max(1, round(float(required_leverage)))
        
        # Cap at maximum allowed leverage
        if recommended_leverage > max_leverage:
            recommended_leverage = max_leverage
            # Calculate actual risk percentage at max leverage
            actual_position_size = (margin_amount * Decimal(str(max_leverage))) / entry_price
            actual_loss = actual_position_size * price_distance
            actual_risk_percent = (actual_loss / total_balance) * 100
            
            explanation = f"Capped at {max_leverage}x (max allowed) - Risk: {actual_risk_percent:.1f}%"
        else:
            explanation = f"Limits loss to 2% of account (${target_loss:.2f})"
        
        # Additional validation - ensure recommended leverage makes sense
        if recommended_leverage < 1:
            return None, "Calculated leverage too low"
            
        logger.info(f"💡 Leverage calculation successful: {recommended_leverage}x for 2% risk")
        logger.debug(f"   Entry: ${entry_price}, SL: ${sl_price}, Margin: ${margin_amount}")
        logger.debug(f"   Account Balance: ${total_balance}, Target Loss: ${target_loss}")
        logger.debug(f"   Price Distance: ${price_distance}, Required Position: {required_position_size}")
        
        return recommended_leverage, explanation
        
    except (InvalidOperation, ZeroDivisionError, ValueError) as e:
        logger.error(f"Mathematical error in leverage calculation: {e}")
        return None, "Calculation error"
    except Exception as e:
        logger.error(f"Unexpected error in leverage calculation: {e}")
        return None, "Calculation failed"

def calculate_risk_percentage(
    entry_price: Decimal,
    sl_price: Decimal,
    margin_amount: Decimal,
    leverage: int,
    total_balance: Decimal
) -> float:
    """
    Calculate the risk percentage for given parameters
    
    Args:
        entry_price: Entry price for the trade
        sl_price: Stop loss price  
        margin_amount: Margin allocated for the trade
        leverage: Leverage to use
        total_balance: Total account balance
        
    Returns:
        Risk percentage (0-100)
    """
    try:
        # Calculate position size
        position_size = (margin_amount * Decimal(str(leverage))) / entry_price
        
        # Calculate potential loss
        price_distance = abs(entry_price - sl_price)
        potential_loss = position_size * price_distance
        
        # Calculate risk percentage
        risk_percentage = float((potential_loss / total_balance) * 100)
        
        return risk_percentage
        
    except Exception as e:
        logger.error(f"Error calculating risk percentage: {e}")
        return 0.0

async def calculate_2_percent_risk_margin(
    entry_price: Decimal,
    sl_price: Decimal, 
    leverage: int
) -> Tuple[Optional[float], str]:
    """
    Calculate recommended margin percentage for 2% account risk
    
    Args:
        entry_price: Entry price for the trade
        sl_price: Stop loss price
        leverage: Selected leverage
        
    Returns:
        Tuple of (recommended_margin_percent, explanation_text)
        If calculation fails, returns (None, error_explanation)
    """
    try:
        # Input validation
        if not all([entry_price > 0, leverage > 0]):
            return None, "Invalid entry price or leverage"
            
        if entry_price == sl_price:
            return None, "Entry and stop loss prices cannot be the same"
        
        # Get total account balance
        try:
            total_balance, available_balance = await get_usdt_wallet_balance_cached()
            if total_balance <= 0:
                return None, "Unable to fetch account balance"
        except Exception as e:
            logger.error(f"Error fetching account balance: {e}")
            return None, "Account balance unavailable"
        
        # Calculate target loss (2% of total balance)
        target_loss = total_balance * Decimal("0.02")
        
        # Calculate price distance (absolute difference)
        price_distance = abs(entry_price - sl_price)
        
        # Calculate required margin percentage for 2% risk
        # Formula: target_loss = (margin_amount * leverage / entry_price) * price_distance
        # Solving for margin_amount: margin_amount = (target_loss * entry_price) / (leverage * price_distance)
        # As percentage: margin_percent = (margin_amount / total_balance) * 100
        
        required_margin_usdt = (target_loss * entry_price) / (Decimal(str(leverage)) * price_distance)
        required_margin_percent = (required_margin_usdt / total_balance) * 100
        
        # Convert to float and round to 1 decimal place
        margin_percent = round(float(required_margin_percent), 1)
        
        # Validation - ensure reasonable range
        if margin_percent < 0.1:
            return None, "Calculated margin too small"
        if margin_percent > 50:
            return None, "Calculated margin too large (>50%)"
            
        explanation = f"Limits loss to 2% of account (${target_loss:.2f})"
        
        logger.info(f"💡 Margin calculation successful: {margin_percent}% for 2% risk")
        logger.debug(f"   Entry: ${entry_price}, SL: ${sl_price}, Leverage: {leverage}x")
        logger.debug(f"   Account Balance: ${total_balance}, Target Loss: ${target_loss}")
        logger.debug(f"   Price Distance: ${price_distance}, Required Margin: ${required_margin_usdt}")
        
        return margin_percent, explanation
        
    except (InvalidOperation, ZeroDivisionError, ValueError) as e:
        logger.error(f"Mathematical error in margin calculation: {e}")
        return None, "Calculation error"
    except Exception as e:
        logger.error(f"Unexpected error in margin calculation: {e}")
        return None, "Calculation failed"

def validate_leverage_inputs(
    entry_price: Decimal,
    sl_price: Decimal,
    margin_amount: Decimal
) -> Tuple[bool, str]:
    """
    Validate inputs for leverage calculation
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        if entry_price <= 0:
            return False, "Entry price must be positive"
            
        if margin_amount <= 0:
            return False, "Margin amount must be positive"
            
        if entry_price == sl_price:
            return False, "Entry and stop loss prices cannot be the same"
            
        # Check if stop loss is reasonable (not more than 30% away for safety)
        price_distance_percent = abs(entry_price - sl_price) / entry_price * 100
        if price_distance_percent > 30:
            return False, f"Stop loss too far from entry ({price_distance_percent:.1f}%)"
            
        return True, "Valid"
        
    except Exception as e:
        return False, f"Validation error: {e}"