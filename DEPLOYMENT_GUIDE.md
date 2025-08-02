# 🚀 Cloud Deployment Guide

This guide will help you deploy your Bybit Telegram bot to run 100% online.

## 🎯 Quick Deploy Options

### Option 1: Railway (Easiest - $5/month)

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Add cloud deployment files"
   git push origin main
   ```

2. **Deploy to Railway**:
   - Go to [railway.app](https://railway.app)
   - Sign up with GitHub
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository
   - Railway will automatically detect `railway.json` and deploy

3. **Set Environment Variables**:
   - In Railway dashboard, go to your project
   - Click "Variables" tab
   - Add these required variables:
   ```
   TELEGRAM_TOKEN=your_telegram_bot_token
   BYBIT_API_KEY=your_bybit_api_key  
   BYBIT_API_SECRET=your_bybit_api_secret
   USE_TESTNET=false
   OPENAI_API_KEY=your_openai_api_key
   ```

### Option 2: Render (Most Reliable - $7/month)

1. **Push to GitHub** (same as above)

2. **Deploy to Render**:
   - Go to [render.com](https://render.com)
   - Sign up with GitHub
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Render will detect `render.yaml` automatically

3. **Environment Variables**: Set in Render dashboard

### Option 3: Google Cloud Run (Most Scalable)

1. **Install Google Cloud CLI**:
   ```bash
   curl https://sdk.cloud.google.com | bash
   gcloud init
   ```

2. **Deploy**:
   ```bash
   gcloud run deploy bybit-bot --source . --region us-central1
   ```

3. **Set Environment Variables**:
   ```bash
   gcloud run services update bybit-bot \
     --set-env-vars TELEGRAM_TOKEN=your_token,BYBIT_API_KEY=your_key
   ```

### Option 4: Digital Ocean App Platform

1. **Push to GitHub** (same as above)
2. **Connect to Digital Ocean Apps**
3. **Auto-detects Dockerfile and deploys**

## 🔐 Required Environment Variables

### Essential (Required for bot to work):
```bash
TELEGRAM_TOKEN=your_telegram_bot_token_here
BYBIT_API_KEY=your_bybit_api_key_here  
BYBIT_API_SECRET=your_bybit_api_secret_here
USE_TESTNET=false
```

### AI Features (Recommended):
```bash
OPENAI_API_KEY=your_openai_api_key_here
LLM_PROVIDER=openai
ENABLE_GPT4_REASONING=true
```

### Mirror Trading (Optional):
```bash
BYBIT_API_KEY_2=your_second_account_api_key
BYBIT_API_SECRET_2=your_second_account_api_secret
```

### Social Media APIs (Optional):
```bash
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
YOUTUBE_API_KEY=your_youtube_api_key
```

## 📱 Getting API Keys

### 1. Telegram Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Follow instructions to create your bot
4. Save the token (format: `123456789:ABCDEF...`)

### 2. Bybit API Keys
1. Go to [Bybit API Management](https://www.bybit.com/app/user/api-management)
2. Create new API key with permissions:
   - ✅ Read-Write
   - ✅ Derivatives (for futures trading)
   - ✅ No IP restriction (for cloud deployment)
3. Save API Key and Secret immediately

### 3. OpenAI API Key (Optional but Recommended)
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Create new secret key
3. Save the key (format: `sk-...`)

## 🔍 Verifying Deployment

1. **Check Health Endpoint**:
   ```bash
   curl https://your-app-url.railway.app/health
   ```

2. **Check Logs**:
   - Railway: Dashboard → "Deployments" → "View Logs"
   - Render: Dashboard → "Logs"
   - Google Cloud: `gcloud run logs tail bybit-bot`

3. **Test Bot**:
   - Message your bot on Telegram with `/start`
   - Should respond with trading interface

## 🛠️ Troubleshooting

### Bot Not Responding
- Check environment variables are set correctly
- Verify Telegram token is valid
- Check logs for errors

### API Connection Issues
- Verify Bybit API keys are correct
- Check API key permissions include derivatives trading
- Ensure no IP restrictions on API keys

### Memory/Performance Issues
- Bot is optimized for cloud deployment
- Uses connection pooling and caching
- Monitor resource usage in platform dashboard

## 💰 Cost Estimates

| Platform | Monthly Cost | Features |
|----------|-------------|----------|
| Railway | $5 | 512MB RAM, automatic deployments |
| Render | $7 | 512MB RAM, health checks, better uptime |
| Digital Ocean | $5-12 | Scalable resources |
| Google Cloud Run | $5-15 | Pay-per-use, enterprise grade |

## 🔒 Security Best Practices

1. **Never commit API keys to Git**
2. **Use environment variables for all secrets**
3. **Enable 2FA on all accounts**
4. **Regularly rotate API keys**
5. **Monitor API usage for unusual activity**

## 📊 Monitoring Your Bot

- **Health Check**: Available at `/health` endpoint
- **Logs**: Real-time logs in platform dashboard
- **Telegram**: Bot sends alerts for all trading activities
- **Performance**: Monitor CPU/memory usage in platform

Your bot will now run 24/7 in the cloud! 🎉