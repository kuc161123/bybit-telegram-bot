#!/usr/bin/env python3
"""
Check SL Status for Both Accounts
This script provides a comprehensive report of SL orders across main and mirror accounts
"""

import asyncio
import logging
from decimal import Decimal
import sys
import os
from typing import Dict, List, Optional
from tabulate import tabulate
import json

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_sl_status():
    """Check SL status for all positions in both accounts"""
    try:
        from clients.bybit_helpers import get_all_positions
        from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2
        from clients.bybit_client import bybit_client
        
        logger.info("🔍 Checking SL Status for Both Accounts")
        logger.info("=" * 80)
        
        # Get all positions
        main_positions = await get_all_positions(client=bybit_client)
        
        mirror_positions = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_positions = await get_all_positions(client=bybit_client_2)
        else:
            logger.warning("⚠️ Mirror trading not enabled - checking main account only")
        
        # Filter active positions
        active_main = [pos for pos in main_positions if float(pos.get('size', 0)) > 0]
        active_mirror = [pos for pos in mirror_positions if float(pos.get('size', 0)) > 0]
        
        logger.info(f"\n📊 Found {len(active_main)} main positions, {len(active_mirror)} mirror positions")
        
        # Collect SL data
        sl_data = []
        
        # Process main positions
        for position in active_main:
            symbol = position['symbol']
            side = position['side']
            size = position.get('size', '0')
            
            # Get SL order
            sl_info = await get_sl_info_for_position(bybit_client, symbol, side)
            
            sl_data.append({
                'Account': 'Main',
                'Symbol': symbol,
                'Side': side,
                'Size': size,
                'SL Price': sl_info.get('price', '-'),
                'SL Qty': sl_info.get('qty', '-'),
                'Coverage': sl_info.get('coverage', '-'),
                'Status': sl_info.get('status', 'NO SL')
            })
        
        # Process mirror positions
        for position in active_mirror:
            symbol = position['symbol']
            side = position['side']
            size = position.get('size', '0')
            
            # Get SL order
            sl_info = await get_sl_info_for_position(bybit_client_2, symbol, side)
            
            sl_data.append({
                'Account': 'Mirror',
                'Symbol': symbol,
                'Side': side,
                'Size': size,
                'SL Price': sl_info.get('price', '-'),
                'SL Qty': sl_info.get('qty', '-'),
                'Coverage': sl_info.get('coverage', '-'),
                'Status': sl_info.get('status', 'NO SL')
            })
        
        # Sort by symbol and account
        sl_data.sort(key=lambda x: (x['Symbol'], x['Account']))
        
        # Print table
        if sl_data:
            print("\n" + tabulate(sl_data, headers='keys', tablefmt='grid'))
        else:
            print("\nNo active positions found")
        
        # Generate comparison report
        logger.info("\n📊 SL Comparison Report")
        logger.info("=" * 80)
        
        # Group by symbol
        symbol_groups = {}
        for item in sl_data:
            symbol_key = f"{item['Symbol']}_{item['Side']}"
            if symbol_key not in symbol_groups:
                symbol_groups[symbol_key] = {'main': None, 'mirror': None}
            
            if item['Account'] == 'Main':
                symbol_groups[symbol_key]['main'] = item
            else:
                symbol_groups[symbol_key]['mirror'] = item
        
        # Check for mismatches
        mismatches = []
        missing_sl = []
        price_differences = []
        
        for symbol_key, accounts in symbol_groups.items():
            main = accounts['main']
            mirror = accounts['mirror']
            
            if main and mirror:
                # Both accounts have position
                main_has_sl = main['Status'] != 'NO SL'
                mirror_has_sl = mirror['Status'] != 'NO SL'
                
                if main_has_sl and not mirror_has_sl:
                    missing_sl.append(f"{symbol_key} - Mirror missing SL")
                elif not main_has_sl and mirror_has_sl:
                    missing_sl.append(f"{symbol_key} - Main missing SL")
                elif not main_has_sl and not mirror_has_sl:
                    missing_sl.append(f"{symbol_key} - Both missing SL")
                elif main_has_sl and mirror_has_sl:
                    # Check price match
                    if main['SL Price'] != mirror['SL Price']:
                        price_differences.append(
                            f"{symbol_key} - Main: {main['SL Price']}, Mirror: {mirror['SL Price']}"
                        )
            elif main and not mirror:
                mismatches.append(f"{symbol_key} - Only in main account")
                if main['Status'] == 'NO SL':
                    missing_sl.append(f"{symbol_key} - Main missing SL")
            elif mirror and not main:
                mismatches.append(f"{symbol_key} - Only in mirror account")
                if mirror['Status'] == 'NO SL':
                    missing_sl.append(f"{symbol_key} - Mirror missing SL")
        
        # Print issues
        if mismatches:
            logger.warning("\n⚠️ Position Mismatches:")
            for mismatch in mismatches:
                logger.warning(f"   {mismatch}")
        
        if missing_sl:
            logger.error("\n❌ Missing SL Orders:")
            for missing in missing_sl:
                logger.error(f"   {missing}")
        
        if price_differences:
            logger.warning("\n⚠️ SL Price Differences:")
            for diff in price_differences:
                logger.warning(f"   {diff}")
        
        if not mismatches and not missing_sl and not price_differences:
            logger.info("\n✅ All positions have matching SL orders with correct prices!")
        
        # Save detailed report
        report = {
            'timestamp': asyncio.get_event_loop().time(),
            'summary': {
                'main_positions': len(active_main),
                'mirror_positions': len(active_mirror),
                'position_mismatches': len(mismatches),
                'missing_sl_orders': len(missing_sl),
                'price_differences': len(price_differences)
            },
            'details': {
                'sl_data': sl_data,
                'mismatches': mismatches,
                'missing_sl': missing_sl,
                'price_differences': price_differences
            }
        }
        
        with open('sl_status_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("\n📝 Detailed report saved to sl_status_report.json")
        
    except Exception as e:
        logger.error(f"❌ Error checking SL status: {e}")
        import traceback
        traceback.print_exc()

async def get_sl_info_for_position(client, symbol: str, side: str) -> Dict:
    """Get SL order information for a position"""
    try:
        response = client.get_open_orders(
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] != 0:
            return {'status': 'ERROR'}
        
        orders = response.get('result', {}).get('list', [])
        sl_side = "Sell" if side == "Buy" else "Buy"
        
        # Find SL order
        for order in orders:
            if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and
                order.get('side') == sl_side and
                order.get('reduceOnly')):
                
                qty = Decimal(str(order.get('qty', '0')))
                
                # Get position size to calculate coverage
                pos_response = client.get_positions(
                    category="linear",
                    symbol=symbol
                )
                
                coverage = '-'
                if pos_response['retCode'] == 0:
                    positions = pos_response.get('result', {}).get('list', [])
                    for pos in positions:
                        if pos.get('side') == side:
                            pos_size = Decimal(str(pos.get('size', '0')))
                            if pos_size > 0:
                                coverage = f"{(qty/pos_size*100):.0f}%"
                            break
                
                return {
                    'price': order.get('triggerPrice'),
                    'qty': order.get('qty'),
                    'coverage': coverage,
                    'status': 'ACTIVE',
                    'order_id': order.get('orderId')
                }
        
        return {'status': 'NO SL'}
        
    except Exception as e:
        logger.error(f"Error getting SL info for {symbol}: {e}")
        return {'status': 'ERROR'}

if __name__ == "__main__":
    asyncio.run(check_sl_status())