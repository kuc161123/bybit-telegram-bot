#!/usr/bin/env python3
"""
Discord Data Collector - Light Usage (Practically Unlimited API)
Rate Limit: 50 requests/second = 4,320,000 requests/day
Using only ~500 requests per 6-hour cycle for efficiency
"""
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)

class DiscordCollector:
    def __init__(self):
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")
        self.client = None
        
        # Light usage configuration (API is practically unlimited)
        self.requests_per_cycle = 500  # Conservative usage
        self.requests_made = 0
        self.cycle_start = time.time()
        
        # Target public crypto Discord servers (need proper permissions)
        self.target_servers = {
            # These would need to be real server IDs with proper permissions
            # "123456789": "Crypto General",
            # "987654321": "Bitcoin Discussion", 
            # "456789123": "DeFi Community"
        }
        
        # For demo purposes, we'll simulate data collection
        self.demo_mode = True
        
        self.initialize_discord()
    
    def initialize_discord(self):
        """Initialize Discord API client"""
        try:
            if not self.bot_token:
                logger.warning("Discord bot token not configured - using demo mode")
                self.demo_mode = True
                return True
                
            import discord
            
            # Note: Discord.py requires async setup, handled separately
            logger.info("✅ Discord client configuration ready")
            return True
            
        except ImportError:
            logger.error("discord.py library not installed. Run: pip install discord.py")
            self.demo_mode = True
            return False
        except Exception as e:
            logger.error(f"Discord client setup issue: {e}")
            self.demo_mode = True
            return False
    
    def check_rate_limit(self) -> bool:
        """Check if we're within usage limits"""
        current_time = time.time()
        cycle_elapsed = current_time - self.cycle_start
        
        # Reset counter every 6 hours
        if cycle_elapsed > 21600:  # 6 hours
            self.requests_made = 0
            self.cycle_start = current_time
            
        # Check if we're within budget (very conservative)
        if self.requests_made >= self.requests_per_cycle:
            logger.warning(f"Discord API cycle budget ({self.requests_per_cycle}) reached")
            return False
            
        return True
    
    async def collect_sentiment_data(self) -> Dict[str, Any]:
        """Collect sentiment data from Discord servers"""
        if self.demo_mode:
            return await self._collect_demo_data()
        
        if not self.check_rate_limit():
            return self._empty_result()
        
        collected_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "discord",
            "messages": [],
            "server_data": {},
            "api_calls_used": 0,
            "data_quality": "good"
        }
        
        try:
            # Would collect from actual Discord servers here
            # This requires proper bot setup and server permissions
            
            collected_data["api_calls_used"] = self.requests_made
            collected_data["total_messages"] = len(collected_data["messages"])
            collected_data["servers_processed"] = len(collected_data["server_data"])
            
            logger.info(f"Discord collection complete: {collected_data['total_messages']} messages "
                       f"from {collected_data['servers_processed']} servers")
            
            return collected_data
            
        except Exception as e:
            logger.error(f"Error collecting Discord data: {e}")
            return self._empty_result()
    
    async def _collect_demo_data(self) -> Dict[str, Any]:
        """Generate demo Discord sentiment data"""
        demo_messages = [
            {
                "id": "demo_1",
                "content": "Bitcoin looking bullish today! 🚀",
                "author": "CryptoTrader123",
                "server": "Crypto General",
                "channel": "general-chat",
                "timestamp": datetime.utcnow().isoformat(),
                "sentiment_text": "Bitcoin looking bullish today!"
            },
            {
                "id": "demo_2", 
                "content": "ETH is forming a nice support level here",
                "author": "TechnicalAnalyst",
                "server": "Crypto General",
                "channel": "technical-analysis",
                "timestamp": (datetime.utcnow() - timedelta(minutes=15)).isoformat(),
                "sentiment_text": "ETH is forming a nice support level here"
            },
            {
                "id": "demo_3",
                "content": "Market looking uncertain, might be time to DCA",
                "author": "HODLer2021",
                "server": "Bitcoin Discussion",
                "channel": "price-discussion",
                "timestamp": (datetime.utcnow() - timedelta(minutes=30)).isoformat(),
                "sentiment_text": "Market looking uncertain, might be time to DCA"
            },
            {
                "id": "demo_4",
                "content": "DeFi yields are getting interesting again",
                "author": "DeFiExplorer",
                "server": "DeFi Community",
                "channel": "yield-farming",
                "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                "sentiment_text": "DeFi yields are getting interesting again"
            },
            {
                "id": "demo_5",
                "content": "New altcoin season incoming? Seeing some good moves",
                "author": "AltcoinHunter",
                "server": "Crypto General",
                "channel": "altcoin-discussion",
                "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                "sentiment_text": "New altcoin season incoming? Seeing some good moves"
            }
        ]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "discord",
            "messages": demo_messages,
            "server_data": {
                "Crypto General": {
                    "name": "Crypto General",
                    "member_count": 15420,
                    "online_members": 3240,
                    "messages_collected": 3
                },
                "Bitcoin Discussion": {
                    "name": "Bitcoin Discussion", 
                    "member_count": 8930,
                    "online_members": 1820,
                    "messages_collected": 1
                },
                "DeFi Community": {
                    "name": "DeFi Community",
                    "member_count": 6780,
                    "online_members": 1450,
                    "messages_collected": 1
                }
            },
            "api_calls_used": 15,  # Simulated usage
            "total_messages": len(demo_messages),
            "servers_processed": 3,
            "data_quality": "demo",
            "note": "Demo data - configure DISCORD_BOT_TOKEN for real collection"
        }
    
    async def _collect_server_data(self, server_id: str, server_name: str) -> Dict[str, Any]:
        """Collect data from a specific Discord server"""
        server_data = {
            "name": server_name,
            "id": server_id,
            "messages": [],
            "member_count": 0,
            "online_members": 0
        }
        
        try:
            # Would implement actual Discord data collection here
            # This requires:
            # 1. Bot to be added to servers
            # 2. Proper permissions to read messages
            # 3. Respect for server rules and Discord ToS
            
            return server_data
            
        except Exception as e:
            logger.error(f"Error collecting from Discord server {server_name}: {e}")
            return server_data
    
    def _is_crypto_relevant_message(self, content: str) -> bool:
        """Check if Discord message is crypto-relevant"""
        if len(content) < 10:  # Skip very short messages
            return False
            
        crypto_keywords = [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'blockchain', 'defi', 'nft', 'altcoin', 'satoshi', 'hodl',
            'trading', 'pump', 'dump', 'moon', 'bear', 'bull', 'market',
            'price', 'chart', 'analysis', 'dca', 'yield', 'farming'
        ]
        
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in crypto_keywords)
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "platform": "discord",
            "messages": [],
            "server_data": {},
            "api_calls_used": 0,
            "total_messages": 0,
            "servers_processed": 0,
            "data_quality": "unavailable",
            "error": "API unavailable or rate limited"
        }
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current API usage statistics"""
        cycle_elapsed = time.time() - self.cycle_start
        cycle_remaining = max(0, 21600 - cycle_elapsed)  # 6 hours
        requests_remaining = max(0, self.requests_per_cycle - self.requests_made)
        
        return {
            "requests_made": self.requests_made,
            "cycle_budget": self.requests_per_cycle,
            "requests_remaining": requests_remaining,
            "cycle_time_remaining": cycle_remaining,
            "usage_percentage": (self.requests_made / self.requests_per_cycle) * 100,
            "within_limits": self.requests_made < self.requests_per_cycle,
            "demo_mode": self.demo_mode,
            "note": "Discord API has very high limits (50 req/sec)"
        }