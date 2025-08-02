#!/usr/bin/env python3
"""
Data models for the enhanced dashboard system
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime


@dataclass
class AccountSummary:
    """Account summary data model"""
    balance: Decimal
    available_balance: Decimal
    margin_used: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    position_count: int
    order_count: int
    health_score: float
    account_type: str = "main"  # "main" or "mirror"

    @property
    def total_pnl(self) -> Decimal:
        return self.unrealized_pnl + self.realized_pnl

    @property
    def balance_used_pct(self) -> float:
        if self.balance > 0:
            return float(self.margin_used / self.balance * 100)
        return 0.0

    @property
    def health_emoji(self) -> str:
        if self.health_score >= 80:
            return "🟢"
        elif self.health_score >= 60:
            return "🟡"
        elif self.health_score >= 40:
            return "🟠"
        return "🔴"

    @property
    def health_status(self) -> str:
        if self.health_score >= 80:
            return "Excellent"
        elif self.health_score >= 60:
            return "Good"
        elif self.health_score >= 40:
            return "Caution"
        return "Risk"


@dataclass
class PnLAnalysis:
    """P&L analysis data model"""
    tp_profit: Decimal
    tp_full_profit: Decimal
    all_tp_profit: Decimal
    all_sl_loss: Decimal
    tp_coverage: float
    
    # Legacy aliases for backward compatibility
    @property
    def tp1_profit(self) -> Decimal:
        return self.tp_profit
    
    @property
    def tp1_full_profit(self) -> Decimal:
        return self.tp_full_profit
    
    @property
    def tp1_coverage(self) -> float:
        return self.tp_coverage

    @property
    def risk_reward_ratio(self) -> float:
        if self.all_sl_loss > 0:
            return float(self.all_tp_profit / self.all_sl_loss)
        return 0.0


@dataclass
class PositionSummary:
    """Position summary data model"""
    symbol: str
    side: str
    size: Decimal
    avg_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    pnl_percentage: float
    margin_used: Decimal
    has_tp: bool = False
    has_sl: bool = False
    approach: str = "unknown"  # "fast", "conservative", "unknown"
    account_type: str = "main"  # "main" or "mirror" - source account tracking

    @property
    def pnl_emoji(self) -> str:
        if self.unrealized_pnl > 0:
            return "📈"
        elif self.unrealized_pnl < 0:
            return "📉"
        return "➖"

    @property
    def direction_emoji(self) -> str:
        return "🟢" if self.side == "Buy" else "🔴"

    @property
    def account_indicator(self) -> str:
        """Account type indicator for display"""
        if self.account_type == "mirror":
            return "🪞"
        return "🔷"

    @property
    def full_symbol_display(self) -> str:
        """Full symbol with account indicator"""
        return f"{self.account_indicator} {self.symbol}"


@dataclass
class PerformanceMetrics:
    """Performance metrics data model"""
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    recovery_factor: float
    best_trade: Decimal
    worst_trade: Decimal
    avg_trade: Decimal
    current_streak: Tuple[str, int]  # ("win" or "loss", count)

    @property
    def profit_factor_display(self) -> str:
        if self.total_trades == 0:
            return "Building..."
        elif self.profit_factor >= 999:
            return "∞"
        elif self.profit_factor == 0:
            return "N/A"
        return f"{self.profit_factor:.2f}"

    @property
    def streak_display(self) -> str:
        if self.total_trades == 0:
            return "🚀 Ready to Start"
        
        streak_type, count = self.current_streak
        if count == 0:
            return "⚖️ None"
        elif streak_type == "win":
            return f"🔥 {count} wins"
        else:
            return f"❄️ {count} losses"


@dataclass
class MarketStatus:
    """Enhanced market status data model with comprehensive analysis"""
    # Basic info
    primary_symbol: Optional[str] = None
    timestamp: Optional[datetime] = None

    # Core metrics with enhanced data
    market_sentiment: str = "Neutral"
    sentiment_score: float = 50.0  # 0-100
    sentiment_emoji: str = "⚖️"

    volatility: str = "Normal"
    volatility_score: float = 50.0  # 0-100 percentile
    volatility_percentage: Optional[float] = None  # Actual volatility %
    volatility_emoji: str = "📊"

    trend: str = "Ranging"
    trend_strength: float = 0.0  # -100 to 100
    trend_emoji: str = "↔️"

    momentum: str = "Neutral"
    momentum_score: float = 0.0  # -100 to 100
    momentum_emoji: str = "⚡"

    # Advanced analysis
    market_regime: str = "Ranging Market"
    regime_strength: float = 0.0  # 0-100
    volume_strength: float = 50.0  # 0-100

    # Price information
    current_price: float = 0.0
    price_change_24h: float = 0.0
    price_change_pct_24h: float = 0.0

    # NEW: Support and Resistance levels
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None

    # NEW: Volume Profile
    volume_profile: Optional[str] = None  # "High", "Normal", "Low"
    volume_ratio: Optional[float] = None  # Multiplier vs average

    # NEW: Market Structure
    market_structure: Optional[str] = None  # "HH-HL", "LH-LL", etc.
    structure_bias: Optional[str] = None  # "Bullish", "Bearish", "Neutral"

    # NEW: Funding and Open Interest (for perpetuals)
    funding_rate: Optional[float] = None  # Percentage
    funding_bias: Optional[str] = None  # "Bullish", "Bearish", "Neutral"
    open_interest_change_24h: Optional[float] = None  # Percentage change

    # NEW: AI Recommendation (GPT-4 Enhanced)
    ai_recommendation: Optional[str] = None  # "BUY", "HOLD", "SELL"
    ai_reasoning: Optional[str] = None  # Brief explanation
    ai_risk_assessment: Optional[str] = None  # "LOW", "MEDIUM", "HIGH"
    ai_confidence: Optional[float] = None  # Enhanced confidence from AI

    # Confidence and quality
    confidence: float = 0.0  # 0-100
    data_quality: float = 0.0  # 0-100
    analysis_depth: str = "Basic"  # "Basic", "Standard", "Comprehensive"

    # Key levels
    key_levels: Dict[str, float] = field(default_factory=dict)

    # Source attribution
    data_sources: List[str] = field(default_factory=lambda: ["fallback"])
    last_updated: Optional[datetime] = None

    @property
    def confidence_emoji(self) -> str:
        """Visual indicator for analysis confidence"""
        if self.confidence >= 80:
            return "🟢"
        elif self.confidence >= 60:
            return "🟡"
        elif self.confidence >= 40:
            return "🟠"
        return "🔴"

    @property
    def quality_indicator(self) -> str:
        """Data quality indicator"""
        if self.data_quality >= 80:
            return "High"
        elif self.data_quality >= 60:
            return "Medium"
        elif self.data_quality >= 40:
            return "Low"
        return "Poor"

    @property
    def is_enhanced(self) -> bool:
        """Check if this uses enhanced analysis"""
        return "bybit_api" in self.data_sources and "technical_analysis" in self.data_sources

    @property
    def price_display(self) -> str:
        """Formatted price with change"""
        if self.current_price > 0:
            change_sign = "+" if self.price_change_pct_24h >= 0 else ""
            return f"${self.current_price:,.4f} ({change_sign}{self.price_change_pct_24h:.2f}%)"
        return "N/A"


@dataclass
class DashboardData:
    """Complete dashboard data model"""
    main_account: AccountSummary
    mirror_account: Optional[AccountSummary]
    main_pnl: PnLAnalysis
    mirror_pnl: Optional[PnLAnalysis]
    positions: List[PositionSummary]
    performance: PerformanceMetrics
    market_status: MarketStatus
    active_monitors: Dict[str, int]  # approach -> count
    last_update: datetime = field(default_factory=datetime.now)

    @property
    def total_positions(self) -> int:
        return len(self.positions)

    @property
    def main_positions(self) -> List[PositionSummary]:
        # In current implementation, all positions are main account
        return self.positions

    @property
    def has_mirror(self) -> bool:
        return self.mirror_account is not None