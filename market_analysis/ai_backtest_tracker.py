#!/usr/bin/env python3
"""
AI Trade Backtest Tracker
Tracks and validates AI trade recommendations with real market outcomes
"""

import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

class TradeOutcome(Enum):
    """Trade outcome types"""
    WIN_TP_HIT = "win_tp_hit"           # Target price reached
    WIN_PARTIAL = "win_partial"          # Partial profit taken
    LOSS_SL_HIT = "loss_sl_hit"         # Stop loss hit
    LOSS_INVALIDATED = "loss_invalidated" # Invalidation level breached
    PENDING = "pending"                  # Still in progress
    EXPIRED = "expired"                  # Time horizon exceeded
    CANCELLED = "cancelled"              # Trade not taken

@dataclass
class AITradeRecommendation:
    """Record of an AI trade recommendation"""
    id: str
    timestamp: datetime
    symbol: str
    recommendation: str  # BUY/SELL/HOLD
    confidence: float
    risk_assessment: str
    
    # Entry and exit levels
    entry_zone: Tuple[float, float]
    targets: List[float]
    stop_loss: Optional[float]
    invalidation: Optional[float]
    
    # Live market data at recommendation time
    price_at_recommendation: float
    
    # Trade setup details
    risk_reward: float
    position_size: str
    time_horizon: str
    key_signals: List[str]
    pattern_confluence: float
    
    # Tracking fields
    outcome: TradeOutcome = TradeOutcome.PENDING
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    actual_pnl_pct: Optional[float] = None
    time_to_outcome: Optional[timedelta] = None
    max_favorable_excursion: Optional[float] = None  # Best unrealized profit
    max_adverse_excursion: Optional[float] = None    # Worst unrealized loss
    outcome_timestamp: Optional[datetime] = None
    notes: Optional[str] = None
    
    # Enhanced tracking
    target_hit_index: Optional[int] = None  # Which target was hit (0, 1, 2)
    entry_timing_accuracy: Optional[str] = None  # "perfect", "good", "late", "missed"
    actual_vs_expected_rr: Optional[float] = None  # Actual R:R vs expected

@dataclass
class BacktestStatistics:
    """Aggregated backtest statistics"""
    total_recommendations: int = 0
    total_executed: int = 0
    
    # Win/Loss stats
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    
    # Performance by confidence level
    high_confidence_win_rate: float = 0.0  # >70% confidence
    medium_confidence_win_rate: float = 0.0  # 50-70% confidence
    low_confidence_win_rate: float = 0.0    # <50% confidence
    
    # Risk assessment accuracy
    low_risk_success_rate: float = 0.0
    medium_risk_success_rate: float = 0.0
    high_risk_success_rate: float = 0.0
    
    # Average performance metrics
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    
    # Time metrics
    avg_time_to_tp: Optional[timedelta] = None
    avg_time_to_sl: Optional[timedelta] = None
    
    # Pattern performance
    best_performing_patterns: List[Tuple[str, float]] = None  # Pattern name, win rate
    worst_performing_patterns: List[Tuple[str, float]] = None
    
    # Market condition performance
    trending_market_win_rate: float = 0.0
    ranging_market_win_rate: float = 0.0
    volatile_market_win_rate: float = 0.0
    
    # Recent performance (last 30 days)
    recent_win_rate: float = 0.0
    recent_recommendations: int = 0
    
    # Target hit distribution
    target_1_hits: int = 0  # First target hits
    target_2_hits: int = 0  # Second target hits
    target_3_hits: int = 0  # Third target hits
    most_common_target: Optional[int] = None  # Most frequently hit target index
    target_hit_rate: Dict[int, float] = None  # Hit rate by target level
    
    # Entry timing accuracy
    perfect_entries: int = 0  # Entered at optimal price
    good_entries: int = 0     # Entered within 0.5% of optimal
    late_entries: int = 0     # Entered >0.5% from optimal
    missed_entries: int = 0   # Never entered (price ran away)
    
    # Actual vs Expected R:R
    avg_actual_rr: float = 0.0
    avg_expected_rr: float = 0.0
    rr_accuracy: float = 0.0  # How close actual R:R is to expected
    
    last_updated: Optional[datetime] = None

class AIBacktestTracker:
    """Tracks and validates AI trade recommendations"""
    
    def __init__(self, storage_path: str = "ai_backtest_data.pkl"):
        self.storage_path = storage_path
        self.recommendations: Dict[str, AITradeRecommendation] = {}
        self.statistics = BacktestStatistics()
        self.load_data()
        
    def load_data(self):
        """Load existing backtest data from storage"""
        try:
            if Path(self.storage_path).exists():
                with open(self.storage_path, 'rb') as f:
                    data = pickle.load(f)
                    self.recommendations = data.get('recommendations', {})
                    self.statistics = data.get('statistics', BacktestStatistics())
                    logger.info(f"Loaded {len(self.recommendations)} backtest records")
        except Exception as e:
            logger.error(f"Error loading backtest data: {e}")
            self.recommendations = {}
            self.statistics = BacktestStatistics()
    
    def save_data(self):
        """Save backtest data to storage"""
        try:
            data = {
                'recommendations': self.recommendations,
                'statistics': self.statistics,
                'last_saved': datetime.now()
            }
            with open(self.storage_path, 'wb') as f:
                pickle.dump(data, f)
            logger.debug(f"Saved {len(self.recommendations)} backtest records")
        except Exception as e:
            logger.error(f"Error saving backtest data: {e}")
    
    async def record_recommendation(
        self,
        symbol: str,
        recommendation: str,
        confidence: float,
        risk_assessment: str,
        entry_zone: Tuple[float, float],
        targets: List[float],
        stop_loss: float,
        current_price: float,
        **kwargs
    ) -> str:
        """Record a new AI trade recommendation"""
        
        # Generate unique ID
        rec_id = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create recommendation record
        rec = AITradeRecommendation(
            id=rec_id,
            timestamp=datetime.now(),
            symbol=symbol,
            recommendation=recommendation,
            confidence=confidence,
            risk_assessment=risk_assessment,
            entry_zone=entry_zone,
            targets=targets,
            stop_loss=stop_loss,
            invalidation=kwargs.get('invalidation'),
            price_at_recommendation=current_price,
            risk_reward=kwargs.get('risk_reward', 0),
            position_size=kwargs.get('position_size', ''),
            time_horizon=kwargs.get('time_horizon', ''),
            key_signals=kwargs.get('key_signals', []),
            pattern_confluence=kwargs.get('pattern_confluence', 0)
        )
        
        # Store recommendation
        self.recommendations[rec_id] = rec
        self.save_data()
        
        logger.info(f"📝 Recorded AI recommendation: {symbol} {recommendation} @ ${current_price:,.2f} (ID: {rec_id})")
        
        return rec_id
    
    async def update_recommendation_outcome(
        self,
        rec_id: str,
        current_price: float,
        high_since: float = None,
        low_since: float = None
    ) -> Optional[TradeOutcome]:
        """Update the outcome of a recommendation based on current price"""
        
        if rec_id not in self.recommendations:
            return None
            
        rec = self.recommendations[rec_id]
        
        # Skip if already completed
        if rec.outcome not in [TradeOutcome.PENDING]:
            return rec.outcome
        
        # Check if price entered the entry zone
        if not rec.entry_price:
            if rec.entry_zone[0] <= current_price <= rec.entry_zone[1]:
                rec.entry_price = current_price
                
                # Assess entry timing accuracy
                optimal_entry = (rec.entry_zone[0] + rec.entry_zone[1]) / 2
                entry_deviation = abs(current_price - optimal_entry) / optimal_entry * 100
                
                if entry_deviation < 0.1:
                    rec.entry_timing_accuracy = "perfect"
                elif entry_deviation < 0.5:
                    rec.entry_timing_accuracy = "good"
                else:
                    rec.entry_timing_accuracy = "late"
                
                logger.info(f"✅ Trade entered: {rec.symbol} @ ${current_price:,.2f} ({rec.entry_timing_accuracy} timing)")
        
        # If trade was entered, check for outcomes
        if rec.entry_price:
            # Update excursions
            if rec.recommendation == "BUY":
                profit_pct = (current_price - rec.entry_price) / rec.entry_price * 100
                if high_since:
                    max_profit = (high_since - rec.entry_price) / rec.entry_price * 100
                    rec.max_favorable_excursion = max(rec.max_favorable_excursion or 0, max_profit)
                if low_since:
                    max_loss = (low_since - rec.entry_price) / rec.entry_price * 100
                    rec.max_adverse_excursion = min(rec.max_adverse_excursion or 0, max_loss)
            else:  # SELL
                profit_pct = (rec.entry_price - current_price) / rec.entry_price * 100
                if low_since:
                    max_profit = (rec.entry_price - low_since) / rec.entry_price * 100
                    rec.max_favorable_excursion = max(rec.max_favorable_excursion or 0, max_profit)
                if high_since:
                    max_loss = (rec.entry_price - high_since) / rec.entry_price * 100
                    rec.max_adverse_excursion = min(rec.max_adverse_excursion or 0, max_loss)
            
            # Check for target hit
            if rec.targets:
                if rec.recommendation == "BUY":
                    for idx, target in enumerate(rec.targets):
                        if current_price >= target:
                            rec.outcome = TradeOutcome.WIN_TP_HIT
                            rec.exit_price = current_price
                            rec.actual_pnl_pct = profit_pct
                            rec.outcome_timestamp = datetime.now()
                            rec.time_to_outcome = rec.outcome_timestamp - rec.timestamp
                            rec.target_hit_index = idx
                            
                            # Calculate actual vs expected R:R
                            actual_risk = abs(rec.entry_price - rec.stop_loss) if rec.stop_loss else 0
                            actual_reward = abs(current_price - rec.entry_price)
                            if actual_risk > 0:
                                rec.actual_vs_expected_rr = actual_reward / actual_risk
                            
                            logger.info(f"🎯 Target {idx+1} hit: {rec.symbol} +{profit_pct:.2f}%")
                            break
                else:  # SELL
                    for idx, target in enumerate(rec.targets):
                        if current_price <= target:
                            rec.outcome = TradeOutcome.WIN_TP_HIT
                            rec.exit_price = current_price
                            rec.actual_pnl_pct = profit_pct
                            rec.outcome_timestamp = datetime.now()
                            rec.time_to_outcome = rec.outcome_timestamp - rec.timestamp
                            rec.target_hit_index = idx
                            
                            # Calculate actual vs expected R:R
                            actual_risk = abs(rec.entry_price - rec.stop_loss) if rec.stop_loss else 0
                            actual_reward = abs(rec.entry_price - current_price)
                            if actual_risk > 0:
                                rec.actual_vs_expected_rr = actual_reward / actual_risk
                            
                            logger.info(f"🎯 Target {idx+1} hit: {rec.symbol} +{profit_pct:.2f}%")
                            break
            
            # Check for stop loss hit
            if rec.stop_loss and rec.outcome == TradeOutcome.PENDING:
                if rec.recommendation == "BUY" and current_price <= rec.stop_loss:
                    rec.outcome = TradeOutcome.LOSS_SL_HIT
                    rec.exit_price = current_price
                    rec.actual_pnl_pct = profit_pct
                    rec.outcome_timestamp = datetime.now()
                    rec.time_to_outcome = rec.outcome_timestamp - rec.timestamp
                    logger.info(f"🛑 Stop loss hit: {rec.symbol} {profit_pct:.2f}%")
                elif rec.recommendation == "SELL" and current_price >= rec.stop_loss:
                    rec.outcome = TradeOutcome.LOSS_SL_HIT
                    rec.exit_price = current_price
                    rec.actual_pnl_pct = profit_pct
                    rec.outcome_timestamp = datetime.now()
                    rec.time_to_outcome = rec.outcome_timestamp - rec.timestamp
                    logger.info(f"🛑 Stop loss hit: {rec.symbol} {profit_pct:.2f}%")
            
            # Check for invalidation
            if rec.invalidation and rec.outcome == TradeOutcome.PENDING:
                if rec.recommendation == "BUY" and current_price < rec.invalidation:
                    rec.outcome = TradeOutcome.LOSS_INVALIDATED
                    rec.exit_price = current_price
                    rec.actual_pnl_pct = profit_pct
                    rec.outcome_timestamp = datetime.now()
                    logger.info(f"❌ Trade invalidated: {rec.symbol}")
                elif rec.recommendation == "SELL" and current_price > rec.invalidation:
                    rec.outcome = TradeOutcome.LOSS_INVALIDATED
                    rec.exit_price = current_price
                    rec.actual_pnl_pct = profit_pct
                    rec.outcome_timestamp = datetime.now()
                    logger.info(f"❌ Trade invalidated: {rec.symbol}")
        
        # Check for expiration
        if rec.outcome == TradeOutcome.PENDING:
            # Parse time horizon (e.g., "3-5 days")
            try:
                if "day" in rec.time_horizon:
                    days = int(rec.time_horizon.split("-")[-1].split()[0])
                    if datetime.now() - rec.timestamp > timedelta(days=days):
                        rec.outcome = TradeOutcome.EXPIRED
                        rec.outcome_timestamp = datetime.now()
                        if rec.entry_price:
                            rec.exit_price = current_price
                            if rec.recommendation == "BUY":
                                rec.actual_pnl_pct = (current_price - rec.entry_price) / rec.entry_price * 100
                            else:
                                rec.actual_pnl_pct = (rec.entry_price - current_price) / rec.entry_price * 100
                        logger.info(f"⏰ Trade expired: {rec.symbol}")
            except:
                pass
        
        # Save if outcome changed
        if rec.outcome != TradeOutcome.PENDING:
            self.save_data()
            await self.update_statistics()
        
        return rec.outcome
    
    async def update_statistics(self):
        """Recalculate statistics based on all recommendations"""
        
        stats = BacktestStatistics()
        stats.total_recommendations = len(self.recommendations)
        
        # Filter executed trades
        executed = [r for r in self.recommendations.values() if r.entry_price is not None]
        stats.total_executed = len(executed)
        
        if not executed:
            self.statistics = stats
            return
        
        # Calculate win/loss stats
        wins = [r for r in executed if r.outcome in [TradeOutcome.WIN_TP_HIT, TradeOutcome.WIN_PARTIAL]]
        losses = [r for r in executed if r.outcome in [TradeOutcome.LOSS_SL_HIT, TradeOutcome.LOSS_INVALIDATED]]
        
        stats.wins = len(wins)
        stats.losses = len(losses)
        
        if stats.wins + stats.losses > 0:
            stats.win_rate = stats.wins / (stats.wins + stats.losses) * 100
        
        # Performance by confidence level
        high_conf = [r for r in executed if r.confidence > 70]
        med_conf = [r for r in executed if 50 <= r.confidence <= 70]
        low_conf = [r for r in executed if r.confidence < 50]
        
        if high_conf:
            high_wins = len([r for r in high_conf if r.outcome in [TradeOutcome.WIN_TP_HIT, TradeOutcome.WIN_PARTIAL]])
            stats.high_confidence_win_rate = high_wins / len(high_conf) * 100
        
        if med_conf:
            med_wins = len([r for r in med_conf if r.outcome in [TradeOutcome.WIN_TP_HIT, TradeOutcome.WIN_PARTIAL]])
            stats.medium_confidence_win_rate = med_wins / len(med_conf) * 100
        
        if low_conf:
            low_wins = len([r for r in low_conf if r.outcome in [TradeOutcome.WIN_TP_HIT, TradeOutcome.WIN_PARTIAL]])
            stats.low_confidence_win_rate = low_wins / len(low_conf) * 100
        
        # Risk assessment accuracy
        for risk_level in ["LOW", "MEDIUM", "HIGH"]:
            risk_trades = [r for r in executed if r.risk_assessment == risk_level]
            if risk_trades:
                risk_wins = len([r for r in risk_trades if r.outcome in [TradeOutcome.WIN_TP_HIT, TradeOutcome.WIN_PARTIAL]])
                if risk_level == "LOW":
                    stats.low_risk_success_rate = risk_wins / len(risk_trades) * 100
                elif risk_level == "MEDIUM":
                    stats.medium_risk_success_rate = risk_wins / len(risk_trades) * 100
                else:
                    stats.high_risk_success_rate = risk_wins / len(risk_trades) * 100
        
        # Average performance metrics
        if wins:
            stats.avg_win_pct = sum(r.actual_pnl_pct for r in wins if r.actual_pnl_pct) / len(wins)
        
        if losses:
            stats.avg_loss_pct = sum(r.actual_pnl_pct for r in losses if r.actual_pnl_pct) / len(losses)
        
        if stats.avg_loss_pct != 0:
            stats.profit_factor = abs(stats.avg_win_pct * stats.wins) / abs(stats.avg_loss_pct * stats.losses)
        
        stats.expectancy = (stats.win_rate / 100 * stats.avg_win_pct) + ((1 - stats.win_rate / 100) * stats.avg_loss_pct)
        
        # Time metrics
        tp_times = [r.time_to_outcome for r in wins if r.time_to_outcome]
        if tp_times:
            stats.avg_time_to_tp = sum(tp_times, timedelta()) / len(tp_times)
        
        sl_times = [r.time_to_outcome for r in losses if r.time_to_outcome]
        if sl_times:
            stats.avg_time_to_sl = sum(sl_times, timedelta()) / len(sl_times)
        
        # Pattern performance
        pattern_performance = {}
        for rec in executed:
            for signal in rec.key_signals:
                if signal not in pattern_performance:
                    pattern_performance[signal] = {'wins': 0, 'total': 0}
                pattern_performance[signal]['total'] += 1
                if rec.outcome in [TradeOutcome.WIN_TP_HIT, TradeOutcome.WIN_PARTIAL]:
                    pattern_performance[signal]['wins'] += 1
        
        # Calculate win rates for patterns
        pattern_win_rates = []
        for pattern, perf in pattern_performance.items():
            if perf['total'] >= 3:  # Minimum 3 occurrences
                win_rate = perf['wins'] / perf['total'] * 100
                pattern_win_rates.append((pattern, win_rate))
        
        pattern_win_rates.sort(key=lambda x: x[1], reverse=True)
        stats.best_performing_patterns = pattern_win_rates[:5]
        stats.worst_performing_patterns = pattern_win_rates[-5:] if len(pattern_win_rates) > 5 else []
        
        # Target hit distribution
        target_hits = {0: 0, 1: 0, 2: 0}
        for rec in wins:
            if rec.target_hit_index is not None:
                if rec.target_hit_index < 3:
                    target_hits[rec.target_hit_index] += 1
        
        stats.target_1_hits = target_hits[0]
        stats.target_2_hits = target_hits[1]
        stats.target_3_hits = target_hits[2]
        
        # Find most common target
        if any(target_hits.values()):
            stats.most_common_target = max(target_hits, key=target_hits.get) + 1  # Convert to 1-based index
            
            # Calculate hit rate by target level
            stats.target_hit_rate = {}
            total_targets = sum(target_hits.values())
            if total_targets > 0:
                for idx, hits in target_hits.items():
                    stats.target_hit_rate[idx + 1] = hits / total_targets * 100
        
        # Entry timing accuracy
        for rec in executed:
            if rec.entry_timing_accuracy == "perfect":
                stats.perfect_entries += 1
            elif rec.entry_timing_accuracy == "good":
                stats.good_entries += 1
            elif rec.entry_timing_accuracy == "late":
                stats.late_entries += 1
        
        # Track missed entries (recommendations that never entered)
        never_entered = [r for r in self.recommendations.values() if r.entry_price is None and r.outcome != TradeOutcome.PENDING]
        stats.missed_entries = len(never_entered)
        
        # Calculate actual vs expected R:R
        rr_data = [r for r in executed if r.actual_vs_expected_rr is not None and r.risk_reward > 0]
        if rr_data:
            stats.avg_actual_rr = sum(r.actual_vs_expected_rr for r in rr_data) / len(rr_data)
            stats.avg_expected_rr = sum(r.risk_reward for r in rr_data) / len(rr_data)
            
            # Calculate R:R accuracy (how close actual is to expected)
            rr_deviations = [abs(r.actual_vs_expected_rr - r.risk_reward) / r.risk_reward * 100 for r in rr_data]
            avg_deviation = sum(rr_deviations) / len(rr_deviations)
            stats.rr_accuracy = max(0, 100 - avg_deviation)  # Convert deviation to accuracy %
        
        # Recent performance (last 30 days)
        recent_cutoff = datetime.now() - timedelta(days=30)
        recent = [r for r in executed if r.timestamp > recent_cutoff]
        stats.recent_recommendations = len(recent)
        
        if recent:
            recent_wins = len([r for r in recent if r.outcome in [TradeOutcome.WIN_TP_HIT, TradeOutcome.WIN_PARTIAL]])
            recent_completed = len([r for r in recent if r.outcome != TradeOutcome.PENDING])
            if recent_completed > 0:
                stats.recent_win_rate = recent_wins / recent_completed * 100
        
        stats.last_updated = datetime.now()
        self.statistics = stats
        self.save_data()
    
    def get_performance_summary(self) -> Dict:
        """Get a summary of backtest performance for display"""
        return {
            'total_recommendations': self.statistics.total_recommendations,
            'total_executed': self.statistics.total_executed,
            'win_rate': self.statistics.win_rate,
            'profit_factor': self.statistics.profit_factor,
            'expectancy': self.statistics.expectancy,
            'high_confidence_win_rate': self.statistics.high_confidence_win_rate,
            'recent_win_rate': self.statistics.recent_win_rate,
            'best_patterns': self.statistics.best_performing_patterns[:3] if self.statistics.best_performing_patterns else [],
            'avg_time_to_tp': str(self.statistics.avg_time_to_tp).split('.')[0] if self.statistics.avg_time_to_tp else "N/A",
            'last_updated': self.statistics.last_updated
        }
    
    def format_statistics_for_display(self) -> str:
        """Format statistics for dashboard display"""
        stats = self.statistics
        
        if stats.total_recommendations == 0:
            return "📊 <b>AI Backtest Tracker</b>\n<i>No recommendations recorded yet</i>"
        
        result = "📊 <b>AI TRADE PERFORMANCE</b>\n"
        result += "━" * 20 + "\n"
        
        # Overall performance
        result += f"📈 <b>Overall Performance</b>\n"
        result += f"  • Total Signals: {stats.total_recommendations}\n"
        result += f"  • Executed: {stats.total_executed}\n"
        
        if stats.total_executed > 0:
            win_emoji = "🟢" if stats.win_rate > 60 else "🟡" if stats.win_rate > 40 else "🔴"
            result += f"  • Win Rate: {win_emoji} {stats.win_rate:.1f}%\n"
            result += f"  • Profit Factor: {stats.profit_factor:.2f}\n"
            result += f"  • Expectancy: {stats.expectancy:+.2f}%\n\n"
            
            # Performance by confidence
            result += f"🎯 <b>By Confidence Level</b>\n"
            if stats.high_confidence_win_rate > 0:
                result += f"  • High (>70%): {stats.high_confidence_win_rate:.1f}% wins\n"
            if stats.medium_confidence_win_rate > 0:
                result += f"  • Medium (50-70%): {stats.medium_confidence_win_rate:.1f}% wins\n"
            if stats.low_confidence_win_rate > 0:
                result += f"  • Low (<50%): {stats.low_confidence_win_rate:.1f}% wins\n"
            result += "\n"
            
            # Risk assessment accuracy
            result += f"⚡ <b>Risk Assessment Accuracy</b>\n"
            if stats.low_risk_success_rate > 0:
                result += f"  • Low Risk: {stats.low_risk_success_rate:.1f}% success\n"
            if stats.medium_risk_success_rate > 0:
                result += f"  • Medium Risk: {stats.medium_risk_success_rate:.1f}% success\n"
            if stats.high_risk_success_rate > 0:
                result += f"  • High Risk: {stats.high_risk_success_rate:.1f}% success\n"
            result += "\n"
            
            # Target hit distribution
            if stats.target_hit_rate:
                result += f"🎯 <b>Target Hit Distribution</b>\n"
                for target_num, hit_rate in sorted(stats.target_hit_rate.items()):
                    bar = "█" * int(hit_rate / 10) + "░" * (10 - int(hit_rate / 10))
                    result += f"  • Target {target_num}: {bar} {hit_rate:.1f}%\n"
                if stats.most_common_target:
                    result += f"  • <i>Most hit: Target {stats.most_common_target}</i>\n"
                result += "\n"
            
            # Entry timing accuracy
            if stats.total_executed > 0:
                result += f"⏱️ <b>Entry Timing Accuracy</b>\n"
                perfect_pct = (stats.perfect_entries / stats.total_executed * 100) if stats.total_executed > 0 else 0
                good_pct = (stats.good_entries / stats.total_executed * 100) if stats.total_executed > 0 else 0
                late_pct = (stats.late_entries / stats.total_executed * 100) if stats.total_executed > 0 else 0
                
                if perfect_pct > 0:
                    result += f"  • Perfect: {perfect_pct:.1f}% ({stats.perfect_entries})\n"
                if good_pct > 0:
                    result += f"  • Good: {good_pct:.1f}% ({stats.good_entries})\n"
                if late_pct > 0:
                    result += f"  • Late: {late_pct:.1f}% ({stats.late_entries})\n"
                if stats.missed_entries > 0:
                    result += f"  • Missed: {stats.missed_entries} trades\n"
                result += "\n"
            
            # R:R accuracy
            if stats.rr_accuracy > 0:
                result += f"📊 <b>Risk/Reward Accuracy</b>\n"
                result += f"  • Expected R:R: {stats.avg_expected_rr:.2f}\n"
                result += f"  • Actual R:R: {stats.avg_actual_rr:.2f}\n"
                accuracy_emoji = "🟢" if stats.rr_accuracy > 80 else "🟡" if stats.rr_accuracy > 60 else "🔴"
                result += f"  • Accuracy: {accuracy_emoji} {stats.rr_accuracy:.1f}%\n"
                result += "\n"
            
            # Best performing patterns
            if stats.best_performing_patterns:
                result += f"🏆 <b>Best Patterns</b>\n"
                for pattern, win_rate in stats.best_performing_patterns[:3]:
                    result += f"  • {pattern}: {win_rate:.1f}% wins\n"
                result += "\n"
            
            # Recent performance
            if stats.recent_recommendations > 0:
                trend_emoji = "📈" if stats.recent_win_rate > stats.win_rate else "📉"
                result += f"{trend_emoji} <b>Last 30 Days</b>\n"
                result += f"  • Signals: {stats.recent_recommendations}\n"
                result += f"  • Win Rate: {stats.recent_win_rate:.1f}%\n"
        
        return result

# Global instance
ai_backtest_tracker = AIBacktestTracker()