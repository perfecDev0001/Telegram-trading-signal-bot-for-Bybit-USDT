#!/usr/bin/env python3
"""
Test Deployment Script

This script tests the deployment configuration and webhook clearing.
"""

import asyncio
import sys
import os
import subprocess
import time
import psutil

async def test_telegram_connection():
    """Test Telegram bot connection"""
    try:
        from config import Config
        import telegram
        
        print("🤖 Testing Telegram bot connection...")
        
        # Create bot instance
        bot = telegram.Bot(token=Config.BOT_TOKEN)
        
        # Clear any existing webhook
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook cleared")
        
        # Test bot connection
        bot_info = await bot.get_me()
        print(f"✅ Bot connected: @{bot_info.username}")
        
        # Test message sending
        await bot.send_message(
            chat_id=Config.ADMIN_ID,
            text="🧪 Test message from deployment script"
        )
        print("✅ Test message sent successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Telegram connection failed: {e}")
        return False

def test_configuration():
    """Test configuration"""
    try:
        from config import Config
        
        print("🔧 Testing configuration...")
        
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

def test_process_cleanup():
    """Test process cleanup functionality"""
    print("🧹 Testing process cleanup...")
    
    current_pid = os.getpid()
    bot_processes = []
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if (proc.info['pid'] != current_pid and 
                proc.info['cmdline'] and
                any(keyword in ' '.join(proc.info['cmdline']).lower() 
                    for keyword in ['main.py', 'telegram_bot', 'start_render.py'])):
                bot_processes.append(proc.info['pid'])
    
        if bot_processes:
            print(f"⚠️ Found {len(bot_processes)} potentially conflicting processes")
            print("   These may cause conflicts during deployment")
            return False
        else:
            print("✅ No conflicting processes found")
            return True
            
    except Exception as e:
        print(f"❌ Process cleanup test failed: {e}")
        return False

def test_imports():
    """Test critical imports"""
    print("📦 Testing imports...")
    
    try:
        import telegram
        print(f"✅ python-telegram-bot version: {telegram.__version__}")
        
        from telegram.ext import Application
        print("✅ Application class imported")
        
        from config import Config
        print("✅ Config imported")
        
        from main import BotManager
        print("✅ BotManager imported")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Deployment Test Suite")
    print("=" * 50)
    
    tests = [
        ("Configuration", test_configuration),
        ("Imports", test_imports),
        ("Process Cleanup", test_process_cleanup),
        ("Telegram Connection", test_telegram_connection),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running {test_name} test...")
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                print(f"✅ {test_name} test PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} test FAILED")
                failed += 1
                
        except Exception as e:
            print(f"❌ {test_name} test FAILED: {e}")
            failed += 1
    
    print(f"\n📊 Test Results:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! Ready for deployment.")
        return True
    else:
        print("\n⚠️ Some tests failed. Please fix issues before deployment.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)