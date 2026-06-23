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
    """Authenticate customer by phone number across all branches"""
    cleaned_phone = re.sub(r'\D', '', str(phone))
    customer, found_branch = search_customer_by_phone(cleaned_phone)
    
    if customer is None:
        return False, None
    
    loyalty_info = get_loyalty_for_customer(cleaned_phone, found_branch)
    
    if loyalty_info:
        for key, value in loyalty_info.items():
            if key not in customer:
                customer[key] = value
    else:
        customer["points"] = 0
        customer["tier"] = "🥉 BRONZE"
        customer["last_visit"] = datetime.now().strftime("%Y-%m-%d")
        customer["joined_date"] = datetime.now().strftime("%Y-%m-%d")
    
    customer["branch"] = found_branch
    
    return True, customer


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
        "tier": "🥉 BRONZE",
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
                        if not df.empty and "customer_phone" in df.columns:
                            for idx, row in df.iterrows():
                                db_phone = str(row.get("customer_phone", "")).strip()
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
        if "date" in result.columns:
            result = result.sort_values("date", ascending=False).drop_duplicates(subset=["receipt_no"]).head(limit)
        return result
    
    return pd.DataFrame()


def get_customer_recommendations(phone):
    """Get product recommendations based on purchase history"""
    sales_df = load_sales()
    products_df = load_products()
    
    if sales_df.empty or products_df.empty:
        return pd.DataFrame()
    
    # Determine product name column
    name_col = "name" if "name" in sales_df.columns else "product_name" if "product_name" in sales_df.columns else None
    
    if name_col is None:
        return pd.DataFrame()
    
    cleaned_phone = re.sub(r'\D', '', str(phone))
    search_phone = cleaned_phone[1:] if cleaned_phone.startswith('0') else cleaned_phone
    
    # Get customer's phone column
    phone_col = "customer_phone" if "customer_phone" in sales_df.columns else "phone" if "phone" in sales_df.columns else None
    
    if phone_col is None:
        # Return top selling products if no customer phone column
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
        # Return top selling products
        top_products = sales_df.groupby(name_col)["items"].sum().nlargest(5).reset_index()
        top_products.columns = ["name", "items"]
        return top_products
    
    # Get customer's top products
    top_customer_products = customer_sales.groupby(name_col)["items"].sum().nlargest(3).reset_index()
    top_customer_products.columns = ["name", "items"]
    return top_customer_products


def generate_digital_loyalty_card(customer_data):
    """Generate a digital loyalty card with QR code"""
    
    phone = customer_data.get("phone_display", normalize_phone_for_display(customer_data.get("phone", "")))
    points = customer_data.get("points", 0)
    tier = customer_data.get("tier", "🥉 BRONZE")
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
                <p style="margin: 5px 0; font-size: 12px;">📞 {phone}</p>
                <p style="margin: 5px 0;">📍 Branch: {branch}</p>
                <p style="margin: 5px 0;">🏆 {tier}</p>
                <p style="margin: 5px 0;">⭐ {points} points</p>
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
    """Customer login/register page"""
    
    st.markdown("""
    <style>
        .customer-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.1);
            max-width: 500px;
            margin: 0 auto;
        }
        .stButton > button {
            background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%) !important;
            color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='customer-card'>", unsafe_allow_html=True)
    
    try:
        st.image("aziellogo.png", width=150)
    except:
        pass
    st.markdown("<h2 style='text-align:center;'>Customer Portal</h2>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
    
    with tab1:
        phone = st.text_input("Phone Number", placeholder="e.g., 0772123456 or 782905853", key="login_phone")
        
        if st.button("Login", type="primary", use_container_width=True):
            if phone:
                success, customer_data = authenticate_customer(phone)
                if success:
                    st.session_state.customer_logged_in = True
                    st.session_state.customer_data = customer_data
                    st.session_state.customer_phone = phone
                    st.session_state.customer_branch = customer_data.get("branch", "HO")
                    st.success(f"Welcome back, {customer_data.get('customer_name')}!")
                    st.rerun()
                else:
                    st.error("Customer not found. Please register.")
            else:
                st.error("Please enter your phone number")
    
    with tab2:
        current_branch = get_current_branch()
        st.info(f"📍 Registering for branch: {current_branch}")
        
        name = st.text_input("Full Name", placeholder="John Doe", key="reg_name")
        phone = st.text_input("Phone Number", placeholder="e.g., 0772123456", key="reg_phone")
        
        if st.button("Register", type="primary", use_container_width=True):
            if name and phone:
                success, message = register_customer(phone, name)
                if success:
                    st.success(message)
                    success, customer_data = authenticate_customer(phone)
                    if success:
                        st.session_state.customer_logged_in = True
                        st.session_state.customer_data = customer_data
                        st.session_state.customer_phone = phone
                        st.session_state.customer_branch = customer_data.get("branch", current_branch)
                        st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please fill all fields")
    
    st.markdown("</div>", unsafe_allow_html=True)


def customer_dashboard():
    """Customer app main dashboard"""
    
    # Load products at the start for recommendations
    products_df = load_products()
    
    customer = st.session_state.customer_data
    phone = st.session_state.customer_phone
    
    display_phone = normalize_phone_for_display(customer.get("phone", phone))
    
    st.title("🎁 My Loyalty Dashboard")
    st.caption(f"Welcome back, {customer.get('customer_name', 'Valued Customer')}!")
    
    if customer.get("branch"):
        st.info(f"📍 Registered Branch: {customer.get('branch')}")
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🏆 Tier", customer.get('tier', '🥉 BRONZE'))
    with col2:
        st.metric("⭐ Points", f"{customer.get('points', 0):,}")
    with col3:
        st.metric("💰 Total Spent", f"${to_float(customer.get('total_spent', 0)):,.2f}")
    with col4:
        st.metric("🛒 Orders", customer.get('total_orders', 0))
    
    st.markdown("---")
    
    # Digital Loyalty Card
    st.markdown("## 💳 Digital Loyalty Card")
    
    card_html, qr_base64 = generate_digital_loyalty_card(customer)
    st.markdown(card_html, unsafe_allow_html=True)
    
    st.download_button(
        label="📥 Download QR Code",
        data=base64.b64decode(qr_base64),
        file_name=f"loyalty_qr_{display_phone}.png",
        mime="image/png",
        use_container_width=True
    )
    
    st.markdown("---")
    
    # Tier Benefits
    st.markdown("## ✨ Your Tier Benefits")
    
    tier = customer.get('tier', '🥉 BRONZE')
    benefits = get_tier_benefits(tier)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Points Multiplier", f"{benefits.get('points_multiplier', 1)}x")
    with col2:
        st.metric("Tier Discount", f"{benefits.get('discount', 0)}%")
    with col3:
        st.metric("Birthday Bonus", f"{benefits.get('birthday_bonus', 50)} pts")
    with col4:
        st.metric("Free Delivery", "✅" if benefits.get('free_delivery', False) else "❌")
    
    # Next Tier Progress
    st.markdown("### 🎯 Next Tier Progress")
    
    current_spent = to_float(customer.get('total_spent', 0))
    if current_spent < 500:
        next_tier = "🥈 SILVER"
        next_amount = 500 - current_spent
        progress = current_spent / 500
    elif current_spent < 2000:
        next_tier = "🥇 GOLD"
        next_amount = 2000 - current_spent
        progress = current_spent / 2000
    elif current_spent < 5000:
        next_tier = "👑 PLATINUM"
        next_amount = 5000 - current_spent
        progress = current_spent / 5000
    else:
        next_tier = "👑 PLATINUM (Max)"
        next_amount = 0
        progress = 1
    
    st.progress(min(progress, 1.0))
    if next_amount > 0:
        st.caption(f"Spend ${next_amount:,.2f} more to reach {next_tier}")
    else:
        st.caption("🎉 You've reached the highest tier! Congratulations!")
    
    st.markdown("---")
    
    # Purchase History
    st.markdown("## 📜 My Purchase History")
    
    purchase_history = get_customer_purchase_history(phone, 10)
    
    if not purchase_history.empty:
        display_cols = ["date", "receipt_no", "items", "total", "payment_method", "branch"]
        available_cols = [col for col in display_cols if col in purchase_history.columns]
        
        st.dataframe(
            purchase_history[available_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total": st.column_config.NumberColumn("Amount", format="$%.2f")
            }
        )
    else:
        st.info("No purchase history yet. Start shopping to earn points!")
    
    st.markdown("---")
    
    # Recommendations
    st.markdown("## 🛍️ Recommended for You")
    
    recommendations = get_customer_recommendations(phone)
    
    if not recommendations.empty and "name" in recommendations.columns:
        cols = st.columns(min(3, len(recommendations)))
        for idx, (_, product) in enumerate(recommendations.head(3).iterrows()):
            with cols[idx % len(cols)]:
                # Get product price from products table
                product_name = product['name']
                product_price = 0
                if not products_df.empty and "name" in products_df.columns:
                    product_match = products_df[products_df["name"] == product_name]
                    if not product_match.empty:
                        product_price = to_float(product_match.iloc[0].get("price", 0))
                
                st.markdown(f"""
                <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; text-align: center;">
                    <h4>📦 {product['name'][:20]}</h4>
                    <p style="font-size: 24px; color: green;">${product_price:.2f}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Start shopping to get personalized recommendations!")
    
    st.markdown("---")
    
    # Redeem Points
    st.markdown("## 💎 Redeem Points")
    
    current_points = customer.get('points', 0)
    points_value = current_points / 100
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info(f"💰 Your {current_points} points are worth **${points_value:.2f}** discount!")
        st.caption("100 points = $1 discount")
    
    with col2:
        if current_points >= 100:
            if st.button("🎁 Redeem Now", use_container_width=True):
                st.session_state.show_redeem = True
        
        if st.session_state.get("show_redeem", False):
            points_to_redeem = st.number_input(
                "Points to redeem",
                min_value=100,
                max_value=current_points,
                step=100,
                value=min(500, current_points)
            )
            
            if st.button("Confirm Redemption", use_container_width=True):
                st.info(f"🎉 Show this screen at checkout to redeem {points_to_redeem} points for ${points_to_redeem/100:.2f} discount!")
    
    st.markdown("---")
    
    # Stay Connected
    st.markdown("## 📱 Stay Connected")
    
    col1, col2 = st.columns(2)
    
    with col1:
        whatsapp_link = get_whatsapp_link(display_phone, "I want to receive loyalty updates and offers!")
        if whatsapp_link:
            st.markdown(f"""
            <a href="{whatsapp_link}" target="_blank">
                <button style="background:#25D366;color:white;border:none;border-radius:30px;padding:10px;width:100%;cursor:pointer;">
                    📱 Get Offers on WhatsApp
                </button>
            </a>
            """, unsafe_allow_html=True)
    
    with col2:
        if st.button("📞 Contact Support", use_container_width=True):
            st.info("Call us: +263 78 290 5853")
    
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.customer_logged_in = False
        st.session_state.customer_data = None
        st.session_state.customer_phone = None
        st.session_state.customer_branch = None
        st.rerun()


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
    
    st.markdown("## 📊 Customer Insights Dashboard")
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