#!/usr/bin/env python3
"""
Compare Positions with Exchange
===============================

Compare pickle monitor data with actual exchange positions to find discrepancies.
"""
import asyncio
import pickle
import sys
import os
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clients.bybit_client import create_bybit_client
from clients.bybit_helpers import get_all_positions
from execution.mirror_trader import bybit_client_2

async def compare_with_exchange():
    """Compare monitor data with exchange positions"""
    print("🔍 COMPARING POSITIONS WITH EXCHANGE DATA")
    print("="*60)
    
    try:
        # Initialize clients
        bybit_client = create_bybit_client()
        # bybit_client_2 is already imported from mirror_trader
        
        # Get positions from exchange
        print("📡 Fetching positions from exchange...")
        main_positions = await get_all_positions(bybit_client)
        mirror_positions = await get_all_positions(bybit_client_2)
        
        # Load pickle data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        
        # Convert exchange positions to dict for easy lookup
        main_pos_dict = {pos['symbol']: pos for pos in main_positions}
        mirror_pos_dict = {pos['symbol']: pos for pos in mirror_positions}
        
        print(f"📊 Main positions on exchange: {len(main_positions)}")
        print(f"📊 Mirror positions on exchange: {len(mirror_positions)}")
        print(f"📊 Monitors in pickle: {len(enhanced_monitors)}")
        
        discrepancies = []
        
        # Check each monitor against exchange
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            account = monitor_data.get('account_type', 'main')
            
            # Get exchange position
            if account == 'main':
                exchange_pos = main_pos_dict.get(symbol)
            else:
                exchange_pos = mirror_pos_dict.get(symbol)
            
            if not exchange_pos:
                print(f"\n❌ {symbol} ({account}): Monitor exists but NO POSITION on exchange!")
                discrepancies.append({
                    'symbol': symbol,
                    'account': account,
                    'issue': 'NO_EXCHANGE_POSITION',
                    'monitor_size': monitor_data.get('position_size'),
                    'monitor_remaining': monitor_data.get('remaining_size')
                })
                continue
            
            # Compare sizes
            monitor_total = Decimal(str(monitor_data.get('position_size', '0')))
            monitor_remaining = Decimal(str(monitor_data.get('remaining_size', '0')))
            monitor_filled = monitor_total - monitor_remaining
            
            exchange_size = Decimal(str(exchange_pos.get('size', '0')))
            exchange_filled = monitor_total - exchange_size
            
            # Check for discrepancies
            if abs(monitor_remaining - exchange_size) > Decimal('0.01'):
                print(f"\n⚠️ {symbol} ({account}): SIZE MISMATCH!")
                print(f"   Monitor: {monitor_remaining} remaining")
                print(f"   Exchange: {exchange_size} actual")
                print(f"   Difference: {abs(monitor_remaining - exchange_size)}")
                
                discrepancies.append({
                    'symbol': symbol,
                    'account': account,
                    'issue': 'SIZE_MISMATCH',
                    'monitor_remaining': monitor_remaining,
                    'exchange_size': exchange_size,
                    'difference': abs(monitor_remaining - exchange_size)
                })
                
                # Check if more TPs were filled than detected
                tp1_hit = monitor_data.get('tp1_hit', False)
                filled_tps = monitor_data.get('filled_tps', [])
                
                if exchange_filled > monitor_filled and not tp1_hit:
                    print(f"   🚨 Exchange shows MORE fills than monitor detected!")
                    print(f"   Monitor filled: {monitor_filled}")
                    print(f"   Exchange filled: {exchange_filled}")
        
        # Check for exchange positions without monitors
        print(f"\n{'='*60}")
        print("🔍 Checking for positions without monitors...")
        
        all_monitor_symbols = set()
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol')
            account = monitor_data.get('account_type')
            all_monitor_symbols.add(f"{symbol}_{account}")
        
        # Check main positions
        for pos in main_positions:
            symbol = pos['symbol']
            if f"{symbol}_main" not in all_monitor_symbols:
                print(f"❌ {symbol} (MAIN): Position on exchange but NO MONITOR!")
                discrepancies.append({
                    'symbol': symbol,
                    'account': 'main',
                    'issue': 'NO_MONITOR',
                    'exchange_size': pos.get('size')
                })
        
        # Check mirror positions  
        for pos in mirror_positions:
            symbol = pos['symbol']
            if f"{symbol}_mirror" not in all_monitor_symbols:
                print(f"❌ {symbol} (MIRROR): Position on exchange but NO MONITOR!")
                discrepancies.append({
                    'symbol': symbol,
                    'account': 'mirror',
                    'issue': 'NO_MONITOR',
                    'exchange_size': pos.get('size')
                })
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 DISCREPANCY SUMMARY:")
        print(f"   Total discrepancies: {len(discrepancies)}")
        
        if discrepancies:
            print(f"\n🚨 Issues found:")
            
            no_exchange = [d for d in discrepancies if d['issue'] == 'NO_EXCHANGE_POSITION']
            size_mismatch = [d for d in discrepancies if d['issue'] == 'SIZE_MISMATCH']
            no_monitor = [d for d in discrepancies if d['issue'] == 'NO_MONITOR']
            
            if no_exchange:
                print(f"\n❌ Monitors without exchange positions: {len(no_exchange)}")
                for d in no_exchange:
                    print(f"   - {d['symbol']} ({d['account']})")
            
            if size_mismatch:
                print(f"\n⚠️ Size mismatches: {len(size_mismatch)}")
                for d in size_mismatch:
                    print(f"   - {d['symbol']} ({d['account']}): {d['difference']} difference")
            
            if no_monitor:
                print(f"\n❌ Exchange positions without monitors: {len(no_monitor)}")
                for d in no_monitor:
                    print(f"   - {d['symbol']} ({d['account']}): {d['exchange_size']} size")
        else:
            print(f"\n✅ No discrepancies found!")
            
    except Exception as e:
        print(f"❌ Comparison failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(compare_with_exchange())