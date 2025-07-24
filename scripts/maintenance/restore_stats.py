#!/usr/bin/env python3
"""
Restore performance stats from trading bot logs
"""
import pickle
import logging
from decimal import Decimal
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def restore_stats():
    """Restore stats based on last known values from logs"""
    
    # Load persistence file
    persistence_file = "bybit_bot_dashboard_v4.1_enhanced.pkl"
    
    try:
        with open(persistence_file, 'rb') as f:
            data = pickle.load(f)
        logger.info("✅ Loaded persistence file")
    except Exception as e:
        logger.error(f"❌ Error loading persistence file: {e}")
        return
    
    # Get bot data
    bot_data = data.get('bot_data', {})
    
    # Restore stats from last known good values (from logs at 04:21 AM)
    # These values were logged when ALGOUSDT positions closed
    bot_data['stats_total_trades_initiated'] = 10
    bot_data['stats_total_wins'] = 10
    bot_data['stats_total_losses'] = 0
    bot_data['stats_total_pnl'] = Decimal("1677.470925558")
    bot_data['stats_tp1_hits'] = 0  # Not tracked in the logs
    bot_data['stats_sl_hits'] = 0  # No SL hits recorded
    bot_data['stats_other_closures'] = 10  # All were manual closes
    bot_data['stats_win_streak'] = 10
    bot_data['stats_loss_streak'] = 0
    bot_data['stats_best_trade'] = Decimal("403.89")  # From BTCUSDT trades
    bot_data['stats_worst_trade'] = Decimal("0")  # No losses
    bot_data['stats_conservative_trades'] = 5  # From logs
    bot_data['stats_fast_trades'] = 5  # From logs
    bot_data['stats_conservative_tp1_cancellations'] = 1
    bot_data['stats_total_wins_pnl'] = Decimal("1677.470925558")  # All wins
    bot_data['stats_total_losses_pnl'] = Decimal("0")  # No losses in recent history
    bot_data['stats_max_drawdown'] = Decimal("0")
    bot_data['stats_peak_equity'] = Decimal("1677.470925558")
    bot_data['stats_current_drawdown'] = Decimal("0")
    bot_data['recent_trade_pnls'] = [26.79, 26.79, 384.51, 384.51, 403.89, 403.89]  # Last 6 trades
    
    # Don't change the reset timestamp - keep it as is
    
    logger.info("📊 Restored stats:")
    logger.info(f"   Total Trades: {bot_data['stats_total_trades_initiated']}")
    logger.info(f"   Total Wins: {bot_data['stats_total_wins']}")
    logger.info(f"   Total Losses: {bot_data['stats_total_losses']}")
    logger.info(f"   Total P&L: {bot_data['stats_total_pnl']}")
    logger.info(f"   Win Rate: 100.0%")
    logger.info(f"   Conservative Trades: {bot_data['stats_conservative_trades']}")
    logger.info(f"   Fast Trades: {bot_data['stats_fast_trades']}")
    
    # Save updated persistence
    try:
        with open(persistence_file, 'wb') as f:
            pickle.dump(data, f)
        logger.info("✅ Successfully updated persistence file with restored stats")
    except Exception as e:
        logger.error(f"❌ Error saving persistence file: {e}")

if __name__ == "__main__":
    restore_stats()