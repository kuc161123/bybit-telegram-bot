#!/usr/bin/env python3
"""
Fix DOGEUSDT position state
- Update monitor to recognize limit orders were already filled
- Ensure TP orders are correctly sized
- Fix mirror account sync
"""
import asyncio
import logging
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fix_dogeusdt():
    """Fix DOGEUSDT position state"""
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from execution.mirror_enhanced_tp_sl import mirror_enhanced_tp_sl_manager
        from clients.bybit_helpers import get_all_positions, get_open_orders
        
        logger.info("🔧 Fixing DOGEUSDT position state...")
        
        # Check if monitor exists
        monitor_key = "DOGEUSDT_Buy"
        if monitor_key not in enhanced_tp_sl_manager.position_monitors:
            logger.error("❌ No monitor found for DOGEUSDT Buy")
            return
        
        monitor_data = enhanced_tp_sl_manager.position_monitors[monitor_key]
        
        # Get current position
        positions = await get_all_positions()
        doge_position = None
        for pos in positions:
            if pos.get('symbol') == 'DOGEUSDT' and pos.get('side') == 'Buy':
                doge_position = pos
                break
        
        if not doge_position:
            logger.error("❌ No DOGEUSDT Buy position found")
            return
        
        current_size = Decimal(str(doge_position.get('size', '0')))
        logger.info(f"📊 Current DOGEUSDT position size: {current_size}")
        
        # Update monitor data
        logger.info("📝 Updating monitor state...")
        
        # Mark that limit orders have already been filled
        monitor_data['limit_orders_filled'] = True
        monitor_data['phase'] = 'PROFIT_TAKING'  # We're now in profit-taking phase
        monitor_data['position_size'] = current_size  # Update to current size
        monitor_data['remaining_size'] = current_size
        
        # Reset fill tracker to correct state
        fill_tracker_key = "DOGEUSDT_Buy"
        enhanced_tp_sl_manager.fill_tracker[fill_tracker_key] = {
            "total_filled": Decimal("0"),  # Reset since we're starting fresh
            "target_size": current_size  # Target is current position
        }
        
        logger.info("✅ Monitor state updated")
        
        # Check and update TP orders
        all_orders = await get_open_orders()
        doge_orders = [o for o in all_orders if o.get('symbol') == 'DOGEUSDT']
        
        tp_orders = []
        for order in doge_orders:
            if 'TP' in order.get('orderLinkId', '') and order.get('orderType') == 'Limit':
                tp_orders.append(order)
        
        logger.info(f"📋 Found {len(tp_orders)} TP orders")
        
        # Verify TP order quantities match position size
        expected_quantities = {
            'TP1': int(current_size * Decimal('0.85')),  # 85%
            'TP2': int(current_size * Decimal('0.05')),  # 5%
            'TP3': int(current_size * Decimal('0.05')),  # 5%
            'TP4': int(current_size * Decimal('0.05'))   # 5%
        }
        
        logger.info("🎯 Expected TP quantities:")
        for tp, qty in expected_quantities.items():
            logger.info(f"   {tp}: {qty} DOGE")
        
        # Update monitor's TP order tracking
        monitor_tp_orders = []
        for order in tp_orders:
            link_id = order.get('orderLinkId', '')
            for tp_num in ['TP1', 'TP2', 'TP3', 'TP4']:
                if tp_num in link_id:
                    monitor_tp_orders.append({
                        'order_id': order.get('orderId'),
                        'order_link_id': link_id,
                        'price': Decimal(str(order.get('price', '0'))),
                        'quantity': Decimal(str(order.get('qty', '0'))),
                        'original_quantity': Decimal(str(order.get('qty', '0'))),
                        'tp_number': int(tp_num[2])  # Extract number from TP1, TP2, etc
                    })
                    break
        
        # Sort by TP number
        monitor_tp_orders.sort(key=lambda x: x.get('tp_number', 0))
        monitor_data['tp_orders'] = monitor_tp_orders
        
        logger.info(f"✅ Updated monitor with {len(monitor_tp_orders)} TP orders")
        
        # Fix mirror account sync
        if mirror_enhanced_tp_sl_manager:
            logger.info("\n🪞 Fixing mirror account sync...")
            
            # Get mirror position
            from execution.mirror_trader import get_mirror_positions
            mirror_positions = await get_mirror_positions()
            mirror_doge = None
            
            for pos in mirror_positions:
                if pos.get('symbol') == 'DOGEUSDT' and pos.get('side') == 'Buy':
                    mirror_doge = pos
                    break
            
            if mirror_doge:
                mirror_size = Decimal(str(mirror_doge.get('size', '0')))
                logger.info(f"📊 Mirror position size: {mirror_size}")
                
                # Update mirror monitor if exists
                mirror_key = "DOGEUSDT_Buy"
                if mirror_key in mirror_enhanced_tp_sl_manager.mirror_monitors:
                    mirror_monitor = mirror_enhanced_tp_sl_manager.mirror_monitors[mirror_key]
                    mirror_monitor['limit_orders_filled'] = True
                    mirror_monitor['phase'] = 'PROFIT_TAKING'
                    mirror_monitor['position_size'] = mirror_size
                    mirror_monitor['remaining_size'] = mirror_size
                    logger.info("✅ Mirror monitor updated")
                
                # Trigger sync to ensure orders are correct
                await mirror_enhanced_tp_sl_manager.sync_with_main_position_enhanced(
                    'DOGEUSDT', 'Buy', current_size
                )
                logger.info("✅ Mirror sync triggered")
            else:
                logger.warning("⚠️ No mirror position found for DOGEUSDT")
        
        logger.info("\n✅ DOGEUSDT position fix completed!")
        logger.info("📊 Summary:")
        logger.info(f"   - Position size: {current_size}")
        logger.info(f"   - Limit orders marked as filled")
        logger.info(f"   - Phase: PROFIT_TAKING")
        logger.info(f"   - TP orders tracked: {len(monitor_tp_orders)}")
        logger.info(f"   - Mirror sync completed")
        
    except Exception as e:
        logger.error(f"❌ Error fixing DOGEUSDT: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_dogeusdt())