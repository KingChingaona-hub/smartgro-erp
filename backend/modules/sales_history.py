# backend/modules/sales_history.py
# Sales History with proper deduplication, product names, and date filters

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from backend.core.db_adapter import load_sales


# ==============================
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def find_column(df, possible_names, default=None):
    """Find the first column that matches any of the possible names"""
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return None


# ==============================
# SALES HISTORY PAGE
# ==============================
def sales_history_page():
    """Sales History with proper deduplication, product names, and date filters"""

    st.title("Sales History")
    st.caption("View all sales transactions with product details")

    df = load_sales()

    if df.empty:
        st.warning("No sales recorded yet.")
        return

    # ==============================
    # FORCE SAFE NUMERIC
    # ==============================
    numeric_cols = ["items", "total", "profit", "final_total"]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).fillna(0)

    # ==============================
    # FIND DATE COLUMN
    # ==============================
    date_col = find_column(df, ["sale_date", "date", "transaction_date", "created_at"])
    
    # Convert date column to datetime
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        # Create a date-only column for filtering
        df["date_only"] = df[date_col].dt.date

    # ==============================
    # FIND PRODUCT NAME COLUMN
    # ==============================
    product_name_col = None
    for col in ["product_name", "name", "Product", "item_name"]:
        if col in df.columns:
            product_name_col = col
            break
    
    # ==============================
    # DEDUPLICATION - GET UNIQUE RECEIPTS
    # ==============================
    receipt_col = find_column(df, ["receipt_no", "receipt", "transaction_id", "order_id"])
    
    # Create unique receipts dataframe for accurate totals
    unique_receipts_df = None
    if receipt_col:
        # Get unique receipts with their totals (keep first row per receipt)
        unique_receipts_df = df.drop_duplicates(subset=[receipt_col], keep="first").copy()
    
    # ==============================
    # FILTER SECTION - WITH DATE RANGE
    # ==============================
    st.subheader("Filter Sales")
    
    # Quick date filters
    st.markdown("### Quick Date Filters")
    
    quick_filters = st.columns(7)
    
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    this_month_start = today.replace(day=1)
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    
    filter_type = None
    filter_date = None
    
    with quick_filters[0]:
        if st.button("Today", use_container_width=True, key="filter_today"):
            filter_type = "today"
    with quick_filters[1]:
        if st.button("Yesterday", use_container_width=True, key="filter_yesterday"):
            filter_type = "yesterday"
    with quick_filters[2]:
        if st.button("Last 7 Days", use_container_width=True, key="filter_7days"):
            filter_type = "last_7_days"
    with quick_filters[3]:
        if st.button("Last 30 Days", use_container_width=True, key="filter_30days"):
            filter_type = "last_30_days"
    with quick_filters[4]:
        if st.button("This Month", use_container_width=True, key="filter_this_month"):
            filter_type = "this_month"
    with quick_filters[5]:
        if st.button("Last Month", use_container_width=True, key="filter_last_month"):
            filter_type = "last_month"
    with quick_filters[6]:
        if st.button("Clear", use_container_width=True, key="filter_clear"):
            filter_type = "clear"
    
    st.markdown("---")
    
    # Custom date range
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=today - timedelta(days=30) if filter_type is None else None,
            key="start_date_filter"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=today,
            key="end_date_filter"
        )
    
    with col3:
        st.caption("Apply custom date range or use quick filters above")
        if st.button("Apply Date Range", use_container_width=True, key="apply_date_range"):
            filter_type = "custom"
    
    st.markdown("---")
    
    # Apply filters to dataframe
    filtered_df = df.copy()
    
    # Apply quick filter
    if filter_type == "today":
        filtered_df = filtered_df[filtered_df["date_only"] == today]
        st.info(f"Showing sales for Today: {today.strftime('%Y-%m-%d')}")
    elif filter_type == "yesterday":
        filtered_df = filtered_df[filtered_df["date_only"] == yesterday]
        st.info(f"Showing sales for Yesterday: {yesterday.strftime('%Y-%m-%d')}")
    elif filter_type == "last_7_days":
        filtered_df = filtered_df[filtered_df["date_only"] >= last_7_days]
        st.info(f"Showing sales for Last 7 Days: {last_7_days.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    elif filter_type == "last_30_days":
        filtered_df = filtered_df[filtered_df["date_only"] >= last_30_days]
        st.info(f"Showing sales for Last 30 Days: {last_30_days.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    elif filter_type == "this_month":
        filtered_df = filtered_df[filtered_df["date_only"] >= this_month_start]
        st.info(f"Showing sales for This Month: {this_month_start.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    elif filter_type == "last_month":
        filtered_df = filtered_df[
            (filtered_df["date_only"] >= last_month_start) & 
            (filtered_df["date_only"] < this_month_start)
        ]
        st.info(f"Showing sales for Last Month: {last_month_start.strftime('%Y-%m-%d')} to {(this_month_start - timedelta(days=1)).strftime('%Y-%m-%d')}")
    elif filter_type == "clear":
        filtered_df = df.copy()
        st.info("Showing all sales")
    elif filter_type == "custom":
        if start_date and end_date:
            filtered_df = filtered_df[
                (filtered_df["date_only"] >= start_date) & 
                (filtered_df["date_only"] <= end_date)
            ]
            st.info(f"Showing sales from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Additional search filters
    col1, col2, col3 = st.columns(3)

    search_barcode = col1.text_input("Barcode")
    search_receipt = col2.text_input("Receipt No")
    search_name = col3.text_input("Product Name")

    if search_barcode:
        filtered_df = filtered_df[
            filtered_df["barcode"]
            .astype(str)
            .str.contains(search_barcode, case=False)
        ]

    if search_receipt:
        filtered_df = filtered_df[
            filtered_df["receipt_no"]
            .astype(str)
            .str.contains(search_receipt, case=False)
        ]

    if search_name and product_name_col:
        filtered_df = filtered_df[
            filtered_df[product_name_col]
            .astype(str)
            .str.contains(search_name, case=False)
        ]

    st.markdown("---")

    # ==============================
    # SALES TABLE - WITH ALL COLUMNS
    # ==============================
    st.subheader("Sales Records")
    
    # Show filter summary
    if filter_type and filter_type != "clear":
        st.caption(f"Filtered: {len(filtered_df)} item rows")
    else:
        st.caption(f"Total: {len(filtered_df)} item rows")

    # Define display columns - ALL columns
    display_cols = []
    col_map = {}
    
    # Date column
    if date_col:
        col_map[date_col] = "Date"
    
    # Receipt column
    receipt_display = find_column(filtered_df, ["receipt_no", "receipt", "transaction_id"])
    if receipt_display:
        col_map[receipt_display] = "Receipt No"
    
    # Product name column
    if product_name_col:
        col_map[product_name_col] = "Product"
    
    # Barcode column
    barcode_col = find_column(filtered_df, ["barcode", "product_barcode"])
    if barcode_col:
        col_map[barcode_col] = "Barcode"
    
    # Quantity column
    qty_col = find_column(filtered_df, ["items", "quantity", "qty"])
    if qty_col:
        col_map[qty_col] = "Qty"
    
    # Price column
    price_col = find_column(filtered_df, ["price", "unit_price", "selling_price"])
    if price_col:
        col_map[price_col] = "Price"
    
    # Total column
    total_col = find_column(filtered_df, ["final_total", "total", "amount"])
    if total_col:
        col_map[total_col] = "Total"
    
    # Profit column
    profit_col = find_column(filtered_df, ["profit"])
    if profit_col:
        col_map[profit_col] = "Profit"
    
    # Payment method
    payment_col = find_column(filtered_df, ["payment_method", "payment_type"])
    if payment_col:
        col_map[payment_col] = "Payment"
    
    # Customer column
    customer_col = find_column(filtered_df, ["customer_name", "customer", "Customer"])
    if customer_col:
        col_map[customer_col] = "Customer"
    
    # Customer phone
    phone_col = find_column(filtered_df, ["customer_phone", "phone", "Phone"])
    if phone_col:
        col_map[phone_col] = "Phone"
    
    # Cashier
    cashier_col = find_column(filtered_df, ["cashier", "user", "username"])
    if cashier_col:
        col_map[cashier_col] = "Cashier"
    
    # Shift ID
    shift_col = find_column(filtered_df, ["shift_id", "shift"])
    if shift_col:
        col_map[shift_col] = "Shift"
    
    # Notes
    notes_col = find_column(filtered_df, ["notes", "note", "description"])
    if notes_col:
        col_map[notes_col] = "Notes"
    
    # Get the column names from the map
    display_cols = list(col_map.keys())
    
    if display_cols:
        # Create a clean display dataframe with unique columns only
        display_df = filtered_df[display_cols].copy()
        
        # Rename columns for display
        display_df = display_df.rename(columns=col_map)
        
        # Configure columns
        config = {}
        for col in display_df.columns:
            if col in ["Total", "Profit", "Price"]:
                config[col] = st.column_config.NumberColumn(col, format="$%.2f")
            elif col == "Qty":
                config[col] = st.column_config.NumberColumn(col, format="%.2f")
            elif col in ["Date", date_col]:
                if date_col in display_df.columns:
                    config["Date"] = st.column_config.DatetimeColumn("Date", format="YYYY-MM-DD HH:mm")
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config=config
        )
        
        # Show count
        st.caption(f"Showing {len(display_df)} item rows")
    else:
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # ==============================
    # SUMMARY - USING UNIQUE RECEIPTS
    # ==============================
    st.markdown("---")
    st.subheader("Summary")

    # Get filtered unique receipts for accurate totals
    if receipt_col:
        filtered_unique_receipts = filtered_df.drop_duplicates(subset=[receipt_col], keep="first").copy()
        total_col = find_column(filtered_unique_receipts, ["final_total", "total", "amount"])
        profit_col = find_column(filtered_unique_receipts, ["profit"])
        
        if total_col:
            total_sales = safe_float(filtered_unique_receipts[total_col].sum())
        else:
            total_sales = 0
            
        if profit_col:
            total_profit = safe_float(filtered_unique_receipts[profit_col].sum())
        else:
            total_profit = 0
    else:
        total_col = find_column(filtered_df, ["final_total", "total", "amount"])
        profit_col = find_column(filtered_df, ["profit"])
        
        if total_col:
            total_sales = safe_float(filtered_df[total_col].sum())
        else:
            total_sales = 0
            
        if profit_col:
            total_profit = safe_float(filtered_df[profit_col].sum())
        else:
            total_profit = 0
    
    # Items sold - sum all items
    items_col = find_column(filtered_df, ["items", "quantity", "qty"])
    if items_col:
        total_items = safe_int(filtered_df[items_col].sum())
    else:
        total_items = 0
    
    # Transaction count from unique receipts
    if receipt_col:
        transactions = filtered_df[receipt_col].nunique()
    else:
        transactions = len(filtered_df)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Revenue",
        f"${total_sales:,.2f}"
    )

    col2.metric(
        "Total Profit",
        f"${total_profit:,.2f}"
    )

    col3.metric(
        "Total Items Sold",
        f"{total_items:,}"
    )

    col4.metric(
        "Transactions",
        f"{transactions:,}"
    )

    # ==============================
    # TOP PRODUCTS - WITH PRODUCT NAMES
    # ==============================
    st.markdown("---")
    st.subheader("Top Products")
    
    if product_name_col:
        # Group by product name
        top_products = (
            filtered_df
            .groupby(product_name_col)
            .agg({
                "items": "sum",
                "total": "sum",
                "profit": "sum"
            })
            .reset_index()
            .sort_values(
                by="total",
                ascending=False
            )
            .head(10)
        )
        
        top_products.columns = ["Product", "Items Sold", "Revenue", "Profit"]
        
        st.dataframe(
            top_products,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Product": st.column_config.TextColumn("Product"),
                "Items Sold": st.column_config.NumberColumn("Items Sold", format="%.2f"),
                "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                "Profit": st.column_config.NumberColumn("Profit", format="$%.2f")
            }
        )
        
        # Chart of top products
        if not top_products.empty:
            st.markdown("### Top Products Chart")
            chart_data = top_products[["Product", "Items Sold"]].head(10)
            st.bar_chart(chart_data.set_index("Product"))
    else:
        st.warning("Product name column not found. Available columns: " + ", ".join(df.columns.tolist()))

    # ==============================
    # RECEIPT LOOKUP
    # ==============================
    st.markdown("---")
    st.subheader("Receipt Lookup")

    receipt_search = st.text_input(
        "Enter Receipt Number"
    )

    if receipt_search:
        receipt_df = filtered_df[
            filtered_df["receipt_no"]
            .astype(str) == receipt_search
        ]

        if not receipt_df.empty:
            # Rename product column for display
            display_receipt = receipt_df.copy()
            if product_name_col and product_name_col in display_receipt.columns:
                display_receipt = display_receipt.rename(columns={product_name_col: "Product"})
            
            st.dataframe(
                display_receipt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Product": "Product Name",
                    "items": st.column_config.NumberColumn("Qty", format="%.2f"),
                    "total": st.column_config.NumberColumn("Total", format="$%.2f"),
                    "profit": st.column_config.NumberColumn("Profit", format="$%.2f")
                }
            )

            # Use first row of receipt for total
            total_col = find_column(receipt_df, ["final_total", "total", "amount"])
            profit_col = find_column(receipt_df, ["profit"])
            
            if total_col:
                receipt_total = safe_float(receipt_df.iloc[0][total_col])
            else:
                receipt_total = 0
                
            if profit_col:
                receipt_profit = safe_float(receipt_df.iloc[0][profit_col])
            else:
                receipt_profit = 0

            item_count = len(receipt_df)

            st.success(
                f"Receipt found | {item_count} items | Revenue: ${receipt_total:.2f} | Profit: ${receipt_profit:.2f}"
            )

        else:
            st.error("Receipt not found")

    # ==============================
    # EXPORT
    # ==============================
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Filtered Data (CSV)",
            data=csv,
            file_name=f"sales_history_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Export top products
        if product_name_col:
            top_products_export = (
                filtered_df
                .groupby(product_name_col)
                .agg({
                    "items": "sum",
                    "total": "sum",
                    "profit": "sum"
                })
                .reset_index()
                .sort_values(by="total", ascending=False)
            )
            top_products_export.columns = ["Product", "Items Sold", "Revenue", "Profit"]
            csv_products = top_products_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Top Products (CSV)",
                data=csv_products,
                file_name=f"top_products_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    sales_history_page()