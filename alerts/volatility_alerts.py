#!/usr/bin/env python3
"""
Market volatility and volume monitoring alerts
"""
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict

from utils.cache import get_ticker_price_cached
from .alert_types import Alert, AlertType, ALERT_CONFIGS

logger = logging.getLogger(__name__)

class VolatilityAlertChecker:
    """Checks volatility and volume-based alerts"""
    
    def __init__(self):
        self.volatility_cache = {}  # symbol -> (timestamp, volatility)
        self.volume_cache = {}      # symbol -> (timestamp, volume_data)
        self.cache_ttl = 300        # 5 minutes
    
    async def check_alerts(self, alerts: List[Alert]) -> List[Dict]:
        """Check volatility alerts and return triggered ones"""
        triggered = []
        
        # Group alerts by symbol for efficiency
        alerts_by_symbol = defaultdict(lambda: defaultdict(list))
        for alert in alerts:
            if alert.symbol:
                alerts_by_symbol[alert.symbol][alert.type].append(alert)
        
        # Check each symbol
        for symbol, type_alerts in alerts_by_symbol.items():
            try:
                # Check volatility spike alerts
                if AlertType.VOLATILITY_SPIKE in type_alerts:
                    volatility = await self._get_volatility(symbol)
                    if volatility:
                        for alert in type_alerts[AlertType.VOLATILITY_SPIKE]:
                            if volatility >= alert.condition_value:
                                triggered.append({
                                    'alert': alert,
                                    'message': self._format_volatility_message(
                                        symbol, volatility, alert.condition_value
                                    ),
                                    'volatility': volatility,
                                    'trigger_type': 'volatility_spike'
                                })
                
                # Check volume spike alerts
                if AlertType.VOLUME_SPIKE in type_alerts:
                    volume_data = await self._get_volume_data(symbol)
                    if volume_data:
                        current_volume = volume_data['current']
                        avg_volume = volume_data['average']
                        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
                        
                        for alert in type_alerts[AlertType.VOLUME_SPIKE]:
                            if volume_ratio >= alert.condition_value:
                                triggered.append({
                                    'alert': alert,
                                    'message': self._format_volume_message(
                                        symbol, current_volume, avg_volume, 
                                        volume_ratio, alert.condition_value
                                    ),
                                    'volume_ratio': volume_ratio,
                                    'trigger_type': 'volume_spike'
                                })
                
                # Check funding rate alerts
                if AlertType.FUNDING_RATE in type_alerts:
                    funding_rate = await self._get_funding_rate(symbol)
                    if funding_rate is not None:
                        for alert in type_alerts[AlertType.FUNDING_RATE]:
                            # Check both positive and negative funding rates
                            if abs(funding_rate) >= abs(alert.condition_value):
                                triggered.append({
                                    'alert': alert,
                                    'message': self._format_funding_message(
                                        symbol, funding_rate, alert.condition_value
                                    ),
                                    'funding_rate': funding_rate,
                                    'trigger_type': 'funding_rate'
                                })
                        
            except Exception as e:
                logger.error(f"Error checking volatility alerts for {symbol}: {e}")
        
        return triggered
    
    async def _get_volatility(self, symbol: str) -> Optional[Decimal]:
        """Calculate current volatility for symbol"""
        try:
            # Check cache
            now = datetime.utcnow()
            if symbol in self.volatility_cache:
                cached_time, cached_vol = self.volatility_cache[symbol]
                if (now - cached_time).total_seconds() < self.cache_ttl:
                    return cached_vol
            
            # For now, return a placeholder volatility
            # TODO: Implement actual kline data fetching
            # This would require implementing get_kline_data in bybit_helpers
            return None
            
        except Exception as e:
            logger.error(f"Error calculating volatility for {symbol}: {e}")
            return None
    
    async def _get_volume_data(self, symbol: str) -> Optional[Dict]:
        """Get current and average volume data"""
        try:
            # Check cache
            now = datetime.utcnow()
            if symbol in self.volume_cache:
                cached_time, cached_data = self.volume_cache[symbol]
                if (now - cached_time).total_seconds() < self.cache_ttl:
                    return cached_data
            
            # For now, return placeholder volume data
            # TODO: Implement actual kline data fetching
            # This would require implementing get_kline_data in bybit_helpers
            return None
            
        except Exception as e:
            logger.error(f"Error getting volume data for {symbol}: {e}")
            return None
    
    async def _get_funding_rate(self, symbol: str) -> Optional[Decimal]:
        """Get current funding rate for symbol"""
        try:
            # This would need to be implemented with Bybit API
            # For now, return None (not implemented)
            # In a real implementation, you would fetch from Bybit's funding rate endpoint
            return None
            
        except Exception as e:
            logger.error(f"Error getting funding rate for {symbol}: {e}")
            return None
    
    def _format_volatility_message(self, symbol: str, volatility: Decimal, 
                                  threshold: Decimal) -> str:
        """Format volatility alert message"""
        return f"""
🌊 <b>HIGH VOLATILITY ALERT</b>
━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
📈 Volatility: {volatility:.2f}%
🎯 Threshold: {threshold}%

⚠️ Market is highly volatile!
Consider adjusting position sizes.
""".strip()
    
    def _format_volume_message(self, symbol: str, current_volume: Decimal,
                             avg_volume: Decimal, volume_ratio: Decimal,
                             threshold: Decimal) -> str:
        """Format volume spike alert message"""
        change_percent = ((current_volume - avg_volume) / avg_volume * 100) if avg_volume > 0 else 0
        
        return f"""
📊 <b>VOLUME SPIKE ALERT</b>
━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
📈 Current Volume: {current_volume:,.0f}
📊 Average Volume: {avg_volume:,.0f}
⚡ Spike: {volume_ratio:.1f}x ({change_percent:+.1f}%)
🎯 Threshold: {threshold}x

🔥 Unusual trading activity detected!
""".strip()
    
    def _format_funding_message(self, symbol: str, funding_rate: Decimal,
                              threshold: Decimal) -> str:
        """Format funding rate alert message"""
        rate_pct = funding_rate * 100  # Convert to percentage
        emoji = "📈" if funding_rate > 0 else "📉"
        
        return f"""
💰 <b>FUNDING RATE ALERT</b>
━━━━━━━━━━━━━━━
📊 Symbol: {symbol}
{emoji} Funding Rate: {rate_pct:+.4f}%
🎯 Threshold: {abs(threshold * 100):.4f}%

{"⚠️ Longs paying shorts!" if funding_rate > 0 else "⚠️ Shorts paying longs!"}
Consider the cost of holding positions.
""".strip()