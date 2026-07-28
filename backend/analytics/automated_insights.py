# backend/analytics/automated_insights.py
"""
Automated Insights Digest
Daily/weekly AI-generated business summaries sent via email
"""

import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import json
from pathlib import Path
import plotly.graph_objects as go
import plotly.utils
import json as json_lib
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_customers,
    load_expenses,
    load_debtors,
    load_purchases,
    to_float
)
from backend.integrations.email_reports import get_email_config, send_email
from backend.modules.expenses import load_expenses as load_expenses_direct


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
INSIGHTS_FILE = DATA_DIR / "insights_settings.json"
INSIGHTS_HISTORY_FILE = DATA_DIR / "insights_history.csv"


# ==============================
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_date_column(df):
    """Find date column in dataframe"""
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    """Find amount column"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    """Find receipt number column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_unique_id_column(df):
    """Find a unique identifier column"""
    if df is None or df.empty:
        return None
    for col in ["id", "expense_id", "receipt_no", "transaction_id", "uuid"]:
        if col in df.columns:
            return col
    return None


def deduplicate_dataframe(df, subset_cols=None):
    """
    Deduplicate a dataframe using the best available method.
    Returns deduplicated dataframe.
    """
    if df is None or df.empty:
        return df
    
    df = df.copy()
    
    # Try to find a unique identifier column
    unique_col = get_unique_id_column(df)
    
    if unique_col:
        return df.drop_duplicates(subset=[unique_col])
    
    # If no unique column, try deduplicating by combination of fields
    if subset_cols is None:
        subset_cols = []
        for col in ["date", "category", "amount", "description", "vendor"]:
            if col in df.columns:
                subset_cols.append(col)
    
    if len(subset_cols) >= 2:
        return df.drop_duplicates(subset=subset_cols)
    
    # If all else fails, return original
    return df


# ==============================
# INSIGHTS GENERATOR - FIXED
# ==============================

class InsightsGenerator:
    """Generate automated business insights"""
    
    def __init__(self):
        self.insights = []
        self.metrics = {}
        self.recommendations = []
        self.alerts = []
    
    def generate_daily_insights(self):
        """Generate daily business insights"""
        
        # Load data
        sales_df = load_sales()
        products_df = load_products()
        customers_df = load_customers()
        expenses_df = load_expenses_direct()
        debtors_df = load_debtors()
        
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        self.insights = []
        self.metrics = {}
        self.recommendations = []
        self.alerts = []
        
        # 1. Sales Insights - WITH DEDUPLICATION
        sales_insights = self._analyze_sales(sales_df, today, yesterday, week_ago, month_ago)
        self.insights.extend(sales_insights)
        
        # 2. Product Insights
        product_insights = self._analyze_products(products_df, sales_df)
        self.insights.extend(product_insights)
        
        # 3. Customer Insights
        customer_insights = self._analyze_customers(customers_df, sales_df)
        self.insights.extend(customer_insights)
        
        # 4. Financial Insights - FIXED with deduplication
        financial_insights = self._analyze_financials(expenses_df, sales_df, debtors_df)
        self.insights.extend(financial_insights)
        
        # 5. Alerts
        self.alerts = self._generate_alerts(products_df, debtors_df, sales_df)
        
        return self._format_report()
    
    def _analyze_sales(self, sales_df, today, yesterday, week_ago, month_ago):
        """Analyze sales data - WITH DEDUPLICATION"""
        insights = []
        
        if sales_df.empty:
            return [{"type": "sales", "message": "No sales data available", "priority": "info"}]
        
        date_col = get_date_column(sales_df)
        amount_col = get_amount_column(sales_df)
        receipt_col = get_receipt_column(sales_df)
        
        if date_col is None or amount_col is None:
            return [{"type": "sales", "message": "Sales data incomplete", "priority": "info"}]
        
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        if sales_df.empty:
            return [{"type": "sales", "message": "No valid sales dates", "priority": "info"}]
        
        # ==============================
        # FIX: Deduplicate by receipt_no
        # ==============================
        if receipt_col and receipt_col in sales_df.columns:
            sales_df = sales_df.drop_duplicates(subset=[receipt_col])
        
        # Today's sales
        today_sales = sales_df[sales_df[date_col].dt.date == today]
        today_revenue = safe_float(today_sales[amount_col].sum()) if amount_col else 0
        today_transactions = len(today_sales)
        
        # Yesterday's sales
        yesterday_sales = sales_df[sales_df[date_col].dt.date == yesterday]
        yesterday_revenue = safe_float(yesterday_sales[amount_col].sum()) if amount_col else 0
        
        # Week sales
        week_sales = sales_df[sales_df[date_col] >= pd.Timestamp(week_ago)]
        week_revenue = safe_float(week_sales[amount_col].sum()) if amount_col else 0
        
        # Month sales
        month_sales = sales_df[sales_df[date_col] >= pd.Timestamp(month_ago)]
        month_revenue = safe_float(month_sales[amount_col].sum()) if amount_col else 0
        
        # Store metrics
        self.metrics["today_revenue"] = today_revenue
        self.metrics["today_transactions"] = today_transactions
        self.metrics["yesterday_revenue"] = yesterday_revenue
        self.metrics["week_revenue"] = week_revenue
        self.metrics["month_revenue"] = month_revenue
        
        # Insights
        if today_revenue > 0:
            if yesterday_revenue > 0:
                growth = ((today_revenue - yesterday_revenue) / yesterday_revenue * 100)
                if growth > 20:
                    insights.append({
                        "type": "sales",
                        "message": f"Sales up {growth:.0f}% compared to yesterday",
                        "priority": "high",
                        "detail": f"Today: ${today_revenue:,.2f} vs Yesterday: ${yesterday_revenue:,.2f}"
                    })
                elif growth < -20:
                    insights.append({
                        "type": "sales",
                        "message": f"Sales down {abs(growth):.0f}% compared to yesterday",
                        "priority": "medium",
                        "detail": f"Today: ${today_revenue:,.2f} vs Yesterday: ${yesterday_revenue:,.2f}"
                    })
                else:
                    insights.append({
                        "type": "sales",
                        "message": f"Sales stable at ${today_revenue:,.2f} today",
                        "priority": "info",
                        "detail": f"{today_transactions} transactions today"
                    })
            else:
                insights.append({
                    "type": "sales",
                    "message": f"Today's sales: ${today_revenue:,.2f}",
                    "priority": "info",
                    "detail": f"{today_transactions} transactions today"
                })
        else:
            insights.append({
                "type": "sales",
                "message": "No sales recorded today",
                "priority": "warning",
                "detail": "Check if store is open and POS is working"
            })
        
        # Weekly summary
        if week_revenue > 0:
            insights.append({
                "type": "sales",
                "message": f"Weekly sales: ${week_revenue:,.2f}",
                "priority": "info",
                "detail": "Last 7 days performance"
            })
        
        return insights
    
    def _analyze_products(self, products_df, sales_df):
        """Analyze product data"""
        insights = []
        
        if products_df.empty:
            return [{"type": "products", "message": "No products in inventory", "priority": "info"}]
        
        # Stock levels
        total_products = len(products_df)
        out_of_stock = len(products_df[products_df["stock"] == 0])
        
        # Find reorder level column
        reorder_col = None
        for col in ["reorder_level", "reorder_point", "min_stock"]:
            if col in products_df.columns:
                reorder_col = col
                break
        
        if reorder_col:
            low_stock = len(products_df[products_df["stock"] <= products_df[reorder_col]])
        else:
            # If no reorder level, consider stock < 5 as low
            low_stock = len(products_df[(products_df["stock"] > 0) & (products_df["stock"] < 5)])
        
        self.metrics["total_products"] = total_products
        self.metrics["out_of_stock"] = out_of_stock
        self.metrics["low_stock"] = low_stock
        
        if out_of_stock > 0:
            # Get top out of stock products
            out_of_stock_products = products_df[products_df["stock"] == 0]["name"].head(3).tolist()
            names = ", ".join(out_of_stock_products)
            insights.append({
                "type": "products",
                "message": f"{out_of_stock} products out of stock",
                "priority": "critical",
                "detail": f"Affected: {names}" + ("..." if len(out_of_stock_products) > 3 else "")
            })
        
        if low_stock > 0:
            insights.append({
                "type": "products",
                "message": f"{low_stock} products low on stock",
                "priority": "high",
                "detail": "Place orders soon to avoid stockouts"
            })
        
        if out_of_stock == 0 and low_stock == 0:
            insights.append({
                "type": "products",
                "message": "All products in stock",
                "priority": "success",
                "detail": f"{total_products} products available"
            })
        
        # Top selling products
        if not sales_df.empty and "name" in sales_df.columns:
            # Deduplicate sales for product analysis
            receipt_col = get_receipt_column(sales_df)
            if receipt_col and receipt_col in sales_df.columns:
                sales_products = sales_df.drop_duplicates(subset=[receipt_col])
            else:
                sales_products = sales_df
            
            if "items" in sales_products.columns:
                top_products = sales_products.groupby("name")["items"].sum().nlargest(3)
                if not top_products.empty:
                    top_names = top_products.index.tolist()
                    insights.append({
                        "type": "products",
                        "message": f"Top selling products: {', '.join(top_names)}",
                        "priority": "info",
                        "detail": "Focus on these best-sellers"
                    })
        
        return insights
    
    def _analyze_customers(self, customers_df, sales_df):
        """Analyze customer data"""
        insights = []
        
        if customers_df.empty:
            return [{"type": "customers", "message": "No customer data available", "priority": "info"}]
        
        total_customers = len(customers_df)
        self.metrics["total_customers"] = total_customers
        
        # New customers (last 30 days)
        date_col = None
        for col in ["created_at", "join_date", "date_joined", "last_purchase_date"]:
            if col in customers_df.columns:
                date_col = col
                break
        
        if date_col:
            customers_df[date_col] = pd.to_datetime(customers_df[date_col], errors="coerce")
            month_ago = datetime.now() - timedelta(days=30)
            new_customers = len(customers_df[customers_df[date_col] >= month_ago])
            self.metrics["new_customers"] = new_customers
            
            if new_customers > 0:
                insights.append({
                    "type": "customers",
                    "message": f"{new_customers} new customers this month",
                    "priority": "info",
                    "detail": f"Total: {total_customers} customers"
                })
        
        # Customer retention
        if not sales_df.empty:
            customer_col = None
            for col in ["customer", "customer_name", "client"]:
                if col in sales_df.columns:
                    customer_col = col
                    break
            
            if customer_col:
                # Deduplicate sales for customer analysis
                receipt_col = get_receipt_column(sales_df)
                if receipt_col and receipt_col in sales_df.columns:
                    sales_customers = sales_df.drop_duplicates(subset=[receipt_col])
                else:
                    sales_customers = sales_df
                
                repeat_customers = sales_customers.groupby(customer_col).filter(lambda x: len(x) > 1)[customer_col].nunique()
                self.metrics["repeat_customers"] = repeat_customers
                
                if repeat_customers > 0:
                    retention_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
                    if retention_rate < 20:
                        insights.append({
                            "type": "customers",
                            "message": f"Low retention rate: {retention_rate:.1f}%",
                            "priority": "medium",
                            "detail": "Consider loyalty programs to improve retention"
                        })
                    else:
                        insights.append({
                            "type": "customers",
                            "message": f"Customer retention: {retention_rate:.1f}%",
                            "priority": "success",
                            "detail": f"{repeat_customers} repeat customers"
                        })
        
        return insights
    
    def _analyze_financials(self, expenses_df, sales_df, debtors_df):
        """Analyze financial data - FIXED with correct unduplicated revenue"""
        insights = []
        
        # ==============================
        # FIX 1: Expenses - Load correctly
        # ==============================
        total_expenses = 0
        if expenses_df is not None and not expenses_df.empty:
            expenses_clean = deduplicate_dataframe(expenses_df)
            amount_col = None
            for col in ["amount", "total", "value", "expense_amount"]:
                if col in expenses_clean.columns:
                    amount_col = col
                    break
            if amount_col:
                total_expenses = safe_float(expenses_clean[amount_col].sum())
        
        # If still 0, try loading from core
        if total_expenses == 0:
            try:
                from backend.core.db_adapter import load_expenses as load_expenses_core
                expenses_core = load_expenses_core()
                if expenses_core is not None and not expenses_core.empty:
                    expenses_clean = deduplicate_dataframe(expenses_core)
                    amount_col = None
                    for col in ["amount", "total", "value", "expense_amount"]:
                        if col in expenses_clean.columns:
                            amount_col = col
                            break
                    if amount_col:
                        total_expenses = safe_float(expenses_clean[amount_col].sum())
            except:
                pass
        
        self.metrics["total_expenses"] = total_expenses
        
        # Monthly expenses (last 30 days)
        monthly_expenses = 0
        if expenses_df is not None and not expenses_df.empty:
            date_col = get_date_column(expenses_df)
            if date_col:
                expenses_df[date_col] = pd.to_datetime(expenses_df[date_col], errors="coerce")
                expenses_df = expenses_df.dropna(subset=[date_col])
                month_ago = datetime.now() - timedelta(days=30)
                
                expenses_month = expenses_df[expenses_df[date_col] >= month_ago].copy()
                if not expenses_month.empty:
                    expenses_month = deduplicate_dataframe(expenses_month)
                    amount_col = None
                    for col in ["amount", "total", "value", "expense_amount"]:
                        if col in expenses_month.columns:
                            amount_col = col
                            break
                    if amount_col:
                        monthly_expenses = safe_float(expenses_month[amount_col].sum())
                        self.metrics["monthly_expenses"] = monthly_expenses
        
        if monthly_expenses > 0:
            insights.append({
                "type": "financial",
                "message": f"Monthly expenses: ${monthly_expenses:,.2f}",
                "priority": "info",
                "detail": f"Total expenses: ${total_expenses:,.2f}"
            })
        elif total_expenses > 0:
            insights.append({
                "type": "financial",
                "message": f"Total expenses: ${total_expenses:,.2f}",
                "priority": "info",
                "detail": "Expenses recorded in system"
            })
        else:
            insights.append({
                "type": "financial",
                "message": "No expenses recorded",
                "priority": "info",
                "detail": "Start recording expenses in the Expenses module"
            })
        
        # ==============================
        # FIX 2: Revenue - STRONG DEDUPLICATION BY RECEIPT_NO
        # ==============================
        total_revenue = 0
        if not sales_df.empty:
            amount_col = get_amount_column(sales_df)
            receipt_col = get_receipt_column(sales_df)
            
            if amount_col:
                # STRONG FIX: Deduplicate by receipt_no
                if receipt_col and receipt_col in sales_df.columns:
                    # Get unique receipts only
                    sales_undup = sales_df.drop_duplicates(subset=[receipt_col])
                    total_revenue = safe_float(sales_undup[amount_col].sum())
                else:
                    # If no receipt_no, try deduplicating by date + amount
                    # But this is less reliable
                    sales_undup = sales_df.copy()
                    if "date" in sales_undup.columns:
                        sales_undup = sales_undup.drop_duplicates(subset=["date", amount_col])
                    total_revenue = safe_float(sales_undup[amount_col].sum())
                
                self.metrics["total_revenue"] = total_revenue
                
                # Calculate profit
                profit = total_revenue - total_expenses
                margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
                self.metrics["profit"] = profit
                self.metrics["profit_margin"] = margin
                
                if total_revenue > 0:
                    insights.append({
                        "type": "financial",
                        "message": f"Total revenue: ${total_revenue:,.2f}",
                        "priority": "info",
                        "detail": f"Based on unduplicated receipts"
                    })
                    
                    if total_expenses > 0:
                        insights.append({
                            "type": "financial",
                            "message": f"Total expenses: ${total_expenses:,.2f}",
                            "priority": "info",
                            "detail": f"Profit: ${profit:,.2f}"
                        })
                
                if margin < 10 and total_revenue > 0:
                    insights.append({
                        "type": "financial",
                        "message": f"Low profit margin: {margin:.1f}%",
                        "priority": "medium",
                        "detail": f"Revenue: ${total_revenue:,.2f}, Expenses: ${total_expenses:,.2f}"
                    })
                elif margin > 20 and total_revenue > 0:
                    insights.append({
                        "type": "financial",
                        "message": f"Healthy profit margin: {margin:.1f}%",
                        "priority": "success",
                        "detail": f"Profit: ${profit:,.2f}"
                    })
                elif total_revenue > 0:
                    insights.append({
                        "type": "financial",
                        "message": f"Profit margin: {margin:.1f}%",
                        "priority": "info",
                        "detail": f"Revenue: ${total_revenue:,.2f}, Expenses: ${total_expenses:,.2f}"
                    })
        else:
            self.metrics["total_revenue"] = 0
            self.metrics["profit"] = 0
            self.metrics["profit_margin"] = 0
            insights.append({
                "type": "financial",
                "message": "No sales data for financial analysis",
                "priority": "info",
                "detail": "Complete some sales to see financial metrics"
            })
        
        # Debtors
        if not debtors_df.empty:
            balance_col = None
            for col in ["balance", "outstanding", "amount_due"]:
                if col in debtors_df.columns:
                    balance_col = col
                    break
            
            if balance_col:
                total_debt = safe_float(debtors_df[balance_col].sum())
                self.metrics["total_debt"] = total_debt
                
                debtors_count = len(debtors_df[debtors_df[balance_col] > 0])
                self.metrics["debtors_count"] = debtors_count
                
                if total_debt > 0:
                    insights.append({
                        "type": "financial",
                        "message": f"Outstanding debt: ${total_debt:,.2f}",
                        "priority": "medium" if total_debt > 1000 else "info",
                        "detail": f"{debtors_count} customers with outstanding balance"
                    })
            else:
                self.metrics["total_debt"] = 0
                self.metrics["debtors_count"] = 0
        
        return insights
    
    def _generate_alerts(self, products_df, debtors_df, sales_df):
        """Generate critical alerts"""
        alerts = []
        
        # Stock alerts
        if not products_df.empty:
            out_of_stock = len(products_df[products_df["stock"] == 0])
            if out_of_stock > 0:
                alerts.append({
                    "type": "stock",
                    "message": f"{out_of_stock} products out of stock",
                    "severity": "critical"
                })
        
        # Debt alerts
        if not debtors_df.empty:
            balance_col = None
            for col in ["balance", "outstanding", "amount_due"]:
                if col in debtors_df.columns:
                    balance_col = col
                    break
            
            if balance_col:
                high_debt = debtors_df[debtors_df[balance_col] > 1000]
                if not high_debt.empty:
                    alerts.append({
                        "type": "debt",
                        "message": f"{len(high_debt)} customers with high debt (>$1000)",
                        "severity": "warning"
                    })
        
        # Sales alerts
        if not sales_df.empty:
            date_col = get_date_column(sales_df)
            receipt_col = get_receipt_column(sales_df)
            
            if date_col:
                sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                today = datetime.now().date()
                
                # Deduplicate for today's sales check
                if receipt_col and receipt_col in sales_df.columns:
                    today_sales = sales_df[sales_df[date_col].dt.date == today].drop_duplicates(subset=[receipt_col])
                else:
                    today_sales = sales_df[sales_df[date_col].dt.date == today]
                
                if today_sales.empty:
                    alerts.append({
                        "type": "sales",
                        "message": "No sales recorded today",
                        "severity": "warning"
                    })
        
        return alerts
    
    def _format_report(self):
        """Format insights into report"""
        return {
            "generated_at": datetime.now().isoformat(),
            "period": "daily",
            "metrics": self.metrics,
            "insights": self.insights,
            "alerts": self.alerts,
            "summary": self._generate_summary()
        }
    
    def _generate_summary(self):
        """Generate executive summary"""
        summary = []
        
        # Count insights by priority
        high_count = sum(1 for i in self.insights if i.get("priority") == "high")
        medium_count = sum(1 for i in self.insights if i.get("priority") == "medium")
        
        if high_count > 0:
            summary.append(f"{high_count} high-priority insights require attention")
        if medium_count > 0:
            summary.append(f"{medium_count} medium-priority insights to review")
        
        # Key metrics
        if self.metrics:
            revenue = self.metrics.get("today_revenue", 0)
            if revenue > 0:
                summary.append(f"Today's revenue: ${revenue:,.2f}")
            else:
                summary.append("No sales recorded today")
        
        if not summary:
            summary.append("All metrics look good")
        
        return " | ".join(summary)


# ==============================
# INSIGHTS SETTINGS
# ==============================

def load_insights_settings():
    """Load insights settings"""
    if INSIGHTS_FILE.exists():
        try:
            with open(INSIGHTS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    
    return {
        "enabled": True,
        "frequency": "daily",  # daily, weekly
        "send_time": "08:00",
        "last_sent": None,
        "recipients": [],
        "include_sales": True,
        "include_products": True,
        "include_customers": True,
        "include_financial": True,
        "send_alerts": True
    }


def save_insights_settings(settings):
    """Save insights settings"""
    INSIGHTS_FILE.parent.mkdir(exist_ok=True)
    with open(INSIGHTS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def log_insights_history(insights_data):
    """Log insights in history"""
    INSIGHTS_FILE.parent.mkdir(exist_ok=True)
    
    if not INSIGHTS_HISTORY_FILE.exists():
        df = pd.DataFrame(columns=[
            "timestamp", "period", "revenue", "transactions", "insights_count"
        ])
    else:
        df = pd.read_csv(INSIGHTS_HISTORY_FILE)
    
    metrics = insights_data.get("metrics", {})
    new_row = pd.DataFrame([{
        "timestamp": insights_data.get("generated_at", datetime.now().isoformat()),
        "period": insights_data.get("period", "daily"),
        "revenue": metrics.get("today_revenue", 0),
        "transactions": metrics.get("today_transactions", 0),
        "insights_count": len(insights_data.get("insights", []))
    }])
    
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(INSIGHTS_HISTORY_FILE, index=False)


# ==============================
# EMAIL REPORT GENERATOR
# ==============================

def generate_insights_email_html(insights_data):
    """Generate HTML email for insights"""
    
    metrics = insights_data.get("metrics", {})
    insights = insights_data.get("insights", [])
    alerts = insights_data.get("alerts", [])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Business Insights - Aziel Investments</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f4f4f4;
            }}
            .container {{
                max-width: 700px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                border-bottom: 3px solid #6366F1;
                padding-bottom: 20px;
                margin-bottom: 25px;
            }}
            .header h1 {{
                color: #1a1a2e;
                margin: 0;
                font-size: 24px;
            }}
            .header p {{
                color: #666;
                margin: 5px 0 0 0;
                font-size: 14px;
            }}
            .metric-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 15px;
                margin-bottom: 25px;
            }}
            .metric-card {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                border: 1px solid #e5e7eb;
            }}
            .metric-value {{
                font-size: 22px;
                font-weight: bold;
                color: #1a1a2e;
            }}
            .metric-label {{
                font-size: 12px;
                color: #6B7280;
                margin-top: 5px;
            }}
            .insight-item {{
                padding: 12px 15px;
                margin: 8px 0;
                border-radius: 8px;
                border-left: 4px solid #6366F1;
                background: #f8f9fa;
            }}
            .insight-critical {{
                border-left-color: #ef4444;
                background: #fef2f2;
            }}
            .insight-high {{
                border-left-color: #f59e0b;
                background: #fffbeb;
            }}
            .insight-medium {{
                border-left-color: #3b82f6;
                background: #eff6ff;
            }}
            .insight-info {{
                border-left-color: #10b981;
                background: #ecfdf5;
            }}
            .alert-item {{
                padding: 12px 15px;
                margin: 8px 0;
                border-radius: 8px;
                background: #fef2f2;
                border: 1px solid #fca5a5;
                color: #991b1b;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e5e7eb;
                color: #6B7280;
                font-size: 12px;
            }}
            .summary {{
                background: #f0fdf4;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border: 1px solid #bbf7d0;
                color: #166534;
            }}
    </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>SmartGro ERP Insights</h1>
                <p>Business Intelligence Report</p>
                <p style="font-size: 12px; color: #999;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
    """
    
    # Summary
    if insights_data.get("summary"):
        html += f"""
            <div class="summary">
                <strong>Executive Summary</strong><br>
                {insights_data.get("summary")}
            </div>
        """
    
    # Alerts
    if alerts:
        html += """
            <h3 style="color: #991b1b;">Alerts</h3>
        """
        for alert in alerts:
            html += f"""
                <div class="alert-item">
                    <strong>{alert.get('message', 'Alert')}</strong>
                </div>
            """
    
    # Metrics
    if metrics:
        html += """
            <h3>Key Metrics</h3>
            <div class="metric-grid">
        """
        
        metric_display = [
            ("Today's Revenue", f"${metrics.get('today_revenue', 0):,.2f}"),
            ("Transactions", f"{metrics.get('today_transactions', 0)}"),
            ("Products", f"{metrics.get('total_products', 0)}"),
            ("Customers", f"{metrics.get('total_customers', 0)}"),
            ("Low Stock", f"{metrics.get('low_stock', 0)}"),
            ("Total Expenses", f"${metrics.get('total_expenses', 0):,.2f}"),
            ("Profit", f"${metrics.get('profit', 0):,.2f}"),
            ("Debt", f"${metrics.get('total_debt', 0):,.2f}")
        ]
        
        for label, value in metric_display:
            html += f"""
                <div class="metric-card">
                    <div class="metric-value">{value}</div>
                    <div class="metric-label">{label}</div>
                </div>
            """
        
        html += """
            </div>
        """
    
    # Insights
    if insights:
        html += """
            <h3>Insights</h3>
        """
        
        for insight in insights:
            priority = insight.get("priority", "info")
            if priority == "critical":
                priority_class = "insight-critical"
            elif priority == "high":
                priority_class = "insight-high"
            elif priority == "medium":
                priority_class = "insight-medium"
            else:
                priority_class = "insight-info"
            
            detail = insight.get("detail", "")
            html += f"""
                <div class="insight-item {priority_class}">
                    <strong>{insight.get('message', '')}</strong>
                    {f'<br><span style="font-size: 13px; color: #6B7280;">{detail}</span>' if detail else ''}
                </div>
            """
    
    # Footer
    html += f"""
            <div class="footer">
                <p>SmartGro ERP System • Aziel Investments</p>
                <p>This report is automatically generated. For support, contact +263 78 290 5853</p>
                <p>© {datetime.now().year} Aziel Investments. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html


# ==============================
# SEND INSIGHTS
# ==============================

def send_insights_email(insights_data, recipient=None):
    """Send insights email to recipient"""
    
    settings = load_insights_settings()
    
    if not settings.get("enabled", True):
        return False, "Insights are disabled"
    
    recipients = recipient if recipient else settings.get("recipients", [])
    if isinstance(recipients, str):
        recipients = [recipients]
    
    if not recipients:
        return False, "No recipients configured"
    
    # Generate email
    subject = f"SmartGro Insights - {datetime.now().strftime('%Y-%m-%d')}"
    body = generate_insights_email_html(insights_data)
    
    # Send to each recipient
    success_count = 0
    for email in recipients:
        if email and email.strip():
            success, message = send_email(
                recipient=email.strip(),
                subject=subject,
                body=body
            )
            if success:
                success_count += 1
    
    if success_count > 0:
        # Update last sent time
        settings["last_sent"] = datetime.now().isoformat()
        save_insights_settings(settings)
        
        # Log history
        log_insights_history(insights_data)
        
        return True, f"Sent to {success_count} recipient(s)"
    
    return False, "Failed to send to any recipient"


def send_daily_insights():
    """Send daily insights to all recipients"""
    
    generator = InsightsGenerator()
    insights_data = generator.generate_daily_insights()
    
    return send_insights_email(insights_data)


def send_test_insights_email(email):
    """Send a test insights email"""
    
    generator = InsightsGenerator()
    insights_data = generator.generate_daily_insights()
    
    return send_insights_email(insights_data, email)


# ==============================
# INSIGHTS DASHBOARD
# ==============================

def automated_insights_dashboard():
    """Automated Insights Digest Dashboard"""
    
    st.title("Automated Insights Digest")
    st.caption("Daily/weekly AI-generated business summaries sent via email")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access insights digest.")
        return
    
    # Load settings
    settings = load_insights_settings()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "Generate Insights",
        "Settings",
        "History"
    ])
    
    # ==============================
    # TAB 1: GENERATE INSIGHTS
    # ==============================
    with tab1:
        st.markdown("## Generate Business Insights")
        
        if st.button("Generate Today's Insights", type="primary", use_container_width=True):
            with st.spinner("Generating insights..."):
                generator = InsightsGenerator()
                insights_data = generator.generate_daily_insights()
                
                st.session_state.current_insights = insights_data
                st.success("Insights generated!")
                st.balloons()
        
        # Display current insights
        if "current_insights" in st.session_state:
            insights_data = st.session_state.current_insights
            
            # Summary
            if insights_data.get("summary"):
                st.info(f"{insights_data.get('summary')}")
            
            # Alerts
            alerts = insights_data.get("alerts", [])
            if alerts:
                st.markdown("### Alerts")
                for alert in alerts:
                    st.error(f"**{alert.get('message', 'Alert')}**")
            
            # Metrics
            metrics = insights_data.get("metrics", {})
            if metrics:
                st.markdown("### Key Metrics")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Today's Revenue", f"${metrics.get('today_revenue', 0):,.2f}")
                with col2:
                    st.metric("Transactions", metrics.get('today_transactions', 0))
                with col3:
                    st.metric("Products", metrics.get('total_products', 0))
                with col4:
                    st.metric("Customers", metrics.get('total_customers', 0))
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Low Stock", metrics.get('low_stock', 0))
                with col2:
                    st.metric("Total Expenses", f"${metrics.get('total_expenses', 0):,.2f}")
                with col3:
                    st.metric("Profit", f"${metrics.get('profit', 0):,.2f}")
                with col4:
                    st.metric("Debt", f"${metrics.get('total_debt', 0):,.2f}")
            
            # Insights
            insights = insights_data.get("insights", [])
            if insights:
                st.markdown("### Insights")
                for insight in insights:
                    priority = insight.get("priority", "info")
                    icon = {
                        "critical": "[CRITICAL]",
                        "high": "[HIGH]",
                        "medium": "[MEDIUM]",
                        "info": "[INFO]",
                        "success": "[OK]"
                    }.get(priority, "[INFO]")
                    
                    if priority in ["critical", "high"]:
                        st.error(f"{icon} **{insight.get('message', '')}**")
                        if insight.get("detail"):
                            st.caption(insight.get("detail"))
                    elif priority == "medium":
                        st.warning(f"{icon} **{insight.get('message', '')}**")
                        if insight.get("detail"):
                            st.caption(insight.get("detail"))
                    else:
                        st.info(f"{icon} **{insight.get('message', '')}**")
                        if insight.get("detail"):
                            st.caption(insight.get("detail"))
            
            # Send email button
            st.markdown("---")
            st.markdown("### Send Report")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Send to Configured Recipients", type="primary", use_container_width=True):
                    with st.spinner("Sending..."):
                        success, message = send_insights_email(insights_data)
                        if success:
                            st.success(f"{message}")
                        else:
                            st.error(f"{message}")
            
            with col2:
                recipient = st.text_input("Send to specific email", placeholder="email@example.com")
                if recipient and st.button("Send Test Email", use_container_width=True):
                    with st.spinner("Sending..."):
                        success, message = send_test_insights_email(recipient)
                        if success:
                            st.success(f"{message}")
                        else:
                            st.error(f"{message}")
    
    # ==============================
    # TAB 2: SETTINGS
    # ==============================
    with tab2:
        st.markdown("## Insights Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enabled = st.checkbox("Enable Automated Insights", value=settings.get("enabled", True))
            frequency = st.selectbox(
                "Frequency",
                ["daily", "weekly"],
                index=["daily", "weekly"].index(settings.get("frequency", "daily"))
            )
            send_time = st.time_input("Send Time", value=datetime.strptime(settings.get("send_time", "08:00"), "%H:%M").time())
        
        with col2:
            include_sales = st.checkbox("Include Sales Insights", value=settings.get("include_sales", True))
            include_products = st.checkbox("Include Product Insights", value=settings.get("include_products", True))
            include_customers = st.checkbox("Include Customer Insights", value=settings.get("include_customers", True))
            include_financial = st.checkbox("Include Financial Insights", value=settings.get("include_financial", True))
            send_alerts = st.checkbox("Send Critical Alerts", value=settings.get("send_alerts", True))
        
        st.markdown("---")
        st.markdown("### Recipients")
        
        recipients_text = st.text_area(
            "Recipient Emails (one per line)",
            value="\n".join(settings.get("recipients", [])),
            height=100,
            placeholder="manager@example.com\nowner@example.com"
        )
        
        if st.button("Save Settings", type="primary", use_container_width=True):
            recipients = [r.strip() for r in recipients_text.split("\n") if r.strip()]
            
            settings.update({
                "enabled": enabled,
                "frequency": frequency,
                "send_time": send_time.strftime("%H:%M"),
                "recipients": recipients,
                "include_sales": include_sales,
                "include_products": include_products,
                "include_customers": include_customers,
                "include_financial": include_financial,
                "send_alerts": send_alerts
            })
            
            save_insights_settings(settings)
            st.success("Settings saved successfully!")
            st.rerun()
        
        # Test button
        st.markdown("---")
        if st.button("Send Test Insights Email", use_container_width=True):
            with st.spinner("Generating and sending..."):
                generator = InsightsGenerator()
                insights_data = generator.generate_daily_insights()
                success, message = send_insights_email(insights_data)
                if success:
                    st.success(f"{message}")
                else:
                    st.error(f"{message}")
    
    # ==============================
    # TAB 3: HISTORY
    # ==============================
    with tab3:
        st.markdown("## Insights History")
        
        if INSIGHTS_HISTORY_FILE.exists():
            history_df = pd.read_csv(INSIGHTS_HISTORY_FILE)
            
            if not history_df.empty:
                # Convert timestamp
                history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])
                history_df["date"] = history_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")
                
                st.dataframe(
                    history_df[["date", "period", "revenue", "transactions", "insights_count"]].tail(30),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "revenue": st.column_config.NumberColumn("Revenue", format="$%.2f")
                    }
                )
                
                # Chart
                if len(history_df) > 1:
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=history_df["timestamp"],
                        y=history_df["revenue"],
                        mode="lines+markers",
                        name="Revenue",
                        line=dict(color="#6366F1", width=2)
                    ))
                    
                    fig.update_layout(
                        title="Revenue Trend (Last 30 Days)",
                        xaxis_title="Date",
                        yaxis_title="Revenue ($)",
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Export
                csv = history_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download History (CSV)",
                    data=csv,
                    file_name=f"insights_history_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No history data available")
        else:
            st.info("No history data available")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    automated_insights_dashboard()