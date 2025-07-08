#!/usr/bin/env python3
"""
Test script to verify the Telegram bot fix works
"""
import asyncio
import sys
import os

# Add the current directory to the path
sys.path.insert(0, '/home/rheedan/Documents/working/forFreelancer/Bybit_Scanner_Bot')

from config import Config
from telegram_bot_fix import TelegramBotFix

async def test_bot():
    """Test the bot initialization and basic functionality"""
    print("🧪 Testing Telegram bot initialization...")
    
    # Test 1: Bot initialization
    try:
        bot = TelegramBotFix()
        print("✅ Bot initialization successful")
    except Exception as e:
        print(f"❌ Bot initialization failed: {e}")
        return False
    
    # Test 2: Bot connection test
    try:
        bot_info = await bot.bot.get_me()
        print(f"✅ Bot connection test successful: @{bot_info.username}")
    except Exception as e:
        print(f"❌ Bot connection test failed: {e}")
        return False
    
    # Test 3: Start bot (briefly)
    try:
        print("🚀 Testing bot start...")
        success = await bot.start_bot()
        if success:
            print("✅ Bot start successful")
            await asyncio.sleep(2)  # Let it run briefly
            await bot.stop_bot()
            print("✅ Bot stop successful")
        else:
            print("❌ Bot start failed")
            return False
    except Exception as e:
        print(f"❌ Bot start/stop test failed: {e}")
        return False
    
    print("🎉 All tests passed!")
    return True

if __name__ == "__main__":
    if not Config.BOT_TOKEN:
        print("❌ BOT_TOKEN not found in config")
        sys.exit(1)
    
    asyncio.run(test_bot())