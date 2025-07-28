#!/usr/bin/env python3
"""
CAREFUL LOG ANALYSIS: Extract exact original order parameters from trading logs
This will analyze the logs thoroughly to understand what orders were originally created
and what happened to them, before making any changes.
"""
import re
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

def analyze_trading_logs_thoroughly():
    """Comprehensive analysis of trading logs to understand order history"""
    log_file = 'trading_bot.log'
    if not os.path.exists(log_file):
        print(f"❌ Log file {log_file} not found")
        return {}
    
    print("🔍 COMPREHENSIVE TRADING LOG ANALYSIS")
    print("=" * 50)
    
    # Data structures to track order lifecycle
    position_orders = defaultdict(lambda: {
        'symbol': '',
        'side': '',
        'account': '',
        'tp_orders': {},      # tp_number -> order_info
        'sl_orders': [],      # list of SL order events
        'limit_orders': [],   # list of limit order events
        'order_events': [],   # chronological list of all events
        'phases': [],         # phase transitions
        'rebalancing': []     # rebalancing events
    })
    
    # Patterns to look for
    patterns = {
        'tp_placement': [
            r'TP(\d+).*?placed.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'TP(\d+).*?created.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'placed.*?TP(\d+).*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)'
        ],
        'sl_placement': [
            r'SL.*?placed.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'Stop.*?Loss.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'placed.*?SL.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)'
        ],
        'limit_placement': [
            r'Limit.*?(\d+/\d+).*?placed.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)',
            r'placed.*?limit.*?(\d+\.?\d*)\s*@\s*(\d+\.?\d*)'
        ],
        'order_fill': [
            r'(TP\d+|Limit \d+/\d+|SL).*?(filled|hit)',
            r'(filled|hit).*?(TP\d+|Limit \d+/\d+|SL)'
        ],
        'order_cancellation': [
            r'cancel.*?(TP\d+|SL|limit)',
            r'(TP\d+|SL|limit).*?cancel'
        ],
        'rebalancing': [
            r'rebalanc.*?TP',
            r'TP.*?rebalanc',
            r'adjust.*?TP'
        ],
        'breakeven': [
            r'breakeven',
            r'moved.*?SL',
            r'SL.*?moved'
        ]
    }
    
    print("📖 Reading and parsing log file...")
    
    total_lines = 0
    relevant_lines = 0
    
    with open(log_file, 'r') as f:
        for line_num, line in enumerate(f, 1):
            total_lines += 1
            
            # Extract timestamp
            timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if not timestamp_match:
                continue
            
            timestamp = timestamp_match.group(1)
            message = line[timestamp_match.end():].strip()
            
            # Check if line is relevant
            if not any(keyword in message for keyword in [
                'TP', 'SL', 'limit', 'placed', 'filled', 'cancel', 'rebalance', 'breakeven',
                'Conservative', 'ALTUSDT', 'CHRUSDT', 'AVAXUSDT', 'KSMUSDT', 'GMTUSDT'
            ]):
                continue
            
            relevant_lines += 1
            
            # Extract symbol
            symbol_match = re.search(r'([A-Z]{3,}USDT)', message)
            if not symbol_match:
                continue
            
            symbol = symbol_match.group(1)
            
            # Extract side
            side_match = re.search(r'(Buy|Sell)', message, re.IGNORECASE)
            if not side_match:
                continue
            
            side = side_match.group(1)
            
            # Determine account
            account = 'main'
            if 'MIRROR' in message or 'mirror' in message or '🪞' in message:
                account = 'mirror'
            
            position_key = f"{symbol}_{side}_{account}"
            
            # Initialize position data
            if not position_orders[position_key]['symbol']:
                position_orders[position_key]['symbol'] = symbol
                position_orders[position_key]['side'] = side
                position_orders[position_key]['account'] = account
            
            # Create event record
            event = {
                'timestamp': timestamp,
                'line_number': line_num,
                'message': message,
                'event_type': 'unknown'
            }
            
            # Categorize the event
            if any(pattern in message.lower() for pattern in ['tp', 'take profit']):
                # TP-related event
                if any(pattern in message.lower() for pattern in ['placed', 'created']):
                    event['event_type'] = 'tp_placement'
                    # Extract TP details
                    for pattern in patterns['tp_placement']:
                        match = re.search(pattern, message, re.IGNORECASE)
                        if match:
                            tp_number = int(match.group(1))
                            quantity = Decimal(match.group(2))
                            price = Decimal(match.group(3))
                            
                            position_orders[position_key]['tp_orders'][tp_number] = {
                                'tp_number': tp_number,
                                'quantity': quantity,
                                'price': price,
                                'timestamp': timestamp,
                                'status': 'placed'
                            }
                            break
                
                elif any(pattern in message.lower() for pattern in ['filled', 'hit']):
                    event['event_type'] = 'tp_fill'
                
                elif any(pattern in message.lower() for pattern in ['cancel']):
                    event['event_type'] = 'tp_cancellation'
                
                elif any(pattern in message.lower() for pattern in ['rebalance', 'adjust']):
                    event['event_type'] = 'tp_rebalancing'
                    position_orders[position_key]['rebalancing'].append(event)
            
            elif any(pattern in message.lower() for pattern in ['sl', 'stop loss', 'stop']):
                # SL-related event
                if any(pattern in message.lower() for pattern in ['placed', 'created']):
                    event['event_type'] = 'sl_placement'
                    # Extract SL details
                    for pattern in patterns['sl_placement']:
                        match = re.search(pattern, message, re.IGNORECASE)
                        if match:
                            quantity = Decimal(match.group(1))
                            price = Decimal(match.group(2))
                            
                            sl_info = {
                                'quantity': quantity,
                                'price': price,
                                'timestamp': timestamp,
                                'status': 'placed'
                            }
                            position_orders[position_key]['sl_orders'].append(sl_info)
                            break
                
                elif any(pattern in message.lower() for pattern in ['filled', 'hit']):
                    event['event_type'] = 'sl_fill'
                
                elif any(pattern in message.lower() for pattern in ['cancel']):
                    event['event_type'] = 'sl_cancellation'
                
                elif any(pattern in message.lower() for pattern in ['breakeven', 'moved']):
                    event['event_type'] = 'sl_breakeven'
            
            elif any(pattern in message.lower() for pattern in ['limit']):
                # Limit order event
                if any(pattern in message.lower() for pattern in ['placed', 'created']):
                    event['event_type'] = 'limit_placement'
                elif any(pattern in message.lower() for pattern in ['filled', 'fill']):
                    event['event_type'] = 'limit_fill'
                elif any(pattern in message.lower() for pattern in ['cancel']):
                    event['event_type'] = 'limit_cancellation'
            
            # Add event to position history
            position_orders[position_key]['order_events'].append(event)
    
    print(f"📊 Log Analysis Results:")
    print(f"   Total lines read: {total_lines:,}")
    print(f"   Relevant lines found: {relevant_lines:,}")
    print(f"   Positions with order history: {len(position_orders)}")
    
    # Analyze each position's order history
    print(f"\n📋 POSITION ORDER ANALYSIS")
    print("=" * 40)
    
    for position_key, data in position_orders.items():
        symbol = data['symbol']
        side = data['side']
        account = data['account']
        
        print(f"\n🔍 {position_key}:")
        print(f"   Total events: {len(data['order_events'])}")
        
        # Count event types
        event_counts = {}
        for event in data['order_events']:
            event_type = event['event_type']
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        print(f"   Event breakdown: {dict(event_counts)}")
        
        # Show TP orders found
        if data['tp_orders']:
            print(f"   TP Orders found: {len(data['tp_orders'])}")
            for tp_num, tp_info in sorted(data['tp_orders'].items()):
                print(f"      TP{tp_num}: {tp_info['quantity']} @ {tp_info['price']} ({tp_info['timestamp']})")
        
        # Show SL orders found
        if data['sl_orders']:
            print(f"   SL Orders found: {len(data['sl_orders'])}")
            for i, sl_info in enumerate(data['sl_orders']):
                print(f"      SL{i+1}: {sl_info['quantity']} @ {sl_info['price']} ({sl_info['timestamp']})")
        
        # Show recent events (last 5)
        if data['order_events']:
            print(f"   Recent events:")
            for event in data['order_events'][-5:]:
                print(f"      {event['timestamp']}: {event['event_type']} - {event['message'][:60]}...")
    
    return position_orders

def compare_logs_with_exchange_state():
    """Compare what logs show vs what's actually on the exchange"""
    print(f"\n🔄 COMPARING LOGS WITH EXCHANGE STATE")
    print("=" * 45)
    
    # This will be filled in next step
    print("Next: Compare log analysis with current exchange orders...")
    
    return {}

def main():
    """Main analysis function"""
    print("🎯 STARTING CAREFUL ANALYSIS")
    print("This will take time to ensure accuracy...")
    print()
    
    # Step 1: Analyze logs thoroughly
    position_orders = analyze_trading_logs_thoroughly()
    
    # Step 2: Compare with exchange state
    exchange_comparison = compare_logs_with_exchange_state()
    
    print(f"\n✅ ANALYSIS COMPLETE")
    print(f"Found order history for {len(position_orders)} positions")
    print(f"Ready for careful order reconstruction...")
    
    return {
        'position_orders': position_orders,
        'exchange_comparison': exchange_comparison
    }

if __name__ == "__main__":
    main()