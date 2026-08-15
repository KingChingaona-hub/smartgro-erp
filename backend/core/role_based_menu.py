import streamlit as st
from backend.core.auth import can_access_feature

def _get_permission_key(item):
    """Helper function to map menu items to permission keys"""
    
    # NEW DATA SCIENCE MODULES
    if item == "Anomaly Detection":
        return "anomaly_detection"
    elif item == "Automated Insights":
        return "automated_insights"
    elif item == "Churn Prediction":
        return "churn_prediction"
    elif item == "Inventory Optimizer":
        return "inventory_optimizer"
    elif item == "Recommendation Engine":
        return "recommendation_engine"
    
    # FLOATING FINANCIALS
    elif item == "Floating Financials":
        return "floating_financials"
    
    # Existing mappings
    elif item == "Branch Management":
        return "branch_management"
    elif item == "Branch Performance":
        return "branch_performance"
    elif item == "User Management":
        return "user_management"
    elif item == "Shift Management":
        return "shift_management"
    elif item == "Settings":
        return "settings"
    elif item == "Mobile Dashboard":
        return "mobile_dashboard"
    elif item == "Demand Forecasting":
        return "demand_forecasting"
    elif item == "Live Dashboard":
        return "live_dashboard"
    elif item == "Barcode Generator":
        return "inventory_view"
    elif item == "Customer App":
        return "customer_app"
    elif item == "Customer Insights":
        return "customer_insights"
    elif item == "Security Dashboard":
        return "security"
    elif item == "Language Management":
        return "language_management"
    elif item == "Offline Mode":
        return "offline_mode"
    elif item == "Financial Closing":
        return "financial_closing"
    elif item == "Supplier Bidding":
        return "supplier_bidding"
    elif item == "Customer 360 View":
        return "customer_360"
    elif item == "Returns & Refunds":
        return "returns_management"
    elif item == "Documents":
        return "documents"
    elif item == "Profit Center Analysis":
        return "profit_analysis"
    elif item == "Predictive Analytics":
        return "predictive_analytics"
    elif item == "Competitor Price Monitoring":
        return "competitor_price"
    elif item == "Payment Gateway":
        return "payment_gateway"
    elif item == "Accounting Sync":
        return "accounting_sync"
    elif item == "E-commerce Sync":
        return "ecommerce_sync"
    elif item == "SMS Gateway":
        return "sms_gateway"
    elif item == "Smart Replenishment":
        return "smart_replenishment"
    elif item == "Automated Follow-up":
        return "automated_followup"
    elif item == "Workflow Approvals":
        return "workflow_approvals"
    elif item == "PWA Setup":
        return "pwa_setup"
    elif item == "Voice Commands":
        return "voice_commands"
    elif item == "Barcode Scanner":
        return "barcode_scanner"
    elif item == "White Label":
        return "white_label"
    elif item == "Multi-Tenant":
        return "multi_tenant"
    elif item == "API Developer":
        return "api_developer"
    elif item == "Debtors":
        return "debtors"
    elif item == "Debtors Dashboard":
        return "debtors_dashboard"
    elif item == "Business Advisor":
        return "business_advisor"
    elif item == "Sales History":
        return "sales_history"
    elif item == "Sales Dashboard":
        return "sales_dashboard"
    elif item == "Stock Dashboard":
        return "inventory_view"
    elif item == "Inventory":
        return "inventory_view"
    elif item == "POS":
        return "pos"
    elif item == "Customer Dashboard":
        return "customers"
    elif item == "Customer Insights 360":
        return "customer_360"
    elif item == "Retention Dashboard":
        return "customers"
    elif item == "Segmentation Dashboard":
        return "customers"
    elif item == "Lifecycle Dashboard":
        return "customers"
    elif item == "Reports Dashboard":
        return "reports"
    elif item == "Duplicate Products":
        return "inventory_view"
    elif item == "P&L":
        return "pl"
    elif item == "Income":
        return "income"
    elif item == "Income Dashboard":
        return "income"
    elif item == "Expenses":
        return "expenses"
    elif item == "Expenses Dashboard":
        return "expenses"
    elif item == "Cash Dashboard":
        return "cash_dashboard"
    elif item == "Purchases":
        return "purchases"
    elif item == "Purchases Dashboard":
        return "purchases"
    elif item == "Supplier Bidding Portal":
        return "supplier_bidding"
    
    # Return None if no mapping found - but we'll handle this differently
    return None


# ============================================================
# COMPLETE REWRITE - get_visible_modules FIXED
# ============================================================

def get_visible_modules(role):
    """Return ALL modules a role can access - FIXED VERSION"""
    
    # Define ALL modules with their permission keys
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
    
    # If owner, return ALL modules
    if role == "owner":
        return sorted([m["name"] for m in all_modules])
    
    # For other roles, filter based on permissions
    visible_modules = []
    for module in all_modules:
        # Check if role has permission for this module
        if can_access_feature(role, module["permission"]):
            visible_modules.append(module["name"])
    
    # Remove duplicates and sort
    visible_modules = sorted(list(dict.fromkeys(visible_modules)))
    
    return visible_modules


# ============================================================
# get_navigation_menu - KEPT FOR BACKWARD COMPATIBILITY
# ============================================================

def get_navigation_menu(role):
    """Get the complete navigation structure based on role - FIXED VERSION"""
    
    # Get all visible modules for this role
    visible_modules = get_visible_modules(role)
    
    # Define category groupings
    categories = {
        "🛒 Sales": ["POS", "Sales Dashboard", "Sales History", "Returns & Refunds"],
        "📦 Stock": ["Stock Dashboard", "Inventory", "Barcode Generator", "Barcode Scanner", "Duplicate Products", "Inventory Optimizer"],
        "📥 Purchases": ["Purchases", "Purchases Dashboard", "Supplier Bidding", "Supplier Bidding Portal", "Smart Replenishment"],
        "💰 Finance": ["Cash Dashboard", "Income", "Income Dashboard", "Expenses", "Expenses Dashboard", "P&L", "Financial Closing", "Payment Gateway", "Accounting Sync"],
        "👥 Customers": ["Customer Dashboard", "Customer 360 View", "Customer Insights 360", "Retention Dashboard", "Segmentation Dashboard", "Lifecycle Dashboard"],
        "💰 Credit & Debtors": ["Debtors", "Debtors Dashboard"],
        "💳 Floating Financials": ["Floating Financials"],
        "📊 Analytics": [
            "Reports Dashboard", "Business Advisor", "Demand Forecasting",
            "Predictive Analytics", "Profit Center Analysis", "Competitor Price Monitoring",
            "Churn Prediction", "Automated Insights", "Anomaly Detection", "Recommendation Engine"
        ],
        "🔄 Operations": ["Shift Management", "Live Dashboard", "Mobile Dashboard", "Voice Commands", "Automated Follow-up", "Workflow Approvals", "Documents"],
        "🛍️ Integrations": ["E-commerce Sync", "SMS Gateway"],
        "🔒 Admin": [
            "Security Dashboard", "Language Management", "Offline Mode", "PWA Setup",
            "API Developer", "Multi-Tenant", "White Label", "Branch Management",
            "Branch Performance", "User Management", "Settings"
        ]
    }
    
    # Build menu with only visible modules
    filtered_menu = {}
    for category, items in categories.items():
        visible_items = [item for item in items if item in visible_modules]
        if visible_items:
            filtered_menu[category] = visible_items
    
    # If no items found, return default fallback
    if not filtered_menu:
        return {
            "🛒 Sales": ["POS", "Sales History"],
            "📦 Stock": ["Stock Dashboard", "Inventory"],
            "👥 Customers": ["Customer Dashboard"],
        }
    
    return filtered_menu


# ============================================================
# get_mobile_menu - FIXED
# ============================================================

def get_mobile_menu(role):
    """Get simplified mobile-optimized menu structure"""
    
    visible_modules = get_visible_modules(role)
    
    # Simplified menu for mobile devices
    mobile_menu = {
        "Dashboard": ["Mobile Dashboard"],
        "Sales": ["POS", "Sales History", "Returns & Refunds"],
        "Stock": ["Stock Dashboard", "Inventory", "Barcode Generator", "Barcode Scanner"],
        "Finance": ["Cash Dashboard", "P&L", "Financial Closing", "Payment Gateway", "Accounting Sync", "Floating Financials"],
        "Customers": ["Customer Dashboard", "Customer 360 View", "Customer Insights 360"],
        "Credit & Debtors": ["Debtors", "Debtors Dashboard"],
        "Intelligence": ["Demand Forecasting", "Live Dashboard", "Security Dashboard", "Language Management"],
        "Analytics": [
            "Profit Center Analysis", "Predictive Analytics", "Competitor Price Monitoring",
            "Churn Prediction", "Recommendation Engine", "Inventory Optimizer",
            "Anomaly Detection", "Automated Insights"
        ],
        "Purchases": ["Purchases", "Purchases Dashboard", "Supplier Bidding", "Smart Replenishment"],
        "E-commerce": ["E-commerce Sync"],
        "Communications": ["SMS Gateway", "Voice Commands"],
        "Automation": ["Automated Follow-up", "Workflow Approvals"],
        "Admin": ["User Management", "Settings", "Branch Management", "Branch Performance", "White Label", "Multi-Tenant", "API Developer", "PWA Setup", "Offline Mode", "Documents"],
        "More": []
    }
    
    # Filter based on permissions
    filtered_menu = {}
    for category, items in mobile_menu.items():
        visible_items = [item for item in items if item in visible_modules]
        if visible_items:
            filtered_menu[category] = visible_items
    
    return filtered_menu


# ============================================================
# get_mobile_navigation_html - FIXED
# ============================================================

def get_mobile_navigation_html(role, current_page):
    """Generate HTML for mobile bottom navigation bar"""
    
    visible_modules = get_visible_modules(role)
    
    # Define bottom navigation items
    nav_items = [
        {"icon": "📊", "label": "Dashboard", "page": "Mobile Dashboard"},
        {"icon": "🛒", "label": "POS", "page": "POS"},
        {"icon": "📦", "label": "Stock", "page": "Stock Dashboard"},
        {"icon": "💰", "label": "Sales", "page": "Sales Dashboard"},
        {"icon": "🔄", "label": "Returns", "page": "Returns & Refunds"},
        {"icon": "📄", "label": "Docs", "page": "Documents"},
        {"icon": "📊", "label": "Profit", "page": "Profit Center Analysis"},
        {"icon": "🔮", "label": "Predict", "page": "Predictive Analytics"},
        {"icon": "🏪", "label": "Price", "page": "Competitor Price Monitoring"},
        {"icon": "💳", "label": "Payment", "page": "Payment Gateway"},
        {"icon": "📊", "label": "Accounting", "page": "Accounting Sync"},
        {"icon": "🛍️", "label": "E-comm", "page": "E-commerce Sync"},
        {"icon": "📱", "label": "SMS", "page": "SMS Gateway"},
        {"icon": "🎤", "label": "Voice", "page": "Voice Commands"},
        {"icon": "📷", "label": "Scan", "page": "Barcode Scanner"},
        {"icon": "📦", "label": "Replenish", "page": "Smart Replenishment"},
        {"icon": "🤖", "label": "Auto", "page": "Automated Follow-up"},
        {"icon": "🔬", "label": "Anomaly", "page": "Anomaly Detection"},
        {"icon": "📧", "label": "Insights", "page": "Automated Insights"},
        {"icon": "🎯", "label": "Churn", "page": "Churn Prediction"},
        {"icon": "📊", "label": "Optimizer", "page": "Inventory Optimizer"},
        {"icon": "🛍️", "label": "Recommend", "page": "Recommendation Engine"},
        {"icon": "💰", "label": "Debtors", "page": "Debtors"},
        {"icon": "💳", "label": "Float", "page": "Floating Financials"},
        {"icon": "⚙️", "label": "More", "page": None}
    ]
    
    # Filter by permissions
    visible_nav = []
    for item in nav_items:
        if item["page"]:
            if item["page"] in visible_modules:
                visible_nav.append(item)
        else:
            visible_nav.append(item)
    
    # Generate HTML
    nav_html = """
    <style>
        .mobile-bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: white;
            display: flex;
            justify-content: space-around;
            padding: 10px 5px;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
            border-top: 1px solid #e0e0e0;
        }
        .mobile-nav-item {
            text-align: center;
            flex: 1;
            padding: 5px;
            cursor: pointer;
            text-decoration: none;
            color: #666;
            transition: all 0.3s ease;
        }
        .mobile-nav-item.active {
            color: #667eea;
        }
        .mobile-nav-icon {
            font-size: 24px;
            display: block;
        }
        .mobile-nav-label {
            font-size: 11px;
            margin-top: 4px;
            display: block;
        }
        @media (min-width: 769px) {
            .mobile-bottom-nav {
                display: none;
            }
        }
        @media (max-width: 768px) {
            .main .block-container {
                padding-bottom: 80px !important;
            }
        }
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
            position: fixed;
            bottom: 70px;
            right: 10px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            padding: 10px 0;
            min-width: 150px;
            display: none;
            z-index: 1001;
        }
        .mobile-menu-panel.show {
            display: block;
        }
        .mobile-menu-item {
            padding: 12px 20px;
            text-decoration: none;
            color: #333;
            display: block;
            transition: background 0.2s;
        }
        .mobile-menu-item:hover {
            background: #f5f5f5;
        }
    </style>
    <div class="mobile-menu-panel">
    """
    
    # Add more menu items
    more_items = get_mobile_menu(role)
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


def get_menu_badge_counts():
    """Get notification badge counts for menu items"""
    from backend.core.db_adapter import load_products
    
    badges = {}
    
    # Low stock badge
    products_df = load_products()
    if not products_df.empty:
        low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]])
        if low_stock > 0:
            badges["Stock Dashboard"] = low_stock
        if low_stock > 3:
            badges["Inventory"] = low_stock
    
    # Pending purchases badge
    from backend.core.db_adapter import load_purchases
    purchases_df = load_purchases()
    if not purchases_df.empty:
        pending = len(purchases_df[purchases_df["status"] == "PENDING"])
        if pending > 0:
            badges["Purchases"] = pending
            badges["Purchases Dashboard"] = pending
    
    # Pending returns badge
    from backend.modules.returns_management import load_returns
    returns_df = load_returns()
    if not returns_df.empty:
        pending_returns = len(returns_df[returns_df["status"] == "PENDING"])
        if pending_returns > 0:
            badges["Returns & Refunds"] = pending_returns
    
    return badges


def render_sidebar_menu(role, current_page):
    """Render the sidebar menu with badges"""
    
    menu = get_navigation_menu(role)
    badges = get_menu_badge_counts()
    
    st.sidebar.markdown("### Navigation")
    
    for category, items in menu.items():
        st.sidebar.markdown(f"**{category}**")
        for item in items:
            # Add badge if exists
            badge_text = ""
            if item in badges:
                badge_text = f" <span style='background: #ef4444; color: white; border-radius: 10px; padding: 2px 8px; font-size: 11px; margin-left: 5px;'>{badges[item]}</span>"
            
            button_key = f"nav_{item.replace(' ', '_').replace('&', '')}"
            
            if st.sidebar.button(
                f"{item}{badge_text}", 
                key=button_key, 
                use_container_width=True
            ):
                return item
        st.sidebar.markdown("---")
    
    return current_page


def is_mobile_device():
    """Detect if current device is mobile"""
    try:
        from streamlit import runtime
        if runtime.exists():
            user_agent = st.context.headers.get("User-Agent", "")
            mobile_keywords = ["Mobile", "Android", "iPhone", "iPad", "iPod", "BlackBerry"]
            return any(keyword in user_agent for keyword in mobile_keywords)
    except:
        pass
    return False