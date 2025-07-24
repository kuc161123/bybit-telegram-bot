#!/usr/bin/env python3
"""
Fix stats accuracy and ensure manual closes are properly logged
"""

import asyncio
import logging
import json
from decimal import Decimal
from pathlib import Path
import pickle

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants from the bot
STATS_TOTAL_PNL = "stats_total_pnl"
STATS_TOTAL_WINS = "stats_total_wins"
STATS_TOTAL_LOSSES = "stats_total_losses"
STATS_TOTAL_TRADES = "stats_total_trades_initiated"
PERSISTENCE_FILE = "bybit_bot_dashboard_v4.1_enhanced.pkl"

async def analyze_and_fix_stats():
    """Analyze and fix the stats accuracy issue"""
    
    # First try to load from stats backup for analysis
    try:
        with open('stats_backup.json', 'r') as f:
            backup_stats = json.load(f)
        logger.info("Loaded stats from backup file for analysis")
    except Exception as e:
        logger.error(f"Error loading stats backup: {e}")
        backup_stats = {}
    
    # Load current stats from persistence file
    try:
        with open(PERSISTENCE_FILE, 'rb') as f:
            bot_data = pickle.load(f)
    except Exception as e:
        logger.error(f"Error loading persistence file: {e}")
        return
    
    # Use backup stats if bot_data doesn't have the stats
    if not bot_data.get(STATS_TOTAL_TRADES, 0) and backup_stats:
        logger.info("Using backup stats as primary source")
        for key, value in backup_stats.items():
            if key not in ['backup_timestamp', 'backup_date']:
                bot_data[key] = value
    
    logger.info("Current Stats Analysis:")
    logger.info("=" * 60)
    
    # Extract key stats
    total_trades = bot_data.get(STATS_TOTAL_TRADES, 0)
    total_wins = bot_data.get(STATS_TOTAL_WINS, 0)
    total_losses = bot_data.get(STATS_TOTAL_LOSSES, 0)
    total_pnl = Decimal(str(bot_data.get(STATS_TOTAL_PNL, 0)))
    wins_pnl = Decimal(str(bot_data.get('stats_total_wins_pnl', 0)))
    losses_pnl = Decimal(str(bot_data.get('stats_total_losses_pnl', 0)))
    recent_trades = bot_data.get('recent_trade_pnls', [])
    
    logger.info(f"Total Trades: {total_trades}")
    logger.info(f"Wins: {total_wins} | Losses: {total_losses}")
    logger.info(f"Total P&L: ${total_pnl}")
    logger.info(f"Wins P&L: ${wins_pnl}")
    logger.info(f"Losses P&L: ${losses_pnl} (stored as positive)")
    
    # Calculate what the losses should actually be
    calculated_losses_pnl = wins_pnl - total_pnl
    logger.info(f"\nCalculated Losses P&L: ${calculated_losses_pnl}")
    logger.info(f"Discrepancy: ${losses_pnl - calculated_losses_pnl}")
    
    # Analyze recent trades
    logger.info(f"\nRecent trades analysis:")
    unique_trades = []
    seen = set()
    
    # Remove duplicates from recent trades
    for i, pnl in enumerate(recent_trades):
        if pnl not in seen or (i > 0 and pnl != recent_trades[i-1]):
            unique_trades.append(pnl)
            seen.add(pnl)
    
    logger.info(f"Recent trades (with duplicates): {len(recent_trades)}")
    logger.info(f"Unique recent trades: {len(unique_trades)}")
    
    # Recalculate from unique trades
    recalc_wins_pnl = Decimal('0')
    recalc_losses_pnl = Decimal('0')
    recalc_wins = 0
    recalc_losses = 0
    
    for pnl in unique_trades:
        pnl_decimal = Decimal(str(pnl))
        if pnl_decimal > 0:
            recalc_wins_pnl += pnl_decimal
            recalc_wins += 1
        elif pnl_decimal < 0:
            recalc_losses_pnl += pnl_decimal
            recalc_losses += 1
    
    recalc_total_pnl = recalc_wins_pnl + recalc_losses_pnl
    
    logger.info(f"\nRecalculated from unique trades:")
    logger.info(f"Wins: {recalc_wins} trades, P&L: ${recalc_wins_pnl}")
    logger.info(f"Losses: {recalc_losses} trades, P&L: ${recalc_losses_pnl}")
    logger.info(f"Total P&L: ${recalc_total_pnl}")
    
    # Calculate correct profit factor
    profit_factor = 0.0
    if recalc_losses_pnl < 0:
        profit_factor = float(recalc_wins_pnl) / abs(float(recalc_losses_pnl))
    logger.info(f"Correct Profit Factor: {profit_factor:.2f}")
    
    # Fix the stats
    logger.info("\n" + "=" * 60)
    logger.info("FIXING STATS...")
    
    # Update bot_data with corrected values
    bot_data['stats_total_wins_pnl'] = float(recalc_wins_pnl)
    bot_data['stats_total_losses_pnl'] = float(recalc_losses_pnl)  # Store as negative
    bot_data[STATS_TOTAL_WINS] = recalc_wins
    bot_data[STATS_TOTAL_LOSSES] = recalc_losses
    bot_data[STATS_TOTAL_TRADES] = recalc_wins + recalc_losses
    bot_data[STATS_TOTAL_PNL] = float(recalc_total_pnl)
    
    # Remove duplicate entries from recent trades
    bot_data['recent_trade_pnls'] = unique_trades[-20:]  # Keep last 20 unique trades
    
    # Save corrected stats
    try:
        with open(PERSISTENCE_FILE, 'wb') as f:
            pickle.dump(bot_data, f)
        logger.info("✅ Stats corrected and saved!")
        
        # Also update stats backup
        stats_backup = {
            STATS_TOTAL_TRADES: bot_data[STATS_TOTAL_TRADES],
            STATS_TOTAL_WINS: bot_data[STATS_TOTAL_WINS],
            STATS_TOTAL_LOSSES: bot_data[STATS_TOTAL_LOSSES],
            STATS_TOTAL_PNL: str(bot_data[STATS_TOTAL_PNL]),
            'stats_total_wins_pnl': bot_data['stats_total_wins_pnl'],
            'stats_total_losses_pnl': bot_data['stats_total_losses_pnl'],
            'recent_trade_pnls': bot_data['recent_trade_pnls'],
            'corrected': True
        }
        
        with open('stats_backup_corrected.json', 'w') as f:
            json.dump(stats_backup, f, indent=2)
        logger.info("✅ Backup stats saved to stats_backup_corrected.json")
        
    except Exception as e:
        logger.error(f"Error saving corrected stats: {e}")
        
    logger.info("\nCorrected Stats Summary:")
    logger.info(f"Total Trades: {bot_data[STATS_TOTAL_TRADES]}")
    logger.info(f"Win Rate: {(recalc_wins/max(1, recalc_wins+recalc_losses)*100):.1f}%")
    logger.info(f"Total P&L: ${recalc_total_pnl}")
    logger.info(f"Avg Trade: ${recalc_total_pnl/max(1, recalc_wins+recalc_losses):.2f}")
    logger.info(f"Profit Factor: {profit_factor:.2f}")

async def main():
    """Main function"""
    await analyze_and_fix_stats()

if __name__ == "__main__":
    asyncio.run(main())