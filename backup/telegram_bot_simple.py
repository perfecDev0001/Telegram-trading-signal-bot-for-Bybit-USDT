import asyncio
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

from config import Config
from database import db
from settings_manager import settings_manager, is_admin

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        try:
            # Simple application builder for v20.8
            self.application = Application.builder().token(Config.BOT_TOKEN).build()
            self.setup_handlers()
            self._running = False
            print("✅ TelegramBot initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing TelegramBot: {e}")
            raise
    
    async def start_bot(self):
        """Start the bot with proper error handling"""
        try:
            print("🤖 Initializing bot...")
            await self.application.initialize()
            
            print("🔍 Testing bot connection...")
            try:
                bot_info = await asyncio.wait_for(self.application.bot.get_me(), timeout=10)
                print(f"✅ Bot connection successful: @{bot_info.username}")
            except Exception as e:
                print(f"❌ Bot connection test failed: {e}")
                return False
            
            print("🚀 Starting bot application...")
            await self.application.start()
            
            print("📡 Starting polling...")
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"]
            )
            
            self._running = True
            print("✅ Bot is running and polling for messages!")
            print(f"🔑 Admin ID: {Config.ADMIN_ID}")
            print("📱 Send /start to test the bot")
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
            
            # Stop polling first
            if hasattr(self.application, 'updater') and self.application.updater:
                if self.application.updater.running:
                    await self.application.updater.stop()
            
            # Stop application
            if self.application.running:
                await self.application.stop()
            
            # Shutdown
            await self.application.shutdown()
            print("✅ Bot stopped successfully")
            
        except Exception as e:
            print(f"⚠️ Error during bot shutdown: {e}")
    
    def is_running(self):
        """Check if bot is running"""
        return self._running and hasattr(self.application, 'updater') and self.application.updater and self.application.updater.running
    
    def setup_handlers(self):
        """Setup basic handlers"""
        try:
            print("🔧 Setting up bot handlers...")
            
            # Add error handler
            self.application.add_error_handler(self.error_handler)
            
            # Command handlers
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CommandHandler("help", self.help_command))
            
            # Callback query handler
            self.application.add_handler(CallbackQueryHandler(self.handle_callback))
            
            print("✅ All handlers set up successfully!")
            
        except Exception as e:
            print(f"❌ Error setting up handlers: {e}")
            import traceback
            traceback.print_exc()
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error("Exception while handling an update:", exc_info=context.error)
        
        if isinstance(context.error, asyncio.CancelledError):
            logger.debug("Task was cancelled (normal during shutdown)")
            return
        
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ An error occurred. Please try again or use /start to restart."
                )
            except Exception:
                pass
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id == Config.ADMIN_ID or is_admin(user_id)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        print(f"👤 /start command from User ID: {user_id}, Username: @{username}")
        
        if self.is_admin(user_id):
            await self.show_admin_panel(update, context)
        else:
            await update.message.reply_text(
                "🚫 <b>Access Denied</b>\n\n"
                "You are not authorized to use this bot.\n"
                "Contact the administrator for access.",
                parse_mode=ParseMode.HTML
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        
        if self.is_admin(user_id):
            help_text = """
🤖 <b>Admin Commands</b>

/start - Show admin panel
/help - Show this help message

<b>Admin Panel Features:</b>
• 👥 Manage subscribers
• ⚙️ Configure scanner settings
• 📊 View system status
• 🔧 Control scanner operation
            """
        else:
            help_text = """
🤖 <b>Crypto Scanner Bot</b>

This bot provides real-time cryptocurrency market signals.

Contact the administrator for access.
            """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
    async def show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin control panel"""
        try:
            # Get system status
            system_status = settings_manager.get_system_status()
            scanner_status = db.get_scanner_status()
            
            # Create status message
            message = "🤖 <b>Admin Control Panel</b>\n\n"
            
            # Scanner status
            status_emoji = "🟢" if scanner_status['is_running'] else "🔴"
            message += f"{status_emoji} <b>Scanner Status:</b> {'Running' if scanner_status['is_running'] else 'Stopped'}\n"
            
            # System info
            message += f"📊 <b>Monitored Pairs:</b> {len(system_status['monitored_pairs'])}\n"
            message += f"👥 <b>Active Subscribers:</b> {len([s for s in db.get_subscribers_info() if s['is_active']])}\n"
            
            # Thresholds
            thresholds = system_status['thresholds']
            message += f"\n📈 <b>Current Thresholds:</b>\n"
            message += f"• Pump: {thresholds['pump']}%\n"
            message += f"• Dump: {thresholds['dump']}%\n"
            message += f"• Breakout: {thresholds['breakout']}%\n"
            message += f"• Volume: {thresholds['volume']}%\n"
            
            # Recent activity
            if scanner_status.get('last_scan'):
                last_scan = datetime.fromisoformat(scanner_status['last_scan'])
                message += f"\n⏰ <b>Last Scan:</b> {last_scan.strftime('%H:%M:%S')}\n"
            
            if scanner_status.get('signals_sent_today', 0) > 0:
                message += f"📡 <b>Signals Today:</b> {scanner_status['signals_sent_today']}\n"
            
            # Create keyboard
            keyboard = [
                [
                    InlineKeyboardButton("👥 Subscribers", callback_data="manage_subscribers"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="settings")
                ],
                [
                    InlineKeyboardButton("📊 Status", callback_data="system_status"),
                    InlineKeyboardButton("🔄 Control", callback_data="scanner_control")
                ],
                [
                    InlineKeyboardButton("📈 Signals", callback_data="recent_signals"),
                    InlineKeyboardButton("🔧 Advanced", callback_data="advanced_settings")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
                
        except Exception as e:
            logger.error(f"Error showing admin panel: {e}")
            error_message = "❌ Error loading admin panel. Please try again."
            if update.message:
                await update.message.reply_text(error_message)
            else:
                await update.callback_query.edit_message_text(error_message)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(query.from_user.id):
            await query.edit_message_text("🚫 Access Denied")
            return
        
        data = query.data
        
        if data == "manage_subscribers":
            await self.show_subscribers_management(query, context)
        elif data == "settings":
            await self.show_settings_menu(query, context)
        elif data == "system_status":
            await self.show_system_status(query, context)
        elif data == "scanner_control":
            await self.show_scanner_control(query, context)
        elif data == "recent_signals":
            await self.show_recent_signals(query, context)
        elif data == "back_to_main":
            # Convert callback query to update-like object for admin panel
            fake_update = type('obj', (object,), {
                'callback_query': query,
                'message': None
            })()
            await self.show_admin_panel(fake_update, context)
        else:
            await query.edit_message_text(f"Feature '{data}' coming soon!")
    
    # Placeholder methods for menu displays
    async def show_subscribers_management(self, query, context):
        message = "👥 <b>Subscriber Management</b>\n\nFeature coming soon!"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    
    async def show_settings_menu(self, query, context):
        message = "⚙️ <b>Settings</b>\n\nFeature coming soon!"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    
    async def show_system_status(self, query, context):
        try:
            system_status = settings_manager.get_system_status()
            scanner_status = db.get_scanner_status()
            
            message = "📊 <b>System Status</b>\n\n"
            message += f"🔄 Scanner: {'🟢 Running' if scanner_status['is_running'] else '🔴 Stopped'}\n"
            message += f"📈 Monitored Pairs: {len(system_status['monitored_pairs'])}\n"
            message += f"👥 Active Subscribers: {len([s for s in db.get_subscribers_info() if s['is_active']])}\n"
            
            if scanner_status.get('last_scan'):
                last_scan = datetime.fromisoformat(scanner_status['last_scan'])
                message += f"⏰ Last Scan: {last_scan.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            message += f"📡 Signals Today: {scanner_status.get('signals_sent_today', 0)}\n"
            
        except Exception as e:
            message = f"❌ Error loading system status: {e}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    
    async def show_scanner_control(self, query, context):
        message = "🔄 <b>Scanner Control</b>\n\nFeature coming soon!"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    
    async def show_recent_signals(self, query, context):
        try:
            recent_signals = db.get_recent_signals(limit=10)
            
            message = "📈 <b>Recent Signals</b>\n\n"
            
            if recent_signals:
                for signal in recent_signals:
                    signal_time = datetime.fromisoformat(signal['timestamp']).strftime('%H:%M:%S')
                    message += f"• {signal_time} - {signal['symbol']} ({signal['signal_type']})\n"
            else:
                message += "No recent signals found."
                
        except Exception as e:
            message = f"❌ Error loading recent signals: {e}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)