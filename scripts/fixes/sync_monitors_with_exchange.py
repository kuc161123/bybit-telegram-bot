#!/usr/bin/env python3
"""
Sync Monitors with Exchange Data
================================

This script will:
1. Fetch actual position data from exchange for both accounts
2. Update all monitors to reflect true position sizes
3. Recalculate which TPs have been filled based on correct data
4. Fix all discrepancies between monitors and exchange

CRITICAL: This fixes the major issue where monitors show HALF the actual position size
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

def create_sync_backup():
    """Create timestamped backup before sync"""
    timestamp = int(time.time())
    backup_name = f'bybit_bot_dashboard_v4.1_enhanced.pkl.backup_exchange_sync_{timestamp}'
    shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
    print(f"📁 Created backup: {backup_name}")
    return backup_name

async def sync_with_exchange():
    """Sync all monitors with actual exchange data"""
    print("🚨 CRITICAL MONITOR-EXCHANGE SYNC")
    print("="*60)
    print("⚠️ This will update ALL monitors to match exchange data")
    print("="*60)
    
    # Create backup
    backup_file = create_sync_backup()
    
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
        
        # Convert to dicts for easy lookup
        main_pos_dict = {pos['symbol']: pos for pos in main_positions}
        mirror_pos_dict = {pos['symbol']: pos for pos in mirror_positions}
        
        # Load pickle data
        print("\n📖 Loading monitor data...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"📊 Found {len(enhanced_monitors)} monitors")
        
        sync_stats = {
            'monitors_updated': 0,
            'size_corrections': 0,
            'tp_recalculations': 0,
            'positions_closed': 0
        }
        
        # Process each monitor
        for monitor_key, monitor_data in enhanced_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            account = monitor_data.get('account_type', 'main')
            
            print(f"\n{'='*60}")
            print(f"🔍 SYNCING: {symbol} ({account.upper()})")
            print(f"{'='*60}")
            
            # Get exchange position
            if account == 'main':
                exchange_pos = main_pos_dict.get(symbol)
            else:
                exchange_pos = mirror_pos_dict.get(symbol)
            
            if not exchange_pos:
                print(f"❌ No position on exchange - marking as closed")
                enhanced_monitors[monitor_key]['remaining_size'] = '0'
                enhanced_monitors[monitor_key]['phase'] = 'POSITION_CLOSED'
                enhanced_monitors[monitor_key]['position_closed'] = True
                sync_stats['positions_closed'] += 1
                continue
            
            # Get sizes
            monitor_total = Decimal(str(monitor_data.get('position_size', '0')))
            monitor_remaining = Decimal(str(monitor_data.get('remaining_size', '0')))
            exchange_size = Decimal(str(exchange_pos.get('size', '0')))
            
            print(f"📊 Monitor Total: {monitor_total}")
            print(f"📊 Monitor Remaining: {monitor_remaining}")
            print(f"📊 Exchange Actual: {exchange_size}")
            
            # Check if total size needs correction (doubled issue)
            if abs(exchange_size - monitor_remaining) > abs(exchange_size - monitor_total):
                # Exchange size is closer to total than remaining - likely the doubling issue
                print(f"🔧 Correcting doubled position size issue")
                print(f"   Old total: {monitor_total} → New total: {exchange_size * 2}")
                enhanced_monitors[monitor_key]['position_size'] = str(exchange_size * 2)
                monitor_total = exchange_size * 2
                sync_stats['size_corrections'] += 1
            
            # Update remaining size to match exchange
            if monitor_remaining != exchange_size:
                print(f"🔄 Updating remaining size: {monitor_remaining} → {exchange_size}")
                enhanced_monitors[monitor_key]['remaining_size'] = str(exchange_size)
                sync_stats['monitors_updated'] += 1
            
            # Recalculate filled amount
            filled_amount = monitor_total - exchange_size
            print(f"📈 Filled amount: {filled_amount} ({filled_amount/monitor_total*100:.1f}%)")
            
            # Recalculate which TPs were filled
            if filled_amount > 0:
                filled_tps = calculate_filled_tps(monitor_data, filled_amount, monitor_total)
                
                if filled_tps:
                    print(f"🎯 Recalculated filled TPs: {filled_tps}")
                    
                    # Update monitor state
                    enhanced_monitors[monitor_key]['filled_tps'] = filled_tps
                    
                    if 1 in filled_tps and not monitor_data.get('tp1_hit', False):
                        print(f"✅ Setting TP1 as hit")
                        enhanced_monitors[monitor_key]['tp1_hit'] = True
                        enhanced_monitors[monitor_key]['phase'] = 'PROFIT_TAKING'
                        enhanced_monitors[monitor_key]['phase_transition_time'] = time.time()
                        enhanced_monitors[monitor_key]['sl_moved_to_be'] = True
                        enhanced_monitors[monitor_key]['limit_orders_cancelled'] = True
                        sync_stats['tp_recalculations'] += 1
                    
                    # Check if all TPs filled
                    tp_count = len(monitor_data.get('tp_orders', {}))
                    if len(filled_tps) >= tp_count:
                        print(f"🎯 All TPs filled - marking as closed")
                        enhanced_monitors[monitor_key]['phase'] = 'POSITION_CLOSED'
                        enhanced_monitors[monitor_key]['position_closed'] = True
            
            # Add sync metadata
            enhanced_monitors[monitor_key]['exchange_synced'] = True
            enhanced_monitors[monitor_key]['sync_timestamp'] = time.time()
            enhanced_monitors[monitor_key]['exchange_size_at_sync'] = str(exchange_size)
        
        # Save updated data
        print(f"\n💾 Saving synced data...")
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
            pickle.dump(data, f)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 SYNC SUMMARY")
        print(f"{'='*60}")
        print(f"✅ Monitors Updated: {sync_stats['monitors_updated']}")
        print(f"🔧 Size Corrections: {sync_stats['size_corrections']}")
        print(f"🎯 TP Recalculations: {sync_stats['tp_recalculations']}")
        print(f"📕 Positions Closed: {sync_stats['positions_closed']}")
        
        print(f"\n🎉 EXCHANGE SYNC COMPLETED!")
        print(f"🔄 Restart the bot to activate corrected monitoring")
        
        return True
        
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Restore backup
        shutil.copy(backup_file, 'bybit_bot_dashboard_v4.1_enhanced.pkl')
        print(f"🔄 Restored backup from {backup_file}")
        return False

def calculate_filled_tps(monitor_data, filled_amount, total_size):
    """Calculate which TPs have been filled based on amount"""
    tp_orders = monitor_data.get('tp_orders', {})
    
    # Build list of TPs
    tp_list = []
    for order_id, order_info in tp_orders.items():
        tp_num = order_info.get('tp_number', 0)
        qty = Decimal(str(order_info.get('quantity', '0')))
        tp_list.append((tp_num, qty))
    
    # Sort by TP number
    tp_list.sort(key=lambda x: x[0])
    
    # Calculate filled TPs
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
    success = asyncio.run(sync_with_exchange())
    if success:
        print("\n✅ All monitors are now synced with exchange data!")
    else:
        print("\n❌ Sync failed - check errors above")