#!/usr/bin/env python3
"""
Trend Detection for Social Media Sentiment
Identifies trending topics and emerging patterns
"""
import logging
import re
from typing import Dict, List, Any, Tuple
from collections import Counter, defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TrendDetector:
    def __init__(self):
        """Initialize trend detector"""
        self.crypto_keywords = {
            # Major cryptocurrencies
            'bitcoin', 'btc', 'ethereum', 'eth', 'binancecoin', 'bnb',
            'cardano', 'ada', 'solana', 'sol', 'polkadot', 'dot',
            'chainlink', 'link', 'litecoin', 'ltc', 'avalanche', 'avax',
            'polygon', 'matic', 'uniswap', 'uni', 'dogecoin', 'doge',
            'shiba', 'shib', 'ripple', 'xrp', 'stellar', 'xlm',
            
            # DeFi and trends
            'defi', 'nft', 'dao', 'metaverse', 'web3', 'gamefi',
            'yield', 'farming', 'staking', 'liquidity', 'dex',
            'swap', 'bridge', 'layer2', 'scaling', 'rollup',
            
            # Market terms
            'bullish', 'bearish', 'pump', 'dump', 'moon', 'lambo',
            'hodl', 'buy', 'sell', 'long', 'short', 'leverage',
            'futures', 'options', 'spot', 'margin', 'liquidation',
            
            # Sentiment indicators
            'fomo', 'fud', 'hype', 'bubble', 'crash', 'rally',
            'correction', 'dip', 'ath', 'bottom', 'resistance', 'support'
        }
        
        # Trending patterns
        self.trend_patterns = {
            'price_action': [
                r'\b(?:up|down|pump|dump|rally|crash|moon|tank)\b',
                r'\b(?:bull|bear)(?:ish|run|market)?\b',
                r'\b(?:ath|all[- ]?time[- ]?high)\b',
                r'\b(?:\d+[%$]|x\d+|to the moon)\b'
            ],
            'market_events': [
                r'\b(?:halving|fork|upgrade|listing|delisting)\b',
                r'\b(?:regulation|ban|legal|sec|lawsuit)\b',
                r'\b(?:partnership|adoption|integration)\b',
                r'\b(?:hack|exploit|rug[- ]?pull|scam)\b'
            ],
            'technical_analysis': [
                r'\b(?:resistance|support|breakout|breakdown)\b',
                r'\b(?:rsi|macd|fibonacci|bollinger)\b',
                r'\b(?:trend|channel|triangle|wedge)\b',
                r'\b(?:volume|momentum|divergence)\b'
            ]
        }
    
    def extract_trending_topics(self, platform_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract trending topics from platform data"""
        try:
            trending_topics = {
                'keywords': {},
                'hashtags': {},
                'mentions': {},
                'patterns': {},
                'sentiment_shifts': [],
                'emerging_trends': []
            }
            
            all_text = []
            
            # Collect all text data
            for platform, data in platform_data.items():
                items = data.get('items', [])
                for item in items:
                    if isinstance(item, dict):
                        text = item.get('content', '') or item.get('title', '') or item.get('text', '')
                        if text:
                            all_text.append(text.lower())
            
            if not all_text:
                logger.debug("No text data found for trend analysis")
                return trending_topics
            
            # Extract keywords
            trending_topics['keywords'] = self._extract_keywords(all_text)
            
            # Extract hashtags
            trending_topics['hashtags'] = self._extract_hashtags(all_text)
            
            # Extract mentions
            trending_topics['mentions'] = self._extract_mentions(all_text)
            
            # Detect patterns
            trending_topics['patterns'] = self._detect_patterns(all_text)
            
            # Identify emerging trends
            trending_topics['emerging_trends'] = self._identify_emerging_trends(
                trending_topics['keywords'], 
                trending_topics['patterns']
            )
            
            logger.debug(f"Extracted trends: {len(trending_topics['keywords'])} keywords, "
                        f"{len(trending_topics['hashtags'])} hashtags, "
                        f"{len(trending_topics['emerging_trends'])} emerging trends")
            
            return trending_topics
            
        except Exception as e:
            logger.error(f"Error extracting trending topics: {e}")
            return {
                'keywords': {},
                'hashtags': {},
                'mentions': {},
                'patterns': {},
                'sentiment_shifts': [],
                'emerging_trends': []
            }
    
    def _extract_keywords(self, text_list: List[str]) -> Dict[str, int]:
        """Extract and count crypto-related keywords"""
        try:
            keyword_counts = Counter()
            
            for text in text_list:
                # Clean text and split into words
                words = re.findall(r'\b\w+\b', text.lower())
                
                # Count crypto keywords
                for word in words:
                    if word in self.crypto_keywords:
                        keyword_counts[word] += 1
                    
                    # Also check for variations
                    for keyword in self.crypto_keywords:
                        if keyword in word and len(word) <= len(keyword) + 2:
                            keyword_counts[keyword] += 1
            
            # Return top 20 keywords
            return dict(keyword_counts.most_common(20))
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return {}
    
    def _extract_hashtags(self, text_list: List[str]) -> Dict[str, int]:
        """Extract and count hashtags"""
        try:
            hashtag_counts = Counter()
            
            for text in text_list:
                # Find hashtags
                hashtags = re.findall(r'#(\w+)', text.lower())
                
                # Filter for crypto-related hashtags
                for hashtag in hashtags:
                    if any(keyword in hashtag for keyword in self.crypto_keywords):
                        hashtag_counts[f"#{hashtag}"] += 1
            
            # Return top 15 hashtags
            return dict(hashtag_counts.most_common(15))
            
        except Exception as e:
            logger.error(f"Error extracting hashtags: {e}")
            return {}
    
    def _extract_mentions(self, text_list: List[str]) -> Dict[str, int]:
        """Extract and count @mentions"""
        try:
            mention_counts = Counter()
            
            for text in text_list:
                # Find mentions
                mentions = re.findall(r'@(\w+)', text.lower())
                
                # Count mentions
                for mention in mentions:
                    mention_counts[f"@{mention}"] += 1
            
            # Return top 10 mentions
            return dict(mention_counts.most_common(10))
            
        except Exception as e:
            logger.error(f"Error extracting mentions: {e}")
            return {}
    
    def _detect_patterns(self, text_list: List[str]) -> Dict[str, int]:
        """Detect trading and market patterns in text"""
        try:
            pattern_counts = defaultdict(int)
            
            combined_text = ' '.join(text_list)
            
            for pattern_type, patterns in self.trend_patterns.items():
                for pattern in patterns:
                    matches = re.findall(pattern, combined_text, re.IGNORECASE)
                    if matches:
                        pattern_counts[pattern_type] += len(matches)
            
            return dict(pattern_counts)
            
        except Exception as e:
            logger.error(f"Error detecting patterns: {e}")
            return {}
    
    def _identify_emerging_trends(self, keywords: Dict[str, int], patterns: Dict[str, int]) -> List[Dict[str, Any]]:
        """Identify emerging trends based on keyword and pattern analysis"""
        try:
            emerging_trends = []
            
            # High-frequency keywords could indicate emerging trends
            if keywords:
                top_keywords = list(keywords.items())[:5]
                for keyword, count in top_keywords:
                    if count >= 3:  # Threshold for emerging trend
                        trend_strength = min(count / 10, 1.0)  # Normalize to 0-1
                        emerging_trends.append({
                            'type': 'keyword_surge',
                            'topic': keyword,
                            'strength': trend_strength,
                            'mentions': count,
                            'description': f'High activity around "{keyword}"'
                        })
            
            # Pattern-based trends
            if patterns:
                for pattern_type, count in patterns.items():
                    if count >= 5:  # Threshold for pattern trend
                        trend_strength = min(count / 20, 1.0)  # Normalize to 0-1
                        emerging_trends.append({
                            'type': 'pattern_trend',
                            'topic': pattern_type,
                            'strength': trend_strength,
                            'mentions': count,
                            'description': f'Increased {pattern_type.replace("_", " ")} discussions'
                        })
            
            # Sort by strength
            emerging_trends.sort(key=lambda x: x['strength'], reverse=True)
            
            # Return top 5 trends
            return emerging_trends[:5]
            
        except Exception as e:
            logger.error(f"Error identifying emerging trends: {e}")
            return []
    
    def analyze_trend_sentiment(self, trends: Dict[str, Any], platform_sentiments: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sentiment patterns in trending topics"""
        try:
            trend_sentiment = {
                'overall_trend_sentiment': 'NEUTRAL',
                'trending_topics_sentiment': {},
                'sentiment_momentum': 'STABLE',
                'trend_signals': []
            }
            
            # Analyze overall sentiment momentum
            sentiment_scores = []
            for platform, data in platform_sentiments.items():
                score = data.get('sentiment_score', 50)
                sentiment_scores.append(score)
            
            if sentiment_scores:
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                
                if avg_sentiment > 65:
                    trend_sentiment['overall_trend_sentiment'] = 'BULLISH'
                    trend_sentiment['sentiment_momentum'] = 'BULLISH'
                elif avg_sentiment < 35:
                    trend_sentiment['overall_trend_sentiment'] = 'BEARISH'
                    trend_sentiment['sentiment_momentum'] = 'BEARISH'
                else:
                    trend_sentiment['overall_trend_sentiment'] = 'NEUTRAL'
            
            # Analyze trending topic sentiment
            emerging_trends = trends.get('emerging_trends', [])
            for trend in emerging_trends:
                topic = trend.get('topic', '')
                strength = trend.get('strength', 0)
                
                # Determine if trend is positive or negative based on keywords
                if any(word in topic.lower() for word in ['bull', 'pump', 'moon', 'rally', 'up']):
                    trend_sentiment['trending_topics_sentiment'][topic] = 'POSITIVE'
                elif any(word in topic.lower() for word in ['bear', 'dump', 'crash', 'down', 'fud']):
                    trend_sentiment['trending_topics_sentiment'][topic] = 'NEGATIVE'
                else:
                    trend_sentiment['trending_topics_sentiment'][topic] = 'NEUTRAL'
                
                # Generate signals based on strong trends
                if strength > 0.7:
                    signal_type = 'STRONG_TREND'
                    if trend_sentiment['trending_topics_sentiment'][topic] == 'POSITIVE':
                        signal = f"Strong bullish trend detected in {topic}"
                    elif trend_sentiment['trending_topics_sentiment'][topic] == 'NEGATIVE':
                        signal = f"Strong bearish trend detected in {topic}"
                    else:
                        signal = f"Strong neutral activity in {topic}"
                    
                    trend_sentiment['trend_signals'].append({
                        'type': signal_type,
                        'signal': signal,
                        'strength': strength,
                        'topic': topic
                    })
            
            return trend_sentiment
            
        except Exception as e:
            logger.error(f"Error analyzing trend sentiment: {e}")
            return {
                'overall_trend_sentiment': 'NEUTRAL',
                'trending_topics_sentiment': {},
                'sentiment_momentum': 'STABLE',
                'trend_signals': []
            }
    
    def generate_trend_summary(self, trends: Dict[str, Any], trend_sentiment: Dict[str, Any]) -> str:
        """Generate human-readable trend summary"""
        try:
            summary_parts = []
            
            # Overall sentiment
            overall_sentiment = trend_sentiment.get('overall_trend_sentiment', 'NEUTRAL')
            momentum = trend_sentiment.get('sentiment_momentum', 'STABLE')
            
            summary_parts.append(f"Market sentiment: {overall_sentiment} ({momentum})")
            
            # Top trending topics
            emerging_trends = trends.get('emerging_trends', [])
            if emerging_trends:
                top_trend = emerging_trends[0]
                topic = top_trend.get('topic', 'Unknown')
                strength = top_trend.get('strength', 0)
                
                summary_parts.append(f"Top trend: {topic} (strength: {strength:.0%})")
            
            # Key hashtags
            hashtags = trends.get('hashtags', {})
            if hashtags:
                top_hashtag = list(hashtags.keys())[0]
                summary_parts.append(f"Trending: {top_hashtag}")
            
            # Signals
            signals = trend_sentiment.get('trend_signals', [])
            if signals:
                signal_count = len(signals)
                summary_parts.append(f"{signal_count} trend signal{'s' if signal_count != 1 else ''}")
            
            return " | ".join(summary_parts) if summary_parts else "No significant trends detected"
            
        except Exception as e:
            logger.error(f"Error generating trend summary: {e}")
            return "Trend analysis unavailable"