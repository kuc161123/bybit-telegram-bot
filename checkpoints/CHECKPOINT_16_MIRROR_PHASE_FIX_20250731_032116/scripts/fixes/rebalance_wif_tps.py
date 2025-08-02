#!/usr/bin/env python3
"""
Rebalance WIFUSDT TP orders after limit fill
This script fixes the issue where limit fills didn't trigger TP rebalancing
"""
import asyncio
import logging
from decimal import Decimal
from pybit.unified_trading import HTTP
import pickle
import sys
import os
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import (
    USE_TESTNET, BYBIT_API_KEY, BYBIT_API_SECRET, 
    BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)
from clients.bybit_helpers import cancel_order_with_retry, place_order_with_retry
from utils.helpers import value_adjusted_to_step
from utils.order_identifier import generate_order_link_id, ORDER_TYPE_TP
from telegram import Bot

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def rebalance_wif_tps():
    """Rebalance WIFUSDT TP orders based on current position size"""
    
    # Initialize clients
    main_client = HTTP(
        api_key=BYBIT_API_KEY,
        api_secret=BYBIT_API_SECRET,
        testnet=USE_TESTNET
    )
    
    mirror_client = HTTP(
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2,
        testnet=USE_TESTNET
    )
    
    logger.info("=" * 80)
    logger.info("WIFUSDT TP REBALANCING SCRIPT")
    logger.info("=" * 80)
    
    # Load pickle data
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    with open(pickle_file, 'rb') as f:
        data = pickle.load(f)
    
    # Get chat ID from pickle
    chat_id = None
    if 'enhanced_tp_sl_monitors' in data:
        wif_main = data['enhanced_tp_sl_monitors'].get('WIFUSDT_Sell_main', {})
        chat_id = wif_main.get('chat_id')
    
    if not chat_id:
        logger.warning("No chat ID found for WIFUSDT position")
        chat_id = "5634913742"  # Default chat ID
    
    results = {"main": None, "mirror": None}
    
    # Process both accounts
    for account_name, client in [("main", main_client), ("mirror", mirror_client)]:
        logger.info(f"\n{account_name.upper()} ACCOUNT:")
        logger.info("-" * 40)
        
        try:
            # Get current position
            pos_response = client.get_positions(
                category="linear",
                symbol="WIFUSDT"
            )
            
            if pos_response.get("retCode") != 0:
                logger.error(f"Failed to get position: {pos_response}")
                continue
                
            positions = pos_response.get("result", {}).get("list", [])
            if not positions:
                logger.warning("No WIFUSDT position found")
                continue
                
            position = positions[0]
            current_size = Decimal(position.get("size", 0))
            side = position.get("side", "")
            
            logger.info(f"Current position: {side} {current_size} WIFUSDT")
            
            if current_size == 0:
                logger.warning("Position size is 0, skipping")
                continue
            
            # Get open orders
            orders_response = client.get_open_orders(
                category="linear",
                symbol="WIFUSDT"
            )
            
            if orders_response.get("retCode") != 0:
                logger.error(f"Failed to get orders: {orders_response}")
                continue
                
            orders = orders_response.get("result", {}).get("list", [])
            
            # Find existing TP orders
            tp_orders = []
            for order in orders:
                link_id = order.get("orderLinkId", "")
                stop_type = order.get("stopOrderType", "")
                if "TP" in link_id or stop_type == "TakeProfit":
                    tp_orders.append({
                        "order_id": order.get("orderId"),
                        "link_id": link_id,
                        "price": Decimal(order.get("price", 0) or order.get("triggerPrice", 0)),
                        "quantity": Decimal(order.get("qty", 0)),
                        "side": order.get("side")
                    })
            
            # Sort TP orders by price
            if side == "Buy":
                tp_orders.sort(key=lambda x: x["price"])  # Ascending for Buy
            else:
                tp_orders.sort(key=lambda x: x["price"], reverse=True)  # Descending for Sell
            
            logger.info(f"Found {len(tp_orders)} TP orders")
            
            # Calculate new TP quantities based on current position size
            # Conservative approach: 85%, 5%, 5%, 5%
            tp_percentages = [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")]
            
            # Get instrument info for quantity step
            instrument_info = client.get_instruments_info(
                category="linear",
                symbol="WIFUSDT"
            )
            
            qty_step = Decimal("1")
            if instrument_info.get("retCode") == 0:
                instruments = instrument_info.get("result", {}).get("list", [])
                if instruments:
                    qty_step = Decimal(instruments[0].get("lotSizeFilter", {}).get("qtyStep", "1"))
            
            # Cancel existing TP orders
            logger.info("\nCancelling existing TP orders...")
            for tp in tp_orders:
                try:
                    cancel_result = await cancel_order_with_retry(
                        client, tp["order_id"]
                    )
                    if cancel_result:
                        logger.info(f"✅ Cancelled TP order: {tp['order_id']}")
                    else:
                        logger.error(f"❌ Failed to cancel TP order: {tp['order_id']}")
                except Exception as e:
                    logger.error(f"Error cancelling order: {e}")
            
            # Place new TP orders with correct quantities
            logger.info("\nPlacing new TP orders with correct quantities...")
            placed_orders = []
            
            for i, (tp, percentage) in enumerate(zip(tp_orders[:4], tp_percentages), 1):
                new_quantity = value_adjusted_to_step(current_size * percentage / 100, qty_step)
                
                # Ensure last TP covers any remaining quantity
                if i == 4:
                    total_placed = sum(Decimal(o["quantity"]) for o in placed_orders)
                    new_quantity = current_size - total_placed
                    new_quantity = value_adjusted_to_step(new_quantity, qty_step)
                
                if new_quantity <= 0:
                    logger.warning(f"TP{i} quantity is 0, skipping")
                    continue
                
                order_link_id = generate_order_link_id(
                    ORDER_TYPE_TP, "WIFUSDT", i, account_name
                )
                
                try:
                    result = await place_order_with_retry(
                        symbol="WIFUSDT",
                        side="Buy" if side == "Sell" else "Sell",
                        order_type="Limit",
                        qty=str(new_quantity),
                        price=str(tp["price"]),
                        reduce_only=True,
                        order_link_id=order_link_id,
                        client=client
                    )
                    if result:
                        logger.info(f"✅ Placed TP{i}: {new_quantity} @ {tp['price']} ({percentage}%)")
                        placed_orders.append({"quantity": new_quantity, "tp_number": i})
                    else:
                        logger.error(f"❌ Failed to place TP{i}")
                except Exception as e:
                    logger.error(f"Error placing TP{i}: {e}")
            
            results[account_name] = {
                "success": len(placed_orders) > 0,
                "position_size": current_size,
                "orders_placed": len(placed_orders)
            }
            
        except Exception as e:
            logger.error(f"Error processing {account_name} account: {e}")
            results[account_name] = {"success": False, "error": str(e)}
    
    # Send alert about the rebalancing
    alert_message = (
        "🔧 WIFUSDT TP Orders Rebalanced\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )
    
    if results["main"] and results["main"].get("success"):
        alert_message += (
            f"✅ Main Account:\n"
            f"   Position: {results['main']['position_size']} WIFUSDT\n"
            f"   TPs Placed: {results['main']['orders_placed']}\n\n"
        )
    else:
        alert_message += "❌ Main Account: Failed\n\n"
    
    if results["mirror"] and results["mirror"].get("success"):
        alert_message += (
            f"✅ Mirror Account:\n"
            f"   Position: {results['mirror']['position_size']} WIFUSDT\n"
            f"   TPs Placed: {results['mirror']['orders_placed']}\n\n"
        )
    else:
        alert_message += "❌ Mirror Account: Failed\n\n"
    
    alert_message += (
        "📝 Note: Limit orders filled but alert wasn't sent.\n"
        "This manual rebalancing ensures TPs match current position size."
    )
    
    # Send the alert using telegram bot directly
    try:
        from config.settings import TELEGRAM_TOKEN
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=chat_id, text=alert_message, parse_mode='HTML')
        logger.info("✅ Alert sent successfully")
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
    
    # Update pickle file to mark limit fill as processed
    try:
        if 'enhanced_tp_sl_monitors' in data:
            for key in ['WIFUSDT_Sell_main', 'WIFUSDT_Sell_mirror']:
                if key in data['enhanced_tp_sl_monitors']:
                    # Add a flag to indicate manual rebalancing was done
                    data['enhanced_tp_sl_monitors'][key]['manual_rebalance_done'] = True
                    data['enhanced_tp_sl_monitors'][key]['manual_rebalance_time'] = int(time.time())  # Current timestamp
        
        # Save updated pickle
        with open(pickle_file, 'wb') as f:
            pickle.dump(data, f)
        logger.info("✅ Updated pickle file with rebalancing flag")
    except Exception as e:
        logger.error(f"Failed to update pickle file: {e}")
    
    logger.info("\n" + "=" * 80)
    logger.info("REBALANCING COMPLETE")
    logger.info("=" * 80)

if __name__ == "__main__":
    asyncio.run(rebalance_wif_tps())