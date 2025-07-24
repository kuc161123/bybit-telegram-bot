#!/usr/bin/env python3
"""
Check approach type for all current positions
"""

import pickle
import logging
from datetime import datetime
import asyncio
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2 as mirror_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_position_orders(client, symbol: str, side: str, account_name: str):
    """Check orders for a specific position"""
    try:
        # Get orders
        response = await asyncio.to_thread(
            client.get_open_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            return None
            
        orders = response['result']['list']
        
        # Count order types
        tp_orders = []
        limit_orders = []
        
        for order in orders:
            if order.get('reduceOnly'):
                tp_orders.append(order)
            else:
                # Entry order
                limit_orders.append(order)
        
        return {
            'tp_count': len(tp_orders),
            'limit_count': len(limit_orders),
            'has_limit_orders': len(limit_orders) > 0
        }
        
    except Exception as e:
        logger.error(f"Error checking orders for {symbol}: {e}")
        return None

async def check_all_positions():
    """Check approach type for all positions"""
    
    # Load pickle file to get monitor data
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading pickle file: {e}")
        return
    
    # Get Enhanced TP/SL monitors
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 POSITION APPROACH ANALYSIS")
    logger.info(f"{'='*60}")
    
    # Analyze main account positions
    logger.info(f"\n🏦 MAIN ACCOUNT POSITIONS:")
    logger.info(f"{'='*60}")
    
    main_positions = []
    for key, monitor in enhanced_monitors.items():
        if not key.endswith('_mirror'):
            symbol = monitor.get('symbol')
            side = monitor.get('side')
            approach = monitor.get('approach', 'Unknown')
            phase = monitor.get('phase', 'Unknown')
            
            # Get order info from Bybit
            order_info = await check_position_orders(bybit_client, symbol, side, "Main")
            
            position_info = {
                'symbol': symbol,
                'side': side,
                'approach': approach,
                'phase': phase,
                'monitor_key': key,
                'order_info': order_info
            }
            main_positions.append(position_info)
            
            # Display info
            logger.info(f"\n📈 {symbol} {side}:")
            logger.info(f"   Approach: {approach.upper()}")
            logger.info(f"   Phase: {phase}")
            if order_info:
                logger.info(f"   TP Orders: {order_info['tp_count']}")
                logger.info(f"   Limit Entry Orders: {order_info['limit_count']}")
                
                # Analysis
                if approach == 'conservative' and order_info['has_limit_orders']:
                    logger.info(f"   ✅ Confirmed: Conservative with active limit orders")
                elif approach == 'conservative' and not order_info['has_limit_orders']:
                    logger.info(f"   ⚠️ Conservative but no limit orders (may be fully filled)")
                elif approach == 'fast' and order_info['has_limit_orders']:
                    logger.warning(f"   ❌ INCONSISTENT: Fast approach but has limit orders!")
                elif approach == 'fast':
                    logger.info(f"   ✅ Confirmed: Fast approach (no limit orders)")
    
    # Analyze mirror account positions
    logger.info(f"\n\n🏦 MIRROR ACCOUNT POSITIONS:")
    logger.info(f"{'='*60}")
    
    mirror_positions = []
    for key, monitor in enhanced_monitors.items():
        if key.endswith('_mirror'):
            symbol = monitor.get('symbol')
            side = monitor.get('side')
            approach = monitor.get('approach', 'Unknown')
            phase = monitor.get('phase', 'Unknown')
            
            # Get order info from Bybit
            order_info = await check_position_orders(mirror_client, symbol, side, "Mirror")
            
            position_info = {
                'symbol': symbol,
                'side': side,
                'approach': approach,
                'phase': phase,
                'monitor_key': key,
                'order_info': order_info
            }
            mirror_positions.append(position_info)
            
            # Display info
            logger.info(f"\n📉 {symbol} {side}:")
            logger.info(f"   Approach: {approach.upper()}")
            logger.info(f"   Phase: {phase}")
            if order_info:
                logger.info(f"   TP Orders: {order_info['tp_count']}")
                logger.info(f"   Limit Entry Orders: {order_info['limit_count']}")
                
                # Analysis
                if approach == 'conservative' and order_info['has_limit_orders']:
                    logger.info(f"   ✅ Confirmed: Conservative with active limit orders")
                elif approach == 'conservative' and not order_info['has_limit_orders']:
                    logger.info(f"   ⚠️ Conservative but no limit orders (may be fully filled)")
                elif approach == 'fast' and order_info['has_limit_orders']:
                    logger.warning(f"   ❌ INCONSISTENT: Fast approach but has limit orders!")
                elif approach == 'fast':
                    logger.info(f"   ✅ Confirmed: Fast approach (no limit orders)")
    
    # Summary
    logger.info(f"\n\n{'='*60}")
    logger.info(f"📊 SUMMARY")
    logger.info(f"{'='*60}")
    
    # Count approaches
    main_conservative = sum(1 for p in main_positions if p['approach'] == 'conservative')
    main_fast = sum(1 for p in main_positions if p['approach'] == 'fast')
    mirror_conservative = sum(1 for p in mirror_positions if p['approach'] == 'conservative')
    mirror_fast = sum(1 for p in mirror_positions if p['approach'] == 'fast')
    
    logger.info(f"\n🏦 Main Account:")
    logger.info(f"   Conservative: {main_conservative}")
    logger.info(f"   Fast: {main_fast}")
    logger.info(f"   Total: {len(main_positions)}")
    
    logger.info(f"\n🏦 Mirror Account:")
    logger.info(f"   Conservative: {mirror_conservative}")
    logger.info(f"   Fast: {mirror_fast}")
    logger.info(f"   Total: {len(mirror_positions)}")
    
    # Check if all are conservative
    total_positions = len(main_positions) + len(mirror_positions)
    total_conservative = main_conservative + mirror_conservative
    
    logger.info(f"\n🎯 FINAL VERDICT:")
    if total_conservative == total_positions:
        logger.info(f"   ✅ YES - ALL {total_positions} positions are CONSERVATIVE approach!")
    else:
        logger.info(f"   ❌ NO - Only {total_conservative}/{total_positions} positions are Conservative")
        logger.info(f"   Fast approach positions:")
        for p in main_positions + mirror_positions:
            if p['approach'] == 'fast':
                logger.info(f"      - {p['symbol']} {p['side']} ({'Mirror' if p['monitor_key'].endswith('_mirror') else 'Main'})")

async def main():
    """Main execution"""
    await check_all_positions()

if __name__ == "__main__":
    asyncio.run(main())