import streamlit as st

# ==============================
# MODULE CONFIG (ICONS + LABELS) - ALPHABETICAL ORDER
# ==============================
MODULES = {
    "Accounting Sync": "📊",
    "Anomaly Detection": "🚨",
    "API Developer": "🔗",
    "Automated Follow-up": "🤖",
    "Automated Insights": "📧",
    "Barcode Generator": "🏷️",
    "Barcode Scanner": "📷",
    "Branch Management": "🏢",
    "Business Advisor": "🤖",
    "Cash": "💳",
    "Churn Prediction": "🎯",
    "Competitor Price Monitoring": "🏪",
    "Credit & Debtors": "⏱️",
    "Customer 360 View": "👤",
    "Customer App": "🎁",
    "Customers": "👥",
    "Demand Forecasting": "🤖",
    "E-commerce Sync": "🛍️",
    "Expenses": "💸",
    "Financial Closing": "💰",
    "Income": "📈",
    "Inventory Optimizer": "📊",
    "Language Management": "🌐",
    "Live Dashboard": "⚡",
    "Mobile": "📱",
    "Multi-Tenant": "🏢",
    "Offline Mode": "📡",
    "P&L": "📊",
    "Payment Gateway": "💳",
    "POS": "🛒",
    "Predictive Analytics": "🔮",
    "Profit Center Analysis": "📊",
    "Purchases": "📥",
    "PWA Setup": "📱",
    "Recommendation Engine": "🛍️",
    "Reports": "📁",
    "Returns & Refunds": "🔄",
    "Sales": "💰",
    "Security Dashboard": "🔒",
    "Shift Management": "🔄",
    "Smart Replenishment": "📦",
    "SMS Gateway": "📱",
    "Stock": "📦",
    "Supplier Bidding": "🏪",
    "Voice Commands": "🎤",
    "White Label": "🏷️",
    "Workflow Approvals": "✅"
}

# ==============================
# CUSTOMER SUB MENU (Alphabetical)
# ==============================
CUSTOMER_SUB = {
    "Business Advisor": "🤖",
    "Customer 360 View": "👤",
    "Customer App": "🎁",
    "Customer Dashboard": "📊",
    "Customer Insights": "📈",
    "Lifecycle Dashboard": "🔄",
    "Retention Dashboard": "🔁",
    "Segmentation Dashboard": "🧠"
}

# ==============================
# ROLE-BASED MENU
# ==============================
def get_navigation_menu(role):
    """Get navigation menu based on user role"""
    
    # Base menu for all users
    base_menu = [
        "Stock",
        "POS",
        "Sales",
        "Customers",
        "Credit & Debtors"  # Now accessible to cashiers
    ]
    
    # Manager adds more features
    manager_menu = base_menu + [
        "Purchases",
        "Income",
        "Expenses",
        "Cash",
        "P&L",
        "Shift Management",
        "Reports",
        "Demand Forecasting",
        "Live Dashboard",
        "Barcode Generator",
        "Barcode Scanner",
        "Competitor Price Monitoring",
        "Predictive Analytics",
        "Profit Center Analysis",
        "Smart Replenishment",
        "Supplier Bidding",
        "Automated Follow-up",
        "Workflow Approvals",
        "Security Dashboard",
        "Language Management",
        "Offline Mode",
        "Financial Closing",
        "Payment Gateway",
        "Accounting Sync",
        "E-commerce Sync",
        "SMS Gateway",
        "Mobile",
        "Voice Commands",
        "API Developer",
        "Business Advisor",
        # Data Science Modules
        "Anomaly Detection",
        "Automated Insights",
        "Churn Prediction",
        "Inventory Optimizer",
        "Recommendation Engine"
    ]
    
    # Owner adds admin features
    owner_menu = manager_menu + [
        "Branch Management",
        "Multi-Tenant",
        "PWA Setup",
        "White Label",
        "Returns & Refunds"
    ]
    
    if role == "owner":
        return owner_menu
    elif role == "manager":
        return manager_menu
    elif role == "cashier":
        return base_menu
    else:
        return ["Stock", "Sales", "Customers", "Credit & Debtors"]

# ==============================
# MAIN MENU - FLAT ALPHABETICAL (NO CATEGORIES)
# ==============================
def main_menu():
    st.sidebar.title("AZIEL ERP")
    
    # Get user role
    role = st.session_state.get("role", "cashier")
    
    # Get menu based on role
    available_modules = get_navigation_menu(role)
    
    # Filter MODULES to only show available ones
    filtered_modules = {k: v for k, v in MODULES.items() if k in available_modules}
    
    # Sort modules alphabetically
    sorted_modules = sorted(filtered_modules.items())
    menu_items = [f"{icon} {name}" for name, icon in sorted_modules]
    
    # Display as a flat list without any category headers
    if menu_items:
        module = st.sidebar.radio(
            "Modules",
            menu_items,
            key="main_menu_radio"
        )
        return module.split(" ", 1)[1]
    else:
        st.sidebar.warning("No modules available for your role")
        return "Stock"

# ==============================
# SUB MENU - ALPHABETICAL
# ==============================
def sub_menu(module):
    
    # ==============================
    # STOCK
    # ==============================
    if module == "Stock":
        options = ["Barcode Generator", "Inventory", "Stock Dashboard"]
        choice = st.sidebar.radio("Stock Menu", options, key="stock_menu_radio")
        return choice
    
    # ==============================
    # SALES
    # ==============================
    elif module == "Sales":
        options = ["Returns & Refunds", "Sales Dashboard", "Sales History"]
        choice = st.sidebar.radio("Sales Menu", options, key="sales_menu_radio")
        return choice
    
    # ==============================
    # PURCHASES
    # ==============================
    elif module == "Purchases":
        options = ["Purchases", "Purchases Dashboard", "Supplier Bidding"]
        choice = st.sidebar.radio("Purchases Menu", options, key="purchases_menu_radio")
        return choice
    
    # ==============================
    # INCOME
    # ==============================
    elif module == "Income":
        options = ["Income", "Income Dashboard"]
        choice = st.sidebar.radio("Income Menu", options, key="income_menu_radio")
        return choice
    
    # ==============================
    # EXPENSES
    # ==============================
    elif module == "Expenses":
        options = ["Expenses", "Expenses Dashboard"]
        choice = st.sidebar.radio("Expenses Menu", options, key="expenses_menu_radio")
        return choice
    
    # ==============================
    # CUSTOMERS
    # ==============================
    elif module == "Customers":
        sorted_customers = sorted(CUSTOMER_SUB.items())
        customer_items = [f"{icon} {name}" for name, icon in sorted_customers]
        choice = st.sidebar.radio("Customer Menu", customer_items, key="customers_menu_radio")
        return choice.split(" ", 1)[1]
    
    # ==============================
    # CREDIT & DEBTORS - UPDATED FOR CASHIERS
    # ==============================
    elif module == "Credit & Debtors":
        options = ["Debtors", "Debtors Dashboard"]
        choice = st.sidebar.radio("Debtors Menu", options, key="debtors_menu_radio")
        return choice
    
    # ==============================
    # RETURNS & REFUNDS
    # ==============================
    elif module == "Returns & Refunds":
        options = [
            "Process Return",
            "Store Credit",
            "Warranty Check",
            "Return Analytics",
            "Return History"
        ]
        choice = st.sidebar.radio("Returns Menu", options, key="returns_menu_radio")
        return choice
    
    # ==============================
    # SINGLE PAGE MODULES (No sub-menu)
    # ==============================
    elif module == "POS":
        return "POS"
    
    elif module == "Cash":
        return "Cash Dashboard"
    
    elif module == "P&L":
        return "P&L"
    
    elif module == "Reports":
        return "Reports Dashboard"
    
    elif module == "Shift Management":
        return "Shift Management"
    
    elif module == "Branch Management":
        return "Branch Management"
    
    elif module == "Mobile":
        return "Mobile Dashboard"
    
    elif module == "Demand Forecasting":
        return "Demand Forecasting"
    
    elif module == "Live Dashboard":
        return "Live Dashboard"
    
    elif module == "Barcode Generator":
        return "Barcode Generator"
    
    elif module == "Customer App":
        return "Customer App"
    
    elif module == "Security Dashboard":
        return "Security Dashboard"
    
    elif module == "Language Management":
        return "Language Management"
    
    elif module == "Offline Mode":
        return "Offline Mode"
    
    elif module == "Financial Closing":
        return "Financial Closing"
    
    elif module == "Supplier Bidding":
        return "Supplier Bidding"
    
    elif module == "Customer 360 View":
        return "Customer 360 View"
    
    elif module == "Profit Center Analysis":
        return "Profit Center Analysis"
    
    elif module == "Predictive Analytics":
        return "Predictive Analytics"
    
    elif module == "Competitor Price Monitoring":
        return "Competitor Price Monitoring"
    
    elif module == "Payment Gateway":
        return "Payment Gateway"
    
    elif module == "Accounting Sync":
        return "Accounting Sync"
    
    elif module == "E-commerce Sync":
        return "E-commerce Sync"
    
    elif module == "SMS Gateway":
        return "SMS Gateway"
    
    elif module == "Smart Replenishment":
        return "Smart Replenishment"
    
    elif module == "Automated Follow-up":
        return "Automated Follow-up"
    
    elif module == "Workflow Approvals":
        return "Workflow Approvals"
    
    elif module == "PWA Setup":
        return "PWA Setup"
    
    elif module == "Voice Commands":
        return "Voice Commands"
    
    elif module == "Barcode Scanner":
        return "Barcode Scanner"
    
    elif module == "White Label":
        return "White Label"
    
    elif module == "Multi-Tenant":
        return "Multi-Tenant"
    
    elif module == "API Developer":
        return "API Developer"
    
    elif module == "Business Advisor":
        return "Business Advisor"
    
    # ==============================
    # NEW DATA SCIENCE MODULES - SINGLE PAGE
    # ==============================
    elif module == "Anomaly Detection":
        return "Anomaly Detection"
    
    elif module == "Automated Insights":
        return "Automated Insights"
    
    elif module == "Churn Prediction":
        return "Churn Prediction"
    
    elif module == "Inventory Optimizer":
        return "Inventory Optimizer"
    
    elif module == "Recommendation Engine":
        return "Recommendation Engine"
    
    # ==============================
    # FALLBACK
    # ==============================
    return module