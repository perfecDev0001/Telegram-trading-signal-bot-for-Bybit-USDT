#!/usr/bin/env python3
"""
Public API Scanner Bot - Main Entry Point

This script runs both the Telegram bot and the public API scanner concurrently.
The bot provides admin interface while the scanner monitors markets using public APIs.
No authentication required - fully public access.
"""

import asyncio
import signal
import sys
import time
import psutil
import os
import aiohttp
from datetime import datetime
from aiohttp import web
import threading

# Import scheduler fix to handle ZoneInfo compatibility
import scheduler_fix

from config import Config
from telegram_bot import TelegramBot  # Use the original telegram_bot implementation
from telegram_bot_fix import TelegramBotFix  # Fallback implementation
from enhanced_scanner import public_api_scanner
from settings_manager import settings_manager
from scheduler import market_scheduler

class BotManager:
    def __init__(self):
        self.running = True
        self.bot_task = None
        self.scanner_task = None
        self.web_task = None
        self.keepalive_task = None
        self.startup_time = time.time()
        self.telegram_bot = None  # Will be created later
        self.service_url = None  # Will be set after server starts
    
    def cleanup_processes(self):
        """Kill conflicting processes - optimized for speed"""
        current_pid = os.getpid()
        killed = 0
        
        print("🧹 Cleaning up conflicting processes...")
        
        # Get all python processes at once (faster than iterating)
        python_processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if (proc.info['pid'] != current_pid and 
                    proc.info['name'] == 'python.exe'):
                    python_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        # Check only python processes for bot keywords
        for proc in python_processes:
            try:
                if (proc.info['cmdline'] and
                    any(keyword in ' '.join(proc.info['cmdline']).lower() 
                        for keyword in ['main.py', 'working_bot', 'bot'])):
                    
                    print(f"  Killing PID {proc.info['pid']}")
                    proc.kill()
                    killed += 1
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed > 0:
            print(f"✅ Cleaned up {killed} processes")
            time.sleep(0.3)  # Minimal delay for process cleanup
        else:
            print("✅ No conflicts found")
    
    async def start_bot(self):
        """Start the Telegram bot with scheduled health checks"""
        try:
            print("🤖 Creating Telegram Bot...")
            
            # Create the bot instance here to avoid weak reference issues
            if self.telegram_bot is None:
                try:
                    # Try the original implementation first
                    self.telegram_bot = TelegramBot()
                    print("✅ Using original TelegramBot implementation")
                except Exception as e:
                    print(f"⚠️ Original TelegramBot failed: {e}")
                    print("🔄 Trying fallback TelegramBotFix implementation...")
                    try:
                        # Create a wrapper that mimics the original interface
                        class TelegramBotWrapper:
                            def __init__(self, bot_fix):
                                self.bot_fix = bot_fix
                                self.bot = bot_fix.bot
                                self.application = bot_fix.application
                            
                            async def start_bot(self):
                                return await self.bot_fix.start_bot()
                            
                            async def stop_bot(self):
                                return await self.bot_fix.stop_bot()
                            
                            def is_running(self):
                                return self.bot_fix.is_running()
                            
                            async def restart_if_needed(self):
                                return await self.bot_fix.start_bot()
                            
                            async def send_scan_result(self, result):
                                # Basic implementation for sending results
                                try:
                                    await self.bot.send_message(
                                        chat_id=Config.ADMIN_ID,
                                        text=f"📊 Scan Result: {result}"
                                    )
                                except Exception as e:
                                    print(f"Failed to send scan result: {e}")
                        
                        bot_fix = TelegramBotFix()
                        self.telegram_bot = TelegramBotWrapper(bot_fix)
                        print("✅ Using fallback TelegramBotFix implementation")
                    except Exception as e2:
                        print(f"❌ Both implementations failed: {e2}")
                        raise
            
            print("🤖 Starting Telegram Bot...")
            
            # Start the bot using the new method
            if await self.telegram_bot.start_bot():
                print(f"🔑 Admin ID: {Config.ADMIN_ID}")
                print(f"📱 Bot Token: {Config.BOT_TOKEN[:10]}***")
                if Config.CHANNEL_ID != 0:
                    print(f"📢 Private Channel: {Config.CHANNEL_ID}")
                else:
                    print("📢 Private Channel: Disabled")
                if Config.SUBSCRIBER_ID != 0:
                    print(f"👤 Default Subscriber: {Config.SUBSCRIBER_ID}")
                print("✅ Bot started successfully - health checks will be handled by scheduler")
                
                # Wait for shutdown signal instead of continuous polling
                while self.running:
                    await asyncio.sleep(5)  # Reduced sleep time for faster shutdown response
            else:
                print("❌ Failed to start Telegram bot")
                
        except asyncio.CancelledError:
            print("🛑 Bot task was cancelled")
        except Exception as e:
            print(f"❌ Bot error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Use the new stop method
            await self.telegram_bot.stop_bot()
    
    async def start_keepalive(self):
        """Initialize keep-alive service - actual pinging handled by scheduler"""
        print("💓 Keep-alive service initialized - will be handled by scheduler")
        
        # Just wait for shutdown signal instead of continuous polling
        while self.running:
            await asyncio.sleep(10)  # Reduced sleep for faster shutdown response

    async def start_health_server(self):
        """Start HTTP health check server for Render deployment"""
        async def health_check(request):
            """Health check endpoint"""
            uptime = time.time() - self.startup_time
            
            # Get system status (non-blocking)
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory = psutil.virtual_memory()
            except:
                cpu_percent = 0
                memory = type('obj', (object,), {'percent': 0, 'available': 0})()
            
            status = {
                "status": "healthy",
                "uptime_seconds": int(uptime),
                "uptime_formatted": f"{int(uptime//3600)}h {int((uptime%3600)//60)}m {int(uptime%60)}s",
                "bot_running": self.telegram_bot.is_running() if hasattr(self.telegram_bot, 'is_running') else False,
                "scanner_status": "running" if self.running else "stopped",
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_mb": memory.available // 1024 // 1024
                },
                "timestamp": datetime.now().isoformat(),
                "last_ping": datetime.now().isoformat()
            }
            
            return web.json_response(status)
        
        async def root_handler(request):
            """Root endpoint"""
            return web.Response(text="🤖 Public API Crypto Scanner Bot is running!\n\nHealthcheck: /health\nStatus: /status")
        
        async def status_handler(request):
            """Status endpoint with more details"""
            try:
                from database import db
                scanner_status = db.get_scanner_status()
                
                status = {
                    "bot_info": {
                        "name": "Public API Crypto Scanner Bot",
                        "version": "1.0.0",
                        "admin_id": Config.ADMIN_ID
                    },
                    "scanner": scanner_status,
                    "uptime": time.time() - self.startup_time,
                    "timestamp": datetime.now().isoformat()
                }
                return web.json_response(status)
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)
        
        # Create web application
        app = web.Application()
        app.router.add_get('/', root_handler)
        app.router.add_get('/health', health_check)
        app.router.add_get('/status', status_handler)
        
        # Get port from environment (Render provides PORT env var)
        port = int(os.environ.get('PORT', 8080))
        
        print(f"🌐 Starting health check server on port {port}")
        
        try:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', port)
            await site.start()
            
            # Set service URL for keep-alive and pass it to scheduler
            service_name = os.environ.get('RENDER_SERVICE_NAME', 'public-api-crypto-scanner')
            self.service_url = f"https://{service_name}.onrender.com"
            
            # Pass service URL to scheduler for keep-alive management
            market_scheduler.set_service_url(self.service_url)
            
            print(f"✅ Health check server running on http://0.0.0.0:{port}")
            print(f"   - Health check: http://0.0.0.0:{port}/health")
            print(f"   - Status: http://0.0.0.0:{port}/status")
            print(f"   - Service URL: {self.service_url}")
            
            # Keep the server running with reduced polling
            while self.running:
                await asyncio.sleep(5)  # Reduced sleep for faster shutdown response
                
        except Exception as e:
            print(f"❌ Failed to start health server: {e}")
            raise
    
    async def start_scanner(self):
        """Start the Enhanced Public API Scanner using APScheduler"""
        try:
            print("🔍 Starting Enhanced Public API Scanner with APScheduler...")
            print(f"⏱️ Scan interval: {Config.SCANNER_INTERVAL} seconds")
            print(f"📊 Advanced filtering with confluence scoring")
            print(f"🔓 Using Public APIs: No authentication required")
            
            # Initialize settings sync
            settings_manager.sync_to_database()
            
            # Ensure scanner is set to running state on startup
            from database import db
            db.update_scanner_status(is_running=True)
            print("✅ Scanner status set to RUNNING")
            
            # Set the telegram bot instance in the scheduler
            # Try to get the bot instance, with fallback
            try:
                if hasattr(self.telegram_bot, 'bot') and self.telegram_bot.bot:
                    market_scheduler.telegram_bot = self.telegram_bot.bot
                    print("✅ Scheduler linked to Telegram bot")
                else:
                    print("⚠️ Bot instance not ready, scheduler will start without bot instance")
            except Exception as e:
                print(f"⚠️ Could not link scheduler to bot: {e}")
                print("📊 Scheduler will run without Telegram notifications")
            
            # Start the scheduler
            await market_scheduler.start()
            
            # Scanner is now fully managed by APScheduler - no continuous monitoring needed
            print("✅ Scanner started successfully - APScheduler handles all timing and health checks")
            print("📅 All monitoring is now handled by the scheduler itself")
            # Just wait for shutdown signal instead of continuous health checking
            while self.running:
            
                await asyncio.sleep(10)  # Reduced sleep for faster shutdown response
            
        except Exception as e:
            print(f"❌ Enhanced Scanner error: {e}")
        finally:
            # Stop the scheduler
            await market_scheduler.stop()
    
    async def run(self):
        """Run both bot and scanner concurrently"""
        print("=" * 60)
        print("🚀 ENHANCED PUBLIC API SCANNER BOT STARTING")
        print("=" * 60)
        print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Admin ID: {Config.ADMIN_ID}")
        print(f"🔓 API Mode: Public APIs Only (No Authentication Required)")
        print(f"🌐 Data Sources: CoinGecko, CryptoCompare, CoinPaprika")
        print(f"🔄 Automatic Fallback: Multiple APIs for reliability")
        
        # Get current settings
        system_status = settings_manager.get_system_status()
        print(f"📊 Monitoring: {system_status['monitored_pairs']} pairs")
        print(f"🚀 Pump threshold: {system_status['thresholds']['pump']}%")
        print(f"📉 Dump threshold: {system_status['thresholds']['dump']}%")
        print(f"💥 Breakout threshold: {system_status['thresholds']['breakout']}%")
        print(f"📈 Volume threshold: {system_status['thresholds']['volume']}%")
        print(f"🎯 TP Multipliers: {system_status['tp_multipliers']}")
        print("=" * 60)
        
        # Cleanup first
        self.cleanup_processes()
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            print(f"\n⚠️ Received signal {signum}, shutting down...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Start bot first
            print("🤖 Starting Telegram Bot...")
            self.bot_task = asyncio.create_task(self.start_bot())
            
            # Give the bot a moment to initialize
            await asyncio.sleep(2)
            
            # Now start other services
            print("📊 Starting Scanner...")
            self.scanner_task = asyncio.create_task(self.start_scanner())
            
            print("🌐 Starting Health Server...")
            self.web_task = asyncio.create_task(self.start_health_server())
            
            print("💓 Starting Keep-Alive...")
            self.keepalive_task = asyncio.create_task(self.start_keepalive())
            
            print("🚀 All services started. Waiting for completion...")
            
            # Wait for any task to complete or fail
            done, pending = await asyncio.wait(
                [self.bot_task, self.scanner_task, self.web_task, self.keepalive_task],
                return_when=asyncio.FIRST_EXCEPTION
            )
            
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except KeyboardInterrupt:
            print("\n🛑 Keyboard interrupt received")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        finally:
            print("🛑 Shutting down...")
            self.running = False
            
            # Ensure all tasks are cancelled
            if hasattr(self, 'bot_task') and self.bot_task and not self.bot_task.done():
                self.bot_task.cancel()
            if hasattr(self, 'scanner_task') and self.scanner_task and not self.scanner_task.done():
                self.scanner_task.cancel()
            if hasattr(self, 'keepalive_task') and self.keepalive_task and not self.keepalive_task.done():
                self.keepalive_task.cancel()

def check_configuration():
    """Check if the bot is properly configured"""
    issues = []
    
    if not Config.BOT_TOKEN or Config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        issues.append("❌ BOT_TOKEN not configured in .env file")
    
    if Config.ADMIN_ID == 0:
        issues.append("❌ ADMIN_ID not configured in .env file")
    
    if issues:
        print("🚨 CONFIGURATION ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
        print("\n📝 Please update your .env file with correct values:")
        print("  1. Set BOT_TOKEN to your actual bot token")
        print("  2. Set ADMIN_ID to your Telegram user ID")
        print("\n💡 To get your Telegram user ID:")
        print("  - Message @userinfobot on Telegram")
        print("  - Or use @RawDataBot")
        return False
    
    return True

async def test_mode():
    """Run bot in test mode to verify functionality"""
    print("🧪 Running in TEST MODE")
    print("🔍 Testing API connectivity...")
    
    # Test Bybit API connectivity
    try:
        await bybit_scanner.initialize()
        print("✅ Bybit API connection successful!")
    except Exception as e:
        print(f"❌ Bybit API connection failed: {e}")
    
    # Test bot initialization
    print("🤖 Testing bot initialization...")
    bot = TelegramBot()
    bot_started = await bot.start_bot()
    
    if bot_started:
        print("✅ Bot initialization successful!")
        print("🔍 Testing force scan functionality...")
        
        # Test a single scan
        try:
            signals = await bybit_scanner.scan_markets()
            print(f"✅ Force scan completed: {len(signals)} signals generated")
        except Exception as e:
            print(f"❌ Force scan failed: {e}")
        
        # Stop the bot
        await bot.stop_bot()
    else:
        print("❌ Bot initialization failed!")
    
    print("🧪 Test mode completed")

def main():
    """Main function"""
    # Check for test mode
    if "--test" in sys.argv:
        print("🧪 Starting in test mode...")
        asyncio.run(test_mode())
        return
    
    print("🔧 Checking configuration...")
    
    if not check_configuration():
        print("\n❌ Cannot start bot due to configuration issues")
        sys.exit(1)
    
    print("✅ Configuration OK")
    
    try:
        # Create and run the bot manager
        manager = BotManager()
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)
    finally:
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()