#!/usr/bin/env python3
"""
Reconstruct monitor states from trading logs
This will analyze the trading_bot.log to understand:
- Original TP placements and quantities
- Which TPs have been hit
- Breakeven movements
- Limit order fills
- Current phase of each position
"""
import re
import os
import sys
import time
import pickle
from decimal import Decimal
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def parse_log_line(line: str) -> Optional[Dict]:
    """Parse a log line to extract relevant trading information"""
    # Extract timestamp and message
    timestamp_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
    timestamp_match = re.search(timestamp_pattern, line)
    
    if not timestamp_match:
        return None
    
    timestamp = timestamp_match.group(1)
    message = line[timestamp_match.end():].strip()
    
    # Skip non-relevant lines
    if not any(keyword in message for keyword in [
        'TP', 'SL', 'limit', 'breakeven', 'Conservative', 'ALTUSDT', 'CHRUSDT', 
        'placed', 'filled', 'hit', 'rebalancing', 'monitor', 'PROFIT_TAKING'
    ]):
        return None
    
    return {
        'timestamp': timestamp,
        'message': message,
        'raw_line': line
    }

def analyze_position_from_logs(symbol: str, side: str, account: str, log_entries: List[Dict]) -> Dict:
    """Analyze a specific position's history from log entries"""
    position_key = f"{symbol}_{side}_{account}"
    position_logs = []
    
    # Filter logs for this specific position
    for entry in log_entries:
        message = entry['message']
        if symbol in message and (
            (side == 'Buy' and ('Buy' in message or 'Long' in message)) or
            (side == 'Sell' and ('Sell' in message or 'Short' in message))
        ):
            # Check for account type indicators
            if account == 'main' and ('MAIN' in message or 'main' in message or '🏠' in message):
                position_logs.append(entry)
            elif account == 'mirror' and ('MIRROR' in message or 'mirror' in message or '🪞' in message):
                position_logs.append(entry)
            elif account == 'main' and 'mirror' not in message.lower() and 'MIRROR' not in message:
                # Assume main if no explicit account mentioned
                position_logs.append(entry)
    
    # Analyze the logs for this position
    analysis = {
        'symbol': symbol,
        'side': side,
        'account_type': account,
        'phase': 'MONITORING',
        'tp1_hit': False,
        'sl_moved_to_be': False,
        'limit_orders_filled': False,
        'tp_hits': [],
        'original_tps': {},
        'current_tps': {},
        'sl_moves': [],
        'limit_fills': [],
        'rebalancing_events': [],
        'breakeven_events': []
    }
    
    for entry in position_logs:
        message = entry['message']
        timestamp = entry['timestamp']
        
        # Look for TP placement
        if 'TP' in message and 'placed' in message:
            tp_match = re.search(r'TP(\d+).*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)', message)
            if tp_match:
                tp_num = int(tp_match.group(1))
                qty = Decimal(tp_match.group(2))
                price = Decimal(tp_match.group(3))
                analysis['original_tps'][f'tp_{tp_num}'] = {
                    'tp_number': tp_num,
                    'quantity': qty,
                    'price': price,
                    'timestamp': timestamp
                }
        
        # Look for TP hits
        if 'TP' in message and ('hit' in message or 'filled' in message):
            if 'TP1' in message:
                analysis['tp1_hit'] = True
                analysis['phase'] = 'PROFIT_TAKING'
                analysis['tp_hits'].append({'tp': 1, 'timestamp': timestamp})
            
            tp_hit_match = re.search(r'TP(\d+)', message)
            if tp_hit_match:
                tp_num = int(tp_hit_match.group(1))
                analysis['tp_hits'].append({'tp': tp_num, 'timestamp': timestamp})
        
        # Look for breakeven movements
        if 'breakeven' in message.lower() or 'moved to BE' in message:
            analysis['sl_moved_to_be'] = True
            analysis['breakeven_events'].append({
                'timestamp': timestamp,
                'message': message
            })
        
        # Look for limit order fills
        if 'limit' in message.lower() and ('filled' in message or 'fill' in message):
            analysis['limit_orders_filled'] = True
            analysis['limit_fills'].append({
                'timestamp': timestamp,
                'message': message
            })
        
        # Look for rebalancing events
        if 'rebalanc' in message.lower():
            analysis['rebalancing_events'].append({
                'timestamp': timestamp,
                'message': message
            })
        
        # Look for phase transitions
        if 'PROFIT_TAKING' in message:
            analysis['phase'] = 'PROFIT_TAKING'
    
    return analysis

def main():
    """Main function to reconstruct monitor states from logs"""
    print("📖 Reconstructing Monitor States from Trading Logs")
    print("=" * 55)
    
    # Read the trading log file
    log_file = 'trading_bot.log'
    if not os.path.exists(log_file):
        print(f"❌ Log file {log_file} not found")
        return
    
    print(f"📄 Reading {log_file}...")
    
    # Parse log entries
    log_entries = []
    with open(log_file, 'r') as f:
        for line in f:
            parsed = parse_log_line(line.strip())
            if parsed:
                log_entries.append(parsed)
    
    print(f"📊 Parsed {len(log_entries)} relevant log entries")
    
    # Get list of active positions from current API state
    from clients.bybit_helpers import get_all_positions
    from pybit.unified_trading import HTTP
    import asyncio
    
    async def get_current_positions():
        # Get configuration
        config = {
            'TESTNET': os.getenv('TESTNET', 'false').lower() == 'true',
            'BYBIT_API_KEY': os.getenv('BYBIT_API_KEY'),
            'BYBIT_API_SECRET': os.getenv('BYBIT_API_SECRET'),
            'ENABLE_MIRROR_TRADING': os.getenv('ENABLE_MIRROR_TRADING', 'false').lower() == 'true',
            'BYBIT_API_KEY_2': os.getenv('BYBIT_API_KEY_2'),
            'BYBIT_API_SECRET_2': os.getenv('BYBIT_API_SECRET_2')
        }
        
        positions = []
        
        # Main account
        main_client = HTTP(
            testnet=config['TESTNET'],
            api_key=config['BYBIT_API_KEY'],
            api_secret=config['BYBIT_API_SECRET']
        )
        
        main_positions = await get_all_positions(client=main_client)
        for pos in main_positions:
            if float(pos.get('size', 0)) > 0:
                positions.append({
                    'symbol': pos.get('symbol'),
                    'side': pos.get('side'),
                    'size': Decimal(str(pos.get('size'))),
                    'account': 'main'
                })
        
        # Mirror account
        if config['ENABLE_MIRROR_TRADING']:
            mirror_client = HTTP(
                testnet=config['TESTNET'],
                api_key=config['BYBIT_API_KEY_2'],
                api_secret=config['BYBIT_API_SECRET_2']
            )
            
            mirror_positions = await get_all_positions(client=mirror_client)
            for pos in mirror_positions:
                if float(pos.get('size', 0)) > 0:
                    positions.append({
                        'symbol': pos.get('symbol'),
                        'side': pos.get('side'),
                        'size': Decimal(str(pos.get('size'))),
                        'account': 'mirror'
                    })
        
        return positions
    
    # Get current positions
    current_positions = asyncio.run(get_current_positions())
    print(f"📍 Found {len(current_positions)} active positions to analyze")
    
    # Analyze each position
    reconstructed_monitors = {}
    
    for pos in current_positions:
        symbol = pos['symbol']
        side = pos['side']
        account = pos['account']
        size = pos['size']
        
        print(f"\n🔍 Analyzing {symbol} {side} ({account.upper()})...")
        
        # Analyze this position's history
        analysis = analyze_position_from_logs(symbol, side, account, log_entries)
        
        # Create monitor data structure
        monitor_key = f"{symbol}_{side}_{account}"
        monitor_data = {
            'symbol': symbol,
            'side': side,
            'account_type': account,
            'position_size': size,
            'current_size': size,
            'remaining_size': size,
            'last_known_size': size,
            'approach': 'CONSERVATIVE',
            'phase': analysis['phase'],
            'tp1_hit': analysis['tp1_hit'],
            'sl_moved_to_be': analysis['sl_moved_to_be'],
            'limit_orders_filled': analysis['limit_orders_filled'],
            'tp_orders': {},  # Will be populated from current API state
            'sl_order': {},   # Will be populated from current API state
            'limit_orders': [],
            'last_check': time.time(),
            'created_at': time.time(),
            'updated_at': time.time(),
            'analysis_metadata': {
                'tp_hits_detected': len(analysis['tp_hits']),
                'original_tps_found': len(analysis['original_tps']),
                'rebalancing_events': len(analysis['rebalancing_events']),
                'breakeven_events': len(analysis['breakeven_events']),
                'limit_fills': len(analysis['limit_fills'])
            }
        }
        
        reconstructed_monitors[monitor_key] = monitor_data
        
        # Print analysis summary
        print(f"   Phase: {analysis['phase']}")
        print(f"   TP1 Hit: {analysis['tp1_hit']}")
        print(f"   SL to Breakeven: {analysis['sl_moved_to_be']}")
        print(f"   Limit Fills: {len(analysis['limit_fills'])}")
        print(f"   TP Hits: {len(analysis['tp_hits'])}")
        print(f"   Rebalancing Events: {len(analysis['rebalancing_events'])}")
    
    # Now sync with current API state to get actual orders
    print(f"\n🔄 Syncing with current exchange state...")
    
    # Load existing pickle data or create new
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
    except FileNotFoundError:
        data = {}
    
    if 'enhanced_monitors' not in data:
        data['enhanced_monitors'] = {}
    
    # Update monitors with reconstructed data
    data['enhanced_monitors'].update(reconstructed_monitors)
    
    # Save to pickle
    with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
        pickle.dump(data, f)
    
    # Create signal for bot reload
    with open('.reload_enhanced_monitors.signal', 'w') as f:
        f.write(f"Log-based reconstruction: {len(reconstructed_monitors)} monitors at {time.time()}")
    
    print(f"\n✅ RECONSTRUCTION COMPLETE:")
    print(f"   Monitors reconstructed: {len(reconstructed_monitors)}")
    print(f"   Log entries analyzed: {len(log_entries)}")
    print(f"   Bot reload signal created")
    
    print(f"\n📋 Summary of reconstructed states:")
    for key, monitor in reconstructed_monitors.items():
        print(f"   {key}: Phase={monitor['phase']}, TP1_Hit={monitor['tp1_hit']}")

if __name__ == "__main__":
    main()