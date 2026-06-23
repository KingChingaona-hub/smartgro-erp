import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import json
import secrets

# ==============================
# IMPORT FROM CORRECT MODULE
# ==============================
from backend.core.db_adapter import (
    load_customers,
    load_sales,
    load_products,
    to_float
)

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
FOLLOWUP_FILE = DATA_DIR / "followup_settings.json"
FOLLOWUP_LOG_FILE = DATA_DIR / "followup_logs.csv"
FOLLOWUP_SCHEDULE_FILE = DATA_DIR / "followup_schedule.csv"

# ==============================
# INITIALIZATION
# ==============================
def init_followup_files():
    """Initialize follow-up related files"""
    DATA_DIR.mkdir(exist_ok=True)
    
    # Follow-up settings
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
            "max_followups_per_day": 50
        }
        with open(FOLLOWUP_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    
    # Follow-up logs
    if not FOLLOWUP_LOG_FILE.exists():
        df = pd.DataFrame(columns=[
            "log_id", "customer_name", "customer_phone", "customer_email",
            "followup_type", "message", "sent_date", "status", "response", "notes"
        ])
        df.to_csv(FOLLOWUP_LOG_FILE, index=False)
    
    # Follow-up schedule
    if not FOLLOWUP_SCHEDULE_FILE.exists():
        df = pd.DataFrame(columns=[
            "schedule_id", "customer_name", "customer_phone", "followup_type",
            "scheduled_date", "message", "status", "notes"
        ])
        df.to_csv(FOLLOWUP_SCHEDULE_FILE, index=False)


def load_followup_settings():
    """Load follow-up settings"""
    init_followup_files()
    with open(FOLLOWUP_FILE, "r") as f:
        return json.load(f)


def save_followup_settings(settings):
    """Save follow-up settings"""
    with open(FOLLOWUP_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def load_followup_logs():
    """Load follow-up logs"""
    init_followup_files()
    if FOLLOWUP_LOG_FILE.exists():
        return pd.read_csv(FOLLOWUP_LOG_FILE)
    return pd.DataFrame(columns=[
        "log_id", "customer_name", "customer_phone", "customer_email",
        "followup_type", "message", "sent_date", "status", "response", "notes"
    ])


def save_followup_logs(df):
    """Save follow-up logs"""
    df.to_csv(FOLLOWUP_LOG_FILE, index=False)


def load_followup_schedule():
    """Load follow-up schedule"""
    init_followup_files()
    if FOLLOWUP_SCHEDULE_FILE.exists():
        return pd.read_csv(FOLLOWUP_SCHEDULE_FILE)
    return pd.DataFrame(columns=[
        "schedule_id", "customer_name", "customer_phone", "followup_type",
        "scheduled_date", "message", "status", "notes"
    ])


def save_followup_schedule(df):
    """Save follow-up schedule"""
    df.to_csv(FOLLOWUP_SCHEDULE_FILE, index=False)


# ==============================
# MESSAGE TEMPLATES
# ==============================
def get_message_template(template_type, data):
    """Get formatted message template"""
    
    templates = {
        "thank_you": "Thank you for your purchase at Aziel Investments! We appreciate your business. {customer_name}, your order #{receipt_no} of ${total:.2f} was confirmed. Visit us again soon!",
        "review": "Hi {customer_name}, we hope you enjoyed your shopping experience at Aziel Investments. Please take a moment to leave us a review: {review_link}",
        "reengagement": "Hi {customer_name}, we miss you at Aziel Investments! As a valued customer, enjoy {discount}% off your next purchase. Valid until {expiry}. Visit us today!",
        "birthday": "Happy Birthday {customer_name}! 🎂 Celebrate with {discount}% off at Aziel Investments this week. Enjoy your special day!",
        "abandoned_cart": "Hi {customer_name}, you left items in your cart at Aziel Investments. Complete your purchase and get {discount}% off! {cart_link}",
        "loyalty_update": "Hi {customer_name}, you have earned {points} loyalty points at Aziel Investments! Redeem them on your next visit. Current balance: ${balance:.2f}",
        "product_recommendation": "Hi {customer_name}, based on your previous purchases, you might like {product_name}. Available now at Aziel Investments for ${price:.2f}!"
    }
    
    try:
        return templates.get(template_type, "").format(**data)
    except:
        return templates.get(template_type, "")


# ==============================
# FOLLOW-UP FUNCTIONS
# ==============================
def send_followup(customer, followup_type, message):
    """Send a follow-up message to a customer"""
    
    # In production, this would send via SMS/WhatsApp/Email
    # For now, log the follow-up
    
    df = load_followup_logs()
    
    log_id = f"FL{len(df)+1:08d}"
    
    new_log = pd.DataFrame([{
        "log_id": log_id,
        "customer_name": customer.get("name", ""),
        "customer_phone": customer.get("phone", ""),
        "customer_email": customer.get("email", ""),
        "followup_type": followup_type,
        "message": message[:500],
        "sent_date": datetime.now().isoformat(),
        "status": "SENT",
        "response": "",
        "notes": ""
    }])
    
    df = pd.concat([df, new_log], ignore_index=True)
    save_followup_logs(df)
    
    return True, log_id


def send_thank_you(customer, receipt_no, total):
    """Send thank you message after purchase"""
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "receipt_no": receipt_no,
        "total": total
    }
    message = get_message_template("thank_you", data)
    return send_followup(customer, "THANK_YOU", message)


def send_review_request(customer, receipt_no):
    """Send review request after purchase"""
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "review_link": "https://azielinvestments.com/review"
    }
    message = get_message_template("review", data)
    return send_followup(customer, "REVIEW_REQUEST", message)


def send_reengagement(customer, discount=10, expiry_days=14):
    """Send re-engagement message to inactive customers"""
    expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "discount": discount,
        "expiry": expiry
    }
    message = get_message_template("reengagement", data)
    return send_followup(customer, "REENGAGEMENT", message)


def send_birthday_wish(customer, discount=15):
    """Send birthday wish to customer"""
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "discount": discount
    }
    message = get_message_template("birthday", data)
    return send_followup(customer, "BIRTHDAY", message)


def send_abandoned_cart(customer, cart_items, discount=10):
    """Send abandoned cart reminder"""
    data = {
        "customer_name": customer.get("name", "Valued Customer"),
        "discount": discount,
        "cart_link": "https://azielinvestments.com/cart"
    }
    message = get_message_template("abandoned_cart", data)
    return send_followup(customer, "ABANDONED_CART", message)


# ==============================
# ANALYTICS
# ==============================
def get_followup_stats():
    """Get follow-up statistics"""
    df = load_followup_logs()
    
    if df.empty:
        return {
            "total": 0,
            "by_type": {},
            "sent_today": 0,
            "last_7_days": 0
        }
    
    df["sent_date"] = pd.to_datetime(df["sent_date"])
    
    total = len(df)
    by_type = df["followup_type"].value_counts().to_dict()
    sent_today = len(df[df["sent_date"] >= datetime.now().replace(hour=0, minute=0, second=0)])
    last_7_days = len(df[df["sent_date"] >= datetime.now() - timedelta(days=7)])
    
    return {
        "total": total,
        "by_type": by_type,
        "sent_today": sent_today,
        "last_7_days": last_7_days
    }


# ==============================
# TOAST NOTIFICATION
# ==============================
def show_toast(message, type="info"):
    """Display a toast notification"""
    colors = {
        "info": "#4CAF50",
        "success": "#4CAF50",
        "warning": "#FF9800",
        "error": "#f44336"
    }
    icon = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌"
    }
    
    toast_html = f"""
    <div style="
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: {colors.get(type, '#4CAF50')};
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        z-index: 9999;
        animation: slideIn 0.5s ease;
        max-width: 400px;
    ">
        <span style="font-size: 1.2rem; margin-right: 8px;">{icon.get(type, 'ℹ️')}</span>
        {message}
    </div>
    <style>
        @keyframes slideIn {{
            from {{
                transform: translateX(100%);
                opacity: 0;
            }}
            to {{
                transform: translateX(0);
                opacity: 1;
            }}
        }}
    </style>
    """
    st.markdown(toast_html, unsafe_allow_html=True)


# ==============================
# FOLLOW-UP DASHBOARD
# ==============================
def automated_followup_dashboard():
    """Automated Customer Follow-up Dashboard"""
    
    st.title("🤖 Automated Customer Follow-up")
    st.caption("Automated thank you messages, review requests, re-engagement campaigns, and more")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can access automated follow-up.")
        return
    
    init_followup_files()
    
    # Load data from correct module
    customers_df = load_customers()
    sales_df = load_sales()
    products_df = load_products()
    
    # ==============================
    # TABS
    # ==============================
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "📤 Send Follow-ups",
        "📋 Schedule",
        "📜 History",
        "⚙️ Settings"
    ])
    
    # ==============================
    # TAB 1: DASHBOARD
    # ==============================
    with tab1:
        st.markdown("## 📊 Follow-up Dashboard")
        
        stats = get_followup_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📤 Total Follow-ups", stats["total"])
        with col2:
            st.metric("📅 Today", stats["sent_today"])
        with col3:
            st.metric("📊 Last 7 Days", stats["last_7_days"])
        with col4:
            st.metric("👥 Customers", len(customers_df) if not customers_df.empty else 0)
        
        # Follow-up by type
        if stats["by_type"]:
            st.markdown("### 📊 Follow-up by Type")
            types_df = pd.DataFrame(list(stats["by_type"].items()), columns=["Type", "Count"])
            st.bar_chart(types_df.set_index("Type"))
        
        # Customers needing follow-up
        st.markdown("### 🎯 Customers Needing Attention")
        
        if not customers_df.empty:
            # Check if last_purchase_date exists
            if "last_purchase_date" in customers_df.columns:
                customers_df["last_purchase_date"] = pd.to_datetime(customers_df["last_purchase_date"], errors="coerce")
                customers_df["days_inactive"] = (datetime.now() - customers_df["last_purchase_date"]).dt.days
                
                # Customers inactive > 30 days
                inactive = customers_df[customers_df["days_inactive"] > 30]
                
                if not inactive.empty:
                    st.warning(f"⚠️ {len(inactive)} customers inactive for over 30 days")
                    st.dataframe(
                        inactive[["customer_name", "phone", "total_spent", "days_inactive"]],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "days_inactive": st.column_config.NumberColumn("Days Inactive")
                        }
                    )
                    
                    if st.button("📤 Send Re-engagement to All", use_container_width=True):
                        count = 0
                        for _, customer in inactive.iterrows():
                            success, _ = send_reengagement(
                                {"name": customer["customer_name"], "phone": customer["phone"]},
                                discount=10
                            )
                            if success:
                                count += 1
                        st.success(f"✅ Sent re-engagement to {count} customers!")
                        show_toast(f"Re-engagement sent to {count} customers", "success")
                        st.rerun()
                else:
                    st.success("✅ All customers are active!")
            else:
                st.info("Customer purchase data not available")
        else:
            st.info("No customer data available")
    
    # ==============================
    # TAB 2: SEND FOLLOW-UPS
    # ==============================
    with tab2:
        st.markdown("## 📤 Send Follow-ups")
        
        followup_type = st.selectbox(
            "Select Follow-up Type",
            [
                "Thank You Message",
                "Review Request",
                "Re-engagement Campaign",
                "Birthday Wishes",
                "Abandoned Cart Recovery",
                "Custom Message"
            ]
        )
        
        # Customer selection
        if not customers_df.empty:
            customer_list = customers_df["customer_name"].tolist() if "customer_name" in customers_df.columns else []
            
            if customer_list:
                selected_customers = st.multiselect(
                    "Select Customers",
                    customer_list,
                    format_func=lambda x: f"{x} - {customers_df[customers_df['customer_name'] == x]['phone'].iloc[0] if 'phone' in customers_df.columns else ''}"
                )
                
                if followup_type == "Thank You Message":
                    receipt_no = st.text_input("Receipt Number")
                    total = st.number_input("Total Amount ($)", min_value=0.0, value=0.0)
                    
                    if st.button("📤 Send Thank You", type="primary", use_container_width=True):
                        count = 0
                        for customer in selected_customers:
                            customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                            success, _ = send_thank_you(
                                {"name": customer, "phone": customer_data.get("phone", "")},
                                receipt_no,
                                total
                            )
                            if success:
                                count += 1
                        st.success(f"✅ Sent to {count} customers!")
                        show_toast(f"Thank you messages sent to {count} customers", "success")
                
                elif followup_type == "Review Request":
                    if st.button("📤 Send Review Request", type="primary", use_container_width=True):
                        count = 0
                        for customer in selected_customers:
                            customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                            success, _ = send_review_request(
                                {"name": customer, "phone": customer_data.get("phone", "")},
                                ""
                            )
                            if success:
                                count += 1
                        st.success(f"✅ Sent to {count} customers!")
                        show_toast(f"Review requests sent to {count} customers", "success")
                
                elif followup_type == "Re-engagement Campaign":
                    discount = st.number_input("Discount (%)", min_value=5, max_value=50, value=10)
                    expiry_days = st.number_input("Valid for (days)", min_value=7, max_value=30, value=14)
                    
                    if st.button("📤 Send Re-engagement", type="primary", use_container_width=True):
                        count = 0
                        for customer in selected_customers:
                            customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                            success, _ = send_reengagement(
                                {"name": customer, "phone": customer_data.get("phone", "")},
                                discount,
                                expiry_days
                            )
                            if success:
                                count += 1
                        st.success(f"✅ Sent to {count} customers!")
                        show_toast(f"Re-engagement sent to {count} customers", "success")
                
                elif followup_type == "Birthday Wishes":
                    discount = st.number_input("Birthday Discount (%)", min_value=5, max_value=50, value=15)
                    
                    if st.button("🎂 Send Birthday Wishes", type="primary", use_container_width=True):
                        count = 0
                        for customer in selected_customers:
                            customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                            success, _ = send_birthday_wish(
                                {"name": customer, "phone": customer_data.get("phone", "")},
                                discount
                            )
                            if success:
                                count += 1
                        st.success(f"✅ Sent to {count} customers!")
                        show_toast(f"Birthday wishes sent to {count} customers", "success")
                
                elif followup_type == "Abandoned Cart Recovery":
                    discount = st.number_input("Recovery Discount (%)", min_value=5, max_value=30, value=10)
                    
                    if st.button("🛒 Send Recovery", type="primary", use_container_width=True):
                        count = 0
                        for customer in selected_customers:
                            customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                            success, _ = send_abandoned_cart(
                                {"name": customer, "phone": customer_data.get("phone", "")},
                                [],
                                discount
                            )
                            if success:
                                count += 1
                        st.success(f"✅ Sent to {count} customers!")
                        show_toast(f"Abandoned cart recovery sent to {count} customers", "success")
                
                elif followup_type == "Custom Message":
                    custom_message = st.text_area("Custom Message", height=150)
                    custom_subject = st.text_input("Subject (optional)")
                    
                    if st.button("📤 Send Custom Message", type="primary", use_container_width=True):
                        if custom_message:
                            count = 0
                            for customer in selected_customers:
                                customer_data = customers_df[customers_df["customer_name"] == customer].iloc[0]
                                success, _ = send_followup(
                                    {"name": customer, "phone": customer_data.get("phone", "")},
                                    "CUSTOM",
                                    custom_message
                                )
                                if success:
                                    count += 1
                            st.success(f"✅ Sent to {count} customers!")
                            show_toast(f"Custom messages sent to {count} customers", "success")
                        else:
                            st.error("Please enter a message")
            else:
                st.warning("No customers found")
        else:
            st.warning("No customers found")
    
    # ==============================
    # TAB 3: SCHEDULE
    # ==============================
    with tab3:
        st.markdown("## 📋 Follow-up Schedule")
        
        schedule_df = load_followup_schedule()
        
        if not schedule_df.empty:
            st.dataframe(
                schedule_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "scheduled_date": st.column_config.DatetimeColumn("Scheduled Date")
                }
            )
            
            # Add to schedule
            st.markdown("### ➕ Schedule New Follow-up")
            
            col1, col2 = st.columns(2)
            with col1:
                customer_list = customers_df["customer_name"].tolist() if not customers_df.empty and "customer_name" in customers_df.columns else []
                schedule_customer = st.selectbox("Customer", customer_list if customer_list else [""])
                schedule_type = st.selectbox("Follow-up Type", ["THANK_YOU", "REVIEW_REQUEST", "REENGAGEMENT", "BIRTHDAY", "ABANDONED_CART"])
            with col2:
                schedule_date = st.datetime_input("Schedule Date", datetime.now() + timedelta(days=1))
                schedule_notes = st.text_input("Notes")
            
            if st.button("📅 Add to Schedule", use_container_width=True):
                if schedule_customer and schedule_customer != "":
                    customer_data = customers_df[customers_df["customer_name"] == schedule_customer].iloc[0]
                    new_schedule = pd.DataFrame([{
                        "schedule_id": f"SC{len(schedule_df)+1:08d}",
                        "customer_name": schedule_customer,
                        "customer_phone": customer_data.get("phone", ""),
                        "followup_type": schedule_type,
                        "scheduled_date": schedule_date.isoformat(),
                        "message": "",
                        "status": "SCHEDULED",
                        "notes": schedule_notes
                    }])
                    schedule_df = pd.concat([schedule_df, new_schedule], ignore_index=True)
                    save_followup_schedule(schedule_df)
                    st.success("✅ Follow-up scheduled!")
                    show_toast("Follow-up scheduled successfully!", "success")
                    st.rerun()
                else:
                    st.warning("Please select a customer")
        else:
            st.info("No scheduled follow-ups")
    
    # ==============================
    # TAB 4: HISTORY
    # ==============================
    with tab4:
        st.markdown("## 📜 Follow-up History")
        
        logs_df = load_followup_logs()
        
        if not logs_df.empty:
            # Filters
            col1, col2 = st.columns(2)
            with col1:
                type_filter = st.selectbox("Filter by Type", ["All"] + logs_df["followup_type"].unique().tolist())
            with col2:
                status_filter = st.selectbox("Filter by Status", ["All", "SENT", "FAILED"])
            
            filtered_df = logs_df.copy()
            if type_filter != "All":
                filtered_df = filtered_df[filtered_df["followup_type"] == type_filter]
            if status_filter != "All":
                filtered_df = filtered_df[filtered_df["status"] == status_filter]
            
            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True
            )
            
            # Export
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export Follow-up Logs (CSV)",
                data=csv,
                file_name=f"followup_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No follow-up history found")
    
    # ==============================
    # TAB 5: SETTINGS
    # ==============================
    with tab5:
        st.markdown("## ⚙️ Follow-up Settings")
        
        settings = load_followup_settings()
        
        st.markdown("### 🔄 General Settings")
        enabled = st.checkbox("Enable Automated Follow-ups", value=settings.get("enabled", True))
        max_per_day = st.number_input("Max Follow-ups per Day", min_value=10, max_value=500, value=settings.get("max_followups_per_day", 50))
        
        st.markdown("### 💬 Message Types")
        col1, col2 = st.columns(2)
        
        with col1:
            thank_you = st.checkbox("Thank You Messages", value=settings.get("thank_you_enabled", True))
            thank_you_delay = st.number_input("Thank You Delay (hours)", min_value=1, max_value=24, value=settings.get("thank_you_delay_hours", 2))
            
            review = st.checkbox("Review Requests", value=settings.get("review_enabled", True))
            review_delay = st.number_input("Review Request Delay (days)", min_value=1, max_value=7, value=settings.get("review_delay_days", 3))
        
        with col2:
            reengagement = st.checkbox("Re-engagement Campaigns", value=settings.get("reengagement_enabled", True))
            reengagement_days = st.number_input("Inactive Days Before Re-engagement", min_value=7, max_value=90, value=settings.get("reengagement_inactive_days", 30))
            reengagement_discount = st.number_input("Re-engagement Discount (%)", min_value=5, max_value=50, value=settings.get("reengagement_discount", 10))
        
        st.markdown("### 🎂 Birthday & Cart Recovery")
        col1, col2 = st.columns(2)
        
        with col1:
            birthday = st.checkbox("Birthday Wishes", value=settings.get("birthday_enabled", True))
            birthday_discount = st.number_input("Birthday Discount (%)", min_value=5, max_value=50, value=settings.get("birthday_discount", 15))
        
        with col2:
            abandoned_cart = st.checkbox("Abandoned Cart Recovery", value=settings.get("abandoned_cart_enabled", True))
            cart_delay = st.number_input("Cart Recovery Delay (hours)", min_value=1, max_value=48, value=settings.get("abandoned_cart_delay_hours", 24))
        
        st.markdown("### 📱 Communication Channels")
        col1, col2 = st.columns(2)
        
        with col1:
            sms_enabled = st.checkbox("SMS", value=settings.get("sms_enabled", True))
            whatsapp_enabled = st.checkbox("WhatsApp", value=settings.get("whatsapp_enabled", True))
        
        with col2:
            email_enabled = st.checkbox("Email", value=settings.get("email_enabled", False))
        
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
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
                "email_enabled": email_enabled
            })
            save_followup_settings(settings)
            st.success("✅ Settings saved successfully!")
            show_toast("Follow-up settings updated!", "success")


if __name__ == "__main__":
    automated_followup_dashboard()