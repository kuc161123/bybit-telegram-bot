#!/usr/bin/env python3
"""
Summary of position cleanup status
"""
from clients.bybit_client import bybit_client
import os
from pybit.unified_trading import HTTP

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

def check_position_status(symbol, account_type='main'):
    """Check complete status of a position"""
    client = bybit_client_mirror if account_type == 'mirror' else bybit_client
    
    status = {
        'has_sl': False,
        'has_tp': False,
        'has_entry_limits': False,
        'sl_qty': 0,
        'position_size': 0,
        'tp_count': 0,
        'limit_count': 0
    }
    
    try:
        # Get position
        pos_result = client.get_positions(category="linear", symbol=symbol)
        if pos_result and pos_result.get('result'):
            for pos in pos_result['result'].get('list', []):
                if float(pos.get('size', 0)) > 0:
                    status['position_size'] = pos.get('size')
                    break
        
        # Get orders
        order_result = client.get_open_orders(category="linear", symbol=symbol)
        if order_result and order_result.get('result'):
            orders = order_result['result'].get('list', [])
            
            for order in orders:
                if order.get('stopOrderType') in ['StopLoss', 'Stop']:
                    status['has_sl'] = True
                    status['sl_qty'] = order.get('qty')
                elif order.get('stopOrderType') == 'TakeProfit':
                    status['has_tp'] = True
                    status['tp_count'] += 1
                elif order.get('orderType') == 'Limit' and not order.get('reduceOnly'):
                    status['has_entry_limits'] = True
                    status['limit_count'] += 1
                    
    except Exception as e:
        print(f"Error checking {symbol}: {e}")
    
    return status

def generate_summary():
    """Generate comprehensive summary"""
    print("\n" + "="*80)
    print("📊 POSITION CLEANUP SUMMARY")
    print("="*80)
    
    print("\n✅ WHAT WAS DONE:")
    print("1. ✅ Cancelled ALL entry limit orders:")
    print("   - Main Account: 36 entry limits cancelled")
    print("   - Mirror Account: 32 entry limits cancelled")
    print("\n2. ❌ SL Quantity Fix (Partially successful):")
    print("   - Main Account: 1/20 SLs fixed")
    print("   - Mirror Account: 8/20 SLs fixed")
    print("   - Issue: Many positions have NO SL orders at all!")
    
    print("\n⚠️  CRITICAL ISSUES FOUND:")
    print("1. Main Account: 19 positions have NO SL orders")
    print("2. Mirror Account: 12 positions have NO SL orders")
    print("3. These positions are at RISK without stop loss protection!")
    
    print("\n🔧 WHAT NEEDS TO BE DONE:")
    print("1. Create missing SL orders for all positions without SL")
    print("2. Fix SL quantities for positions that have incorrect quantities")
    print("3. Verify all TP orders are in place")
    
    print("\n📝 POSITIONS WITHOUT SL (Main Account):")
    no_sl_main = ['NKNUSDT', 'NTRNUSDT', 'PYTHUSDT', 'ZRXUSDT', 'BOMEUSDT', 
                  'HIGHUSDT', 'RENDERUSDT', 'INJUSDT', '1INCHUSDT', 'AXSUSDT',
                  'ARKMUSDT', 'RUNEUSDT', 'CELRUSDT', 'ENAUSDT', 'PENDLEUSDT',
                  'WOOUSDT', 'TIAUSDT', 'CAKEUSDT', 'ROSEUSDT']
    for symbol in no_sl_main:
        print(f"   - {symbol}")
    
    print("\n📝 POSITIONS WITHOUT SL (Mirror Account):")
    no_sl_mirror = ['NTRNUSDT', 'ZRXUSDT', 'BOMEUSDT', 'HIGHUSDT', 'INJUSDT',
                    '1INCHUSDT', 'AXSUSDT', 'NKNUSDT', 'ARKMUSDT', 'CELRUSDT',
                    'WOOUSDT', 'CAKEUSDT']
    for symbol in no_sl_mirror:
        print(f"   - {symbol}")
    
    print("\n⚠️  BOMEUSDT SPECIAL CASE:")
    print("- TP1 already hit but SL was NOT moved to breakeven")
    print("- Limit orders were NOT cancelled on main account")
    print("- Both main and mirror have NO SL orders now!")
    
    print("\n🚨 URGENT ACTION REQUIRED:")
    print("These positions need immediate SL order creation to protect against losses!")
    print("\n" + "="*80)

def check_sample_positions():
    """Check a few sample positions for detailed status"""
    print("\n🔍 SAMPLE POSITION CHECKS:")
    print("-" * 40)
    
    # Check BOMEUSDT on both accounts
    print("\nBOMEUSDT Status:")
    main_status = check_position_status('BOMEUSDT', 'main')
    mirror_status = check_position_status('BOMEUSDT', 'mirror')
    
    print(f"Main Account:")
    print(f"  Position Size: {main_status['position_size']}")
    print(f"  Has SL: {'✅' if main_status['has_sl'] else '❌'}")
    print(f"  Has TP: {'✅' if main_status['has_tp'] else '❌'} ({main_status['tp_count']} orders)")
    print(f"  Entry Limits: {main_status['limit_count']} remaining")
    
    print(f"\nMirror Account:")
    print(f"  Position Size: {mirror_status['position_size']}")
    print(f"  Has SL: {'✅' if mirror_status['has_sl'] else '❌'}")
    print(f"  Has TP: {'✅' if mirror_status['has_tp'] else '❌'} ({mirror_status['tp_count']} orders)")
    print(f"  Entry Limits: {mirror_status['limit_count']} remaining")

def main():
    generate_summary()
    check_sample_positions()
    
    print("\n\n💡 RECOMMENDATION:")
    print("Run a script to create missing SL orders for all positions")
    print("based on the original entry prices and standard SL percentages.")

if __name__ == "__main__":
    main()