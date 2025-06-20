#!/usr/bin/env python3
"""
Enhanced Multi-Platform Social Media Sentiment Analysis System
Optimized for 6-hour updates within free API limits
"""

__version__ = "1.0.0"
__author__ = "Trading Bot Enhanced AI System"

# Export main components
from .collectors import RedditCollector, TwitterCollector, YouTubeCollector, DiscordCollector
from .processors import SentimentAnalyzer, TrendDetector, DataAggregator
from .storage import SentimentCache, HistoricalStorage
from .dashboard import SentimentWidgets

__all__ = [
    "RedditCollector",
    "TwitterCollector", 
    "YouTubeCollector",
    "DiscordCollector",
    "SentimentAnalyzer",
    "TrendDetector",
    "DataAggregator",
    "SentimentCache",
    "HistoricalStorage",
    "SentimentWidgets"
]