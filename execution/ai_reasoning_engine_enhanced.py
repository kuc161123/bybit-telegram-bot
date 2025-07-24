#!/usr/bin/env python3
"""
Enhanced AI Reasoning Engine - Phase 4
Integrates pattern recognition and historical context for superior market analysis
"""
import asyncio
import logging
from typing import Dict, Optional, Tuple, List
from datetime import datetime
import json

from .ai_reasoning_engine import AIReasoningEngine
from market_analysis.pattern_recognition import pattern_recognition_engine, PatternAnalysis
from market_analysis.historical_context_engine import historical_context_engine, HistoricalContext
from config.settings import AI_MODEL

logger = logging.getLogger(__name__)

class EnhancedAIReasoningEngine(AIReasoningEngine):
    """Enhanced AI reasoning with pattern recognition and historical context"""
    
    def __init__(self, ai_client):
        super().__init__(ai_client)
        self.pattern_weight = 0.25    # 25% weight for patterns
        self.historical_weight = 0.30  # 30% weight for historical context
        self.technical_weight = 0.45   # 45% weight for technical analysis
        
        logger.info(f"🚀 Enhanced AI Reasoning Engine initialized with pattern & historical analysis")
    
    async def analyze_with_enhanced_reasoning(
        self,
        symbol: str,
        market_data: Dict,
        technical_signals: Dict,
        market_regime: str,
        current_confidence: float,
        kline_data: Optional[Dict] = None,
        sentiment_data: Optional[Dict] = None
    ) -> Tuple[str, str, float, str]:
        """
        Perform enhanced market analysis with patterns and historical context
        
        Returns:
            - recommendation: BUY/HOLD/SELL
            - reasoning: Detailed explanation with patterns and historical context
            - enhanced_confidence: Improved confidence score
            - risk_assessment: Current risk level
        """
        try:
            # Check cache first
            cache_key = f"enhanced_{symbol}_{market_regime}_{datetime.now().hour}"
            if cache_key in self.reasoning_cache:
                cached_time, cached_result = self.reasoning_cache[cache_key]
                if (datetime.now() - cached_time).seconds < self.cache_ttl:
                    return cached_result
            
            # Step 1: Pattern Recognition Analysis
            pattern_analysis = await self._analyze_patterns(symbol, kline_data, market_data)
            
            # Step 2: Historical Context Analysis
            historical_context = await self._analyze_historical_context(
                symbol, market_data, technical_signals, pattern_analysis, sentiment_data
            )
            
            # Step 3: Enhanced AI Analysis with Comprehensive Context
            recommendation, reasoning, risk_assessment = await self._get_enhanced_gpt4_analysis(
                symbol, market_data, technical_signals, market_regime,
                pattern_analysis, historical_context
            )
            
            # Step 4: Calculate Enhanced Confidence
            enhanced_confidence = await self._calculate_comprehensive_confidence(
                current_confidence, technical_signals, recommendation, market_regime,
                pattern_analysis, historical_context
            )
            
            # Cache result
            result = (recommendation, reasoning, enhanced_confidence, risk_assessment)
            self.reasoning_cache[cache_key] = (datetime.now(), result)
            
            logger.info(f"✅ Enhanced AI analysis for {symbol}: {recommendation} "
                       f"({enhanced_confidence:.1f}% confidence, {risk_assessment} risk)")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced AI reasoning: {e}")
            # Fallback to standard reasoning
            return await super().analyze_with_reasoning(
                symbol, market_data, technical_signals, market_regime, current_confidence
            )
    
    async def _analyze_patterns(
        self, 
        symbol: str, 
        kline_data: Optional[Dict],
        market_data: Dict
    ) -> PatternAnalysis:
        """Analyze chart and candlestick patterns"""
        try:
            if not kline_data:
                # Create basic kline data structure if not provided
                kline_data = {"5m": [], "15m": [], "1h": []}
            
            current_price = market_data.get("current_price", 0)
            
            pattern_analysis = await pattern_recognition_engine.analyze_patterns(
                symbol=symbol,
                kline_data=kline_data,
                current_price=current_price,
                timeframes=["5m", "15m", "1h"]
            )
            
            logger.debug(f"Pattern analysis for {symbol}: {pattern_analysis.pattern_count} patterns, "
                        f"{pattern_analysis.dominant_signal} signal, "
                        f"{pattern_analysis.pattern_confluence:.1f}% confluence")
            
            return pattern_analysis
            
        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")
            # Return empty analysis
            from market_analysis.pattern_recognition import PatternAnalysis
            return PatternAnalysis(
                chart_patterns=[],
                candlestick_patterns=[],
                pattern_confluence=0.0,
                dominant_signal="neutral",
                pattern_count=0,
                confidence_average=0.0,
                key_insights=["Pattern analysis unavailable"]
            )
    
    async def _analyze_historical_context(
        self,
        symbol: str,
        market_data: Dict,
        technical_signals: Dict,
        pattern_analysis: PatternAnalysis,
        sentiment_data: Optional[Dict]
    ) -> HistoricalContext:
        """Analyze historical context and similar conditions"""
        try:
            all_patterns = pattern_analysis.chart_patterns + pattern_analysis.candlestick_patterns
            
            historical_context = await historical_context_engine.get_historical_context(
                symbol=symbol,
                current_market_data=market_data,
                technical_indicators=technical_signals,
                detected_patterns=all_patterns,
                sentiment_data=sentiment_data
            )
            
            logger.debug(f"Historical context for {symbol}: {len(historical_context.similar_patterns)} similar patterns, "
                        f"{historical_context.success_probability:.2f} success probability, "
                        f"{historical_context.context_quality:.1f}% context quality")
            
            return historical_context
            
        except Exception as e:
            logger.error(f"Error analyzing historical context: {e}")
            return historical_context_engine._get_fallback_context(symbol)
    
    async def _get_enhanced_gpt4_analysis(
        self,
        symbol: str,
        market_data: Dict,
        technical_signals: Dict,
        market_regime: str,
        pattern_analysis: PatternAnalysis,
        historical_context: HistoricalContext
    ) -> Tuple[str, str, str]:
        """Get GPT-4 analysis with enhanced context"""
        
        # Prepare comprehensive context
        context = self._prepare_enhanced_context(
            symbol, market_data, technical_signals, market_regime,
            pattern_analysis, historical_context
        )
        
        prompt = self._create_enhanced_prompt(context)
        
        try:
            if self.ai_client.llm_provider == "stub":
                return self._get_enhanced_fallback_analysis(context)
            
            # Use GPT-4 with enhanced context
            response = self.ai_client.client.chat.completions.create(
                model=self.gpt4_model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert cryptocurrency trading analyst with deep knowledge of chart patterns, market history, and behavioral finance. Provide clear, actionable recommendations based on comprehensive technical and contextual analysis."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Lower temperature for more consistent analysis
                max_tokens=1500   # More tokens for detailed analysis
            )
            
            # Parse enhanced response
            content = response.choices[0].message.content
            recommendation, reasoning, risk = self._parse_enhanced_response(content)
            
            return recommendation, reasoning, risk
            
        except Exception as e:
            logger.error(f"Enhanced GPT-4 analysis error: {e}")
            return self._get_enhanced_fallback_analysis(context)
    
    def _prepare_enhanced_context(
        self,
        symbol: str,
        market_data: Dict,
        technical_signals: Dict,
        market_regime: str,
        pattern_analysis: PatternAnalysis,
        historical_context: HistoricalContext
    ) -> Dict:
        """Prepare comprehensive context with patterns and history"""
        
        base_context = super()._prepare_analysis_context(
            symbol, market_data, technical_signals, market_regime
        )
        
        # Add pattern analysis
        pattern_context = {
            "detected_patterns": {
                "chart_patterns": [
                    {
                        "name": p.pattern_name,
                        "signal": p.signal,
                        "confidence": p.confidence,
                        "strength": p.strength,
                        "description": p.description,
                        "timeframe": p.timeframe
                    }
                    for p in pattern_analysis.chart_patterns
                ],
                "candlestick_patterns": [
                    {
                        "name": p.pattern_name,
                        "signal": p.signal,
                        "confidence": p.confidence,
                        "description": p.description,
                        "timeframe": p.timeframe
                    }
                    for p in pattern_analysis.candlestick_patterns
                ],
                "pattern_confluence": pattern_analysis.pattern_confluence,
                "dominant_signal": pattern_analysis.dominant_signal,
                "key_insights": pattern_analysis.key_insights
            }
        }
        
        # Add historical context
        historical_context_data = {
            "historical_analysis": {
                "similar_patterns_found": len(historical_context.similar_patterns),
                "pattern_success_rates": historical_context.pattern_success_rates,
                "similar_market_conditions": len(historical_context.recent_similar_conditions),
                "success_probability": historical_context.success_probability,
                "context_quality": historical_context.context_quality,
                "volatility_regime": historical_context.volatility_regime,
                "seasonal_context": self._get_current_seasonal_context(historical_context.seasonal_trends),
                "confidence_boosters": historical_context.confidence_boosters,
                "risk_factors": historical_context.risk_factors,
                "market_correlations": [
                    f"{corr.correlated_symbol} ({corr.correlation_strength:.2f})"
                    for corr in historical_context.market_correlations[:3]
                ]
            }
        }
        
        # Combine all contexts
        enhanced_context = {**base_context, **pattern_context, **historical_context_data}
        
        return enhanced_context
    
    def _get_current_seasonal_context(self, seasonal_trends: Dict[str, float]) -> str:
        """Get current seasonal context"""
        try:
            current_month = datetime.now().strftime("%B").lower()
            if current_month in seasonal_trends:
                trend = seasonal_trends[current_month]
                if trend > 0.05:
                    return f"Historically strong month (+{trend:.1%})"
                elif trend < -0.05:
                    return f"Historically weak month ({trend:.1%})"
                else:
                    return f"Historically neutral month ({trend:.1%})"
            return "No seasonal data"
        except:
            return "No seasonal data"
    
    def _create_enhanced_prompt(self, context: Dict) -> str:
        """Create enhanced prompt with all available context"""
        
        # Basic market data
        basic_info = f"""COMPREHENSIVE MARKET ANALYSIS FOR {context['symbol']}

CURRENT MARKET SNAPSHOT:
- Price: ${context['current_price']:,.2f} ({context['price_change_24h']:+.2f}% 24h)
- Market Regime: {context['market_regime']}
- Volume: {context['volume_analysis']['interpretation']} ({context['volume_analysis']['ratio']:.1f}x average)

TECHNICAL INDICATORS:
- RSI: {context['technical_indicators']['rsi']['value']:.1f} ({context['technical_indicators']['rsi']['condition']})
- MACD: {context['technical_indicators']['macd']['crossover']} crossover
- Moving Averages: {context['technical_indicators']['moving_averages']['trend']} trend
- Bollinger Bands: Price is {context['technical_indicators']['bollinger_bands']['position']}
- Support: ${context['price_levels']['support']:,.2f} ({context['price_levels']['distance_to_support']:.1f}% away)
- Resistance: ${context['price_levels']['resistance']:,.2f} ({context['price_levels']['distance_to_resistance']:.1f}% away)"""
        
        # Pattern analysis
        pattern_info = ""
        if context.get("detected_patterns"):
            patterns = context["detected_patterns"]
            pattern_info = f"""

PATTERN ANALYSIS:
- Chart Patterns Detected: {len(patterns['chart_patterns'])}"""
            
            for pattern in patterns['chart_patterns'][:3]:  # Top 3 patterns
                pattern_info += f"\n  • {pattern['name']}: {pattern['signal']} signal ({pattern['confidence']:.0f}% confidence, {pattern['strength']} strength)"
            
            pattern_info += f"\n- Candlestick Patterns: {len(patterns['candlestick_patterns'])}"
            for pattern in patterns['candlestick_patterns'][:3]:
                pattern_info += f"\n  • {pattern['name']}: {pattern['signal']} signal ({pattern['confidence']:.0f}% confidence)"
            
            pattern_info += f"\n- Pattern Confluence: {patterns['pattern_confluence']:.0f}% (agreement between patterns)"
            pattern_info += f"\n- Dominant Pattern Signal: {patterns['dominant_signal']}"
            
            if patterns['key_insights']:
                pattern_info += f"\n- Key Pattern Insights: {'; '.join(patterns['key_insights'][:2])}"
        
        # Historical context
        historical_info = ""
        if context.get("historical_analysis"):
            hist = context["historical_analysis"]
            historical_info = f"""

HISTORICAL CONTEXT:
- Similar Patterns Found: {hist['similar_patterns_found']} historical occurrences
- Success Probability: {hist['success_probability']:.1%} based on similar conditions
- Context Quality: {hist['context_quality']:.0f}% (data reliability)
- Volatility Regime: {hist['volatility_regime']} vs historical
- Seasonal Context: {hist['seasonal_context']}"""
            
            if hist['pattern_success_rates']:
                historical_info += "\n- Pattern Success Rates:"
                for pattern_name, success_rate in list(hist['pattern_success_rates'].items())[:3]:
                    historical_info += f"\n  • {pattern_name}: {success_rate:.1%}"
            
            if hist['confidence_boosters']:
                historical_info += f"\n- Confidence Boosters: {'; '.join(hist['confidence_boosters'][:2])}"
            
            if hist['risk_factors']:
                historical_info += f"\n- Risk Factors: {'; '.join(hist['risk_factors'][:2])}"
            
            if hist['market_correlations']:
                historical_info += f"\n- Correlated Assets: {', '.join(hist['market_correlations'])}"
        
        # Enhanced analysis request
        analysis_request = """

COMPREHENSIVE ANALYSIS REQUIRED:
Based on the technical indicators, detected patterns, and historical context provided above:

1. PATTERN INTEGRATION: How do the detected chart and candlestick patterns align with technical indicators?
2. HISTORICAL VALIDATION: How do similar historical conditions support or contradict the current signals?
3. CONFLUENCE ASSESSMENT: What's the agreement level between technical, pattern, and historical signals?
4. RISK-REWARD ANALYSIS: Considering pattern targets and historical outcomes, what's the risk-reward ratio?
5. TIMING CONSIDERATIONS: Based on seasonal and historical timing patterns, is this optimal timing?

REQUIRED OUTPUT FORMAT:
RECOMMENDATION: [BUY/HOLD/SELL]
REASONING: [3-4 sentences covering pattern confirmation, historical validation, and confluence analysis]
CONFIDENCE_DRIVERS: [Key factors supporting this recommendation]
RISK: [LOW/MEDIUM/HIGH]
TIMEFRAME: [Expected timeframe for the recommendation to play out]"""
        
        return basic_info + pattern_info + historical_info + analysis_request
    
    def _parse_enhanced_response(self, content: str) -> Tuple[str, str, str]:
        """Parse enhanced GPT-4 response"""
        try:
            lines = content.strip().split('\n')
            
            recommendation = "HOLD"
            reasoning = "Analysis indicates mixed signals"
            risk = "MEDIUM"
            confidence_drivers = ""
            timeframe = ""
            
            for line in lines:
                line = line.strip()
                if line.startswith("RECOMMENDATION:"):
                    recommendation = line.split(":", 1)[1].strip()
                elif line.startswith("REASONING:"):
                    reasoning = line.split(":", 1)[1].strip()
                elif line.startswith("CONFIDENCE_DRIVERS:"):
                    confidence_drivers = line.split(":", 1)[1].strip()
                elif line.startswith("RISK:"):
                    risk = line.split(":", 1)[1].strip()
                elif line.startswith("TIMEFRAME:"):
                    timeframe = line.split(":", 1)[1].strip()
            
            # Enhance reasoning with confidence drivers and timeframe
            enhanced_reasoning = reasoning
            if confidence_drivers:
                enhanced_reasoning += f" Key factors: {confidence_drivers}"
            if timeframe:
                enhanced_reasoning += f" Expected timeframe: {timeframe}"
            
            return recommendation, enhanced_reasoning, risk
            
        except Exception as e:
            logger.error(f"Error parsing enhanced response: {e}")
            return "HOLD", "Analysis parsing failed", "MEDIUM"
    
    def _get_enhanced_fallback_analysis(self, context: Dict) -> Tuple[str, str, str]:
        """Enhanced fallback analysis using pattern and historical data"""
        try:
            # Use pattern signals
            pattern_signal = "neutral"
            if context.get("detected_patterns"):
                pattern_signal = context["detected_patterns"]["dominant_signal"]
            
            # Use historical probability
            success_prob = 0.5
            if context.get("historical_analysis"):
                success_prob = context["historical_analysis"]["success_probability"]
            
            # Combine signals
            if pattern_signal == "bullish" and success_prob > 0.6:
                return "BUY", "Bullish patterns with strong historical support", "LOW"
            elif pattern_signal == "bearish" and success_prob > 0.6:
                return "SELL", "Bearish patterns with strong historical support", "LOW"
            elif success_prob > 0.7:
                return "BUY", "Strong historical probability despite mixed patterns", "MEDIUM"
            elif success_prob < 0.3:
                return "SELL", "Weak historical probability suggests caution", "MEDIUM"
            else:
                return "HOLD", "Mixed pattern and historical signals", "MEDIUM"
                
        except Exception as e:
            logger.error(f"Error in enhanced fallback analysis: {e}")
            return "HOLD", "Enhanced analysis unavailable", "MEDIUM"
    
    async def _calculate_comprehensive_confidence(
        self,
        base_confidence: float,
        technical_signals: Dict,
        recommendation: str,
        market_regime: str,
        pattern_analysis: PatternAnalysis,
        historical_context: HistoricalContext
    ) -> float:
        """Calculate confidence with pattern and historical factors"""
        
        # Start with enhanced base confidence from parent class
        enhanced_confidence = super()._calculate_enhanced_confidence(
            base_confidence, technical_signals, recommendation, market_regime
        )
        
        # Pattern confidence boost
        pattern_boost = 0.0
        if pattern_analysis.pattern_count > 0:
            # Strong confluence boost
            if pattern_analysis.pattern_confluence > 80:
                pattern_boost += 8.0
            elif pattern_analysis.pattern_confluence > 60:
                pattern_boost += 5.0
            
            # Signal alignment boost
            if pattern_analysis.dominant_signal == recommendation.lower():
                pattern_boost += 5.0
            elif pattern_analysis.dominant_signal != "neutral":
                pattern_boost -= 3.0  # Conflicting signal penalty
            
            # High confidence patterns boost
            if pattern_analysis.confidence_average > 75:
                pattern_boost += 3.0
        
        # Historical confidence boost
        historical_boost = 0.0
        if historical_context.context_quality > 60:
            # Success probability boost
            success_prob = historical_context.success_probability
            if success_prob > 0.7:
                historical_boost += 10.0
            elif success_prob > 0.6:
                historical_boost += 6.0
            elif success_prob < 0.4:
                historical_boost -= 5.0
            
            # Similar patterns boost
            if len(historical_context.similar_patterns) > 3:
                avg_success = sum(p.success_rate for p in historical_context.similar_patterns) / len(historical_context.similar_patterns)
                if avg_success > 0.7:
                    historical_boost += 5.0
            
            # Context quality boost
            if historical_context.context_quality > 80:
                historical_boost += 3.0
        
        # Confidence booster/risk factor adjustments
        confidence_adjustment = len(historical_context.confidence_boosters) * 2.0
        risk_adjustment = len(historical_context.risk_factors) * 1.5
        
        # Apply all boosts
        total_boost = pattern_boost + historical_boost + confidence_adjustment - risk_adjustment
        final_confidence = enhanced_confidence + total_boost
        
        # Cap confidence appropriately
        final_confidence = max(10.0, min(95.0, final_confidence))
        
        logger.debug(f"Confidence calculation: base={base_confidence:.1f}, "
                    f"enhanced={enhanced_confidence:.1f}, pattern_boost={pattern_boost:.1f}, "
                    f"historical_boost={historical_boost:.1f}, final={final_confidence:.1f}")
        
        return round(final_confidence, 1)

# Enhanced factory function
def get_enhanced_reasoning_engine(ai_client):
    """Get or create enhanced reasoning engine instance"""
    global _enhanced_reasoning_engine
    if '_enhanced_reasoning_engine' not in globals():
        globals()['_enhanced_reasoning_engine'] = EnhancedAIReasoningEngine(ai_client)
    return globals()['_enhanced_reasoning_engine']