#!/usr/bin/env python3
"""
Market Conditions Analyzer for Trade Entry Filtering
Analyzes volatility periods and liquidity to optimize trade timing and R:R ratio
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple
from enum import Enum

from clients.bybit_client import bybit_client
from utils.cache import enhanced_cache as cache

logger = logging.getLogger(__name__)

class MarketCondition(Enum):
    """Market condition ratings"""
    EXCELLENT = "excellent"      # Best conditions for trading
    GOOD = "good"                # Good conditions, proceed normally
    MODERATE = "moderate"        # Acceptable but not ideal
    POOR = "poor"                # Poor conditions, consider waiting
    AVOID = "avoid"              # Should avoid trading

class VolatilityLevel(Enum):
    """Volatility classification"""
    EXTREME = "extreme"          # >5% in 1hr - Too volatile
    HIGH = "high"                # 2-5% in 1hr - Good for trading
    NORMAL = "normal"            # 0.5-2% in 1hr - Standard
    LOW = "low"                  # <0.5% in 1hr - Poor for TP targets

class LiquidityLevel(Enum):
    """Liquidity classification"""
    EXCELLENT = "excellent"      # >$100M 24h volume
    GOOD = "good"                # $50-100M 24h volume  
    MODERATE = "moderate"        # $10-50M 24h volume
    LOW = "low"                  # $5-10M 24h volume
    POOR = "poor"                # <$5M 24h volume

class MarketConditionsAnalyzer:
    """Analyzes market conditions for optimal trade entry"""
    
    def __init__(self):
        self.cache = cache
        self.cache_ttl = 60  # 1 minute cache for market conditions
        
    async def analyze_trading_conditions(self, symbol: str) -> Dict[str, Any]:
        """
        Comprehensive analysis of current trading conditions
        Returns recommendations for trade entry timing
        """
        try:
            # Check cache first
            cache_key = f"market_conditions:{symbol}"
            cached = self.cache.get(cache_key)
            if cached:
                logger.debug(f"Using cached market conditions for {symbol}")
                return cached
            
            # Fetch market data
            kline_data = await self._fetch_kline_data(symbol)
            ticker_data = await self._fetch_ticker_data(symbol)
            
            # Analyze components
            volatility_analysis = self._analyze_volatility(kline_data)
            liquidity_analysis = self._analyze_liquidity(ticker_data)
            timing_analysis = self._analyze_market_timing()
            
            # Calculate overall condition
            overall_condition = self._calculate_overall_condition(
                volatility_analysis, 
                liquidity_analysis,
                timing_analysis
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                overall_condition,
                volatility_analysis,
                liquidity_analysis,
                timing_analysis
            )
            
            result = {
                "symbol": symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_condition": overall_condition.value,
                "volatility": volatility_analysis,
                "liquidity": liquidity_analysis,
                "timing": timing_analysis,
                "recommendations": recommendations,
                "can_trade": overall_condition not in [MarketCondition.POOR, MarketCondition.AVOID],
                "wait_recommended": overall_condition in [MarketCondition.POOR, MarketCondition.AVOID],
                "confidence": self._calculate_confidence(volatility_analysis, liquidity_analysis)
            }
            
            # Cache result
            self.cache.set(cache_key, result, ttl=self.cache_ttl)
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing market conditions for {symbol}: {e}")
            return self._get_fallback_conditions(symbol)
    
    async def _fetch_kline_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch recent kline data for volatility analysis"""
        try:
            # Get 1-hour and 5-minute klines
            response_1h = bybit_client.get_kline(
                category="linear",
                symbol=symbol,
                interval="60",  # 1 hour
                limit=24  # Last 24 hours
            )
            
            response_5m = bybit_client.get_kline(
                category="linear",
                symbol=symbol,
                interval="5",  # 5 minutes
                limit=24  # Last 2 hours
            )
            
            return {
                "1h": response_1h.get("result", {}).get("list", []),
                "5m": response_5m.get("result", {}).get("list", [])
            }
        except Exception as e:
            logger.error(f"Error fetching kline data: {e}")
            return {"1h": [], "5m": []}
    
    async def _fetch_ticker_data(self, symbol: str) -> Dict[str, Any]:
        """Fetch ticker data for liquidity analysis"""
        try:
            response = bybit_client.get_tickers(
                category="linear",
                symbol=symbol
            )
            
            if response.get("result", {}).get("list"):
                return response["result"]["list"][0]
            return {}
        except Exception as e:
            logger.error(f"Error fetching ticker data: {e}")
            return {}
    
    def _analyze_volatility(self, kline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market volatility"""
        try:
            hourly_candles = kline_data.get("1h", [])
            five_min_candles = kline_data.get("5m", [])
            
            if not hourly_candles:
                return {
                    "level": VolatilityLevel.NORMAL.value,
                    "percentage": 1.0,
                    "trend": "unknown",
                    "suitable": True
                }
            
            # Calculate 1-hour volatility
            latest_candle = hourly_candles[0]
            high = float(latest_candle[2])  # High price
            low = float(latest_candle[3])   # Low price
            close = float(latest_candle[4]) # Close price
            
            volatility_pct = ((high - low) / close) * 100 if close > 0 else 0
            
            # Calculate average volatility over 24h
            total_volatility = 0
            for candle in hourly_candles[:24]:
                h = float(candle[2])
                l = float(candle[3])
                c = float(candle[4])
                if c > 0:
                    total_volatility += ((h - l) / c) * 100
            
            avg_volatility = total_volatility / min(len(hourly_candles), 24) if hourly_candles else 1.0
            
            # Determine volatility level
            if volatility_pct > 5:
                level = VolatilityLevel.EXTREME
                suitable = False  # Too volatile
            elif volatility_pct > 2:
                level = VolatilityLevel.HIGH
                suitable = True  # Good for R:R
            elif volatility_pct > 0.5:
                level = VolatilityLevel.NORMAL
                suitable = True
            else:
                level = VolatilityLevel.LOW
                suitable = False  # Too quiet for good R:R
            
            # Analyze trend from 5-minute candles
            trend = self._analyze_micro_trend(five_min_candles)
            
            return {
                "level": level.value,
                "percentage": round(volatility_pct, 2),
                "avg_24h": round(avg_volatility, 2),
                "trend": trend,
                "suitable": suitable,
                "message": self._get_volatility_message(level, volatility_pct)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing volatility: {e}")
            return {
                "level": VolatilityLevel.NORMAL.value,
                "percentage": 1.0,
                "trend": "unknown",
                "suitable": True
            }
    
    def _analyze_liquidity(self, ticker_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze market liquidity"""
        try:
            # Get 24h volume in USDT
            volume_24h = float(ticker_data.get("turnover24h", 0))
            
            # Get bid-ask spread
            bid = float(ticker_data.get("bid1Price", 0))
            ask = float(ticker_data.get("ask1Price", 0))
            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
            spread_pct = ((ask - bid) / mid * 100) if mid > 0 else 0
            
            # Determine liquidity level
            if volume_24h > 100_000_000:  # >$100M
                level = LiquidityLevel.EXCELLENT
                suitable = True
            elif volume_24h > 50_000_000:  # >$50M
                level = LiquidityLevel.GOOD
                suitable = True
            elif volume_24h > 10_000_000:  # >$10M
                level = LiquidityLevel.MODERATE
                suitable = True
            elif volume_24h > 5_000_000:   # >$5M
                level = LiquidityLevel.LOW
                suitable = False  # Caution
            else:
                level = LiquidityLevel.POOR
                suitable = False  # Avoid
            
            return {
                "level": level.value,
                "volume_24h": volume_24h,
                "volume_24h_formatted": f"${volume_24h/1_000_000:.1f}M",
                "spread_percentage": round(spread_pct, 4),
                "suitable": suitable,
                "message": self._get_liquidity_message(level, volume_24h, spread_pct)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing liquidity: {e}")
            return {
                "level": LiquidityLevel.MODERATE.value,
                "volume_24h": 0,
                "spread_percentage": 0,
                "suitable": True
            }
    
    def _analyze_market_timing(self) -> Dict[str, Any]:
        """Analyze current market session and timing"""
        now = datetime.now(timezone.utc)
        hour = now.hour
        day = now.weekday()  # 0=Monday, 6=Sunday
        
        # Define market sessions (UTC)
        # Asian: 00:00-08:00 UTC
        # European: 07:00-16:00 UTC  
        # US: 13:00-22:00 UTC
        
        sessions = []
        if 0 <= hour < 8:
            sessions.append("Asian")
        if 7 <= hour < 16:
            sessions.append("European")
        if 13 <= hour < 22:
            sessions.append("US")
        
        # Best trading hours (high liquidity overlap)
        is_optimal = False
        timing_score = 50  # Base score
        
        # European-US overlap (13:00-16:00 UTC) - Best liquidity
        if 13 <= hour < 16:
            is_optimal = True
            timing_score = 100
            timing_quality = "Excellent - EU/US overlap"
        # Asian-European overlap (07:00-08:00 UTC) - Good liquidity
        elif 7 <= hour < 8:
            timing_score = 80
            timing_quality = "Good - Asia/EU overlap"
        # Core US session (16:00-20:00 UTC)
        elif 16 <= hour < 20:
            timing_score = 75
            timing_quality = "Good - US session"
        # Core European session (08:00-13:00 UTC)
        elif 8 <= hour < 13:
            timing_score = 70
            timing_quality = "Good - EU session"
        # Weekend - Lower liquidity
        elif day >= 5:  # Saturday or Sunday
            timing_score = 30
            timing_quality = "Poor - Weekend"
        # Off-hours
        else:
            timing_score = 40
            timing_quality = "Moderate - Off-peak"
        
        return {
            "current_sessions": sessions,
            "is_optimal": is_optimal,
            "timing_score": timing_score,
            "timing_quality": timing_quality,
            "hour_utc": hour,
            "day_of_week": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][day],
            "suitable": timing_score >= 50
        }
    
    def _analyze_micro_trend(self, five_min_candles: list) -> str:
        """Analyze short-term trend from 5-minute candles"""
        if not five_min_candles or len(five_min_candles) < 3:
            return "neutral"
        
        try:
            # Get last 3 candle closes
            closes = [float(candle[4]) for candle in five_min_candles[:3]]
            
            # Simple trend detection
            if closes[0] > closes[1] > closes[2]:
                return "bullish"
            elif closes[0] < closes[1] < closes[2]:
                return "bearish"
            else:
                return "neutral"
        except:
            return "neutral"
    
    def _calculate_overall_condition(self, volatility: Dict, liquidity: Dict, timing: Dict) -> MarketCondition:
        """Calculate overall market condition rating"""
        score = 0
        weight_total = 0
        
        # Volatility weight: 35%
        if volatility["suitable"]:
            if volatility["level"] == VolatilityLevel.HIGH.value:
                score += 35  # Perfect for R:R
            else:
                score += 25  # Acceptable
        weight_total += 35
        
        # Liquidity weight: 40%
        if liquidity["suitable"]:
            if liquidity["level"] == LiquidityLevel.EXCELLENT.value:
                score += 40
            elif liquidity["level"] == LiquidityLevel.GOOD.value:
                score += 30
            else:
                score += 20
        weight_total += 40
        
        # Timing weight: 25%
        score += (timing["timing_score"] / 100) * 25
        weight_total += 25
        
        # Calculate percentage
        overall_score = (score / weight_total) * 100 if weight_total > 0 else 50
        
        # Determine condition
        if overall_score >= 80:
            return MarketCondition.EXCELLENT
        elif overall_score >= 60:
            return MarketCondition.GOOD
        elif overall_score >= 40:
            return MarketCondition.MODERATE
        elif overall_score >= 20:
            return MarketCondition.POOR
        else:
            return MarketCondition.AVOID
    
    def _generate_recommendations(self, condition: MarketCondition, volatility: Dict, 
                                 liquidity: Dict, timing: Dict) -> Dict[str, Any]:
        """Generate trading recommendations based on conditions"""
        recommendations = {
            "action": "proceed",
            "warnings": [],
            "suggestions": [],
            "expected_rr_impact": "normal"
        }
        
        # Overall condition recommendations
        if condition == MarketCondition.EXCELLENT:
            recommendations["action"] = "proceed"
            recommendations["message"] = "✅ Excellent trading conditions! High probability of achieving target R:R."
            recommendations["expected_rr_impact"] = "enhanced"
        elif condition == MarketCondition.GOOD:
            recommendations["action"] = "proceed"
            recommendations["message"] = "👍 Good trading conditions. Proceed with normal position size."
            recommendations["expected_rr_impact"] = "normal"
        elif condition == MarketCondition.MODERATE:
            recommendations["action"] = "proceed_with_caution"
            recommendations["message"] = "⚠️ Moderate conditions. Consider reducing position size."
            recommendations["expected_rr_impact"] = "slightly_reduced"
        elif condition == MarketCondition.POOR:
            recommendations["action"] = "wait"
            recommendations["message"] = "❌ Poor trading conditions. Consider waiting for better setup."
            recommendations["expected_rr_impact"] = "significantly_reduced"
        else:
            recommendations["action"] = "avoid"
            recommendations["message"] = "🚫 Avoid trading now. Very poor conditions for achieving R:R targets."
            recommendations["expected_rr_impact"] = "poor"
        
        # Specific warnings
        if not volatility["suitable"]:
            if volatility["level"] == VolatilityLevel.EXTREME.value:
                recommendations["warnings"].append("⚠️ Extreme volatility - Higher risk of stopout")
            elif volatility["level"] == VolatilityLevel.LOW.value:
                recommendations["warnings"].append("⚠️ Low volatility - TP targets may take longer")
        
        if not liquidity["suitable"]:
            recommendations["warnings"].append(f"⚠️ Low liquidity ({liquidity['volume_24h_formatted']}) - Expect slippage")
        
        if not timing["suitable"]:
            recommendations["warnings"].append(f"⚠️ Off-peak hours - {timing['timing_quality']}")
        
        # Suggestions for improvement
        if condition in [MarketCondition.POOR, MarketCondition.AVOID]:
            if timing["timing_score"] < 50:
                next_good_session = self._get_next_good_session()
                recommendations["suggestions"].append(f"💡 Try again during {next_good_session}")
            
            if liquidity["level"] in [LiquidityLevel.LOW.value, LiquidityLevel.POOR.value]:
                recommendations["suggestions"].append("💡 Consider more liquid pairs (BTC, ETH)")
            
            if volatility["level"] == VolatilityLevel.LOW.value:
                recommendations["suggestions"].append("💡 Wait for volatility to increase (news/events)")
        
        return recommendations
    
    def _get_next_good_session(self) -> str:
        """Get the next optimal trading session"""
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        if hour < 7:
            return "Asian-European overlap (07:00 UTC)"
        elif hour < 13:
            return "European-US overlap (13:00 UTC)"
        elif hour < 22:
            return "current US session"
        else:
            return "Asian session (00:00 UTC)"
    
    def _calculate_confidence(self, volatility: Dict, liquidity: Dict) -> float:
        """Calculate confidence score for the analysis"""
        confidence = 50.0  # Base confidence
        
        # Add confidence based on data availability
        if volatility.get("percentage", 0) > 0:
            confidence += 25
        if liquidity.get("volume_24h", 0) > 0:
            confidence += 25
        
        return min(confidence, 100.0)
    
    def _get_volatility_message(self, level: VolatilityLevel, percentage: float) -> str:
        """Get descriptive message for volatility level"""
        messages = {
            VolatilityLevel.EXTREME: f"🔴 Extreme volatility ({percentage:.1f}%) - High risk",
            VolatilityLevel.HIGH: f"🟢 High volatility ({percentage:.1f}%) - Excellent for R:R",
            VolatilityLevel.NORMAL: f"🟡 Normal volatility ({percentage:.1f}%) - Standard conditions",
            VolatilityLevel.LOW: f"🔴 Low volatility ({percentage:.1f}%) - Poor for targets"
        }
        return messages.get(level, f"Volatility: {percentage:.1f}%")
    
    def _get_liquidity_message(self, level: LiquidityLevel, volume: float, spread: float) -> str:
        """Get descriptive message for liquidity level"""
        volume_str = f"${volume/1_000_000:.1f}M"
        messages = {
            LiquidityLevel.EXCELLENT: f"🟢 Excellent liquidity ({volume_str}) - Minimal slippage",
            LiquidityLevel.GOOD: f"🟢 Good liquidity ({volume_str}) - Low slippage",
            LiquidityLevel.MODERATE: f"🟡 Moderate liquidity ({volume_str}) - Some slippage",
            LiquidityLevel.LOW: f"🟠 Low liquidity ({volume_str}) - Expect slippage",
            LiquidityLevel.POOR: f"🔴 Poor liquidity ({volume_str}) - High slippage risk"
        }
        return messages.get(level, f"Volume: {volume_str}")
    
    def _get_fallback_conditions(self, symbol: str) -> Dict[str, Any]:
        """Return fallback conditions when analysis fails"""
        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_condition": MarketCondition.MODERATE.value,
            "can_trade": True,
            "wait_recommended": False,
            "recommendations": {
                "action": "proceed_with_caution",
                "message": "⚠️ Could not analyze conditions. Proceed with caution.",
                "warnings": ["Unable to fetch complete market data"],
                "suggestions": [],
                "expected_rr_impact": "unknown"
            },
            "confidence": 25.0
        }
    
    def format_conditions_message(self, analysis: Dict[str, Any]) -> str:
        """Format market conditions analysis for display"""
        lines = []
        
        # Header
        condition = analysis["overall_condition"]
        emoji = "🟢" if condition == "excellent" else "🟡" if condition in ["good", "moderate"] else "🔴"
        lines.append(f"{emoji} <b>Market Conditions: {condition.upper()}</b>")
        lines.append("")
        
        # Volatility
        vol = analysis.get("volatility", {})
        lines.append(f"📊 <b>Volatility:</b> {vol.get('message', 'N/A')}")
        
        # Liquidity
        liq = analysis.get("liquidity", {})
        lines.append(f"💧 <b>Liquidity:</b> {liq.get('message', 'N/A')}")
        
        # Timing
        tim = analysis.get("timing", {})
        lines.append(f"⏰ <b>Timing:</b> {tim.get('timing_quality', 'N/A')}")
        
        # Recommendation
        rec = analysis.get("recommendations", {})
        lines.append("")
        lines.append(rec.get("message", ""))
        
        # Warnings
        if rec.get("warnings"):
            lines.append("")
            for warning in rec["warnings"]:
                lines.append(warning)
        
        # Suggestions
        if rec.get("suggestions"):
            lines.append("")
            for suggestion in rec["suggestions"]:
                lines.append(suggestion)
        
        return "\n".join(lines)


# Global instance
market_conditions_analyzer = MarketConditionsAnalyzer()