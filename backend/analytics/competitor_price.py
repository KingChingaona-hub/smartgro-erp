import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from pathlib import Path
import json

# Import animations
from backend.core.animations import show_toast, show_confetti

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
COMPETITOR_FILE = DATA_DIR / "competitors.csv"
PRICE_MONITOR_FILE = DATA_DIR / "price_monitoring.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_price_monitoring_files():
    """Initialize competitor price monitoring files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Competitors file
    if not COMPETITOR_FILE.exists():
        df = pd.DataFrame(columns=[
            "competitor_id", "name", "website", "location", "rating", "notes", "added_date", "added_by"
        ])
        df.to_csv(COMPETITOR_FILE, index=False)
    
    # Price monitoring file
    if not PRICE_MONITOR_FILE.exists():
        df = pd.DataFrame(columns=[
            "id", "product_name", "product_barcode", "competitor_id", "competitor_name",
            "our_price", "competitor_price", "price_difference", "difference_percent",
            "date_recorded", "recorded_by", "notes"
        ])
        df.to_csv(PRICE_MONITOR_FILE, index=False)


def load_competitors():
    """Load all competitors"""
    init_price_monitoring_files()
    return pd.read_csv(COMPETITOR_FILE)


def save_competitors(df):
    """Save competitors to file"""
    df.to_csv(COMPETITOR_FILE, index=False)


def load_price_monitoring():
    """Load all price monitoring records"""
    init_price_monitoring_files()
    df = pd.read_csv(PRICE_MONITOR_FILE)
    
    # Convert numeric columns
    numeric_cols = ["our_price", "competitor_price", "price_difference", "difference_percent"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    return df


def save_price_monitoring(df):
    """Save price monitoring records"""
    df.to_csv(PRICE_MONITOR_FILE, index=False)


def add_competitor(name, website, location, rating, notes, added_by):
    """Add a new competitor"""
    df = load_competitors()
    
    competitor_id = f"COMP{len(df)+1:04d}"
    
    new_competitor = pd.DataFrame([{
        "competitor_id": competitor_id,
        "name": name,
        "website": website,
        "location": location,
        "rating": rating,
        "notes": notes,
        "added_date": datetime.now().isoformat(),
        "added_by": added_by
    }])
    
    df = pd.concat([df, new_competitor], ignore_index=True)
    save_competitors(df)
    
    return competitor_id


def record_price_comparison(product_name, product_barcode, competitor_id, competitor_name, 
                            our_price, competitor_price, notes, recorded_by):
    """Record a price comparison"""
    df = load_price_monitoring()
    
    record_id = f"PR{len(df)+1:06d}"
    price_difference = competitor_price - our_price
    difference_percent = (price_difference / our_price) * 100 if our_price > 0 else 0
    
    new_record = pd.DataFrame([{
        "id": record_id,
        "product_name": product_name,
        "product_barcode": product_barcode,
        "competitor_id": competitor_id,
        "competitor_name": competitor_name,
        "our_price": our_price,
        "competitor_price": competitor_price,
        "price_difference": price_difference,
        "difference_percent": difference_percent,
        "date_recorded": datetime.now().isoformat(),
        "recorded_by": recorded_by,
        "notes": notes
    }])
    
    df = pd.concat([df, new_record], ignore_index=True)
    save_price_monitoring(df)
    
    return record_id


def get_price_analysis():
    """Get price comparison analysis"""
    df = load_price_monitoring()
    
    if df.empty:
        return {
            "total_comparisons": 0,
            "avg_price_difference": 0,
            "products_cheaper": 0,
            "products_expensive": 0,
            "best_opportunities": pd.DataFrame()
        }
    
    analysis = {
        "total_comparisons": len(df),
        "avg_price_difference": df["price_difference"].mean(),
        "products_cheaper": len(df[df["price_difference"] > 0]),  # Competitor more expensive
        "products_expensive": len(df[df["price_difference"] < 0]),  # Competitor cheaper
        "best_opportunities": df.nlargest(10, "price_difference")[["product_name", "competitor_name", "our_price", "competitor_price", "price_difference"]]
    }
    
    return analysis


def get_price_trends(product_name=None):
    """Get price trends over time for a product"""
    df = load_price_monitoring()
    
    if df.empty:
        return pd.DataFrame()
    
    if product_name:
        df = df[df["product_name"] == product_name]
    
    df["date_recorded"] = pd.to_datetime(df["date_recorded"])
    df = df.sort_values("date_recorded")
    
    return df


def get_price_alert_products(threshold_percent=20):
    """Get products where competitor price is significantly lower"""
    df = load_price_monitoring()
    
    if df.empty:
        return pd.DataFrame()
    
    # Find products where competitor is cheaper by more than threshold%
    alerts = df[df["difference_percent"] < -threshold_percent]
    alerts = alerts.sort_values("difference_percent")
    
    return alerts


def suggest_price_adjustments():
    """Suggest price adjustments based on competitor prices"""
    df = load_price_monitoring()
    
    if df.empty:
        return pd.DataFrame()
    
    # Group by product to get latest competitor prices
    latest_prices = df.sort_values("date_recorded").groupby("product_name").last().reset_index()
    
    suggestions = []
    for _, row in latest_prices.iterrows():
        if row["difference_percent"] < -15:  # Competitor 15% cheaper
            suggestions.append({
                "product": row["product_name"],
                "current_price": row["our_price"],
                "competitor_price": row["competitor_price"],
                "suggested_price": row["competitor_price"] + (row["competitor_price"] * 0.05),  # 5% above competitor
                "reason": f"Competitor is {abs(row['difference_percent']):.1f}% cheaper"
            })
        elif row["difference_percent"] > 20:  # We are 20% more expensive than competitor
            suggestions.append({
                "product": row["product_name"],
                "current_price": row["our_price"],
                "competitor_price": row["competitor_price"],
                "suggested_price": row["competitor_price"] * 0.95,  # 5% below competitor
                "reason": f"We are {row['difference_percent']:.1f}% more expensive than competitor"
            })
    
    return pd.DataFrame(suggestions)


# ==============================
# MAIN DASHBOARD
# ==============================
def competitor_price_monitoring_dashboard():
    """Competitor Price Monitoring Dashboard"""
    
    st.title("🏪 Competitor Price Monitoring")
    st.caption("Track competitor prices, analyze market trends, and optimize pricing strategy")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access price monitoring.")
        return
    
    init_price_monitoring_files()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Price Dashboard",
        "➕ Record Price Comparison",
        "🏢 Manage Competitors",
        "📈 Price Trends",
        "💡 Price Recommendations"
    ])
    
    # ==============================
    # TAB 1: PRICE DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## 📊 Price Monitoring Dashboard")
        
        analysis = get_price_analysis()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📊 Total Comparisons", analysis["total_comparisons"])
        with col2:
            avg_diff = analysis["avg_price_difference"]
            st.metric("💰 Avg Price Difference", f"${avg_diff:.2f}", 
                     delta="Higher" if avg_diff > 0 else "Lower")
        with col3:
            st.metric("🟢 Products We're Cheaper", analysis["products_cheaper"])
        with col4:
            st.metric("🔴 Products Competitor Cheaper", analysis["products_expensive"])
        
        st.markdown("---")
        
        # Best opportunities
        if not analysis["best_opportunities"].empty:
            st.markdown("### 🎯 Best Pricing Opportunities")
            st.dataframe(
                analysis["best_opportunities"],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "price_difference": st.column_config.NumberColumn("Difference", format="$%.2f")
                }
            )
        else:
            st.info("No price comparison data available")
        
        # Price alerts
        st.markdown("### ⚠️ Price Alerts")
        alerts = get_price_alert_products(15)
        
        if not alerts.empty:
            st.warning(f"⚠️ {len(alerts)} products where competitors are significantly cheaper!")
            st.dataframe(
                alerts[["product_name", "competitor_name", "our_price", "competitor_price", "difference_percent"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "difference_percent": st.column_config.NumberColumn("Difference %", format="%.1f%%")
                }
            )
        else:
            st.success("✅ No critical price alerts")
    
    # ==============================
    # TAB 2: RECORD PRICE COMPARISON
    # ==============================
    with tab2:
        st.markdown("## ➕ Record Price Comparison")
        
        from backend.core.database import load_products
        
        products_df = load_products()
        competitors_df = load_competitors()
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Product selection
            if not products_df.empty:
                product_list = products_df["name"].tolist()
                selected_product = st.selectbox("Select Product", product_list)
                
                if selected_product:
                    product_data = products_df[products_df["name"] == selected_product].iloc[0]
                    product_barcode = product_data.get("barcode", "")
                    our_price = float(product_data.get("price", 0))
                    
                    st.info(f"💰 Our Current Price: **${our_price:.2f}**")
                else:
                    product_barcode = ""
                    our_price = 0
            else:
                st.warning("No products found. Please add products first.")
                selected_product = None
                product_barcode = ""
                our_price = 0
        
        with col2:
            # Competitor selection
            if not competitors_df.empty:
                competitor_list = competitors_df["name"].tolist()
                selected_competitor = st.selectbox("Select Competitor", competitor_list)
                
                if selected_competitor:
                    competitor_data = competitors_df[competitors_df["name"] == selected_competitor].iloc[0]
                    competitor_id = competitor_data.get("competitor_id", "")
                else:
                    competitor_id = ""
            else:
                st.warning("No competitors added. Please add competitors first.")
                selected_competitor = None
                competitor_id = ""
        
        if selected_product and selected_competitor:
            competitor_price = st.number_input("Competitor Price ($)", min_value=0.0, step=0.5, value=0.0)
            notes = st.text_area("Notes", placeholder="Additional information about this price comparison")
            
            if st.button("💾 Save Price Comparison", type="primary", use_container_width=True):
                if competitor_price > 0:
                    record_id = record_price_comparison(
                        product_name=selected_product,
                        product_barcode=product_barcode,
                        competitor_id=competitor_id,
                        competitor_name=selected_competitor,
                        our_price=our_price,
                        competitor_price=competitor_price,
                        notes=notes,
                        recorded_by=st.session_state.get("username", "system")
                    )
                    st.success(f"✅ Price comparison saved! ID: {record_id}")
                    show_confetti()
                    st.rerun()
                else:
                    st.error("Please enter competitor price")
    
    # ==============================
    # TAB 3: MANAGE COMPETITORS
    # ==============================
    with tab3:
        st.markdown("## 🏢 Manage Competitors")
        
        # Add new competitor
        with st.expander("➕ Add New Competitor", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                comp_name = st.text_input("Competitor Name", placeholder="e.g., Pick n Pay")
                comp_website = st.text_input("Website", placeholder="www.example.com")
                comp_location = st.text_input("Location", placeholder="Harare, Zimbabwe")
            
            with col2:
                comp_rating = st.slider("Rating (1-5)", 1.0, 5.0, 3.0, 0.5)
                comp_notes = st.text_area("Notes", placeholder="Additional information")
            
            if st.button("➕ Add Competitor", use_container_width=True):
                if comp_name:
                    comp_id = add_competitor(
                        name=comp_name,
                        website=comp_website,
                        location=comp_location,
                        rating=comp_rating,
                        notes=comp_notes,
                        added_by=st.session_state.get("username", "system")
                    )
                    st.success(f"✅ Competitor added! ID: {comp_id}")
                    show_toast("Competitor added successfully!", "success")
                    st.rerun()
                else:
                    st.error("Please enter competitor name")
        
        # List competitors
        st.markdown("### 📋 Competitors List")
        
        competitors_df = load_competitors()
        
        if not competitors_df.empty:
            st.dataframe(
                competitors_df[["competitor_id", "name", "location", "rating", "notes"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No competitors added yet")
    
    # ==============================
    # TAB 4: PRICE TRENDS
    # ==============================
    with tab4:
        st.markdown("## 📈 Price Trends Analysis")
        
        from backend.core.database import load_products
        
        products_df = load_products()
        
        if not products_df.empty:
            product_list = ["All"] + products_df["name"].tolist()
            selected_trend_product = st.selectbox("Select Product", product_list)
            
            if selected_trend_product != "All":
                trends_df = get_price_trends(selected_trend_product)
            else:
                trends_df = get_price_trends()
            
            if not trends_df.empty:
                # Price comparison chart
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=trends_df["date_recorded"],
                    y=trends_df["our_price"],
                    mode='lines+markers',
                    name='Our Price',
                    line=dict(color='#2ECC71', width=2)
                ))
                
                fig.add_trace(go.Scatter(
                    x=trends_df["date_recorded"],
                    y=trends_df["competitor_price"],
                    mode='lines+markers',
                    name='Competitor Price',
                    line=dict(color='#E74C3C', width=2)
                ))
                
                fig.update_layout(
                    title="Price Comparison Trend",
                    xaxis_title="Date",
                    yaxis_title="Price ($)",
                    height=400,
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Price difference over time
                fig_diff = px.area(
                    trends_df,
                    x="date_recorded",
                    y="price_difference",
                    title="Price Difference Over Time",
                    labels={"price_difference": "Difference ($)", "date_recorded": "Date"},
                    color_discrete_sequence=["#3498DB"]
                )
                fig_diff.add_hline(y=0, line_dash="dash", line_color="red")
                st.plotly_chart(fig_diff, use_container_width=True)
                
                # Data table
                st.dataframe(
                    trends_df[["date_recorded", "competitor_name", "our_price", "competitor_price", "price_difference", "difference_percent"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "date_recorded": st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD HH:mm"),
                        "difference_percent": st.column_config.NumberColumn("Difference %", format="%.1f%%")
                    }
                )
            else:
                st.info("No price trend data available for this product")
        else:
            st.info("No products available")
    
    # ==============================
    # TAB 5: PRICE RECOMMENDATIONS
    # ==============================
    with tab5:
        st.markdown("## 💡 AI-Powered Price Recommendations")
        st.caption("Smart pricing suggestions based on competitor analysis and market trends")
        
        suggestions = suggest_price_adjustments()
        
        if not suggestions.empty:
            st.markdown("### 📊 Recommended Price Adjustments")
            
            for _, suggestion in suggestions.iterrows():
                with st.container():
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    with col1:
                        st.markdown(f"**{suggestion['product']}**")
                        st.caption(suggestion['reason'])
                    with col2:
                        st.metric("Current Price", f"${suggestion['current_price']:.2f}")
                    with col3:
                        st.metric("Competitor Price", f"${suggestion['competitor_price']:.2f}")
                    with col4:
                        st.metric("Suggested Price", f"${suggestion['suggested_price']:.2f}")
                    st.markdown("---")
            
            # Export recommendations
            csv = suggestions.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Price Recommendations (CSV)",
                data=csv,
                file_name=f"price_recommendations_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No price recommendations available. Add more price comparisons to get suggestions.")


if __name__ == "__main__":
    competitor_price_monitoring_dashboard()