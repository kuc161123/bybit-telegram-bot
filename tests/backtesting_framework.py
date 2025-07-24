#!/usr/bin/env python3
"""
Backtesting Framework for Enhanced Market Analysis
Validates historical predictions and analysis accuracy
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics
import numpy as np
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Represents a backtested trade"""
    entry_time: datetime
    exit_time: Optional[datetime]
    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    exit_price: Optional[float]
    quantity: float
    pnl: Optional[float]
    pnl_percentage: Optional[float]
    recommendation_source: str  # "market_regime", "pattern", "ai"
    confidence: float
    status: str  # "open", "closed", "stopped_out"
    stop_loss: Optional[float]
    take_profit: Optional[float]
    max_drawdown: Optional[float]


@dataclass
class BacktestMetrics:
    """Backtesting performance metrics"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_pnl: float
    roi_percentage: float
    avg_trade_duration: timedelta
    best_trade: Optional[BacktestTrade]
    worst_trade: Optional[BacktestTrade]
    strategy_score: float  # 0-100 composite score


class BacktestingFramework:
    """Framework for backtesting market analysis strategies"""
    
    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.trades: List[BacktestTrade] = []
        self.historical_data: Dict[str, List] = {}
        self.position_size_pct = 0.02  # 2% risk per trade
        self.max_concurrent_trades = 5
        self.commission_rate = 0.0006  # 0.06% taker fee
        
    async def load_historical_data(
        self, 
        symbol: str, 
        start_date: datetime,
        end_date: datetime,
        interval: str = "5m"
    ) -> bool:
        """Load historical price data for backtesting"""
        from clients.bybit_client import bybit_client
        
        logger.info(f"Loading historical data for {symbol} from {start_date} to {end_date}")
        
        try:
            # In real implementation, would fetch historical data
            # For now, generate synthetic data
            self.historical_data[symbol] = self._generate_synthetic_data(
                symbol, start_date, end_date, interval
            )
            
            logger.info(f"Loaded {len(self.historical_data[symbol])} data points")
            return True
            
        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            return False
    
    def _generate_synthetic_data(
        self, 
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str
    ) -> List[Dict]:
        """Generate synthetic price data for testing"""
        data = []
        current_time = start_date
        base_price = 100000 if "BTC" in symbol else 100
        
        # Calculate interval in minutes
        interval_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "4h": 240, "1d": 1440
        }.get(interval, 5)
        
        i = 0
        while current_time <= end_date:
            # Generate realistic price movement
            trend = np.sin(i * 0.01) * 0.02  # 2% trend
            noise = np.random.randn() * 0.005  # 0.5% noise
            price_change = trend + noise
            
            price = base_price * (1 + price_change)
            
            data.append({
                "timestamp": current_time,
                "open": price,
                "high": price * (1 + abs(np.random.randn() * 0.001)),
                "low": price * (1 - abs(np.random.randn() * 0.001)),
                "close": price * (1 + np.random.randn() * 0.0005),
                "volume": 1000 + abs(np.random.randn() * 100),
                "symbol": symbol
            })
            
            current_time += timedelta(minutes=interval_minutes)
            i += 1
            
        return data
    
    async def backtest_market_regime_strategy(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestMetrics:
        """Backtest market regime-based trading strategy"""
        from market_analysis.market_status_engine_enhanced import enhanced_market_status_engine
        
        logger.info("🔄 Backtesting Market Regime Strategy...")
        
        if symbol not in self.historical_data:
            await self.load_historical_data(symbol, start_date, end_date)
        
        data = self.historical_data[symbol]
        open_trades: List[BacktestTrade] = []
        
        for i in range(100, len(data)):  # Need history for indicators
            current_data = data[i]
            historical_slice = data[max(0, i-100):i]
            
            # Get market analysis
            kline_data = self._format_kline_data(historical_slice)
            
            status = await enhanced_market_status_engine.get_enhanced_market_status(
                symbol=symbol,
                enable_ai_analysis=False,
                kline_data_override=kline_data,
                price_override=current_data["close"]
            )
            
            # Trading logic based on market regime
            signal = self._get_regime_signal(status.market_regime, status.confidence)
            
            # Manage positions
            await self._manage_positions(
                open_trades, current_data, signal, status.confidence, "market_regime"
            )
            
            # Check stop losses and take profits
            self._check_exits(open_trades, current_data)
            
            # Limit concurrent trades
            open_trades = [t for t in open_trades if t.status == "open"]
            
        # Close all remaining positions
        for trade in open_trades:
            self._close_trade(trade, data[-1]["close"], data[-1]["timestamp"])
        
        return self._calculate_metrics()
    
    async def backtest_pattern_strategy(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestMetrics:
        """Backtest pattern recognition trading strategy"""
        from market_analysis.pattern_recognition import pattern_recognition_engine
        
        logger.info("📊 Backtesting Pattern Recognition Strategy...")
        
        if symbol not in self.historical_data:
            await self.load_historical_data(symbol, start_date, end_date)
        
        data = self.historical_data[symbol]
        open_trades: List[BacktestTrade] = []
        
        for i in range(100, len(data)):
            current_data = data[i]
            historical_slice = data[max(0, i-100):i]
            
            # Analyze patterns
            kline_data = self._format_kline_data(historical_slice)
            pattern_analysis = await pattern_recognition_engine.analyze_patterns(
                symbol=symbol,
                kline_data=kline_data,
                current_price=current_data["close"]
            )
            
            # Trading logic based on patterns
            if pattern_analysis.dominant_signal != "neutral" and pattern_analysis.confidence_average > 70:
                signal = "long" if pattern_analysis.dominant_signal == "bullish" else "short"
                
                # Find patterns with targets
                patterns_with_targets = [
                    p for p in pattern_analysis.chart_patterns 
                    if p.target_price and p.confidence > 75
                ]
                
                if patterns_with_targets and len(open_trades) < self.max_concurrent_trades:
                    pattern = patterns_with_targets[0]
                    
                    trade = BacktestTrade(
                        entry_time=current_data["timestamp"],
                        exit_time=None,
                        symbol=symbol,
                        direction=signal,
                        entry_price=current_data["close"],
                        exit_price=None,
                        quantity=self._calculate_position_size(current_data["close"]),
                        pnl=None,
                        pnl_percentage=None,
                        recommendation_source="pattern",
                        confidence=pattern.confidence,
                        status="open",
                        stop_loss=pattern.stop_loss,
                        take_profit=pattern.target_price,
                        max_drawdown=None
                    )
                    
                    open_trades.append(trade)
                    self.trades.append(trade)
            
            # Check exits
            self._check_exits(open_trades, current_data)
            open_trades = [t for t in open_trades if t.status == "open"]
        
        # Close remaining positions
        for trade in open_trades:
            self._close_trade(trade, data[-1]["close"], data[-1]["timestamp"])
        
        return self._calculate_metrics()
    
    async def backtest_combined_strategy(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestMetrics:
        """Backtest combined strategy using all components"""
        from market_analysis.market_status_engine_enhanced import enhanced_market_status_engine
        from market_analysis.pattern_recognition import pattern_recognition_engine
        from market_analysis.sentiment_aggregator import sentiment_aggregator
        
        logger.info("🚀 Backtesting Combined Strategy...")
        
        if symbol not in self.historical_data:
            await self.load_historical_data(symbol, start_date, end_date)
        
        data = self.historical_data[symbol]
        open_trades: List[BacktestTrade] = []
        
        async with sentiment_aggregator as sent_agg:
            for i in range(100, len(data), 5):  # Sample every 5 bars
                current_data = data[i]
                historical_slice = data[max(0, i-100):i]
                kline_data = self._format_kline_data(historical_slice)
                
                # Get comprehensive analysis
                status = await enhanced_market_status_engine.get_enhanced_market_status(
                    symbol=symbol,
                    enable_ai_analysis=False,
                    kline_data_override=kline_data,
                    price_override=current_data["close"]
                )
                
                pattern_analysis = await pattern_recognition_engine.analyze_patterns(
                    symbol=symbol,
                    kline_data=kline_data,
                    current_price=current_data["close"]
                )
                
                # Combined signal generation
                signal = self._generate_combined_signal(
                    status, pattern_analysis, None  # No real sentiment in backtest
                )
                
                if signal["action"] != "hold" and len(open_trades) < self.max_concurrent_trades:
                    trade = BacktestTrade(
                        entry_time=current_data["timestamp"],
                        exit_time=None,
                        symbol=symbol,
                        direction="long" if signal["action"] == "buy" else "short",
                        entry_price=current_data["close"],
                        exit_price=None,
                        quantity=self._calculate_position_size(current_data["close"]),
                        pnl=None,
                        pnl_percentage=None,
                        recommendation_source="combined",
                        confidence=signal["confidence"],
                        status="open",
                        stop_loss=signal.get("stop_loss"),
                        take_profit=signal.get("take_profit"),
                        max_drawdown=None
                    )
                    
                    open_trades.append(trade)
                    self.trades.append(trade)
                
                # Update drawdowns and check exits
                self._update_drawdowns(open_trades, current_data["close"])
                self._check_exits(open_trades, current_data)
                open_trades = [t for t in open_trades if t.status == "open"]
        
        # Close remaining positions
        for trade in open_trades:
            self._close_trade(trade, data[-1]["close"], data[-1]["timestamp"])
        
        return self._calculate_metrics()
    
    def _get_regime_signal(self, regime: str, confidence: float) -> Optional[str]:
        """Generate trading signal from market regime"""
        if confidence < 60:
            return None
            
        regime_signals = {
            "Bull Market": "long",
            "Bear Market": "short",
            "Accumulation": "long",
            "Distribution": "short",
            "Breakout": "long",
            "Breakdown": "short"
        }
        
        return regime_signals.get(regime)
    
    def _generate_combined_signal(
        self, 
        status, 
        pattern_analysis, 
        sentiment
    ) -> Dict:
        """Generate combined signal from all analyses"""
        # Weight different components
        regime_weight = 0.3
        pattern_weight = 0.4
        sentiment_weight = 0.3
        
        # Calculate directional scores
        bullish_score = 0
        bearish_score = 0
        
        # Market regime contribution
        if status.market_regime in ["Bull Market", "Accumulation", "Breakout"]:
            bullish_score += regime_weight * (status.confidence / 100)
        elif status.market_regime in ["Bear Market", "Distribution", "Breakdown"]:
            bearish_score += regime_weight * (status.confidence / 100)
        
        # Pattern contribution
        if pattern_analysis.dominant_signal == "bullish":
            bullish_score += pattern_weight * (pattern_analysis.confidence_average / 100)
        elif pattern_analysis.dominant_signal == "bearish":
            bearish_score += pattern_weight * (pattern_analysis.confidence_average / 100)
        
        # Determine action
        if bullish_score > bearish_score and bullish_score > 0.5:
            action = "buy"
            confidence = bullish_score * 100
        elif bearish_score > bullish_score and bearish_score > 0.5:
            action = "sell"
            confidence = bearish_score * 100
        else:
            action = "hold"
            confidence = 50
        
        # Set targets from patterns if available
        stop_loss = None
        take_profit = None
        
        if pattern_analysis.chart_patterns:
            relevant_patterns = [
                p for p in pattern_analysis.chart_patterns
                if p.signal == pattern_analysis.dominant_signal and p.target_price
            ]
            if relevant_patterns:
                pattern = relevant_patterns[0]
                stop_loss = pattern.stop_loss
                take_profit = pattern.target_price
        
        return {
            "action": action,
            "confidence": confidence,
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }
    
    async def _manage_positions(
        self,
        open_trades: List[BacktestTrade],
        current_data: Dict,
        signal: Optional[str],
        confidence: float,
        source: str
    ):
        """Manage position entries and exits"""
        if signal and len(open_trades) < self.max_concurrent_trades and confidence > 60:
            trade = BacktestTrade(
                entry_time=current_data["timestamp"],
                exit_time=None,
                symbol=current_data["symbol"],
                direction=signal,
                entry_price=current_data["close"],
                exit_price=None,
                quantity=self._calculate_position_size(current_data["close"]),
                pnl=None,
                pnl_percentage=None,
                recommendation_source=source,
                confidence=confidence,
                status="open",
                stop_loss=self._calculate_stop_loss(current_data["close"], signal),
                take_profit=self._calculate_take_profit(current_data["close"], signal),
                max_drawdown=None
            )
            
            open_trades.append(trade)
            self.trades.append(trade)
    
    def _check_exits(self, open_trades: List[BacktestTrade], current_data: Dict):
        """Check for stop loss and take profit exits"""
        for trade in open_trades:
            if trade.status != "open":
                continue
                
            current_price = current_data["close"]
            
            # Check stop loss
            if trade.stop_loss:
                if (trade.direction == "long" and current_price <= trade.stop_loss) or \
                   (trade.direction == "short" and current_price >= trade.stop_loss):
                    self._close_trade(trade, trade.stop_loss, current_data["timestamp"])
                    trade.status = "stopped_out"
                    continue
            
            # Check take profit
            if trade.take_profit:
                if (trade.direction == "long" and current_price >= trade.take_profit) or \
                   (trade.direction == "short" and current_price <= trade.take_profit):
                    self._close_trade(trade, trade.take_profit, current_data["timestamp"])
                    continue
    
    def _close_trade(self, trade: BacktestTrade, exit_price: float, exit_time: datetime):
        """Close a trade and calculate P&L"""
        trade.exit_price = exit_price
        trade.exit_time = exit_time
        trade.status = "closed"
        
        # Calculate P&L
        if trade.direction == "long":
            price_change = exit_price - trade.entry_price
        else:
            price_change = trade.entry_price - exit_price
            
        # Account for commission
        commission = (trade.entry_price + exit_price) * trade.quantity * self.commission_rate
        
        trade.pnl = (price_change * trade.quantity) - commission
        trade.pnl_percentage = (price_change / trade.entry_price) * 100
        
        # Update capital
        self.current_capital += trade.pnl
    
    def _update_drawdowns(self, open_trades: List[BacktestTrade], current_price: float):
        """Update maximum drawdown for open trades"""
        for trade in open_trades:
            if trade.status != "open":
                continue
                
            if trade.direction == "long":
                current_pnl_pct = ((current_price - trade.entry_price) / trade.entry_price) * 100
            else:
                current_pnl_pct = ((trade.entry_price - current_price) / trade.entry_price) * 100
            
            if trade.max_drawdown is None or current_pnl_pct < trade.max_drawdown:
                trade.max_drawdown = current_pnl_pct
    
    def _calculate_position_size(self, price: float) -> float:
        """Calculate position size based on risk management"""
        risk_amount = self.current_capital * self.position_size_pct
        return risk_amount / price
    
    def _calculate_stop_loss(self, price: float, direction: str) -> float:
        """Calculate stop loss price"""
        stop_distance = 0.02  # 2% stop loss
        if direction == "long":
            return price * (1 - stop_distance)
        else:
            return price * (1 + stop_distance)
    
    def _calculate_take_profit(self, price: float, direction: str) -> float:
        """Calculate take profit price"""
        tp_distance = 0.03  # 3% take profit
        if direction == "long":
            return price * (1 + tp_distance)
        else:
            return price * (1 - tp_distance)
    
    def _format_kline_data(self, historical_slice: List[Dict]) -> Dict:
        """Format historical data into kline format"""
        klines = []
        for data in historical_slice:
            klines.append([
                int(data["timestamp"].timestamp() * 1000),
                data["open"],
                data["high"],
                data["low"],
                data["close"],
                data["volume"]
            ])
        
        return {
            "5m": klines,
            "15m": klines[::3] if len(klines) >= 3 else klines,
            "1h": klines[::12] if len(klines) >= 12 else klines
        }
    
    def _calculate_metrics(self) -> BacktestMetrics:
        """Calculate comprehensive backtest metrics"""
        closed_trades = [t for t in self.trades if t.status == "closed"]
        
        if not closed_trades:
            return BacktestMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                avg_win=0,
                avg_loss=0,
                profit_factor=0,
                sharpe_ratio=0,
                max_drawdown=0,
                total_pnl=0,
                roi_percentage=0,
                avg_trade_duration=timedelta(0),
                best_trade=None,
                worst_trade=None,
                strategy_score=0
            )
        
        # Calculate basic metrics
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]
        
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0
        
        avg_win = statistics.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = statistics.mean([abs(t.pnl) for t in losing_trades]) if losing_trades else 0
        
        # Profit factor
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = sum(abs(t.pnl) for t in losing_trades)
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Sharpe ratio (simplified)
        returns = [t.pnl_percentage for t in closed_trades]
        if len(returns) > 1:
            sharpe_ratio = statistics.mean(returns) / statistics.stdev(returns) if statistics.stdev(returns) > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Max drawdown
        cumulative_pnl = []
        running_total = 0
        for trade in sorted(closed_trades, key=lambda x: x.exit_time):
            running_total += trade.pnl
            cumulative_pnl.append(running_total)
        
        if cumulative_pnl:
            peak = cumulative_pnl[0]
            max_dd = 0
            for value in cumulative_pnl:
                if value > peak:
                    peak = value
                dd = (peak - value) / self.initial_capital * 100
                if dd > max_dd:
                    max_dd = dd
        else:
            max_dd = 0
        
        # Total P&L and ROI
        total_pnl = sum(t.pnl for t in closed_trades)
        roi_percentage = (total_pnl / self.initial_capital) * 100
        
        # Average trade duration
        durations = [
            (t.exit_time - t.entry_time) for t in closed_trades 
            if t.exit_time and t.entry_time
        ]
        avg_duration = sum(durations, timedelta()) / len(durations) if durations else timedelta(0)
        
        # Best and worst trades
        best_trade = max(closed_trades, key=lambda x: x.pnl) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda x: x.pnl) if closed_trades else None
        
        # Strategy score (0-100)
        score_components = [
            win_rate * 40,  # 40 points for win rate
            min(profit_factor / 2, 1) * 20,  # 20 points for profit factor
            (1 - min(max_dd / 20, 1)) * 20,  # 20 points for low drawdown
            min(abs(sharpe_ratio), 2) / 2 * 20  # 20 points for Sharpe ratio
        ]
        strategy_score = sum(score_components)
        
        return BacktestMetrics(
            total_trades=len(closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_dd,
            total_pnl=total_pnl,
            roi_percentage=roi_percentage,
            avg_trade_duration=avg_duration,
            best_trade=best_trade,
            worst_trade=worst_trade,
            strategy_score=strategy_score
        )
    
    def generate_backtest_report(self, metrics: BacktestMetrics) -> Dict:
        """Generate comprehensive backtest report"""
        logger.info("\n" + "="*60)
        logger.info("📊 BACKTEST REPORT")
        logger.info("="*60)
        
        logger.info(f"\n📈 PERFORMANCE SUMMARY:")
        logger.info(f"  Total Trades: {metrics.total_trades}")
        logger.info(f"  Win Rate: {metrics.win_rate:.1%}")
        logger.info(f"  Profit Factor: {metrics.profit_factor:.2f}")
        logger.info(f"  Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        logger.info(f"  Max Drawdown: {metrics.max_drawdown:.1f}%")
        
        logger.info(f"\n💰 P&L ANALYSIS:")
        logger.info(f"  Total P&L: ${metrics.total_pnl:,.2f}")
        logger.info(f"  ROI: {metrics.roi_percentage:.1f}%")
        logger.info(f"  Average Win: ${metrics.avg_win:,.2f}")
        logger.info(f"  Average Loss: ${metrics.avg_loss:,.2f}")
        
        logger.info(f"\n⏱️ TRADE STATISTICS:")
        logger.info(f"  Winning Trades: {metrics.winning_trades}")
        logger.info(f"  Losing Trades: {metrics.losing_trades}")
        logger.info(f"  Avg Trade Duration: {metrics.avg_trade_duration}")
        
        if metrics.best_trade:
            logger.info(f"\n🏆 Best Trade:")
            logger.info(f"  P&L: ${metrics.best_trade.pnl:,.2f} ({metrics.best_trade.pnl_percentage:.1f}%)")
            logger.info(f"  Source: {metrics.best_trade.recommendation_source}")
            
        if metrics.worst_trade:
            logger.info(f"\n😰 Worst Trade:")
            logger.info(f"  P&L: ${metrics.worst_trade.pnl:,.2f} ({metrics.worst_trade.pnl_percentage:.1f}%)")
            logger.info(f"  Source: {metrics.worst_trade.recommendation_source}")
        
        logger.info(f"\n🎯 STRATEGY SCORE: {metrics.strategy_score:.1f}/100")
        
        # Generate report dictionary
        report = {
            "timestamp": datetime.now().isoformat(),
            "metrics": asdict(metrics),
            "capital": {
                "initial": self.initial_capital,
                "final": self.current_capital,
                "change": self.current_capital - self.initial_capital
            },
            "trade_details": [asdict(t) for t in self.trades[:10]]  # First 10 trades
        }
        
        # Save report
        filename = f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"\n📄 Report saved to: {filename}")
        logger.info("="*60 + "\n")
        
        return report
    
    async def run_comprehensive_backtest(
        self,
        symbol: str = "BTCUSDT",
        days_back: int = 30
    ) -> Dict:
        """Run comprehensive backtest of all strategies"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        logger.info(f"🚀 Running Comprehensive Backtest")
        logger.info(f"  Symbol: {symbol}")
        logger.info(f"  Period: {start_date.date()} to {end_date.date()}")
        logger.info(f"  Initial Capital: ${self.initial_capital:,.2f}\n")
        
        results = {}
        
        # Test individual strategies
        strategies = [
            ("Market Regime", self.backtest_market_regime_strategy),
            ("Pattern Recognition", self.backtest_pattern_strategy),
            ("Combined", self.backtest_combined_strategy)
        ]
        
        for strategy_name, strategy_func in strategies:
            # Reset for each strategy
            self.trades = []
            self.current_capital = self.initial_capital
            
            logger.info(f"\n{'='*40}")
            logger.info(f"Testing {strategy_name} Strategy")
            logger.info(f"{'='*40}")
            
            metrics = await strategy_func(symbol, start_date, end_date)
            report = self.generate_backtest_report(metrics)
            results[strategy_name] = report
        
        # Compare strategies
        logger.info("\n" + "="*60)
        logger.info("📊 STRATEGY COMPARISON")
        logger.info("="*60)
        
        comparison = []
        for strategy, report in results.items():
            metrics = report["metrics"]
            comparison.append({
                "Strategy": strategy,
                "Score": f"{metrics['strategy_score']:.1f}",
                "Win Rate": f"{metrics['win_rate']:.1%}",
                "ROI": f"{metrics['roi_percentage']:.1f}%",
                "Max DD": f"{metrics['max_drawdown']:.1f}%",
                "Sharpe": f"{metrics['sharpe_ratio']:.2f}"
            })
        
        # Print comparison table
        headers = ["Strategy", "Score", "Win Rate", "ROI", "Max DD", "Sharpe"]
        col_widths = [15, 8, 10, 10, 10, 8]
        
        # Header
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        logger.info(header_line)
        logger.info("-" * len(header_line))
        
        # Data rows
        for row in comparison:
            row_line = " | ".join(
                str(row[h]).ljust(w) for h, w in zip(headers, col_widths)
            )
            logger.info(row_line)
        
        # Best strategy
        best_strategy = max(comparison, key=lambda x: float(x["Score"]))
        logger.info(f"\n🏆 Best Strategy: {best_strategy['Strategy']} (Score: {best_strategy['Score']})")
        
        return results


async def main():
    """Run backtesting framework"""
    framework = BacktestingFramework(initial_capital=100000)
    
    # Run comprehensive backtest
    results = await framework.run_comprehensive_backtest(
        symbol="BTCUSDT",
        days_back=30
    )
    
    return results


if __name__ == "__main__":
    # Initialize environment
    import dotenv
    dotenv.load_dotenv()
    
    # Run backtesting
    asyncio.run(main())