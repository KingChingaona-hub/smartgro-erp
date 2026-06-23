import streamlit as st
import pandas as pd
from backend.core.db_adapter import load_products

# ==============================
# DASHBOARD PAGE
# ==============================
def dashboard_page():

    st.title("📊 SmartGro Dashboard")

    df = load_products()

    # ==========================
    # BASIC STATS
    # ==========================
    total_products = len(df)
    total_stock = df["stock"].sum()

    df["stock_value"] = df["stock"] * df["price"]
    total_value = df["stock_value"].sum()

    low_stock = df[df["stock"] <= df["reorder_level"]]

    # ==========================
    # METRICS DISPLAY
    # ==========================
    col1, col2, col3 = st.columns(3)

    col1.metric("Total Products", total_products)
    col2.metric("Total Stock Units", total_stock)
    col3.metric("Stock Value ($)", f"{total_value:.2f}")

    st.markdown("---")

    # ==========================
    # LOW STOCK ALERT
    # ==========================
    st.subheader("⚠️ Low Stock Items")

    if not low_stock.empty:
        st.dataframe(low_stock[["barcode", "name", "stock", "reorder_level"]])
    else:
        st.success("No low stock items 🎉")

    st.markdown("---")

    # ==========================
    # STOCK OVERVIEW
    # ==========================
    st.subheader("📦 Inventory Overview")
    st.dataframe(df, use_container_width=True)

    # ==========================
    # CATEGORY INSIGHT
    # ==========================
    st.subheader("📂 Stock by Category")

    category_summary = df.groupby("category")["stock"].sum().reset_index()
    st.dataframe(category_summary, use_container_width=True)