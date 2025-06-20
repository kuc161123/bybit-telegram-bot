#!/usr/bin/env python3
"""
Sentiment Data Cache
Fast access to recent sentiment analysis results
"""
import logging
import json
import time
import pickle
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class SentimentCache:
    def __init__(self, cache_dir: str = "cache"):
        """Initialize sentiment cache"""
        self.cache_dir = cache_dir
        self.ensure_cache_dir()
        
        # Cache file paths
        self.aggregated_sentiment_file = os.path.join(cache_dir, "aggregated_sentiment.json")
        self.platform_sentiments_file = os.path.join(cache_dir, "platform_sentiments.json")
        self.collection_history_file = os.path.join(cache_dir, "collection_history.json")
        
        # Cache TTL settings
        self.cache_ttl = {
            "aggregated_sentiment": 1800,  # 30 minutes
            "platform_sentiments": 3600,   # 1 hour
            "collection_history": 86400    # 24 hours
        }
        
        # In-memory cache
        self.memory_cache = {}
        self.cache_timestamps = {}
    
    def ensure_cache_dir(self):
        """Ensure cache directory exists"""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Could not create cache directory: {e}")
    
    async def store_aggregated_sentiment(self, sentiment_data: Dict[str, Any]) -> bool:
        """Store aggregated sentiment data"""
        try:
            # Add cache timestamp
            sentiment_data["cache_timestamp"] = time.time()
            
            # Store in memory cache
            self.memory_cache["aggregated_sentiment"] = sentiment_data
            self.cache_timestamps["aggregated_sentiment"] = time.time()
            
            # Store in file cache
            with open(self.aggregated_sentiment_file, 'w') as f:
                json.dump(sentiment_data, f, indent=2, default=str)
            
            logger.debug("Aggregated sentiment stored in cache")
            return True
            
        except Exception as e:
            logger.error(f"Error storing aggregated sentiment: {e}")
            return False
    
    async def get_latest_aggregated_sentiment(self) -> Optional[Dict[str, Any]]:
        """Get latest aggregated sentiment from cache"""
        try:
            # Check memory cache first
            if "aggregated_sentiment" in self.memory_cache:
                cache_time = self.cache_timestamps.get("aggregated_sentiment", 0)
                if time.time() - cache_time < self.cache_ttl["aggregated_sentiment"]:
                    return self.memory_cache["aggregated_sentiment"]
            
            # Check file cache
            if os.path.exists(self.aggregated_sentiment_file):
                with open(self.aggregated_sentiment_file, 'r') as f:
                    data = json.load(f)
                
                # Check if cache is still valid
                cache_timestamp = data.get("cache_timestamp", 0)
                if time.time() - cache_timestamp < self.cache_ttl["aggregated_sentiment"]:
                    # Update memory cache
                    self.memory_cache["aggregated_sentiment"] = data
                    self.cache_timestamps["aggregated_sentiment"] = time.time()
                    return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving aggregated sentiment from cache: {e}")
            return None
    
    async def store_platform_sentiments(self, platform_sentiments: Dict[str, Any]) -> bool:
        """Store platform-specific sentiment data"""
        try:
            # Add cache timestamp
            cache_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "cache_timestamp": time.time(),
                "platform_sentiments": platform_sentiments
            }
            
            # Store in memory cache
            self.memory_cache["platform_sentiments"] = cache_data
            self.cache_timestamps["platform_sentiments"] = time.time()
            
            # Store in file cache
            with open(self.platform_sentiments_file, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            
            logger.debug("Platform sentiments stored in cache")
            return True
            
        except Exception as e:
            logger.error(f"Error storing platform sentiments: {e}")
            return False
    
    async def get_platform_sentiments(self) -> Optional[Dict[str, Any]]:
        """Get platform sentiments from cache"""
        try:
            # Check memory cache first
            if "platform_sentiments" in self.memory_cache:
                cache_time = self.cache_timestamps.get("platform_sentiments", 0)
                if time.time() - cache_time < self.cache_ttl["platform_sentiments"]:
                    return self.memory_cache["platform_sentiments"]
            
            # Check file cache
            if os.path.exists(self.platform_sentiments_file):
                with open(self.platform_sentiments_file, 'r') as f:
                    data = json.load(f)
                
                # Check if cache is still valid
                cache_timestamp = data.get("cache_timestamp", 0)
                if time.time() - cache_timestamp < self.cache_ttl["platform_sentiments"]:
                    # Update memory cache
                    self.memory_cache["platform_sentiments"] = data
                    self.cache_timestamps["platform_sentiments"] = time.time()
                    return data
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving platform sentiments from cache: {e}")
            return None
    
    async def store_collection_result(self, collection_result: Dict[str, Any]) -> bool:
        """Store complete collection cycle result"""
        try:
            # Load existing history
            history = await self.get_collection_history() or []
            
            # Add new result
            history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "cache_timestamp": time.time(),
                "result": collection_result
            })
            
            # Keep only last 24 collection cycles (6 hours × 4 = 24 hours × 4 = 96 hours = 4 days)
            history = history[-24:]
            
            # Store in file cache
            with open(self.collection_history_file, 'w') as f:
                json.dump(history, f, indent=2, default=str)
            
            # Update memory cache
            self.memory_cache["collection_history"] = history
            self.cache_timestamps["collection_history"] = time.time()
            
            logger.debug("Collection result stored in history")
            return True
            
        except Exception as e:
            logger.error(f"Error storing collection result: {e}")
            return False
    
    async def get_collection_history(self) -> Optional[List[Dict[str, Any]]]:
        """Get collection history from cache"""
        try:
            # Check memory cache first
            if "collection_history" in self.memory_cache:
                cache_time = self.cache_timestamps.get("collection_history", 0)
                if time.time() - cache_time < self.cache_ttl["collection_history"]:
                    return self.memory_cache["collection_history"]
            
            # Check file cache
            if os.path.exists(self.collection_history_file):
                with open(self.collection_history_file, 'r') as f:
                    data = json.load(f)
                
                # Update memory cache
                self.memory_cache["collection_history"] = data
                self.cache_timestamps["collection_history"] = time.time()
                return data
            
            return []
            
        except Exception as e:
            logger.error(f"Error retrieving collection history from cache: {e}")
            return []
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            stats = {
                "memory_cache_items": len(self.memory_cache),
                "cache_files": {},
                "cache_ages": {}
            }
            
            # Check file cache stats
            cache_files = [
                ("aggregated_sentiment", self.aggregated_sentiment_file),
                ("platform_sentiments", self.platform_sentiments_file),
                ("collection_history", self.collection_history_file)
            ]
            
            for cache_name, file_path in cache_files:
                if os.path.exists(file_path):
                    stat = os.stat(file_path)
                    stats["cache_files"][cache_name] = {
                        "exists": True,
                        "size_bytes": stat.st_size,
                        "modified_time": stat.st_mtime,
                        "age_seconds": time.time() - stat.st_mtime
                    }
                else:
                    stats["cache_files"][cache_name] = {"exists": False}
                
                # Memory cache age
                if cache_name in self.cache_timestamps:
                    cache_age = time.time() - self.cache_timestamps[cache_name]
                    stats["cache_ages"][cache_name] = cache_age
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {"error": str(e)}
    
    async def clear_cache(self, cache_type: Optional[str] = None) -> bool:
        """Clear cache (specific type or all)"""
        try:
            if cache_type:
                # Clear specific cache
                if cache_type in self.memory_cache:
                    del self.memory_cache[cache_type]
                
                if cache_type in self.cache_timestamps:
                    del self.cache_timestamps[cache_type]
                
                # Remove file cache
                file_map = {
                    "aggregated_sentiment": self.aggregated_sentiment_file,
                    "platform_sentiments": self.platform_sentiments_file,
                    "collection_history": self.collection_history_file
                }
                
                if cache_type in file_map and os.path.exists(file_map[cache_type]):
                    os.remove(file_map[cache_type])
                
                logger.info(f"Cleared {cache_type} cache")
            else:
                # Clear all caches
                self.memory_cache.clear()
                self.cache_timestamps.clear()
                
                # Remove all cache files
                for file_path in [self.aggregated_sentiment_file, 
                                self.platform_sentiments_file, 
                                self.collection_history_file]:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                
                logger.info("Cleared all caches")
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return False
    
    async def is_cache_valid(self, cache_type: str) -> bool:
        """Check if specific cache is valid (not expired)"""
        try:
            if cache_type in self.cache_timestamps:
                cache_age = time.time() - self.cache_timestamps[cache_type]
                ttl = self.cache_ttl.get(cache_type, 3600)
                return cache_age < ttl
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking cache validity: {e}")
            return False