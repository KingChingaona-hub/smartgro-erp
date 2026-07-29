# backend/customers/customers_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import re

from backend.core.db_adapter import load_customers, load_sales, load_products
from backend.modules.loyalty import (
    load_loyalty,
    get_top_loyalty_customers,
    get_birthday_customers,
    get_customer_loyalty_info,
    get_tier_benefits,
    save_loyalty
)
from backend.utils.utils import generate_whatsapp_promotion
from backend.utils.phone_utils import get_whatsapp_link


# ==============================
# HELPER FUNCTIONS
# ==============================

def to_float(value):
    """Safely convert value to float"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_str(value, default=""):
    """Safely convert value to string"""
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default


def get_customer_column(df):
    """Find customer name column"""
    if df is None or df.empty:
        return None
    for col in ["customer_name", "customer", "name", "client_name"]:
        if col in df.columns:
            return col
    return None


def get_phone_column(df):
    """Find phone column"""
    if df is None or df.empty:
        return None
    for col in ["phone", "customer_phone", "contact", "mobile"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    """Find amount column"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    """Find receipt number column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def extract_customers_from_sales(sales_df):
    """
    Extract unique customers from sales data.
    This is the primary source for customers since they are recorded during checkout.
    """
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()
    
    customer_col = get_customer_column(sales_df)
    phone_col = get_phone_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    
    if customer_col is None:
        return pd.DataFrame()
    
    # Use receipt-level deduplication to get unique customers
    if receipt_col and receipt_col in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        customer_data = unique_receipts[[customer_col]].copy()
        
        if phone_col and phone_col in sales_df.columns:
            customer_data["phone"] = unique_receipts[phone_col].astype(str)
        else:
            customer_data["phone"] = ""
    else:
        customer_data = sales_df[[customer_col]].copy()
        if phone_col and phone_col in sales_df.columns:
            customer_data["phone"] = sales_df[phone_col].astype(str)
        else:
            customer_data["phone"] = ""
    
    customer_data.columns = ["customer_name", "phone"]
    
    # Clean data - remove Walk-in and empty entries
    customer_data = customer_data.drop_duplicates(subset=["customer_name", "phone"])
    customer_data = customer_data[
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('walk-in', na=False) &
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('unknown', na=False) &
        (customer_data["customer_name"].astype(str).str.strip() != '') &
        (customer_data["customer_name"].astype(str).str.strip() != 'nan') &
        (customer_data["customer_name"].astype(str).str.strip() != 'None')
    ]
    
    return customer_data


def get_combined_customers(customers_df, sales_df):
    """Combine customers from both table and sales data."""
    sales_customers = extract_customers_from_sales(sales_df)
    
    if not sales_customers.empty:
        return sales_customers
    
    if customers_df is not None and not customers_df.empty:
        customer_col = get_customer_column(customers_df)
        phone_col = get_phone_column(customers_df)
        
        if customer_col:
            result = customers_df[[customer_col]].copy()
            result.columns = ["customer_name"]
            if phone_col and phone_col in customers_df.columns:
                result["phone"] = customers_df[phone_col].astype(str)
            else:
                result["phone"] = ""
            return result
    
    return pd.DataFrame()


def get_customer_total_spent(customer_name, sales_df):
    """Calculate total spent for a customer from sales data"""
    if sales_df is None or sales_df.empty:
        return 0
    
    customer_col = get_customer_column(sales_df)
    amount_col = get_amount_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    
    if customer_col is None or amount_col is None:
        return 0
    
    customer_sales = sales_df[sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)]
    
    if customer_sales.empty:
        return 0
    
    # Use unduplicated receipts for accurate total
    if receipt_col and receipt_col in customer_sales.columns:
        unique_receipts = customer_sales.drop_duplicates(subset=[receipt_col])
        return to_float(unique_receipts[amount_col].sum())
    
    return to_float(customer_sales[amount_col].sum())


def get_customer_total_orders(customer_name, sales_df):
    """Calculate total orders for a customer from sales data"""
    if sales_df is None or sales_df.empty:
        return 0
    
    customer_col = get_customer_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    
    if customer_col is None:
        return 0
    
    customer_sales = sales_df[sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)]
    
    if customer_sales.empty:
        return 0
    
    if receipt_col and receipt_col in customer_sales.columns:
        return len(customer_sales.drop_duplicates(subset=[receipt_col]))
    
    return len(customer_sales)


def get_customer_last_purchase(customer_name, sales_df):
    """Get last purchase date for a customer"""
    if sales_df is None or sales_df.empty:
        return None
    
    customer_col = get_customer_column(sales_df)
    date_col = None
    for col in ["date", "sale_date", "transaction_date"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if customer_col is None or date_col is None:
        return None
    
    customer_sales = sales_df[sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)]
    
    if customer_sales.empty:
        return None
    
    customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
    last_date = customer_sales[date_col].max()
    
    return last_date


def get_customer_products(customer_name, sales_df):
    """Get products purchased by a customer"""
    if sales_df is None or sales_df.empty:
        return []
    
    customer_col = get_customer_column(sales_df)
    
    if customer_col is None:
        return []
    
    customer_sales = sales_df[sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)]
    
    if customer_sales.empty:
        return []
    
    name_col = None
    for col in ["name", "product_name", "item_name"]:
        if col in customer_sales.columns:
            name_col = col
            break
    
    if name_col is None:
        return []
    
    return customer_sales[name_col].tolist()


def customers_dashboard():
    """Enhanced Customer Intelligence Dashboard - FIXED to use REAL data from sales"""
    
    st.title("Customer Intelligence Dashboard")
    st.caption("Track loyalty, spending patterns, and customer engagement")
    
    # Load data
    customers_df = load_customers()
    sales_df = load_sales()
    loyalty_df = load_loyalty()
    products_df = load_products()
    
    # ==============================
    # FIX: Extract customers from sales data
    # ==============================
    real_customers = get_combined_customers(customers_df, sales_df)
    
    if real_customers.empty:
        st.warning("No customer data found. Customers are recorded during sales checkout.")
        st.info("Tip: When making a sale, enter a customer name (not 'Walk-in') to build customer profiles.")
        return
    
    st.sidebar.markdown("### Customer Info")
    st.sidebar.write(f"Total Customers: {len(real_customers)}")
    st.sidebar.write(f"Total Sales: {len(sales_df)}")
    
    # ==============================
    # CUSTOMER LOYALTY SEARCH
    # ==============================
    st.markdown("## Customer Loyalty Lookup")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        search_term = st.text_input("Search by Name or Phone", placeholder="Enter customer name or phone...")
    
    with col2:
        if st.button("Search", use_container_width=True):
            if search_term:
                # Search in real customers
                results = real_customers[
                    real_customers["customer_name"].str.contains(search_term, case=False) |
                    real_customers["phone"].str.contains(search_term)
                ]
                
                if not results.empty:
                    st.session_state.search_results = results
                    st.success(f"Found {len(results)} customers")
                else:
                    st.error("No customers found")
                    st.session_state.search_results = None
    
    # Display search results
    if st.session_state.get("search_results") is not None:
        results = st.session_state.search_results
        
        if not results.empty:
            for idx, customer in results.iterrows():
                name = customer.get("customer_name", "Unknown")
                phone = customer.get("phone", "")
                
                with st.expander(f"{name} - {phone}"):
                    # Get customer metrics from sales
                    total_spent = get_customer_total_spent(name, sales_df)
                    total_orders = get_customer_total_orders(name, sales_df)
                    last_purchase = get_customer_last_purchase(name, sales_df)
                    products = get_customer_products(name, sales_df)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Spent", f"${total_spent:,.2f}")
                    with col2:
                        st.metric("Total Orders", total_orders)
                    with col3:
                        if last_purchase:
                            days = (datetime.now() - last_purchase).days
                            st.metric("Last Purchase", f"{days} days ago")
                        else:
                            st.metric("Last Purchase", "Never")
                    
                    if products:
                        unique_products = list(set(products))[:5]
                        st.write("**Products Purchased:**", ", ".join(unique_products))
    
    st.markdown("---")
    
    # ==============================
    # KEY METRICS - USING REAL DATA
    # ==============================
    st.markdown("## Key Metrics")
    
    total_customers = len(real_customers)
    
    # Calculate total spent from sales
    amount_col = get_amount_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    
    total_revenue = 0
    if not sales_df.empty and amount_col:
        if receipt_col and receipt_col in sales_df.columns:
            unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
            total_revenue = to_float(unique_receipts[amount_col].sum())
        else:
            total_revenue = to_float(sales_df[amount_col].sum())
    
    avg_spent = total_revenue / total_customers if total_customers > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Customers", total_customers)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("Avg Customer Spend", f"${avg_spent:.2f}")
    with col4:
        # Active customers (last 90 days)
        active_customers = 0
        date_col = None
        for col in ["date", "sale_date", "transaction_date"]:
            if col in sales_df.columns:
                date_col = col
                break
        
        if date_col and get_customer_column(sales_df):
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=90)
            recent_sales = sales_df[sales_df[date_col] >= cutoff]
            if not recent_sales.empty:
                customer_col = get_customer_column(sales_df)
                if customer_col:
                    active_customers = recent_sales[customer_col].nunique()
        st.metric("Active Customers (90 days)", active_customers)
    
    st.markdown("---")
    
    # ==============================
    # TOP CUSTOMERS BY SPENDING
    # ==============================
    st.markdown("## Top Customers by Spending")
    
    if not sales_df.empty:
        customer_col = get_customer_column(sales_df)
        amount_col = get_amount_column(sales_df)
        receipt_col = get_receipt_column(sales_df)
        
        if customer_col and amount_col:
            # Use unique receipts for accurate spending
            if receipt_col and receipt_col in sales_df.columns:
                unique_sales = sales_df.drop_duplicates(subset=[receipt_col])
            else:
                unique_sales = sales_df
            
            customer_spending = unique_sales.groupby(customer_col)[amount_col].sum().nlargest(10).reset_index()
            
            if not customer_spending.empty:
                fig_spend = px.bar(
                    customer_spending,
                    x=amount_col,
                    y=customer_col,
                    orientation="h",
                    title="Top 10 Customers by Spending",
                    color=amount_col,
                    color_continuous_scale="Greens",
                    text=amount_col
                )
                fig_spend.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
                fig_spend.update_layout(height=400, xaxis_title="Total Spent ($)", yaxis_title="")
                st.plotly_chart(fig_spend, use_container_width=True)
            else:
                st.info("No customer spending data available")
    else:
        st.info("No sales data available for spending trends")
    
    st.markdown("---")
    
    # ==============================
    # CUSTOMER LIST
    # ==============================
    st.markdown("## All Customers")
    
    st.dataframe(real_customers, use_container_width=True, hide_index=True)
    
    csv = real_customers.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Customer Data (CSV)",
        data=csv,
        file_name=f"customers_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
    
    st.markdown("---")
    
    # ==============================
    # WHATSAPP BULK MESSAGING
    # ==============================
    st.markdown("## WhatsApp Bulk Messaging")
    st.caption("Send promotions and notifications to customers via WhatsApp")
    
    if real_customers.empty:
        st.warning("No customers available for messaging")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        segment = st.selectbox(
            "Select Customer Segment",
            ["All Customers", "High Spenders", "Recent Customers", "Inactive Customers"],
            key="whatsapp_segment"
        )
    
    with col2:
        message_type = st.selectbox(
            "Message Type",
            ["Promotion", "General Announcement", "Custom Message"],
            key="whatsapp_message_type"
        )
    
    # Get filtered customer list based on segment
    filtered_customers = real_customers.copy()
    
    if segment == "High Spenders":
        # Get customers who have spent more than average
        avg_spent_calc = 0
        customer_col = get_customer_column(sales_df)
        amount_col = get_amount_column(sales_df)
        receipt_col = get_receipt_column(sales_df)
        
        if customer_col and amount_col and not sales_df.empty:
            if receipt_col and receipt_col in sales_df.columns:
                unique_sales = sales_df.drop_duplicates(subset=[receipt_col])
            else:
                unique_sales = sales_df
            
            customer_spending = unique_sales.groupby(customer_col)[amount_col].sum()
            avg_spent_calc = customer_spending.mean() if not customer_spending.empty else 0
            
            # Filter customers who spent more than average
            high_spenders = customer_spending[customer_spending > avg_spent_calc].index.tolist()
            filtered_customers = filtered_customers[filtered_customers["customer_name"].isin(high_spenders)]
    
    elif segment == "Recent Customers":
        # Customers who purchased in last 30 days
        date_col = None
        customer_col = get_customer_column(sales_df)
        for col in ["date", "sale_date", "transaction_date"]:
            if col in sales_df.columns:
                date_col = col
                break
        
        if date_col and customer_col:
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=30)
            recent_sales = sales_df[sales_df[date_col] >= cutoff]
            recent_customers = recent_sales[customer_col].unique().tolist()
            filtered_customers = filtered_customers[filtered_customers["customer_name"].isin(recent_customers)]
    
    elif segment == "Inactive Customers":
        # Customers who haven't purchased in 90 days
        date_col = None
        customer_col = get_customer_column(sales_df)
        for col in ["date", "sale_date", "transaction_date"]:
            if col in sales_df.columns:
                date_col = col
                break
        
        if date_col and customer_col:
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            cutoff = datetime.now() - timedelta(days=90)
            inactive_sales = sales_df[sales_df[date_col] < cutoff]
            inactive_customers = inactive_sales[customer_col].unique().tolist()
            # Only if they have no recent sales
            recent_sales = sales_df[sales_df[date_col] >= cutoff]
            recent_customers = recent_sales[customer_col].unique().tolist()
            inactive_customers = [c for c in inactive_customers if c not in recent_customers]
            filtered_customers = filtered_customers[filtered_customers["customer_name"].isin(inactive_customers)]
    
    # Message input
    final_message = ""
    
    if message_type == "Promotion":
        promo_message = st.text_area("Promotion Message", height=100, 
                                     placeholder="e.g., 20% OFF on all products this weekend!",
                                     key="promo_message")
        discount_code = st.text_input("Discount Code (optional)", placeholder="e.g., SAVE20", key="discount_code")
        
        if promo_message:
            final_message = promo_message
            if discount_code:
                final_message += f"\n\nUse code: {discount_code}"
            st.info(f"Preview:\n\n{final_message}")
    
    elif message_type == "General Announcement":
        announcement = st.text_area("Announcement", height=100, key="announcement")
        final_message = announcement
        if announcement:
            st.info(f"Preview:\n\n{announcement}")
    
    else:
        custom_message = st.text_area("Custom Message", height=100,
                                      placeholder="Type your custom message here...",
                                      key="custom_message")
        final_message = custom_message
        if custom_message:
            st.info(f"Preview:\n\n{custom_message}")
    
    # Display customer count
    customer_count = len(filtered_customers)
    st.info(f"This message will be sent to **{customer_count}** customers")
    
    # Show filtered customers
    if not filtered_customers.empty and customer_count > 0:
        with st.expander("View Recipient List"):
            st.dataframe(
                filtered_customers[["customer_name", "phone"]],
                use_container_width=True,
                hide_index=True
            )
    
    col1, col2 = st.columns(2)
    
    with col1:
        send_button = st.button("Generate WhatsApp Links", type="primary", use_container_width=True)
        
        if send_button:
            if filtered_customers.empty:
                st.error("No customers found in this segment")
            elif not final_message:
                st.error("Please enter a message to send")
            else:
                # Generate WhatsApp links for each customer
                whatsapp_links = []
                for _, customer in filtered_customers.iterrows():
                    phone = str(customer["phone"])
                    # Clean phone number
                    phone_clean = re.sub(r'\D', '', phone)
                    if phone_clean.startswith('0'):
                        phone_clean = '263' + phone_clean[1:]
                    elif not phone_clean.startswith('263'):
                        phone_clean = '263' + phone_clean
                    
                    name = customer.get("customer_name", "Customer")
                    encoded_message = final_message.replace(' ', '%20').replace('\n', '%0A')
                    whatsapp_link = f"https://wa.me/{phone_clean}?text={encoded_message}"
                    whatsapp_links.append({
                        "Customer": name,
                        "Phone": phone,
                        "WhatsApp Link": whatsapp_link
                    })
                
                # Display all WhatsApp links
                st.success(f"Generated {len(whatsapp_links)} WhatsApp links!")
                
                links_df = pd.DataFrame(whatsapp_links)
                
                # Display clickable links
                st.markdown("### Click to send messages")
                
                for idx, row in links_df.iterrows():
                    st.markdown(f"**{row['Customer']}** ({row['Phone']}): [Send WhatsApp]({row['WhatsApp Link']})")
                
                # Download all links as CSV
                csv_links = links_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download WhatsApp Links (CSV)",
                    data=csv_links,
                    file_name=f"whatsapp_links_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
                st.info("Click each link above to send the message via WhatsApp")
    
    with col2:
        # Export customer list for manual WhatsApp Broadcast
        if not real_customers.empty:
            csv_export = real_customers[["customer_name", "phone"]].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Customer List for WhatsApp Broadcast",
                data=csv_export,
                file_name=f"customers_for_whatsapp_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            st.caption("Import this CSV to WhatsApp Business for bulk broadcast")


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    customers_dashboard()