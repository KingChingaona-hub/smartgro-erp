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
    get_cash_summary
)
from backend.analytics.pl_engine import profit_loss_account
from backend.admin.security import log_audit

# ==============================
# FILE PATHS
# ==============================
DATA_DIR = Path("data")
CLOSING_DIR = DATA_DIR / "closing_reports"
BACKUP_DIR = DATA_DIR / "backups"


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


def get_period_data(period_type, year, month=None, quarter=None):
    """Get REAL financial data for a period from PostgreSQL"""
    
    start_date, end_date = get_period_dates(period_type, year, month, quarter)
    
    # Load data from PostgreSQL
    sales_df = load_sales()
    expenses_df = load_expenses()
    purchases_df = load_purchases()
    customers_df = load_customers()
    debtors_df = load_debtors()
    products_df = load_products()
    
    # ============================================================
    # SALES DATA
    # ============================================================
    total_revenue = 0
    total_profit = 0
    transaction_count = 0
    items_sold = 0
    
    if not sales_df.empty:
        date_col = None
        for col in ["sale_date", "date", "transaction_date", "created_at"]:
            if col in sales_df.columns:
                date_col = col
                break
        
        if date_col:
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            sales_df = sales_df.dropna(subset=[date_col])
            
            period_sales = sales_df[(sales_df[date_col] >= start_date) & (sales_df[date_col] <= end_date)]
            
            if not period_sales.empty:
                total_col = "final_total" if "final_total" in period_sales.columns else "total" if "total" in period_sales.columns else None
                profit_col = "profit" if "profit" in period_sales.columns else None
                items_col = "items" if "items" in period_sales.columns else None
                receipt_col = "receipt_no" if "receipt_no" in period_sales.columns else None
                
                total_revenue = float(period_sales[total_col].sum()) if total_col else 0
                total_profit = float(period_sales[profit_col].sum()) if profit_col else 0
                items_sold = float(period_sales[items_col].sum()) if items_col else 0
                transaction_count = period_sales[receipt_col].nunique() if receipt_col else len(period_sales)
    
    # ============================================================
    # EXPENSES DATA
    # ============================================================
    total_expenses = 0
    if not expenses_df.empty and "expense_date" in expenses_df.columns:
        expenses_df["expense_date"] = pd.to_datetime(expenses_df["expense_date"], errors="coerce")
        period_expenses = expenses_df[(expenses_df["expense_date"] >= start_date) & (expenses_df["expense_date"] <= end_date)]
        total_expenses = float(period_expenses["amount"].sum()) if "amount" in period_expenses.columns and not period_expenses.empty else 0
    
    # ============================================================
    # PURCHASES DATA
    # ============================================================
    total_purchases = 0
    if not purchases_df.empty:
        date_col = None
        for col in ["date_ordered", "date", "order_date"]:
            if col in purchases_df.columns:
                date_col = col
                break
        
        if date_col:
            purchases_df[date_col] = pd.to_datetime(purchases_df[date_col], errors="coerce")
            period_purchases = purchases_df[(purchases_df[date_col] >= start_date) & (purchases_df[date_col] <= end_date)]
            total_purchases = float(period_purchases["total_cost"].sum()) if "total_cost" in period_purchases.columns and not period_purchases.empty else 0
    
    # ============================================================
    # NEW CUSTOMERS
    # ============================================================
    new_customers = 0
    if not customers_df.empty:
        date_col = None
        for col in ["created_at", "join_date", "date_joined", "last_purchase_date"]:
            if col in customers_df.columns:
                date_col = col
                break
        
        if date_col:
            customers_df[date_col] = pd.to_datetime(customers_df[date_col], errors="coerce")
            new_customers = len(customers_df[customers_df[date_col] >= start_date])
        else:
            new_customers = len(customers_df)
    
    net_profit = total_revenue - total_expenses
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
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
        ["Total Expenses", f"${data['total_expenses']:,.2f}"],
        ["Net Profit", f"${data['net_profit']:,.2f}"],
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
    expenses_df = load_expenses()
    
    total_sales = 0
    if not sales_df.empty:
        date_col = None
        for col in ["sale_date", "date", "transaction_date"]:
            if col in sales_df.columns:
                date_col = col
                break
        
        if date_col:
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            period_sales = sales_df[(sales_df[date_col] >= start_date) & (sales_df[date_col] <= end_date)]
            total_col = "final_total" if "final_total" in period_sales.columns else "total" if "total" in period_sales.columns else None
            total_sales = float(period_sales[total_col].sum()) if total_col and not period_sales.empty else 0
    
    total_expenses = 0
    if not expenses_df.empty and "expense_date" in expenses_df.columns:
        expenses_df["expense_date"] = pd.to_datetime(expenses_df["expense_date"], errors="coerce")
        period_expenses = expenses_df[(expenses_df["expense_date"] >= start_date) & (expenses_df["expense_date"] <= end_date)]
        total_expenses = float(period_expenses["amount"].sum()) if "amount" in period_expenses.columns and not period_expenses.empty else 0
    
    taxable_income = total_sales - total_expenses
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
    
    st.title("💰 Automated Financial Closing")
    st.caption("End-of-day, month-end, and year-end closing with real data")
    
    role = st.session_state.get("role", "cashier")
    
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can perform financial closing.")
        return
    
    init_closing_files()
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "📅 Daily Closing",
        "📆 Month-End Closing",
        "📊 Tax Reports",
        "📁 Closing History"
    ])
    
    # ==============================
    # TAB 1: DAILY CLOSING
    # ==============================
    with tab1:
        st.markdown("## 📅 End-of-Day Closing")
        st.caption("Close the day's transactions and generate report")
        
        today_data = get_period_data("daily", datetime.now().year, datetime.now().month)
        today_data["period_type"] = "daily"
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Today's Revenue", f"${today_data['total_revenue']:,.2f}")
        with col2:
            st.metric("Today's Profit", f"${today_data['total_profit']:,.2f}")
        with col3:
            st.metric("Transactions", today_data['transaction_count'])
        with col4:
            st.metric("Items Sold", today_data['items_sold'])
        
        st.markdown("---")
        st.warning("⚠️ Performing daily closing will create a backup and generate a closing report.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📅 Perform Daily Closing", type="primary", use_container_width=True):
                with st.spinner("Performing daily closing..."):
                    success, report_path, backup_path = perform_daily_close()
                    if success:
                        st.success("✅ Daily closing completed successfully!")
                        st.info(f"📄 Report saved: {report_path}")
                        st.info(f"💾 Backup created: {backup_path}")
                        
                        with open(report_path, "rb") as f:
                            st.download_button(
                                label="📥 Download Closing Report (PDF)",
                                data=f,
                                file_name=f"daily_close_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf"
                            )
                    else:
                        st.error("❌ Daily closing failed")
        
        with col2:
            closing_files = list(CLOSING_DIR.glob("daily_close_*.pdf"))
            if closing_files:
                latest = max(closing_files, key=lambda x: x.stat().st_mtime)
                st.info(f"📁 Last closing: {latest.name}")
    
    # ==============================
    # TAB 2: MONTH-END CLOSING
    # ==============================
    with tab2:
        st.markdown("## 📆 Month-End Closing")
        st.caption("Close the month's transactions and generate financial report")
        
        col1, col2 = st.columns(2)
        
        with col1:
            close_year = st.number_input("Year", min_value=2020, max_value=2030, value=datetime.now().year, key="month_close_year")
        
        with col2:
            close_month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1, key="month_close_month")
        
        month_data = get_period_data("monthly", close_year, close_month)
        month_data["period_type"] = "monthly"
        
        st.markdown("### 📊 Month Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Revenue", f"${month_data['total_revenue']:,.2f}")
        with col2:
            st.metric("Expenses", f"${month_data['total_expenses']:,.2f}")
        with col3:
            net_color = "normal" if month_data['net_profit'] >= 0 else "inverse"
            st.metric("Net Profit", f"${month_data['net_profit']:,.2f}", delta_color=net_color)
        with col4:
            st.metric("Transactions", month_data['transaction_count'])
        
        st.markdown("---")
        st.warning("⚠️ Month-end closing will create a backup and generate a comprehensive monthly report.")
        
        if st.button("📆 Perform Month-End Closing", type="primary", use_container_width=True):
            with st.spinner("Performing month-end closing..."):
                success, report_path, backup_path = perform_monthly_close(close_year, close_month)
                if success:
                    st.success(f"✅ Month-end closing completed for {close_year}-{close_month:02d}!")
                    st.info(f"📄 Report saved: {report_path}")
                    st.info(f"💾 Backup created: {backup_path}")
                    
                    with open(report_path, "rb") as f:
                        st.download_button(
                            label="📥 Download Monthly Report (PDF)",
                            data=f,
                            file_name=f"monthly_close_{close_year}_{close_month:02d}.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.error("❌ Month-end closing failed")
    
    # ==============================
    # TAB 3: TAX REPORTS
    # ==============================
    with tab3:
        st.markdown("## 📊 Tax Reports (ZIMRA Format)")
        st.caption("Generate tax reports for ZIMRA filing")
        
        col1, col2 = st.columns(2)
        
        with col1:
            tax_year = st.number_input("Tax Year", min_value=2020, max_value=2030, value=datetime.now().year, key="tax_year")
        
        with col2:
            tax_period = st.selectbox("Tax Period", ["Annual", "Quarterly"], key="tax_period")
        
        if st.button("📊 Generate Tax Report", type="primary", use_container_width=True):
            with st.spinner("Generating tax report..."):
                tax_report = generate_tax_report(tax_year, tax_period.lower())
                
                st.text_area("Tax Report Preview", tax_report, height=400)
                
                st.download_button(
                    label="📥 Download Tax Report (TXT)",
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
        st.markdown("## 📁 Closing History")
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
                        label="📥 Download Selected Report",
                        data=f,
                        file_name=selected_report,
                        mime="application/pdf"
                    )
        else:
            st.info("No closing reports found. Perform a closing to generate reports.")
        
        st.markdown("### 💾 Backup History")
        
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