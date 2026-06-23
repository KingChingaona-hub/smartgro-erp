import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import load_sales, load_products

# ==============================
# DEMAND FORECASTING ENGINE
# ==============================

def get_column_mapping(df, column_types):
    """
    Helper function to find columns in a DataFrame
    
    Args:
        df: DataFrame to search
        column_types: dict with keys like 'product', 'date', 'total', 'items'
                     and values being lists of possible column names
    """
    if df is None or df.empty:
        return {}
    
    result = {}
    for key, possible_names in column_types.items():
        for name in possible_names:
            if name in df.columns:
                result[key] = name
                break
        if key not in result:
            result[key] = None
    
    return result


def prepare_sales_data(sales_df, product_name=None):
    """Prepare sales data for forecasting"""
    
    if sales_df.empty:
        return None
    
    # Find the date column
    date_col = None
    for col in ["date", "sale_date", "transaction_date"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col is None:
        return None
    
    sales_df[date_col] = pd.to_datetime(sales_df[date_col])
    
    # Find the product name column
    product_col = None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in sales_df.columns:
            product_col = col
            break
    
    if product_col is None:
        return None
    
    # Find the total/sales column
    total_col = None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    if total_col is None:
        return None
    
    # Filter by product if specified
    if product_name and product_name != "All Products" and product_name != "All":
        # Try to match product name
        df = sales_df[sales_df[product_col] == product_name].copy()
        if df.empty:
            # Try partial match
            df = sales_df[sales_df[product_col].str.contains(product_name, case=False, na=False)].copy()
        if df.empty:
            return None
    else:
        df = sales_df.copy()
    
    if df.empty:
        return None
    
    # Aggregate by date
    daily_sales = df.groupby(df[date_col].dt.date)[total_col].sum().reset_index()
    daily_sales.columns = ["date", "sales"]
    daily_sales["date"] = pd.to_datetime(daily_sales["date"])
    daily_sales = daily_sales.sort_values("date")
    
    return daily_sales


def add_time_features(df):
    """Add time-based features for better predictions"""
    
    if df is None or df.empty:
        return None
    
    df = df.copy()
    df["day_of_week"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["day_of_month"] = df["date"].dt.day
    df["week_of_year"] = df["date"].dt.isocalendar().week
    df["quarter"] = df["date"].dt.quarter
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["days_since_start"] = (df["date"] - df["date"].min()).dt.days
    
    return df


def forecast_sales_linear(daily_sales, days=30):
    """Linear regression forecast with confidence intervals"""
    
    if daily_sales is None or len(daily_sales) < 7:
        return None
    
    # Prepare features
    sales_data = add_time_features(daily_sales)
    
    # Use days_since_start as feature
    X = sales_data["days_since_start"].values.reshape(-1, 1)
    y = sales_data["sales"].values
    
    # Train model
    model = LinearRegression()
    model.fit(X, y)
    
    # Predict future
    last_day = sales_data["days_since_start"].max()
    future_days = np.arange(last_day + 1, last_day + days + 1).reshape(-1, 1)
    predictions = model.predict(future_days)
    predictions = np.maximum(predictions, 0)  # No negative sales
    
    # Calculate confidence intervals (95%)
    residuals = y - model.predict(X)
    std_residual = np.std(residuals)
    confidence_interval = 1.96 * std_residual
    
    # Generate forecast dates
    last_date = daily_sales["date"].max()
    forecast_dates = [last_date + timedelta(days=i) for i in range(1, days + 1)]
    
    forecast = []
    for i, (date, pred) in enumerate(zip(forecast_dates, predictions)):
        forecast.append({
            "date": date.strftime("%Y-%m-%d"),
            "forecast_sales": round(pred, 2),
            "lower_bound": round(max(0, pred - confidence_interval), 2),
            "upper_bound": round(pred + confidence_interval, 2)
        })
    
    # Calculate metrics
    mae = mean_absolute_error(y, model.predict(X))
    rmse = np.sqrt(mean_squared_error(y, model.predict(X)))
    
    # Calculate trend
    slope = model.coef_[0]
    trend = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
    
    return {
        "forecast": forecast,
        "total_forecast": round(sum(predictions), 2),
        "avg_daily": round(np.mean(predictions), 2),
        "trend": trend,
        "trend_strength": abs(slope),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "confidence_interval": round(confidence_interval, 2),
        "model_type": "Linear Regression"
    }


def forecast_sales_random_forest(daily_sales, days=30):
    """Random Forest forecast for better accuracy"""
    
    if daily_sales is None or len(daily_sales) < 30:
        return None
    
    sales_data = add_time_features(daily_sales)
    
    # Features for Random Forest
    feature_cols = ["day_of_week", "month", "day_of_month", "week_of_year", "quarter", "is_weekend", "days_since_start"]
    X = sales_data[feature_cols].values
    y = sales_data["sales"].values
    
    # Train model
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X, y)
    
    # Predict future
    last_date = daily_sales["date"].max()
    future_dates = [last_date + timedelta(days=i) for i in range(1, days + 1)]
    
    # Create feature matrix for future dates
    future_features = []
    for i, date in enumerate(future_dates):
        features = {
            "day_of_week": date.weekday(),
            "month": date.month,
            "day_of_month": date.day,
            "week_of_year": date.isocalendar().week,
            "quarter": (date.month - 1) // 3 + 1,
            "is_weekend": 1 if date.weekday() >= 5 else 0,
            "days_since_start": sales_data["days_since_start"].max() + i + 1
        }
        future_features.append([features[col] for col in feature_cols])
    
    predictions = model.predict(future_features)
    predictions = np.maximum(predictions, 0)
    
    # Calculate confidence intervals
    residuals = y - model.predict(X)
    std_residual = np.std(residuals)
    confidence_interval = 1.96 * std_residual
    
    forecast = []
    for i, (date, pred) in enumerate(zip(future_dates, predictions)):
        forecast.append({
            "date": date.strftime("%Y-%m-%d"),
            "forecast_sales": round(pred, 2),
            "lower_bound": round(max(0, pred - confidence_interval), 2),
            "upper_bound": round(pred + confidence_interval, 2)
        })
    
    # Calculate metrics
    mae = mean_absolute_error(y, model.predict(X))
    rmse = np.sqrt(mean_squared_error(y, model.predict(X)))
    
    # Feature importance
    feature_importance = dict(zip(feature_cols, model.feature_importances_))
    
    return {
        "forecast": forecast,
        "total_forecast": round(sum(predictions), 2),
        "avg_daily": round(np.mean(predictions), 2),
        "trend": "based on multiple factors",
        "feature_importance": feature_importance,
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "confidence_interval": round(confidence_interval, 2),
        "model_type": "Random Forest"
    }


def calculate_eoq(annual_demand, order_cost, holding_cost_per_unit):
    """Calculate Economic Order Quantity (EOQ)"""
    if annual_demand <= 0 or order_cost <= 0 or holding_cost_per_unit <= 0:
        return 0
    eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost_per_unit)
    return round(eoq)


def get_product_demand_metrics(product_name, sales_df, products_df):
    """
    Get demand metrics for a specific product
    FIXED: Now handles missing columns properly
    """
    
    if sales_df.empty or products_df.empty:
        return None
    
    # Find product name column in sales
    product_col_sales = None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in sales_df.columns:
            product_col_sales = col
            break
    
    if product_col_sales is None:
        return None
    
    # Find date column
    date_col = None
    for col in ["date", "sale_date", "transaction_date"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col is None:
        return None
    
    # Find items column
    items_col = None
    for col in ["items", "quantity", "qty", "amount"]:
        if col in sales_df.columns:
            items_col = col
            break
    
    # Find total column for revenue
    total_col = None
    for col in ["total", "final_total", "sale_amount", "revenue"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    # Find product price and cost columns
    price_col = None
    cost_col = None
    stock_col = None
    product_col_products = None
    
    if not products_df.empty:
        for col in ["name", "product_name", "Product"]:
            if col in products_df.columns:
                product_col_products = col
                break
        
        for col in ["price", "selling_price", "unit_price"]:
            if col in products_df.columns:
                price_col = col
                break
        
        for col in ["cost", "cost_price", "purchase_price"]:
            if col in products_df.columns:
                cost_col = col
                break
        
        for col in ["stock", "quantity", "inventory", "current_stock"]:
            if col in products_df.columns:
                stock_col = col
                break
    
    # Filter sales for this product
    product_sales = sales_df[sales_df[product_col_sales] == product_name]
    
    if product_sales.empty:
        return None
    
    # Get product cost and price
    cost = 0
    price = 0
    current_stock = 0
    
    if product_col_products and not products_df.empty:
        product = products_df[products_df[product_col_products] == product_name]
        if not product.empty:
            if cost_col and cost_col in product.columns:
                cost = product.iloc[0].get(cost_col, 0)
            if price_col and price_col in product.columns:
                price = product.iloc[0].get(price_col, 0)
            if stock_col and stock_col in product.columns:
                current_stock = product.iloc[0].get(stock_col, 0)
    
    # Convert date column
    product_sales[date_col] = pd.to_datetime(product_sales[date_col])
    
    # Calculate metrics
    # Get quantity sold
    if items_col and items_col in product_sales.columns:
        total_sold = product_sales[items_col].sum()
    else:
        total_sold = len(product_sales)
    
    # Daily sales
    daily_sales = product_sales.groupby(product_sales[date_col].dt.date)[items_col].sum() if items_col else product_sales.groupby(product_sales[date_col].dt.date).size()
    avg_daily_sales = daily_sales.mean() if not daily_sales.empty else 0
    
    # Weekly sales
    weekly_sales = product_sales.groupby(product_sales[date_col].dt.isocalendar().week)[items_col].sum() if items_col else product_sales.groupby(product_sales[date_col].dt.isocalendar().week).size()
    avg_weekly_sales = weekly_sales.mean() if not weekly_sales.empty else 0
    
    # Monthly sales
    monthly_sales = product_sales.groupby(product_sales[date_col].dt.month)[items_col].sum() if items_col else product_sales.groupby(product_sales[date_col].dt.month).size()
    avg_monthly_sales = monthly_sales.mean() if not monthly_sales.empty else 0
    
    # Sales per day
    date_range = (product_sales[date_col].max() - product_sales[date_col].min()).days
    if date_range == 0:
        date_range = 1
    sales_per_day = total_sold / date_range
    
    # Days of stock remaining
    days_of_stock = current_stock / sales_per_day if sales_per_day > 0 else 0
    
    # Seasonality detection
    monthly_pattern = monthly_sales.to_dict() if not monthly_sales.empty else {}
    
    # Growth rate
    if len(product_sales) >= 30:
        product_sales = product_sales.sort_values(date_col)
        product_sales["cumulative"] = product_sales[items_col].cumsum() if items_col else product_sales.index.cumsum()
        if len(product_sales) >= 2:
            first_half = product_sales.iloc[:len(product_sales)//2][items_col].sum() if items_col else len(product_sales.iloc[:len(product_sales)//2])
            second_half = product_sales.iloc[len(product_sales)//2:][items_col].sum() if items_col else len(product_sales.iloc[len(product_sales)//2:])
            growth_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
        else:
            growth_rate = 0
    else:
        growth_rate = 0
    
    # Classification
    if total_sold < 10:
        classification = "Slow Mover"
    elif total_sold < 50:
        classification = "Standard"
    elif total_sold < 200:
        classification = "Fast Mover"
    else:
        classification = "Super Mover"
    
    # Profitability
    if cost > 0 and price > 0:
        margin_percent = ((price - cost) / price * 100) if price > 0 else 0
    else:
        margin_percent = 0
    
    return {
        "product_name": product_name,
        "total_sold": int(total_sold),
        "avg_daily_sales": round(avg_daily_sales, 2),
        "avg_weekly_sales": round(avg_weekly_sales, 2),
        "avg_monthly_sales": round(avg_monthly_sales, 2),
        "sales_per_day": round(sales_per_day, 2),
        "current_stock": int(current_stock),
        "days_of_stock": round(days_of_stock, 1),
        "growth_rate": round(growth_rate, 1),
        "classification": classification,
        "price": price,
        "cost": cost,
        "margin_percent": round(margin_percent, 1),
        "monthly_pattern": monthly_pattern
    }


def get_recommendations(sales_df, products_df):
    """Generate product recommendations based on purchase patterns"""
    
    if sales_df.empty or len(sales_df) < 100:
        return pd.DataFrame()
    
    # Find receipt and product columns
    receipt_col = None
    product_col = None
    
    for col in ["receipt_no", "receipt", "transaction_id", "order_id"]:
        if col in sales_df.columns:
            receipt_col = col
            break
    
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in sales_df.columns:
            product_col = col
            break
    
    if receipt_col is None or product_col is None:
        return pd.DataFrame()
    
    # Create baskets
    baskets = sales_df.groupby(receipt_col)[product_col].apply(list).reset_index()
    
    # Find product pairs
    from collections import Counter
    from itertools import combinations
    
    pair_counter = Counter()
    
    for basket in baskets[product_col]:
        if len(basket) > 1:
            # Remove duplicates in basket
            basket = list(set(basket))
            if len(basket) > 1:
                for pair in combinations(sorted(basket), 2):
                    pair_counter[pair] += 1
    
    # Get top recommendations
    recommendations = []
    for (product1, product2), count in pair_counter.most_common(30):
        recommendations.append({
            "Product": product1,
            "Bought With": product2,
            "Frequency": count
        })
    
    return pd.DataFrame(recommendations)


def identify_slow_movers(products_df, sales_df, days_threshold=90):
    """Identify slow-moving products"""
    
    if sales_df.empty or products_df.empty:
        return pd.DataFrame()
    
    # Find date and product columns
    date_col = None
    for col in ["date", "sale_date", "transaction_date"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    product_col_sales = None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in sales_df.columns:
            product_col_sales = col
            break
    
    product_col_products = None
    for col in ["name", "product_name", "Product"]:
        if col in products_df.columns:
            product_col_products = col
            break
    
    if date_col is None or product_col_sales is None or product_col_products is None:
        return pd.DataFrame()
    
    sales_df[date_col] = pd.to_datetime(sales_df[date_col])
    cutoff_date = datetime.now() - timedelta(days=days_threshold)
    
    # Get products sold in last X days
    recent_sales = sales_df[sales_df[date_col] >= cutoff_date]
    sold_products = recent_sales[product_col_sales].unique() if not recent_sales.empty else []
    
    # Find stock and price columns
    stock_col = None
    price_col = None
    for col in ["stock", "quantity", "inventory"]:
        if col in products_df.columns:
            stock_col = col
            break
    
    for col in ["price", "selling_price", "unit_price"]:
        if col in products_df.columns:
            price_col = col
            break
    
    # Find products not sold in period
    slow_movers = []
    for _, product in products_df.iterrows():
        product_name = product[product_col_products]
        if product_name not in sold_products:
            stock = product.get(stock_col, 0) if stock_col else 0
            price = product.get(price_col, 0) if price_col else 0
            slow_movers.append({
                "Product Name": product_name,
                "Current Stock": stock,
                "Last Sale": f"No sales in {days_threshold} days",
                "Stock Value": stock * price,
                "Suggested Action": "Consider discount or removal"
            })
        elif recent_sales is not None and not recent_sales.empty:
            product_sales = recent_sales[recent_sales[product_col_sales] == product_name]
            if len(product_sales) < 2:
                stock = product.get(stock_col, 0) if stock_col else 0
                price = product.get(price_col, 0) if price_col else 0
                slow_movers.append({
                    "Product Name": product_name,
                    "Current Stock": stock,
                    "Last Sale": f"{len(product_sales)} sale(s) in {days_threshold} days",
                    "Stock Value": stock * price,
                    "Suggested Action": "Monitor closely"
                })
    
    return pd.DataFrame(slow_movers)


# ==============================
# DEMAND FORECASTING DASHBOARD
# ==============================

def demand_forecasting_dashboard():
    """Main demand forecasting dashboard - FIXED for column name issues"""
    
    st.title("🤖 AI-Powered Demand Forecasting")
    st.caption("Predict sales, identify trends, and optimize inventory with machine learning")
    
    # Load data
    sales_df = load_sales()
    products_df = load_products()
    
    if sales_df.empty:
        st.warning("Not enough sales data for forecasting. Complete at least 7 days of sales.")
        return
    
    # Determine column names for products
    product_col_sales = None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in sales_df.columns:
            product_col_sales = col
            break
    
    product_col_products = None
    for col in ["name", "product_name", "Product"]:
        if col in products_df.columns:
            product_col_products = col
            break
    
    # Get product list for dropdown
    if products_df.empty:
        products_list = []
    elif product_col_products:
        products_list = ["All Products"] + products_df[product_col_products].tolist()
    else:
        products_list = ["All Products"]
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Sales Forecast",
        "📊 Product Analytics",
        "🔄 Product Recommendations",
        "🐌 Slow Movers",
        "📋 EOQ Calculator"
    ])
    
    # ==============================
    # TAB 1: SALES FORECAST
    # ==============================
    with tab1:
        st.markdown("## 📈 30-Day Sales Forecast")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_product = st.selectbox("Select Product", products_list, key="forecast_product")
        
        with col2:
            forecast_days = st.slider("Forecast Days", 7, 90, 30, key="forecast_days")
            model_type = st.selectbox("Forecast Model", ["Linear Regression", "Random Forest"], key="model_type")
        
        if st.button("🔮 Generate Forecast", type="primary", use_container_width=True):
            with st.spinner("Training AI model and generating forecast..."):
                daily_sales = prepare_sales_data(sales_df, selected_product)
                
                if daily_sales is None or len(daily_sales) < 7:
                    st.error("Not enough historical data for this product. Need at least 7 days of sales.")
                else:
                    # Generate forecast
                    if model_type == "Linear Regression":
                        forecast_result = forecast_sales_linear(daily_sales, forecast_days)
                    else:
                        forecast_result = forecast_sales_random_forest(daily_sales, forecast_days)
                    
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
                        
                        # Create chart
                        import plotly.graph_objects as go
                        
                        fig = go.Figure()
                        
                        # Add actual sales (last 30 days)
                        actual_df = daily_sales.tail(30)
                        fig.add_trace(go.Scatter(
                            x=actual_df["date"],
                            y=actual_df["sales"],
                            mode="lines+markers",
                            name="Actual Sales",
                            line=dict(color="#3498db", width=2),
                            marker=dict(size=6)
                        ))
                        
                        # Add forecast
                        fig.add_trace(go.Scatter(
                            x=forecast_df["date"],
                            y=forecast_df["forecast_sales"],
                            mode="lines+markers",
                            name="Forecast",
                            line=dict(color="#2ecc71", width=2, dash="dash"),
                            marker=dict(size=6)
                        ))
                        
                        # Add confidence interval
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
                            title=f"Sales Forecast for {selected_product} - Next {forecast_days} Days",
                            xaxis_title="Date",
                            yaxis_title="Sales ($)",
                            height=450,
                            hovermode="x unified"
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Model metrics
                        with st.expander("📊 Model Performance Metrics"):
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Mean Absolute Error (MAE)", f"${forecast_result['mae']:.2f}")
                            with col2:
                                st.metric("Root Mean Squared Error (RMSE)", f"${forecast_result['rmse']:.2f}")
                            
                            if "feature_importance" in forecast_result:
                                st.markdown("**Feature Importance:**")
                                for feature, importance in sorted(forecast_result['feature_importance'].items(), key=lambda x: -x[1])[:5]:
                                    st.progress(importance, text=f"{feature}: {importance:.1%}")
                        
                        # Download forecast
                        csv = forecast_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Forecast (CSV)",
                            data=csv,
                            file_name=f"forecast_{selected_product}_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.error("Forecast failed. Please try again.")
    
    # ==============================
    # TAB 2: PRODUCT ANALYTICS
    # ==============================
    with tab2:
        st.markdown("## 📊 Product Demand Analytics")
        
        if not products_df.empty and product_col_products:
            selected_product = st.selectbox("Select Product for Analysis", products_df[product_col_products].tolist(), key="analytics_product")
            
            if selected_product:
                metrics = get_product_demand_metrics(selected_product, sales_df, products_df)
                
                if metrics:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📦 Total Sold", metrics['total_sold'])
                    with col2:
                        st.metric("📈 Sales/Day", f"{metrics['sales_per_day']:.1f}")
                    with col3:
                        st.metric("📊 Classification", metrics['classification'])
                    with col4:
                        st.metric("💰 Margin", f"{metrics['margin_percent']:.1f}%")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("🏷️ Current Stock", metrics['current_stock'])
                    with col2:
                        days_color = "inverse" if metrics['days_of_stock'] < 7 else "normal"
                        st.metric("📅 Days of Stock", f"{metrics['days_of_stock']:.0f}", delta_color=days_color)
                    with col3:
                        growth_icon = "📈" if metrics['growth_rate'] > 0 else "📉"
                        st.metric(f"{growth_icon} Growth Rate", f"{metrics['growth_rate']:.1f}%")
                    
                    st.markdown("---")
                    
                    # Monthly pattern visualization
                    if metrics['monthly_pattern']:
                        st.markdown("### 📅 Seasonal Pattern")
                        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                        pattern_data = []
                        for month, sales in metrics['monthly_pattern'].items():
                            if 1 <= month <= 12:
                                pattern_data.append({"Month": months[month-1], "Sales": sales})
                        
                        if pattern_data:
                            pattern_df = pd.DataFrame(pattern_data)
                            
                            import plotly.express as px
                            fig = px.bar(
                                pattern_df,
                                x="Month",
                                y="Sales",
                                title="Monthly Sales Pattern",
                                color="Sales",
                                color_continuous_scale="Viridis"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # Reorder recommendation
                    st.markdown("### 💡 Reorder Recommendation")
                    if metrics['days_of_stock'] < 7:
                        st.error(f"⚠️ CRITICAL: Only {metrics['days_of_stock']:.0f} days of stock remaining! Order immediately.")
                    elif metrics['days_of_stock'] < 14:
                        st.warning(f"⚠️ Low stock: {metrics['days_of_stock']:.0f} days remaining. Place order soon.")
                    else:
                        st.success(f"✅ Stock healthy: {metrics['days_of_stock']:.0f} days of inventory.")
                else:
                    st.info("Not enough data for this product")
        else:
            st.info("No products found")
    
    # ==============================
    # TAB 3: PRODUCT RECOMMENDATIONS
    # ==============================
    with tab3:
        st.markdown("## 🔄 Frequently Bought Together")
        st.caption("\"Customers who bought X also bought Y\" recommendations")
        
        recommendations_df = get_recommendations(sales_df, products_df)
        
        if not recommendations_df.empty:
            st.dataframe(recommendations_df, use_container_width=True, hide_index=True)
            
            # Visualization
            top_recs = recommendations_df.head(10)
            import plotly.express as px
            fig = px.bar(
                top_recs,
                x="Frequency",
                y="Product",
                color="Frequency",
                orientation='h',
                title="Top Product Affinities",
                text="Frequency"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough transaction data for recommendations. Need at least 100 transactions.")
    
    # ==============================
    # TAB 4: SLOW MOVERS
    # ==============================
    with tab4:
        st.markdown("## 🐌 Slow-Moving Products")
        st.caption("Products that need attention")
        
        days_threshold = st.slider("Days without sale to classify as slow mover", 30, 180, 90)
        
        slow_movers_df = identify_slow_movers(products_df, sales_df, days_threshold)
        
        if not slow_movers_df.empty:
            st.warning(f"⚠️ {len(slow_movers_df)} products are slow-moving or have no recent sales")
            st.dataframe(slow_movers_df, use_container_width=True, hide_index=True)
            
            # Total value at risk
            total_value = slow_movers_df["Stock Value"].sum()
            st.error(f"💰 Total inventory value at risk: ${total_value:,.2f}")
            
            if st.button("Generate Markdown Suggestions"):
                st.info("Suggested actions sent to manager's dashboard")
        else:
            st.success("✅ No slow-moving products detected! All products are selling well.")
    
    # ==============================
    # TAB 5: EOQ CALCULATOR
    # ==============================
    with tab5:
        st.markdown("## 📋 Economic Order Quantity (EOQ) Calculator")
        st.caption("Calculate the optimal order quantity to minimize total inventory costs")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if not products_df.empty and product_col_products:
                selected_product = st.selectbox("Select Product", products_df[product_col_products].tolist(), key="eoq_product")
                
                # Get product metrics
                metrics = get_product_demand_metrics(selected_product, sales_df, products_df)
                if metrics:
                    # Calculate annual demand
                    date_col = None
                    for col in ["date", "sale_date", "transaction_date"]:
                        if col in sales_df.columns:
                            date_col = col
                            break
                    
                    if date_col:
                        days_range = (sales_df[date_col].max() - sales_df[date_col].min()).days
                        if days_range > 0:
                            annual_demand = metrics['total_sold'] * (365 / days_range)
                        else:
                            annual_demand = metrics['total_sold'] * 12  # Assume monthly
                    else:
                        annual_demand = metrics['total_sold'] * 12
                    
                    st.info(f"📊 Estimated Annual Demand: {int(annual_demand):,} units")
                else:
                    annual_demand = st.number_input("Annual Demand (units)", min_value=1, value=100)
            else:
                annual_demand = st.number_input("Annual Demand (units)", min_value=1, value=100)
        
        with col2:
            order_cost = st.number_input("Order Cost ($ per order)", min_value=1.0, value=50.0, step=5.0)
            holding_cost = st.number_input("Holding Cost ($ per unit per year)", min_value=0.1, value=5.0, step=0.5)
        
        if st.button("📊 Calculate EOQ", type="primary", use_container_width=True):
            eoq = calculate_eoq(annual_demand, order_cost, holding_cost)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🎯 Economic Order Quantity", f"{eoq:,} units")
            with col2:
                orders_per_year = annual_demand / eoq if eoq > 0 else 0
                st.metric("📦 Orders per Year", f"{orders_per_year:.1f}")
            with col3:
                total_cost = (annual_demand / eoq * order_cost) + (eoq / 2 * holding_cost) if eoq > 0 else 0
                st.metric("💰 Total Annual Cost", f"${total_cost:,.2f}")
            
            st.info(f"""
            **Recommendation:** Order **{eoq:,} units** each time to minimize total inventory costs.
            
            This balances ordering costs (${order_cost}/order) and holding costs (${holding_cost}/unit/year).
            """)

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    demand_forecasting_dashboard()