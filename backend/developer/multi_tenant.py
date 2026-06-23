import streamlit as st
import json
import hashlib
import secrets
from pathlib import Path
from datetime import datetime
import pandas as pd
import re

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
TENANTS_FILE = DATA_DIR / "tenants.json"
TENANT_LOGS_FILE = DATA_DIR / "tenant_logs.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_tenant_files():
    """Initialize tenant-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    if not TENANTS_FILE.exists():
        tenants = {
            "tenants": {
                "default": {
                    "tenant_id": "default",
                    "tenant_name": "Default Tenant",
                    "business_name": "SmartGro Retail",
                    "domain": "default",
                    "owner_email": "admin@smartgro.com",
                    "created_date": datetime.now().isoformat(),
                    "status": "active",
                    "subscription_plan": "premium",
                    "subscription_expiry": "2025-12-31",
                    "features": {
                        "pos": True,
                        "inventory": True,
                        "sales": True,
                        "customers": True,
                        "reports": True,
                        "white_label": True,
                        "multi_currency": True,
                        "voice_commands": True,
                        "barcode_scanner": True,
                        "receipt_printer": True
                    },
                    "settings": {
                        "currency": "USD",
                        "tax_rate": 15.0,
                        "default_markup": 30.0,
                        "enable_loyalty": True,
                        "enable_returns": True
                    },
                    "api_keys": {},
                    "whitelabel": {
                        "business_name": "SmartGro Retail",
                        "primary_color": "#6366F1",
                        "secondary_color": "#8B5CF6"
                    }
                }
            }
        }
        with open(TENANTS_FILE, "w") as f:
            json.dump(tenants, f, indent=2)
    
    if not TENANT_LOGS_FILE.exists():
        df = pd.DataFrame(columns=[
            "log_id", "timestamp", "tenant_id", "action", 
            "user", "details", "status"
        ])
        df.to_csv(TENANT_LOGS_FILE, index=False)


def load_tenants():
    """Load all tenants"""
    init_tenant_files()
    with open(TENANTS_FILE, "r") as f:
        return json.load(f)


def save_tenants(tenants_data):
    """Save tenants data"""
    with open(TENANTS_FILE, "w") as f:
        json.dump(tenants_data, f, indent=2)


def get_tenant(tenant_id):
    """Get specific tenant"""
    tenants = load_tenants()
    return tenants["tenants"].get(tenant_id)


def get_current_tenant():
    """Get current tenant from session state"""
    tenant_id = st.session_state.get("tenant_id", "default")
    return get_tenant(tenant_id)


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


def log_tenant_action(tenant_id, action, user, details, status="SUCCESS"):
    """Log tenant action"""
    df = pd.read_csv(TENANT_LOGS_FILE)
    
    new_log = pd.DataFrame([{
        "log_id": f"TL{len(df)+1:08d}",
        "timestamp": datetime.now().isoformat(),
        "tenant_id": tenant_id,
        "action": action,
        "user": user,
        "details": json.dumps(details),
        "status": status
    }])
    
    df = pd.concat([df, new_log], ignore_index=True)
    df.to_csv(TENANT_LOGS_FILE, index=False)


def validate_tenant_name(name):
    """Validate tenant name"""
    if not name or len(name) < 2:
        return False, "Tenant name must be at least 2 characters"
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', name):
        return False, "Tenant name can only contain letters, numbers, spaces, hyphens, and underscores"
    return True, ""


def validate_domain(domain):
    """Validate domain"""
    if not domain or len(domain) < 2:
        return False, "Domain must be at least 2 characters"
    if not re.match(r'^[a-z0-9\-]+$', domain):
        return False, "Domain can only contain lowercase letters, numbers, and hyphens"
    return True, ""


def generate_tenant_id():
    """Generate unique tenant ID"""
    return f"T{secrets.token_hex(4).upper()}"


def generate_api_key():
    """Generate API key for tenant"""
    return f"SK_{secrets.token_urlsafe(32)}"


# ==============================
# TENANT MANAGEMENT FUNCTIONS
# ==============================
def create_tenant(tenant_name, domain, business_name, owner_email, plan="basic"):
    """Create a new tenant"""
    
    # Validate
    valid, msg = validate_tenant_name(tenant_name)
    if not valid:
        return False, msg
    
    valid, msg = validate_domain(domain)
    if not valid:
        return False, msg
    
    # Check if domain exists
    tenants = load_tenants()
    for tid, tenant in tenants["tenants"].items():
        if tenant.get("domain") == domain:
            return False, "Domain already exists"
    
    # Create tenant
    tenant_id = generate_tenant_id()
    
    new_tenant = {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "business_name": business_name,
        "domain": domain,
        "owner_email": owner_email,
        "created_date": datetime.now().isoformat(),
        "status": "active",
        "subscription_plan": plan,
        "subscription_expiry": (datetime.now().replace(year=datetime.now().year + 1)).strftime("%Y-%m-%d"),
        "features": {
            "pos": True,
            "inventory": True,
            "sales": True,
            "customers": True,
            "reports": True,
            "white_label": True,
            "multi_currency": True,
            "voice_commands": True,
            "barcode_scanner": True,
            "receipt_printer": True
        },
        "settings": {
            "currency": "USD",
            "tax_rate": 15.0,
            "default_markup": 30.0,
            "enable_loyalty": True,
            "enable_returns": True
        },
        "api_keys": {
            "primary": generate_api_key(),
            "secondary": generate_api_key()
        },
        "whitelabel": {
            "business_name": business_name,
            "primary_color": "#6366F1",
            "secondary_color": "#8B5CF6"
        }
    }
    
    tenants["tenants"][tenant_id] = new_tenant
    save_tenants(tenants)
    
    log_tenant_action(tenant_id, "CREATE", "system", {"tenant_name": tenant_name}, "SUCCESS")
    
    return True, tenant_id


def update_tenant(tenant_id, updates):
    """Update tenant details"""
    tenants = load_tenants()
    
    if tenant_id not in tenants["tenants"]:
        return False, "Tenant not found"
    
    tenant = tenants["tenants"][tenant_id]
    tenant.update(updates)
    
    save_tenants(tenants)
    log_tenant_action(tenant_id, "UPDATE", "system", updates, "SUCCESS")
    
    return True, "Tenant updated successfully"


def delete_tenant(tenant_id):
    """Delete a tenant"""
    if tenant_id == "default":
        return False, "Cannot delete default tenant"
    
    tenants = load_tenants()
    
    if tenant_id not in tenants["tenants"]:
        return False, "Tenant not found"
    
    del tenants["tenants"][tenant_id]
    save_tenants(tenants)
    
    log_tenant_action(tenant_id, "DELETE", "system", {}, "SUCCESS")
    
    return True, "Tenant deleted successfully"


def switch_tenant(tenant_id):
    """Switch to a different tenant"""
    tenant = get_tenant(tenant_id)
    if not tenant:
        return False, "Tenant not found"
    
    if tenant.get("status") != "active":
        return False, "Tenant is not active"
    
    st.session_state.tenant_id = tenant_id
    st.session_state.tenant_name = tenant.get("tenant_name")
    st.session_state.business_name = tenant.get("business_name")
    
    # Update whitelabel settings
    if "whitelabel" in tenant:
        st.session_state.primary_color = tenant["whitelabel"].get("primary_color", "#6366F1")
        st.session_state.secondary_color = tenant["whitelabel"].get("secondary_color", "#8B5CF6")
    
    return True, f"Switched to {tenant.get('tenant_name')}"


def get_tenant_stats():
    """Get tenant statistics"""
    tenants = load_tenants()
    stats = {
        "total": len(tenants["tenants"]),
        "active": 0,
        "inactive": 0,
        "suspended": 0,
        "plans": {}
    }
    
    for tenant in tenants["tenants"].values():
        status = tenant.get("status", "inactive")
        if status == "active":
            stats["active"] += 1
        elif status == "inactive":
            stats["inactive"] += 1
        elif status == "suspended":
            stats["suspended"] += 1
        
        plan = tenant.get("subscription_plan", "basic")
        stats["plans"][plan] = stats["plans"].get(plan, 0) + 1
    
    return stats


# ==============================
# MULTI-TENANT DASHBOARD
# ==============================
def multi_tenant_dashboard():
    """Multi-Tenant Management Dashboard"""
    
    st.title("🏢 Multi-Tenant Management")
    st.caption("Manage multiple tenants from a single installation")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Multi-tenant management is for owners and managers only.")
        return
    
    init_tenant_files()
    
    # Get current tenant
    current_tenant_id = st.session_state.get("tenant_id", "default")
    current_tenant = get_tenant(current_tenant_id)
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "👥 Tenants",
        "➕ Create Tenant",
        "🔑 API Keys",
        "📜 Logs"
    ])
    
    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## 📊 Tenant Dashboard")
        
        stats = get_tenant_stats()
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Tenants", stats["total"])
        with col2:
            st.metric("Active Tenants", stats["active"])
        with col3:
            st.metric("Inactive Tenants", stats["inactive"])
        with col4:
            st.metric("Suspended", stats["suspended"])
        
        # Current tenant info
        st.markdown("### 🏢 Current Tenant")
        if current_tenant:
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Tenant ID:** {current_tenant.get('tenant_id')}")
                st.markdown(f"**Tenant Name:** {current_tenant.get('tenant_name')}")
                st.markdown(f"**Business Name:** {current_tenant.get('business_name')}")
            with col2:
                st.markdown(f"**Domain:** {current_tenant.get('domain')}")
                st.markdown(f"**Owner Email:** {current_tenant.get('owner_email')}")
                st.markdown(f"**Subscription Plan:** {current_tenant.get('subscription_plan', 'N/A')}")
        
        # Plan distribution
        st.markdown("### 📊 Subscription Plans")
        if stats["plans"]:
            plan_data = pd.DataFrame({
                "Plan": list(stats["plans"].keys()),
                "Count": list(stats["plans"].values())
            })
            st.bar_chart(plan_data.set_index("Plan"))
        else:
            st.info("No subscription data available")
    
    # ==============================
    # TAB 2: TENANTS
    # ==============================
    with tab2:
        st.markdown("## 👥 Tenant Management")
        st.caption("View and manage all tenants")
        
        tenants = load_tenants()
        
        # Tenant list
        tenant_list = []
        for tenant_id, tenant in tenants["tenants"].items():
            tenant_list.append({
                "Tenant ID": tenant_id,
                "Tenant Name": tenant.get("tenant_name", ""),
                "Business Name": tenant.get("business_name", ""),
                "Domain": tenant.get("domain", ""),
                "Plan": tenant.get("subscription_plan", "basic"),
                "Status": tenant.get("status", "inactive"),
                "Created": tenant.get("created_date", "")[:10]
            })
        
        if tenant_list:
            df = pd.DataFrame(tenant_list)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Tenant ID": st.column_config.TextColumn("Tenant ID", width="small"),
                    "Tenant Name": st.column_config.TextColumn("Tenant Name", width="medium"),
                    "Business Name": st.column_config.TextColumn("Business Name", width="medium"),
                    "Domain": st.column_config.TextColumn("Domain", width="small"),
                    "Plan": st.column_config.TextColumn("Plan", width="small"),
                    "Status": st.column_config.TextColumn("Status", width="small"),
                    "Created": st.column_config.TextColumn("Created", width="small")
                }
            )
        else:
            st.info("No tenants found")
        
        # Tenant actions
        st.markdown("### 🔧 Tenant Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Switch tenant
            tenant_ids = [t_id for t_id in tenants["tenants"].keys()]
            switch_to = st.selectbox("Switch to Tenant", tenant_ids)
            
            if st.button("🔄 Switch Tenant", use_container_width=True):
                success, msg = switch_tenant(switch_to)
                if success:
                    show_toast(msg, "success")
                    st.rerun()
                else:
                    show_toast(msg, "error")
        
        with col2:
            # Update tenant status
            tenant_to_update = st.selectbox("Select Tenant to Update", tenant_ids)
            new_status = st.selectbox("New Status", ["active", "inactive", "suspended"])
            
            if st.button("📝 Update Status", use_container_width=True):
                success, msg = update_tenant(tenant_to_update, {"status": new_status})
                if success:
                    show_toast(msg, "success")
                    st.rerun()
                else:
                    show_toast(msg, "error")
        
        with col3:
            # Delete tenant
            tenant_to_delete = st.selectbox("Select Tenant to Delete", 
                                           [t for t in tenant_ids if t != "default"])
            
            if st.button("🗑️ Delete Tenant", use_container_width=True):
                if tenant_to_delete:
                    if st.session_state.get("confirm_delete") == tenant_to_delete:
                        success, msg = delete_tenant(tenant_to_delete)
                        if success:
                            show_toast(msg, "success")
                            st.session_state.confirm_delete = None
                            st.rerun()
                        else:
                            show_toast(msg, "error")
                    else:
                        st.session_state.confirm_delete = tenant_to_delete
                        show_toast(f"Click again to confirm deletion of {tenant_to_delete}", "warning")
    
    # ==============================
    # TAB 3: CREATE TENANT
    # ==============================
    with tab3:
        st.markdown("## ➕ Create New Tenant")
        st.caption("Add a new tenant to the system")
        
        with st.form("create_tenant_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                tenant_name = st.text_input("Tenant Name", placeholder="My Business")
                business_name = st.text_input("Business Name", placeholder="My Business Ltd")
                domain = st.text_input("Domain", placeholder="mybusiness")
                st.caption("Domain must be unique and use lowercase letters, numbers, and hyphens")
            
            with col2:
                owner_email = st.text_input("Owner Email", placeholder="owner@business.com")
                subscription_plan = st.selectbox(
                    "Subscription Plan",
                    ["basic", "standard", "premium", "enterprise"],
                    format_func=lambda x: x.title()
                )
                
                st.markdown("### 🚀 Features")
                features = {
                    "pos": st.checkbox("POS", value=True),
                    "inventory": st.checkbox("Inventory", value=True),
                    "sales": st.checkbox("Sales", value=True),
                    "customers": st.checkbox("Customers", value=True),
                    "reports": st.checkbox("Reports", value=True),
                    "white_label": st.checkbox("White Label", value=True)
                }
            
            submitted = st.form_submit_button("🚀 Create Tenant", use_container_width=True, type="primary")
            
            if submitted:
                if not all([tenant_name, business_name, domain, owner_email]):
                    show_toast("Please fill all required fields", "error")
                else:
                    success, result = create_tenant(
                        tenant_name,
                        domain,
                        business_name,
                        owner_email,
                        subscription_plan
                    )
                    
                    if success:
                        show_toast(f"Tenant {tenant_name} created!", "success")
                        # Clear form
                        st.rerun()
                    else:
                        show_toast(f"Failed to create tenant: {result}", "error")
    
    # ==============================
    # TAB 4: API KEYS
    # ==============================
    with tab4:
        st.markdown("## 🔑 API Key Management")
        st.caption("Manage API keys for tenant access")
        
        if current_tenant:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Primary API Key")
                api_key_primary = current_tenant.get("api_keys", {}).get("primary", "N/A")
                st.code(api_key_primary)
                
                if st.button("🔄 Regenerate Primary Key", use_container_width=True):
                    new_key = generate_api_key()
                    success, msg = update_tenant(
                        current_tenant_id,
                        {"api_keys": {"primary": new_key, "secondary": current_tenant.get("api_keys", {}).get("secondary", "")}}
                    )
                    if success:
                        show_toast("Primary API key regenerated", "success")
                        st.rerun()
            
            with col2:
                st.markdown("### Secondary API Key")
                api_key_secondary = current_tenant.get("api_keys", {}).get("secondary", "N/A")
                st.code(api_key_secondary)
                
                if st.button("🔄 Regenerate Secondary Key", use_container_width=True):
                    new_key = generate_api_key()
                    success, msg = update_tenant(
                        current_tenant_id,
                        {"api_keys": {"primary": current_tenant.get("api_keys", {}).get("primary", ""), "secondary": new_key}}
                    )
                    if success:
                        show_toast("Secondary API key regenerated", "success")
                        st.rerun()
            
            st.info("⚠️ API keys provide full access to tenant data. Keep them secure and regenerate if compromised.")
    
    # ==============================
    # TAB 5: LOGS
    # ==============================
    with tab5:
        st.markdown("## 📜 Tenant Activity Logs")
        st.caption("Audit trail of tenant management actions")
        
        if Path(TENANT_LOGS_FILE).exists():
            df = pd.read_csv(TENANT_LOGS_FILE)
            
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
                
                st.dataframe(
                    df[["timestamp", "tenant_id", "action", "user", "status"]],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Export
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Export Tenant Logs (CSV)",
                    data=csv,
                    file_name=f"tenant_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No tenant logs found")
        else:
            st.info("No tenant logs found")


# ==============================
# TENANT CONTEXT PROVIDER
# ==============================
def get_tenant_context():
    """Get current tenant context for data isolation"""
    tenant_id = st.session_state.get("tenant_id", "default")
    tenant = get_tenant(tenant_id)
    
    if not tenant:
        return {
            "tenant_id": "default",
            "tenant_name": "Default Tenant",
            "business_name": "SmartGro Retail",
            "domain": "default",
            "settings": {
                "currency": "USD",
                "tax_rate": 15.0,
                "default_markup": 30.0,
                "enable_loyalty": True,
                "enable_returns": True
            }
        }
    
    return {
        "tenant_id": tenant_id,
        "tenant_name": tenant.get("tenant_name", ""),
        "business_name": tenant.get("business_name", ""),
        "domain": tenant.get("domain", ""),
        "settings": tenant.get("settings", {}),
        "features": tenant.get("features", {})
    }


def get_tenant_data_paths():
    """Get tenant-specific data paths for data isolation"""
    tenant_id = st.session_state.get("tenant_id", "default")
    tenant_dir = DATA_DIR / "tenants" / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "tenant_dir": tenant_dir,
        "products": tenant_dir / "products.json",
        "inventory": tenant_dir / "inventory.json",
        "sales": tenant_dir / "sales.json",
        "customers": tenant_dir / "customers.json",
        "transactions": tenant_dir / "transactions.json"
    }


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    multi_tenant_dashboard()