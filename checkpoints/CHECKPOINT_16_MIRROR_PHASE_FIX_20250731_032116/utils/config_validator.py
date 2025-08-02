#!/usr/bin/env python3
"""
Configuration validation for the trading bot
Ensures all required settings are present and valid
"""
import os
import logging
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ConfigValidator:
    """Validates bot configuration on startup"""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def validate_all(self) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate all configuration

        Returns:
            tuple: (is_valid, messages_dict)
        """
        self.errors = []
        self.warnings = []
        self.info = []

        # Core validations
        self._validate_telegram_config()
        self._validate_bybit_config()
        self._validate_network_config()
        self._validate_optional_features()
        self._validate_file_permissions()

        return len(self.errors) == 0, {
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info
        }

    def _validate_telegram_config(self):
        """Validate Telegram configuration"""
        token = os.getenv("TELEGRAM_TOKEN")

        if not token:
            self.errors.append("TELEGRAM_TOKEN is not set")
            return

        # Basic token format validation
        if not token.count(':') == 1:
            self.errors.append("TELEGRAM_TOKEN format appears invalid")
            return

        bot_id, bot_hash = token.split(':')
        if not bot_id.isdigit():
            self.errors.append("TELEGRAM_TOKEN bot ID should be numeric")

        if len(bot_hash) < 20:
            self.warnings.append("TELEGRAM_TOKEN hash seems short")

    def _validate_bybit_config(self):
        """Validate Bybit configuration"""
        api_key = os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_API_SECRET")
        use_testnet = os.getenv("USE_TESTNET", "false").lower() == "true"

        if not api_key:
            self.errors.append("BYBIT_API_KEY is not set")
        elif len(api_key) < 20:
            self.warnings.append("BYBIT_API_KEY seems short")

        if not api_secret:
            self.errors.append("BYBIT_API_SECRET is not set")
        elif len(api_secret) < 20:
            self.warnings.append("BYBIT_API_SECRET seems short")

        if use_testnet:
            self.info.append("Using TESTNET environment")
        else:
            self.warnings.append("Using MAINNET environment - real money at risk!")

        # Check mirror trading config
        if os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true":
            api_key_2 = os.getenv("BYBIT_API_KEY_2")
            api_secret_2 = os.getenv("BYBIT_API_SECRET_2")

            if not api_key_2 or not api_secret_2:
                self.errors.append("Mirror trading enabled but BYBIT_API_KEY_2 or BYBIT_API_SECRET_2 not set")
            else:
                self.info.append("Mirror trading configuration validated")

    def _validate_network_config(self):
        """Validate network and performance settings"""
        timeout = os.getenv("BYBIT_TIMEOUT_SECONDS", "60")
        max_connections = os.getenv("HTTP_MAX_CONNECTIONS", "300")

        try:
            timeout_int = int(timeout)
            if timeout_int < 10:
                self.warnings.append(f"BYBIT_TIMEOUT_SECONDS ({timeout_int}) might be too low")
            elif timeout_int > 120:
                self.warnings.append(f"BYBIT_TIMEOUT_SECONDS ({timeout_int}) might be too high")
        except ValueError:
            self.errors.append(f"BYBIT_TIMEOUT_SECONDS must be numeric, got: {timeout}")

        try:
            connections_int = int(max_connections)
            if connections_int < 50:
                self.warnings.append(f"HTTP_MAX_CONNECTIONS ({connections_int}) might be too low for monitoring")
        except ValueError:
            self.errors.append(f"HTTP_MAX_CONNECTIONS must be numeric, got: {max_connections}")

    def _validate_optional_features(self):
        """Validate optional feature configuration"""
        # AI/OpenAI
        llm_provider = os.getenv("LLM_PROVIDER", "stub").lower()
        if llm_provider == "openai":
            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key:
                self.warnings.append("LLM_PROVIDER is 'openai' but OPENAI_API_KEY not set")
            else:
                self.info.append("OpenAI integration configured")

        # Social media sentiment
        if os.getenv("ENABLE_SOCIAL_SENTIMENT", "true").lower() == "true":
            social_keys = {
                "REDDIT_CLIENT_ID": "Reddit",
                "REDDIT_CLIENT_SECRET": "Reddit",
                "TWITTER_BEARER_TOKEN": "Twitter",
                "YOUTUBE_API_KEY": "YouTube"
            }

            configured = []
            for key, platform in social_keys.items():
                if os.getenv(key):
                    configured.append(platform)

            if configured:
                self.info.append(f"Social sentiment configured for: {', '.join(configured)}")
            else:
                self.info.append("Social sentiment enabled but no API keys configured")

    def _validate_file_permissions(self):
        """Validate file permissions and paths"""
        persistence_file = os.getenv("PERSISTENCE_FILE", "bybit_bot_dashboard_v4.1_enhanced.pkl")

        # Check if we can write to the directory
        directory = os.path.dirname(persistence_file) or "."
        if not os.access(directory, os.W_OK):
            self.errors.append(f"Cannot write to persistence directory: {directory}")

        # Check log file permissions
        log_file = "trading_bot.log"
        log_dir = os.path.dirname(log_file) or "."
        if not os.access(log_dir, os.W_OK):
            self.warnings.append(f"Cannot write to log directory: {log_dir}")

def validate_configuration() -> bool:
    """
    Validate configuration on startup

    Returns:
        bool: True if configuration is valid
    """
    validator = ConfigValidator()
    is_valid, messages = validator.validate_all()

    # Log results
    for error in messages['errors']:
        logger.error(f"Config Error: {error}")

    for warning in messages['warnings']:
        logger.warning(f"Config Warning: {warning}")

    for info in messages['info']:
        logger.info(f"Config Info: {info}")

    if not is_valid:
        logger.error("Configuration validation failed!")
        logger.error("Please check your environment variables and fix the errors above.")
    else:
        logger.info("✅ Configuration validation passed")

    return is_valid

def get_configuration_summary() -> Dict[str, Any]:
    """Get configuration summary for logging"""
    return {
        'environment': 'TESTNET' if os.getenv("USE_TESTNET", "false").lower() == "true" else "MAINNET",
        'features': {
            'mirror_trading': os.getenv("ENABLE_MIRROR_TRADING", "false").lower() == "true",
            'social_sentiment': os.getenv("ENABLE_SOCIAL_SENTIMENT", "true").lower() == "true",
            'ai_enabled': os.getenv("LLM_PROVIDER", "stub").lower() != "stub"
        },
        'performance': {
            'timeout': int(os.getenv("BYBIT_TIMEOUT_SECONDS", "60")),
            'max_connections': int(os.getenv("HTTP_MAX_CONNECTIONS", "300")),
            'cache_ttl': int(os.getenv("CACHE_DEFAULT_TTL", "300"))
        }
    }