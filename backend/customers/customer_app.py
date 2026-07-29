# backend/customers/customer_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import qrcode
from io import BytesIO
import base64
import re
from pathlib import Path

from backend.core.db_adapter import (
    load_customers, 
    load_sales, 
    load_products, 
    save_customers, 
    get_current_branch, 
    BRANCH_DATA_DIR,
    load_customer_transactions
)
from backend.modules.loyalty import (
    load_loyalty, 
    get_customer_loyalty_info, 
    add_loyalty_points,
    redeem_points,
    get_tier_benefits,
    save_loyalty
)
from backend.utils.phone_utils import validate_zimbabwe_phone, get_whatsapp_link
from backend.utils.utils import generate_whatsapp_receipt


# ==============================
# HELPER: Convert Decimal to float
# ==============================
def to_float(value):
    """Safely convert Decimal or any value to float"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ==============================
# SAFE NAVIGATION - FIXED
# ==============================
def safe_rerun():
    """Safe rerun that works on all devices"""
    try:
        st.rerun()
    except:
        pass


def navigate_to(page):
    """Safe navigation for customer app"""
    st.session_state.page = page
    safe_rerun()


def logout_customer():
    """Safe logout for customer"""
    st.session_state.customer_logged_in = False
    st.session_state.customer_data = None
    st.session_state.customer_phone = None
    st.session_state.customer_branch = None
    safe_rerun()


# ==============================
# CUSTOMER APP SESSION
# ==============================

def init_customer_session():
    """Initialize customer app session"""
    if "customer_logged_in" not in st.session_state:
        st.session_state.customer_logged_in = False
    if "customer_data" not in st.session_state:
        st.session_state.customer_data = None
    if "customer_phone" not in st.session_state:
        st.session_state.customer_phone = None
    if "customer_branch" not in st.session_state:
        st.session_state.customer_branch = None


def normalize_phone_for_storage(phone):
    """Convert phone to the format used in database (without leading 0, as float string)"""
    if not phone:
        return ""
    cleaned = re.sub(r'\D', '', str(phone))
    if cleaned.startswith('0'):
        cleaned = cleaned[1:]
    if cleaned.endswith('.0'):
        cleaned = cleaned[:-2]
    return cleaned


def normalize_phone_for_display(phone):
    """Convert phone to display format (with leading 0)"""
    if not phone:
        return ""
    cleaned = re.sub(r'\D', '', str(phone).replace('.0', ''))
    if len(cleaned) == 9:
        cleaned = '0' + cleaned
    return cleaned


def search_customer_by_phone(phone):
    """Search for a customer by exact phone number across all branches"""
    cleaned_input = re.sub(r'\D', '', str(phone))
    search_phone = cleaned_input[1:] if cleaned_input.startswith('0') else cleaned_input
    
    if BRANCH_DATA_DIR.exists():
        for branch_folder in BRANCH_DATA_DIR.iterdir():
            if branch_folder.is_dir():
                customers_file = branch_folder / "customers.csv"
                if customers_file.exists():
                    try:
                        df = pd.read_csv(customers_file)
                        if not df.empty and "phone" in df.columns:
                            for idx, row in df.iterrows():
                                db_phone = str(row["phone"]).strip()
                                if db_phone.endswith('.0'):
                                    db_phone = db_phone[:-2]
                                db_phone_clean = re.sub(r'\D', '', db_phone)
                                
                                if db_phone_clean == search_phone:
                                    customer = row.to_dict()
                                    customer["found_in_branch"] = branch_folder.name
                                    customer["phone_display"] = normalize_phone_for_display(db_phone)
                                    return customer, branch_folder.name
                    except Exception as e:
                        print(f"Error reading {customers_file}: {e}")
    
    return None, None


# ==============================
# GET REAL CUSTOMER DATA FROM SALES
# ==============================

def get_customer_sales_data(phone):
    """
    Get real customer data from sales history across all branches.
    This calculates actual spent, orders, and purchase history.
    """
    cleaned_phone = re.sub(r'\D', '', str(phone))
    search_phone = cleaned_phone[1:] if cleaned_phone.startswith('0') else cleaned_phone
    
    all_sales = []
    branch_found = None
    
    if BRANCH_DATA_DIR.exists():
        for branch_folder in BRANCH_DATA_DIR.iterdir():
            if branch_folder.is_dir():
                sales_file = branch_folder / "sales.csv"
                if sales_file.exists():
                    try:
                        df = pd.read_csv(sales_file)
                        if not df.empty:
                            phone_col = None
                            for col in ["customer_phone", "phone", "customer_phone_str"]:
                                if col in df.columns:
                                    phone_col = col
                                    break
                            
                            if phone_col:
                                for idx, row in df.iterrows():
                                    db_phone = str(row.get(phone_col, "")).strip()
                                    if db_phone.endswith('.0'):
                                        db_phone = db_phone[:-2]
                                    db_phone_clean = re.sub(r'\D', '', db_phone)
                                    if db_phone_clean == search_phone:
                                        row_dict = row.to_dict()
                                        row_dict["branch"] = branch_folder.name
                                        name_col = None
                                        for col in ["customer_name", "customer", "name"]:
                                            if col in df.columns:
                                                name_col = col
                                                break
                                        if name_col:
                                            row_dict["customer_name_display"] = row.get(name_col, "Unknown")
                                        all_sales.append(row_dict)
                                        branch_found = branch_folder.name
                    except Exception as e:
                        print(f"Error reading sales: {e}")
    
    if not all_sales:
        return None, None, 0, 0, pd.DataFrame()
    
    sales_df = pd.DataFrame(all_sales)
    
    receipt_col = None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in sales_df.columns:
            receipt_col = col
            break
    
    amount_col = None
    for col in ["final_total", "total", "amount"]:
        if col in sales_df.columns:
            amount_col = col
            break
    
    if receipt_col and receipt_col in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        total_orders = len(unique_receipts)
        total_spent = to_float(unique_receipts[amount_col].sum()) if amount_col else 0
    else:
        total_orders = len(sales_df)
        total_spent = to_float(sales_df[amount_col].sum()) if amount_col else 0
    
    customer_name = "Valued Customer"
    name_col = None
    for col in ["customer_name", "customer", "name", "customer_name_display"]:
        if col in sales_df.columns and not sales_df[col].isna().all():
            name_col = col
            break
    
    if name_col:
        name_counts = sales_df[name_col].value_counts()
        if not name_counts.empty:
            customer_name = name_counts.index[0]
    
    date_col = None
    for col in ["date", "sale_date", "transaction_date"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.sort_values(date_col, ascending=False)
    
    return customer_name, branch_found, total_spent, total_orders, sales_df


def get_loyalty_for_customer(phone, branch):
    """Get loyalty data for a customer from their branch"""
    loyalty_file = BRANCH_DATA_DIR / branch / "loyalty_points.csv"
    search_phone = normalize_phone_for_storage(phone)
    
    if loyalty_file.exists():
        try:
            df = pd.read_csv(loyalty_file)
            if not df.empty and "phone" in df.columns:
                for idx, row in df.iterrows():
                    db_phone = str(row["phone"]).strip()
                    if db_phone.endswith('.0'):
                        db_phone = db_phone[:-2]
                    db_phone_clean = re.sub(r'\D', '', db_phone)
                    if db_phone_clean == search_phone:
                        return row.to_dict()
        except Exception as e:
            print(f"Error reading loyalty: {e}")
    
    return None


def authenticate_customer(phone):
    """
    Authenticate customer by phone number.
    Uses REAL sales data to get customer information.
    """
    cleaned_phone = re.sub(r'\D', '', str(phone))
    
    customer, found_branch = search_customer_by_phone(cleaned_phone)
    customer_name, sales_branch, total_spent, total_orders, sales_df = get_customer_sales_data(cleaned_phone)
    
    if customer is None and total_orders == 0:
        return False, None
    
    if customer is None:
        customer = {
            "customer_name": customer_name or "Valued Customer",
            "phone": normalize_phone_for_storage(cleaned_phone),
            "found_in_branch": sales_branch or "HO",
            "phone_display": normalize_phone_for_display(cleaned_phone)
        }
        found_branch = sales_branch or "HO"
    else:
        customer["customer_name"] = customer_name or customer.get("customer_name", "Valued Customer")
        customer["found_in_branch"] = sales_branch or customer.get("found_in_branch", "HO")
        found_branch = customer.get("found_in_branch", sales_branch or "HO")
    
    customer["total_spent"] = total_spent
    customer["total_orders"] = total_orders
    customer["total_transactions"] = total_orders
    customer["avg_transaction_value"] = total_spent / total_orders if total_orders > 0 else 0
    
    date_col = None
    for col in ["date", "sale_date", "transaction_date"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col and not sales_df.empty:
        customer["last_purchase_date"] = sales_df.iloc[0].get(date_col, datetime.now())
        customer["days_since_last_purchase"] = (datetime.now() - customer["last_purchase_date"]).days if customer["last_purchase_date"] else 999
    
    customer["purchase_history"] = sales_df.to_dict('records')
    
    loyalty_info = get_loyalty_for_customer(cleaned_phone, found_branch)
    
    if loyalty_info:
        for key, value in loyalty_info.items():
            if key not in customer:
                customer[key] = value
    else:
        customer["points"] = int(total_spent / 10)
        customer["tier"] = get_tier_from_spent(total_spent)
        customer["last_visit"] = datetime.now().strftime("%Y-%m-%d")
        customer["joined_date"] = datetime.now().strftime("%Y-%m-%d")
    
    customer["branch"] = found_branch
    
    return True, customer


def get_tier_from_spent(total_spent):
    """Determine tier based on total spent"""
    if total_spent >= 5000:
        return "PLATINUM"
    elif total_spent >= 2000:
        return "GOLD"
    elif total_spent >= 500:
        return "SILVER"
    else:
        return "BRONZE"


def register_customer(phone, name):
    """Register a new customer in the current branch"""
    current_branch = get_current_branch()
    
    cleaned_phone = re.sub(r'\D', '', str(phone))
    storage_phone = cleaned_phone[1:] if cleaned_phone.startswith('0') else cleaned_phone
    
    existing, existing_branch = search_customer_by_phone(cleaned_phone)
    if existing:
        return False, f"Customer already exists in {existing_branch} branch. Please login instead."
    
    customers_df = load_customers()
    
    new_id = f"CUST{len(customers_df)+1:04d}"
    new_customer = pd.DataFrame([{
        "customer_id": new_id,
        "customer_name": name.strip().title(),
        "phone": storage_phone,
        "total_orders": 0,
        "total_spent": 0,
        "last_purchase_date": "",
        "favorite_product": ""
    }])
    
    required_cols = ["customer_id", "customer_name", "phone", "total_orders", "total_spent", "last_purchase_date", "favorite_product"]
    for col in required_cols:
        if col not in customers_df.columns:
            customers_df[col] = "" if col in ["customer_id", "customer_name", "phone", "favorite_product"] else 0
    
    customers_df = pd.concat([customers_df, new_customer], ignore_index=True)
    save_customers(customers_df)
    
    loyalty_df = load_loyalty()
    new_loyalty = pd.DataFrame([{
        "customer_name": name.strip().title(),
        "phone": storage_phone,
        "points": 100,
        "tier": "BRONZE",
        "total_spent": 0,
        "total_orders": 0,
        "last_visit": datetime.now().strftime("%Y-%m-%d"),
        "birthday": "",
        "joined_date": datetime.now().strftime("%Y-%m-%d")
    }])
    
    loyalty_cols = ["customer_name", "phone", "points", "tier", "total_spent", "total_orders", "last_visit", "birthday", "joined_date"]
    for col in loyalty_cols:
        if col not in loyalty_df.columns:
            loyalty_df[col] = "" if col in ["customer_name", "phone", "birthday"] else 0
    
    loyalty_df = pd.concat([loyalty_df, new_loyalty], ignore_index=True)
    save_loyalty(loyalty_df)
    
    return True, f"Welcome {name}! You've earned 100 bonus points!"


def get_customer_purchase_history(phone, limit=20):
    """Get customer's purchase history from all branches"""
    cleaned_phone = re.sub(r'\D', '', str(phone))
    search_phone = cleaned_phone[1:] if cleaned_phone.startswith('0') else cleaned_phone
    
    all_sales = []
    
    if BRANCH_DATA_DIR.exists():
        for branch_folder in BRANCH_DATA_DIR.iterdir():
            if branch_folder.is_dir():
                sales_file = branch_folder / "sales.csv"
                if sales_file.exists():
                    try:
                        df = pd.read_csv(sales_file)
                        if not df.empty:
                            phone_col = None
                            for col in ["customer_phone", "phone", "customer_phone_str"]:
                                if col in df.columns:
                                    phone_col = col
                                    break
                            
                            if phone_col:
                                for idx, row in df.iterrows():
                                    db_phone = str(row.get(phone_col, "")).strip()
                                    if db_phone.endswith('.0'):
                                        db_phone = db_phone[:-2]
                                    db_phone_clean = re.sub(r'\D', '', db_phone)
                                    if db_phone_clean == search_phone:
                                        row_dict = row.to_dict()
                                        row_dict["branch"] = branch_folder.name
                                        all_sales.append(row_dict)
                    except Exception as e:
                        print(f"Error reading sales: {e}")
    
    if all_sales:
        result = pd.DataFrame(all_sales)
        date_col = None
        for col in ["date", "sale_date", "transaction_date"]:
            if col in result.columns:
                date_col = col
                break
        
        if date_col:
            result[date_col] = pd.to_datetime(result[date_col], errors="coerce")
            result = result.sort_values(date_col, ascending=False)
        
        receipt_col = None
        for col in ["receipt_no", "receipt", "transaction_id"]:
            if col in result.columns:
                receipt_col = col
                break
        
        if receipt_col:
            result = result.drop_duplicates(subset=[receipt_col])
        
        return result.head(limit)
    
    return pd.DataFrame()


def get_customer_recommendations(phone):
    """Get product recommendations based on purchase history"""
    sales_df = load_sales()
    products_df = load_products()
    
    if sales_df.empty or products_df.empty:
        return pd.DataFrame()
    
    name_col = "name" if "name" in sales_df.columns else "product_name" if "product_name" in sales_df.columns else None
    
    if name_col is None:
        return pd.DataFrame()
    
    cleaned_phone = re.sub(r'\D', '', str(phone))
    search_phone = cleaned_phone[1:] if cleaned_phone.startswith('0') else cleaned_phone
    
    phone_col = "customer_phone" if "customer_phone" in sales_df.columns else "phone" if "phone" in sales_df.columns else None
    
    if phone_col is None:
        top_products = sales_df.groupby(name_col)["items"].sum().nlargest(5).reset_index()
        top_products.columns = ["name", "items"]
        return top_products
    
    customer_sales = pd.DataFrame()
    for idx, row in sales_df.iterrows():
        db_phone = str(row.get(phone_col, "")).strip()
        if db_phone.endswith('.0'):
            db_phone = db_phone[:-2]
        db_phone_clean = re.sub(r'\D', '', db_phone)
        if db_phone_clean == search_phone:
            customer_sales = pd.concat([customer_sales, pd.DataFrame([row.to_dict()])])
    
    if customer_sales.empty:
        top_products = sales_df.groupby(name_col)["items"].sum().nlargest(5).reset_index()
        top_products.columns = ["name", "items"]
        return top_products
    
    top_customer_products = customer_sales.groupby(name_col)["items"].sum().nlargest(3).reset_index()
    top_customer_products.columns = ["name", "items"]
    return top_customer_products


def generate_digital_loyalty_card(customer_data):
    """Generate a digital loyalty card with QR code"""
    
    phone = customer_data.get("phone_display", normalize_phone_for_display(customer_data.get("phone", "")))
    points = customer_data.get("points", 0)
    tier = customer_data.get("tier", "BRONZE")
    name = customer_data.get("customer_name", "Valued Customer")
    branch = customer_data.get("branch", "HO")
    
    qr_data = f"LOYALTY|{branch}|{phone}|{name}|{points}|{tier}"
    
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    benefits = get_tier_benefits(tier)
    
    card_html = f"""
    <div style="
        width: 350px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        padding: 20px;
        color: white;
        margin: 10px auto;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    ">
        <div style="text-align: center; margin-bottom: 15px;">
            <h3 style="margin: 0; color: white;">AZIEL INVESTMENTS</h3>
            <p style="margin: 0; font-size: 12px;">Loyalty Card</p>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <p style="margin: 5px 0;"><strong>{name}</strong></p>
                <p style="margin: 5px 0; font-size: 12px;">{phone}</p>
                <p style="margin: 5px 0;"> Branch: {branch}</p>
                <p style="margin: 5px 0;">{tier}</p>
                <p style="margin: 5px 0;">{points} points</p>
            </div>
            <div>
                <img src="data:image/png;base64,{qr_base64}" width="100" height="100">
            </div>
        </div>
        <div style="margin-top: 15px; font-size: 10px; text-align: center; border-top: 1px solid rgba(255,255,255,0.3); padding-top: 10px;">
            <p>Benefits: {benefits.get('points_multiplier', 1)}x points | {benefits.get('discount', 0)}% discount</p>
            <p>Show this card at checkout to earn points!</p>
        </div>
    </div>
    """
    
    return card_html, qr_base64


def customer_login_page():
    """Professional and clean customer login/register page"""
    
    st.markdown("""
    <style>
        .main-container {
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
        }
        .login-card {
            background: white;
            border-radius: 24px;
            padding: 40px 35px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.08), 0 8px 24px rgba(0,0,0,0.04);
            border: 1px solid rgba(0,0,0,0.04);
        }
        .logo-section {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo-section h1 {
            font-size: 28px;
            font-weight: 700;
            color: #1a1a2e;
            margin: 10px 0 5px 0;
        }
        .logo-section p {
            color: #6B7280;
            font-size: 14px;
            margin: 0;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: #f8f9fa;
            border-radius: 12px;
            padding: 4px;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px;
            padding: 8px 24px;
            font-weight: 600;
            font-size: 14px;
            color: #6B7280;
            transition: all 0.3s ease;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: white;
            color: #1a1a2e;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .stTextInput > div > div > input {
            border-radius: 12px !important;
            border: 2px solid #e5e7eb !important;
            padding: 12px 16px !important;
            font-size: 15px !important;
            transition: all 0.3s ease;
        }
        .stTextInput > div > div > input:focus {
            border-color: #6366F1 !important;
            box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1) !important;
        }
        .stButton > button {
            border-radius: 12px !important;
            padding: 12px 24px !important;
            font-weight: 600 !important;
            font-size: 15px !important;
            transition: all 0.3s ease !important;
        }
        .stAlert {
            border-radius: 12px !important;
            border: none !important;
            padding: 14px 18px !important;
        }
        .info-box {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 12px 16px;
            margin: 8px 0;
            font-size: 13px;
            color: #4a5568;
            border-left: 4px solid #6366F1;
        }
        .divider {
            border: none;
            border-top: 1px solid #e5e7eb;
            margin: 20px 0;
        }
        @media (max-width: 600px) {
            .login-card {
                padding: 25px 20px;
            }
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="main-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    
    st.markdown('<div class="logo-section">', unsafe_allow_html=True)
    try:
        st.image("aziellogo.png", width=120)
    except:
        pass
    st.markdown('<h1>Welcome Back</h1>', unsafe_allow_html=True)
    st.markdown('<p>Sign in to view your loyalty rewards and purchase history</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔑 Sign In", "✨ Register"])
    
    with tab1:
        st.markdown('<div class="info-box">📱 Enter your phone number to access your account</div>', unsafe_allow_html=True)
        
        phone = st.text_input("Phone Number", placeholder="e.g., 0782905853", key="login_phone")
        
        if st.button("Sign In", type="primary", use_container_width=True):
            if phone:
                success, customer_data = authenticate_customer(phone)
                if success:
                    st.session_state.customer_logged_in = True
                    st.session_state.customer_data = customer_data
                    st.session_state.customer_phone = phone
                    st.session_state.customer_branch = customer_data.get("branch", "HO")
                    st.success(f"👋 Welcome back, {customer_data.get('customer_name')}!")
                    safe_rerun()
                else:
                    st.error("❌ Customer not found. Please register.")
            else:
                st.warning("⚠️ Please enter your phone number")
    
    with tab2:
        st.markdown('<div class="info-box">🎉 Create your account and earn 100 bonus points!</div>', unsafe_allow_html=True)
        
        name = st.text_input("Full Name", placeholder="John Doe", key="reg_name")
        phone = st.text_input("Phone Number", placeholder="e.g., 0772123456", key="reg_phone")
        
        if st.button("Create Account", type="primary", use_container_width=True):
            if name and phone:
                current_branch = get_current_branch()
                success, message = register_customer(phone, name)
                if success:
                    st.success(f"✅ {message}")
                    success, customer_data = authenticate_customer(phone)
                    if success:
                        st.session_state.customer_logged_in = True
                        st.session_state.customer_data = customer_data
                        st.session_state.customer_phone = phone
                        st.session_state.customer_branch = customer_data.get("branch", current_branch)
                        safe_rerun()
                else:
                    st.error(f"❌ {message}")
            else:
                st.warning("⚠️ Please fill all fields")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def customer_dashboard():
    """Professional customer dashboard with clean design"""
    
    products_df = load_products()
    
    customer = st.session_state.customer_data
    phone = st.session_state.customer_phone
    
    display_phone = normalize_phone_for_display(customer.get("phone", phone))
    
    st.markdown("""
    <style>
        .dashboard-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            flex-wrap: wrap;
        }
        .greeting-text {
            font-size: 28px;
            font-weight: 700;
            color: #1a1a2e;
        }
        .greeting-sub {
            color: #6B7280;
            font-size: 14px;
        }
        .metric-card {
            background: white;
            border-radius: 16px;
            padding: 18px 20px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.04);
            border: 1px solid #f0f0f0;
            text-align: center;
            transition: all 0.3s ease;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.06);
        }
        .metric-value {
            font-size: 24px;
            font-weight: 700;
            color: #1a1a2e;
        }
        .metric-label {
            font-size: 13px;
            color: #6B7280;
            margin-top: 4px;
        }
        .section-title {
            font-size: 20px;
            font-weight: 600;
            color: #1a1a2e;
            margin: 25px 0 15px 0;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.04);
            border: 1px solid #f0f0f0;
        }
        .product-item {
            background: #f8f9fa;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            border: 1px solid #f0f0f0;
            transition: all 0.3s ease;
        }
        .product-item:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.06);
        }
        .product-name {
            font-weight: 600;
            color: #1a1a2e;
            font-size: 14px;
        }
        .product-price {
            color: #22c55e;
            font-size: 18px;
            font-weight: 700;
            margin: 5px 0;
        }
        .product-tag {
            background: #e5e7eb;
            color: #4a5568;
            font-size: 11px;
            padding: 2px 12px;
            border-radius: 20px;
        }
        .logout-btn {
            background: none !important;
            border: 2px solid #e5e7eb !important;
            color: #4a5568 !important;
            border-radius: 12px !important;
            padding: 8px 20px !important;
            font-weight: 500 !important;
        }
        .logout-btn:hover {
            background: #fee2e2 !important;
            border-color: #f87171 !important;
            color: #dc2626 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown(f"""
    <div class="dashboard-header">
        <div>
            <div class="greeting-text">👋 {customer.get('customer_name', 'Valued Customer')}</div>
            <div class="greeting-sub">📱 {display_phone} • 🏢 {customer.get('branch', 'HO')}</div>
        </div>
        <div>
            <button onclick="window.location.href='?logout=true'" style="background:none;border:2px solid #e5e7eb;border-radius:12px;padding:8px 20px;color:#4a5568;font-weight:500;cursor:pointer;">🚪 Logout</button>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_spent = to_float(customer.get('total_spent', 0))
    total_orders = safe_int(customer.get('total_orders', 0))
    points = customer.get('points', 0)
    tier = customer.get('tier', 'BRONZE')
    
    tier_icons = {"BRONZE": "🥉", "SILVER": "🥈", "GOLD": "🥇", "PLATINUM": "💎"}
    tier_icon = tier_icons.get(tier, "🥉")
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${total_spent:,.2f}</div>
            <div class="metric-label">Total Spent</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total_orders}</div>
            <div class="metric-label">Orders</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{points:,}</div>
            <div class="metric-label">Points</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{tier_icon} {tier}</div>
            <div class="metric-label">Tier</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Two columns: Loyalty Card + Products
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown('<div class="section-title">💳 Loyalty Card</div>', unsafe_allow_html=True)
        card_html, qr_base64 = generate_digital_loyalty_card(customer)
        st.markdown(card_html, unsafe_allow_html=True)
        
        st.download_button(
            label="📥 Download QR Code",
            data=base64.b64decode(qr_base64),
            file_name=f"loyalty_qr_{display_phone}.png",
            mime="image/png",
            use_container_width=True
        )
    
    with col2:
        st.markdown('<div class="section-title">🛍️ Products Available</div>', unsafe_allow_html=True)
        
        if not products_df.empty:
            product_cols = st.columns(2)
            for idx, (_, product) in enumerate(products_df.head(4).iterrows()):
                with product_cols[idx % 2]:
                    product_name = product.get("name", "Unknown Product")
                    product_price = to_float(product.get("price", 0))
                    
                    st.markdown(f"""
                    <div class="product-item">
                        <div class="product-name">{product_name[:25]}</div>
                        <div class="product-price">${product_price:.2f}</div>
                        <span class="product-tag">In Stock</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            if len(products_df) > 4:
                st.caption(f"Showing 4 of {len(products_df)} products available")
        else:
            st.info("No products available at the moment.")
    
    st.markdown("---")
    
    # Purchase History
    st.markdown('<div class="section-title">📜 Purchase History</div>', unsafe_allow_html=True)
    
    purchase_history = get_customer_purchase_history(phone, 20)
    
    if not purchase_history.empty:
        display_cols = []
        
        date_col = None
        for col in ["date", "sale_date", "transaction_date"]:
            if col in purchase_history.columns:
                date_col = col
                break
        
        if date_col:
            display_cols.append(date_col)
            purchase_history[date_col] = pd.to_datetime(purchase_history[date_col], errors="coerce")
            purchase_history[date_col] = purchase_history[date_col].dt.strftime("%Y-%m-%d %H:%M")
        
        receipt_col = None
        for col in ["receipt_no", "receipt", "transaction_id"]:
            if col in purchase_history.columns:
                receipt_col = col
                break
        
        if receipt_col:
            display_cols.append(receipt_col)
        
        amount_col = None
        for col in ["final_total", "total", "amount"]:
            if col in purchase_history.columns:
                amount_col = col
                break
        
        if amount_col:
            display_cols.append(amount_col)
            purchase_history[amount_col] = purchase_history[amount_col].apply(to_float)
        
        if "items" in purchase_history.columns:
            display_cols.append("items")
        
        payment_col = None
        for col in ["payment_method", "payment_type"]:
            if col in purchase_history.columns:
                payment_col = col
                break
        
        if payment_col:
            display_cols.append(payment_col)
        
        if "branch" in purchase_history.columns:
            display_cols.append("branch")
        
        if display_cols:
            st.dataframe(
                purchase_history[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    amount_col: st.column_config.NumberColumn("Amount", format="$%.2f") if amount_col else None
                } if amount_col else {}
            )
        else:
            st.dataframe(purchase_history, use_container_width=True, hide_index=True)
        
        st.caption(f"Showing {len(purchase_history)} purchases")
    else:
        st.info("No purchase history yet. Start shopping to earn points!")
    
    st.markdown("---")
    
    # Recommendations
    st.markdown('<div class="section-title">🎯 Recommended for You</div>', unsafe_allow_html=True)
    
    recommendations = get_customer_recommendations(phone)
    
    if not recommendations.empty and "name" in recommendations.columns:
        cols = st.columns(min(3, len(recommendations)))
        for idx, (_, product) in enumerate(recommendations.head(3).iterrows()):
            with cols[idx % len(cols)]:
                product_name = product['name']
                product_price = 0
                if not products_df.empty and "name" in products_df.columns:
                    product_match = products_df[products_df["name"] == product_name]
                    if not product_match.empty:
                        product_price = to_float(product_match.iloc[0].get("price", 0))
                
                st.markdown(f"""
                <div class="product-item">
                    <div class="product-name">{product['name'][:25]}</div>
                    <div class="product-price">${product_price:.2f}</div>
                    <span class="product-tag">⭐ Recommended</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Start shopping to get personalized recommendations!")
    
    st.markdown("---")
    
    # Redeem Points
    st.markdown('<div class="section-title">🔄 Redeem Points</div>', unsafe_allow_html=True)
    
    current_points = customer.get('points', 0)
    points_value = current_points / 100
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"💎 Your {current_points} points are worth **${points_value:.2f}** discount!")
        st.caption("100 points = $1 discount")
    
    with col2:
        if current_points >= 100:
            if st.button("🔄 Redeem Now", use_container_width=True):
                st.session_state.show_redeem = True
        
        if st.session_state.get("show_redeem", False):
            points_to_redeem = st.number_input(
                "Points to redeem",
                min_value=100,
                max_value=current_points,
                step=100,
                value=min(500, current_points)
            )
            
            if st.button("✅ Confirm Redemption", use_container_width=True):
                st.info(f"Show this screen at checkout to redeem {points_to_redeem} points for ${points_to_redeem/100:.2f} discount!")
    
    st.markdown("---")
    
    # Stay Connected
    st.markdown('<div class="section-title">📱 Stay Connected</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        whatsapp_link = get_whatsapp_link(display_phone, "I want to receive loyalty updates and offers!")
        if whatsapp_link:
            st.markdown(f"""
            <a href="{whatsapp_link}" target="_blank">
                <button style="background:#25D366;color:white;border:none;border-radius:30px;padding:10px;width:100%;cursor:pointer;font-weight:600;">
                    💬 WhatsApp
                </button>
            </a>
            """, unsafe_allow_html=True)
    
    with col2:
        if st.button("📞 Contact Support", use_container_width=True):
            st.info("Call us: +263 78 290 5853")
    
    with col3:
        if st.button("🚪 Logout", use_container_width=True):
            logout_customer()
    
    st.markdown("""
    <div style="text-align:center;color:#6B7280;font-size:12px;margin-top:20px;padding-top:15px;border-top:1px solid #e5e7eb;">
        Aziel Investments • SmartGro ERP • Version 3.0
    </div>
    """, unsafe_allow_html=True)


# ==============================
# MAIN CUSTOMER APP
# ==============================
def customer_app():
    """Main customer app entry point"""
    
    init_customer_session()
    
    if not st.session_state.customer_logged_in:
        customer_login_page()
    else:
        customer_dashboard()


# ==============================
# ADMIN: CUSTOMER INSIGHTS
# ==============================
def customer_insights_page():
    """Admin page for customer insights across all branches"""
    
    st.markdown("## Customer Insights Dashboard")
    st.caption("Analytics about customer behavior and loyalty program across all branches")
    
    all_customers = []
    if BRANCH_DATA_DIR.exists():
        for branch_folder in BRANCH_DATA_DIR.iterdir():
            if branch_folder.is_dir():
                customers_file = branch_folder / "customers.csv"
                if customers_file.exists():
                    try:
                        df = pd.read_csv(customers_file)
                        if not df.empty:
                            df["branch"] = branch_folder.name
                            all_customers.append(df)
                    except Exception as e:
                        print(f"Error reading {customers_file}: {e}")
    
    if not all_customers:
        st.info("No customer data available")
        return
    
    customers_df = pd.concat(all_customers, ignore_index=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Customers", len(customers_df))
    with col2:
        total_spent = customers_df["total_spent"].sum() if "total_spent" in customers_df.columns else 0
        st.metric("Total Spent", f"${to_float(total_spent):,.2f}")
    with col3:
        avg_spent = customers_df["total_spent"].mean() if "total_spent" in customers_df.columns else 0
        st.metric("Avg Order Value", f"${to_float(avg_spent):.2f}")
    with col4:
        st.metric("Active Branches", len(customers_df["branch"].unique()) if "branch" in customers_df.columns else 1)
    
    if "branch" in customers_df.columns:
        st.markdown("### Customers by Branch")
        branch_counts = customers_df["branch"].value_counts().reset_index()
        branch_counts.columns = ["Branch", "Count"]
        st.dataframe(branch_counts, use_container_width=True, hide_index=True)
    
    st.markdown("### Top Customers by Spending")
    if "total_spent" in customers_df.columns:
        top_customers = customers_df.nlargest(10, "total_spent")[["customer_name", "phone", "total_spent", "total_orders", "branch"]]
        st.dataframe(top_customers, use_container_width=True, hide_index=True)
    else:
        st.info("No spending data available")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customer_app()