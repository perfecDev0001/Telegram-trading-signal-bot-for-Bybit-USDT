# 🚀 Render.com Deployment Guide

## Pre-Deployment Checklist ✅

Before deploying to Render, ensure you have:

1. **Telegram Bot Token** - Get from [@BotFather](https://t.me/botfather)
2. **Admin Telegram ID** - Your Telegram user ID (7974254350)
3. **Bybit API Key** - From Bybit API settings (1Lf8RrbAZwhGz42UNY)
4. **Bybit Secret Key** - If required by your API setup

## Step-by-Step Deployment 📋

### 1. Connect Repository to Render
1. Go to [render.com](https://render.com) and sign up/login
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Select this repository: `Bybit_Scanner_Bot`

### 2. Configure Build Settings
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py`
- **Instance Type**: `Starter` (Free tier)

### 3. Set Environment Variables
Add these environment variables in Render dashboard:

**Required Variables:**
```
BOT_TOKEN = your_telegram_bot_token_here (from @BotFather)
ADMIN_ID = 7974254350
BYBIT_API_KEY = 1Lf8RrbAZwhGz42UNY
```

**Optional Variables:**
```
BYBIT_SECRET = your_bybit_secret_if_needed
SCANNER_INTERVAL = 60
PUMP_THRESHOLD = 5.0
DUMP_THRESHOLD = -5.0
BREAKOUT_THRESHOLD = 3.0
DATABASE_PATH = ./bot_data.db
```

### 4. Deploy
1. Click "Deploy Web Service"
2. Wait for build to complete (5-10 minutes)
3. Monitor logs for any errors

## Post-Deployment Verification 🧪

### 1. Check Logs
Monitor the Render logs for:
- ✅ "Bot initialized successfully"
- ✅ "Database initialized"
- ✅ "Scanner started"

### 2. Test Bot
1. Send `/start` to your bot on Telegram
2. You should receive the admin panel
3. Test with "📊 Scanner Status" button

### 3. Verify Scanning
- Check logs for market scanning activity
- Look for "🔍 Scanning X markets..." messages

## Troubleshooting Common Issues 🔧

### Build Fails
```
Error: No module named 'telegram'
```
**Solution**: Check requirements.txt is properly formatted

### Bot Not Responding
```
Error: Unauthorized (401)
```
**Solution**: Verify BOT_TOKEN is correct

### API Connection Failed
```
Error: Bybit API 403 Forbidden
```
**Solution**: 
- Check BYBIT_API_KEY is correct
- Add BYBIT_SECRET if required
- Bot will still work for testing without API

### Database Issues
```
Error: Cannot create database
```
**Solution**: Check DATABASE_PATH environment variable

## Environment Variables Reference 📝

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| BOT_TOKEN | ✅ | - | Telegram bot token from @BotFather |
| ADMIN_ID | ✅ | - | Your Telegram user ID |
| BYBIT_API_KEY | ✅ | - | Bybit API key for market data |
| BYBIT_SECRET | ⚠️ | - | Bybit secret (if required) |
| SCANNER_INTERVAL | ❌ | 60 | Scan interval in seconds |
| PUMP_THRESHOLD | ❌ | 5.0 | Pump detection threshold % |
| DUMP_THRESHOLD | ❌ | -5.0 | Dump detection threshold % |
| BREAKOUT_THRESHOLD | ❌ | 3.0 | Breakout detection threshold % |
| DATABASE_PATH | ❌ | ./bot_data.db | SQLite database path |

## Success Indicators 🎉

Your deployment is successful when you see:

1. **Build Logs**: No errors, all dependencies installed
2. **Deploy Logs**: 
   ```
   🚀 Bybit Scanner Bot Starting...
   📊 Database initialized successfully
   🤖 Bot initialized successfully
   🔍 Scanner started - monitoring X markets
   ```
3. **Telegram Bot**: Responds to `/start` command
4. **Admin Panel**: All buttons work correctly

## Next Steps After Deployment 📈

1. **Monitor Performance**: Check logs regularly
2. **Add Users**: Use admin panel to add subscribers
3. **Configure Settings**: Adjust thresholds via admin panel
4. **Set Alerts**: Configure signal recipients

## Support 💬

If you encounter issues:
1. Check Render logs first
2. Verify all environment variables are set
3. Test locally with `python setup_verification.py`
4. Ensure all required files are in repository

---

**🎯 Deployment Status: Ready for Production**