# app.py - dynamic branch & package support.
# Page access = role permission AND branch package (backend/core/packages.py,
# enforced via role_based_menu.can_access_page) for BOTH sidebar and router.
import os
os.environ['TZ'] = 'Africa/Harare'
try:
    import time as _time
    _time.tzset()
except:
    pass

import streamlit as st

# ==============================
# HANDLE MOBILE NAVIGATION - FIXED
# ==============================
if "page" not in st.session_state:
    st.session_state.page = "Home"

def navigate_to(page):
    """Navigate to a page using Streamlit's native method."""
    st.session_state.current_page = page
    st.rerun()

# ==============================
# SESSION TIMEOUT - FIXED
# ==============================
def check_session_timeout():
    """Check session timeout using Streamlit's native method"""
    if "last_activity" in st.session_state:
        idle_time = (datetime.now() - st.session_state.last_activity).total_seconds()
        if idle_time > 7200:  # 2 hours
            for key in list(st.session_state.keys()):
                if key not in ["branch_selected", "branch_authenticated", "current_branch",
                               "user_branch", "current_branch_code", "current_branch_name",
                               "current_theme", "auto_switch_theme", "welcome_seen",
                               "branch_package"]: # Added branch_package to keep
                    try:
                        del st.session_state[key]
                    except:
                        pass
            st.session_state.logged_in = False
            st.rerun()
            return True
    return False

from backend.core.config import get_current_time
import traceback
import sys

# ==============================
# ERROR HANDLING WRAPPER
# ==============================
def safe_execute(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_msg = f"Error in {func.__name__}: {str(e)}"
        st.error(f"{error_msg}")
        print(f"ERROR: {error_msg}")
        print(traceback.format_exc())
        return None

from backend.scripts.remove_duplicate_products import duplicate_products_page

# ==============================
# CORE SYSTEM IMPORTS
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

from backend.core.auth import init_users, check_login, can_access_feature, get_user_permissions
from backend.core.branch_manager import branch_selector, get_current_branch, set_user_branch
# UPDATED IMPORT: Added get_branch_info, is_branch_active, get_branch_display_name
from backend.core.branch_auth import (
    branch_selection_page, 
    get_current_branch as get_branch_code, 
    BRANCHES,
    get_branch_info,
    is_branch_active,
    get_branch_display_name
)
from backend.core.role_based_menu import (
    get_visible_modules,
    get_navigation_menu,
    can_access_page,
    locked_page_message,
)
from backend.core.packages import normalize_package
from backend.core.theme_manager import (
    apply_theme, 
    get_page_theme, 
    apply_login_theme, 
    apply_branch_selection_theme,
    theme_selector,
    AVAILABLE_THEMES,
    load_theme_preference,
    get_auto_theme,
    apply_no_theme,
    apply_page_theme
)
from backend.core.documents import documents_page
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
from backend.core.language_manager import language_dashboard, get_current_language, _

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
from backend.modules.welcome_page import welcome_page

# ==============================
# FLOATING FINANCIALS IMPORT
# ==============================
from backend.modules.floating_financials import floating_financials_page

# ==============================
# CUSTOMER IMPORTS
# ==============================
from backend.customers.customers_dashboard import customers_dashboard
from backend.customers.retention_dashboard import customers_retention_dashboard
from backend.customers.segmentation_dashboard import customers_segmentation_dashboard
from backend.customers.lifecycle_dashboard import customers_lifecycle_dashboard
from backend.customers.customer_360_view import customer_360_view, customer_insights_360

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
# NEW DATA SCIENCE MODULES
# ==============================
from backend.analytics.churn_prediction import churn_prediction_dashboard
from backend.analytics.recommendation_engine import recommendation_engine_dashboard
from backend.analytics.inventory_optimizer import inventory_optimizer_dashboard
from backend.analytics.automated_insights import automated_insights_dashboard
from backend.analytics.anomaly_detection import anomaly_detection_dashboard

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
# DATE/TIME IMPORTS
# ==============================
from datetime import datetime, timedelta
import pandas as pd

# ==============================
# PAGE CONFIG - FIXED
# ==============================
st.set_page_config(
    page_title="AZIEL INVESTMENTS",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================
# INIT SYSTEM WITH ERROR HANDLING
# ==============================
try:
    init_data_folder()
    print("Data folder initialized successfully")
except Exception as e:
    print(f"Error initializing data folder: {e}")
    st.error(f"System initialization error: {e}")

try:
    init_users()
    print("Users initialized successfully")
except Exception as e:
    print(f"Error initializing users: {e}")
    st.error(f"User initialization error: {e}")

# ==============================
# SESSION DEFAULTS
# ==============================
# setdefault-style initialization also repairs sessions created by older
# versions of the application.
SESSION_DEFAULTS = {
    "logged_in": False,
    "username": "",
    "role": "",
    "current_branch": "HO",
    "user_full_name": "",
    "user_branch": "HO",
    "current_branch_code": "HO",
    "current_branch_name": "Head Office",
    "active_shift_id": None,
    "active_shift_branch": None,
    "active_shift_branch_name": None,
    "branch_selected": False,
    "branch_authenticated": False,
    "current_page": "Stock Dashboard",
    "last_activity": datetime.now(),
    "modules_debug": False,
    "branch_package": "Bronze",
    "welcome_seen": False,
}

for _key, _default in SESSION_DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _default

if "current_theme" not in st.session_state:
    try:
        st.session_state.current_theme = load_theme_preference()
    except Exception as e:
        print(f"Error loading theme preference: {e}")
        st.session_state.current_theme = "default"

if "auto_switch_theme" not in st.session_state:
    st.session_state.auto_switch_theme = False

# ==============================
# SESSION TIMEOUT CHECK
# ==============================
if st.session_state.logged_in:
    check_session_timeout()

# ==============================
# BRANCH SELECTION PAGE - UPDATED
# ==============================
def branch_login_page():
    """Page for selecting and authenticating branch"""
    
    try:
        apply_branch_selection_theme()
    except Exception as e:
        print(f"Error applying branch theme: {e}")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
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
        
        with st.form("branch_login_form"):
            branch_code = st.text_input("Branch Code", placeholder="Enter branch code")
            branch_password = st.text_input("Branch Password", type="password", placeholder="Enter branch password")
            
            login_btn = st.form_submit_button("Branch Login", use_container_width=True)
            
            if login_btn:
                try:
                    if branch_code and branch_password:
                        branch_code_upper = branch_code.upper()
                        
                        # Fetch dynamic branch info
                        branch_info = get_branch_info(branch_code_upper)
                        
                        if branch_info:
                            if branch_info["password"] == branch_password:
                                # Check if Terminated
                                if branch_info.get("status", "Active") != "Active":
                                    st.error("This branch's subscription has been terminated. Please contact Aziel Investments.")
                                    try:
                                        show_toast("Subscription Terminated", "error")
                                    except:
                                        pass
                                else:
                                    # Clear any stale branch keys first
                                    for stale_key in ("user_branch", "current_branch", "current_branch_code", "current_branch_name", "branch_package"):
                                        st.session_state.pop(stale_key, None)

                                    st.session_state.branch_selected = True
                                    st.session_state.branch_authenticated = True
                                    st.session_state.current_branch = branch_code_upper
                                    st.session_state.branch_name = branch_info["name"]
                                    st.session_state.user_branch = branch_code_upper
                                    st.session_state.current_branch_code = branch_code_upper
                                    st.session_state.current_branch_name = branch_info["name"]
                                    
                                    # SAVE PACKAGE TO SESSION
                                    st.session_state.branch_package = branch_info.get("package", "Bronze")
                                    
                                    set_current_branch(branch_code_upper)
                                    st.success("Access granted")
                                    try:
                                        show_toast("Branch access granted successfully!", "success")
                                    except:
                                        pass
                                    st.rerun()
                            else:
                                st.error("Invalid branch password")
                                try:
                                    show_toast("Invalid branch password", "error")
                                except:
                                    pass
                        else:
                            st.error("Invalid branch code")
                            try:
                                show_toast("Invalid branch code", "error")
                            except:
                                pass
                    else:
                        st.error("Please enter branch code and password")
                        try:
                            show_toast("Please enter branch code and password", "warning")
                        except:
                            pass
                except Exception as e:
                    st.error(f"Branch login error: {str(e)}")
                    print(f"Branch login error: {e}")
                    print(traceback.format_exc())

# ==============================
# LOGIN PAGE - FIXED
# ==============================
def login_page():
    """Login page with proper error handling"""
    
    try:
        apply_login_theme()
    except Exception as e:
        print(f"Error applying login theme: {e}")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        try:
            current_branch = st.session_state.get("current_branch_code", "HO")
            branch_name = get_branch_display_name(current_branch)
        except Exception as e:
            print(f"Error getting branch info: {e}")
            branch_name = "Unknown"
        
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown(
            "<h2 style='text-align:center;'>AZIEL INVESTMENTS</h2>",
            unsafe_allow_html=True
        )

        st.markdown(
            f"<p style='text-align:center;color:rgba(255,255,255,0.9);'>"
            f"Smart Retail ERP System — {branch_name}</p>",
            unsafe_allow_html=True
        )

        st.markdown("---")

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            login_btn = st.form_submit_button("Login")

            if login_btn:
                try:
                    if not username or not password:
                        st.error("Please enter both username and password")
                        return
                    
                    try:
                        success, role = check_login(username, password)
                    except Exception as e:
                        st.error(f"Login system error: {str(e)}")
                        print(f"check_login error: {e}")
                        print(traceback.format_exc())
                        return

                    if success:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.session_state.role = role
                        st.session_state.branch_name = branch_name
                        
                        if role == "cashier":
                            st.session_state.current_page = "POS"
                        else:
                            st.session_state.current_page = "Cash Dashboard"
            
                        try:
                            show_toast(f"Welcome back, {username}!", "success")
                            show_confetti()
                        except:
                            pass
                        st.session_state.last_activity = datetime.now()
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
                        try:
                            show_toast("Invalid username or password", "error")
                        except:
                            pass
                except Exception as e:
                    st.error(f"Login error: {str(e)}")
                    print(f"Login error: {e}")
                    print(traceback.format_exc())

# ==============================
# PAGE ROUTES  (page name -> function)
# ==============================
# One entry per page. WHO may open a page is NOT decided here: that is
# decided once, in main_app(), by can_access_page() (role AND package).
PAGE_ROUTES = {
    "Accounting Sync": accounting_sync_dashboard,
    "Anomaly Detection": anomaly_detection_dashboard,
    "API Developer": api_developer_dashboard,
    "Automated Follow-up": automated_followup_dashboard,
    "Automated Insights": automated_insights_dashboard,
    "Barcode Generator": barcode_generator_page,
    "Barcode Scanner": barcode_scanner_dashboard,
    "Branch Management": branch_management_page,
    "Branch Performance": branch_performance_page,
    "Business Advisor": business_advisor_dashboard,
    "Cash Dashboard": cash_dashboard,
    "Churn Prediction": churn_prediction_dashboard,
    "Competitor Price Monitoring": competitor_price_monitoring_dashboard,
    "Customer 360 View": customer_360_view,
    "Customer Dashboard": customers_dashboard,
    "Customer Insights 360": customer_insights_360,
    "Debtors": debtors_page,
    "Debtors Dashboard": debtors_dashboard,
    "Demand Forecasting": demand_forecasting_dashboard,
    "Documents": documents_page,
    "Duplicate Products": duplicate_products_page,
    "E-commerce Sync": ecommerce_sync_dashboard,
    "Expenses": expenses_page,
    "Expenses Dashboard": expenses_dashboard,
    "Financial Closing": financial_closing_dashboard,
    "Floating Financials": floating_financials_page,
    "Income": income_page,
    "Income Dashboard": income_dashboard,
    "Inventory": inventory_page,
    "Inventory Optimizer": inventory_optimizer_dashboard,
    "Language Management": language_dashboard,
    "Lifecycle Dashboard": customers_lifecycle_dashboard,
    "Live Dashboard": live_dashboard,
    "Mobile Dashboard": mobile_dashboard,
    "Multi-Tenant": multi_tenant_dashboard,
    "Offline Mode": offline_mode_dashboard,
    "P&L": pl_dashboard,
    "Payment Gateway": payment_dashboard,
    "POS": pos_page,
    "Predictive Analytics": predictive_analytics_dashboard,
    "Profit Center Analysis": profit_center_analysis,
    "Purchases": purchases_page,
    "Purchases Dashboard": purchases_dashboard,
    "PWA Setup": pwa_setup_dashboard,
    "Recommendation Engine": recommendation_engine_dashboard,
    "Reports Dashboard": reports_dashboard,
    "Retention Dashboard": customers_retention_dashboard,
    "Returns & Refunds": returns_management_dashboard,
    "Returns Management": returns_management_dashboard,
    "Sales Dashboard": sales_dashboard,
    "Sales History": sales_history_page,
    "Security Dashboard": security_dashboard,
    "Segmentation Dashboard": customers_segmentation_dashboard,
    "Settings": settings_page,
    "Shift Management": shift_management_page,
    "Smart Replenishment": smart_replenishment_dashboard,
    "SMS Gateway": sms_gateway_dashboard,
    "Stock Dashboard": dashboard_page,
    "Supplier Bidding": supplier_bidding_dashboard,
    "Supplier Bidding Portal": supplier_bidding_portal,
    "User Management": user_management_page,
    "Voice Commands": voice_commands_dashboard,
    "White Label": white_label_dashboard,
    "Workflow Approvals": workflow_approvals_dashboard,
}

# Old page names still reachable from stale sessions/bookmarks.
PAGE_ALIASES = {"Returns Management": "Returns & Refunds"}

# ==============================
# MAIN APP - DYNAMIC PACKAGE NAVIGATION
# ==============================
def main_app():
    st.session_state.last_activity = datetime.now()

    # ==============================
    # LIGHTWEIGHT LOW-STOCK CHECK
    # ==============================
    try:
        now = datetime.now()
        last_check = st.session_state.get("last_stock_check")
        if last_check is None or (now - last_check).total_seconds() > 1800:  # every 30 min
            st.session_state.last_stock_check = now
            try:
                check_and_send_low_stock_alerts(force=False)
            except Exception as e:
                print(f"Low stock check error: {e}")
    except Exception as e:
        print(f"Stock check wrapper error: {e}")
    
    # ==============================
    # BRANCH GUARD & TERMINATION CHECK
    # ==============================
    role = str(st.session_state.get("role", "cashier") or "cashier").strip().lower()
    session_branch = (
        st.session_state.get("current_branch_code")
        or st.session_state.get("user_branch")
        or st.session_state.get("current_branch")
    )
    session_branch = str(session_branch).strip().upper() if session_branch else None
    current_branch = session_branch or "HO"

    # The head-office owner administers the platform itself. Owners attached
    # to client branches remain subject to that branch's subscription.
    is_head_office_owner = role == "owner" and current_branch == "HO"

    try:
        # Refresh the branch record on each rerun so package changes take
        # effect immediately without requiring users to log in again.
        branch_record = get_branch_info(current_branch)
    except Exception as e:
        branch_record = None
        print(f"Branch lookup error for {current_branch}: {e}")

    if is_head_office_owner:
        branch_package = normalize_package(
            st.session_state.get("branch_package", "Platinum")
        )
    else:
        if not branch_record:
            st.error("Your branch could not be verified. Please log in again.")
            st.session_state.logged_in = False
            st.session_state.branch_selected = False
            st.session_state.branch_authenticated = False
            st.rerun()
            return

        branch_status = str(branch_record.get("status", "Active")).strip().lower()
        if branch_status != "active":
            st.error("Your branch subscription is not active. Please contact Aziel Investments.")
            st.session_state.logged_in = False
            st.session_state.branch_selected = False
            st.session_state.branch_authenticated = False
            st.rerun()
            return

        branch_package = normalize_package(branch_record.get("package"))
        st.session_state.branch_package = branch_package

    branch_package = normalize_package(branch_package)
    st.session_state.branch_package = branch_package

    # ==============================
    # PWA META TAGS
    # ==============================
    try:
        if is_pwa_enabled():
            st.markdown(get_pwa_meta_tags(), unsafe_allow_html=True)
    except Exception as e:
        print(f"PWA setup error: {e}")
    
    username = st.session_state.get("username", "User")
    try:
        branch_name = get_branch_display_name(current_branch)
    except:
        branch_name = "Unknown"
    
    page = st.session_state.get("current_page", "Cash Dashboard")
    
    # ==============================
    # CHECK IF WELCOME PAGE SHOULD BE SHOWN
    # ==============================
    if not st.session_state.get("welcome_seen", False):
        try:
            welcome_page()
        except Exception as e:
            st.error(f"Error loading welcome page: {str(e)}")
            print(f"Welcome page error: {e}")
            print(traceback.format_exc())
        return
    
    # ==============================
    # APPLY THEME
    # ==============================
    try:
        if st.session_state.get("auto_switch_theme", False):
            auto_theme = get_auto_theme()
            if auto_theme != st.session_state.get("current_theme"):
                st.session_state.current_theme = auto_theme
            apply_page_theme(page)
        else:
            if st.session_state.get("current_theme") and st.session_state.current_theme in AVAILABLE_THEMES:
                apply_page_theme(page)
            else:
                apply_no_theme()
    except Exception as e:
        print(f"Theme application error: {e}")
        apply_no_theme()
    
    try:
        init_animations()
    except Exception as e:
        print(f"Animation initialization error: {e}")
    
    # ==============================
    # SIDEBAR
    # ==============================
    st.sidebar.markdown(f"""
    <div style='background: linear-gradient(135deg, #006400 0%, #FFD700 50%, #FF0000 100%); 
                border-radius: 10px; padding: 10px; text-align: center; color: white;'>
        <strong>{branch_name}</strong><br>
        <small>Code: {current_branch} | Pkg: {branch_package}</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    
    # ==============================
    # THEME SELECTOR
    # ==============================
    try:
        theme_selector()
    except Exception as e:
        print(f"Theme selector error: {e}")
    
    st.sidebar.markdown("---")
    
    # ==============================
    # FLAT ALPHABETICAL NAVIGATION (FILTERED BY PACKAGE)
    # ==============================
    try:
        # Role AND package AND branch (head-office owner sees everything)
        all_items = get_visible_modules(role, branch_package, current_branch)
        
        exclude = ["Customer App", "Customer Insights"]
        all_items = [item for item in all_items if item not in exclude]
        
        all_items = sorted(all_items)
        
        st.sidebar.write(f"📊 {len(all_items)} modules available")
        
    except Exception as e:
        st.error(f"Error loading navigation: {str(e)}")
        print(f"Navigation error: {e}")
        print(traceback.format_exc())
        # Fail closed if permission calculation fails; never expose a
        # hard-coded fallback menu that may bypass role/package restrictions.
        all_items = []
    
    selected_page = None
    
    try:
        for item in all_items:
            button_key = f"nav_{item.replace(' ', '_').replace('&', '').replace('/', '_').replace('-', '_')}"
            if st.sidebar.button(f"{item}", key=button_key, use_container_width=True):
                selected_page = item
                st.session_state.current_page = item
    except Exception as e:
        print(f"Navigation rendering error: {e}")
    
    st.sidebar.markdown("---")
    
    # ==============================
    # USER INFO & CONTROLS
    # ==============================
    st.sidebar.markdown(f"**{username}**")
    st.sidebar.markdown(f"**Role:** {role.upper()}")
    
    if role == "cashier" and st.session_state.get("active_shift_id"):
        st.sidebar.info(f"Shift Active\nID: {st.session_state.active_shift_id[:8]}...")
    
    if st.sidebar.button("Switch Branch", key="switch_branch_sidebar", use_container_width=True):
        try:
            st.session_state.branch_selected = False
            st.session_state.branch_authenticated = False
            st.session_state.logged_in = False
            st.session_state.welcome_seen = False
            for key in ("user_branch", "current_branch", "current_branch_code", "current_branch_name", "branch_package"):
                st.session_state.pop(key, None)
            st.rerun()
        except Exception as e:
            print(f"Branch switch error: {e}")
    
    st.sidebar.markdown("---")
    st.sidebar.caption("AZIEL INVESTMENTS ERP")
    st.sidebar.caption("2026 All Rights Reserved")
    
    if st.sidebar.button("Logout", key="logout_sidebar", use_container_width=True):
        try:
            keys_to_keep = ["current_theme", "auto_switch_theme"]
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    try:
                        del st.session_state[key]
                    except:
                        pass
            try:
                show_toast("Logged out successfully!", "info")
            except:
                pass
            st.rerun()
        except Exception as e:
            print(f"Logout error: {e}")
    
    # ==============================
    # FLOATING ACTION BUTTON
    # ==============================
    try:
        if page in ["Stock Dashboard", "Inventory", "POS"]:
            floating_action_button(icon="⚡", label="Quick Action", link="#")
    except Exception as e:
        print(f"Floating action button error: {e}")
    
    # ==============================
    # ROUTING ENGINE
    # ==============================
    
    if selected_page:
        page = selected_page
        st.session_state.current_page = selected_page

    # Route to the page. Access = role permission AND branch package, decided
    # in ONE place (the same rule that builds the sidebar), so the sidebar and
    # the router can never disagree.
    try:
        route_page = PAGE_ALIASES.get(page, page)
        handler = PAGE_ROUTES.get(route_page)

        if handler is None:
            st.warning(f"Module not found: {page}")
        elif not can_access_page(role, route_page, branch_package, current_branch):
            st.error(locked_page_message(route_page, branch_package))
        else:
            handler()
    except Exception as e:
        st.error(f"Error loading page: {str(e)}")
        print(f"Page routing error: {e}")
        print(traceback.format_exc())


# ==============================
# APP FLOW WITH ERROR HANDLING
# ==============================
try:
    if not st.session_state.get("branch_selected", False):
        branch_login_page()
    elif not st.session_state.logged_in:
        login_page()
    else:
        main_app()
except Exception as e:
    st.error(f"Application error: {str(e)}")
    print(f"App flow error: {e}")
    print(traceback.format_exc())
    
    st.markdown("---")
    st.info("Please try refreshing the page or contact support if the issue persists.")
    
    if st.button("Restart Application"):
        try:
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        except:
            pass