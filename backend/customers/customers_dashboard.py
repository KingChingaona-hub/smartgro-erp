# backend/customers/customers_dashboard.py
# Customer Intelligence Dashboard — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import re

from backend.core.db_adapter import (
    load_customers,
    load_sales,
    load_products,
    load_branches,
)
from backend.modules.loyalty import (
    load_loyalty,
    get_top_loyalty_customers,
    get_birthday_customers,
    get_customer_loyalty_info,
    get_tier_benefits,
    save_loyalty,
)
from backend.utils.utils import generate_whatsapp_promotion
from backend.utils.phone_utils import get_whatsapp_link


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


def _branch_scope_selector(branches_df):
    """Owner picks; everyone else is locked to their session branch."""
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
            key="customers_dashboard_branch_scope",
            help="Owners may view company-wide or one branch at a time.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Customer dashboard locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# SAFE CONVERTERS
# ==============================
def to_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
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


def get_date_column(df):
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def get_product_column(df):
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "item_name"]:
        if col in df.columns:
            return col
    return None


# ==============================
# CUSTOMER EXTRACTION / METRICS
# ==============================
def extract_customers_from_sales(sales_df):
    """Unique customers from an already-scoped sales DataFrame."""
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
    customer_data = customer_data.drop_duplicates(subset=["customer_name", "phone"])
    customer_data = customer_data[
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('walk-in', na=False)
        & ~customer_data["customer_name"].astype(str).str.lower().str.contains('unknown', na=False)
        & (customer_data["customer_name"].astype(str).str.strip() != '')
        & (customer_data["customer_name"].astype(str).str.strip() != 'nan')
        & (customer_data["customer_name"].astype(str).str.strip() != 'None')
    ]
    return customer_data


def get_combined_customers(customers_df, sales_df):
    """Sales-derived customers take priority; fall back to customers table."""
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


def get_customer_total_spent(customer_name, sales_df):
    if sales_df is None or sales_df.empty or not customer_name:
        return 0

    customer_col = get_customer_column(sales_df)
    amount_col = get_amount_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    if customer_col is None or amount_col is None:
        return 0

    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
    ]
    if customer_sales.empty:
        return 0

    if receipt_col and receipt_col in customer_sales.columns:
        unique_receipts = customer_sales.drop_duplicates(subset=[receipt_col])
        return to_float(unique_receipts[amount_col].sum())
    return to_float(customer_sales[amount_col].sum())


def get_customer_total_orders(customer_name, sales_df):
    if sales_df is None or sales_df.empty or not customer_name:
        return 0

    customer_col = get_customer_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    if customer_col is None:
        return 0

    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
    ]
    if customer_sales.empty:
        return 0

    if receipt_col and receipt_col in customer_sales.columns:
        return len(customer_sales.drop_duplicates(subset=[receipt_col]))
    return len(customer_sales)


def get_customer_last_purchase(customer_name, sales_df):
    if sales_df is None or sales_df.empty or not customer_name:
        return None

    customer_col = get_customer_column(sales_df)
    date_col = get_date_column(sales_df)
    if customer_col is None or date_col is None:
        return None

    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
    ]
    if customer_sales.empty:
        return None

    customer_sales = customer_sales.copy()
    customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
    return customer_sales[date_col].max()


def get_customer_products(customer_name, sales_df):
    if sales_df is None or sales_df.empty or not customer_name:
        return []

    customer_col = get_customer_column(sales_df)
    if customer_col is None:
        return []

    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
    ]
    if customer_sales.empty:
        return []

    name_col = get_product_column(customer_sales)
    if name_col is None:
        return []
    return customer_sales[name_col].tolist()


# ==============================
# WHATSAPP SEGMENTS (branch-scoped recipients)
# ==============================
def _get_segment_recipients(segment, real_customers, sales_df):
    """
    Return a filtered DataFrame of customers for the WhatsApp segment.
    All filtering uses only the branch-scoped real_customers / sales_df.
    """
    filtered = real_customers.copy()

    if segment == "High Spenders":
        customer_col = get_customer_column(sales_df)
        amount_col = get_amount_column(sales_df)
        receipt_col = get_receipt_column(sales_df)
        if customer_col and amount_col and not sales_df.empty:
            scoped = sales_df.copy()
            scoped[amount_col] = pd.to_numeric(scoped[amount_col], errors="coerce").fillna(0)
            if receipt_col and receipt_col in scoped.columns:
                scoped = scoped.drop_duplicates(subset=[receipt_col])
            customer_spending = scoped.groupby(customer_col)[amount_col].sum()
            avg_spent = customer_spending.mean() if not customer_spending.empty else 0
            high_spenders = customer_spending[customer_spending > avg_spent].index.tolist()
            filtered = filtered[filtered["customer_name"].isin(high_spenders)]

    elif segment == "Recent Customers":
        date_col = get_date_column(sales_df)
        customer_col = get_customer_column(sales_df)
        if date_col and customer_col and not sales_df.empty:
            scoped = sales_df.copy()
            scoped[date_col] = pd.to_datetime(scoped[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=30)
            recent = scoped[scoped[date_col] >= cutoff]
            recent_customers = recent[customer_col].unique().tolist()
            filtered = filtered[filtered["customer_name"].isin(recent_customers)]

    elif segment == "Inactive Customers":
        date_col = get_date_column(sales_df)
        customer_col = get_customer_column(sales_df)
        if date_col and customer_col and not sales_df.empty:
            scoped = sales_df.copy()
            scoped[date_col] = pd.to_datetime(scoped[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=90)
            inactive = scoped[scoped[date_col] < cutoff]
            recent = scoped[scoped[date_col] >= cutoff]
            inactive_names = set(inactive[customer_col].unique().tolist())
            recent_names = set(recent[customer_col].unique().tolist())
            only_inactive = [c for c in inactive_names if c not in recent_names]
            filtered = filtered[filtered["customer_name"].isin(only_inactive)]

    return filtered


def _build_whatsapp_link(phone, final_message):
    phone_clean = re.sub(r'\D', '', str(phone))
    if phone_clean.startswith('0'):
        phone_clean = '263' + phone_clean[1:]
    elif not phone_clean.startswith('263'):
        phone_clean = '263' + phone_clean
    encoded = final_message.replace(' ', '%20').replace('\n', '%0A')
    return f"https://wa.me/{phone_clean}?text={encoded}"


# ==============================
# DASHBOARD
# ==============================
def customers_dashboard(branch_id=None):
    """Customer Intelligence Dashboard — branch-scoped."""

    st.title("Customer Intelligence Dashboard")
    st.caption("Track loyalty, spending patterns, and customer engagement — branch-scoped")

    # ---- Branch scope ----
    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Viewing: **{branch_label}**")

    # ---- Scoped loads ----
    customers_df = _load_scoped(load_customers, branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    loyalty_df = _load_scoped(load_loyalty, branch_id)
    products_df = _load_scoped(load_products, branch_id)

    real_customers = get_combined_customers(customers_df, sales_df)

    if real_customers.empty:
        st.warning(f"No customer data found for {branch_label}.")
        st.info("Tip: When making a sale, enter a customer name (not 'Walk-in') to build customer profiles.")
        return

    st.sidebar.markdown("### Customer Info")
    st.sidebar.write(f"Branch: {branch_label}")
    st.sidebar.write(f"Total Customers: {len(real_customers)}")
    st.sidebar.write(f"Total Sales: {len(sales_df)}")

    # ==============================
    # LOOKUP
    # ==============================
    st.markdown("## Customer Loyalty Lookup")

    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input(
            "Search by Name or Phone",
            placeholder="Enter customer name or phone...",
        )
    with col2:
        if st.button("Search", use_container_width=True):
            if search_term:
                results = real_customers[
                    real_customers["customer_name"].str.contains(search_term, case=False, na=False)
                    | real_customers["phone"].str.contains(search_term, na=False)
                ]
                if not results.empty:
                    st.session_state.search_results = results
                    st.success(f"Found {len(results)} customers")
                else:
                    st.error("No customers found")
                    st.session_state.search_results = None

    if st.session_state.get("search_results") is not None:
        results = st.session_state.search_results
        if not results.empty:
            for _, customer in results.iterrows():
                name = customer.get("customer_name", "Unknown")
                phone = customer.get("phone", "")
                with st.expander(f"{name} - {phone}"):
                    total_spent = get_customer_total_spent(name, sales_df)
                    total_orders = get_customer_total_orders(name, sales_df)
                    last_purchase = get_customer_last_purchase(name, sales_df)
                    products = get_customer_products(name, sales_df)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Spent", f"${total_spent:,.2f}")
                    with col2:
                        st.metric("Total Orders", total_orders)
                    with col3:
                        if last_purchase is not None and pd.notna(last_purchase):
                            days = (datetime.now() - last_purchase).days
                            st.metric("Last Purchase", f"{days} days ago")
                        else:
                            st.metric("Last Purchase", "Never")

                    if products:
                        unique_products = list(set(products))[:5]
                        st.write("**Products Purchased:**", ", ".join(str(p) for p in unique_products))

    st.markdown("---")

    # ==============================
    # KEY METRICS
    # ==============================
    st.markdown("## Key Metrics")

    total_customers = len(real_customers)

    amount_col = get_amount_column(sales_df)
    receipt_col = get_receipt_column(sales_df)

    total_revenue = 0
    if not sales_df.empty and amount_col:
        scoped = sales_df.copy()
        scoped[amount_col] = pd.to_numeric(scoped[amount_col], errors="coerce").fillna(0)
        if receipt_col and receipt_col in scoped.columns:
            scoped = scoped.drop_duplicates(subset=[receipt_col])
        total_revenue = to_float(scoped[amount_col].sum())

    avg_spent = total_revenue / total_customers if total_customers > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Customers", total_customers)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("Avg Customer Spend", f"${avg_spent:.2f}")
    with col4:
        active_customers = 0
        date_col = get_date_column(sales_df)
        customer_col = get_customer_column(sales_df)
        if date_col and customer_col and not sales_df.empty:
            scoped = sales_df.copy()
            scoped[date_col] = pd.to_datetime(scoped[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=90)
            recent = scoped[scoped[date_col] >= cutoff]
            if not recent.empty:
                active_customers = recent[customer_col].nunique()
        st.metric("Active Customers (90 days)", active_customers)

    st.markdown("---")

    # ==============================
    # TOP CUSTOMERS BY SPENDING
    # ==============================
    st.markdown("## Top Customers by Spending")

    if not sales_df.empty:
        customer_col = get_customer_column(sales_df)
        amount_col = get_amount_column(sales_df)
        receipt_col = get_receipt_column(sales_df)

        if customer_col and amount_col:
            try:
                scoped = sales_df.copy()
                scoped[amount_col] = pd.to_numeric(scoped[amount_col], errors="coerce").fillna(0)
                if receipt_col and receipt_col in scoped.columns:
                    scoped = scoped.drop_duplicates(subset=[receipt_col])

                customer_spending = scoped.groupby(customer_col)[amount_col].sum().reset_index()
                customer_spending.columns = ["customer", "total_spent"]
                customer_spending["total_spent"] = customer_spending["total_spent"].astype(float)
                customer_spending = customer_spending[customer_spending["total_spent"] > 0]

                top_customers = customer_spending.nlargest(10, "total_spent")

                if not top_customers.empty:
                    fig = px.bar(
                        top_customers, x="total_spent", y="customer", orientation="h",
                        title=f"Top 10 Customers by Spending — {branch_label}",
                        color="total_spent", color_continuous_scale="Greens", text="total_spent",
                    )
                    fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
                    fig.update_layout(height=400, xaxis_title="Total Spent ($)", yaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No customer spending data available")
            except Exception as e:
                st.error(f"Error calculating top customers: {str(e)}")
    else:
        st.info(f"No sales data for {branch_label}")

    st.markdown("---")

    # ==============================
    # ALL CUSTOMERS
    # ==============================
    st.markdown("## All Customers")
    st.dataframe(real_customers, use_container_width=True, hide_index=True)

    csv = real_customers.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Customer Data (CSV)",
        data=csv,
        file_name=f"customers_{_branch_slug(branch_id)}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    st.markdown("---")

    # ==============================
    # WHATSAPP BULK MESSAGING
    # ==============================
    st.markdown("## WhatsApp Bulk Messaging")
    st.caption(f"Send promotions to customers in {branch_label}")

    if real_customers.empty:
        st.warning("No customers available for messaging")
        return

    col1, col2 = st.columns(2)
    with col1:
        segment = st.selectbox(
            "Select Customer Segment",
            ["All Customers", "High Spenders", "Recent Customers", "Inactive Customers"],
            key=f"whatsapp_segment_{branch_id}",
        )
    with col2:
        message_type = st.selectbox(
            "Message Type",
            ["Promotion", "General Announcement", "Custom Message"],
            key=f"whatsapp_message_type_{branch_id}",
        )

    filtered_customers = _get_segment_recipients(segment, real_customers, sales_df)

    final_message = ""
    if message_type == "Promotion":
        promo_message = st.text_area(
            "Promotion Message", height=100,
            placeholder="e.g., 20% OFF on all products this weekend!",
            key=f"promo_message_{branch_id}",
        )
        discount_code = st.text_input(
            "Discount Code (optional)", placeholder="e.g., SAVE20",
            key=f"discount_code_{branch_id}",
        )
        if promo_message:
            final_message = promo_message
            if discount_code:
                final_message += f"\n\nUse code: {discount_code}"
            st.info(f"Preview:\n\n{final_message}")

    elif message_type == "General Announcement":
        announcement = st.text_area("Announcement", height=100, key=f"announcement_{branch_id}")
        final_message = announcement
        if announcement:
            st.info(f"Preview:\n\n{announcement}")

    else:
        custom_message = st.text_area(
            "Custom Message", height=100,
            placeholder="Type your custom message here...",
            key=f"custom_message_{branch_id}",
        )
        final_message = custom_message
        if custom_message:
            st.info(f"Preview:\n\n{custom_message}")

    customer_count = len(filtered_customers)
    st.info(f"This message will be sent to **{customer_count}** customers in {branch_label}")

    if not filtered_customers.empty and customer_count > 0:
        with st.expander("View Recipient List"):
            st.dataframe(
                filtered_customers[["customer_name", "phone"]],
                use_container_width=True,
                hide_index=True,
            )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Generate WhatsApp Links", type="primary", use_container_width=True,
                     key=f"gen_wa_{branch_id}"):
            if filtered_customers.empty:
                st.error("No customers found in this segment")
            elif not final_message:
                st.error("Please enter a message to send")
            else:
                links = []
                for _, customer in filtered_customers.iterrows():
                    phone = customer["phone"]
                    name = customer.get("customer_name", "Customer")
                    link = _build_whatsapp_link(phone, final_message)
                    links.append({"Customer": name, "Phone": phone, "WhatsApp Link": link})

                st.success(f"Generated {len(links)} WhatsApp links for {branch_label}!")
                links_df = pd.DataFrame(links)

                st.markdown("### Click to send messages")
                for _, row in links_df.iterrows():
                    st.markdown(f"**{row['Customer']}** ({row['Phone']}): [Send WhatsApp]({row['WhatsApp Link']})")

                csv_links = links_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download WhatsApp Links (CSV)",
                    data=csv_links,
                    file_name=(
                        f"whatsapp_links_{_branch_slug(branch_id)}_"
                        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                    ),
                    mime="text/csv",
                    use_container_width=True,
                )

    with col2:
        if not real_customers.empty:
            csv_export = real_customers[["customer_name", "phone"]].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Customer List for WhatsApp Broadcast",
                data=csv_export,
                file_name=(
                    f"customers_for_whatsapp_{_branch_slug(branch_id)}_"
                    f"{datetime.now().strftime('%Y%m%d')}.csv"
                ),
                mime="text/csv",
                use_container_width=True,
            )
            st.caption("Import this CSV to WhatsApp Business for bulk broadcast")


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    customers_dashboard()