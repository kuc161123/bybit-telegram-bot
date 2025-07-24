# Manual Code Edits Required for Complete Removal

After running the hot-patch, these manual edits are needed for permanent removal:

## 1. clients/bybit_helpers.py

Remove line 975:
```python
from utils.external_order_protection import external_order_protection
```

Remove lines 980-988 in amend_order_with_retry():
```python
if order_info and not external_order_protection.can_modify_order(order_info):
    logger.warning(f"🛡️ Order {order_id[:8]}... is external - modification blocked")
    return None
# ... and the except block checking strict_mode
```

Remove lines 1077-1085 in cancel_order_with_retry():
```python
if not external_order_protection.can_modify_order(order_info):
    logger.warning(f"🛡️ Order {order_id[:8]}... is external - cancellation blocked")
    return False
# ... and the except block checking strict_mode
```

## 2. execution/monitor.py

Remove line 38:
```python
from utils.external_order_protection import external_order_protection
```

Remove lines 2312-2323:
```python
# Check if this position should be monitored (skip external positions)
# Get orders for this position to check ownership
try:
    all_orders = await get_open_orders(symbol)
    
    # Check if we should monitor this position
    if not external_order_protection.should_monitor_position(position, all_orders):
        logger.info(f"🛡️ Stopping monitor for {symbol} - external position detected")
        # Deactivate this monitor
        chat_data[ACTIVE_MONITOR_TASK] = {"active": False}
        break
except Exception as e:
    logger.error(f"Error checking position ownership: {e}")
```

## 3. config/settings.py

Remove line 142:
```python
BOT_ORDER_PREFIX_STRICT = os.getenv("BOT_ORDER_PREFIX_STRICT", "true").lower() == "true"
```

## 4. .env.example

Remove these lines:
```
EXTERNAL_ORDER_PROTECTION=true
BOT_ORDER_PREFIX_STRICT=true
```

## 5. CLAUDE.md

Remove the "External Order Protection System" section from the documentation.

Generated: 20250712_110804
