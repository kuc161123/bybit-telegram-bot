#!/usr/bin/env python3
"""
Multi-Platform Data Aggregator
Combines sentiment data from all platforms into unified intelligence
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)

class DataAggregator:
    def __init__(self):
        # Platform importance weights for aggregation
        self.platform_weights = {
            "reddit": 1.0,      # High quality discussions
            "twitter": 0.9,     # Influencer focused
            "youtube": 1.0,     # In-depth analysis
            "discord": 0.7,     # More casual
            "news_market": 1.2  # Official data gets highest weight
        }
        
        # Minimum data quality thresholds
        self.quality_thresholds = {
            "minimum_confidence": 30,
            "minimum_items_per_platform": 3,
            "maximum_age_hours": 6
        }
    
    async def aggregate_platform_data(self, platform_sentiments: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate sentiment data from all platforms"""
        aggregated_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_sentiment": "NEUTRAL",
            "sentiment_score": 50,
            "confidence": 0,
            "platform_breakdown": {},
            "trending_topics": [],
            "market_signals": [],
            "data_quality": "good",
            "platforms_analyzed": 0,
            "total_data_points": 0
        }
        
        try:
            # Filter and validate platform data
            valid_platforms = self._filter_valid_platforms(platform_sentiments)
            
            if not valid_platforms:
                aggregated_result["data_quality"] = "insufficient"
                aggregated_result["error"] = "No valid platform data available"
                return aggregated_result
            
            # Calculate weighted sentiment scores
            weighted_scores = []
            weighted_confidences = []
            total_items = 0
            
            for platform, sentiment_data in valid_platforms.items():
                weight = self.platform_weights.get(platform, 1.0)
                score = sentiment_data.get("sentiment_score", 50)
                confidence = sentiment_data.get("confidence", 0)
                items = sentiment_data.get("total_items", 0)
                
                # Apply weight to score and confidence
                weighted_score = score * weight
                weighted_confidence = confidence * weight
                
                weighted_scores.append(weighted_score)
                weighted_confidences.append(weighted_confidence)
                total_items += items
                
                # Store platform breakdown
                aggregated_result["platform_breakdown"][platform] = {
                    "sentiment": sentiment_data.get("overall_sentiment", "NEUTRAL"),
                    "score": score,
                    "confidence": confidence,
                    "weight": weight,
                    "items_analyzed": items,
                    "top_keywords": sentiment_data.get("top_keywords", [])
                }
            
            # Calculate overall metrics
            if weighted_scores:
                # Calculate weighted average
                total_weight = sum(self.platform_weights.get(p, 1.0) for p in valid_platforms.keys())
                overall_score = sum(weighted_scores) / total_weight
                overall_confidence = sum(weighted_confidences) / total_weight
                
                aggregated_result["sentiment_score"] = int(max(0, min(100, overall_score)))
                aggregated_result["confidence"] = int(max(0, min(100, overall_confidence)))
                
                # Determine overall sentiment
                if overall_score >= 65:
                    aggregated_result["overall_sentiment"] = "BULLISH"
                elif overall_score <= 35:
                    aggregated_result["overall_sentiment"] = "BEARISH"
                else:
                    aggregated_result["overall_sentiment"] = "NEUTRAL"
            
            # Generate additional insights
            aggregated_result["trending_topics"] = self._extract_trending_topics(valid_platforms)
            aggregated_result["market_signals"] = self._generate_market_signals(valid_platforms, aggregated_result)
            aggregated_result["platforms_analyzed"] = len(valid_platforms)
            aggregated_result["total_data_points"] = total_items
            
            # Assess data quality
            aggregated_result["data_quality"] = self._assess_data_quality(
                valid_platforms, aggregated_result["confidence"], total_items
            )
            
            logger.info(f"Data aggregation complete: {aggregated_result['overall_sentiment']} "
                       f"(Score: {aggregated_result['sentiment_score']}, "
                       f"Confidence: {aggregated_result['confidence']}%) "
                       f"from {len(valid_platforms)} platforms")
            
            return aggregated_result
            
        except Exception as e:
            logger.error(f"Error aggregating platform data: {e}")
            aggregated_result["error"] = str(e)
            aggregated_result["data_quality"] = "error"
            return aggregated_result
    
    def _filter_valid_platforms(self, platform_sentiments: Dict[str, Any]) -> Dict[str, Any]:
        """Filter platforms with sufficient data quality"""
        valid_platforms = {}
        
        for platform, data in platform_sentiments.items():
            if not isinstance(data, dict):
                continue
            
            # Check minimum requirements
            confidence = data.get("confidence", 0)
            total_items = data.get("total_items", 0)
            timestamp_str = data.get("timestamp")
            
            # Check confidence threshold
            if confidence < self.quality_thresholds["minimum_confidence"]:
                logger.debug(f"Platform {platform} filtered: low confidence ({confidence}%)")
                continue
            
            # Check minimum items
            if total_items < self.quality_thresholds["minimum_items_per_platform"]:
                logger.debug(f"Platform {platform} filtered: insufficient items ({total_items})")
                continue
            
            # Check data freshness
            if timestamp_str:
                try:
                    data_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    age_hours = (datetime.utcnow() - data_time.replace(tzinfo=None)).total_seconds() / 3600
                    
                    if age_hours > self.quality_thresholds["maximum_age_hours"]:
                        logger.debug(f"Platform {platform} filtered: data too old ({age_hours:.1f}h)")
                        continue
                except:
                    pass  # If timestamp parsing fails, allow the data
            
            valid_platforms[platform] = data
            logger.debug(f"Platform {platform} validated: {total_items} items, {confidence}% confidence")
        
        return valid_platforms
    
    def _extract_trending_topics(self, valid_platforms: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract trending topics across all platforms"""
        try:
            # Collect all keywords from all platforms
            keyword_counts = {}
            keyword_platforms = {}
            
            for platform, data in valid_platforms.items():
                keywords = data.get("top_keywords", [])
                for keyword in keywords:
                    keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
                    
                    if keyword not in keyword_platforms:
                        keyword_platforms[keyword] = []
                    keyword_platforms[keyword].append(platform)
            
            # Create trending topics list
            trending_topics = []
            for keyword, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                trending_topics.append({
                    "keyword": keyword,
                    "mentions": count,
                    "platforms": keyword_platforms[keyword],
                    "cross_platform": len(keyword_platforms[keyword]) > 1
                })
            
            return trending_topics
            
        except Exception as e:
            logger.error(f"Error extracting trending topics: {e}")
            return []
    
    def _generate_market_signals(self, valid_platforms: Dict[str, Any], 
                                aggregated_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate market signals based on aggregated data"""
        signals = []
        
        try:
            overall_score = aggregated_result["sentiment_score"]
            confidence = aggregated_result["confidence"]
            
            # Strong sentiment signals
            if overall_score >= 80 and confidence >= 70:
                signals.append({
                    "type": "STRONG_BULLISH",
                    "message": "Very positive sentiment across platforms",
                    "confidence": confidence,
                    "action": "Consider long positions"
                })
            elif overall_score <= 20 and confidence >= 70:
                signals.append({
                    "type": "STRONG_BEARISH", 
                    "message": "Very negative sentiment across platforms",
                    "confidence": confidence,
                    "action": "Consider short positions or risk management"
                })
            
            # Platform consensus signals
            platform_sentiments = [data.get("sentiment_score", 50) for data in valid_platforms.values()]
            if len(platform_sentiments) >= 3:
                sentiment_std = statistics.stdev(platform_sentiments)
                
                if sentiment_std < 10:  # Low deviation = high consensus
                    avg_sentiment = statistics.mean(platform_sentiments)
                    if avg_sentiment >= 60:
                        signals.append({
                            "type": "CONSENSUS_BULLISH",
                            "message": "Strong consensus across all platforms",
                            "confidence": 90,
                            "action": "High confidence bullish signal"
                        })
                    elif avg_sentiment <= 40:
                        signals.append({
                            "type": "CONSENSUS_BEARISH",
                            "message": "Strong bearish consensus across platforms",
                            "confidence": 90,
                            "action": "High confidence bearish signal"
                        })
            
            # FOMO/FUD detection
            if overall_score >= 90:
                signals.append({
                    "type": "FOMO_WARNING",
                    "message": "Extreme positive sentiment detected",
                    "confidence": confidence,
                    "action": "Potential market top - exercise caution"
                })
            elif overall_score <= 10:
                signals.append({
                    "type": "EXTREME_FUD",
                    "message": "Extreme negative sentiment detected", 
                    "confidence": confidence,
                    "action": "Potential market bottom - opportunity?"
                })
            
            # News/Market specific signals
            if "news_market" in valid_platforms:
                news_data = valid_platforms["news_market"]
                if "fear_greed_index" in news_data:
                    # This would be extracted from the news collector's processed data
                    pass
            
            return signals
            
        except Exception as e:
            logger.error(f"Error generating market signals: {e}")
            return []
    
    def _assess_data_quality(self, valid_platforms: Dict[str, Any], 
                           overall_confidence: float, total_items: int) -> str:
        """Assess overall data quality"""
        try:
            # Count high-quality platforms
            high_quality_platforms = sum(
                1 for data in valid_platforms.values() 
                if data.get("confidence", 0) >= 60
            )
            
            # Assess data coverage
            platform_coverage = len(valid_platforms)
            
            # Assess data volume
            item_density = total_items / max(1, platform_coverage)
            
            # Determine quality level
            if (overall_confidence >= 80 and 
                high_quality_platforms >= 3 and 
                platform_coverage >= 4 and 
                item_density >= 50):
                return "excellent"
            elif (overall_confidence >= 60 and 
                  high_quality_platforms >= 2 and 
                  platform_coverage >= 3 and 
                  item_density >= 20):
                return "good"
            elif (overall_confidence >= 40 and 
                  platform_coverage >= 2 and 
                  item_density >= 10):
                return "fair"
            else:
                return "limited"
                
        except Exception as e:
            logger.error(f"Error assessing data quality: {e}")
            return "unknown"
    
    def generate_summary_report(self, aggregated_data: Dict[str, Any]) -> str:
        """Generate human-readable summary report"""
        try:
            sentiment = aggregated_data.get("overall_sentiment", "NEUTRAL")
            score = aggregated_data.get("sentiment_score", 50)
            confidence = aggregated_data.get("confidence", 0)
            platforms = aggregated_data.get("platforms_analyzed", 0)
            data_points = aggregated_data.get("total_data_points", 0)
            quality = aggregated_data.get("data_quality", "unknown")
            
            # Sentiment emoji
            sentiment_emoji = {
                "BULLISH": "🐂",
                "BEARISH": "🐻", 
                "NEUTRAL": "🦉"
            }.get(sentiment, "🤖")
            
            # Quality indicator
            quality_emoji = {
                "excellent": "⭐⭐⭐⭐⭐",
                "good": "⭐⭐⭐⭐",
                "fair": "⭐⭐⭐",
                "limited": "⭐⭐",
                "insufficient": "⭐"
            }.get(quality, "❓")
            
            summary = f"""📊 <b>AGGREGATED MARKET SENTIMENT</b>
            
🎯 <b>Overall Assessment:</b> {sentiment} {sentiment_emoji}
📈 <b>Sentiment Score:</b> {score}/100
🎯 <b>Confidence Level:</b> {confidence}%
📊 <b>Data Quality:</b> {quality_emoji} ({quality.title()})

📱 <b>Analysis Coverage:</b>
• Platforms: {platforms}
• Data Points: {data_points:,}
"""
            
            # Add platform breakdown
            if aggregated_data.get("platform_breakdown"):
                summary += "\n⚡ <b>Platform Breakdown:</b>\n"
                for platform, data in aggregated_data["platform_breakdown"].items():
                    platform_emoji = {
                        "reddit": "🔵",
                        "twitter": "🐦", 
                        "youtube": "📺",
                        "discord": "💬",
                        "news_market": "📰"
                    }.get(platform, "📱")
                    
                    summary += f"  {platform_emoji} {platform.title()}: {data['sentiment']} ({data['score']}/100)\n"
            
            # Add trending topics
            trending = aggregated_data.get("trending_topics", [])
            if trending:
                summary += "\n🔥 <b>Trending Topics:</b>\n"
                for topic in trending[:5]:
                    cross_platform = "🌐" if topic.get("cross_platform") else ""
                    summary += f"  • {topic['keyword']} {cross_platform}\n"
            
            # Add market signals
            signals = aggregated_data.get("market_signals", [])
            if signals:
                summary += "\n🚨 <b>Market Signals:</b>\n"
                for signal in signals[:3]:
                    signal_emoji = {
                        "STRONG_BULLISH": "🚀",
                        "STRONG_BEARISH": "📉",
                        "CONSENSUS_BULLISH": "✅",
                        "CONSENSUS_BEARISH": "❌",
                        "FOMO_WARNING": "⚠️",
                        "EXTREME_FUD": "🔴"
                    }.get(signal.get("type"), "📊")
                    
                    summary += f"  {signal_emoji} {signal.get('message', '')}\n"
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary report: {e}")
            return f"📊 <b>MARKET SENTIMENT ANALYSIS</b>\n\nError generating report: {str(e)}"