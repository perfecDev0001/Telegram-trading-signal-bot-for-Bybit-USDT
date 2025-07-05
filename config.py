import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Telegram Bot Configuration
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_ID = int(os.getenv('ADMIN_ID', '7974254350'))  # Admin Telegram user ID
    SUBSCRIBER_ID = int(os.getenv('SUBSCRIBER_ID', '0'))  # Default subscriber ID
    CHANNEL_ID = int(os.getenv('CHANNEL_ID', '-1002674839519'))  # Default channel ID
    
    # Bybit API Configuration
    BYBIT_API_KEY = os.getenv('BYBIT_API_KEY', '')
    BYBIT_SECRET = os.getenv('BYBIT_SECRET', '')
    
    # Scanner Configuration
    SCANNER_INTERVAL = int(os.getenv('SCANNER_INTERVAL', '60'))
    PUMP_THRESHOLD = float(os.getenv('PUMP_THRESHOLD', '5.0'))
    DUMP_THRESHOLD = float(os.getenv('DUMP_THRESHOLD', '-5.0'))
    BREAKOUT_THRESHOLD = float(os.getenv('BREAKOUT_THRESHOLD', '3.0'))
    VOLUME_THRESHOLD = float(os.getenv('VOLUME_THRESHOLD', '50.0'))
    
    # Database Configuration
    DATABASE_PATH = os.getenv('DATABASE_PATH', './bot_data.db')
    
    # Enhanced Signal Detection Thresholds
    SIGNAL_STRENGTH_THRESHOLD = float(os.getenv('SIGNAL_STRENGTH_THRESHOLD', '70.0'))
    WHALE_THRESHOLD = float(os.getenv('WHALE_THRESHOLD', '15000.0'))  # $15k minimum
    LIQUIDITY_RATIO_THRESHOLD = float(os.getenv('LIQUIDITY_RATIO_THRESHOLD', '3.0'))  # 3x imbalance
    RSI_OVERBOUGHT = float(os.getenv('RSI_OVERBOUGHT', '75.0'))
    RSI_OVERSOLD = float(os.getenv('RSI_OVERSOLD', '25.0'))
    SPREAD_THRESHOLD = float(os.getenv('SPREAD_THRESHOLD', '0.3'))  # 0.3% max spread
    RANGE_BREAK_THRESHOLD = float(os.getenv('RANGE_BREAK_THRESHOLD', '1.2'))  # 1.2% range break
    
    # Default trading pairs to monitor (USDT Perpetuals)
    DEFAULT_PAIRS = [
        'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'XRPUSDT',
        'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT',
        'LINKUSDT', 'LTCUSDT', 'BCHUSDT', 'EOSUSDT', 'TRXUSDT',
        'ARBUSDT', 'OPUSDT', 'ATOMUSDT', 'NEARUSDT', 'APTUSDT'
    ]

# Validate critical configurations
if not Config.BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables!")

if Config.ADMIN_ID == 0:
    print("⚠️  WARNING: ADMIN_ID not set! Please update your .env file with your Telegram user ID")