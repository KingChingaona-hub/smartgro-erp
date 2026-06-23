# backend/core/auth.py
import pandas as pd
import streamlit as st
from backend.core.db_adapter import load_users, save_users
from backend.utils.utils import hash_password
from backend.utils.phone_utils import validate_zimbabwe_phone
from backend.modules.shift_manager import can_cashier_login

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
# INIT USERS - PostgreSQL VERSION
# ==============================

def init_users():
    """Initialize default users if none exist - PostgreSQL version"""
    df = load_users()
    
    # Check if users exist
    if not df.empty:
        # Users already exist, check if we have at least one admin
        if "admin" in df["username"].values:
            return df
    
    # Create default users
    default_users = [
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
    ]
    
    # Create DataFrame from defaults
    default_df = pd.DataFrame(default_users)
    
    # Combine with existing if any
    if df.empty:
        combined_df = default_df
    else:
        combined_df = pd.concat([df, default_df], ignore_index=True)
        # Remove duplicates keeping the last (defaults take precedence)
        combined_df = combined_df.drop_duplicates(subset=["username"], keep="last")
    
    # Save to database
    save_users(combined_df)
    
    return combined_df


# ==============================
# LOGIN FUNCTIONS
# ==============================

def check_login(username, password):
    """Standard login check with mobile support"""
    df = load_users()
    
    hashed = hash_password(password)
    
    if "active" not in df.columns:
        df["active"] = True
        save_users(df)
    
    user = df[
        (df["username"] == username) &
        (df["password"] == hashed) &
        (df["active"] == True)
    ]
    
    if not user.empty:
        role = user.iloc[0]["role"]
        branch_id = user.iloc[0].get("branch_id", "HO")
        full_name = user.iloc[0].get("full_name", username)
        mobile_enabled = user.iloc[0].get("mobile_enabled", True)
        whatsapp = user.iloc[0].get("whatsapp", "")
        
        # Cashier shift check
        if role == "cashier":
            can_login, active_shift = can_cashier_login(username)
            if not can_login:
                st.error("❌ No active shift assigned. Please ask your manager to start a shift.")
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
            df["last_login"] = ""
        df.loc[idx, "last_login"] = datetime.now().isoformat()
        save_users(df)
        
        return True, role
    
    return False, None


def check_mobile_login(username, password):
    """Check login specifically for mobile access"""
    df = load_users()
    
    hashed = hash_password(password)
    
    if "active" not in df.columns:
        df["active"] = True
        save_users(df)
    
    if "mobile_enabled" not in df.columns:
        df["mobile_enabled"] = True
        save_users(df)
    
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
        full_name = user.iloc[0].get("full_name", username)
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


# ==============================
# USER MANAGEMENT FUNCTIONS
# ==============================

def get_all_users():
    """Get all users (owner only)"""
    return load_users()


def create_user(username, password, role, branch_id="HO", full_name="", phone="", 
                mobile_enabled=True, whatsapp="", receive_alerts=True):
    """Create a new user with mobile support (owner only)"""
    df = load_users()
    
    if username in df["username"].values:
        return False, "Username already exists"
    
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
        "last_login": "",
        "last_mobile_login": "",
        "device_info": "",
        "two_factor_enabled": False,
        "session_token": ""
    }])
    
    df = pd.concat([df, new_user], ignore_index=True)
    save_users(df)
    return True, "User created successfully"


def update_user(username, **kwargs):
    """Update user details (owner only)"""
    df = load_users()
    
    if username not in df["username"].values:
        return False
    
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
    
    for key, value in kwargs.items():
        if key in df.columns:
            df.loc[idx, key] = value
    
    save_users(df)
    return True, "User updated successfully"


def delete_user(username):
    """Delete or deactivate user (owner only)"""
    df = load_users()
    
    if username == "admin":
        return False, "Cannot delete admin user"
    
    if username not in df["username"].values:
        return False, "User not found"
    
    df = df[df["username"] != username]
    save_users(df)
    return True, "User deleted"


def toggle_user_active(username):
    """Activate/deactivate user"""
    df = load_users()
    
    if username not in df["username"].values:
        return False
    
    idx = df[df["username"] == username].index[0]
    df.loc[idx, "active"] = not df.loc[idx, "active"]
    save_users(df)
    return True


def toggle_mobile_access(username):
    """Enable/disable mobile access for a user"""
    df = load_users()
    
    if username not in df["username"].values:
        return False
    
    idx = df[df["username"] == username].index[0]
    df.loc[idx, "mobile_enabled"] = not df.loc[idx, "mobile_enabled"]
    save_users(df)
    return True


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
            if len(row["password"]) != 64:
                df.loc[idx, "password"] = hash_password(row["password"])
        
        save_users(df)
        return True, "Users imported successfully"
    except Exception as e:
        return False, f"Import failed: {str(e)}"


# Import datetime for login functions
from datetime import datetime