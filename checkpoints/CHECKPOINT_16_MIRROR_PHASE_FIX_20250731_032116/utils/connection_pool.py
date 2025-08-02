#!/usr/bin/env python3
"""
Enhanced Connection Pool Manager for improved API performance
Optimizes HTTP connections to Bybit API for faster response times
"""
import asyncio
import aiohttp
import logging
import time
from typing import Optional, Dict, Any
from collections import deque

logger = logging.getLogger(__name__)

class ConnectionPool:
    """Manage a pool of API connections (legacy compatibility)"""
    
    def __init__(self, max_connections: int = 50, ttl: float = 600):
        self.max_connections = max_connections
        self.ttl = ttl
        self.available = deque()
        self.in_use = set()
        self.lock = asyncio.Lock()
        
    async def acquire(self):
        """Acquire a connection from the pool"""
        async with self.lock:
            # Clean up expired connections
            current_time = time.time()
            while self.available:
                conn, created_at = self.available[0]
                if current_time - created_at > self.ttl:
                    self.available.popleft()
                else:
                    break
            
            # Get or create connection
            if self.available:
                conn, _ = self.available.popleft()
            else:
                if len(self.in_use) >= self.max_connections:
                    # Wait for a connection to be released
                    while not self.available:
                        await asyncio.sleep(0.1)
                    conn, _ = self.available.popleft()
                else:
                    # Create new connection
                    conn = await self._create_connection()
            
            self.in_use.add(conn)
            return conn
    
    async def release(self, conn):
        """Release a connection back to the pool"""
        async with self.lock:
            if conn in self.in_use:
                self.in_use.remove(conn)
                self.available.append((conn, time.time()))
    
    async def _create_connection(self):
        """Create a new connection (override in subclass)"""
        return object()  # Placeholder

class EnhancedConnectionPool:
    """
    Enhanced connection pool with optimized settings for trading API performance
    """
    
    def __init__(self):
        self._session = None
        self._connector = None
        self.pool_stats = {
            "requests_made": 0,
            "connection_reuses": 0,
            "new_connections": 0,
            "last_reset": time.time()
        }
        
        # Enhanced monitoring for 2025 best practices
        self._base_limit = 150
        self._base_limit_per_host = 40
        self._current_limit = self._base_limit
        self._current_limit_per_host = self._base_limit_per_host
        self._request_rate_history = deque(maxlen=300)  # 5 minutes of history
        self._last_scale_time = 0
        self._scale_cooldown = 300  # 5 minutes between scaling operations
        self._health_failures = 0
        self._max_health_failures = 3
        
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create optimized aiohttp session with connection pooling"""
        if self._session is None or self._session.closed:
            await self._create_optimized_session()
        return self._session
    
    async def _create_optimized_session(self):
        """Create aiohttp session with optimized connection pool settings"""
        try:
            # Enhanced connector settings for trading API performance (dynamic limits)
            connector_settings = {
                # Connection pool settings (optimized for trading bot load)
                "limit": self._current_limit,  # Dynamic total connection pool size
                "limit_per_host": self._current_limit_per_host,  # Dynamic max connections per host
                "ttl_dns_cache": 600,  # DNS cache TTL - 10 minutes
                "use_dns_cache": True,
                
                # Keep-alive settings for connection reuse
                "keepalive_timeout": 45,  # Keep connections alive for 45 seconds
                "enable_cleanup_closed": True,
                
                # Performance optimizations
                "tcp_nodelay": True,  # Disable Nagle's algorithm for lower latency
                "sock_read": 25,  # Socket read timeout
                "sock_connect": 8,  # Socket connect timeout
            }
            
            self._connector = aiohttp.TCPConnector(**connector_settings)
            
            # Session timeout settings (balanced for trading API)
            timeout_settings = aiohttp.ClientTimeout(
                total=25,      # Total timeout for request
                connect=8,     # Connection establishment timeout  
                sock_read=18,  # Socket read timeout
                sock_connect=5 # Socket connection timeout
            )
            
            # Create session with optimized settings
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout_settings,
                headers={
                    'User-Agent': 'BybitTradingBot/1.0',
                    'Connection': 'keep-alive',
                    'Accept-Encoding': 'gzip, deflate'
                }
            )
            
            logger.info("✅ Enhanced connection pool created with optimized settings")
            logger.debug(f"📊 Pool config: {connector_settings['limit']} total, {connector_settings['limit_per_host']} per host")
            
        except Exception as e:
            logger.error(f"❌ Error creating enhanced connection pool: {e}")
            # Fallback to default session if optimization fails
            self._session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the connection pool and cleanup resources"""
        try:
            if self._session and not self._session.closed:
                await self._session.close()
                logger.info("🔌 Enhanced connection pool closed")
                
            # Log final stats
            self.log_pool_statistics()
                
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
    
    def log_pool_statistics(self):
        """Log connection pool performance statistics"""
        try:
            total_requests = self.pool_stats["requests_made"]
            if total_requests > 0:
                reuse_rate = (self.pool_stats["connection_reuses"] / total_requests) * 100
                uptime_hours = (time.time() - self.pool_stats["last_reset"]) / 3600
                
                logger.info(
                    f"📊 Connection Pool Stats: "
                    f"{total_requests} requests, "
                    f"{reuse_rate:.1f}% reuse rate, "
                    f"{uptime_hours:.1f}h uptime"
                )
        except Exception as e:
            logger.error(f"Error logging pool statistics: {e}")
    
    def track_request(self, reused_connection: bool = False):
        """Track request statistics for monitoring"""
        self.pool_stats["requests_made"] += 1
        if reused_connection:
            self.pool_stats["connection_reuses"] += 1
        else:
            self.pool_stats["new_connections"] += 1
        
        # PHASE 3 OPTIMIZATION: Track request rate for dynamic scaling
        current_time = time.time()
        self._request_rate_history.append(current_time)
        
        # Consider scaling based on request patterns
        asyncio.create_task(self._consider_pool_scaling())
    
    async def _consider_pool_scaling(self):
        """Consider scaling the connection pool based on request patterns"""
        current_time = time.time()
        
        # Respect cooldown period
        if current_time - self._last_scale_time < self._scale_cooldown:
            return
        
        # Need sufficient history
        if len(self._request_rate_history) < 10:
            return
        
        # Calculate request rate over last 60 seconds
        recent_requests = [t for t in self._request_rate_history if current_time - t <= 60]
        request_rate = len(recent_requests) / 60  # requests per second
        
        # Scale up if high request rate
        if request_rate > 5 and self._current_limit < self._base_limit * 2:
            old_limit = self._current_limit
            old_limit_per_host = self._current_limit_per_host
            
            self._current_limit = min(self._current_limit + 50, self._base_limit * 2)
            self._current_limit_per_host = min(self._current_limit_per_host + 15, self._base_limit_per_host * 2)
            
            logger.info(f"📈 Scaled UP connection pool: {old_limit}/{old_limit_per_host} → {self._current_limit}/{self._current_limit_per_host} (rate: {request_rate:.1f} req/s)")
            
            # Recreate session with new limits
            await self._recreate_session_with_new_limits()
            self._last_scale_time = current_time
        
        # Scale down if low request rate
        elif request_rate < 1 and self._current_limit > self._base_limit:
            old_limit = self._current_limit
            old_limit_per_host = self._current_limit_per_host
            
            self._current_limit = max(self._current_limit - 25, self._base_limit)
            self._current_limit_per_host = max(self._current_limit_per_host - 10, self._base_limit_per_host)
            
            logger.info(f"📉 Scaled DOWN connection pool: {old_limit}/{old_limit_per_host} → {self._current_limit}/{self._current_limit_per_host} (rate: {request_rate:.1f} req/s)")
            
            # Recreate session with new limits
            await self._recreate_session_with_new_limits()
            self._last_scale_time = current_time
    
    async def _recreate_session_with_new_limits(self):
        """Recreate the session with new connection limits"""
        try:
            # Close existing session
            if self._session and not self._session.closed:
                await self._session.close()
            
            # Recreate with new limits
            await self._create_optimized_session()
            
        except Exception as e:
            logger.error(f"Error recreating session with new limits: {e}")

    async def health_check(self) -> bool:
        """Perform enhanced health check on the connection pool (2025 version)"""
        try:
            if self._session is None or self._session.closed:
                self._health_failures += 1
                logger.warning(f"Health check failed: session closed (failures: {self._health_failures})")
                return False
                
            # Check connector health
            if self._connector and self._connector.closed:
                self._health_failures += 1
                logger.warning(f"Health check failed: connector closed (failures: {self._health_failures})")
                return False
            
            # Additional health checks for 2025 standards
            if self._connector:
                # Check for connection leaks
                total_connections = getattr(self._connector, '_connections', {})
                if hasattr(total_connections, '__len__'):
                    connection_count = len(total_connections)
                    if connection_count > self._current_limit * 1.2:  # 20% over limit indicates leak
                        logger.warning(f"Potential connection leak detected: {connection_count} connections (limit: {self._current_limit})")
                        self._health_failures += 1
                        return False
                
                # Check if we have too many health failures
                if self._health_failures >= self._max_health_failures:
                    logger.error(f"Connection pool unhealthy: {self._health_failures} consecutive failures")
                    return False
            
            # Reset failure count on successful health check
            self._health_failures = 0
            return True
            
        except Exception as e:
            self._health_failures += 1
            logger.error(f"Connection pool health check failed: {e} (failures: {self._health_failures})")
            return False
    
    def get_pool_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive connection pool health report"""
        try:
            total_requests = self.pool_stats["requests_made"]
            reuses = self.pool_stats["connection_reuses"]
            new_connections = self.pool_stats["new_connections"]
            reuse_rate = (reuses / total_requests * 100) if total_requests > 0 else 0
            
            # Calculate request rate
            current_time = time.time()
            recent_requests = [t for t in self._request_rate_history if current_time - t <= 60]
            request_rate = len(recent_requests) / 60  # requests per second
            
            # Determine health status
            health_status = "healthy"
            issues = []
            
            if self._health_failures > 0:
                health_status = "degraded"
                issues.append(f"{self._health_failures} recent health check failures")
            
            if reuse_rate < 50 and total_requests > 100:
                health_status = "degraded"
                issues.append(f"Low connection reuse rate: {reuse_rate:.1f}%")
            
            if request_rate > 10:
                issues.append("High request rate detected")
                
            if not issues:
                issues.append("All connection pool metrics normal")
            
            return {
                "health_status": health_status,
                "issues": issues,
                "current_limits": {
                    "total": self._current_limit,
                    "per_host": self._current_limit_per_host
                },
                "base_limits": {
                    "total": self._base_limit,
                    "per_host": self._base_limit_per_host
                },
                "performance_metrics": {
                    "total_requests": total_requests,
                    "reuse_rate_percent": reuse_rate,
                    "current_request_rate": request_rate,
                    "health_failures": self._health_failures
                },
                "scaling_info": {
                    "last_scale_time": self._last_scale_time,
                    "cooldown_remaining": max(0, self._scale_cooldown - (current_time - self._last_scale_time))
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating pool health report: {e}")
            return {"health_status": "error", "error": str(e)}

# PERFORMANCE OPTIMIZATION: Import lock-free connection pool
from .lockfree_connection_pool import LockFreeConnectionPool, get_global_pool, cleanup_global_pool

# Global enhanced connection pool instance (legacy)
enhanced_pool = EnhancedConnectionPool()

# NEW: Lock-free connection pool for high-performance scenarios
_lockfree_pool = None

# Legacy compatibility
api_connection_pool = ConnectionPool(max_connections=50)

async def get_enhanced_session() -> aiohttp.ClientSession:
    """Get the global enhanced session instance"""
    return await enhanced_pool.get_session()

async def get_lockfree_session() -> aiohttp.ClientSession:
    """Get a session from the lock-free connection pool (high performance)"""
    global _lockfree_pool
    
    if _lockfree_pool is None:
        _lockfree_pool = await get_global_pool()
    
    connection = _lockfree_pool.get_connection()
    if connection is None:
        # Fallback to enhanced pool if lock-free pool is exhausted
        logger.warning("🔄 Lock-free pool exhausted, falling back to enhanced pool")
        return await enhanced_pool.get_session()
    
    return connection

async def close_enhanced_pool():
    """Close the global enhanced connection pool"""
    await enhanced_pool.close()
    
    # Also cleanup lock-free pool
    await cleanup_global_pool()

# Periodic health check and statistics logging
async def connection_pool_maintenance():
    """Periodic maintenance task for the connection pool (enhanced with lock-free monitoring)"""
    while True:
        try:
            await asyncio.sleep(900)  # Every 15 minutes (more frequent monitoring)
            
            # Enhanced pool health check
            is_healthy = await enhanced_pool.health_check()
            if not is_healthy:
                logger.warning("⚠️ Enhanced connection pool health check failed - recreating session")
                await enhanced_pool._create_optimized_session()
            
            # Lock-free pool health check
            try:
                if _lockfree_pool is not None:
                    lockfree_stats = _lockfree_pool.get_health_report()
                    logger.info(f"🏊 Lock-free pool: {lockfree_stats['health_status']} "
                              f"({lockfree_stats['active_connections']}/{lockfree_stats['max_size']} active, "
                              f"{lockfree_stats['timeout_rate_percent']:.1f}% timeout rate)")
                    
                    # Alert if lock-free pool is degraded
                    if lockfree_stats['health_status'] in ['degraded', 'critical']:
                        logger.warning(f"⚠️ Lock-free pool health: {lockfree_stats['health_status']} - "
                                     f"Issues: {', '.join(lockfree_stats.get('issues', []))}")
            except Exception as lf_error:
                logger.debug(f"Lock-free pool monitoring error: {lf_error}")
            
            # Log enhanced pool statistics
            enhanced_pool.log_pool_statistics()
            
            # Log combined performance metrics
            enhanced_health = enhanced_pool.get_pool_health_report()
            logger.info(f"📊 Connection Pool Summary: Enhanced={enhanced_health['health_status']}, "
                       f"Requests={enhanced_health['performance_metrics']['total_requests']}, "
                       f"Rate={enhanced_health['performance_metrics']['current_request_rate']:.1f}/s")
            
        except Exception as e:
            logger.error(f"Error in connection pool maintenance: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes on error

def start_connection_pool_maintenance():
    """Start the connection pool maintenance task"""
    try:
        asyncio.create_task(connection_pool_maintenance())
        logger.info("✅ Connection pool maintenance task started")
    except Exception as e:
        logger.error(f"Error starting connection pool maintenance: {e}")
