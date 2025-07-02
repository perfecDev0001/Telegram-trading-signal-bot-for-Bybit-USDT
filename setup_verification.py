#!/usr/bin/env python3
"""
Bybit Scanner Bot - Setup Verification Script
Verifies all configuration and dependencies before running the bot
"""

import os
import sys
import asyncio
import importlib
from datetime import datetime

def print_header():
    """Print verification header"""
    print("🔧 BYBIT SCANNER BOT - SETUP VERIFICATION")
    print("=" * 60)
    print(f"⏰ Verification started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

def check_python_version():
    """Check Python version compatibility"""
    print("\n🐍 CHECKING PYTHON VERSION")
    print("-" * 30)
    
    version = sys.version_info
    print(f"Python Version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major >= 3 and version.minor >= 8:
        print("✅ Python version is compatible")
        return True
    else:
        print("❌ Python 3.8+ required")
        return False

def check_dependencies():
    """Check required dependencies"""
    print("\n📦 CHECKING DEPENDENCIES")
    print("-" * 30)
    
    required_packages = [
        'telegram',
        'dotenv', 
        'requests',
        'aiohttp',
        'psutil'
    ]
    
    missing = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Missing")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️ Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies installed")
    return True

def check_configuration():
    """Check configuration files and settings"""
    print("\n⚙️ CHECKING CONFIGURATION")
    print("-" * 30)
    
    issues = []
    
    # Check .env file
    if not os.path.exists('.env'):
        print("⚠️ .env file not found")
        print("   Copy .env.example to .env and configure it")
        issues.append(".env file missing")
    else:
        print("✅ .env file exists")
    
    # Check config values
    try:
        from config import Config
        
        # Bot Token
        if not Config.BOT_TOKEN or Config.BOT_TOKEN == "your_telegram_bot_token_here":
            print("❌ BOT_TOKEN not configured")
            issues.append("BOT_TOKEN not set")
        else:
            print(f"✅ BOT_TOKEN configured: {Config.BOT_TOKEN[:10]}***")
        
        # Admin ID
        if Config.ADMIN_ID == 7974254350:
            print(f"✅ ADMIN_ID configured: {Config.ADMIN_ID}")
        else:
            print(f"⚠️ ADMIN_ID: {Config.ADMIN_ID} (expected: 7974254350)")
        
        # Bybit API Key
        if Config.BYBIT_API_KEY == "1Lf8RrbAZwhGz42UNY":
            print(f"✅ BYBIT_API_KEY configured: {Config.BYBIT_API_KEY}")
        else:
            print(f"⚠️ BYBIT_API_KEY: {Config.BYBIT_API_KEY}")
        
        # Scanner Interval
        if Config.SCANNER_INTERVAL == 60:
            print(f"✅ SCANNER_INTERVAL: {Config.SCANNER_INTERVAL} seconds")
        else:
            print(f"⚠️ SCANNER_INTERVAL: {Config.SCANNER_INTERVAL} (expected: 60)")
            
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        issues.append(f"Config error: {e}")
    
    return len(issues) == 0, issues

def check_files():
    """Check essential project files"""
    print("\n📁 CHECKING PROJECT FILES")
    print("-" * 30)
    
    essential_files = [
        'main.py',
        'config.py', 
        'enhanced_scanner.py',
        'telegram_bot.py',
        'database.py',
        'settings_manager.py',
        'requirements.txt',
        'Procfile',
        'render.yaml',
        '.env.example'
    ]
    
    missing = []
    
    for file in essential_files:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - Missing")
            missing.append(file)
    
    if missing:
        return False, missing
    
    return True, []

async def test_api_connectivity():
    """Test Bybit API connectivity"""
    print("\n🌐 TESTING API CONNECTIVITY")
    print("-" * 30)
    
    try:
        from enhanced_scanner import enhanced_scanner
        
        print("Testing Bybit API connection...")
        connected = await enhanced_scanner.test_api_connectivity()
        
        if connected:
            print("✅ Bybit API connection successful")
            return True
        else:
            print("❌ Bybit API connection failed")
            return False
            
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def test_database():
    """Test database functionality"""
    print("\n🗄️ TESTING DATABASE")
    print("-" * 30)
    
    try:
        from database import db
        
        # Test database initialization
        db.init_database()
        print("✅ Database initialization successful")
        
        # Test database operations
        db.update_scanner_status(is_running=True)
        status = db.get_scanner_status()
        
        if status.get('is_running'):
            print("✅ Database read/write operations working")
            return True
        else:
            print("❌ Database operations failed")
            return False
            
    except Exception as e:
        print(f"❌ Database test error: {e}")
        return False

def check_deployment_readiness():
    """Check deployment configuration"""
    print("\n🚀 CHECKING DEPLOYMENT READINESS")
    print("-" * 30)
    
    checks = []
    
    # Procfile
    if os.path.exists('Procfile'):
        with open('Procfile', 'r') as f:
            content = f.read().strip()
            if 'python main.py' in content:
                print("✅ Procfile configured correctly")
                checks.append(True)
            else:
                print("❌ Procfile configuration issue")
                checks.append(False)
    else:
        print("❌ Procfile missing")
        checks.append(False)
    
    # render.yaml
    if os.path.exists('render.yaml'):
        print("✅ render.yaml exists")
        checks.append(True)
    else:
        print("❌ render.yaml missing")
        checks.append(False)
    
    # requirements.txt
    if os.path.exists('requirements.txt'):
        print("✅ requirements.txt exists")
        checks.append(True)
    else:
        print("❌ requirements.txt missing") 
        checks.append(False)
    
    return all(checks)

async def main():
    """Run complete setup verification"""
    print_header()
    
    results = []
    
    # Run all checks
    results.append(check_python_version())
    results.append(check_dependencies())
    
    config_ok, config_issues = check_configuration()
    results.append(config_ok)
    
    files_ok, missing_files = check_files()
    results.append(files_ok)
    
    if all(results[:4]):  # Only test these if basic setup is OK
        results.append(await test_api_connectivity())
        results.append(test_database())
        results.append(check_deployment_readiness())
    
    # Final summary
    print("\n" + "="*60)
    print("📋 VERIFICATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"Checks Passed: {passed}/{total}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 SETUP VERIFICATION COMPLETE!")
        print("✅ Your bot is ready to run")
        print("🚀 Run with: python main.py")
        return True
    else:
        print("\n⚠️ SETUP ISSUES FOUND")
        
        if not config_ok and config_issues:
            print("\n🔧 Configuration Issues:")
            for issue in config_issues:
                print(f"   • {issue}")
        
        if not files_ok and missing_files:
            print("\n📁 Missing Files:")
            for file in missing_files:
                print(f"   • {file}")
        
        print("\n💡 Please fix these issues before running the bot")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Verification error: {e}")
        sys.exit(1)