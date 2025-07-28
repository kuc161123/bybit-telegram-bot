#!/usr/bin/env python3
"""
API Request Batching System for Monitor Operations
Implements 2025 best practices for asyncio batch processing and performance optimization
"""
import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import weakref

logger = logging.getLogger(__name__)

class BatchPriority(Enum):
    """Priority levels for batch operations"""
    CRITICAL = 1  # Position updates, urgent monitoring
    HIGH = 2      # TP/SL checks, active positions
    MEDIUM = 3    # Standard monitoring, order updates
    LOW = 4       # Statistics, cleanup operations

@dataclass
class BatchRequest:
    """Individual request within a batch"""
    request_id: str
    operation_type: str
    params: Dict[str, Any]
    priority: BatchPriority
    callback: Optional[Callable] = None
    created_at: float = field(default_factory=time.time)
    completed: bool = False
    result: Any = None
    error: Optional[Exception] = None

@dataclass
class BatchGroup:
    """Group of related requests that can be batched together"""
    operation_type: str
    requests: List[BatchRequest] = field(default_factory=list)
    max_batch_size: int = 10
    max_wait_time: float = 2.0  # seconds
    created_at: float = field(default_factory=time.time)

class APIBatchProcessor:
    """
    High-performance API request batching system
    Based on 2025 asyncio best practices with dynamic batching and priority queues
    """

    def __init__(self, max_concurrent_batches: int = 5):
        self.max_concurrent_batches = max_concurrent_batches
        self.request_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.batch_groups: Dict[str, BatchGroup] = {}
        self.pending_batches: Dict[str, asyncio.Task] = {}
        self.processing_semaphore = asyncio.Semaphore(max_concurrent_batches)
        
        # Performance metrics
        self.stats = {
            'requests_processed': 0,
            'batches_created': 0,
            'average_batch_size': 0.0,
            'cache_hits': 0,
            'processing_time_total': 0.0
        }
        
        # Request deduplication cache
        self.request_cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_ttl = 5.0  # 5 second cache for request deduplication
        
        # Batch processing configuration by operation type
        self.batch_configs = {
            'position_info': {'max_size': 20, 'max_wait': 1.0},
            'order_info': {'max_size': 15, 'max_wait': 1.5},
            'market_data': {'max_size': 10, 'max_wait': 2.0},
            'balance_info': {'max_size': 5, 'max_wait': 0.5},
            'default': {'max_size': 10, 'max_wait': 2.0}
        }
        
        # Start background processor
        self._processor_task = None
        self._stop_event = asyncio.Event()
        
    async def start(self):
        """Start the batch processor"""
        if self._processor_task is None:
            self._processor_task = asyncio.create_task(self._batch_processor())
            logger.info("🚀 API Batch Processor started")
    
    async def stop(self):
        """Stop the batch processor gracefully"""
        self._stop_event.set()
        if self._processor_task:
            await self._processor_task
            logger.info("✅ API Batch Processor stopped")
    
    def _generate_cache_key(self, operation_type: str, params: Dict[str, Any]) -> str:
        """Generate cache key for request deduplication"""
        # Create a consistent key from operation type and parameters
        sorted_params = sorted(params.items())
        param_str = "_".join(f"{k}:{v}" for k, v in sorted_params)
        return f"{operation_type}:{param_str}"
    
    def _check_cache(self, cache_key: str) -> Optional[Any]:
        """Check if request result is cached"""
        if cache_key in self.request_cache:
            result, timestamp = self.request_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                self.stats['cache_hits'] += 1
                return result
            else:
                # Cache expired
                del self.request_cache[cache_key]
        return None
    
    def _update_cache(self, cache_key: str, result: Any):
        """Update request cache"""
        self.request_cache[cache_key] = (result, time.time())
    
    async def submit_request(self, operation_type: str, params: Dict[str, Any], 
                           priority: BatchPriority = BatchPriority.MEDIUM,
                           callback: Optional[Callable] = None) -> str:
        """
        Submit a request for batched processing
        Returns request_id for tracking
        """
        # Check cache first
        cache_key = self._generate_cache_key(operation_type, params)
        cached_result = self._check_cache(cache_key)
        if cached_result is not None:
            if callback:
                await callback(cached_result)
            return f"cached_{int(time.time() * 1000000)}"
        
        # Create request
        request_id = f"{operation_type}_{int(time.time() * 1000000)}"
        request = BatchRequest(
            request_id=request_id,
            operation_type=operation_type,
            params=params,
            priority=priority,
            callback=callback
        )
        
        # Add to priority queue
        await self.request_queue.put((priority.value, request.created_at, request))
        
        return request_id
    
    async def _batch_processor(self):
        """Main batch processing loop"""
        logger.info("🔄 Batch processor loop started")
        
        while not self._stop_event.is_set():
            try:
                # Get requests from queue with timeout
                requests_to_process = []
                
                # Collect requests for batching (up to 100ms window)
                timeout = 0.1  # 100ms collection window
                start_time = time.time()
                
                while (time.time() - start_time < timeout and 
                       len(requests_to_process) < 50):  # Max 50 requests per batch cycle
                    try:
                        priority, created_at, request = await asyncio.wait_for(
                            self.request_queue.get(), timeout=0.05
                        )
                        requests_to_process.append(request)
                    except asyncio.TimeoutError:
                        break
                
                if requests_to_process:
                    # Group requests by operation type
                    grouped_requests = defaultdict(list)
                    for request in requests_to_process:
                        grouped_requests[request.operation_type].append(request)
                    
                    # Process each group as a batch
                    batch_tasks = []
                    for operation_type, requests in grouped_requests.items():
                        task = asyncio.create_task(
                            self._process_batch(operation_type, requests)
                        )
                        batch_tasks.append(task)
                    
                    # Wait for all batches to complete with semaphore control
                    if batch_tasks:
                        await asyncio.gather(*batch_tasks, return_exceptions=True)
                else:
                    # No requests - short sleep to prevent CPU spinning
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"❌ Error in batch processor: {e}")
                await asyncio.sleep(0.1)  # Brief pause before retry
    
    async def _process_batch(self, operation_type: str, requests: List[BatchRequest]):
        """Process a batch of requests for the same operation type"""
        if not requests:
            return
        
        async with self.processing_semaphore:
            start_time = time.time()
            
            try:
                logger.debug(f"🔍 Processing batch: {operation_type} ({len(requests)} requests)")
                
                # Get batch configuration
                config = self.batch_configs.get(operation_type, self.batch_configs['default'])
                
                # Split into smaller batches if needed
                batch_size = min(len(requests), config['max_size'])
                
                for i in range(0, len(requests), batch_size):
                    batch_requests = requests[i:i + batch_size]
                    
                    # Process batch based on operation type
                    if operation_type == 'position_info':
                        await self._process_position_batch(batch_requests)
                    elif operation_type == 'order_info':
                        await self._process_order_batch(batch_requests)
                    elif operation_type == 'market_data':
                        await self._process_market_data_batch(batch_requests)
                    elif operation_type == 'balance_info':
                        await self._process_balance_batch(batch_requests)
                    else:
                        # Generic batch processing
                        await self._process_generic_batch(batch_requests)
                
                # Update statistics
                processing_time = time.time() - start_time
                self.stats['requests_processed'] += len(requests)
                self.stats['batches_created'] += 1
                self.stats['processing_time_total'] += processing_time
                self.stats['average_batch_size'] = (
                    self.stats['requests_processed'] / self.stats['batches_created']
                )
                
                logger.debug(f"✅ Batch completed: {operation_type} in {processing_time:.3f}s")
                
            except Exception as e:
                logger.error(f"❌ Error processing batch {operation_type}: {e}")
                # Mark all requests as failed
                for request in requests:
                    request.error = e
                    request.completed = True
    
    async def _process_position_batch(self, requests: List[BatchRequest]):
        """Process position info requests in batch"""
        from clients.bybit_helpers import get_all_positions
        
        try:
            # Single API call gets all positions
            positions = await get_all_positions()
            
            # Distribute results to individual requests
            for request in requests:
                symbol = request.params.get('symbol')
                account = request.params.get('account', 'main')
                
                # Filter positions for this request
                if symbol:
                    filtered_positions = [p for p in positions if p.get('symbol') == symbol]
                else:
                    filtered_positions = positions
                
                request.result = filtered_positions
                request.completed = True
                
                # Update cache
                cache_key = self._generate_cache_key(request.operation_type, request.params)
                self._update_cache(cache_key, filtered_positions)
                
                # Execute callback
                if request.callback:
                    await request.callback(filtered_positions)
                    
        except Exception as e:
            for request in requests:
                request.error = e
                request.completed = True
    
    async def _process_order_batch(self, requests: List[BatchRequest]):
        """Process order info requests in batch"""
        from clients.bybit_helpers import get_all_open_orders
        
        try:
            # Get all orders for each unique symbol/account combination
            unique_params = set()
            for request in requests:
                symbol = request.params.get('symbol')
                account = request.params.get('account', 'main')
                unique_params.add((symbol, account))
            
            # Batch API calls for unique parameter combinations
            results_cache = {}
            for symbol, account in unique_params:
                if account == 'mirror':
                    from execution.mirror_trader import bybit_client_2
                    if bybit_client_2:
                        orders = await get_all_open_orders(client=bybit_client_2, symbol=symbol)
                    else:
                        orders = []
                else:
                    orders = await get_all_open_orders(symbol=symbol)
                
                results_cache[(symbol, account)] = orders
            
            # Distribute results
            for request in requests:
                symbol = request.params.get('symbol')
                account = request.params.get('account', 'main')
                
                request.result = results_cache.get((symbol, account), [])
                request.completed = True
                
                # Update cache
                cache_key = self._generate_cache_key(request.operation_type, request.params)
                self._update_cache(cache_key, request.result)
                
                # Execute callback
                if request.callback:
                    await request.callback(request.result)
                    
        except Exception as e:
            for request in requests:
                request.error = e
                request.completed = True
    
    async def _process_market_data_batch(self, requests: List[BatchRequest]):
        """Process market data requests in batch"""
        # Group by symbol to minimize API calls
        symbols = set()
        for request in requests:
            symbol = request.params.get('symbol')
            if symbol:
                symbols.add(symbol)
        
        # Batch fetch market data for all symbols
        from market_analysis.market_data_collector import market_data_collector
        
        results_cache = {}
        for symbol in symbols:
            try:
                market_data = await market_data_collector.collect_market_data(symbol)
                results_cache[symbol] = market_data
            except Exception as e:
                logger.error(f"Error fetching market data for {symbol}: {e}")
                results_cache[symbol] = None
        
        # Distribute results
        for request in requests:
            symbol = request.params.get('symbol')
            request.result = results_cache.get(symbol)
            request.completed = True
            
            # Update cache
            cache_key = self._generate_cache_key(request.operation_type, request.params)
            self._update_cache(cache_key, request.result)
            
            # Execute callback
            if request.callback:
                await request.callback(request.result)
    
    async def _process_balance_batch(self, requests: List[BatchRequest]):
        """Process balance info requests in batch"""
        from clients.bybit_helpers import get_wallet_balance
        from execution.mirror_trader import get_mirror_wallet_balance
        
        try:
            # Batch get both main and mirror balances
            main_balance_task = asyncio.create_task(get_wallet_balance())
            mirror_balance_task = asyncio.create_task(get_mirror_wallet_balance())
            
            main_balance, mirror_balance = await asyncio.gather(
                main_balance_task, mirror_balance_task, return_exceptions=True
            )
            
            # Distribute results
            for request in requests:
                account = request.params.get('account', 'main')
                
                if account == 'mirror':
                    if isinstance(mirror_balance, Exception):
                        request.error = mirror_balance
                    else:
                        request.result = mirror_balance
                else:
                    if isinstance(main_balance, Exception):
                        request.error = main_balance
                    else:
                        request.result = main_balance
                
                request.completed = True
                
                # Update cache
                cache_key = self._generate_cache_key(request.operation_type, request.params)
                if not request.error:
                    self._update_cache(cache_key, request.result)
                
                # Execute callback
                if request.callback and not request.error:
                    await request.callback(request.result)
                    
        except Exception as e:
            for request in requests:
                request.error = e
                request.completed = True
    
    async def _process_generic_batch(self, requests: List[BatchRequest]):
        """Generic batch processing for unknown operation types"""
        for request in requests:
            # For now, mark as completed with no result
            # This can be extended for specific operation types
            request.result = None
            request.completed = True
            
            if request.callback:
                await request.callback(None)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get batch processor statistics"""
        current_time = time.time()
        return {
            **self.stats,
            'pending_requests': self.request_queue.qsize(),
            'active_batches': len(self.pending_batches),
            'cache_size': len(self.request_cache),
            'requests_per_second': (
                self.stats['requests_processed'] / 
                max(self.stats['processing_time_total'], 0.001)
            )
        }
    
    async def cleanup_expired_cache(self):
        """Clean up expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.request_cache.items()
            if current_time - timestamp > self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.request_cache[key]
        
        if expired_keys:
            logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")

# Global batch processor instance
batch_processor: Optional[APIBatchProcessor] = None

def get_batch_processor() -> APIBatchProcessor:
    """Get or create the global batch processor instance"""
    global batch_processor
    if batch_processor is None:
        batch_processor = APIBatchProcessor()
    return batch_processor

async def start_batch_processor():
    """Start the global batch processor"""
    processor = get_batch_processor()
    await processor.start()

async def stop_batch_processor():
    """Stop the global batch processor"""
    global batch_processor
    if batch_processor:
        await batch_processor.stop()
        batch_processor = None