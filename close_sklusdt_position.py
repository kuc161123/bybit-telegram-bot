#!/usr/bin/env python3
"""
Close SKLUSDT position and cancel all orders on both main and mirror accounts
"""
import asyncio
import logging
from decimal import Decimal
from clients.bybit_client import bybit_client
from clients.bybit_helpers import cancel_order_with_retry, get_position_info_for_account, get_open_orders
import os
from pybit.unified_trading import HTTP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

async def close_position_and_cancel_orders(symbol: str, account_type: str = "main"):
    """Close position and cancel all orders for a symbol"""
    client = bybit_client_mirror if account_type == "mirror" else bybit_client
    account_label = account_type.upper()
    
    print(f"\n{'='*60}")
    print(f"Processing {account_label} Account - {symbol}")
    print(f"{'='*60}")
    
    try:
        # 1. Get current position
        positions = await get_position_info_for_account(symbol, account_type)
        position_to_close = None
        
        if positions:
            for pos in positions:
                if pos.get('symbol') == symbol and float(pos.get('size', 0)) > 0:
                    position_to_close = pos
                    break
        
        if position_to_close:
            size = float(position_to_close.get('size', 0))
            side = position_to_close.get('side')
            avg_price = float(position_to_close.get('avgPrice', 0))
            
            print(f"\n📊 Found {account_label} Position:")
            print(f"   Symbol: {symbol}")
            print(f"   Side: {side}")
            print(f"   Size: {size}")
            print(f"   Avg Price: {avg_price}")
            
            # 2. Close the position with market order
            close_side = "Sell" if side == "Buy" else "Buy"
            
            print(f"\n🔄 Closing position with {close_side} market order...")
            
            close_result = client.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(size),
                reduceOnly=True,
                orderLinkId=f"CLOSE_{symbol}_{account_type}"
            )
            
            if close_result and close_result.get('retCode') == 0:
                order_id = close_result['result'].get('orderId', '')
                print(f"✅ Position close order placed successfully (ID: {order_id[:8]}...)")
            else:
                print(f"❌ Failed to close position: {close_result}")
        else:
            print(f"ℹ️ No open position found for {symbol} on {account_label} account")
        
        # 3. Cancel all open orders
        print(f"\n🧹 Cancelling all open orders for {symbol}...")
        
        open_orders = await get_open_orders(symbol)
        cancelled_count = 0
        failed_count = 0
        
        if open_orders:
            for order in open_orders:
                if order.get('symbol') == symbol:
                    order_id = order.get('orderId')
                    order_type = order.get('orderType', '')
                    stop_type = order.get('stopOrderType', '')
                    side = order.get('side')
                    qty = order.get('qty')
                    
                    print(f"\n   Cancelling {order_type} {stop_type} {side} order: {qty} (ID: {order_id[:8]}...)")
                    
                    try:
                        success = await cancel_order_with_retry(symbol, order_id)
                        if success:
                            cancelled_count += 1
                            print(f"   ✅ Cancelled successfully")
                        else:
                            failed_count += 1
                            print(f"   ❌ Failed to cancel")
                    except Exception as e:
                        failed_count += 1
                        print(f"   ❌ Error cancelling: {e}")
        
        print(f"\n📊 {account_label} Account Summary:")
        print(f"   Position: {'Closed' if position_to_close else 'No position found'}")
        print(f"   Orders Cancelled: {cancelled_count}")
        print(f"   Orders Failed: {failed_count}")
        
        return {
            'position_closed': bool(position_to_close),
            'orders_cancelled': cancelled_count,
            'orders_failed': failed_count
        }
        
    except Exception as e:
        logger.error(f"Error processing {account_label} account: {e}")
        return {
            'position_closed': False,
            'orders_cancelled': 0,
            'orders_failed': 0,
            'error': str(e)
        }

async def main():
    """Main execution"""
    symbol = "SKLUSDT"
    
    print(f"\n{'='*80}")
    print(f"CLOSING {symbol} POSITION AND CANCELLING ALL ORDERS")
    print(f"{'='*80}")
    print("\n⚠️  WARNING: This will close all positions and cancel all orders for SKLUSDT!")
    print("⏸️  Starting in 5 seconds... (Press Ctrl+C to cancel)")
    
    await asyncio.sleep(5)
    
    results = {
        'main': None,
        'mirror': None
    }
    
    # Process main account
    print("\n" + "="*80)
    print("PROCESSING MAIN ACCOUNT")
    print("="*80)
    results['main'] = await close_position_and_cancel_orders(symbol, "main")
    
    # Process mirror account if available
    if bybit_client_mirror:
        print("\n" + "="*80)
        print("PROCESSING MIRROR ACCOUNT")
        print("="*80)
        results['mirror'] = await close_position_and_cancel_orders(symbol, "mirror")
    else:
        print("\nℹ️ Mirror account not configured, skipping...")
    
    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    
    for account, result in results.items():
        if result:
            print(f"\n{account.upper()} Account:")
            if 'error' in result:
                print(f"   ❌ Error: {result['error']}")
            else:
                print(f"   Position Closed: {'Yes' if result['position_closed'] else 'No position found'}")
                print(f"   Orders Cancelled: {result['orders_cancelled']}")
                print(f"   Orders Failed: {result['orders_failed']}")
    
    print(f"\n✅ {symbol} cleanup complete!")
    print("\n💡 Note: The Enhanced TP/SL monitor will automatically detect the closed position")
    print("   and clean up its monitoring tasks.")

if __name__ == "__main__":
    asyncio.run(main())