#!/usr/bin/env python3
"""
Preview what entry limit orders will be cancelled and what SL quantities need fixing
SAFE - This only shows what would be done, doesn't execute anything
"""
#!/usr/bin/env python3
"""
Preview what entry limit orders will be cancelled and what SL quantities need fixing
SAFE - This only shows what would be done, doesn't execute anything
"""
from decimal import Decimal
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
import logging
# from tabulate import tabulate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_position(symbol, side, size, account_type='main'):
    """Analyze a single position for entry limits and SL issues"""
    client = bybit_client_mirror if account_type == 'mirror' else bybit_client
    
    entry_limits = []
    sl_info = None
    tp_orders = []
    
    try:
        # Get all open orders
        result = client.get_open_orders(category="linear", symbol=symbol)
        
        if result and result.get('result'):
            orders = result['result'].get('list', [])
            
            for order in orders:
                order_type = order.get('orderType')
                reduce_only = order.get('reduceOnly')
                order_side = order.get('side')
                order_id = order.get('orderId', '')[:8] + '...'
                order_link_id = order.get('orderLinkId', '')
                qty = order.get('qty')
                price = order.get('price') or order.get('triggerPrice')
                
                # Identify order category
                if order.get('stopOrderType') in ['StopLoss', 'Stop']:
                    sl_info = {
                        'id': order_id,
                        'qty': qty,
                        'price': price,
                        'needs_fix': abs(Decimal(qty) - Decimal(size)) > Decimal('0.001')
                    }
                elif order.get('stopOrderType') in ['TakeProfit']:
                    tp_orders.append({
                        'id': order_id,
                        'qty': qty,
                        'price': price,
                        'link_id': order_link_id
                    })
                elif order_type == 'Limit' and not reduce_only and order_side == side:
                    # This is an entry limit order
                    if 'TP' not in order_link_id.upper() and 'SL' not in order_link_id.upper():
                        entry_limits.append({
                            'id': order_id,
                            'qty': qty,
                            'price': price,
                            'link_id': order_link_id
                        })
                        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
    
    return entry_limits, sl_info, tp_orders

def analyze_all_positions():
    """Analyze all positions on both accounts"""
    print("\n🔍 POSITION ANALYSIS - Entry Limits & SL Status")
    print("=" * 100)
    
    accounts = {
        'main': {'client': bybit_client, 'positions': []},
        'mirror': {'client': bybit_client_mirror, 'positions': []}
    }
    
    # Fetch positions for both accounts
    for account_type, account_data in accounts.items():
        try:
            result = account_data['client'].get_positions(category="linear", settleCoin="USDT")
            if result and result.get('result'):
                for pos in result['result'].get('list', []):
                    if float(pos.get('size', 0)) > 0:
                        account_data['positions'].append(pos)
        except Exception as e:
            logger.error(f"Error fetching {account_type} positions: {e}")
    
    # Analyze each account
    for account_type, account_data in accounts.items():
        print(f"\n\n{'='*40} {account_type.upper()} ACCOUNT {'='*40}")
        
        if not account_data['positions']:
            print("No active positions found")
            continue
        
        all_entry_limits = []
        sl_issues = []
        
        for pos in account_data['positions']:
            symbol = pos.get('symbol')
            side = pos.get('side')
            size = pos.get('size')
            
            print(f"\n📊 {symbol} {side} - Position Size: {size}")
            
            # Analyze position
            entry_limits, sl_info, tp_orders = analyze_position(symbol, side, size, account_type)
            
            # Show entry limits to be cancelled
            if entry_limits:
                print(f"\n   🚫 Entry Limit Orders to Cancel ({len(entry_limits)}):")
                for limit in entry_limits:
                    print(f"      - ID: {limit['id']} | Qty: {limit['qty']} | Price: {limit['price']} | LinkID: {limit['link_id']}")
                    all_entry_limits.append([symbol, limit['id'], limit['qty'], limit['price']])
            else:
                print("   ✅ No entry limit orders found")
            
            # Show SL status
            if sl_info:
                if sl_info['needs_fix']:
                    print(f"\n   ⚠️  SL Quantity Mismatch:")
                    print(f"      - Current SL Qty: {sl_info['qty']}")
                    print(f"      - Position Size: {size}")
                    print(f"      - Needs adjustment: YES")
                    sl_issues.append([symbol, sl_info['qty'], size, "YES"])
                else:
                    print(f"\n   ✅ SL Quantity Correct: {sl_info['qty']}")
            else:
                print("\n   ❌ No SL order found!")
                sl_issues.append([symbol, "None", size, "MISSING"])
            
            # Show TP orders (won't be touched)
            if tp_orders:
                print(f"\n   ✅ TP Orders (Will NOT be touched): {len(tp_orders)}")
                for tp in tp_orders[:2]:  # Show first 2
                    print(f"      - ID: {tp['id']} | Qty: {tp['qty']} | Price: {tp['price']}")
                if len(tp_orders) > 2:
                    print(f"      ... and {len(tp_orders) - 2} more")
        
        # Summary tables
        if all_entry_limits:
            print(f"\n\n📋 {account_type.upper()} - Entry Limits to Cancel Summary:")
            # print(tabulate(all_entry_limits, headers=['Symbol', 'Order ID', 'Quantity', 'Price'], tablefmt='grid'))
            print("\n".join([f"   {item[0]} | {item[1]} | {item[2]} | {item[3]}" for item in all_entry_limits]))
        
        if sl_issues:
            print(f"\n📋 {account_type.upper()} - SL Issues Summary:")
            # print(tabulate(sl_issues, headers=['Symbol', 'Current SL Qty', 'Position Size', 'Needs Fix'], tablefmt='grid'))
            print("\n".join([f"   {item[0]} | {item[1]} | {item[2]} | {item[3]}" for item in sl_issues]))

def main():
    """Main execution"""
    print("🔍 DRY RUN - Entry Limit & SL Analysis")
    print("This will show what needs to be done WITHOUT making any changes\n")
    
    analyze_all_positions()
    
    print("\n\n" + "="*100)
    print("📝 SUMMARY")
    print("="*100)
    print("\nThis preview shows:")
    print("1. Which entry limit orders would be cancelled")
    print("2. Which SL orders need quantity adjustment")
    print("3. Which TP orders exist (these will NOT be touched)")
    
    print("\n⚠️  To execute these changes, run:")
    print("   python3 cancel_all_entry_limits_fix_sl.py")
    
    print("\n✅ Preview complete - No changes were made")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Preview cancelled by user")