#!/usr/bin/env python3
"""
Historical Storage for Social Media Sentiment
Manages long-term sentiment data storage and analysis
"""
import logging
import json
import os
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class HistoricalStorage:
    def __init__(self, storage_dir: str = "cache/historical"):
        """Initialize historical storage"""
        self.storage_dir = storage_dir
        self.ensure_storage_dir()
        
        # Storage files
        self.daily_aggregates_file = os.path.join(storage_dir, "daily_aggregates.json")
        self.weekly_aggregates_file = os.path.join(storage_dir, "weekly_aggregates.json")
        self.sentiment_history_file = os.path.join(storage_dir, "sentiment_history.json")
        self.trend_history_file = os.path.join(storage_dir, "trend_history.json")
        
        # Retention settings
        self.retention_days = {
            'daily_aggregates': 30,     # Keep 30 days of daily data
            'weekly_aggregates': 365,   # Keep 1 year of weekly data
            'sentiment_history': 7,     # Keep 7 days of detailed history
            'trend_history': 14         # Keep 14 days of trend history
        }
    
    def ensure_storage_dir(self):
        """Ensure storage directory exists"""
        try:
            os.makedirs(self.storage_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Could not create storage directory: {e}")
    
    async def store_daily_aggregate(self, date: str, sentiment_data: Dict[str, Any]) -> bool:
        """Store daily sentiment aggregate"""
        try:
            # Load existing data
            daily_data = self._load_json_file(self.daily_aggregates_file, {})
            
            # Add new data
            daily_data[date] = {
                'date': date,
                'timestamp': time.time(),
                'sentiment_data': sentiment_data,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Clean old data
            cutoff_date = (datetime.utcnow() - timedelta(days=self.retention_days['daily_aggregates'])).strftime('%Y-%m-%d')
            daily_data = {k: v for k, v in daily_data.items() if k >= cutoff_date}
            
            # Save data
            return self._save_json_file(self.daily_aggregates_file, daily_data)
            
        except Exception as e:
            logger.error(f"Error storing daily aggregate: {e}")
            return False
    
    async def store_weekly_aggregate(self, week: str, sentiment_data: Dict[str, Any]) -> bool:
        """Store weekly sentiment aggregate"""
        try:
            # Load existing data
            weekly_data = self._load_json_file(self.weekly_aggregates_file, {})
            
            # Add new data
            weekly_data[week] = {
                'week': week,
                'timestamp': time.time(),
                'sentiment_data': sentiment_data,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Clean old data
            cutoff_date = (datetime.utcnow() - timedelta(days=self.retention_days['weekly_aggregates'])).strftime('%Y-W%U')
            weekly_data = {k: v for k, v in weekly_data.items() if k >= cutoff_date}
            
            # Save data
            return self._save_json_file(self.weekly_aggregates_file, weekly_data)
            
        except Exception as e:
            logger.error(f"Error storing weekly aggregate: {e}")
            return False
    
    async def store_sentiment_history(self, sentiment_data: Dict[str, Any]) -> bool:
        """Store detailed sentiment history"""
        try:
            # Load existing data
            history_data = self._load_json_file(self.sentiment_history_file, [])
            
            # Add new entry
            entry = {
                'timestamp': time.time(),
                'datetime': datetime.utcnow().isoformat(),
                'sentiment_data': sentiment_data
            }
            
            history_data.append(entry)
            
            # Clean old data
            cutoff_time = time.time() - (self.retention_days['sentiment_history'] * 24 * 3600)
            history_data = [entry for entry in history_data if entry.get('timestamp', 0) > cutoff_time]
            
            # Keep only last 1000 entries to prevent file size issues
            history_data = history_data[-1000:]
            
            # Save data
            return self._save_json_file(self.sentiment_history_file, history_data)
            
        except Exception as e:
            logger.error(f"Error storing sentiment history: {e}")
            return False
    
    async def store_trend_history(self, trend_data: Dict[str, Any]) -> bool:
        """Store trend history"""
        try:
            # Load existing data
            trend_history = self._load_json_file(self.trend_history_file, [])
            
            # Add new entry
            entry = {
                'timestamp': time.time(),
                'datetime': datetime.utcnow().isoformat(),
                'trend_data': trend_data
            }
            
            trend_history.append(entry)
            
            # Clean old data
            cutoff_time = time.time() - (self.retention_days['trend_history'] * 24 * 3600)
            trend_history = [entry for entry in trend_history if entry.get('timestamp', 0) > cutoff_time]
            
            # Keep only last 500 entries
            trend_history = trend_history[-500:]
            
            # Save data
            return self._save_json_file(self.trend_history_file, trend_history)
            
        except Exception as e:
            logger.error(f"Error storing trend history: {e}")
            return False
    
    async def get_daily_aggregates(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily aggregates for the last N days"""
        try:
            daily_data = self._load_json_file(self.daily_aggregates_file, {})
            
            # Get recent dates
            cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
            recent_data = {k: v for k, v in daily_data.items() if k >= cutoff_date}
            
            # Convert to list and sort by date
            result = list(recent_data.values())
            result.sort(key=lambda x: x.get('date', ''))
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting daily aggregates: {e}")
            return []
    
    async def get_sentiment_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get sentiment history for the last N hours"""
        try:
            history_data = self._load_json_file(self.sentiment_history_file, [])
            
            # Filter by time
            cutoff_time = time.time() - (hours * 3600)
            recent_data = [entry for entry in history_data if entry.get('timestamp', 0) > cutoff_time]
            
            # Sort by timestamp
            recent_data.sort(key=lambda x: x.get('timestamp', 0))
            
            return recent_data
            
        except Exception as e:
            logger.error(f"Error getting sentiment history: {e}")
            return []
    
    async def get_trend_history(self, hours: int = 48) -> List[Dict[str, Any]]:
        """Get trend history for the last N hours"""
        try:
            trend_history = self._load_json_file(self.trend_history_file, [])
            
            # Filter by time
            cutoff_time = time.time() - (hours * 3600)
            recent_data = [entry for entry in trend_history if entry.get('timestamp', 0) > cutoff_time]
            
            # Sort by timestamp
            recent_data.sort(key=lambda x: x.get('timestamp', 0))
            
            return recent_data
            
        except Exception as e:
            logger.error(f"Error getting trend history: {e}")
            return []
    
    async def analyze_sentiment_trends(self, days: int = 7) -> Dict[str, Any]:
        """Analyze sentiment trends over time"""
        try:
            # Get historical data
            daily_aggregates = await self.get_daily_aggregates(days)
            
            if len(daily_aggregates) < 2:
                return {
                    'trend_direction': 'INSUFFICIENT_DATA',
                    'trend_strength': 0,
                    'average_sentiment': 50,
                    'volatility': 0,
                    'data_points': len(daily_aggregates)
                }
            
            # Extract sentiment scores
            sentiment_scores = []
            dates = []
            
            for day_data in daily_aggregates:
                sentiment_data = day_data.get('sentiment_data', {})
                score = sentiment_data.get('sentiment_score', 50)
                sentiment_scores.append(score)
                dates.append(day_data.get('date', ''))
            
            # Calculate trend metrics
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            
            # Simple linear trend calculation
            if len(sentiment_scores) >= 2:
                recent_avg = sum(sentiment_scores[-3:]) / len(sentiment_scores[-3:])
                early_avg = sum(sentiment_scores[:3]) / len(sentiment_scores[:3])
                trend_change = recent_avg - early_avg
                
                if trend_change > 5:
                    trend_direction = 'IMPROVING'
                elif trend_change < -5:
                    trend_direction = 'DECLINING'
                else:
                    trend_direction = 'STABLE'
                
                trend_strength = min(abs(trend_change) / 20, 1.0)  # Normalize to 0-1
            else:
                trend_direction = 'STABLE'
                trend_strength = 0
            
            # Calculate volatility
            if len(sentiment_scores) > 1:
                variance = sum((score - avg_sentiment) ** 2 for score in sentiment_scores) / len(sentiment_scores)
                volatility = min(variance / 100, 1.0)  # Normalize to 0-1
            else:
                volatility = 0
            
            return {
                'trend_direction': trend_direction,
                'trend_strength': trend_strength,
                'average_sentiment': avg_sentiment,
                'volatility': volatility,
                'data_points': len(sentiment_scores),
                'date_range': f"{dates[0]} to {dates[-1]}" if dates else "No data",
                'latest_sentiment': sentiment_scores[-1] if sentiment_scores else 50,
                'sentiment_range': {
                    'min': min(sentiment_scores) if sentiment_scores else 50,
                    'max': max(sentiment_scores) if sentiment_scores else 50
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment trends: {e}")
            return {
                'trend_direction': 'ERROR',
                'trend_strength': 0,
                'average_sentiment': 50,
                'volatility': 1.0,
                'data_points': 0,
                'error': str(e)
            }
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            stats = {
                'storage_directory': self.storage_dir,
                'files': {},
                'total_size_bytes': 0,
                'retention_settings': self.retention_days
            }
            
            # Check each storage file
            storage_files = [
                ('daily_aggregates', self.daily_aggregates_file),
                ('weekly_aggregates', self.weekly_aggregates_file),
                ('sentiment_history', self.sentiment_history_file),
                ('trend_history', self.trend_history_file)
            ]
            
            for file_type, file_path in storage_files:
                if os.path.exists(file_path):
                    file_stat = os.stat(file_path)
                    stats['files'][file_type] = {
                        'exists': True,
                        'size_bytes': file_stat.st_size,
                        'modified_time': file_stat.st_mtime,
                        'age_hours': (time.time() - file_stat.st_mtime) / 3600
                    }
                    stats['total_size_bytes'] += file_stat.st_size
                else:
                    stats['files'][file_type] = {'exists': False}
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {'error': str(e)}
    
    async def cleanup_old_data(self) -> Dict[str, Any]:
        """Clean up old data according to retention policies"""
        try:
            cleanup_results = {
                'daily_aggregates': 0,
                'weekly_aggregates': 0,
                'sentiment_history': 0,
                'trend_history': 0
            }
            
            # Clean daily aggregates
            daily_data = self._load_json_file(self.daily_aggregates_file, {})
            original_count = len(daily_data)
            cutoff_date = (datetime.utcnow() - timedelta(days=self.retention_days['daily_aggregates'])).strftime('%Y-%m-%d')
            daily_data = {k: v for k, v in daily_data.items() if k >= cutoff_date}
            cleanup_results['daily_aggregates'] = original_count - len(daily_data)
            self._save_json_file(self.daily_aggregates_file, daily_data)
            
            # Clean weekly aggregates
            weekly_data = self._load_json_file(self.weekly_aggregates_file, {})
            original_count = len(weekly_data)
            cutoff_date = (datetime.utcnow() - timedelta(days=self.retention_days['weekly_aggregates'])).strftime('%Y-W%U')
            weekly_data = {k: v for k, v in weekly_data.items() if k >= cutoff_date}
            cleanup_results['weekly_aggregates'] = original_count - len(weekly_data)
            self._save_json_file(self.weekly_aggregates_file, weekly_data)
            
            # Clean sentiment history
            history_data = self._load_json_file(self.sentiment_history_file, [])
            original_count = len(history_data)
            cutoff_time = time.time() - (self.retention_days['sentiment_history'] * 24 * 3600)
            history_data = [entry for entry in history_data if entry.get('timestamp', 0) > cutoff_time]
            cleanup_results['sentiment_history'] = original_count - len(history_data)
            self._save_json_file(self.sentiment_history_file, history_data)
            
            # Clean trend history
            trend_history = self._load_json_file(self.trend_history_file, [])
            original_count = len(trend_history)
            cutoff_time = time.time() - (self.retention_days['trend_history'] * 24 * 3600)
            trend_history = [entry for entry in trend_history if entry.get('timestamp', 0) > cutoff_time]
            cleanup_results['trend_history'] = original_count - len(trend_history)
            self._save_json_file(self.trend_history_file, trend_history)
            
            total_cleaned = sum(cleanup_results.values())
            logger.info(f"Cleanup completed: {total_cleaned} total entries removed")
            
            return cleanup_results
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return {'error': str(e)}
    
    def _load_json_file(self, file_path: str, default_value: Any) -> Any:
        """Load JSON file with error handling"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
            return default_value
        except Exception as e:
            logger.error(f"Error loading JSON file {file_path}: {e}")
            return default_value
    
    def _save_json_file(self, file_path: str, data: Any) -> bool:
        """Save JSON file with error handling"""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Error saving JSON file {file_path}: {e}")
            return False