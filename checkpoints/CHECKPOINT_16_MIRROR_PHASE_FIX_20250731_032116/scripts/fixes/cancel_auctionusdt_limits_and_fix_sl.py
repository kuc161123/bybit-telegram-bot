#!/usr/bin/env python3
"""
Cancel limit entry orders for AUCTIONUSDT and fix SL quantity
"""
import asyncio
import sys
import os
from decimal import Decimal
import logging

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def cancel_limit_orders_and_fix_sl():
    """Cancel limit orders and fix SL for AUCTIONUSDT"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Import after env vars are loaded
        from clients.bybit_client import create_bybit_client
        from execution.mirror_trader import bybit_client_2
        
        logger.info("🎯 CANCELLING AUCTIONUSDT LIMIT ORDERS AND FIXING SL")
        logger.info("=" * 60)
        
        bybit_client = create_bybit_client()
        
        # Process main account
        logger.info("\n📈 MAIN ACCOUNT:")
        
        # Get open orders
        orders = bybit_client.get_open_orders(
            category="linear",
            symbol="AUCTIONUSDT"
        )
        
        if orders['retCode'] == 0:
            order_list = orders['result']['list']
            limit_orders_to_cancel = []
            sl_order = None
            
            for order in order_list:
                # Check if it's a limit entry order (not reduce only)
                if (order.get('orderType') == 'Limit' and 
                    not order.get('reduceOnly') and
                    order.get('side') == 'Buy'):
                    limit_orders_to_cancel.append(order)
                # Check if it's the SL order
                elif (order.get('orderType') == 'Market' and 
                      order.get('stopOrderType') == 'Stop' and
                      order.get('reduceOnly')):
                    sl_order = order
            
            # Cancel limit orders
            for order in limit_orders_to_cancel:
                order_id = order.get('orderId')
                logger.info(f"  Cancelling limit order: {order_id} (qty: {order.get('qty')})")
                try:
                    cancel_result = bybit_client.cancel_order(
                        category="linear",
                        symbol="AUCTIONUSDT",
                        orderId=order_id
                    )
                    if cancel_result['retCode'] == 0:
                        logger.info(f"  ✅ Cancelled order {order_id}")
                    else:
                        logger.error(f"  ❌ Failed to cancel: {cancel_result}")
                except Exception as e:
                    logger.error(f"  ❌ Error cancelling order: {e}")
            
            # Get current position
            positions = bybit_client.get_positions(
                category="linear",
                symbol="AUCTIONUSDT"
            )
            
            current_position_size = Decimal("0")
            if positions['retCode'] == 0:
                for pos in positions['result']['list']:
                    if float(pos.get('size', 0)) > 0 and pos.get('side') == 'Buy':
                        current_position_size = Decimal(str(pos.get('size')))
                        logger.info(f"\n  Current position size: {current_position_size}")
                        break
            
            # Fix SL quantity if needed
            if sl_order and current_position_size > 0:
                sl_qty = Decimal(str(sl_order.get('qty', '0')))
                if sl_qty != current_position_size:
                    logger.info(f"  SL order quantity mismatch: {sl_qty} vs position {current_position_size}")
                    logger.info(f"  Amending SL order to match position size...")
                    
                    try:
                        # Cancel old SL
                        cancel_result = bybit_client.cancel_order(
                            category="linear",
                            symbol="AUCTIONUSDT",
                            orderId=sl_order['orderId']
                        )
                        
                        if cancel_result['retCode'] == 0:
                            logger.info("  ✅ Cancelled old SL order")
                            
                            # Place new SL with correct quantity
                            sl_price = sl_order.get('triggerPrice')
                            new_sl_result = bybit_client.place_order(
                                category="linear",
                                symbol="AUCTIONUSDT",
                                side="Sell",
                                orderType="Market",
                                qty=str(current_position_size),
                                stopOrderType="Stop",
                                triggerPrice=sl_price,
                                reduceOnly=True,
                                orderLinkId=f"BOT_FIXED_SL_{int(asyncio.get_event_loop().time())}"
                            )
                            
                            if new_sl_result['retCode'] == 0:
                                logger.info(f"  ✅ Placed new SL with qty: {current_position_size}")
                            else:
                                logger.error(f"  ❌ Failed to place new SL: {new_sl_result}")
                    except Exception as e:
                        logger.error(f"  ❌ Error fixing SL: {e}")
                else:
                    logger.info(f"  ✅ SL quantity already correct: {sl_qty}")
        
        # Process mirror account
        if bybit_client_2:
            logger.info("\n\n🪞 MIRROR ACCOUNT:")
            
            # Get open orders
            orders = bybit_client_2.get_open_orders(
                category="linear",
                symbol="AUCTIONUSDT"
            )
            
            if orders['retCode'] == 0:
                order_list = orders['result']['list']
                limit_orders_to_cancel = []
                sl_order = None
                
                for order in order_list:
                    # Check if it's a limit entry order
                    if (order.get('orderType') == 'Limit' and 
                        not order.get('reduceOnly') and
                        order.get('side') == 'Buy'):
                        limit_orders_to_cancel.append(order)
                    # Check if it's the SL order
                    elif (order.get('orderType') == 'Market' and 
                          order.get('stopOrderType') == 'Stop' and
                          order.get('reduceOnly')):
                        sl_order = order
                
                # Cancel limit orders
                for order in limit_orders_to_cancel:
                    order_id = order.get('orderId')
                    logger.info(f"  Cancelling limit order: {order_id} (qty: {order.get('qty')})")
                    try:
                        cancel_result = bybit_client_2.cancel_order(
                            category="linear",
                            symbol="AUCTIONUSDT",
                            orderId=order_id
                        )
                        if cancel_result['retCode'] == 0:
                            logger.info(f"  ✅ Cancelled order {order_id}")
                        else:
                            logger.error(f"  ❌ Failed to cancel: {cancel_result}")
                    except Exception as e:
                        logger.error(f"  ❌ Error cancelling order: {e}")
                
                # Get current position
                positions = bybit_client_2.get_positions(
                    category="linear",
                    symbol="AUCTIONUSDT"
                )
                
                current_position_size = Decimal("0")
                if positions['retCode'] == 0:
                    for pos in positions['result']['list']:
                        if float(pos.get('size', 0)) > 0 and pos.get('side') == 'Buy':
                            current_position_size = Decimal(str(pos.get('size')))
                            logger.info(f"\n  Current position size: {current_position_size}")
                            break
                
                # Fix SL quantity if needed
                if sl_order and current_position_size > 0:
                    sl_qty = Decimal(str(sl_order.get('qty', '0')))
                    if sl_qty != current_position_size:
                        logger.info(f"  SL order quantity mismatch: {sl_qty} vs position {current_position_size}")
                        logger.info(f"  Amending SL order to match position size...")
                        
                        try:
                            # Cancel old SL
                            cancel_result = bybit_client_2.cancel_order(
                                category="linear",
                                symbol="AUCTIONUSDT",
                                orderId=sl_order['orderId']
                            )
                            
                            if cancel_result['retCode'] == 0:
                                logger.info("  ✅ Cancelled old SL order")
                                
                                # Place new SL with correct quantity
                                sl_price = sl_order.get('triggerPrice')
                                new_sl_result = bybit_client_2.place_order(
                                    category="linear",
                                    symbol="AUCTIONUSDT",
                                    side="Sell",
                                    orderType="Market",
                                    qty=str(current_position_size),
                                    stopOrderType="Stop",
                                    triggerPrice=sl_price,
                                    reduceOnly=True,
                                    orderLinkId=f"MIR_FIXED_SL_{int(asyncio.get_event_loop().time())}"
                                )
                                
                                if new_sl_result['retCode'] == 0:
                                    logger.info(f"  ✅ Placed new SL with qty: {current_position_size}")
                                else:
                                    logger.error(f"  ❌ Failed to place new SL: {new_sl_result}")
                        except Exception as e:
                            logger.error(f"  ❌ Error fixing SL: {e}")
                    else:
                        logger.info(f"  ✅ SL quantity already correct: {sl_qty}")
        
        # Update pickle file to mark limit orders as cancelled
        import pickle
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        enhanced_monitors = bot_data.get('enhanced_tp_sl_monitors', {})
        
        # Update AUCTIONUSDT monitors
        for key, monitor in enhanced_monitors.items():
            if 'AUCTIONUSDT' in key:
                monitor['limit_orders_cancelled'] = True
                if monitor.get('tp1_hit'):
                    monitor['phase'] = 'PROFIT_TAKING'
                logger.info(f"\n✅ Updated monitor {key}: limit_orders_cancelled=True")
        
        # Save back
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info("\n✅ AUCTIONUSDT CLEANUP COMPLETE")
        logger.info("=" * 60)
        logger.info("Summary:")
        logger.info("- Cancelled all limit entry orders")
        logger.info("- Fixed SL quantities to match current position sizes")
        logger.info("- Updated monitor data to reflect changes")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(cancel_limit_orders_and_fix_sl())