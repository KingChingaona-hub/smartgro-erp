# backend/integrations/email_reports.py
# Email Reports — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner digest)
#
# Recipient model (data/email_config.json):
#     "recipients": [...]                 -> legacy fallback / All-Branches digest
#     "recipients_by_branch": {
#         "HO": ["ho-manager@example.com"],
#         "NAT": ["nat-manager@example.com"]
#     }
# If `recipients_by_branch` is missing or empty, the legacy `recipients` list
# is used (one email per recipient containing every branch's report — because
# that's what the caller asked for when they ran send_daily_report()).

import streamlit as st
import smtplib
import pandas as pd
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
import json
from pathlib import Path

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_debtors,
    load_branches,
)


# ==============================
# EMAIL CONFIGURATION
# ==============================
EMAIL_CONFIG_FILE = Path("data/email_config.json")


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


def _branch_label_short(branch_id):
    """Compact form for email subjects."""
    if _is_all_branches(branch_id):
        return "All Branches"
    return _branch_label(branch_id)


# ==============================
# LOAD / SAVE CONFIG
# ==============================
def get_email_config():
    """Load email configuration."""
    if not EMAIL_CONFIG_FILE.exists():
        return {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "",
            "sender_password": "",
            "recipient_emails": [],
            "recipients_by_branch": {},
            "enable_daily_report": False,
            "enable_weekly_report": False,
            "enable_low_stock_alert": False,
        }
    try:
        with open(EMAIL_CONFIG_FILE, "r") as f:
            config = json.load(f)
        config.setdefault("recipient_emails", [])
        config.setdefault("recipients_by_branch", {})
        return config
    except Exception as e:
        st.error(f"Error loading email config: {e}")
        return get_email_config()


def save_email_config(config):
    """Save email configuration."""
    try:
        EMAIL_CONFIG_FILE.parent.mkdir(exist_ok=True)
        with open(EMAIL_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving email config: {e}")
        return False


def _recipients_for(branch_id, config=None):
    """
    Return the list of recipients for a given branch.

    Order of resolution:
      1. config["recipients_by_branch"][<CODE>]   if present and non-empty
      2. config["recipient_emails"]               legacy global list
    """
    if config is None:
        config = get_email_config()

    if not _is_all_branches(branch_id):
        per_branch = config.get("recipients_by_branch", {}) or {}
        branch_recipients = per_branch.get(str(branch_id).upper(), [])
        if branch_recipients:
            return [r.strip() for r in branch_recipients if r and str(r).strip()]

    return [r.strip() for r in config.get("recipient_emails", []) if r and str(r).strip()]


# ==============================
# SMTP
# ==============================
def test_email_connection():
    config = get_email_config()
    if not config["sender_email"] or not config["sender_password"]:
        return False, "Email not configured. Please set sender email and password in Settings."
    try:
        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        server.starttls()
        server.login(config["sender_email"], config["sender_password"])
        server.quit()
        return True, "Connection successful!"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. For Gmail, use an App Password (not your regular password)."
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def send_email(recipient, subject, body, attachment=None):
    config = get_email_config()
    if not config["sender_email"] or not config["sender_password"]:
        return False, "Email not configured. Please set up email in Settings."
    try:
        msg = MIMEMultipart()
        msg['From'] = config["sender_email"]
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename=report.pdf')
            msg.attach(part)

        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        server.starttls()
        server.login(config["sender_email"], config["sender_password"])
        server.send_message(msg)
        server.quit()
        return True, f"Email sent to {recipient}"
    except smtplib.SMTPAuthenticationError:
        return False, (
            "Authentication failed! For Gmail, use an App Password. "
            "Go to Google Account → Security → App Passwords."
        )
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


# ==============================
# COLUMN HELPERS
# ==============================
def _find_col(df, names, default=None):
    if df is None or df.empty:
        return default
    for c in names:
        if c in df.columns:
            return c
    return default


# ==============================
# REPORT GENERATORS (branch-scoped)
# ==============================
def generate_daily_sales_report(branch_id=None):
    """Daily sales report scoped to a branch."""
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    sales_df = _load_scoped(load_sales, branch_id)

    today = datetime.now().strftime("%Y-%m-%d")

    if sales_df is not None and not sales_df.empty:
        date_col = _find_col(sales_df, ["date", "sale_date", "transaction_date", "created_at"])
        receipt_col = _find_col(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
        total_col = _find_col(sales_df, ["final_total", "total", "amount", "sale_amount"])
        items_col = _find_col(sales_df, ["items", "quantity", "qty", "item_count"])

        if date_col:
            sales_df = sales_df.copy()
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            today_sales = sales_df[sales_df[date_col].dt.strftime("%Y-%m-%d") == today]
        else:
            today_sales = pd.DataFrame()
    else:
        today_sales = pd.DataFrame()
        receipt_col = None
        total_col = None
        items_col = None

    # Deduplicate by receipt so revenue is not inflated
    if not today_sales.empty and receipt_col:
        unique_today = today_sales.drop_duplicates(subset=[receipt_col])
    else:
        unique_today = today_sales

    total_revenue = (
        float(pd.to_numeric(unique_today[total_col], errors="coerce").fillna(0).sum())
        if total_col and not unique_today.empty else 0.0
    )
    total_transactions = len(unique_today)
    total_items = (
        int(pd.to_numeric(today_sales[items_col], errors="coerce").fillna(0).sum())
        if items_col and not today_sales.empty else 0
    )
    avg_transaction = total_revenue / total_transactions if total_transactions > 0 else 0

    report = f"""
{'='*50}
AZIEL INVESTMENTS - DAILY SALES REPORT
{'='*50}

Branch: {label}
Date: {datetime.now().strftime('%Y-%m-%d')}
Time: {datetime.now().strftime('%H:%M:%S')}

{'─'*40}
SALES SUMMARY
{'─'*40}
Total Revenue: ${total_revenue:,.2f}
Total Transactions: {total_transactions}
Total Items Sold: {total_items}
Average Transaction: ${avg_transaction:.2f}

{'─'*40}
{'='*50}
Generated by SmartGro ERP System - Aziel Investments
Contact: +263 78 290 5853
"""
    return report


def generate_weekly_sales_report(branch_id=None):
    """Weekly sales report scoped to a branch."""
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    sales_df = _load_scoped(load_sales, branch_id)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    if sales_df is not None and not sales_df.empty:
        date_col = _find_col(sales_df, ["date", "sale_date", "transaction_date", "created_at"])
        receipt_col = _find_col(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
        total_col = _find_col(sales_df, ["final_total", "total", "amount", "sale_amount"])

        if date_col and total_col:
            sales_df = sales_df.copy()
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            week_sales = sales_df[
                (sales_df[date_col] >= start_date) & (sales_df[date_col] <= end_date)
            ]
        else:
            week_sales = pd.DataFrame()
    else:
        week_sales = pd.DataFrame()
        receipt_col = None
        total_col = None
        date_col = None

    if not week_sales.empty and receipt_col:
        unique_week = week_sales.drop_duplicates(subset=[receipt_col])
    else:
        unique_week = week_sales

    total_revenue = (
        float(pd.to_numeric(unique_week[total_col], errors="coerce").fillna(0).sum())
        if total_col and not unique_week.empty else 0.0
    )
    total_transactions = len(unique_week)

    daily_breakdown = ""
    if not unique_week.empty and date_col:
        try:
            daily = (
                unique_week.groupby(unique_week[date_col].dt.strftime("%A"))[total_col]
                .sum()
                .apply(lambda x: float(x))
            )
            for day, amount in daily.items():
                daily_breakdown += f"{day}: ${amount:,.2f}\n"
        except Exception:
            daily_breakdown = "(Could not compute daily breakdown)\n"

    report = f"""
{'='*50}
AZIEL INVESTMENTS - WEEKLY SALES REPORT
{'='*50}

Branch: {label}
Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'─'*40}
SALES SUMMARY
{'─'*40}
Total Revenue: ${total_revenue:,.2f}
Total Transactions: {total_transactions}

{'─'*40}
DAILY BREAKDOWN
{'─'*40}
{daily_breakdown}
{'─'*40}
{'='*50}
Generated by SmartGro ERP System - Aziel Investments
"""
    return report


def generate_low_stock_alert(branch_id=None):
    """Low stock alert scoped to a branch."""
    branch_id = _resolve_branch(branch_id)
    label = _branch_label(branch_id)

    products_df = _load_scoped(load_products, branch_id)

    if products_df is None or products_df.empty:
        return None

    if "stock" not in products_df.columns or "reorder_level" not in products_df.columns:
        return None

    products_df = products_df.copy()
    products_df["stock"] = pd.to_numeric(products_df["stock"], errors="coerce").fillna(0)
    products_df["reorder_level"] = pd.to_numeric(
        products_df["reorder_level"], errors="coerce"
    ).fillna(0)

    low_stock = products_df[products_df["stock"] <= products_df["reorder_level"]]
    if low_stock.empty:
        return None

    items = ""
    for _, product in low_stock.iterrows():
        items += (
            f"• {product['name']}: {int(product['stock'])} units "
            f"(Reorder at {int(product['reorder_level'])})\n"
        )

    report = f"""
{'='*50}
AZIEL INVESTMENTS - LOW STOCK ALERT
{'='*50}

Branch: {label}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The following products in {label} are below reorder level:

{items}
{'─'*40}
ACTION REQUIRED: Please place purchase orders for these items.

{'='*50}
"""
    return report, low_stock


# ==============================
# SEND REPORTS
# ==============================
def _send_report_to(recipients, subject, body):
    """Send an email to each recipient. Returns (success_count, errors)."""
    success_count = 0
    errors = []
    for recipient in recipients:
        if recipient and recipient.strip():
            success, message = send_email(recipient.strip(), subject, body)
            if success:
                success_count += 1
            else:
                errors.append(f"{recipient}: {message}")
    return success_count, errors


def send_daily_report(branch_id=None):
    """Send the daily report for a branch (or All Branches)."""
    config = get_email_config()
    branch_id = _resolve_branch(branch_id)

    if not config.get("enable_daily_report", False):
        return False, "Daily reports are disabled in settings"

    if not config["sender_email"] or not config["sender_password"]:
        return False, "Sender email not configured. Set up email in Settings."

    recipients = _recipients_for(branch_id, config)
    if not recipients:
        return False, f"No recipient emails configured for {_branch_label(branch_id)}"

    report = generate_daily_sales_report(branch_id=branch_id)
    subject = (
        f"Daily Sales Report [{_branch_label_short(branch_id)}] - "
        f"{datetime.now().strftime('%Y-%m-%d')}"
    )

    success_count, errors = _send_report_to(recipients, subject, report)
    if success_count > 0:
        return True, (
            f"Sent to {success_count} recipient(s) for {_branch_label(branch_id)}"
        )
    return False, f"Failed to send. Errors: {'; '.join(errors[:3])}"


def send_weekly_report(branch_id=None):
    """Send the weekly report for a branch (or All Branches)."""
    config = get_email_config()
    branch_id = _resolve_branch(branch_id)

    if not config.get("enable_weekly_report", False):
        return False, "Weekly reports are disabled in settings"

    if not config["sender_email"] or not config["sender_password"]:
        return False, "Sender email not configured. Set up email in Settings."

    recipients = _recipients_for(branch_id, config)
    if not recipients:
        return False, f"No recipient emails configured for {_branch_label(branch_id)}"

    report = generate_weekly_sales_report(branch_id=branch_id)
    subject = (
        f"Weekly Sales Report [{_branch_label_short(branch_id)}] - "
        f"Week Ending {datetime.now().strftime('%Y-%m-%d')}"
    )

    success_count, errors = _send_report_to(recipients, subject, report)
    if success_count > 0:
        return True, (
            f"Sent to {success_count} recipient(s) for {_branch_label(branch_id)}"
        )
    return False, f"Failed to send. Errors: {'; '.join(errors[:3])}"


def send_low_stock_alert(branch_id=None):
    """Send the low-stock alert for a branch (or All Branches)."""
    config = get_email_config()
    branch_id = _resolve_branch(branch_id)

    if not config.get("enable_low_stock_alert", False):
        return False, "Low stock alerts are disabled in settings"

    if not config["sender_email"] or not config["sender_password"]:
        return False, "Sender email not configured. Set up email in Settings."

    recipients = _recipients_for(branch_id, config)
    if not recipients:
        return False, f"No recipient emails configured for {_branch_label(branch_id)}"

    result = generate_low_stock_alert(branch_id=branch_id)
    if result is None:
        return False, f"No low stock items found in {_branch_label(branch_id)}"

    report, _low_stock = result
    subject = (
        f"LOW STOCK ALERT [{_branch_label_short(branch_id)}] - "
        f"{datetime.now().strftime('%Y-%m-%d')}"
    )

    success_count, errors = _send_report_to(recipients, subject, report)
    if success_count > 0:
        return True, (
            f"Alert sent to {success_count} recipient(s) for {_branch_label(branch_id)}"
        )
    return False, f"Failed to send. Errors: {'; '.join(errors[:3])}"


def send_test_email(branch_id=None):
    """Send a test email to the branch's recipients (or the legacy list)."""
    config = get_email_config()
    branch_id = _resolve_branch(branch_id)
    recipients = _recipients_for(branch_id, config)

    if not recipients:
        return False, f"No recipient emails configured for {_branch_label(branch_id)}"

    if not config["sender_email"] or not config["sender_password"]:
        return False, "Sender email not configured"

    label = _branch_label(branch_id)
    test_body = f"""
{'='*40}
AZIEL INVESTMENTS - TEST EMAIL
{'='*40}

Branch: {label}
Sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
From: {config['sender_email']}

If you received this, your email settings are working correctly
for {label}.

{'='*40}
SmartGro ERP System
"""

    success_count, errors = _send_report_to(
        recipients, f"SmartGro ERP - Test Email [{label}]", test_body
    )
    if success_count > 0:
        return True, (
            f"Test email sent to {success_count} recipient(s) for {label}"
        )
    return False, f"Failed to send test email. Errors: {'; '.join(errors[:3])}"


# ==============================
# CONVENIENCE: send one email per branch
# ==============================
def send_daily_report_to_all_branches():
    """
    Owner-mode helper: sends one email per branch, addressed to that branch's
    recipients. Returns (ok_count, errors).
    """
    config = get_email_config()
    ok_count = 0
    errors = []

    try:
        bdf = load_branches()
    except Exception:
        bdf = pd.DataFrame()

    if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
        return 0, ["No branches configured"]

    for bid in bdf["branch_id"].astype(str).tolist():
        success, message = send_daily_report(branch_id=bid)
        if success:
            ok_count += 1
        else:
            errors.append(f"{bid}: {message}")
    return ok_count, errors


def send_weekly_report_to_all_branches():
    config = get_email_config()
    ok_count = 0
    errors = []

    try:
        bdf = load_branches()
    except Exception:
        bdf = pd.DataFrame()

    if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
        return 0, ["No branches configured"]

    for bid in bdf["branch_id"].astype(str).tolist():
        success, message = send_weekly_report(branch_id=bid)
        if success:
            ok_count += 1
        else:
            errors.append(f"{bid}: {message}")
    return ok_count, errors


def send_low_stock_alert_to_all_branches():
    config = get_email_config()
    ok_count = 0
    errors = []

    try:
        bdf = load_branches()
    except Exception:
        bdf = pd.DataFrame()

    if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
        return 0, ["No branches configured"]

    for bid in bdf["branch_id"].astype(str).tolist():
        success, message = send_low_stock_alert(branch_id=bid)
        if success:
            ok_count += 1
        else:
            errors.append(f"{bid}: {message}")
    return ok_count, errors