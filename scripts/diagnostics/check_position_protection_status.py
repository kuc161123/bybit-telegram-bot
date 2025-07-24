#!/usr/bin/env python3
"""
Check if all positions are properly protected by Enhanced TP/SL monitors
"""

import asyncio
import logging
import pickle
from decimal import Decimal
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2 as mirror_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def get_all_positions(client, account_name):
    """Get all open positions from an account"""
    try:
        response = await asyncio.to_thread(
            client.get_positions,
            category="linear",
            settleCoin="USDT"
        )
        
        if response['retCode'] != 0:
            logger.error(f"Failed to get positions: {response.get('retMsg', '')}")
            return []
        
        positions = []
        for pos in response['result']['list']:
            if float(pos['size']) > 0:
                positions.append({
                    'symbol': pos['symbol'],
                    'side': pos['side'],
                    'size': float(pos['size']),
                    'avgPrice': float(pos['avgPrice']),
                    'unrealisedPnl': float(pos.get('unrealisedPnl', 0)),
                    'account': account_name
                })
        
        return positions
        
    except Exception as e:
        logger.error(f"Error getting positions for {account_name}: {e}")
        return []

async def check_position_orders(client, symbol, side):
    """Check if position has TP/SL orders"""
    try:
        response = await asyncio.to_thread(
            client.get_open_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            return {'tp_count': 0, 'sl_count': 0}
        
        tp_count = 0
        sl_count = 0
        
        for order in response['result']['list']:
            if order.get('reduceOnly'):
                # It's a TP or SL order
                if order.get('orderType') in ['Limit', 'Market']:
                    # Check if it's TP or SL based on side
                    if ((side == 'Buy' and order['side'] == 'Sell') or 
                        (side == 'Sell' and order['side'] == 'Buy')):
                        tp_count += 1
                elif order.get('orderType') in ['StopLimit', 'StopMarket']:
                    sl_count += 1
        
        return {'tp_count': tp_count, 'sl_count': sl_count}
        
    except Exception as e:
        logger.error(f"Error checking orders: {e}")
        return {'tp_count': 0, 'sl_count': 0}

async def check_all_position_protection():
    """Check protection status for all positions"""
    
    # Load monitors from pickle
    pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    try:
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading pickle file: {e}")
        return
    
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🛡️ POSITION PROTECTION STATUS CHECK")
    logger.info(f"{'='*60}")
    
    # Get all positions from both accounts
    main_positions = await get_all_positions(bybit_client, "Main")
    mirror_positions = await get_all_positions(mirror_client, "Mirror")
    
    all_positions = main_positions + mirror_positions
    
    logger.info(f"\n📊 Found {len(all_positions)} total positions:")
    logger.info(f"   Main Account: {len(main_positions)}")
    logger.info(f"   Mirror Account: {len(mirror_positions)}")
    
    # Check each position
    unprotected_positions = []
    partially_protected = []
    fully_protected = []
    
    for pos in all_positions:
        symbol = pos['symbol']
        side = pos['side']
        account = pos['account']
        
        # Check if monitor exists
        if account == "Main":
            monitor_key = f"{symbol}_{side}"
        else:
            monitor_key = f"{symbol}_{side}_mirror"
        
        has_monitor = monitor_key in enhanced_monitors
        
        # Check orders
        client = bybit_client if account == "Main" else mirror_client
        order_status = await check_position_orders(client, symbol, side)
        
        # Determine protection status
        protection_status = "❌ UNPROTECTED"
        status_details = []
        
        if not has_monitor:
            status_details.append("No monitor")
            unprotected_positions.append(pos)
        
        if order_status['tp_count'] == 0:
            status_details.append("No TP orders")
            if has_monitor:
                partially_protected.append(pos)
            else:
                unprotected_positions.append(pos)
        elif order_status['tp_count'] < 4:
            status_details.append(f"Only {order_status['tp_count']} TP orders (expected 4)")
            partially_protected.append(pos)
        
        if order_status['sl_count'] == 0:
            status_details.append("No SL order")
            if has_monitor and order_status['tp_count'] > 0:
                partially_protected.append(pos)
        
        # Determine overall status
        if has_monitor and order_status['tp_count'] >= 4 and order_status['sl_count'] > 0:
            protection_status = "✅ FULLY PROTECTED"
            fully_protected.append(pos)
        elif has_monitor and (order_status['tp_count'] > 0 or order_status['sl_count'] > 0):
            protection_status = "⚠️ PARTIALLY PROTECTED"
        
        # Log position status
        logger.info(f"\n{protection_status} {symbol} {side} ({account}):")
        logger.info(f"   Size: {pos['size']}")
        logger.info(f"   Entry: ${pos['avgPrice']}")
        logger.info(f"   Monitor: {'✅ Yes' if has_monitor else '❌ No'}")
        logger.info(f"   TP Orders: {order_status['tp_count']}")
        logger.info(f"   SL Orders: {order_status['sl_count']}")
        
        if status_details:
            logger.info(f"   Issues: {', '.join(status_details)}")
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 PROTECTION SUMMARY")
    logger.info(f"{'='*60}")
    
    # Remove duplicates from lists
    unprotected_unique = []
    partially_unique = []
    seen = set()
    
    for pos in unprotected_positions:
        key = f"{pos['symbol']}_{pos['side']}_{pos['account']}"
        if key not in seen:
            seen.add(key)
            unprotected_unique.append(pos)
    
    seen = set()
    for pos in partially_protected:
        key = f"{pos['symbol']}_{pos['side']}_{pos['account']}"
        if key not in seen:
            seen.add(key)
            partially_unique.append(pos)
    
    fully_protected_count = len(set(f"{p['symbol']}_{p['side']}_{p['account']}" for p in fully_protected))
    logger.info(f"\n✅ Fully Protected: {fully_protected_count}")
    logger.info(f"⚠️  Partially Protected: {len(partially_unique)}")
    logger.info(f"❌ Unprotected: {len(unprotected_unique)}")
    
    if unprotected_unique:
        logger.error(f"\n❌ UNPROTECTED POSITIONS:")
        for pos in unprotected_unique:
            logger.error(f"   {pos['symbol']} {pos['side']} ({pos['account']})")
    
    if partially_unique:
        logger.warning(f"\n⚠️ PARTIALLY PROTECTED POSITIONS:")
        for pos in partially_unique:
            logger.warning(f"   {pos['symbol']} {pos['side']} ({pos['account']})")
    
    # Final verdict
    logger.info(f"\n🎯 FINAL VERDICT:")
    if not unprotected_unique and not partially_unique:
        logger.info(f"   ✅ ALL POSITIONS ARE FULLY PROTECTED!")
    else:
        total_issues = len(unprotected_unique) + len(partially_unique)
        logger.warning(f"   ⚠️ {total_issues} positions need attention")

async def main():
    """Main execution"""
    await check_all_position_protection()

if __name__ == "__main__":
    asyncio.run(main())