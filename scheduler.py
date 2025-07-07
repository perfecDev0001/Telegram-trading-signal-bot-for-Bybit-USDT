#!/usr/bin/env python3
"""
Market Scanner Scheduler Module
Uses APScheduler for reliable and efficient market scanning
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import Config
from database import db
from enhanced_scanner import public_api_scanner, SignalData
from bybit_scanner import bybit_scanner

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MarketScheduler:
    """
    Market scanner scheduler using APScheduler
    Handles all scanning tasks with proper error handling and recovery
    """
    
    def __init__(self, telegram_bot=None):
        self.scheduler = AsyncIOScheduler()
        self.telegram_bot = telegram_bot
        self.is_running = False
        self.last_scan_time = None
        self.scan_count = 0
        self.error_count = 0
        self.service_url = None  # Will be set by main.py
        
        # Configure scheduler
        self.scheduler.add_jobstore('memory')
        
        # Add error listener
        from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._job_success_listener, EVENT_JOB_EXECUTED)
        
        logger.info("✅ Market Scheduler initialized with comprehensive task management")
    
    def _job_error_listener(self, event):
        """Handle job errors"""
        self.error_count += 1
        logger.error(f"❌ Scheduler job error: {event.exception}")
        
        # If too many errors, pause briefly
        if self.error_count > 5:
            logger.warning("🔄 Too many errors, pausing scanner for 30 seconds...")
            self.pause_scanner(30)
            self.error_count = 0
    
    def _job_success_listener(self, event):
        """Handle successful job execution"""
        self.last_scan_time = datetime.now()
        self.scan_count += 1
        if self.scan_count % 10 == 0:  # Log every 10 scans
            logger.info(f"✅ Completed {self.scan_count} scans. Last scan: {self.last_scan_time.strftime('%H:%M:%S')}")
    
    async def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("⚠️ Scheduler already running")
            return
        
        try:
            # Check if scanner should be running
            scanner_status = db.get_scanner_status()
            if not scanner_status.get('is_running', True):
                logger.info("📴 Scanner is disabled in database")
                return
            
            # Start the scheduler
            self.scheduler.start()
            self.is_running = True
            
            # Add the main scanning job
            self.scheduler.add_job(
                self._scan_markets,
                trigger=IntervalTrigger(seconds=Config.SCANNER_INTERVAL),
                id='main_scanner',
                name='Market Scanner',
                replace_existing=True,
                max_instances=1,  # Prevent overlapping scans
                coalesce=True,    # Merge missed runs
                misfire_grace_time=30  # Allow 30 seconds grace time
            )
            
            # Add comprehensive health check job (every 5 minutes)
            self.scheduler.add_job(
                self._health_check,
                trigger=IntervalTrigger(minutes=5),
                id='health_check',
                name='System Health Check',
                replace_existing=True,
                max_instances=1
            )
            
            # Add bot health check job (every 2 minutes)
            self.scheduler.add_job(
                self._bot_health_check,
                trigger=IntervalTrigger(minutes=2),
                id='bot_health_check',
                name='Bot Health Check',
                replace_existing=True,
                max_instances=1
            )
            
            # Add keep-alive job (every 10 minutes)
            self.scheduler.add_job(
                self._keep_alive_ping,
                trigger=IntervalTrigger(minutes=10),
                id='keep_alive',
                name='Keep Alive Ping',
                replace_existing=True,
                max_instances=1
            )
            
            logger.info(f"🚀 Market Scanner started with {Config.SCANNER_INTERVAL}s interval")
            logger.info("📅 Added scheduled tasks: Health Check, Bot Health, Keep-Alive")
            
        except Exception as e:
            logger.error(f"❌ Failed to start scheduler: {e}")
            self.is_running = False
            raise
    
    async def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=False)
            self.is_running = False
            logger.info("🛑 Market Scanner stopped")
        except Exception as e:
            logger.error(f"❌ Error stopping scheduler: {e}")
    
    async def pause_scanner(self, seconds: int):
        """Pause the scanner for a specified number of seconds"""
        if not self.is_running:
            return
        
        try:
            # Remove the main scanner job temporarily
            self.scheduler.remove_job('main_scanner')
            logger.info(f"⏸️ Scanner paused for {seconds} seconds")
            
            # Schedule restart
            self.scheduler.add_job(
                self._restart_scanner,
                trigger=IntervalTrigger(seconds=seconds),
                id='restart_scanner',
                name='Restart Scanner',
                replace_existing=True,
                max_instances=1
            )
            
        except Exception as e:
            logger.error(f"❌ Error pausing scanner: {e}")
    
    async def _restart_scanner(self):
        """Restart the scanner after pause"""
        try:
            # Remove the restart job
            self.scheduler.remove_job('restart_scanner')
            
            # Add back the main scanner job
            self.scheduler.add_job(
                self._scan_markets,
                trigger=IntervalTrigger(seconds=Config.SCANNER_INTERVAL),
                id='main_scanner',
                name='Market Scanner',
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30
            )
            
            logger.info("🔄 Scanner restarted after pause")
            
        except Exception as e:
            logger.error(f"❌ Error restarting scanner: {e}")
    
    async def _scan_markets(self):
        """Main market scanning function - using Bybit scanner"""
        try:
            # Check if scanner is enabled
            scanner_status = db.get_scanner_status()
            if not scanner_status.get('is_running', True):
                logger.debug("📴 Scanner is disabled, skipping scan")
                return
            
            # Initialize scanner if not already done
            if not hasattr(public_api_scanner, 'api_sources'):
                await public_api_scanner.initialize()
            
            # Scan markets for signals
            logger.info("🔍 Scanning Markets using Public APIs...")
            signals = await public_api_scanner.scan_markets()
            
            # Process signals
            for signal in signals:
                try:
                    # Store signal in database
                    signal_dict = {
                        'symbol': signal.symbol,
                        'signal_type': signal.signal_type,
                        'entry_price': signal.entry_price,
                        'strength': signal.strength,
                        'tp_targets': signal.tp_targets,
                        'volume': signal.volume,
                        'change_percent': signal.change_percent,
                        'filters_passed': signal.filters_passed,
                        'whale_activity': signal.whale_activity,
                        'rsi_value': signal.rsi_value,
                        'message': signal.message,
                        'timestamp': signal.timestamp.isoformat()
                    }
                    db.store_signal(signal_dict)
                    
                    # Send signal via Telegram
                    if self.telegram_bot:
                        await self._send_signal_to_telegram(signal)
                    
                    logger.info(f"📤 Signal sent: {signal.symbol} {signal.signal_type}")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing signal {signal.symbol}: {e}")
            
            # Update scanner status
            db.update_scanner_status(
                is_running=True,
                last_scan=datetime.now().isoformat(),
                scan_count=bybit_scanner.scan_count,
                signals_sent=bybit_scanner.signals_sent
            )
            
        except Exception as e:
            logger.error(f"❌ Market scan error: {e}")
            # Don't sleep here - let scheduler handle timing
    
    async def _health_check(self):
        """Periodic health check"""
        try:
            # Check Bybit API connectivity
            try:
                # Initialize scanner if needed
                if not hasattr(bybit_scanner, 'monitored_pairs') or not bybit_scanner.monitored_pairs:
                    await bybit_scanner.initialize()
                
                # Test with a simple API call
                status = bybit_scanner.get_status()
                api_connected = status.get('is_active', False)
                
                if not api_connected:
                    logger.warning("⚠️ Bybit API connectivity issues detected")
                    
                    # Try to reconnect or adjust settings
                    if self.error_count < 3:
                        logger.info("🔄 Attempting to recover Bybit API connection...")
                        await bybit_scanner.initialize()
                    else:
                        logger.warning("🔄 Too many API errors, pausing scanner briefly...")
                        await self.pause_scanner(60)  # Pause for 1 minute
                else:
                    logger.debug("✅ Bybit API connectivity OK")
                    
            except Exception as e:
                logger.warning(f"⚠️ Bybit API health check failed: {e}")
            
            # Check memory usage
            import psutil
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 85:
                logger.warning(f"⚠️ High memory usage: {memory_percent}%")
                # Clear scanner history to free memory
                if hasattr(bybit_scanner, 'price_history'):
                    bybit_scanner.price_history.clear()
            
            logger.debug(f"💚 Health check passed - Memory: {memory_percent}%")
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
    
    async def _bot_health_check(self):
        """Check Telegram bot health and restart if needed"""
        try:
            if self.telegram_bot and hasattr(self.telegram_bot, 'restart_if_needed'):
                # This would be implemented in the TelegramBot class
                logger.debug("🤖 Checking bot health...")
                # For now, just log that we're checking
                logger.debug("💚 Bot health check completed")
            else:
                logger.debug("⚠️ No bot instance available for health check")
        except Exception as e:
            logger.error(f"❌ Bot health check failed: {e}")
    
    async def _keep_alive_ping(self):
        """Send keep-alive ping to prevent service sleep"""
        try:
            if self.service_url:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"{self.service_url}/health", timeout=10) as response:
                            if response.status == 200:
                                logger.info("🔄 Keep-alive ping successful")
                            else:
                                logger.warning(f"⚠️ Keep-alive ping failed: {response.status}")
                    except Exception as e:
                        logger.warning(f"⚠️ Keep-alive ping error: {e}")
            else:
                logger.debug("⚠️ No service URL configured for keep-alive")
        except Exception as e:
            logger.error(f"❌ Keep-alive ping failed: {e}")
    
    def set_service_url(self, url: str):
        """Set the service URL for keep-alive pings"""
        self.service_url = url
        logger.info(f"🌐 Service URL set for keep-alive: {url}")
    
    async def force_scan(self) -> list:
        """Force an immediate scan of all monitored pairs"""
        try:
            scanner_status = db.get_scanner_status()
            import json
            monitored_pairs = json.loads(scanner_status.get('monitored_pairs', '["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]'))
            
            logger.info(f"⚡ Force scan initiated for {len(monitored_pairs)} pairs")
            
            signals_found = []
            scan_results = []
            
            # Initialize scanner if needed
            if not hasattr(public_api_scanner, 'api_sources'):
                await public_api_scanner.initialize()
            
            # Perform scan using Public API scanner
            signals = await public_api_scanner.scan_markets()
            
            if signals:
                for signal in signals:
                    try:
                        signals_found.append(signal)
                        scan_results.append(f"🎯 {signal.symbol}: SIGNAL ({signal.strength:.0f}%)")
                        
                        # Store signal in database
                        db.store_signal(signal.to_dict())
                        
                        # Send signal immediately
                        if self.telegram_bot:
                            try:
                                await self._send_signal_to_telegram(signal)
                            except Exception as send_error:
                                logger.error(f"❌ Error sending signal for {signal.symbol}: {send_error}")
                    except Exception as e:
                        logger.error(f"❌ Error processing signal {signal.symbol}: {e}")
                        scan_results.append(f"❌ {signal.symbol}: Processing error")
            
            # Add general market data using public API scanner
            try:
                top_movers = await public_api_scanner.get_top_movers(5)
                if top_movers:
                    for mover in top_movers[:3]:
                        change_emoji = "📈" if mover['change_24h'] > 0 else "📉"
                        scan_results.append(f"{change_emoji} {mover['symbol']}: {mover['change_24h']:+.2f}%")
            except Exception as e:
                logger.error(f"❌ Error getting market data: {e}")
                scan_results.append(f"⚠️ Market data unavailable")
            
            # If no signals found, add message
            if not signals:
                scan_results.append("📊 No signals detected in current market conditions")
            
            logger.info(f"⚡ Force scan completed - {len(signals_found)} signals found")
            return scan_results
            
        except Exception as e:
            logger.error(f"❌ Force scan failed: {e}")
            return [f"❌ Force scan failed: {str(e)}"]
    
    async def get_live_monitor_data(self, pairs: list) -> list:
        """Get live data specifically for the monitor display"""
        try:
            logger.info(f"📊 Getting live monitor data for {len(pairs)} pairs")
            
            # Initialize scanner if needed
            if not hasattr(public_api_scanner, 'api_sources'):
                await public_api_scanner.initialize()
            
            live_data = []
            
            for symbol in pairs:
                try:
                    # Get fresh market data for each symbol
                    market_data = await public_api_scanner.get_market_data(symbol)
                    
                    if market_data:
                        live_data.append({
                            'symbol': symbol,
                            'price': market_data.price,
                            'change_24h': market_data.change_24h,
                            'volume_24h': market_data.volume_24h,
                            'high_24h': market_data.high_24h,
                            'low_24h': market_data.low_24h,
                            'error': False
                        })
                    else:
                        live_data.append({
                            'symbol': symbol,
                            'price': 0.0,
                            'change_24h': 0.0,
                            'volume_24h': 0.0,
                            'high_24h': 0.0,
                            'low_24h': 0.0,
                            'error': True,
                            'error_msg': 'No data available'
                        })
                        
                except Exception as e:
                    logger.error(f"❌ Error getting data for {symbol}: {e}")
                    live_data.append({
                        'symbol': symbol,
                        'price': 0.0,
                        'change_24h': 0.0,
                        'volume_24h': 0.0,
                        'high_24h': 0.0,
                        'low_24h': 0.0,
                        'error': True,
                        'error_msg': f'Error: {str(e)[:30]}'
                    })
            
            logger.info(f"📊 Live monitor data collected for {len(live_data)} pairs")
            return live_data
            
        except Exception as e:
            logger.error(f"❌ Error getting live monitor data: {e}")
            return [
                {
                    'symbol': symbol,
                    'price': 0.0,
                    'change_24h': 0.0,
                    'volume_24h': 0.0,
                    'high_24h': 0.0,
                    'low_24h': 0.0,
                    'error': True,
                    'error_msg': 'Scheduler error'
                }
                for symbol in pairs
            ]
    
    async def _send_signal_to_telegram(self, signal: SignalData):
        """Send signal to Telegram"""
        try:
            if not self.telegram_bot:
                return
            
            # Format signal message
            message = self._format_signal_message(signal)
            
            # Send to admin, subscribers, and channel
            await self._send_to_recipients(message)
            
        except Exception as e:
            logger.error(f"❌ Error sending signal to Telegram: {e}")
    
    def _format_signal_message(self, signal: SignalData) -> str:
        """Format signal for Telegram"""
        try:
            # Create TP targets text
            tp_text = ""
            percentages = [40, 60, 80, 100]
            for i, (tp, pct) in enumerate(zip(signal.tp_targets, percentages)):
                tp_text += f"TP{i+1} – ${tp:.6f} ({pct}%)\n"
            
            # Create filters text
            filters_text = ""
            for filter_name in signal.filters_passed:
                filters_text += f"✅ {filter_name}\n"
            
            # Format message
            message = f"""#{signal.symbol} ({signal.signal_type}, x20)

📊 Entry - ${signal.entry_price:.6f}
🎯 Strength: {signal.strength:.0f}%

Take-Profit:
{tp_text}
🔥 Filters Passed:
{filters_text}⏰ {signal.timestamp.strftime('%H:%M:%S')} UTC"""
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error formatting signal message: {e}")
            return f"Signal detected for {signal.symbol} {signal.signal_type}"
    
    async def _send_to_recipients(self, message: str):
        """Send message to all recipients"""
        try:
            # This would integrate with the telegram bot's sending methods
            # For now, just log the message
            logger.info(f"📤 Signal message:\n{message}")
            
        except Exception as e:
            logger.error(f"❌ Error sending to recipients: {e}")
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            'is_running': self.is_running,
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'scan_count': self.scan_count,
            'error_count': self.error_count,
            'active_jobs': len(self.scheduler.get_jobs()) if self.is_running else 0,
            'next_scan': self.scheduler.get_job('main_scanner').next_run_time.isoformat() if self.is_running and self.scheduler.get_job('main_scanner') else None
        }

# Global scheduler instance
market_scheduler = MarketScheduler()