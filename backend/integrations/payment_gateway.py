# backend/integrations/payment_gateway.py
# Payment Gateway Dashboard — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Payments generated from sales carry the branch of the sale, not a hard-coded
# "HO". EcoCash and card transaction logs gain branch_id columns.

import streamlit as st
import pandas as pd
import hashlib
import secrets
import json
import requests
import re
from datetime import datetime, timedelta
from pathlib import Path
import qrcode
from io import BytesIO
import base64

from backend.core.db_adapter import (
    load_sales,
    load_customers,
    load_debtors,
    load_cash,
    load_branches,
    get_cash_summary,
)


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
PAYMENT_FILE = DATA_DIR / "payments.csv"
ECO_CASH_FILE = DATA_DIR / "ecocash_transactions.csv"
CARD_FILE = DATA_DIR / "card_transactions.csv"

PAYMENT_COLUMNS = [
    "payment_id", "receipt_no", "amount", "payment_method", "status",
    "reference", "transaction_id", "payment_date", "customer_name",
    "customer_phone", "branch_code", "processed_by",
]

ECOCASH_COLUMNS = [
    "transaction_id", "branch_code", "receipt_no", "amount", "customer_phone",
    "merchant_code", "status", "request_date", "completion_date",
    "reference", "notes",
]

CARD_COLUMNS = [
    "transaction_id", "branch_code", "receipt_no", "amount", "card_type",
    "last_four", "status", "payment_date", "auth_code", "notes",
]


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
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_").upper() or "HO"


def _branch_scope_selector(branches_df):
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
            key="payment_branch_scope",
            help="Owners may view payments per branch or across all.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Payment dashboard locked to your branch: **{label}**")
    return session_branch, label


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


def _find_col(df, names, default=None):
    if df is None or df.empty:
        return default
    for c in names:
        if c in df.columns:
            return c
    return default


# ==============================
# INITIALIZATION
# ==============================
def init_payment_files():
    DATA_DIR.mkdir(exist_ok=True)

    if not PAYMENT_FILE.exists():
        pd.DataFrame(columns=PAYMENT_COLUMNS).to_csv(PAYMENT_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(PAYMENT_FILE)
            if "branch_code" not in existing.columns:
                existing.insert(11, "branch_code", "HO")
                existing = existing[[c for c in PAYMENT_COLUMNS if c in existing.columns]]
                existing.to_csv(PAYMENT_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=PAYMENT_COLUMNS).to_csv(PAYMENT_FILE, index=False)

    if not ECO_CASH_FILE.exists():
        pd.DataFrame(columns=ECOCASH_COLUMNS).to_csv(ECO_CASH_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(ECO_CASH_FILE)
            if "branch_code" not in existing.columns:
                existing.insert(1, "branch_code", "HO")
                existing = existing[[c for c in ECOCASH_COLUMNS if c in existing.columns]]
                existing.to_csv(ECO_CASH_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=ECOCASH_COLUMNS).to_csv(ECO_CASH_FILE, index=False)

    if not CARD_FILE.exists():
        pd.DataFrame(columns=CARD_COLUMNS).to_csv(CARD_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(CARD_FILE)
            if "branch_code" not in existing.columns:
                existing.insert(1, "branch_code", "HO")
                existing = existing[[c for c in CARD_COLUMNS if c in existing.columns]]
                existing.to_csv(CARD_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=CARD_COLUMNS).to_csv(CARD_FILE, index=False)


# ==============================
# PAYMENTS FROM SALES (scoped)
# ==============================
def load_payments_from_sales(date_from=None, date_to=None, branch_id=None):
    """
    Load payments from sales data for the branch.
    Deduplicates by receipt and stamps each payment with the branch it belongs to.
    """
    branch_id = _resolve_branch(branch_id)
    branch_code = _branch_slug(branch_id)

    sales_df = _load_scoped(load_sales, branch_id)
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    date_col = _find_col(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    if date_col:
        sales_df = sales_df.copy()
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        if date_from:
            sales_df = sales_df[sales_df[date_col] >= pd.to_datetime(date_from)]
        if date_to:
            sales_df = sales_df[sales_df[date_col] <= pd.to_datetime(date_to)]

    if sales_df.empty:
        return pd.DataFrame()

    total_col = _find_col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    if total_col is None:
        return pd.DataFrame()

    receipt_col = _find_col(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])

    # Deduplicate to avoid revenue inflation
    if receipt_col:
        sales_df = sales_df.drop_duplicates(subset=[receipt_col], keep="first")

    payment_method_col = _find_col(sales_df, ["payment_method", "payment_type", "payment"])
    customer_name_col = _find_col(sales_df, ["customer_name", "customer", "Customer"])
    customer_phone_col = _find_col(sales_df, ["customer_phone", "phone", "Phone"])
    cashier_col = _find_col(sales_df, ["cashier", "user", "username"])

    payments = []
    for _, sale in sales_df.iterrows():
        amount = to_float(sale.get(total_col, 0))
        if amount <= 0:
            continue

        receipt_no = (
            str(sale.get(receipt_col, "")) if receipt_col and pd.notna(sale.get(receipt_col)) else ""
        ).strip()
        if not receipt_no or receipt_no.lower() == "nan":
            receipt_no = f"SALE{len(payments)+1:08d}"

        payment_method = "CASH"
        if payment_method_col:
            v = sale.get(payment_method_col, "CASH")
            if v and str(v).strip() and str(v).strip().lower() != "nan":
                payment_method = str(v).strip().upper()

        customer_name = "Walk-in"
        if customer_name_col:
            v = sale.get(customer_name_col, "Walk-in")
            if v and str(v).strip() and str(v).strip().lower() != "nan":
                customer_name = str(v).strip()

        customer_phone = ""
        if customer_phone_col:
            v = sale.get(customer_phone_col, "")
            if v and str(v).strip() and str(v).strip().lower() != "nan":
                customer_phone = str(v).strip()

        cashier = "system"
        if cashier_col:
            v = sale.get(cashier_col, "system")
            if v and str(v).strip() and str(v).strip().lower() != "nan":
                cashier = str(v).strip()

        sale_date = sale.get(date_col, datetime.now()) if date_col else datetime.now()

        payments.append({
            "payment_id": f"PAY{len(payments)+1:08d}",
            "receipt_no": receipt_no,
            "amount": amount,
            "payment_method": payment_method,
            "status": "COMPLETED",
            "reference": receipt_no,
            "transaction_id": receipt_no,
            "payment_date": sale_date,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "branch_code": branch_code,
            "processed_by": cashier,
        })

    return pd.DataFrame(payments) if payments else pd.DataFrame()


# ==============================
# PAYMENT SUMMARY (scoped)
# ==============================
def get_payment_summary(days=30, branch_id=None):
    branch_id = _resolve_branch(branch_id)

    sales_df = _load_scoped(load_sales, branch_id)

    empty = {
        "total_payments": 0,
        "total_amount": 0,
        "by_method": {},
        "recent_payments": pd.DataFrame(),
        "cash_vs_credit": {"CASH": 0, "CREDIT": 0, "OTHER": 0},
        "branch_id": branch_id,
    }

    if sales_df is None or sales_df.empty:
        return empty

    date_col = _find_col(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    if date_col:
        sales_df = sales_df.copy()
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        cutoff = datetime.now() - timedelta(days=days)
        sales_df = sales_df[sales_df[date_col] >= cutoff]

    if sales_df.empty:
        return empty

    total_col = _find_col(sales_df, ["final_total", "total", "amount", "sale_amount"])
    if total_col is None:
        return empty

    receipt_col = _find_col(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
    payment_col = _find_col(sales_df, ["payment_method", "payment_type", "payment"])

    if receipt_col:
        unique_sales = sales_df.drop_duplicates(subset=[receipt_col], keep="first")
    else:
        unique_sales = sales_df

    total_payments = len(unique_sales)
    total_amount = to_float(pd.to_numeric(
        unique_sales[total_col], errors="coerce"
    ).fillna(0).sum())

    by_method = {}
    if payment_col:
        method_data = unique_sales.groupby(payment_col)[total_col].sum()
        by_method = {str(k): to_float(v) for k, v in method_data.items()}

    cash_vs_credit = {"CASH": 0, "CREDIT": 0, "OTHER": 0}
    for method, amount in by_method.items():
        upper = method.upper()
        if "CASH" in upper:
            cash_vs_credit["CASH"] += amount
        elif "CREDIT" in upper:
            cash_vs_credit["CREDIT"] += amount
        else:
            cash_vs_credit["OTHER"] += amount

    if date_col:
        recent = unique_sales.sort_values(date_col, ascending=False).head(10)
    else:
        recent = unique_sales.head(10)

    return {
        "total_payments": total_payments,
        "total_amount": total_amount,
        "by_method": by_method,
        "recent_payments": recent,
        "cash_vs_credit": cash_vs_credit,
        "branch_id": branch_id,
    }


# ==============================
# ECOCASH / CARD (branch-tagged)
# ==============================
def load_ecocash_transactions(branch_id=None):
    init_payment_files()
    try:
        df = pd.read_csv(ECO_CASH_FILE)
    except Exception:
        return pd.DataFrame(columns=ECOCASH_COLUMNS)

    if "branch_code" not in df.columns:
        df["branch_code"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_code"].astype(str).str.upper() == str(branch_id).upper()].copy()


def load_card_transactions(branch_id=None):
    init_payment_files()
    try:
        df = pd.read_csv(CARD_FILE)
    except Exception:
        return pd.DataFrame(columns=CARD_COLUMNS)

    if "branch_code" not in df.columns:
        df["branch_code"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_code"].astype(str).str.upper() == str(branch_id).upper()].copy()


# ==============================
# ECOCASH PAYMENT REQUEST (branch-tagged)
# ==============================
def generate_ecocash_payment_request(amount, customer_phone, receipt_no, branch_id=None):
    """
    Simulated EcoCash payment request. The transaction is written with the
    caller's branch so a HO request is never logged as NAT or vice versa.
    """
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return {
            "success": False,
            "message": "Cannot create an EcoCash request against All Branches. Pick a specific branch.",
        }

    branch_code = _branch_slug(branch_id)

    transaction_id = (
        f"ECO{branch_code}{datetime.now().strftime('%Y%m%d%H%M%S')}"
        f"{secrets.randbelow(1000):03d}"
    )
    merchant_code = "AZIEL001"

    payment_link = (
        f"https://pay.ecocash.co.zw/pay?txn={transaction_id}"
        f"&amt={amount}&msisdn={customer_phone}"
    )

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(payment_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    df = load_ecocash_transactions(branch_id=ALL_BRANCHES)
    new_transaction = pd.DataFrame([{
        "transaction_id": transaction_id,
        "branch_code": branch_code,
        "receipt_no": receipt_no,
        "amount": amount,
        "customer_phone": customer_phone,
        "merchant_code": merchant_code,
        "status": "PENDING",
        "request_date": datetime.now().isoformat(),
        "completion_date": "",
        "reference": "",
        "notes": "",
    }])
    df = pd.concat([df, new_transaction], ignore_index=True)
    df.to_csv(ECO_CASH_FILE, index=False)

    return {
        "success": True,
        "transaction_id": transaction_id,
        "payment_link": payment_link,
        "qr_code": qr_base64,
        "branch_code": branch_code,
        "message": f"Payment request generated for {_branch_label(branch_id)}.",
    }


def verify_ecocash_payment(transaction_id, branch_id=None):
    """Verify payment status. If branch_id given, refuses if the record belongs elsewhere."""
    branch_id = _resolve_branch(branch_id)

    if not ECO_CASH_FILE.exists():
        return {"success": False, "status": "NOT_FOUND", "message": "Transaction not found"}

    df = pd.read_csv(ECO_CASH_FILE)
    if "branch_code" not in df.columns:
        df["branch_code"] = "HO"

    transaction = df[df["transaction_id"] == transaction_id]
    if transaction.empty:
        return {"success": False, "status": "NOT_FOUND", "message": "Transaction not found"}

    row = transaction.iloc[0]
    row_branch = str(row.get("branch_code", "HO")).upper()

    if not _is_all_branches(branch_id) and row_branch != str(branch_id).upper():
        return {
            "success": False,
            "status": "FORBIDDEN",
            "message": (
                f"Refused: transaction belongs to {row_branch}, "
                f"your scope is {branch_id}."
            ),
        }

    current_status = row["status"]
    if current_status == "PENDING":
        time_since = (datetime.now() - pd.to_datetime(row["request_date"])).seconds
        if time_since > 30:
            idx = transaction.index[0]
            df.loc[idx, "status"] = "COMPLETED"
            df.loc[idx, "completion_date"] = datetime.now().isoformat()
            df.loc[idx, "reference"] = f"REF{secrets.randbelow(10000):04d}"
            df.to_csv(ECO_CASH_FILE, index=False)
            return {
                "success": True,
                "status": "COMPLETED",
                "message": "Payment completed successfully",
                "reference": df.loc[idx, "reference"],
            }
        return {
            "success": False,
            "status": "PENDING",
            "message": "Payment pending. Please wait for customer to complete payment.",
        }

    if current_status == "COMPLETED":
        return {
            "success": True,
            "status": "COMPLETED",
            "message": "Payment already completed",
            "reference": row.get("reference", ""),
        }

    return {"success": False, "status": current_status, "message": f"Payment status: {current_status}"}


# ==============================
# DASHBOARD
# ==============================
def payment_dashboard(branch_id=None):
    st.title("Payment Gateway Dashboard")
    st.caption("Manage payments and view transaction history — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access payment dashboard.")
        return

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Viewing: **{branch_label}**")

    init_payment_files()

    tab1, tab2, tab3 = st.tabs([
        "Payment Summary",
        "Transaction History",
        "Gateway Settings",
    ])

    # ==============================
    # TAB 1: SUMMARY
    # ==============================
    with tab1:
        st.markdown(f"## Payment Summary — {branch_label}")

        summary = get_payment_summary(30, branch_id=branch_id)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Payments", f"${summary['total_amount']:,.2f}")
        with col2:
            st.metric("Total Transactions", summary["total_payments"])
        with col3:
            avg = (
                summary['total_amount'] / summary['total_payments']
                if summary['total_payments'] > 0 else 0
            )
            st.metric("Avg Transaction", f"${avg:.2f}")

        st.markdown("### Cash vs Credit Breakdown")
        cvc = summary.get("cash_vs_credit", {"CASH": 0, "CREDIT": 0, "OTHER": 0})
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Cash Sales", f"${cvc['CASH']:,.2f}")
        with col2:
            st.metric("Credit Sales", f"${cvc['CREDIT']:,.2f}")
        with col3:
            st.metric("Other Payments", f"${cvc['OTHER']:,.2f}")

        st.markdown("### Payment Methods Breakdown")
        if summary["by_method"]:
            methods_df = pd.DataFrame(
                list(summary["by_method"].items()), columns=["Method", "Amount"]
            )
            st.bar_chart(methods_df.set_index("Method"))
            st.dataframe(
                methods_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                },
            )
        else:
            st.info(f"No payment data available for {branch_label}. Complete some sales first.")

        if not summary["recent_payments"].empty:
            st.markdown("### Recent Payments")
            recent = summary["recent_payments"]
            display_cols = []
            for c in ["receipt_no", "receipt", "customer_name", "customer",
                      "total", "final_total", "payment_method", "date", "sale_date"]:
                if c in recent.columns:
                    display_cols.append(c)
            if display_cols:
                st.dataframe(
                    recent[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        c: st.column_config.NumberColumn("Amount", format="$%.2f")
                        for c in ["total", "final_total"] if c in recent.columns
                    },
                )

    # ==============================
    # TAB 2: TRANSACTIONS
    # ==============================
    with tab2:
        st.markdown(f"## Transaction History — {branch_label}")

        payments_df = load_payments_from_sales(branch_id=branch_id)

        if payments_df.empty:
            st.info(f"No transactions found for {branch_label}.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                date_from = st.date_input(
                    "From Date", datetime.now() - timedelta(days=30),
                    key=f"pg_from_{branch_id}",
                )
            with col2:
                date_to = st.date_input(
                    "To Date", datetime.now(),
                    key=f"pg_to_{branch_id}",
                )

            payments_df = payments_df.copy()
            payments_df["payment_date"] = pd.to_datetime(
                payments_df["payment_date"], errors="coerce"
            )
            payments_df = payments_df[
                (payments_df["payment_date"] >= pd.to_datetime(date_from))
                & (payments_df["payment_date"] <= pd.to_datetime(date_to))
            ]

            display_cols = [
                c for c in [
                    "payment_date", "receipt_no", "customer_name",
                    "amount", "payment_method", "status", "branch_code",
                ] if c in payments_df.columns
            ]
            st.dataframe(
                payments_df[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                    "payment_date": st.column_config.DatetimeColumn(
                        "Date", format="YYYY-MM-DD HH:mm"
                    ),
                },
            )

            total_amount = (
                payments_df["amount"].sum() if "amount" in payments_df.columns else 0
            )
            st.info(
                f"Total: ${to_float(total_amount):,.2f} | "
                f"Count: {len(payments_df)}"
            )

            csv = payments_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Export Transactions (CSV)",
                data=csv,
                file_name=(
                    f"payments_{_branch_slug(branch_id)}_"
                    f"{datetime.now().strftime('%Y%m%d')}.csv"
                ),
                mime="text/csv",
                key=f"pg_dl_{branch_id}",
            )

    # ==============================
    # TAB 3: SETTINGS
    # ==============================
    with tab3:
        st.markdown(f"## Gateway Settings — {branch_label}")

        st.info("Payment gateway configuration")
        st.markdown("""
        **Available Payment Gateways:**
        - Cash (Physical)
        - EcoCash (Mobile Money) — Coming Soon
        - Card Payments (Visa/Mastercard) — Coming Soon
        - Bank Transfer — Coming Soon
        - PayNow (Coming Soon)
        - InnBucks (Coming Soon)
        """)

        sales_df = _load_scoped(load_sales, branch_id)
        if sales_df is not None and not sales_df.empty:
            st.markdown("### Current Payment Statistics")

            total_col = _find_col(sales_df, ["final_total", "total", "amount", "sale_amount"])
            receipt_col = _find_col(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
            payment_col = _find_col(sales_df, ["payment_method", "payment_type", "payment"])

            if total_col:
                if receipt_col:
                    unique_sales = sales_df.drop_duplicates(subset=[receipt_col])
                else:
                    unique_sales = sales_df
                total_amount = to_float(pd.to_numeric(
                    unique_sales[total_col], errors="coerce"
                ).fillna(0).sum())
                total_count = len(unique_sales)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Sales (All Time)", f"${total_amount:,.2f}")
                with col2:
                    st.metric("Total Transactions", total_count)

                if payment_col:
                    st.markdown("### Payment Method Distribution")
                    method_dist = unique_sales.groupby(payment_col)[total_col].sum()
                    method_df = (
                        method_dist.reset_index()
                        .rename(columns={payment_col: "Method", total_col: "Amount"})
                    )
                    method_df["Amount"] = method_df["Amount"].apply(to_float)
                    st.dataframe(
                        method_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                        },
                    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    payment_dashboard()