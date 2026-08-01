# backend/modules/sales_history.py
# Sales History with proper deduplication and product names

import streamlit as st
import pandas as pd
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
    """Sales History with proper deduplication and product names"""

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
    # FILTER SECTION
    # ==============================
    st.subheader("Filter Sales")

    col1, col2, col3 = st.columns(3)

    search_barcode = col1.text_input("Barcode")
    search_receipt = col2.text_input("Receipt No")
    search_name = col3.text_input("Product Name")

    filtered_df = df.copy()

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
    # SALES TABLE - WITH PRODUCT NAMES
    # ==============================
    st.subheader("Sales Records")

    # Define display columns without duplicates
    display_cols = []
    
    # List of columns to display with their display names
    col_map = {}
    
    # Date column
    date_col = find_column(filtered_df, ["sale_date", "date", "transaction_date"])
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
            if col in ["Total", "Profit"]:
                config[col] = st.column_config.NumberColumn(col, format="$%.2f")
            elif col == "Qty":
                config[col] = st.column_config.NumberColumn(col, format="%.2f")
            elif col == "Date":
                config[col] = st.column_config.DatetimeColumn(col, format="YYYY-MM-DD HH:mm")
        
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

    # Calculate totals from unique receipts for accurate revenue and profit
    if unique_receipts_df is not None and not unique_receipts_df.empty:
        total_col = find_column(unique_receipts_df, ["final_total", "total", "amount"])
        profit_col = find_column(unique_receipts_df, ["profit"])
        
        if total_col:
            total_sales = safe_float(unique_receipts_df[total_col].sum())
        else:
            total_sales = 0
            
        if profit_col:
            total_profit = safe_float(unique_receipts_df[profit_col].sum())
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
        receipt_df = df[
            df["receipt_no"]
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