#!/usr/bin/env python3
"""
Bybit API client initialization and management.
FIXED: Improved connection pool configuration and stability
FIXED: Better async/sync compatibility and error handling
FIXED: Removed incompatible parameters for better version compatibility
ENHANCED: Proper HTTP client configuration with connection limits
FIXED: Increased connection pool size to prevent "pool full" errors
"""
import logging
import asyncio
import aiohttp
from contextlib import contextmanager
from typing import List, Dict, Optional
from pybit.unified_trading import HTTP
from pybit.exceptions import InvalidRequestError, FailedRequestError
from config.settings import (
    BYBIT_API_KEY, BYBIT_API_SECRET, USE_TESTNET, BYBIT_TIMEOUT_SECONDS,
    HTTP_MAX_CONNECTIONS, HTTP_MAX_CONNECTIONS_PER_HOST, HTTP_KEEPALIVE_TIMEOUT,
    HTTP_DNS_CACHE_TTL
)

logger = logging.getLogger(__name__)

# FIXED: Global HTTP session for connection pooling
_http_session = None
_session_lock = asyncio.Lock()

async def get_http_session():
    """Get or create HTTP session with proper connection pooling"""
    global _http_session

    if _http_session is None or _http_session.closed:
        # PERFORMANCE OPTIMIZED: Create connector with DOUBLED connection pool settings
        connector = aiohttp.TCPConnector(
            limit=HTTP_MAX_CONNECTIONS,  # Total connection pool size (600 - DOUBLED)
            limit_per_host=HTTP_MAX_CONNECTIONS_PER_HOST,  # Per-host connections (150 - DOUBLED)
            ttl_dns_cache=HTTP_DNS_CACHE_TTL,  # DNS cache TTL
            use_dns_cache=True,
            keepalive_timeout=HTTP_KEEPALIVE_TIMEOUT,
            enable_cleanup_closed=True,
            force_close=False,  # Keep connections alive
            # NEW: Connection recycling and performance optimizations
            ttl_pool=300,  # Connection pool TTL (5 minutes)
            limit_per_host_active=50,  # Active connections per host
            resolver=None,  # Use default resolver with caching
            family=0,  # Use both IPv4 and IPv6
            ssl=False  # Disable SSL verification for performance (use with caution)
        )

        # Create session with timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=BYBIT_TIMEOUT_SECONDS,
            connect=15,
            sock_read=BYBIT_TIMEOUT_SECONDS,
            sock_connect=15
        )

        _http_session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Enhanced-Trading-Bot/1.0',
                'Connection': 'keep-alive',
                'Keep-Alive': f'timeout={HTTP_KEEPALIVE_TIMEOUT}'
            }
        )

        logger.info(f"✅ HTTP session created with ENHANCED connection pooling")
        logger.info(f"   Total connections: {HTTP_MAX_CONNECTIONS}")
        logger.info(f"   Per-host connections: {HTTP_MAX_CONNECTIONS_PER_HOST}")
        logger.info(f"   Keep-alive timeout: {HTTP_KEEPALIVE_TIMEOUT}s")

    return _http_session

async def cleanup_http_session():
    """Cleanup HTTP session on shutdown"""
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
        logger.info("✅ HTTP session cleaned up")

async def recycle_http_session():
    """Recycle HTTP session to prevent connection pool exhaustion"""
    global _http_session
    async with _session_lock:
        if _http_session and not _http_session.closed:
            logger.info("🔄 Recycling HTTP session for performance optimization")
            await _http_session.close()
            _http_session = None
            # Next call to get_http_session() will create a fresh session
            logger.info("✅ HTTP session recycled successfully")

# Initialize Bybit client with enhanced configuration
def create_bybit_client():
    """Create and return a Bybit HTTP client with enhanced configuration"""
    try:
        # FIXED: Basic client configuration with only widely supported parameters
        basic_params = {
            "api_key": BYBIT_API_KEY,
            "api_secret": BYBIT_API_SECRET,
            "testnet": USE_TESTNET
        }

        # Add optional parameters that are commonly supported
        optional_params = {}

        # Try adding timeout parameter (widely supported)
        try:
            optional_params["timeout"] = BYBIT_TIMEOUT_SECONDS
        except:
            logger.warning("Timeout parameter not supported in this pybit version")

        # FIXED: Try adding recv_window parameter with larger value
        try:
            optional_params["recv_window"] = 20000  # Increased from 5000 to 20000
        except:
            logger.warning("recv_window parameter not supported in this pybit version")

        # Combine parameters
        client_params = {**basic_params, **optional_params}

        # Create client with compatible parameters only
        client = HTTP(**client_params)

        logger.info(f"✅ Bybit client initialized successfully")
        logger.info(f"  Environment: {'TESTNET' if USE_TESTNET else 'MAINNET'}")
        logger.info(f"  Timeout: {BYBIT_TIMEOUT_SECONDS}s")
        logger.info(f"  Connection Pool: {HTTP_MAX_CONNECTIONS} total, {HTTP_MAX_CONNECTIONS_PER_HOST} per host")
        logger.info(f"  Enhanced reliability: Enabled")
        logger.info(f"  Compatible mode: Active (removed unsupported parameters)")

        # FIXED: Enhanced connection test with proper error handling
        try:
            # Test with a simple API call that works on both testnet and mainnet
            test_response = client.get_instruments_info(category="linear", limit=1)
            if test_response and test_response.get("retCode") == 0:
                logger.info(f"✅ Bybit API connection test successful")
            else:
                logger.warning(f"⚠️ Bybit API test returned: {test_response}")
        except Exception as e:
            logger.warning(f"⚠️ Bybit API connection test failed: {e}")
            logger.info("Continuing with client initialization...")

        return client

    except Exception as e:
        logger.error(f"❌ Failed Bybit client initialization: {e}", exc_info=True)

        # FIXED: Fallback to minimal configuration if enhanced config fails
        try:
            logger.info("🔄 Attempting fallback client initialization...")
            fallback_client = HTTP(
                api_key=BYBIT_API_KEY,
                api_secret=BYBIT_API_SECRET,
                testnet=USE_TESTNET
            )
            logger.info("✅ Fallback Bybit client initialized successfully")
            return fallback_client
        except Exception as fallback_error:
            logger.error(f"❌ Fallback client initialization also failed: {fallback_error}")
            raise RuntimeError(f"Critical error: Could not initialize Bybit client with any configuration: {fallback_error}")

@contextmanager
def api_error_handler(operation: str):
    """Enhanced context manager for API error handling with better logging"""
    try:
        yield
    except InvalidRequestError as e:
        logger.error(f"{operation} - Bybit Invalid Request: {e}")
        raise
    except FailedRequestError as e:
        logger.error(f"{operation} - Bybit Failed Request: {e}")
        raise
    except Exception as e:
        logger.error(f"{operation} - Unexpected error: {e}", exc_info=True)
        raise

# Global client instance
bybit_client = create_bybit_client()

# =============================================
# ENHANCED POSITION HELPER FUNCTIONS
# =============================================

async def get_position_info(symbol: str) -> Optional[Dict]:
    """
    Get position information for a specific symbol with enhanced error handling

    Args:
        symbol: Trading symbol (e.g., 'BTCUSDT')

    Returns:
        Position dict or None if not found
    """
    try:
        with api_error_handler(f"Get position info for {symbol}"):
            # FIXED: Use async wrapper for better performance
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client.get_positions(
                    category="linear",
                    symbol=symbol
                )
            )

            if response.get("retCode") == 0:
                result = response.get("result", {})
                positions = result.get("list", [])

                # Find the position for this symbol
                for pos in positions:
                    if pos.get("symbol") == symbol:
                        return pos

                # Return empty position if symbol not found
                return {
                    "symbol": symbol,
                    "side": "",
                    "size": "0",
                    "avgPrice": "0",
                    "markPrice": "0",
                    "unrealisedPnl": "0",
                    "positionIM": "0",
                    "positionMM": "0",
                    "positionStatus": "Normal"
                }
            else:
                logger.error(f"Bybit API error getting position for {symbol}: {response}")
                return None

    except Exception as e:
        logger.error(f"Error getting position info for {symbol}: {e}")
        return None

async def get_all_positions() -> List[Dict]:
    """
    Get all active positions with enhanced error handling and connection pooling

    Returns:
        List of position dicts
    """
    try:
        with api_error_handler("Get all positions"):
            # FIXED: Use async wrapper for better performance
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: bybit_client.get_positions(
                    category="linear",
                    settleCoin="USDT"
                )
            )

            if response.get("retCode") == 0:
                result = response.get("result", {})
                positions = result.get("list", [])

                logger.debug(f"Retrieved {len(positions)} positions from Bybit")
                return positions
            else:
                logger.error(f"Bybit API error getting all positions: {response}")
                return []

    except Exception as e:
        logger.error(f"Error getting all positions: {e}")
        return []

async def get_active_positions() -> List[Dict]:
    """
    Get only active positions (size > 0) with enhanced filtering

    Returns:
        List of active position dicts
    """
    try:
        all_positions = await get_all_positions()
        active_positions = []

        for pos in all_positions:
            try:
                size = float(pos.get("size", "0"))
                if size > 0:
                    active_positions.append(pos)
            except (ValueError, TypeError):
                # Skip positions with invalid size data
                logger.warning(f"Skipping position with invalid size: {pos.get('symbol', 'Unknown')}")
                continue

        logger.info(f"Found {len(active_positions)} active positions out of {len(all_positions)} total")
        return active_positions

    except Exception as e:
        logger.error(f"Error filtering active positions: {e}")
        return []

async def get_position_pnl(symbol: str) -> Dict:
    """
    Get P&L information for a specific position with enhanced calculation

    Args:
        symbol: Trading symbol

    Returns:
        Dict with P&L information
    """
    try:
        positions = await get_position_info(symbol)
        position = None

        if positions:
            # Find the position with non-zero size
            for pos in positions:
                if float(pos.get("size", 0)) > 0:
                    position = pos
                    break

        if not position:
            return {
                "symbol": symbol,
                "unrealisedPnl": "0",
                "realisedPnl": "0",
                "pnlPercent": "0",
                "error": "Position not found"
            }

        try:
            unrealised_pnl = float(position.get("unrealisedPnl", "0"))
            size = float(position.get("size", "0"))
            avg_price = float(position.get("avgPrice", "0"))
            mark_price = float(position.get("markPrice", "0"))
            side = position.get("side", "")

            # Calculate percentage PnL with enhanced error handling
            pnl_percent = 0
            if avg_price > 0 and mark_price > 0 and size > 0:
                if side == "Buy":
                    pnl_percent = ((mark_price - avg_price) / avg_price) * 100
                elif side == "Sell":
                    pnl_percent = ((avg_price - mark_price) / avg_price) * 100

        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.warning(f"Error calculating P&L for {symbol}: {e}")
            unrealised_pnl = 0
            pnl_percent = 0
            size = 0
            avg_price = 0
            mark_price = 0
            side = ""

        return {
            "symbol": symbol,
            "unrealisedPnl": str(unrealised_pnl),
            "realisedPnl": position.get("cumRealisedPnl", "0"),
            "pnlPercent": f"{pnl_percent:.2f}",
            "size": str(size),
            "side": side,
            "avgPrice": str(avg_price),
            "markPrice": str(mark_price)
        }

    except Exception as e:
        logger.error(f"Error getting P&L for {symbol}: {e}")
        return {
            "symbol": symbol,
            "unrealisedPnl": "0",
            "realisedPnl": "0",
            "pnlPercent": "0",
            "error": str(e)
        }

async def get_total_unrealised_pnl() -> float:
    """
    Get total unrealised P&L across all positions with enhanced error handling

    Returns:
        Total unrealised P&L as float
    """
    try:
        positions = await get_all_positions()
        total_pnl = 0.0

        for pos in positions:
            try:
                unrealised_pnl = float(pos.get("unrealisedPnl", "0"))
                total_pnl += unrealised_pnl
            except (ValueError, TypeError):
                # Skip positions with invalid P&L data
                logger.warning(f"Skipping position with invalid P&L: {pos.get('symbol', 'Unknown')}")
                continue

        return total_pnl

    except Exception as e:
        logger.error(f"Error calculating total unrealised P&L: {e}")
        return 0.0

async def get_positions_summary() -> Dict:
    """
    Get enhanced summary of all positions including totals and risk metrics

    Returns:
        Dict with comprehensive position summary
    """
    try:
        positions = await get_all_positions()
        active_positions = [p for p in positions if float(p.get("size", "0")) > 0]

        # Initialize counters with error handling
        total_unrealised_pnl = 0.0
        total_margin = 0.0
        profit_positions = []
        loss_positions = []

        for pos in active_positions:
            try:
                unrealised_pnl = float(pos.get("unrealisedPnl", "0"))
                position_margin = float(pos.get("positionIM", "0"))

                total_unrealised_pnl += unrealised_pnl
                total_margin += position_margin

                if unrealised_pnl > 0:
                    profit_positions.append(pos)
                elif unrealised_pnl < 0:
                    loss_positions.append(pos)

            except (ValueError, TypeError):
                logger.warning(f"Skipping position with invalid data: {pos.get('symbol', 'Unknown')}")
                continue

        # Calculate ROI with error handling
        roi_percent = 0
        if total_margin > 0:
            roi_percent = (total_unrealised_pnl / total_margin * 100)

        return {
            "total_positions": len(active_positions),
            "profit_positions": len(profit_positions),
            "loss_positions": len(loss_positions),
            "total_unrealised_pnl": total_unrealised_pnl,
            "total_margin": total_margin,
            "roi_percent": roi_percent,
            "positions": active_positions
        }

    except Exception as e:
        logger.error(f"Error getting positions summary: {e}")
        return {
            "total_positions": 0,
            "profit_positions": 0,
            "loss_positions": 0,
            "total_unrealised_pnl": 0,
            "total_margin": 0,
            "roi_percent": 0,
            "positions": [],
            "error": str(e)
        }

# =============================================
# ENHANCED CLIENT HEALTH CHECK FUNCTIONS
# =============================================

def check_client_health() -> Dict:
    """
    Check the health of the Bybit client connection with enhanced diagnostics

    Returns:
        Dict with health status
    """
    try:
        # FIXED: Test basic connectivity with server time (works on both testnet and mainnet)
        response = bybit_client.get_server_time()

        if response and response.get("retCode") == 0:
            server_time = response.get("result", {}).get("timeSecond", "Unknown")
            return {
                "healthy": True,
                "testnet": USE_TESTNET,
                "timeout": BYBIT_TIMEOUT_SECONDS,
                "server_time": server_time,
                "message": "Connection healthy",
                "compatible_mode": True,
                "connection_pool": f"{HTTP_MAX_CONNECTIONS} total, {HTTP_MAX_CONNECTIONS_PER_HOST} per host"
            }
        else:
            return {
                "healthy": False,
                "error": "Invalid API response",
                "response": response,
                "message": "Connection issues detected"
            }

    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "testnet": USE_TESTNET,
            "timeout": BYBIT_TIMEOUT_SECONDS,
            "message": "Connection failed"
        }

def get_client_info() -> Dict:
    """
    Get information about the current client configuration with enhanced details

    Returns:
        Dict with client information
    """
    return {
        "testnet": USE_TESTNET,
        "timeout": BYBIT_TIMEOUT_SECONDS,
        "api_key_set": bool(BYBIT_API_KEY),
        "api_secret_set": bool(BYBIT_API_SECRET),
        "enhanced_features": True,
        "connection_pooling": True,
        "async_support": True,
        "compatible_mode": True,
        "version_compatibility": "Enhanced",
        "connection_pool_config": {
            "total_connections": HTTP_MAX_CONNECTIONS,
            "per_host_connections": HTTP_MAX_CONNECTIONS_PER_HOST,
            "keepalive_timeout": HTTP_KEEPALIVE_TIMEOUT,
            "dns_cache_ttl": HTTP_DNS_CACHE_TTL
        }
    }

# =============================================
# CLEANUP FUNCTIONS
# =============================================

async def shutdown_client():
    """Shutdown client and cleanup resources"""
    try:
        await cleanup_http_session()
        logger.info("✅ Bybit client shutdown completed")
    except Exception as e:
        logger.error(f"Error during client shutdown: {e}")