#!/usr/bin/env python3
"""
Dashboard Widgets for Social Media Sentiment
UI components for displaying sentiment data
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SentimentWidgets:
    def __init__(self):
        """Initialize sentiment widgets"""
        self.emoji_map = {
            'BULLISH': '🟢',
            'POSITIVE': '🟢', 
            'BEARISH': '🔴',
            'NEGATIVE': '🔴',
            'NEUTRAL': '🟡',
            'UNKNOWN': '⚪'
        }
        
        self.signal_emojis = {
            'STRONG_BUY': '🚀',
            'BUY': '⬆️',
            'WEAK_BUY': '↗️',
            'NEUTRAL': '➡️',
            'WEAK_SELL': '↘️',
            'SELL': '⬇️',
            'STRONG_SELL': '💥'
        }
    
    def format_sentiment_summary(self, sentiment_data: Dict[str, Any]) -> str:
        """Format overall sentiment summary"""
        try:
            overall_sentiment = sentiment_data.get('overall_sentiment', 'NEUTRAL')
            sentiment_score = sentiment_data.get('sentiment_score', 50)
            confidence = sentiment_data.get('confidence', 0)
            data_quality = sentiment_data.get('data_quality', 'unknown')
            
            emoji = self.emoji_map.get(overall_sentiment, '⚪')
            
            summary = f"{emoji} **{overall_sentiment}** ({sentiment_score}/100)\n"
            summary += f"📊 Confidence: {confidence}% | Quality: {data_quality.title()}"
            
            return summary
            
        except Exception as e:
            logger.error(f"Error formatting sentiment summary: {e}")
            return "❌ Sentiment data unavailable"
    
    def format_platform_breakdown(self, platform_sentiments: Dict[str, Any]) -> str:
        """Format platform-by-platform breakdown"""
        try:
            if not platform_sentiments:
                return "📱 No platform data available"
            
            breakdown = "📱 **Platform Breakdown:**\n"
            
            for platform, data in platform_sentiments.items():
                platform_sentiment = data.get('sentiment', 'NEUTRAL')
                platform_score = data.get('sentiment_score', 50)
                items_count = data.get('items_analyzed', 0)
                confidence = data.get('confidence', 0)
                
                emoji = self.emoji_map.get(platform_sentiment, '⚪')
                platform_name = platform.title()
                
                breakdown += f"{emoji} {platform_name}: {platform_sentiment} ({platform_score}/100) - {items_count} items (conf: {confidence}%)\n"
            
            return breakdown.rstrip()
            
        except Exception as e:
            logger.error(f"Error formatting platform breakdown: {e}")
            return "❌ Platform breakdown unavailable"
    
    def format_trending_topics(self, trends: Dict[str, Any]) -> str:
        """Format trending topics display"""
        try:
            if not trends:
                return "📈 No trending data available"
            
            trending_section = "📈 **Trending Topics:**\n"
            
            # Emerging trends
            emerging_trends = trends.get('emerging_trends', [])
            if emerging_trends:
                trending_section += "🔥 **Emerging Trends:**\n"
                for trend in emerging_trends[:3]:  # Top 3
                    topic = trend.get('topic', 'Unknown')
                    strength = trend.get('strength', 0)
                    mentions = trend.get('mentions', 0)
                    
                    strength_bar = self._create_strength_bar(strength)
                    trending_section += f"  • {topic} {strength_bar} ({mentions} mentions)\n"
            
            # Top keywords
            keywords = trends.get('keywords', {})
            if keywords:
                trending_section += "\n🔤 **Top Keywords:**\n"
                top_keywords = list(keywords.items())[:5]
                for keyword, count in top_keywords:
                    trending_section += f"  • {keyword} ({count})\n"
            
            # Top hashtags
            hashtags = trends.get('hashtags', {})
            if hashtags:
                trending_section += "\n#️⃣ **Trending Hashtags:**\n"
                top_hashtags = list(hashtags.items())[:3]
                hashtag_list = [f"{hashtag} ({count})" for hashtag, count in top_hashtags]
                trending_section += "  " + " | ".join(hashtag_list) + "\n"
            
            return trending_section.rstrip()
            
        except Exception as e:
            logger.error(f"Error formatting trending topics: {e}")
            return "❌ Trending topics unavailable"
    
    def format_signals(self, signals: Dict[str, Any]) -> str:
        """Format trading signals display"""
        try:
            if not signals:
                return "🎯 No signal data available"
            
            primary_signal = signals.get('primary_signal', 'NEUTRAL')
            signal_strength = signals.get('signal_strength', 0)
            confidence = signals.get('confidence', 0)
            risk_level = signals.get('risk_level', 'HIGH')
            
            signal_emoji = self.signal_emojis.get(primary_signal, '➡️')
            strength_bar = self._create_strength_bar(signal_strength)
            
            signals_section = "🎯 **Trading Signals:**\n"
            signals_section += f"{signal_emoji} **{primary_signal}** {strength_bar}\n"
            signals_section += f"📊 Strength: {signal_strength:.0%} | Confidence: {confidence}% | Risk: {risk_level}\n"
            
            # Signal details
            signal_details = signals.get('signal_details', [])
            if signal_details:
                signals_section += "\n💡 **Analysis:**\n"
                for detail in signal_details[:3]:  # Top 3 details
                    signals_section += f"  • {detail}\n"
            
            # Recommendations
            recommendations = signals.get('recommendations', [])
            if recommendations:
                signals_section += "\n📋 **Recommendations:**\n"
                for rec in recommendations[:2]:  # Top 2 recommendations
                    signals_section += f"  • {rec}\n"
            
            # Warnings
            warnings = signals.get('warnings', [])
            if warnings:
                signals_section += "\n⚠️ **Warnings:**\n"
                for warning in warnings[:2]:  # Top 2 warnings
                    signals_section += f"  • {warning}\n"
            
            return signals_section.rstrip()
            
        except Exception as e:
            logger.error(f"Error formatting signals: {e}")
            return "❌ Signal data unavailable"
    
    def format_market_conditions(self, market_conditions: Dict[str, Any]) -> str:
        """Format market conditions display"""
        try:
            if not market_conditions:
                return "🌡️ Market conditions unavailable"
            
            market_mood = market_conditions.get('market_mood', 'NEUTRAL')
            volatility = market_conditions.get('volatility_expectation', 'MEDIUM')
            fomo_level = market_conditions.get('fomo_level', 'LOW')
            fear_level = market_conditions.get('fear_level', 'LOW')
            
            mood_emoji = self.emoji_map.get(market_mood, '⚪')
            
            conditions_section = "🌡️ **Market Conditions:**\n"
            conditions_section += f"{mood_emoji} Mood: {market_mood} | Volatility: {volatility}\n"
            conditions_section += f"😱 FOMO: {fomo_level} | 😰 Fear: {fear_level}\n"
            
            return conditions_section
            
        except Exception as e:
            logger.error(f"Error formatting market conditions: {e}")
            return "❌ Market conditions unavailable"
    
    def format_data_quality_info(self, sentiment_data: Dict[str, Any], 
                                platform_sentiments: Dict[str, Any]) -> str:
        """Format data quality and collection info"""
        try:
            timestamp = sentiment_data.get('timestamp', '')
            collection_time = sentiment_data.get('collection_summary', {}).get('collection_time', 0)
            total_items = sentiment_data.get('collection_summary', {}).get('total_items_collected', 0)
            
            quality_section = "📊 **Data Quality:**\n"
            
            # Timestamp
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    time_str = dt.strftime('%H:%M %d/%m')
                    quality_section += f"🕐 Last updated: {time_str}\n"
                except:
                    quality_section += f"🕐 Last updated: {timestamp[:16]}\n"
            
            # Collection stats
            if collection_time > 0:
                quality_section += f"⏱️ Collection time: {collection_time:.1f}s\n"
            
            if total_items > 0:
                quality_section += f"📦 Items analyzed: {total_items}\n"
            
            # Platform count
            platform_count = len(platform_sentiments) if platform_sentiments else 0
            quality_section += f"📱 Active platforms: {platform_count}/5\n"
            
            return quality_section.rstrip()
            
        except Exception as e:
            logger.error(f"Error formatting data quality info: {e}")
            return "📊 Data quality info unavailable"
    
    def format_compact_summary(self, sentiment_data: Dict[str, Any]) -> str:
        """Format a compact one-line summary"""
        try:
            overall_sentiment = sentiment_data.get('overall_sentiment', 'NEUTRAL')
            sentiment_score = sentiment_data.get('sentiment_score', 50)
            confidence = sentiment_data.get('confidence', 0)
            
            emoji = self.emoji_map.get(overall_sentiment, '⚪')
            
            return f"{emoji} {overall_sentiment} ({sentiment_score}/100, {confidence}% conf)"
            
        except Exception as e:
            logger.error(f"Error formatting compact summary: {e}")
            return "❌ Sentiment unavailable"
    
    def format_historical_trend(self, trend_analysis: Dict[str, Any]) -> str:
        """Format historical trend analysis"""
        try:
            if not trend_analysis:
                return "📈 Historical trend unavailable"
            
            trend_direction = trend_analysis.get('trend_direction', 'STABLE')
            trend_strength = trend_analysis.get('trend_strength', 0)
            average_sentiment = trend_analysis.get('average_sentiment', 50)
            volatility = trend_analysis.get('volatility', 0)
            data_points = trend_analysis.get('data_points', 0)
            
            trend_section = "📈 **Historical Trend:**\n"
            
            # Trend direction with emoji
            if trend_direction == 'IMPROVING':
                trend_emoji = '📈'
            elif trend_direction == 'DECLINING':
                trend_emoji = '📉'
            else:
                trend_emoji = '➡️'
            
            trend_section += f"{trend_emoji} Direction: {trend_direction} (strength: {trend_strength:.0%})\n"
            trend_section += f"📊 Avg sentiment: {average_sentiment:.0f}/100\n"
            trend_section += f"📊 Volatility: {self._format_volatility_level(volatility)}\n"
            trend_section += f"📦 Data points: {data_points}\n"
            
            return trend_section.rstrip()
            
        except Exception as e:
            logger.error(f"Error formatting historical trend: {e}")
            return "❌ Historical trend unavailable"
    
    def _create_strength_bar(self, strength: float, length: int = 5) -> str:
        """Create a visual strength bar"""
        try:
            filled = int(strength * length)
            bar = '█' * filled + '░' * (length - filled)
            return f"[{bar}]"
        except:
            return "[░░░░░]"
    
    def _format_volatility_level(self, volatility: float) -> str:
        """Format volatility as a readable level"""
        try:
            if volatility > 0.7:
                return "Very High"
            elif volatility > 0.5:
                return "High"
            elif volatility > 0.3:
                return "Medium"
            elif volatility > 0.1:
                return "Low"
            else:
                return "Very Low"
        except:
            return "Unknown"
    
    def create_full_dashboard_display(self, sentiment_data: Dict[str, Any],
                                     platform_sentiments: Dict[str, Any],
                                     trends: Optional[Dict[str, Any]] = None,
                                     signals: Optional[Dict[str, Any]] = None,
                                     market_conditions: Optional[Dict[str, Any]] = None,
                                     historical_trend: Optional[Dict[str, Any]] = None) -> str:
        """Create a complete dashboard display"""
        try:
            dashboard_sections = []
            
            # Overall sentiment summary
            dashboard_sections.append(self.format_sentiment_summary(sentiment_data))
            
            # Platform breakdown
            if platform_sentiments:
                dashboard_sections.append(self.format_platform_breakdown(platform_sentiments))
            
            # Trending topics
            if trends:
                dashboard_sections.append(self.format_trending_topics(trends))
            
            # Trading signals
            if signals:
                dashboard_sections.append(self.format_signals(signals))
            
            # Market conditions
            if market_conditions:
                dashboard_sections.append(self.format_market_conditions(market_conditions))
            
            # Historical trend
            if historical_trend:
                dashboard_sections.append(self.format_historical_trend(historical_trend))
            
            # Data quality info
            dashboard_sections.append(self.format_data_quality_info(sentiment_data, platform_sentiments))
            
            return "\n\n".join(dashboard_sections)
            
        except Exception as e:
            logger.error(f"Error creating full dashboard display: {e}")
            return "❌ Dashboard display error"