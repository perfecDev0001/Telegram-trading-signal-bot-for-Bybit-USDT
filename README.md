# 🚀 Enhanced Bybit Scanner Bot

A comprehensive Python-based Telegram trading signal bot for Bybit USDT Perpetuals with advanced market analysis, multi-layered filtering, and real-time alerts.

## ✨ Core Features

- **🔍 Real-time Market Scanning**: 1-minute interval monitoring of Bybit USDT perpetuals
- **🧠 Advanced Signal Detection**: 10+ layered filters with confluence-based scoring (0-100%)
- **📱 Telegram Integration**: Automated alerts to admin, users, and private channels
- **⚙️ Complete Admin Panel**: Full control via Telegram inline buttons
- **☁️ Cloud Optimized**: Ready for 24/7 deployment on Render platform
- **🎯 High Accuracy**: Only sends high-confidence signals (≥70% strength)

## 🔬 Signal Detection System

### **📊 Price Action Filters**
- ✅ **Breakout Detection**: Closes above short-term resistance
- ✅ **Range Break**: Price closes >1.2% above last high  
- ✅ **Candle Body Rule**: Body >60% of total size (low wick rejection)

### **📈 Volume Filters**
- ✅ **Volume Surge**: 1m volume > 2.5× 5-candle MA
- ✅ **Volume Divergence**: Filters out price up + volume down cases
- ✅ **CVD Analysis**: Cumulative Volume Delta for buy/sell pressure

### **💧 Order Book Filters**
- ✅ **Buy Wall Confirmation**: Large buy walls support long setups
- ✅ **Liquidity Imbalance**: 70/30 order book ratio requirement
- ✅ **Spoofing Detection**: Identifies and filters fake walls
- ✅ **Spread Filter**: Only alerts if spread <0.3%

### **🐋 Whale Activity Filters**
- ✅ **Smart Wallet Tracking**: Monitors large trades >$15k
- ✅ **Whale Confirmation**: Buying/selling activity supports signal direction

### **📉 Technical Filters**
- ✅ **Multi-Timeframe Match**: 1m signal aligns with 5m EMA trend
- ✅ **RSI Momentum Cap**: Blocks LONG if RSI >75, SHORT if RSI <25
- ✅ **New Coin Filter**: Avoids newly listed tokens
- ✅ **Liquidity Support**: Buy-side ≥3× sell-side for LONG signals

## 🎯 Signal Recipients

**Configured Recipients:**
- 👤 **Admin**:
- 👤 **User**:
- 📢 **Channel:

## ⚙️ Quick Setup

### 1. **Clone & Install**
```bash
git clone <repository-url>
cd Bybit_Scanner_Bot
pip install -r requirements.txt
```

### 2. **Configure Environment**
```bash
cp .env.example .env
```

Edit `.env` file:
```env
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=admin_id
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_SECRET=your_bybit_secret_key_here
```

### 3. **Verify Setup**
```bash
python setup_verification.py
```

### 4. **Run Bot**
```bash
python main.py
```

## 📱 Admin Panel Features

Access via Telegram `/start` command:

### **🔧 Scanner Controls**
- ⏸️ **Pause/Resume**: Stop/start market scanning
- 📊 **Status**: View real-time scanner status
- 🧪 **Test Signal**: Send test alert to verify delivery

### **📈 Data & Logs**
- 📋 **Signals Log**: View recent trading signals
- 📊 **Live Monitor**: Real-time market data for top pairs
- 📤 **Export**: Download logs and subscriber lists

### **⚙️ Settings Management**
- 🎯 **Thresholds**: Configure pump/dump/volume thresholds
- 💱 **Trading Pairs**: Add/remove monitored symbols
- 🎯 **TP Multipliers**: Customize take-profit percentages
- 🔍 **Advanced Filters**: Toggle whale tracking, spoofing detection, etc.

### **👥 User Management**
- ➕ **Add Subscribers**: Include new Telegram users
- ➖ **Remove Subscribers**: Manage user access
- 📋 **View List**: See all active subscribers

## 📨 Signal Format

```
#BTCUSDT (Long, x20)

📊 Entry - $50000.00
🎯 Strength: 92%

Take-Profit:
TP1 – $50750.00 (40%)
TP2 – $51500.00 (60%)
TP3 – $52500.00 (80%)
TP4 – $53750.00 (100%)

🔥 Filters Passed:
✅ Breakout Pattern
✅ Volume Surge  
✅ Order Book Imbalance
✅ Whale Activity
✅ Range Break (>1.2%)
✅ Liquidity Support (3x)
✅ Trend Alignment
✅ RSI Filter (65)
✅ No Volume Divergence
✅ Tight Spread

⏰ 15:30:45 UTC
```

## 🚀 Deployment (Render)

### **Automatic Deployment**
1. Connect GitHub repository to Render
2. Set environment variables in Render dashboard
3. Deploy using provided configuration files

### **Configuration Files**
- `render.yaml` - Service configuration
- `Procfile` - Process definition  
- `runtime.txt` - Python version
- `requirements.txt` - Dependencies

### **Environment Variables**
Set in Render dashboard:
```
BOT_TOKEN=your_bot_token
ADMIN_ID=admin_id
BYBIT_API_KEY=your_bybit_api_key_here
BYBIT_SECRET=your_bybit_secret_key_here
```

## 🧪 Testing

Run comprehensive test suite:
```bash
python test_all_features.py
```

Tests include:
- API connectivity
- Signal detection filters
- Database operations
- Message formatting
- Admin panel functions

## 📊 Technical Specifications

### **Performance**
- **Scan Frequency**: Every 60 seconds
- **API Rate Limit**: 20 requests/second (authenticated)
- **Signal Threshold**: ≥70% confluence strength
- **Response Time**: <3 seconds per scan cycle

### **Architecture**
- **Scanner Engine**: `enhanced_scanner.py`
- **Telegram Bot**: `telegram_bot.py`
- **Database**: SQLite with automated backups
- **Configuration**: `settings_manager.py`
- **Entry Point**: `main.py`

### **Security**
- Admin-only access control
- User ID validation
- Error handling with retry logic
- Rate limiting protection

## 📁 Project Structure

```
Bybit_Scanner_Bot/
├── main.py                 # Main entry point
├── config.py              # Configuration settings
├── enhanced_scanner.py    # Market scanner engine
├── telegram_bot.py        # Telegram bot interface
├── database.py           # Database operations
├── settings_manager.py   # Settings management
├── test_all_features.py  # Comprehensive tests
├── setup_verification.py # Setup validation
├── requirements.txt      # Python dependencies
├── Procfile             # Render deployment
├── render.yaml          # Render configuration
├── runtime.txt          # Python version
├── .env.example         # Environment template
└── README.md           # This file
```

## 🆘 Troubleshooting

### **Common Issues**
1. **Bot not responding**: Check BOT_TOKEN in .env
2. **No signals**: Verify thresholds and scanner status
3. **API errors**: Check Bybit API connectivity
4. **Database issues**: Run setup_verification.py

### **Debug Commands**
```bash
python setup_verification.py  # Validate setup
python test_all_features.py   # Run all tests
```

## 📞 Support

- 📖 **Documentation**: `ADMIN_PANEL_GUIDE.md`
- 📋 **Requirements**: `FINAL_CLIENT_REQUIREMENTS_REPORT.md`
- 🧪 **Testing**: Run `test_all_features.py`

## 📄 License

This project is proprietary software developed for specific client requirements.

---

**🎉 Status: Production Ready | 100% Client Requirements Met**