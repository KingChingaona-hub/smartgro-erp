# backend/core/role_based_menu.py
# UPDATED: Added Package Modules filtering. 
# Access = (User Role Permissions) INTERSECT (Branch Subscription Package).

import streamlit as st
from backend.core.auth import can_access_feature
from backend.core.db_adapter import (
    load_products,
    load_purchases,
    get_current_branch,
    load_branches,
)

# ============================================================
# PACKAGE MODULE MAPPING
# ============================================================
PACKAGE_MODULES = {
    "Bronze": [
        # Sales & POS
        "POS", "Sales History",
        # Stock Management
        "Stock Dashboard", "Inventory", "Barcode Generator", "Barcode Scanner",
        # Purchases & Expenses
        "Purchases", "Purchases Dashboard", "Expenses", "Expenses Dashboard",
        # Income & Cash
        "Income", "Income Dashboard", "Cash Dashboard",
        # Credit
        "Debtors", "Debtors Dashboard",
        # Store Ops
        "Shift Management", "Documents",
        # Security
        "User Management"
    ],
    "Silver": [
        # All Bronze
        "POS", "Sales History", "Stock Dashboard", "Inventory", "Barcode Generator", "Barcode Scanner",
        "Purchases", "Purchases Dashboard", "Expenses", "Expenses Dashboard",
        "Income", "Income Dashboard", "Cash Dashboard", "Debtors", "Debtors Dashboard",
        "Shift Management", "Documents", "User Management",
        # Silver Additions
        "Customer Dashboard", "Retention Dashboard", "Segmentation Dashboard", "Lifecycle Dashboard",
        "Reports Dashboard", "Floating Financials", "P&L", "Duplicate Products",
        "Mobile Dashboard", "PWA Setup", "Offline Mode", "Language Management"
    ],
    "Gold": [
        # All Silver
        "POS", "Sales History", "Stock Dashboard", "Inventory", "Barcode Generator", "Barcode Scanner",
        "Purchases", "Purchases Dashboard", "Expenses", "Expenses Dashboard",
        "Income", "Income Dashboard", "Cash Dashboard", "Debtors", "Debtors Dashboard",
        "Shift Management", "Documents", "User Management",
        "Customer Dashboard", "Retention Dashboard", "Segmentation Dashboard", "Lifecycle Dashboard",
        "Reports Dashboard", "Floating Financials", "P&L", "Duplicate Products",
        "Mobile Dashboard", "PWA Setup", "Offline Mode", "Language Management",
        # Gold Additions
        "Customer 360 View", "Customer Insights 360",
        "Supplier Bidding", "Supplier Bidding Portal", "Smart Replenishment", "Inventory Optimizer",
        "Financial Closing", "Profit Center Analysis",
        "Automated Follow-up", "Workflow Approvals",
        "Live Dashboard", "Payment Gateway", "SMS Gateway", "E-commerce Sync"
    ],
    "Platinum": [
        # All Gold
        "POS", "Sales History", "Stock Dashboard", "Inventory", "Barcode Generator", "Barcode Scanner",
        "Purchases", "Purchases Dashboard", "Expenses", "Expenses Dashboard",
        "Income", "Income Dashboard", "Cash Dashboard", "Debtors", "Debtors Dashboard",
        "Shift Management", "Documents", "User Management",
        "Customer Dashboard", "Retention Dashboard", "Segmentation Dashboard", "Lifecycle Dashboard",
        "Reports Dashboard", "Floating Financials", "P&L", "Duplicate Products",
        "Mobile Dashboard", "PWA Setup", "Offline Mode", "Language Management",
        "Customer 360 View", "Customer Insights 360",
        "Supplier Bidding", "Supplier Bidding Portal", "Smart Replenishment", "Inventory Optimizer",
        "Financial Closing", "Profit Center Analysis",
        "Automated Follow-up", "Workflow Approvals",
        "Live Dashboard", "Payment Gateway", "SMS Gateway", "E-commerce Sync",
        # Platinum Additions
        "Predictive Analytics", "Demand Forecasting", "Churn Prediction", "Recommendation Engine",
        "Anomaly Detection", "Automated Insights", "Competitor Price Monitoring", "Business Advisor",
        "Accounting Sync", "API Developer", "Multi-Tenant", "White Label", "Voice Commands",
        "Branch Management", "Branch Performance", "Security Dashboard", "Settings"
    ]
}


# ==============================
# BRANCH HELPERS
# ==============================
def _resolve_branch(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    if not branch_id:
        branch_id = "HO"
    return str(branch_id).strip().upper()


def _branch_label(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == branch_id]
            if not match.empty:
                name = match.iloc[0].get("branch_name", "")
                pkg = match.iloc[0].get("package", "Unknown")
                if name:
                    return f"{name} ({branch_id}) - {pkg} Tier"
    except Exception:
        pass
    return branch_id


# ============================================================
# get_visible_modules - UPDATED WITH PACKAGE FILTERING
# ============================================================
def get_visible_modules(role, branch_package=None):
    """Return ALL modules a role can access, filtered by the branch's package."""
    
    # If no package is passed, pull from session (defaults to Bronze)
    if branch_package is None:
        branch_package = st.session_state.get("branch_package", "Bronze")
    
    # Ensure we have a valid package fallback
    if branch_package not in PACKAGE_MODULES:
        branch_package = "Bronze"

    all_modules = [
        # Stock Management
        {"name": "Stock Dashboard", "permission": "inventory_view"},
        {"name": "Inventory", "permission": "inventory_view"},
        {"name": "Barcode Generator", "permission": "inventory_view"},
        {"name": "Barcode Scanner", "permission": "barcode_scanner"},
        {"name": "Duplicate Products", "permission": "inventory_view"},

        # Sales
        {"name": "POS", "permission": "pos"},
        {"name": "Sales History", "permission": "sales_history"},
        {"name": "Sales Dashboard", "permission": "sales_dashboard"},
        {"name": "Returns & Refunds", "permission": "returns_management"},

        # Finance
        {"name": "Cash Dashboard", "permission": "cash_dashboard"},
        {"name": "Income", "permission": "income"},
        {"name": "Income Dashboard", "permission": "income"},
        {"name": "Expenses", "permission": "expenses"},
        {"name": "Expenses Dashboard", "permission": "expenses"},
        {"name": "P&L", "permission": "pl"},
        {"name": "Financial Closing", "permission": "financial_closing"},
        {"name": "Payment Gateway", "permission": "payment_gateway"},
        {"name": "Accounting Sync", "permission": "accounting_sync"},
        {"name": "Floating Financials", "permission": "floating_financials"},

        # Purchases
        {"name": "Purchases", "permission": "purchases"},
        {"name": "Purchases Dashboard", "permission": "purchases"},
        {"name": "Supplier Bidding", "permission": "supplier_bidding"},
        {"name": "Supplier Bidding Portal", "permission": "supplier_bidding"},
        {"name": "Smart Replenishment", "permission": "smart_replenishment"},

        # Customers
        {"name": "Customer Dashboard", "permission": "customers"},
        {"name": "Customer 360 View", "permission": "customer_360"},
        {"name": "Customer Insights 360", "permission": "customer_360"},
        {"name": "Retention Dashboard", "permission": "customers"},
        {"name": "Segmentation Dashboard", "permission": "customers"},
        {"name": "Lifecycle Dashboard", "permission": "customers"},

        # Credit & Debtors
        {"name": "Debtors", "permission": "debtors"},
        {"name": "Debtors Dashboard", "permission": "debtors_dashboard"},

        # Analytics
        {"name": "Reports Dashboard", "permission": "reports"},
        {"name": "Business Advisor", "permission": "business_advisor"},
        {"name": "Demand Forecasting", "permission": "demand_forecasting"},
        {"name": "Predictive Analytics", "permission": "predictive_analytics"},
        {"name": "Profit Center Analysis", "permission": "profit_analysis"},
        {"name": "Competitor Price Monitoring", "permission": "competitor_price"},
        {"name": "Churn Prediction", "permission": "churn_prediction"},
        {"name": "Automated Insights", "permission": "automated_insights"},
        {"name": "Anomaly Detection", "permission": "anomaly_detection"},
        {"name": "Recommendation Engine", "permission": "recommendation_engine"},
        {"name": "Inventory Optimizer", "permission": "inventory_optimizer"},

        # Operations
        {"name": "Shift Management", "permission": "shift_management"},
        {"name": "Live Dashboard", "permission": "live_dashboard"},
        {"name": "Mobile Dashboard", "permission": "mobile_dashboard"},
        {"name": "Voice Commands", "permission": "voice_commands"},
        {"name": "Automated Follow-up", "permission": "automated_followup"},
        {"name": "Workflow Approvals", "permission": "workflow_approvals"},
        {"name": "Documents", "permission": "documents"},

        # Integrations
        {"name": "E-commerce Sync", "permission": "ecommerce_sync"},
        {"name": "SMS Gateway", "permission": "sms_gateway"},

        # Admin
        {"name": "Security Dashboard", "permission": "security"},
        {"name": "Language Management", "permission": "language_management"},
        {"name": "Offline Mode", "permission": "offline_mode"},
        {"name": "PWA Setup", "permission": "pwa_setup"},
        {"name": "API Developer", "permission": "api_developer"},
        {"name": "Multi-Tenant", "permission": "multi_tenant"},
        {"name": "White Label", "permission": "white_label"},
        {"name": "Branch Management", "permission": "branch_management"},
        {"name": "Branch Performance", "permission": "branch_performance"},
        {"name": "User Management", "permission": "user_management"},
        {"name": "Settings", "permission": "settings"},
    ]

    # Get allowed modules for the package
    allowed_by_package = PACKAGE_MODULES[branch_package]

    # 1. CASHIER - RESTRICTED ACCESS
    if role == "cashier":
        cashier_modules = [
            "POS", "Sales History", "Barcode Scanner",
            "Customer Dashboard", "Floating Financials",
            "Debtors", "Debtors Dashboard", "Shift Management", "Documents"
        ]
        # Intersection: Cashier modules + Package modules
        final_modules = [m for m in cashier_modules if m in allowed_by_package]
        return sorted(final_modules)

    # 2. OWNER & MANAGER - FULL ACCESS (Limited by Package)
    visible_modules = []
    for module in all_modules:
        # Check if role allows it AND package allows it
        if can_access_feature(role, module["permission"]) and module["name"] in allowed_by_package:
            visible_modules.append(module["name"])

    # If somehow empty, fallback to basic POS/Stock if they are in package
    if not visible_modules:
        fallback = [m for m in ["POS", "Stock Dashboard", "Inventory"] if m in allowed_by_package]
        return sorted(fallback)

    return sorted(list(dict.fromkeys(visible_modules)))


# ============================================================
# get_navigation_menu - UPDATED WITH PACKAGE FILTERING
# ============================================================
def get_navigation_menu(role, branch_package=None):
    """Get the complete navigation structure based on role and package."""
    
    if branch_package is None:
        branch_package = st.session_state.get("branch_package", "Bronze")

    visible_modules = get_visible_modules(role, branch_package)

    # CASHIER - RESTRICTED MENU
    if role == "cashier":
        cashier_menu = {
            "Sales": ["POS", "Sales History"],
            "Scanner": ["Barcode Scanner"],
            "Customers": ["Customer Dashboard"],
            "Credit": ["Debtors", "Debtors Dashboard"],
            "Operations": ["Shift Management", "Documents"],
            "Financial": ["Floating Financials"],
        }
        # Filter out empty categories
        return {k: [i for i in v if i in visible_modules] for k, v in cashier_menu.items() if any(i in visible_modules for i in v)}

    # Category groupings for Manager and Owner
    categories = {
        "Sales": ["POS", "Sales Dashboard", "Sales History", "Returns & Refunds"],
        "Stock": [
            "Stock Dashboard", "Inventory", "Barcode Generator",
            "Barcode Scanner", "Duplicate Products", "Inventory Optimizer",
        ],
        "Purchases": [
            "Purchases", "Purchases Dashboard", "Supplier Bidding",
            "Supplier Bidding Portal", "Smart Replenishment",
        ],
        "Finance": [
            "Cash Dashboard", "Income", "Income Dashboard", "Expenses",
            "Expenses Dashboard", "P&L", "Financial Closing",
            "Payment Gateway", "Accounting Sync", "Floating Financials",
        ],
        "Customers": [
            "Customer Dashboard", "Customer 360 View", "Customer Insights 360",
            "Retention Dashboard", "Segmentation Dashboard", "Lifecycle Dashboard",
        ],
        "Credit & Debtors": ["Debtors", "Debtors Dashboard"],
        "Analytics": [
            "Reports Dashboard", "Business Advisor", "Demand Forecasting",
            "Predictive Analytics", "Profit Center Analysis", "Competitor Price Monitoring",
            "Churn Prediction", "Automated Insights", "Anomaly Detection",
            "Recommendation Engine",
        ],
        "Operations": [
            "Shift Management", "Live Dashboard", "Mobile Dashboard",
            "Voice Commands", "Automated Follow-up", "Workflow Approvals", "Documents",
        ],
        "Integrations": ["E-commerce Sync", "SMS Gateway"],
        "Admin": [
            "Security Dashboard", "Language Management", "Offline Mode", "PWA Setup",
            "API Developer", "Multi-Tenant", "White Label", "Branch Management",
            "Branch Performance", "User Management", "Settings",
        ],
    }

    filtered_menu = {}
    for category, items in categories.items():
        visible_items = [item for item in items if item in visible_modules]
        if visible_items:
            filtered_menu[category] = visible_items

    if not filtered_menu:
        return {
            "Sales": ["POS"],
            "Stock": ["Stock Dashboard", "Inventory"],
        }

    return filtered_menu


# ============================================================
# get_mobile_menu - UPDATED WITH PACKAGE FILTERING
# ============================================================
def get_mobile_menu(role, branch_package=None):
    """Get simplified mobile-optimized menu structure."""
    
    if branch_package is None:
        branch_package = st.session_state.get("branch_package", "Bronze")

    visible_modules = get_visible_modules(role, branch_package)

    if role == "cashier":
        cashier_mobile = {
            "Sales": ["POS", "Sales History"],
            "Scan": ["Barcode Scanner"],
            "Customers": ["Customer Dashboard"],
            "Credit": ["Debtors"],
            "Operations": ["Shift Management", "Documents"],
            "Financial": ["Floating Financials"],
        }
        return {k: [i for i in v if i in visible_modules] for k, v in cashier_mobile.items() if any(i in visible_modules for i in v)}

    mobile_menu = {
        "Dashboard": ["Mobile Dashboard"],
        "Sales": ["POS", "Sales History", "Returns & Refunds"],
        "Stock": ["Stock Dashboard", "Inventory", "Barcode Generator", "Barcode Scanner"],
        "Finance": [
            "Cash Dashboard", "P&L", "Financial Closing",
            "Payment Gateway", "Accounting Sync", "Floating Financials",
        ],
        "Customers": [
            "Customer Dashboard", "Customer 360 View", "Customer Insights 360",
        ],
        "Credit & Debtors": ["Debtors", "Debtors Dashboard"],
        "Intelligence": ["Demand Forecasting", "Live Dashboard", "Security Dashboard", "Language Management"],
        "Analytics": [
            "Profit Center Analysis", "Predictive Analytics", "Competitor Price Monitoring",
            "Churn Prediction", "Recommendation Engine", "Inventory Optimizer",
            "Anomaly Detection", "Automated Insights",
        ],
        "Purchases": ["Purchases", "Purchases Dashboard", "Supplier Bidding", "Smart Replenishment"],
        "E-commerce": ["E-commerce Sync"],
        "Communications": ["SMS Gateway", "Voice Commands"],
        "Automation": ["Automated Follow-up", "Workflow Approvals"],
        "Admin": [
            "User Management", "Settings", "Branch Management", "Branch Performance",
            "White Label", "Multi-Tenant", "API Developer", "PWA Setup",
            "Offline Mode", "Documents",
        ],
        "More": [],
    }

    filtered_menu = {}
    for category, items in mobile_menu.items():
        visible_items = [item for item in items if item in visible_modules]
        if visible_items:
            filtered_menu[category] = visible_items

    return filtered_menu


# ============================================================
# get_mobile_navigation_html - UPDATED WITH PACKAGE FILTERING
# ============================================================
def get_mobile_navigation_html(role, current_page, branch_package=None):
    """Generate HTML for mobile bottom navigation bar."""
    
    if branch_package is None:
        branch_package = st.session_state.get("branch_package", "Bronze")

    visible_modules = get_visible_modules(role, branch_package)

    nav_items = [
        {"icon": "DB", "label": "Dashboard", "page": "Mobile Dashboard"},
        {"icon": "PS", "label": "POS", "page": "POS"},
        {"icon": "ST", "label": "Stock", "page": "Stock Dashboard"},
        {"icon": "SL", "label": "Sales", "page": "Sales Dashboard"},
        {"icon": "RT", "label": "Returns", "page": "Returns & Refunds"},
        {"icon": "DC", "label": "Docs", "page": "Documents"},
        {"icon": "PF", "label": "Profit", "page": "Profit Center Analysis"},
        {"icon": "PD", "label": "Predict", "page": "Predictive Analytics"},
        {"icon": "PR", "label": "Price", "page": "Competitor Price Monitoring"},
        {"icon": "PY", "label": "Payment", "page": "Payment Gateway"},
        {"icon": "AC", "label": "Accounting", "page": "Accounting Sync"},
        {"icon": "EC", "label": "E-comm", "page": "E-commerce Sync"},
        {"icon": "SM", "label": "SMS", "page": "SMS Gateway"},
        {"icon": "VC", "label": "Voice", "page": "Voice Commands"},
        {"icon": "SC", "label": "Scan", "page": "Barcode Scanner"},
        {"icon": "RP", "label": "Replenish", "page": "Smart Replenishment"},
        {"icon": "AF", "label": "Auto", "page": "Automated Follow-up"},
        {"icon": "AN", "label": "Anomaly", "page": "Anomaly Detection"},
        {"icon": "AI", "label": "Insights", "page": "Automated Insights"},
        {"icon": "CH", "label": "Churn", "page": "Churn Prediction"},
        {"icon": "OP", "label": "Optimizer", "page": "Inventory Optimizer"},
        {"icon": "RC", "label": "Recommend", "page": "Recommendation Engine"},
        {"icon": "DT", "label": "Debtors", "page": "Debtors"},
        {"icon": "FF", "label": "Float", "page": "Floating Financials"},
        {"icon": "MO", "label": "More", "page": None},
    ]

    visible_nav = []
    for item in nav_items:
        if item["page"]:
            if item["page"] in visible_modules:
                visible_nav.append(item)
        else:
            visible_nav.append(item)

    nav_html = """
    <style>
        .mobile-bottom-nav {
            position: fixed; bottom: 0; left: 0; right: 0;
            background: white; display: flex; justify-content: space-around;
            padding: 10px 5px; box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
            z-index: 1000; border-top: 1px solid #e0e0e0;
        }
        .mobile-nav-item {
            text-align: center; flex: 1; padding: 5px; cursor: pointer;
            text-decoration: none; color: #666; transition: all 0.3s ease;
        }
        .mobile-nav-item.active { color: #667eea; }
        .mobile-nav-icon { font-size: 20px; display: block; font-weight: bold; }
        .mobile-nav-label { font-size: 11px; margin-top: 4px; display: block; }
        @media (min-width: 769px) { .mobile-bottom-nav { display: none; } }
        @media (max-width: 768px) { .main .block-container { padding-bottom: 80px !important; } }
    </style>
    <div class="mobile-bottom-nav">
    """

    for item in visible_nav:
        active_class = "active" if current_page == item["page"] else ""
        if item["page"]:
            nav_html += f"""
            <a href="#" class="mobile-nav-item {active_class}" onclick="window.location.href='?page={item["page"]}'">
                <span class="mobile-nav-icon">{item["icon"]}</span>
                <span class="mobile-nav-label">{item["label"]}</span>
            </a>
            """
        else:
            nav_html += f"""
            <div class="mobile-nav-item" onclick="document.querySelector('.mobile-menu-panel').classList.toggle('show')">
                <span class="mobile-nav-icon">{item["icon"]}</span>
                <span class="mobile-nav-label">{item["label"]}</span>
            </div>
            """

    nav_html += """
    </div>
    <style>
        .mobile-menu-panel {
            position: fixed; bottom: 70px; right: 10px; background: white;
            border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            padding: 10px 0; min-width: 150px; display: none; z-index: 1001;
        }
        .mobile-menu-panel.show { display: block; }
        .mobile-menu-item {
            padding: 12px 20px; text-decoration: none; color: #333;
            display: block; transition: background 0.2s;
        }
        .mobile-menu-item:hover { background: #f5f5f5; }
    </style>
    <div class="mobile-menu-panel">
    """

    more_items = get_mobile_menu(role, branch_package)
    for category, items in more_items.items():
        if category != "More" and category != "Admin":
            continue
        for item in items:
            nav_html += f'<a href="#" class="mobile-menu-item" onclick="window.location.href=\'?page={item}\'">{item}</a>'

    nav_html += """
    </div>
    <script>
        document.addEventListener('click', function(event) {
            if (!event.target.closest('.mobile-nav-item') && !event.target.closest('.mobile-menu-panel')) {
                document.querySelector('.mobile-menu-panel')?.classList.remove('show');
            }
        });
    </script>
    """
    return nav_html


# ============================================================
# get_menu_badge_counts - BRANCH-SCOPED
# ============================================================
def get_menu_badge_counts(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    badges = {}

    try:
        products_df = load_products(branch_id=branch_id)
        if products_df is not None and not products_df.empty:
            for col in ("stock", "reorder_level"):
                if col in products_df.columns:
                    products_df[col] = pd.to_numeric(products_df[col], errors="coerce").fillna(0)
            if "reorder_level" in products_df.columns:
                low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]])
                if low_stock > 0:
                    badges["Stock Dashboard"] = low_stock
                    badges["Inventory"] = low_stock
    except Exception as e:
        print(f"[role_based_menu] Low stock badge error: {e}")

    try:
        purchases_df = load_purchases(branch_id=branch_id)
        if purchases_df is not None and not purchases_df.empty and "status" in purchases_df.columns:
            pending = len(purchases_df[purchases_df["status"].astype(str).str.upper() == "PENDING"])
            if pending > 0:
                badges["Purchases"] = pending
                badges["Purchases Dashboard"] = pending
    except Exception as e:
        print(f"[role_based_menu] Pending purchases badge error: {e}")

    try:
        from backend.modules.returns_management import load_returns
        returns_df = load_returns(branch_id=branch_id) if "branch_id" in load_returns.__code__.co_varnames else load_returns()
        if returns_df is not None and not returns_df.empty and "status" in returns_df.columns:
            pending_returns = len(returns_df[returns_df["status"].astype(str).str.upper() == "PENDING"])
            if pending_returns > 0:
                badges["Returns & Refunds"] = pending_returns
    except Exception:
        pass

    return badges


# ============================================================
# render_sidebar_menu - BRANCH & PACKAGE AWARE
# ============================================================
def render_sidebar_menu(role, current_page, branch_id=None, branch_package=None):
    """Render the sidebar menu with badges, scoped to the given branch and package."""
    
    if branch_package is None:
        branch_package = st.session_state.get("branch_package", "Bronze")

    branch_id = _resolve_branch(branch_id)
    menu = get_navigation_menu(role, branch_package)
    badges = get_menu_badge_counts(branch_id=branch_id)

    st.sidebar.markdown("### Navigation")
    st.sidebar.caption(f"📍 {_branch_label(branch_id)}")

    selected_item = current_page

    for category, items in menu.items():
        st.sidebar.markdown(f"**{category}**")
        for item in items:
            badge_text = ""
            if item in badges:
                badge_text = (
                    f" <span style='background: #ef4444; color: white; "
                    f"border-radius: 10px; padding: 2px 8px; font-size: 11px; "
                    f"margin-left: 5px;'>{badges[item]}</span>"
                )

            button_key = f"nav_{item.replace(' ', '_').replace('&', '')}"

            if st.sidebar.button(
                f"{item}{badge_text}",
                key=button_key,
                use_container_width=True,
            ):
                selected_item = item
        st.sidebar.markdown("---")

    return selected_item


# ============================================================
# is_mobile_device - unchanged
# ============================================================
def is_mobile_device():
    try:
        from streamlit import runtime
        if runtime.exists():
            user_agent = st.context.headers.get("User-Agent", "")
            mobile_keywords = ["Mobile", "Android", "iPhone", "iPad", "iPod", "BlackBerry"]
            return any(keyword in user_agent for keyword in mobile_keywords)
    except Exception:
        pass
    return False