#!/usr/bin/env python3
"""
Fix XRPUSDT mirror SL to provide full position coverage including pending limit orders
Following Enhanced TP/SL manager logic
"""
import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional
import pickle

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from clients.bybit_helpers import get_open_orders
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled, get_mirror_positions

async def get_xrpusdt_orders_detailed() -> Dict:
    """Get detailed XRPUSDT orders on mirror account"""
    if not bybit_client_2:
        return {"sl_order": None, "entry_orders": [], "tp_orders": []}
    
    try:
        response = bybit_client_2.get_open_orders(
            category="linear",
            symbol="XRPUSDT"
        )
        
        if response and response.get('retCode') == 0:
            orders = response.get('result', {}).get('list', [])
            
            sl_order = None
            entry_orders = []
            tp_orders = []
            
            for order in orders:
                order_link_id = order.get('orderLinkId', '')
                
                if order.get('reduceOnly'):
                    if 'SL' in order_link_id:
                        sl_order = order
                    elif 'TP' in order_link_id:
                        tp_orders.append(order)
                else:
                    # Non-reduce-only orders are entry orders
                    entry_orders.append(order)
            
            return {
                "sl_order": sl_order,
                "entry_orders": entry_orders,
                "tp_orders": tp_orders
            }
        else:
            logger.error(f"Error getting mirror orders: {response}")
            return {"sl_order": None, "entry_orders": [], "tp_orders": []}
            
    except Exception as e:
        logger.error(f"Exception getting mirror orders: {e}")
        return {"sl_order": None, "entry_orders": [], "tp_orders": []}

async def cancel_mirror_sl_order(symbol: str, order_id: str) -> bool:
    """Cancel SL order on mirror account"""
    if not bybit_client_2:
        return False
    
    try:
        logger.info(f"🔄 Canceling SL order {order_id[:8]}...")
        
        response = bybit_client_2.cancel_order(
            category="linear",
            symbol=symbol,
            orderId=order_id
        )
        
        if response and response.get("retCode") == 0:
            logger.info(f"✅ SL order cancelled successfully")
            return True
        elif response and response.get("retCode") == 110001:
            logger.info(f"ℹ️ SL order already cancelled or filled")
            return True
        else:
            logger.error(f"❌ Cancel failed: {response}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception canceling SL order: {e}")
        return False

async def place_mirror_sl_full_coverage(
    symbol: str,
    side: str,
    full_qty: str,
    trigger_price: str,
    order_link_id: str
) -> Optional[Dict]:
    """Place SL order with full position coverage on mirror account"""
    if not bybit_client_2:
        return None
    
    try:
        logger.info(f"🛡️ MIRROR: Placing FULL COVERAGE SL order {side} {full_qty} @ trigger {trigger_price}")
        
        # For a Buy position: SL triggers when price goes DOWN (Sell to close)
        trigger_direction = 2  # <= (price falls below trigger)
        
        response = bybit_client_2.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            orderType="Market",
            qty=full_qty,
            triggerPrice=trigger_price,
            triggerDirection=trigger_direction,
            reduceOnly=True,
            orderLinkId=order_link_id,
            positionIdx=0  # Mirror uses One-Way mode
        )
        
        if response and response.get("retCode") == 0:
            result = response.get("result", {})
            order_id = result.get("orderId", "")
            logger.info(f"✅ MIRROR: Full coverage SL placed: {order_id[:8]}...")
            return result
        else:
            logger.error(f"❌ MIRROR: SL order failed: {response}")
            return None
            
    except Exception as e:
        logger.error(f"❌ MIRROR: Exception placing SL order: {e}")
        return None

async def update_enhanced_monitor(symbol: str, side: str, current_size: Decimal, target_size: Decimal):
    """Update Enhanced TP/SL monitor with proper target size"""
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        monitor_key = f"{symbol}_{side}"
        
        if monitor_key in enhanced_monitors:
            monitor_data = enhanced_monitors[monitor_key]
            
            # Update monitor with full position information
            monitor_data['has_mirror'] = True
            monitor_data['mirror_synced'] = True
            monitor_data['target_size'] = str(target_size)
            monitor_data['current_size'] = str(current_size)
            monitor_data['position_size'] = str(target_size)  # Full intended size
            monitor_data['remaining_size'] = str(current_size)  # Current filled size
            
            logger.info(f"✅ Updated Enhanced monitor with target size: {target_size}")
            
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
        else:
            logger.warning(f"⚠️ No Enhanced TP/SL monitor found for {monitor_key}")
            logger.info(f"Creating new monitor entry...")
            
            # Create new monitor
            enhanced_monitors[monitor_key] = {
                'symbol': symbol,
                'side': side,
                'has_mirror': True,
                'mirror_synced': True,
                'target_size': str(target_size),
                'current_size': str(current_size),
                'position_size': str(target_size),
                'remaining_size': str(current_size),
                'approach': 'CONSERVATIVE',  # Based on the entry orders
                'active': True
            }
            
            with open(pickle_file, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"✅ Created Enhanced monitor for {monitor_key}")
            
    except Exception as e:
        logger.error(f"❌ Error updating monitor: {e}")

async def main():
    logger.info("Starting XRPUSDT Mirror SL Full Coverage Fix...")
    logger.info("=" * 60)
    
    if not is_mirror_trading_enabled():
        logger.error("❌ Mirror trading is not enabled")
        return
    
    # Step 1: Get mirror position
    mirror_positions = await get_mirror_positions()
    mirror_position = None
    for pos in mirror_positions:
        if pos.get('symbol') == 'XRPUSDT' and float(pos.get('size', 0)) > 0 and pos.get('side') == 'Buy':
            mirror_position = pos
            break
    
    if not mirror_position:
        logger.error("❌ No active XRPUSDT Buy position found on mirror account")
        return
    
    current_position_size = Decimal(str(mirror_position['size']))
    logger.info(f"Current position size: {current_position_size}")
    
    # Step 2: Get current orders
    order_data = await get_xrpusdt_orders_detailed()
    sl_order = order_data["sl_order"]
    entry_orders = order_data["entry_orders"]
    tp_orders = order_data["tp_orders"]
    
    logger.info(f"\nCurrent orders:")
    logger.info(f"  SL orders: {1 if sl_order else 0}")
    logger.info(f"  TP orders: {len(tp_orders)}")
    logger.info(f"  Entry orders: {len(entry_orders)}")
    
    # Step 3: Calculate target position size
    pending_entry_size = Decimal("0")
    for order in entry_orders:
        pending_entry_size += Decimal(str(order.get('qty', '0')))
    
    target_position_size = current_position_size + pending_entry_size
    
    logger.info(f"\nPosition sizing:")
    logger.info(f"  Current filled: {current_position_size}")
    logger.info(f"  Pending entries: {pending_entry_size}")
    logger.info(f"  Target size: {target_position_size}")
    
    # Step 4: Check if SL needs update
    if sl_order:
        current_sl_qty = Decimal(str(sl_order.get('qty', '0')))
        sl_trigger_price = sl_order.get('triggerPrice')
        sl_order_id = sl_order.get('orderId')
        
        logger.info(f"\nCurrent SL: {current_sl_qty} @ trigger {sl_trigger_price}")
        
        if current_sl_qty < target_position_size:
            logger.warning(f"⚠️ SL only covers {current_sl_qty}/{target_position_size} ({(current_sl_qty/target_position_size*100):.1f}%)")
            
            # Cancel current SL
            if await cancel_mirror_sl_order("XRPUSDT", sl_order_id):
                await asyncio.sleep(1)  # Wait for cancellation
                
                # Place new SL with full coverage
                new_sl_result = await place_mirror_sl_full_coverage(
                    symbol="XRPUSDT",
                    side="Sell",  # Opposite of Buy position
                    full_qty=str(int(target_position_size)),
                    trigger_price=str(sl_trigger_price),
                    order_link_id="BOT_MIRROR_XRPUSDT_SL_FULL_COVERAGE"
                )
                
                if new_sl_result:
                    logger.info("✅ Full coverage SL order placed successfully")
                else:
                    logger.error("❌ Failed to place full coverage SL order")
                    return
            else:
                logger.error("❌ Failed to cancel current SL order")
                return
        else:
            logger.info("✅ SL already provides full coverage")
    else:
        logger.error("❌ No SL order found - this should not happen!")
        return
    
    # Step 5: Update Enhanced TP/SL monitor
    logger.info("\nUpdating Enhanced TP/SL monitor...")
    await update_enhanced_monitor("XRPUSDT", "Buy", current_position_size, target_position_size)
    
    # Step 6: Trigger position sync
    try:
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        await enhanced_tp_sl_manager.sync_existing_positions()
        logger.info("✅ Triggered Enhanced TP/SL position sync")
    except Exception as e:
        logger.warning(f"⚠️ Could not trigger position sync: {e}")
    
    # Final verification
    logger.info("\n" + "=" * 60)
    logger.info("Verification:")
    
    await asyncio.sleep(2)
    final_orders = await get_xrpusdt_orders_detailed()
    
    if final_orders["sl_order"]:
        final_sl_qty = Decimal(str(final_orders["sl_order"].get('qty', '0')))
        coverage_pct = (final_sl_qty / target_position_size) * 100
        logger.info(f"  Final SL coverage: {final_sl_qty}/{target_position_size} ({coverage_pct:.1f}%)")
        
        if coverage_pct >= 99.9:  # Allow for minor rounding
            logger.info("  ✅ Full position coverage achieved!")
        else:
            logger.warning(f"  ⚠️ Coverage still incomplete: {coverage_pct:.1f}%")
    
    logger.info(f"  TP orders: {len(final_orders['tp_orders'])}")
    logger.info(f"  Entry orders: {len(final_orders['entry_orders'])}")
    
    logger.info("\n✅ XRPUSDT Mirror SL Full Coverage Fix Completed!")

if __name__ == "__main__":
    asyncio.run(main())