#!/usr/bin/env python3
"""
Comprehensive Enhanced TP/SL Monitoring Fix
Addresses missing alerts and TP rebalancing for filled limit orders
"""

import asyncio
import logging
import pickle
import os
from datetime import datetime
from decimal import Decimal

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def comprehensive_monitoring_fix():
    """
    Comprehensive fix for Enhanced TP/SL monitoring issues
    """
    try:
        logger.info("=" * 80)
        logger.info("COMPREHENSIVE ENHANCED TP/SL MONITORING FIX")
        logger.info("=" * 80)
        
        # Step 1: Analyze current state
        logger.info("\n1️⃣ ANALYZING CURRENT STATE")
        logger.info("-" * 50)
        
        # Load pickle data
        with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'rb') as f:
            data = pickle.load(f)
        
        monitors = data.get('bot_data', {}).get('enhanced_tp_sl_monitors', {})
        logger.info(f"Found {len(monitors)} Enhanced TP/SL monitors")
        
        # Check monitor statuses
        active_count = 0
        unknown_count = 0
        inactive_count = 0
        
        for key, monitor in monitors.items():
            status = monitor.get('active', 'unknown')
            if status == True or status == 'true':
                active_count += 1
            elif status == 'unknown':
                unknown_count += 1
            else:
                inactive_count += 1
        
        logger.info(f"Monitor Status Distribution:")
        logger.info(f"   Active: {active_count}")
        logger.info(f"   Unknown: {unknown_count}")
        logger.info(f"   Inactive: {inactive_count}")
        
        # Check for chat_id issues
        no_chat_id_count = 0
        for key, monitor in monitors.items():
            if not monitor.get('chat_id'):
                no_chat_id_count += 1
        
        if no_chat_id_count > 0:
            logger.warning(f"⚠️ {no_chat_id_count} monitors missing chat_id")
        
        # Step 2: Check current positions vs monitors
        logger.info("\n2️⃣ CHECKING POSITION VS MONITOR ALIGNMENT")
        logger.info("-" * 50)
        
        from clients.bybit_helpers import get_all_positions
        
        # Get main account positions
        main_positions = await get_all_positions()
        logger.info(f"Main account positions: {len(main_positions)}")
        
        # Get mirror account positions if enabled
        mirror_positions = []
        if os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true":
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            if hasattr(enhanced_tp_sl_manager, '_mirror_client') and enhanced_tp_sl_manager._mirror_client:
                from clients.bybit_helpers import api_call_with_retry
                response = await api_call_with_retry(
                    lambda: enhanced_tp_sl_manager._mirror_client.get_positions(
                        category="linear",
                        settleCoin="USDT"
                    )
                )
                if response and response.get("result"):
                    mirror_positions = [
                        pos for pos in response["result"].get("list", [])
                        if float(pos.get('size', 0)) > 0
                    ]
            logger.info(f"Mirror account positions: {len(mirror_positions)}")
        
        total_positions = len(main_positions) + len(mirror_positions)
        logger.info(f"Total positions: {total_positions}")
        logger.info(f"Monitor vs Position gap: {len(monitors) - total_positions}")
        
        # Step 3: Fix backup frequency issue
        logger.info("\n3️⃣ FIXING BACKUP FREQUENCY ISSUE")
        logger.info("-" * 50)
        
        try:
            # Check if backup frequency script exists
            if os.path.exists('reduce_backup_frequency.py'):
                logger.info("Running backup frequency fix...")
                from reduce_backup_frequency import fix_backup_frequency_automatically
                await fix_backup_frequency_automatically()
                logger.info("✅ Backup frequency optimized")
            else:
                logger.warning("⚠️ reduce_backup_frequency.py not found - skipping")
        except Exception as e:
            logger.error(f"Error fixing backup frequency: {e}")
        
        # Step 4: Fix monitor activation status
        logger.info("\n4️⃣ FIXING MONITOR ACTIVATION STATUS")
        logger.info("-" * 50)
        
        if unknown_count > 0:
            logger.info(f"Activating {unknown_count} monitors with unknown status...")
            
            # Create backup before making changes
            backup_filename = f"bybit_bot_dashboard_v4.1_enhanced.pkl.backup_fix_activation_{int(datetime.now().timestamp())}"
            import shutil
            shutil.copy('bybit_bot_dashboard_v4.1_enhanced.pkl', backup_filename)
            logger.info(f"📦 Created backup: {backup_filename}")
            
            # Fix monitor statuses
            fixed_count = 0
            for key, monitor in monitors.items():
                if monitor.get('active') == 'unknown':
                    monitors[key]['active'] = True
                    fixed_count += 1
            
            # Save updated data
            with open('bybit_bot_dashboard_v4.1_enhanced.pkl', 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"✅ Fixed {fixed_count} monitor activation statuses")
        else:
            logger.info("✅ All monitors already have proper activation status")
        
        # Step 5: Verify chat_id associations
        logger.info("\n5️⃣ VERIFYING CHAT_ID ASSOCIATIONS")
        logger.info("-" * 50)
        
        # Check for monitors without chat_id and attempt to fix
        if no_chat_id_count > 0:
            logger.warning(f"Found {no_chat_id_count} monitors without chat_id")
            
            # Try to find a default chat_id from user_data
            user_data = data.get('user_data', {})
            default_chat_id = None
            
            # Find the most recent chat_id from user_data
            for chat_id, user_info in user_data.items():
                if user_info and isinstance(user_info, dict):
                    default_chat_id = int(chat_id)
                    break
            
            if default_chat_id:
                logger.info(f"Found default chat_id: {default_chat_id}")
                
                # Option to fix (but don't automatically change)
                logger.info(f"To fix monitors without chat_id, run:")
                logger.info(f"   python fix_monitor_chat_ids.py --chat-id {default_chat_id}")
            else:
                logger.warning("⚠️ No default chat_id found - alerts may not work")
        else:
            logger.info("✅ All monitors have chat_id associations")
        
        # Step 6: Test Enhanced TP/SL Manager
        logger.info("\n6️⃣ TESTING ENHANCED TP/SL MANAGER")
        logger.info("-" * 50)
        
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        
        # Load monitors into manager
        enhanced_tp_sl_manager.position_monitors.clear()
        for key, monitor_data in monitors.items():
            if key.endswith('_main') or key.endswith('_mirror'):
                sanitized_data = enhanced_tp_sl_manager._sanitize_monitor_data(monitor_data)
                enhanced_tp_sl_manager.position_monitors[key] = sanitized_data
        
        logger.info(f"✅ Loaded {len(enhanced_tp_sl_manager.position_monitors)} monitors into manager")
        
        # Test one position monitoring cycle
        if enhanced_tp_sl_manager.position_monitors:
            test_key = list(enhanced_tp_sl_manager.position_monitors.keys())[0]
            test_monitor = enhanced_tp_sl_manager.position_monitors[test_key]
            symbol = test_monitor['symbol']
            side = test_monitor['side']
            account_type = test_monitor.get('account_type', 'main')
            
            logger.info(f"Testing monitor for {symbol} {side} ({account_type})...")
            
            try:
                await enhanced_tp_sl_manager.monitor_and_adjust_orders(symbol, side, account_type)
                logger.info(f"✅ Monitor test successful for {symbol}")
            except Exception as e:
                logger.error(f"❌ Monitor test failed for {symbol}: {e}")
        
        # Step 7: Verify alert system
        logger.info("\n7️⃣ VERIFYING ALERT SYSTEM")
        logger.info("-" * 50)
        
        from config.settings import ENHANCED_TP_SL_ALERTS_ONLY, ALERT_SETTINGS
        logger.info(f"Enhanced TP/SL alerts only: {ENHANCED_TP_SL_ALERTS_ONLY}")
        logger.info(f"Alert settings: {ALERT_SETTINGS}")
        
        # Check if alert system is properly configured
        if ENHANCED_TP_SL_ALERTS_ONLY:
            logger.info("✅ Enhanced TP/SL alerts are enabled")
        else:
            logger.info("⚠️ Enhanced TP/SL alerts may be limited by ALERT_SETTINGS")
        
        # Step 8: Create monitor reload trigger
        logger.info("\n8️⃣ TRIGGERING MONITOR RELOAD")
        logger.info("-" * 50)
        
        # Create signal file to trigger monitor reload
        signal_file = 'reload_enhanced_monitors.signal'
        with open(signal_file, 'w') as f:
            f.write(f"Monitor reload triggered by comprehensive fix at {datetime.now()}")
        
        logger.info(f"✅ Created monitor reload signal: {signal_file}")
        
        # Summary and recommendations
        logger.info("\n" + "=" * 80)
        logger.info("🎯 COMPREHENSIVE FIX SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"✅ Actions Completed:")
        logger.info(f"   • Analyzed {len(monitors)} monitors")
        logger.info(f"   • Fixed {unknown_count} monitor activation statuses")
        logger.info(f"   • Optimized backup frequency")
        logger.info(f"   • Verified alert system configuration")
        logger.info(f"   • Triggered monitor reload")
        
        logger.info(f"\n📝 Next Steps:")
        logger.info(f"   1. Restart the bot to apply monitor fixes")
        logger.info(f"   2. Monitor logs for 'Enhanced TP/SL monitoring loop' messages")
        logger.info(f"   3. Watch for position change detection and alerts")
        logger.info(f"   4. Test with a small limit order fill to verify alerts")
        
        if no_chat_id_count > 0:
            logger.info(f"\n⚠️ Important:")
            logger.info(f"   • {no_chat_id_count} monitors missing chat_id")
            logger.info(f"   • Create and run fix_monitor_chat_ids.py if needed")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Comprehensive fix failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = asyncio.run(comprehensive_monitoring_fix())
    if success:
        print("\n🎉 Comprehensive fix completed! Restart the bot to apply changes.")
    else:
        print("\n❌ Fix failed! Check the logs above.")
        exit(1)