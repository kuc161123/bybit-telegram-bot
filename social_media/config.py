#!/usr/bin/env python3
"""
Social Media Configuration
API credentials and rate limiting settings
"""
import os
from typing import Dict, Any, List

# Social Media API Configuration
SOCIAL_MEDIA_CONFIG = {
    # Reddit API (praw)
    "reddit": {
        "client_id": os.getenv("REDDIT_CLIENT_ID", ""),
        "client_secret": os.getenv("REDDIT_CLIENT_SECRET", ""),
        "user_agent": "CryptoSentimentBot/1.0",
        "enabled": bool(os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")),
        "requests_per_minute": 100,
        "cycle_budget": 2500,
        "target_subreddits": [
            "CryptoCurrency",
            "Bitcoin", 
            "ethereum",
            "altcoins",
            "CryptoMarkets"
        ]
    },
    
    # Twitter API v2
    "twitter": {
        "bearer_token": os.getenv("TWITTER_BEARER_TOKEN", ""),
        "api_key": os.getenv("TWITTER_API_KEY", ""),
        "enabled": bool(os.getenv("TWITTER_BEARER_TOKEN")),
        "posts_per_month": 1500,
        "posts_per_day": 50,
        "posts_per_cycle": 12,
        "target_accounts": [
            "elonmusk",
            "michael_saylor",
            "coinbureau",
            "altcoindaily",
            "PlanB_99",
            "APompliano",
            "VitalikButerin",
            "justinsuntron",
            "cz_binance",
            "BTC_Archive"
        ]
    },
    
    # YouTube Data API v3
    "youtube": {
        "api_key": os.getenv("YOUTUBE_API_KEY", ""),
        "enabled": bool(os.getenv("YOUTUBE_API_KEY") and os.getenv("YOUTUBE_API_KEY") != "your_youtube_api_key_here"),
        "units_per_day": 10000,
        "units_per_cycle": 2500,
        "target_channels": {
            "UCqK_GSMbpiV8spgD3ZGloSw": "Coin Bureau",
            "UCrYmtJBtLdtm2ov84ulV-yg": "Altcoin Daily", 
            "UCRvqjQPSeaWn-uEx-w0XOIg": "Benjamin Cowen",
            "UC4f8-6wuWXhqGaAHe3eVPKQ": "InvestAnswers",
            "UC0zGwzu0zzCImC1hjP0TKxg": "Crypto Zombie",
            "UCjemQfjaXAzA-95RKoy9n_g": "BitBoy Crypto",
            "UC-BhiXCUcTIaQ7rEd9b8uAQ": "The Modern Investor",
            "UCCatR7nWbYrkVXdxXb4cGXw": "DataDash",
            "UCrYmtJBtLdtm2ov84ulV-yg": "Ivan on Tech",
            "UC3RaY_-L0QvOvVbKzLkTGsg": "Crypto Banter"
        }
    },
    
    # Discord API
    "discord": {
        "bot_token": os.getenv("DISCORD_BOT_TOKEN", ""),
        "enabled": bool(os.getenv("DISCORD_BOT_TOKEN")),
        "requests_per_cycle": 500,
        "target_servers": {
            # These would need to be real server IDs with proper permissions
            # "123456789": "Crypto General",
            # "987654321": "Bitcoin Discussion", 
            # "456789123": "DeFi Community"
        },
        "demo_mode": True  # Enable demo mode if no bot token
    },
    
    # News/Market Data APIs
    "news_market": {
        "coingecko_base_url": "https://api.coingecko.com/api/v3",
        "alternative_me_fng_url": "https://api.alternative.me/fng/",
        "calls_per_cycle": 25,
        "target_cryptocurrencies": [
            "bitcoin", "ethereum", "binancecoin", "cardano", "solana",
            "polkadot", "chainlink", "litecoin", "avalanche-2", "polygon"
        ]
    }
}

# Rate Limiting Safety Settings
RATE_LIMIT_CONFIG = {
    "safety_margin": 0.8,  # Use only 80% of available limits
    "enable_quota_monitoring": True,
    "enable_emergency_mode": True,
    "circuit_breaker_threshold": 0.75,  # Stop at 75% quota usage
    "retry_delays": [1, 2, 4, 8, 16],  # Exponential backoff
    "max_retries": 3
}

# Collection Schedule Configuration
SCHEDULE_CONFIG = {
    "collection_interval_hours": 6,
    "collection_times_utc": [0, 6, 12, 18],  # 00:00, 06:00, 12:00, 18:00 UTC
    "maintenance_time_utc": 2,  # 02:00 UTC
    "cache_refresh_interval_minutes": 60,
    "api_monitoring_interval_minutes": 30
}

# Sentiment Analysis Configuration
SENTIMENT_CONFIG = {
    "minimum_confidence_threshold": 30,
    "minimum_items_per_platform": 3,
    "maximum_data_age_hours": 6,
    "platform_weights": {
        "reddit": 1.0,
        "twitter": 0.9,
        "youtube": 1.0,
        "discord": 0.7,
        "news_market": 1.2
    },
    "quality_thresholds": {
        "excellent": {"confidence": 80, "platforms": 4, "items": 100},
        "good": {"confidence": 60, "platforms": 3, "items": 50},
        "fair": {"confidence": 40, "platforms": 2, "items": 20},
        "limited": {"confidence": 20, "platforms": 1, "items": 5}
    }
}

# Cache Configuration
CACHE_CONFIG = {
    "cache_directory": "cache",
    "aggregated_sentiment_ttl": 1800,  # 30 minutes
    "platform_sentiments_ttl": 3600,   # 1 hour
    "collection_history_ttl": 86400,   # 24 hours
    "max_history_items": 24,            # Keep 24 collection cycles (6 days)
    "enable_memory_cache": True,
    "enable_file_cache": True
}

# Feature Flags
FEATURE_FLAGS = {
    "enable_social_sentiment": os.getenv("ENABLE_SOCIAL_SENTIMENT", "true").lower() == "true",
    "enable_openai_analysis": True,
    "enable_backup_analyzers": True,
    "enable_trending_detection": True,
    "enable_signal_generation": True,
    "enable_api_usage_monitoring": True,
    "enable_cache_persistence": True,
    "enable_scheduler": True
}

# Validation Functions
def validate_api_credentials() -> Dict[str, bool]:
    """Validate that required API credentials are configured"""
    credentials_status = {}
    
    # Reddit
    reddit_config = SOCIAL_MEDIA_CONFIG["reddit"]
    credentials_status["reddit"] = bool(
        reddit_config["client_id"] and reddit_config["client_secret"]
    )
    
    # Twitter
    twitter_config = SOCIAL_MEDIA_CONFIG["twitter"]
    credentials_status["twitter"] = bool(
        twitter_config["bearer_token"]
    )
    
    # YouTube
    youtube_config = SOCIAL_MEDIA_CONFIG["youtube"]
    credentials_status["youtube"] = bool(
        youtube_config["api_key"]
    )
    
    # Discord (optional)
    discord_config = SOCIAL_MEDIA_CONFIG["discord"]
    credentials_status["discord"] = bool(
        discord_config["bot_token"]
    ) or discord_config.get("demo_mode", False)
    
    # News/Market (no credentials required)
    credentials_status["news_market"] = True
    
    return credentials_status

def get_enabled_platforms() -> List[str]:
    """Get list of platforms with valid credentials"""
    if not FEATURE_FLAGS["enable_social_sentiment"]:
        return []
    
    credentials_status = validate_api_credentials()
    return [platform for platform, is_valid in credentials_status.items() if is_valid]

def get_configuration_summary() -> Dict[str, Any]:
    """Get summary of current configuration"""
    credentials_status = validate_api_credentials()
    enabled_platforms = get_enabled_platforms()
    
    return {
        "feature_enabled": FEATURE_FLAGS["enable_social_sentiment"],
        "credentials_configured": credentials_status,
        "enabled_platforms": enabled_platforms,
        "platforms_count": len(enabled_platforms),
        "collection_interval_hours": SCHEDULE_CONFIG["collection_interval_hours"],
        "openai_analysis_enabled": FEATURE_FLAGS["enable_openai_analysis"],
        "cache_enabled": FEATURE_FLAGS["enable_cache_persistence"],
        "scheduler_enabled": FEATURE_FLAGS["enable_scheduler"]
    }

# Environment Variable Documentation
REQUIRED_ENV_VARS = {
    "REDDIT_CLIENT_ID": "Reddit API client ID (required for Reddit sentiment)",
    "REDDIT_CLIENT_SECRET": "Reddit API client secret (required for Reddit sentiment)",
    "TWITTER_BEARER_TOKEN": "Twitter API v2 Bearer Token (required for Twitter sentiment)",
    "YOUTUBE_API_KEY": "YouTube Data API v3 key (required for YouTube sentiment)",
    "DISCORD_BOT_TOKEN": "Discord bot token (optional - demo mode available)",
    "ENABLE_SOCIAL_SENTIMENT": "Enable social media sentiment analysis (default: true)"
}

def print_configuration_help():
    """Print configuration help for environment variables"""
    print("\n📱 Social Media Sentiment Analysis Configuration")
    print("=" * 55)
    print("\nRequired Environment Variables:")
    
    for var_name, description in REQUIRED_ENV_VARS.items():
        current_value = "✅ Configured" if os.getenv(var_name) else "❌ Not set"
        print(f"  {var_name}")
        print(f"    Description: {description}")
        print(f"    Status: {current_value}")
        print()
    
    # Show configuration summary
    summary = get_configuration_summary()
    print("Current Configuration Summary:")
    print(f"  Feature Enabled: {'✅' if summary['feature_enabled'] else '❌'}")
    print(f"  Platforms Available: {summary['platforms_count']}/5")
    print(f"  Collection Interval: {summary['collection_interval_hours']} hours")
    print(f"  OpenAI Analysis: {'✅' if summary['openai_analysis_enabled'] else '❌'}")
    print()

if __name__ == "__main__":
    print_configuration_help()