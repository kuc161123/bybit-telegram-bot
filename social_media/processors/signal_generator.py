#!/usr/bin/env python3
"""
Signal Generation for Social Media Sentiment
Generates trading signals from sentiment data
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self):
        """Initialize signal generator"""
        self.signal_thresholds = {
            'sentiment_score': {
                'extreme_bullish': 85,
                'bullish': 70,
                'neutral_high': 60,
                'neutral_low': 40,
                'bearish': 30,
                'extreme_bearish': 15
            },
            'confidence': {
                'high': 80,
                'medium': 60,
                'low': 40
            },
            'platform_consensus': {
                'strong': 0.8,    # 80% of platforms agree
                'moderate': 0.6,  # 60% of platforms agree
                'weak': 0.4       # 40% of platforms agree
            }
        }
        
        # FOMO indicators
        self.fomo_keywords = [
            'moon', 'lambo', 'to the moon', 'buy now', 'last chance',
            'dont miss', 'all in', 'yolo', 'pump', 'rocket',
            'explosive', 'massive gains', 'next big thing'
        ]
        
        # Fear indicators
        self.fear_keywords = [
            'crash', 'dump', 'sell everything', 'panic', 'liquidation',
            'bear market', 'winter', 'dead', 'worthless', 'scam',
            'rug pull', 'exit', 'cut losses'
        ]
    
    def generate_signals(self, aggregated_sentiment: Dict[str, Any], 
                        platform_sentiments: Dict[str, Any],
                        trends: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate trading signals from sentiment data"""
        try:
            signals = {
                'primary_signal': 'NEUTRAL',
                'signal_strength': 0,
                'confidence': 0,
                'risk_level': 'MEDIUM',
                'signal_details': [],
                'market_conditions': {},
                'recommendations': [],
                'warnings': []
            }
            
            # Extract key metrics
            overall_sentiment = aggregated_sentiment.get('overall_sentiment', 'NEUTRAL')
            sentiment_score = aggregated_sentiment.get('sentiment_score', 50)
            confidence = aggregated_sentiment.get('confidence', 0)
            
            # Generate primary signal
            signals['primary_signal'] = self._determine_primary_signal(
                overall_sentiment, sentiment_score, confidence
            )
            
            # Calculate signal strength
            signals['signal_strength'] = self._calculate_signal_strength(
                sentiment_score, confidence, platform_sentiments
            )
            
            # Set confidence level
            signals['confidence'] = confidence
            
            # Determine risk level
            signals['risk_level'] = self._determine_risk_level(
                signals['signal_strength'], confidence, platform_sentiments
            )
            
            # Generate detailed signal analysis
            signals['signal_details'] = self._generate_signal_details(
                sentiment_score, platform_sentiments, trends
            )
            
            # Analyze market conditions
            signals['market_conditions'] = self._analyze_market_conditions(
                platform_sentiments, trends
            )
            
            # Generate recommendations
            signals['recommendations'] = self._generate_recommendations(
                signals['primary_signal'], signals['signal_strength'], 
                signals['risk_level'], signals['market_conditions']
            )
            
            # Generate warnings
            signals['warnings'] = self._generate_warnings(
                platform_sentiments, trends, signals['market_conditions']
            )
            
            logger.debug(f"Generated signal: {signals['primary_signal']} "
                        f"(strength: {signals['signal_strength']:.2f}, "
                        f"confidence: {confidence}%)")
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
            return {
                'primary_signal': 'NEUTRAL',
                'signal_strength': 0,
                'confidence': 0,
                'risk_level': 'HIGH',
                'signal_details': ['Error generating signals'],
                'market_conditions': {},
                'recommendations': ['Avoid trading due to signal generation error'],
                'warnings': ['Signal system unavailable']
            }
    
    def _determine_primary_signal(self, overall_sentiment: str, 
                                 sentiment_score: int, confidence: int) -> str:
        """Determine the primary trading signal"""
        try:
            thresholds = self.signal_thresholds['sentiment_score']
            
            # Only generate strong signals if confidence is sufficient
            min_confidence = self.signal_thresholds['confidence']['low']
            
            if confidence < min_confidence:
                return 'NEUTRAL'
            
            if sentiment_score >= thresholds['extreme_bullish']:
                return 'STRONG_BUY'
            elif sentiment_score >= thresholds['bullish']:
                return 'BUY'
            elif sentiment_score >= thresholds['neutral_high']:
                return 'WEAK_BUY'
            elif sentiment_score <= thresholds['extreme_bearish']:
                return 'STRONG_SELL'
            elif sentiment_score <= thresholds['bearish']:
                return 'SELL'
            elif sentiment_score <= thresholds['neutral_low']:
                return 'WEAK_SELL'
            else:
                return 'NEUTRAL'
                
        except Exception as e:
            logger.error(f"Error determining primary signal: {e}")
            return 'NEUTRAL'
    
    def _calculate_signal_strength(self, sentiment_score: int, confidence: int, 
                                  platform_sentiments: Dict[str, Any]) -> float:
        """Calculate signal strength (0.0 to 1.0)"""
        try:
            # Base strength from sentiment score deviation from neutral (50)
            deviation = abs(sentiment_score - 50) / 50
            base_strength = min(deviation, 1.0)
            
            # Confidence multiplier
            confidence_multiplier = confidence / 100
            
            # Platform consensus multiplier
            consensus_multiplier = self._calculate_platform_consensus(platform_sentiments)
            
            # Combined strength
            signal_strength = base_strength * confidence_multiplier * consensus_multiplier
            
            return min(signal_strength, 1.0)
            
        except Exception as e:
            logger.error(f"Error calculating signal strength: {e}")
            return 0.0
    
    def _calculate_platform_consensus(self, platform_sentiments: Dict[str, Any]) -> float:
        """Calculate how much platforms agree on sentiment direction"""
        try:
            if not platform_sentiments:
                return 0.5
            
            sentiments = []
            for platform, data in platform_sentiments.items():
                sentiment = data.get('sentiment', 'NEUTRAL')
                sentiments.append(sentiment)
            
            if not sentiments:
                return 0.5
            
            # Count sentiment types
            bullish_count = sum(1 for s in sentiments if s in ['BULLISH', 'POSITIVE'])
            bearish_count = sum(1 for s in sentiments if s in ['BEARISH', 'NEGATIVE'])
            neutral_count = len(sentiments) - bullish_count - bearish_count
            
            total_platforms = len(sentiments)
            
            # Calculate consensus based on majority
            max_agreement = max(bullish_count, bearish_count, neutral_count)
            consensus = max_agreement / total_platforms
            
            return consensus
            
        except Exception as e:
            logger.error(f"Error calculating platform consensus: {e}")
            return 0.5
    
    def _determine_risk_level(self, signal_strength: float, confidence: int, 
                             platform_sentiments: Dict[str, Any]) -> str:
        """Determine risk level for the signal"""
        try:
            # High risk conditions
            if confidence < self.signal_thresholds['confidence']['medium']:
                return 'HIGH'
            
            if signal_strength < 0.3:
                return 'HIGH'
            
            # Check for conflicting platform signals
            consensus = self._calculate_platform_consensus(platform_sentiments)
            if consensus < self.signal_thresholds['platform_consensus']['weak']:
                return 'HIGH'
            
            # Medium risk conditions
            if signal_strength < 0.6 or consensus < self.signal_thresholds['platform_consensus']['moderate']:
                return 'MEDIUM'
            
            # Low risk
            return 'LOW'
            
        except Exception as e:
            logger.error(f"Error determining risk level: {e}")
            return 'HIGH'
    
    def _generate_signal_details(self, sentiment_score: int, 
                                platform_sentiments: Dict[str, Any],
                                trends: Optional[Dict[str, Any]]) -> List[str]:
        """Generate detailed signal analysis"""
        try:
            details = []
            
            # Sentiment score analysis
            if sentiment_score > 70:
                details.append(f"Strong bullish sentiment detected ({sentiment_score}/100)")
            elif sentiment_score < 30:
                details.append(f"Strong bearish sentiment detected ({sentiment_score}/100)")
            else:
                details.append(f"Neutral sentiment range ({sentiment_score}/100)")
            
            # Platform analysis
            if platform_sentiments:
                platform_count = len(platform_sentiments)
                consensus = self._calculate_platform_consensus(platform_sentiments)
                details.append(f"Platform consensus: {consensus:.0%} across {platform_count} sources")
                
                # Identify strongest platform signals
                strongest_platform = None
                strongest_score = 0
                
                for platform, data in platform_sentiments.items():
                    score = abs(data.get('sentiment_score', 50) - 50)
                    if score > strongest_score:
                        strongest_score = score
                        strongest_platform = platform
                
                if strongest_platform:
                    platform_sentiment = platform_sentiments[strongest_platform].get('sentiment', 'NEUTRAL')
                    details.append(f"Strongest signal from {strongest_platform}: {platform_sentiment}")
            
            # Trend analysis
            if trends:
                emerging_trends = trends.get('emerging_trends', [])
                if emerging_trends:
                    top_trend = emerging_trends[0]
                    topic = top_trend.get('topic', 'unknown')
                    strength = top_trend.get('strength', 0)
                    details.append(f"Top trending topic: {topic} (strength: {strength:.0%})")
            
            return details[:5]  # Limit to top 5 details
            
        except Exception as e:
            logger.error(f"Error generating signal details: {e}")
            return ["Signal analysis unavailable"]
    
    def _analyze_market_conditions(self, platform_sentiments: Dict[str, Any],
                                  trends: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze current market conditions"""
        try:
            conditions = {
                'market_mood': 'NEUTRAL',
                'volatility_expectation': 'MEDIUM',
                'fomo_level': 'LOW',
                'fear_level': 'LOW',
                'trend_momentum': 'STABLE'
            }
            
            # Analyze overall market mood
            sentiment_scores = []
            for platform, data in platform_sentiments.items():
                score = data.get('sentiment_score', 50)
                sentiment_scores.append(score)
            
            if sentiment_scores:
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                if avg_sentiment > 65:
                    conditions['market_mood'] = 'BULLISH'
                elif avg_sentiment < 35:
                    conditions['market_mood'] = 'BEARISH'
            
            # Analyze FOMO and Fear levels
            if trends:
                keywords = trends.get('keywords', {})
                
                # FOMO detection
                fomo_indicators = sum(count for keyword, count in keywords.items() 
                                     if any(fomo_word in keyword.lower() for fomo_word in self.fomo_keywords))
                
                if fomo_indicators > 10:
                    conditions['fomo_level'] = 'HIGH'
                elif fomo_indicators > 5:
                    conditions['fomo_level'] = 'MEDIUM'
                
                # Fear detection
                fear_indicators = sum(count for keyword, count in keywords.items() 
                                     if any(fear_word in keyword.lower() for fear_word in self.fear_keywords))
                
                if fear_indicators > 10:
                    conditions['fear_level'] = 'HIGH'
                elif fear_indicators > 5:
                    conditions['fear_level'] = 'MEDIUM'
            
            # Volatility expectation
            sentiment_variance = 0
            if len(sentiment_scores) > 1:
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                sentiment_variance = sum((score - avg_sentiment) ** 2 for score in sentiment_scores) / len(sentiment_scores)
                
                if sentiment_variance > 400:  # High variance
                    conditions['volatility_expectation'] = 'HIGH'
                elif sentiment_variance > 100:
                    conditions['volatility_expectation'] = 'MEDIUM'
                else:
                    conditions['volatility_expectation'] = 'LOW'
            
            return conditions
            
        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return {
                'market_mood': 'UNKNOWN',
                'volatility_expectation': 'HIGH',
                'fomo_level': 'UNKNOWN',
                'fear_level': 'UNKNOWN',
                'trend_momentum': 'UNKNOWN'
            }
    
    def _generate_recommendations(self, primary_signal: str, signal_strength: float,
                                 risk_level: str, market_conditions: Dict[str, Any]) -> List[str]:
        """Generate trading recommendations"""
        try:
            recommendations = []
            
            # Signal-based recommendations
            if primary_signal in ['STRONG_BUY', 'BUY']:
                if signal_strength > 0.7:
                    recommendations.append("Consider long positions with strong conviction")
                else:
                    recommendations.append("Consider small long positions")
                    
            elif primary_signal in ['STRONG_SELL', 'SELL']:
                if signal_strength > 0.7:
                    recommendations.append("Consider short positions or exit longs")
                else:
                    recommendations.append("Consider reducing long exposure")
                    
            else:  # NEUTRAL or WEAK signals
                recommendations.append("Hold current positions, avoid new entries")
            
            # Risk-based recommendations
            if risk_level == 'HIGH':
                recommendations.append("Use smaller position sizes due to high uncertainty")
                recommendations.append("Set tight stop losses")
                
            elif risk_level == 'LOW' and signal_strength > 0.6:
                recommendations.append("Signal quality supports normal position sizing")
            
            # Market condition recommendations
            fomo_level = market_conditions.get('fomo_level', 'LOW')
            fear_level = market_conditions.get('fear_level', 'LOW')
            
            if fomo_level == 'HIGH':
                recommendations.append("Beware of FOMO - market may be overextended")
                
            if fear_level == 'HIGH':
                recommendations.append("Extreme fear detected - potential reversal opportunity")
            
            volatility = market_conditions.get('volatility_expectation', 'MEDIUM')
            if volatility == 'HIGH':
                recommendations.append("Expect high volatility - use appropriate risk management")
            
            return recommendations[:4]  # Limit to top 4 recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return ["Error generating recommendations"]
    
    def _generate_warnings(self, platform_sentiments: Dict[str, Any],
                          trends: Optional[Dict[str, Any]],
                          market_conditions: Dict[str, Any]) -> List[str]:
        """Generate warning messages"""
        try:
            warnings = []
            
            # Platform consensus warnings
            consensus = self._calculate_platform_consensus(platform_sentiments)
            if consensus < 0.4:
                warnings.append("Low platform consensus - conflicting signals detected")
            
            # Data quality warnings
            platform_count = len(platform_sentiments)
            if platform_count < 2:
                warnings.append("Limited data sources - signal reliability reduced")
            
            # Market condition warnings
            fomo_level = market_conditions.get('fomo_level', 'LOW')
            fear_level = market_conditions.get('fear_level', 'LOW')
            
            if fomo_level == 'HIGH' and fear_level == 'HIGH':
                warnings.append("Conflicting FOMO and fear signals - market confusion")
                
            # Trend warnings
            if trends:
                emerging_trends = trends.get('emerging_trends', [])
                if len(emerging_trends) == 0:
                    warnings.append("No clear trends detected - sideways market possible")
            
            return warnings[:3]  # Limit to top 3 warnings
            
        except Exception as e:
            logger.error(f"Error generating warnings: {e}")
            return ["Error generating warnings"]
    
    def format_signal_summary(self, signals: Dict[str, Any]) -> str:
        """Format signal data into human-readable summary"""
        try:
            primary_signal = signals.get('primary_signal', 'NEUTRAL')
            signal_strength = signals.get('signal_strength', 0)
            confidence = signals.get('confidence', 0)
            risk_level = signals.get('risk_level', 'HIGH')
            
            # Primary signal with strength
            summary = f"{primary_signal}"
            
            if signal_strength > 0:
                summary += f" (strength: {signal_strength:.0%})"
            
            # Confidence and risk
            summary += f" | Confidence: {confidence}% | Risk: {risk_level}"
            
            return summary
            
        except Exception as e:
            logger.error(f"Error formatting signal summary: {e}")
            return "Signal summary unavailable"