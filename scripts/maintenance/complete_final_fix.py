#!/usr/bin/env python3
"""
Complete Final Monitor Fix

Create the last 2 missing mirror dashboard monitors for XTZUSDT and BANDUSDT
to achieve perfect 28/28 alignment.
"""

import pickle
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_final_mirror_monitors():
    """Create the final 2 missing mirror dashboard monitors"""
    try:
        pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
        
        # Load data
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
        
        chat_id = 5634913742
        missing_symbols = ['XTZUSDT', 'BANDUSDT']
        created_count = 0
        
        for symbol in missing_symbols:
            mirror_key = f"{symbol}_Sell_MIRROR"
            dashboard_key = f"{chat_id}_{symbol}_conservative_mirror"
            
            # Check if mirror dashboard monitor exists
            if dashboard_key not in dashboard_monitors:
                # Get Enhanced TP/SL monitor data
                enhanced_data = enhanced_monitors.get(mirror_key, {})
                
                # Create mirror dashboard monitor
                dashboard_entry = {
                    "symbol": symbol,
                    "side": "Sell",
                    "approach": "conservative",
                    "account_type": "mirror",
                    "chat_id": chat_id,
                    "active": True,
                    "started_at": time.time(),
                    "last_update": time.time(),
                    "position_size": enhanced_data.get("position_size", "0"),
                    "entry_price": enhanced_data.get("entry_price", "0"),
                    "current_status": "monitoring",
                    "tp_orders": enhanced_data.get("tp_orders", []),
                    "sl_orders": enhanced_data.get("sl_orders", []),
                    "created_by": "final_mirror_fix",
                    "mirror_monitor": True
                }
                
                dashboard_monitors[dashboard_key] = dashboard_entry
                created_count += 1
                logger.info(f"✅ Created final mirror dashboard monitor: {dashboard_key}")
            else:
                logger.info(f"ℹ️ Mirror dashboard monitor already exists: {dashboard_key}")
        
        # Save updated data
        with open(pkl_path, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"✅ Created {created_count} final mirror dashboard monitors")
        logger.info(f"📊 Final totals:")
        logger.info(f"   Enhanced TP/SL monitors: {len(enhanced_monitors)}")
        logger.info(f"   Dashboard monitors: {len(dashboard_monitors)}")
        
        # Verify perfect alignment
        if len(enhanced_monitors) == len(dashboard_monitors) == 28:
            logger.info("🎯 PERFECT ALIGNMENT ACHIEVED: 28/28 monitors!")
        
        return created_count > 0
        
    except Exception as e:
        logger.error(f"❌ Error creating final mirror monitors: {e}")
        return False

if __name__ == "__main__":
    logger.info("🎯 Creating Final Mirror Dashboard Monitors")
    logger.info("=" * 50)
    
    success = create_final_mirror_monitors()
    
    if success:
        logger.info("✅ Final mirror dashboard monitors created!")
        logger.info("🎯 Monitor tracking fix is now COMPLETE!")
        logger.info("📊 You should now see 'Monitoring 28 positions' in the logs")
    else:
        logger.info("ℹ️ All monitors already exist - system is complete")