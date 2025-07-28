#!/usr/bin/env python3
"""
Balance TPs for positions that have had limit order fills
Only applies to positions where limit orders have been filled
"""
import os
import sys
import asyncio
import pickle
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_helpers import get_all_positions, get_all_open_orders
from execution.mirror_trader import bybit_client_2, ENABLE_MIRROR_TRADING
from execution.enhanced_tp_sl_manager import EnhancedTPSLManager

async def balance_tps_after_limit_fills():
    """Balance TPs for positions with filled limit orders"""
    
    print("⚖️ BALANCING TPs AFTER LIMIT ORDER FILLS")
    print("=" * 50)
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_tp_balance_{timestamp}"
    
    try:
        import shutil
        shutil.copy2('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_name)
        print(f"✅ Created backup: {backup_name}")
    except Exception as e:
        print(f"⚠️ Could not create backup: {e}")
    
    # Load current monitors
    print("\n📋 Loading current monitors...")
    try:
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        print(f"✅ Loaded {len(monitors)} monitors")
        
    except Exception as e:
        print(f"❌ Error loading monitors: {e}")
        return False
    
    # Get current positions to verify sizes
    print("\n📊 Fetching current positions for size verification...")
    
    main_positions = {}
    try:
        main_pos_list = await get_all_positions()
        for pos in main_pos_list:
            if float(pos.get('size', 0)) > 0:
                key = f"{pos['symbol']}_{pos['side']}_main"
                main_positions[key] = {
                    'current_size': float(pos['size']),
                    'avg_price': float(pos.get('avgPrice', 0))
                }
        print(f"✅ Main account: {len(main_positions)} positions")
    except Exception as e:
        print(f"❌ Error fetching main positions: {e}")
        return False
    
    mirror_positions = {}
    if ENABLE_MIRROR_TRADING and bybit_client_2:
        try:
            mirror_response = bybit_client_2.get_positions(category='linear', settleCoin='USDT')
            if mirror_response['retCode'] == 0:
                for pos in mirror_response['result']['list']:
                    if float(pos.get('size', 0)) > 0:
                        key = f"{pos['symbol']}_{pos['side']}_mirror"
                        mirror_positions[key] = {
                            'current_size': float(pos['size']),
                            'avg_price': float(pos.get('avgPrice', 0))
                        }
                print(f"✅ Mirror account: {len(mirror_positions)} positions")
        except Exception as e:
            print(f"❌ Error fetching mirror positions: {e}")
    
    # Analyze monitors for limit fill indicators
    print(f"\n🔍 ANALYZING MONITORS FOR LIMIT FILLS")
    print("=" * 40)
    
    positions_needing_rebalance = []
    positions_no_rebalance = []
    
    for monitor_key, monitor_data in monitors.items():
        try:
            symbol = monitor_data.get('symbol', '')
            side = monitor_data.get('side', '')
            account = monitor_data.get('account_type', 'main')
            
            # Check if this position has had limit fills
            limit_orders = monitor_data.get('limit_orders', [])
            limit_orders_filled = monitor_data.get('limit_orders_filled', 0)
            
            # Check position size vs original size  
            original_size = float(monitor_data.get('position_size', 0))
            current_size_from_monitor = float(monitor_data.get('current_size', 0))
            
            # Get actual current size from exchange
            actual_current_size = 0
            if monitor_key in main_positions:
                actual_current_size = main_positions[monitor_key]['current_size']
            elif monitor_key in mirror_positions:
                actual_current_size = mirror_positions[monitor_key]['current_size']
            
            # Determine if rebalancing is needed
            needs_rebalance = False
            reason = ""
            
            if limit_orders_filled > 0:
                needs_rebalance = True
                reason = f"{limit_orders_filled} limit orders filled"
            elif actual_current_size > original_size and original_size > 0:
                needs_rebalance = True
                reason = f"Position grew ({original_size:.2f} → {actual_current_size:.2f})"
            elif len(limit_orders) > 0 and actual_current_size > current_size_from_monitor:
                needs_rebalance = True
                reason = f"Size increase detected"
            
            position_info = {
                'monitor_key': monitor_key,
                'symbol': symbol,
                'side': side,
                'account': account,
                'original_size': original_size,
                'current_size': actual_current_size,
                'limit_orders': len(limit_orders),
                'limit_fills': limit_orders_filled,
                'reason': reason,
                'monitor_data': monitor_data
            }
            
            if needs_rebalance:
                positions_needing_rebalance.append(position_info)
            else:
                positions_no_rebalance.append(position_info)
                
        except Exception as e:
            print(f"⚠️ Error analyzing {monitor_key}: {e}")
            continue
    
    print(f"📊 Analysis Results:")
    print(f"   • Positions needing TP rebalance: {len(positions_needing_rebalance)}")
    print(f"   • Positions already balanced: {len(positions_no_rebalance)}")
    
    if positions_needing_rebalance:
        print(f"\n🔄 POSITIONS NEEDING TP REBALANCING:")
        for pos in positions_needing_rebalance:
            print(f"   • {pos['symbol']} {pos['side']} ({pos['account'].upper()})")
            print(f"     - Original: {pos['original_size']:.2f}, Current: {pos['current_size']:.2f}")
            print(f"     - Limit orders: {pos['limit_orders']}, Filled: {pos['limit_fills']}")
            print(f"     - Reason: {pos['reason']}")
            print()
    
    if not positions_needing_rebalance:
        print(f"\n✅ No positions need TP rebalancing!")
        print(f"   All positions are already properly balanced.")
        return True
    
    # Proceed automatically for CLI execution
    print(f"🔄 Proceeding automatically with TP rebalancing for {len(positions_needing_rebalance)} positions...")
    
    # Initialize Enhanced TP/SL Manager
    print(f"\n🔄 PROCEEDING WITH TP REBALANCING...")
    print("=" * 40)
    
    tp_sl_manager = EnhancedTPSLManager()
    
    successful_rebalances = 0
    failed_rebalances = 0
    
    for pos in positions_needing_rebalance:
        try:
            print(f"🔄 Rebalancing {pos['symbol']} {pos['side']} ({pos['account'].upper()})...")
            
            # Load monitor into manager
            monitor_key = pos['monitor_key']
            monitor_data = pos['monitor_data']
            tp_sl_manager.position_monitors[monitor_key] = monitor_data
            
            # Trigger TP rebalancing with current position size
            current_size = pos['current_size']  # Use the actual current position size
            success = await tp_sl_manager._adjust_all_orders_for_partial_fill(monitor_data, current_size)
            
            if success:
                print(f"   ✅ Successfully rebalanced {pos['symbol']} {pos['side']} ({pos['account']})")
                successful_rebalances += 1
            else:
                print(f"   ❌ Failed to rebalance {pos['symbol']} {pos['side']} ({pos['account']})")
                failed_rebalances += 1
                
        except Exception as e:
            print(f"   ❌ Error rebalancing {pos['symbol']} {pos['side']} ({pos['account']}): {e}")
            failed_rebalances += 1
    
    # Final summary
    print(f"\n📊 TP REBALANCING SUMMARY")
    print("=" * 30)
    print(f"✅ Successful rebalances: {successful_rebalances}")
    print(f"❌ Failed rebalances: {failed_rebalances}")
    print(f"📋 Total processed: {len(positions_needing_rebalance)}")
    
    if successful_rebalances > 0:
        print(f"\n🎯 {successful_rebalances} positions have been rebalanced!")
        print(f"   TPs are now properly adjusted for the current position sizes.")
    
    if failed_rebalances > 0:
        print(f"\n⚠️ {failed_rebalances} positions failed rebalancing.")
        print(f"   Check the logs above for specific error details.")
    
    return successful_rebalances > 0

if __name__ == "__main__":
    asyncio.run(balance_tps_after_limit_fills())