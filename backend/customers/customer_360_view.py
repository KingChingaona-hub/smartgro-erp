import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import load_customers, load_sales, load_products, load_customer_transactions
from backend.modules.loyalty import get_customer_loyalty_info
from backend.analytics.debtors_engine import load_debtors

# ==============================
# CUSTOMER 360 ANALYTICS ENGINE
# ==============================

def get_customer_complete_profile(phone):
    """Get complete 360° profile for a customer"""
    
    customers_df = load_customers()
    sales_df = load_sales()
    transactions_df = load_customer_transactions()
    debtors_df = load_debtors()
    
    # Find customer
    if customers_df.empty or "phone" not in customers_df.columns:
        return None
    
    customers_df["phone_str"] = customers_df["phone"].astype(str)
    customer = customers_df[customers_df["phone_str"] == str(phone)]
    
    if customer.empty:
        return None
    
    customer_data = customer.iloc[0].to_dict()
    
    # Get loyalty info
    loyalty_info = get_customer_loyalty_info(phone)
    if loyalty_info:
        customer_data.update(loyalty_info)
    
    # Get purchase history
    if not sales_df.empty and "customer_phone" in sales_df.columns:
        sales_df["customer_phone_str"] = sales_df["customer_phone"].astype(str)
        customer_sales = sales_df[sales_df["customer_phone_str"] == str(phone)]
        customer_data["purchase_history"] = customer_sales.to_dict('records') if not customer_sales.empty else []
        
        # Calculate metrics
        customer_data["total_transactions"] = len(customer_sales)
        customer_data["total_revenue"] = customer_sales["final_total"].sum() if "final_total" in customer_sales.columns else customer_sales["total"].sum()
        customer_data["avg_transaction_value"] = customer_data["total_revenue"] / customer_data["total_transactions"] if customer_data["total_transactions"] > 0 else 0
        
        # Get last purchase date
        if "date" in customer_sales.columns:
            customer_sales["date"] = pd.to_datetime(customer_sales["date"])
            customer_data["last_purchase_date"] = customer_sales["date"].max()
            customer_data["days_since_last_purchase"] = (datetime.now() - customer_data["last_purchase_date"]).days
    
    # Get favorite products
    if not transactions_df.empty and "phone" in transactions_df.columns:
        transactions_df["phone_str"] = transactions_df["phone"].astype(str)
        customer_transactions = transactions_df[transactions_df["phone_str"] == str(phone)]
        
        if not customer_transactions.empty and "product_name" in customer_transactions.columns:
            favorite_products = customer_transactions.groupby("product_name")["quantity"].sum().nlargest(5).to_dict()
            customer_data["favorite_products"] = favorite_products
    
    # Get debt info
    if not debtors_df.empty and "phone" in debtors_df.columns:
        debtors_df["phone_str"] = debtors_df["phone"].astype(str)
        customer_debts = debtors_df[debtors_df["phone_str"] == str(phone)]
        
        if not customer_debts.empty:
            customer_data["total_debt"] = customer_debts["balance"].sum()
            customer_data["has_debt"] = customer_data["total_debt"] > 0
            customer_data["debt_details"] = customer_debts.to_dict('records')
    
    return customer_data


def predict_churn_risk(customer_data):
    """Predict customer churn risk based on behavior"""
    
    risk_score = 0
    risk_factors = []
    
    # Factor 1: Days since last purchase
    days_since = customer_data.get("days_since_last_purchase", 999)
    if days_since > 90:
        risk_score += 40
        risk_factors.append(f"⚠️ No purchase in {days_since} days")
    elif days_since > 60:
        risk_score += 25
        risk_factors.append(f"⚠️ No purchase in {days_since} days")
    elif days_since > 30:
        risk_score += 10
        risk_factors.append(f"⚠️ No purchase in {days_since} days")
    
    # Factor 2: Transaction frequency
    transactions = customer_data.get("total_transactions", 0)
    if transactions <= 1:
        risk_score += 25
        risk_factors.append("⚠️ Only 1 transaction - low engagement")
    elif transactions <= 3:
        risk_score += 10
        risk_factors.append("⚠️ Low transaction frequency")
    
    # Factor 3: Average transaction value trend
    avg_value = customer_data.get("avg_transaction_value", 0)
    if avg_value < 10:
        risk_score += 15
        risk_factors.append("⚠️ Low average transaction value")
    
    # Factor 4: Debt status
    if customer_data.get("has_debt", False):
        risk_score += 20
        risk_factors.append("⚠️ Has outstanding debt")
    
    # Determine risk level
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
    
    sales_df = load_sales()
    phone = customer_data.get("phone")
    
    if not sales_df.empty and "customer_phone" in sales_df.columns and phone:
        sales_df["customer_phone_str"] = sales_df["customer_phone"].astype(str)
        customer_sales = sales_df[sales_df["customer_phone_str"] == str(phone)]
        
        if len(customer_sales) >= 2:
            # Calculate average days between purchases
            customer_sales = customer_sales.sort_values("date")
            customer_sales["date"] = pd.to_datetime(customer_sales["date"])
            date_diffs = customer_sales["date"].diff().dt.days.dropna()
            
            if not date_diffs.empty:
                avg_days_between = date_diffs.mean()
                last_purchase = customer_sales["date"].max()
                predicted_date = last_purchase + timedelta(days=int(avg_days_between))
                days_from_now = (predicted_date - datetime.now()).days
                
                return {
                    "predicted_date": predicted_date,
                    "days_from_now": max(0, days_from_now),
                    "confidence": "Medium" if len(date_diffs) >= 3 else "Low",
                    "avg_days_between": int(avg_days_between)
                }
    
    # Default prediction
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
        # Get top favorite categories
        fav_product_names = list(favorite_products.keys())
        
        # Find similar products (by category)
        for product_name in fav_product_names[:3]:
            product = products_df[products_df["name"] == product_name]
            if not product.empty:
                category = product.iloc[0].get("category", "")
                if category:
                    similar = products_df[products_df["category"] == category]
                    similar = similar[similar["name"] != product_name]
                    for _, p in similar.head(2).iterrows():
                        recommendations.append({
                            "product_name": p["name"],
                            "price": p["price"],
                            "reason": f"Similar to {product_name}",
                            "category": category
                        })
    
    # If no recommendations, show top selling products
    if not recommendations:
        sales_df = load_sales()
        if not sales_df.empty and "name" in sales_df.columns:
            top_products = sales_df.groupby("name")["items"].sum().nlargest(5).reset_index()
            for _, p in top_products.iterrows():
                product = products_df[products_df["name"] == p["name"]]
                price = product.iloc[0]["price"] if not product.empty else 0
                recommendations.append({
                    "product_name": p["name"],
                    "price": price,
                    "reason": "Popular item",
                    "category": ""
                })
    
    return recommendations[:6]


def calculate_customer_lifetime_value(customer_data):
    """Calculate Customer Lifetime Value (CLV)"""
    
    total_spent = customer_data.get("total_spent", 0)
    total_orders = customer_data.get("total_orders", 0)
    
    # Average order value
    avg_order = total_spent / total_orders if total_orders > 0 else 0
    
    # Purchase frequency (orders per year)
    days_as_customer = customer_data.get("days_since_last_purchase", 365)
    if days_as_customer < 1:
        days_as_customer = 1
    purchase_frequency = (total_orders / days_as_customer) * 365
    
    # Customer lifespan (estimated 3 years for retail)
    customer_lifespan = 3  # years
    
    # CLV = Avg Order × Purchase Frequency × Lifespan
    clv = avg_order * purchase_frequency * customer_lifespan
    
    return {
        "clv": clv,
        "avg_order_value": avg_order,
        "purchase_frequency": purchase_frequency,
        "estimated_lifespan_years": customer_lifespan,
        "tier": customer_data.get("tier", "🥉 BRONZE")
    }


def get_customer_segment(customer_data):
    """Determine customer segment based on behavior"""
    
    total_spent = customer_data.get("total_spent", 0)
    total_orders = customer_data.get("total_orders", 0)
    days_since = customer_data.get("days_since_last_purchase", 999)
    avg_order = customer_data.get("avg_transaction_value", 0)
    
    # High Value Loyal
    if total_spent >= 500 and total_orders >= 5:
        return "👑 VIP - High Value Loyal"
    
    # High Value
    if total_spent >= 500:
        return "💰 High Value"
    
    # Frequent Buyer
    if total_orders >= 5:
        return "🔄 Frequent Buyer"
    
    # Regular
    if total_spent >= 150:
        return "⭐ Regular"
    
    # At Risk
    if days_since > 60:
        return "⚠️ At Risk"
    
    # New
    if total_orders <= 2:
        return "🆕 New Customer"
    
    return "📊 Standard"


# ==============================
# CUSTOMER 360 DASHBOARD
# ==============================
def customer_360_view():
    """Customer 360° View Dashboard"""
    
    st.title("👤 Customer 360° View")
    st.caption("Complete customer intelligence with AI-powered insights")
    
    customers_df = load_customers()
    
    if customers_df.empty:
        st.warning("No customers found. Add customers first.")
        return
    
    # ==============================
    # CUSTOMER SEARCH
    # ==============================
    st.markdown("## 🔍 Find Customer")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        search_term = st.text_input("Search by Name or Phone", placeholder="Enter customer name or phone number...")
    
    with col2:
        if st.button("🔍 Search", type="primary", use_container_width=True):
            st.session_state.search_customer = search_term
    
    # Filter customers
    if search_term:
        filtered_customers = customers_df[
            customers_df["customer_name"].str.contains(search_term, case=False) |
            customers_df["phone"].astype(str).str.contains(search_term)
        ]
    else:
        filtered_customers = customers_df.head(20)
    
    if filtered_customers.empty:
        st.warning("No customers found matching your search")
        return
    
    # Create display options safely
    customer_options = []
    customer_map = {}
    
    for _, row in filtered_customers.iterrows():
        phone_val = str(row["phone"])
        name_val = row["customer_name"]
        display_text = f"{name_val} - {phone_val}"
        customer_options.append(display_text)
        customer_map[display_text] = phone_val
    
    # Select customer
    selected_display = st.selectbox(
        "Select Customer",
        customer_options
    )
    
    if selected_display:
        selected_customer = customer_map[selected_display]
        
        # Get complete profile
        profile = get_customer_complete_profile(selected_customer)
        
        if profile:
            # ==============================
            # HEADER SECTION
            # ==============================
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("👤 Customer", profile.get("customer_name", "N/A"))
            with col2:
                st.metric("📞 Phone", profile.get("phone", "N/A"))
            with col3:
                st.metric("🏆 Tier", profile.get("tier", "🥉 BRONZE"))
            with col4:
                segment = get_customer_segment(profile)
                st.metric("📊 Segment", segment.split(" - ")[0] if " - " in segment else segment)
            
            st.markdown("---")
            
            # ==============================
            # KEY METRICS
            # ==============================
            st.markdown("## 📊 Key Metrics")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("💰 Total Spent", f"${profile.get('total_spent', 0):,.2f}")
            with col2:
                st.metric("🛒 Orders", profile.get('total_orders', 0))
            with col3:
                st.metric("⭐ Points", f"{profile.get('points', 0):,}")
            with col4:
                days_since = profile.get('days_since_last_purchase', 'N/A')
                if days_since != 'N/A':
                    st.metric("📅 Days Since Last", f"{days_since} days")
                else:
                    st.metric("📅 Last Purchase", "Never")
            with col5:
                st.metric("💳 Avg Order", f"${profile.get('avg_transaction_value', 0):.2f}")
            
            st.markdown("---")
            
            # ==============================
            # CHURN RISK & PREDICTIONS
            # ==============================
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("## 🚨 Churn Risk Analysis")
                
                churn = predict_churn_risk(profile)
                
                # Risk gauge
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
                
                st.info(f"💡 **Recommendation:** {churn['recommendation']}")
            
            with col2:
                st.markdown("## 🔮 Next Purchase Prediction")
                
                prediction = predict_next_purchase(profile)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("📅 Predicted Date", prediction["predicted_date"].strftime("%Y-%m-%d"))
                with col_b:
                    st.metric("⏰ Days from Now", f"{prediction['days_from_now']} days")
                
                st.progress(min(1.0, prediction["days_from_now"] / 90))
                st.caption(f"Confidence: {prediction['confidence']}")
                st.info(f"Average between purchases: {prediction['avg_days_between']} days")
            
            st.markdown("---")
            
            # ==============================
            # CUSTOMER LIFETIME VALUE
            # ==============================
            st.markdown("## 💰 Customer Lifetime Value (CLV)")
            
            clv_data = calculate_customer_lifetime_value(profile)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 CLV", f"${clv_data['clv']:,.2f}")
            with col2:
                st.metric("💵 Avg Order", f"${clv_data['avg_order_value']:.2f}")
            with col3:
                st.metric("🔄 Frequency", f"{clv_data['purchase_frequency']:.1f}/year")
            with col4:
                st.metric("📅 Lifespan", f"{clv_data['estimated_lifespan_years']} years")
            
            st.markdown("---")
            
            # ==============================
            # FAVORITE PRODUCTS
            # ==============================
            st.markdown("## ❤️ Favorite Products")
            
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
            # PERSONALIZED RECOMMENDATIONS
            # ==============================
            st.markdown("## 🎯 Personalized Recommendations")
            
            recommendations = get_personalized_recommendations(profile)
            
            if recommendations:
                cols = st.columns(min(3, len(recommendations)))
                for idx, rec in enumerate(recommendations[:3]):
                    with cols[idx]:
                        st.markdown(f"""
                        <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; margin: 5px; text-align: center;">
                            <h4>📦 {rec['product_name'][:25]}</h4>
                            <p style="font-size: 20px; color: green;">${rec['price']:.2f}</p>
                            <p style="font-size: 12px; color: gray;">{rec['reason']}</p>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("Not enough data for personalized recommendations")
            
            st.markdown("---")
            
            # ==============================
            # PURCHASE HISTORY
            # ==============================
            st.markdown("## 📜 Purchase History")
            
            purchase_history = profile.get("purchase_history", [])
            
            if purchase_history:
                history_df = pd.DataFrame(purchase_history)
                display_cols = ["date", "receipt_no", "items", "total", "payment_method"]
                available_cols = [col for col in display_cols if col in history_df.columns]
                
                st.dataframe(
                    history_df[available_cols].head(20),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "total": st.column_config.NumberColumn("Amount", format="$%.2f")
                    }
                )
            else:
                st.info("No purchase history available")
            
            # ==============================
            # DEBT INFORMATION
            # ==============================
            if profile.get("has_debt", False):
                st.markdown("---")
                st.markdown("## ⚠️ Debt Information")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.error(f"💰 Outstanding Debt: ${profile.get('total_debt', 0):,.2f}")
                with col2:
                    if st.button("📋 View Debt Details", use_container_width=True):
                        debt_details = profile.get("debt_details", [])
                        if debt_details:
                            st.dataframe(pd.DataFrame(debt_details), use_container_width=True)
        else:
            st.error("Could not load customer profile")


# ==============================
# CUSTOMER INSIGHTS DASHBOARD (Admin)
# ==============================
def customer_insights_360():
    """Admin dashboard for customer insights"""
    
    st.title("📊 Customer Intelligence Dashboard")
    st.caption("AI-powered insights across all customers")
    
    customers_df = load_customers()
    sales_df = load_sales()
    
    if customers_df.empty:
        st.warning("No customer data available")
        return
    
    # ==============================
    # OVERALL METRICS
    # ==============================
    st.markdown("## 📈 Overall Customer Metrics")
    
    total_customers = len(customers_df)
    total_revenue = customers_df["total_spent"].sum() if "total_spent" in customers_df.columns else 0
    avg_spent = customers_df["total_spent"].mean() if "total_spent" in customers_df.columns else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("👥 Total Customers", total_customers)
    with col2:
        st.metric("💰 Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("📊 Avg Customer Spend", f"${avg_spent:.2f}")
    with col4:
        active_customers = len(customers_df[customers_df["total_orders"] > 0]) if "total_orders" in customers_df.columns else 0
        st.metric("🟢 Active Customers", active_customers)
    
    st.markdown("---")
    
    # ==============================
    # CUSTOMER SEGMENTATION
    # ==============================
    st.markdown("## 🎯 Customer Segmentation")
    
    # Calculate segments for all customers
    segments = []
    for _, customer in customers_df.iterrows():
        phone_str = str(customer["phone"])
        profile = get_customer_complete_profile(phone_str)
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
    
    # ==============================
    # AT-RISK CUSTOMERS
    # ==============================
    st.markdown("## ⚠️ At-Risk Customers")
    
    at_risk_customers = []
    for _, customer in customers_df.iterrows():
        phone_str = str(customer["phone"])
        profile = get_customer_complete_profile(phone_str)
        if profile:
            churn = predict_churn_risk(profile)
            if churn["risk_level"] in ["HIGH", "MEDIUM"]:
                at_risk_customers.append({
                    "Customer": profile.get("customer_name", "N/A"),
                    "Phone": profile.get("phone", "N/A"),
                    "Risk Level": churn["risk_level"],
                    "Risk Score": churn["risk_score"],
                    "Days Since Last": profile.get("days_since_last_purchase", "N/A"),
                    "Total Spent": profile.get("total_spent", 0)
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
        
        # Export button
        csv = at_risk_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download At-Risk Customers List",
            data=csv,
            file_name=f"at_risk_customers_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.success("✅ No at-risk customers detected!")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customer_360_view()