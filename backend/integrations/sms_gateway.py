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
# AFRICA'S TALKING SMS - FIXED
# ==============================
def send_sms_africastalking(recipient, message, settings):
    """Send SMS via Africa's Talking - FIXED AUTHENTICATION"""
    try:
        api_key = settings.get("africastalking_api_key", "").strip()
        username = settings.get("africastalking_username", "sandbox").strip()
        
        # Check if API key is configured
        if not api_key:
            return {
                "success": False, 
                "message": "❌ API Key not configured. Go to Settings tab to add your Africa's Talking API Key."
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
        
        # Correct headers for Africa's Talking
        headers = {
            "apiKey": api_key,  # Note: lowercase 'apiKey' as per Africa's Talking docs
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        # Correct data format
        data = {
            "username": username,
            "to": recipient,
            "message": message,
            "from": settings.get("sender_id", "AzielInvest")[:11]  # Max 11 characters
        }
        
        # Send request with timeout
        response = requests.post(
            url, 
            headers=headers, 
            data=data, 
            timeout=30
        )
        
        # Check response
        if response.status_code == 200 or response.status_code == 201:
            try:
                result = response.json()
                
                # Check for API error response
                if "SMSMessageData" in result:
                    recipients_data = result["SMSMessageData"].get("Recipients", [])
                    if recipients_data and len(recipients_data) > 0:
                        status = recipients_data[0].get("status", "")
                        if status.lower() == "success":
                            return {
                                "success": True,
                                "message": "✅ SMS sent successfully!",
                                "sms_id": recipients_data[0].get("messageId", f"SMS_{secrets.randbelow(10000):04d}"),
                                "cost": 0.05
                            }
                        else:
                            error_msg = recipients_data[0].get("status", "Unknown error")
                            return {
                                "success": False,
                                "message": f"❌ Africa's Talking Error: {error_msg}"
                            }
                else:
                    # Check for error in response
                    error_msg = result.get("error", "Unknown error")
                    return {
                        "success": False,
                        "message": f"❌ Africa's Talking Error: {error_msg}"
                    }
            except json.JSONDecodeError:
                return {
                    "success": False,
                    "message": f"❌ Invalid response from Africa's Talking: {response.text[:200]}"
                }
        else:
            # Handle HTTP errors
            try:
                error_data = response.json()
                error_msg = error_data.get("error", response.text)
            except:
                error_msg = response.text
            
            return {
                "success": False,
                "message": f"❌ HTTP Error {response.status_code}: {error_msg[:200]}"
            }
            
    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"❌ Network error: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"❌ Error: {str(e)}"}


# ==============================
# MAIN SEND SMS FUNCTION
# ==============================
def send_sms(recipient, message, sms_type="GENERAL", sent_by="system"):
    """Send SMS using configured provider"""
    
    settings = load_sms_settings()
    
    if not settings.get("enabled", True):
        return {"success": False, "message": "❌ SMS service is disabled"}
    
    # Validate phone number
    valid, standardized, msg = validate_zimbabwe_phone(recipient)
    if not valid:
        return {"success": False, "message": f"❌ Invalid phone number: {msg}"}
    
    # Get provider
    provider = settings.get("provider", "africastalking")
    
    # Send based on provider
    if provider == "africastalking":
        result = send_sms_africastalking(standardized, message, settings)
    else:
        return {"success": False, "message": f"❌ Unknown provider: {provider}"}
    
    # Log SMS
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
    settings = load_sms_settings()
    
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
        
        # Show current status
        if settings.get("test_mode", True):
            st.info("🧪 **Test Mode is ENABLED** - SMS will not be sent. Disable in Settings to send real SMS.")
        else:
            if settings.get("africastalking_api_key", ""):
                st.success("✅ **Live Mode** - SMS will be sent to real numbers.")
            else:
                st.warning("⚠️ **API Key not configured** - Go to Settings to add your API Key.")
        
        # Load customer data
        try:
            from backend.core.database import load_customers
            customers_df = load_customers()
        except:
            customers_df = pd.DataFrame()
        
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
                sender_name = st.text_input("Sender ID", value=settings.get("sender_id", "AzielInvest"), 
                                           help="Max 11 characters")
            
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
                st.warning(f"⚠️ This will send to {len(recipients)} recipients")
                
                if st.button("📤 Send Bulk SMS", type="primary", use_container_width=True):
                    with st.spinner("Sending bulk SMS..."):
                        result = send_bulk_sms(recipients, message, "BULK", st.session_state.get("username", "system"))
                        
                        st.success(f"✅ Sent {result['success_count']}/{result['total']} messages")
                        if result["failed_count"] > 0:
                            st.warning(f"⚠️ {result['failed_count']} messages failed")
                        st.balloons()
        
        # Rest of the message types...
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
    # TAB 5: SETTINGS - FIXED
    # ==============================
    with tab5:
        st.markdown("## ⚙️ SMS Gateway Settings")
        
        settings = load_sms_settings()
        
        st.markdown("### 📌 Africa's Talking Setup")
        st.info("""
        1. Go to https://account.africastalking.com/
        2. **Sign Up** or **Log In** with your email and password
        3. Go to **Settings** → **API Key**
        4. Copy your **Live API Key**
        5. Your **Username** is your account username (usually 'sandbox' for testing)
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            enabled = st.checkbox("Enable SMS Service", value=settings.get("enabled", True))
            test_mode = st.checkbox("🧪 Test Mode (no actual SMS sent)", value=settings.get("test_mode", True))
            if test_mode:
                st.warning("⚠️ Test Mode is ON - No real SMS will be sent")
            else:
                st.success("✅ Test Mode is OFF - Real SMS will be sent")
        
        with col2:
            sender_id = st.text_input("Sender ID", value=settings.get("sender_id", "AzielInvest"), 
                                     help="Max 11 characters. This will appear as the sender name")
            default_country = st.text_input("Default Country Code", value=settings.get("default_country_code", "263"))
        
        st.markdown("---")
        st.markdown("### 🔑 Africa's Talking Credentials")
        
        # Show current status
        current_api_key = settings.get("africastalking_api_key", "")
        if current_api_key:
            st.success(f"✅ API Key is configured (length: {len(current_api_key)} characters)")
        else:
            st.warning("⚠️ API Key not configured - SMS will not work")
        
        api_key = st.text_input(
            "API Key", 
            type="password", 
            value=current_api_key,
            help="Your Africa's Talking Live API Key from Settings → API Key"
        )
        username = st.text_input(
            "Username", 
            value=settings.get("africastalking_username", "sandbox"),
            help="Your Africa's Talking username (usually 'sandbox' for testing)"
        )
        
        col1, col2 = st.columns(2)
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
            if st.button("🔌 Test API Key", use_container_width=True):
                if api_key:
                    st.success(f"✅ API Key saved (length: {len(api_key)} characters)")
                    st.info("💡 To test actual SMS:\n1. Disable Test Mode\n2. Send a message to your number")
                else:
                    st.error("❌ Please enter your API Key first")


if __name__ == "__main__":
    sms_gateway_dashboard()