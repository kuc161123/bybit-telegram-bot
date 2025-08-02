#!/usr/bin/env python3
"""
Recreate monitors properly for both main and mirror accounts
"""

import asyncio
import logging
from config.settings import BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET, ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
from pybit.unified_trading import HTTP
import pickle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def recreate_monitors():
    """Recreate monitors for active positions with proper setup"""
    
    print("\n🔄 RECREATING MONITORS PROPERLY")
    print("=" * 60)
    
    # Initialize clients
    main_client = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET
    )
    
    mirror_client = None
    if ENABLE_MIRROR_TRADING and BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
        mirror_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY_2,
            api_secret=BYBIT_API_SECRET_2
        )
    
    # Load persistence
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        print(f"❌ Error loading persistence: {e}")
        return
    
    # Get bot_data
    bot_data = data.get('bot_data', {})
    if 'enhanced_tp_sl_monitors' not in bot_data:
        bot_data['enhanced_tp_sl_monitors'] = {}
    
    # Clear existing monitors to start fresh
    bot_data['enhanced_tp_sl_monitors'].clear()
    print("✅ Cleared existing monitors")
    
    # Get user data to find chat_id
    user_data = data.get('user_data', {})
    # Find first active chat_id
    chat_id = None
    for uid, udata in user_data.items():
        if isinstance(uid, int):
            chat_id = uid
            break
    
    if not chat_id:
        print("⚠️  No chat_id found in user_data, using default 1234567890")
        chat_id = 1234567890
    else:
        print(f"✅ Found chat_id: {chat_id}")
    
    # Check main account positions
    print("\n🔍 MAIN ACCOUNT:")
    try:
        response = main_client.get_positions(category="linear", settleCoin="USDT")
        if response.get("retCode") == 0:
            positions = response.get("result", {}).get("list", [])
            for pos in positions:
                if float(pos.get("size", 0)) > 0:
                    symbol = pos.get("symbol")
                    side = pos.get("side")
                    size = float(pos.get("size"))
                    entry_price = float(pos.get("avgPrice", 0))
                    
                    print(f"  • {symbol} {side}: {size} @ ${entry_price}")
                    
                    # Get orders for this position
                    orders_response = main_client.get_open_orders(
                        category="linear",
                        symbol=symbol,
                        settleCoin="USDT"
                    )
                    
                    tp_orders = {}
                    sl_order = None
                    limit_orders = []
                    
                    if orders_response.get("retCode") == 0:
                        orders = orders_response.get("result", {}).get("list", [])
                        for order in orders:
                            if order.get("reduceOnly"):
                                if order.get("orderType") == "Limit" and order.get("side") != side:
                                    # TP order
                                    tp_orders[order["orderId"]] = {
                                        "order_id": order["orderId"],
                                        "price": float(order["price"]),
                                        "qty": float(order["qty"]),
                                        "status": "ACTIVE"
                                    }
                                elif order.get("orderType") == "Market" and order.get("side") != side:
                                    # SL order
                                    sl_order = {
                                        "order_id": order["orderId"],
                                        "price": float(order.get("triggerPrice", 0)),
                                        "qty": float(order["qty"]),
                                        "status": "ACTIVE"
                                    }
                            else:
                                # Entry limit order
                                limit_orders.append({
                                    "order_id": order["orderId"],
                                    "price": float(order["price"]),
                                    "qty": float(order["qty"]),
                                    "status": "ACTIVE"
                                })
                    
                    # Create monitor
                    monitor_key = f"{symbol}_{side}_main"
                    monitor_data = {
                        "symbol": symbol,
                        "side": side,
                        "position_size": size,
                        "remaining_size": size,
                        "entry_price": entry_price,
                        "tp_orders": tp_orders,  # Already dict format
                        "sl_order": sl_order,
                        "limit_orders": limit_orders,
                        "chat_id": chat_id,
                        "approach": "conservative",
                        "account_type": "main",
                        "phase": "PROFIT_TAKING" if len(limit_orders) == 0 else "BUILDING",
                        "created_at": pos.get("createdTime"),
                        "tp1_hit": False,
                        "monitoring_active": True
                    }
                    
                    bot_data['enhanced_tp_sl_monitors'][monitor_key] = monitor_data
                    print(f"    ✅ Created main monitor: {monitor_key}")
                    print(f"       TP orders: {len(tp_orders)}, SL: {'Yes' if sl_order else 'No'}, Limits: {len(limit_orders)}")
    except Exception as e:
        print(f"❌ Error checking main positions: {e}")
    
    # Check mirror account positions
    if mirror_client:
        print("\n🔍 MIRROR ACCOUNT:")
        try:
            response = mirror_client.get_positions(category="linear", settleCoin="USDT")
            if response.get("retCode") == 0:
                positions = response.get("result", {}).get("list", [])
                for pos in positions:
                    if float(pos.get("size", 0)) > 0:
                        symbol = pos.get("symbol")
                        side = pos.get("side")
                        size = float(pos.get("size"))
                        entry_price = float(pos.get("avgPrice", 0))
                        
                        print(f"  • {symbol} {side}: {size} @ ${entry_price}")
                        
                        # Get orders for this position
                        orders_response = mirror_client.get_open_orders(
                            category="linear",
                            symbol=symbol,
                            settleCoin="USDT"
                        )
                        
                        tp_orders = {}
                        sl_order = None
                        limit_orders = []
                        
                        if orders_response.get("retCode") == 0:
                            orders = orders_response.get("result", {}).get("list", [])
                            for order in orders:
                                if order.get("reduceOnly"):
                                    if order.get("orderType") == "Limit" and order.get("side") != side:
                                        # TP order
                                        tp_orders[order["orderId"]] = {
                                            "order_id": order["orderId"],
                                            "price": float(order["price"]),
                                            "qty": float(order["qty"]),
                                            "status": "ACTIVE"
                                        }
                                    elif order.get("orderType") == "Market" and order.get("side") != side:
                                        # SL order
                                        sl_order = {
                                            "order_id": order["orderId"],
                                            "price": float(order.get("triggerPrice", 0)),
                                            "qty": float(order["qty"]),
                                            "status": "ACTIVE"
                                        }
                                else:
                                    # Entry limit order
                                    limit_orders.append({
                                        "order_id": order["orderId"],
                                        "price": float(order["price"]),
                                        "qty": float(order["qty"]),
                                        "status": "ACTIVE"
                                    })
                        
                        # Create monitor
                        monitor_key = f"{symbol}_{side}_mirror"
                        monitor_data = {
                            "symbol": symbol,
                            "side": side,
                            "position_size": size,
                            "remaining_size": size,
                            "entry_price": entry_price,
                            "tp_orders": tp_orders,  # Already dict format
                            "sl_order": sl_order,
                            "limit_orders": limit_orders,
                            "chat_id": chat_id,
                            "approach": "conservative",
                            "account_type": "mirror",
                            "phase": "PROFIT_TAKING" if len(limit_orders) == 0 else "BUILDING",
                            "created_at": pos.get("createdTime"),
                            "tp1_hit": False,
                            "monitoring_active": True
                        }
                        
                        bot_data['enhanced_tp_sl_monitors'][monitor_key] = monitor_data
                        print(f"    ✅ Created mirror monitor: {monitor_key}")
                        print(f"       TP orders: {len(tp_orders)}, SL: {'Yes' if sl_order else 'No'}, Limits: {len(limit_orders)}")
        except Exception as e:
            print(f"❌ Error checking mirror positions: {e}")
    
    # Save persistence
    with open(pkl_path, 'wb') as f:
        pickle.dump(data, f)
    
    print(f"\n✅ Monitor recreation complete!")
    print(f"   Total monitors: {len(bot_data['enhanced_tp_sl_monitors'])}")
    
    # Trigger monitor reload in the bot
    print("\n🔄 To activate these monitors, restart the bot or wait for next sync cycle")

if __name__ == "__main__":
    asyncio.run(recreate_monitors())