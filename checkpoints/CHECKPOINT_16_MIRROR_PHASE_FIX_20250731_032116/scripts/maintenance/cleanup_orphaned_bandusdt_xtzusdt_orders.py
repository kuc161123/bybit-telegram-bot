#!/usr/bin/env python3
"""
Clean up orphaned BANDUSDT and XTZUSDT orders
Remove all remaining orders for closed positions
"""
import asyncio
import sys
import os
from typing import List, Dict

# Add project root to path
sys.path.insert(0, '/Users/lualakol/bybit-telegram-bot')

async def cleanup_orphaned_orders():
    """Clean up all orphaned BANDUSDT and XTZUSDT orders"""
    try:
        print("🧹 CLEANING UP ORPHANED BANDUSDT & XTZUSDT ORDERS")
        print("=" * 60)
        
        # Import required modules
        from clients.bybit_helpers import get_all_open_orders
        from clients.bybit_client import bybit_client
        from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled, cancel_mirror_order
        
        target_symbols = ['BANDUSDT', 'XTZUSDT']
        
        # 1. GET ALL CURRENT ORDERS
        print("\n📋 FINDING ORPHANED ORDERS:")
        print("-" * 40)
        
        main_orders = await get_all_open_orders(bybit_client)
        mirror_orders = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_orders = await get_all_open_orders(bybit_client_2)
        
        orphaned_orders = {'main': [], 'mirror': []}
        
        # Find all BANDUSDT and XTZUSDT orders
        for order in main_orders:
            symbol = order.get('symbol', '')
            if symbol in target_symbols:
                orphaned_orders['main'].append({
                    'symbol': symbol,
                    'orderId': order.get('orderId', ''),
                    'orderLinkId': order.get('orderLinkId', ''),
                    'qty': order.get('qty', '0'),
                    'price': order.get('price', '0'),
                    'side': order.get('side', ''),
                    'orderType': order.get('orderType', ''),
                    'orderStatus': order.get('orderStatus', '')
                })
                
                order_type = "TP" if 'TP' in order.get('orderLinkId', '') else "SL" if 'SL' in order.get('orderLinkId', '') else "LIMIT"
                print(f"📋 MAIN {symbol} {order_type}: {order.get('qty')} @ {order.get('price')} (ID: {order.get('orderId', '')[:8]}...)")
        
        for order in mirror_orders:
            symbol = order.get('symbol', '')
            if symbol in target_symbols:
                orphaned_orders['mirror'].append({
                    'symbol': symbol,
                    'orderId': order.get('orderId', ''),
                    'orderLinkId': order.get('orderLinkId', ''),
                    'qty': order.get('qty', '0'),
                    'price': order.get('price', '0'),
                    'side': order.get('side', ''),
                    'orderType': order.get('orderType', ''),
                    'orderStatus': order.get('orderStatus', '')
                })
                
                order_type = "TP" if 'TP' in order.get('orderLinkId', '') else "SL" if 'SL' in order.get('orderLinkId', '') else "LIMIT"
                print(f"📋 MIRROR {symbol} {order_type}: {order.get('qty')} @ {order.get('price')} (ID: {order.get('orderId', '')[:8]}...)")
        
        total_orphaned = len(orphaned_orders['main']) + len(orphaned_orders['mirror'])
        print(f"\n📊 Found {total_orphaned} orphaned orders to clean up")
        print(f"   Main account: {len(orphaned_orders['main'])} orders")
        print(f"   Mirror account: {len(orphaned_orders['mirror'])} orders")
        
        if total_orphaned == 0:
            print("✅ No orphaned orders found - cleanup not needed")
            return
        
        # 2. CANCEL ALL ORPHANED ORDERS
        print("\n🗑️ CANCELLING ORPHANED ORDERS:")
        print("-" * 40)
        
        cancelled_count = 0
        failed_count = 0
        
        # Cancel main account orders
        if orphaned_orders['main']:
            print(f"\n🗑️ Cancelling {len(orphaned_orders['main'])} main account orders...")
            
            for order in orphaned_orders['main']:
                try:
                    symbol = order['symbol']
                    order_id = order['orderId']
                    order_link_id = order['orderLinkId']
                    
                    # Cancel using direct API call
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda: bybit_client.cancel_order(
                            category="linear",
                            symbol=symbol,
                            orderId=order_id
                        )
                    )
                    
                    if response and response.get("retCode") == 0:
                        print(f"  ✅ Cancelled MAIN {symbol}: {order_link_id}")
                        cancelled_count += 1
                    else:
                        print(f"  ❌ Failed to cancel MAIN {symbol}: {order_link_id} - {response}")
                        failed_count += 1
                        
                except Exception as e:
                    print(f"  ❌ Error cancelling MAIN {order['symbol']}: {order['orderLinkId']} - {e}")
                    failed_count += 1
                
                # Small delay between cancellations
                await asyncio.sleep(0.2)
        
        # Cancel mirror account orders
        if orphaned_orders['mirror']:
            print(f"\n🗑️ Cancelling {len(orphaned_orders['mirror'])} mirror account orders...")
            
            for order in orphaned_orders['mirror']:
                try:
                    symbol = order['symbol']
                    order_id = order['orderId']
                    order_link_id = order['orderLinkId']
                    
                    # Cancel using mirror function
                    success = await cancel_mirror_order(symbol, order_id)
                    
                    if success:
                        print(f"  ✅ Cancelled MIRROR {symbol}: {order_link_id}")
                        cancelled_count += 1
                    else:
                        print(f"  ❌ Failed to cancel MIRROR {symbol}: {order_link_id}")
                        failed_count += 1
                        
                except Exception as e:
                    print(f"  ❌ Error cancelling MIRROR {order['symbol']}: {order['orderLinkId']} - {e}")
                    failed_count += 1
                
                # Small delay between cancellations
                await asyncio.sleep(0.2)
        
        # 3. VERIFICATION
        print("\n📊 VERIFICATION - CHECK FOR REMAINING ORDERS:")
        print("-" * 50)
        
        # Wait a moment for cancellations to process
        await asyncio.sleep(2)
        
        # Check if any orders remain
        main_orders_after = await get_all_open_orders(bybit_client)
        mirror_orders_after = []
        if is_mirror_trading_enabled() and bybit_client_2:
            mirror_orders_after = await get_all_open_orders(bybit_client_2)
        
        remaining_main = [o for o in main_orders_after if o.get('symbol') in target_symbols]
        remaining_mirror = [o for o in mirror_orders_after if o.get('symbol') in target_symbols]
        
        total_remaining = len(remaining_main) + len(remaining_mirror)
        
        if total_remaining == 0:
            print("✅ All BANDUSDT and XTZUSDT orders successfully cleaned up")
        else:
            print(f"⚠️ {total_remaining} orders still remain:")
            for order in remaining_main:
                print(f"  MAIN {order.get('symbol')}: {order.get('orderLinkId')} (Status: {order.get('orderStatus')})")
            for order in remaining_mirror:
                print(f"  MIRROR {order.get('symbol')}: {order.get('orderLinkId')} (Status: {order.get('orderStatus')})")
        
        # 4. UPDATE ENHANCED TP/SL MONITORS
        print("\n📊 CLEANING UP MONITOR DATA:")
        print("-" * 40)
        
        try:
            import pickle
            import time
            
            pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
            
            # Create backup
            backup_path = f"{pkl_path}.backup_cleanup_{int(time.time())}"
            import shutil
            shutil.copy2(pkl_path, backup_path)
            
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            
            bot_data = data.get('bot_data', {})
            monitors = bot_data.get('enhanced_tp_sl_monitors', {})
            
            # Remove monitors for closed positions
            monitors_to_remove = []
            for monitor_key in monitors.keys():
                if any(symbol in monitor_key for symbol in target_symbols):
                    monitors_to_remove.append(monitor_key)
            
            for monitor_key in monitors_to_remove:
                removed_monitor = monitors.pop(monitor_key, None)
                if removed_monitor:
                    symbol = removed_monitor.get('symbol', 'UNKNOWN')
                    account = 'MIRROR' if 'MIRROR' in monitor_key else 'MAIN'
                    print(f"🗑️ Removed {symbol} {account} monitor")
            
            # Save updated data
            data['bot_data']['enhanced_tp_sl_monitors'] = monitors
            with open(pkl_path, 'wb') as f:
                pickle.dump(data, f)
            
            print(f"✅ Removed {len(monitors_to_remove)} monitors from Enhanced TP/SL system")
            
        except Exception as e:
            print(f"❌ Error cleaning monitor data: {e}")
        
        # 5. SUMMARY
        print("\n📊 CLEANUP SUMMARY:")
        print("-" * 30)
        print(f"✅ Orders Cancelled: {cancelled_count}")
        print(f"❌ Failed Cancellations: {failed_count}")
        print(f"🗑️ Monitors Removed: {len(monitors_to_remove) if 'monitors_to_remove' in locals() else 0}")
        print(f"📋 Remaining Orders: {total_remaining}")
        
        if cancelled_count > 0 and total_remaining == 0:
            print("\n🎉 CLEANUP COMPLETED SUCCESSFULLY!")
            print("✅ All BANDUSDT and XTZUSDT orders removed")
            print("✅ Enhanced TP/SL monitors cleaned up")
            print("🔒 Only the intended positions were closed")
        elif failed_count > 0 or total_remaining > 0:
            print("\n⚠️ CLEANUP PARTIALLY COMPLETED")
            print("🔧 Some manual intervention may be needed")
        
        print("\n" + "=" * 60)
        print("🧹 ORPHANED ORDER CLEANUP COMPLETE")
        
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(cleanup_orphaned_orders())