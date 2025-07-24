#!/usr/bin/env python3
"""
Identify Missing Monitors - Complete Analysis
Compares actual positions from Bybit with monitors in pickle file
"""

import asyncio
import logging
import pickle
import sys
import os
from decimal import Decimal
from typing import Dict, List, Tuple
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from clients.bybit_client import bybit_client
from clients.bybit_helpers import get_all_positions
from execution.mirror_trader import bybit_client_2

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_all_active_positions() -> Tuple[List[Dict], List[Dict]]:
    """Get all positions from both main and mirror accounts"""
    try:
        # Get main account positions
        logger.info("📊 Fetching main account positions...")
        main_positions = await get_all_positions(client=bybit_client)
        
        # Get mirror account positions
        logger.info("📊 Fetching mirror account positions...")
        mirror_positions = await get_all_positions(client=bybit_client_2)
        
        return main_positions, mirror_positions
    
    except Exception as e:
        logger.error(f"❌ Error fetching positions: {e}")
        return [], []

def analyze_monitors_vs_positions(main_positions: List[Dict], mirror_positions: List[Dict]) -> Dict:
    """Analyze discrepancies between positions and monitors"""
    
    # Load pickle file
    pickle_file = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    try:
        with open(pickle_file, 'rb') as f:
            data = pickle.load(f)
        
        # Get monitors from pickle
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        logger.info(f"📊 Found {len(monitors)} monitors in pickle file")
        
        # Create position sets
        main_position_keys = set()
        mirror_position_keys = set()
        
        # Process main positions
        for pos in main_positions:
            if float(pos.get('size', 0)) > 0:
                key = f"{pos['symbol']}_{pos['side']}_main"
                main_position_keys.add(key)
        
        # Process mirror positions
        for pos in mirror_positions:
            if float(pos.get('size', 0)) > 0:
                key = f"{pos['symbol']}_{pos['side']}_mirror"
                mirror_position_keys.add(key)
        
        all_position_keys = main_position_keys | mirror_position_keys
        monitor_keys = set(monitors.keys())
        
        # Find discrepancies
        missing_monitors = all_position_keys - monitor_keys
        orphaned_monitors = monitor_keys - all_position_keys
        
        # Detailed analysis
        analysis = {
            'total_positions': len(all_position_keys),
            'main_positions': len(main_position_keys),
            'mirror_positions': len(mirror_position_keys),
            'total_monitors': len(monitors),
            'missing_monitors': list(missing_monitors),
            'orphaned_monitors': list(orphaned_monitors),
            'main_position_list': list(main_position_keys),
            'mirror_position_list': list(mirror_position_keys),
            'monitor_list': list(monitor_keys),
            'positions_by_symbol': {},
            'missing_details': []
        }
        
        # Get detailed info for missing monitors
        all_positions = [(p, 'main') for p in main_positions] + [(p, 'mirror') for p in mirror_positions]
        
        for pos, account in all_positions:
            if float(pos.get('size', 0)) > 0:
                monitor_key = f"{pos['symbol']}_{pos['side']}_{account}"
                
                # Store position info by symbol
                symbol = pos['symbol']
                if symbol not in analysis['positions_by_symbol']:
                    analysis['positions_by_symbol'][symbol] = {}
                analysis['positions_by_symbol'][symbol][account] = {
                    'side': pos['side'],
                    'size': pos['size'],
                    'avgPrice': pos.get('avgPrice', 0),
                    'monitor_exists': monitor_key in monitors
                }
                
                # If monitor is missing, add to detailed list
                if monitor_key in missing_monitors:
                    analysis['missing_details'].append({
                        'monitor_key': monitor_key,
                        'symbol': pos['symbol'],
                        'side': pos['side'],
                        'account': account,
                        'size': pos['size'],
                        'avgPrice': pos.get('avgPrice', 0),
                        'markPrice': pos.get('markPrice', 0),
                        'unrealisedPnl': pos.get('unrealisedPnl', 0)
                    })
        
        return analysis
        
    except Exception as e:
        logger.error(f"❌ Error analyzing monitors: {e}")
        import traceback
        traceback.print_exc()
        return {}

async def main():
    """Main analysis function"""
    logger.info("🔍 Starting Missing Monitor Analysis")
    logger.info("=" * 80)
    
    try:
        # Get all positions
        main_positions, mirror_positions = await get_all_active_positions()
        
        logger.info(f"📊 Main account: {len(main_positions)} total positions")
        logger.info(f"📊 Mirror account: {len(mirror_positions)} total positions")
        
        # Filter active positions only
        active_main = [p for p in main_positions if float(p.get('size', 0)) > 0]
        active_mirror = [p for p in mirror_positions if float(p.get('size', 0)) > 0]
        
        logger.info(f"📊 Main account: {len(active_main)} active positions")
        logger.info(f"📊 Mirror account: {len(active_mirror)} active positions")
        
        # Analyze discrepancies
        analysis = analyze_monitors_vs_positions(active_main, active_mirror)
        
        # Print results
        logger.info("\n" + "=" * 80)
        logger.info("📊 ANALYSIS RESULTS:")
        logger.info(f"   Total Positions: {analysis.get('total_positions', 0)}")
        logger.info(f"   Main Positions: {analysis.get('main_positions', 0)}")
        logger.info(f"   Mirror Positions: {analysis.get('mirror_positions', 0)}")
        logger.info(f"   Total Monitors in Pickle: {analysis.get('total_monitors', 0)}")
        
        missing = analysis.get('missing_monitors', [])
        if missing:
            logger.warning(f"\n⚠️ MISSING MONITORS: {len(missing)}")
            for monitor_key in missing:
                logger.warning(f"   - {monitor_key}")
        
        orphaned = analysis.get('orphaned_monitors', [])
        if orphaned:
            logger.warning(f"\n⚠️ ORPHANED MONITORS (no position): {len(orphaned)}")
            for monitor_key in orphaned:
                logger.warning(f"   - {monitor_key}")
        
        # Show detailed missing monitor info
        if analysis.get('missing_details'):
            logger.info("\n📋 MISSING MONITOR DETAILS:")
            for detail in analysis['missing_details']:
                logger.info(f"\n   Monitor Key: {detail['monitor_key']}")
                logger.info(f"   Symbol: {detail['symbol']}")
                logger.info(f"   Side: {detail['side']}")
                logger.info(f"   Account: {detail['account']}")
                logger.info(f"   Size: {detail['size']}")
                logger.info(f"   Avg Price: {detail['avgPrice']}")
                logger.info(f"   Unrealised PnL: ${detail['unrealisedPnl']}")
        
        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 SUMMARY:")
        logger.info(f"   Expected monitors: {analysis.get('total_positions', 0)}")
        logger.info(f"   Actual monitors: {analysis.get('total_monitors', 0)}")
        logger.info(f"   Missing monitors: {len(missing)}")
        logger.info(f"   Orphaned monitors: {len(orphaned)}")
        
        if len(missing) == 0 and len(orphaned) == 0:
            logger.info("\n✅ All positions have monitors! No discrepancies found.")
        else:
            logger.warning(f"\n⚠️ Found {len(missing)} missing monitors and {len(orphaned)} orphaned monitors")
        
        # Save analysis to file for next phase
        import json
        with open('monitor_analysis.json', 'w') as f:
            json.dump(analysis, f, indent=2)
        logger.info("\n💾 Analysis saved to monitor_analysis.json")
        
        return analysis
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    asyncio.run(main())