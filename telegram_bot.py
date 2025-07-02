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
        self.application = Application.builder().token(Config.BOT_TOKEN).build()
        self.setup_handlers()
        self._running = False
    
    async def start_bot(self):
        """Start the bot with proper error handling"""
        try:
            print("🤖 Initializing bot...")
            await self.application.initialize()
            
            print("🚀 Starting bot...")
            await self.application.start()
            
            print("📡 Starting polling...")
            await self.application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
            
            self._running = True
            print("✅ Bot is running!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
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
        return self._running
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors that occur during bot operation"""
        # Log the error
        logger.error("Exception while handling an update:", exc_info=context.error)
        
        # Don't print CancelledError as it's expected during shutdown
        if isinstance(context.error, asyncio.CancelledError):
            logger.debug("Task was cancelled (normal during shutdown)")
            return
        
        # For other errors, we can try to inform the user
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="⚠️ An error occurred while processing your request. Please try again."
                )
            except Exception:
                # If we can't send the error message, just log it
                logger.error("Could not send error message to user")
    
    def setup_handlers(self):
        """Setup all command and callback handlers"""
        
        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
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
                CallbackQueryHandler(self.cancel_conversation, pattern="^(back_to_main|manage_subscribers)$")
            ],
            per_chat=True,
            per_user=True,
            name="admin_conversation"
        )
        self.application.add_handler(conv_handler)
        
        # General callback query handlers (excluding conversation entry points)
        self.application.add_handler(CallbackQueryHandler(self.handle_callback, pattern="^(?!(subscribers_add|subscribers_remove)$).*$"))
        
        # General message handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id == Config.ADMIN_ID or is_admin(user_id)
    
    def get_panel_image_path(self) -> str:
        """Get the path to the panel image"""
        return os.path.join(os.path.dirname(__file__), "image", "Bybit_4.jpg")
    
    async def start_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start conversation based on callback data"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(query.from_user.id):
            await query.edit_message_text("🚫 Access Denied")
            return ConversationHandler.END
        
        data = query.data
        
        # Handle settings callbacks that need conversation
        if data.startswith("settings_"):
            return await self.handle_settings_callback(query, data)
        elif data.startswith("threshold_"):
            return await self.handle_threshold_callback(query, data)
        
        return ConversationHandler.END
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(query.from_user.id):
            await query.edit_message_text("🚫 Access Denied")
            return
        
        data = query.data
        
        # Handle subscriber-related callbacks directly
        if data == "subscribers_add":
            # Start the add subscriber conversation
            message = "✏️ <b>Add New Subscriber</b>\n\n"
            message += "Please send the Telegram User ID as your next message.\n"
            message += "You can get user ID from @userinfobot\n\n"
            message += "<b>Example:</b> <code>123456789</code>"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="manage_subscribers")]]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            context.user_data['waiting_for'] = 'add_subscriber'
            return WAITING_ADD_SUBSCRIBER
            
        elif data == "subscribers_remove":
            # Start the remove subscriber conversation
            subscribers = db.get_subscribers_info()
            
            if not subscribers:
                message = "❌ <b>No Subscribers Found</b>\n\nThere are no subscribers to remove."
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="manage_subscribers")]]
                
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
                return
            
            message = "🗑️ <b>Remove Subscriber</b>\n\n"
            message += "Current subscribers:\n"
            
            for sub in subscribers[:10]:  # Show first 10
                status = "✅" if sub['is_active'] else "❌"
                username = f"@{sub['username']}" if sub['username'] else "No username"
                message += f"• {status} <code>{sub['user_id']}</code> ({username})\n"
            
            if len(subscribers) > 10:
                message += f"... and {len(subscribers) - 10} more\n"
            
            message += "\nPlease type the Telegram ID to remove:"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="manage_subscribers")]]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            context.user_data['waiting_for'] = 'remove_subscriber'
            return WAITING_REMOVE_SUBSCRIBER
            
        elif data == "subscribers_view_all":
            return await self.show_all_subscribers(query)
        elif data == "subscribers_export":
            return await self.export_subscribers(query)
        
        # Skip other conversation entry points - they should be handled by ConversationHandler
        conversation_entry_points = [
            "settings_add_pair", "settings_remove_pair", "settings_tp_multipliers",
            "threshold_"
        ]
        
        if any(data.startswith(prefix) for prefix in conversation_entry_points):
            # These are handled by the conversation handler
            return
        
        # Main menu callbacks
        if data == "scanner_status":
            await self.show_scanner_status(query)
        elif data == "signals_log":
            await self.show_signals_log(query)
        elif data == "settings":
            await self.show_settings(query)
        elif data == "manage_subscribers":
            await self.show_manage_subscribers(query)
        elif data == "pause_scanner":
            await self.pause_scanner(query)
        elif data == "resume_scanner":
            await self.resume_scanner(query)
        elif data == "logout":
            await self.logout(query)
        elif data == "back_to_main":
            await self.back_to_main(query)
        elif data == "main_menu":
            await self.back_to_main(query)
        elif data == "settings_thresholds":
            await self.show_threshold_settings(query)
        elif data == "settings_features":
            await self.show_feature_settings(query)
        elif data == "settings_pairs":
            await self.show_pairs_settings(query)
        elif data.startswith("settings_") and not any(data == ep for ep in ["settings_add_pair", "settings_remove_pair", "settings_tp_multipliers"]):
            await self.handle_settings_callback(query, data)
        elif data.startswith("filter_"):
            await self.handle_filter_toggle(query, data)
        elif data == "export_log":
            await self.export_signals_log(query)
        elif data.startswith("advanced_"):
            await self.handle_advanced_settings(query, data)
        elif data == "live_monitor":
            await self.show_live_monitor(query)
        elif data == "force_scan":
            await self.force_scan(query)
        elif data == "help_menu":
            await self.show_help_menu(query)
        elif data == "restart_session":
            await self.restart_session(query)
    
    async def show_manage_subscribers(self, query):
        """Show subscriber management menu"""
        subscribers = db.get_subscribers_info()
        
        message = f"👥 <b>Subscribers Management</b>\n\n"
        message += f"📊 <b>Total Subscribers:</b> {len(subscribers)}\n"
        message += f"✅ <b>Active Subscribers:</b> {len([s for s in subscribers if s['is_active']])}\n\n"
        
        # Show first few subscribers as preview
        active_subs = [sub for sub in subscribers if sub['is_active']]
        if active_subs:
            message += f"<b>Recent Active Subscribers:</b>\n"
            for i, sub in enumerate(active_subs[:5]):  # Show first 5
                username_text = f"@{sub['username']}" if sub['username'] else "No username"
                name_text = sub['first_name'] or "No name"
                message += f"• {sub['user_id']} ({username_text}) - {name_text}\n"
            
            if len(active_subs) > 5:
                message += f"... and {len(active_subs) - 5} more\n"
        else:
            message += "• No active subscribers\n"
        
        keyboard = [
            [
                InlineKeyboardButton("➕ Add Subscriber", callback_data="subscribers_add"),
                InlineKeyboardButton("➖ Remove Subscriber", callback_data="subscribers_remove")
            ],
            [
                InlineKeyboardButton("👁️ View All", callback_data="subscribers_view_all"),
                InlineKeyboardButton("📄 Export List", callback_data="subscribers_export")
            ],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_main")]
        ]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def show_all_subscribers(self, query):
        """Show detailed list of all subscribers"""
        try:
            subscribers = db.get_subscribers_info()
            
            if not subscribers:
                message = "👥 <b>All Subscribers</b>\n\n❌ No subscribers found."
            else:
                message = f"👥 <b>All Subscribers ({len(subscribers)} total)</b>\n\n"
                active_count = 0
                
                for i, sub in enumerate(subscribers, 1):
                    status_emoji = "✅" if sub['is_active'] else "❌"
                    username_text = f"@{sub['username']}" if sub['username'] else "No username"
                    name_text = sub['first_name'] or "No name"
                    
                    message += f"{i}. {status_emoji} <code>{sub['user_id']}</code>\n"
                    message += f"   👤 {name_text}\n"
                    message += f"   📱 {username_text}\n"
                    message += f"   📅 Added: {sub['added_date']}\n\n"
                    
                    if sub['is_active']:
                        active_count += 1
                    
                    if len(message) > 3500:
                        remaining = len(subscribers) - i
                        if remaining > 0:
                            message += f"... and {remaining} more subscribers\n"
                        break
                
                message += f"📊 <b>Summary:</b> {active_count} active of {len(subscribers)} total"
            
            keyboard = [
                [
                    InlineKeyboardButton("➕ Add Subscriber", callback_data="subscribers_add"),
                    InlineKeyboardButton("➖ Remove Subscriber", callback_data="subscribers_remove")
                ],
                [
                    InlineKeyboardButton("📄 Export List", callback_data="subscribers_export"),
                    InlineKeyboardButton("🔙 Back", callback_data="manage_subscribers")
                ]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            await query.edit_message_text(
                "❌ <b>Error</b>\n\nFailed to load subscribers list.",
                parse_mode=ParseMode.HTML
            )
    
    async def handle_subscribers_callback(self, query, data):
        """Handle subscriber-related callbacks - this is now handled directly in handle_callback"""
        # This method is kept for backward compatibility but is no longer used
        return ConversationHandler.END
    
    async def add_subscriber_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle add subscriber input"""
        try:
            user_id = int(update.message.text.strip())
            
            # Try to get user info
            try:
                chat = await context.bot.get_chat(user_id)
                username = chat.username
                first_name = chat.first_name
                last_name = chat.last_name
            except Exception:
                username = None
                first_name = None
                last_name = None
            
            success = db.add_subscriber(user_id, username, first_name, last_name)
            
            if success:
                message = f"✅ <b>Subscriber Added!</b>\n\n"
                message += f"User ID: <code>{user_id}</code>\n"
                if username:
                    message += f"Username: @{username}\n"
                if first_name:
                    message += f"Name: {first_name} {last_name or ''}\n"
                message += f"\nThey will now receive trading signals!"
            else:
                message = f"❌ <b>Failed to add subscriber {user_id}</b>\n\nPlease try again or check the user ID."
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid Input</b>\n\n"
                "Please enter a valid numeric Telegram User ID.\n\n"
                "<b>Example:</b> <code>123456789</code>",
                parse_mode=ParseMode.HTML
            )
        
        return ConversationHandler.END
    
    async def remove_subscriber_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle remove subscriber input"""
        try:
            user_id = int(update.message.text.strip())
            
            success = db.remove_subscriber(user_id)
            
            if success:
                message = f"✅ <b>Subscriber Removed!</b>\n\n"
                message += f"User ID <code>{user_id}</code> has been removed from the subscriber list."
            else:
                message = f"❌ <b>Subscriber Not Found</b>\n\n"
                message += f"User ID <code>{user_id}</code> was not found in the subscriber list."
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid Input</b>\n\n"
                "Please enter a valid numeric Telegram User ID.\n\n"
                "<b>Example:</b> <code>123456789</code>",
                parse_mode=ParseMode.HTML
            )
        
        return ConversationHandler.END
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current conversation"""
        await update.message.reply_text(
            "❌ <b>Operation Cancelled</b>\n\n"
            "Current operation has been cancelled.\n\n"
            "Use /start to return to the main admin panel.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation via callback query"""
        query = update.callback_query
        await query.answer()
        
        # Handle the callback normally (back to main or manage subscribers)
        if query.data == "back_to_main":
            await self.back_to_main(query)
        elif query.data == "manage_subscribers":
            await self.show_manage_subscribers(query)
        
        return ConversationHandler.END
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        if not self.is_admin(user.id):
            await update.message.reply_text(
                "🚫 <b>Access Denied</b>\n\n"
                "You are not authorized to use this bot.\n"
                "Only the admin can access this bot's features.",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Show admin panel
        keyboard = self.get_admin_keyboard()
        
        welcome_message = f"""
🤖 <b>Bybit Scanner Bot - Admin Panel</b>

Welcome, <b>{user.first_name}</b>! 👋

🎛️ <b>Control Panel:</b>
• Monitor trading signals in real-time
• Configure scanner settings and thresholds
• Manage subscriber notifications  
• Control scanner operation

Choose an option from the menu below:
        """.strip()
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    def get_admin_keyboard(self) -> InlineKeyboardMarkup:
        """Get admin panel keyboard with new layout"""
        scanner_status = db.get_scanner_status()
        is_running = scanner_status.get('is_running', True)
        
        keyboard = [
            # Row 1: Scanner Status | Signals Log
            [
                InlineKeyboardButton("📊 Scanner Status", callback_data="scanner_status"),
                InlineKeyboardButton("📈 Signals Log", callback_data="signals_log")
            ],
            # Row 2: Live Monitor | System Status
            [
                InlineKeyboardButton("📊 Live Monitor", callback_data="live_monitor"),
                InlineKeyboardButton("🖥 System Status", callback_data="advanced_system_status")
            ],
            # Row 3: Settings | Force Scan
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                InlineKeyboardButton("⚡ Force Scan", callback_data="force_scan")
            ],
            # Row 4: Logout | Pause Scanner
            [
                InlineKeyboardButton("🚪 Logout", callback_data="logout"),
                InlineKeyboardButton("⏸ Pause Scanner" if is_running else "▶️ Resume Scanner", 
                                   callback_data="pause_scanner" if is_running else "resume_scanner")
            ],
            # Row 5: Manage Subscribers | Help
            [
                InlineKeyboardButton("👥 Manage Subscribers", callback_data="manage_subscribers"),
                InlineKeyboardButton("❓ Help", callback_data="help_menu")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("🚫 Access Denied")
            return
        
        help_text = """
🤖 <b>Bybit Scanner Bot - Help</b>

<b>Available Commands:</b>
• /start - Show main admin panel
• /help - Show this help message
• /cancel - Cancel current operation

<b>Features:</b>
• 📊 Real-time market scanning
• 🔔 Subscriber management
• ⚙️ Configurable settings
• 📈 Signal logging and export
• 🎯 Custom thresholds

<b>Admin Functions:</b>
• Add/remove subscribers
• Configure scanner parameters
• Monitor system status
• Export data and logs

Use /start to access the main control panel.
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    
    async def show_help_menu(self, query):
        """Show help menu with project overview and admin panel usage"""
        help_text = """
🚀 <b>Enhanced Bybit Scanner Bot - Help</b>

<b>📋 Project Overview:</b>
A comprehensive Python-based Telegram trading signal bot for Bybit USDT Perpetuals with advanced market analysis, multi-layered filtering, and real-time alerts.

<b>✨ Core Features:</b>
• 🔍 Real-time Market Scanning (1-minute intervals)
• 🧠 Advanced Signal Detection (10+ layered filters)
• 📱 Telegram Integration with automated alerts
• ⚙️ Complete Admin Panel with full control
• ☁️ Cloud Optimized for 24/7 deployment
• 🎯 High Accuracy (≥70% confidence signals only)

<b>🎛️ Admin Panel Usage:</b>

<b>📊 Scanner Status</b> - View real-time scanner status and statistics
<b>📈 Signals Log</b> - Review recent trading signals and export logs
<b>📊 Live Monitor</b> - Monitor top trading pairs in real-time
<b>🖥 System Status</b> - Check system health and performance

<b>⚙️ Settings</b> - Configure thresholds, filters, and trading pairs
<b>⚡ Force Scan</b> - Manually trigger market scan
<b>👥 Manage Subscribers</b> - Add/remove Telegram users
<b>⏸ Pause Scanner</b> - Temporarily stop/start scanning

<b>🎯 Signal Recipients:</b>
• Admin: @dream_code_star (ID: 7974254350)
• User: @space_ion99 (ID: 7452976451)
• Private Channel: -1002674839519

<b>💡 Quick Tips:</b>
• Only signals with ≥70% strength are sent
• Scanner monitors 1-minute intervals automatically
• Use Force Scan to test signal detection
• Export logs for analysis and reporting
        """.strip()
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]]
        
        await query.edit_message_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle general text messages"""
        if not self.is_admin(update.effective_user.id):
            return
        
        await update.message.reply_text(
            "ℹ️ Use /start to access the admin panel or /help for assistance.",
            parse_mode=ParseMode.HTML
        )
    
    async def back_to_main(self, query):
        """Return to main admin panel"""
        keyboard = self.get_admin_keyboard()
        
        message = """
🤖 <b>Bybit Scanner Bot - Admin Panel</b>

🎛️ <b>Control Panel:</b>
• Monitor trading signals in real-time
• Configure scanner settings and thresholds
• Manage subscriber notifications  
• Control scanner operation

Choose an option from the menu below:
        """.strip()
        
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    # Placeholder methods for other callbacks
    async def show_scanner_status(self, query):
        """Show current scanner status and statistics"""
        try:
            # Get scanner status from database
            scanner_status = db.get_scanner_status()
            is_running = scanner_status.get('is_running', True)
            last_scan = scanner_status.get('last_scan', 'Never')
            
            # Format last scan time
            if last_scan and last_scan != 'Never':
                try:
                    # Convert ISO format to datetime
                    from datetime import datetime
                    last_scan_dt = datetime.fromisoformat(last_scan)
                    last_scan = last_scan_dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    pass
            
            # Get monitored pairs
            monitored_pairs_str = scanner_status.get('monitored_pairs', '[]')
            try:
                import json
                monitored_pairs = json.loads(monitored_pairs_str)
                pairs_count = len(monitored_pairs)
                pairs_preview = ', '.join(monitored_pairs[:5])
                if len(monitored_pairs) > 5:
                    pairs_preview += f" and {len(monitored_pairs) - 5} more"
            except:
                pairs_count = 0
                pairs_preview = "None"
            
            # Get thresholds
            pump_threshold = scanner_status.get('pump_threshold', 5.0)
            dump_threshold = scanner_status.get('dump_threshold', -5.0)
            breakout_threshold = scanner_status.get('breakout_threshold', 3.0)
            volume_threshold = scanner_status.get('volume_threshold', 50.0)
            
            # Get recent signals
            recent_signals = db.get_recent_signals(5)
            signals_count = len(recent_signals)
            
            # Build status message with timestamp to ensure uniqueness
            current_time = datetime.now().strftime('%H:%M:%S')
            status_message = f"""
📊 <b>Scanner Status</b>

<b>Current Status:</b> {'🟢 RUNNING' if is_running else '🔴 PAUSED'}
<b>Last Scan:</b> {last_scan}
<b>Last Updated:</b> {current_time} UTC
<b>Monitored Pairs:</b> {pairs_count} pairs
<b>Pairs:</b> {pairs_preview}

<b>Signal Thresholds:</b>
• Pump: {pump_threshold}%
• Dump: {dump_threshold}%
• Breakout: {breakout_threshold}%
• Volume: {volume_threshold}%

<b>Recent Signals:</b> {signals_count} signals
"""
            
            # Add recent signals if any
            if signals_count > 0:
                status_message += "\n<b>Latest Signals:</b>"
                for signal in recent_signals:
                    signal_time = signal.get('timestamp', '')
                    if signal_time:
                        try:
                            # Convert to readable format
                            from datetime import datetime
                            signal_time = datetime.fromisoformat(signal_time.replace('Z', '+00:00'))
                            signal_time = signal_time.strftime('%m-%d %H:%M')
                        except:
                            pass
                    
                    status_message += f"\n• {signal_time} {signal.get('symbol', '')} {signal.get('signal_type', '')}: {signal.get('change_percent', 0):.2f}%"
            
            # Create keyboard with control buttons
            keyboard = [
                [
                    InlineKeyboardButton("⏸ Pause Scanner" if is_running else "▶️ Resume Scanner", 
                                      callback_data="pause_scanner" if is_running else "resume_scanner")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Status", callback_data="scanner_status")
                ],
                [
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]
            ]
            
            await query.edit_message_text(
                status_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            print(f"Error showing scanner status: {e}")
            await query.edit_message_text(
                f"❌ Error showing scanner status: {e}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]])
            )
    
    async def show_signals_log(self, query):
        """Show recent signals log"""
        try:
            # Get recent signals from database (last 10)
            recent_signals = db.get_recent_signals(10)
            signals_count = len(recent_signals)
            
            # Add timestamp to ensure message uniqueness
            current_time = datetime.now().strftime('%H:%M:%S')
            if signals_count == 0:
                message = f"""
📈 <b>Signals Log</b>

No signals have been generated yet.
The scanner will generate signals when market conditions meet the criteria.

<b>Last Updated:</b> {current_time} UTC
"""
            else:
                message = f"""
📈 <b>Signals Log</b>

Showing the {signals_count} most recent signals:
<b>Last Updated:</b> {current_time} UTC
"""
                
                for signal in recent_signals:
                    signal_time = signal.get('timestamp', '')
                    if signal_time:
                        try:
                            # Convert to readable format
                            from datetime import datetime
                            signal_time = datetime.fromisoformat(signal_time.replace('Z', '+00:00'))
                            signal_time = signal_time.strftime('%Y-%m-%d %H:%M')
                        except:
                            pass
                    
                    symbol = signal.get('symbol', '')
                    signal_type = signal.get('signal_type', '')
                    price = signal.get('price', 0)
                    change = signal.get('change_percent', 0)
                    
                    # Format signal type with emoji
                    if signal_type == 'PUMP':
                        signal_type = '🚀 PUMP'
                    elif signal_type == 'DUMP':
                        signal_type = '📉 DUMP'
                    elif signal_type == 'BREAKOUT_UP':
                        signal_type = '💥 BREAKOUT UP'
                    elif signal_type == 'BREAKOUT_DOWN':
                        signal_type = '💥 BREAKOUT DOWN'
                    
                    message += f"\n• <b>{signal_time}</b> | <b>{symbol}</b> | {signal_type} | ${price:.4f} | {change:+.2f}%"
            
            # Create keyboard with control buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Refresh Log", callback_data="signals_log")
                ],
                [
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]
            ]
            
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            print(f"Error showing signals log: {e}")
            await query.edit_message_text(
                f"❌ Error showing signals log: {e}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]])
            )
    
    async def show_settings(self, query):
        """Show scanner settings"""
        try:
            # Get scanner status from database
            scanner_status = db.get_scanner_status()
            
            # Get thresholds
            pump_threshold = scanner_status.get('pump_threshold', 5.0)
            dump_threshold = scanner_status.get('dump_threshold', -5.0)
            breakout_threshold = scanner_status.get('breakout_threshold', 3.0)
            volume_threshold = scanner_status.get('volume_threshold', 50.0)
            
            # Get feature flags
            whale_tracking = scanner_status.get('whale_tracking', True)
            spoofing_detection = scanner_status.get('spoofing_detection', False)
            spread_filter = scanner_status.get('spread_filter', True)
            trend_match = scanner_status.get('trend_match', True)
            
            # Get TP multipliers
            tp_multipliers_str = scanner_status.get('tp_multipliers', '[1.5, 3.0, 5.0, 7.5]')
            try:
                import json
                tp_multipliers = json.loads(tp_multipliers_str)
                tp_multipliers_text = ', '.join([f"{m}x" for m in tp_multipliers])
            except:
                tp_multipliers_text = "1.5x, 3.0x, 5.0x, 7.5x"
            
            # Build settings message
            settings_message = f"""
⚙️ <b>Scanner Settings</b>

<b>Signal Thresholds:</b>
• Pump: {pump_threshold}%
• Dump: {dump_threshold}%
• Breakout: {breakout_threshold}%
• Volume: {volume_threshold}%

<b>Take Profit Targets:</b>
• Multipliers: {tp_multipliers_text}

<b>Advanced Features:</b>
• Whale Activity Tracking: {'✅ Enabled' if whale_tracking else '❌ Disabled'}
• Spoofing Detection: {'✅ Enabled' if spoofing_detection else '❌ Disabled'}
• Spread Filter: {'✅ Enabled' if spread_filter else '❌ Disabled'}
• Trend Match: {'✅ Enabled' if trend_match else '❌ Disabled'}

<i>Click the buttons below to adjust settings:</i>
"""
            
            # Create keyboard with settings buttons
            keyboard = [
                [
                    InlineKeyboardButton("🎯 Adjust Thresholds", callback_data="settings_thresholds")
                ],
                [
                    InlineKeyboardButton("🔄 Toggle Features", callback_data="settings_features")
                ],
                [
                    InlineKeyboardButton("📋 Manage Pairs", callback_data="settings_pairs")
                ],
                [
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]
            ]
            
            await query.edit_message_text(
                settings_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            print(f"Error showing settings: {e}")
            await query.edit_message_text(
                f"❌ Error showing settings: {e}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]])
            )
    
    async def show_threshold_settings(self, query):
        """Show threshold settings with adjustment buttons"""
        try:
            # Get scanner status from database
            scanner_status = db.get_scanner_status()
            
            # Get thresholds
            pump_threshold = scanner_status.get('pump_threshold', 5.0)
            dump_threshold = scanner_status.get('dump_threshold', -5.0)
            breakout_threshold = scanner_status.get('breakout_threshold', 3.0)
            volume_threshold = scanner_status.get('volume_threshold', 50.0)
            
            # Build settings message
            settings_message = f"""
🎯 <b>Threshold Settings</b>

Adjust the thresholds for signal generation:

<b>Pump Threshold:</b> {pump_threshold}%
<i>Minimum price increase to trigger a PUMP signal</i>

<b>Dump Threshold:</b> {dump_threshold}%
<i>Minimum price decrease to trigger a DUMP signal</i>

<b>Breakout Threshold:</b> {breakout_threshold}%
<i>Minimum price movement to trigger a BREAKOUT signal</i>

<b>Volume Threshold:</b> {volume_threshold}%
<i>Minimum volume increase to consider in signal generation</i>

<i>Note: Changes will apply to future scans</i>
"""
            
            # Create keyboard with adjustment buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")
                ],
                [
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]
            ]
            
            await query.edit_message_text(
                settings_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            print(f"Error showing threshold settings: {e}")
            await query.edit_message_text(
                f"❌ Error showing threshold settings: {e}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")
                ]])
            )
    
    async def show_feature_settings(self, query):
        """Show feature toggle settings"""
        try:
            # Get scanner status from database
            scanner_status = db.get_scanner_status()
            
            # Get feature flags
            whale_tracking = scanner_status.get('whale_tracking', True)
            spoofing_detection = scanner_status.get('spoofing_detection', False)
            spread_filter = scanner_status.get('spread_filter', True)
            trend_match = scanner_status.get('trend_match', True)
            
            # Build settings message
            settings_message = f"""
🔄 <b>Feature Settings</b>

Toggle advanced scanner features:

<b>Whale Activity Tracking:</b> {'✅ Enabled' if whale_tracking else '❌ Disabled'}
<i>Detect large wallet movements and whale activity</i>

<b>Spoofing Detection:</b> {'✅ Enabled' if spoofing_detection else '❌ Disabled'}
<i>Detect order book manipulation and spoofing</i>

<b>Spread Filter:</b> {'✅ Enabled' if spread_filter else '❌ Disabled'}
<i>Filter out signals with excessive bid-ask spread</i>

<b>Trend Match:</b> {'✅ Enabled' if trend_match else '❌ Disabled'}
<i>Ensure signals match the overall market trend</i>

<i>Note: Changes will apply to future scans</i>
"""
            
            # Create keyboard with toggle buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")
                ],
                [
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]
            ]
            
            await query.edit_message_text(
                settings_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            print(f"Error showing feature settings: {e}")
            await query.edit_message_text(
                f"❌ Error showing feature settings: {e}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")
                ]])
            )
    
    async def show_pairs_settings(self, query):
        """Show pairs management settings"""
        try:
            # Get scanner status from database
            scanner_status = db.get_scanner_status()
            
            # Get monitored pairs
            monitored_pairs_str = scanner_status.get('monitored_pairs', '[]')
            try:
                import json
                monitored_pairs = json.loads(monitored_pairs_str)
                pairs_count = len(monitored_pairs)
                pairs_list = '\n'.join([f"• {pair}" for pair in monitored_pairs[:15]])
                if len(monitored_pairs) > 15:
                    pairs_list += f"\n• ... and {len(monitored_pairs) - 15} more"
            except:
                pairs_count = 0
                pairs_list = "None"
            
            # Build settings message
            settings_message = f"""
📋 <b>Pairs Management</b>

Currently monitoring {pairs_count} trading pairs:

{pairs_list}

<i>Note: Changes will apply to future scans</i>
"""
            
            # Create keyboard with management buttons
            keyboard = [
                [
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")
                ],
                [
                    InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
                ]
            ]
            
            await query.edit_message_text(
                settings_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            print(f"Error showing pairs settings: {e}")
            await query.edit_message_text(
                f"❌ Error showing pairs settings: {e}\n\nPlease try again.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings")
                ]])
            )
    
    async def pause_scanner(self, query):
        """Pause the scanner and update the database"""
        try:
            # Update scanner status in the database
            db.update_scanner_status(is_running=False)
            
            # Create a keyboard with the Resume button and Back button
            keyboard = [
                [InlineKeyboardButton("▶️ Resume Scanner", callback_data="resume_scanner")]
            ]
            keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")])
            
            await query.edit_message_text(
                "⏸ <b>Scanner Paused!</b>\n\n"
                "The scanner has been paused and will not generate any signals.\n"
                "Click 'Resume Scanner' to start scanning again.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            print("Scanner paused by admin")
        except Exception as e:
            print(f"Error pausing scanner: {e}")
            await query.edit_message_text(f"❌ Error pausing scanner: {e}")
    
    async def resume_scanner(self, query):
        """Resume the scanner and update the database"""
        try:
            # Update scanner status in the database
            db.update_scanner_status(is_running=True)
            
            # Create a keyboard with the Pause button and Back button
            keyboard = [
                [InlineKeyboardButton("⏸ Pause Scanner", callback_data="pause_scanner")]
            ]
            keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")])
            
            await query.edit_message_text(
                "▶️ <b>Scanner Resumed!</b>\n\n"
                "The scanner is now running and will generate signals.\n"
                "Click 'Pause Scanner' to stop scanning.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
            print("Scanner resumed by admin")
        except Exception as e:
            print(f"Error resuming scanner: {e}")
            await query.edit_message_text(f"❌ Error resuming scanner: {e}")
    
    async def logout(self, query):
        """Handle logout with restart option"""
        keyboard = [[InlineKeyboardButton("🔄 Restart", callback_data="restart_session")]]
        
        await query.edit_message_text(
            "👋 Logged out. Use /start to return.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def restart_session(self, query):
        """Restart the admin session - return to main panel"""
        keyboard = self.get_admin_keyboard()
        
        welcome_message = f"""
🤖 <b>Bybit Scanner Bot - Admin Panel</b>

Welcome back! 👋

🎛️ <b>Control Panel:</b>
• Monitor trading signals in real-time
• Configure scanner settings and thresholds
• Manage subscriber notifications  
• Control scanner operation

Choose an option from the menu below:
        """.strip()
        
        await query.edit_message_text(
            welcome_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    async def handle_settings_callback(self, query, data):
        """Handle settings menu navigation"""
        try:
            if data == "settings_thresholds":
                await self.show_threshold_settings(query)
            elif data == "settings_pairs":
                await self.show_pairs_settings(query)
            elif data == "settings_features":
                await self.show_feature_settings(query)
            elif data == "settings_advanced":
                await self.handle_advanced_settings(query, data)
            else:
                await query.edit_message_text("⚙️ Unknown settings option!")
        except Exception as e:
            await query.edit_message_text(f"❌ Settings error: {e}")
    
    async def handle_threshold_callback(self, query, data):
        """Handle threshold-related callbacks"""
        try:
            if data == "threshold_pump":
                context = {"threshold_type": "pump"}
                await query.edit_message_text(
                    "🚀 **Set Pump Threshold**\n\n"
                    "Enter new pump threshold percentage (e.g., `pump 7.5`):\n\n"
                    "Current value: 5.0%\n"
                    "Valid range: 0.1% to 50.0%",
                    parse_mode='Markdown'
                )
            elif data == "threshold_dump":
                await query.edit_message_text(
                    "📉 **Set Dump Threshold**\n\n"
                    "Enter new dump threshold percentage (e.g., `dump -6.0`):\n\n"
                    "Current value: -5.0%\n"
                    "Valid range: -50.0% to -0.1%",
                    parse_mode='Markdown'
                )
            elif data == "threshold_breakout":
                await query.edit_message_text(
                    "💥 **Set Breakout Threshold**\n\n"
                    "Enter new breakout threshold percentage (e.g., `breakout 4.0`):\n\n"
                    "Current value: 3.0%\n"
                    "Valid range: 0.1% to 20.0%",
                    parse_mode='Markdown'
                )
            elif data == "threshold_volume":
                await query.edit_message_text(
                    "📊 **Set Volume Threshold**\n\n"
                    "Enter new volume threshold percentage (e.g., `volume 50`):\n\n"
                    "Current value: 50.0%\n"
                    "Valid range: 1.0% to 200.0%",
                    parse_mode='Markdown'
                )
            else:
                await self.show_threshold_settings(query)
        except Exception as e:
            await query.edit_message_text(f"❌ Threshold error: {e}")
    
    async def handle_filter_toggle(self, query, data):
        """Handle advanced filter toggle"""
        try:
            # Extract filter name from callback data
            filter_name = data.replace("filter_", "")
            
            # Get current filter states from database
            scanner_status = db.get_scanner_status()
            
            # Define filter mappings
            filter_mappings = {
                'whale': 'whale_tracking',
                'spoofing': 'spoofing_detection', 
                'spread': 'spread_filter',
                'trend': 'trend_match',
                'rsi': 'rsi_filter',
                'liquidity': 'liquidity_filter',
                'divergence': 'volume_divergence'
            }
            
            if filter_name not in filter_mappings:
                await query.edit_message_text("❌ Unknown filter!")
                return
            
            db_key = filter_mappings[filter_name]
            current_state = scanner_status.get(db_key, True)
            new_state = not current_state
            
            # Update database
            db.update_scanner_setting(db_key, new_state)
            
            status_emoji = "✅" if new_state else "❌"
            status_text = "ENABLED" if new_state else "DISABLED"
            
            await query.edit_message_text(
                f"🔄 **Filter Updated!**\n\n"
                f"🎯 **{filter_name.title()} Filter:** {status_emoji} {status_text}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error toggling filter: {e}")
    
    async def export_signals_log(self, query):
        """Export signals log as a text file"""
        try:
            await query.edit_message_text("📄 **Generating signals log export...**")
            
            # Get recent signals from database
            signals = db.get_recent_signals(limit=100)
            
            if not signals:
                await query.edit_message_text("📄 **No signals found to export**")
                return
            
            # Create export content
            export_content = f"""📊 BYBIT SCANNER SIGNALS LOG
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Total Signals: {len(signals)}

{'='*60}

"""
            
            for signal in signals:
                export_content += f"""Signal #{signal['id']}
Symbol: {signal['symbol']}
Type: {signal['signal_type']}
Price: ${signal['price']:.4f}
Change: {signal['change_percent']:+.2f}%
Volume: {signal['volume']:,.0f}
Time: {signal['timestamp']}

Message:
{signal['message']}

{'-'*40}

"""
            
            # Create temporary file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                f.write(export_content)
                temp_file = f.name
            
            # Send file to user
            with open(temp_file, 'rb') as f:
                await query.bot.send_document(
                    chat_id=query.message.chat.id,
                    document=f,
                    filename=f"bybit_signals_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    caption=f"📊 **Signals Log Export**\n\n📈 {len(signals)} signals exported\n⏰ Generated: {datetime.now().strftime('%H:%M:%S UTC')}"
                )
            
            # Clean up temp file
            os.unlink(temp_file)
            
            # Update the message
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📄 **Export Complete!**\n\n✅ {len(signals)} signals exported as text file",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Export failed: {e}")
    
    async def export_subscribers(self, query):
        """Export subscriber list as a text file"""
        try:
            await query.edit_message_text("📄 **Generating subscriber list export...**")
            
            # Get detailed subscriber info instead of just IDs
            subscribers = db.get_subscribers_info()
            active_subscribers = [sub for sub in subscribers if sub['is_active']]
            
            if not active_subscribers:
                await query.edit_message_text("📄 **No active subscribers found to export**")
                return
            
            # Create export content
            export_content = f"""👥 BYBIT SCANNER SUBSCRIBER LIST
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Total Active Subscribers: {len(active_subscribers)}

{'='*60}

"""
            
            for i, subscriber in enumerate(active_subscribers, 1):
                export_content += f"""Subscriber #{i}
User ID: {subscriber['user_id']}
Username: @{subscriber['username'] or 'N/A'}
Name: {subscriber['first_name'] or ''} {subscriber['last_name'] or ''}
Added: {subscriber['added_date']}
Status: {'✅ Active' if subscriber['is_active'] else '❌ Inactive'}

{'-'*40}

"""
            
            # Create temporary file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                f.write(export_content)
                temp_file = f.name
            
            # Send file to user
            with open(temp_file, 'rb') as f:
                await query.bot.send_document(
                    chat_id=query.message.chat.id,
                    document=f,
                    filename=f"bybit_subscribers_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                    caption=f"👥 **Subscriber List Export**\n\n📋 {len(active_subscribers)} subscribers exported\n⏰ Generated: {datetime.now().strftime('%H:%M:%S UTC')}"
                )
            
            # Clean up temp file
            os.unlink(temp_file)
            
            # Update the message
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📄 **Export Complete!**\n\n✅ {len(active_subscribers)} subscribers exported as text file",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Export failed: {e}")
    
    async def handle_advanced_settings(self, query, data):
        """Handle advanced settings menu"""
        try:
            # Get current advanced filter states
            scanner_status = db.get_scanner_status()
            
            filters = {
                'whale_tracking': scanner_status.get('whale_tracking', True),
                'spoofing_detection': scanner_status.get('spoofing_detection', False),
                'spread_filter': scanner_status.get('spread_filter', True),
                'trend_match': scanner_status.get('trend_match', True),
                'rsi_filter': scanner_status.get('rsi_filter', True),
                'liquidity_filter': scanner_status.get('liquidity_filter', True),
                'volume_divergence': scanner_status.get('volume_divergence', True)
            }
            
            def get_status_emoji(enabled):
                return "✅" if enabled else "❌"
            
            message = f"""🖥 **Advanced Filter Settings**

Current filter states:

🐋 **Whale Tracking:** {get_status_emoji(filters['whale_tracking'])}
🎭 **Spoofing Detection:** {get_status_emoji(filters['spoofing_detection'])}
📊 **Spread Filter (<0.3%):** {get_status_emoji(filters['spread_filter'])}
📈 **Trend Match (1m/5m):** {get_status_emoji(filters['trend_match'])}
📉 **RSI Filter (75/25):** {get_status_emoji(filters['rsi_filter'])}
💧 **Liquidity Filter (3x):** {get_status_emoji(filters['liquidity_filter'])}
📊 **Volume Divergence:** {get_status_emoji(filters['volume_divergence'])}

Click below to toggle filters:"""
            
            # Create toggle buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        f"🐋 Whale {get_status_emoji(filters['whale_tracking'])}", 
                        callback_data="filter_whale"
                    ),
                    InlineKeyboardButton(
                        f"🎭 Spoof {get_status_emoji(filters['spoofing_detection'])}", 
                        callback_data="filter_spoofing"
                    )
                ],
                [
                    InlineKeyboardButton(
                        f"📊 Spread {get_status_emoji(filters['spread_filter'])}", 
                        callback_data="filter_spread"
                    ),
                    InlineKeyboardButton(
                        f"📈 Trend {get_status_emoji(filters['trend_match'])}", 
                        callback_data="filter_trend"
                    )
                ],
                [
                    InlineKeyboardButton(
                        f"📉 RSI {get_status_emoji(filters['rsi_filter'])}", 
                        callback_data="filter_rsi"
                    ),
                    InlineKeyboardButton(
                        f"💧 Liquid {get_status_emoji(filters['liquidity_filter'])}", 
                        callback_data="filter_liquidity"
                    )
                ],
                [
                    InlineKeyboardButton(
                        f"📊 Diverg {get_status_emoji(filters['volume_divergence'])}", 
                        callback_data="filter_divergence"
                    )
                ],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error loading advanced settings: {e}")
    
    async def show_live_monitor(self, query):
        """Show live market monitor for top pairs"""
        try:
            from enhanced_scanner import enhanced_scanner
            
            # Get monitored pairs
            scanner_status = db.get_scanner_status()
            monitored_pairs = json.loads(scanner_status.get('monitored_pairs', '["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]'))
            
            # Get live data for top 5 pairs
            live_data = []
            for symbol in monitored_pairs[:5]:
                try:
                    market_data = await enhanced_scanner.get_market_data(symbol)
                    if market_data:
                        live_data.append({
                            'symbol': symbol,
                            'price': market_data.price,
                            'change_24h': market_data.change_24h,
                            'volume_24h': market_data.volume_24h
                        })
                except Exception as e:
                    print(f"Error getting data for {symbol}: {e}")
                    continue
            
            # Format live monitor message
            scanner_running = scanner_status.get('is_running', False)
            status_emoji = "🟢" if scanner_running else "🔴"
            status_text = "RUNNING" if scanner_running else "PAUSED"
            
            message = f"""📊 **Live Market Monitor**
            
🤖 **Scanner Status:** {status_emoji} {status_text}
📅 **Updated:** {datetime.now().strftime('%H:%M:%S UTC')}

💹 **Top 5 Monitored Pairs:**
"""
            
            for data in live_data:
                change_emoji = "🟢" if data['change_24h'] >= 0 else "🔴"
                volume_formatted = f"{data['volume_24h']:,.0f}" if data['volume_24h'] > 1000 else f"{data['volume_24h']:.2f}"
                
                message += f"""
**{data['symbol']}**
💰 ${data['price']:,.4f} | {change_emoji} {data['change_24h']:+.2f}%
📊 Vol: ${volume_formatted}
"""
            
            # Add refresh button
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="live_monitor")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Error loading live monitor: {e}")
    
    async def force_scan(self, query):
        """Force an immediate scan of all monitored pairs"""
        try:
            from enhanced_scanner import enhanced_scanner
            
            await query.edit_message_text("⚡ **Force Scan Initiated...**\n\n🔍 Scanning all monitored pairs...")
            
            # Get monitored pairs
            scanner_status = db.get_scanner_status()
            monitored_pairs = json.loads(scanner_status.get('monitored_pairs', '["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]'))
            
            # Perform comprehensive scan
            signals_found = []
            scan_results = []
            
            for symbol in monitored_pairs:
                try:
                    # Scan individual symbol using enhanced comprehensive scan
                    signal = await enhanced_scanner.enhanced_comprehensive_scan(symbol)
                    
                    if signal:
                        signals_found.append(signal)
                        scan_results.append(f"🎯 **{symbol}**: SIGNAL ({signal.strength:.0f}%)")
                        
                        # Send signal immediately
                        if hasattr(enhanced_scanner, 'send_signal_to_recipients'):
                            await enhanced_scanner.send_signal_to_recipients(signal, query.bot)
                    else:
                        scan_results.append(f"📊 **{symbol}**: No signal")
                        
                except Exception as e:
                    scan_results.append(f"❌ **{symbol}**: Error ({str(e)[:30]}...)")
                    print(f"Error scanning {symbol}: {e}")
            
            # Format results message
            message = f"""⚡ **Force Scan Complete**

📊 **Scan Results:**
{chr(10).join(scan_results)}

🎯 **Signals Generated:** {len(signals_found)}
⏰ **Scan Time:** {datetime.now().strftime('%H:%M:%S UTC')}
"""
            
            if signals_found:
                message += f"\n✅ **{len(signals_found)} signals sent to recipients!**"
            else:
                message += "\nℹ️ **No signals met the threshold criteria**"
            
            # Add menu buttons
            keyboard = [
                [InlineKeyboardButton("⚡ Scan Again", callback_data="force_scan")],
                [InlineKeyboardButton("📈 Signals Log", callback_data="signals_log")],
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(f"❌ Force scan failed: {e}")
    
    # Placeholder methods for conversation handlers
    async def change_threshold_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle threshold change input"""
        try:
            text = update.message.text.strip()
            
            # Parse input format: "pump 7.5" or "dump -6.0" or "breakout 4.0" or "volume 50"
            parts = text.lower().split()
            if len(parts) != 2:
                await update.message.reply_text(
                    "❌ **Invalid format!**\n\n"
                    "Please use format:\n"
                    "• `pump 7.5` - Set pump threshold to 7.5%\n"
                    "• `dump -6.0` - Set dump threshold to -6.0%\n"
                    "• `breakout 4.0` - Set breakout threshold to 4.0%\n"
                    "• `volume 50` - Set volume threshold to 50%",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
            
            threshold_type, value_str = parts
            
            try:
                value = float(value_str)
            except ValueError:
                await update.message.reply_text("❌ **Invalid number!** Please enter a valid number.")
                return ConversationHandler.END
            
            # Validate threshold type and value
            valid_types = {
                'pump': (0.1, 50.0),
                'dump': (-50.0, -0.1), 
                'breakout': (0.1, 20.0),
                'volume': (1.0, 200.0)
            }
            
            if threshold_type not in valid_types:
                await update.message.reply_text(
                    f"❌ **Invalid threshold type!**\n\n"
                    f"Valid types: {', '.join(valid_types.keys())}"
                )
                return ConversationHandler.END
            
            min_val, max_val = valid_types[threshold_type]
            if not (min_val <= value <= max_val):
                await update.message.reply_text(
                    f"❌ **Value out of range!**\n\n"
                    f"**{threshold_type}** must be between {min_val}% and {max_val}%"
                )
                return ConversationHandler.END
            
            # Update threshold in database
            scanner_status = db.get_scanner_status()
            thresholds = {
                'pump': scanner_status.get('pump_threshold', 5.0),
                'dump': scanner_status.get('dump_threshold', -5.0),
                'breakout': scanner_status.get('breakout_threshold', 3.0),
                'volume': scanner_status.get('volume_threshold', 50.0)
            }
            
            old_value = thresholds[threshold_type]
            thresholds[threshold_type] = value
            
            # Update database
            updates = {
                'pump_threshold': thresholds['pump'],
                'dump_threshold': thresholds['dump'],
                'breakout_threshold': thresholds['breakout'],
                'volume_threshold': thresholds['volume']
            }
            
            # Update scanner status
            for key, val in updates.items():
                db.update_scanner_setting(key, val)
            
            await update.message.reply_text(
                f"✅ **Threshold Updated!**\n\n"
                f"🎯 **{threshold_type.title()}**: {old_value}% → {value}%\n\n"
                f"📊 **Current Thresholds:**\n"
                f"🚀 Pump: {thresholds['pump']}%\n"
                f"📉 Dump: {thresholds['dump']}%\n"
                f"💥 Breakout: {thresholds['breakout']}%\n"
                f"📊 Volume: {thresholds['volume']}%",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating threshold: {e}")
        
        return ConversationHandler.END
    
    async def add_pair_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle add trading pair input"""
        try:
            text = update.message.text.strip().upper()
            
            # Validate input format
            if not text.endswith('USDT'):
                await update.message.reply_text(
                    "❌ **Invalid pair format!**\n\n"
                    "Please enter a valid USDT pair like:\n"
                    "• `BTCUSDT`\n"
                    "• `ETHUSDT`\n"
                    "• `ADAUSDT`",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
            
            # Validate with Bybit API
            from enhanced_scanner import enhanced_scanner
            try:
                market_data = await enhanced_scanner.get_market_data(text)
                if not market_data:
                    await update.message.reply_text(f"❌ **Pair {text} not found on Bybit!**")
                    return ConversationHandler.END
            except Exception as e:
                await update.message.reply_text(f"❌ **Error validating pair:** {e}")
                return ConversationHandler.END
            
            # Get current monitored pairs
            scanner_status = db.get_scanner_status()
            current_pairs = json.loads(scanner_status.get('monitored_pairs', '["BTCUSDT", "ETHUSDT"]'))
            
            # Check if already exists
            if text in current_pairs:
                await update.message.reply_text(f"⚠️ **{text} is already being monitored!**")
                return ConversationHandler.END
            
            # Add the new pair
            current_pairs.append(text)
            
            # Update database
            db.update_scanner_setting('monitored_pairs', json.dumps(current_pairs))
            
            await update.message.reply_text(
                f"✅ **Pair Added Successfully!**\n\n"
                f"➕ **Added:** {text}\n"
                f"📊 **Current Price:** ${market_data.price:,.4f}\n"
                f"📈 **24h Change:** {market_data.change_24h:+.2f}%\n\n"
                f"🔍 **Total Monitored Pairs:** {len(current_pairs)}\n"
                f"📋 **All Pairs:** {', '.join(current_pairs)}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error adding pair: {e}")
        
        return ConversationHandler.END
    
    async def remove_pair_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle remove trading pair input"""
        try:
            text = update.message.text.strip().upper()
            
            # Get current monitored pairs
            scanner_status = db.get_scanner_status()
            current_pairs = json.loads(scanner_status.get('monitored_pairs', '["BTCUSDT", "ETHUSDT"]'))
            
            # Check if pair exists
            if text not in current_pairs:
                await update.message.reply_text(
                    f"❌ **{text} is not in the monitored pairs!**\n\n"
                    f"📋 **Current pairs:** {', '.join(current_pairs)}",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
            
            # Prevent removing all pairs
            if len(current_pairs) <= 1:
                await update.message.reply_text("❌ **Cannot remove the last pair!** At least one pair must be monitored.")
                return ConversationHandler.END
            
            # Remove the pair
            current_pairs.remove(text)
            
            # Update database
            db.update_scanner_setting('monitored_pairs', json.dumps(current_pairs))
            
            await update.message.reply_text(
                f"✅ **Pair Removed Successfully!**\n\n"
                f"➖ **Removed:** {text}\n\n"
                f"🔍 **Remaining Monitored Pairs:** {len(current_pairs)}\n"
                f"📋 **Current Pairs:** {', '.join(current_pairs)}",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error removing pair: {e}")
        
        return ConversationHandler.END
    
    async def tp_multipliers_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle TP multipliers input"""
        try:
            text = update.message.text.strip()
            
            # Parse input format: "1.5, 3.0, 5.0, 7.5" or "[1.5, 3.0, 5.0, 7.5]"
            try:
                # Clean the input
                text = text.replace('[', '').replace(']', '').replace(' ', '')
                multipliers = [float(x.strip()) for x in text.split(',')]
                
                if len(multipliers) != 4:
                    raise ValueError("Must have exactly 4 values")
                
                # Validate multipliers are increasing
                if not all(multipliers[i] < multipliers[i+1] for i in range(3)):
                    raise ValueError("Multipliers must be in increasing order")
                
                # Validate reasonable ranges
                if any(m < 0.1 or m > 20.0 for m in multipliers):
                    raise ValueError("Multipliers must be between 0.1% and 20.0%")
                
            except (ValueError, IndexError) as e:
                await update.message.reply_text(
                    "❌ **Invalid format!**\n\n"
                    "Please enter 4 comma-separated percentages:\n"
                    "• `1.5, 3.0, 5.0, 7.5`\n"
                    "• `[2.0, 4.0, 6.0, 8.0]`\n\n"
                    "**Requirements:**\n"
                    "• Exactly 4 values\n"
                    "• Increasing order\n"
                    "• Between 0.1% and 20.0%",
                    parse_mode='Markdown'
                )
                return ConversationHandler.END
            
            # Get current multipliers
            scanner_status = db.get_scanner_status()
            current_tp = scanner_status.get('tp_multipliers', '[1.5, 3.0, 5.0, 7.5]')
            
            # Update database
            new_tp_str = json.dumps(multipliers)
            db.update_scanner_setting('tp_multipliers', new_tp_str)
            
            await update.message.reply_text(
                f"✅ **TP Multipliers Updated!**\n\n"
                f"📊 **Previous:** {current_tp}\n"
                f"🎯 **New:** {new_tp_str}\n\n"
                f"**Take Profit Targets:**\n"
                f"🎯 TP1: {multipliers[0]}% (40%)\n"
                f"🎯 TP2: {multipliers[1]}% (60%)\n"
                f"🎯 TP3: {multipliers[2]}% (80%)\n"
                f"🎯 TP4: {multipliers[3]}% (100%)",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Error updating TP multipliers: {e}")
        
        return ConversationHandler.END
    
    def get_application(self):
        """Get the telegram application instance"""
        return self.application

# Create global bot instance
telegram_bot = TelegramBot()