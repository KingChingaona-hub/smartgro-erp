import streamlit as st
from backend.core.auth import can_access_feature

def get_visible_modules(role):
    """Return modules visible to a specific role"""
    
    # All available modules with their required permission
    all_modules = {
        # Stock Management
        "Stock Dashboard": "inventory_view",
        "Inventory": "inventory_view",
        "Barcode Generator": "inventory_view",
        
        # Sales
        "POS": "pos",
        "Sales History": "sales_history",
        "Sales Dashboard": "sales_dashboard",
        
        # Finance
        "Cash Dashboard": "cash_dashboard",
        "Income": "income",
        "Income Dashboard": "income",
        "Expenses": "expenses",
        "Expenses Dashboard": "expenses",
        "P&L": "pl",
        "Financial Closing": "financial_closing",
        
        # Purchases
        "Purchases": "purchases",
        "Purchases Dashboard": "purchases",
        "Supplier Bidding": "supplier_bidding",
        
        # Customers
        "Customer Dashboard": "customers",
        "Retention Dashboard": "customers",
        "Segmentation Dashboard": "customers",
        "Lifecycle Dashboard": "customers",
        "Customer App": "customer_app",
        "Customer Insights": "customer_insights",
        "Customer 360 View": "customer_360",
        
        # Intelligence
        "Business Advisor": "business_advisor",
        "Debtors": "debtors",
        "Debtors Dashboard": "debtors_dashboard",
        "Demand Forecasting": "demand_forecasting",
        "Live Dashboard": "live_dashboard",
        "Security Dashboard": "security",
        "Language Management": "language_management",
        
        # Reports
        "Reports Dashboard": "reports",
        
        # Operations
        "Shift Management": "shift_management",
        
        # Mobile
        "Mobile Dashboard": "mobile_dashboard",
        
        # Returns & Refunds
        "Returns & Refunds": "returns_management",
        
        # Professional Documents
        "Documents": "documents",
        
        # Analytics Features
        "Profit Center Analysis": "profit_analysis",
        "Predictive Analytics": "predictive_analytics",
        "Competitor Price Monitoring": "competitor_price",
        
        # Payment Gateway
        "Payment Gateway": "payment_gateway",
        
        # Accounting Sync
        "Accounting Sync": "accounting_sync",
        
        # E-commerce Sync
        "E-commerce Sync": "ecommerce_sync",
        
        # SMS Gateway
        "SMS Gateway": "sms_gateway",
        
        # Smart Replenishment
        "Smart Replenishment": "smart_replenishment",
        
        # Automated Follow-up
        "Automated Follow-up": "automated_followup",
        
        # Workflow Approvals
        "Workflow Approvals": "workflow_approvals",
        
        # Progressive Web App (PWA)
        "PWA Setup": "pwa_setup",
        
        # Voice Commands
        "Voice Commands": "voice_commands",
        
        # Barcode Scanner
        "Barcode Scanner": "barcode_scanner",
        
        # White Label
        "White Label": "white_label",
        
        # Multi-Tenant
        "Multi-Tenant": "multi_tenant",
        
        # API Developer
        "API Developer": "api_developer",
        
        # Administration (Owner only)
        "Branch Management": "branch_management",
        "Branch Performance": "branch_performance",
        "Settings": "settings",
        "User Management": "user_management",
        "Offline Mode": "offline_mode"
    }
    
    visible_modules = []
    for module, permission in all_modules.items():
        if can_access_feature(role, permission):
            visible_modules.append(module)
    
    return visible_modules


def get_navigation_menu(role):
    """Get the complete navigation structure based on role"""
    
    # Define menu hierarchy with emoji icons
    menu_structure = {
        "📦 Stock": ["Stock Dashboard", "Inventory", "Barcode Generator"],
        "💰 Sales": ["POS", "Sales History", "Sales Dashboard", "Returns & Refunds"],
        "💳 Finance": ["Cash Dashboard", "Income", "Income Dashboard", "Expenses", "Expenses Dashboard", "P&L", "Financial Closing", "Payment Gateway", "Accounting Sync"],
        "📥 Purchases": ["Purchases", "Purchases Dashboard", "Supplier Bidding"],
        "👥 Customers": ["Customer Dashboard", "Retention Dashboard", "Segmentation Dashboard", "Lifecycle Dashboard", "Customer App", "Customer Insights", "Customer 360 View"],
        "🤖 Intelligence": ["Business Advisor", "Debtors", "Debtors Dashboard", "Demand Forecasting", "Live Dashboard", "Security Dashboard", "Language Management"],
        "📊 Analytics": ["Profit Center Analysis", "Predictive Analytics", "Competitor Price Monitoring"],
        "📁 Reports": ["Reports Dashboard", "Documents"],
        "🔄 Operations": ["Shift Management"],
        "📱 Mobile": ["Mobile Dashboard"],
        "🛍️ E-commerce": ["E-commerce Sync"],
        "📱 Communications": ["SMS Gateway", "Voice Commands"],
        "📷 Scanner": ["Barcode Scanner"],
        "📦 Replenishment": ["Smart Replenishment"],
        "🤖 Automation": ["Automated Follow-up", "Workflow Approvals"],
        "⚙️ Administration": ["White Label", "Multi-Tenant", "API Developer", "PWA Setup", "User Management", "Branch Management", "Branch Performance", "Settings", "Offline Mode"]
    }
    
    # Cashier gets simplified mobile view
    if role == "cashier":
        menu_structure = {
            "🛒 POS": ["POS"],
            "📊 Today": ["Mobile Dashboard"],
            "📜 History": ["Sales History"],
            "📦 Stock": ["Stock Dashboard", "Barcode Generator"],
            "🎤 Voice": ["Voice Commands"],
            "📷 Scanner": ["Barcode Scanner"]
        }
    
    # Filter based on role permissions
    filtered_menu = {}
    for category, items in menu_structure.items():
        visible_items = []
        for item in items:
            # Map menu item to permission key
            perm_key = None
            
            if item == "Branch Management":
                perm_key = "branch_management"
            elif item == "Branch Performance":
                perm_key = "branch_performance"
            elif item == "User Management":
                perm_key = "user_management"
            elif item == "Shift Management":
                perm_key = "shift_management"
            elif item == "Settings":
                perm_key = "settings"
            elif item == "Mobile Dashboard":
                perm_key = "mobile_dashboard"
            elif item == "Demand Forecasting":
                perm_key = "demand_forecasting"
            elif item == "Live Dashboard":
                perm_key = "live_dashboard"
            elif item == "Barcode Generator":
                perm_key = "inventory_view"
            elif item == "Customer App":
                perm_key = "customer_app"
            elif item == "Customer Insights":
                perm_key = "customer_insights"
            elif item == "Security Dashboard":
                perm_key = "security"
            elif item == "Language Management":
                perm_key = "language_management"
            elif item == "Offline Mode":
                perm_key = "offline_mode"
            elif item == "Financial Closing":
                perm_key = "financial_closing"
            elif item == "Supplier Bidding":
                perm_key = "supplier_bidding"
            elif item == "Customer 360 View":
                perm_key = "customer_360"
            elif item == "Returns & Refunds":
                perm_key = "returns_management"
            elif item == "Documents":
                perm_key = "documents"
            elif item == "Profit Center Analysis":
                perm_key = "profit_analysis"
            elif item == "Predictive Analytics":
                perm_key = "predictive_analytics"
            elif item == "Competitor Price Monitoring":
                perm_key = "competitor_price"
            elif item == "Payment Gateway":
                perm_key = "payment_gateway"
            elif item == "Accounting Sync":
                perm_key = "accounting_sync"
            elif item == "E-commerce Sync":
                perm_key = "ecommerce_sync"
            elif item == "SMS Gateway":
                perm_key = "sms_gateway"
            elif item == "Smart Replenishment":
                perm_key = "smart_replenishment"
            elif item == "Automated Follow-up":
                perm_key = "automated_followup"
            elif item == "Workflow Approvals":
                perm_key = "workflow_approvals"
            elif item == "PWA Setup":
                perm_key = "pwa_setup"
            elif item == "Voice Commands":
                perm_key = "voice_commands"
            elif item == "Barcode Scanner":
                perm_key = "barcode_scanner"
            elif item == "White Label":
                perm_key = "white_label"
            elif item == "Multi-Tenant":
                perm_key = "multi_tenant"
            elif item == "API Developer":
                perm_key = "api_developer"
            
            # Check if user has permission
            if perm_key:
                if can_access_feature(role, perm_key):
                    visible_items.append(item)
            else:
                # For items without specific permission, check default
                default_key = item.lower().replace(" ", "_")
                if can_access_feature(role, default_key):
                    visible_items.append(item)
        
        if visible_items:
            filtered_menu[category] = visible_items
    
    return filtered_menu


def get_mobile_menu(role):
    """Get simplified mobile-optimized menu structure"""
    
    # Simplified menu for mobile devices
    mobile_menu = {
        "📊 Dashboard": ["Mobile Dashboard"],
        "🛒 Sales": ["POS", "Sales History", "Returns & Refunds"],
        "📦 Stock": ["Stock Dashboard", "Inventory", "Barcode Generator"],
        "💰 Finance": ["Cash Dashboard", "P&L", "Financial Closing", "Payment Gateway", "Accounting Sync"],
        "👥 Customers": ["Customer Dashboard", "Customer App", "Customer 360 View"],
        "🤖 Intelligence": ["Demand Forecasting", "Live Dashboard", "Security Dashboard", "Language Management"],
        "📊 Analytics": ["Profit Center Analysis", "Predictive Analytics", "Competitor Price Monitoring"],
        "🛍️ E-commerce": ["E-commerce Sync"],
        "📱 Communications": ["SMS Gateway", "Voice Commands"],
        "📷 Scanner": ["Barcode Scanner"],
        "📦 Replenishment": ["Smart Replenishment"],
        "🤖 Automation": ["Automated Follow-up", "Workflow Approvals"],
        "⚙️ More": []
    }
    
    # Add role-specific items
    if role in ["manager", "owner"]:
        mobile_menu["⚙️ More"].extend(["Purchases", "Expenses", "Reports Dashboard", "Customer Insights", "Offline Mode", "Supplier Bidding", "Documents", "PWA Setup", "API Developer"])
    
    if role == "owner":
        mobile_menu["⚙️ More"].extend(["User Management", "Settings", "Branch Management", "White Label", "Multi-Tenant"])
    
    if role == "manager":
        mobile_menu["⚙️ More"].extend(["Branch Performance"])
    
    # Filter based on permissions
    filtered_menu = {}
    for category, items in mobile_menu.items():
        visible_items = []
        for item in items:
            perm_key = None
            
            if item == "Mobile Dashboard":
                perm_key = "mobile_dashboard"
            elif item == "Branch Management":
                perm_key = "branch_management"
            elif item == "Settings":
                perm_key = "settings"
            elif item == "User Management":
                perm_key = "user_management"
            elif item == "Demand Forecasting":
                perm_key = "demand_forecasting"
            elif item == "Live Dashboard":
                perm_key = "live_dashboard"
            elif item == "Barcode Generator":
                perm_key = "inventory_view"
            elif item == "Customer App":
                perm_key = "customer_app"
            elif item == "Customer Insights":
                perm_key = "customer_insights"
            elif item == "Security Dashboard":
                perm_key = "security"
            elif item == "Language Management":
                perm_key = "language_management"
            elif item == "Offline Mode":
                perm_key = "offline_mode"
            elif item == "Financial Closing":
                perm_key = "financial_closing"
            elif item == "Supplier Bidding":
                perm_key = "supplier_bidding"
            elif item == "Customer 360 View":
                perm_key = "customer_360"
            elif item == "Returns & Refunds":
                perm_key = "returns_management"
            elif item == "Documents":
                perm_key = "documents"
            elif item == "Profit Center Analysis":
                perm_key = "profit_analysis"
            elif item == "Predictive Analytics":
                perm_key = "predictive_analytics"
            elif item == "Competitor Price Monitoring":
                perm_key = "competitor_price"
            elif item == "Payment Gateway":
                perm_key = "payment_gateway"
            elif item == "Accounting Sync":
                perm_key = "accounting_sync"
            elif item == "E-commerce Sync":
                perm_key = "ecommerce_sync"
            elif item == "SMS Gateway":
                perm_key = "sms_gateway"
            elif item == "Smart Replenishment":
                perm_key = "smart_replenishment"
            elif item == "Automated Follow-up":
                perm_key = "automated_followup"
            elif item == "Workflow Approvals":
                perm_key = "workflow_approvals"
            elif item == "PWA Setup":
                perm_key = "pwa_setup"
            elif item == "Voice Commands":
                perm_key = "voice_commands"
            elif item == "Barcode Scanner":
                perm_key = "barcode_scanner"
            elif item == "White Label":
                perm_key = "white_label"
            elif item == "Multi-Tenant":
                perm_key = "multi_tenant"
            elif item == "API Developer":
                perm_key = "api_developer"
            
            if perm_key and can_access_feature(role, perm_key):
                visible_items.append(item)
            elif not perm_key:
                default_key = item.lower().replace(" ", "_")
                if can_access_feature(role, default_key):
                    visible_items.append(item)
        
        # Don't show empty categories
        if visible_items or category == "⚙️ More":
            filtered_menu[category] = visible_items
    
    return filtered_menu


def get_mobile_navigation_html(role, current_page):
    """Generate HTML for mobile bottom navigation bar"""
    
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
        {"icon": "⚙️", "label": "More", "page": None}
    ]
    
    # Filter by permissions
    visible_nav = []
    for item in nav_items:
        if item["page"]:
            perm_key = item["page"].lower().replace(" ", "_")
            if can_access_feature(role, perm_key):
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
        /* Add padding to main content for mobile */
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
        if category != "⚙️ More":
            continue
        for item in items:
            nav_html += f'<a href="#" class="mobile-menu-item" onclick="window.location.href=\'?page={item}\'">{item}</a>'
    
    nav_html += """
    </div>
    <script>
        // Close menu when clicking outside
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
    from backend.core.database import load_products
    
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
    from backend.core.database import load_purchases
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
    
    st.sidebar.markdown("### 📋 Navigation")
    
    for category, items in menu.items():
        st.sidebar.markdown(f"**{category}**")
        for item in items:
            # Add badge if exists
            badge_text = ""
            if item in badges:
                badge_text = f" <span style='background: #ef4444; color: white; border-radius: 10px; padding: 2px 8px; font-size: 11px; margin-left: 5px;'>{badges[item]}</span>"
            
            button_key = f"nav_{item.replace(' ', '_').replace('&', '')}"
            
            if st.sidebar.button(
                f"📌 {item}{badge_text}", 
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