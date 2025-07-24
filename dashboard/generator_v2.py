#!/usr/bin/env python3
"""
Enhanced modular dashboard generator with improved performance and design
"""
import logging
import asyncio
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from config.constants import *
from utils.formatters import format_number
from utils.cache import get_usdt_wallet_balance_cached, get_mirror_wallet_balance_cached
from utils.dashboard_cache import cached_component, dashboard_cache
from clients.bybit_helpers import get_positions_and_orders_batch, get_all_positions
from utils.request_batcher import get_dashboard_data_optimized

from dashboard.models import (
    AccountSummary, PnLAnalysis, PositionSummary,
    PerformanceMetrics, MarketStatus, DashboardData
)
from dashboard.components import DashboardComponents
from market_analysis.market_status_engine import market_status_engine
from dashboard.lazy_components import lazy_loader, load_market_status, load_ai_insights

logger = logging.getLogger(__name__)


class DashboardGenerator:
    """Enhanced dashboard generator with modular components"""

    def __init__(self):
        self.components = DashboardComponents()
        self._last_data_hash = None

    async def generate(self, chat_id: int, context: Any, force_refresh: bool = False) -> str:
        """Generate complete dashboard with all components"""
        try:
            # Fetch dashboard data
            dashboard_data = await self._fetch_dashboard_data(chat_id, context, force_refresh=force_refresh)

            # Check if data has changed significantly
            if not self._has_significant_change(dashboard_data):
                logger.debug("No significant dashboard changes, using cached version")
                cached = dashboard_cache.get(f"full_dashboard_{chat_id}")
                if cached:
                    return cached

            # Build dashboard sections
            sections = []

            # Header with timestamp
            timestamp = datetime.now().strftime('%H:%M:%S')
            auto_refresh = len(dashboard_data.positions) > 0
            sections.append(self.components.header(timestamp, auto_refresh))

            # Quick commands
            sections.append(self.components.quick_commands())
            sections.append(self.components.divider())

            # Account overview
            sections.append(self.components.account_comparison(
                dashboard_data.main_account,
                dashboard_data.mirror_account
            ))
            sections.append("")

            # P&L Analysis
            sections.append(self.components.pnl_analysis_table(
                dashboard_data.main_pnl,
                dashboard_data.mirror_pnl
            ))
            sections.append("")

            # Active positions
            sections.append(self.components.positions_summary(
                dashboard_data.positions,
                limit=3  # Show fewer positions on mobile
            ))
            sections.append("")

            # Performance metrics (collapsed by default)
            sections.append(self.components.performance_summary(
                dashboard_data.performance,
                expanded=False
            ))
            sections.append("")

            # Market status
            sections.append(self.components.market_status(
                dashboard_data.market_status
            ))
            sections.append("")

            # Monitor status
            sections.append(self.components.monitor_status(
                dashboard_data.active_monitors,
                dashboard_data.has_mirror
            ))
            sections.append("")

            # Quick actions grid
            sections.append(self.components.quick_actions_grid())

            # Join all sections
            dashboard_text = "\n".join(sections)

            # Cache the complete dashboard
            dashboard_cache.set(f"full_dashboard_{chat_id}", dashboard_text)

            return dashboard_text

        except Exception as e:
            logger.error(f"Error generating dashboard: {e}")
            return self._generate_error_dashboard(str(e))

    async def _fetch_dashboard_data(self, chat_id: int, context: Any, force_refresh: bool = False) -> DashboardData:
        """Fetch all dashboard data with caching"""
        chat_data = context.chat_data or {}
        bot_data = context.bot_data or {}

        # Fetch data in parallel for better performance
        tasks = [
            self._fetch_account_data(),
            self._fetch_positions_and_orders(),
            self._fetch_performance_stats(bot_data),
            self._fetch_market_status(chat_data, force_refresh=force_refresh),
            self._fetch_monitor_status(bot_data)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Unpack results
        account_data = results[0] if not isinstance(results[0], Exception) else self._default_account_data()
        positions_data = results[1] if not isinstance(results[1], Exception) else ([], [], [], [])
        performance = results[2] if not isinstance(results[2], Exception) else self._default_performance()
        market_status = results[3] if not isinstance(results[3], Exception) else MarketStatus()
        monitor_counts = results[4] if not isinstance(results[4], Exception) else {}

        # Process account data
        main_account, mirror_account = account_data

        # Process positions and calculate P&L
        # New format always returns 4 values
        main_positions, main_orders, mirror_positions, mirror_orders = positions_data

        # Process positions with account type tracking
        main_summaries = await self._process_positions(main_positions, account_type="main")
        mirror_summaries = await self._process_positions(mirror_positions, account_type="mirror") if mirror_positions else []
        position_summaries = main_summaries + mirror_summaries

        # Calculate P&L separately for each account
        main_pnl = await self._calculate_pnl_analysis_single(main_positions, main_orders)
        mirror_pnl = await self._calculate_pnl_analysis_single(mirror_positions, mirror_orders) if mirror_positions else None

        # Count active positions for each account
        active_main = [p for p in main_positions if float(p.get('size', 0)) > 0]
        active_mirror = [p for p in mirror_positions if float(p.get('size', 0)) > 0]

        # Calculate unrealized P&L for each account
        main_unrealized_pnl = sum(
            Decimal(str(p.get('unrealisedPnl', '0')))
            for p in active_main
        )
        mirror_unrealized_pnl = sum(
            Decimal(str(p.get('unrealisedPnl', '0')))
            for p in active_mirror
        )

        # Update main account with actual data
        main_account.position_count = len(active_main)
        main_account.order_count = len(main_orders)
        main_account.unrealized_pnl = main_unrealized_pnl

        # Update mirror account if available
        if mirror_account:
            mirror_account.position_count = len(active_mirror)
            mirror_account.order_count = len(mirror_orders)
            mirror_account.unrealized_pnl = mirror_unrealized_pnl

        return DashboardData(
            main_account=main_account,
            mirror_account=mirror_account,
            main_pnl=main_pnl,
            mirror_pnl=mirror_pnl,
            positions=position_summaries,
            performance=performance,
            market_status=market_status,
            active_monitors=monitor_counts,
            last_update=datetime.now()
        )

    @cached_component("account_data", ttl=30)
    async def _fetch_account_data(self) -> Tuple[AccountSummary, Optional[AccountSummary]]:
        """Fetch main and mirror account data"""
        # Main account
        try:
            wallet_info = await get_usdt_wallet_balance_cached()

            if isinstance(wallet_info, tuple) and len(wallet_info) >= 2:
                total_balance = Decimal(str(wallet_info[0]))
                available_balance = Decimal(str(wallet_info[1]))
            else:
                total_balance = Decimal("0")
                available_balance = Decimal("0")

            # Calculate health score
            margin_used = total_balance - available_balance
            balance_used_pct = float(margin_used / total_balance * 100) if total_balance > 0 else 0
            health_score = 100 - min(100, balance_used_pct)

            main_account = AccountSummary(
                balance=total_balance,
                available_balance=available_balance,
                margin_used=margin_used,
                unrealized_pnl=Decimal("0"),  # Will be updated with positions
                realized_pnl=Decimal("0"),
                position_count=0,
                order_count=0,
                health_score=health_score,
                account_type="main"
            )
        except Exception as e:
            logger.error(f"Error fetching main account data: {e}")
            main_account = self._default_account_summary("main")

        # Mirror account
        mirror_account = None
        try:
            from execution.mirror_trader import is_mirror_trading_enabled
            if is_mirror_trading_enabled():
                mirror_info = await get_mirror_wallet_balance_cached()

                if isinstance(mirror_info, tuple) and len(mirror_info) >= 2:
                    total_balance = Decimal(str(mirror_info[0]))
                    available_balance = Decimal(str(mirror_info[1]))
                else:
                    total_balance = Decimal("0")
                    available_balance = Decimal("0")

                margin_used = total_balance - available_balance
                balance_used_pct = float(margin_used / total_balance * 100) if total_balance > 0 else 0
                health_score = 100 - min(100, balance_used_pct)

                mirror_account = AccountSummary(
                    balance=total_balance,
                    available_balance=available_balance,
                    margin_used=margin_used,
                    unrealized_pnl=Decimal("0"),
                    realized_pnl=Decimal("0"),
                    position_count=0,
                    order_count=0,
                    health_score=health_score,
                    account_type="mirror"
                )
        except Exception as e:
            logger.debug(f"Mirror account not available: {e}")

        return main_account, mirror_account

    async def _fetch_positions_and_orders(self) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
        """Fetch positions and orders with caching"""
        try:
            # get_positions_and_orders_batch now returns 4 values
            main_positions, main_orders, mirror_positions, mirror_orders = await get_positions_and_orders_batch()
            return main_positions, main_orders, mirror_positions, mirror_orders
        except Exception as e:
            logger.error(f"Error fetching positions and orders: {e}")
            return [], [], [], []

    async def _process_positions(self, positions: List[Dict], account_type: str = "main") -> List[PositionSummary]:
        """Process raw positions into summary objects with account type tracking"""
        summaries = []

        for pos in positions:
            try:
                size = Decimal(str(pos.get('size', '0')))
                if size <= 0:
                    continue

                # Enhanced data validation
                try:
                    avg_price = Decimal(str(pos.get('avgPrice', '0')))
                    mark_price = Decimal(str(pos.get('markPrice', '0')))
                    unrealized_pnl = Decimal(str(pos.get('unrealisedPnl', '0')))
                    pnl_percentage = float(pos.get('unrealisedPnlPcnt', 0)) * 100
                    margin_used = Decimal(str(pos.get('positionIM', '0')))
                except (ValueError, TypeError, InvalidOperation) as e:
                    logger.warning(f"Invalid numeric data in position {pos.get('symbol', 'unknown')}: {e}")
                    continue

                summary = PositionSummary(
                    symbol=pos.get('symbol', ''),
                    side=pos.get('side', ''),
                    size=size,
                    avg_price=avg_price,
                    mark_price=mark_price,
                    unrealized_pnl=unrealized_pnl,
                    pnl_percentage=pnl_percentage,
                    margin_used=margin_used,
                    has_tp=False,  # Will be updated when processing orders
                    has_sl=False,  # Will be updated when processing orders
                    approach="unknown",
                    account_type=account_type  # Track source account
                )
                summaries.append(summary)
            except Exception as e:
                logger.error(f"Error processing position {pos}: {e}")
                continue

        # Sort by absolute P&L (largest first)
        summaries.sort(key=lambda x: abs(x.unrealized_pnl), reverse=True)

        return summaries

    async def _calculate_pnl_analysis_single(self, positions: List[Dict], orders: List[Dict]) -> PnLAnalysis:
        """Calculate P&L analysis for a single account with comprehensive validation"""

        tp1_profit = Decimal("0")
        tp1_full_profit = Decimal("0")
        all_tp_profit = Decimal("0")
        all_sl_loss = Decimal("0")

        try:
            # Group orders by symbol for efficiency
            orders_by_symbol = {}
            for order in orders:
                symbol = order.get('symbol', '')
                if symbol not in orders_by_symbol:
                    orders_by_symbol[symbol] = []
                orders_by_symbol[symbol].append(order)

            # Calculate P&L for each position
            for pos in positions:
                try:
                    # Enhanced data validation
                    size = Decimal(str(pos.get('size', '0')))
                    if size <= 0:
                        continue

                    symbol = pos.get('symbol', '')
                    side = pos.get('side', '')
                    avg_price = Decimal(str(pos.get('avgPrice', '0')))

                    # Validate critical data
                    if not symbol or not side or avg_price <= 0:
                        logger.warning(f"Invalid position data: symbol={symbol}, side={side}, avg_price={avg_price}")
                        continue

                except (ValueError, TypeError, InvalidOperation) as e:
                    logger.warning(f"Invalid numeric data in P&L calculation for position {pos.get('symbol', 'unknown')}: {e}")
                    continue

                # Get orders for this position
                pos_orders = orders_by_symbol.get(symbol, [])

                # Find TP and SL orders
                tp_orders = []
                sl_orders = []

                for order in pos_orders:
                    # Check if order is TP/SL based on OrderLinkId (for Enhanced TP/SL system)
                    order_link_id = order.get('orderLinkId', '')
                    is_enhanced_tp_sl = ('_TP' in order_link_id.upper() or
                                        'TP1' in order_link_id.upper() or
                                        'TP2' in order_link_id.upper() or
                                        'TP3' in order_link_id.upper() or
                                        'TP4' in order_link_id.upper() or
                                        '_SL' in order_link_id.upper() or
                                        'SL' in order_link_id.upper())

                    # Include orders that are either reduce_only OR Enhanced TP/SL orders
                    if not order.get('reduceOnly', False) and not is_enhanced_tp_sl:
                        continue

                    # Handle both stop orders (with triggerPrice) and limit orders (with price)
                    trigger_price_str = order.get('triggerPrice', '')
                    limit_price_str = order.get('price', '')
                    order_type = order.get('orderType', '').lower()

                    # Enhanced order price extraction with validation
                    price_to_use = 0
                    price_source = "unknown"

                    # Priority 1: Try triggerPrice (stop orders, Enhanced TP/SL SL orders)
                    if trigger_price_str and trigger_price_str != '':
                        try:
                            price_to_use = float(trigger_price_str)
                            price_source = "trigger"
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid triggerPrice for order {order.get('orderId', 'unknown')}: {trigger_price_str}")

                    # Priority 2: Try limit price (limit orders, Enhanced TP/SL TP orders)
                    if price_to_use == 0 and limit_price_str and limit_price_str != '':
                        try:
                            price_to_use = float(limit_price_str)
                            price_source = "limit"
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid price for order {order.get('orderId', 'unknown')}: {limit_price_str}")

                    # Validation: Skip orders without valid prices
                    if price_to_use == 0:
                        logger.warning(f"Skipping order {order.get('orderId', 'unknown')} - no valid price found")
                        continue

                    # Enhanced classification based on order type and price source
                    order_classification = {
                        'price': price_to_use,
                        'source': price_source,
                        'order_type': order_type,
                        'stop_order_type': order.get('stopOrderType', ''),
                        'order_link_id': order.get('orderLinkId', '')
                    }

                    # Enhanced TP/SL classification - same logic as comprehensive display
                    is_tp_order = False
                    is_sl_order = False

                    # Priority 1: Order Link ID detection (most reliable)
                    if ('_TP' in order_link_id.upper() or
                        'TP1' in order_link_id.upper() or
                        'TP2' in order_link_id.upper() or
                        'TP3' in order_link_id.upper() or
                        'TP4' in order_link_id.upper()):
                        is_tp_order = True
                    elif ('_SL' in order_link_id.upper() or
                          'SL' in order_link_id.upper()):
                        is_sl_order = True
                    # Priority 2: Stop order type
                    elif order.get('stopOrderType') == 'TakeProfit':
                        is_tp_order = True
                    elif order.get('stopOrderType') in ['StopLoss', 'Stop']:
                        is_sl_order = True
                    # Priority 3: Price-based classification
                    else:
                        if side == 'Buy':
                            if price_to_use > float(avg_price):
                                is_tp_order = True
                            else:
                                is_sl_order = True
                        else:  # Sell
                            if price_to_use < float(avg_price):
                                is_tp_order = True
                            else:
                                is_sl_order = True

                    # Add enhanced order info for debugging
                    order['_classification'] = order_classification
                    order['_is_tp'] = is_tp_order
                    order['_is_sl'] = is_sl_order

                    # Categorize the order
                    if is_tp_order:
                        tp_orders.append(order)
                    elif is_sl_order:
                        sl_orders.append(order)
                    else:
                        logger.warning(f"Order {order.get('orderId', 'unknown')} could not be classified as TP or SL")
                        # Still add to appropriate category based on price as fallback
                        if side == 'Buy':
                            if price_to_use > float(avg_price):
                                tp_orders.append(order)
                            else:
                                sl_orders.append(order)
                        else:
                            if price_to_use < float(avg_price):
                                tp_orders.append(order)
                            else:
                                sl_orders.append(order)

                # Sort TP orders by price (closest first)
                def safe_decimal_order_price(order):
                    """Get the order price as Decimal (triggerPrice for stops, price for limits)"""
                    trigger_price = order.get('triggerPrice', '')
                    limit_price = order.get('price', '')

                    if trigger_price and trigger_price != '':
                        try:
                            return Decimal(str(trigger_price))
                        except (ValueError, TypeError, InvalidOperation):
                            pass

                    if limit_price and limit_price != '':
                        try:
                            return Decimal(str(limit_price))
                        except (ValueError, TypeError, InvalidOperation):
                            pass

                    return Decimal('0')

                # Legacy float function for sorting (maintains backward compatibility)
                def safe_float_order_price(order):
                    """Get the order price as float for sorting purposes"""
                    decimal_price = safe_decimal_order_price(order)
                    return float(decimal_price) if decimal_price > 0 else 0

                if side == 'Buy':
                    tp_orders.sort(key=lambda x: safe_float_order_price(x))
                else:
                    tp_orders.sort(key=lambda x: safe_float_order_price(x), reverse=True)

                # Calculate TP1 profit (normalized for fair comparison between accounts)
                if tp_orders:
                    tp1_order = tp_orders[0]
                    tp1_price = safe_decimal_order_price(tp1_order)
                    tp1_qty = Decimal(str(tp1_order.get('qty', 0)))

                    if tp1_price > 0:  # Only calculate if valid price
                        # Calculate price difference per unit
                        if side == 'Buy':
                            price_diff_per_unit = tp1_price - avg_price
                        else:
                            price_diff_per_unit = avg_price - tp1_price

                        # For fair comparison: normalize TP1 to conservative approach standard (85% of position)
                        # This ensures both accounts show similar R:R ratios regardless of proportional sizing
                        conservative_tp1_percentage = Decimal('0.85')  # 85% is standard TP1 in conservative approach
                        normalized_tp1_qty = size * conservative_tp1_percentage

                        # Calculate profits using normalized quantities for fair comparison
                        tp1_profit += price_diff_per_unit * normalized_tp1_qty
                        tp1_full_profit += price_diff_per_unit * size

                # Calculate all TP profit (normalized for fair comparison between accounts)
                for tp_order in tp_orders:
                    tp_price = safe_decimal_order_price(tp_order)
                    tp_qty = Decimal(str(tp_order.get('qty', 0)))

                    if tp_price > 0:  # Only calculate if valid price
                        # Calculate price difference per unit
                        if side == 'Buy':
                            price_diff_per_unit = tp_price - avg_price
                        else:
                            price_diff_per_unit = avg_price - tp_price

                        # Use actual TP quantities but ensure fair comparison
                        # The normalization happens at the TP1 level, total TP should use actual quantities
                        all_tp_profit += price_diff_per_unit * tp_qty

                # Calculate SL loss (all variables as Decimal)
                if sl_orders:
                    sl_order = sl_orders[0]  # Should only be one SL
                    sl_price = safe_decimal_order_price(sl_order)

                    if sl_price > 0:  # Only calculate if valid price
                        if side == 'Buy':
                            all_sl_loss += abs((avg_price - sl_price) * size)
                        else:
                            all_sl_loss += abs((sl_price - avg_price) * size)

            # Calculate coverage with zero division protection
            try:
                tp1_coverage = float(tp1_profit / tp1_full_profit * 100) if tp1_full_profit > 0 else 0
            except (ZeroDivisionError, InvalidOperation):
                tp1_coverage = 0

            return PnLAnalysis(
                tp1_profit=tp1_profit,
                tp1_full_profit=tp1_full_profit,
                all_tp_profit=all_tp_profit,
                all_sl_loss=all_sl_loss,
                tp1_coverage=tp1_coverage
            )

        except Exception as e:
            logger.error(f"Error in P&L analysis calculation: {e}")
            # Return safe default values
            return PnLAnalysis(
                tp1_profit=Decimal("0"),
                tp1_full_profit=Decimal("0"),
                all_tp_profit=Decimal("0"),
                all_sl_loss=Decimal("0"),
                tp1_coverage=0.0
            )

    async def _fetch_performance_stats(self, bot_data: Dict) -> PerformanceMetrics:
        """Fetch performance statistics"""
        try:
            # Get stats from bot data
            total_trades = bot_data.get(STATS_TOTAL_TRADES, 0)
            wins = bot_data.get(STATS_TOTAL_WINS, 0)
            losses = bot_data.get(STATS_TOTAL_LOSSES, 0)
            total_pnl = Decimal(str(bot_data.get(STATS_TOTAL_PNL, 0)))

            # Calculate metrics with enhanced validation
            try:
                win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            except ZeroDivisionError:
                win_rate = 0

            try:
                avg_trade = total_pnl / Decimal(str(total_trades)) if total_trades > 0 else Decimal("0")
            except (ZeroDivisionError, InvalidOperation):
                avg_trade = Decimal("0")

            # Get additional stats with validation
            try:
                best_trade = Decimal(str(bot_data.get(STATS_BEST_TRADE, 0)))
                worst_trade = Decimal(str(bot_data.get(STATS_WORST_TRADE, 0)))
            except (ValueError, TypeError, InvalidOperation):
                best_trade = Decimal("0")
                worst_trade = Decimal("0")

            # Calculate profit factor with enhanced validation
            try:
                total_wins_pnl = Decimal(str(bot_data.get('stats_total_wins_pnl', 0)))
                total_losses_pnl = abs(Decimal(str(bot_data.get('stats_total_losses_pnl', 0))))

                if total_losses_pnl > 0:
                    profit_factor = float(total_wins_pnl / total_losses_pnl)
                elif total_wins_pnl > 0:
                    profit_factor = 999.99
                else:
                    profit_factor = 0.0
            except (ValueError, TypeError, InvalidOperation, ZeroDivisionError):
                profit_factor = 0.0

            # Calculate ratios (simplified)
            sharpe_ratio = self._calculate_sharpe_ratio(bot_data)
            sortino_ratio = sharpe_ratio * 1.3  # Simplified
            max_drawdown = float(bot_data.get('stats_max_drawdown', 5.2))

            # Recovery factor
            recovery_factor = float(total_pnl) / max_drawdown if max_drawdown > 0 and total_pnl > 0 else 0.0

            # Current streak
            win_streak = bot_data.get(STATS_WIN_STREAK, 0)
            loss_streak = bot_data.get(STATS_LOSS_STREAK, 0)
            if win_streak > 0:
                current_streak = ("win", win_streak)
            elif loss_streak > 0:
                current_streak = ("loss", loss_streak)
            else:
                current_streak = ("none", 0)

            return PerformanceMetrics(
                total_trades=total_trades,
                wins=wins,
                losses=losses,
                win_rate=win_rate,
                profit_factor=profit_factor,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=max_drawdown,
                recovery_factor=recovery_factor,
                best_trade=best_trade,
                worst_trade=worst_trade,
                avg_trade=avg_trade,
                current_streak=current_streak
            )
        except Exception as e:
            logger.error(f"Error fetching performance stats: {e}")
            return self._default_performance()

    async def _fetch_market_status(self, chat_data: Dict, force_refresh: bool = False) -> MarketStatus:
        """Fetch enhanced market status with real-time analysis"""
        try:
            if force_refresh:
                logger.info("🔄 Force refresh: Fetching fresh enhanced market status")
            else:
                logger.info("🔍 Fetching enhanced market status")

            # Get enhanced market status from the new engine
            enhanced_status = await market_status_engine.get_enhanced_market_status(
                symbol=chat_data.get('primary_symbol'),
                positions=chat_data.get('positions', []),
                chat_data=chat_data,
                force_refresh=force_refresh
            )

            # Convert EnhancedMarketStatus to MarketStatus model
            market_status = MarketStatus(
                primary_symbol=enhanced_status.symbol,
                timestamp=enhanced_status.timestamp,

                # Core metrics
                market_sentiment=enhanced_status.sentiment_label,
                sentiment_score=enhanced_status.sentiment_score,
                sentiment_emoji=enhanced_status.sentiment_emoji,

                volatility=enhanced_status.volatility_level,
                volatility_score=enhanced_status.volatility_score,
                volatility_percentage=getattr(enhanced_status, 'volatility_percentage', None),
                volatility_emoji=enhanced_status.volatility_emoji,

                trend=enhanced_status.trend_direction,
                trend_strength=enhanced_status.trend_strength,
                trend_emoji=enhanced_status.trend_emoji,

                momentum=enhanced_status.momentum_state,
                momentum_score=enhanced_status.momentum_score,
                momentum_emoji=enhanced_status.momentum_emoji,

                # Advanced analysis
                market_regime=enhanced_status.market_regime,
                regime_strength=enhanced_status.regime_strength,
                volume_strength=enhanced_status.volume_strength,

                # Price information
                current_price=enhanced_status.current_price,
                price_change_24h=enhanced_status.price_change_24h,
                price_change_pct_24h=enhanced_status.price_change_pct_24h,

                # NEW: Support and Resistance levels
                support_level=getattr(enhanced_status, 'support_level', None),
                resistance_level=getattr(enhanced_status, 'resistance_level', None),

                # NEW: Volume Profile
                volume_profile=getattr(enhanced_status, 'volume_profile', None),
                volume_ratio=getattr(enhanced_status, 'volume_ratio', None),

                # NEW: Market Structure
                market_structure=getattr(enhanced_status, 'market_structure', None),
                structure_bias=getattr(enhanced_status, 'structure_bias', None),

                # NEW: Funding and Open Interest
                funding_rate=getattr(enhanced_status, 'funding_rate', None),
                funding_bias=getattr(enhanced_status, 'funding_bias', None),
                open_interest_change_24h=getattr(enhanced_status, 'open_interest_change_24h', None),

                # NEW: AI Recommendation fields
                ai_recommendation=getattr(enhanced_status, 'ai_recommendation', None),
                ai_reasoning=getattr(enhanced_status, 'ai_reasoning', None),
                ai_risk_assessment=getattr(enhanced_status, 'ai_risk_assessment', None),
                ai_confidence=getattr(enhanced_status, 'ai_confidence', None),

                # Confidence and quality
                confidence=enhanced_status.confidence,
                data_quality=enhanced_status.data_quality,
                analysis_depth=enhanced_status.analysis_depth,

                # Key levels and metadata
                key_levels=enhanced_status.key_levels,
                data_sources=enhanced_status.data_sources,
                last_updated=enhanced_status.last_updated
            )

            logger.info(f"✅ Enhanced market status fetched - Confidence: {enhanced_status.confidence:.1f}%")
            return market_status

        except Exception as e:
            logger.error(f"❌ Error fetching enhanced market status: {e}")
            # Fallback to basic market status
            return self._get_fallback_market_status(chat_data)

    def _get_fallback_market_status(self, chat_data: Dict) -> MarketStatus:
        """Get basic market status when enhanced analysis fails"""
        try:
            # Simple sentiment calculation based on recent performance
            sentiment_score = 50.0  # Default neutral
            sentiment_emoji = "⚖️"
            market_sentiment = "Neutral"

            recent_pnl = chat_data.get('recent_pnl_trend', [])
            if recent_pnl:
                positive = sum(1 for pnl in recent_pnl if pnl > 0)
                sentiment_score = float(positive / len(recent_pnl) * 100)

                if sentiment_score >= 70:
                    sentiment_emoji = "🟢"
                    market_sentiment = "Bullish"
                elif sentiment_score >= 30:
                    sentiment_emoji = "⚖️"
                    market_sentiment = "Neutral"
                else:
                    sentiment_emoji = "🔴"
                    market_sentiment = "Bearish"

            return MarketStatus(
                primary_symbol=chat_data.get('primary_symbol'),
                timestamp=datetime.now(),
                market_sentiment=market_sentiment,
                sentiment_score=sentiment_score,
                sentiment_emoji=sentiment_emoji,
                volatility="Normal",
                trend="Ranging",
                momentum="Neutral",
                data_sources=["fallback"],
                last_updated=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error creating fallback market status: {e}")
            return MarketStatus(
                timestamp=datetime.now(),
                last_updated=datetime.now()
            )

    async def _fetch_monitor_status(self, bot_data: Dict) -> Dict[str, int]:
        """Fetch active monitor counts by account"""
        try:
            monitor_tasks = bot_data.get('monitor_tasks', {})

            counts = {
                'main': 0,
                'mirror': 0,
                'total': 0,
                # Conservative approach only
                'conservative': 0,
                'ggshot': 0
            }

            for monitor_key, monitor_data in monitor_tasks.items():
                if not monitor_data.get('active', False):
                    continue

                # Enhanced monitor key parsing with validation
                # Expected format: {chat_id}_{symbol}_{approach}_{account_type}
                try:
                    key_parts = monitor_key.split('_')
                    if len(key_parts) >= 4:
                        # Structured monitor key format
                        account_type = key_parts[-1].lower()  # Last part should be account type
                        if account_type in ['main', 'mirror']:
                            counts[account_type] += 1
                        else:
                            # Fallback to data inspection
                            if monitor_data.get('account_type') == 'mirror':
                                counts['mirror'] += 1
                            else:
                                counts['main'] += 1
                    else:
                        # Legacy format - use string matching as fallback
                        if 'mirror' in monitor_key.lower():
                            counts['mirror'] += 1
                        else:
                            counts['main'] += 1
                except Exception as e:
                    logger.warning(f"Error parsing monitor key '{monitor_key}': {e}")
                    # Safe fallback - assume main account
                    counts['main'] += 1

                # Enhanced approach counting with validation
                approach = monitor_data.get('approach', 'unknown').lower()
                if approach in counts:
                    counts[approach] += 1
                elif 'conservative' in approach:
                    counts['conservative'] += 1
                elif 'ggshot' in approach:
                    counts['ggshot'] += 1
                else:
                    logger.debug(f"Unknown approach '{approach}' for monitor {monitor_key}")

                counts['total'] += 1

            return counts
        except Exception as e:
            logger.error(f"Error fetching monitor status: {e}")
            return {}

    def _calculate_sharpe_ratio(self, stats_data: Dict) -> float:
        """Calculate simplified Sharpe ratio"""
        win_rate = float(stats_data.get('overall_win_rate', 0)) / 100
        total_wins_pnl = abs(float(stats_data.get('stats_total_wins_pnl', 0)))
        total_losses_pnl = abs(float(stats_data.get('stats_total_losses_pnl', 0)))

        if total_losses_pnl > 0:
            win_loss_ratio = total_wins_pnl / total_losses_pnl
        else:
            win_loss_ratio = 2.0 if total_wins_pnl > 0 else 0

        # Sharpe approximation
        if win_rate > 0.5 and win_loss_ratio > 1:
            return 1.0 + (win_rate - 0.5) * 2 + (win_loss_ratio - 1) * 0.5
        elif win_rate > 0.4:
            return 0.5 + win_rate
        else:
            return win_rate

    def _has_significant_change(self, data: DashboardData) -> bool:
        """Check if dashboard data has significant changes"""
        # Always update if positions exist (for real-time P&L)
        if data.total_positions > 0:
            return True

        # Check if data hash has changed
        current_hash = dashboard_cache._generate_hash({
            'balance': float(data.main_account.balance),
            'positions': data.total_positions,
            'total_pnl': float(data.main_account.total_pnl)
        })

        if current_hash != self._last_data_hash:
            self._last_data_hash = current_hash
            return True

        return False

    def _generate_error_dashboard(self, error: str) -> str:
        """Generate error dashboard"""
        return f"""<b>📈 TRADING DASHBOARD</b> • ERROR

⚠️ <b>Dashboard Generation Error</b>
└ {error}

Please try:
• <code>/start</code> - Restart bot
• <code>/help</code> - Get help
• Contact support if issue persists"""

    def _default_account_summary(self, account_type: str = "main") -> AccountSummary:
        """Default account summary when data unavailable"""
        return AccountSummary(
            balance=Decimal("0"),
            available_balance=Decimal("0"),
            margin_used=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            position_count=0,
            order_count=0,
            health_score=100.0,
            account_type=account_type
        )

    def _default_performance(self) -> PerformanceMetrics:
        """Default performance metrics"""
        return PerformanceMetrics(
            total_trades=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            profit_factor=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown=0.0,
            recovery_factor=0.0,
            best_trade=Decimal("0"),
            worst_trade=Decimal("0"),
            avg_trade=Decimal("0"),
            current_streak=("none", 0)
        )


# Global generator instance
dashboard_generator = DashboardGenerator()


async def build_mobile_dashboard_text(chat_id: int, context: Any, force_refresh: bool = False) -> str:
    """Build mobile-optimized dashboard text (compatibility wrapper)"""
    return await dashboard_generator.generate(chat_id, context, force_refresh=force_refresh)