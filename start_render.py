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
import psutil
import signal

def cleanup_existing_processes():
    """Clean up any existing bot processes to prevent conflicts"""
    current_pid = os.getpid()
    killed = 0
    
    print("🧹 Cleaning up existing bot processes...")
    
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if (proc.info['pid'] != current_pid and 
                proc.info['cmdline'] and
                any(keyword in ' '.join(proc.info['cmdline']).lower() 
                    for keyword in ['main.py', 'telegram_bot', 'start_render.py'])):
                
                try:
                    print(f"  Terminating conflicting process PID {proc.info['pid']}")
                    proc.terminate()
                    proc.wait(timeout=3)
                    killed += 1
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    try:
                        proc.kill()
                        killed += 1
                    except psutil.NoSuchProcess:
                        pass
                except psutil.AccessDenied:
                    pass
    except Exception as e:
        print(f"⚠️ Error during cleanup: {e}")
    
    if killed > 0:
        print(f"✅ Cleaned up {killed} conflicting processes")
        time.sleep(2)
    else:
        print("✅ No conflicting processes found")

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
        
        # Force reinstall without version conflicts
        try:
            # First uninstall potentially conflicting packages
            subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "python-telegram-bot", "httpx"], check=False)
            
            # Install the correct version
            subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", "python-telegram-bot==20.8"], check=True)
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
    
    # Clean up any existing processes first
    cleanup_existing_processes()
    
    # Ensure dependencies
    if not ensure_dependencies():
        print("❌ Failed to ensure dependencies")
        sys.exit(1)
    
    # Clear any existing webhooks
    try:
        print("🔄 Clearing Telegram webhooks...")
        import asyncio
        from clear_webhook import clear_webhook
        asyncio.run(clear_webhook())
        print("✅ Webhooks cleared")
    except Exception as e:
        print(f"⚠️ Could not clear webhooks: {e}")
        print("🔄 Continuing anyway...")
    
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