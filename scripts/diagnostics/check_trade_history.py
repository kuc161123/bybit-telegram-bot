import json
from datetime import datetime
import os

# Load trade history
history_file = 'data/trade_history.json'
if os.path.exists(history_file):
    with open(history_file, 'r') as f:
        trades = json.load(f)
    
    # Get recent trades for the symbols mentioned
    symbols = ['ENAUSDT', 'TIAUSDT', 'JTOUSDT', 'WIFUSDT', 'JASMYUSDT', 'WLDUSDT', 'KAVAUSDT', 'BTCUSDT']
    
    print("RECENT TRADE HISTORY FOR FAST APPROACH POSITIONS:")
    print("="*80)
    
    # Check the structure of trades
    if isinstance(trades, dict):
        # If trades is a dict, get values
        trade_list = list(trades.values()) if trades else []
    else:
        trade_list = trades
    
    for symbol in symbols:
        symbol_trades = []
        for trade in trade_list:
            if isinstance(trade, dict) and trade.get('symbol') == symbol and trade.get('approach') == 'fast':
                symbol_trades.append(trade)
        
        if symbol_trades:
            print(f"\n{symbol}:")
            print("-"*40)
            # Sort by timestamp and show latest
            symbol_trades.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            latest = symbol_trades[0]
            
            print(f"Latest trade: {datetime.fromtimestamp(latest['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Side: {latest.get('side')}")
            print(f"Entry: {latest.get('entry_price')}")
            print(f"TP: {latest.get('tp_price')} (trigger)")
            print(f"SL: {latest.get('sl_price')} (trigger)")
            print(f"Status: {latest.get('status')}")
            
            # Check for TP/SL orders
            tp_orders = latest.get('tp_orders', [])
            sl_orders = latest.get('sl_orders', [])
            print(f"TP Orders: {len(tp_orders)}")
            if tp_orders:
                for tp in tp_orders:
                    print(f"  - {tp.get('order_id', 'Unknown')[:8]}... @ {tp.get('price')}")
            print(f"SL Orders: {len(sl_orders)}")
            if sl_orders:
                for sl in sl_orders:
                    print(f"  - {sl.get('order_id', 'Unknown')[:8]}... @ {sl.get('price')}")
            
            # Check for any fills
            if 'fills' in latest:
                print(f"Fills: {len(latest['fills'])}")
                for fill in latest['fills']:
                    print(f"  - {fill.get('order_type')} @ {fill.get('fill_price')} qty: {fill.get('fill_qty')}")
else:
    print(f"Trade history file not found: {history_file}")