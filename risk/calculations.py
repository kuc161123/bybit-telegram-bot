#!/usr/bin/env python3
"""
Risk and position size calculations with FIXED decimal handling.
FIXES: Improved validation, better error handling, correct TP/SL logic
ADDED: Helper functions for potential P&L calculations
"""
import logging
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

def safe_decimal(value) -> Decimal:
    """Safely convert value to Decimal"""
    try:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (ValueError, InvalidOperation, TypeError):
        logger.error(f"Could not convert {value} to Decimal")
        return Decimal("0")

def validate_trade_direction_and_prices(side: str, entry_price: Decimal, tp_price: Decimal, sl_price: Decimal) -> Tuple[bool, str]:
    """
    FIXED: Validate trade direction and price relationships
    
    Returns:
        tuple: (is_valid: bool, message: str)
    """
    try:
        entry_price = safe_decimal(entry_price)
        tp_price = safe_decimal(tp_price)
        sl_price = safe_decimal(sl_price)
        
        if entry_price <= 0 or tp_price <= 0 or sl_price <= 0:
            return False, "All prices must be greater than 0"
        
        if side.upper() in ["BUY", "LONG"]:
            # For BUY/LONG positions:
            # - TP should be ABOVE entry price (profit when price goes up)
            # - SL should be BELOW entry price (loss when price goes down)
            if tp_price <= entry_price:
                return False, f"BUY: Take Profit ({tp_price}) must be above Entry ({entry_price})"
            
            if sl_price >= entry_price:
                return False, f"BUY: Stop Loss ({sl_price}) must be below Entry ({entry_price})"
                
        elif side.upper() in ["SELL", "SHORT"]:
            # For SELL/SHORT positions:
            # - TP should be BELOW entry price (profit when price goes down)
            # - SL should be ABOVE entry price (loss when price goes up)
            if tp_price >= entry_price:
                return False, f"SELL: Take Profit ({tp_price}) must be below Entry ({entry_price})"
            
            if sl_price <= entry_price:
                return False, f"SELL: Stop Loss ({sl_price}) must be above Entry ({entry_price})"
        else:
            return False, f"Invalid side: {side}. Must be BUY/LONG or SELL/SHORT"
        
        return True, "Trade direction and prices are valid"
        
    except Exception as e:
        logger.error(f"Error validating trade direction: {e}")
        return False, f"Validation error: {e}"

def calculate_risk_reward_ratio(entry_price: Decimal, tp_price: Decimal, 
                               sl_price: Decimal, side: str) -> Dict:
    """
    FIXED: Calculate risk/reward ratio for a trade with proper validation.
    
    Args:
        entry_price: Entry price
        tp_price: Take profit price
        sl_price: Stop loss price
        side: "Buy" or "Sell"
    
    Returns:
        Dict with ratio and analysis
    """
    try:
        if not all([entry_price, tp_price, sl_price]):
            return {"error": "Missing required prices"}
        
        # Convert to Decimal if needed
        entry_price = safe_decimal(entry_price)
        tp_price = safe_decimal(tp_price)
        sl_price = safe_decimal(sl_price)
        
        # First validate the trade direction and prices
        is_valid, validation_msg = validate_trade_direction_and_prices(side, entry_price, tp_price, sl_price)
        if not is_valid:
            return {"error": validation_msg}
        
        # Calculate risk and reward distances (always positive)
        if side.upper() in ["BUY", "LONG"]:
            risk = entry_price - sl_price  # How much we lose if SL hits
            reward = tp_price - entry_price  # How much we gain if TP hits
        else:  # SELL/SHORT
            risk = sl_price - entry_price  # How much we lose if SL hits
            reward = entry_price - tp_price  # How much we gain if TP hits
        
        # Validate risk and reward (should be positive after validation above)
        if risk <= 0:
            return {"error": f"Invalid risk calculation: {risk}"}
        if reward <= 0:
            return {"error": f"Invalid reward calculation: {reward}"}
        
        # Calculate ratio
        ratio = float(reward / risk)
        
        # Determine rating
        if ratio >= 3:
            rating = "🟢 EXCELLENT"
            analysis = "Excellent risk/reward ratio"
        elif ratio >= 2:
            rating = "🟢 GOOD"
            analysis = "Good risk/reward ratio"
        elif ratio >= 1.5:
            rating = "🟡 ACCEPTABLE"
            analysis = "Acceptable risk/reward ratio"
        elif ratio >= 1:
            rating = "🟡 MARGINAL"
            analysis = "Marginal risk/reward ratio"
        else:
            rating = "🔴 POOR"
            analysis = "Poor risk/reward ratio - consider adjusting TP/SL"
        
        return {
            "ratio": f"1:{ratio:.2f}",
            "decimal_ratio": ratio,
            "risk": float(risk),
            "reward": float(reward),
            "risk_percent": float((risk / entry_price) * 100),
            "reward_percent": float((reward / entry_price) * 100),
            "rating": rating,
            "analysis": analysis,
            "valid": True
        }
        
    except Exception as e:
        logger.error(f"Error calculating R:R ratio: {e}")
        return {"error": str(e)}

async def calculate_order_qty_for_margin_and_leverage(symbol: str, margin_amount: Decimal, 
                                                     leverage: int, entry_price: Decimal) -> Dict:
    """
    FIXED: Calculate order quantity based on margin amount and leverage with enhanced validation.
    
    Args:
        symbol: Trading symbol
        margin_amount: USDT margin amount
        leverage: Trading leverage
        entry_price: Entry price for the position
    
    Returns:
        Dict with 'order_qty' or 'error'
    """
    try:
        # Convert to Decimal for precision with validation
        margin_amount = safe_decimal(margin_amount)
        leverage = safe_decimal(leverage)
        entry_price = safe_decimal(entry_price)
        
        logger.info(f"Calculating quantity: margin={margin_amount}, leverage={leverage}, entry={entry_price}")
        
        # Validate inputs
        if margin_amount <= 0:
            return {"error": "Margin amount must be greater than 0"}
        if leverage <= 0:
            return {"error": "Leverage must be greater than 0"}
        if leverage > 100:
            return {"error": "Leverage too high (max 100x)"}
        if entry_price <= 0:
            return {"error": "Entry price must be greater than 0"}
        
        # Basic calculation: Position Value = Margin * Leverage
        position_value = margin_amount * leverage
        logger.info(f"Position value: {position_value}")
        
        # Order Quantity = Position Value / Entry Price
        raw_order_qty = position_value / entry_price
        logger.info(f"Raw order quantity: {raw_order_qty}")
        
        # Validate that quantity is reasonable
        if raw_order_qty <= 0:
            return {"error": "Calculated quantity is zero or negative"}
        
        if raw_order_qty > Decimal("1000000"):
            return {"error": "Calculated quantity is unreasonably large"}
        
        # Get instrument info to check minimum order requirements
        from utils.cache import get_instrument_info_cached
        inst_info = await get_instrument_info_cached(symbol)
        
        if inst_info:
            # Get step sizes and minimums
            qty_step = safe_decimal(inst_info.get("lotSizeFilter", {}).get("qtyStep", "0.01"))
            min_qty = safe_decimal(inst_info.get("lotSizeFilter", {}).get("minOrderQty", "0"))
            max_qty = safe_decimal(inst_info.get("lotSizeFilter", {}).get("maxOrderQty", "1000000"))
            min_notional = safe_decimal(inst_info.get("lotSizeFilter", {}).get("minNotional", "0"))
            
            logger.info(f"Instrument limits: qtyStep={qty_step}, minQty={min_qty}, maxQty={max_qty}, minNotional={min_notional}")
            
            # Adjust quantity to step size
            from utils.helpers import value_adjusted_to_step
            order_qty = value_adjusted_to_step(raw_order_qty, qty_step)
            
            logger.info(f"Adjusted order quantity: {order_qty}")
            
            # Check minimum order quantity
            if order_qty < min_qty:
                return {
                    "error": f"Calculated quantity {order_qty:.8f} is below minimum {min_qty}"
                }
            
            # Check maximum order quantity
            if max_qty > 0 and order_qty > max_qty:
                return {
                    "error": f"Calculated quantity {order_qty:.8f} exceeds maximum {max_qty}"
                }
            
            # Check minimum notional value
            notional_value = order_qty * entry_price
            if min_notional > 0 and notional_value < min_notional:
                return {
                    "error": f"Order value {notional_value:.2f} USDT is below minimum {min_notional} USDT"
                }
            
            # Final safety checks
            if order_qty <= 0:
                return {"error": "Final calculated quantity is zero or negative"}
        
        else:
            # Fallback if no instrument info
            logger.warning(f"No instrument info for {symbol}, using basic rounding")
            order_qty = raw_order_qty.quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            
            # Basic validation without instrument info
            if order_qty <= 0:
                return {"error": "Calculated quantity is zero after rounding"}
        
        logger.info(f"Final order quantity: {order_qty}")
        
        return {
            "order_qty": order_qty,
            "position_value": float(position_value),
            "notional_value": float(order_qty * entry_price),
            "margin_used": float(margin_amount),
            "leverage_used": int(leverage),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error calculating order quantity: {e}", exc_info=True)
        return {
            "error": f"Calculation error: {str(e)}"
        }

def calculate_position_risk_percent(entry_price: Decimal, sl_price: Decimal, side: str) -> float:
    """
    Calculate risk as percentage of entry price
    
    Args:
        entry_price: Entry price
        sl_price: Stop loss price
        side: Trade side
    
    Returns:
        Risk percentage (always positive)
    """
    try:
        entry_price = safe_decimal(entry_price)
        sl_price = safe_decimal(sl_price)
        
        if entry_price <= 0:
            return 0.0
        
        if side.upper() in ["BUY", "LONG"]:
            risk_distance = entry_price - sl_price
        else:
            risk_distance = sl_price - entry_price
        
        risk_percent = float((risk_distance / entry_price) * 100)
        return max(0.0, risk_percent)  # Ensure positive
        
    except Exception as e:
        logger.error(f"Error calculating risk percent: {e}")
        return 0.0

def calculate_position_risk(position_value: Decimal, sl_distance_percent: Decimal) -> Decimal:
    """
    Calculate risk amount for a position.
    
    Args:
        position_value: Total position value
        sl_distance_percent: Stop loss distance as percentage
    
    Returns:
        Risk amount in USDT
    """
    try:
        position_value = safe_decimal(position_value)
        sl_distance_percent = safe_decimal(sl_distance_percent)
        return position_value * (sl_distance_percent / 100)
    except Exception as e:
        logger.error(f"Error calculating position risk: {e}")
        return Decimal("0")

def calculate_required_margin(position_value: Decimal, leverage: int) -> Decimal:
    """
    Calculate required margin for a position.
    
    Args:
        position_value: Total position value
        leverage: Trading leverage
    
    Returns:
        Required margin amount
    """
    try:
        position_value = safe_decimal(position_value)
        leverage = safe_decimal(leverage)
        
        if leverage <= 0:
            return position_value
        return position_value / leverage
    except Exception as e:
        logger.error(f"Error calculating required margin: {e}")
        return safe_decimal(position_value)

def calculate_liquidation_price(entry_price: Decimal, side: str, leverage: int, 
                               maintenance_margin_rate: Decimal = Decimal("0.005")) -> Decimal:
    """
    Calculate approximate liquidation price.
    
    Args:
        entry_price: Entry price
        side: "Buy" or "Sell"
        leverage: Trading leverage
        maintenance_margin_rate: Maintenance margin rate (default 0.5%)
    
    Returns:
        Approximate liquidation price
    """
    try:
        # Convert to Decimal for precision
        entry_price = safe_decimal(entry_price)
        leverage = safe_decimal(leverage)
        maintenance_margin_rate = safe_decimal(maintenance_margin_rate)
        
        # Initial margin rate
        initial_margin_rate = Decimal("1") / leverage
        
        # Buffer before liquidation (initial margin - maintenance margin)
        buffer = initial_margin_rate - maintenance_margin_rate
        
        if side.upper() in ["BUY", "LONG"]:
            # For long positions, liquidation occurs below entry
            liquidation_price = entry_price * (Decimal("1") - buffer)
        else:
            # For short positions, liquidation occurs above entry
            liquidation_price = entry_price * (Decimal("1") + buffer)
        
        return liquidation_price
    except Exception as e:
        logger.error(f"Error calculating liquidation price: {e}")
        return safe_decimal(entry_price)

def calculate_position_pnl(entry_price: Decimal, current_price: Decimal, 
                          quantity: Decimal, side: str) -> Dict:
    """
    FIXED: Calculate position PnL with proper validation.
    
    Args:
        entry_price: Average entry price
        current_price: Current market price
        quantity: Position quantity
        side: "Buy" or "Sell"
    
    Returns:
        Dict with PnL details
    """
    try:
        # Convert to Decimal
        entry_price = safe_decimal(entry_price)
        current_price = safe_decimal(current_price)
        quantity = safe_decimal(quantity)
        
        if entry_price <= 0 or current_price <= 0 or quantity <= 0:
            return {
                "pnl": 0,
                "pnl_percent": 0,
                "is_profit": False,
                "error": "Invalid input values"
            }
        
        if side.upper() in ["BUY", "LONG"]:
            # For long positions: profit when price goes up
            pnl = (current_price - entry_price) * quantity
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
        else:  # SELL/SHORT
            # For short positions: profit when price goes down
            pnl = (entry_price - current_price) * quantity
            pnl_percent = ((entry_price - current_price) / entry_price) * 100
        
        return {
            "pnl": float(pnl),
            "pnl_percent": float(pnl_percent),
            "is_profit": pnl > 0,
            "price_change": float(current_price - entry_price),
            "price_change_percent": float(((current_price - entry_price) / entry_price) * 100)
        }
    except Exception as e:
        logger.error(f"Error calculating PnL: {e}")
        return {
            "pnl": 0,
            "pnl_percent": 0,
            "is_profit": False,
            "error": str(e)
        }

def calculate_pnl_at_price(entry_price: Decimal, target_price: Decimal, 
                          quantity: Decimal, side: str) -> float:
    """
    Calculate P&L at a specific target price (used for potential P&L calculations)
    
    Args:
        entry_price: Average entry price
        target_price: Target price (TP or SL)
        quantity: Position quantity
        side: "Buy" or "Sell"
    
    Returns:
        P&L amount at target price
    """
    try:
        # Convert to Decimal
        entry_price = safe_decimal(entry_price)
        target_price = safe_decimal(target_price)
        quantity = safe_decimal(quantity)
        
        if entry_price <= 0 or target_price <= 0 or quantity <= 0:
            return 0.0
        
        if side.upper() in ["BUY", "LONG"]:
            # For long positions: profit when price goes up
            pnl = (target_price - entry_price) * quantity
        else:  # SELL/SHORT
            # For short positions: profit when price goes down
            pnl = (entry_price - target_price) * quantity
        
        return float(pnl)
        
    except Exception as e:
        logger.error(f"Error calculating P&L at price: {e}")
        return 0.0

def validate_quantity_precision(quantity: Decimal, qty_step: Decimal) -> bool:
    """
    Validate that quantity matches the required step size
    
    Args:
        quantity: The quantity to validate
        qty_step: The required step size
    
    Returns:
        bool: True if quantity is valid for the step size
    """
    try:
        quantity = safe_decimal(quantity)
        qty_step = safe_decimal(qty_step)
        
        if qty_step <= 0:
            return True  # No step restriction
        
        # Check if quantity is a multiple of step
        remainder = quantity % qty_step
        return remainder == 0 or remainder < Decimal('1e-8')
    
    except Exception as e:
        logger.error(f"Error validating quantity precision: {e}")
        return False

def calculate_optimal_position_size(account_balance: Decimal, risk_percent: Decimal, 
                                   entry_price: Decimal, sl_price: Decimal, 
                                   side: str, leverage: int = 1) -> Dict:
    """
    FIXED: Calculate optimal position size based on risk management
    
    Args:
        account_balance: Available account balance
        risk_percent: Percentage of account to risk (e.g., 2.0 for 2%)
        entry_price: Entry price
        sl_price: Stop loss price
        side: Trade side
        leverage: Trading leverage
    
    Returns:
        Dict with position size details
    """
    try:
        # Convert inputs
        account_balance = safe_decimal(account_balance)
        risk_percent = safe_decimal(risk_percent)
        entry_price = safe_decimal(entry_price)
        sl_price = safe_decimal(sl_price)
        leverage = safe_decimal(leverage)
        
        # Validate inputs
        if account_balance <= 0:
            return {"error": "Account balance must be positive"}
        
        if not (0.1 <= risk_percent <= 10):
            return {"error": "Risk percent should be between 0.1% and 10%"}
        
        # Validate trade direction
        is_valid, validation_msg = validate_trade_direction_and_prices(side, entry_price, sl_price, entry_price)
        if not is_valid:
            return {"error": validation_msg}
        
        # Calculate risk per unit
        if side.upper() in ["BUY", "LONG"]:
            risk_per_unit = entry_price - sl_price
        else:
            risk_per_unit = sl_price - entry_price
        
        if risk_per_unit <= 0:
            return {"error": "Invalid stop loss placement"}
        
        # Calculate risk amount in USDT
        risk_amount = account_balance * (risk_percent / 100)
        
        # Calculate position size based on risk
        position_size = risk_amount / risk_per_unit
        
        # Calculate required margin
        position_value = position_size * entry_price
        required_margin = position_value / leverage
        
        # Check if we have enough balance
        if required_margin > account_balance:
            return {
                "error": f"Insufficient balance. Required: {required_margin:.2f}, Available: {account_balance:.2f}"
            }
        
        return {
            "position_size": float(position_size),
            "position_value": float(position_value),
            "required_margin": float(required_margin),
            "risk_amount": float(risk_amount),
            "risk_per_unit": float(risk_per_unit),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error calculating optimal position size: {e}")
        return {"error": str(e)}

def format_calculation_summary(calc_result: Dict, symbol: str, side: str) -> str:
    """
    Format calculation results for display
    
    Returns:
        Formatted string with calculation summary
    """
    try:
        if calc_result.get("error"):
            return f"❌ Error: {calc_result['error']}"
        
        if calc_result.get("success"):
            return f"""
📊 **Position Calculation Summary**
━━━━━━━━━━━━━━━━━━━━━━
🎯 Symbol: {symbol}
📈 Side: {side.upper()}
💎 Position Size: {calc_result.get('position_size', 0):.6f}
💰 Position Value: ${calc_result.get('position_value', 0):.2f}
🔒 Required Margin: ${calc_result.get('required_margin', 0):.2f}
⚠️ Risk Amount: ${calc_result.get('risk_amount', 0):.2f}
"""
        
        return "❌ Unknown calculation result format"
        
    except Exception as e:
        return f"❌ Error formatting summary: {e}"