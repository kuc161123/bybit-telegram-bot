#!/usr/bin/env python3
"""
Social Media Data Processors
Advanced sentiment analysis and trend detection
"""

from .sentiment_analyzer import SentimentAnalyzer
from .trend_detector import TrendDetector
from .data_aggregator import DataAggregator
from .signal_generator import SignalGenerator

__all__ = [
    "SentimentAnalyzer",
    "TrendDetector",
    "DataAggregator", 
    "SignalGenerator"
]