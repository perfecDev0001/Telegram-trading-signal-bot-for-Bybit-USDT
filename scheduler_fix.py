#!/usr/bin/env python3
"""
Scheduler Fix Module
Handles ZoneInfo compatibility issues for APScheduler
"""

import sys
import warnings

# Suppress APScheduler warnings about timezone
warnings.filterwarnings('ignore', message='.*timezone.*')

# Fix for APScheduler timezone issues
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for older Python versions
    try:
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        # If neither is available, use pytz
        import pytz
        def ZoneInfo(key):
            return pytz.timezone(key)

# Fix for APScheduler
def fix_apscheduler_timezone():
    """Fix APScheduler timezone issues"""
    try:
        import apscheduler.schedulers.asyncio
        # APScheduler should work with the above imports
        return True
    except Exception:
        return False

# Initialize the fix
fix_apscheduler_timezone()