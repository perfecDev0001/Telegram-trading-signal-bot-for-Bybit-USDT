#!/usr/bin/env python3
"""
Enhanced Bybit Market Scanner Engine
Complete implementation with advanced filtering and signal scoring
"""

import asyncio
import json
import time
import requests
import aiohttp
import hashlib
import hmac
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
class OrderBookData:
    """Order book data structure"""
    bids: List[Tuple[float, float]]  # [(price, size), ...]
    asks: List[Tuple[float, float]]  # [(price, size), ...]
    timestamp: datetime

@dataclass
class WhaleActivity:
    """Whale activity data"""
    large_trades: List[Dict]
    total_buy_volume: float
    total_sell_volume: float
    net_flow: float
    is_bullish: bool

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
    filters_passed: List[str]  # Changed to List[str] to match client format
    whale_activity: bool = False
    liquidity_imbalance: bool = False
    rsi_value: float = 50.0
    message: str = ""
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class EnhancedBybitScanner:
    def __init__(self):
        self.base_url = "https://api.bybit.com"
        self.api_key = Config.BYBIT_API_KEY if hasattr(Config, 'BYBIT_API_KEY') and Config.BYBIT_API_KEY else None
        # We're using public API only, so we don't need the secret
        self.api_secret = None
        
        # Optimized memory management with circular buffers
        self.price_history = {}  # Limited to last 100 entries per symbol
        self.volume_history = {}  # Limited to last 100 entries per symbol
        self.last_scan_time = {}
        self.max_history_size = 100  # Prevent memory leaks
        
        # Rate limiting optimized for public API
        self.last_request_time = 0
        # More conservative rate limiting for public API (5 requests per second max)
        self.min_request_interval = 0.25  # 250ms between requests (4 req/sec) to stay under limits
        self.api_errors = 0  # Track API errors for adaptive rate limiting
        self.request_count = 0
        self.request_window_start = time.time()
        self.max_requests_per_window = 10  # Max 10 requests per 1-second window
        
        # New filter thresholds for enhanced requirements
        self.whale_threshold = 15000  # $15k minimum for whale detection
        self.liquidity_ratio_threshold = 3.0  # 3x imbalance required
        self.rsi_overbought = 75  # Block LONG signals above this
        self.rsi_oversold = 25   # Block SHORT signals below this
        
    async def _rate_limit(self):
        """Implement enhanced rate limiting for public API"""
        current_time = time.time()
        
        # Check time since last request (basic rate limiting)
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        # Check if we're in a new time window
        window_duration = current_time - self.request_window_start
        if window_duration >= 1.0:  # 1 second window
            # Reset for new window
            self.request_window_start = current_time
            self.request_count = 0
        
        # Check if we've exceeded our rate limit for this window
        if self.request_count >= self.max_requests_per_window:
            # Wait until the end of the current window
            wait_time = 1.0 - window_duration
            if wait_time > 0:
                print(f"⚠️ Rate limit approaching, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                # Reset for new window
                self.request_window_start = time.time()
                self.request_count = 0
        
        # Update tracking variables
        self.last_request_time = time.time()
        self.request_count += 1
        
    async def _make_api_request(self, url, params, headers, max_retries=3, timeout=15):
        """Make API request with retry logic using aiohttp - optimized for public API"""
        retries = 0
        last_error = None
        
        # For public API, use a more conservative timeout
        if not self.api_secret:
            timeout = min(timeout, 10)  # More conservative timeout for public API
        
        while retries < max_retries:
            try:
                # Use a more conservative timeout configuration for public API
                timeout_config = aiohttp.ClientTimeout(total=timeout, connect=5, sock_read=5)
                
                # Use a simpler request approach with fewer options
                async with aiohttp.ClientSession(timeout=timeout_config) as session:
                    async with session.get(url, params=params, headers=headers) as response:
                        if response.status == 200:
                            try:
                                response_data = await response.json()
                                # Create a mock response object for compatibility
                                class MockResponse:
                                    def __init__(self, status, data):
                                        self.status_code = status
                                        self._data = data
                                    def json(self):
                                        return self._data
                                return MockResponse(200, response_data)
                            except Exception as e:
                                print(f"⚠️ Error parsing JSON response: {e}")
                                last_error = f"JSON parse error: {e}"
                        elif response.status == 429:  # Rate limit exceeded
                            wait_time = 2 ** retries  # Exponential backoff
                            print(f"⚠️ Rate limit exceeded, waiting {wait_time}s before retry...")
                            self.api_errors += 1  # Increment error count for rate limiting
                            await asyncio.sleep(wait_time)
                            last_error = f"Rate limit exceeded (429)"
                        else:
                            try:
                                response_text = await response.text()
                                error_msg = f"HTTP {response.status}: {response_text[:200]}"
                            except:
                                error_msg = f"HTTP {response.status}: Unable to read response"
                            
                            print(f"⚠️ API request failed: {error_msg}")
                            self.api_errors += 1  # Increment error count for rate limiting
                            last_error = error_msg
                            
            except asyncio.TimeoutError:
                error_msg = f"Request timed out after {timeout}s"
                print(f"⚠️ {error_msg}, retrying ({retries+1}/{max_retries})...")
                self.api_errors += 1  # Increment error count for rate limiting
                last_error = error_msg
            except aiohttp.ClientError as e:
                error_msg = f"Connection error: {e}"
                print(f"⚠️ {error_msg}, retrying ({retries+1}/{max_retries})...")
                self.api_errors += 1  # Increment error count for rate limiting
                last_error = error_msg
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                print(f"⚠️ {error_msg}, retrying ({retries+1}/{max_retries})...")
                self.api_errors += 1  # Increment error count for rate limiting
                last_error = error_msg
            
            retries += 1
            if retries < max_retries:
                # Exponential backoff with jitter
                wait_time = (2 ** retries) + (random.random() * 0.5)
                await asyncio.sleep(wait_time)
        
        print(f"❌ All retries failed. Last error: {last_error}")
        self.api_errors += 1  # Increment error count for rate limiting
        return None  # All retries failed
    
    def _generate_signature(self, params: str, timestamp: str) -> str:
        """Generate HMAC SHA256 signature for authenticated requests"""
        if not self.api_secret:
            return ""
        
        param_str = f"{timestamp}{self.api_key}{params}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _get_auth_headers(self, params: Dict = None) -> Dict[str, str]:
        """Get headers for public API requests"""
        headers = {
            'Content-Type': 'application/json'
        }
        
        # Add API key if available (helps with higher rate limits)
        if self.api_key:
            headers['X-BAPI-API-KEY'] = self.api_key
        
        return headers
    
    def _manage_memory(self, symbol: str):
        """Manage memory by limiting history size"""
        for history_dict in [self.price_history, self.volume_history]:
            if symbol in history_dict and len(history_dict[symbol]) > self.max_history_size:
                # Keep only the most recent entries
                history_dict[symbol] = history_dict[symbol][-self.max_history_size:]
    
    def _adaptive_rate_limit(self):
        """Adjust rate limiting based on API performance for public endpoints"""
        if self.api_errors > 3:
            # Slow down significantly if we're getting errors (public API is stricter)
            self.min_request_interval = min(0.5, self.min_request_interval * 1.5)  # Up to 500ms between requests
            self.max_requests_per_window = max(5, self.max_requests_per_window - 1)  # Reduce window limit
            print(f"⚠️ Reducing API rate limits due to errors: {self.min_request_interval:.2f}s interval, {self.max_requests_per_window} req/window")
            self.api_errors = 0
        elif self.api_errors == 0:
            # Speed up very gradually if no errors
            self.min_request_interval = max(0.2, self.min_request_interval * 0.95)  # No faster than 200ms
            if self.min_request_interval < 0.3:  # Only increase window limit if we're at a good interval
                self.max_requests_per_window = min(10, self.max_requests_per_window + 1)  # Increase window limit
    
    async def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Get comprehensive market data for a symbol"""
        await self._rate_limit()
        
        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {
                'category': 'linear',  # Using perpetual futures
                'symbol': symbol
            }
            
            # Get headers (will be public if no API key)
            headers = self._get_auth_headers()
            
            response = await self._make_api_request(url, params, headers)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    ticker = data['result']['list'][0]
                    self.api_errors = max(0, self.api_errors - 1)  # Reduce error count on success
                    
                    # Handle potential missing or invalid data
                    try:
                        price = float(ticker.get('lastPrice', 0))
                        volume_24h = float(ticker.get('volume24h', 0))
                        change_24h = float(ticker.get('price24hPcnt', 0)) * 100
                        high_24h = float(ticker.get('highPrice24h', 0))
                        low_24h = float(ticker.get('lowPrice24h', 0))
                        
                        return MarketData(
                            symbol=symbol,
                            price=price,
                            volume_24h=volume_24h,
                            change_24h=change_24h,
                            high_24h=high_24h,
                            low_24h=low_24h,
                            timestamp=datetime.now()
                        )
                    except (ValueError, TypeError) as e:
                        print(f"❌ Error parsing ticker data for {symbol}: {e}")
                        self.api_errors += 1
                else:
                    print(f"❌ API returned error for {symbol}: {data.get('retMsg', 'Unknown error')}")
                    self.api_errors += 1
            else:
                print(f"❌ HTTP error for {symbol}: {response.status_code if response else 'No response'}")
                self.api_errors += 1
            return None
        except Exception as e:
            print(f"❌ Error fetching market data for {symbol}: {e}")
            self.api_errors += 1
            return None
    
    async def get_kline_data(self, symbol: str, interval: str = "1", limit: int = 100) -> List[CandleData]:
        """Get candlestick data with enhanced structure"""
        await self._rate_limit()
        
        try:
            url = f"{self.base_url}/v5/market/kline"
            params = {
                'category': 'linear',
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            # Get headers (will be public if no API key)
            headers = self._get_auth_headers()
            
            response = await self._make_api_request(url, params, headers)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    candles = []
                    for kline in data['result']['list']:
                        candles.append(CandleData(
                            open=float(kline[1]),
                            high=float(kline[2]),
                            low=float(kline[3]),
                            close=float(kline[4]),
                            volume=float(kline[5]),
                            timestamp=int(kline[0])
                        ))
                    self.api_errors = max(0, self.api_errors - 1)  # Reduce error count on success
                    return candles
                else:
                    print(f"❌ Kline API returned error for {symbol}: {data.get('retMsg', 'Unknown error')}")
            else:
                print(f"❌ Kline HTTP error for {symbol}: {response.status_code if response else 'No response'}")
            return []
        except Exception as e:
            print(f"❌ Error fetching klines for {symbol}: {e}")
            self.api_errors += 1
            return []
    
    async def get_order_book(self, symbol: str, depth: int = 25) -> Optional[OrderBookData]:
        """Get order book data for liquidity analysis"""
        await self._rate_limit()
        
        try:
            url = f"{self.base_url}/v5/market/orderbook"
            params = {
                'category': 'linear',
                'symbol': symbol,
                'limit': depth
            }
            
            # Get headers (will be public if no API key)
            headers = self._get_auth_headers()
            
            response = await self._make_api_request(url, params, headers)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0 and data.get('result'):
                    result = data['result']
                    
                    bids = [(float(bid[0]), float(bid[1])) for bid in result.get('b', [])]
                    asks = [(float(ask[0]), float(ask[1])) for ask in result.get('a', [])]
                    
                    self.api_errors = max(0, self.api_errors - 1)  # Reduce error count on success
                    return OrderBookData(
                        bids=bids,
                        asks=asks,
                        timestamp=datetime.now()
                    )
                else:
                    print(f"❌ Order book API returned error for {symbol}: {data.get('retMsg', 'Unknown error')}")
            else:
                print(f"❌ Order book HTTP error for {symbol}: {response.status_code if response else 'No response'}")
            return None
        except Exception as e:
            print(f"❌ Error fetching order book for {symbol}: {e}")
            self.api_errors += 1
            return None
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return sum(prices) / len(prices)
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def analyze_price_action(self, candles: List[CandleData], market_data: MarketData) -> Dict[str, any]:
        """Analyze price action for breakout detection"""
        if len(candles) < 20:
            return {'breakout': False, 'candle_strength': 0}
        
        current_candle = candles[0]  # Most recent candle
        recent_highs = [c.high for c in candles[:20]]
        resistance_level = max(recent_highs[1:])  # Exclude current candle
        
        # Check breakout conditions
        breakout_threshold = 1.2  # 1.2% breakout requirement
        price_breakout = (current_candle.close - resistance_level) / resistance_level * 100
        
        # Candle body strength
        candle_body = abs(current_candle.close - current_candle.open)
        candle_range = current_candle.high - current_candle.low
        body_strength = (candle_body / candle_range) * 100 if candle_range > 0 else 0
        
        breakout_detected = (
            price_breakout > breakout_threshold and
            body_strength > 60 and
            current_candle.close > current_candle.open  # Bullish candle
        )
        
        return {
            'breakout': breakout_detected,
            'price_breakout_percent': price_breakout,
            'candle_strength': body_strength,
            'resistance_level': resistance_level
        }
    
    def analyze_volume(self, candles: List[CandleData]) -> Dict[str, any]:
        """Analyze volume patterns"""
        if len(candles) < 5:
            return {'volume_surge': False, 'volume_ratio': 1.0}
        
        current_volume = candles[0].volume
        recent_volumes = [c.volume for c in candles[1:6]]  # Last 5 candles
        avg_volume = sum(recent_volumes) / len(recent_volumes)
        
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        volume_surge = volume_ratio >= 2.5
        
        # CVD simulation (buy pressure estimation)
        bullish_volume = sum(c.volume for c in candles[:5] if c.close > c.open)
        total_volume = sum(c.volume for c in candles[:5])
        buy_pressure = (bullish_volume / total_volume) * 100 if total_volume > 0 else 50
        
        return {
            'volume_surge': volume_surge,
            'volume_ratio': volume_ratio,
            'buy_pressure': buy_pressure,
            'cvd_bullish': buy_pressure > 60
        }
    
    def analyze_order_book(self, order_book: OrderBookData, current_price: float) -> Dict[str, any]:
        """Analyze order book for liquidity patterns"""
        if not order_book or not order_book.bids or not order_book.asks:
            return {'imbalance': False, 'buy_wall': False, 'spoofing': False}
        
        # Calculate bid/ask volumes
        bid_volume = sum(size for _, size in order_book.bids[:10])
        ask_volume = sum(size for _, size in order_book.asks[:10])
        total_volume = bid_volume + ask_volume
        
        # Liquidity imbalance (70/30 ratio)
        bid_ratio = (bid_volume / total_volume) * 100 if total_volume > 0 else 50
        imbalance_detected = bid_ratio >= 70 or bid_ratio <= 30
        
        # Buy wall detection (large bid orders)
        large_bids = [size for price, size in order_book.bids if size > bid_volume * 0.1]
        buy_wall = len(large_bids) > 0
        
        # Spoofing detection (large orders far from price)
        best_bid = order_book.bids[0][0]
        best_ask = order_book.asks[0][0]
        spread_percent = ((best_ask - best_bid) / current_price) * 100
        
        # Check for large orders that might be spoofing
        far_bids = [size for price, size in order_book.bids 
                   if (current_price - price) / current_price > 0.02]  # >2% from price
        spoofing_detected = len(far_bids) > 0 and sum(far_bids) > bid_volume * 0.3
        
        return {
            'imbalance': imbalance_detected,
            'bid_ratio': bid_ratio,
            'buy_wall': buy_wall,
            'spoofing': spoofing_detected,
            'spread_percent': spread_percent,
            'tight_spread': spread_percent < 0.3
        }
    
    def detect_whale_activity_from_candles(self, candles: List[CandleData], order_book: OrderBookData) -> Dict[str, any]:
        """Simulate whale activity detection from candle data"""
        if len(candles) < 3:
            return {'whale_detected': False, 'confidence': 0}
        
        # Large volume candles
        current_volume = candles[0].volume
        avg_volume = sum(c.volume for c in candles[1:6]) / 5 if len(candles) > 5 else current_volume
        
        volume_spike = current_volume > avg_volume * 3  # 3x normal volume
        
        # Large price movement with volume
        price_change = abs(candles[0].close - candles[1].close) / candles[1].close * 100
        significant_move = price_change > 2.0  # >2% move
        
        # Order book whale signs
        whale_orders = False
        if order_book:
            large_orders = [size for _, size in order_book.bids + order_book.asks 
                          if size > avg_volume * 0.1]
            whale_orders = len(large_orders) > 0
        
        confidence = 0
        if volume_spike:
            confidence += 40
        if significant_move:
            confidence += 30
        if whale_orders:
            confidence += 30
        
        return {
            'whale_detected': confidence >= 60,
            'confidence': confidence,
            'volume_spike': volume_spike,
            'significant_move': significant_move,
            'whale_orders': whale_orders
        }
    
    def analyze_trend_confluence(self, candles: List[CandleData], current_price: float) -> Dict[str, any]:
        """Analyze trend confluence for 1m/5m EMA match and spread check"""
        if len(candles) < 20:
            return {'ema_alignment': False, 'spread_check': False}
        
        # Calculate 1-minute EMAs
        ema_short = self.calculate_ema([c.close for c in candles[:10]], 5)
        ema_long = self.calculate_ema([c.close for c in candles[:20]], 20)
        
        # EMA alignment (trend confirmation)
        ema_alignment = ema_short > ema_long if current_price > ema_short else ema_short < ema_long
        
        # Spread check (using bid-ask simulation)
        avg_price = sum(c.close for c in candles[:3]) / 3
        spread_percent = abs(current_price - avg_price) / avg_price * 100
        spread_check = spread_percent < 0.5  # Tight spread
        
        return {
            'ema_alignment': ema_alignment,
            'spread_check': spread_check,
            'ema_short': ema_short,
            'ema_long': ema_long,
            'spread_percent': spread_percent
        }
    
    def calculate_signal_strength(self, filters: Dict[str, any]) -> float:
        """Calculate signal strength based on filter confluence (Client Requirements)"""
        
        # Start with minimum threshold
        strength = 0.0
        
        # Filter weights according to client requirements
        weights = {
            # Price Action Filters (30%)
            'breakout_pattern': 10.0,        # Breakout confirmation
            'range_break': 10.0,             # >1.2% above last high
            'candle_body': 10.0,             # >60% body rule
            
            # Volume Filters (25%)
            'volume_surge': 15.0,            # 1m > 2.5× 5-candle MA
            'volume_divergence': 5.0,        # No price up + volume down
            'buy_pressure': 5.0,             # CVD confirmation
            
            # Order Book Filters (20%)
            'order_book_imbalance': 10.0,    # 70/30 ratio
            'liquidity_support': 5.0,        # 3x liquidity requirement
            'tight_spread': 5.0,             # <0.3% spread
            
            # Whale Activity (15%)
            'whale_activity': 15.0,          # Large trades >$15k
            
            # Technical Filters (10%)
            'trend_match': 5.0,              # 1m/5m EMA alignment
            'rsi_filter': 3.0,               # RSI 75/25 caps
            'new_coin_filter': 2.0           # Avoid new tokens
        }
        
        # Price Action Filters
        if filters.get('price_action', {}).get('breakout'):
            strength += weights['breakout_pattern']
        
        if filters.get('price_action', {}).get('range_break'):
            strength += weights['range_break']
            
        if filters.get('price_action', {}).get('candle_body'):
            strength += weights['candle_body']
        
        # Volume Filters
        if filters.get('volume', {}).get('volume_surge'):
            strength += weights['volume_surge']
            
        if filters.get('volume', {}).get('volume_divergence'):
            strength += weights['volume_divergence']
            
        if filters.get('volume', {}).get('buy_pressure'):
            strength += weights['buy_pressure']
        
        # Order Book Filters
        if filters.get('order_book', {}).get('imbalance'):
            strength += weights['order_book_imbalance']
            
        if filters.get('order_book', {}).get('liquidity_support'):
            strength += weights['liquidity_support']
            
        if filters.get('order_book', {}).get('tight_spread'):
            strength += weights['tight_spread']
        
        # Whale Activity
        if filters.get('whale', {}).get('whale_detected'):
            strength += weights['whale_activity']
        
        # Technical Filters
        if filters.get('technical', {}).get('trend_match'):
            strength += weights['trend_match']
            
        if filters.get('technical', {}).get('rsi_filter'):
            strength += weights['rsi_filter']
            
        if filters.get('technical', {}).get('new_coin_filter'):
            strength += weights['new_coin_filter']
        
        # Bonus points for spoofing detection (clean = bonus)
        if not filters.get('order_book', {}).get('spoofing'):
            strength += 3.0
        
        # Only signals ≥70% strength meet client requirements
        return max(strength, 70.0) if strength >= 70.0 else 0.0
    
    def calculate_tp_targets(self, entry_price: float, tp_multipliers: List[float]) -> List[float]:
        """Calculate take profit targets"""
        targets = []
        for multiplier in tp_multipliers:
            target_price = entry_price * (1 + multiplier / 100)
            targets.append(target_price)
        return targets
    
    async def scan_symbol_comprehensive(self, symbol: str) -> Optional[SignalData]:
        """Comprehensive symbol analysis with all filters"""
        try:
            # Get all required data
            market_data = await self.get_market_data(symbol)
            if not market_data:
                return None
            
            candles_5m = await self.get_kline_data(symbol, "5", 50)
            candles_1m = await self.get_kline_data(symbol, "1", 20)  # Supporting data
            order_book = await self.get_order_book(symbol)
            
            if not candles_5m:
                return None
            
            # Get scanner settings (including new filters)
            scanner_status = db.get_scanner_status()
            settings = {
                'pump_threshold': scanner_status.get('pump_threshold', 5.0),
                'dump_threshold': scanner_status.get('dump_threshold', -5.0),
                'volume_threshold': scanner_status.get('volume_threshold', 50.0),
                'whale_tracking': scanner_status.get('whale_tracking', True),
                'spoofing_detection': scanner_status.get('spoofing_detection', False),
                'spread_filter': scanner_status.get('spread_filter', True),
                'trend_match': scanner_status.get('trend_match', True),
                'liquidity_imbalance': scanner_status.get('liquidity_imbalance', True),
                'rsi_momentum': scanner_status.get('rsi_momentum', True)
            }
            
            # Apply all filters
            filters = {}
            
            # 1. Price Action Analysis (5-minute candles as primary)
            filters['price_action'] = self.analyze_price_action(candles_5m, market_data)
            
            # 2. Volume Analysis (5-minute candles as primary)
            filters['volume'] = self.analyze_volume(candles_5m)
            
            # 3. Order Book Analysis
            if order_book:
                filters['order_book'] = self.analyze_order_book(order_book, market_data.price)
            else:
                filters['order_book'] = {'imbalance': False, 'tight_spread': True, 'spoofing': False}
            
            # 4. Whale Activity (if enabled)
            if settings['whale_tracking']:
                filters['whale'] = self.detect_whale_activity_from_candles(candles_5m, order_book)
            else:
                filters['whale'] = {'whale_detected': False}
            
            # 5. Check if signal should be generated
            signal_triggered = False
            signal_type = ""
            
            # Breakout signal
            if filters['price_action']['breakout'] and filters['volume']['volume_surge']:
                signal_triggered = True
                signal_type = "BREAKOUT_LONG"
            
            # Pump/Dump signals
            elif market_data.change_24h >= settings['pump_threshold']:
                if filters['volume']['volume_surge']:
                    signal_triggered = True
                    signal_type = "PUMP"
            
            elif market_data.change_24h <= settings['dump_threshold']:
                if filters['volume']['volume_surge']:
                    signal_triggered = True
                    signal_type = "DUMP"
            
            if not signal_triggered:
                return None
            
            # Apply new enhanced filters
            if settings['liquidity_imbalance'] or settings['rsi_momentum']:
                # Calculate base strength first
                base_strength = self.calculate_signal_strength(filters)
                
                # Apply enhanced filters
                signal_valid, final_strength, filter_results = await self.analyze_signal_with_new_filters(
                    symbol, signal_type, base_strength
                )
                
                if not signal_valid:
                    print(f"🚫 Signal blocked for {symbol}: Enhanced filters failed")
                    return None
                
                strength = final_strength
                
                # Update filters_passed with new filter results
                enhanced_filters = {
                    'price_action': filters['price_action']['breakout'],
                    'volume_surge': filters['volume']['volume_surge'],
                    'order_book_imbalance': filters['order_book']['imbalance'],
                    'whale_activity': filters['whale']['whale_detected'],
                    'liquidity_imbalance': filter_results['liquidity_imbalance']['passed'],
                    'rsi_momentum': filter_results['rsi_momentum']['passed'],
                    'range_break': filter_results['range_break']['passed'],
                    'volume_divergence': filter_results['volume_divergence']['passed'],
                    'trend_match': filter_results['trend_match']['passed'],
                    'new_coin': filter_results['new_coin']['passed'],
                    'spread_filter': filters['order_book']['tight_spread']
                }
                
                # Store additional data for signal
                whale_activity = filter_results['whale_activity']['detected']
                liquidity_imbalance = filter_results['liquidity_imbalance']['passed']
                rsi_value = filter_results['rsi_momentum']['rsi_value']
                
            else:
                # Use original logic if new filters are disabled
                strength = self.calculate_signal_strength(filters)
                
                # Skip weak signals
                if strength < 75.0:  # Only send high-confidence signals
                    return None
                
                enhanced_filters = {
                    'price_action': filters['price_action']['breakout'],
                    'volume_surge': filters['volume']['volume_surge'],
                    'order_book_imbalance': filters['order_book']['imbalance'],
                    'whale_activity': filters['whale']['whale_detected']
                }
                
                whale_activity = filters['whale']['whale_detected']
                liquidity_imbalance = False
                rsi_value = 50.0
            
            # Calculate TP targets
            tp_multipliers_str = scanner_status.get('tp_multipliers', '[1.5, 3.0, 5.0, 7.5]')
            tp_multipliers = json.loads(tp_multipliers_str)
            tp_targets = self.calculate_tp_targets(market_data.price, tp_multipliers)
            
            # Create enhanced signal
            signal = SignalData(
                symbol=symbol,
                signal_type=signal_type,
                price=market_data.price,
                strength=strength,
                entry_price=market_data.price,
                tp_targets=tp_targets,
                volume=market_data.volume_24h,
                change_percent=market_data.change_24h,
                filters_passed=enhanced_filters,
                whale_activity=whale_activity,
                liquidity_imbalance=liquidity_imbalance,
                rsi_value=rsi_value
            )
            
            return signal
            
        except Exception as e:
            print(f"❌ Error in comprehensive scan for {symbol}: {e}")
            return None
    
    async def scan_all_pairs(self) -> List[SignalData]:
        """Scan all monitored pairs comprehensively"""
        scanner_status = db.get_scanner_status()
        
        # Check if scanner is paused
        is_running = scanner_status.get('is_running', True)
        if not is_running:
            print("⏸️ Scanner is paused")
            return []
        
        # Get monitored pairs
        monitored_pairs_str = scanner_status.get('monitored_pairs', '[]')
        try:
            monitored_pairs = json.loads(monitored_pairs_str)
        except:
            monitored_pairs = Config.DEFAULT_PAIRS
        
        print(f"🔍 Comprehensive scanning {len(monitored_pairs)} pairs...")
        
        signals = []
        
        # Use enhanced comprehensive scan with timeout protection
        async def scan_with_timeout(symbol):
            try:
                # Set a timeout for each individual scan
                return await asyncio.wait_for(
                    self.enhanced_comprehensive_scan(symbol),  # Use new enhanced scan
                    timeout=30  # 30 second timeout per symbol
                )
            except asyncio.TimeoutError:
                print(f"⏱️ Scan timed out for {symbol}")
                return None
            except Exception as e:
                print(f"❌ Error scanning {symbol}: {e}")
                return None
        
        # Process symbols in smaller batches with more conservative limits for public API
        batch_size = 3  # Smaller batch size for public API
        for i in range(0, len(monitored_pairs), batch_size):
            batch = monitored_pairs[i:i+batch_size]
            print(f"📊 Processing batch {i//batch_size + 1}/{math.ceil(len(monitored_pairs)/batch_size)}: {', '.join(batch)}")
            
            # Use semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(2)  # Max 2 concurrent requests for public API
            
            async def limited_scan(symbol):
                async with semaphore:
                    return await scan_with_timeout(symbol)
            
            batch_results = await asyncio.gather(*[limited_scan(symbol) for symbol in batch])
            
            for symbol, result in zip(batch, batch_results):
                if result:
                    signals.append(result)
                    print(f"🎯 Signal generated for {symbol}: {result.signal_type} ({result.strength:.1f}%)")
            
            # Add a longer delay between batches for public API
            delay = 2.0  # 2 seconds between batches
            print(f"⏱️ Waiting {delay}s before next batch to respect rate limits...")
            await asyncio.sleep(delay)
        
        return signals
    
    def format_signal_message(self, signal: SignalData) -> str:
        """Format signal message EXACTLY as per client requirements"""
        
        # Client exact format requirements
        direction = "Long" if signal.signal_type in ["PUMP", "BREAKOUT_LONG"] else "Short"
        leverage = "x20"  # Fixed leverage reference
        
        # Format TP targets exactly as client specified
        tp_lines = []
        percentages = [40, 60, 80, 100]  # Client specified distribution
        for i, (tp_price, pct) in enumerate(zip(signal.tp_targets, percentages)):
            tp_lines.append(f"TP{i+1} – ${tp_price:.4f} ({pct}%)")
        
        # Create filters passed list exactly as shown in client requirements
        filters_text = "\n".join(signal.filters_passed) if signal.filters_passed else "✅ Basic filters passed"
        
        # EXACT client format: #COIN/USDT (Long, x20)
        message = f"""#{signal.symbol} ({direction}, {leverage})

📊 **Entry** - ${signal.price:.4f}
🎯 **Strength:** {signal.strength:.0f}%

**Take-Profit:**
{chr(10).join(tp_lines)}

🔥 **Filters Passed:**
{filters_text}

⏰ {signal.timestamp.strftime('%H:%M:%S')} UTC"""
        
        return message
    
    async def send_signal_to_recipients(self, signal: SignalData, bot):
        """Send signal to all configured recipients"""
        try:
            message = self.format_signal_message(signal)
            
            # Get active subscribers from database
            from database import db
            active_subscribers = db.get_active_subscribers()
            
            # Add default recipients (from config)
            from config import Config
            hardcoded_recipients = [
                Config.ADMIN_ID,  # Admin from environment variable
                Config.SUBSCRIBER_ID,  # Default subscriber
                Config.CHANNEL_ID  # Default channel
            ]
            
            # Combine all recipients (remove duplicates)
            all_recipients = list(set(active_subscribers + hardcoded_recipients))
            
            sent_count = 0
            
            for recipient in all_recipients:
                try:
                    await bot.send_message(
                        chat_id=recipient,
                        text=message,
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                    print(f"✅ Enhanced signal sent to {recipient}")
                    
                except Exception as e:
                    print(f"❌ Failed to send signal to {recipient}: {e}")
                    continue
            
            # Log signal to database
            db.log_signal(
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                price=signal.price,
                change_percent=signal.change_percent,
                volume=signal.volume,
                message=message
            )
            
            print(f"📤 Enhanced signal sent to {sent_count} recipients and logged")
            
        except Exception as e:
            print(f"❌ Error sending enhanced signal: {e}")
    
    async def test_api_connectivity(self) -> bool:
        """Test API connectivity for public endpoints"""
        try:
            print("🔍 Testing Bybit public API connectivity...")
            
            # Test basic connection with a simple ticker request
            url = f"{self.base_url}/v5/market/tickers"
            params = {
                'category': 'linear',
                'symbol': 'BTCUSDT'
            }
            
            headers = self._get_auth_headers()
            response = await self._make_api_request(url, params, headers)
            
            if response and response.status_code == 200:
                data = response.json()
                if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                    ticker = data['result']['list'][0]
                    price = float(ticker['lastPrice'])
                    
                    print(f"✅ Public API Connection: SUCCESS")
                    print(f"✅ Using API Key for Rate Limits: {'Yes' if self.api_key else 'No'}")
                    print(f"✅ Mode: Public API (Read-Only)")
                    print(f"✅ Rate Limit: {1/self.min_request_interval:.1f} requests/second, {self.max_requests_per_window} per window")
                    print(f"✅ Test Data: BTCUSDT @ ${price:,.2f}")
                    
                    return True
                else:
                    print(f"❌ API returned error: {data.get('retMsg', 'Unknown error')}")
                    return False
            else:
                print(f"❌ HTTP error: {response.status_code if response else 'No response'}")
                return False
            
        except Exception as e:
            print(f"❌ API connectivity test failed: {e}")
            return False
    
    async def run_enhanced_scanner(self, bot_instance=None):
        """Main enhanced scanner loop"""
        print("🚀 Starting Enhanced Bybit Scanner...")
        print("🔍 Using 5-minute candles with advanced filtering")
        print("📊 Confluence-based signal generation")
        print("⚡ Real-time order book analysis using public API")
        print("⚠️ Using public API with optimized rate limiting")
        
        # Test API connectivity first
        if not await self.test_api_connectivity():
            print("⚠️ API connectivity issues - scanner may not work properly")
            print("🔧 Check your internet connection and API configuration")
        else:
            print("✅ Public API connection successful - scanner ready")
            print(f"⏱️ Rate limits: {1/self.min_request_interval:.1f} req/sec, {self.max_requests_per_window} per window")
        
        while True:
            try:
                scanner_status = db.get_scanner_status()
                if not scanner_status.get('is_running', True):
                    print("⏸️ Enhanced scanner paused, waiting...")
                    await asyncio.sleep(30)
                    continue
                
                print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Enhanced scan cycle started...")
                
                # Comprehensive scan
                signals = await self.scan_all_pairs()
                
                if signals:
                    print(f"🎯 Generated {len(signals)} high-quality signals")
                    
                    for signal in signals:
                        # Save to database with enhanced data
                        db.add_signal(
                            symbol=signal.symbol,
                            signal_type=signal.signal_type,
                            price=signal.price,
                            change_percent=signal.change_percent,
                            volume=signal.volume,
                            message=f"Strength: {signal.strength:.1f}% | Whale: {'Yes' if signal.whale_activity else 'No'}"
                        )
                        
                        # Send enhanced signal
                        if bot_instance:
                            await self.send_enhanced_signal(bot_instance, signal)
                        
                        print(f"📢 Enhanced {signal.signal_type} signal: {signal.symbol} ({signal.strength:.1f}%)")
                else:
                    print("✅ No high-quality signals detected")
                
                # Update scan timestamp
                db.update_last_scan()
                
                # Wait for next scan (60 seconds)
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"❌ Enhanced scanner error: {e}")
                await asyncio.sleep(60)
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI (Relative Strength Index)"""
        if len(prices) < period + 1:
            return 50.0  # Neutral RSI if not enough data
        
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [delta if delta > 0 else 0 for delta in deltas]
        losses = [-delta if delta < 0 else 0 for delta in deltas]
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    async def check_liquidity_imbalance(self, symbol: str, signal_type: str) -> Tuple[bool, float]:
        """
        NEW REQUIREMENT 1: Liquidity Imbalance Filter
        Check if order book supports the breakout direction
        """
        order_book = await self.get_order_book(symbol, depth=20)
        if not order_book:
            return False, 0.0
        
        try:
            # Get current price for 1% spread calculation
            market_data = await self.get_market_data(symbol)
            if not market_data:
                return False, 0.0
            
            current_price = market_data.price
            spread_threshold = current_price * 0.01  # 1% spread
            
            # Calculate buy-side depth (within 1% above current price)
            buy_depth = 0.0
            for price, size in order_book.bids:
                if current_price - price <= spread_threshold:
                    buy_depth += size
            
            # Calculate sell-side depth (within 1% below current price)
            sell_depth = 0.0
            for price, size in order_book.asks:
                if price - current_price <= spread_threshold:
                    sell_depth += size
            
            # Check imbalance based on signal type
            if signal_type in ['PUMP', 'BREAKOUT_UP']:
                # For LONG signals: buy-side must be >= 3x sell-side
                ratio = buy_depth / sell_depth if sell_depth > 0 else float('inf')
                return ratio >= self.liquidity_ratio_threshold, ratio
            
            elif signal_type in ['DUMP', 'BREAKOUT_DOWN']:
                # For SHORT signals: sell-side must be >= 3x buy-side
                ratio = sell_depth / buy_depth if buy_depth > 0 else float('inf')
                return ratio >= self.liquidity_ratio_threshold, ratio
            
            return False, 0.0
            
        except Exception as e:
            print(f"❌ Error checking liquidity imbalance for {symbol}: {e}")
            return False, 0.0

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> Optional[List[Dict]]:
        """Get recent trades for whale activity detection"""
        await self._rate_limit()
        
        try:
            url = f"{self.base_url}/v5/market/recent-trade"
            params = {
                'category': 'linear',
                'symbol': symbol,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['retCode'] == 0:
                    trades = []
                    for trade in data['result']['list']:
                        trades.append({
                            'price': float(trade['price']),
                            'size': float(trade['size']),
                            'side': trade['side'],
                            'time': int(trade['time']),
                            'value': float(trade['price']) * float(trade['size'])
                        })
                    return trades
            
            self.api_errors = 0
            return None
            
        except Exception as e:
            print(f"❌ Error fetching recent trades for {symbol}: {e}")
            self.api_errors += 1
            return None

    async def detect_whale_activity(self, symbol: str) -> Tuple[bool, WhaleActivity]:
        """
        NEW REQUIREMENT 2: Whale Alert Filter
        Detect large wallet activity (>$15k trades)
        """
        trades = await self.get_recent_trades(symbol, limit=100)
        if not trades:
            return False, WhaleActivity([], 0.0, 0.0, 0.0, False)
        
        try:
            large_trades = []
            total_buy_volume = 0.0
            total_sell_volume = 0.0
            
            # Filter trades from last 5 minutes
            current_time = int(time.time() * 1000)
            five_minutes_ago = current_time - (5 * 60 * 1000)
            
            for trade in trades:
                if trade['time'] >= five_minutes_ago and trade['value'] >= self.whale_threshold:
                    large_trades.append(trade)
                    
                    if trade['side'] == 'Buy':
                        total_buy_volume += trade['value']
                    else:
                        total_sell_volume += trade['value']
            
            net_flow = total_buy_volume - total_sell_volume
            is_bullish = net_flow > 0
            
            whale_activity = WhaleActivity(
                large_trades=large_trades,
                total_buy_volume=total_buy_volume,
                total_sell_volume=total_sell_volume,
                net_flow=net_flow,
                is_bullish=is_bullish
            )
            
            # Consider whale activity significant if there are large trades
            has_whale_activity = len(large_trades) > 0
            
            return has_whale_activity, whale_activity
            
        except Exception as e:
            print(f"❌ Error detecting whale activity for {symbol}: {e}")
            return False, WhaleActivity([], 0.0, 0.0, 0.0, False)

    async def check_rsi_momentum_cap(self, symbol: str, signal_type: str) -> Tuple[bool, float]:
        """
        NEW REQUIREMENT 3: RSI / Momentum Cap
        Prevent entries when price is overbought/oversold
        """
        try:
            # Get 5-minute candles for RSI calculation
            candles = await self.get_kline_data(symbol, interval="5", limit=50)
            if not candles or len(candles) < 15:
                return True, 50.0  # Allow signal if no RSI data
            
            # Extract closing prices
            prices = [candle.close for candle in reversed(candles)]  # Reverse to get chronological order
            
            # Calculate RSI
            rsi = self.calculate_rsi(prices, period=14)
            
            # Apply momentum cap rules
            if signal_type in ['PUMP', 'BREAKOUT_UP']:
                # Block LONG signals if RSI > 75 (overbought)
                return rsi <= self.rsi_overbought, rsi
            
            elif signal_type in ['DUMP', 'BREAKOUT_DOWN']:
                # Block SHORT signals if RSI < 25 (oversold)
                return rsi >= self.rsi_oversold, rsi
            
            return True, rsi
            
        except Exception as e:
            print(f"❌ Error checking RSI momentum cap for {symbol}: {e}")
            return True, 50.0  # Allow signal on error

    async def check_range_break(self, symbol: str) -> Tuple[bool, float]:
        """
        NEW REQUIREMENT: Range Break Detection
        Price closes >1.2% above last high
        """
        try:
            # Get recent candles to find the high
            candles = await self.get_kline_data(symbol, "1", 50)
            if not candles or len(candles) < 10:
                return False, 0.0
            
            current_price = candles[0].close
            
            # Find highest price in last 20 candles (excluding current)
            recent_highs = [c.high for c in candles[1:21]]
            if not recent_highs:
                return False, 0.0
                
            last_high = max(recent_highs)
            
            # Calculate break percentage
            break_percent = ((current_price - last_high) / last_high) * 100
            
            # Check if price closes >1.2% above last high
            range_break_detected = break_percent >= 1.2
            
            if range_break_detected:
                print(f"✅ Range break detected for {symbol}: {break_percent:.2f}% above last high")
            
            return range_break_detected, break_percent
            
        except Exception as e:
            print(f"❌ Error checking range break for {symbol}: {e}")
            return False, 0.0
    
    async def check_volume_divergence(self, symbol: str) -> Tuple[bool, str]:
        """
        NEW REQUIREMENT: Volume Divergence Detection
        Filter out price up + volume down cases
        """
        try:
            # Get recent candles for divergence analysis
            candles = await self.get_kline_data(symbol, "1", 10)
            if not candles or len(candles) < 5:
                return True, "insufficient_data"
            
            # Get recent trades for CVD calculation
            trades = await self.get_recent_trades(symbol, limit=100)
            if not trades:
                return True, "no_trades"
            
            # Calculate price direction (last 3 candles)
            price_changes = []
            for i in range(min(3, len(candles)-1)):
                change = (candles[i].close - candles[i+1].close) / candles[i+1].close
                price_changes.append(change)
            
            avg_price_change = sum(price_changes) / len(price_changes)
            price_direction = "up" if avg_price_change > 0 else "down"
            
            # Calculate CVD (Cumulative Volume Delta)
            buy_volume = 0.0
            sell_volume = 0.0
            
            for trade in trades:
                if trade['side'] == 'Buy':
                    buy_volume += trade['size']
                else:
                    sell_volume += trade['size']
            
            total_volume = buy_volume + sell_volume
            if total_volume == 0:
                return True, "no_volume"
                
            buy_pressure = (buy_volume / total_volume) * 100
            
            # Determine volume direction
            if buy_pressure > 60:
                volume_direction = "bullish"
            elif buy_pressure < 40:
                volume_direction = "bearish"
            else:
                volume_direction = "neutral"
            
            # Check for divergence
            divergence_detected = False
            
            if price_direction == "up" and volume_direction == "bearish":
                divergence_detected = True
                print(f"⚠️ Volume divergence detected for {symbol}: Price UP but Volume BEARISH")
            elif price_direction == "down" and volume_direction == "bullish":
                divergence_detected = True
                print(f"⚠️ Volume divergence detected for {symbol}: Price DOWN but Volume BULLISH")
            
            # Return True if NO divergence (passed), False if divergence detected
            return not divergence_detected, volume_direction
            
        except Exception as e:
            print(f"❌ Error checking volume divergence for {symbol}: {e}")
            return True, "error"
    
    async def check_new_coin_filter(self, symbol: str) -> Tuple[bool, int]:
        """
        NEW REQUIREMENT: New Coin Filter
        Avoid newly listed tokens (optional filter)
        """
        try:
            # This would require additional API endpoint to get listing date
            # For now, we'll use a simplified approach based on 24h volume
            # New coins typically have lower 24h volume or unusual patterns
            
            market_data = await self.get_market_data(symbol)
            if not market_data:
                return True, 999  # Default to pass if no data
            
            # Get historical volume data to check consistency
            candles = await self.get_kline_data(symbol, "D", 30)  # 30 days of daily candles
            if not candles or len(candles) < 7:
                # If less than 7 days of data, likely a new coin
                print(f"⚠️ Possible new coin detected for {symbol}: Limited historical data")
                return False, len(candles)
            
            # Check volume consistency (new coins often have erratic volume)
            volumes = [c.volume for c in candles[:7]]  # Last 7 days
            if not volumes:
                return False, 0
                
            avg_volume = sum(volumes) / len(volumes)
            volume_std = statistics.stdev(volumes) if len(volumes) > 1 else 0
            
            # High volume volatility might indicate new listing
            if avg_volume > 0:
                volume_cv = volume_std / avg_volume  # Coefficient of variation
                if volume_cv > 2.0:  # Very high volume volatility
                    print(f"⚠️ High volume volatility for {symbol}: Possible new coin (CV: {volume_cv:.2f})")
                    return False, len(candles)
            
            # Coin passes new coin filter
            return True, len(candles)
            
        except Exception as e:
            print(f"❌ Error checking new coin filter for {symbol}: {e}")
            return True, 999
    
    async def check_multi_timeframe_trend(self, symbol: str, signal_type: str) -> Tuple[bool, Dict]:
        """
        NEW REQUIREMENT: Multi-timeframe Trend Match
        1m signal must align with 5m EMA trend
        """
        try:
            # Get 1m and 5m candles
            candles_1m = await self.get_kline_data(symbol, "1", 20)
            candles_5m = await self.get_kline_data(symbol, "5", 20)
            
            if not candles_1m or not candles_5m or len(candles_1m) < 10 or len(candles_5m) < 10:
                return True, {"reason": "insufficient_data"}
            
            # Calculate EMAs for 5m timeframe
            prices_5m = [c.close for c in reversed(candles_5m)]
            ema_5_short = self.calculate_ema(prices_5m, 9)  # 9-period EMA
            ema_5_long = self.calculate_ema(prices_5m, 21)   # 21-period EMA
            
            # Determine 5m trend
            if ema_5_short > ema_5_long:
                trend_5m = "bullish"
            elif ema_5_short < ema_5_long:
                trend_5m = "bearish"
            else:
                trend_5m = "neutral"
            
            # Check alignment with 1m signal
            alignment = False
            
            if signal_type in ['PUMP', 'BREAKOUT_UP', 'BREAKOUT_LONG']:
                alignment = trend_5m == "bullish"
                if not alignment:
                    print(f"⚠️ Trend mismatch for {symbol}: 1m LONG signal but 5m trend is {trend_5m}")
            
            elif signal_type in ['DUMP', 'BREAKOUT_DOWN', 'BREAKOUT_SHORT']:
                alignment = trend_5m == "bearish"
                if not alignment:
                    print(f"⚠️ Trend mismatch for {symbol}: 1m SHORT signal but 5m trend is {trend_5m}")
            
            else:
                alignment = True  # Neutral signals always pass
            
            trend_data = {
                "1m_signal": signal_type,
                "5m_trend": trend_5m,
                "ema_5_short": ema_5_short,
                "ema_5_long": ema_5_long,
                "alignment": alignment
            }
            
            return alignment, trend_data
            
        except Exception as e:
            print(f"❌ Error checking multi-timeframe trend for {symbol}: {e}")
            return True, {"error": str(e)}

    async def analyze_signal_with_new_filters(self, symbol: str, signal_type: str, base_strength: float) -> Tuple[bool, float, Dict[str, any]]:
        """
        Apply all new filters and calculate final signal strength
        """
        filter_results = {
            'liquidity_imbalance': {'passed': False, 'ratio': 0.0},
            'whale_activity': {'detected': False, 'is_bullish': False, 'net_flow': 0.0},
            'rsi_momentum': {'passed': True, 'rsi_value': 50.0},
            'range_break': {'passed': False, 'break_percent': 0.0},
            'volume_divergence': {'passed': True, 'direction': 'neutral'},
            'new_coin': {'passed': True, 'age_days': 999},
            'trend_match': {'passed': True, 'alignment': True}
        }
        
        # 1. Check Liquidity Imbalance Filter
        liquidity_passed, liquidity_ratio = await self.check_liquidity_imbalance(symbol, signal_type)
        filter_results['liquidity_imbalance'] = {
            'passed': liquidity_passed,
            'ratio': liquidity_ratio
        }
        
        # 2. Check Whale Activity Filter
        whale_detected, whale_data = await self.detect_whale_activity(symbol)
        filter_results['whale_activity'] = {
            'detected': whale_detected,
            'is_bullish': whale_data.is_bullish,
            'net_flow': whale_data.net_flow,
            'large_trades_count': len(whale_data.large_trades)
        }
        
        # 3. Check RSI Momentum Cap
        rsi_passed, rsi_value = await self.check_rsi_momentum_cap(symbol, signal_type)
        filter_results['rsi_momentum'] = {
            'passed': rsi_passed,
            'rsi_value': rsi_value
        }
        
        # 4. Check Range Break Detection
        range_passed, break_percent = await self.check_range_break(symbol)
        filter_results['range_break'] = {
            'passed': range_passed,
            'break_percent': break_percent
        }
        
        # 5. Check Volume Divergence
        divergence_passed, volume_direction = await self.check_volume_divergence(symbol)
        filter_results['volume_divergence'] = {
            'passed': divergence_passed,
            'direction': volume_direction
        }
        
        # 6. Check New Coin Filter
        new_coin_passed, age_days = await self.check_new_coin_filter(symbol)
        filter_results['new_coin'] = {
            'passed': new_coin_passed,
            'age_days': age_days
        }
        
        # 7. Check Multi-timeframe Trend Match
        trend_passed, trend_data = await self.check_multi_timeframe_trend(symbol, signal_type)
        filter_results['trend_match'] = {
            'passed': trend_passed,
            'alignment': trend_data.get('alignment', True),
            'trend_5m': trend_data.get('5m_trend', 'unknown')
        }
        
        # Calculate final strength with all new filters
        final_strength = base_strength
        
        # Liquidity imbalance adds/removes strength
        if liquidity_passed:
            final_strength += 10  # Bonus for good liquidity support
        else:
            final_strength -= 15  # Penalty for poor liquidity
        
        # Whale activity confirmation
        if whale_detected:
            if signal_type in ['PUMP', 'BREAKOUT_UP'] and whale_data.is_bullish:
                final_strength += 15  # Whale buying supports long signal
            elif signal_type in ['DUMP', 'BREAKOUT_DOWN'] and not whale_data.is_bullish:
                final_strength += 15  # Whale selling supports short signal
            else:
                final_strength -= 10  # Whale activity contradicts signal
        
        # Apply new filter strength adjustments
        if range_passed:
            final_strength += 8  # Bonus for range break confirmation
        
        if not divergence_passed:
            final_strength -= 20  # Major penalty for volume divergence
            print(f"⚠️ Volume divergence penalty for {symbol}: -{volume_direction}")
        
        if not new_coin_passed:
            print(f"🚫 Signal blocked for {symbol}: New coin filter (age: {age_days} days)")
            return False, 0.0, filter_results  # Block new coins entirely
        
        if not trend_passed:
            final_strength -= 12  # Penalty for trend mismatch
            print(f"⚠️ Trend mismatch penalty for {symbol}: 5m trend is {trend_data.get('5m_trend', 'unknown')}")
        
        # RSI momentum cap - hard block (most important)
        if not rsi_passed:
            print(f"🚫 Signal blocked for {symbol}: RSI filter (RSI: {rsi_value:.1f})")
            return False, 0.0, filter_results  # Block signal entirely
        
        # Ensure strength stays within bounds
        final_strength = max(0, min(100, final_strength))
        
        # Enhanced signal validation - must pass multiple criteria
        critical_filters_passed = (
            liquidity_passed and 
            rsi_passed and 
            new_coin_passed and
            divergence_passed
        )
        
        # Signal must pass minimum threshold (70%) and critical filters
        signal_valid = final_strength >= 70 and critical_filters_passed
        
        if not signal_valid:
            reasons = []
            if final_strength < 70:
                reasons.append(f"Low strength ({final_strength:.1f}%)")
            if not liquidity_passed:
                reasons.append("Poor liquidity")
            if not divergence_passed:
                reasons.append("Volume divergence")
            print(f"🚫 Signal rejected for {symbol}: {', '.join(reasons)}")
        
        return signal_valid, final_strength, filter_results

    async def send_enhanced_signal(self, bot_instance, signal: SignalData):
        """Send enhanced signal to all subscribers"""
        try:
            # Get IDs from config
            from config import Config
            admin_id = Config.ADMIN_ID
            special_user = Config.SUBSCRIBER_ID
            channel_id = Config.CHANNEL_ID
            
            # Get all subscribers
            subscribers = db.get_active_subscribers()
            all_recipients = set(subscribers + [admin_id, special_user])
            
            message = self.format_signal_message(signal)
            
            # Send to all recipients
            sent_count = 0
            for recipient in all_recipients:
                try:
                    await bot_instance.send_message(
                        chat_id=recipient,
                        text=message,
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                except Exception as e:
                    print(f"❌ Failed to send enhanced signal to {recipient}: {e}")
            
            # Send to channel
            try:
                await bot_instance.send_message(
                    chat_id=channel_id,
                    text=message,
                    parse_mode='Markdown'
                )
                sent_count += 1
            except Exception as e:
                print(f"❌ Failed to send to channel: {e}")
            
            print(f"📤 Enhanced signal sent to {sent_count} recipients")
            
        except Exception as e:
            print(f"❌ Error sending enhanced signal: {e}")

    async def run_single_scan(self, bot_instance=None):
        """Run a single scan cycle"""
        try:
            # Check if scanner is paused
            scanner_status = db.get_scanner_status()
            is_running = scanner_status.get('is_running', True)
            
            if not is_running:
                print("⏸️ Scanner is paused. Skipping scan cycle.")
                return 0
                
            # Scan all pairs
            signals = await self.scan_all_pairs()
            
            # Process and send signals
            if signals and bot_instance:
                for signal in signals:
                    await self.send_enhanced_signal(bot_instance, signal)
            
            return len(signals)
        except Exception as e:
            print(f"❌ Error in scan cycle: {e}")
            return 0
    
    async def run_enhanced_scanner(self, bot_instance=None):
        """Run the enhanced scanner continuously"""
        print("🚀 Starting Enhanced Bybit Scanner...")
        
        while True:
            try:
                # Check if scanner is paused
                scanner_status = db.get_scanner_status()
                is_running = scanner_status.get('is_running', True)
                
                if not is_running:
                    print("⏸️ Scanner is paused. Waiting for resume...")
                    await asyncio.sleep(5)  # Check every 5 seconds if scanner is resumed
                    continue
                
                # Run a single scan cycle
                signals_count = await self.run_single_scan(bot_instance)
                
                if signals_count > 0:
                    print(f"✅ Scan complete: {signals_count} signals generated")
                else:
                    print("✅ Scan complete: No signals generated")
                
                # Wait before next scan
                print("⏱️ Waiting 60 seconds before next scan...")
                await asyncio.sleep(60)
                
            except Exception as e:
                print(f"❌ Error in scanner loop: {e}")
                await asyncio.sleep(10)  # Wait a bit before retrying

    async def check_candle_body_rule(self, candles: List[CandleData]) -> Tuple[bool, float]:
        """Check if candle body is >60% of total candle size (low wick rejection)"""
        try:
            if not candles:
                return False, 0.0
            
            current_candle = candles[-1]
            
            # Calculate candle metrics
            candle_high = float(current_candle.high)
            candle_low = float(current_candle.low)
            candle_open = float(current_candle.open)
            candle_close = float(current_candle.close)
            
            candle_range = candle_high - candle_low
            candle_body = abs(candle_close - candle_open)
            
            if candle_range == 0:
                return False, 0.0
            
            body_percentage = (candle_body / candle_range) * 100
            
            # Client requirement: Body must be >60% of total size
            passes = body_percentage > 60.0
            
            return passes, body_percentage
            
        except Exception as e:
            print(f"❌ Error checking candle body rule: {e}")
            return False, 0.0

    async def check_buy_pressure_cvd(self, candles: List[CandleData]) -> Tuple[bool, float]:
        """Check Cumulative Volume Delta for buy pressure"""
        try:
            if len(candles) < 5:
                return False, 0.0
            
            # Calculate CVD over last 5 candles
            cvd = 0.0
            
            for candle in candles[-5:]:
                volume = float(candle.volume)
                close_price = float(candle.close)
                open_price = float(candle.open)
                
                # Simple CVD calculation: green candle = positive, red = negative
                if close_price > open_price:
                    cvd += volume  # Buying pressure
                else:
                    cvd -= volume  # Selling pressure
            
            # Normalize CVD as percentage
            total_volume = sum(float(c.volume) for c in candles[-5:])
            cvd_percentage = (cvd / total_volume * 100) if total_volume > 0 else 0.0
            
            # Require positive CVD for buy pressure
            passes = cvd_percentage > 10.0  # At least 10% net buying
            
            return passes, cvd_percentage
            
        except Exception as e:
            print(f"❌ Error checking CVD buy pressure: {e}")
            return False, 0.0

    async def check_ask_liquidity_removal(self, order_book: OrderBookData, current_price: float) -> Tuple[bool, float]:
        """Check if ask-side (sell orders) is thin above breakout price"""
        try:
            if not order_book or not order_book.asks:
                return False, 0.0
            
            asks = order_book.asks
            if not asks:
                return False, 0.0
            
            # Check liquidity within 1% above current price
            price_threshold = current_price * 1.01
            thin_asks = 0.0
            total_asks = 0.0
            
            for price, quantity in asks:
                if price <= price_threshold:
                    thin_asks += quantity
                total_asks += quantity
            
            # Thin ask-side means less resistance for breakouts
            ask_ratio = (thin_asks / total_asks * 100) if total_asks > 0 else 0.0
            
            # Passes if ask-side is thin (< 30% of total liquidity above current price)
            passes = ask_ratio < 30.0
            
            return passes, ask_ratio
            
        except Exception as e:
            print(f"❌ Error checking ask liquidity removal: {e}")
            return False, 0.0

    async def enhanced_comprehensive_scan(self, symbol: str) -> Optional[SignalData]:
        """
        COMPLETE CLIENT REQUIREMENTS SCAN
        
        This function implements ALL client-specified filters:
        - Price Action: Breakout, Range Break (>1.2%), Candle Body (>60%)
        - Volume: Surge (2.5x MA), Divergence Detection, CVD Buy Pressure
        - Order Book: Buy Wall, Ask Removal, 70/30 Imbalance, Spoofing Detection
        - Whale: Smart Wallet Tracking (>$15k trades), Confirmation
        - Technical: Multi-timeframe (1m/5m EMA), Spread (<0.3%), New Coin Filter
        - RSI: Momentum Cap (75/25), 14-period calculation
        - Liquidity: Buy-side ≥3x sell-side for LONG signals
        """
        try:
            # Get all market data
            market_data = await self.get_market_data(symbol)
            if not market_data:
                return None

            candles_1m = await self.get_kline_data(symbol, "1", 50)
            candles_5m = await self.get_kline_data(symbol, "5", 20)
            order_book = await self.get_order_book(symbol)

            if not candles_1m or not candles_5m:
                return None

            # Get scanner settings
            scanner_status = db.get_scanner_status()
            
            # === CLIENT REQUIREMENT FILTERS ===
            filters = {
                'price_action': {},
                'volume': {},
                'order_book': {},
                'whale': {},
                'technical': {}
            }

            # 1. PRICE ACTION FILTERS
            # Breakout Detection
            breakout_data = self.analyze_price_action(candles_1m, market_data)
            filters['price_action']['breakout'] = breakout_data['breakout']

            # Range Break: >1.2% above last high
            range_passed, break_percent = await self.check_range_break(symbol)
            filters['price_action']['range_break'] = range_passed

            # Candle Body Rule: >60% of total size
            body_passed, body_percentage = await self.check_candle_body_rule(candles_1m)
            filters['price_action']['candle_body'] = body_passed

            # 2. VOLUME FILTERS
            volume_data = self.analyze_volume(candles_1m)
            filters['volume']['volume_surge'] = volume_data['volume_surge']

            # Volume Divergence Detection
            divergence_passed, volume_direction = await self.check_volume_divergence(symbol)
            filters['volume']['volume_divergence'] = divergence_passed

            # Buy Pressure (CVD)
            cvd_passed, cvd_percentage = await self.check_buy_pressure_cvd(candles_1m)
            filters['volume']['buy_pressure'] = cvd_passed

            # 3. ORDER BOOK FILTERS
            if order_book:
                ob_data = self.analyze_order_book(order_book, market_data.price)
                filters['order_book']['imbalance'] = ob_data['imbalance']
                filters['order_book']['tight_spread'] = ob_data['tight_spread']
                filters['order_book']['spoofing'] = ob_data.get('spoofing', False)

                # Ask Liquidity Removal
                ask_removal, ask_ratio = await self.check_ask_liquidity_removal(order_book, market_data.price)
                filters['order_book']['ask_removal'] = ask_removal

                # Liquidity Support (3x requirement)
                liquidity_passed, liquidity_ratio = await self.check_liquidity_imbalance(symbol, "LONG")
                filters['order_book']['liquidity_support'] = liquidity_passed
            else:
                filters['order_book'] = {
                    'imbalance': False, 'tight_spread': True, 'spoofing': False,
                    'ask_removal': False, 'liquidity_support': False
                }

            # 4. WHALE ACTIVITY FILTERS
            whale_detected, whale_data = await self.detect_whale_activity(symbol)
            filters['whale']['whale_detected'] = whale_detected
            filters['whale']['whale_bullish'] = whale_data.is_bullish if whale_detected else False

            # 5. TECHNICAL FILTERS
            # Multi-Timeframe Match (1m/5m EMA)
            trend_match, trend_data = await self.check_multi_timeframe_trend(symbol, "LONG")
            filters['technical']['trend_match'] = trend_match

            # RSI Momentum Cap
            rsi_passed, rsi_value = await self.check_rsi_momentum_cap(symbol, "PUMP")
            filters['technical']['rsi_filter'] = rsi_passed

            # New Coin Filter
            new_coin_passed, coin_age = await self.check_new_coin_filter(symbol)
            filters['technical']['new_coin_filter'] = new_coin_passed

            # === SIGNAL DETECTION ===
            signal_triggered = False
            signal_type = ""

            # Check pump threshold
            if market_data.change_24h >= scanner_status.get('pump_threshold', 5.0):
                if filters['volume']['volume_surge']:
                    signal_triggered = True
                    signal_type = "PUMP"

            # Check dump threshold  
            elif market_data.change_24h <= scanner_status.get('dump_threshold', -5.0):
                if filters['volume']['volume_surge']:
                    signal_triggered = True
                    signal_type = "DUMP"

            # Check breakout
            elif filters['price_action']['breakout'] and filters['volume']['volume_surge']:
                signal_triggered = True
                signal_type = "BREAKOUT_LONG"

            if not signal_triggered:
                return None

            # === CALCULATE SIGNAL STRENGTH ===
            strength = self.calculate_signal_strength(filters)

            # Client requirement: Only signals ≥70% strength
            if strength < 70.0:
                return None

            # === CREATE ENHANCED SIGNAL ===
            tp_multipliers_str = scanner_status.get('tp_multipliers', '[1.5, 3.0, 5.0, 7.5]')
            tp_multipliers = json.loads(tp_multipliers_str)
            tp_targets = self.calculate_tp_targets(market_data.price, tp_multipliers)

            # Count passed filters for message
            filters_passed = []
            if filters['price_action']['breakout']: filters_passed.append("✅ Breakout Pattern")
            if filters['volume']['volume_surge']: filters_passed.append("✅ Volume Surge")
            if filters['order_book']['imbalance']: filters_passed.append("✅ Order Book Imbalance")
            if filters['whale']['whale_detected']: filters_passed.append("✅ Whale Activity")
            if filters['price_action']['range_break']: filters_passed.append(f"✅ Range Break ({break_percent:.1f}%)")
            if filters['order_book']['liquidity_support']: filters_passed.append("✅ Liquidity Support (3x)")
            if filters['technical']['trend_match']: filters_passed.append("✅ Trend Alignment")
            if filters['technical']['rsi_filter']: filters_passed.append(f"✅ RSI Filter ({rsi_value:.0f})")
            if filters['volume']['volume_divergence']: filters_passed.append("✅ No Volume Divergence")
            if filters['order_book']['tight_spread']: filters_passed.append("✅ Tight Spread")

            signal = SignalData(
                symbol=symbol,
                signal_type=signal_type,
                price=market_data.price,
                strength=strength,
                tp_targets=tp_targets,
                volume=market_data.volume_24h,
                change_percent=market_data.change_24h,
                filters_passed=filters_passed,
                whale_activity=whale_detected,
                liquidity_imbalance=filters['order_book']['liquidity_support'],
                rsi_value=rsi_value,
                timestamp=datetime.now()
            )

            return signal

        except Exception as e:
            print(f"❌ Error in enhanced comprehensive scan for {symbol}: {e}")
            return None

# Global enhanced scanner instance
enhanced_scanner = EnhancedBybitScanner()

if __name__ == "__main__":
    # Run enhanced scanner standalone
    asyncio.run(enhanced_scanner.run_enhanced_scanner())