#!/usr/bin/env python3
"""
Daily trading summary reports
"""
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from collections import defaultdict

from clients.bybit_helpers import get_all_positions
from utils.cache import get_usdt_wallet_balance_cached

logger = logging.getLogger(__name__)

class DailyReportGenerator:
    """Generates daily trading summary reports"""
    
    async def generate_report(self, chat_id: int) -> Optional[str]:
        """Generate daily report for user"""
        try:
            # Get current time and date range
            now = datetime.utcnow()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday_start = today_start - timedelta(days=1)
            
            # Gather data
            report_data = await self._gather_report_data(
                chat_id, yesterday_start, today_start
            )
            
            if not report_data:
                return None
            
            # Format report
            return self._format_report(report_data, yesterday_start)
            
        except Exception as e:
            logger.error(f"Error generating daily report for chat {chat_id}: {e}")
            return None
    
    async def _gather_report_data(self, chat_id: int, start_time: datetime, 
                                 end_time: datetime) -> Optional[Dict]:
        """Gather data for report"""
        try:
            data = {
                'chat_id': chat_id,
                'start_time': start_time,
                'end_time': end_time
            }
            
            # Get account balance
            total_balance, available_balance = await get_usdt_wallet_balance_cached()
            data['total_balance'] = total_balance
            data['available_balance'] = available_balance
            
            # Get current positions
            positions = await get_all_positions()
            data['open_positions'] = []
            data['total_unrealized_pnl'] = Decimal('0')
            
            for pos in positions:
                if float(pos.get('size', 0)) > 0:
                    unrealized_pnl = Decimal(str(pos.get('unrealisedPnl', 0)))
                    data['open_positions'].append({
                        'symbol': pos.get('symbol'),
                        'side': pos.get('side'),
                        'size': pos.get('size'),
                        'unrealized_pnl': unrealized_pnl,
                        'leverage': pos.get('leverage')
                    })
                    data['total_unrealized_pnl'] += unrealized_pnl
            
            # Get realized P&L for the period
            realized_pnl_data = await self._get_period_realized_pnl(
                start_time, end_time
            )
            data.update(realized_pnl_data)
            
            # Get active monitors count (placeholder for now)
            # TODO: Implement actual monitor counting
            data['active_monitors'] = 0
            
            return data
            
        except Exception as e:
            logger.error(f"Error gathering report data: {e}")
            return None
    
    async def _get_period_realized_pnl(self, start_time: datetime, 
                                      end_time: datetime) -> Dict:
        """Get realized P&L for time period"""
        try:
            # For now, return placeholder data
            # TODO: Implement get_realized_pnl_history in bybit_helpers
            pnl_history = []
            
            if not pnl_history:
                return {
                    'trades_count': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'total_realized_pnl': Decimal('0'),
                    'best_trade': None,
                    'worst_trade': None,
                    'symbols_traded': set()
                }
            
            # Filter by time period
            period_trades = []
            for trade in pnl_history:
                trade_time = datetime.fromtimestamp(
                    int(trade.get('createdTime', 0)) / 1000
                )
                if start_time <= trade_time < end_time:
                    period_trades.append(trade)
            
            # Analyze trades
            winning_trades = 0
            losing_trades = 0
            total_pnl = Decimal('0')
            best_trade = None
            worst_trade = None
            symbols_traded = set()
            
            for trade in period_trades:
                pnl = Decimal(str(trade.get('closedPnl', 0)))
                symbol = trade.get('symbol')
                
                total_pnl += pnl
                if symbol:
                    symbols_traded.add(symbol)
                
                if pnl > 0:
                    winning_trades += 1
                    if not best_trade or pnl > Decimal(str(best_trade.get('closedPnl', 0))):
                        best_trade = trade
                elif pnl < 0:
                    losing_trades += 1
                    if not worst_trade or pnl < Decimal(str(worst_trade.get('closedPnl', 0))):
                        worst_trade = trade
            
            return {
                'trades_count': len(period_trades),
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'total_realized_pnl': total_pnl,
                'best_trade': best_trade,
                'worst_trade': worst_trade,
                'symbols_traded': symbols_traded
            }
            
        except Exception as e:
            logger.error(f"Error getting period P&L: {e}")
            return {
                'trades_count': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_realized_pnl': Decimal('0'),
                'best_trade': None,
                'worst_trade': None,
                'symbols_traded': set()
            }
    
    def _format_report(self, data: Dict, report_date: datetime) -> str:
        """Format the daily report"""
        # Header
        report = f"""
📊 <b>DAILY TRADING REPORT</b>
📅 {report_date.strftime('%B %d, %Y')}
━━━━━━━━━━━━━━━━━━

💰 <b>ACCOUNT SUMMARY</b>
• Total Balance: ${data['total_balance']:,.2f}
• Available: ${data['available_balance']:,.2f}
• Active Positions: {len(data['open_positions'])}
• Active Monitors: {data['active_monitors']}
"""
        
        # Trading Performance
        if data['trades_count'] > 0:
            win_rate = (data['winning_trades'] / data['trades_count']) * 100
            
            report += f"""
📈 <b>TRADING PERFORMANCE</b>
• Total Trades: {data['trades_count']}
• Winning Trades: {data['winning_trades']} ({win_rate:.1f}%)
• Losing Trades: {data['losing_trades']}
• Realized P&L: ${data['total_realized_pnl']:+,.2f}
"""
            
            # Best/Worst trades
            if data['best_trade']:
                best_pnl = Decimal(str(data['best_trade'].get('closedPnl', 0)))
                best_symbol = data['best_trade'].get('symbol', 'Unknown')
                report += f"• Best Trade: {best_symbol} ${best_pnl:+,.2f}\n"
            
            if data['worst_trade']:
                worst_pnl = Decimal(str(data['worst_trade'].get('closedPnl', 0)))
                worst_symbol = data['worst_trade'].get('symbol', 'Unknown')
                report += f"• Worst Trade: {worst_symbol} ${worst_pnl:+,.2f}\n"
            
            # Symbols traded
            if data['symbols_traded']:
                report += f"• Symbols Traded: {', '.join(sorted(data['symbols_traded']))}\n"
        else:
            report += """
📈 <b>TRADING PERFORMANCE</b>
• No trades executed today
"""
        
        # Open Positions
        if data['open_positions']:
            report += f"""
📊 <b>OPEN POSITIONS</b>
• Count: {len(data['open_positions'])}
• Unrealized P&L: ${data['total_unrealized_pnl']:+,.2f}
"""
            
            # Top 3 positions by size
            positions_by_pnl = sorted(
                data['open_positions'], 
                key=lambda x: abs(x['unrealized_pnl']), 
                reverse=True
            )[:3]
            
            for pos in positions_by_pnl:
                side_emoji = "📈" if pos['side'] == 'Buy' else "📉"
                report += f"• {pos['symbol']} {side_emoji} ${pos['unrealized_pnl']:+,.2f}\n"
        
        # Daily P&L Summary
        total_daily_pnl = data['total_realized_pnl'] + data['total_unrealized_pnl']
        pnl_emoji = "🟢" if total_daily_pnl >= 0 else "🔴"
        
        report += f"""
━━━━━━━━━━━━━━━━━━
{pnl_emoji} <b>TOTAL P&L: ${total_daily_pnl:+,.2f}</b>
"""
        
        # Trading tips based on performance
        if data['trades_count'] > 0:
            if win_rate < 40:
                report += "\n💡 Tip: Consider reviewing your entry criteria"
            elif win_rate > 70:
                report += "\n💡 Great win rate! Keep up the good work"
            
            if data['losing_trades'] > data['winning_trades'] * 2:
                report += "\n💡 Tip: Focus on risk management"
        
        return report.strip()