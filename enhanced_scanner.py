#!/usr/bin/env python3
"""
Enhanced Public API Market Scanner Engine
Complete implementation using only public APIs without authentication
Supports multiple data sources for maximum reliability
"""

import asyncio
import json
import time
import aiohttp
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import statistics
import math
from database import db
from config import Config

@dataclass
class MarketData:
    """Market data structure"""
    symbol: str
    price: float
    volume_24h: float
    change_24h: float
    high_24h: float
    low_24h: float
    timestamp: datetime

@dataclass
class CandleData:
    """Candlestick data structure"""
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: int

@dataclass
class SignalData:
    """Signal data with scoring"""
    symbol: str
    signal_type: str
    price: float
    strength: float
    entry_price: float
    tp_targets: List[float]
    volume: float
    change_percent: float
    filters_passed: List[str]
    whale_activity: bool = False
    liquidity_imbalance: bool = False
    rsi_value: float = 50.0
    message: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class PublicAPIScanner:
    """Enhanced scanner using only public APIs"""
    
    def __init__(self):
        print("🌐 Initializing Public API Scanner (No Authentication Required)")
        
        # Public API sources configuration
        self.api_sources = {
            'coingecko': {
                'name': 'CoinGecko',
                'base_url': 'https://api.coingecko.com/api/v3',
                'rate_limit': 1.0,  # 1 second between requests (free tier)
                'priority': 1,
                'is_active': True,
                'error_count': 0,
                'last_success': None
            },
            'cryptocompare': {
                'name': 'CryptoCompare',
                'base_url': 'https://min-api.cryptocompare.com/data',
                'rate_limit': 0.5,  # 2 requests per second
                'priority': 2,
                'is_active': True,
                'error_count': 0,
                'last_success': None
            },
            'coinpaprika': {
                'name': 'CoinPaprika',
                'base_url': 'https://api.coinpaprika.com/v1',
                'rate_limit': 0.1,  # 10 requests per second
                'priority': 3,
                'is_active': True,
                'error_count': 0,
                'last_success': None
            }
        }
        
        # Symbol mapping for different APIs
        self.symbol_mapping = {
            'coingecko': {
                'BTCUSDT': 'bitcoin',
                'ETHUSDT': 'ethereum',
                'ADAUSDT': 'cardano',
                'BNBUSDT': 'binancecoin',
                'XRPUSDT': 'ripple',
                'SOLUSDT': 'solana',
                'DOTUSDT': 'polkadot',
                'DOGEUSDT': 'dogecoin',
                'AVAXUSDT': 'avalanche-2',
                'MATICUSDT': 'matic-network',
                'LINKUSDT': 'chainlink',
                'LTCUSDT': 'litecoin',
                'BCHUSDT': 'bitcoin-cash',
                'EOSUSDT': 'eos',
                'TRXUSDT': 'tron',
                'ARBUSDT': 'arbitrum',
                'OPUSDT': 'optimism',
                'ATOMUSDT': 'cosmos',
                'NEARUSDT': 'near',
                'APTUSDT': 'aptos'
            },
            'cryptocompare': {
                'BTCUSDT': 'BTC',
                'ETHUSDT': 'ETH',
                'ADAUSDT': 'ADA',
                'BNBUSDT': 'BNB',
                'XRPUSDT': 'XRP',
                'SOLUSDT': 'SOL',
                'DOTUSDT': 'DOT',
                'DOGEUSDT': 'DOGE',
                'AVAXUSDT': 'AVAX',
                'MATICUSDT': 'MATIC',
                'LINKUSDT': 'LINK',
                'LTCUSDT': 'LTC',
                'BCHUSDT': 'BCH',
                'EOSUSDT': 'EOS',
                'TRXUSDT': 'TRX',
                'ARBUSDT': 'ARB',
                'OPUSDT': 'OP',
                'ATOMUSDT': 'ATOM',
                'NEARUSDT': 'NEAR',
                'APTUSDT': 'APT'
            },
            'coinpaprika': {
                'BTCUSDT': 'btc-bitcoin',
                'ETHUSDT': 'eth-ethereum',
                'ADAUSDT': 'ada-cardano',
                'BNBUSDT': 'bnb-binance-coin',
                'XRPUSDT': 'xrp-xrp',
                'SOLUSDT': 'sol-solana',
                'DOTUSDT': 'dot-polkadot',
                'DOGEUSDT': 'doge-dogecoin',
                'AVAXUSDT': 'avax-avalanche',
                'MATICUSDT': 'matic-polygon',
                'LINKUSDT': 'link-chainlink',
                'LTCUSDT': 'ltc-litecoin',
                'BCHUSDT': 'bch-bitcoin-cash',
                'EOSUSDT': 'eos-eos',
                'TRXUSDT': 'trx-tron',
                'ARBUSDT': 'arb-arbitrum',
                'OPUSDT': 'op-optimism-ethereum',
                'ATOMUSDT': 'atom-cosmos',
                'NEARUSDT': 'near-near-protocol',
                'APTUSDT': 'apt-aptos'
            }
        }
        
        # Rate limiting
        self.last_request_times = {}
        
        # Memory management
        self.price_history = {}
        self.volume_history = {}
        self.max_history_size = 100
        
        # Signal detection thresholds
        self.whale_threshold = Config.WHALE_THRESHOLD
        self.liquidity_ratio_threshold = Config.LIQUIDITY_RATIO_THRESHOLD
        self.rsi_overbought = Config.RSI_OVERBOUGHT
        self.rsi_oversold = Config.RSI_OVERSOLD
        
        print("✅ Public API Scanner initialized successfully")
        print(f"📊 Monitoring {len(self.symbol_mapping['coingecko'])} trading pairs")
        print(f"🌐 Using {len(self.api_sources)} public API sources")
    
    async def _rate_limit(self, api_name: str):
        """Apply rate limiting for specific API"""
        if api_name not in self.last_request_times:
            self.last_request_times[api_name] = 0
        
        source = self.api_sources.get(api_name)
        if not source:
            return
        
        time_since_last = time.time() - self.last_request_times[api_name]
        rate_limit = source['rate_limit']
        
        if time_since_last < rate_limit:
            wait_time = rate_limit - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_times[api_name] = time.time()
    
    async def _make_request(self, url: str, timeout: int = 10) -> Optional[Dict]:
        """Make HTTP request with error handling"""
        session = None
        try:
            session = aiohttp.ClientSession()
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"⚠️ HTTP {response.status} for {url}")
                    return None
        except asyncio.TimeoutError:
            print(f"⚠️ Timeout for {url}")
            return None
        except Exception as e:
            print(f"⚠️ Request error for {url}: {e}")
            return None
        finally:
            if session:
                await session.close()
    
    async def _get_coingecko_data(self, symbol: str) -> Optional[MarketData]:
        """Get data from CoinGecko API"""
        await self._rate_limit('coingecko')
        
        coin_id = self.symbol_mapping['coingecko'].get(symbol)
        if not coin_id:
            return None
        
        url = f"{self.api_sources['coingecko']['base_url']}/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
            'include_24hr_vol': 'true'
        }
        
        url_with_params = f"{url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        data = await self._make_request(url_with_params)
        
        if data and coin_id in data:
            coin_data = data[coin_id]
            
            # CoinGecko doesn't provide high/low, so we estimate them
            price = coin_data.get('usd', 0)
            change_24h = coin_data.get('usd_24h_change', 0)
            volume_24h = coin_data.get('usd_24h_vol', 0)
            
            # Estimate high/low based on current price and 24h change
            if change_24h > 0:
                high_24h = price
                low_24h = price / (1 + change_24h / 100)
            else:
                high_24h = price / (1 + change_24h / 100)
                low_24h = price
            
            self.api_sources['coingecko']['error_count'] = max(0, self.api_sources['coingecko']['error_count'] - 1)
            self.api_sources['coingecko']['last_success'] = datetime.now().isoformat()
            
            return MarketData(
                symbol=symbol,
                price=price,
                volume_24h=volume_24h,
                change_24h=change_24h,
                high_24h=high_24h,
                low_24h=low_24h,
                timestamp=datetime.now()
            )
        
        self.api_sources['coingecko']['error_count'] += 1
        return None
    
    async def _get_cryptocompare_data(self, symbol: str) -> Optional[MarketData]:
        """Get data from CryptoCompare API"""
        await self._rate_limit('cryptocompare')
        
        crypto_symbol = self.symbol_mapping['cryptocompare'].get(symbol)
        if not crypto_symbol:
            return None
        
        url = f"{self.api_sources['cryptocompare']['base_url']}/pricemultifull"
        params = {
            'fsyms': crypto_symbol,
            'tsyms': 'USD'
        }
        
        url_with_params = f"{url}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
        data = await self._make_request(url_with_params)
        
        if data and 'RAW' in data and crypto_symbol in data['RAW'] and 'USD' in data['RAW'][crypto_symbol]:
            usd_data = data['RAW'][crypto_symbol]['USD']
            
            price = usd_data.get('PRICE', 0)
            change_24h = usd_data.get('CHANGEPCT24HOUR', 0)
            volume_24h = usd_data.get('VOLUME24HOURTO', 0)
            high_24h = usd_data.get('HIGH24HOUR', price)
            low_24h = usd_data.get('LOW24HOUR', price)
            
            self.api_sources['cryptocompare']['error_count'] = max(0, self.api_sources['cryptocompare']['error_count'] - 1)
            self.api_sources['cryptocompare']['last_success'] = datetime.now().isoformat()
            
            return MarketData(
                symbol=symbol,
                price=price,
                volume_24h=volume_24h,
                change_24h=change_24h,
                high_24h=high_24h,
                low_24h=low_24h,
                timestamp=datetime.now()
            )
        
        self.api_sources['cryptocompare']['error_count'] += 1
        return None
    
    async def _get_coinpaprika_data(self, symbol: str) -> Optional[MarketData]:
        """Get data from CoinPaprika API"""
        await self._rate_limit('coinpaprika')
        
        coin_id = self.symbol_mapping['coinpaprika'].get(symbol)
        if not coin_id:
            return None
        
        url = f"{self.api_sources['coinpaprika']['base_url']}/tickers/{coin_id}"
        data = await self._make_request(url)
        
        if data and 'quotes' in data and 'USD' in data['quotes']:
            usd_data = data['quotes']['USD']
            
            price = usd_data.get('price', 0)
            change_24h = usd_data.get('percent_change_24h', 0)
            volume_24h = usd_data.get('volume_24h', 0)
            
            # CoinPaprika doesn't provide high/low, estimate them
            if change_24h > 0:
                high_24h = price
                low_24h = price / (1 + change_24h / 100)
            else:
                high_24h = price / (1 + change_24h / 100)
                low_24h = price
            
            self.api_sources['coinpaprika']['error_count'] = max(0, self.api_sources['coinpaprika']['error_count'] - 1)
            self.api_sources['coinpaprika']['last_success'] = datetime.now().isoformat()
            
            return MarketData(
                symbol=symbol,
                price=price,
                volume_24h=volume_24h,
                change_24h=change_24h,
                high_24h=high_24h,
                low_24h=low_24h,
                timestamp=datetime.now()
            )
        
        self.api_sources['coinpaprika']['error_count'] += 1
        return None
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get market data using public APIs with fallback"""
        print(f"🔍 Getting market data for {symbol} using public APIs...")
        
        # Try APIs in priority order
        api_methods = [
            ('coingecko', self._get_coingecko_data),
            ('cryptocompare', self._get_cryptocompare_data),
            ('coinpaprika', self._get_coinpaprika_data)
        ]
        
        for api_name, method in api_methods:
            source = self.api_sources[api_name]
            
            # Skip if API is temporarily disabled
            if not source['is_active']:
                continue
            
            # Skip if too many errors
            if source['error_count'] >= 3:
                print(f"⚠️ {source['name']} API temporarily disabled due to errors")
                source['is_active'] = False
                continue
            
            try:
                print(f"🔍 Trying {source['name']} API for {symbol}...")
                result = await method(symbol)
                
                if result:
                    print(f"✅ Got data from {source['name']} for {symbol}")
                    
                    # Store in history for technical analysis
                    self._update_history(symbol, result)
                    
                    return result
                
            except Exception as e:
                print(f"❌ {source['name']} API error for {symbol}: {e}")
                source['error_count'] += 1
        
        print(f"❌ All public APIs failed for {symbol}")
        return None
    
    def _update_history(self, symbol: str, market_data: MarketData):
        """Update price and volume history for technical analysis"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        if symbol not in self.volume_history:
            self.volume_history[symbol] = []
        
        # Add new data
        self.price_history[symbol].append({
            'price': market_data.price,
            'timestamp': market_data.timestamp
        })
        self.volume_history[symbol].append({
            'volume': market_data.volume_24h,
            'timestamp': market_data.timestamp
        })
        
        # Limit history size
        if len(self.price_history[symbol]) > self.max_history_size:
            self.price_history[symbol] = self.price_history[symbol][-self.max_history_size:]
        if len(self.volume_history[symbol]) > self.max_history_size:
            self.volume_history[symbol] = self.volume_history[symbol][-self.max_history_size:]
    
    def _calculate_rsi(self, symbol: str, period: int = 14) -> float:
        """Calculate RSI from price history"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < period + 1:
            return 50.0  # Neutral RSI if insufficient data
        
        prices = [entry['price'] for entry in self.price_history[symbol][-period-1:]]
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if not gains or not losses:
            return 50.0
        
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _detect_whale_activity(self, symbol: str, market_data: MarketData) -> bool:
        """Detect whale activity based on volume and price movement"""
        if market_data.volume_24h < self.whale_threshold:
            return False
        
        # Check for unusual volume compared to recent history
        if symbol in self.volume_history and len(self.volume_history[symbol]) > 5:
            recent_volumes = [entry['volume'] for entry in self.volume_history[symbol][-5:]]
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            
            # Current volume is significantly higher than average
            if market_data.volume_24h > avg_volume * 2:
                return True
        
        return False
    
    def _calculate_signal_strength(self, symbol: str, market_data: MarketData) -> float:
        """Calculate signal strength based on multiple factors"""
        strength = 0.0
        
        # Price change factor (0-40 points)
        change_strength = min(abs(market_data.change_24h) * 4, 40)
        strength += change_strength
        
        # Volume factor (0-30 points)
        if market_data.volume_24h > 1000000:  # $1M+ volume
            volume_strength = min(market_data.volume_24h / 100000, 30)
            strength += volume_strength
        
        # RSI factor (0-20 points)
        rsi = self._calculate_rsi(symbol)
        if rsi > 70 or rsi < 30:  # Overbought or oversold
            rsi_strength = min(abs(rsi - 50) / 2.5, 20)
            strength += rsi_strength
        
        # Whale activity bonus (0-10 points)
        if self._detect_whale_activity(symbol, market_data):
            strength += 10
        
        return min(strength, 100.0)  # Cap at 100
    
    def _generate_tp_targets(self, entry_price: float, signal_type: str, change_percent: float) -> List[float]:
        """Generate take profit targets based on signal strength"""
        targets = []
        
        if signal_type == "LONG":
            # Long targets - prices above entry
            multipliers = [1.02, 1.05, 1.08] if abs(change_percent) < 5 else [1.03, 1.07, 1.12]
            targets = [entry_price * mult for mult in multipliers]
        elif signal_type == "SHORT":
            # Short targets - prices below entry
            multipliers = [0.98, 0.95, 0.92] if abs(change_percent) < 5 else [0.97, 0.93, 0.88]
            targets = [entry_price * mult for mult in multipliers]
        
        return targets
    
    async def analyze_symbol(self, symbol: str) -> Optional[SignalData]:
        """Analyze a symbol and generate signals if criteria are met"""
        try:
            market_data = await self.get_market_data(symbol)
            if not market_data:
                return None
            
            change_percent = market_data.change_24h
            
            # Check if change meets threshold
            if abs(change_percent) < Config.PUMP_THRESHOLD:
                return None
            
            # Determine signal type
            if change_percent >= Config.PUMP_THRESHOLD:
                signal_type = "LONG"
            elif change_percent <= Config.DUMP_THRESHOLD:
                signal_type = "SHORT"
            else:
                return None
            
            # Calculate signal strength
            strength = self._calculate_signal_strength(symbol, market_data)
            
            # Only generate signals above minimum strength
            if strength < Config.SIGNAL_STRENGTH_THRESHOLD:
                return None
            
            # Check RSI filters
            rsi = self._calculate_rsi(symbol)
            if signal_type == "LONG" and rsi > self.rsi_overbought:
                return None  # Don't go long when overbought
            if signal_type == "SHORT" and rsi < self.rsi_oversold:
                return None  # Don't go short when oversold
            
            # Generate filters passed list
            filters_passed = ["Price Change", "Volume", "Public API Data"]
            
            if self._detect_whale_activity(symbol, market_data):
                filters_passed.append("Whale Activity")
            
            if 30 < rsi < 70:
                filters_passed.append("RSI Neutral")
            
            # Generate take profit targets
            tp_targets = self._generate_tp_targets(market_data.price, signal_type, change_percent)
            
            # Create signal message
            message = f"{signal_type} Signal for {symbol}\n"
            message += f"Price: ${market_data.price:.4f}\n"
            message += f"24h Change: {change_percent:+.2f}%\n"
            message += f"Volume: ${market_data.volume_24h:,.0f}\n"
            message += f"Signal Strength: {strength:.1f}/100\n"
            message += f"RSI: {rsi:.1f}\n"
            message += f"Data Source: Public APIs"
            
            return SignalData(
                symbol=symbol,
                signal_type=signal_type,
                price=market_data.price,
                strength=strength,
                entry_price=market_data.price,
                tp_targets=tp_targets,
                volume=market_data.volume_24h,
                change_percent=change_percent,
                filters_passed=filters_passed,
                whale_activity=self._detect_whale_activity(symbol, market_data),
                rsi_value=rsi,
                message=message,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            print(f"❌ Error analyzing {symbol}: {e}")
            return None
    
    async def scan_all_pairs(self) -> List[SignalData]:
        """Scan all configured pairs for signals"""
        print("🔍 Starting comprehensive market scan using public APIs...")
        
        signals = []
        pairs = Config.DEFAULT_PAIRS
        
        print(f"📊 Scanning {len(pairs)} pairs...")
        
        for symbol in pairs:
            try:
                signal = await self.analyze_symbol(symbol)
                if signal:
                    signals.append(signal)
                    print(f"🎯 Signal generated for {symbol}: {signal.signal_type} ({signal.strength:.1f}/100)")
                
                # Small delay between symbols to be respectful to APIs
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"❌ Error scanning {symbol}: {e}")
                continue
        
        print(f"✅ Scan completed. Generated {len(signals)} signals.")
        return signals
    
    async def get_api_status(self) -> Dict:
        """Get status of all public APIs"""
        status = {
            'public_apis': {},
            'total_apis': len(self.api_sources),
            'active_apis': 0,
            'status_text': 'Unknown',
            'connected': False,
            'public_api_mode': True
        }
        
        for api_name, source in self.api_sources.items():
            api_status = {
                'name': source['name'],
                'is_active': source['is_active'],
                'error_count': source['error_count'],
                'priority': source['priority'],
                'last_success': source['last_success']
            }
            
            if source['is_active'] and source['error_count'] < 3:
                status['active_apis'] += 1
            
            status['public_apis'][api_name] = api_status
        
        # Determine overall status
        if status['active_apis'] >= 2:
            status['status_text'] = 'Excellent'
            status['connected'] = True
        elif status['active_apis'] >= 1:
            status['status_text'] = 'Good'
            status['connected'] = True
        else:
            status['status_text'] = 'Issues'
            status['connected'] = False
        
        return status
    
    async def test_api_connectivity(self) -> bool:
        """Test connectivity to public APIs"""
        print("🧪 Testing public API connectivity...")
        
        # Test with BTCUSDT
        result = await self.get_market_data('BTCUSDT')
        
        if result:
            print(f"✅ Public API connectivity test successful")
            print(f"✅ BTCUSDT: ${result.price:.2f} ({result.change_24h:+.2f}%)")
            return True
        else:
            print("❌ Public API connectivity test failed")
            return False
    
    async def get_batch_market_data(self, symbols: List[str]) -> List[Dict]:
        """Get market data for multiple symbols efficiently"""
        print(f"📊 Fetching batch data for {len(symbols)} symbols...")
        
        results = []
        for symbol in symbols:
            try:
                market_data = await self.get_market_data(symbol)
                if market_data:
                    results.append({
                        'symbol': symbol,
                        'price': market_data.price,
                        'change_24h': market_data.change_24h,
                        'volume_24h': market_data.volume_24h,
                        'error': False
                    })
                else:
                    results.append({
                        'symbol': symbol,
                        'price': 0.0,
                        'change_24h': 0.0,
                        'volume_24h': 0.0,
                        'error': True,
                        'error_msg': 'No data available'
                    })
                
                # Small delay between requests to respect rate limits
                await asyncio.sleep(0.2)
                
            except Exception as e:
                results.append({
                    'symbol': symbol,
                    'price': 0.0,
                    'change_24h': 0.0,
                    'volume_24h': 0.0,
                    'error': True,
                    'error_msg': f'Error: {str(e)[:30]}'
                })
        
        return results
    
    async def perform_scheduled_scan(self, telegram_bot=None):
        """Perform scheduled scan and send signals if found"""
        try:
            print("🔍 Performing scheduled market scan...")
            
            # Get monitored pairs from database
            from database import db
            scanner_status = db.get_scanner_status()
            
            # Check if scanner is enabled
            if not scanner_status.get('is_running', True):
                print("📴 Scanner is disabled, skipping scan")
                return
            
            # Get monitored pairs
            import json
            monitored_pairs_str = scanner_status.get('monitored_pairs', '["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]')
            try:
                monitored_pairs = json.loads(monitored_pairs_str)
            except json.JSONDecodeError:
                monitored_pairs = ["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]
            
            signals_found = []
            
            # Scan each pair
            for symbol in monitored_pairs:
                try:
                    signal = await self.analyze_symbol(symbol)
                    if signal:
                        signals_found.append(signal)
                        print(f"🎯 Signal found for {symbol}: {signal.signal_type} ({signal.strength:.1f}%)")
                        
                        # Send signal immediately if telegram bot is available
                        if telegram_bot:
                            await self.send_signal_to_recipients(signal, telegram_bot)
                    
                    # Small delay between symbols
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    print(f"❌ Error scanning {symbol}: {e}")
                    continue
            
            # Update scan statistics
            db.update_scan_stats(len(signals_found))
            
            if signals_found:
                print(f"✅ Scheduled scan completed: {len(signals_found)} signals generated")
            else:
                print("✅ Scheduled scan completed: No signals generated")
                
        except Exception as e:
            print(f"❌ Scheduled scan error: {e}")
    
    async def scan_symbol_comprehensive(self, symbol: str) -> Optional[SignalData]:
        """Comprehensive scan of a single symbol (used by force scan)"""
        try:
            return await self.analyze_symbol(symbol)
        except Exception as e:
            print(f"❌ Error in comprehensive scan for {symbol}: {e}")
            return None
    
    async def send_signal_to_recipients(self, signal: SignalData, telegram_bot):
        """Send signal to all configured recipients"""
        try:
            from config import Config
            from database import db
            
            # Format signal message
            message = self._format_signal_message(signal)
            
            # Send to admin
            if Config.ADMIN_ID:
                try:
                    await telegram_bot.send_message(
                        chat_id=Config.ADMIN_ID,
                        text=message,
                        parse_mode='HTML'
                    )
                    print(f"📤 Signal sent to admin: {Config.ADMIN_ID}")
                except Exception as e:
                    print(f"❌ Failed to send signal to admin: {e}")
            
            # Send to private channel
            if Config.CHANNEL_ID and Config.CHANNEL_ID != 0:
                try:
                    await telegram_bot.send_message(
                        chat_id=Config.CHANNEL_ID,
                        text=message,
                        parse_mode='HTML'
                    )
                    print(f"📤 Signal sent to channel: {Config.CHANNEL_ID}")
                except Exception as e:
                    print(f"❌ Failed to send signal to channel: {e}")
            
            # Send to subscribers
            try:
                subscribers = db.get_subscribers_info()
                for subscriber in subscribers:
                    if subscriber['is_active']:
                        try:
                            await telegram_bot.send_message(
                                chat_id=subscriber['user_id'],
                                text=message,
                                parse_mode='HTML'
                            )
                            print(f"📤 Signal sent to subscriber: {subscriber['user_id']}")
                        except Exception as e:
                            print(f"❌ Failed to send signal to subscriber {subscriber['user_id']}: {e}")
            except Exception as e:
                print(f"❌ Error getting subscribers: {e}")
            
            # Save signal to database
            db.save_signal(signal)
            
        except Exception as e:
            print(f"❌ Error sending signal to recipients: {e}")
    
    def _format_signal_message(self, signal: SignalData) -> str:
        """Format signal for Telegram message"""
        try:
            # Get TP multipliers from settings
            from settings_manager import settings_manager
            system_status = settings_manager.get_system_status()
            tp_multipliers = system_status.get('tp_multipliers', [1.5, 3.0, 5.0, 7.5])
            
            # Calculate TP targets based on multipliers
            tp_targets = []
            for i, multiplier in enumerate(tp_multipliers):
                if signal.signal_type == "LONG":
                    tp_price = signal.entry_price * (1 + multiplier / 100)
                else:  # SHORT
                    tp_price = signal.entry_price * (1 - multiplier / 100)
                tp_targets.append(tp_price)
            
            # Format message according to requirements
            message = f"🚨 <b>#{signal.symbol} ({signal.signal_type}, x20)</b>\n\n"
            message += f"📍 <b>Entry:</b> ${signal.entry_price:.4f}\n"
            message += f"💪 <b>Strength:</b> {signal.strength:.0f}%\n\n"
            message += f"🎯 <b>Take-Profit:</b>\n"
            
            percentages = [40, 60, 80, 100]
            for i, (tp_price, percentage) in enumerate(zip(tp_targets, percentages)):
                message += f"TP{i+1} – ${tp_price:.4f} ({percentage}%)\n"
            
            message += f"\n📊 <b>Analysis:</b>\n"
            message += f"• 24h Change: {signal.change_percent:+.2f}%\n"
            message += f"• Volume: ${signal.volume:,.0f}\n"
            message += f"• RSI: {signal.rsi_value:.1f}\n"
            message += f"• Filters: {', '.join(signal.filters_passed)}\n"
            
            if signal.whale_activity:
                message += f"🐋 <b>Whale Activity Detected</b>\n"
            
            message += f"\n🕐 <b>Time:</b> {signal.timestamp.strftime('%H:%M:%S UTC')}\n"
            message += f"🔓 <b>Source:</b> Public APIs (No Auth Required)"
            
            return message
            
        except Exception as e:
            print(f"❌ Error formatting signal message: {e}")
            return f"🚨 Signal for {signal.symbol}: {signal.signal_type} at ${signal.entry_price:.4f}"

# Create global scanner instance
enhanced_scanner = PublicAPIScanner()