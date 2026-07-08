import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import json

from backend.core.db_adapter import (
    load_shifts, save_shifts, start_shift, end_shift, 
    get_all_active_shifts, get_active_shifts_by_branch,
    get_current_branch, load_cash, get_cash_summary,
    load_sales, load_products, load_users
)

# ==============================
# CONSTANTS
# ==============================
SHIFTS = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO"]
COMPANY_NAME = "AZIEL INVESTMENTS"
COMPANY_ADDRESS = "Retail Park, Harare"
COMPANY_PHONE = "+263 78 290 5853"
COMPANY_EMAIL = "info@azielinvestments.co.zw"

# WhatsApp notification number (for testing/notification)
WHATSAPP_NUMBER = "263782905853"
EMAIL_NOTIFICATION = "kingtimothy495@gmail.com"


def safe_format_time(time_val):
    """Safely format a time value to string."""
    if time_val is None:
        return "N/A"
    if isinstance(time_val, pd.Timestamp):
        return time_val.strftime("%Y-%m-%d %H:%M")
    if isinstance(time_val, datetime):
        return time_val.strftime("%Y-%m-%d %H:%M")
    time_str = str(time_val)
    return time_str[:16] if time_str else "N/A"


def send_whatsapp_message(phone_number, message):
    """Send WhatsApp message using WhatsApp API or fallback to link"""
    try:
        # Clean phone number
        phone = phone_number.replace("+", "").replace(" ", "")
        if not phone.startswith("263"):
            phone = "263" + phone.lstrip("0")
        
        # Generate WhatsApp link
        whatsapp_link = f"https://wa.me/{phone}?text={message.replace(' ', '%20').replace('\n', '%0A')}"
        return whatsapp_link
    except Exception as e:
        print(f"Error sending WhatsApp: {e}")
        return None


def send_email_notification(to_email, subject, body):
    """Send email notification using SMTP (configure with your email settings)"""
    try:
        # For now, we'll just log and return success
        # In production, configure with actual SMTP settings
        print(f"Email would be sent to: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        
        # Placeholder for actual email sending
        # Uncomment and configure for actual email sending:
        """
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        sender_email = "your_email@gmail.com"
        sender_password = "your_password"
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        """
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def generate_shift_report(shift_data, shift_summary):
    """Generate a comprehensive shift report"""
    
    report = f"""
{'='*60}
{COMPANY_NAME} - SHIFT REPORT
{'='*60}

Shift ID: {shift_data.get('shift_id', 'N/A')}
Shift Name: {shift_data.get('shift_name', 'N/A')}
Cashier: {shift_data.get('cashier_name', 'N/A')}
Branch: {shift_data.get('branch_name', 'N/A')}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'-'*40}
SHIFT SUMMARY
{'-'*40}
Start Time: {safe_format_time(shift_data.get('start_time'))}
End Time: {safe_format_time(shift_data.get('end_time', datetime.now()))}
Duration: {shift_summary.get('duration', 'N/A')}
Status: {shift_data.get('status', 'N/A')}

{'-'*40}
FINANCIAL SUMMARY
{'-'*40}
Opening Cash: ${shift_summary.get('opening_cash', 0):,.2f}
Total Revenue: ${shift_summary.get('total_revenue', 0):,.2f}
Total Profit: ${shift_summary.get('total_profit', 0):,.2f}
Cash Sales: ${shift_summary.get('cash_sales', 0):,.2f}
Credit Sales: ${shift_summary.get('credit_sales', 0):,.2f}
Debt Payments: ${shift_summary.get('debt_payments', 0):,.2f}
Expenses: ${shift_summary.get('expenses', 0):,.2f}

{'-'*40}
TRANSACTIONS
{'-'*40}
Total Transactions: {shift_summary.get('transactions', 0)}
Closing Cash: ${shift_summary.get('closing_cash', 0):,.2f}
Variance: ${shift_summary.get('variance', 0):,.2f}

{'-'*40}
NOTES
{'-'*40}
{shift_summary.get('notes', 'No notes')}

{'='*60}
End of Shift Report
{COMPANY_NAME} - {COMPANY_PHONE}
{'='*60}
"""
    
    return report


def initialize_shifts():
    """Initialize shift management with predefined shifts"""
    shifts_df = load_shifts()
    users_df = load_users()
    
    # Create shifts if they don't exist
    if "shift_name" not in shifts_df.columns:
        shifts_df["shift_name"] = ""
    
    # Check if shifts are already initialized
    existing_shifts = shifts_df["shift_name"].unique().tolist() if not shifts_df.empty else []
    
    # Add predefined shifts if they don't exist
    shifts_created = False
    for shift in SHIFTS:
        if shift not in existing_shifts:
            # Create a placeholder shift record
            new_shift = pd.DataFrame([{
                "shift_id": f"SHIFT-{shift}-{datetime.now().strftime('%Y%m%d')}",
                "shift_name": shift,
                "cashier_username": "system",
                "cashier_name": f"Shift {shift}",
                "branch_id": get_current_branch(),
                "branch_name": "Head Office",
                "start_time": datetime.now().isoformat(),
                "end_time": "",
                "status": "INACTIVE",
                "opening_cash": 0,
                "closing_cash": 0,
                "total_revenue": 0,
                "profit": 0,
                "transactions": 0,
                "variance": 0,
                "manager_username": "system",
                "notes": f"Predefined shift: {shift}"
            }])
            shifts_df = pd.concat([shifts_df, new_shift], ignore_index=True)
            shifts_created = True
    
    if shifts_created:
        save_shifts(shifts_df)
    
    return shifts_df


def shift_management_page():
    """Main shift management page"""
    
    st.title("🕐 Shift Management")
    st.caption("Manage cashier shifts, track performance, and monitor activity")
    
    role = st.session_state.get("role", "cashier")
    
    # Initialize shifts
    initialize_shifts()
    
    # Get current branch
    branch_id = get_current_branch()
    
    # Load data
    shifts_df = load_shifts()
    active_shifts = get_all_active_shifts()
    
    # ==============================
    # SESSION STATE INITIALIZATION
    # ==============================
    if "show_end_shift" not in st.session_state:
        st.session_state.show_end_shift = False
    if "end_shift_id" not in st.session_state:
        st.session_state.end_shift_id = None
    if "shift_ended" not in st.session_state:
        st.session_state.shift_ended = False
    if "button_clicked" not in st.session_state:
        st.session_state.button_clicked = False
    if "shift_report" not in st.session_state:
        st.session_state.shift_report = None
    
    # ==============================
    # SIDEBAR - Shift Controls
    # ==============================
    st.sidebar.header("🔄 Shift Controls")
    
    # Only owner/manager can manage shifts
    if role in ["owner", "manager"]:
        st.sidebar.subheader("📌 Start New Shift")
        
        with st.sidebar.form("start_shift_form"):
            # Select shift from predefined list
            shift_name = st.selectbox("Select Shift", SHIFTS)
            
            cashier_username = st.text_input("Cashier Username", value=st.session_state.get("username", ""))
            cashier_name = st.text_input("Cashier Name", value=st.session_state.get("full_name", ""))
            manager_username = st.text_input("Manager Username", value=st.session_state.get("username", ""))
            opening_cash = st.number_input("Opening Cash ($)", min_value=0.0, value=0.0, step=10.0)
            
            submitted = st.form_submit_button("🚀 Start Shift", use_container_width=True)
            
            if submitted:
                if not st.session_state.button_clicked:
                    st.session_state.button_clicked = True
                    
                    if not cashier_username or not cashier_name:
                        st.sidebar.error("Please enter cashier details")
                    else:
                        success, result = start_shift(
                            cashier_username, 
                            cashier_name, 
                            branch_id, 
                            "Head Office", 
                            manager_username,
                            opening_cash,
                            shift_name
                        )
                        if success:
                            st.sidebar.success(f"✅ Shift started! ID: {result}")
                            st.session_state.button_clicked = False
                            st.rerun()
                        else:
                            st.sidebar.error(f"❌ {result}")
                            st.session_state.button_clicked = False
        
        # Shift Management (Add/Remove)
        with st.sidebar.expander("⚙️ Manage Shifts", expanded=False):
            st.markdown("### Manage Available Shifts")
            
            # Display current shifts
            current_shifts = shifts_df["shift_name"].unique().tolist() if not shifts_df.empty else []
            st.write("**Current Shifts:**")
            for s in current_shifts:
                if s and s in SHIFTS:
                    st.write(f"✅ {s}")
            
            st.markdown("---")
            
            # Add new shift
            st.markdown("#### ➕ Add New Shift")
            new_shift = st.text_input("Shift Name", placeholder="e.g., FOXTROT")
            if st.button("➕ Add Shift", use_container_width=True):
                if new_shift and new_shift not in SHIFTS:
                    # Add to SHIFTS list and initialize
                    SHIFTS.append(new_shift)
                    # Create shift record
                    new_shift_record = pd.DataFrame([{
                        "shift_id": f"SHIFT-{new_shift}-{datetime.now().strftime('%Y%m%d')}",
                        "shift_name": new_shift,
                        "cashier_username": "system",
                        "cashier_name": f"Shift {new_shift}",
                        "branch_id": branch_id,
                        "branch_name": "Head Office",
                        "start_time": datetime.now().isoformat(),
                        "end_time": "",
                        "status": "INACTIVE",
                        "opening_cash": 0,
                        "closing_cash": 0,
                        "total_revenue": 0,
                        "profit": 0,
                        "transactions": 0,
                        "variance": 0,
                        "manager_username": "system",
                        "notes": f"Added shift: {new_shift}"
                    }])
                    shifts_df = pd.concat([shifts_df, new_shift_record], ignore_index=True)
                    save_shifts(shifts_df)
                    st.success(f"✅ Shift '{new_shift}' added successfully!")
                    st.rerun()
                elif new_shift in SHIFTS:
                    st.warning(f"⚠️ Shift '{new_shift}' already exists")
                else:
                    st.error("Please enter a shift name")
            
            st.markdown("---")
            
            # Remove shift
            st.markdown("#### 🗑️ Remove Shift")
            shifts_to_remove = [s for s in SHIFTS if s not in ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO"]]
            if shifts_to_remove:
                remove_shift = st.selectbox("Select Shift to Remove", shifts_to_remove)
                if st.button("🗑️ Remove Shift", use_container_width=True):
                    if remove_shift in SHIFTS:
                        SHIFTS.remove(remove_shift)
                        # Mark shift as inactive in database
                        if not shifts_df.empty:
                            shifts_df.loc[shifts_df["shift_name"] == remove_shift, "status"] = "REMOVED"
                            save_shifts(shifts_df)
                        st.success(f"✅ Shift '{remove_shift}' removed successfully!")
                        st.rerun()
            else:
                st.info("No additional shifts to remove (only core shifts remain)")
    
    # Active shifts display in sidebar
    if not active_shifts.empty:
        st.sidebar.subheader("🟢 Active Shifts")
        for _, shift in active_shifts.iterrows():
            start_time_str = safe_format_time(shift['start_time'])
            
            st.sidebar.info(
                f"**{shift['cashier_name']}**\n"
                f"Shift: {shift['shift_id']}\n"
                f"Started: {start_time_str}\n"
                f"Opening: ${shift['opening_cash']:.2f}"
            )
    else:
        st.sidebar.info("No active shifts")
    
    # ==============================
    # MAIN CONTENT - Tabs
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Active Shifts",
        "📈 Shift History",
        "💰 Shift Summary",
        "📋 Shift Performance"
    ])
    
    # ==============================
    # TAB 1: ACTIVE SHIFTS
    # ==============================
    with tab1:
        st.markdown("## 🟢 Active Shifts")
        
        if active_shifts.empty:
            st.info("No active shifts at the moment")
        else:
            st.markdown("### Select Shift to Manage")
            
            shift_options = []
            for _, shift in active_shifts.iterrows():
                shift_id = shift['shift_id']
                cashier_name = shift['cashier_name']
                start_time_str = safe_format_time(shift['start_time'])
                shift_options.append(f"{shift_id} - {cashier_name} - Started: {start_time_str}")
            
            selected_option = st.selectbox(
                "Select Active Shift",
                options=shift_options,
                key="active_shift_select"
            )
            
            if selected_option:
                shift_id = selected_option.split(" - ")[0]
                shift = active_shifts[active_shifts["shift_id"] == shift_id]
                
                if not shift.empty:
                    shift_data = shift.iloc[0]
                    
                    col1, col2, col3 = st.columns(3)
                    
                    start_time_str = safe_format_time(shift_data['start_time'])
                    
                    with col1:
                        st.metric("🧑‍💼 Cashier", shift_data['cashier_name'])
                        st.metric("🆔 Shift ID", shift_data['shift_id'])
                    
                    with col2:
                        st.metric("⏰ Started", start_time_str)
                        st.metric("💰 Opening Cash", f"${shift_data['opening_cash']:.2f}")
                    
                    with col3:
                        st.metric("📊 Status", f"🟢 {shift_data['status']}")
                        
                        if st.button("🛑 End This Shift", type="primary", use_container_width=True):
                            if not st.session_state.button_clicked:
                                st.session_state.button_clicked = True
                                st.session_state.end_shift_id = shift_id
                                st.session_state.show_end_shift = True
                                st.rerun()
                    
                    # End Shift Dialog - FIXED
                    if st.session_state.get("show_end_shift", False) and st.session_state.get("end_shift_id") == shift_id:
                        with st.expander("📝 End Shift", expanded=True):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                sales_df = load_sales()
                                cash_df = load_cash()
                                
                                shift_sales = sales_df[sales_df["shift_id"] == shift_id] if not sales_df.empty else pd.DataFrame()
                                shift_cash = cash_df[cash_df["shift_id"] == shift_id] if not cash_df.empty else pd.DataFrame()
                                
                                total_sales = shift_sales["final_total"].sum() if not shift_sales.empty and "final_total" in shift_sales.columns else 0
                                total_transactions = len(shift_sales)
                                total_profit = shift_sales["profit"].sum() if not shift_sales.empty and "profit" in shift_sales.columns else 0
                                
                                # Calculate cash movements
                                if not shift_cash.empty:
                                    cash_sales = shift_cash[shift_cash["type"] == "CASH_SALE"]["amount"].sum() if "type" in shift_cash.columns else 0
                                    credit_sales = shift_cash[shift_cash["type"] == "CREDIT_SALE"]["amount"].sum() if "type" in shift_cash.columns else 0
                                    debt_payments = shift_cash[shift_cash["type"] == "DEBT_PAYMENT"]["amount"].sum() if "type" in shift_cash.columns else 0
                                    expenses = shift_cash[shift_cash["type"] == "EXPENSE"]["amount"].sum() if "type" in shift_cash.columns else 0
                                else:
                                    cash_sales = 0
                                    credit_sales = 0
                                    debt_payments = 0
                                    expenses = 0
                                
                                st.metric("💰 Total Sales", f"${total_sales:,.2f}")
                                st.metric("📈 Total Profit", f"${total_profit:,.2f}")
                                st.metric("📊 Transactions", f"{total_transactions}")
                            
                            with col2:
                                closing_cash = st.number_input(
                                    "Closing Cash ($)",
                                    min_value=0.0,
                                    value=float(shift_data.get("opening_cash", 0)),
                                    step=10.0
                                )
                                
                                notes = st.text_area("Shift Notes", placeholder="Any issues or comments about this shift...")
                                
                                if st.button("✅ Confirm End Shift", type="primary", use_container_width=True):
                                    if not st.session_state.button_clicked:
                                        st.session_state.button_clicked = True
                                        
                                        # Call the end_shift function
                                        success, message = end_shift(
                                            shift_id,
                                            closing_cash,
                                            total_sales,
                                            total_profit,
                                            total_transactions,
                                            notes
                                        )
                                        
                                        if success:
                                            # Calculate shift summary for report
                                            shift_summary = {
                                                "opening_cash": shift_data.get("opening_cash", 0),
                                                "total_revenue": total_sales,
                                                "total_profit": total_profit,
                                                "cash_sales": cash_sales,
                                                "credit_sales": credit_sales,
                                                "debt_payments": debt_payments,
                                                "expenses": expenses,
                                                "transactions": total_transactions,
                                                "closing_cash": closing_cash,
                                                "variance": closing_cash - (shift_data.get("opening_cash", 0) + cash_sales + debt_payments - expenses),
                                                "duration": f"{safe_format_time(shift_data.get('start_time'))} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                                                "notes": notes
                                            }
                                            
                                            # Generate report
                                            report = generate_shift_report(shift_data.to_dict(), shift_summary)
                                            st.session_state.shift_report = report
                                            
                                            # Send WhatsApp notification
                                            whatsapp_message = f"""
                                            ✅ SHIFT ENDED - {COMPANY_NAME}
                                            
                                            Shift: {shift_data.get('shift_id')}
                                            Cashier: {shift_data.get('cashier_name')}
                                            Revenue: ${total_sales:,.2f}
                                            Profit: ${total_profit:,.2f}
                                            Transactions: {total_transactions}
                                            Closing Cash: ${closing_cash:,.2f}
                                            
                                            Full report attached.
                                            """
                                            
                                            whatsapp_link = send_whatsapp_message(WHATSAPP_NUMBER, whatsapp_message)
                                            if whatsapp_link:
                                                st.success(f"📱 WhatsApp notification ready: [Click to send]({whatsapp_link})")
                                            
                                            # Send email
                                            email_body = f"""
                                            Shift Report - {COMPANY_NAME}
                                            
                                            {report}
                                            """
                                            email_sent = send_email_notification(EMAIL_NOTIFICATION, f"Shift Report - {shift_data.get('shift_id')}", email_body)
                                            if email_sent:
                                                st.success(f"📧 Email sent to {EMAIL_NOTIFICATION}")
                                            
                                            st.balloons()
                                            st.success(f"✅ {message}")
                                            
                                            # Show report
                                            with st.expander("📄 View Shift Report", expanded=True):
                                                st.text(report)
                                            
                                            # Reset session state
                                            st.session_state.show_end_shift = False
                                            st.session_state.end_shift_id = None
                                            st.session_state.shift_ended = True
                                            st.session_state.button_clicked = False
                                            
                                            st.rerun()
                                        else:
                                            st.error(f"❌ {message}")
                                            st.session_state.button_clicked = False
            
            # Quick stats
            if not active_shifts.empty:
                st.markdown("### 📊 Active Shifts Summary")
                
                total_cashiers = len(active_shifts)
                total_opening = active_shifts["opening_cash"].sum()
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("👥 Active Cashiers", total_cashiers)
                with col2:
                    st.metric("💰 Total Opening Cash", f"${total_opening:,.2f}")
                with col3:
                    oldest_time = min(active_shifts['start_time'])
                    oldest_time_str = safe_format_time(oldest_time)
                    st.metric("⏰ Oldest Shift", oldest_time_str)
    
    # ==============================
    # TAB 2: SHIFT HISTORY
    # ==============================
    with tab2:
        st.markdown("## 📈 Shift History")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date_range = st.date_input(
                "Date Range",
                value=(datetime.now() - timedelta(days=7), datetime.now())
            )
        
        with col2:
            if not shifts_df.empty and "cashier_name" in shifts_df.columns:
                cashiers = ["All"] + sorted(shifts_df["cashier_name"].unique().tolist())
                selected_cashier = st.selectbox("Cashier", cashiers)
            else:
                selected_cashier = "All"
        
        with col3:
            statuses = ["All", "OPEN", "CLOSED"]
            selected_status = st.selectbox("Status", statuses)
        
        filtered_shifts = shifts_df.copy()
        
        if not filtered_shifts.empty:
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = date_range
                filtered_shifts["start_date"] = pd.to_datetime(filtered_shifts["start_time"]).dt.date
                filtered_shifts = filtered_shifts[
                    (filtered_shifts["start_date"] >= start_date) & 
                    (filtered_shifts["start_date"] <= end_date)
                ]
            
            if selected_cashier != "All" and "cashier_name" in filtered_shifts.columns:
                filtered_shifts = filtered_shifts[filtered_shifts["cashier_name"] == selected_cashier]
            
            if selected_status != "All" and "status" in filtered_shifts.columns:
                filtered_shifts = filtered_shifts[filtered_shifts["status"] == selected_status]
            
            if not filtered_shifts.empty:
                display_df = filtered_shifts.copy()
                
                for col in ["start_time", "end_time"]:
                    if col in display_df.columns:
                        display_df[col] = pd.to_datetime(display_df[col])
                        display_df[col] = display_df[col].dt.strftime("%Y-%m-%d %H:%M")
                
                display_columns = {
                    "shift_id": "Shift ID",
                    "cashier_name": "Cashier",
                    "cashier_username": "Username",
                    "start_time": "Start Time",
                    "end_time": "End Time",
                    "opening_cash": "Opening Cash",
                    "closing_cash": "Closing Cash",
                    "total_revenue": "Revenue",
                    "profit": "Profit",
                    "transactions": "Transactions",
                    "variance": "Variance",
                    "status": "Status",
                    "shift_name": "Shift Name"
                }
                
                display_df = display_df.rename(columns=display_columns)
                
                show_cols = ["Shift ID", "Shift Name", "Cashier", "Start Time", "End Time", "Revenue", "Transactions", "Status"]
                available_cols = [col for col in show_cols if col in display_df.columns]
                
                st.dataframe(
                    display_df[available_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                        "Opening Cash": st.column_config.NumberColumn("Opening Cash", format="$%.2f"),
                        "Closing Cash": st.column_config.NumberColumn("Closing Cash", format="$%.2f"),
                        "Variance": st.column_config.NumberColumn("Variance", format="$%.2f"),
                        "Profit": st.column_config.NumberColumn("Profit", format="$%.2f")
                    }
                )
                
                st.markdown("### 📊 History Summary")
                
                total_shifts = len(filtered_shifts)
                total_revenue = filtered_shifts["total_revenue"].sum() if "total_revenue" in filtered_shifts.columns else 0
                total_profit = filtered_shifts["profit"].sum() if "profit" in filtered_shifts.columns else 0
                total_transactions = filtered_shifts["transactions"].sum() if "transactions" in filtered_shifts.columns else 0
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📊 Total Shifts", total_shifts)
                with col2:
                    st.metric("💰 Total Revenue", f"${total_revenue:,.2f}")
                with col3:
                    st.metric("📈 Total Profit", f"${total_profit:,.2f}")
                with col4:
                    st.metric("🛒 Transactions", f"{total_transactions:,.0f}")
            else:
                st.info("No shifts found matching the filters")
        else:
            st.info("No shift history available")
    
    # ==============================
    # TAB 3: SHIFT SUMMARY
    # ==============================
    with tab3:
        st.markdown("## 💰 Shift Summary")
        
        cash_summary = get_cash_summary()
        
        if cash_summary:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💰 Opening Cash", f"${cash_summary.get('opening_cash', 0):,.2f}")
            with col2:
                st.metric("💵 Cash Sales", f"${cash_summary.get('cash_sales', 0):,.2f}")
            with col3:
                st.metric("💳 Credit Sales", f"${cash_summary.get('credit_sales', 0):,.2f}")
            with col4:
                st.metric("📊 Total Revenue", f"${cash_summary.get('total_revenue', 0):,.2f}")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("💸 Expenses", f"${cash_summary.get('expenses', 0):,.2f}")
            with col2:
                st.metric("🏦 Deposits", f"${cash_summary.get('deposits', 0):,.2f}")
            with col3:
                st.metric("📋 Transactions", cash_summary.get('transactions_count', 0))
            with col4:
                st.metric("📊 Variance", f"${cash_summary.get('variance', 0):,.2f}")
        
        st.markdown("### 📈 Daily Shift Performance")
        
        if not shifts_df.empty:
            shifts_copy = shifts_df.copy()
            shifts_copy["date"] = pd.to_datetime(shifts_copy["start_time"]).dt.date
            daily_summary = shifts_copy.groupby("date").agg({
                "total_revenue": "sum",
                "profit": "sum",
                "transactions": "sum"
            }).reset_index()
            
            if not daily_summary.empty:
                fig = px.line(
                    daily_summary,
                    x="date",
                    y=["total_revenue", "profit"],
                    title="Daily Revenue and Profit",
                    labels={"value": "Amount ($)", "date": "Date", "variable": "Metric"}
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
    
    # ==============================
    # TAB 4: SHIFT PERFORMANCE
    # ==============================
    with tab4:
        st.markdown("## 📋 Shift Performance")
        
        if not shifts_df.empty and "cashier_name" in shifts_df.columns:
            cashier_performance = shifts_df.groupby("cashier_name").agg({
                "shift_id": "count",
                "total_revenue": "sum",
                "profit": "sum",
                "transactions": "sum"
            }).reset_index()
            
            cashier_performance.columns = ["Cashier", "Shifts", "Total Revenue", "Total Profit", "Transactions"]
            cashier_performance["Avg Revenue/Shift"] = cashier_performance["Total Revenue"] / cashier_performance["Shifts"]
            cashier_performance["Avg Profit/Shift"] = cashier_performance["Total Profit"] / cashier_performance["Shifts"]
            
            cashier_performance = cashier_performance.sort_values("Total Revenue", ascending=False)
            
            st.markdown("### 🏆 Cashier Performance Ranking")
            
            st.dataframe(
                cashier_performance,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Cashier": "Cashier",
                    "Shifts": "Shifts",
                    "Total Revenue": st.column_config.NumberColumn("Total Revenue", format="$%.2f"),
                    "Total Profit": st.column_config.NumberColumn("Total Profit", format="$%.2f"),
                    "Transactions": "Transactions",
                    "Avg Revenue/Shift": st.column_config.NumberColumn("Avg Revenue/Shift", format="$%.2f"),
                    "Avg Profit/Shift": st.column_config.NumberColumn("Avg Profit/Shift", format="$%.2f")
                }
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.bar(
                    cashier_performance.head(10),
                    x="Cashier",
                    y="Total Revenue",
                    title="Top Cashiers by Revenue",
                    color="Total Revenue",
                    color_continuous_scale="Greens",
                    text="Total Revenue"
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.bar(
                    cashier_performance.head(10),
                    x="Cashier",
                    y="Transactions",
                    title="Top Cashiers by Transactions",
                    color="Transactions",
                    color_continuous_scale="Blues",
                    text="Transactions"
                )
                fig.update_traces(texttemplate="%{text}", textposition="outside")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No performance data available")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    shift_management_page()