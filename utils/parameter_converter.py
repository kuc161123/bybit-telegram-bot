#!/usr/bin/env python3
"""
Parameter Converter for Bybit API
Converts snake_case parameters to camelCase for API compatibility
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Comprehensive parameter mapping for Bybit API
PARAMETER_MAPPING = {
    # Order parameters
    'order_id': 'orderId',
    'order_link_id': 'orderLinkId',
    'order_type': 'orderType',
    'order_status': 'orderStatus',
    'order_filter': 'orderFilter',
    
    # Price and quantity
    'trigger_price': 'triggerPrice',
    'trigger_by': 'triggerBy',
    'trigger_direction': 'triggerDirection',
    'take_profit': 'takeProfit',
    'stop_loss': 'stopLoss',
    'tp_trigger_by': 'tpTriggerBy',
    'sl_trigger_by': 'slTriggerBy',
    'tp_order_type': 'tpOrderType',
    'sl_order_type': 'slOrderType',
    'tp_size': 'tpSize',
    'sl_size': 'slSize',
    'tp_limit_price': 'tpLimitPrice',
    'sl_limit_price': 'slLimitPrice',
    
    # Position parameters
    'position_idx': 'positionIdx',
    'position_mode': 'positionMode',
    'position_side': 'positionSide',
    'position_value': 'positionValue',
    'position_balance': 'positionBalance',
    'position_mm': 'positionMM',
    'position_im': 'positionIM',
    
    # Trading parameters
    'time_in_force': 'timeInForce',
    'reduce_only': 'reduceOnly',
    'close_on_trigger': 'closeOnTrigger',
    'stop_order_type': 'stopOrderType',
    'market_unit': 'marketUnit',
    
    # Account parameters
    'account_type': 'accountType',
    'settle_coin': 'settleCoin',
    'base_coin': 'baseCoin',
    'quote_coin': 'quoteCoin',
    
    # Risk parameters
    'risk_limit': 'riskLimit',
    'trailing_stop': 'trailingStop',
    'active_price': 'activePrice',
    'auto_add_margin': 'autoAddMargin',
    
    # Time parameters
    'created_time': 'createdTime',
    'updated_time': 'updatedTime',
    'exec_time': 'execTime',
    
    # Other parameters
    'is_leverage': 'isLeverage',
    'leave_qty': 'leaveQty',
    'leave_value': 'leaveValue',
    'cum_exec_qty': 'cumExecQty',
    'cum_exec_value': 'cumExecValue',
    'cum_exec_fee': 'cumExecFee',
    'last_price': 'lastPrice',
    'unrealised_pnl': 'unrealisedPnl',
    'realised_pnl': 'realisedPnl',
    'avg_price': 'avgPrice',
    'mark_price': 'markPrice',
    'index_price': 'indexPrice',
    'liq_price': 'liqPrice',
    'bust_price': 'bustPrice',
    'leverage_sz': 'leverageSz',
    'adl_rank_indicator': 'adlRankIndicator'
}

def convert_to_camel_case(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert snake_case parameters to camelCase for Bybit API
    
    Args:
        params: Dictionary with snake_case keys
        
    Returns:
        Dictionary with camelCase keys
    """
    if not params:
        return {}
    
    converted = {}
    conversions_made = []
    
    for key, value in params.items():
        # Check if we have a mapping for this parameter
        if key in PARAMETER_MAPPING:
            new_key = PARAMETER_MAPPING[key]
            converted[new_key] = value
            if key != new_key:  # Only log if actually converted
                conversions_made.append(f"{key} -> {new_key}")
        else:
            # Keep original key if no mapping exists
            converted[key] = value
    
    if conversions_made:
        logger.debug(f"Parameter conversions: {', '.join(conversions_made)}")
    
    return converted

def convert_to_snake_case(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert camelCase parameters to snake_case (reverse conversion)
    
    Args:
        params: Dictionary with camelCase keys
        
    Returns:
        Dictionary with snake_case keys
    """
    if not params:
        return {}
    
    # Create reverse mapping
    reverse_mapping = {v: k for k, v in PARAMETER_MAPPING.items()}
    
    converted = {}
    
    for key, value in params.items():
        if key in reverse_mapping:
            converted[reverse_mapping[key]] = value
        else:
            # Keep original key if no mapping exists
            converted[key] = value
    
    return converted

def ensure_required_params(params: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    """
    Ensure required parameters are present
    
    Args:
        params: Parameters dictionary
        required: List of required parameter names (in camelCase)
        
    Returns:
        Parameters with required fields
        
    Raises:
        ValueError: If required parameters are missing
    """
    missing = []
    
    for param in required:
        if param not in params:
            # Check if snake_case version exists
            snake_case_key = None
            for k, v in PARAMETER_MAPPING.items():
                if v == param:
                    snake_case_key = k
                    break
            
            if snake_case_key and snake_case_key in params:
                # Convert it
                params[param] = params[snake_case_key]
            else:
                missing.append(param)
    
    if missing:
        raise ValueError(f"Missing required parameters: {', '.join(missing)}")
    
    return params

def prepare_order_params(params: Dict[str, Any], is_mirror: bool = False) -> Dict[str, Any]:
    """
    Prepare order parameters for API call
    
    Args:
        params: Order parameters
        is_mirror: Whether this is for mirror account
        
    Returns:
        Prepared parameters ready for API
    """
    # Convert to camelCase
    converted = convert_to_camel_case(params)
    
    # Ensure category is set for mirror accounts
    if is_mirror and 'category' not in converted:
        converted['category'] = 'linear'
        logger.debug("Added 'category': 'linear' for mirror account order")
    
    # Ensure common required fields
    if 'symbol' in converted:
        # Symbol should always be uppercase
        converted['symbol'] = converted['symbol'].upper()
    
    # Handle boolean conversions
    bool_fields = ['reduceOnly', 'closeOnTrigger', 'isLeverage']
    for field in bool_fields:
        if field in converted and isinstance(converted[field], str):
            converted[field] = converted[field].lower() == 'true'
    
    # Handle numeric conversions
    numeric_fields = ['qty', 'price', 'triggerPrice', 'leverage', 'positionIdx']
    for field in numeric_fields:
        if field in converted and converted[field] is not None:
            converted[field] = str(converted[field])
    
    return converted

def prepare_position_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare position query parameters
    
    Args:
        params: Position parameters
        
    Returns:
        Prepared parameters
    """
    converted = convert_to_camel_case(params)
    
    # Ensure category is set
    if 'category' not in converted:
        converted['category'] = 'linear'
    
    # Ensure settleCoin for position queries without symbol
    if 'symbol' not in converted and 'settleCoin' not in converted:
        converted['settleCoin'] = 'USDT'
        logger.debug("Added 'settleCoin': 'USDT' for position query")
    
    return converted