# backend/analytics/customer_360_view.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import load_customers, load_sales, load_products, load_customer_transactions, to_float
from backend.modules.loyalty import get_customer_loyalty_info
from backend.analytics.debtors_engine import load_debtors


# ==============================
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_str(value, default=""):
    """Safely convert value to string"""
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default


def get_receipt_column(df):
    """Find receipt number column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    """Find amount column"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_customer_column(df):
    """Find customer name column"""
    if df is None or df.empty:
        return None
    for col in ["customer_name", "customer", "name", "client_name"]:
        if col in df.columns:
            return col
    return None


def get_phone_column(df):
    """Find phone column"""
    if df is None or df.empty:
        return None
    for col in ["phone", "customer_phone", "contact", "mobile"]:
        if col in df.columns:
            return col
    return None


def get_date_column(df):
    """Find date column"""
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


# ==============================
# EXTRACT CUSTOMERS FROM SALES
# ==============================

def extract_customers_from_sales(sales_df):
    """
    Extract unique customers from sales data using unduplicated receipts.
    """
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()
    
    customer_col = get_customer_column(sales_df)
    phone_col = get_phone_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    
    if customer_col is None:
        return pd.DataFrame()
    
    # Use receipt-level deduplication to get unique customers
    if receipt_col and receipt_col in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        customer_data = unique_receipts[[customer_col]].copy()
        
        if phone_col and phone_col in sales_df.columns:
            customer_data["phone"] = unique_receipts[phone_col].astype(str)
        else:
            customer_data["phone"] = ""
    else:
        customer_data = sales_df[[customer_col]].copy()
        if phone_col and phone_col in sales_df.columns:
            customer_data["phone"] = sales_df[phone_col].astype(str)
        else:
            customer_data["phone"] = ""
    
    customer_data.columns = ["customer_name", "phone"]
    
    # Clean data - remove Walk-in and empty entries
    customer_data = customer_data.drop_duplicates(subset=["customer_name", "phone"])
    customer_data = customer_data[
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('walk-in', na=False) &
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('unknown', na=False) &
        (customer_data["customer_name"].astype(str).str.strip() != '') &
        (customer_data["customer_name"].astype(str).str.strip() != 'nan') &
        (customer_data["customer_name"].astype(str).str.strip() != 'None')
    ]
    
    return customer_data


def get_combined_customers(customers_df, sales_df):
    """Combine customers from both table and sales data."""
    sales_customers = extract_customers_from_sales(sales_df)
    
    if not sales_customers.empty:
        return sales_customers
    
    if customers_df is not None and not customers_df.empty:
        customer_col = get_customer_column(customers_df)
        phone_col = get_phone_column(customers_df)
        
        if customer_col:
            result = customers_df[[customer_col]].copy()
            result.columns = ["customer_name"]
            if phone_col and phone_col in customers_df.columns:
                result["phone"] = customers_df[phone_col].astype(str)
            else:
                result["phone"] = ""
            return result
    
    return pd.DataFrame()


# ==============================
# CUSTOMER 360 ANALYTICS ENGINE
# ==============================

def get_customer_complete_profile(phone, sales_df=None):
    """Get complete 360° profile for a customer using unduplicated data"""
    
    if sales_df is None:
        sales_df = load_sales()
    
    customers_df = load_customers()
    transactions_df = load_customer_transactions()
    debtors_df = load_debtors()
    
    customer_data = {}
    phone_str = str(phone)
    
    if not sales_df.empty:
        phone_col = get_phone_column(sales_df)
        customer_col = get_customer_column(sales_df)
        receipt_col = get_receipt_column(sales_df)
        amount_col = get_amount_column(sales_df)
        date_col = get_date_column(sales_df)
        
        if phone_col and phone_col in sales_df.columns:
            sales_df["phone_str"] = sales_df[phone_col].astype(str)
            customer_sales = sales_df[sales_df["phone_str"] == phone_str]
            
            if not customer_sales.empty:
                # Get customer name
                if customer_col and customer_col in sales_df.columns:
                    customer_data["customer_name"] = safe_str(customer_sales.iloc[0].get(customer_col, "Unknown"))
                else:
                    customer_data["customer_name"] = "Unknown"
                
                customer_data["phone"] = phone_str
                
                # ==============================
                # FIX: Use unduplicated receipts for all calculations
                # ==============================
                if receipt_col and receipt_col in customer_sales.columns:
                    unique_receipts = customer_sales.drop_duplicates(subset=[receipt_col])
                    total_transactions = len(unique_receipts)
                    total_spent = safe_float(unique_receipts[amount_col].sum()) if amount_col and amount_col in unique_receipts.columns else 0
                    
                    # Get items count from original sales (sum of items across all rows)
                    if "items" in customer_sales.columns:
                        total_items = safe_int(customer_sales["items"].sum())
                    else:
                        total_items = 0
                else:
                    unique_receipts = customer_sales
                    total_transactions = len(customer_sales)
                    total_spent = safe_float(customer_sales[amount_col].sum()) if amount_col and amount_col in customer_sales.columns else 0
                    total_items = safe_int(customer_sales["items"].sum()) if "items" in customer_sales.columns else 0
                
                customer_data["total_transactions"] = total_transactions
                customer_data["total_spent"] = total_spent
                customer_data["total_orders"] = total_transactions
                customer_data["avg_transaction_value"] = total_spent / total_transactions if total_transactions > 0 else 0
                customer_data["total_items"] = total_items
                
                # Get last purchase date
                if date_col:
                    customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
                    last_date = customer_sales[date_col].max()
                    if pd.notna(last_date):
                        customer_data["last_purchase_date"] = last_date
                        customer_data["days_since_last_purchase"] = (datetime.now() - last_date).days
                    else:
                        customer_data["days_since_last_purchase"] = 999
                else:
                    customer_data["days_since_last_purchase"] = 999
                
                # Get payment methods
                payment_col = None
                for col in ["payment_method", "payment_type"]:
                    if col in customer_sales.columns:
                        payment_col = col
                        break
                
                if payment_col:
                    customer_data["payment_methods"] = customer_sales[payment_col].unique().tolist()
                
                # ==============================
                # FIX: Store unduplicated purchase history
                # ==============================
                if receipt_col and receipt_col in customer_sales.columns:
                    # Use unique receipts for purchase history
                    history_data = unique_receipts.copy()
                else:
                    history_data = customer_sales.copy()
                
                # Convert to dict and store
                customer_data["purchase_history"] = history_data.to_dict('records')
    
    if not customer_data and not customers_df.empty:
        phone_col = get_phone_column(customers_df)
        if phone_col and phone_col in customers_df.columns:
            customers_df["phone_str"] = customers_df[phone_col].astype(str)
            customer = customers_df[customers_df["phone_str"] == phone_str]
            if not customer.empty:
                row = customer.iloc[0]
                customer_data["customer_name"] = safe_str(row.get("customer_name", "Unknown"))
                customer_data["phone"] = phone_str
                customer_data["total_spent"] = safe_float(row.get("total_spent", 0))
                customer_data["total_orders"] = safe_int(row.get("total_orders", 0))
                customer_data["total_transactions"] = customer_data["total_orders"]
                customer_data["days_since_last_purchase"] = 999
    
    if not customer_data:
        return None
    
    # Get loyalty info
    loyalty_info = get_customer_loyalty_info(phone_str)
    if loyalty_info:
        customer_data.update(loyalty_info)
    
    # Get debt info
    if not debtors_df.empty:
        phone_col = get_phone_column(debtors_df)
        if phone_col and phone_col in debtors_df.columns:
            debtors_df["phone_str"] = debtors_df[phone_col].astype(str)
            customer_debts = debtors_df[debtors_df["phone_str"] == phone_str]
            
            if not customer_debts.empty:
                balance_col = None
                for col in ["balance", "outstanding", "amount_due"]:
                    if col in customer_debts.columns:
                        balance_col = col
                        break
                
                if balance_col:
                    customer_data["total_debt"] = safe_float(customer_debts[balance_col].sum())
                    customer_data["has_debt"] = customer_data["total_debt"] > 0
                    customer_data["debt_details"] = customer_debts.to_dict('records')
    
    # Get favorite products
    if not transactions_df.empty and "phone" in transactions_df.columns:
        transactions_df["phone_str"] = transactions_df["phone"].astype(str)
        customer_transactions = transactions_df[transactions_df["phone_str"] == phone_str]
        
        if not customer_transactions.empty and "product_name" in customer_transactions.columns:
            favorite_products = customer_transactions.groupby("product_name")["quantity"].sum().nlargest(5).to_dict()
            customer_data["favorite_products"] = favorite_products
    
    return customer_data


def predict_churn_risk(customer_data):
    """Predict customer churn risk based on behavior"""
    
    risk_score = 0
    risk_factors = []
    
    days_since = customer_data.get("days_since_last_purchase", 999)
    if days_since is None or days_since > 999:
        days_since = 999
    
    if days_since > 90:
        risk_score += 40
        risk_factors.append(f"No purchase in {days_since} days")
    elif days_since > 60:
        risk_score += 25
        risk_factors.append(f"No purchase in {days_since} days")
    elif days_since > 30:
        risk_score += 10
        risk_factors.append(f"No purchase in {days_since} days")
    
    transactions = customer_data.get("total_transactions", 0)
    if transactions <= 1:
        risk_score += 25
        risk_factors.append("Only 1 transaction - low engagement")
    elif transactions <= 3:
        risk_score += 10
        risk_factors.append("Low transaction frequency")
    
    avg_value = customer_data.get("avg_transaction_value", 0)
    if avg_value < 10:
        risk_score += 15
        risk_factors.append("Low average transaction value")
    
    if customer_data.get("has_debt", False):
        risk_score += 20
        risk_factors.append("Has outstanding debt")
    
    if risk_score >= 70:
        risk_level = "HIGH"
        risk_color = "red"
        recommendation = "Immediate re-engagement campaign needed"
    elif risk_score >= 40:
        risk_level = "MEDIUM"
        risk_color = "orange"
        recommendation = "Send special offers to encourage repeat purchase"
    elif risk_score >= 20:
        risk_level = "LOW"
        risk_color = "yellow"
        recommendation = "Monitor and maintain relationship"
    else:
        risk_level = "VERY LOW"
        risk_color = "green"
        recommendation = "Continue current engagement strategy"
    
    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "risk_factors": risk_factors,
        "recommendation": recommendation
    }


def predict_next_purchase(customer_data):
    """Predict when customer will likely make next purchase"""
    
    purchase_history = customer_data.get("purchase_history", [])
    
    if purchase_history and len(purchase_history) >= 2:
        dates = []
        for sale in purchase_history:
            for col in ["date", "sale_date", "transaction_date"]:
                if col in sale:
                    try:
                        dates.append(pd.to_datetime(sale[col]))
                        break
                    except:
                        pass
        
        if len(dates) >= 2:
            dates = sorted(dates)
            date_diffs = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
            
            if date_diffs:
                avg_days_between = np.mean(date_diffs)
                last_purchase = dates[-1]
                predicted_date = last_purchase + timedelta(days=int(avg_days_between))
                days_from_now = (predicted_date - datetime.now()).days
                
                return {
                    "predicted_date": predicted_date,
                    "days_from_now": max(0, days_from_now),
                    "confidence": "High" if len(date_diffs) >= 3 else "Medium",
                    "avg_days_between": int(avg_days_between)
                }
    
    return {
        "predicted_date": datetime.now() + timedelta(days=30),
        "days_from_now": 30,
        "confidence": "Low",
        "avg_days_between": 30
    }


def get_personalized_recommendations(customer_data):
    """Get personalized product recommendations"""
    
    favorite_products = customer_data.get("favorite_products", {})
    products_df = load_products()
    
    recommendations = []
    
    if favorite_products and not products_df.empty:
        fav_product_names = list(favorite_products.keys())
        
        for product_name in fav_product_names[:3]:
            product = products_df[products_df["name"] == product_name]
            if not product.empty:
                category = product.iloc[0].get("category", "")
                if category:
                    similar = products_df[products_df["category"] == category]
                    similar = similar[similar["name"] != product_name]
                    for _, p in similar.head(2).iterrows():
                        recommendations.append({
                            "product_name": p.get("name", "Unknown"),
                            "price": safe_float(p.get("price", 0)),
                            "reason": f"Similar to {product_name}",
                            "category": category
                        })
    
    if not recommendations:
        sales_df = load_sales()
        if not sales_df.empty:
            name_col = get_customer_column(sales_df)
            if name_col and name_col in sales_df.columns:
                top_products = sales_df.groupby(name_col)["items"].sum().nlargest(5).reset_index()
                for _, p in top_products.iterrows():
                    product_name = p.get(name_col, "Unknown")
                    product = products_df[products_df["name"] == product_name]
                    price = safe_float(product.iloc[0]["price"]) if not product.empty else 0
                    recommendations.append({
                        "product_name": product_name,
                        "price": price,
                        "reason": "Popular item",
                        "category": ""
                    })
    
    return recommendations[:6]


def calculate_customer_lifetime_value(customer_data):
    """Calculate Customer Lifetime Value (CLV) using unduplicated data"""
    
    total_spent = safe_float(customer_data.get("total_spent", 0))
    total_orders = safe_int(customer_data.get("total_orders", 0))
    
    avg_order = total_spent / total_orders if total_orders > 0 else 0
    
    days_since = customer_data.get("days_since_last_purchase", 365)
    if days_since is None or days_since < 1:
        days_since = 1
    
    # Purchase frequency per year
    purchase_frequency = (total_orders / days_since) * 365 if total_orders > 0 and days_since > 0 else 0
    
    # Cap at reasonable values
    purchase_frequency = min(purchase_frequency, 365)  # Max once per day
    
    customer_lifespan = 3
    
    clv = avg_order * purchase_frequency * customer_lifespan
    
    return {
        "clv": clv,
        "avg_order_value": avg_order,
        "purchase_frequency": purchase_frequency,
        "estimated_lifespan_years": customer_lifespan,
        "tier": customer_data.get("tier", "BRONZE")
    }


def get_customer_segment(customer_data):
    """Determine customer segment based on behavior"""
    
    total_spent = safe_float(customer_data.get("total_spent", 0))
    total_orders = safe_int(customer_data.get("total_orders", 0))
    days_since = customer_data.get("days_since_last_purchase", 999)
    if days_since is None:
        days_since = 999
    
    if total_spent >= 500 and total_orders >= 5:
        return "VIP - High Value Loyal"
    
    if total_spent >= 500:
        return "High Value"
    
    if total_orders >= 5:
        return "Frequent Buyer"
    
    if total_spent >= 150:
        return "Regular"
    
    if days_since > 60:
        return "At Risk"
    
    if total_orders <= 2:
        return "New Customer"
    
    return "Standard"


# ==============================
# CUSTOMER 360 DASHBOARD
# ==============================

def customer_360_view():
    """Customer 360° View Dashboard"""
    
    st.title("Customer 360° View")
    st.caption("Complete customer intelligence with AI-powered insights")
    
    sales_df = load_sales()
    customers_df = load_customers()
    
    customer_list = get_combined_customers(customers_df, sales_df)
    
    if customer_list.empty:
        st.warning("No customers found. Customers are recorded during sales checkout.")
        st.info("Tip: When making a sale, enter a customer name (not 'Walk-in') to build customer profiles.")
        return
    
    st.sidebar.markdown("### Customer Info")
    st.sidebar.write(f"Total Customers: {len(customer_list)}")
    st.sidebar.write(f"Total Sales: {len(sales_df)}")
    
    # ==============================
    # CUSTOMER SEARCH
    # ==============================
    st.markdown("## Find Customer")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        search_term = st.text_input("Search by Name or Phone", placeholder="Enter customer name or phone number...")
    
    with col2:
        if st.button("Search", type="primary", use_container_width=True):
            st.session_state.search_customer = search_term
    
    if search_term:
        filtered_customers = customer_list[
            customer_list["customer_name"].str.contains(search_term, case=False) |
            customer_list["phone"].str.contains(search_term)
        ]
    else:
        filtered_customers = customer_list.head(20)
    
    if filtered_customers.empty:
        st.warning("No customers found matching your search")
        return
    
    customer_options = []
    customer_map = {}
    
    for _, row in filtered_customers.iterrows():
        phone_val = safe_str(row["phone"])
        name_val = safe_str(row["customer_name"])
        display_text = f"{name_val} - {phone_val}"
        customer_options.append(display_text)
        customer_map[display_text] = phone_val
    
    selected_display = st.selectbox(
        "Select Customer",
        customer_options
    )
    
    if selected_display:
        selected_customer = customer_map[selected_display]
        
        profile = get_customer_complete_profile(selected_customer, sales_df)
        
        if profile:
            # ==============================
            # HEADER
            # ==============================
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Customer", profile.get("customer_name", "N/A"))
            with col2:
                st.metric("Phone", profile.get("phone", "N/A"))
            with col3:
                st.metric("Tier", profile.get("tier", "BRONZE"))
            with col4:
                segment = get_customer_segment(profile)
                st.metric("Segment", segment.split(" - ")[0] if " - " in segment else segment)
            
            st.markdown("---")
            
            # ==============================
            # KEY METRICS
            # ==============================
            st.markdown("## Key Metrics")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            total_spent = safe_float(profile.get('total_spent', 0))
            total_orders = safe_int(profile.get('total_orders', 0))
            avg_order = safe_float(profile.get('avg_transaction_value', 0))
            days_since = profile.get('days_since_last_purchase', 'N/A')
            
            with col1:
                st.metric("Total Spent", f"${total_spent:,.2f}")
            with col2:
                st.metric("Orders", total_orders)
            with col3:
                st.metric("Points", f"{profile.get('points', 0):,}")
            with col4:
                if days_since != 'N/A' and days_since is not None:
                    st.metric("Days Since Last", f"{int(days_since)} days")
                else:
                    st.metric("Last Purchase", "Never")
            with col5:
                st.metric("Avg Order", f"${avg_order:.2f}")
            
            st.markdown("---")
            
            # ==============================
            # CHURN RISK
            # ==============================
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("## Churn Risk Analysis")
                
                churn = predict_churn_risk(profile)
                
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=churn["risk_score"],
                    title={"text": f"Risk Score - {churn['risk_level']}"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": churn["risk_color"]},
                        "steps": [
                            {"range": [0, 30], "color": "lightgreen"},
                            {"range": [30, 60], "color": "yellow"},
                            {"range": [60, 100], "color": "salmon"}
                        ]
                    }
                ))
                fig_gauge.update_layout(height=250)
                st.plotly_chart(fig_gauge, use_container_width=True)
                
                for factor in churn["risk_factors"]:
                    st.warning(factor)
                
                st.info(f"**Recommendation:** {churn['recommendation']}")
            
            with col2:
                st.markdown("## Next Purchase Prediction")
                
                prediction = predict_next_purchase(profile)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Predicted Date", prediction["predicted_date"].strftime("%Y-%m-%d"))
                with col_b:
                    st.metric("Days from Now", f"{prediction['days_from_now']} days")
                
                st.progress(min(1.0, prediction["days_from_now"] / 90))
                st.caption(f"Confidence: {prediction['confidence']}")
                st.info(f"Average between purchases: {prediction['avg_days_between']} days")
            
            st.markdown("---")
            
            # ==============================
            # CLV
            # ==============================
            st.markdown("## Customer Lifetime Value (CLV)")
            
            clv_data = calculate_customer_lifetime_value(profile)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("CLV", f"${clv_data['clv']:,.2f}")
            with col2:
                st.metric("Avg Order", f"${clv_data['avg_order_value']:.2f}")
            with col3:
                st.metric("Frequency", f"{clv_data['purchase_frequency']:.1f}/year")
            with col4:
                st.metric("Lifespan", f"{clv_data['estimated_lifespan_years']} years")
            
            st.markdown("---")
            
            # ==============================
            # FAVORITE PRODUCTS
            # ==============================
            st.markdown("## Favorite Products")
            
            favorite_products = profile.get("favorite_products", {})
            
            if favorite_products:
                fav_df = pd.DataFrame([
                    {"Product": name, "Quantity": qty} 
                    for name, qty in favorite_products.items()
                ])
                
                fig_fav = px.bar(
                    fav_df,
                    x="Quantity",
                    y="Product",
                    orientation='h',
                    title="Top Purchased Products",
                    color="Quantity",
                    color_continuous_scale="Viridis",
                    text="Quantity"
                )
                fig_fav.update_layout(height=300)
                st.plotly_chart(fig_fav, use_container_width=True)
            else:
                st.info("No favorite products data available")
            
            st.markdown("---")
            
            # ==============================
            # RECOMMENDATIONS
            # ==============================
            st.markdown("## Personalized Recommendations")
            
            recommendations = get_personalized_recommendations(profile)
            
            if recommendations:
                cols = st.columns(min(3, len(recommendations)))
                for idx, rec in enumerate(recommendations[:3]):
                    with cols[idx]:
                        st.markdown(f"""
                        <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; margin: 5px; text-align: center;">
                            <h4>{rec['product_name'][:25]}</h4>
                            <p style="font-size: 20px; color: green;">${rec['price']:.2f}</p>
                            <p style="font-size: 12px; color: gray;">{rec['reason']}</p>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("Not enough data for personalized recommendations")
            
            st.markdown("---")
            
            # ==============================
            # PURCHASE HISTORY - FIXED
            # ==============================
            st.markdown("## Purchase History")
            
            purchase_history = profile.get("purchase_history", [])
            
            if purchase_history:
                history_df = pd.DataFrame(purchase_history)
                
                # Standardize column names for display
                display_cols = []
                col_mapping = {}
                
                # Date column
                date_col = None
                for col in ["date", "sale_date", "transaction_date"]:
                    if col in history_df.columns:
                        date_col = col
                        break
                
                if date_col:
                    display_cols.append(date_col)
                    history_df[date_col] = pd.to_datetime(history_df[date_col], errors="coerce")
                    history_df[date_col] = history_df[date_col].dt.strftime("%Y-%m-%d %H:%M")
                
                # Receipt number
                receipt_col = None
                for col in ["receipt_no", "receipt", "transaction_id"]:
                    if col in history_df.columns:
                        receipt_col = col
                        break
                
                if receipt_col:
                    display_cols.append(receipt_col)
                
                # Customer
                customer_col = None
                for col in ["customer_name", "customer"]:
                    if col in history_df.columns:
                        customer_col = col
                        break
                
                if customer_col:
                    display_cols.append(customer_col)
                
                # Amount
                amount_col = None
                for col in ["final_total", "total"]:
                    if col in history_df.columns:
                        amount_col = col
                        break
                
                if amount_col:
                    display_cols.append(amount_col)
                    # Format the amount
                    history_df[amount_col] = history_df[amount_col].apply(safe_float)
                
                # Items
                if "items" in history_df.columns:
                    display_cols.append("items")
                
                # Payment method
                payment_col = None
                for col in ["payment_method", "payment_type"]:
                    if col in history_df.columns:
                        payment_col = col
                        break
                
                if payment_col:
                    display_cols.append(payment_col)
                
                if display_cols:
                    # Show the data with proper formatting
                    st.dataframe(
                        history_df[display_cols],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            amount_col: st.column_config.NumberColumn("Amount", format="$%.2f") if amount_col else None
                        } if amount_col else {}
                    )
                else:
                    # Show all columns if we couldn't find standard ones
                    st.dataframe(history_df, use_container_width=True, hide_index=True)
                
                st.caption(f"Showing {len(history_df)} purchases")
            else:
                st.info("No purchase history available")
            
            # ==============================
            # DEBT INFORMATION
            # ==============================
            if profile.get("has_debt", False):
                st.markdown("---")
                st.markdown("## Debt Information")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.error(f"Outstanding Debt: ${safe_float(profile.get('total_debt', 0)):,.2f}")
                with col2:
                    if st.button("View Debt Details", use_container_width=True):
                        debt_details = profile.get("debt_details", [])
                        if debt_details:
                            st.dataframe(pd.DataFrame(debt_details), use_container_width=True)
        else:
            st.error("Could not load customer profile")


# ==============================
# CUSTOMER INSIGHTS DASHBOARD
# ==============================

def customer_insights_360():
    """Admin dashboard for customer insights"""
    
    st.title("Customer Intelligence Dashboard")
    st.caption("AI-powered insights across all customers")
    
    sales_df = load_sales()
    customers_df = load_customers()
    
    customer_list = get_combined_customers(customers_df, sales_df)
    
    if customer_list.empty:
        st.warning("No customer data available. Customers are recorded during sales.")
        return
    
    # Overall metrics using unduplicated data
    st.markdown("## Overall Customer Metrics")
    
    total_customers = len(customer_list)
    
    # Calculate metrics from unduplicated sales
    total_revenue = 0
    total_transactions = 0
    
    receipt_col = get_receipt_column(sales_df)
    amount_col = get_amount_column(sales_df)
    
    if not sales_df.empty and amount_col:
        if receipt_col and receipt_col in sales_df.columns:
            unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
            total_revenue = safe_float(unique_receipts[amount_col].sum())
            total_transactions = len(unique_receipts)
        else:
            total_revenue = safe_float(sales_df[amount_col].sum())
            total_transactions = len(sales_df)
    
    avg_spent = total_revenue / total_customers if total_customers > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Customers", total_customers)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("Avg Customer Spend", f"${avg_spent:.2f}")
    with col4:
        # Active customers (last 90 days)
        date_col = get_date_column(sales_df)
        phone_col = get_phone_column(sales_df)
        active_customers = 0
        if date_col and phone_col:
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=90)
            recent_sales = sales_df[sales_df[date_col] >= cutoff]
            if not recent_sales.empty and phone_col in recent_sales.columns:
                active_customers = recent_sales[phone_col].nunique()
        st.metric("Active Customers (90 days)", active_customers)
    
    st.markdown("---")
    
    # Customer segmentation
    st.markdown("## Customer Segmentation")
    
    segments = []
    for _, customer in customer_list.iterrows():
        phone_str = safe_str(customer["phone"])
        profile = get_customer_complete_profile(phone_str, sales_df)
        if profile:
            segment = get_customer_segment(profile)
            segments.append(segment)
    
    if segments:
        segment_counts = pd.Series(segments).value_counts().reset_index()
        segment_counts.columns = ["Segment", "Count"]
        
        fig_segments = px.pie(
            segment_counts,
            values="Count",
            names="Segment",
            title="Customer Segment Distribution",
            hole=0.4
        )
        st.plotly_chart(fig_segments, use_container_width=True)
    
    st.markdown("---")
    
    # At-risk customers
    st.markdown("## At-Risk Customers")
    
    at_risk_customers = []
    for _, customer in customer_list.iterrows():
        phone_str = safe_str(customer["phone"])
        profile = get_customer_complete_profile(phone_str, sales_df)
        if profile:
            churn = predict_churn_risk(profile)
            if churn["risk_level"] in ["HIGH", "MEDIUM"]:
                at_risk_customers.append({
                    "Customer": profile.get("customer_name", "N/A"),
                    "Phone": profile.get("phone", "N/A"),
                    "Risk Level": churn["risk_level"],
                    "Risk Score": churn["risk_score"],
                    "Days Since Last": profile.get("days_since_last_purchase", "N/A"),
                    "Total Spent": safe_float(profile.get("total_spent", 0))
                })
    
    if at_risk_customers:
        at_risk_df = pd.DataFrame(at_risk_customers).sort_values("Risk Score", ascending=False)
        st.dataframe(
            at_risk_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total Spent": st.column_config.NumberColumn("Total Spent", format="$%.2f")
            }
        )
        
        csv = at_risk_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download At-Risk Customers List",
            data=csv,
            file_name=f"at_risk_customers_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.success("No at-risk customers detected!")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customer_360_view()