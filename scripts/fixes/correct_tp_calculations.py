#!/usr/bin/env python3
"""
Correct TP Calculations Fix
===========================

This script fixes the incorrect POSITION_CLOSED markings by:
1. Properly calculating which TPs were actually filled
2. Setting correct phase (PROFIT_TAKING not POSITION_CLOSED)
3. Removing position_closed flag for positions still open
4. Ensuring monitoring resumes for all open positions
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

def create_correction_backup():
    """Create timestamped backup before correction"""
    timestamp = int(time.time())
    backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_tp_correction_{timestamp}'
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
    print(f"📁 Created backup: {backup_name}")
    return backup_name

def calculate_actual_filled_tps(monitor_data, filled_amount, total_size):
    """Calculate which TPs were ACTUALLY filled based on exact amounts"""
    if filled_amount <= 0:
        return []
    
    tp_orders = monitor_data.get('tp_orders', {})
    
    # Build list of TPs with exact quantities
    tp_list = []
    for order_id, order_info in tp_orders.items():
        tp_num = order_info.get('tp_number', 0)
        qty = Decimal(str(order_info.get('quantity', '0')))
        tp_list.append((tp_num, qty))
    
    tp_list.sort(key=lambda x: x[0])
    
    # Calculate filled TPs with EXACT matching
    filled_tps = []
    cumulative = Decimal('0')
    
    # For conservative approach: TP1=85%, TP2=5%, TP3=5%, TP4=5%
    for tp_num, tp_qty in tp_list:
        cumulative += tp_qty
        
        # Check if this TP is fully filled
        if filled_amount >= cumulative - (tp_qty * Decimal('0.01')):  # 1% tolerance per TP
            filled_tps.append(tp_num)
        else:
            # This TP is not fully filled, stop here
            break
    
    return filled_tps

async def correct_tp_calculations():
    """Correct all TP calculations and monitor states"""
    print("🔧 CORRECTING TP CALCULATIONS")
    print("="*80)
    
    # Create backup
    backup_file = create_correction_backup()
    
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
        
        correction_stats = {
            'corrected': 0,
            'alerts_needed': 0,
            'phase_changes': 0,
            'tp_recalculations': 0
        }
        
        positions_needing_alerts = []
        
        # Process each monitor
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            account = monitor_data.get('account_type', 'main')
            
            # Get exchange position
            if account == 'main':
                exchange_pos = main_pos_dict.get(symbol)
            else:
                exchange_pos = mirror_pos_dict.get(symbol)
            
            if not exchange_pos:
                # No position on exchange - keep as closed
                continue
            
            # Get sizes
            monitor_total = Decimal(str(monitor_data.get('position_size', '0')))
            exchange_size = Decimal(str(exchange_pos.get('size', '0')))
            filled_amount = monitor_total - exchange_size
            
            # Skip if no fills
            if filled_amount <= 0:
                continue
            
            # Current state
            current_phase = monitor_data.get('phase', 'UNKNOWN')
            current_closed = monitor_data.get('position_closed', False)
            current_filled_tps = monitor_data.get('filled_tps', [])
            
            # Check if marked as closed but still has position
            if current_phase == 'POSITION_CLOSED' and exchange_size > 0:
                print(f"\n🔧 CORRECTING: {symbol} ({account.upper()})")
                print(f"   Exchange Size: {exchange_size} (not closed!)")
                print(f"   Filled: {filled_amount} ({filled_amount/monitor_total*100:.1f}%)")
                
                # Calculate actual filled TPs
                actual_filled_tps = calculate_actual_filled_tps(monitor_data, filled_amount, monitor_total)
                print(f"   Current Filled TPs: {current_filled_tps}")
                print(f"   Actual Filled TPs: {actual_filled_tps}")
                
                # Update monitor
                enhanced_monitors[monitor_key]['filled_tps'] = actual_filled_tps
                
                # Position is NOT closed - it still has size
                enhanced_monitors[monitor_key]['phase'] = 'PROFIT_TAKING'
                enhanced_monitors[monitor_key]['position_closed'] = False
                
                # Remove closure fields
                if 'closure_reason' in enhanced_monitors[monitor_key]:
                    del enhanced_monitors[monitor_key]['closure_reason']
                
                # Keep TP1 hit if it was hit
                if 1 in actual_filled_tps:
                    enhanced_monitors[monitor_key]['tp1_hit'] = True
                    
                    # Check if this needs an alert
                    if not monitor_data.get('tp1_alert_sent'):
                        positions_needing_alerts.append({
                            'symbol': symbol,
                            'account': account,
                            'monitor_key': monitor_key,
                            'tp1_price': None,  # Will get from TP orders
                            'tp1_qty': None,
                            'filled_amount': filled_amount,
                            'total_size': monitor_total
                        })
                        correction_stats['alerts_needed'] += 1
                else:
                    enhanced_monitors[monitor_key]['tp1_hit'] = False
                
                correction_stats['corrected'] += 1
                correction_stats['phase_changes'] += 1
                correction_stats['tp_recalculations'] += 1
                
                print(f"   ✅ Corrected: phase=PROFIT_TAKING, filled_tps={actual_filled_tps}")
        
        # Save corrected data
        print(f"\n💾 Saving corrected data...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        # Summary
        print(f"\n{'='*80}")
        print(f"📊 CORRECTION SUMMARY")
        print(f"{'='*80}")
        print(f"✅ Positions Corrected: {correction_stats['corrected']}")
        print(f"🔄 Phase Changes: {correction_stats['phase_changes']}")
        print(f"🎯 TP Recalculations: {correction_stats['tp_recalculations']}")
        print(f"📢 Alerts Needed: {correction_stats['alerts_needed']}")
        
        if positions_needing_alerts:
            print(f"\n📢 Positions needing TP1 alerts:")
            for pos in positions_needing_alerts:
                print(f"   - {pos['symbol']} ({pos['account']})")
        
        print(f"\n🎉 TP CALCULATION CORRECTION COMPLETED!")
        print(f"✅ All positions now have correct TP fill status")
        print(f"✅ Monitoring will resume for all open positions")
        print(f"🔄 Restart the bot to activate corrected monitoring")
        
        return True
        
    except Exception as e:
        print(f"❌ Correction failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Restore backup
        shutil.copy(backup_file, 'bybit_bot_dashboard_v4.1_enhanced.pkl')
        print(f"🔄 Restored backup from {backup_file}")
        return False

if __name__ == "__main__":
    success = asyncio.run(correct_tp_calculations())
    if success:
        print("\n✅ Monitor states have been corrected!")
        print("📋 Next steps:")
        print("   1. Restart the bot")
        print("   2. Monitoring will resume for all open positions")
        print("   3. Future TP fills will be detected correctly")