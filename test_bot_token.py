#!/usr/bin/env python3
"""
Simple bot token test
"""

import asyncio
import sys
from telegram import Bot
from config import Config

async def test_token():
    """Test if bot token is valid"""
    print("🔍 Testing Bot Token...")
    print(f"Token: {Config.BOT_TOKEN[:10] if Config.BOT_TOKEN else 'None'}***")
    
    try:
        bot = Bot(token=Config.BOT_TOKEN)
        bot_info = await bot.get_me()
        
        print("✅ Bot token is VALID!")
        print(f"   Bot Username: @{bot_info.username}")
        print(f"   Bot Name: {bot_info.first_name}")
        print(f"   Bot ID: {bot_info.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot token is INVALID: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_token())
    sys.exit(0 if result else 1)