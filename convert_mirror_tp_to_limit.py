#!/usr/bin/env python3
"""
Convert mirror account stop market TP orders to limit orders
"""
import pickle
import asyncio
import time
from decimal import Decimal
from datetime import datetime
import shutil
import sys
sys.path.append('/Users/lualakol/bybit-telegram-bot')

from clients.bybit_helpers import api_call_with_retry
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from config.constants import BOT_PREFIX

async def convert_mirror_tp_to_limit():
    """Convert stop market TP orders to limit orders"""
    
    if not is_mirror_trading_enabled() or not bybit_client_2:
        print("Mirror trading not enabled")
        return
    
    # Create backup
    print("Creating backup...")
    backup_filename = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_limit_conversion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_filename)
    print(f"Backup created: {backup_filename}")
    
    # Load pickle file
    print("\nLoading pickle file...")
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
        data = pickle.load(f)
    
    enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
    
    # Process each mirror monitor
    print("\n" + "="*80)
    print("CONVERTING MIRROR TP ORDERS TO LIMIT ORDERS")
    print("="*80)
    
    conversion_results = {}
    
    for monitor_key, monitor_data in enhanced_monitors.items():
        if not monitor_key.endswith('_mirror'):
            continue
        
        symbol = monitor_data.get('symbol')
        side = monitor_data.get('side')
        tp_orders = monitor_data.get('tp_orders', {})
        
        if not tp_orders:
            print(f"\n{monitor_key}: No TP orders to convert")
            continue
        
        print(f"\n{monitor_key}: Converting {len(tp_orders)} TP orders")
        conversion_results[monitor_key] = []
        
        # Determine order side for TPs (opposite of position)
        tp_side = "Sell" if side == "Buy" else "Buy"
        
        # Process each TP order
        new_tp_orders = {}
        
        for old_order_id, tp_data in tp_orders.items():
            tp_number = tp_data.get('tp_number')
            price = tp_data.get('price')
            quantity = tp_data.get('quantity')
            
            print(f"\n  Converting TP{tp_number}:")
            print(f"    Old Order ID: {old_order_id[:12]}...")
            print(f"    Price: {price}")
            print(f"    Quantity: {quantity}")
            
            try:
                # Step 1: Cancel the stop market order
                print(f"    Cancelling stop market order...")
                cancel_response = await api_call_with_retry(
                    lambda: bybit_client_2.cancel_order(
                        category="linear",
                        symbol=symbol,
                        orderId=old_order_id
                    )
                )
                
                if cancel_response and cancel_response.get("retCode") == 0:
                    print(f"    ✅ Cancelled successfully")
                else:
                    print(f"    ⚠️  Cancel failed: {cancel_response}")
                    continue
                
                # Step 2: Place new limit order
                print(f"    Placing new limit order...")
                
                # Generate order link ID
                order_link_id = f"{BOT_PREFIX}MIR_TP{tp_number}_{symbol}_{int(time.time() * 1000)}"
                
                place_response = await api_call_with_retry(
                    lambda: bybit_client_2.place_order(
                        category="linear",
                        symbol=symbol,
                        side=tp_side,
                        orderType="Limit",
                        qty=str(quantity),
                        price=str(price),
                        reduceOnly=True,
                        orderLinkId=order_link_id,
                        timeInForce="GTC"
                    )
                )
                
                if place_response and place_response.get("retCode") == 0:
                    new_order_id = place_response.get("result", {}).get("orderId")
                    print(f"    ✅ New limit order placed: {new_order_id[:12]}...")
                    
                    # Update TP data
                    new_tp_orders[new_order_id] = {
                        'order_id': new_order_id,
                        'order_link_id': order_link_id,
                        'price': price,
                        'quantity': quantity,
                        'original_quantity': quantity,
                        'percentage': tp_data.get('percentage'),
                        'tp_number': tp_number,
                        'account': 'mirror',
                        'order_type': 'limit'  # Now it's a limit order
                    }
                    
                    conversion_results[monitor_key].append({
                        'tp_number': tp_number,
                        'old_id': old_order_id,
                        'new_id': new_order_id,
                        'status': 'success'
                    })
                else:
                    print(f"    ❌ Failed to place limit order: {place_response}")
                    conversion_results[monitor_key].append({
                        'tp_number': tp_number,
                        'old_id': old_order_id,
                        'status': 'failed',
                        'error': str(place_response)
                    })
                    
            except Exception as e:
                print(f"    ❌ Error during conversion: {e}")
                conversion_results[monitor_key].append({
                    'tp_number': tp_number,
                    'old_id': old_order_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        # Update monitor with new TP orders
        if new_tp_orders:
            monitor_data['tp_orders'] = new_tp_orders
            print(f"\n  Updated monitor with {len(new_tp_orders)} new limit orders")
    
    # Save updated pickle
    print("\n" + "="*80)
    print("SAVING UPDATED PICKLE FILE")
    print("="*80)
    
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    print("✅ Pickle file updated")
    
    # Summary
    print("\n" + "="*80)
    print("CONVERSION SUMMARY")
    print("="*80)
    
    total_success = 0
    total_failed = 0
    
    for monitor_key, results in conversion_results.items():
        success_count = sum(1 for r in results if r['status'] == 'success')
        failed_count = len(results) - success_count
        total_success += success_count
        total_failed += failed_count
        
        print(f"\n{monitor_key}:")
        print(f"  Successful conversions: {success_count}")
        print(f"  Failed conversions: {failed_count}")
        
        if failed_count > 0:
            print("  Failed orders:")
            for r in results:
                if r['status'] != 'success':
                    print(f"    TP{r['tp_number']}: {r.get('error', 'Unknown error')}")
    
    print(f"\nTotal: {total_success} successful, {total_failed} failed")
    print(f"\nBackup saved as: {backup_filename}")

if __name__ == "__main__":
    asyncio.run(convert_mirror_tp_to_limit())