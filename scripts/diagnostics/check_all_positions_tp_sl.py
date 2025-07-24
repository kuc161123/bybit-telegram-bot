#!/usr/bin/env python3
"""
Check all positions on main and mirror accounts for missing TP/SL orders
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from collections import defaultdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled

async def check_position_orders(account_name: str, client, position: Dict) -> Dict:
    """Check if a position has proper TP and SL orders"""
    symbol = position.get('symbol')
    side = position.get('side')
    size = float(position.get('size', 0))
    
    if size <= 0:
        return None
    
    # Get orders for this symbol
    if account_name == "MAIN":
        orders = await get_open_orders(symbol)
    else:
        response = client.get_open_orders(category="linear", symbol=symbol)
        orders = response.get('result', {}).get('list', []) if response.get('retCode') == 0 else []
    
    # Categorize orders
    tp_orders = []
    sl_orders = []
    entry_orders = []
    
    for order in orders:
        order_type = order.get('orderType', '')
        reduce_only = order.get('reduceOnly', False)
        order_link_id = order.get('orderLinkId', '')
        
        if reduce_only:
            if 'TP' in order_link_id or order_type == 'TakeProfit':
                tp_orders.append({
                    'orderId': order.get('orderId'),
                    'qty': order.get('qty'),
                    'price': order.get('price'),
                    'orderType': order_type,
                    'orderLinkId': order_link_id
                })
            elif 'SL' in order_link_id or order_type == 'StopLoss':
                sl_orders.append({
                    'orderId': order.get('orderId'),
                    'qty': order.get('qty'),
                    'triggerPrice': order.get('triggerPrice'),
                    'orderType': order_type,
                    'orderLinkId': order_link_id
                })
        else:
            entry_orders.append({
                'orderId': order.get('orderId'),
                'qty': order.get('qty'),
                'price': order.get('price'),
                'orderType': order_type
            })
    
    # Calculate TP coverage
    tp_total_qty = sum(float(tp.get('qty', 0)) for tp in tp_orders)
    tp_coverage = (tp_total_qty / size * 100) if size > 0 else 0
    
    # Calculate SL coverage
    sl_total_qty = sum(float(sl.get('qty', 0)) for sl in sl_orders)
    # For SL, should cover current position + pending entries
    pending_qty = sum(float(e.get('qty', 0)) for e in entry_orders)
    target_size = size + pending_qty
    sl_coverage = (sl_total_qty / target_size * 100) if target_size > 0 else 0
    
    return {
        'symbol': symbol,
        'side': side,
        'size': size,
        'pending_entries': pending_qty,
        'target_size': target_size,
        'tp_count': len(tp_orders),
        'tp_total_qty': tp_total_qty,
        'tp_coverage': tp_coverage,
        'sl_count': len(sl_orders),
        'sl_total_qty': sl_total_qty,
        'sl_coverage': sl_coverage,
        'has_tp': len(tp_orders) > 0,
        'has_sl': len(sl_orders) > 0,
        'tp_orders': tp_orders,
        'sl_orders': sl_orders,
        'entry_orders': entry_orders
    }

async def check_all_positions():
    """Check all positions on both accounts"""
    results = {
        'main': {'positions': [], 'issues': []},
        'mirror': {'positions': [], 'issues': []}
    }
    
    # Check main account
    logger.info("=" * 60)
    logger.info("CHECKING MAIN ACCOUNT POSITIONS")
    logger.info("=" * 60)
    
    try:
        response = bybit_client.get_positions(category="linear", settleCoin="USDT")
        if response and response.get('retCode') == 0:
            positions = response.get('result', {}).get('list', [])
            
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    result = await check_position_orders("MAIN", bybit_client, pos)
                    if result:
                        results['main']['positions'].append(result)
                        
                        # Check for issues
                        issues = []
                        if not result['has_tp']:
                            issues.append("MISSING TP ORDERS")
                        elif result['tp_coverage'] < 95:
                            issues.append(f"LOW TP COVERAGE: {result['tp_coverage']:.1f}%")
                            
                        if not result['has_sl']:
                            issues.append("MISSING SL ORDER")
                        elif result['sl_coverage'] < 95:
                            issues.append(f"LOW SL COVERAGE: {result['sl_coverage']:.1f}%")
                        
                        if issues:
                            results['main']['issues'].append({
                                'position': result,
                                'issues': issues
                            })
                            logger.warning(f"❌ MAIN {result['symbol']} {result['side']}: {', '.join(issues)}")
                        else:
                            logger.info(f"✅ MAIN {result['symbol']} {result['side']}: TP={result['tp_count']} ({result['tp_coverage']:.1f}%), SL={result['sl_count']} ({result['sl_coverage']:.1f}%)")
    except Exception as e:
        logger.error(f"Error checking main account: {e}")
    
    # Check mirror account
    if is_mirror_trading_enabled() and bybit_client_2:
        logger.info("\n" + "=" * 60)
        logger.info("CHECKING MIRROR ACCOUNT POSITIONS")
        logger.info("=" * 60)
        
        try:
            response = bybit_client_2.get_positions(category="linear", settleCoin="USDT")
            if response and response.get('retCode') == 0:
                positions = response.get('result', {}).get('list', [])
                
                for pos in positions:
                    if float(pos.get('size', 0)) > 0:
                        result = await check_position_orders("MIRROR", bybit_client_2, pos)
                        if result:
                            results['mirror']['positions'].append(result)
                            
                            # Check for issues
                            issues = []
                            if not result['has_tp']:
                                issues.append("MISSING TP ORDERS")
                            elif result['tp_coverage'] < 95:
                                issues.append(f"LOW TP COVERAGE: {result['tp_coverage']:.1f}%")
                                
                            if not result['has_sl']:
                                issues.append("MISSING SL ORDER")
                            elif result['sl_coverage'] < 95:
                                issues.append(f"LOW SL COVERAGE: {result['sl_coverage']:.1f}%")
                            
                            if issues:
                                results['mirror']['issues'].append({
                                    'position': result,
                                    'issues': issues
                                })
                                logger.warning(f"❌ MIRROR {result['symbol']} {result['side']}: {', '.join(issues)}")
                            else:
                                logger.info(f"✅ MIRROR {result['symbol']} {result['side']}: TP={result['tp_count']} ({result['tp_coverage']:.1f}%), SL={result['sl_count']} ({result['sl_coverage']:.1f}%)")
        except Exception as e:
            logger.error(f"Error checking mirror account: {e}")
    
    return results

async def main():
    """Main function"""
    results = await check_all_positions()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    main_issues = results['main']['issues']
    mirror_issues = results['mirror']['issues']
    
    logger.info(f"\nMAIN ACCOUNT:")
    logger.info(f"  Total positions: {len(results['main']['positions'])}")
    logger.info(f"  Positions with issues: {len(main_issues)}")
    
    if main_issues:
        logger.info("\n  POSITIONS NEEDING ATTENTION:")
        for issue_data in main_issues:
            pos = issue_data['position']
            issues = issue_data['issues']
            logger.info(f"    • {pos['symbol']} {pos['side']}: {', '.join(issues)}")
            logger.info(f"      Size: {pos['size']}, TP orders: {pos['tp_count']}, SL orders: {pos['sl_count']}")
    
    logger.info(f"\nMIRROR ACCOUNT:")
    logger.info(f"  Total positions: {len(results['mirror']['positions'])}")
    logger.info(f"  Positions with issues: {len(mirror_issues)}")
    
    if mirror_issues:
        logger.info("\n  POSITIONS NEEDING ATTENTION:")
        for issue_data in mirror_issues:
            pos = issue_data['position']
            issues = issue_data['issues']
            logger.info(f"    • {pos['symbol']} {pos['side']}: {', '.join(issues)}")
            logger.info(f"      Size: {pos['size']}, TP orders: {pos['tp_count']}, SL orders: {pos['sl_count']}")
    
    # Final verdict
    total_issues = len(main_issues) + len(mirror_issues)
    if total_issues == 0:
        logger.info("\n✅ ALL POSITIONS HAVE PROPER TP AND SL ORDERS!")
    else:
        logger.info(f"\n❌ FOUND {total_issues} POSITIONS WITH MISSING OR INCOMPLETE TP/SL ORDERS")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())