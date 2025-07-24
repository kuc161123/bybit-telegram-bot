import asyncio
from clients.bybit_client import bybit_client
from clients.bybit_helpers import place_order_with_retry
from decimal import Decimal
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define BOT_PREFIX constant
BOT_PREFIX = "BOT_"

async def fix_fast_approach_positions():
    """
    Fix fast approach positions that have no TP/SL orders
    """
    symbols_to_fix = ['ENAUSDT', 'TIAUSDT', 'WIFUSDT', 'JASMYUSDT', 'WLDUSDT', 'BTCUSDT']
    
    try:
        # Get positions
        pos_response = bybit_client.get_positions(category="linear", settleCoin="USDT")
        positions = pos_response.get("result", {}).get("list", [])
        
        # Get orders
        order_response = bybit_client.get_open_orders(category="linear", settleCoin="USDT")
        orders = order_response.get("result", {}).get("list", [])
        
        print("FIXING FAST APPROACH POSITIONS:")
        print("="*80)
        
        for symbol in symbols_to_fix:
            pos = next((p for p in positions if p['symbol'] == symbol and float(p['size']) > 0), None)
            if not pos:
                continue
                
            sym_orders = [o for o in orders if o['symbol'] == symbol]
            
            # Check if position needs fixing (no TP/SL orders)
            tp_orders = [o for o in sym_orders if o.get('stopOrderType') == 'TakeProfit' and o.get('reduceOnly')]
            sl_orders = [o for o in sym_orders if o.get('stopOrderType') == 'StopLoss' and o.get('reduceOnly')]
            
            if len(tp_orders) == 0 or len(sl_orders) == 0:
                print(f"\n{symbol} - NEEDS FIXING:")
                print(f"Position: {pos['size']} @ {pos['avgPrice']} ({pos['side']})")
                print(f"Current P&L: ${float(pos['unrealisedPnl']):.2f}")
                print(f"TP Orders: {len(tp_orders)}, SL Orders: {len(sl_orders)}")
                
                # Calculate TP/SL prices based on position
                side = pos['side']
                avg_price = Decimal(pos['avgPrice'])
                position_size = pos['size']
                
                # For fast approach: TP at ~5-10% profit, SL at ~2-3% loss
                if side == 'Buy':
                    # Long position
                    tp_price = avg_price * Decimal('1.07')  # 7% profit
                    sl_price = avg_price * Decimal('0.975')  # 2.5% loss
                else:
                    # Short position
                    tp_price = avg_price * Decimal('0.93')  # 7% profit
                    sl_price = avg_price * Decimal('1.025')  # 2.5% loss
                
                # Get instrument info for proper decimal precision
                inst_response = bybit_client.get_instruments_info(category="linear", symbol=symbol)
                if inst_response and inst_response.get("retCode") == 0:
                    instruments = inst_response.get("result", {}).get("list", [])
                    if instruments:
                        price_filter = instruments[0].get("priceFilter", {})
                        tick_size = Decimal(price_filter.get("tickSize", "0.01"))
                        
                        # Round prices to tick size
                        tp_price = (tp_price / tick_size).quantize(Decimal('1')) * tick_size
                        sl_price = (sl_price / tick_size).quantize(Decimal('1')) * tick_size
                
                print(f"Calculated TP: {tp_price}, SL: {sl_price}")
                
                # Place TP order if missing
                if len(tp_orders) == 0:
                    print(f"Placing TP order...")
                    tp_result = await place_order_with_retry(
                        symbol=symbol,
                        side="Sell" if side == "Buy" else "Buy",
                        order_type="Market",
                        qty=position_size,
                        trigger_price=str(tp_price),
                        order_link_id=f"{BOT_PREFIX}FAST_FIX_{symbol}_TP",
                        reduce_only=True,
                        stop_order_type="TakeProfit"
                    )
                    
                    if tp_result:
                        print(f"✅ TP order placed: {tp_result.get('orderId', '')[:8]}...")
                    else:
                        print(f"❌ Failed to place TP order")
                
                # Place SL order if missing
                if len(sl_orders) == 0:
                    print(f"Placing SL order...")
                    sl_result = await place_order_with_retry(
                        symbol=symbol,
                        side="Sell" if side == "Buy" else "Buy",
                        order_type="Market",
                        qty=position_size,
                        trigger_price=str(sl_price),
                        order_link_id=f"{BOT_PREFIX}FAST_FIX_{symbol}_SL",
                        reduce_only=True,
                        stop_order_type="StopLoss"
                    )
                    
                    if sl_result:
                        print(f"✅ SL order placed: {sl_result.get('orderId', '')[:8]}...")
                    else:
                        print(f"❌ Failed to place SL order")
                        
        print("\n" + "="*80)
        print("FIX COMPLETE!")
        
    except Exception as e:
        logger.error(f"Error fixing positions: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(fix_fast_approach_positions())