# app.py - Fixed version with Customer App removed and Mobile Mode disabled
import os
os.environ['TZ'] = 'Africa/Harare'
try:
    import time
    time.tzset()
except:
    pass

import streamlit as st

# ==============================
# HANDLE MOBILE NAVIGATION - FIXED
# ==============================
if "page" not in st.session_state:
    st.session_state.page = "Home"

def navigate_to(page):
    """Navigate to a page using Streamlit's native method"""
    st.session_state.page = page
    st.rerun()

# ==============================
# SESSION TIMEOUT - FIXED (No window.location.href)
# ==============================
def check_session_timeout():
    """Check session timeout using Streamlit's native method"""
    if "last_activity" in st.session_state:
        idle_time = (datetime.now() - st.session_state.last_activity).seconds
        if idle_time > 7200:  # 2 hours
            # Clear session without using window.location.href
            for key in list(st.session_state.keys()):
                if key not in ["branch_selected", "branch_authenticated", "current_branch", 
                               "user_branch", "stock_monitor_started", "stock_monitor_thread", 
                               "current_theme", "auto_switch_theme", "welcome_seen"]:
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
    """Safely execute a function with error handling"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_msg = f"Error in {func.__name__}: {str(e)}"
        st.error(f"{error_msg}")
        print(f"ERROR: {error_msg}")
        print(traceback.format_exc())
        return None

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
    get_auto_theme,
    apply_no_theme,
    apply_page_theme
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
# CUSTOMER IMPORTS - REMOVED customer_app
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
# MOBILE RESPONSIVE IMPORTS
# ==============================
# from backend.core.responsive import (
#     is_mobile_device, 
#     apply_mobile_css, 
#     get_device_type, 
#     show_mobile_banner
# )
# from backend.core.mobile_quick_actions import (
#     show_mobile_quick_actions, 
#     show_mobile_bottom_nav
# )

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
# PAGE CONFIG - FIXED
# ==============================
st.set_page_config(
    page_title="AZIEL INVESTMENTS",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================
# REMOVED: window.location.href JavaScript
# ==============================
# The JavaScript that was causing mobile navigation issues has been removed.
# Session timeout is now handled by check_session_timeout() function above.

# ==============================
# AUTO-NOTIFICATION BACKGROUND THREAD
# ==============================
def start_stock_monitor_thread():
    """Start background thread for automatic stock monitoring"""
    
    def monitor_loop():
        """Background monitoring loop"""
        while True:
            try:
                settings = load_notification_settings()
                
                if settings.get("auto_notify_enabled", True):
                    success, message, new_found = check_and_send_low_stock_alerts(force=False)
                    
                    if success:
                        print(f"[Auto-Monitor] {message} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    elif new_found is not False and "No low stock" not in message:
                        print(f"[Auto-Monitor] Info: {message}")
                
                check_interval = settings.get("check_interval_minutes", 30)
                time.sleep(check_interval * 60)
                
            except Exception as e:
                print(f"[Auto-Monitor Error] {str(e)}")
                time.sleep(60)
    
    try:
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        return monitor_thread
    except Exception as e:
        print(f"Failed to start monitor thread: {e}")
        return None

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
# START AUTO-NOTIFICATION MONITOR
# ==============================
if "stock_monitor_started" not in st.session_state:
    try:
        monitor_thread = start_stock_monitor_thread()
        if monitor_thread:
            st.session_state.stock_monitor_started = True
            st.session_state.stock_monitor_thread = monitor_thread
            print("Stock monitor thread started")
        else:
            print("Failed to start stock monitor thread")
    except Exception as e:
        print(f"Error starting stock monitor: {e}")

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
    st.session_state.last_activity = datetime.now()
    st.session_state.modules_debug = False

if "current_theme" not in st.session_state:
    try:
        st.session_state.current_theme = load_theme_preference()
    except Exception as e:
        print(f"Error loading theme preference: {e}")
        st.session_state.current_theme = "default"
        
if "auto_switch_theme" not in st.session_state:
    st.session_state.auto_switch_theme = False

# ==============================
# SESSION TIMEOUT CHECK - FIXED
# ==============================
if st.session_state.logged_in:
    check_session_timeout()

# ==============================
# BRANCH SELECTION PAGE
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
                        if branch_code_upper in BRANCHES:
                            if BRANCHES[branch_code_upper]["password"] == branch_password:
                                st.session_state.branch_selected = True
                                st.session_state.branch_authenticated = True
                                st.session_state.current_branch = branch_code_upper
                                st.session_state.branch_name = BRANCHES[branch_code_upper]["name"]
                                st.session_state.user_branch = branch_code_upper
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
            current_branch = st.session_state.get("current_branch", "HO")
            branch_name = BRANCHES.get(current_branch, {}).get("name", "Unknown")
        except Exception as e:
            print(f"Error getting branch info: {e}")
            branch_name = "Unknown"
        
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
                            st.session_state.current_page = "Stock Dashboard"
            
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
# MAIN APP - FLAT ALPHABETICAL NAVIGATION
# ==============================
def main_app():
    # ==============================
    # SESSION TIMEOUT - Already handled above
    # ==============================
    st.session_state.last_activity = datetime.now()
    
    # ==============================
    # PWA META TAGS
    # ==============================
    try:
        if is_pwa_enabled():
            st.markdown(get_pwa_meta_tags(), unsafe_allow_html=True)
    except Exception as e:
        print(f"PWA setup error: {e}")
    
    # ==============================
    # MOBILE RESPONSIVENESS - DISABLED
    # ==============================
    # try:
    #     if is_mobile_device():
    #         apply_mobile_css()
    #         show_mobile_banner()
    # except Exception as e:
    #     print(f"Mobile responsiveness error: {e}")
    
    role = st.session_state.get("role", "cashier")
    username = st.session_state.get("username", "User")
    current_branch = st.session_state.get("current_branch", "HO")
    try:
        branch_name = BRANCHES.get(current_branch, {}).get("name", "Unknown")
    except:
        branch_name = "Unknown"
    
    page = st.session_state.get("current_page", "Stock Dashboard")
    
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
    # SIDEBAR - FLAT ALPHABETICAL NAVIGATION
    # ==============================
    
    st.sidebar.markdown(f"""
    <div style='background: linear-gradient(135deg, #006400 0%, #FFD700 50%, #FF0000 100%); 
                border-radius: 10px; padding: 10px; text-align: center; color: white;'>
        <strong>{branch_name}</strong><br>
        <small>Code: {current_branch}</small>
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
    # FLAT ALPHABETICAL NAVIGATION - REMOVED Customer App
    # ==============================
    try:
        navigation_menu = get_navigation_menu(role)
    except Exception as e:
        st.error(f"Error loading navigation: {str(e)}")
        print(f"Navigation error: {e}")
        print(traceback.format_exc())
        navigation_menu = {}
    
    selected_page = None
    
    all_items = []
    try:
        for category, items in navigation_menu.items():
            for item in items:
                # Skip Customer App if it appears in navigation
                if item == "Customer App":
                    continue
                all_items.append(item)
        
        all_items = sorted(all_items)
        
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
            st.rerun()
        except Exception as e:
            print(f"Branch switch error: {e}")
    
    st.sidebar.markdown("---")
    st.sidebar.caption("AZIEL INVESTMENTS ERP")
    st.sidebar.caption("2026 All Rights Reserved")
    
    if st.sidebar.button("Logout", key="logout_sidebar", use_container_width=True):
        try:
            keys_to_keep = ["branch_selected", "branch_authenticated", "current_branch", "user_branch", 
                           "stock_monitor_started", "stock_monitor_thread", "current_theme", "auto_switch_theme"]
            for key in list(st.session_state.keys()):
                if key not in keys_to_keep:
                    del st.session_state[key]
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
    # MOBILE QUICK ACTIONS - DISABLED
    # ==============================
    # try:
    #     if is_mobile_device():
    #         show_mobile_quick_actions()
    #         show_mobile_bottom_nav()
    # except Exception as e:
    #     print(f"Mobile actions error: {e}")
    
    # ==============================
    # ROUTING ENGINE - REMOVED Customer App route
    # ==============================
    
    if selected_page:
        page = selected_page
        st.session_state.current_page = selected_page

    # Route to appropriate page with error handling
    try:
        # ================= ACCOUNTING =================
        if page == "Accounting Sync":
            if can_access_feature(role, "accounting_sync") or role in ["owner", "manager"]:
                accounting_sync_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= ADMIN =================
        elif page == "API Developer":
            if can_access_feature(role, "api_developer") or role in ["owner", "manager"]:
                api_developer_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Anomaly Detection":
            if can_access_feature(role, "security") or role in ["owner", "manager"]:
                anomaly_detection_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Automated Follow-up":
            if can_access_feature(role, "automated_followup") or role in ["owner", "manager"]:
                automated_followup_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Automated Insights":
            if can_access_feature(role, "reports") or role in ["owner", "manager"]:
                automated_insights_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= BARCODE =================
        elif page == "Barcode Generator":
            if can_access_feature(role, "inventory_view"):
                barcode_generator_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Barcode Scanner":
            if can_access_feature(role, "barcode_scanner") or role in ["owner", "manager", "cashier"]:
                barcode_scanner_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= BRANCH =================
        elif page == "Branch Management":
            if role == "owner":
                branch_management_page()
            else:
                st.error("Only system owner can access branch management")

        elif page == "Branch Performance":
            if can_access_feature(role, "branch_performance"):
                branch_performance_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Business Advisor":
            if can_access_feature(role, "business_advisor"):
                business_advisor_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= CASH =================
        elif page == "Cash Dashboard":
            if can_access_feature(role, "cash_dashboard"):
                cash_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Churn Prediction":
            if can_access_feature(role, "predictive_analytics") or role in ["owner", "manager"]:
                churn_prediction_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Competitor Price Monitoring":
            if can_access_feature(role, "competitor_price") or role in ["owner", "manager"]:
                competitor_price_monitoring_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= CUSTOMERS =================
        elif page == "Customer 360 View":
            if can_access_feature(role, "customer_360") or role in ["owner", "manager"]:
                customer_360_view()
            else:
                st.error("You don't have permission to access this page")

        # REMOVED: Customer App
        # elif page == "Customer App":
        #     customer_app()

        elif page == "Customer Dashboard":
            if can_access_feature(role, "customers"):
                customers_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Customer Insights":
            if can_access_feature(role, "customers"):
                customer_insights_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Customer Insights 360":
            if can_access_feature(role, "customer_360") or role in ["owner", "manager"]:
                customer_insights_360()
            else:
                st.error("You don't have permission to access this page")

        # ================= DEBTORS =================
        elif page == "Debtors":
            if can_access_feature(role, "debtors"):
                debtors_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Debtors Dashboard":
            if can_access_feature(role, "debtors_dashboard"):
                debtors_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Demand Forecasting":
            if can_access_feature(role, "demand_forecasting") or role in ["owner", "manager"]:
                demand_forecasting_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Documents":
            if role in ["owner", "manager"]:
                documents_page()
            else:
                st.error("You don't have permission to access this page")

        # ================= E-COMMERCE =================
        elif page == "E-commerce Sync":
            if can_access_feature(role, "ecommerce_sync") or role in ["owner", "manager"]:
                ecommerce_sync_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= EXPENSES =================
        elif page == "Expenses":
            if can_access_feature(role, "expenses"):
                expenses_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Expenses Dashboard":
            if can_access_feature(role, "expenses"):
                expenses_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= FINANCIAL =================
        elif page == "Financial Closing":
            if can_access_feature(role, "financial_closing") or role in ["owner", "manager"]:
                financial_closing_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= INCOME =================
        elif page == "Income":
            if can_access_feature(role, "income"):
                income_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Income Dashboard":
            if can_access_feature(role, "income"):
                income_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= INVENTORY =================
        elif page == "Inventory":
            if can_access_feature(role, "inventory_view"):
                inventory_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Inventory Optimizer":
            if can_access_feature(role, "inventory_view") or role in ["owner", "manager"]:
                inventory_optimizer_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= LANGUAGE =================
        elif page == "Language Management":
            if can_access_feature(role, "language_management") or role in ["owner", "manager"]:
                language_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Lifecycle Dashboard":
            if can_access_feature(role, "customers"):
                customers_lifecycle_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Live Dashboard":
            if can_access_feature(role, "live_dashboard") or role in ["owner", "manager"]:
                live_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= MOBILE =================
        elif page == "Mobile Dashboard":
            if can_access_feature(role, "mobile_dashboard") or role in ["owner", "manager", "cashier"]:
                mobile_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Multi-Tenant":
            if can_access_feature(role, "multi_tenant") or role == "owner":
                multi_tenant_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= OFFLINE =================
        elif page == "Offline Mode":
            if can_access_feature(role, "offline_mode") or role in ["owner", "manager"]:
                offline_mode_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= P&L =================
        elif page == "P&L":
            if can_access_feature(role, "pl"):
                pl_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Payment Gateway":
            if can_access_feature(role, "payment_gateway") or role in ["owner", "manager"]:
                payment_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "POS":
            if can_access_feature(role, "pos"):
                pos_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Predictive Analytics":
            if can_access_feature(role, "predictive_analytics") or role in ["owner", "manager"]:
                predictive_analytics_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Profit Center Analysis":
            if can_access_feature(role, "profit_analysis") or role in ["owner", "manager"]:
                profit_center_analysis()
            else:
                st.error("You don't have permission to access this page")

        # ================= PURCHASES =================
        elif page == "Purchases":
            if can_access_feature(role, "purchases"):
                purchases_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Purchases Dashboard":
            if can_access_feature(role, "purchases"):
                purchases_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "PWA Setup":
            if can_access_feature(role, "pwa_setup") or role in ["owner", "manager"]:
                pwa_setup_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= RECOMMENDATION =================
        elif page == "Recommendation Engine":
            if can_access_feature(role, "predictive_analytics") or role in ["owner", "manager"]:
                recommendation_engine_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= REPORTS =================
        elif page == "Reports Dashboard":
            if can_access_feature(role, "reports"):
                reports_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Retention Dashboard":
            if can_access_feature(role, "customers"):
                customers_retention_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Returns & Refunds":
            if can_access_feature(role, "returns_management") or role in ["owner", "manager"]:
                returns_management_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Returns Management":
            if can_access_feature(role, "returns_management") or role in ["owner", "manager"]:
                returns_management_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= SALES =================
        elif page == "Sales Dashboard":
            if can_access_feature(role, "sales_dashboard"):
                sales_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Sales History":
            if can_access_feature(role, "sales_history"):
                sales_history_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Security Dashboard":
            if can_access_feature(role, "security") or role in ["owner", "manager"]:
                security_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Segmentation Dashboard":
            if can_access_feature(role, "customers"):
                customers_segmentation_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Settings":
            if role == "owner":
                settings_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Shift Management":
            if can_access_feature(role, "shift_management"):
                shift_management_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Smart Replenishment":
            if can_access_feature(role, "smart_replenishment") or role in ["owner", "manager"]:
                smart_replenishment_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "SMS Gateway":
            if can_access_feature(role, "sms_gateway") or role in ["owner", "manager"]:
                sms_gateway_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Stock Dashboard":
            if can_access_feature(role, "inventory_view"):
                dashboard_page()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Supplier Bidding":
            if can_access_feature(role, "supplier_bidding") or role in ["owner", "manager"]:
                supplier_bidding_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Supplier Bidding Portal":
            supplier_bidding_portal()

        # ================= USER =================
        elif page == "User Management":
            if role == "owner":
                user_management_page()
            else:
                st.error("Only system owner can access user management")

        # ================= VOICE =================
        elif page == "Voice Commands":
            if can_access_feature(role, "voice_commands") or role in ["owner", "manager", "cashier"]:
                voice_commands_dashboard()
            else:
                st.error("You don't have permission to access this page")

        # ================= WHITE LABEL =================
        elif page == "White Label":
            if can_access_feature(role, "white_label") or role == "owner":
                white_label_dashboard()
            else:
                st.error("You don't have permission to access this page")

        elif page == "Workflow Approvals":
            if can_access_feature(role, "workflow_approvals") or role in ["owner", "manager"]:
                workflow_approvals_dashboard()
            else:
                st.error("You don't have permission to access this page")

        else:
            st.warning(f"Module not found: {page}")
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