#!/usr/bin/env python3
"""
Debug script to test bot responsiveness
"""

import asyncio
import logging
from config import Config
from telegram_bot import TelegramBot

# Enable debug logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

async def debug_bot():
    """Debug bot connectivity and handlers"""
    print("🔍 DEBUGGING BOT ISSUES")
    print("=" * 50)
    
    # Check configuration
    print(f"🔑 Bot Token: {Config.BOT_TOKEN[:10] if Config.BOT_TOKEN else 'None'}***")
    print(f"👤 Admin ID: {Config.ADMIN_ID}")
    print(f"📊 Bybit API Key: {Config.BYBIT_API_KEY}")
    
    # Test bot initialization
    bot = TelegramBot()
    print(f"🤖 Bot instance created: {bot is not None}")
    
    # Test token with a simple API call
    try:
        print("🌐 Testing bot token validity...")
        application = bot.get_application()
        bot_info = await application.bot.get_me()
        print(f"✅ Bot connected successfully!")
        print(f"   Bot name: @{bot_info.username}")
        print(f"   Bot ID: {bot_info.id}")
        print(f"   Bot first name: {bot_info.first_name}")
        
        # Check if handlers are registered
        handlers = application.handlers
        print(f"📋 Registered handlers: {len(handlers)} groups")
        
        for group_id, handler_list in handlers.items():
            print(f"   Group {group_id}: {len(handler_list)} handlers")
            for handler in handler_list:
                print(f"     - {type(handler).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot token test failed: {e}")
        return False

async def test_admin_check():
    """Test admin authorization"""
    print("\n👤 TESTING ADMIN AUTHORIZATION")
    print("-" * 30)
    
    bot = TelegramBot()
    
    # Test with configured admin ID
    is_admin = bot.is_admin(Config.ADMIN_ID)
    print(f"Admin ID {Config.ADMIN_ID} authorization: {'✅ ALLOWED' if is_admin else '❌ DENIED'}")
    
    # Test with a random ID
    is_random = bot.is_admin(123456789)
    print(f"Random ID 123456789 authorization: {'✅ ALLOWED' if is_random else '❌ DENIED'}")
    
    return is_admin

async def main():
    """Run debug tests"""
    print("🚀 Starting bot debug session...")
    
    # Test 1: Bot connectivity
    bot_ok = await debug_bot()
    
    # Test 2: Admin authorization
    admin_ok = await test_admin_check()
    
    print("\n📋 DEBUG SUMMARY")
    print("=" * 50)
    print(f"Bot connectivity: {'✅ OK' if bot_ok else '❌ FAILED'}")
    print(f"Admin authorization: {'✅ OK' if admin_ok else '❌ FAILED'}")
    
    if bot_ok and admin_ok:
        print("\n🎉 Bot should be working properly!")
        print("📱 Try sending /start to the bot again")
        
        # Keep bot running for testing
        print("\n🔄 Starting bot for testing...")
        print("Send /start to test (Ctrl+C to stop)")
        
        bot = TelegramBot()
        try:
            await bot.start_bot()
        except KeyboardInterrupt:
            print("\n⏹️ Bot stopped by user")
            await bot.stop_bot()
    else:
        print("\n⚠️ Issues found - bot may not respond properly")
        
        if not bot_ok:
            print("🔧 Check your BOT_TOKEN in .env file")
        if not admin_ok:
            print("🔧 Check your ADMIN_ID in .env file")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Debug session ended")