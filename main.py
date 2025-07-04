#!/usr/bin/env python3
"""
Bybit Scanner Bot - Main Entry Point

This script runs both the Telegram bot and the Bybit scanner concurrently.
The bot provides admin interface while the scanner monitors markets.
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

from config import Config
from telegram_bot import TelegramBot
from enhanced_scanner import enhanced_scanner
from settings_manager import settings_manager

class BotManager:
    def __init__(self):
        self.running = True
        self.bot_task = None
        self.scanner_task = None
        self.web_task = None
        self.keepalive_task = None
        self.startup_time = time.time()
        self.telegram_bot = TelegramBot()
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
                    (proc.info['name'] in ['python', 'python3', 'python.exe', 'python3.exe'])):
                    python_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        # Check only python processes for bot keywords
        for proc in python_processes:
            try:
                if (proc.info['cmdline'] and
                    any(keyword in ' '.join(proc.info['cmdline']).lower() 
                        for keyword in ['main.py', 'telegram_bot', 'bybit', 'scanner', 'bot'])):
                    
                    print(f"  Killing conflicting process PID {proc.info['pid']}: {' '.join(proc.info['cmdline'])}")
                    proc.kill()
                    killed += 1
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        if killed > 0:
            print(f"✅ Cleaned up {killed} conflicting processes")
            time.sleep(2)  # Give more time for process cleanup
        else:
            print("✅ No conflicting processes found")
    
    async def start_bot(self):
        """Start the Telegram bot"""
        try:
            print("🤖 Starting Telegram Bot...")
            
            # Start the bot using the new method
            if await self.telegram_bot.start_bot():
                print(f"🔑 Admin ID: {Config.ADMIN_ID}")
                print(f"📱 Bot Token: {Config.BOT_TOKEN[:10]}***")
                
                # Keep the bot running with health monitoring
                last_health_check = time.time()
                while self.running:
                    # Health check every 60 seconds
                    if time.time() - last_health_check > 60:
                        if not await self.telegram_bot.restart_if_needed():
                            print("❌ Bot restart failed, stopping bot task")
                            break
                        last_health_check = time.time()
                    
                    await asyncio.sleep(1)
            else:
                print("❌ Failed to start Telegram bot")
                
        except asyncio.CancelledError:
            print("🛑 Bot task was cancelled")
        except Exception as e:
            error_msg = str(e)
            if "409" in error_msg or "Conflict" in error_msg:
                print(f"❌ Bot conflict error: {e}")
                print("💡 This usually means another bot instance is running.")
                print("   Try running: python clear_bot_conflicts.py")
            else:
                print(f"❌ Bot error: {e}")
                import traceback
                traceback.print_exc()
        finally:
            # Use the new stop method
            await self.telegram_bot.stop_bot()
    
    async def start_keepalive(self):
        """Keep the service alive by self-pinging every 10 minutes"""
        await asyncio.sleep(30)  # Wait for server to start
        
        while self.running:
            try:
                if self.service_url:
                    # Self-ping to prevent sleep
                    async with aiohttp.ClientSession() as session:
                        try:
                            async with session.get(f"{self.service_url}/health", timeout=10) as response:
                                if response.status == 200:
                                    print("🔄 Keep-alive ping successful")
                                else:
                                    print(f"⚠️ Keep-alive ping failed: {response.status}")
                        except Exception as e:
                            print(f"⚠️ Keep-alive ping error: {e}")
                
                # Wait 10 minutes before next ping
                await asyncio.sleep(600)  # 10 minutes
                
            except Exception as e:
                print(f"❌ Keep-alive task error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

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
                "bot_running": self.telegram_bot.is_running() if hasattr(self.telegram_bot, 'is_running') else True,
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
            return web.Response(text="🤖 Bybit Scanner Bot is running!\n\nHealthcheck: /health\nStatus: /status")
        
        async def status_handler(request):
            """Status endpoint with more details"""
            try:
                from database import db
                scanner_status = db.get_scanner_status()
                
                status = {
                    "bot_info": {
                        "name": "Bybit Scanner Bot",
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
            
            # Set service URL for keep-alive
            service_name = os.environ.get('RENDER_SERVICE_NAME', 'bybit-scanner-bot')
            self.service_url = f"https://{service_name}.onrender.com"
            
            print(f"✅ Health check server running on http://0.0.0.0:{port}")
            print(f"   - Health check: http://0.0.0.0:{port}/health")
            print(f"   - Status: http://0.0.0.0:{port}/status")
            print(f"   - Service URL: {self.service_url}")
            
            # Keep the server running
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"❌ Failed to start health server: {e}")
            raise
    
    async def start_scanner(self):
        """Start the Enhanced Bybit Scanner"""
        try:
            print("🔍 Starting Enhanced Bybit Scanner...")
            print(f"⏱️ Scan interval: 60 seconds (5-minute candles)")
            print(f"📊 Advanced filtering with confluence scoring")
            print(f"🎯 Using Bybit API Key: {Config.BYBIT_API_KEY or 'Public Access'}")
            
            # Initialize settings sync
            settings_manager.sync_to_database()
            
            # Ensure scanner is set to running state on startup
            from database import db
            db.update_scanner_status(is_running=True)
            print("✅ Scanner status set to RUNNING")
            
            # Run the enhanced scanner with bot instance for sending signals
            while self.running:
                try:
                    # Run scanner for shorter periods with restarts
                    await asyncio.wait_for(
                        enhanced_scanner.run_enhanced_scanner(self.telegram_bot.application.bot),
                        timeout=300  # 5 minute timeout, then restart
                    )
                except asyncio.TimeoutError:
                    print("⏱️ Scanner cycle completed, restarting...")
                    continue
                except asyncio.CancelledError:
                    print("🛑 Scanner cancelled")
                    break
                except Exception as e:
                    print(f"❌ Scanner error: {e}, restarting in 30 seconds...")
                    await asyncio.sleep(30)
                    continue
            
        except Exception as e:
            print(f"❌ Enhanced Scanner error: {e}")
    
    async def run(self):
        """Run both bot and scanner concurrently"""
        print("=" * 60)
        print("🚀 ENHANCED BYBIT SCANNER BOT STARTING")
        print("=" * 60)
        print(f"⏰ Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Admin ID: {Config.ADMIN_ID}")
        # Don't print sensitive information directly
        print(f"🔑 API Key: {Config.BYBIT_API_KEY[:5]}..." if Config.BYBIT_API_KEY else "No API Key configured")
        print(f"🔐 API Secret: {'[CONFIGURED]' if Config.BYBIT_SECRET else '[NOT CONFIGURED]'}")
        print(f"🎯 API Mode: {'Authenticated' if Config.BYBIT_API_KEY and Config.BYBIT_SECRET else 'Public'}")
        
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
        
        # Add startup delay to ensure any previous instances are fully terminated
        print("⏳ Waiting for system stabilization...")
        await asyncio.sleep(5)
        
        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            print(f"\n⚠️ Received signal {signum}, shutting down...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Start bot, scanner, health server, and keep-alive concurrently
            self.bot_task = asyncio.create_task(self.start_bot())
            self.scanner_task = asyncio.create_task(self.start_scanner())
            self.web_task = asyncio.create_task(self.start_health_server())
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
    
    from enhanced_scanner import enhanced_scanner
    
    # Test API connectivity
    api_test = await enhanced_scanner.test_api_connectivity()
    if api_test:
        print("✅ API connection successful!")
    else:
        print("❌ API connection failed!")
    
    # Test bot initialization
    print("🤖 Testing bot initialization...")
    bot = TelegramBot()
    bot_started = await bot.start_bot()
    
    if bot_started:
        print("✅ Bot initialization successful!")
        print("🔍 Testing force scan functionality...")
        
        # Test a single scan
        try:
            signal_count = await enhanced_scanner.run_single_scan(bot.application.bot)
            print(f"✅ Force scan completed: {signal_count} signals generated")
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