#!/usr/bin/env python3
"""
Verify SL Coverage Including Limit Orders

Check that SL orders cover 100% including unfilled limit orders for conservative positions
"""

import asyncio
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def verify_sl_coverage():
    """Verify SL coverage for all positions"""
    try:
        from clients.bybit_helpers import get_all_positions, get_all_open_orders, get_instrument_info
        from execution.mirror_trader import is_mirror_trading_enabled, bybit_client_2
        from clients.bybit_client import bybit_client
        import pickle
        
        # Load approach data
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        logger.info("🔍 VERIFYING SL COVERAGE INCLUDING LIMIT ORDERS")
        logger.info("=" * 80)
        
        # Check main account
        logger.info("\n📍 MAIN ACCOUNT")
        logger.info("-" * 60)
        
        main_positions = await get_all_positions()
        main_orders = await get_all_open_orders()
        
        await check_account_coverage(main_positions, main_orders, enhanced_monitors, "main")
        
        # Check mirror account
        if is_mirror_trading_enabled() and bybit_client_2:
            logger.info("\n🪞 MIRROR ACCOUNT")
            logger.info("-" * 60)
            
            mirror_positions = await get_all_positions(client=bybit_client_2)
            mirror_orders = await get_all_open_orders(bybit_client_2)
            
            await check_account_coverage(mirror_positions, mirror_orders, enhanced_monitors, "mirror")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ SL Coverage Verification Complete")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

async def check_account_coverage(positions, orders, monitors, account_type):
    """Check SL coverage for an account"""
    
    for position in positions:
        if float(position.get('size', 0)) <= 0:
            continue
            
        symbol = position.get('symbol')
        side = position.get('side')
        current_size = Decimal(str(position.get('size', '0')))
        
        logger.info(f"\n🎯 {symbol} {side}")
        logger.info(f"   Current position: {current_size}")
        
        # Get approach from monitor
        monitor_key = f"{symbol}_{side}"
        if account_type == "mirror":
            monitor_key += "_MIRROR"
            
        monitor_data = monitors.get(monitor_key, {})
        approach = monitor_data.get('approach', 'FAST').upper()
        
        logger.info(f"   Approach: {approach}")
        
        # Find limit orders (unfilled)
        position_orders = [o for o in orders if o.get('symbol') == symbol]
        limit_orders = []
        sl_order = None
        
        for order in position_orders:
            order_type = order.get('orderType', '')
            order_link_id = order.get('orderLinkId', '')
            
            # Find unfilled limit orders
            if (order_type == 'Limit' and 
                not order.get('reduceOnly') and 
                order.get('side') == side and
                'BOT_' in order_link_id):
                limit_qty = Decimal(str(order.get('qty', '0')))
                limit_orders.append({
                    'id': order.get('orderId'),
                    'qty': limit_qty,
                    'price': order.get('price')
                })
            
            # Find SL order
            if (order.get('stopOrderType') in ['StopLoss', 'Stop'] and
                order.get('orderStatus') in ['New', 'Untriggered'] and
                order.get('side') != side):
                sl_order = order
        
        # Calculate total intended position
        total_limit_qty = sum(lo['qty'] for lo in limit_orders)
        intended_position = current_size + total_limit_qty
        
        logger.info(f"   Unfilled limit orders: {len(limit_orders)}")
        if limit_orders:
            for lo in limit_orders:
                logger.info(f"      - {lo['qty']} @ {lo['price']}")
            logger.info(f"   Total limit quantity: {total_limit_qty}")
        
        logger.info(f"   Intended position (current + limits): {intended_position}")
        
        # Check SL coverage
        if sl_order:
            sl_qty = Decimal(str(sl_order.get('qty', '0')))
            sl_price = sl_order.get('triggerPrice', '')
            
            logger.info(f"   SL order: {sl_qty} @ {sl_price}")
            
            # Calculate coverage percentage
            if approach == "CONSERVATIVE":
                # For conservative, SL should cover intended position
                coverage_pct = (sl_qty / intended_position * 100) if intended_position > 0 else 0
                expected_coverage = intended_position
                logger.info(f"   Expected SL coverage: {expected_coverage} (includes unfilled limits)")
            else:
                # For fast, SL should cover current position
                coverage_pct = (sl_qty / current_size * 100) if current_size > 0 else 0
                expected_coverage = current_size
                logger.info(f"   Expected SL coverage: {expected_coverage} (current position only)")
            
            logger.info(f"   Coverage: {coverage_pct:.1f}%")
            
            if abs(coverage_pct - 100) > 1:  # Allow 1% tolerance
                logger.warning(f"   ⚠️ ISSUE: SL coverage is {coverage_pct:.1f}%, expected 100%")
                logger.warning(f"   ⚠️ SL quantity {sl_qty} vs expected {expected_coverage}")
            else:
                logger.info(f"   ✅ SL has 100% coverage")
        else:
            logger.error(f"   ❌ NO SL ORDER FOUND!")

if __name__ == "__main__":
    asyncio.run(verify_sl_coverage())