import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional
from config import Config

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Subscribers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Signals log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    price REAL NOT NULL,
                    change_percent REAL NOT NULL,
                    volume REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message TEXT
                )
            ''')
            
            # Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Scanner status table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scanner_status (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    is_running BOOLEAN DEFAULT 1,
                    last_scan TIMESTAMP,
                    monitored_pairs TEXT,
                    pump_threshold REAL DEFAULT 5.0,
                    dump_threshold REAL DEFAULT -5.0,
                    breakout_threshold REAL DEFAULT 3.0,
                    volume_threshold REAL DEFAULT 50.0,
                    tp_multipliers TEXT DEFAULT '[1.5, 3.0, 5.0, 7.5]',
                    whale_tracking BOOLEAN DEFAULT 1,
                    spoofing_detection BOOLEAN DEFAULT 0,
                    spread_filter BOOLEAN DEFAULT 1,
                    trend_match BOOLEAN DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            self.migrate_database()
            self.init_default_settings()
    
    def migrate_database(self):
        """Handle database migrations"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Check if volume_threshold column exists
            cursor.execute("PRAGMA table_info(scanner_status)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Add missing columns (including new enhanced filters)
            new_columns = {
                'volume_threshold': 'REAL DEFAULT 50.0',
                'tp_multipliers': 'TEXT DEFAULT \'[1.5, 3.0, 5.0, 7.5]\'',
                'whale_tracking': 'BOOLEAN DEFAULT 1',
                'spoofing_detection': 'BOOLEAN DEFAULT 0',
                'spread_filter': 'BOOLEAN DEFAULT 1',
                'trend_match': 'BOOLEAN DEFAULT 1',
                'liquidity_imbalance': 'BOOLEAN DEFAULT 1',
                'rsi_momentum': 'BOOLEAN DEFAULT 1'
            }
            
            for column_name, column_def in new_columns.items():
                if column_name not in columns:
                    try:
                        cursor.execute(f'ALTER TABLE scanner_status ADD COLUMN {column_name} {column_def}')
                        print(f"✅ Added {column_name} column to scanner_status table")
                    except Exception as e:
                        print(f"Error adding {column_name} column: {e}")
            
            conn.commit()
    
    def init_default_settings(self):
        """Initialize default settings if they don't exist"""
        default_settings = {
            'monitored_pairs': json.dumps(Config.DEFAULT_PAIRS),
            'pump_threshold': str(Config.PUMP_THRESHOLD),
            'dump_threshold': str(Config.DUMP_THRESHOLD),
            'breakout_threshold': str(Config.BREAKOUT_THRESHOLD),
            'scanner_enabled': 'true'
        }
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for key, value in default_settings.items():
                cursor.execute('''
                    INSERT OR IGNORE INTO settings (key, value) 
                    VALUES (?, ?)
                ''', (key, value))
            
            # Initialize scanner status
            cursor.execute('''
                INSERT OR IGNORE INTO scanner_status (
                    id, is_running, monitored_pairs, pump_threshold, 
                    dump_threshold, breakout_threshold, volume_threshold
                ) VALUES (1, 1, ?, ?, ?, ?, ?)
            ''', (
                json.dumps(Config.DEFAULT_PAIRS),
                Config.PUMP_THRESHOLD,
                Config.DUMP_THRESHOLD,
                Config.BREAKOUT_THRESHOLD,
                50.0  # Default volume threshold
            ))
            
            # Add default admin subscriber
            cursor.execute('''
                INSERT OR IGNORE INTO subscribers (user_id, username, first_name, is_active)
                VALUES (?, ?, ?, ?)
            ''', (Config.ADMIN_ID, 'admin', 'Admin User', 1))
            
            # Add default user subscriber
            cursor.execute('''
                INSERT OR IGNORE INTO subscribers (user_id, username, first_name, is_active)
                VALUES (?, ?, ?, ?)
            ''', (Config.SUBSCRIBER_ID, 'subscriber', 'Subscriber User', 1))
            
            conn.commit()
    
    # Subscriber methods
    def add_subscriber(self, user_id: int, username: str = None, 
                      first_name: str = None, last_name: str = None) -> bool:
        """Add a new subscriber"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO subscribers 
                    (user_id, username, first_name, last_name, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (user_id, username, first_name, last_name))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding subscriber: {e}")
            return False
    
    def remove_subscriber(self, user_id: int) -> bool:
        """Remove a subscriber"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM subscribers WHERE user_id = ?', (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing subscriber: {e}")
            return False
    
    def get_active_subscribers(self) -> List[int]:
        """Get list of active subscriber IDs"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM subscribers WHERE is_active = 1')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting subscribers: {e}")
            return []
    
    def get_subscribers_info(self) -> List[Dict]:
        """Get detailed subscriber information"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT user_id, username, first_name, last_name, added_date, is_active
                    FROM subscribers ORDER BY added_date DESC
                ''')
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting subscriber info: {e}")
            return []
    
    # Signal methods
    def add_signal(self, symbol: str, signal_type: str, price: float, 
                   change_percent: float, volume: float = None, message: str = None) -> bool:
        """Add a new signal to the log"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO signals_log 
                    (symbol, signal_type, price, change_percent, volume, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, signal_type, price, change_percent, volume, message))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding signal: {e}")
            return False
    
    def get_recent_signals(self, limit: int = 10) -> List[Dict]:
        """Get recent signals from the log"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM signals_log 
                    ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting signals: {e}")
            return []
    
    # Settings methods
    def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"Error getting setting {key}: {e}")
            return None
    
    def set_setting(self, key: str, value: str) -> bool:
        """Set a setting value"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, value))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error setting {key}: {e}")
            return False
    
    # Scanner status methods
    def get_scanner_status(self) -> Dict:
        """Get current scanner status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM scanner_status WHERE id = 1')
                result = cursor.fetchone()
                if result:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, result))
                return {}
        except Exception as e:
            print(f"Error getting scanner status: {e}")
            return {}
    
    def update_scanner_status(self, **kwargs) -> bool:
        """Update scanner status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build dynamic update query
                fields = []
                values = []
                for key, value in kwargs.items():
                    fields.append(f"{key} = ?")
                    values.append(value)
                
                if fields:
                    fields.append("updated_at = CURRENT_TIMESTAMP")
                    query = f"UPDATE scanner_status SET {', '.join(fields)} WHERE id = 1"
                    cursor.execute(query, values)
                    conn.commit()
                    return True
                return False
        except Exception as e:
            print(f"Error updating scanner status: {e}")
            return False
    
    def update_last_scan(self):
        """Update the last scan timestamp"""
        return self.update_scanner_status(last_scan=datetime.now().isoformat())
    
    def update_scanner_setting(self, key: str, value) -> bool:
        """Update a single scanner setting"""
        try:
            return self.update_scanner_status(**{key: value})
        except Exception as e:
            print(f"Error updating scanner setting {key}: {e}")
            return False
    
    def log_signal(self, symbol: str, signal_type: str, price: float, 
                   change_percent: float, volume: float = None, message: str = None) -> bool:
        """Log a signal (alias for add_signal for compatibility)"""
        return self.add_signal(symbol, signal_type, price, change_percent, volume, message)
    
    def get_signals_log(self, limit: int = 100) -> List[Dict]:
        """Get signals log with specified limit"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM signals_log 
                    ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting signals log: {e}")
            return []
    
    def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get counts
                cursor.execute("SELECT COUNT(*) FROM subscribers WHERE is_active = 1")
                active_subscribers = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM signals_log WHERE DATE(timestamp) = DATE('now')")
                signals_today = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM signals_log WHERE timestamp >= datetime('now', '-24 hours')")
                signals_24h = cursor.fetchone()[0]
                
                # Get scanner status
                scanner_status = self.get_scanner_status()
                
                return {
                    'active_subscribers': active_subscribers,
                    'signals_today': signals_today,
                    'signals_24h': signals_24h,
                    'scanner_running': scanner_status.get('is_running', False),
                    'last_scan': scanner_status.get('last_scan', 'Never'),
                    'monitored_pairs_count': len(json.loads(scanner_status.get('monitored_pairs', '[]'))),
                    'thresholds': {
                        'pump': scanner_status.get('pump_threshold', 5.0),
                        'dump': scanner_status.get('dump_threshold', -5.0),
                        'breakout': scanner_status.get('breakout_threshold', 3.0),
                        'volume': scanner_status.get('volume_threshold', 50.0)
                    }
                }
                
        except Exception as e:
            print(f"Error getting system stats: {e}")
            return {}
    
    def save_signal(self, signal) -> bool:
        """Save a signal object to the database"""
        try:
            return self.add_signal(
                symbol=signal.symbol,
                signal_type=signal.signal_type,
                price=signal.price,
                change_percent=signal.change_percent,
                volume=signal.volume,
                message=signal.message
            )
        except Exception as e:
            print(f"Error saving signal: {e}")
            return False
    
    def update_scan_stats(self, signals_count: int) -> bool:
        """Update scan statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update last scan time
                cursor.execute('''
                    UPDATE scanner_status 
                    SET last_scan = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = 1
                ''')
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating scan stats: {e}")
            return False

# Global database instance
db = Database()