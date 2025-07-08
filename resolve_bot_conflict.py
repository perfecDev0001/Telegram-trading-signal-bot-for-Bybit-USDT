#!/usr/bin/env python3
"""
Bot Conflict Resolution Script
This script helps resolve conflicts when multiple bot instances are running
"""
import asyncio
import sys
import time
import signal
import psutil
sys.path.insert(0, '/home/rheedan/Documents/working/forFreelancer/Bybit_Scanner_Bot')

from telegram import Bot
from telegram.error import Conflict, TelegramError
from config import Config

class BotConflictResolver:
    def __init__(self):
        self.bot = Bot(token=Config.BOT_TOKEN)
        
    async def clear_webhooks(self):
        """Clear any existing webhooks"""
        try:
            print("🔄 Clearing webhooks...")
            await self.bot.delete_webhook(drop_pending_updates=True)
            print("✅ Webhooks cleared")
            return True
        except Exception as e:
            print(f"⚠️ Error clearing webhooks: {e}")
            return False
    
    async def test_bot_connection(self):
        """Test if bot can connect without conflicts"""
        try:
            print("🔍 Testing bot connection...")
            bot_info = await self.bot.get_me()
            print(f"✅ Bot connection successful: @{bot_info.username}")
            return True
        except Conflict as e:
            print(f"❌ Bot conflict detected: {e}")
            return False
        except Exception as e:
            print(f"❌ Bot connection failed: {e}")
            return False
    
    async def force_stop_updates(self):
        """Force stop any ongoing update polling"""
        try:
            print("🛑 Attempting to force stop updates...")
            
            # Try to get updates with a short timeout to interrupt any ongoing polling
            await self.bot.get_updates(offset=-1, limit=1, timeout=1)
            print("✅ Updates polling interrupted")
            return True
        except Conflict:
            print("⚠️ Still conflicting, will retry...")
            return False
        except Exception as e:
            print(f"⚠️ Error during force stop: {e}")
            return False
    
    def kill_existing_processes(self):
        """Kill any existing bot processes"""
        try:
            print("🔍 Searching for existing bot processes...")
            current_pid = os.getpid()
            killed_count = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['pid'] == current_pid:
                        continue
                    
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    
                    # Look for Python processes running bot-related scripts
                    if ('python' in proc.info['name'].lower() and 
                        any(keyword in cmdline.lower() for keyword in ['main.py', 'telegram_bot', 'bot', 'scanner'])):
                        
                        print(f"🎯 Found potential bot process: PID {proc.info['pid']} - {cmdline}")
                        proc.terminate()
                        killed_count += 1
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if killed_count > 0:
                print(f"✅ Terminated {killed_count} processes")
                time.sleep(2)  # Give processes time to stop
            else:
                print("ℹ️ No conflicting processes found")
            
            return killed_count > 0
        except Exception as e:
            print(f"⚠️ Error killing processes: {e}")
            return False
    
    async def resolve_conflicts(self):
        """Main conflict resolution method"""
        print("🔧 Starting bot conflict resolution...")
        
        # Step 1: Clear webhooks
        await self.clear_webhooks()
        
        # Step 2: Test connection
        if await self.test_bot_connection():
            print("✅ No conflicts detected!")
            return True
        
        # Step 3: Kill existing processes
        print("🛑 Killing existing processes...")
        self.kill_existing_processes()
        
        # Step 4: Wait and clear webhooks again
        await asyncio.sleep(3)
        await self.clear_webhooks()
        
        # Step 5: Force stop updates
        for attempt in range(5):
            print(f"🔄 Attempt {attempt + 1}/5 to resolve conflicts...")
            
            if await self.force_stop_updates():
                await asyncio.sleep(2)
                
                if await self.test_bot_connection():
                    print("✅ Conflicts resolved!")
                    return True
            
            await asyncio.sleep(3)
        
        print("❌ Could not resolve conflicts automatically")
        return False
    
    async def cleanup(self):
        """Cleanup resources"""
        try:
            # Close the bot session
            if hasattr(self.bot, '_bot') and hasattr(self.bot._bot, 'session'):
                await self.bot._bot.session.close()
        except Exception:
            pass

async def main():
    """Main function"""
    resolver = BotConflictResolver()
    
    try:
        success = await resolver.resolve_conflicts()
        
        if success:
            print("\n🎉 Conflict resolution completed successfully!")
            print("✅ You can now start your bot normally")
            return 0
        else:
            print("\n❌ Conflict resolution failed")
            print("💡 Manual steps you can try:")
            print("1. Wait 5-10 minutes for Telegram to timeout the other instance")
            print("2. Check for any running bot processes and kill them manually")
            print("3. If deployed, restart your hosting service")
            return 1
    
    except KeyboardInterrupt:
        print("\n⏹️ Resolution interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1
    finally:
        await resolver.cleanup()

if __name__ == "__main__":
    import os
    
    if not Config.BOT_TOKEN:
        print("❌ BOT_TOKEN not found in config")
        sys.exit(1)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)