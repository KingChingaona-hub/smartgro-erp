# backend/analytics/anomaly_detection.py
"""
Advanced Anomaly Detection
Detect unusual patterns in sales, inventory, pricing, and financial data
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_purchases,
    load_expenses,
    load_cash,
    load_customers,
    to_float
)


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


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(value)
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
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in df.columns:
            return col
    return None


def convert_decimal_to_float(value):
    """Convert Decimal to float for numpy operations"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ==============================
# ANOMALY DETECTION ENGINE
# ==============================

class AnomalyDetector:
    """Detect anomalies in business data using ML"""
    
    def __init__(self):
        self.sales_anomalies = []
        self.inventory_anomalies = []
        self.price_anomalies = []
        self.financial_anomalies = []
        self.customer_anomalies = []
        self.last_analysis = None
        self.model = None
        self.scaler = None
        
    def detect_sales_anomalies(self, sales_df, days=30):
        """Detect anomalies in sales data"""
        
        self.sales_anomalies = []
        
        if sales_df.empty:
            return self.sales_anomalies
        
        date_col = get_date_column(sales_df)
        amount_col = get_amount_column(sales_df)
        
        if date_col is None or amount_col is None:
            return self.sales_anomalies
        
        # Convert and filter
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        cutoff = datetime.now() - timedelta(days=days)
        recent_sales = sales_df[sales_df[date_col] >= cutoff]
        
        if recent_sales.empty:
            return self.sales_anomalies
        
        # Convert amount column to float to avoid Decimal issues
        recent_sales[amount_col] = recent_sales[amount_col].apply(convert_decimal_to_float)
        
        # 1. Daily sales anomaly (Z-score method)
        daily_sales = recent_sales.groupby(recent_sales[date_col].dt.date)[amount_col].sum().reset_index()
        daily_sales.columns = ["date", "sales"]
        
        if len(daily_sales) >= 7:
            mean_sales = daily_sales["sales"].mean()
            std_sales = daily_sales["sales"].std()
            
            if std_sales > 0:
                for _, row in daily_sales.iterrows():
                    z_score = (row["sales"] - mean_sales) / std_sales
                    if abs(z_score) > 2.5:  # 2.5 standard deviations
                        self.sales_anomalies.append({
                            "type": "SALES_SPIKE" if z_score > 0 else "SALES_DROP",
                            "severity": "HIGH" if abs(z_score) > 3.5 else "MEDIUM",
                            "date": row["date"],
                            "value": row["sales"],
                            "expected": mean_sales,
                            "z_score": z_score,
                            "message": f"{'Spike' if z_score > 0 else 'Drop'} detected on {row['date']}: ${row['sales']:,.2f} vs expected ${mean_sales:,.2f}",
                            "confidence": min(100, abs(z_score) * 20)
                        })
        
        # 2. Individual transaction anomalies - FIXED: Convert to float first
        if len(recent_sales) > 10:
            # Convert amount column to float for quantile calculation
            amount_values = recent_sales[amount_col].astype(float)
            threshold = amount_values.quantile(0.95)
            large_transactions = recent_sales[recent_sales[amount_col] > threshold]
            
            for _, row in large_transactions.iterrows():
                self.sales_anomalies.append({
                    "type": "LARGE_TRANSACTION",
                    "severity": "MEDIUM",
                    "date": row[date_col],
                    "value": float(row[amount_col]),
                    "receipt_no": row.get("receipt_no", "N/A"),
                    "customer": row.get("customer", "N/A"),
                    "message": f"Unusually large transaction: ${float(row[amount_col]):,.2f}",
                    "confidence": 80
                })
        
        # 3. Zero sales days
        all_dates = pd.date_range(start=cutoff, end=datetime.now()).date
        sales_dates = set(daily_sales["date"])
        zero_days = [d for d in all_dates if d not in sales_dates]
        
        if len(zero_days) > 3:
            weekend_zero = sum(1 for d in zero_days if d.weekday() >= 5)
            weekday_zero = len(zero_days) - weekend_zero
            
            if weekday_zero > 2:
                self.sales_anomalies.append({
                    "type": "NO_SALES",
                    "severity": "HIGH" if weekday_zero > 5 else "MEDIUM",
                    "date": zero_days[0],
                    "value": 0,
                    "expected": mean_sales if 'mean_sales' in locals() else 0,
                    "message": f"{len(zero_days)} days with no sales in the last {days} days",
                    "confidence": 90
                })
        
        return self.sales_anomalies
    
    def detect_inventory_anomalies(self, products_df, sales_df, purchases_df):
        """Detect anomalies in inventory"""
        
        self.inventory_anomalies = []
        
        if products_df.empty:
            return self.inventory_anomalies
        
        # Convert stock to float
        products_df["stock"] = products_df["stock"].apply(convert_decimal_to_float)
        
        # 1. Negative stock (should never happen)
        negative_stock = products_df[products_df["stock"] < 0]
        if not negative_stock.empty:
            for _, product in negative_stock.iterrows():
                self.inventory_anomalies.append({
                    "type": "NEGATIVE_STOCK",
                    "severity": "CRITICAL",
                    "product": product.get("name", "Unknown"),
                    "barcode": product.get("barcode", ""),
                    "stock": product["stock"],
                    "message": f"Negative stock detected: {product.get('name', 'Unknown')} has {product['stock']} units",
                    "confidence": 100
                })
        
        # 2. Sudden stock drops
        if not purchases_df.empty and not sales_df.empty:
            product_col_sales = get_product_column(sales_df)
            qty_col_sales = get_quantity_column(sales_df)
            date_col_sales = get_date_column(sales_df)
            
            if product_col_sales and qty_col_sales and date_col_sales:
                sales_df[date_col_sales] = pd.to_datetime(sales_df[date_col_sales], errors="coerce")
                cutoff = datetime.now() - timedelta(days=7)
                recent_sales = sales_df[sales_df[date_col_sales] >= cutoff]
                
                if not recent_sales.empty:
                    # Get top selling products in last 7 days
                    top_products = recent_sales.groupby(product_col_sales)[qty_col_sales].sum().nlargest(10)
                    
                    for product_name, qty_sold in top_products.items():
                        product = products_df[products_df["name"] == product_name]
                        if not product.empty:
                            current_stock = safe_int(product.iloc[0]["stock"])
                            if current_stock < qty_sold * 0.5:
                                self.inventory_anomalies.append({
                                    "type": "RAPID_STOCK_DEPLETION",
                                    "severity": "HIGH",
                                    "product": product_name,
                                    "stock": current_stock,
                                    "sold_last_7_days": qty_sold,
                                    "message": f"Rapid stock depletion: {product_name} sold {qty_sold} units in 7 days, only {current_stock} left",
                                    "confidence": 70
                                })
        
        # 3. Slow movers with high stock
        if not sales_df.empty:
            product_col_sales = get_product_column(sales_df)
            date_col_sales = get_date_column(sales_df)
            if product_col_sales:
                cutoff = datetime.now() - timedelta(days=90)
                sales_df[date_col_sales] = pd.to_datetime(sales_df[date_col_sales], errors="coerce")
                recent_sales = sales_df[sales_df[date_col_sales] >= cutoff]
                
                sold_products = set(recent_sales[product_col_sales].unique()) if not recent_sales.empty else set()
                
                for _, product in products_df.iterrows():
                    product_name = product.get("name", "")
                    stock = safe_int(product.get("stock", 0))
                    
                    if product_name not in sold_products and stock > 10:
                        self.inventory_anomalies.append({
                            "type": "DEAD_STOCK",
                            "severity": "MEDIUM",
                            "product": product_name,
                            "stock": stock,
                            "message": f"Dead stock: {product_name} has {stock} units with no sales in 90 days",
                            "confidence": 80
                        })
        
        return self.inventory_anomalies
    
    def detect_price_anomalies(self, products_df, purchases_df):
        """Detect anomalies in pricing"""
        
        self.price_anomalies = []
        
        if products_df.empty:
            return self.price_anomalies
        
        # Convert price and cost to float
        products_df["price"] = products_df["price"].apply(convert_decimal_to_float)
        products_df["cost"] = products_df["cost"].apply(convert_decimal_to_float)
        
        # 1. Products where cost > price (selling at loss)
        loss_products = products_df[products_df["cost"] > products_df["price"]]
        if not loss_products.empty:
            for _, product in loss_products.iterrows():
                self.price_anomalies.append({
                    "type": "NEGATIVE_MARGIN",
                    "severity": "HIGH",
                    "product": product.get("name", "Unknown"),
                    "cost": product["cost"],
                    "price": product["price"],
                    "loss_per_unit": product["cost"] - product["price"],
                    "message": f"Selling at loss: {product.get('name', 'Unknown')} (Cost: ${product['cost']:.2f}, Price: ${product['price']:.2f})",
                    "confidence": 100
                })
        
        # 2. Products with price > cost * 3 (high margin, might be overpriced)
        high_margin = products_df[products_df["price"] > products_df["cost"] * 3]
        if not high_margin.empty:
            for _, product in high_margin.iterrows():
                margin_pct = ((product["price"] - product["cost"]) / product["cost"] * 100) if product["cost"] > 0 else 0
                self.price_anomalies.append({
                    "type": "HIGH_MARGIN",
                    "severity": "LOW",
                    "product": product.get("name", "Unknown"),
                    "cost": product["cost"],
                    "price": product["price"],
                    "margin": margin_pct,
                    "message": f"Very high margin: {product.get('name', 'Unknown')} ({margin_pct:.0f}% markup)",
                    "confidence": 60
                })
        
        # 3. Price changes (if purchase data available)
        if not purchases_df.empty and "product_name" in purchases_df.columns and "cost_price" in purchases_df.columns:
            purchases_df["cost_price"] = purchases_df["cost_price"].apply(convert_decimal_to_float)
            # Group by product and check price variations
            for product_name, group in purchases_df.groupby("product_name"):
                if len(group) > 1:
                    costs = group["cost_price"].unique()
                    if len(costs) > 1:
                        cost_range = max(costs) - min(costs)
                        if cost_range > 5:
                            self.price_anomalies.append({
                                "type": "PRICE_VOLATILITY",
                                "severity": "MEDIUM",
                                "product": product_name,
                                "min_cost": min(costs),
                                "max_cost": max(costs),
                                "message": f"Price volatility: {product_name} cost varies from ${min(costs):.2f} to ${max(costs):.2f}",
                                "confidence": 70
                            })
        
        return self.price_anomalies
    
    def detect_financial_anomalies(self, expenses_df, cash_df, purchases_df):
        """Detect anomalies in financial data"""
        
        self.financial_anomalies = []
        
        # 1. Unusually high expenses
        if not expenses_df.empty and "amount" in expenses_df.columns:
            expenses_df["amount"] = expenses_df["amount"].apply(convert_decimal_to_float)
            date_col = get_date_column(expenses_df)
            if date_col:
                expenses_df[date_col] = pd.to_datetime(expenses_df[date_col], errors="coerce")
                cutoff = datetime.now() - timedelta(days=30)
                monthly_expenses = expenses_df[expenses_df[date_col] >= cutoff]
                
                if not monthly_expenses.empty:
                    # Check for individual high expenses
                    threshold = monthly_expenses["amount"].quantile(0.90)
                    high_expenses = monthly_expenses[monthly_expenses["amount"] > threshold]
                    
                    for _, row in high_expenses.iterrows():
                        self.financial_anomalies.append({
                            "type": "HIGH_EXPENSE",
                            "severity": "MEDIUM",
                            "date": row[date_col],
                            "amount": row["amount"],
                            "category": row.get("category", "Unknown"),
                            "description": row.get("description", "N/A"),
                            "message": f"Unusually high expense: ${row['amount']:,.2f} ({row.get('category', 'Unknown')})",
                            "confidence": 75
                        })
        
        # 2. Cash variance (if cash data available)
        if not cash_df.empty and "amount" in cash_df.columns:
            cash_df["amount"] = cash_df["amount"].apply(convert_decimal_to_float)
            # Check for negative cash (shouldn't happen)
            negative_cash = cash_df[cash_df["amount"] < 0]
            if not negative_cash.empty:
                for _, row in negative_cash.head(5).iterrows():
                    self.financial_anomalies.append({
                        "type": "NEGATIVE_CASH",
                        "severity": "CRITICAL",
                        "date": row.get("date", "Unknown"),
                        "amount": row["amount"],
                        "message": f"Negative cash transaction: ${row['amount']:,.2f}",
                        "confidence": 100
                    })
        
        # 3. Missing entries (gaps in cash register)
        if not cash_df.empty and "date" in cash_df.columns:
            cash_df["date"] = pd.to_datetime(cash_df["date"], errors="coerce")
            cash_dates = set(cash_df["date"].dt.date)
            all_dates = pd.date_range(start=datetime.now() - timedelta(days=7), end=datetime.now()).date
            missing_dates = [d for d in all_dates if d not in cash_dates]
            
            if len(missing_dates) > 2:
                self.financial_anomalies.append({
                    "type": "MISSING_CASH_ENTRIES",
                    "severity": "HIGH",
                    "missing_days": len(missing_dates),
                    "message": f"{len(missing_dates)} days with no cash register entries",
                    "confidence": 60
                })
        
        return self.financial_anomalies
    
    def detect_customer_anomalies(self, customers_df, sales_df):
        """Detect anomalies in customer behavior"""
        
        self.customer_anomalies = []
        
        if customers_df.empty or sales_df.empty:
            return self.customer_anomalies
        
        customer_col = get_customer_column(sales_df)
        amount_col = get_amount_column(sales_df)
        date_col = get_date_column(sales_df)
        
        if customer_col is None or amount_col is None or date_col is None:
            return self.customer_anomalies
        
        # Convert amount to float
        sales_df[amount_col] = sales_df[amount_col].apply(convert_decimal_to_float)
        
        # 1. High-value customers with no recent purchases
        if "total_spent" in customers_df.columns:
            customers_df["total_spent"] = customers_df["total_spent"].apply(convert_decimal_to_float)
            high_value = customers_df[customers_df["total_spent"] > 500]
            
            if not high_value.empty:
                high_value_names = set(high_value["customer_name"].tolist()) if "customer_name" in high_value.columns else set()
                
                cutoff = datetime.now() - timedelta(days=60)
                sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                recent_sales = sales_df[sales_df[date_col] >= cutoff]
                
                recent_customers = set(recent_sales[customer_col].unique()) if not recent_sales.empty else set()
                
                at_risk = high_value_names - recent_customers
                
                for name in at_risk:
                    customer_data = high_value[high_value["customer_name"] == name]
                    if not customer_data.empty:
                        self.customer_anomalies.append({
                            "type": "HIGH_VALUE_AT_RISK",
                            "severity": "HIGH",
                            "customer": name,
                            "total_spent": customer_data.iloc[0]["total_spent"],
                            "message": f"High-value customer at risk: {name} (${customer_data.iloc[0]['total_spent']:,.2f} spent, no purchase in 60 days)",
                            "confidence": 85
                        })
        
        # 2. Customers with unusually high recent spending
        if date_col:
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=30)
            recent_sales = sales_df[sales_df[date_col] >= cutoff]
            
            if not recent_sales.empty and customer_col and amount_col:
                customer_spending = recent_sales.groupby(customer_col)[amount_col].sum().reset_index()
                threshold = customer_spending[amount_col].quantile(0.95)
                
                high_spenders = customer_spending[customer_spending[amount_col] > threshold]
                
                for _, row in high_spenders.iterrows():
                    self.customer_anomalies.append({
                        "type": "HIGH_RECENT_SPENDING",
                        "severity": "LOW",
                        "customer": row[customer_col],
                        "amount": row[amount_col],
                        "message": f"Unusually high spending: {row[customer_col]} spent ${row[amount_col]:,.2f} in 30 days",
                        "confidence": 60
                    })
        
        return self.customer_anomalies
    
    def run_full_analysis(self, sales_df, products_df, customers_df, expenses_df, purchases_df, cash_df):
        """Run all anomaly detection algorithms"""
        
        self.detect_sales_anomalies(sales_df)
        self.detect_inventory_anomalies(products_df, sales_df, purchases_df)
        self.detect_price_anomalies(products_df, purchases_df)
        self.detect_financial_anomalies(expenses_df, cash_df, purchases_df)
        self.detect_customer_anomalies(customers_df, sales_df)
        
        self.last_analysis = datetime.now()
        
        # Combine all anomalies
        all_anomalies = {
            "sales": self.sales_anomalies,
            "inventory": self.inventory_anomalies,
            "price": self.price_anomalies,
            "financial": self.financial_anomalies,
            "customer": self.customer_anomalies,
            "total_count": (
                len(self.sales_anomalies) +
                len(self.inventory_anomalies) +
                len(self.price_anomalies) +
                len(self.financial_anomalies) +
                len(self.customer_anomalies)
            ),
            "critical_count": self._count_critical(),
            "analysis_date": self.last_analysis
        }
        
        return all_anomalies
    
    def _count_critical(self):
        """Count critical severity anomalies"""
        count = 0
        for anomaly_list in [
            self.sales_anomalies,
            self.inventory_anomalies,
            self.price_anomalies,
            self.financial_anomalies,
            self.customer_anomalies
        ]:
            count += sum(1 for a in anomaly_list if a.get("severity") == "CRITICAL")
        return count
    
    def get_summary(self):
        """Get summary of anomalies"""
        return {
            "total": self._count_total(),
            "critical": self._count_critical(),
            "high": self._count_by_severity("HIGH"),
            "medium": self._count_by_severity("MEDIUM"),
            "low": self._count_by_severity("LOW"),
            "by_type": self._count_by_type()
        }
    
    def _count_total(self):
        """Count total anomalies"""
        count = 0
        for anomaly_list in [
            self.sales_anomalies,
            self.inventory_anomalies,
            self.price_anomalies,
            self.financial_anomalies,
            self.customer_anomalies
        ]:
            count += len(anomaly_list)
        return count
    
    def _count_by_severity(self, severity):
        """Count anomalies by severity"""
        count = 0
        for anomaly_list in [
            self.sales_anomalies,
            self.inventory_anomalies,
            self.price_anomalies,
            self.financial_anomalies,
            self.customer_anomalies
        ]:
            count += sum(1 for a in anomaly_list if a.get("severity") == severity)
        return count
    
    def _count_by_type(self):
        """Count anomalies by type"""
        type_counts = {}
        for anomaly_list in [
            self.sales_anomalies,
            self.inventory_anomalies,
            self.price_anomalies,
            self.financial_anomalies,
            self.customer_anomalies
        ]:
            for anomaly in anomaly_list:
                anomaly_type = anomaly.get("type", "UNKNOWN")
                type_counts[anomaly_type] = type_counts.get(anomaly_type, 0) + 1
        return type_counts


# ==============================
# HELPER FUNCTIONS (continued)
# ==============================

def get_product_column(df):
    """Find product name column"""
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in df.columns:
            return col
    return None


def get_quantity_column(df):
    """Find quantity column"""
    if df is None or df.empty:
        return None
    for col in ["items", "quantity", "qty", "item_count"]:
        if col in df.columns:
            return col
    return None


def get_customer_column(df):
    """Find customer column"""
    if df is None or df.empty:
        return None
    for col in ["customer", "customer_name", "client", "buyer"]:
        if col in df.columns:
            return col
    return None


# ==============================
# ANOMALY DETECTION DASHBOARD
# ==============================

def anomaly_detection_dashboard():
    """Advanced Anomaly Detection Dashboard"""
    
    st.title("🚨 Advanced Anomaly Detection")
    st.caption("AI-powered detection of unusual patterns in your business data")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access anomaly detection.")
        return
    
    # Load data
    with st.spinner("Loading data..."):
        sales_df = load_sales()
        products_df = load_products()
        customers_df = load_customers()
        expenses_df = load_expenses()
        purchases_df = load_purchases()
        cash_df = load_cash()
    
    if sales_df.empty:
        st.warning("No sales data available. Please complete some transactions first.")
        return
    
    # Initialize detector
    if "anomaly_detector" not in st.session_state:
        st.session_state.anomaly_detector = AnomalyDetector()
        st.session_state.anomalies_detected = False
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3 = st.tabs([
        "📊 Overview",
        "🔍 Detected Anomalies",
        "📈 Trends & Patterns"
    ])
    
    # ==============================
    # TAB 1: OVERVIEW
    # ==============================
    with tab1:
        st.markdown("## 📊 Anomaly Detection Overview")
        
        # Run detection button
        col1, col2 = st.columns([3, 1])
        with col1:
            days = st.slider("Analysis Period (days)", 7, 90, 30)
        with col2:
            if st.button("🔍 Run Detection", type="primary", use_container_width=True):
                with st.spinner("Analyzing data..."):
                    results = st.session_state.anomaly_detector.run_full_analysis(
                        sales_df, products_df, customers_df, 
                        expenses_df, purchases_df, cash_df
                    )
                    st.session_state.anomalies_detected = True
                    st.session_state.anomaly_results = results
                    st.success(f"✅ Analysis complete! Found {results['total_count']} anomalies")
                    st.balloons()
                    st.rerun()
        
        # Show summary if anomalies detected
        if st.session_state.anomalies_detected:
            results = st.session_state.anomaly_results
            summary = st.session_state.anomaly_detector.get_summary()
            
            st.markdown("### 📊 Anomaly Summary")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📊 Total Anomalies", summary.get("total", 0))
            with col2:
                st.metric("🚨 Critical", summary.get("critical", 0), delta="⚠️" if summary.get("critical", 0) > 0 else "✅")
            with col3:
                st.metric("🔴 High", summary.get("high", 0))
            with col4:
                st.metric("🟡 Medium", summary.get("medium", 0))
            
            # Breakdown by type
            if summary.get("by_type"):
                st.markdown("### 📈 Anomalies by Type")
                
                type_data = pd.DataFrame({
                    "Type": list(summary["by_type"].keys()),
                    "Count": list(summary["by_type"].values())
                })
                
                fig = px.pie(
                    type_data,
                    values="Count",
                    names="Type",
                    title="Anomaly Distribution by Type",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # Analysis date
            st.caption(f"🔍 Last analysis: {results.get('analysis_date', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Quick actions
            st.markdown("---")
            st.markdown("### ⚡ Quick Actions")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📧 Send Anomaly Report", use_container_width=True):
                    st.info("Anomaly report would be sent to configured recipients")
            with col2:
                if st.button("📥 Export Anomalies", use_container_width=True):
                    st.info("Exporting anomalies data...")
        else:
            st.info("🔍 Click 'Run Detection' to analyze your data for anomalies")
    
    # ==============================
    # TAB 2: DETECTED ANOMALIES
    # ==============================
    with tab2:
        st.markdown("## 🔍 Detected Anomalies")
        
        if not st.session_state.anomalies_detected:
            st.warning("⚠️ Run anomaly detection first in the Overview tab.")
        else:
            # Get all anomalies by category
            anomalies = {
                "Sales": st.session_state.anomaly_detector.sales_anomalies,
                "Inventory": st.session_state.anomaly_detector.inventory_anomalies,
                "Pricing": st.session_state.anomaly_detector.price_anomalies,
                "Financial": st.session_state.anomaly_detector.financial_anomalies,
                "Customer": st.session_state.anomaly_detector.customer_anomalies
            }
            
            # Category filter
            selected_category = st.selectbox(
                "Filter by Category",
                ["All"] + list(anomalies.keys())
            )
            
            # Severity filter
            severity_filter = st.selectbox(
                "Filter by Severity",
                ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
            )
            
            # Display anomalies
            all_anomalies = []
            
            for category, anomaly_list in anomalies.items():
                if selected_category != "All" and category != selected_category:
                    continue
                
                for anomaly in anomaly_list:
                    severity = anomaly.get("severity", "UNKNOWN")
                    if severity_filter != "All" and severity != severity_filter:
                        continue
                    
                    all_anomalies.append({
                        "Category": category,
                        "Severity": severity,
                        "Type": anomaly.get("type", "UNKNOWN"),
                        "Message": anomaly.get("message", ""),
                        "Date": anomaly.get("date", "N/A"),
                        "Confidence": anomaly.get("confidence", 0)
                    })
            
            if all_anomalies:
                df = pd.DataFrame(all_anomalies)
                
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Confidence": st.column_config.ProgressColumn("Confidence %", min_value=0, max_value=100),
                        "Severity": st.column_config.TextColumn("Severity")
                    }
                )
                
                # Critical anomalies alert
                critical_count = len(df[df["Severity"] == "CRITICAL"])
                high_count = len(df[df["Severity"] == "HIGH"])
                
                if critical_count > 0:
                    st.error(f"🚨 {critical_count} CRITICAL anomalies require immediate attention!")
                if high_count > 0:
                    st.warning(f"⚠️ {high_count} HIGH severity anomalies need review")
                
                # Export
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Anomalies Report (CSV)",
                    data=csv,
                    file_name=f"anomalies_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.success("✅ No anomalies found matching the filters!")
    
    # ==============================
    # TAB 3: TRENDS & PATTERNS
    # ==============================
    with tab3:
        st.markdown("## 📈 Trends & Patterns")
        
        if not sales_df.empty:
            date_col = get_date_column(sales_df)
            amount_col = get_amount_column(sales_df)
            
            if date_col and amount_col:
                sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                sales_df = sales_df.dropna(subset=[date_col])
                
                # Convert amount to float for plotting
                sales_df[amount_col] = sales_df[amount_col].apply(convert_decimal_to_float)
                
                # Daily sales trend
                daily_sales = sales_df.groupby(sales_df[date_col].dt.date)[amount_col].sum().reset_index()
                daily_sales.columns = ["date", "sales"]
                
                # Add moving averages
                if len(daily_sales) >= 7:
                    daily_sales["ma_7"] = daily_sales["sales"].rolling(window=7, min_periods=1).mean()
                    daily_sales["ma_30"] = daily_sales["sales"].rolling(window=30, min_periods=1).mean()
                    
                    # Detect anomalies in the trend
                    daily_sales["is_anomaly"] = False
                    mean = daily_sales["sales"].mean()
                    std = daily_sales["sales"].std()
                    
                    if std > 0:
                        daily_sales["z_score"] = (daily_sales["sales"] - mean) / std
                        daily_sales["is_anomaly"] = daily_sales["z_score"].abs() > 2.5
                    
                    # Plot
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=daily_sales["date"],
                        y=daily_sales["sales"],
                        mode="lines+markers",
                        name="Daily Sales",
                        line=dict(color="#6366F1", width=1),
                        opacity=0.6
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=daily_sales["date"],
                        y=daily_sales["ma_7"],
                        mode="lines",
                        name="7-Day Average",
                        line=dict(color="#f59e0b", width=2)
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=daily_sales["date"],
                        y=daily_sales["ma_30"],
                        mode="lines",
                        name="30-Day Average",
                        line=dict(color="#10b981", width=2)
                    ))
                    
                    # Highlight anomalies
                    anomaly_points = daily_sales[daily_sales["is_anomaly"]]
                    if not anomaly_points.empty:
                        fig.add_trace(go.Scatter(
                            x=anomaly_points["date"],
                            y=anomaly_points["sales"],
                            mode="markers",
                            name="Anomaly Detected",
                            marker=dict(color="red", size=12, symbol="x")
                        ))
                    
                    fig.update_layout(
                        title="Sales Trend with Anomaly Detection",
                        xaxis_title="Date",
                        yaxis_title="Sales ($)",
                        height=400,
                        hovermode="x unified"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Stats
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("📊 Avg Daily Sales", f"${daily_sales['sales'].mean():,.2f}")
                    with col2:
                        st.metric("📈 Trend", "Increasing" if daily_sales['sales'].iloc[-1] > daily_sales['sales'].iloc[0] else "Decreasing")
                    with col3:
                        st.metric("🔍 Anomalies Found", len(anomaly_points))
                    
                    # Seasonality detection
                    st.markdown("### 📅 Day of Week Pattern")
                    
                    daily_sales["day_of_week"] = daily_sales["date"].apply(lambda x: x.weekday())
                    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    daily_sales["day_name"] = daily_sales["day_of_week"].apply(lambda x: day_names[x])
                    
                    weekly_avg = daily_sales.groupby("day_name")["sales"].mean().reset_index()
                    
                    fig = px.bar(
                        weekly_avg,
                        x="day_name",
                        y="sales",
                        title="Average Sales by Day of Week",
                        color="sales",
                        color_continuous_scale="Viridis",
                        text="sales"
                    )
                    fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True)


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    anomaly_detection_dashboard()