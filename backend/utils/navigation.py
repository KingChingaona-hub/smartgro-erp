import streamlit as st

# ==============================
# MODULE CONFIG (ICONS + LABELS)
# ==============================
MODULES = {
    "Stock": "📦",
    "Sales": "💰",
    "POS": "🛒",
    "Cash": "💳",
    "Purchases": "📥",
    "Income": "📈",
    "Expenses": "💸",
    "P&L": "📊",
    "Customers": "👥",
    "Credit & Debtors": "⏱️",
    "Reports": "📁",
    "Shift Management": "🔄",
    "Branch Management": "🏢",
    "Mobile": "📱",
    "Demand Forecasting": "🤖",
    "Live Dashboard": "⚡",
    "Barcode Generator": "🏷️",
    "Customer App": "🎁",
    "Security Dashboard": "🔒",
    "Language Management": "🌐",
    "Offline Mode": "📡",
    "Financial Closing": "💰",
    "Supplier Bidding": "🏪",
    "Customer 360 View": "👤",
    "Returns & Refunds": "🔄",
    "Profit Center Analysis": "📊",
    "Predictive Analytics": "🔮",
    "Competitor Price Monitoring": "🏪",
    "Payment Gateway": "💳",
    "Accounting Sync": "📊",
    "E-commerce Sync": "🛍️",
    "SMS Gateway": "📱",
    "Smart Replenishment": "📦",
    "Automated Follow-up": "🤖",
    "Workflow Approvals": "✅",
    "PWA Setup": "📱",
    "Voice Commands": "🎤",
    "Barcode Scanner": "📷",
    "White Label": "🏷️",
    "Multi-Tenant": "🏢",
    "API Developer": "🔗"
}

CUSTOMER_SUB = {
    "Customer Dashboard": "📊",
    "Retention Dashboard": "🔁",
    "Segmentation Dashboard": "🧠",
    "Lifecycle Dashboard": "🔄",
    "Business Advisor": "🤖",
    "Customer App": "🎁",
    "Customer Insights": "📈",
    "Customer 360 View": "👤"
}


# ==============================
# MAIN MENU
# ==============================
def main_menu():

    st.sidebar.title("AZIEL ERP")

    module = st.sidebar.radio(
        "Modules",
        [f"{icon} {name}" for name, icon in MODULES.items()]
    )

    # remove icon when returning logic key
    return module.split(" ", 1)[1]


# ==============================
# SUB MENU
# ==============================
def sub_menu(module):

    if module == "Stock":
        choice = st.sidebar.radio(
            "Stock Menu",
            ["Stock Dashboard", "Inventory", "Barcode Generator"]
        )
        return choice

    elif module == "Sales":
        choice = st.sidebar.radio(
            "Sales Menu",
            ["Sales History", "Sales Dashboard", "Returns & Refunds"]
        )
        return choice

    elif module == "Purchases":
        return st.sidebar.radio(
            "Purchases Menu",
            ["Purchases", "Purchases Dashboard", "Supplier Bidding"]
        )

    elif module == "Income":
        return st.sidebar.radio(
            "Income Menu",
            ["Income", "Income Dashboard"]
        )

    elif module == "Expenses":
        return st.sidebar.radio(
            "Expenses Menu",
            ["Expenses", "Expenses Dashboard"]
        )

    elif module == "Customers":
        return st.sidebar.radio(
            "Customer Menu",
            [f"{CUSTOMER_SUB[x]} {x}" for x in CUSTOMER_SUB]
        ).split(" ", 1)[1]

    elif module == "POS":
        return "POS"

    elif module == "Cash":
        return "Cash Dashboard"

    elif module == "P&L":
        return "P&L"
    
    elif module == "Credit & Debtors":
        return st.sidebar.radio(
            "Debtors Menu",
            [
                "Debtors",
                "Debtors Dashboard"
            ]
        )
    
    # ==============================
    # REPORTS MODULE
    # ==============================
    elif module == "Reports":
        return st.sidebar.radio(
            "Reports Menu",
            ["Reports Dashboard"]
        )
    
    # ==============================
    # SHIFT MANAGEMENT MODULE
    # ==============================
    elif module == "Shift Management":
        return "Shift Management"
    
    # ==============================
    # BRANCH MANAGEMENT MODULE
    # ==============================
    elif module == "Branch Management":
        return "Branch Management"
    
    # ==============================
    # MOBILE MODULE
    # ==============================
    elif module == "Mobile":
        return "Mobile Dashboard"
    
    # ==============================
    # DEMAND FORECASTING MODULE
    # ==============================
    elif module == "Demand Forecasting":
        return "Demand Forecasting"
    
    # ==============================
    # LIVE DASHBOARD MODULE
    # ==============================
    elif module == "Live Dashboard":
        return "Live Dashboard"
    
    # ==============================
    # BARCODE GENERATOR MODULE
    # ==============================
    elif module == "Barcode Generator":
        return "Barcode Generator"
    
    # ==============================
    # CUSTOMER APP MODULE
    # ==============================
    elif module == "Customer App":
        return "Customer App"
    
    # ==============================
    # SECURITY DASHBOARD MODULE
    # ==============================
    elif module == "Security Dashboard":
        return "Security Dashboard"
    
    # ==============================
    # LANGUAGE MANAGEMENT MODULE
    # ==============================
    elif module == "Language Management":
        return "Language Management"
    
    # ==============================
    # OFFLINE MODE MODULE
    # ==============================
    elif module == "Offline Mode":
        return "Offline Mode"
    
    # ==============================
    # FINANCIAL CLOSING MODULE
    # ==============================
    elif module == "Financial Closing":
        return "Financial Closing"
    
    # ==============================
    # SUPPLIER BIDDING MODULE
    # ==============================
    elif module == "Supplier Bidding":
        return "Supplier Bidding"
    
    # ==============================
    # CUSTOMER 360 VIEW MODULE
    # ==============================
    elif module == "Customer 360 View":
        return "Customer 360 View"
    
    # ==============================
    # RETURNS & REFUNDS MODULE
    # ==============================
    elif module == "Returns & Refunds":
        return st.sidebar.radio(
            "Returns Menu",
            [
                "📝 Process Return",
                "💰 Store Credit",
                "📋 Warranty Check",
                "📊 Return Analytics",
                "📜 Return History"
            ]
        )
    
    # ==============================
    # PROFIT CENTER ANALYSIS MODULE
    # ==============================
    elif module == "Profit Center Analysis":
        return "Profit Center Analysis"
    
    # ==============================
    # PREDICTIVE ANALYTICS MODULE
    # ==============================
    elif module == "Predictive Analytics":
        return "Predictive Analytics"
    
    # ==============================
    # COMPETITOR PRICE MONITORING MODULE
    # ==============================
    elif module == "Competitor Price Monitoring":
        return "Competitor Price Monitoring"
    
    # ==============================
    # PAYMENT GATEWAY MODULE
    # ==============================
    elif module == "Payment Gateway":
        return "Payment Gateway"
    
    # ==============================
    # ACCOUNTING SYNC MODULE
    # ==============================
    elif module == "Accounting Sync":
        return "Accounting Sync"
    
    # ==============================
    # E-COMMERCE SYNC MODULE
    # ==============================
    elif module == "E-commerce Sync":
        return "E-commerce Sync"
    
    # ==============================
    # SMS GATEWAY MODULE
    # ==============================
    elif module == "SMS Gateway":
        return "SMS Gateway"
    
    # ==============================
    # SMART REPLENISHMENT MODULE
    # ==============================
    elif module == "Smart Replenishment":
        return "Smart Replenishment"
    
    # ==============================
    # AUTOMATED FOLLOW-UP MODULE
    # ==============================
    elif module == "Automated Follow-up":
        return "Automated Follow-up"
    
    # ==============================
    # WORKFLOW APPROVALS MODULE
    # ==============================
    elif module == "Workflow Approvals":
        return "Workflow Approvals"
    
    # ==============================
    # PWA SETUP MODULE
    # ==============================
    elif module == "PWA Setup":
        return "PWA Setup"
    
    # ==============================
    # VOICE COMMANDS MODULE
    # ==============================
    elif module == "Voice Commands":
        return "Voice Commands"
    
    # ==============================
    # BARCODE SCANNER MODULE
    # ==============================
    elif module == "Barcode Scanner":
        return "Barcode Scanner"
    
    # ==============================
    # WHITE LABEL MODULE
    # ==============================
    elif module == "White Label":
        return "White Label"
    
    # ==============================
    # MULTI-TENANT MODULE
    # ==============================
    elif module == "Multi-Tenant":
        return "Multi-Tenant"
    
    # ==============================
    # API DEVELOPER MODULE
    # ==============================
    elif module == "API Developer":
        return "API Developer"

    return module