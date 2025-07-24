#!/usr/bin/env python3
"""
Save current state of all positions and their orders.
This creates a backup of all position data before restarting the bot.
"""
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List
from decimal import Decimal

from clients.bybit_helpers import get_all_positions, get_open_orders
from config.settings import USE_TESTNET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def save_position_state():
    """Save complete state of all positions and orders."""
    try:
        logger.info("📊 Saving current position state...")
        
        # Get all positions
        positions = await get_all_positions()
        active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
        
        logger.info(f"Found {len(active_positions)} active positions")
        
        # Get all open orders
        all_orders = await get_open_orders()
        logger.info(f"Found {len(all_orders)} open orders")
        
        # Group orders by symbol
        orders_by_symbol = {}
        for order in all_orders:
            symbol = order.get('symbol', '')
            if symbol:
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)
        
        # Build position state data
        position_states = []
        
        for position in active_positions:
            symbol = position['symbol']
            side = position['side']
            size = float(position['size'])
            avg_price = float(position['avgPrice'])
            
            # Get orders for this position
            symbol_orders = orders_by_symbol.get(symbol, [])
            
            # Categorize orders
            tp_orders = []
            sl_orders = []
            limit_orders = []
            
            for order in symbol_orders:
                order_type = order.get('orderType')
                reduce_only = order.get('reduceOnly', False)
                trigger_price = float(order.get('triggerPrice', 0))
                
                if order_type == 'Limit' and not reduce_only:
                    # Limit entry order
                    limit_orders.append({
                        'orderId': order['orderId'],
                        'price': order.get('price'),
                        'qty': order.get('qty'),
                        'orderLinkId': order.get('orderLinkId', '')
                    })
                elif reduce_only and trigger_price > 0:
                    # TP or SL order
                    if side == 'Buy':
                        if trigger_price > avg_price:
                            tp_orders.append({
                                'orderId': order['orderId'],
                                'triggerPrice': order.get('triggerPrice'),
                                'qty': order.get('qty'),
                                'orderLinkId': order.get('orderLinkId', '')
                            })
                        else:
                            sl_orders.append({
                                'orderId': order['orderId'],
                                'triggerPrice': order.get('triggerPrice'),
                                'qty': order.get('qty'),
                                'orderLinkId': order.get('orderLinkId', '')
                            })
                    else:  # Sell
                        if trigger_price < avg_price:
                            tp_orders.append({
                                'orderId': order['orderId'],
                                'triggerPrice': order.get('triggerPrice'),
                                'qty': order.get('qty'),
                                'orderLinkId': order.get('orderLinkId', '')
                            })
                        else:
                            sl_orders.append({
                                'orderId': order['orderId'],
                                'triggerPrice': order.get('triggerPrice'),
                                'qty': order.get('qty'),
                                'orderLinkId': order.get('orderLinkId', '')
                            })
            
            # Sort TP orders by price
            if side == 'Buy':
                tp_orders.sort(key=lambda x: float(x['triggerPrice']))
            else:
                tp_orders.sort(key=lambda x: float(x['triggerPrice']), reverse=True)
            
            # Detect trading approach
            approach = "unknown"
            if len(tp_orders) == 4:
                approach = "conservative"
            elif len(tp_orders) == 1:
                approach = "fast"
            
            position_state = {
                'symbol': symbol,
                'side': side,
                'size': str(size),
                'avgPrice': str(avg_price),
                'unrealisedPnl': position.get('unrealisedPnl', '0'),
                'markPrice': position.get('markPrice', '0'),
                'positionIdx': position.get('positionIdx', 0),
                'approach': approach,
                'tp_orders': tp_orders,
                'sl_orders': sl_orders,
                'limit_orders': limit_orders,
                'tp_count': len(tp_orders),
                'sl_count': len(sl_orders),
                'limit_count': len(limit_orders),
                'missing_sl': len(sl_orders) == 0
            }
            
            position_states.append(position_state)
        
        # Save to file
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'testnet': USE_TESTNET,
            'position_count': len(position_states),
            'total_orders': len(all_orders),
            'positions': position_states
        }
        
        filename = f"position_state_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        logger.info(f"✅ Position state saved to {filename}")
        
        # Print summary
        logger.info("\n📊 Position Summary:")
        for pos in position_states:
            logger.info(f"\n{pos['symbol']} {pos['side']} ({pos['approach']})")
            logger.info(f"  Size: {pos['size']}, Avg Price: {pos['avgPrice']}")
            logger.info(f"  TP Orders: {pos['tp_count']}, SL Orders: {pos['sl_count']}")
            if pos['missing_sl']:
                logger.warning(f"  ⚠️ MISSING STOP LOSS!")
            if pos['limit_orders']:
                logger.info(f"  Limit Orders: {pos['limit_count']}")
        
        # Check for issues
        issues = []
        for pos in position_states:
            if pos['missing_sl']:
                issues.append(f"{pos['symbol']} missing SL")
            if pos['approach'] == 'conservative' and pos['tp_count'] != 4:
                issues.append(f"{pos['symbol']} conservative with {pos['tp_count']} TPs")
            if pos['approach'] == 'fast' and pos['tp_count'] != 1:
                issues.append(f"{pos['symbol']} fast with {pos['tp_count']} TPs")
        
        if issues:
            logger.warning(f"\n⚠️ Issues found:")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("\n✅ All positions have proper order structure")
        
        return position_states
        
    except Exception as e:
        logger.error(f"Error saving position state: {e}")
        return []

async def main():
    """Main entry point."""
    await save_position_state()

if __name__ == "__main__":
    asyncio.run(main())