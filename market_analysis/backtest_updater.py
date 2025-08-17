#!/usr/bin/env python3
"""
Background task to update AI backtest outcomes
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from market_analysis.ai_backtest_tracker import ai_backtest_tracker, TradeOutcome
from clients.bybit_client import bybit_client

logger = logging.getLogger(__name__)

class BacktestUpdater:
    """Updates backtest outcomes based on real market prices"""
    
    def __init__(self, update_interval: int = 300):  # 5 minutes default
        self.update_interval = update_interval
        self.running = False
        self.last_prices: Dict[str, float] = {}
        self.high_since: Dict[str, float] = {}
        self.low_since: Dict[str, float] = {}
    
    async def start(self):
        """Start the backtest updater"""
        if self.running:
            logger.warning("Backtest updater already running")
            return
        
        self.running = True
        logger.info("🔄 Starting AI backtest updater")
        
        while self.running:
            try:
                await self.update_all_recommendations()
                await asyncio.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error in backtest updater: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def stop(self):
        """Stop the backtest updater"""
        self.running = False
        logger.info("Stopping AI backtest updater")
    
    async def update_all_recommendations(self):
        """Update all pending recommendations with current prices"""
        
        # Get all pending recommendations
        pending_recs = [
            rec for rec in ai_backtest_tracker.recommendations.values()
            if rec.outcome == TradeOutcome.PENDING
        ]
        
        if not pending_recs:
            return
        
        # Get unique symbols
        symbols = list(set(rec.symbol for rec in pending_recs))
        
        # Fetch current prices for all symbols
        current_prices = {}
        for symbol in symbols:
            try:
                ticker = await bybit_client.get_ticker(symbol)
                if ticker and 'lastPrice' in ticker:
                    price = float(ticker['lastPrice'])
                    current_prices[symbol] = price
                    
                    # Track highs and lows
                    if symbol not in self.high_since:
                        self.high_since[symbol] = price
                        self.low_since[symbol] = price
                    else:
                        self.high_since[symbol] = max(self.high_since[symbol], price)
                        self.low_since[symbol] = min(self.low_since[symbol], price)
                    
                    # Log significant price movements
                    if symbol in self.last_prices:
                        change_pct = (price - self.last_prices[symbol]) / self.last_prices[symbol] * 100
                        if abs(change_pct) > 1:  # More than 1% change
                            logger.debug(f"{symbol}: ${price:,.2f} ({change_pct:+.2f}%)")
                    
                    self.last_prices[symbol] = price
                    
            except Exception as e:
                logger.error(f"Error fetching price for {symbol}: {e}")
                continue
        
        # Update each pending recommendation
        updated_count = 0
        for rec in pending_recs:
            if rec.symbol in current_prices:
                outcome = await ai_backtest_tracker.update_recommendation_outcome(
                    rec_id=rec.id,
                    current_price=current_prices[rec.symbol],
                    high_since=self.high_since.get(rec.symbol),
                    low_since=self.low_since.get(rec.symbol)
                )
                
                # Reset high/low tracking if trade completed
                if outcome and outcome != TradeOutcome.PENDING:
                    updated_count += 1
                    # Keep tracking for other pending trades on same symbol
                    # Only reset if no other pending trades for this symbol
                    other_pending = any(
                        r.symbol == rec.symbol and r.id != rec.id and r.outcome == TradeOutcome.PENDING
                        for r in ai_backtest_tracker.recommendations.values()
                    )
                    if not other_pending:
                        self.high_since.pop(rec.symbol, None)
                        self.low_since.pop(rec.symbol, None)
        
        if updated_count > 0:
            logger.info(f"✅ Updated {updated_count} backtest outcomes")
            await ai_backtest_tracker.update_statistics()
    
    async def force_update(self, symbol: Optional[str] = None):
        """Force an immediate update for a specific symbol or all symbols"""
        if symbol:
            pending_recs = [
                rec for rec in ai_backtest_tracker.recommendations.values()
                if rec.outcome == TradeOutcome.PENDING and rec.symbol == symbol
            ]
        else:
            pending_recs = [
                rec for rec in ai_backtest_tracker.recommendations.values()
                if rec.outcome == TradeOutcome.PENDING
            ]
        
        if not pending_recs:
            logger.info("No pending recommendations to update")
            return
        
        logger.info(f"Force updating {len(pending_recs)} recommendations")
        await self.update_all_recommendations()

# Global instance
backtest_updater = BacktestUpdater()