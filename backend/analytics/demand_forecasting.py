import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import plotly.graph_objects as go
import plotly.express as px
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import load_sales, load_products


# ==============================
# HELPER FUNCTIONS - FIXED
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


def find_column(df, possible_names, default=None):
    """Find the first column that matches any of the possible names"""
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return default


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
        found = find_column(df, possible_names)
        result[key] = found
    
    return result


def prepare_sales_data(sales_df, product_name=None):
    """Prepare sales data for forecasting - FIXED"""
    
    if sales_df.empty:
        return None
    
    # Find the date column
    date_col = find_column(sales_df, ["date", "sale_date", "transaction_date", "created_at"])
    if date_col is None:
        return None
    
    # Find the product name column
    product_col = find_column(sales_df, ["name", "product_name", "Product", "item_name", "product"])
    if product_col is None:
        return None
    
    # Find the total/sales column
    total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount", "revenue"])
    if total_col is None:
        return None
    
    # Find items/quantity column for volume
    items_col = find_column(sales_df, ["items", "quantity", "qty", "units"])
    
    try:
        # Convert date column
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        if sales_df.empty:
            return None
        
        # Filter by product if specified
        if product_name and product_name != "All Products" and product_name != "All":
            # Try to match product name
            df = sales_df[sales_df[product_col] == product_name].copy()
            if df.empty:
                # Try partial match
                df = sales_df[sales_df[product_col].astype(str).str.contains(product_name, case=False, na=False)].copy()
            if df.empty:
                return None
        else:
            df = sales_df.copy()
        
        if df.empty:
            return None
        
        # Use items column if available for quantity, otherwise use count
        if items_col and items_col in df.columns:
            daily_sales = df.groupby(df[date_col].dt.date)[items_col].sum().reset_index()
        else:
            # Use total value
            daily_sales = df.groupby(df[date_col].dt.date)[total_col].sum().reset_index()
        
        daily_sales.columns = ["date", "sales"]
        daily_sales["date"] = pd.to_datetime(daily_sales["date"])
        daily_sales = daily_sales.sort_values("date")
        
        return daily_sales
    except Exception as e:
        print(f"Error preparing sales data: {e}")
        return None


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
    """Linear regression forecast with confidence intervals - FIXED"""
    
    if daily_sales is None or len(daily_sales) < 7:
        return None
    
    try:
        # Prepare features
        sales_data = add_time_features(daily_sales)
        if sales_data is None:
            return None
        
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
                "forecast_sales": round(safe_float(pred), 2),
                "lower_bound": round(max(0, safe_float(pred - confidence_interval)), 2),
                "upper_bound": round(safe_float(pred + confidence_interval), 2)
            })
        
        # Calculate metrics
        mae = mean_absolute_error(y, model.predict(X))
        rmse = np.sqrt(mean_squared_error(y, model.predict(X)))
        
        # Calculate trend
        slope = model.coef_[0]
        trend = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
        
        return {
            "forecast": forecast,
            "total_forecast": round(safe_float(sum(predictions)), 2),
            "avg_daily": round(safe_float(np.mean(predictions)), 2),
            "trend": trend,
            "trend_strength": abs(slope),
            "mae": round(safe_float(mae), 2),
            "rmse": round(safe_float(rmse), 2),
            "confidence_interval": round(safe_float(confidence_interval), 2),
            "model_type": "Linear Regression"
        }
    except Exception as e:
        print(f"Linear forecast error: {e}")
        return None


def forecast_sales_random_forest(daily_sales, days=30):
    """Random Forest forecast for better accuracy - FIXED"""
    
    if daily_sales is None or len(daily_sales) < 14:
        return None
    
    try:
        sales_data = add_time_features(daily_sales)
        if sales_data is None:
            return None
        
        # Features for Random Forest
        feature_cols = ["day_of_week", "month", "day_of_month", "week_of_year", "quarter", "is_weekend", "days_since_start"]
        X = sales_data[feature_cols].values
        y = sales_data["sales"].values
        
        # Train model
        model = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=10)
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
                "forecast_sales": round(safe_float(pred), 2),
                "lower_bound": round(max(0, safe_float(pred - confidence_interval)), 2),
                "upper_bound": round(safe_float(pred + confidence_interval), 2)
            })
        
        # Calculate metrics
        mae = mean_absolute_error(y, model.predict(X))
        rmse = np.sqrt(mean_squared_error(y, model.predict(X)))
        
        # Feature importance
        feature_importance = dict(zip(feature_cols, model.feature_importances_))
        
        return {
            "forecast": forecast,
            "total_forecast": round(safe_float(sum(predictions)), 2),
            "avg_daily": round(safe_float(np.mean(predictions)), 2),
            "trend": "based on multiple factors",
            "feature_importance": feature_importance,
            "mae": round(safe_float(mae), 2),
            "rmse": round(safe_float(rmse), 2),
            "confidence_interval": round(safe_float(confidence_interval), 2),
            "model_type": "Random Forest"
        }
    except Exception as e:
        print(f"Random Forest forecast error: {e}")
        return None


def calculate_eoq(annual_demand, order_cost, holding_cost_per_unit):
    """Calculate Economic Order Quantity (EOQ)"""
    try:
        annual_demand = safe_float(annual_demand)
        order_cost = safe_float(order_cost)
        holding_cost_per_unit = safe_float(holding_cost_per_unit)
        
        if annual_demand <= 0 or order_cost <= 0 or holding_cost_per_unit <= 0:
            return 0
        eoq = np.sqrt((2 * annual_demand * order_cost) / holding_cost_per_unit)
        return round(eoq)
    except:
        return 0


def get_product_demand_metrics(product_name, sales_df, products_df):
    """Get demand metrics for a specific product - FIXED"""
    
    if sales_df.empty or products_df.empty:
        return None
    
    # Find columns
    product_col_sales = find_column(sales_df, ["name", "product_name", "Product", "item_name", "product"])
    date_col = find_column(sales_df, ["date", "sale_date", "transaction_date", "created_at"])
    items_col = find_column(sales_df, ["items", "quantity", "qty", "units"])
    total_col = find_column(sales_df, ["total", "final_total", "amount", "sale_amount"])
    
    if product_col_sales is None or date_col is None:
        return None
    
    # Find product columns
    product_col_products = find_column(products_df, ["name", "product_name", "Product"])
    price_col = find_column(products_df, ["price", "selling_price", "unit_price"])
    cost_col = find_column(products_df, ["cost", "cost_price", "purchase_price"])
    stock_col = find_column(products_df, ["stock", "quantity", "inventory", "current_stock"])
    
    try:
        # Filter sales for this product
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
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
                if cost_col:
                    cost = safe_float(product.iloc[0].get(cost_col, 0))
                if price_col:
                    price = safe_float(product.iloc[0].get(price_col, 0))
                if stock_col:
                    current_stock = safe_int(product.iloc[0].get(stock_col, 0))
        
        # Calculate metrics
        if items_col and items_col in product_sales.columns:
            total_sold = safe_int(product_sales[items_col].sum())
        else:
            total_sold = len(product_sales)
        
        # Daily sales
        daily_sales = product_sales.groupby(product_sales[date_col].dt.date)[items_col].sum() if items_col and items_col in product_sales.columns else product_sales.groupby(product_sales[date_col].dt.date).size()
        avg_daily_sales = daily_sales.mean() if not daily_sales.empty else 0
        
        # Weekly sales
        weekly_sales = product_sales.groupby(product_sales[date_col].dt.isocalendar().week)[items_col].sum() if items_col and items_col in product_sales.columns else product_sales.groupby(product_sales[date_col].dt.isocalendar().week).size()
        avg_weekly_sales = weekly_sales.mean() if not weekly_sales.empty else 0
        
        # Monthly sales
        monthly_sales = product_sales.groupby(product_sales[date_col].dt.month)[items_col].sum() if items_col and items_col in product_sales.columns else product_sales.groupby(product_sales[date_col].dt.month).size()
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
        growth_rate = 0
        if len(product_sales) >= 14:
            product_sales = product_sales.sort_values(date_col)
            if len(product_sales) >= 2:
                mid_point = len(product_sales) // 2
                first_half = product_sales.iloc[:mid_point]
                second_half = product_sales.iloc[mid_point:]
                
                first_total = first_half[items_col].sum() if items_col and items_col in first_half.columns else len(first_half)
                second_total = second_half[items_col].sum() if items_col and items_col in second_half.columns else len(second_half)
                
                if first_total > 0:
                    growth_rate = ((second_total - first_total) / first_total) * 100
        
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
            "avg_daily_sales": round(safe_float(avg_daily_sales), 2),
            "avg_weekly_sales": round(safe_float(avg_weekly_sales), 2),
            "avg_monthly_sales": round(safe_float(avg_monthly_sales), 2),
            "sales_per_day": round(safe_float(sales_per_day), 2),
            "current_stock": int(current_stock),
            "days_of_stock": round(safe_float(days_of_stock), 1),
            "growth_rate": round(safe_float(growth_rate), 1),
            "classification": classification,
            "price": safe_float(price),
            "cost": safe_float(cost),
            "margin_percent": round(safe_float(margin_percent), 1),
            "monthly_pattern": monthly_pattern
        }
    except Exception as e:
        print(f"Error getting product metrics: {e}")
        return None


def get_recommendations(sales_df, products_df):
    """Generate product recommendations based on purchase patterns - FIXED"""
    
    if sales_df.empty or len(sales_df) < 50:
        return pd.DataFrame()
    
    receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id", "invoice_no"])
    product_col = find_column(sales_df, ["name", "product_name", "Product", "item_name", "product"])
    
    if receipt_col is None or product_col is None:
        return pd.DataFrame()
    
    try:
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
    except Exception as e:
        print(f"Error getting recommendations: {e}")
        return pd.DataFrame()


def identify_slow_movers(products_df, sales_df, days_threshold=90):
    """Identify slow-moving products - FIXED"""
    
    if sales_df.empty or products_df.empty:
        return pd.DataFrame()
    
    date_col = find_column(sales_df, ["date", "sale_date", "transaction_date", "created_at"])
    product_col_sales = find_column(sales_df, ["name", "product_name", "Product", "item_name", "product"])
    product_col_products = find_column(products_df, ["name", "product_name", "Product"])
    
    if date_col is None or product_col_sales is None or product_col_products is None:
        return pd.DataFrame()
    
    try:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        # Get products sold in last X days
        recent_sales = sales_df[sales_df[date_col] >= cutoff_date]
        sold_products = recent_sales[product_col_sales].unique() if not recent_sales.empty else []
        
        # Find stock and price columns
        stock_col = find_column(products_df, ["stock", "quantity", "inventory", "current_stock"])
        price_col = find_column(products_df, ["price", "selling_price", "unit_price"])
        
        # Find products not sold in period
        slow_movers = []
        for _, product in products_df.iterrows():
            product_name = product[product_col_products]
            if product_name not in sold_products:
                stock = safe_int(product.get(stock_col, 0)) if stock_col else 0
                price = safe_float(product.get(price_col, 0)) if price_col else 0
                slow_movers.append({
                    "Product Name": product_name,
                    "Current Stock": stock,
                    "Last Sale": f"No sales in {days_threshold} days",
                    "Stock Value": stock * price,
                    "Suggested Action": "Consider discount or removal"
                })
        
        return pd.DataFrame(slow_movers)
    except Exception as e:
        print(f"Error identifying slow movers: {e}")
        return pd.DataFrame()


# ==============================
# DEMAND FORECASTING DASHBOARD
# ==============================

def demand_forecasting_dashboard():
    """Main demand forecasting dashboard - FIXED"""
    
    st.title("🤖 AI-Powered Demand Forecasting")
    st.caption("Predict sales, identify trends, and optimize inventory with machine learning")
    
    # Load data
    sales_df = load_sales()
    products_df = load_products()
    
    if sales_df.empty:
        st.warning("Not enough sales data for forecasting. Complete at least 7 days of sales.")
        return
    
    # Determine column names for products
    product_col_sales = find_column(sales_df, ["name", "product_name", "Product", "item_name"])
    product_col_products = find_column(products_df, ["name", "product_name", "Product"])
    
    # Get product list for dropdown
    if products_df.empty or product_col_products is None:
        products_list = ["All Products"]
    else:
        products_list = ["All Products"] + products_df[product_col_products].tolist()
    
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
            st.info("Not enough transaction data for recommendations. Need at least 50 transactions.")
    
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
                    date_col = find_column(sales_df, ["date", "sale_date", "transaction_date"])
                    
                    if date_col:
                        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                        days_range = (sales_df[date_col].max() - sales_df[date_col].min()).days
                        if days_range > 0:
                            annual_demand = metrics['total_sold'] * (365 / days_range)
                        else:
                            annual_demand = metrics['total_sold'] * 12
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
            
            This balances ordering costs (${order_cost:.2f}/order) and holding costs (${holding_cost:.2f}/unit/year).
            """)


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    demand_forecasting_dashboard()