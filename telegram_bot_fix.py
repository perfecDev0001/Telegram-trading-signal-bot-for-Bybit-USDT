"""
Alternative TelegramBot initialization that should work with problematic versions
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.request import HTTPXRequest
from config import Config

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBotFix:
    def __init__(self):
        try:
            # Method 1: Simple initialization without custom request
            print("🔄 Trying simple initialization...")
            try:
                self.application = Application.builder().token(Config.BOT_TOKEN).build()
                self.bot = self.application.bot
                self._running = False
                self._polling_task = None
                print("✅ TelegramBot initialized with simple method")
                return
            except Exception as e:
                print(f"⚠️ Simple initialization failed: {e}")
            
            # Method 2: Custom request with specific parameters
            print("🔄 Trying custom request initialization...")
            try:
                request = HTTPXRequest(
                    connection_pool_size=8,
                    read_timeout=30,
                    write_timeout=30,
                    connect_timeout=30,
                    pool_timeout=30
                )
                
                # Create application step by step
                builder = Application.builder()
                builder.token(Config.BOT_TOKEN)
                builder.request(request)
                
                # Try to disable job queue if possible
                try:
                    builder.job_queue(None)
                except (AttributeError, TypeError):
                    pass
                
                self.application = builder.build()
                self.bot = self.application.bot
                self._running = False
                self._polling_task = None
                print("✅ TelegramBot initialized with custom request")
                return
            except Exception as e:
                print(f"⚠️ Custom request initialization failed: {e}")
            
            # Method 3: Minimal initialization
            print("🔄 Trying minimal initialization...")
            try:
                builder = Application.builder()
                builder.token(Config.BOT_TOKEN)
                self.application = builder.build()
                self.bot = self.application.bot
                self._running = False
                self._polling_task = None
                print("✅ TelegramBot initialized with minimal method")
                return
            except Exception as e:
                print(f"⚠️ Minimal initialization failed: {e}")
            
            raise Exception("All initialization methods failed")
            
        except Exception as e:
            print(f"❌ Error initializing TelegramBot: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def start_bot(self):
        """Start the bot with proper error handling"""
        try:
            print("🤖 Starting bot...")
            
            # Test bot connection
            try:
                bot_info = await self.bot.get_me()
                print(f"✅ Bot connection successful: @{bot_info.username}")
            except Exception as e:
                print(f"❌ Bot connection test failed: {e}")
                return False
            
            # Start polling with the asyncio-friendly approach
            self._running = True
            
            # Initialize the application first
            await self.application.initialize()
            
            # Start the updater
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                bootstrap_retries=3
            )
            
            # Start the application
            await self.application.start()
            
            print("✅ Bot is running!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def stop_bot(self):
        """Stop the bot gracefully"""
        if not self._running:
            return
        
        try:
            print("🛑 Stopping bot...")
            self._running = False
            
        # Stop the application components in order
            if hasattr(self.application, 'updater') and self.application.updater:
                    await self.application.updater.stop()
            
            if self.application.running:
                await self.application.stop()
            
            # Shutdown the application
            await self.application.shutdown()
            
            print("✅ Bot stopped successfully")
            
        except Exception as e:
            print(f"⚠️ Error during bot shutdown: {e}")
    
    def is_running(self):
        """Check if bot is running"""
        return (self._running and 
                hasattr(self, '_polling_task') and 
                self._polling_task and 
                not self._polling_task.done())