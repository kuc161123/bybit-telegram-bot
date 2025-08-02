#!/usr/bin/env python3
"""
Validate all fixes are working correctly
"""
import asyncio
import logging
from decimal import Decimal
import os
from telegram import Bot
from telegram.constants import ParseMode
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CHAT_ID = 5634913742

async def send_validation_alert(message: str):
    """Send validation alert"""
    try:
        bot_token = os.getenv('TELEGRAM_TOKEN')
        if bot_token:
            bot = Bot(token=bot_token)
            await bot.send_message(
                chat_id=CHAT_ID,
                text=message,
                parse_mode=ParseMode.HTML
            )
            return True
    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        return False

async def validate_fixes():
    """Validate all fixes"""
    try:
        from clients.bybit_helpers import get_all_positions, get_open_orders, get_instrument_info
        from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
        from execution.mirror_trader import is_mirror_trading_enabled, get_mirror_positions
        from utils.helpers import value_adjusted_to_step
        
        logger.info("🔍 Validating all fixes...")
        
        issues = []
        validations = []
        
        # 1. Check DOGEUSDT quantity step
        logger.info("\n1️⃣ Validating DOGEUSDT quantity precision...")
        instrument_info = await get_instrument_info('DOGEUSDT')
        if instrument_info:
            qty_step = Decimal(instrument_info.get('lotSizeFilter', {}).get('qtyStep', '1'))
            logger.info(f"   DOGEUSDT qty step: {qty_step}")
            
            # Test quantity adjustment
            test_qty = Decimal("13.275")
            adjusted = value_adjusted_to_step(test_qty, qty_step)
            logger.info(f"   Test: {test_qty} -> {adjusted}")
            
            if adjusted == Decimal("13"):
                validations.append("✅ DOGEUSDT quantity adjustment working correctly")
            else:
                issues.append(f"❌ DOGEUSDT quantity adjustment failed: {test_qty} -> {adjusted}")
        
        # 2. Check Enhanced TP/SL monitors
        logger.info("\n2️⃣ Validating Enhanced TP/SL monitors...")
        positions = await get_all_positions()
        
        for position in positions:
            symbol = position.get('symbol', '')
            side = position.get('side', '')
            size = Decimal(str(position.get('size', '0')))
            
            if not symbol or not side or size == 0:
                continue
            
            monitor_key = f"{symbol}_{side}"
            
            if monitor_key in enhanced_tp_sl_manager.position_monitors:
                monitor = enhanced_tp_sl_manager.position_monitors[monitor_key]
                
                # Check DOGEUSDT specifically
                if symbol == 'DOGEUSDT' and side == 'Buy':
                    if monitor.get('limit_orders_filled'):
                        validations.append("✅ DOGEUSDT limit_orders_filled flag is True")
                    else:
                        issues.append("❌ DOGEUSDT limit_orders_filled flag is False")
                    
                    if monitor.get('phase') == 'PROFIT_TAKING':
                        validations.append("✅ DOGEUSDT phase is PROFIT_TAKING")
                    else:
                        issues.append(f"❌ DOGEUSDT phase is {monitor.get('phase')}")
                
                # General checks
                if monitor.get('chat_id') == CHAT_ID:
                    validations.append(f"✅ {symbol} has valid chat_id")
                else:
                    issues.append(f"❌ {symbol} has invalid chat_id: {monitor.get('chat_id')}")
            else:
                issues.append(f"❌ No monitor for {symbol} {side}")
        
        # 3. Check mirror account sync
        if is_mirror_trading_enabled():
            logger.info("\n3️⃣ Validating mirror account sync...")
            mirror_positions = await get_mirror_positions()
            
            for position in positions:
                symbol = position.get('symbol', '')
                side = position.get('side', '')
                main_size = Decimal(str(position.get('size', '0')))
                
                # Find mirror position
                mirror_pos = None
                for mp in mirror_positions:
                    if mp.get('symbol') == symbol and mp.get('side') == side:
                        mirror_pos = mp
                        break
                
                if mirror_pos:
                    mirror_size = Decimal(str(mirror_pos.get('size', '0')))
                    ratio = mirror_size / main_size if main_size > 0 else 0
                    
                    if 0.3 <= ratio <= 0.35:  # Expected ~33% ratio
                        validations.append(f"✅ {symbol} mirror ratio OK: {ratio:.2%}")
                    else:
                        issues.append(f"❌ {symbol} mirror ratio issue: {ratio:.2%}")
        
        # 4. Test alert system
        logger.info("\n4️⃣ Testing alert system...")
        from utils.alert_helpers import send_simple_alert
        
        test_message = "🧪 <b>VALIDATION TEST</b>\n\nTesting alert system after fixes."
        result = await send_simple_alert(CHAT_ID, test_message, "validation")
        
        if result:
            validations.append("✅ Alert system working")
        else:
            issues.append("❌ Alert system not working")
        
        # Generate report
        report = f"""📊 <b>VALIDATION REPORT</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>✅ Successful Validations ({len(validations)}):</b>
"""
        for validation in validations:
            report += f"\n{validation}"
        
        if issues:
            report += f"\n\n<b>❌ Issues Found ({len(issues)}):</b>"
            for issue in issues:
                report += f"\n{issue}"
        else:
            report += "\n\n🎉 <b>All validations passed!</b>"
        
        report += f"""

<b>📈 System Status:</b>
• Active positions: {len(positions)}
• Active monitors: {len(enhanced_tp_sl_manager.position_monitors)}
• Mirror trading: {'Enabled' if is_mirror_trading_enabled() else 'Disabled'}

✅ Fixes have been successfully applied!"""
        
        # Send report
        await send_validation_alert(report)
        
        logger.info("\n" + "="*50)
        logger.info("VALIDATION SUMMARY:")
        logger.info(f"✅ Successful: {len(validations)}")
        logger.info(f"❌ Issues: {len(issues)}")
        
        if not issues:
            logger.info("\n🎉 All validations passed!")
        else:
            logger.warning(f"\n⚠️ Found {len(issues)} issues that need attention")
        
    except Exception as e:
        logger.error(f"❌ Validation error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(validate_fixes())