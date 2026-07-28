# backend/core/config.py
import os
import time
from datetime import datetime, timedelta

# Force timezone to CAT (UTC+2)
def set_timezone():
    """Set application timezone to CAT"""
    try:
        # Try to set environment variable
        os.environ['TZ'] = 'Africa/Harare'
        
        # For Python datetime
        import pytz
        from datetime import datetime
        CAT = pytz.timezone('Africa/Harare')
        
        # Store in session state or global
        return CAT
    except:
        # Fallback: manual offset
        return 2  # hours offset from UTC

# Use this for datetime operations
def get_current_time():
    """Get current time in CAT"""
    try:
        import pytz
        CAT = pytz.timezone('Africa/Harare')
        return datetime.now(CAT)
    except:
        # Manual offset
        return datetime.utcnow() + timedelta(hours=2)

# Set default timezone for the app
try:
    import pytz
    CAT = pytz.timezone('Africa/Harare')
except:
    CAT = None