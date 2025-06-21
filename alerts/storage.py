#!/usr/bin/env python3
"""
Alert storage and persistence
"""
import logging
import pickle
import os
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .alert_types import Alert, AlertType

logger = logging.getLogger(__name__)

class AlertStorage:
    """Manages alert persistence"""
    
    def __init__(self, storage_path: str = "alerts_data.pkl"):
        self.storage_path = storage_path
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: List[Dict] = []
        self.user_preferences: Dict[int, Dict] = {}  # chat_id -> preferences
        self._load()
    
    def _load(self):
        """Load alerts from storage"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'rb') as f:
                    data = pickle.load(f)
                    self.alerts = data.get('alerts', {})
                    self.alert_history = data.get('history', [])
                    self.user_preferences = data.get('preferences', {})
                    logger.info(f"Loaded {len(self.alerts)} alerts from storage")
            else:
                logger.info("No existing alerts storage found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading alerts: {e}")
            self.alerts = {}
            self.alert_history = []
            self.user_preferences = {}
    
    def save(self):
        """Save alerts to storage"""
        try:
            data = {
                'alerts': self.alerts,
                'history': self.alert_history,
                'preferences': self.user_preferences,
                'last_saved': datetime.utcnow()
            }
            
            # Create backup
            if os.path.exists(self.storage_path):
                backup_path = f"{self.storage_path}.backup"
                os.rename(self.storage_path, backup_path)
            
            # Save new data
            with open(self.storage_path, 'wb') as f:
                pickle.dump(data, f)
            
            logger.debug(f"Saved {len(self.alerts)} alerts to storage")
        except Exception as e:
            logger.error(f"Error saving alerts: {e}")
    
    def add_alert(self, alert: Alert) -> bool:
        """Add new alert"""
        try:
            self.alerts[alert.id] = alert
            self.save()
            logger.info(f"Added alert {alert.id} for chat {alert.chat_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding alert: {e}")
            return False
    
    def remove_alert(self, alert_id: str) -> bool:
        """Remove alert"""
        try:
            if alert_id in self.alerts:
                del self.alerts[alert_id]
                self.save()
                logger.info(f"Removed alert {alert_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing alert: {e}")
            return False
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get specific alert"""
        return self.alerts.get(alert_id)
    
    def get_user_alerts(self, chat_id: int) -> List[Alert]:
        """Get all alerts for a user"""
        return [alert for alert in self.alerts.values() if alert.chat_id == chat_id]
    
    def get_alerts_by_type(self, alert_type: AlertType) -> List[Alert]:
        """Get all alerts of specific type"""
        return [alert for alert in self.alerts.values() if alert.type == alert_type]
    
    def get_alerts_by_symbol(self, symbol: str) -> List[Alert]:
        """Get all alerts for a symbol"""
        return [alert for alert in self.alerts.values() if alert.symbol == symbol]
    
    def update_alert(self, alert_id: str, **kwargs) -> bool:
        """Update alert properties"""
        try:
            if alert_id in self.alerts:
                alert = self.alerts[alert_id]
                for key, value in kwargs.items():
                    if hasattr(alert, key):
                        setattr(alert, key, value)
                self.save()
                return True
            return False
        except Exception as e:
            logger.error(f"Error updating alert: {e}")
            return False
    
    def add_to_history(self, alert_id: str, trigger_info: Dict):
        """Add alert trigger to history"""
        try:
            history_entry = {
                'alert_id': alert_id,
                'triggered_at': datetime.utcnow(),
                'info': trigger_info
            }
            self.alert_history.append(history_entry)
            
            # Keep only last 1000 history entries
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-1000:]
            
            self.save()
        except Exception as e:
            logger.error(f"Error adding to history: {e}")
    
    def get_user_history(self, chat_id: int, limit: int = 50) -> List[Dict]:
        """Get alert history for user"""
        user_alert_ids = {alert.id for alert in self.get_user_alerts(chat_id)}
        user_history = [h for h in self.alert_history if h['alert_id'] in user_alert_ids]
        return user_history[-limit:]
    
    def get_user_preferences(self, chat_id: int) -> Dict:
        """Get user preferences"""
        default_prefs = {
            'daily_report_enabled': True,
            'daily_report_time': '08:00',
            'mute_start': None,
            'mute_end': None,
            'alert_sound': True,
            'min_priority': 'low'
        }
        return self.user_preferences.get(chat_id, default_prefs)
    
    def update_user_preferences(self, chat_id: int, **kwargs) -> bool:
        """Update user preferences"""
        try:
            if chat_id not in self.user_preferences:
                self.user_preferences[chat_id] = self.get_user_preferences(chat_id)
            
            self.user_preferences[chat_id].update(kwargs)
            self.save()
            return True
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return False
    
    def cleanup_expired(self):
        """Remove expired alerts"""
        try:
            current_time = datetime.utcnow()
            expired_ids = [
                alert_id for alert_id, alert in self.alerts.items()
                if alert.expires_at and alert.expires_at < current_time
            ]
            
            for alert_id in expired_ids:
                del self.alerts[alert_id]
            
            if expired_ids:
                logger.info(f"Cleaned up {len(expired_ids)} expired alerts")
                self.save()
        except Exception as e:
            logger.error(f"Error cleaning up alerts: {e}")