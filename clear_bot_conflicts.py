#!/usr/bin/env python3
"""
Bot Conflict Resolution Utility

This script helps resolve Telegram bot conflicts by:
1. Clearing any existing webhooks
2. Dropping pending updates
3. Testing bot connectivity

Run this script if you're experiencing "409 Conflict" errors.
"""

import asyncio
import sys
from telegram import Bot
from config import Config

async def clear_bot_conflicts():
    """Clear bot conflicts and test connectivity"""
    print("🔧 Bot Conflict Resolution Utility")
    print("=" * 50)
    
    try:
        # Initialize bot
        print("🤖 Initializing bot...")
        bot = Bot(token=Config.BOT_TOKEN)
        
        # Test bot connection
        print("🔍 Testing bot connection...")
        bot_info = await bot.get_me()
        print(f"✅ Bot connected: @{bot_info.username} ({bot_info.first_name})")
        
        # Clear webhooks
        print("🧹 Clearing webhooks...")
        webhook_info = await bot.get_webhook_info()
        
        if webhook_info.url:
            print(f"   Found webhook: {webhook_info.url}")
            await bot.delete_webhook(drop_pending_updates=True)
            print("✅ Webhook cleared and pending updates dropped")
        else:
            print("   No webhook found")
            # Still drop pending updates
            await bot.delete_webhook(drop_pending_updates=True)
            print("✅ Pending updates dropped")
        
        # Test polling capability
        print("📡 Testing polling capability...")
        try:
            updates = await bot.get_updates(limit=1, timeout=5)
            print(f"✅ Polling test successful (received {len(updates)} updates)")
        except Exception as e:
            if "409" in str(e) or "Conflict" in str(e):
                print(f"❌ Polling conflict still exists: {e}")
                print("💡 Suggestion: Wait a few minutes and try again, or check for other running instances")
                return False
            else:
                print(f"⚠️ Polling test warning: {e}")
        
        print("\n✅ Bot conflict resolution completed successfully!")
        print("🚀 You can now start your bot normally")
        return True
        
    except Exception as e:
        print(f"❌ Error during conflict resolution: {e}")
        return False

async def main():
    """Main function"""
    success = await clear_bot_conflicts()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())