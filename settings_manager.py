#!/usr/bin/env python3
"""
Settings & Configuration Management Module
JSON-based configuration with real-time updates
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from database import db
from config import Config

@dataclass
class ScannerSettings:
    """Scanner configuration structure"""
    volume_threshold: float = 50.0
    pump_threshold: float = 5.0
    dump_threshold: float = -5.0
    breakout_threshold: float = 3.0
    scanner_status: bool = True
    pairs: List[str] = None
    tp_multipliers: List[float] = None
    
    def __post_init__(self):
        if self.pairs is None:
            self.pairs = [
                'BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT', 'XRPUSDT',
                'SOLUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT'
            ]
        if self.tp_multipliers is None:
            self.tp_multipliers = [1.5, 3.0, 5.0, 7.5]

@dataclass
class AdvancedFilters:
    """Advanced filter settings"""
    whale_tracking: bool = True
    spoofing_detection: bool = False
    spread_check: bool = True
    trend_match: bool = True
    volume_divergence: bool = False
    rsi_filter: bool = False
    ema_trend: bool = True

class SettingsManager:
    def __init__(self):
        self.settings_file = "settings.json"
        self.subscribers_file = "subscribers.json"
        self.signals_log_file = "signals_log.json"
        
        # Initialize files if they don't exist
        self.init_settings_files()
    
    def init_settings_files(self):
        """Initialize settings files with default values"""
        # Initialize settings.json
        if not os.path.exists(self.settings_file):
            default_settings = {
                "scanner": asdict(ScannerSettings()),
                "advanced_filters": asdict(AdvancedFilters()),
                "api": {
                    "bybit_api_key": Config.BYBIT_API_KEY or "",
                    "bybit_secret": Config.BYBIT_SECRET or "",
                    "rate_limit": 0.1,
                    "timeout": 10
                },
                "telegram": {
                    "admin_id": Config.ADMIN_ID,
                    "special_user": Config.SUBSCRIBER_ID,
                    "channel_id": Config.CHANNEL_ID
                },
                "last_updated": datetime.now().isoformat()
            }
            self.save_json(self.settings_file, default_settings)
        
        # Initialize subscribers.json
        if not os.path.exists(self.subscribers_file):
            default_subscribers = {
                "subscribers": [
                    {
                        "user_id": Config.ADMIN_ID,
                        "username": "dream_code_star",
                        "first_name": "Admin",
                        "added_date": datetime.now().isoformat(),
                        "is_active": True,
                        "is_admin": True
                    },
                    {
                        "user_id": Config.SUBSCRIBER_ID,
                        "username": "subscriber",
                        "first_name": "Subscriber",
                        "added_date": datetime.now().isoformat(),
                        "is_active": True,
                        "is_admin": False
                    }
                ],
                "last_updated": datetime.now().isoformat()
            }
            self.save_json(self.subscribers_file, default_subscribers)
        
        # Initialize signals_log.json
        if not os.path.exists(self.signals_log_file):
            default_log = {
                "signals": [],
                "last_updated": datetime.now().isoformat(),
                "total_signals": 0
            }
            self.save_json(self.signals_log_file, default_log)
    
    def load_json(self, filename: str) -> Dict:
        """Load JSON file safely"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading {filename}: {e}")
            return {}
    
    def save_json(self, filename: str, data: Dict) -> bool:
        """Save JSON file safely"""
        try:
            # Update timestamp
            data['last_updated'] = datetime.now().isoformat()
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error saving {filename}: {e}")
            return False
    
    # Scanner Settings Methods
    def get_scanner_settings(self) -> ScannerSettings:
        """Get current scanner settings"""
        data = self.load_json(self.settings_file)
        scanner_data = data.get('scanner', {})
        
        return ScannerSettings(
            volume_threshold=scanner_data.get('volume_threshold', 50.0),
            pump_threshold=scanner_data.get('pump_threshold', 5.0),
            dump_threshold=scanner_data.get('dump_threshold', -5.0),
            breakout_threshold=scanner_data.get('breakout_threshold', 3.0),
            scanner_status=scanner_data.get('scanner_status', True),
            pairs=scanner_data.get('pairs', []),
            tp_multipliers=scanner_data.get('tp_multipliers', [1.5, 3.0, 5.0, 7.5])
        )
    
    def update_scanner_settings(self, **kwargs) -> bool:
        """Update scanner settings"""
        try:
            data = self.load_json(self.settings_file)
            
            # Update scanner section
            for key, value in kwargs.items():
                if key in ['volume_threshold', 'pump_threshold', 'dump_threshold', 
                          'breakout_threshold', 'scanner_status', 'pairs', 'tp_multipliers']:
                    data['scanner'][key] = value
            
            # Also update database
            self.sync_to_database()
            
            return self.save_json(self.settings_file, data)
        except Exception as e:
            print(f"❌ Error updating scanner settings: {e}")
            return False
    
    def get_advanced_filters(self) -> AdvancedFilters:
        """Get advanced filter settings"""
        data = self.load_json(self.settings_file)
        filters_data = data.get('advanced_filters', {})
        
        return AdvancedFilters(
            whale_tracking=filters_data.get('whale_tracking', True),
            spoofing_detection=filters_data.get('spoofing_detection', False),
            spread_check=filters_data.get('spread_check', True),
            trend_match=filters_data.get('trend_match', True),
            volume_divergence=filters_data.get('volume_divergence', False),
            rsi_filter=filters_data.get('rsi_filter', False),
            ema_trend=filters_data.get('ema_trend', True)
        )
    
    def update_advanced_filters(self, **kwargs) -> bool:
        """Update advanced filter settings"""
        try:
            data = self.load_json(self.settings_file)
            
            # Update advanced_filters section
            for key, value in kwargs.items():
                if key in ['whale_tracking', 'spoofing_detection', 'spread_check', 
                          'trend_match', 'volume_divergence', 'rsi_filter', 'ema_trend']:
                    data['advanced_filters'][key] = value
            
            # Sync to database
            self.sync_to_database()
            
            return self.save_json(self.settings_file, data)
        except Exception as e:
            print(f"❌ Error updating advanced filters: {e}")
            return False
    
    def toggle_scanner(self) -> bool:
        """Toggle scanner on/off"""
        settings = self.get_scanner_settings()
        new_status = not settings.scanner_status
        return self.update_scanner_settings(scanner_status=new_status)
    
    def update_thresholds(self, volume: float = None, pump: float = None, 
                         dump: float = None, breakout: float = None) -> bool:
        """Update detection thresholds"""
        updates = {}
        if volume is not None:
            updates['volume_threshold'] = volume
        if pump is not None:
            updates['pump_threshold'] = pump
        if dump is not None:
            updates['dump_threshold'] = dump
        if breakout is not None:
            updates['breakout_threshold'] = breakout
        
        return self.update_scanner_settings(**updates)
    
    def update_tp_multipliers(self, multipliers: List[float]) -> bool:
        """Update TP multiplier values"""
        if len(multipliers) != 4:
            return False
        return self.update_scanner_settings(tp_multipliers=multipliers)
    
    def add_trading_pair(self, symbol: str) -> bool:
        """Add a trading pair to monitoring list"""
        settings = self.get_scanner_settings()
        if symbol.upper() not in settings.pairs:
            settings.pairs.append(symbol.upper())
            return self.update_scanner_settings(pairs=settings.pairs)
        return False
    
    def remove_trading_pair(self, symbol: str) -> bool:
        """Remove a trading pair from monitoring list"""
        settings = self.get_scanner_settings()
        if symbol.upper() in settings.pairs:
            settings.pairs.remove(symbol.upper())
            return self.update_scanner_settings(pairs=settings.pairs)
        return False
    
    # Subscriber Management Methods
    def get_all_subscribers(self) -> List[Dict]:
        """Get all subscribers"""
        data = self.load_json(self.subscribers_file)
        return data.get('subscribers', [])
    
    def get_active_subscribers(self) -> List[int]:
        """Get active subscriber IDs"""
        subscribers = self.get_all_subscribers()
        return [sub['user_id'] for sub in subscribers if sub.get('is_active', True)]
    
    def add_subscriber(self, user_id: int, username: str = None, 
                      first_name: str = None, last_name: str = None) -> bool:
        """Add a new subscriber"""
        try:
            data = self.load_json(self.subscribers_file)
            
            # Check if already exists
            for sub in data['subscribers']:
                if sub['user_id'] == user_id:
                    sub['is_active'] = True  # Reactivate if exists
                    return self.save_json(self.subscribers_file, data)
            
            # Add new subscriber
            new_subscriber = {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "added_date": datetime.now().isoformat(),
                "is_active": True,
                "is_admin": user_id == Config.ADMIN_ID
            }
            
            data['subscribers'].append(new_subscriber)
            
            # Also add to database
            db.add_subscriber(user_id, username, first_name, last_name)
            
            return self.save_json(self.subscribers_file, data)
        except Exception as e:
            print(f"❌ Error adding subscriber: {e}")
            return False
    
    def remove_subscriber(self, user_id: int) -> bool:
        """Remove/deactivate a subscriber"""
        try:
            data = self.load_json(self.subscribers_file)
            
            for sub in data['subscribers']:
                if sub['user_id'] == user_id:
                    sub['is_active'] = False
                    
                    # Also remove from database
                    db.remove_subscriber(user_id)
                    
                    return self.save_json(self.subscribers_file, data)
            return False
        except Exception as e:
            print(f"❌ Error removing subscriber: {e}")
            return False
    
    def export_subscribers(self) -> str:
        """Export subscribers list as formatted text"""
        subscribers = self.get_all_subscribers()
        
        export_text = f"📋 SUBSCRIBERS EXPORT\n"
        export_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        export_text += f"Total: {len(subscribers)} subscribers\n\n"
        
        for i, sub in enumerate(subscribers, 1):
            status = "✅ Active" if sub.get('is_active', True) else "❌ Inactive"
            admin = " (ADMIN)" if sub.get('is_admin', False) else ""
            
            export_text += f"{i}. User ID: {sub['user_id']}\n"
            export_text += f"   Username: @{sub.get('username', 'N/A')}\n"
            export_text += f"   Name: {sub.get('first_name', 'N/A')}\n"
            export_text += f"   Status: {status}{admin}\n"
            export_text += f"   Added: {sub.get('added_date', 'N/A')}\n\n"
        
        return export_text
    
    # Signal Logging Methods
    def add_signal_log(self, symbol: str, signal_type: str, price: float, 
                      strength: float, tp_targets: List[float], 
                      filters_passed: Dict[str, bool]) -> bool:
        """Add a signal to the log"""
        try:
            data = self.load_json(self.signals_log_file)
            
            signal_entry = {
                "id": data.get('total_signals', 0) + 1,
                "symbol": symbol,
                "signal_type": signal_type,
                "price": price,
                "strength": strength,
                "tp_targets": tp_targets,
                "filters_passed": filters_passed,
                "timestamp": datetime.now().isoformat(),
                "sent_to_subscribers": True
            }
            
            data['signals'].append(signal_entry)
            data['total_signals'] = data.get('total_signals', 0) + 1
            
            # Keep only last 1000 signals
            if len(data['signals']) > 1000:
                data['signals'] = data['signals'][-1000:]
            
            return self.save_json(self.signals_log_file, data)
        except Exception as e:
            print(f"❌ Error adding signal log: {e}")
            return False
    
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """Get recent signals from log"""
        data = self.load_json(self.signals_log_file)
        signals = data.get('signals', [])
        return signals[-limit:] if signals else []
    
    def export_signals_log(self, days: int = 7) -> str:
        """Export signals log as formatted text"""
        from datetime import datetime, timedelta
        
        data = self.load_json(self.signals_log_file)
        signals = data.get('signals', [])
        
        # Filter by date
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_signals = []
        
        for signal in signals:
            try:
                signal_date = datetime.fromisoformat(signal['timestamp'])
                if signal_date >= cutoff_date:
                    recent_signals.append(signal)
            except:
                continue
        
        export_text = f"📊 SIGNALS LOG EXPORT\n"
        export_text += f"Period: Last {days} days\n"
        export_text += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        export_text += f"Total signals: {len(recent_signals)}\n\n"
        
        for signal in recent_signals:
            export_text += f"🎯 #{signal['symbol']} - {signal['signal_type']}\n"
            export_text += f"   Price: ${signal['price']:.4f}\n"
            export_text += f"   Strength: {signal['strength']:.1f}%\n"
            export_text += f"   Time: {signal['timestamp']}\n"
            
            # Filters passed
            filters = signal.get('filters_passed', {})
            passed_filters = [k for k, v in filters.items() if v]
            export_text += f"   Filters: {', '.join(passed_filters)}\n\n"
        
        return export_text
    
    def sync_to_database(self):
        """Sync JSON settings to database"""
        try:
            settings = self.get_scanner_settings()
            filters = self.get_advanced_filters()
            
            # Update database scanner status
            db.update_scanner_status(
                is_running=settings.scanner_status,
                monitored_pairs=json.dumps(settings.pairs),
                pump_threshold=settings.pump_threshold,
                dump_threshold=settings.dump_threshold,
                breakout_threshold=settings.breakout_threshold,
                volume_threshold=settings.volume_threshold,
                tp_multipliers=json.dumps(settings.tp_multipliers),
                whale_tracking=filters.whale_tracking,
                spoofing_detection=filters.spoofing_detection,
                spread_filter=filters.spread_check,
                trend_match=filters.trend_match
            )
            
        except Exception as e:
            print(f"❌ Error syncing to database: {e}")
    
    def get_all_settings(self) -> Dict:
        """Get all settings (compatibility method)"""
        return self.load_json(self.settings_file)
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status"""
        settings = self.get_scanner_settings()
        filters = self.get_advanced_filters()
        subscribers = self.get_all_subscribers()
        recent_signals = self.get_recent_signals(5)
        
        return {
            "scanner_running": settings.scanner_status,
            "monitored_pairs": len(settings.pairs),
            "active_subscribers": len([s for s in subscribers if s.get('is_active', True)]),
            "recent_signals": len(recent_signals),
            "thresholds": {
                "volume": settings.volume_threshold,
                "pump": settings.pump_threshold,
                "dump": settings.dump_threshold,
                "breakout": settings.breakout_threshold
            },
            "advanced_filters": {
                "whale_tracking": filters.whale_tracking,
                "spoofing_detection": filters.spoofing_detection,
                "spread_check": filters.spread_check,
                "trend_match": filters.trend_match
            },
            "tp_multipliers": settings.tp_multipliers,
            "last_updated": datetime.now().isoformat()
        }

# Global settings manager instance
settings_manager = SettingsManager()

# Access control function
def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    from config import Config
    return user_id == Config.ADMIN_ID

if __name__ == "__main__":
    # Test settings manager
    sm = SettingsManager()
    print("✅ Settings Manager initialized")
    print(f"📊 System Status: {sm.get_system_status()}")