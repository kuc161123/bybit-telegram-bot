#!/usr/bin/env python3
"""
Check and analyze performance statistics in the pickle file
"""
import pickle
import json
from decimal import Decimal
from typing import Dict, Any

def check_performance_stats():
    """Check performance statistics in pickle file"""
    try:
        # Load pickle file
        pkl_path = 'bybit_bot_dashboard_v4.1_enhanced.pkl'
        with open(pkl_path, 'rb') as f:
            data = pickle.load(f)
        
        bot_data = data.get('bot_data', {})
        
        # Get all stats
        stats = {
            'TRADES': {
                'total_trades': bot_data.get('stats_total_trades_initiated', 0),
                'wins': bot_data.get('stats_total_wins', 0),
                'losses': bot_data.get('stats_total_losses', 0),
                'tp1_hits': bot_data.get('stats_tp1_hits', 0),
                'sl_hits': bot_data.get('stats_sl_hits', 0),
                'other_closures': bot_data.get('stats_other_closures', 0),
            },
            'P&L': {
                'total_pnl': float(bot_data.get('stats_total_pnl', 0)),
                'total_wins_pnl': float(bot_data.get('stats_total_wins_pnl', 0)),
                'total_losses_pnl': float(bot_data.get('stats_total_losses_pnl', 0)),
                'best_trade': float(bot_data.get('stats_best_trade', 0)),
                'worst_trade': float(bot_data.get('stats_worst_trade', 0)),
            },
            'STREAKS': {
                'win_streak': bot_data.get('stats_win_streak', 0),
                'loss_streak': bot_data.get('stats_loss_streak', 0),
                'max_win_streak': bot_data.get('stats_max_win_streak', 0),
                'max_loss_streak': bot_data.get('stats_max_loss_streak', 0),
            },
            'RISK': {
                'max_drawdown': float(bot_data.get('stats_max_drawdown', 0)),
                'peak_equity': float(bot_data.get('stats_peak_equity', 0)),
                'current_equity': float(bot_data.get('stats_current_equity', 0)),
            }
        }
        
        # Calculate derived metrics
        total_trades = stats['TRADES']['total_trades']
        wins = stats['TRADES']['wins']
        losses = stats['TRADES']['losses']
        
        # Win rate
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Profit factor
        wins_pnl = abs(stats['P&L']['total_wins_pnl'])
        losses_pnl = abs(stats['P&L']['total_losses_pnl'])
        
        if losses_pnl > 0:
            profit_factor = wins_pnl / losses_pnl
        elif wins_pnl > 0:
            profit_factor = 999.99
        else:
            profit_factor = 0
        
        # Sharpe ratio (simplified)
        if losses_pnl > 0:
            win_loss_ratio = wins_pnl / losses_pnl
        else:
            win_loss_ratio = 2.0 if wins_pnl > 0 else 0
            
        if win_rate > 50 and win_loss_ratio > 1:
            sharpe_ratio = 1.0 + (win_rate/100 - 0.5) * 2 + (win_loss_ratio - 1) * 0.5
        elif win_rate > 40:
            sharpe_ratio = 0.5 + win_rate/100
        else:
            sharpe_ratio = win_rate/100
        
        # Print results
        print("\n" + "="*60)
        print("PERFORMANCE STATISTICS ANALYSIS")
        print("="*60)
        
        print("\n📊 TRADE STATISTICS:")
        for key, value in stats['TRADES'].items():
            print(f"  {key:20s}: {value}")
        
        print("\n💰 P&L STATISTICS:")
        for key, value in stats['P&L'].items():
            print(f"  {key:20s}: ${value:,.2f}")
        
        print("\n🔥 STREAK STATISTICS:")
        for key, value in stats['STREAKS'].items():
            print(f"  {key:20s}: {value}")
        
        print("\n⚠️ RISK STATISTICS:")
        for key, value in stats['RISK'].items():
            print(f"  {key:20s}: ${value:,.2f}")
        
        print("\n📈 CALCULATED METRICS:")
        print(f"  Win Rate:            {win_rate:.1f}%")
        print(f"  Profit Factor:       {profit_factor:.2f}")
        print(f"  Sharpe Ratio:        {sharpe_ratio:.2f}")
        print(f"  Avg Win:             ${wins_pnl/wins:.2f}" if wins > 0 else "  Avg Win:             N/A")
        print(f"  Avg Loss:            ${losses_pnl/losses:.2f}" if losses > 0 else "  Avg Loss:            N/A")
        
        print("\n🔍 DATA QUALITY CHECK:")
        issues = []
        
        # Check for inconsistencies
        if total_trades != (wins + losses):
            issues.append(f"Trade count mismatch: {total_trades} != {wins} + {losses}")
        
        if wins > 0 and stats['P&L']['total_wins_pnl'] <= 0:
            issues.append(f"Wins exist but no winning P&L recorded")
        
        if losses > 0 and stats['P&L']['total_losses_pnl'] >= 0:
            issues.append(f"Losses exist but no losing P&L recorded")
        
        closure_sum = stats['TRADES']['tp1_hits'] + stats['TRADES']['sl_hits'] + stats['TRADES']['other_closures']
        if closure_sum != total_trades and total_trades > 0:
            issues.append(f"Closure reason mismatch: {closure_sum} != {total_trades}")
        
        if issues:
            print("  ⚠️ Issues found:")
            for issue in issues:
                print(f"    - {issue}")
        else:
            print("  ✅ All data quality checks passed")
        
        print("\n" + "="*60)
        
        # Show what the dashboard would display
        print("\nDASHBOARD DISPLAY PREVIEW:")
        print(f"Win Rate: {win_rate:.1f}% • PF: {profit_factor:.2f}")
        print(f"Sharpe: {sharpe_ratio:.2f} • DD: {stats['RISK']['max_drawdown']:.1f}%")
        
        return stats
        
    except FileNotFoundError:
        print("❌ Pickle file not found")
        return {}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {}

if __name__ == "__main__":
    check_performance_stats()