import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from backend.core.db_adapter import (
    load_sales, 
    load_products, 
    load_purchases,
    load_shifts,
    load_cash,
    get_all_active_shifts,
    to_float,
    get_active_shift_id
)
from backend.utils.utils import get_whatsapp_link, generate_whatsapp_receipt
from backend.utils.phone_utils import validate_zimbabwe_phone

# ==============================
# MOBILE RESPONSIVE DASHBOARD
# ==============================

def is_mobile():
    """Detect if user is on mobile device"""
    try:
        from streamlit import runtime
        if runtime.exists():
            user_agent = st.context.headers.get("User-Agent", "")
            mobile_keywords = ["Mobile", "Android", "iPhone", "iPad", "iPod", "BlackBerry", "Windows Phone"]
            return any(keyword in user_agent for keyword in mobile_keywords)
    except:
        pass
    return False


def get_mobile_css():
    """Return mobile-optimized CSS"""
    return """
    <style>
        /* Mobile optimizations */
        @media only screen and (max-width: 768px) {
            .main .block-container {
                padding: 1rem !important;
            }
            h1 {
                font-size: 1.5rem !important;
            }
            h2 {
                font-size: 1.3rem !important;
            }
            .stMetric {
                text-align: center;
            }
            .stButton button {
                width: 100% !important;
                padding: 0.75rem !important;
                font-size: 1rem !important;
            }
            div[data-testid="column"] {
                padding: 0.25rem !important;
            }
        }
        
        /* WhatsApp button styling */
        .whatsapp-btn {
            background: #25D366;
            color: white;
            border: none;
            border-radius: 30px;
            padding: 12px 20px;
            cursor: pointer;
            font-weight: bold;
            text-decoration: none;
            display: inline-block;
            text-align: center;
            margin: 5px 0;
            width: 100%;
        }
        .whatsapp-btn:hover {
            background: #128C7E;
            transform: scale(1.02);
            transition: all 0.3s ease;
        }
        
        /* Alert cards */
        .alert-critical {
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
            color: white;
            border-radius: 12px;
            padding: 12px;
            margin: 8px 0;
        }
        .alert-warning {
            background: linear-gradient(135deg, #ffd93d 0%, #f9ca24 100%);
            color: #333;
            border-radius: 12px;
            padding: 12px;
            margin: 8px 0;
        }
        .alert-info {
            background: linear-gradient(135deg, #6c5ce7 0%, #5b4cc9 100%);
            color: white;
            border-radius: 12px;
            padding: 12px;
            margin: 8px 0;
        }
        
        /* Quick stats cards */
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin: 8px 0;
        }
        .stat-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #2d3436;
        }
        .stat-label {
            font-size: 0.8rem;
            color: #636e72;
            margin-top: 5px;
        }
        
        /* Mobile navigation */
        .mobile-nav {
            display: flex;
            overflow-x: auto;
            gap: 8px;
            padding: 10px 0;
            margin-bottom: 15px;
        }
        .mobile-nav-item {
            background: #f0f0f0;
            padding: 8px 16px;
            border-radius: 25px;
            white-space: nowrap;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .mobile-nav-item.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
    </style>
    """


def get_whatsapp_alert_message(alert_type, data):
    """Generate WhatsApp alert message for different alert types"""
    
    if alert_type == "stock_out":
        products = data.get("products", [])
        if not products:
            return None
        message = f"🚨 *STOCK OUT ALERT* 🚨\n\n"
        message += f"The following products are OUT OF STOCK:\n\n"
        for p in products[:5]:
            message += f"❌ {p['name']}\n"
        if len(products) > 5:
            message += f"\n... and {len(products) - 5} more items\n"
        message += f"\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"🔔 *Immediate action required!*\n"
        return message
    
    elif alert_type == "low_stock":
        products = data.get("products", [])
        if not products:
            return None
        message = f"⚠️ *LOW STOCK ALERT* ⚠️\n\n"
        message += f"The following products need reordering:\n\n"
        for p in products[:5]:
            message += f"📦 {p['name']}: {p['stock']} units left (Reorder at {p['reorder_level']})\n"
        if len(products) > 5:
            message += f"\n... and {len(products) - 5} more items\n"
        message += f"\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        return message
    
    elif alert_type == "daily_summary":
        sales = data.get("sales", 0)
        profit = data.get("profit", 0)
        transactions = data.get("transactions", 0)
        top_product = data.get("top_product", "N/A")
        shift_id = data.get("shift_id", "N/A")
        
        message = f"📊 *Daily Sales Summary* 📊\n\n"
        message += f"📅 Date: {datetime.now().strftime('%Y-%m-%d')}\n"
        message += f"💰 Total Sales: ${sales:,.2f}\n"
        message += f"📈 Profit: ${profit:,.2f}\n"
        message += f"🛒 Transactions: {transactions}\n"
        message += f"🏆 Top Product: {top_product}\n"
        if shift_id != "N/A":
            message += f"🆔 Shift: {shift_id}\n"
        message += f"\n📱 *SmartGro ERP* - Aziel Investments"
        return message
    
    elif alert_type == "purchase_approval":
        po_number = data.get("po_number", "")
        supplier = data.get("supplier", "")
        total = data.get("total", 0)
        items = data.get("items", [])
        
        message = f"📋 *Purchase Order Approval Required* 📋\n\n"
        message += f"PO Number: {po_number}\n"
        message += f"Supplier: {supplier}\n"
        message += f"Total Value: ${total:,.2f}\n"
        message += f"Items: {len(items)}\n\n"
        message += f"Reply 'APPROVE {po_number}' to approve\n"
        message += f"Reply 'REJECT {po_number}' to reject"
        return message
    
    elif alert_type == "shift_summary":
        shift_data = data.get("shift_data", {})
        shift_id = shift_data.get("shift_id", "N/A")
        cashier = shift_data.get("cashier_name", "N/A")
        revenue = shift_data.get("total_revenue", 0)
        profit = shift_data.get("profit", 0)
        transactions = shift_data.get("transactions", 0)
        cash_sales = shift_data.get("cash_sales", 0)
        credit_sales = shift_data.get("credit_sales", 0)
        
        message = f"🕐 *Shift Summary* 🕐\n\n"
        message += f"Shift ID: {shift_id}\n"
        message += f"Cashier: {cashier}\n"
        message += f"💰 Revenue: ${revenue:,.2f}\n"
        message += f"📈 Profit: ${profit:,.2f}\n"
        message += f"🛒 Transactions: {transactions}\n"
        message += f"💵 Cash Sales: ${cash_sales:,.2f}\n"
        message += f"💳 Credit Sales: ${credit_sales:,.2f}\n"
        message += f"\n📱 *SmartGro ERP* - Aziel Investments"
        return message
    
    return None


def send_whatsapp_alert(phone, alert_type, data):
    """Send WhatsApp alert to a specific number"""
    message = get_whatsapp_alert_message(alert_type, data)
    if message:
        return get_whatsapp_link(phone, message)
    return None


def get_todays_stats():
    """
    Get today's sales statistics from actual data.
    Uses shift-linked sales for accurate reporting.
    """
    sales_df = load_sales()
    shifts_df = load_shifts()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Default empty stats
    empty_stats = {
        "sales": 0,
        "profit": 0,
        "transactions": 0,
        "items_sold": 0,
        "top_product": "N/A",
        "avg_transaction": 0,
        "shift_id": "N/A",
        "cash_sales": 0,
        "credit_sales": 0
    }
    
    if sales_df.empty:
        return empty_stats
    
    # Ensure date column exists
    if "date" not in sales_df.columns and "sale_date" in sales_df.columns:
        sales_df["date"] = sales_df["sale_date"]
    
    if "date" not in sales_df.columns:
        return empty_stats
    
    # Convert to datetime and filter for today
    sales_df["date"] = pd.to_datetime(sales_df["date"])
    today_mask = sales_df["date"].dt.strftime("%Y-%m-%d") == today
    today_sales = sales_df[today_mask]
    
    if today_sales.empty:
        return empty_stats
    
    # Calculate metrics
    total_sales = 0
    total_profit = 0
    items_sold = 0
    transactions = 0
    cash_sales = 0
    credit_sales = 0
    
    # Use final_total or total
    if "final_total" in today_sales.columns:
        total_sales = to_float(today_sales["final_total"].sum())
    elif "total" in today_sales.columns:
        total_sales = to_float(today_sales["total"].sum())
    
    if "profit" in today_sales.columns:
        total_profit = to_float(today_sales["profit"].sum())
    
    if "items" in today_sales.columns:
        items_sold = int(today_sales["items"].sum())
    
    # Get unique transactions (receipt numbers)
    if "receipt_no" in today_sales.columns:
        transactions = today_sales["receipt_no"].nunique()
    else:
        transactions = len(today_sales)
    
    # Get cash vs credit sales
    if "payment_method" in today_sales.columns:
        cash_sales = to_float(today_sales[today_sales["payment_method"] == "CASH"]["final_total"].sum())
        credit_sales = to_float(today_sales[today_sales["payment_method"] == "CREDIT"]["final_total"].sum())
    
    # Get top product
    top_product = "N/A"
    if "name" in today_sales.columns and "items" in today_sales.columns:
        product_sales = today_sales.groupby("name")["items"].sum()
        if not product_sales.empty:
            top_product = product_sales.nlargest(1).index[0]
    
    # Get shift ID from today's sales
    shift_id = "N/A"
    if "shift_id" in today_sales.columns:
        shift_ids = today_sales["shift_id"].dropna().unique()
        if len(shift_ids) > 0:
            shift_id = shift_ids[0]
    
    return {
        "sales": total_sales,
        "profit": total_profit,
        "transactions": transactions,
        "items_sold": items_sold,
        "top_product": top_product,
        "avg_transaction": total_sales / transactions if transactions > 0 else 0,
        "shift_id": shift_id,
        "cash_sales": cash_sales,
        "credit_sales": credit_sales
    }


def get_weekly_stats():
    """Get weekly sales statistics"""
    sales_df = load_sales()
    
    if sales_df.empty:
        return {
            "sales": 0,
            "profit": 0,
            "transactions": 0,
            "daily_average": 0
        }
    
    # Ensure date column exists
    if "date" not in sales_df.columns and "sale_date" in sales_df.columns:
        sales_df["date"] = sales_df["sale_date"]
    
    if "date" not in sales_df.columns:
        return {"sales": 0, "profit": 0, "transactions": 0, "daily_average": 0}
    
    sales_df["date"] = pd.to_datetime(sales_df["date"])
    week_ago = datetime.now() - timedelta(days=7)
    week_sales = sales_df[sales_df["date"] >= week_ago]
    
    if week_sales.empty:
        return {"sales": 0, "profit": 0, "transactions": 0, "daily_average": 0}
    
    total_sales = to_float(week_sales["final_total"].sum()) if "final_total" in week_sales.columns else to_float(week_sales["total"].sum())
    total_profit = to_float(week_sales["profit"].sum()) if "profit" in week_sales.columns else 0
    
    if "receipt_no" in week_sales.columns:
        transactions = week_sales["receipt_no"].nunique()
    else:
        transactions = len(week_sales)
    
    return {
        "sales": total_sales,
        "profit": total_profit,
        "transactions": transactions,
        "daily_average": total_sales / 7
    }


def get_monthly_stats():
    """Get monthly sales statistics"""
    sales_df = load_sales()
    
    if sales_df.empty:
        return {"sales": 0, "profit": 0, "transactions": 0}
    
    # Ensure date column exists
    if "date" not in sales_df.columns and "sale_date" in sales_df.columns:
        sales_df["date"] = sales_df["sale_date"]
    
    if "date" not in sales_df.columns:
        return {"sales": 0, "profit": 0, "transactions": 0}
    
    sales_df["date"] = pd.to_datetime(sales_df["date"])
    current_month = datetime.now().strftime("%Y-%m")
    month_sales = sales_df[sales_df["date"].dt.strftime("%Y-%m") == current_month]
    
    if month_sales.empty:
        return {"sales": 0, "profit": 0, "transactions": 0}
    
    total_sales = to_float(month_sales["final_total"].sum()) if "final_total" in month_sales.columns else to_float(month_sales["total"].sum())
    total_profit = to_float(month_sales["profit"].sum()) if "profit" in month_sales.columns else 0
    
    if "receipt_no" in month_sales.columns:
        transactions = month_sales["receipt_no"].nunique()
    else:
        transactions = len(month_sales)
    
    return {
        "sales": total_sales,
        "profit": total_profit,
        "transactions": transactions
    }


def get_shift_summary():
    """Get current shift summary"""
    shifts_df = load_shifts()
    
    if shifts_df.empty:
        return {
            "active_shift": None,
            "total_shifts": 0,
            "total_revenue": 0,
            "total_profit": 0,
            "total_transactions": 0
        }
    
    # Get active shifts
    active_shifts = shifts_df[shifts_df["status"] == "OPEN"]
    active_shift = None
    if not active_shifts.empty:
        active_shift = active_shifts.iloc[0].to_dict()
    
    # Get closed shifts
    closed_shifts = shifts_df[shifts_df["status"] == "CLOSED"]
    
    total_revenue = to_float(shifts_df["total_revenue"].sum()) if "total_revenue" in shifts_df.columns else 0
    total_profit = to_float(shifts_df["profit"].sum()) if "profit" in shifts_df.columns else 0
    total_transactions = int(shifts_df["transactions"].sum()) if "transactions" in shifts_df.columns else 0
    
    return {
        "active_shift": active_shift,
        "total_shifts": len(shifts_df),
        "active_shifts": len(active_shifts),
        "closed_shifts": len(closed_shifts),
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_transactions": total_transactions
    }


def get_stock_alerts():
    """Get current stock alerts"""
    products_df = load_products()
    
    if products_df.empty:
        return {"critical": [], "warning": []}
    
    out_of_stock = products_df[products_df["stock"] == 0].to_dict('records')
    low_stock = products_df[
        (products_df["stock"] > 0) & 
        (products_df["stock"] <= products_df["reorder_level"])
    ].to_dict('records')
    
    return {
        "critical": out_of_stock,
        "warning": low_stock
    }


def get_pending_purchases():
    """Get pending purchase orders for approval"""
    purchases_df = load_purchases()
    
    if purchases_df.empty:
        return []
    
    pending = purchases_df[purchases_df["status"] == "PENDING"]
    pending_pos = pending.groupby("po_number").agg({
        "supplier": "first",
        "total_cost": "sum",
        "product_name": "count"
    }).reset_index()
    
    return pending_pos.to_dict('records')


def mobile_dashboard():
    """Mobile Responsive Dashboard with WhatsApp Alerts"""
    
    # Apply mobile CSS
    st.markdown(get_mobile_css(), unsafe_allow_html=True)
    
    # Check if mobile
    mobile_view = is_mobile()
    
    # Title
    st.title("📱 SmartGro Mobile")
    st.caption("Real-time business insights at your fingertips")
    
    # Mobile navigation
    nav_options = ["Dashboard", "Alerts", "WhatsApp", "Reports", "Shifts"]
    nav_cols = st.columns(len(nav_options))
    
    if "mobile_tab" not in st.session_state:
        st.session_state.mobile_tab = "Dashboard"
    
    for idx, option in enumerate(nav_options):
        with nav_cols[idx]:
            if st.button(option, key=f"nav_{option}", use_container_width=True):
                st.session_state.mobile_tab = option
    
    st.markdown("---")
    
    # ==============================
    # DASHBOARD TAB
    # ==============================
    if st.session_state.mobile_tab == "Dashboard":
        st.markdown("## 📊 Today's Overview")
        
        stats = get_todays_stats()
        weekly = get_weekly_stats()
        monthly = get_monthly_stats()
        shift_summary = get_shift_summary()
        
        # Active shift status
        active_shift = shift_summary.get("active_shift")
        if active_shift:
            st.info(f"🟢 Active Shift: {active_shift.get('shift_id', 'N/A')} - {active_shift.get('cashier_name', 'Unknown')}")
        else:
            st.warning("⚠️ No active shift")
        
        # Quick stats in a grid
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">${stats['sales']:,.0f}</div>
                <div class="stat-label">Today's Sales</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">${stats['profit']:,.0f}</div>
                <div class="stat-label">Today's Profit</div>
            </div>
            """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{stats['transactions']}</div>
                <div class="stat-label">Transactions</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-value">{stats['items_sold']}</div>
                <div class="stat-label">Items Sold</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Weekly and Monthly stats
        st.markdown("## 📈 Period Summary")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Weekly Sales", f"${weekly['sales']:,.0f}", delta=f"${weekly['daily_average']:,.0f}/day")
        with col2:
            st.metric("Weekly Profit", f"${weekly['profit']:,.0f}")
        with col3:
            st.metric("Monthly Sales", f"${monthly['sales']:,.0f}")
        
        # Stock alerts summary
        alerts = get_stock_alerts()
        
        if alerts["critical"] or alerts["warning"]:
            st.markdown("## ⚠️ Stock Alerts")
            
            if alerts["critical"]:
                st.markdown(f"""
                <div class="alert-critical">
                    🚨 <strong>{len(alerts['critical'])} products OUT OF STOCK</strong><br>
                    Immediate action required!
                </div>
                """, unsafe_allow_html=True)
            
            if alerts["warning"]:
                st.markdown(f"""
                <div class="alert-warning">
                    ⚠️ <strong>{len(alerts['warning'])} products low on stock</strong><br>
                    Reorder soon to avoid stockouts.
                </div>
                """, unsafe_allow_html=True)
        
        # Top product
        if stats['top_product'] != "N/A":
            st.markdown(f"""
            <div class="alert-info">
                🏆 <strong>Top Selling Today</strong><br>
                {stats['top_product']}
            </div>
            """, unsafe_allow_html=True)
        
        # Pending approvals
        pending = get_pending_purchases()
        if pending:
            st.markdown("## 📋 Pending Approvals")
            for po in pending[:3]:
                st.markdown(f"""
                <div class="stat-card">
                    <strong>PO: {po['po_number']}</strong><br>
                    Supplier: {po['supplier']}<br>
                    Value: ${po['total_cost']:,.2f}<br>
                    Items: {po['product_name']}
                </div>
                """, unsafe_allow_html=True)
    
    # ==============================
    # ALERTS TAB
    # ==============================
    elif st.session_state.mobile_tab == "Alerts":
        st.markdown("## 🔔 Real-time Alerts")
        
        alerts = get_stock_alerts()
        
        # Critical alerts
        if alerts["critical"]:
            st.markdown("### 🚨 Critical Alerts")
            for product in alerts["critical"]:
                st.error(f"**{product['name']}** - OUT OF STOCK!\nReorder immediately.")
        
        # Warning alerts
        if alerts["warning"]:
            st.markdown("### ⚠️ Warning Alerts")
            for product in alerts["warning"][:10]:
                st.warning(f"**{product['name']}** - Only {product['stock']} units left (Reorder at {product['reorder_level']})")
        
        if not alerts["critical"] and not alerts["warning"]:
            st.success("✅ No active alerts! All stock levels are healthy.")
        
        # Pending purchase approvals
        pending = get_pending_purchases()
        if pending:
            st.markdown("### 📋 Pending Approvals")
            for po in pending:
                with st.expander(f"PO: {po['po_number']} - {po['supplier']}"):
                    st.write(f"**Total Value:** ${po['total_cost']:,.2f}")
                    st.write(f"**Items:** {po['product_name']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Approve", key=f"approve_{po['po_number']}"):
                            st.success(f"PO {po['po_number']} approved!")
                    with col2:
                        if st.button(f"❌ Reject", key=f"reject_{po['po_number']}"):
                            st.warning(f"PO {po['po_number']} rejected")
    
    # ==============================
    # WHATSAPP TAB
    # ==============================
    elif st.session_state.mobile_tab == "WhatsApp":
        st.markdown("## 📱 WhatsApp Notifications")
        st.caption("Receive real-time alerts on WhatsApp")
        
        # Phone number input
        st.markdown("### Configure WhatsApp Alerts")
        
        phone = st.text_input("Your WhatsApp Number", 
                             placeholder="0777123456",
                             help="Enter Zimbabwe phone number")
        
        if phone:
            valid, standardized, msg = validate_zimbabwe_phone(phone)
            if valid:
                st.success(f"✅ Valid number: {standardized}")
                
                # Alert preferences
                st.markdown("### Select Alerts to Receive")
                
                col1, col2 = st.columns(2)
                with col1:
                    stock_out_alerts = st.checkbox("🚨 Stock Out Alerts", value=True)
                    low_stock_alerts = st.checkbox("⚠️ Low Stock Alerts", value=True)
                with col2:
                    daily_summary = st.checkbox("📊 Daily Sales Summary", value=True)
                    shift_summary_alert = st.checkbox("🕐 Shift Summary", value=True)
                
                # Test button
                if st.button("📱 Send Test WhatsApp Message", use_container_width=True):
                    test_message = f"✅ *SmartGro ERP Test*\n\nYour WhatsApp alerts are now configured!\n\nYou will receive real-time notifications for:\n"
                    if stock_out_alerts:
                        test_message += "• Stock out alerts\n"
                    if low_stock_alerts:
                        test_message += "• Low stock alerts\n"
                    if daily_summary:
                        test_message += "• Daily sales summary\n"
                    if shift_summary_alert:
                        test_message += "• Shift summaries\n"
                    test_message += f"\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    link = get_whatsapp_link(standardized, test_message)
                    if link:
                        st.markdown(f'<a href="{link}" target="_blank"><button class="whatsapp-btn">📱 Send Test Message</button></a>', unsafe_allow_html=True)
                
                # Save settings button
                if st.button("💾 Save Alert Settings", type="primary", use_container_width=True):
                    st.session_state.whatsapp_number = standardized
                    st.session_state.alert_prefs = {
                        "stock_out": stock_out_alerts,
                        "low_stock": low_stock_alerts,
                        "daily_summary": daily_summary,
                        "shift_summary": shift_summary_alert
                    }
                    st.success("✅ Alert settings saved!")
            else:
                st.error(f"❌ {msg}")
        
        # Quick send section
        st.markdown("---")
        st.markdown("### 📤 Quick WhatsApp Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            stats = get_todays_stats()
            summary_msg = get_whatsapp_alert_message("daily_summary", stats)
            if summary_msg:
                link = get_whatsapp_link(phone if phone else "0772123456", summary_msg)
                if link:
                    st.markdown(f'<a href="{link}" target="_blank"><button class="whatsapp-btn">📊 Send Daily Summary</button></a>', unsafe_allow_html=True)
        
        with col2:
            alerts = get_stock_alerts()
            if alerts["critical"]:
                stock_msg = get_whatsapp_alert_message("stock_out", {"products": alerts["critical"]})
                if stock_msg:
                    link = get_whatsapp_link(phone if phone else "0772123456", stock_msg)
                    if link:
                        st.markdown(f'<a href="{link}" target="_blank"><button class="whatsapp-btn">🚨 Send Stock Alert</button></a>', unsafe_allow_html=True)
    
    # ==============================
    # REPORTS TAB
    # ==============================
    elif st.session_state.mobile_tab == "Reports":
        st.markdown("## 📈 Mobile Reports")
        
        report_type = st.selectbox("Select Report", 
                                   ["Today's Sales", "Weekly Sales", "Monthly Sales", "Low Stock Report", "Pending Orders"])
        
        if report_type == "Today's Sales":
            stats = get_todays_stats()
            
            st.markdown(f"""
            ### Sales Summary
            | Metric | Value |
            |--------|-------|
            | Total Sales | ${stats['sales']:,.2f} |
            | Total Profit | ${stats['profit']:,.2f} |
            | Transactions | {stats['transactions']} |
            | Items Sold | {stats['items_sold']} |
            | Avg Transaction | ${stats['avg_transaction']:.2f} |
            | Top Product | {stats['top_product']} |
            | Cash Sales | ${stats['cash_sales']:,.2f} |
            | Credit Sales | ${stats['credit_sales']:,.2f} |
            | Shift ID | {stats['shift_id']} |
            """)
            
            # Share via WhatsApp
            share_msg = f"📊 *Daily Sales Report*\n\n"
            share_msg += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
            share_msg += f"Sales: ${stats['sales']:,.2f}\n"
            share_msg += f"Profit: ${stats['profit']:,.2f}\n"
            share_msg += f"Transactions: {stats['transactions']}\n"
            share_msg += f"Top Product: {stats['top_product']}\n"
            
            if st.button("📱 Share via WhatsApp", use_container_width=True):
                phone = st.session_state.get("whatsapp_number", "0772123456")
                link = get_whatsapp_link(phone, share_msg)
                if link:
                    st.markdown(f'<a href="{link}" target="_blank"><button class="whatsapp-btn">📱 Share Report</button></a>', unsafe_allow_html=True)
        
        elif report_type == "Weekly Sales":
            stats = get_weekly_stats()
            
            st.markdown(f"""
            ### Weekly Sales Summary
            | Metric | Value |
            |--------|-------|
            | Total Sales | ${stats['sales']:,.2f} |
            | Total Profit | ${stats['profit']:,.2f} |
            | Transactions | {stats['transactions']} |
            | Daily Average | ${stats['daily_average']:.2f} |
            """)
        
        elif report_type == "Monthly Sales":
            stats = get_monthly_stats()
            
            st.markdown(f"""
            ### Monthly Sales Summary
            | Metric | Value |
            |--------|-------|
            | Total Sales | ${stats['sales']:,.2f} |
            | Total Profit | ${stats['profit']:,.2f} |
            | Transactions | {stats['transactions']} |
            """)
        
        elif report_type == "Low Stock Report":
            alerts = get_stock_alerts()
            
            if alerts["warning"]:
                st.markdown("### Low Stock Items")
                for product in alerts["warning"]:
                    st.write(f"• **{product['name']}**: {product['stock']} units (Reorder at {product['reorder_level']})")
            else:
                st.success("No low stock items")
        
        elif report_type == "Pending Orders":
            pending = get_pending_purchases()
            if pending:
                for po in pending:
                    st.markdown(f"""
                    **PO: {po['po_number']}**  
                    Supplier: {po['supplier']}  
                    Value: ${po['total_cost']:,.2f}  
                    Items: {po['product_name']}
                    ---
                    """)
            else:
                st.info("No pending orders")
    
    # ==============================
    # SHIFTS TAB
    # ==============================
    elif st.session_state.mobile_tab == "Shifts":
        st.markdown("## 🕐 Shift Management")
        
        shift_summary = get_shift_summary()
        
        # Shift summary stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Shifts", shift_summary["total_shifts"])
        with col2:
            st.metric("Active Shifts", shift_summary["active_shifts"])
        with col3:
            st.metric("Closed Shifts", shift_summary["closed_shifts"])
        
        st.markdown("---")
        
        # Active shifts
        shifts_df = load_shifts()
        active_shifts = shifts_df[shifts_df["status"] == "OPEN"] if not shifts_df.empty else pd.DataFrame()
        
        if not active_shifts.empty:
            st.markdown("### 🟢 Active Shifts")
            for _, shift in active_shifts.iterrows():
                with st.expander(f"Shift: {shift['shift_id']} - {shift.get('cashier_name', 'Unknown')}"):
                    st.write(f"**Cashier:** {shift.get('cashier_name', 'N/A')}")
                    st.write(f"**Started:** {shift.get('start_time', 'N/A')}")
                    st.write(f"**Opening Cash:** ${to_float(shift.get('opening_cash', 0)):,.2f}")
                    st.write(f"**Current Revenue:** ${to_float(shift.get('total_revenue', 0)):,.2f}")
                    st.write(f"**Transactions:** {int(shift.get('transactions', 0))}")
        
        # Recent closed shifts
        closed_shifts = shifts_df[shifts_df["status"] == "CLOSED"] if not shifts_df.empty else pd.DataFrame()
        
        if not closed_shifts.empty:
            st.markdown("### 📋 Recent Closed Shifts")
            recent = closed_shifts.head(10)
            for _, shift in recent.iterrows():
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**{shift.get('shift_id', 'N/A')}**")
                with col2:
                    st.write(f"Cashier: {shift.get('cashier_name', 'N/A')}")
                with col3:
                    st.write(f"Revenue: ${to_float(shift.get('total_revenue', 0)):,.2f}")
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ==============================
# ALERT SENDER (Background)
# ==============================
def send_auto_whatsapp_alerts():
    """Automatically send WhatsApp alerts based on preferences"""
    settings = st.session_state.get("alert_prefs", {})
    phone = st.session_state.get("whatsapp_number", "")
    
    if not phone or not settings:
        return
    
    alerts = get_stock_alerts()
    
    # Stock out alerts
    if settings.get("stock_out", False) and alerts["critical"]:
        message = get_whatsapp_alert_message("stock_out", {"products": alerts["critical"]})
        if message:
            link = get_whatsapp_link(phone, message)
            print(f"Would send stock alert to {phone}")
    
    # Low stock alerts
    if settings.get("low_stock", False) and alerts["warning"]:
        message = get_whatsapp_alert_message("low_stock", {"products": alerts["warning"]})
        if message:
            link = get_whatsapp_link(phone, message)
            print(f"Would send low stock alert to {phone}")
    
    # Daily summary (run once per day)
    if settings.get("daily_summary", False):
        stats = get_todays_stats()
        if stats["sales"] > 0:
            message = get_whatsapp_alert_message("daily_summary", stats)
            if message:
                link = get_whatsapp_link(phone, message)
                print(f"Would send daily summary to {phone}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    mobile_dashboard()