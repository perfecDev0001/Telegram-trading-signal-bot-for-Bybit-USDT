#!/usr/bin/env python3
"""
Clear Telegram Bot Webhook Script

This script clears any existing webhooks to prevent conflicts.
"""

import asyncio
import sys
import os
from config import Config

async def clear_webhook():
    """Clear any existing webhook"""
    try:
        import telegram
        
        print("🔄 Clearing existing webhooks...")
        
        # Create bot instance
        bot = telegram.Bot(token=Config.BOT_TOKEN)
        
        # Clear webhook
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook cleared successfully")
        
        # Get bot info to verify connection
        bot_info = await bot.get_me()
        print(f"✅ Bot connected: @{bot_info.username}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to clear webhook: {e}")
        return False

async def main():
    """Main function"""
    print("🤖 Telegram Bot Webhook Cleaner")
    print("=" * 40)
    
    if await clear_webhook():
        print("✅ Webhook cleared successfully")
    else:
        print("❌ Failed to clear webhook")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())