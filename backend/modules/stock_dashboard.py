import streamlit as st
import pandas as pd
from backend.core.db_adapter import load_products

# ==============================
# DASHBOARD PAGE
# ==============================
def dashboard_page():

    st.title("SmartGro Dashboard")

    df = load_products()

    # ==========================
    # BASIC STATS
    # ==========================
    total_products = len(df)
    
    # Handle decimal stock values
    if not df.empty and "stock" in df.columns:
        # Ensure stock is numeric
        df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
        total_stock = df["stock"].sum()
    else:
        total_stock = 0

    if not df.empty and "stock" in df.columns and "price" in df.columns:
        # Ensure price is numeric
        df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
        # Create stock_value as numeric
        df["stock_value"] = df["stock"] * df["price"]
        total_value = df["stock_value"].sum()
    else:
        total_value = 0

    if not df.empty and "stock" in df.columns and "reorder_level" in df.columns:
        # Ensure reorder_level is numeric
        df["reorder_level"] = pd.to_numeric(df["reorder_level"], errors="coerce").fillna(0)
        low_stock = df[df["stock"] <= df["reorder_level"]]
    else:
        low_stock = pd.DataFrame()

    # ==========================
    # METRICS DISPLAY
    # ==========================
    col1, col2, col3 = st.columns(3)

    col1.metric("Total Products", total_products)
    col2.metric("Total Stock Units", f"{total_stock:.2f}" if isinstance(total_stock, float) and total_stock % 1 != 0 else int(total_stock))
    col3.metric("Stock Value ($)", f"${total_value:,.2f}")

    st.markdown("---")

    # ==========================
    # LOW STOCK ALERT
    # ==========================
    st.subheader("Low Stock Items")

    if not low_stock.empty:
        # Display with decimal formatting
        display_cols = ["barcode", "name", "stock", "reorder_level"]
        if "category" in low_stock.columns:
            display_cols.insert(2, "category")
        
        st.dataframe(
            low_stock[display_cols], 
            use_container_width=True,
            hide_index=True,
            column_config={
                "stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                "reorder_level": st.column_config.NumberColumn("Reorder Level", format="%.2f")
            }
        )
        
        # Show count of low stock items
        st.warning(f"⚠️ {len(low_stock)} products need reordering!")
    else:
        st.success("✅ All products are sufficiently stocked! 🎉")

    st.markdown("---")

    # ==========================
    # STOCK OVERVIEW
    # ==========================
    st.subheader("Inventory Overview")
    
    if not df.empty:
        # Ensure all numeric columns are properly typed
        numeric_cols = ["price", "stock", "reorder_level", "cost"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        # Create stock_value if it doesn't exist
        if "stock_value" not in df.columns:
            df["stock_value"] = df["stock"] * df["price"]
        
        # Display with decimal formatting for stock
        display_cols = []
        available_cols = ["barcode", "name", "category", "price", "stock", "reorder_level", "cost", "stock_value"]
        for col in available_cols:
            if col in df.columns:
                display_cols.append(col)
        
        st.dataframe(
            df[display_cols], 
            use_container_width=True,
            hide_index=True,
            column_config={
                "stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                "reorder_level": st.column_config.NumberColumn("Reorder Level", format="%.2f"),
                "stock_value": st.column_config.NumberColumn("Stock Value", format="$%.2f")
            }
        )
        
        # Show total products count
        st.caption(f"📊 Total products: {len(df)}")
    else:
        st.info("No products in inventory. Start by adding products in the Inventory Management page.")

    st.markdown("---")

    # ==========================
    # CATEGORY INSIGHT
    # ==========================
    st.subheader("Stock by Category")
    
    if not df.empty and "category" in df.columns and "stock" in df.columns:
        # Ensure stock is numeric
        df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
        
        # Group by category with decimal support
        category_summary = df.groupby("category")["stock"].sum().reset_index()
        category_summary = category_summary.sort_values("stock", ascending=False)
        
        # Display with decimal formatting
        st.dataframe(
            category_summary, 
            use_container_width=True,
            hide_index=True,
            column_config={
                "stock": st.column_config.NumberColumn("Total Stock", format="%.2f")
            }
        )
        
        # Show category count
        st.caption(f"📂 Total categories: {len(category_summary)}")
        
        # Optional: Add a bar chart for visual representation
        if len(category_summary) > 0:
            st.subheader("Stock Distribution by Category")
            # Create a bar chart
            chart_data = category_summary.set_index("category")
            st.bar_chart(chart_data)
    else:
        st.info("No categories found. Add categories to your products for better insights.")

    st.markdown("---")

    # ==========================
    # ADDITIONAL INSIGHTS (Optional)
    # ==========================
    with st.expander("📈 Additional Insights"):
        if not df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Most valuable products (by stock value)
                if "stock_value" in df.columns:
                    # Ensure stock_value is numeric
                    df["stock_value"] = pd.to_numeric(df["stock_value"], errors="coerce").fillna(0)
                    st.markdown("**Top 5 Most Valuable Products**")
                    top_value = df.nlargest(5, "stock_value")[["name", "stock_value"]]
                    st.dataframe(
                        top_value,
                        hide_index=True,
                        column_config={
                            "stock_value": st.column_config.NumberColumn("Value", format="$%.2f")
                        }
                    )
            
            with col2:
                # Top 5 products with highest stock
                st.markdown("**Top 5 Products by Stock**")
                # Ensure stock is numeric
                df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
                top_stock = df.nlargest(5, "stock")[["name", "stock"]]
                st.dataframe(
                    top_stock,
                    hide_index=True,
                    column_config={
                        "stock": st.column_config.NumberColumn("Stock", format="%.2f")
                    }
                )
            
            # Average stock per product
            avg_stock = df["stock"].mean()
            st.metric("Average Stock per Product", f"{avg_stock:.2f}" if avg_stock % 1 != 0 else int(avg_stock))
        else:
            st.info("Add products to see additional insights.")


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    dashboard_page()