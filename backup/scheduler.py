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
from enhanced_scanner import enhanced_scanner

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
        
        # Configure scheduler
        self.scheduler.add_jobstore('memory')
        
        # Add error listener
        from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
        self.scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._job_success_listener, EVENT_JOB_EXECUTED)
        
        logger.info("✅ Market Scheduler initialized")
    
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
            
            # Add health check job (every 5 minutes)
            self.scheduler.add_job(
                self._health_check,
                trigger=IntervalTrigger(minutes=5),
                id='health_check',
                name='Health Check',
                replace_existing=True,
                max_instances=1
            )
            
            logger.info(f"🚀 Market Scanner started with {Config.SCANNER_INTERVAL}s interval")
            
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
        """Main market scanning function"""
        try:
            # Check if scanner is enabled
            scanner_status = db.get_scanner_status()
            if not scanner_status.get('is_running', True):
                logger.info("📴 Scanner disabled, skipping scan")
                return
            
            # Get monitored pairs
            import json
            monitored_pairs = json.loads(scanner_status.get('monitored_pairs', '["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]'))
            
            logger.info(f"🔍 Starting scan of {len(monitored_pairs)} pairs...")
            
            # Scan all pairs
            signals_found = []
            for symbol in monitored_pairs:
                try:
                    # Add timeout to prevent hanging
                    signal = await asyncio.wait_for(
                        enhanced_scanner.scan_symbol_comprehensive(symbol),
                        timeout=10.0  # 10 second timeout per symbol
                    )
                    
                    if signal:
                        signals_found.append(signal)
                        logger.info(f"🎯 Signal found for {symbol}: {signal.signal_type} ({signal.strength:.1f}%)")
                        
                        # Send signal to recipients
                        if self.telegram_bot:
                            try:
                                await enhanced_scanner.send_signal_to_recipients(signal, self.telegram_bot)
                            except Exception as send_error:
                                logger.error(f"❌ Error sending signal for {symbol}: {send_error}")
                
                except asyncio.TimeoutError:
                    logger.warning(f"⏱️ Timeout scanning {symbol}")
                    continue
                except Exception as e:
                    logger.error(f"❌ Error scanning {symbol}: {e}")
                    continue
            
            # Log scan results
            if signals_found:
                logger.info(f"✅ Scan completed - {len(signals_found)} signals found")
            else:
                logger.debug("✅ Scan completed - no signals found")
            
            # Update database with scan timestamp
            db.update_scanner_status(last_scan_time=datetime.now().isoformat())
            
        except Exception as e:
            logger.error(f"❌ Error in market scan: {e}")
            raise
    
    async def _health_check(self):
        """Periodic health check"""
        try:
            # Check API connectivity
            api_status = await enhanced_scanner.get_api_status()
            
            if not api_status.get('connected', False):
                logger.warning("⚠️ API connectivity issues detected")
                
                # Try to reconnect or adjust settings
                if self.error_count < 3:
                    logger.info("🔄 Attempting to recover API connection...")
                    # Reset error counters in scanner
                    enhanced_scanner.api_errors = 0
                else:
                    logger.warning("🔄 Too many API errors, pausing scanner briefly...")
                    await self.pause_scanner(60)  # Pause for 1 minute
            
            # Check memory usage
            import psutil
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > 85:
                logger.warning(f"⚠️ High memory usage: {memory_percent}%")
                # Clear scanner history to free memory
                enhanced_scanner.price_history.clear()
                enhanced_scanner.volume_history.clear()
            
            logger.debug(f"💚 Health check passed - Memory: {memory_percent}%, API: {'✅' if api_status.get('connected') else '❌'}")
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
    
    async def force_scan(self) -> list:
        """Force an immediate scan of all monitored pairs"""
        try:
            scanner_status = db.get_scanner_status()
            import json
            monitored_pairs = json.loads(scanner_status.get('monitored_pairs', '["BTCUSDT", "ETHUSDT", "ADAUSDT", "BNBUSDT", "XRPUSDT"]'))
            
            logger.info(f"⚡ Force scan initiated for {len(monitored_pairs)} pairs")
            
            signals_found = []
            scan_results = []
            
            for symbol in monitored_pairs:
                try:
                    # Scan with timeout
                    signal = await asyncio.wait_for(
                        enhanced_scanner.scan_symbol_comprehensive(symbol),
                        timeout=8.0
                    )
                    
                    if signal:
                        signals_found.append(signal)
                        scan_results.append(f"🎯 {symbol}: SIGNAL ({signal.strength:.0f}%)")
                        
                        # Send signal immediately
                        if self.telegram_bot:
                            try:
                                await enhanced_scanner.send_signal_to_recipients(signal, self.telegram_bot)
                            except Exception as send_error:
                                logger.error(f"❌ Error sending signal for {symbol}: {send_error}")
                    else:
                        # Get basic market data
                        market_data = await asyncio.wait_for(
                            enhanced_scanner.get_market_data(symbol),
                            timeout=5.0
                        )
                        if market_data:
                            change_emoji = "📈" if market_data.change_24h > 0 else "📉"
                            scan_results.append(f"{change_emoji} {symbol}: {market_data.change_24h:+.2f}%")
                        else:
                            scan_results.append(f"⚠️ {symbol}: No data")
                
                except asyncio.TimeoutError:
                    scan_results.append(f"⏱️ {symbol}: Timeout")
                except Exception as e:
                    scan_results.append(f"❌ {symbol}: Error")
            
            logger.info(f"⚡ Force scan completed - {len(signals_found)} signals found")
            return scan_results
            
        except Exception as e:
            logger.error(f"❌ Force scan failed: {e}")
            return [f"❌ Force scan failed: {str(e)}"]
    
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