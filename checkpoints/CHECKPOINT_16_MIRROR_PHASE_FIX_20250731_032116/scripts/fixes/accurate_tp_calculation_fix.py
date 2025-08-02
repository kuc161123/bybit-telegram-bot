#!/usr/bin/env python3
"""
Accurate TP Calculation Fix
===========================

More accurate calculation of which TPs were actually filled.
For conservative approach:
- TP1: 85% of position
- TP2: 5% of position  
- TP3: 5% of position
- TP4: 5% of position
"""
import asyncio
import pickle
import sys
import os
import time
import shutil
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from clients.bybit_client import create_bybit_client
from clients.bybit_helpers import get_all_positions
from execution.mirror_trader import bybit_client_2

def create_accurate_backup():
    """Create timestamped backup"""
    timestamp = int(time.time())
    backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_accurate_tp_{timestamp}'
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
    print(f"📁 Created backup: {backup_name}")
    return backup_name

def calculate_tp_percentages(filled_percent):
    """Calculate which TPs are filled based on percentage"""
    filled_tps = []
    
    # Conservative approach percentages (cumulative)
    # TP1: 85%
    # TP1+TP2: 90%
    # TP1+TP2+TP3: 95%
    # TP1+TP2+TP3+TP4: 100%
    
    if filled_percent >= 84:  # Allow 1% tolerance
        filled_tps.append(1)
    if filled_percent >= 89:
        filled_tps.append(2)
    if filled_percent >= 94:
        filled_tps.append(3)
    if filled_percent >= 99:
        filled_tps.append(4)
    
    return filled_tps

async def accurate_tp_calculation():
    """Apply accurate TP calculations"""
    print("🎯 ACCURATE TP CALCULATION FIX")
    print("="*80)
    
    # Create backup
    backup_file = create_accurate_backup()
    
    try:
        # Initialize clients
        print("📡 Connecting to exchange...")
        bybit_client = create_bybit_client()
        
        if not bybit_client_2:
            print("❌ Mirror client not available!")
            return False
        
        # Get positions from exchange
        print("📊 Fetching actual positions from exchange...")
        main_positions = await get_all_positions(bybit_client)
        mirror_positions = await get_all_positions(bybit_client_2)
        
        print(f"✅ Main account: {len(main_positions)} positions")
        print(f"✅ Mirror account: {len(mirror_positions)} positions")
        
        # Convert to dicts
        main_pos_dict = {pos['symbol']: pos for pos in main_positions}
        mirror_pos_dict = {pos['symbol']: pos for pos in mirror_positions}
        
        # Load pickle data
        print("\n📖 Loading monitor data...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Found {len(enhanced_monitors)} monitors")
        
        fix_stats = {
            'total_processed': 0,
            'tp_corrections': 0,
            'phase_corrections': 0,
            'tp1_hits': 0,
            'positions_still_open': 0
        }
        
        # Process each monitor
        print("\n" + "="*80)
        print("APPLYING ACCURATE TP CALCULATIONS")
        print("="*80)
        
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            account = monitor_data.get('account_type', 'main')
            
            # Skip if not PROFIT_TAKING phase
            if monitor_data.get('phase') != 'PROFIT_TAKING':
                continue
            
            fix_stats['total_processed'] += 1
            
            # Get exchange position
            if account == 'main':
                exchange_pos = main_pos_dict.get(symbol)
            else:
                exchange_pos = mirror_pos_dict.get(symbol)
            
            if not exchange_pos:
                continue
            
            # Calculate filled percentage
            monitor_total = Decimal(str(monitor_data.get('position_size', '0')))
            exchange_size = Decimal(str(exchange_pos.get('size', '0')))
            filled_amount = monitor_total - exchange_size
            filled_percent = (filled_amount / monitor_total * 100) if monitor_total > 0 else 0
            
            # Calculate actual filled TPs
            actual_filled_tps = calculate_tp_percentages(filled_percent)
            current_filled_tps = monitor_data.get('filled_tps', [])
            
            if actual_filled_tps != current_filled_tps:
                print(f"\n🔧 {symbol} ({account.upper()})")
                print(f"   Total Size: {monitor_total}")
                print(f"   Remaining: {exchange_size}")
                print(f"   Filled: {filled_amount} ({filled_percent:.1f}%)")
                print(f"   Current TPs: {current_filled_tps}")
                print(f"   Actual TPs: {actual_filled_tps}")
                
                # Update filled TPs
                enhanced_monitors[monitor_key]['filled_tps'] = actual_filled_tps
                fix_stats['tp_corrections'] += 1
                
                # Update TP1 hit flag
                if 1 in actual_filled_tps:
                    enhanced_monitors[monitor_key]['tp1_hit'] = True
                    fix_stats['tp1_hits'] += 1
                else:
                    enhanced_monitors[monitor_key]['tp1_hit'] = False
                
                print(f"   ✅ Updated to: {actual_filled_tps}")
            
            # Count open positions
            if exchange_size > 0:
                fix_stats['positions_still_open'] += 1
        
        # Save corrected data
        print(f"\n💾 Saving accurate TP data...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        # Summary
        print(f"\n" + "="*80)
        print(f"📊 ACCURATE TP CALCULATION SUMMARY")
        print(f"="*80)
        print(f"📈 Positions Processed: {fix_stats['total_processed']}")
        print(f"🔧 TP Corrections Made: {fix_stats['tp_corrections']}")
        print(f"🎯 TP1 Hits Confirmed: {fix_stats['tp1_hits']}")
        print(f"📗 Positions Still Open: {fix_stats['positions_still_open']}")
        
        print(f"\n🎉 ACCURATE TP CALCULATION COMPLETED!")
        print(f"✅ All TPs now reflect actual fill percentages")
        print(f"✅ Conservative approach percentages applied correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Restore backup
        shutil.copy(backup_file, 'bybit_bot_dashboard_v4.1_enhanced.pkl')
        print(f"🔄 Restored backup from {backup_file}")
        return False

if __name__ == "__main__":
    success = asyncio.run(accurate_tp_calculation())
    if success:
        print("\n✅ TP calculations are now accurate!")
        print("📋 Next steps:")
        print("   1. Restart the bot to resume monitoring")
        print("   2. Enhanced TP/SL manager will track remaining TPs")
        print("   3. Alerts will be sent for future TP fills")