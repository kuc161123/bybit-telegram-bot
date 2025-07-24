#!/usr/bin/env python3
"""
Test the Backtesting Framework
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from backtesting_framework import BacktestingFramework, BacktestTrade, BacktestMetrics


class TestBacktestingFramework:
    """Test suite for backtesting framework"""
    
    @pytest.mark.asyncio
    async def test_basic_backtest_functionality(self):
        """Test basic backtesting functionality"""
        framework = BacktestingFramework(initial_capital=10000)
        
        # Test with short period
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        # Run market regime backtest
        metrics = await framework.backtest_market_regime_strategy(
            symbol="BTCUSDT",
            start_date=start_date,
            end_date=end_date
        )
        
        # Verify metrics structure
        assert isinstance(metrics, BacktestMetrics)
        assert metrics.total_trades >= 0
        assert 0 <= metrics.win_rate <= 1
        assert metrics.strategy_score >= 0
    
    @pytest.mark.asyncio
    async def test_pattern_strategy_backtest(self):
        """Test pattern recognition strategy backtest"""
        framework = BacktestingFramework(initial_capital=10000)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        metrics = await framework.backtest_pattern_strategy(
            symbol="BTCUSDT",
            start_date=start_date,
            end_date=end_date
        )
        
        # Check metrics validity
        assert metrics.winning_trades + metrics.losing_trades == metrics.total_trades
        if metrics.total_trades > 0:
            assert metrics.win_rate == metrics.winning_trades / metrics.total_trades
    
    @pytest.mark.asyncio
    async def test_combined_strategy_backtest(self):
        """Test combined strategy backtest"""
        framework = BacktestingFramework(initial_capital=10000)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3)  # Shorter for speed
        
        metrics = await framework.backtest_combined_strategy(
            symbol="BTCUSDT",
            start_date=start_date,
            end_date=end_date
        )
        
        # Verify P&L calculations
        if metrics.total_trades > 0:
            assert metrics.roi_percentage == (metrics.total_pnl / 10000) * 100
    
    def test_position_sizing(self):
        """Test position sizing calculations"""
        framework = BacktestingFramework(initial_capital=10000)
        framework.position_size_pct = 0.02  # 2% risk
        
        position_size = framework._calculate_position_size(100000)  # BTC price
        
        # Should be 2% of capital divided by price
        expected_size = (10000 * 0.02) / 100000
        assert abs(position_size - expected_size) < 0.0001
    
    def test_stop_loss_take_profit_calculation(self):
        """Test SL/TP calculations"""
        framework = BacktestingFramework()
        
        # Test long position
        sl_long = framework._calculate_stop_loss(100000, "long")
        tp_long = framework._calculate_take_profit(100000, "long")
        
        assert sl_long < 100000  # SL below entry for long
        assert tp_long > 100000  # TP above entry for long
        assert abs(sl_long - 98000) < 1  # 2% SL
        assert abs(tp_long - 103000) < 1  # 3% TP
        
        # Test short position
        sl_short = framework._calculate_stop_loss(100000, "short")
        tp_short = framework._calculate_take_profit(100000, "short")
        
        assert sl_short > 100000  # SL above entry for short
        assert tp_short < 100000  # TP below entry for short
    
    def test_trade_closure_pnl(self):
        """Test trade closure and P&L calculation"""
        framework = BacktestingFramework(initial_capital=10000)
        
        # Create a test trade
        trade = BacktestTrade(
            entry_time=datetime.now(),
            exit_time=None,
            symbol="BTCUSDT",
            direction="long",
            entry_price=100000,
            exit_price=None,
            quantity=0.01,
            pnl=None,
            pnl_percentage=None,
            recommendation_source="test",
            confidence=80,
            status="open",
            stop_loss=98000,
            take_profit=103000,
            max_drawdown=None
        )
        
        # Close with profit
        framework._close_trade(trade, 102000, datetime.now())
        
        # Check P&L calculation
        assert trade.status == "closed"
        assert trade.exit_price == 102000
        assert trade.pnl is not None
        assert trade.pnl > 0  # Should be profitable
        assert trade.pnl_percentage == 2.0  # 2% profit
    
    def test_metrics_calculation(self):
        """Test comprehensive metrics calculation"""
        framework = BacktestingFramework(initial_capital=10000)
        
        # Add some test trades
        framework.trades = [
            BacktestTrade(
                entry_time=datetime.now() - timedelta(hours=2),
                exit_time=datetime.now() - timedelta(hours=1),
                symbol="BTCUSDT",
                direction="long",
                entry_price=100000,
                exit_price=101000,
                quantity=0.01,
                pnl=10,
                pnl_percentage=1.0,
                recommendation_source="test",
                confidence=80,
                status="closed",
                stop_loss=98000,
                take_profit=103000,
                max_drawdown=-0.5
            ),
            BacktestTrade(
                entry_time=datetime.now() - timedelta(hours=3),
                exit_time=datetime.now() - timedelta(hours=2),
                symbol="BTCUSDT",
                direction="short",
                entry_price=101000,
                exit_price=102000,
                quantity=0.01,
                pnl=-10,
                pnl_percentage=-1.0,
                recommendation_source="test",
                confidence=75,
                status="closed",
                stop_loss=103000,
                take_profit=99000,
                max_drawdown=-1.5
            )
        ]
        
        metrics = framework._calculate_metrics()
        
        # Verify calculations
        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == 0.5
        assert metrics.avg_win == 10
        assert metrics.avg_loss == 10
        assert metrics.total_pnl == 0
        assert metrics.profit_factor == 1.0
    
    @pytest.mark.asyncio
    async def test_comprehensive_backtest(self):
        """Test comprehensive backtest with all strategies"""
        framework = BacktestingFramework(initial_capital=10000)
        
        # Run with very short period for speed
        results = await framework.run_comprehensive_backtest(
            symbol="BTCUSDT",
            days_back=1
        )
        
        # Should have results for all strategies
        assert "Market Regime" in results
        assert "Pattern Recognition" in results
        assert "Combined" in results
        
        # Each result should have required fields
        for strategy, report in results.items():
            assert "metrics" in report
            assert "capital" in report
            assert "trade_details" in report
            
            metrics = report["metrics"]
            assert "strategy_score" in metrics
            assert 0 <= metrics["strategy_score"] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])