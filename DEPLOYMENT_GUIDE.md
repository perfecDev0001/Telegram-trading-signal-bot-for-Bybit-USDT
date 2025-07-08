
🚀 RENDER DEPLOYMENT GUIDE
=========================

✅ Your bot is ready for deployment!

STEP 1: Commit and push your code
---------------------------------
git add .
git commit -m "Fix: Resolved Telegram bot conflicts"
git push origin main

STEP 2: Deploy to Render
------------------------
1. Go to your Render dashboard
2. Find your service (or create a new one)
3. Connect your repository
4. Set the following environment variables:
   - BOT_TOKEN: Your bot token
   - ADMIN_ID: Your Telegram user ID
   - CHANNEL_ID: Your channel ID (optional)

STEP 3: Deploy settings
-----------------------
- Build Command: pip install -r requirements.txt
- Start Command: python start_render.py
- Environment: Python 3

STEP 4: Monitor deployment
--------------------------
- Check the logs for "✅ Bot started successfully"
- Visit your service URL to see health status
- Send /start to your bot to test

⚠️ IMPORTANT: Only run ONE instance at a time!
- Either run locally OR on Render, not both
- If you need to test locally, stop the Render service first
