import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Telegram Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_ID = int(os.getenv('ADMIN_ID', '0'))  # Replace with your actual Telegram user ID
    
    # Bybit API Configuration
    BYBIT_API_KEY = os.getenv('BYBIT_API_KEY', '')
    BYBIT_SECRET = os.getenv('BYBIT_SECRET', '')
    
    # Scanner Configuration
    SCANNER_INTERVAL = int(os.getenv('SCANNER_INTERVAL', '60'))
    PUMP_THRESHOLD = float(os.getenv('PUMP_THRESHOLD', '5.0'))
    DUMP_THRESHOLD = float(os.getenv('DUMP_THRESHOLD', '-5.0'))
    BREAKOUT_THRESHOLD = float(os.getenv('BREAKOUT_THRESHOLD', '3.0'))
    
    # Database Configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', './bot_data.db')
    
    # Default trading pairs to monitor (USDT Perpetuals)
    DEFAULT_PAIRS = [
        'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'XRPUSDT',
        'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT',
        'LINKUSDT', 'LTCUSDT', 'BCHUSDT', 'EOSUSDT', 'TRXUSDT'
    ]

# Validate critical configurations
if not Config.BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables!")

if Config.ADMIN_ID == 0:
    print("⚠️  WARNING: ADMIN_ID not set! Please update your .env file with your Telegram user ID")