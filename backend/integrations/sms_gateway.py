# backend/integrations/sms_gateway.py
# SMS Gateway Integration — customer-scoped, branch-audited.
#
# Design (SMS = A):
#   - SMS is a message to a CUSTOMER, not to a branch.
#   - The customer is one entity across all branches. A birthday wish is sent
#     once, whichever branch's session triggered it.
#   - sms_logs.csv carries a branch_id column for AUDIT ONLY: "which branch's
#     session sent this message". It is not used to filter recipients.
#
# Branch scoping (audit + history filter):
#     branch_id = None          -> session branch (default for new logs)
#     branch_id = "HO"/"NAT"/.. -> explicit code
#     branch_id = "__ALL__"     -> only meaningful for the History filter

import streamlit as st
import pandas as pd
import json
import requests
import re
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import base64

from backend.utils.phone_utils import validate_zimbabwe_phone
from backend.core.animations import show_toast, show_confetti
from backend.core.db_adapter import load_branches


# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
SMS_FILE = DATA_DIR / "sms_logs.csv"
SMS_TEMPLATES_FILE = DATA_DIR / "sms_templates.json"
SMS_SETTINGS_FILE = DATA_DIR / "sms_settings.json"

SMS_LOG_COLUMNS = [
    "sms_id", "sent_date", "branch_id", "recipient", "message",
    "type", "status", "sent_by", "response", "cost",
]


# ==============================
# BRANCH RESOLUTION (audit only)
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


# ==============================
# INITIALIZATION
# ==============================
def init_sms_files():
    DATA_DIR.mkdir(exist_ok=True)

    # Logs — migrate to add branch_id
    if not SMS_FILE.exists():
        pd.DataFrame(columns=SMS_LOG_COLUMNS).to_csv(SMS_FILE, index=False)
    else:
        try:
            existing = pd.read_csv(SMS_FILE)
            if "branch_id" not in existing.columns:
                existing.insert(2, "branch_id", "HO")
                existing = existing[[c for c in SMS_LOG_COLUMNS if c in existing.columns]]
                existing.to_csv(SMS_FILE, index=False)
        except Exception:
            pd.DataFrame(columns=SMS_LOG_COLUMNS).to_csv(SMS_FILE, index=False)

    # Templates (global vocabulary — shared across branches)
    if not SMS_TEMPLATES_FILE.exists():
        templates = {
            "welcome": {
                "name": "Welcome Message",
                "template": "Welcome to Aziel Investments! Thank you for shopping with us. Your loyalty is appreciated.",
                "category": "Customer Onboarding",
            },
            "order_confirmation": {
                "name": "Order Confirmation",
                "template": "Your order #{order_id} has been confirmed. Total: ${total}. Thank you for shopping at Aziel Investments.",
                "category": "Sales",
            },
            "delivery_notification": {
                "name": "Delivery Notification",
                "template": "Your order #{order_id} has been dispatched and will be delivered today. Thank you for choosing Aziel Investments.",
                "category": "Logistics",
            },
            "payment_reminder": {
                "name": "Payment Reminder",
                "template": "Dear {customer}, your payment of ${amount} is due on {due_date}. Please settle your account to avoid late fees.",
                "category": "Finance",
            },
            "promotional": {
                "name": "Promotional Offer",
                "template": "Special offer at Aziel Investments! {offer} valid until {expiry}. Visit us today!",
                "category": "Marketing",
            },
            "birthday": {
                "name": "Birthday Wishes",
                "template": "Happy Birthday {customer}! Enjoy a special {discount}% discount at Aziel Investments this week.",
                "category": "Customer Engagement",
            },
            "thank_you": {
                "name": "Thank You Message",
                "template": "Thank you for your purchase at Aziel Investments! We value your business.",
                "category": "Customer Engagement",
            },
            "review_request": {
                "name": "Review Request",
                "template": "We hope you enjoyed your shopping experience at Aziel Investments. Please leave us a review: {link}",
                "category": "Customer Engagement",
            },
            "re_engagement": {
                "name": "Re-engagement",
                "template": "We miss you at Aziel Investments! Visit us and get {discount}% off your next purchase.",
                "category": "Customer Engagement",
            },
            "two_factor": {
                "name": "2FA Code",
                "template": "Your Aziel Investments verification code is: {code}. Valid for 5 minutes.",
                "category": "Security",
            },
        }
        with open(SMS_TEMPLATES_FILE, "w") as f:
            json.dump(templates, f, indent=2)

    # Settings (global — one SMS account / provider for the whole business)
    if not SMS_SETTINGS_FILE.exists():
        settings = {
            "provider": "africastalking",
            "sender_id": "AzielInvest",
            "enabled": True,
            "default_country_code": "263",
            "test_mode": True,
            "africastalking_api_key": "",
            "africastalking_username": "sandbox",
            "twilio_account_sid": "",
            "twilio_auth_token": "",
            "twilio_phone_number": "",
            "semaphore_api_key": "",
            "semaphore_sender_name": "AzielInvest",
        }
        with open(SMS_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)


# ==============================
# LOAD / SAVE
# ==============================
def load_sms_logs(branch_id=None):
    """
    Load SMS logs.
    - branch_id=None        -> everything (raw)
    - branch_id="HO"/"NAT"  -> only that branch's sent rows
    - branch_id="__ALL__"   -> everything (used for the owner filter)
    """
    init_sms_files()
    try:
        df = pd.read_csv(SMS_FILE)
    except Exception:
        return pd.DataFrame(columns=SMS_LOG_COLUMNS)

    if "branch_id" not in df.columns:
        df["branch_id"] = "HO"

    if branch_id is None:
        return df
    branch_id = _resolve_branch(branch_id)
    if _is_all_branches(branch_id):
        return df
    return df[df["branch_id"].astype(str).str.upper() == str(branch_id).upper()].copy()


def save_sms_logs(df):
    df.to_csv(SMS_FILE, index=False)


def load_sms_templates():
    init_sms_files()
    with open(SMS_TEMPLATES_FILE, "r") as f:
        return json.load(f)


def save_sms_templates(templates):
    with open(SMS_TEMPLATES_FILE, "w") as f:
        json.dump(templates, f, indent=2)


def load_sms_settings():
    init_sms_files()
    try:
        with open(SMS_SETTINGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "provider": "africastalking",
            "sender_id": "AzielInvest",
            "enabled": True,
            "default_country_code": "263",
            "test_mode": True,
            "africastalking_api_key": "",
            "africastalking_username": "sandbox",
            "twilio_account_sid": "",
            "twilio_auth_token": "",
            "twilio_phone_number": "",
            "semaphore_api_key": "",
            "semaphore_sender_name": "AzielInvest",
        }


def save_sms_settings(settings):
    with open(SMS_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def log_sms(recipient, message, sms_type, status, sent_by, response,
            cost=0, branch_id=None):
    """Append an SMS log row. Records the branch that sent it (audit only)."""
    branch_id = _resolve_branch(branch_id)

    df = load_sms_logs(branch_id=ALL_BRANCHES)
    new_sms = pd.DataFrame([{
        "sms_id": f"SMS{len(df)+1:08d}",
        "sent_date": datetime.now().isoformat(),
        "branch_id": _branch_slug(branch_id),
        "recipient": recipient,
        "message": message[:500],
        "type": sms_type,
        "status": status,
        "sent_by": sent_by,
        "response": response,
        "cost": cost,
    }])
    df = pd.concat([df, new_sms], ignore_index=True)
    save_sms_logs(df)


# ==============================
# PROVIDER CONNECTORS
# ==============================
def test_africastalking_connection(api_key, username):
    try:
        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "ApiKey": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "username": username,
            "to": "+263771234567",
            "message": "Test",
            "from": "AzielInvest",
        }
        response = requests.post(url, headers=headers, data=data, timeout=30)
        return {
            "status_code": response.status_code,
            "response": response.text[:500],
        }
    except Exception as e:
        return {"error": str(e)}


def send_sms_africastalking(recipient, message, settings):
    try:
        api_key = settings.get("africastalking_api_key", "").strip()
        username = settings.get("africastalking_username", "sandbox").strip()

        if not api_key:
            return {"success": False, "message": "API Key not configured."}

        if not recipient.startswith("+"):
            recipient = f"+{settings.get('default_country_code', '263')}{recipient.lstrip('0')}"

        if settings.get("test_mode", True):
            return {
                "success": True,
                "message": f"TEST MODE: SMS would be sent to {recipient}",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00,
            }

        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "ApiKey": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "username": username,
            "to": recipient,
            "message": message,
            "from": settings.get("sender_id", "AzielInvest")[:11],
        }

        response = requests.post(url, headers=headers, data=data, timeout=30)

        if response.status_code in (200, 201):
            try:
                result = response.json()
                if "SMSMessageData" in result:
                    recipients_data = result["SMSMessageData"].get("Recipients", [])
                    if recipients_data:
                        status = recipients_data[0].get("status", "")
                        if status.lower() == "success":
                            return {
                                "success": True,
                                "message": "SMS sent successfully!",
                                "sms_id": recipients_data[0].get("messageId"),
                                "cost": 0.05,
                            }
                        return {"success": False, "message": f"Error: {status}"}
                error_msg = result.get("error", "Unknown error")
                return {"success": False, "message": f"{error_msg}"}
            except Exception:
                return {"success": False, "message": f"Invalid response: {response.text[:200]}"}

        if response.status_code == 401:
            return {
                "success": False,
                "message": (
                    "Authentication failed (401).\n\nPlease check:\n"
                    "1. Your API Key is correct\n"
                    "2. Your username is 'sandbox'\n"
                    "3. You have credit in your account"
                ),
            }
        return {
            "success": False,
            "message": f"HTTP Error {response.status_code}: {response.text[:200]}",
        }

    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Network error: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}


def send_sms_twilio(recipient, message, settings):
    try:
        account_sid = settings.get("twilio_account_sid", "")
        auth_token = settings.get("twilio_auth_token", "")
        twilio_phone = settings.get("twilio_phone_number", "")

        if not account_sid or not auth_token or not twilio_phone:
            return {"success": False, "message": "Twilio credentials not configured."}

        if not recipient.startswith("+"):
            recipient = f"+{settings.get('default_country_code', '263')}{recipient.lstrip('0')}"

        if settings.get("test_mode", True):
            return {
                "success": True,
                "message": f"TEST MODE: SMS would be sent to {recipient}",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00,
            }

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"To": recipient, "From": twilio_phone, "Body": message}

        response = requests.post(url, headers=headers, data=data, timeout=30)

        if response.status_code in (200, 201):
            result = response.json()
            return {
                "success": True,
                "message": "SMS sent successfully!",
                "sms_id": result.get("sid"),
                "cost": 0.05,
            }
        return {"success": False, "message": f"Failed: {response.text[:200]}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def send_sms_semaphore(recipient, message, settings):
    try:
        api_key = settings.get("semaphore_api_key", "")
        sender_name = settings.get("semaphore_sender_name", "AzielInvest")

        if not api_key:
            return {"success": False, "message": "Semaphore API Key not configured."}

        if recipient.startswith("+"):
            recipient = recipient[1:]

        if settings.get("test_mode", True):
            return {
                "success": True,
                "message": f"TEST MODE: SMS would be sent to {recipient}",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00,
            }

        url = "https://api.semaphore.co/api/v4/messages"
        data = {
            "apikey": api_key,
            "number": recipient,
            "message": message,
            "sendername": sender_name,
        }
        response = requests.post(url, data=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and result:
                status = result[0].get("status", "")
                if status in ("queued", "sent"):
                    return {
                        "success": True,
                        "message": "SMS sent successfully!",
                        "sms_id": result[0].get("message_id"),
                        "cost": 0.05,
                    }
        return {"success": False, "message": f"Failed: {response.text[:200]}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ==============================
# PUBLIC SEND API
# ==============================
def send_sms(recipient, message, sms_type="GENERAL", sent_by="system", branch_id=None):
    """
    Send an SMS. `branch_id` is recorded on the log row for audit. It does NOT
    scope the recipient — the customer is a business-level entity.
    """
    branch_id = _resolve_branch(branch_id)
    settings = load_sms_settings()

    if not settings.get("enabled", True):
        return {"success": False, "message": "SMS service is disabled"}

    valid, standardized, msg = validate_zimbabwe_phone(recipient)
    if not valid:
        return {"success": False, "message": f"Invalid phone number: {msg}"}

    provider = settings.get("provider", "africastalking")

    if provider == "africastalking":
        result = send_sms_africastalking(standardized, message, settings)
    elif provider == "twilio":
        result = send_sms_twilio(standardized, message, settings)
    elif provider == "semaphore":
        result = send_sms_semaphore(standardized, message, settings)
    else:
        return {"success": False, "message": f"Unknown provider: {provider}"}

    log_sms(
        recipient=standardized,
        message=message,
        sms_type=sms_type,
        status="SENT" if result["success"] else "FAILED",
        sent_by=sent_by,
        response=result.get("message", ""),
        cost=result.get("cost", 0),
        branch_id=branch_id,
    )
    return result


def send_bulk_sms(recipients, message, sms_type="BULK", sent_by="system", branch_id=None):
    results = []
    success_count = 0
    for recipient in recipients:
        result = send_sms(recipient, message, sms_type, sent_by, branch_id=branch_id)
        results.append(result)
        if result["success"]:
            success_count += 1
    return {
        "success": success_count > 0,
        "total": len(recipients),
        "success_count": success_count,
        "failed_count": len(recipients) - success_count,
        "results": results,
    }


# ==============================
# TYPED SENDERS
# ==============================
def send_promotional_sms(customer_phones, offer, expiry, sent_by="system", branch_id=None):
    templates = load_sms_templates()
    template = templates.get("promotional", {}).get("template", "")
    message = template.replace("{offer}", offer).replace("{expiry}", expiry)
    return send_bulk_sms(customer_phones, message, "PROMOTIONAL", sent_by, branch_id=branch_id)


def send_order_confirmation(phone, order_id, total, sent_by="system", branch_id=None):
    templates = load_sms_templates()
    template = templates.get("order_confirmation", {}).get("template", "")
    message = template.replace("{order_id}", order_id).replace("{total}", f"{total:.2f}")
    return send_sms(phone, message, "ORDER_CONFIRMATION", sent_by, branch_id=branch_id)


def send_delivery_notification(phone, order_id, sent_by="system", branch_id=None):
    templates = load_sms_templates()
    template = templates.get("delivery_notification", {}).get("template", "")
    message = template.replace("{order_id}", order_id)
    return send_sms(phone, message, "DELIVERY", sent_by, branch_id=branch_id)


def send_payment_reminder(phone, customer, amount, due_date, sent_by="system", branch_id=None):
    templates = load_sms_templates()
    template = templates.get("payment_reminder", {}).get("template", "")
    message = (
        template.replace("{customer}", customer)
        .replace("{amount}", f"{amount:.2f}")
        .replace("{due_date}", due_date)
    )
    return send_sms(phone, message, "PAYMENT_REMINDER", sent_by, branch_id=branch_id)


def send_birthday_wish(phone, customer, discount, sent_by="system", branch_id=None):
    templates = load_sms_templates()
    template = templates.get("birthday", {}).get("template", "")
    message = template.replace("{customer}", customer).replace("{discount}", str(discount))
    return send_sms(phone, message, "BIRTHDAY", sent_by, branch_id=branch_id)


def send_2fa_code(phone, code, sent_by="system", branch_id=None):
    templates = load_sms_templates()
    template = templates.get("two_factor", {}).get("template", "")
    message = template.replace("{code}", code)
    return send_sms(phone, message, "2FA", sent_by, branch_id=branch_id)


# ==============================
# DASHBOARD
# ==============================
def sms_gateway_dashboard(branch_id=None):
    st.title("SMS Gateway Integration")
    st.caption("Send and manage SMS communications with customers")

    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can access SMS gateway.")
        return

    branch_id = _resolve_branch(branch_id)
    branch_label = _branch_label(branch_id)

    st.caption(
        f"Logged as sent by: **{branch_label}** "
        f"(the customer is the same business-wide)"
    )

    init_sms_files()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Send SMS",
        "Templates",
        "SMS Analytics",
        "SMS History",
        "Settings",
    ])

    # ==============================
    # TAB 1: SEND SMS
    # ==============================
    with tab1:
        st.markdown("## Send SMS")

        settings = load_sms_settings()

        if settings.get("test_mode", True):
            st.info("Test Mode is ENABLED — SMS will be simulated. Disable in Settings to send real SMS.")
        else:
            if settings.get("africastalking_api_key", ""):
                st.success("Live Mode — SMS will be sent to real numbers.")
                st.warning("Ensure you have credit in your Africa's Talking account.")
            else:
                st.warning("API Key not configured — go to Settings to add your API Key.")

        from backend.core.db_adapter import load_customers
        customers_df = load_customers(branch_id=branch_id)

        send_type = st.selectbox(
            "Message Type",
            [
                "Single Message",
                "Bulk Message",
                "Promotional Campaign",
                "Order Confirmation",
                "Delivery Notification",
                "Payment Reminder",
                "Birthday Wishes",
            ],
            key=f"sms_send_type_{branch_id}",
        )

        # ---------- Single ----------
        if send_type == "Single Message":
            st.markdown("### Send Single SMS")
            col1, col2 = st.columns(2)
            with col1:
                recipient = st.text_input(
                    "Recipient Phone", placeholder="0777123456",
                    key=f"sms_single_phone_{branch_id}",
                )
                st.caption("Enter Zimbabwe number without country code")
            with col2:
                sender_name = st.text_input(
                    "Sender ID", value=settings.get("sender_id", "AzielInvest"),
                    key=f"sms_single_sender_{branch_id}",
                )

            message = st.text_area(
                "Message", height=150, placeholder="Type your message here...",
                key=f"sms_single_msg_{branch_id}",
            )
            char_count = len(message)
            sms_count = (char_count // 160) + 1 if char_count > 0 else 0
            st.info(f"{char_count} characters | {sms_count} SMS segment(s)")

            if st.button("Send SMS", type="primary", use_container_width=True,
                         key=f"sms_single_send_{branch_id}"):
                if recipient and message:
                    with st.spinner("Sending SMS..."):
                        result = send_sms(
                            recipient, message, "SINGLE",
                            st.session_state.get("username", "system"),
                            branch_id=branch_id,
                        )
                        if result["success"]:
                            st.success(result["message"])
                            st.balloons()
                        else:
                            st.error(result["message"])
                else:
                    st.error("Please enter recipient and message")

        # ---------- Bulk ----------
        elif send_type == "Bulk Message":
            st.markdown("### Send Bulk SMS")
            upload_method = st.radio(
                "Recipient Selection",
                ["Select from Customers", "Manual Entry", "Upload CSV"],
                key=f"sms_bulk_method_{branch_id}",
            )

            recipients = []
            if upload_method == "Select from Customers":
                if not customers_df.empty:
                    name_col = next(
                        (c for c in ["customer_name", "name", "customer"] if c in customers_df.columns),
                        None,
                    )
                    phone_col = next(
                        (c for c in ["phone", "customer_phone", "contact"] if c in customers_df.columns),
                        None,
                    )
                    if name_col and phone_col:
                        selected = st.multiselect(
                            "Select Customers",
                            customers_df[name_col].tolist(),
                            format_func=lambda x: f"{x} - {customers_df[customers_df[name_col] == x][phone_col].iloc[0]}",
                            key=f"sms_bulk_select_{branch_id}",
                        )
                        recipients = customers_df[customers_df[name_col].isin(selected)][phone_col].tolist()
                        st.info(f"{len(recipients)} customers selected")
                    else:
                        st.warning("Customer table missing name or phone column")
                else:
                    st.warning(f"No customers found for {branch_label}")

            elif upload_method == "Manual Entry":
                manual_numbers = st.text_area(
                    "Enter Phone Numbers (one per line)",
                    placeholder="0777123456\n0777234567\n0777345678",
                    key=f"sms_bulk_manual_{branch_id}",
                )
                recipients = [n.strip() for n in manual_numbers.split("\n") if n.strip()]
                st.info(f"{len(recipients)} numbers entered")

            else:
                uploaded_file = st.file_uploader(
                    "Upload CSV with phone numbers", type=["csv"],
                    key=f"sms_bulk_upload_{branch_id}",
                )
                if uploaded_file:
                    df = pd.read_csv(uploaded_file)
                    if "phone" in df.columns:
                        recipients = df["phone"].tolist()
                        st.info(f"{len(recipients)} numbers loaded")
                    else:
                        st.error("CSV must have a 'phone' column")

            message = st.text_area(
                "Message", height=150, placeholder="Type your bulk message here...",
                key=f"sms_bulk_msg_{branch_id}",
            )

            if recipients and message:
                st.warning(f"This will send {len(recipients)} SMS messages")
                if st.button("Send Bulk SMS", type="primary", use_container_width=True,
                             key=f"sms_bulk_send_{branch_id}"):
                    with st.spinner("Sending bulk SMS..."):
                        result = send_bulk_sms(
                            recipients, message, "BULK",
                            st.session_state.get("username", "system"),
                            branch_id=branch_id,
                        )
                        st.success(f"Sent {result['success_count']}/{result['total']} messages")
                        if result["failed_count"] > 0:
                            st.warning(f"{result['failed_count']} messages failed")
                        st.balloons()

        # ---------- Promotional ----------
        elif send_type == "Promotional Campaign":
            st.markdown("### Promotional Campaign")
            offer = st.text_input(
                "Offer Description", placeholder="20% off all products",
                key=f"sms_promo_offer_{branch_id}",
            )
            expiry = st.date_input(
                "Offer Expiry", value=datetime.now() + timedelta(days=7),
                key=f"sms_promo_expiry_{branch_id}",
            )
            if not customers_df.empty:
                name_col = next(
                    (c for c in ["customer_name", "name", "customer"] if c in customers_df.columns),
                    None,
                )
                phone_col = next(
                    (c for c in ["phone", "customer_phone", "contact"] if c in customers_df.columns),
                    None,
                )
                if name_col and phone_col:
                    targets = st.multiselect(
                        "Select Target Customers",
                        customers_df[name_col].tolist(),
                        key=f"sms_promo_targets_{branch_id}",
                    )
                    recipient_phones = customers_df[customers_df[name_col].isin(targets)][phone_col].tolist()
                    if targets:
                        st.info(f"Sending to {len(targets)} customers")
                        if st.button("Send Campaign", type="primary",
                                     use_container_width=True,
                                     key=f"sms_promo_send_{branch_id}"):
                            with st.spinner("Sending campaign..."):
                                result = send_promotional_sms(
                                    recipient_phones, offer,
                                    expiry.strftime("%Y-%m-%d"),
                                    st.session_state.get("username", "system"),
                                    branch_id=branch_id,
                                )
                                st.success(f"Campaign sent to {result['success_count']} customers")
                                st.balloons()
                else:
                    st.warning("Customer table missing name or phone column")
            else:
                st.warning(f"No customers found for {branch_label}")

        # ---------- Order Confirmation ----------
        elif send_type == "Order Confirmation":
            st.markdown("### Order Confirmation")
            col1, col2 = st.columns(2)
            with col1:
                order_id = st.text_input("Order ID", placeholder="ORD-001",
                                         key=f"sms_oc_id_{branch_id}")
            with col2:
                total = st.number_input("Order Total ($)", min_value=0.0, value=0.0,
                                        key=f"sms_oc_total_{branch_id}")
            if not customers_df.empty:
                name_col = next(
                    (c for c in ["customer_name", "name", "customer"] if c in customers_df.columns),
                    None,
                )
                phone_col = next(
                    (c for c in ["phone", "customer_phone", "contact"] if c in customers_df.columns),
                    None,
                )
                if name_col and phone_col:
                    customer = st.selectbox("Select Customer", customers_df[name_col].tolist(),
                                            key=f"sms_oc_cust_{branch_id}")
                    customer_phone = customers_df[customers_df[name_col] == customer][phone_col].iloc[0]
                    if st.button("Send Confirmation", type="primary",
                                 use_container_width=True,
                                 key=f"sms_oc_send_{branch_id}"):
                        with st.spinner("Sending confirmation..."):
                            result = send_order_confirmation(
                                customer_phone, order_id, total,
                                st.session_state.get("username", "system"),
                                branch_id=branch_id,
                            )
                            if result["success"]:
                                st.success("Order confirmation sent!")
                                st.balloons()
                            else:
                                st.error(f"{result['message']}")

        # ---------- Delivery Notification ----------
        elif send_type == "Delivery Notification":
            st.markdown("### Delivery Notification")
            col1, col2 = st.columns(2)
            with col1:
                order_id = st.text_input("Order ID", placeholder="ORD-001",
                                         key=f"sms_dn_id_{branch_id}")
            with col2:
                st.date_input("Delivery Date", value=datetime.now(),
                              key=f"sms_dn_date_{branch_id}")
            if not customers_df.empty:
                name_col = next(
                    (c for c in ["customer_name", "name", "customer"] if c in customers_df.columns),
                    None,
                )
                phone_col = next(
                    (c for c in ["phone", "customer_phone", "contact"] if c in customers_df.columns),
                    None,
                )
                if name_col and phone_col:
                    customer = st.selectbox("Select Customer", customers_df[name_col].tolist(),
                                            key=f"sms_dn_cust_{branch_id}")
                    customer_phone = customers_df[customers_df[name_col] == customer][phone_col].iloc[0]
                    if st.button("Send Delivery Notification", type="primary",
                                 use_container_width=True,
                                 key=f"sms_dn_send_{branch_id}"):
                        with st.spinner("Sending notification..."):
                            result = send_delivery_notification(
                                customer_phone, order_id,
                                st.session_state.get("username", "system"),
                                branch_id=branch_id,
                            )
                            if result["success"]:
                                st.success("Delivery notification sent!")
                                st.balloons()
                            else:
                                st.error(f"{result['message']}")

        # ---------- Payment Reminder ----------
        elif send_type == "Payment Reminder":
            st.markdown("### Payment Reminder")
            col1, col2 = st.columns(2)
            with col1:
                customer_name = st.text_input("Customer Name", key=f"sms_pr_name_{branch_id}")
                amount = st.number_input("Amount Due ($)", min_value=0.0, value=0.0,
                                         key=f"sms_pr_amount_{branch_id}")
            with col2:
                due_date = st.date_input("Due Date", value=datetime.now() + timedelta(days=7),
                                         key=f"sms_pr_due_{branch_id}")
                customer_phone = st.text_input("Customer Phone", placeholder="0777123456",
                                               key=f"sms_pr_phone_{branch_id}")
            if st.button("Send Reminder", type="primary", use_container_width=True,
                         key=f"sms_pr_send_{branch_id}"):
                if customer_name and customer_phone and amount > 0:
                    with st.spinner("Sending reminder..."):
                        result = send_payment_reminder(
                            customer_phone, customer_name, amount,
                            due_date.strftime("%Y-%m-%d"),
                            st.session_state.get("username", "system"),
                            branch_id=branch_id,
                        )
                        if result["success"]:
                            st.success("Payment reminder sent!")
                            st.balloons()
                        else:
                            st.error(f"{result['message']}")
                else:
                    st.error("Please fill all required fields")

        # ---------- Birthday Wishes ----------
        elif send_type == "Birthday Wishes":
            st.markdown("### Birthday Wishes")
            if not customers_df.empty:
                name_col = next(
                    (c for c in ["customer_name", "name", "customer"] if c in customers_df.columns),
                    None,
                )
                phone_col = next(
                    (c for c in ["phone", "customer_phone", "contact"] if c in customers_df.columns),
                    None,
                )
                if name_col and phone_col:
                    customer = st.selectbox("Select Customer", customers_df[name_col].tolist(),
                                            key=f"sms_bd_cust_{branch_id}")
                    customer_phone = customers_df[customers_df[name_col] == customer][phone_col].iloc[0]
                    discount = st.number_input("Discount (%)", min_value=0, max_value=100, value=10,
                                               key=f"sms_bd_disc_{branch_id}")
                    if st.button("Send Birthday Wish", type="primary",
                                 use_container_width=True,
                                 key=f"sms_bd_send_{branch_id}"):
                        with st.spinner("Sending birthday wish..."):
                            result = send_birthday_wish(
                                customer_phone, customer, discount,
                                st.session_state.get("username", "system"),
                                branch_id=branch_id,
                            )
                            if result["success"]:
                                st.success("Birthday wish sent!")
                                st.balloons()
                            else:
                                st.error(f"{result['message']}")

    # ==============================
    # TAB 2: TEMPLATES (global — shared vocabulary)
    # ==============================
    with tab2:
        st.markdown("## SMS Templates")
        templates = load_sms_templates()

        with st.expander("Add New Template"):
            template_name = st.text_input("Template Name", key=f"sms_tpl_name_{branch_id}")
            template_category = st.selectbox(
                "Category",
                ["Customer Onboarding", "Sales", "Logistics", "Finance",
                 "Marketing", "Customer Engagement", "Security", "Other"],
                key=f"sms_tpl_cat_{branch_id}",
            )
            template_content = st.text_area(
                "Template Content", height=100,
                placeholder="Use {variables} for dynamic content",
                key=f"sms_tpl_content_{branch_id}",
            )
            if st.button("Save Template", type="primary", key=f"sms_tpl_save_{branch_id}"):
                if template_name and template_content:
                    templates[template_name.lower().replace(" ", "_")] = {
                        "name": template_name,
                        "template": template_content,
                        "category": template_category,
                    }
                    save_sms_templates(templates)
                    st.success(f"Template '{template_name}' saved!")
                    show_toast(f"Template '{template_name}' saved!", "success")
                    st.rerun()
                else:
                    st.error("Please enter template name and content")

        st.markdown("### Available Templates")
        if templates:
            for key, template in templates.items():
                with st.expander(f"{template.get('name', key)} - {template.get('category', 'Uncategorized')}"):
                    st.code(template.get("template", ""), language="text")
                    st.caption(f"Template ID: {key}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Edit", key=f"sms_tpl_edit_{branch_id}_{key}"):
                            st.session_state.edit_template = key
                    with col2:
                        if st.button("Delete", key=f"sms_tpl_del_{branch_id}_{key}"):
                            del templates[key]
                            save_sms_templates(templates)
                            show_toast("Template deleted!", "info")
                            st.rerun()
        else:
            st.info("No templates found")

    # ==============================
    # TAB 3: ANALYTICS (branch-scoped)
    # ==============================
    with tab3:
        st.markdown("## SMS Analytics")
        st.caption(f"Scope: {branch_label}")

        logs_df = load_sms_logs(branch_id=branch_id)

        if not logs_df.empty:
            logs_df = logs_df.copy()
            logs_df["sent_date"] = pd.to_datetime(logs_df["sent_date"], errors="coerce")

            total_sent = len(logs_df)
            total_success = len(logs_df[logs_df["status"] == "SENT"])
            total_failed = len(logs_df[logs_df["status"] == "FAILED"])
            total_cost = pd.to_numeric(logs_df["cost"], errors="coerce").fillna(0).sum()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Sent", total_sent)
            with col2:
                st.metric(
                    "Successful", total_success,
                    delta=f"{total_success/total_sent*100:.1f}%" if total_sent > 0 else "0%",
                )
            with col3:
                st.metric("Failed", total_failed)
            with col4:
                st.metric("Total Cost", f"${total_cost:.2f}")

            st.markdown("### SMS Activity")
            daily_sms = (
                logs_df.dropna(subset=["sent_date"])
                .groupby(logs_df["sent_date"].dt.date)
                .size()
                .reset_index()
            )
            if not daily_sms.empty:
                daily_sms.columns = ["Date", "Count"]
                st.bar_chart(daily_sms.set_index("Date"))

            st.markdown("### SMS by Type")
            sms_by_type = logs_df["type"].value_counts().reset_index()
            sms_by_type.columns = ["Type", "Count"]
            st.dataframe(sms_by_type, use_container_width=True, hide_index=True)
        else:
            st.info(f"No SMS data available for {branch_label}")

    # ==============================
    # TAB 4: HISTORY (scoped, owner can widen)
    # ==============================
    with tab4:
        st.markdown("## SMS History")

        role = st.session_state.get("role", "cashier")
        is_owner = role in ("owner", "admin")

        # Owners get a scope selector; everyone else sees only their branch.
        if is_owner:
            try:
                bdf = load_branches()
            except Exception:
                bdf = pd.DataFrame()

            if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
                options = ["All Branches"] + [
                    f"{r['branch_name']} ({r['branch_id']})"
                    for _, r in bdf.iterrows()
                ]
                choice = st.selectbox(
                    "Branch filter", options, key=f"sms_hist_scope_{branch_id}",
                    help="Owners can view any branch's outbound SMS.",
                )
                if choice == "All Branches":
                    hist_branch = ALL_BRANCHES
                    hist_label = "All Branches"
                else:
                    m = re.search(r"\(([^)]+)\)\s*$", choice)
                    hist_branch = m.group(1).strip() if m else choice
                    hist_label = choice
            else:
                hist_branch = branch_id
                hist_label = branch_label
        else:
            hist_branch = branch_id
            hist_label = branch_label
            st.info(f"Showing only your branch's outbound SMS: **{hist_label}**")

        logs_df = load_sms_logs(branch_id=hist_branch)

        if not logs_df.empty:
            logs_df = logs_df.copy()
            logs_df["sent_date"] = pd.to_datetime(logs_df["sent_date"], errors="coerce")

            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox(
                    "Status", ["All", "SENT", "FAILED"],
                    key=f"sms_hist_status_{branch_id}",
                )
            with col2:
                type_options = ["All"] + sorted(logs_df["type"].dropna().unique().tolist())
                type_filter = st.selectbox(
                    "Type", type_options,
                    key=f"sms_hist_type_{branch_id}",
                )
            with col3:
                date_filter = st.date_input(
                    "Date", value=None,
                    key=f"sms_hist_date_{branch_id}",
                )

            filtered_df = logs_df.copy()
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df["status"] == status_filter]
            if type_filter != "All":
                filtered_df = filtered_df[filtered_df["type"] == type_filter]
            if date_filter:
                filtered_df = filtered_df[
                    filtered_df["sent_date"].dt.date == date_filter
                ]

            display_cols = [
                c for c in [
                    "sent_date", "branch_id", "recipient",
                    "message", "type", "status", "cost",
                ] if c in filtered_df.columns
            ]
            display_df = filtered_df[display_cols].copy()
            if "sent_date" in display_df.columns:
                display_df["sent_date"] = display_df["sent_date"].dt.strftime("%Y-%m-%d %H:%M")
            if "message" in display_df.columns:
                display_df["message"] = display_df["message"].astype(str).str[:100] + "..."

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                    "branch_id": "Branch",
                },
            )

            csv = filtered_df.to_csv(index=False).encode("utf-8")
            safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", str(hist_label)).strip("_") or "sms"
            st.download_button(
                label=f"Export SMS Logs (CSV) — {hist_label}",
                data=csv,
                file_name=f"sms_logs_{safe_label}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info(f"No SMS history found for {hist_label}")

    # ==============================
    # TAB 5: SETTINGS (global)
    # ==============================
    with tab5:
        st.markdown("## SMS Gateway Settings")
        st.caption("Provider credentials and sender identity are shared company-wide.")

        settings = load_sms_settings()

        st.markdown("### Africa's Talking Setup")
        st.info(
            "1. Go to https://account.africastalking.com/\n"
            "2. Settings -> API Key\n"
            "3. Copy your API Key (starts with 'atsk_')\n"
            "4. Paste it below and click Save"
        )

        col1, col2 = st.columns(2)
        with col1:
            enabled = st.checkbox(
                "Enable SMS Service", value=settings.get("enabled", True),
                key=f"sms_set_enabled_{branch_id}",
            )
            test_mode = st.checkbox(
                "Test Mode (no actual SMS sent)", value=settings.get("test_mode", True),
                key=f"sms_set_test_{branch_id}",
            )
            if test_mode:
                st.info("Test Mode: SMS are simulated")
            else:
                st.warning("Live Mode: SMS will be sent to real numbers")
                st.warning("Ensure you have credit in your Africa's Talking account.")

        with col2:
            sender_id = st.text_input(
                "Sender ID", value=settings.get("sender_id", "AzielInvest"),
                help="Max 11 characters",
                key=f"sms_set_sender_{branch_id}",
            )
            default_country = st.text_input(
                "Default Country Code", value=settings.get("default_country_code", "263"),
                key=f"sms_set_country_{branch_id}",
            )

        st.markdown("---")
        st.markdown("### Africa's Talking Credentials")

        current_api_key = settings.get("africastalking_api_key", "")
        if current_api_key:
            st.success(f"API Key is configured (length: {len(current_api_key)} characters)")
        else:
            st.warning("API Key not configured")

        api_key = st.text_input(
            "API Key", type="password", value=current_api_key,
            key=f"sms_set_api_{branch_id}",
        )
        username = st.text_input(
            "Username", value=settings.get("africastalking_username", "sandbox"),
            key=f"sms_set_user_{branch_id}",
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("Save Settings", type="primary", use_container_width=True,
                         key=f"sms_set_save_{branch_id}"):
                settings.update({
                    "enabled": enabled,
                    "test_mode": test_mode,
                    "sender_id": sender_id,
                    "default_country_code": default_country,
                    "africastalking_api_key": api_key,
                    "africastalking_username": username,
                })
                save_sms_settings(settings)
                st.success("Settings saved successfully!")
                show_toast("SMS settings updated!", "success")

        with col2:
            if st.button("Test Connection", use_container_width=True,
                         key=f"sms_set_test_conn_{branch_id}"):
                if api_key:
                    st.success(f"API Key validated! (Length: {len(api_key)} characters)")
                    st.info("To test actual SMS:\n1. Disable Test Mode\n2. Send a message")
                else:
                    st.error("Please enter your API Key")

        with col3:
            if st.button("Diagnostic Test", use_container_width=True,
                         key=f"sms_set_diag_{branch_id}"):
                if api_key:
                    with st.spinner("Testing API connection..."):
                        result = test_africastalking_connection(api_key, username)
                        if result.get("status_code") == 200:
                            st.success("API Key is valid and working!")
                        elif result.get("status_code") == 401:
                            st.error(
                                "Authentication failed - Invalid API Key or username\n\n"
                                "Please check:\n1. Your API Key is correct\n2. Your username is 'sandbox'"
                            )
                        else:
                            st.warning(f"Response: {result}")
                else:
                    st.error("Please enter your API Key")

        st.markdown("---")
        st.markdown("### Current Configuration")

        config_data = {
            "Provider": settings.get("provider", "africastalking"),
            "Sender ID": settings.get("sender_id", "Not set"),
            "Test Mode": "Enabled" if settings.get("test_mode", True) else "Disabled",
            "Service Status": "Enabled" if settings.get("enabled", True) else "Disabled",
            "API Key": "Configured" if settings.get("africastalking_api_key", "") else "Not Configured",
            "Username": settings.get("africastalking_username", "Not set"),
        }
        for key, value in config_data.items():
            st.write(f"**{key}:** {value}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    sms_gateway_dashboard()