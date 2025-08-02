#!/usr/bin/env python3
"""
Close ALL positions and orders on both main and mirror accounts
This will give a complete fresh start
"""

import asyncio
import logging
import time
from decimal import Decimal
from datetime import datetime
from clients.bybit_client import bybit_client
from execution.mirror_trader import bybit_client_2 as mirror_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Safety confirmation
CONFIRM_CLOSE_ALL = True  # Must be True to execute

async def get_all_positions(client, account_name):
    """Get all open positions"""
    try:
        all_positions = []
        response = await asyncio.to_thread(
            client.get_positions,
            category="linear",
            settleCoin="USDT"
        )
        
        if response['retCode'] == 0:
            for pos in response['result']['list']:
                if float(pos['size']) > 0:
                    all_positions.append({
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'size': float(pos['size']),
                        'avgPrice': float(pos['avgPrice']),
                        'unrealisedPnl': float(pos.get('unrealisedPnl', 0)),
                        'positionIdx': pos.get('positionIdx', 0)
                    })
        
        return all_positions
    except Exception as e:
        logger.error(f"Error getting positions for {account_name}: {e}")
        return []

async def cancel_all_orders(client, symbol, account_name):
    """Cancel all orders for a symbol"""
    try:
        # Cancel regular orders
        response = await asyncio.to_thread(
            client.cancel_all_orders,
            category="linear",
            symbol=symbol
        )
        
        if response['retCode'] == 0:
            cancelled = response['result']['list']
            if cancelled:
                logger.info(f"   ✅ Cancelled {len(cancelled)} orders for {symbol}")
        else:
            logger.error(f"   ❌ Failed to cancel orders: {response.get('retMsg', '')}")
            
    except Exception as e:
        logger.error(f"   ❌ Error cancelling orders: {e}")

async def close_position(client, position, account_name):
    """Close a single position with market order"""
    symbol = position['symbol']
    side = position['side']
    size = position['size']
    
    # Opposite side to close
    close_side = 'Sell' if side == 'Buy' else 'Buy'
    
    try:
        # First cancel all orders for this symbol
        await cancel_all_orders(client, symbol, account_name)
        await asyncio.sleep(0.5)  # Brief pause
        
        # Place market order to close position
        order_params = {
            'category': 'linear',
            'symbol': symbol,
            'side': close_side,
            'orderType': 'Market',
            'qty': str(size),
            'reduceOnly': True,
            'positionIdx': position.get('positionIdx', 0)
        }
        
        response = await asyncio.to_thread(
            client.place_order,
            **order_params
        )
        
        if response['retCode'] == 0:
            logger.info(f"   ✅ Closed {symbol} {side}: {size} units")
            logger.info(f"      Realized P&L: ${position['unrealisedPnl']:.2f}")
            return True
        else:
            logger.error(f"   ❌ Failed to close: {response.get('retMsg', '')}")
            return False
            
    except Exception as e:
        logger.error(f"   ❌ Error closing position: {e}")
        return False

async def close_all_positions_account(client, account_name):
    """Close all positions for an account"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🏦 CLOSING ALL POSITIONS - {account_name.upper()} ACCOUNT")
    logger.info(f"{'='*60}")
    
    # Get all positions
    positions = await get_all_positions(client, account_name)
    
    if not positions:
        logger.info(f"✅ No open positions found on {account_name} account")
        return
    
    # Display positions to be closed
    total_pnl = sum(p['unrealisedPnl'] for p in positions)
    logger.info(f"\n📊 Found {len(positions)} positions to close:")
    logger.info(f"   Total Unrealized P&L: ${total_pnl:,.2f}")
    
    for pos in positions:
        pnl_emoji = "🟢" if pos['unrealisedPnl'] >= 0 else "🔴"
        logger.info(f"   {pnl_emoji} {pos['symbol']} {pos['side']}: {pos['size']} @ ${pos['avgPrice']} (P&L: ${pos['unrealisedPnl']:.2f})")
    
    # Close each position
    logger.info(f"\n🔄 Closing positions...")
    success_count = 0
    failed_positions = []
    
    for pos in positions:
        logger.info(f"\nClosing {pos['symbol']} {pos['side']}...")
        if await close_position(client, pos, account_name):
            success_count += 1
        else:
            failed_positions.append(f"{pos['symbol']} {pos['side']}")
        
        # Rate limiting
        await asyncio.sleep(1)
    
    # Summary
    logger.info(f"\n📊 {account_name} Account Summary:")
    logger.info(f"   Closed: {success_count}/{len(positions)} positions")
    if failed_positions:
        logger.error(f"   Failed: {', '.join(failed_positions)}")

async def cancel_all_remaining_orders(client, account_name):
    """Cancel any remaining orders across all symbols"""
    logger.info(f"\n🗑️ Cancelling all remaining orders on {account_name} account...")
    
    try:
        # Get all open orders
        response = await asyncio.to_thread(
            client.get_open_orders,
            category="linear"
        )
        
        if response['retCode'] == 0:
            orders = response['result']['list']
            if orders:
                # Group by symbol
                symbols = set(order['symbol'] for order in orders)
                for symbol in symbols:
                    await cancel_all_orders(client, symbol, account_name)
                    await asyncio.sleep(0.5)
            else:
                logger.info(f"   ✅ No remaining orders found")
    except Exception as e:
        logger.error(f"Error cancelling remaining orders: {e}")

async def main():
    """Main execution"""
    if not CONFIRM_CLOSE_ALL:
        logger.error("❌ CONFIRM_CLOSE_ALL is not True. Aborting for safety.")
        return
    
    logger.info("🚨 FRESH START - CLOSING ALL POSITIONS AND ORDERS")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    # Confirm action
    logger.warning("\n⚠️  WARNING: This will close ALL positions and may result in losses!")
    logger.info("\nStarting in 5 seconds... Press Ctrl+C to cancel")
    
    try:
        for i in range(5, 0, -1):
            logger.info(f"   {i}...")
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n❌ Cancelled by user")
        return
    
    # Close all positions on main account
    await close_all_positions_account(bybit_client, "Main")
    
    # Close all positions on mirror account
    if mirror_client:
        await close_all_positions_account(mirror_client, "Mirror")
    else:
        logger.warning("⚠️ Mirror client not available")
    
    # Cancel any remaining orders
    await cancel_all_remaining_orders(bybit_client, "Main")
    if mirror_client:
        await cancel_all_remaining_orders(mirror_client, "Mirror")
    
    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ FRESH START COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"All positions and orders have been closed.")
    logger.info(f"You can now start fresh with new positions.")
    
    # Save completion timestamp
    with open('fresh_start_completed.txt', 'w') as f:
        f.write(f"Fresh start completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    asyncio.run(main())