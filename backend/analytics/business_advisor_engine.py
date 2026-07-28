# backend/analytics/business_advisor_engine.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backend.core.db_adapter import load_sales, load_products, load_customers, to_float
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
    if df is None or df.empty:
        return None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


# ==============================
# HELPER: Get amount column
# ==============================
def get_amount_column(df):
    """Find amount column"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


# ==============================
# HELPER: Get receipt column
# ==============================
def get_receipt_column(df):
    """Find receipt number column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


# ==============================
# HELPER: Deduplicate sales for revenue calculation
# ==============================
def get_unduplicated_sales(sales_df):
    """Get unduplicated sales by receipt_no to avoid revenue duplication"""
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()
    
    sales_df = sales_df.copy()
    receipt_col = get_receipt_column(sales_df)
    
    # If we have receipt_no, deduplicate
    if receipt_col and receipt_col in sales_df.columns:
        return sales_df.drop_duplicates(subset=[receipt_col])
    
    # If no receipt_no, try to deduplicate by date and amount
    date_col = get_date_column(sales_df)
    amount_col = get_amount_column(sales_df)
    
    if date_col and amount_col and date_col in sales_df.columns and amount_col in sales_df.columns:
        try:
            return sales_df.drop_duplicates(subset=[date_col, amount_col])
        except:
            return sales_df
    
    return sales_df


# ==============================
# BUSINESS SCORECARD
# ==============================
def calculate_business_score():
    """Calculate overall business health score (0-100)"""
    
    sales_df = load_sales()
    products_df = load_products()
    customers_df = load_customers()
    expenses_df = load_expenses()
    
    scores = {
        "profitability": 0,
        "sales": 0,
        "inventory": 0,
        "customers": 0,
        "expenses": 0
    }
    
    # 1. Profitability Score (30 points)
    try:
        pl = profit_loss_account()
        if pl:
            net_profit = to_float(pl.get("net_profit", 0))
            if net_profit > 0:
                scores["profitability"] = min(30, (net_profit / 1000) * 10)
            else:
                scores["profitability"] = 0
    except Exception:
        scores["profitability"] = 0
    
    # 2. Sales Performance Score (25 points) - USING UNDUPLICATED REVENUE
    if not sales_df.empty:
        # Deduplicate sales by receipt_no
        sales_undup = get_unduplicated_sales(sales_df)
        
        amount_col = get_amount_column(sales_undup)
        if amount_col:
            total_sales = to_float(sales_undup[amount_col].sum())
            scores["sales"] = min(25, (total_sales / 5000) * 25)
    
    # 3. Inventory Health Score (20 points)
    if not products_df.empty:
        try:
            low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]])
            total_products = len(products_df)
            stock_health = (total_products - low_stock) / total_products * 100 if total_products > 0 else 0
            scores["inventory"] = (stock_health / 100) * 20
        except Exception:
            scores["inventory"] = 10
    
    # 4. Customer Health Score (15 points)
    if not customers_df.empty:
        try:
            if "total_orders" in customers_df.columns:
                repeat_customers = len(customers_df[customers_df["total_orders"] > 1])
                repeat_rate = (repeat_customers / len(customers_df)) * 100
                scores["customers"] = (repeat_rate / 100) * 15
            else:
                scores["customers"] = 7.5
        except Exception:
            scores["customers"] = 7.5
    
    # 5. Expense Control Score (10 points)
    if not expenses_df.empty and "amount" in expenses_df.columns:
        try:
            expense_date_col = get_date_column(expenses_df)
            if expense_date_col:
                expenses_df[expense_date_col] = pd.to_datetime(expenses_df[expense_date_col], errors="coerce")
                current_month = datetime.now().month
                current_year = datetime.now().year
                
                monthly_expenses = expenses_df[
                    (expenses_df[expense_date_col].dt.month == current_month) & 
                    (expenses_df[expense_date_col].dt.year == current_year)
                ]["amount"].sum()
                
                # Get monthly revenue using unduplicated sales
                if not sales_df.empty:
                    sales_undup = get_unduplicated_sales(sales_df)
                    sales_date_col = get_date_column(sales_undup)
                    amount_col = get_amount_column(sales_undup)
                    
                    if sales_date_col and amount_col:
                        sales_undup[sales_date_col] = pd.to_datetime(sales_undup[sales_date_col], errors="coerce")
                        revenue = sales_undup[
                            (sales_undup[sales_date_col].dt.month == current_month) & 
                            (sales_undup[sales_date_col].dt.year == current_year)
                        ][amount_col].sum() if amount_col in sales_undup.columns else 0
                    else:
                        revenue = 0
                else:
                    revenue = 0
                
                expense_ratio = (to_float(monthly_expenses) / to_float(revenue) * 100) if revenue > 0 else 100
                scores["expenses"] = max(0, 10 - (expense_ratio / 10))
            else:
                scores["expenses"] = 5
        except Exception:
            scores["expenses"] = 5
    
    total_score = sum(scores.values())
    total_score = min(100, max(0, total_score))
    
    # Determine rating
    if total_score >= 80:
        rating = "Excellent"
    elif total_score >= 60:
        rating = "Good"
    elif total_score >= 40:
        rating = "Fair"
    elif total_score >= 20:
        rating = "Poor"
    else:
        rating = "Critical"
    
    return {
        "total_score": round(total_score, 1),
        "rating": rating,
        "breakdown": scores
    }


# ==============================
# ANOMALY DETECTION - FIXED
# ==============================
def detect_anomalies():
    """Detect unusual patterns in business data using unduplicated revenue"""
    
    anomalies = []
    sales_df = load_sales()
    
    if sales_df.empty or len(sales_df) < 7:
        return anomalies
    
    # Deduplicate sales for accurate analysis
    sales_undup = get_unduplicated_sales(sales_df)
    
    if sales_undup.empty or len(sales_undup) < 7:
        return anomalies
    
    date_col = get_date_column(sales_undup)
    if date_col is None:
        return anomalies
    
    try:
        sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
        sales_undup = sales_undup.dropna(subset=[date_col])
        sales_undup["day"] = sales_undup[date_col].dt.date
        
        amount_col = get_amount_column(sales_undup)
        
        if amount_col:
            sales_undup[amount_col] = sales_undup[amount_col].apply(to_float)
            daily_sales = sales_undup.groupby("day")[amount_col].sum().reset_index()
            daily_sales.columns = ["date", "sales"]
            
            if len(daily_sales) >= 7:
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
                                "message": f"Unusual sales spike detected: {abs(z_score * 100):.0f}% above average",
                                "value": to_float(latest["sales"]),
                                "expected": to_float(latest["ma_7"])
                            })
                        else:
                            anomalies.append({
                                "type": "SALES_DROP",
                                "severity": "HIGH" if abs(z_score) > 3 else "MEDIUM",
                                "message": f"Unusual sales drop detected: {abs(z_score * 100):.0f}% below average",
                                "value": to_float(latest["sales"]),
                                "expected": to_float(latest["ma_7"])
                            })
    except Exception:
        pass
    
    return anomalies


# ==============================
# INTELLIGENT RECOMMENDATIONS - FIXED
# ==============================
def get_intelligent_recommendations():
    """Generate AI-powered business recommendations using unduplicated data"""
    
    recommendations = []
    sales_df = load_sales()
    products_df = load_products()
    customers_df = load_customers()
    expenses_df = load_expenses()
    score = calculate_business_score()
    
    # Priority levels
    priorities = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}
    
    # Get unduplicated sales
    sales_undup = get_unduplicated_sales(sales_df)
    sales_date_col = get_date_column(sales_undup)
    amount_col = get_amount_column(sales_undup)
    
    # 1. Stock-related recommendations
    if not products_df.empty:
        try:
            low_stock = products_df[products_df["stock"] <= products_df["reorder_level"]]
            out_of_stock = products_df[products_df["stock"] == 0]
            
            if len(out_of_stock) > 0:
                names = out_of_stock["name"].head(3).tolist()
                name_str = ", ".join(names) + ("..." if len(out_of_stock) > 3 else "")
                recommendations.append({
                    "category": "Inventory",
                    "priority": "Critical",
                    "title": f"{len(out_of_stock)} Products Out of Stock",
                    "description": f"The following products are out of stock: {name_str}",
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
        except Exception:
            pass
    
    # 2. Sales-related recommendations - USING UNDUPLICATED REVENUE
    if not sales_undup.empty and sales_date_col and amount_col:
        try:
            sales_undup[sales_date_col] = pd.to_datetime(sales_undup[sales_date_col], errors="coerce")
            sales_undup = sales_undup.dropna(subset=[sales_date_col])
            
            last_30_days = sales_undup[sales_undup[sales_date_col] >= (datetime.now() - timedelta(days=30))]
            previous_30_days = sales_undup[(sales_undup[sales_date_col] < (datetime.now() - timedelta(days=30))) & 
                                             (sales_undup[sales_date_col] >= (datetime.now() - timedelta(days=60)))]
            
            current_sales = to_float(last_30_days[amount_col].sum()) if not last_30_days.empty else 0
            previous_sales = to_float(previous_30_days[amount_col].sum()) if not previous_30_days.empty else 0
            
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
        except Exception:
            pass
    
    # 3. Customer-related recommendations
    if not customers_df.empty:
        try:
            if "last_purchase_date" in customers_df.columns:
                inactive = customers_df[customers_df["last_purchase_date"].isna()]
                if len(inactive) > len(customers_df) * 0.5:
                    recommendations.append({
                        "category": "Customers",
                        "priority": "Medium",
                        "title": "High Customer Inactivity",
                        "description": f"{len(inactive)} customers have not made repeat purchases.",
                        "action": "Launch a re-engagement campaign with special offers.",
                        "potential_impact": "Could recover up to 30% of inactive customers."
                    })
        except Exception:
            pass
    
    # 4. Expense-related recommendations
    expense_date_col = get_date_column(expenses_df)
    if not expenses_df.empty and "amount" in expenses_df.columns and expense_date_col:
        try:
            expenses_df[expense_date_col] = pd.to_datetime(expenses_df[expense_date_col], errors="coerce")
            monthly_expenses = expenses_df[expenses_df[expense_date_col].dt.month == datetime.now().month]["amount"].sum()
            
            revenue = 0
            if not sales_undup.empty and amount_col and sales_date_col:
                sales_undup[sales_date_col] = pd.to_datetime(sales_undup[sales_date_col], errors="coerce")
                revenue = sales_undup[sales_undup[sales_date_col].dt.month == datetime.now().month][amount_col].sum() if amount_col in sales_undup.columns else 0
            
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
        except Exception:
            pass
    
    # 5. Profitability recommendations
    try:
        pl = profit_loss_account()
        if pl:
            net_profit = to_float(pl.get("net_profit", 0))
            net_margin = to_float(pl.get("net_margin", 0))
            
            if net_profit < 0:
                recommendations.append({
                    "category": "Profitability",
                    "priority": "Critical",
                    "title": "Business Operating at a Loss",
                    "description": f"Net loss of ${abs(net_profit):.2f} for the period.",
                    "action": "Immediate review of pricing, costs, and sales strategy required.",
                    "potential_impact": "Essential for business survival and growth."
                })
            elif net_margin < 10 and net_margin > 0:
                recommendations.append({
                    "category": "Profitability",
                    "priority": "Medium",
                    "title": "Low Profit Margin",
                    "description": f"Net profit margin is only {net_margin:.1f}%.",
                    "action": "Consider price optimization or cost reduction strategies.",
                    "potential_impact": "Could increase profitability significantly."
                })
    except Exception:
        pass
    
    # Sort by priority
    recommendations.sort(key=lambda x: priorities.get(x.get("priority", "Low"), 99))
    
    return recommendations


# ==============================
# SALES FORECAST (AI) - FIXED
# ==============================
def ai_sales_forecast(days=30):
    """AI-powered sales forecast using simple linear regression with unduplicated data"""
    
    sales_df = load_sales()
    
    if sales_df.empty or len(sales_df) < 14:
        return None
    
    # Deduplicate sales
    sales_undup = get_unduplicated_sales(sales_df)
    
    if sales_undup.empty or len(sales_undup) < 7:
        return None
    
    date_col = get_date_column(sales_undup)
    if date_col is None:
        return None
    
    try:
        sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
        sales_undup = sales_undup.dropna(subset=[date_col])
        
        amount_col = get_amount_column(sales_undup)
        if amount_col is None:
            return None
        
        sales_undup[amount_col] = sales_undup[amount_col].apply(to_float)
        daily_sales = sales_undup.groupby(sales_undup[date_col].dt.date)[amount_col].sum().reset_index()
        daily_sales.columns = ["date", "sales"]
        
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
    except Exception:
        return None


# ==============================
# SEASONAL TREND ANALYSIS - FIXED
# ==============================
def seasonal_trend_analysis():
    """Identify seasonal patterns in sales using unduplicated data"""
    
    sales_df = load_sales()
    
    if sales_df.empty:
        return None
    
    # Deduplicate sales
    sales_undup = get_unduplicated_sales(sales_df)
    
    if sales_undup.empty:
        return None
    
    date_col = get_date_column(sales_undup)
    if date_col is None:
        return None
    
    try:
        sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
        sales_undup = sales_undup.dropna(subset=[date_col])
        sales_undup["month"] = sales_undup[date_col].dt.month
        sales_undup["day_of_week"] = sales_undup[date_col].dt.day_name()
        
        amount_col = get_amount_column(sales_undup)
        if amount_col is None:
            return None
        
        sales_undup[amount_col] = sales_undup[amount_col].apply(to_float)
        
        # Monthly seasonality
        monthly_sales = sales_undup.groupby("month")[amount_col].sum().reset_index()
        
        # Day of week patterns
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_sales = sales_undup.groupby("day_of_week")[amount_col].sum().reset_index()
        
        if not dow_sales.empty:
            dow_sales["day_of_week"] = pd.Categorical(dow_sales["day_of_week"], categories=dow_order, ordered=True)
            dow_sales = dow_sales.sort_values("day_of_week")
        
        # Identify peak periods
        peak_month = monthly_sales.loc[monthly_sales[amount_col].idxmax(), "month"] if not monthly_sales.empty else None
        peak_day = dow_sales.loc[dow_sales[amount_col].idxmax(), "day_of_week"] if not dow_sales.empty else None
        slow_day = dow_sales.loc[dow_sales[amount_col].idxmin(), "day_of_week"] if not dow_sales.empty else None
        
        return {
            "peak_month": int(peak_month) if peak_month is not None else None,
            "peak_day": peak_day,
            "slow_day": slow_day,
            "monthly_pattern": monthly_sales.to_dict('records') if not monthly_sales.empty else [],
            "weekly_pattern": dow_sales.to_dict('records') if not dow_sales.empty else []
        }
    except Exception:
        return None


# ==============================
# ALERT GENERATION - FIXED
# ==============================
def generate_alerts():
    """Generate critical business alerts using unduplicated data"""
    
    alerts = []
    products_df = load_products()
    sales_df = load_sales()
    score = calculate_business_score()
    anomalies = detect_anomalies()
    
    # Critical stock alerts
    if not products_df.empty:
        try:
            out_of_stock = products_df[products_df["stock"] == 0]
            if len(out_of_stock) > 0:
                names = out_of_stock["name"].head(3).tolist()
                name_str = ", ".join(names) + ("..." if len(out_of_stock) > 3 else "")
                alerts.append({
                    "level": "critical",
                    "title": f"{len(out_of_stock)} Products Out of Stock",
                    "message": f"Immediate action required: {name_str}",
                    "timestamp": datetime.now()
                })
        except Exception:
            pass
    
    # Business health alerts
    try:
        total_score = score.get("total_score", 0)
        if total_score < 40:
            alerts.append({
                "level": "critical",
                "title": f"Business Health Critical ({total_score}/100)",
                "message": "Urgent attention needed across multiple business areas.",
                "timestamp": datetime.now()
            })
        elif total_score < 60:
            alerts.append({
                "level": "warning",
                "title": f"Business Health Warning ({total_score}/100)",
                "message": "Several areas need improvement to reach good standing.",
                "timestamp": datetime.now()
            })
    except Exception:
        pass
    
    # Sales alerts - check if no sales today using unduplicated data
    if not sales_df.empty:
        sales_undup = get_unduplicated_sales(sales_df)
        date_col = get_date_column(sales_undup)
        
        if date_col:
            try:
                sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
                today = datetime.now().date()
                today_sales = sales_undup[sales_undup[date_col].dt.date == today]
                
                if today_sales.empty:
                    alerts.append({
                        "level": "warning",
                        "title": "No Sales Recorded Today",
                        "message": "No transactions have been recorded for today.",
                        "timestamp": datetime.now()
                    })
            except Exception:
                pass
    
    # Anomaly alerts
    for anomaly in anomalies:
        severity = anomaly.get("severity", "MEDIUM")
        alerts.append({
            "level": "warning" if severity == "MEDIUM" else "critical",
            "title": f"{anomaly.get('type', 'Anomaly').replace('_', ' ')} Detected",
            "message": anomaly.get("message", "Anomaly detected"),
            "timestamp": datetime.now()
        })
    
    return alerts