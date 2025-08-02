# 🚀 ONE-CLICK DEPLOY - Bybit Telegram Bot

Deploy your sophisticated trading bot to the cloud in just **2 minutes** with one click!

## 🎯 **INSTANT DEPLOYMENT OPTIONS**

### ⚡ **Option 1: Railway (Easiest - $5/month)**
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/bybit-telegram-bot)

**Steps:**
1. Click the Railway button above
2. Sign in with GitHub 
3. Enter your API keys in the form
4. Click "Deploy" - Done! ✅

---

### 🛡️ **Option 2: Render (Most Reliable - $7/month)**  
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

**Steps:**
1. Click the Render button above
2. Connect your GitHub account
3. Enter your API keys
4. Deploy automatically! ✅

---

### 🏢 **Option 3: Heroku (Industry Standard - $7/month)**
[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

**Steps:**
1. Click the Heroku button above  
2. Create Heroku account if needed
3. Fill in environment variables
4. Deploy with one click! ✅

---

### ☁️ **Option 4: Google Cloud Run (Enterprise - Pay-per-use)**
[![Run on Google Cloud](https://deploy.cloud.run/button.svg)](https://console.cloud.google.com/cloudshell/editor?shellonly=true&cloudshell_git_repo=https://github.com/YOUR_USERNAME/bybit-telegram-bot)

**Steps:**
1. Click the Google Cloud button above
2. Authorize Google Cloud Shell
3. Run deployment command
4. Set environment variables ✅

---

## 🔐 **REQUIRED API KEYS** 

### **Essential (Bot won't work without these):**
- **TELEGRAM_TOKEN** - Get from [@BotFather](https://t.me/BotFather) on Telegram
- **BYBIT_API_KEY** - Create at [Bybit API Management](https://www.bybit.com/app/user/api-management) 
- **BYBIT_API_SECRET** - From same Bybit API page

### **Recommended:**
- **OPENAI_API_KEY** - Get from [OpenAI](https://platform.openai.com/api-keys) for AI features

### **Optional (Advanced):**
- **BYBIT_API_KEY_2** / **BYBIT_API_SECRET_2** - Second account for mirror trading
- **REDDIT_CLIENT_ID** / **REDDIT_CLIENT_SECRET** - For Reddit sentiment
- **TWITTER_BEARER_TOKEN** - For Twitter sentiment

---

## 📱 **GETTING YOUR API KEYS**

### 1️⃣ **Telegram Bot Token**
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose bot name and username
4. Copy the token (format: `123456789:ABCDEF...`)

### 2️⃣ **Bybit API Keys**
1. Go to [Bybit API Management](https://www.bybit.com/app/user/api-management)
2. Click "Create New Key"
3. **Permissions needed:**
   - ✅ Read-Write  
   - ✅ Derivatives (for futures)
   - ✅ No IP restriction (for cloud)
4. Save API Key and Secret immediately!

### 3️⃣ **OpenAI API Key (Optional)**
1. Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
2. Click "Create new secret key"
3. Copy the key (format: `sk-...`)

---

## ✅ **DEPLOYMENT VERIFICATION**

After deployment, your bot will:
1. **Start automatically** in the cloud
2. **Be available 24/7** at a public URL
3. **Health check endpoint** at `/health`
4. **Ready for trading** - message on Telegram with `/start`

### **Check if it's working:**
```bash
# Replace YOUR-APP-URL with your actual deployment URL
curl https://YOUR-APP-URL.railway.app/health
```

Should return:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00",
  "pickle_file_exists": true,
  "bot_uptime": "running"
}
```

---

## 🎉 **THAT'S IT!**

Your bot is now running 24/7 in the cloud! 

**Next steps:**
1. Open Telegram
2. Find your bot by username
3. Send `/start`
4. Begin trading! 📈

---

## 🔧 **TROUBLESHOOTING**

### **Bot not responding on Telegram:**
- Check environment variables are set correctly
- Verify TELEGRAM_TOKEN is valid
- Check deployment logs for errors

### **API errors:**
- Verify Bybit API keys have correct permissions
- Ensure no IP restrictions on API keys
- Check API key is for the right account (live vs testnet)

### **Need help?**
- Check deployment logs in your platform dashboard
- Verify all required environment variables are set
- Ensure bot username is correct in Telegram

---

## 💰 **COSTS SUMMARY**

| Platform | Cost | Best For |
|----------|------|----------|
| Railway | $5/month | Beginners |
| Render | $7/month | Reliability |  
| Heroku | $7/month | Standard |
| Google Cloud | $5-15/month | Enterprise |

All platforms include:
- ✅ 24/7 uptime
- ✅ Automatic restarts
- ✅ SSL certificates
- ✅ Health monitoring
- ✅ Log access

**Your sophisticated trading bot is now online! 🚀**