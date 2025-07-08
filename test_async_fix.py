#!/usr/bin/env python3
"""
Test script to verify async/await fixes for the Telegram bot
"""
import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import TelegramBot
from config import Config

async def test_bot_initialization():
    """Test that the bot can be initialized without async/await errors"""
    try:
        print("🔍 Testing bot initialization...")
        bot = TelegramBot()
        print("✅ Bot initialized successfully")
        
        # Test that the bot can be started
        print("🚀 Testing bot start...")
        success = await bot.start_bot()
        
        if success:
            print("✅ Bot started successfully")
            
            # Let it run for a few seconds to catch any immediate errors
            await asyncio.sleep(3)
            
            print("🛑 Stopping bot...")
            await bot.stop_bot()
            print("✅ Bot stopped successfully")
            
            return True
        else:
            print("❌ Bot failed to start")
            return False
            
    except Exception as e:
        print(f"❌ Error during bot test: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("🧪 Starting Telegram Bot Async/Await Fix Test")
    print("=" * 50)
    
    # Test configuration
    print(f"📋 Configuration Test:")
    print(f"   Bot Token: {'✅ Set' if Config.BOT_TOKEN else '❌ Not Set'}")
    print(f"   Admin ID: {'✅ Set' if Config.ADMIN_ID else '❌ Not Set'}")
    print()
    
    # Test bot functionality
    success = await test_bot_initialization()
    
    print("=" * 50)
    if success:
        print("✅ All tests passed! The async/await fixes are working correctly.")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(main())
    sys.exit(0 if success else 1)