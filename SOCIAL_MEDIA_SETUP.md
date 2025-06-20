# Social Media Sentiment Analysis Setup Guide

## Overview

The trading bot now includes a comprehensive social media sentiment analysis system that monitors multiple platforms to provide market intelligence. This system collects data every 6 hours and integrates seamlessly with the existing AI insights.

## Features

- **Multi-Platform Data Collection**: Reddit, Twitter, YouTube, Discord, News/Market Data
- **Advanced Sentiment Analysis**: OpenAI integration with VADER and TextBlob fallbacks
- **6-Hour Collection Cycles**: Optimized for free API tier limits
- **Trend Detection**: Identifies emerging trends and market signals
- **Professional Dashboard Integration**: Rich sentiment display in the bot dashboard
- **Caching & Storage**: High-performance data management
- **Automated Scheduling**: Background collection with APScheduler

## Quick Start

### 1. Environment Setup

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your API credentials (optional platforms):
```bash
# Social Media Sentiment Analysis (OPTIONAL)
ENABLE_SOCIAL_SENTIMENT=true

# Reddit API (OPTIONAL)
REDDIT_CLIENT_ID=your_reddit_client_id_here
REDDIT_CLIENT_SECRET=your_reddit_client_secret_here

# Twitter API v2 (OPTIONAL)
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here

# YouTube Data API v3 (OPTIONAL)
YOUTUBE_API_KEY=your_youtube_api_key_here

# Discord Bot (OPTIONAL)
DISCORD_BOT_TOKEN=your_discord_bot_token_here
```

### 2. Setup and Test

Run the interactive setup script:
```bash
python setup_social_sentiment.py
```

This will:
- Check your configuration
- Test API connections
- Run a manual collection cycle
- Show API setup instructions

### 3. Start the Bot

The social media sentiment system will automatically start with the bot:
```bash
python main.py
```

## API Setup Instructions

### Reddit API (Free)
1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Choose "script" application type
4. Copy the client ID and secret
5. Add to .env: `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`

### Twitter API v2 (Free Tier: 1,500 posts/month)
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Create a new project/app
3. Generate Bearer Token
4. Add to .env: `TWITTER_BEARER_TOKEN`

### YouTube Data API v3 (Free: 10,000 units/day)
1. Go to https://console.developers.google.com/
2. Create a new project or select existing
3. Enable YouTube Data API v3
4. Create credentials (API Key)
5. Add to .env: `YOUTUBE_API_KEY`

### Discord Bot (Optional)
1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to Bot section and create bot
4. Copy the bot token
5. Add to .env: `DISCORD_BOT_TOKEN`

## How It Works

### Collection Cycle (Every 6 Hours)
- **00:00, 06:00, 12:00, 18:00 UTC**: Automated collection
- **Rate Limit Optimization**: Uses only a fraction of free API limits
- **Concurrent Collection**: All platforms collected simultaneously
- **Error Handling**: Graceful fallbacks and retry logic

### Sentiment Analysis Pipeline
1. **Data Collection**: Platform-specific collectors gather relevant content
2. **Content Filtering**: Crypto-relevant content identification
3. **Sentiment Analysis**: OpenAI GPT analysis with fallbacks
4. **Aggregation**: Multi-platform sentiment scoring
5. **Signal Generation**: Trading signals and market condition analysis
6. **Caching**: Fast access for dashboard integration

### Dashboard Integration
The sentiment data appears in the enhanced AI insights section:
- **Overall Sentiment**: Aggregated market mood
- **Platform Breakdown**: Individual platform analysis
- **Trending Topics**: Emerging trends and keywords
- **Trading Signals**: Generated recommendations
- **Market Conditions**: FOMO, fear, and volatility indicators

## Usage Limits (Free Tiers)

### Conservative API Usage
- **Reddit**: 2,500/cycle vs 36,000 available (7% usage)
- **Twitter**: 12 posts/cycle vs 50 daily (24% daily quota)
- **YouTube**: 2,500 units/cycle vs 10,000 daily (25% daily quota)
- **Discord**: 500 requests/cycle (minimal usage)
- **News/Market**: 25 calls/cycle (CoinGecko free tier)

### Built-in Safety Features
- **Circuit Breakers**: Automatic stop at 75% quota usage
- **Rate Limiting**: Conservative request patterns
- **Usage Monitoring**: Real-time API usage tracking
- **Graceful Degradation**: System works with partial data

## System Requirements

### Dependencies
All required packages are in `requirements.txt`:
```bash
pip install -r requirements.txt
```

Key new dependencies:
- `praw` - Reddit API
- `tweepy` - Twitter API v2
- `google-api-python-client` - YouTube API
- `discord.py` - Discord API
- `textblob` - Sentiment analysis
- `vaderSentiment` - Social media sentiment analysis

### Storage
- **Cache Directory**: `cache/` (auto-created)
- **Historical Data**: Configurable retention periods
- **Memory Usage**: Optimized with TTL caching

## Configuration Options

### Feature Flags (social_media/config.py)
```python
FEATURE_FLAGS = {
    "enable_social_sentiment": True,    # Master enable/disable
    "enable_openai_analysis": True,     # Use OpenAI for analysis
    "enable_backup_analyzers": True,    # VADER/TextBlob fallbacks
    "enable_trending_detection": True,  # Trend analysis
    "enable_signal_generation": True,   # Trading signals
    "enable_scheduler": True            # Automated collection
}
```

### Rate Limiting
```python
RATE_LIMIT_CONFIG = {
    "safety_margin": 0.8,              # Use 80% of limits
    "circuit_breaker_threshold": 0.75,  # Stop at 75%
    "retry_delays": [1, 2, 4, 8, 16],  # Exponential backoff
    "max_retries": 3
}
```

## Monitoring & Maintenance

### System Status
Check system status anytime:
```python
from social_media.integration import get_sentiment_system_status
status = get_sentiment_system_status()
```

### Manual Collection
Trigger manual collection:
```python
from social_media.integration import trigger_sentiment_collection
result = await trigger_sentiment_collection()
```

### Logs
Monitor the bot logs for sentiment collection activities:
```
📱 Social media sentiment analysis initialized
🎯 Starting scheduled sentiment collection cycle...
✅ Sentiment collection completed and cached successfully
```

## Troubleshooting

### Common Issues

1. **No platforms enabled**: Configure at least one API credential
2. **Rate limit exceeded**: Check usage monitoring, wait for reset
3. **Import errors**: Ensure all dependencies installed
4. **Cache issues**: Clear cache directory if needed

### Debug Mode
Enable detailed logging by setting log level to DEBUG in your environment.

### Support Commands
```bash
# Test configuration
python setup_social_sentiment.py

# Check system status
python -c "from social_media.config import print_configuration_help; print_configuration_help()"

# Manual collection test
python -c "import asyncio; from social_media.integration import trigger_sentiment_collection; asyncio.run(trigger_sentiment_collection())"
```

## Security & Privacy

- **No Personal Data**: Only public social media content analyzed
- **API Rate Limits**: Respectful usage of all platforms
- **Local Storage**: All data stored locally, not shared
- **Optional Feature**: Can be completely disabled

## Performance Impact

- **Minimal CPU Usage**: Background collection only
- **Low Memory Footprint**: Efficient caching system
- **No Trading Interference**: Read-only market intelligence
- **Dashboard Enhancement**: Enriches existing AI insights

---

The social media sentiment analysis system provides valuable market intelligence while maintaining responsible API usage and system performance. It enhances trading decisions with real-time social sentiment data from multiple platforms.