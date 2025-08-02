#!/usr/bin/env python3
"""
Fixed Position Detector

This script fixes the API parameter issues and properly detects open positions.
"""

import asyncio
import sys
import logging
from decimal import Decimal

sys.path.append('/Users/lualakol/bybit-telegram-bot')

from clients.bybit_helpers import bybit_client
from execution.mirror_trader import bybit_client_2, is_mirror_trading_enabled
from config.settings import ENABLE_MIRROR_TRADING

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_positions_fixed(client, account_name="Main"):
    """Get positions with proper API parameters"""
    
    logger.info(f"📊 {account_name} Account Position Detection")
    logger.info("-" * 40)
    
    all_positions = []
    settlement_coins = ["USDT", "USDC", "BTC", "ETH"]  # Common settlement coins
    
    try:
        loop = asyncio.get_event_loop()
        
        # Try each settlement coin
        for settle_coin in settlement_coins:
            try:
                logger.info(f"   🔍 Checking {settle_coin} positions...")
                
                response = await loop.run_in_executor(
                    None,
                    lambda: client.get_positions(
                        category="linear",
                        settleCoin=settle_coin
                    )
                )
                
                if response and response.get("retCode") == 0:
                    positions = response.get("result", {}).get("list", [])
                    active_positions = [pos for pos in positions if float(pos.get('size', 0)) > 0]
                    
                    if active_positions:
                        logger.info(f"      ✅ Found {len(active_positions)} active positions in {settle_coin}")
                        all_positions.extend(active_positions)
                        
                        for pos in active_positions:
                            symbol = pos.get('symbol', 'Unknown')
                            side = pos.get('side', 'Unknown')
                            size = pos.get('size', '0')
                            avg_price = pos.get('avgPrice', '0')
                            pnl = pos.get('unrealisedPnl', '0')
                            
                            logger.info(f"         📍 {symbol} {side}")
                            logger.info(f"            Size: {size}")
                            logger.info(f"            Entry: ${avg_price}")
                            logger.info(f"            P&L: ${float(pnl):.2f}")
                    else:
                        logger.info(f"      ➖ No active positions in {settle_coin}")
                        
                else:
                    logger.warning(f"      ⚠️ API call failed for {settle_coin}: {response}")
                    
            except Exception as e:
                logger.warning(f"      ⚠️ Error checking {settle_coin}: {e}")
        
        logger.info(f"\\n📊 {account_name} Account Summary: {len(all_positions)} total active positions")
        return all_positions
        
    except Exception as e:
        logger.error(f"❌ Error getting {account_name} positions: {e}")
        return []

async def get_orders_fixed(client, account_name="Main"):
    """Get orders with proper API parameters"""
    
    logger.info(f"\\n📋 {account_name} Account Order Detection")
    logger.info("-" * 40)
    
    all_orders = []
    settlement_coins = ["USDT", "USDC", "BTC", "ETH"]
    
    try:
        loop = asyncio.get_event_loop()
        
        for settle_coin in settlement_coins:
            try:
                logger.info(f"   🔍 Checking {settle_coin} orders...")
                
                response = await loop.run_in_executor(
                    None,
                    lambda: client.get_open_orders(
                        category="linear",
                        settleCoin=settle_coin
                    )
                )
                
                if response and response.get("retCode") == 0:
                    orders = response.get("result", {}).get("list", [])
                    
                    if orders:
                        logger.info(f"      ✅ Found {len(orders)} orders in {settle_coin}")
                        all_orders.extend(orders)
                        
                        # Show first few orders
                        for order in orders[:3]:
                            symbol = order.get('symbol', 'Unknown')
                            side = order.get('side', 'Unknown')
                            order_type = order.get('orderType', 'Unknown')
                            qty = order.get('qty', '0')
                            status = order.get('orderStatus', 'Unknown')
                            order_link_id = order.get('orderLinkId', '')
                            
                            logger.info(f"         📋 {symbol} {side} {order_type}")
                            logger.info(f"            Qty: {qty}, Status: {status}")
                            if 'TP' in order_link_id.upper() or 'SL' in order_link_id.upper():
                                logger.info(f"            🎯 TP/SL Order: {order_link_id}")
                    else:
                        logger.info(f"      ➖ No orders in {settle_coin}")
                        
                else:
                    logger.warning(f"      ⚠️ API call failed for {settle_coin}: {response}")
                    
            except Exception as e:
                logger.warning(f"      ⚠️ Error checking {settle_coin} orders: {e}")
        
        logger.info(f"\\n📋 {account_name} Orders Summary: {len(all_orders)} total orders")
        return all_orders
        
    except Exception as e:
        logger.error(f"❌ Error getting {account_name} orders: {e}")
        return []

async def analyze_positions_and_orders():
    """Analyze positions and orders to understand current setup"""
    
    logger.info("🔍 FIXED POSITION AND ORDER DETECTION")
    logger.info("=" * 60)
    logger.info("Using proper API parameters to detect your positions")
    logger.info("")
    
    # Main account
    main_positions = await get_positions_fixed(bybit_client, "Main")
    main_orders = await get_orders_fixed(bybit_client, "Main")
    
    # Mirror account
    mirror_positions = []
    mirror_orders = []
    
    if ENABLE_MIRROR_TRADING and is_mirror_trading_enabled() and bybit_client_2:
        mirror_positions = await get_positions_fixed(bybit_client_2, "Mirror")
        mirror_orders = await get_orders_fixed(bybit_client_2, "Mirror")
    else:
        logger.info("\\n🪞 Mirror Account: Disabled or not configured")
    
    # Analysis summary
    logger.info("\\n" + "=" * 60)
    logger.info("📊 COMPREHENSIVE ANALYSIS")
    logger.info("=" * 60)
    
    total_positions = len(main_positions) + len(mirror_positions)
    total_orders = len(main_orders) + len(mirror_orders)
    
    logger.info(f"🏛️ Main Account:")
    logger.info(f"   Active Positions: {len(main_positions)}")
    logger.info(f"   Open Orders: {len(main_orders)}")
    
    if ENABLE_MIRROR_TRADING:
        logger.info(f"\\n🪞 Mirror Account:")
        logger.info(f"   Active Positions: {len(mirror_positions)}")
        logger.info(f"   Open Orders: {len(mirror_orders)}")
    
    logger.info(f"\\n📊 Total Overview:")
    logger.info(f"   Total Active Positions: {total_positions}")
    logger.info(f"   Total Open Orders: {total_orders}")
    
    if total_positions > 0:
        logger.info("\\n🎯 POSITIONS FOUND! Ready for enhanced TP/SL upgrade")
        logger.info("\\n💡 What the enhanced system will provide:")
        
        # Analyze each position
        all_positions = main_positions + mirror_positions
        
        for i, pos in enumerate(all_positions, 1):
            symbol = pos.get('symbol', 'Unknown')
            side = pos.get('side', 'Unknown')
            size = Decimal(str(pos.get('size', '0')))
            account = "Main" if pos in main_positions else "Mirror"
            
            logger.info(f"\\n   📍 Position {i}: {account} {symbol} {side} ({size})")
            logger.info(f"      🚀 Enhanced features that will be applied:")
            logger.info(f"         • Absolute position sizing for TPs")
            logger.info(f"         • Enhanced SL coverage logic")
            logger.info(f"         • Real-time rebalancing on limit fills")
            logger.info(f"         • Automatic mirror sync (if applicable)")
            
            # Show what enhanced TPs would look like
            tp_percentages = [Decimal("85"), Decimal("5"), Decimal("5"), Decimal("5")]
            logger.info(f"      📊 Enhanced TP structure:")
            for j, tp_pct in enumerate(tp_percentages, 1):
                tp_qty = (size * tp_pct) / Decimal("100")
                logger.info(f"         TP{j}: {tp_qty} ({tp_pct}% of {size})")
        
        logger.info("\\n🚀 NEXT STEP:")
        logger.info("Run: python force_apply_enhanced_tp_sl_to_current_positions.py")
        logger.info("This will upgrade all positions to use the new TP rebalancing system")
        
        return True, main_positions, mirror_positions, main_orders, mirror_orders
        
    else:
        logger.info("\\n✅ No open positions detected")
        logger.info("The enhanced TP/SL system is ready for your next trades!")
        return False, [], [], [], []

if __name__ == "__main__":
    success, main_pos, mirror_pos, main_orders, mirror_orders = asyncio.run(analyze_positions_and_orders())
    
    if success:
        print(f"\\n🎉 SUCCESS! Found {len(main_pos + mirror_pos)} positions ready for enhancement!")
    else:
        print("\\n✅ No positions found - system ready for new trades!")