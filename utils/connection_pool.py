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
        
    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create optimized aiohttp session with connection pooling"""
        if self._session is None or self._session.closed:
            await self._create_optimized_session()
        return self._session
    
    async def _create_optimized_session(self):
        """Create aiohttp session with optimized connection pool settings"""
        try:
            # Enhanced connector settings for trading API performance
            connector_settings = {
                # Connection pool settings (optimized for trading bot load)
                "limit": 150,  # Total connection pool size (balanced for performance)
                "limit_per_host": 40,  # Max connections per host
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
        """Perform health check on the connection pool"""
        try:
            if self._session is None or self._session.closed:
                return False
                
            # Check connector health
            if self._connector and self._connector.closed:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Connection pool health check failed: {e}")
            return False

# Global enhanced connection pool instance
enhanced_pool = EnhancedConnectionPool()

# Legacy compatibility
api_connection_pool = ConnectionPool(max_connections=50)

async def get_enhanced_session() -> aiohttp.ClientSession:
    """Get the global enhanced session instance"""
    return await enhanced_pool.get_session()

async def close_enhanced_pool():
    """Close the global enhanced connection pool"""
    await enhanced_pool.close()

# Periodic health check and statistics logging
async def connection_pool_maintenance():
    """Periodic maintenance task for the connection pool"""
    while True:
        try:
            await asyncio.sleep(1800)  # Every 30 minutes
            
            # Health check
            is_healthy = await enhanced_pool.health_check()
            if not is_healthy:
                logger.warning("⚠️ Connection pool health check failed - recreating session")
                await enhanced_pool._create_optimized_session()
            
            # Log statistics
            enhanced_pool.log_pool_statistics()
            
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
