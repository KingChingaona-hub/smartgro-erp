import pandas as pd
import streamlit as st
from backend.core.db_adapter import load_products, save_products


# ==============================
# INVENTORY PAGE
# ==============================
def inventory_page():
    
    # Load products
    df = load_products()
    
    st.title("📦 Inventory Management")
    
    # ==============================
    # DISPLAY CURRENT BRANCH
    # ==============================
    current_branch = st.session_state.get("user_branch", "HO")
    st.info(f"📍 Managing inventory for Branch: **{current_branch}**")
    
    # ==============================
    # SMART STOCK ALERTS
    # ==============================
    st.markdown("## ⚠️ Smart Stock Alerts")
    
    if not df.empty and "stock" in df.columns and "reorder_level" in df.columns:
        low_stock = df[df["stock"] <= df["reorder_level"]]
        
        if not low_stock.empty:
            st.error(f"⚠️ {len(low_stock)} products need reordering!")
            st.dataframe(low_stock[["name", "stock", "reorder_level", "price"]], use_container_width=True, hide_index=True)
        else:
            st.success("✅ All products are sufficiently stocked.")
    else:
        st.info("Add products to see stock alerts")
    
    st.markdown("---")
    
    # ==============================
    # SEARCH PRODUCT
    # ==============================
    st.markdown("## 🔍 Search Product")
    
    search = st.text_input("Enter Barcode or Name", key="inventory_search", placeholder="Type to search...")
    
    if search and not df.empty:
        result = df[
            df["barcode"].astype(str).str.contains(search, case=False) |
            df["name"].str.contains(search, case=False)
        ]
        
        if not result.empty:
            st.dataframe(result, use_container_width=True, hide_index=True)
            st.success(f"✅ Found {len(result)} product(s)")
        else:
            st.warning("No product found")
    
    st.markdown("---")
    
    # ==============================
    # ALL PRODUCTS TABLE
    # ==============================
    st.markdown("## 📋 All Products")
    
    if not df.empty:
        # Display all products
        display_cols = ["barcode", "name", "category", "price", "stock", "reorder_level"]
        available_cols = [col for col in display_cols if col in df.columns]
        st.dataframe(df[available_cols], use_container_width=True, hide_index=True)
        st.caption(f"Total products: {len(df)}")
    else:
        st.info("No products in inventory. Add your first product below.")
    
    st.markdown("---")
    
    # ==============================
    # ADD PRODUCT (NO AUTO-RERUN)
    # ==============================
    st.markdown("## ➕ Add Product")
    
    with st.form("add_product_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            barcode = st.text_input("Barcode *", key="add_barcode")
            name = st.text_input("Product Name *", key="add_name")
            category = st.text_input("Category", key="add_category")
            price = st.number_input("Price ($) *", min_value=0.0, step=0.5, key="add_price")
        
        with col2:
            cost = st.number_input("Cost ($)", min_value=0.0, step=0.5, key="add_cost")
            stock = st.number_input("Stock", min_value=0, step=1, key="add_stock")
            reorder_level = st.number_input("Reorder Level", min_value=0, step=1, key="add_reorder")
        
        submitted = st.form_submit_button("➕ Add Product", type="primary", use_container_width=True)
        
        if submitted:
            if barcode and name and price > 0:
                # Check if barcode already exists
                if not df.empty and barcode in df["barcode"].astype(str).values:
                    st.error(f"❌ Barcode '{barcode}' already exists! Please use a unique barcode.")
                else:
                    # Create new product
                    new_row = pd.DataFrame([{
                        "barcode": barcode.strip(),
                        "name": name,
                        "category": category if category else "Uncategorized",
                        "price": price,
                        "cost": cost,
                        "stock": stock,
                        "reorder_level": reorder_level
                    }])
                    
                    # Append to existing dataframe
                    if df.empty:
                        df = new_row
                    else:
                        df = pd.concat([df, new_row], ignore_index=True)
                    
                    # Save to branch-specific file
                    if save_products(df):
                        st.success(f"✅ Product '{name}' added successfully!")
                    else:
                        st.error("❌ Failed to save product. Please check file permissions.")
            else:
                st.error("❌ Barcode, Name, and Price are required fields.")
    
    st.markdown("---")
    
    # ==============================
    # UPDATE PRODUCT
    # ==============================
    st.markdown("## ✏️ Update Product")
    
    if not df.empty:
        # Create a list of product names for selection
        product_names = df["name"].tolist()
        selected_product = st.selectbox("Select Product to Update", product_names, key="update_product_select")
        
        if selected_product:
            # Get current product data
            product_data = df[df["name"] == selected_product].iloc[0]
            
            with st.form("update_product_form", clear_on_submit=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    update_barcode = st.text_input("Barcode", value=product_data["barcode"], key="update_barcode")
                    update_name = st.text_input("Product Name", value=product_data["name"], key="update_name")
                    update_category = st.text_input("Category", value=product_data.get("category", ""), key="update_category")
                    update_price = st.number_input("Price ($)", value=float(product_data["price"]), step=0.5, key="update_price")
                
                with col2:
                    update_cost = st.number_input("Cost ($)", value=float(product_data.get("cost", 0)), step=0.5, key="update_cost")
                    update_stock = st.number_input("Stock", value=int(product_data["stock"]), step=1, key="update_stock")
                    update_reorder = st.number_input("Reorder Level", value=int(product_data["reorder_level"]), step=1, key="update_reorder")
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                        # Find the index of the product to update
                        idx = df[df["name"] == selected_product].index[0]
                        
                        # Update values
                        df.at[idx, "barcode"] = update_barcode.strip()
                        df.at[idx, "name"] = update_name
                        df.at[idx, "category"] = update_category if update_category else "Uncategorized"
                        df.at[idx, "price"] = update_price
                        df.at[idx, "cost"] = update_cost
                        df.at[idx, "stock"] = update_stock
                        df.at[idx, "reorder_level"] = update_reorder
                        
                        # Save to branch-specific file
                        if save_products(df):
                            st.success(f"✅ Product '{update_name}' updated successfully!")
                        else:
                            st.error("❌ Failed to update product.")
                
                with col_btn2:
                    # Delete button with confirmation
                    delete_clicked = st.form_submit_button("🗑️ Delete Product", use_container_width=True)
                    
                    if delete_clicked:
                        # Show warning and confirmation checkbox
                        st.warning("⚠️ Check the box below to confirm deletion")
                        confirm = st.checkbox("I understand this action CANNOT be undone", key="delete_confirm")
                        
                        if confirm:
                            # Remove product from dataframe
                            df = df[df["name"] != selected_product]
                            
                            # Save to branch-specific file
                            if save_products(df):
                                st.success(f"✅ Product '{selected_product}' deleted successfully!")
                                # Refresh the page to show updated list
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete product.")
    else:
        st.info("No products in inventory. Add your first product above.")
    
    # ==============================
    # MANUAL REFRESH BUTTON (User controls refresh)
    # ==============================
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.success("✅ Data refreshed!")
    
    with col2:
        if st.button("🗑️ Clear All Products (Reset Branch)", use_container_width=True):
            confirm = st.checkbox("⚠️ This will DELETE ALL products in this branch!", key="clear_all_confirm")
            if confirm:
                empty_df = pd.DataFrame(columns=[
                    "barcode", "name", "category", "price", "cost", "stock", "reorder_level"
                ])
                save_products(empty_df)
                st.success("✅ All products cleared! Click 'Refresh Data' to see changes.")