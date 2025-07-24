#!/usr/bin/env python3
"""
Immediately sync mirror positions without restarting bot
"""
import asyncio
import pickle
import time
from datetime import datetime
from decimal import Decimal

async def immediate_mirror_sync():
    """Run immediate mirror position sync"""
    print("="*60)
    print("IMMEDIATE MIRROR POSITION SYNC")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # First, add mirror monitors to pickle
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    # Mirror positions from exchange
    mirror_positions = {
        'COTIUSDT': {'side': 'Buy', 'size': '124', 'avgPrice': '0.05125'},
        'CAKEUSDT': {'side': 'Buy', 'size': '27.5', 'avgPrice': '2.29'},
        'SNXUSDT': {'side': 'Buy', 'size': '112', 'avgPrice': '0.57089098'},
        '1INCHUSDT': {'side': 'Buy', 'size': '328.7', 'avgPrice': '0.2012'},
        'SUSHIUSDT': {'side': 'Buy', 'size': '107.7', 'avgPrice': '0.6166'}
    }
    
    added = 0
    for symbol, pos_data in mirror_positions.items():
        monitor_key = f"{symbol}_{pos_data['side']}_mirror"
        
        if monitor_key not in monitors:
            monitors[monitor_key] = {
                'symbol': symbol,
                'side': pos_data['side'],
                'position_size': Decimal(pos_data['size']),
                'remaining_size': Decimal(pos_data['size']),
                'entry_price': Decimal(pos_data['avgPrice']),
                'avg_price': Decimal(pos_data['avgPrice']),
                'approach': 'conservative',
                'tp_orders': {},
                'sl_order': None,
                'filled_tps': [],
                'cancelled_limits': False,
                'tp1_hit': False,
                'tp1_info': None,
                'sl_moved_to_be': False,
                'sl_move_attempts': 0,
                'created_at': time.time(),
                'last_check': time.time(),
                'limit_orders': [],
                'limit_orders_cancelled': False,
                'phase': 'MONITORING',
                'chat_id': None,
                'account_type': 'mirror'
            }
            added += 1
            print(f"✅ Added {monitor_key}")
    
    # Save back
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print(f"\n✅ Added {added} mirror monitors")
    print(f"✅ Total monitors: {len(monitors)}")
    
    # Create sync signal
    with open('mirror_sync_complete.signal', 'w') as f:
        f.write(f"SYNC_TIME={int(time.time())}\n")
        f.write(f"MIRROR_MONITORS={added}\n")
        f.write(f"TOTAL_MONITORS={len(monitors)}\n")
    
    print("\n✅ Mirror sync complete!")

if __name__ == "__main__":
    asyncio.run(immediate_mirror_sync())
