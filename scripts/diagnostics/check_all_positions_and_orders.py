#!/usr/bin/env python3
"""
Check all positions and their orders
"""

import logging
from pybit.unified_trading import HTTP
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET,
    ENABLE_MIRROR_TRADING, BYBIT_API_KEY_2, BYBIT_API_SECRET_2
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_all_positions_and_orders():
    """Check all positions and orders"""
    try:
        # Check MAIN account
        logger.info("=== MAIN ACCOUNT ===")
        main_client = HTTP(
            testnet=USE_TESTNET,
            api_key=BYBIT_API_KEY,
            api_secret=BYBIT_API_SECRET
        )
        
        # Get positions
        pos_response = main_client.get_positions(category="linear", settleCoin="USDT")
        if pos_response['retCode'] == 0:
            positions = [p for p in pos_response['result']['list'] if float(p['size']) > 0]
            logger.info(f"\nPositions: {len(positions)}")
            for pos in positions:
                logger.info(f"  - {pos['symbol']} {pos['side']}: {pos['size']} @ {pos['avgPrice']}")
        
        # Get orders
        order_response = main_client.get_open_orders(category="linear", settleCoin="USDT")
        if order_response['retCode'] == 0:
            orders = order_response['result']['list']
            logger.info(f"\nTotal Orders: {len(orders)}")
            
            # Group by symbol
            by_symbol = {}
            for order in orders:
                symbol = order['symbol']
                if symbol not in by_symbol:
                    by_symbol[symbol] = []
                by_symbol[symbol].append(order)
            
            for symbol, symbol_orders in by_symbol.items():
                logger.info(f"\n{symbol}:")
                for order in symbol_orders:
                    order_type = order['orderType']
                    side = order['side']
                    reduce_only = order.get('reduceOnly', False)
                    price = order['price']
                    qty = order['qty']
                    order_id = order['orderId']
                    
                    if order_type == 'Limit' and not reduce_only:
                        logger.info(f"  📥 LIMIT ENTRY: {side} {qty} @ {price} [{order_id[:8]}...]")
                    elif order_type == 'Limit' and reduce_only:
                        if side != order.get('positionSide', side):
                            logger.info(f"  🎯 TP: {qty} @ {price} [{order_id[:8]}...]")
                        else:
                            logger.info(f"  🛡️ SL: {qty} @ {price} [{order_id[:8]}...]")
                    else:
                        logger.info(f"  ❓ {order_type}: {side} {qty} @ {price} [{order_id[:8]}...]")
        
        # Check MIRROR account
        if ENABLE_MIRROR_TRADING:
            logger.info("\n\n=== MIRROR ACCOUNT ===")
            mirror_client = HTTP(
                testnet=USE_TESTNET,
                api_key=BYBIT_API_KEY_2,
                api_secret=BYBIT_API_SECRET_2
            )
            
            # Get positions
            pos_response = mirror_client.get_positions(category="linear", settleCoin="USDT")
            if pos_response['retCode'] == 0:
                positions = [p for p in pos_response['result']['list'] if float(p['size']) > 0]
                logger.info(f"\nPositions: {len(positions)}")
                for pos in positions:
                    logger.info(f"  - {pos['symbol']} {pos['side']}: {pos['size']} @ {pos['avgPrice']}")
            
            # Get orders
            order_response = mirror_client.get_open_orders(category="linear", settleCoin="USDT")
            if order_response['retCode'] == 0:
                orders = order_response['result']['list']
                logger.info(f"\nTotal Orders: {len(orders)}")
                
                # Group by symbol
                by_symbol = {}
                for order in orders:
                    symbol = order['symbol']
                    if symbol not in by_symbol:
                        by_symbol[symbol] = []
                    by_symbol[symbol].append(order)
                
                for symbol, symbol_orders in by_symbol.items():
                    logger.info(f"\n{symbol}:")
                    for order in symbol_orders:
                        order_type = order['orderType']
                        side = order['side']
                        reduce_only = order.get('reduceOnly', False)
                        price = order['price']
                        qty = order['qty']
                        order_id = order['orderId']
                        
                        if order_type == 'Limit' and not reduce_only:
                            logger.info(f"  📥 LIMIT ENTRY: {side} {qty} @ {price} [{order_id[:8]}...]")
                        elif order_type == 'Limit' and reduce_only:
                            if side != order.get('positionSide', side):
                                logger.info(f"  🎯 TP: {qty} @ {price} [{order_id[:8]}...]")
                            else:
                                logger.info(f"  🛡️ SL: {qty} @ {price} [{order_id[:8]}...]")
                        else:
                            logger.info(f"  ❓ {order_type}: {side} {qty} @ {price} [{order_id[:8]}...]")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_all_positions_and_orders()