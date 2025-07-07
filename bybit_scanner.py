#!/usr/bin/env python3
"""
Bybit USDT Perpetuals Scanner
Specialized scanner for Bybit USDT Perpetuals with 5-minute candle analysis
Implements all required filters and signal detection logic
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

from bybit_api import bybit_api, BybitKline, BybitTicker, BybitOrderBook
from database import db
from config import Config

logger = logging.getLogger(__name__)

@dataclass
class BybitSignal:
    """Bybit trading signal"""
    symbol: str
    signal_type: str  # 'LONG' or 'SHORT'
    entry_price: float
    strength: float
    tp_targets: List[float]
    filters_passed: List[str]
    volume_surge: float
    price_change: float
    rsi_value: float
    order_book_imbalance: float
    spread_percent: float
    whale_activity: bool
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for database storage"""
        return {
            'symbol': self.symbol,
            'signal_type': self.signal_type,
            'entry_price': self.entry_price,
            'strength': self.strength,
            'tp_targets': json.dumps(self.tp_targets),
            'filters_passed': json.dumps(self.filters_passed),
            'volume_surge': self.volume_surge,
            'price_change': self.price_change,
            'rsi_value': self.rsi_value,
            'order_book_imbalance': self.order_book_imbalance,
            'spread_percent': self.spread_percent,
            'whale_activity': self.whale_activity,
            'timestamp': self.timestamp.isoformat()
        }

class BybitScanner:
    """Bybit USDT Perpetuals scanner with comprehensive signal detection"""
    
    def __init__(self):
        self.name = "Bybit USDT Perpetuals Scanner"
        self.last_scan_time = None
        self.scan_count = 0
        self.signals_sent = 0
        self.monitored_pairs = []
        self.price_history = {}  # Store price history for each symbol
        
    async def initialize(self):
        """Initialize scanner with latest pairs"""
        try:
            async with bybit_api:
                # Get all USDT perpetual pairs
                all_pairs = await bybit_api.get_usdt_perpetuals()
                
                # Get monitored pairs from database
                settings = db.get_settings()
                monitored_pairs = settings.get('monitored_pairs', Config.DEFAULT_PAIRS)
                
                # Filter to only include pairs that exist on Bybit
                self.monitored_pairs = [pair for pair in monitored_pairs if pair in all_pairs]
                
                logger.info(f"✅ Initialized with {len(self.monitored_pairs)} USDT perpetual pairs")
                logger.info(f"📊 Pairs: {', '.join(self.monitored_pairs[:10])}{'...' if len(self.monitored_pairs) > 10 else ''}")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Scanner initialization failed: {e}")
            return False
    
    async def scan_markets(self) -> List[BybitSignal]:
        """Scan all monitored pairs for signals"""
        logger.info(f"🔍 Scanning {len(self.monitored_pairs)} Bybit USDT Perpetual pairs...")
        
        signals = []
        scanned_count = 0
        
        async with bybit_api:
            for symbol in self.monitored_pairs:
                try:
                    signal = await self._analyze_symbol(symbol)
                    if signal:
                        signals.append(signal)
                        logger.info(f"✅ Signal detected: {symbol} {signal.signal_type} ({signal.strength:.1f}%)")
                    
                    scanned_count += 1
                    
                    # Progress update every 10 pairs
                    if scanned_count % 10 == 0:
                        logger.info(f"📊 Scanned {scanned_count}/{len(self.monitored_pairs)} pairs...")
                
                except Exception as e:
                    logger.error(f"❌ Error scanning {symbol}: {e}")
                    continue
        
        self.last_scan_time = datetime.now()
        self.scan_count += 1
        
        logger.info(f"🎯 Scan complete: {len(signals)} signals detected from {scanned_count} pairs")
        
        return signals
    
    async def _analyze_symbol(self, symbol: str) -> Optional[BybitSignal]:
        """Analyze a single symbol for trading signals"""
        try:
            # Get market data
            market_data = await bybit_api.analyze_market_structure(symbol)
            
            if not market_data:
                return None
            
            # Get 5-minute candles for detailed analysis
            klines = await bybit_api.get_kline_data(symbol, '5', 50)  # Last 50 candles
            
            if len(klines) < 20:  # Need at least 20 candles for analysis
                return None
            
            # Update price history
            self._update_price_history(symbol, klines)
            
            # Apply all filters
            filters_passed = []
            strength_score = 70.0  # Base score
            
            current_candle = klines[0]  # Most recent candle
            prev_candles = klines[1:21]  # Previous 20 candles
            
            # 1. Price Action Filters
            breakout_detected = await self._check_breakout_pattern(symbol, current_candle, prev_candles)
            if breakout_detected:
                filters_passed.append("Breakout Pattern")
                strength_score += 15
            
            range_break = await self._check_range_break(symbol, current_candle, prev_candles)
            if range_break:
                filters_passed.append("Range Break (>1.2%)")
                strength_score += 10
            
            valid_candle = await self._check_valid_candle(current_candle)
            if valid_candle:
                filters_passed.append("Valid Candle Body")
                strength_score += 5
            
            # 2. Volume Filters
            volume_surge = await self._check_volume_surge(symbol, klines)
            if volume_surge:
                filters_passed.append("Volume Surge")
                strength_score += 15
            
            volume_divergence = await self._check_volume_divergence(klines)
            if volume_divergence:
                filters_passed.append("No Volume Divergence")
                strength_score += 10
            
            # 3. Order Book Filters
            order_book_imbalance = market_data.get('order_book_imbalance', 0)
            if abs(order_book_imbalance) > 0.4:  # 70/30 ratio
                filters_passed.append("Order Book Imbalance")
                strength_score += 20
            
            # 4. Technical Filters
            rsi_value = market_data.get('rsi', 50)
            spread_percent = market_data.get('spread_percent', 0)
            
            if spread_percent < Config.SPREAD_THRESHOLD:
                filters_passed.append("Tight Spread")
                strength_score += 10
            
            # 5. Trend Alignment
            trend_alignment = await self._check_trend_alignment(klines)
            if trend_alignment:
                filters_passed.append("Trend Alignment")
                strength_score += 10
            
            # 6. Whale Activity (simplified - based on large volume)
            whale_activity = await self._check_whale_activity(symbol, klines)
            if whale_activity:
                filters_passed.append("Whale Activity")
                strength_score += 20
            
            # Determine signal type
            signal_type = None
            
            # LONG signal conditions
            if (breakout_detected and 
                order_book_imbalance > 0.2 and 
                current_candle.close > current_candle.open and
                rsi_value < Config.RSI_OVERBOUGHT):
                signal_type = "LONG"
            
            # SHORT signal conditions
            elif (breakout_detected and 
                  order_book_imbalance < -0.2 and 
                  current_candle.close < current_candle.open and
                  rsi_value > Config.RSI_OVERSOLD):
                signal_type = "SHORT"
            
            # Check minimum requirements
            if (signal_type and 
                len(filters_passed) >= 5 and  # At least 5 filters must pass
                strength_score >= Config.SIGNAL_STRENGTH_THRESHOLD):
                
                # Calculate TP targets
                tp_targets = self._calculate_tp_targets(current_candle.close, signal_type)
                
                signal = BybitSignal(
                    symbol=symbol,
                    signal_type=signal_type,
                    entry_price=current_candle.close,
                    strength=min(strength_score, 100.0),
                    tp_targets=tp_targets,
                    filters_passed=filters_passed,
                    volume_surge=market_data.get('volume_surge', 0),
                    price_change=market_data.get('price_change_24h', 0),
                    rsi_value=rsi_value,
                    order_book_imbalance=order_book_imbalance,
                    spread_percent=spread_percent,
                    whale_activity=whale_activity,
                    timestamp=datetime.now()
                )
                
                return signal
        
        except Exception as e:
            logger.error(f"❌ Error analyzing {symbol}: {e}")
            return None
        
        return None
    
    def _update_price_history(self, symbol: str, klines: List[BybitKline]):
        """Update price history for technical analysis"""
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        # Add new candles to history
        for kline in klines:
            # Check if this candle is already in history
            if not any(h['timestamp'] == kline.open_time for h in self.price_history[symbol]):
                self.price_history[symbol].append({
                    'timestamp': kline.open_time,
                    'open': kline.open,
                    'high': kline.high,
                    'low': kline.low,
                    'close': kline.close,
                    'volume': kline.volume
                })
        
        # Sort by timestamp and keep only last 200 candles
        self.price_history[symbol].sort(key=lambda x: x['timestamp'], reverse=True)
        self.price_history[symbol] = self.price_history[symbol][:200]
    
    async def _check_breakout_pattern(self, symbol: str, current: BybitKline, prev_candles: List[BybitKline]) -> bool:
        """Check for breakout pattern"""
        if not prev_candles:
            return False
        
        # Calculate resistance level (highest high of last 20 candles)
        resistance = max(candle.high for candle in prev_candles)
        
        # Check if current candle closes above resistance
        return current.close > resistance
    
    async def _check_range_break(self, symbol: str, current: BybitKline, prev_candles: List[BybitKline]) -> bool:
        """Check for range break >1.2%"""
        if not prev_candles:
            return False
        
        # Get the highest high from previous candles
        last_high = max(candle.high for candle in prev_candles)
        
        # Check if current close is >1.2% above last high
        if last_high > 0:
            break_percentage = ((current.close - last_high) / last_high) * 100
            return break_percentage > Config.RANGE_BREAK_THRESHOLD
        
        return False
    
    async def _check_valid_candle(self, candle: BybitKline) -> bool:
        """Check if candle body is >60% of total size"""
        total_size = candle.high - candle.low
        body_size = abs(candle.close - candle.open)
        
        if total_size > 0:
            body_ratio = body_size / total_size
            return body_ratio > 0.6
        
        return False
    
    async def _check_volume_surge(self, symbol: str, klines: List[BybitKline]) -> bool:
        """Check for volume surge (current > 2.5x MA)"""
        if len(klines) < 6:
            return False
        
        current_volume = klines[0].volume
        prev_volumes = [k.volume for k in klines[1:6]]  # Previous 5 candles
        
        avg_volume = sum(prev_volumes) / len(prev_volumes)
        
        if avg_volume > 0:
            return current_volume > (avg_volume * 2.5)
        
        return False
    
    async def _check_volume_divergence(self, klines: List[BybitKline]) -> bool:
        """Check for volume divergence (price up but volume down)"""
        if len(klines) < 3:
            return True  # Pass if not enough data
        
        current = klines[0]
        prev = klines[1]
        
        price_up = current.close > prev.close
        volume_down = current.volume < prev.volume
        
        # Return True if no divergence (good signal)
        return not (price_up and volume_down)
    
    async def _check_trend_alignment(self, klines: List[BybitKline]) -> bool:
        """Check if 1m signal aligns with 5m EMA trend"""
        if len(klines) < 20:
            return False
        
        # Calculate simple EMA (20 period)
        closes = [k.close for k in klines]
        ema = self._calculate_ema(closes, 20)
        
        # Check if current price is above EMA (bullish trend)
        return closes[0] > ema
    
    async def _check_whale_activity(self, symbol: str, klines: List[BybitKline]) -> bool:
        """Check for whale activity (large volume spikes)"""
        if len(klines) < 10:
            return False
        
        current_volume = klines[0].volume
        avg_volume = sum(k.volume for k in klines[1:11]) / 10
        
        # Consider whale activity if volume is 5x average
        return current_volume > (avg_volume * 5.0)
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return sum(prices) / len(prices)
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[-period:]) / period  # Start with SMA
        
        for price in prices[-period+1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def _calculate_tp_targets(self, entry_price: float, signal_type: str) -> List[float]:
        """Calculate take profit targets"""
        settings = db.get_settings()
        tp_multipliers = settings.get('tp_multipliers', [1.5, 3.0, 5.0, 7.5])
        
        targets = []
        for multiplier in tp_multipliers:
            if signal_type == "LONG":
                tp_price = entry_price * (1 + multiplier / 100)
            else:  # SHORT
                tp_price = entry_price * (1 - multiplier / 100)
            
            targets.append(round(tp_price, 6))
        
        return targets
    
    def get_status(self) -> Dict:
        """Get scanner status"""
        return {
            'name': self.name,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'scan_count': self.scan_count,
            'signals_sent': self.signals_sent,
            'monitored_pairs': len(self.monitored_pairs),
            'pairs_list': self.monitored_pairs[:10],  # Show first 10 pairs
            'is_active': True
        }
    
    async def get_live_data(self, symbol: str) -> Dict:
        """Get live market data for a specific symbol"""
        try:
            async with bybit_api:
                market_data = await bybit_api.analyze_market_structure(symbol)
                return market_data
        except Exception as e:
            logger.error(f"❌ Error getting live data for {symbol}: {e}")
            return {}
    
    async def get_top_movers(self, limit: int = 10) -> List[Dict]:
        """Get top price movers"""
        try:
            top_movers = []
            async with bybit_api:
                for symbol in self.monitored_pairs[:20]:  # Check first 20 pairs
                    try:
                        ticker = await bybit_api.get_ticker_24h(symbol)
                        if ticker:
                            top_movers.append({
                                'symbol': symbol,
                                'price': ticker.price,
                                'change_24h': ticker.price_change_percent,
                                'volume_24h': ticker.volume_24h
                            })
                    except Exception as e:
                        continue
            
            # Sort by price change (descending)
            top_movers.sort(key=lambda x: abs(x['change_24h']), reverse=True)
            
            return top_movers[:limit]
            
        except Exception as e:
            logger.error(f"❌ Error getting top movers: {e}")
            return []

# Global instance
bybit_scanner = BybitScanner()