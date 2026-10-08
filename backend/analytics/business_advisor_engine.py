# backend/analytics/business_advisor_engine.py
# Branch-aware business advisor engine.
#
# Branch scoping (identical convention to pl_engine / reports_engine):
#   branch_id = None            -> session branch
#   branch_id = "HO"/"NAT"/..   -> single branch
#   branch_id = "__ALL__"       -> aggregate across all branches (owner only)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_customers,
    load_branches,
    to_float,
)
from backend.modules.expenses import load_expenses
from backend.analytics.pl_engine import profit_loss_account, get_financial_ratios


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        import streamlit as st
        return (
            st.session_state.get("user_branch")
            or st.session_state.get("current_branch_code")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_all_branches(branch_id):
    return isinstance(branch_id, str) and branch_id.upper() == ALL_BRANCHES


def _load_scoped(loader, branch_id, **kwargs):
    """Call loader once per branch when __ALL__, else once."""
    if _is_all_branches(branch_id):
        try:
            bdf = load_branches()
        except Exception:
            bdf = pd.DataFrame()
        if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
            try:
                return loader(**kwargs)
            except Exception:
                return pd.DataFrame()
        frames = []
        for bid in bdf["branch_id"].astype(str).tolist():
            try:
                df = loader(branch_id=bid, **kwargs)
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    try:
        return loader(branch_id=branch_id, **kwargs)
    except TypeError:
        try:
            return loader(**kwargs)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ==============================
# HELPERS
# ==============================
def to_float(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_date_column(df):
    if df is None or df.empty:
        return None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_customer_column(df):
    if df is None or df.empty:
        return None
    for col in df.columns:
        col_lower = str(col).lower()
        if any(term in col_lower for term in ['customer', 'cust', 'client', 'buyer', 'email', 'phone', 'contact']):
            return col
    for col in ["customer_id", "customer", "customer_email", "email", "phone", "contact", "client_id", "client"]:
        if col in df.columns:
            return col
    return None


def get_unduplicated_sales(sales_df):
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()
    sales_df = sales_df.copy()
    receipt_col = get_receipt_column(sales_df)
    if receipt_col and receipt_col in sales_df.columns:
        return sales_df.drop_duplicates(subset=[receipt_col])
    date_col = get_date_column(sales_df)
    amount_col = get_amount_column(sales_df)
    if date_col and amount_col and date_col in sales_df.columns and amount_col in sales_df.columns:
        try:
            return sales_df.drop_duplicates(subset=[date_col, amount_col])
        except Exception:
            return sales_df
    return sales_df


# ==============================
# CUSTOMER ANALYTICS FROM SALES
# ==============================
def get_customer_analytics_from_sales(sales_df=None, branch_id=None):
    """Extract customer analytics from sales data — branch-scoped."""
    branch_id = _resolve_branch(branch_id)

    if sales_df is None:
        sales_df = _load_scoped(load_sales, branch_id)

    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    sales_undup = get_unduplicated_sales(sales_df)
    if sales_undup.empty:
        return pd.DataFrame()

    customer_col = get_customer_column(sales_undup)

    # Fallback: derive a customer proxy
    if customer_col is None or customer_col not in sales_undup.columns:
        receipt_col = get_receipt_column(sales_undup)
        if receipt_col and receipt_col in sales_undup.columns:
            customer_col = receipt_col
        else:
            date_col = get_date_column(sales_undup)
            amount_col = get_amount_column(sales_undup)
            if date_col and amount_col:
                sales_undup = sales_undup.copy()
                sales_undup['_customer_proxy'] = (
                    sales_undup[date_col].astype(str) + '_' + sales_undup[amount_col].astype(str)
                )
                customer_col = '_customer_proxy'
            else:
                return pd.DataFrame()

    amount_col = get_amount_column(sales_undup)
    if amount_col is None:
        if "final_total" in sales_undup.columns:
            amount_col = "final_total"
        else:
            return pd.DataFrame()

    date_col = get_date_column(sales_undup)

    sales_undup = sales_undup.copy()
    sales_undup[amount_col] = sales_undup[amount_col].apply(to_float)

    try:
        customer_data = sales_undup.groupby(customer_col).agg({
            amount_col: ['sum', 'count', 'mean'],
        }).reset_index()
        customer_data.columns = ['customer_id', 'total_spent', 'total_orders', 'avg_order_value']

        if date_col and date_col in sales_undup.columns:
            sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors='coerce')
            last_purchase = sales_undup.groupby(customer_col)[date_col].max().reset_index()
            last_purchase.columns = ['customer_id', 'last_purchase_date']
            customer_data = customer_data.merge(last_purchase, on='customer_id', how='left')
            customer_data['days_since_last_purchase'] = (
                datetime.now() - customer_data['last_purchase_date']
            ).dt.days

        def categorize_customer(row):
            if row['total_orders'] >= 5:
                return 'VIP'
            elif row['total_orders'] >= 2:
                return 'Regular'
            return 'New'

        customer_data['segment'] = customer_data.apply(categorize_customer, axis=1)
        return customer_data
    except Exception as e:
        print(f"[business_advisor_engine] customer analytics error: {e}")
        return pd.DataFrame()


# ==============================
# BUSINESS SCORECARD
# ==============================
def calculate_business_score(branch_id=None):
    """Overall business health score — branch-scoped."""
    branch_id = _resolve_branch(branch_id)

    sales_df = _load_scoped(load_sales, branch_id)
    products_df = _load_scoped(load_products, branch_id)
    customers_df = _load_scoped(load_customers, branch_id)

    try:
        expenses_df = load_expenses(branch_id=branch_id) if not _is_all_branches(branch_id) \
            else _load_scoped(load_expenses, branch_id)
    except TypeError:
        try:
            expenses_df = load_expenses()
        except Exception:
            expenses_df = pd.DataFrame()
    except Exception:
        expenses_df = pd.DataFrame()

    scores = {"profitability": 0, "sales": 0, "inventory": 0, "customers": 0, "expenses": 0}

    # 1) Profitability (30 pts) — pl_engine is now branch-aware
    try:
        pl = profit_loss_account(branch_id=branch_id)
        if pl:
            net_profit = to_float(pl.get("net_profit", 0))
            if net_profit > 0:
                scores["profitability"] = min(30, (net_profit / 1000) * 10)
    except Exception:
        scores["profitability"] = 0

    # 2) Sales (25 pts) — unduplicated
    if sales_df is not None and not sales_df.empty:
        sales_undup = get_unduplicated_sales(sales_df)
        amount_col = get_amount_column(sales_undup)
        if amount_col:
            total_sales = to_float(sales_undup[amount_col].sum())
            scores["sales"] = min(25, (total_sales / 5000) * 25)

    # 3) Inventory (20 pts)
    if products_df is not None and not products_df.empty:
        try:
            if "reorder_level" in products_df.columns and "stock" in products_df.columns:
                low_stock = len(products_df[products_df["stock"] <= products_df["reorder_level"]])
            elif "stock" in products_df.columns:
                low_stock = len(products_df[products_df["stock"] <= 5])
            else:
                low_stock = 0
            total_products = len(products_df)
            stock_health = (total_products - low_stock) / total_products * 100 if total_products > 0 else 0
            scores["inventory"] = (stock_health / 100) * 20
        except Exception:
            scores["inventory"] = 10

    # 4) Customers (15 pts)
    try:
        customer_analytics = get_customer_analytics_from_sales(sales_df, branch_id)
        if not customer_analytics.empty and len(customer_analytics) > 1:
            repeat_customers = len(customer_analytics[customer_analytics['total_orders'] > 1])
            total_customers = len(customer_analytics)
            repeat_rate = (repeat_customers / total_customers) * 100 if total_customers > 0 else 0
            scores["customers"] = (repeat_rate / 100) * 15
        elif customers_df is not None and not customers_df.empty:
            repeat_customers = (
                len(customers_df[customers_df["total_orders"] > 1])
                if "total_orders" in customers_df.columns else 0
            )
            total_customers = len(customers_df)
            repeat_rate = (repeat_customers / total_customers) * 100 if total_customers > 0 else 0
            scores["customers"] = (repeat_rate / 100) * 15
        else:
            scores["customers"] = 7.5
    except Exception:
        scores["customers"] = 7.5

    # 5) Expense control (10 pts)
    if expenses_df is not None and not expenses_df.empty and "amount" in expenses_df.columns:
        try:
            expense_date_col = get_date_column(expenses_df)
            if expense_date_col:
                expenses_df = expenses_df.copy()
                expenses_df[expense_date_col] = pd.to_datetime(expenses_df[expense_date_col], errors="coerce")
                current_month = datetime.now().month
                current_year = datetime.now().year
                monthly_expenses = expenses_df[
                    (expenses_df[expense_date_col].dt.month == current_month) &
                    (expenses_df[expense_date_col].dt.year == current_year)
                ]["amount"].sum()

                revenue = 0
                if sales_df is not None and not sales_df.empty:
                    sales_undup = get_unduplicated_sales(sales_df)
                    sales_date_col = get_date_column(sales_undup)
                    amount_col = get_amount_column(sales_undup)
                    if sales_date_col and amount_col:
                        sales_undup = sales_undup.copy()
                        sales_undup[sales_date_col] = pd.to_datetime(sales_undup[sales_date_col], errors="coerce")
                        revenue = sales_undup[
                            (sales_undup[sales_date_col].dt.month == current_month) &
                            (sales_undup[sales_date_col].dt.year == current_year)
                        ][amount_col].sum()

                expense_ratio = (to_float(monthly_expenses) / to_float(revenue) * 100) if revenue > 0 else 100
                scores["expenses"] = max(0, 10 - (expense_ratio / 10))
            else:
                scores["expenses"] = 5
        except Exception:
            scores["expenses"] = 5

    total_score = min(100, max(0, sum(scores.values())))

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
        "breakdown": scores,
        "branch_id": branch_id,
    }


# ==============================
# ANOMALY DETECTION
# ==============================
def detect_anomalies(branch_id=None):
    """Detect sales anomalies — branch-scoped."""
    branch_id = _resolve_branch(branch_id)
    anomalies = []
    sales_df = _load_scoped(load_sales, branch_id)

    if sales_df is None or sales_df.empty or len(sales_df) < 7:
        return anomalies

    sales_undup = get_unduplicated_sales(sales_df)
    if sales_undup.empty or len(sales_undup) < 7:
        return anomalies

    date_col = get_date_column(sales_undup)
    if date_col is None:
        return anomalies

    try:
        sales_undup = sales_undup.copy()
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
                    z = (latest["sales"] - latest["ma_7"]) / latest["std_7"]
                    if abs(z) > 2:
                        anomalies.append({
                            "type": "SALES_SPIKE" if z > 0 else "SALES_DROP",
                            "severity": "HIGH" if abs(z) > 3 else "MEDIUM",
                            "message": (
                                f"Unusual sales {'spike' if z > 0 else 'drop'} detected: "
                                f"{abs(z * 100):.0f}% {'above' if z > 0 else 'below'} average"
                            ),
                            "value": to_float(latest["sales"]),
                            "expected": to_float(latest["ma_7"]),
                        })
    except Exception:
        pass

    return anomalies


# ==============================
# INTELLIGENT RECOMMENDATIONS
# ==============================
def get_intelligent_recommendations(branch_id=None):
    branch_id = _resolve_branch(branch_id)

    recommendations = []
    priorities = {"Critical": 1, "High": 2, "Medium": 3, "Low": 4}

    sales_df = _load_scoped(load_sales, branch_id)
    products_df = _load_scoped(load_products, branch_id)

    try:
        expenses_df = load_expenses(branch_id=branch_id) if not _is_all_branches(branch_id) \
            else _load_scoped(load_expenses, branch_id)
    except TypeError:
        try:
            expenses_df = load_expenses()
        except Exception:
            expenses_df = pd.DataFrame()
    except Exception:
        expenses_df = pd.DataFrame()

    score = calculate_business_score(branch_id)
    sales_undup = get_unduplicated_sales(sales_df)
    sales_date_col = get_date_column(sales_undup)
    amount_col = get_amount_column(sales_undup)

    # 1) Stock recommendations
    if products_df is not None and not products_df.empty:
        try:
            if "reorder_level" in products_df.columns:
                low_stock = products_df[products_df["stock"] <= products_df["reorder_level"]]
            else:
                low_stock = products_df[products_df["stock"] <= 5]
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
                    "potential_impact": "Prevents lost sales and customer dissatisfaction.",
                })
            elif len(low_stock) > 0:
                recommendations.append({
                    "category": "Inventory",
                    "priority": "High",
                    "title": f"{len(low_stock)} Products Running Low",
                    "description": "Several products are below reorder level.",
                    "action": "Review stock levels and place purchase orders.",
                    "potential_impact": "Prevents stockouts and ensures availability.",
                })
        except Exception:
            pass

    # 2) Sales trend recommendations
    if sales_undup is not None and not sales_undup.empty and sales_date_col and amount_col:
        try:
            sales_undup = sales_undup.copy()
            sales_undup[sales_date_col] = pd.to_datetime(sales_undup[sales_date_col], errors="coerce")
            sales_undup = sales_undup.dropna(subset=[sales_date_col])

            last_30 = sales_undup[sales_undup[sales_date_col] >= (datetime.now() - timedelta(days=30))]
            prev_30 = sales_undup[
                (sales_undup[sales_date_col] < (datetime.now() - timedelta(days=30))) &
                (sales_undup[sales_date_col] >= (datetime.now() - timedelta(days=60)))
            ]

            current_sales = to_float(last_30[amount_col].sum()) if not last_30.empty else 0
            previous_sales = to_float(prev_30[amount_col].sum()) if not prev_30.empty else 0

            if previous_sales > 0:
                growth = ((current_sales - previous_sales) / previous_sales) * 100
                if growth < -10:
                    recommendations.append({
                        "category": "Sales",
                        "priority": "High",
                        "title": "Sales Declining",
                        "description": f"Sales decreased by {abs(growth):.0f}% vs previous 30 days.",
                        "action": "Review pricing, run promotions, or increase marketing efforts.",
                        "potential_impact": "Could recover lost revenue and improve cash flow.",
                    })
                elif growth > 20:
                    recommendations.append({
                        "category": "Sales",
                        "priority": "Low",
                        "title": "Strong Sales Growth",
                        "description": f"Sales increased by {growth:.0f}% — excellent performance!",
                        "action": "Analyze what's working and consider expanding successful products.",
                        "potential_impact": "Capitalize on momentum for further growth.",
                    })
        except Exception:
            pass

    # 3) Customer recommendations
    try:
        customer_analytics = get_customer_analytics_from_sales(sales_df, branch_id)
        if not customer_analytics.empty and len(customer_analytics) > 1:
            if 'days_since_last_purchase' in customer_analytics.columns:
                inactive = customer_analytics[customer_analytics['days_since_last_purchase'] > 90]
                if len(inactive) > len(customer_analytics) * 0.5 and len(inactive) > 3:
                    recommendations.append({
                        "category": "Customers",
                        "priority": "Medium",
                        "title": f"High Customer Inactivity ({len(inactive)} inactive)",
                        "description": f"{len(inactive)} customers haven't purchased in over 90 days.",
                        "action": "Launch a re-engagement campaign with special offers.",
                        "potential_impact": "Could recover up to 30% of inactive customers.",
                    })
            vip_customers = customer_analytics[customer_analytics['segment'] == 'VIP']
            if len(vip_customers) > 0:
                recommendations.append({
                    "category": "Customers",
                    "priority": "Low",
                    "title": f"{len(vip_customers)} VIP Customers Identified",
                    "description": "These customers are your most valuable. Consider a loyalty program.",
                    "action": "Create exclusive offers and personalized service for VIPs.",
                    "potential_impact": "Increase customer lifetime value and retention.",
                })
    except Exception:
        pass

    # 4) Expense recommendations
    expense_date_col = get_date_column(expenses_df)
    if expenses_df is not None and not expenses_df.empty and "amount" in expenses_df.columns and expense_date_col:
        try:
            expenses_df = expenses_df.copy()
            expenses_df[expense_date_col] = pd.to_datetime(expenses_df[expense_date_col], errors="coerce")
            monthly_expenses = expenses_df[
                expenses_df[expense_date_col].dt.month == datetime.now().month
            ]["amount"].sum()

            revenue = 0
            if sales_undup is not None and not sales_undup.empty and amount_col and sales_date_col:
                sales_undup = sales_undup.copy()
                sales_undup[sales_date_col] = pd.to_datetime(sales_undup[sales_date_col], errors="coerce")
                revenue = sales_undup[
                    sales_undup[sales_date_col].dt.month == datetime.now().month
                ][amount_col].sum()

            expense_ratio = (to_float(monthly_expenses) / to_float(revenue) * 100) if revenue > 0 else 100
            if expense_ratio > 40:
                recommendations.append({
                    "category": "Expenses",
                    "priority": "High",
                    "title": "High Expense Ratio",
                    "description": f"Expenses are {expense_ratio:.0f}% of revenue — above recommended 30–40%.",
                    "action": "Review all expenses and identify cost-cutting opportunities.",
                    "potential_impact": "Could increase net profit by 10–20%.",
                })
        except Exception:
            pass

    # 5) Profitability recommendations — pl_engine is branch-aware
    try:
        pl = profit_loss_account(branch_id=branch_id)
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
                    "potential_impact": "Essential for business survival and growth.",
                })
            elif net_margin < 10 and net_margin > 0:
                recommendations.append({
                    "category": "Profitability",
                    "priority": "Medium",
                    "title": "Low Profit Margin",
                    "description": f"Net profit margin is only {net_margin:.1f}%.",
                    "action": "Consider price optimization or cost reduction strategies.",
                    "potential_impact": "Could increase profitability significantly.",
                })
    except Exception:
        pass

    recommendations.sort(key=lambda x: priorities.get(x.get("priority", "Low"), 99))
    return recommendations


# ==============================
# SALES FORECAST
# ==============================
def ai_sales_forecast(branch_id=None, days=30):
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)

    if sales_df is None or sales_df.empty or len(sales_df) < 14:
        return None

    sales_undup = get_unduplicated_sales(sales_df)
    if sales_undup.empty or len(sales_undup) < 7:
        return None

    date_col = get_date_column(sales_undup)
    if date_col is None:
        return None

    try:
        sales_undup = sales_undup.copy()
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

        x = np.arange(len(daily_sales))
        y = daily_sales["sales"].values
        z = np.polyfit(x, y, 1)
        trend = np.poly1d(z)

        forecast_dates = [
            (datetime.now().date() + timedelta(days=i)) for i in range(1, days + 1)
        ]
        forecast_sales = [trend(len(daily_sales) + i) for i in range(1, days + 1)]
        forecast_sales = [max(0, s) for s in forecast_sales]

        residuals = y - trend(x)
        std_residual = np.std(residuals)

        forecast_data = []
        for date, sales in zip(forecast_dates, forecast_sales):
            forecast_data.append({
                "date": date,
                "forecast_sales": sales,
                "lower_bound": max(0, sales - 1.96 * std_residual),
                "upper_bound": sales + 1.96 * std_residual,
            })

        return {
            "forecast": forecast_data,
            "trend_slope": z[0],
            "trend_direction": "increasing" if z[0] > 0 else "decreasing",
            "total_forecast": sum(forecast_sales),
            "avg_daily_forecast": sum(forecast_sales) / days,
            "branch_id": branch_id,
        }
    except Exception:
        return None


# ==============================
# SEASONAL TRENDS
# ==============================
def seasonal_trend_analysis(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)

    if sales_df is None or sales_df.empty:
        return None

    sales_undup = get_unduplicated_sales(sales_df)
    if sales_undup.empty:
        return None

    date_col = get_date_column(sales_undup)
    if date_col is None:
        return None

    try:
        sales_undup = sales_undup.copy()
        sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
        sales_undup = sales_undup.dropna(subset=[date_col])
        sales_undup["month"] = sales_undup[date_col].dt.month
        sales_undup["day_of_week"] = sales_undup[date_col].dt.day_name()

        amount_col = get_amount_column(sales_undup)
        if amount_col is None:
            return None

        sales_undup[amount_col] = sales_undup[amount_col].apply(to_float)

        monthly_sales = sales_undup.groupby("month")[amount_col].sum().reset_index()

        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_sales = sales_undup.groupby("day_of_week")[amount_col].sum().reset_index()
        if not dow_sales.empty:
            dow_sales["day_of_week"] = pd.Categorical(
                dow_sales["day_of_week"], categories=dow_order, ordered=True
            )
            dow_sales = dow_sales.sort_values("day_of_week")

        peak_month = (
            monthly_sales.loc[monthly_sales[amount_col].idxmax(), "month"]
            if not monthly_sales.empty else None
        )
        peak_day = (
            dow_sales.loc[dow_sales[amount_col].idxmax(), "day_of_week"]
            if not dow_sales.empty else None
        )
        slow_day = (
            dow_sales.loc[dow_sales[amount_col].idxmin(), "day_of_week"]
            if not dow_sales.empty else None
        )

        return {
            "peak_month": int(peak_month) if peak_month is not None else None,
            "peak_day": peak_day,
            "slow_day": slow_day,
            "monthly_pattern": monthly_sales.to_dict('records') if not monthly_sales.empty else [],
            "weekly_pattern": dow_sales.to_dict('records') if not dow_sales.empty else [],
            "branch_id": branch_id,
        }
    except Exception:
        return None


# ==============================
# ALERT GENERATION
# ==============================
def generate_alerts(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    alerts = []

    products_df = _load_scoped(load_products, branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    score = calculate_business_score(branch_id)
    anomalies = detect_anomalies(branch_id)

    if products_df is not None and not products_df.empty and "stock" in products_df.columns:
        try:
            out_of_stock = products_df[products_df["stock"] == 0]
            if len(out_of_stock) > 0:
                names = out_of_stock["name"].head(3).tolist() if "name" in out_of_stock.columns else []
                name_str = ", ".join(names) + ("..." if len(out_of_stock) > 3 else "")
                alerts.append({
                    "level": "critical",
                    "title": f"{len(out_of_stock)} Products Out of Stock",
                    "message": f"Immediate action required: {name_str}" if name_str else "Immediate action required.",
                    "timestamp": datetime.now(),
                })
        except Exception:
            pass

    try:
        total_score = score.get("total_score", 0)
        if total_score < 40:
            alerts.append({
                "level": "critical",
                "title": f"Business Health Critical ({total_score}/100)",
                "message": "Urgent attention needed across multiple business areas.",
                "timestamp": datetime.now(),
            })
        elif total_score < 60:
            alerts.append({
                "level": "warning",
                "title": f"Business Health Warning ({total_score}/100)",
                "message": "Several areas need improvement to reach good standing.",
                "timestamp": datetime.now(),
            })
    except Exception:
        pass

    if sales_df is not None and not sales_df.empty:
        sales_undup = get_unduplicated_sales(sales_df)
        date_col = get_date_column(sales_undup)
        if date_col:
            try:
                sales_undup = sales_undup.copy()
                sales_undup[date_col] = pd.to_datetime(sales_undup[date_col], errors="coerce")
                today = datetime.now().date()
                today_sales = sales_undup[sales_undup[date_col].dt.date == today]
                if today_sales.empty:
                    alerts.append({
                        "level": "warning",
                        "title": "No Sales Recorded Today",
                        "message": "No transactions have been recorded for today.",
                        "timestamp": datetime.now(),
                    })
            except Exception:
                pass

    try:
        customer_analytics = get_customer_analytics_from_sales(sales_df, branch_id)
        if not customer_analytics.empty and len(customer_analytics) > 3:
            if 'days_since_last_purchase' in customer_analytics.columns:
                active_customers = len(customer_analytics[customer_analytics['days_since_last_purchase'] <= 30])
                total_customers = len(customer_analytics)
                active_rate = (active_customers / total_customers) * 100 if total_customers > 0 else 0
                if active_rate < 20 and total_customers > 10:
                    alerts.append({
                        "level": "warning",
                        "title": "Low Customer Retention",
                        "message": f"Only {active_rate:.0f}% of customers are active (purchased in last 30 days).",
                        "timestamp": datetime.now(),
                    })
    except Exception:
        pass

    for anomaly in anomalies:
        severity = anomaly.get("severity", "MEDIUM")
        alerts.append({
            "level": "warning" if severity == "MEDIUM" else "critical",
            "title": f"{anomaly.get('type', 'Anomaly').replace('_', ' ')} Detected",
            "message": anomaly.get("message", "Anomaly detected"),
            "timestamp": datetime.now(),
        })

    return alerts