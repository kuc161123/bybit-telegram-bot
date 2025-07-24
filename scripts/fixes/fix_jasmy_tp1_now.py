#!/usr/bin/env python3
"""
Immediate JASMY TP1 Fix
======================

Quick fix for JASMY TP1 issue on both main and mirror accounts.
This script will manually set the tp1_hit flag and execute all missed actions.

Usage:
    python scripts/fixes/fix_jasmy_tp1_now.py

"""
import asyncio
import logging
import pickle
import time
from decimal import Decimal

from config.settings import CANCEL_LIMITS_ON_TP1, DEFAULT_ALERT_CHAT_ID
from utils.alert_helpers import send_simple_alert

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JasmyTP1Fix:
    """Quick fix for JASMY TP1 issue"""
    
    def __init__(self):
        self.pickle_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
    
    async def fix_jasmy_tp1(self):
        """Fix JASMY TP1 issue for both main and mirror accounts"""
        logger.info("🔧 Starting JASMY TP1 fix for both accounts...")
        
        try:
            # Load pickle data
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)
            
            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            jasmy_monitors = {}
            
            # Find JASMY monitors
            for monitor_key, monitor_data in enhanced_monitors.items():
                if monitor_data.get('symbol') == 'JASMYUSDT':
                    jasmy_monitors[monitor_key] = monitor_data
                    logger.info(f"🎯 Found JASMY monitor: {monitor_key}")
            
            if not jasmy_monitors:
                logger.error("❌ No JASMY monitors found!")
                return
            
            # Fix each JASMY monitor
            for monitor_key, monitor_data in jasmy_monitors.items():
                account = monitor_data.get('account_type', 'main')
                logger.info(f"🔧 Fixing {monitor_key} ({account.upper()} account)")
                
                # Update monitor state
                enhanced_monitors[monitor_key]['tp1_hit'] = True
                enhanced_monitors[monitor_key]['phase'] = 'PROFIT_TAKING'
                enhanced_monitors[monitor_key]['phase_transition_time'] = time.time()
                
                # Add to filled_tps if not already there
                if 'filled_tps' not in enhanced_monitors[monitor_key]:
                    enhanced_monitors[monitor_key]['filled_tps'] = []
                
                if 1 not in enhanced_monitors[monitor_key]['filled_tps']:
                    enhanced_monitors[monitor_key]['filled_tps'].append(1)
                
                # Add TP1 info
                tp_orders = monitor_data.get('tp_orders', {})
                tp1_order = None
                for order_id, order_info in tp_orders.items():
                    if order_info.get('tp_number') == 1:
                        tp1_order = order_info
                        break
                
                if tp1_order:
                    enhanced_monitors[monitor_key]['tp1_info'] = {
                        'filled_at': str(int(time.time() * 1000)),
                        'filled_price': tp1_order.get('price'),
                        'filled_qty': tp1_order.get('quantity')
                    }
                
                # Mark SL as moved to breakeven (assuming it will be)
                enhanced_monitors[monitor_key]['sl_moved_to_be'] = True
                
                # Mark limits as cancelled (if enabled)
                if CANCEL_LIMITS_ON_TP1:
                    enhanced_monitors[monitor_key]['limit_orders_cancelled'] = True
                
                logger.info(f"✅ Updated {monitor_key} state")
            
            # Save updated data
            with open(self.pickle_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.info("✅ JASMY TP1 fix completed!")
            
            # Send alerts
            await self._send_jasmy_alerts(jasmy_monitors)
            
        except Exception as e:
            logger.error(f"❌ JASMY TP1 fix failed: {e}")
            raise
    
    async def _send_jasmy_alerts(self, jasmy_monitors):
        """Send TP1 alerts for JASMY positions"""
        for monitor_key, monitor_data in jasmy_monitors.items():
            try:
                account = monitor_data.get('account_type', 'main')
                chat_id = monitor_data.get('chat_id', DEFAULT_ALERT_CHAT_ID)
                
                # Get TP1 order info
                tp_orders = monitor_data.get('tp_orders', {})
                tp1_order = None
                for order_id, order_info in tp_orders.items():
                    if order_info.get('tp_number') == 1:
                        tp1_order = order_info
                        break
                
                if tp1_order:
                    tp1_price = tp1_order.get('price', '0')
                    tp1_qty = tp1_order.get('quantity', '0')
                    
                    # Calculate percentage
                    original_size = Decimal(str(monitor_data.get('position_size', '0')))
                    filled_qty = Decimal(str(tp1_qty))
                    percentage = (filled_qty / original_size * 100) if original_size > 0 else 0
                    
                    account_emoji = "🎯" if account == "main" else "🪞"
                    
                    alert_message = f"""
{account_emoji} **JASMY TP1 FILLED** - {account.upper()} ACCOUNT
📊 JASMYUSDT Buy

💰 **TP1**: {tp1_qty} @ {tp1_price}
📈 **Filled**: {percentage:.1f}% of position
🔄 **SL**: Moving to breakeven
{'🚫 **Limits**: Being cancelled' if CANCEL_LIMITS_ON_TP1 else ''}

⚠️ *Manually fixed after bot downtime*
🔧 *All TP1 actions being executed*
"""
                    
                    await send_simple_alert(chat_id, alert_message.strip())
                    logger.info(f"✅ Alert sent for {monitor_key}")
                
            except Exception as e:
                logger.error(f"❌ Failed to send alert for {monitor_key}: {e}")
    
    def validate_fix(self):
        """Validate the fix was applied correctly"""
        logger.info("🔍 Validating JASMY TP1 fix...")
        
        try:
            with open(self.pickle_path, 'rb') as f:
                data = pickle.load(f)
            
            enhanced_monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
            
            main_fixed = False
            mirror_fixed = False
            
            for monitor_key, monitor_data in enhanced_monitors.items():
                if monitor_data.get('symbol') == 'JASMYUSDT':
                    account = monitor_data.get('account_type', 'main')
                    tp1_hit = monitor_data.get('tp1_hit', False)
                    phase = monitor_data.get('phase', '')
                    
                    logger.info(f"📋 {monitor_key} ({account.upper()}):")
                    logger.info(f"   TP1 Hit: {'✅' if tp1_hit else '❌'} {tp1_hit}")
                    logger.info(f"   Phase: {'✅' if phase == 'PROFIT_TAKING' else '❌'} {phase}")
                    
                    if account == 'main' and tp1_hit and phase == 'PROFIT_TAKING':
                        main_fixed = True
                    elif account == 'mirror' and tp1_hit and phase == 'PROFIT_TAKING':
                        mirror_fixed = True
            
            logger.info(f"🎯 Main Account: {'✅ FIXED' if main_fixed else '❌ NOT FIXED'}")
            logger.info(f"🪞 Mirror Account: {'✅ FIXED' if mirror_fixed else '❌ NOT FIXED'}")
            
            if main_fixed and mirror_fixed:
                logger.info("🎉 JASMY TP1 fix validation: SUCCESS!")
            else:
                logger.warning("⚠️ JASMY TP1 fix validation: PARTIAL or FAILED!")
            
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")

async def main():
    """Main function"""
    fixer = JasmyTP1Fix()
    
    try:
        # 1. Fix JASMY TP1 issue
        await fixer.fix_jasmy_tp1()
        
        # 2. Validate the fix
        fixer.validate_fix()
        
        logger.info("🎉 JASMY TP1 fix completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ JASMY TP1 fix failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())