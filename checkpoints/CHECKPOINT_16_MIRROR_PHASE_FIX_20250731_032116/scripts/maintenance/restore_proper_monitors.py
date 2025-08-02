#!/usr/bin/env python3
"""
Restore monitors with proper account-aware keys
"""
import pickle
import time
import logging
from decimal import Decimal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Main account positions
main_positions = [
    {"symbol": "IDUSDT", "side": "Sell", "size": "1165.0", "entry": "0.1478"},
    {"symbol": "LINKUSDT", "side": "Buy", "size": "30.9", "entry": "13.478"},
    {"symbol": "XRPUSDT", "side": "Buy", "size": "260.0", "entry": "2.28959577"},
    {"symbol": "JUPUSDT", "side": "Sell", "size": "4160.0", "entry": "0.4283"},
    {"symbol": "ICPUSDT", "side": "Sell", "size": "72.3", "entry": "4.743"},
    {"symbol": "TIAUSDT", "side": "Buy", "size": "510.2", "entry": "1.6015"},
    {"symbol": "DOGEUSDT", "side": "Buy", "size": "4069.0", "entry": "0.16872771"},
]

# Mirror account positions
mirror_positions = [
    {"symbol": "ICPUSDT", "side": "Sell", "size": "24.3", "entry": "4.743"},
    {"symbol": "IDUSDT", "side": "Sell", "size": "391", "entry": "0.1478"},
    {"symbol": "JUPUSDT", "side": "Sell", "size": "1401", "entry": "0.4283"},
    {"symbol": "TIAUSDT", "side": "Buy", "size": "168.2", "entry": "1.6015"},
    {"symbol": "LINKUSDT", "side": "Buy", "size": "10.2", "entry": "13.478"},
    {"symbol": "XRPUSDT", "side": "Buy", "size": "87", "entry": "2.28959577"},
]

# Load pickle
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
    data = pickle.load(f)

monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})

# Create main account monitors
for pos in main_positions:
    monitor_key = f"{pos['symbol']}_{pos['side']}_main"
    if monitor_key not in monitors:
        monitors[monitor_key] = {
            "symbol": pos['symbol'],
            "side": pos['side'],
            "position_size": Decimal(pos['size']),
            "remaining_size": Decimal(pos['size']),
            "entry_price": Decimal(pos['entry']),
            "avg_price": Decimal(pos['entry']),
            "approach": "fast",
            "tp_orders": {},
            "sl_order": None,
            "filled_tps": [],
            "cancelled_limits": False,
            "tp1_hit": False,
            "tp1_info": None,
            "sl_moved_to_be": False,
            "sl_move_attempts": 0,
            "created_at": time.time(),
            "last_check": time.time(),
            "limit_orders": [],
            "limit_orders_cancelled": False,
            "phase": "MONITORING",
            "chat_id": 402061794,
            "account_type": "main"
        }
        logger.info(f"✅ Created monitor: {monitor_key}")

# Create mirror account monitors
for pos in mirror_positions:
    monitor_key = f"{pos['symbol']}_{pos['side']}_mirror"
    if monitor_key not in monitors:
        monitors[monitor_key] = {
            "symbol": pos['symbol'],
            "side": pos['side'],
            "position_size": Decimal(pos['size']),
            "remaining_size": Decimal(pos['size']),
            "entry_price": Decimal(pos['entry']),
            "avg_price": Decimal(pos['entry']),
            "approach": "fast",
            "tp_orders": {},
            "sl_order": None,
            "filled_tps": [],
            "cancelled_limits": False,
            "tp1_hit": False,
            "tp1_info": None,
            "sl_moved_to_be": False,
            "sl_move_attempts": 0,
            "created_at": time.time(),
            "last_check": time.time(),
            "limit_orders": [],
            "limit_orders_cancelled": False,
            "phase": "MONITORING",
            "chat_id": None,
            "account_type": "mirror",
            "has_mirror": True
        }
        logger.info(f"✅ Created monitor: {monitor_key}")

# Save updated data
data['bot_data']['enhanced_tp_sl_monitors'] = monitors
with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
    pickle.dump(data, f)

logger.info(f"\n✅ Total monitors: {len(monitors)}")
logger.info(f"✅ Main account: {sum(1 for k in monitors if k.endswith('_main'))}")
logger.info(f"✅ Mirror account: {sum(1 for k in monitors if k.endswith('_mirror'))}")

# Create signal file
with open('reload_enhanced_monitors.signal', 'w') as f:
    f.write(str(time.time()))
logger.info("\n✅ Created reload signal")