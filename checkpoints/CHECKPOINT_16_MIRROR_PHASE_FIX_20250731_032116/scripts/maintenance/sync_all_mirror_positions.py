#!/usr/bin/env python3
"""
Sync all mirror positions to ensure they have proper TP/SL orders
"""

import asyncio
import logging
from decimal import Decimal
from clients.bybit_client import bybit_client, get_mirror_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def sync_mirror_positions():
    """Ensure all mirror positions have proper TP/SL orders"""
    
    # Get mirror client
    mirror_client = get_mirror_client()
    if not mirror_client:
        logger.error("❌ Mirror trading not enabled")
        return
    
    logger.info("📊 Fetching mirror positions...")
    
    # Get all mirror positions
    try:
        response = await asyncio.to_thread(
            mirror_client.get_positions,
            category="linear",
            settleCoin="USDT"
        )
        positions = response.get('result', {}).get('list', [])
    except Exception as e:
        logger.error(f"Error getting mirror positions: {e}")
        return
    
    # Check each position
    missing_tp_sl = []
    
    for pos in positions:
        if float(pos['size']) > 0:
            symbol = pos['symbol']
            side = pos['side']
            size = float(pos['size'])
            avg_price = float(pos['avgPrice'])
            
            logger.info(f"\n🔍 Checking {symbol} {side}: {size} @ ${avg_price}")
            
            # Check for TP/SL orders
            try:
                orders_resp = await asyncio.to_thread(
                    mirror_client.get_open_orders,
                    category="linear",
                    symbol=symbol
                )
                orders = orders_resp.get('result', {}).get('list', [])
                
                # Count TP and SL orders
                tp_orders = [o for o in orders if o.get('reduceOnly') and 
                           ((side == 'Buy' and o['side'] == 'Sell' and float(o['price']) > avg_price) or
                            (side == 'Sell' and o['side'] == 'Buy' and float(o['price']) < avg_price))]
                
                sl_orders = [o for o in orders if o.get('reduceOnly') and 
                           ((side == 'Buy' and o['side'] == 'Sell' and float(o['price']) < avg_price) or
                            (side == 'Sell' and o['side'] == 'Buy' and float(o['price']) > avg_price))]
                
                logger.info(f"   TP orders: {len(tp_orders)}")
                logger.info(f"   SL orders: {len(sl_orders)}")
                
                if len(tp_orders) == 0 or len(sl_orders) == 0:
                    missing_tp_sl.append({
                        'symbol': symbol,
                        'side': side,
                        'size': size,
                        'avg_price': avg_price,
                        'has_tp': len(tp_orders) > 0,
                        'has_sl': len(sl_orders) > 0
                    })
                    logger.warning(f"   ⚠️ Missing {'TP' if len(tp_orders) == 0 else ''} {'SL' if len(sl_orders) == 0 else ''}")
                else:
                    logger.info(f"   ✅ Has both TP and SL orders")
                    
            except Exception as e:
                logger.error(f"   ❌ Error checking orders: {e}")
    
    # Summary
    logger.info(f"\n📊 Summary:")
    logger.info(f"   Total mirror positions: {len([p for p in positions if float(p['size']) > 0])}")
    logger.info(f"   Positions missing TP/SL: {len(missing_tp_sl)}")
    
    if missing_tp_sl:
        logger.info("\n❌ Positions needing TP/SL orders:")
        for pos in missing_tp_sl:
            logger.info(f"   {pos['symbol']} {pos['side']}: {pos['size']} @ ${pos['avg_price']}")
            logger.info(f"      Missing: {'TP ' if not pos['has_tp'] else ''}{'SL' if not pos['has_sl'] else ''}")
    
    return missing_tp_sl

async def main():
    """Main entry point"""
    missing = await sync_mirror_positions()
    
    if missing:
        print(f"\n⚠️ {len(missing)} mirror positions need TP/SL orders")
        print("These positions won't be properly monitored until orders are placed")
    else:
        print("\n✅ All mirror positions have proper TP/SL orders")

if __name__ == "__main__":
    asyncio.run(main())