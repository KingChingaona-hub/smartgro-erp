import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import json
import zipfile
import shutil
from pathlib import Path
import platform
import sys

# ==============================
# EMAIL REPORTS IMPORT
# ==============================
from backend.integrations.email_reports import (
    get_email_config, 
    save_email_config, 
    send_daily_report, 
    send_weekly_report, 
    send_low_stock_alert,
    test_email_connection,
    send_test_email
)

# ==============================
# DATABASE IMPORTS
# ==============================
from backend.core.db_adapter import (
    load_products, 
    load_sales, 
    load_customers, 
    load_branches,
    load_debtors,
    load_expenses,
    load_purchases,
    save_sales,
    init_data_folder,
    load_users
)

# ==============================
# SYSTEM CONSTANTS
# ==============================
SYSTEM_NAME = "SmartGro ERP System"
SYSTEM_VERSION = "3.0 (Zimbabwe Edition)"
FOUNDER = "King T Chingaona"
CO_DEVELOPER = "Walker Takaendesa"
RELEASE_DATE = "June 2026"
TARGET_MARKET = "Zimbabwe Retail Businesses"
COMPANY_NAME = "Aziel Investments"
COMPANY_ADDRESS = "Retreat Park, Harare, Zimbabwe"
COMPANY_PHONE = "+263 78 290 5853"
COMPANY_EMAIL = "info@azielinvestments.co.zw"


# ==============================
# SESSION STATE INIT
# ==============================
def init_settings_session():
    if "settings_initialized" not in st.session_state:
        st.session_state.settings_initialized = True
        st.session_state.settings_message = ""
        st.session_state.settings_message_type = ""
        st.session_state.settings_force_refresh = False
        st.session_state.settings_backup_created = False
        st.session_state.settings_export_done = False


# ==============================
# LOAD SETTINGS
# ==============================
def load_settings():
    """Load settings from file"""
    settings_file = Path("data/system_settings.json")
    if settings_file.exists():
        try:
            with open(settings_file, "r") as f:
                return json.load(f)
        except:
            return get_default_settings()
    return get_default_settings()


def get_default_settings():
    """Get default settings"""
    return {
        "store_name": "Aziel Investments",
        "store_phone": "+263 78 290 5853/ 0776067967",
        "store_email": "info@azielinvestments.co.zw",
        "store_address": "Retreat Park, Harare, Zimbabwe",
        "tax_rate": 15,
        "currency": "ZWL",
        "receipt_footer": "Thank you for shopping with us!",
        "system_name": SYSTEM_NAME,
        "system_version": SYSTEM_VERSION,
        "auto_backup": False,
        "backup_frequency": "daily",
        "data_retention_days": 90,
        "enable_ai_advisor": True,
        "enable_whatsapp_integration": True,
        "whatsapp_number": "+263 78 290 5853",
        "enable_sms": False,
        "sms_provider": "africastalking",
        "date_format": "YYYY-MM-DD",
        "time_format": "24h"
    }


def save_settings(settings):
    """Save settings to file"""
    settings_file = Path("data/system_settings.json")
    settings_file.parent.mkdir(exist_ok=True)
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)
    return True


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
# SYSTEM MANUAL
# ==============================
def get_system_manual():
    """Return the complete system manual"""
    
    now = datetime.now()
    current_date = now.strftime('%B %d, %Y')
    
    manual = f"""
{'='*70}
                    AZIEL INVESTMENTS - SMARTGRO ERP SYSTEM
                    COMPLETE USER MANUAL
{'='*70}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                        SYSTEM OVERVIEW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SmartGro is a comprehensive Enterprise Resource Planning (ERP) system designed 
specifically for retail businesses in Zimbabwe. The system provides complete 
management of sales, inventory, customers, debtors, expenses, and multi-branch 
operations.

┌─────────────────────────────────────────────────────────────────────────────┐
│  DEVELOPER INFORMATION                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Founder & Lead Developer:  King T Chingaona                                │
│  Co-Developer:              Walker Takaendesa                               │
│  System Name:               SmartGro ERP System                              │
│  Version:                   3.0 (Zimbabwe Edition)                           │
│  Release Date:              June 2026                                        │
│  Target Market:             Zimbabwe Retail Businesses                       │
└─────────────────────────────────────────────────────────────────────────────┘

Key Features:
• Multi-branch support (Head Office, National, Provincial, District, Village)
• Role-based access control (Owner, Manager, Cashier)
• Point of Sale (POS) with receipt printing
• Inventory management with stock alerts
• Customer database and loyalty points
• Debtors management with credit scoring
• Expense and income tracking
• Profit & Loss reporting
• Business intelligence and AI advisor
• Multi-currency support (ZWL, USD, ZiG, RAND)
• WhatsApp integration for receipts
• Email reporting system
• Automated SMS notifications
• Voice command support
• Mobile-responsive interface

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    SYSTEM REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Hardware Requirements:
• Processor: Intel Core i3 or equivalent
• RAM: 4GB minimum (8GB recommended)
• Storage: 500MB free space
• Internet: Required for email reports and initial setup
• Barcode Scanner: USB compatible (optional)
• Printer: Any printer for receipts

Software Requirements:
• Operating System: Windows 10/11, macOS, or Linux
• Python 3.8 or higher
• Web Browser: Chrome, Firefox, or Edge

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    INSTALLATION GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Install Python
• Download Python from python.org (version 3.8 or higher)
• During installation, check "Add Python to PATH"
• Verify installation: Open Command Prompt and type "python --version"

Step 2: Install Required Libraries
Open Command Prompt/Terminal and run:

    pip install streamlit pandas numpy plotly scikit-learn reportlab

Step 3: Download SmartGro System
• Download the SmartGro_System folder to your computer
• Ensure all files are in the correct directory structure

Step 4: Run the System
Navigate to the SmartGro_System folder and run:

    streamlit run app.py

Step 5: Access the System
• Open your web browser
• Go to: https://smartgro.streamlit.app/
• Login using the provided credentials

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    LOGIN & ACCESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Branch Selection:
┌─────────┬─────────────────────┬──────────┬───────────────┐
│ Branch  │ Code                │ Password │ Level         │
├─────────┼─────────────────────┼──────────┼───────────────┤
│ Head Office    │ HO               │ ho123    │ 1             │
│ National       │ NAT              │ nat123   │ 2             │
│ Provincial     │ PRO              │ pro123   │ 3             │
│ District       │ DIS              │ dis123   │ 4             │
│ Village        │ VIL              │ vil123   │ 5             │
└─────────┴─────────────────────┴──────────┴───────────────┘

User Login Credentials:
┌─────────────┬──────────────┬─────────────────────────────────┐
│ Username    │ Password     │ Role                            │
├─────────────┼──────────────┼─────────────────────────────────┤
│ admin       │ admin123     │ Owner (Full System Access)      │
│ manager     │ manager123   │ Manager (Operations Access)     │
│ cashier     │ cash123      │ Cashier (POS Only)              │
└─────────────┴──────────────┴─────────────────────────────────┘

Login Process:
1. Select your branch from the branch selection screen
2. Enter the branch password
3. Enter your username and password
4. Click "Login" to access the system

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    EMAIL REPORTING SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

To enable email reports:

For Gmail Users:
1. Enable 2-Factor Authentication on your Google Account
2. Go to myaccount.google.com/apppasswords
3. Generate an App Password for "Mail"
4. Copy the 16-character password
5. In SmartGro Settings → Email Reports:
   - SMTP Server: smtp.gmail.com
   - Port: 587
   - Sender Email: your-email@gmail.com
   - App Password: paste the 16-character password
6. Add recipient emails (one per line)
7. Click "Test Email Connection" then "Send Test Email"

For Other Email Providers:
• Outlook/Hotmail: smtp-mail.outlook.com, port 587
• Yahoo: smtp.mail.yahoo.com, port 587
• Zimbra/Corporate: Ask your IT department for SMTP settings

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    MODULE GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. STOCK DASHBOARD - View inventory overview and stock health
2. INVENTORY - Add, edit, delete products
3. POINT OF SALE (POS) - Process customer sales
4. SALES HISTORY - View all completed sales
5. SALES DASHBOARD - Analyze sales performance
6. CASH DASHBOARD - Manage cash register and shifts
7. PURCHASES - Manage supplier purchases
8. EXPENSES - Track business expenses
9. INCOME - Track non-sales income
10. P&L DASHBOARD - Profit & Loss reporting
11. CUSTOMERS - Manage customer database
12. DEBTORS - Manage customer credit
13. BUSINESS ADVISOR - AI-powered insights
14. REPORTS - Generate business reports
15. BRANCH MANAGEMENT - Manage multi-branch operations
16. SHIFT MANAGEMENT - Manage cashier shifts
17. USER MANAGEMENT - Manage system users
18. SETTINGS - System configuration

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    QUICK START GUIDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For Cashiers:
1. Manager must start a shift for you
2. Login with your cashier credentials
3. Go to POS module
4. Search/add products to cart
5. Process payment
6. Print receipt

For Managers:
1. Login with manager credentials
2. Start shifts for cashiers
3. Monitor inventory levels
4. Review sales reports
5. Manage customers and debtors
6. Process purchases and expenses

For Owners:
1. Login with admin credentials
2. Manage users and branches
3. View all business reports
4. Analyze P&L statements
5. Review business advisor insights
6. Export all data for accounting

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Issue: Cannot login
Solution: 
• Verify branch selection is correct
• Check username and password
• Ensure branch is active
• Contact system administrator

Issue: Products not saving
Solution:
• Refresh the page
• Check file permissions
• Clear browser cache
• Restart the application

Issue: Receipt not printing
Solution:
• Check printer connection
• Use PDF download as alternative
• Try printing from browser
• Check receipt paper

Issue: Emails not sending
Solution:
• Verify email settings in Settings → Email Reports
• Test connection using "Test Email Connection" button
• For Gmail, ensure using App Password (not regular password)
• Check spam folder
• Verify recipient emails are correct

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    SUPPORT & CONTACT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Developer:          King T Chingaona, Walker Takaendesa
System Name:        SmartGro ERP System
Version:            3.0 (Zimbabwe Edition)
Email Support:      aziel@investments.co.zw
Phone Support:      +263 78 290 5853
Website:            www.azielinvestments.co.zw

Office Address:
Aziel Investments
Retreat Park, Harare
Zimbabwe

Support Hours:
Monday - Friday: 7:00 AM - 8:00 PM
Saturday: 9:00 AM - 1:00 PM
Sunday: Closed

Emergency Support: +263 78 290 5853 / 0776067967

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    LICENSE & COPYRIGHT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SmartGro ERP System
Copyright © 2026 Aziel Investments

All rights reserved. This software is proprietary and confidential.
Unauthorized copying, distribution, or modification is strictly prohibited.

For licensing inquiries, please contact: aziel@investments.co.zw

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ACKNOWLEDGMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Special thanks to:
• The entire Aziel Investments team
• Beta testers who provided valuable feedback
• All branch managers and cashiers for their input
• The Zimbabwe business community for inspiration

Technology Stack:
• Streamlit - Web Framework
• Pandas - Data Management
• Plotly - Data Visualization
• Scikit-learn - Machine Learning
• ReportLab - PDF Generation

This manual was last updated on: {current_date}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    END OF MANUAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SmartGro ERP System - Empowering Zimbabwean Retail Businesses
Developed with ❤️ by King T Chingaona & Walker Takaendesa

{'='*70}
"""
    
    return manual


# ==============================
# BACKUP FUNCTIONS
# ==============================
def create_backup():
    """Create a backup zip file of all data"""
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    
    backup_file = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    
    with zipfile.ZipFile(backup_file, 'w') as zipf:
        data_dir = Path("data")
        branch_dir = Path("branch_data")
        
        if data_dir.exists():
            for file in data_dir.glob("*.csv"):
                zipf.write(file, f"data/{file.name}")
            for file in data_dir.glob("*.json"):
                zipf.write(file, f"data/{file.name}")
        
        if branch_dir.exists():
            for branch in branch_dir.iterdir():
                if branch.is_dir():
                    for file in branch.glob("*.csv"):
                        zipf.write(file, f"branch_data/{branch.name}/{file.name}")
    
    return backup_file


def restore_backup(zip_file):
    """Restore data from backup zip file"""
    extract_path = Path("temp_restore")
    
    with zipfile.ZipFile(zip_file, 'r') as zipf:
        zipf.extractall(extract_path)
    
    if (extract_path / "data").exists():
        shutil.copytree(extract_path / "data", "data", dirs_exist_ok=True)
    
    if (extract_path / "branch_data").exists():
        shutil.copytree(extract_path / "branch_data", "branch_data", dirs_exist_ok=True)
    
    shutil.rmtree(extract_path)
    return True


# ==============================
# MAIN SETTINGS PAGE
# ==============================
def settings_page():
    """Settings Page with complete configuration"""
    
    init_settings_session()
    
    st.title("System Settings")
    st.caption(f"Configure {SYSTEM_NAME} - Version {SYSTEM_VERSION}")
    
    # Security check - only owner can access
    if st.session_state.get("role") != "owner":
        st.error("Access Denied. Only system owner can access settings.")
        return
    
    # Load current settings
    settings = load_settings()
    
    # ==============================
    # TABS FOR DIFFERENT SETTINGS
    # ==============================
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "User Manual",
        "Store Settings",
        "Email Reports",
        "Backup & Restore",
        "System Info",
        "Data Management",
        "Advanced"
    ])
    
    # ==============================
    # TAB 1: USER MANUAL
    # ==============================
    with tab1:
        st.markdown("## System User Manual")
        st.caption(f"Complete documentation for {SYSTEM_NAME}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### Manual Contents
            
            - System Overview
            - Installation Guide
            - Email Reporting Setup
            - Login & Access
            - User Roles & Permissions
            - Module Guide (All Modules)
            - Quick Start Guide
            - Troubleshooting
            - Support & Contact
            - License Information
            
            **Founder:** King T Chingaona
            **Co-Developer:** Walker Takaendesa
            **Version:** 3.0 (Zimbabwe Edition)
            """)
            
            st.info("""
            **System Information:**
            - Target Market: Zimbabwe Retail Businesses
            - Support Hours: Mon-Fri 7AM-8PM
            - Emergency: +263 78 290 5853
            """)
        
        with col2:
            st.markdown("""
            ### Download Options
            
            Choose your preferred format:
            
            - **TXT Format** - Plain text, works everywhere
            """)
            
            manual_text = get_system_manual()
            current_date = datetime.now().strftime('%Y%m%d')
            
            st.download_button(
                label="Download TXT Manual",
                data=manual_text,
                file_name=f"SmartGro_Manual_{current_date}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
            st.info("Tip: The manual includes complete system documentation, installation guide, and troubleshooting tips.")
        
        st.markdown("---")
        
        # Quick links
        st.markdown("### Quick Links")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("[Email Setup](#email-reports)")
        with col2:
            st.markdown("[Login Guide](#login-access)")
        with col3:
            st.markdown("[Troubleshooting](#troubleshooting)")
        with col4:
            st.markdown("[Support](#support-contact)")
        
        # Preview manual
        with st.expander("Preview Manual (Click to expand)"):
            st.text_area("Manual Preview", manual_text[:3000], height=400)
    
    # ==============================
    # TAB 2: STORE SETTINGS
    # ==============================
    with tab2:
        st.markdown("## Store Information")
        st.caption("Configure your store details for receipts, invoices, and reports")
        
        col1, col2 = st.columns(2)
        
        with col1:
            store_name = st.text_input("Store Name *", value=settings.get("store_name", "Aziel Investments"))
            store_phone = st.text_input("Store Phone *", value=settings.get("store_phone", "+263 78 290 5853/ 0776067967"))
            store_email = st.text_input("Store Email *", value=settings.get("store_email", "info@azielinvestments.co.zw"))
        
        with col2:
            currency = st.selectbox("Default Currency", ["ZWL", "USD", "ZiG", "RAND"], 
                                   index=["ZWL", "USD", "ZiG", "RAND"].index(settings.get("currency", "ZWL")))
            tax_rate = st.number_input("Default Tax Rate (%)", min_value=0.0, max_value=100.0, 
                                      value=float(settings.get("tax_rate", 15)))
            date_format = st.selectbox("Date Format", ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"], 
                                      index=["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"].index(settings.get("date_format", "YYYY-MM-DD")))
        
        store_address = st.text_area("Store Address", value=settings.get("store_address", "Retreat Park, Harare, Zimbabwe"))
        receipt_footer = st.text_input("Receipt Footer Message", value=settings.get("receipt_footer", "Thank you for shopping with us!"))
        
        col1, col2 = st.columns(2)
        with col1:
            enable_whatsapp = st.checkbox("Enable WhatsApp Integration", value=settings.get("enable_whatsapp_integration", True))
            if enable_whatsapp:
                whatsapp_number = st.text_input("WhatsApp Number", value=settings.get("whatsapp_number", "+263 78 290 5853"))
        
        with col2:
            enable_sms = st.checkbox("Enable SMS Notifications", value=settings.get("enable_sms", False))
            if enable_sms:
                sms_provider = st.selectbox("SMS Provider", ["africastalking", "twilio", "semaphore"],
                                           index=["africastalking", "twilio", "semaphore"].index(settings.get("sms_provider", "africastalking")))
        
        if st.button("Save Store Settings", type="primary", use_container_width=True):
            settings["store_name"] = store_name
            settings["store_phone"] = store_phone
            settings["store_email"] = store_email
            settings["store_address"] = store_address
            settings["currency"] = currency
            settings["tax_rate"] = tax_rate
            settings["receipt_footer"] = receipt_footer
            settings["date_format"] = date_format
            settings["enable_whatsapp_integration"] = enable_whatsapp
            if enable_whatsapp:
                settings["whatsapp_number"] = whatsapp_number
            settings["enable_sms"] = enable_sms
            if enable_sms:
                settings["sms_provider"] = sms_provider
            
            if save_settings(settings):
                st.success("Store settings saved successfully!")
                show_toast("Store settings updated!", "success")
                st.rerun()
    
    # ==============================
    # TAB 3: EMAIL REPORTS
    # ==============================
    with tab3:
        st.markdown("## Email Reports Configuration")
        st.caption("Configure email settings for automated reports")
        
        email_config = get_email_config()
        
        # Test connection row
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔌 Test Email Connection", use_container_width=True):
                with st.spinner("Testing connection..."):
                    success, message = test_email_connection()
                    if success:
                        st.success(f"{message}")
                    else:
                        st.error(f"{message}")
                        st.info("For Gmail: You need to use an App Password. Go to Google Account → Security → App Passwords.")
        
        with col2:
            if st.button("Send Test Email", use_container_width=True):
                with st.spinner("Sending test email..."):
                    success, message = send_test_email()
                    if success:
                        st.success(f"{message}")
                    else:
                        st.error(f"{message}")
        
        st.markdown("---")
        
        st.markdown("### SMTP Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            smtp_server = st.text_input("SMTP Server", value=email_config.get("smtp_server", "smtp.gmail.com"), key="email_smtp_server")
            smtp_port = st.number_input("SMTP Port", value=email_config.get("smtp_port", 587), step=1, key="email_smtp_port")
            sender_email = st.text_input("Sender Email", value=email_config.get("sender_email", ""), placeholder="your-email@gmail.com", key="email_sender")
        
        with col2:
            sender_password = st.text_input("App Password", type="password", value=email_config.get("sender_password", ""), 
                                            placeholder="16-character app password", key="email_password")
            st.caption("**Gmail users:** Generate an App Password at myaccount.google.com/apppasswords")
            st.caption("**Other providers:** Use your regular password or SMTP password")
        
        st.markdown("### Recipients")
        
        recipients_text = st.text_area("Recipient Emails (one per line)", 
                                       value="\n".join(email_config.get("recipient_emails", [])),
                                       height=100,
                                       placeholder="manager@example.com\nowner@example.com\naccountant@example.com",
                                       key="email_recipients")
        
        st.markdown("### Report Schedule")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enable_daily = st.checkbox("Enable Daily Sales Report", value=email_config.get("enable_daily_report", False), key="email_enable_daily")
            if enable_daily:
                st.info("Daily report will be sent at end of each day")
        
        with col2:
            enable_weekly = st.checkbox("Enable Weekly Sales Report", value=email_config.get("enable_weekly_report", False), key="email_enable_weekly")
            if enable_weekly:
                st.info("Weekly report will be sent every Sunday")
        
        enable_low_stock = st.checkbox("Enable Low Stock Alerts", value=email_config.get("enable_low_stock_alert", False), key="email_enable_low_stock")
        if enable_low_stock:
            st.info("Low stock alerts sent when inventory falls below reorder levels")
        
        if st.button("Save Email Settings", type="primary", use_container_width=True):
            recipients = [r.strip() for r in recipients_text.split("\n") if r.strip()]
            
            new_config = {
                "smtp_server": smtp_server,
                "smtp_port": smtp_port,
                "sender_email": sender_email,
                "sender_password": sender_password,
                "recipient_emails": recipients,
                "enable_daily_report": enable_daily,
                "enable_weekly_report": enable_weekly,
                "enable_low_stock_alert": enable_low_stock
            }
            if save_email_config(new_config):
                st.success("Email settings saved successfully!")
            else:
                st.error("Failed to save email settings")
        
        st.markdown("---")
        
        st.markdown("### Manual Send")
        st.caption("Send reports immediately regardless of schedule")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Send Daily Report Now", use_container_width=True):
                with st.spinner("Sending daily report..."):
                    success, message = send_daily_report()
                    if success:
                        st.success(f"{message}")
                    else:
                        st.error(f"{message}")
        
        with col2:
            if st.button("Send Weekly Report Now", use_container_width=True):
                with st.spinner("Sending weekly report..."):
                    success, message = send_weekly_report()
                    if success:
                        st.success(f"{message}")
                    else:
                        st.error(f"{message}")
        
        with col3:
            if st.button("Send Low Stock Alert", use_container_width=True):
                with st.spinner("Checking stock and sending..."):
                    success, message = send_low_stock_alert()
                    if success:
                        st.success(f"{message}")
                    else:
                        st.error(f"{message}")
        
        st.markdown("---")
        
        with st.expander("Why aren't emails sending? Click for help"):
            st.markdown("""
            **Common Issues and Solutions:**
            
            | Issue | Solution |
            |-------|----------|
            | **Gmail authentication fails** | Use an App Password (16 characters). Regular password won't work. |
            | **Connection timeout** | Check firewall settings. Port 587 must be open. |
            | **No recipients configured** | Add recipient emails in the field above. |
            | **Emails going to spam** | Check spam folder. Add sender to contacts. |
            | **Invalid SMTP settings** | Use correct server: smtp.gmail.com for Gmail |
            
            **For Gmail Users:**
            1. Enable 2-Factor Authentication on your Google Account
            2. Go to myaccount.google.com/apppasswords
            3. Select "Mail" as the app
            4. Copy the 16-character password
            5. Paste it in the App Password field above
            
            **For Other Email Providers:**
            - **Outlook/Hotmail:** smtp-mail.outlook.com, port 587
            - **Yahoo:** smtp.mail.yahoo.com, port 587
            - **Zimbra/Corporate:** Ask your IT department for SMTP settings
            """)
    
    # ==============================
    # TAB 4: BACKUP & RESTORE
    # ==============================
    with tab4:
        st.markdown("## Backup & Restore")
        st.caption("Protect your data with automatic and manual backups")
        
        st.warning("Regular backups are recommended to prevent data loss")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Manual Backup")
            if st.button("Create Backup Now", use_container_width=True):
                with st.spinner("Creating backup..."):
                    backup_file = create_backup()
                    st.success(f"Backup created successfully!")
                    
                    with open(backup_file, "rb") as f:
                        st.download_button(
                            label="Download Backup",
                            data=f,
                            file_name=backup_file.name,
                            mime="application/zip",
                            use_container_width=True
                        )
                    st.session_state.settings_backup_created = True
        
        with col2:
            st.markdown("### Restore Backup")
            uploaded_file = st.file_uploader("Restore from Backup", type=["zip"])
            if uploaded_file is not None:
                st.warning("Restoring will overwrite current data!")
                confirm = st.checkbox("I understand this will replace all current data")
                if confirm and st.button("Restore Backup", use_container_width=True):
                    with st.spinner("Restoring backup..."):
                        temp_zip = Path("temp_restore.zip")
                        with open(temp_zip, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        restore_backup(temp_zip)
                        temp_zip.unlink()
                        
                        st.success("Backup restored successfully! Please restart the application.")
        
        st.markdown("---")
        
        st.markdown("### Auto Backup Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            auto_backup = st.checkbox("Enable Auto Backup", value=settings.get("auto_backup", False))
            if auto_backup:
                backup_frequency = st.selectbox("Backup Frequency", ["daily", "weekly", "monthly"],
                                               index=["daily", "weekly", "monthly"].index(settings.get("backup_frequency", "daily")))
        
        with col2:
            data_retention = st.number_input("Data Retention (days)", min_value=30, max_value=365, 
                                            value=settings.get("data_retention_days", 90))
        
        if auto_backup:
            st.info(f"Auto backup will run {backup_frequency} and keep {data_retention} days of data")
        
        # List existing backups
        st.markdown("### Existing Backups")
        
        backup_dir = Path("backups")
        if backup_dir.exists():
            backups = sorted(backup_dir.glob("backup_*.zip"), reverse=True)
            if backups:
                backup_data = []
                for backup in backups[:10]:
                    size = backup.stat().st_size / (1024 * 1024)
                    backup_data.append({
                        "File": backup.name,
                        "Date": datetime.fromtimestamp(backup.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        "Size": f"{size:.2f} MB"
                    })
                st.dataframe(pd.DataFrame(backup_data), use_container_width=True, hide_index=True)
            else:
                st.info("No backups found")
        else:
            st.info("No backups found")
    
    # ==============================
    # TAB 5: SYSTEM INFO
    # ==============================
    with tab5:
        st.markdown("## System Information")
        st.caption(f"Details about {SYSTEM_NAME}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### System Details")
            st.write(f"**System Name:** {SYSTEM_NAME}")
            st.write(f"**Version:** {SYSTEM_VERSION}")
            st.write(f"**Founder:** {FOUNDER}")
            st.write(f"**Co-Developer:** {CO_DEVELOPER}")
            st.write(f"**Release Date:** {RELEASE_DATE}")
            st.write(f"**Framework:** Streamlit")
            st.write(f"**Python Version:** {sys.version[:10]}")
            st.write(f"**OS:** {platform.system()} {platform.release()}")
        
        with col2:
            st.markdown("### Database Stats")
            
            try:
                products = load_products()
                sales = load_sales()
                customers = load_customers()
                branches = load_branches()
                debtors = load_debtors()
                expenses = load_expenses()
                users = load_users()
                
                total_sales_value = sales["total"].sum() if not sales.empty and "total" in sales.columns else 0
                total_profit = sales["profit"].sum() if not sales.empty and "profit" in sales.columns else 0
                total_debt = debtors["balance"].sum() if not debtors.empty and "balance" in debtors.columns else 0
                total_expenses = expenses["amount"].sum() if not expenses.empty and "amount" in expenses.columns else 0
                
                st.write(f"**Total Products:** {len(products)}")
                st.write(f"**Total Sales:** {len(sales)}")
                st.write(f"**Total Revenue:** ${total_sales_value:,.2f}")
                st.write(f"**Total Profit:** ${total_profit:,.2f}")
                st.write(f"**Total Customers:** {len(customers)}")
                st.write(f"**Total Branches:** {len(branches)}")
                st.write(f"**Total Users:** {len(users)}")
                st.write(f"**Total Debt:** ${total_debt:,.2f}")
                st.write(f"**Total Expenses:** ${total_expenses:,.2f}")
            except Exception as e:
                st.warning(f"Could not load all statistics: {str(e)}")
        
        st.markdown("---")
        
        st.markdown("### Developer Information")
        st.markdown(f"""
        | Detail | Information |
        |--------|-------------|
        | **Founder & Lead Developer** | {FOUNDER} |
        | **Co-Developer** | {CO_DEVELOPER} |
        | **Company** | {COMPANY_NAME} |
        | **Location** | {COMPANY_ADDRESS} |
        | **Contact** | {COMPANY_PHONE} |
        | **Email** | {COMPANY_EMAIL} |
        """)
        
        st.markdown("---")
        
        st.markdown("### License Information")
        st.markdown("""
        **SmartGro ERP System**  
        Copyright © 2026 Aziel Investments  
        
        All rights reserved. This software is proprietary and confidential.
        Unauthorized copying, distribution, or modification is strictly prohibited.
        
        **Commercial License:** For commercial use, please contact Aziel Investments.
        **Open Source:** Not open source. All rights reserved.
        """)
        
        st.markdown("---")
        
        st.markdown("### Technology Stack")
        st.markdown("""
        | Component | Technology |
        |-----------|------------|
        | **Frontend** | Streamlit |
        | **Data Management** | Pandas, NumPy |
        | **Visualization** | Plotly, Matplotlib |
        | **Machine Learning** | Scikit-learn |
        | **PDF Generation** | ReportLab |
        | **Email** | SMTP (Gmail/Outlook) |
        | **SMS** | Africa's Talking, Twilio |
        | **Database** | CSV/JSON (File-based) |
        | **Deployment** | Streamlit Cloud |
        """)
        
        # Clear cache button
        if st.button("Clear System Cache", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache cleared! Refresh the page.")
    
    # ==============================
    # TAB 6: DATA MANAGEMENT
    # ==============================
    with tab6:
        st.markdown("## Data Management")
        st.caption("Clean up old data and manage system storage")
        
        st.warning("These actions can permanently delete data. Use with caution.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Clear Old Sales Data")
            days_to_keep = st.number_input("Keep data from last (days)", min_value=30, max_value=365, value=settings.get("data_retention_days", 90))
            
            if st.button("Clear Old Sales", use_container_width=True):
                confirm = st.checkbox("I understand this will delete old sales records permanently")
                if confirm:
                    sales_df = load_sales()
                    if not sales_df.empty and "date" in sales_df.columns:
                        sales_df["date"] = pd.to_datetime(sales_df["date"])
                        cutoff = datetime.now() - timedelta(days=days_to_keep)
                        filtered_df = sales_df[sales_df["date"] >= cutoff]
                        save_sales(filtered_df)
                        st.success(f"Removed records older than {days_to_keep} days. {len(filtered_df)} records remaining.")
        
        with col2:
            st.markdown("### Export All Data")
            
            if st.button("Export All Data (CSV)", use_container_width=True):
                import zipfile
                from io import BytesIO
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                    products_df = load_products()
                    sales_df = load_sales()
                    customers_df = load_customers()
                    debtors_df = load_debtors()
                    expenses_df = load_expenses()
                    purchases_df = load_purchases()
                    
                    for name, df in [("products", products_df), ("sales", sales_df), 
                                    ("customers", customers_df), ("debtors", debtors_df),
                                    ("expenses", expenses_df), ("purchases", purchases_df)]:
                        if not df.empty:
                            csv_data = df.to_csv(index=False).encode('utf-8')
                            zipf.writestr(f"{name}_{datetime.now().strftime('%Y%m%d')}.csv", csv_data)
                    
                    # Also export settings
                    settings_json = json.dumps(load_settings(), indent=2).encode('utf-8')
                    zipf.writestr(f"settings_{datetime.now().strftime('%Y%m%d')}.json", settings_json)
                
                zip_buffer.seek(0)
                st.download_button(
                    label="Download All Data (ZIP)",
                    data=zip_buffer,
                    file_name=f"all_data_export_{datetime.now().strftime('%Y%m%d')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
                st.session_state.settings_export_done = True
        
        st.markdown("---")
        
        st.markdown("### Clear Cache Files")
        if st.button("Clear All Cache Files", use_container_width=True):
            import shutil
            cache_dir = Path("__pycache__")
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
                st.success("Cache files cleared!")
            else:
                st.info("No cache files found.")
        
        st.markdown("---")
        
        st.markdown("### Reset System")
        st.error("This will delete ALL data and reset the system to factory defaults!")
        
        confirm_reset = st.checkbox("I understand this will delete ALL data. This action CANNOT be undone.")
        reset_password = st.text_input("Type 'RESET' to confirm", type="password")
        
        if confirm_reset and reset_password == "RESET":
            if st.button("RESET SYSTEM", use_container_width=True):
                # Backup before reset
                backup_file = create_backup()
                st.info(f"Backup created at: {backup_file}")
                
                # Reset data files
                data_dir = Path("data")
                branch_dir = Path("branch_data")
                
                if data_dir.exists():
                    for file in data_dir.glob("*.csv"):
                        file.unlink()
                    for file in data_dir.glob("*.json"):
                        file.unlink()
                
                if branch_dir.exists():
                    shutil.rmtree(branch_dir)
                    branch_dir.mkdir()
                
                init_data_folder()
                
                st.success("System reset to factory defaults! Please restart the application.")
                st.warning("Your backup file has been saved. You can restore it from Backup & Restore tab.")
    
    # ==============================
    # TAB 7: ADVANCED
    # ==============================
    with tab7:
        st.markdown("## Advanced Settings")
        st.caption("Configure advanced system features")
        
        st.markdown("### AI & Intelligence")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enable_ai_advisor = st.checkbox("Enable AI Business Advisor", value=settings.get("enable_ai_advisor", True))
            if enable_ai_advisor:
                st.info("AI advisor provides intelligent business insights and recommendations")
        
        with col2:
            enable_voice = st.checkbox("Enable Voice Commands", value=settings.get("enable_voice", False))
            if enable_voice:
                st.info("Voice commands allow hands-free operation of the system")
        
        st.markdown("### Branch Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_branch = st.selectbox("Default Branch", ["HO", "NAT", "PRO", "DIS", "VIL"],
                                         index=["HO", "NAT", "PRO", "DIS", "VIL"].index(settings.get("default_branch", "HO")))
        
        with col2:
            branch_auto_sync = st.checkbox("Auto-sync Products Across Branches", value=settings.get("branch_auto_sync", False))
            if branch_auto_sync:
                st.info("Products will be automatically synced to all branches")
        
        st.markdown("### Security")
        
        col1, col2 = st.columns(2)
        
        with col1:
            session_timeout = st.number_input("Session Timeout (minutes)", min_value=5, max_value=120, 
                                             value=settings.get("session_timeout", 30))
        
        with col2:
            max_login_attempts = st.number_input("Max Login Attempts", min_value=3, max_value=10, 
                                                value=settings.get("max_login_attempts", 5))
        
        st.markdown("### Integration Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enable_api = st.checkbox("Enable API Access", value=settings.get("enable_api", False))
            if enable_api:
                api_key = st.text_input("API Key", value=settings.get("api_key", ""), type="password")
                st.info("API access allows external applications to connect")
        
        with col2:
            enable_webhooks = st.checkbox("Enable Webhooks", value=settings.get("enable_webhooks", False))
            if enable_webhooks:
                webhook_url = st.text_input("Webhook URL", value=settings.get("webhook_url", ""))
                st.info("Webhooks send real-time data to external services")
        
        if st.button("Save Advanced Settings", type="primary", use_container_width=True):
            settings.update({
                "enable_ai_advisor": enable_ai_advisor,
                "enable_voice": enable_voice,
                "default_branch": default_branch,
                "branch_auto_sync": branch_auto_sync,
                "session_timeout": session_timeout,
                "max_login_attempts": max_login_attempts,
                "enable_api": enable_api,
                "api_key": api_key if enable_api else "",
                "enable_webhooks": enable_webhooks,
                "webhook_url": webhook_url if enable_webhooks else ""
            })
            save_settings(settings)
            st.success("Advanced settings saved successfully!")
            st.rerun()
        
        st.markdown("---")
        st.markdown("### System Performance")
        
        st.info("""
        **Performance Tips:**
        - Keep data retention period reasonable (60-90 days)
        - Regular backups help maintain system health
        - Clear cache periodically for optimal performance
        - Use appropriate branch level for your operations
        """)
        
        # System health check
        st.markdown("### 🩺 System Health Check")
        
        if st.button("🩺 Run System Health Check", use_container_width=True):
            with st.spinner("Running health check..."):
                issues = []
                warnings = []
                
                # Check data directories
                data_dir = Path("data")
                if not data_dir.exists():
                    issues.append("Data directory not found")
                
                # Check file sizes
                data_size = sum(f.stat().st_size for f in data_dir.glob("*.csv")) / (1024 * 1024) if data_dir.exists() else 0
                if data_size > 10:
                    warnings.append(f"Data size is {data_size:.1f} MB. Consider cleaning old data.")
                
                # Check products
                try:
                    products = load_products()
                    if len(products) == 0:
                        warnings.append("No products found in inventory")
                except:
                    issues.append("Cannot load products")
                
                if issues:
                    for issue in issues:
                        st.error(f"{issue}")
                if warnings:
                    for warning in warnings:
                        st.warning(f"{warning}")
                if not issues and not warnings:
                    st.success("All systems healthy!")
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.settings_force_refresh = True
        st.rerun()


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    settings_page()