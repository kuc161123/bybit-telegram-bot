#!/usr/bin/env python3
"""
Verify current monitor state and fix any remaining issues
"""

import pickle
import logging
from decimal import Decimal
import json

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_monitors():
    """Check current monitor state"""
    try:
        # Load pickle file
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data['bot_data'].get('enhanced_tp_sl_monitors', {})
        
        logger.info(f"\n=== CURRENT MONITOR STATE ===")
        logger.info(f"Total monitors: {len(monitors)}")
        
        issues_found = []
        
        # Check each monitor
        for key, monitor in monitors.items():
            symbol = monitor['symbol']
            side = monitor['side']
            position_size = monitor.get('position_size', 0)
            remaining_size = monitor.get('remaining_size', 0)
            account_type = monitor.get('account_type', 'unknown')
            
            logger.info(f"\n{key}:")
            logger.info(f"  Symbol: {symbol} {side}")
            logger.info(f"  Account: {account_type}")
            logger.info(f"  Position Size: {position_size}")
            logger.info(f"  Remaining Size: {remaining_size}")
            
            # Check for potential issues
            if key.endswith('_mirror'):
                # Check if mirror has suspiciously large sizes
                if symbol == 'ICPUSDT' and position_size > 50:
                    issues_found.append(f"{key}: position_size {position_size} seems too large for mirror")
                elif symbol == 'IDUSDT' and position_size > 500:
                    issues_found.append(f"{key}: position_size {position_size} seems too large for mirror")
                elif symbol == 'JUPUSDT' and position_size > 2000:
                    issues_found.append(f"{key}: position_size {position_size} seems too large for mirror")
                    
            # Check for mismatched position/remaining sizes
            if position_size != remaining_size:
                issues_found.append(f"{key}: position_size ({position_size}) != remaining_size ({remaining_size})")
        
        if issues_found:
            logger.warning(f"\n⚠️ ISSUES FOUND:")
            for issue in issues_found:
                logger.warning(f"  - {issue}")
        else:
            logger.info(f"\n✅ All monitors look correct")
            
        return monitors, issues_found
        
    except Exception as e:
        logger.error(f"Error verifying monitors: {e}")
        return None, []

def main():
    """Main verification"""
    monitors, issues = verify_monitors()
    
    # Save state to JSON for analysis
    if monitors:
        state = {}
        for key, monitor in monitors.items():
            state[key] = {
                'symbol': monitor.get('symbol'),
                'side': monitor.get('side'),
                'position_size': float(monitor.get('position_size', 0)),
                'remaining_size': float(monitor.get('remaining_size', 0)),
                'account_type': monitor.get('account_type', 'unknown')
            }
        
        with open('current_monitor_state.json', 'w') as f:
            json.dump(state, f, indent=2)
        logger.info(f"\n📄 Saved current state to current_monitor_state.json")

if __name__ == "__main__":
    main()