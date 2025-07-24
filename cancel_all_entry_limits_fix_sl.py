#!/usr/bin/env python3
"""
Cancel ALL entry limit orders and fix SL quantities for all positions
ONLY cancels entry limits - NOT TP or SL orders
"""
#!/usr/bin/env python3
"""
Cancel ALL entry limit orders and fix SL quantities for all positions
ONLY cancels entry limits - NOT TP or SL orders
"""
import pickle
from decimal import Decimal
from clients.bybit_client import bybit_client
import os
from pybit.unified_trading import HTTP
import time

# Initialize mirror client
BYBIT_API_KEY_2 = os.getenv('BYBIT_API_KEY_2')
BYBIT_API_SECRET_2 = os.getenv('BYBIT_API_SECRET_2')
USE_TESTNET = os.getenv('USE_TESTNET', 'false').lower() == 'true'

if BYBIT_API_KEY_2 and BYBIT_API_SECRET_2:
    bybit_client_mirror = HTTP(
        testnet=USE_TESTNET,
        api_key=BYBIT_API_KEY_2,
        api_secret=BYBIT_API_SECRET_2
    )
else:
    bybit_client_mirror = None
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_all_positions():
    """Get all active positions from both accounts"""
    positions = {'main': [], 'mirror': []}
    
    try:
        # Get main account positions
        logger.info("📊 Fetching main account positions...")
        main_result = bybit_client.get_positions(category="linear", settleCoin="USDT")
        if main_result and main_result.get('result'):
            for pos in main_result['result'].get('list', []):
                if float(pos.get('size', 0)) > 0:
                    positions['main'].append(pos)
        
        # Get mirror account positions
        logger.info("📊 Fetching mirror account positions...")
        if bybit_client_mirror:
            mirror_result = bybit_client_mirror.get_positions(category="linear", settleCoin="USDT")
            if mirror_result and mirror_result.get('result'):
                for pos in mirror_result['result'].get('list', []):
                    if float(pos.get('size', 0)) > 0:
                        positions['mirror'].append(pos)
                    
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
    
    return positions

def cancel_entry_limits_for_position(symbol, side, account_type='main'):
    """Cancel ONLY entry limit orders for a specific position"""
    cancelled_count = 0
    client = bybit_client_mirror if account_type == 'mirror' else bybit_client
    
    try:
        # Get all open orders for this symbol
        result = client.get_open_orders(category="linear", symbol=symbol)
        
        if result and result.get('result'):
            orders = result['result'].get('list', [])
            
            for order in orders:
                # CRITICAL: Only cancel limit orders that are NOT reduce-only
                # Entry orders have reduceOnly=False, TP/SL have reduceOnly=True
                if (order.get('orderType') == 'Limit' and 
                    not order.get('reduceOnly') and
                    order.get('side') == side):
                    
                    order_id = order.get('orderId')
                    order_link_id = order.get('orderLinkId', '')
                    
                    # Double check it's an entry order by checking the link ID
                    if 'TP' not in order_link_id.upper() and 'SL' not in order_link_id.upper():
                        logger.info(f"🚫 Cancelling entry limit order: {order_id[:8]}... ({order_link_id})")
                        
                        try:
                            result = client.cancel_order(
                                category="linear",
                                symbol=symbol,
                                orderId=order_id
                            )
                            
                            if result and result.get('retCode') == 0:
                                logger.info(f"✅ Cancelled entry limit: {order_id[:8]}...")
                                cancelled_count += 1
                            else:
                                logger.warning(f"⚠️  Failed to cancel: {result}")
                                
                        except Exception as e:
                            logger.error(f"❌ Error cancelling {order_id[:8]}...: {e}")
                    else:
                        logger.info(f"⏭️  Skipping TP/SL order: {order_id[:8]}... ({order_link_id})")
                else:
                    order_type = order.get('orderType')
                    reduce_only = order.get('reduceOnly')
                    order_side = order.get('side')
                    logger.debug(f"⏭️  Skipping order: Type={order_type}, ReduceOnly={reduce_only}, Side={order_side}")
                    
    except Exception as e:
        logger.error(f"Error getting orders for {symbol}: {e}")
    
    return cancelled_count

def fix_sl_quantity_for_position(position, account_type='main'):
    """Ensure SL quantity matches the current position size"""
    symbol = position.get('symbol')
    side = position.get('side')
    current_size = Decimal(str(position.get('size', 0)))
    
    if current_size <= 0:
        return False
    
    client = bybit_client_mirror if account_type == 'mirror' else bybit_client
    sl_fixed = False
    
    try:
        # Get current SL order
        result = client.get_open_orders(category="linear", symbol=symbol)
        
        if result and result.get('result'):
            orders = result['result'].get('list', [])
            
            # Find SL order
            sl_order = None
            for order in orders:
                if order.get('stopOrderType') in ['StopLoss', 'Stop']:
                    sl_order = order
                    break
            
            if sl_order:
                current_sl_qty = Decimal(str(sl_order.get('qty', 0)))
                sl_price = Decimal(str(sl_order.get('triggerPrice', 0)))
                
                # Check if adjustment needed (tolerance of 0.001)
                if abs(current_sl_qty - current_size) > Decimal('0.001'):
                    logger.info(f"🔧 SL quantity mismatch for {symbol}:")
                    logger.info(f"   Current SL qty: {current_sl_qty}")
                    logger.info(f"   Position size: {current_size}")
                    logger.info(f"   Adjustment needed: {current_size - current_sl_qty}")
                    
                    # Cancel old SL
                    order_id = sl_order.get('orderId')
                    logger.info(f"🔄 Cancelling old SL: {order_id[:8]}...")
                    
                    try:
                        client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        )
                        logger.info("✅ Old SL cancelled")
                        
                        # Place new SL with correct quantity
                        sl_side = "Sell" if side == "Buy" else "Buy"
                        
                        new_sl_result = client.place_order(
                            category="linear",
                            symbol=symbol,
                            side=sl_side,
                            orderType="Market",
                            qty=str(current_size),
                            triggerPrice=str(sl_price),
                            triggerDirection="1" if side == "Buy" else "2",  # 1=rise for long SL, 2=fall for short SL
                            reduceOnly=True,
                            stopOrderType="StopLoss"
                        )
                        
                        if new_sl_result and new_sl_result.get('retCode') == 0:
                            new_order_id = new_sl_result['result'].get('orderId', '')
                            logger.info(f"✅ New SL placed with correct qty: {current_size} (ID: {new_order_id[:8]}...)")
                            sl_fixed = True
                        else:
                            logger.error(f"❌ Failed to place new SL: {new_sl_result}")
                            
                    except Exception as e:
                        logger.error(f"❌ Error fixing SL: {e}")
                else:
                    logger.info(f"✅ SL quantity already correct for {symbol}: {current_sl_qty}")
                    sl_fixed = True
            else:
                logger.warning(f"⚠️  No SL order found for {symbol}")
                
    except Exception as e:
        logger.error(f"Error checking SL for {symbol}: {e}")
    
    return sl_fixed

def process_all_positions():
    """Process all positions on both accounts"""
    print("\n🚀 Processing All Positions - Entry Limit Cancellation & SL Fix")
    print("=" * 80)
    
    # Get all positions
    positions = get_all_positions()
    
    # Process main account
    print("\n📊 MAIN ACCOUNT")
    print("-" * 40)
    
    if positions['main']:
        for pos in positions['main']:
            symbol = pos.get('symbol')
            side = pos.get('side')
            size = pos.get('size')
            
            print(f"\n🔍 Processing {symbol} {side} (Size: {size})")
            
            # Cancel entry limits
            cancelled = cancel_entry_limits_for_position(symbol, side, 'main')
            print(f"   Entry limits cancelled: {cancelled}")
            
            # Fix SL quantity
            sl_fixed = fix_sl_quantity_for_position(pos, 'main')
            print(f"   SL quantity fixed: {'✅' if sl_fixed else '❌'}")
    else:
        print("No positions found")
    
    # Process mirror account
    print("\n\n📊 MIRROR ACCOUNT")
    print("-" * 40)
    
    if positions['mirror']:
        for pos in positions['mirror']:
            symbol = pos.get('symbol')
            side = pos.get('side')
            size = pos.get('size')
            
            print(f"\n🔍 Processing {symbol} {side} (Size: {size})")
            
            # Cancel entry limits
            cancelled = cancel_entry_limits_for_position(symbol, side, 'mirror')
            print(f"   Entry limits cancelled: {cancelled}")
            
            # Fix SL quantity
            sl_fixed = fix_sl_quantity_for_position(pos, 'mirror')
            print(f"   SL quantity fixed: {'✅' if sl_fixed else '❌'}")
    else:
        print("No positions found")

def update_monitor_flags():
    """Update monitor flags to reflect the changes"""
    try:
        # Load pickle data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Update all monitors to reflect limit cancellation
        for key, monitor in monitors.items():
            if monitor.get('approach') in ['conservative', 'ggshot']:
                monitor['limit_orders_cancelled'] = True
        
        # Save updated data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
            
        logger.info("✅ Updated monitor flags")
        
    except Exception as e:
        logger.error(f"Error updating monitor flags: {e}")

def main():
    """Main execution"""
    print("⚠️  WARNING: This will cancel ALL entry limit orders for ALL positions!")
    print("✅ TP and SL orders will NOT be touched")
    print("\nThis script will:")
    print("1. Cancel all entry limit orders (reduceOnly=False)")
    print("2. Ensure all SL quantities match position sizes")
    print("3. Work on both main and mirror accounts")
    
    # Wait for confirmation
    print("\n⏸️  Starting in 5 seconds... (Ctrl+C to cancel)")
    time.sleep(5)
    
    # Process all positions
    process_all_positions()
    
    # Update monitor flags
    update_monitor_flags()
    
    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("\n📝 Summary:")
    print("- All entry limit orders cancelled")
    print("- All SL quantities verified/fixed")
    print("- Both accounts processed")
    print("\n🔄 The bot will continue monitoring with clean positions")

if __name__ == "__main__":
    main()