#!/usr/bin/env python3
"""
Emergency SL placement - Place SL orders 5% below current market price
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

# Emergency SL percentage below current price
EMERGENCY_SL_PERCENTAGE = 0.05  # 5% below current price

def get_current_price(symbol, client):
    """Get current market price"""
    try:
        result = client.get_tickers(category="linear", symbol=symbol)
        if result and result.get('result'):
            tickers = result['result'].get('list', [])
            if tickers:
                return float(tickers[0].get('lastPrice', 0))
    except Exception as e:
        logger.error(f"Error getting price for {symbol}: {e}")
    return 0

def place_emergency_sl(position, account_type='main'):
    """Place emergency SL order for a position"""
    client = bybit_client_mirror if account_type == 'mirror' else bybit_client
    symbol = position.get('symbol')
    side = position.get('side')
    current_size = float(position.get('size', 0))
    
    if current_size == 0:
        return False
    
    try:
        # Check if SL already exists
        result = client.get_open_orders(category="linear", symbol=symbol)
        if result and result.get('result'):
            orders = result['result'].get('list', [])
            for order in orders:
                if order.get('stopOrderType') in ['StopLoss', 'Stop']:
                    logger.info(f"✅ SL already exists for {symbol} {account_type}")
                    return True
        
        # Get current market price
        current_price = get_current_price(symbol, client)
        if current_price == 0:
            logger.error(f"Could not get current price for {symbol}")
            return False
        
        # Calculate SL price (5% below for long, 5% above for short)
        if side == "Buy":
            sl_price = current_price * (1 - EMERGENCY_SL_PERCENTAGE)
        else:
            sl_price = current_price * (1 + EMERGENCY_SL_PERCENTAGE)
        
        # Get tick size for proper price formatting
        try:
            info_result = client.get_instruments_info(category="linear", symbol=symbol)
            if info_result and info_result['result']:
                tick_size = float(info_result['result']['list'][0]['priceFilter']['tickSize'])
                # Round to tick size
                sl_price = round(sl_price / tick_size) * tick_size
        except:
            pass
        
        sl_side = "Sell" if side == "Buy" else "Buy"
        
        logger.info(f"🚨 Placing emergency SL for {symbol} {account_type}")
        logger.info(f"   Current Price: {current_price}")
        logger.info(f"   SL Price: {sl_price} (5% {'below' if side == 'Buy' else 'above'})")
        logger.info(f"   Quantity: {current_size}")
        
        # Place SL order
        result = client.place_order(
            category="linear",
            symbol=symbol,
            side=sl_side,
            orderType="Market",
            qty=str(current_size),
            triggerPrice=str(sl_price),
            triggerDirection="2" if side == "Buy" else "1",  # 2=fall for long SL, 1=rise for short SL
            reduceOnly=True,
            stopOrderType="StopLoss"
        )
        
        if result and result.get('retCode') == 0:
            order_id = result['result'].get('orderId', '')
            logger.info(f"✅ Emergency SL placed for {symbol} {account_type} (ID: {order_id[:8]}...)")
            return True
        else:
            logger.error(f"❌ Failed to place SL for {symbol}: {result}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error placing SL for {symbol}: {e}")
        return False

def place_all_emergency_sl():
    """Place emergency SL orders for all positions"""
    print("\n🚨 EMERGENCY SL PLACEMENT")
    print("=" * 80)
    print("Placing SL orders 5% below current market prices...")
    print("This is to protect all positions that currently have NO stop loss!")
    
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
    results = {'main': {'placed': 0, 'failed': 0}, 'mirror': {'placed': 0, 'failed': 0}}
    
    for account_type, account_positions in positions.items():
        print(f"\n📊 Processing {account_type.upper()} Account...")
        print("-" * 40)
        
        for pos in account_positions:
            symbol = pos.get('symbol')
            
            success = place_emergency_sl(pos, account_type)
            
            if success:
                results[account_type]['placed'] += 1
            else:
                results[account_type]['failed'] += 1
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 EMERGENCY SL PLACEMENT SUMMARY")
    print("=" * 80)
    print(f"\nMain Account:")
    print(f"  ✅ SL Placed: {results['main']['placed']}")
    print(f"  ❌ Failed: {results['main']['failed']}")
    print(f"\nMirror Account:")
    print(f"  ✅ SL Placed: {results['mirror']['placed']}")
    print(f"  ❌ Failed: {results['mirror']['failed']}")
    print(f"\nTotal:")
    total_placed = results['main']['placed'] + results['mirror']['placed']
    total_failed = results['main']['failed'] + results['mirror']['failed']
    print(f"  ✅ SL Placed: {total_placed}")
    print(f"  ❌ Failed: {total_failed}")
    
    print("\n⚠️  IMPORTANT:")
    print("These are EMERGENCY stop losses placed 5% below current market price.")
    print("You may want to adjust them manually to more appropriate levels.")

def main():
    """Main execution"""
    print("⚠️  EMERGENCY: Placing SL orders for all unprotected positions!")
    print("✅ SL will be placed 5% below current market price")
    print("✅ This is to ensure all positions have protection")
    print("\n⏸️  Starting in 3 seconds... (Ctrl+C to cancel)")
    time.sleep(3)
    
    place_all_emergency_sl()
    
    print("\n✅ Emergency SL placement complete!")
    print("🔄 All positions now have stop loss protection")

if __name__ == "__main__":
    main()