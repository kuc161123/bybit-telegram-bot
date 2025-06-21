#!/usr/bin/env python3
"""
Price monitoring and alerts
"""
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta

from utils.cache import get_ticker_price_cached
from .alert_types import Alert, AlertType

logger = logging.getLogger(__name__)

class PriceAlertChecker:
    """Checks price-based alerts"""
    
    def __init__(self):
        self.price_history = {}  # symbol -> list of (timestamp, price)
        self.max_history = 100
    
    async def check_alerts(self, alerts: List[Alert]) -> List[Dict]:
        """Check price alerts and return triggered ones"""
        triggered = []
        
        # Group alerts by symbol for efficiency
        alerts_by_symbol = {}
        for alert in alerts:
            if alert.symbol not in alerts_by_symbol:
                alerts_by_symbol[alert.symbol] = []
            alerts_by_symbol[alert.symbol].append(alert)
        
        # Check each symbol
        for symbol, symbol_alerts in alerts_by_symbol.items():
            try:
                # Get current price
                current_price = await get_ticker_price_cached(symbol)
                if not current_price:
                    continue
                
                current_price = Decimal(str(current_price))
                
                # Update price history
                self._update_price_history(symbol, current_price)
                
                # Check each alert for this symbol
                for alert in symbol_alerts:
                    trigger_info = await self._check_single_alert(
                        alert, symbol, current_price
                    )
                    if trigger_info:
                        triggered.append(trigger_info)
                        
            except Exception as e:
                logger.error(f"Error checking price alerts for {symbol}: {e}")
        
        return triggered
    
    async def _check_single_alert(self, alert: Alert, symbol: str, 
                                 current_price: Decimal) -> Optional[Dict]:
        """Check individual price alert"""
        try:
            if alert.type == AlertType.PRICE_ABOVE:
                if current_price > alert.condition_value:
                    return {
                        'alert': alert,
                        'message': self._format_price_alert_message(
                            alert, symbol, current_price, "crossed ABOVE"
                        ),
                        'current_price': current_price,
                        'trigger_type': 'price_above'
                    }
            
            elif alert.type == AlertType.PRICE_BELOW:
                if current_price < alert.condition_value:
                    return {
                        'alert': alert,
                        'message': self._format_price_alert_message(
                            alert, symbol, current_price, "crossed BELOW"
                        ),
                        'current_price': current_price,
                        'trigger_type': 'price_below'
                    }
            
            elif alert.type == AlertType.PRICE_CROSS:
                # Check if price crossed the target level
                if self._check_price_cross(symbol, alert.condition_value, current_price):
                    direction = "UP" if current_price > alert.condition_value else "DOWN"
                    return {
                        'alert': alert,
                        'message': self._format_price_alert_message(
                            alert, symbol, current_price, f"crossed {direction} through"
                        ),
                        'current_price': current_price,
                        'trigger_type': 'price_cross'
                    }
            
            elif alert.type == AlertType.PRICE_CHANGE_PERCENT:
                # Check percentage change
                change_percent = self._calculate_price_change_percent(symbol)
                if change_percent and abs(change_percent) >= abs(alert.condition_value):
                    return {
                        'alert': alert,
                        'message': self._format_price_change_message(
                            alert, symbol, current_price, change_percent
                        ),
                        'current_price': current_price,
                        'change_percent': change_percent,
                        'trigger_type': 'price_change_percent'
                    }
            
        except Exception as e:
            logger.error(f"Error checking alert {alert.id}: {e}")
        
        return None
    
    def _update_price_history(self, symbol: str, price: Decimal):
        """Update price history for symbol"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        history = self.price_history[symbol]
        history.append((datetime.utcnow(), price))
        
        # Keep only recent history
        if len(history) > self.max_history:
            self.price_history[symbol] = history[-self.max_history:]
    
    def _check_price_cross(self, symbol: str, target_price: Decimal, 
                          current_price: Decimal) -> bool:
        """Check if price crossed target level"""
        history = self.price_history.get(symbol, [])
        if len(history) < 2:
            return False
        
        # Get previous price
        _, prev_price = history[-2]
        
        # Check for cross
        crossed_up = prev_price <= target_price < current_price
        crossed_down = prev_price >= target_price > current_price
        
        return crossed_up or crossed_down
    
    def _calculate_price_change_percent(self, symbol: str) -> Optional[Decimal]:
        """Calculate price change percentage over last hour"""
        history = self.price_history.get(symbol, [])
        if not history:
            return None
        
        current_time = datetime.utcnow()
        one_hour_ago = current_time - timedelta(hours=1)
        
        # Find price from ~1 hour ago
        old_price = None
        for timestamp, price in history:
            if timestamp >= one_hour_ago:
                old_price = price
                break
        
        if not old_price:
            # Use oldest available price
            if history:
                _, old_price = history[0]
            else:
                return None
        
        # Calculate percentage change
        _, current_price = history[-1]
        change_percent = ((current_price - old_price) / old_price) * 100
        
        return change_percent
    
    def _format_price_alert_message(self, alert: Alert, symbol: str, 
                                   current_price: Decimal, action: str) -> str:
        """Format price alert message"""
        config = ALERT_CONFIGS.get(alert.type, {})
        emoji = config.get('emoji', '🔔')
        
        return f"""
{emoji} <b>PRICE ALERT - {symbol}</b>
━━━━━━━━━━━━━━━
📊 Current: ${current_price:,.2f}
🎯 Target: ${alert.condition_value:,.2f}
📈 Action: {action}
⏰ Time: {datetime.utcnow().strftime('%H:%M UTC')}

{alert.notes or ''}
""".strip()
    
    def _format_price_change_message(self, alert: Alert, symbol: str,
                                   current_price: Decimal, change_percent: Decimal) -> str:
        """Format price change percentage alert"""
        emoji = "📈" if change_percent > 0 else "📉"
        
        return f"""
{emoji} <b>PRICE CHANGE ALERT - {symbol}</b>
━━━━━━━━━━━━━━━
📊 Current: ${current_price:,.2f}
📊 Change: {change_percent:+.2f}%
🎯 Threshold: {alert.condition_value:+.2f}%
⏰ Time: {datetime.utcnow().strftime('%H:%M UTC')}

{alert.notes or ''}
""".strip()