# backend/analytics/business_advisor_engine.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backend.core.db_adapter import load_sales, load_products, load_customers
from backend.modules.expenses import load_expenses
from backend.analytics.pl_engine import profit_loss_account, get_financial_ratios


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
# HELPER: Get date column
# ==============================
def get_date_column(df):
    """Determine which date column exists in the dataframe"""
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


# ==============================
# HELPER FUNCTION FOR SAFE DATE CONVERSION
# ==============================
def safe_datetime(series):
    """Safely convert series to datetime"""
    return pd.to_datetime(series, errors="coerce")


def safe_date_filter(df, date_column="date"):
    """Ensure date column is properly formatted"""
    if df is None or df.empty:
        return df
    
    # Find the actual date column
    actual_date_col = get_date_column(df)
    if actual_date_col is None:
        return df
    
    df[actual_date_col] = pd.to_datetime(df[actual_date_col], errors="coerce")
    
    return df


# ==============================
# BUSINESS SCORECARD (FIXED)
# ==============================
def calculate_business_score():
    """Calculate overall business health score (0-100)"""
    
    sales_df = load_sales()
    products_df = load_products()
    customers_df = load_customers()
    expenses_df = load_expenses()
    
    # Get date columns
    sales_date_col = get_date_column(sales_df)
    expenses_date_col = get_date_column(expenses_df)
    
    # Ensure date columns are properly formatted
    if not sales_df.empty and sales_date_col:
        sales_df[sales_date_col] = pd.to_datetime(sales_df[sales_date_col], errors="coerce")
    
    if not expenses_df.empty and expenses_date_col:
        expenses_df[expenses_date_col] = pd.to_datetime(expenses_df[expenses_date_col], errors="coerce")
    
    scores = {}
    
    # 1. Profitability Score (30 points)
    pl = profit_loss_account()
    net_profit = to_float(pl.get("net_profit", 0))
    if pl and net_profit > 0:
        profit_score = min(30, (net_profit / 1000) * 10) if net_profit > 0 else 0
    else:
        profit_score = 0
    scores["profitability"] = min(30, profit_score)
    
    # 2. Sales Performance Score (25 points)
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    if not sales_df.empty and total_col:
        total_sales = to_float(sales_df[total_col].sum())
        sales_score = min(25, (total_sales / 5000) * 25)
    else:
        sales_score = 0
    scores["sales"] = min(25, sales_score)
    
    # 3. Inventory Health Score (20 points)
    if not products_df.empty:
        low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]])
        total_products = len(products_df)
        stock_health = (total_products - low_stock) / total_products * 100 if total_products > 0 else 0
        inventory_score = (stock_health / 100) * 20
    else:
        inventory_score = 0
    scores["inventory"] = min(20, inventory_score)
    
    # 4. Customer Health Score (15 points)
    if not customers_df.empty:
        repeat_rate = len(customers_df[customers_df["total_orders"] > 1]) / len(customers_df) * 100 if len(customers_df) > 0 else 0
        customer_score = (repeat_rate / 100) * 15
    else:
        customer_score = 0
    scores["customers"] = min(15, customer_score)
    
    # 5. Expense Control Score (10 points)
    if not expenses_df.empty and expenses_date_col and "amount" in expenses_df.columns:
        # Filter for current month
        current_month = datetime.now().month
        current_year = datetime.now().year
        expenses_df["month"] = expenses_df[expenses_date_col].dt.month
        expenses_df["year"] = expenses_df[expenses_date_col].dt.year
        
        monthly_expenses = expenses_df[(expenses_df["month"] == current_month) & (expenses_df["year"] == current_year)]["amount"].sum()
        
        if not sales_df.empty and total_col:
            sales_df["month"] = sales_df[sales_date_col].dt.month
            sales_df["year"] = sales_df[sales_date_col].dt.year
            revenue = sales_df[(sales_df["month"] == current_month) & (sales_df["year"] == current_year)][total_col].sum()
        else:
            revenue = 1
        
        expense_ratio = (to_float(monthly_expenses) / to_float(revenue) * 100) if revenue > 0 else 100
        expense_score = max(0, 10 - (expense_ratio / 10))
    else:
        expense_score = 5
    scores["expenses"] = min(10, expense_score)
    
    total_score = sum(scores.values())
    
    # Determine rating
    if total_score >= 80:
        rating = "Excellent"
        color = "green"
        emoji = "🏆"
    elif total_score >= 60:
        rating = "Good"
        color = "blue"
        emoji = "👍"
    elif total_score >= 40:
        rating = "Fair"
        color = "yellow"
        emoji = "⚠️"
    elif total_score >= 20:
        rating = "Poor"
        color = "orange"
        emoji = "❌"
    else:
        rating = "Critical"
        color = "red"
        emoji = "🚨"
    
    return {
        "total_score": round(total_score, 1),
        "rating": rating,
        "color": color,
        "emoji": emoji,
        "breakdown": scores
    }


# ==============================
# ANOMALY DETECTION (FIXED)
# ==============================
def detect_anomalies():
    """Detect unusual patterns in business data"""
    
    anomalies = []
    sales_df = load_sales()
    
    if sales_df.empty or len(sales_df) < 7:
        return anomalies
    
    # Get date column
    date_col = get_date_column(sales_df)
    if date_col is None:
        return anomalies
    
    # Safely convert date
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    sales_df["day"] = sales_df[date_col].dt.date
    
    # Daily sales trend
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    if total_col:
        sales_df[total_col] = to_float(sales_df[total_col])
        daily_sales = sales_df.groupby("day")[total_col].sum().reset_index()
        daily_sales.columns = ["date", "sales"]
        
        if len(daily_sales) >= 7:
            # Calculate moving average and std deviation
            daily_sales["ma_7"] = daily_sales["sales"].rolling(window=7, min_periods=1).mean()
            daily_sales["std_7"] = daily_sales["sales"].rolling(window=7, min_periods=1).std()
            
            latest = daily_sales.iloc[-1]
            
            if latest["std_7"] > 0:
                z_score = (latest["sales"] - latest["ma_7"]) / latest["std_7"]
                
                if abs(z_score) > 2:
                    if z_score > 0:
                        anomalies.append({
                            "type": "SALES_SPIKE",
                            "severity": "HIGH" if z_score > 3 else "MEDIUM",
                            "message": f"Unusual sales spike detected: {latest['sales']:.0f}% above average",
                            "value": to_float(latest["sales"]),
                            "expected": to_float(latest["ma_7"])
                        })
                    else:
                        anomalies.append({
                            "type": "SALES_DROP",
                            "severity": "HIGH" if abs(z_score) > 3 else "MEDIUM",
                            "message": f"Unusual sales drop detected: {abs(z_score):.0f}% below average",
                            "value": to_float(latest["sales"]),
                            "expected": to_float(latest["ma_7"])
                        })
    
    return anomalies


# ==============================
# INTELLIGENT RECOMMENDATIONS
# ==============================
def get_intelligent_recommendations():
    """Generate AI-powered business recommendations"""
    
    recommendations = []
    sales_df = load_sales()
    products_df = load_products()
    customers_df = load_customers()
    expenses_df = load_expenses()
    score = calculate_business_score()
    
    # Priority levels
    priorities = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
    
    # Get date columns
    sales_date_col = get_date_column(sales_df)
    
    # 1. Stock-related recommendations
    if not products_df.empty:
        low_stock = products_df[products_df["stock"] <= products_df["reorder_level"]]
        out_of_stock = products_df[products_df["stock"] == 0]
        
        if len(out_of_stock) > 0:
            recommendations.append({
                "category": "Inventory",
                "priority": "Critical",
                "title": f"{len(out_of_stock)} Products Out of Stock",
                "description": f"The following products are out of stock: {', '.join(out_of_stock['name'].head(3).tolist())}...",
                "action": "Place urgent purchase orders for these items.",
                "potential_impact": "Prevents lost sales and customer dissatisfaction."
            })
        elif len(low_stock) > 0:
            recommendations.append({
                "category": "Inventory",
                "priority": "High",
                "title": f"{len(low_stock)} Products Running Low",
                "description": "Several products are below reorder level.",
                "action": "Review stock levels and place purchase orders.",
                "potential_impact": "Prevents stockouts and ensures availability."
            })
    
    # 2. Sales-related recommendations
    if not sales_df.empty and sales_date_col:
        sales_df[sales_date_col] = pd.to_datetime(sales_df[sales_date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[sales_date_col])
        
        last_30_days = sales_df[sales_df[sales_date_col] >= (datetime.now() - timedelta(days=30))]
        previous_30_days = sales_df[(sales_df[sales_date_col] < (datetime.now() - timedelta(days=30))) & 
                                     (sales_df[sales_date_col] >= (datetime.now() - timedelta(days=60)))]
        
        total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
        if total_col:
            current_sales = to_float(last_30_days[total_col].sum()) if not last_30_days.empty else 0
            previous_sales = to_float(previous_30_days[total_col].sum()) if not previous_30_days.empty else 0
            
            if previous_sales > 0:
                growth = ((current_sales - previous_sales) / previous_sales) * 100
                
                if growth < -10:
                    recommendations.append({
                        "category": "Sales",
                        "priority": "High",
                        "title": "Sales Declining",
                        "description": f"Sales decreased by {abs(growth):.0f}% compared to previous period.",
                        "action": "Review pricing, run promotions, or increase marketing efforts.",
                        "potential_impact": "Could recover lost revenue and improve cash flow."
                    })
                elif growth > 20:
                    recommendations.append({
                        "category": "Sales",
                        "priority": "Low",
                        "title": "Strong Sales Growth",
                        "description": f"Sales increased by {growth:.0f}% - excellent performance!",
                        "action": "Analyze what's working and consider expanding successful products.",
                        "potential_impact": "Capitalize on momentum for further growth."
                    })
    
    # 3. Customer-related recommendations
    if not customers_df.empty:
        inactive = customers_df[customers_df["last_purchase_date"].isna()] if "last_purchase_date" in customers_df.columns else pd.DataFrame()
        if len(inactive) > len(customers_df) * 0.5:
            recommendations.append({
                "category": "Customers",
                "priority": "Medium",
                "title": "High Customer Inactivity",
                "description": f"{len(inactive)} customers have not made repeat purchases.",
                "action": "Launch a re-engagement campaign with special offers.",
                "potential_impact": "Could recover up to 30% of inactive customers."
            })
    
    # 4. Expense-related recommendations
    expense_date_col = get_date_column(expenses_df)
    if not expenses_df.empty and "amount" in expenses_df.columns and expense_date_col:
        expenses_df[expense_date_col] = pd.to_datetime(expenses_df[expense_date_col], errors="coerce")
        monthly_expenses = expenses_df[expenses_df[expense_date_col].dt.month == datetime.now().month]["amount"].sum()
        
        total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
        if not sales_df.empty and total_col and sales_date_col:
            sales_df[sales_date_col] = pd.to_datetime(sales_df[sales_date_col], errors="coerce")
            revenue = sales_df[sales_df[sales_date_col].dt.month == datetime.now().month][total_col].sum()
        else:
            revenue = 1
        
        expense_ratio = (to_float(monthly_expenses) / to_float(revenue) * 100) if revenue > 0 else 100
        
        if expense_ratio > 40:
            recommendations.append({
                "category": "Expenses",
                "priority": "High",
                "title": "High Expense Ratio",
                "description": f"Expenses are {expense_ratio:.0f}% of revenue - above recommended 30-40%.",
                "action": "Review all expenses and identify cost-cutting opportunities.",
                "potential_impact": "Could increase net profit by 10-20%."
            })
    
    # 5. Profitability recommendations
    pl = profit_loss_account()
    net_profit = to_float(pl.get("net_profit", 0))
    net_margin = to_float(pl.get("net_margin", 0))
    
    if pl and net_profit < 0:
        recommendations.append({
            "category": "Profitability",
            "priority": "Critical",
            "title": "Business Operating at a Loss",
            "description": f"Net loss of ${abs(net_profit):.2f} for the period.",
            "action": "Immediate review of pricing, costs, and sales strategy required.",
            "potential_impact": "Essential for business survival and growth."
        })
    elif pl and net_margin < 10:
        recommendations.append({
            "category": "Profitability",
            "priority": "Medium",
            "title": "Low Profit Margin",
            "description": f"Net profit margin is only {net_margin:.1f}%.",
            "action": "Consider price optimization or cost reduction strategies.",
            "potential_impact": "Could increase profitability significantly."
        })
    
    # Sort by priority
    recommendations.sort(key=lambda x: priorities.get(x["priority"], 99))
    
    return recommendations


# ==============================
# SALES FORECAST (AI)
# ==============================
def ai_sales_forecast(days=30):
    """AI-powered sales forecast using simple linear regression"""
    
    sales_df = load_sales()
    
    if sales_df.empty or len(sales_df) < 14:
        return None
    
    date_col = get_date_column(sales_df)
    if date_col is None:
        return None
    
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    if total_col:
        sales_df[total_col] = to_float(sales_df[total_col])
        daily_sales = sales_df.groupby(sales_df[date_col].dt.date)[total_col].sum().reset_index()
        daily_sales.columns = ["date", "sales"]
    else:
        return None
    
    if len(daily_sales) < 7:
        return None
    
    # Simple linear regression
    x = np.arange(len(daily_sales))
    y = daily_sales["sales"].values
    
    # Calculate trend
    z = np.polyfit(x, y, 1)
    trend = np.poly1d(z)
    
    # Forecast future days
    forecast_dates = [(datetime.now().date() + timedelta(days=i)) for i in range(1, days + 1)]
    forecast_sales = [trend(len(daily_sales) + i) for i in range(1, days + 1)]
    
    # Ensure no negative forecasts
    forecast_sales = [max(0, s) for s in forecast_sales]
    
    # Calculate confidence intervals
    residuals = y - trend(x)
    std_residual = np.std(residuals)
    
    forecast_data = []
    for i, (date, sales) in enumerate(zip(forecast_dates, forecast_sales)):
        forecast_data.append({
            "date": date,
            "forecast_sales": sales,
            "lower_bound": max(0, sales - 1.96 * std_residual),
            "upper_bound": sales + 1.96 * std_residual
        })
    
    return {
        "forecast": forecast_data,
        "trend_slope": z[0],
        "trend_direction": "increasing" if z[0] > 0 else "decreasing",
        "total_forecast": sum(forecast_sales),
        "avg_daily_forecast": sum(forecast_sales) / days
    }


# ==============================
# SEASONAL TREND ANALYSIS (FIXED)
# ==============================
def seasonal_trend_analysis():
    """Identify seasonal patterns in sales"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return None
    
    date_col = get_date_column(sales_df)
    if date_col is None:
        return None
    
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    sales_df["month"] = sales_df[date_col].dt.month
    sales_df["day_of_week"] = sales_df[date_col].dt.day_name()
    
    # Monthly seasonality
    total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
    if total_col:
        sales_df[total_col] = to_float(sales_df[total_col])
        monthly_sales = sales_df.groupby("month")[total_col].sum().reset_index()
    else:
        monthly_sales = pd.DataFrame()
    
    # Day of week patterns
    dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_sales = sales_df.groupby("day_of_week")[total_col].sum().reset_index() if total_col and total_col in sales_df.columns else pd.DataFrame()
    
    if not dow_sales.empty:
        dow_sales["day_of_week"] = pd.Categorical(dow_sales["day_of_week"], categories=dow_order, ordered=True)
        dow_sales = dow_sales.sort_values("day_of_week")
    
    # Identify peak periods
    peak_month = monthly_sales.loc[monthly_sales[total_col].idxmax(), "month"] if not monthly_sales.empty else None
    peak_day = dow_sales.loc[dow_sales[total_col].idxmax(), "day_of_week"] if not dow_sales.empty else None
    slow_day = dow_sales.loc[dow_sales[total_col].idxmin(), "day_of_week"] if not dow_sales.empty else None
    
    return {
        "peak_month": peak_month,
        "peak_day": peak_day,
        "slow_day": slow_day,
        "monthly_pattern": monthly_sales.to_dict('records') if not monthly_sales.empty else [],
        "weekly_pattern": dow_sales.to_dict('records') if not dow_sales.empty else []
    }


# ==============================
# ALERT GENERATION (FIXED)
# ==============================
def generate_alerts():
    """Generate critical business alerts"""
    
    alerts = []
    products_df = load_products()
    score = calculate_business_score()
    anomalies = detect_anomalies()
    
    # Critical stock alerts
    if not products_df.empty:
        out_of_stock = products_df[products_df["stock"] == 0]
        if len(out_of_stock) > 0:
            alerts.append({
                "level": "critical",
                "title": f"🚨 {len(out_of_stock)} Products Out of Stock",
                "message": f"Immediate action required: {', '.join(out_of_stock['name'].head(3).tolist())}...",
                "timestamp": datetime.now()
            })
    
    # Business health alerts
    if score["total_score"] < 40:
        alerts.append({
            "level": "critical",
            "title": f"🚨 Business Health Critical ({score['total_score']}/100)",
            "message": "Urgent attention needed across multiple business areas.",
            "timestamp": datetime.now()
        })
    elif score["total_score"] < 60:
        alerts.append({
            "level": "warning",
            "title": f"⚠️ Business Health Warning ({score['total_score']}/100)",
            "message": "Several areas need improvement to reach good standing.",
            "timestamp": datetime.now()
        })
    
    # Anomaly alerts
    for anomaly in anomalies:
        alerts.append({
            "level": "warning" if anomaly["severity"] == "MEDIUM" else "critical",
            "title": f"📊 {anomaly['type'].replace('_', ' ')} Detected",
            "message": anomaly["message"],
            "timestamp": datetime.now()
        })
    
    return alerts