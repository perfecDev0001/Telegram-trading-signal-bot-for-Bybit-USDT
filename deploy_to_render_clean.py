#!/usr/bin/env python3
"""
Clean Render Deployment Script

This script helps you redeploy to Render cleanly after resolving conflicts.
"""

import sys
import os
import asyncio
import subprocess
import time
from config import Config

def check_environment():
    """Check if environment is ready for deployment"""
    print("🔍 Checking deployment environment...")
    
    issues = []
    
    # Check bot token
    if not Config.BOT_TOKEN or Config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        issues.append("❌ BOT_TOKEN not configured")
    else:
        print(f"✅ BOT_TOKEN: {Config.BOT_TOKEN[:10]}***")
    
    # Check admin ID
    if Config.ADMIN_ID == 0:
        issues.append("❌ ADMIN_ID not configured")
    else:
        print(f"✅ ADMIN_ID: {Config.ADMIN_ID}")
    
    # Check required files
    required_files = [
        'main.py', 'telegram_bot.py', 'config.py', 'requirements.txt',
        'render.yaml', 'start_render.py'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            issues.append(f"❌ Missing file: {file}")
    
    if issues:
        print("\n🚨 ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
        return False
    
    print("✅ Environment check passed!")
    return True

async def final_webhook_clear():
    """Final webhook clear before deployment"""
    try:
        import telegram
        
        print("🔄 Final webhook clearing...")
        bot = telegram.Bot(token=Config.BOT_TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhooks cleared for deployment")
        return True
    except Exception as e:
        print(f"⚠️ Webhook clear failed: {e}")
        return False

def create_deployment_guide():
    """Create a deployment guide"""
    guide = """
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
"""
    
    with open('DEPLOYMENT_GUIDE.md', 'w') as f:
        f.write(guide)
    
    print("📋 Deployment guide created: DEPLOYMENT_GUIDE.md")
    return guide

def main():
    """Main deployment preparation"""
    print("🚀 RENDER DEPLOYMENT PREPARATION")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        print("\n❌ Environment check failed")
        print("   Fix the issues above before deploying")
        sys.exit(1)
    
    # Final webhook clear
    print("\n🔄 Final preparation...")
    asyncio.run(final_webhook_clear())
    
    # Create deployment guide
    print("\n📋 Creating deployment guide...")
    guide = create_deployment_guide()
    
    print("\n✅ DEPLOYMENT READY!")
    print("=" * 50)
    print(guide)
    
    print("\n🎯 NEXT STEPS:")
    print("1. Read the DEPLOYMENT_GUIDE.md file")
    print("2. Commit and push your changes")
    print("3. Deploy to Render")
    print("4. Monitor the deployment logs")

if __name__ == "__main__":
    main()