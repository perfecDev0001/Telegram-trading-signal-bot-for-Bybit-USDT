# 🚀 RENDER DEPLOYMENT CHECKLIST

## ✅ Pre-Deployment (COMPLETED)
- [x] Bot conflicts resolved
- [x] Webhooks cleared
- [x] Code committed and pushed to GitHub
- [x] Environment validated

## 🌐 Render Dashboard Steps

### Step 1: Access Render Dashboard
1. Go to https://dashboard.render.com/
2. Log in to your account

### Step 2: Create or Update Service
**If creating a new service:**
1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Choose your repository: `Telegram-trading-signal-bot-for-Bybit-USDT`
4. Set branch: `main`

**If updating existing service:**
1. Go to your existing service
2. Click "Manual Deploy" or wait for auto-deploy

### Step 3: Configuration Settings
```
Name: bybit-scanner-bot
Environment: Python 3
Build Command: pip install -r requirements.txt
Start Command: python start_render.py
```

### Step 4: Environment Variables
Set these in the "Environment" tab:

**REQUIRED:**
- `BOT_TOKEN`: 7341495471:AAGnNL9XxxxxxxxxxxxxxxxxxxxxxxxDg
- `ADMIN_ID`: 7186880587

**OPTIONAL:**
- `CHANNEL_ID`: Your channel ID (0 to disable)
- `SUBSCRIBER_ID`: Default subscriber ID (0 to disable)

**SYSTEM (auto-configured):**
- `USE_PUBLIC_APIS_ONLY`: true
- `SCANNER_INTERVAL`: 60
- `PORT`: 8080
- `RENDER_SERVICE_NAME`: public-api-crypto-scanner

### Step 5: Deploy and Monitor

1. **Deploy:**
   - Click "Create Web Service" or "Manual Deploy"
   - Wait for deployment to complete

2. **Monitor Logs:**
   Look for these success messages:
   ```
   ✅ Bot started successfully
   ✅ Scanner started successfully
   ✅ Health check server running
   ```

3. **Test Service:**
   - Visit your service URL: `https://your-service-name.onrender.com`
   - Check health endpoint: `/health`
   - Test bot: Send `/start` to your bot

## 🔍 Troubleshooting

### If deployment fails:
1. Check the logs for error messages
2. Verify environment variables are set
3. Ensure your GitHub repository is connected

### If bot conflicts return:
1. Check you don't have local instances running
2. Verify only one Render service is active
3. Run the conflict resolution script again

### If bot doesn't respond:
1. Check the logs for "Bot started successfully"
2. Verify BOT_TOKEN and ADMIN_ID are correct
3. Send `/start` to test the bot

## 📊 Success Indicators

**Deployment Success:**
- ✅ Build completed without errors
- ✅ Service is "Live" in dashboard
- ✅ Health endpoint returns 200 OK
- ✅ Bot responds to `/start` command

**Runtime Success:**
- ✅ Scanner is running and finding signals
- ✅ No conflict errors in logs
- ✅ Memory usage under 512MB
- ✅ Service stays online

## 🎯 Post-Deployment

1. **Test the bot:**
   - Send `/start` to verify it's working
   - Try `/status` to check scanner status
   - Test `/scan` for manual scanning

2. **Monitor for 24 hours:**
   - Check logs periodically
   - Verify no conflicts occur
   - Ensure scanner is finding signals

3. **Set up monitoring:**
   - Bookmark your service URL
   - Set up alerts if needed
   - Document any issues

## 🚨 Emergency Procedures

**If conflicts return:**
1. Stop the Render service immediately
2. Run local conflict resolution script
3. Redeploy after conflicts are cleared

**If service crashes:**
1. Check logs for error messages
2. Verify environment variables
3. Restart the service

**If bot stops responding:**
1. Check service health endpoint
2. Restart the service
3. Clear webhooks if needed

---

## 📞 Support

If you encounter issues:
1. Check the logs first
2. Verify your environment variables
3. Ensure no local instances are running
4. Contact support if problems persist

**Service URL:** `https://your-service-name.onrender.com`
**Health Check:** `https://your-service-name.onrender.com/health`
**Status:** `https://your-service-name.onrender.com/status`