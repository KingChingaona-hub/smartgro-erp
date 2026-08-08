import streamlit as st
import pandas as pd
from datetime import datetime
from backend.core.db_adapter import load_purchases, load_products


# ==============================
# HELPER: Convert Decimal to float
# ==============================
def to_float(value):
    """Safely convert Decimal or any value to float"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_numeric(df, columns):
    """Convert multiple columns to float safely"""
    for col in columns:
        if col in df.columns:
            df[col] = df[col].apply(to_float)
    return df


def find_column(df, possible_names, default=None):
    """Find the first column that matches any of the possible names"""
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return default


# ==============================
# PURCHASES DASHBOARD
# ==============================
def purchases_dashboard():
    """Purchases Dashboard with analytics"""
    
    st.title("Purchases Dashboard")
    st.caption("Analytics and insights for all purchase orders")
    
    df = load_purchases()
    
    if df.empty:
        st.warning("No purchases recorded yet. Go to Purchases page to create purchase orders.")
        return
    
    # Load products to get selling prices
    products_df = load_products()
    
    # ==============================
    # DETERMINE COLUMN NAMES
    # ==============================
    
    # Quantity column
    qty_col = find_column(df, ["quantity_ordered", "quantity", "items"])
    
    # Cost column
    cost_col = find_column(df, ["cost_price", "cost", "unit_cost"])
    
    # Total cost column
    total_cost_col = find_column(df, ["total_cost", "total", "total_amount"])
    
    # Product name column
    product_col = find_column(df, ["product_name", "name", "item_name"])
    
    # Supplier column
    supplier_col = find_column(df, ["supplier", "supplier_name", "vendor"])
    
    # Status column
    status_col = find_column(df, ["status"])
    
    # Date column
    date_col = find_column(df, ["date_ordered", "order_date", "created_at", "date"])
    
    # ==============================
    # CONVERT ALL NUMERIC COLUMNS TO FLOAT
    # ==============================
    numeric_cols = ["quantity_ordered", "quantity_received", "cost_price", "total_cost", 
                   "quantity", "cost", "total", "total_amount", "items"]
    df = safe_numeric(df, numeric_cols)
    
    # Also convert product prices
    if not products_df.empty:
        products_df = safe_numeric(products_df, ["price", "cost", "stock"])
    
    # ==============================
    # CALCULATE TOTAL PURCHASE VALUE
    # ==============================
    if total_cost_col:
        total_purchase_value = df[total_cost_col].sum()
    elif qty_col and cost_col:
        df["calculated_total"] = df[qty_col] * df[cost_col]
        total_purchase_value = df["calculated_total"].sum()
    else:
        total_purchase_value = 0
    
    # ==============================
    # CALCULATE EXPECTED PROFIT
    # ==============================
    expected_profit = 0
    profit_details = []
    
    if product_col and qty_col and not products_df.empty:
        # Create a dictionary of product prices
        products_df["name_lower"] = products_df["name"].astype(str).str.lower().str.strip()
        price_dict = {}
        for _, row in products_df.iterrows():
            name = str(row["name"]).lower().strip()
            price_dict[name] = to_float(row.get("price", 0))
        
        # Calculate profit for each purchase row
        for idx, row in df.iterrows():
            product_name = str(row.get(product_col, "")).lower().strip()
            quantity = to_float(row.get(qty_col, 0))
            
            # Get cost
            if total_cost_col:
                cost = to_float(row.get(total_cost_col, 0))
            elif cost_col:
                cost = to_float(row.get(cost_col, 0)) * quantity
            else:
                cost = 0
            
            # Get selling price from products database
            selling_price = price_dict.get(product_name, 0)
            
            if selling_price > 0 and quantity > 0:
                expected_revenue = selling_price * quantity
                profit = expected_revenue - cost
                expected_profit += profit
                profit_details.append({
                    "Product": product_name.title(),
                    "Quantity": int(quantity),
                    "Cost": cost,
                    "Selling Price": selling_price,
                    "Expected Revenue": expected_revenue,
                    "Expected Profit": profit
                })
    
    # If no profit calculated from products, use markup estimate
    if expected_profit == 0 and total_purchase_value > 0:
        # Assume 30% markup
        expected_profit = total_purchase_value * 0.3
        st.info("Expected profit calculated using 30% estimated markup (selling prices not found in product database)")
    
    # Calculate total items
    if qty_col:
        total_items = df[qty_col].sum()
    else:
        total_items = 0
    
    # Get number of orders
    po_col = find_column(df, ["po_number", "purchase_order", "order_id"])
    if po_col:
        total_orders = df[po_col].nunique()
    else:
        total_orders = len(df)
    
    # Calculate received quantity
    received_col = find_column(df, ["quantity_received", "received", "received_qty"])
    if received_col:
        total_received = df[received_col].sum()
    else:
        total_received = 0
    
    # Calculate profit margin
    profit_margin = (expected_profit / total_purchase_value * 100) if total_purchase_value > 0 else 0
    
    # ==============================
    # FILTERS
    # ==============================
    st.markdown("## Filters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Filter by supplier
        if supplier_col:
            suppliers = ["All"] + sorted(df[supplier_col].dropna().unique().tolist())
            filter_supplier = st.selectbox("Filter by Supplier", suppliers, key="dash_supplier_filter")
        else:
            filter_supplier = "All"
    
    with col2:
        # Filter by status
        if status_col:
            statuses = ["All"] + sorted(df[status_col].dropna().unique().tolist())
            filter_status = st.selectbox("Filter by Status", statuses, key="dash_status_filter")
        else:
            filter_status = "All"
    
    with col3:
        # Filter by date
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
            min_date = df[date_col].min().date() if not df[date_col].isna().all() else datetime.now().date()
            max_date = df[date_col].max().date() if not df[date_col].isna().all() else datetime.now().date()
            date_range = st.date_input(
                "Date Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="dash_date_filter"
            )
        else:
            date_range = None
    
    # Apply filters
    filtered_df = df.copy()
    
    if filter_supplier != "All" and supplier_col:
        filtered_df = filtered_df[filtered_df[supplier_col] == filter_supplier]
    
    if filter_status != "All" and status_col:
        filtered_df = filtered_df[filtered_df[status_col] == filter_status]
    
    if date_range and len(date_range) == 2 and date_col:
        start_date, end_date = date_range
        filtered_df = filtered_df[
            (filtered_df[date_col].dt.date >= start_date) & 
            (filtered_df[date_col].dt.date <= end_date)
        ]
    
    # ==============================
    # DISPLAY METRICS
    # ==============================
    st.markdown("---")
    st.markdown("## Purchases Overview")
    
    # Calculate filtered metrics
    filtered_total = filtered_df[total_cost_col].sum() if total_cost_col and total_cost_col in filtered_df.columns else 0
    filtered_items = filtered_df[qty_col].sum() if qty_col and qty_col in filtered_df.columns else 0
    filtered_orders = filtered_df[po_col].nunique() if po_col and po_col in filtered_df.columns else len(filtered_df)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Total Purchase Value", f"${filtered_total:,.2f}")
    
    with col2:
        st.metric("Expected Profit", f"${expected_profit:,.2f}")
    
    with col3:
        st.metric("Items Purchased", f"{int(filtered_items):,}")
    
    with col4:
        st.metric("Purchase Orders", filtered_orders)
    
    with col5:
        if received_col and received_col in filtered_df.columns:
            received_total = filtered_df[received_col].sum()
            st.metric("Items Received", f"{int(received_total):,}")
        else:
            st.metric("Status", f"{filtered_orders} Orders")
    
    st.markdown("---")
    
    # Profit margin
    if profit_margin > 0:
        if profit_margin < 20:
            st.warning(f"Expected Profit Margin: {profit_margin:.1f}% (Consider increasing prices or negotiating better costs)")
        elif profit_margin > 40:
            st.success(f"Excellent Expected Profit Margin: {profit_margin:.1f}%")
        else:
            st.info(f"Expected Profit Margin: {profit_margin:.1f}%")
    
    # ==============================
    # SHOW PROFIT BREAKDOWN (if available)
    # ==============================
    if profit_details:
        st.markdown("---")
        st.markdown("## Expected Profit Breakdown by Product")
        
        profit_df = pd.DataFrame(profit_details)
        st.dataframe(profit_df, use_container_width=True, hide_index=True)
        
        # Chart of profit by product
        if not profit_df.empty:
            chart_df = profit_df.nlargest(10, "Expected Profit")[["Product", "Expected Profit"]]
            st.bar_chart(chart_df.set_index("Product"))
    
    # ==============================
    # TOP SUPPLIERS
    # ==============================
    st.markdown("---")
    st.markdown("## Supplier Analysis")
    
    if supplier_col and supplier_col in filtered_df.columns:
        # Get total purchases per supplier
        if total_cost_col and total_cost_col in filtered_df.columns:
            supplier_cost = filtered_df.groupby(supplier_col)[total_cost_col].sum().reset_index()
            supplier_cost.columns = ["Supplier", "Total Purchases"]
        else:
            supplier_cost = pd.DataFrame()
        
        # Get order counts
        if po_col and po_col in filtered_df.columns:
            supplier_orders = filtered_df.groupby(supplier_col)[po_col].nunique().reset_index()
            supplier_orders.columns = ["Supplier", "Orders"]
        else:
            supplier_orders = pd.DataFrame()
        
        if not supplier_cost.empty:
            if not supplier_orders.empty:
                supplier_summary = supplier_cost.merge(supplier_orders, on="Supplier", how="left")
            else:
                supplier_summary = supplier_cost
            
            supplier_summary = supplier_summary.sort_values("Total Purchases", ascending=False)
            
            st.dataframe(
                supplier_summary,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Total Purchases": st.column_config.NumberColumn("Total Purchases", format="$%.2f")
                }
            )
        else:
            st.info("Supplier cost data not available")
    else:
        st.info("Supplier data not available")
    
    # ==============================
    # TOP PRODUCTS
    # ==============================
    st.markdown("---")
    st.markdown("## Top Purchased Products")
    
    if product_col and product_col in filtered_df.columns and qty_col and qty_col in filtered_df.columns:
        top_products = filtered_df.groupby(product_col)[qty_col].sum().sort_values(ascending=False).head(10).reset_index()
        top_products.columns = ["Product", "Quantity Purchased"]
        top_products["Quantity Purchased"] = top_products["Quantity Purchased"].astype(int)
        
        st.dataframe(top_products, use_container_width=True, hide_index=True)
        
        # Chart
        if not top_products.empty:
            st.bar_chart(top_products.set_index("Product"))
    else:
        st.info("Product purchase data not available")
    
    # ==============================
    # ORDER STATUS BREAKDOWN
    # ==============================
    if status_col and status_col in filtered_df.columns:
        st.markdown("---")
        st.markdown("## Order Status Breakdown")
        
        status_breakdown = filtered_df[status_col].value_counts().reset_index()
        status_breakdown.columns = ["Status", "Count"]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.dataframe(status_breakdown, use_container_width=True, hide_index=True)
        
        with col2:
            st.metric("Total Orders", len(filtered_df))
            if po_col:
                unique_pos = filtered_df[po_col].nunique()
                st.metric("Unique POs", unique_pos)
    
    # ==============================
    # RECENT PURCHASES
    # ==============================
    st.markdown("---")
    st.markdown("## Recent Purchases")
    
    # Select columns for display
    display_cols = []
    if date_col and date_col in filtered_df.columns:
        display_cols.append(date_col)
    
    if supplier_col and supplier_col in filtered_df.columns:
        display_cols.append(supplier_col)
    
    if product_col and product_col in filtered_df.columns:
        display_cols.append(product_col)
    
    if qty_col and qty_col in filtered_df.columns:
        display_cols.append(qty_col)
    
    if total_cost_col and total_cost_col in filtered_df.columns:
        display_cols.append(total_cost_col)
    
    if status_col and status_col in filtered_df.columns:
        display_cols.append(status_col)
    
    if po_col and po_col in filtered_df.columns:
        display_cols.append(po_col)
    
    # Filter to existing columns
    available_cols = [col for col in display_cols if col in filtered_df.columns]
    
    if available_cols:
        # Sort by date
        if date_col and date_col in filtered_df.columns:
            recent_df = filtered_df.sort_values(date_col, ascending=False)
        else:
            recent_df = filtered_df
        
        # Display
        st.dataframe(
            recent_df[available_cols].head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                total_cost_col: st.column_config.NumberColumn("Total", format="$%.2f") if total_cost_col else None,
                qty_col: st.column_config.NumberColumn("Quantity", format="%.2f") if qty_col else None
            }
        )
        
        # Show total count
        st.caption(f"Showing {min(20, len(recent_df))} of {len(filtered_df)} records")
    else:
        st.dataframe(filtered_df.head(20), use_container_width=True, hide_index=True)
    
    # ==============================
    # DATA QUALITY TIPS
    # ==============================
    st.markdown("---")
    st.markdown("## Data Quality Tips")
    
    if expected_profit == 0 and not profit_details:
        st.warning("""
        **Expected profit not showing because:**
        
        1. **Products don't have selling prices** - Go to Inventory and add prices to your products
        2. **Product names don't match** - Make sure product names in purchases match exactly with inventory names
        3. **Missing purchase data** - Complete more purchases
        
        **To fix:**
        - Go to **Inventory** page and ensure all products have prices
        - Make sure product names are spelled consistently
        - Future purchases will show expected profit
        """)
        
        if st.button("Go to Inventory Page"):
            st.session_state.current_page = "Inventory"
            st.rerun()
    
    # Check for products without categories
    if "category" in df.columns:
        uncategorized = df[df["category"].isna() | (df["category"] == "") | (df["category"] == "New Purchase")]
        if not uncategorized.empty:
            st.info(f"💡 {len(uncategorized)} products have no category. Consider categorizing them for better reporting.")
    
    # ==============================
    # EXPORT SECTION
    # ==============================
    st.markdown("---")
    st.markdown("## Export Purchases Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Full Purchases CSV",
            data=csv,
            file_name=f"purchases_full_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        # Export filtered data
        if not filtered_df.equals(df):
            csv_filtered = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Filtered Data CSV",
                data=csv_filtered,
                file_name=f"purchases_filtered_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    # ==============================
    # REFRESH BUTTON
    # ==============================
    st.markdown("---")
    if st.button("Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    purchases_dashboard()