import streamlit as st
import pandas as pd
from backend.core.db_adapter import load_sales


# ==============================
# SALES HISTORY PAGE
# ==============================
def sales_history_page():

    st.title("📜 Sales History")

    df = load_sales()

    if df.empty:
        st.warning("No sales recorded yet.")
        return

    # ==============================
    # FORCE SAFE NUMERIC
    # ==============================
    numeric_cols = ["items", "total", "profit"]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            ).fillna(0)

    # ==============================
    # FILTER SECTION
    # ==============================
    st.subheader("🔍 Filter Sales")

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
        # Check if column exists - try both 'name' and 'product_name'
        name_col = None
        if "name" in filtered_df.columns:
            name_col = "name"
        elif "product_name" in filtered_df.columns:
            name_col = "product_name"
        
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
    st.subheader("📊 Sales Records")

    st.dataframe(
        filtered_df,
        use_container_width=True
    )

    # ==============================
    # SUMMARY
    # ==============================
    st.markdown("---")
    st.subheader("📈 Summary")

    total_sales = float(filtered_df["total"].sum()) if "total" in filtered_df.columns else 0
    total_profit = float(filtered_df["profit"].sum()) if "profit" in filtered_df.columns else 0
    total_items = int(filtered_df["items"].sum()) if "items" in filtered_df.columns else 0

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Revenue ($)",
        f"{total_sales:,.2f}"
    )

    col2.metric(
        "Total Profit ($)",
        f"{total_profit:,.2f}"
    )

    col3.metric(
        "Items Sold",
        total_items
    )

    # ==============================
    # TOP PRODUCTS - FIXED for column names
    # ==============================
    st.markdown("---")
    st.subheader("📦 Top Products")

    # Determine which column names exist
    product_col = None
    name_col = None
    
    if "barcode" in filtered_df.columns:
        # Check for name column
        if "name" in filtered_df.columns:
            name_col = "name"
        elif "product_name" in filtered_df.columns:
            name_col = "product_name"
        
        if name_col:
            # Group by barcode and name
            top_products = (
                filtered_df
                .groupby(["barcode", name_col])
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
            
            # Rename columns for display
            top_products.columns = ["Barcode", "Product Name", "Items Sold", "Revenue", "Profit"]
            
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
            # Only barcode available
            top_products = (
                filtered_df
                .groupby("barcode")
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
            
            top_products.columns = ["Barcode", "Items Sold", "Revenue", "Profit"]
            
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
        st.info("No product data available")

    # ==============================
    # RECEIPT LOOKUP
    # ==============================
    st.markdown("---")
    st.subheader("🧾 Receipt Lookup")

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

            receipt_total = float(
                receipt_df["total"].sum()
            ) if "total" in receipt_df.columns else 0

            receipt_profit = float(
                receipt_df["profit"].sum()
            ) if "profit" in receipt_df.columns else 0

            st.success(
                f"✔ Receipt found | Revenue: ${receipt_total:.2f} | Profit: ${receipt_profit:.2f}"
            )

        else:
            st.error("Receipt not found")