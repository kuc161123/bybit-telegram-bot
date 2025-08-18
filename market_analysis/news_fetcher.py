#!/usr/bin/env python3
"""
Market News and Economic Calendar Fetcher
Provides breaking crypto news and upcoming economic events
"""
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal
import pytz

logger = logging.getLogger(__name__)

class MarketNewsFetcher:
    """Fetches breaking crypto news and economic calendar events"""
    
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes cache for news
        self.economic_cache_ttl = 3600  # 1 hour cache for economic calendar
        
        # Initialize timezone
        self.utc = pytz.UTC
        self.est = pytz.timezone('US/Eastern')
        
    async def get_breaking_news(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch breaking crypto news that affects the market
        Returns list of news items with title, time, and impact
        """
        try:
            # Check cache first
            cache_key = f"breaking_news_{limit}"
            if cache_key in self.cache:
                cached_data, cached_time = self.cache[cache_key]
                if (datetime.now() - cached_time).seconds < self.cache_ttl:
                    logger.debug(f"Using cached breaking news (age: {(datetime.now() - cached_time).seconds}s)")
                    return cached_data
            
            news_items = []
            
            # Fetch from CryptoCompare News API (free tier available)
            async with aiohttp.ClientSession() as session:
                url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
                
                try:
                    async with session.get(url, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            if data.get("Data"):
                                for item in data["Data"][:limit]:
                                    # Parse news item
                                    published_time = datetime.fromtimestamp(item.get("published_on", 0))
                                    time_ago = self._format_time_ago(published_time)
                                    
                                    # Determine impact level based on keywords
                                    impact = self._determine_news_impact(
                                        item.get("title", ""),
                                        item.get("categories", ""),
                                        item.get("tags", [])
                                    )
                                    
                                    news_items.append({
                                        "title": item.get("title", "Unknown"),
                                        "source": item.get("source", "Unknown"),
                                        "time": published_time,
                                        "time_ago": time_ago,
                                        "impact": impact,
                                        "url": item.get("url", ""),
                                        "categories": item.get("categories", ""),
                                        "body_preview": item.get("body", "")[:100] + "..."
                                    })
                                    
                except asyncio.TimeoutError:
                    logger.error("Timeout fetching breaking news")
                except Exception as e:
                    logger.error(f"Error fetching news from CryptoCompare: {e}")
            
            # If no news from primary source, add fallback news
            if not news_items:
                news_items = self._get_fallback_news()
            
            # Cache the results
            self.cache[cache_key] = (news_items, datetime.now())
            
            return news_items
            
        except Exception as e:
            logger.error(f"Error in get_breaking_news: {e}")
            return self._get_fallback_news()
    
    async def get_economic_calendar(self, hours_ahead: int = 24) -> List[Dict[str, Any]]:
        """
        Fetch upcoming economic events that could impact crypto markets
        Returns list of events with countdown timers
        """
        try:
            # Check cache first
            cache_key = f"economic_calendar_{hours_ahead}"
            if cache_key in self.cache:
                cached_data, cached_time = self.cache[cache_key]
                if (datetime.now() - cached_time).seconds < self.economic_cache_ttl:
                    # Update countdowns for cached data
                    return self._update_countdowns(cached_data)
            
            events = []
            now = datetime.now(self.utc)
            
            # Key economic events that affect crypto
            # In production, this would come from an economic calendar API
            scheduled_events = [
                {
                    "name": "FOMC Meeting Minutes",
                    "impact": "HIGH",
                    "time": self._get_next_occurrence("wednesday", 14, 0),  # 2 PM EST Wednesdays
                    "currency": "USD",
                    "forecast": None,
                    "previous": None
                },
                {
                    "name": "US CPI Data",
                    "impact": "HIGH", 
                    "time": self._get_next_occurrence("monthly", 8, 30),  # Monthly at 8:30 AM EST
                    "currency": "USD",
                    "forecast": "3.2%",
                    "previous": "3.1%"
                },
                {
                    "name": "US Non-Farm Payrolls",
                    "impact": "HIGH",
                    "time": self._get_next_occurrence("first_friday", 8, 30),  # First Friday 8:30 AM EST
                    "currency": "USD",
                    "forecast": "185K",
                    "previous": "175K"
                },
                {
                    "name": "ECB Interest Rate Decision",
                    "impact": "MEDIUM",
                    "time": self._get_next_occurrence("thursday", 8, 45),  # Thursdays 8:45 AM EST
                    "currency": "EUR",
                    "forecast": "4.50%",
                    "previous": "4.50%"
                },
                {
                    "name": "US GDP (Q4)",
                    "impact": "MEDIUM",
                    "time": self._get_next_occurrence("monthly", 8, 30),
                    "currency": "USD",
                    "forecast": "2.8%",
                    "previous": "2.6%"
                }
            ]
            
            # Filter events within the specified time window
            cutoff_time = now + timedelta(hours=hours_ahead)
            
            for event in scheduled_events:
                event_time = event["time"]
                if now <= event_time <= cutoff_time:
                    # Calculate countdown
                    time_until = event_time - now
                    hours_until = int(time_until.total_seconds() / 3600)
                    minutes_until = int((time_until.total_seconds() % 3600) / 60)
                    
                    event_data = {
                        "name": event["name"],
                        "impact": event["impact"],
                        "time": event_time,
                        "time_str": event_time.strftime("%H:%M UTC"),
                        "countdown_hours": hours_until,
                        "countdown_minutes": minutes_until,
                        "countdown_str": self._format_countdown(hours_until, minutes_until),
                        "currency": event["currency"],
                        "forecast": event["forecast"],
                        "previous": event["previous"]
                    }
                    events.append(event_data)
            
            # Sort by time
            events.sort(key=lambda x: x["time"])
            
            # Cache the results
            self.cache[cache_key] = (events, datetime.now())
            
            return events[:5]  # Return top 5 upcoming events
            
        except Exception as e:
            logger.error(f"Error in get_economic_calendar: {e}")
            return []
    
    async def get_market_moving_news(self) -> Dict[str, Any]:
        """
        Get combined breaking news and economic calendar for dashboard
        """
        try:
            # Fetch both in parallel
            news_task = asyncio.create_task(self.get_breaking_news(limit=3))
            calendar_task = asyncio.create_task(self.get_economic_calendar(hours_ahead=24))
            
            breaking_news, economic_events = await asyncio.gather(news_task, calendar_task)
            
            return {
                "breaking_news": breaking_news,
                "economic_calendar": economic_events,
                "last_updated": datetime.now(),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error fetching market moving news: {e}")
            return {
                "breaking_news": self._get_fallback_news()[:3],
                "economic_calendar": [],
                "last_updated": datetime.now(),
                "status": "error"
            }
    
    def _format_time_ago(self, timestamp: datetime) -> str:
        """Format timestamp as 'X minutes/hours ago'"""
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago"
        else:
            return "Just now"
    
    def _format_countdown(self, hours: int, minutes: int) -> str:
        """Format countdown timer"""
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def _determine_news_impact(self, title: str, categories: str, tags: List[str]) -> str:
        """Determine impact level of news based on keywords"""
        title_lower = title.lower()
        categories_lower = categories.lower() if categories else ""
        tags_lower = [tag.lower() for tag in tags] if tags else []
        
        # High impact keywords
        high_impact = [
            "sec", "regulation", "ban", "hack", "exploit", "liquidation",
            "etf", "approval", "reject", "lawsuit", "investigation",
            "whale", "crash", "surge", "plunge", "rally", "dump",
            "bitcoin", "ethereum", "btc", "eth"
        ]
        
        # Medium impact keywords
        medium_impact = [
            "partnership", "integration", "upgrade", "launch", "listing",
            "adoption", "investment", "funding", "acquisition"
        ]
        
        # Check for high impact
        for keyword in high_impact:
            if keyword in title_lower or keyword in categories_lower or any(keyword in tag for tag in tags_lower):
                return "HIGH"
        
        # Check for medium impact
        for keyword in medium_impact:
            if keyword in title_lower or keyword in categories_lower or any(keyword in tag for tag in tags_lower):
                return "MEDIUM"
        
        return "LOW"
    
    def _get_next_occurrence(self, schedule_type: str, hour: int, minute: int) -> datetime:
        """Get next occurrence of a scheduled event"""
        now = datetime.now(self.utc)
        
        if schedule_type == "wednesday":
            # Next Wednesday at specified time
            days_ahead = 2 - now.weekday()  # Wednesday is 2
            if days_ahead <= 0:  # Already passed this week
                days_ahead += 7
            next_date = now + timedelta(days=days_ahead)
            
        elif schedule_type == "thursday":
            # Next Thursday at specified time
            days_ahead = 3 - now.weekday()  # Thursday is 3
            if days_ahead <= 0:
                days_ahead += 7
            next_date = now + timedelta(days=days_ahead)
            
        elif schedule_type == "first_friday":
            # First Friday of the month
            next_date = now.replace(day=1)  # Start of month
            while next_date.weekday() != 4:  # Find first Friday
                next_date += timedelta(days=1)
            if next_date <= now:  # If passed, get next month's first Friday
                next_month = now.replace(day=28) + timedelta(days=4)
                next_date = next_month.replace(day=1)
                while next_date.weekday() != 4:
                    next_date += timedelta(days=1)
                    
        else:  # monthly
            # Next occurrence this month or next
            next_date = now.replace(day=15)  # Mid-month placeholder
            if next_date <= now:
                next_month = now.replace(day=28) + timedelta(days=4)
                next_date = next_month.replace(day=15)
        
        # Set the time
        next_date = next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        return next_date
    
    def _update_countdowns(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Update countdown timers for cached events"""
        now = datetime.now(self.utc)
        updated_events = []
        
        for event in events:
            event_time = event["time"]
            if event_time > now:
                time_until = event_time - now
                hours_until = int(time_until.total_seconds() / 3600)
                minutes_until = int((time_until.total_seconds() % 3600) / 60)
                
                event["countdown_hours"] = hours_until
                event["countdown_minutes"] = minutes_until
                event["countdown_str"] = self._format_countdown(hours_until, minutes_until)
                updated_events.append(event)
        
        return updated_events
    
    def _get_fallback_news(self) -> List[Dict[str, Any]]:
        """Return fallback news when API is unavailable"""
        now = datetime.now()
        return [
            {
                "title": "Crypto Markets Remain Volatile",
                "source": "Market Analysis",
                "time": now - timedelta(minutes=30),
                "time_ago": "30m ago",
                "impact": "MEDIUM",
                "url": "",
                "categories": "Market",
                "body_preview": "Markets continue to show volatility..."
            },
            {
                "title": "Bitcoin Holding Key Support Levels",
                "source": "Technical Analysis",
                "time": now - timedelta(hours=1),
                "time_ago": "1h ago",
                "impact": "LOW",
                "url": "",
                "categories": "Bitcoin",
                "body_preview": "BTC maintaining support above key levels..."
            }
        ]

# Create singleton instance
market_news_fetcher = MarketNewsFetcher()

# Export functions
async def get_market_news():
    """Get market moving news for dashboard"""
    return await market_news_fetcher.get_market_moving_news()

async def get_breaking_news(limit: int = 5):
    """Get breaking crypto news"""
    return await market_news_fetcher.get_breaking_news(limit)

async def get_economic_calendar(hours_ahead: int = 24):
    """Get upcoming economic events"""
    return await market_news_fetcher.get_economic_calendar(hours_ahead)