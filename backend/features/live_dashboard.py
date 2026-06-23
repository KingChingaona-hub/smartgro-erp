import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from backend.core.db_adapter import load_sales, load_products, load_purchases

# ==============================
# LIVE DASHBOARD WITH AUTO-REFRESH
# ==============================

def get_live_metrics():
    """Get current live metrics - FIXED for proper accumulation"""
    
    sales_df = load_sales()
    products_df = load_products()
    purchases_df = load_purchases()
    
    # Get today's date
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")
    
    # Initialize metrics with defaults
    metrics = {
        "total_today": 0,
        "transactions_today": 0,
        "items_today": 0,
        "last_hour_amount": 0,
        "out_of_stock": 0,
        "low_stock": 0,
        "pending_purchases": 0,
        "current_time": datetime.now().strftime("%H:%M:%S"),
        "current_date": today_str,
        "total_all_time": 0,
        "total_products": 0
    }
    
    # Process sales data
    if not sales_df.empty:
        # Ensure date column exists and is properly formatted
        date_col = None
        for col in ["sale_date", "date", "transaction_date", "created_at"]:
            if col in sales_df.columns:
                date_col = col
                break
        
        if date_col:
            # Convert to datetime
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            
            # Filter out invalid dates
            sales_df = sales_df.dropna(subset=[date_col])
            
            # Get today's sales
            today_mask = sales_df[date_col].dt.date == today
            today_sales = sales_df[today_mask]
            
            # Find total column
            total_col = None
            for col in ["final_total", "total", "amount", "sale_amount"]:
                if col in sales_df.columns:
                    total_col = col
                    break
            
            # Find items column
            items_col = None
            for col in ["items", "quantity", "qty", "item_count"]:
                if col in sales_df.columns:
                    items_col = col
                    break
            
            # Find receipt column
            receipt_col = None
            for col in ["receipt_no", "receipt", "transaction_id", "order_id"]:
                if col in sales_df.columns:
                    receipt_col = col
                    break
            
            # Calculate today's metrics
            if total_col and not today_sales.empty:
                metrics["total_today"] = float(today_sales[total_col].sum())
            
            if receipt_col:
                metrics["transactions_today"] = today_sales[receipt_col].nunique() if not today_sales.empty else 0
            else:
                metrics["transactions_today"] = len(today_sales)
            
            if items_col:
                metrics["items_today"] = int(today_sales[items_col].sum()) if not today_sales.empty else 0
            
            # Calculate all-time total
            if total_col:
                metrics["total_all_time"] = float(sales_df[total_col].sum())
            
            # Calculate last hour sales
            one_hour_ago = datetime.now() - timedelta(hours=1)
            last_hour_mask = sales_df[date_col] >= one_hour_ago
            last_hour_sales = sales_df[last_hour_mask]
            if total_col and not last_hour_sales.empty:
                metrics["last_hour_amount"] = float(last_hour_sales[total_col].sum())
    
    # Process products data
    if not products_df.empty:
        metrics["total_products"] = len(products_df)
        
        # Find stock and reorder level columns
        stock_col = None
        reorder_col = None
        
        for col in ["stock", "quantity", "inventory", "current_stock"]:
            if col in products_df.columns:
                stock_col = col
                break
        
        for col in ["reorder_level", "min_stock", "threshold", "reorder_point"]:
            if col in products_df.columns:
                reorder_col = col
                break
        
        if stock_col:
            # Ensure numeric
            products_df[stock_col] = pd.to_numeric(products_df[stock_col], errors="coerce").fillna(0)
            
            metrics["out_of_stock"] = len(products_df[products_df[stock_col] == 0])
            
            if reorder_col:
                products_df[reorder_col] = pd.to_numeric(products_df[reorder_col], errors="coerce").fillna(0)
                metrics["low_stock"] = len(
                    products_df[
                        (products_df[stock_col] > 0) & 
                        (products_df[stock_col] <= products_df[reorder_col])
                    ]
                )
    
    # Process purchases data
    if not purchases_df.empty:
        if "status" in purchases_df.columns:
            metrics["pending_purchases"] = len(
                purchases_df[purchases_df["status"].str.upper().isin(["PENDING", "ORDERED", "PENDING APPROVAL"])]
            )
    
    return metrics


def get_hourly_sales():
    """Get hourly sales for today's heatmap - FIXED"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return pd.DataFrame()
    
    today = datetime.now().date()
    
    # Find date column
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if not date_col:
        return pd.DataFrame()
    
    # Convert to datetime
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    # Filter today
    today_sales = sales_df[sales_df[date_col].dt.date == today]
    
    if today_sales.empty:
        return pd.DataFrame()
    
    # Find total column
    total_col = None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    if not total_col:
        return pd.DataFrame()
    
    # Extract hour from datetime
    today_sales["hour"] = today_sales[date_col].dt.hour
    
    # Group by hour
    hourly = today_sales.groupby("hour")[total_col].sum().reset_index()
    hourly.columns = ["hour", "total"]
    hourly = hourly.sort_values("hour")
    
    # Ensure all hours 0-23 are present
    all_hours = pd.DataFrame({"hour": range(24)})
    hourly = all_hours.merge(hourly, on="hour", how="left").fillna(0)
    
    return hourly


def get_top_products_live():
    """Get top selling products today - FIXED"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return pd.DataFrame()
    
    today = datetime.now().date()
    
    # Find date column
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if not date_col:
        return pd.DataFrame()
    
    # Find product name column
    product_col = None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in sales_df.columns:
            product_col = col
            break
    
    if not product_col:
        return pd.DataFrame()
    
    # Find items/quantity column
    items_col = None
    for col in ["items", "quantity", "qty", "item_count"]:
        if col in sales_df.columns:
            items_col = col
            break
    
    if not items_col:
        # Use count if no items column
        items_col = product_col
        use_count = True
    else:
        use_count = False
    
    # Convert to datetime
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    # Filter today
    today_sales = sales_df[sales_df[date_col].dt.date == today]
    
    if today_sales.empty:
        return pd.DataFrame()
    
    # Group by product
    if use_count:
        top_products = today_sales.groupby(product_col).size().nlargest(5).reset_index()
        top_products.columns = ["name", "items"]
    else:
        top_products = today_sales.groupby(product_col)[items_col].sum().nlargest(5).reset_index()
        top_products.columns = ["name", "items"]
    
    return top_products


def get_recent_transactions():
    """Get most recent transactions - FIXED"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return pd.DataFrame()
    
    # Find date column
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if not date_col:
        return pd.DataFrame()
    
    # Convert to datetime
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    # Sort by date descending
    sales_df = sales_df.sort_values(date_col, ascending=False)
    
    # Get last 10 transactions (take more to ensure we have 5 unique)
    recent = sales_df.head(10)
    
    # Define columns to display
    display_cols = []
    col_mapping = {
        "receipt_no": "Receipt No",
        "receipt": "Receipt No",
        "transaction_id": "Receipt No",
        "customer": "Customer",
        "customer_name": "Customer",
        "total": "Amount",
        "final_total": "Amount",
        "amount": "Amount",
        "payment_method": "Payment",
        "payment_type": "Payment",
        "product_name": "Product",
        "name": "Product"
    }
    
    # Find available columns
    for db_col, display_name in col_mapping.items():
        if db_col in recent.columns and db_col not in [c for c, _ in display_cols]:
            display_cols.append((db_col, display_name))
    
    # Limit to 5 columns
    display_cols = display_cols[:5]
    
    if not display_cols:
        return pd.DataFrame()
    
    # Create result dataframe
    result = pd.DataFrame()
    for db_col, display_name in display_cols:
        result[display_name] = recent[db_col].head(5).values
    
    # Format amount as currency
    if "Amount" in result.columns:
        result["Amount"] = result["Amount"].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "$0.00")
    
    return result.head(5)


def get_sales_ticker():
    """Get recent sales for ticker - FIXED"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return []
    
    # Find date column
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if not date_col:
        return []
    
    # Find product column
    product_col = None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in sales_df.columns:
            product_col = col
            break
    
    if not product_col:
        return []
    
    # Find total column
    total_col = None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    if not total_col:
        return []
    
    # Convert to datetime
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    # Get last 15 sales for ticker
    last_sales = sales_df.sort_values(date_col, ascending=False).head(15)
    
    ticker_items = []
    for _, sale in last_sales.iterrows():
        product = sale.get(product_col, "Product")
        amount = sale.get(total_col, 0)
        ticker_items.append(f"🛒 {product} - ${float(amount):.2f}")
    
    return ticker_items


def live_dashboard():
    """Real-time Live Dashboard with auto-refresh - FIXED"""
    
    st.title("⚡ LIVE COMMAND CENTER")
    st.caption("Real-time business metrics - Auto-refreshes every 10 seconds")
    
    # Auto-refresh setup
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    # Auto-refresh placeholder
    refresh_placeholder = st.empty()
    
    # Check if we need to refresh (every 10 seconds)
    current_time = time.time()
    if current_time - st.session_state.last_refresh >= 10:
        st.session_state.last_refresh = current_time
        st.rerun()
    
    # Show countdown
    time_since = current_time - st.session_state.last_refresh
    remaining = max(0, 10 - int(time_since))
    refresh_placeholder.info(f"🔄 Auto-refreshing in {remaining} seconds...")
    
    # Get live metrics
    metrics = get_live_metrics()
    
    # ==============================
    # TOP METRICS ROW
    # ==============================
    st.markdown("## 📊 Live Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💰 Today's Sales",
            f"${metrics['total_today']:,.2f}",
            delta=f"+${metrics['last_hour_amount']:.0f} last hour",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "🛒 Transactions",
            f"{metrics['transactions_today']}",
            help="Number of sales today"
        )
    
    with col3:
        st.metric(
            "📦 Items Sold",
            f"{metrics['items_today']}",
            help="Total items sold today"
        )
    
    with col4:
        st.metric(
            "⏰ Last Updated",
            metrics['current_time'],
            help=f"Date: {metrics['current_date']}"
        )
    
    # Additional metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📊 All-Time Sales",
            f"${metrics.get('total_all_time', 0):,.2f}",
            help="Total sales all time"
        )
    
    with col2:
        st.metric(
            "📦 Total Products",
            f"{metrics.get('total_products', 0)}",
            help="Total products in inventory"
        )
    
    with col3:
        st.metric(
            "🚫 Out of Stock",
            f"{metrics['out_of_stock']}",
            delta="⚠️" if metrics['out_of_stock'] > 0 else "✅",
            help="Products with zero stock"
        )
    
    with col4:
        st.metric(
            "⚠️ Low Stock",
            f"{metrics['low_stock']}",
            delta="⚠️" if metrics['low_stock'] > 0 else "✅",
            help="Products below reorder level"
        )
    
    st.markdown("---")
    
    # ==============================
    # ALERT ROW
    # ==============================
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if metrics['out_of_stock'] > 0:
            st.error(f"🚨 {metrics['out_of_stock']} products OUT OF STOCK!")
        else:
            st.success("✅ No out of stock items")
    
    with col2:
        if metrics['low_stock'] > 0:
            st.warning(f"⚠️ {metrics['low_stock']} products low on stock")
        else:
            st.success("✅ Stock levels healthy")
    
    with col3:
        if metrics['pending_purchases'] > 0:
            st.info(f"📋 {metrics['pending_purchases']} pending purchase orders")
        else:
            st.success("✅ No pending orders")
    
    st.markdown("---")
    
    # ==============================
    # TWO COLUMN LAYOUT
    # ==============================
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("## 🏆 Top Products Today")
        
        top_products = get_top_products_live()
        
        if not top_products.empty:
            fig = px.bar(
                top_products,
                x="items",
                y="name",
                orientation='h',
                title="Best Sellers Today",
                color="items",
                color_continuous_scale="Viridis",
                text="items"
            )
            fig.update_traces(texttemplate="%{text}", textposition="outside")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sales recorded today")
    
    with col2:
        st.markdown("## 📈 Hourly Sales")
        
        hourly_sales = get_hourly_sales()
        
        if not hourly_sales.empty:
            fig = px.line(
                hourly_sales,
                x="hour",
                y="total",
                title="Sales by Hour Today",
                markers=True,
                line_shape="spline"
            )
            fig.update_layout(
                height=350,
                xaxis_title="Hour of Day",
                yaxis_title="Sales Amount ($)"
            )
            fig.update_traces(fill="tozeroy", fillcolor="rgba(46, 204, 113, 0.2)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hourly data available")
    
    st.markdown("---")
    
    # ==============================
    # RECENT TRANSACTIONS
    # ==============================
    st.markdown("## 📜 Recent Transactions")
    
    recent = get_recent_transactions()
    
    if not recent.empty:
        st.dataframe(
            recent,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No recent transactions")
    
    st.markdown("---")
    
    # ==============================
    # QUICK ACTION BUTTONS
    # ==============================
    st.markdown("## ⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🛒 Go to POS", use_container_width=True):
            st.session_state.current_page = "POS"
            st.rerun()
    
    with col2:
        if st.button("📦 Check Stock", use_container_width=True):
            st.session_state.current_page = "Stock Dashboard"
            st.rerun()
    
    with col3:
        if st.button("📋 View Purchases", use_container_width=True):
            st.session_state.current_page = "Purchases"
            st.rerun()
    
    with col4:
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # ==============================
    # LIVE TICKER (Sales ticker)
    # ==============================
    st.markdown("---")
    st.markdown("## 📢 Live Sales Ticker")
    
    ticker_items = get_sales_ticker()
    
    if ticker_items:
        # Create scrolling marquee with HTML
        ticker_html = f"""
        <div style="background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 15px; border-radius: 10px; overflow: hidden; white-space: nowrap;">
            <marquee behavior="scroll" direction="left" scrollamount="4" style="color: white; font-size: 16px;">
                {'  &nbsp;&nbsp; ⭐  &nbsp;&nbsp; '.join(ticker_items)}
            </marquee>
        </div>
        """
        st.markdown(ticker_html, unsafe_allow_html=True)
    else:
        st.info("No recent sales to display")
    
    # ==============================
    # SALES GAUGE (Daily Target)
    # ==============================
    st.markdown("---")
    st.markdown("## 🎯 Daily Sales Target")
    
    # Set daily target (can be configured)
    daily_target = 5000
    
    progress_percentage = min(100, (metrics['total_today'] / daily_target) * 100)
    
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=metrics['total_today'],
        title={"text": f"Target: ${daily_target:,.2f}"},
        delta={"reference": daily_target},
        gauge={
            "axis": {"range": [0, daily_target * 1.2]},
            "bar": {"color": "darkgreen" if progress_percentage >= 100 else "orange"},
            "steps": [
                {"range": [0, daily_target * 0.5], "color": "lightgray"},
                {"range": [daily_target * 0.5, daily_target], "color": "gray"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": daily_target
            }
        }
    ))
    fig_gauge.update_layout(height=250)
    st.plotly_chart(fig_gauge, use_container_width=True)
    
    # Progress bar
    st.progress(min(1.0, progress_percentage / 100))
    st.caption(f"Progress: {min(100, progress_percentage):.1f}% of daily target")
    
    # ==============================
    # MANUAL REFRESH NOTE
    # ==============================
    st.caption("💡 This dashboard auto-refreshes every 10 seconds. Data updates automatically as new sales come in.")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    live_dashboard()