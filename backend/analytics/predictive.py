import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from decimal import Decimal
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import load_sales, load_products

# ==============================
# HELPER FUNCTIONS
# ==============================

def convert_decimal_to_float(df):
    """Convert all Decimal columns to float for compatibility"""
    if df is None or df.empty:
        return df
    
    for col in df.columns:
        if df[col].dtype == object:
            # Check if column contains Decimal values
            sample = df[col].iloc[0] if len(df) > 0 else None
            if sample is not None and isinstance(sample, Decimal):
                df[col] = df[col].astype(float)
            elif sample is not None and isinstance(sample, (int, float)):
                pass  # Already numeric
    return df


def get_sales_data():
    """Load and prepare sales data with proper column handling"""
    sales_df = load_sales()
    
    if sales_df.empty:
        return pd.DataFrame()
    
    # Convert Decimal columns to float
    sales_df = convert_decimal_to_float(sales_df)
    
    # Find date column
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col is None:
        return pd.DataFrame()
    
    # Convert date column
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    # Rename to standard 'date' for consistency
    if date_col != "date":
        sales_df["date"] = sales_df[date_col]
    
    # Find total column
    total_col = None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    if total_col and total_col != "total":
        sales_df["total"] = pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0)
    elif not total_col:
        sales_df["total"] = 0
    
    # Ensure total is float
    sales_df["total"] = sales_df["total"].astype(float)
    
    # Find profit column
    profit_col = None
    for col in ["profit", "profit_margin", "gross_profit"]:
        if col in sales_df.columns:
            profit_col = col
            break
    
    if profit_col and profit_col != "profit":
        sales_df["profit"] = pd.to_numeric(sales_df[profit_col], errors="coerce").fillna(0)
    elif not profit_col:
        sales_df["profit"] = 0
    
    # Ensure profit is float
    sales_df["profit"] = sales_df["profit"].astype(float)
    
    # Find items column
    items_col = None
    for col in ["items", "quantity", "qty", "item_count"]:
        if col in sales_df.columns:
            items_col = col
            break
    
    if items_col and items_col != "items":
        sales_df["items"] = pd.to_numeric(sales_df[items_col], errors="coerce").fillna(1)
    elif not items_col:
        sales_df["items"] = 1
    
    # Ensure items is int
    sales_df["items"] = sales_df["items"].astype(int)
    
    # Find product name column
    product_col = None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in sales_df.columns:
            product_col = col
            break
    
    if product_col and product_col != "name":
        sales_df["name"] = sales_df[product_col].fillna("Unknown")
    elif not product_col:
        sales_df["name"] = "Unknown"
    
    # Ensure name is string
    sales_df["name"] = sales_df["name"].astype(str)
    
    # Find receipt column
    receipt_col = None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in sales_df.columns:
            receipt_col = col
            break
    
    if receipt_col and receipt_col != "receipt_no":
        sales_df["receipt_no"] = sales_df[receipt_col].fillna("")
    elif not receipt_col:
        sales_df["receipt_no"] = sales_df.index.astype(str)
    
    return sales_df


def get_products_data():
    """Load and prepare products data"""
    products_df = load_products()
    
    if products_df.empty:
        return pd.DataFrame()
    
    # Convert Decimal columns to float
    products_df = convert_decimal_to_float(products_df)
    
    # Find product name column
    product_col = None
    for col in ["name", "product_name", "Product"]:
        if col in products_df.columns:
            product_col = col
            break
    
    if product_col and product_col != "name":
        products_df["name"] = products_df[product_col].fillna("Unknown")
    
    # Find price column
    price_col = None
    for col in ["price", "selling_price", "unit_price"]:
        if col in products_df.columns:
            price_col = col
            break
    
    if price_col and price_col != "price":
        products_df["price"] = pd.to_numeric(products_df[price_col], errors="coerce").fillna(0)
    
    if "price" not in products_df.columns:
        products_df["price"] = 0
    
    products_df["price"] = products_df["price"].astype(float)
    
    # Find cost column
    cost_col = None
    for col in ["cost", "cost_price", "purchase_price"]:
        if col in products_df.columns:
            cost_col = col
            break
    
    if cost_col and cost_col != "cost":
        products_df["cost"] = pd.to_numeric(products_df[cost_col], errors="coerce").fillna(0)
    
    if "cost" not in products_df.columns:
        products_df["cost"] = 0
    
    products_df["cost"] = products_df["cost"].astype(float)
    
    # Find stock column
    stock_col = None
    for col in ["stock", "quantity", "inventory", "current_stock"]:
        if col in products_df.columns:
            stock_col = col
            break
    
    if stock_col and stock_col != "stock":
        products_df["stock"] = pd.to_numeric(products_df[stock_col], errors="coerce").fillna(0)
    
    if "stock" not in products_df.columns:
        products_df["stock"] = 0
    
    products_df["stock"] = products_df["stock"].astype(int)
    
    return products_df


def prepare_time_series_data(sales_df, product_name=None):
    """Prepare time series data for forecasting"""
    
    if sales_df.empty:
        return None
    
    # Filter by product if specified
    if product_name and product_name != "All Products" and product_name != "All":
        df = sales_df[sales_df["name"] == product_name].copy()
        if df.empty:
            return None
    else:
        df = sales_df.copy()
    
    # Aggregate by date
    daily_sales = df.groupby(df["date"].dt.date)["total"].sum().reset_index()
    daily_sales.columns = ["date", "sales"]
    daily_sales["date"] = pd.to_datetime(daily_sales["date"])
    daily_sales = daily_sales.sort_values("date")
    
    # Add time features
    daily_sales["day_of_week"] = daily_sales["date"].dt.dayofweek
    daily_sales["month"] = daily_sales["date"].dt.month
    daily_sales["day_of_month"] = daily_sales["date"].dt.day
    daily_sales["week_of_year"] = daily_sales["date"].dt.isocalendar().week
    daily_sales["quarter"] = daily_sales["date"].dt.quarter
    daily_sales["is_weekend"] = (daily_sales["day_of_week"] >= 5).astype(int)
    daily_sales["days_since_start"] = (daily_sales["date"] - daily_sales["date"].min()).dt.days
    
    return daily_sales


def forecast_sales(daily_sales, days=30, model_type="Linear Regression"):
    """Generate sales forecast"""
    
    if daily_sales is None or len(daily_sales) < 7:
        return None
    
    # Prepare features
    X = daily_sales["days_since_start"].values.reshape(-1, 1)
    y = daily_sales["sales"].values
    
    # Train model
    if model_type == "Linear Regression":
        model = LinearRegression()
        model.fit(X, y)
    else:  # Random Forest
        # Use more features for Random Forest
        feature_cols = ["day_of_week", "month", "day_of_month", "week_of_year", "quarter", "is_weekend", "days_since_start"]
        X_rf = daily_sales[feature_cols].values
        model = RandomForestRegressor(n_estimators=100, random_state=42)
        model.fit(X_rf, y)
    
    # Predict future
    last_day = daily_sales["days_since_start"].max()
    last_date = daily_sales["date"].max()
    
    if model_type == "Linear Regression":
        future_days = np.arange(last_day + 1, last_day + days + 1).reshape(-1, 1)
        predictions = model.predict(future_days)
    else:
        # Random Forest predictions with future features
        feature_cols = ["day_of_week", "month", "day_of_month", "week_of_year", "quarter", "is_weekend", "days_since_start"]
        future_features = []
        for i in range(1, days + 1):
            future_date = last_date + timedelta(days=i)
            features = {
                "day_of_week": future_date.weekday(),
                "month": future_date.month,
                "day_of_month": future_date.day,
                "week_of_year": future_date.isocalendar().week,
                "quarter": (future_date.month - 1) // 3 + 1,
                "is_weekend": 1 if future_date.weekday() >= 5 else 0,
                "days_since_start": last_day + i
            }
            future_features.append([features[col] for col in feature_cols])
        predictions = model.predict(future_features)
    
    predictions = np.maximum(predictions, 0)  # No negative sales
    
    # Calculate confidence intervals (95%)
    y_pred = model.predict(X if model_type == "Linear Regression" else X_rf)
    residuals = y - y_pred
    std_residual = np.std(residuals)
    confidence_interval = 1.96 * std_residual
    
    # Generate forecast dates
    forecast_dates = [last_date + timedelta(days=i) for i in range(1, days + 1)]
    
    forecast = []
    for i, (date, pred) in enumerate(zip(forecast_dates, predictions)):
        forecast.append({
            "date": date.strftime("%Y-%m-%d"),
            "forecast_sales": float(round(pred, 2)),
            "lower_bound": float(round(max(0, pred - confidence_interval), 2)),
            "upper_bound": float(round(pred + confidence_interval, 2))
        })
    
    # Calculate metrics
    mae = float(mean_absolute_error(y, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y, y_pred)))
    r2 = float(r2_score(y, y_pred))
    
    return {
        "forecast": forecast,
        "total_forecast": float(round(sum(predictions), 2)),
        "avg_daily": float(round(np.mean(predictions), 2)),
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
        "confidence_interval": float(round(confidence_interval, 2)),
        "model_type": model_type,
        "trend": "increasing" if model.coef_[0] > 0 else "decreasing" if model_type == "Linear Regression" else "variable"
    }


def get_top_products(sales_df, n=10):
    """Get top N products by sales"""
    
    if sales_df.empty:
        return pd.DataFrame()
    
    top_products = sales_df.groupby("name").agg({
        "total": "sum",
        "profit": "sum",
        "items": "sum"
    }).reset_index()
    
    top_products = top_products.sort_values("total", ascending=False).head(n)
    top_products["total"] = top_products["total"].astype(float)
    top_products["profit"] = top_products["profit"].astype(float)
    top_products["items"] = top_products["items"].astype(int)
    
    return top_products


def get_product_trend(sales_df, product_name, days=30):
    """Get product sales trend"""
    
    if sales_df.empty:
        return pd.DataFrame()
    
    product_sales = sales_df[sales_df["name"] == product_name].copy()
    
    if product_sales.empty:
        return pd.DataFrame()
    
    # Get last N days
    cutoff_date = datetime.now() - timedelta(days=days)
    product_sales = product_sales[product_sales["date"] >= cutoff_date]
    
    if product_sales.empty:
        return pd.DataFrame()
    
    # Aggregate by date
    trend = product_sales.groupby(product_sales["date"].dt.date)["total"].sum().reset_index()
    trend.columns = ["date", "sales"]
    trend["date"] = pd.to_datetime(trend["date"])
    trend = trend.sort_values("date")
    
    # Add moving average
    if len(trend) >= 3:
        trend["ma_3"] = trend["sales"].rolling(window=3, min_periods=1).mean()
        trend["ma_7"] = trend["sales"].rolling(window=7, min_periods=1).mean()
    
    return trend


# ==============================
# PREDICTIVE ANALYTICS DASHBOARD
# ==============================

def predictive_analytics_dashboard():
    """Main predictive analytics dashboard"""
    
    st.title("🔮 Predictive Analytics Dashboard")
    st.caption("AI-powered sales forecasting and business intelligence")
    
    # Load data
    sales_df = get_sales_data()
    products_df = get_products_data()
    
    if sales_df.empty:
        st.warning("No sales data available for predictive analytics")
        return
    
    # ==============================
    # SIDEBAR FILTERS
    # ==============================
    st.sidebar.header("🔍 Filters")
    
    # Date filter
    min_date = sales_df["date"].min().date()
    max_date = sales_df["date"].max().date()
    
    date_range = st.sidebar.date_input(
        "Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    # Apply date filter
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        mask = (sales_df["date"].dt.date >= start_date) & (sales_df["date"].dt.date <= end_date)
        filtered_df = sales_df[mask].copy()
    else:
        filtered_df = sales_df.copy()
    
    if filtered_df.empty:
        st.warning("No data matches the selected filters")
        return
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Sales Forecast",
        "📊 Product Insights",
        "📉 Trend Analysis",
        "💡 Predictions & Recommendations"
    ])
    
    # ==============================
    # TAB 1: SALES FORECAST
    # ==============================
    with tab1:
        st.markdown("## 📈 Sales Forecast")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Product selection
            products = ["All Products"] + sorted(filtered_df["name"].unique().tolist())
            selected_product = st.selectbox("Select Product", products, key="forecast_product")
        
        with col2:
            forecast_days = st.slider("Forecast Days", 7, 90, 30, key="forecast_days")
            model_type = st.selectbox("Forecast Model", ["Linear Regression", "Random Forest"], key="model_type")
        
        if st.button("🔮 Generate Forecast", type="primary", use_container_width=True):
            with st.spinner("Training AI model and generating forecast..."):
                # Prepare data
                daily_sales = prepare_time_series_data(filtered_df, selected_product)
                
                if daily_sales is None or len(daily_sales) < 7:
                    st.error("Not enough historical data for this selection. Need at least 7 days of sales.")
                else:
                    # Generate forecast
                    forecast_result = forecast_sales(daily_sales, forecast_days, model_type)
                    
                    if forecast_result:
                        # Display metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("📊 Total Forecast", f"${forecast_result['total_forecast']:,.2f}")
                        with col2:
                            st.metric("📈 Avg Daily", f"${forecast_result['avg_daily']:.2f}")
                        with col3:
                            st.metric("🎯 Trend", forecast_result['trend'].capitalize())
                        with col4:
                            st.metric("📐 Confidence", f"±${forecast_result['confidence_interval']:.2f}")
                        
                        st.markdown("---")
                        
                        # Forecast chart
                        forecast_df = pd.DataFrame(forecast_result['forecast'])
                        
                        fig = go.Figure()
                        
                        # Actual sales (last 30 days)
                        actual_df = daily_sales.tail(30)
                        fig.add_trace(go.Scatter(
                            x=actual_df["date"],
                            y=actual_df["sales"],
                            mode="lines+markers",
                            name="Actual Sales",
                            line=dict(color="#3498db", width=2),
                            marker=dict(size=6)
                        ))
                        
                        # Forecast
                        fig.add_trace(go.Scatter(
                            x=forecast_df["date"],
                            y=forecast_df["forecast_sales"],
                            mode="lines+markers",
                            name="Forecast",
                            line=dict(color="#2ecc71", width=2, dash="dash"),
                            marker=dict(size=6)
                        ))
                        
                        # Confidence interval
                        fig.add_trace(go.Scatter(
                            x=forecast_df["date"],
                            y=forecast_df["upper_bound"],
                            mode="lines",
                            name="Upper Bound",
                            line=dict(color="rgba(46, 204, 113, 0.3)", width=0),
                            showlegend=False
                        ))
                        
                        fig.add_trace(go.Scatter(
                            x=forecast_df["date"],
                            y=forecast_df["lower_bound"],
                            mode="lines",
                            name="Lower Bound",
                            line=dict(color="rgba(46, 204, 113, 0.3)", width=0),
                            fill="tonexty",
                            fillcolor="rgba(46, 204, 113, 0.2)",
                            showlegend=False
                        ))
                        
                        fig.update_layout(
                            title=f"Sales Forecast - Next {forecast_days} Days",
                            xaxis_title="Date",
                            yaxis_title="Sales ($)",
                            height=450,
                            hovermode="x unified"
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Model metrics
                        with st.expander("📊 Model Performance Metrics"):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Mean Absolute Error (MAE)", f"${forecast_result['mae']:.2f}")
                            with col2:
                                st.metric("Root Mean Squared Error (RMSE)", f"${forecast_result['rmse']:.2f}")
                            with col3:
                                st.metric("R² Score", f"{forecast_result['r2']:.3f}")
                        
                        # Download forecast
                        csv = forecast_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Forecast (CSV)",
                            data=csv,
                            file_name=f"forecast_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.error("Forecast failed. Please try again.")
    
    # ==============================
    # TAB 2: PRODUCT INSIGHTS
    # ==============================
    with tab2:
        st.markdown("## 📊 Product Insights")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏆 Top Products")
            top_products = get_top_products(filtered_df, 10)
            
            if not top_products.empty:
                fig = px.bar(
                    top_products,
                    x="total",
                    y="name",
                    orientation='h',
                    title="Top 10 Products by Revenue",
                    color="total",
                    color_continuous_scale="Blues",
                    text="total"
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No product data available")
        
        with col2:
            st.markdown("### 📈 Product Performance")
            
            if not products_df.empty:
                # Show product performance table
                product_performance = filtered_df.groupby("name").agg({
                    "total": "sum",
                    "profit": "sum",
                    "items": "sum"
                }).reset_index()
                
                product_performance["total"] = product_performance["total"].astype(float)
                product_performance["profit"] = product_performance["profit"].astype(float)
                product_performance["items"] = product_performance["items"].astype(int)
                product_performance["margin"] = (product_performance["profit"] / product_performance["total"] * 100).fillna(0)
                
                # Merge with product data for stock info
                if not products_df.empty:
                    product_performance = product_performance.merge(
                        products_df[["name", "stock"]], 
                        on="name", 
                        how="left"
                    )
                else:
                    product_performance["stock"] = 0
                
                st.dataframe(
                    product_performance.head(10),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "name": "Product",
                        "total": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                        "profit": st.column_config.NumberColumn("Profit", format="$%.2f"),
                        "items": "Units Sold",
                        "margin": st.column_config.NumberColumn("Margin", format="%.1f%%"),
                        "stock": "Stock"
                    }
                )
            else:
                st.info("No performance data available")
        
        st.markdown("---")
        
        # Product search
        st.markdown("### 🔍 Product Lookup")
        search_product = st.selectbox(
            "Search for a product",
            options=sorted(filtered_df["name"].unique().tolist())
        )
        
        if search_product:
            product_data = filtered_df[filtered_df["name"] == search_product]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Total Revenue",
                    f"${product_data['total'].sum():,.2f}"
                )
            
            with col2:
                st.metric(
                    "Units Sold",
                    f"{product_data['items'].sum():,.0f}"
                )
            
            with col3:
                profit = product_data['profit'].sum()
                margin = (profit / product_data['total'].sum() * 100) if product_data['total'].sum() > 0 else 0
                st.metric(
                    "Profit Margin",
                    f"{margin:.1f}%"
                )
            
            # Product trend
            product_trend = get_product_trend(filtered_df, search_product, 30)
            
            if not product_trend.empty:
                fig = px.line(
                    product_trend,
                    x="date",
                    y=["sales", "ma_3", "ma_7"] if "ma_3" in product_trend.columns else ["sales"],
                    title=f"Sales Trend for {search_product}",
                    labels={"value": "Sales ($)", "date": "Date", "variable": "Metric"}
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
    
    # ==============================
    # TAB 3: TREND ANALYSIS
    # ==============================
    with tab3:
        st.markdown("## 📉 Trend Analysis")
        
        # Overall sales trend
        daily_total = filtered_df.groupby(filtered_df["date"].dt.date)["total"].sum().reset_index()
        daily_total.columns = ["date", "sales"]
        daily_total["date"] = pd.to_datetime(daily_total["date"])
        daily_total = daily_total.sort_values("date")
        
        if not daily_total.empty:
            # Add moving averages
            if len(daily_total) >= 7:
                daily_total["ma_7"] = daily_total["sales"].rolling(window=7, min_periods=1).mean()
            if len(daily_total) >= 30:
                daily_total["ma_30"] = daily_total["sales"].rolling(window=30, min_periods=1).mean()
            
            # Plot
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=daily_total["date"],
                y=daily_total["sales"],
                mode="lines",
                name="Daily Sales",
                line=dict(color="#3498db", width=1),
                opacity=0.5
            ))
            
            if "ma_7" in daily_total.columns:
                fig.add_trace(go.Scatter(
                    x=daily_total["date"],
                    y=daily_total["ma_7"],
                    mode="lines",
                    name="7-Day MA",
                    line=dict(color="#e67e22", width=2)
                ))
            
            if "ma_30" in daily_total.columns:
                fig.add_trace(go.Scatter(
                    x=daily_total["date"],
                    y=daily_total["ma_30"],
                    mode="lines",
                    name="30-Day MA",
                    line=dict(color="#2ecc71", width=2)
                ))
            
            fig.update_layout(
                title="Overall Sales Trend",
                xaxis_title="Date",
                yaxis_title="Sales ($)",
                height=400,
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Growth metrics
            if len(daily_total) >= 2:
                # Calculate growth
                first_half = daily_total.head(len(daily_total)//2)["sales"].mean()
                second_half = daily_total.tail(len(daily_total)//2)["sales"].mean()
                growth = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "📊 Growth Rate",
                        f"{growth:.1f}%",
                        delta=f"{growth:.1f}%" if growth != 0 else None
                    )
                
                with col2:
                    st.metric(
                        "📈 Avg Daily Sales",
                        f"${daily_total['sales'].mean():.2f}"
                    )
                
                with col3:
                    st.metric(
                        "📉 Avg 7-Day",
                        f"${daily_total['sales'].tail(7).mean():.2f}"
                    )
            
            # Weekly pattern
            st.markdown("### 📅 Weekly Pattern")
            
            daily_total["day_of_week"] = daily_total["date"].dt.dayofweek
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            weekly_avg = daily_total.groupby("day_of_week")["sales"].mean().reset_index()
            weekly_avg["day_name"] = weekly_avg["day_of_week"].apply(lambda x: day_names[x])
            
            fig = px.bar(
                weekly_avg,
                x="day_name",
                y="sales",
                title="Average Sales by Day of Week",
                color="sales",
                color_continuous_scale="Viridis",
                text="sales"
            )
            fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
    
    # ==============================
    # TAB 4: PREDICTIONS & RECOMMENDATIONS
    # ==============================
    with tab4:
        st.markdown("## 💡 AI Predictions & Recommendations")
        
        # Calculate various predictions
        total_sales = float(filtered_df["total"].sum())
        total_profit = float(filtered_df["profit"].sum())
        total_items = int(filtered_df["items"].sum())
        
        # Calculate growth rate
        if len(filtered_df) >= 2:
            # Get monthly totals
            filtered_df["month"] = filtered_df["date"].dt.to_period("M")
            monthly = filtered_df.groupby("month")["total"].sum()
            
            if len(monthly) >= 2:
                last_month = monthly.iloc[-1]
                prev_month = monthly.iloc[-2]
                month_growth = ((last_month - prev_month) / prev_month * 100) if prev_month > 0 else 0
            else:
                month_growth = 0
        else:
            month_growth = 0
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "📈 Monthly Growth",
                f"{month_growth:.1f}%",
                delta=f"{month_growth:.1f}%" if month_growth != 0 else None,
                delta_color="normal" if month_growth >= 0 else "inverse"
            )
        
        with col2:
            # Predict next month sales
            if len(filtered_df) >= 30:
                daily = prepare_time_series_data(filtered_df)
                if daily and len(daily) >= 30:
                    forecast = forecast_sales(daily, 30, "Linear Regression")
                    if forecast:
                        st.metric(
                            "📊 Next Month Forecast",
                            f"${forecast['total_forecast']:,.2f}",
                            delta=f"±${forecast['confidence_interval']:.2f}"
                        )
                    else:
                        st.metric("📊 Next Month Forecast", "Insufficient data")
                else:
                    st.metric("📊 Next Month Forecast", "Insufficient data")
            else:
                st.metric("📊 Next Month Forecast", "Need 30+ days of data")
        
        with col3:
            # Profitability prediction
            if total_sales > 0:
                profit_margin = (total_profit / total_sales * 100)
                st.metric(
                    "💰 Profit Margin",
                    f"{profit_margin:.1f}%",
                    delta="Good" if profit_margin > 20 else ("Fair" if profit_margin > 10 else "Low"),
                    delta_color="normal" if profit_margin > 15 else "inverse"
                )
            else:
                st.metric("💰 Profit Margin", "N/A")
        
        st.markdown("---")
        
        # Recommendations
        st.markdown("### 🎯 AI Recommendations")
        
        recommendations = []
        
        # Check for top products
        top_products = get_top_products(filtered_df, 5)
        if not top_products.empty:
            top_names = top_products["name"].head(3).tolist()
            recommendations.append(
                f"📈 **Focus on Top Products**: {', '.join(top_names)} are your best sellers. "
                f"Consider increasing stock and marketing these products."
            )
        
        # Check for slow movers
        all_products = filtered_df["name"].unique()
        if len(all_products) > 5:
            product_counts = filtered_df.groupby("name")["items"].sum()
            slow_movers = product_counts[product_counts < product_counts.quantile(0.25)].index.tolist()[:3]
            if slow_movers:
                recommendations.append(
                    f"⚠️ **Slow Movers**: {', '.join(slow_movers)} have low sales. "
                    f"Consider discounting or running promotions to clear stock."
                )
        
        # Check for seasonal patterns
        if len(filtered_df) >= 30:
            daily = prepare_time_series_data(filtered_df)
            if daily and len(daily) >= 30:
                # Check for weekend effect
                weekend_avg = daily[daily["is_weekend"] == 1]["sales"].mean()
                weekday_avg = daily[daily["is_weekend"] == 0]["sales"].mean()
                
                if weekend_avg > weekday_avg * 1.2:
                    recommendations.append(
                        f"📅 **Weekend Effect**: Sales are {weekend_avg/weekday_avg:.1f}x higher on weekends. "
                        f"Consider weekend promotions and staffing accordingly."
                    )
        
        # Check for profit optimization
        product_margin = filtered_df.groupby("name").agg({"profit": "sum", "total": "sum"}).reset_index()
        product_margin["margin"] = (product_margin["profit"] / product_margin["total"] * 100).fillna(0)
        
        low_margin = product_margin[product_margin["margin"] < 10]["name"].tolist()[:3]
        if low_margin:
            recommendations.append(
                f"💰 **Margin Improvement**: {', '.join(low_margin)} have low profit margins. "
                f"Review pricing or find cheaper suppliers."
            )
        
        if recommendations:
            for rec in recommendations:
                st.info(rec)
        else:
            st.success("✅ All metrics look good! Continue current strategies.")
        
        st.markdown("---")
        
        # Export predictions
        st.markdown("### 📥 Export Predictions")
        
        if st.button("Generate AI Report", type="primary"):
            report_data = {
                "Metric": [
                    "Total Sales", "Total Profit", "Average Daily Sales",
                    "Monthly Growth", "Number of Products Sold", "Average Transaction Value"
                ],
                "Value": [
                    f"${total_sales:,.2f}",
                    f"${total_profit:,.2f}",
                    f"${daily_total['sales'].mean():.2f}" if 'daily_total' in locals() else "N/A",
                    f"{month_growth:.1f}%",
                    len(filtered_df["name"].unique()),
                    f"${total_sales / len(filtered_df['receipt_no'].unique()):.2f}" if "receipt_no" in filtered_df.columns else "N/A"
                ]
            }
            report_df = pd.DataFrame(report_data)
            
            csv_report = report_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download AI Report (CSV)",
                data=csv_report,
                file_name=f"ai_report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    predictive_analytics_dashboard()