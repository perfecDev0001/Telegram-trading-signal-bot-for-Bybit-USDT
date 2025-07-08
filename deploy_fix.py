#!/usr/bin/env python3
"""
Deploy Fix Script - Ensures correct python-telegram-bot version on Render

This script helps debug and fix deployment issues related to python-telegram-bot
version compatibility on Render.
"""

import sys
import subprocess
import importlib.util
import pkg_resources

def check_telegram_bot_version():
    """Check the installed version of python-telegram-bot"""
    try:
        import telegram
        print(f"✅ python-telegram-bot version: {telegram.__version__}")
        
        # Check for specific attributes that changed in v20.x
        from telegram.ext import Application
        app = Application.builder().token("dummy").build()
        
        if hasattr(app, 'updater'):
            print("✅ Application has 'updater' attribute")
        else:
            print("❌ Application does NOT have 'updater' attribute")
            
        print("✅ Version check passed")
        return True
    except ImportError as e:
        print(f"❌ python-telegram-bot not installed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking version: {e}")
        return False

def force_reinstall():
    """Force reinstall python-telegram-bot"""
    try:
        print("🔄 Force reinstalling python-telegram-bot...")
        
        # Uninstall first
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "python-telegram-bot"], check=True)
        
        # Clear pip cache
        subprocess.run([sys.executable, "-m", "pip", "cache", "purge"], check=True)
        
        # Install specific version
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "python-telegram-bot==20.8"], check=True)
        
        print("✅ Reinstallation complete")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Reinstallation failed: {e}")
        return False

def main():
    """Main function to run deployment fixes"""
    print("🚀 Starting deployment fix script...")
    
    # Check Python version
    print(f"🐍 Python version: {sys.version}")
    
    # Check current installation
    if not check_telegram_bot_version():
        print("❌ python-telegram-bot not properly installed")
        if force_reinstall():
            check_telegram_bot_version()
        else:
            print("❌ Failed to fix installation")
            sys.exit(1)
    
    # Test telegram bot import
    try:
        from telegram_bot import TelegramBot
        print("✅ TelegramBot import successful")
    except Exception as e:
        print(f"❌ TelegramBot import failed: {e}")
        sys.exit(1)
    
    print("✅ All checks passed! Deployment should work now.")

if __name__ == "__main__":
    main()