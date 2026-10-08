# backend/modules/settings_page.py
"""
System Settings.

Tabs:
- User Manual
- Store Settings
- Backup & Restore
- System Info
- Email Reports
- Data Management   (branch-aware, PostgreSQL-backed)
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import json
import zipfile
import shutil
from pathlib import Path
from io import BytesIO

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
    send_test_email,
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
    get_db_cursor,
)


# ==============================================================
# SETTINGS FILE HELPERS
# ==============================================================
SETTINGS_FILE = Path("data/system_settings.json")


def get_default_settings():
    return {
        "store_name": "Aziel Investments",
        "store_phone": "+263 78 290 5853",
        "store_email": "info@azielinvestments.co.zw",
        "store_address": "Retreat Park, Harare, Zimbabwe",
        "tax_rate": 15,
        "currency": "ZWL",
        "receipt_footer": "Thank you for shopping with us!",
    }


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return get_default_settings()
    return get_default_settings()


def save_settings(settings):
    SETTINGS_FILE.parent.mkdir(exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)
    return True


# ==============================================================
# BRANCH-SCOPED TABLE LIST (single source of truth)
# ==============================================================
BRANCH_SCOPED_TABLES = [
    "products",
    "sales",
    "customers",
    "customer_transactions",
    "debtors",
    "debtor_payments",
    "expenses",
    "income",
    "purchases",
    "cash_register",
    "shifts",
    "shift_definitions",
    "suppliers",
    "loyalty_points",
    "loyalty_redemptions",
    "expense_budget",
    "recurring_expenses",
    "petty_cash",
    "bank_deposits",
    "returns",
    "refunds",
]

# Tables that are never touched by reset
PROTECTED_TABLES = ["users", "branches", "security", "audit_log"]


# ==============================================================
# DB OVERVIEW HELPERS
# ==============================================================
def _row_count(table, branch_id=None):
    """Count rows in a table, optionally filtered by branch_id."""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return 0
            try:
                if branch_id:
                    cur.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE branch_id = %s", (branch_id,))
                else:
                    cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
                row = cur.fetchone()
                if row is None:
                    return 0
                count = row["c"] if isinstance(row, dict) else row[0]
                return int(count or 0)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                return -1  # table missing
    except Exception:
        return -1


def _branch_row_counts(branch_id):
    counts = {}
    for table in BRANCH_SCOPED_TABLES:
        c = _row_count(table, branch_id=branch_id)
        if c >= 0:
            counts[table] = c
    return counts


def _total_rows(branch_id=None):
    total = 0
    for table in BRANCH_SCOPED_TABLES:
        c = _row_count(table, branch_id=branch_id)
        if c > 0:
            total += c
    return total


# ==============================================================
# DESTRUCTIVE OPERATIONS (PostgreSQL)
# ==============================================================
def clear_old_sales(branch_id, days_to_keep):
    """
    Delete sales rows older than N days.
    If branch_id is None, applies to all branches.
    Returns (success, deleted_count, message).
    """
    cutoff = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, 0, "Database connection failed"

            if branch_id:
                cur.execute(
                    "DELETE FROM sales WHERE branch_id = %s AND sale_date::date < %s",
                    (branch_id, cutoff),
                )
            else:
                cur.execute(
                    "DELETE FROM sales WHERE sale_date::date < %s",
                    (cutoff,),
                )
            deleted = cur.rowcount or 0
            conn.commit()

        scope = f"branch {branch_id}" if branch_id else "all branches"
        return True, deleted, f"Deleted {deleted} sales rows older than {days_to_keep} days from {scope}."
    except Exception as e:
        return False, 0, f"Error clearing old sales: {str(e)}"


def reset_system(branch_id):
    """
    Clear every branch-scoped table for the given branch.
    If branch_id is None, clears ALL branch-scoped tables across all branches.
    NEVER touches users or branches.
    Returns (success, total_deleted, message).
    """
    deleted_summary = {}
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, 0, "Database connection failed"

            for table in BRANCH_SCOPED_TABLES:
                try:
                    if branch_id:
                        cur.execute(f"DELETE FROM {table} WHERE branch_id = %s", (branch_id,))
                    else:
                        cur.execute(f"DELETE FROM {table}")
                    deleted_summary[table] = cur.rowcount or 0
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue

            conn.commit()

        total = sum(deleted_summary.values())
        parts = [f"{t}: {n}" for t, n in deleted_summary.items() if n > 0]
        scope = f"branch {branch_id}" if branch_id else "all branches"
        summary = ", ".join(parts) if parts else "no rows to delete"
        return True, total, f"Reset {scope}. Deleted {total} rows ({summary})."
    except Exception as e:
        return False, 0, f"Error resetting system: {str(e)}"


# ==============================================================
# EXPORT HELPERS
# ==============================================================
def export_all_data_zip(branch_id=None):
    """
    Export every branch-scoped table to a single ZIP.
    If branch_id is given, only that branch's rows are exported.
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return None
            for table in BRANCH_SCOPED_TABLES:
                try:
                    if branch_id:
                        cur.execute(f"SELECT * FROM {table} WHERE branch_id = %s", (branch_id,))
                    else:
                        cur.execute(f"SELECT * FROM {table}")
                    rows = cur.fetchall()
                    if not rows:
                        continue
                    df = pd.DataFrame(rows)
                    csv_bytes = df.to_csv(index=False).encode("utf-8")
                    scope = branch_id if branch_id else "all"
                    zf.writestr(f"{table}_{scope}.csv", csv_bytes)
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue
    buf.seek(0)
    return buf


# ==============================================================
# BACKUP HELPERS (filesystem-based, unchanged behaviour)
# ==============================================================
def create_backup():
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    backup_file = backup_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    with zipfile.ZipFile(backup_file, "w") as zipf:
        for folder in [Path("data"), Path("branch_data")]:
            if folder.exists():
                for file in folder.rglob("*"):
                    if file.is_file():
                        zipf.write(file, str(file))

    return backup_file


def restore_backup(zip_file):
    extract_path = Path("temp_restore")
    if extract_path.exists():
        shutil.rmtree(extract_path)
    with zipfile.ZipFile(zip_file, "r") as zipf:
        zipf.extractall(extract_path)

    if (extract_path / "data").exists():
        shutil.copytree(extract_path / "data", "data", dirs_exist_ok=True)
    if (extract_path / "branch_data").exists():
        shutil.copytree(extract_path / "branch_data", "branch_data", dirs_exist_ok=True)

    shutil.rmtree(extract_path)
    return True


# ==============================================================
# SYSTEM MANUAL
# ==============================================================
def get_system_manual():
    """Return the complete system manual (unchanged from original)."""
    now = datetime.now()
    current_date = now.strftime("%B %d, %Y")

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
│  Co-Developer:              Walker Takaendesa                                │
│  System Name:               SmartGro ERP System                              │
│  Version:                   2.0 (Zimbabwe Edition)                           │
│  Release Date:              July 2026                                        │
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
Version:            2.0 (Zimbabwe Edition)
Email Support:      aziel@investments.co.zw
Phone Support:      +263 78 290 5853
Website:            www.azielinvestments.co.zw

Office Address:
Aziel Investments
Retreat Park, Harare
Zimbabwe

Support Hours:
Monday - Friday: 7:00 AM - 8:00 PM
Saturday: 7:00 AM - 5:00 PM
Sunday: Closed

Emergency Support: +263 78 290 5853

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


# ==============================================================
# MAIN PAGE
# ==============================================================
def settings_page():
    st.title("System Settings")
    st.caption("Configure system preferences, manage backups, and access documentation")

    if st.session_state.get("role") != "owner":
        st.error("Access Denied. Only system owner can access settings.")
        return

    settings = load_settings()
    branches_df = load_branches()
    if branches_df is None:
        branches_df = pd.DataFrame()

    # ==========================================================
    # TABS
    # ==========================================================
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "User Manual",
        "Store Settings",
        "Backup & Restore",
        "ℹ System Info",
        "Email Reports",
        "Data Management",
    ])

    # ==========================================================
    # TAB 1: USER MANUAL
    # ==========================================================
    with tab1:
        st.markdown("## System User Manual")
        st.markdown("Complete documentation for the SmartGro ERP System")

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
            **Version:** 2.0 (Zimbabwe Edition)
            """)

        with col2:
            st.markdown("""
            ### Download Options

            Choose your preferred format:

            - **TXT Format** - Plain text, works everywhere
            """)

            manual_text = get_system_manual()
            current_date = datetime.now().strftime("%Y%m%d")

            st.download_button(
                label="Download TXT Manual",
                data=manual_text,
                file_name=f"SmartGro_Manual_{current_date}.txt",
                mime="text/plain",
                use_container_width=True,
            )

            st.info(
                "Tip: The manual includes complete system documentation, "
                "installation guide, and troubleshooting tips."
            )

        st.markdown("---")
        with st.expander("Preview Manual (Click to expand)"):
            st.text_area("Manual Preview", manual_text[:3000], height=400)

    # ==========================================================
    # TAB 2: STORE SETTINGS
    # ==========================================================
    with tab2:
        st.markdown("## Store Information")

        col1, col2 = st.columns(2)

        with col1:
            store_name = st.text_input("Store Name", value=settings.get("store_name", "Aziel Investments"))
            store_phone = st.text_input("Store Phone", value=settings.get("store_phone", "+263 78 290 5853"))
            store_email = st.text_input("Store Email", value=settings.get("store_email", "info@azielinvestments.co.zw"))

        with col2:
            currency = st.selectbox(
                "Default Currency",
                ["ZWL", "USD", "ZiG", "RAND"],
                index=["ZWL", "USD", "ZiG", "RAND"].index(settings.get("currency", "ZWL")),
            )
            tax_rate = st.number_input(
                "Default Tax Rate (%)",
                min_value=0.0, max_value=100.0,
                value=float(settings.get("tax_rate", 15)),
            )

        store_address = st.text_area(
            "Store Address",
            value=settings.get("store_address", "Retreat Park, Harare, Zimbabwe"),
        )
        receipt_footer = st.text_input(
            "Receipt Footer Message",
            value=settings.get("receipt_footer", "Thank you for shopping with us!"),
        )

        if st.button("Save Store Settings", type="primary", use_container_width=True):
            settings.update({
                "store_name": store_name,
                "store_phone": store_phone,
                "store_email": store_email,
                "store_address": store_address,
                "currency": currency,
                "tax_rate": tax_rate,
                "receipt_footer": receipt_footer,
            })
            save_settings(settings)
            st.success("Store settings saved successfully!")
            st.rerun()

    # ==========================================================
    # TAB 3: BACKUP & RESTORE
    # ==========================================================
    with tab3:
        st.markdown("## Backup & Restore")
        st.warning("Regular backups are recommended to prevent data loss")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Create Backup", use_container_width=True):
                with st.spinner("Creating backup..."):
                    backup_file = create_backup()
                    st.success("Backup created successfully!")
                    with open(backup_file, "rb") as f:
                        st.download_button(
                            label="Download Backup",
                            data=f,
                            file_name=backup_file.name,
                            mime="application/zip",
                            use_container_width=True,
                        )

        with col2:
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

    # ==========================================================
    # TAB 4: SYSTEM INFO
    # ==========================================================
    with tab4:
        st.markdown("## System Information")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### System Details")
            st.write("**System Name:** SmartGro ERP")
            st.write("**Version:** 2.0 (Zimbabwe Edition)")
            st.write("**Founder:** King T Chingaona")
            st.write("**Co-Developer:** Walker Takaendesa")
            st.write("**Release Date:** June 2026")
            st.write("**Framework:** Streamlit")

        with col2:
            st.markdown("### Database Stats")
            st.write(f"**Total Products:** {len(load_products())}")
            st.write(f"**Total Sales Rows:** {len(load_sales())}")
            st.write(f"**Total Customers:** {len(load_customers())}")
            st.write(f"**Total Branches:** {len(branches_df)}")

        st.markdown("---")
        st.markdown("### Developer Information")
        st.markdown("""
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
        st.markdown("### License Information")
        st.markdown("""
        **SmartGro ERP System**
        Copyright © 2026 Aziel Investments

        All rights reserved. This software is proprietary and confidential.
        Unauthorized copying, distribution, or modification is strictly prohibited.
        """)

        if st.button("Clear System Cache", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache cleared! Refresh the page.")

    # ==========================================================
    # TAB 5: EMAIL REPORTS  (unchanged)
    # ==========================================================
    with tab5:
        st.markdown("## Email Reports Configuration")
        st.caption("Configure email settings for automated reports")

        email_config = get_email_config()

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
        recipients_text = st.text_area(
            "Recipient Emails (one per line)",
            value="\n".join(email_config.get("recipient_emails", [])),
            height=100,
            placeholder="manager@example.com\nowner@example.com\naccountant@example.com",
            key="email_recipients",
        )

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
                "enable_low_stock_alert": enable_low_stock,
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

    # ==========================================================
    # TAB 6: DATA MANAGEMENT (branch-aware, PostgreSQL-backed)
    # ==========================================================
    with tab6:
        st.markdown("## Data Management")
        st.caption("Clean up old data and manage system storage — branch-aware and PostgreSQL-backed.")

        st.warning("These actions can permanently delete data. Use with caution.")

        # -------- Branch selector --------
        if branches_df.empty:
            st.error("No branches configured. Add a branch first.")
            return

        branch_labels = [f"{r['branch_name']} ({r['branch_id']})" for _, r in branches_df.iterrows()]
        scope_options = ["All branches"] + branch_labels
        scope_choice = st.selectbox("Target scope", scope_options, key="dm_scope_choice")

        if scope_choice == "All branches":
            target_branch_id = None
        else:
            idx = branch_labels.index(scope_choice)
            target_branch_id = branches_df.iloc[idx]["branch_id"]

        # -------- Database overview --------
        with st.expander("📊 Database overview", expanded=False):
            st.markdown("**Rows per branch per table**")
            overview_rows = []
            for _, br in branches_df.iterrows():
                bid = br["branch_id"]
                counts = _branch_row_counts(bid)
                overview_rows.append({
                    "Branch": br["branch_name"],
                    "Code": bid,
                    "Total rows": _total_rows(bid),
                })
            st.dataframe(pd.DataFrame(overview_rows), use_container_width=True, hide_index=True)

            st.markdown("**Detailed counts for selected scope**")
            if target_branch_id is None:
                detail_rows = [{"Table": t, "Rows": _row_count(t)} for t in BRANCH_SCOPED_TABLES]
            else:
                counts = _branch_row_counts(target_branch_id)
                detail_rows = [{"Table": t, "Rows": counts.get(t, 0)} for t in BRANCH_SCOPED_TABLES]
            detail_df = pd.DataFrame(detail_rows)
            detail_df = detail_df[detail_df["Rows"] >= 0]
            st.dataframe(detail_df, use_container_width=True, hide_index=True)

        st.markdown("---")

        # -------- Clear old sales --------
        st.markdown("### Clear Old Sales Data")
        days_to_keep = st.number_input("Keep data from last (days)", min_value=30, max_value=365, value=90)
        st.caption(
            f"This will delete sales rows older than **{days_to_keep} days** "
            f"for **{scope_choice}**."
        )

        if st.button("Clear Old Sales", use_container_width=True, key="clear_old_sales_btn"):
            st.session_state["dm_confirm_clear_sales"] = True

        if st.session_state.get("dm_confirm_clear_sales", False):
            typed = st.text_input(
                "Type **DELETE** to confirm",
                key="dm_clear_sales_typed",
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirm Delete", type="primary", use_container_width=True, key="dm_clear_sales_confirm"):
                    if typed.strip().upper() != "DELETE":
                        st.error("Confirmation text does not match.")
                    else:
                        ok, count, msg = clear_old_sales(target_branch_id, days_to_keep)
                        if ok:
                            st.success(msg)
                            st.session_state["dm_confirm_clear_sales"] = False
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(msg)
            with col2:
                if st.button("Cancel", use_container_width=True, key="dm_clear_sales_cancel"):
                    st.session_state["dm_confirm_clear_sales"] = False
                    st.rerun()

        st.markdown("---")

        # -------- Export all data --------
        st.markdown("### Export All Data")
        st.caption(f"Export every table for **{scope_choice}** as a single ZIP.")
        if st.button("Prepare Export (ZIP)", use_container_width=True, key="prepare_export_btn"):
            with st.spinner("Preparing ZIP..."):
                buf = export_all_data_zip(branch_id=target_branch_id)
                if buf is not None:
                    st.download_button(
                        label="Download All Data (ZIP)",
                        data=buf,
                        file_name=f"all_data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                        mime="application/zip",
                        use_container_width=True,
                    )
                else:
                    st.error("Could not prepare export.")

        st.markdown("---")

        # -------- Reset system --------
        st.markdown("### Reset System (Danger Zone)")
        st.error(
            f"This will delete every row in every branch-scoped table for **{scope_choice}**. "
            f"Users and branches are never touched."
        )

        # Backup before reset
        if st.button("1. Create Safety Backup First", use_container_width=True, key="reset_backup_btn"):
            with st.spinner("Creating backup..."):
                backup_file = create_backup()
                st.success(f"Safety backup created at: {backup_file}")

        st.markdown("#### To proceed with the reset:")
        st.markdown(
            f"Type **RESET** and confirm you understand the consequences for **{scope_choice}**."
        )

        typed_reset = st.text_input("Type **RESET** to confirm", key="reset_typed")
        confirm_reset = st.checkbox(
            "I understand this will delete ALL branch-scoped data for the selected scope. "
            "This action CANNOT be undone (except from a backup).",
            key="reset_confirm_box",
        )

        if st.button("2. RESET SYSTEM NOW", use_container_width=True, key="reset_now_btn"):
            if typed_reset.strip().upper() != "RESET" or not confirm_reset:
                st.error("Please type RESET and tick the confirmation checkbox.")
            else:
                ok, total, msg = reset_system(target_branch_id)
                if ok:
                    st.success(msg)
                    st.info("Safety tip: restore from the backup you created above if needed.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(msg)

    # ==========================================================
    # REFRESH
    # ==========================================================
    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True, key="settings_refresh"):
        st.cache_data.clear()
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    settings_page()