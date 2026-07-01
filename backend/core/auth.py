# backend/core/auth.py - COMPLETE FIXED VERSION WITH BRANCH-LEVEL SHIFT SUPPORT
import pandas as pd
import streamlit as st
from backend.core.db_adapter import load_users, save_users
from backend.utils.utils import hash_password
from backend.utils.phone_utils import validate_zimbabwe_phone
from backend.modules.shift_manager import can_cashier_login, get_active_shift_for_branch
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
# SESSION STATE INITIALIZATION
# ==============================
def init_auth_session_state():
    """Initialize auth-related session state variables"""
    if "auth_initialized" not in st.session_state:
        st.session_state.auth_initialized = False
    if "auth_users_loaded" not in st.session_state:
        st.session_state.auth_users_loaded = False
    if "auth_last_check" not in st.session_state:
        st.session_state.auth_last_check = None
    if "active_shift_id" not in st.session_state:
        st.session_state.active_shift_id = None
    if "active_shift_branch" not in st.session_state:
        st.session_state.active_shift_branch = None
    if "active_shift_branch_name" not in st.session_state:
        st.session_state.active_shift_branch_name = None
    if "shift_started_by" not in st.session_state:
        st.session_state.shift_started_by = None


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
    if role == "owner":
        return True
    
    feature_permissions = {
        "pos": ["cashier", "manager", "owner"],
        "inventory_view": ["cashier", "manager", "owner", "mobile_user"],
        "inventory_edit": ["manager", "owner"],
        "sales_history": ["cashier", "manager", "owner", "mobile_user"],
        "sales_dashboard": ["manager", "owner"],
        "purchases": ["manager", "owner"],
        "expenses": ["manager", "owner"],
        "income": ["manager", "owner"],
        "pl": ["manager", "owner"],
        "cash_dashboard": ["manager", "owner"],
        "customers": ["cashier", "manager", "owner"],
        "debtors": ["manager", "owner"],
        "debtors_dashboard": ["manager", "owner"],
        "customer_app": ["owner", "manager", "cashier", "viewer", "mobile_user"],
        "customer_insights": ["manager", "owner"],
        "customer_360": ["manager", "owner"],
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
        "settings": ["owner"],
        "user_management": ["owner"],
        "branch_management": ["owner"],
        "shift_management": ["manager", "owner"],
        "branch_performance": ["manager", "owner"],
        "mobile_dashboard": ["owner", "manager", "cashier", "mobile_user"],
        "whatsapp_alerts": ["owner", "manager"],
        "receive_notifications": ["owner", "manager", "mobile_user"],
        "mobile_approvals": ["owner", "manager"]
    }
    
    allowed_roles = feature_permissions.get(feature, [])
    return role in allowed_roles


def can_use_mobile(role):
    return ROLES.get(role, {}).get("mobile_access", False)


def get_role_icon(role):
    return ROLES.get(role, {}).get("icon", "👤")


def get_role_color(role):
    return ROLES.get(role, {}).get("color", "#666666")


def can_start_shift(role):
    """Check if a user can start a shift (manager, admin, owner)"""
    return role in ["owner", "manager", "admin"]


# ==============================
# PASSWORD STRENGTH VALIDATION
# ==============================

def validate_password_strength(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    return True, "Password is strong"


def generate_strong_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    return ''.join(secrets.choice(alphabet) for i in range(length))


def get_password_strength_score(password):
    score = 0
    if len(password) >= 12:
        score += 25
    elif len(password) >= 8:
        score += 15
    else:
        score += 5
    if re.search(r'[A-Z]', password):
        score += 15
    if re.search(r'[a-z]', password):
        score += 15
    if re.search(r'[0-9]', password):
        score += 15
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 20
    if len(set(password)) > len(password) * 0.7:
        score += 10
    return min(score, 100)


# ==============================
# INIT USERS - WITH PLAIN TEXT SUPPORT
# ==============================

def create_default_users():
    """Create default users list with PLAIN TEXT passwords (temporary)"""
    return pd.DataFrame([
        {
            "username": "admin",
            "password": "admin123",  # Plain text for testing
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
            "password": "manager123",  # Plain text for testing
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
            "password": "cash123",  # Plain text for testing
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


def init_users():
    """Initialize default users if none exist - with loop prevention"""
    try:
        # Check if already initialized
        if st.session_state.get("auth_initialized", False):
            logger.info("✅ Users already initialized in this session, skipping...")
            return load_users()
        
        logger.info("Initializing users...")
        df = load_users()
        
        if df.empty:
            logger.info("No users found. Creating default users...")
            default_users = create_default_users()
            save_users(default_users)
            logger.info("✅ Default users created successfully!")
            st.session_state.auth_initialized = True
            return default_users
        
        if "admin" in df["username"].values:
            logger.info("✅ Users already exist. Found admin user.")
            st.session_state.auth_initialized = True
            return df
        
        logger.info("No admin user found. Adding default users...")
        default_users = create_default_users()
        combined_df = pd.concat([df, default_users], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=["username"], keep="last")
        save_users(combined_df)
        logger.info("✅ Default users added successfully!")
        st.session_state.auth_initialized = True
        return combined_df
        
    except Exception as e:
        logger.error(f"❌ Error initializing users: {e}")
        return pd.DataFrame()


# ==============================
# LOGIN FUNCTIONS - SUPPORTS BOTH PLAIN AND HASHED
# ==============================

def check_login(username, password):
    """
    Standard login check with rate limiting.
    Supports both plain text and hashed passwords.
    """
    try:
        logger.info(f"Login attempt for user: {username}")
        
        # Initialize session state
        init_auth_session_state()
        
        # Load users
        df = load_users()
        
        # If no users, initialize them
        if df.empty:
            logger.warning("No users found! Creating default users...")
            if not st.session_state.get("auth_initialized", False):
                df = init_users()
            else:
                logger.error("Users already initialized but still empty!")
                return False, None
            
            if df.empty:
                logger.error("Failed to create users!")
                return False, None
        
        # Ensure required columns exist
        if "active" not in df.columns:
            df["active"] = True
            save_users(df)
        
        # Try plain text first (for new users or plain text passwords)
        user = df[
            (df["username"] == username) &
            (df["password"] == password) &
            (df["active"] == True)
        ]
        
        if not user.empty:
            logger.info(f"✅ Login successful (plain text) for: {username}")
            # Convert to hashed password for security
            try:
                hashed = hash_password(password)
                idx = user.index[0]
                df.loc[idx, "password"] = hashed
                save_users(df)
                logger.info(f"✅ Updated password to hashed for: {username}")
            except Exception as e:
                logger.warning(f"Could not update to hashed password: {e}")
            return process_login_user(user, df)
        
        # Try hashed password (for existing users)
        hashed = hash_password(password)
        user = df[
            (df["username"] == username) &
            (df["password"] == hashed) &
            (df["active"] == True)
        ]
        
        if not user.empty:
            logger.info(f"✅ Login successful (hashed) for: {username}")
            return process_login_user(user, df)
        
        # Check if user exists but inactive
        inactive_user = df[
            (df["username"] == username) &
            (df["active"] == False)
        ]
        
        if not inactive_user.empty:
            logger.warning(f"❌ Login blocked - user inactive: {username}")
            st.error("User account is deactivated. Please contact administrator.")
            return False, None
        
        # Check if user exists but password doesn't match
        user_exists = df[df["username"] == username]
        if not user_exists.empty:
            logger.warning(f"❌ Invalid password for: {username}")
            # Increment attempts
            _login_attempts[username] += 1
            attempts_left = _MAX_ATTEMPTS - _login_attempts[username]
            
            if _login_attempts[username] >= _MAX_ATTEMPTS:
                _login_lockout[username] = time.time() + _LOCKOUT_TIME
                st.error(f"Too many failed attempts. Account locked for 5 minutes.")
                return False, None
            
            st.error(f"Invalid credentials. {attempts_left} attempts remaining.")
            return False, None
        
        # User doesn't exist
        logger.warning(f"❌ User not found: {username}")
        st.error("User not found. Please check your username.")
        return False, None
        
    except Exception as e:
        logger.error(f"❌ Login error: {e}")
        st.error(f"Login error: {str(e)}")
        return False, None


def process_login_user(user, df):
    """Process a successful login"""
    try:
        role = user.iloc[0]["role"]
        branch_id = user.iloc[0].get("branch_id", "HO")
        full_name = user.iloc[0].get("full_name", user.iloc[0]["username"])
        mobile_enabled = user.iloc[0].get("mobile_enabled", True)
        whatsapp = user.iloc[0].get("whatsapp", "")
        
        # ============================================================
        # SHIFT CHECK - BRANCH LEVEL (FIXED)
        # ============================================================
        if role == "cashier":
            # Check if there's an active shift in the user's branch
            can_login, active_shift = can_cashier_login(user.iloc[0]["username"])
            
            if not can_login:
                st.error("❌ No active shift in your branch. Please ask your manager to start a shift.")
                return False, None
            
            # Store shift information in session
            st.session_state.active_shift_id = active_shift.get("shift_id")
            st.session_state.active_shift_branch = active_shift.get("branch_id", branch_id)
            st.session_state.active_shift_branch_name = active_shift.get("branch_name", "")
            st.session_state.shift_started_by = active_shift.get("cashier_name", "Unknown")
            
            logger.info(f"✅ Cashier {username} logged in under branch shift {active_shift.get('shift_id')}")
        
        # For non-cashier roles, check if they can start a shift
        elif can_start_shift(role):
            # Check if there's an active shift in this branch
            active_shift = get_active_shift_for_branch(branch_id)
            
            if active_shift:
                # Store the existing shift info
                st.session_state.active_shift_id = active_shift.get("shift_id")
                st.session_state.active_shift_branch = active_shift.get("branch_id", branch_id)
                st.session_state.active_shift_branch_name = active_shift.get("branch_name", "")
                st.session_state.shift_started_by = active_shift.get("cashier_name", "Unknown")
                
                logger.info(f"✅ Manager/Owner {username} logged in - branch shift {active_shift.get('shift_id')} is active")
            else:
                # No active shift - clear any stale shift data
                st.session_state.active_shift_id = None
                st.session_state.active_shift_branch = None
                st.session_state.active_shift_branch_name = None
                st.session_state.shift_started_by = None
                
                logger.info(f"ℹ️ No active shift in branch {branch_id}")
        
        # Store user info in session
        st.session_state.user_full_name = full_name
        st.session_state.user_branch = branch_id
        st.session_state.mobile_enabled = mobile_enabled
        st.session_state.whatsapp_number = whatsapp if whatsapp else None
        st.session_state.mobile_mode = False
        st.session_state.user_role = role
        
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
        
        # Try plain text first
        user = df[
            (df["username"] == username) &
            (df["password"] == password) &
            (df["active"] == True) &
            (df["mobile_enabled"] == True)
        ]
        
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
        
        # Try hashed password
        hashed = hash_password(password)
        user = df[
            (df["username"] == username) &
            (df["password"] == hashed) &
            (df["active"] == True) &
            (df["mobile_enabled"] == True)
        ]
        
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
    return load_users()


def create_user(username, password, role, branch_id="HO", full_name="", phone="", 
                mobile_enabled=True, whatsapp="", receive_alerts=True):
    try:
        df = load_users()
        
        if username in df["username"].values:
            return False, "Username already exists"
        
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
            "password": hash_password(password),  # Hash new passwords
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
        
        if "password" in kwargs and kwargs["password"]:
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
    df = load_users()
    return df[df["role"] == role]


def get_mobile_users():
    df = load_users()
    if "mobile_enabled" in df.columns:
        return df[df["mobile_enabled"] == True]
    return df


def get_users_for_whatsapp_alerts():
    df = load_users()
    if "receive_alerts" in df.columns and "whatsapp" in df.columns:
        return df[(df["receive_alerts"] == True) & (df["whatsapp"] != "") & (df["whatsapp"].notna())]
    return pd.DataFrame()


# ==============================
# PASSWORD RESET FUNCTIONS
# ==============================

def reset_password(username, new_password):
    try:
        df = load_users()
        
        if username not in df["username"].values:
            return False, "User not found"
        
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
    try:
        df = load_users()
        
        if username not in df["username"].values:
            return False, "User not found"
        
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
    df = load_users()
    user = df[df["username"] == username]
    if not user.empty:
        stored_token = user.iloc[0].get("session_token", "")
        return stored_token == session_token
    return False


def end_all_sessions(username):
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
    if username in _login_lockout:
        if time.time() < _login_lockout[username]:
            remaining = int(_login_lockout[username] - time.time())
            return True, remaining
        else:
            del _login_lockout[username]
            _login_attempts[username] = 0
    return False, 0


def unlock_account(username):
    if username in _login_lockout:
        del _login_lockout[username]
        _login_attempts[username] = 0
        return True, "Account unlocked"
    return False, "Account not locked"


# ==============================
# SHIFT HELPER FUNCTIONS
# ==============================

def get_current_shift_status():
    """Get current shift status for the logged-in user's branch"""
    branch_id = st.session_state.get("user_branch", "HO")
    active_shift = get_active_shift_for_branch(branch_id)
    
    if active_shift:
        return {
            "active": True,
            "shift_id": active_shift.get("shift_id"),
            "started_by": active_shift.get("cashier_name", "Unknown"),
            "start_time": active_shift.get("start_time"),
            "branch_name": active_shift.get("branch_name", ""),
            "opening_cash": active_shift.get("opening_cash", 0)
        }
    else:
        return {
            "active": False,
            "shift_id": None,
            "started_by": None,
            "start_time": None,
            "branch_name": None,
            "opening_cash": 0
        }


def clear_shift_session():
    """Clear shift-related session data"""
    st.session_state.active_shift_id = None
    st.session_state.active_shift_branch = None
    st.session_state.active_shift_branch_name = None
    st.session_state.shift_started_by = None


# ==============================
# MOBILE AUTHENTICATION HELPERS
# ==============================

def generate_mobile_session_token(username):
    token = secrets.token_urlsafe(32)
    df = load_users()
    idx = df[df["username"] == username].index
    if len(idx) > 0:
        df.loc[idx[0], "session_token"] = token
        save_users(df)
    return token


def verify_mobile_session_token(username, token):
    df = load_users()
    user = df[df["username"] == username]
    if not user.empty:
        stored_token = user.iloc[0].get("session_token", "")
        return stored_token == token
    return False


def revoke_mobile_session(username):
    df = load_users()
    idx = df[df["username"] == username].index
    if len(idx) > 0:
        df.loc[idx[0], "session_token"] = ""
        save_users(df)
        return True
    return False


# ==============================
# EXPORT FUNCTIONS
# ==============================

def export_users_to_csv():
    df = load_users()
    if "password" in df.columns:
        df = df.drop(columns=["password"])
    return df.to_csv(index=False).encode("utf-8")


def import_users_from_csv(csv_data):
    try:
        df = pd.read_csv(csv_data)
        if "password" not in df.columns:
            return False, "CSV must contain password column"
        
        for idx, row in df.iterrows():
            # Hash passwords if not already hashed
            if len(row["password"]) != 64:
                df.loc[idx, "password"] = hash_password(row["password"])
        
        save_users(df)
        return True, "Users imported successfully"
    except Exception as e:
        return False, f"Import failed: {str(e)}"


# ==============================
# AUTO-INITIALIZE ON IMPORT
# ==============================
init_auth_session_state()


# ==============================
# ROLE HELPERS
# ==============================

def get_role_description(role):
    return ROLES.get(role, {}).get("description", "No description")


def is_authorized_to_start_shift(role):
    """Check if user role can start a shift"""
    return can_start_shift(role)