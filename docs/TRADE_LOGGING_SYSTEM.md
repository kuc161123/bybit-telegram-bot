# Trade Logging System

## Overview

The Trade Logging System provides comprehensive tracking of all trade operations, including entries, exits, merges, and rebalances. This system helps the auto-rebalancer verify positions and maintain correct order quantities.

## Components

### 1. Trade Logger (`utils/trade_logger.py`)
- Logs all trade executions with complete details
- Tracks entry prices, TP/SL levels, and trigger prices
- Stores approach type (Fast/Conservative)
- Records fills, merges, and rebalances
- Maintains trade history in JSON format
- Automatic file rotation when size exceeds 50MB

### 2. Trade Verifier (`utils/trade_verifier.py`)
- Verifies current positions match logged trades
- Detects discrepancies in order quantities
- Provides correction suggestions
- Validates against expected distributions:
  - Fast: 100% for both TP and SL
  - Conservative: 85%, 5%, 5%, 5% for TPs, 100% for SL

### 3. Integration Points

#### Trader (`execution/trader.py`)
- Logs trade entry on execution
- Records TP/SL orders with trigger prices
- Logs position merges

#### Monitor (`execution/monitor.py`)
- Logs order fills (TP/SL hits)
- Updates trade status

#### Auto-Rebalancer (`execution/auto_rebalancer.py`)
- Uses trade history for verification
- Logs rebalancing operations
- References original trigger prices

#### Position Merger (`execution/position_merger.py`)
- Logs merge operations
- Tracks position evolution

## Data Structure

### Trade History Entry
```json
{
  "BTCUSDT_Buy_Fast_123456_20250626_100000": {
    "symbol": "BTCUSDT",
    "side": "Buy",
    "approach": "Fast",
    "chat_id": "123456",
    "entry": {
      "price": "65000.00",
      "size": "0.1",
      "timestamp": "2025-06-26T10:00:00Z",
      "order_type": "Market",
      "leverage": 10,
      "risk_percentage": "2"
    },
    "tp_orders": [
      {
        "level": 1,
        "price": "67000.00",
        "quantity": "0.1",
        "percentage": 100,
        "order_id": "TP123456",
        "order_link_id": "BOT_FAST_123_TP",
        "status": "pending"
      }
    ],
    "sl_order": {
      "price": "63000.00",
      "quantity": "0.1",
      "percentage": 100,
      "order_id": "SL123456",
      "order_link_id": "BOT_FAST_123_SL",
      "status": "pending"
    },
    "fills": [
      {
        "type": "TP",
        "price": "67000.00",
        "quantity": "0.1",
        "timestamp": "2025-06-26T11:30:00Z",
        "order_id": "TP123456"
      }
    ],
    "merges": [],
    "rebalances": [
      {
        "timestamp": "2025-06-26T10:05:00Z",
        "trigger_type": "new_position",
        "orders_cancelled": 0,
        "orders_created": 2,
        "details": {
          "position_size": "0.1",
          "tp_distribution": "100%"
        }
      }
    ],
    "status": "closed"
  }
}
```

## Key Features

### 1. Complete Trade Lifecycle
- Entry logging with all parameters
- TP/SL order tracking
- Fill detection and P&L calculation
- Position closure tracking

### 2. Original Trigger Price Preservation
- Stores initial TP/SL prices
- Available for reference during rebalancing
- Helps maintain trading plan integrity

### 3. Merge Operation Tracking
- Records positions being merged
- Tracks size evolution
- Maintains average price history

### 4. Rebalance History
- Logs all rebalancing operations
- Records trigger type (new position, merge, orders filled)
- Tracks orders cancelled/created

### 5. Verification Support
- Compare current positions with logged data
- Detect quantity discrepancies
- Identify missing or extra orders

## Usage Examples

### Log New Trade
```python
from utils.trade_logger import log_trade_entry, log_tp_orders, log_sl_order

# Log entry
trade_key = await log_trade_entry(
    symbol="BTCUSDT",
    side="Buy",
    approach="Fast",
    entry_price=Decimal("65000"),
    size=Decimal("0.1"),
    order_type="Market",
    chat_id="123456",
    leverage=10,
    risk_percentage=Decimal("2")
)

# Log TP order
await log_tp_orders(trade_key, [{
    'symbol': 'BTCUSDT',
    'side': 'Sell',
    'price': '67000',
    'qty': '0.1',
    'percentage': 100,
    'orderId': 'TP123456',
    'orderLinkId': 'BOT_FAST_123_TP'
}])

# Log SL order
await log_sl_order(trade_key, {
    'symbol': 'BTCUSDT',
    'side': 'Buy',
    'triggerPrice': '63000',
    'qty': '0.1',
    'orderId': 'SL123456',
    'orderLinkId': 'BOT_FAST_123_SL'
})
```

### Log Order Fill
```python
from utils.trade_logger import log_order_fill

await log_order_fill(
    symbol="BTCUSDT",
    side="Buy",
    order_type="TP",
    fill_price=Decimal("67000"),
    fill_qty=Decimal("0.1"),
    order_id="TP123456"
)
```

### Get Original Trigger Prices
```python
from utils.trade_logger import get_original_trigger_prices

original_prices = await get_original_trigger_prices("BTCUSDT", "Buy")
# Returns:
# {
#     "entry_price": "65000",
#     "tp_prices": ["67000"],
#     "sl_price": "63000",
#     "approach": "Fast",
#     "trade_key": "BTCUSDT_Buy_Fast_123456_20250626_100000"
# }
```

### Verify Position
```python
from utils.trade_verifier import verify_position

verification_result = await verify_position(
    symbol="BTCUSDT",
    side="Buy",
    position=position_dict,
    orders=orders_list
)

if not verification_result.get("verified"):
    print("Discrepancies found:")
    for discrepancy in verification_result.get("discrepancies", []):
        print(f"  - {discrepancy['message']}")
```

## Auto-Rebalancer Integration

The auto-rebalancer automatically:
1. Verifies positions against trade history
2. Logs detected discrepancies
3. References original trigger prices
4. Records all rebalancing operations

When the auto-rebalancer detects a position change:
```
[INFO] Position verification failed for BTCUSDT:
   - TP quantity should be 100% (0.1), found 0.08
[INFO] Original trigger prices from trade history:
   Entry: 65000
   TPs: ['67000']
   SL: 63000
[INFO] Rebalancing completed for BTCUSDT
[INFO] Logged rebalancing to trade history
```

## Testing

Run the test script to see the system in action:
```bash
python test_trade_logger.py
```

This demonstrates:
- Trade entry logging
- TP/SL order logging
- Order fill tracking
- Trade history retrieval
- Original price lookup
- Rebalance logging
- Conservative approach with 4 TPs

## File Locations

- **Trade History**: `data/trade_history.json`
- **Archived History**: `data/trade_history_YYYYMMDD_HHMMSS.json`
- **Test Script**: `test_trade_logger.py`

## Benefits

1. **Complete Audit Trail**: Every trade action is logged
2. **Position Verification**: Detect and fix discrepancies
3. **Historical Reference**: Access original trading parameters
4. **Automated Corrections**: Auto-rebalancer uses history for decisions
5. **Performance Analysis**: Track fills and P&L over time