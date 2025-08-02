#!/usr/bin/env python3
"""
Comprehensive Monitor Verification
==================================

This script performs a deep analysis to understand why monitors aren't working:
1. Compare pickle data with exchange positions
2. Check monitor states vs actual fills
3. Identify why TP hits aren't triggering actions
4. Verify monitor functionality for all positions
"""
import asyncio
import pickle
import sys
import os
import time
from decimal import Decimal
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clients.bybit_client import create_bybit_client
from clients.bybit_helpers import get_all_positions
from execution.mirror_trader import bybit_client_2

async def comprehensive_monitor_verification():
    """Comprehensive verification of monitor functionality"""
    print("🔍 COMPREHENSIVE MONITOR VERIFICATION")
    print("="*80)
    print(f"Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    try:
        # Initialize clients
        print("\n📡 Connecting to exchange...")
        bybit_client = create_bybit_client()
        
        if not bybit_client_2:
            print("❌ Mirror client not available!")
            return
        
        # Get positions from exchange
        print("📊 Fetching actual positions from exchange...")
        main_positions = await get_all_positions(bybit_client)
        mirror_positions = await get_all_positions(bybit_client_2)
        
        print(f"✅ Main account: {len(main_positions)} positions")
        print(f"✅ Mirror account: {len(mirror_positions)} positions")
        
        # Load pickle data
        print("\n📖 Loading monitor data from pickle...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Found {len(enhanced_monitors)} monitors in pickle")
        
        # Create position dictionaries
        main_pos_dict = {pos['symbol']: pos for pos in main_positions}
        mirror_pos_dict = {pos['symbol']: pos for pos in mirror_positions}
        
        # Analysis results
        analysis_results = {
            'working_correctly': [],
            'not_detecting_fills': [],
            'closed_but_still_monitored': [],
            'monitor_without_position': [],
            'position_without_monitor': [],
            'phase_mismatches': []
        }
        
        # Analyze each monitor
        print("\n" + "="*80)
        print("DETAILED POSITION ANALYSIS")
        print("="*80)
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            account = monitor_data.get('account_type', 'main')
            
            print(f"\n{'='*60}")
            print(f"📈 {symbol} ({account.upper()})")
            print(f"Monitor Key: {monitor_key}")
            print(f"{'='*60}")
            
            # Get exchange position
            if account == 'main':
                exchange_pos = main_pos_dict.get(symbol)
            else:
                exchange_pos = mirror_pos_dict.get(symbol)
            
            # Monitor data
            monitor_total = Decimal(str(monitor_data.get('position_size', '0')))
            monitor_remaining = Decimal(str(monitor_data.get('remaining_size', '0')))
            monitor_filled = monitor_total - monitor_remaining
            phase = monitor_data.get('phase', 'UNKNOWN')
            tp1_hit = monitor_data.get('tp1_hit', False)
            filled_tps = monitor_data.get('filled_tps', [])
            position_closed = monitor_data.get('position_closed', False)
            
            print(f"\n📊 MONITOR DATA:")
            print(f"   Total Size: {monitor_total}")
            print(f"   Remaining: {monitor_remaining}")
            print(f"   Filled: {monitor_filled} ({monitor_filled/monitor_total*100:.1f}%)")
            print(f"   Phase: {phase}")
            print(f"   TP1 Hit: {tp1_hit}")
            print(f"   Filled TPs: {filled_tps}")
            print(f"   Position Closed Flag: {position_closed}")
            
            if not exchange_pos:
                print(f"\n❌ NO POSITION ON EXCHANGE!")
                if phase != 'POSITION_CLOSED':
                    print(f"   ⚠️ Monitor active but position doesn't exist")
                    analysis_results['monitor_without_position'].append({
                        'symbol': symbol,
                        'account': account,
                        'phase': phase,
                        'monitor_key': monitor_key
                    })
                else:
                    print(f"   ✅ Position correctly marked as closed")
                continue
            
            # Exchange data
            exchange_size = Decimal(str(exchange_pos.get('size', '0')))
            exchange_filled = monitor_total - exchange_size
            
            print(f"\n📊 EXCHANGE DATA:")
            print(f"   Current Size: {exchange_size}")
            print(f"   Calculated Filled: {exchange_filled} ({exchange_filled/monitor_total*100:.1f}%)")
            
            # Compare monitor vs exchange
            print(f"\n🔍 COMPARISON:")
            size_match = abs(monitor_remaining - exchange_size) < Decimal('0.01')
            print(f"   Size Match: {'✅' if size_match else '❌'} (Difference: {abs(monitor_remaining - exchange_size)})")
            
            # Analyze fills
            if exchange_filled > 0:
                # Calculate expected filled TPs
                expected_tps = calculate_expected_filled_tps(monitor_data, exchange_filled, monitor_total)
                print(f"   Expected Filled TPs: {expected_tps}")
                print(f"   Monitor Shows TPs: {filled_tps}")
                
                # Check if monitor detected fills correctly
                if not tp1_hit and 1 in expected_tps:
                    print(f"\n🚨 CRITICAL ISSUE: TP1 hit but not detected!")
                    print(f"   Exchange shows {exchange_filled} filled")
                    print(f"   Monitor failed to detect TP1 hit")
                    analysis_results['not_detecting_fills'].append({
                        'symbol': symbol,
                        'account': account,
                        'exchange_filled': exchange_filled,
                        'monitor_filled': monitor_filled,
                        'expected_tps': expected_tps,
                        'detected_tps': filled_tps
                    })
                
                # Check phase
                if exchange_filled > 0 and phase in ['BUILDING', 'MONITORING']:
                    print(f"\n⚠️ Phase mismatch: Should be PROFIT_TAKING but is {phase}")
                    analysis_results['phase_mismatches'].append({
                        'symbol': symbol,
                        'account': account,
                        'phase': phase,
                        'filled_amount': exchange_filled
                    })
            
            # Check if position should be closed
            if phase == 'POSITION_CLOSED' and exchange_size > 0:
                print(f"\n⚠️ Monitor shows closed but position still open on exchange!")
                analysis_results['closed_but_still_monitored'].append({
                    'symbol': symbol,
                    'account': account,
                    'exchange_size': exchange_size
                })
            
            # Determine if monitor is working correctly
            if size_match and tp1_hit == (1 in expected_tps if exchange_filled > 0 else False):
                print(f"\n✅ Monitor appears to be working correctly")
                analysis_results['working_correctly'].append(symbol + "_" + account)
            
        # Check for positions without monitors
        print("\n" + "="*80)
        print("CHECKING FOR POSITIONS WITHOUT MONITORS")
        print("="*80)
        
        all_monitor_symbols = set()
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol')
            account = monitor_data.get('account_type')
            all_monitor_symbols.add(f"{symbol}_{account}")
        
        # Check main positions
        for pos in main_positions:
            symbol = pos['symbol']
            if f"{symbol}_main" not in all_monitor_symbols:
                print(f"\n❌ {symbol} (MAIN): Position exists but NO MONITOR!")
                analysis_results['position_without_monitor'].append({
                    'symbol': symbol,
                    'account': 'main',
                    'size': pos.get('size')
                })
        
        # Check mirror positions
        for pos in mirror_positions:
            symbol = pos['symbol']
            if f"{symbol}_mirror" not in all_monitor_symbols:
                print(f"\n❌ {symbol} (MIRROR): Position exists but NO MONITOR!")
                analysis_results['position_without_monitor'].append({
                    'symbol': symbol,
                    'account': 'mirror',
                    'size': pos.get('size')
                })
        
        # Summary Report
        print("\n" + "="*80)
        print("📊 ANALYSIS SUMMARY")
        print("="*80)
        
        print(f"\n✅ Working Correctly: {len(analysis_results['working_correctly'])}")
        for item in analysis_results['working_correctly']:
            print(f"   - {item}")
        
        print(f"\n🚨 Not Detecting Fills: {len(analysis_results['not_detecting_fills'])}")
        for item in analysis_results['not_detecting_fills']:
            print(f"   - {item['symbol']} ({item['account']}): {item['exchange_filled']} filled but monitor shows {item['monitor_filled']}")
        
        print(f"\n⚠️ Phase Mismatches: {len(analysis_results['phase_mismatches'])}")
        for item in analysis_results['phase_mismatches']:
            print(f"   - {item['symbol']} ({item['account']}): Phase={item['phase']} but {item['filled_amount']} filled")
        
        print(f"\n📕 Closed But Still Monitored: {len(analysis_results['closed_but_still_monitored'])}")
        for item in analysis_results['closed_but_still_monitored']:
            print(f"   - {item['symbol']} ({item['account']}): Still has {item['exchange_size']} on exchange")
        
        print(f"\n❌ Monitor Without Position: {len(analysis_results['monitor_without_position'])}")
        for item in analysis_results['monitor_without_position']:
            print(f"   - {item['symbol']} ({item['account']}): Phase={item['phase']}")
        
        print(f"\n❌ Position Without Monitor: {len(analysis_results['position_without_monitor'])}")
        for item in analysis_results['position_without_monitor']:
            print(f"   - {item['symbol']} ({item['account']}): Size={item['size']}")
        
        # Root Cause Analysis
        print("\n" + "="*80)
        print("🔍 ROOT CAUSE ANALYSIS")
        print("="*80)
        
        if len(analysis_results['not_detecting_fills']) > 0:
            print("\n1. 🚨 MONITORS NOT DETECTING FILLS")
            print("   The Enhanced TP/SL manager is NOT properly detecting when TPs are filled.")
            print("   This appears to be because:")
            print("   - The monitoring loop is not checking position size changes")
            print("   - The system relies on order fill events that may be missed")
            print("   - Position size comparison logic may be faulty")
        
        if len(analysis_results['closed_but_still_monitored']) > 0:
            print("\n2. 📕 CLOSED POSITIONS STILL BEING MONITORED")
            print("   Monitors for closed positions are not being removed.")
            print("   This causes:")
            print("   - Unnecessary monitoring overhead")
            print("   - Confusion in the dashboard display")
            print("   - Potential for incorrect actions on non-existent positions")
        
        if len(analysis_results['phase_mismatches']) > 0:
            print("\n3. ⚠️ PHASE TRANSITION FAILURES")
            print("   Monitors are not transitioning phases when TPs are hit.")
            print("   This prevents:")
            print("   - SL movement to breakeven")
            print("   - Limit order cancellation")
            print("   - Proper TP rebalancing")
        
        # Recommendations
        print("\n" + "="*80)
        print("💡 RECOMMENDATIONS")
        print("="*80)
        
        print("\n1. IMMEDIATE ACTIONS NEEDED:")
        print("   - The monitoring system needs to actively compare position sizes")
        print("   - Monitors for closed positions must be removed")
        print("   - Phase transitions must be triggered based on position size changes")
        
        print("\n2. MONITOR SYSTEM ISSUES:")
        print("   - The system is maintaining monitors for positions that don't exist")
        print("   - Fill detection is not working for many positions")
        print("   - The pickle updates we made are not being acted upon by the monitoring loop")
        
        print("\n3. LIKELY CAUSE:")
        print("   - The Enhanced TP/SL manager monitoring loop is not properly")
        print("     checking for position size changes to detect TP fills")
        print("   - It may be relying solely on order fill events which can be missed")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

def calculate_expected_filled_tps(monitor_data, filled_amount, total_size):
    """Calculate which TPs should have been filled based on amount"""
    if filled_amount <= 0:
        return []
    
    tp_orders = monitor_data.get('tp_orders', {})
    tp_list = []
    
    for order_id, order_info in tp_orders.items():
        tp_num = order_info.get('tp_number', 0)
        qty = Decimal(str(order_info.get('quantity', '0')))
        tp_list.append((tp_num, qty))
    
    tp_list.sort(key=lambda x: x[0])
    
    filled_tps = []
    cumulative = Decimal('0')
    tolerance = total_size * Decimal('0.01')  # 1% tolerance
    
    for tp_num, tp_qty in tp_list:
        if cumulative + tp_qty <= filled_amount + tolerance:
            filled_tps.append(tp_num)
            cumulative += tp_qty
        else:
            break
    
    return filled_tps

if __name__ == "__main__":
    asyncio.run(comprehensive_monitor_verification())