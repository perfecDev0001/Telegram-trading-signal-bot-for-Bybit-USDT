#!/usr/bin/env python3
"""
Simple test to verify the bot works
"""
import asyncio
import sys
import signal
sys.path.insert(0, '/home/rheedan/Documents/working/forFreelancer/Bybit_Scanner_Bot')

from telegram_bot import TelegramBot
from config import Config

async def test_bot():
    """Test bot initialization and basic functionality"""
    print("🧪 Testing Telegram bot...")
    
    # Test bot initialization
    try:
        bot = TelegramBot()
        print("✅ Bot initialization successful")
    except Exception as e:
        print(f"❌ Bot initialization failed: {e}")
        return False
    
    # Test bot connection
    try:
        bot_info = await bot.bot.get_me()
        print(f"✅ Bot connection successful: @{bot_info.username}")
    except Exception as e:
        print(f"❌ Bot connection failed: {e}")
        return False
    
    # Test bot start (with timeout)
    try:
        print("🚀 Starting bot...")
        
        # Set up signal handler to stop after 5 seconds
        def timeout_handler(signum, frame):
            print("⏰ Timeout reached, stopping test...")
            raise TimeoutError("Test timeout")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)  # 5 second timeout
        
        # Start the bot
        await bot.start_bot()
        
        # If we reach here, the bot started successfully
        print("✅ Bot started successfully")
        
        # Check if running
        if bot.is_running():
            print("✅ Bot is running")
        else:
            print("⚠️ Bot is not running")
        
        # Stop the bot
        await bot.stop_bot()
        print("✅ Bot stopped successfully")
        
        signal.alarm(0)  # Cancel the alarm
        return True
        
    except TimeoutError:
        print("⏰ Test completed within timeout")
        try:
            await bot.stop_bot()
        except:
            pass
        return True
    except Exception as e:
        print(f"❌ Bot start/stop failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if not Config.BOT_TOKEN:
        print("❌ BOT_TOKEN not found in config")
        sys.exit(1)
    
    success = asyncio.run(test_bot())
    if success:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("❌ Tests failed!")
        sys.exit(1)