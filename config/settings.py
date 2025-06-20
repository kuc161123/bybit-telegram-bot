#!/usr/bin/env python3
"""
Configuration and environment settings for the trading bot.
FIXED: Enhanced HTTP client configuration and connection management
ENHANCED: Better timeout and rate limiting settings
FIXED: Increased connection pool sizes to prevent "connection pool full" errors
"""
import os
import logging
from decimal import getcontext

# Set decimal precision for financial calculations
getcontext().prec = 28

# --- Optional: Load .env file ---
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded environment variables from .env file")
except ImportError:
    print("ℹ️ python-dotenv not installed, skipping .env file loading")

# --- Bot & Trade Configuration ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")
USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"
PERSISTENCE_FILE = os.getenv("PERSISTENCE_FILE", "bybit_bot_dashboard_v4.1_enhanced.pkl")

# --- Second Bybit Account (Mirror Trading) ---
ENABLE_MIRROR_TRADING = os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true"
BYBIT_API_KEY_2 = os.getenv("BYBIT_API_KEY_2")
BYBIT_API_SECRET_2 = os.getenv("BYBIT_API_SECRET_2")

# ENHANCED: HTTP Client Configuration - FIXED CONNECTION POOL LIMITS
BYBIT_TIMEOUT_SECONDS = int(os.getenv("BYBIT_TIMEOUT_SECONDS", "60"))  # Increased from 45
HTTP_MAX_CONNECTIONS = int(os.getenv("HTTP_MAX_CONNECTIONS", "300"))  # Increased for high monitoring load
HTTP_MAX_CONNECTIONS_PER_HOST = int(os.getenv("HTTP_MAX_CONNECTIONS_PER_HOST", "75"))  # Increased for high API usage
HTTP_KEEPALIVE_TIMEOUT = int(os.getenv("HTTP_KEEPALIVE_TIMEOUT", "60"))  # Increased from 30
HTTP_DNS_CACHE_TTL = int(os.getenv("HTTP_DNS_CACHE_TTL", "300"))  # DNS cache TTL

# --- AI RELATED CONFIG ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "stub").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- TELEGRAM MESSAGE LIMITS ---
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MESSAGE_BUFFER = 100
MAX_RETRIES = 3
RETRY_DELAY = 1

# --- CONVERSATION TIMEOUT ---
CONVERSATION_TIMEOUT_SECONDS = 300

# --- TRADING PARAMETERS ---
MONITOR_TP1_INTERVAL_SECONDS = 30
AUTO_MOVE_SL_TO_BE_AFTER_TP1 = True

# --- ENHANCED API RETRY AND TIMEOUT CONFIGURATION ---
API_RETRY_MAX_ATTEMPTS = int(os.getenv("API_RETRY_MAX_ATTEMPTS", "5"))  # Increased retries
API_RETRY_INITIAL_DELAY = float(os.getenv("API_RETRY_INITIAL_DELAY", "2.0"))  # Increased from 1.5
API_RETRY_BACKOFF_FACTOR = float(os.getenv("API_RETRY_BACKOFF_FACTOR", "2.0"))
API_DEFAULT_TIMEOUT = int(os.getenv("API_DEFAULT_TIMEOUT", "45"))  # Increased from 35
API_CONNECT_TIMEOUT = int(os.getenv("API_CONNECT_TIMEOUT", "20"))  # Increased from 15
API_READ_TIMEOUT = int(os.getenv("API_READ_TIMEOUT", "40"))  # Increased from 30

# --- ENHANCED ORDER CLEANUP CONFIGURATION ---
# Enable automatic cleanup of orphaned orders (orders without corresponding positions)
ENABLE_ORDER_CLEANUP = os.getenv("ENABLE_ORDER_CLEANUP", "true").lower() == "true"

# How often to run the cleanup check (in seconds) - increased for stability
ORDER_CLEANUP_INTERVAL_SECONDS = int(os.getenv("ORDER_CLEANUP_INTERVAL_SECONDS", "600"))  # 10 minutes

# Run cleanup on bot startup
ORDER_CLEANUP_ON_STARTUP = os.getenv("ORDER_CLEANUP_ON_STARTUP", "true").lower() == "true"

# Delay before first cleanup on startup (seconds) - increased for stability
ORDER_CLEANUP_STARTUP_DELAY = int(os.getenv("ORDER_CLEANUP_STARTUP_DELAY", "30"))  # 30 seconds

# --- ENHANCED MONITORING SETTINGS ---
POSITION_MONITOR_INTERVAL = int(os.getenv("POSITION_MONITOR_INTERVAL", "10"))  # Slightly increased from 8
POSITION_MONITOR_LOG_INTERVAL = int(os.getenv("POSITION_MONITOR_LOG_INTERVAL", "20"))  # Increased from 15

# --- ENHANCED RATE LIMITING SETTINGS ---
API_RATE_LIMIT_CALLS_PER_SECOND = float(os.getenv("API_RATE_LIMIT_CALLS_PER_SECOND", "5"))  # Reduced from 8
API_RATE_LIMIT_BURST = int(os.getenv("API_RATE_LIMIT_BURST", "10"))  # Reduced from 15
API_RATE_LIMIT_WINDOW = int(os.getenv("API_RATE_LIMIT_WINDOW", "60"))  # Rate limit window

# --- ENHANCED CONNECTION MANAGEMENT ---
CONNECTION_POOL_SIZE = int(os.getenv("CONNECTION_POOL_SIZE", "100"))  # Increased from 50
CONNECTION_POOL_MAXSIZE = int(os.getenv("CONNECTION_POOL_MAXSIZE", "20"))  # Increased from 10
CONNECTION_RETRY_TOTAL = int(os.getenv("CONNECTION_RETRY_TOTAL", "5"))  # Increased from 3
CONNECTION_RETRY_BACKOFF_FACTOR = float(os.getenv("CONNECTION_RETRY_BACKOFF_FACTOR", "0.5"))  # Increased from 0.3

# --- MEMORY AND PERFORMANCE SETTINGS ---
CACHE_DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "300"))  # 5 minutes default cache
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "1000"))  # Maximum cache entries
MEMORY_CLEANUP_INTERVAL = int(os.getenv("MEMORY_CLEANUP_INTERVAL", "3600"))  # 1 hour
MAX_CONCURRENT_MONITORS = int(os.getenv("MAX_CONCURRENT_MONITORS", "50"))  # Monitor limit

# --- ENHANCED ERROR HANDLING ---
ENABLE_CIRCUIT_BREAKER = os.getenv("ENABLE_CIRCUIT_BREAKER", "true").lower() == "true"
CIRCUIT_BREAKER_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = int(os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "60"))

# Validate required environment variables
def validate_config():
    """Enhanced configuration validation with detailed logging"""
    if not all([TELEGRAM_TOKEN, BYBIT_API_KEY, BYBIT_API_SECRET]):
        logging.error("❌ CRITICAL: Missing required environment variables")
        logging.error("   Required: TELEGRAM_TOKEN, BYBIT_API_KEY, BYBIT_API_SECRET")
        exit(1)
    
    # Validate numeric settings
    validations = [
        (BYBIT_TIMEOUT_SECONDS > 0, "BYBIT_TIMEOUT_SECONDS must be positive"),
        (API_RETRY_MAX_ATTEMPTS > 0, "API_RETRY_MAX_ATTEMPTS must be positive"), 
        (CONNECTION_POOL_SIZE > 0, "CONNECTION_POOL_SIZE must be positive"),
        (POSITION_MONITOR_INTERVAL > 0, "POSITION_MONITOR_INTERVAL must be positive")
    ]
    
    for is_valid, error_msg in validations:
        if not is_valid:
            logging.error(f"❌ Configuration error: {error_msg}")
            exit(1)
    
    # Log enhanced configuration
    logging.info("✅ Enhanced configuration validation passed")
    logging.info(f"📊 API Configuration:")
    logging.info(f"   Bybit Timeout: {BYBIT_TIMEOUT_SECONDS}s")
    logging.info(f"   API Default Timeout: {API_DEFAULT_TIMEOUT}s")
    logging.info(f"   Max Retry Attempts: {API_RETRY_MAX_ATTEMPTS}")
    logging.info(f"   Rate Limit: {API_RATE_LIMIT_CALLS_PER_SECOND} calls/sec")
    
    logging.info(f"🔗 Connection Configuration:")
    logging.info(f"   HTTP Pool Size: {HTTP_MAX_CONNECTIONS}")
    logging.info(f"   HTTP Max Per Host: {HTTP_MAX_CONNECTIONS_PER_HOST}")
    logging.info(f"   Connection Pool Size: {CONNECTION_POOL_SIZE}")
    logging.info(f"   Keep-alive: {HTTP_KEEPALIVE_TIMEOUT}s")
    
    logging.info(f"📊 Monitoring Configuration:")
    logging.info(f"   Monitor Interval: {POSITION_MONITOR_INTERVAL}s")
    logging.info(f"   Order Cleanup Enabled: {ENABLE_ORDER_CLEANUP}")
    logging.info(f"   Cleanup Interval: {ORDER_CLEANUP_INTERVAL_SECONDS}s")
    
    logging.info(f"🧠 Memory Configuration:")
    logging.info(f"   Cache Default TTL: {CACHE_DEFAULT_TTL}s")
    logging.info(f"   Max Cache Size: {CACHE_MAX_SIZE}")
    logging.info(f"   Max Concurrent Monitors: {MAX_CONCURRENT_MONITORS}")

# --- Enhanced Logging & Config ---
def setup_logging():
    """Setup enhanced logging configuration with better performance"""
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    simple_formatter = logging.Formatter(
        "%(levelname)s - %(message)s"
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler with simple format
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with detailed format and rotation
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            'trading_bot.log', 
            maxBytes=100*1024*1024,  # 100MB max size
            backupCount=5,  # Keep 5 backup files
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        logging.info("✅ File logging enabled with rotation: trading_bot.log (100MB max, 5 backups)")
    except Exception as e:
        logging.warning(f"⚠️ Could not setup file logging: {e}")
    
    # ENHANCED: Reduce noise from HTTP libraries and third-party modules
    noisy_loggers = [
        "httpx", 
        "urllib3.connectionpool",
        "urllib3.util.retry",
        "requests.packages.urllib3.connectionpool",
        "telegram.vendor.ptb_urllib3.urllib3",
        "telegram.ext.Application", 
        "telegram.ext.ExtBot",
        "telegram.bot", 
        "telegram.ext.Updater", 
        "telegram.ext.dispatcher",
        "telegram.ext.JobQueue",
        "openai._base_client", 
        "apscheduler.scheduler",
        "apscheduler.executors.default",
        "pybit.unified_trading",
        "pybit._http_manager",
        "aiohttp.access",
        "asyncio"
    ]
    
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)
    
    # Keep important loggers at INFO level
    important_loggers = [
        "execution.trader",
        "execution.monitor", 
        "clients.bybit_client",
        "clients.bybit_helpers",
        "handlers.conversation",
        "main"
    ]
    
    for logger_name in important_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
    
    # Log enhanced configuration
    logging.info("✅ Enhanced logging configuration applied")
    logging.info(f"📊 Performance Settings:")
    logging.info(f"   Timeout: Bybit={BYBIT_TIMEOUT_SECONDS}s, API={API_DEFAULT_TIMEOUT}s")
    logging.info(f"   HTTP Connections: Pool={HTTP_MAX_CONNECTIONS}, PerHost={HTTP_MAX_CONNECTIONS_PER_HOST}")
    logging.info(f"   Connection Pool: Size={CONNECTION_POOL_SIZE}, MaxSize={CONNECTION_POOL_MAXSIZE}")
    logging.info(f"   Rate Limiting: {API_RATE_LIMIT_CALLS_PER_SECOND} calls/sec")
    logging.info(f"   Circuit Breaker: {'Enabled' if ENABLE_CIRCUIT_BREAKER else 'Disabled'}")

def get_environment_info() -> dict:
    """Get comprehensive environment information for debugging"""
    return {
        "environment": "TESTNET" if USE_TESTNET else "MAINNET",
        "bybit_timeout": BYBIT_TIMEOUT_SECONDS,
        "api_timeout": API_DEFAULT_TIMEOUT,
        "retry_attempts": API_RETRY_MAX_ATTEMPTS,
        "http_max_connections": HTTP_MAX_CONNECTIONS,
        "http_connections_per_host": HTTP_MAX_CONNECTIONS_PER_HOST,
        "connection_pool_size": CONNECTION_POOL_SIZE,
        "rate_limit_per_second": API_RATE_LIMIT_CALLS_PER_SECOND,
        "order_cleanup_enabled": ENABLE_ORDER_CLEANUP,
        "cleanup_interval": ORDER_CLEANUP_INTERVAL_SECONDS,
        "monitor_interval": POSITION_MONITOR_INTERVAL,
        "cache_ttl": CACHE_DEFAULT_TTL,
        "circuit_breaker": ENABLE_CIRCUIT_BREAKER,
        "max_concurrent_monitors": MAX_CONCURRENT_MONITORS
    }