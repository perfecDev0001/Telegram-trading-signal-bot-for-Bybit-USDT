#!/usr/bin/env python3
"""
Bybit API Integration Module
Handles all Bybit-specific API calls for USDT Perpetuals
Uses Bybit's public API (no authentication required)
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class BybitKline:
    """Bybit kline/candlestick data"""
    symbol: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float
    
@dataclass
class BybitTicker:
    """Bybit 24h ticker data"""
    symbol: str
    price: float
    price_change_percent: float
    high_24h: float
    low_24h: float
    volume_24h: float
    turnover_24h: float
    
@dataclass
class BybitOrderBook:
    """Bybit order book data"""
    symbol: str
    asks: List[Tuple[float, float]]  # (price, size)
    bids: List[Tuple[float, float]]  # (price, size)
    timestamp: int

class BybitAPI:
    """Bybit Public API client for USDT Perpetuals"""
    
    def __init__(self):
        # Use main API - no fallback to testnet which causes issues
        self.base_url = "https://api.bybit.com"
        self.session = None
        self.last_request_time = 0
        self.rate_limit_delay = 0.2  # 200ms between requests to avoid rate limiting
        self.request_count = 0
        self.max_retries = 3
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)
        
        self.last_request_time = time.time()
    
    async def _make_request(self, endpoint: str, params: Optional[Dict] = None, retry_count: int = 0) -> Optional[Dict]:
        """Make HTTP request to Bybit API with retry logic"""
        await self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        
        # Add headers for public API access - rotate User-Agent to avoid blocking
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        
        headers = {
            'User-Agent': user_agents[self.request_count % len(user_agents)],
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        }
        
        self.request_count += 1
        
        try:
            async with self.session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('retCode') == 0:
                        return data.get('result')
                    else:
                        logger.error(f"Bybit API error: {data.get('retMsg', 'Unknown error')} (Code: {data.get('retCode')})")
                        return None
                elif response.status == 403:
                    logger.warning(f"HTTP 403 for {url} - Rate limited, waiting...")
                    if retry_count < self.max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        await asyncio.sleep(wait_time)
                        return await self._make_request(endpoint, params, retry_count + 1)
                    return None
                elif response.status == 429:
                    logger.warning(f"HTTP 429 Rate Limited for {url}")
                    if retry_count < self.max_retries:
                        wait_time = 3 + (retry_count * 2)  # Longer wait for rate limit
                        await asyncio.sleep(wait_time)
                        return await self._make_request(endpoint, params, retry_count + 1)
                    return None
                else:
                    logger.error(f"HTTP {response.status} for {url}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout for {url}")
            if retry_count < self.max_retries:
                await asyncio.sleep(1)
                return await self._make_request(endpoint, params, retry_count + 1)
            return None
        except Exception as e:
            logger.error(f"Request error for {url}: {e}")
            return None
    
    async def get_usdt_perpetuals(self) -> List[str]:
        """Get all USDT Perpetual trading pairs"""
        endpoint = "/v5/market/instruments-info"
        params = {
            'category': 'linear'
        }
        
        data = await self._make_request(endpoint, params)
        
        if data and 'list' in data:
            # Filter only USDT pairs
            usdt_pairs = [
                item['symbol'] for item in data['list'] 
                if item['symbol'].endswith('USDT') and item.get('status') == 'Trading'
            ]
            return usdt_pairs
        
        # Fallback: return popular USDT pairs for testing
        logger.warning("Using fallback USDT pairs due to API unavailability")
        return [
            'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'XRPUSDT',
            'SOLUSDT', 'DOGEUSDT', 'AVAXUSDT', 'DOTUSDT', 'MATICUSDT'
        ]
    
    async def get_kline_data(self, symbol: str, interval: str = '5', limit: int = 200) -> List[BybitKline]:
        """Get kline/candlestick data for a symbol"""
        endpoint = "/v5/market/kline"
        params = {
            'category': 'linear',
            'symbol': symbol,
            'interval': interval,  # 5 = 5 minutes
            'limit': limit
        }
        
        data = await self._make_request(endpoint, params)
        
        if data and 'list' in data:
            klines = []
            for item in data['list']:
                try:
                    kline = BybitKline(
                        symbol=symbol,
                        open_time=int(item[0]),
                        open=float(item[1]),
                        high=float(item[2]),
                        low=float(item[3]),
                        close=float(item[4]),
                        volume=float(item[5]),
                        turnover=float(item[6])
                    )
                    klines.append(kline)
                except (ValueError, IndexError) as e:
                    logger.error(f"Error parsing kline data for {symbol}: {e}")
                    continue
            
            # Sort by timestamp (most recent first)
            klines.sort(key=lambda x: x.open_time, reverse=True)
            return klines
        
        return []
    
    async def get_ticker_24h(self, symbol: str) -> Optional[BybitTicker]:
        """Get 24h ticker data for a symbol"""
        endpoint = "/v5/market/tickers"
        params = {
            'category': 'linear',
            'symbol': symbol
        }
        
        data = await self._make_request(endpoint, params)
        
        if data and 'list' in data and len(data['list']) > 0:
            item = data['list'][0]
            try:
                return BybitTicker(
                    symbol=symbol,
                    price=float(item['lastPrice']),
                    price_change_percent=float(item['price24hPcnt']) * 100,
                    high_24h=float(item['highPrice24h']),
                    low_24h=float(item['lowPrice24h']),
                    volume_24h=float(item['volume24h']),
                    turnover_24h=float(item['turnover24h'])
                )
            except (ValueError, KeyError) as e:
                logger.error(f"Error parsing ticker data for {symbol}: {e}")
                return None
        
        return None
    
    async def get_order_book(self, symbol: str, limit: int = 25) -> Optional[BybitOrderBook]:
        """Get order book data for a symbol"""
        endpoint = "/v5/market/orderbook"
        params = {
            'category': 'linear',
            'symbol': symbol,
            'limit': limit
        }
        
        data = await self._make_request(endpoint, params)
        
        if data:
            try:
                asks = [(float(ask[0]), float(ask[1])) for ask in data.get('a', [])]
                bids = [(float(bid[0]), float(bid[1])) for bid in data.get('b', [])]
                
                return BybitOrderBook(
                    symbol=symbol,
                    asks=asks,
                    bids=bids,
                    timestamp=int(data.get('ts', 0))
                )
            except (ValueError, KeyError) as e:
                logger.error(f"Error parsing order book data for {symbol}: {e}")
                return None
        
        return None
    
    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """Get recent trades for a symbol"""
        endpoint = "/v5/market/recent-trade"
        params = {
            'category': 'linear',
            'symbol': symbol,
            'limit': limit
        }
        
        data = await self._make_request(endpoint, params)
        
        if data and 'list' in data:
            trades = []
            for trade in data['list']:
                try:
                    trades.append({
                        'symbol': symbol,
                        'price': float(trade['price']),
                        'size': float(trade['size']),
                        'side': trade['side'],
                        'timestamp': int(trade['time'])
                    })
                except (ValueError, KeyError) as e:
                    logger.error(f"Error parsing trade data for {symbol}: {e}")
                    continue
            
            return trades
        
        return []
    
    async def get_server_time(self) -> Optional[int]:
        """Get Bybit server time"""
        endpoint = "/v5/market/time"
        data = await self._make_request(endpoint)
        
        if data and 'timeSecond' in data:
            return int(data['timeSecond']) * 1000  # Convert to milliseconds
        
        return None
    
    async def analyze_market_structure(self, symbol: str) -> Dict:
        """Analyze market structure for a symbol"""
        # Get 5-minute candles (last 200 candles = ~16 hours)
        klines = await self.get_kline_data(symbol, '5', 200)
        
        # Get order book
        order_book = await self.get_order_book(symbol)
        
        # Get recent trades
        trades = await self.get_recent_trades(symbol)
        
        # Get 24h ticker
        ticker = await self.get_ticker_24h(symbol)
        
        if not klines or not ticker:
            return {}
        
        # Calculate technical indicators
        closes = [k.close for k in klines]
        volumes = [k.volume for k in klines]
        
        # RSI calculation (simplified)
        rsi = self._calculate_rsi(closes)
        
        # Volume analysis
        avg_volume = sum(volumes[-20:]) / 20  # 20-period average
        current_volume = volumes[0] if volumes else 0
        volume_surge = (current_volume / avg_volume) if avg_volume > 0 else 0
        
        # Price analysis
        recent_high = max([k.high for k in klines[:20]])  # Last 20 candles high
        recent_low = min([k.low for k in klines[:20]])    # Last 20 candles low
        current_price = klines[0].close if klines else 0
        
        # Order book analysis
        order_book_imbalance = 0
        spread_percent = 0
        
        if order_book and order_book.bids and order_book.asks:
            bid_volume = sum([bid[1] for bid in order_book.bids[:10]])  # Top 10 bids
            ask_volume = sum([ask[1] for ask in order_book.asks[:10]])  # Top 10 asks
            
            total_volume = bid_volume + ask_volume
            if total_volume > 0:
                order_book_imbalance = (bid_volume - ask_volume) / total_volume
            
            # Calculate spread
            best_bid = order_book.bids[0][0] if order_book.bids else 0
            best_ask = order_book.asks[0][0] if order_book.asks else 0
            
            if best_bid > 0 and best_ask > 0:
                spread_percent = ((best_ask - best_bid) / best_bid) * 100
        
        return {
            'symbol': symbol,
            'current_price': current_price,
            'price_change_24h': ticker.price_change_percent,
            'volume_24h': ticker.volume_24h,
            'recent_high': recent_high,
            'recent_low': recent_low,
            'rsi': rsi,
            'volume_surge': volume_surge,
            'order_book_imbalance': order_book_imbalance,
            'spread_percent': spread_percent,
            'klines_count': len(klines),
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> float:
        """Calculate RSI indicator"""
        if len(closes) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(closes)):
            change = closes[i-1] - closes[i]  # Note: reversed because klines are newest first
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < period:
            return 50.0
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)

# Global instance
bybit_api = BybitAPI()