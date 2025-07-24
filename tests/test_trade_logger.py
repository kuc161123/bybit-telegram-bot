#!/usr/bin/env python3
"""
Test and demonstrate the trade logging system
"""

import asyncio
import logging
from decimal import Decimal
from datetime import datetime
import json

from utils.trade_logger import (
    log_trade_entry, log_tp_orders, log_sl_order,
    log_order_fill, log_position_merge, log_rebalance,
    get_trade_history, get_original_trigger_prices
)
from utils.trade_verifier import verify_all_positions, get_correction_suggestions

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demonstrate_trade_logging():
    """Demonstrate the trade logging functionality"""
    
    print("\n" + "="*70)
    print("TRADE LOGGING SYSTEM DEMONSTRATION")
    print("="*70)
    
    # 1. Log a new trade entry
    print("\n1. LOGGING NEW TRADE ENTRY")
    print("-" * 50)
    
    trade_key = await log_trade_entry(
        symbol="BTCUSDT",
        side="Buy",
        approach="Fast",
        entry_price=Decimal("65000"),
        size=Decimal("0.1"),
        order_type="Market",
        chat_id="123456",
        leverage=10,
        risk_percentage=Decimal("2")
    )
    
    print(f"✅ Trade logged with key: {trade_key}")
    
    # 2. Log TP order
    print("\n2. LOGGING TP ORDER")
    print("-" * 50)
    
    await log_tp_orders(trade_key, [{
        'symbol': 'BTCUSDT',
        'side': 'Sell',
        'price': '67000',
        'qty': '0.1',
        'percentage': 100,
        'orderId': 'TP123456',
        'orderLinkId': 'BOT_FAST_123_TP'
    }])
    
    print("✅ TP order logged")
    
    # 3. Log SL order
    print("\n3. LOGGING SL ORDER")
    print("-" * 50)
    
    await log_sl_order(trade_key, {
        'symbol': 'BTCUSDT',
        'side': 'Buy',
        'triggerPrice': '63000',
        'qty': '0.1',
        'orderId': 'SL123456',
        'orderLinkId': 'BOT_FAST_123_SL'
    })
    
    print("✅ SL order logged")
    
    # 4. Simulate TP fill
    print("\n4. SIMULATING TP FILL")
    print("-" * 50)
    
    await log_order_fill(
        symbol="BTCUSDT",
        side="Buy",
        order_type="TP",
        fill_price=Decimal("67000"),
        fill_qty=Decimal("0.1"),
        order_id="TP123456"
    )
    
    print("✅ TP fill logged")
    
    # 5. Get trade history
    print("\n5. RETRIEVING TRADE HISTORY")
    print("-" * 50)
    
    history = await get_trade_history(symbol="BTCUSDT")
    
    for trade in history:
        print(f"\nTrade: {trade['trade_key']}")
        print(f"  Symbol: {trade['symbol']} {trade['side']}")
        print(f"  Approach: {trade['approach']}")
        print(f"  Entry: ${trade['entry']['price']} x {trade['entry']['size']}")
        print(f"  Status: {trade['status']}")
        
        if trade['tp_orders']:
            print("  TP Orders:")
            for tp in trade['tp_orders']:
                print(f"    - Level {tp['level']}: ${tp['price']} ({tp['percentage']}%)")
        
        if trade['sl_order']:
            print(f"  SL Order: ${trade['sl_order']['price']}")
        
        if trade['fills']:
            print("  Fills:")
            for fill in trade['fills']:
                print(f"    - {fill['type']}: ${fill['price']} x {fill['quantity']}")
    
    # 6. Get original trigger prices
    print("\n6. RETRIEVING ORIGINAL TRIGGER PRICES")
    print("-" * 50)
    
    original_prices = await get_original_trigger_prices("BTCUSDT", "Buy")
    
    if original_prices:
        print(f"Original prices for BTCUSDT Buy:")
        print(f"  Entry: ${original_prices['entry_price']}")
        print(f"  TPs: {[f'${p}' for p in original_prices['tp_prices']]}")
        print(f"  SL: ${original_prices['sl_price']}")
        print(f"  Approach: {original_prices['approach']}")
    
    # 7. Log a rebalance operation
    print("\n7. LOGGING REBALANCE OPERATION")
    print("-" * 50)
    
    await log_rebalance(
        symbol="BTCUSDT",
        side="Buy",
        approach="Fast",
        orders_cancelled=1,
        orders_created=2,
        trigger_type="new_position",
        details={
            "position_size": "0.1",
            "tp_distribution": "100%"
        }
    )
    
    print("✅ Rebalance operation logged")
    
    # 8. Demonstrate Conservative approach
    print("\n8. LOGGING CONSERVATIVE TRADE")
    print("-" * 50)
    
    cons_trade_key = await log_trade_entry(
        symbol="ETHUSDT",
        side="Buy",
        approach="Conservative",
        entry_price=Decimal("3500"),
        size=Decimal("1.0"),
        order_type="Limit",
        chat_id="123456",
        leverage=5
    )
    
    # Log multiple TPs for conservative
    await log_tp_orders(cons_trade_key, [
        {
            'symbol': 'ETHUSDT',
            'side': 'Sell',
            'price': '3600',
            'qty': '0.85',
            'percentage': 85,
            'orderId': 'TP1_456',
            'orderLinkId': 'BOT_CONS_456_TP1'
        },
        {
            'symbol': 'ETHUSDT',
            'side': 'Sell',
            'price': '3700',
            'qty': '0.05',
            'percentage': 5,
            'orderId': 'TP2_456',
            'orderLinkId': 'BOT_CONS_456_TP2'
        },
        {
            'symbol': 'ETHUSDT',
            'side': 'Sell',
            'price': '3800',
            'qty': '0.05',
            'percentage': 5,
            'orderId': 'TP3_456',
            'orderLinkId': 'BOT_CONS_456_TP3'
        },
        {
            'symbol': 'ETHUSDT',
            'side': 'Sell',
            'price': '3900',
            'qty': '0.05',
            'percentage': 5,
            'orderId': 'TP4_456',
            'orderLinkId': 'BOT_CONS_456_TP4'
        }
    ])
    
    print("✅ Conservative trade with 4 TPs logged")
    
    # 9. Show trade history summary
    print("\n9. TRADE HISTORY SUMMARY")
    print("-" * 50)
    
    all_trades = await get_trade_history()
    active_trades = [t for t in all_trades if t['status'] == 'active']
    closed_trades = [t for t in all_trades if t['status'] == 'closed']
    
    print(f"Total trades: {len(all_trades)}")
    print(f"Active trades: {len(active_trades)}")
    print(f"Closed trades: {len(closed_trades)}")
    
    print("\n" + "="*70)
    print("✅ DEMONSTRATION COMPLETE")
    print("="*70)
    print("\nThe trade logging system provides:")
    print("1. Complete trade lifecycle tracking")
    print("2. Original trigger price preservation")
    print("3. Fill and P&L tracking")
    print("4. Merge and rebalance history")
    print("5. Support for both Fast and Conservative approaches")
    print("6. Integration with auto-rebalancer for verification")
    print("\nCheck data/trade_history.json for the complete log")


async def main():
    """Main function"""
    try:
        await demonstrate_trade_logging()
    except Exception as e:
        logger.error(f"Error in demonstration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())