#!/usr/bin/env python3
"""
Lazy loading components for dashboard sections
Improves initial dashboard load time by deferring heavy computations
"""
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class LazyLoader:
    """Manages lazy loading of dashboard components"""
    
    def __init__(self):
        self._loading_tasks: Dict[str, asyncio.Task] = {}
        self._loaded_data: Dict[str, Any] = {}
        self._loading_placeholders = {
            'market_status': "📊 Market Analysis: Loading...",
            'ai_insights': "🧠 AI Insights: Loading...",
            'performance_details': "📈 Performance: Loading...",
            'social_sentiment': "💬 Social Sentiment: Loading..."
        }
    
    def get_placeholder(self, component: str) -> str:
        """Get loading placeholder for component"""
        return self._loading_placeholders.get(component, "⏳ Loading...")
    
    def is_loaded(self, component: str) -> bool:
        """Check if component data is loaded"""
        return component in self._loaded_data
    
    def get_data(self, component: str) -> Optional[Any]:
        """Get loaded data if available"""
        return self._loaded_data.get(component)
    
    async def load_component(self, component: str, loader_func: Callable) -> Any:
        """Load component data asynchronously"""
        # Check if already loaded
        if component in self._loaded_data:
            return self._loaded_data[component]
        
        # Check if loading in progress
        if component in self._loading_tasks:
            task = self._loading_tasks[component]
            if not task.done():
                # Wait for existing task
                return await task
        
        # Start new loading task
        task = asyncio.create_task(self._load_with_error_handling(component, loader_func))
        self._loading_tasks[component] = task
        
        return await task
    
    async def _load_with_error_handling(self, component: str, loader_func: Callable) -> Any:
        """Load component with error handling"""
        try:
            logger.debug(f"Loading lazy component: {component}")
            data = await loader_func()
            self._loaded_data[component] = data
            return data
        except Exception as e:
            logger.error(f"Error loading {component}: {e}")
            # Return error placeholder
            return f"❌ {component}: Error loading data"
        finally:
            # Clean up task reference
            self._loading_tasks.pop(component, None)
    
    def clear(self, component: Optional[str] = None):
        """Clear loaded data"""
        if component:
            self._loaded_data.pop(component, None)
            # Cancel any loading task
            if component in self._loading_tasks:
                task = self._loading_tasks[component]
                if not task.done():
                    task.cancel()
                self._loading_tasks.pop(component)
        else:
            # Clear all
            self._loaded_data.clear()
            # Cancel all loading tasks
            for task in self._loading_tasks.values():
                if not task.done():
                    task.cancel()
            self._loading_tasks.clear()


# Global lazy loader instance
lazy_loader = LazyLoader()


def lazy_component(component_name: str):
    """Decorator for lazy-loaded dashboard components"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Return placeholder immediately
            placeholder = lazy_loader.get_placeholder(component_name)
            
            # Check if already loaded
            if lazy_loader.is_loaded(component_name):
                return lazy_loader.get_data(component_name)
            
            # Start loading in background
            asyncio.create_task(
                lazy_loader.load_component(component_name, lambda: func(*args, **kwargs))
            )
            
            # Return placeholder for now
            return placeholder
            
        # Add method to force load and wait
        async def force_load(*args, **kwargs):
            return await lazy_loader.load_component(
                component_name, 
                lambda: func(*args, **kwargs)
            )
        
        wrapper.force_load = force_load
        return wrapper
    return decorator


# Lazy loading implementations for heavy components
@lazy_component('market_status')
async def load_market_status() -> str:
    """Load market status analysis"""
    try:
        from market_analysis.market_status_engine import market_status_engine
        analysis = await market_status_engine.get_market_analysis()
        
        if not analysis:
            return "📊 Market Analysis: No data available"
        
        lines = ["📊 Market Status:"]
        lines.append(f"├ Trend: {analysis.get('trend', 'Unknown')}")
        lines.append(f"├ Volatility: {analysis.get('volatility', 'Unknown')}")
        lines.append(f"└ Sentiment: {analysis.get('sentiment', 'Neutral')}")
        
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error loading market status: {e}")
        return "📊 Market Analysis: Unavailable"


@lazy_component('ai_insights')
async def load_ai_insights(positions: list) -> str:
    """Load AI insights for positions"""
    try:
        # Only load if we have positions and AI is enabled
        if not positions:
            return ""
        
        from clients.ai_client import get_ai_market_insight
        
        # Get insights for top 3 positions by size
        top_positions = sorted(positions, key=lambda x: float(x.get('positionValue', 0)), reverse=True)[:3]
        
        insights = []
        for pos in top_positions:
            symbol = pos.get('symbol', '')
            insight = await get_ai_market_insight(symbol)
            if insight:
                insights.append(f"{symbol}: {insight}")
        
        if insights:
            return "🧠 AI Insights:\n" + "\n".join(f"├ {i}" for i in insights[:-1]) + f"\n└ {insights[-1]}"
        
        return ""
        
    except Exception as e:
        logger.error(f"Error loading AI insights: {e}")
        return ""


@lazy_component('performance_details')
async def load_performance_details(chat_id: int, context: Any) -> str:
    """Load detailed performance metrics"""
    try:
        bot_data = context.bot_data
        
        # Calculate win rate
        total_wins = bot_data.get('stats_total_wins', 0)
        total_losses = bot_data.get('stats_total_losses', 0)
        total_trades = total_wins + total_losses
        
        if total_trades > 0:
            win_rate = (total_wins / total_trades) * 100
            avg_win = bot_data.get('stats_total_wins_pnl', 0) / max(total_wins, 1)
            avg_loss = abs(bot_data.get('stats_total_losses_pnl', 0)) / max(total_losses, 1)
            
            lines = ["📈 Performance Details:"]
            lines.append(f"├ Win Rate: {win_rate:.1f}%")
            lines.append(f"├ Avg Win: ${avg_win:.2f}")
            lines.append(f"├ Avg Loss: ${avg_loss:.2f}")
            lines.append(f"└ Total Trades: {total_trades}")
            
            return "\n".join(lines)
        
        return ""
        
    except Exception as e:
        logger.error(f"Error loading performance details: {e}")
        return ""