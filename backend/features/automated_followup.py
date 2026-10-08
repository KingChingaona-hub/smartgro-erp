# backend/features/automated_followup.py
# Automated Customer Follow-up — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)
#
# Customers are extracted from the SCOPED sales frame. Follow-up log and
# schedule CSVs gain a branch_id column and auto-migrate existing files.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import secrets
import re

from backend.core.db_adapter import (
    load_customers,
    load_sales,
    load_products,
    load_branches,
    to_float,
)

try:
    from backend.integrations.sms_gateway import send_sms
except ImportError:
    def send_sms(phone, message, sms_type="GENERAL", sent_by="system"):
        print(f"SMS would be sent to {phone}: {message[:50]}...")
        return {"success": True, "message": "SMS logged (gateway not available)"}

try:
    from backend.utils.phone_utils import get_whatsapp_link, validate_zimbabwe_phone
except ImportError:
    def get_whatsapp_link(phone, message):
        return f"https://wa.me/263{phone.lstrip('0')}?text={message.replace(' ', '%20')}"

    def validate_zimbabwe_phone(phone):
        phone = re.sub(r'\D', '', str(phone))
        if phone.startswith('0'):
            phone = phone[1:]
        if not phone.startswith('263'):
            phone = '263' + phone
        return True, phone, "Valid"


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
FOLLOWUP_FILE = DATA_DIR / "followup_settings.json"
FOLLOWUP_LOG_FILE = DATA_DIR / "followup_logs.csv"
FOLLOWUP_SCHEDULE_FILE = DATA_DIR / "followup_schedule.csv"

FOLLOWUP_LOG_COLUMNS = [
    "log_id", "timestamp", "branch_id", "customer_name", "customer_phone",
    "customer_email", "followup_type", "message", "sent_date", "status",
    "response", "notes",
]

FOLLOWUP_SCHEDULE_COLUMNS = [
    "schedule_id", "branch_id", "customer_name", "customer_phone",
    "followup_type", "scheduled_date", "message", "status", "notes",
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
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_") or "branch"


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
            key="followup_branch_scope",
            help="Owners may send company-wide or per-branch campaigns.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Follow-up locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# INITIALIZATION
# ==============================
def init_followup_files():
    """Initialize follow-up files. Migrates CSVs to include branch_id."""
    DATA_DIR.mkdir(exist_ok=True)

    if not FOLLOWUP_FILE.exists():
        settings = {
            "enabled": True,
            "thank_you_enabled": True,
            "thank_you_delay_hours": 2,
            "review_enabled": True,
            "review_delay_days": 3,
            "reengagement_enabled": True,
            "reengagement_inactive_days": 30,
            "reengagement_discount": 10,
            "birthday_enabled": True,
            "birthday_discount": 15,
            "abandoned_cart_enabled": True,
            "abandoned_cart_delay_hours": 24,
            "sms_enabled": True,
            "email_enabled": False,
            "whatsapp_enabled": True,
            "max_followups_per_day": 50,
        }
        with open(FOLLOWUP_FILE, "w") as f:
            json.dump(settings, f, indent=2)

    # Logs — migrate to add branch_id
    if not FOLLOWUP_LOG_FILE.exists():
        pd.DataFrame(columns=FOLLOWUP_LOG_COLUMNS).to_csv(FOLLOWUP_LOG_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(FOLLOWUP_LOG_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(2, "branch_id", "HO")
                existing.to_csv(FOLLOWUP_LOG_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=FOLLOWUP_LOG_COLUMNS).to_csv(FOLLOWUP_LOG_FILE, index=False)

    # Schedule — migrate to add branch_id
    if not FOLLOWUP_SCHEDULE_FILE.exists():
        pd.DataFrame(columns=FOLLOWUP_SCHEDULE_COLUMNS).to_csv(FOLLOWUP_SCHEDULE_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(FOLLOWUP_SCHEDULE_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(1, "branch_id", "HO")
                existing.to_csv(FOLLOWUP_SCHEDULE_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=FOLLOWUP_SCHEDULE_COLUMNS).to_csv(FOLLOWUP_SCHEDULE_FILE, index=False)


# ==============================
# LOAD / SAVE
# ==============================
def load_followup_settings():
    init_followup_files()
    with open(FOLLOWUP_FILE, "r") as f:
        return json.load(f)


def save_followup_settings(settings):
    with open(FOLLOWUP_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_followup_logs():
    init_followup_files()
    try:
        df = pd.read_csv(FOLLOWUP_LOG_FILE)
        if "branch_id" not in df.columns:
            df.insert(2, "branch_id", "HO")
        return df
    except Exception:
        return pd.DataFrame(columns=FOLLOWUP_LOG_COLUMNS)


def save_followup_logs(df):
    df.to_csv(FOLLOWUP_LOG_FILE, index=False)


def load_followup_schedule():
    init_followup_files()
    try:
        df = pd.read_csv(FOLLOWUP_SCHEDULE_FILE)
        if "branch_id" not in df.columns:
            df.insert(1, "branch_id", "HO")
        return df
    except Exception:
        return pd.DataFrame(columns=FOLLOWUP_SCHEDULE_COLUMNS)


def save_followup_schedule(df):
    df.to_csv(FOLLOWUP_SCHEDULE_FILE, index=False)


# ==============================
# CUSTOMERS FROM SCOPED SALES
# ==============================
def _get_customer_col(df):
    for c in ["customer_name", "customer", "Customer"]:
        if c in df.columns:
            return c
    return None


def _get_phone_col(df):
    for c in ["customer_phone", "phone", "Phone"]:
        if c in df.columns:
            return c
    return None


def _get_total_col(df):
    for c in ["final_total", "total", "amount"]:
        if c in df.columns:
            return c
    return None


def _get_date_col(df):
    for c in ["sale_date", "date", "transaction_date"]:
        if c in df.columns:
            return c
    return None


def _get_receipt_col(df):
    for c in ["receipt_no", "receipt", "transaction_id"]:
        if c in df.columns:
            return c
    return None


def get_customers_from_sales(sales_df=None, branch_id=None):
    """
    Extract unique customers from an already-scoped sales frame.
    If sales_df is None, load scoped data using branch_id.
    """
    branch_id = _resolve_branch(branch_id)

    if sales_df is None:
        sales_df = _load_scoped(load_sales, branch_id)

    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    customer_col = _get_customer_col(sales_df)
    phone_col = _get_phone_col(sales_df)
    total_col = _get_total_col(sales_df)
    date_col = _get_date_col(sales_df)
    receipt_col = _get_receipt_col(sales_df)

    if customer_col is None:
        return pd.DataFrame()

    customers = (
        sales_df[customer_col].dropna().unique().tolist()
    )
    customers = [
        str(c).strip() for c in customers
        if str(c).strip() and str(c).strip().lower() != "walk-in"
    ]
    if not customers:
        return pd.DataFrame()

    customer_data = []
    for name in customers:
        customer_sales = sales_df[
            sales_df[customer_col].astype(str).str.contains(name, case=False, na=False)
        ]

        phone = ""
        if phone_col and not customer_sales.empty:
            phone_rows = customer_sales[phone_col].dropna()
            if not phone_rows.empty:
                phone = str(phone_rows.iloc[0]).strip()

        total_spent = 0
        if total_col and not customer_sales.empty:
            total_spent = to_float(customer_sales[total_col].sum())

        last_purchase = None
        if date_col and not customer_sales.empty:
            customer_sales = customer_sales.copy()
            customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
            last_purchase = customer_sales[date_col].max()

        total_orders = 0
        if receipt_col and not customer_sales.empty:
            total_orders = customer_sales[receipt_col].nunique()

        customer_data.append({
            "customer_name": name,
            "phone": phone,
            "total_spent": total_spent,
            "total_orders": total_orders,
            "last_purchase_date": last_purchase,
        })

    return pd.DataFrame(customer_data)


# ==============================
# MESSAGE TEMPLATES
# ==============================
def get_message_template(template_type, data):
    templates = {
        "thank_you": "Thank you for your purchase at Aziel Investments! We appreciate your business. {customer_name}, your order #{receipt_no} of ${total:.2f} was confirmed. Visit us again soon!",
        "review": "Hi {customer_name}, we hope you enjoyed your shopping experience at Aziel Investments. Please take a moment to leave us a review: {review_link}",
        "reengagement": "Hi {customer_name}, we miss you at Aziel Investments! As a valued customer, enjoy {discount}% off your next purchase. Valid until {expiry}. Visit us today!",
        "birthday": "Happy Birthday {customer_name}! Celebrate with {discount}% off at Aziel Investments this week. Enjoy your special day!",
        "abandoned_cart": "Hi {customer_name}, you left items in your cart at Aziel Investments. Complete your purchase and get {discount}% off! {cart_link}",
        "loyalty_update": "Hi {customer_name}, you have earned {points} loyalty points at Aziel Investments! Redeem them on your next visit. Current balance: ${balance:.2f}",
        "product_recommendation": "Hi {customer_name}, based on your previous purchases, you might like {product_name}. Available now at Aziel Investments for ${price:.2f}!",
    }
    try:
        return templates.get(template_type, "").format(**data)
    except Exception:
        return templates.get(template_type, "")


# ==============================
# CUSTOMER HELPERS (scoped)
# ==============================
def get_customer_total_spent(customer_name, sales_df):
    if sales_df is None or sales_df.empty:
        return 0
    customer_col = _get_customer_col(sales_df)
    total_col = _get_total_col(sales_df)
    if customer_col is None or total_col is None:
        return 0
    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
    ]
    if customer_sales.empty:
        return 0
    return float(to_float(customer_sales[total_col].sum()))


def get_customer_latest_receipt(customer_name, sales_df):
    if sales_df is None or sales_df.empty:
        return "REC-001"
    customer_col = _get_customer_col(sales_df)
    receipt_col = _get_receipt_col(sales_df)
    date_col = _get_date_col(sales_df)
    if customer_col is None or receipt_col is None:
        return "REC-001"
    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
    ]
    if customer_sales.empty:
        return "REC-001"
    if date_col:
        customer_sales = customer_sales.copy()
        customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
        customer_sales = customer_sales.sort_values(date_col, ascending=False)
    return customer_sales.iloc[0].get(receipt_col, "REC-001")


# ==============================
# SEND FOLLOW-UP
# ==============================
def send_followup(customer, followup_type, message, branch_id=None):
    """Send a follow-up message and log it against the correct branch."""
    branch_id = _resolve_branch(branch_id)
    settings = load_followup_settings()
    phone = customer.get("phone", "")
    name = customer.get("name", "Valued Customer")

    if not settings.get("sms_enabled", True):
        return False, "SMS is disabled in settings"
    if not phone or phone == "":
        return False, f"No phone number available for {name}"

    try:
        valid, standardized, msg = validate_zimbabwe_phone(phone)
        if not valid:
            return False, f"Invalid phone number {phone}: {msg}"
        phone_clean = standardized
    except Exception:
        phone_clean = re.sub(r'\D', '', str(phone))
        if phone_clean.startswith('0'):
            phone_clean = phone_clean[1:]
        if not phone_clean.startswith('263'):
            phone_clean = '263' + phone_clean

    print(f"[{branch_id}] Sending to: {name} ({phone_clean})")
    print(f"[{branch_id}] Message: {message[:100]}...")

    sms_result = send_sms(
        recipient=phone_clean,
        message=message,
        sms_type="FOLLOWUP",
        sent_by=st.session_state.get("username", "system"),
    )

    df = load_followup_logs()
    log_id = f"FL{len(df)+1:08d}"

    new_log = pd.DataFrame([{
        "log_id": log_id,
        "timestamp": datetime.now().isoformat(),
        "branch_id": branch_id,
        "customer_name": name,
        "customer_phone": phone,
        "customer_email": customer.get("email", ""),
        "followup_type": followup_type,
        "message": message[:500],
        "sent_date": datetime.now().isoformat(),
        "status": "SENT" if sms_result.get("success", False) else "FAILED",
        "response": sms_result.get("message", ""),
        "notes": f"[{branch_id}] Sent via SMS. Phone: {phone_clean}. Result: {sms_result.get('message', 'Unknown')}",
    }])

    df = pd.concat([df, new_log], ignore_index=True)
    save_followup_logs(df)

    return sms_result.get("success", False), sms_result.get("message", "")


def send_thank_you(customer, receipt_no, total, branch_id=None):
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "receipt_no": receipt_no,
        "total": total,
    }
    message = get_message_template("thank_you", data)
    return send_followup(customer, "THANK_YOU", message, branch_id=branch_id)


def send_review_request(customer, receipt_no, branch_id=None):
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "review_link": "https://azielinvestments.com/review",
    }
    message = get_message_template("review", data)
    return send_followup(customer, "REVIEW_REQUEST", message, branch_id=branch_id)


def send_reengagement(customer, discount=10, expiry_days=14, branch_id=None):
    expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "discount": discount,
        "expiry": expiry,
    }
    message = get_message_template("reengagement", data)
    return send_followup(customer, "REENGAGEMENT", message, branch_id=branch_id)


def send_birthday_wish(customer, discount=15, branch_id=None):
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "discount": discount,
    }
    message = get_message_template("birthday", data)
    return send_followup(customer, "BIRTHDAY", message, branch_id=branch_id)


def send_abandoned_cart(customer, cart_items, discount=10, branch_id=None):
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "discount": discount,
        "cart_link": "https://azielinvestments.com/cart",
    }
    message = get_message_template("abandoned_cart", data)
    return send_followup(customer, "ABANDONED_CART", message, branch_id=branch_id)


# ==============================
# ANALYTICS (scoped)
# ==============================
def get_followup_stats(branch_id=None):
    branch_id = _resolve_branch(branch_id)
    df = load_followup_logs()

    if df.empty:
        return {"total": 0, "by_type": {}, "sent_today": 0, "last_7_days": 0, "success_rate": 0}

    # Scope
    if not _is_all_branches(branch_id) and "branch_id" in df.columns:
        df = df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()]

    if df.empty:
        return {"total": 0, "by_type": {}, "sent_today": 0, "last_7_days": 0, "success_rate": 0}

    df["sent_date"] = pd.to_datetime(df["sent_date"], errors="coerce")

    total = len(df)
    by_type = df["followup_type"].value_counts().to_dict()
    sent_today = len(df[df["sent_date"] >= datetime.now().replace(hour=0, minute=0, second=0)])
    last_7_days = len(df[df["sent_date"] >= datetime.now() - timedelta(days=7)])

    success_count = len(df[df["status"] == "SENT"])
    success_rate = (success_count / total * 100) if total > 0 else 0

    return {
        "total": total,
        "by_type": by_type,
        "sent_today": sent_today,
        "last_7_days": last_7_days,
        "success_rate": success_rate,
    }


def show_toast(message, type="info"):
    if type == "success":
        st.success(f"{message}")
    elif type == "error":
        st.error(f"{message}")
    elif type == "warning":
        st.warning(f"{message}")
    else:
        st.info(f"{message}")


# ==============================
# DASHBOARD
# ==============================
def automated_followup_dashboard(branch_id=None):
    st.title("Automated Customer Follow-up")
    st.caption("Thank-you messages, reviews, re-engagement — branch-scoped")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access automated follow-up.")
        return

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Sending on behalf of: **{branch_label}**")

    init_followup_files()

    # Scoped loads
    customers_df = get_customers_from_sales(branch_id=branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    products_df = _load_scoped(load_products, branch_id)

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Dashboard", "Send Follow-ups", "Schedule", "History", "Settings",
    ])

    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## Follow-up Dashboard")

        stats = get_followup_stats(branch_id)

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Follow-ups", stats["total"])
        with col2:
            st.metric("Today", stats["sent_today"])
        with col3:
            st.metric("Last 7 Days", stats["last_7_days"])
        with col4:
            st.metric("Customers", len(customers_df) if not customers_df.empty else 0)
        with col5:
            st.metric("Success Rate", f"{stats['success_rate']:.1f}%")

        if stats["by_type"]:
            st.markdown("### Follow-up by Type")
            types_df = pd.DataFrame(list(stats["by_type"].items()), columns=["Type", "Count"])
            st.bar_chart(types_df.set_index("Type"))

        st.markdown("### Customers Needing Attention")

        if not customers_df.empty and "last_purchase_date" in customers_df.columns:
            customers_df = customers_df.copy()
            customers_df["last_purchase_date"] = pd.to_datetime(
                customers_df["last_purchase_date"], errors="coerce"
            )
            customers_df["days_inactive"] = (
                datetime.now() - customers_df["last_purchase_date"]
            ).dt.days

            inactive = customers_df[customers_df["days_inactive"] > 30]

            if not inactive.empty:
                st.warning(f"{len(inactive)} customers inactive for over 30 days in {branch_label}")
                st.dataframe(
                    inactive[["customer_name", "phone", "total_spent", "days_inactive"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "days_inactive": st.column_config.NumberColumn("Days Inactive")
                    },
                )

                if st.button("Send Re-engagement to All", use_container_width=True,
                             key=f"reengage_all_{branch_id}"):
                    count = 0
                    for _, customer in inactive.iterrows():
                        success, _ = send_reengagement(
                            {"name": customer["customer_name"], "phone": customer["phone"]},
                            discount=10, branch_id=branch_id,
                        )
                        if success:
                            count += 1
                    st.success(f"Sent re-engagement to {count} customers in {branch_label}!")
                    show_toast(f"Re-engagement sent to {count} customers", "success")
            else:
                st.success(f"All customers in {branch_label} are active!")
        else:
            st.info(f"No customer purchase data available for {branch_label}")

    # ==============================
    # TAB 2: SEND FOLLOW-UPS
    # ==============================
    with tab2:
        st.markdown("## Send Follow-ups")
        st.caption(f"Recipients come from {branch_label} only.")

        try:
            from backend.integrations.sms_gateway import send_sms as _sms  # noqa: F401
            st.success("SMS Gateway is available")
        except Exception:
            st.warning("SMS Gateway not available. Messages will be logged only.")

        followup_type = st.selectbox(
            "Select Follow-up Type",
            [
                "Thank You Message",
                "Review Request",
                "Re-engagement Campaign",
                "Birthday Wishes",
                "Abandoned Cart Recovery",
                "Custom Message",
            ],
            key=f"followup_type_{branch_id}",
        )

        if customers_df.empty:
            st.warning(f"No customers found for {branch_label}")
            return

        customer_list = customers_df["customer_name"].tolist() if "customer_name" in customers_df.columns else []

        if not customer_list:
            st.warning("No customers found")
            return

        selected_customers = st.multiselect(
            "Select Customers",
            customer_list,
            format_func=lambda x: (
                f"{x} - "
                f"{customers_df[customers_df['customer_name'] == x]['phone'].iloc[0] if 'phone' in customers_df.columns else ''}"
            ),
            key=f"selected_customers_{branch_id}",
        )

        if not selected_customers:
            return

        st.markdown("### Message Preview")
        sample_customer = customers_df[customers_df["customer_name"] == selected_customers[0]].iloc[0]
        sample_name = sample_customer.get("customer_name", "Valued Customer")

        customer_total = get_customer_total_spent(sample_name, sales_df)
        latest_receipt = get_customer_latest_receipt(sample_name, sales_df)

        if followup_type == "Thank You Message":
            receipt_no = st.text_input("Receipt Number", value=latest_receipt,
                                       key=f"ty_receipt_{branch_id}")
            st.info(f"Customer's Total Spending: ${customer_total:.2f}")

            use_auto_total = st.checkbox("Use customer's actual total", value=True,
                                         key=f"ty_use_auto_{branch_id}")
            if use_auto_total:
                total = customer_total
                st.info(f"Using customer's actual total: ${total:.2f}")
            else:
                total = st.number_input("Total Amount ($)", min_value=0.0,
                                        value=customer_total if customer_total > 0 else 10.0,
                                        key=f"ty_total_{branch_id}")

            preview_message = get_message_template("thank_you", {
                "customer_name": sample_name, "receipt_no": receipt_no, "total": total,
            })
            st.info(preview_message)

            if st.button("Send Thank You", type="primary", use_container_width=True,
                         key=f"send_ty_{branch_id}"):
                count = 0
                for customer in selected_customers:
                    customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                    cust_name = customer_data.get("customer_name", "Valued Customer")
                    cust_total = get_customer_total_spent(cust_name, sales_df)
                    cust_receipt = get_customer_latest_receipt(cust_name, sales_df)
                    success, msg = send_thank_you(
                        {"name": cust_name, "phone": customer_data.get("phone", "")},
                        cust_receipt,
                        cust_total if use_auto_total else total,
                        branch_id=branch_id,
                    )
                    if success:
                        count += 1
                    else:
                        st.warning(f"Failed for {cust_name}: {msg}")
                st.success(f"Sent to {count} customers in {branch_label}!")
                show_toast(f"Thank you messages sent to {count} customers", "success")

        elif followup_type == "Review Request":
            preview_message = get_message_template("review", {
                "customer_name": sample_name,
                "review_link": "https://azielinvestments.com/review",
            })
            st.info(preview_message)

            if st.button("Send Review Request", type="primary", use_container_width=True,
                         key=f"send_rv_{branch_id}"):
                count = 0
                for customer in selected_customers:
                    customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                    cust_name = customer_data.get("customer_name", "Valued Customer")
                    success, msg = send_review_request(
                        {"name": cust_name, "phone": customer_data.get("phone", "")},
                        get_customer_latest_receipt(cust_name, sales_df),
                        branch_id=branch_id,
                    )
                    if success:
                        count += 1
                    else:
                        st.warning(f"Failed for {cust_name}: {msg}")
                st.success(f"Sent to {count} customers in {branch_label}!")
                show_toast(f"Review requests sent to {count} customers", "success")

        elif followup_type == "Re-engagement Campaign":
            discount = st.number_input("Discount (%)", min_value=5, max_value=50, value=10,
                                       key=f"re_discount_{branch_id}")
            expiry_days = st.number_input("Valid for (days)", min_value=7, max_value=30, value=14,
                                          key=f"re_expiry_{branch_id}")
            st.info(f"Customer's Total Spending: ${customer_total:.2f}")

            preview_message = get_message_template("reengagement", {
                "customer_name": sample_name,
                "discount": discount,
                "expiry": (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d"),
            })
            st.info(preview_message)

            if st.button("Send Re-engagement", type="primary", use_container_width=True,
                         key=f"send_re_{branch_id}"):
                count = 0
                for customer in selected_customers:
                    customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                    cust_name = customer_data.get("customer_name", "Valued Customer")
                    success, msg = send_reengagement(
                        {"name": cust_name, "phone": customer_data.get("phone", "")},
                        discount, expiry_days, branch_id=branch_id,
                    )
                    if success:
                        count += 1
                    else:
                        st.warning(f"Failed for {cust_name}: {msg}")
                st.success(f"Sent to {count} customers in {branch_label}!")
                show_toast(f"Re-engagement sent to {count} customers", "success")

        elif followup_type == "Birthday Wishes":
            discount = st.number_input("Birthday Discount (%)", min_value=5, max_value=50, value=15,
                                       key=f"bd_discount_{branch_id}")
            preview_message = get_message_template("birthday", {
                "customer_name": sample_name, "discount": discount,
            })
            st.info(preview_message)

            if st.button("Send Birthday Wishes", type="primary", use_container_width=True,
                         key=f"send_bd_{branch_id}"):
                count = 0
                for customer in selected_customers:
                    customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                    cust_name = customer_data.get("customer_name", "Valued Customer")
                    success, msg = send_birthday_wish(
                        {"name": cust_name, "phone": customer_data.get("phone", "")},
                        discount, branch_id=branch_id,
                    )
                    if success:
                        count += 1
                    else:
                        st.warning(f"Failed for {cust_name}: {msg}")
                st.success(f"Sent to {count} customers in {branch_label}!")
                show_toast(f"Birthday wishes sent to {count} customers", "success")

        elif followup_type == "Abandoned Cart Recovery":
            discount = st.number_input("Recovery Discount (%)", min_value=5, max_value=30, value=10,
                                       key=f"ac_discount_{branch_id}")
            preview_message = get_message_template("abandoned_cart", {
                "customer_name": sample_name,
                "discount": discount,
                "cart_link": "https://azielinvestments.com/cart",
            })
            st.info(preview_message)

            if st.button("Send Recovery", type="primary", use_container_width=True,
                         key=f"send_ac_{branch_id}"):
                count = 0
                for customer in selected_customers:
                    customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                    cust_name = customer_data.get("customer_name", "Valued Customer")
                    success, msg = send_abandoned_cart(
                        {"name": cust_name, "phone": customer_data.get("phone", "")},
                        [], discount, branch_id=branch_id,
                    )
                    if success:
                        count += 1
                    else:
                        st.warning(f"Failed for {cust_name}: {msg}")
                st.success(f"Sent to {count} customers in {branch_label}!")
                show_toast(f"Abandoned cart recovery sent to {count} customers", "success")

        elif followup_type == "Custom Message":
            custom_message = st.text_area("Custom Message", height=150,
                                          key=f"custom_msg_{branch_id}")
            if custom_message:
                st.info(f"Preview: {custom_message}")

            if st.button("Send Custom Message", type="primary", use_container_width=True,
                         key=f"send_cm_{branch_id}"):
                if not custom_message:
                    st.error("Please enter a message")
                else:
                    count = 0
                    for customer in selected_customers:
                        customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                        cust_name = customer_data.get("customer_name", "Valued Customer")
                        success, msg = send_followup(
                            {"name": cust_name, "phone": customer_data.get("phone", "")},
                            "CUSTOM", custom_message, branch_id=branch_id,
                        )
                        if success:
                            count += 1
                        else:
                            st.warning(f"Failed for {cust_name}: {msg}")
                    st.success(f"Sent to {count} customers in {branch_label}!")
                    show_toast(f"Custom messages sent to {count} customers", "success")

    # ==============================
    # TAB 3: SCHEDULE
    # ==============================
    with tab3:
        st.markdown("## Follow-up Schedule")
        st.caption(f"Schedule entries are tagged with the branch that created them.")

        schedule_df = load_followup_schedule()

        # Scope the view
        if not _is_all_branches(branch_id) and "branch_id" in schedule_df.columns:
            view_schedule = schedule_df[
                schedule_df["branch_id"].astype(str).str.upper() == str(branch_id).upper()
            ]
        else:
            view_schedule = schedule_df

        if not view_schedule.empty:
            st.dataframe(view_schedule, use_container_width=True, hide_index=True)
        else:
            st.info(f"No scheduled follow-ups for {branch_label}")

        st.markdown("### Schedule New Follow-up")

        col1, col2 = st.columns(2)
        with col1:
            customer_list = (
                customers_df["customer_name"].tolist()
                if not customers_df.empty and "customer_name" in customers_df.columns else [""]
            )
            schedule_customer = st.selectbox("Customer", customer_list,
                                             key=f"sched_customer_{branch_id}")
            schedule_type = st.selectbox(
                "Follow-up Type",
                ["THANK_YOU", "REVIEW_REQUEST", "REENGAGEMENT", "BIRTHDAY", "ABANDONED_CART"],
                key=f"sched_type_{branch_id}",
            )
        with col2:
            schedule_date = st.datetime_input(
                "Schedule Date", datetime.now() + timedelta(days=1),
                key=f"sched_date_{branch_id}",
            )
            schedule_notes = st.text_input("Notes", key=f"sched_notes_{branch_id}")

        if st.button("Add to Schedule", use_container_width=True, key=f"sched_add_{branch_id}"):
            if schedule_customer and schedule_customer != "":
                customer_data = customers_df[customers_df["customer_name"] == schedule_customer].iloc[0]
                new_schedule = pd.DataFrame([{
                    "schedule_id": f"SC{len(schedule_df)+1:08d}",
                    "branch_id": branch_id,
                    "customer_name": schedule_customer,
                    "customer_phone": customer_data.get("phone", ""),
                    "followup_type": schedule_type,
                    "scheduled_date": schedule_date.isoformat(),
                    "message": "",
                    "status": "SCHEDULED",
                    "notes": schedule_notes,
                }])
                schedule_df = pd.concat([schedule_df, new_schedule], ignore_index=True)
                save_followup_schedule(schedule_df)
                st.success(f"Follow-up scheduled for {branch_label}!")
                show_toast("Follow-up scheduled successfully!", "success")
                st.rerun()
            else:
                st.warning("Please select a customer")

    # ==============================
    # TAB 4: HISTORY
    # ==============================
    with tab4:
        st.markdown("## Follow-up History")

        logs_df = load_followup_logs()

        if logs_df.empty:
            st.info(f"No follow-up history for {branch_label}")
        else:
            # Scope filter
            is_owner = role in ("owner", "admin")
            if "branch_id" in logs_df.columns:
                if is_owner:
                    branches_present = sorted(logs_df["branch_id"].dropna().unique().tolist())
                    filter_choice = st.selectbox(
                        "Filter by branch",
                        ["Current branch"] + branches_present + ["All branches"],
                        key=f"history_branch_filter_{branch_id}",
                    )
                    if filter_choice == "Current branch":
                        logs_df = logs_df[logs_df["branch_id"].astype(str).str.upper()
                                          == str(branch_id).upper()]
                    elif filter_choice == "All branches":
                        pass
                    else:
                        logs_df = logs_df[logs_df["branch_id"] == filter_choice]
                else:
                    logs_df = logs_df[logs_df["branch_id"].astype(str).str.upper()
                                      == str(branch_id).upper()]

            if logs_df.empty:
                st.info(f"No follow-up history for {branch_label}")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    type_filter = st.selectbox(
                        "Filter by Type",
                        ["All"] + logs_df["followup_type"].unique().tolist(),
                        key=f"hist_type_{branch_id}",
                    )
                with col2:
                    status_filter = st.selectbox(
                        "Filter by Status",
                        ["All", "SENT", "FAILED"],
                        key=f"hist_status_{branch_id}",
                    )

                filtered = logs_df.copy()
                if type_filter != "All":
                    filtered = filtered[filtered["followup_type"] == type_filter]
                if status_filter != "All":
                    filtered = filtered[filtered["status"] == status_filter]

                st.dataframe(filtered, use_container_width=True, hide_index=True)

                csv = filtered.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Export Follow-up Logs (CSV)",
                    data=csv,
                    file_name=(
                        f"followup_logs_{_branch_slug(branch_id)}_"
                        f"{datetime.now().strftime('%Y%m%d')}.csv"
                    ),
                    mime="text/csv",
                )

    # ==============================
    # TAB 5: SETTINGS
    # ==============================
    with tab5:
        st.markdown("## Follow-up Settings")
        st.caption("Settings are shared across all branches.")

        settings = load_followup_settings()

        st.markdown("### General Settings")
        enabled = st.checkbox("Enable Automated Follow-ups",
                              value=settings.get("enabled", True),
                              key=f"f_enabled_{branch_id}")
        max_per_day = st.number_input(
            "Max Follow-ups per Day", min_value=10, max_value=500,
            value=settings.get("max_followups_per_day", 50),
            key=f"f_max_{branch_id}",
        )

        st.markdown("### Message Types")
        col1, col2 = st.columns(2)
        with col1:
            thank_you = st.checkbox("Thank You Messages",
                                    value=settings.get("thank_you_enabled", True),
                                    key=f"f_ty_{branch_id}")
            thank_you_delay = st.number_input(
                "Thank You Delay (hours)", min_value=1, max_value=24,
                value=settings.get("thank_you_delay_hours", 2),
                key=f"f_ty_delay_{branch_id}",
            )
            review = st.checkbox("Review Requests",
                                 value=settings.get("review_enabled", True),
                                 key=f"f_rv_{branch_id}")
            review_delay = st.number_input(
                "Review Request Delay (days)", min_value=1, max_value=7,
                value=settings.get("review_delay_days", 3),
                key=f"f_rv_delay_{branch_id}",
            )
        with col2:
            reengagement = st.checkbox("Re-engagement Campaigns",
                                       value=settings.get("reengagement_enabled", True),
                                       key=f"f_re_{branch_id}")
            reengagement_days = st.number_input(
                "Inactive Days Before Re-engagement", min_value=7, max_value=90,
                value=settings.get("reengagement_inactive_days", 30),
                key=f"f_re_days_{branch_id}",
            )
            reengagement_discount = st.number_input(
                "Re-engagement Discount (%)", min_value=5, max_value=50,
                value=settings.get("reengagement_discount", 10),
                key=f"f_re_disc_{branch_id}",
            )

        st.markdown("### Birthday & Cart Recovery")
        col1, col2 = st.columns(2)
        with col1:
            birthday = st.checkbox("Birthday Wishes",
                                   value=settings.get("birthday_enabled", True),
                                   key=f"f_bd_{branch_id}")
            birthday_discount = st.number_input(
                "Birthday Discount (%)", min_value=5, max_value=50,
                value=settings.get("birthday_discount", 15),
                key=f"f_bd_disc_{branch_id}",
            )
        with col2:
            abandoned_cart = st.checkbox("Abandoned Cart Recovery",
                                         value=settings.get("abandoned_cart_enabled", True),
                                         key=f"f_ac_{branch_id}")
            cart_delay = st.number_input(
                "Cart Recovery Delay (hours)", min_value=1, max_value=48,
                value=settings.get("abandoned_cart_delay_hours", 24),
                key=f"f_ac_delay_{branch_id}",
            )

        st.markdown("### Communication Channels")
        col1, col2 = st.columns(2)
        with col1:
            sms_enabled = st.checkbox("SMS", value=settings.get("sms_enabled", True),
                                      key=f"f_sms_{branch_id}")
            whatsapp_enabled = st.checkbox("WhatsApp",
                                           value=settings.get("whatsapp_enabled", True),
                                           key=f"f_wa_{branch_id}")
        with col2:
            email_enabled = st.checkbox("Email",
                                        value=settings.get("email_enabled", False),
                                        key=f"f_email_{branch_id}")

        if st.button("Save Settings", type="primary", use_container_width=True,
                     key=f"f_save_{branch_id}"):
            settings.update({
                "enabled": enabled,
                "max_followups_per_day": max_per_day,
                "thank_you_enabled": thank_you,
                "thank_you_delay_hours": thank_you_delay,
                "review_enabled": review,
                "review_delay_days": review_delay,
                "reengagement_enabled": reengagement,
                "reengagement_inactive_days": reengagement_days,
                "reengagement_discount": reengagement_discount,
                "birthday_enabled": birthday,
                "birthday_discount": birthday_discount,
                "abandoned_cart_enabled": abandoned_cart,
                "abandoned_cart_delay_hours": cart_delay,
                "sms_enabled": sms_enabled,
                "whatsapp_enabled": whatsapp_enabled,
                "email_enabled": email_enabled,
            })
            save_followup_settings(settings)
            st.success("Settings saved successfully!")
            show_toast("Follow-up settings updated!", "success")


if __name__ == "__main__":
    automated_followup_dashboard()