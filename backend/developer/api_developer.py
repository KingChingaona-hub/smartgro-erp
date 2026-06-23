import streamlit as st
import json
import secrets
import hashlib
import hmac
import time
import base64
import requests
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import re

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
API_CONFIG_FILE = DATA_DIR / "api_config.json"
API_LOGS_FILE = DATA_DIR / "api_logs.csv"
API_KEYS_FILE = DATA_DIR / "api_keys.json"

# ==============================
# INITIALIZATION
# ==============================
def init_api_files():
    """Initialize API-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    if not API_CONFIG_FILE.exists():
        config = {
            "enabled": True,
            "rate_limiting": True,
            "max_requests_per_minute": 60,
            "max_requests_per_hour": 1000,
            "jwt_expiry_minutes": 60,
            "allowed_origins": ["*"],
            "version": "v1",
            "endpoints": {
                "products": {
                    "enabled": True,
                    "methods": ["GET", "POST", "PUT", "DELETE"]
                },
                "inventory": {
                    "enabled": True,
                    "methods": ["GET", "PUT"]
                },
                "sales": {
                    "enabled": True,
                    "methods": ["GET", "POST"]
                },
                "customers": {
                    "enabled": True,
                    "methods": ["GET", "POST", "PUT"]
                },
                "reports": {
                    "enabled": True,
                    "methods": ["GET"]
                },
                "voice_commands": {
                    "enabled": True,
                    "methods": ["POST"]
                }
            },
            "webhooks": [],
            "api_docs_url": "/api/docs"
        }
        with open(API_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    
    if not API_KEYS_FILE.exists():
        keys = {
            "api_keys": {
                "default": {
                    "key": generate_api_key(),
                    "tenant_id": "default",
                    "created_at": datetime.now().isoformat(),
                    "last_used": None,
                    "status": "active",
                    "permissions": ["read", "write", "delete"],
                    "rate_limit": 60,
                    "expires_at": (datetime.now() + timedelta(days=365)).isoformat()
                }
            }
        }
        with open(API_KEYS_FILE, "w") as f:
            json.dump(keys, f, indent=2)
    
    if not API_LOGS_FILE.exists():
        df = pd.DataFrame(columns=[
            "log_id", "timestamp", "api_key", "endpoint", 
            "method", "status_code", "response_time", "ip_address", "user_agent"
        ])
        df.to_csv(API_LOGS_FILE, index=False)


def load_api_config():
    """Load API configuration"""
    init_api_files()
    with open(API_CONFIG_FILE, "r") as f:
        return json.load(f)


def save_api_config(config):
    """Save API configuration"""
    with open(API_CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_api_keys():
    """Load API keys"""
    init_api_files()
    with open(API_KEYS_FILE, "r") as f:
        return json.load(f)


def save_api_keys(keys):
    """Save API keys"""
    with open(API_KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)


def show_toast(message, type="info"):
    """Show a toast notification using Streamlit"""
    if type == "success":
        st.success(f"✅ {message}")
    elif type == "error":
        st.error(f"❌ {message}")
    elif type == "warning":
        st.warning(f"⚠️ {message}")
    else:
        st.info(f"ℹ️ {message}")


def generate_api_key():
    """Generate a new API key"""
    return f"sk_{secrets.token_urlsafe(32)}"


def log_api_call(api_key, endpoint, method, status_code, response_time, ip_address="127.0.0.1", user_agent="unknown"):
    """Log API call"""
    if API_LOGS_FILE.exists():
        df = pd.read_csv(API_LOGS_FILE)
    else:
        df = pd.DataFrame(columns=[
            "log_id", "timestamp", "api_key", "endpoint", 
            "method", "status_code", "response_time", "ip_address", "user_agent"
        ])
    
    masked_key = api_key[:8] + "..." + api_key[-8:] if len(api_key) > 16 else api_key
    
    new_log = pd.DataFrame([{
        "log_id": f"AL{len(df)+1:08d}",
        "timestamp": datetime.now().isoformat(),
        "api_key": masked_key,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "response_time": response_time,
        "ip_address": ip_address,
        "user_agent": user_agent
    }])
    
    df = pd.concat([df, new_log], ignore_index=True)
    df.to_csv(API_LOGS_FILE, index=False)


def validate_api_key(api_key):
    """Validate an API key"""
    keys = load_api_keys()
    
    for key_id, key_data in keys["api_keys"].items():
        if key_data["key"] == api_key:
            if key_data["status"] != "active":
                return False, "API key is inactive"
            
            if key_data.get("expires_at"):
                try:
                    expiry = datetime.fromisoformat(key_data["expires_at"])
                    if expiry < datetime.now():
                        return False, "API key has expired"
                except:
                    pass
            
            return True, key_data
    
    return False, "Invalid API key"


def generate_jwt(api_key, tenant_id, expiry_minutes=60):
    """Generate a JWT token for API authentication"""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "api_key": api_key,
        "tenant_id": tenant_id,
        "exp": int(time.time()) + (expiry_minutes * 60),
        "iat": int(time.time())
    }
    
    header_encoded = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    
    signature = hmac.new(
        b"your-secret-key",
        f"{header_encoded}.{payload_encoded}".encode(),
        hashlib.sha256
    ).digest()
    signature_encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    
    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"


def decode_jwt(token):
    """Decode JWT token"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
        return payload
    except:
        return None


def get_api_stats():
    """Get API usage statistics"""
    stats = {
        "total_calls": 0,
        "successful_calls": 0,
        "failed_calls": 0,
        "endpoints": {},
        "methods": {},
        "recent_calls": []
    }
    
    if API_LOGS_FILE.exists():
        df = pd.read_csv(API_LOGS_FILE)
        
        if not df.empty:
            stats["total_calls"] = len(df)
            
            if "status_code" in df.columns:
                stats["successful_calls"] = len(df[df["status_code"] < 400])
                stats["failed_calls"] = len(df[df["status_code"] >= 400])
            
            if "endpoint" in df.columns:
                endpoint_stats = df["endpoint"].value_counts().head(10)
                stats["endpoints"] = endpoint_stats.to_dict()
            
            if "method" in df.columns:
                method_stats = df["method"].value_counts()
                stats["methods"] = method_stats.to_dict()
            
            if len(df) > 0:
                cols = ["timestamp", "endpoint", "method", "status_code"]
                available_cols = [col for col in cols if col in df.columns]
                if available_cols:
                    recent = df.tail(10)[available_cols]
                    stats["recent_calls"] = recent.to_dict("records")
    
    return stats


# ==============================
# API DEVELOPER DASHBOARD
# ==============================
def api_developer_dashboard():
    """API Developer Dashboard"""
    
    st.title("🔌 API Developer Dashboard")
    st.caption("Manage and monitor API access for developers")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager", "developer"]:
        st.error("❌ Access Denied. API management is for owners, managers, and developers only.")
        return
    
    init_api_files()
    config = load_api_config()
    keys = load_api_keys()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "🔑 API Keys",
        "⚙️ Configuration",
        "📜 Logs",
        "📚 Documentation"
    ])
    
    with tab1:
        st.markdown("## 📊 API Usage Dashboard")
        
        col1, col2 = st.columns(2)
        with col1:
            status_color = "🟢" if config.get("enabled", True) else "🔴"
            st.metric("API Status", f"{status_color} {'Enabled' if config.get('enabled', True) else 'Disabled'}")
        
        with col2:
            st.metric("API Version", config.get("version", "v1"))
        
        stats = get_api_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total API Calls", stats["total_calls"])
        with col2:
            st.metric("Successful", stats["successful_calls"])
        with col3:
            st.metric("Failed", stats["failed_calls"])
        with col4:
            success_rate = (stats["successful_calls"] / stats["total_calls"] * 100) if stats["total_calls"] > 0 else 0
            st.metric("Success Rate", f"{success_rate:.1f}%")
        
        st.markdown("### 📋 Recent API Calls")
        if stats["recent_calls"]:
            df = pd.DataFrame(stats["recent_calls"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No API calls recorded yet")
        
        if stats["endpoints"]:
            st.markdown("### 🔝 Top Endpoints")
            endpoint_df = pd.DataFrame(list(stats["endpoints"].items()), columns=["Endpoint", "Calls"])
            st.bar_chart(endpoint_df.set_index("Endpoint"))
    
    with tab2:
        st.markdown("## 🔑 API Key Management")
        st.caption("Generate and manage API keys for developers")
        
        st.markdown("### 📋 Existing API Keys")
        
        key_list = []
        for key_id, key_data in keys["api_keys"].items():
            key_list.append({
                "Key ID": key_id,
                "API Key": key_data["key"][:12] + "..." + key_data["key"][-8:] if len(key_data["key"]) > 20 else key_data["key"],
                "Status": key_data.get("status", "active"),
                "Created": key_data.get("created_at", "")[:10] if key_data.get("created_at") else "",
                "Expires": key_data.get("expires_at", "Never")[:10] if key_data.get("expires_at") else "Never",
                "Permissions": ", ".join(key_data.get("permissions", []))
            })
        
        if key_list:
            df = pd.DataFrame(key_list)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No API keys found")
        
        st.markdown("### 🔑 Generate New API Key")
        
        col1, col2 = st.columns(2)
        with col1:
            key_name = st.text_input("Key Name", placeholder="My API Key")
            permissions = st.multiselect(
                "Permissions",
                ["read", "write", "delete", "admin"],
                default=["read"]
            )
        
        with col2:
            rate_limit = st.number_input("Rate Limit (requests per minute)", min_value=10, max_value=1000, value=60)
            expires_in_days = st.number_input("Expires In (days)", min_value=1, max_value=365, value=30)
        
        if st.button("🔑 Generate API Key", type="primary", use_container_width=True):
            if key_name:
                new_key = generate_api_key()
                new_key_data = {
                    "key": new_key,
                    "tenant_id": st.session_state.get("tenant_id", "default"),
                    "created_at": datetime.now().isoformat(),
                    "last_used": None,
                    "status": "active",
                    "permissions": permissions,
                    "rate_limit": rate_limit,
                    "expires_at": (datetime.now() + timedelta(days=expires_in_days)).isoformat()
                }
                
                keys["api_keys"][key_name] = new_key_data
                save_api_keys(keys)
                
                show_toast("API Key generated successfully!", "success")
                st.info(f"📋 **Your API Key:** `{new_key}`")
                st.warning("⚠️ Copy this key now. It will not be shown again.")
                st.rerun()
            else:
                show_toast("Please enter a key name", "error")
        
        st.markdown("### 🔒 Revoke API Key")
        key_to_revoke = st.selectbox("Select Key to Revoke", list(keys["api_keys"].keys()))
        
        if st.button("🔒 Revoke Key", use_container_width=True):
            if key_to_revoke and key_to_revoke in keys["api_keys"]:
                keys["api_keys"][key_to_revoke]["status"] = "revoked"
                save_api_keys(keys)
                show_toast(f"API key {key_to_revoke} revoked", "success")
                st.rerun()
    
    with tab3:
        st.markdown("## ⚙️ API Configuration")
        st.caption("Configure API settings and endpoints")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enabled = st.checkbox("Enable API", value=config.get("enabled", True))
            rate_limiting = st.checkbox("Enable Rate Limiting", value=config.get("rate_limiting", True))
            max_requests_minute = st.number_input(
                "Max Requests per Minute",
                min_value=10,
                max_value=1000,
                value=config.get("max_requests_per_minute", 60)
            )
            max_requests_hour = st.number_input(
                "Max Requests per Hour",
                min_value=100,
                max_value=10000,
                value=config.get("max_requests_per_hour", 1000)
            )
        
        with col2:
            jwt_expiry = st.number_input(
                "JWT Expiry (minutes)",
                min_value=5,
                max_value=1440,
                value=config.get("jwt_expiry_minutes", 60)
            )
            api_version = st.text_input("API Version", value=config.get("version", "v1"))
            allowed_origins = st.text_area(
                "Allowed Origins (comma separated)",
                value=", ".join(config.get("allowed_origins", ["*"]))
            )
        
        st.markdown("### 🎯 Endpoint Configuration")
        
        endpoints = config.get("endpoints", {})
        for endpoint, settings in endpoints.items():
            with st.expander(f"📌 {endpoint.upper()}"):
                enabled_endpoint = st.checkbox(f"Enable {endpoint}", value=settings.get("enabled", True))
                methods = st.multiselect(
                    f"Methods for {endpoint}",
                    ["GET", "POST", "PUT", "DELETE", "PATCH"],
                    default=settings.get("methods", ["GET"])
                )
                endpoints[endpoint] = {
                    "enabled": enabled_endpoint,
                    "methods": methods
                }
        
        if st.button("💾 Save API Configuration", type="primary", use_container_width=True):
            config.update({
                "enabled": enabled,
                "rate_limiting": rate_limiting,
                "max_requests_per_minute": max_requests_minute,
                "max_requests_per_hour": max_requests_hour,
                "jwt_expiry_minutes": jwt_expiry,
                "version": api_version,
                "allowed_origins": [o.strip() for o in allowed_origins.split(",") if o.strip()],
                "endpoints": endpoints
            })
            save_api_config(config)
            show_toast("API settings updated!", "success")
            st.rerun()
    
    with tab4:
        st.markdown("## 📜 API Access Logs")
        st.caption("Audit trail of all API requests")
        
        if API_LOGS_FILE.exists():
            df = pd.read_csv(API_LOGS_FILE)
            
            if not df.empty:
                if "timestamp" in df.columns:
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
                
                display_cols = ["timestamp", "api_key", "endpoint", "method", "status_code", "response_time"]
                available_cols = [col for col in display_cols if col in df.columns]
                
                st.dataframe(df[available_cols], use_container_width=True, hide_index=True)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export API Logs (CSV)",
                    data=csv,
                    file_name=f"api_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No API logs found")
        else:
            st.info("No API logs found")
        
        st.markdown("### 🔍 Filter Logs")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            filter_endpoint = st.text_input("Filter by Endpoint", placeholder="/api/v1/products")
        
        with col2:
            filter_status = st.selectbox("Filter by Status", ["All", "Success (2xx)", "Client Error (4xx)", "Server Error (5xx)"])
        
        with col3:
            filter_method = st.selectbox("Filter by Method", ["All", "GET", "POST", "PUT", "DELETE"])
        
        if st.button("🔍 Apply Filters", use_container_width=True):
            show_toast("Filters applied", "info")
    
    with tab5:
        st.markdown("## 📚 API Documentation")
        st.caption("API endpoint documentation and examples")
        
        # Getting Started section
        st.markdown("### 🚀 Getting Started")
        st.markdown("#### Base URL")
        st.code("https://your-domain.com/api/v1/", language="text")
        
        st.markdown("#### Authentication")
        st.markdown("All API requests require an API key or JWT token.")
        
        st.markdown("**Using API Key:**")
        st.code("""
import requests

headers = {
    "X-API-Key": "your-api-key-here"
}
response = requests.get("https://your-domain.com/api/v1/products", headers=headers)
        """, language="python")
        
        st.markdown("**Using JWT Token:**")
        st.code("""
import requests

headers = {
    "Authorization": "Bearer your-jwt-token"
}
response = requests.get("https://your-domain.com/api/v1/products", headers=headers)
        """, language="python")
        
        # Endpoints section
        st.markdown("### 📡 Endpoints")
        
        endpoints = config.get("endpoints", {})
        for endpoint, settings in endpoints.items():
            if settings.get("enabled", True):
                with st.expander(f"📌 {endpoint.upper()}"):
                    st.markdown(f"**Endpoint:** `/api/{config.get('version', 'v1')}/{endpoint}`")
                    st.markdown(f"**Methods:** {', '.join(settings.get('methods', ['GET']))}")
                    
                    if endpoint == "products":
                        st.markdown("**Example - Get Products:**")
                        st.code("""
import requests

response = requests.get(
    "https://your-domain.com/api/v1/products",
    headers={"X-API-Key": "your-api-key"}
)

products = response.json()
                        """, language="python")
                        
                        st.markdown("**Example - Create Product:**")
                        st.code("""
import requests

data = {
    "name": "Product Name",
    "price": 29.99,
    "quantity": 100
}

response = requests.post(
    "https://your-domain.com/api/v1/products",
    headers={"X-API-Key": "your-api-key"},
    json=data
)
                        """, language="python")
                    
                    elif endpoint == "sales":
                        st.markdown("**Example - Get Sales:**")
                        st.code("""
import requests

response = requests.get(
    "https://your-domain.com/api/v1/sales",
    headers={"X-API-Key": "your-api-key"},
    params={"date_from": "2024-01-01", "date_to": "2024-12-31"}
)

sales = response.json()
                        """, language="python")
                    
                    elif endpoint == "inventory":
                        st.markdown("**Example - Get Inventory:**")
                        st.code("""
import requests

response = requests.get(
    "https://your-domain.com/api/v1/inventory",
    headers={"X-API-Key": "your-api-key"}
)

inventory = response.json()
                        """, language="python")
                    
                    elif endpoint == "customers":
                        st.markdown("**Example - Get Customers:**")
                        st.code("""
import requests

response = requests.get(
    "https://your-domain.com/api/v1/customers",
    headers={"X-API-Key": "your-api-key"}
)

customers = response.json()
                        """, language="python")
        
        # Response Format section
        st.markdown("### 📊 Response Format")
        st.markdown("All responses follow this format:")
        st.code("""
{
    "status": "success",
    "data": {
        // Response data here
    },
    "meta": {
        "timestamp": "2024-01-01T12:00:00Z",
        "version": "v1"
    }
}
        """, language="json")
        
        # Error Responses section
        st.markdown("### ⚠️ Error Responses")
        st.code("""
{
    "status": "error",
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Rate limit exceeded. Try again in 60 seconds."
    }
}
        """, language="json")
        
        # Rate Limiting section
        st.markdown("### 🔒 Rate Limiting")
        st.markdown(f"""
- **Requests per minute:** {config.get('max_requests_per_minute', 60)}
- **Requests per hour:** {config.get('max_requests_per_hour', 1000)}
        """)
        
        st.info("💡 For more detailed documentation, visit the API reference page.")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    api_developer_dashboard()