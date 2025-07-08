#!/usr/bin/env python3
"""
Render Deployment Script

This script prepares the bot for deployment to Render and prevents conflicts.
"""

import asyncio
import sys
import os
import subprocess
import time

def check_files():
    """Check if required files exist"""
    required_files = [
        'main.py',
        'start_render.py',
        'Procfile',
        'render.yaml',
        'requirements.txt',
        'config.py',
        'telegram_bot.py',
        '.env'
    ]
    
    missing = []
    for file in required_files:
        if not os.path.exists(file):
            missing.append(file)
    
    if missing:
        print(f"❌ Missing required files: {', '.join(missing)}")
        return False
    
    print("✅ All required files present")
    return True

def check_configuration():
    """Check configuration"""
    try:
        from config import Config
        
        issues = []
        
        if not Config.BOT_TOKEN or Config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            issues.append("BOT_TOKEN not configured")
        
        if Config.ADMIN_ID == 0:
            issues.append("ADMIN_ID not configured")
        
        if issues:
            print("❌ Configuration issues:")
            for issue in issues:
                print(f"  - {issue}")
            return False
        
        print("✅ Configuration OK")
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

async def clear_bot_webhook():
    """Clear any existing bot webhook"""
    try:
        from config import Config
        import telegram
        
        print("🔄 Clearing bot webhook...")
        
        bot = telegram.Bot(token=Config.BOT_TOKEN)
        await bot.delete_webhook(drop_pending_updates=True)
        
        print("✅ Bot webhook cleared")
        return True
        
    except Exception as e:
        print(f"⚠️ Could not clear webhook: {e}")
        return False

def main():
    """Main deployment preparation"""
    print("🚀 Render Deployment Preparation")
    print("=" * 50)
    
    # Check files
    if not check_files():
        print("❌ Deployment preparation failed")
        sys.exit(1)
    
    # Check configuration
    if not check_configuration():
        print("❌ Deployment preparation failed")
        sys.exit(1)
    
    # Clear webhook
    try:
        asyncio.run(clear_bot_webhook())
    except Exception as e:
        print(f"⚠️ Webhook clearing failed: {e}")
        print("🔄 Continuing anyway...")
    
    print("\n✅ Deployment preparation complete!")
    print("\n📋 Next steps:")
    print("1. Commit and push your changes to GitHub")
    print("2. Deploy on Render using the GitHub connection")
    print("3. Make sure environment variables are set in Render dashboard:")
    print("   - BOT_TOKEN")
    print("   - ADMIN_ID")
    print("   - CHANNEL_ID")
    print("4. Monitor the deployment logs for any issues")
    
    print("\n🔧 Render Configuration:")
    print("- Build Command: pip install -r requirements.txt")
    print("- Start Command: python start_render.py")
    print("- Environment: Python 3")
    print("- Service Type: Web Service")

if __name__ == "__main__":
    main()