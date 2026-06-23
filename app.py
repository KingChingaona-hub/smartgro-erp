import streamlit as st

# ==============================
# CORE SYSTEM IMPORTS - FIXED
# ==============================
from backend.core.db_adapter import (
    init_data_folder,
    get_current_branch as get_db_branch,
    set_current_branch,
    load_branches,
    load_products,
    load_sales,
    load_customers,
    load_debtors,
    load_expenses,
    load_purchases,
    load_cash,
    load_shifts,
    load_suppliers,
    load_loyalty,
    save_products,
    save_sales,
    save_customers,
    save_debtors,
    save_expenses,
    save_purchases,
    save_cash,
    save_shifts,
    save_loyalty,
    save_branches,
    generate_receipt_number
)

# Note: get_current_branch is imported as get_db_branch above
# We'll use the one from db_adapter for database operations
# And keep the branch_manager version for UI

from backend.core.auth import init_users, check_login, can_access_feature, get_user_permissions
from backend.core.branch_manager import branch_selector, get_current_branch, set_user_branch
from backend.core.branch_auth import branch_selection_page, get_current_branch as get_branch_code, BRANCHES
from backend.core.role_based_menu import get_navigation_menu
from backend.core.theme_manager import (
    apply_theme, 
    get_page_theme, 
    apply_login_theme, 
    apply_branch_selection_theme,
    theme_selector,
    AVAILABLE_THEMES,
    load_theme_preference,
    get_auto_theme
)
from backend.core.animations import (
    init_animations,
    show_toast,
    show_confetti,
    animated_progress,
    loading_skeleton,
    with_loading_spinner,
    animated_metric,
    floating_action_button
)
from backend.core.documents import (
    generate_proforma_invoice,
    generate_delivery_note,
    generate_credit_note,
    generate_customer_statement,
    generate_purchase_order,
    download_pdf_button,
    generate_qr_code
)
from backend.core.auto_notifications import check_and_send_low_stock_alerts, load_notification_settings
from backend.core.language_manager import language_dashboard, language_selector, get_current_language, _

# ==============================
# MODULE IMPORTS
# ==============================
from backend.modules.inventory import inventory_page
from backend.modules.pos import pos_page
from backend.modules.stock_dashboard import dashboard_page
from backend.modules.sales_history import sales_history_page
from backend.modules.sales_dashboard import sales_dashboard
from backend.modules.cash_dashboard import cash_dashboard
from backend.modules.purchases import purchases_page
from backend.modules.purchases_dashboard import purchases_dashboard
from backend.modules.expenses_page import expenses_page
from backend.modules.expenses_dashboard import expenses_dashboard
from backend.modules.income_page import income_page
from backend.modules.income_dashboard import income_dashboard
from backend.modules.pl_dashboard import pl_dashboard
from backend.modules.debtors import debtors_page
from backend.modules.debtors_dashboard import debtors_dashboard
from backend.modules.returns_management import returns_management_dashboard
from backend.modules.shift_management import shift_management_page
from backend.modules.settings_page import settings_page

# ==============================
# CUSTOMER IMPORTS
# ==============================
from backend.customers.customers_dashboard import customers_dashboard
from backend.customers.retention_dashboard import customers_retention_dashboard
from backend.customers.segmentation_dashboard import customers_segmentation_dashboard
from backend.customers.lifecycle_dashboard import customers_lifecycle_dashboard
from backend.customers.customer_360_view import customer_360_view, customer_insights_360
from backend.customers.customer_app import customer_app, customer_insights_page

# ==============================
# ANALYTICS IMPORTS
# ==============================
from backend.analytics.business_advisor import business_advisor_dashboard
from backend.analytics.reports_dashboard import reports_dashboard
from backend.analytics.profit_center import profit_center_analysis
from backend.analytics.predictive import predictive_analytics_dashboard
from backend.analytics.demand_forecasting import demand_forecasting_dashboard
from backend.analytics.competitor_price import competitor_price_monitoring_dashboard

# ==============================
# ADMIN IMPORTS
# ==============================
from backend.admin.user_management import user_management_page
from backend.admin.branch_management import branch_management_page
from backend.admin.branch_performance import branch_performance_page
from backend.admin.security import security_dashboard

# ==============================
# FEATURES IMPORTS
# ==============================
from backend.features.mobile_dashboard import mobile_dashboard
from backend.features.live_dashboard import live_dashboard
from backend.features.offline_mode import offline_mode_dashboard
from backend.features.barcode_generator import barcode_generator_page
from backend.features.barcode_scanner import barcode_scanner_dashboard
from backend.features.financial_closing import financial_closing_dashboard
from backend.features.supplier_bidding import supplier_bidding_dashboard, supplier_bidding_portal
from backend.features.smart_replenishment import smart_replenishment_dashboard
from backend.features.automated_followup import automated_followup_dashboard
from backend.features.workflow_approvals import workflow_approvals_dashboard

# ==============================
# INTEGRATIONS IMPORTS
# ==============================
from backend.integrations.payment_gateway import payment_dashboard
from backend.integrations.accounting_sync import accounting_sync_dashboard
from backend.integrations.ecommerce_sync import ecommerce_sync_dashboard
from backend.integrations.sms_gateway import sms_gateway_dashboard

# ==============================
# DEVELOPER IMPORTS
# ==============================
from backend.developer.pwa_setup import (
    get_pwa_meta_tags,
    get_pwa_install_prompt,
    get_offline_status,
    is_pwa_enabled,
    pwa_setup_dashboard
)
from backend.developer.voice_commands import voice_commands_dashboard
from backend.developer.white_label import white_label_dashboard
from backend.developer.multi_tenant import multi_tenant_dashboard
from backend.developer.api_developer import api_developer_dashboard

# ==============================
# MOBILE RESPONSIVE IMPORTS
# ==============================
from backend.core.responsive import (
    is_mobile_device, 
    apply_mobile_css, 
    get_device_type, 
    show_mobile_banner
)
from backend.core.mobile_quick_actions import (
    show_mobile_quick_actions, 
    show_mobile_bottom_nav
)

# ==============================
# DATE/TIME IMPORTS
# ==============================
from datetime import datetime, timedelta
import pandas as pd

# ==============================
# AUTO-NOTIFICATION SCHEDULER
# ==============================
import threading
import time

# ==============================
# PAGE CONFIG
# ==============================
st.set_page_config(
    page_title="AZIEL INVESTMENTS",
    page_icon="🛒",
    layout="wide"
)

# ==============================
# AUTO-NOTIFICATION BACKGROUND THREAD
# ==============================
def start_stock_monitor_thread():
    """Start background thread for automatic stock monitoring"""
    
    def monitor_loop():
        """Background monitoring loop"""
        while True:
            try:
                # Load current settings
                settings = load_notification_settings()
                
                # Check if auto-notifications are enabled
                if settings.get("auto_notify_enabled", True):
                    # Check stock levels and send alerts if needed
                    success, message, new_found = check_and_send_low_stock_alerts(force=False)
                    
                    # Log activity (optional - for debugging)
                    if success:
                        print(f"[Auto-Monitor] {message} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    elif new_found is not False and "No low stock" not in message:
                        print(f"[Auto-Monitor] Info: {message}")
                
                # Wait before next check (convert minutes to seconds)
                check_interval = settings.get("check_interval_minutes", 30)
                time.sleep(check_interval * 60)
                
            except Exception as e:
                print(f"[Auto-Monitor Error] {str(e)}")
                # Wait 1 minute before retry on error
                time.sleep(60)
    
    # Start daemon thread (runs in background, won't block app shutdown)
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    return monitor_thread


# ==============================
# INIT SYSTEM
# ==============================
init_data_folder()
init_users()

# ==============================
# START AUTO-NOTIFICATION MONITOR
# ==============================
# Check if monitor has already been started (prevents duplicate threads)
if "stock_monitor_started" not in st.session_state:
    monitor_thread = start_stock_monitor_thread()
    st.session_state.stock_monitor_started = True
    st.session_state.stock_monitor_thread = monitor_thread


# ==============================
# SESSION DEFAULTS
# ==============================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.current_branch = "HO"
    st.session_state.user_full_name = ""
    st.session_state.user_branch = "HO"
    st.session_state.active_shift_id = None
    st.session_state.active_shift_branch = None
    st.session_state.active_shift_branch_name = None
    st.session_state.branch_selected = False
    st.session_state.branch_authenticated = False
    st.session_state.current_page = "Stock Dashboard"

# Initialize theme settings
if "current_theme" not in st.session_state:
    st.session_state.current_theme = load_theme_preference()
if "auto_switch_theme" not in st.session_state:
    st.session_state.auto_switch_theme = False


# ==============================
# BRANCH SELECTION PAGE (Clean - No Logo)
# ==============================
def branch_login_page():
    """Page for selecting and authenticating branch - Clean version"""
    
    # Apply pure white background theme
    apply_branch_selection_theme()
    
    st.markdown('<div class="centered-form">', unsafe_allow_html=True)
    
    st.title("Aziel Investments")
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### Branch Access")
    
    branch_code = st.text_input("Branch Code", placeholder="Enter branch code", key="branch_code_input")
    branch_password = st.text_input("Branch Password", type="password", placeholder="Enter branch password", key="branch_password_input")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        if st.button("🔐 Access Branch", type="primary", use_container_width=True):
            if branch_code and branch_password:
                branch_code_upper = branch_code.upper()
                if branch_code_upper in BRANCHES:
                    if BRANCHES[branch_code_upper]["password"] == branch_password:
                        st.session_state.branch_selected = True
                        st.session_state.branch_authenticated = True
                        st.session_state.current_branch = branch_code_upper
                        st.session_state.user_branch = branch_code_upper
                        # Use the db_adapter version for database operations
                        set_current_branch(branch_code_upper)
                        st.success(f"✅ Access granted")
                        show_toast("Branch access granted successfully!", "success")
                        st.rerun()
                    else:
                        st.error("❌ Invalid branch password")
                        show_toast("Invalid branch password", "error")
                else:
                    st.error("❌ Invalid branch code")
                    show_toast("Invalid branch code", "error")
            else:
                st.error("Please enter branch code and password")
                show_toast("Please enter branch code and password", "warning")
    
    with col_b:
        if st.button("🏠 Head Office Demo", use_container_width=True):
            st.session_state.branch_selected = True
            st.session_state.branch_authenticated = True
            st.session_state.current_branch = "HO"
            st.session_state.user_branch = "HO"
            set_current_branch("HO")
            st.success("✅ Access granted to Head Office")
            show_toast("Head Office Demo mode activated", "info")
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)


# ==============================
# LOGIN PAGE
# ==============================
def login_page():
    
    # Apply elegant login theme
    apply_login_theme()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        current_branch = st.session_state.get("current_branch", "HO")
        branch_name = BRANCHES.get(current_branch, {}).get("name", "Unknown")
        
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown(
            "<h2 style='text-align:center;'>AZIEL INVESTMENTS</h2>",
            unsafe_allow_html=True
        )

        st.markdown(
            "<p style='text-align:center;color:rgba(255,255,255,0.9);'>Smart Retail ERP System</p>",
            unsafe_allow_html=True
        )

        st.markdown("---")

        with st.form("login_form"):

            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            login_btn = st.form_submit_button("Login")

            if login_btn:

                success, role = check_login(username, password)

                if success:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.role = role
                    show_toast(f"Welcome back, {username}!", "success")
                    show_confetti()
                    st.rerun()
                else:
                    st.error("Invalid credentials")
                    show_toast("Invalid username or password", "error")
        
        st.markdown("---")
        st.caption("Demo Users: admin/admin123 | manager/manager123 | cashier/cash123")
        
        if st.button("🔄 Switch to Different Branch"):
            st.session_state.branch_selected = False
            st.session_state.branch_authenticated = False
            st.rerun()


# ==============================
# DOCUMENTS PAGE
# ==============================
def documents_page():
    """Professional Documents Generation Page"""
    st.title("📄 Professional Documents")
    st.caption("Generate professional business documents")
    
    doc_type = st.selectbox(
        "Select Document Type",
        [
            "Proforma Invoice",
            "Delivery Note",
            "Credit Note",
            "Customer Statement",
            "Purchase Order"
        ]
    )
    
    if doc_type == "Proforma Invoice":
        st.subheader("Proforma Invoice Generator")
        
        col1, col2 = st.columns(2)
        with col1:
            customer = st.text_input("Customer Name", placeholder="Enter customer name")
            customer_phone = st.text_input("Customer Phone", placeholder="Optional")
        with col2:
            invoice_no = st.text_input("Invoice Number", value=f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            valid_until = st.date_input("Valid Until", value=datetime.now() + timedelta(days=30))
        
        st.markdown("### Items")
        items = []
        num_items = st.number_input("Number of Items", min_value=1, max_value=20, value=1)
        
        for i in range(num_items):
            st.markdown(f"**Item {i+1}**")
            col1, col2, col3 = st.columns(3)
            with col1:
                name = st.text_input(f"Product Name", key=f"item_name_{i}")
            with col2:
                qty = st.number_input(f"Quantity", min_value=1, value=1, key=f"qty_{i}")
            with col3:
                price = st.number_input(f"Unit Price ($)", min_value=0.0, value=0.0, key=f"price_{i}")
            
            if name and price > 0:
                items.append({
                    "name": name,
                    "quantity": qty,
                    "price": price,
                    "total": qty * price
                })
        
        if items:
            subtotal = sum(i['total'] for i in items)
            tax_rate = st.number_input("Tax Rate (%)", min_value=0.0, value=15.0)
            tax = subtotal * (tax_rate / 100)
            total = subtotal + tax
            
            st.markdown("### Summary")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Subtotal", f"${subtotal:.2f}")
            with col2:
                st.metric(f"Tax ({tax_rate}%)", f"${tax:.2f}")
            with col3:
                st.metric("Total", f"${total:.2f}")
            
            if st.button("📄 Generate Proforma Invoice", type="primary", use_container_width=True):
                data = {
                    "invoice_no": invoice_no,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "customer": customer or "Walk-in Customer",
                    "valid_until": valid_until.strftime("%Y-%m-%d"),
                    "items": items,
                    "subtotal": subtotal,
                    "tax_rate": tax_rate,
                    "tax": tax,
                    "total": total
                }
                with st.spinner("Generating PDF..."):
                    pdf = generate_proforma_invoice(data)
                    download_pdf_button(pdf, f"proforma_{invoice_no}.pdf", "📥 Download Proforma Invoice")
                    show_toast("Proforma Invoice generated successfully!", "success")
                    show_confetti()
    
    elif doc_type == "Delivery Note":
        st.subheader("Delivery Note Generator")
        
        col1, col2 = st.columns(2)
        with col1:
            customer = st.text_input("Customer Name", key="dn_customer")
            address = st.text_area("Delivery Address", placeholder="Enter delivery address")
        with col2:
            note_no = st.text_input("Delivery Note Number", value=f"DN-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            delivery_date = st.date_input("Delivery Date", value=datetime.now())
        
        st.markdown("### Items to Deliver")
        items = []
        num_items = st.number_input("Number of Items", min_value=1, max_value=20, value=1, key="dn_items")
        
        for i in range(num_items):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input(f"Item Name", key=f"dn_item_name_{i}")
            with col2:
                qty = st.number_input(f"Quantity", min_value=1, value=1, key=f"dn_qty_{i}")
            
            if name:
                items.append({"name": name, "quantity": qty})
        
        if st.button("📄 Generate Delivery Note", type="primary", use_container_width=True):
            data = {
                "note_no": note_no,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "customer": customer or "Walk-in Customer",
                "address": address or "Store Pickup",
                "items": items,
                "delivery_date": delivery_date.strftime("%Y-%m-%d")
            }
            with st.spinner("Generating PDF..."):
                pdf = generate_delivery_note(data)
                download_pdf_button(pdf, f"delivery_note_{note_no}.pdf", "📥 Download Delivery Note")
                show_toast("Delivery Note generated successfully!", "success")
    
    elif doc_type == "Credit Note":
        st.subheader("Credit Note Generator")
        
        col1, col2 = st.columns(2)
        with col1:
            customer = st.text_input("Customer Name", key="cn_customer")
            original_invoice = st.text_input("Original Invoice Number")
        with col2:
            note_no = st.text_input("Credit Note Number", value=f"CN-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            reason = st.selectbox("Reason for Credit", ["Product Return", "Price Adjustment", "Damaged Goods", "Other"])
        
        st.markdown("### Items to Credit")
        items = []
        num_items = st.number_input("Number of Items", min_value=1, max_value=20, value=1, key="cn_items")
        total_refund = 0
        
        for i in range(num_items):
            col1, col2, col3 = st.columns(3)
            with col1:
                name = st.text_input(f"Item Name", key=f"cn_item_name_{i}")
            with col2:
                qty = st.number_input(f"Quantity", min_value=1, value=1, key=f"cn_qty_{i}")
            with col3:
                refund = st.number_input(f"Refund Amount ($)", min_value=0.0, value=0.0, key=f"cn_refund_{i}")
            
            if name and refund > 0:
                items.append({"name": name, "quantity": qty, "refund": refund})
                total_refund += refund
        
        if items:
            st.metric("Total Credit Amount", f"${total_refund:.2f}")
        
        if st.button("📄 Generate Credit Note", type="primary", use_container_width=True):
            data = {
                "note_no": note_no,
                "invoice_no": original_invoice,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "customer": customer or "Walk-in Customer",
                "items": items,
                "total": total_refund,
                "reason": reason
            }
            with st.spinner("Generating PDF..."):
                pdf = generate_credit_note(data)
                download_pdf_button(pdf, f"credit_note_{note_no}.pdf", "📥 Download Credit Note")
                show_toast("Credit Note generated successfully!", "success")
    
    elif doc_type == "Customer Statement":
        st.subheader("Customer Statement Generator")
        
        from backend.core.db_adapter import load_customers, load_sales
        
        customers_df = load_customers()
        if not customers_df.empty:
            customer_list = customers_df["customer_name"].tolist()
            selected_customer = st.selectbox("Select Customer", customer_list)
            
            period = st.selectbox("Statement Period", ["Last 30 Days", "Last 90 Days", "Last 6 Months", "Last Year", "All Time"])
            
            if st.button("📄 Generate Statement", type="primary", use_container_width=True):
                # Get period in days
                period_days = {
                    "Last 30 Days": 30,
                    "Last 90 Days": 90,
                    "Last 6 Months": 180,
                    "Last Year": 365,
                    "All Time": 9999
                }
                
                # Get customer transactions
                sales_df = load_sales()
                customer_sales = sales_df[sales_df["customer"] == selected_customer]
                
                # Filter by period
                if period != "All Time":
                    cutoff_date = datetime.now() - timedelta(days=period_days[period])
                    customer_sales = customer_sales[pd.to_datetime(customer_sales["date"]) >= cutoff_date]
                
                # Build transactions
                transactions = []
                for _, sale in customer_sales.iterrows():
                    transactions.append({
                        "date": str(sale.get("date", ""))[:10],
                        "invoice": str(sale.get("receipt_no", "")),
                        "description": "Sale",
                        "debit": float(sale.get("final_total", 0)),
                        "credit": 0,
                        "balance": 0
                    })
                
                data = {
                    "customer": selected_customer,
                    "phone": "",
                    "period": period,
                    "transactions": transactions,
                    "opening_balance": 0,
                    "total_debits": sum(t["debit"] for t in transactions),
                    "total_credits": 0,
                    "closing_balance": sum(t["debit"] for t in transactions)
                }
                
                pdf = generate_customer_statement(data)
                download_pdf_button(pdf, f"statement_{selected_customer}.pdf", "📥 Download Statement")
                show_toast("Customer Statement generated successfully!", "success")
        else:
            st.info("No customers found")
    
    elif doc_type == "Purchase Order":
        st.subheader("Purchase Order Generator")
        
        col1, col2 = st.columns(2)
        with col1:
            supplier = st.text_input("Supplier Name")
            po_number = st.text_input("PO Number", value=f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        with col2:
            delivery_date = st.date_input("Requested Delivery Date", value=datetime.now() + timedelta(days=7))
            terms = st.text_input("Payment Terms", value="Net 30 Days")
        
        st.markdown("### Items to Order")
        items = []
        num_items = st.number_input("Number of Items", min_value=1, max_value=20, value=1, key="po_items")
        total_cost = 0
        
        for i in range(num_items):
            col1, col2, col3 = st.columns(3)
            with col1:
                name = st.text_input(f"Product Name", key=f"po_item_name_{i}")
            with col2:
                qty = st.number_input(f"Quantity", min_value=1, value=1, key=f"po_qty_{i}")
            with col3:
                cost = st.number_input(f"Unit Cost ($)", min_value=0.0, value=0.0, key=f"po_cost_{i}")
            
            if name and cost > 0:
                items.append({"name": name, "quantity": qty, "cost": cost, "total": qty * cost})
                total_cost += qty * cost
        
        if items:
            st.metric("Total Order Value", f"${total_cost:.2f}")
        
        if st.button("📄 Generate Purchase Order", type="primary", use_container_width=True):
            data = {
                "po_number": po_number,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "supplier": supplier or "Unknown Supplier",
                "delivery_date": delivery_date.strftime("%Y-%m-%d"),
                "items": items,
                "total": total_cost,
                "terms": terms
            }
            with st.spinner("Generating PDF..."):
                pdf = generate_purchase_order(data)
                download_pdf_button(pdf, f"purchase_order_{po_number}.pdf", "📥 Download Purchase Order")
                show_toast("Purchase Order generated successfully!", "success")


# ==============================
# MAIN APP
# ==============================
def main_app():
    # ==============================
    # PWA META TAGS (Only after login)
    # ==============================
    if is_pwa_enabled():
        st.markdown(get_pwa_meta_tags(), unsafe_allow_html=True)
    
    # ==============================
    # MOBILE RESPONSIVENESS
    # ==============================
    if is_mobile_device():
        apply_mobile_css()
        show_mobile_banner()
    
    role = st.session_state.get("role", "cashier")
    username = st.session_state.get("username", "User")
    current_branch = st.session_state.get("current_branch", "HO")
    branch_name = BRANCHES.get(current_branch, {}).get("name", "Unknown")
    
    # Determine current page for theme
    page = st.session_state.get("current_page", "Stock Dashboard")
    
    # Apply theme based on current page and user preference
    if st.session_state.get("auto_switch_theme", False):
        auto_theme = get_auto_theme()
        if auto_theme != st.session_state.get("current_theme"):
            st.session_state.current_theme = auto_theme
        colors = AVAILABLE_THEMES[st.session_state.current_theme]["colors"]
        apply_theme(colors)
    else:
        if st.session_state.get("current_theme") and st.session_state.current_theme in AVAILABLE_THEMES:
            colors = AVAILABLE_THEMES[st.session_state.current_theme]["colors"]
            apply_theme(colors)
        else:
            theme = get_page_theme(page)
            apply_theme(theme)
    
    # Initialize animations
    init_animations()
    
    # ==============================
    # SIDEBAR - ROLE BASED NAVIGATION
    # ==============================
    
    st.sidebar.markdown(f"""
    <div style='background: linear-gradient(135deg, #006400 0%, #FFD700 50%, #FF0000 100%); 
                border-radius: 10px; padding: 10px; text-align: center; color: white;'>
        <strong>📍 {branch_name}</strong><br>
        <small>Code: {current_branch}</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    
    # Add Theme Selector to Sidebar
    theme_selector()
    
    st.sidebar.markdown("---")
    
    navigation_menu = get_navigation_menu(role)
    
    st.sidebar.markdown("### 📋 Navigation")
    
    selected_page = None
    
    for category, items in navigation_menu.items():
        st.sidebar.markdown(f"**{category}**")
        for item in items:
            button_key = f"nav_{item.replace(' ', '_').replace('&', '')}"
            if st.sidebar.button(f"{item}", key=button_key, use_container_width=True):
                selected_page = item
                st.session_state.current_page = item
        st.sidebar.markdown("---")
    
    st.sidebar.markdown(f"**👤 {username}**")
    st.sidebar.markdown(f"**Role:** {role.upper()}")
    
    if role == "cashier" and st.session_state.get("active_shift_id"):
        st.sidebar.info(f"🟢 Shift Active\nID: {st.session_state.active_shift_id[:8]}...")
    
    if st.sidebar.button("🔄 Switch Branch", key="switch_branch_sidebar", use_container_width=True):
        st.session_state.branch_selected = False
        st.session_state.branch_authenticated = False
        st.session_state.logged_in = False
        st.rerun()
    
    # ==============================
    # LANGUAGE SELECTOR
    # ==============================
    st.sidebar.markdown("---")
    language_selector()
    
    # ==============================
    # PWA INSTALL BUTTON - IN SIDEBAR (Under Navigation)
    # ==============================
    if is_pwa_enabled():
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📱 Install App")
        
        install_html = """
        <style>
            .install-btn {
                display: block;
                width: 100%;
                padding: 12px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                border-radius: 12px;
                text-decoration: none;
                font-size: 1rem;
                font-weight: 500;
                margin: 10px 0;
                border: none;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            .install-btn:hover {
                transform: scale(1.02);
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            }
            .install-btn:active {
                transform: scale(0.98);
            }
            .install-btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            .install-status {
                font-size: 0.8rem;
                color: #666;
                text-align: center;
                margin-top: 5px;
            }
            .install-status.available {
                color: #4CAF50;
            }
            .install-status.unavailable {
                color: #f44336;
            }
            @media (prefers-color-scheme: dark) {
                .install-btn {
                    background: linear-gradient(135deg, #4a5db8 0%, #5a3d8a 100%);
                }
                .install-status {
                    color: #aaa;
                }
            }
        </style>
        
        <div id="pwa-install-container">
            <button class="install-btn" id="pwaInstallBtn">
                📲 Add to Home Screen
            </button>
            <div class="install-status" id="installStatus">Checking availability...</div>
        </div>
        
        <script>
            (function() {
                const btn = document.getElementById('pwaInstallBtn');
                const statusEl = document.getElementById('installStatus');
                let deferredPrompt = null;
                
                // Check if already installed
                function isAppInstalled() {
                    if (window.matchMedia('(display-mode: standalone)').matches) {
                        return true;
                    }
                    if (window.navigator.standalone === true) {
                        return true;
                    }
                    return false;
                }
                
                function isMobile() {
                    return /Android|iPhone|iPad|iPod|BlackBerry|Windows Phone/i.test(navigator.userAgent);
                }
                
                function isHTTPS() {
                    return window.location.protocol === 'https:' || 
                           window.location.hostname === 'localhost' || 
                           window.location.hostname === '127.0.0.1';
                }
                
                function updateStatus(message, type) {
                    statusEl.textContent = message;
                    statusEl.className = 'install-status ' + type;
                }
                
                if (isAppInstalled()) {
                    btn.style.display = 'none';
                    updateStatus('✅ App already installed!', 'available');
                    return;
                }
                
                if (!isMobile()) {
                    updateStatus('💻 Open on mobile device to install', 'unavailable');
                    btn.style.opacity = '0.6';
                    btn.style.cursor = 'default';
                    btn.onclick = function(e) {
                        e.preventDefault();
                        alert('📱 To install this app on your phone:\\n\\n' +
                              '1. Open this page on your mobile device\\n' +
                              '2. Tap the browser menu\\n' +
                              '3. Select "Add to Home Screen"');
                    };
                    return;
                }
                
                if (!isHTTPS()) {
                    updateStatus('⚠️ HTTPS required for installation', 'unavailable');
                    btn.style.opacity = '0.6';
                    btn.style.cursor = 'default';
                    btn.onclick = function(e) {
                        e.preventDefault();
                        alert('⚠️ To install this app:\\n\\n' +
                              'The app needs to be served over HTTPS.\\n' +
                              'If you\'re on localhost, try using ngrok or deploy to a secure server.');
                    };
                    return;
                }
                
                window.addEventListener('beforeinstallprompt', function(e) {
                    e.preventDefault();
                    deferredPrompt = e;
                    updateStatus('✅ Ready to install!', 'available');
                    btn.style.opacity = '1';
                    btn.style.cursor = 'pointer';
                    btn.disabled = false;
                });
                
                btn.addEventListener('click', function() {
                    if (deferredPrompt) {
                        deferredPrompt.prompt();
                        deferredPrompt.userChoice.then(function(result) {
                            if (result.outcome === 'accepted') {
                                updateStatus('✅ Installation started!', 'available');
                                btn.style.display = 'none';
                            } else {
                                updateStatus('Installation declined', 'unavailable');
                            }
                            deferredPrompt = null;
                        });
                    } else {
                        const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);
                        let message = '📱 To install this app:\\n\\n';
                        if (isIOS) {
                            message += '1. Tap the share button (⬆)\\n';
                            message += '2. Scroll and tap "Add to Home Screen"\\n';
                            message += '3. Tap "Add"';
                        } else if (/Android/i.test(navigator.userAgent)) {
                            message += '1. Tap the menu button (⋮)\\n';
                            message += '2. Select "Add to Home Screen"\\n';
                            message += '3. Tap "Add"';
                        } else {
                            message += 'Look for the install icon (⊕) in your browser\'s address bar\\n\\n';
                            message += 'Or use your browser\'s "Add to Home Screen" feature.';
                        }
                        alert(message);
                    }
                });
                
                window.addEventListener('appinstalled', function() {
                    btn.style.display = 'none';
                    updateStatus('✅ App installed successfully! 🎉', 'available');
                });
                
                if (isMobile() && isHTTPS()) {
                    updateStatus('⏳ Waiting for install prompt...', 'unavailable');
                    setTimeout(function() {
                        if (!deferredPrompt && !isAppInstalled()) {
                            updateStatus('📱 Tap "Add to Home Screen" in your browser menu', 'unavailable');
                        }
                    }, 3000);
                }
            })();
        </script>
        """
        st.markdown(install_html, unsafe_allow_html=True)
    
    # ==============================
    # SIDEBAR FOOTER & LOGOUT
    # ==============================
    st.sidebar.markdown("---")
    st.sidebar.caption("AZIEL INVESTMENTS ERP")
    st.sidebar.caption("© 2024 All Rights Reserved")
    
    if st.sidebar.button("🚪 Logout", key="logout_sidebar", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key not in ["branch_selected", "branch_authenticated", "current_branch", "user_branch", "stock_monitor_started", "stock_monitor_thread", "current_theme", "auto_switch_theme"]:
                del st.session_state[key]
        show_toast("Logged out successfully!", "info")
        st.rerun()
    
    # ==============================
    # FLOATING ACTION BUTTON (Main Content)
    # ==============================
    if page in ["Stock Dashboard", "Inventory", "POS"]:
        floating_action_button(icon="➕", label="Quick Action", link="#")
    
    # ==============================
    # MOBILE QUICK ACTIONS (Main Content)
    # ==============================
    if is_mobile_device():
        show_mobile_quick_actions()
        show_mobile_bottom_nav()
    
    # ==============================
    # ROUTING ENGINE
    # ==============================
    
    if selected_page:
        page = selected_page
        st.session_state.current_page = selected_page

    # ================= STOCK =================
    if page == "Stock Dashboard":
        if can_access_feature(role, "inventory_view"):
            dashboard_page()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Inventory":
        if can_access_feature(role, "inventory_view"):
            inventory_page()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Barcode Generator":
        if can_access_feature(role, "inventory_view"):
            barcode_generator_page()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= SALES =================
    elif page == "Sales History":
        if can_access_feature(role, "sales_history"):
            sales_history_page()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Sales Dashboard":
        if can_access_feature(role, "sales_dashboard"):
            sales_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= POS =================
    elif page == "POS":
        if can_access_feature(role, "pos"):
            pos_page()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= CASH =================
    elif page == "Cash Dashboard":
        if can_access_feature(role, "cash_dashboard"):
            cash_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= PURCHASES =================
    elif page == "Purchases":
        if can_access_feature(role, "purchases"):
            purchases_page()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Purchases Dashboard":
        if can_access_feature(role, "purchases"):
            purchases_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= INCOME =================
    elif page == "Income":
        if can_access_feature(role, "income"):
            income_page()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Income Dashboard":
        if can_access_feature(role, "income"):
            income_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= EXPENSES =================
    elif page == "Expenses":
        if can_access_feature(role, "expenses"):
            expenses_page()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Expenses Dashboard":
        if can_access_feature(role, "expenses"):
            expenses_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= P&L =================
    elif page == "P&L":
        if can_access_feature(role, "pl"):
            pl_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= CUSTOMERS =================
    elif page == "Customer Dashboard":
        if can_access_feature(role, "customers"):
            customers_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Retention Dashboard":
        if can_access_feature(role, "customers"):
            customers_retention_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Segmentation Dashboard":
        if can_access_feature(role, "customers"):
            customers_segmentation_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Lifecycle Dashboard":
        if can_access_feature(role, "customers"):
            customers_lifecycle_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= CUSTOMER 360 VIEW =================
    elif page == "Customer 360 View":
        if can_access_feature(role, "customer_360") or role in ["owner", "manager"]:
            customer_360_view()
        else:
            st.error("❌ You don't have permission to access this page")
    
    elif page == "Customer Insights 360":
        if can_access_feature(role, "customer_360") or role in ["owner", "manager"]:
            customer_insights_360()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= CUSTOMER APP =================
    elif page == "Customer App":
        customer_app()
    
    elif page == "Customer Insights":
        if can_access_feature(role, "customers"):
            customer_insights_page()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Business Advisor":
        if can_access_feature(role, "business_advisor"):
            business_advisor_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")
        
    # ================= DEBTORS =================
    elif page == "Debtors":
        if can_access_feature(role, "debtors"):
            debtors_page()
        else:
            st.error("❌ You don't have permission to access this page")

    elif page == "Debtors Dashboard":
        if can_access_feature(role, "debtors_dashboard"):
            debtors_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= REPORTS =================
    elif page == "Reports Dashboard":
        if can_access_feature(role, "reports"):
            reports_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= SHIFT MANAGEMENT =================
    elif page == "Shift Management":
        if can_access_feature(role, "shift_management"):
            shift_management_page()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= BRANCH PERFORMANCE =================
    elif page == "Branch Performance":
        if can_access_feature(role, "branch_performance"):
            branch_performance_page()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= MOBILE DASHBOARD =================
    elif page == "Mobile Dashboard":
        if can_access_feature(role, "mobile_dashboard") or role in ["owner", "manager", "cashier"]:
            mobile_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= DEMAND FORECASTING =================
    elif page == "Demand Forecasting":
        if can_access_feature(role, "demand_forecasting") or role in ["owner", "manager"]:
            demand_forecasting_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= LIVE DASHBOARD =================
    elif page == "Live Dashboard":
        if can_access_feature(role, "live_dashboard") or role in ["owner", "manager"]:
            live_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= SECURITY DASHBOARD =================
    elif page == "Security Dashboard":
        if can_access_feature(role, "security") or role in ["owner", "manager"]:
            security_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= LANGUAGE MANAGEMENT =================
    elif page == "Language Management":
        if can_access_feature(role, "language_management") or role in ["owner", "manager"]:
            language_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= OFFLINE MODE =================
    elif page == "Offline Mode":
        if can_access_feature(role, "offline_mode") or role in ["owner", "manager"]:
            offline_mode_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= FINANCIAL CLOSING =================
    elif page == "Financial Closing":
        if can_access_feature(role, "financial_closing") or role in ["owner", "manager"]:
            financial_closing_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= SUPPLIER BIDDING =================
    elif page == "Supplier Bidding":
        if can_access_feature(role, "supplier_bidding") or role in ["owner", "manager"]:
            supplier_bidding_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")
    
    elif page == "Supplier Bidding Portal":
        supplier_bidding_portal()

    # ================= RETURNS & REFUNDS MANAGEMENT =================
    elif page == "Returns & Refunds":
        if can_access_feature(role, "returns_management") or role in ["owner", "manager"]:
            returns_management_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")
    
    elif page == "Returns Management":
        if can_access_feature(role, "returns_management") or role in ["owner", "manager"]:
            returns_management_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= PROFIT CENTER ANALYSIS =================
    elif page == "Profit Center Analysis":
        if can_access_feature(role, "profit_analysis") or role in ["owner", "manager"]:
            profit_center_analysis()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= PREDICTIVE ANALYTICS =================
    elif page == "Predictive Analytics":
        if can_access_feature(role, "predictive_analytics") or role in ["owner", "manager"]:
            predictive_analytics_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= COMPETITOR PRICE MONITORING =================
    elif page == "Competitor Price Monitoring":
        if can_access_feature(role, "competitor_price") or role in ["owner", "manager"]:
            competitor_price_monitoring_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= PAYMENT GATEWAY =================
    elif page == "Payment Gateway":
        if can_access_feature(role, "payment_gateway") or role in ["owner", "manager"]:
            payment_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= ACCOUNTING SYNC =================
    elif page == "Accounting Sync":
        if can_access_feature(role, "accounting_sync") or role in ["owner", "manager"]:
            accounting_sync_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= E-COMMERCE SYNC =================
    elif page == "E-commerce Sync":
        if can_access_feature(role, "ecommerce_sync") or role in ["owner", "manager"]:
            ecommerce_sync_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= SMS GATEWAY =================
    elif page == "SMS Gateway":
        if can_access_feature(role, "sms_gateway") or role in ["owner", "manager"]:
            sms_gateway_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= SMART REPLENISHMENT =================
    elif page == "Smart Replenishment":
        if can_access_feature(role, "smart_replenishment") or role in ["owner", "manager"]:
            smart_replenishment_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= AUTOMATED FOLLOW-UP =================
    elif page == "Automated Follow-up":
        if can_access_feature(role, "automated_followup") or role in ["owner", "manager"]:
            automated_followup_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= WORKFLOW APPROVALS =================
    elif page == "Workflow Approvals":
        if can_access_feature(role, "workflow_approvals") or role in ["owner", "manager"]:
            workflow_approvals_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= PWA SETUP =================
    elif page == "PWA Setup":
        if can_access_feature(role, "pwa_setup") or role in ["owner", "manager"]:
            pwa_setup_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= VOICE COMMANDS =================
    elif page == "Voice Commands":
        if can_access_feature(role, "voice_commands") or role in ["owner", "manager", "cashier"]:
            voice_commands_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= BARCODE SCANNER =================
    elif page == "Barcode Scanner":
        if can_access_feature(role, "barcode_scanner") or role in ["owner", "manager", "cashier"]:
            barcode_scanner_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= WHITE LABEL =================
    elif page == "White Label":
        if can_access_feature(role, "white_label") or role == "owner":
            white_label_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= MULTI-TENANT =================
    elif page == "Multi-Tenant":
        if can_access_feature(role, "multi_tenant") or role == "owner":
            multi_tenant_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= API DEVELOPER =================
    elif page == "API Developer":
        if can_access_feature(role, "api_developer") or role in ["owner", "manager"]:
            api_developer_dashboard()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= DOCUMENTS =================
    elif page == "Documents":
        if role in ["owner", "manager"]:
            documents_page()
        else:
            st.error("❌ You don't have permission to access this page")

    # ================= ADMIN ONLY =================
    elif page == "Settings":
        if role == "owner":
            settings_page()
        else:
            st.error("❌ You don't have permission to access this page")
        
    elif page == "User Management":
        if role == "owner":
            user_management_page()
        else:
            st.error("❌ Only system owner can access user management")

    elif page == "Branch Management":
        if role == "owner":
            branch_management_page()
        else:
            st.error("❌ Only system owner can access branch management")

    else:
        st.warning(f"Module not found: {page}")


# ==============================
# APP FLOW
# ==============================
if not st.session_state.get("branch_selected", False):
    branch_login_page()
elif not st.session_state.logged_in:
    login_page()
else:
    main_app()