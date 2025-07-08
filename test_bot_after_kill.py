#!/usr/bin/env python3
"""
Test Bot After Killing Render Service

This script verifies that the bot can now run without conflicts
after killing the Render service.
"""

import asyncio
import sys
import os
import time
from config import Config

async def test_bot_connection():
    """Test if bot can connect without conflicts"""
    try:
        import telegram
        
        print("🧪 Testing bot after killing Render service...")
        
        # Create bot instance
        bot = telegram.Bot(token=Config.BOT_TOKEN)
        
        # Test 1: Get bot info
        print("1️⃣ Testing bot info...")
        bot_info = await bot.get_me()
        print(f"   ✅ Bot: @{bot_info.username} (ID: {bot_info.id})")
        
        # Test 2: Clear any remaining webhooks
        print("2️⃣ Clearing webhooks...")
        await bot.delete_webhook(drop_pending_updates=True)
        print("   ✅ Webhooks cleared")
        
        # Test 3: Test get_updates (this was failing before)
        print("3️⃣ Testing get_updates...")
        updates = await bot.get_updates(timeout=2, limit=1)
        print(f"   ✅ get_updates successful: {len(updates)} updates received")
        
        # Test 4: Test multiple get_updates calls
        print("4️⃣ Testing multiple get_updates calls...")
        for i in range(3):
            updates = await bot.get_updates(timeout=1, limit=1)
            print(f"   ✅ Call {i+1}: {len(updates)} updates")
            await asyncio.sleep(1)
        
        print("\n✅ SUCCESS: Bot is working without conflicts!")
        return True
        
    except Exception as e:
        print(f"\n❌ Bot test failed: {e}")
        if "Conflict" in str(e):
            print("   ⚠️ Still have conflicts - another instance might be running")
        return False

async def test_bot_polling():
    """Test if bot can start polling without conflicts"""
    try:
        import telegram
        from telegram.ext import Application
        
        print("🔄 Testing bot polling...")
        
        # Create application
        app = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Initialize
        await app.initialize()
        
        # Try to start polling for a few seconds
        print("   🚀 Starting polling for 5 seconds...")
        await app.updater.start_polling(drop_pending_updates=True)
        await app.start()
        
        # Let it run for a bit
        await asyncio.sleep(5)
        
        # Stop polling
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        
        print("   ✅ Polling test successful!")
        return True
        
    except Exception as e:
        print(f"   ❌ Polling test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🔧 TESTING BOT AFTER RENDER SERVICE KILL")
    print("=" * 50)
    
    # Wait a moment for Render to fully shut down
    print("⏳ Waiting for Render service to fully shut down...")
    await asyncio.sleep(5)
    
    # Test basic connection
    print("\n🧪 Testing basic bot connection...")
    if await test_bot_connection():
        print("\n✅ Basic connection test PASSED!")
        
        # Test polling
        print("\n🔄 Testing bot polling...")
        if await test_bot_polling():
            print("\n🎉 ALL TESTS PASSED!")
            print("✅ Your bot is ready to run without conflicts!")
            print("\n🚀 You can now:")
            print("   - Run your bot locally: python main.py")
            print("   - Or redeploy to Render with confidence")
        else:
            print("\n⚠️ Polling test failed, but basic connection works")
            print("   This might be a temporary issue")
    else:
        print("\n❌ Basic connection test FAILED")
        print("   There might still be conflicts")
        print("   Wait a few more minutes and try again")

if __name__ == "__main__":
    asyncio.run(main())