#!/usr/bin/env python3
"""
Initialize database with proper default settings
"""

from database import db

def init_database():
    """Initialize database with default settings"""
    print("🔧 Initializing database...")
    
    # Ensure scanner is enabled
    db.update_scanner_status(is_running=True)
    
    # Get current status
    status = db.get_scanner_status()
    print(f"📊 Scanner status: {status}")
    
    print("✅ Database initialized successfully")

if __name__ == "__main__":
    init_database()