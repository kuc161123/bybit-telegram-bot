
# Runtime patch for stop loss detection
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

def identify_order_type_enhanced(order: Dict, position_side: str, entry_price: float) -> str:
    """Enhanced order type identification that doesn't rely on stopOrderType."""

    try:
        trigger_price = float(order.get('triggerPrice', 0))
        trigger_direction = order.get('triggerDirection', 0)

        if trigger_price == 0:
            return 'unknown'

        # For long positions
        if position_side == "Buy":
            if trigger_price > entry_price:
                # Price above entry = Take Profit
                return 'tp' if trigger_direction == 1 else 'misconfigured_tp'
            else:
                # Price below entry = Stop Loss
                return 'sl' if trigger_direction == 2 else 'misconfigured_sl'

        # For short positions
        else:
            if trigger_price < entry_price:
                # Price below entry = Take Profit
                return 'tp' if trigger_direction == 2 else 'misconfigured_tp'
            else:
                # Price above entry = Stop Loss
                return 'sl' if trigger_direction == 1 else 'misconfigured_sl'

    except Exception as e:
        logger.error(f"Error identifying order type: {e}")
        return 'unknown'

# Monkey patch the function into the monitor module
try:
    import execution.monitor
    execution.monitor.identify_order_type_enhanced = identify_order_type_enhanced
    logger.info("✅ Runtime patch installed successfully")
except Exception as e:
    logger.error(f"Failed to install runtime patch: {e}")
