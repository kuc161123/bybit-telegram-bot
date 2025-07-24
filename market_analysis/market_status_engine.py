#!/usr/bin/env python3
"""
Market Status Engine
Main orchestrator for comprehensive market analysis and status generation
"""
import asyncio
import logging
import statistics
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from .market_data_collector import market_data_collector, MarketData
from .technical_indicators import technical_analysis_engine, TechnicalIndicators
from .market_regime_detector import market_regime_detector, MarketRegimeAnalysis
from config.constants import MARKET_ANALYSIS_CACHE_TTL

logger = logging.getLogger(__name__)

@dataclass
class EnhancedMarketStatus:
    """Enhanced market status with comprehensive analysis"""
    # Basic info
    symbol: str
    timestamp: datetime
    
    # Core metrics
    sentiment_score: float          # 0-100
    sentiment_label: str           # "Very Bearish" to "Very Bullish"
    sentiment_emoji: str           # 🔴, 🟠, ⚖️, 🟢, 🚀
    
    volatility_level: str          # "Very Low" to "Very High"
    volatility_score: float        # 0-100 percentile
    volatility_emoji: str          # 📊
    
    trend_direction: str           # "Strong Downtrend" to "Strong Uptrend"
    trend_strength: float          # -100 to 100
    trend_emoji: str               # 📈, 📉, ↔️
    
    momentum_state: str            # "Very Bearish" to "Very Bullish"
    momentum_score: float          # -100 to 100
    momentum_emoji: str            # ⚡
    
    # Advanced analysis
    market_regime: str             # "Bull Market", "Bear Market", etc.
    regime_strength: float         # 0-100
    volume_strength: float         # 0-100
    
    # Price info
    current_price: float
    price_change_24h: float
    price_change_pct_24h: float
    
    # Confidence and quality
    confidence: float              # 0-100
    data_quality: float           # 0-100
    analysis_depth: str           # "Basic", "Standard", "Comprehensive"
    
    # Key levels
    key_levels: Dict[str, float]
    
    # Source attribution
    data_sources: List[str]
    last_updated: datetime
    
    # NEW: Enhanced metrics (with defaults)
    volatility_percentage: Optional[float] = None  # Actual volatility %
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    volume_profile: Optional[str] = None  # "High", "Normal", "Low"
    volume_ratio: Optional[float] = None  # Multiplier vs average
    market_structure: Optional[str] = None  # "HH-HL", "LH-LL", etc.
    structure_bias: Optional[str] = None  # "Bullish", "Bearish", "Neutral"
    funding_rate: Optional[float] = None  # Percentage
    funding_bias: Optional[str] = None  # "Bullish", "Bearish", "Neutral"
    open_interest_change_24h: Optional[float] = None  # Percentage change
    
    # NEW: AI Recommendation fields (GPT-4 Enhanced)
    ai_recommendation: Optional[str] = None  # "BUY", "HOLD", "SELL"
    ai_reasoning: Optional[str] = None  # Brief explanation
    ai_risk_assessment: Optional[str] = None  # "LOW", "MEDIUM", "HIGH"
    ai_confidence: Optional[float] = None  # Enhanced confidence from AI

class MarketStatusEngine:
    """
    Main engine for comprehensive market status analysis
    Orchestrates data collection, technical analysis, and regime detection
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = MARKET_ANALYSIS_CACHE_TTL  # 24 hours for reduced token usage
        self.last_analysis = {}
        
        # Configuration
        self.enable_social_sentiment = True
        self.enable_advanced_analysis = True
        self.min_confidence_threshold = 60.0
        
    async def get_enhanced_market_status(
        self,
        symbol: Optional[str] = None,
        positions: Optional[List[Dict]] = None,
        chat_data: Optional[Dict] = None,
        force_refresh: bool = False
    ) -> EnhancedMarketStatus:
        """
        Get comprehensive market status analysis
        
        Args:
            symbol: Specific symbol to analyze (optional)
            positions: Current positions for context (optional)
            chat_data: Chat context data (optional)
            force_refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            EnhancedMarketStatus with complete analysis
        """
        try:
            # Determine primary symbol
            primary_symbol = await self._determine_primary_symbol(symbol, positions)
            
            logger.info(f"🔍 Generating enhanced market status for {primary_symbol}")
            
            # Check cache first (unless force refresh requested)
            cache_key = f"market_status_{primary_symbol}"
            if not force_refresh and cache_key in self.cache:
                cached_data = self.cache[cache_key]
                cache_age = (datetime.now() - cached_data["timestamp"]).total_seconds()
                if cache_age < self.cache_ttl:
                    hours_cached = cache_age / 3600
                    logger.info(f"📦 Using cached market status for {primary_symbol} (cached {hours_cached:.1f}h ago)")
                    return cached_data["status"]
                    
            if force_refresh:
                logger.info(f"🔄 Force refresh requested for {primary_symbol} - bypassing cache")
            
            # Collect comprehensive data
            market_data, technical_indicators, sentiment_score = await self._collect_comprehensive_data(
                primary_symbol, chat_data
            )
            
            # Perform regime analysis
            regime_analysis = await market_regime_detector.analyze_market_regime(
                primary_symbol, market_data, technical_indicators, sentiment_score
            )
            
            # Generate enhanced status
            enhanced_status = await self._generate_enhanced_status(
                primary_symbol, market_data, technical_indicators, regime_analysis
            )
            
            # Cache the result
            self.cache[cache_key] = {
                "status": enhanced_status,
                "timestamp": datetime.now()
            }
            
            # Store for comparison
            self.last_analysis[primary_symbol] = enhanced_status
            
            logger.info(f"✅ Enhanced market status generated for {primary_symbol} - Confidence: {enhanced_status.confidence:.1f}%")
            return enhanced_status
            
        except Exception as e:
            logger.error(f"❌ Error generating enhanced market status: {e}")
            return self._get_fallback_status(symbol or "BTCUSDT")
    
    async def _determine_primary_symbol(
        self,
        symbol: Optional[str],
        positions: Optional[List[Dict]]
    ) -> str:
        """Determine the primary symbol for analysis"""
        
        if symbol:
            return symbol
        
        if positions:
            # Find largest position by size
            largest_position = max(positions, key=lambda p: float(p.get('size', 0)), default=None)
            if largest_position:
                return largest_position.get('symbol', 'BTCUSDT')
        
        # Default to BTCUSDT
        return "BTCUSDT"
    
    async def _collect_comprehensive_data(
        self,
        symbol: str,
        chat_data: Optional[Dict]
    ) -> Tuple[MarketData, TechnicalIndicators, Optional[float]]:
        """Collect all necessary data for analysis"""
        
        # Collect in parallel for efficiency
        tasks = [
            market_data_collector.collect_market_data(symbol),
            self._get_sentiment_score(symbol, chat_data)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        market_data = results[0] if not isinstance(results[0], Exception) else MarketData(symbol=symbol, current_price=0, price_24h_change=0, price_24h_change_pct=0, volume_24h=0, high_24h=0, low_24h=0, collected_at=datetime.now())
        sentiment_score = results[1] if not isinstance(results[1], Exception) else None
        
        # Calculate technical indicators
        kline_data = {
            "1h": market_data.kline_1h or [],
            "4h": market_data.kline_4h or [],
            "1d": market_data.kline_1d or []
        }
        
        technical_indicators = await technical_analysis_engine.calculate_indicators(
            symbol, kline_data, market_data.current_price, market_data.volume_24h
        )
        
        return market_data, technical_indicators, sentiment_score
    
    async def _get_sentiment_score(
        self,
        symbol: str,
        chat_data: Optional[Dict]
    ) -> Optional[float]:
        """Get sentiment score from multiple sources with enhanced integration"""
        try:
            sentiment_sources = []
            
            # 1. Social media sentiment (if available and enabled)
            if self.enable_social_sentiment:
                try:
                    # Try to import and get social sentiment
                    from social_media.processors.sentiment_analyzer import SentimentAnalyzer
                    from social_media.integration import social_media_integration
                    
                    social_sentiment = await social_media_integration.get_symbol_sentiment(symbol)
                    if social_sentiment and social_sentiment.get("confidence", 0) > 0.5:
                        sentiment_sources.append({
                            "score": social_sentiment["sentiment_score"],
                            "weight": 0.6,  # Higher weight for social sentiment
                            "source": "social_media",
                            "confidence": social_sentiment.get("confidence", 0.5)
                        })
                        logger.debug(f"Social sentiment for {symbol}: {social_sentiment['sentiment_score']:.1f} (confidence: {social_sentiment.get('confidence', 0.5):.2f})")
                except ImportError:
                    logger.debug("Social media sentiment modules not available")
                except Exception as e:
                    logger.debug(f"Could not get social sentiment for {symbol}: {e}")
            
            # 2. Market sentiment from news/fear & greed (placeholder for future implementation)
            try:
                # This could integrate with Fear & Greed Index, news sentiment, etc.
                # For now, we'll use a neutral baseline
                market_sentiment = await self._get_market_sentiment_baseline(symbol)
                if market_sentiment:
                    sentiment_sources.append({
                        "score": market_sentiment["score"],
                        "weight": 0.2,
                        "source": "market_indicators",
                        "confidence": market_sentiment.get("confidence", 0.3)
                    })
            except Exception as e:
                logger.debug(f"Could not get market sentiment baseline: {e}")
            
            # 3. Historical performance sentiment (from chat data)
            if chat_data:
                try:
                    recent_pnl = chat_data.get('recent_pnl_trend', [])
                    if recent_pnl and len(recent_pnl) >= 3:  # Need at least 3 data points
                        positive_trades = sum(1 for pnl in recent_pnl if pnl > 0)
                        performance_sentiment = (positive_trades / len(recent_pnl)) * 100
                        
                        # Weight based on data quality
                        data_quality = min(len(recent_pnl) / 10, 1.0)  # Up to 10 trades for full weight
                        weight = 0.3 * data_quality
                        
                        sentiment_sources.append({
                            "score": performance_sentiment,
                            "weight": weight,
                            "source": "performance_history",
                            "confidence": data_quality
                        })
                        logger.debug(f"Performance sentiment for {symbol}: {performance_sentiment:.1f} (weight: {weight:.2f})")
                except Exception as e:
                    logger.debug(f"Could not calculate performance sentiment: {e}")
            
            # 4. Volume sentiment (high volume = stronger sentiment conviction)
            try:
                volume_sentiment = await self._get_volume_sentiment(symbol)
                if volume_sentiment:
                    sentiment_sources.append({
                        "score": volume_sentiment["score"],
                        "weight": 0.1,
                        "source": "volume_analysis",
                        "confidence": volume_sentiment.get("confidence", 0.5)
                    })
            except Exception as e:
                logger.debug(f"Could not get volume sentiment: {e}")
            
            # Calculate weighted average with confidence adjustment
            if sentiment_sources:
                total_weight = sum(s["weight"] for s in sentiment_sources)
                if total_weight > 0:
                    weighted_score = sum(s["score"] * s["weight"] for s in sentiment_sources) / total_weight
                    
                    # Calculate overall confidence
                    avg_confidence = sum(s.get("confidence", 0.5) * s["weight"] for s in sentiment_sources) / total_weight
                    
                    # Log sentiment composition
                    source_summary = ", ".join([f"{s['source']}:{s['score']:.1f}" for s in sentiment_sources])
                    logger.debug(f"Multi-source sentiment for {symbol}: {weighted_score:.1f} (confidence: {avg_confidence:.2f}) - {source_summary}")
                    
                    return weighted_score
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating multi-source sentiment score for {symbol}: {e}")
            return None
    
    async def _get_market_sentiment_baseline(self, symbol: str) -> Optional[Dict]:
        """Get market sentiment baseline from technical and market structure indicators"""
        try:
            # Get market data for technical analysis
            from .market_data_collector import market_data_collector
            market_data = await market_data_collector.collect_market_data(symbol)
            
            if not market_data or not market_data.kline_1h:
                return {
                    "score": 50.0,
                    "confidence": 0.2,
                    "source": "baseline_fallback"
                }
            
            # Analyze price action for sentiment indicators
            sentiment_factors = []
            
            # 1. Recent price momentum (last 6 hours vs 24 hours)
            if len(market_data.kline_1h) >= 24:
                # Calculate 6h and 24h price changes
                current_price = market_data.current_price
                price_6h_ago = float(market_data.kline_1h[-6][4])  # Close price 6h ago
                price_24h_ago = float(market_data.kline_1h[-24][4])  # Close price 24h ago
                
                momentum_6h = ((current_price - price_6h_ago) / price_6h_ago) * 100
                momentum_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
                
                # Short-term momentum sentiment
                momentum_sentiment = 50 + (momentum_6h * 2)  # Scale 6h momentum
                momentum_sentiment = max(0, min(100, momentum_sentiment))
                
                sentiment_factors.append({
                    "score": momentum_sentiment,
                    "weight": 0.3,
                    "source": "price_momentum"
                })
                
                logger.debug(f"Price momentum sentiment for {symbol}: {momentum_sentiment:.1f} (6h: {momentum_6h:.2f}%, 24h: {momentum_24h:.2f}%)")
            
            # 2. Volatility sentiment (high volatility can indicate fear or excitement)
            if hasattr(market_data, 'volatility_percentage') and market_data.volatility_percentage:
                vol_pct = market_data.volatility_percentage
                
                # High volatility sentiment interpretation
                if vol_pct > 5.0:  # Very high volatility
                    vol_sentiment = 30  # Generally bearish (fear)
                elif vol_pct > 3.0:  # High volatility
                    vol_sentiment = 40  # Slightly bearish
                elif vol_pct > 1.5:  # Normal volatility
                    vol_sentiment = 50  # Neutral
                elif vol_pct > 0.5:  # Low volatility
                    vol_sentiment = 55  # Slightly bullish (stability)
                else:  # Very low volatility
                    vol_sentiment = 45  # Slightly bearish (stagnation)
                
                sentiment_factors.append({
                    "score": vol_sentiment,
                    "weight": 0.2,
                    "source": "volatility_sentiment"
                })
                
                logger.debug(f"Volatility sentiment for {symbol}: {vol_sentiment} (vol: {vol_pct:.2f}%)")
            
            # 3. Funding rate sentiment (if available)
            if hasattr(market_data, 'funding_rate') and market_data.funding_rate is not None:
                funding_rate = market_data.funding_rate
                
                # Convert funding rate to sentiment
                # Positive funding = longs pay shorts = bullish crowd = contrarian bearish
                # Negative funding = shorts pay longs = bearish crowd = contrarian bullish
                
                if funding_rate > 0.02:  # > 0.02%
                    funding_sentiment = 35  # Very crowded long position
                elif funding_rate > 0.01:  # > 0.01%
                    funding_sentiment = 45  # Crowded long
                elif funding_rate < -0.02:  # < -0.02%
                    funding_sentiment = 65  # Very crowded short position
                elif funding_rate < -0.01:  # < -0.01%
                    funding_sentiment = 55  # Crowded short
                else:
                    funding_sentiment = 50  # Balanced
                
                sentiment_factors.append({
                    "score": funding_sentiment,
                    "weight": 0.3,
                    "source": "funding_contrarian"
                })
                
                logger.debug(f"Funding sentiment for {symbol}: {funding_sentiment} (rate: {funding_rate:.4f}%)")
            
            # 4. Open Interest sentiment (if available)
            if hasattr(market_data, 'open_interest_change_24h') and market_data.open_interest_change_24h is not None:
                oi_change = market_data.open_interest_change_24h
                
                # Rising OI generally bullish, falling OI generally bearish
                if oi_change > 10:  # Large increase
                    oi_sentiment = 70
                elif oi_change > 5:  # Moderate increase
                    oi_sentiment = 60
                elif oi_change > 0:  # Small increase
                    oi_sentiment = 55
                elif oi_change > -5:  # Small decrease
                    oi_sentiment = 45
                elif oi_change > -10:  # Moderate decrease
                    oi_sentiment = 40
                else:  # Large decrease
                    oi_sentiment = 30
                
                sentiment_factors.append({
                    "score": oi_sentiment,
                    "weight": 0.2,
                    "source": "open_interest"
                })
                
                logger.debug(f"Open Interest sentiment for {symbol}: {oi_sentiment} (change: {oi_change:.2f}%)")
            
            # Calculate weighted sentiment
            if sentiment_factors:
                total_weight = sum(f["weight"] for f in sentiment_factors)
                weighted_score = sum(f["score"] * f["weight"] for f in sentiment_factors) / total_weight
                
                # Calculate confidence based on available factors
                confidence = 0.3 + (len(sentiment_factors) / 4) * 0.4  # Max 0.7 confidence
                
                return {
                    "score": weighted_score,
                    "confidence": confidence,
                    "source": "technical_sentiment_analysis",
                    "factors_used": len(sentiment_factors)
                }
            else:
                return {
                    "score": 50.0,
                    "confidence": 0.3,
                    "source": "baseline_neutral"
                }
                
        except Exception as e:
            logger.debug(f"Error getting enhanced market sentiment baseline: {e}")
            return {
                "score": 50.0,
                "confidence": 0.2,
                "source": "baseline_error"
            }
    
    async def _get_volume_sentiment(self, symbol: str) -> Optional[Dict]:
        """Get sentiment indication from volume analysis with enhanced calculation"""
        try:
            # Get market data for volume and price analysis
            from .market_data_collector import market_data_collector
            market_data = await market_data_collector.collect_market_data(symbol)
            
            if not market_data or not market_data.kline_1h:
                return {
                    "score": 50.0,
                    "confidence": 0.2,
                    "source": "volume_fallback"
                }
            
            # Analyze recent volume and price action (last 24 hours)
            recent_candles = market_data.kline_1h[-24:] if len(market_data.kline_1h) >= 24 else market_data.kline_1h
            
            if len(recent_candles) < 5:
                return {
                    "score": 50.0,
                    "confidence": 0.3,
                    "source": "volume_insufficient_data"
                }
            
            # Calculate volume-weighted sentiment
            total_volume = 0
            bullish_volume = 0
            bearish_volume = 0
            
            for candle in recent_candles:
                # candle format: [timestamp, open, high, low, close, volume]
                open_price = float(candle[1])
                close_price = float(candle[4])
                volume = float(candle[5])
                
                total_volume += volume
                
                # Determine candle sentiment
                if close_price > open_price:
                    # Bullish candle
                    bullish_volume += volume
                elif close_price < open_price:
                    # Bearish candle
                    bearish_volume += volume
                # Neutral/doji candles don't contribute to sentiment
            
            # Calculate volume ratio vs average
            volume_ratio = market_data.volume_ratio if hasattr(market_data, 'volume_ratio') and market_data.volume_ratio else 1.0
            
            # Calculate sentiment score
            if total_volume > 0:
                bullish_ratio = bullish_volume / total_volume
                bearish_ratio = bearish_volume / total_volume
                
                # Base sentiment from bullish/bearish volume distribution
                base_sentiment = (bullish_ratio - bearish_ratio) * 100 + 50  # Scale to 0-100
                
                # Adjust based on volume strength
                # High volume increases conviction, low volume reduces it
                volume_strength_multiplier = min(volume_ratio, 2.0)  # Cap at 2x for stability
                
                if volume_ratio > 1.2:  # Above average volume
                    # High volume amplifies sentiment conviction
                    if base_sentiment > 50:
                        # Amplify bullish sentiment
                        adjusted_sentiment = 50 + (base_sentiment - 50) * volume_strength_multiplier
                    else:
                        # Amplify bearish sentiment
                        adjusted_sentiment = 50 - (50 - base_sentiment) * volume_strength_multiplier
                else:
                    # Low volume reduces sentiment conviction, move toward neutral
                    volume_weakness_factor = max(volume_ratio, 0.5)  # Don't go below 0.5
                    adjusted_sentiment = 50 + (base_sentiment - 50) * volume_weakness_factor
                
                # Ensure bounds
                sentiment_score = max(0, min(100, adjusted_sentiment))
                
                # Calculate confidence based on data quality and volume consistency
                confidence = min(0.8, 0.4 + (len(recent_candles) / 24) * 0.2 + min(volume_ratio, 1.5) * 0.2)
                
                logger.debug(f"Volume sentiment for {symbol}: {sentiment_score:.1f} (bullish vol: {bullish_ratio:.2f}, bearish vol: {bearish_ratio:.2f}, vol ratio: {volume_ratio:.2f})")
                
                return {
                    "score": sentiment_score,
                    "confidence": confidence,
                    "source": "volume_price_action",
                    "details": {
                        "bullish_volume_ratio": bullish_ratio,
                        "bearish_volume_ratio": bearish_ratio,
                        "volume_ratio_vs_avg": volume_ratio,
                        "candles_analyzed": len(recent_candles)
                    }
                }
            else:
                return {
                    "score": 50.0,
                    "confidence": 0.2,
                    "source": "volume_no_data"
                }
                
        except Exception as e:
            logger.debug(f"Error getting enhanced volume sentiment: {e}")
            return {
                "score": 50.0,
                "confidence": 0.1,
                "source": "volume_error"
            }
    
    async def _generate_enhanced_status(
        self,
        symbol: str,
        market_data: MarketData,
        technical_indicators: TechnicalIndicators,
        regime_analysis: MarketRegimeAnalysis
    ) -> EnhancedMarketStatus:
        """Generate comprehensive enhanced market status"""
        
        # Format trend information
        trend_info = self._format_trend_info(regime_analysis.trend_direction, technical_indicators.trend_strength)
        
        # Format volatility information
        volatility_info = self._format_volatility_info(regime_analysis.volatility_level, technical_indicators.volatility_percentile)
        
        # Format momentum information
        momentum_info = self._format_momentum_info(regime_analysis.momentum_state, technical_indicators.momentum_score)
        
        # Determine data sources
        data_sources = ["bybit_api", "technical_analysis"]
        if regime_analysis.sentiment_score != 50:  # Non-default sentiment
            data_sources.append("sentiment_analysis")
        
        # Determine analysis depth
        analysis_depth = "Comprehensive" if technical_indicators.confidence > 80 else "Standard" if technical_indicators.confidence > 50 else "Basic"
        
        # Calculate volatility percentage if ATR is available
        volatility_percentage = None
        if technical_indicators.atr_14 and market_data.current_price > 0:
            volatility_percentage = (technical_indicators.atr_14 / market_data.current_price) * 100
            logger.debug(f"Volatility calculation for {symbol}: ATR={technical_indicators.atr_14:.6f}, Price={market_data.current_price:.2f}, Vol%={volatility_percentage:.2f}%")
        
        # Get support and resistance levels
        support_level = technical_indicators.major_support if hasattr(technical_indicators, 'major_support') else None
        resistance_level = technical_indicators.major_resistance if hasattr(technical_indicators, 'major_resistance') else None
        
        # Determine volume profile
        volume_profile = None
        volume_ratio = market_data.volume_ratio if hasattr(market_data, 'volume_ratio') else technical_indicators.volume_ratio
        if volume_ratio:
            if volume_ratio > 1.5:
                volume_profile = "High"
            elif volume_ratio < 0.5:
                volume_profile = "Low"
            else:
                volume_profile = "Normal"
        
        # Determine market structure
        market_structure, structure_bias = self._analyze_market_structure(
            technical_indicators, market_data.current_price
        )
        
        # Determine funding bias
        funding_bias = None
        if market_data.funding_rate is not None:
            if market_data.funding_rate < -0.01:
                funding_bias = "Bearish"  # Negative funding = shorts paying longs = bearish sentiment
            elif market_data.funding_rate > 0.01:
                funding_bias = "Bullish"  # Positive funding = longs paying shorts = bullish sentiment
            else:
                funding_bias = "Neutral"
        
        # Get open interest change from market data
        open_interest_change_24h = None
        if hasattr(market_data, 'open_interest_change_24h'):
            open_interest_change_24h = market_data.open_interest_change_24h
        
        # Get AI analysis if available
        ai_recommendation = None
        ai_reasoning = None
        ai_risk_assessment = None
        ai_confidence = None
        
        try:
            # Import AI market analyzer
            from execution.ai_market_analysis import AIMarketAnalyzer
            from clients.ai_client import get_ai_client
            
            ai_client = get_ai_client()
            if ai_client and ai_client.llm_provider != "stub":
                from clients.bybit_client import bybit_client; analyzer = AIMarketAnalyzer(bybit_client, ai_client)
                
                # Prepare position data if available
                position_data = {
                    "symbol": symbol,
                    "pnl_percentage": 0  # Default value
                }
                
                # Get AI market insight
                insight = await analyzer.analyze_market(symbol, position_data)
                
                if insight:
                    ai_recommendation = insight.recommendation
                    ai_reasoning = insight.ai_analysis
                    ai_risk_assessment = insight.risk_assessment
                    ai_confidence = insight.enhanced_confidence
                    
                    logger.info(f"🤖 AI Analysis: {ai_recommendation} - Confidence: {ai_confidence:.1f}%")
        except Exception as e:
            logger.debug(f"Could not get AI analysis: {e}")
        
        return EnhancedMarketStatus(
            # Basic info
            symbol=symbol,
            timestamp=datetime.now(),
            
            # Core metrics
            sentiment_score=regime_analysis.sentiment_score,
            sentiment_label=regime_analysis.sentiment_label,
            sentiment_emoji=regime_analysis.sentiment_emoji,
            
            volatility_level=volatility_info["level"],
            volatility_score=technical_indicators.volatility_percentile or 50.0,
            volatility_emoji="📊",
            
            trend_direction=trend_info["direction"],
            trend_strength=technical_indicators.trend_strength or 0.0,
            trend_emoji=trend_info["emoji"],
            
            momentum_state=momentum_info["state"],
            momentum_score=technical_indicators.momentum_score or 0.0,
            momentum_emoji="⚡",
            
            # Advanced analysis
            market_regime=regime_analysis.regime.value.replace("_", " ").title(),
            regime_strength=regime_analysis.regime_strength,
            volume_strength=technical_indicators.volume_strength or 50.0,
            
            # Price info
            current_price=market_data.current_price,
            price_change_24h=market_data.price_24h_change,
            price_change_pct_24h=market_data.price_24h_change_pct,
            
            # NEW: Enhanced metrics
            volatility_percentage=volatility_percentage,
            support_level=support_level,
            resistance_level=resistance_level,
            volume_profile=volume_profile,
            volume_ratio=volume_ratio,
            market_structure=market_structure,
            structure_bias=structure_bias,
            funding_rate=market_data.funding_rate,
            funding_bias=funding_bias,
            open_interest_change_24h=open_interest_change_24h,
            
            # NEW: AI Recommendation fields (GPT-4 Enhanced)
            ai_recommendation=ai_recommendation,
            ai_reasoning=ai_reasoning,
            ai_risk_assessment=ai_risk_assessment,
            ai_confidence=ai_confidence,
            
            # Confidence and quality
            confidence=regime_analysis.confidence,
            data_quality=market_data.data_quality,
            analysis_depth=analysis_depth,
            
            # Key levels
            key_levels=regime_analysis.key_levels or {},
            
            # Source attribution
            data_sources=data_sources,
            last_updated=datetime.now()
        )
    
    def _format_trend_info(self, trend_direction, trend_strength: Optional[float]) -> Dict[str, str]:
        """Format trend direction and emoji"""
        direction_map = {
            "strong_uptrend": {"direction": "Strong Uptrend", "emoji": "📈"},
            "uptrend": {"direction": "Uptrend", "emoji": "📈"},
            "ranging": {"direction": "Ranging", "emoji": "↔️"},
            "downtrend": {"direction": "Downtrend", "emoji": "📉"},
            "strong_downtrend": {"direction": "Strong Downtrend", "emoji": "📉"}
        }
        
        trend_key = trend_direction.value if hasattr(trend_direction, 'value') else str(trend_direction)
        return direction_map.get(trend_key, {"direction": "Ranging", "emoji": "↔️"})
    
    def _format_volatility_info(self, volatility_level, volatility_score: Optional[float]) -> Dict[str, str]:
        """Format volatility level"""
        level_map = {
            "very_low": "Very Low",
            "low": "Low", 
            "normal": "Normal",
            "high": "High",
            "very_high": "Very High"
        }
        
        vol_key = volatility_level.value if hasattr(volatility_level, 'value') else str(volatility_level)
        return {"level": level_map.get(vol_key, "Normal")}
    
    def _format_momentum_info(self, momentum_state, momentum_score: Optional[float]) -> Dict[str, str]:
        """Format momentum state"""
        state_map = {
            "very_bullish": "Very Bullish",
            "bullish": "Bullish",
            "neutral": "Neutral", 
            "bearish": "Bearish",
            "very_bearish": "Very Bearish"
        }
        
        momentum_key = momentum_state.value if hasattr(momentum_state, 'value') else str(momentum_state)
        return {"state": state_map.get(momentum_key, "Neutral")}
    
    def _analyze_market_structure(self, technical_indicators: Any, current_price: float) -> Tuple[Optional[str], Optional[str]]:
        """
        Enhanced market structure analysis based on multiple timeframes and price action
        Returns: (structure_pattern, structure_bias)
        """
        try:
            if not hasattr(technical_indicators, 'sma_20') or not technical_indicators.sma_20:
                return None, None
            
            # Gather technical data
            sma_20 = technical_indicators.sma_20
            sma_50 = technical_indicators.sma_50 if hasattr(technical_indicators, 'sma_50') else None
            ema_20 = technical_indicators.ema_20 if hasattr(technical_indicators, 'ema_20') else None
            trend_strength = technical_indicators.trend_strength if hasattr(technical_indicators, 'trend_strength') else 0
            rsi_14 = technical_indicators.rsi_14 if hasattr(technical_indicators, 'rsi_14') else None
            bb_upper = technical_indicators.bb_upper if hasattr(technical_indicators, 'bb_upper') else None
            bb_lower = technical_indicators.bb_lower if hasattr(technical_indicators, 'bb_lower') else None
            
            # Initialize structure analysis
            structure_signals = []
            
            # 1. Moving Average Structure Analysis
            ma_structure_score = 0
            if sma_20 and sma_50:
                if current_price > sma_20 > sma_50:
                    ma_structure_score = 2  # Strong bullish
                elif current_price > sma_20 and sma_20 < sma_50:
                    ma_structure_score = 1  # Weak bullish
                elif current_price < sma_20 < sma_50:
                    ma_structure_score = -2  # Strong bearish
                elif current_price < sma_20 and sma_20 > sma_50:
                    ma_structure_score = -1  # Weak bearish
                else:
                    ma_structure_score = 0  # Mixed/consolidation
                
                structure_signals.append({
                    "signal": "moving_averages",
                    "score": ma_structure_score,
                    "weight": 0.3
                })
            
            # 2. Price vs EMA Analysis (more responsive)
            if ema_20:
                ema_distance = ((current_price - ema_20) / ema_20) * 100
                if ema_distance > 2:
                    ema_score = 2  # Strong bullish
                elif ema_distance > 0.5:
                    ema_score = 1  # Bullish
                elif ema_distance < -2:
                    ema_score = -2  # Strong bearish
                elif ema_distance < -0.5:
                    ema_score = -1  # Bearish
                else:
                    ema_score = 0  # Neutral
                
                structure_signals.append({
                    "signal": "ema_distance",
                    "score": ema_score,
                    "weight": 0.25
                })
            
            # 3. Bollinger Band Position Analysis
            if bb_upper and bb_lower:
                bb_position = None
                if current_price > bb_upper:
                    bb_position = 2  # Above upper band - potential overbought but bullish
                elif current_price > sma_20:  # Assume sma_20 is middle band
                    bb_position = 1  # Upper half - bullish
                elif current_price < bb_lower:
                    bb_position = -2  # Below lower band - potential oversold but bearish
                else:
                    bb_position = -1  # Lower half - bearish
                
                structure_signals.append({
                    "signal": "bollinger_position",
                    "score": bb_position,
                    "weight": 0.2
                })
            
            # 4. RSI Structure Analysis
            if rsi_14:
                rsi_score = 0
                if rsi_14 > 70:
                    rsi_score = 1  # Overbought but shows strength
                elif rsi_14 > 60:
                    rsi_score = 2  # Strong bullish momentum
                elif rsi_14 > 40:
                    rsi_score = 0  # Neutral
                elif rsi_14 > 30:
                    rsi_score = -2  # Strong bearish momentum
                else:
                    rsi_score = -1  # Oversold but shows weakness
                
                structure_signals.append({
                    "signal": "rsi_momentum",
                    "score": rsi_score,
                    "weight": 0.15
                })
            
            # 5. Trend Strength Override
            if trend_strength is not None:
                trend_score = 0
                if trend_strength > 75:
                    trend_score = 2  # Very strong trend
                elif trend_strength > 25:
                    trend_score = 1  # Strong trend
                elif trend_strength < -75:
                    trend_score = -2  # Very strong downtrend
                elif trend_strength < -25:
                    trend_score = -1  # Strong downtrend
                else:
                    trend_score = 0  # Weak trend
                
                structure_signals.append({
                    "signal": "trend_strength",
                    "score": trend_score,
                    "weight": 0.1
                })
            
            # Calculate weighted structure score
            if structure_signals:
                total_weight = sum(s["weight"] for s in structure_signals)
                weighted_score = sum(s["score"] * s["weight"] for s in structure_signals) / total_weight
                
                # Determine structure pattern and bias
                structure_pattern = None
                structure_bias = None
                
                if weighted_score > 1.5:
                    structure_pattern = "HH-HL"  # Higher Highs, Higher Lows
                    structure_bias = "Strong Bullish"
                elif weighted_score > 0.5:
                    structure_pattern = "HH-HL"
                    structure_bias = "Bullish"
                elif weighted_score > -0.5:
                    structure_pattern = "Consolidation"
                    structure_bias = "Neutral"
                elif weighted_score > -1.5:
                    structure_pattern = "LH-LL"  # Lower Highs, Lower Lows
                    structure_bias = "Bearish"
                else:
                    structure_pattern = "LH-LL"
                    structure_bias = "Strong Bearish"
                
                logger.debug(f"Market structure analysis - Score: {weighted_score:.2f}, Pattern: {structure_pattern}, Bias: {structure_bias}")
                logger.debug(f"Structure signals: {[(s['signal'], s['score']) for s in structure_signals]}")
                
                return structure_pattern, structure_bias
            else:
                return "Insufficient Data", "Neutral"
            
        except Exception as e:
            logger.debug(f"Error in enhanced market structure analysis: {e}")
            return None, None
    
    def _get_fallback_status(self, symbol: str) -> EnhancedMarketStatus:
        """Get basic fallback status when analysis fails"""
        return EnhancedMarketStatus(
            symbol=symbol,
            timestamp=datetime.now(),
            sentiment_score=50.0,
            sentiment_label="Neutral",
            sentiment_emoji="⚖️",
            volatility_level="Normal",
            volatility_score=50.0,
            volatility_emoji="📊",
            trend_direction="Ranging",
            trend_strength=0.0,
            trend_emoji="↔️",
            momentum_state="Neutral",
            momentum_score=0.0,
            momentum_emoji="⚡",
            market_regime="Ranging Market",
            regime_strength=0.0,
            volume_strength=50.0,
            current_price=0.0,
            price_change_24h=0.0,
            price_change_pct_24h=0.0,
            confidence=0.0,
            data_quality=0.0,
            analysis_depth="Basic",
            key_levels={},
            data_sources=["fallback"],
            last_updated=datetime.now()
        )
    
    def get_market_status_summary(self, enhanced_status: EnhancedMarketStatus) -> str:
        """Generate a formatted summary string for display"""
        confidence_indicator = "🔴" if enhanced_status.confidence < 50 else "🟡" if enhanced_status.confidence < 80 else "🟢"
        
        return f"""🌍 <b>MARKET STATUS</b> ({enhanced_status.symbol})
{enhanced_status.sentiment_emoji} Sentiment: {enhanced_status.sentiment_label} ({enhanced_status.sentiment_score:.0f}/100)
{enhanced_status.volatility_emoji} Volatility: {enhanced_status.volatility_level}
{enhanced_status.trend_emoji} Trend: {enhanced_status.trend_direction}
{enhanced_status.momentum_emoji} Momentum: {enhanced_status.momentum_state}

🔍 Regime: {enhanced_status.market_regime}
{confidence_indicator} Confidence: {enhanced_status.confidence:.0f}%
⏱️ Updated: {enhanced_status.last_updated.strftime('%H:%M:%S')}"""

# Global instance
market_status_engine = MarketStatusEngine()