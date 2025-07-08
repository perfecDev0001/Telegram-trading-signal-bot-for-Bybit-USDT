#!/usr/bin/env python3
"""
Test script to verify conversation handlers work correctly
"""
import asyncio
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import TelegramBot
from config import Config
from unittest.mock import Mock, AsyncMock
from telegram import Update, CallbackQuery, Message, User, Chat
from telegram.ext import ContextTypes

async def test_conversation_handlers():
    """Test conversation handlers to ensure they work without async/await issues"""
    try:
        print("🔍 Testing conversation handlers...")
        bot = TelegramBot()
        
        # Create mock objects for testing
        mock_user = Mock(spec=User)
        mock_user.id = Config.ADMIN_ID
        mock_user.username = "test_admin"
        
        mock_chat = Mock(spec=Chat)
        mock_chat.id = Config.ADMIN_ID
        
        mock_message = Mock(spec=Message)
        mock_message.chat_id = Config.ADMIN_ID
        mock_message.chat = mock_chat
        
        mock_query = Mock(spec=CallbackQuery)
        mock_query.from_user = mock_user
        mock_query.message = mock_message
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        
        mock_update = Mock(spec=Update)
        mock_update.callback_query = mock_query
        mock_update.effective_chat = mock_chat
        
        mock_context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        mock_context.user_data = {}
        mock_context.bot = Mock()
        mock_context.bot.send_message = AsyncMock()
        
        print("✅ Mock objects created")
        
        # Test threshold callback
        print("🧪 Testing threshold callback...")
        mock_query.data = "threshold_pump"
        result = await bot.handle_threshold_callback(mock_query, mock_query.data, mock_context)
        print(f"   Threshold result: {result}")
        
        # Test TP multipliers callback
        print("🧪 Testing TP multipliers callback...")
        result = await bot.handle_tp_multipliers_callback(mock_query, mock_context)
        print(f"   TP multipliers result: {result}")
        
        # Test settings callback
        print("🧪 Testing settings callback...")
        mock_query.data = "settings_add_pair"
        result = await bot.handle_settings_callback(mock_query, mock_query.data)
        print(f"   Settings result: {result}")
        
        # Test start conversation
        print("🧪 Testing start conversation...")
        result = await bot.start_conversation(mock_update, mock_context)
        print(f"   Start conversation result: {result}")
        
        print("✅ All conversation handlers tested successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error testing conversation handlers: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("🧪 Starting Conversation Handler Test")
    print("=" * 50)
    
    success = await test_conversation_handlers()
    
    print("=" * 50)
    if success:
        print("✅ All conversation handler tests passed!")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    
    return success

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(main())
    sys.exit(0 if success else 1)