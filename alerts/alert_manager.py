#!/usr/bin/env python3
"""
Core alert management system
"""
import logging
import asyncio
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import uuid

from telegram import Bot
from telegram.constants import ParseMode

from .alert_types import Alert, AlertType, AlertPriority, ALERT_CONFIGS
from .storage import AlertStorage
from .price_alerts import PriceAlertChecker
from .position_alerts import PositionAlertChecker
from .risk_alerts import RiskAlertChecker
from .volatility_alerts import VolatilityAlertChecker
from .daily_reports import DailyReportGenerator

logger = logging.getLogger(__name__)

class AlertManager:
    """Central alert management system"""
    
    def __init__(self, bot: Bot, storage_path: str = "alerts_data.pkl"):
        self.bot = bot
        self.storage = AlertStorage(storage_path)
        self.is_running = False
        self._monitoring_task = None
        self._daily_report_task = None
        
        # Initialize alert checkers
        self.price_checker = PriceAlertChecker()
        self.position_checker = PositionAlertChecker()
        self.risk_checker = RiskAlertChecker()
        self.volatility_checker = VolatilityAlertChecker()
        self.report_generator = DailyReportGenerator()
        
        # Alert check interval (seconds)
        self.check_interval = 30
        
        logger.info("Alert Manager initialized")
    
    async def start(self):
        """Start alert monitoring"""
        if self.is_running:
            logger.warning("Alert monitoring already running")
            return
        
        self.is_running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._daily_report_task = asyncio.create_task(self._daily_report_loop())
        logger.info("Alert monitoring started")
    
    async def stop(self):
        """Stop alert monitoring"""
        self.is_running = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self._daily_report_task:
            self._daily_report_task.cancel()
            try:
                await self._daily_report_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Alert monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self._check_all_alerts()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_all_alerts(self):
        """Check all active alerts"""
        current_time = datetime.utcnow()
        
        # Cleanup expired alerts
        self.storage.cleanup_expired()
        
        # Group alerts by type for efficient checking
        alerts_by_type = {}
        for alert in self.storage.alerts.values():
            if alert.enabled and alert.should_trigger(current_time):
                if alert.type not in alerts_by_type:
                    alerts_by_type[alert.type] = []
                alerts_by_type[alert.type].append(alert)
        
        # Check each type
        for alert_type, alerts in alerts_by_type.items():
            try:
                if alert_type in [AlertType.PRICE_ABOVE, AlertType.PRICE_BELOW, 
                                 AlertType.PRICE_CROSS, AlertType.PRICE_CHANGE_PERCENT]:
                    triggered = await self.price_checker.check_alerts(alerts)
                    await self._process_triggered_alerts(triggered)
                
                elif alert_type in [AlertType.POSITION_PROFIT_AMOUNT, AlertType.POSITION_PROFIT_PERCENT,
                                   AlertType.POSITION_LOSS_AMOUNT, AlertType.POSITION_LOSS_PERCENT,
                                   AlertType.POSITION_NEAR_TP, AlertType.POSITION_NEAR_SL,
                                   AlertType.POSITION_BREAKEVEN]:
                    triggered = await self.position_checker.check_alerts(alerts)
                    await self._process_triggered_alerts(triggered)
                
                elif alert_type in [AlertType.HIGH_LEVERAGE, AlertType.LARGE_POSITION,
                                   AlertType.ACCOUNT_DRAWDOWN, AlertType.CORRELATED_POSITIONS]:
                    triggered = await self.risk_checker.check_alerts(alerts)
                    await self._process_triggered_alerts(triggered)
                
                elif alert_type in [AlertType.VOLATILITY_SPIKE, AlertType.VOLUME_SPIKE,
                                   AlertType.FUNDING_RATE]:
                    triggered = await self.volatility_checker.check_alerts(alerts)
                    await self._process_triggered_alerts(triggered)
                    
            except Exception as e:
                logger.error(f"Error checking {alert_type} alerts: {e}")
    
    async def _process_triggered_alerts(self, triggered_alerts: List[Dict]):
        """Process and send triggered alerts"""
        for trigger_info in triggered_alerts:
            alert = trigger_info['alert']
            message = trigger_info['message']
            
            try:
                # Check user preferences
                prefs = self.storage.get_user_preferences(alert.chat_id)
                
                # Check mute times
                current_hour = datetime.utcnow().hour
                if prefs.get('mute_start') and prefs.get('mute_end'):
                    mute_start = int(prefs['mute_start'])
                    mute_end = int(prefs['mute_end'])
                    if mute_start <= current_hour < mute_end:
                        continue
                
                # Check priority
                min_priority = AlertPriority[prefs.get('min_priority', 'low').upper()]
                if alert.priority.value < min_priority.value:
                    continue
                
                # Send notification
                await self.bot.send_message(
                    chat_id=alert.chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML
                )
                
                # Update alert
                alert.mark_triggered()
                self.storage.save()
                
                # Add to history
                self.storage.add_to_history(alert.id, trigger_info)
                
                logger.info(f"Sent alert {alert.id} to chat {alert.chat_id}")
                
            except Exception as e:
                logger.error(f"Error sending alert {alert.id}: {e}")
    
    async def _daily_report_loop(self):
        """Daily report generation loop"""
        while self.is_running:
            try:
                # Check every hour if any reports need to be sent
                current_time = datetime.utcnow()
                current_hour = current_time.strftime("%H:00")
                
                # Get all users with daily reports enabled
                for chat_id, prefs in self.storage.user_preferences.items():
                    if prefs.get('daily_report_enabled', True):
                        report_time = prefs.get('daily_report_time', '08:00')
                        if report_time == current_hour:
                            # Check if report was already sent today
                            last_report_key = f"last_daily_report_{chat_id}"
                            last_report = prefs.get(last_report_key)
                            today = current_time.date()
                            
                            if not last_report or last_report != str(today):
                                # Generate and send report
                                report = await self.report_generator.generate_report(chat_id)
                                if report:
                                    await self.bot.send_message(
                                        chat_id=chat_id,
                                        text=report,
                                        parse_mode=ParseMode.HTML
                                    )
                                    
                                    # Update last sent
                                    self.storage.update_user_preferences(
                                        chat_id, 
                                        **{last_report_key: str(today)}
                                    )
                
                # Sleep until next hour
                next_hour = (current_time + timedelta(hours=1)).replace(minute=0, second=0)
                sleep_seconds = (next_hour - current_time).total_seconds()
                await asyncio.sleep(sleep_seconds)
                
            except Exception as e:
                logger.error(f"Error in daily report loop: {e}")
                await asyncio.sleep(3600)  # Sleep 1 hour on error
    
    def create_alert(self, chat_id: int, alert_type: AlertType, **kwargs) -> Optional[Alert]:
        """Create new alert"""
        try:
            alert_id = str(uuid.uuid4())[:8]
            config = ALERT_CONFIGS.get(alert_type, {})
            
            alert = Alert(
                id=alert_id,
                type=alert_type,
                chat_id=chat_id,
                priority=config.get('priority', AlertPriority.MEDIUM),
                **kwargs
            )
            
            if self.storage.add_alert(alert):
                return alert
            return None
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
            return None
    
    def delete_alert(self, alert_id: str) -> bool:
        """Delete alert"""
        return self.storage.remove_alert(alert_id)
    
    def get_user_alerts(self, chat_id: int) -> List[Alert]:
        """Get all alerts for user"""
        return self.storage.get_user_alerts(chat_id)
    
    def toggle_alert(self, alert_id: str) -> bool:
        """Toggle alert enabled/disabled"""
        alert = self.storage.get_alert(alert_id)
        if alert:
            return self.storage.update_alert(alert_id, enabled=not alert.enabled)
        return False
    
    def update_preferences(self, chat_id: int, **kwargs) -> bool:
        """Update user preferences"""
        return self.storage.update_user_preferences(chat_id, **kwargs)