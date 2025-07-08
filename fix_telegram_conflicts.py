#!/usr/bin/env python3
"""
Comprehensive Telegram Bot Conflict Resolution Script

This script resolves all common conflicts that cause the
"terminated by other getUpdates request" error.
"""

import asyncio
import sys
import os
import psutil
import time
import requests
from config import Config

async def clear_all_webhooks():
    """Clear all webhooks and get updates conflicts"""
    try:
        import telegram
        
        print("🔄 Clearing all webhooks and conflicts...")
        
        # Create bot instance with extended timeout
        bot = telegram.Bot(token=Config.BOT_TOKEN)
        
        # Step 1: Delete webhook with drop_pending_updates=True
        print("  📝 Deleting webhooks...")
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Step 2: Wait for Telegram to process
        print("  ⏳ Waiting for Telegram to process...")
        await asyncio.sleep(3)
        
        # Step 3: Try to get updates manually to clear any remaining conflicts
        print("  🔍 Clearing pending updates...")
        try:
            updates = await bot.get_updates(timeout=1, limit=100)
            print(f"  ✅ Cleared {len(updates)} pending updates")
        except Exception as e:
            print(f"  ⚠️ Could not clear pending updates: {e}")
        
        # Step 4: Verify bot connection
        print("  🤖 Verifying bot connection...")
        bot_info = await bot.get_me()
        print(f"  ✅ Bot verified: @{bot_info.username}")
        
        print("✅ All webhooks and conflicts cleared successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to clear webhooks: {e}")
        return False

def kill_conflicting_processes():
    """Kill all conflicting bot processes"""
    current_pid = os.getpid()
    killed = 0
    
    print("🧹 Killing conflicting processes...")
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if (proc.info['pid'] != current_pid and 
                proc.info['cmdline'] and
                any(keyword in ' '.join(proc.info['cmdline']).lower() 
                    for keyword in ['main.py', 'telegram_bot', 'start_render.py', 'bot', 'scanner'])):
                
                try:
                    print(f"  🗑️ Killing process PID {proc.info['pid']}: {' '.join(proc.info['cmdline'])}")
                    proc.terminate()
                    proc.wait(timeout=5)
                    killed += 1
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    try:
                        proc.kill()
                        killed += 1
                    except psutil.NoSuchProcess:
                        pass
                except psutil.AccessDenied:
                    print(f"  ⚠️ Access denied for PID {proc.info['pid']}")
                    pass
    except Exception as e:
        print(f"⚠️ Error during process cleanup: {e}")
    
    if killed > 0:
        print(f"✅ Killed {killed} conflicting processes")
        time.sleep(3)  # Give processes time to fully terminate
    else:
        print("✅ No conflicting processes found")

def check_render_deployment():
    """Check if there are multiple deployments on Render"""
    try:
        service_name = os.getenv('RENDER_SERVICE_NAME', 'public-api-crypto-scanner')
        if service_name and service_name != 'public-api-crypto-scanner':
            print(f"⚠️ Service name mismatch: {service_name}")
            print("   This might indicate multiple deployments!")
            return False
        
        # Check if we're running in Render environment
        if os.getenv('RENDER'):
            print("🌐 Running in Render environment")
            return True
        else:
            print("🏠 Running in local environment")
            return False
            
    except Exception as e:
        print(f"⚠️ Could not check deployment status: {e}")
        return False

async def test_bot_alone():
    """Test if the bot can run without conflicts"""
    try:
        import telegram
        
        print("🧪 Testing bot isolation...")
        
        # Create bot instance
        bot = telegram.Bot(token=Config.BOT_TOKEN)
        
        # Test get_me
        bot_info = await bot.get_me()
        print(f"  ✅ Bot info: @{bot_info.username}")
        
        # Test get_updates with short timeout
        updates = await bot.get_updates(timeout=2, limit=1)
        print(f"  ✅ Can get updates: {len(updates)} received")
        
        print("✅ Bot is ready and conflict-free!")
        return True
        
    except Exception as e:
        print(f"❌ Bot test failed: {e}")
        return False

async def main():
    """Main conflict resolution function"""
    print("🔧 TELEGRAM BOT CONFLICT RESOLUTION")
    print("=" * 50)
    
    # Step 1: Kill conflicting processes
    print("\n1️⃣ Killing conflicting processes...")
    kill_conflicting_processes()
    
    # Step 2: Check deployment status
    print("\n2️⃣ Checking deployment status...")
    is_render = check_render_deployment()
    
    # Step 3: Clear all webhooks and conflicts
    print("\n3️⃣ Clearing webhooks and conflicts...")
    webhook_cleared = await clear_all_webhooks()
    
    if not webhook_cleared:
        print("❌ Failed to clear webhooks. Check your bot token.")
        sys.exit(1)
    
    # Step 4: Wait a bit more for full cleanup
    print("\n4️⃣ Waiting for full cleanup...")
    await asyncio.sleep(5)
    
    # Step 5: Test bot isolation
    print("\n5️⃣ Testing bot isolation...")
    bot_ready = await test_bot_alone()
    
    if bot_ready:
        print("\n✅ SUCCESS: Bot is ready and conflict-free!")
        print("🚀 You can now start your bot safely.")
        
        if is_render:
            print("\n📋 RENDER DEPLOYMENT NOTES:")
            print("   - Make sure you have only ONE active deployment")
            print("   - Check your Render dashboard for duplicate services")
            print("   - Redeploy if necessary after this fix")
    else:
        print("\n❌ FAILED: Bot still has conflicts.")
        print("🔍 Additional troubleshooting needed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())