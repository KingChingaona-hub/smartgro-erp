import streamlit as st
import pandas as pd
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


# ==============================
# PURCHASES DASHBOARD
# ==============================
def purchases_dashboard():
    """Purchases Dashboard with analytics"""
    
    st.title("📊 Purchases Dashboard")
    
    df = load_purchases()
    
    if df.empty:
        st.warning("No purchases recorded yet.")
        return
    
    # Load products to get selling prices
    products_df = load_products()
    
    # ==============================
    # DETERMINE COLUMN NAMES
    # ==============================
    
    # Quantity column
    if "quantity_ordered" in df.columns:
        qty_col = "quantity_ordered"
    elif "quantity" in df.columns:
        qty_col = "quantity"
    else:
        qty_col = None
    
    # Cost column
    if "cost_price" in df.columns:
        cost_col = "cost_price"
    elif "cost" in df.columns:
        cost_col = "cost"
    else:
        cost_col = None
    
    # Total cost column
    if "total_cost" in df.columns:
        total_cost_col = "total_cost"
    elif "total" in df.columns:
        total_cost_col = "total"
    else:
        total_cost_col = None
    
    # Product name column
    if "product_name" in df.columns:
        product_col = "product_name"
    elif "name" in df.columns:
        product_col = "name"
    else:
        product_col = None
    
    # ==============================
    # CONVERT ALL NUMERIC COLUMNS TO FLOAT
    # ==============================
    numeric_cols = ["quantity_ordered", "quantity_received", "cost_price", "total_cost", 
                   "quantity", "cost", "total"]
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
            price_dict[name] = to_float(row["price"])
        
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
        st.info("📊 Expected profit calculated using 30% estimated markup (selling prices not found in product database)")
    
    # Calculate total items
    if qty_col:
        total_items = df[qty_col].sum()
    else:
        total_items = 0
    
    # Get number of orders
    if "po_number" in df.columns:
        total_orders = df["po_number"].nunique()
    else:
        total_orders = len(df)
    
    # Calculate profit margin
    profit_margin = (expected_profit / total_purchase_value * 100) if total_purchase_value > 0 else 0
    
    # ==============================
    # DISPLAY METRICS
    # ==============================
    st.markdown("## 💰 Purchases Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Total Purchase Value", f"${total_purchase_value:,.2f}")
    
    with col2:
        st.metric("📈 Expected Profit", f"${expected_profit:,.2f}")
    
    with col3:
        st.metric("📦 Items Purchased", f"{int(total_items):,}")
    
    with col4:
        st.metric("📋 Purchase Orders", total_orders)
    
    st.markdown("---")
    
    # Profit margin
    if profit_margin > 0:
        if profit_margin < 20:
            st.warning(f"⚠️ Expected Profit Margin: {profit_margin:.1f}% (Consider increasing prices or negotiating better costs)")
        elif profit_margin > 40:
            st.success(f"✅ Excellent Expected Profit Margin: {profit_margin:.1f}%")
        else:
            st.info(f"📊 Expected Profit Margin: {profit_margin:.1f}%")
    
    # ==============================
    # SHOW PROFIT BREAKDOWN (if available)
    # ==============================
    if profit_details:
        st.markdown("---")
        st.markdown("## 💰 Expected Profit Breakdown by Product")
        
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
    st.markdown("## 🚚 Supplier Analysis")
    
    if "supplier" in df.columns:
        # Get total purchases per supplier
        if total_cost_col:
            supplier_cost = df.groupby("supplier")[total_cost_col].sum().reset_index()
            supplier_cost.columns = ["Supplier", "Total Purchases"]
        else:
            supplier_cost = pd.DataFrame()
        
        # Get order counts
        if "po_number" in df.columns:
            supplier_orders = df.groupby("supplier")["po_number"].nunique().reset_index()
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
    st.markdown("## 🏆 Top Purchased Products")
    
    if product_col and qty_col:
        top_products = df.groupby(product_col)[qty_col].sum().sort_values(ascending=False).head(10).reset_index()
        top_products.columns = ["Product", "Quantity Purchased"]
        top_products["Quantity Purchased"] = top_products["Quantity Purchased"].astype(int)
        
        st.dataframe(top_products, use_container_width=True, hide_index=True)
    else:
        st.info("Product purchase data not available")
    
    # ==============================
    # RECENT PURCHASES
    # ==============================
    st.markdown("---")
    st.markdown("## 📜 Recent Purchases")
    
    # Select columns for display
    display_cols = []
    if "date_ordered" in df.columns:
        display_cols.append("date_ordered")
    elif "date" in df.columns:
        display_cols.append("date")
    
    if "supplier" in df.columns:
        display_cols.append("supplier")
    
    if product_col:
        display_cols.append(product_col)
    
    if qty_col:
        display_cols.append(qty_col)
    
    if total_cost_col:
        display_cols.append(total_cost_col)
    
    if "status" in df.columns:
        display_cols.append("status")
    
    # Filter to existing columns
    available_cols = [col for col in display_cols if col in df.columns]
    
    if available_cols:
        # Sort by date
        date_col = "date_ordered" if "date_ordered" in df.columns else "date" if "date" in df.columns else None
        if date_col and date_col in df.columns:
            recent_df = df.sort_values(date_col, ascending=False)
        else:
            recent_df = df
        
        # Display
        st.dataframe(
            recent_df[available_cols].head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                total_cost_col: st.column_config.NumberColumn("Total", format="$%.2f") if total_cost_col else None
            }
        )
    else:
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)
    
    # ==============================
    # DATA QUALITY TIPS
    # ==============================
    st.markdown("---")
    st.markdown("## 🔧 Data Quality Tips")
    
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
    
    # ==============================
    # EXPORT SECTION
    # ==============================
    st.markdown("---")
    st.markdown("## 📥 Export Purchases Data")
    
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇ Download Purchases CSV",
        data=csv,
        file_name=f"purchases_report_{pd.Timestamp.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    purchases_dashboard()