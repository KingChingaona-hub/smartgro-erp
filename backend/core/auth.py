# backend/core/auth.py
import pandas as pd
import streamlit as st
from backend.core.db_adapter import load_users, save_users
from backend.utils.utils import hash_password
from backend.utils.phone_utils import validate_zimbabwe_phone
from backend.modules.shift_manager import can_cashier_login
from datetime import datetime
import logging
from collections import defaultdict
import time
import re
import secrets
import string

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================
# RATE LIMITING
# ==============================
_login_attempts = defaultdict(int)
_login_lockout = {}
_LOCKOUT_TIME = 300  # 5 minutes
_MAX_ATTEMPTS = 5

# ==============================
# USER ROLES AND PERMISSIONS
# ==============================

ROLES = {
    "owner": {
        "level": 100,
        "permissions": ["all"],
        "description": "Full system access - all features",
        "mobile_access": True,
        "color": "#FF6B6B",
        "icon": "👑"
    },
    "manager": {
        "level": 80,
        "permissions": [
            "view_all", "edit_products", "view_reports", "manage_staff", 
            "manage_debtors", "manage_purchases", "manage_shifts",
            "branch_performance", "mobile_dashboard", "whatsapp_alerts",
            "demand_forecasting", "live_dashboard", "security",
            "language_management", "offline_mode", "financial_closing",
            "supplier_bidding", "customer_360", "returns_management", "documents", 
            "profit_analysis", "predictive_analytics", "competitor_price", 
            "payment_gateway", "accounting_sync", "ecommerce_sync", "sms_gateway",
            "smart_replenishment", "automated_followup", "workflow_approvals",
            "pwa_setup", "voice_commands", "barcode_scanner", "white_label",
            "multi_tenant", "api_developer"
        ],
        "description": "Can manage operations but not system settings",
        "mobile_access": True,
        "color": "#4ECDC4",
        "icon": "📊"
    },
    "cashier": {
        "level": 50,
        "permissions": [
            "pos", "view_inventory", "create_customer", "view_sales_history",
            "mobile_dashboard", "voice_commands", "barcode_scanner"
        ],
        "description": "Can process sales and view basic info",
        "mobile_access": True,
        "color": "#45B7D1",
        "icon": "🛒"
    },
    "viewer": {
        "level": 20,
        "permissions": ["view_reports_only", "mobile_dashboard"],
        "description": "Read-only access to reports",
        "mobile_access": True,
        "color": "#96CEB4",
        "icon": "👁️"
    },
    "mobile_user": {
        "level": 30,
        "permissions": [
            "mobile_dashboard", "view_inventory", "view_sales_history",
            "whatsapp_alerts", "receive_notifications"
        ],
        "description": "Mobile-only access for on-the-go monitoring",
        "mobile_access": True,
        "color": "#FFEAA7",
        "icon": "📱"
    }
}


def get_user_permissions(role):
    """Get permissions for a specific role"""
    return ROLES.get(role, {}).get("permissions", [])


def has_permission(role, permission):
    """Check if a role has a specific permission"""
    permissions = get_user_permissions(role)
    return "all" in permissions or permission in permissions


def can_access_feature(role, feature):
    """Check if user can access a specific feature"""
    # Owner has access to everything
    if role == "owner":
        return True
    
    # Define feature permissions
    feature_permissions = {
        # POS & Sales
        "pos": ["cashier", "manager", "owner"],
        "inventory_view": ["cashier", "manager", "owner", "mobile_user"],
        "inventory_edit": ["manager", "owner"],
        "sales_history": ["cashier", "manager", "owner", "mobile_user"],
        "sales_dashboard": ["manager", "owner"],
        
        # Purchasing
        "purchases": ["manager", "owner"],
        
        # Finance
        "expenses": ["manager", "owner"],
        "income": ["manager", "owner"],
        "pl": ["manager", "owner"],
        "cash_dashboard": ["manager", "owner"],
        
        # Customers
        "customers": ["cashier", "manager", "owner"],
        "debtors": ["manager", "owner"],
        "debtors_dashboard": ["manager", "owner"],
        "customer_app": ["owner", "manager", "cashier", "viewer", "mobile_user"],
        "customer_insights": ["manager", "owner"],
        "customer_360": ["manager", "owner"],
        
        # Analytics & Intelligence
        "business_advisor": ["manager", "owner"],
        "reports": ["manager", "owner"],
        "demand_forecasting": ["manager", "owner"],
        "live_dashboard": ["manager", "owner"],
        "security": ["manager", "owner"],
        "language_management": ["manager", "owner"],
        "offline_mode": ["manager", "owner"],
        "financial_closing": ["manager", "owner"],
        "supplier_bidding": ["manager", "owner"],
        "returns_management": ["manager", "owner"],
        "documents": ["manager", "owner"],
        "profit_analysis": ["manager", "owner"],
        "predictive_analytics": ["manager", "owner"],
        "competitor_price": ["manager", "owner"],
        "payment_gateway": ["manager", "owner"],
        "accounting_sync": ["manager", "owner"],
        "ecommerce_sync": ["manager", "owner"],
        "sms_gateway": ["manager", "owner"],
        "smart_replenishment": ["manager", "owner"],
        "automated_followup": ["manager", "owner"],
        "workflow_approvals": ["manager", "owner"],
        "pwa_setup": ["manager", "owner"],
        "voice_commands": ["cashier", "manager", "owner"],
        "barcode_scanner": ["cashier", "manager", "owner"],
        "white_label": ["owner"],
        "multi_tenant": ["owner"],
        "api_developer": ["manager", "owner"],
        
        # Administration
        "settings": ["owner"],
        "user_management": ["owner"],
        "branch_management": ["owner"],
        
        # Operations
        "shift_management": ["manager", "owner"],
        "branch_performance": ["manager", "owner"],
        
        # Mobile & Alerts
        "mobile_dashboard": ["owner", "manager", "cashier", "mobile_user"],
        "whatsapp_alerts": ["owner", "manager"],
        "receive_notifications": ["owner", "manager", "mobile_user"],
        "mobile_approvals": ["owner", "manager"]
    }
    
    allowed_roles = feature_permissions.get(feature, [])
    return role in allowed_roles


def can_use_mobile(role):
    """Check if role has mobile access"""
    return ROLES.get(role, {}).get("mobile_access", False)


def get_role_icon(role):
    """Get icon for role"""
    return ROLES.get(role, {}).get("icon", "👤")


def get_role_color(role):
    """Get color for role"""
    return ROLES.get(role, {}).get("color", "#666666")


# ==============================
# PASSWORD STRENGTH VALIDATION
# ==============================

def validate_password_strength(password):
    """
    Validate password strength.
    Returns (is_valid, message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)"
    
    return True, "Password is strong"


def generate_strong_password(length=16):
    """Generate a strong random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    return ''.join(secrets.choice(alphabet) for i in range(length))


def get_password_strength_score(password):
    """Get password strength score (0-100)"""
    score = 0
    
    # Length
    if len(password) >= 12:
        score += 25
    elif len(password) >= 8:
        score += 15
    else:
        score += 5
    
    # Uppercase
    if re.search(r'[A-Z]', password):
        score += 15
    
    # Lowercase
    if re.search(r'[a-z]', password):
        score += 15
    
    # Numbers
    if re.search(r'[0-9]', password):
        score += 15
    
    # Special characters
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 20
    
    # Uniqueness (no repeated patterns)
    if len(set(password)) > len(password) * 0.7:
        score += 10
    
    return min(score, 100)


# ==============================
# INIT USERS - PostgreSQL VERSION WITH FALLBACK
# ==============================

def init_users():
    """Initialize default users if none exist - with fallback for plain text"""
    try:
        logger.info("Initializing users...")
        df = load_users()
        
        # If no users exist, create default ones
        if df.empty:
            logger.info("No users found. Creating default users...")
            default_users = create_default_users()
            save_users(default_users)
            logger.info("✅ Default users created successfully!")
            return default_users
        
        # Check if we have at least one admin user
        if "admin" in df["username"].values:
            logger.info("✅ Users already exist. Found admin user.")
            return df
        
        # If no admin, add default users
        logger.info("No admin user found. Adding default users...")
        default_users = create_default_users()
        
        # Combine with existing
        combined_df = pd.concat([df, default_users], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=["username"], keep="last")
        save_users(combined_df)
        logger.info("✅ Default users added successfully!")
        return combined_df
        
    except Exception as e:
        logger.error(f"❌ Error initializing users: {e}")
        # Try to create a temporary user for testing
        try:
            logger.info("Attempting emergency user creation...")
            emergency_users = pd.DataFrame([{
                "username": "admin",
                "password": "admin123",  # Plain text for emergency
                "role": "owner",
                "branch_id": "HO",
                "full_name": "Emergency Admin",
                "phone": "",
                "active": True,
                "mobile_enabled": True,
                "whatsapp": "",
                "receive_alerts": False,
                "last_login": None,
                "last_mobile_login": None,
                "device_info": "",
                "two_factor_enabled": False,
                "session_token": ""
            }])
            save_users(emergency_users)
            logger.info("✅ Emergency admin user created!")
            return emergency_users
        except Exception as e2:
            logger.error(f"❌ Emergency user creation failed: {e2}")
            return pd.DataFrame()


def create_default_users():
    """Create default users list"""
    return pd.DataFrame([
        {
            "username": "admin",
            "password": hash_password("admin123"),
            "role": "owner",
            "branch_id": "HO",
            "full_name": "System Administrator",
            "phone": "0772123456",
            "active": True,
            "mobile_enabled": True,
            "whatsapp": "0772123456",
            "receive_alerts": True,
            "last_login": None,
            "last_mobile_login": None,
            "device_info": "",
            "two_factor_enabled": False,
            "session_token": ""
        },
        {
            "username": "manager",
            "password": hash_password("manager123"),
            "role": "manager",
            "branch_id": "HO",
            "full_name": "Store Manager",
            "phone": "0772123457",
            "active": True,
            "mobile_enabled": True,
            "whatsapp": "0772123457",
            "receive_alerts": True,
            "last_login": None,
            "last_mobile_login": None,
            "device_info": "",
            "two_factor_enabled": False,
            "session_token": ""
        },
        {
            "username": "cashier",
            "password": hash_password("cash123"),
            "role": "cashier",
            "branch_id": "HO",
            "full_name": "Cashier",
            "phone": "0772123458",
            "active": True,
            "mobile_enabled": True,
            "whatsapp": "",
            "receive_alerts": False,
            "last_login": None,
            "last_mobile_login": None,
            "device_info": "",
            "two_factor_enabled": False,
            "session_token": ""
        }
    ])


# ==============================
# LOGIN FUNCTIONS - WITH RATE LIMITING
# ==============================

def check_login(username, password):
    """Standard login check with rate limiting"""
    try:
        logger.info(f"Login attempt for user: {username}")
        df = load_users()
        
        # Check if account is locked out
        if username in _login_lockout:
            lockout_time = _login_lockout[username]
            if time.time() < lockout_time:
                remaining = int(lockout_time - time.time())
                st.error(f"Account locked. Try again in {remaining} seconds.")
                return False, None
            else:
                # Lockout expired
                del _login_lockout[username]
                _login_attempts[username] = 0
        
        if df.empty:
            logger.warning("No users found in database! Creating default users...")
            df = init_users()
            if df.empty:
                logger.error("❌ Failed to create default users!")
                return False, None
        
        # Ensure required columns exist
        if "active" not in df.columns:
            df["active"] = True
            save_users(df)
        
        # Try hashed password first
        hashed = hash_password(password)
        
        # Check for user with hashed password
        user = df[
            (df["username"] == username) &
            (df["password"] == hashed) &
            (df["active"] == True)
        ]
        
        if not user.empty:
            logger.info(f"✅ Login successful (hashed) for: {username}")
            # Reset attempts on successful login
            _login_attempts[username] = 0
            if username in _login_lockout:
                del _login_lockout[username]
            return process_login_user(user, df)
        
        # If hashed fails, try plain text (for backward compatibility)
        user = df[
            (df["username"] == username) &
            (df["password"] == password) &
            (df["active"] == True)
        ]
        
        if not user.empty:
            logger.info(f"⚠️ Login successful (plain text) for: {username}")
            # Reset attempts on successful login
            _login_attempts[username] = 0
            if username in _login_lockout:
                del _login_lockout[username]
            # Update to hashed password for security
            try:
                idx = user.index[0]
                df.loc[idx, "password"] = hashed
                save_users(df)
                logger.info(f"✅ Updated password to hashed for: {username}")
            except Exception as e:
                logger.warning(f"Could not update to hashed password: {e}")
            return process_login_user(user, df)
        
        # Login failed - increment attempts
        _login_attempts[username] += 1
        attempts_left = _MAX_ATTEMPTS - _login_attempts[username]
        
        if _login_attempts[username] >= _MAX_ATTEMPTS:
            _login_lockout[username] = time.time() + _LOCKOUT_TIME
            logger.warning(f"🔒 Account locked for {username} due to too many failed attempts")
            st.error(f"Too many failed attempts. Account locked for 5 minutes.")
            return False, None
        
        # Check if user exists but inactive
        inactive_user = df[
            (df["username"] == username) &
            (df["active"] == False)
        ]
        
        if not inactive_user.empty:
            logger.warning(f"❌ Login blocked - user inactive: {username}")
            st.error("User account is deactivated. Please contact administrator.")
            return False, None
        
        logger.warning(f"❌ Invalid credentials for: {username}")
        st.error(f"Invalid credentials. {attempts_left} attempts remaining.")
        return False, None
        
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        return False, None


def process_login_user(user, df):
    """Process a successful login"""
    try:
        role = user.iloc[0]["role"]
        branch_id = user.iloc[0].get("branch_id", "HO")
        full_name = user.iloc[0].get("full_name", user.iloc[0]["username"])
        mobile_enabled = user.iloc[0].get("mobile_enabled", True)
        whatsapp = user.iloc[0].get("whatsapp", "")
        
        # Cashier shift check
        if role == "cashier":
            can_login, active_shift = can_cashier_login(user.iloc[0]["username"])
            if not can_login:
                st.error("No active shift assigned. Please ask your manager to start a shift.")
                return False, None
            
            st.session_state.active_shift_id = active_shift.get("shift_id")
            st.session_state.active_shift_branch = active_shift.get("branch_id", branch_id)
            st.session_state.active_shift_branch_name = active_shift.get("branch_name", "")
        
        # Store user info in session
        st.session_state.user_full_name = full_name
        st.session_state.user_branch = branch_id
        st.session_state.mobile_enabled = mobile_enabled
        st.session_state.whatsapp_number = whatsapp if whatsapp else None
        st.session_state.mobile_mode = False
        
        # Update last login
        idx = user.index[0]
        if "last_login" not in df.columns:
            df["last_login"] = None
        df.loc[idx, "last_login"] = datetime.now().isoformat()
        save_users(df)
        
        logger.info(f"✅ Login processed successfully for: {user.iloc[0]['username']}")
        return True, role
        
    except Exception as e:
        logger.error(f"❌ Error processing login: {e}")
        return False, None


def check_mobile_login(username, password):
    """Check login specifically for mobile access"""
    try:
        df = load_users()
        
        if df.empty:
            return False, None, "No users found"
        
        if "active" not in df.columns:
            df["active"] = True
            save_users(df)
        
        if "mobile_enabled" not in df.columns:
            df["mobile_enabled"] = True
            save_users(df)
        
        hashed = hash_password(password)
        
        # Try hashed password
        user = df[
            (df["username"] == username) &
            (df["password"] == hashed) &
            (df["active"] == True) &
            (df["mobile_enabled"] == True)
        ]
        
        # If hashed fails, try plain text
        if user.empty:
            user = df[
                (df["username"] == username) &
                (df["password"] == password) &
                (df["active"] == True) &
                (df["mobile_enabled"] == True)
            ]
            if not user.empty:
                # Update to hashed password
                try:
                    idx = user.index[0]
                    df.loc[idx, "password"] = hashed
                    save_users(df)
                except:
                    pass
        
        if not user.empty:
            role = user.iloc[0]["role"]
            
            if not can_use_mobile(role):
                return False, None, "Mobile access not enabled for this role"
            
            branch_id = user.iloc[0].get("branch_id", "HO")
            full_name = user.iloc[0].get("full_name", user.iloc[0]["username"])
            whatsapp = user.iloc[0].get("whatsapp", "")
            
            idx = user.index[0]
            df.loc[idx, "last_mobile_login"] = datetime.now().isoformat()
            save_users(df)
            
            st.session_state.user_full_name = full_name
            st.session_state.user_branch = branch_id
            st.session_state.whatsapp_number = whatsapp if whatsapp else None
            st.session_state.mobile_mode = True
            
            return True, role, "Mobile login successful"
        
        return False, None, "Invalid credentials or mobile access disabled"
        
    except Exception as e:
        logger.error(f"❌ Mobile login error: {e}")
        return False, None, f"Login error: {str(e)}"


# ==============================
# USER MANAGEMENT FUNCTIONS
# ==============================

def get_all_users():
    """Get all users (owner only)"""
    return load_users()


def create_user(username, password, role, branch_id="HO", full_name="", phone="", 
                mobile_enabled=True, whatsapp="", receive_alerts=True):
    """Create a new user with mobile support (owner only)"""
    try:
        df = load_users()
        
        if username in df["username"].values:
            return False, "Username already exists"
        
        # Validate password strength
        is_valid, msg = validate_password_strength(password)
        if not is_valid:
            return False, f"Password too weak: {msg}"
        
        standardized_phone = ""
        if phone:
            valid, standardized_phone, msg = validate_zimbabwe_phone(phone)
            if not valid:
                return False, msg
        
        standardized_whatsapp = ""
        if whatsapp:
            valid, standardized_whatsapp, msg = validate_zimbabwe_phone(whatsapp)
            if not valid:
                return False, f"WhatsApp: {msg}"
        
        new_user = pd.DataFrame([{
            "username": username,
            "password": hash_password(password),
            "role": role,
            "branch_id": branch_id,
            "full_name": full_name if full_name else username,
            "phone": standardized_phone,
            "active": True,
            "mobile_enabled": mobile_enabled,
            "whatsapp": standardized_whatsapp,
            "receive_alerts": receive_alerts,
            "last_login": None,
            "last_mobile_login": None,
            "device_info": "",
            "two_factor_enabled": False,
            "session_token": ""
        }])
        
        df = pd.concat([df, new_user], ignore_index=True)
        save_users(df)
        return True, "User created successfully"
        
    except Exception as e:
        logger.error(f"❌ Error creating user: {e}")
        return False, f"Error creating user: {str(e)}"


def update_user(username, **kwargs):
    """Update user details (owner only)"""
    try:
        df = load_users()
        
        if username not in df["username"].values:
            return False, "User not found"
        
        idx = df[df["username"] == username].index[0]
        
        if "phone" in kwargs and kwargs["phone"]:
            valid, standardized, msg = validate_zimbabwe_phone(kwargs["phone"])
            if not valid:
                return False, msg
            kwargs["phone"] = standardized
        
        if "whatsapp" in kwargs and kwargs["whatsapp"]:
            valid, standardized, msg = validate_zimbabwe_phone(kwargs["whatsapp"])
            if not valid:
                return False, f"WhatsApp: {msg}"
            kwargs["whatsapp"] = standardized
        
        # If password is being updated, hash it
        if "password" in kwargs and kwargs["password"]:
            # Validate new password strength
            is_valid, msg = validate_password_strength(kwargs["password"])
            if not is_valid:
                return False, f"Password too weak: {msg}"
            kwargs["password"] = hash_password(kwargs["password"])
        
        for key, value in kwargs.items():
            if key in df.columns:
                df.loc[idx, key] = value
        
        save_users(df)
        return True, "User updated successfully"
        
    except Exception as e:
        logger.error(f"❌ Error updating user: {e}")
        return False, f"Error updating user: {str(e)}"


def delete_user(username):
    """Delete or deactivate user (owner only)"""
    try:
        df = load_users()
        
        if username == "admin":
            return False, "Cannot delete admin user"
        
        if username not in df["username"].values:
            return False, "User not found"
        
        df = df[df["username"] != username]
        save_users(df)
        return True, "User deleted"
        
    except Exception as e:
        logger.error(f"❌ Error deleting user: {e}")
        return False, f"Error deleting user: {str(e)}"


def toggle_user_active(username):
    """Activate/deactivate user"""
    try:
        df = load_users()
        
        if username not in df["username"].values:
            return False
        
        idx = df[df["username"] == username].index[0]
        df.loc[idx, "active"] = not df.loc[idx, "active"]
        save_users(df)
        return True
        
    except Exception as e:
        logger.error(f"❌ Error toggling user active: {e}")
        return False


def toggle_mobile_access(username):
    """Enable/disable mobile access for a user"""
    try:
        df = load_users()
        
        if username not in df["username"].values:
            return False
        
        idx = df[df["username"] == username].index[0]
        df.loc[idx, "mobile_enabled"] = not df.loc[idx, "mobile_enabled"]
        save_users(df)
        return True
        
    except Exception as e:
        logger.error(f"❌ Error toggling mobile access: {e}")
        return False


def get_users_by_role(role):
    """Get all users with a specific role"""
    df = load_users()
    return df[df["role"] == role]


def get_mobile_users():
    """Get all users with mobile access enabled"""
    df = load_users()
    if "mobile_enabled" in df.columns:
        return df[df["mobile_enabled"] == True]
    return df


def get_users_for_whatsapp_alerts():
    """Get users who should receive WhatsApp alerts"""
    df = load_users()
    if "receive_alerts" in df.columns and "whatsapp" in df.columns:
        return df[(df["receive_alerts"] == True) & (df["whatsapp"] != "") & (df["whatsapp"].notna())]
    return pd.DataFrame()


# ==============================
# PASSWORD RESET FUNCTIONS
# ==============================

def reset_password(username, new_password):
    """Reset user password (admin only)"""
    try:
        df = load_users()
        
        if username not in df["username"].values:
            return False, "User not found"
        
        # Validate new password
        is_valid, msg = validate_password_strength(new_password)
        if not is_valid:
            return False, f"Password too weak: {msg}"
        
        idx = df[df["username"] == username].index[0]
        df.loc[idx, "password"] = hash_password(new_password)
        save_users(df)
        
        return True, "Password reset successfully"
        
    except Exception as e:
        logger.error(f"❌ Error resetting password: {e}")
        return False, f"Error resetting password: {str(e)}"


def force_reset_password(username):
    """Force password reset for a user (admin only)"""
    try:
        df = load_users()
        
        if username not in df["username"].values:
            return False, "User not found"
        
        # Generate a temporary password
        temp_password = generate_strong_password(12)
        
        idx = df[df["username"] == username].index[0]
        df.loc[idx, "password"] = hash_password(temp_password)
        save_users(df)
        
        return True, f"Password reset. Temporary password: {temp_password}"
        
    except Exception as e:
        logger.error(f"❌ Error forcing password reset: {e}")
        return False, f"Error resetting password: {str(e)}"


# ==============================
# SESSION SECURITY FUNCTIONS
# ==============================

def validate_session(username, session_token):
    """Validate a session token"""
    df = load_users()
    user = df[df["username"] == username]
    if not user.empty:
        stored_token = user.iloc[0].get("session_token", "")
        return stored_token == session_token
    return False


def end_all_sessions(username):
    """End all sessions for a user (admin only)"""
    try:
        df = load_users()
        idx = df[df["username"] == username].index
        if len(idx) > 0:
            df.loc[idx[0], "session_token"] = ""
            save_users(df)
            return True
        return False
    except Exception as e:
        logger.error(f"❌ Error ending sessions: {e}")
        return False


def is_account_locked(username):
    """Check if an account is locked"""
    if username in _login_lockout:
        if time.time() < _login_lockout[username]:
            remaining = int(_login_lockout[username] - time.time())
            return True, remaining
        else:
            del _login_lockout[username]
            _login_attempts[username] = 0
    return False, 0


def unlock_account(username):
    """Unlock a locked account (admin only)"""
    if username in _login_lockout:
        del _login_lockout[username]
        _login_attempts[username] = 0
        return True, "Account unlocked"
    return False, "Account not locked"


# ==============================
# MOBILE AUTHENTICATION HELPERS
# ==============================

def generate_mobile_session_token(username):
    """Generate a session token for mobile authentication"""
    import secrets
    token = secrets.token_urlsafe(32)
    
    df = load_users()
    idx = df[df["username"] == username].index
    if len(idx) > 0:
        df.loc[idx[0], "session_token"] = token
        save_users(df)
    
    return token


def verify_mobile_session_token(username, token):
    """Verify a mobile session token"""
    df = load_users()
    user = df[df["username"] == username]
    if not user.empty:
        stored_token = user.iloc[0].get("session_token", "")
        return stored_token == token
    return False


def revoke_mobile_session(username):
    """Revoke mobile session for a user"""
    df = load_users()
    idx = df[df["username"] == username].index
    if len(idx) > 0:
        df.loc[idx[0], "session_token"] = ""
        save_users(df)
        return True
    return False


# ==============================
# ROLE HELPERS
# ==============================

def get_role_color(role):
    """Get color for role badge"""
    colors = {
        "owner": "#FF6B6B",
        "manager": "#4ECDC4",
        "cashier": "#45B7D1",
        "viewer": "#96CEB4",
        "mobile_user": "#FFEAA7"
    }
    return colors.get(role, "#666666")


def get_role_icon(role):
    """Get icon for role badge"""
    icons = {
        "owner": "👑",
        "manager": "📊",
        "cashier": "🛒",
        "viewer": "👁️",
        "mobile_user": "📱"
    }
    return icons.get(role, "👤")


def get_role_description(role):
    """Get description for role"""
    return ROLES.get(role, {}).get("description", "No description")


# ==============================
# EXPORT FUNCTIONS
# ==============================

def export_users_to_csv():
    """Export users to CSV for backup"""
    df = load_users()
    if "password" in df.columns:
        df = df.drop(columns=["password"])
    return df.to_csv(index=False).encode("utf-8")


def import_users_from_csv(csv_data):
    """Import users from CSV (owner only)"""
    try:
        df = pd.read_csv(csv_data)
        if "password" not in df.columns:
            return False, "CSV must contain password column"
        
        for idx, row in df.iterrows():
            if len(row["password"]) != 64:  # Not already hashed
                df.loc[idx, "password"] = hash_password(row["password"])
        
        save_users(df)
        return True, "Users imported successfully"
    except Exception as e:
        return False, f"Import failed: {str(e)}"