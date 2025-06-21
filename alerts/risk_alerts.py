#!/usr/bin/env python3
"""
Risk monitoring and alerts
"""
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from collections import defaultdict

from clients.bybit_helpers import get_all_positions
from utils.cache import get_usdt_wallet_balance_cached
from .alert_types import Alert, AlertType, ALERT_CONFIGS

logger = logging.getLogger(__name__)

class RiskAlertChecker:
    """Checks risk-based alerts"""
    
    def __init__(self):
        self.last_account_balance = None
        self.peak_balance = None
    
    async def check_alerts(self, alerts: List[Alert]) -> List[Dict]:
        """Check risk alerts and return triggered ones"""
        triggered = []
        
        try:
            # Get current positions and account data
            positions = await get_all_positions()
            total_balance, available_balance = await get_usdt_wallet_balance_cached()
            
            # Update balance tracking
            if self.last_account_balance is None:
                self.last_account_balance = total_balance
            if self.peak_balance is None or total_balance > self.peak_balance:
                self.peak_balance = total_balance
            
            # Group alerts by type
            alerts_by_type = defaultdict(list)
            for alert in alerts:
                alerts_by_type[alert.type].append(alert)
            
            # Check each type
            for alert_type, type_alerts in alerts_by_type.items():
                if alert_type == AlertType.HIGH_LEVERAGE:
                    triggered.extend(await self._check_high_leverage(type_alerts, positions))
                
                elif alert_type == AlertType.LARGE_POSITION:
                    triggered.extend(await self._check_large_positions(
                        type_alerts, positions, total_balance
                    ))
                
                elif alert_type == AlertType.ACCOUNT_DRAWDOWN:
                    triggered.extend(await self._check_drawdown(
                        type_alerts, total_balance, self.peak_balance
                    ))
                
                elif alert_type == AlertType.CORRELATED_POSITIONS:
                    triggered.extend(await self._check_correlated_positions(
                        type_alerts, positions
                    ))
            
            # Update last balance
            self.last_account_balance = total_balance
            
        except Exception as e:
            logger.error(f"Error checking risk alerts: {e}")
        
        return triggered
    
    async def _check_high_leverage(self, alerts: List[Alert], 
                                 positions: List[Dict]) -> List[Dict]:
        """Check for high leverage usage"""
        triggered = []
        
        for position in positions:
            if float(position.get('size', 0)) <= 0:
                continue
            
            leverage = int(position.get('leverage', 1))
            symbol = position.get('symbol')
            
            for alert in alerts:
                if alert.condition_value is not None and leverage >= alert.condition_value:
                    triggered.append({
                        'alert': alert,
                        'message': self._format_high_leverage_message(
                            symbol, leverage, alert.condition_value
                        ),
                        'leverage': leverage,
                        'symbol': symbol,
                        'trigger_type': 'high_leverage'
                    })
                    break  # Only trigger once per position
        
        return triggered
    
    async def _check_large_positions(self, alerts: List[Alert], 
                                   positions: List[Dict],
                                   total_balance: Decimal) -> List[Dict]:
        """Check for large position sizes"""
        triggered = []
        
        if total_balance <= 0:
            return triggered
        
        for position in positions:
            if float(position.get('size', 0)) <= 0:
                continue
            
            position_value = Decimal(str(position.get('positionValue', 0)))
            position_percent = (position_value / total_balance) * 100
            symbol = position.get('symbol')
            
            for alert in alerts:
                if alert.condition_value is not None and position_percent >= alert.condition_value:
                    triggered.append({
                        'alert': alert,
                        'message': self._format_large_position_message(
                            symbol, position_percent, position_value,
                            alert.condition_value
                        ),
                        'position_percent': position_percent,
                        'symbol': symbol,
                        'trigger_type': 'large_position'
                    })
                    break
        
        return triggered
    
    async def _check_drawdown(self, alerts: List[Alert],
                            current_balance: Decimal,
                            peak_balance: Decimal) -> List[Dict]:
        """Check for account drawdown"""
        triggered = []
        
        if not peak_balance or peak_balance <= 0:
            return triggered
        
        drawdown_percent = ((peak_balance - current_balance) / peak_balance) * 100
        
        for alert in alerts:
            if alert.condition_value is not None and drawdown_percent >= alert.condition_value:
                triggered.append({
                    'alert': alert,
                    'message': self._format_drawdown_message(
                        drawdown_percent, current_balance, peak_balance,
                        alert.condition_value
                    ),
                    'drawdown_percent': drawdown_percent,
                    'trigger_type': 'account_drawdown'
                })
        
        return triggered
    
    async def _check_correlated_positions(self, alerts: List[Alert],
                                        positions: List[Dict]) -> List[Dict]:
        """Check for correlated positions"""
        triggered = []
        
        # Group positions by correlation
        # Simple implementation: check for multiple positions in same direction
        long_positions = []
        short_positions = []
        
        for position in positions:
            if float(position.get('size', 0)) <= 0:
                continue
            
            if position.get('side') == 'Buy':
                long_positions.append(position)
            else:
                short_positions.append(position)
        
        # Check if too many positions in same direction
        for alert in alerts:
            threshold = int(alert.condition_value)
            
            if len(long_positions) >= threshold:
                triggered.append({
                    'alert': alert,
                    'message': self._format_correlated_message(
                        'LONG', long_positions, threshold
                    ),
                    'position_count': len(long_positions),
                    'trigger_type': 'correlated_positions'
                })
            
            if len(short_positions) >= threshold:
                triggered.append({
                    'alert': alert,
                    'message': self._format_correlated_message(
                        'SHORT', short_positions, threshold
                    ),
                    'position_count': len(short_positions),
                    'trigger_type': 'correlated_positions'
                })
        
        return triggered
    
    def _format_high_leverage_message(self, symbol: str, leverage: int,
                                    threshold: Decimal) -> str:
        """Format high leverage alert message"""
        return f"""
⚠️ <b>HIGH LEVERAGE WARNING</b>
━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
⚡ Leverage: {leverage}x
🎯 Threshold: {threshold}x

⚠️ High leverage increases risk!
Consider reducing leverage or position size.
""".strip()
    
    def _format_large_position_message(self, symbol: str, position_percent: Decimal,
                                     position_value: Decimal, threshold: Decimal) -> str:
        """Format large position alert message"""
        return f"""
⚠️ <b>LARGE POSITION WARNING</b>
━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
💰 Position Value: ${position_value:,.2f}
📊 % of Account: {position_percent:.1f}%
🎯 Threshold: {threshold}%

⚠️ Large position size detected!
Consider diversifying risk.
""".strip()
    
    def _format_drawdown_message(self, drawdown_percent: Decimal,
                               current_balance: Decimal,
                               peak_balance: Decimal,
                               threshold: Decimal) -> str:
        """Format drawdown alert message"""
        loss_amount = peak_balance - current_balance
        
        return f"""
🔴 <b>ACCOUNT DRAWDOWN ALERT</b>
━━━━━━━━━━━━━━━
📉 Drawdown: -{drawdown_percent:.1f}%
💰 Current: ${current_balance:,.2f}
📊 Peak: ${peak_balance:,.2f}
💸 Loss: -${loss_amount:,.2f}
🎯 Threshold: -{threshold}%

⚠️ Significant drawdown detected!
Consider reducing risk or taking a break.
""".strip()
    
    def _format_correlated_message(self, direction: str,
                                 positions: List[Dict],
                                 threshold: int) -> str:
        """Format correlated positions alert"""
        symbols = [p.get('symbol') for p in positions[:5]]  # Show first 5
        total_value = sum(Decimal(str(p.get('positionValue', 0))) for p in positions)
        
        emoji = "📈" if direction == "LONG" else "📉"
        
        message = f"""
⚠️ <b>CORRELATED POSITIONS WARNING</b>
━━━━━━━━━━━━━━━
{emoji} Direction: {direction}
📊 Count: {len(positions)} positions
💰 Total Value: ${total_value:,.2f}
🎯 Threshold: {threshold} positions

Positions: {', '.join(symbols)}
"""
        
        if len(positions) > 5:
            message += f"\n... and {len(positions) - 5} more"
        
        message += "\n\n⚠️ Multiple correlated positions increase risk!"
        
        return message.strip()