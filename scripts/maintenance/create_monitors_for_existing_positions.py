#!/usr/bin/env python3
"""
Create monitors for existing SUSHIUSDT positions
"""
import pickle
import time
from decimal import Decimal

def create_monitors():
    """Create monitors for existing positions"""
    try:
        print("🔍 CREATING MONITORS FOR EXISTING POSITIONS")
        print("=" * 60)
        
        # Load current pickle data
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        # Ensure structure exists
        if 'bot_data' not in data:
            data['bot_data'] = {}
        if 'enhanced_tp_sl_monitors' not in data['bot_data']:
            data['bot_data']['enhanced_tp_sl_monitors'] = {}
        
        current_time = int(time.time() * 1000)
        
        # Create main account monitor
        main_monitor = {
            "symbol": "SUSHIUSDT",
            "side": "Buy",
            "position_size": Decimal("326.1"),
            "remaining_size": Decimal("326.1"),
            "entry_price": Decimal("0.6166"),
            "avg_price": Decimal("0.6189"),
            "approach": "conservative",
            "tp_orders": {
                "3efde8a7-917e-45a5-889e-1dddb6013a9c": {
                    "order_id": "3efde8a7-917e-45a5-889e-1dddb6013a9c",
                    "price": Decimal("0.6458"),
                    "quantity": Decimal("277.1"),
                    "tp_level": 1
                },
                "e157824c-0530-457c-bc89-50da0f434a11": {
                    "order_id": "e157824c-0530-457c-bc89-50da0f434a11",
                    "price": Decimal("0.6757"),
                    "quantity": Decimal("16.3"),
                    "tp_level": 2
                },
                "cd50b84b-6c17-4a1f-b2e9-be613c436df2": {
                    "order_id": "cd50b84b-6c17-4a1f-b2e9-be613c436df2",
                    "price": Decimal("0.7057"),
                    "quantity": Decimal("16.3"),
                    "tp_level": 3
                },
                "417871b9-7e4a-4a7e-9b29-bf1e82f2dc49": {
                    "order_id": "417871b9-7e4a-4a7e-9b29-bf1e82f2dc49",
                    "price": Decimal("0.7956"),
                    "quantity": Decimal("16.3"),
                    "tp_level": 4
                }
            },
            "sl_order": {
                "order_id": "a99eb408-21d1-4920-8b82-6e50e9fd3f21",
                "price": Decimal("0.5566"),
                "quantity": Decimal("978.3")
            },
            "filled_tps": [],
            "cancelled_limits": False,
            "tp1_hit": False,
            "tp1_info": None,
            "sl_moved_to_be": False,
            "sl_move_attempts": 0,
            "created_at": current_time,
            "last_check": current_time,
            "limit_orders": [
                {
                    "order_id": "2a04a71f-aca7-4f04-9c9b-12d8b2cb2db7",
                    "price": Decimal("0.5996"),
                    "quantity": Decimal("326.1")
                },
                {
                    "order_id": "0ef166bc-6858-43ef-80c3-7dcbc3596432",
                    "price": Decimal("0.5852"),
                    "quantity": Decimal("326.1")
                }
            ],
            "limit_orders_cancelled": False,
            "phase": "MONITORING",
            "chat_id": 5634913742,
            "account_type": "main",
            "has_mirror": True,
            "monitoring_active": True
        }
        
        # Create mirror account monitor
        mirror_monitor = {
            "symbol": "SUSHIUSDT",
            "side": "Buy",
            "position_size": Decimal("108"),
            "remaining_size": Decimal("108"),
            "entry_price": Decimal("0.6166"),
            "avg_price": Decimal("0.6189"),
            "approach": "conservative",
            "tp_orders": {},  # Empty due to error
            "sl_order": {
                "order_id": "1e4e694e-15ef-4974-9f1f-50d511dd6338",
                "price": Decimal("0.5566"),
                "quantity": Decimal("108")
            },
            "filled_tps": [],
            "cancelled_limits": False,
            "tp1_hit": False,
            "tp1_info": None,
            "sl_moved_to_be": False,
            "sl_move_attempts": 0,
            "created_at": current_time,
            "last_check": current_time,
            "limit_orders": [
                {
                    "order_id": "4cf68802-a574-4357-bc77-b9f3792b62b8",
                    "price": Decimal("0.5996"),
                    "quantity": Decimal("108")
                },
                {
                    "order_id": "ed455471-3de0-4e33-950d-fd2b394d72fe",
                    "price": Decimal("0.5852"),
                    "quantity": Decimal("108")
                }
            ],
            "limit_orders_cancelled": False,
            "phase": "MONITORING",
            "chat_id": 5634913742,
            "account_type": "mirror",
            "has_mirror": False,
            "monitoring_active": True
        }
        
        # Add monitors
        data['bot_data']['enhanced_tp_sl_monitors']['SUSHIUSDT_Buy'] = main_monitor
        data['bot_data']['enhanced_tp_sl_monitors']['SUSHIUSDT_Buy_mirror'] = mirror_monitor
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        print("✅ Created monitor: SUSHIUSDT_Buy (main)")
        print("✅ Created monitor: SUSHIUSDT_Buy_mirror")
        print(f"📊 Total monitors: 2")
        
        print("\n📝 NOTE: Mirror TP orders missing due to earlier error")
        print("   The bot will need to be restarted with the fix to place mirror TP orders")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_monitors()