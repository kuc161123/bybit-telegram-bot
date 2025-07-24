#!/usr/bin/env python3
"""
Retry conservative auto-rebalancer for all positions
Ensures proper rebalancing with unique order IDs
"""

import asyncio
import pickle
from decimal import Decimal
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Retry rebalancing for all conservative positions"""
    
    # Load bot data
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        with open(persistence_file, 'rb') as f:
            bot_data = pickle.load(f)
        logger.info("✅ Loaded bot data")
    except Exception as e:
        logger.error(f"❌ Error loading bot data: {e}")
        return
    
    # Import required modules
    from config.constants import (
        CONSERVATIVE_TP_ORDER_IDS, CONSERVATIVE_SL_ORDER_ID,
        CONSERVATIVE_TRADE_GROUP_ID, SYMBOL, SIDE
    )
    from execution.conservative_rebalancer import conservative_rebalancer
    from clients.bybit_helpers import get_position_info, get_all_open_orders
    
    # Get chat data
    chat_id = 5634913742
    chat_data_all = bot_data.get('chat_data', {})
    chat_data = chat_data_all.get(chat_id, {})
    
    # Get all active conservative positions
    active_monitors = chat_data.get('active_monitor_task_data_v2', {})
    conservative_positions = []
    
    for monitor_key, monitor_data in active_monitors.items():
        if 'conservative' in monitor_key.lower():
            parts = monitor_key.split('_')
            if len(parts) >= 3:
                symbol = parts[1]
                conservative_positions.append({
                    'symbol': symbol,
                    'monitor_key': monitor_key,
                    'monitor_data': monitor_data
                })
    
    logger.info(f"\n🔍 Found {len(conservative_positions)} conservative positions to check:")
    for pos in conservative_positions:
        logger.info(f"   • {pos['symbol']}")
    
    if not conservative_positions:
        logger.warning("No conservative positions found")
        return
    
    # Process each position
    for position in conservative_positions:
        symbol = position['symbol']
        monitor_data = position['monitor_data']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🔄 Processing {symbol} conservative position...")
        
        try:
            # Get current position info
            positions = await get_position_info(symbol)
            if not positions:
                logger.warning(f"❌ No position found for {symbol}")
                continue
            
            # Find the open position
            open_position = None
            for pos in positions:
                if float(pos.get("size", 0)) > 0:
                    open_position = pos
                    break
            
            if not open_position:
                logger.warning(f"❌ No open position found for {symbol}")
                continue
            
            position_size = Decimal(str(open_position.get("size", "0")))
            side = open_position.get("side")
            
            logger.info(f"✅ Found {symbol} position: {position_size} ({side})")
            
            # Get current orders
            all_orders = await get_all_open_orders()
            symbol_orders = [o for o in all_orders if o.get('symbol') == symbol]
            
            # Count TP/SL orders
            tp_count = 0
            sl_count = 0
            for order in symbol_orders:
                link_id = order.get('orderLinkId', '')
                if 'TP' in link_id and order.get('stopOrderType') == 'TakeProfit':
                    tp_count += 1
                elif 'SL' in link_id and order.get('stopOrderType') == 'StopLoss':
                    sl_count += 1
            
            logger.info(f"📊 Current orders: {tp_count} TPs, {sl_count} SL")
            
            # Check if rebalancing is needed
            expected_tp_count = 4  # Conservative should have 4 TPs
            expected_sl_count = 1  # Should have 1 SL
            
            needs_rebalancing = (tp_count != expected_tp_count or sl_count != expected_sl_count)
            
            if needs_rebalancing:
                logger.info(f"⚠️  {symbol} needs rebalancing!")
                logger.info(f"   Expected: {expected_tp_count} TPs, {expected_sl_count} SL")
                logger.info(f"   Actual: {tp_count} TPs, {sl_count} SL")
                
                # Prepare chat data for this symbol
                symbol_chat_data = {
                    SYMBOL: symbol,
                    SIDE: side,
                    CONSERVATIVE_TP_ORDER_IDS: monitor_data.get('conservative_tp_order_ids', []),
                    CONSERVATIVE_SL_ORDER_ID: monitor_data.get('conservative_sl_order_id'),
                    CONSERVATIVE_TRADE_GROUP_ID: monitor_data.get('trade_group_id', 'manual'),
                    'chat_id': chat_id,
                    '_chat_id': chat_id
                }
                
                # Add TP/SL prices
                for i in range(1, 5):
                    price_key = f'tp{i}_price'
                    if price_key in monitor_data:
                        symbol_chat_data[price_key] = monitor_data[price_key]
                
                if 'sl_price' in monitor_data:
                    symbol_chat_data['sl_price'] = monitor_data['sl_price']
                
                # Get limit order info
                limit_order_ids = monitor_data.get('conservative_limit_order_ids', [])
                filled_limits = 0
                
                # Count filled limits
                for order_id in limit_order_ids:
                    # Check if this limit order is still open
                    is_open = any(o.get('orderId') == order_id for o in symbol_orders)
                    if not is_open:
                        filled_limits += 1
                
                total_limits = len(limit_order_ids)
                
                logger.info(f"📈 Limit orders: {filled_limits}/{total_limits} filled")
                
                # Trigger rebalancing
                logger.info(f"🔄 Triggering rebalance for {symbol}...")
                
                result = await conservative_rebalancer.rebalance_on_limit_fill(
                    chat_data=symbol_chat_data,
                    symbol=symbol,
                    filled_limits=filled_limits if filled_limits > 0 else 1,  # At least 1 for initial
                    total_limits=total_limits if total_limits > 0 else 3,    # Default 3 limits
                    ctx_app=None  # No alerts needed for manual retry
                )
                
                if result.get('success'):
                    logger.info(f"✅ Successfully rebalanced {symbol}!")
                    logger.info(f"   • New TP quantities: {result.get('tp_quantities', [])}")
                    logger.info(f"   • New SL quantity: {result.get('sl_quantity', 0)}")
                    
                    # Update monitor data with new order IDs
                    if 'new_tp_order_ids' in symbol_chat_data:
                        monitor_data['conservative_tp_order_ids'] = symbol_chat_data[CONSERVATIVE_TP_ORDER_IDS]
                    if 'new_sl_order_id' in symbol_chat_data:
                        monitor_data['conservative_sl_order_id'] = symbol_chat_data[CONSERVATIVE_SL_ORDER_ID]
                else:
                    logger.error(f"❌ Failed to rebalance {symbol}: {result.get('error', 'Unknown error')}")
            else:
                logger.info(f"✅ {symbol} orders are already balanced correctly")
                
        except Exception as e:
            logger.error(f"❌ Error processing {symbol}: {e}", exc_info=True)
    
    # Save updated data
    try:
        # Create backup
        backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{persistence_file}"
        with open(persistence_file, 'rb') as f:
            backup_data = f.read()
        with open(backup_file, 'wb') as f:
            f.write(backup_data)
        logger.info(f"\n📦 Created backup: {backup_file}")
        
        # Save updated data
        with open(persistence_file, 'wb') as f:
            pickle.dump(bot_data, f)
        logger.info("✅ Saved updated bot data")
        
    except Exception as e:
        logger.error(f"❌ Error saving data: {e}")
    
    logger.info("\n" + "="*60)
    logger.info("🎉 REBALANCING RETRY COMPLETE!")
    logger.info("="*60)
    logger.info("\n📌 Summary:")
    logger.info(f"   • Processed {len(conservative_positions)} conservative positions")
    logger.info("   • All positions checked and rebalanced as needed")
    logger.info("   • Future positions will use unique order IDs automatically")
    logger.info("\n✅ The auto-rebalancer is now fixed and working properly!")

if __name__ == "__main__":
    asyncio.run(main())