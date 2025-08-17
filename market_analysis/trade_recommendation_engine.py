#!/usr/bin/env python3
"""
Trade Recommendation Engine
Analyzes market conditions to provide timeframe-specific trading recommendations
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TradeDirection(Enum):
    """Trade direction recommendations"""
    STRONG_LONG = "strong_long"
    LONG = "long"
    NEUTRAL = "neutral"
    SHORT = "short"
    STRONG_SHORT = "strong_short"
    NO_TRADE = "no_trade"


@dataclass
class TimeframeRecommendation:
    """Recommendation for a specific timeframe"""
    timeframe: str
    direction: TradeDirection
    confidence: float  # 0-100
    reasoning: str
    risk_level: str  # "Low", "Medium", "High"
    entry_suggestion: Optional[str] = None


class TradeRecommendationEngine:
    """
    Analyzes market conditions to provide timeframe-specific trading recommendations
    """
    
    def __init__(self):
        # Define timeframes to analyze
        self.timeframes = ["30m", "1h", "2h", "3h", "4h", "5h", "6h", "7h", "8h"]
        
        # Weights for different factors
        self.weights = {
            "structure": 0.25,      # Market structure (HH-HL, LH-LL)
            "momentum": 0.20,       # RSI, MACD, momentum
            "volatility": 0.15,     # Volatility level
            "volume": 0.15,         # Volume profile and trend
            "sentiment": 0.15,      # Market sentiment
            "trend": 0.10          # Overall trend direction
        }
    
    def get_recommendations(self, market_status: Dict) -> List[TimeframeRecommendation]:
        """
        Generate trading recommendations for all timeframes
        
        Args:
            market_status: Enhanced market status data
            
        Returns:
            List of recommendations for each timeframe
        """
        recommendations = []
        
        # Analyze market conditions
        market_score = self._calculate_market_score(market_status)
        structure_bias = self._analyze_structure_confluence(market_status)
        volatility_context = self._assess_volatility_context(market_status)
        volume_context = self._assess_volume_context(market_status)
        
        for timeframe in self.timeframes:
            recommendation = self._get_timeframe_recommendation(
                timeframe,
                market_status,
                market_score,
                structure_bias,
                volatility_context,
                volume_context
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _calculate_market_score(self, status: Dict) -> float:
        """
        Calculate overall market score (-100 to +100)
        Positive = Bullish, Negative = Bearish
        """
        score = 0.0
        
        # Sentiment score (0-100, convert to -50 to +50)
        sentiment_score = status.get('sentiment_score', 50)
        score += (sentiment_score - 50) * self.weights['sentiment']
        
        # Momentum score (already -100 to +100)
        momentum_score = status.get('momentum_score', 0) 
        score += momentum_score * self.weights['momentum'] * 0.5
        
        # Trend strength (already -100 to +100)
        trend_strength = status.get('trend_strength', 0)
        score += trend_strength * self.weights['trend'] * 0.5
        
        return score
    
    def _analyze_structure_confluence(self, status: Dict) -> Dict:
        """
        Analyze market structure across timeframes
        """
        structures = {
            '1h': status.get('market_structure_1h'),
            '4h': status.get('market_structure_4h'),
            '1d': status.get('market_structure_1d')
        }
        
        biases = {
            '1h': status.get('structure_bias_1h'),
            '4h': status.get('structure_bias_4h'),
            '1d': status.get('structure_bias_1d')
        }
        
        # Count bullish/bearish structures
        bullish_count = sum(1 for bias in biases.values() if bias and "Bullish" in str(bias))
        bearish_count = sum(1 for bias in biases.values() if bias and "Bearish" in str(bias))
        
        # Check for specific patterns
        has_hh_hl = any(s == "HH-HL" for s in structures.values() if s)
        has_lh_ll = any(s == "LH-LL" for s in structures.values() if s)
        has_expanding = any(s == "Expanding" for s in structures.values() if s)
        has_contracting = any(s == "Contracting" for s in structures.values() if s)
        
        return {
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'has_uptrend': has_hh_hl,
            'has_downtrend': has_lh_ll,
            'has_expanding': has_expanding,
            'has_contracting': has_contracting,
            'structures': structures,
            'biases': biases
        }
    
    def _assess_volatility_context(self, status: Dict) -> Dict:
        """
        Assess volatility for trading decisions
        """
        volatility_level = status.get('volatility_level', 'Normal')
        volatility_pct = status.get('volatility_percentage', 2.0)
        
        # Determine trading suitability based on volatility
        if volatility_pct < 1.0:
            suitability = "low_vol_breakout"  # Good for breakout trades
        elif volatility_pct < 2.5:
            suitability = "normal_trading"    # Good for normal trading
        elif volatility_pct < 5.0:
            suitability = "high_vol_caution"  # Use wider stops
        else:
            suitability = "extreme_caution"   # Very risky
        
        return {
            'level': volatility_level,
            'percentage': volatility_pct,
            'suitability': suitability
        }
    
    def _assess_volume_context(self, status: Dict) -> Dict:
        """
        Assess volume for trading decisions
        """
        volume_profile = status.get('volume_profile', 'Normal')
        volume_ratio = status.get('volume_ratio', 1.0)
        volume_trend = status.get('volume_trend', 'stable')
        
        # High volume confirms moves, low volume suggests weak moves
        if volume_ratio > 1.5 and volume_trend == "increasing":
            strength = "very_strong"
        elif volume_ratio > 1.2:
            strength = "strong"
        elif volume_ratio > 0.8:
            strength = "normal"
        elif volume_ratio > 0.5:
            strength = "weak"
        else:
            strength = "very_weak"
        
        return {
            'profile': volume_profile,
            'ratio': volume_ratio,
            'trend': volume_trend,
            'strength': strength
        }
    
    def _get_timeframe_recommendation(
        self,
        timeframe: str,
        status: Dict,
        market_score: float,
        structure_bias: Dict,
        volatility_context: Dict,
        volume_context: Dict
    ) -> TimeframeRecommendation:
        """
        Generate recommendation for a specific timeframe
        """
        # Timeframe-specific adjustments
        tf_hours = self._parse_timeframe_hours(timeframe)
        
        # Initialize scores
        long_score = 0
        short_score = 0
        confidence = 50
        risk_level = "Medium"
        reasoning_parts = []
        
        # 1. Structure Analysis (most important)
        if structure_bias['has_uptrend']:
            if tf_hours <= 4:  # Short timeframes follow trend
                long_score += 30
                reasoning_parts.append("Uptrend structure (HH-HL)")
            else:  # Longer timeframes might see pullbacks
                long_score += 20
                reasoning_parts.append("Uptrend but watch for pullbacks")
        
        elif structure_bias['has_downtrend']:
            if tf_hours <= 4:
                short_score += 30
                reasoning_parts.append("Downtrend structure (LH-LL)")
            else:
                short_score += 20
                reasoning_parts.append("Downtrend but watch for bounces")
        
        # Handle mixed structures
        if structure_bias['has_contracting'] and structure_bias['has_expanding']:
            if tf_hours <= 2:
                reasoning_parts.append("Mixed structure - wait for breakout")
                confidence -= 20
            else:
                reasoning_parts.append("Volatility expansion expected")
                risk_level = "High"
        
        # 2. Timeframe Alignment
        if structure_bias['bullish_count'] == 3:
            long_score += 25
            confidence += 15
            reasoning_parts.append("All timeframes bullish")
        elif structure_bias['bearish_count'] == 3:
            short_score += 25
            confidence += 15
            reasoning_parts.append("All timeframes bearish")
        elif structure_bias['bullish_count'] > structure_bias['bearish_count']:
            long_score += 15
            reasoning_parts.append("Majority bullish bias")
        elif structure_bias['bearish_count'] > structure_bias['bullish_count']:
            short_score += 15
            reasoning_parts.append("Majority bearish bias")
        
        # 3. Volatility Adjustments
        if volatility_context['suitability'] == "low_vol_breakout":
            if tf_hours >= 4:  # Better for longer timeframes
                reasoning_parts.append("Low vol - breakout setup")
                confidence += 10
            else:
                reasoning_parts.append("Low vol - wait for momentum")
                confidence -= 10
        elif volatility_context['suitability'] == "extreme_caution":
            risk_level = "High"
            confidence -= 20
            reasoning_parts.append("Extreme volatility - caution")
            if tf_hours < 2:  # Very short timeframes too risky
                long_score -= 20
                short_score -= 20
        
        # 4. Volume Confirmation
        if volume_context['strength'] == "very_strong":
            # Strong volume confirms current direction
            if market_score > 0:
                long_score += 15
                reasoning_parts.append("Strong volume confirms upside")
            else:
                short_score += 15
                reasoning_parts.append("Strong volume confirms downside")
            confidence += 10
        elif volume_context['strength'] in ["weak", "very_weak"]:
            confidence -= 15
            reasoning_parts.append("Weak volume - low conviction")
            if tf_hours <= 2:
                # Very risky for short timeframes
                long_score -= 10
                short_score -= 10
        
        # 5. Market Score Integration
        if market_score > 25:
            long_score += 20
            reasoning_parts.append("Overall bullish sentiment")
        elif market_score < -25:
            short_score += 20
            reasoning_parts.append("Overall bearish sentiment")
        else:
            reasoning_parts.append("Neutral market sentiment")
        
        # 6. Timeframe-Specific Rules
        if tf_hours <= 1:  # 30m-1h: Scalping
            # Need strong signals for scalping
            if abs(long_score - short_score) < 30:
                direction = TradeDirection.NO_TRADE
                reasoning_parts.append("Insufficient edge for scalping")
            else:
                risk_level = "Medium" if volume_context['strength'] != "very_weak" else "High"
        elif tf_hours <= 4:  # 2h-4h: Intraday
            # Good for trend following
            if structure_bias['has_contracting']:
                confidence -= 10
                reasoning_parts.append("Consolidation - wait for breakout")
        else:  # 5h-8h: Swing trading
            # Need strong confluence
            if structure_bias['bullish_count'] < 2 and structure_bias['bearish_count'] < 2:
                confidence -= 15
                reasoning_parts.append("Mixed signals for swing timeframe")
        
        # Determine final direction
        if long_score >= short_score + 30:
            direction = TradeDirection.STRONG_LONG
            entry_suggestion = "Look for pullbacks to support or breakout above resistance"
        elif long_score > short_score + 15:
            direction = TradeDirection.LONG
            entry_suggestion = "Enter on pullbacks or momentum confirmation"
        elif short_score >= long_score + 30:
            direction = TradeDirection.STRONG_SHORT
            entry_suggestion = "Look for rallies to resistance or breakdown below support"
        elif short_score > long_score + 15:
            direction = TradeDirection.SHORT
            entry_suggestion = "Enter on rallies or momentum confirmation"
        elif abs(long_score - short_score) < 10:
            direction = TradeDirection.NEUTRAL
            entry_suggestion = "Wait for clearer signals or trade the range"
        else:
            direction = TradeDirection.NO_TRADE
            entry_suggestion = "Avoid trading - conflicting signals"
        
        # Adjust confidence
        confidence = max(0, min(100, confidence))
        
        # Risk level based on conditions
        if volatility_context['percentage'] > 5 or volume_context['strength'] == "very_weak":
            risk_level = "High"
        elif volatility_context['percentage'] < 2 and volume_context['strength'] in ["strong", "very_strong"]:
            risk_level = "Low"
        
        return TimeframeRecommendation(
            timeframe=timeframe,
            direction=direction,
            confidence=confidence,
            reasoning=" | ".join(reasoning_parts),
            risk_level=risk_level,
            entry_suggestion=entry_suggestion
        )
    
    def _parse_timeframe_hours(self, timeframe: str) -> float:
        """Convert timeframe string to hours"""
        if timeframe.endswith('m'):
            return float(timeframe[:-1]) / 60
        elif timeframe.endswith('h'):
            return float(timeframe[:-1])
        else:
            return 1.0  # Default to 1 hour
    
    def format_recommendations_for_display(
        self,
        recommendations: List[TimeframeRecommendation]
    ) -> str:
        """
        Format recommendations for dashboard display
        """
        result = "📊 <b>TRADING RECOMMENDATIONS BY TIMEFRAME</b>\n"
        result += "━" * 25 + "\n\n"
        
        # Group by trading suitability
        strong_longs = []
        longs = []
        shorts = []
        strong_shorts = []
        neutral = []
        no_trade = []
        
        for rec in recommendations:
            if rec.direction == TradeDirection.STRONG_LONG:
                strong_longs.append(rec)
            elif rec.direction == TradeDirection.LONG:
                longs.append(rec)
            elif rec.direction == TradeDirection.SHORT:
                shorts.append(rec)
            elif rec.direction == TradeDirection.STRONG_SHORT:
                strong_shorts.append(rec)
            elif rec.direction == TradeDirection.NEUTRAL:
                neutral.append(rec)
            else:
                no_trade.append(rec)
        
        # Display recommendations by category
        if strong_longs:
            result += "🟢 <b>STRONG LONG</b> (High Confidence)\n"
            for rec in strong_longs:
                risk_emoji = "🟢" if rec.risk_level == "Low" else "🟡" if rec.risk_level == "Medium" else "🔴"
                result += f"  {rec.timeframe}: {risk_emoji} Risk | {rec.confidence:.0f}% conf\n"
            result += "\n"
        
        if longs:
            result += "🔵 <b>LONG</b> (Moderate Confidence)\n"
            for rec in longs:
                risk_emoji = "🟢" if rec.risk_level == "Low" else "🟡" if rec.risk_level == "Medium" else "🔴"
                result += f"  {rec.timeframe}: {risk_emoji} Risk | {rec.confidence:.0f}% conf\n"
            result += "\n"
        
        if shorts:
            result += "🟠 <b>SHORT</b> (Moderate Confidence)\n"
            for rec in shorts:
                risk_emoji = "🟢" if rec.risk_level == "Low" else "🟡" if rec.risk_level == "Medium" else "🔴"
                result += f"  {rec.timeframe}: {risk_emoji} Risk | {rec.confidence:.0f}% conf\n"
            result += "\n"
        
        if strong_shorts:
            result += "🔴 <b>STRONG SHORT</b> (High Confidence)\n"
            for rec in strong_shorts:
                risk_emoji = "🟢" if rec.risk_level == "Low" else "🟡" if rec.risk_level == "Medium" else "🔴"
                result += f"  {rec.timeframe}: {risk_emoji} Risk | {rec.confidence:.0f}% conf\n"
            result += "\n"
        
        if neutral:
            result += "⚪ <b>NEUTRAL/RANGE</b>\n"
            for rec in neutral:
                result += f"  {rec.timeframe}: Range trading possible\n"
            result += "\n"
        
        if no_trade:
            result += "⛔ <b>NO TRADE</b> (Avoid)\n"
            for rec in no_trade:
                result += f"  {rec.timeframe}: Conflicting signals\n"
            result += "\n"
        
        # Add best opportunity
        best_long = max((r for r in recommendations if r.direction in [TradeDirection.LONG, TradeDirection.STRONG_LONG]),
                       key=lambda x: x.confidence, default=None)
        best_short = max((r for r in recommendations if r.direction in [TradeDirection.SHORT, TradeDirection.STRONG_SHORT]),
                        key=lambda x: x.confidence, default=None)
        
        if best_long or best_short:
            result += "💡 <b>BEST OPPORTUNITIES</b>\n"
            if best_long and best_long.confidence > 60:
                result += f"📈 Long: {best_long.timeframe} ({best_long.confidence:.0f}% conf)\n"
                if best_long.entry_suggestion:
                    result += f"   <i>{best_long.entry_suggestion}</i>\n"
            if best_short and best_short.confidence > 60:
                result += f"📉 Short: {best_short.timeframe} ({best_short.confidence:.0f}% conf)\n"
                if best_short.entry_suggestion:
                    result += f"   <i>{best_short.entry_suggestion}</i>\n"
        
        return result


# Global instance
trade_recommendation_engine = TradeRecommendationEngine()