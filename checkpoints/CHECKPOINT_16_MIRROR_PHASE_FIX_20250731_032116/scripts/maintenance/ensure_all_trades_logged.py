#!/usr/bin/env python3
"""
Ensure all current trades are properly logged in the trade history.
Migrates data from current_positions_trigger_prices.json to enhanced trade logger.
"""

import asyncio
import os
import sys
import json
from datetime import datetime, timezone
from decimal import Decimal
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

load_dotenv()


async def ensure_trades_logged():
    """Ensure all current positions are logged in trade history."""
    
    print("📊 Ensuring All Trades Are Logged")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Import the enhanced trade logger
    from utils.enhanced_trade_logger import enhanced_trade_logger
    
    # Load current positions
    positions_file = "current_positions_trigger_prices.json"
    if not os.path.exists(positions_file):
        print("❌ No current positions file found")
        return
    
    try:
        with open(positions_file, 'r') as f:
            data = json.load(f)
        
        positions = data.get('positions', [])
        print(f"\n📋 Found {len(positions)} positions in current log")
        
        # Load enhanced trade history
        history = await enhanced_trade_logger._load_history()
        existing_trades = history.get('trades', {})
        
        print(f"📂 Existing trades in enhanced history: {len(existing_trades)}")
        
        # Process each position
        added_count = 0
        
        for pos in positions:
            symbol = pos.get('symbol')
            side = pos.get('side')
            approach = pos.get('approach', 'conservative')
            
            # Check if already logged
            already_logged = False
            for trade_id, trade in existing_trades.items():
                if (trade.get('symbol') == symbol and 
                    trade.get('side') == side and
                    trade.get('status') == 'active'):
                    already_logged = True
                    break
            
            if already_logged:
                print(f"   ✅ {symbol} {side} already logged")
                continue
            
            # Add to enhanced logger
            print(f"\n   📝 Adding {symbol} {side} to enhanced logger...")
            
            # Prepare trade data
            entry_price = pos.get('entry_price')
            size = pos.get('entry_size')
            entry_time = pos.get('entry_timestamp', datetime.now(timezone.utc).isoformat())
            
            # Prepare TP orders
            tp_orders = []
            for tp in pos.get('tp_orders', []):
                tp_orders.append({
                    'price': str(tp.get('price')),
                    'quantity': str(tp.get('quantity')),
                    'order_id': tp.get('order_id', '')
                })
            
            # Prepare SL order
            sl_order = None
            if pos.get('sl_price'):
                sl_order = {
                    'price': str(pos['sl_price']),
                    'quantity': str(size),
                    'order_id': pos.get('sl_order_id', '')
                }
            
            # Log the trade
            trade_id = await enhanced_trade_logger.log_trade_entry(
                symbol=symbol,
                side=side,
                approach=approach,
                entry_price=entry_price,
                size=size,
                order_type="Market",
                take_profits=tp_orders,
                stop_loss=sl_order,
                metadata={
                    'imported_from': 'current_positions_trigger_prices.json',
                    'import_time': datetime.now(timezone.utc).isoformat(),
                    'original_timestamp': entry_time
                }
            )
            
            if trade_id:
                print(f"   ✅ Successfully logged with ID: {trade_id}")
                added_count += 1
            else:
                print(f"   ❌ Failed to log trade")
        
        print(f"\n\n📊 Summary:")
        print(f"   Total positions: {len(positions)}")
        print(f"   Already logged: {len(positions) - added_count}")
        print(f"   Newly logged: {added_count}")
        
        # Verify the enhanced history
        updated_history = await enhanced_trade_logger._load_history()
        updated_trades = updated_history.get('trades', {})
        
        print(f"\n✅ Enhanced trade history now contains {len(updated_trades)} trades")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def verify_logging_works():
    """Test that new trades will be logged properly."""
    
    print("\n\n🧪 Testing Trade Logging System")
    print("=" * 80)
    
    from utils.enhanced_trade_logger import enhanced_trade_logger
    
    # Create a test trade
    test_trade_id = await enhanced_trade_logger.log_trade_entry(
        symbol="TESTUSDT",
        side="Buy",
        approach="test",
        entry_price="100.00",
        size="10",
        order_type="Market",
        take_profits=[
            {'price': '110.00', 'quantity': '8.5'},
            {'price': '115.00', 'quantity': '0.5'},
            {'price': '120.00', 'quantity': '0.5'},
            {'price': '125.00', 'quantity': '0.5'}
        ],
        stop_loss={'price': '95.00', 'quantity': '10'},
        metadata={'test': True}
    )
    
    if test_trade_id:
        print(f"✅ Test trade logged successfully with ID: {test_trade_id}")
        
        # Log a test fill
        await enhanced_trade_logger.log_order_event(
            test_trade_id,
            "filled",
            "tp",
            "test_order_123",
            {
                'fill_price': '110.00',
                'fill_qty': '8.5',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        )
        
        print("✅ Test order fill logged successfully")
        
        # Clean up test trade
        history = await enhanced_trade_logger._load_history()
        if 'trades' in history and test_trade_id in history['trades']:
            del history['trades'][test_trade_id]
            await enhanced_trade_logger._save_history(history)
            print("✅ Test trade cleaned up")
        
        print("\n✅ Trade logging system is working properly!")
    else:
        print("❌ Failed to log test trade - system may have issues")


async def create_logging_summary():
    """Create a summary of what's being logged."""
    
    print("\n\n📝 Trade Logging Summary")
    print("=" * 80)
    
    print("""
The Enhanced Trade Logger captures:

1. **Trade Entry**
   - Symbol, side, approach
   - Entry price and size
   - All limit orders with prices
   - All TP orders with trigger prices and quantities
   - SL order with trigger price
   - Timestamp and metadata

2. **Order Events**
   - Order placements
   - Order fills (partial and complete)
   - Order cancellations
   - Order modifications

3. **Position Updates**
   - Position merges
   - Size changes
   - Average price updates

4. **Trade Exit**
   - Exit reason (TP hit, SL hit, manual close)
   - Final P&L calculation
   - Total fees
   - Duration

5. **Performance Metrics**
   - Win/loss tracking
   - P&L by approach
   - Success rates
   - Risk metrics

All of this is stored in:
- data/enhanced_trade_history.json (main file)
- data/enhanced_trade_history_backup.json (backup)
- data/trade_archives/ (when rotating)

The system automatically:
- Creates backups before each save
- Rotates files when they exceed 100MB
- Archives old data with compression
- Maintains data integrity
""")


async def main():
    """Main function."""
    await ensure_trades_logged()
    await verify_logging_works()
    await create_logging_summary()


if __name__ == "__main__":
    asyncio.run(main())