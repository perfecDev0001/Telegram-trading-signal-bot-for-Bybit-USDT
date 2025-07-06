#!/usr/bin/env python3
"""
Deployment Fix Test
Test the fixed telegram bot initialization
"""

import asyncio
import sys
import os

def test_imports():
    """Test if all imports work correctly"""
    print("🔍 Testing imports...")
    
    try:
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
        from telegram.constants import ParseMode
        print("   ✅ Telegram imports: OK")
    except Exception as e:
        print(f"   ❌ Telegram imports failed: {e}")
        return False
    
    try:
        from config import Config
        print("   ✅ Config import: OK")
    except Exception as e:
        print(f"   ❌ Config import failed: {e}")
        return False
    
    try:
        from database import db
        print("   ✅ Database import: OK")
    except Exception as e:
        print(f"   ❌ Database import failed: {e}")
        return False
    
    try:
        from settings_manager import settings_manager, is_admin
        print("   ✅ Settings manager import: OK")
    except Exception as e:
        print(f"   ❌ Settings manager import failed: {e}")
        return False
    
    return True

def test_telegram_bot_creation():
    """Test TelegramBot class creation"""
    print("\n🤖 Testing TelegramBot creation...")
    
    try:
        from telegram_bot import TelegramBot
        print("   ✅ TelegramBot import: OK")
        
        # Test bot creation (this should not fail now)
        bot = TelegramBot()
        print("   ✅ TelegramBot creation: OK")
        
        # Test if application is created
        if hasattr(bot, 'application') and bot.application:
            print("   ✅ Application created: OK")
        else:
            print("   ❌ Application not created")
            return False
        
        # Test if handlers are set up
        if len(bot.application.handlers) > 0:
            print(f"   ✅ Handlers set up: {len(bot.application.handlers[0])} handlers")
        else:
            print("   ❌ No handlers found")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ TelegramBot creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_values():
    """Test configuration values"""
    print("\n⚙️ Testing configuration...")
    
    try:
        from config import Config
        
        if hasattr(Config, 'BOT_TOKEN') and Config.BOT_TOKEN:
            print(f"   ✅ BOT_TOKEN: Set ({Config.BOT_TOKEN[:10]}...)")
        else:
            print("   ❌ BOT_TOKEN: Not set")
            return False
        
        if hasattr(Config, 'ADMIN_ID') and Config.ADMIN_ID:
            print(f"   ✅ ADMIN_ID: Set ({Config.ADMIN_ID})")
        else:
            print("   ❌ ADMIN_ID: Not set")
            return False
        
        return True
        
    except Exception as e:
        print(f"   ❌ Config test failed: {e}")
        return False

async def test_bot_initialization():
    """Test bot initialization without starting"""
    print("\n🚀 Testing bot initialization...")
    
    try:
        from telegram_bot import TelegramBot
        
        bot = TelegramBot()
        
        # Test initialization
        await bot.application.initialize()
        print("   ✅ Bot initialization: OK")
        
        # Test bot info (this will fail if token is invalid)
        try:
            bot_info = await asyncio.wait_for(bot.application.bot.get_me(), timeout=10)
            print(f"   ✅ Bot connection test: OK (@{bot_info.username})")
        except Exception as e:
            print(f"   ❌ Bot connection test failed: {e}")
            return False
        
        # Shutdown properly
        await bot.application.shutdown()
        print("   ✅ Bot shutdown: OK")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Bot initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧪 Deployment Fix Test")
    print("=" * 50)
    
    # Test 1: Imports
    if not test_imports():
        print("\n❌ Import tests failed!")
        return False
    
    # Test 2: Config
    if not test_config_values():
        print("\n❌ Configuration tests failed!")
        return False
    
    # Test 3: Bot creation
    if not test_telegram_bot_creation():
        print("\n❌ TelegramBot creation tests failed!")
        return False
    
    # Test 4: Bot initialization (async)
    try:
        if not asyncio.run(test_bot_initialization()):
            print("\n❌ Bot initialization tests failed!")
            return False
    except Exception as e:
        print(f"\n❌ Async test failed: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("🚀 The deployment fix should work now!")
    print("=" * 50)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)