import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import json
import zipfile
import shutil
from pathlib import Path

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
    init_data_folder
)

# ==============================
# SETTINGS PAGE
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
        "store_phone": "+263 78 290 5853",
        "store_email": "info@azielinvestments.co.zw",
        "store_address": "Retreat Park, Harare, Zimbabwe",
        "tax_rate": 15,
        "currency": "ZWL",
        "receipt_footer": "Thank you for shopping with us!"
    }


def save_settings(settings):
    """Save settings to file"""
    settings_file = Path("data/system_settings.json")
    settings_file.parent.mkdir(exist_ok=True)
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)
    return True


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
│  Release Date:              June 2024                                        │
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
• Go to: http://localhost:8501
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
Monday - Friday: 8:00 AM - 5:00 PM
Saturday: 9:00 AM - 1:00 PM
Sunday: Closed

Emergency Support: +263 78 290 5853

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    LICENSE & COPYRIGHT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SmartGro ERP System
Copyright © 2024 Aziel Investments

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


def settings_page():
    """Settings Page with complete configuration"""
    
    st.title("⚙️ System Settings")
    st.caption("Configure system preferences, manage backups, and access documentation")
    
    # Security check - only owner can access
    if st.session_state.get("role") != "owner":
        st.error("❌ Access Denied. Only system owner can access settings.")
        return
    
    # Load current settings
    settings = load_settings()
    
    # ==============================
    # TABS FOR DIFFERENT SETTINGS
    # ==============================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📖 User Manual",
        "🏪 Store Settings",
        "💾 Backup & Restore",
        "ℹ️ System Info",
        "📧 Email Reports",
        "🧹 Data Management"
    ])
    
    # ==============================
    # TAB 1: USER MANUAL
    # ==============================
    with tab1:
        st.markdown("## 📖 System User Manual")
        st.markdown("Complete documentation for the SmartGro ERP System")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 📚 Manual Contents
            
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
        
        with col2:
            st.markdown("""
            ### 📥 Download Options
            
            Choose your preferred format:
            
            - **TXT Format** - Plain text, works everywhere
            """)
            
            # Download buttons
            manual_text = get_system_manual()
            current_date = datetime.now().strftime('%Y%m%d')
            
            st.download_button(
                label="📄 Download TXT Manual",
                data=manual_text,
                file_name=f"SmartGro_Manual_{current_date}.txt",
                mime="text/plain",
                use_container_width=True
            )
            
            st.info("💡 Tip: The manual includes complete system documentation, installation guide, and troubleshooting tips.")
        
        st.markdown("---")
        
        # Preview manual
        with st.expander("📖 Preview Manual (Click to expand)"):
            st.text_area("Manual Preview", manual_text[:3000], height=400)
    
    # ==============================
    # TAB 2: STORE SETTINGS
    # ==============================
    with tab2:
        st.markdown("## 🏪 Store Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            store_name = st.text_input("Store Name", value=settings.get("store_name", "Aziel Investments"))
            store_phone = st.text_input("Store Phone", value=settings.get("store_phone", "+263 78 290 5853"))
            store_email = st.text_input("Store Email", value=settings.get("store_email", "info@azielinvestments.co.zw"))
        
        with col2:
            currency = st.selectbox("Default Currency", ["ZWL", "USD", "ZiG", "RAND"], 
                                   index=["ZWL", "USD", "ZiG", "RAND"].index(settings.get("currency", "ZWL")))
            tax_rate = st.number_input("Default Tax Rate (%)", min_value=0.0, max_value=100.0, 
                                      value=float(settings.get("tax_rate", 15)))
        
        store_address = st.text_area("Store Address", value=settings.get("store_address", "Retreat Park, Harare, Zimbabwe"))
        receipt_footer = st.text_input("Receipt Footer Message", value=settings.get("receipt_footer", "Thank you for shopping with us!"))
        
        if st.button("💾 Save Store Settings", type="primary", use_container_width=True):
            settings["store_name"] = store_name
            settings["store_phone"] = store_phone
            settings["store_email"] = store_email
            settings["store_address"] = store_address
            settings["currency"] = currency
            settings["tax_rate"] = tax_rate
            settings["receipt_footer"] = receipt_footer
            save_settings(settings)
            st.success("✅ Store settings saved successfully!")
            st.rerun()
    
    # ==============================
    # TAB 3: BACKUP & RESTORE
    # ==============================
    with tab3:
        st.markdown("## 💾 Backup & Restore")
        st.warning("⚠️ Regular backups are recommended to prevent data loss")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📦 Create Backup", use_container_width=True):
                with st.spinner("Creating backup..."):
                    backup_file = create_backup()
                    st.success(f"✅ Backup created successfully!")
                    
                    with open(backup_file, "rb") as f:
                        st.download_button(
                            label="📥 Download Backup",
                            data=f,
                            file_name=backup_file.name,
                            mime="application/zip",
                            use_container_width=True
                        )
        
        with col2:
            uploaded_file = st.file_uploader("Restore from Backup", type=["zip"])
            if uploaded_file is not None:
                st.warning("⚠️ Restoring will overwrite current data!")
                confirm = st.checkbox("I understand this will replace all current data")
                if confirm and st.button("🔄 Restore Backup", use_container_width=True):
                    with st.spinner("Restoring backup..."):
                        # Save uploaded file temporarily
                        temp_zip = Path("temp_restore.zip")
                        with open(temp_zip, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        restore_backup(temp_zip)
                        temp_zip.unlink()
                        
                        st.success("✅ Backup restored successfully! Please restart the application.")
    
    # ==============================
    # TAB 4: SYSTEM INFO
    # ==============================
    with tab4:
        st.markdown("## ℹ️ System Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 System Details")
            st.write(f"**System Name:** SmartGro ERP")
            st.write(f"**Version:** 3.0 (Zimbabwe Edition)")
            st.write(f"**Founder:** King T Chingaona")
            st.write(f"**Co-Developer:** Walker Takaendesa")
            st.write(f"**Release Date:** June 2024")
            st.write(f"**Framework:** Streamlit")
        
        with col2:
            st.markdown("### 📈 Database Stats")
            
            products = load_products()
            sales = load_sales()
            customers = load_customers()
            branches = load_branches()
            
            st.write(f"**Total Products:** {len(products)}")
            st.write(f"**Total Sales:** {len(sales)}")
            st.write(f"**Total Customers:** {len(customers)}")
            st.write(f"**Total Branches:** {len(branches)}")
        
        st.markdown("---")
        
        st.markdown("### 👨‍💻 Developer Information")
        st.markdown(f"""
        | Detail | Information |
        |--------|-------------|
        | **Founder & Lead Developer** | King T Chingaona |
        | **Co-Developer** | Walker Takaendesa |
        | **Company** | Aziel Investments |
        | **Location** | Retreat Park, Harare, Zimbabwe |
        | **Contact** | +263 78 290 5853 |
        | **Email** | aziel@investments.co.zw |
        """)
        
        st.markdown("---")
        
        st.markdown("### 📜 License Information")
        st.markdown("""
        **SmartGro ERP System**  
        Copyright © 2024 Aziel Investments  
        
        All rights reserved. This software is proprietary and confidential.
        Unauthorized copying, distribution, or modification is strictly prohibited.
        """)
        
        # Clear cache button
        if st.button("🗑️ Clear System Cache", use_container_width=True):
            st.cache_data.clear()
            st.success("✅ Cache cleared! Refresh the page.")
    
    # ==============================
    # TAB 5: EMAIL REPORTS (FULLY FUNCTIONAL)
    # ==============================
    with tab5:
        st.markdown("## 📧 Email Reports Configuration")
        st.caption("Configure email settings for automated reports")
        
        # Load email config
        email_config = get_email_config()
        
        # Test connection row
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔌 Test Email Connection", use_container_width=True):
                with st.spinner("Testing connection..."):
                    success, message = test_email_connection()
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
                        st.info("💡 For Gmail: You need to use an App Password. Go to Google Account → Security → App Passwords.")
        
        with col2:
            if st.button("📧 Send Test Email", use_container_width=True):
                with st.spinner("Sending test email..."):
                    success, message = send_test_email()
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
        
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
            st.caption("🔑 **Gmail users:** Generate an App Password at myaccount.google.com/apppasswords")
            st.caption("📧 **Other providers:** Use your regular password or SMTP password")
        
        st.markdown("### Recipients")
        
        recipients_text = st.text_area("Recipient Emails (one per line)", 
                                       value="\n".join(email_config.get("recipient_emails", [])),
                                       height=100,
                                       placeholder="manager@example.com\nowner@example.com\naccountant@example.com",
                                       key="email_recipients")
        
        st.markdown("### Report Schedule")
        
        col1, col2 = st.columns(2)
        
        with col1:
            enable_daily = st.checkbox("📊 Enable Daily Sales Report", value=email_config.get("enable_daily_report", False), key="email_enable_daily")
            if enable_daily:
                st.info("Daily report will be sent at end of each day")
        
        with col2:
            enable_weekly = st.checkbox("📈 Enable Weekly Sales Report", value=email_config.get("enable_weekly_report", False), key="email_enable_weekly")
            if enable_weekly:
                st.info("Weekly report will be sent every Sunday")
        
        enable_low_stock = st.checkbox("⚠️ Enable Low Stock Alerts", value=email_config.get("enable_low_stock_alert", False), key="email_enable_low_stock")
        if enable_low_stock:
            st.info("Low stock alerts sent when inventory falls below reorder levels")
        
        if st.button("💾 Save Email Settings", type="primary", use_container_width=True):
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
                st.success("✅ Email settings saved successfully!")
            else:
                st.error("❌ Failed to save email settings")
        
        st.markdown("---")
        
        st.markdown("### Manual Send")
        st.caption("Send reports immediately regardless of schedule")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📧 Send Daily Report Now", use_container_width=True):
                with st.spinner("Sending daily report..."):
                    success, message = send_daily_report()
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
        
        with col2:
            if st.button("📊 Send Weekly Report Now", use_container_width=True):
                with st.spinner("Sending weekly report..."):
                    success, message = send_weekly_report()
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
        
        with col3:
            if st.button("⚠️ Send Low Stock Alert", use_container_width=True):
                with st.spinner("Checking stock and sending..."):
                    success, message = send_low_stock_alert()
                    if success:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
        
        st.markdown("---")
        
        st.markdown("### Troubleshooting")
        
        with st.expander("🔧 Why aren't emails sending? Click for help"):
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
    # TAB 6: DATA MANAGEMENT
    # ==============================
    with tab6:
        st.markdown("## 🧹 Data Management")
        st.caption("Clean up old data and manage system storage")
        
        st.warning("⚠️ These actions can permanently delete data. Use with caution.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Clear Old Sales Data")
            days_to_keep = st.number_input("Keep data from last (days)", min_value=30, max_value=365, value=90)
            
            if st.button("🗑️ Clear Old Sales", use_container_width=True):
                confirm = st.checkbox("⚠️ I understand this will delete old sales records permanently")
                if confirm:
                    sales_df = load_sales()
                    if not sales_df.empty and "date" in sales_df.columns:
                        sales_df["date"] = pd.to_datetime(sales_df["date"])
                        cutoff = datetime.now() - timedelta(days=days_to_keep)
                        filtered_df = sales_df[sales_df["date"] >= cutoff]
                        save_sales(filtered_df)
                        st.success(f"✅ Removed records older than {days_to_keep} days. {len(filtered_df)} records remaining.")
        
        with col2:
            st.markdown("### Export All Data")
            
            if st.button("📥 Export All Data (CSV)", use_container_width=True):
                import zipfile
                from io import BytesIO
                
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                    # Export all data files
                    products_df = load_products()
                    sales_df = load_sales()
                    customers_df = load_customers()
                    debtors_df = load_debtors()
                    expenses_df = load_expenses()
                    purchases_df = load_purchases()
                    
                    # Save to CSV in memory and add to zip
                    for name, df in [("products", products_df), ("sales", sales_df), 
                                    ("customers", customers_df), ("debtors", debtors_df),
                                    ("expenses", expenses_df), ("purchases", purchases_df)]:
                        if not df.empty:
                            csv_data = df.to_csv(index=False).encode('utf-8')
                            zipf.writestr(f"{name}_{datetime.now().strftime('%Y%m%d')}.csv", csv_data)
                
                zip_buffer.seek(0)
                st.download_button(
                    label="📥 Download All Data (ZIP)",
                    data=zip_buffer,
                    file_name=f"all_data_export_{datetime.now().strftime('%Y%m%d')}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        st.markdown("### Reset System (Danger Zone)")
        st.error("⚠️ This will delete ALL data and reset the system to factory defaults!")
        
        confirm_reset = st.checkbox("I understand this will delete ALL data. This action CANNOT be undone.")
        reset_password = st.text_input("Type 'RESET' to confirm", type="password")
        
        if confirm_reset and reset_password == "RESET":
            if st.button("🔥 RESET SYSTEM", use_container_width=True):
                # Backup before reset
                backup_file = create_backup()
                st.info(f"Backup created at: {backup_file}")
                
                # Reset data files
                import shutil
                
                # Clear data folders
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
                
                # Reinitialize
                init_data_folder()
                
                st.success("✅ System reset to factory defaults! Please restart the application.")
                st.warning("Your backup file has been saved. You can restore it from Backup & Restore tab.")
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# Call the function if running directly
if __name__ == "__main__":
    settings_page()