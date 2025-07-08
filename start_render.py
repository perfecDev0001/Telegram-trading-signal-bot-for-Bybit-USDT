#!/usr/bin/env python3
"""
Render Start Script - Optimized for Render deployment

This script ensures proper initialization on Render platform.
"""

import sys
import os
import asyncio
import subprocess
import time

def ensure_dependencies():
    """Ensure all dependencies are properly installed"""
    try:
        # Check if python-telegram-bot is the correct version
        import telegram
        version = telegram.__version__
        print(f"✅ python-telegram-bot version: {version}")
        
        if not version.startswith('20.'):
            print("❌ Wrong python-telegram-bot version")
            raise ImportError("Incorrect version")
            
        # Test Application class
        from telegram.ext import Application
        print("✅ Application class imported successfully")
        
        return True
    except ImportError as e:
        print(f"❌ Dependency issue: {e}")
        print("🔄 Attempting to fix dependencies...")
        
        # Force reinstall
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "--force-reinstall", "python-telegram-bot==20.8"], check=True)
            print("✅ Dependencies fixed")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to fix dependencies")
            return False

def main():
    """Main function for Render deployment"""
    print("🚀 Starting Render deployment...")
    
    # Check environment
    print(f"🌍 Environment: {os.getenv('RENDER_SERVICE_NAME', 'Unknown')}")
    print(f"🐍 Python version: {sys.version}")
    
    # Ensure dependencies
    if not ensure_dependencies():
        print("❌ Failed to ensure dependencies")
        sys.exit(1)
    
    # Import and run the main application
    try:
        print("📦 Importing main application...")
        from main import main as run_main
        print("✅ Main application imported successfully")
        
        # Run the main application
        print("🚀 Starting main application...")
        run_main()
        
    except Exception as e:
        print(f"❌ Failed to start main application: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()