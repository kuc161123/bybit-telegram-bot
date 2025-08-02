# Execution Summary Module

## Overview
The Execution Summary module provides comprehensive tracking and reporting of trade executions, position merges, and monitor health for both main and mirror Bybit accounts.

## Features

### 1. Trade Execution Tracking
- Records detailed execution data for every trade
- Tracks orders placed, fill status, and execution times
- Monitors both main and mirror account executions
- Captures position merge decisions and rationale

### 2. Monitor Health Reporting
- Real-time health status of position monitors
- Tracks active monitors by approach (Fast/Conservative/GGShot)
- Reports errors and restarts for reliability monitoring
- Separate tracking for main and mirror accounts

### 3. Dashboard Integration
The execution summary integrates seamlessly with the analytics dashboard, providing:

#### Monitor Overview Section
```
🎯 MONITOR OVERVIEW
┌─────────────────────────────────────
│ PRIMARY ACCOUNT
├ ⚡ Fast: 2 monitors
├ 🛡️ Conservative: 3 monitors  
├ 📸 GGShot: 1 monitors
└ 📊 Total: 6 active

│ MIRROR ACCOUNT
├ ⚡ Fast: 2 monitors
├ 🛡️ Conservative: 3 monitors
├ 📸 GGShot: 1 monitors
└ 📊 Total: 6 active
```

#### Execution Summary Section
```
📋 EXECUTION SUMMARY
├ Total Executions: 25
├ Success Rate: 96.0%
├ Order Fill Rate: 94.2%/150 orders
├ Position Merges: 8 (32% of trades)
├ Main Exec Time: 1.25s avg
├ Mirror Exec Time: 1.45s avg
├ Mirror Sync: 95.0% synced
├ Fast Trades: 10 (40%)
├ Conservative: 12 (48%)
└ GGShot: 3 (12%)
```

#### Recent Executions Display
```
🚀 RECENT EXECUTIONS
├ ✅ BTCUSDT 📈 (C) 🔄🪞 - 5 mins ago
│  └ Merged: Same symbol and side
├ ✅ ETHUSDT 📉 (F) 🪞 - 15 mins ago
└ ⚠️ SOLUSDT 📈 (G) - 1 hour ago
```

### 4. Merge Decision Tracking
The module records detailed information about position merge decisions:
- Why positions were merged (same symbol/side)
- Parameter changes (SL/TP adjustments)
- Conservative vs Aggressive selection logic
- Limit order replacement decisions

### 5. Execution Details Format
Detailed execution information can be retrieved for any trade:

```
📊 EXECUTION DETAILS - TRADE-ID
════════════════════════════════════════

🎯 Trade Info
├ Symbol: BTCUSDT Buy
├ Approach: CONSERVATIVE
├ Leverage: 10x
├ Size: 0.01
└ Margin: $100

📍 Main Account Execution
├ Orders: 5
├ Status: filled
├ Slippage: 0.025%
├ Time: 1.34s
└ ✅ No errors

🪞 Mirror Account Execution
├ Orders: 5
├ Status: filled
├ Sync: synced
├ Time: 1.56s
└ ✅ Synced successfully

🔄 Position Merge
├ Status: MERGED ✅
├ Reason: Same symbol and side position exists
├ Previous: 0.005 BTC
└ New Total: 0.015 BTC

📋 Order Breakdown
├ Market: 1
├ Limit: 2  
├ TP Orders: 4
├ SL Orders: 1
└ Cancelled: 0

📈 Metrics
├ Success Rate: 100.0%
├ Avg Fill Time: 0.27s
└ Risk/Reward: 1:2.5
```

## Implementation Details

### Recording Executions
The trader.py module records execution data at key points:
1. After order placement (market/limit orders)
2. After TP/SL order creation
3. When position merges occur
4. Upon execution completion

### Monitor Health Updates
The monitor.py module reports health status:
- Every 10 monitoring cycles
- On error occurrence
- When monitor stops

### Data Management
- Executions: Keeps last 50 trades (auto-cleanup)
- Merge decisions: Keeps last 10 per symbol/side pair
- Monitor health: Real-time with 5-minute staleness check
- Order history: Last 100 entries

## Usage

### Recording an Execution
```python
execution_data = {
    'trade_id': trade_group_id,
    'symbol': symbol,
    'side': side,
    'approach': 'conservative',
    'leverage': leverage,
    'margin_amount': float(margin_amount),
    'position_size': float(position_size),
    'entry_price': float(entry_price),
    'main_orders': order_ids,
    'main_fill_status': 'filled',
    'main_execution_time': exec_time,
    'main_errors': errors,
    # ... additional fields
}
await execution_summary.record_execution(trade_id, execution_data)
```

### Updating Monitor Health
```python
health_data = {
    'symbol': symbol,
    'approach': approach,
    'account': 'primary',
    'status': 'active',
    'last_check': time.time(),
    'errors': 0,
    'position_size': float(position_size),
    'unrealized_pnl': float(pnl)
}
await execution_summary.update_monitor_health(monitor_id, health_data)
```

### Recording Merge Decisions
```python
merge_decision = {
    'merged': True,
    'reason': 'Same symbol and side',
    'existing_size': float(existing_size),
    'new_size': float(new_size),
    'approach': 'conservative',
    'parameters_changed': True,
    'sl_changed': True,
    'details': {
        'sl_selection': 'Conservative SL chosen',
        'tp_selection': 'Aggressive TP chosen'
    }
}
await execution_summary.record_merge_decision(symbol, side, merge_decision)
```

## Performance Considerations
- Uses asyncio locks for thread safety
- Automatic cleanup of old data
- Minimal memory footprint
- No external dependencies
- Fast in-memory operations

## Future Enhancements
- Persistent storage option
- Historical analytics
- Export functionality
- WebSocket real-time updates
- Advanced merge analytics