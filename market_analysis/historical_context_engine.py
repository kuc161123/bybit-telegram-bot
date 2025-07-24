#!/usr/bin/env python3
"""
Historical Context Engine
Provides rich historical context for AI analysis including patterns, correlations, and market memory
"""
import asyncio
import logging
import pickle
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import statistics
import numpy as np

from utils.cache import async_cache

logger = logging.getLogger(__name__)

@dataclass
class HistoricalPattern:
    """Historical pattern occurrence"""
    pattern_name: str
    pattern_type: str  # "chart", "candlestick", "market_regime"
    occurrence_date: datetime
    market_context: Dict[str, Any]
    outcome: str  # "bullish", "bearish", "neutral"
    success_rate: float  # How often this pattern worked
    time_to_target: Optional[int] = None  # Days to reach target
    target_achieved: Optional[bool] = None

@dataclass
class MarketCorrelation:
    """Market correlation data"""
    primary_symbol: str
    correlated_symbol: str
    correlation_strength: float  # -1 to 1
    correlation_period: int  # Days
    last_updated: datetime

@dataclass
class HistoricalContext:
    """Complete historical context for AI analysis"""
    symbol: str
    
    # Pattern history
    similar_patterns: List[HistoricalPattern]
    pattern_success_rates: Dict[str, float]
    
    # Market memory
    recent_similar_conditions: List[Dict[str, Any]]
    historical_outcomes: Dict[str, List[float]]  # Outcomes by condition type
    
    # Correlations
    market_correlations: List[MarketCorrelation]
    sector_context: Dict[str, Any]
    
    # Seasonal patterns
    seasonal_trends: Dict[str, float]  # Month/week -> avg performance
    time_of_day_patterns: Dict[str, float]  # Hour -> avg performance
    
    # Volatility context
    current_vs_historical_volatility: float
    volatility_regime: str  # "low", "normal", "high", "extreme"
    
    # Sentiment context
    sentiment_persistence: float  # How long current sentiment typically lasts
    sentiment_reversal_probability: float
    
    # Market structure
    support_resistance_strength: Dict[str, float]  # Based on historical tests
    volume_profile_significance: float
    
    # AI enhancement data
    confidence_boosters: List[str]
    risk_factors: List[str]
    success_probability: float
    
    context_quality: float  # 0-100 quality of historical data

class HistoricalContextEngine:
    """Manages historical market context for enhanced AI analysis"""
    
    def __init__(self):
        self.context_cache = {}
        self.cache_ttl = 3600  # 1 hour cache for historical context
        
        # Historical data storage
        self.pattern_history = defaultdict(list)  # symbol -> patterns
        self.market_memory = defaultdict(deque)   # symbol -> market states
        self.correlation_matrix = {}              # symbol pairs -> correlation
        
        # Configuration
        self.max_history_days = 365  # Keep 1 year of history
        self.pattern_memory_size = 100  # Max patterns per symbol
        self.market_memory_size = 1000  # Max market states per symbol
        
        # Load existing historical data
        self._load_historical_data()
        
    async def get_historical_context(
        self,
        symbol: str,
        current_market_data: Dict[str, Any],
        technical_indicators: Dict[str, Any],
        detected_patterns: List[Any],
        sentiment_data: Optional[Dict[str, Any]] = None
    ) -> HistoricalContext:
        """
        Generate comprehensive historical context for AI analysis
        
        Args:
            symbol: Trading symbol
            current_market_data: Current market conditions
            technical_indicators: Technical analysis results
            detected_patterns: Recently detected patterns
            sentiment_data: Current sentiment information
            
        Returns:
            HistoricalContext with relevant historical information
        """
        try:
            cache_key = f"historical_context_{symbol}_{datetime.now().hour}"
            
            if cache_key in self.context_cache:
                cached_time, cached_context = self.context_cache[cache_key]
                if (datetime.now() - cached_time).seconds < self.cache_ttl:
                    return cached_context
            
            # Build comprehensive historical context
            similar_patterns = await self._find_similar_patterns(symbol, detected_patterns)
            pattern_success_rates = self._calculate_pattern_success_rates(symbol, detected_patterns)
            
            recent_similar_conditions = await self._find_similar_market_conditions(
                symbol, current_market_data, technical_indicators
            )
            
            historical_outcomes = self._analyze_historical_outcomes(symbol, current_market_data)
            
            market_correlations = await self._get_market_correlations(symbol)
            sector_context = await self._get_sector_context(symbol)
            
            seasonal_trends = self._analyze_seasonal_patterns(symbol)
            time_patterns = self._analyze_time_patterns(symbol)
            
            volatility_context = self._analyze_volatility_context(symbol, current_market_data)
            
            sentiment_context = self._analyze_sentiment_context(symbol, sentiment_data)
            
            support_resistance = self._analyze_level_strength(symbol, technical_indicators)
            volume_significance = self._analyze_volume_significance(symbol, current_market_data)
            
            # Generate AI enhancement data
            confidence_boosters, risk_factors = self._identify_confidence_factors(
                similar_patterns, recent_similar_conditions, pattern_success_rates
            )
            
            success_probability = self._calculate_success_probability(
                pattern_success_rates, historical_outcomes, volatility_context
            )
            
            context_quality = self._assess_context_quality(
                similar_patterns, recent_similar_conditions, len(self.pattern_history[symbol])
            )
            
            historical_context = HistoricalContext(
                symbol=symbol,
                similar_patterns=similar_patterns,
                pattern_success_rates=pattern_success_rates,
                recent_similar_conditions=recent_similar_conditions,
                historical_outcomes=historical_outcomes,
                market_correlations=market_correlations,
                sector_context=sector_context,
                seasonal_trends=seasonal_trends,
                time_of_day_patterns=time_patterns,
                current_vs_historical_volatility=volatility_context.get("relative_volatility", 1.0),
                volatility_regime=volatility_context.get("regime", "normal"),
                sentiment_persistence=sentiment_context.get("persistence", 0.5),
                sentiment_reversal_probability=sentiment_context.get("reversal_prob", 0.3),
                support_resistance_strength=support_resistance,
                volume_profile_significance=volume_significance,
                confidence_boosters=confidence_boosters,
                risk_factors=risk_factors,
                success_probability=success_probability,
                context_quality=context_quality
            )
            
            # Cache the result
            self.context_cache[cache_key] = (datetime.now(), historical_context)
            
            # Update historical records
            await self._update_historical_records(symbol, current_market_data, technical_indicators)
            
            return historical_context
            
        except Exception as e:
            logger.error(f"Error generating historical context: {e}")
            return self._get_fallback_context(symbol)
    
    async def _find_similar_patterns(
        self, 
        symbol: str, 
        current_patterns: List[Any]
    ) -> List[HistoricalPattern]:
        """Find historically similar patterns"""
        similar_patterns = []
        
        try:
            historical_patterns = self.pattern_history.get(symbol, [])
            
            for current_pattern in current_patterns:
                if hasattr(current_pattern, 'pattern_name'):
                    pattern_name = current_pattern.pattern_name
                    
                    # Find matching historical patterns
                    matches = [
                        hp for hp in historical_patterns 
                        if hp.pattern_name == pattern_name
                        and (datetime.now() - hp.occurrence_date).days <= self.max_history_days
                    ]
                    
                    # Sort by recency and success
                    matches.sort(key=lambda x: (x.success_rate, -((datetime.now() - x.occurrence_date).days)))
                    
                    similar_patterns.extend(matches[:5])  # Take top 5 matches
                    
        except Exception as e:
            logger.debug(f"Error finding similar patterns: {e}")
        
        return similar_patterns
    
    def _calculate_pattern_success_rates(
        self, 
        symbol: str, 
        current_patterns: List[Any]
    ) -> Dict[str, float]:
        """Calculate success rates for detected patterns"""
        success_rates = {}
        
        try:
            historical_patterns = self.pattern_history.get(symbol, [])
            
            for current_pattern in current_patterns:
                if hasattr(current_pattern, 'pattern_name'):
                    pattern_name = current_pattern.pattern_name
                    
                    # Find all occurrences of this pattern
                    pattern_occurrences = [
                        hp for hp in historical_patterns 
                        if hp.pattern_name == pattern_name
                    ]
                    
                    if pattern_occurrences:
                        successful = sum(1 for p in pattern_occurrences if p.target_achieved)
                        success_rates[pattern_name] = successful / len(pattern_occurrences)
                    else:
                        # Default success rate for new patterns
                        success_rates[pattern_name] = 0.6  # Assume 60% for new patterns
                        
        except Exception as e:
            logger.debug(f"Error calculating pattern success rates: {e}")
        
        return success_rates
    
    async def _find_similar_market_conditions(
        self,
        symbol: str,
        current_market_data: Dict[str, Any],
        current_technicals: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find historically similar market conditions"""
        similar_conditions = []
        
        try:
            market_history = self.market_memory.get(symbol, deque())
            
            if not market_history:
                return similar_conditions
            
            # Current condition fingerprint
            current_fingerprint = self._create_market_fingerprint(
                current_market_data, current_technicals
            )
            
            # Find similar conditions
            for historical_state in market_history:
                historical_fingerprint = historical_state.get("fingerprint", {})
                
                similarity = self._calculate_fingerprint_similarity(
                    current_fingerprint, historical_fingerprint
                )
                
                if similarity > 0.7:  # 70% similarity threshold
                    similar_conditions.append({
                        "date": historical_state.get("timestamp"),
                        "similarity": similarity,
                        "market_data": historical_state.get("market_data", {}),
                        "outcome": historical_state.get("outcome", "unknown"),
                        "performance_1d": historical_state.get("performance_1d", 0),
                        "performance_7d": historical_state.get("performance_7d", 0)
                    })
            
            # Sort by similarity and recency
            similar_conditions.sort(key=lambda x: (-x["similarity"], x["date"]), reverse=True)
            
        except Exception as e:
            logger.debug(f"Error finding similar market conditions: {e}")
        
        return similar_conditions[:10]  # Return top 10 similar conditions
    
    def _create_market_fingerprint(
        self, 
        market_data: Dict[str, Any], 
        technicals: Dict[str, Any]
    ) -> Dict[str, float]:
        """Create a fingerprint for market conditions"""
        fingerprint = {}
        
        try:
            # RSI range
            rsi = technicals.get("rsi", 50)
            fingerprint["rsi_range"] = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"
            
            # Trend strength
            trend_strength = technicals.get("trend_strength", 0)
            fingerprint["trend_strength"] = "strong" if trend_strength > 5 else "weak"
            
            # Volume relative
            volume_ratio = technicals.get("volume_ratio", 1)
            fingerprint["volume"] = "high" if volume_ratio > 2 else "low" if volume_ratio < 0.5 else "normal"
            
            # Volatility level
            volatility = market_data.get("price_change_24h", 0)
            fingerprint["volatility"] = "high" if abs(volatility) > 5 else "low" if abs(volatility) < 1 else "normal"
            
            # Price position (in Bollinger Bands)
            price_position = technicals.get("price_position", 0.5)
            fingerprint["price_position"] = "upper" if price_position > 0.8 else "lower" if price_position < 0.2 else "middle"
            
        except Exception as e:
            logger.debug(f"Error creating market fingerprint: {e}")
        
        return fingerprint
    
    def _calculate_fingerprint_similarity(
        self, 
        fp1: Dict[str, Any], 
        fp2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two market fingerprints"""
        if not fp1 or not fp2:
            return 0.0
        
        common_keys = set(fp1.keys()) & set(fp2.keys())
        if not common_keys:
            return 0.0
        
        matches = sum(1 for key in common_keys if fp1[key] == fp2[key])
        return matches / len(common_keys)
    
    def _analyze_historical_outcomes(
        self, 
        symbol: str, 
        current_market_data: Dict[str, Any]
    ) -> Dict[str, List[float]]:
        """Analyze historical outcomes by market condition"""
        outcomes = defaultdict(list)
        
        try:
            market_history = self.market_memory.get(symbol, deque())
            
            for state in market_history:
                market_regime = state.get("market_regime", "unknown")
                performance = state.get("performance_7d", 0)
                
                if performance != 0:  # Valid performance data
                    outcomes[market_regime].append(performance)
            
            # Calculate statistics for each regime
            outcome_stats = {}
            for regime, performances in outcomes.items():
                if performances:
                    outcome_stats[regime] = {
                        "mean": statistics.mean(performances),
                        "median": statistics.median(performances),
                        "std": statistics.stdev(performances) if len(performances) > 1 else 0,
                        "win_rate": sum(1 for p in performances if p > 0) / len(performances),
                        "sample_size": len(performances)
                    }
            
            return outcome_stats
            
        except Exception as e:
            logger.debug(f"Error analyzing historical outcomes: {e}")
            return {}
    
    async def _get_market_correlations(self, symbol: str) -> List[MarketCorrelation]:
        """Get market correlations for the symbol"""
        correlations = []
        
        try:
            # Major crypto correlations (simplified)
            if symbol == "BTCUSDT":
                correlations = [
                    MarketCorrelation("BTCUSDT", "ETHUSDT", 0.8, 30, datetime.now()),
                    MarketCorrelation("BTCUSDT", "ADAUSDT", 0.7, 30, datetime.now()),
                    MarketCorrelation("BTCUSDT", "SOLUSDT", 0.75, 30, datetime.now())
                ]
            elif symbol == "ETHUSDT":
                correlations = [
                    MarketCorrelation("ETHUSDT", "BTCUSDT", 0.8, 30, datetime.now()),
                    MarketCorrelation("ETHUSDT", "ADAUSDT", 0.85, 30, datetime.now())
                ]
            # Add more correlations as needed
            
        except Exception as e:
            logger.debug(f"Error getting market correlations: {e}")
        
        return correlations
    
    async def _get_sector_context(self, symbol: str) -> Dict[str, Any]:
        """Get sector/category context"""
        try:
            # Categorize symbols
            if symbol in ["BTCUSDT"]:
                return {
                    "sector": "digital_gold",
                    "market_cap_rank": 1,
                    "dominance": 50.0,
                    "institutional_adoption": "high"
                }
            elif symbol in ["ETHUSDT"]:
                return {
                    "sector": "smart_contracts",
                    "market_cap_rank": 2,
                    "defi_exposure": "high",
                    "institutional_adoption": "medium"
                }
            else:
                return {
                    "sector": "altcoin",
                    "market_cap_rank": 10,
                    "volatility_tier": "high"
                }
                
        except Exception as e:
            logger.debug(f"Error getting sector context: {e}")
            return {}
    
    def _analyze_seasonal_patterns(self, symbol: str) -> Dict[str, float]:
        """Analyze seasonal and cyclical patterns"""
        try:
            # Mock seasonal data - in production, calculate from historical prices
            current_month = datetime.now().month
            
            # General crypto seasonal patterns
            seasonal_patterns = {
                "january": 0.05,    # 5% average gain
                "february": -0.02,  # 2% average loss
                "march": 0.08,      # 8% average gain
                "april": 0.12,      # Strong Q2 start
                "may": -0.05,       # "Sell in May"
                "june": -0.03,
                "july": 0.02,
                "august": 0.06,
                "september": -0.08, # Traditionally weak
                "october": 0.15,    # "Uptober"
                "november": 0.20,   # Strong Q4
                "december": 0.10    # Year-end rally
            }
            
            return seasonal_patterns
            
        except Exception as e:
            logger.debug(f"Error analyzing seasonal patterns: {e}")
            return {}
    
    def _analyze_time_patterns(self, symbol: str) -> Dict[str, float]:
        """Analyze time-of-day patterns"""
        try:
            # Mock time patterns - in production, analyze intraday performance
            time_patterns = {
                "00-06": 0.001,   # Overnight Asian session
                "06-12": 0.003,   # European morning
                "12-18": 0.005,   # US morning/European afternoon
                "18-24": 0.002    # US afternoon/evening
            }
            
            return time_patterns
            
        except Exception as e:
            logger.debug(f"Error analyzing time patterns: {e}")
            return {}
    
    def _analyze_volatility_context(
        self, 
        symbol: str, 
        current_market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze current volatility vs historical"""
        try:
            current_volatility = abs(current_market_data.get("price_change_24h", 0))
            
            # Historical volatility ranges (mock data)
            volatility_percentiles = {
                "p10": 1.0,    # 10th percentile
                "p25": 2.0,    # 25th percentile
                "p50": 4.0,    # Median
                "p75": 8.0,    # 75th percentile
                "p90": 15.0    # 90th percentile
            }
            
            if current_volatility <= volatility_percentiles["p25"]:
                regime = "low"
                relative = current_volatility / volatility_percentiles["p25"]
            elif current_volatility <= volatility_percentiles["p75"]:
                regime = "normal"
                relative = current_volatility / volatility_percentiles["p50"]
            elif current_volatility <= volatility_percentiles["p90"]:
                regime = "high"
                relative = current_volatility / volatility_percentiles["p75"]
            else:
                regime = "extreme"
                relative = current_volatility / volatility_percentiles["p90"]
            
            return {
                "regime": regime,
                "relative_volatility": relative,
                "percentile_rank": self._get_volatility_percentile(current_volatility, volatility_percentiles)
            }
            
        except Exception as e:
            logger.debug(f"Error analyzing volatility context: {e}")
            return {"regime": "normal", "relative_volatility": 1.0}
    
    def _get_volatility_percentile(self, current_vol: float, percentiles: Dict[str, float]) -> float:
        """Get volatility percentile rank"""
        if current_vol <= percentiles["p10"]:
            return 10
        elif current_vol <= percentiles["p25"]:
            return 25
        elif current_vol <= percentiles["p50"]:
            return 50
        elif current_vol <= percentiles["p75"]:
            return 75
        elif current_vol <= percentiles["p90"]:
            return 90
        else:
            return 95
    
    def _analyze_sentiment_context(
        self, 
        symbol: str, 
        sentiment_data: Optional[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Analyze sentiment persistence and reversal patterns"""
        try:
            if not sentiment_data:
                return {"persistence": 0.5, "reversal_prob": 0.3}
            
            current_sentiment = sentiment_data.get("overall_score", 50)
            
            # Mock sentiment analysis
            if current_sentiment > 80:
                # Extreme greed - likely to reverse
                persistence = 0.2
                reversal_prob = 0.7
            elif current_sentiment < 20:
                # Extreme fear - likely to reverse
                persistence = 0.2
                reversal_prob = 0.7
            elif 40 <= current_sentiment <= 60:
                # Neutral - tends to persist
                persistence = 0.8
                reversal_prob = 0.2
            else:
                # Moderate sentiment
                persistence = 0.6
                reversal_prob = 0.3
            
            return {
                "persistence": persistence,
                "reversal_prob": reversal_prob
            }
            
        except Exception as e:
            logger.debug(f"Error analyzing sentiment context: {e}")
            return {"persistence": 0.5, "reversal_prob": 0.3}
    
    def _analyze_level_strength(
        self, 
        symbol: str, 
        technical_indicators: Dict[str, Any]
    ) -> Dict[str, float]:
        """Analyze strength of support/resistance levels"""
        try:
            # Mock level strength analysis
            support_strength = 0.7  # 70% reliable
            resistance_strength = 0.6  # 60% reliable
            
            # Adjust based on volume and touches
            volume_ratio = technical_indicators.get("volume_ratio", 1.0)
            if volume_ratio > 2.0:
                support_strength += 0.1
                resistance_strength += 0.1
            
            return {
                "support": min(support_strength, 1.0),
                "resistance": min(resistance_strength, 1.0)
            }
            
        except Exception as e:
            logger.debug(f"Error analyzing level strength: {e}")
            return {"support": 0.5, "resistance": 0.5}
    
    def _analyze_volume_significance(
        self, 
        symbol: str, 
        current_market_data: Dict[str, Any]
    ) -> float:
        """Analyze volume profile significance"""
        try:
            # Mock volume analysis
            volume_24h = current_market_data.get("volume_24h", 0)
            
            # Calculate significance based on volume patterns
            if volume_24h > 1000000:  # High volume
                return 0.8
            elif volume_24h > 100000:  # Medium volume
                return 0.6
            else:  # Low volume
                return 0.3
                
        except Exception as e:
            logger.debug(f"Error analyzing volume significance: {e}")
            return 0.5
    
    def _identify_confidence_factors(
        self,
        similar_patterns: List[HistoricalPattern],
        similar_conditions: List[Dict[str, Any]],
        pattern_success_rates: Dict[str, float]
    ) -> Tuple[List[str], List[str]]:
        """Identify factors that boost or reduce confidence"""
        confidence_boosters = []
        risk_factors = []
        
        try:
            # Pattern-based factors
            if pattern_success_rates:
                high_success_patterns = [name for name, rate in pattern_success_rates.items() if rate > 0.7]
                if high_success_patterns:
                    confidence_boosters.append(f"High success patterns detected: {', '.join(high_success_patterns)}")
                
                low_success_patterns = [name for name, rate in pattern_success_rates.items() if rate < 0.4]
                if low_success_patterns:
                    risk_factors.append(f"Low success patterns present: {', '.join(low_success_patterns)}")
            
            # Historical condition factors
            if similar_conditions:
                positive_outcomes = [c for c in similar_conditions if c.get("performance_7d", 0) > 0]
                if len(positive_outcomes) >= len(similar_conditions) * 0.7:
                    confidence_boosters.append("Similar historical conditions showed positive outcomes")
                elif len(positive_outcomes) <= len(similar_conditions) * 0.3:
                    risk_factors.append("Similar historical conditions showed negative outcomes")
            
            # Recent pattern performance
            if similar_patterns:
                recent_patterns = [p for p in similar_patterns 
                                 if (datetime.now() - p.occurrence_date).days <= 90]
                if recent_patterns:
                    recent_success = sum(1 for p in recent_patterns if p.target_achieved) / len(recent_patterns)
                    if recent_success > 0.7:
                        confidence_boosters.append("Recent similar patterns highly successful")
                    elif recent_success < 0.4:
                        risk_factors.append("Recent similar patterns underperformed")
            
        except Exception as e:
            logger.debug(f"Error identifying confidence factors: {e}")
        
        return confidence_boosters, risk_factors
    
    def _calculate_success_probability(
        self,
        pattern_success_rates: Dict[str, float],
        historical_outcomes: Dict[str, Any],
        volatility_context: Dict[str, Any]
    ) -> float:
        """Calculate overall success probability"""
        try:
            base_probability = 0.5  # 50% base
            
            # Pattern success factor
            if pattern_success_rates:
                avg_pattern_success = statistics.mean(pattern_success_rates.values())
                pattern_factor = (avg_pattern_success - 0.5) * 0.5  # -0.25 to +0.25
                base_probability += pattern_factor
            
            # Historical outcome factor
            if historical_outcomes:
                positive_regimes = sum(1 for stats in historical_outcomes.values() 
                                     if stats.get("win_rate", 0.5) > 0.5)
                total_regimes = len(historical_outcomes)
                if total_regimes > 0:
                    historical_factor = (positive_regimes / total_regimes - 0.5) * 0.3
                    base_probability += historical_factor
            
            # Volatility adjustment
            volatility_regime = volatility_context.get("regime", "normal")
            if volatility_regime == "extreme":
                base_probability -= 0.1  # Reduce confidence in extreme volatility
            elif volatility_regime == "low":
                base_probability += 0.05  # Slight boost in low volatility
            
            return max(0.1, min(0.9, base_probability))
            
        except Exception as e:
            logger.debug(f"Error calculating success probability: {e}")
            return 0.5
    
    def _assess_context_quality(
        self,
        similar_patterns: List[HistoricalPattern],
        similar_conditions: List[Dict[str, Any]],
        total_history_count: int
    ) -> float:
        """Assess the quality of historical context"""
        try:
            quality_score = 0.0
            
            # Pattern data quality
            if similar_patterns:
                quality_score += min(30, len(similar_patterns) * 5)  # Up to 30 points
            
            # Similar conditions quality
            if similar_conditions:
                quality_score += min(30, len(similar_conditions) * 3)  # Up to 30 points
            
            # Overall history depth
            if total_history_count > 100:
                quality_score += 20  # Rich history
            elif total_history_count > 50:
                quality_score += 15  # Good history
            elif total_history_count > 20:
                quality_score += 10  # Moderate history
            
            # Data recency
            recent_patterns = [p for p in similar_patterns 
                             if (datetime.now() - p.occurrence_date).days <= 30]
            if recent_patterns:
                quality_score += min(20, len(recent_patterns) * 5)  # Up to 20 points
            
            return min(100, quality_score)
            
        except Exception as e:
            logger.debug(f"Error assessing context quality: {e}")
            return 50.0
    
    async def _update_historical_records(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        technical_indicators: Dict[str, Any]
    ):
        """Update historical records with current state"""
        try:
            # Create market state record
            market_state = {
                "timestamp": datetime.now(),
                "market_data": market_data.copy(),
                "technicals": technical_indicators.copy(),
                "fingerprint": self._create_market_fingerprint(market_data, technical_indicators),
                "outcome": "pending"  # Will be updated later with actual performance
            }
            
            # Add to market memory
            if symbol not in self.market_memory:
                self.market_memory[symbol] = deque(maxlen=self.market_memory_size)
            
            self.market_memory[symbol].append(market_state)
            
            # Periodically save historical data
            if len(self.market_memory[symbol]) % 100 == 0:
                self._save_historical_data()
                
        except Exception as e:
            logger.debug(f"Error updating historical records: {e}")
    
    def _load_historical_data(self):
        """Load historical data from storage"""
        try:
            # In production, load from database or persistent storage
            # For now, start with empty data
            pass
        except Exception as e:
            logger.debug(f"Error loading historical data: {e}")
    
    def _save_historical_data(self):
        """Save historical data to storage"""
        try:
            # In production, save to database or persistent storage
            # For now, just log the save operation
            logger.debug("Historical data saved")
        except Exception as e:
            logger.debug(f"Error saving historical data: {e}")
    
    def _get_fallback_context(self, symbol: str) -> HistoricalContext:
        """Get basic fallback context when full analysis fails"""
        return HistoricalContext(
            symbol=symbol,
            similar_patterns=[],
            pattern_success_rates={},
            recent_similar_conditions=[],
            historical_outcomes={},
            market_correlations=[],
            sector_context={},
            seasonal_trends={},
            time_of_day_patterns={},
            current_vs_historical_volatility=1.0,
            volatility_regime="normal",
            sentiment_persistence=0.5,
            sentiment_reversal_probability=0.3,
            support_resistance_strength={"support": 0.5, "resistance": 0.5},
            volume_profile_significance=0.5,
            confidence_boosters=["Historical data limited"],
            risk_factors=["Insufficient historical context"],
            success_probability=0.5,
            context_quality=25.0
        )

# Global instance
historical_context_engine = HistoricalContextEngine()