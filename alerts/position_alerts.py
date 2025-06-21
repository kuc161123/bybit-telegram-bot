#!/usr/bin/env python3
"""
Position P&L monitoring and alerts
"""
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal

from clients.bybit_helpers import get_all_positions
from .alert_types import Alert, AlertType, ALERT_CONFIGS

logger = logging.getLogger(__name__)

class PositionAlertChecker:
    """Checks position-based alerts"""
    
    async def check_alerts(self, alerts: List[Alert]) -> List[Dict]:
        """Check position alerts and return triggered ones"""
        triggered = []
        
        try:
            # Get all positions
            positions = await get_all_positions()
            if not positions:
                return triggered
            
            # Create position lookup by symbol
            positions_by_symbol = {}
            for pos in positions:
                symbol = pos.get('symbol')
                if symbol and float(pos.get('size', 0)) > 0:
                    positions_by_symbol[symbol] = pos
            
            # Check each alert
            for alert in alerts:
                if alert.symbol and alert.symbol in positions_by_symbol:
                    position = positions_by_symbol[alert.symbol]
                    trigger_info = await self._check_single_alert(alert, position)
                    if trigger_info:
                        triggered.append(trigger_info)
                        
        except Exception as e:
            logger.error(f"Error checking position alerts: {e}")
        
        return triggered
    
    async def _check_single_alert(self, alert: Alert, position: Dict) -> Optional[Dict]:
        """Check individual position alert"""
        try:
            # Extract position data
            symbol = position.get('symbol')
            side = position.get('side')
            size = Decimal(str(position.get('size', 0)))
            avg_price = Decimal(str(position.get('avgPrice', 0)))
            mark_price = Decimal(str(position.get('markPrice', 0)))
            unrealized_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
            position_value = Decimal(str(position.get('positionValue', 0)))
            
            # Calculate P&L percentage
            if position_value > 0:
                pnl_percent = (unrealized_pnl / position_value) * 100
            else:
                pnl_percent = Decimal('0')
            
            # Check alert conditions
            if alert.type == AlertType.POSITION_PROFIT_AMOUNT:
                if unrealized_pnl >= alert.condition_value:
                    return {
                        'alert': alert,
                        'message': self._format_pnl_alert_message(
                            alert, position, unrealized_pnl, pnl_percent, "PROFIT TARGET REACHED"
                        ),
                        'pnl': unrealized_pnl,
                        'trigger_type': 'profit_amount'
                    }
            
            elif alert.type == AlertType.POSITION_PROFIT_PERCENT:
                if pnl_percent >= alert.condition_value:
                    return {
                        'alert': alert,
                        'message': self._format_pnl_alert_message(
                            alert, position, unrealized_pnl, pnl_percent, "PROFIT % TARGET REACHED"
                        ),
                        'pnl_percent': pnl_percent,
                        'trigger_type': 'profit_percent'
                    }
            
            elif alert.type == AlertType.POSITION_LOSS_AMOUNT:
                if unrealized_pnl <= -abs(alert.condition_value):
                    return {
                        'alert': alert,
                        'message': self._format_pnl_alert_message(
                            alert, position, unrealized_pnl, pnl_percent, "LOSS THRESHOLD REACHED"
                        ),
                        'pnl': unrealized_pnl,
                        'trigger_type': 'loss_amount'
                    }
            
            elif alert.type == AlertType.POSITION_LOSS_PERCENT:
                if pnl_percent <= -abs(alert.condition_value):
                    return {
                        'alert': alert,
                        'message': self._format_pnl_alert_message(
                            alert, position, unrealized_pnl, pnl_percent, "LOSS % THRESHOLD REACHED"
                        ),
                        'pnl_percent': pnl_percent,
                        'trigger_type': 'loss_percent'
                    }
            
            elif alert.type == AlertType.POSITION_BREAKEVEN:
                # Check if position is near breakeven (within 0.1%)
                if abs(pnl_percent) <= Decimal('0.1'):
                    return {
                        'alert': alert,
                        'message': self._format_breakeven_alert_message(alert, position, unrealized_pnl),
                        'pnl': unrealized_pnl,
                        'trigger_type': 'breakeven'
                    }
            
            elif alert.type == AlertType.POSITION_NEAR_TP:
                # Check if near take profit (within 2% of TP orders)
                tp_distance = await self._check_near_tp(position, mark_price)
                if tp_distance and tp_distance <= 2:
                    return {
                        'alert': alert,
                        'message': self._format_near_tp_alert_message(
                            alert, position, tp_distance
                        ),
                        'distance_percent': tp_distance,
                        'trigger_type': 'near_tp'
                    }
            
            elif alert.type == AlertType.POSITION_NEAR_SL:
                # Check if near stop loss (within 2% of SL orders)
                sl_distance = await self._check_near_sl(position, mark_price)
                if sl_distance and sl_distance <= 2:
                    return {
                        'alert': alert,
                        'message': self._format_near_sl_alert_message(
                            alert, position, sl_distance
                        ),
                        'distance_percent': sl_distance,
                        'trigger_type': 'near_sl'
                    }
                    
        except Exception as e:
            logger.error(f"Error checking position alert {alert.id}: {e}")
        
        return None
    
    async def _check_near_tp(self, position: Dict, mark_price: Decimal) -> Optional[Decimal]:
        """Check distance to nearest TP order"""
        # This would need to fetch orders for the position
        # For now, return None (not implemented)
        return None
    
    async def _check_near_sl(self, position: Dict, mark_price: Decimal) -> Optional[Decimal]:
        """Check distance to SL order"""
        # This would need to fetch orders for the position
        # For now, return None (not implemented)
        return None
    
    def _format_pnl_alert_message(self, alert: Alert, position: Dict,
                                 pnl: Decimal, pnl_percent: Decimal, title: str) -> str:
        """Format P&L alert message"""
        symbol = position.get('symbol')
        side = position.get('side')
        avg_price = Decimal(str(position.get('avgPrice', 0)))
        mark_price = Decimal(str(position.get('markPrice', 0)))
        size = Decimal(str(position.get('size', 0)))
        
        emoji = "💰" if pnl > 0 else "🔴"
        side_emoji = "📈" if side == 'Buy' else "📉"
        
        message = f"""
{emoji} <b>{title}!</b>
━━━━━━━━━━━━━━━
📊 {symbol} {side_emoji} {side}
💵 P&L: ${pnl:,.2f} ({pnl_percent:+.2f}%)
📍 Entry: ${avg_price:,.2f}
📈 Current: ${mark_price:,.2f}
📦 Size: {size}
"""
        
        if alert.type in [AlertType.POSITION_PROFIT_AMOUNT, AlertType.POSITION_LOSS_AMOUNT]:
            message += f"🎯 Target: ${alert.condition_value:,.2f}\n"
        else:
            message += f"🎯 Target: {alert.condition_value:+.2f}%\n"
        
        if alert.notes:
            message += f"\n💬 {alert.notes}"
        
        return message.strip()
    
    def _format_breakeven_alert_message(self, alert: Alert, position: Dict,
                                      pnl: Decimal) -> str:
        """Format breakeven alert message"""
        symbol = position.get('symbol')
        side = position.get('side')
        mark_price = Decimal(str(position.get('markPrice', 0)))
        side_emoji = "📈" if side == 'Buy' else "📉"
        
        return f"""
⚖️ <b>POSITION AT BREAKEVEN</b>
━━━━━━━━━━━━━━━
📊 {symbol} {side_emoji} {side}
💵 P&L: ${pnl:,.2f}
📈 Price: ${mark_price:,.2f}

Consider moving stop loss to breakeven!
""".strip()
    
    def _format_near_tp_alert_message(self, alert: Alert, position: Dict,
                                    distance_percent: Decimal) -> str:
        """Format near TP alert message"""
        symbol = position.get('symbol')
        side = position.get('side')
        unrealized_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
        side_emoji = "📈" if side == 'Buy' else "📉"
        
        return f"""
🎯 <b>APPROACHING TAKE PROFIT</b>
━━━━━━━━━━━━━━━
📊 {symbol} {side_emoji} {side}
📏 Distance to TP: {distance_percent:.1f}%
💵 Current P&L: ${unrealized_pnl:,.2f}

Position is close to take profit target!
""".strip()
    
    def _format_near_sl_alert_message(self, alert: Alert, position: Dict,
                                    distance_percent: Decimal) -> str:
        """Format near SL alert message"""
        symbol = position.get('symbol')
        side = position.get('side')
        unrealized_pnl = Decimal(str(position.get('unrealisedPnl', 0)))
        side_emoji = "📈" if side == 'Buy' else "📉"
        
        return f"""
⚠️ <b>APPROACHING STOP LOSS</b>
━━━━━━━━━━━━━━━
📊 {symbol} {side_emoji} {side}
📏 Distance to SL: {distance_percent:.1f}%
💵 Current P&L: ${unrealized_pnl:,.2f}

⚠️ Position at risk! Consider action.
""".strip()