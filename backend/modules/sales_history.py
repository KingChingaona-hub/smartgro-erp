# backend/modules/sales_history.py
# Sales History with proper deduplication

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
    """Sales History with proper deduplication"""

    st.title("Sales History")

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
    # DEDUPLICATE BY RECEIPT FOR TOTALS
    # ==============================
    receipt_col = find_column(df, ["receipt_no", "receipt", "transaction_id", "order_id"])
    
    # Create a unique receipts dataframe for accurate totals
    unique_receipts_df = None
    if receipt_col:
        # Get unique receipts with their totals
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

    if search_name:
        name_col = find_column(filtered_df, ["name", "product_name", "Product"])
        if name_col:
            filtered_df = filtered_df[
                filtered_df[name_col]
                .astype(str)
                .str.contains(search_name, case=False)
            ]

    st.markdown("---")

    # ==============================
    # SALES TABLE
    # ==============================
    st.subheader("Sales Records")

    # Display columns
    display_cols = []
    for col in ["receipt_no", "barcode", "name", "items", "total", "profit", "payment_method", "customer_name", "sale_date"]:
        if col in filtered_df.columns:
            display_cols.append(col)
    
    if display_cols:
        st.dataframe(
            filtered_df[display_cols],
            use_container_width=True,
            column_config={
                "total": st.column_config.NumberColumn("Total", format="$%.2f"),
                "profit": st.column_config.NumberColumn("Profit", format="$%.2f")
            }
        )

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
    
    # Items sold should sum all items (this is correct)
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
        "Items Sold",
        f"{total_items:,}"
    )

    col4.metric(
        "Transactions",
        f"{transactions:,}"
    )

    # ==============================
    # TOP PRODUCTS - FIXED
    # ==============================
    st.markdown("---")
    st.subheader("Top Products")

    name_col = find_column(filtered_df, ["name", "product_name", "Product"])
    
    if name_col:
        # Group by product name
        top_products = (
            filtered_df
            .groupby(name_col)
            .agg({
                "items": "sum",
                "total": "sum",
                "profit": "sum"
            })
            .reset_index()
            .sort_values(
                by="items",
                ascending=False
            )
            .head(10)
        )
        
        top_products.columns = ["Product Name", "Items Sold", "Revenue", "Profit"]
        
        st.dataframe(
            top_products,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
                "Profit": st.column_config.NumberColumn("Profit", format="$%.2f")
            }
        )
    else:
        st.info("No product name data available")

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
            st.dataframe(
                receipt_df,
                use_container_width=True
            )

            # Use first row of receipt for total (all rows in same receipt have same total)
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

            st.success(
                f"Receipt found | Revenue: ${receipt_total:.2f} | Profit: ${receipt_profit:.2f}"
            )

        else:
            st.error("Receipt not found")

    # ==============================
    # EXPORT
    # ==============================
    st.markdown("---")
    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Filtered Data (CSV)",
        data=csv,
        file_name=f"sales_history_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    sales_history_page()