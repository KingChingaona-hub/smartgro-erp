import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from backend.core.db_adapter import load_sales, load_products, load_purchases

# ==============================
# HELPER FUNCTIONS
# ==============================

def find_column(df, possible_names, default=None):
    """Find the first column that matches any of the possible names"""
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return default


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


# ==============================
# LIVE DASHBOARD WITH AUTO-REFRESH
# ==============================

def get_live_metrics():
    """Get current live metrics - FIXED"""
    
    try:
        sales_df = load_sales()
        products_df = load_products()
        purchases_df = load_purchases()
    except Exception as e:
        print(f"Error loading data: {e}")
        return get_default_metrics()
    
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
        try:
            # Find date column
            date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
            
            if date_col:
                # Convert to datetime
                sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                sales_df = sales_df.dropna(subset=[date_col])
                
                if not sales_df.empty:
                    # Get today's sales
                    today_mask = sales_df[date_col].dt.date == today
                    today_sales = sales_df[today_mask]
                    
                    # Find total column
                    total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
                    
                    # Find items column
                    items_col = find_column(sales_df, ["items", "quantity", "qty", "item_count"])
                    
                    # Find receipt column
                    receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
                    
                    # Calculate today's metrics
                    if total_col and not today_sales.empty:
                        metrics["total_today"] = safe_float(today_sales[total_col].sum())
                    
                    if receipt_col:
                        metrics["transactions_today"] = today_sales[receipt_col].nunique() if not today_sales.empty else 0
                    else:
                        metrics["transactions_today"] = len(today_sales)
                    
                    if items_col:
                        metrics["items_today"] = safe_int(today_sales[items_col].sum()) if not today_sales.empty else 0
                    
                    # Calculate all-time total
                    if total_col:
                        metrics["total_all_time"] = safe_float(sales_df[total_col].sum())
                    
                    # Calculate last hour sales
                    one_hour_ago = datetime.now() - timedelta(hours=1)
                    last_hour_mask = sales_df[date_col] >= one_hour_ago
                    last_hour_sales = sales_df[last_hour_mask]
                    if total_col and not last_hour_sales.empty:
                        metrics["last_hour_amount"] = safe_float(last_hour_sales[total_col].sum())
        except Exception as e:
            print(f"Error processing sales: {e}")
    
    # Process products data
    if not products_df.empty:
        try:
            metrics["total_products"] = len(products_df)
            
            # Find stock and reorder level columns
            stock_col = find_column(products_df, ["stock", "quantity", "inventory", "current_stock"])
            reorder_col = find_column(products_df, ["reorder_level", "min_stock", "threshold", "reorder_point"])
            
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
        except Exception as e:
            print(f"Error processing products: {e}")
    
    # Process purchases data
    if not purchases_df.empty and "status" in purchases_df.columns:
        try:
            metrics["pending_purchases"] = len(
                purchases_df[purchases_df["status"].str.upper().isin(["PENDING", "ORDERED", "PENDING APPROVAL"])]
            )
        except Exception as e:
            print(f"Error processing purchases: {e}")
    
    return metrics


def get_default_metrics():
    """Return default metrics when data loading fails"""
    today = datetime.now().date()
    return {
        "total_today": 0,
        "transactions_today": 0,
        "items_today": 0,
        "last_hour_amount": 0,
        "out_of_stock": 0,
        "low_stock": 0,
        "pending_purchases": 0,
        "current_time": datetime.now().strftime("%H:%M:%S"),
        "current_date": today.strftime("%Y-%m-%d"),
        "total_all_time": 0,
        "total_products": 0
    }


def get_hourly_sales():
    """Get hourly sales for today's heatmap - FIXED"""
    
    try:
        sales_df = load_sales()
        
        if sales_df.empty:
            return pd.DataFrame()
        
        today = datetime.now().date()
        
        # Find date column
        date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
        
        if not date_col:
            return pd.DataFrame()
        
        # Convert to datetime
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Filter today
        today_sales = sales_df[sales_df[date_col].dt.date == today]
        
        if today_sales.empty:
            return pd.DataFrame()
        
        # Find total column
        total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
        
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
    except Exception as e:
        print(f"Error getting hourly sales: {e}")
        return pd.DataFrame()


def get_top_products_live():
    """Get top selling products today - FIXED"""
    
    try:
        sales_df = load_sales()
        
        if sales_df.empty:
            return pd.DataFrame()
        
        today = datetime.now().date()
        
        # Find date column
        date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
        
        if not date_col:
            return pd.DataFrame()
        
        # Find product name column
        product_col = find_column(sales_df, ["name", "product_name", "Product", "item_name"])
        
        if not product_col:
            return pd.DataFrame()
        
        # Find items/quantity column
        items_col = find_column(sales_df, ["items", "quantity", "qty", "item_count"])
        
        use_count = False
        if not items_col:
            items_col = product_col
            use_count = True
        
        # Convert to datetime
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        if sales_df.empty:
            return pd.DataFrame()
        
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
    except Exception as e:
        print(f"Error getting top products: {e}")
        return pd.DataFrame()


def get_recent_transactions():
    """Get most recent transactions - FIXED"""
    
    try:
        sales_df = load_sales()
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Find date column
        date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
        
        if not date_col:
            return pd.DataFrame()
        
        # Convert to datetime
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Sort by date descending
        sales_df = sales_df.sort_values(date_col, ascending=False)
        
        # Get last 10 transactions
        recent = sales_df.head(10)
        
        # Define columns to display
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
        display_cols = []
        used_columns = set()
        for db_col, display_name in col_mapping.items():
            if db_col in recent.columns and db_col not in used_columns:
                display_cols.append((db_col, display_name))
                used_columns.add(db_col)
                if len(display_cols) >= 5:
                    break
        
        if not display_cols:
            return pd.DataFrame()
        
        # Create result dataframe
        result = pd.DataFrame()
        for db_col, display_name in display_cols:
            result[display_name] = recent[db_col].head(5).values
        
        # Format amount as currency
        if "Amount" in result.columns:
            result["Amount"] = result["Amount"].apply(
                lambda x: f"${safe_float(x):.2f}" if pd.notna(x) else "$0.00"
            )
        
        return result.head(5)
    except Exception as e:
        print(f"Error getting recent transactions: {e}")
        return pd.DataFrame()


def get_sales_ticker():
    """Get recent sales for ticker - FIXED"""
    
    try:
        sales_df = load_sales()
        
        if sales_df.empty:
            return []
        
        # Find date column
        date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
        
        if not date_col:
            return []
        
        # Find product column
        product_col = find_column(sales_df, ["name", "product_name", "Product", "item_name"])
        
        if not product_col:
            return []
        
        # Find total column
        total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
        
        if not total_col:
            return []
        
        # Convert to datetime
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        if sales_df.empty:
            return []
        
        # Get last 15 sales for ticker
        last_sales = sales_df.sort_values(date_col, ascending=False).head(15)
        
        ticker_items = []
        for _, sale in last_sales.iterrows():
            product = str(sale.get(product_col, "Product"))[:30]  # Truncate long names
            amount = safe_float(sale.get(total_col, 0))
            ticker_items.append(f"🛒 {product} - ${amount:.2f}")
        
        return ticker_items
    except Exception as e:
        print(f"Error getting sales ticker: {e}")
        return []


def live_dashboard():
    """Real-time Live Dashboard with auto-refresh - FIXED"""
    
    st.title("⚡ LIVE COMMAND CENTER")
    st.caption("Real-time business metrics - Auto-refreshes every 10 seconds")
    
    # Auto-refresh setup
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    # Auto-refresh placeholder
    refresh_placeholder = st.empty()
    
    # Check if we need to refresh (every 10 seconds) - FIXED: Only rerun if not already in a rerun
    current_time = time.time()
    time_since = current_time - st.session_state.last_refresh
    
    if time_since >= 10 and not st.session_state.get("_is_rerunning", False):
        st.session_state.last_refresh = current_time
        st.session_state._is_rerunning = True
        st.rerun()
    
    # Reset rerun flag after render
    if st.session_state.get("_is_rerunning", False):
        st.session_state._is_rerunning = False
    
    # Show countdown
    remaining = max(0, 10 - int(time_since))
    refresh_placeholder.info(f"Auto-refreshing in {remaining} seconds...")
    
    # Get live metrics
    metrics = get_live_metrics()
    
    # ==============================
    # TOP METRICS ROW
    # ==============================
    st.markdown("## Live Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Today's Sales",
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
            "Items Sold",
            f"{metrics['items_today']}",
            help="Total items sold today"
        )
    
    with col4:
        st.metric(
            "Last Updated",
            metrics['current_time'],
            help=f"Date: {metrics['current_date']}"
        )
    
    # Additional metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "All-Time Sales",
            f"${metrics.get('total_all_time', 0):,.2f}",
            help="Total sales all time"
        )
    
    with col2:
        st.metric(
            "Total Products",
            f"{metrics.get('total_products', 0)}",
            help="Total products in inventory"
        )
    
    with col3:
        st.metric(
            "Out of Stock",
            f"{metrics['out_of_stock']}",
            delta="⚠️" if metrics['out_of_stock'] > 0 else "✅",
            help="Products with zero stock"
        )
    
    with col4:
        st.metric(
            "Low Stock",
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
            st.error(f"{metrics['out_of_stock']} products OUT OF STOCK!")
        else:
            st.success("No out of stock items")
    
    with col2:
        if metrics['low_stock'] > 0:
            st.warning(f"{metrics['low_stock']} products low on stock")
        else:
            st.success("Stock levels healthy")
    
    with col3:
        if metrics['pending_purchases'] > 0:
            st.info(f"{metrics['pending_purchases']} pending purchase orders")
        else:
            st.success("No pending orders")
    
    st.markdown("---")
    
    # ==============================
    # TWO COLUMN LAYOUT
    # ==============================
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("## Top Products Today")
        
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
        st.markdown("## Hourly Sales")
        
        hourly_sales = get_hourly_sales()
        
        if not hourly_sales.empty and hourly_sales["total"].sum() > 0:
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
    st.markdown("## Recent Transactions")
    
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
    st.markdown("## Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🛒 Go to POS", use_container_width=True):
            st.session_state.current_page = "POS"
            st.rerun()
    
    with col2:
        if st.button("Check Stock", use_container_width=True):
            st.session_state.current_page = "Stock Dashboard"
            st.rerun()
    
    with col3:
        if st.button("View Purchases", use_container_width=True):
            st.session_state.current_page = "Purchases"
            st.rerun()
    
    with col4:
        if st.button("Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # ==============================
    # LIVE TICKER (Sales ticker) - FIXED (no marquee)
    # ==============================
    st.markdown("---")
    st.markdown("## Live Sales Ticker")
    
    ticker_items = get_sales_ticker()
    
    if ticker_items:
        # Create scrolling ticker with CSS animation (modern approach)
        ticker_html = f"""
        <div style="background: linear-gradient(90deg, #1a1a2e, #16213e); padding: 15px; border-radius: 10px; overflow: hidden; white-space: nowrap; position: relative;">
            <div style="display: inline-block; animation: scrollTicker 20s linear infinite; white-space: nowrap;">
                {'  &nbsp;&nbsp; ⭐  &nbsp;&nbsp; '.join(ticker_items)}
            </div>
        </div>
        <style>
            @keyframes scrollTicker {{
                0% {{ transform: translateX(100%); }}
                100% {{ transform: translateX(-100%); }}
            }}
        </style>
        """
        st.markdown(ticker_html, unsafe_allow_html=True)
    else:
        st.info("No recent sales to display")
    
    # ==============================
    # SALES GAUGE (Daily Target)
    # ==============================
    st.markdown("---")
    st.markdown("## Daily Sales Target")
    
    # Set daily target (can be configured)
    daily_target = 5000
    
    if daily_target > 0:
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
    else:
        st.info("Daily target not configured")
    
    # ==============================
    # MANUAL REFRESH NOTE
    # ==============================
    st.caption("💡 This dashboard auto-refreshes every 10 seconds. Data updates automatically as new sales come in.")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    live_dashboard()