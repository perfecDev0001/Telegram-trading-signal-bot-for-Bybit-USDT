#!/usr/bin/env python3
"""
Clean Deployment Script

This script ensures a clean deployment by:
1. Clearing bot conflicts
2. Waiting for stabilization
3. Starting the main application

Use this for deployment to avoid conflicts.
"""

import asyncio
import subprocess
import sys
import time
from clear_bot_conflicts import clear_bot_conflicts

async def deploy_clean():
    """Deploy with conflict resolution"""
    print("🚀 Clean Deployment Starting")
    print("=" * 50)
    
    # Step 1: Clear bot conflicts
    print("Step 1: Clearing bot conflicts...")
    if not await clear_bot_conflicts():
        print("❌ Failed to clear bot conflicts")
        return False
    
    # Step 2: Wait for stabilization
    print("\nStep 2: Waiting for system stabilization...")
    for i in range(10, 0, -1):
        print(f"   Waiting {i} seconds...", end='\r')
        await asyncio.sleep(1)
    print("   ✅ System stabilized" + " " * 20)
    
    # Step 3: Start main application
    print("\nStep 3: Starting main application...")
    print("🚀 Launching main.py...")
    
    try:
        # Import and run main
        from main import BotManager
        manager = BotManager()
        await manager.run()
        return True
    except KeyboardInterrupt:
        print("\n🛑 Deployment interrupted by user")
        return True
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(deploy_clean())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Deployment cancelled")
        sys.exit(0)