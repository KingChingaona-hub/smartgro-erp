import streamlit as st
import pandas as pd
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
import json
import re

from backend.utils.phone_utils import validate_zimbabwe_phone, get_whatsapp_link
from backend.utils.utils import hash_password
from backend.core.db_adapter import load_users, save_users

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
AUDIT_LOG_FILE = DATA_DIR / "audit_log.csv"
TWOFA_FILE = DATA_DIR / "twofa_codes.csv"
SESSION_FILE = DATA_DIR / "active_sessions.csv"
IP_WHITELIST_FILE = DATA_DIR / "ip_whitelist.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_security_files():
    """Initialize security-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Audit log file
    if not AUDIT_LOG_FILE.exists():
        df = pd.DataFrame(columns=[
            "timestamp", "user", "action", "details", "ip_address", "branch", "status"
        ])
        df.to_csv(AUDIT_LOG_FILE, index=False)
    
    # 2FA codes file
    if not TWOFA_FILE.exists():
        df = pd.DataFrame(columns=[
            "user", "code", "expiry", "verified", "phone"
        ])
        df.to_csv(TWOFA_FILE, index=False)
    
    # Active sessions file
    if not SESSION_FILE.exists():
        df = pd.DataFrame(columns=[
            "session_id", "user", "login_time", "last_activity", "ip_address", "device_info", "active"
        ])
        df.to_csv(SESSION_FILE, index=False)
    
    # IP whitelist file
    if not IP_WHITELIST_FILE.exists():
        df = pd.DataFrame(columns=[
            "ip_address", "description", "added_by", "added_date", "active"
        ])
        df.to_csv(IP_WHITELIST_FILE, index=False)


# ==============================
# AUDIT LOG FUNCTIONS
# ==============================
def log_audit(user, action, details="", ip_address="", branch="", status="SUCCESS"):
    """Log an audit event"""
    init_security_files()
    
    df = pd.read_csv(AUDIT_LOG_FILE)
    
    new_entry = pd.DataFrame([{
        "timestamp": datetime.now().isoformat(),
        "user": user,
        "action": action,
        "details": details,
        "ip_address": ip_address,
        "branch": branch,
        "status": status
    }])
    
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(AUDIT_LOG_FILE, index=False)
    
    return True


def get_audit_log(days=30, user=None, action=None):
    """Get audit log entries - FIXED datetime parsing"""
    init_security_files()
    
    df = pd.read_csv(AUDIT_LOG_FILE)
    
    if df.empty:
        return df
    
    # Fix: Handle ISO8601 format properly
    try:
        # Try parsing with ISO8601 format (handles 'T' separator)
        df["timestamp"] = pd.to_datetime(df["timestamp"], format='ISO8601', errors='coerce')
    except Exception:
        try:
            # Try mixed format parsing
            df["timestamp"] = pd.to_datetime(df["timestamp"], format='mixed', errors='coerce')
        except Exception:
            try:
                # Fallback to default parsing
                df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
            except Exception:
                pass
    
    # Drop rows with invalid timestamps
    df = df.dropna(subset=["timestamp"])
    
    if df.empty:
        return df
    
    # Filter by days
    cutoff = datetime.now() - timedelta(days=days)
    df = df[df["timestamp"] >= cutoff]
    
    # Filter by user
    if user:
        df = df[df["user"] == user]
    
    # Filter by action
    if action:
        df = df[df["action"] == action]
    
    return df.sort_values("timestamp", ascending=False)


def get_user_activity_summary(user=None, days=30):
    """Get summary of user activities"""
    df = get_audit_log(days, user)
    
    if df.empty:
        return {
            "total_actions": 0,
            "successful": 0,
            "failed": 0,
            "unique_actions": 0,
            "action_breakdown": {}
        }
    
    summary = {
        "total_actions": len(df),
        "successful": len(df[df["status"] == "SUCCESS"]),
        "failed": len(df[df["status"] == "FAILED"]),
        "unique_actions": df["action"].nunique(),
        "action_breakdown": df["action"].value_counts().to_dict()
    }
    
    return summary


# ==============================
# TWO-FACTOR AUTHENTICATION
# ==============================
def generate_2fa_code():
    """Generate a 6-digit 2FA code"""
    return f"{secrets.randbelow(1000000):06d}"


def send_2fa_via_whatsapp(phone, code):
    """Send 2FA code via WhatsApp"""
    message = f"""🔐 *AZIEL INVESTMENTS - SECURITY CODE*

Your verification code is:

*{code}*

This code will expire in 5 minutes.

If you didn't request this, please ignore this message.

*Do not share this code with anyone!*

- Aziel Investments Security Team
"""
    return get_whatsapp_link(phone, message)


def send_2fa_via_sms(phone, code):
    """Send 2FA code via SMS (placeholder - requires SMS gateway)"""
    # This would integrate with an SMS gateway
    # For now, return WhatsApp link as fallback
    return send_2fa_via_whatsapp(phone, code)


def create_2fa_code(username, phone):
    """Create and send a 2FA code"""
    init_security_files()
    
    # Generate code
    code = generate_2fa_code()
    expiry = (datetime.now() + timedelta(minutes=5)).isoformat()
    
    # Store code
    df = pd.read_csv(TWOFA_FILE)
    
    # Remove old codes for this user
    df = df[df["user"] != username]
    
    new_code = pd.DataFrame([{
        "user": username,
        "code": code,
        "expiry": expiry,
        "verified": False,
        "phone": phone
    }])
    
    df = pd.concat([df, new_code], ignore_index=True)
    df.to_csv(TWOFA_FILE, index=False)
    
    # Send via WhatsApp
    whatsapp_link = send_2fa_via_whatsapp(phone, code)
    
    return whatsapp_link


def verify_2fa_code(username, code):
    """Verify a 2FA code"""
    init_security_files()
    
    df = pd.read_csv(TWOFA_FILE)
    
    # Find active code for user
    user_codes = df[(df["user"] == username) & (df["verified"] == False)]
    
    if user_codes.empty:
        return False, "No active verification code found"
    
    # Check each code
    for idx, row in user_codes.iterrows():
        if str(row["code"]) == str(code).strip():
            # Check expiry
            try:
                expiry = pd.to_datetime(row["expiry"])
                if datetime.now() > expiry:
                    return False, "Code has expired. Please request a new one."
            except:
                pass
            
            # Mark as verified
            df.loc[idx, "verified"] = True
            df.to_csv(TWOFA_FILE, index=False)
            
            return True, "Verification successful"
    
    return False, "Invalid code"


def is_2fa_enabled(username):
    """Check if user has 2FA enabled"""
    users_df = load_users()
    
    user = users_df[users_df["username"] == username]
    
    if not user.empty and "two_factor_enabled" in user.columns:
        return bool(user.iloc[0]["two_factor_enabled"])
    
    return False


def enable_2fa(username, phone):
    """Enable 2FA for a user"""
    users_df = load_users()
    idx = users_df[users_df["username"] == username].index
    
    if len(idx) > 0:
        if "two_factor_enabled" not in users_df.columns:
            users_df["two_factor_enabled"] = False
        if "two_factor_phone" not in users_df.columns:
            users_df["two_factor_phone"] = ""
        
        users_df.loc[idx[0], "two_factor_enabled"] = True
        users_df.loc[idx[0], "two_factor_phone"] = phone
        save_users(users_df)
        
        log_audit(username, "2FA_ENABLED", f"2FA enabled for user {username}")
        return True
    
    return False


def disable_2fa(username):
    """Disable 2FA for a user"""
    users_df = load_users()
    idx = users_df[users_df["username"] == username].index
    
    if len(idx) > 0:
        if "two_factor_enabled" in users_df.columns:
            users_df.loc[idx[0], "two_factor_enabled"] = False
        save_users(users_df)
        
        log_audit(username, "2FA_DISABLED", f"2FA disabled for user {username}")
        return True
    
    return False


# ==============================
# SESSION MANAGEMENT
# ==============================
def create_session(username, ip_address="", device_info=""):
    """Create a new session for logged-in user"""
    init_security_files()
    
    session_id = secrets.token_urlsafe(32)
    
    df = pd.read_csv(SESSION_FILE)
    
    new_session = pd.DataFrame([{
        "session_id": session_id,
        "user": username,
        "login_time": datetime.now().isoformat(),
        "last_activity": datetime.now().isoformat(),
        "ip_address": ip_address,
        "device_info": device_info,
        "active": True
    }])
    
    df = pd.concat([df, new_session], ignore_index=True)
    
    # Clean up old inactive sessions (older than 7 days)
    cutoff = datetime.now() - timedelta(days=7)
    try:
        df["login_time_dt"] = pd.to_datetime(df["login_time"], errors='coerce')
        df = df[(df["login_time_dt"] >= cutoff) | (df["active"] == True)]
        df = df.drop(columns=["login_time_dt"])
    except:
        pass
    
    df.to_csv(SESSION_FILE, index=False)
    
    return session_id


def update_session_activity(session_id):
    """Update last activity time for a session"""
    init_security_files()
    
    df = pd.read_csv(SESSION_FILE)
    idx = df[df["session_id"] == session_id].index
    
    if len(idx) > 0:
        df.loc[idx[0], "last_activity"] = datetime.now().isoformat()
        df.to_csv(SESSION_FILE, index=False)
        return True
    
    return False


def end_session(session_id):
    """End a session (logout)"""
    init_security_files()
    
    df = pd.read_csv(SESSION_FILE)
    idx = df[df["session_id"] == session_id].index
    
    if len(idx) > 0:
        df.loc[idx[0], "active"] = False
        df.to_csv(SESSION_FILE, index=False)
        return True
    
    return False


def get_active_sessions(user=None):
    """Get all active sessions - FIXED datetime parsing"""
    init_security_files()
    
    df = pd.read_csv(SESSION_FILE)
    df = df[df["active"] == True]
    
    if df.empty:
        return df
    
    if user:
        df = df[df["user"] == user]
    
    # Calculate idle time safely
    if not df.empty:
        try:
            df["last_activity"] = pd.to_datetime(df["last_activity"], errors='coerce')
            df["idle_minutes"] = (datetime.now() - df["last_activity"]).dt.total_seconds() / 60
            df["idle_minutes"] = df["idle_minutes"].fillna(0)
        except:
            df["idle_minutes"] = 0
    
    return df


def revoke_all_sessions(user, exclude_current=None):
    """Revoke all sessions for a user"""
    init_security_files()
    
    df = pd.read_csv(SESSION_FILE)
    
    if exclude_current:
        df.loc[(df["user"] == user) & (df["session_id"] != exclude_current), "active"] = False
    else:
        df.loc[df["user"] == user, "active"] = False
    
    df.to_csv(SESSION_FILE, index=False)
    
    log_audit(user, "SESSIONS_REVOKED", f"All sessions revoked for {user}")
    return True


def check_session_timeout(session_id, timeout_minutes=30):
    """Check if session has timed out"""
    df = get_active_sessions()
    session = df[df["session_id"] == session_id]
    
    if not session.empty:
        idle_minutes = session.iloc[0].get("idle_minutes", 0)
        if idle_minutes > timeout_minutes:
            end_session(session_id)
            return True  # Timed out
    
    return False  # Still active


# ==============================
# IP WHITELISTING
# ==============================
def add_ip_to_whitelist(ip_address, description, added_by):
    """Add IP address to whitelist"""
    init_security_files()
    
    df = pd.read_csv(IP_WHITELIST_FILE)
    
    # Check if already exists
    if ip_address in df["ip_address"].values:
        return False, "IP already in whitelist"
    
    new_ip = pd.DataFrame([{
        "ip_address": ip_address,
        "description": description,
        "added_by": added_by,
        "added_date": datetime.now().isoformat(),
        "active": True
    }])
    
    df = pd.concat([df, new_ip], ignore_index=True)
    df.to_csv(IP_WHITELIST_FILE, index=False)
    
    log_audit(added_by, "IP_WHITELIST_ADD", f"Added IP {ip_address} to whitelist")
    return True, "IP added to whitelist"


def remove_ip_from_whitelist(ip_address, removed_by):
    """Remove IP from whitelist"""
    init_security_files()
    
    df = pd.read_csv(IP_WHITELIST_FILE)
    df = df[df["ip_address"] != ip_address]
    df.to_csv(IP_WHITELIST_FILE, index=False)
    
    log_audit(removed_by, "IP_WHITELIST_REMOVE", f"Removed IP {ip_address} from whitelist")
    return True


def is_ip_whitelisted(ip_address):
    """Check if IP is whitelisted"""
    init_security_files()
    
    df = pd.read_csv(IP_WHITELIST_FILE)
    df = df[df["active"] == True]
    
    return ip_address in df["ip_address"].values


def get_whitelisted_ips():
    """Get all whitelisted IPs"""
    init_security_files()
    
    df = pd.read_csv(IP_WHITELIST_FILE)
    df = df[df["active"] == True]
    
    return df


# ==============================
# SECURITY DASHBOARD
# ==============================
def security_dashboard():
    """Security management dashboard for admins"""
    
    st.title("🔒 Advanced Security Dashboard")
    st.caption("Manage security settings, audit logs, and user sessions")
    
    role = st.session_state.get("role", "cashier")
    
    # Only owner and managers can access security settings
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access security settings.")
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Audit Log",
        "🔐 Two-Factor Authentication",
        "🖥️ Active Sessions",
        "🌐 IP Whitelist",
        "⚙️ Security Settings"
    ])
    
    # ==============================
    # TAB 1: AUDIT LOG
    # ==============================
    with tab1:
        st.markdown("## 📋 System Audit Log")
        st.caption("Track all user activities and system events")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            days = st.selectbox("Days to show", [7, 14, 30, 60, 90], index=2)
        
        with col2:
            user_filter = st.text_input("Filter by User", placeholder="Username")
        
        with col3:
            action_filter = st.text_input("Filter by Action", placeholder="LOGIN, LOGOUT, etc.")
        
        audit_df = get_audit_log(days, user_filter if user_filter else None, action_filter if action_filter else None)
        
        if not audit_df.empty:
            # Format timestamp for display
            audit_df["timestamp"] = pd.to_datetime(audit_df["timestamp"], errors='coerce')
            audit_df["timestamp"] = audit_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            
            st.dataframe(
                audit_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Summary stats
            st.markdown("### 📊 Activity Summary")
            summary = get_user_activity_summary(user_filter if user_filter else None, days)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Actions", summary.get("total_actions", 0))
            with col2:
                st.metric("Successful", summary.get("successful", 0))
            with col3:
                st.metric("Failed", summary.get("failed", 0))
            with col4:
                st.metric("Unique Actions", summary.get("unique_actions", 0))
            
            # Export
            csv = audit_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Audit Log (CSV)",
                data=csv,
                file_name=f"audit_log_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No audit log entries found")
    
    # ==============================
    # TAB 2: TWO-FACTOR AUTHENTICATION
    # ==============================
    with tab2:
        st.markdown("## 🔐 Two-Factor Authentication (2FA)")
        st.caption("Add an extra layer of security to user accounts")
        
        users_df = load_users()
        
        if not users_df.empty:
            # Select user
            selected_user = st.selectbox(
                "Select User",
                users_df["username"].tolist(),
                format_func=lambda x: f"{x} - {users_df[users_df['username'] == x]['full_name'].iloc[0] if 'full_name' in users_df.columns else x}"
            )
            
            if selected_user:
                user_data = users_df[users_df["username"] == selected_user].iloc[0]
                current_2fa = user_data.get("two_factor_enabled", False)
                current_phone = user_data.get("two_factor_phone", "")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Current Status:** {'✅ ENABLED' if current_2fa else '❌ DISABLED'}")
                    if current_phone:
                        st.markdown(f"**2FA Phone:** {current_phone}")
                
                with col2:
                    if not current_2fa:
                        phone = st.text_input("Phone Number for 2FA", placeholder="0777123456")
                        if st.button("🔐 Enable 2FA", use_container_width=True):
                            if phone:
                                valid, standardized, msg = validate_zimbabwe_phone(phone)
                                if valid:
                                    if enable_2fa(selected_user, standardized):
                                        st.success(f"✅ 2FA enabled for {selected_user}")
                                        st.rerun()
                                    else:
                                        st.error("Failed to enable 2FA")
                                else:
                                    st.error(msg)
                            else:
                                st.error("Please enter phone number")
                    else:
                        if st.button("🔓 Disable 2FA", use_container_width=True):
                            if disable_2fa(selected_user):
                                st.success(f"✅ 2FA disabled for {selected_user}")
                                st.rerun()
                            else:
                                st.error("Failed to disable 2FA")
                
                # Test 2FA
                if current_2fa and current_phone:
                    st.markdown("---")
                    st.markdown("### 📱 Test 2FA")
                    
                    if st.button("📧 Send Test Code", use_container_width=True):
                        whatsapp_link = create_2fa_code(selected_user, current_phone)
                        if whatsapp_link:
                            st.markdown(f'<a href="{whatsapp_link}" target="_blank"><button style="background:#25D366;color:white;border:none;border-radius:30px;padding:10px;width:100%;">📱 Send Test Code via WhatsApp</button></a>', unsafe_allow_html=True)
                            
                            test_code = st.text_input("Enter verification code")
                            if st.button("Verify Test Code"):
                                success, message = verify_2fa_code(selected_user, test_code)
                                if success:
                                    st.success("✅ Test successful! 2FA is working correctly.")
                                else:
                                    st.error(f"❌ {message}")
        else:
            st.info("No users found")
    
    # ==============================
    # TAB 3: ACTIVE SESSIONS
    # ==============================
    with tab3:
        st.markdown("## 🖥️ Active User Sessions")
        st.caption("Monitor and manage active user sessions")
        
        sessions_df = get_active_sessions()
        
        if not sessions_df.empty:
            display_df = sessions_df[["user", "login_time", "last_activity", "idle_minutes", "device_info", "ip_address"]].copy()
            
            # Format datetime columns
            display_df["login_time"] = pd.to_datetime(display_df["login_time"], errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
            display_df["last_activity"] = pd.to_datetime(display_df["last_activity"], errors='coerce').dt.strftime("%Y-%m-%d %H:%M:%S")
            display_df["idle_minutes"] = display_df["idle_minutes"].round(0).astype(int)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Revoke all sessions for a user
            st.markdown("### 🔒 Revoke Sessions")
            users_with_sessions = sessions_df["user"].unique().tolist()
            if users_with_sessions:
                selected_revoke_user = st.selectbox("Select User", users_with_sessions)
                
                if st.button("🚫 Revoke All Sessions for User", use_container_width=True):
                    revoke_all_sessions(selected_revoke_user)
                    st.success(f"All sessions revoked for {selected_revoke_user}")
                    st.rerun()
        else:
            st.info("No active sessions")
    
    # ==============================
    # TAB 4: IP WHITELIST
    # ==============================
    with tab4:
        st.markdown("## 🌐 IP Whitelist")
        st.caption("Restrict access to specific IP addresses")
        
        # Add new IP
        st.markdown("### ➕ Add IP to Whitelist")
        
        col1, col2 = st.columns(2)
        
        with col1:
            new_ip = st.text_input("IP Address", placeholder="192.168.1.1")
        
        with col2:
            ip_description = st.text_input("Description", placeholder="Head Office Network")
        
        if st.button("➕ Add IP", use_container_width=True):
            if new_ip:
                success, message = add_ip_to_whitelist(new_ip, ip_description, st.session_state.get("username", "admin"))
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please enter IP address")
        
        # List whitelisted IPs
        st.markdown("### 📋 Whitelisted IPs")
        
        whitelist_df = get_whitelisted_ips()
        
        if not whitelist_df.empty:
            st.dataframe(whitelist_df, use_container_width=True, hide_index=True)
            
            # Remove IP
            ip_to_remove = st.selectbox("Select IP to Remove", whitelist_df["ip_address"].tolist())
            if st.button("🗑️ Remove IP", use_container_width=True):
                remove_ip_from_whitelist(ip_to_remove, st.session_state.get("username", "admin"))
                st.success(f"IP {ip_to_remove} removed from whitelist")
                st.rerun()
        else:
            st.info("No IPs in whitelist")
    
    # ==============================
    # TAB 5: SECURITY SETTINGS
    # ==============================
    with tab5:
        st.markdown("## ⚙️ Security Settings")
        st.caption("Configure system-wide security policies")
        
        # Session timeout settings
        st.markdown("### ⏱️ Session Management")
        
        session_timeout = st.slider("Session Timeout (minutes)", 5, 120, 30, help="User will be logged out after inactivity")
        
        # Password policy
        st.markdown("### 🔑 Password Policy")
        
        min_password_length = st.number_input("Minimum Password Length", min_value=4, max_value=20, value=6)
        require_special_chars = st.checkbox("Require Special Characters", value=False)
        require_numbers = st.checkbox("Require Numbers", value=False)
        
        # Login attempts
        st.markdown("### 🔒 Login Security")
        
        max_login_attempts = st.number_input("Max Login Attempts before lockout", min_value=3, max_value=10, value=5)
        lockout_duration = st.number_input("Lockout Duration (minutes)", min_value=5, max_value=120, value=30)
        
        if st.button("💾 Save Security Settings", type="primary", use_container_width=True):
            settings = {
                "session_timeout": session_timeout,
                "min_password_length": min_password_length,
                "require_special_chars": require_special_chars,
                "require_numbers": require_numbers,
                "max_login_attempts": max_login_attempts,
                "lockout_duration": lockout_duration,
                "updated_at": datetime.now().isoformat(),
                "updated_by": st.session_state.get("username", "system")
            }
            
            settings_file = DATA_DIR / "security_settings.json"
            with open(settings_file, "w") as f:
                json.dump(settings, f, indent=2)
            
            log_audit(st.session_state.get("username", "system"), "SECURITY_SETTINGS_UPDATED", "Security settings updated")
            st.success("✅ Security settings saved successfully!")
        
        # Clear audit log button
        st.markdown("---")
        st.markdown("### 🗑️ Data Management")
        
        if st.button("🗑️ Clear Old Audit Logs (30+ days)", use_container_width=True):
            cutoff = datetime.now() - timedelta(days=30)
            df = pd.read_csv(AUDIT_LOG_FILE)
            if not df.empty:
                try:
                    df["timestamp"] = pd.to_datetime(df["timestamp"], format='ISO8601', errors='coerce')
                    df = df[df["timestamp"] >= cutoff]
                    df.to_csv(AUDIT_LOG_FILE, index=False)
                    st.success("Old audit logs cleared successfully")
                except:
                    st.error("Error clearing audit logs")


# ==============================
# 2FA LOGIN INTEGRATION
# ==============================
def two_factor_login_step(username, phone):
    """Handle 2FA step during login"""
    
    st.markdown("### 🔐 Two-Factor Authentication")
    st.caption(f"Verification code sent to {phone}")
    
    # Send code
    whatsapp_link = create_2fa_code(username, phone)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f'<a href="{whatsapp_link}" target="_blank"><button style="background:#25D366;color:white;border:none;border-radius:30px;padding:10px;width:100%;">📱 Send Code via WhatsApp</button></a>', unsafe_allow_html=True)
    
    with col2:
        if st.button("🔄 Resend Code", use_container_width=True):
            whatsapp_link = create_2fa_code(username, phone)
            st.success("New code sent!")
    
    verification_code = st.text_input("Enter 6-digit verification code", type="password")
    
    if st.button("✅ Verify & Login", type="primary", use_container_width=True):
        success, message = verify_2fa_code(username, verification_code)
        if success:
            return True, "Verified"
        else:
            st.error(message)
            return False, message
    
    return False, "Waiting for verification"


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    security_dashboard()