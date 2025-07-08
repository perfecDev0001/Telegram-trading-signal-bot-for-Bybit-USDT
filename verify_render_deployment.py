#!/usr/bin/env python3
"""
Verify Render Deployment

This script verifies that your Render deployment is working correctly.
"""

import asyncio
import requests
import sys
import time
from config import Config

def check_render_service():
    """Check if Render service is responding"""
    print("🌐 Checking Render service...")
    
    # Common service URLs
    service_urls = [
        "https://bybit-scanner-bot.onrender.com",
        "https://public-api-crypto-scanner.onrender.com",
        "https://bybit-scanner-bot-latest.onrender.com"
    ]
    
    for url in service_urls:
        try:
            print(f"  🔍 Checking {url}...")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"  ✅ Service is LIVE: {url}")
                print(f"      Response: {response.text[:100]}...")
                return url
            else:
                print(f"  ⚠️ Service responded with {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"  📴 Service not reachable: {e}")
    
    print("  ❌ No active Render services found")
    return None

def check_health_endpoint(service_url):
    """Check service health endpoint"""
    try:
        print(f"🏥 Checking health endpoint...")
        health_url = f"{service_url}/health"
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"  ✅ Health check passed")
            print(f"      Status: {health_data.get('status', 'unknown')}")
            print(f"      Uptime: {health_data.get('uptime_formatted', 'unknown')}")
            print(f"      Bot running: {health_data.get('bot_running', 'unknown')}")
            return True
        else:
            print(f"  ❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Health check error: {e}")
        return False

def check_status_endpoint(service_url):
    """Check service status endpoint"""
    try:
        print(f"📊 Checking status endpoint...")
        status_url = f"{service_url}/status"
        response = requests.get(status_url, timeout=10)
        
        if response.status_code == 200:
            status_data = response.json()
            print(f"  ✅ Status check passed")
            print(f"      Scanner running: {status_data.get('scanner', {}).get('is_running', 'unknown')}")
            print(f"      Monitored pairs: {len(status_data.get('scanner', {}).get('monitored_pairs', []))}")
            return True
        else:
            print(f"  ❌ Status check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Status check error: {e}")
        return False

async def test_bot_directly():
    """Test bot directly to ensure no conflicts"""
    try:
        import telegram
        
        print("🤖 Testing bot directly...")
        bot = telegram.Bot(token=Config.BOT_TOKEN)
        
        # This should work without conflicts if Render is running properly
        bot_info = await bot.get_me()
        print(f"  ✅ Bot info: @{bot_info.username}")
        
        # Try to get updates - this will fail if Render is running (which is expected)
        try:
            updates = await bot.get_updates(timeout=1, limit=1)
            print(f"  ⚠️ Got updates directly: {len(updates)}")
            print(f"      This means Render might not be running the bot!")
            return False
        except Exception as e:
            if "Conflict" in str(e):
                print(f"  ✅ Bot conflict detected - Render is running the bot properly!")
                return True
            else:
                print(f"  ❌ Unexpected error: {e}")
                return False
                
    except Exception as e:
        print(f"  ❌ Bot test failed: {e}")
        return False

async def main():
    """Main verification function"""
    print("🔍 RENDER DEPLOYMENT VERIFICATION")
    print("=" * 50)
    
    # Step 1: Check if Render service is running
    service_url = check_render_service()
    if not service_url:
        print("\n❌ RENDER SERVICE NOT FOUND")
        print("   Please check your Render dashboard")
        print("   Ensure your service is deployed and running")
        return False
    
    # Step 2: Check health endpoint
    print(f"\n🏥 Checking service health...")
    health_ok = check_health_endpoint(service_url)
    
    # Step 3: Check status endpoint
    print(f"\n📊 Checking service status...")
    status_ok = check_status_endpoint(service_url)
    
    # Step 4: Test bot conflicts (should have conflicts if Render is running)
    print(f"\n🤖 Testing bot conflicts...")
    conflicts_ok = await test_bot_directly()
    
    # Final assessment
    print(f"\n{'='*50}")
    print("📋 DEPLOYMENT VERIFICATION RESULTS")
    print(f"{'='*50}")
    
    print(f"🌐 Service URL: {service_url}")
    print(f"🏥 Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"📊 Status Check: {'✅ PASS' if status_ok else '❌ FAIL'}")
    print(f"🤖 Bot Conflicts: {'✅ PASS' if conflicts_ok else '❌ FAIL'}")
    
    if health_ok and status_ok and conflicts_ok:
        print(f"\n🎉 DEPLOYMENT SUCCESSFUL!")
        print(f"✅ Your bot is running on Render without conflicts!")
        print(f"\n🎯 NEXT STEPS:")
        print(f"   1. Send /start to your bot to test it")
        print(f"   2. Monitor the logs for any issues")
        print(f"   3. Check the service URL: {service_url}")
        return True
    else:
        print(f"\n❌ DEPLOYMENT ISSUES DETECTED")
        print(f"   Please check the Render logs for errors")
        print(f"   Verify your environment variables are set")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)