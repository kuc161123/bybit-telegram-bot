#!/usr/bin/env python3
"""
Enhanced Market Status Engine
Integrates all enhanced components for improved accuracy
"""
import asyncio
import logging
import statistics
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from .market_data_collector import market_data_collector, MarketData
from .technical_indicators_enhanced import enhanced_technical_analysis_engine, EnhancedTechnicalIndicators
from .market_regime_detector_enhanced import enhanced_market_regime_detector, EnhancedMarketRegimeAnalysis

logger = logging.getLogger(__name__)

@dataclass
class EnhancedMarketStatus:
    """Enhanced market status with comprehensive analysis and improved accuracy"""
    # Basic info (required fields)
    symbol: str
    timestamp: datetime
    
    # Core metrics with enhanced accuracy (required)
    sentiment_score: float          # 0-100
    sentiment_label: str           # More granular labels
    sentiment_emoji: str           
    
    volatility_level: str          # Including "Extreme" level
    volatility_score: float        # 0-100 percentile
    volatility_emoji: str          
    
    trend_direction: str           
    trend_strength: float          # -100 to 100
    trend_emoji: str               
    
    momentum_state: str            
    momentum_score: float          # -100 to 100
    momentum_emoji: str            
    
    # Advanced analysis (required)
    market_regime: str             
    regime_strength: float         # 0-100
    regime_transition_probability: float  # 0-100
    volume_strength: float         # 0-100
    
    # Price info (required)
    current_price: float
    price_change_24h: float
    price_change_pct_24h: float
    
    # All optional fields with defaults
    volatility_percentage: Optional[float] = None  # Actual volatility %
    
    # Multi-timeframe analysis
    timeframe_alignment: Optional[Dict[str, str]] = None  # 5m, 15m, 1h, 4h, 1d trends
    timeframe_confluence: float = 0.0  # 0-100 alignment score
    
    # Market microstructure
    bid_ask_spread: Optional[float] = None
    order_book_imbalance: Optional[float] = None
    liquidity_score: Optional[float] = None
    
    # Enhanced technical indicators
    macd_divergence: Optional[str] = None  # Bullish/Bearish divergence
    vwap: Optional[float] = None
    vwap_distance: Optional[float] = None  # % distance from VWAP
    poc: Optional[float] = None  # Point of Control
    vah: Optional[float] = None  # Value Area High
    val: Optional[float] = None  # Value Area Low
    
    # Enhanced support/resistance
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    support_strength: Optional[float] = None  # 0-100
    resistance_strength: Optional[float] = None  # 0-100
    
    # Volume analysis
    volume_profile: Optional[str] = None  # "High", "Normal", "Low"
    volume_ratio: Optional[float] = None  # Multiplier vs average
    cumulative_delta: Optional[float] = None  # Buy vs sell pressure
    delta_trend: Optional[str] = None  # Increasing/Decreasing/Neutral
    
    # Market structure
    market_structure: Optional[str] = None  # "HH-HL", "LH-LL", etc.
    structure_bias: Optional[str] = None  # "Bullish", "Bearish", "Neutral"
    
    # Funding and open interest
    funding_rate: Optional[float] = None  # Percentage
    funding_bias: Optional[str] = None  # "Bullish", "Bearish", "Neutral"
    open_interest_change_24h: Optional[float] = None  # Percentage change
    
    # AI Recommendation fields (GPT-4 Enhanced)
    ai_recommendation: Optional[str] = None  # "BUY", "HOLD", "SELL"
    ai_reasoning: Optional[str] = None  # Brief explanation
    ai_risk_assessment: Optional[str] = None  # "LOW", "MEDIUM", "HIGH"
    ai_confidence: Optional[float] = None  # Enhanced confidence from AI
    
    # Confidence and quality
    confidence: float = 0.0          # 0-100
    data_quality: float = 0.0        # 0-100
    analysis_depth: str = "Basic"    # "Basic", "Standard", "Comprehensive", "Advanced"
    
    # Key levels
    key_levels: Optional[Dict[str, float]] = None
    
    # Source attribution
    data_sources: Optional[List[str]] = None
    last_updated: Optional[datetime] = None
    
    # Adaptive thresholds info
    adaptive_thresholds_confidence: float = 0.0  # Confidence in adaptive thresholds

class EnhancedMarketStatusEngine:
    """
    Enhanced market status engine with improved accuracy
    Integrates enhanced technical indicators and adaptive regime detection
    """
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.last_analysis = {}
        
        # Configuration
        self.enable_social_sentiment = True
        self.enable_advanced_analysis = True
        self.enable_multi_timeframe = True
        self.enable_microstructure = True
        self.min_confidence_threshold = 60.0
        
    async def get_enhanced_market_status(
        self,
        symbol: Optional[str] = None,
        positions: Optional[List[Dict]] = None,
        chat_data: Optional[Dict] = None,
        enable_ai_analysis: bool = True
    ) -> EnhancedMarketStatus:
        """
        Get comprehensive market status analysis with enhanced accuracy
        """
        try:
            # Determine primary symbol
            primary_symbol = await self._determine_primary_symbol(symbol, positions)
            
            logger.info(f"🔍 Generating enhanced market status for {primary_symbol}")
            
            # Check cache first
            cache_key = f"enhanced_market_status_{primary_symbol}"
            if cache_key in self.cache:
                cached_data = self.cache[cache_key]
                if (datetime.now() - cached_data["timestamp"]).seconds < self.cache_ttl:
                    logger.info(f"📦 Using cached enhanced market status for {primary_symbol}")
                    return cached_data["status"]
            
            # Collect comprehensive data
            market_data, orderbook_data, multi_timeframe_data = await self._collect_comprehensive_data(
                primary_symbol
            )
            
            # Calculate enhanced technical indicators
            # Note: For 5m data, we'll need to fetch it separately or use 1h as primary
            kline_data = {
                "1h": market_data.kline_1h or [],
                "4h": market_data.kline_4h or [],
                "1d": market_data.kline_1d or []
            }
            
            # Get 5m data for more granular analysis if needed
            if self.enable_advanced_analysis:
                try:
                    from clients.bybit_client import bybit_client
                    kline_5m_response = bybit_client.get_kline(
                        category="linear",
                        symbol=primary_symbol,
                        interval="5",
                        limit=288  # Last 24 hours
                    )
                    if kline_5m_response.get("retCode") == 0:
                        kline_data["5m"] = kline_5m_response.get("result", {}).get("list", [])
                except Exception as e:
                    logger.debug(f"Could not get 5m kline data: {e}")
            
            technical_indicators = await enhanced_technical_analysis_engine.calculate_indicators(
                symbol=primary_symbol,
                kline_data=kline_data,
                current_price=market_data.current_price,
                volume_24h=market_data.volume_24h,
                orderbook_data=orderbook_data
            )
            
            # Get sentiment score
            sentiment_score = await self._get_enhanced_sentiment_score(
                primary_symbol, chat_data, technical_indicators
            )
            
            # Perform enhanced regime analysis
            regime_analysis = await enhanced_market_regime_detector.analyze_market_regime(
                symbol=primary_symbol,
                market_data=market_data,
                technical_indicators=technical_indicators,
                sentiment_score=sentiment_score,
                multi_timeframe_data=multi_timeframe_data,
                orderbook_data=orderbook_data
            )
            
            # Get AI analysis if enabled
            ai_recommendation = None
            ai_reasoning = None
            ai_risk_assessment = None
            ai_confidence = None
            
            if enable_ai_analysis:
                try:
                    from execution.ai_market_analysis import AIMarketAnalyzer
                    from clients.ai_client import get_ai_client
                    
                    ai_client = get_ai_client()
                    if ai_client and ai_client.llm_provider != "stub":
                        from clients.bybit_client import bybit_client
                        analyzer = AIMarketAnalyzer(bybit_client, ai_client)
                        
                        # Prepare enhanced position data
                        position_data = {
                            "symbol": primary_symbol,
                            "pnl_percentage": 0,
                            "technical_indicators": asdict(technical_indicators),
                            "regime_analysis": {
                                "regime": regime_analysis.regime.value,
                                "trend": regime_analysis.trend_direction.value,
                                "volatility": regime_analysis.volatility_level.value,
                                "momentum": regime_analysis.momentum_state.value,
                                "timeframe_confluence": regime_analysis.timeframe_confluence
                            }
                        }
                        
                        # Get AI market insight
                        insight = await analyzer.analyze_market(primary_symbol, position_data)
                        
                        if insight:
                            ai_recommendation = insight.recommendation
                            ai_reasoning = insight.ai_analysis
                            ai_risk_assessment = insight.risk_assessment
                            ai_confidence = insight.enhanced_confidence
                            
                            logger.info(f"🤖 AI Analysis: {ai_recommendation} - Confidence: {ai_confidence:.1f}%")
                except Exception as e:
                    logger.debug(f"Could not get AI analysis: {e}")
            
            # Generate enhanced status
            enhanced_status = self._generate_enhanced_status(
                primary_symbol, market_data, technical_indicators, regime_analysis,
                ai_recommendation, ai_reasoning, ai_risk_assessment, ai_confidence
            )
            
            # Cache the result
            self.cache[cache_key] = {
                "status": enhanced_status,
                "timestamp": datetime.now()
            }
            
            # Store for comparison
            self.last_analysis[primary_symbol] = enhanced_status
            
            logger.info(f"✅ Enhanced market status generated for {primary_symbol} - "
                       f"Confidence: {enhanced_status.confidence:.1f}%, "
                       f"Regime: {enhanced_status.market_regime}")
            
            return enhanced_status
            
        except Exception as e:
            logger.error(f"❌ Error generating enhanced market status: {e}")
            import traceback
            traceback.print_exc()
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
        symbol: str
    ) -> Tuple[MarketData, Optional[Dict], Optional[Dict]]:
        """Collect all necessary data for enhanced analysis"""
        
        # Get market data
        market_data = await market_data_collector.collect_market_data(symbol)
        
        # Get orderbook data for microstructure analysis
        orderbook_data = None
        if self.enable_microstructure:
            try:
                from clients.bybit_client import bybit_client
                orderbook_response = bybit_client.get_orderbook(
                    category="linear", symbol=symbol, limit=50
                )
                if orderbook_response.get("retCode") == 0:
                    orderbook_data = orderbook_response.get("result", {})
            except Exception as e:
                logger.debug(f"Could not get orderbook data: {e}")
        
        # Get multi-timeframe data
        multi_timeframe_data = None
        if self.enable_multi_timeframe:
            multi_timeframe_data = await self._collect_multi_timeframe_data(symbol)
        
        return market_data, orderbook_data, multi_timeframe_data
    
    async def _collect_multi_timeframe_data(self, symbol: str) -> Dict[str, Any]:
        """Collect data for multiple timeframes"""
        try:
            from clients.bybit_client import bybit_client
            
            timeframes = {
                "5m": "5",
                "15m": "15",
                "1h": "60",
                "4h": "240",
                "1d": "D"
            }
            
            multi_data = {}
            
            for tf_name, tf_value in timeframes.items():
                try:
                    response = bybit_client.get_kline(
                        category="linear",
                        symbol=symbol,
                        interval=tf_value,
                        limit=50
                    )
                    
                    if response.get("retCode") == 0:
                        klines = response.get("result", {}).get("list", [])
                        if klines and len(klines) >= 20:
                            # Calculate basic indicators for timeframe
                            closes = [float(k[4]) for k in klines]
                            sma_20 = sum(closes[-20:]) / 20
                            
                            multi_data[tf_name] = {
                                "close": closes[-1],
                                "sma_20": sma_20,
                                "trend": "up" if closes[-1] > sma_20 else "down"
                            }
                except Exception as e:
                    logger.debug(f"Error collecting {tf_name} data: {e}")
            
            return multi_data
            
        except Exception as e:
            logger.debug(f"Error collecting multi-timeframe data: {e}")
            return {}
    
    async def _get_enhanced_sentiment_score(
        self,
        symbol: str,
        chat_data: Optional[Dict],
        technical_indicators: EnhancedTechnicalIndicators
    ) -> Optional[float]:
        """Get enhanced sentiment score from multiple sources including real sentiment data"""
        try:
            # Get real sentiment from aggregator
            from .sentiment_aggregator import sentiment_aggregator
            
            real_sentiment = None
            real_sentiment_data = None
            
            try:
                async with sentiment_aggregator:
                    aggregated = await sentiment_aggregator.get_aggregated_sentiment(
                        symbol=symbol,
                        include_social=self.enable_social_sentiment
                    )
                    
                    if aggregated and aggregated.confidence > 0.5:
                        real_sentiment = aggregated.overall_score
                        real_sentiment_data = aggregated
                        
                        logger.info(f"📊 Real sentiment for {symbol}: {aggregated.overall_label} "
                                   f"({aggregated.overall_score:.1f}/100) - "
                                   f"Sources: {', '.join(aggregated.sources_used)}")
            except Exception as e:
                logger.debug(f"Could not get real sentiment: {e}")
            
            sentiment_sources = []
            
            # 1. Real sentiment data (highest priority)
            if real_sentiment is not None:
                # Add individual real sentiment sources
                if real_sentiment_data.fear_greed_score is not None:
                    sentiment_sources.append({
                        "score": real_sentiment_data.fear_greed_score,
                        "weight": 0.25,
                        "source": "fear_greed_index",
                        "confidence": 0.9
                    })
                
                if real_sentiment_data.funding_sentiment is not None:
                    sentiment_sources.append({
                        "score": real_sentiment_data.funding_sentiment,
                        "weight": 0.30,
                        "source": "funding_rate",
                        "confidence": 0.85
                    })
                
                if real_sentiment_data.oi_sentiment is not None:
                    sentiment_sources.append({
                        "score": real_sentiment_data.oi_sentiment,
                        "weight": 0.20,
                        "source": "open_interest",
                        "confidence": 0.7
                    })
                
                if real_sentiment_data.long_short_sentiment is not None:
                    sentiment_sources.append({
                        "score": real_sentiment_data.long_short_sentiment,
                        "weight": 0.15,
                        "source": "long_short_ratio",
                        "confidence": 0.6
                    })
                
                if real_sentiment_data.social_sentiment is not None:
                    sentiment_sources.append({
                        "score": real_sentiment_data.social_sentiment,
                        "weight": 0.10,
                        "source": "social_media",
                        "confidence": 0.5
                    })
            
            # 2. Technical sentiment (lower weight when real sentiment available)
            weight_multiplier = 0.3 if real_sentiment is not None else 1.0
            
            if technical_indicators:
                # MACD divergence sentiment
                if technical_indicators.macd_divergence:
                    divergence_score = 70 if technical_indicators.macd_divergence == "Bullish" else 30
                    sentiment_sources.append({
                        "score": divergence_score,
                        "weight": 0.2 * weight_multiplier,
                        "source": "macd_divergence",
                        "confidence": 0.8
                    })
                
                # VWAP sentiment
                if technical_indicators.vwap and technical_indicators.current_price:
                    vwap_position = (technical_indicators.current_price - technical_indicators.vwap) / technical_indicators.vwap * 100
                    vwap_sentiment = 50 + (vwap_position * 5)  # Convert to 0-100
                    sentiment_sources.append({
                        "score": max(0, min(100, vwap_sentiment)),
                        "weight": 0.15 * weight_multiplier,
                        "source": "vwap_analysis",
                        "confidence": 0.7
                    })
                
                # Cumulative delta sentiment
                if technical_indicators.cumulative_delta is not None:
                    delta_sentiment = 50 + technical_indicators.cumulative_delta
                    sentiment_sources.append({
                        "score": max(0, min(100, delta_sentiment)),
                        "weight": 0.25 * weight_multiplier,
                        "source": "order_flow",
                        "confidence": 0.9
                    })
            
            # 3. Historical performance sentiment (from chat data)
            if chat_data:
                try:
                    recent_pnl = chat_data.get('recent_pnl_trend', [])
                    if recent_pnl and len(recent_pnl) >= 5:
                        positive_trades = sum(1 for pnl in recent_pnl[-10:] if pnl > 0)
                        performance_sentiment = (positive_trades / len(recent_pnl[-10:])) * 100
                        
                        sentiment_sources.append({
                            "score": performance_sentiment,
                            "weight": 0.1 * weight_multiplier,
                            "source": "performance_history",
                            "confidence": 0.6
                        })
                except Exception as e:
                    logger.debug(f"Could not calculate performance sentiment: {e}")
            
            # Calculate weighted average
            if sentiment_sources:
                total_weight = sum(s["weight"] for s in sentiment_sources)
                if total_weight > 0:
                    weighted_score = sum(s["score"] * s["weight"] for s in sentiment_sources) / total_weight
                    
                    # Log sentiment composition
                    source_summary = ", ".join([f"{s['source']}:{s['score']:.1f}" for s in sentiment_sources])
                    logger.debug(f"Enhanced sentiment for {symbol}: {weighted_score:.1f} - {source_summary}")
                    
                    # Store real sentiment data for later use
                    if real_sentiment_data:
                        self.last_real_sentiment = {
                            symbol: real_sentiment_data
                        }
                    
                    return weighted_score
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating enhanced sentiment score: {e}")
            return None
    
    def _generate_enhanced_status(
        self,
        symbol: str,
        market_data: MarketData,
        technical_indicators: EnhancedTechnicalIndicators,
        regime_analysis: EnhancedMarketRegimeAnalysis,
        ai_recommendation: Optional[str] = None,
        ai_reasoning: Optional[str] = None,
        ai_risk_assessment: Optional[str] = None,
        ai_confidence: Optional[float] = None
    ) -> EnhancedMarketStatus:
        """Generate comprehensive enhanced market status"""
        
        # Format trend information
        trend_info = self._format_trend_info(regime_analysis.trend_direction)
        
        # Format volatility information
        volatility_info = self._format_volatility_info(regime_analysis.volatility_level)
        
        # Format momentum information
        momentum_info = self._format_momentum_info(regime_analysis.momentum_state)
        
        # Determine data sources
        data_sources = ["bybit_api", "enhanced_technical_analysis", "adaptive_regime_detection"]
        if regime_analysis.sentiment_score != 50:
            data_sources.append("multi_source_sentiment")
        if regime_analysis.microstructure:
            data_sources.append("market_microstructure")
        if regime_analysis.timeframe_alignment:
            data_sources.append("multi_timeframe_analysis")
        if ai_recommendation:
            data_sources.append("ai_reasoning_engine")
        
        # Determine analysis depth
        if technical_indicators.confidence > 90 and regime_analysis.confidence > 80:
            analysis_depth = "Advanced"
        elif technical_indicators.confidence > 80:
            analysis_depth = "Comprehensive"
        elif technical_indicators.confidence > 50:
            analysis_depth = "Standard"
        else:
            analysis_depth = "Basic"
        
        # Calculate VWAP distance
        vwap_distance = None
        if technical_indicators.vwap and market_data.current_price > 0:
            vwap_distance = ((market_data.current_price - technical_indicators.vwap) / 
                           technical_indicators.vwap) * 100
        
        # Get support/resistance info
        support_level = technical_indicators.major_support
        resistance_level = technical_indicators.major_resistance
        
        # Calculate support/resistance strength (based on volume nodes)
        support_strength = 50.0
        resistance_strength = 50.0
        
        if technical_indicators.volume_nodes:
            # Find strength based on volume concentration
            for node in technical_indicators.volume_nodes:
                if support_level and abs(node["price"] - support_level) < support_level * 0.01:
                    support_strength = min(100, 50 + node["strength"] * 10)
                if resistance_level and abs(node["price"] - resistance_level) < resistance_level * 0.01:
                    resistance_strength = min(100, 50 + node["strength"] * 10)
        
        # Determine volume profile
        volume_profile = None
        if technical_indicators.volume_ratio:
            if technical_indicators.volume_ratio > 2.0:
                volume_profile = "Very High"
            elif technical_indicators.volume_ratio > 1.5:
                volume_profile = "High"
            elif technical_indicators.volume_ratio < 0.5:
                volume_profile = "Low"
            else:
                volume_profile = "Normal"
        
        # Determine market structure and bias
        market_structure = "Consolidation"
        structure_bias = "Neutral"
        
        if regime_analysis.trend_direction.value.endswith("uptrend"):
            market_structure = "HH-HL"  # Higher Highs, Higher Lows
            structure_bias = "Bullish"
        elif regime_analysis.trend_direction.value.endswith("downtrend"):
            market_structure = "LH-LL"  # Lower Highs, Lower Lows
            structure_bias = "Bearish"
        
        # Get microstructure data
        bid_ask_spread = None
        order_book_imbalance = None
        liquidity_score = None
        
        if regime_analysis.microstructure:
            bid_ask_spread = regime_analysis.microstructure.bid_ask_spread
            order_book_imbalance = regime_analysis.microstructure.order_book_imbalance
            liquidity_score = regime_analysis.microstructure.liquidity_score
        
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
            volatility_percentage=(technical_indicators.atr_14 / market_data.current_price * 100) 
                                if technical_indicators.atr_14 and market_data.current_price else None,
            
            trend_direction=trend_info["direction"],
            trend_strength=technical_indicators.trend_strength or 0.0,
            trend_emoji=trend_info["emoji"],
            
            momentum_state=momentum_info["state"],
            momentum_score=technical_indicators.momentum_score or 0.0,
            momentum_emoji="⚡",
            
            # Advanced analysis
            market_regime=regime_analysis.regime.value.replace("_", " ").title(),
            regime_strength=regime_analysis.regime_strength,
            regime_transition_probability=regime_analysis.regime_transition_probability,
            volume_strength=technical_indicators.volume_strength or 50.0,
            
            # Multi-timeframe
            timeframe_alignment=regime_analysis.timeframe_alignment,
            timeframe_confluence=regime_analysis.timeframe_confluence,
            
            # Microstructure
            bid_ask_spread=bid_ask_spread,
            order_book_imbalance=order_book_imbalance,
            liquidity_score=liquidity_score,
            
            # Price info
            current_price=market_data.current_price,
            price_change_24h=market_data.price_24h_change,
            price_change_pct_24h=market_data.price_24h_change_pct,
            
            # Enhanced technical indicators
            macd_divergence=technical_indicators.macd_divergence,
            vwap=technical_indicators.vwap,
            vwap_distance=vwap_distance,
            poc=technical_indicators.poc,
            vah=technical_indicators.vah,
            val=technical_indicators.val,
            
            # Enhanced support/resistance
            support_level=support_level,
            resistance_level=resistance_level,
            support_strength=support_strength,
            resistance_strength=resistance_strength,
            
            # Volume analysis
            volume_profile=volume_profile,
            volume_ratio=technical_indicators.volume_ratio,
            cumulative_delta=technical_indicators.cumulative_delta,
            delta_trend=technical_indicators.delta_trend,
            
            # Market structure
            market_structure=market_structure,
            structure_bias=structure_bias,
            
            # Funding and OI (from market data if available)
            funding_rate=market_data.funding_rate if hasattr(market_data, 'funding_rate') else None,
            funding_bias="Bullish" if market_data.funding_rate and market_data.funding_rate > 0.01 
                        else "Bearish" if market_data.funding_rate and market_data.funding_rate < -0.01 
                        else "Neutral" if market_data.funding_rate else None,
            open_interest_change_24h=market_data.open_interest_change_24h 
                                   if hasattr(market_data, 'open_interest_change_24h') else None,
            
            # AI Recommendation fields
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
            last_updated=datetime.now(),
            
            # Adaptive thresholds info
            adaptive_thresholds_confidence=regime_analysis.thresholds_used.confidence 
                                         if regime_analysis.thresholds_used else 0.0
        )
    
    def _format_trend_info(self, trend_direction) -> Dict[str, str]:
        """Format trend direction and emoji"""
        direction_map = {
            "strong_uptrend": {"direction": "Strong Uptrend", "emoji": "🚀"},
            "uptrend": {"direction": "Uptrend", "emoji": "📈"},
            "ranging": {"direction": "Ranging", "emoji": "↔️"},
            "downtrend": {"direction": "Downtrend", "emoji": "📉"},
            "strong_downtrend": {"direction": "Strong Downtrend", "emoji": "💥"}
        }
        
        trend_key = trend_direction.value if hasattr(trend_direction, 'value') else str(trend_direction)
        return direction_map.get(trend_key, {"direction": "Ranging", "emoji": "↔️"})
    
    def _format_volatility_info(self, volatility_level) -> Dict[str, str]:
        """Format volatility level"""
        level_map = {
            "very_low": "Very Low",
            "low": "Low", 
            "normal": "Normal",
            "high": "High",
            "very_high": "Very High",
            "extreme": "Extreme"
        }
        
        vol_key = volatility_level.value if hasattr(volatility_level, 'value') else str(volatility_level)
        return {"level": level_map.get(vol_key, "Normal")}
    
    def _format_momentum_info(self, momentum_state) -> Dict[str, str]:
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
            regime_transition_probability=50.0,
            volume_strength=50.0,
            current_price=0.0,
            price_change_24h=0.0,
            price_change_pct_24h=0.0,
            confidence=0.0,
            data_quality=0.0,
            analysis_depth="Basic",
            key_levels={},
            data_sources=["fallback"],
            last_updated=datetime.now(),
            adaptive_thresholds_confidence=0.0
        )
    
    def get_enhanced_market_status_summary(self, status: EnhancedMarketStatus) -> str:
        """Generate a formatted summary string for display"""
        confidence_indicator = "🔴" if status.confidence < 50 else "🟡" if status.confidence < 80 else "🟢"
        
        # Build enhanced summary
        summary_lines = [
            f"🌍 <b>ENHANCED MARKET STATUS</b> ({status.symbol})",
            f"{status.sentiment_emoji} Sentiment: {status.sentiment_label} ({status.sentiment_score:.0f}/100)",
            f"{status.volatility_emoji} Volatility: {status.volatility_level}"
        ]
        
        if status.volatility_percentage:
            summary_lines[-1] += f" ({status.volatility_percentage:.2f}%)"
        
        summary_lines.extend([
            f"{status.trend_emoji} Trend: {status.trend_direction} (Strength: {abs(status.trend_strength):.0f})",
            f"{status.momentum_emoji} Momentum: {status.momentum_state}"
        ])
        
        # Multi-timeframe confluence if available
        if status.timeframe_confluence > 0:
            confluence_emoji = "🔥" if status.timeframe_confluence > 80 else "✅" if status.timeframe_confluence > 60 else "⚠️"
            summary_lines.append(f"{confluence_emoji} Timeframe Alignment: {status.timeframe_confluence:.0f}%")
        
        summary_lines.extend([
            "",
            f"🔍 Regime: {status.market_regime} ({status.regime_strength:.0f}% strength)"
        ])
        
        # Transition probability if significant
        if status.regime_transition_probability > 50:
            summary_lines.append(f"⚠️ Regime Change Probability: {status.regime_transition_probability:.0f}%")
        
        # AI recommendation if available
        if status.ai_recommendation:
            risk_emoji = "🟢" if status.ai_risk_assessment == "LOW" else "🟡" if status.ai_risk_assessment == "MEDIUM" else "🔴"
            summary_lines.extend([
                "",
                f"🤖 AI: {status.ai_recommendation} {risk_emoji} Risk: {status.ai_risk_assessment}"
            ])
            if status.ai_confidence:
                summary_lines[-1] += f" ({status.ai_confidence:.0f}% confidence)"
        
        # Key levels if available
        if status.support_level and status.resistance_level:
            summary_lines.extend([
                "",
                f"📊 Support: ${status.support_level:,.2f} | Resistance: ${status.resistance_level:,.2f}"
            ])
        
        # VWAP if available
        if status.vwap and status.vwap_distance is not None:
            vwap_emoji = "⬆️" if status.vwap_distance > 0 else "⬇️"
            summary_lines.append(f"📈 VWAP: ${status.vwap:,.2f} {vwap_emoji} {abs(status.vwap_distance):.1f}%")
        
        # Order flow if available
        if status.cumulative_delta is not None:
            delta_emoji = "🟢" if status.cumulative_delta > 10 else "🔴" if status.cumulative_delta < -10 else "⚪"
            summary_lines.append(f"{delta_emoji} Order Flow: {status.delta_trend} ({status.cumulative_delta:.1f})")
        
        summary_lines.extend([
            "",
            f"{confidence_indicator} Confidence: {status.confidence:.0f}% | Analysis: {status.analysis_depth}",
            f"⏱️ Updated: {status.last_updated.strftime('%H:%M:%S')}"
        ])
        
        return "\n".join(summary_lines)

# Global instance
enhanced_market_status_engine = EnhancedMarketStatusEngine()