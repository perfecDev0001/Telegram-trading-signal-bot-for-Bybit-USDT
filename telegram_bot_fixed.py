import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from config import Config
from database import db
from enhanced_scanner import enhanced_scanner
from settings_manager import settings_manager, is_admin

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(WAITING_ADD_SUBSCRIBER, WAITING_REMOVE_SUBSCRIBER,
 WAITING_THRESHOLD_CHANGE, WAITING_PAIR_ADD, WAITING_PAIR_REMOVE,
 WAITING_TP_MULTIPLIERS) = range(6)

class TelegramBot:
    def __init__(self):
        try:
            # Create application with proper configuration for v20.8
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
            
            # Quick bot test
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
    
    async def restart_if_needed(self):
        """Restart bot if it's not responsive"""
        try:
            if not self.is_running():
                print("🔄 Bot not running, attempting restart...")
                await self.stop_bot()
                await asyncio.sleep(5)
                return await self.start_bot()
            else:
                # Test bot responsiveness
                try:
                    await asyncio.wait_for(self.application.bot.get_me(), timeout=10)
                    return True
                except Exception:
                    print("🔄 Bot not responsive, restarting...")
                    await self.stop_bot()
                    await asyncio.sleep(5)
                    return await self.start_bot()
        except Exception as e:
            print(f"❌ Error during bot restart: {e}")
            return False
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors that occur during bot operation"""
        # Log the error
        logger.error("Exception while handling an update:", exc_info=context.error)
        
        # Don't print CancelledError as it's expected during shutdown
        if isinstance(context.error, asyncio.CancelledError):
            logger.debug("Task was cancelled (normal during shutdown)")
            return
        
        # Try to inform user about error if possible
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ An error occurred. Please try again or use /start to restart."
                )
            except Exception:
                pass  # Ignore if we can't send error message
    
    def setup_handlers(self):
        """Setup all command and callback handlers"""
        try:
            print("🔧 Setting up bot handlers...")
            
            # Add error handler first
            self.application.add_error_handler(self.error_handler)
            print("   ✅ Error handler added")
            
            # Command handlers - these should be prioritized
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CommandHandler("help", self.help_command))
            print("   ✅ Command handlers added (/start, /help)")
            
            # Conversation handler for user input (must be added before general callback handler)
            conv_handler = ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(self.start_conversation, pattern="^(settings_add_pair|settings_remove_pair|settings_tp_multipliers|threshold_.*)$"),
                    CallbackQueryHandler(self.handle_callback, pattern="^(subscribers_add|subscribers_remove)$")
                ],
                states={
                    WAITING_ADD_SUBSCRIBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_subscriber_callback)],
                    WAITING_REMOVE_SUBSCRIBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.remove_subscriber_callback)],
                    WAITING_THRESHOLD_CHANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.change_threshold_callback)],
                    WAITING_PAIR_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.add_pair_callback)],
                    WAITING_PAIR_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.remove_pair_callback)],
                    WAITING_TP_MULTIPLIERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.tp_multipliers_callback)],
                },
                fallbacks=[
                    CommandHandler("cancel", self.cancel),
                    CallbackQueryHandler(self.cancel_conversation, pattern="^(back_to_main|manage_subscribers|settings|settings_pairs)$")
                ],
                per_chat=True,
                per_user=True,
                name="admin_conversation"
            )
            self.application.add_handler(conv_handler)
            print("   ✅ Conversation handler added")
            
            # General callback query handlers (excluding conversation entry points)
            self.application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^(?!(subscribers_add|subscribers_remove)$).*$"))
            print("   ✅ Callback query handlers added")
            
            # General message handler (lowest priority)
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            print("   ✅ General message handler added")
            
            print("✅ All handlers set up successfully!")
            
        except Exception as e:
            print(f"❌ Error setting up handlers: {e}")
            import traceback
            traceback.print_exc()
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id == Config.ADMIN_ID or is_admin(user_id)
    
    def is_subscriber(self, user_id: int) -> tuple:
        """Check if user is a subscriber and return subscriber info"""
        try:
            subscribers = db.get_subscribers_info()
            for subscriber in subscribers:
                if subscriber['user_id'] == user_id and subscriber['is_active']:
                    return True, subscriber
            return False, None
        except Exception as e:
            logger.error(f"Error checking subscriber status: {e}")
            return False, None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        username = update.effective_user.username or "Unknown"
        
        print(f"👤 /start command from User ID: {user_id}, Username: @{username}")
        
        if self.is_admin(user_id):
            await self.show_admin_panel(update, context)
        else:
            is_sub, sub_info = self.is_subscriber(user_id)
            if is_sub:
                await self.show_subscriber_panel(update, context, sub_info)
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

<b>Scanner Features:</b>
• 🚀 Pump detection
• 📉 Dump detection  
• 💥 Breakout signals
• 📈 Volume spikes
• 🎯 Take profit levels
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
                    InlineKeyboardButton("👥 Manage Subscribers", callback_data="manage_subscribers"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="settings")
                ],
                [
                    InlineKeyboardButton("📊 System Status", callback_data="system_status"),
                    InlineKeyboardButton("🔄 Scanner Control", callback_data="scanner_control")
                ],
                [
                    InlineKeyboardButton("📈 Recent Signals", callback_data="recent_signals"),
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
    
    async def show_subscriber_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, sub_info: dict):
        """Show subscriber panel"""
        message = f"👋 <b>Welcome, {sub_info.get('username', 'Subscriber')}!</b>\n\n"
        message += "📊 <b>Your Subscription Status:</b>\n"
        message += f"• Status: {'✅ Active' if sub_info['is_active'] else '❌ Inactive'}\n"
        message += f"• Signals Received: {sub_info.get('signals_received', 0)}\n"
        
        # Get recent signals for this subscriber
        try:
            recent_signals = db.get_recent_signals(limit=5)
            if recent_signals:
                message += f"\n📈 <b>Recent Signals:</b>\n"
                for signal in recent_signals[:3]:
                    signal_time = datetime.fromisoformat(signal['timestamp']).strftime('%H:%M')
                    message += f"• {signal_time} - {signal['symbol']} ({signal['signal_type']})\n"
        except Exception:
            pass
        
        keyboard = [
            [InlineKeyboardButton("📊 View Recent Signals", callback_data="subscriber_signals")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="subscriber_help")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    
    # Add placeholder methods for the handlers referenced in setup_handlers
    async def start_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start conversation placeholder"""
        await update.callback_query.answer("Feature coming soon!")
        return ConversationHandler.END
    
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
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("🚫 Access Denied. Use /start to begin.")
            return
        
        # For now, just redirect to admin panel
        await self.show_admin_panel(update, context)
    
    # Placeholder methods for conversation handlers
    async def add_subscriber_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Feature coming soon!")
        return ConversationHandler.END
    
    async def remove_subscriber_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Feature coming soon!")
        return ConversationHandler.END
    
    async def change_threshold_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Feature coming soon!")
        return ConversationHandler.END
    
    async def add_pair_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Feature coming soon!")
        return ConversationHandler.END
    
    async def remove_pair_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Feature coming soon!")
        return ConversationHandler.END
    
    async def tp_multipliers_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Feature coming soon!")
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END
    
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer("Operation cancelled.")
        return ConversationHandler.END
    
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

# Create global instance
telegram_bot = None

def get_telegram_bot():
    """Get or create telegram bot instance"""
    global telegram_bot
    if telegram_bot is None:
        telegram_bot = TelegramBot()
    return telegram_bot