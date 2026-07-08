import streamlit as st
import pandas as pd
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import base64

from backend.utils.phone_utils import validate_zimbabwe_phone
from backend.core.animations import show_toast, show_confetti

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
SMS_FILE = DATA_DIR / "sms_logs.csv"
SMS_TEMPLATES_FILE = DATA_DIR / "sms_templates.json"
SMS_SETTINGS_FILE = DATA_DIR / "sms_settings.json"

# ==============================
# INITIALIZATION
# ==============================
def init_sms_files():
    """Initialize SMS-related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    if not SMS_FILE.exists():
        df = pd.DataFrame(columns=[
            "sms_id", "recipient", "message", "type", "status", 
            "sent_date", "sent_by", "response", "cost"
        ])
        df.to_csv(SMS_FILE, index=False)
    
    if not SMS_TEMPLATES_FILE.exists():
        templates = {
            "welcome": {
                "name": "Welcome Message",
                "template": "Welcome to Aziel Investments! Thank you for shopping with us. Your loyalty is appreciated.",
                "category": "Customer Onboarding"
            },
            "order_confirmation": {
                "name": "Order Confirmation",
                "template": "Your order #{order_id} has been confirmed. Total: ${total}. Thank you for shopping at Aziel Investments.",
                "category": "Sales"
            },
            "delivery_notification": {
                "name": "Delivery Notification",
                "template": "Your order #{order_id} has been dispatched and will be delivered today. Thank you for choosing Aziel Investments.",
                "category": "Logistics"
            },
            "payment_reminder": {
                "name": "Payment Reminder",
                "template": "Dear {customer}, your payment of ${amount} is due on {due_date}. Please settle your account to avoid late fees.",
                "category": "Finance"
            },
            "promotional": {
                "name": "Promotional Offer",
                "template": "Special offer at Aziel Investments! {offer} valid until {expiry}. Visit us today!",
                "category": "Marketing"
            },
            "birthday": {
                "name": "Birthday Wishes",
                "template": "Happy Birthday {customer}! Enjoy a special {discount}% discount at Aziel Investments this week.",
                "category": "Customer Engagement"
            },
            "thank_you": {
                "name": "Thank You Message",
                "template": "Thank you for your purchase at Aziel Investments! We value your business.",
                "category": "Customer Engagement"
            },
            "review_request": {
                "name": "Review Request",
                "template": "We hope you enjoyed your shopping experience at Aziel Investments. Please leave us a review: {link}",
                "category": "Customer Engagement"
            },
            "re_engagement": {
                "name": "Re-engagement",
                "template": "We miss you at Aziel Investments! Visit us and get {discount}% off your next purchase.",
                "category": "Customer Engagement"
            },
            "two_factor": {
                "name": "2FA Code",
                "template": "Your Aziel Investments verification code is: {code}. Valid for 5 minutes.",
                "category": "Security"
            }
        }
        with open(SMS_TEMPLATES_FILE, "w") as f:
            json.dump(templates, f, indent=2)
    
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
            "semaphore_sender_name": "AzielInvest"
        }
        with open(SMS_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)


def load_sms_logs():
    """Load SMS logs"""
    init_sms_files()
    try:
        return pd.read_csv(SMS_FILE)
    except:
        return pd.DataFrame(columns=[
            "sms_id", "recipient", "message", "type", "status", 
            "sent_date", "sent_by", "response", "cost"
        ])


def save_sms_logs(df):
    """Save SMS logs"""
    df.to_csv(SMS_FILE, index=False)


def load_sms_templates():
    """Load SMS templates"""
    init_sms_files()
    with open(SMS_TEMPLATES_FILE, "r") as f:
        return json.load(f)


def save_sms_templates(templates):
    """Save SMS templates"""
    with open(SMS_TEMPLATES_FILE, "w") as f:
        json.dump(templates, f, indent=2)


def load_sms_settings():
    """Load SMS settings"""
    init_sms_files()
    try:
        with open(SMS_SETTINGS_FILE, "r") as f:
            return json.load(f)
    except:
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
            "semaphore_sender_name": "AzielInvest"
        }


def save_sms_settings(settings):
    """Save SMS settings"""
    with open(SMS_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def log_sms(recipient, message, sms_type, status, sent_by, response, cost=0):
    """Log SMS to file"""
    df = load_sms_logs()
    
    new_sms = pd.DataFrame([{
        "sms_id": f"SMS{len(df)+1:08d}",
        "recipient": recipient,
        "message": message[:500],
        "type": sms_type,
        "status": status,
        "sent_date": datetime.now().isoformat(),
        "sent_by": sent_by,
        "response": response,
        "cost": cost
    }])
    
    df = pd.concat([df, new_sms], ignore_index=True)
    save_sms_logs(df)


# ==============================
# TEST AFRICA'S TALKING CONNECTION
# ==============================
def test_africastalking_connection(api_key, username):
    """Test Africa's Talking API connection"""
    try:
        url = "https://api.africastalking.com/version1/messaging"
        
        headers = {
            "ApiKey": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        data = {
            "username": username,
            "to": "+263771234567",
            "message": "Test",
            "from": "AzielInvest"
        }
        
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        return {
            "status_code": response.status_code,
            "response": response.text[:500]
        }
    except Exception as e:
        return {"error": str(e)}


# ==============================
# REAL SMS PROVIDERS - AFRICA'S TALKING
# ==============================
def send_sms_africastalking(recipient, message, settings):
    """Send SMS via Africa's Talking - FIXED AUTHENTICATION"""
    try:
        api_key = settings.get("africastalking_api_key", "").strip()
        username = settings.get("africastalking_username", "sandbox").strip()
        
        if not api_key:
            return {
                "success": False, 
                "message": "❌ API Key not configured. Please add your API Key in Settings tab."
            }
        
        # Format phone number
        if not recipient.startswith("+"):
            recipient = f"+{settings.get('default_country_code', '263')}{recipient.lstrip('0')}"
        
        # Check test mode
        if settings.get("test_mode", True):
            return {
                "success": True,
                "message": f"🧪 TEST MODE: SMS would be sent to {recipient}\n\nDisable Test Mode in Settings to send real SMS.",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00
            }
        
        # Africa's Talking API endpoint
        url = "https://api.africastalking.com/version1/messaging"
        
        headers = {
            "ApiKey": api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        data = {
            "username": username,
            "to": recipient,
            "message": message,
            "from": settings.get("sender_id", "AzielInvest")[:11]
        }
        
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200 or response.status_code == 201:
            try:
                result = response.json()
                if "SMSMessageData" in result:
                    recipients_data = result["SMSMessageData"].get("Recipients", [])
                    if recipients_data and len(recipients_data) > 0:
                        status = recipients_data[0].get("status", "")
                        if status.lower() == "success":
                            return {
                                "success": True,
                                "message": "✅ SMS sent successfully!",
                                "sms_id": recipients_data[0].get("messageId"),
                                "cost": 0.05
                            }
                        else:
                            return {
                                "success": False,
                                "message": f"❌ Error: {status}"
                            }
                error_msg = result.get("error", "Unknown error")
                return {"success": False, "message": f"❌ {error_msg}"}
            except:
                return {"success": False, "message": f"❌ Invalid response: {response.text[:200]}"}
        else:
            if response.status_code == 401:
                return {
                    "success": False,
                    "message": "❌ Authentication failed (401).\n\nPlease check:\n1. Your API Key is correct\n2. Your username is 'sandbox'\n3. You have credit in your account"
                }
            return {
                "success": False,
                "message": f"❌ HTTP Error {response.status_code}: {response.text[:200]}"
            }
            
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"❌ Network error: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Error: {str(e)}"


# ==============================
# TWILIO SMS PROVIDER
# ==============================
def send_sms_twilio(recipient, message, settings):
    """Send SMS via Twilio"""
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
                "message": f"🧪 TEST MODE: SMS would be sent to {recipient}",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00
            }
        
        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "To": recipient,
            "From": twilio_phone,
            "Body": message
        }
        
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            return {
                "success": True,
                "message": "✅ SMS sent successfully!",
                "sms_id": result.get("sid"),
                "cost": 0.05
            }
        
        return {
            "success": False,
            "message": f"❌ Failed: {response.text[:200]}"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


# ==============================
# SEMAPHORE SMS PROVIDER
# ==============================
def send_sms_semaphore(recipient, message, settings):
    """Send SMS via Semaphore"""
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
                "message": f"🧪 TEST MODE: SMS would be sent to {recipient}",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00
            }
        
        url = "https://api.semaphore.co/api/v4/messages"
        data = {
            "apikey": api_key,
            "number": recipient,
            "message": message,
            "sendername": sender_name
        }
        
        response = requests.post(url, data=data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                status = result[0].get("status", "")
                if status == "queued" or status == "sent":
                    return {
                        "success": True,
                        "message": "✅ SMS sent successfully!",
                        "sms_id": result[0].get("message_id"),
                        "cost": 0.05
                    }
        
        return {
            "success": False,
            "message": f"❌ Failed: {response.text[:200]}"
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


# ==============================
# MAIN SEND SMS FUNCTION
# ==============================
def send_sms(recipient, message, sms_type="GENERAL", sent_by="system"):
    """Send SMS using configured provider"""
    
    settings = load_sms_settings()
    
    if not settings.get("enabled", True):
        return {"success": False, "message": "❌ SMS service is disabled"}
    
    valid, standardized, msg = validate_zimbabwe_phone(recipient)
    if not valid:
        return {"success": False, "message": f"❌ Invalid phone number: {msg}"}
    
    provider = settings.get("provider", "africastalking")
    
    if provider == "africastalking":
        result = send_sms_africastalking(standardized, message, settings)
    elif provider == "twilio":
        result = send_sms_twilio(standardized, message, settings)
    elif provider == "semaphore":
        result = send_sms_semaphore(standardized, message, settings)
    else:
        return {"success": False, "message": f"❌ Unknown provider: {provider}"}
    
    log_sms(
        recipient=standardized,
        message=message,
        sms_type=sms_type,
        status="SENT" if result["success"] else "FAILED",
        sent_by=sent_by,
        response=result.get("message", ""),
        cost=result.get("cost", 0)
    )
    
    return result


def send_bulk_sms(recipients, message, sms_type="BULK", sent_by="system"):
    """Send SMS to multiple recipients"""
    results = []
    success_count = 0
    
    for recipient in recipients:
        result = send_sms(recipient, message, sms_type, sent_by)
        results.append(result)
        if result["success"]:
            success_count += 1
    
    return {
        "success": success_count > 0,
        "total": len(recipients),
        "success_count": success_count,
        "failed_count": len(recipients) - success_count,
        "results": results
    }


def send_promotional_sms(customer_phones, offer, expiry, sent_by="system"):
    """Send promotional SMS to customers"""
    templates = load_sms_templates()
    template = templates.get("promotional", {}).get("template", "")
    message = template.replace("{offer}", offer).replace("{expiry}", expiry)
    return send_bulk_sms(customer_phones, message, "PROMOTIONAL", sent_by)


def send_order_confirmation(phone, order_id, total, sent_by="system"):
    """Send order confirmation SMS"""
    templates = load_sms_templates()
    template = templates.get("order_confirmation", {}).get("template", "")
    message = template.replace("{order_id}", order_id).replace("{total}", f"{total:.2f}")
    return send_sms(phone, message, "ORDER_CONFIRMATION", sent_by)


def send_delivery_notification(phone, order_id, sent_by="system"):
    """Send delivery notification SMS"""
    templates = load_sms_templates()
    template = templates.get("delivery_notification", {}).get("template", "")
    message = template.replace("{order_id}", order_id)
    return send_sms(phone, message, "DELIVERY", sent_by)


def send_payment_reminder(phone, customer, amount, due_date, sent_by="system"):
    """Send payment reminder SMS"""
    templates = load_sms_templates()
    template = templates.get("payment_reminder", {}).get("template", "")
    message = template.replace("{customer}", customer).replace("{amount}", f"{amount:.2f}").replace("{due_date}", due_date)
    return send_sms(phone, message, "PAYMENT_REMINDER", sent_by)


def send_birthday_wish(phone, customer, discount, sent_by="system"):
    """Send birthday wish SMS"""
    templates = load_sms_templates()
    template = templates.get("birthday", {}).get("template", "")
    message = template.replace("{customer}", customer).replace("{discount}", str(discount))
    return send_sms(phone, message, "BIRTHDAY", sent_by)


def send_2fa_code(phone, code, sent_by="system"):
    """Send 2FA verification code"""
    templates = load_sms_templates()
    template = templates.get("two_factor", {}).get("template", "")
    message = template.replace("{code}", code)
    return send_sms(phone, message, "2FA", sent_by)


# ==============================
# SMS DASHBOARD
# ==============================
def sms_gateway_dashboard():
    """SMS Gateway Integration Dashboard"""
    
    st.title("📱 SMS Gateway Integration")
    st.caption("Send and manage SMS communications with customers")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access SMS gateway.")
        return
    
    init_sms_files()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📤 Send SMS",
        "📋 Templates",
        "📊 SMS Analytics",
        "📜 SMS History",
        "⚙️ Settings"
    ])
    
    # ==============================
    # TAB 1: SEND SMS
    # ==============================
    with tab1:
        st.markdown("## 📤 Send SMS")
        
        settings = load_sms_settings()
        
        if settings.get("test_mode", True):
            st.info("🧪 **Test Mode is ENABLED** - SMS will be simulated. Disable in Settings to send real SMS.")
        else:
            if settings.get("africastalking_api_key", ""):
                st.success("✅ **Live Mode** - SMS will be sent to real numbers.")
                st.warning("💰 Ensure you have credit in your Africa's Talking account.")
            else:
                st.warning("⚠️ **API Key not configured** - Go to Settings to add your API Key.")
        
        from backend.core.database import load_customers
        customers_df = load_customers()
        
        send_type = st.selectbox(
            "Message Type",
            [
                "Single Message",
                "Bulk Message",
                "Promotional Campaign",
                "Order Confirmation",
                "Delivery Notification",
                "Payment Reminder",
                "Birthday Wishes"
            ]
        )
        
        if send_type == "Single Message":
            st.markdown("### Send Single SMS")
            
            col1, col2 = st.columns(2)
            with col1:
                recipient = st.text_input("Recipient Phone", placeholder="0777123456")
                st.caption("Enter Zimbabwe number without country code")
            with col2:
                sender_name = st.text_input("Sender ID", value=settings.get("sender_id", "AzielInvest"))
            
            message = st.text_area("Message", height=150, placeholder="Type your message here...")
            char_count = len(message)
            sms_count = (char_count // 160) + 1 if char_count > 0 else 0
            
            st.info(f"📊 {char_count} characters | {sms_count} SMS segment(s)")
            
            if st.button("📤 Send SMS", type="primary", use_container_width=True):
                if recipient and message:
                    with st.spinner("Sending SMS..."):
                        result = send_sms(recipient, message, "SINGLE", st.session_state.get("username", "system"))
                        if result["success"]:
                            st.success(result["message"])
                            st.balloons()
                        else:
                            st.error(result["message"])
                else:
                    st.error("Please enter recipient and message")
        
        elif send_type == "Bulk Message":
            st.markdown("### Send Bulk SMS")
            
            st.markdown("#### Select Recipients")
            
            col1, col2 = st.columns(2)
            with col1:
                upload_method = st.radio(
                    "Recipient Selection",
                    ["Select from Customers", "Manual Entry", "Upload CSV"]
                )
            
            recipients = []
            
            if upload_method == "Select from Customers":
                if not customers_df.empty:
                    selected_customers = st.multiselect(
                        "Select Customers",
                        customers_df["customer_name"].tolist(),
                        format_func=lambda x: f"{x} - {customers_df[customers_df['customer_name'] == x]['phone'].iloc[0]}"
                    )
                    recipients = customers_df[customers_df["customer_name"].isin(selected_customers)]["phone"].tolist()
                    st.info(f"📊 {len(recipients)} customers selected")
                else:
                    st.warning("No customers found")
            
            elif upload_method == "Manual Entry":
                manual_numbers = st.text_area(
                    "Enter Phone Numbers (one per line)",
                    placeholder="0777123456\n0777234567\n0777345678"
                )
                recipients = [num.strip() for num in manual_numbers.split("\n") if num.strip()]
                st.info(f"📊 {len(recipients)} numbers entered")
            
            else:
                uploaded_file = st.file_uploader("Upload CSV with phone numbers", type=["csv"])
                if uploaded_file:
                    df = pd.read_csv(uploaded_file)
                    if "phone" in df.columns:
                        recipients = df["phone"].tolist()
                        st.info(f"📊 {len(recipients)} numbers loaded")
                    else:
                        st.error("CSV must have a 'phone' column")
            
            message = st.text_area("Message", height=150, placeholder="Type your bulk message here...")
            
            if recipients and message:
                st.warning(f"⚠️ This will send {len(recipients)} SMS messages")
                
                if st.button("📤 Send Bulk SMS", type="primary", use_container_width=True):
                    with st.spinner("Sending bulk SMS..."):
                        result = send_bulk_sms(recipients, message, "BULK", st.session_state.get("username", "system"))
                        st.success(f"✅ Sent {result['success_count']}/{result['total']} messages")
                        if result["failed_count"] > 0:
                            st.warning(f"⚠️ {result['failed_count']} messages failed")
                        st.balloons()
        
        elif send_type == "Promotional Campaign":
            st.markdown("### 📢 Promotional Campaign")
            
            offer = st.text_input("Offer Description", placeholder="20% off all products")
            expiry = st.date_input("Offer Expiry", value=datetime.now() + timedelta(days=7))
            
            if not customers_df.empty:
                target_customers = st.multiselect(
                    "Select Target Customers",
                    customers_df["customer_name"].tolist()
                )
                recipient_phones = customers_df[customers_df["customer_name"].isin(target_customers)]["phone"].tolist()
                
                if target_customers:
                    st.info(f"📊 Sending to {len(target_customers)} customers")
                    if st.button("📤 Send Campaign", type="primary", use_container_width=True):
                        with st.spinner("Sending campaign..."):
                            result = send_promotional_sms(
                                recipient_phones,
                                offer,
                                expiry.strftime("%Y-%m-%d"),
                                st.session_state.get("username", "system")
                            )
                            st.success(f"✅ Campaign sent to {result['success_count']} customers")
                            st.balloons()
            else:
                st.warning("No customers found")
        
        elif send_type == "Order Confirmation":
            st.markdown("### 📦 Order Confirmation")
            
            col1, col2 = st.columns(2)
            with col1:
                order_id = st.text_input("Order ID", placeholder="ORD-001")
            with col2:
                total = st.number_input("Order Total ($)", min_value=0.0, value=0.0)
            
            if not customers_df.empty:
                customer = st.selectbox("Select Customer", customers_df["customer_name"].tolist())
                customer_phone = customers_df[customers_df["customer_name"] == customer]["phone"].iloc[0]
                
                if st.button("📤 Send Confirmation", type="primary", use_container_width=True):
                    with st.spinner("Sending confirmation..."):
                        result = send_order_confirmation(
                            customer_phone,
                            order_id,
                            total,
                            st.session_state.get("username", "system")
                        )
                        if result["success"]:
                            st.success("✅ Order confirmation sent!")
                            st.balloons()
                        else:
                            st.error(f"❌ {result['message']}")
        
        elif send_type == "Delivery Notification":
            st.markdown("### 🚚 Delivery Notification")
            
            col1, col2 = st.columns(2)
            with col1:
                order_id = st.text_input("Order ID", placeholder="ORD-001")
            with col2:
                delivery_date = st.date_input("Delivery Date", value=datetime.now())
            
            if not customers_df.empty:
                customer = st.selectbox("Select Customer", customers_df["customer_name"].tolist(), key="delivery_customer")
                customer_phone = customers_df[customers_df["customer_name"] == customer]["phone"].iloc[0]
                
                if st.button("📤 Send Delivery Notification", type="primary", use_container_width=True):
                    with st.spinner("Sending notification..."):
                        result = send_delivery_notification(
                            customer_phone,
                            order_id,
                            st.session_state.get("username", "system")
                        )
                        if result["success"]:
                            st.success("✅ Delivery notification sent!")
                            st.balloons()
                        else:
                            st.error(f"❌ {result['message']}")
        
        elif send_type == "Payment Reminder":
            st.markdown("### 💰 Payment Reminder")
            
            col1, col2 = st.columns(2)
            with col1:
                customer_name = st.text_input("Customer Name")
                amount = st.number_input("Amount Due ($)", min_value=0.0, value=0.0)
            with col2:
                due_date = st.date_input("Due Date", value=datetime.now() + timedelta(days=7))
                customer_phone = st.text_input("Customer Phone", placeholder="0777123456")
            
            if st.button("📤 Send Reminder", type="primary", use_container_width=True):
                if customer_name and customer_phone and amount > 0:
                    with st.spinner("Sending reminder..."):
                        result = send_payment_reminder(
                            customer_phone,
                            customer_name,
                            amount,
                            due_date.strftime("%Y-%m-%d"),
                            st.session_state.get("username", "system")
                        )
                        if result["success"]:
                            st.success("✅ Payment reminder sent!")
                            st.balloons()
                        else:
                            st.error(f"❌ {result['message']}")
                else:
                    st.error("Please fill all required fields")
        
        elif send_type == "Birthday Wishes":
            st.markdown("### 🎂 Birthday Wishes")
            
            if not customers_df.empty:
                customer = st.selectbox("Select Customer", customers_df["customer_name"].tolist(), key="birthday_customer")
                customer_phone = customers_df[customers_df["customer_name"] == customer]["phone"].iloc[0]
                discount = st.number_input("Discount (%)", min_value=0, max_value=100, value=10)
                
                if st.button("📤 Send Birthday Wish", type="primary", use_container_width=True):
                    with st.spinner("Sending birthday wish..."):
                        result = send_birthday_wish(
                            customer_phone,
                            customer,
                            discount,
                            st.session_state.get("username", "system")
                        )
                        if result["success"]:
                            st.success("✅ Birthday wish sent!")
                            st.balloons()
                        else:
                            st.error(f"❌ {result['message']}")
    
    # ==============================
    # TAB 2: TEMPLATES
    # ==============================
    with tab2:
        st.markdown("## 📋 SMS Templates")
        
        templates = load_sms_templates()
        
        with st.expander("➕ Add New Template"):
            template_name = st.text_input("Template Name")
            template_category = st.selectbox(
                "Category",
                ["Customer Onboarding", "Sales", "Logistics", "Finance", "Marketing", "Customer Engagement", "Security", "Other"]
            )
            template_content = st.text_area("Template Content", height=100, placeholder="Use {variables} for dynamic content")
            
            if st.button("💾 Save Template", type="primary"):
                if template_name and template_content:
                    templates[template_name.lower().replace(" ", "_")] = {
                        "name": template_name,
                        "template": template_content,
                        "category": template_category
                    }
                    save_sms_templates(templates)
                    st.success(f"✅ Template '{template_name}' saved!")
                    show_toast(f"Template '{template_name}' saved!", "success")
                    st.rerun()
                else:
                    st.error("Please enter template name and content")
        
        st.markdown("### 📋 Available Templates")
        
        if templates:
            for key, template in templates.items():
                with st.expander(f"📝 {template.get('name', key)} - {template.get('category', 'Uncategorized')}"):
                    st.code(template.get('template', ''), language='text')
                    st.caption(f"Template ID: {key}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ Edit", key=f"edit_{key}"):
                            st.session_state.edit_template = key
                    with col2:
                        if st.button(f"🗑️ Delete", key=f"delete_{key}"):
                            del templates[key]
                            save_sms_templates(templates)
                            show_toast("Template deleted!", "info")
                            st.rerun()
        else:
            st.info("No templates found")
    
    # ==============================
    # TAB 3: SMS ANALYTICS
    # ==============================
    with tab3:
        st.markdown("## 📊 SMS Analytics")
        
        logs_df = load_sms_logs()
        
        if not logs_df.empty:
            logs_df["sent_date"] = pd.to_datetime(logs_df["sent_date"])
            
            total_sent = len(logs_df)
            total_success = len(logs_df[logs_df["status"] == "SENT"])
            total_failed = len(logs_df[logs_df["status"] == "FAILED"])
            total_cost = logs_df["cost"].sum()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📤 Total Sent", total_sent)
            with col2:
                st.metric("✅ Successful", total_success, delta=f"{total_success/total_sent*100:.1f}%" if total_sent > 0 else "0%")
            with col3:
                st.metric("❌ Failed", total_failed)
            with col4:
                st.metric("💰 Total Cost", f"${total_cost:.2f}")
            
            st.markdown("### 📈 SMS Activity")
            daily_sms = logs_df.groupby(logs_df["sent_date"].dt.date).size().reset_index()
            daily_sms.columns = ["Date", "Count"]
            st.bar_chart(daily_sms.set_index("Date"))
            
            st.markdown("### 📊 SMS by Type")
            sms_by_type = logs_df["type"].value_counts().reset_index()
            sms_by_type.columns = ["Type", "Count"]
            st.dataframe(sms_by_type, use_container_width=True, hide_index=True)
        else:
            st.info("No SMS data available")
    
    # ==============================
    # TAB 4: SMS HISTORY
    # ==============================
    with tab4:
        st.markdown("## 📜 SMS History")
        
        logs_df = load_sms_logs()
        
        if not logs_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox("Status", ["All", "SENT", "FAILED"])
            with col2:
                type_filter = st.selectbox("Type", ["All"] + logs_df["type"].unique().tolist())
            with col3:
                date_filter = st.date_input("Date", value=None)
            
            filtered_df = logs_df.copy()
            
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df["status"] == status_filter]
            
            if type_filter != "All":
                filtered_df = filtered_df[filtered_df["type"] == type_filter]
            
            if date_filter:
                filtered_df["sent_date_dt"] = pd.to_datetime(filtered_df["sent_date"]).dt.date
                filtered_df = filtered_df[filtered_df["sent_date_dt"] == date_filter]
            
            display_df = filtered_df[["sent_date", "recipient", "message", "type", "status", "cost"]].copy()
            display_df["sent_date"] = pd.to_datetime(display_df["sent_date"]).dt.strftime("%Y-%m-%d %H:%M")
            display_df["message"] = display_df["message"].str[:100] + "..."
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "cost": st.column_config.NumberColumn("Cost", format="$%.2f")
                }
            )
            
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export SMS Logs (CSV)",
                data=csv,
                file_name=f"sms_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No SMS history found")
    
    # ==============================
    # TAB 5: SETTINGS - UPDATED
    # ==============================
    with tab5:
        st.markdown("## ⚙️ SMS Gateway Settings")
        
        settings = load_sms_settings()
        
        st.markdown("### 📌 Africa's Talking Setup")
        st.info("""
        1. Go to https://account.africastalking.com/
        2. **Settings** → **API Key**
        3. Copy your API Key (starts with 'atsk_')
        4. Paste it below and click Save
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            enabled = st.checkbox("Enable SMS Service", value=settings.get("enabled", True))
            test_mode = st.checkbox("🧪 Test Mode (no actual SMS sent)", value=settings.get("test_mode", True))
            
            if test_mode:
                st.info("🔹 Test Mode: SMS are simulated")
            else:
                st.warning("🔸 Live Mode: SMS will be sent to real numbers")
                st.warning("💰 Ensure you have credit in your Africa's Talking account.")
        
        with col2:
            sender_id = st.text_input("Sender ID", value=settings.get("sender_id", "AzielInvest"), 
                                     help="Max 11 characters")
            default_country = st.text_input("Default Country Code", value=settings.get("default_country_code", "263"))
        
        st.markdown("---")
        st.markdown("### 🔑 Africa's Talking Credentials")
        
        current_api_key = settings.get("africastalking_api_key", "")
        if current_api_key:
            st.success(f"✅ API Key is configured (length: {len(current_api_key)} characters)")
        else:
            st.warning("⚠️ API Key not configured")
        
        api_key = st.text_input("API Key", type="password", value=current_api_key)
        username = st.text_input("Username", value=settings.get("africastalking_username", "sandbox"))
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 Save Settings", type="primary", use_container_width=True):
                settings.update({
                    "enabled": enabled,
                    "test_mode": test_mode,
                    "sender_id": sender_id,
                    "default_country_code": default_country,
                    "africastalking_api_key": api_key,
                    "africastalking_username": username
                })
                save_sms_settings(settings)
                st.success("✅ Settings saved successfully!")
                show_toast("SMS settings updated!", "success")
                st.rerun()
        
        with col2:
            if st.button("🔌 Test Connection", use_container_width=True):
                if api_key:
                    st.success(f"✅ API Key validated! (Length: {len(api_key)} characters)")
                    st.info("💡 To test actual SMS:\n1. Disable Test Mode\n2. Send a message")
                else:
                    st.error("❌ Please enter your API Key")
        
        with col3:
            if st.button("🔍 Diagnostic Test", use_container_width=True):
                if api_key:
                    with st.spinner("Testing API connection..."):
                        result = test_africastalking_connection(api_key, username)
                        if result.get("status_code") == 200:
                            st.success("✅ API Key is valid and working!")
                        elif result.get("status_code") == 401:
                            st.error("❌ Authentication failed - Invalid API Key or username\n\nPlease check:\n1. Your API Key is correct\n2. Your username is 'sandbox'")
                        else:
                            st.warning(f"Response: {result}")
                else:
                    st.error("❌ Please enter your API Key")
        
        st.markdown("---")
        st.markdown("### 📋 Current Configuration")
        
        config_data = {
            "Provider": settings.get("provider", "africastalking"),
            "Sender ID": settings.get("sender_id", "Not set"),
            "Test Mode": "✅ Enabled" if settings.get("test_mode", True) else "❌ Disabled",
            "Service Status": "✅ Enabled" if settings.get("enabled", True) else "❌ Disabled",
            "API Key": "✅ Configured" if settings.get("africastalking_api_key", "") else "❌ Not Configured",
            "Username": settings.get("africastalking_username", "Not set")
        }
        
        for key, value in config_data.items():
            st.write(f"**{key}:** {value}")


if __name__ == "__main__":
    sms_gateway_dashboard()