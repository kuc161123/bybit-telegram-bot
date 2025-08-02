#!/usr/bin/env python3
"""
Lock-free connection pool with burst capability for high-performance trading bots.
Based on research findings: burst-capable pool free of explicit locking.
"""
import asyncio
import aiohttp
import logging
import time
from typing import Optional, Dict, Any
from collections import deque
from dataclasses import dataclass
import weakref

logger = logging.getLogger(__name__)


@dataclass
class PoolStats:
    """Connection pool statistics"""
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    peak_connections: int = 0
    connection_requests: int = 0
    connection_timeouts: int = 0
    burst_activations: int = 0


class LockFreeConnectionPool:
    """
    High-throughput, optionally-burstable pool free of explicit locking.
    No locking; no asyncio.Lock or asyncio.Condition needs to be taken to get a connection.
    Available connections are retrieved without yielding to the event loop.
    """
    
    def __init__(
        self,
        max_size: int = 150,  # Soft limit
        burst_limit: int = 300,  # Hard limit during bursts
        keepalive_timeout: int = 60,  # Keep connections alive for 60s
        burst_duration: int = 30,  # Allow burst for 30s
        shrink_interval: int = 10  # Check for shrinking every 10s
    ):
        self.max_size = max_size
        self.burst_limit = burst_limit
        self.keepalive_timeout = keepalive_timeout
        self.burst_duration = burst_duration
        self.shrink_interval = shrink_interval
        
        # Lock-free data structures
        self._available_connections = deque()  # Available connections
        self._active_connections = weakref.WeakSet()  # Active connections (auto-cleanup)
        self._connection_times = {}  # Connection ID -> creation time
        self._last_burst_time = 0
        self._last_shrink_time = time.time()
        
        # Statistics (lock-free counters)
        self._stats = PoolStats()
        
        # Connector for creating new connections
        self._connector = None
        self._session = None
        
        # Background tasks
        self._cleanup_task = None
        self._shrink_task = None
        
        logger.info(f"🏊 Initialized lock-free connection pool: max={max_size}, burst={burst_limit}")
    
    async def start(self):
        """Start the connection pool and background tasks"""
        try:
            # Create optimized connector
            self._connector = aiohttp.TCPConnector(
                limit=self.burst_limit,
                limit_per_host=self.max_size,
                keepalive_timeout=self.keepalive_timeout,
                enable_cleanup_closed=True,
                use_dns_cache=True,
                ttl_dns_cache=300,
                family=0,  # Allow both IPv4 and IPv6
                ssl=False,  # Disable SSL verification for performance (use with caution)
                force_close=False  # Keep connections alive
            )
            
            # Create session
            timeout = aiohttp.ClientTimeout(total=60, connect=20)
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers={'Connection': 'keep-alive'}
            )
            
            # Start background maintenance
            self._cleanup_task = asyncio.create_task(self._background_cleanup())
            self._shrink_task = asyncio.create_task(self._background_shrink())
            
            logger.info("✅ Lock-free connection pool started with background maintenance")
            
        except Exception as e:
            logger.error(f"❌ Failed to start connection pool: {e}")
            raise
    
    async def stop(self):
        """Stop the connection pool and cleanup"""
        try:
            # Cancel background tasks
            if self._cleanup_task:
                self._cleanup_task.cancel()
            if self._shrink_task:
                self._shrink_task.cancel()
            
            # Close all connections
            if self._session:
                await self._session.close()
            if self._connector:
                await self._connector.close()
            
            # Clear data structures
            self._available_connections.clear()
            self._active_connections.clear()
            self._connection_times.clear()
            
            logger.info("✅ Lock-free connection pool stopped and cleaned up")
            
        except Exception as e:
            logger.error(f"❌ Error stopping connection pool: {e}")
    
    def get_connection(self) -> Optional[aiohttp.ClientSession]:
        """
        Get a connection without blocking (lock-free).
        Returns immediately with available connection or None.
        """
        current_time = time.time()
        self._stats.connection_requests += 1
        
        # Try to get available connection first (lock-free)
        try:
            connection = self._available_connections.popleft()
            self._active_connections.add(connection)
            return connection
        except IndexError:
            pass  # No available connections
        
        # Check if we can create new connection
        total_connections = len(self._active_connections) + len(self._available_connections)
        
        # Within normal limit
        if total_connections < self.max_size:
            return self._create_new_connection()
        
        # Check if burst is allowed
        if self._can_burst(current_time) and total_connections < self.burst_limit:
            self._last_burst_time = current_time
            self._stats.burst_activations += 1
            logger.debug(f"🚀 Burst activation: {total_connections}/{self.burst_limit} connections")
            return self._create_new_connection()
        
        # Pool exhausted
        self._stats.connection_timeouts += 1
        logger.warning(f"⚠️ Connection pool exhausted: {total_connections} connections active")
        return None
    
    def return_connection(self, connection: aiohttp.ClientSession):
        """Return a connection to the pool (lock-free)"""
        if connection in self._active_connections:
            self._active_connections.discard(connection)
            
            # Only return healthy connections to available pool
            if not connection.closed:
                self._available_connections.append(connection)
            else:
                # Connection is closed, remove from tracking
                conn_id = id(connection)
                self._connection_times.pop(conn_id, None)
    
    def _create_new_connection(self) -> aiohttp.ClientSession:
        """Create a new connection (internal use)"""
        if not self._session:
            logger.error("❌ Cannot create connection - pool not started")
            return None
        
        # Use the shared session (it manages connections internally)
        self._active_connections.add(self._session)
        self._stats.total_connections += 1
        self._stats.active_connections = len(self._active_connections)
        
        if self._stats.active_connections > self._stats.peak_connections:
            self._stats.peak_connections = self._stats.active_connections
        
        return self._session
    
    def _can_burst(self, current_time: float) -> bool:
        """Check if burst mode is allowed"""
        # Allow burst if we haven't burst recently or if we're still within burst duration
        time_since_burst = current_time - self._last_burst_time
        return time_since_burst > self.burst_duration or time_since_burst < 5  # 5s grace period
    
    async def _background_cleanup(self):
        """Background task to cleanup stale connections"""
        while True:
            try:
                await asyncio.sleep(30)  # Cleanup every 30 seconds
                
                current_time = time.time()
                stale_connections = []
                
                # Find stale connections (lock-free iteration)
                for connection in list(self._available_connections):
                    conn_id = id(connection)
                    create_time = self._connection_times.get(conn_id, current_time)
                    
                    if current_time - create_time > self.keepalive_timeout:
                        stale_connections.append(connection)
                
                # Remove stale connections
                for connection in stale_connections:
                    try:
                        self._available_connections.remove(connection)
                        conn_id = id(connection)
                        self._connection_times.pop(conn_id, None)
                        if hasattr(connection, 'close'):
                            await connection.close()
                    except (ValueError, Exception) as e:
                        logger.debug(f"Error cleaning up stale connection: {e}")
                
                if stale_connections:
                    logger.debug(f"🧹 Cleaned up {len(stale_connections)} stale connections")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in background cleanup: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _background_shrink(self):
        """Background task to shrink pool after burst periods"""
        while True:
            try:
                await asyncio.sleep(self.shrink_interval)
                
                current_time = time.time()
                self._last_shrink_time = current_time
                
                # Check if we should shrink after burst
                time_since_burst = current_time - self._last_burst_time
                total_connections = len(self._active_connections) + len(self._available_connections)
                
                if (time_since_burst > self.burst_duration and 
                    total_connections > self.max_size and
                    len(self._available_connections) > 0):
                    
                    # Calculate how many to shrink
                    excess_connections = total_connections - self.max_size
                    shrink_count = min(excess_connections, len(self._available_connections))
                    
                    # Remove excess available connections
                    for _ in range(shrink_count):
                        try:
                            connection = self._available_connections.popleft()
                            conn_id = id(connection)
                            self._connection_times.pop(conn_id, None)
                            if hasattr(connection, 'close'):
                                await connection.close()
                        except (IndexError, Exception):
                            break
                    
                    if shrink_count > 0:
                        logger.info(f"📉 Shrunk pool by {shrink_count} connections after burst period")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in background shrink: {e}")
                await asyncio.sleep(60)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        total_connections = len(self._active_connections) + len(self._available_connections)
        
        return {
            'total_connections': total_connections,
            'active_connections': len(self._active_connections),
            'idle_connections': len(self._available_connections),
            'peak_connections': self._stats.peak_connections,
            'connection_requests': self._stats.connection_requests,
            'connection_timeouts': self._stats.connection_timeouts,
            'burst_activations': self._stats.burst_activations,
            'max_size': self.max_size,
            'burst_limit': self.burst_limit,
            'health_status': 'healthy' if self._stats.connection_timeouts < 10 else 'degraded'
        }
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get detailed health report"""
        stats = self.get_stats()
        
        # Calculate health score
        timeout_rate = (stats['connection_timeouts'] / max(stats['connection_requests'], 1)) * 100
        utilization = (stats['active_connections'] / max(stats['max_size'], 1)) * 100
        
        health_score = 100
        if timeout_rate > 5:
            health_score -= min(timeout_rate * 2, 50)
        if utilization > 90:
            health_score -= min((utilization - 90) * 2, 30)
        
        return {
            **stats,
            'timeout_rate_percent': timeout_rate,
            'utilization_percent': utilization,
            'health_score': max(0, health_score),
            'health_status': 'healthy' if health_score > 80 else 'degraded' if health_score > 50 else 'critical'
        }


# Global instance
_global_pool = None


async def get_global_pool() -> LockFreeConnectionPool:
    """Get or create the global connection pool"""
    global _global_pool
    
    if _global_pool is None:
        from config.settings import HTTP_MAX_CONNECTIONS, HTTP_MAX_CONNECTIONS_PER_HOST
        
        _global_pool = LockFreeConnectionPool(
            max_size=HTTP_MAX_CONNECTIONS_PER_HOST,
            burst_limit=HTTP_MAX_CONNECTIONS,
            keepalive_timeout=60,
            burst_duration=30,
            shrink_interval=10
        )
        await _global_pool.start()
        logger.info("🌍 Global lock-free connection pool initialized")
    
    return _global_pool


async def cleanup_global_pool():
    """Cleanup the global connection pool"""
    global _global_pool
    
    if _global_pool:
        await _global_pool.stop()
        _global_pool = None
        logger.info("🌍 Global lock-free connection pool cleaned up")