#!/usr/bin/env python3
"""
Execution Summary Module - Tracks comprehensive trade execution details
for both main and mirror accounts including orders, fills, and merge decisions
"""
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from decimal import Decimal
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)

class ExecutionSummary:
    """Tracks comprehensive execution details for dashboard display"""

    def __init__(self):
        self._executions: Dict[str, Dict[str, Any]] = {}
        self._merge_decisions: Dict[str, List[Dict[str, Any]]] = {}
        self._monitor_health: Dict[str, Dict[str, Any]] = {}
        self._order_history: List[Dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._max_history = 100
        self._max_executions = 50  # Keep last 50 executions

    async def record_execution(self, trade_id: str, execution_data: Dict[str, Any]):
        """Record a trade execution with all details"""
        async with self._lock:
            timestamp = time.time()

            # Clean old executions if needed
            if len(self._executions) >= self._max_executions:
                # Remove oldest executions
                sorted_keys = sorted(self._executions.keys(),
                                   key=lambda k: self._executions[k].get('timestamp', 0))
                for key in sorted_keys[:10]:  # Remove 10 oldest
                    del self._executions[key]

            self._executions[trade_id] = {
                'timestamp': timestamp,
                'datetime': datetime.now().isoformat(),
                'symbol': execution_data.get('symbol'),
                'side': execution_data.get('side'),
                'approach': execution_data.get('approach'),
                'leverage': execution_data.get('leverage'),
                'margin': execution_data.get('margin_amount'),
                'position_size': execution_data.get('position_size'),
                'entry_price': execution_data.get('entry_price'),

                # Main account execution
                'main_account': {
                    'orders_placed': execution_data.get('main_orders', []),
                    'fill_status': execution_data.get('main_fill_status', 'pending'),
                    'slippage': execution_data.get('main_slippage', 0),
                    'execution_time': execution_data.get('main_execution_time', 0),
                    'errors': execution_data.get('main_errors', [])
                },

                # Mirror account execution
                'mirror_account': {
                    'enabled': execution_data.get('mirror_enabled', False),
                    'orders_placed': execution_data.get('mirror_orders', []),
                    'fill_status': execution_data.get('mirror_fill_status', 'N/A'),
                    'slippage': execution_data.get('mirror_slippage', 0),
                    'execution_time': execution_data.get('mirror_execution_time', 0),
                    'sync_status': execution_data.get('mirror_sync_status', 'N/A'),
                    'errors': execution_data.get('mirror_errors', [])
                },

                # Position merge details
                'merge_info': {
                    'position_merged': execution_data.get('position_merged', False),
                    'merge_reason': execution_data.get('merge_reason', 'N/A'),
                    'existing_position': execution_data.get('existing_position'),
                    'new_position': execution_data.get('new_position'),
                    'merged_parameters': execution_data.get('merged_parameters', {})
                },

                # Order details
                'orders': {
                    'market_orders': execution_data.get('market_orders', []),
                    'limit_orders': execution_data.get('limit_orders', []),
                    'tp_orders': execution_data.get('tp_orders', []),
                    'sl_orders': execution_data.get('sl_orders', []),
                    'cancelled_orders': execution_data.get('cancelled_orders', [])
                },

                # Execution metrics
                'metrics': {
                    'total_orders': execution_data.get('total_orders', 0),
                    'successful_orders': execution_data.get('successful_orders', 0),
                    'failed_orders': execution_data.get('failed_orders', 0),
                    'avg_fill_time': execution_data.get('avg_fill_time', 0),
                    'risk_reward_ratio': execution_data.get('risk_reward_ratio', 0)
                }
            }

            # Add to order history
            self._add_to_history(trade_id, self._executions[trade_id])

    async def record_merge_decision(self, symbol: str, side: str, decision: Dict[str, Any]):
        """Record a position merge decision"""
        async with self._lock:
            key = f"{symbol}_{side}"
            if key not in self._merge_decisions:
                self._merge_decisions[key] = []

            merge_record = {
                'timestamp': time.time(),
                'datetime': datetime.now().isoformat(),
                'merged': decision.get('merged', False),
                'reason': decision.get('reason', 'Unknown'),
                'existing_size': decision.get('existing_size', 0),
                'new_size': decision.get('new_size', 0),
                'approach': decision.get('approach', 'unknown'),
                'parameters_changed': decision.get('parameters_changed', False),
                'sl_changed': decision.get('sl_changed', False),
                'tp_changed': decision.get('tp_changed', False),
                'details': decision.get('details', {})
            }

            self._merge_decisions[key].append(merge_record)

            # Keep only recent decisions
            if len(self._merge_decisions[key]) > 10:
                self._merge_decisions[key] = self._merge_decisions[key][-10:]

    async def update_monitor_health(self, monitor_id: str, health_data: Dict[str, Any]):
        """Update monitor health status"""
        async with self._lock:
            self._monitor_health[monitor_id] = {
                'last_update': time.time(),
                'symbol': health_data.get('symbol'),
                'approach': health_data.get('approach'),
                'account': health_data.get('account', 'primary'),
                'status': health_data.get('status', 'active'),
                'last_check': health_data.get('last_check'),
                'errors': health_data.get('errors', 0),
                'restarts': health_data.get('restarts', 0),
                'position_size': health_data.get('position_size'),
                'unrealized_pnl': health_data.get('unrealized_pnl'),
                'monitoring_mode': health_data.get('monitoring_mode')
            }

    def _add_to_history(self, trade_id: str, execution: Dict[str, Any]):
        """Add execution to history with size limit"""
        history_entry = {
            'trade_id': trade_id,
            'timestamp': execution['timestamp'],
            'symbol': execution['symbol'],
            'side': execution['side'],
            'approach': execution['approach'],
            'success': execution['metrics']['failed_orders'] == 0
        }

        self._order_history.append(history_entry)

        # Keep only recent history
        if len(self._order_history) > self._max_history:
            self._order_history = self._order_history[-self._max_history:]

    async def get_latest_executions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get latest trade executions"""
        async with self._lock:
            sorted_executions = sorted(
                self._executions.items(),
                key=lambda x: x[1]['timestamp'],
                reverse=True
            )
            return [exec_data for _, exec_data in sorted_executions[:limit]]

    async def get_monitor_summary(self) -> Dict[str, Any]:
        """Get summary of all monitors"""
        async with self._lock:
            active_monitors = {
                'primary': {'fast': 0, 'conservative': 0, 'ggshot': 0, 'total': 0},
                'mirror': {'fast': 0, 'conservative': 0, 'ggshot': 0, 'total': 0}
            }

            monitor_details = []
            current_time = time.time()

            for monitor_id, health in self._monitor_health.items():
                # Skip stale monitors (no update in 5 minutes)
                if current_time - health['last_update'] > 300:
                    continue

                account = health.get('account', 'primary')
                approach = health.get('approach', 'unknown')

                if approach in ['fast', 'conservative', 'ggshot']:
                    active_monitors[account][approach] += 1
                    active_monitors[account]['total'] += 1

                monitor_details.append({
                    'id': monitor_id,
                    'symbol': health.get('symbol'),
                    'approach': approach,
                    'account': account,
                    'status': health.get('status'),
                    'pnl': health.get('unrealized_pnl', 0),
                    'errors': health.get('errors', 0)
                })

            return {
                'counts': active_monitors,
                'details': sorted(monitor_details, key=lambda x: x['symbol'])
            }

    async def get_merge_history(self, symbol: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get merge decision history"""
        async with self._lock:
            if symbol:
                # Return history for specific symbol
                result = {}
                for key, decisions in self._merge_decisions.items():
                    if key.startswith(f"{symbol}_"):
                        result[key] = decisions
                return result
            else:
                # Return all merge history
                return dict(self._merge_decisions)

    async def get_execution_stats(self) -> Dict[str, Any]:
        """Get overall execution statistics"""
        async with self._lock:
            total_trades = len(self._executions)
            successful_trades = sum(
                1 for exec in self._executions.values()
                if exec['metrics']['failed_orders'] == 0
            )

            total_orders = sum(
                exec['metrics']['total_orders']
                for exec in self._executions.values()
            )

            successful_orders = sum(
                exec['metrics']['successful_orders']
                for exec in self._executions.values()
            )

            # Calculate average execution times
            main_exec_times = [
                exec['main_account']['execution_time']
                for exec in self._executions.values()
                if exec['main_account']['execution_time'] > 0
            ]

            mirror_exec_times = [
                exec['mirror_account']['execution_time']
                for exec in self._executions.values()
                if exec['mirror_account']['enabled'] and
                   exec['mirror_account']['execution_time'] > 0
            ]

            return {
                'total_trades': total_trades,
                'successful_trades': successful_trades,
                'success_rate': (successful_trades / total_trades * 100) if total_trades > 0 else 0,
                'total_orders': total_orders,
                'successful_orders': successful_orders,
                'order_success_rate': (successful_orders / total_orders * 100) if total_orders > 0 else 0,
                'avg_main_exec_time': sum(main_exec_times) / len(main_exec_times) if main_exec_times else 0,
                'avg_mirror_exec_time': sum(mirror_exec_times) / len(mirror_exec_times) if mirror_exec_times else 0,
                'total_merges': sum(
                    1 for exec in self._executions.values()
                    if exec['merge_info']['position_merged']
                ),
                'approaches': {
                    'fast': sum(1 for exec in self._executions.values() if exec['approach'] == 'fast'),
                    'conservative': sum(1 for exec in self._executions.values() if exec['approach'] == 'conservative'),
                    'ggshot': sum(1 for exec in self._executions.values() if exec['approach'] == 'ggshot')
                }
            }

    async def format_execution_details(self, trade_id: str) -> str:
        """Format execution details for display"""
        async with self._lock:
            if trade_id not in self._executions:
                return "❌ Execution details not found"

            exec_data = self._executions[trade_id]

            # Format the execution summary
            summary = f"""
📊 <b>EXECUTION DETAILS - {trade_id}</b>
{'═' * 40}

🎯 <b>Trade Info</b>
├ Symbol: {exec_data['symbol']} {exec_data['side']}
├ Approach: {exec_data['approach'].upper()}
├ Leverage: {exec_data['leverage']}x
├ Size: {exec_data['position_size']}
└ Margin: ${exec_data['margin']}

📍 <b>Main Account Execution</b>
├ Orders: {len(exec_data['main_account']['orders_placed'])}
├ Status: {exec_data['main_account']['fill_status']}
├ Slippage: {exec_data['main_account']['slippage']:.3f}%
├ Time: {exec_data['main_account']['execution_time']:.2f}s
"""

            if exec_data['main_account']['errors']:
                summary += f"└ ⚠️ Errors: {', '.join(exec_data['main_account']['errors'])}\n"
            else:
                summary += "└ ✅ No errors\n"

            # Mirror account section
            if exec_data['mirror_account']['enabled']:
                summary += f"""
🪞 <b>Mirror Account Execution</b>
├ Orders: {len(exec_data['mirror_account']['orders_placed'])}
├ Status: {exec_data['mirror_account']['fill_status']}
├ Sync: {exec_data['mirror_account']['sync_status']}
├ Time: {exec_data['mirror_account']['execution_time']:.2f}s
"""
                if exec_data['mirror_account']['errors']:
                    summary += f"└ ⚠️ Errors: {', '.join(exec_data['mirror_account']['errors'])}\n"
                else:
                    summary += "└ ✅ Synced successfully\n"

            # Merge information
            if exec_data['merge_info']['position_merged']:
                summary += f"""
🔄 <b>Position Merge</b>
├ Status: MERGED ✅
├ Reason: {exec_data['merge_info']['merge_reason']}
├ Previous: {exec_data['merge_info']['existing_position']}
└ New Total: {exec_data['merge_info']['new_position']}
"""

            # Order breakdown
            summary += f"""
📋 <b>Order Breakdown</b>
├ Market: {len(exec_data['orders']['market_orders'])}
├ Limit: {len(exec_data['orders']['limit_orders'])}
├ TP Orders: {len(exec_data['orders']['tp_orders'])}
├ SL Orders: {len(exec_data['orders']['sl_orders'])}
└ Cancelled: {len(exec_data['orders']['cancelled_orders'])}

📈 <b>Metrics</b>
├ Success Rate: {(exec_data['metrics']['successful_orders'] / exec_data['metrics']['total_orders'] * 100):.1f}%
├ Avg Fill Time: {exec_data['metrics']['avg_fill_time']:.2f}s
└ Risk/Reward: 1:{exec_data['metrics']['risk_reward_ratio']:.1f}
"""

            return summary

# Global instance
execution_summary = ExecutionSummary()

# Export for direct import
__all__ = ['ExecutionSummary', 'execution_summary']