#!/usr/bin/env python3
"""
Check alert status for all positions and monitors
"""
import asyncio
import logging
import pickle
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def check_alert_status():
    """Check alert system status and configuration"""
    try:
        # Import required modules
        from clients.bybit_helpers import get_all_positions
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from config.settings import ENHANCED_TP_SL_ALERTS_ONLY, ALERT_SETTINGS
        
        logger.info("🔍 Checking Alert System Status...")
        
        # Check alert configuration
        logger.info("\n📋 Alert Configuration:")
        logger.info(f"ENHANCED_TP_SL_ALERTS_ONLY: {ENHANCED_TP_SL_ALERTS_ONLY}")
        logger.info(f"ALERT_SETTINGS: {ALERT_SETTINGS}")
        
        # Get current positions
        positions = await get_all_positions()
        logger.info(f"\n📊 Open Positions: {len(positions)}")
        
        for position in positions:
            symbol = position.get('symbol', 'UNKNOWN')
            side = position.get('side', 'UNKNOWN')
            size = Decimal(str(position.get('size', '0')))
            avg_price = Decimal(str(position.get('avgPrice', '0')))
            logger.info(f"  - {symbol} {side}: Size={size}, Entry=${avg_price}")
        
        # Check enhanced TP/SL monitors
        logger.info(f"\n🎯 Enhanced TP/SL Monitors: {len(enhanced_tp_sl_manager.position_monitors)}")
        
        for monitor_key, monitor_data in enhanced_tp_sl_manager.position_monitors.items():
            symbol = monitor_data.get('symbol', 'UNKNOWN')
            side = monitor_data.get('side', 'UNKNOWN')
            chat_id = monitor_data.get('chat_id', 'NO_CHAT_ID')
            phase = monitor_data.get('phase', 'UNKNOWN')
            approach = monitor_data.get('approach', 'UNKNOWN')
            
            # Check if monitor has proper alert capability
            has_chat_id = chat_id != 'NO_CHAT_ID' and chat_id is not None
            
            logger.info(f"\n  Monitor: {symbol} {side}")
            logger.info(f"    - Chat ID: {chat_id} {'✅' if has_chat_id else '❌ MISSING'}")
            logger.info(f"    - Phase: {phase}")
            logger.info(f"    - Approach: {approach}")
            
            # Check TP orders
            tp_orders = monitor_data.get('tp_orders', [])
            logger.info(f"    - TP Orders: {len(tp_orders)}")
            for i, tp in enumerate(tp_orders):
                logger.info(f"      • TP{i+1}: ${tp.get('price', 0)}, Qty={tp.get('quantity', 0)}")
            
            # Check SL order
            sl_order = monitor_data.get('sl_order', {})
            if sl_order:
                logger.info(f"    - SL Order: ${sl_order.get('price', 0)}, Qty={sl_order.get('quantity', 0)}")
        
        # Check dashboard monitors
        logger.info("\n📊 Checking Dashboard Monitors...")
        try:
            pkl_path = '/Users/lualakol/bybit-telegram-bot/bybit_bot_dashboard_v4.1_enhanced.pkl'
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            
            dashboard_monitors = data.get('bot_data', {}).get('monitor_tasks', {})
            logger.info(f"Dashboard Monitors: {len(dashboard_monitors)}")
            
            # Group by symbol for easier viewing
            by_symbol = {}
            for key, monitor in dashboard_monitors.items():
                symbol = monitor.get('symbol', 'UNKNOWN')
                if symbol not in by_symbol:
                    by_symbol[symbol] = []
                by_symbol[symbol].append(monitor)
            
            for symbol, monitors in by_symbol.items():
                logger.info(f"  - {symbol}: {len(monitors)} monitor(s)")
        
        except Exception as e:
            logger.error(f"Could not load dashboard monitors: {e}")
        
        # Check for alert issues
        logger.info("\n🚨 Potential Alert Issues:")
        
        issues_found = False
        
        # Check for monitors without chat IDs
        for monitor_key, monitor_data in enhanced_tp_sl_manager.position_monitors.items():
            chat_id = monitor_data.get('chat_id')
            if not chat_id or chat_id == 'NO_CHAT_ID':
                symbol = monitor_data.get('symbol', 'UNKNOWN')
                side = monitor_data.get('side', 'UNKNOWN')
                logger.warning(f"  ⚠️ Monitor {symbol} {side} has no valid chat ID!")
                issues_found = True
        
        # Check for positions without monitors
        for position in positions:
            symbol = position.get('symbol', 'UNKNOWN')
            side = position.get('side', 'UNKNOWN')
            monitor_key = f"{symbol}_{side}"
            
            if monitor_key not in enhanced_tp_sl_manager.position_monitors:
                logger.warning(f"  ⚠️ Position {symbol} {side} has no enhanced TP/SL monitor!")
                issues_found = True
        
        if not issues_found:
            logger.info("  ✅ No issues found - all positions have monitors with chat IDs")
        
        logger.info("\n✅ Alert status check completed!")
        
    except Exception as e:
        logger.error(f"❌ Error checking alert status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_alert_status())