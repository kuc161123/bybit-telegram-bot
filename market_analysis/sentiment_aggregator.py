#!/usr/bin/env python3
"""
Sentiment Aggregator
Integrates multiple real sentiment sources for enhanced market analysis
"""
import asyncio
import aiohttp
import logging
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import statistics

from utils.cache import async_cache

logger = logging.getLogger(__name__)

class SentimentSource(Enum):
    """Available sentiment data sources"""
    FEAR_GREED = "fear_greed"
    FUNDING_RATE = "funding_rate"
    OPEN_INTEREST = "open_interest"
    LONG_SHORT_RATIO = "long_short_ratio"
    SOCIAL_MEDIA = "social_media"
    NEWS_SENTIMENT = "news_sentiment"

@dataclass
class SentimentData:
    """Container for sentiment data from various sources"""
    source: SentimentSource
    value: float  # 0-100 scale
    label: str
    confidence: float  # 0-1 confidence in data
    timestamp: datetime
    raw_data: Optional[Dict] = None
    
@dataclass
class AggregatedSentiment:
    """Aggregated sentiment from all sources"""
    overall_score: float  # 0-100
    overall_label: str
    
    # Individual source scores
    fear_greed_score: Optional[float] = None
    funding_sentiment: Optional[float] = None
    oi_sentiment: Optional[float] = None
    long_short_sentiment: Optional[float] = None
    social_sentiment: Optional[float] = None
    
    # Metadata
    sources_used: List[str] = None
    confidence: float = 0.0
    timestamp: datetime = None
    
    # Detailed insights
    market_emotion: Optional[str] = None  # "Euphoria", "Greed", "Fear", "Panic"
    sentiment_trend: Optional[str] = None  # "Improving", "Deteriorating", "Stable"
    contrarian_signal: Optional[bool] = None  # True if extreme sentiment suggests reversal

class SentimentAggregator:
    """Aggregates sentiment from multiple real-time sources"""
    
    def __init__(self):
        self.session = None
        self.cache_ttl = 60   # 1 minute for real-time updates
        self.sentiment_history = {}  # Symbol -> List of historical sentiments
        
        # API endpoints
        self.fear_greed_url = "https://api.alternative.me/fng/"
        self.coinglass_api = "https://api.coinglass.com/api"  # For funding, OI, long/short
        
        # Thresholds for sentiment interpretation
        self.sentiment_thresholds = {
            "extreme_fear": 20,
            "fear": 40,
            "neutral": 60,
            "greed": 80,
            "extreme_greed": 100
        }
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def get_aggregated_sentiment(
        self, 
        symbol: str = "BTCUSDT",
        include_social: bool = True
    ) -> AggregatedSentiment:
        """
        Get aggregated sentiment from all available sources
        
        Args:
            symbol: Trading symbol
            include_social: Whether to include social media sentiment
            
        Returns:
            AggregatedSentiment with combined analysis
        """
        try:
            # Ensure we have a session
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Collect sentiment from all sources
            tasks = [
                self._get_fear_greed_index(),
                self._get_funding_rate_sentiment(symbol),
                self._get_open_interest_sentiment(symbol),
                self._get_long_short_ratio_sentiment(symbol)
            ]
            
            if include_social:
                tasks.append(self._get_social_sentiment(symbol))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            sentiment_data = []
            fear_greed = None
            funding_sentiment = None
            oi_sentiment = None
            long_short_sentiment = None
            social_sentiment = None
            
            for i, result in enumerate(results):
                if isinstance(result, SentimentData):
                    sentiment_data.append(result)
                    
                    if i == 0:  # Fear & Greed
                        fear_greed = result.value
                    elif i == 1:  # Funding rate
                        funding_sentiment = result.value
                    elif i == 2:  # Open interest
                        oi_sentiment = result.value
                    elif i == 3:  # Long/short ratio
                        long_short_sentiment = result.value
                    elif i == 4:  # Social
                        social_sentiment = result.value
                else:
                    logger.debug(f"Sentiment source {i} failed: {result}")
            
            # Calculate aggregated sentiment
            overall_score, confidence = self._calculate_weighted_sentiment(sentiment_data)
            overall_label = self._get_sentiment_label(overall_score)
            
            # Determine market emotion
            market_emotion = self._determine_market_emotion(overall_score, sentiment_data)
            
            # Check sentiment trend
            sentiment_trend = await self._analyze_sentiment_trend(symbol, overall_score)
            
            # Check for contrarian signals
            contrarian_signal = self._check_contrarian_signal(overall_score, sentiment_data)
            
            # Get sources used
            sources_used = [data.source.value for data in sentiment_data]
            
            return AggregatedSentiment(
                overall_score=overall_score,
                overall_label=overall_label,
                fear_greed_score=fear_greed,
                funding_sentiment=funding_sentiment,
                oi_sentiment=oi_sentiment,
                long_short_sentiment=long_short_sentiment,
                social_sentiment=social_sentiment,
                sources_used=sources_used,
                confidence=confidence,
                timestamp=datetime.now(),
                market_emotion=market_emotion,
                sentiment_trend=sentiment_trend,
                contrarian_signal=contrarian_signal
            )
            
        except Exception as e:
            logger.error(f"Error aggregating sentiment: {e}")
            # Return neutral sentiment on error
            return AggregatedSentiment(
                overall_score=50.0,
                overall_label="Neutral",
                sources_used=[],
                confidence=0.0,
                timestamp=datetime.now()
            )
    
    @async_cache(ttl_seconds=300)
    async def _get_fear_greed_index(self) -> Optional[SentimentData]:
        """Get the Crypto Fear & Greed Index"""
        try:
            async with self.session.get(
                self.fear_greed_url,
                params={"limit": 1, "format": "json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        fg_data = data["data"][0]
                        value = float(fg_data["value"])
                        
                        # Convert to our 0-100 scale (already in this format)
                        return SentimentData(
                            source=SentimentSource.FEAR_GREED,
                            value=value,
                            label=fg_data["value_classification"],
                            confidence=0.9,  # High confidence in this index
                            timestamp=datetime.now(),
                            raw_data=fg_data
                        )
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed Index: {e}")
        
        return None
    
    async def _get_funding_rate_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Calculate sentiment from funding rates"""
        try:
            # Get funding rate from Bybit
            from clients.bybit_client import bybit_client
            
            # Get current funding rate
            ticker_response = bybit_client.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            if ticker_response.get("retCode") == 0:
                ticker_data = ticker_response.get("result", {}).get("list", [])
                if ticker_data:
                    funding_rate = float(ticker_data[0].get("fundingRate", 0))
                    
                    # Convert funding rate to sentiment
                    # Positive funding = longs pay shorts = bullish sentiment
                    # Negative funding = shorts pay longs = bearish sentiment
                    
                    # Scale: -0.1% to +0.1% funding rate -> 0-100 sentiment
                    # Extreme rates beyond this range are capped
                    
                    if funding_rate > 0:
                        # Bullish - scale 0 to 0.001 (0.1%) -> 50 to 100
                        sentiment = 50 + min(funding_rate / 0.001, 1) * 50
                    else:
                        # Bearish - scale 0 to -0.001 (-0.1%) -> 50 to 0
                        sentiment = 50 + max(funding_rate / 0.001, -1) * 50
                    
                    # Determine label
                    if funding_rate > 0.0005:  # > 0.05%
                        label = "Very Bullish"
                    elif funding_rate > 0.0001:  # > 0.01%
                        label = "Bullish"
                    elif funding_rate < -0.0005:  # < -0.05%
                        label = "Very Bearish"
                    elif funding_rate < -0.0001:  # < -0.01%
                        label = "Bearish"
                    else:
                        label = "Neutral"
                    
                    return SentimentData(
                        source=SentimentSource.FUNDING_RATE,
                        value=sentiment,
                        label=label,
                        confidence=0.85,
                        timestamp=datetime.now(),
                        raw_data={"funding_rate": funding_rate}
                    )
                    
        except Exception as e:
            logger.error(f"Error calculating funding rate sentiment: {e}")
        
        return None
    
    async def _get_open_interest_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Calculate sentiment from open interest changes"""
        try:
            # Get open interest data from Bybit
            from clients.bybit_client import bybit_client
            
            # Get current open interest
            oi_response = bybit_client.get_open_interest(
                category="linear",
                symbol=symbol,
                intervalTime="5min",
                limit=288  # Last 24 hours
            )
            
            if oi_response.get("retCode") == 0:
                oi_data = oi_response.get("result", {}).get("list", [])
                
                if len(oi_data) >= 2:
                    # Calculate 24h change
                    current_oi = float(oi_data[0]["openInterest"])
                    past_oi = float(oi_data[-1]["openInterest"])
                    
                    if past_oi > 0:
                        oi_change_pct = ((current_oi - past_oi) / past_oi) * 100
                        
                        # Interpret OI changes
                        # Rising OI + Rising price = Bullish (new longs)
                        # Rising OI + Falling price = Bearish (new shorts)
                        # Falling OI = Position closing (neutral to bearish)
                        
                        # Get price change (simplified - assumes we have it)
                        price_change = 0  # Would get from ticker data
                        
                        if oi_change_pct > 10:  # Significant increase
                            if price_change > 0:
                                sentiment = 70  # Bullish - new longs
                                label = "Bullish (Rising OI)"
                            else:
                                sentiment = 30  # Bearish - new shorts
                                label = "Bearish (Rising OI)"
                        elif oi_change_pct < -10:  # Significant decrease
                            sentiment = 40  # Slightly bearish - positions closing
                            label = "Cautious (Falling OI)"
                        else:
                            sentiment = 50
                            label = "Neutral OI"
                        
                        return SentimentData(
                            source=SentimentSource.OPEN_INTEREST,
                            value=sentiment,
                            label=label,
                            confidence=0.7,
                            timestamp=datetime.now(),
                            raw_data={
                                "oi_change_pct": oi_change_pct,
                                "current_oi": current_oi
                            }
                        )
                        
        except Exception as e:
            logger.error(f"Error calculating open interest sentiment: {e}")
        
        return None
    
    async def _get_long_short_ratio_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Calculate sentiment from long/short ratio"""
        try:
            # This would typically come from an external API like Coinglass
            # For now, we'll use a mock implementation
            # In production, integrate with actual data provider
            
            # Mock data - replace with actual API call
            long_ratio = 52  # % of positions that are long
            short_ratio = 48  # % of positions that are short
            
            # Calculate sentiment
            # High long ratio = crowded long = potential bearish (contrarian)
            # High short ratio = crowded short = potential bullish (contrarian)
            
            if long_ratio > 70:
                sentiment = 30  # Very crowded long - bearish
                label = "Overcrowded Long"
            elif long_ratio > 60:
                sentiment = 40  # Crowded long - slightly bearish
                label = "Crowded Long"
            elif short_ratio > 70:
                sentiment = 70  # Very crowded short - bullish
                label = "Overcrowded Short"
            elif short_ratio > 60:
                sentiment = 60  # Crowded short - slightly bullish
                label = "Crowded Short"
            else:
                sentiment = 50  # Balanced
                label = "Balanced L/S"
            
            return SentimentData(
                source=SentimentSource.LONG_SHORT_RATIO,
                value=sentiment,
                label=label,
                confidence=0.6,  # Lower confidence for mock data
                timestamp=datetime.now(),
                raw_data={
                    "long_ratio": long_ratio,
                    "short_ratio": short_ratio
                }
            )
            
        except Exception as e:
            logger.error(f"Error calculating long/short ratio sentiment: {e}")
        
        return None
    
    async def _get_social_sentiment(self, symbol: str) -> Optional[SentimentData]:
        """Get social media sentiment if available"""
        try:
            # Check if social sentiment is available
            from social_media.integration import social_media_integration
            
            if social_media_integration.is_initialized:
                base_symbol = symbol.replace('USDT', '')
                sentiment_data = await social_media_integration.get_symbol_sentiment(base_symbol)
                
                if sentiment_data and 'overall_score' in sentiment_data:
                    return SentimentData(
                        source=SentimentSource.SOCIAL_MEDIA,
                        value=float(sentiment_data['overall_score']),
                        label=sentiment_data.get('sentiment_label', 'Neutral'),
                        confidence=sentiment_data.get('confidence', 0.5),
                        timestamp=datetime.now(),
                        raw_data=sentiment_data
                    )
        except ImportError:
            logger.debug("Social media integration not available")
        except Exception as e:
            logger.error(f"Error getting social sentiment: {e}")
        
        return None
    
    def _calculate_weighted_sentiment(self, sentiment_data: List[SentimentData]) -> Tuple[float, float]:
        """Calculate weighted average sentiment with confidence"""
        if not sentiment_data:
            return 50.0, 0.0
        
        # Define weights for each source
        source_weights = {
            SentimentSource.FEAR_GREED: 0.25,
            SentimentSource.FUNDING_RATE: 0.30,
            SentimentSource.OPEN_INTEREST: 0.20,
            SentimentSource.LONG_SHORT_RATIO: 0.15,
            SentimentSource.SOCIAL_MEDIA: 0.10
        }
        
        total_weight = 0
        weighted_sum = 0
        confidence_sum = 0
        
        for data in sentiment_data:
            weight = source_weights.get(data.source, 0.1)
            adjusted_weight = weight * data.confidence
            
            weighted_sum += data.value * adjusted_weight
            confidence_sum += data.confidence * weight
            total_weight += adjusted_weight
        
        if total_weight > 0:
            overall_score = weighted_sum / total_weight
            overall_confidence = confidence_sum / sum(source_weights.get(d.source, 0.1) for d in sentiment_data)
        else:
            overall_score = 50.0
            overall_confidence = 0.0
        
        return overall_score, overall_confidence
    
    def _get_sentiment_label(self, score: float) -> str:
        """Get sentiment label from score"""
        if score < self.sentiment_thresholds["extreme_fear"]:
            return "Extreme Fear"
        elif score < self.sentiment_thresholds["fear"]:
            return "Fear"
        elif score < self.sentiment_thresholds["neutral"]:
            return "Neutral"
        elif score < self.sentiment_thresholds["greed"]:
            return "Greed"
        else:
            return "Extreme Greed"
    
    def _determine_market_emotion(self, overall_score: float, 
                                sentiment_data: List[SentimentData]) -> str:
        """Determine the dominant market emotion"""
        # Check for extreme readings
        extreme_count = sum(1 for d in sentiment_data 
                          if d.value < 20 or d.value > 80)
        
        if overall_score > 85:
            return "Euphoria" if extreme_count >= 2 else "Strong Greed"
        elif overall_score > 70:
            return "Greed"
        elif overall_score > 60:
            return "Optimism"
        elif overall_score > 40:
            return "Uncertainty"
        elif overall_score > 30:
            return "Anxiety"
        elif overall_score > 15:
            return "Fear"
        else:
            return "Panic" if extreme_count >= 2 else "Extreme Fear"
    
    async def _analyze_sentiment_trend(self, symbol: str, current_score: float) -> str:
        """Analyze sentiment trend over time"""
        # Store current sentiment
        if symbol not in self.sentiment_history:
            self.sentiment_history[symbol] = []
        
        self.sentiment_history[symbol].append({
            "score": current_score,
            "timestamp": datetime.now()
        })
        
        # Keep only last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        self.sentiment_history[symbol] = [
            s for s in self.sentiment_history[symbol]
            if s["timestamp"] > cutoff
        ]
        
        # Need at least 3 data points for trend
        if len(self.sentiment_history[symbol]) < 3:
            return "Insufficient Data"
        
        # Calculate trend
        recent_scores = [s["score"] for s in self.sentiment_history[symbol][-10:]]
        
        if len(recent_scores) >= 2:
            avg_change = (recent_scores[-1] - recent_scores[0]) / len(recent_scores)
            
            if avg_change > 2:
                return "Rapidly Improving"
            elif avg_change > 0.5:
                return "Improving"
            elif avg_change < -2:
                return "Rapidly Deteriorating"
            elif avg_change < -0.5:
                return "Deteriorating"
            else:
                return "Stable"
        
        return "Stable"
    
    def _check_contrarian_signal(self, overall_score: float,
                                sentiment_data: List[SentimentData]) -> bool:
        """Check if extreme sentiment suggests contrarian opportunity"""
        # Extreme sentiment often precedes reversals
        if overall_score < 15 or overall_score > 85:
            # Check if multiple sources confirm extreme
            extreme_sources = sum(1 for d in sentiment_data 
                                if d.value < 20 or d.value > 80)
            return extreme_sources >= 2
        
        # Check for divergences
        if sentiment_data:
            values = [d.value for d in sentiment_data]
            if len(values) >= 2:
                # High divergence between sources can signal opportunity
                divergence = max(values) - min(values)
                return divergence > 40
        
        return False

# Global instance
sentiment_aggregator = SentimentAggregator()