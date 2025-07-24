#!/usr/bin/env python3
"""
Restore SL orders using prices found in trading logs
"""
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

# SL prices extracted from logs (Mirror SL placed messages)
SL_PRICES_FROM_LOGS = {
    # Format: (symbol, side): sl_price
    ('ZRXUSDT', 'Buy'): '0.2049',
    ('HIGHUSDT', 'Buy'): '0.5056', 
    ('WOOUSDT', 'Buy'): '0.06113',
    ('1INCHUSDT', 'Buy'): '0.1743',
    ('CELRUSDT', 'Buy'): '0.007273',
    ('CAKEUSDT', 'Buy'): '2.264',
    ('PENDLEUSDT', 'Buy'): '3.3247',
    ('RENDERUSDT', 'Buy'): '2.969',
    ('PYTHUSDT', 'Buy'): '0.0985',
    ('ENAUSDT', 'Buy'): '0.2484',
    ('ROSEUSDT', 'Buy'): '0.02221',
    ('BOMEUSDT', 'Buy'): '0.001408',
    ('AXSUSDT', 'Buy'): '2.177',
    ('INJUSDT', 'Buy'): '10.497',
    ('ARKMUSDT', 'Buy'): '0.4463',
    ('NKNUSDT', 'Buy'): '0.02259',
    ('TIAUSDT', 'Buy'): '1.452',
    ('RUNEUSDT', 'Buy'): '1.335',
    ('NTRNUSDT', 'Buy'): '0.0809',
}

# Additional SL prices for AUCTIONUSDT (already had correct SL)
# We'll use a standard 3% below entry for any missing
STANDARD_SL_PERCENTAGE = 0.03  # 3%

def restore_sl_order(symbol, side, sl_price, account_type='main'):
    """Restore a single SL order"""
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
        avg_price = 0
        
        if pos_result and pos_result.get('result'):
            for pos in pos_result['result'].get('list', []):
                if pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0:
                    current_size = float(pos.get('size'))
                    avg_price = float(pos.get('avgPrice', 0))
                    break
        
        if current_size == 0:
            logger.warning(f"No position found for {symbol} {account_type}")
            return False
        
        # If no SL price provided, calculate based on entry
        if not sl_price and avg_price > 0:
            sl_price = str(avg_price * (1 - STANDARD_SL_PERCENTAGE))
            logger.info(f"Using calculated SL price for {symbol}: {sl_price} (3% below {avg_price})")
        
        sl_side = "Sell" if side == "Buy" else "Buy"
        
        logger.info(f"🔄 Restoring SL for {symbol} {account_type}")
        logger.info(f"   Price: {sl_price}, Qty: {current_size}")
        
        # Place SL order
        result = client.place_order(
            category="linear",
            symbol=symbol,
            side=sl_side,
            orderType="Market",
            qty=str(current_size),
            triggerPrice=str(sl_price),
            triggerDirection="1" if side == "Buy" else "2",
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

def restore_all_positions():
    """Restore SL orders for all positions"""
    print("\n🚨 EMERGENCY SL RESTORATION")
    print("=" * 80)
    print("Restoring SL orders using prices from trading logs...")
    
    # Get all positions
    positions = {'main': [], 'mirror': []}
    
    try:
        # Get main account positions
        main_result = bybit_client.get_positions(category="linear", settleCoin="USDT")
        if main_result and main_result.get('result'):
            for pos in main_result['result'].get('list', []):
                if float(pos.get('size', 0)) > 0:
                    positions['main'].append(pos)
        
        # Get mirror account positions
        if bybit_client_mirror:
            mirror_result = bybit_client_mirror.get_positions(category="linear", settleCoin="USDT")
            if mirror_result and mirror_result.get('result'):
                for pos in mirror_result['result'].get('list', []):
                    if float(pos.get('size', 0)) > 0:
                        positions['mirror'].append(pos)
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
    
    # Process each account
    results = {'main': {'restored': 0, 'failed': 0}, 'mirror': {'restored': 0, 'failed': 0}}
    
    for account_type, account_positions in positions.items():
        print(f"\n📊 Processing {account_type.upper()} Account...")
        
        for pos in account_positions:
            symbol = pos.get('symbol')
            side = pos.get('side')
            
            # Get SL price from logs
            sl_price = SL_PRICES_FROM_LOGS.get((symbol, side))
            
            success = restore_sl_order(symbol, side, sl_price, account_type)
            
            if success:
                results[account_type]['restored'] += 1
            else:
                results[account_type]['failed'] += 1
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 RESTORATION SUMMARY")
    print("=" * 80)
    print(f"\nMain Account:")
    print(f"  ✅ Restored: {results['main']['restored']}")
    print(f"  ❌ Failed: {results['main']['failed']}")
    print(f"\nMirror Account:")
    print(f"  ✅ Restored: {results['mirror']['restored']}")
    print(f"  ❌ Failed: {results['mirror']['failed']}")
    print(f"\nTotal:")
    total_restored = results['main']['restored'] + results['mirror']['restored']
    total_failed = results['main']['failed'] + results['mirror']['failed']
    print(f"  ✅ Restored: {total_restored}")
    print(f"  ❌ Failed: {total_failed}")

def main():
    """Main execution"""
    print("⚠️  EMERGENCY: Restoring all SL orders!")
    print("✅ Using SL prices found in trading logs")
    print("✅ SL quantities will match current position sizes")
    print("\n⏸️  Starting in 3 seconds... (Ctrl+C to cancel)")
    time.sleep(3)
    
    restore_all_positions()
    
    print("\n✅ SL restoration complete!")
    print("🔄 The bot will continue monitoring with restored SL orders")

if __name__ == "__main__":
    main()