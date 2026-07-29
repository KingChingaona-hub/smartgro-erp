# backend/features/financial_closing.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path
import json
import shutil
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO

from backend.core.db_adapter import (
    load_sales, 
    load_expenses, 
    load_purchases, 
    load_products, 
    load_customers, 
    load_debtors,
    load_cash,
    load_shifts,
    get_cash_summary,
    to_float
)
from backend.modules.income import load_income
from backend.analytics.pl_engine import profit_loss_account
from backend.admin.security import log_audit

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
CLOSING_DIR = DATA_DIR / "closing_reports"
BACKUP_DIR = DATA_DIR / "backups"
EXPENSES_FILE = DATA_DIR / "expenses.csv"


# ==============================
# INITIALIZATION
# ==============================
def init_closing_files():
    """Initialize closing report directories"""
    CLOSING_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def get_period_dates(period_type, year, month=None, quarter=None):
    """Get start and end dates for a period"""
    
    today = datetime.now()
    
    if period_type == "daily":
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period_type == "monthly":
        if month:
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        else:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31)
    elif period_type == "quarterly":
        quarter_months = {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}
        start_month = quarter_months[quarter][0]
        end_month = quarter_months[quarter][2]
        start_date = datetime(year, start_month, 1)
        if end_month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, end_month + 1, 1) - timedelta(days=1)
    elif period_type == "yearly":
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31)
    else:
        start_date = today - timedelta(days=30)
        end_date = today
    
    if isinstance(end_date, datetime):
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return start_date, end_date


# ==============================
# DEDUPLICATE SALES HELPER
# ==============================
def get_unduplicated_sales(sales_df, date_col=None, total_col=None, receipt_col=None):
    """
    Get unduplicated sales by receipt_no.
    This handles the old table structure where each item is a row.
    """
    if sales_df.empty:
        return pd.DataFrame(), 0, 0, 0, 0
    
    # If we have receipt_no, deduplicate
    if receipt_col and receipt_col in sales_df.columns:
        # Get unique receipts only
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        total_revenue = to_float(unique_receipts[total_col].sum()) if total_col in unique_receipts.columns else 0
        transaction_count = len(unique_receipts)
        
        # For items sold, sum from original (or use item_count if available)
        if 'items' in sales_df.columns:
            items_sold = to_float(sales_df['items'].sum())
        elif 'item_count' in unique_receipts.columns:
            items_sold = to_float(unique_receipts['item_count'].sum())
        else:
            items_sold = len(sales_df)
        
        # For profit, sum from original (profit is per item)
        if 'profit' in sales_df.columns:
            total_profit = to_float(sales_df['profit'].sum())
        else:
            total_profit = 0
        
        return unique_receipts, total_revenue, total_profit, items_sold, transaction_count
    
    # Fallback: no receipt_no, use original logic
    total_revenue = to_float(sales_df[total_col].sum()) if total_col in sales_df.columns else 0
    total_profit = to_float(sales_df['profit'].sum()) if 'profit' in sales_df.columns else 0
    items_sold = to_float(sales_df['items'].sum()) if 'items' in sales_df.columns else len(sales_df)
    transaction_count = len(sales_df)
    
    return sales_df, total_revenue, total_profit, items_sold, transaction_count


# ==============================
# DIRECT EXPENSES LOADER
# ==============================
def load_expenses_direct():
    """Load expenses directly from CSV file"""
    try:
        if not EXPENSES_FILE.exists():
            print(f"Expenses file not found: {EXPENSES_FILE}")
            return pd.DataFrame()
        
        df = pd.read_csv(EXPENSES_FILE)
        print(f"Loaded {len(df)} expenses from CSV")
        
        if df.empty:
            print("Expenses file is empty")
            return df
        
        # Ensure required columns
        required_cols = ["date", "category", "amount", "description"]
        for col in required_cols:
            if col not in df.columns:
                print(f"Missing column: {col}")
                df[col] = "" if col != "amount" else 0
        
        # Convert date to datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        # Convert amount to float
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        
        print(f"Total expenses in file: ${df['amount'].sum():,.2f}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
        
        return df
    except Exception as e:
        print(f"Error loading expenses: {e}")
        return pd.DataFrame()


def get_period_data(period_type, year, month=None, quarter=None):
    """Get REAL financial data for a period - WITH UNDUPLICATED REVENUE"""
    
    start_date, end_date = get_period_dates(period_type, year, month, quarter)
    
    # Load data
    sales_df = load_sales()
    expenses_df = load_expenses_direct()
    purchases_df = load_purchases()
    customers_df = load_customers()
    debtors_df = load_debtors()
    products_df = load_products()
    
    # ==============================
    # LOAD INCOME FROM INCOME TABLE - FIXED
    # ==============================
    income_df = load_income()
    total_income = 0
    income_categories = {}
    
    if not income_df.empty:
        # Find date column
        date_col_inc = None
        for col in ["date", "income_date", "created_at"]:
            if col in income_df.columns:
                date_col_inc = col
                break
        
        # Find amount column
        amount_col_inc = None
        for col in ["amount", "total", "value"]:
            if col in income_df.columns:
                amount_col_inc = col
                break
        
        # Find category column
        category_col_inc = None
        for col in ["category", "income_type", "type"]:
            if col in income_df.columns:
                category_col_inc = col
                break
        
        if date_col_inc and amount_col_inc:
            income_df[date_col_inc] = pd.to_datetime(income_df[date_col_inc], errors="coerce")
            income_df = income_df.dropna(subset=[date_col_inc])
            
            period_income = income_df[(income_df[date_col_inc] >= start_date) & (income_df[date_col_inc] <= end_date)]
            
            if not period_income.empty:
                total_income = to_float(period_income[amount_col_inc].sum())
                
                if category_col_inc:
                    category_summary = period_income.groupby(category_col_inc)[amount_col_inc].sum().to_dict()
                    income_categories = {str(k): to_float(v) for k, v in category_summary.items()}
                
                print(f"Total Income from income table: ${total_income:,.2f}")
            else:
                print(f"No income found for period {start_date} to {end_date}")
        else:
            print(f"Missing date or amount column in income data")
    else:
        print("No income data found")
    
    # ============================================================
    # FIND COLUMNS IN SALES
    # ============================================================
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    total_col = None
    for col in ["final_total", "total", "amount", "sale_amount"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    receipt_col = None
    for col in ["receipt_no", "receipt", "transaction_id", "invoice_no"]:
        if col in sales_df.columns:
            receipt_col = col
            break
    
    # ============================================================
    # SALES DATA - Filter by date then deduplicate
    # ============================================================
    total_revenue = 0
    total_profit = 0
    transaction_count = 0
    items_sold = 0
    
    if not sales_df.empty and date_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
        
        period_sales = sales_df[(sales_df[date_col] >= start_date) & (sales_df[date_col] <= end_date)]
        
        if not period_sales.empty:
            # DEDUPLICATE: Get unique receipts for revenue calculation
            unique_receipts, revenue, profit, items, transactions = get_unduplicated_sales(
                period_sales, date_col, total_col, receipt_col
            )
            
            total_revenue = revenue
            total_profit = profit
            items_sold = items
            transaction_count = transactions
            
            print(f"Total Revenue (unduplicated): ${total_revenue:,.2f}")
            print(f"Transactions: {transaction_count}")
            print(f"Items Sold: {items_sold}")
    
    # ============================================================
    # EXPENSES DATA
    # ============================================================
    total_expenses = 0
    expense_categories = {}
    
    if not expenses_df.empty:
        # Find the date column
        date_col_exp = None
        for col in ["date", "expense_date", "created_at"]:
            if col in expenses_df.columns:
                date_col_exp = col
                break
        
        # Find the amount column
        amount_col = None
        for col in ["amount", "total", "value"]:
            if col in expenses_df.columns:
                amount_col = col
                break
        
        # Find the category column
        category_col = None
        for col in ["category", "expense_type", "type"]:
            if col in expenses_df.columns:
                category_col = col
                break
        
        if date_col_exp and amount_col:
            expenses_df[date_col_exp] = pd.to_datetime(expenses_df[date_col_exp], errors="coerce")
            expenses_df = expenses_df.dropna(subset=[date_col_exp])
            
            period_expenses = expenses_df[(expenses_df[date_col_exp] >= start_date) & (expenses_df[date_col_exp] <= end_date)]
            
            if not period_expenses.empty:
                total_expenses = to_float(period_expenses[amount_col].sum())
                
                if category_col:
                    category_summary = period_expenses.groupby(category_col)[amount_col].sum().to_dict()
                    expense_categories = {str(k): to_float(v) for k, v in category_summary.items()}
                
                print(f"Total Expenses: ${total_expenses:,.2f}")
    
    # ============================================================
    # NET INCOME = Total Income from Income Table - Total Expenses
    # ============================================================
    net_income = total_income - total_expenses
    print(f"Net Income (Income - Expenses): ${net_income:,.2f}")
    
    # ============================================================
    # PURCHASES DATA
    # ============================================================
    total_purchases = 0
    if not purchases_df.empty:
        date_col_pur = None
        for col in ["date_ordered", "date", "order_date"]:
            if col in purchases_df.columns:
                date_col_pur = col
                break
        
        if date_col_pur:
            purchases_df[date_col_pur] = pd.to_datetime(purchases_df[date_col_pur], errors="coerce")
            period_purchases = purchases_df[(purchases_df[date_col_pur] >= start_date) & (purchases_df[date_col_pur] <= end_date)]
            total_purchases = to_float(period_purchases["total_cost"].sum()) if "total_cost" in period_purchases.columns and not period_purchases.empty else 0
    
    # ============================================================
    # NEW CUSTOMERS
    # ============================================================
    new_customers = 0
    if not customers_df.empty:
        date_col_cust = None
        for col in ["created_at", "join_date", "date_joined", "last_purchase_date"]:
            if col in customers_df.columns:
                date_col_cust = col
                break
        
        if date_col_cust:
            customers_df[date_col_cust] = pd.to_datetime(customers_df[date_col_cust], errors="coerce")
            new_customers = len(customers_df[customers_df[date_col_cust] >= start_date])
        else:
            new_customers = len(customers_df)
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_revenue": total_revenue,
        "total_income": total_income,
        "income_categories": income_categories,
        "total_expenses": total_expenses,
        "expense_categories": expense_categories,
        "net_income": net_income,
        "total_purchases": total_purchases,
        "transaction_count": transaction_count,
        "items_sold": items_sold,
        "total_profit": total_profit,
        "new_customers": new_customers,
        "period_type": period_type,
        "year": year,
        "month": month,
        "quarter": quarter
    }


def generate_closing_report_pdf(data):
    """Generate a professional closing report PDF with REAL data"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
    
    if data["period_type"] == "daily":
        period_text = f"Daily Report - {data['start_date'].strftime('%Y-%m-%d')}"
    elif data["period_type"] == "monthly":
        period_text = f"Monthly Report - {data['start_date'].strftime('%B %Y')}"
    elif data["period_type"] == "quarterly":
        period_text = f"Quarterly Report - Q{data['quarter']} {data['year']}"
    else:
        period_text = f"Annual Report - {data['year']}"
    
    story.append(Paragraph(f"AZIEL INVESTMENTS - {period_text}", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Summary Table with REAL data
    summary_data = [
        ["Metric", "Value"],
        ["Total Revenue", f"${data['total_revenue']:,.2f}"],
        ["Total Income", f"${data['total_income']:,.2f}"],
        ["Total Expenses", f"${data['total_expenses']:,.2f}"],
        ["Net Income", f"${data['net_income']:,.2f}"],
        ["Total Purchases", f"${data['total_purchases']:,.2f}"],
        ["Transactions", f"{data['transaction_count']:,}"],
        ["Items Sold", f"{data['items_sold']:,}"],
        ["New Customers", f"{data['new_customers']}"]
    ]
    
    table = Table(summary_data, colWidths=[3*inch, 3*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    
    story.append(table)
    
    # Income by category
    if data.get('income_categories'):
        story.append(Spacer(1, 20))
        story.append(Paragraph("Income by Category", styles['Heading2']))
        
        inc_data = [["Category", "Amount"]]
        for category, amount in sorted(data['income_categories'].items(), key=lambda x: -x[1]):
            inc_data.append([category, f"${amount:,.2f}"])
        
        inc_table = Table(inc_data, colWidths=[3*inch, 3*inch])
        inc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(inc_table)
    
    # Expenses by category
    if data.get('expense_categories'):
        story.append(Spacer(1, 20))
        story.append(Paragraph("Expenses by Category", styles['Heading2']))
        
        exp_data = [["Category", "Amount"]]
        for category, amount in sorted(data['expense_categories'].items(), key=lambda x: -x[1]):
            exp_data.append([category, f"${amount:,.2f}"])
        
        exp_table = Table(exp_data, colWidths=[3*inch, 3*inch])
        exp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(exp_table)
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer


def create_backup():
    """Create a backup before closing"""
    backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = BACKUP_DIR / backup_name
    backup_path.mkdir(exist_ok=True)
    
    data_dir = DATA_DIR
    for file in data_dir.glob("*.csv"):
        shutil.copy2(file, backup_path / file.name)
    for file in data_dir.glob("*.json"):
        shutil.copy2(file, backup_path / file.name)
    
    branch_dir = Path("branch_data")
    if branch_dir.exists():
        shutil.copytree(branch_dir, backup_path / "branch_data", dirs_exist_ok=True)
    
    return backup_path


def perform_daily_close():
    """Perform end-of-day closing with REAL data"""
    init_closing_files()
    
    backup_path = create_backup()
    
    data = get_period_data("daily", datetime.now().year, datetime.now().month)
    data["period_type"] = "daily"
    
    pdf = generate_closing_report_pdf(data)
    
    report_path = CLOSING_DIR / f"daily_close_{datetime.now().strftime('%Y%m%d')}.pdf"
    with open(report_path, "wb") as f:
        f.write(pdf.getvalue())
    
    log_audit(st.session_state.get("username", "system"), "DAILY_CLOSE", f"Daily closing completed. Backup: {backup_path}")
    
    return True, report_path, backup_path


def perform_monthly_close(year, month):
    """Perform month-end closing with REAL data"""
    init_closing_files()
    
    backup_path = create_backup()
    
    data = get_period_data("monthly", year, month)
    data["period_type"] = "monthly"
    
    pdf = generate_closing_report_pdf(data)
    
    report_path = CLOSING_DIR / f"monthly_close_{year}_{month:02d}.pdf"
    with open(report_path, "wb") as f:
        f.write(pdf.getvalue())
    
    log_audit(st.session_state.get("username", "system"), "MONTHLY_CLOSE", f"Monthly closing completed for {year}-{month:02d}. Backup: {backup_path}")
    
    return True, report_path, backup_path


def generate_tax_report(year, tax_period="annual"):
    """Generate ZIMRA tax report with REAL data"""
    
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    
    sales_df = load_sales()
    expenses_df = load_expenses_direct()
    income_df = load_income()
    
    # Find columns
    date_col = None
    for col in ["sale_date", "date", "transaction_date"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    total_col = None
    for col in ["final_total", "total", "amount"]:
        if col in sales_df.columns:
            total_col = col
            break
    
    receipt_col = None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in sales_df.columns:
            receipt_col = col
            break
    
    # Calculate unduplicated revenue
    total_sales = 0
    if not sales_df.empty and date_col and total_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        period_sales = sales_df[(sales_df[date_col] >= start_date) & (sales_df[date_col] <= end_date)]
        
        if not period_sales.empty:
            if receipt_col and receipt_col in period_sales.columns:
                # Deduplicate by receipt
                unique_receipts = period_sales.drop_duplicates(subset=[receipt_col])
                total_sales = to_float(unique_receipts[total_col].sum())
            else:
                total_sales = to_float(period_sales[total_col].sum())
    
    # Total Income from Income Table
    total_income = 0
    if not income_df.empty:
        date_col_inc = None
        for col in ["date", "income_date"]:
            if col in income_df.columns:
                date_col_inc = col
                break
        
        amount_col_inc = None
        for col in ["amount", "total"]:
            if col in income_df.columns:
                amount_col_inc = col
                break
        
        if date_col_inc and amount_col_inc:
            income_df[date_col_inc] = pd.to_datetime(income_df[date_col_inc], errors="coerce")
            period_income = income_df[(income_df[date_col_inc] >= start_date) & (income_df[date_col_inc] <= end_date)]
            total_income = to_float(period_income[amount_col_inc].sum()) if amount_col_inc in period_income.columns and not period_income.empty else 0
    
    # Expenses
    total_expenses = 0
    if not expenses_df.empty:
        date_col_exp = None
        for col in ["date", "expense_date"]:
            if col in expenses_df.columns:
                date_col_exp = col
                break
        
        amount_col = None
        for col in ["amount", "total"]:
            if col in expenses_df.columns:
                amount_col = col
                break
        
        if date_col_exp and amount_col:
            expenses_df[date_col_exp] = pd.to_datetime(expenses_df[date_col_exp], errors="coerce")
            period_expenses = expenses_df[(expenses_df[date_col_exp] >= start_date) & (expenses_df[date_col_exp] <= end_date)]
            total_expenses = to_float(period_expenses[amount_col].sum()) if amount_col in period_expenses.columns and not period_expenses.empty else 0
    
    taxable_income = total_income - total_expenses
    tax_rate = 0.25
    tax_due = taxable_income * tax_rate if taxable_income > 0 else 0
    
    report = f"""
{'='*60}
AZIEL INVESTMENTS - ZIMRA TAX REPORT
{'='*60}

Tax Period: {tax_period.upper()} {year}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'─'*40}
INCOME STATEMENT
{'─'*40}
Total Sales (Revenue): ${total_sales:,.2f}
Total Income: ${total_income:,.2f}
Total Expenses: ${total_expenses:,.2f}
{'─'*40}
Taxable Income: ${taxable_income:,.2f}

{'─'*40}
TAX CALCULATION
{'─'*40}
Tax Rate: 25%
Tax Due: ${tax_due:,.2f}

{'─'*40}
{'='*60}
This report is generated automatically by SmartGro ERP System
For official ZIMRA filing, please consult with your accountant.
{'='*60}
"""
    
    return report


# ==============================
# FINANCIAL CLOSING DASHBOARD
# ==============================
def financial_closing_dashboard():
    """Financial Closing Management Dashboard with REAL data"""
    
    st.title("Automated Financial Closing")
    st.caption("End-of-day, month-end, and year-end closing with real data")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("Access Denied. Only owners and managers can perform financial closing.")
        return
    
    init_closing_files()
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Daily Closing",
        "Month-End Closing",
        "Tax Reports",
        "Closing History"
    ])
    
    # ==============================
    # TAB 1: DAILY CLOSING
    # ==============================
    with tab1:
        st.markdown("## End-of-Day Closing")
        st.caption("Close the day's transactions and generate report")
        
        today_data = get_period_data("daily", datetime.now().year, datetime.now().month)
        today_data["period_type"] = "daily"
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Revenue", f"${today_data['total_revenue']:,.2f}")
        with col2:
            st.metric("Total Income", f"${today_data['total_income']:,.2f}")
        with col3:
            st.metric("Net Income", f"${today_data['net_income']:,.2f}")
        with col4:
            st.metric("Transactions", today_data['transaction_count'])
        
        st.markdown("---")
        st.warning("Performing daily closing will create a backup and generate a closing report.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Perform Daily Closing", type="primary", use_container_width=True):
                with st.spinner("Performing daily closing..."):
                    success, report_path, backup_path = perform_daily_close()
                    if success:
                        st.success("Daily closing completed successfully!")
                        st.info(f"Report saved: {report_path}")
                        st.info(f"Backup created: {backup_path}")
                        
                        with open(report_path, "rb") as f:
                            st.download_button(
                                label="Download Closing Report (PDF)",
                                data=f,
                                file_name=f"daily_close_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf"
                            )
                    else:
                        st.error("Daily closing failed")
        
        with col2:
            closing_files = list(CLOSING_DIR.glob("daily_close_*.pdf"))
            if closing_files:
                latest = max(closing_files, key=lambda x: x.stat().st_mtime)
                st.info(f"Last closing: {latest.name}")
    
    # ==============================
    # TAB 2: MONTH-END CLOSING
    # ==============================
    with tab2:
        st.markdown("## Month-End Closing")
        st.caption("Close the month's transactions and generate financial report")
        
        col1, col2 = st.columns(2)
        
        with col1:
            close_year = st.number_input("Year", min_value=2020, max_value=2030, value=datetime.now().year, key="month_close_year")
        
        with col2:
            close_month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1, key="month_close_month")
        
        month_data = get_period_data("monthly", close_year, close_month)
        month_data["period_type"] = "monthly"
        
        st.markdown("### Month Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Revenue", f"${month_data['total_revenue']:,.2f}")
        with col2:
            st.metric("Total Income", f"${month_data['total_income']:,.2f}")
        with col3:
            net_color = "normal" if month_data['net_income'] >= 0 else "inverse"
            st.metric("Net Income", f"${month_data['net_income']:,.2f}", delta_color=net_color)
        with col4:
            st.metric("Transactions", month_data['transaction_count'])
        
        st.markdown("---")
        st.warning("Month-end closing will create a backup and generate a comprehensive monthly report.")
        
        if st.button("Perform Month-End Closing", type="primary", use_container_width=True):
            with st.spinner("Performing month-end closing..."):
                success, report_path, backup_path = perform_monthly_close(close_year, close_month)
                if success:
                    st.success(f"Month-end closing completed for {close_year}-{close_month:02d}!")
                    st.info(f"Report saved: {report_path}")
                    st.info(f"Backup created: {backup_path}")
                    
                    with open(report_path, "rb") as f:
                        st.download_button(
                            label="Download Monthly Report (PDF)",
                            data=f,
                            file_name=f"monthly_close_{close_year}_{close_month:02d}.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.error("Month-end closing failed")
    
    # ==============================
    # TAB 3: TAX REPORTS
    # ==============================
    with tab3:
        st.markdown("## Tax Reports (ZIMRA Format)")
        st.caption("Generate tax reports for ZIMRA filing")
        
        col1, col2 = st.columns(2)
        
        with col1:
            tax_year = st.number_input("Tax Year", min_value=2020, max_value=2030, value=datetime.now().year, key="tax_year")
        
        with col2:
            tax_period = st.selectbox("Tax Period", ["Annual", "Quarterly"], key="tax_period")
        
        if st.button("Generate Tax Report", type="primary", use_container_width=True):
            with st.spinner("Generating tax report..."):
                tax_report = generate_tax_report(tax_year, tax_period.lower())
                
                st.text_area("Tax Report Preview", tax_report, height=400)
                
                st.download_button(
                    label="Download Tax Report (TXT)",
                    data=tax_report,
                    file_name=f"zimra_tax_report_{tax_year}_{tax_period.lower()}.txt",
                    mime="text/plain"
                )
        
        st.markdown("---")
        st.info("""
        **Tax Information:**
        - Corporate Tax Rate: 25%
        - VAT Rate: 15% (if applicable)
        - Filing deadlines: Check with ZIMRA for current deadlines
        
        **Note:** This report is for informational purposes. Please consult with your accountant for official filing.
        """)
    
    # ==============================
    # TAB 4: CLOSING HISTORY
    # ==============================
    with tab4:
        st.markdown("## Closing History")
        st.caption("View all previous closing reports and backups")
        
        closing_reports = list(CLOSING_DIR.glob("*.pdf"))
        
        if closing_reports:
            reports_data = []
            for report in closing_reports:
                reports_data.append({
                    "Filename": report.name,
                    "Size": f"{report.stat().st_size / 1024:.1f} KB",
                    "Modified": datetime.fromtimestamp(report.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
            
            reports_df = pd.DataFrame(reports_data)
            st.dataframe(reports_df, use_container_width=True, hide_index=True)
            
            selected_report = st.selectbox("Select Report to Download", [r["Filename"] for r in reports_data])
            if selected_report:
                report_path = CLOSING_DIR / selected_report
                with open(report_path, "rb") as f:
                    st.download_button(
                        label="Download Selected Report",
                        data=f,
                        file_name=selected_report,
                        mime="application/pdf"
                    )
        else:
            st.info("No closing reports found. Perform a closing to generate reports.")
        
        st.markdown("### Backup History")
        
        backups = list(BACKUP_DIR.iterdir())
        if backups:
            backup_data = []
            for backup in backups:
                backup_data.append({
                    "Backup Name": backup.name,
                    "Created": datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
            
            backup_df = pd.DataFrame(backup_data)
            st.dataframe(backup_df, use_container_width=True, hide_index=True)
        else:
            st.info("No backups found. Perform a closing to create backups.")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    financial_closing_dashboard()