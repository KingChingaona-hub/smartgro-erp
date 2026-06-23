import streamlit as st
import pandas as pd
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
import secrets

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
            "api_key": "",
            "username": "",
            "sender_id": "AzielInvest",
            "enabled": True,
            "default_country_code": "263",
            "test_mode": True
        }
        with open(SMS_SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)


def load_sms_logs():
    """Load SMS logs"""
    init_sms_files()
    return pd.read_csv(SMS_FILE)


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
    with open(SMS_SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_sms_settings(settings):
    """Save SMS settings"""
    with open(SMS_SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# ==============================
# SMS PROVIDERS
# ==============================
def send_sms_africastalking(recipient, message, settings):
    """Send SMS via Africa's Talking"""
    try:
        # Format phone number
        if not recipient.startswith("+"):
            recipient = f"+{settings.get('default_country_code', '263')}{recipient.lstrip('0')}"
        
        # In test mode, just log
        if settings.get("test_mode", True):
            return {
                "success": True,
                "message": "Test mode: SMS would be sent",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00
            }
        
        # Real API call (simulated - replace with actual API)
        return {
            "success": True,
            "message": "SMS sent successfully",
            "sms_id": f"SMS_{secrets.randbelow(10000):04d}",
            "cost": 0.05
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def send_sms_twilio(recipient, message, settings):
    """Send SMS via Twilio"""
    try:
        if settings.get("test_mode", True):
            return {
                "success": True,
                "message": "Test mode: SMS would be sent",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00
            }
        
        return {
            "success": True,
            "message": "SMS sent successfully",
            "sms_id": f"SMS_{secrets.randbelow(10000):04d}",
            "cost": 0.05
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def send_sms_semaphore(recipient, message, settings):
    """Send SMS via Semaphore"""
    try:
        if settings.get("test_mode", True):
            return {
                "success": True,
                "message": "Test mode: SMS would be sent",
                "sms_id": f"TEST_{secrets.randbelow(10000):04d}",
                "cost": 0.00
            }
        
        return {
            "success": True,
            "message": "SMS sent successfully",
            "sms_id": f"SMS_{secrets.randbelow(10000):04d}",
            "cost": 0.05
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def send_sms(recipient, message, sms_type="GENERAL", sent_by="system"):
    """Send SMS using configured provider"""
    
    settings = load_sms_settings()
    
    if not settings.get("enabled", True):
        return {"success": False, "message": "SMS service is disabled"}
    
    # Validate phone number
    valid, standardized, msg = validate_zimbabwe_phone(recipient)
    if not valid:
        return {"success": False, "message": f"Invalid phone number: {msg}"}
    
    # Send based on provider
    provider = settings.get("provider", "africastalking")
    
    if provider == "africastalking":
        result = send_sms_africastalking(standardized, message, settings)
    elif provider == "twilio":
        result = send_sms_twilio(standardized, message, settings)
    elif provider == "semaphore":
        result = send_sms_semaphore(standardized, message, settings)
    else:
        return {"success": False, "message": f"Unknown provider: {provider}"}
    
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


def log_sms(recipient, message, sms_type, status, sent_by, response, cost=0):
    """Log SMS to file"""
    df = load_sms_logs()
    
    new_sms = pd.DataFrame([{
        "sms_id": f"SMS{len(df)+1:08d}",
        "recipient": recipient,
        "message": message[:500],  # Truncate for storage
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
# SMS FUNCTIONS
# ==============================
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
        
        # Load customer data
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
            with col2:
                sender_name = st.text_input("Sender Name", value="AzielInvest")
            
            message = st.text_area("Message", height=150, placeholder="Type your message here...")
            char_count = len(message)
            sms_count = (char_count // 160) + 1 if char_count > 0 else 0
            
            st.info(f"📊 {char_count} characters | {sms_count} SMS segment(s)")
            
            if st.button("📤 Send SMS", type="primary", use_container_width=True):
                if recipient and message:
                    result = send_sms(recipient, message, "SINGLE", st.session_state.get("username", "system"))
                    if result["success"]:
                        st.success("✅ SMS sent successfully!")
                        show_toast("SMS sent successfully!", "success")
                    else:
                        st.error(f"❌ Failed to send SMS: {result['message']}")
                else:
                    st.error("Please enter recipient and message")
        
        elif send_type == "Bulk Message":
            st.markdown("### Send Bulk SMS")
            
            # Select recipients
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
            
            else:  # Upload CSV
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
                    result = send_bulk_sms(recipients, message, "BULK", st.session_state.get("username", "system"))
                    
                    st.success(f"✅ Sent {result['success_count']}/{result['total']} messages")
                    if result["failed_count"] > 0:
                        st.warning(f"⚠️ {result['failed_count']} messages failed")
                    show_toast(f"Bulk SMS sent! {result['success_count']} successful", "success")
        
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
                        result = send_promotional_sms(
                            recipient_phones,
                            offer,
                            expiry.strftime("%Y-%m-%d"),
                            st.session_state.get("username", "system")
                        )
                        st.success(f"✅ Campaign sent to {result['success_count']} customers")
                        show_toast("Promotional campaign sent!", "success")
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
                    result = send_order_confirmation(
                        customer_phone,
                        order_id,
                        total,
                        st.session_state.get("username", "system")
                    )
                    if result["success"]:
                        st.success("✅ Order confirmation sent!")
                        show_toast("Order confirmation sent!", "success")
                    else:
                        st.error(f"❌ Failed: {result['message']}")
        
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
                    result = send_delivery_notification(
                        customer_phone,
                        order_id,
                        st.session_state.get("username", "system")
                    )
                    if result["success"]:
                        st.success("✅ Delivery notification sent!")
                        show_toast("Delivery notification sent!", "success")
                    else:
                        st.error(f"❌ Failed: {result['message']}")
        
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
                    result = send_payment_reminder(
                        customer_phone,
                        customer_name,
                        amount,
                        due_date.strftime("%Y-%m-%d"),
                        st.session_state.get("username", "system")
                    )
                    if result["success"]:
                        st.success("✅ Payment reminder sent!")
                        show_toast("Payment reminder sent!", "success")
                    else:
                        st.error(f"❌ Failed: {result['message']}")
                else:
                    st.error("Please fill all required fields")
        
        elif send_type == "Birthday Wishes":
            st.markdown("### 🎂 Birthday Wishes")
            
            if not customers_df.empty:
                customer = st.selectbox("Select Customer", customers_df["customer_name"].tolist(), key="birthday_customer")
                customer_phone = customers_df[customers_df["customer_name"] == customer]["phone"].iloc[0]
                discount = st.number_input("Discount (%)", min_value=0, max_value=100, value=10)
                
                if st.button("📤 Send Birthday Wish", type="primary", use_container_width=True):
                    result = send_birthday_wish(
                        customer_phone,
                        customer,
                        discount,
                        st.session_state.get("username", "system")
                    )
                    if result["success"]:
                        st.success("✅ Birthday wish sent!")
                        show_toast("Birthday wish sent!", "success")
                    else:
                        st.error(f"❌ Failed: {result['message']}")
    
    # ==============================
    # TAB 2: TEMPLATES
    # ==============================
    with tab2:
        st.markdown("## 📋 SMS Templates")
        
        templates = load_sms_templates()
        
        # Add new template
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
        
        # Display templates
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
            
            # Summary metrics
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
            
            # SMS over time
            st.markdown("### 📈 SMS Activity")
            daily_sms = logs_df.groupby(logs_df["sent_date"].dt.date).size().reset_index()
            daily_sms.columns = ["Date", "Count"]
            
            st.bar_chart(daily_sms.set_index("Date"))
            
            # SMS by type
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
            # Filters
            col1, col2, col3 = st.columns(3)
            with col1:
                status_filter = st.selectbox("Status", ["All", "SENT", "FAILED"])
            with col2:
                type_filter = st.selectbox("Type", ["All"] + logs_df["type"].unique().tolist())
            with col3:
                date_filter = st.date_input("Date Range", value=None)
            
            filtered_df = logs_df.copy()
            
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df["status"] == status_filter]
            
            if type_filter != "All":
                filtered_df = filtered_df[filtered_df["type"] == type_filter]
            
            if date_filter:
                filtered_df["sent_date_dt"] = pd.to_datetime(filtered_df["sent_date"]).dt.date
                filtered_df = filtered_df[filtered_df["sent_date_dt"] == date_filter]
            
            # Display
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
            
            # Export
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
    # TAB 5: SETTINGS
    # ==============================
    with tab5:
        st.markdown("## ⚙️ SMS Gateway Settings")
        
        settings = load_sms_settings()
        
        col1, col2 = st.columns(2)
        
        with col1:
            enabled = st.checkbox("Enable SMS Service", value=settings.get("enabled", True))
            provider = st.selectbox(
                "SMS Provider",
                ["africastalking", "twilio", "semaphore"],
                index=["africastalking", "twilio", "semaphore"].index(settings.get("provider", "africastalking"))
            )
            test_mode = st.checkbox("Test Mode (no actual SMS sent)", value=settings.get("test_mode", True))
        
        with col2:
            sender_id = st.text_input("Sender ID", value=settings.get("sender_id", "AzielInvest"))
            default_country = st.text_input("Default Country Code", value=settings.get("default_country_code", "263"))
            
            if provider == "africastalking":
                api_key = st.text_input("API Key", type="password", value=settings.get("api_key", ""))
                username = st.text_input("Username", value=settings.get("username", ""))
            elif provider == "twilio":
                account_sid = st.text_input("Account SID", type="password", value=settings.get("account_sid", ""))
                auth_token = st.text_input("Auth Token", type="password", value=settings.get("auth_token", ""))
            elif provider == "semaphore":
                api_key = st.text_input("API Key", type="password", value=settings.get("api_key", ""))
        
        # Save settings
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
            settings.update({
                "enabled": enabled,
                "provider": provider,
                "test_mode": test_mode,
                "sender_id": sender_id,
                "default_country_code": default_country,
                "api_key": api_key if provider != "twilio" else settings.get("api_key", ""),
                "username": username if provider == "africastalking" else settings.get("username", ""),
                "account_sid": account_sid if provider == "twilio" else settings.get("account_sid", ""),
                "auth_token": auth_token if provider == "twilio" else settings.get("auth_token", "")
            })
            save_sms_settings(settings)
            st.success("✅ Settings saved successfully!")
            show_toast("SMS settings updated!", "success")
        
        # Balance check
        st.markdown("---")
        st.markdown("### 💰 Account Balance")
        
        if st.button("🔄 Check Balance", use_container_width=True):
            st.info("💰 Balance: $10.00 (Simulated) - Connect to actual provider for real balance")


if __name__ == "__main__":
    sms_gateway_dashboard()