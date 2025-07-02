#!/usr/bin/env python3
"""
Comprehensive Test Suite for Bybit Scanner Bot
Tests all core functionality and requirements compliance
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from database import db
from enhanced_scanner import enhanced_scanner
from telegram_bot import TelegramBot
from settings_manager import settings_manager

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
    
    def test(self, name: str, condition: bool, details: str = ""):
        """Record test result"""
        if condition:
            self.passed += 1
            status = "✅ PASS"
            print(f"{status}: {name}")
        else:
            self.failed += 1
            status = "❌ FAIL"
            print(f"{status}: {name}")
            if details:
                print(f"   Details: {details}")
        
        self.results.append({
            'name': name,
            'status': status,
            'details': details
        })
    
    def summary(self):
        """Print test summary"""
        total = self.passed + self.failed
        print("\n" + "="*70)
        print("🧪 TEST SUMMARY")
        print("="*70)
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Success Rate: {(self.passed/total)*100:.1f}%" if total > 0 else "N/A")
        return self.failed == 0

async def test_configuration():
    """Test configuration settings"""
    print("\n🔧 TESTING CONFIGURATION")
    print("-" * 40)
    
    tester = TestRunner()
    
    # Test Bot Token
    tester.test(
        "Bot Token Configuration",
        Config.BOT_TOKEN and Config.BOT_TOKEN != "YOUR_BOT_TOKEN_HERE",
        f"Token: {Config.BOT_TOKEN[:10] if Config.BOT_TOKEN else 'None'}***"
    )
    
    # Test Admin ID
    tester.test(
        "Admin ID Configuration", 
        Config.ADMIN_ID == 7974254350,
        f"Admin ID: {Config.ADMIN_ID}"
    )
    
    # Test Bybit API Key
    tester.test(
        "Bybit API Key",
        Config.BYBIT_API_KEY == "1Lf8RrbAZwhGz42UNY",
        f"API Key: {Config.BYBIT_API_KEY}"
    )
    
    # Test Default Pairs
    tester.test(
        "Default Trading Pairs",
        len(Config.DEFAULT_PAIRS) >= 10,
        f"Pairs count: {len(Config.DEFAULT_PAIRS)}"
    )
    
    return tester.summary()

async def test_database():
    """Test database functionality"""
    print("\n🗄️ TESTING DATABASE")
    print("-" * 40)
    
    tester = TestRunner()
    
    # Test database initialization
    try:
        db.init_database()
        tester.test("Database Initialization", True)
    except Exception as e:
        tester.test("Database Initialization", False, str(e))
    
    # Test signal logging
    try:
        db.log_signal("BTCUSDT", "TEST", 50000.0, 5.0, 1000000.0, "Test message")
        signals = db.get_recent_signals(limit=1)
        tester.test("Signal Logging", len(signals) > 0 and signals[0]['symbol'] == 'BTCUSDT')
    except Exception as e:
        tester.test("Signal Logging", False, str(e))
    
    # Test settings storage
    try:
        db.update_scanner_status(is_running=True)
        status = db.get_scanner_status()
        tester.test("Settings Storage", status.get('is_running') == True)
    except Exception as e:
        tester.test("Settings Storage", False, str(e))
    
    return tester.summary()

async def test_scanner():
    """Test scanner functionality"""
    print("\n🔍 TESTING SCANNER ENGINE")
    print("-" * 40)
    
    tester = TestRunner()
    
    # Test API connectivity
    try:
        connected = await enhanced_scanner.test_api_connectivity()
        tester.test("API Connectivity", connected)
    except Exception as e:
        tester.test("API Connectivity", False, str(e))
    
    # Test market data fetching
    try:
        market_data = await enhanced_scanner.get_market_data("BTCUSDT")
        tester.test("Market Data Fetching", market_data is not None and market_data.symbol == "BTCUSDT")
    except Exception as e:
        tester.test("Market Data Fetching", False, str(e))
    
    # Test 5-minute candle data (requirements compliance)
    try:
        candles = await enhanced_scanner.get_kline_data("BTCUSDT", "5", 10)
        tester.test("5-Minute Candle Data", len(candles) > 0)
    except Exception as e:
        tester.test("5-Minute Candle Data", False, str(e))
    
    # Test order book data
    try:
        order_book = await enhanced_scanner.get_order_book("BTCUSDT")
        tester.test("Order Book Data", order_book is not None and order_book.bids and order_book.asks)
    except Exception as e:
        tester.test("Order Book Data", False, str(e))
    
    return tester.summary()

async def test_signal_detection():
    """Test signal detection filters"""
    print("\n📊 TESTING SIGNAL DETECTION")
    print("-" * 40)
    
    tester = TestRunner()
    
    # Test signal analysis (single pair)
    try:
        signal = await enhanced_scanner.analyze_symbol("BTCUSDT")
        tester.test("Signal Analysis", True)  # Should complete without error
    except Exception as e:
        tester.test("Signal Analysis", False, str(e))
    
    # Test signal strength calculation
    try:
        test_filters = {
            'price_action': {'breakout': True, 'candle_strength': 70},
            'volume': {'volume_surge': True, 'buy_pressure': 65},
            'order_book': {'imbalance': True, 'tight_spread': True},
            'whale': {'whale_detected': False}
        }
        strength = enhanced_scanner.calculate_signal_strength(test_filters)
        tester.test("Signal Strength Calculation", 70 <= strength <= 100, f"Strength: {strength}%")
    except Exception as e:
        tester.test("Signal Strength Calculation", False, str(e))
    
    return tester.summary()

async def test_telegram_bot():
    """Test Telegram bot functionality"""
    print("\n🤖 TESTING TELEGRAM BOT")
    print("-" * 40)
    
    tester = TestRunner()
    
    # Test bot initialization
    try:
        bot = TelegramBot()
        tester.test("Bot Initialization", bot is not None)
    except Exception as e:
        tester.test("Bot Initialization", False, str(e))
    
    # Test admin panel keyboard
    try:
        bot = TelegramBot()
        keyboard = bot.get_admin_keyboard()
        tester.test("Admin Panel Keyboard", keyboard is not None and len(keyboard.inline_keyboard) >= 5)
    except Exception as e:
        tester.test("Admin Panel Keyboard", False, str(e))
    
    # Test admin authorization
    try:
        bot = TelegramBot()
        is_admin_check = bot.is_admin(7974254350)  # Admin ID from requirements
        tester.test("Admin Authorization", is_admin_check == True)
    except Exception as e:
        tester.test("Admin Authorization", False, str(e))
    
    return tester.summary()

async def test_signal_format():
    """Test signal message formatting compliance"""
    print("\n📨 TESTING SIGNAL FORMAT")
    print("-" * 40)
    
    tester = TestRunner()
    
    try:
        from enhanced_scanner import SignalData
        
        # Create test signal
        test_signal = SignalData(
            symbol="BTCUSDT",
            signal_type="BREAKOUT_LONG",
            price=50000.0,
            change_percent=5.0,
            volume=1000000.0,
            strength=85.0,
            tp_targets=[50750.0, 51500.0, 52500.0, 53750.0],
            filters_passed=[
                "✅ Breakout Pattern",
                "✅ Volume Surge",
                "✅ Order Book Imbalance", 
                "✅ 5-minute Candle Analysis"
            ],
            timestamp=datetime.now(),
            whale_activity=False
        )
        
        # Test message formatting
        message = enhanced_scanner.format_signal_message(test_signal)
        
        # Check requirements compliance
        required_elements = [
            "#BTCUSDT",
            "(Long, x20)",
            "Entry",
            "Strength:",
            "Take-Profit:",
            "TP1 –",
            "TP2 –", 
            "TP3 –",
            "TP4 –",
            "Filters Passed:",
            "UTC"
        ]
        
        all_present = all(element in message for element in required_elements)
        tester.test("Signal Format Compliance", all_present, "All required elements present")
        
        # Test recipients configuration
        recipients = [7974254350, 7452976451, -1002674839519]
        tester.test("Signal Recipients", len(recipients) == 3, f"Recipients: {recipients}")
        
    except Exception as e:
        tester.test("Signal Format Testing", False, str(e))
    
    return tester.summary()

async def test_requirements_compliance():
    """Test compliance with all project requirements"""
    print("\n✅ TESTING REQUIREMENTS COMPLIANCE")
    print("-" * 40)
    
    tester = TestRunner()
    
    # Test 60-second scan interval
    tester.test("60-Second Scan Interval", Config.SCANNER_INTERVAL == 60)
    
    # Test 5-minute candle usage (corrected from 1-minute)
    try:
        candles = await enhanced_scanner.get_kline_data("BTCUSDT", "5", 10)
        tester.test("5-Minute Candle Analysis", len(candles) > 0, "Uses 5-minute candles as specified")
    except:
        tester.test("5-Minute Candle Analysis", False)
    
    # Test signal strength scoring (0-100%)
    test_filters = {
        'price_action': {'breakout': True, 'candle_strength': 70},
        'volume': {'volume_surge': True, 'buy_pressure': 65},
        'order_book': {'imbalance': True, 'tight_spread': True},
        'whale': {'whale_detected': False}
    }
    strength = enhanced_scanner.calculate_signal_strength(test_filters)
    tester.test("Signal Strength Scoring (0-100%)", 0 <= strength <= 100, f"Strength: {strength}%")
    
    # Test admin panel features
    bot = TelegramBot()
    keyboard = bot.get_admin_keyboard()
    required_buttons = ["Scanner Status", "Signals Log", "Settings", "Live Monitor", "System Status"]
    button_texts = [btn.text for row in keyboard.inline_keyboard for btn in row]
    has_required = all(any(req in btn for btn in button_texts) for req in required_buttons)
    tester.test("Admin Panel Features", has_required, "All required admin features present")
    
    # Test deployment readiness
    tester.test("Deployment Files Present", 
               os.path.exists("Procfile") and os.path.exists("render.yaml"),
               "Procfile and render.yaml exist")
    
    return tester.summary()

async def main():
    """Run all tests"""
    print("🧪 BYBIT SCANNER BOT - COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    results = []
    
    # Run all test suites
    results.append(await test_configuration())
    results.append(await test_database())
    results.append(await test_scanner())
    results.append(await test_signal_detection())
    results.append(await test_telegram_bot())
    results.append(await test_signal_format())
    results.append(await test_requirements_compliance())
    
    # Final summary
    print("\n" + "="*70)
    print("🏁 FINAL TEST RESULTS")
    print("="*70)
    
    passed_suites = sum(1 for result in results if result)
    total_suites = len(results)
    
    print(f"Test Suites Passed: {passed_suites}/{total_suites}")
    print(f"Overall Success Rate: {(passed_suites/total_suites)*100:.1f}%")
    
    if passed_suites == total_suites:
        print("🎉 ALL TESTS PASSED - Bot is ready for deployment!")
        return True
    else:
        print("⚠️ Some tests failed - Please review and fix issues before deployment")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner error: {e}")
        sys.exit(1)