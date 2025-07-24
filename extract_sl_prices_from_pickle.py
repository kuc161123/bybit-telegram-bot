#!/usr/bin/env python3
"""
Extract original SL prices from pickle file
"""
import pickle
from decimal import Decimal
import json

def extract_sl_prices():
    """Extract all SL prices from monitor data"""
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        sl_prices = {'main': {}, 'mirror': {}}
        
        print("🔍 Extracting SL prices from monitor data...")
        print("=" * 80)
        
        for monitor_key, monitor_data in monitors.items():
            symbol = monitor_data.get('symbol')
            side = monitor_data.get('side')
            account_type = monitor_data.get('account_type', 'main')
            
            # Get SL orders
            sl_orders = monitor_data.get('sl_orders', {})
            
            if sl_orders:
                # Get first SL order (should be only one)
                sl_id, sl_info = next(iter(sl_orders.items()), (None, None))
                if sl_info:
                    sl_price = sl_info.get('price')
                    sl_qty = sl_info.get('qty')
                    
                    key = f"{symbol}_{side}"
                    sl_prices[account_type][key] = {
                        'price': str(sl_price) if sl_price else None,
                        'qty': str(sl_qty) if sl_qty else None,
                        'monitor_key': monitor_key
                    }
                    
                    print(f"\n{account_type.upper()} - {symbol} {side}:")
                    print(f"  SL Price: {sl_price}")
                    print(f"  SL Qty: {sl_qty}")
                    print(f"  Monitor Key: {monitor_key}")
        
        # Save to JSON for easy access
        with open('sl_prices_backup.json', 'w') as f:
            json.dump(sl_prices, f, indent=2)
        
        print("\n" + "=" * 80)
        print("✅ SL prices extracted and saved to sl_prices_backup.json")
        
        # Summary
        print(f"\nSummary:")
        print(f"Main Account: {len(sl_prices['main'])} SL prices found")
        print(f"Mirror Account: {len(sl_prices['mirror'])} SL prices found")
        
        return sl_prices
        
    except Exception as e:
        print(f"❌ Error extracting SL prices: {e}")
        return None

def main():
    sl_prices = extract_sl_prices()
    
    if sl_prices:
        print("\n📋 SL Prices by Symbol:")
        print("\nMAIN ACCOUNT:")
        for key, info in sl_prices['main'].items():
            print(f"  {key}: {info['price']}")
        
        print("\nMIRROR ACCOUNT:")
        for key, info in sl_prices['mirror'].items():
            print(f"  {key}: {info['price']}")

if __name__ == "__main__":
    main()