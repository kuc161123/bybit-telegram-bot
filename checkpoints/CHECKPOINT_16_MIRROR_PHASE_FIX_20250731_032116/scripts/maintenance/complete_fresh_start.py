#!/usr/bin/env python3
"""
Complete fresh start - close all positions/orders and wipe bot memory
"""

import asyncio
import pickle
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.bybit_client import bybit_client
from config.settings import ENABLE_MIRROR_TRADING as BYBIT_MIRROR_ENABLED

async def close_all_positions_and_orders():
    """Close all positions and orders on both accounts"""
    
    print("🧹 Starting complete fresh start process...")
    print("=" * 60)
    
    # 1. Cancel all orders on main account
    print("\n📌 MAIN ACCOUNT - Cancelling all orders...")
    try:
        main_orders = await bybit_client.fetch_open_orders()
        if main_orders:
            print(f"Found {len(main_orders)} open orders on main account")
            for order in main_orders:
                try:
                    result = await bybit_client.cancel_order(
                        symbol=order['symbol'],
                        order_id=order['orderId']
                    )
                    print(f"  ✅ Cancelled {order['symbol']} order: {order['orderId']}")
                except Exception as e:
                    print(f"  ❌ Failed to cancel {order['symbol']} order: {e}")
        else:
            print("  No open orders found on main account")
    except Exception as e:
        print(f"  ❌ Error fetching main orders: {e}")
    
    # 2. Close all positions on main account
    print("\n📌 MAIN ACCOUNT - Closing all positions...")
    try:
        main_positions = await bybit_client.fetch_positions()
        active_positions = [p for p in main_positions if float(p.get('size', 0)) > 0]
        
        if active_positions:
            print(f"Found {len(active_positions)} open positions on main account")
            for position in active_positions:
                try:
                    symbol = position['symbol']
                    side = position['side']
                    size = position['size']
                    
                    # Close position with market order
                    close_side = "Sell" if side == "Buy" else "Buy"
                    result = await bybit_client.place_order(
                        symbol=symbol,
                        side=close_side,
                        order_type="Market",
                        qty=str(size),
                        reduce_only=True
                    )
                    print(f"  ✅ Closed {symbol} {side} position: {size}")
                except Exception as e:
                    print(f"  ❌ Failed to close {symbol} position: {e}")
        else:
            print("  No open positions found on main account")
    except Exception as e:
        print(f"  ❌ Error fetching main positions: {e}")
    
    # 3. Handle mirror account if enabled
    if BYBIT_MIRROR_ENABLED:
        print("\n📌 MIRROR ACCOUNT - Cancelling all orders...")
        try:
            from clients.bybit_client import mirror_client
            
            mirror_orders = await mirror_client.fetch_open_orders()
            if mirror_orders:
                print(f"Found {len(mirror_orders)} open orders on mirror account")
                for order in mirror_orders:
                    try:
                        result = await mirror_client.cancel_order(
                            symbol=order['symbol'],
                            order_id=order['orderId']
                        )
                        print(f"  ✅ Cancelled {order['symbol']} order: {order['orderId']}")
                    except Exception as e:
                        print(f"  ❌ Failed to cancel {order['symbol']} order: {e}")
            else:
                print("  No open orders found on mirror account")
        except Exception as e:
            print(f"  ❌ Error handling mirror orders: {e}")
        
        print("\n📌 MIRROR ACCOUNT - Closing all positions...")
        try:
            mirror_positions = await mirror_client.fetch_positions()
            active_positions = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
            
            if active_positions:
                print(f"Found {len(active_positions)} open positions on mirror account")
                for position in active_positions:
                    try:
                        symbol = position['symbol']
                        side = position['side']
                        size = position['size']
                        
                        # Close position with market order
                        close_side = "Sell" if side == "Buy" else "Buy"
                        result = await mirror_client.place_order(
                            symbol=symbol,
                            side=close_side,
                            order_type="Market",
                            qty=str(size),
                            reduce_only=True
                        )
                        print(f"  ✅ Closed {symbol} {side} position: {size}")
                    except Exception as e:
                        print(f"  ❌ Failed to close {symbol} position: {e}")
            else:
                print("  No open positions found on mirror account")
        except Exception as e:
            print(f"  ❌ Error handling mirror positions: {e}")
    
    print("\n✅ All positions and orders closed!")
    return True

def wipe_bot_memory():
    """Wipe the bot's persistence file for a fresh start"""
    
    print("\n🧹 Wiping bot memory...")
    
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    # Create backup first
    if os.path.exists(persistence_file):
        backup_name = f"{persistence_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        import shutil
        shutil.copy(persistence_file, backup_name)
        print(f"✅ Created backup: {backup_name}")
    
    # Create fresh persistence data
    fresh_data = {
        'bot_data': {
            'enhanced_tp_sl_monitors': {},
            'monitor_tasks': {},
            'order_protection': {},
            'active_conversations': {},
            'execution_summary': {},
            'trade_groups': {},
            'position_modes': {},
            'actual_entry_prices': {},
            'breakeven_positions': set(),
            'pending_limit_orders': {},
            'closed_positions': set(),
            'tp1_cancelled_trades': set(),
            'protected_symbols': {},
            'warned_positions': set(),
            'fill_tracker': {},
            'order_lifecycle': {},
            'captured_orders': {}
        },
        'user_data': {},
        'chat_data': {},
        'callback_data': {},
        'conversations': {}
    }
    
    # Save fresh persistence data
    with open(persistence_file, 'wb') as f:
        pickle.dump(fresh_data, f)
    
    print("✅ Bot memory wiped - fresh persistence file created")
    
    # Create marker files to prevent restoration
    marker_files = [
        '.fresh_start',
        '.no_backup_restore', 
        '.disable_persistence_recovery'
    ]
    
    for marker in marker_files:
        with open(marker, 'w') as f:
            f.write(datetime.now().isoformat())
        print(f"✅ Created marker: {marker}")
    
    print("\n✅ Bot memory completely wiped!")
    print("📌 Restart the bot for a completely fresh start")

async def main():
    """Main execution"""
    print("🚀 COMPLETE FRESH START")
    print("This will:")
    print("  1. Close all positions on both accounts")
    print("  2. Cancel all orders on both accounts")
    print("  3. Wipe bot memory (persistence file)")
    print("\n⚠️  This action cannot be undone!")
    
    # Auto-proceed for script execution
    print("\n✅ Auto-proceeding with fresh start...")
    
    # Close all positions and orders
    await close_all_positions_and_orders()
    
    # Wipe bot memory
    wipe_bot_memory()
    
    print("\n" + "=" * 60)
    print("✅ FRESH START COMPLETE!")
    print("=" * 60)
    print("\n📌 Please restart the bot with: python3 main.py")
    print("📌 The bot will start with:")
    print("  - No open positions or orders")
    print("  - No monitoring tasks")
    print("  - No saved trade history")
    print("  - Fresh persistence file")

if __name__ == "__main__":
    asyncio.run(main())