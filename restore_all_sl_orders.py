#!/usr/bin/env python3
"""
EMERGENCY: Restore all SL orders from monitor data
"""
import pickle
from decimal import Decimal
from clients.bybit_client import bybit_client
import os
from pybit.unified_trading import HTTP
import time
import logging

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_monitor_data():
    """Get monitor data from pickle file"""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        return monitors
    except Exception as e:
        logger.error(f"Error reading monitor data: {e}")
        return {}

def restore_sl_for_position(monitor_key, monitor_data):
    """Restore SL order for a position"""
    symbol = monitor_data.get('symbol')
    side = monitor_data.get('side')
    account_type = monitor_data.get('account_type', 'main')
    
    # Get SL info from monitor
    sl_orders = monitor_data.get('sl_orders', {})
    if not sl_orders:
        logger.warning(f"No SL data found for {symbol}")
        return False
    
    # Get first (should be only) SL order
    sl_id, sl_info = next(iter(sl_orders.items()), (None, None))
    if not sl_info:
        logger.warning(f"No SL info found for {symbol}")
        return False
    
    sl_price = sl_info.get('price')
    sl_qty = sl_info.get('qty')
    
    if not sl_price or not sl_qty:
        logger.warning(f"Invalid SL data for {symbol}: price={sl_price}, qty={sl_qty}")
        return False
    
    client = bybit_client_mirror if account_type == 'mirror' else bybit_client
    
    try:
        # Check if SL already exists
        result = client.get_open_orders(category="linear", symbol=symbol)
        if result and result.get('result'):
            orders = result['result'].get('list', [])
            for order in orders:
                if order.get('stopOrderType') in ['StopLoss', 'Stop']:
                    logger.info(f"✅ SL already exists for {symbol} {account_type}")
                    return True
        
        # Get current position
        pos_result = client.get_positions(category="linear", symbol=symbol)
        current_size = 0
        if pos_result and pos_result.get('result'):
            for pos in pos_result['result'].get('list', []):
                if pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0:
                    current_size = float(pos.get('size'))
                    break
        
        if current_size == 0:
            logger.warning(f"No position found for {symbol} {account_type}")
            return False
        
        # Use current position size for SL quantity
        sl_side = "Sell" if side == "Buy" else "Buy"
        
        logger.info(f"🔄 Restoring SL for {symbol} {account_type}")
        logger.info(f"   Price: {sl_price}, Qty: {current_size} (position size)")
        
        # Place SL order
        result = client.place_order(
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
        
        if result and result.get('retCode') == 0:
            order_id = result['result'].get('orderId', '')
            logger.info(f"✅ SL restored for {symbol} {account_type} (ID: {order_id[:8]}...)")
            return True
        else:
            logger.error(f"❌ Failed to restore SL for {symbol}: {result}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error restoring SL for {symbol}: {e}")
        return False

def restore_all_sl_orders():
    """Restore all SL orders from monitor data"""
    print("\n🚨 EMERGENCY SL RESTORATION")
    print("=" * 80)
    print("Restoring all SL orders from saved monitor data...")
    
    monitors = get_monitor_data()
    if not monitors:
        print("❌ No monitor data found!")
        return
    
    main_restored = 0
    main_failed = 0
    mirror_restored = 0
    mirror_failed = 0
    
    for monitor_key, monitor_data in monitors.items():
        account_type = monitor_data.get('account_type', 'main')
        
        success = restore_sl_for_position(monitor_key, monitor_data)
        
        if account_type == 'main':
            if success:
                main_restored += 1
            else:
                main_failed += 1
        else:
            if success:
                mirror_restored += 1
            else:
                mirror_failed += 1
        
        # Small delay to avoid rate limits
        time.sleep(0.5)
    
    print("\n" + "=" * 80)
    print("📊 RESTORATION SUMMARY")
    print("=" * 80)
    print(f"\nMain Account:")
    print(f"  ✅ Restored: {main_restored}")
    print(f"  ❌ Failed: {main_failed}")
    print(f"\nMirror Account:")
    print(f"  ✅ Restored: {mirror_restored}")
    print(f"  ❌ Failed: {mirror_failed}")
    print(f"\nTotal:")
    print(f"  ✅ Restored: {main_restored + mirror_restored}")
    print(f"  ❌ Failed: {main_failed + mirror_failed}")

def main():
    """Main execution"""
    print("⚠️  EMERGENCY: This will restore all missing SL orders!")
    print("✅ Using saved monitor data to restore original SL prices")
    print("✅ SL quantities will match current position sizes")
    print("\n⏸️  Starting in 3 seconds... (Ctrl+C to cancel)")
    time.sleep(3)
    
    restore_all_sl_orders()
    
    print("\n✅ SL restoration complete!")
    print("🔄 The bot will continue monitoring with restored SL orders")

if __name__ == "__main__":
    main()