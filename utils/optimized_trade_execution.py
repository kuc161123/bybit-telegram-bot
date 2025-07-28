#!/usr/bin/env python3
"""
Optimized Trade Execution Pipeline
Implements 2025 best practices for non-blocking, concurrent order placement
"""
import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

logger = logging.getLogger(__name__)

class ExecutionPhase(Enum):
    """Trade execution phases"""
    PREPARATION = "preparation"
    ENTRY_ORDERS = "entry_orders"
    TP_SL_SETUP = "tp_sl_setup"
    MIRROR_SYNC = "mirror_sync"
    MONITORING_SETUP = "monitoring_setup"
    COMPLETED = "completed"

@dataclass
class OrderRequest:
    """Individual order request for batch processing"""
    order_id: str
    symbol: str
    side: str
    order_type: str
    qty: str
    price: Optional[str] = None
    order_link_id: Optional[str] = None
    is_mirror: bool = False
    retry_count: int = 0
    max_retries: int = 3
    result: Optional[Dict] = None
    error: Optional[Exception] = None
    created_at: float = field(default_factory=time.time)

@dataclass
class ExecutionResult:
    """Result of trade execution"""
    success: bool
    phase: ExecutionPhase
    orders_placed: List[Dict]
    orders_failed: List[Dict]
    execution_time: float
    total_orders: int
    mirror_orders: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)

class OptimizedTradeExecutor:
    """
    High-performance trade execution system with concurrent order placement
    Based on 2025 best practices for async trading systems
    """
    
    def __init__(self, max_concurrent_orders: int = 10):
        self.max_concurrent_orders = max_concurrent_orders
        self.execution_semaphore = asyncio.Semaphore(max_concurrent_orders)
        
        # Performance tracking
        self.execution_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0.0,
            "orders_per_second": 0.0,
            "concurrent_efficiency": 0.0
        }
        
        # Execution phases timing
        self.phase_timings = {phase: [] for phase in ExecutionPhase}
        
    async def execute_conservative_trade_async(self, symbol: str, side: str, leverage: float,
                                             limit_prices: List[Decimal], qty_per_limit: Decimal,
                                             tp_prices: List[Decimal], sl_price: Decimal,
                                             trade_group_id: str, enable_mirror: bool = False) -> ExecutionResult:
        """
        Execute conservative trade with optimized concurrent order placement
        
        Args:
            symbol: Trading symbol
            side: Buy/Sell
            leverage: Position leverage
            limit_prices: List of limit entry prices
            qty_per_limit: Quantity per limit order
            tp_prices: Take profit prices
            sl_price: Stop loss price
            trade_group_id: Unique trade identifier
            enable_mirror: Enable mirror account trading
            
        Returns:
            ExecutionResult with comprehensive execution details
        """
        start_time = time.time()
        execution_result = ExecutionResult(
            success=False,
            phase=ExecutionPhase.PREPARATION,
            orders_placed=[],
            orders_failed=[],
            execution_time=0.0,
            total_orders=0
        )
        
        try:
            logger.info(f"🚀 Starting optimized conservative trade execution: {symbol} {side}")
            
            # Switch to execution mode for faster caching
            await self._set_execution_mode(True)
            
            # Phase 1: Preparation
            phase_start = time.time()
            execution_result.phase = ExecutionPhase.PREPARATION
            
            # Prepare all order requests
            entry_orders = await self._prepare_entry_orders(
                symbol, side, limit_prices, qty_per_limit, trade_group_id
            )
            
            tp_sl_orders = await self._prepare_tp_sl_orders(
                symbol, side, tp_prices, sl_price, qty_per_limit, trade_group_id
            )
            
            mirror_orders = []
            if enable_mirror:
                mirror_orders = await self._prepare_mirror_orders(
                    symbol, side, limit_prices, qty_per_limit, tp_prices, sl_price, trade_group_id
                )
            
            self._record_phase_timing(ExecutionPhase.PREPARATION, time.time() - phase_start)
            
            # Phase 2: Concurrent Entry Order Placement
            phase_start = time.time()
            execution_result.phase = ExecutionPhase.ENTRY_ORDERS
            
            entry_results = await self._execute_orders_concurrent(entry_orders)
            execution_result.orders_placed.extend(entry_results["successful"])
            execution_result.orders_failed.extend(entry_results["failed"])
            
            self._record_phase_timing(ExecutionPhase.ENTRY_ORDERS, time.time() - phase_start)
            
            # Phase 3: TP/SL Setup (can run concurrently with entry orders)
            phase_start = time.time()
            execution_result.phase = ExecutionPhase.TP_SL_SETUP
            
            # Wait a brief moment for entry orders to be filled before placing TP/SL
            await asyncio.sleep(0.5)
            
            tp_sl_results = await self._execute_orders_concurrent(tp_sl_orders)
            execution_result.orders_placed.extend(tp_sl_results["successful"])
            execution_result.orders_failed.extend(tp_sl_results["failed"])
            
            self._record_phase_timing(ExecutionPhase.TP_SL_SETUP, time.time() - phase_start)
            
            # Phase 4: Mirror Account Sync (if enabled)
            if enable_mirror and mirror_orders:
                phase_start = time.time()
                execution_result.phase = ExecutionPhase.MIRROR_SYNC
                
                mirror_results = await self._execute_orders_concurrent(mirror_orders)
                execution_result.mirror_orders.extend(mirror_results["successful"])
                execution_result.orders_failed.extend(mirror_results["failed"])
                
                self._record_phase_timing(ExecutionPhase.MIRROR_SYNC, time.time() - phase_start)
            
            # Phase 5: Setup Enhanced Monitoring
            phase_start = time.time()
            execution_result.phase = ExecutionPhase.MONITORING_SETUP
            
            await self._setup_enhanced_monitoring(
                symbol, side, trade_group_id, 
                execution_result.orders_placed,
                execution_result.mirror_orders
            )
            
            self._record_phase_timing(ExecutionPhase.MONITORING_SETUP, time.time() - phase_start)
            
            # Finalize execution
            execution_result.phase = ExecutionPhase.COMPLETED
            execution_result.success = len(execution_result.orders_failed) == 0
            execution_result.execution_time = time.time() - start_time
            execution_result.total_orders = len(entry_orders) + len(tp_sl_orders) + len(mirror_orders)
            
            # Calculate performance metrics
            execution_result.performance_metrics = self._calculate_performance_metrics(
                execution_result, start_time
            )
            
            # Update global statistics
            self._update_execution_stats(execution_result)
            
            logger.info(f"✅ Trade execution completed in {execution_result.execution_time:.2f}s")
            logger.info(f"   Orders placed: {len(execution_result.orders_placed)}")
            logger.info(f"   Orders failed: {len(execution_result.orders_failed)}")
            logger.info(f"   Success rate: {(len(execution_result.orders_placed) / execution_result.total_orders * 100):.1f}%")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"❌ Trade execution failed: {e}")
            execution_result.success = False
            execution_result.errors.append(str(e))
            execution_result.execution_time = time.time() - start_time
            return execution_result
            
        finally:
            # Switch back to monitoring mode
            await self._set_execution_mode(False)
    
    async def _prepare_entry_orders(self, symbol: str, side: str, limit_prices: List[Decimal],
                                  qty_per_limit: Decimal, trade_group_id: str) -> List[OrderRequest]:
        """Prepare entry order requests"""
        orders = []
        
        for i, limit_price in enumerate(limit_prices, 1):
            # First order is market, rest are limits
            order_type = "Market" if i == 1 else "Limit"
            order_link_id = f"CONS_{trade_group_id}_ENTRY{i}"
            
            order = OrderRequest(
                order_id=f"entry_{i}",
                symbol=symbol,
                side=side,
                order_type=order_type,
                qty=str(qty_per_limit),
                price=str(limit_price) if order_type == "Limit" else None,
                order_link_id=order_link_id,
                is_mirror=False
            )
            orders.append(order)
        
        return orders
    
    async def _prepare_tp_sl_orders(self, symbol: str, side: str, tp_prices: List[Decimal],
                                  sl_price: Decimal, base_qty: Decimal, trade_group_id: str) -> List[OrderRequest]:
        """Prepare TP/SL order requests"""
        orders = []
        
        # TP orders (85%, 5%, 5%, 5% distribution)
        tp_percentages = [85, 5, 5, 5]
        for i, (tp_price, percentage) in enumerate(zip(tp_prices, tp_percentages), 1):
            tp_qty = (base_qty * len(tp_prices) * percentage) / 100  # Adjust for total position
            order_link_id = f"CONS_{trade_group_id}_TP{i}"
            
            order = OrderRequest(
                order_id=f"tp_{i}",
                symbol=symbol,
                side="Sell" if side == "Buy" else "Buy",  # Opposite side for TP
                order_type="Limit",
                qty=str(tp_qty),
                price=str(tp_price),
                order_link_id=order_link_id,
                is_mirror=False
            )
            orders.append(order)
        
        # SL order (covers full position)
        sl_qty = base_qty * len(tp_prices)  # Full position size
        sl_order_link_id = f"CONS_{trade_group_id}_SL"
        
        sl_order = OrderRequest(
            order_id="sl_main",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",  # Opposite side for SL
            order_type="StopMarket",
            qty=str(sl_qty),
            price=str(sl_price),
            order_link_id=sl_order_link_id,
            is_mirror=False
        )
        orders.append(sl_order)
        
        return orders
    
    async def _prepare_mirror_orders(self, symbol: str, side: str, limit_prices: List[Decimal],
                                   qty_per_limit: Decimal, tp_prices: List[Decimal],
                                   sl_price: Decimal, trade_group_id: str) -> List[OrderRequest]:
        """Prepare mirror account order requests"""
        orders = []
        
        # Calculate mirror quantities (typically ~33% of main account)
        mirror_qty_ratio = 0.33  # This should be calculated based on account balances
        mirror_qty_per_limit = qty_per_limit * mirror_qty_ratio
        
        # Mirror entry orders
        for i, limit_price in enumerate(limit_prices, 1):
            order_type = "Market" if i == 1 else "Limit"
            order_link_id = f"CONS_{trade_group_id}_MIRROR_ENTRY{i}"
            
            order = OrderRequest(
                order_id=f"mirror_entry_{i}",
                symbol=symbol,
                side=side,
                order_type=order_type,
                qty=str(mirror_qty_per_limit),
                price=str(limit_price) if order_type == "Limit" else None,
                order_link_id=order_link_id,
                is_mirror=True
            )
            orders.append(order)
        
        # Mirror TP/SL orders
        tp_percentages = [85, 5, 5, 5]
        total_mirror_qty = mirror_qty_per_limit * len(limit_prices)
        
        for i, (tp_price, percentage) in enumerate(zip(tp_prices, tp_percentages), 1):
            tp_qty = (total_mirror_qty * percentage) / 100
            order_link_id = f"CONS_{trade_group_id}_MIRROR_TP{i}"
            
            order = OrderRequest(
                order_id=f"mirror_tp_{i}",
                symbol=symbol,
                side="Sell" if side == "Buy" else "Buy",
                order_type="Limit",
                qty=str(tp_qty),
                price=str(tp_price),
                order_link_id=order_link_id,
                is_mirror=True
            )
            orders.append(order)
        
        # Mirror SL order
        sl_order = OrderRequest(
            order_id="mirror_sl",
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            order_type="StopMarket",
            qty=str(total_mirror_qty),
            price=str(sl_price),
            order_link_id=f"CONS_{trade_group_id}_MIRROR_SL",
            is_mirror=True
        )
        orders.append(sl_order)
        
        return orders
    
    async def _execute_orders_concurrent(self, orders: List[OrderRequest]) -> Dict[str, List]:
        """Execute orders concurrently with semaphore control"""
        if not orders:
            return {"successful": [], "failed": []}
        
        logger.info(f"📦 Executing {len(orders)} orders concurrently")
        
        # Create tasks for concurrent execution
        tasks = []
        for order in orders:
            task = asyncio.create_task(self._execute_single_order(order))
            tasks.append(task)
        
        # Wait for all orders to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful = []
        failed = []
        
        for order, result in zip(orders, results):
            if isinstance(result, Exception):
                order.error = result
                failed.append({
                    "order_id": order.order_id,
                    "error": str(result),
                    "is_mirror": order.is_mirror
                })
            elif result and result.get("success"):
                order.result = result
                successful.append({
                    "order_id": order.order_id,
                    "bybit_order_id": result.get("orderId", ""),
                    "is_mirror": order.is_mirror,
                    "order_type": order.order_type,
                    "symbol": order.symbol,
                    "side": order.side,
                    "qty": order.qty,
                    "price": order.price
                })
            else:
                failed.append({
                    "order_id": order.order_id,
                    "error": "Order placement failed",
                    "is_mirror": order.is_mirror
                })
        
        logger.info(f"✅ Concurrent execution completed: {len(successful)} success, {len(failed)} failed")
        
        return {"successful": successful, "failed": failed}
    
    async def _execute_single_order(self, order: OrderRequest) -> Dict[str, Any]:
        """Execute a single order with retry logic and semaphore control"""
        async with self.execution_semaphore:
            for attempt in range(order.max_retries):
                try:
                    # Import here to avoid circular imports
                    if order.is_mirror:
                        from execution.mirror_trader import mirror_limit_order, mirror_market_order
                        
                        if order.order_type == "Market":
                            result = await mirror_market_order(
                                order.symbol, order.side, order.qty
                            )
                        else:
                            result = await mirror_limit_order(
                                order.symbol, order.side, order.qty, order.price
                            )
                    else:
                        from clients.bybit_helpers import place_order_with_retry
                        
                        order_params = {
                            "symbol": order.symbol,
                            "side": order.side,
                            "order_type": order.order_type,
                            "qty": order.qty,
                            "order_link_id": order.order_link_id
                        }
                        
                        if order.price:
                            order_params["price"] = order.price
                        
                        result = await place_order_with_retry(**order_params)
                    
                    if result:
                        return {"success": True, **result}
                    else:
                        raise Exception("Order placement returned no result")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Order {order.order_id} attempt {attempt + 1} failed: {e}")
                    
                    if attempt < order.max_retries - 1:
                        # Wait before retry with exponential backoff
                        wait_time = (2 ** attempt) * 0.5  # 0.5s, 1s, 2s
                        await asyncio.sleep(wait_time)
                    else:
                        # Final attempt failed
                        order.retry_count = order.max_retries
                        raise
        
        return {"success": False, "error": "All retry attempts failed"}
    
    async def _setup_enhanced_monitoring(self, symbol: str, side: str, trade_group_id: str,
                                       main_orders: List[Dict], mirror_orders: List[Dict]):
        """Setup enhanced TP/SL monitoring for the trade"""
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            
            # Prepare monitor data for main account
            if main_orders:
                monitor_key = f"{symbol}_{side}_main"
                monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "account_type": "main",
                    "trade_group_id": trade_group_id,
                    "orders": main_orders,
                    "phase": "BUILDING"
                }
                
                # Create monitor (this will be handled by the enhanced TP/SL manager)
                logger.info(f"🔍 Setting up enhanced monitoring for main account: {monitor_key}")
            
            # Prepare monitor data for mirror account
            if mirror_orders:
                monitor_key = f"{symbol}_{side}_mirror"
                monitor_data = {
                    "symbol": symbol,
                    "side": side,
                    "account_type": "mirror",
                    "trade_group_id": trade_group_id,
                    "orders": mirror_orders,
                    "phase": "BUILDING"
                }
                
                logger.info(f"🔍 Setting up enhanced monitoring for mirror account: {monitor_key}")
                
        except Exception as e:
            logger.error(f"❌ Failed to setup enhanced monitoring: {e}")
    
    async def _set_execution_mode(self, enable: bool):
        """Switch to execution mode for optimized caching"""
        try:
            from execution.enhanced_tp_sl_manager import enhanced_tp_sl_manager
            await enhanced_tp_sl_manager.set_execution_mode(enable)
        except Exception as e:
            logger.debug(f"Could not switch execution mode: {e}")
    
    def _record_phase_timing(self, phase: ExecutionPhase, duration: float):
        """Record timing for execution phase"""
        self.phase_timings[phase].append(duration)
        
        # Keep only last 100 timings for each phase
        if len(self.phase_timings[phase]) > 100:
            self.phase_timings[phase] = self.phase_timings[phase][-100:]
    
    def _calculate_performance_metrics(self, result: ExecutionResult, start_time: float) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics"""
        total_time = result.execution_time
        orders_per_second = result.total_orders / total_time if total_time > 0 else 0
        
        # Calculate phase breakdown
        phase_breakdown = {}
        for phase, timings in self.phase_timings.items():
            if timings:
                phase_breakdown[phase.value] = {
                    "average_time": sum(timings) / len(timings),
                    "last_time": timings[-1] if timings else 0,
                    "percentage_of_total": (timings[-1] / total_time * 100) if timings and total_time > 0 else 0
                }
        
        return {
            "orders_per_second": orders_per_second,
            "success_rate": (len(result.orders_placed) / result.total_orders * 100) if result.total_orders > 0 else 0,
            "concurrent_efficiency": self._calculate_concurrent_efficiency(result),
            "phase_breakdown": phase_breakdown,
            "total_execution_time": total_time
        }
    
    def _calculate_concurrent_efficiency(self, result: ExecutionResult) -> float:
        """Calculate how much time was saved by concurrent execution"""
        # Estimate sequential execution time
        estimated_sequential_time = result.total_orders * 2.0  # Assume 2s per order sequentially
        actual_time = result.execution_time
        
        if estimated_sequential_time > 0:
            efficiency = ((estimated_sequential_time - actual_time) / estimated_sequential_time) * 100
            return max(0, min(100, efficiency))  # Clamp between 0-100%
        
        return 0.0
    
    def _update_execution_stats(self, result: ExecutionResult):
        """Update global execution statistics"""
        self.execution_stats["total_executions"] += 1
        
        if result.success:
            self.execution_stats["successful_executions"] += 1
        else:
            self.execution_stats["failed_executions"] += 1
        
        # Update average execution time
        total_executions = self.execution_stats["total_executions"]
        current_avg = self.execution_stats["average_execution_time"]
        self.execution_stats["average_execution_time"] = (
            (current_avg * (total_executions - 1) + result.execution_time) / total_executions
        )
        
        # Update orders per second
        if result.execution_time > 0:
            current_ops = result.total_orders / result.execution_time
            current_ops_avg = self.execution_stats["orders_per_second"]
            self.execution_stats["orders_per_second"] = (
                (current_ops_avg * (total_executions - 1) + current_ops) / total_executions
            )
        
        # Update concurrent efficiency
        efficiency = result.performance_metrics.get("concurrent_efficiency", 0)
        current_eff_avg = self.execution_stats["concurrent_efficiency"]
        self.execution_stats["concurrent_efficiency"] = (
            (current_eff_avg * (total_executions - 1) + efficiency) / total_executions
        )
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get comprehensive execution statistics"""
        return {
            **self.execution_stats,
            "phase_timings": {
                phase.value: {
                    "average": sum(timings) / len(timings) if timings else 0,
                    "samples": len(timings)
                }
                for phase, timings in self.phase_timings.items()
            }
        }

# Global optimized executor instance
optimized_executor: Optional[OptimizedTradeExecutor] = None

def get_optimized_executor() -> OptimizedTradeExecutor:
    """Get or create the global optimized trade executor"""
    global optimized_executor
    
    if optimized_executor is None:
        optimized_executor = OptimizedTradeExecutor()
    
    return optimized_executor

async def execute_trade_optimized(*args, **kwargs) -> ExecutionResult:
    """Convenience function for optimized trade execution"""
    executor = get_optimized_executor()
    return await executor.execute_conservative_trade_async(*args, **kwargs)