# backend/customers/customer_360_view.py
# Customer 360° View — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Debt source: backend.core.floating_financials (NOT the deleted debtors_engine).

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
import re
import warnings
warnings.filterwarnings('ignore')

from backend.core.db_adapter import (
    load_customers,
    load_sales,
    load_products,
    load_customer_transactions,
    load_branches,
    to_float,
)
from backend.modules.loyalty import get_customer_loyalty_info

# Debt now comes from floating financials
from backend.core.floating_financials import (
    get_credit_records,
    get_credit_summary,
)


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_all_branches(branch_id):
    return isinstance(branch_id, str) and branch_id.upper() == ALL_BRANCHES


def _load_scoped(loader, branch_id, **kwargs):
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


def _branch_slug(branch_id):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_") or "branch"


def _branch_scope_selector(branches_df, key_suffix=""):
    role = st.session_state.get("role", "cashier")
    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})"
            for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            options,
            key=f"c360_branch_scope{key_suffix}",
            help="Owners may view company-wide or one branch at a time.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Customer 360 locked to your branch: **{label}**")
    return session_branch, label


def _load_scoped_debts(branch_id):
    """
    Load debt records for the branch via floating_financials.
    Falls back gracefully if the module doesn't accept branch_id.
    """
    try:
        if _is_all_branches(branch_id):
            try:
                bdf = load_branches()
                frames = []
                for bid in bdf["branch_id"].astype(str).tolist():
                    try:
                        df = get_credit_records(branch_id=bid)
                        if df is not None and not df.empty:
                            frames.append(df)
                    except Exception:
                        continue
                return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            except Exception:
                return get_credit_records()
        try:
            return get_credit_records(branch_id=branch_id)
        except TypeError:
            df = get_credit_records()
            if df is not None and not df.empty and "branch_id" in df.columns:
                df = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            return df
    except Exception as e:
        print(f"[customer_360_view] debt load failed: {e}")
        return pd.DataFrame()


# ==============================
# SAFE CONVERTERS
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


def safe_str(value, default=""):
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default


# ==============================
# COLUMN FINDERS
# ==============================
def get_receipt_column(df):
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
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


def get_customer_column(df):
    if df is None or df.empty:
        return None
    for col in ["customer_name", "customer", "name", "client_name"]:
        if col in df.columns:
            return col
    return None


def get_phone_column(df):
    if df is None or df.empty:
        return None
    for col in ["phone", "customer_phone", "contact", "mobile"]:
        if col in df.columns:
            return col
    return None


def get_date_column(df):
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


# ==============================
# CUSTOMER EXTRACTION
# ==============================
def extract_customers_from_sales(sales_df):
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    customer_col = get_customer_column(sales_df)
    phone_col = get_phone_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    if customer_col is None:
        return pd.DataFrame()

    if receipt_col and receipt_col in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        customer_data = unique_receipts[[customer_col]].copy()
        customer_data["phone"] = (
            unique_receipts[phone_col].astype(str)
            if phone_col and phone_col in sales_df.columns else ""
        )
    else:
        customer_data = sales_df[[customer_col]].copy()
        customer_data["phone"] = (
            sales_df[phone_col].astype(str)
            if phone_col and phone_col in sales_df.columns else ""
        )

    customer_data.columns = ["customer_name", "phone"]
    customer_data = customer_data.drop_duplicates(subset=["customer_name"])
    customer_data = customer_data[
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('walk-in', na=False)
        & ~customer_data["customer_name"].astype(str).str.lower().str.contains('unknown', na=False)
        & (customer_data["customer_name"].astype(str).str.strip() != '')
        & (customer_data["customer_name"].astype(str).str.strip() != 'nan')
        & (customer_data["customer_name"].astype(str).str.strip() != 'None')
    ]
    return customer_data


def get_combined_customers(customers_df, sales_df):
    sales_customers = extract_customers_from_sales(sales_df)
    if not sales_customers.empty:
        return sales_customers

    if customers_df is not None and not customers_df.empty:
        customer_col = get_customer_column(customers_df)
        phone_col = get_phone_column(customers_df)
        if customer_col:
            result = customers_df[[customer_col]].copy()
            result.columns = ["customer_name"]
            result["phone"] = (
                customers_df[phone_col].astype(str)
                if phone_col and phone_col in customers_df.columns else ""
            )
            return result
    return pd.DataFrame()


# ==============================
# COMPLETE PROFILE (branch-scoped)
# ==============================
def get_customer_complete_profile(customer_name, sales_df=None, branch_id=None):
    """
    Get complete 360° profile for a customer.
    Matches on customer name only, within a single branch scope.
    """
    branch_id = _resolve_branch(branch_id)

    if sales_df is None:
        sales_df = _load_scoped(load_sales, branch_id)

    customers_df = _load_scoped(load_customers, branch_id)
    transactions_df = _load_scoped(load_customer_transactions, branch_id)
    debtors_df = _load_scoped_debts(branch_id)

    customer_data = {}
    if sales_df is None or sales_df.empty:
        return None

    customer_col = get_customer_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    amount_col = get_amount_column(sales_df)
    date_col = get_date_column(sales_df)

    if customer_col is None:
        return None

    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.lower() == customer_name.lower()
    ]
    if customer_sales.empty:
        customer_sales = sales_df[
            sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
        ]
    if customer_sales.empty:
        return None

    customer_sales = customer_sales.copy()
    customer_data["customer_name"] = safe_str(
        customer_sales.iloc[0].get(customer_col, customer_name)
    )
    phone_col = get_phone_column(sales_df)
    customer_data["phone"] = (
        safe_str(customer_sales.iloc[0].get(phone_col, ""))
        if phone_col and phone_col in sales_df.columns else ""
    )

    if receipt_col and receipt_col in customer_sales.columns:
        unique_receipts = customer_sales.drop_duplicates(subset=[receipt_col])
        total_transactions = len(unique_receipts)
        total_spent = (
            safe_float(unique_receipts[amount_col].sum())
            if amount_col and amount_col in unique_receipts.columns else 0
        )
        total_items = safe_int(customer_sales["items"].sum()) if "items" in customer_sales.columns else 0
        purchase_history = unique_receipts.copy()
    else:
        unique_receipts = customer_sales
        total_transactions = len(customer_sales)
        total_spent = (
            safe_float(customer_sales[amount_col].sum())
            if amount_col and amount_col in customer_sales.columns else 0
        )
        total_items = safe_int(customer_sales["items"].sum()) if "items" in customer_sales.columns else 0
        purchase_history = customer_sales.copy()

    customer_data["total_transactions"] = total_transactions
    customer_data["total_spent"] = total_spent
    customer_data["total_orders"] = total_transactions
    customer_data["avg_transaction_value"] = (
        total_spent / total_transactions if total_transactions > 0 else 0
    )
    customer_data["total_items"] = total_items

    if date_col:
        customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
        last_date = customer_sales[date_col].max()
        if pd.notna(last_date):
            customer_data["last_purchase_date"] = last_date
            customer_data["days_since_last_purchase"] = (datetime.now() - last_date).days
        else:
            customer_data["days_since_last_purchase"] = 999
    else:
        customer_data["days_since_last_purchase"] = 999

    payment_col = None
    for col in ["payment_method", "payment_type"]:
        if col in customer_sales.columns:
            payment_col = col
            break
    if payment_col:
        customer_data["payment_methods"] = customer_sales[payment_col].unique().tolist()

    customer_data["purchase_history"] = purchase_history.to_dict('records')
    customer_data["branch_id"] = branch_id

    # Loyalty — the loyalty module is already branch-scoped internally
    try:
        loyalty_info = get_customer_loyalty_info(customer_data.get("phone", ""))
        if loyalty_info:
            customer_data.update(loyalty_info)
    except Exception:
        pass

    # Debt from floating_financials
    if debtors_df is not None and not debtors_df.empty:
        debt_customer_col = None
        for col in ["customer_name", "customer"]:
            if col in debtors_df.columns:
                debt_customer_col = col
                break
        if debt_customer_col:
            customer_debts = debtors_df[
                debtors_df[debt_customer_col].astype(str).str.lower() == customer_name.lower()
            ]
            if customer_debts.empty:
                customer_debts = debtors_df[
                    debtors_df[debt_customer_col].astype(str).str.contains(customer_name, case=False, na=False)
                ]
            if not customer_debts.empty:
                balance_col = None
                for col in ["balance", "outstanding", "amount_due"]:
                    if col in customer_debts.columns:
                        balance_col = col
                        break
                if balance_col:
                    customer_data["total_debt"] = safe_float(customer_debts[balance_col].sum())
                    customer_data["has_debt"] = customer_data["total_debt"] > 0
                    customer_data["debt_details"] = customer_debts.to_dict('records')

    # Favorite products
    if transactions_df is not None and not transactions_df.empty:
        trans_customer_col = get_customer_column(transactions_df)
        if trans_customer_col and trans_customer_col in transactions_df.columns:
            customer_transactions = transactions_df[
                transactions_df[trans_customer_col].astype(str).str.lower() == customer_name.lower()
            ]
            if customer_transactions.empty:
                customer_transactions = transactions_df[
                    transactions_df[trans_customer_col].astype(str).str.contains(customer_name, case=False, na=False)
                ]
            if not customer_transactions.empty and "product_name" in customer_transactions.columns:
                favorite_products = (
                    customer_transactions.groupby("product_name")["quantity"]
                    .sum().nlargest(5).to_dict()
                )
                customer_data["favorite_products"] = favorite_products

    return customer_data


# ==============================
# PREDICTIONS
# ==============================
def predict_churn_risk(customer_data):
    risk_score = 0
    risk_factors = []

    days_since = customer_data.get("days_since_last_purchase", 999)
    if days_since is None or days_since > 999:
        days_since = 999

    if days_since > 90:
        risk_score += 40
        risk_factors.append(f"No purchase in {days_since} days")
    elif days_since > 60:
        risk_score += 25
        risk_factors.append(f"No purchase in {days_since} days")
    elif days_since > 30:
        risk_score += 10
        risk_factors.append(f"No purchase in {days_since} days")

    transactions = customer_data.get("total_transactions", 0)
    if transactions <= 1:
        risk_score += 25
        risk_factors.append("Only 1 transaction - low engagement")
    elif transactions <= 3:
        risk_score += 10
        risk_factors.append("Low transaction frequency")

    avg_value = customer_data.get("avg_transaction_value", 0)
    if avg_value < 10:
        risk_score += 15
        risk_factors.append("Low average transaction value")

    if customer_data.get("has_debt", False):
        risk_score += 20
        risk_factors.append("Has outstanding debt")

    if risk_score >= 70:
        risk_level, risk_color = "HIGH", "red"
        recommendation = "Immediate re-engagement campaign needed"
    elif risk_score >= 40:
        risk_level, risk_color = "MEDIUM", "orange"
        recommendation = "Send special offers to encourage repeat purchase"
    elif risk_score >= 20:
        risk_level, risk_color = "LOW", "yellow"
        recommendation = "Monitor and maintain relationship"
    else:
        risk_level, risk_color = "VERY LOW", "green"
        recommendation = "Continue current engagement strategy"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "risk_factors": risk_factors,
        "recommendation": recommendation,
    }


def predict_next_purchase(customer_data):
    purchase_history = customer_data.get("purchase_history", [])

    if purchase_history and len(purchase_history) >= 2:
        dates = []
        for sale in purchase_history:
            for col in ["date", "sale_date", "transaction_date"]:
                if col in sale:
                    try:
                        dates.append(pd.to_datetime(sale[col]))
                        break
                    except Exception:
                        pass
        if len(dates) >= 2:
            dates = sorted(dates)
            date_diffs = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            if date_diffs:
                avg_days_between = np.mean(date_diffs)
                last_purchase = dates[-1]
                predicted_date = last_purchase + timedelta(days=int(avg_days_between))
                days_from_now = (predicted_date - datetime.now()).days
                return {
                    "predicted_date": predicted_date,
                    "days_from_now": max(0, days_from_now),
                    "confidence": "High" if len(date_diffs) >= 3 else "Medium",
                    "avg_days_between": int(avg_days_between),
                }

    return {
        "predicted_date": datetime.now() + timedelta(days=30),
        "days_from_now": 30,
        "confidence": "Low",
        "avg_days_between": 30,
    }


def get_personalized_recommendations(customer_data, branch_id=None):
    branch_id = _resolve_branch(branch_id)
    favorite_products = customer_data.get("favorite_products", {})
    products_df = _load_scoped(load_products, branch_id)
    sales_df = _load_scoped(load_sales, branch_id)

    recommendations = []

    if favorite_products and products_df is not None and not products_df.empty:
        for product_name in list(favorite_products.keys())[:3]:
            product = products_df[products_df["name"] == product_name]
            if not product.empty:
                category = product.iloc[0].get("category", "")
                if category:
                    similar = products_df[
                        (products_df["category"] == category) & (products_df["name"] != product_name)
                    ]
                    for _, p in similar.head(2).iterrows():
                        recommendations.append({
                            "product_name": p.get("name", "Unknown"),
                            "price": safe_float(p.get("price", 0)),
                            "reason": f"Similar to {product_name}",
                            "category": category,
                        })

    if not recommendations and sales_df is not None and not sales_df.empty:
        name_col = get_customer_column(sales_df)
        if name_col and name_col in sales_df.columns:
            top_products = (
                sales_df.groupby(name_col)["items"].sum().nlargest(5).reset_index()
                if "items" in sales_df.columns
                else pd.DataFrame()
            )
            for _, p in top_products.iterrows():
                product_name = p.get(name_col, "Unknown")
                product = (
                    products_df[products_df["name"] == product_name]
                    if products_df is not None and not products_df.empty else pd.DataFrame()
                )
                price = safe_float(product.iloc[0]["price"]) if not product.empty else 0
                recommendations.append({
                    "product_name": product_name,
                    "price": price,
                    "reason": "Popular item",
                    "category": "",
                })

    return recommendations[:6]


def calculate_customer_lifetime_value(customer_data):
    total_spent = safe_float(customer_data.get("total_spent", 0))
    total_orders = safe_int(customer_data.get("total_orders", 0))
    avg_order = total_spent / total_orders if total_orders > 0 else 0

    days_since = customer_data.get("days_since_last_purchase", 365)
    if days_since is None or days_since < 1:
        days_since = 1

    purchase_frequency = (
        (total_orders / days_since) * 365 if total_orders > 0 and days_since > 0 else 0
    )
    purchase_frequency = min(purchase_frequency, 365)
    customer_lifespan = 3
    clv = avg_order * purchase_frequency * customer_lifespan

    return {
        "clv": clv,
        "avg_order_value": avg_order,
        "purchase_frequency": purchase_frequency,
        "estimated_lifespan_years": customer_lifespan,
        "tier": customer_data.get("tier", "BRONZE"),
    }


def get_customer_segment(customer_data):
    total_spent = safe_float(customer_data.get("total_spent", 0))
    total_orders = safe_int(customer_data.get("total_orders", 0))
    days_since = customer_data.get("days_since_last_purchase", 999)
    if days_since is None:
        days_since = 999

    if total_spent >= 500 and total_orders >= 5:
        return "VIP - High Value Loyal"
    if total_spent >= 500:
        return "High Value"
    if total_orders >= 5:
        return "Frequent Buyer"
    if total_spent >= 150:
        return "Regular"
    if days_since > 60:
        return "At Risk"
    if total_orders <= 2:
        return "New Customer"
    return "Standard"


# ==============================
# CUSTOMER 360 DASHBOARD
# ==============================
def customer_360_view(branch_id=None):
    st.title("Customer 360° View")
    st.caption("Complete customer intelligence with AI-powered insights — branch-scoped")

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Viewing: **{branch_label}**")

    sales_df = _load_scoped(load_sales, branch_id)
    customers_df = _load_scoped(load_customers, branch_id)

    customer_list = get_combined_customers(customers_df, sales_df)

    if customer_list.empty:
        st.warning(f"No customers found in {branch_label}.")
        st.info("Tip: When making a sale, enter a customer name (not 'Walk-in') to build profiles.")
        return

    st.sidebar.markdown("### Customer Info")
    st.sidebar.write(f"Branch: {branch_label}")
    st.sidebar.write(f"Total Customers: {len(customer_list)}")
    st.sidebar.write(f"Total Sales: {len(sales_df)}")

    st.markdown("## Find Customer")

    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input(
            "Search by Customer Name",
            placeholder="Enter customer name...",
            key=f"c360_search_{branch_id}",
        )
    with col2:
        if st.button("Search", type="primary", use_container_width=True,
                     key=f"c360_search_btn_{branch_id}"):
            st.session_state[f"c360_search_customer_{branch_id}"] = search_term

    if search_term:
        filtered = customer_list[
            customer_list["customer_name"].str.contains(search_term, case=False, na=False)
        ]
    else:
        filtered = customer_list.head(20)

    if filtered.empty:
        st.warning("No customers found matching your search")
        return

    customer_options = []
    customer_map = {}
    for _, row in filtered.iterrows():
        name_val = safe_str(row["customer_name"])
        phone_val = safe_str(row.get("phone", ""))
        display = f"{name_val} - {phone_val}" if phone_val else name_val
        customer_options.append(display)
        customer_map[display] = name_val

    selected_display = st.selectbox(
        "Select Customer", customer_options, key=f"c360_select_{branch_id}",
    )

    if not selected_display:
        return

    selected_customer_name = customer_map[selected_display]
    profile = get_customer_complete_profile(selected_customer_name, sales_df, branch_id)

    if not profile:
        st.error("Could not load customer profile")
        return

    # ==============================
    # HEADER
    # ==============================
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Customer", profile.get("customer_name", "N/A"))
    with col2:
        st.metric("Phone", profile.get("phone", "N/A") or "N/A")
    with col3:
        st.metric("Tier", profile.get("tier", "BRONZE"))
    with col4:
        segment = get_customer_segment(profile)
        st.metric("Segment", segment.split(" - ")[0] if " - " in segment else segment)

    st.markdown("---")

    # ==============================
    # KEY METRICS
    # ==============================
    st.markdown("## Key Metrics")

    total_spent = safe_float(profile.get('total_spent', 0))
    total_orders = safe_int(profile.get('total_orders', 0))
    avg_order = safe_float(profile.get('avg_transaction_value', 0))
    days_since = profile.get('days_since_last_purchase', 'N/A')

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Spent", f"${total_spent:,.2f}")
    with col2:
        st.metric("Orders", total_orders)
    with col3:
        st.metric("Points", f"{profile.get('points', 0):,}")
    with col4:
        if days_since != 'N/A' and days_since is not None:
            st.metric("Days Since Last", f"{int(days_since)} days")
        else:
            st.metric("Last Purchase", "Never")
    with col5:
        st.metric("Avg Order", f"${avg_order:.2f}")

    st.markdown("---")

    # ==============================
    # CHURN RISK + NEXT PURCHASE
    # ==============================
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("## Churn Risk Analysis")
        churn = predict_churn_risk(profile)

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=churn["risk_score"],
            title={"text": f"Risk Score - {churn['risk_level']}"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": churn["risk_color"]},
                "steps": [
                    {"range": [0, 30], "color": "lightgreen"},
                    {"range": [30, 60], "color": "yellow"},
                    {"range": [60, 100], "color": "salmon"},
                ],
            },
        ))
        fig_gauge.update_layout(height=250)
        st.plotly_chart(fig_gauge, use_container_width=True)

        for factor in churn["risk_factors"]:
            st.warning(factor)
        st.info(f"**Recommendation:** {churn['recommendation']}")

    with col2:
        st.markdown("## Next Purchase Prediction")
        prediction = predict_next_purchase(profile)

        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Predicted Date", prediction["predicted_date"].strftime("%Y-%m-%d"))
        with col_b:
            st.metric("Days from Now", f"{prediction['days_from_now']} days")

        st.progress(min(1.0, prediction["days_from_now"] / 90))
        st.caption(f"Confidence: {prediction['confidence']}")
        st.info(f"Average between purchases: {prediction['avg_days_between']} days")

    st.markdown("---")

    # ==============================
    # CLV
    # ==============================
    st.markdown("## Customer Lifetime Value (CLV)")
    clv_data = calculate_customer_lifetime_value(profile)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("CLV", f"${clv_data['clv']:,.2f}")
    with col2:
        st.metric("Avg Order", f"${clv_data['avg_order_value']:.2f}")
    with col3:
        st.metric("Frequency", f"{clv_data['purchase_frequency']:.1f}/year")
    with col4:
        st.metric("Lifespan", f"{clv_data['estimated_lifespan_years']} years")

    st.markdown("---")

    # ==============================
    # FAVORITE PRODUCTS
    # ==============================
    st.markdown("## Favorite Products")
    favorite_products = profile.get("favorite_products", {})

    if favorite_products:
        fav_df = pd.DataFrame([
            {"Product": name, "Quantity": qty}
            for name, qty in favorite_products.items()
        ])
        fig_fav = px.bar(
            fav_df, x="Quantity", y="Product", orientation='h',
            title=f"Top Purchased Products — {selected_customer_name}",
            color="Quantity", color_continuous_scale="Viridis", text="Quantity",
        )
        fig_fav.update_layout(height=300)
        st.plotly_chart(fig_fav, use_container_width=True)
    else:
        st.info("No favorite products data available")

    st.markdown("---")

    # ==============================
    # RECOMMENDATIONS
    # ==============================
    st.markdown("## Personalized Recommendations")
    recommendations = get_personalized_recommendations(profile, branch_id)

    if recommendations:
        cols = st.columns(min(3, len(recommendations)))
        for idx, rec in enumerate(recommendations[:3]):
            with cols[idx]:
                st.markdown(f"""
                <div style="background: #f8f9fa; border-radius: 10px; padding: 15px; margin: 5px; text-align: center;">
                    <h4>{rec['product_name'][:25]}</h4>
                    <p style="font-size: 20px; color: green;">${rec['price']:.2f}</p>
                    <p style="font-size: 12px; color: gray;">{rec['reason']}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Not enough data for personalized recommendations")

    st.markdown("---")

    # ==============================
    # PURCHASE HISTORY
    # ==============================
    st.markdown("## Purchase History")
    st.caption(f"All purchases for: {selected_customer_name} in {branch_label}")

    purchase_history = profile.get("purchase_history", [])
    if purchase_history:
        history_df = pd.DataFrame(purchase_history)
        display_cols = []

        date_col = None
        for col in ["date", "sale_date", "transaction_date"]:
            if col in history_df.columns:
                date_col = col
                break
        if date_col:
            display_cols.append(date_col)
            history_df[date_col] = pd.to_datetime(history_df[date_col], errors="coerce")
            history_df[date_col] = history_df[date_col].dt.strftime("%Y-%m-%d %H:%M")

        receipt_col = None
        for col in ["receipt_no", "receipt", "transaction_id"]:
            if col in history_df.columns:
                receipt_col = col
                break
        if receipt_col:
            display_cols.append(receipt_col)

        customer_col = None
        for col in ["customer_name", "customer"]:
            if col in history_df.columns:
                customer_col = col
                break
        if customer_col:
            display_cols.append(customer_col)

        amount_col = None
        for col in ["final_total", "total"]:
            if col in history_df.columns:
                amount_col = col
                break
        if amount_col:
            display_cols.append(amount_col)
            history_df[amount_col] = history_df[amount_col].apply(safe_float)

        if "items" in history_df.columns:
            display_cols.append("items")

        payment_col = None
        for col in ["payment_method", "payment_type"]:
            if col in history_df.columns:
                payment_col = col
                break
        if payment_col:
            display_cols.append(payment_col)

        if display_cols:
            st.dataframe(
                history_df[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    amount_col: st.column_config.NumberColumn("Amount", format="$%.2f")
                } if amount_col else {},
            )
        else:
            st.dataframe(history_df, use_container_width=True, hide_index=True)

        st.caption(f"Showing {len(history_df)} purchases")
    else:
        st.info(f"No purchase history available for {selected_customer_name}")

    # ==============================
    # DEBT INFO
    # ==============================
    if profile.get("has_debt", False):
        st.markdown("---")
        st.markdown("## Debt Information")
        col1, col2 = st.columns(2)
        with col1:
            st.error(f"Outstanding Debt: ${safe_float(profile.get('total_debt', 0)):,.2f}")
        with col2:
            if st.button("View Debt Details", use_container_width=True,
                         key=f"c360_debt_{branch_id}"):
                debt_details = profile.get("debt_details", [])
                if debt_details:
                    st.dataframe(pd.DataFrame(debt_details), use_container_width=True)


# ==============================
# CUSTOMER INSIGHTS DASHBOARD
# ==============================
def customer_insights_360(branch_id=None):
    st.title("Customer Intelligence Dashboard")
    st.caption("AI-powered insights across customers — branch-scoped")

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df, key_suffix="_insights")
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Viewing: **{branch_label}**")

    sales_df = _load_scoped(load_sales, branch_id)
    customers_df = _load_scoped(load_customers, branch_id)

    customer_list = get_combined_customers(customers_df, sales_df)
    if customer_list.empty:
        st.warning(f"No customer data available for {branch_label}.")
        return

    st.markdown("## Overall Customer Metrics")

    total_customers = len(customer_list)
    receipt_col = get_receipt_column(sales_df)
    amount_col = get_amount_column(sales_df)

    total_revenue = 0
    total_transactions = 0
    if not sales_df.empty and amount_col:
        scoped = sales_df.copy()
        scoped[amount_col] = pd.to_numeric(scoped[amount_col], errors="coerce").fillna(0)
        if receipt_col and receipt_col in scoped.columns:
            scoped = scoped.drop_duplicates(subset=[receipt_col])
        total_revenue = safe_float(scoped[amount_col].sum())
        total_transactions = len(scoped)

    avg_spent = total_revenue / total_customers if total_customers > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Customers", total_customers)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("Avg Customer Spend", f"${avg_spent:.2f}")
    with col4:
        date_col = get_date_column(sales_df)
        customer_col = get_customer_column(sales_df)
        active_customers = 0
        if date_col and customer_col and not sales_df.empty:
            scoped = sales_df.copy()
            scoped[date_col] = pd.to_datetime(scoped[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=90)
            recent = scoped[scoped[date_col] >= cutoff]
            if not recent.empty:
                active_customers = recent[customer_col].nunique()
        st.metric("Active Customers (90 days)", active_customers)

    st.markdown("---")
    st.markdown("## Customer Segmentation")

    segments = []
    for _, customer in customer_list.iterrows():
        name_val = safe_str(customer["customer_name"])
        profile = get_customer_complete_profile(name_val, sales_df, branch_id)
        if profile:
            segments.append(get_customer_segment(profile))

    if segments:
        segment_counts = pd.Series(segments).value_counts().reset_index()
        segment_counts.columns = ["Segment", "Count"]
        fig = px.pie(
            segment_counts, values="Count", names="Segment",
            title=f"Customer Segment Distribution — {branch_label}",
            hole=0.4,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("## At-Risk Customers")

    at_risk = []
    for _, customer in customer_list.iterrows():
        name_val = safe_str(customer["customer_name"])
        profile = get_customer_complete_profile(name_val, sales_df, branch_id)
        if profile:
            churn = predict_churn_risk(profile)
            if churn["risk_level"] in ["HIGH", "MEDIUM"]:
                at_risk.append({
                    "Customer": profile.get("customer_name", "N/A"),
                    "Phone": profile.get("phone", "N/A"),
                    "Risk Level": churn["risk_level"],
                    "Risk Score": churn["risk_score"],
                    "Days Since Last": profile.get("days_since_last_purchase", "N/A"),
                    "Total Spent": safe_float(profile.get("total_spent", 0)),
                })

    if at_risk:
        at_risk_df = pd.DataFrame(at_risk).sort_values("Risk Score", ascending=False)
        st.dataframe(
            at_risk_df, use_container_width=True, hide_index=True,
            column_config={"Total Spent": st.column_config.NumberColumn("Total Spent", format="$%.2f")},
        )
        csv = at_risk_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download At-Risk Customers List",
            data=csv,
            file_name=f"at_risk_customers_{_branch_slug(branch_id)}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.success(f"No at-risk customers detected in {branch_label}!")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customer_360_view()