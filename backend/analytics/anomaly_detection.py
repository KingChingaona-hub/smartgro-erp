# backend/analytics/anomaly_detection.py
"""
Advanced Anomaly Detection — branch-aware dashboard.

The AnomalyDetector class takes DataFrames, so it stays branch-agnostic.
The dashboard scopes every loader to a single branch (or __ALL__) and passes
the scoped frames into the detector.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_purchases,
    load_expenses,
    load_customers,
    load_branches,
    to_float,
)

try:
    from backend.core.db_adapter import load_cash
except ImportError:
    def load_cash(branch_id=None):
        return pd.DataFrame()


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
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
    """Call loader per branch when __ALL__, else once with branch_id."""
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


def _branch_label(branch_id):
    if _is_all_branches(branch_id):
        return "All Branches"
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                return f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()
    except Exception:
        pass
    return str(branch_id)


# ==============================
# HELPER FUNCTIONS
# ==============================
def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_date_column(df):
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in df.columns:
            return col
    return None


def get_product_column(df):
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "Product", "item_name"]:
        if col in df.columns:
            return col
    return None


def get_quantity_column(df):
    if df is None or df.empty:
        return None
    for col in ["items", "quantity", "qty", "item_count"]:
        if col in df.columns:
            return col
    return None


def get_customer_column(df):
    if df is None or df.empty:
        return None
    for col in ["customer", "customer_name", "client", "buyer"]:
        if col in df.columns:
            return col
    return None


def clean_to_float_list(values):
    result = []
    if values is None:
        return result
    for val in values:
        try:
            if val is not None and val != '' and val != 'nan' and val != 'None':
                result.append(float(val))
            else:
                result.append(0.0)
        except (TypeError, ValueError):
            result.append(0.0)
    return result


def safe_quantile(values, q):
    clean_values = clean_to_float_list(values)
    if len(clean_values) == 0:
        return 0.0
    try:
        arr = np.array(clean_values, dtype=np.float64)
        return float(np.percentile(arr, q * 100))
    except Exception:
        try:
            sorted_vals = sorted(clean_values)
            idx = int(q * (len(sorted_vals) - 1))
            return sorted_vals[idx]
        except Exception:
            return 0.0


def safe_mean(values):
    clean_values = clean_to_float_list(values)
    if len(clean_values) == 0:
        return 0.0
    try:
        return float(np.mean(clean_values))
    except Exception:
        return sum(clean_values) / len(clean_values) if clean_values else 0.0


def safe_std(values):
    clean_values = clean_to_float_list(values)
    if len(clean_values) == 0:
        return 0.0
    try:
        return float(np.std(clean_values))
    except Exception:
        return 0.0


def safe_sum(values):
    clean_values = clean_to_float_list(values)
    return sum(clean_values)


# ==============================
# ANOMALY DETECTION ENGINE (unchanged logic)
# ==============================
class AnomalyDetector:
    """Detect anomalies in business data using ML."""

    def __init__(self):
        self.sales_anomalies = []
        self.inventory_anomalies = []
        self.price_anomalies = []
        self.financial_anomalies = []
        self.customer_anomalies = []
        self.last_analysis = None

    def detect_sales_anomalies(self, sales_df, days=30):
        self.sales_anomalies = []
        if sales_df is None or sales_df.empty:
            return self.sales_anomalies

        date_col = get_date_column(sales_df)
        amount_col = get_amount_column(sales_df)
        if date_col is None or amount_col is None:
            return self.sales_anomalies

        sales_data = []
        for _, row in sales_df.iterrows():
            try:
                date_val = pd.to_datetime(row[date_col], errors='coerce')
                if pd.notna(date_val):
                    sales_data.append({
                        'date': date_val,
                        'amount': safe_float(row[amount_col]),
                        'receipt_no': row.get('receipt_no', 'N/A'),
                        'customer': row.get('customer', 'N/A'),
                    })
            except Exception:
                continue

        if not sales_data:
            return self.sales_anomalies

        cutoff = datetime.now() - timedelta(days=days)
        recent_sales = [s for s in sales_data if s['date'] >= cutoff]
        if not recent_sales:
            return self.sales_anomalies

        # Daily sales anomaly (Z-score)
        daily_dict = {}
        for sale in recent_sales:
            date_key = sale['date'].date()
            daily_dict[date_key] = daily_dict.get(date_key, 0.0) + sale['amount']

        dates = sorted(daily_dict.keys())
        sales_values = [daily_dict[d] for d in dates]

        if len(sales_values) >= 7:
            mean_sales = safe_mean(sales_values)
            std_sales = safe_std(sales_values)
            if std_sales > 0:
                for date, sales_value in zip(dates, sales_values):
                    z_score = (sales_value - mean_sales) / std_sales
                    if abs(z_score) > 2.5:
                        self.sales_anomalies.append({
                            "type": "SALES_SPIKE" if z_score > 0 else "SALES_DROP",
                            "severity": "HIGH" if abs(z_score) > 3.5 else "MEDIUM",
                            "date": date,
                            "value": sales_value,
                            "expected": mean_sales,
                            "z_score": z_score,
                            "message": (
                                f"{'Spike' if z_score > 0 else 'Drop'} detected on {date}: "
                                f"${sales_value:,.2f} vs expected ${mean_sales:,.2f}"
                            ),
                            "confidence": min(100, abs(z_score) * 20),
                        })

        if len(recent_sales) > 10:
            amount_values = [s['amount'] for s in recent_sales]
            threshold = safe_quantile(amount_values, 0.95)
            for sale in recent_sales:
                if sale['amount'] > threshold:
                    self.sales_anomalies.append({
                        "type": "LARGE_TRANSACTION",
                        "severity": "MEDIUM",
                        "date": sale['date'],
                        "value": sale['amount'],
                        "receipt_no": sale['receipt_no'],
                        "customer": sale['customer'],
                        "message": f"Unusually large transaction: ${sale['amount']:,.2f}",
                        "confidence": 80,
                    })

        all_dates = pd.date_range(start=cutoff, end=datetime.now()).date
        sales_dates = set(dates)
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
                    "confidence": 90,
                })

        return self.sales_anomalies

    def detect_inventory_anomalies(self, products_df, sales_df, purchases_df):
        self.inventory_anomalies = []
        if products_df is None or products_df.empty:
            return self.inventory_anomalies

        products = []
        for _, row in products_df.iterrows():
            products.append({
                'name': row.get('name', 'Unknown'),
                'barcode': row.get('barcode', ''),
                'stock': safe_float(row.get('stock', 0)),
                'price': safe_float(row.get('price', 0)),
                'cost': safe_float(row.get('cost', 0)),
            })

        for product in products:
            if product['stock'] < 0:
                self.inventory_anomalies.append({
                    "type": "NEGATIVE_STOCK",
                    "severity": "CRITICAL",
                    "product": product['name'],
                    "barcode": product['barcode'],
                    "stock": product['stock'],
                    "message": f"Negative stock detected: {product['name']} has {product['stock']} units",
                    "confidence": 100,
                })

        if (purchases_df is not None and not purchases_df.empty
                and sales_df is not None and not sales_df.empty):
            date_col = get_date_column(sales_df)
            product_col = get_product_column(sales_df)
            qty_col = get_quantity_column(sales_df)
            if date_col and product_col and qty_col:
                cutoff = datetime.now() - timedelta(days=7)
                sales_data = []
                for _, row in sales_df.iterrows():
                    try:
                        date_val = pd.to_datetime(row[date_col], errors='coerce')
                        if pd.notna(date_val) and date_val >= cutoff:
                            sales_data.append({
                                'product': str(row.get(product_col, '')),
                                'qty': safe_float(row.get(qty_col, 0)),
                            })
                    except Exception:
                        continue
                if sales_data:
                    product_sales = {}
                    for sale in sales_data:
                        if sale['product']:
                            product_sales[sale['product']] = (
                                product_sales.get(sale['product'], 0.0) + sale['qty']
                            )
                    sorted_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:10]
                    for product_name, qty_sold in sorted_products:
                        product = next((p for p in products if p['name'] == product_name), None)
                        if product and product['stock'] < qty_sold * 0.5:
                            self.inventory_anomalies.append({
                                "type": "RAPID_STOCK_DEPLETION",
                                "severity": "HIGH",
                                "product": product_name,
                                "stock": product['stock'],
                                "sold_last_7_days": qty_sold,
                                "message": (
                                    f"Rapid stock depletion: {product_name} sold {qty_sold:.0f} units "
                                    f"in 7 days, only {product['stock']} left"
                                ),
                                "confidence": 70,
                            })

        if sales_df is not None and not sales_df.empty:
            date_col = get_date_column(sales_df)
            product_col = get_product_column(sales_df)
            if date_col and product_col:
                cutoff = datetime.now() - timedelta(days=90)
                sold_products = set()
                for _, row in sales_df.iterrows():
                    try:
                        date_val = pd.to_datetime(row[date_col], errors='coerce')
                        if pd.notna(date_val) and date_val >= cutoff:
                            sold_products.add(str(row.get(product_col, '')))
                    except Exception:
                        continue
                for product in products:
                    if product['name'] not in sold_products and product['stock'] > 10:
                        self.inventory_anomalies.append({
                            "type": "DEAD_STOCK",
                            "severity": "MEDIUM",
                            "product": product['name'],
                            "stock": product['stock'],
                            "message": f"Dead stock: {product['name']} has {product['stock']} units with no sales in 90 days",
                            "confidence": 80,
                        })

        return self.inventory_anomalies

    def detect_price_anomalies(self, products_df, purchases_df):
        self.price_anomalies = []
        if products_df is None or products_df.empty:
            return self.price_anomalies

        products = []
        for _, row in products_df.iterrows():
            products.append({
                'name': row.get('name', 'Unknown'),
                'price': safe_float(row.get('price', 0)),
                'cost': safe_float(row.get('cost', 0)),
            })

        for product in products:
            if product['cost'] > product['price']:
                self.price_anomalies.append({
                    "type": "NEGATIVE_MARGIN",
                    "severity": "HIGH",
                    "product": product['name'],
                    "cost": product['cost'],
                    "price": product['price'],
                    "loss_per_unit": product['cost'] - product['price'],
                    "message": (
                        f"Selling at loss: {product['name']} "
                        f"(Cost: ${product['cost']:.2f}, Price: ${product['price']:.2f})"
                    ),
                    "confidence": 100,
                })
            if product['cost'] > 0 and product['price'] > product['cost'] * 3:
                margin_pct = ((product['price'] - product['cost']) / product['cost'] * 100)
                self.price_anomalies.append({
                    "type": "HIGH_MARGIN",
                    "severity": "LOW",
                    "product": product['name'],
                    "cost": product['cost'],
                    "price": product['price'],
                    "margin": margin_pct,
                    "message": f"Very high margin: {product['name']} ({margin_pct:.0f}% markup)",
                    "confidence": 60,
                })

        if (purchases_df is not None and not purchases_df.empty
                and "product_name" in purchases_df.columns
                and "cost_price" in purchases_df.columns):
            purchase_data = {}
            for _, row in purchases_df.iterrows():
                product_name = str(row.get('product_name', ''))
                cost = safe_float(row.get('cost_price', 0))
                if product_name:
                    purchase_data.setdefault(product_name, []).append(cost)
            for product_name, costs in purchase_data.items():
                if len(costs) > 1:
                    unique_costs = list(set(costs))
                    if len(unique_costs) > 1:
                        cost_range = max(unique_costs) - min(unique_costs)
                        if cost_range > 5:
                            self.price_anomalies.append({
                                "type": "PRICE_VOLATILITY",
                                "severity": "MEDIUM",
                                "product": product_name,
                                "min_cost": min(unique_costs),
                                "max_cost": max(unique_costs),
                                "message": (
                                    f"Price volatility: {product_name} cost varies from "
                                    f"${min(unique_costs):.2f} to ${max(unique_costs):.2f}"
                                ),
                                "confidence": 70,
                            })

        return self.price_anomalies

    def detect_financial_anomalies(self, expenses_df, cash_df, purchases_df):
        self.financial_anomalies = []

        if expenses_df is not None and not expenses_df.empty and "amount" in expenses_df.columns:
            expenses_data = []
            date_col = get_date_column(expenses_df)
            if date_col:
                cutoff = datetime.now() - timedelta(days=30)
                for _, row in expenses_df.iterrows():
                    try:
                        date_val = pd.to_datetime(row[date_col], errors='coerce')
                        if pd.notna(date_val) and date_val >= cutoff:
                            expenses_data.append({
                                'date': date_val,
                                'amount': safe_float(row.get('amount', 0)),
                                'category': row.get('category', 'Unknown'),
                                'description': row.get('description', 'N/A'),
                            })
                    except Exception:
                        continue
                if expenses_data:
                    amount_values = [e['amount'] for e in expenses_data]
                    threshold = safe_quantile(amount_values, 0.90)
                    for expense in expenses_data:
                        if expense['amount'] > threshold:
                            self.financial_anomalies.append({
                                "type": "HIGH_EXPENSE",
                                "severity": "MEDIUM",
                                "date": expense['date'],
                                "amount": expense['amount'],
                                "category": expense['category'],
                                "description": expense['description'],
                                "message": f"Unusually high expense: ${expense['amount']:,.2f} ({expense['category']})",
                                "confidence": 75,
                            })

        if cash_df is not None and not cash_df.empty and "amount" in cash_df.columns:
            for _, row in cash_df.head(5).iterrows():
                amount_val = safe_float(row.get('amount', 0))
                if amount_val < 0:
                    self.financial_anomalies.append({
                        "type": "NEGATIVE_CASH",
                        "severity": "CRITICAL",
                        "date": row.get('date', 'Unknown'),
                        "amount": amount_val,
                        "message": f"Negative cash transaction: ${amount_val:,.2f}",
                        "confidence": 100,
                    })

        if cash_df is not None and not cash_df.empty and "date" in cash_df.columns:
            cash_dates = set()
            for _, row in cash_df.iterrows():
                try:
                    date_val = pd.to_datetime(row['date'], errors='coerce')
                    if pd.notna(date_val):
                        cash_dates.add(date_val.date())
                except Exception:
                    continue
            all_dates = pd.date_range(
                start=datetime.now() - timedelta(days=7),
                end=datetime.now(),
            ).date
            missing_dates = [d for d in all_dates if d not in cash_dates]
            if len(missing_dates) > 2:
                self.financial_anomalies.append({
                    "type": "MISSING_CASH_ENTRIES",
                    "severity": "HIGH",
                    "missing_days": len(missing_dates),
                    "message": f"{len(missing_dates)} days with no cash register entries",
                    "confidence": 60,
                })

        return self.financial_anomalies

    def detect_customer_anomalies(self, customers_df, sales_df):
        self.customer_anomalies = []
        if (customers_df is None or customers_df.empty
                or sales_df is None or sales_df.empty):
            return self.customer_anomalies

        customers = []
        for _, row in customers_df.iterrows():
            customers.append({
                'name': row.get('customer_name', ''),
                'total_spent': safe_float(row.get('total_spent', 0)),
            })

        customer_col = get_customer_column(sales_df)
        amount_col = get_amount_column(sales_df)
        date_col = get_date_column(sales_df)

        if customer_col is None or amount_col is None or date_col is None:
            return self.customer_anomalies

        high_value = [c for c in customers if c['total_spent'] > 500]
        if high_value:
            cutoff = datetime.now() - timedelta(days=60)
            recent_customers = set()
            for _, row in sales_df.iterrows():
                try:
                    date_val = pd.to_datetime(row[date_col], errors='coerce')
                    if pd.notna(date_val) and date_val >= cutoff:
                        recent_customers.add(str(row.get(customer_col, '')))
                except Exception:
                    continue
            for customer in high_value:
                if customer['name'] not in recent_customers:
                    self.customer_anomalies.append({
                        "type": "HIGH_VALUE_AT_RISK",
                        "severity": "HIGH",
                        "customer": customer['name'],
                        "total_spent": customer['total_spent'],
                        "message": (
                            f"High-value customer at risk: {customer['name']} "
                            f"(${customer['total_spent']:,.2f} spent, no purchase in 60 days)"
                        ),
                        "confidence": 85,
                    })

        cutoff = datetime.now() - timedelta(days=30)
        customer_spending = {}
        for _, row in sales_df.iterrows():
            try:
                date_val = pd.to_datetime(row[date_col], errors='coerce')
                if pd.notna(date_val) and date_val >= cutoff:
                    customer = str(row.get(customer_col, ''))
                    amount = safe_float(row.get(amount_col, 0))
                    if customer:
                        customer_spending[customer] = customer_spending.get(customer, 0.0) + amount
            except Exception:
                continue
        if customer_spending:
            spending_values = list(customer_spending.values())
            threshold = safe_quantile(spending_values, 0.95)
            for customer, amount in customer_spending.items():
                if amount > threshold:
                    self.customer_anomalies.append({
                        "type": "HIGH_RECENT_SPENDING",
                        "severity": "LOW",
                        "customer": customer,
                        "amount": amount,
                        "message": f"Unusually high spending: {customer} spent ${amount:,.2f} in 30 days",
                        "confidence": 60,
                    })

        return self.customer_anomalies

    def run_full_analysis(self, sales_df, products_df, customers_df,
                          expenses_df, purchases_df, cash_df):
        self.detect_sales_anomalies(sales_df)
        self.detect_inventory_anomalies(products_df, sales_df, purchases_df)
        self.detect_price_anomalies(products_df, purchases_df)
        self.detect_financial_anomalies(expenses_df, cash_df, purchases_df)
        self.detect_customer_anomalies(customers_df, sales_df)

        self.last_analysis = datetime.now()

        return {
            "sales": self.sales_anomalies,
            "inventory": self.inventory_anomalies,
            "price": self.price_anomalies,
            "financial": self.financial_anomalies,
            "customer": self.customer_anomalies,
            "total_count": (
                len(self.sales_anomalies) + len(self.inventory_anomalies)
                + len(self.price_anomalies) + len(self.financial_anomalies)
                + len(self.customer_anomalies)
            ),
            "critical_count": self._count_critical(),
            "analysis_date": self.last_analysis,
        }

    def _count_critical(self):
        count = 0
        for lst in [self.sales_anomalies, self.inventory_anomalies, self.price_anomalies,
                    self.financial_anomalies, self.customer_anomalies]:
            count += sum(1 for a in lst if a.get("severity") == "CRITICAL")
        return count

    def get_summary(self):
        return {
            "total": self._count_total(),
            "critical": self._count_critical(),
            "high": self._count_by_severity("HIGH"),
            "medium": self._count_by_severity("MEDIUM"),
            "low": self._count_by_severity("LOW"),
            "by_type": self._count_by_type(),
        }

    def _count_total(self):
        count = 0
        for lst in [self.sales_anomalies, self.inventory_anomalies, self.price_anomalies,
                    self.financial_anomalies, self.customer_anomalies]:
            count += len(lst)
        return count

    def _count_by_severity(self, severity):
        count = 0
        for lst in [self.sales_anomalies, self.inventory_anomalies, self.price_anomalies,
                    self.financial_anomalies, self.customer_anomalies]:
            count += sum(1 for a in lst if a.get("severity") == severity)
        return count

    def _count_by_type(self):
        type_counts = {}
        for lst in [self.sales_anomalies, self.inventory_anomalies, self.price_anomalies,
                    self.financial_anomalies, self.customer_anomalies]:
            for anomaly in lst:
                anomaly_type = anomaly.get("type", "UNKNOWN")
                type_counts[anomaly_type] = type_counts.get(anomaly_type, 0) + 1
        return type_counts


# ==============================
# DASHBOARD
# ==============================
def anomaly_detection_dashboard():
    st.title("Advanced Anomaly Detection")
    st.caption("AI-powered detection of unusual patterns in your business data — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access anomaly detection.")
        return

    # ---- Branch scope ----
    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        branch_options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})"
            for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            branch_options,
            key="anomaly_branch_scope",
            help="Owners may analyze company-wide or one branch at a time.",
        )
        if choice == "All Branches":
            branch_id = ALL_BRANCHES
            branch_label = "All Branches"
        else:
            m = re.search(r"\(([^)]+)\)\s*$", choice)
            branch_id = m.group(1).strip() if m else choice
            branch_label = choice
    else:
        branch_id = _resolve_branch(None)
        branch_label = _branch_label(branch_id)
        st.info(f"Anomaly detection locked to your branch: **{branch_label}**")

    st.caption(f"Analysis scope: **{branch_label}**")
    st.markdown("---")

    # ---- Scoped loads ----
    with st.spinner("Loading data..."):
        sales_df = _load_scoped(load_sales, branch_id)
        products_df = _load_scoped(load_products, branch_id)
        customers_df = _load_scoped(load_customers, branch_id)
        expenses_df = _load_scoped(load_expenses, branch_id)
        purchases_df = _load_scoped(load_purchases, branch_id)
        cash_df = _load_scoped(load_cash, branch_id)

    if sales_df is None or sales_df.empty:
        st.warning(f"No sales data available for {branch_label}. Complete some transactions first.")
        return

    # ---- Detector state (per branch) ----
    detector_key = f"anomaly_detector_{branch_id}"
    results_key = f"anomaly_results_{branch_id}"
    detected_key = f"anomalies_detected_{branch_id}"

    if detector_key not in st.session_state:
        st.session_state[detector_key] = AnomalyDetector()
        st.session_state[detected_key] = False

    tab1, tab2, tab3 = st.tabs(["Overview", "Detected Anomalies", "Trends & Patterns"])

    # ==============================
    # TAB 1: OVERVIEW
    # ==============================
    with tab1:
        st.markdown("## Anomaly Detection Overview")
        st.caption(f"Branch: **{branch_label}**")

        col1, col2 = st.columns([3, 1])
        with col1:
            days = st.slider("Analysis Period (days)", 7, 90, 30, key=f"anomaly_days_{branch_id}")
        with col2:
            if st.button("Run Detection", type="primary", use_container_width=True,
                         key=f"anomaly_run_{branch_id}"):
                with st.spinner(f"Analyzing {branch_label} data..."):
                    results = st.session_state[detector_key].run_full_analysis(
                        sales_df, products_df, customers_df,
                        expenses_df, purchases_df, cash_df,
                    )
                    st.session_state[detected_key] = True
                    st.session_state[results_key] = results
                    st.success(f"Analysis complete for {branch_label}! Found {results['total_count']} anomalies")

        if st.session_state.get(detected_key, False):
            results = st.session_state.get(results_key, {})
            summary = st.session_state[detector_key].get_summary()

            st.markdown("### Anomaly Summary")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Anomalies", summary.get("total", 0))
            with col2:
                critical = summary.get("critical", 0)
                st.metric("Critical", critical, delta="⚠️" if critical > 0 else "✅")
            with col3:
                st.metric("High", summary.get("high", 0))
            with col4:
                st.metric("Medium", summary.get("medium", 0))

            if summary.get("by_type"):
                st.markdown("### Anomalies by Type")
                type_data = pd.DataFrame({
                    "Type": list(summary["by_type"].keys()),
                    "Count": list(summary["by_type"].values()),
                })
                fig = px.pie(
                    type_data, values="Count", names="Type",
                    title=f"Anomaly Distribution — {branch_label}",
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

            st.caption(f"Last analysis: {results.get('analysis_date', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}")

            st.markdown("---")
            st.markdown("### Quick Actions")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Send Anomaly Report", use_container_width=True,
                             key=f"anomaly_send_{branch_id}"):
                    st.info("Anomaly report would be sent to configured recipients")
            with col2:
                if st.button("Export Anomalies", use_container_width=True,
                             key=f"anomaly_export_{branch_id}"):
                    st.info("Exporting anomalies data...")
        else:
            st.info("Click 'Run Detection' to analyze your data for anomalies")

    # ==============================
    # TAB 2: DETECTED ANOMALIES
    # ==============================
    with tab2:
        st.markdown("## Detected Anomalies")
        st.caption(f"Branch: **{branch_label}**")

        if not st.session_state.get(detected_key, False):
            st.warning("Run anomaly detection first in the Overview tab.")
        else:
            detector = st.session_state[detector_key]
            anomalies = {
                "Sales": detector.sales_anomalies,
                "Inventory": detector.inventory_anomalies,
                "Pricing": detector.price_anomalies,
                "Financial": detector.financial_anomalies,
                "Customer": detector.customer_anomalies,
            }

            selected_category = st.selectbox(
                "Filter by Category",
                ["All"] + list(anomalies.keys()),
                key=f"anomaly_cat_{branch_id}",
            )
            severity_filter = st.selectbox(
                "Filter by Severity",
                ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"],
                key=f"anomaly_sev_{branch_id}",
            )

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
                        "Confidence": anomaly.get("confidence", 0),
                    })

            if all_anomalies:
                df = pd.DataFrame(all_anomalies)
                st.dataframe(
                    df, use_container_width=True, hide_index=True,
                    column_config={
                        "Confidence": st.column_config.ProgressColumn(
                            "Confidence %", min_value=0, max_value=100
                        ),
                        "Severity": st.column_config.TextColumn("Severity"),
                    },
                )

                critical_count = len(df[df["Severity"] == "CRITICAL"])
                high_count = len(df[df["Severity"] == "HIGH"])
                if critical_count > 0:
                    st.error(f"{critical_count} CRITICAL anomalies require immediate attention!")
                if high_count > 0:
                    st.warning(f"{high_count} HIGH severity anomalies need review")

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Anomalies Report (CSV)",
                    data=csv,
                    file_name=(
                        f"anomalies_{re.sub(r'[^A-Za-z0-9_-]+', '_', str(branch_id))}_"
                        f"{datetime.now().strftime('%Y%m%d')}.csv"
                    ),
                    mime="text/csv",
                )
            else:
                st.success("No anomalies found matching the filters!")

    # ==============================
    # TAB 3: TRENDS & PATTERNS (now branch-scoped)
    # ==============================
    with tab3:
        st.markdown("## Trends & Patterns")
        st.caption(f"Sales trends for **{branch_label}** with unduplicated revenue (each receipt counted once)")

        if sales_df is None or sales_df.empty:
            st.warning("No sales data available for trend analysis.")
        else:
            date_col = get_date_column(sales_df)
            amount_col = get_amount_column(sales_df)
            receipt_col = "receipt_no" if "receipt_no" in sales_df.columns else None

            if date_col is None or amount_col is None:
                st.warning("Required columns (date or amount) not found in sales data.")
            else:
                working_df = sales_df.copy()
                if receipt_col:
                    working_df = working_df.drop_duplicates(subset=[receipt_col])
                    st.caption(f"📊 Using {len(working_df)} unique receipts (deduplicated)")
                else:
                    st.caption("No receipt_no column found — using all rows")

                sales_data = []
                for _, row in working_df.iterrows():
                    try:
                        date_val = pd.to_datetime(row[date_col], errors='coerce')
                        if pd.notna(date_val):
                            sales_data.append({
                                'date': date_val,
                                'amount': safe_float(row[amount_col]),
                            })
                    except Exception:
                        continue

                if not sales_data:
                    st.warning("No valid sales data found.")
                    return

                daily_dict = {}
                for sale in sales_data:
                    date_key = sale['date'].date()
                    daily_dict[date_key] = daily_dict.get(date_key, 0.0) + sale['amount']

                dates = sorted(daily_dict.keys())
                sales_values = [daily_dict[d] for d in dates]

                if len(sales_values) < 3:
                    st.info("Not enough sales data for trend analysis. Need at least 3 days of data.")
                    return

                ma_7 = []
                ma_30 = []
                for i in range(len(sales_values)):
                    start_7 = max(0, i - 6)
                    ma_7.append(safe_mean(sales_values[start_7:i + 1]))
                    start_30 = max(0, i - 29)
                    ma_30.append(safe_mean(sales_values[start_30:i + 1]))

                daily_sales = pd.DataFrame({
                    'date': dates, 'sales': sales_values, 'ma_7': ma_7, 'ma_30': ma_30,
                })

                mean = safe_mean(sales_values)
                std = safe_std(sales_values)
                daily_sales['is_anomaly'] = False
                if std > 0:
                    z_scores = [(v - mean) / std for v in sales_values]
                    daily_sales['z_score'] = z_scores
                    daily_sales['is_anomaly'] = [abs(z) > 2.5 for z in z_scores]

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=daily_sales['date'], y=daily_sales['sales'],
                    mode="lines+markers", name="Daily Sales",
                    line=dict(color="#6366F1", width=1), opacity=0.6,
                ))
                if len(daily_sales) >= 7:
                    fig.add_trace(go.Scatter(
                        x=daily_sales['date'], y=daily_sales['ma_7'],
                        mode="lines", name="7-Day Average",
                        line=dict(color="#f59e0b", width=2),
                    ))
                if len(daily_sales) >= 30:
                    fig.add_trace(go.Scatter(
                        x=daily_sales['date'], y=daily_sales['ma_30'],
                        mode="lines", name="30-Day Average",
                        line=dict(color="#10b981", width=2),
                    ))
                anomaly_points = daily_sales[daily_sales['is_anomaly']]
                if not anomaly_points.empty:
                    fig.add_trace(go.Scatter(
                        x=anomaly_points['date'], y=anomaly_points['sales'],
                        mode="markers", name="Anomaly Detected",
                        marker=dict(color="red", size=12, symbol="x"),
                    ))
                fig.update_layout(
                    title=f"Sales Trend with Anomaly Detection — {branch_label}",
                    xaxis_title="Date", yaxis_title="Sales ($)",
                    height=400, hovermode="x unified",
                )
                st.plotly_chart(fig, use_container_width=True)

                total_revenue = sum(sales_values)
                avg_daily = safe_mean(sales_values)
                total_days = len(sales_values)

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Revenue", f"${total_revenue:,.2f}")
                with col2:
                    st.metric("Avg Daily Sales", f"${avg_daily:,.2f}")
                with col3:
                    trend = "📈 Increasing" if sales_values[-1] > sales_values[0] else "📉 Decreasing"
                    st.metric("Trend", trend)
                with col4:
                    st.metric("Anomalies Found", len(anomaly_points))

                st.markdown("### Day of Week Pattern")
                day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                weekly_dict = {day: [] for day in day_names}
                for date, value in zip(dates, sales_values):
                    weekly_dict[day_names[date.weekday()]].append(value)
                weekly_avg_data = [{"day_name": day, "sales": safe_mean(weekly_dict[day])} for day in day_names]
                weekly_avg = pd.DataFrame(weekly_avg_data)

                fig2 = px.bar(
                    weekly_avg, x="day_name", y="sales",
                    title=f"Average Sales by Day of Week — {branch_label}",
                    color="sales", color_continuous_scale="Viridis", text="sales",
                )
                fig2.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
                fig2.update_layout(height=300)
                st.plotly_chart(fig2, use_container_width=True)

                st.markdown("### Summary Statistics")
                stats_df = pd.DataFrame({
                    "Metric": ["Total Days", "Average Daily Sales", "Highest Day", "Lowest Day", "Total Revenue"],
                    "Value": [
                        total_days,
                        f"${avg_daily:,.2f}",
                        f"${max(sales_values):,.2f}",
                        f"${min(sales_values):,.2f}",
                        f"${total_revenue:,.2f}",
                    ],
                })
                st.dataframe(stats_df, use_container_width=True, hide_index=True)


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    anomaly_detection_dashboard()